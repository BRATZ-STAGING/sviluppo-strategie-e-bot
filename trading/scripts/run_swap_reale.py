#!/usr/bin/env python3
"""Appendice AQ: le candidate overnight con lo SWAP REALE di FP.

Dati presi dalle specifiche del simbolo XAUUSD sul conto FP (03/08/2026):

    tipo di swap      in punti
    swap long         -71,5 punti per lotto e per notte
    swap short        +32,5 punti per lotto e per notte
    dimensione lotto  100 once
    coefficiente      x3 il mercoledi', x1 gli altri giorni

Su XAUUSD un punto vale 0,01 $ di prezzo, che su 100 once fa **1 $ per lotto**:
una notte di long costa quindi 71,50 $ per lotto, una di short ne rende 32,50.

In multipli del rischio: swap_R = punti / (100 x distanza dello stop in $).
Con lo stop mediano di 4,72 $ una notte di long vale **0,151 R**, cioe' il 15%
del rischio dell'operazione. E' un costo enorme, mai considerato finora perche'
la strategia in vigore chiude prima della notte.

Il rollover cade alle 00:00 del server (UTC+3), cioe' alle 21:00 UTC: la stessa
ora della chiusura di fine giornata. Chi chiude alle 21 non paga mai swap.

Uso: python3 run_swap_reale.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

from run_scale_trailing import GESTIONI                          # noqa: E402
from run_schede_lunghe import esito_i                            # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SWAP_LONG, SWAP_SHORT = -71.5, 32.5     # punti per lotto e per notte
CONTRATTO = 100                         # once per lotto
ROLLOVER_UTC = 21                       # 00:00 del server, che sta a UTC+3
TRIPLO = 2                              # mercoledi' = 2 in weekday()
GIORNI_MAX = 30

PROVE = [
    ("in uso: pari +3R 1:10, sera",   "pari a +3R (in uso)", 10, "giornaliera"),
    ("A: pari +3R 1:8, venerdi'",     "pari a +3R (in uso)", 8,  "settimanale"),
    ("B: trail MFE-2 1:8, aperta",    "trail MFE-2 da +3R",  8,  "aperta"),
    ("B': trail MFE-2 1:8, venerdi'", "trail MFE-2 da +3R",  8,  "settimanale"),
]


def notti(t_in, t_out):
    """Rollover attraversati, con il peso del mercoledi' triplo."""
    primo = t_in.normalize() + pd.Timedelta(hours=ROLLOVER_UTC)
    if primo <= t_in:
        primo += pd.Timedelta(days=1)
    peso = 0
    t = primo
    while t < t_out:
        if t.weekday() != 5:                      # il sabato non c'e' rollover
            peso += 3 if t.weekday() == TRIPLO else 1
        t += pd.Timedelta(days=1)
    return peso


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [op for op in genera(m1, T)
           if all(op[f"c_{tf}"] for tf in T.conferme)
           and all(not op[f"c_{tf}"] for tf in T.ritracciamento)]
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    hi, lo, cl = m1.high.values, m1.low.values, m1.close.values
    anni = np.array([op["anno"] for op in ops])
    lunghe = sum(1 for op in ops if op["lato"] == "long")
    print(f"operazioni: {len(ops)} ({lunghe} long, {len(ops)-lunghe} short)", flush=True)
    print(f"una notte di long costa {abs(SWAP_LONG)/100/4.72:.3f} R con lo stop "
          f"mediano; una di short ne rende {SWAP_SHORT/100/4.72:.3f}\n", flush=True)

    for eti, nome, rr, regime in PROVE:
        scala, trail = next((s, t) for n, s, t in GESTIONI if n == nome)
        lordo, swap, pesi = [], [], []
        for op in ops:
            t_in = pd.Timestamp(op["time"]).tz_convert("UTC")
            segno = 1 if op["lato"] == "long" else -1
            e, k = op["entry"], op["rischio"]
            g = t_in.normalize()
            fine = {"giornaliera": g + pd.Timedelta(hours=T.ora_chiusura),
                    "settimanale": g + pd.Timedelta(days=(4 - g.weekday()) % 7)
                    + pd.Timedelta(hours=T.ora_chiusura),
                    "aperta": t_in + pd.Timedelta(days=GIORNI_MAX)}[regime]
            a = int(np.searchsorted(idx, t_in.value))
            b = int(np.searchsorted(idx, fine.value))
            h_, l_, c_ = hi[a:b], lo[a:b], cl[a:b]
            if segno == 1:
                fav, sfav = (h_ - e) / k, (e - l_) / k
            else:
                fav, sfav = (e - l_) / k, (h_ - e) / k
            r_eod = ((float(c_[-1]) - e) if segno == 1 else (e - float(c_[-1]))) / k
            x, _, j = esito_i(fav, sfav, r_eod, rr, scala, trail)
            t_out = pd.Timestamp(idx[a + j], unit="ns", tz="UTC")
            p = notti(t_in, t_out)
            punti = SWAP_LONG if segno == 1 else SWAP_SHORT
            lordo.append(x - op["costo"])
            swap.append(p * punti / (CONTRATTO * k))    # gia' in multipli di R
            pesi.append(p)
        lordo, swap = np.array(lordo), np.array(swap)
        netto = lordo + swap
        ap = sum(1 for y in np.unique(anni) if netto[anni == y].sum() > 0)
        cum = np.cumsum(netto)
        dd = (np.maximum.accumulate(cum) - cum).max()
        print(f"{eti}")
        print(f"   lordo {lordo.sum():+7.1f} R | swap {swap.sum():+7.1f} R | "
              f"NETTO {netto.sum():+7.1f} R  ({10000 + 100*netto.sum():,.0f} EUR)"
              .replace(",", "."))
        print(f"   notti pesate {sum(pesi):4d} | vinte {(netto>0).mean()*100:4.1f}% | "
              f"DD {dd:4.1f} R | anni+ {ap}/7 | "
              f"peggiore {min(netto[anni==y].sum() for y in np.unique(anni)):+.1f} R\n")


if __name__ == "__main__":
    main()
