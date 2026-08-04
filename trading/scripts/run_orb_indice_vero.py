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
Cosi' lo spread lo paghi due volte come nella vita reale, e non c'e' nessun
numero da difendere.

I livelli (apertura, Stretch, NR4) si calcolano sul BID, che e' la serie
"prezzo" di riferimento; il lato lettera serve solo all'esecuzione.

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
MIN_MINUTI = 300
RISCHIO_CONTO = 0.01
RICERCA, VERIFICA = (2012, 2018), (2019, 2026)


def carica(simbolo):
    """BID e ASK allineati sullo stesso minuto, in ora di New York."""
    fuori = {}
    for lato in ("BID", "ASK"):
        f = sorted(glob.glob(os.path.join(DATI, simbolo, f"{lato}_*.parquet")))
        if not f:
            raise SystemExit(f"manca {lato} in {os.path.join(DATI, simbolo)}")
        d = pd.concat([pd.read_parquet(x) for x in f]).sort_index()
        d = d[~d.index.duplicated(keep="first")]
        fuori[lato] = d[d.volume > 0]        # i minuti senza scambi non esistono
    b, a = fuori["BID"], fuori["ASK"]
    comune = b.index.intersection(a.index)
    b, a = b.loc[comune], a.loc[comune]
    ny = comune.tz_convert(FUSO)
    o = ny.hour * 60 + ny.minute
    dentro = ((o >= APERTURA[0] * 60 + APERTURA[1])
              & (o <= CHIUSURA[0] * 60 + CHIUSURA[1]))
    b, a = b[dentro], a[dentro]
    giorno = ny[dentro].normalize().tz_localize(None)
    return b, a, pd.Series(giorno, index=b.index)


def profilo(b, giorno):
    g = b.groupby(giorno.values)
    d = pd.DataFrame({"apertura": g.open.first(), "massimo": g.high.max(),
                      "minimo": g.low.min(), "minuti": g.size()})
    d = d[d.minuti >= MIN_MINUTI]
    minore = np.minimum((d.apertura - d.massimo).abs(),
                        (d.apertura - d.minimo).abs())
    d["stretch"] = minore.rolling(GIORNI_STRETCH).mean().shift(1)
    r = d.massimo - d.minimo
    d["NR4"] = (r == r.rolling(4).min()).shift(1).fillna(False)
    return d


def percorri(bh, bl, bc, ah, al, ac, sopra, sotto, obiettivo):
    """Un giorno, con i due lati del prezzo usati come si usano davvero.

    Long: entra quando la LETTERA tocca la soglia sopra (compro caro), esce sul
    DENARO (vendo a sconto). Short: specularmente. Lo stop e' l'ordine opposto,
    come in Crabel. A parita' di minuto lo stop prevale sull'obiettivo.
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


def main():
    simbolo = sys.argv[1] if len(sys.argv) > 1 else "USA500IDXUSD"
    b, a, giorno = carica(simbolo)
    print(f"{simbolo}: {len(b):,} minuti di cassa, "
          f"{b.index.min():%Y-%m-%d} -> {b.index.max():%Y-%m-%d}".replace(",", "."),
          flush=True)
    sp = (a.close - b.close)
    print("spread reale in sessione: mediano %.3f punti, medio %.3f"
          % (sp.median(), sp.mean()), flush=True)
    d = profilo(b, giorno)
    print(f"sessioni piene: {len(d)} | NR4 il {d.NR4.mean()*100:.1f}% dei giorni",
          flush=True)

    gb, ga = b.groupby(giorno.values), a.groupby(giorno.values)
    righe = []
    for g, bg in gb:
        if g not in d.index:
            continue
        riga = d.loc[g]
        st = riga.stretch
        if not np.isfinite(st) or st <= 0:
            continue
        ag = ga.get_group(g)
        if len(ag) != len(bg):
            continue
        for eti, ob in [("chiusura", None), ("1:1", 1.0)]:
            e = percorri(bg.high.values, bg.low.values, bg.close.values,
                         ag.high.values, ag.low.values, ag.close.values,
                         riga.apertura + st, riga.apertura - st, ob)
            if e is None:
                continue
            # il LORDO si ricostruisce restituendo lo spread mediano del giorno
            spg = float((ag.close - bg.close).median())
            righe.append({"giorno": g, "anno": g.year, "uscita": eti,
                          "NR4": bool(riga.NR4), "spread": spg,
                          "lordo": e["netto"] + spg / e["rischio"], **e})
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
                "netto R": x.netto.sum(), "%anno": x.netto.sum() * RISCHIO_CONTO * 100 / anni,
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
    for eti, (da, aa) in [(f"ricerca {RICERCA}", RICERCA),
                          (f"verifica {VERIFICA}", VERIFICA)]:
        p = t[(t.anno >= da) & (t.anno <= aa) & (t.uscita == "chiusura")]
        print(f"\n  {eti}")
        print(tabella(p).round(3).to_string())

    print("\n=== ipotesi C: obiettivo 1:1 (TP e stop, nessun pareggio)")
    for eti, (da, aa) in [("ricerca", RICERCA), ("verifica", VERIFICA)]:
        p = t[(t.anno >= da) & (t.anno <= aa) & (t.uscita == "1:1")]
        print(f"\n  {eti}")
        print(tabella(p).round(3).to_string())

    print("\n=== anno per anno, uscita a fine sessione, tutti i giorni")
    p = t[t.uscita == "chiusura"]
    r = p.groupby("anno").agg(op=("netto", "size"), spread=("spread", "median"),
                              lordo_op=("lordo", "mean"), netto_op=("netto", "mean"),
                              netto_R=("netto", "sum"))
    print(r.round(3).to_string())


if __name__ == "__main__":
    main()
