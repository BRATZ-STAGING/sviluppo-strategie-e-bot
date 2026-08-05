#!/usr/bin/env python3
"""Appendice AM: stabilita' delle gestioni, misurata a LOTTI FISSI.

Il conto in euro con rischio percentuale confonde due cose: quanto rende la
strategia e quanto la composizione amplifica i periodi buoni. A lotti fissi
(stessa cifra rischiata a ogni operazione, sempre) ogni operazione pesa
uguale e resta solo il vantaggio: la somma delle R diventa una linea, e la
sua regolarita' si puo' misurare.

Per ogni combinazione di gestione x obiettivo calcola: risultato, quota di
operazioni in perdita, perdite di fila, perdita massima IN R, tempo passato
sotto il massimo precedente, quota di mesi e anni positivi, regolarita' dei
risultati annuali, e il rapporto fra risultato e perdita massima.

Uso: python3 run_stabilita.py
Scrive docs/studies/dati/stabilita.parquet
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

from run_scale_trailing import GESTIONI, OBIETTIVI, esito        # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CAPITALE = 10_000.0
RISCHIO = 100.0            # euro fissi per operazione, mai ricalcolati


def misure(r, mesi, anni):
    """Tutte le misure di stabilita' di una serie di risultati in R."""
    cum = np.cumsum(r)
    picco = np.maximum.accumulate(cum)
    sotto = picco - cum
    # tempo passato sotto il massimo precedente, in operazioni
    lung = corr = 0
    for x in sotto:
        corr = corr + 1 if x > 1e-9 else 0
        lung = max(lung, corr)
    # perdite di fila
    serie = pmax = 0
    for x in r:
        serie = serie + 1 if x < 0 else 0
        pmax = max(pmax, serie)
    per_anno = np.array([r[anni == a].sum() for a in np.unique(anni)])
    per_mese = np.array([r[mesi == m].sum() for m in np.unique(mesi)])
    gl = -r[r < 0].sum()
    return {
        "r_tot": r.sum(), "r_op": r.mean(),
        "perse_pct": (r < 0).mean() * 100,
        "perdite_fila": pmax,
        "dd_r": sotto.max(),
        "sotto_max_op": lung,
        "recupero": r.sum() / max(sotto.max(), 1e-9),
        "mesi_pos_pct": (per_mese > 0).mean() * 100,
        "anni_pos": int((per_anno > 0).sum()),
        "anno_peggiore": per_anno.min(),
        "regolarita": per_anno.mean() / max(per_anno.std(), 1e-9),
        "profit_factor": r[r > 0].sum() / max(gl, 1e-9),
        "conto_lotti_fissi": CAPITALE + RISCHIO * r.sum(),
    }


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [op for op in genera(m1, T)
           if all(op[f"c_{tf}"] for tf in T.conferme)
           and all(not op[f"c_{tf}"] for tf in T.ritracciamento)]
    anni = np.array([op["anno"] for op in ops])
    mesi = np.array([pd.Timestamp(op["time"]).strftime("%Y-%m") for op in ops])
    print(f"operazioni: {len(ops)}  ({CAPITALE:,.0f} EUR, {RISCHIO:,.0f} EUR fissi "
          f"per operazione)".replace(",", "."), flush=True)

    righe = []
    for nome, scala, trail in GESTIONI:
        for rr in OBIETTIVI:
            r = np.array([esito(op["fav"], op["sfav"], op["r_eod"], rr,
                                scala, trail)[0] - op["costo"] for op in ops])
            righe.append({"gestione": nome, "rr": rr, **misure(r, mesi, anni)})
    df = pd.DataFrame(righe)
    df.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                               "stabilita.parquet"), index=False)

    pd.set_option("display.width", 240)
    col = ["gestione", "rr", "r_tot", "conto_lotti_fissi", "perse_pct",
           "perdite_fila", "dd_r", "sotto_max_op", "recupero", "mesi_pos_pct",
           "anni_pos", "anno_peggiore", "profit_factor"]
    print("\n=== migliori per RECUPERO (risultato diviso perdita massima)")
    print(df.nlargest(8, "recupero")[col].round(2).to_string(index=False))
    print("\n=== migliori per MENO OPERAZIONI IN PERDITA")
    print(df.nsmallest(8, "perse_pct")[col].round(2).to_string(index=False))
    print("\n=== migliori per REGOLARITA' fra gli anni")
    print(df.nlargest(8, "regolarita")[col].round(2).to_string(index=False))
    print("\n=== migliori per MENO TEMPO SOTTO IL MASSIMO")
    print(df.nsmallest(8, "sotto_max_op")[col].round(2).to_string(index=False))
    b = df[(df.gestione == "pari a +3R (in uso)") & (df.rr == 10)].iloc[0]
    print("\n=== configurazione in uso")
    print(b[col].to_frame().T.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
