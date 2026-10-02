#!/usr/bin/env python3
"""Riempie la cache di ``scarica_indice.py`` rispettando il limite del datafeed.

PERCHE' ESISTE. Il datafeed Dukascopy risponde **429 (troppe richieste)** a
raffiche di connessioni, e da una linea domestica blocca per minuti. Il curl di
``scarica_indice.py`` scrive il corpo dell'errore (113 byte) al posto del file,
la decodifica fallisce, e dopo due giri il giorno finisce marcato ``.empty``
per sempre: cosi' il 02/10/2026 un anno intero (2012) era diventato "vuoto" in
un minuto.

Qui un giorno si marca vuoto SOLO se il server lo dice davvero: 404, oppure
200 con zero byte. Un 429/5xx/timeout fa aspettare (attesa crescente) e
riprovare, e non lascia mai un marcatore. Poche connessioni, pausa fra una
richiesta e l'altra.

Stesso schema di cache di ``scarica_indice.py``: <CACHE>/<SIMBOLO>/<LATO>/
<giorno>.bi5|.empty. Dopo, ``scarica_indice.py`` trova tutto in cache e si
limita a decodificare e scrivere i parquet.

Uso:  python riempi_cache_indice.py SIMBOLO anno_da anno_a
Env:  IDX_CACHE, PARALLELO (default 2), PAUSA (secondi, default 0.4)
"""
from __future__ import annotations

import datetime as dt
import os
import random
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE = os.environ.get("IDX_CACHE", os.path.join(ROOT, "..", "cache_indici"))
PARALLELO = int(os.environ.get("PARALLELO", "2"))
PAUSA = float(os.environ.get("PAUSA", "0.4"))

# Ambienti con proxy che intercetta il TLS (container): bundle e proxy si usano
# solo se presenti, cosi' lo stesso script gira anche su Windows senza niente.
_BUNDLE = os.environ.get("IDX_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
_gestori = []
if os.path.exists(_BUNDLE):
    _gestori.append(urllib.request.HTTPSHandler(
        context=ssl.create_default_context(cafile=_BUNDLE)))
_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
if _proxy:
    _gestori.insert(0, urllib.request.ProxyHandler({"https": _proxy, "http": _proxy}))
_apri = urllib.request.build_opener(*_gestori).open

_freno = threading.Lock()
_sosta_fino = [0.0]          # se il server ci rallenta, si fermano tutti


def url_di(simbolo, lato, g):
    # ATTENZIONE: nel datafeed Dukascopy il mese e' 0-based
    return (f"https://datafeed.dukascopy.com/datafeed/{simbolo}/{g.year}/"
            f"{g.month - 1:02d}/{g.day:02d}/{lato}_candles_min_1.bi5")


def scarica_giorno(simbolo, lato, g):
    base = os.path.join(CACHE, simbolo, lato, g.isoformat())
    if os.path.exists(base + ".bi5") or os.path.exists(base + ".empty"):
        return "skip"
    for tentativo in range(10):
        attesa = _sosta_fino[0] - time.time()
        if attesa > 0:
            time.sleep(attesa)
        time.sleep(PAUSA + random.uniform(0, PAUSA))
        try:
            req = urllib.request.Request(url_di(simbolo, lato, g),
                                         headers={"User-Agent": "Mozilla/5.0"})
            with _apri(req, timeout=60) as r:
                dati = r.read()
            if not dati:
                open(base + ".empty", "w").close()
                return "vuoto"
            tmp = base + ".tmp"
            with open(tmp, "wb") as f:
                f.write(dati)
            os.replace(tmp, base + ".bi5")
            return "ok"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                open(base + ".empty", "w").close()
                return "vuoto"
            ritardo = (20 * (tentativo + 1) if e.code in (429, 503)
                       else 5 * (tentativo + 1))
        except Exception:
            ritardo = 10 * (tentativo + 1)
        with _freno:
            _sosta_fino[0] = max(_sosta_fino[0], time.time() + ritardo)
    return "fallito"


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    simbolo, da, a = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    oggi = dt.date.today()
    lavori = []
    for anno in range(a, da - 1, -1):          # prima gli anni recenti
        g = dt.date(anno, 1, 1)
        while g.year == anno and g < oggi:
            if g.weekday() != 5:               # sabato chiuso
                for lato in ("BID", "ASK"):
                    lavori.append((lato, g))
            g += dt.timedelta(days=1)
    for lato in ("BID", "ASK"):
        os.makedirs(os.path.join(CACHE, simbolo, lato), exist_ok=True)
    conta = {"ok": 0, "vuoto": 0, "skip": 0, "fallito": 0}
    t0, fatti = time.time(), 0
    with ThreadPoolExecutor(PARALLELO) as ex:
        for esito in ex.map(lambda x: scarica_giorno(simbolo, *x), lavori):
            conta[esito] += 1
            fatti += 1
            if fatti % 200 == 0 or fatti == len(lavori):
                v = fatti / (time.time() - t0)
                print(f"{simbolo} {fatti}/{len(lavori)} {conta} "
                      f"{v:.1f}/s resto {(len(lavori) - fatti) / v / 60:.0f} min",
                      flush=True)
    print(f"{simbolo} FINE {conta}", flush=True)
    sys.exit(1 if conta["fallito"] else 0)


if __name__ == "__main__":
    main()
