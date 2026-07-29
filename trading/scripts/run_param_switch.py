#!/usr/bin/env python3
"""Far coesistere le due parametrizzazioni scegliendo mese per mese, in modo causale.

Le due varianti della stessa strategia (soglie in dollari fissi / in unità di
ATR) non si escludono: si può decidere quale usare in ogni mese. La decisione
deve però basarsi SOLO su informazione disponibile a quel momento, altrimenti
si sta solo raccontando il passato.

Regole confrontate:
- sempre_dollari / sempre_atr        : riferimenti statici
- switch_performance                 : ogni mese usa la variante con expR
                                       migliore nei K mesi precedenti
                                       (richiede almeno MIN_TRADE operazioni)
- switch_volatilita                  : usa la variante ATR quando l'ATR
                                       corrente supera di X volte la mediana
                                       storica NOTA FINO A QUEL MOMENTO
                                       (finestra espansiva, nessun lookahead)
- oracolo_annuale                    : sceglie col senno di poi la variante
                                       migliore di ogni anno. NON e' una
                                       strategia: e' il tetto massimo che una
                                       qualunque regola di switch puo' sperare.

Uso: python3 run_param_switch.py <usd.parquet> <atr.parquet>
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1              # noqa: E402
from framework.volatility import daily_atr      # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRAIL_MESI, MIN_TRADE = 6, 12       # switch su performance
VOL_FATTORE = 1.5                   # switch su volatilita' (pre-registrato)
MIN_STORIA_GIORNI = 250             # storia minima per la mediana espansiva


def mesi(df):
    return df.time.dt.tz_localize(None).dt.to_period("M")


def switch_performance(streams):
    """Per ogni mese la variante con expR trailing migliore (solo mesi passati)."""
    tutti = sorted(set().union(*[set(d["m"]) for d in streams.values()]))
    scelte = {}
    for m in tutti:
        best, best_exp = None, -np.inf
        for nome, d in streams.items():
            tr = d[(d["m"] < m) & (d["m"] >= m - TRAIL_MESI)]
            if len(tr) >= MIN_TRADE and tr.r.mean() > best_exp:
                best, best_exp = nome, float(tr.r.mean())
        scelte[m] = best
    return scelte


def switch_volatilita(streams, atr):
    """ATR quando la volatilita' corrente supera la sua mediana storica x VOL_FATTORE."""
    tutti = sorted(set().union(*[set(d["m"]) for d in streams.values()]))
    scelte = {}
    for m in tutti:
        inizio = m.start_time.tz_localize("UTC")     # l'indice ATR è UTC-aware
        passato = atr[atr.index < inizio].dropna()
        if len(passato) < MIN_STORIA_GIORNI:
            scelte[m] = "dollari"        # default finche' non c'e' storia
            continue
        recente = passato.tail(21).median()          # ultimo mese di borsa
        storica = passato.median()                   # finestra espansiva
        scelte[m] = "atr" if recente > VOL_FATTORE * storica else "dollari"
    return scelte


def applica(streams, scelte):
    righe = []
    for m, nome in scelte.items():
        if nome is None:
            continue
        d = streams[nome]
        cur = d[d["m"] == m]
        for _, r in cur.iterrows():
            righe.append({"time": r.time, "anno": r.anno, "r": r.r, "var": nome})
    return pd.DataFrame(righe).sort_values("time").reset_index(drop=True)


def riepiloga(df, nome, per_anno=True):
    if df.empty:
        print(f"{nome:22s} nessuna operazione")
        return None
    g = df.groupby("anno").r.agg(["size", "mean", "sum"])
    eq = df.r.cumsum()
    dd = float((eq.cummax() - eq).max())
    print(f"{nome:22s} n={len(df):5d}  expR={df.r.mean():+.3f}  "
          f"totR={df.r.sum():+7.1f}  maxDD={dd:5.1f}R  "
          f"anni+={int((g['mean'] > 0).sum())}/{len(g)}")
    return g["mean"]


def main():
    p_usd, p_atr = sys.argv[1], sys.argv[2]
    usd, atrv = pd.read_parquet(p_usd), pd.read_parquet(p_atr)
    usd["m"], atrv["m"] = mesi(usd), mesi(atrv)
    streams = {"dollari": usd, "atr": atrv}

    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    atr = daily_atr(m1, 14)

    print(f"flussi: dollari n={len(usd)}  atr n={len(atrv)}\n")
    print("=== RISULTATI ===")
    curve = {}
    curve["sempre dollari"] = riepiloga(usd.assign(var="dollari"), "sempre dollari")
    curve["sempre atr"] = riepiloga(atrv.assign(var="atr"), "sempre atr")

    sp = switch_performance(streams)
    df_sp = applica(streams, sp)
    curve["switch performance"] = riepiloga(df_sp, "switch performance")

    sv = switch_volatilita(streams, atr)
    df_sv = applica(streams, sv)
    curve["switch volatilita"] = riepiloga(df_sv, "switch volatilita")

    # tetto teorico: scelta col senno di poi, anno per anno
    ann_u = usd.groupby("anno").r.mean()
    ann_a = atrv.groupby("anno").r.mean()
    orac = []
    for a in sorted(set(ann_u.index) | set(ann_a.index)):
        pick = "atr" if ann_a.get(a, -9) > ann_u.get(a, -9) else "dollari"
        d = streams[pick]
        orac.append(d[d.anno == a].assign(var=pick))
    df_or = pd.concat(orac).sort_values("time")
    curve["oracolo (senno di poi)"] = riepiloga(df_or, "oracolo (senno poi)")

    print("\n=== expR PER ANNO ===")
    tab = pd.DataFrame(curve)
    print(tab.to_string(float_format=lambda x: f"{x:+.3f}"))

    print("\n=== SCELTE DELLE REGOLE CAUSALI ===")
    def sintesi(scelte, nome):
        s = pd.Series({str(k): (v or "flat") for k, v in scelte.items()})
        s.index = pd.PeriodIndex(s.index, freq="M")
        per_anno = s.groupby(s.index.year).apply(
            lambda x: " ".join(f"{k}:{v}" for k, v in x.value_counts().items()))
        print(f"\n{nome}:")
        print(per_anno.to_string())
    sintesi(sp, "switch performance")
    sintesi(sv, "switch volatilita")


if __name__ == "__main__":
    main()
