#!/usr/bin/env python3
"""Appendice AL: obiettivi 1:5-1:12 x gestioni della posizione a gradini.

Finora il pareggio e' stato provato solo come soglia unica (+2R, +3R). Qui si
provano vere SCALE di trailing — a +3R lo stop va a pari, a +5R a +2R, e cosi'
via — e il trailing continuo (stop sempre a MFE meno k), incrociati con gli
obiettivi da 1:5 a 1:12.

Convenzione conservativa, la stessa di tutto il progetto: dentro il minuto lo
stop prevale sull'obiettivo, e la scala si aggiorna DOPO aver controllato lo
stop di quel minuto (non sappiamo in che ordine il prezzo abbia toccato i due
estremi, quindi si sceglie l'ipotesi sfavorevole).

Uso: python3 run_scale_trailing.py
Scrive docs/studies/dati/scale-trailing.parquet
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OBIETTIVI = [5, 6, 7, 8, 9, 10, 12]

# (nome, scala, trail): la scala e' una lista di (soglia -> dove va lo stop),
# il trail e' (da che punto parte, di quanto sta sotto il massimo)
GESTIONI = [
    ("stop fisso",             [],                        None),
    ("pari a +2R",             [(2, 0)],                  None),
    ("pari a +3R (in uso)",    [(3, 0)],                  None),
    ("pari a +5R",             [(5, 0)],                  None),
    ("scala 3>0 5>2",          [(3, 0), (5, 2)],          None),
    ("scala 3>0 5>2 7>4",      [(3, 0), (5, 2), (7, 4)],  None),
    ("scala 2>0 4>2 6>4",      [(2, 0), (4, 2), (6, 4)],  None),
    ("scala 5>0 8>4",          [(5, 0), (8, 4)],          None),
    ("scala 4>1 7>4",          [(4, 1), (7, 4)],          None),
    ("trail MFE-2 da +3R",     [],                        (3, 2)),
    ("trail MFE-3 da +4R",     [],                        (4, 3)),
    ("trail MFE-4 da +6R",     [],                        (6, 4)),
]


def esito(fav, sfav, r_eod, rr, scala, trail):
    """R dell'operazione con obiettivo ``rr`` e la gestione data.

    ``fav[i]``/``sfav[i]`` sono l'escursione favorevole e contraria del minuto
    i, in multipli del rischio. Lo stop vive a un livello in R: parte da -1 e
    sale quando la scala (o il trailing) si attiva.
    """
    livello = -1.0
    mfe = 0.0
    for i in range(len(fav)):
        if sfav[i] >= -livello:                  # 1) lo stop, per primo
            if livello <= -1:
                return livello, 0                # stop pieno
            return livello, (3 if livello == 0 else 4)   # pareggio / stop in utile
        if fav[i] >= rr:                         # 2) poi l'obiettivo
            return float(rr), 1
        mfe = max(mfe, fav[i])                   # 3) infine la protezione
        for soglia, dove in scala:
            if mfe >= soglia:
                livello = max(livello, float(dove))
        if trail is not None and mfe >= trail[0]:
            livello = max(livello, mfe - trail[1])
    return max(r_eod, livello), 2                # fine giornata


def conto_dd(r, f):
    eq = pk = 1.0
    dd = 0.0
    for x in r:
        eq *= 1 + f * x
        pk = max(pk, eq)
        dd = max(dd, (pk - eq) / pk)
    return eq, dd


def pari_dd(r, bersaglio):
    lo, hi = 1e-4, 0.06
    for _ in range(40):
        f = (lo + hi) / 2
        if conto_dd(r, f)[1] > bersaglio:
            hi = f
        else:
            lo = f
    return conto_dd(r, (lo + hi) / 2)[0]


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [op for op in genera(m1, T)
           if all(op[f"c_{tf}"] for tf in T.conferme)
           and all(not op[f"c_{tf}"] for tf in T.ritracciamento)]
    anni = np.array([op["anno"] for op in ops])
    print(f"operazioni: {len(ops)}", flush=True)

    righe, serie = [], {}
    for nome, scala, trail in GESTIONI:
        for rr in OBIETTIVI:
            r = np.empty(len(ops))
            mo = np.empty(len(ops), dtype=int)
            for i, op in enumerate(ops):
                x, m = esito(op["fav"], op["sfav"], op["r_eod"], rr, scala, trail)
                r[i] = x - op["costo"]
                mo[i] = m
            eq, dd = conto_dd(r, 0.01)
            serie[(nome, rr)] = r
            righe.append({
                "gestione": nome, "rr": rr, "r_tot": r.sum(), "r_op": r.mean(),
                "stop_pct": (mo == 0).mean() * 100, "tp_pct": (mo == 1).mean() * 100,
                "prot_pct": (mo == 3).mean() * 100,
                "anni_pos": sum(1 for y in np.unique(anni) if r[anni == y].sum() > 0),
                "dd_pct": dd * 100, "conto": 10000 * eq})
        print(f"  {nome}", flush=True)

    base = next(x for x in righe
                if x["gestione"] == "pari a +3R (in uso)" and x["rr"] == 10)
    for x in righe:
        x["pari_dd"] = 10000 * pari_dd(serie[(x["gestione"], x["rr"])],
                                       base["dd_pct"] / 100)
    df = pd.DataFrame(righe)
    df.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                               "scale-trailing.parquet"), index=False)
    pd.set_option("display.width", 220)
    print("\nCONTO A PARITA' DI DRAWDOWN (euro da 10.000):")
    print(df.pivot(index="gestione", columns="rr", values="pari_dd").round(0).to_string())
    print("\nR TOTALE:")
    print(df.pivot(index="gestione", columns="rr", values="r_tot").round(1).to_string())
    print("\nle 8 celle migliori a parita' di drawdown:")
    print(df.nlargest(8, "pari_dd")[
        ["gestione", "rr", "r_tot", "r_op", "stop_pct", "tp_pct", "prot_pct",
         "anni_pos", "dd_pct", "conto", "pari_dd"]].round(2).to_string(index=False))
    print(f"\nriferimento in uso: {base['r_tot']:+.1f} R, conto {base['conto']:,.0f}, "
          f"DD {base['dd_pct']:.1f}%, {base['anni_pos']}/7 anni".replace(",", "."))


if __name__ == "__main__":
    main()
