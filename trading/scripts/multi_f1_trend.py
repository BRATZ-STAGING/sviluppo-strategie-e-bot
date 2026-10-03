#!/usr/bin/env python3
"""Famiglia 1 — trend following sul paniere di 12 mercati, regole canoniche.

Protocollo: docs/multigiorno-paniere-registrazione.md; regole dichiarate in
docs/studies/multi/f1-trend.md PRIMA del calcolo. Solo scoperta 2010-2017:

    D:\\ricerca_multi\\scoperta\\PANIERE_D1.parquet   (giornate 22->22 UTC)
    D:\\ricerca_multi\\costi.csv                      (round trip, prezzo)

Decisione alla chiusura D1, esecuzione all'apertura della giornata valida
successiva; 1R per operazione in ogni mercato; costi di transazione + swap
(3%/365 del nominale, oro listino FP riscalato, x3 il mercoledi'); R del
portafoglio giorno per giorno (mark-to-market), sommato per mese.

Scrive il dettaglio in D:\\ricerca_multi\\risultati\\f1_*.parquet e stampa
solo aggregati compatti.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

PAN = r"D:\ricerca_multi\scoperta\PANIERE_D1.parquet"
COSTI = r"D:\ricerca_multi\costi.csv"
OUT = r"D:\ricerca_multi\risultati"
INIZIO = pd.Timestamp("2010-01-01")
SWAP_ANNUO = 0.03
ORO_L, ORO_S, ORO_P = 0.715, 0.325, 4156.98
N_PLACEBO, SEED = 2000, 12345
REGOLE = ["TSMOM1", "TSMOM3", "TSMOM12", "DON20/10", "DON55/20",
          "MA50/200", "MA50/200S"]
ORO = "XAUUSD"

pd.set_option("display.width", 200)


# ---------------------------------------------------------------- indicatori
def indicatori(g: pd.DataFrame) -> dict:
    o, h, l, c = (g[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    pc = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(pc), h - l,
                  np.maximum(h, pc) - np.minimum(l, pc))
    s = pd.Series(c)
    return {
        "o": o, "h": h, "l": l, "c": c, "date": g["giorno"].to_numpy(),
        "atr": pd.Series(tr).rolling(20).mean().to_numpy(),
        "sig": s.diff().rolling(60).std().to_numpy(),
        "sma50": s.rolling(50).mean().to_numpy(),
        "sma200": s.rolling(200).mean().to_numpy(),
    }


def canale(x, n, f):
    """Massimo/minimo delle n giornate PRECEDENTI (esclusa quella corrente)."""
    r = pd.Series(x).rolling(n)
    return (r.max() if f == "max" else r.min()).shift(1).to_numpy()


# ---------------------------------------------------------------- motori
def _ok_entrata(d, t):
    return pd.Timestamp(d["date"][t]) >= INIZIO


def sim_stop(d, segnale_entrata, segnale_uscita, con_stop=True):
    """Motore comune Donchian / medie con stop.

    segnale_entrata(t) -> +1/-1/0 alla chiusura t (con R in prezzo);
    segnale_uscita(t, pos) -> True se alla chiusura t si esce.
    Restituisce operazioni (i0, E, i1, X, dir, Rp, tipo).
    """
    o, h, l, c, atr = d["o"], d["h"], d["l"], d["c"], d["atr"]
    N = len(c)
    ops = []
    pos, E, i0, stop, Rp = 0, 0.0, 0, 0.0, 0.0
    pend = None  # (uscire: bool, nuovo verso, Rp)
    for t in range(N):
        if pend is not None:
            esci, nv, nR = pend
            pend = None
            if esci and pos != 0:
                ops.append((i0, E, t, o[t], pos, Rp, "segnale"))
                pos = 0
            if nv != 0 and pos == 0 and _ok_entrata(d, t):
                pos, E, i0, Rp = nv, o[t], t, nR
                stop = E - pos * Rp
        if pos != 0 and con_stop:
            if t > i0 and (o[t] - stop) * pos <= 0:
                ops.append((i0, E, t, o[t], pos, Rp, "gap"))
                pos = 0
            elif (pos == 1 and l[t] <= stop) or (pos == -1 and h[t] >= stop):
                ops.append((i0, E, t, stop, pos, Rp, "stop"))
                pos = 0
        if t == N - 1:
            if pos != 0:
                ops.append((i0, E, t, c[t], pos, Rp, "fine"))
            break
        if not np.isfinite(atr[t]) or atr[t] <= 0:
            continue
        nv = segnale_entrata(t)
        if pos != 0:
            if segnale_uscita(t, pos):
                pend = (True, nv if nv == -pos else 0, 2 * atr[t])
        elif nv != 0:
            pend = (False, nv, 2 * atr[t])
    return ops


def sim_donchian(d, n_in, n_out):
    c = d["c"]
    hi_in, lo_in = canale(d["h"], n_in, "max"), canale(d["l"], n_in, "min")
    hi_out, lo_out = canale(d["h"], n_out, "max"), canale(d["l"], n_out, "min")

    def ent(t):
        if not np.isfinite(hi_in[t]):
            return 0
        return 1 if c[t] > hi_in[t] else (-1 if c[t] < lo_in[t] else 0)

    def usc(t, pos):
        return (c[t] < lo_out[t]) if pos == 1 else (c[t] > hi_out[t])
    return sim_stop(d, ent, usc)


def _stato_ma(d):
    s = np.sign(d["sma50"] - d["sma200"])
    s[~np.isfinite(s)] = 0
    return s.astype(int)


def sim_ma_stop(d):
    s = _stato_ma(d)

    def ent(t):  # incrocio: cambio di stato fra t-1 e t
        if t == 0 or s[t] == 0 or s[t - 1] == 0 or s[t] == s[t - 1]:
            return 0
        return int(s[t])

    def usc(t, pos):
        return ent(t) == -pos
    return sim_stop(d, ent, usc)


def sim_ma_sempre(d):
    s = _stato_ma(d)

    def ent(t):
        return int(s[t])

    def usc(t, pos):
        return s[t] == -pos
    return sim_stop(d, ent, usc, con_stop=False)


def sim_tsmom(d, k):
    c, o, sig = d["c"], d["o"], d["sig"]
    dt = pd.DatetimeIndex(d["date"])
    mese = dt.year * 12 + dt.month
    fm = np.flatnonzero(np.r_[mese[1:] != mese[:-1], True])  # fine mese
    N = len(c)
    ops = []
    for j in range(k, len(fm) - 1):
        t = fm[j]
        if t + 1 >= N or not np.isfinite(sig[t]) or sig[t] <= 0:
            continue
        r = c[t] / c[fm[j - k]] - 1
        if r == 0 or not _ok_entrata(d, t + 1):
            continue
        i0, t2 = t + 1, fm[j + 1]
        if t2 + 1 < N:
            i1, X, tipo = t2 + 1, o[t2 + 1], "ribil"
        else:
            i1, X, tipo = t2, c[t2], "fine"
        ops.append((i0, o[i0], i1, X, int(np.sign(r)), 2 * sig[t], tipo))
    return ops


SIM = {
    "TSMOM1": lambda d: sim_tsmom(d, 1),
    "TSMOM3": lambda d: sim_tsmom(d, 3),
    "TSMOM12": lambda d: sim_tsmom(d, 12),
    "DON20/10": lambda d: sim_donchian(d, 20, 10),
    "DON55/20": lambda d: sim_donchian(d, 55, 20),
    "MA50/200": sim_ma_sempre,
    "MA50/200S": sim_ma_stop,
}


# ---------------------------------------------------------------- contabilita'
def calendario_swap(d, mercato):
    """Calendario lun-ven del mercato e swap cumulato per unita' (L, S)."""
    dt = pd.DatetimeIndex(d["date"])
    B = pd.bdate_range(dt[0], dt[-1])
    cf = pd.Series(d["c"], index=dt).reindex(B).ffill().to_numpy()
    molt = np.where(B.dayofweek == 2, 3.0, 1.0)
    if mercato == ORO:
        sl = molt * ORO_L / ORO_P * cf
        ss = -molt * ORO_S / ORO_P * cf      # lo short incassa
    else:
        sl = molt * SWAP_ANNUO / 365 * cf
        ss = sl.copy()
    return B, sl, ss


