"""Ricerca da zero, famiglia 2: momentum contro ritorno alla media.

Protocollo: docs/ricerca-da-zero-registrazione.md. Piano e varianti dichiarati
in docs/studies/zero/f2-momentum.md (sezione 0) prima del calcolo.

Usa SOLO D:/ricerca_zero/scoperta/ (M5 per i prezzi, D1 per l'ATR).
Fase A: mappa statistica (pendenza NW, coda, pendenza per terzile di volatilita').
Fase B: regole semplici sulle celle consistenti, con costi e placebo.
Dettaglio in D:/ricerca_zero/risultati/f2_fasea.parquet e f2_faseb.parquet.

Uso: python trading/scripts/zero_f2_momentum.py [A|B|AB]
"""
from __future__ import annotations

import gc
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCOP = Path(r"D:/ricerca_zero/scoperta")
RIS = Path(r"D:/ricerca_zero/risultati")
MERCATI = ["XAUUSD", "SPXUSD", "NSXUSD", "XAGUSD", "GRXEUR"]
COSTO = {"XAUUSD": 0.40, "SPXUSD": 0.55, "NSXUSD": 1.50, "GRXEUR": 1.50, "XAGUSD": 0.025}
# orizzonti: nome -> (minuti di calendario se intraday, giorni feriali se giornaliero, minuti di borsa per la scala)
ORIZ = {"5m": (5, 0, 5), "15m": (15, 0, 15), "1h": (60, 0, 60), "4h": (240, 0, 240),
        "1g": (0, 1, 1380), "5g": (0, 5, 6900)}
NOMI = list(ORIZ)
SESS = {"asia": (0, 7), "londra": (7, 12), "ny": (12, 21)}
COPPIE = [(L, H) for L in NOMI for H in NOMI
          if ORIZ[H][2] <= 4 * ORIZ[L][2]]
assert len(COPPIE) == 24
KS = [1.0, 2.0, 3.0]
REGIMI = ["tutti", "basso", "medio", "alto"]
SEED = 20261002
NPLACEBO = 1000
DAY = 1440


