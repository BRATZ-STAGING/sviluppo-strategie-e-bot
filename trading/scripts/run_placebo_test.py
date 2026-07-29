#!/usr/bin/env python3
"""Test del placebo: il segnale vale qualcosa, o basta essere comprati?

Domanda: se al posto del nostro criterio d'ingresso (tocco del VWAP con
conferma, in doppio uptrend, dopo un impulso) entrassimo in un momento
QUALSIASI della stessa giornata, con lo stesso stop, lo stesso obiettivo e
la stessa uscita, otterremmo un risultato diverso?

Il placebo replica tutto tranne il criterio: stessi giorni, stesso numero di
operazioni per giorno, stessa finestra oraria, stessa costruzione dello stop
(minimo delle ultime 5 candele M6 meno il buffer), stessi filtri di rischio,
stesso obiettivo 3R, stessa chiusura alle 21:00, stesso spread. Cambia solo
QUANDO si entra: a caso invece che al segnale.

Se il risultato reale cade dentro la distribuzione dei placebo, il criterio
d'ingresso non sta aggiungendo nulla.

Uso: python3 run_placebo_test.py [ripetizioni]
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1, resample_tf                 # noqa: E402
from framework.structure import state_at, trend_state_series     # noqa: E402
from framework.volatility import (atr_at, daily_atr,             # noqa: E402
                                  high_volatility_months)
from framework.vwap import anchored_vwap                         # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPREAD, BUF, RR = 0.30, 0.3, 3.0
MIN_RISK, MAX_RISK, MIN_IMPULSE = 1.0, 10.0, 4.0
CALIB = (2020, 2024)
SEED = 20260726                      # riproducibilità


def simula(i, m6v, m1v, day_start, day_end_m1, buf, r_min, r_max):
    """Esito in R di un'operazione aperta alla chiusura della candela M6 ``i``."""
    idx, lo, cl = m6v["idx"], m6v["lo"], m6v["cl"]
    m1_idx, m1h, m1l, m1c = m1v
    entry = float(cl[i])
    j0 = max(day_start, i - 5)
    stop = float(lo[j0:i + 1].min() - buf)
    risk = entry - stop
    if not (r_min <= risk <= r_max):
        return None
    a = int(m1_idx.searchsorted(idx[i] + pd.Timedelta("6min")))
    b = day_end_m1
    if b - a < 2:
        return None
    target = entry + RR * risk
    h_, l_ = m1h[a:b], m1l[a:b]
    sl, tp = l_ <= stop, h_ >= target
    i_sl = int(np.argmax(sl)) if sl.any() else None
    i_tp = int(np.argmax(tp)) if tp.any() else None
    if i_sl is not None and (i_tp is None or i_sl <= i_tp):
        r = -1.0
    elif i_tp is not None:
        r = RR
    else:
        r = float((m1c[b - 1] - entry) / risk)
    return r - SPREAD / risk


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    rng = np.random.default_rng(SEED)
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    m6 = resample_tf(m1, "M6")
    m6["vwap"] = anchored_vwap(m6, "day")
    closes = m6.index + pd.Timedelta("6min")
    m6["h6"] = state_at(trend_state_series(resample_tf(m1, "H6"), 3, "6h"), closes)
    m6["h2"] = state_at(trend_state_series(resample_tf(m1, "H2"), 3, "2h"), closes)
    atr = daily_atr(m1, 14)
    m6["atr"] = atr_at(atr, m6.index).values

    mask = (atr.index.year >= CALIB[0]) & (atr.index.year <= CALIB[1])
    med = float(atr[mask].median())
    k = {"imp": MIN_IMPULSE / med, "buf": BUF / med,
         "rmin": MIN_RISK / med, "rmax": MAX_RISK / med}

    idx = m6.index
    hours, days = idx.hour, idx.normalize()
    hi, lo, cl = m6.high.values, m6.low.values, m6.close.values
    vd, h6, h2 = m6.vwap.values, m6.h6.values, m6.h2.values
    atrv = m6.atr.values
    m6v = {"idx": idx, "lo": lo, "cl": cl}
    m1v = (m1.index, m1.high.values, m1.low.values, m1.close.values)

    # confini di giornata e indici utilizzabili per gli ingressi
    giorni = {}
    for i in range(1, len(m6)):
        d = days[i]
        if d not in giorni:
            giorni[d] = {"start": i, "cand": []}
        if 7 <= hours[i] < 19:
            giorni[d]["cand"].append(i)
    for d, g in giorni.items():
        g["end_m1"] = int(m1v[0].searchsorted(d + pd.Timedelta(hours=21)))

    mesi_alto = high_volatility_months(
        atr, sorted({pd.Period(x.strftime("%Y-%m"), "M") for x in idx}), factor=1.5)

    def params(i):
        m = pd.Period(idx[i].strftime("%Y-%m"), "M")
        if mesi_alto.get(m, False):
            u = atrv[i]
            if np.isnan(u) or u <= 0:
                return None
            return k["buf"] * u, k["rmin"] * u, k["rmax"] * u, k["imp"] * u
        return BUF, MIN_RISK, MAX_RISK, MIN_IMPULSE

    # ---- strategia reale (switch) ----
    reali, per_giorno = [], {}
    last_sig, day_count = None, {}
    for i in range(1, len(m6)):
        d = days[i]
        g = giorni[d]
        if not (7 <= hours[i] < 19) or h6[i] != 1 or h2[i] != 1 or np.isnan(vd[i]):
            continue
        p = params(i)
        if p is None or day_count.get(d, 0) >= 3:
            continue
        buf, rmin, rmax, impmin = p
        t_sig = idx[i] + pd.Timedelta("6min")
        if last_sig is not None and (t_sig - last_sig) < pd.Timedelta("30min"):
            continue
        if not (lo[i] <= vd[i] and cl[i] > vd[i] and cl[i] > hi[i - 1]):
            continue
        if (float(hi[g["start"]:i].max() - vd[i]) if i > g["start"] else 0.0) < impmin:
            continue
        r = simula(i, m6v, m1v, g["start"], g["end_m1"], buf, rmin, rmax)
        if r is None:
            continue
        last_sig = t_sig
        day_count[d] = day_count.get(d, 0) + 1
        reali.append({"anno": int(idx[i].year), "r": r})
        per_giorno[d] = per_giorno.get(d, 0) + 1

    reale = pd.DataFrame(reali)
    tot_reale = reale.r.sum()
    print(f"strategia reale: {len(reale)} trade, {tot_reale:+.1f} R "
          f"({reale.r.mean():+.4f} per trade)\n", flush=True)

    # ---- placebo: stessi giorni e stesso numero di trade, ingresso a caso ----
    tot, per_anno = [], []
    for rep in range(reps):
        righe = []
        for d, quanti in per_giorno.items():
            g = giorni[d]
            cand = g["cand"]
            if not cand:
                continue
            scelti = rng.choice(cand, size=min(quanti, len(cand)), replace=False)
            for i in scelti:
                p = params(int(i))
                if p is None:
                    continue
                buf, rmin, rmax, _ = p
                r = simula(int(i), m6v, m1v, g["start"], g["end_m1"], buf, rmin, rmax)
                if r is not None:
                    righe.append({"anno": int(idx[int(i)].year), "r": r})
        df = pd.DataFrame(righe)
        tot.append(df.r.sum())
        per_anno.append(df.groupby("anno").r.sum())
        if (rep + 1) % 25 == 0:
            print(f"  {rep+1}/{reps} placebo simulati", flush=True)

    tot = np.array(tot)
    pct = float((tot >= tot_reale).mean())
    print(f"\n=== PLACEBO ({reps} simulazioni) ===")
    print(f"R totale placebo: mediana {np.median(tot):+.1f}, "
          f"5°-95° percentile [{np.percentile(tot,5):+.1f}, {np.percentile(tot,95):+.1f}]")
    print(f"R totale reale:   {tot_reale:+.1f}")
    print(f"\nquota di placebo che fanno MEGLIO del reale: {pct:.1%}")
    print("→ " + ("il criterio d'ingresso NON aggiunge nulla di distinguibile dal caso"
                  if pct > 0.10 else
                  "il criterio d'ingresso batte il caso a questo livello di campione"))

    pa = pd.DataFrame(per_anno)
    conf = pd.DataFrame({
        "reale": reale.groupby("anno").r.sum(),
        "placebo_mediana": pa.median(),
        "placebo_p05": pa.quantile(0.05),
        "placebo_p95": pa.quantile(0.95),
    })
    conf["reale_batte_placebo"] = [
        f"{(pa[a] < conf.reale[a]).mean():.0%}" if a in pa else "-" for a in conf.index]
    print("\n=== PER ANNO (R totale) ===")
    print(conf.to_string(float_format=lambda x: f"{x:+.1f}"))


if __name__ == "__main__":
    main()
