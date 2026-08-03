#!/usr/bin/env python3
"""Appendice AV: il crollo sul 2009-2019 e' regime o unita' di misura?

L'appendice AU misura la strategia ufficiale su undici anni mai visti e
trova **-39,3 R**, contro i +157,1 R del 2020-2026. Prima di concludere
qualcosa serve escludere una spiegazione banale.

Le soglie della taratura sono in DOLLARI: impulso 4,00, buffer 0,30, rischio
fra 1,00 e 10,00. Sono numeri scelti su un oro fra 2.000 e 4.000 dollari, con
ATR giornaliero di decine di dollari. Nel 2009-2019 l'oro stava fra 1.050 e
1.900 con un ATR molto piu' piccolo: le stesse soglie in dollari li' dentro
significano tutt'altro in termini di mercato. La conversione all'ATR scatta
solo nei mesi ad alta volatilita' (``fattore_alta_volatilita`` 1,5), quindi
quasi mai in quegli anni.

IPOTESI PRE-REGISTRATA. Se il vantaggio e' una proprieta' della strategia e
non del periodo, misurando TUTTE le soglie in ATR invece che in dollari il
2009-2019 deve tornare positivo. Se resta negativo, il vantaggio appartiene
al 2020-2026 e non alla strategia.

Il trucco per convertire sempre: ``fattore_alta_volatilita = 0`` rende vero
il test di regime per ogni mese, quindi ``soglie()`` riceve sempre l'ATR.
Nessuna modifica al framework. Si prova con entrambi i riferimenti di
mediana, quello ufficiale (2020-2024, che nel 2009 non esisteva) e uno noto
all'epoca (2009-2013).

Uso: python3 run_scala_atr.py
Scrive docs/studies/dati/scala_atr.parquet
"""
import dataclasses
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

from run_scale_trailing import esito                             # noqa: E402
from run_fuori_campione import PARI3, PERIODI, misure, prepara    # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

VARIANTI = [
    ("ufficiale (dollari)", dict()),
    ("sempre ATR, rif. 2020-2024", dict(fattore_alta_volatilita=0.0)),
    ("sempre ATR, rif. 2009-2013", dict(fattore_alta_volatilita=0.0,
                                        calibrazione=(2009, 2013))),
]


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    righe = []
    for eti, campi in VARIANTI:
        tar = dataclasses.replace(T, **campi) if campi else T
        ops = prepara(m1, tar)
        anni = np.array([o["anno"] for o in ops])
        mesi = np.array([pd.Timestamp(o["time"]).strftime("%Y-%m") for o in ops])
        r = np.array([esito(o["fav"], o["sfav"], o["r_eod"], 10.0, *PARI3)[0]
                      - o["costo"] for o in ops])
        for nome, da, a_ in PERIODI:
            sel = (anni >= da) & (anni <= a_)
            if sel.any():
                righe.append({"variante": eti, "periodo": nome,
                              **misure(r[sel], anni[sel], mesi[sel])})
        print(f"{eti}: {len(ops)} operazioni", flush=True)

    df = pd.DataFrame(righe)
    df.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                               "scala_atr.parquet"), index=False)
    pd.set_option("display.width", 240)
    col = ["variante", "periodo", "ops", "r_tot", "r_op", "vinte_pct", "dd_r",
           "anni_pos", "anni", "anno_peggiore", "profit_factor"]
    print()
    print(df[col].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