def contabilizza(d, mercato, ops, costo):
    B, sl, ss = calendario_swap(d, mercato)
    pos_b = B.get_indexer(pd.DatetimeIndex(d["date"]))
    nb = len(B)
    gross = np.zeros(nb)
    cst = np.zeros(nb)
    swp = np.zeros(nb)
    righe = []
    c = d["c"]
    for (i0, E, i1, X, dr, Rp, tipo) in ops:
        seq = np.r_[E, c[i0:i1], X]
        g = dr * np.diff(seq) / Rp
        gross[pos_b[i0:i1 + 1]] += g
        cR = costo / Rp
        cst[pos_b[i0]] += cR / 2
        cst[pos_b[i1]] += cR / 2
        a, b = pos_b[i0], pos_b[i1]
        swL = sl[a:b] / Rp
        swS = ss[a:b] / Rp
        swp[a:b] += swL if dr == 1 else swS
        righe.append({
            "mercato": mercato, "entrata": d["date"][i0],
            "uscita": d["date"][i1], "verso": dr, "E": E, "X": X,
            "R_prezzo": Rp, "tipo": tipo, "giorni": i1 - i0,
            "u": (X - E) / Rp, "lordo": dr * (X - E) / Rp, "costo": cR,
            "swapL": swL.sum(), "swapS": swS.sum(),
        })
    t = pd.DataFrame(righe)
    if len(t):
        t["swap"] = np.where(t["verso"] == 1, t["swapL"], t["swapS"])
        t["netto"] = t["lordo"] - t["costo"] - t["swap"]
    gio = pd.DataFrame({"lordo": gross, "costo": cst, "swap": swp}, index=B)
    gio["mercato"] = mercato
    return t, gio


