#!/usr/bin/env python3
"""Legge i CSV che i bot scrivono e dice cosa sta succedendo davvero.

Le colonne sono identiche fra MT5 e cTrader (scelta di chi ha scritto i bot),
quindi questo lettore vale per tutti e quattro.

Non basta il totale in R: 21 operazioni non distinguono un vantaggio da una
serie fortunata, e il file degli scarti dice cosa il bot NON ha fatto — che e'
la parte che nessuno guarda.

Uso: python analizza_forward.py <cartella con i CSV>
"""
import glob
import math
import os
import sys

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)


def wilson(vinte, n, z=1.96):
    """Intervallo di confidenza al 95% per una proporzione (Wilson).

    Sulle proporzioni con pochi casi la formula ingenua da' intervalli sbagliati
    (puo' uscire dal range 0-1). Wilson e' quella corretta.
    """
    if n == 0:
        return 0.0, 0.0
    p = vinte / n
    d = 1 + z**2 / n
    centro = (p + z**2 / (2 * n)) / d
    meta = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return max(0.0, centro - meta), min(1.0, centro + meta)


def binomiale_almeno(k, n, p):
    """P(almeno k successi su n) con probabilita' p: quanto e' facile il caso."""
    tot = 0.0
    for i in range(k, n + 1):
        tot += math.comb(n, i) * p**i * (1 - p)**(n - i)
    return tot


def trova(cartella, prefisso):
    files = sorted(glob.glob(os.path.join(cartella, "**", f"{prefisso}_*.csv"),
                             recursive=True))
    return files


def analizza_trades(path):
    df = pd.read_csv(path)
    df["signal_time_utc"] = pd.to_datetime(df.signal_time_utc)
    df["exit_time_utc"] = pd.to_datetime(df.exit_time_utc)
    n = len(df)
    vinte = int((df.R > 0).sum())
    tot_r = df.R.sum()

    print(f"\n{'='*72}\n{os.path.basename(path)}\n{'='*72}")
    print(f"periodo: {df.signal_time_utc.min():%Y-%m-%d} → "
          f"{df.signal_time_utc.max():%Y-%m-%d}")
    print(f"operazioni {n}   a obiettivo {vinte}   "
          f"R totale {tot_r:+.2f}   R medio {df.R.mean():+.3f}")

    print("\n--- IL VANTAGGIO E' DIMOSTRATO? ---")
    # rapporto vero fra vincita e perdita, dai dati (non dai parametri)
    vinc = df.loc[df.R > 0, "R"].mean()
    perd = -df.loc[df.R <= 0, "R"].mean()
    be = perd / (vinc + perd)
    lo, hi = wilson(vinte, n)
    p_caso = binomiale_almeno(vinte, n, be)
    print(f"vincita media  {vinc:+.3f} R      perdita media  {-perd:+.3f} R")
    print(f"pareggio a     {be*100:.1f}% di operazioni vincenti")
    print(f"osservato      {vinte/n*100:.1f}%   "
          f"intervallo di confidenza 95%: {lo*100:.1f}% - {hi*100:.1f}%")
    print(f"probabilita' di fare almeno cosi' bene per caso: {p_caso*100:.1f}%")
    if lo <= be:
        print("→ l'intervallo CONTIENE il pareggio: il vantaggio NON e' dimostrato")
    else:
        print("→ l'intervallo sta sopra il pareggio")

    print("\n--- COSTI: quanto pesano davvero ---")
    print(f"spread all'esecuzione (punti): mediano {df.spread_pips_fill.median():.0f}   "
          f"massimo {df.spread_pips_fill.max():.0f}")
    print(f"  in dollari: mediano {df.spread_pips_fill.median()/100:.3f} $   "
          f"massimo {df.spread_pips_fill.max()/100:.3f} $")
    comm_r = (-df.commission / df.real_risk)
    print(f"commissione: {comm_r.mean():.4f} R per operazione "
          f"({-df.commission.sum():.2f} in valuta)")
    swap = df[df.swap != 0]
    if len(swap):
        swap_r = swap.swap / swap.real_risk
        print(f"swap: {len(swap)} operazioni tenute oltre la notte, "
              f"da {swap_r.min():+.3f} a {swap_r.max():+.3f} R "
              f"(totale {swap.swap.sum():+.2f})")

    print("\n--- ESECUZIONE ---")
    print(f"attesa dal segnale al riempimento (minuti): "
          f"mediana {df.min_signal_to_fill.median():.0f}   "
          f"massima {df.min_signal_to_fill.max():.0f}")
    print(f"rischio effettivo: {df.real_risk_pct.min():.2f}% - "
          f"{df.real_risk_pct.max():.2f}% (obiettivo 1,00%)")
    print(f"ampiezza dello stop: mediana {df.sl_dist.median():.2f} $   "
          f"minima {df.sl_dist.min():.2f} $   massima {df.sl_dist.max():.2f} $")

    print("\n--- PER MOTIVO DI CHIUSURA ---")
    g = df.groupby("close_reason").agg(n=("R", "size"), R_medio=("R", "mean"),
                                       R_totale=("R", "sum"))
    print(g.to_string(float_format=lambda x: f"{x:+.3f}"))

    print("\n--- PER DIREZIONE ---")
    g = df.groupby("direction").agg(n=("R", "size"), vinte=("R", lambda s: (s > 0).sum()),
                                    R_medio=("R", "mean"), R_totale=("R", "sum"))
    print(g.to_string(float_format=lambda x: f"{x:+.3f}"))
    return df


def analizza_skips(path, colonne=("time_utc", "id", "direction", "reason", "detail")):
    df = pd.read_csv(path, header=None, names=colonne, engine="python")
    print(f"\n{'='*72}\n{os.path.basename(path)}  —  cosa il bot NON ha fatto"
          f"\n{'='*72}")
    g = df.groupby("reason").size().sort_values(ascending=False)
    print(g.to_string())
    print(f"\ntotale righe: {len(df)}")

    # REPLACED non e' un'occasione persa: e' lo stesso setup spostato piu' avanti
    persi = df[~df.reason.isin(["REPLACED"])]
    if len(persi):
        print("\nrighe che sono davvero occasioni non sfruttate o problemi:")
        for motivo, gr in persi.groupby("reason"):
            print(f"\n  {motivo}  ({len(gr)})")
            for _, r in gr.head(6).iterrows():
                print(f"    {r.time_utc}  {r.direction}  {str(r.detail)[:60]}")
            if len(gr) > 6:
                print(f"    ...e altre {len(gr)-6}")
    return df


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cartella = sys.argv[1]
    for path in trova(cartella, "trades"):
        analizza_trades(path)
    for path in trova(cartella, "skips"):
        analizza_skips(path)


if __name__ == "__main__":
    main()
