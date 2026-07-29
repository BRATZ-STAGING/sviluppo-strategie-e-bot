#!/usr/bin/env python3
"""Confronto pre-registrato: soglie in dollari fissi vs soglie in unità di ATR.

IPOTESI (fissata PRIMA di guardare i risultati): il crollo 2025-2026 non
dipende dall'idea della strategia ma dai parametri espressi in dollari fissi,
mentre la volatilità dell'oro è cresciuta di ~4 volte. Se l'ipotesi è vera,
riesprimendo le stesse soglie in unità di ATR il 2026 deve smettere di
perdere SENZA che il resto del campione peggiori.

NESSUN PARAMETRO VIENE OTTIMIZZATO SUGLI ESITI. I coefficienti k sono
ricavati per costruzione: k = soglia_in_dollari / ATR mediano del periodo di
calibrazione 2020-2024. Nel periodo di calibrazione le due varianti sono
quindi quasi equivalenti; differiscono solo dove la volatilità è cambiata.

La logica del segnale è identica nelle due varianti: cambia solo il modo in
cui sono espresse le soglie.

Uso: python3 run_atr_study.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1, resample_tf              # noqa: E402
from framework.structure import state_at, trend_state_series  # noqa: E402
from framework.volatility import atr_at, daily_atr           # noqa: E402
from framework.vwap import anchored_vwap                     # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPREAD, RR = 0.30, 3.0
CALIB = (2020, 2024)          # periodo su cui i due schemi sono resi equivalenti

# soglie storiche, in dollari
D_IMPULSE, D_RMIN, D_RMAX, D_BUF = 4.0, 1.0, 10.0, 0.3


def signals(m1, m6, atr_day, mode, k):
    """Segnali della strategia continuation.

    mode='usd'  soglie in dollari fissi (versione storica)
    mode='atr'  stesse soglie espresse in multipli dell'ATR del giorno
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

        u = 1.0 if mode == "usd" else atr[i]          # unità di misura
        imp_min = (D_IMPULSE if mode == "usd" else k["imp"] * u)
        buf = (D_BUF if mode == "usd" else k["buf"] * u)
        r_min = (D_RMIN if mode == "usd" else k["rmin"] * u)
        r_max = (D_RMAX if mode == "usd" else k["rmax"] * u)

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
            r = -1.0
        elif i_tp is not None:
            r = RR
        else:
            r = float((m1c[b - 1] - entry) / risk)
        out.append({"time": t_sig, "anno": int(idx[i].year), "risk": risk,
                    "r": r - SPREAD / risk, "win": i_tp is not None and
                    (i_sl is None or i_tp < i_sl)})
    return pd.DataFrame(out)


def riepilogo(df, nome):
    if df.empty:
        print(f"{nome}: nessun segnale")
        return None
    g = df.groupby("anno").agg(n=("r", "size"), expR=("r", "mean"), totR=("r", "sum"))
    g["rischio$"] = df.groupby("anno").risk.median()
    print(f"\n### {nome} — {len(df)} segnali, R medio {df.r.mean():+.4f}, "
          f"R totale {df.r.sum():+.1f} ###")
    print(g.to_string(float_format=lambda x: f"{x:+.3f}"))
    return g


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    m6 = resample_tf(m1, "M6")
    m6["vwap"] = anchored_vwap(m6, "day")
    closes = m6.index + pd.Timedelta("6min")
    m6["h6"] = state_at(trend_state_series(resample_tf(m1, "H6"), 3, "6h"), closes)
    m6["h2"] = state_at(trend_state_series(resample_tf(m1, "H2"), 3, "2h"), closes)

    atr = daily_atr(m1, 14)
    m6["atr"] = atr_at(atr, m6.index).values

    # --- calibrazione: k tale che in 2020-2024 la soglia ATR == soglia in $ ---
    mask = (atr.index.year >= CALIB[0]) & (atr.index.year <= CALIB[1])
    atr_med = float(atr[mask].median())
    k = {"imp": D_IMPULSE / atr_med, "buf": D_BUF / atr_med,
         "rmin": D_RMIN / atr_med, "rmax": D_RMAX / atr_med}
    print(f"ATR14 mediano {CALIB[0]}-{CALIB[1]}: {atr_med:.2f}$")
    print("coefficienti derivati (nessun adattamento agli esiti): " +
          ", ".join(f"{a}={b:.3f}" for a, b in k.items()))
    print("\nATR14 mediano per anno:")
    print(atr.groupby(atr.index.year).median().to_string(float_format=lambda x: f"{x:.2f}"))

    usd = signals(m1, m6, atr, "usd", k)
    atr_v = signals(m1, m6, atr, "atr", k)
    a = riepilogo(usd, "SOGLIE IN DOLLARI FISSI (versione storica)")
    b = riepilogo(atr_v, "SOGLIE IN UNITÀ DI ATR (versione riparametrizzata)")

    if a is not None and b is not None:
        cmp = pd.DataFrame({"expR_usd": a.expR, "expR_atr": b.expR,
                            "n_usd": a.n, "n_atr": b.n})
        cmp["delta"] = cmp.expR_atr - cmp.expR_usd
        print("\n### CONFRONTO PER ANNO ###")
        print(cmp.to_string(float_format=lambda x: f"{x:+.3f}"))
        rec_u = usd[usd.anno >= 2025].r
        rec_a = atr_v[atr_v.anno >= 2025].r
        print(f"\n2025-2026  dollari: {rec_u.mean():+.3f} R su {len(rec_u)} trade | "
              f"ATR: {rec_a.mean():+.3f} R su {len(rec_a)} trade")
        old_u = usd[usd.anno <= 2024].r
        old_a = atr_v[atr_v.anno <= 2024].r
        print(f"2020-2024  dollari: {old_u.mean():+.3f} R su {len(old_u)} trade | "
              f"ATR: {old_a.mean():+.3f} R su {len(old_a)} trade")

    out = os.environ.get("ATR_OUT")
    if out:
        usd.to_parquet(out.replace(".parquet", "_usd.parquet"))
        atr_v.to_parquet(out.replace(".parquet", "_atr.parquet"))


if __name__ == "__main__":
    main()
