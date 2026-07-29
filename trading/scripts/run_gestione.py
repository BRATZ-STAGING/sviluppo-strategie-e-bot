#!/usr/bin/env python3
"""Meno stop: si ottiene con le conferme o con la gestione della posizione?

Lo studio sulle conferme (run_conferme_full.py) mostra che il tasso di stop
resta fra il 60% e il 64% qualunque combinazione di timeframe si usi: le
conferme spostano il RENDIMENTO, non la frequenza degli stop. La frequenza
degli stop dipende da dove sta lo stop e da come si gestisce la posizione.

Qui si confrontano, sulle stesse identiche operazioni:
- base           stop fisso fino all'obiettivo
- pareggio a xR  raggiunto +xR lo stop va al prezzo d'ingresso
- parziale a xR  a +xR si chiude meta' posizione e il resto va a pareggio

Regole conservative invariate: al minuto, se stop e obiettivo cadono insieme
vince lo stop; lo stesso vale fra stop-a-pareggio e obiettivo.

Uso: python3 run_gestione.py <out.parquet>
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf      # noqa: E402
from framework.gestione import chiusura_fine_giornata, esito  # noqa: E402
from framework.structure import state_at, trend_state_series     # noqa: E402
from framework.taratura import UFFICIALE as T                     # noqa: E402
from framework.volatility import (atr_at, daily_atr,             # noqa: E402
                                  high_volatility_months)
from framework.vwap import anchored_vwap                         # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPREAD, BUF = T.spread, T.buffer
MIN_RISK, MAX_RISK, MIN_IMPULSE = T.rischio_min, T.rischio_max, T.impulso_min
CALIB = T.calibrazione
MAX_GIORNO, COOLDOWN, SMA = T.max_operazioni_giorno, T.attesa_minuti, T.media_macro
TFS = ["M3", "M6", "M12", "M33", "M66", "H3", "H12"]
RR_GRID = [2, 3, 4, 5, 6, 7, 8, 9, 10]
BE_GRID = [1.0, 1.5, 2.0, 3.0, 4.0]      # soglie di spostamento a pareggio


def main():
    out_path = sys.argv[1]
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    m6 = resample_tf(m1, "M6")
    m6["vwap"] = anchored_vwap(m6, "day")
    t_cl = m6.index + pd.Timedelta("6min")
    for tf in TFS + ["H6", "H2"]:
        s = resample_tf(m1, tf)
        m6[tf] = state_at(trend_state_series(s, T.frattale_k, pd.Timedelta(TIMEFRAMES[tf])), t_cl)
    atr = daily_atr(m1, 14)
    m6["atr"] = atr_at(atr, m6.index).values
    d1 = m1.close.resample("1D").last().dropna()
    macro = (d1 > d1.rolling(SMA).mean()).shift(1)
    macro.index = macro.index.normalize()
    macro = macro.to_dict()

    mask = (atr.index.year >= CALIB[0]) & (atr.index.year <= CALIB[1])
    med = float(atr[mask].median())
    k = {"imp": MIN_IMPULSE / med, "buf": BUF / med,
         "rmin": MIN_RISK / med, "rmax": MAX_RISK / med}
    alto = high_volatility_months(
        atr, sorted({pd.Period(x.strftime("%Y-%m"), "M") for x in m6.index}),
        T.fattore_alta_volatilita)

    idx = m6.index
    hours, days = idx.hour, idx.normalize()
    hi, lo, cl = m6.high.values, m6.low.values, m6.close.values
    vd, atrv = m6.vwap.values, m6.atr.values
    st = {tf: m6[tf].values for tf in TFS + ["H6", "H2"]}
    h6, h2 = st["H6"], st["H2"]
    m1_idx = m1.index
    m1h, m1l, m1c = m1.high.values, m1.low.values, m1.close.values
    mese = pd.PeriodIndex(idx, freq="M")

    out, last, count, dstart = [], None, {}, 0
    for i in range(1, len(m6)):
        d = days[i]
        if d != days[i - 1]:
            dstart = i
        if not (T.ora_inizio <= hours[i] < T.ora_fine) or np.isnan(vd[i]) or count.get(d, 0) >= MAX_GIORNO:
            continue
        t = idx[i] + pd.Timedelta("6min")
        if last is not None and (t - last) < pd.Timedelta(minutes=COOLDOWN):
            continue
        if alto.get(mese[i], False):
            u = atrv[i]
            if np.isnan(u) or u <= 0:
                continue
            imp_min, buf = k["imp"] * u, k["buf"] * u
            rmin, rmax = k["rmin"] * u, k["rmax"] * u
        else:
            imp_min, buf, rmin, rmax = MIN_IMPULSE, BUF, MIN_RISK, MAX_RISK

        lato = None
        if h6[i] == 1 and h2[i] == 1 and lo[i] <= vd[i] and cl[i] > vd[i] \
                and cl[i] > hi[i - 1]:
            if (float(hi[dstart:i].max() - vd[i]) if i > dstart else 0) >= imp_min:
                lato = "long"
        if lato is None and h6[i] == -1 and h2[i] == -1 and hi[i] >= vd[i] \
                and cl[i] < vd[i] and cl[i] < lo[i - 1]:
            if (float(vd[i] - lo[dstart:i].min()) if i > dstart else 0) >= imp_min:
                lato = "short"
        if lato is None:
            continue
        segno = 1 if lato == "long" else -1
        if macro.get(d, False) != (lato == "long"):
            continue
        entry = float(cl[i]); j0 = max(dstart, i - T.barre_stop)
        stop = float(lo[j0:i + 1].min() - buf) if lato == "long" \
            else float(hi[j0:i + 1].max() + buf)
        risk = entry - stop if lato == "long" else stop - entry
        if not (rmin <= risk <= rmax):
            continue
        a = int(m1_idx.searchsorted(t))
        b = int(m1_idx.searchsorted(d + pd.Timedelta(hours=T.ora_chiusura)))
        if b - a < 2:
            continue
        last = t; count[d] = count.get(d, 0) + 1

        h_, l_, c_ = m1h[a:b], m1l[a:b], m1c[a:b]
        if lato == "long":
            fav, sfav = (h_ - entry) / risk, (entry - l_) / risk
        else:
            fav, sfav = (entry - l_) / risk, (h_ - entry) / risk
        r_eod = ((float(c_[-1]) - entry) if lato == "long"
                 else (entry - float(c_[-1]))) / risk
        costo = SPREAD / risk

        rec = {"time": t, "anno": int(idx[i].year), "lato": lato, "risk": risk,
               "costo": costo, "volalta": bool(alto.get(mese[i], False)),
               "mfe": float(fav.max())}
        for tf in TFS:
            rec[f"c_{tf}"] = int(st[tf][i] == segno)

        for rr in RR_GRID:
            r, mo = esito(fav, sfav, rr, costo=costo)
            if r is None:
                r = r_eod - costo
            rec[f"r{rr}"], rec[f"m{rr}"] = r, mo
            for be in BE_GRID:
                if be >= rr:
                    continue
                for nome, parz in (("be", False), ("pz", True)):
                    r2, m2 = esito(fav, sfav, rr, be=be, parziale=parz, costo=costo)
                    if r2 is None:
                        r2 = chiusura_fine_giornata(r_eod, be, parz,
                                                    rec["mfe"], costo)
                    key = f"{nome}{be:g}_{rr}"
                    rec[f"r_{key}"], rec[f"m_{key}"] = r2, m2
        out.append(rec)

    df = pd.DataFrame(out)
    df.to_parquet(out_path)
    print(f"{len(df)} operazioni -> {out_path}  ({df.shape[1]} colonne)")


if __name__ == "__main__":
    main()