# ---------------------------------------------------------------- misure
def tstat(x):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return np.nan
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x))


def misure(ops, gio, rng_seed):
    """Misure del portafoglio (ops e serie giornaliera gia' filtrate)."""
    gp = gio.groupby(level=0)[["lordo", "costo", "swap"]].sum().sort_index()
    gp = gp[gp.index >= INIZIO]
    net1 = gp["lordo"] - gp["costo"] - gp["swap"]
    net15 = gp["lordo"] - 1.5 * gp["costo"] - gp["swap"]
    net0 = gp["lordo"] - gp["costo"]          # diagnostica: senza swap
    primo = ops["entrata"].min()
    mesi = pd.period_range(pd.Timestamp(primo).to_period("M"), "2017-12", freq="M")
    m1 = net1.groupby(net1.index.to_period("M")).sum().reindex(mesi, fill_value=0)
    m15 = net15.groupby(net15.index.to_period("M")).sum().reindex(mesi, fill_value=0)
    m0 = net0.groupby(net0.index.to_period("M")).sum().reindex(mesi, fill_value=0)
    anni = net1.groupby(net1.index.year).sum()
    anni = anni[anni.index >= pd.Timestamp(primo).year]
    eq = net1.cumsum()
    dd = (eq.cummax().clip(lower=0) - eq).max()
    # placebo: stesse entrate/uscite, verso a caso
    rng = np.random.default_rng(rng_seed)
    u = ops["u"].to_numpy()
    s = rng.choice(np.array([-1.0, 1.0]), size=(N_PLACEBO, len(u)))
    pl = (s @ u - ops["costo"].sum()
          - np.where(s > 0, ops["swapL"].to_numpy(), ops["swapS"].to_numpy()).sum(1))
    reale = ops["netto"].sum()
    p = (1 + (pl >= reale).sum()) / (N_PLACEBO + 1)
    sempre_long = (u - ops["costo"] - ops["swapL"]).sum()
    assert abs(net1.sum() - reale) < 1e-6 * max(1, abs(reale)), (net1.sum(), reale)
    return {
        "n": len(ops), "mesi": len(mesi), "op_mese": len(ops) / len(mesi),
        "lordo": ops["lordo"].sum(), "costo": ops["costo"].sum(),
        "swap": ops["swap"].sum(), "netto": reale,
        "netto_op": reale / len(ops), "netto_x15": m15.sum(),
        "t": tstat(m1), "t_x15": tstat(m15),
        "anni_pos": int((anni > 0).sum()), "anni": len(anni),
        "dd": dd, "vinte": (ops["netto"] > 0).mean(), "p": p,
        "placebo_med": np.median(pl), "netto_noswap": m0.sum(),
        "t_noswap": tstat(m0), "long_stessi_ist": sempre_long,
    }, m1, anni


def passa(r):
    return (r["netto"] > 0 and r["netto_x15"] > 0 and r["t"] >= 2
            and r["anni_pos"] >= 5 and r["p"] < 0.05)