# ---------------------------------------------------------------- dati
def carica(sym: str):
    m5 = pd.read_parquet(SCOP / f"{sym}_M5.parquet", columns=["open", "close"])
    m5 = m5[~m5.index.duplicated()].sort_index()
    lab = (m5.index.as_unit("s").asi8 // 60).astype(np.int64)  # minuti epoch
    o = m5["open"].to_numpy(np.float64)
    c = m5["close"].to_numpy(np.float64)
    del m5
    d1 = pd.read_parquet(SCOP / f"{sym}_D1.parquet", columns=["high", "low", "close"])
    d1 = d1[d1.index.dayofweek < 5].sort_index()
    pc = d1["close"].shift(1)
    tr = pd.concat([d1["high"] - d1["low"], (d1["high"] - pc).abs(), (d1["low"] - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().shift(1)            # solo giorni precedenti
    atrp = atr / d1["close"].shift(1)
    pct = atrp.rolling(253, min_periods=253).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True)
    reg = np.where(pct.isna(), -1, np.where(pct < 1 / 3, 0, np.where(pct < 2 / 3, 1, 2)))
    dday = (d1.index.as_unit("s").asi8 // 60) // DAY
    return lab, o, c, dday.astype(np.int64), atr.to_numpy(), reg.astype(np.int8)


def sposta(t: np.ndarray, nome: str, segno: int) -> np.ndarray:
    m, g, _ = ORIZ[nome]
    if g == 0:
        return t + segno * m
    giorno = (t // DAY).astype("datetime64[D]")
    nuovo = np.busday_offset(giorno, segno * g, roll="forward").astype(np.int64)
    return nuovo * DAY + t % DAY


def c_asof(clt, c, T, tol):
    i = np.searchsorted(clt, T, side="right") - 1
    ok = (i >= 0)
    i2 = np.clip(i, 0, len(c) - 1)
    ok &= clt[i2] >= T - tol
    return np.where(ok, c[i2], np.nan)


def o_fwd(lab, o, T, tol):
    i = np.searchsorted(lab, T, side="left")
    ok = i < len(o)
    i2 = np.clip(i, 0, len(o) - 1)
    ok &= lab[i2] <= T + tol
    return np.where(ok, o[i2], np.nan), np.where(ok, lab[i2], -1)


# ---------------------------------------------------------------- statistica
def nw_var(z: np.ndarray, lag: int) -> float:
    v = float(z @ z)
    for j in range(1, lag + 1):
        v += 2 * (1 - j / (lag + 1)) * float(z[:-j] @ z[j:])
    return v


def nw_lag(ts: np.ndarray, tex: np.ndarray) -> int:
    if len(ts) < 2:
        return 0
    k = np.searchsorted(ts, tex, side="left") - np.arange(len(ts)) - 1
    return int(min(max(np.max(k), 0), 400))


def pendenza(x, y, ts, tex):
    n = len(x)
    if n < 30:
        return np.nan, np.nan, n
    xm = x - x.mean()
    sxx = xm @ xm
    b = (xm @ y) / sxx
    e = y - y.mean() - b * xm
    z = xm * e
    se = np.sqrt(max(nw_var(z, nw_lag(ts, tex)), 1e-300)) / sxx
    return b, b / se, n


def media_nw(w, ts, tex):
    n = len(w)
    if n < 30:
        return np.nan, np.nan, n
    m = w.mean()
    se = np.sqrt(max(nw_var(w - m, nw_lag(ts, tex)), 1e-300)) / n
    return m, m / se, n


# ---------------------------------------------------------------- preparazione per mercato
def prepara(sym):
    lab, o, c, dday, atr, reg = carica(sym)
    clt = lab + 5
    t = clt.copy()                                   # istanti di decisione = chiusure M5
    hr = (t % DAY) // 60
    sess = np.full(len(t), -1, np.int8)
    for j, (a, b) in enumerate(SESS.values()):
        sess[(hr >= a) & (hr < b)] = j
    keep = sess >= 0
    t, sess = t[keep], sess[keep]
    k = np.searchsorted(dday, t // DAY, side="right") - 1
    okk = k >= 0
    kk = np.clip(k, 0, len(dday) - 1)
    a_t = np.where(okk, atr[kk], np.nan)
    r_t = np.where(okk, reg[kk], -1).astype(np.int8)
    ent_s, entlab = o_fwd(lab, o, t, 30)
    ent_r = ent_s
    X, Y, YR, TEX, EXLAB = {}, {}, {}, {}, {}
    ct = c_asof(clt, c, t, 0)
    for nm in NOMI:
        Tp = sposta(t, nm, -1)
        tol = min(30, ORIZ[nm][0]) if ORIZ[nm][1] == 0 else 30
        X[nm] = (ct - c_asof(clt, c, Tp, tol)) / (a_t * np.sqrt(ORIZ[nm][2] / 1380))
        Tf = sposta(t, nm, +1)
        TEX[nm] = Tf
        ex_s, _ = o_fwd(lab, o, Tf, 30)
        Y[nm] = (ex_s - ent_s) / (a_t * np.sqrt(ORIZ[nm][2] / 1380))
        ex_r, exl = o_fwd(lab, o, Tf, 4 * DAY)
        YR[nm] = ex_r - ent_r                       # lordo in prezzo, uscita reale
        EXLAB[nm] = exl
    del lab, o, c, clt
    return dict(t=t, sess=sess, reg=r_t, X=X, Y=Y, YR=YR, TEX=TEX, EXLAB=EXLAB, entlab=entlab)


# ---------------------------------------------------------------- fase A
def fase_a(sym, P):
    righe = []
    for L, H in COPPIE:
        step = min(ORIZ[H][0] if ORIZ[H][1] == 0 else 60, 60)
        x0, y0 = P["X"][L], P["Y"][H]
        base = (P["t"] % step == 0) & np.isfinite(x0) & np.isfinite(y0)
        for j, sn in enumerate(SESS):
            m = base & (P["sess"] == j)
            ts, tex = P["t"][m], P["TEX"][H][m]
            x, y = np.clip(x0[m], -10, 10), np.clip(y0[m], -10, 10)
            rg = P["reg"][m]
            r = dict(mercato=sym, L=L, H=H, sessione=sn)
            r["b"], r["t_pend"], r["n"] = pendenza(x, y, ts, tex)
            if len(x) >= 300:
                thr = np.quantile(np.abs(x), 0.9)
                q = np.abs(x) >= thr
                r["coda_m"], r["t_coda"], r["n_coda"] = media_nw(np.sign(x[q]) * y[q], ts[q], tex[q])
            else:
                r["coda_m"], r["t_coda"], r["n_coda"] = np.nan, np.nan, 0
            for g, gn in enumerate(["basso", "medio", "alto"]):
                q = rg == g
                _, r[f"t_{gn}"], _ = pendenza(x[q], y[q], ts[q], tex[q])
            righe.append(r)
    return righe


# ---------------------------------------------------------------- fase B
def regola(P, sym, L, H, sn, k, regime, segno, rng_seed=SEED):
    j = list(SESS).index(sn)
    step = min(ORIZ[L][0] if ORIZ[L][1] == 0 else 60, 60)
    x, g = P["X"][L], P["YR"][H]
    m = (P["t"] % step == 0) & (P["sess"] == j) & np.isfinite(x) & np.isfinite(g) & (np.abs(x) >= k)
    if regime != "tutti":
        m &= P["reg"] == REGIMI.index(regime) - 1
    idx = np.flatnonzero(m)
    if len(idx) == 0:
        return None
    ts, exl = P["t"][idx], P["EXLAB"][H][idx]
    pres = []
    i = 0
    while i < len(idx):
        pres.append(i)
        i = int(np.searchsorted(ts, exl[i], side="left"))
        if i <= pres[-1]:
            i = pres[-1] + 1
    pres = np.asarray(pres)
    sel = idx[pres]
    d = np.sign(P["X"][L][sel]) * segno
    lordo = d * g[sel]
    netto = lordo - COSTO[sym]
    n = len(netto)
    anni = pd.Series(netto).groupby((P["t"][sel] // DAY).astype("datetime64[D]").astype("datetime64[Y]")).sum()
    sd = netto.std(ddof=1) if n > 1 else np.nan
    tt = netto.mean() / sd * np.sqrt(n) if n > 1 and sd > 0 else np.nan
    # robustezza: senza l'1% di operazioni piu' estreme (per |lordo|)
    if n >= 100:
        cut = np.quantile(np.abs(lordo), 0.99)
        nr = netto[np.abs(lordo) <= cut]
        t_rob = nr.mean() / nr.std(ddof=1) * np.sqrt(len(nr))
    else:
        t_rob = np.nan
    r = dict(mercato=sym, L=L, H=H, sessione=sn, k=k, regime=regime,
             direzione="a favore" if segno > 0 else "contro", n=n,
             netto=netto.mean(), netto_costi=netto.mean() / COSTO[sym], lordo=lordo.mean(),
             t=tt, t_rob=t_rob, anni_pos=int((anni > 0).sum()), anni=len(anni),
             quota_anni=(anni > 0).mean(), p_placebo=np.nan)
    if n >= 30 and tt >= 2 and r["netto"] > 0:
        rng = np.random.default_rng(rng_seed)
        cnt = 0
        for _ in range(NPLACEBO // 100):
            s = rng.choice(np.array([-1.0, 1.0]), size=(100, n))
            pm = (s * g[sel][None, :]).mean(axis=1) - COSTO[sym]
            cnt += int((pm >= r["netto"]).sum())
        r["p_placebo"] = (cnt + 1) / (NPLACEBO + 1)
    return r


def selezione(A: pd.DataFrame) -> pd.DataFrame:
    s = A[(A["t_pend"].abs() >= 2) | (A["t_coda"].abs() >= 2)].copy()
    s["segno"] = np.where(s["t_coda"].abs() >= 2, np.sign(s["t_coda"]), np.sign(s["t_pend"])).astype(int)
    return s


def main(fasi: str):
    RIS.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)
    fa, fb = RIS / "f2_fasea.parquet", RIS / "f2_faseb.parquet"
    if "A" in fasi:
        righe = []
        for sym in MERCATI:
            P = prepara(sym)
            righe += fase_a(sym, P)
            del P
            gc.collect()
            print(f"fase A {sym} ok", flush=True)
        pd.DataFrame(righe).to_parquet(fa)
    A = pd.read_parquet(fa)
    print(f"Fase A: {len(A)} celle, {5 * len(A)} test; |t_pend|>=3: {(A.t_pend.abs() >= 3).sum()}, "
          f"|t_coda|>=3: {(A.t_coda.abs() >= 3).sum()}")
    if "B" in fasi:
        S = selezione(A)
        print(f"Celle selezionate: {len(S)} -> varianti regola {12 * len(S)}", flush=True)
        righe = []
        for sym in MERCATI:
            Ss = S[S.mercato == sym]
            if Ss.empty:
                continue
            P = prepara(sym)
            for _, c in Ss.iterrows():
                for k in KS:
                    for rg in REGIMI:
                        r = regola(P, sym, c.L, c.H, c.sessione, k, rg, int(c.segno))
                        if r is None:
                            r = dict(mercato=sym, L=c.L, H=c.H, sessione=c.sessione, k=k, regime=rg,
                                     direzione="a favore" if c.segno > 0 else "contro", n=0)
                        righe.append(r)
            del P
            gc.collect()
            print(f"fase B {sym} ok", flush=True)
        pd.DataFrame(righe).to_parquet(fb)
    if fb.exists():
        B = pd.read_parquet(fb)
        lento = B.L.isin(["1g", "5g"]) | B.H.isin(["1g", "5g"])
        nmin = np.where(lento, 100, 200)
        B["promossa"] = (B.netto > 0) & (B.t >= 3) & (B.quota_anni >= 0.75) & (B.p_placebo < 0.01) & (B.n >= nmin)
        B.to_parquet(fb)
        print(f"Fase B: {len(B)} varianti; netto>0: {(B.netto > 0).sum()}; t>=3: {(B.t >= 3).sum()}; "
              f"promosse: {B.promossa.sum()}")
        cols = ["mercato", "L", "H", "sessione", "k", "regime", "direzione", "n", "netto", "netto_costi",
                "t", "t_rob", "anni_pos", "anni", "p_placebo", "promossa"]
        print(B.sort_values("t", ascending=False)[cols].head(12).round(3).to_string(index=False))


def tabelle():
    """Tabelle markdown per il rapporto (scritte su file, non stampate)."""
    A = pd.read_parquet(RIS / "f2_fasea.parquet")
    B = pd.read_parquet(RIS / "f2_faseb.parquet")

    def simb(t):
        if not np.isfinite(t):
            return "x"
        return "++" if t >= 3 else "+" if t >= 2 else "--" if t <= -3 else "-" if t <= -2 else "."
    out = ["| L -> H | " + " | ".join(MERCATI) + " |", "|---|" + "---|" * len(MERCATI)]
    for L, H in COPPIE:
        cel = []
        for m in MERCATI:
            q = A[(A.mercato == m) & (A.L == L) & (A.H == H)].set_index("sessione")
            cel.append(" ".join(simb(q.loc[sn, "t_pend"]) for sn in SESS))
        out.append(f"| {L} -> {H} | " + " | ".join(cel) + " |")
    cols = ["mercato", "L", "H", "sessione", "k", "regime", "direzione", "n", "netto", "netto_costi",
            "t", "t_rob", "anni_pos", "anni", "p_placebo"]
    top = B[B.n >= 30].sort_values("t", ascending=False)[cols].head(10).round(3)
    out += ["", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(v) for v in r) + " |" for r in top.itertuples(index=False)]
    (RIS / "f2_tabelle.md").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "R":
        tabelle()
        sys.exit()
    main(sys.argv[1] if len(sys.argv) > 1 else "AB")
