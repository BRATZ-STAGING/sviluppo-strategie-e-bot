#!/usr/bin/env python3
"""Scarica i file tick orari XAUUSD da Dukascopy (riavviabile, firma Chrome).

Il datafeed Dukascopy lascia in timeout i client non-browser (filtro sulla
firma TLS): questo script usa curl_cffi per presentarsi come Chrome.

Requisito (una volta sola):  python -m pip install curl_cffi

Uso: python download_ticks.py [YYYY-MM-DD inizio] [YYYY-MM-DD fine]
Env opzionali: TICKS_CACHE, WORKERS (default 2), PACING (0.5s),
REQ_TIMEOUT (30s), BREAK_AFTER (5), BREAK_SLEEP (600s).

Circuit-breaker: dopo BREAK_AFTER errori consecutivi si ferma 10-60 min
(insistere durante una penalità del feed la allunga soltanto). Riavviabile:
i file già in cache non vengono riscaricati.
"""
import datetime as dt
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

try:
    from curl_cffi import requests as creq
except ImportError:
    print("Manca la libreria curl_cffi. Esegui prima:")
    print("  python -m pip install curl_cffi")
    sys.exit(1)

CACHE = os.environ.get("TICKS_CACHE", os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "ticks_cache"))
os.makedirs(CACHE, exist_ok=True)

START = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date(2022, 11, 1)
END = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else dt.date(2026, 7, 6)

WORKERS = int(os.environ.get("WORKERS", "2"))
PACING = float(os.environ.get("PACING", "0.5"))
REQ_TIMEOUT = float(os.environ.get("REQ_TIMEOUT", "30"))
BREAK_AFTER = int(os.environ.get("BREAK_AFTER", "5"))
BREAK_SLEEP = float(os.environ.get("BREAK_SLEEP", "600"))

_tls = threading.local()


def _session():
    if not hasattr(_tls, "s"):
        _tls.s = creq.Session()
    return _tls.s


_lock = threading.Lock()
_consec_errors = 0
_pause_until = 0.0
_break_mult = 1.0


def _note_result(ok: bool):
    """Aggiorna il circuit-breaker in modo thread-safe."""
    global _consec_errors, _pause_until, _break_mult
    with _lock:
        if ok:
            _consec_errors = 0
            _break_mult = 1.0
        else:
            _consec_errors += 1
            if _consec_errors >= BREAK_AFTER:
                pause = min(BREAK_SLEEP * _break_mult, 3600)
                _pause_until = time.time() + pause
                _break_mult *= 2
                _consec_errors = 0
                print(f"CIRCUITO APERTO: pausa {pause/60:.0f} min "
                      f"(il feed sta penalizzando)", flush=True)


def _wait_if_open():
    while True:
        with _lock:
            wait = _pause_until - time.time()
        if wait <= 0:
            return
        time.sleep(min(wait, 30))


def url_for(d, h):
    # mese 0-based nel datafeed Dukascopy
    return (f"https://datafeed.dukascopy.com/datafeed/XAUUSD/"
            f"{d.year}/{d.month-1:02d}/{d.day:02d}/{h:02d}h_ticks.bi5")


def fetch(dh):
    d, h = dh
    stem = os.path.join(CACHE, f"{d.isoformat()}_{h:02d}")
    if os.path.exists(stem + ".bi5") or os.path.exists(stem + ".empty"):
        return "skip"
    for attempt in range(4):
        _wait_if_open()
        time.sleep(PACING + random.uniform(0, PACING))
        try:
            r = _session().get(url_for(d, h), impersonate="chrome",
                               timeout=REQ_TIMEOUT)
            if r.status_code == 404 or (r.status_code == 200 and not r.content):
                open(stem + ".empty", "wb").close()
                _note_result(True)
                return "empty"
            if r.status_code != 200:
                _note_result(False)
                continue
            tmp = stem + ".tmp"
            with open(tmp, "wb") as f:
                f.write(r.content)
            os.replace(tmp, stem + ".bi5")
            _note_result(True)
            return "ok"
        except Exception:
            _note_result(False)
    return "fail"


def main():
    hours = []
    d = START
    while d <= END:
        if d.weekday() != 5:  # sabato: mercato chiuso
            for h in range(24):
                hours.append((d, h))
        d += dt.timedelta(days=1)
    todo = [x for x in hours
            if not os.path.exists(os.path.join(CACHE, f"{x[0].isoformat()}_{x[1]:02d}.bi5"))
            and not os.path.exists(os.path.join(CACHE, f"{x[0].isoformat()}_{x[1]:02d}.empty"))]
    print(f"ore totali={len(hours)} da scaricare={len(todo)} "
          f"(workers={WORKERS} pacing={PACING}s timeout={REQ_TIMEOUT}s)", flush=True)
    done = ok = emp = fail = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for res in ex.map(fetch, todo):
            done += 1
            ok += res == "ok"; emp += res == "empty"; fail += res == "fail"
            if done % 100 == 0 or done == len(todo):
                rate = done / (time.time() - t0)
                eta = (len(todo) - done) / rate / 3600 if rate else 0
                print(f"{done}/{len(todo)} ok={ok} empty={emp} fail={fail} "
                      f"rate={rate:.2f}/s eta={eta:.1f}h", flush=True)
    print(f"FINE ok={ok} empty={emp} fail={fail}", flush=True)
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
