"""Famiglia 3 FX: ritorno alla media e momentum di breve (5-60 minuti).

Protocollo: docs/fx-intraday-registrazione.md. Rapporto: docs/studies/fx/c-media-momentum.md.
Dati SOLO D:/ricerca_fx/scoperta (2010-2017). Una coppia alla volta, niente multiprocessing.

Uso:
  python fx_c_media_momentum.py calcola [COPPIA ...]   # fase A + fase B per coppia (salta se gia' fatta)
  python fx_c_media_momentum.py aggrega                # portafoglio fra coppie positive + promozione
  python fx_c_media_momentum.py tabelle                # tabelle markdown in risultati/c_tabelle.md
"""
import sys
import time
import bisect
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)

SC = Path(r"D:\ricerca_fx\scoperta")
RIS = Path(r"D:\ricerca_fx\risultati")
COPPIE = ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "EURJPY"]
COSTO = {"EURUSD": 0.8, "GBPUSD": 1.0, "AUDUSD": 0.9, "USDCHF": 1.0,
         "USDCAD": 1.2, "USDJPY": 1.2, "EURJPY": 1.4}
LS = [5, 15, 30, 60]
HS = [5, 15, 30, 60]
FASCE = ["asia", "londra", "sovrapp", "ny"]
KS = [1.0, 2.0, 3.0]
USCITE = [("tempo", None, None), ("s1o1", 1.0, 1.0), ("s2o1", 2.0, 1.0), ("s1o2", 1.0, 2.0)]
REGIMI = ["tutti", "basso", "medio", "alto"]
DIREZ = ["contro", "favore"]  # dir -1, +1
SEED = 20261003
NPLAC = 1000
ANNI = list(range(2010, 2018))


def fascia_di(tm):
    """tm = minuto del giorno UTC dell'istante di decisione/entrata."""
    f = np.full(tm.shape, -1, np.int8)
    f[(tm >= 22 * 60 + 15) | (tm < 7 * 60)] = 0
    f[(tm >= 7 * 60) & (tm < 12 * 60)] = 1
    f[(tm >= 12 * 60) & (tm < 16 * 60)] = 2
    f[(tm >= 16 * 60) & (tm < 20 * 60 + 45)] = 3
    return f


def rid_di(iL, iH, iF, iD, iK, iU, iR):
    return ((((((iL * 4 + iH) * 4 + iF) * 2 + iD) * 3 + iK) * 4 + iU) * 4 + iR)


