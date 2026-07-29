#!/usr/bin/env python3
"""Studio di precisione dell'entrata sul setup di continuazione.

Per OGNI setup (H6+H2 uptrend, pullback M6 sul VWAP giornaliero, candela di
conferma, impulso di giornata >= 4$) confronta in modo appaiato:

Entrate (stop sempre sotto il minimo del pullback, TP 3R, EOD 21:00):
- market  : al close della candela di conferma (baseline)
- stopbuy : buy-stop sopra il massimo della conferma (+0.05$), finestra 60'
- limit50 : limit al 50% della candela di conferma, finestra 60'
- limitvw : limit al VWAP giornaliero, finestra 60'

Filtro qualità (applicato alla baseline):
- displacement: corpo della conferma >= 50% del range

Stop alternativi (entrata market):
- stop_pullback (base), stop_vwap (VWAP - 0.5$), stop_bar (low conferma - 0.3$)
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
SPREAD, BUF = 0.30, 0.3
MIN_RISK, MAX_RISK = 1.0, 10.0
RR = 3.0
FILL_WINDOW_MIN = 60
MIN_IMPULSE = 4.0


def outcome(m1h, m1l, m1c, i0, i1, entry, stop, cfg_rr=RR):
    risk = entry - stop
    target = entry + cfg_rr * risk
    h, l = m1h[i0:i1], m1l[i0:i1]
    hit_sl, hit_tp = l <= stop, h >= target
    i_sl = int(np.argmax(hit_sl)) if hit_sl.any() else None
    i_tp = int(np.argmax(hit_tp)) if hit_tp.any() else None
    if i_sl is not None and (i_tp is None or i_sl <= i_tp):
        r = -1.0
    elif i_tp is not None:
        r = cfg_rr
    else:
        r = float((m1c[i1 - 1] - entry) / risk)
    return r - SPREAD / risk


def find_fill(m1h, m1l, i0, i_max, kind, price):
    """Indice M1 del fill di un ordine pendente, o None."""
    if kind == "stopbuy":
        hit = m1h[i0:i_max] >= price
    else:  # limit
        hit = m1l[i0:i_max] <= price
    if not hit.any():
        return None
    return i0 + int(np.argmax(hit))


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    m6 = resample_tf(m1, "M6")
    m6["vwap_d"] = anchored_vwap(m6, "day")
    s_h6 = trend_state_series(resample_tf(m1, "H6"), k=3, freq="6h")
    s_h2 = trend_state_series(resample_tf(m1, "H2"), k=3, freq="2h")
    h6 = state_at(s_h6, m6.index + pd.Timedelta("6min"))
    h2 = state_at(s_h2, m6.index + pd.Timedelta("6min"))

    m1_idx = m1.index
    m1h, m1l, m1c = m1.high.values, m1.low.values, m1.close.values
    op, hi, lo, cl = m6.open.values, m6.high.values, m6.low.values, m6.close.values
    vd = m6.vwap_d.values
    idx = m6.index
    hours = idx.hour
    days = idx.normalize()

    rows = []
    last_sig = None
    day_count = {}
    day_start_i = 0
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
        if imp < MIN_IMPULSE:
            continue
        j0 = max(day_start_i, i - 5)
        stop_pb = lo[j0:i + 1].min() - BUF
        entry0 = cl[i]
        if not (MIN_RISK <= entry0 - stop_pb <= MAX_RISK):
            continue
        i0 = int(m1_idx.searchsorted(t_close))
        i1 = int(m1_idx.searchsorted(days[i] + pd.Timedelta(hours=21)))
        i_max = min(i0 + FILL_WINDOW_MIN, i1)
        if i1 - i0 < 2:
            continue
        last_sig = t_close
        day_count[days[i]] = day_count.get(days[i], 0) + 1

        rng = hi[i] - lo[i]
        body = cl[i] - op[i]
        row = {"time": t_close, "year": int(idx[i].year),
               "displacement": bool(rng > 0 and body / rng >= 0.5)}
        # entrata baseline + stop alternativi
        row["market"] = outcome(m1h, m1l, m1c, i0, i1, entry0, stop_pb)
        row["risk_market"] = entry0 - stop_pb
        for sname, sprice in (("stop_vwap", vd[i] - 0.5), ("stop_bar", lo[i] - BUF)):
            if MIN_RISK / 3 <= entry0 - sprice <= MAX_RISK:
                row[sname] = outcome(m1h, m1l, m1c, i0, i1, entry0, sprice)
                row[f"risk_{sname}"] = entry0 - sprice
        # entrate alternative (stop sotto il pullback)
        for ename, kind, price in (("stopbuy", "stopbuy", hi[i] + 0.05),
                                   ("limit50", "limit", (hi[i] + lo[i]) / 2),
                                   ("limitvw", "limit", vd[i])):
            j = find_fill(m1h, m1l, i0, i_max, kind, price)
            if j is None or price - stop_pb < MIN_RISK / 3 or price - stop_pb > MAX_RISK:
                row[ename] = np.nan
            else:
                row[ename] = outcome(m1h, m1l, m1c, j, i1, price, stop_pb)
                row[f"risk_{ename}"] = price - stop_pb
        rows.append(row)

    df = pd.DataFrame(rows)
    out = os.environ.get("ENTRY_OUT")
    if out:
        df.to_parquet(out)
    print(f"setup: {len(df)}  (displacement: {df.displacement.mean():.0%})\n")

    def line(name, col, sub=None):
        d = df if sub is None else df[sub]
        s = d[col].dropna()
        if len(s) < 50:
            print(f"{name:28s} n={len(s)} (piccolo)")
            return
        fill = len(s) / len(d)
        rk = d.get(f"risk_{col}")
        rk_med = rk.dropna().median() if rk is not None else float("nan")
        rec = d[d.year >= 2024][col].dropna()
        win = (s >= RR - 0.5).mean()
        print(f"{name:28s} fill={fill:5.0%} rischio~{rk_med:4.2f}$ n={len(s):4d} "
              f"win={win:.3f} expR={s.mean():+.3f} perSetup={s.mean()*fill:+.3f} "
              f"| 2024-26 expR={rec.mean():+.3f} (n={len(rec)})")

    print("== ENTRATE (stop sotto il pullback, TP 3R) ==")
    line("market@close (baseline)", "market")
    line("stop-buy sopra conferma", "stopbuy")
    line("limit 50% conferma", "limit50")
    line("limit al VWAP", "limitvw")
    print("\n== FILTRO DISPLACEMENT (entrata market) ==")
    line("con displacement", "market", df.displacement)
    line("senza displacement", "market", ~df.displacement)
    print("\n== STOP ALTERNATIVI (entrata market) ==")
    line("stop sotto pullback (base)", "market")
    line("stop sotto VWAP-0.5", "stop_vwap")
    line("stop sotto candela conferma", "stop_bar")


if __name__ == "__main__":
    main()
