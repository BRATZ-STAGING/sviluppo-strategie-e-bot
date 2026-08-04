#!/usr/bin/env python3
"""Appendice BL: l'ORB sull'indice fino a OGGI, con lo scarto denaro-lettera VERO.

Le appendici BJ e BK hanno lasciato due buchi, e questo script li chiude
entrambi.

BUCO 1 — i dati finivano nel 2018. Quindi non si poteva rispondere alla
domanda che conta: l'ORB funziona ANCORA? Crabel dice che il decadimento e'
recente, e il periodo in cui lo colloca e' proprio quello che mancava. Qui si
arriva a oggi con Dukascopy (stessa fonte dell'oro, gia' validata).

BUCO 2 — il costo era un'ipotesi. In BK il verdetto cambiava segno fra 0,25 e
0,50 punti tondi: con un vantaggio lordo di 0,05 R/op e il pareggio a 0,32, il
risultato ERA l'ipotesi sui costi. Qui il costo non si ipotizza: si scarica.
Ogni minuto ha il suo BID e il suo ASK, e l'esecuzione li usa per quel che
sono:
  - compro solo quando la **lettera** raggiunge la soglia, e pago la lettera;
  - vendo solo quando il **denaro** la raggiunge, e incasso il denaro;
  - chiudo dalla parte sfavorevole, sempre.
Cosi' lo spread lo paghi davvero, e non c'e' nessun numero da difendere.

I livelli (apertura, Stretch, NR4) si calcolano sul BID, che e' la serie
"prezzo" di riferimento; il lato lettera serve solo all'esecuzione.

IL LORDO NON SI STIMA, SI MISURA. La prima versione ricostruiva il lordo
sommando lo spread al netto. E' un'approssimazione: a spread zero cambia anche
il MINUTO in cui l'ordine scatta. Qui il lordo e' una seconda passata completa
con il solo BID su tutti e due i lati — cioe' esattamente il modello a serie
unica delle appendici BJ/BK, confrontabile con HistData riga per riga.

CONTROLLO DI QUALITA' DEL DATO, prima di qualunque risultato. Il feed indice di
Dukascopy nei primi anni e' povero: nel 2012 la serie ASK e' una COPIA della
BID (scarto identicamente nullo, nessun mercato a due lati) e il reticolo dei
minuti e' bucato. Una serie bucata non registra tutti gli estremi: lo Stretch
esce piu' piccolo del vero, il rischio si rimpicciolisce, gli stop non vengono
toccati e il risultato in R si gonfia da solo. Percio' ogni giornata deve
superare due soglie misurabili prima di entrare nel campione:
  - copertura: almeno il 95% dei minuti della sessione ha scambi;
  - mercato a due lati: lettera > denaro in almeno il 90% dei minuti.
Le giornate scartate vengono contate e stampate, cosi' il buco si vede.

IPOTESI PRE-REGISTRATE:
  A. il vantaggio LORDO misurato in BK (+0,060 ricerca / +0,042 verifica) si
     ritrova su una fonte diversa nel periodo comune 2012-2018. Se no, uno dei
     due dati e' sbagliato e prima di tutto va capito quale.
  B. quel vantaggio lordo esiste ancora nel 2019-2026.
  C. con lo spread vero il netto e' negativo (previsione esplicita: lo spread
     misurato sul CFD e' ~0,51 punti, il pareggio di BK cade a 0,32).
Se C viene confermata, la conclusione non e' "l'ORB non esiste" ma "l'ORB non
si paga con questo strumento", che e' un'affermazione diversa e piu' utile.

Uso: python3 run_orb_indice_vero.py [USA500IDXUSD]
Scrive docs/studies/dati/orb_indice_vero.parquet
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATI = os.environ.get("IDX_OUT", os.path.join(ROOT, "..", "dati_grezzi", "indici"))
FUSO = "America/New_York"
APERTURA, CHIUSURA = (9, 30), (16, 0)
GIORNI_STRETCH = 10
MIN_COPERTURA = 0.95        # quota di minuti della sessione con scambi
MIN_DUE_LATI = 0.90         # quota di minuti con lettera > denaro
MAX_GIORNI_FINESTRA = 25    # i 10 giorni dello Stretch devono stare vicini
RISCHIO_CONTO = 0.01
RICERCA, VERIFICA = (2012, 2018), (2019, 2026)


def carica(simbolo):
    """BID e ASK allineati sullo stesso minuto, in ora di New York.

    Niente filtro sul volume qui: per misurare la COPERTURA di una giornata
    servono anche i minuti vuoti, che sono l'informazione da pesare.
    """
    fuori = {}
    for lato in ("BID", "ASK"):
        f = sorted(glob.glob(os.path.join(DATI, simbolo, f"{lato}_*.parquet")))
        if not f:
            raise SystemExit(f"manca {lato} in {os.path.join(DATI, simbolo)}")
        d = pd.concat([pd.read_parquet(x) for x in f]).sort_index()
        fuori[lato] = d[~d.index.duplicated(keep="first")]
    b, a = fuori["BID"], fuori["ASK"]
    comune = b.index.intersection(a.index)
    b, a = b.loc[comune], a.loc[comune]
    ny = comune.tz_convert(FUSO)
    o = ny.hour * 60 + ny.minute
    dentro = ((o >= APERTURA[0] * 60 + APERTURA[1])
              & (o <= CHIUSURA[0] * 60 + CHIUSURA[1]))
    b, a = b[dentro], a[dentro]
    giorno = pd.Series(ny[dentro].normalize().tz_localize(None), index=b.index)
    return b, a, giorno


def qualita(b, a, giorno):
    """Una riga per giornata con i due indicatori di salute del dato."""
    scambi = (b.volume.values > 0) & (a.volume.values > 0)
    due = (a.close.values - b.close.values) > 0
    q = pd.DataFrame({"g": giorno.values, "scambi": scambi, "due": due})
    return q.groupby("g").agg(minuti=("scambi", "size"),
                              copertura=("scambi", "mean"),
                              due_lati=("due", "mean"))


def profilo(b, giorno, buoni):
    """Apertura, estremi, Stretch e NR4, sulle sole giornate sane.

    Lo Stretch e' la media a 10 giorni del minore fra |apertura - massimo| e
    |apertura - minimo|, sempre spostata di un giorno (mai il giorno in corso).
    Con una copertura a buchi i 10 giorni possono distare mesi: in quel caso il
    livello non ha senso e la giornata si salta.
    """
    v = b[b.volume.values > 0]
    gv = giorno[b.volume.values > 0]
    g = v.groupby(gv.values)
    d = pd.DataFrame({"apertura": g.open.first(), "massimo": g.high.max(),
                      "minimo": g.low.min()})
    d = d.loc[d.index.intersection(buoni)].sort_index()
    minore = np.minimum((d.apertura - d.massimo).abs(),
                        (d.apertura - d.minimo).abs())
    d["stretch"] = minore.rolling(GIORNI_STRETCH).mean().shift(1)
    giorni = pd.Series(d.index, index=d.index)
    span = (giorni - giorni.shift(GIORNI_STRETCH)).dt.days
    d.loc[span > MAX_GIORNI_FINESTRA, "stretch"] = np.nan
    r = d.massimo - d.minimo
    d["NR4"] = (r == r.rolling(4).min()).shift(1).fillna(False).astype(bool)
    return d


def percorri(bh, bl, bc, ah, al, ac, sopra, sotto, obiettivo):
    """Un giorno, con i due lati del prezzo usati come si usano davvero.

    Long: entra quando la LETTERA tocca la soglia sopra (compro caro), esce sul
    DENARO (vendo a sconto). Short: specularmente. Lo stop e' l'ordine opposto,
    come in Crabel. A parita' di minuto lo stop prevale sull'obiettivo.

    Passando il solo BID su tutti e due i lati si ottiene la stessa cosa a
    spread zero, cioe' il LORDO.
    """
    su = np.flatnonzero(ah >= sopra)              # la lettera rompe verso l'alto
    giu = np.flatnonzero(bl <= sotto)             # il denaro rompe verso il basso
    k_su = su[0] if len(su) else None
    k_giu = giu[0] if len(giu) else None
    if k_su is None and k_giu is None:
        return None
    if k_giu is None or (k_su is not None and k_su <= k_giu):
        verso, k, entry, stop = 1, k_su, sopra, sotto
    else:
        verso, k, entry, stop = -1, k_giu, sotto, sopra
    rischio = abs(entry - stop)
    if rischio <= 0:
        return None
    j = k + 1
    if len(bc) - j < 2:
        return None
    if verso == 1:
        k_stop = np.flatnonzero(bl[j:] <= stop)   # lo stop del long scatta sul denaro
        bers = entry + obiettivo * rischio if obiettivo else None
        k_tp = np.flatnonzero(bh[j:] >= bers) if bers else []
        finale = bc[-1]
    else:
        k_stop = np.flatnonzero(ah[j:] >= stop)   # lo stop dello short scatta sulla lettera
        bers = entry - obiettivo * rischio if obiettivo else None
        k_tp = np.flatnonzero(al[j:] <= bers) if bers else []
        finale = ac[-1]
    ks = k_stop[0] if len(k_stop) else None
    kt = k_tp[0] if len(k_tp) else None
    if ks is not None and (kt is None or ks <= kt):
        netto, motivo = (stop - entry) * verso, "stop"
    elif kt is not None:
        netto, motivo = (bers - entry) * verso, "obiettivo"
    else:
        netto, motivo = (finale - entry) * verso, "chiusura"
    return {"verso": verso, "rischio": float(rischio),
            "netto": float(netto) / rischio, "motivo": motivo}


def un_lato(simbolo):
    """Il solo LORDO, su una serie a un lato, per arrivare fino al 2026.

    Lo scarico ha lasciato anni con un lato solo (2022, 2024 e 2026 hanno la
    lettera, il 2025 il denaro). Il costo li' non si puo' misurare, ma il
    vantaggio LORDO si': serve una serie di prezzi sola, e denaro o lettera
    danno lo stesso risultato a meno di mezzo punto su un rischio di quindici.
    Vale come risposta alla domanda "il vantaggio esiste ANCORA", non come
    risposta sul netto. Resta il filtro di copertura: una serie bucata gonfia
    il risultato da sola.
    """
    fuori = []
    for f in sorted(glob.glob(os.path.join(DATI, simbolo, "*_*.parquet"))):
        lato, anno = os.path.basename(f)[:-8].split("_")
        fuori.append((int(anno), lato, f))
    per_anno = {}
    for anno, lato, f in fuori:
        d = pd.read_parquet(f)
        if anno not in per_anno or len(d) > len(per_anno[anno][1]):
            per_anno[anno] = (lato, d)
    righe = []
    for anno in sorted(per_anno):
        lato, d = per_anno[anno]
        d = d[~d.index.duplicated(keep="first")]
        ny = d.index.tz_convert(FUSO)
        o = ny.hour * 60 + ny.minute
        dentro = ((o >= APERTURA[0] * 60 + APERTURA[1])
                  & (o <= CHIUSURA[0] * 60 + CHIUSURA[1]))
        d = d[dentro]
        g = pd.Series(ny[dentro].normalize().tz_localize(None), index=d.index)
        cop = pd.Series(d.volume.values > 0, index=g.values).groupby(level=0).mean()
        sane = cop[cop >= MIN_COPERTURA].index
        p = profilo(d, g, sane)
        v = d[d.volume.values > 0]
        gv = g[d.volume.values > 0]
        for gg, bg in v.groupby(gv.values):
            if gg not in p.index:
                continue
            r = p.loc[gg]
            if not np.isfinite(r.stretch) or r.stretch <= 0:
                continue
            bv = (bg.high.values, bg.low.values, bg.close.values)
            e = percorri(*bv, *bv, r.apertura + r.stretch, r.apertura - r.stretch, None)
            if e is not None:
                righe.append({"anno": anno, "lato": lato, "giorno": gg,
                              "rischio": e["rischio"], "lordo": e["netto"]})
    return pd.DataFrame(righe)


def main():
    simbolo = sys.argv[1] if len(sys.argv) > 1 else "USA500IDXUSD"
    b, a, giorno = carica(simbolo)
    q = qualita(b, a, giorno)
    sane = q[(q.copertura >= MIN_COPERTURA) & (q.due_lati >= MIN_DUE_LATI)]
    print(f"{simbolo}: {b.index.min():%Y-%m-%d} -> {b.index.max():%Y-%m-%d}, "
          f"{len(q)} giornate scaricate, {len(sane)} sane", flush=True)

    q["anno"] = q.index.year
    sp = pd.Series((a.close.values - b.close.values), index=giorno.values)
    sq = sp[np.isin(sp.index, sane.index)]
    print("\n=== qualita' del dato e spread reale, anno per anno")
    tq = q.groupby("anno").agg(gg=("copertura", "size"), sane=("copertura", "size"))
    tq["sane"] = sane.groupby(sane.index.year).size().reindex(tq.index).fillna(0).astype(int)
    tq["copertura"] = q.groupby("anno").copertura.median()
    tq["due_lati"] = q.groupby("anno").due_lati.median()
    tq["spread_med"] = sq.groupby(sq.index.year).median().reindex(tq.index)
    tq["spread_medio"] = sq.groupby(sq.index.year).mean().reindex(tq.index)
    print(tq.round(3).to_string())

    d = profilo(b, giorno, sane.index)
    v = b[b.volume.values > 0]
    va = a[b.volume.values > 0]
    gv = giorno[b.volume.values > 0]
    gb, ga = v.groupby(gv.values), va.groupby(gv.values)
    righe = []
    for g, bg in gb:
        if g not in d.index:
            continue
        riga = d.loc[g]
        st = riga.stretch
        if not np.isfinite(st) or st <= 0:
            continue
        ag = ga.get_group(g)
        bv = (bg.high.values, bg.low.values, bg.close.values)
        av = (ag.high.values, ag.low.values, ag.close.values)
        spg = float(np.median(ag.close.values - bg.close.values))
        for eti, ob in [("chiusura", None), ("1:1", 1.0)]:
            e = percorri(*bv, *av, riga.apertura + st, riga.apertura - st, ob)
            l = percorri(*bv, *bv, riga.apertura + st, riga.apertura - st, ob)
            if e is None or l is None:
                continue
            righe.append({"giorno": g, "anno": g.year, "uscita": eti,
                          "NR4": bool(riga.NR4), "spread": spg,
                          "lordo": l["netto"], "lordo_ric": e["netto"] + spg / e["rischio"],
                          "costo_su_rischio": spg / e["rischio"], **e})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "orb_indice_vero.parquet"), index=False)
    pd.set_option("display.width", 230)

    def conto(x):
        if not len(x):
            return None
        anni = x.anno.nunique()
        pl, pn = x.lordo.groupby(x.anno).sum(), x.netto.groupby(x.anno).sum()
        return {"op": len(x), "op/anno": len(x) / anni,
                "lordo R/op": x.lordo.mean(), "netto R/op": x.netto.mean(),
                "netto R": x.netto.sum(),
                "%anno": x.netto.sum() * RISCHIO_CONTO * 100 / anni,
                "anni+ lordo": int((pl > 0).sum()), "anni+ netto": int((pn > 0).sum()),
                "anni": anni}

    def tabella(p):
        f = []
        for eti, x in [("tutti i giorni", p), ("NR4", p[p.NR4])]:
            c = conto(x)
            if c:
                f.append({"selezione": eti, **c})
        return pd.DataFrame(f).set_index("selezione")

    print("\n=== ipotesi A e B: uscita a fine sessione, lordo contro netto vero")
    for eti, (da, aa) in [("ricerca", RICERCA), ("verifica", VERIFICA)]:
        p = t[(t.anno >= da) & (t.anno <= aa) & (t.uscita == "chiusura")]
        if not len(p):
            continue
        print(f"\n  {eti} {da}-{aa} (anni disponibili: "
              f"{', '.join(map(str, sorted(p.anno.unique())))})")
        print(tabella(p).round(3).to_string())

    print("\n=== ipotesi C: obiettivo 1:1 (TP e stop, nessun pareggio)")
    for eti, (da, aa) in [("ricerca", RICERCA), ("verifica", VERIFICA)]:
        p = t[(t.anno >= da) & (t.anno <= aa) & (t.uscita == "1:1")]
        if not len(p):
            continue
        print(f"\n  {eti}")
        print(tabella(p).round(3).to_string())

    print("\n=== anno per anno, uscita a fine sessione, tutti i giorni")
    p = t[t.uscita == "chiusura"]
    r = p.groupby("anno").agg(op=("netto", "size"), rischio=("rischio", "median"),
                              spread=("spread", "median"),
                              costo_perc=("costo_su_rischio", "median"),
                              lordo_op=("lordo", "mean"), netto_op=("netto", "mean"),
                              netto_R=("netto", "sum"))
    r["costo_perc"] = r.costo_perc * 100
    print(r.round(3).to_string())

    # confronto con HistData, giornata per giornata, sul periodo comune
    f = os.path.join(ROOT, "docs", "studies", "dati", "orb_crabel_vero.parquet")
    if os.path.exists(f):
        h = pd.read_parquet(f)
        h = h[h.uscita == "chiusura"][["giorno", "rischio", "lordo"]]
        h.columns = ["giorno", "r_hist", "l_hist"]
        m = p[["giorno", "anno", "rischio", "lordo"]].merge(h, on="giorno")
        if len(m):
            c = m.groupby("anno").apply(
                lambda x: pd.Series({
                    "gg": len(x), "rischio_hist": x.r_hist.median(),
                    "rischio_duka": x.rischio.median(),
                    "rapporto": (x.rischio / x.r_hist).median(),
                    "corr R": x.lordo.corr(x.l_hist),
                    "lordo_hist": x.l_hist.mean(), "lordo_duka": x.lordo.mean()}),
                include_groups=False)
            print("\n=== ipotesi A: le due fonti sulla stessa giornata")
            print(c.round(3).to_string())

    # il solo lordo, fino al 2026, su serie a un lato
    u = un_lato(simbolo)
    if len(u):
        s = u.groupby("anno").agg(lato=("lato", "first"), op=("lordo", "size"),
                                  rischio=("rischio", "median"),
                                  lordo_op=("lordo", "mean"), lordo_R=("lordo", "sum"))
        # a quanto spread pareggia: lordo = spread * media(1/rischio)
        s["pareggio_pt"] = (u.groupby("anno").lordo.mean()
                            / u.groupby("anno").rischio.apply(lambda x: (1 / x).mean()))
        print("\n=== solo LORDO su serie a un lato, tutti gli anni (2012-14 dato povero)")
        print(s.round(3).to_string())


if __name__ == "__main__":
    main()
