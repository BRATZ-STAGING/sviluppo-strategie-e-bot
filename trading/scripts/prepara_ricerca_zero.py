#!/usr/bin/env python3
"""Prepara le candele per la ricerca da zero, separando FISICAMENTE i periodi.

- scoperta : fino al 31/12/2017  -> D:\\ricerca_zero\\scoperta\\<SIMBOLO>_<TF>.parquet
- verifica : dal 01/01/2018      -> D:\\ricerca_zero\\verifica\\<SIMBOLO>_<TF>.parquet

Gli agenti della fase di scoperta ricevono solo la prima cartella: non possono
guardare il periodo di verifica nemmeno per sbaglio.

Timeframe: M5, M15, H1, D1. Candele etichettate all'apertura, UTC. Una
candela esiste solo se nel periodo c'e' almeno un minuto (niente riempimenti).
Colonne: open, high, low, close, minuti (quanti minuti M1 l'hanno formata).
Il volume non si usa: le fonti non sono confrontabili (HistData non lo ha).

Mercati: XAUUSD (Dukascopy, 2009->), SPXUSD, NSXUSD, XAGUSD (HistData, 2010->),
GRXEUR (HistData, SOLO fino al 14/06/2020: dopo la serie contiene un altro
indice, vedi data/histdata/README.md; quindi il DAX ha la scoperta intera e una
verifica corta 2018 -> 06/2020).
"""
from __future__ import annotations

import glob
import os

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.environ.get("RZ_OUT", r"D:\ricerca_zero")
TAGLIO = pd.Timestamp("2018-01-01", tz="UTC")
TF = {"M5": "5min", "M15": "15min", "H1": "1h", "D1": "1D"}
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "minuti": "sum"}

MERCATI = {
    "XAUUSD": os.path.join(ROOT, "data", "XAUUSD_M1", "XAUUSD_M1_*.parquet"),
    "SPXUSD": os.path.join(ROOT, "data", "histdata", "SPXUSD", "SPXUSD_M1_*.parquet"),
    "NSXUSD": os.path.join(ROOT, "data", "histdata", "NSXUSD", "NSXUSD_M1_*.parquet"),
    "XAGUSD": os.path.join(ROOT, "data", "histdata", "XAGUSD", "XAGUSD_M1_*.parquet"),
    "GRXEUR": os.path.join(ROOT, "data", "histdata", "GRXEUR", "GRXEUR_M1_*.parquet"),
}
FINE_VALIDA = {"GRXEUR": pd.Timestamp("2020-06-15", tz="UTC")}


def carica_anno(f: str) -> pd.DataFrame:
    d = pd.read_parquet(f)
    if "timestamp" in d.columns:
        d = d.set_index("timestamp")
    d.index = pd.to_datetime(d.index, utc=True)
    d = d[["open", "high", "low", "close"]].astype("float64")
    d["minuti"] = 1
    return d.sort_index()


def main():
    for cart in ("scoperta", "verifica"):
        os.makedirs(os.path.join(OUT, cart), exist_ok=True)
    for sim, pat in MERCATI.items():
        pezzi = {tf: [] for tf in TF}
        for f in sorted(glob.glob(pat)):
            m1 = carica_anno(f)
            if sim in FINE_VALIDA:
                m1 = m1[m1.index < FINE_VALIDA[sim]]
            if m1.empty:
                continue
            for tf, regola in TF.items():
                b = m1.resample(regola).agg(AGG)
                pezzi[tf].append(b[b["minuti"] > 0])
            del m1
        for tf in TF:
            tutto = pd.concat(pezzi[tf])
            tutto = tutto[~tutto.index.duplicated(keep="first")].sort_index()
            for cart, parte in (("scoperta", tutto[tutto.index < TAGLIO]),
                                ("verifica", tutto[tutto.index >= TAGLIO])):
                parte.to_parquet(os.path.join(OUT, cart, f"{sim}_{tf}.parquet"))
            s = tutto[tutto.index < TAGLIO]
            print(f"{sim} {tf}: scoperta {len(s):>7} candele "
                  f"{s.index.min():%Y-%m-%d} -> {s.index.max():%Y-%m-%d} | "
                  f"verifica {len(tutto) - len(s):>7}", flush=True)


if __name__ == "__main__":
    main()
