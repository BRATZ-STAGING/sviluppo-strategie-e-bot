#!/usr/bin/env python3
"""Appendice AC: sensibilita' della taratura, un parametro alla volta.

Per ogni variante passata come ``campo=valore`` rigenera le operazioni con la
taratura ufficiale modificata SOLO in quel campo e valuta l'esito ufficiale
(obiettivo e pareggio della taratura stessa). Stampa una riga per variante e
accoda i risultati a docs/studies/dati/sensibilita.parquet.

Uso: python3 run_sensibilita.py base ora_inizio=6 buffer=0.60 ...
(una lista per processo: i campi si spartiscono fra processi paralleli)
"""
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.gestione import valuta                            # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE                         # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INTERI = {"barre_stop", "ora_inizio", "ora_fine", "ora_chiusura",
          "max_operazioni_giorno", "attesa_minuti", "media_macro",
          "frattale_k"}


def misura(m1, t):
    # genera applica struttura, macro e finestre; le conferme le registra
    # soltanto (per gli studi), quindi la regola ufficiale si chiude qui
    ops = [op for op in genera(m1, t)
           if all(op[f"c_{tf}"] for tf in t.conferme)
           and all(not op[f"c_{tf}"] for tf in t.ritracciamento)]
    r = np.array([valuta(op, t.obiettivo, be=t.pareggio)[0] for op in ops])
    anni = np.array([op["anno"] for op in ops])
    eq = pk = 1.0
    dd = 0.0
    for x in r:
        eq *= 1 + t.rischio_per_operazione * x
        pk = max(pk, eq)
        dd = max(dd, (pk - eq) / pk)
    positivi = sum(1 for y in np.unique(anni) if r[anni == y].sum() > 0)
    return {"n": len(r), "r_tot": float(r.sum()), "r_op": float(r.mean()),
            "anni_pos": int(positivi), "anni": int(len(np.unique(anni))),
            "dd_pct": float(dd * 100), "conto": float(10000 * eq)}


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    righe = []
    for spec in sys.argv[1:]:
        if spec == "base":
            campo, valore, t = "base", "", UFFICIALE
        else:
            campo, valore = spec.split("=")
            v = int(valore) if campo in INTERI else float(valore)
            t = replace(UFFICIALE, **{campo: v})
        m = misura(m1, t)
        m["campo"], m["valore"] = campo, valore
        righe.append(m)
        print(f"{campo}={valore or '-':6s} n={m['n']:4d} r_tot={m['r_tot']:+7.1f} "
              f"r_op={m['r_op']:+6.3f} anni+={m['anni_pos']}/{m['anni']} "
              f"dd={m['dd_pct']:4.1f}% conto={m['conto']:8,.0f}".replace(",", "."),
              flush=True)
    dest = os.path.join(ROOT, "docs", "studies", "dati", "sensibilita.parquet")
    df = pd.DataFrame(righe)
    if os.path.exists(dest):
        df = pd.concat([pd.read_parquet(dest), df], ignore_index=True)
    df.to_parquet(dest, index=False)


if __name__ == "__main__":
    main()
