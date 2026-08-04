#!/usr/bin/env python3
"""Base per le verifiche AW-AY: un solo passaggio su 2009-2026, tutto su disco.

Generare i segnali sui diciotto anni costa sei minuti; le tre verifiche
chieste (filtro di regime, rinuncia al lato corto, taratura invertita) ne
avrebbero chiesti una decina di passaggi. Qui il passaggio si fa UNA volta e
si salva abbastanza da rispondere a tutte e tre leggendo un Parquet:

- il segnale grezzo, cioe' PRIMA del filtro sulle conferme, con tutti i flag
  ``c_<tf>``: cosi' si puo' ricomporre qualunque combinazione di conferme e
  ritracciamenti senza rigenerare niente;
- l'esito per ogni coppia gestione x obiettivo della griglia gia' in uso;
- le misure di regime del giorno (ATR, ATR in percentuale del prezzo,
  distanza della chiusura D1 dalle medie 50 e 200 in unita' di ATR), tutte
  calcolate causalmente, per definire un filtro di regime senza sbirciare.

Uso: python3 prepara_verifiche.py
Scrive docs/studies/dati/verifiche_base.parquet
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402
from framework.volatility import daily_atr, daily_bars           # noqa: E402

from run_scale_trailing import GESTIONI, OBIETTIVI, esito        # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def regimi(m1):
    """Misure di contesto note all'APERTURA di ogni giornata (nessun futuro)."""
    d1 = daily_bars(m1)
    atr = daily_atr(m1, 14)
    ch = d1.close.shift(1)                       # ieri: oggi non e' ancora finito
    out = pd.DataFrame({
        "atr": atr,
        "prezzo": ch,
        "atr_pct": atr / ch * 100,
        "sopra50": (ch - d1.close.rolling(50).mean().shift(1)) / atr,
        "sopra200": (ch - d1.close.rolling(200).mean().shift(1)) / atr,
    })
    out.index = out.index.normalize()
    return out


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = genera(m1, T)               # nessun filtro sulle conferme: grezzo
    print(f"segnali grezzi: {len(ops)}", flush=True)

    reg = regimi(m1)
    giorni = pd.DatetimeIndex([pd.Timestamp(o["time"]) for o in ops]).normalize()
    ctx = reg.reindex(giorni).ffill().reset_index(drop=True)

    tab = pd.DataFrame({
        "time": [pd.Timestamp(o["time"]) for o in ops],
        "anno": [o["anno"] for o in ops],
        "mese": [pd.Timestamp(o["time"]).strftime("%Y-%m") for o in ops],
        "lato": [o["lato"] for o in ops],
        "entry": [o["entry"] for o in ops],
        "rischio": [o["rischio"] for o in ops],
        "costo": [o["costo"] for o in ops],
        "volalta": [o["volalta"] for o in ops],
        "mfe": [o["mfe"] for o in ops],
        "r_eod": [o["r_eod"] for o in ops],
    })
    for tf in T.timeframes:
        tab[f"c_{tf}"] = [int(o[f"c_{tf}"]) for o in ops]
    for c in ctx.columns:
        tab[c] = ctx[c].values

    for nome, scala, trail in GESTIONI:
        for rr in OBIETTIVI:
            col = f"r|{nome}|{rr}"
            tab[col] = [esito(o["fav"], o["sfav"], o["r_eod"], rr, scala,
                              trail)[0] - o["costo"] for o in ops]
    fuori = os.path.join(ROOT, "docs", "studies", "dati", "verifiche_base.parquet")
    tab.to_parquet(fuori, index=False)
    print(f"{len(tab)} righe, {len(tab.columns)} colonne -> {fuori}")
    ufficiali = (tab[[f"c_{tf}" for tf in T.conferme]].all(axis=1)
                 & ~tab[[f"c_{tf}" for tf in T.ritracciamento]].any(axis=1))
    print(f"di cui con le conferme ufficiali: {int(ufficiali.sum())}")
    print(f"contesto mancante: {int(tab.atr.isna().sum())} righe")


if __name__ == "__main__":
    main()
