#!/usr/bin/env python3
"""Spread reale dell'XAUUSD sul conto FP Markets (demo), letto da MT5 in sola lettura.

Si collega al terminale MT5 gia' aperto (nessun ordine, nessuna modifica):
1. candele M1 2020 -> oggi a blocchi mensili: campo ``spread`` in punti
   (XAUUSD: 1 punto = 0,01 $). In MT5 e' lo spread registrato nella candela
   (di norma il minimo del minuto): e' una stima ottimistica;
2. tick veri (bid/ask) della prima settimana completa di ogni mese dal 2023:
   distribuzione di ask - bid per ora UTC. E' la misura di riferimento.

Scrive D:\\ricerca_spread\\fp_spread_m1.parquet e fp_spread_tick.parquet e
stampa solo aggregati. Uso: python misura_spread_fp.py
"""
from __future__ import annotations

import datetime as dt
import os

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

OUT = r"D:\ricerca_spread"
SIM = "XAUUSD"
UTC = dt.timezone.utc


def mesi(da, a):
    d = dt.datetime(da.year, da.month, 1, tzinfo=UTC)
    while d < a:
        n = dt.datetime(d.year + (d.month == 12), d.month % 12 + 1, 1, tzinfo=UTC)
        yield d, min(n, a)
        d = n


def main():
    os.makedirs(OUT, exist_ok=True)
    if not mt5.initialize():
        raise SystemExit(f"MT5 non raggiungibile: {mt5.last_error()}")
    ti, ai = mt5.terminal_info(), mt5.account_info()
    print(f"server {ai.server} | conto demo: {ai.trade_mode == 0} | trading automatico: {ti.trade_allowed}")
    info = mt5.symbol_info(SIM)
    mt5.symbol_select(SIM, True)
    punto = info.point
    print(f"{SIM}: punto {punto} | spread attuale {info.spread} punti = {info.spread * punto:.2f} $")
    # differenza fra ora del server e UTC, dall'ultimo tick
    oggi = dt.datetime.now(UTC)

    righe = []
    for a, b in mesi(dt.datetime(2020, 1, 1, tzinfo=UTC), oggi):
        r = mt5.copy_rates_range(SIM, mt5.TIMEFRAME_M1, a, b)
        if r is None or not len(r):
            continue
        d = pd.DataFrame(r)
        d["t"] = pd.to_datetime(d["time"], unit="s")
        d["spread_usd"] = d["spread"] * punto
        righe.append(d[["t", "spread_usd"]])
    m1 = pd.concat(righe, ignore_index=True)
    m1.to_parquet(os.path.join(OUT, "fp_spread_m1.parquet"))
    a = m1.assign(anno=m1.t.dt.year).groupby("anno").spread_usd.agg(["median", "mean", "count"])
    print("\nSpread dalle candele M1 (stima ottimistica), $ per oncia:")
    print(a.round(3).to_string())

    tick = []
    for a_, _ in mesi(dt.datetime(2023, 1, 1, tzinfo=UTC), oggi - dt.timedelta(days=10)):
        lun = a_ + dt.timedelta(days=(7 - a_.weekday()) % 7)            # primo lunedi'
        t = mt5.copy_ticks_range(SIM, lun, lun + dt.timedelta(days=5), mt5.COPY_TICKS_INFO)
        if t is None or not len(t):
            continue
        d = pd.DataFrame(t)
        d = d[(d.ask > 0) & (d.bid > 0)]
        tick.append(pd.DataFrame({"t": pd.to_datetime(d["time_msc"], unit="ms"),
                                  "spread_usd": d["ask"] - d["bid"]}))
    mt5.shutdown()
    tk = pd.concat(tick, ignore_index=True)
    tk.to_parquet(os.path.join(OUT, "fp_spread_tick.parquet"))
    print(f"\nTick (prima settimana di ogni mese dal 2023): {len(tk):,} tick")
    y = tk.assign(anno=tk.t.dt.year).groupby("anno").spread_usd.describe(percentiles=[.5, .9])[["50%", "mean", "90%", "count"]]
    print(y.round(3).to_string())
    print("\nOra del SERVER (non UTC) -> spread mediano dai tick:")
    h = tk.groupby(tk.t.dt.hour).spread_usd.median()
    print(" ".join(f"{k:02d}:{v:.2f}" for k, v in h.items()))


if __name__ == "__main__":
    main()
