#!/usr/bin/env python3
"""Appendice BN: lo spread vero dell'oro, ora per ora e anno per anno.

L'appendice BM ha mostrato che lo scalp a pochi punti non muore per colpa
dell'ingresso: muore perche' 0,30 $ di spread su uno stop di 3 $ sono il 10%
del rischio, e il vantaggio lordo misurato e' la meta'. La domanda che resta
e' netta: **quel 0,30 $ e' il numero giusto, o e' una media che nasconde ore
molto piu' economiche?** Se esiste una finestra della giornata in cui lo
spread e' un terzo, lo scalp cambia natura; se non esiste, e' chiuso.

La taratura usa 0,30 $ come costo tondo. Qui non si assume niente: si scarica
il denaro-lettera vero, tick per tick, e si guarda dove sta.

CAMPIONE. I tick sono ~28 milioni l'anno: scaricarli tutti per rispondere a
questa domanda sarebbe uno spreco. Si prende un **campione sistematico** —
alcuni giorni per trimestre su piu' anni — che e' abbondante per stimare una
mediana oraria e permette di vedere se lo spread e' cambiato nel tempo. Il
campione e' sistematico e non casuale cosi' e' riproducibile.

FORMATO Dukascopy: un file per ora, ``.bi5`` LZMA, record da **20 byte**
``>3i2f`` (millisecondi dall'inizio dell'ora, **ask**, **bid**, volume ask,
volume bid). Prezzi interi in millesimi. ATTENZIONE: nell'URL il **mese e'
0-based** e l'ask viene PRIMA del bid — invertirli darebbe spread negativi.

IPOTESI PRE-REGISTRATE:
  A. lo spread ha una forma oraria marcata, con il minimo nelle ore di Londra
     e New York sovrapposte (12-16 UTC) e il massimo alla riapertura asiatica;
  B. nella finestra migliore lo spread e' abbastanza basso da rendere pagabile
     uno stop di 3 $ — cioe' sotto ~0,12 $, che e' il 4% di 3 $;
  C. lo spread e' cresciuto insieme alla volatilita' dal 2024 in poi.

Uso: python3 run_spread_orario.py [giorni_per_trimestre]
Scrive docs/studies/dati/spread_orario.parquet
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
CACHE = os.environ.get("TICK_CACHE", os.path.join(ROOT, "..", "cache_tick"))
ANNI = range(2021, 2027)
GIORNI_TRIM = int(sys.argv[1]) if len(sys.argv) > 1 else 4
REC = np.dtype([("ms", ">i4"), ("ask", ">i4"), ("bid", ">i4"),
                ("va", ">f4"), ("vb", ">f4")])


def giorni_campione():
    """Giorni fissi per trimestre: sistematico, quindi riproducibile."""
    fuori = []
    oggi = dt.date.today()
    for anno in ANNI:
        for mese in (2, 5, 8, 11):
            for k in range(GIORNI_TRIM):
                g = dt.date(anno, mese, 3 + k * 5)
                if g.weekday() < 5 and g < oggi:
                    fuori.append(g)
    return fuori


def url(g, h):
    # mese 0-based, come in tutto il feed Dukascopy
    return (f"https://datafeed.dukascopy.com/datafeed/XAUUSD/{g.year}/"
            f"{g.month - 1:02d}/{g.day:02d}/{h:02d}h_ticks.bi5")


def scarica(coppie):
    manca = [(g, h) for g, h in coppie
             if not os.path.exists(os.path.join(CACHE, f"{g}_{h:02d}.bi5"))
             and not os.path.exists(os.path.join(CACHE, f"{g}_{h:02d}.empty"))]
    if not manca:
        return
    conf = os.path.join(CACHE, "_curl.conf")
    for i in range(0, len(manca), 400):
        with open(conf, "w") as f:
            for g, h in manca[i:i + 400]:
                f.write(f'url = "{url(g, h)}"\n'
                        f'output = "{os.path.join(CACHE, f"{g}_{h:02d}.bi5")}"\n')
        subprocess.run(["curl", "-sS", "-Z", "--parallel-max", "12", "--retry", "3",
                        "--retry-delay", "1", "-K", conf], check=False)
        print(f"  scaricati {min(i + 400, len(manca))}/{len(manca)}", flush=True)
    for g, h in manca:
        p = os.path.join(CACHE, f"{g}_{h:02d}.bi5")
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            if os.path.exists(p):
                os.remove(p)
            open(os.path.join(CACHE, f"{g}_{h:02d}.empty"), "w").close()


def leggi(g, h):
    p = os.path.join(CACHE, f"{g}_{h:02d}.bi5")
    if not os.path.exists(p):
        return None
    try:
        d = lzma.decompress(open(p, "rb").read())
    except lzma.LZMAError:
        os.remove(p)
        return None
    if len(d) < 20:
        return None
    v = np.frombuffer(d, dtype=REC, count=len(d) // 20)
    sp = (v["ask"].astype(np.float64) - v["bid"].astype(np.float64)) / 1000.0
    return sp[(sp > 0) & (sp < 5)]          # oltre 5 $ e' un buco del feed


def main():
    os.makedirs(CACHE, exist_ok=True)
    giorni = giorni_campione()
    coppie = [(g, h) for g in giorni for h in range(24)]
    print(f"{len(giorni)} giorni, {len(coppie)} file orari", flush=True)
    scarica(coppie)

    righe = []
    for g, h in coppie:
        sp = leggi(g, h)
        if sp is None or len(sp) < 50:
            continue
        righe.append({"giorno": pd.Timestamp(g), "anno": g.year, "ora": h,
                      "tick": len(sp), "mediano": float(np.median(sp)),
                      "medio": float(sp.mean()), "q25": float(np.quantile(sp, .25)),
                      "q90": float(np.quantile(sp, .90))})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "spread_orario.parquet"), index=False)
    pd.set_option("display.width", 240)
    print(f"\nore utili: {len(t)}  ({t.tick.sum()/1e6:.1f} milioni di tick)")

    print("\n=== ipotesi A: la forma oraria (mediana dei giorni, $ )")
    per_ora = t.groupby("ora").agg(mediano=("mediano", "median"),
                                   q25=("q25", "median"), q90=("q90", "median"),
                                   tick=("tick", "median"))
    per_ora["%di 3$"] = per_ora.mediano / 3 * 100
    per_ora["%di 10$"] = per_ora.mediano / 10 * 100
    print(per_ora.round(3).to_string())

    print("\n=== ipotesi C: e' cambiato negli anni? (mediana per anno e fascia)")
    fasce = pd.cut(t.ora, [-1, 6, 11, 15, 20, 23],
                   labels=["asia 0-6", "londra 7-11", "sovrapp. 12-15",
                           "ny 16-20", "sera 21-23"])
    print(t.pivot_table(index="anno", columns=fasce, values="mediano",
                        aggfunc="median", observed=True).round(3).to_string())

    print("\n=== ipotesi B: la finestra migliore rende pagabile uno stop di 3 $?")
    ult = t[t.anno >= 2025]
    m = ult.groupby("ora").mediano.median().sort_values()
    print("  le 5 ore piu' economiche (2025-2026):")
    for ora, v in m.head(5).items():
        print(f"    {ora:02d}:00 UTC  spread {v:.3f} $  = {v/3*100:4.1f}% di uno "
              f"stop da 3 $  ->  serve un vantaggio lordo di {v/3:.3f} R per pareggiare")
    print(f"  soglia dell'ipotesi B: 0,120 $  ->  "
          f"{'SUPERATA' if m.min() <= 0.12 else 'NON superata (minimo %.3f $)' % m.min()}")


if __name__ == "__main__":
    main()
