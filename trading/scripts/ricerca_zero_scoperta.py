#!/usr/bin/env python3
"""Ricerca da zero, fase di SCOPERTA: cosa si vede sul grafico pulito dell'oro.

Analisi cieca decisa il 02/10/2026 (docs/sessions/2026-10-02-...): nessun
VWAP, order block, livello o risultato gia' studiato. Solo il prezzo.

Periodo: SOLO 2009-2014 (scelto dall'utente). Lo script apre unicamente i file
di quegli anni e si ferma se trova una candela successiva: il 2015-2026 resta
intatto per la verifica.

Sezioni (ognuna stampa poche righe, il dettaglio va in Parquet):
  A  dati caricati
  B  stagionalita' per ora UTC e giorno della settimana (H1)
  C  continuazione o ritorno: autocorrelazione e variance ratio (M1..D1)
  D  dopo una candela molto grande: continua o torna indietro?
  E  la prima ora di una sessione dice qualcosa sul resto?
  F  gap del lunedi': si chiude?
  G  quanto si muove il prezzo, in dollari, contro lo spread

Uscita dettagliata: $RZ_OUT (default D:\\ricerca_zero\\scoperta_2009_2014) come Parquet.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ANNI = range(2009, 2015)
FINE = pd.Timestamp("2015-01-01", tz="UTC")
OUT = os.environ.get("RZ_OUT", r"D:\ricerca_zero\scoperta_2009_2014")
SPREAD_RIF = 0.35  # $: spread mediano Dukascopy 2023, il piu' basso misurato

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)


def carica_m1() -> pd.DataFrame:
    pezzi = []
    for a in ANNI:
        f = os.path.join(ROOT, "data", "XAUUSD_M1", f"XAUUSD_M1_{a}.parquet")
        d = pd.read_parquet(f, columns=["timestamp", "open", "high", "low", "close"])
        pezzi.append(d.set_index("timestamp"))
    m1 = pd.concat(pezzi).sort_index()
    m1.index = pd.to_datetime(m1.index, utc=True)
    if m1.index.max() >= FINE:
        sys.exit("STOP: trovata una candela del periodo di verifica")
    return m1[~m1.index.duplicated()]


def barre(m1: pd.DataFrame, regola: str) -> pd.DataFrame:
    b = m1.resample(regola).agg({"open": "first", "high": "max",
                                 "low": "min", "close": "last"})
    return b.dropna()


def tstat(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 else np.nan


def anni_concordi(x: pd.Series) -> str:
    """Quanti anni hanno la media dello stesso segno della media complessiva."""
    x = x.dropna()
    s = np.sign(x.mean())
    per_anno = x.groupby(x.index.year).mean()
    return f"{int((np.sign(per_anno) == s).sum())}/{len(per_anno)}"


def rendimenti(b: pd.DataFrame, passo: pd.Timedelta) -> pd.Series:
    """Log-rendimento chiusura su chiusura, solo fra barre consecutive."""
    r = np.log(b["close"]).diff()
    ok = b.index.to_series().diff() == passo
    return r[ok]


# --------------------------------------------------------------------- A
def sez_a(m1):
    print("\n== A. dati ==")
    g = m1.groupby(m1.index.year)
    t = pd.DataFrame({"minuti": g.size(), "min": g["low"].min(), "max": g["high"].max()})
    print(t.round(2).to_string())


# --------------------------------------------------------------------- B
def sez_b(h1):
    print("\n== B. stagionalita' (H1, rendimento in punti base) ==")
    r = rendimenti(h1, pd.Timedelta("1h")) * 1e4
    righe = []
    for ora, x in r.groupby(r.index.hour):
        righe.append({"ora": ora, "n": len(x), "media": x.mean(), "t": tstat(x),
                      "anni": anni_concordi(x), "|r| medio": x.abs().mean()})
    t = pd.DataFrame(righe).set_index("ora")
    t.to_parquet(os.path.join(OUT, "b_ore.parquet"))
    print("le 6 ore con |t| piu' alto:")
    print(t.reindex(t["t"].abs().sort_values(ascending=False).index).head(6).round(3).to_string())
    print("volatilita' per sessione (|r| medio, pb): "
          + ", ".join(f"{s} {t.loc[list(o), '|r| medio'].mean():.1f}"
                      for s, o in (("asia", range(0, 7)), ("london", range(7, 12)),
                                   ("ny", range(12, 21)), ("late", range(21, 24)))))
    d1 = r.groupby(r.index.normalize()).sum()
    righe = []
    for g, x in d1.groupby(d1.index.dayofweek):
        righe.append({"giorno": "lun mar mer gio ven sab dom".split()[g], "n": len(x),
                      "media": x.mean(), "t": tstat(x), "anni": anni_concordi(x)})
    print(pd.DataFrame(righe).set_index("giorno").round(3).to_string())


# --------------------------------------------------------------------- C
def sez_c(tfs):
    print("\n== C. continuazione o ritorno (autocorrelazione e variance ratio) ==")
    righe = []
    for nome, (b, passo) in tfs.items():
        r = rendimenti(b, passo)
        ac = r.autocorr(1)
        ac_anni = r.groupby(r.index.year).apply(lambda x: x.autocorr(1))
        riga = {"tf": nome, "n": len(r), "ac1": ac,
                "anni ac1<0": f"{int((ac_anni < 0).sum())}/{len(ac_anni)}"}
        var1 = r.var()
        for q in (2, 4, 8, 16):
            rq = r.rolling(q).sum().iloc[::q]
            riga[f"VR{q}"] = rq.var() / (q * var1)
        righe.append(riga)
    t = pd.DataFrame(righe).set_index("tf")
    t.to_parquet(os.path.join(OUT, "c_vr.parquet"))
    print(t.round(3).to_string())
    print("(VR<1 = il prezzo tende a tornare indietro, VR>1 = tende a continuare)")


# --------------------------------------------------------------------- D
def sez_d(tfs):
    print("\n== D. dopo una candela molto grande (z = rendimento / dev.std delle 100 precedenti) ==")
    print("   ingresso all'apertura della candela dopo, uscita dopo N candele;"
          " valori in dev.std, + = continua")
    righe, dett = [], []
    for nome in ("M5", "M15", "H1"):
        b, passo = tfs[nome]
        lr = np.log(b["close"]).diff()
        cont = b.index.to_series().diff() == passo
        lr = lr.where(cont)
        sd = lr.rolling(100, min_periods=80).std().shift(1)
        z = lr / sd
        for soglia in (2.0, 3.0):
            ev = z.abs() >= soglia
            riga = {"tf": nome, "soglia": soglia, "n": int(ev.sum())}
            for n in (1, 3, 6, 12):
                fut = np.log(b["close"].shift(-n) / b["open"].shift(-1))
                span = b.index.to_series().shift(-n) - b.index.to_series()
                fut = fut.where(span == n * passo)
                x = (np.sign(z) * fut / sd)[ev].dropna()
                riga[f"N{n}"] = f"{x.mean():+.3f} t{tstat(x):+.1f} {anni_concordi(x)}"
                dett.append(pd.DataFrame({"tf": nome, "soglia": soglia, "N": n, "esito": x}))
            righe.append(riga)
    pd.concat(dett).to_parquet(os.path.join(OUT, "d_grandi.parquet"))
    print(pd.DataFrame(righe).set_index(["tf", "soglia"]).to_string())


# --------------------------------------------------------------------- E
def sez_e(m1):
    print("\n== E. la prima parte della sessione dice qualcosa sul resto? ==")
    c = m1["close"]
    o = m1["open"]
    giorni = pd.Series(m1.index.normalize().unique())
    finestre = [("asia 0-7 -> london 7-12", (0, 7), (7, 12)),
                ("london 7-8 -> 8-12", (7, 8), (8, 12)),
                ("ny 12-13 -> 13-17", (12, 13), (13, 17)),
                ("ny 13-14 -> 14-20", (13, 14), (14, 20)),
                ("mattina 0-12 -> pomeriggio 12-21", (0, 12), (12, 21))]
    giorno = m1.index.normalize()
    ora = m1.index.hour
    righe = []
    for nome, (a1, a2), (b1, b2) in finestre:
        def ret(h1, h2):
            m = (ora >= h1) & (ora < h2)
            g = pd.DataFrame({"o": o[m], "c": c[m]}).groupby(giorno[m])
            return np.log(g["c"].last() / g["o"].first())
        r1, r2 = ret(a1, a2), ret(b1, b2)
        d = pd.concat([r1, r2], axis=1, keys=["r1", "r2"]).dropna()
        segno = (np.sign(d["r1"]) * d["r2"] * 1e4)
        righe.append({"finestre": nome, "giorni": len(d), "corr": d["r1"].corr(d["r2"]),
                      "pb continua": segno.mean(), "t": tstat(segno),
                      "anni": anni_concordi(segno)})
    print(pd.DataFrame(righe).set_index("finestre").round(3).to_string())
    print("(pb continua = rendimento della seconda finestra nel verso della prima, in punti base)")


# --------------------------------------------------------------------- F
def sez_f(m1):
    print("\n== F. gap della riapertura settimanale ==")
    t = m1.index.to_series()
    salto = t.diff() > pd.Timedelta("24h")
    idx = np.flatnonzero(salto.values)
    righe = []
    for i in idx:
        chius = m1["close"].iloc[i - 1]
        ap = m1["open"].iloc[i]
        dopo = m1.iloc[i:i + 240]  # le prime 4 ore
        gap = ap - chius
        if abs(gap) < 1e-9:
            continue
        chiuso = (dopo["low"].min() <= chius) if gap > 0 else (dopo["high"].max() >= chius)
        verso = -np.sign(gap) * (dopo["close"].iloc[-1] - ap)
        righe.append({"t": t.iloc[i], "gap": gap, "chiuso4h": chiuso, "verso_chiusura": verso})
    g = pd.DataFrame(righe).set_index("t")
    g.to_parquet(os.path.join(OUT, "f_gap.parquet"))
    for nome, s in (("tutti", g), ("|gap|>=2$", g[g["gap"].abs() >= 2])):
        print(f"{nome:10s} n={len(s):4d} gap mediano {s['gap'].abs().median():.2f}$ "
              f"chiusi entro 4h {s['chiuso4h'].mean():.0%} | movimento verso la chiusura "
              f"{s['verso_chiusura'].mean():+.2f}$ t{tstat(s['verso_chiusura']):+.1f} "
              f"{anni_concordi(s['verso_chiusura'])}")


# --------------------------------------------------------------------- G
def sez_g(m1):
    print(f"\n== G. quanto si muove il prezzo in N minuti (mediana |variazione|, $) "
          f"contro uno spread di {SPREAD_RIF}$ ==")
    c = m1["close"]
    t = m1.index.to_series()
    righe = {}
    for n in (1, 5, 15, 60, 240):
        d = (c.shift(-n) - c).where((t.shift(-n) - t) == pd.Timedelta(minutes=n)).abs()
        righe[f"{n} min"] = d.groupby(d.index.year).median()
    t = pd.DataFrame(righe).T
    t["/spread (2014)"] = t[2014] / SPREAD_RIF
    print(t.round(2).to_string())


def main():
    os.makedirs(OUT, exist_ok=True)
    m1 = carica_m1()
    print(f"periodo caricato: {m1.index.min():%Y-%m-%d} -> {m1.index.max():%Y-%m-%d}",
          file=sys.stderr)
    tfs = {nome: (barre(m1, r), pd.Timedelta(r)) for nome, r in
           (("M1", "1min"), ("M5", "5min"), ("M15", "15min"), ("H1", "1h"), ("H4", "4h"))}
    d1 = barre(m1, "1D")
    sez_a(m1)
    sez_b(tfs["H1"][0])
    sez_c(tfs)
    # D1 a parte: giornate di borsa consecutive (lo spezzone della domenica
    # non conta come giornata, e il lunedi' segue il venerdi')
    d1g = d1[d1.index.dayofweek < 5]
    r = np.log(d1g["close"]).diff().dropna()
    print(f"D1 (giornate di borsa) ac1 {r.autocorr(1):+.3f}, "
          f"anni con ac1<0: {int((r.groupby(r.index.year).apply(lambda x: x.autocorr(1)) < 0).sum())}/6")
    sez_d(tfs)
    sez_e(m1)
    sez_f(m1)
    sez_g(m1)


if __name__ == "__main__":
    main()
