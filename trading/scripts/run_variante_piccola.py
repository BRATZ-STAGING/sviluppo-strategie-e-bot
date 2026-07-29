#!/usr/bin/env python3
"""Variante sui timeframe piccoli: piu' operazioni, stop piu' stretti, 1:3-1:5.

Ipotesi pre-registrata PRIMA di guardare i numeri: la stessa regola d'ingresso
(reclaim del VWAP giornaliero) applicata un gradino piu' in basso nella scala
dei timeframe produce piu' operazioni con rischio in dollari piu' piccolo, e
con obiettivi corti (1:3-1:5) resta profittevole.

                    ufficiale        piccola
  struttura         H6 + H2          M66 + M33
  ingresso          M6               M3
  impulso minimo    4,00 $           2,00 $
  rischio           1-10 $           0,50-4,00 $
  operazioni/giorno 3                8
  attesa fra i segnali  30'          10'
  obiettivo         1:10             1:3, 1:4, 1:5

Il rischio piu' piccolo ha un prezzo che va misurato per primo: lo spread e'
fisso in dollari, quindi in multipli del rischio COSTA DI PIU'. Con 4 $ di
rischio lo spread pesa 0,075R, con 1,5 $ ne pesa 0,20 - un quinto del rischio
per ogni operazione. E' il numero che decide se la variante ha senso.

La scelta delle conferme e' fatta sul 2020-2023 e verificata sul 2024-2026,
mai usato per sceglierle.

Uso: python3 run_variante_piccola.py <out.parquet>
"""
import dataclasses
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                              # noqa: E402
from framework.gestione import valuta                           # noqa: E402
from framework.segnali import genera                            # noqa: E402
from framework.taratura import UFFICIALE                        # noqa: E402

pd.set_option("display.width", 220)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

PICCOLA = dataclasses.replace(
    UFFICIALE,
    tf_ingresso="M3",
    tf_struttura=("M66", "M33"),
    conferme=(),                 # da scegliere: qui si misurano tutte
    ritracciamento=(),
    impulso_min=2.00,
    rischio_min=0.50,
    rischio_max=4.00,
    max_operazioni_giorno=8,
    attesa_minuti=10,
    obiettivo=5.0,
    pareggio=2.0,
)

TFS = ["M3", "M6", "M12", "M33", "M66", "H2", "H3", "H6", "H12"]
RR = [3.0, 4.0, 5.0]
BE = [None, 1.0, 1.5, 2.0, 3.0]
IS, OOS = (2020, 2023), (2024, 2026)


def tabella(df, cols, indice):
    t = pd.DataFrame(cols, index=indice)
    return t.to_string(float_format=lambda x: f"{x:+.3f}")


def riassunto(sub, rr, be=None):
    r = sub[f"r{rr:g}" if be is None else f"r{rr:g}_be{be:g}"].values
    mo = sub[f"m{rr:g}" if be is None else f"m{rr:g}_be{be:g}"].values
    per = pd.Series(r).groupby(sub.anno.values).sum()
    eq = np.cumsum(r)
    return {"n": len(r), "R/op": r.mean(), "R tot": r.sum(),
            "DD": float((np.maximum.accumulate(eq) - eq).max()),
            "%stop": (mo == 0).mean() * 100,
            "anni+": int((per > 0).sum()), "peggiore": per.min()}


