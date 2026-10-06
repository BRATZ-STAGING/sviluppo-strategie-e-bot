#!/usr/bin/env python3
"""Scarica da data.binance.vision (pubblico, gratuito, senza account) le candele
M1 dei future perpetui USDT-M e le converte in parquet annuali.

Colonne Binance kline: open_time, open, high, low, close, volume, close_time,
quote_volume, count (numero di scambi), taker_buy_volume (volume comprato con
ordini a mercato = acquisti aggressivi), taker_buy_quote_volume, ignore.
Il flusso degli ordini al minuto: acquisti aggressivi = taker_buy_volume,
vendite aggressive = volume - taker_buy_volume.

Riavviabile (gli zip validi non si riscaricano), una richiesta alla volta.
Uso: python scarica_binance.py BTCUSDT 2020 2026
Env: BN_CACHE (default D:\\crypto\\binance\\zip), BN_OUT (default D:\\crypto\\binance\\m1)
"""
from __future__ import annotations

import datetime as dt
import io
import os
import sys
import time
import urllib.request
import zipfile

import pandas as pd

CACHE = os.environ.get("BN_CACHE", r"D:\crypto\binance\zip")
OUT = os.environ.get("BN_OUT", r"D:\crypto\binance\m1")
URL = "https://data.binance.vision/data/futures/um/monthly/klines/{s}/1m/{s}-1m-{y}-{m:02d}.zip"
COL = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
       "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]


def scarica(s, y, m):
    f = os.path.join(CACHE, s, f"{s}-1m-{y}-{m:02d}.zip")
    if os.path.exists(f) and zipfile.is_zipfile(f):
        return f
    os.makedirs(os.path.dirname(f), exist_ok=True)
    for t in range(4):
        try:
            with urllib.request.urlopen(URL.format(s=s, y=y, m=m), timeout=120) as r:
                b = r.read()
            if not b.startswith(b"PK"):
                return None
            with open(f + ".tmp", "wb") as h:
                h.write(b)
            os.replace(f + ".tmp", f)
            return f
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(10 * (t + 1))
        except Exception:
            time.sleep(10 * (t + 1))
    return None


def leggi(f):
    with zipfile.ZipFile(f) as z:
        raw = z.read(z.namelist()[0])
    d = pd.read_csv(io.BytesIO(raw), header=None)
    if str(d.iloc[0, 0]).startswith("open"):          # alcuni file hanno l'intestazione
        d = d.iloc[1:]
    d.columns = COL[:d.shape[1]]
    d = d.drop(columns=["close_time", "ignore"], errors="ignore").astype(float)
    d["timestamp"] = pd.to_datetime(d["open_time"].astype("int64"), unit="ms", utc=True)
    return d.drop(columns="open_time")


def main():
    s, a, b = sys.argv[1].upper(), int(sys.argv[2]), int(sys.argv[3])
    oggi = dt.date.today()
    os.makedirs(os.path.join(OUT, s), exist_ok=True)
    for y in range(a, b + 1):
        pezzi = []
        for m in range(1, 13):
            if dt.date(y, m, 1) >= dt.date(oggi.year, oggi.month, 1):
                break
            f = scarica(s, y, m)
            if f:
                pezzi.append(leggi(f))
            time.sleep(0.5)
        if not pezzi:
            print(f"{s} {y}: nessun dato", flush=True)
            continue
        d = pd.concat(pezzi).drop_duplicates("timestamp").sort_values("timestamp")
        d.to_parquet(os.path.join(OUT, s, f"{s}_M1_{y}.parquet"), index=False)
        print(f"{s} {y}: {len(d):>7} minuti {d.timestamp.min():%m-%d} -> {d.timestamp.max():%m-%d}", flush=True)


if __name__ == "__main__":
    main()
