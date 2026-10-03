#!/usr/bin/env python3
"""Famiglia 3 — forza relativa fra mercati (momentum trasversale), scoperta.

Protocollo: docs/multigiorno-paniere-registrazione.md; griglia e regole
dichiarate in docs/studies/multi/f3-forza.md PRIMA del calcolo.

Dati: SOLO D:\\ricerca_multi\\scoperta\\PANIERE_D1.parquet e
D:\\ricerca_multi\\costi.csv. Dettaglio in D:\\ricerca_multi\\risultati\\.

Uso:  python multi_f3_forza.py            (griglia completa + placebo)
      python multi_f3_forza.py --rapido   (senza placebo)
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)

DATI = r"D:\ricerca_multi\scoperta\PANIERE_D1.parquet"
COSTI = r"D:\ricerca_multi\costi.csv"
OUT = r"D:\ricerca_multi\risultati"

CAMBI = ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "EURJPY"]
MI = ["XAUUSD", "XAGUSD", "SPXUSD", "NSXUSD", "GRXEUR"]
TUTTI = MI + CAMBI
UNIVERSI = {"TUTTI": (TUTTI, (2, 3)), "CAMBI": (CAMBI, (2, 3)), "MI": (MI, (1, 2))}
FINESTRE = [("1s", 5, 0), ("1m", 21, 0), ("1m", 21, 5), ("3m", 63, 0), ("3m", 63, 21),
            ("6m", 126, 0), ("6m", 126, 21), ("12m", 252, 0), ("12m", 252, 21)]
BREVI = {("1s", 0), ("1m", 0), ("1m", 5)}
INIZIO, FINE = pd.Timestamp("2010-01-01"), pd.Timestamp("2017-12-31")
SWAP_ANNUO = 0.03
ORO_LONG, ORO_SHORT, ORO_RIF = -0.715, 0.325, 4156.98
N_PLAC, SEED, BLOCCO = 1000, 12345, 250


def carica():
    d = pd.read_parquet(DATI)
    d = d[d["valida"]]
    costi = pd.read_csv(COSTI).set_index("mercato")["costo_rt"]
    cal = pd.DatetimeIndex(sorted(d["giorno"].unique()))
    cal = cal[cal.dayofweek < 5]
    serie = {}
    for m in TUTTI:
        g = d[d["mercato"] == m].set_index("giorno").sort_index()
        c = g["close"]
        lr = np.log(c).diff()
        sig = lr.rolling(60).std()
        sigp = c.diff().rolling(60).std()
        punt = {}
        for nome, L, s in FINESTRE:
            r = np.log(c.shift(s)) - np.log(c.shift(L))
            punt[(nome, s)] = (r / sig).reindex(cal, method="ffill", limit=5)
        serie[m] = dict(
            open=g["open"].reindex(cal).bfill(limit=5),
            close=c.reindex(cal, method="ffill", limit=5),
            ru=(2 * sigp).reindex(cal, method="ffill", limit=5),
            punt=punt)
    return cal, serie, costi


def istanti(cal, freq):
    """Indici (nel calendario) dei giorni di segnale e di esecuzione."""
    s = pd.Series(np.arange(len(cal)), index=cal)
    chiave = cal.to_period("W-FRI") if freq == "W" else cal.to_period("M")
    seg = s.groupby(chiave).max().values
    seg = seg[seg + 1 < len(cal)]
    ese = seg + 1
    tieni = (cal[ese] >= INIZIO) & (cal[ese] <= FINE)
    return seg[tieni], ese[tieni]


def prepara(cal, serie, costi, mercati, freq):
    """Matrici (periodi x mercati) per un universo e una frequenza."""
    seg, ese = istanti(cal, freq)
    # periodo p: da ese[p] a ese[p+1]; l'ultimo ribilanciamento non ha periodo
    seg, e0, e1 = seg[:-1], ese[:-1], ese[1:]
    P, M = len(seg), len(mercati)
    op = np.column_stack([serie[m]["open"].values for m in mercati])
    cl = np.column_stack([serie[m]["close"].values for m in mercati])
    ru = np.column_stack([serie[m]["ru"].values for m in mercati])[seg]
    dP = op[e1] - op[e0]
    pe = op[e0]
    # notti: fine di ogni giorno di calendario da e0 a e1-1, mercoledi' x3
    peso = np.where(cal.dayofweek == 2, 3.0, 1.0)
    cum = np.concatenate([[0.0], np.cumsum(peso)])
    notti = (cum[e1] - cum[e0])[:, None]
    swL = np.empty((P, M))
    swS = np.empty((P, M))
    for j, m in enumerate(mercati):
        if m == "XAUUSD":
            swL[:, j] = ORO_LONG * pe[:, j] / ORO_RIF * notti[:, 0]
            swS[:, j] = ORO_SHORT * pe[:, j] / ORO_RIF * notti[:, 0]
        else:
            swL[:, j] = -SWAP_ANNUO / 365 * pe[:, j] * notti[:, 0]
            swS[:, j] = swL[:, j]
    cst = np.array([costi[m] for m in mercati])
    ok_base = np.isfinite(dP) & np.isfinite(ru) & (ru > 0) & np.isfinite(pe)
    punt = {}
    for nome, L, s in FINESTRE:
        sc = np.column_stack([serie[m]["punt"][(nome, s)].values for m in mercati])[seg]
        sc = np.where(ok_base & np.isfinite(sc), sc, np.nan)
        punt[(nome, s)] = sc
    dP = np.where(ok_base, dP, 0.0)
    ru = np.where(ok_base, ru, 1.0)
    swL = np.where(ok_base, swL, 0.0)
    swS = np.where(ok_base, swS, 0.0)
    return dict(date=cal[e0], dP=dP, ru=ru, swL=swL, swS=swS, cst=cst,
                punt=punt, P=P, M=M, cl=cl)


def direzioni(sc, k, modo, contro):
    """sc (..., P, M) con NaN = non disponibile -> D in {-1, 0, 1}."""
    disp = np.isfinite(sc)
    nd = disp.sum(-1, keepdims=True)
    alto = np.where(disp, sc, -np.inf)
    basso = np.where(disp, sc, np.inf)
    r_alto = np.argsort(np.argsort(-alto, axis=-1, kind="stable"), axis=-1)
    r_basso = np.argsort(np.argsort(basso, axis=-1, kind="stable"), axis=-1)
    ok = nd >= 2 * k
    primi = (r_alto < k) & disp & ok
    ultimi = (r_basso < k) & disp & ok
    if contro:
        lng, sht = ultimi, primi
    else:
        lng, sht = primi, ultimi
    D = np.zeros(sc.shape, dtype=np.int8)
    if modo in ("LS", "L"):
        D = D + lng.astype(np.int8)
    if modo in ("LS", "S"):
        D = D - sht.astype(np.int8)
    return D


def simula(D, X):
    """Restituisce (lordo prezzo, swap, costo x1) in R per periodo e mercato."""
    P, M = X["P"], X["M"]
    prev = np.zeros_like(D)
    prev[..., 1:, :] = D[..., :-1, :]
    nuova = (D != 0) & (D != prev)
    idx = np.where(nuova, np.arange(P)[:, None], 0)
    idx = np.maximum.accumulate(idx, axis=-2)
    ru = X["ru"][idx, np.arange(M)]
    Df = D.astype(float)
    prezzo = Df * X["dP"] / ru
    swap = np.where(D > 0, X["swL"], np.where(D < 0, X["swS"], 0.0)) / ru
    costo = nuova * X["cst"] / ru
    return prezzo, swap, costo, nuova


def drawdown(x):
    c = np.cumsum(x)
    return float(np.max(np.maximum.accumulate(np.concatenate([[0.0], c]))[1:] - c))


def statistiche(D, X):
    prezzo, swap, costo, nuova = simula(D, X)
    lordo_p = (prezzo + swap).sum(1)
    netto1 = lordo_p - costo.sum(1)
    netto15 = lordo_p - 1.5 * costo.sum(1)
    attivo = (D != 0).sum(1) > 0
    if not attivo.any():
        return None, None
    primo = np.argmax(attivo)
    date = X["date"]
    mesi_idx = pd.period_range(date[primo].to_period("M"), "2017-12", freq="M")
    df = pd.DataFrame({"mese": date.to_period("M"), "n1": netto1, "n15": netto15,
                       "lordo": lordo_p, "swap": swap.sum(1)})
    df = df.iloc[primo:]
    mm = df.groupby("mese")[["n1", "n15", "lordo", "swap"]].sum().reindex(mesi_idx, fill_value=0.0)
    n_mesi = len(mm)
    t = mm["n1"].mean() / mm["n1"].std(ddof=1) * np.sqrt(n_mesi) if mm["n1"].std() > 0 else 0.0
    anni = mm["n1"].groupby(mm.index.year).sum()
    n_ent = int(nuova.sum())
    ris = dict(
        mesi=n_mesi, anni_n=len(anni), anni_pos=int((anni > 0).sum()),
        pos_medie=float((D[primo:] != 0).sum(1).mean()),
        entrate_mese=n_ent / n_mesi,
        netto_R=float(netto1.sum()), netto15_R=float(netto15.sum()),
        lordo_R=float(lordo_p.sum()), swap_R=float(swap.sum()),
        costo_R=float(costo.sum()),
        netto_per_op=float(netto1.sum()) / max(n_ent, 1),
        netto_mese=float(mm["n1"].mean()), t=float(t),
        t15=float(mm["n15"].mean() / mm["n15"].std(ddof=1) * np.sqrt(n_mesi)),
        dd_R=drawdown(netto1[primo:]), entrate=n_ent)
    return ris, mm


def placebo(sc, k, modo, contro, X, seed):
    rng = np.random.default_rng(seed)
    disp = np.isfinite(sc)
    tot = []
    for i in range(0, N_PLAC, BLOCCO):
        n = min(BLOCCO, N_PLAC - i)
        r = rng.random((n,) + sc.shape)
        r = np.where(disp, r, np.nan)
        D = direzioni(r, k, modo, False)
        prezzo, swap, _, _ = simula(D, X)
        tot.append((prezzo + swap).sum((-1, -2)))
    return np.concatenate(tot)


def main():
    rapido = "--rapido" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    cal, serie, costi = carica()
    righe, mensili = [], {}
    vid = 0
    for uni, (mercati, ks) in UNIVERSI.items():
        for freq in ("W", "M"):
            X = prepara(cal, serie, costi, mercati, freq)
            for k in ks:
                for nome, L, s in FINESTRE:
                    modi = [(m, False) for m in ("LS", "L", "S")]
                    if (nome, s) in BREVI:
                        modi += [(m, True) for m in ("LS", "L", "S")]
                    for modo, contro in modi:
                        sc = X["punt"][(nome, s)]
                        D = direzioni(sc, k, modo, contro)
                        ris, mm = statistiche(D, X)
                        sk = "0" if s == 0 else ("1s" if s == 5 else "1m")
                        reg = f"{uni} {freq} {nome}/{sk} {'CONTRO' if contro else 'MOM'}-{modo} k{k}"
                        if ris is None:
                            vid += 1
                            continue
                        if not rapido:
                            pl = placebo(sc, k, modo, contro, X, SEED + vid)
                            ris["p"] = (1 + int((pl >= ris["lordo_R"]).sum())) / (N_PLAC + 1)
                            ris["plac_medio_R"] = float(pl.mean())
                        else:
                            ris["p"] = np.nan
                            ris["plac_medio_R"] = np.nan
                        ris.update(regola=reg, universo=uni, freq=freq, k=k, finestra=nome,
                                   salto=sk, tipo="CONTRO" if contro else "MOM", modo=modo, vid=vid)
                        righe.append(ris)
                        mensili[reg] = mm["n1"]
                        vid += 1
            print(f"{uni} {freq} fatto, {vid} varianti, {time.time() - t0:.0f}s", flush=True)
    r = pd.DataFrame(righe)
    r["promossa"] = ((r["netto_R"] > 0) & (r["netto15_R"] > 0) & (r["t"] >= 3)
                     & (r["anni_pos"] >= 6) & (r["p"] < 0.01))
    suff = "_rapido" if rapido else ""
    r.to_parquet(os.path.join(OUT, f"f3_varianti{suff}.parquet"))
    pd.DataFrame(mensili).to_parquet(os.path.join(OUT, f"f3_mensili{suff}.parquet"))
    print(f"varianti valutate: {len(r)} (indice max {vid}); tempo {time.time() - t0:.0f}s")
    print(f"netto>0: {(r.netto_R > 0).sum()}, t>=3: {(r.t >= 3).sum()}, t>=2: {(r.t >= 2).sum()}, "
          f"t<=-2: {(r.t <= -2).sum()}, p<0,01: {(r.p < 0.01).sum()}, promosse: {r.promossa.sum()}")
    col = ["regola", "pos_medie", "entrate_mese", "netto_per_op", "netto_R", "netto15_R",
           "swap_R", "t", "anni_pos", "anni_n", "dd_R", "p"]
    print(r.sort_values("t", ascending=False)[col].head(15).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
