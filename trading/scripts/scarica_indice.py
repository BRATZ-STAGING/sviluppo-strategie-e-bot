#!/usr/bin/env python3
"""Scarica da Dukascopy lo storico M1 di un indice (CFD), BID e ASK.

Stessa fonte, stesso formato e stessa logica riavviabile di
``estendi_storico.py``, generalizzati a un simbolo qualunque. Serve per
misurare l'Opening Range Breakout sul mercato in cui e' nato — un indice
azionario — su dati che arrivano a **oggi** e non si fermano al 2018 come
l'archivio HistData usato nelle appendici BJ e BK.

PERCHE' ANCHE L'ASK. Nell'appendice BK il risultato dipende interamente
dall'ipotesi sui costi: il vantaggio lordo vale ~0,05 R/op e il pareggio cade
a ~0,32 punti indice tondi. Con lo scarto denaro-lettera VERO, scaricato
minuto per minuto, il costo smette di essere un'ipotesi e diventa una misura.

FORMATO: file giornalieri ``{BID,ASK}_candles_min_1.bi5``, XZ, record da 24
byte ``>5if`` (secondo dall'inizio del giorno, apertura, chiusura, minimo,
massimo, volume). Prezzi interi in **millesimi** anche per gli indici
(5432111 -> 5432,111). Timestamp UTC etichettati all'apertura del minuto.
ATTENZIONE: nell'URL il **mese e' 0-based**.

Riavviabile: i file in cache non si riscaricano, i giorni vuoti (festivi,
fine settimana) si marcano ``.empty`` e non si ritentano.

Uso:  python3 scarica_indice.py USA500IDXUSD 2012 2026
      python3 scarica_indice.py USA500IDXUSD 2012 2026 --solo-bid
Env:  IDX_CACHE (cache), IDX_OUT (parquet), LOTTO (giorni per curl)
"""
from __future__ import annotations

import datetime as dt
import lzma
import os
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE = os.environ.get("IDX_CACHE", os.path.join(ROOT, "..", "cache_indici"))
USCITA = os.environ.get("IDX_OUT", os.path.join(ROOT, "..", "dati_grezzi", "indici"))
LOTTO = int(os.environ.get("LOTTO", "400"))
SCALE = 1000.0
REC = np.dtype([("s", ">i4"), ("o", ">i4"), ("c", ">i4"),
                ("l", ">i4"), ("h", ">i4"), ("v", ">f4")])


def url_di(simbolo, lato, g):
    return (f"https://datafeed.dukascopy.com/datafeed/{simbolo}/{g.year}/"
            f"{g.month - 1:02d}/{g.day:02d}/{lato}_candles_min_1.bi5")


def base(simbolo, lato, g):
    return os.path.join(CACHE, simbolo, lato, g.isoformat())


def in_cache(simbolo, lato, g):
    b = base(simbolo, lato, g)
    return os.path.exists(b + ".bi5") or os.path.exists(b + ".empty")


def tira(simbolo, lato, giorni):
    """Un giro di curl in parallelo sui giorni indicati, senza marcare niente.

    curl -Z riusa le connessioni: attraverso il proxy e' circa quattro volte
    piu' veloce di altrettanti thread Python, che ririnegoziano il TLS a ogni
    file.

    NIENTE ``--fail-early``. Con quell'opzione il primo 404 (o il primo scatto
    del rate limiting) abortisce **l'intero blocco**, e i giorni che non hanno
    fatto in tempo a scaricarsi finivano marcati ``.empty`` per sempre: e' cosi'
    che si sono persi interi anni (BID 2022, 2024, 2026 e ASK 2025 hanno 312+
    marcatori ``.empty`` e zero file). Il costo di toglierla e' qualche secondo,
    il beneficio e' non buttare via un anno.
    """
    if not giorni:
        return
    conf = os.path.join(CACHE, "_curl.conf")
    with open(conf, "w") as f:
        for g in giorni:
            f.write(f'url = "{url_di(simbolo, lato, g)}"\n'
                    f'output = "{base(simbolo, lato, g)}.bi5"\n')
    subprocess.run(["curl", "-sS", "-Z", "--parallel-max", "12",
                    "--retry", "3", "--retry-delay", "1", "-K", conf],
                   check=False)


