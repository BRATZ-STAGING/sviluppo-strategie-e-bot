#!/usr/bin/env python3
"""Walk-forward del selettore di meccanica (fase H).

Due flussi di trade (entrambi già definiti negli studi precedenti):
- REVERSION   : sweep&reclaim long ai supporti, depth>=1$, london+ny, TP 5R
- CONTINUATION: pullback al VWAP in doppio uptrend H6/H2, impulso>=4$,
                entrata market al close della conferma, TP 3R

Selettori confrontati (decisione mensile, SOLO dati passati):
- always_rev / always_cont / both  : benchmark statici
- trailing : trada il mese M la meccanica con expR trailing 6 mesi migliore
             (richiede >=12 trade nel trailing; se nessuna positiva: flat)
- regime   : efficiency ratio D1 (Kaufman, 20 giorni, soglia 0.35) del
             giorno del trade: trend -> continuation, range -> reversion

Nota di onestà: i filtri interni dei due flussi sono stati scelti guardando
l'intero campione; il walk-forward valida la REGOLA DI SWITCHING, non i
setup. La validazione completa dei setup richiede dati out-of-sample futuri.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd

from framework.data import load_m1, resample_tf
from framework.regime import regime_series
from framework.rr_study import ReclaimConfig, run_reclaim_study
from framework.structure import state_at, trend_state_series
from framework.vwap import anchored_vwap

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LOWS = ["pdl", "pdc", "swing_l", "asia_l", "round_100", "round_50", "pwl"]
SPREAD, BUF = 0.30, 0.3


def continuation_stream(m1) -> pd.DataFrame:
    """Trade continuation (baseline market@close, TP 3R) → colonne time, r."""
    m6 = resample_tf(m1, "M6")
    m6["vwap_d"] = anchored_vwap(m6, "day")
    h6 = state_at(trend_state_series(resample_tf(m1, "H6"), 3, "6h"),
                  m6.index + pd.Timedelta("6min"))
    h2 = state_at(trend_state_series(resample_tf(m1, "H2"), 3, "2h"),
                  m6.index + pd.Timedelta("6min"))
    m1_idx = m1.index
    m1h, m1l, m1c = m1.high.values, m1.low.values, m1.close.values
    hi, lo, cl = m6.high.values, m6.low.values, m6.close.values
    vd = m6.vwap_d.values
    idx = m6.index
    hours, days = idx.hour, idx.normalize()
    rows, last_sig, day_count, day_start_i = [], None, {}, 0
    for i in range(1, len(m6)):
        if days[i] != days[i - 1]:
            day_start_i = i
        if not (7 <= hours[i] < 19) or h6[i] != 1 or h2[i] != 1 or np.isnan(vd[i]):
            continue
        if day_count.get(days[i], 0) >= 3:
            continue
        t_close = idx[i] + pd.Timedelta("6min")
        if last_sig is not None and (t_close - last_sig) < pd.Timedelta("30min"):
            continue
        if not (lo[i] <= vd[i] and cl[i] > vd[i] and cl[i] > hi[i - 1]):
            continue
        imp = float(hi[day_start_i:i].max() - vd[i]) if i > day_start_i else 0.0
        if imp < 4.0:
            continue
        j0 = max(day_start_i, i - 5)
        entry = cl[i]
        stop = lo[j0:i + 1].min() - BUF
        risk = entry - stop
        if not (1.0 <= risk <= 10.0):
            continue
        i0 = int(m1_idx.searchsorted(t_close))
        i1 = int(m1_idx.searchsorted(days[i] + pd.Timedelta(hours=21)))
        if i1 - i0 < 2:
            continue
        last_sig = t_close
        day_count[days[i]] = day_count.get(days[i], 0) + 1
        target = entry + 3.0 * risk
        h_, l_ = m1h[i0:i1], m1l[i0:i1]
        hit_sl, hit_tp = l_ <= stop, h_ >= target
        i_sl = int(np.argmax(hit_sl)) if hit_sl.any() else None
        i_tp = int(np.argmax(hit_tp)) if hit_tp.any() else None
        if i_sl is not None and (i_tp is None or i_sl <= i_tp):
            r = -1.0
        elif i_tp is not None:
            r = 3.0
        else:
            r = float((m1c[i1 - 1] - entry) / risk)
        rows.append({"time": t_close, "r": r - SPREAD / risk})
    return pd.DataFrame(rows)


def reversion_stream(m1) -> pd.DataFrame:
    df = run_reclaim_study(m1, ReclaimConfig())
    sel = df[(df.side == "above") & df.kind.isin(LOWS)
             & (df.sweep_depth >= 1.0) & df.session.isin(["london", "ny"])]
    return sel[["time", "r_net"]].rename(columns={"r_net": "r"}).reset_index(drop=True)


def monthly_walkforward(streams: dict[str, pd.DataFrame],
                        trailing_months: int = 6, min_trades: int = 12):
    """Per ogni mese sceglie la meccanica con miglior expR trailing (>0)."""
    for df in streams.values():
        df["month"] = df.time.dt.to_period("M")
    months = sorted(set().union(*[set(df.month) for df in streams.values()]))
    picks, out_rows = {}, []
    for m in months:
        best, best_exp = None, 0.0
        for name, df in streams.items():
            trail = df[(df.month < m) & (df.month >= m - trailing_months)]
            if len(trail) >= min_trades and trail.r.mean() > best_exp:
                best, best_exp = name, trail.r.mean()
        picks[str(m)] = best
        if best is not None:
            cur = streams[best][streams[best].month == m]
            for _, row in cur.iterrows():
                out_rows.append({"time": row.time, "r": row.r, "mech": best})
    return pd.DataFrame(out_rows), picks


def describe(df: pd.DataFrame, label: str):
    if df.empty:
        print(f"{label:24s} nessun trade")
        return
    r = df.r
    yearly = df.groupby(df.time.dt.year).r.mean()
    eq = r.cumsum()
    dd = (eq.cummax() - eq).max()
    rec = df[df.time.dt.year >= 2024]
    print(f"{label:24s} n={len(df):4d} expR={r.mean():+.3f} totR={r.sum():+7.1f} "
          f"maxDD={dd:5.1f}R anni+={int((yearly > 0).sum())}/{yearly.notna().sum()} "
          f"| 2024-26: expR={rec.r.mean():+.3f} totR={rec.r.sum():+6.1f}")


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    cont = continuation_stream(m1)
    rev = reversion_stream(m1)
    print(f"flussi: continuation n={len(cont)}, reversion n={len(rev)}\n")

    print("== benchmark statici ==")
    describe(cont.assign(mech="cont"), "always continuation")
    describe(rev.assign(mech="rev"), "always reversion")
    both = pd.concat([cont, rev]).sort_values("time").reset_index(drop=True)
    describe(both.assign(mech="both"), "both (sempre entrambe)")

    print("\n== walk-forward: selettore trailing 6 mesi ==")
    wf, picks = monthly_walkforward({"cont": cont.copy(), "rev": rev.copy()})
    describe(wf, "trailing-switch")
    counts = pd.Series(list(picks.values())).value_counts(dropna=False)
    print("   scelte mensili:", dict(counts))

    print("\n== walk-forward: selettore di regime (ER 20g > 0.35) ==")
    reg = regime_series(m1, n=20, threshold=0.35)
    def with_regime(df):
        d = df.copy()
        d["regime"] = reg.reindex(d.time.dt.normalize()).values
        return d
    cont_r, rev_r = with_regime(cont), with_regime(rev)
    picked = pd.concat([cont_r[cont_r.regime == "trend"].assign(mech="cont"),
                        rev_r[rev_r.regime == "range"].assign(mech="rev")])
    picked = picked.sort_values("time").reset_index(drop=True)
    describe(picked, "regime-switch")
    print("   trend->cont:", int((cont_r.regime == "trend").sum()),
          "trade | range->rev:", int((rev_r.regime == "range").sum()), "trade")
    out = os.environ.get("WF_OUT")
    if out:
        both.to_parquet(out)


if __name__ == "__main__":
    main()