def prepara(coppia):
    m = pd.read_parquet(SC / f"{coppia}_M5.parquet")
    full = pd.date_range(m.index[0], m.index[-1], freq="5min")
    m = m.reindex(full)
    real = m["close"].notna().to_numpy()
    c = m["close"].ffill().to_numpy()
    o = np.where(real, m["open"].to_numpy(), c)
    h = np.where(real, m["high"].to_numpy(), c)
    lo = np.where(real, m["low"].to_numpy(), c)
    del m
    N = len(c)
    ar = np.arange(N)
    labmin = full.tz_convert(None).values.astype("datetime64[m]").astype(np.int64)
    labmd = labmin % 1440
    tmin = labmin + 5                    # istante di decisione = chiusura della candela i
    tm = tmin % 1440
    tday = (tmin // 1440).astype(np.int32)
    lr = np.maximum.accumulate(np.where(real, ar, -10 ** 9))
    okreal = (ar - lr) <= 5
    ri = np.flatnonzero(real)
    starts = np.r_[ri[0], ri[1:][np.diff(ri) > 24]]
    ss = starts[np.searchsorted(starts, ar, "right") - 1]
    pos = np.flatnonzero(labmd == 20 * 60 + 45)
    k = np.searchsorted(pos, ar, "left")
    n2045 = np.where(k < len(pos), pos[np.minimum(k, len(pos) - 1)], N - 1)

    d = pd.read_parquet(SC / f"{coppia}_D1.parquet")
    d = d[(d["minuti"] >= 600) & (d.index.dayofweek < 5)]
    dd = d.index.tz_convert(None).values.astype("datetime64[D]").astype(np.int64)
    pc = d["close"].shift(1)
    tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().to_numpy()
    ratio = atr / d["close"].to_numpy()
    pr = np.full(len(ratio), np.nan)
    for q in range(len(ratio)):
        if not np.isfinite(ratio[q]):
            continue
        prev = ratio[max(0, q - 252):q]
        prev = prev[np.isfinite(prev)]
        if len(prev) >= 60:
            pr[q] = np.mean(prev < ratio[q])
    reg_d = np.where(np.isnan(pr), -1, np.where(pr < 1 / 3, 0, np.where(pr < 2 / 3, 1, 2))).astype(np.int8)
    kk = np.searchsorted(dd, tday, "left") - 1
    okk = kk >= 0
    atr_t = np.where(okk, atr[np.maximum(kk, 0)], np.nan)
    reg_t = np.where(okk, reg_d[np.maximum(kk, 0)], -1).astype(np.int8)
    giorni_borsa = int(((dd >= np.datetime64("2010-01-01").astype(np.int64)) &
                        (dd < np.datetime64("2018-01-01").astype(np.int64))).sum())
    base = okreal & np.isfinite(atr_t) & (atr_t > 0) & (ar < N - 14)
    return dict(o=o, h=h, l=lo, c=c, N=N, ar=ar, tm=tm, tday=tday, ss=ss, n2045=n2045,
                atr=atr_t, reg=reg_t, base=base, fascia=fascia_di(tm), giorni=giorni_borsa)


def nw_slope(xv, yv, lag):
    xc = xv - xv.mean()
    yc = yv - yv.mean()
    sxx = xc @ xc
    b = (xc @ yc) / sxx
    g = xc * (yc - b * xc)
    S = g @ g
    for q in range(1, lag + 1):
        S += 2 * (1 - q / (lag + 1)) * (g[q:] @ g[:-q])
    se = np.sqrt(max(S, 1e-300)) / sxx
    return b, b / se


def nw_mean(v, lag):
    n = len(v)
    mu = v.mean()
    g = v - mu
    S = g @ g
    for q in range(1, lag + 1):
        S += 2 * (1 - q / (lag + 1)) * (g[q:] @ g[:-q])
    se = np.sqrt(max(S, 1e-300)) / n
    return mu, mu / se


def esiti(P, S, H, sH):
    """Esiti per lungo e corto dei segnali S (indici candela del segnale).
    Ritorna dict uscita -> (pnl_long, pnl_short, free_long, free_short) in prezzo."""
    o, h, l, N = P["o"], P["h"], P["l"], P["N"]
    j = S + 1
    E = o[j]
    ex = np.minimum(j + H // 5, P["n2045"][j])
    m = ex - j
    out = {}
    pl = o[ex] - E
    out["tempo"] = (pl, -pl, ex, ex)
    nb = H // 5
    jj = np.minimum(j[:, None] + np.arange(nb)[None, :], N - 1)
    colok = np.arange(nb)[None, :] < m[:, None]
    LO, HI, OP = l[jj], h[jj], o[jj]
    r = np.arange(len(S))
    for nome, s, g in USCITE[1:]:
        res = []
        for lato in (1, -1):
            st = E - lato * s * sH
            tg = E + lato * g * sH
            if lato == 1:
                hs = (LO <= st[:, None]) & colok
                ht = (HI >= tg[:, None]) & colok
            else:
                hs = (HI >= st[:, None]) & colok
                ht = (LO <= tg[:, None]) & colok
            fs = np.where(hs.any(1), hs.argmax(1), 99)
            ft = np.where(ht.any(1), ht.argmax(1), 99)
            stop_px = np.minimum(st, OP[r, np.minimum(fs, nb - 1)]) if lato == 1 else \
                np.maximum(st, OP[r, np.minimum(fs, nb - 1)])
            is_s = (fs < 99) & (fs <= ft)
            is_t = (~is_s) & (ft < 99)
            px = np.where(is_s, stop_px, np.where(is_t, tg, o[ex]))
            free = np.where(is_s, j + fs + 1, np.where(is_t, j + ft + 1, ex))
            res.append((lato * (px - E), free))
        out[nome] = (res[0][0], res[1][0], res[0][1], res[1][1])
    return out


def avido(J, F):
    Jl = J.tolist()
    n = len(Jl)
    out = []
    p = 0
    while p < n:
        out.append(p)
        p = bisect.bisect_left(Jl, int(F[p]), p + 1)
    return np.asarray(out, dtype=np.int64)


def placebo_tot(g, opp, rng):
    """Totali lordi placebo (direzione casuale per operazione): sum(g) + B @ (opp - g)."""
    dlt = (opp - g).astype(np.float32)
    out = np.empty(NPLAC, np.float64)
    blk = 250
    for a in range(0, NPLAC, blk):
        B = rng.integers(0, 2, size=(blk, len(dlt)), dtype=np.int8).astype(np.float32)
        out[a:a + blk] = B @ dlt
    return g.sum() + out


def anno_di(day):
    return (np.datetime64("1970-01-01", "D") + day.astype("timedelta64[D]")).astype("datetime64[Y]").astype(int) + 1970


def calcola(coppia):
    fA = RIS / f"c_mappa_{coppia}.parquet"
    fB = RIS / f"c_regole_{coppia}.parquet"
    if fA.exists() and fB.exists():
        print(coppia, "gia' fatta")
        return
    t0 = time.time()
    pip = 0.01 if "JPY" in coppia else 0.0001
    cbase = COSTO[coppia]
    P = prepara(coppia)
    N, ar, base, fas, reg, atr = P["N"], P["ar"], P["base"], P["fascia"], P["reg"], P["atr"]
    costo_i = np.where(P["tm"] >= 22 * 60 + 15, 2.0, 1.0) * cbase   # costo in pip per entrata
    c, o = P["c"], P["o"]
    rowsA, rowsB, giorni_rows, plac_rows = [], [], [], []
    for iL, L in enumerate(LS):
        sL = L // 5
        x = np.full(N, np.nan)
        x[sL:] = c[sL:] - c[:-sL]
        okL = base & (ar - sL >= P["ss"])
        zxr = x / (atr * np.sqrt(L / 1440))
        for iH, H in enumerate(HS):
            jn = np.minimum(ar + 1, N - 1)
            ex = np.minimum(jn + H // 5, P["n2045"][jn])
            y = o[ex] - o[jn]
            sHv = atr * np.sqrt(H / 1440)
            zyr = y / sHv
            lag = H // 5
            for iF, fn in enumerate(FASCE):
                msk = okL & (fas == iF) & np.isfinite(zxr) & np.isfinite(zyr)
                idx = np.flatnonzero(msk)
                zx = np.clip(zxr[idx], -10, 10)
                zy = np.clip(zyr[idx], -10, 10)
                b, tb = nw_slope(zx, zy, lag)
                thr = np.quantile(np.abs(zx), 0.9)
                tsel = np.abs(zx) >= thr
                tsel &= zx != 0
                v = np.sign(zx[tsel]) * zy[tsel]
                cm, tc = nw_mean(v, lag)
                vp = np.sign(zx[tsel]) * y[idx][tsel] / pip
                row = dict(coppia=coppia, L=L, H=H, fascia=fn, n=len(idx), pend=b, t_pend=tb,
                           coda_z=cm, t_coda=tc, coda_pip=vp.mean(),
                           coda_costi=vp.mean() / costo_i[idx][tsel].mean(), n_coda=int(tsel.sum()))
                rg = reg[idx]
                for q in range(3):
                    mq = rg == q
                    if mq.sum() > 100:
                        bq, tq = nw_slope(zx[mq], zy[mq], lag)
                    else:
                        bq, tq = np.nan, np.nan
                    row[f"pend_r{q}"] = bq
                    row[f"t_r{q}"] = tq
                cons = (abs(tb) >= 2) or (abs(tc) >= 2)
                dcell = int(np.sign(tc if abs(tc) >= 2 else tb))
                row["consistente"] = cons
                row["dir"] = dcell
                rowsA.append(row)
                if not cons or dcell == 0:
                    continue
                # ---------------- Fase B
                iD = 0 if dcell < 0 else 1
                S = idx[np.abs(zxr[idx]) >= 1.0]
                if len(S) == 0:
                    continue
                ES = esiti(P, S, H, sHv[S])
                sgn = dcell * np.sign(x[S])
                azS = np.abs(zxr[S])
                rgS = reg[S]
                J = S + 1
                cS = costo_i[S]
                dayS = P["tday"][S]
                for iU, (un, _, _) in enumerate(USCITE):
                    pL, pS, fL, fS = ES[un]
                    gp = np.where(sgn > 0, pL, pS) / pip
                    op = np.where(sgn > 0, pS, pL) / pip
                    fr = np.where(sgn > 0, fL, fS)
                    for iK, kv in enumerate(KS):
                        for iR, rn in enumerate(REGIMI):
                            sel = azS >= kv
                            if iR > 0:
                                sel &= rgS == (iR - 1)
                            rid = rid_di(iL, iH, iF, iD, iK, iU, iR)
                            rec = dict(coppia=coppia, rid=rid, L=L, H=H, fascia=fn, dir=DIREZ[iD], k=kv,
                                       uscita=un, regime=rn)
                            si = np.flatnonzero(sel)
                            if len(si) == 0:
                                rec.update(n=0)
                                rowsB.append(rec)
                                continue
                            tk = si[avido(J[si], fr[si])]
                            g = gp[tk]
                            cc = cS[tk]
                            n1 = g - cc
                            n15 = g - 1.5 * cc
                            n = len(tk)
                            sd = n1.std(ddof=1) if n > 1 else np.nan
                            yrs = anno_di(dayS[tk])
                            ys = pd.Series(n1).groupby(yrs).sum()
                            rec.update(n=n, opd=n / P["giorni"], netto_pip=n1.mean(), netto15_pip=n15.mean(),
                                       lordo_costi=g.mean() / cc.mean(), netto_costi=n1.mean() / cc.mean(),
                                       t=n1.mean() / sd * np.sqrt(n) if sd and sd > 0 else np.nan,
                                       anni_pos=int((ys > 0).sum()), lordo_tot=g.sum(), costo_tot=cc.sum(),
                                       p=np.nan)
                            if n >= 10 and n1.mean() > 0:
                                rng = np.random.default_rng([SEED, rid, COPPIE.index(coppia)])
                                pt = placebo_tot(g, op[tk], rng)
                                rec["p"] = (np.sum(pt >= g.sum()) + 1) / (NPLAC + 1)
                                plac_rows.append((rid, pt.astype(np.float32)))
                                dser = pd.DataFrame({"giorno": dayS[tk], "net": n1, "net15": n15}).groupby("giorno").sum()
                                giorni_rows.append(pd.DataFrame({"rid": rid, "giorno": dser.index.astype(np.int32),
                                                                 "net": dser["net"].astype(np.float32).values,
                                                                 "net15": dser["net15"].astype(np.float32).values}))
                            rowsB.append(rec)
        print(f"{coppia} L={L} fatto  {time.time() - t0:.0f}s", flush=True)
    A = pd.DataFrame(rowsA)
    B = pd.DataFrame(rowsB)
    B["giorni_borsa"] = P["giorni"]
    if giorni_rows:
        pd.concat(giorni_rows).to_parquet(RIS / f"c_giorni_{coppia}.parquet")
        np.savez(RIS / f"c_placebo_{coppia}.npz", rid=np.array([r for r, _ in plac_rows]),
                 tot=np.vstack([p for _, p in plac_rows]))
    B.to_parquet(fB)
    A.to_parquet(fA)
    print(f"{coppia}: celle consistenti {int(A.consistente.sum())}/{len(A)}, regole {len(B)}, "
          f"netto>0 {int((B.netto_pip > 0).sum())}, t>=3 {int((B.t >= 3).sum())}  {time.time() - t0:.0f}s")


def aggrega():
    B = pd.concat([pd.read_parquet(RIS / f"c_regole_{cp}.parquet") for cp in COPPIE], ignore_index=True)
    pos = B[(B.n >= 10) & (B.netto_pip > 0)]
    G = pd.concat([pd.read_parquet(RIS / f"c_giorni_{cp}.parquet").assign(coppia=cp) for cp in COPPIE
                   if (RIS / f"c_giorni_{cp}.parquet").exists()], ignore_index=True)
    PL = {}
    for cp in COPPIE:
        f = RIS / f"c_placebo_{cp}.npz"
        if f.exists():
            z = np.load(f)
            PL[cp] = dict(zip(z["rid"].tolist(), z["tot"]))
    rows = []
    for rid, grp in pos.groupby("rid"):
        cps = grp.coppia.tolist()
        g = G[(G.rid == rid) & G.coppia.isin(cps)].groupby("giorno")[["net", "net15"]].sum()
        nd = len(g)
        tday = g.net.mean() / g.net.std(ddof=1) * np.sqrt(nd) if nd > 2 else np.nan
        yrs = anno_di(g.index.values)
        ys = g.net.groupby(yrs).sum()
        ptot = sum(PL[cp][rid].astype(np.float64) for cp in cps)
        ltot = grp.lordo_tot.sum()
        n = grp.n.sum()
        net_tot = ltot - grp.costo_tot.sum()
        r0 = grp.iloc[0]
        rows.append(dict(rid=rid, L=r0.L, H=r0.H, fascia=r0.fascia, dir=r0.dir, k=r0.k, uscita=r0.uscita,
                         regime=r0.regime, coppie=",".join(cps), n_coppie=len(cps), n=n, opd=grp.opd.sum(),
                         netto_pip=net_tot / n, netto15_pip=(ltot - 1.5 * grp.costo_tot.sum()) / n,
                         lordo_costi=ltot / grp.costo_tot.sum(), netto_costi=net_tot / grp.costo_tot.sum(),
                         t_giorno=tday, anni_pos=int((ys > 0).sum()),
                         p=(np.sum(ptot >= ltot) + 1) / (NPLAC + 1)))
    A = pd.DataFrame(rows)
    A["promossa"] = ((A.netto_pip > 0) & (A.netto15_pip > 0) & (A.t_giorno >= 3) & (A.anni_pos >= 6)
                     & (A.p < 0.01) & (A.opd >= 1))
    A.to_parquet(RIS / "c_portafoglio.parquet")
    print("regole-portafoglio:", len(A), " promosse:", int(A.promossa.sum()))
    print(A.sort_values("t_giorno", ascending=False).head(12)[
        ["L", "H", "fascia", "dir", "k", "uscita", "regime", "n_coppie", "n", "opd", "netto_pip", "netto15_pip",
         "netto_costi", "t_giorno", "anni_pos", "p"]].round(3).to_string(index=False))


def md(df, index=False):
    """Tabella markdown senza dipendenze (tabulate non installato)."""
    if index:
        df = df.reset_index()
    cols = [str(c) for c in df.columns]
    righe = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        righe.append("| " + " | ".join(str(v) for v in r) + " |")
    return "\n".join(righe)


def tabelle():
    A = pd.concat([pd.read_parquet(RIS / f"c_mappa_{cp}.parquet") for cp in COPPIE], ignore_index=True)
    B = pd.concat([pd.read_parquet(RIS / f"c_regole_{cp}.parquet") for cp in COPPIE], ignore_index=True)
    PF = pd.read_parquet(RIS / "c_portafoglio.parquet")
    out = []

    def simb(t):
        if not np.isfinite(t):
            return "x"
        return "++" if t >= 3 else "+" if t >= 2 else "--" if t <= -3 else "-" if t <= -2 else "."
    out.append("### Mappa pendenza (t NW): celle Asia Londra Sovrapp NY\n")
    out.append("| L -> H | " + " | ".join(COPPIE) + " |")
    out.append("|---" * (len(COPPIE) + 1) + "|")
    for L in LS:
        for H in HS:
            cells = []
            for cp in COPPIE:
                s = A[(A.coppia == cp) & (A.L == L) & (A.H == H)].set_index("fascia")
                cells.append(" ".join(simb(s.loc[f, "t_pend"]) for f in FASCE))
            out.append(f"| {L}m -> {H}m | " + " | ".join(cells) + " |")
    out.append("\n### Mappa coda (t della media sign(x)*y nel decile alto)\n")
    out.append("| L -> H | " + " | ".join(COPPIE) + " |")
    out.append("|---" * (len(COPPIE) + 1) + "|")
    for L in LS:
        for H in HS:
            cells = []
            for cp in COPPIE:
                s = A[(A.coppia == cp) & (A.L == L) & (A.H == H)].set_index("fascia")
                cells.append(" ".join(simb(s.loc[f, "t_coda"]) for f in FASCE))
            out.append(f"| {L}m -> {H}m | " + " | ".join(cells) + " |")
    out.append("\n### Sintesi per fascia e H (mediana fra coppie e L)\n")
    sm = A.groupby(["fascia", "H"]).agg(pend_med=("pend", "median"), t_pend_med=("t_pend", "median"),
                                         coda_pip_med=("coda_pip", "median"),
                                         coda_costi_med=("coda_costi", "median"),
                                         coda_costi_max=("coda_costi", lambda s: s.abs().max()),
                                         n_cons=("consistente", "sum")).reset_index()
    sm["fascia"] = pd.Categorical(sm.fascia, FASCE)
    out.append(sm.sort_values(["fascia", "H"]).round(3).pipe(md))
    out.append("\n### Sintesi per coppia\n")
    sc = A.groupby("coppia").agg(celle_cons=("consistente", "sum"), neg=("t_pend", lambda s: (s <= -2).sum()),
                                 pos=("t_pend", lambda s: (s >= 2).sum()), t_min=("t_pend", "min"),
                                 t_max=("t_pend", "max")).reset_index()
    out.append(sc.round(2).pipe(md))
    out.append("\n### Regole per coppia: conteggi\n")
    Bq = B[B.n > 0]
    cnt = dict(regole=len(B), senza_op=int((B.n == 0).sum()), n_lt30=int((Bq.n < 30).sum()),
               netto_pos=int((Bq.netto_pip > 0).sum()), netto15_pos=int((Bq.netto15_pip > 0).sum()),
               t_ge3=int((Bq.t >= 3).sum()), t_ge3_n30=int(((Bq.t >= 3) & (Bq.n >= 30)).sum()),
               promosse_singola=int(((Bq.netto15_pip > 0) & (Bq.t >= 3) & (Bq.anni_pos >= 6) & (Bq.p < 0.01)
                                     & (Bq.opd >= 1)).sum()))
    out.append(pd.Series(cnt).to_frame("numero").pipe(md, index=True))
    out.append("\n### Lordo in multipli del costo per H (regole per coppia con n >= 30)\n")
    lq = Bq[Bq.n >= 30].groupby(["H", "uscita"]).lordo_costi.describe(percentiles=[0.5, 0.9])[
        ["count", "50%", "90%", "max"]].reset_index()
    out.append(lq.round(3).pipe(md))
    out.append("\n### Migliori 12 regole per coppia per t (n >= 30)\n")
    cols = ["coppia", "L", "H", "fascia", "dir", "k", "uscita", "regime", "n", "opd", "netto_pip", "netto15_pip",
            "lordo_costi", "netto_costi", "t", "anni_pos", "p"]
    out.append(Bq[Bq.n >= 30].sort_values("t", ascending=False).head(12)[cols].round(3).pipe(md))
    out.append("\n### Portafoglio (coppie positive): migliori 15 per t giornaliero\n")
    cols2 = ["L", "H", "fascia", "dir", "k", "uscita", "regime", "coppie", "n", "opd", "netto_pip", "netto15_pip",
             "lordo_costi", "netto_costi", "t_giorno", "anni_pos", "p", "promossa"]
    out.append(PF.sort_values("t_giorno", ascending=False).head(15)[cols2].round(3).pipe(md))
    out.append("\n### Portafoglio con >= 1 operazione/giorno: migliori 10 per t giornaliero\n")
    out.append(PF[PF.opd >= 1].sort_values("t_giorno", ascending=False).head(10)[cols2].round(3)
               .pipe(md))
    out.append(f"\nPortafoglio: {len(PF)} regole, promosse {int(PF.promossa.sum())}, "
               f"con opd>=1 {int((PF.opd >= 1).sum())}, netto15>0 & opd>=1 {int(((PF.opd >= 1) & (PF.netto15_pip > 0)).sum())}")
    (RIS / "c_tabelle.md").write_text("\n".join(out), encoding="utf-8")
    print("scritto", RIS / "c_tabelle.md", " celle consistenti", int(A.consistente.sum()), " regole", len(B))


if __name__ == "__main__":
    RIS.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "calcola"
    if cmd == "calcola":
        for cp in (sys.argv[2:] or COPPIE):
            calcola(cp)
    elif cmd == "aggrega":
        aggrega()
    elif cmd == "tabelle":
        tabelle()
