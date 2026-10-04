#!/usr/bin/env python3
"""Candele 22:00 -> 22:00 UTC di quattro indici mai usati (Nikkei, FTSE,
Euro Stoxx 50, CAC 40), stesso formato di ``prepara_paniere_d1.py``.

Registrazione: docs/compra-ribasso-nuovi-indici-registrazione.md.
Fonte: D:\\histdata_parquet\\<SIMBOLO>\\<SIMBOLO>_M1_<anno>.parquet (HistData,
gia' in UTC). Uscita: D:\\ricerca_multi\\nuovi\\PANIERE_D1.parquet e
D:\\ricerca_multi\\nuovi\\costi.csv.

Difetto della fonte trovato prima di ogni calcolo: ETXEUR dal 17/12/2018 sta
a ~8.900 punti (livello dell'IBEX 35, non dell'Euro Stoxx 50 che era a
~3.000): la serie si taglia al 14/12/2018 compreso. HistData non ha ETXEUR
dopo il 2019.
"""
from __future__ import annotations

import glob
import os

import pandas as pd

FONTE = r"D:\histdata_parquet"
OUT = r"D:\ricerca_multi\nuovi"
FINE = {"ETXEUR": pd.Timestamp("2018-12-15", tz="UTC")}
COSTI = {"JPXJPY": 10.0, "UKXGBP": 1.5, "ETXEUR": 2.0, "FRXEUR": 1.5}


def main():
    os.makedirs(OUT, exist_ok=True)
    pezzi = []
    for m in COSTI:
        anni = []
        for f in sorted(glob.glob(os.path.join(FONTE, m, f"{m}_M1_*.parquet"))):
            d = pd.read_parquet(f).set_index("timestamp")
            if m in FINE:
                d = d[d.index < FINE[m]]
            if d.empty:
                continue
            giorno = (d.index + pd.Timedelta(hours=2)).normalize().tz_localize(None)
            d["m5"] = d.index.floor("5min")
            g = d.groupby(giorno).agg(open=("open", "first"), high=("high", "max"),
                                     low=("low", "min"), close=("close", "last"),
                                     barre=("m5", "nunique"))
            anni.append(g)
        g = pd.concat(anni)
        g = g.groupby(level=0).agg(open=("open", "first"), high=("high", "max"),
                                   low=("low", "min"), close=("close", "last"),
                                   barre=("barre", "sum"))
        g = g[g.index.dayofweek < 5]
        # Emendamento 1 della registrazione: questi indici quotano su HistData
        # meno ore dei mercati del paniere (Euro Stoxx ~10 h, CAC/FTSE ~14 h):
        # la soglia fissa di 150 M5 li scartava quasi tutti. Valida = almeno
        # l'80% della mediana delle M5 per giornata di quel mercato.
        g["valida"] = g["barre"] >= 0.8 * g["barre"].median()
        g["mercato"] = m
        pezzi.append(g.reset_index(names="giorno"))
    p = pd.concat(pezzi, ignore_index=True)
    p.to_parquet(os.path.join(OUT, "PANIERE_D1.parquet"), index=False)
    pd.Series(COSTI, name="costo_rt").rename_axis("mercato").to_csv(os.path.join(OUT, "costi.csv"))
    print(p.groupby("mercato").agg(giorni=("giorno", "size"), valide=("valida", "sum"),
                                   da=("giorno", "min"), a=("giorno", "max")).to_string())


if __name__ == "__main__":
    main()
