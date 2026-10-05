#!/usr/bin/env python3
"""Distanza dal VWAP all'ingresso sul 2009-2019 (docs/vwap-distanza-18anni-registrazione.md).

Stessa misura e stesse operazioni della famiglia 3 di ``run_selezione_fine.py``
(appendice BP): ``genera`` (campione largo), gestione ufficiale 1:10 con
pareggio a +3R, chiusura all'ultima candela prima delle 21:00 UTC, misura
|entry - VWAP giornaliero| / respiro M1 dei 30 minuti precedenti. I terzi NON
si ricalcolano: confini congelati dal 2020-2026 (0,6895 e 1,5879 respiri).

Uso:
  XAU_ANNI=2020-2026 python run_vwap_distanza_18anni.py   controllo: riproduce BP
  python run_vwap_distanza_18anni.py                      verifica 2009-2019
Scrive docs/studies/dati/vwap_distanza_<anni>.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(QUI, ".."))
sys.path.insert(0, QUI)

from framework.data import load_m1                               # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402
from framework.vwap import anchored_vwap                         # noqa: E402
from run_scalp_scaglioni import cammina_uno                      # noqa: E402

ROOT = os.path.abspath(os.path.join(QUI, "..", ".."))
RESPIRO = 30
CONFINI = (0.6895, 1.5879)      # congelati: docs/vwap-distanza-18anni-registrazione.md
SEME = 20261005
N_PLACEBO = 2000
VECCHI = (2009, 2019)


def operazioni(m1: pd.DataFrame) -> pd.DataFrame:
    respiro = (m1.high - m1.low).rolling(RESPIRO).mean().shift(1).values
    vw = anchored_vwap(m1, "day").reindex(m1.index).values
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values
    ufficiali = set(T.conferme), set(T.ritracciamento)
    righe = []
    for o in genera(m1, T):
        t_in = pd.Timestamp(o["time"]).tz_convert("UTC")
        segno = 1 if o["lato"] == "long" else -1
        e, k = o["entry"], float(o["rischio"])
        a = int(np.searchsorted(idx, t_in.value))
        b = int(np.searchsorted(idx, (t_in.normalize() + pd.Timedelta(hours=T.ora_chiusura)).value))
        if b - a < 2 or a >= len(respiro):
            continue
        r_now = respiro[a]
        if not np.isfinite(r_now) or r_now <= 0:
            continue
        o_, h_, l_, c_ = ap_[a:b], hi[a:b], lo[a:b], cl[a:b]
        if segno == 1:
            apri, fav, sfav, chiu = (o_ - e) / k, (h_ - e) / k, (e - l_) / k, (c_ - e) / k
        else:
            apri, fav, sfav, chiu = (e - o_) / k, (e - l_) / k, (h_ - e) / k, (e - c_) / k
        r, _ = cammina_uno(apri, fav, sfav, chiu, 10.0, 3.0)
        uff = (all(o[f"c_{tf}"] for tf in ufficiali[0])
               and all(not o[f"c_{tf}"] for tf in ufficiali[1]))
        righe.append({"time": t_in, "anno": o["anno"], "lato": o["lato"],
                      "netto": r - o["costo"], "netto_040": r - 0.40 / k,
                      "ufficiale": uff,
                      "distanza": abs(e - vw[a]) / r_now if np.isfinite(vw[a]) else np.nan})
    t = pd.DataFrame(righe).dropna(subset=["distanza"])
    t["fascia"] = pd.cut(t["distanza"], [-np.inf, CONFINI[0], CONFINI[1], np.inf],
                         right=False, labels=["basso", "medio", "alto"])
    return t


def differenze(netto: np.ndarray, fascia: np.ndarray) -> tuple[float, float]:
    """H1: medio - resto; H2: resto - basso (R/op)."""
    m = fascia == "medio"
    b = fascia == "basso"
    return netto[m].mean() - netto[~m].mean(), netto[~b].mean() - netto[b].mean()


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    anni = f"{m1.index[0].year}-{m1.index[-1].year}"
    t = operazioni(m1)
    del m1
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati", f"vwap_distanza_{anni}.parquet"), index=False)
    pd.set_option("display.width", 200)
    print(f"operazioni con misura: {len(t)} ({anni})")

    def tabella(x, col="netto"):
        return x.groupby("fascia", observed=True)[col].agg(op="size", Rop="mean").round(3)

    if t.anno.min() >= 2020:
        print("\n== controllo: deve riprodurre BP (medio +0,377 ricerca, +0,382 verifica)")
        for nome, (a, z) in (("ricerca 2020-2022", (2020, 2022)), ("verifica 2023-2026", (2023, 2026))):
            print(nome, tabella(t[t.anno.between(a, z)]).to_dict("index"))
        return

    v = t[t.anno.between(*VECCHI)].reset_index(drop=True)
    print(f"\n== 2009-2019 (mai toccato da questa misura): {len(v)} operazioni")
    print(tabella(v).to_string())
    d1, d2 = differenze(v.netto.values, v.fascia.astype(str).values)
    rng = np.random.default_rng(SEME)
    f = v.fascia.astype(str).values
    pl = np.array([differenze(v.netto.values, rng.permutation(f)) for _ in range(N_PLACEBO)])
    p1, p2 = (pl[:, 0] >= d1).mean(), (pl[:, 1] >= d2).mean()
    anni1 = anni2 = 0
    per_anno = []
    for a, x in v.groupby("anno"):
        e1, e2 = differenze(x.netto.values, x.fascia.astype(str).values)
        anni1 += e1 > 0
        anni2 += e2 > 0
        per_anno.append(f"{a}:{e1:+.2f}/{e2:+.2f}")
    n_anni = v.anno.nunique()
    for nome, d, p, k in (("H1 medio - resto", d1, p1, anni1), ("H2 resto - basso", d2, p2, anni2)):
        regge = d > 0 and p < 0.025 and k >= 7
        print(f"{nome}: {d:+.3f} R/op, placebo p {p:.3f}, anni con segno atteso {k}/{n_anni} -> "
              f"{'REGGE' if regge else 'NON REGGE'}")
    print("per anno (H1/H2): " + " ".join(per_anno))
    medio = v[v.fascia == "medio"].netto.mean()
    non_basso = v[v.fascia != "basso"].netto.mean()
    print(f"netto 2009-2019: terzo medio {medio:+.3f} R/op, medio+alto {non_basso:+.3f} R/op "
          f"(utilizzabile solo se > 0)")

    print("\n== descrittivo, fuori dal verdetto")
    print("2009-2019 spread 0,40:", tabella(v, "netto_040").to_dict("index"))
    print("2009-2019 campione ufficiale:", tabella(v[v.ufficiale]).to_dict("index"))
    print("2009-2026 intero:", tabella(t).to_dict("index"))
    print("2020-2026 su archivio intero:", tabella(t[t.anno >= 2020]).to_dict("index"))


if __name__ == "__main__":
    main()
