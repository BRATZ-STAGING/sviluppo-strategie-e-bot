#!/usr/bin/env python3
"""Diagnostica completa: tutte le combinazioni e la scomposizione del risultato.

Produce (a) la matrice di tutte le combinazioni direzione x filtro macro x
obiettivo con le metriche complete, e (b) per la configurazione richiesta la
scomposizione del risultato per anno, lato, motivo di uscita, sessione,
ampiezza dello stop e regime di volatilita': serve a capire DOVE il sistema
guadagna e dove perde.

Uso: python3 run_diagnostica.py [out.parquet]
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1, resample_tf, session_of      # noqa: E402
from framework.structure import state_at, trend_state_series     # noqa: E402
from framework.volatility import (atr_at, daily_atr,             # noqa: E402
                                  high_volatility_months)
from framework.vwap import anchored_vwap                         # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPREAD, BUF = 0.30, 0.3
MIN_RISK, MAX_RISK, MIN_IMPULSE = 1.0, 10.0, 4.0
CALIB, RR_GRID = (2020, 2024), [2.0, 3.0, 5.0, 8.0, 10.0]
MAX_GIORNO, COOLDOWN, SMA = 3, 30, 50


def costruisci():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    m6 = resample_tf(m1, "M6")
    m6["vwap"] = anchored_vwap(m6, "day")
    cl_t = m6.index + pd.Timedelta("6min")
    m6["h6"] = state_at(trend_state_series(resample_tf(m1, "H6"), 3, "6h"), cl_t)
    m6["h2"] = state_at(trend_state_series(resample_tf(m1, "H2"), 3, "2h"), cl_t)
    atr = daily_atr(m1, 14)
    m6["atr"] = atr_at(atr, m6.index).values
    d1 = m1.close.resample("1D").last().dropna()
    macro = (d1 > d1.rolling(SMA).mean()).shift(1)
    macro.index = macro.index.normalize()
    return m1, m6, atr, macro.to_dict()


def operazioni(m1, m6, atr, macro):
    mask = (atr.index.year >= CALIB[0]) & (atr.index.year <= CALIB[1])
    med = float(atr[mask].median())
    k = {"imp": MIN_IMPULSE / med, "buf": BUF / med,
         "rmin": MIN_RISK / med, "rmax": MAX_RISK / med}
    alto = high_volatility_months(
        atr, sorted({pd.Period(x.strftime("%Y-%m"), "M") for x in m6.index}), 1.5)

    idx = m6.index
    hours, days = idx.hour, idx.normalize()
    hi, lo, cl = m6.high.values, m6.low.values, m6.close.values
    vd, h6, h2, av = m6.vwap.values, m6.h6.values, m6.h2.values, m6.atr.values
    m1_idx = m1.index
    m1h, m1l, m1c = m1.high.values, m1.low.values, m1.close.values
    mese = pd.PeriodIndex(idx, freq="M")

    out, last, count, dstart = [], None, {}, 0
    for i in range(1, len(m6)):
        d = days[i]
        if d != days[i - 1]:
            dstart = i
        if not (7 <= hours[i] < 19) or np.isnan(vd[i]) or count.get(d, 0) >= MAX_GIORNO:
            continue
        t = idx[i] + pd.Timedelta("6min")
        if last is not None and (t - last) < pd.Timedelta(minutes=COOLDOWN):
            continue
        regime = "ATR" if alto.get(mese[i], False) else "dollari"
        if regime == "ATR":
            u = av[i]
            if np.isnan(u) or u <= 0:
                continue
            imp_min, buf, rmin, rmax = k["imp"]*u, k["buf"]*u, k["rmin"]*u, k["rmax"]*u
        else:
            imp_min, buf, rmin, rmax = MIN_IMPULSE, BUF, MIN_RISK, MAX_RISK

        lato = None
        if h6[i] == 1 and h2[i] == 1 and lo[i] <= vd[i] and cl[i] > vd[i] and cl[i] > hi[i-1]:
            if (float(hi[dstart:i].max()-vd[i]) if i > dstart else 0) >= imp_min:
                lato = "long"
        if lato is None and h6[i] == -1 and h2[i] == -1 and hi[i] >= vd[i] \
                and cl[i] < vd[i] and cl[i] < lo[i-1]:
            if (float(vd[i]-lo[dstart:i].min()) if i > dstart else 0) >= imp_min:
                lato = "short"
        if lato is None:
            continue
        entry = float(cl[i]); j0 = max(dstart, i-5)
        stop = float(lo[j0:i+1].min()-buf) if lato == "long" else float(hi[j0:i+1].max()+buf)
        risk = entry - stop if lato == "long" else stop - entry
        if not (rmin <= risk <= rmax):
            continue
        a = int(m1_idx.searchsorted(t)); b = int(m1_idx.searchsorted(d+pd.Timedelta(hours=21)))
        if b - a < 2:
            continue
        last = t; count[d] = count.get(d, 0)+1
        h_, l_, c_ = m1h[a:b], m1l[a:b], m1c[a:b]
        slh = (l_ <= stop) if lato == "long" else (h_ >= stop)
        i_sl = int(np.argmax(slh)) if slh.any() else None
        fine = float(c_[-1])
        r_eod = ((fine-entry) if lato == "long" else (entry-fine))/risk
        rec = {"time": t, "anno": int(idx[i].year), "lato": lato,
               "macro_ok": (macro.get(d, False) == (lato == "long")),
               "sessione": session_of(t), "regime": regime, "risk": risk,
               "ora": int(t.hour), "costo": SPREAD/risk}
        for rr in RR_GRID:
            tgt = entry+rr*risk if lato == "long" else entry-rr*risk
            hit = (h_ >= tgt) if lato == "long" else (l_ <= tgt)
            i_tp = int(np.argmax(hit)) if hit.any() else None
            if i_sl is not None and (i_tp is None or i_sl <= i_tp):
                rec[f"r{rr:g}"], rec[f"m{rr:g}"] = -1.0-rec["costo"], "stop"
            elif i_tp is not None:
                rec[f"r{rr:g}"], rec[f"m{rr:g}"] = rr-rec["costo"], "obiettivo"
            else:
                rec[f"r{rr:g}"], rec[f"m{rr:g}"] = r_eod-rec["costo"], "fine giornata"
        out.append(rec)
    return pd.DataFrame(out)


def metriche(s):
    if not len(s):
        return dict(n=0)
    eq = s.cumsum(); dd = float((eq.cummax()-eq).max())
    return dict(n=len(s), win=float((s > 0).mean()), expR=float(s.mean()),
                totR=float(s.sum()), maxDD=dd)


def main():
    m1, m6, atr, macro = costruisci()
    df = operazioni(m1, m6, atr, macro)
    print(f"operazioni totali: {len(df)}\n")

    print("=== MATRICE COMPLETA (n · win% · R/op · R tot · maxDD · anni+) ===")
    righe = []
    for dire, fsel in [("long+short", lambda d: d), ("solo long", lambda d: d[d.lato == "long"]),
                       ("solo short", lambda d: d[d.lato == "short"])]:
        for mac in [True, False]:
            sub = fsel(df)
            if mac:
                sub = sub[sub.macro_ok]
            for rr in RR_GRID:
                col = f"r{rr:g}"
                m = metriche(sub[col])
                if not m["n"]:
                    continue
                anni = sub.groupby("anno")[col].sum()
                righe.append({"direzione": dire, "macro": "on" if mac else "off",
                              "RR": f"1:{rr:g}", **m,
                              "anni+": f"{int((anni > 0).sum())}/{len(anni)}"})
    mat = pd.DataFrame(righe)
    piv = mat.pivot_table(index=["direzione", "macro"], columns="RR",
                          values="totR", aggfunc="first")
    print("\nR TOTALE per combinazione:")
    print(piv.to_string(float_format=lambda x: f"{x:+.1f}"))
    print("\nWIN RATE (%):")
    pw = mat.pivot_table(index=["direzione", "macro"], columns="RR",
                         values="win", aggfunc="first")*100
    print(pw.to_string(float_format=lambda x: f"{x:.1f}"))
    print("\nANNI POSITIVI:")
    pa = mat.pivot_table(index=["direzione", "macro"], columns="RR",
                         values="anni+", aggfunc="first")
    print(pa.to_string())

    best = mat.loc[mat.totR.idxmax()]
    print(f"\n=== MIGLIORE: {best.direzione} · macro {best.macro} · {best.RR} ===")
    print(f"n={best.n} · win {best.win:.1%} · R/op {best.expR:+.3f} · "
          f"tot {best.totR:+.1f}R · maxDD {best.maxDD:.1f}R · anni+ {best['anni+']}")

    sub = df[df.macro_ok]
    col = "r10"
    print("\n=== DOVE NASCONO E MUOIONO I SOLDI (configurazione migliore) ===")
    for dim, nome in [("anno", "per anno"), ("lato", "per direzione"),
                      (f"m10", "per motivo di uscita"), ("sessione", "per sessione"),
                      ("regime", "per regime di volatilità"), ("ora", "per ora d'ingresso")]:
        g = sub.groupby(dim)[col].agg(n="size", tot="sum", medio="mean")
        g["win%"] = sub.groupby(dim)[col].apply(lambda s: (s > 0).mean()*100)
        print(f"\n-- {nome} --")
        print(g.to_string(float_format=lambda x: f"{x:+.2f}"))
    q = sub.risk.quantile([0, .25, .5, .75, 1.0]).values
    sub = sub.assign(fascia=pd.cut(sub.risk, np.unique(q), include_lowest=True))
    g = sub.groupby("fascia", observed=True)[col].agg(n="size", tot="sum", medio="mean")
    print("\n-- per ampiezza dello stop --")
    print(g.to_string(float_format=lambda x: f"{x:+.2f}"))

    if len(sys.argv) > 1:
        df.to_parquet(sys.argv[1])
        print(f"\ndettaglio salvato in {sys.argv[1]}")


if __name__ == "__main__":
    main()
