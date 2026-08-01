#!/usr/bin/env python3
"""Appendice AF: stop strutturale scalato x obiettivo, sulle 348 ufficiali.

Il moltiplicatore ``m`` allarga (m>1) o stringe (m<1) lo stop strutturale.
Il percorso favorevole/sfavorevole e' espresso in multipli del rischio, quindi
scalare lo stop equivale a dividere il percorso per ``m``; anche il costo
dello spread si riscala, perche' in R vale spread/rischio.

Uso: python3 run_stop_rr.py
Scrive docs/studies/dati/stop-rr.parquet (una riga per cella).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.gestione import chiusura_fine_giornata, esito_indice  # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MOLTI = [0.50, 0.75, 1.00, 1.25, 1.50, 2.00]
OBIETTIVI = [2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0]
PAREGGI = [None, 3.0]


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [op for op in genera(m1, T)
           if all(op[f"c_{tf}"] for tf in T.conferme)
           and all(not op[f"c_{tf}"] for tf in T.ritracciamento)]
    anni = np.array([op["anno"] for op in ops])
    print(f"operazioni ufficiali: {len(ops)}", flush=True)

    righe = []
    for m in MOLTI:
        # percorsi e costo riscalati: stop m volte piu' largo => R m volte piu'
        # piccole, ma anche lo spread pesa m volte meno
        scal = [(op["fav"] / m, op["sfav"] / m, op["r_eod"] / m,
                 op["mfe"] / m, op["costo"] / m) for op in ops]
        for rr in OBIETTIVI:
            for be in PAREGGI:
                r = np.empty(len(ops))
                motivi = np.empty(len(ops), dtype=int)
                for i, (fav, sfav, eod, mfe, costo) in enumerate(scal):
                    x, mo, _ = esito_indice(fav, sfav, rr, be=be, costo=0.0)
                    if x is None:
                        x = chiusura_fine_giornata(eod, be, False, mfe, 0.0)
                        mo = 2
                    r[i] = x - costo
                    motivi[i] = mo
                eq = pk = 1.0
                dd = 0.0
                for x in r:
                    eq *= 1 + T.rischio_per_operazione * x
                    pk = max(pk, eq)
                    dd = max(dd, (pk - eq) / pk)
                righe.append({
                    "m": m, "rr": rr, "be": -1.0 if be is None else be,
                    "r_tot": float(r.sum()), "r_op": float(r.mean()),
                    "stop_pct": float((motivi == 0).mean() * 100),
                    "tp_pct": float((motivi == 1).mean() * 100),
                    "anni_pos": int(sum(1 for y in np.unique(anni)
                                        if r[anni == y].sum() > 0)),
                    "dd_pct": float(dd * 100), "conto": float(10000 * eq)})
        print(f"  m={m:.2f} fatto", flush=True)

    df = pd.DataFrame(righe)
    dest = os.path.join(ROOT, "docs", "studies", "dati", "stop-rr.parquet")
    df.to_parquet(dest, index=False)
    pd.set_option("display.width", 200)
    print("\nR totale per moltiplicatore x obiettivo (pareggio +3R):")
    piv = df[df.be == 3.0].pivot(index="m", columns="rr", values="r_tot")
    print(piv.round(1).to_string())
    print("\nanni positivi (pareggio +3R):")
    print(df[df.be == 3.0].pivot(index="m", columns="rr",
                                 values="anni_pos").to_string())
    print("\nmigliori 8 celle su tutte e 84:")
    print(df.nlargest(8, "r_tot")[["m", "rr", "be", "r_tot", "r_op", "stop_pct",
                                   "tp_pct", "anni_pos", "dd_pct", "conto"]]
          .round(2).to_string(index=False))
    print(f"\n{dest}")


if __name__ == "__main__":
    main()
