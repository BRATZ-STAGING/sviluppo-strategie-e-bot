#!/usr/bin/env python3
"""Lo spread vero contro i 0,30 $ fissi usati in tutti i backtest.

Gli spread mediani mensili vengono dalla conversione dei tick reali
(Dukascopy bid+ask, 222 milioni di tick, novembre 2022 - luglio 2026).
Prima di questo dato ogni misura del progetto assumeva 0,30 $ costanti.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/staging-bratz/trading")
from framework.data import load_m1                  # noqa: E402
from framework.gestione import valuta               # noqa: E402
from framework.segnali import genera                # noqa: E402
from framework.taratura import UFFICIALE as T       # noqa: E402

pd.set_option("display.width", 200)

# spread mediano misurato, dollari, dai Parquet dei tick
SPREAD = {
    "2022-11": 0.425, "2022-12": 0.358, "2023-01": 0.337, "2023-02": 0.340,
    "2023-03": 0.340, "2023-04": 0.340, "2023-05": 0.330, "2023-06": 0.337,
    "2023-07": 0.337, "2023-08": 0.320, "2023-09": 0.310, "2023-10": 0.320,
    "2023-11": 0.327, "2023-12": 0.330, "2024-01": 0.330, "2024-02": 0.327,
    "2024-03": 0.337, "2024-04": 0.370, "2024-05": 0.387, "2024-06": 0.390,
    "2024-07": 0.387, "2024-08": 0.397, "2024-09": 0.397, "2024-10": 0.391,
    "2024-11": 0.397, "2024-12": 0.441, "2025-01": 0.507, "2025-02": 0.530,
    "2025-03": 0.547, "2025-04": 0.646, "2025-05": 0.700, "2025-06": 0.600,
    "2025-07": 0.557, "2025-08": 0.540, "2025-09": 0.577, "2025-10": 0.677,
    "2025-11": 0.620, "2025-12": 0.640, "2026-01": 0.700, "2026-02": 0.887,
    "2026-03": 0.790, "2026-04": 0.710, "2026-05": 0.580, "2026-06": 0.630,
    "2026-07": 0.700,
}

m1 = load_m1("/home/user/staging-bratz/data/XAUUSD_M1")
righe = []
for o in genera(m1, T, tf_extra=("M66",)):
    if not (o["c_M33"] and o["c_H12"] and not o["c_M12"]):
        continue
    mese = o["time"].strftime("%Y-%m")
    vero = SPREAD.get(mese)
    if vero is None:
        continue                                    # periodo senza tick
    r_fisso, mo = valuta(o, T.obiettivo, be=T.pareggio)
    # stesso esito, costo ricalcolato con lo spread vero di quel mese
    o_vero = dict(o, costo=vero / o["rischio"])
    r_vero, _ = valuta(o_vero, T.obiettivo, be=T.pareggio)
    righe.append({"anno": o["anno"], "mese": mese, "rischio": o["rischio"],
                  "spread_vero": vero, "costo_fisso": o["costo"],
                  "costo_vero": vero / o["rischio"],
                  "r_fisso": r_fisso, "r_vero": r_vero, "motivo": mo})
d = pd.DataFrame(righe)

print(f"operazioni nel periodo con i tick (nov 2022 - lug 2026): {len(d)}\n")
print("=== COSTO PER OPERAZIONE: assunto contro reale ===")
g = d.groupby("anno").agg(n=("rischio", "size"), rischio_mediano=("rischio", "median"),
                          spread_vero=("spread_vero", "median"),
                          costo_assunto_R=("costo_fisso", "mean"),
                          costo_vero_R=("costo_vero", "mean"))
g["quanto in piu'"] = (g.costo_vero_R / g.costo_assunto_R - 1) * 100
print(g.to_string(float_format=lambda x: f"{x:.3f}"))

print("\n=== RISULTATO: con 0,30 $ fissi contro spread reale ===")
t = pd.concat([d.groupby("anno").r_fisso.sum().rename("con 0,30 $"),
               d.groupby("anno").r_vero.sum().rename("spread reale")], axis=1)
t["differenza"] = t["spread reale"] - t["con 0,30 $"]
t.loc["TOT"] = t.sum()
print(t.to_string(float_format=lambda x: f"{x:+.1f}"))

print("\n=== SINTESI ===")
for nome, col in (("con 0,30 $ fissi", "r_fisso"), ("con lo spread reale", "r_vero")):
    v = d[col].values
    per = pd.Series(v).groupby(d.anno.values).sum()
    conto = 10000.0
    for x in v:
        conto *= (1 + T.rischio_per_operazione * x)
    print(f"{nome:22s}  R/op {v.mean():+.3f}   R tot {v.sum():+7.1f}   "
          f"anni+ {int((per > 0).sum())}/{len(per)}   conto {conto:,.0f} EUR")
