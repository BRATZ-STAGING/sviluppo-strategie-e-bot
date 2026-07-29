#!/usr/bin/env python3
"""Esporta i dati per il replay visivo della strategia (artifact HTML).

Produce uno o piu' "periodi": ognuno e' una serie di candele a un timeframe
scelto, con i trade della strategia continuation mappati sulla sua timeline.
I timeframe grandi servono al contesto (tutto lo storico), i piccoli
all'entrata precisa (un mese in M6).

Uso:
    python3 export_replay.py <out.json> full:H6 2025-10 2026-01

Formato compatto: i prezzi sono interi in centesimi rispetto a una base.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1, resample_tf          # noqa: E402
from framework.structure import state_at, trend_state_series  # noqa: E402
from framework.volatility import (atr_at, daily_atr,     # noqa: E402
                                  high_volatility_months)
from framework.vwap import anchored_vwap                 # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPREAD, BUF, RR = 0.30, 0.3, 3.0
MIN_RISK, MAX_RISK, MIN_IMPULSE = 1.0, 10.0, 4.0
CALIB = (2020, 2024)     # periodo su cui le due parametrizzazioni si equivalgono


def build_m6(m1):
    """M6 con VWAP giornaliero e stato di trend H6/H2 (tutto causale)."""
    m6 = resample_tf(m1, "M6")
    m6["vwap"] = anchored_vwap(m6, "day")
    closes = m6.index + pd.Timedelta("6min")
    m6["h6"] = state_at(trend_state_series(resample_tf(m1, "H6"), 3, "6h"), closes)
    m6["h2"] = state_at(trend_state_series(resample_tf(m1, "H2"), 3, "2h"), closes)
    return m6


def all_trades(m1, m6, mode="usd", k=None):
    """Trade della strategia continuation, con orari di entrata/uscita.

    mode='usd': soglie in dollari fissi. mode='atr': stesse soglie espresse
    in multipli dell'ATR del giorno (coefficienti ``k``).
    """
    idx = m6.index
    hours, days = idx.hour, idx.normalize()
    hi, lo, cl = m6.high.values, m6.low.values, m6.close.values
    vd, h6, h2 = m6.vwap.values, m6.h6.values, m6.h2.values
    atr = m6.atr.values
    m1_idx = m1.index
    m1h, m1l, m1c = m1.high.values, m1.low.values, m1.close.values

    out, last_sig, day_count, day_start = [], None, {}, 0
    for i in range(1, len(m6)):
        if days[i] != days[i - 1]:
            day_start = i
        if not (7 <= hours[i] < 19) or h6[i] != 1 or h2[i] != 1 or np.isnan(vd[i]):
            continue
        if mode == "atr" and (np.isnan(atr[i]) or atr[i] <= 0):
            continue
        if day_count.get(days[i], 0) >= 3:
            continue
        t_sig = idx[i] + pd.Timedelta("6min")
        if last_sig is not None and (t_sig - last_sig) < pd.Timedelta("30min"):
            continue
        if not (lo[i] <= vd[i] and cl[i] > vd[i] and cl[i] > hi[i - 1]):
            continue
        u = atr[i] if mode == "atr" else 1.0
        imp_min = MIN_IMPULSE if mode == "usd" else k["imp"] * u
        buf = BUF if mode == "usd" else k["buf"] * u
        r_min = MIN_RISK if mode == "usd" else k["rmin"] * u
        r_max = MAX_RISK if mode == "usd" else k["rmax"] * u
        if (float(hi[day_start:i].max() - vd[i]) if i > day_start else 0.0) < imp_min:
            continue
        j0 = max(day_start, i - 5)
        entry = float(cl[i])
        stop = float(lo[j0:i + 1].min() - buf)
        risk = entry - stop
        if not (r_min <= risk <= r_max):
            continue
        a = int(m1_idx.searchsorted(t_sig))
        b = int(m1_idx.searchsorted(days[i] + pd.Timedelta(hours=21)))
        if b - a < 2:
            continue
        last_sig = t_sig
        day_count[days[i]] = day_count.get(days[i], 0) + 1

        target = entry + RR * risk
        h_, l_ = m1h[a:b], m1l[a:b]
        sl_hit, tp_hit = l_ <= stop, h_ >= target
        i_sl = int(np.argmax(sl_hit)) if sl_hit.any() else None
        i_tp = int(np.argmax(tp_hit)) if tp_hit.any() else None
        if i_sl is not None and (i_tp is None or i_sl <= i_tp):
            r, px, xi, why = -1.0, stop, a + i_sl, "stop"
        elif i_tp is not None:
            r, px, xi, why = RR, target, a + i_tp, "target"
        else:
            px, xi, why = float(m1c[b - 1]), b - 1, "chiusura"
            r = (px - entry) / risk
        out.append({
            "t_in": t_sig, "t_out": m1_idx[xi],
            "entry": round(entry, 2), "sl": round(stop, 2),
            "tp": round(target, 2), "exit": round(px, 2),
            "r": round(r - SPREAD / risk, 3), "why": why,
        })
    return out


def daily_volatility(m1):
    """Range mediano delle candele M1 per giornata: misura di volatilita'."""
    rng = (m1.high - m1.low)
    return rng.groupby(m1.index.normalize()).median()


