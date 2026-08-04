#!/usr/bin/env python3
"""Appendice BA: la zona OB raffinata come FILTRO, sui diciotto anni.

L'appendice AZ dice che i livelli non funzionano come ingresso. Ma il
risultato positivo del progetto (appendici P e AJ) non era quello: era la
zona raffinata usata come **voto di qualita' su un segnale gia' valido**,
+1,342 R/op sul campione largo, sette anni su sette. Misurato pero' solo sul
2020-2026, cioe' il periodo che l'appendice AY ha mostrato incapace di
distinguere una regola buona da una fortunata.

Qui si rifa' quella misura sui diciotto anni: per ogni segnale della
strategia si guarda se l'ingresso cade dentro una zona OB attiva e concorde,
piena o raffinata, su ciascun timeframe, e si confronta il risultato dentro
contro fuori nei due periodi separati.

Uso: python3 run_ob_18anni.py
Scrive docs/studies/dati/ob_18anni.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf       # noqa: E402
from framework.segnali import genera                              # noqa: E402
from framework.taratura import UFFICIALE as T                     # noqa: E402

from export_lab import zone_ob                                    # noqa: E402
from run_scale_trailing import esito                              # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TF_ZONE = ["M12", "M33", "M66", "H2", "H3", "H6"]
VALIDITA = 30
PERIODI = [("2009-2019", 2009, 2019), ("2020-2026", 2020, 2026),
           ("2009-2026", 2009, 2026)]


def dentro(zone, quando, prezzo, lato, raffinata):
    """La colonna dentro/fuori per una lista di segnali, su un timeframe."""
    if zone.empty:
        return np.zeros(len(quando), bool)
    da = zone.attiva_da.values.astype("datetime64[ns]")
    a = zone.scade_il.values.astype("datetime64[ns]")
    b = zone.rbasso.values if raffinata else zone.basso.values
    t = zone.ralto.values if raffinata else zone.alto.values
    lz = zone.lato.values
    fuori = np.zeros(len(quando), bool)
    for i in range(len(quando)):
        viva = (da <= quando[i]) & (a > quando[i]) & (lz == lato[i])
        if not viva.any():
            continue
        k = np.flatnonzero(viva)
        fuori[i] = bool(((b[k] <= prezzo[i]) & (prezzo[i] <= t[k])
                         & np.isfinite(b[k]) & np.isfinite(t[k])).any())
    return fuori


def sintesi(r, anni):
    if not len(r):
        return {"op": 0, "R": 0.0, "r_op": 0.0, "anni_pos": 0, "anni": 0}
    pa = np.array([r[anni == y].sum() for y in np.unique(anni)])
    return {"op": len(r), "R": r.sum(), "r_op": r.mean(),
            "anni_pos": int((pa > 0).sum()), "anni": len(pa)}


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    grezzi = genera(m1, T)
    ufficiali = [o for o in grezzi
                 if all(o[f"c_{tf}"] for tf in T.conferme)
                 and all(not o[f"c_{tf}"] for tf in T.ritracciamento)]
    print(f"segnali: {len(grezzi)} grezzi, {len(ufficiali)} con le conferme",
          flush=True)

    scala, trail = [(3, 0)], None            # la gestione in vigore
    tab = {}
    for eti, ops in [("largo", grezzi), ("ufficiale", ufficiali)]:
        quando = pd.DatetimeIndex([o["time"] for o in ops]).as_unit("ns").values
        prezzo = np.array([o["entry"] for o in ops])
        lato = np.array([1 if o["lato"] == "long" else -1 for o in ops])
        t = pd.DataFrame({
            "anno": [o["anno"] for o in ops],
            "r": [esito(o["fav"], o["sfav"], o["r_eod"], 10.0, scala, trail)[0]
                  - o["costo"] for o in ops]})
        for tf in TF_ZONE:
            z = zone_ob(resample_tf(m1, tf), T.frattale_k,
                        pd.Timedelta(TIMEFRAMES[tf]), validita=VALIDITA)
            t[f"{tf}|piena"] = dentro(z, quando, prezzo, lato, False)
            t[f"{tf}|raffinata"] = dentro(z, quando, prezzo, lato, True)
            print(f"  {eti} · {tf}: dentro la piena "
                  f"{int(t[f'{tf}|piena'].sum())}, dentro la raffinata "
                  f"{int(t[f'{tf}|raffinata'].sum())}", flush=True)
        tab[eti] = t

    righe = []
    for eti, t in tab.items():
        for col in [c for c in t.columns if "|" in c]:
            tf, tipo = col.split("|")
            for nome, da, a_ in PERIODI:
                p = t[(t.anno >= da) & (t.anno <= a_)]
                d = sintesi(p.r.values[p[col].values], p.anno.values[p[col].values])
                f = sintesi(p.r.values[~p[col].values], p.anno.values[~p[col].values])
                righe.append({"campione": eti, "tf": tf, "zona": tipo,
                              "periodo": nome,
                              **{f"dentro_{k}": v for k, v in d.items()},
                              **{f"fuori_{k}": v for k, v in f.items()},
                              "delta": d["r_op"] - f["r_op"]})
    g = pd.DataFrame(righe)
    g.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "ob_18anni.parquet"), index=False)

    pd.set_option("display.width", 240)
    col = ["campione", "tf", "zona", "periodo", "dentro_op", "dentro_r_op",
           "dentro_anni_pos", "dentro_anni", "fuori_op", "fuori_r_op", "delta"]
    for eti in tab:
        for tipo in ("raffinata", "piena"):
            q = g[(g.campione == eti) & (g.zona == tipo) & (g.dentro_op >= 15)]
            if q.empty:
                continue
            print(f"\n=== campione {eti}, zona {tipo}")
            print(q[col].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
