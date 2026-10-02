#!/usr/bin/env python3
"""Misura del DATO (non di una strategia) sugli indici in ``data/indici``.

Per ogni anno: minuti BID e ASK, giorni con dati, primo e ultimo giorno, e
quante giornate passano il filtro di qualita' dell'Emendamento 1 di
``docs/trasferimento-indici-registrazione.md``:

- finestra: i minuti [07:00, 21:00) UTC, cioe' 840 minuti;
- copertura: minuti con BID e ASK entrambi presenti e volume > 0, divisi per
  840 (un minuto assente dal file conta come minuto senza scambi): >= 95%;
- mercato a due lati: ASK close > BID close in >= 90% dei minuti della
  finestra presenti su entrambi i lati.

Uso:  python qualita_indici.py data/indici/USA500IDXUSD
Stampa la tabella in markdown (una riga per anno).
"""
from __future__ import annotations

import glob
import os
import sys

import pandas as pd

MINUTI_FINESTRA = 14 * 60
MIN_COPERTURA = 0.95
MIN_DUE_LATI = 0.90


def carica(cartella, lato):
    f = sorted(glob.glob(os.path.join(cartella, f"{lato}_*.parquet")))
    d = pd.concat([pd.read_parquet(x) for x in f]).sort_index()
    return d[~d.index.duplicated(keep="first")]


def giornate_sane(b, a):
    comune = b.index.intersection(a.index)
    bb, aa = b.loc[comune], a.loc[comune]
    h = comune.hour
    dentro = (h >= 7) & (h < 21)
    bb, aa = bb[dentro], aa[dentro]
    q = pd.DataFrame({"g": comune[dentro].normalize(),
                      "scambi": (bb.volume.values > 0) & (aa.volume.values > 0),
                      "due": (aa.close.values - bb.close.values) > 0})
    q = q.groupby("g").agg(scambi=("scambi", "sum"), due=("due", "mean"))
    q["copertura"] = q.scambi / MINUTI_FINESTRA
    return q[(q.copertura >= MIN_COPERTURA) & (q.due >= MIN_DUE_LATI)].index


def main():
    cartella = sys.argv[1]
    simbolo = os.path.basename(os.path.normpath(cartella))
    b, a = carica(cartella, "BID"), carica(cartella, "ASK")
    sane = giornate_sane(b, a)
    righe = []
    for anno in sorted(set(b.index.year) | set(a.index.year)):
        by, ay = b[b.index.year == anno], a[a.index.year == anno]
        giorni = (by[by.volume > 0].index.normalize().unique()
                  .union(ay[ay.volume > 0].index.normalize().unique()))
        righe.append((anno, len(by), len(ay), len(giorni),
                      giorni.min().date() if len(giorni) else "-",
                      giorni.max().date() if len(giorni) else "-",
                      int((sane.year == anno).sum())))
    n = lambda x: f"{x:,}".replace(",", ".")
    print(f"### {simbolo}\n")
    print("| anno | minuti BID | minuti ASK | giorni con dati | primo | ultimo | giorni sani |")
    print("|---|---:|---:|---:|---|---|---:|")
    for r in righe:
        print(f"| {r[0]} | {n(r[1])} | {n(r[2])} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |")
    print(f"| **totale** | {n(sum(r[1] for r in righe))} | {n(sum(r[2] for r in righe))} | "
          f"{sum(r[3] for r in righe)} | | | {sum(r[6] for r in righe)} |")


if __name__ == "__main__":
    main()
