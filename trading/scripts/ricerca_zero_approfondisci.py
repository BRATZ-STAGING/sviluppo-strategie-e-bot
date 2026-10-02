#!/usr/bin/env python3
"""Ricerca da zero, scoperta 2009-2014: secondo passaggio sui due fenomeni
emersi da ricerca_zero_scoperta.py.

1. DERIVA PER FASCIA ORARIA: le ore asiatiche salgono (23, 2, 5 UTC positive
   in 5-6 anni su 6), quelle europee scendono (9 UTC). Sospetto da escludere:
   sulle sole quotazioni BID il rollover (21-23 UTC) allarga lo spread, il BID
   scende alle 21 e risale alle 22-23 senza che il prezzo vero si muova.
   Quindi si misura la deriva per fascia, con e senza le ore del rollover.

2. CONTINUAZIONE DOPO UNA CANDELA H1 MOLTO GRANDE (|z| >= 3): +0,44 dev.std
   dopo 6 ore, t +3,0, 5 anni su 6. Si misura in dollari contro lo spread, per
   verso (rialzo/ribasso), per ora del giorno e per anno.

Stesse protezioni dello script di scoperta: solo 2009-2014.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from ricerca_zero_scoperta import OUT, SPREAD_RIF, anni_concordi, barre, carica_m1, tstat  # noqa: E402

pd.set_option("display.width", 200)


def deriva(m1: pd.DataFrame):
    print("\n== 1. deriva per fascia oraria (rendimento della fascia, punti base) ==")
    h1 = barre(m1, "1h")
    r = np.log(h1["close"]).diff()
    r = r[h1.index.to_series().diff() == pd.Timedelta("1h")] * 1e4
    fasce = {"rollover 21-23": [21, 22], "asia 23-7": [23, 0, 1, 2, 3, 4, 5, 6],
             "london 7-12": list(range(7, 12)), "ny 12-17": list(range(12, 17)),
             "ny tardo 17-21": list(range(17, 21))}
    righe = []
    for nome, ore in fasce.items():
        x = r[r.index.hour.isin(ore)]
        g = x.groupby(x.index.normalize()).sum()
        per_anno = g.groupby(g.index.year).sum()
        righe.append({"fascia": nome, "giorni": len(g), "pb/giorno": g.mean(),
                      "t": tstat(g), "anni": anni_concordi(g),
                      "$/giorno": g.mean() * 1e-4 * 1400,
                      "pb/anno min": per_anno.min(), "pb/anno max": per_anno.max()})
    t = pd.DataFrame(righe).set_index("fascia")
    print(t.round(2).to_string())
    tot = r.groupby(r.index.year).sum()
    print("rendimento totale per anno (pb): " + ", ".join(f"{a} {v:+.0f}" for a, v in tot.items()))
    print(f"(dollari al prezzo medio di 1400; spread di riferimento {SPREAD_RIF}$, "
          "nelle ore del rollover lo spread reale e' molto piu' largo)")


def shock(m1: pd.DataFrame):
    print("\n== 2. dopo una candela H1 con |z| >= 3: esito dopo 6 ore ==")
    b = barre(m1, "1h")
    passo = pd.Timedelta("1h")
    lr = np.log(b["close"]).diff().where(b.index.to_series().diff() == passo)
    sd = lr.rolling(100, min_periods=80).std().shift(1)
    z = lr / sd
    ent = b["open"].shift(-1)
    usc = b["close"].shift(-6)
    span = b.index.to_series().shift(-6) - b.index.to_series()
    ok = (z.abs() >= 3) & (span == 6 * passo)
    e = pd.DataFrame({"z": z, "verso": np.sign(z), "dollari": np.sign(z) * (usc - ent),
                      "dev": np.sign(z) * np.log(usc / ent) / sd,
                      "ora": b.index.hour}, index=b.index)[ok].dropna()
    e.to_parquet(os.path.join(OUT, "shock_h1.parquet"))

    def riga(nome, x):
        return {"gruppo": nome, "n": len(x), "$ medio": x["dollari"].mean(),
                "$ mediano": x["dollari"].median(), "t": tstat(x["dollari"]),
                "anni": anni_concordi(x["dollari"]), "vinte": (x["dollari"] > SPREAD_RIF).mean(),
                "dev": x["dev"].mean()}

    righe = [riga("tutti", e), riga("rialzo", e[e["verso"] > 0]), riga("ribasso", e[e["verso"] < 0])]
    for nome, ore in (("asia 23-7", [23, 0, 1, 2, 3, 4, 5, 6]), ("london 7-12", range(7, 12)),
                      ("ny 12-17", range(12, 17)), ("ny tardo 17-23", range(17, 23))):
        righe.append(riga(nome, e[e["ora"].isin(list(ore))]))
    print(pd.DataFrame(righe).set_index("gruppo").round(3).to_string())
    pa = e.groupby(e.index.year)["dollari"].agg(["size", "mean"])
    print("per anno ($ medi): " + ", ".join(f"{a} {m:+.2f} (n{n})" for a, (n, m) in pa.iterrows()))
    print(f"('vinte' = quota con guadagno oltre {SPREAD_RIF}$; entrata all'apertura dell'ora dopo, "
          "uscita alla chiusura della sesta; nessuno stop)")


def main():
    m1 = carica_m1()
    deriva(m1)
    shock(m1)


if __name__ == "__main__":
    main()
