#!/usr/bin/env python3
"""Aggiorna lo storico M1 scaricando da Dukascopy le ore mancanti.

Pensato per girare AUTOMATICAMENTE (attivita' pianificata ogni 15 minuti):
guarda l'ultimo minuto presente nel Parquet dell'anno, scarica solo le ore
successive che il feed ha gia' pubblicato, ricostruisce le candele M1 (BID,
come tutto lo storico) e riscrive il Parquet.

Limite del feed, misurato: un'ora diventa disponibile solo DOPO che si e'
conclusa, quindi il ritardo massimo e' di circa un'ora. Per i livelli in
tempo reale la fonte giusta e' MT5 (vedi ``livelli_ora.py``); questo script
serve a tenere aggiornato l'archivio su cui girano studi e laboratorio.

Riavviabile: i file gia' in cache non vengono riscaricati, e un'esecuzione
interrotta riprende da dove era arrivata.

Uso:  python3 aggiorna_dati.py            (fino a ora)
      python3 aggiorna_dati.py 2026-08-01 (fino a una data)
Env:  TICKS_CACHE (cartella cache), WORKERS (default 8)
"""
import datetime as dt
import lzma
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE = os.environ.get("TICKS_CACHE",
                       os.path.join(ROOT, "..", "ticks_cache"))
WORKERS = int(os.environ.get("WORKERS", "8"))
SCALE, REC = 1000.0, 20          # prezzi in millesimi, 20 byte per tick


def url_di(giorno, ora):
    # ATTENZIONE: nel percorso Dukascopy il mese e' 0-based
    return (f"https://datafeed.dukascopy.com/datafeed/XAUUSD/{giorno.year}/"
            f"{giorno.month - 1:02d}/{giorno.day:02d}/{ora:02d}h_ticks.bi5")


def scarica(arg):
    """Scarica un'ora se manca. Ritorna (percorso, esito)."""
    giorno, ora = arg
    dest = os.path.join(CACHE, f"{giorno.isoformat()}_{ora:02d}.bi5")
    if os.path.exists(dest):
        return dest, "cache"
    r = subprocess.run(["curl", "-sS", "--max-time", "25", "-f",
                        "-o", dest, url_di(giorno, ora)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        if os.path.exists(dest):
            os.remove(dest)
        return dest, "assente"        # ora non ancora pubblicata o festiva
    return dest, "nuovo"


def leggi(dest):
    """(timestamp_ms, bid) di un file orario, o None se vuoto."""
    nome = os.path.basename(dest)
    giorno = dt.date.fromisoformat(nome[:10])
    ora = int(nome[11:13])
    if not os.path.exists(dest) or os.path.getsize(dest) == 0:
        return None
    try:
        raw = lzma.decompress(open(dest, "rb").read())
    except lzma.LZMAError:
        os.remove(dest)               # file troncato: si riscarica al giro dopo
        return None
    n = len(raw) // REC
    if n == 0:
        return None
    a = np.frombuffer(raw[:n * REC], dtype=">i4").reshape(n, 5)
    base = int(dt.datetime(giorno.year, giorno.month, giorno.day, ora,
                           tzinfo=dt.timezone.utc).timestamp() * 1000)
    return base + a[:, 0].astype(np.int64), a[:, 2] / SCALE


def main():
    os.makedirs(CACHE, exist_ok=True)
    fine = (dt.datetime.fromisoformat(sys.argv[1]).replace(tzinfo=dt.timezone.utc)
            if len(sys.argv) > 1 else dt.datetime.now(dt.timezone.utc))
    anno = fine.year
    pq = os.path.join(ROOT, "data", "XAUUSD_M1", f"XAUUSD_M1_{anno}.parquet")
    if not os.path.exists(pq):
        raise SystemExit(f"manca {pq}: questo anno non e' ancora nello storico")
    vecchio = pd.read_parquet(pq)
    ultimo = pd.Timestamp(vecchio.timestamp.max())

    ore = []
    t = ultimo.to_pydatetime().replace(minute=0, second=0, microsecond=0)
    while t <= fine:
        if t.weekday() != 5:                     # il sabato il mercato e' chiuso
            ore.append((t.date(), t.hour))
        t += dt.timedelta(hours=1)
    if not ore:
        print("gia' aggiornato")
        return

    with ThreadPoolExecutor(WORKERS) as ex:
        esiti = list(ex.map(scarica, ore))
    nuovi = sum(1 for _, e in esiti if e == "nuovo")
    print(f"ore da coprire {len(ore)}: {nuovi} scaricate, "
          f"{sum(1 for _, e in esiti if e == 'cache')} gia' in cache, "
          f"{sum(1 for _, e in esiti if e == 'assente')} non ancora pubblicate",
          flush=True)

    pezzi = [leggi(d) for d, _ in esiti]
    pezzi = [p for p in pezzi if p is not None]
    if not pezzi:
        print("nessun tick nuovo")
        return
    ms = np.concatenate([p[0] for p in pezzi])
    bid = np.concatenate([p[1] for p in pezzi])
    s = pd.Series(bid, index=pd.to_datetime(ms, unit="ms", utc=True)).sort_index()
    m1 = s.resample("1min").agg(["first", "max", "min", "last", "count"]).dropna()
    m1.columns = ["open", "high", "low", "close", "volume"]
    m1 = m1[m1.index > ultimo]
    if m1.empty:
        print(f"nessuna candela nuova (storico gia' a {ultimo})")
        return

    nuovo = pd.concat([vecchio, m1.reset_index().rename(
        columns={"index": "timestamp"})], ignore_index=True)
    nuovo = nuovo.drop_duplicates(subset="timestamp").sort_values("timestamp")
    nuovo.to_parquet(pq, index=False)
    print(f"+{len(m1)} candele -> {nuovo.timestamp.max():%Y-%m-%d %H:%M} UTC, "
          f"ultimo prezzo {nuovo.close.iloc[-1]:.2f}")


if __name__ == "__main__":
    main()
