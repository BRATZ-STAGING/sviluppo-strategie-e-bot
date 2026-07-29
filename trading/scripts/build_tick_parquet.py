#!/usr/bin/env python3
"""Converte la cache tick .bi5 di Dukascopy in Parquet mensili.

Il CSV serve a chi legge i tick con strumenti generici; per passarli a un'altra
sessione o a un altro bot il Parquet e' molto meglio: parecchie volte piu'
piccolo, tipizzato, e si carica con una riga (``pd.read_parquet``).

Uso (Windows, PowerShell):
    $env:TICKS_CACHE = "C:\\dukascopy\\ticks_cache"
    python build_tick_parquet.py C:\\dukascopy\\parquet_out 2022-11 2026-07

La cache e' quella prodotta da ``download_ticks.py``: file tutti nella stessa
cartella, un file per ora, chiamati ``YYYY-MM-DD_HH.bi5`` (le ore senza scambi
sono marcate con un file ``.empty`` e qui non contano).

Output, un file per mese: ``XAUUSD_ticks_YYYY-MM.parquet`` con colonne
- ``timestamp``  datetime64[ms, UTC], ordinato
- ``bid``, ``ask``  float32, in dollari
piu' ``INDICE.csv`` con conteggi, spread mediano e ore mancanti per mese.

Trappole del formato Dukascopy, gia' pagate: record di 20 byte
``>3i2f`` = (millisecondi dall'inizio dell'ora, **ask**, **bid**, volume ask,
volume bid), prezzi interi in millesimi. L'ask viene PRIMA del bid: invertirli
produce spread negativi. I millisecondi vanno sommati in int64, con int32 si va
in overflow.

Richiede: pip install pandas pyarrow numpy
"""
import datetime as dt
import glob
import lzma
import os
import sys

import numpy as np
import pandas as pd

CACHE = os.environ.get("TICKS_CACHE", os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "ticks_cache"))
SCALE = 1000.0
REC = 20


def leggi_ora(path):
    """(timestamp in ms epoch, bid, ask) di un file orario, o None se vuoto."""
    nome = os.path.basename(path)                    # YYYY-MM-DD_HH.bi5
    giorno = dt.date.fromisoformat(nome[:10])
    ora = int(nome[11:13])
    base = int(dt.datetime(giorno.year, giorno.month, giorno.day, ora,
                           tzinfo=dt.timezone.utc).timestamp() * 1000)
    try:
        with open(path, "rb") as f:
            grezzo = f.read()
        if not grezzo:
            return None
        dati = lzma.decompress(grezzo)
    except (lzma.LZMAError, EOFError, OSError):
        return None
    n = len(dati) // REC
    if n == 0:
        return None
    a = np.frombuffer(dati[:n * REC], dtype=">i4").reshape(n, 5)
    ms = base + a[:, 0].astype(np.int64)             # int64: niente overflow
    ask = a[:, 1] / SCALE                            # attenzione: ask PRIMA
    bid = a[:, 2] / SCALE
    return ms, bid, ask


def ore_mancanti(anno, mese):
    """Ore feriali del mese che non risultano ne' scaricate ne' vuote."""
    giorno = dt.date(anno, mese, 1)
    mancanti = 0
    while giorno.month == mese:
        if giorno.weekday() != 5:                    # sabato: mercato chiuso
            for h in range(24):
                stem = os.path.join(CACHE, f"{giorno.isoformat()}_{h:02d}")
                if not os.path.exists(stem + ".bi5") and \
                        not os.path.exists(stem + ".empty"):
                    mancanti += 1
        giorno += dt.timedelta(days=1)
    return mancanti


def mesi(inizio, fine):
    y, m = inizio
    while (y, m) <= fine:
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    out_dir = sys.argv[1]
    inizio = tuple(map(int, sys.argv[2].split("-"))) if len(sys.argv) > 2 else (2022, 11)
    fine = tuple(map(int, sys.argv[3].split("-"))) if len(sys.argv) > 3 else (2026, 7)
    if not os.path.isdir(CACHE):
        print(f"ERRORE: cache non trovata in {CACHE}")
        print("Imposta TICKS_CACHE o metti lo script accanto a ticks_cache.")
        sys.exit(1)
    os.makedirs(out_dir, exist_ok=True)
    print(f"cache : {CACHE}")
    print(f"output: {out_dir}\n", flush=True)

    indice = []
    for anno, mese in mesi(inizio, fine):
        files = sorted(glob.glob(os.path.join(CACHE, f"{anno}-{mese:02d}-*.bi5")))
        pezzi = [p for p in (leggi_ora(f) for f in files) if p is not None]
        if not pezzi:
            print(f"{anno}-{mese:02d}: nessun tick in cache", flush=True)
            continue
        ms = np.concatenate([p[0] for p in pezzi])
        bid = np.concatenate([p[1] for p in pezzi])
        ask = np.concatenate([p[2] for p in pezzi])
        ordine = np.argsort(ms, kind="stable")
        ms, bid, ask = ms[ordine], bid[ordine], ask[ordine]

        df = pd.DataFrame({
            "timestamp": pd.to_datetime(ms, unit="ms", utc=True),
            "bid": bid.astype("float32"),
            "ask": ask.astype("float32"),
        })
        negativi = int((df.ask < df.bid).sum())
        spread = float(np.median(ask - bid))
        buchi = ore_mancanti(anno, mese)
        path = os.path.join(out_dir, f"XAUUSD_ticks_{anno}-{mese:02d}.parquet")
        df.to_parquet(path, index=False, compression="zstd")
        mb = os.path.getsize(path) / 1e6
        indice.append({"mese": f"{anno}-{mese:02d}", "tick": len(df),
                       "spread_mediano": round(spread, 3),
                       "ask_sotto_bid": negativi, "ore_mancanti": buchi,
                       "MB": round(mb, 1)})
        print(f"{anno}-{mese:02d}: {len(df):>10,} tick   spread {spread:.3f}$   "
              f"{buchi:>3} ore mancanti   {mb:6.1f} MB", flush=True)

    if not indice:
        print("\nNessun mese convertito: controlla il periodo richiesto.")
        return
    idx = pd.DataFrame(indice)
    idx.to_csv(os.path.join(out_dir, "INDICE.csv"), index=False)
    print(f"\n{len(idx)} mesi, {idx.tick.sum():,} tick, {idx.MB.sum():.0f} MB")
    print(f"indice in {os.path.join(out_dir, 'INDICE.csv')}")
    if idx.ask_sotto_bid.sum():
        print(f"\nATTENZIONE: {idx.ask_sotto_bid.sum()} tick con ask < bid: "
              "l'ordine dei campi non torna, NON consegnare questi file.")
    else:
        print("verifica ask >= bid: superata su tutti i tick")


if __name__ == "__main__":
    main()
