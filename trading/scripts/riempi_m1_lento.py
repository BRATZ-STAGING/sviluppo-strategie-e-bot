#!/usr/bin/env python3
"""Riempie la cache M1 Dukascopy UN GIORNO ALLA VOLTA, per quando il feed limita.

`estendi_storico.py` scarica in parallelo e Dukascopy, sulle raffiche, risponde
429 o non risponde per ore (06/10/2026). Questo script chiede un file alla
volta, con una pausa fissa e un'attesa che raddoppia a ogni 429/timeout (fino a
15 minuti). Stessa cache e stessi nomi di `estendi_storico.py`: quando la cache
e' piena, `python3 estendi_storico.py 2026 2026 --rifai` ricostruisce l'anno.

Uso:  python3 riempi_m1_lento.py 2026-07-07            (fino a ieri)
      python3 riempi_m1_lento.py 2026-07-07 2026-10-05
"""
import datetime as dt
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from estendi_storico import CACHE, gia_in_cache, url_di  # noqa: E402

PAUSA = 6


def main():
    da = dt.date.fromisoformat(sys.argv[1])
    a = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else dt.date.today() - dt.timedelta(days=1)
    os.makedirs(CACHE, exist_ok=True)
    giorni = [da + dt.timedelta(days=k) for k in range((a - da).days + 1)]
    giorni = [g for g in giorni if g.weekday() != 5]          # sabato chiuso
    attesa = 60
    for g in giorni:
        if gia_in_cache(g):
            continue
        dest = os.path.join(CACHE, f"{g.isoformat()}.bi5")
        while True:
            r = subprocess.run(["curl", "-sS", "--max-time", "30", "-o", dest, "-w", "%{http_code}",
                                url_di(g)], capture_output=True, text=True)
            codice = r.stdout.strip()
            if codice == "200":
                if os.path.getsize(dest) == 0:                # giorno di festa
                    os.remove(dest)
                    open(dest[:-4] + ".empty", "wb").close()
                print(f"{g} ok", flush=True)
                attesa = 60
                break
            if os.path.exists(dest):
                os.remove(dest)
            if codice == "404":
                print(f"{g} 404 (nessun dato)", flush=True)
                break
            print(f"{g} {codice or r.stderr.strip()[:60]}: attendo {attesa}s", flush=True)
            time.sleep(attesa)
            attesa = min(attesa * 2, 900)
        time.sleep(PAUSA)
    print(f"FINE: {sum(gia_in_cache(g) for g in giorni)}/{len(giorni)} giorni in cache", flush=True)


if __name__ == "__main__":
    main()