def mese_di(t):
    return pd.Period(t.tz_localize(None).strftime("%Y-%m"), "M")


def componi_sistemi(usd, atrv, atr):
    """I tre sistemi da confrontare: dollari, switch causale, oracolo annuale."""
    mesi = sorted({mese_di(t["t_in"]) for t in usd + atrv})
    alto = high_volatility_months(atr, mesi, factor=1.5)
    switch = [t for t in usd if not alto.get(mese_di(t["t_in"]), False)] + \
             [t for t in atrv if alto.get(mese_di(t["t_in"]), False)]

    anni = sorted({t["t_in"].year for t in usd + atrv})
    orac = []
    for a in anni:                       # scelta col senno di poi: solo riferimento
        cu = [t for t in usd if t["t_in"].year == a]
        ca = [t for t in atrv if t["t_in"].year == a]
        mu = np.mean([t["r"] for t in cu]) if cu else -9
        ma = np.mean([t["r"] for t in ca]) if ca else -9
        orac += ca if ma > mu else cu

    key = lambda ts: sorted(ts, key=lambda t: t["t_in"])
    return {"dollari": key(usd), "switch": key(switch), "oracolo": key(orac)}


def pack(series, sistemi, vol=None, label=""):
    """Serializza un periodo in forma compatta (prezzi interi in centesimi)."""
    base = float(np.floor(series.low.min()))
    cent = lambda s: [int(round((float(v) - base) * 100)) for v in s]
    idx = series.index
    per = {
        "id": label, "t0": int(idx[0].timestamp() * 1000), "base": base,
        "t": [int((x - idx[0]).total_seconds() // 60) for x in idx],
        "o": cent(series.open), "h": cent(series.high),
        "l": cent(series.low), "c": cent(series.close),
        "v": [None if np.isnan(x) else int(round((x - base) * 100)) for x in series.vwap]
             if "vwap" in series else [None] * len(idx),
        "s": [int(a) * 3 + int(b) for a, b in zip(series.h6, series.h2)]
             if "h6" in series else [0] * len(idx),
        "sistemi": {},
    }
    for nome, trades in sistemi.items():
        righe = []
        for tr in trades:
            i = int(idx.searchsorted(tr["t_in"], side="right") - 1)
            xi = int(idx.searchsorted(tr["t_out"], side="right") - 1)
            if i < 0 or i >= len(idx):
                continue
            righe.append({k: v for k, v in tr.items() if k not in ("t_in", "t_out")}
                         | {"i": i, "xi": max(i, min(xi, len(idx) - 1))})
        per["sistemi"][nome] = righe
    if vol is not None:
        per["vol"] = [round(float(vol.get(x.normalize(), np.nan)), 3)
                      if not np.isnan(vol.get(x.normalize(), np.nan)) else None
                      for x in idx]
    return per


def main():
    out_path = sys.argv[1]
    specs = sys.argv[2:] or ["full:H6"]
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    m6 = build_m6(m1)
    atr = daily_atr(m1, 14)
    m6["atr"] = atr_at(atr, m6.index).values

    # coefficienti derivati per costruzione, non ottimizzati sugli esiti
    mask = (atr.index.year >= CALIB[0]) & (atr.index.year <= CALIB[1])
    med = float(atr[mask].median())
    k = {"imp": MIN_IMPULSE / med, "buf": BUF / med,
         "rmin": MIN_RISK / med, "rmax": MAX_RISK / med}

    usd = all_trades(m1, m6, "usd")
    atrv = all_trades(m1, m6, "atr", k)
    sistemi = componi_sistemi(usd, atrv, atr)
    vol = daily_volatility(m1)
    for nome, ts in sistemi.items():
        print(f"{nome:10s} {len(ts):5d} trade  R totale {sum(t['r'] for t in ts):+7.1f}",
              flush=True)

    periods = []
    for spec in specs:
        if spec.startswith("full:"):
            tf = spec.split(":", 1)[1]
            s = resample_tf(m1, tf)
            s["vwap"] = np.nan                     # a TF grande il VWAP non serve
            s["h6"] = 0; s["h2"] = 0
            periods.append(pack(s, sistemi, vol=vol, label=f"full:{tf}"))
        else:
            month = pd.Period(spec, "M")
            lo_m = month.start_time.tz_localize("UTC")
            hi_m = (month + 1).start_time.tz_localize("UTC")
            s = m6[(m6.index >= lo_m) & (m6.index < hi_m)]
            sub = {n: [t for t in ts if lo_m <= t["t_in"] < hi_m]
                   for n, ts in sistemi.items()}
            periods.append(pack(s, sub, label=spec))
        p = periods[-1]
        det = " · ".join(f"{n} {len(v)}" for n, v in p["sistemi"].items())
        print(f"  {p['id']}: {len(p['t']):,} candele · {det}", flush=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"periods": periods}, f, separators=(",", ":"))
    print(f"\n{out_path}: {os.path.getsize(out_path)/1e6:.2f} MB")


if __name__ == "__main__":
    main()
