#!/usr/bin/env python3
"""Appendice BD: il filtro di fondo conta le domeniche come giornate piene.

Difetto noto del progetto e confermato dalla verifica avversariale:
``segnali.filtro_macro`` fa ``m1.close.resample("1D").last()`` senza soglia di
barre minime, mentre ``volatility.daily_bars`` — usata dall'ATR — scarta le
sessioni sotto le 300 candele proprio perche' non sono giornate.

Misurato: il **17%** delle giornate D1 grezze sono spezzoni, e 104 su 108 sono
domeniche sera (circa due ore di scambi alla riapertura). Conseguenze sulla
media a 50 giorni del filtro di fondo:

- la media copre in realta' ~42 giornate vere invece di 50;
- la chiusura dello spezzone domenicale e' praticamente quella del venerdi',
  quindi entra nella media un valore quasi duplicato una volta a settimana.

Qui si misura quanto cambia: quante giornate il filtro classifica
diversamente, e cosa succede alle operazioni sui diciotto anni.

Uso: python3 run_macro_domenica.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework import segnali                                     # noqa: E402
from framework.data import load_m1                                # noqa: E402
from framework.taratura import UFFICIALE as T                     # noqa: E402
from framework.volatility import daily_bars                       # noqa: E402

from run_scale_trailing import esito                              # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PERIODI = [("2009-2019", 2009, 2019), ("2020-2026", 2020, 2026),
           ("2009-2026", 2009, 2026)]
PARI3 = ([(3, 0)], None)              # la gestione in vigore


def macro_pulito(m1, n):
    """Come filtro_macro, ma sulle sole giornate VERE."""
    d1 = daily_bars(m1).close
    sopra = (d1 > d1.rolling(n).mean()).shift(1)
    sopra.index = sopra.index.normalize()
    return sopra.to_dict()


def sintesi(r, anni):
    if not len(r):
        return {"op": 0, "R": 0.0, "r_op": 0.0, "anni_pos": 0, "anni": 0}
    pa = np.array([r[anni == y].sum() for y in np.unique(anni)])
    cum = np.cumsum(r)
    return {"op": len(r), "R": r.sum(), "r_op": r.mean(),
            "DD": (np.maximum.accumulate(cum) - cum).max(),
            "anni_pos": int((pa > 0).sum()), "anni": len(pa)}


def ufficiali(ops):
    return [o for o in ops
            if all(o[f"c_{tf}"] for tf in T.conferme)
            and all(not o[f"c_{tf}"] for tf in T.ritracciamento)]


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))

    a = segnali.filtro_macro(m1, T.media_macro)
    b = macro_pulito(m1, T.media_macro)
    comuni = [g for g in a if g in b and a[g] is not None and b[g] is not None
              and not pd.isna(a[g]) and not pd.isna(b[g])]
    diversi = [g for g in comuni if bool(a[g]) != bool(b[g])]
    print(f"giornate confrontabili: {len(comuni)}, classificate DIVERSAMENTE: "
          f"{len(diversi)} ({len(diversi) / max(len(comuni), 1) * 100:.1f}%)",
          flush=True)

    righe = []
    for eti, funzione in (("com'e' adesso", segnali.filtro_macro),
                          ("senza domeniche", macro_pulito)):
        originale = segnali.filtro_macro
        segnali.filtro_macro = funzione
        try:
            ops = ufficiali(segnali.genera(m1, T))
        finally:
            segnali.filtro_macro = originale
        anni = np.array([o["anno"] for o in ops])
        r = np.array([esito(o["fav"], o["sfav"], o["r_eod"], 10.0, *PARI3)[0]
                      - o["costo"] for o in ops])
        print(f"{eti}: {len(ops)} operazioni", flush=True)
        for nome, da, a_ in PERIODI:
            sel = (anni >= da) & (anni <= a_)
            if sel.any():
                righe.append({"filtro": eti, "periodo": nome,
                              **sintesi(r[sel], anni[sel])})
    d = pd.DataFrame(righe)
    d.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "macro_domenica.parquet"), index=False)
    pd.set_option("display.width", 200)
    print()
    print(d.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
