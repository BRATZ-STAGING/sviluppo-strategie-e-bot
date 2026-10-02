#!/usr/bin/env python3
"""Scarica da HistData le candele M1 (ASCII) e le converte nello schema del repo.

Fonte gratuita per uso personale: https://www.histdata.com . Un file ZIP per
anno (``HISTDATA_COM_ASCII_<SIMBOLO>_M1<anno>.zip``) con un CSV
``AAAAMMGG HHMMSS;open;high;low;close;volume``.

ATTENZIONE AL FUSO: la documentazione di HistData dice "EST fisso", ma i
file sono in **ora di New York con l'ora legale** (verificato sui dati, vedi
``da_new_york``). Qui si convertono in UTC con il fuso vero, e
le candele restano etichettate all'apertura del minuto, come
``data/XAUUSD_M1``. I prezzi sono **BID**: lo spread non c'e' e va preso da
un'altra misura.

Riavviabile: gli ZIP gia' scaricati e integri non si riscaricano. Una
richiesta alla volta, con pausa, per non farsi bloccare.

Uso:  python scarica_histdata.py SIMBOLO anno_da anno_a
      (es. SPXUSD 2010 2026; simboli: SPXUSD NSXUSD GRXEUR XAGUSD ...)
Env:  HD_CACHE (zip, default D:\\histdata), HD_OUT (parquet, default
      data/histdata/<SIMBOLO>), PAUSA (secondi, default 6)
"""
from __future__ import annotations

import http.cookiejar
import io
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE = os.environ.get("HD_CACHE", r"D:\histdata")
PAUSA = float(os.environ.get("PAUSA", "6"))
BASE = "https://www.histdata.com"
PAGINA = BASE + "/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{s}/{a}"
UA = {"User-Agent": "Mozilla/5.0"}

_jar = http.cookiejar.CookieJar()
_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))


def scarica_zip(simbolo: str, anno: int, mese: int | None = None) -> str | None:
    """Uno ZIP annuale, oppure mensile per l'anno in corso (HistData pubblica
    l'anno corrente solo mese per mese)."""
    suff = f"{anno}" if mese is None else f"{anno}{mese:02d}"
    dest = os.path.join(CACHE, simbolo, f"HISTDATA_COM_ASCII_{simbolo}_M1{suff}.zip")
    if os.path.exists(dest) and zipfile.is_zipfile(dest):
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    pagina = PAGINA.format(s=simbolo.lower(), a=anno)
    if mese is not None:
        pagina += f"/{mese}"
    for tentativo in range(2 if mese is not None else 5):
        try:
            html = _op.open(urllib.request.Request(pagina, headers=UA), timeout=60).read().decode("utf-8", "ignore")
            campi = dict(re.findall(r'name="(tk|date|datemonth|platform|timeframe|fxpair)"[^>]*value="([^"]*)"', html))
            if "tk" not in campi:
                print(f"  {simbolo} {anno}: nessun modulo (anno non disponibile?)", flush=True)
                return None
            dati = urllib.parse.urlencode(campi).encode()
            req = urllib.request.Request(BASE + "/get.php", data=dati,
                                         headers={**UA, "Referer": pagina})
            blob = _op.open(req, timeout=180).read()
            if not blob.startswith(b"PK"):
                raise ValueError(f"risposta non zip ({len(blob)} byte)")
            tmp = dest + ".tmp"
            with open(tmp, "wb") as f:
                f.write(blob)
            if not zipfile.is_zipfile(tmp):
                raise ValueError("zip non valido")
            os.replace(tmp, dest)
            return dest
        except Exception as e:                      # noqa: BLE001
            attesa = 30 * (tentativo + 1)
            print(f"  {simbolo} {anno}: {e} -> riprovo fra {attesa}s", flush=True)
            time.sleep(attesa)
    return None


def da_new_york(locale: pd.Series) -> pd.Series:
    """Orari HistData (ora di New York CON ora legale) -> UTC.

    La documentazione HistData parla di "EST senza ora legale", ma i dati
    dicono altro (misurato il 02/10/2026): l'apertura cash dell'S&P cade alle
    09:30 dei file sia d'inverno sia d'estate, e il DAX apre un'ora "tardi"
    nelle settimane in cui solo gli USA sono in ora legale. Quindi i file sono
    in ora locale di New York e si convertono con il fuso vero.
    L'ora ripetuta di novembre (ambigua) si scarta; quella che non esiste a
    marzo si sposta in avanti.
    """
    utc = (locale.dt.tz_localize("America/New_York", ambiguous="NaT",
                                 nonexistent="shift_forward")
           .dt.tz_convert("UTC"))
    return utc


def converti(zip_path: str) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        raw = z.read(nome)
    d = pd.read_csv(io.BytesIO(raw), sep=";", header=None,
                    names=["t", "open", "high", "low", "close", "volume"])
    ts = da_new_york(pd.to_datetime(d["t"], format="%Y%m%d %H%M%S"))
    out = pd.DataFrame({"timestamp": ts,
                        "open": d["open"].astype(float), "high": d["high"].astype(float),
                        "low": d["low"].astype(float), "close": d["close"].astype(float),
                        "volume": d["volume"].astype(float)})
    out = out.dropna(subset=["timestamp"])
    return out.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    simbolo, da, a = sys.argv[1].upper(), int(sys.argv[2]), int(sys.argv[3])
    uscita = os.environ.get("HD_OUT", os.path.join(ROOT, "data", "histdata", simbolo))
    os.makedirs(uscita, exist_ok=True)
    oggi = time.localtime()
    lavori = []
    for anno in range(da, a + 1):
        if anno == oggi.tm_year:
            lavori += [(anno, m) for m in range(1, oggi.tm_mon + 1)]
        else:
            lavori.append((anno, None))
    for anno, mese in lavori:
        z = scarica_zip(simbolo, anno, mese)
        if z is None:
            print(f"{simbolo} {anno}{'' if mese is None else f'-{mese:02d}'}: NON scaricato", flush=True)
            continue
        df = converti(z)
        # Lo zip dell'anno A e' in EST: le ultime ore del 31/12 diventano, in
        # UTC, il primo gennaio di A+1. Ogni minuto va nel file del SUO anno UTC.
        for anno_utc, parte in df.groupby(df.timestamp.dt.year):
            f = os.path.join(uscita, f"{simbolo}_M1_{anno_utc}.parquet")
            if os.path.exists(f):
                parte = (pd.concat([pd.read_parquet(f), parte])
                         .drop_duplicates("timestamp").sort_values("timestamp"))
            parte.to_parquet(f, compression="zstd", index=False)
        print(f"{simbolo} {anno}: {len(df):>7} minuti  {df.timestamp.min():%Y-%m-%d %H:%M} -> "
              f"{df.timestamp.max():%Y-%m-%d %H:%M} UTC  ({os.path.getsize(z) / 1e6:.1f} MB zip)", flush=True)
        time.sleep(PAUSA)


if __name__ == "__main__":
    main()