def scarica(simbolo, lato, giorni):
    """Due passate, e solo dopo la seconda un giorno si dichiara vuoto.

    Un giorno davvero senza dati (festivo, fine settimana) torna a zero byte
    tutte e due le volte: quello e' un marcatore legittimo. Un giorno caduto
    per un problema di rete torna al secondo giro. Distinguere le due cose
    costa una passata sui soli mancanti e rende il marcatore affidabile.
    """
    if not giorni:
        return
    for passata in (1, 2):
        manca = [g for g in giorni
                 if not os.path.exists(base(simbolo, lato, g) + ".bi5")
                 or os.path.getsize(base(simbolo, lato, g) + ".bi5") == 0]
        if not manca:
            return
        tira(simbolo, lato, manca)
    for g in giorni:
        b = base(simbolo, lato, g)
        if not os.path.exists(b + ".bi5") or os.path.getsize(b + ".bi5") == 0:
            if os.path.exists(b + ".bi5"):
                os.remove(b + ".bi5")
            open(b + ".empty", "w").close()


def decodifica(simbolo, lato, g):
    b = base(simbolo, lato, g) + ".bi5"
    if not os.path.exists(b):
        return None
    try:
        d = lzma.decompress(open(b, "rb").read())
    except lzma.LZMAError:
        os.remove(b)                      # file troncato: si riscarica al giro dopo
        return None
    if len(d) < 24:
        return None
    v = np.frombuffer(d, dtype=REC, count=len(d) // 24)
    t = pd.to_datetime(g) + pd.to_timedelta(v["s"].astype("int64"), unit="s")
    return pd.DataFrame({"open": v["o"] / SCALE, "high": v["h"] / SCALE,
                         "low": v["l"] / SCALE, "close": v["c"] / SCALE,
                         "volume": v["v"].astype(float)},
                        index=t.tz_localize("UTC"))


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    simbolo, da, a = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    lati = ["BID"] if "--solo-bid" in sys.argv else ["BID", "ASK"]
    for lato in lati:
        os.makedirs(os.path.join(CACHE, simbolo, lato), exist_ok=True)
    os.makedirs(os.path.join(USCITA, simbolo), exist_ok=True)

    oggi = dt.date.today()
    for anno in range(da, a + 1):
        giorni = [dt.date(anno, 1, 1) + dt.timedelta(days=i)
                  for i in range((dt.date(anno + 1, 1, 1) - dt.date(anno, 1, 1)).days)]
        giorni = [g for g in giorni if g < oggi and g.weekday() < 5 or g.weekday() == 6]
        for lato in lati:
            # decodifica() cancella i file troncati perche' si riscarichino: se
            # non si ricicla, quei giorni mancano dal parquet dell'anno anche se
            # il dato esiste. Due giri bastano, il secondo lavora sui resti.
            pezzi = []
            for _ in range(2):
                manca = [g for g in giorni if not in_cache(simbolo, lato, g)]
                if not manca:
                    break
                for i in range(0, len(manca), LOTTO):
                    scarica(simbolo, lato, manca[i:i + LOTTO])
                pezzi = [x for x in (decodifica(simbolo, lato, g) for g in giorni)
                         if x is not None and len(x)]
            if not pezzi:
                pezzi = [x for x in (decodifica(simbolo, lato, g) for g in giorni)
                         if x is not None and len(x)]
            if not pezzi:
                print(f"{anno} {lato}: nessun dato", flush=True)
                continue
            d = pd.concat(pezzi).sort_index()
            d = d[~d.index.duplicated(keep="first")]
            f = os.path.join(USCITA, simbolo, f"{lato}_{anno}.parquet")
            d.to_parquet(f)
            print(f"{anno} {lato}: {len(d):>7} minuti  "
                  f"{d.index.min():%m-%d} -> {d.index.max():%m-%d}", flush=True)


if __name__ == "__main__":
    main()