# ---------------------------------------------------------------- main
def main():
    os.makedirs(OUT, exist_ok=True)
    pan = pd.read_parquet(PAN)
    pan = pan[pan["valida"]].sort_values(["mercato", "giorno"])
    costi = pd.read_csv(COSTI).set_index("mercato")["costo_rt"]
    mercati = list(costi.index)
    dati = {m: indicatori(pan[pan["mercato"] == m].reset_index(drop=True))
            for m in mercati}

    tutte_ops, tutte_gio, ris, mensili, annuali = [], [], [], {}, {}
    for k, regola in enumerate(REGOLE):
        ops_r, gio_r = [], []
        for m in mercati:
            t, g = contabilizza(dati[m], m, SIM[regola](dati[m]), costi[m])
            t["regola"] = regola
            g["regola"] = regola
            ops_r.append(t)
            gio_r.append(g)
        ops_r = pd.concat(ops_r, ignore_index=True)
        gio_r = pd.concat(gio_r)
        tutte_ops.append(ops_r)
        tutte_gio.append(gio_r)
        for paniere, filtro in (("12", lambda x: x), ("senza oro",
                                lambda x: x[x["mercato"] != ORO])):
            r, m1, anni = misure(filtro(ops_r), filtro(gio_r), SEED + k)
            r.update({"regola": regola, "paniere": paniere})
            r["passa"] = passa(r)
            ris.append(r)
            mensili[(regola, paniere)] = m1
            annuali[(regola, paniere)] = anni

    ops = pd.concat(tutte_ops, ignore_index=True)
    gio = pd.concat(tutte_gio)
    ris = pd.DataFrame(ris)
    ops.to_parquet(os.path.join(OUT, "f1_operazioni.parquet"))
    gio.reset_index(names="giorno").to_parquet(os.path.join(OUT, "f1_giornaliero.parquet"))
    ris.to_parquet(os.path.join(OUT, "f1_riepilogo.parquet"))
    mm = pd.DataFrame({f"{a}|{b}": v.astype(float) for (a, b), v in mensili.items()})
    mm.index = mm.index.astype(str)
    mm.to_parquet(os.path.join(OUT, "f1_mensile.parquet"))
    aa = pd.DataFrame({f"{a}|{b}": v for (a, b), v in annuali.items()})
    aa.to_parquet(os.path.join(OUT, "f1_annuale.parquet"))

    # contributo per mercato
    contr = ops.pivot_table(index="mercato", columns="regola", values="netto",
                            aggfunc="sum")[REGOLE]
    nmerc = ops.pivot_table(index="mercato", columns="regola", values="netto",
                            aggfunc="size")[REGOLE]
    swm = ops.pivot_table(index="mercato", columns="regola", values="swap",
                          aggfunc="sum")[REGOLE]
    gm = gio[gio.index >= INIZIO].copy()
    gm["net"] = gm["lordo"] - gm["costo"] - gm["swap"]
    gm["mese"] = gm.index.to_period("M")
    tm = (gm.groupby(["regola", "mercato", "mese"])["net"].sum()
          .groupby(["regola", "mercato"]).apply(tstat).unstack(0)[REGOLE])
    contr.to_parquet(os.path.join(OUT, "f1_contributo_mercato.parquet"))

    # controlli
    don = ops[ops["regola"].str.startswith("DON") | (ops["regola"] == "MA50/200S")]
    peggio_stop = don.loc[don["tipo"] == "stop", "lordo"].min()

    cols = ["regola", "paniere", "n", "op_mese", "lordo", "costo", "swap",
            "netto", "netto_op", "netto_x15", "t", "anni_pos", "anni", "dd",
            "p", "passa"]
    print(ris[cols].round(3).to_string(index=False))
    print(ris[["regola", "paniere", "vinte", "placebo_med", "long_stessi_ist",
               "netto_noswap", "t_noswap", "t_x15"]].round(3).to_string(index=False))
    print("\nnetto R per mercato (x1):")
    print(contr.round(1).to_string())
    print("\nt mensile per mercato:")
    print(tm.round(2).to_string())
    print("\nn operazioni per mercato:")
    print(nmerc.to_string())
    print("\nswap R per mercato:")
    print(swm.round(1).to_string())
    print("\nanni (12 mercati):")
    print(pd.DataFrame({r: annuali[(r, "12")] for r in REGOLE}).round(1).T.to_string())
    print("\nanni (senza oro):")
    print(pd.DataFrame({r: annuali[(r, "senza oro")] for r in REGOLE}).round(1).T.to_string())
    print(f"\ncontrolli: lordo minimo uscite 'stop' = {peggio_stop:.4f} (atteso -1)")
    print("tipi di uscita:", ops.groupby(["regola", "tipo"]).size().unstack(fill_value=0).to_string())
    print("prima entrata per mercato:", ops.groupby("mercato")["entrata"].min().dt.date.astype(str).to_dict())


if __name__ == "__main__":
    main()
