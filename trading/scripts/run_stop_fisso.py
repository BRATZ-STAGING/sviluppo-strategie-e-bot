#!/usr/bin/env python3
"""Stop FISSO in dollari su timeframe bassi: 3 e 5 $, obiettivi 1:3 e 1:5.

Specifica dell'utente: opera con 0,01 lotti su XAU, dove 1 punto (es. 3881 ->
3882) vale 1 euro. Quindi "3/5 punti di stop" = 3 e 5 DOLLARI di distanza.

Lo stop non e' piu' strutturale (minimo delle ultime candele) ma un valore
fisso: sono due meccaniche diverse e va misurata questa.

Si usa il segnale come innesco e si ricalcola tutto sullo stop fisso. La banda
di rischio viene disattivata (0,1-100 $) perche' altrimenti filtrerebbe i
segnali in base a uno stop che qui non si usa.
"""
import dataclasses, sys
import numpy as np, pandas as pd
sys.path.insert(0,"/workspace/sviluppo-strategie-e-bot/trading"); sys.path.insert(0,".")
from framework.data import TIMEFRAMES, load_m1, resample_tf
from framework.gestione import esito, chiusura_fine_giornata
from framework.segnali import genera
from framework.taratura import UFFICIALE as T
from ob import order_blocks, dentro_una_zona
pd.set_option("display.width",210)

SPREAD_VERO = 0.63          # misurato sui tick, luglio 2026
STOP = [2.0, 3.0, 5.0]
RR = [3.0, 5.0]

def prova(tf, m1, zone):
    tar = dataclasses.replace(T, tf_ingresso=tf, conferme=(), ritracciamento=(),
                              rischio_min=0.1, rischio_max=100.0,
                              impulso_min=2.0, max_operazioni_giorno=8,
                              attesa_minuti=10)
    righe=[]
    for o in genera(m1, tar, tf_extra=("M33","H12","M12","M66")):
        segno = 1 if o["lato"]=="long" else -1
        # percorsi in DOLLARI, poi rinormalizzati sullo stop fisso
        fav_d = o["fav"]*o["rischio"]
        sfav_d = o["sfav"]*o["rischio"]
        eod_d = o["r_eod"]*o["rischio"]
        rec={"anno":o["anno"],"lato":o["lato"],
             "conf":int(o["c_M33"] and o["c_H12"] and not o["c_M12"]),
             "ob":int(dentro_una_zona(zone,o["time"],o["entry"],segno,2.5))}
        for st in STOP:
            fav, sfav = fav_d/st, sfav_d/st
            costo = SPREAD_VERO/st
            for rr in RR:
                r,mo = esito(fav, sfav, rr, costo=costo)
                if r is None:
                    r = chiusura_fine_giornata(eod_d/st, None, False, float(fav.max()), costo)
                rec[f"r{st:g}_{rr:g}"]=r; rec[f"m{st:g}_{rr:g}"]=mo
        righe.append(rec)
    return pd.DataFrame(righe)

def riepilogo(d, etichetta):
    out=[]
    for st in STOP:
        for rr in RR:
            c,mc=f"r{st:g}_{rr:g}",f"m{st:g}_{rr:g}"
            v=d[c].values; mo=d[mc].values
            per=pd.Series(v).groupby(d.anno.values).sum()
            out.append({"stop":f"{st:g}$","RR":f"1:{rr:g}","n":len(v),
                        "R/op":v.mean(),"R tot":v.sum(),
                        "%obiettivo":(mo==1).mean()*100,"%stop":(mo==0).mean()*100,
                        "anni+":int((per>0).sum())})
    t=pd.DataFrame(out)
    print(f"\n--- {etichetta} ---")
    print(t.to_string(index=False,float_format=lambda x:f"{x:+.3f}"))

if __name__=="__main__":
    m1=load_m1("/workspace/sviluppo-strategie-e-bot/data/XAUUSD_M1")
    zone=order_blocks(resample_tf(m1,"M33"),T.frattale_k,TIMEFRAMES["M33"])
    for tf in sys.argv[1:] or ["M6","M3"]:
        d=prova(tf,m1,zone)
        print(f"\n{'='*78}\ningresso {tf}: {len(d)} segnali "
              f"(spread reale {SPREAD_VERO} $)\n{'='*78}")
        riepilogo(d,"tutti i segnali")
        riepilogo(d[d.conf==1],"con le conferme M33+H12, M12 in ritracciamento")
        riepilogo(d[d.ob==1],"solo dentro un order block M33 (margine 2,5 $)")
        riepilogo(d[(d.conf==1)&(d.ob==1)],"conferme E order block")
        d.to_parquet(f"stopfisso_{tf}.parquet")