def main():
    out_path = sys.argv[1]
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))

    righe = []
    for nome, tar in (("piccola", PICCOLA), ("ufficiale", UFFICIALE)):
        ops = genera(m1, tar, tf_extra=TFS)
        for o in ops:
            rec = {k: v for k, v in o.items() if k not in ("fav", "sfav")}
            rec["variante"] = nome
            for rr in RR + [10.0]:
                rec[f"r{rr:g}"], rec[f"m{rr:g}"] = valuta(o, rr)
                for be in BE[1:]:
                    if be >= rr:
                        continue
                    rec[f"r{rr:g}_be{be:g}"], rec[f"m{rr:g}_be{be:g}"] = \
                        valuta(o, rr, be=be)
            righe.append(rec)
        print(f"{nome}: {len(ops)} operazioni", flush=True)
    df = pd.DataFrame(righe)
    df.to_parquet(out_path)

    print("\n=== 1. QUANTO COSTA LO SPREAD, NELLE DUE VARIANTI ===")
    g = df.groupby("variante").agg(
        operazioni=("rischio", "size"),
        rischio_mediano=("rischio", "median"),
        costo_medio_R=("costo", "mean"),
        costo_mediano_R=("costo", "median"))
    g["op/anno"] = (g.operazioni / 6.5).round(0)
    print(g.to_string(float_format=lambda x: f"{x:.3f}"))
    print("\nlo spread e' 0,30 $ fisso: piu' stretto e' lo stop, piu' pesa in R")

    p = df[df.variante == "piccola"]
    print("\n=== 2. VARIANTE PICCOLA, senza conferme: obiettivi 1:3-1:5 ===")
    print(pd.DataFrame([riassunto(p, rr) for rr in RR],
                       index=[f"1:{rr:g}" for rr in RR]).to_string(
        float_format=lambda x: f"{x:+.2f}"))

    print("\n=== 3. R per anno (variante piccola, senza conferme) ===")
    t = pd.concat([p.groupby("anno")[f"r{rr:g}"].sum().rename(f"1:{rr:g}")
                   for rr in RR], axis=1)
    t.loc["TOT"] = t.sum()
    print(t.to_string(float_format=lambda x: f"{x:+.1f}"))

    print("\n=== 4. POTERE DI OGNI CONFERMA, scelto solo sul 2020-2023 ===")
    cal = p[(p.anno >= IS[0]) & (p.anno <= IS[1])]
    righe = []
    for tf in TFS:
        if tf in PICCOLA.tf_struttura:
            continue
        a = cal[cal[f"c_{tf}"] == 1].r5
        b = cal[cal[f"c_{tf}"] == 0].r5
        if len(a) < 30 or len(b) < 30:
            continue
        righe.append({"TF": tf, "n allineato": len(a), "R/op allineato": a.mean(),
                      "R/op contrario": b.mean(), "delta": a.mean() - b.mean()})
    disc = pd.DataFrame(righe).sort_values("delta", ascending=False)
    print(disc.to_string(index=False, float_format=lambda x: f"{x:+.3f}"))

    scelte = list(disc.head(2).TF)
    print(f"\nconferme scelte sul solo 2020-2023: {scelte}")

    print("\n=== 5. VERIFICA FUORI CAMPIONE (2024-2026, mai usato) ===")
    m = np.ones(len(p), bool)
    for tf in scelte:
        m &= (p[f"c_{tf}"] == 1).values
    filtrato = p[m]
    righe = []
    for nome, sub in (("senza conferme", p), (" + ".join(scelte), filtrato)):
        for periodo, (lo, hi) in (("2020-2023", IS), ("2024-2026", OOS)):
            s = sub[(sub.anno >= lo) & (sub.anno <= hi)]
            if not len(s):
                continue
            righe.append({"filtro": nome, "periodo": periodo, **riassunto(s, 5.0)})
    print(pd.DataFrame(righe).to_string(index=False,
                                        float_format=lambda x: f"{x:+.2f}"))

    print("\n=== 6. CON LO STOP A PAREGGIO (obiettivo 1:5, conferme scelte) ===")
    righe = [{"pareggio": "nessuno", **riassunto(filtrato, 5.0)}]
    for be in BE[1:]:
        righe.append({"pareggio": f"+{be:g}R", **riassunto(filtrato, 5.0, be)})
    print(pd.DataFrame(righe).to_string(index=False,
                                        float_format=lambda x: f"{x:+.2f}"))

    print("\n=== 7. CONFRONTO FINALE con la taratura ufficiale ===")
    u = df[df.variante == "ufficiale"]
    mu = ((u.c_M33 == 1) & (u.c_H12 == 1) & (u.c_M12 == 0)).values
    conf = [{"sistema": "ufficiale (M6, 1:10, pareggio +3R)",
             **riassunto(u[mu], 10.0, 3.0)},
            {"sistema": f"piccola (M3, 1:5, {' + '.join(scelte)})",
             **riassunto(filtrato, 5.0)},
            {"sistema": f"piccola (M3, 1:3, {' + '.join(scelte)})",
             **riassunto(filtrato, 3.0)}]
    print(pd.DataFrame(conf).to_string(index=False,
                                       float_format=lambda x: f"{x:+.2f}"))
    print(f"\ndettaglio in {out_path}")


if __name__ == "__main__":
    main()
