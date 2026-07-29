#!/usr/bin/env python3
"""Converte la cache di file .bi5 (candele M1 BID Dukascopy) in Parquet, un file per anno."""
import os, sys, lzma, struct, glob, datetime as dt
import pandas as pd

SP = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(SP, "cache")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SP, "parquet")
os.makedirs(OUT, exist_ok=True)

PRICE_SCALE = 1000.0  # XAUUSD: prezzi interi in millesimi

def parse_day(path):
    day = dt.date.fromisoformat(os.path.basename(path)[:10])
    raw = lzma.decompress(open(path, "rb").read())
    n = len(raw) // 24
    base = int(dt.datetime(day.year, day.month, day.day,
                           tzinfo=dt.timezone.utc).timestamp())
    rows = []
    for i in range(n):
        sec, o, c, lo, hi, vol = struct.unpack(">5if", raw[i*24:(i+1)*24])
        if vol == 0.0 and o == c == lo == hi:
            continue  # minuto di riempimento (mercato chiuso)
        rows.append((base + sec, o / PRICE_SCALE, hi / PRICE_SCALE,
                     lo / PRICE_SCALE, c / PRICE_SCALE, float(vol)))
    return rows

def main():
    files = sorted(glob.glob(os.path.join(CACHE, "*.bi5")))
    print(f"file bi5 in cache: {len(files)}")
    by_year = {}
    for p in files:
        year = int(os.path.basename(p)[:4])
        by_year.setdefault(year, []).append(p)
    for year in sorted(by_year):
        rows = []
        for p in by_year[year]:
            try:
                rows.extend(parse_day(p))
            except Exception as e:
                print(f"ERRORE {p}: {e}", file=sys.stderr)
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df.pop("ts"), unit="s", utc=True)
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        df = df.sort_values("timestamp").reset_index(drop=True)
        assert df["timestamp"].is_unique, f"timestamp duplicati nel {year}"
        assert ((df.high >= df.low) & (df.high >= df.open) & (df.high >= df.close)
                & (df.low <= df.open) & (df.low <= df.close)).all(), f"OHLC incoerenti nel {year}"
        out = os.path.join(OUT, f"XAUUSD_M1_{year}.parquet")
        df.to_parquet(out, index=False, compression="zstd")
        mb = os.path.getsize(out) / 1e6
        print(f"{year}: {len(df):>7} candele  {df.timestamp.min()} -> {df.timestamp.max()}  {mb:.1f} MB")

if __name__ == "__main__":
    main()
