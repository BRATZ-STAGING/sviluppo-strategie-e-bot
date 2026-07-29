#!/usr/bin/env python3
"""Studio del setup di continuazione multi-timeframe (Esperimento B).

Sequenza: H6 e H2 in uptrend strutturale → su M6 pullback che tocca il VWAP
ancorato (giornaliero o settimanale) → candela di conferma (chiude sopra il
VWAP e sopra il massimo della candela precedente) → ingresso al close, stop
sotto il minimo del pullback, TP a griglia di R. Uscita forzata 21:00 UTC.
Short simmetrico in downtrend (per confronto).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd

from framework.data import load_m1, resample_tf
from framework.structure import state_at, trend_state_series
from framework.vwap import anchored_vwap

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

RR_GRID = [2.0, 3.0, 5.0]
SPREAD = 0.30
STOP_BUFFER = 0.3
MIN_RISK, MAX_RISK = 1.0, 10.0
PULLBACK_LOOKBACK = 5   # barre M6 per il minimo del pullback
COOLDOWN_MIN = 30
EOD_HOUR = 21
LAST_ENTRY_HOUR = 19
MAX_PER_DAY = 3


def walk_outcome(m1h, m1l, m1c, i0, i1, entry, stop, target, side):
    """Esito esatto su M1: (-1 sl | +rr tp | R a EOD, reason)."""
    h, l = m1h[i0:i1], m1l[i0:i1]
    if side == "long":
        hit_sl, hit_tp = l <= stop, h >= target
    else:
        hit_sl, hit_tp = h >= stop, l <= target
    i_sl = int(np.argmax(hit_sl)) if hit_sl.any() else None
    i_tp = int(np.argmax(hit_tp)) if hit_tp.any() else None
    risk = abs(entry - stop)
    if i_sl is not None and (i_tp is None or i_sl <= i_tp):
        return -1.0, "sl"
    if i_tp is not None:
        return abs(target - entry) / risk, "tp"
    last = m1c[i1 - 1]
    r = (last - entry) / risk if side == "long" else (entry - last) / risk
    return float(r), "eod"


def main():
    years = [int(y) for y in sys.argv[1:]] or None
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"), years=years)
    m6 = resample_tf(m1, "M6")
    m6["vwap_d"] = anchored_vwap(m6, "day")
    m6["vwap_w"] = anchored_vwap(m6, "week")
    s_h6 = trend_state_series(resample_tf(m1, "H6"), k=3, freq="6h")
    s_h2 = trend_state_series(resample_tf(m1, "H2"), k=3, freq="2h")
    close_times = m6.index + pd.Timedelta("6min")
    h6 = state_at(s_h6, close_times)
    h2 = state_at(s_h2, close_times)

    m1_idx = m1.index
    m1h, m1l, m1c = m1.high.values, m1.low.values, m1.close.values
    o, hi, lo, cl = m6.open.values, m6.high.values, m6.low.values, m6.close.values
    vd, vw = m6.vwap_d.values, m6.vwap_w.values
    idx = m6.index
    hours = idx.hour
    days = idx.normalize()

    rows = []
    last_signal_time = None
    day_count = {}
    for i in range(1, len(m6)):
        if not (7 <= hours[i] < LAST_ENTRY_HOUR):
            continue
        day = days[i]
        if day_count.get(day, 0) >= MAX_PER_DAY:
            continue
        t_close = idx[i] + pd.Timedelta("6min")
        if last_signal_time is not None and \
                (t_close - last_signal_time) < pd.Timedelta(minutes=COOLDOWN_MIN):
            continue
        for side, st6, st2 in (("long", 1, 1), ("short", -1, -1)):
            if h6[i] != st6 or h2[i] != st2:
                continue
            for vname, v in (("day", vd), ("week", vw)):
                if np.isnan(v[i]):
                    continue
                if side == "long":
                    touched = lo[i] <= v[i]
                    confirmed = cl[i] > v[i] and cl[i] > hi[i - 1]
                else:
                    touched = hi[i] >= v[i]
                    confirmed = cl[i] < v[i] and cl[i] < lo[i - 1]
                if not (touched and confirmed):
                    continue
                j0 = max(0, i - PULLBACK_LOOKBACK)
                entry = cl[i]
                if side == "long":
                    stop = lo[j0:i + 1].min() - STOP_BUFFER
                    risk = entry - stop
                else:
                    stop = hi[j0:i + 1].max() + STOP_BUFFER
                    risk = stop - entry
                if not (MIN_RISK <= risk <= MAX_RISK):
                    continue
                i0 = int(m1_idx.searchsorted(t_close))
                i1 = int(m1_idx.searchsorted(day + pd.Timedelta(hours=EOD_HOUR)))
                if i1 - i0 < 2:
                    continue
                row = {"time": t_close, "side": side, "vwap": vname,
                       "risk_usd": float(risk), "year": int(idx[i].year)}
                # MFE prima dello stop
                h_, l_ = m1h[i0:i1], m1l[i0:i1]
                fav = (h_ - entry) if side == "long" else (entry - l_)
                adv_hit = (l_ <= stop) if side == "long" else (h_ >= stop)
                i_sl = int(np.argmax(adv_hit)) if adv_hit.any() else None
                favw = fav[:i_sl] if i_sl is not None else fav
                row["mfe_r"] = float(favw.max() / risk) if len(favw) else 0.0
                for rr in RR_GRID:
                    target = entry + rr * risk if side == "long" else entry - rr * risk
                    r, reason = walk_outcome(m1h, m1l, m1c, i0, i1, entry, stop,
                                             target, side)
                    row[f"r{rr:g}"] = r - SPREAD / risk
                    row[f"reason{rr:g}"] = reason
                rows.append(row)
                last_signal_time = t_close
                day_count[day] = day_count.get(day, 0) + 1
                break   # un solo vwap per segnale (priorità al giornaliero)
            else:
                continue
            break       # un solo lato per barra
    df = pd.DataFrame(rows)
    out = os.environ.get("MTF_OUT")
    if out:
        df.to_parquet(out)
    print(f"setup trovati: {len(df)}")
    if df.empty:
        return
    for side in ("long", "short"):
        d = df[df.side == side]
        if len(d) < 50:
            print(f"\n{side}: n={len(d)} (troppo piccolo)")
            continue
        print(f"\n### {side} (n={len(d)}, rischio mediano {d.risk_usd.median():.2f}$) ###")
        for rr in RR_GRID:
            col = f"r{rr:g}"
            yearly = d.groupby("year")[col].mean()
            rec = d[d.year >= 2024]
            win = (d[f"reason{rr:g}"] == "tp").mean()
            print(f"  TP {rr:g}R: expR={d[col].mean():+.3f} win={win:.3f} "
                  f"anni+={int((yearly > 0).sum())}/{yearly.notna().sum()} | "
                  f"2024-26 expR={rec[col].mean():+.3f} (n={len(rec)})")
        print("  MFE: " + "  ".join(f">={r}R: {(d.mfe_r >= r).mean():.3f}"
                                    for r in [1, 2, 3, 5]))
        print("  per vwap:", {v: len(d[d.vwap == v]) for v in ("day", "week")})


if __name__ == "__main__":
    main()
