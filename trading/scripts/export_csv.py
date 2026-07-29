#!/usr/bin/env python3
"""Esporta lo storico M1 in CSV per uso con bot/piattaforme esterne.

Uso: python3 export_csv.py <cartella_output> [formato]
Formati:
- generic (default): timestamp ISO UTC, open, high, low, close, volume
- mt5: Date,Time separati (yyyy.MM.dd,HH:MM) per l'import in MetaTrader
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def main():
    out_dir = sys.argv[1]
    fmt = sys.argv[2] if len(sys.argv) > 2 else "generic"
    os.makedirs(out_dir, exist_ok=True)
    data_dir = os.path.join(ROOT, "data", "XAUUSD_M1")
    import glob
    for path in sorted(glob.glob(os.path.join(data_dir, "XAUUSD_M1_*.parquet"))):
        year = os.path.basename(path)[10:14]
        df = pd.read_parquet(path)
        if fmt == "mt5":
            out = pd.DataFrame({
                "Date": df.timestamp.dt.strftime("%Y.%m.%d"),
                "Time": df.timestamp.dt.strftime("%H:%M"),
                "Open": df.open, "High": df.high, "Low": df.low,
                "Close": df.close, "Volume": df.volume,
            })
            name = f"XAUUSD_M1_{year}_mt5.csv"
        else:
            out = df.copy()
            out["timestamp"] = out.timestamp.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            name = f"XAUUSD_M1_{year}.csv"
        dest = os.path.join(out_dir, name)
        out.to_csv(dest, index=False, float_format="%.3f")
        print(f"{name}: {len(out):,} righe, {os.path.getsize(dest)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
