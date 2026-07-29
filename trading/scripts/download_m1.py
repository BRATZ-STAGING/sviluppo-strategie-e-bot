#!/usr/bin/env python3
"""Scarica i file giornalieri BID_candles_min_1.bi5 di XAUUSD da Dukascopy.

Riavviabile: i file gia' scaricati (o marcati vuoti) vengono saltati.
Cache: <scratchpad>/cache/YYYY-MM-DD.bi5  oppure  YYYY-MM-DD.empty
"""
import os, sys, time, random, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import urllib.request, urllib.error, ssl

SP = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(SP, "cache")
os.makedirs(CACHE, exist_ok=True)

START = dt.date(2020, 1, 1)
END = dt.date(2026, 7, 6)  # ultimo giorno completo disponibile

ctx = ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")
proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
handlers = [urllib.request.HTTPSHandler(context=ctx)]
if proxy:
    handlers.insert(0, urllib.request.ProxyHandler({"https": proxy, "http": proxy}))
opener = urllib.request.build_opener(*handlers)

def url_for(d):
    # ATTENZIONE: nel datafeed Dukascopy il mese e' 0-based
    return (f"https://datafeed.dukascopy.com/datafeed/XAUUSD/"
            f"{d.year}/{d.month-1:02d}/{d.day:02d}/BID_candles_min_1.bi5")

def fetch(d):
    out = os.path.join(CACHE, f"{d.isoformat()}.bi5")
    empty = os.path.join(CACHE, f"{d.isoformat()}.empty")
    if os.path.exists(out) or os.path.exists(empty):
        return "skip"
    for attempt in range(6):
        try:
            req = urllib.request.Request(url_for(d), headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=120) as r:
                data = r.read()
            if len(data) == 0:
                open(empty, "wb").close()
                return "empty"
            tmp = out + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, out)
            return "ok"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                open(empty, "wb").close()
                return "empty"
            if e.code in (429, 503):
                time.sleep(8 * (attempt + 1) + random.uniform(0, 3))
                continue
            time.sleep(5 * (attempt + 1))
        except Exception:
            time.sleep(5 * (attempt + 1))
    return "fail"

def main():
    days = []
    d = START
    while d <= END:
        if d.weekday() != 5:  # sabato: mercato chiuso tutto il giorno
            days.append(d)
        d += dt.timedelta(days=1)
    todo = [d for d in days
            if not os.path.exists(os.path.join(CACHE, f"{d.isoformat()}.bi5"))
            and not os.path.exists(os.path.join(CACHE, f"{d.isoformat()}.empty"))]
    print(f"giorni totali={len(days)} da scaricare={len(todo)}", flush=True)
    done = ok = emp = fail = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=int(os.environ.get("WORKERS", "6"))) as ex:
        for res in ex.map(fetch, todo):
            done += 1
            ok += res == "ok"; emp += res == "empty"; fail += res == "fail"
            if done % 25 == 0 or done == len(todo):
                rate = done / (time.time() - t0)
                eta = (len(todo) - done) / rate if rate else 0
                print(f"{done}/{len(todo)} ok={ok} empty={emp} fail={fail} "
                      f"rate={rate:.2f}/s eta={eta/60:.0f}min", flush=True)
            time.sleep(0.1)
    print(f"FINE ok={ok} empty={emp} fail={fail}", flush=True)
    sys.exit(1 if fail else 0)

if __name__ == "__main__":
    main()
