#!/usr/bin/env python3
"""Estende all'indietro lo storico M1 scaricando gli anni mancanti da Dukascopy.

Stessa fonte e stesso formato dell'archivio esistente: file GIORNALIERI
``BID_candles_min_1.bi5`` (record da 24 byte: secondo, open, close, low, high,
volume float), prezzi BID interi in millesimi, timestamp UTC etichettati
all'apertura del minuto.

Riavviabile: i file gia' in cache non si riscaricano, i giorni senza dati si
marcano ``.empty`` e non si ritentano. Un anno gia' presente in
``data/XAUUSD_M1`` viene saltato salvo ``--rifai``.

Uso:  python3 estendi_storico.py 2013 2019
      python3 estendi_storico.py 2013 2019 --rifai
Env:  M1_CACHE (cartella cache), WORKERS (default 8)
"""
from __future__ import annotations

import datetime as dt
import glob
import lzma
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATI = os.path.join(ROOT, "data", "XAUUSD_M1")
CACHE = os.environ.get("M1_CACHE", os.path.join(ROOT, "..", "cache_m1"))
WORKERS = int(os.environ.get("WORKERS", "8"))
LOTTO = 300                         # giorni per invocazione di curl
SCALE = 1000.0                      # XAUUSD: prezzi interi in millesimi
REC = 24                            # byte per candela


def url_di(giorno: dt.date) -> str:
    # ATTENZIONE: nel datafeed Dukascopy il mese e' 0-based
    return (f"https://datafeed.dukascopy.com/datafeed/XAUUSD/{giorno.year}/"
            f"{giorno.month - 1:02d}/{giorno.day:02d}/BID_candles_min_1.bi5")


def gia_in_cache(giorno: dt.date) -> bool:
    base = os.path.join(CACHE, giorno.isoformat())
    return os.path.exists(base + ".bi5") or os.path.exists(base + ".empty")


def scarica_lotto(giorni: list[dt.date]) -> None:
    """Scarica un blocco di giorni con curl in modalita' parallela.

    curl -Z riusa le connessioni: attraverso il proxy e' circa quattro volte
    piu' veloce di altrettanti thread Python, che ririnegoziano il tunnel TLS
    a ogni file. I file a zero byte (giorni di festa) restano tali e vengono
    convertiti in marcatori ``.empty``.
    """
    conf = os.path.join(CACHE, "_curl.conf")
    with open(conf, "w") as f:
        for g in giorni:
            f.write(f'url = "{url_di(g)}"\n'
                    f'output = "{os.path.join(CACHE, g.isoformat())}.bi5"\n')
    subprocess.run(["curl", "-sS", "-Z", "--parallel-max", str(WORKERS),
                    "--retry", "4", "--retry-delay", "3", "--max-time", "90",
                    "-f", "-K", conf],
                   capture_output=True, text=True)
    os.remove(conf)
    for g in giorni:
        dest = os.path.join(CACHE, f"{g.isoformat()}.bi5")
        if os.path.exists(dest) and os.path.getsize(dest) == 0:
            os.remove(dest)
            open(dest[:-4] + ".empty", "wb").close()


def leggi(percorso: str) -> pd.DataFrame | None:
    """Candele M1 di un file giornaliero, o None se illeggibile/vuoto."""
    giorno = dt.date.fromisoformat(os.path.basename(percorso)[:10])
    try:
        raw = lzma.decompress(open(percorso, "rb").read())
    except lzma.LZMAError:
        os.remove(percorso)           # troncato: si riscarica al giro dopo
        return None
    n = len(raw) // REC
    if n == 0:
        return None
    a = np.frombuffer(raw[:n * REC], dtype=">i4").reshape(n, 6)
    vol = raw_vol(raw, n)
    sec, o, c, lo, hi = (a[:, i].astype(np.int64) for i in range(5))
    # i minuti di riempimento a mercato chiuso hanno volume nullo e OHLC piatto
    vivo = ~((vol == 0.0) & (o == c) & (o == lo) & (o == hi))
    base = int(dt.datetime(giorno.year, giorno.month, giorno.day,
                           tzinfo=dt.timezone.utc).timestamp())
    return pd.DataFrame({
        "timestamp": pd.to_datetime(base + sec[vivo], unit="s", utc=True),
        "open": o[vivo] / SCALE, "high": hi[vivo] / SCALE,
        "low": lo[vivo] / SCALE, "close": c[vivo] / SCALE,
        "volume": vol[vivo].astype(np.float64),
    })


