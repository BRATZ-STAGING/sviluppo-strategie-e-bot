#!/usr/bin/env python3
"""Strategia simmetrica: aggiunge il lato SHORT come immagine speculare del long.

Il long attuale opera i pullback sul VWAP in doppio uptrend. Lo short è la
riflessione esatta: doppio downtrend (H6 e H2 entrambe ribassiste), il prezzo
risale a toccare il VWAP e lo richiude SOTTO, chiudendo anche sotto il minimo
della candela precedente; stop sopra il massimo del pullback, obiettivo 3R.

Nessun parametro nuovo: le soglie sono le stesse del long (in dollari o in
unità di ATR secondo lo switch su volatilità già validato). L'unica novità è
che ora si può operare anche al ribasso.

Confronta: solo long · solo short · entrambi (con limiti di giornata condivisi).

Uso: python3 run_long_short.py
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
MAX_GIORNO, COOLDOWN = 3, 30


def prepara(m1):
    m6 = resample_tf(m1, "M6")
    m6["vwap"] = anchored_vwap(m6, "day")
    closes = m6.index + pd.Timedelta("6min")
    m6["h6"] = state_at(trend_state_series(resample_tf(m1, "H6"), 3, "6h"), closes)
    m6["h2"] = state_at(trend_state_series(resample_tf(m1, "H2"), 3, "2h"), closes)
    atr = daily_atr(m1, 14)
    m6["atr"] = atr_at(atr, m6.index).values
    return m6, atr


def macro_trend(m1, n=50):
    """Contesto di fondo: chiusura giornaliera sopra/sotto la propria media a n giorni.

    Causale: il valore del giorno D usa solo chiusure fino a D-1.
    """
    d1 = m1.close.resample("1D").last().dropna()
    sma = d1.rolling(n).mean()
    sopra = (d1 > sma).shift(1)
    sopra.index = sopra.index.normalize()
    return sopra


def genera(m1, m6, alto_vol, k, lati=("long", "short"), macro=None):
    """Segnali della strategia, con limiti di giornata condivisi fra i due lati.

    ``macro``: se fornita (serie booleana per giornata, True = sopra la media
    di fondo), i long si prendono solo sopra e gli short solo sotto.
    """
    idx = m6.index
    hours, days = idx.hour, idx.normalize()
    hi, lo, cl = m6.high.values, m6.low.values, m6.close.values
    vd, h6, h2 = m6.vwap.values, m6.h6.values, m6.h2.values
    atrv = m6.atr.values
    m1_idx = m1.index
    m1h, m1l, m1c = m1.high.values, m1.low.values, m1.close.values
    mese = pd.PeriodIndex(idx, freq="M")

    out, last_sig, day_count, day_start = [], None, {}, 0
    for i in range(1, len(m6)):
        d = days[i]
        if d != days[i - 1]:
            day_start = i
        if not (7 <= hours[i] < 19) or np.isnan(vd[i]):
            continue
        if day_count.get(d, 0) >= MAX_GIORNO:
            continue
        t_sig = idx[i] + pd.Timedelta("6min")
        if last_sig is not None and (t_sig - last_sig) < pd.Timedelta(minutes=COOLDOWN):
            continue

        # soglie: dollari o ATR, secondo il regime di volatilità del mese
        if alto_vol.get(mese[i], False):
            u = atrv[i]
            if np.isnan(u) or u <= 0:
                continue
            imp_min, buf = k["imp"] * u, k["buf"] * u
            r_min, r_max = k["rmin"] * u, k["rmax"] * u
        else:
            imp_min, buf, r_min, r_max = MIN_IMPULSE, BUF, MIN_RISK, MAX_RISK

        su = None if macro is None else macro.get(d, None)
        lato = None
        if "long" in lati and (macro is None or su is True) and h6[i] == 1 and h2[i] == 1 \
                and lo[i] <= vd[i] and cl[i] > vd[i] and cl[i] > hi[i - 1]:
            imp = float(hi[day_start:i].max() - vd[i]) if i > day_start else 0.0
            if imp >= imp_min:
                lato = "long"
        if lato is None and "short" in lati and (macro is None or su is False) \
                and h6[i] == -1 and h2[i] == -1 \
                and hi[i] >= vd[i] and cl[i] < vd[i] and cl[i] < lo[i - 1]:
            imp = float(vd[i] - lo[day_start:i].min()) if i > day_start else 0.0
            if imp >= imp_min:
                lato = "short"
        if lato is None:
            continue

        entry = float(cl[i])
        j0 = max(day_start, i - 5)
        if lato == "long":
            stop = float(lo[j0:i + 1].min() - buf)
            risk = entry - stop
        else:
            stop = float(hi[j0:i + 1].max() + buf)
            risk = stop - entry
        if not (r_min <= risk <= r_max):
            continue
        a = int(m1_idx.searchsorted(t_sig))
        b = int(m1_idx.searchsorted(d + pd.Timedelta(hours=21)))
        if b - a < 2:
            continue
        last_sig = t_sig
        day_count[d] = day_count.get(d, 0) + 1

        h_, l_ = m1h[a:b], m1l[a:b]
        if lato == "long":
            target = entry + RR * risk
            sl_hit, tp_hit = l_ <= stop, h_ >= target
        else:
            target = entry - RR * risk
            sl_hit, tp_hit = h_ >= stop, l_ <= target
        i_sl = int(np.argmax(sl_hit)) if sl_hit.any() else None
        i_tp = int(np.argmax(tp_hit)) if tp_hit.any() else None
        if i_sl is not None and (i_tp is None or i_sl <= i_tp):
            r = -1.0
        elif i_tp is not None:
            r = RR
        else:
            fine = float(m1c[b - 1])
            r = (fine - entry) / risk if lato == "long" else (entry - fine) / risk
        out.append({"time": t_sig, "anno": int(idx[i].year), "lato": lato,
                    "risk": risk, "r": r - SPREAD / risk})
    return pd.DataFrame(out)


def riepiloga(df, nome):
    if df.empty:
        print(f"{nome:24s} nessuna operazione")
        return None
    eq = df.r.cumsum()
    dd = float((eq.cummax() - eq).max())
    g = df.groupby("anno").r.agg(["size", "sum", "mean"])
    print(f"{nome:24s} n={len(df):5d}  expR={df.r.mean():+.3f}  "
          f"totR={df.r.sum():+7.1f}  maxDD={dd:5.1f}R  "
          f"anni+={int((g['mean'] > 0).sum())}/{len(g)}")
    return g["sum"]


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    m6, atr = prepara(m1)
    mask = (atr.index.year >= CALIB[0]) & (atr.index.year <= CALIB[1])
    med = float(atr[mask].median())
    k = {"imp": MIN_IMPULSE / med, "buf": BUF / med,
         "rmin": MIN_RISK / med, "rmax": MAX_RISK / med}
    mesi = sorted({pd.Period(x.strftime("%Y-%m"), "M") for x in m6.index})
    alto = high_volatility_months(atr, mesi, factor=1.5)

    print("=== RISULTATI (switch su volatilità in tutti i casi) ===")
    solo_l = genera(m1, m6, alto, k, ("long",))
    solo_s = genera(m1, m6, alto, k, ("short",))
    ent = genera(m1, m6, alto, k, ("long", "short"))
    # ipotesi: lo short perde perché combatte il trend di fondo dell'oro.
    # Filtro macro pre-registrato: long solo sopra la media a 50 giorni,
    # short solo sotto. Nessuna taratura sugli esiti.
    mac = macro_trend(m1, 50).to_dict()
    ent_f = genera(m1, m6, alto, k, ("long", "short"), macro=mac)
    solo_s_f = genera(m1, m6, alto, k, ("short",), macro=mac)
    curve = {
        "solo long": riepiloga(solo_l, "solo long"),
        "solo short": riepiloga(solo_s, "solo short"),
        "long + short": riepiloga(ent, "long + short"),
        "short + filtro macro": riepiloga(solo_s_f, "short + filtro macro"),
        "long+short + macro": riepiloga(ent_f, "long+short + filtro macro"),
    }
    print("\n=== R TOTALE PER ANNO ===")
    tab = pd.DataFrame(curve)
    tab["oro %"] = None
    d1 = m1.close.resample("1D").last().dropna()
    var = d1.groupby(d1.index.year).agg(["first", "last"])
    tab["oro %"] = ((var["last"] / var["first"] - 1) * 100).round(1)
    print(tab.to_string(float_format=lambda x: f"{x:+.1f}"))

    if not ent.empty:
        print("\n=== COMPOSIZIONE (long + short) ===")
        pl = ent.pivot_table(index="anno", columns="lato", values="r",
                             aggfunc=["size", "sum"])
        print(pl.to_string(float_format=lambda x: f"{x:+.1f}"))
        senza = ent[ent.anno != 2025]
        print(f"\nsenza il 2025: {senza.r.sum():+.1f} R su {len(senza)} operazioni "
              f"({senza.r.mean():+.4f} per operazione)")
        costo = (SPREAD / ent.risk).sum()
        print(f"lordo {ent.r.sum() + costo:+.1f} R · spread -{costo:.1f} R · "
              f"netto {ent.r.sum():+.1f} R")

    out = os.environ.get("LS_OUT")
    if out:
        ent.to_parquet(out)


if __name__ == "__main__":
    main()
