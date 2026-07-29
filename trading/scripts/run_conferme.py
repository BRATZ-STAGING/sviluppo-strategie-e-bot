#!/usr/bin/env python3
"""L'obiettivo deve dipendere dalla qualità del setup: quante conferme ci sono?

Idea (dell'utente): non un RR unico per tutte le operazioni, ma un obiettivo
scelto operazione per operazione in base a QUANTI timeframe confermano la
direzione. Uno swing H6 confermato anche da H3, M66 e M33 merita 1:10; un
setup con le sole condizioni minime merita 1:3.

Qui si misura se l'ipotesi regge, PRIMA di costruirci sopra:
1) per ogni operazione si conta quante strutture fra H3, M66 e M33 sono
   allineate alla direzione (H6 e H2 lo sono già per costruzione: sono la
   condizione d'ingresso). Punteggio 0-3.
2) per ogni punteggio si guarda quanto lontano arriva il prezzo (MFE) e quale
   obiettivo rende di più.
3) se e solo se i punteggi alti corrono di più, si costruisce la mappa
   punteggio -> obiettivo e la si confronta con l'obiettivo unico.

Tutte le strutture sono causali: uno swing è confermato k barre dopo il suo
estremo e lo stato vale dalla chiusura della candela che rompe.

Uso: python3 run_conferme.py [out.parquet]
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf      # noqa: E402
from framework.structure import state_at, trend_state_series     # noqa: E402
from framework.volatility import (atr_at, daily_atr,             # noqa: E402
                                  high_volatility_months)
from framework.vwap import anchored_vwap                         # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPREAD, BUF = 0.30, 0.3
MIN_RISK, MAX_RISK, MIN_IMPULSE = 1.0, 10.0, 4.0
CALIB, RR_GRID = (2020, 2024), [2.0, 3.0, 5.0, 8.0, 10.0]
MAX_GIORNO, COOLDOWN, SMA = 3, 30, 50
CONFERME = ["H12", "H3", "M66", "M33", "M12", "M6", "M3"]   # oltre a H6 e H2,
                                     # che sono già la condizione d'ingresso


def stato_tf(m1, tf, ref_times):
    """Stato di trend del timeframe ``tf`` valutato agli istanti dati."""
    s = resample_tf(m1, tf)
    freq = pd.Timedelta(TIMEFRAMES[tf])
    return state_at(trend_state_series(s, 3, freq), ref_times)


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    m6 = resample_tf(m1, "M6")
    m6["vwap"] = anchored_vwap(m6, "day")
    t_cl = m6.index + pd.Timedelta("6min")
    m6["h6"] = stato_tf(m1, "H6", t_cl)
    m6["h2"] = stato_tf(m1, "H2", t_cl)
    for tf in CONFERME:
        m6[tf] = stato_tf(m1, tf, t_cl)
    atr = daily_atr(m1, 14)
    m6["atr"] = atr_at(atr, m6.index).values
    d1 = m1.close.resample("1D").last().dropna()
    macro = (d1 > d1.rolling(SMA).mean()).shift(1)
    macro.index = macro.index.normalize()
    macro = macro.to_dict()

    mask = (atr.index.year >= CALIB[0]) & (atr.index.year <= CALIB[1])
    med = float(atr[mask].median())
    k = {"imp": MIN_IMPULSE/med, "buf": BUF/med, "rmin": MIN_RISK/med, "rmax": MAX_RISK/med}
    alto = high_volatility_months(
        atr, sorted({pd.Period(x.strftime("%Y-%m"), "M") for x in m6.index}), 1.5)

    idx = m6.index
    hours, days = idx.hour, idx.normalize()
    hi, lo, cl = m6.high.values, m6.low.values, m6.close.values
    vd, h6, h2, av = m6.vwap.values, m6.h6.values, m6.h2.values, m6.atr.values
    conf = {tf: m6[tf].values for tf in CONFERME}
    m1_idx = m1.index
    m1h, m1l, m1c = m1.high.values, m1.low.values, m1.close.values
    mese = pd.PeriodIndex(idx, freq="M")

    out, last, count, dstart = [], None, {}, 0
    for i in range(1, len(m6)):
        d = days[i]
        if d != days[i-1]:
            dstart = i
        if not (7 <= hours[i] < 19) or np.isnan(vd[i]) or count.get(d, 0) >= MAX_GIORNO:
            continue
        t = idx[i] + pd.Timedelta("6min")
        if last is not None and (t-last) < pd.Timedelta(minutes=COOLDOWN):
            continue
        if alto.get(mese[i], False):
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
        segno = 1 if lato == "long" else -1
        if macro.get(d, False) != (lato == "long"):      # filtro di fondo
            continue
        entry = float(cl[i]); j0 = max(dstart, i-5)
        stop = float(lo[j0:i+1].min()-buf) if lato == "long" else float(hi[j0:i+1].max()+buf)
        risk = entry-stop if lato == "long" else stop-entry
        if not (rmin <= risk <= rmax):
            continue
        a = int(m1_idx.searchsorted(t)); b = int(m1_idx.searchsorted(d+pd.Timedelta(hours=21)))
        if b-a < 2:
            continue
        last = t; count[d] = count.get(d, 0)+1

        punteggio = sum(1 for tf in CONFERME if conf[tf][i] == segno)
        h_, l_, c_ = m1h[a:b], m1l[a:b], m1c[a:b]
        slh = (l_ <= stop) if lato == "long" else (h_ >= stop)
        i_sl = int(np.argmax(slh)) if slh.any() else None
        # massima escursione favorevole PRIMA dello stop, in R
        fav = ((h_-entry) if lato == "long" else (entry-l_))/risk
        fin = fav[:i_sl] if i_sl is not None else fav
        mfe = float(fin.max()) if len(fin) else 0.0
        fine = float(c_[-1])
        r_eod = ((fine-entry) if lato == "long" else (entry-fine))/risk
        rec = {"time": t, "anno": int(idx[i].year), "lato": lato,
               "punteggio": punteggio, "risk": risk, "mfe": mfe,
               "costo": SPREAD/risk}
        for tf in CONFERME:
            rec[f"c_{tf}"] = int(conf[tf][i] == segno)
        for rr in RR_GRID:
            tgt = entry+rr*risk if lato == "long" else entry-rr*risk
            hit = (h_ >= tgt) if lato == "long" else (l_ <= tgt)
            i_tp = int(np.argmax(hit)) if hit.any() else None
            if i_sl is not None and (i_tp is None or i_sl <= i_tp):
                rec[f"r{rr:g}"] = -1.0-rec["costo"]
            elif i_tp is not None:
                rec[f"r{rr:g}"] = rr-rec["costo"]
            else:
                rec[f"r{rr:g}"] = r_eod-rec["costo"]
        out.append(rec)

    df = pd.DataFrame(out)
    print(f"operazioni: {len(df)}  (filtro di fondo attivo)\n")

    print("=== 0. POTERE DISCRIMINANTE DI OGNI SINGOLO TIMEFRAME (a 1:10) ===")
    righe = []
    for tf in CONFERME:
        g = df.groupby(f"c_{tf}").r10.agg(n="size", medio="mean", tot="sum")
        if len(g) == 2:
            righe.append({"timeframe": tf, "n_allineato": int(g.loc[1, "n"]),
                          "R/op allineato": g.loc[1, "medio"],
                          "R/op contrario": g.loc[0, "medio"],
                          "differenza": g.loc[1, "medio"] - g.loc[0, "medio"],
                          "R totale allineato": g.loc[1, "tot"]})
    disc = pd.DataFrame(righe).sort_values("differenza", ascending=False)
    print(disc.to_string(index=False, float_format=lambda x: f"{x:+.3f}"))

    print("\n=== 1. I SETUP PIU' CONFERMATI CORRONO DI PIU'? ===")
    g = df.groupby("punteggio").agg(
        n=("mfe", "size"), mfe_mediana=("mfe", "median"),
        oltre_3R=("mfe", lambda s: (s >= 3).mean()),
        oltre_5R=("mfe", lambda s: (s >= 5).mean()),
        oltre_8R=("mfe", lambda s: (s >= 8).mean()),
        oltre_10R=("mfe", lambda s: (s >= 10).mean()))
    print(g.to_string(float_format=lambda x: f"{x:.3f}"))
    print("\nsoglie di break-even: 3R=25,0%  5R=16,7%  8R=11,1%  10R=9,1%")

    print("\n=== 2. QUALE OBIETTIVO RENDE DI PIU', PER PUNTEGGIO (R medio) ===")
    tab = df.groupby("punteggio")[[f"r{r:g}" for r in RR_GRID]].mean()
    tab.columns = [f"1:{r:g}" for r in RR_GRID]
    tab["n"] = df.groupby("punteggio").size()
    tab["migliore"] = tab[[f"1:{r:g}" for r in RR_GRID]].idxmax(axis=1)
    print(tab.to_string(float_format=lambda x: f"{x:+.3f}"))

    print("\n=== 3. R TOTALE per punteggio e obiettivo ===")
    tot = df.groupby("punteggio")[[f"r{r:g}" for r in RR_GRID]].sum()
    tot.columns = [f"1:{r:g}" for r in RR_GRID]
    print(tot.to_string(float_format=lambda x: f"{x:+.1f}"))

    print("\n=== 4. CONTRIBUTO DI OGNI SINGOLA CONFERMA (a 1:10) ===")
    for tf in CONFERME:
        c = df.groupby(f"c_{tf}").r10.agg(n="size", medio="mean", tot="sum")
        print(f"\n{tf} allineato:")
        print(c.to_string(float_format=lambda x: f"{x:+.3f}"))

    if len(sys.argv) > 1:
        df.to_parquet(sys.argv[1])
        print(f"\ndettaglio in {sys.argv[1]}")


if __name__ == "__main__":
    main()
