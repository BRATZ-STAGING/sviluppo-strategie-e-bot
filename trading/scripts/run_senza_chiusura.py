#!/usr/bin/env python3
"""Appendice AO: le otto gestioni migliori SENZA la chiusura di fine giornata.

La chiusura alle 21 UTC serve a non tenere posizioni overnight (vincolo tipico
dei conti prop). Qui si toglie: si tiene aperto fino a stop o obiettivo, in due
regimi — chiusura al venerdi' sera e nessuna chiusura per tempo (tetto 30
giorni) — e si rivalutano le otto gestioni sopravvissute alla scrematura.

I percorsi vanno ricostruiti dai minuti: quelli di ``genera`` si fermano alla
fine della giornata.

Uso: python3 run_senza_chiusura.py
Scrive docs/studies/dati/senza-chiusura.parquet
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

from run_scale_trailing import GESTIONI, esito                   # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCELTE = [                       # le otto della scrematura (appendice AN)
    ("pari a +3R (in uso)", 10), ("pari a +3R (in uso)", 9),
    ("pari a +3R (in uso)", 8), ("scala 3>0 5>2", 10), ("stop fisso", 10),
    ("pari a +2R", 10), ("scala 4>1 7>4", 9), ("trail MFE-2 da +3R", 8),
]
REGIMI = ["giornaliera", "settimanale", "aperta"]
GIORNI_MAX = 30


def misure(r, mesi, anni):
    cum = np.cumsum(r)
    sotto = np.maximum.accumulate(cum) - cum
    lung = corr = 0
    for x in sotto:
        corr = corr + 1 if x > 1e-9 else 0
        lung = max(lung, corr)
    fila_p = fila_v = cp = cv = 0
    for x in r:
        cv, cp = (cv + 1, 0) if x > 0 else ((0, cp + 1) if x < 0 else (0, 0))
        fila_v, fila_p = max(fila_v, cv), max(fila_p, cp)
    pm = np.array([r[mesi == m].sum() for m in np.unique(mesi)])
    pa = np.array([r[anni == a].sum() for a in np.unique(anni)])
    eq = pk = 1.0
    ddp = 0.0
    for x in r:
        eq *= 1 + 0.01 * x
        pk = max(pk, eq)
        ddp = max(ddp, (pk - eq) / pk)
    return {"r_tot": r.sum(), "vinte_pct": (r > 0).mean() * 100,
            "dd_r": sotto.max(), "dd_pct": ddp * 100, "sottomax": lung,
            "fila_v": fila_v, "fila_p": fila_p,
            "mesi_pos": int((pm > 0).sum()), "mesi_tot": len(pm),
            "anni_pos": int((pa > 0).sum()), "anno_peg": pa.min(),
            "pf": r[r > 0].sum() / max(-r[r < 0].sum(), 1e-9),
            "conto_fisso": 10000 + 100 * r.sum()}


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [op for op in genera(m1, T)
           if all(op[f"c_{tf}"] for tf in T.conferme)
           and all(not op[f"c_{tf}"] for tf in T.ritracciamento)]
    anni = np.array([op["anno"] for op in ops])
    mesi = np.array([pd.Timestamp(op["time"]).strftime("%Y-%m") for op in ops])
    print(f"operazioni: {len(ops)}", flush=True)

    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    hi, lo, cl = m1.high.values, m1.low.values, m1.close.values

    # percorsi estesi, uno per regime
    percorsi = {r: [] for r in REGIMI}
    aperte = {r: [] for r in REGIMI}
    for op in ops:
        t_in = pd.Timestamp(op["time"]).tz_convert("UTC")
        segno = 1 if op["lato"] == "long" else -1
        e, k = op["entry"], op["rischio"]
        giorno = t_in.normalize()
        venerdi = giorno + pd.Timedelta(days=(4 - giorno.weekday()) % 7)
        fini = {"giornaliera": giorno + pd.Timedelta(hours=T.ora_chiusura),
                "settimanale": venerdi + pd.Timedelta(hours=T.ora_chiusura),
                "aperta": t_in + pd.Timedelta(days=GIORNI_MAX)}
        a = int(np.searchsorted(idx, t_in.value))
        for reg, fine in fini.items():
            b = int(np.searchsorted(idx, fine.value))
            h_, l_, c_ = hi[a:b], lo[a:b], cl[a:b]
            if segno == 1:
                fav, sfav = (h_ - e) / k, (e - l_) / k
            else:
                fav, sfav = (e - l_) / k, (h_ - e) / k
            r_eod = ((float(c_[-1]) - e) if segno == 1
                     else (e - float(c_[-1]))) / k
            percorsi[reg].append((fav, sfav, r_eod, op["costo"]))
            aperte[reg].append((t_in.value, b - a))

    righe = []
    for nome, rr in SCELTE:
        scala, trail = next((s, t) for n, s, t in GESTIONI if n == nome)
        for reg in REGIMI:
            r = np.array([esito(f, s, eod, rr, scala, trail)[0] - c
                          for f, s, eod, c in percorsi[reg]])
            righe.append({"gestione": nome, "rr": rr, "regime": reg,
                          **misure(r, mesi, anni)})
        print(f"  {nome} 1:{rr}", flush=True)

    df = pd.DataFrame(righe)
    df.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                               "senza-chiusura.parquet"), index=False)
    pd.set_option("display.width", 240)
    for reg in REGIMI:
        s = df[df.regime == reg]
        print(f"\n=== {reg.upper()}")
        print(s[["gestione", "rr", "r_tot", "vinte_pct", "dd_r", "sottomax",
                 "fila_p", "mesi_pos", "anni_pos", "anno_peg", "pf",
                 "conto_fisso"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
