#!/usr/bin/env python3
"""Grafico LIVE da MT5, con i livelli del progetto disegnati sopra.

Quello che Dukascopy non puo' dare: il prezzo in tempo reale. Legge il
terminale MT5 aperto (stesso flusso che vede il broker), calcola a ogni
aggiornamento le zone order block, lo stato della struttura e il VWAP
giornaliero, e serve una pagina che si ridisegna da sola.

    python3 grafico_live.py            poi apri http://127.0.0.1:8765
    python3 grafico_live.py 9000       su un'altra porta

Sul VPS la porta 8080 e' occupata: usarne un'altra e aprirla nel firewall
solo se serve accedervi da fuori (altrimenti resta su 127.0.0.1, piu' sicuro).

Le zone mostrate sono quelle misurate: la RAFFINATA e' la parte che porta il
vantaggio (appendice AJ, +1,342 R/op su sette anni). Una zona NON e' un
segnale da sola (appendice W) e non va usata come ordine limite in attesa
(appendice AA): serve il segnale della strategia con la struttura concorde.
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, resample_tf                # noqa: E402
from framework.structure import trend_state_series                # noqa: E402
from framework.taratura import UFFICIALE as T                     # noqa: E402
from framework.vwap import anchored_vwap                          # noqa: E402

from export_lab import zone_ob                                    # noqa: E402

TF_ZONE = ["M6", "M12", "M33", "M66", "H2", "H3", "H6", "H12"]
VALIDITA = 30              # candele di vita di una zona, come negli studi
BARRE_M1 = 60_000          # ~6 settimane: basta per struttura e zone
AGGIORNA = 3.0             # secondi fra un ricalcolo e l'altro

_dati = {"pronto": False, "errore": "in attesa del primo aggiornamento"}
_lock = threading.Lock()


def leggi_mt5():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise RuntimeError(f"MT5 non risponde: {mt5.last_error()}")
    try:
        nomi = [s.name for s in mt5.symbols_get()
                if "XAU" in s.name.upper() or "GOLD" in s.name.upper()]
        if not nomi:
            raise RuntimeError("nessun simbolo XAU/GOLD presso questo broker")
        simbolo = "XAUUSD" if "XAUUSD" in nomi else nomi[0]
        mt5.symbol_select(simbolo, True)
        barre = mt5.copy_rates_from_pos(simbolo, mt5.TIMEFRAME_M1, 0, BARRE_M1)
        tick = mt5.symbol_info_tick(simbolo)
    finally:
        mt5.shutdown()
    if barre is None or len(barre) == 0:
        raise RuntimeError("il terminale non ha restituito barre M1")
    df = pd.DataFrame(barre)
    df["ts"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("ts")[["open", "high", "low", "close", "tick_volume"]]
    df.columns = ["open", "high", "low", "close", "volume"]
    bid = float(tick.bid) if tick else float(df.close.iloc[-1])
    ask = float(tick.ask) if tick else bid
    return simbolo, df, bid, ask


def calcola():
    simbolo, m1, bid, ask = leggi_mt5()
    out = {"simbolo": simbolo, "bid": bid, "ask": ask,
           "spread": round(ask - bid, 3),
           "ora": pd.Timestamp.now("UTC").strftime("%H:%M:%S"),
           "ultima_candela": m1.index[-1].strftime("%d/%m %H:%M"),
           "serie": {}, "zone": [], "struttura": {}, "pronto": True}
    for tf in ("M6", "M12", "M33", "M66", "H2", "H3", "H6"):
        s = resample_tf(m1, tf).tail(400)
        v = anchored_vwap(s, "day") if tf == "M6" else None
        out["serie"][tf] = {
            "t": [int(x.timestamp() * 1000) for x in s.index],
            "o": [round(x, 2) for x in s.open], "h": [round(x, 2) for x in s.high],
            "l": [round(x, 2) for x in s.low], "c": [round(x, 2) for x in s.close],
            "v": ([None if np.isnan(x) else round(float(x), 2) for x in v]
                  if v is not None else None)}
    for tf in TF_ZONE:
        tfd = resample_tf(m1, tf)
        passo = pd.Timedelta(TIMEFRAMES[tf])
        st = trend_state_series(tfd, T.frattale_k, passo)
        out["struttura"][tf] = int(st.iloc[-1]) if len(st) else 0
        z = zone_ob(tfd, T.frattale_k, passo)
        if z.empty:
            continue
        adesso = tfd.index[-1] + passo
        # la scadenza va ricalcolata: zone_ob la tronca all'ultima candela,
        # quindi al bordo destro le zone appena nate sembrerebbero scadute
        scad = z.attiva_da + VALIDITA * passo
        vive = z[(z.attiva_da <= adesso) & (scad > adesso)
                 & (z.invalidata_il.isna() | (z.invalidata_il > adesso))]
        for i, r in vive.iterrows():
            out["zone"].append({
                "tf": tf, "lato": int(r.lato),
                "basso": round(float(r.basso), 2), "alto": round(float(r.alto), 2),
                "rbasso": None if not np.isfinite(r.rbasso) else round(float(r.rbasso), 2),
                "ralto": None if not np.isfinite(r.ralto) else round(float(r.ralto), 2),
                "da": r.attiva_da.strftime("%d/%m %H:%M"),
                "scade": scad[i].strftime("%d/%m %H:%M"),
                "dist": round(bid - r.alto if r.lato == 1 else r.basso - bid, 2)})
    out["zone"].sort(key=lambda x: abs(x["dist"]))
    out["profilo"] = profilo_sessioni(m1)
    return out


SESSIONI = {"asia": (0, 7), "london": (7, 12), "ny": (12, 21), "late": (21, 24)}
BIN = 0.5                  # larghezza dei livelli di prezzo, in dollari


def profilo_sessioni(m1):
    """Volume scambiato per livello di prezzo, diviso per sessione UTC.

    Solo la giornata corrente: e' il profilo che serve a leggere dove il
    mercato ha lavorato oggi, non una media storica.
    """
    giorno = m1.index[-1].normalize()
    d = m1[m1.index >= giorno]
    if d.empty:
        return None
    tipico = ((d.high + d.low + d.close) / 3).values
    vol = d.volume.values.astype(float)
    vol[~np.isfinite(vol) | (vol <= 0)] = 1.0
    liv = np.round(tipico / BIN).astype(np.int64)
    ore = d.index.hour.values
    unici = np.unique(liv)
    out = {"prezzi": [round(float(u * BIN), 2) for u in unici]}
    somme = {}
    for nome, (a, b) in SESSIONI.items():
        m = (ore >= a) & (ore < b)
        s = np.zeros(len(unici))
        if m.any():
            np.add.at(s, np.searchsorted(unici, liv[m]), vol[m])
        somme[nome] = s
    # il volume e' in unita' diverse a seconda della fonte (conteggio tick da
    # MT5, decimale nello storico): si normalizza a 100, contano le proporzioni
    massimo = max(1e-12, float(sum(somme.values()).max()))
    for nome, s in somme.items():
        out[nome] = [round(float(x) / massimo * 100, 2) for x in s]
    out["giorno"] = giorno.strftime("%d/%m")
    return out


def aggiorna_sempre():
    while True:
        try:
            d = calcola()
        except Exception as e:                       # il terminale puo' chiudersi
            d = {"pronto": False, "errore": str(e)}
        with _lock:
            _dati.clear()
            _dati.update(d)
        time.sleep(AGGIORNA)


PAGINA = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>XAUUSD live</title><style>
:root{--g:#151318;--p:#1C1A20;--i:#E9E4DB;--i3:#6E675F;--l:#2C2932;
--up:#4EA57F;--dn:#C25A46;--br:#C99A3E;--vw:#8E7BD0;
--m:ui-monospace,Menlo,Consolas,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--g);color:var(--i);
font:14px/1.5 system-ui,sans-serif}
.w{max-width:1200px;margin:0 auto;padding:12px;display:flex;flex-direction:column;gap:10px}
h1{margin:0;font:600 16px var(--m)}h1 span{color:var(--br)}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.pill{font:11px var(--m);padding:4px 9px;border:1px solid var(--l);border-radius:99px;
background:var(--p);color:var(--i3)}.pill b{color:var(--i)}
.seg{display:flex;gap:3px;background:var(--p);border:1px solid var(--l);border-radius:9px;padding:3px}
.seg button{border:0;background:none;color:var(--i3);font:12px var(--m);
padding:5px 10px;border-radius:6px;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--br);color:var(--g);font-weight:600}
canvas{display:block;width:100%;height:440px;background:var(--p);
border:1px solid var(--l);border-radius:12px}
table{width:100%;border-collapse:collapse;font:12px var(--m)}
th,td{text-align:right;padding:6px 8px;border-bottom:1px solid var(--l)}
th{color:var(--i3);font-weight:500;text-align:right}td:first-child,th:first-child{text-align:left}
.buy{color:var(--up)}.sell{color:var(--dn)}
.note{color:var(--i3);font-size:12px}
</style></head><body><div class="w">
<h1>XAUUSD <span>·</span> live da MT5</h1>
<div class="bar" id="bar"></div>
<div class="bar"><div class="seg" id="tf"></div><div class="seg" id="vp"></div><div class="seg" id="et"></div></div>
<canvas id="c"></canvas>
<table id="tab"></table>
<p class="note">La colonna <b>raffinata</b> e' la parte che porta il vantaggio misurato.
Una zona non e' un segnale da sola e non va usata come limite in attesa: serve il
segnale della strategia con la struttura concorde.</p>
</div><script>
const TF=["M6","M12","M33","M66","H2","H3","H6"];let tf="M33",D=null,vp=1,etich=0,curY=null,fissate=new Set();
const el=i=>document.getElementById(i);
el("tf").innerHTML=TF.map(t=>`<button aria-pressed="${t===tf}">${t}</button>`).join("");
[...el("tf").children].forEach((b,k)=>b.onclick=()=>{tf=TF[k];
[...el("tf").children].forEach((x,j)=>x.setAttribute("aria-pressed",j===k));draw();});
el("vp").innerHTML=["profilo off","profilo sessioni"].map((t,k)=>
 `<button aria-pressed="${k===vp}">${t}</button>`).join("");
[...el("vp").children].forEach((b,k)=>b.onclick=()=>{vp=k;
 [...el("vp").children].forEach((x,j)=>x.setAttribute("aria-pressed",j===k));draw();});
el("et").innerHTML=["nomi al passaggio","nomi sempre"].map((t,k)=>
 `<button aria-pressed="${k===etich}">${t}</button>`).join("");
[...el("et").children].forEach((b,k)=>b.onclick=()=>{etich=k;
 [...el("et").children].forEach((x,j)=>x.setAttribute("aria-pressed",j===k));draw();});
// il puntatore decide quali nomi mostrare; il clic li fissa
const cv0=el("c");
cv0.addEventListener("mousemove",e=>{curY=e.clientY-cv0.getBoundingClientRect().top;draw();});
cv0.addEventListener("mouseleave",()=>{curY=null;draw();});
cv0.addEventListener("click",()=>{if(!D||!D.zone)return;
 D.zone.forEach((z,i)=>{if(z._sotto){fissate.has(i)?fissate.delete(i):fissate.add(i);}});
 draw();});
const stat=v=>v===1?["rialzista","buy"]:v===-1?["ribassista","sell"]:["neutra",""];
async function tira(){try{const r=await fetch("/api/dati");D=await r.json();draw();}
catch(e){}finally{setTimeout(tira,3000);}}
function draw(){
 const b=el("bar");
 if(!D||!D.pronto){b.innerHTML=`<span class="pill">${D?D.errore:"connessione..."}</span>`;return;}
 b.innerHTML=`<span class="pill">bid <b>${D.bid.toFixed(2)}</b></span>
  <span class="pill">spread <b>${D.spread.toFixed(2)} $</b></span>
  <span class="pill">candela ${D.ultima_candela}</span>
  <span class="pill">agg. ${D.ora} UTC</span>`+
  Object.entries(D.struttura).map(([k,v])=>{const[s,c]=stat(v);
   return `<span class="pill">${k} <b class="${c}">${s}</b></span>`}).join("");
 const s=D.serie[tf];if(!s)return;
 const cv=el("c"),x=cv.getContext("2d"),dpr=devicePixelRatio||1;
 const W=cv.clientWidth,H=cv.clientHeight;cv.width=W*dpr;cv.height=H*dpr;
 x.setTransform(dpr,0,0,dpr,0,0);x.clearRect(0,0,W,H);
 const n=s.c.length,vis=Math.min(n,180),i0=n-vis;
 const zs=D.zone;
 let lo=Math.min(...s.l.slice(i0)),hi=Math.max(...s.h.slice(i0));
 zs.forEach(z=>{if(z.basso>lo-200&&z.alto<hi+200){lo=Math.min(lo,z.basso);hi=Math.max(hi,z.alto);}});
 const pad=(hi-lo)*.06||1;lo-=pad;hi+=pad;
 const pl=8,pr=62,pt=10,pb=8,pw=W-pl-pr,ph=H-pt-pb;
 const X=i=>pl+(i-i0)/Math.max(vis-1,1)*pw, Y=p=>pt+(hi-p)/(hi-lo)*ph;
 const F="11px "+getComputedStyle(document.body).getPropertyValue("--m");

 // --- profilo volume: a SINISTRA, sotto a tutto il resto -------------------
 let poc=null, vuoti=[];
 if(D.profilo){const P=D.profilo,SS=["asia","london","ny","late"],
   CO={asia:"rgba(142,123,208,.50)",london:"rgba(201,154,62,.50)",
       ny:"rgba(78,165,127,.50)",late:"rgba(110,103,95,.50)"};
  const tot=P.prezzi.map((_,i)=>SS.reduce((a,s2)=>a+P[s2][i],0));
  const max=Math.max(...tot,0);
  if(max>0){
   poc=P.prezzi[tot.indexOf(max)];
   // zone di vuoto: livelli scambiati poco, uniti in fasce contigue
   const soglia=max*.15; let ini=null;
   P.prezzi.forEach((p,i)=>{const sotto=tot[i]<soglia&&tot[i]>0;
    if(sotto&&ini===null)ini=p; if(!sotto&&ini!==null){vuoti.push([ini,P.prezzi[i-1]]);ini=null;}});
   if(ini!==null)vuoti.push([ini,P.prezzi[P.prezzi.length-1]]);
   vuoti=vuoti.filter(v=>v[1]-v[0]>=1.5);           // solo i vuoti veri
   if(vp){const lw=pw*.20, hb=Math.max(2,ph/((hi-lo)/0.5));
    // le fasce di vuoto attraversano tutto il grafico
    x.fillStyle="rgba(233,228,219,.045)";
    vuoti.forEach(v=>x.fillRect(pl,Y(v[1]),pw,Math.max(Y(v[0])-Y(v[1]),1.5)));
    P.prezzi.forEach((p,i)=>{if(p<lo||p>hi)return;let x0=pl;
     SS.forEach(s2=>{const v=P[s2][i];if(!v)return;const w2=v/max*lw;
      x.fillStyle=CO[s2];x.fillRect(x0,Y(p)-hb/2,w2,hb);x0+=w2;});});
    // il livello piu' scambiato, esteso su tutto il grafico
    const yp=Math.round(Y(poc))+.5;
    x.strokeStyle="rgba(233,228,219,.55)";x.lineWidth=1;x.setLineDash([2,4]);
    x.beginPath();x.moveTo(pl,yp);x.lineTo(pl+pw,yp);x.stroke();x.setLineDash([]);
    x.font=F;x.textAlign="left";x.textBaseline="bottom";x.fillStyle="#8E877E";
    x.fillText("volume massimo "+poc.toFixed(2),pl+4,yp-2);
    x.textAlign="left";x.textBaseline="top";
    x.fillText("profilo "+P.giorno+" · asia londra ny sera",pl+4,pt+4);}}}

 // --- zone: bande, senza etichetta (le etichette vanno a destra, in fondo) --
 zs.forEach(z=>{const y1=Y(z.alto),y2=Y(z.basso),up=z.lato===1;
  x.fillStyle=up?"rgba(78,165,127,.10)":"rgba(194,90,70,.10)";
  x.fillRect(pl,Math.min(y1,y2),pw,Math.abs(y2-y1));
  if(z.rbasso!==null){const r1=Y(z.ralto),r2=Y(z.rbasso);
   x.fillStyle=up?"rgba(78,165,127,.32)":"rgba(194,90,70,.32)";
   x.fillRect(pl,Math.min(r1,r2),pw,Math.max(Math.abs(r2-r1),1.5));}
  z._sotto = curY!==null && curY>=Math.min(y1,y2)-2 && curY<=Math.max(y1,y2)+2;
  if(z._sotto){x.strokeStyle=up?"#4EA57F":"#C25A46";x.lineWidth=1;
   x.strokeRect(pl+.5,Math.min(y1,y2)+.5,pw-1,Math.max(Math.abs(y2-y1)-1,1));}});

 if(s.v){x.strokeStyle=getComputedStyle(document.body).getPropertyValue("--vw");
  x.lineWidth=1.6;x.beginPath();let pen=false;
  for(let i=i0;i<n;i++){if(s.v[i]===null){pen=false;continue;}
   pen?x.lineTo(X(i),Y(s.v[i])):(x.moveTo(X(i),Y(s.v[i])),pen=true);}x.stroke();}
 const bw=Math.max(1.5,Math.min(pw/vis*.66,9));
 for(let i=i0;i<n;i++){const up=s.c[i]>=s.o[i];
  x.strokeStyle=x.fillStyle=up?"#4EA57F":"#C25A46";x.lineWidth=1;
  x.beginPath();x.moveTo(Math.round(X(i))+.5,Y(s.h[i]));x.lineTo(Math.round(X(i))+.5,Y(s.l[i]));x.stroke();
  const yo=Y(s.o[i]),yc=Y(s.c[i]);
  x.fillRect(X(i)-bw/2,Math.min(yo,yc),bw,Math.max(Math.abs(yc-yo),1));}

 const yb=Math.round(Y(D.bid))+.5;
 x.strokeStyle="#C99A3E";x.lineWidth=1;x.setLineDash([4,3]);
 x.beginPath();x.moveTo(pl,yb);x.lineTo(pl+pw,yb);x.stroke();x.setLineDash([]);
 x.fillStyle="#C99A3E";x.font=F;x.textAlign="left";
 x.textBaseline="middle";x.fillText(D.bid.toFixed(2),pl+pw+6,yb);

 // --- etichette: solo la banda sotto il puntatore, o quelle fissate col clic
 x.font=F;x.textBaseline="middle";x.textAlign="right";
 const scelte=zs.filter((z,i)=>etich===1||z._sotto||fissate.has(i));
 if(!scelte.length){x.fillStyle="#6E675F";x.textAlign="right";x.textBaseline="top";
  x.fillText(zs.length+" zone · passa sopra una banda per il nome, clic per fissarlo",
             pl+pw-4,pt+4);x.textBaseline="middle";}
 const et=scelte.map(z=>({t:z.tf+" "+(z.lato===1?"BUY":"SELL")+"  "
    +z.basso.toFixed(2)+"–"+z.alto.toFixed(2),up:z.lato===1,
   y:(Y(z.alto)+Y(z.basso))/2})).sort((a,b)=>a.y-b.y);
 const H0=16;                                  // altezza minima fra etichette
 for(let k=1;k<et.length;k++)                  // scendendo: spingi in giu'
  if(et[k].y-et[k-1].y<H0) et[k].y=et[k-1].y+H0;
 for(let k=et.length-1;k>0;k--)                // risalendo: rientra nel bordo
  if(et[k].y>pt+ph-8){et[k].y=pt+ph-8;
   if(et[k].y-et[k-1].y<H0) et[k-1].y=et[k].y-H0;}
 et.forEach(e=>{const w=x.measureText(e.t).width+9, xr=pl+pw-4;
  x.fillStyle=e.up?"rgba(78,165,127,.22)":"rgba(194,90,70,.22)";
  x.fillRect(xr-w,e.y-8,w,16);
  x.fillStyle=e.up?"#4EA57F":"#C25A46";x.fillText(e.t,xr-5,e.y);});
 el("tab").innerHTML="<tr><th>tf</th><th>lato</th><th>zona</th><th>raffinata</th>"+
  "<th>distanza</th><th>attiva da</th><th>scade</th></tr>"+
  (D.zone.length?D.zone.map(z=>`<tr><td>${z.tf}</td>
   <td class="${z.lato===1?"buy":"sell"}">${z.lato===1?"BUY":"SELL"}</td>
   <td>${z.basso.toFixed(2)}–${z.alto.toFixed(2)}</td>
   <td>${z.rbasso===null?"—":z.rbasso.toFixed(2)+"–"+z.ralto.toFixed(2)}</td>
   <td>${z.dist>0?"+":""}${z.dist.toFixed(2)}</td><td>${z.da}</td><td>${z.scade}</td></tr>`).join("")
   :`<tr><td colspan="7" style="text-align:center;color:var(--i3)">nessuna zona attiva</td></tr>`);
}
addEventListener("resize",draw);tira();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/dati"):
            with _lock:
                corpo = json.dumps(_dati).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            corpo = PAGINA.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a):
        pass                                   # niente rumore sul terminale


def main():
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    threading.Thread(target=aggiorna_sempre, daemon=True).start()
    print(f"grafico live su http://127.0.0.1:{porta}  (CTRL+C per fermare)")
    HTTPServer(("127.0.0.1", porta), Handler).serve_forever()


if __name__ == "__main__":
    main()