def raw_vol(raw: bytes, n: int) -> np.ndarray:
    """Il volume e' l'ultimo campo del record, float32 big-endian."""
    return np.frombuffer(raw[:n * REC], dtype=">f4").reshape(n, 6)[:, 5]


def costruisci(anno: int, percorsi: list[str]) -> pd.DataFrame:
    pezzi = [d for d in (leggi(p) for p in percorsi) if d is not None]
    if not pezzi:
        raise SystemExit(f"{anno}: nessun file leggibile in cache")
    df = pd.concat(pezzi, ignore_index=True).sort_values("timestamp")
    df = df.drop_duplicates(subset="timestamp").reset_index(drop=True)
    if not df.timestamp.is_unique:
        raise SystemExit(f"{anno}: timestamp duplicati")
    male = ~((df.high >= df.low) & (df.high >= df.open) & (df.high >= df.close)
             & (df.low <= df.open) & (df.low <= df.close))
    if male.any():
        raise SystemExit(f"{anno}: {int(male.sum())} candele con OHLC incoerenti")
    return df


def main() -> None:
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    rifai = "--rifai" in sys.argv
    da = int(argv[0]) if argv else 2013
    a_ = int(argv[1]) if len(argv) > 1 else 2019
    os.makedirs(CACHE, exist_ok=True)

    anni = [y for y in range(da, a_ + 1)
            if rifai or not os.path.exists(
                os.path.join(DATI, f"XAUUSD_M1_{y}.parquet"))]
    if not anni:
        print("niente da fare: gli anni richiesti sono gia' nell'archivio")
        return

    giorni = []
    for y in anni:
        g = dt.date(y, 1, 1)
        while g.year == y:
            if g.weekday() != 5:            # il sabato il mercato e' chiuso
                giorni.append(g)
            g += dt.timedelta(days=1)
    print(f"anni {anni[0]}-{anni[-1]}: {len(giorni)} giorni da coprire", flush=True)

    t0 = time.time()
    for passata in range(1, 6):
        mancanti = [g for g in giorni if not gia_in_cache(g)]
        if not mancanti:
            break
        print(f"  passata {passata}: {len(mancanti)} da scaricare", flush=True)
        for i in range(0, len(mancanti), LOTTO):
            scarica_lotto(mancanti[i:i + LOTTO])
            fatti = sum(1 for g in giorni if gia_in_cache(g))
            print(f"    {fatti}/{len(giorni)} in cache, "
                  f"{time.time() - t0:.0f}s", flush=True)
    restano = [g for g in giorni if not gia_in_cache(g)]
    if restano:
        print(f"ATTENZIONE: {len(restano)} giorni non scaricati "
              f"(primo {restano[0]}), rilanciare lo script per riprenderli")

    righe = []
    for y in anni:
        percorsi = sorted(glob.glob(os.path.join(CACHE, f"{y}-*.bi5")))
        df = costruisci(y, percorsi)
        out = os.path.join(DATI, f"XAUUSD_M1_{y}.parquet")
        df.to_parquet(out, index=False, compression="zstd")
        attesi = len(pd.bdate_range(f"{y}-01-01", f"{y}-12-31"))
        righe.append({
            "anno": y, "candele": len(df), "giorni": df.timestamp.dt.date.nunique(),
            "gg_attesi": attesi, "primo": str(df.timestamp.min())[:10],
            "ultimo": str(df.timestamp.max())[:10],
            "min/gg": round(len(df) / max(df.timestamp.dt.date.nunique(), 1)),
            "MB": round(os.path.getsize(out) / 1e6, 1),
        })
    pd.set_option("display.width", 200)
    print(pd.DataFrame(righe).to_string(index=False))


if __name__ == "__main__":
    main()
