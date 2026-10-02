"""Ricerca da zero, famiglia 6: fra mercati.

Protocollo: docs/ricerca-da-zero-registrazione.md. Usa SOLO
D:\\ricerca_zero\\scoperta\\<SIM>_<M5|M15|H1>.parquet (indice UTC all'apertura).
Varianti dichiarate in docs/studies/zero/f6-intermercato.md prima del calcolo:
282 = 78 (a oro/argento) + 132 (b S&P/Nasdaq) + 72 (c mossa forte -> sessione
successiva di un altro mercato).

Coppie allineate solo sugli istanti presenti in entrambe le serie (nessun
riempimento in avanti). Al massimo due mercati in memoria alla volta.

Uscite in D:\\ricerca_zero\\risultati\\:
  f6_varianti.parquet    una riga per variante (statistiche, placebo, ritardo)
  f6_operazioni.parquet  una riga per operazione (tutte le varianti)
  f6_descr.parquet       descrittive (spread oro/argento, correlazioni
                         incrociate M5, correlazioni segnale -> bersaglio)
Stampa solo aggregati compatti.
"""
from __future__ import annotations

import gc
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)

SCOPERTA = Path(r"D:\ricerca_zero\scoperta")
RISULTATI = Path(r"D:\ricerca_zero\risultati")
COSTO = {"XAUUSD": 0.40, "XAGUSD": 0.025, "SPXUSD": 0.55, "NSXUSD": 1.50, "GRXEUR": 1.50}
N_PLACEBO = 1000
SEED = 12345
MIN_OP_ANNO = 5
NY, BER = "America/New_York", "Europe/Berlin"
MIN = 60 * 10**9
NS5 = 5 * MIN

RES: list[dict] = []
OPS: list[pd.DataFrame] = []
DESCR: list[dict] = []


# ---------------------------------------------------------------- dati
def carica(sim: str, tf: str = "M5") -> pd.DataFrame:
    d = pd.read_parquet(SCOPERTA / f"{sim}_{tf}.parquet", columns=["open", "close", "minuti"])
    d = d[~d.index.duplicated()].sort_index()
    d.index = d.index.as_unit("ns")
    return d


def allinea(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Solo istanti presenti in entrambe (inner join), nessun riempimento."""
    return a.join(b, how="inner", lsuffix="_1", rsuffix="_2")


def open_at(idx: np.ndarray, o: np.ndarray, t: np.ndarray, tol: int) -> np.ndarray:
    """Apertura della prima barra con inizio in [t, t+tol]; NaN se assente."""
    pos = np.searchsorted(idx, t, side="left")
    p2 = np.minimum(pos, len(idx) - 1)
    ok = (pos < len(idx)) & ((idx[p2] - t) <= tol) & (idx[p2] >= t)
    pr = np.full(len(t), np.nan)
    pr[ok] = o[p2[ok]]
    return pr


def close_before(idx: np.ndarray, c: np.ndarray, t: np.ndarray, tol: int) -> np.ndarray:
    """Chiusura dell'ultima barra con inizio < t e >= t - tol; NaN se assente."""
    pos = np.searchsorted(idx, t, side="left") - 1
    p2 = np.maximum(pos, 0)
    ok = (pos >= 0) & ((t - idx[p2]) <= tol)
    pr = np.full(len(t), np.nan)
    pr[ok] = c[p2[ok]]
    return pr


def utc_ns(date_naive: pd.DatetimeIndex, minuti: int, tz: str) -> np.ndarray:
    """Data locale (naive, mezzanotte) + minuti locali -> ns UTC."""
    loc = (date_naive + pd.Timedelta(minutes=minuti)).tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
    return loc.tz_convert("UTC").as_unit("ns").asi8


# ---------------------------------------------------------------- statistiche
def statistiche(g: np.ndarray, c: np.ndarray, anni: np.ndarray) -> dict:
    g = np.asarray(g, float)
    c = np.asarray(c, float)
    n = len(g)
    out = dict(n=n, lordo_bp=np.nan, costo_bp=np.nan, netto_bp=np.nan, netto_x_costo=np.nan,
               t=np.nan, anni_pos=0, anni_tot=0, quota_anni=np.nan, p=np.nan)
    if n < 5:
        return out
    net = g - c
    m, sd = net.mean(), net.std(ddof=1)
    y = pd.DataFrame({"a": anni, "x": net}).groupby("a").x.agg(["mean", "size"])
    y = y[y["size"] >= MIN_OP_ANNO]
    rng = np.random.default_rng(SEED)
    g32 = g.astype(np.float32)
    cnt = 0
    for _ in range(N_PLACEBO // 100):
        S = np.where(rng.random((100, n)) < 0.5, -1.0, 1.0).astype(np.float32)
        pm = (S @ g32) / n - c.mean()
        cnt += int((pm >= m - 1e-9).sum())
    out.update(lordo_bp=g.mean(), costo_bp=c.mean(), netto_bp=m, netto_x_costo=m / c.mean(),
               t=m / sd * np.sqrt(n) if sd > 0 else np.nan, anni_pos=int((y["mean"] > 0).sum()),
               anni_tot=len(y), quota_anni=(y["mean"] > 0).mean() if len(y) else np.nan,
               p=(1 + cnt) / (N_PLACEBO + 1))
    return out


def registra(fam: str, nome: str, nmin: int, t_ns: np.ndarray, g: np.ndarray, c: np.ndarray,
             g_rit: np.ndarray | None = None, c_rit: np.ndarray | None = None, **par) -> None:
    anni = pd.DatetimeIndex(np.asarray(t_ns, "int64")).year.values if len(t_ns) else np.array([], int)
    st = statistiche(g, c, anni)
    rec = dict(fam=fam, variante=nome, nmin=nmin, **par, **st)
    if g_rit is not None:
        nr = len(g_rit)
        if nr >= 5:
            netr = np.asarray(g_rit) - np.asarray(c_rit)
            rec.update(n_rit=nr, netto_rit_bp=netr.mean(), t_rit=netr.mean() / netr.std(ddof=1) * np.sqrt(nr))
        else:
            rec.update(n_rit=nr, netto_rit_bp=np.nan, t_rit=np.nan)
    RES.append(rec)
    if len(g):
        OPS.append(pd.DataFrame({"variante": nome, "t": np.asarray(t_ns, "int64"), "lordo_bp": g,
                                 "costo_bp": c}))


# ---------------------------------------------------------------- (a) oro/argento
def sim_z(z: np.ndarray, pe: np.ndarray, k: float, uscita: str, maxh: int, fix: int):
    """Decisioni d (z noto alla chiusura), entrata alla barra pe[d]; uscita alla
    barra pe[j]. Restituisce (d, barra entrata, barra uscita, direzione spread)."""
    n = len(z)
    out = []
    d = 0
    while d < n:
        zd = z[d]
        if np.isfinite(zd) and abs(zd) >= k and pe[d] >= 0:
            sg = np.sign(zd)
            if uscita == "Z0":
                j = d + 1
                while j < n and j < d + maxh and not (np.isfinite(z[j]) and np.sign(z[j]) != sg):
                    j += 1
            else:
                j = d + fix
            while j < n and pe[j] < 0:
                j += 1
            if j >= n:
                break
            out.append((d, pe[d], pe[j], -sg))
            d = j
            continue
        d += 1
    if not out:
        return (np.array([], int),) * 3 + (np.array([], float),)
    a = np.array(out)
    return a[:, 0].astype(int), a[:, 1].astype(int), a[:, 2].astype(int), a[:, 3]


def parte_a() -> None:
    x = carica("XAUUSD", "H1")
    s_ = carica("XAGUSD", "H1")
    a = allinea(x, s_)
    del x, s_
    ts = a.index.asi8
    ox, cx, os_, cs = a.open_1.values, a.close_1.values, a.open_2.values, a.close_2.values
    lox, los = np.log(ox), np.log(os_)
    s = np.log(cx) - np.log(cs)
    N = len(a)
    cxb, csb = COSTO["XAUUSD"], COSTO["XAGUSD"]

    def legs(pb, px, dr):
        return {
            "PAIR": (dr * ((lox[px] - lox[pb]) - (los[px] - los[pb])) * 1e4,
                     (cxb / ox[pb] + csb / os_[pb]) * 1e4),
            "ORO": (dr * (lox[px] - lox[pb]) * 1e4, cxb / ox[pb] * 1e4),
            "ARG": (-dr * (los[px] - los[pb]) * 1e4, csb / os_[pb] * 1e4),
        }

    def esegui(prefisso, z, pe, k, usc, maxh, fix, nmin, par):
        d, pb, px, dr = sim_z(z, pe, k, usc, maxh, fix)
        base = legs(pb, px, dr)
        ok = pb + 1 < px
        rit = legs(pb[ok] + 1, px[ok], dr[ok])
        for leg in ["PAIR", "ORO", "ARG"]:
            g, c = base[leg]
            gr, cr = rit[leg]
            registra("a", f"{prefisso} {leg}", nmin, ts[pb], g, c, gr, cr, gamba=leg, k=k, uscita=usc, **par)

    # H1
    pe_h = np.r_[np.arange(1, N), -1]
    for W in [24, 120, 480]:
        ss = pd.Series(s)
        z = ((ss - ss.rolling(W).mean()) / ss.rolling(W).std()).values
        for k in [1.5, 2.0, 2.5]:
            for usc in ["Z0", "F"]:
                esegui(f"a H1 W{W} k{k} {usc}", z, pe_h, k, usc, W, W // 4, 200, dict(tf="H1", W=W))
    # giornaliera: decisione alla chiusura della H1 delle 19 UTC, entrata alla H1 delle 20
    hr = pd.DatetimeIndex(ts).tz_localize("UTC").hour.values
    rows = np.flatnonzero(hr[:-1] == 19)
    pe_d = np.where(ts[rows + 1] - ts[rows] == 60 * MIN, rows + 1, -1)
    sd_ = pd.Series(s[rows])
    for W in [20, 60]:
        z = ((sd_ - sd_.rolling(W).mean()) / sd_.rolling(W).std()).values
        for k in [1.5, 2.0]:
            for usc in ["Z0", "F"]:
                esegui(f"a D1 W{W} k{k} {usc}", z, pe_d, k, usc, 20, 5, 100, dict(tf="D1", W=W))

    # descrittive: AR(1) dello spread giornaliero, z H1 -> variazione futura dello spread
    sdv = s[rows]
    yrs = pd.DatetimeIndex(ts[rows]).year.values

    def ar1(v):
        v0, v1 = v[:-1], v[1:]
        phi = np.polyfit(v0, v1, 1)[0]
        return phi, (-np.log(2) / np.log(phi) if 0 < phi < 1 else np.inf)

    phi, hl = ar1(sdv)
    DESCR.append(dict(tipo="a_ar1", chiave="tutto", phi=phi, emivita=hl, n=len(sdv)))
    for y in np.unique(yrs):
        v = sdv[yrs == y]
        if len(v) > 50:
            phi, hl = ar1(v)
            DESCR.append(dict(tipo="a_ar1", chiave=str(y), phi=phi, emivita=hl, n=len(v)))
    # scomposizione (diagnostica a posteriori, non e' una prova): D1 W20 k1,5 Z0
    sdz = ((sd_ - sd_.rolling(20).mean()) / sd_.rolling(20).std()).values
    d, pb, px, dr = sim_z(sdz, pe_d, 1.5, "Z0", 20, 5)
    for sg in [-1.0, 1.0]:
        m = dr == sg
        DESCR.append(dict(tipo="a_scomp", chiave=f"D1 W20 k1.5 Z0 dir_oro {sg:+.0f}", n=int(m.sum()),
                          oro_bp=(sg * (lox[px[m]] - lox[pb[m]]) * 1e4).mean(),
                          arg_bp=(-sg * (los[px[m]] - los[pb[m]]) * 1e4).mean(),
                          durata_g=np.median((ts[px[m]] - ts[pb[m]]) / (24 * 60 * MIN))))
    r20 = pd.Series(np.log(cx[rows])).diff(20).values
    ok = np.isfinite(sdz) & np.isfinite(r20)
    DESCR.append(dict(tipo="a_scomp", chiave="corr z(W20) vs rend. oro 20 giorni", corr=np.corrcoef(sdz[ok], r20[ok])[0, 1],
                      n=int(ok.sum())))
    ss = pd.Series(s)
    for W in [24, 120, 480]:
        z = ((ss - ss.rolling(W).mean()) / ss.rolling(W).std()).values
        for h in [1, 6, 24, 120]:
            fs = np.r_[s[h:] - s[:-h], [np.nan] * h] * 1e4
            ok = np.isfinite(z) & np.isfinite(fs)
            r = np.corrcoef(z[ok], fs[ok])[0, 1]
            slope = np.polyfit(z[ok], fs[ok], 1)[0]
            yy = pd.DatetimeIndex(ts[ok]).year.values
            neg = sum(np.corrcoef(z[ok][yy == y], fs[ok][yy == y])[0, 1] < 0 for y in np.unique(yy))
            DESCR.append(dict(tipo="a_zfut", chiave=f"W{W} h{h}", corr=r, bp_per_z=slope,
                              anni_neg=neg, anni=len(np.unique(yy)), n=int(ok.sum())))
    del a
    gc.collect()


# ---------------------------------------------------------------- correlazioni incrociate M5
def rend_tf(a: pd.DataFrame, tf_min: int, min_frac: float) -> pd.DataFrame:
    """Rendimenti close-to-close sulle barre comuni consecutive e liquide."""
    ts = a.index.asi8
    prev_ok = np.r_[False, np.diff(ts) == tf_min * MIN]
    liq = (a.minuti_1.values >= min_frac) & (a.minuti_2.values >= min_frac)
    liq_prev = np.r_[False, liq[:-1]]
    ok = prev_ok & liq & liq_prev
    r1 = np.r_[np.nan, np.diff(np.log(a.close_1.values))]
    r2 = np.r_[np.nan, np.diff(np.log(a.close_2.values))]
    return pd.DataFrame({"r1": r1, "r2": r2}, index=a.index)[ok]


def ccf(nome: str, s1: str, s2: str) -> None:
    a = allinea(carica(s1), carica(s2))
    r = rend_tf(a, 5, 4)
    del a
    gc.collect()
    hh = r.index.hour
    for sess, m in [("tutte", np.ones(len(r), bool)), ("14-20 UTC", (hh >= 14) & (hh < 20))]:
        rr = r[m]
        for spost in [0, 1]:
            r2 = pd.Series(rr.r2.values, index=rr.index + pd.Timedelta(minutes=5 * spost))
            r2 = r2.reindex(r.index)  # stesso spostamento sulle barre di tutta la serie
            row = dict(tipo="ccf", chiave=f"{nome} {sess} spost{spost}", n=len(rr))
            for L in range(-3, 4):
                y = r2.reindex(rr.index + pd.Timedelta(minutes=5 * L)).values
                x = rr.r1.values
                ok = np.isfinite(y) & np.isfinite(x)
                row[f"L{L:+d}"] = np.corrcoef(x[ok], y[ok])[0, 1]
            DESCR.append(row)


# ---------------------------------------------------------------- (b) S&P / Nasdaq
def cash_mask(ts_ns: np.ndarray, tf_min: int) -> np.ndarray:
    loc = pd.DatetimeIndex(ts_ns).tz_localize("UTC").tz_convert(NY)
    mm = loc.hour * 60 + loc.minute
    return np.asarray((mm >= 570) & (mm + tf_min <= 960) & (loc.dayofweek < 5))


def parte_b1(sp5: pd.DataFrame, nq5: pd.DataFrame) -> None:
    fol = {"SPXUSD": (sp5.index.asi8, sp5.open.values), "NSXUSD": (nq5.index.asi8, nq5.open.values)}
    for tf, tfm in [("M5", 5), ("M15", 15), ("H1", 60)]:
        if tf == "M5":
            a = allinea(sp5, nq5)
        else:
            a = allinea(carica("SPXUSD", tf), carica("NSXUSD", tf))
        r = rend_tf(a, tfm, 4 if tf == "M5" else 0.8 * tfm)
        del a
        rr = {"SPXUSD": r.r1, "NSXUSD": r.r2}
        sig = {k_: v.rolling(2000, min_periods=500).std().shift(1).values for k_, v in rr.items()}
        ts = r.index.asi8
        tend = ts + tfm * MIN
        cash = cash_mask(ts, tfm)
        for lead, fsim in [("SPXUSD", "NSXUSD"), ("NSXUSD", "SPXUSD")]:
            rl, rf = rr[lead].values, rr[fsim].values
            zl, zf = rl / sig[lead], rf / sig[fsim]
            g_ = zl - zf
            fidx, fo = fol[fsim]
            cst = COSTO[fsim]
            for q in [1.0, 2.0]:
                for tipo in ["LEAD", "GAP"]:
                    if tipo == "LEAD":
                        m = np.abs(zl) >= q
                        dr = np.sign(rl)
                    else:
                        m = (np.abs(g_) >= q) & (np.sign(g_) == np.sign(rl))
                        dr = np.sign(g_)
                    m &= np.isfinite(zl) & np.isfinite(zf)
                    for sess in ["TUTTE", "CASH"]:
                        mm = m & cash if sess == "CASH" else m
                        ii = np.flatnonzero(mm)
                        te = tend[ii]
                        pe = open_at(fidx, fo, te, 0)
                        pe_r = open_at(fidx, fo, te + NS5, 0)
                        for hold in [1, 3]:
                            tx = te + hold * tfm * MIN
                            px = open_at(fidx, fo, tx, 30 * MIN)
                            ok = np.isfinite(pe) & np.isfinite(px)
                            sel = []
                            last = -1
                            for j in np.flatnonzero(ok):
                                if te[j] >= last:
                                    sel.append(j)
                                    last = tx[j]
                            sel = np.array(sel, int)
                            d_ = dr[ii[sel]]
                            g = d_ * np.log(px[sel] / pe[sel]) * 1e4
                            c = cst / pe[sel] * 1e4
                            okr = np.isfinite(pe_r[sel])
                            gr = d_[okr] * np.log(px[sel][okr] / pe_r[sel][okr]) * 1e4
                            cr = cst / pe_r[sel][okr] * 1e4
                            verso = "S>N" if lead == "SPXUSD" else "N>S"
                            registra("b1", f"b1 {tf} {verso} {tipo} q{q:g} {sess} h{hold}", 200, te[sel],
                                     g, c, gr, cr, tf=tf, verso=verso, segnale=tipo, k=q, sessione=sess,
                                     tenuta=hold)
        gc.collect()


def parte_b2(sp5: pd.DataFrame, nq5: pd.DataFrame) -> None:
    a = allinea(sp5, nq5)
    loc = a.index.tz_convert(NY)
    mm = (loc.hour * 60 + loc.minute).values
    keep = (mm >= 570) & (mm < 960) & (loc.dayofweek < 5)
    a, mm = a[keep], mm[keep]
    day = loc[keep].tz_localize(None).normalize().values
    ts = a.index.asi8
    oS, cS, oN, cN = a.open_1.values, a.close_1.values, a.open_2.values, a.close_2.values
    cut = np.r_[0, np.flatnonzero(day[1:] != day[:-1]) + 1, len(day)]
    giorni = []
    for i0, i1 in zip(cut[:-1], cut[1:]):
        if mm[i0] != 570 or mm[i1 - 1] < 945:
            continue
        giorni.append((i0, i1))
    deod = np.array([np.log(cN[i1 - 1] / oN[i0]) - np.log(cS[i1 - 1] / oS[i0]) for i0, i1 in giorni])
    sigma = pd.Series(deod).rolling(60, min_periods=40).std().shift(1).values
    cS_, cN_ = COSTO["SPXUSD"], COSTO["NSXUSD"]
    for tc in [630, 690, 810]:
        for k in [1.0, 1.5]:
            for usc in ["EOD", "Z0"]:
                rec = {leg: ([], [], [], [], []) for leg in ["PAIR", "SPX", "NSX"]}
                for gi, (i0, i1) in enumerate(giorni):
                    if not np.isfinite(sigma[gi]):
                        continue
                    seg = slice(i0, i1)
                    m_ = mm[seg]
                    jb = np.flatnonzero(m_ == tc - 5)
                    je = np.flatnonzero(m_ == tc)
                    if len(jb) == 0 or len(je) == 0:
                        continue
                    jb, je = i0 + jb[0], i0 + je[0]
                    D = np.log(cN[jb] / oN[i0]) - np.log(cS[jb] / oS[i0])
                    if abs(D / sigma[gi]) < k:
                        continue
                    sg = np.sign(D)
                    # uscita
                    xS, xN = cS[i1 - 1], cN[i1 - 1]
                    if usc == "Z0":
                        Dj = np.log(cN[je:i1] / oN[i0]) - np.log(cS[je:i1] / oS[i0])
                        cr = np.flatnonzero(np.sign(Dj) != sg)
                        if len(cr) and je + cr[0] + 1 < i1:
                            jx = je + cr[0] + 1
                            xS, xN = oS[jx], oN[jx]
                    jr = je + 1 if je + 1 < i1 and mm[je + 1] == tc + 5 else -1
                    for leg in rec:
                        for ent, lst_off in [(je, 0), (jr, 1)]:
                            if ent < 0:
                                continue
                            rs = np.log(xS / oS[ent]) * 1e4
                            rn = np.log(xN / oN[ent]) * 1e4
                            if leg == "PAIR":
                                g, c = -sg * (rn - rs), (cS_ / oS[ent] + cN_ / oN[ent]) * 1e4
                            elif leg == "SPX":
                                g, c = sg * rs, cS_ / oS[ent] * 1e4
                            else:
                                g, c = -sg * rn, cN_ / oN[ent] * 1e4
                            if lst_off == 0:
                                rec[leg][0].append(ts[je])
                                rec[leg][1].append(g)
                                rec[leg][2].append(c)
                            else:
                                rec[leg][3].append(g)
                                rec[leg][4].append(c)
                hh = f"{tc // 60}:{tc % 60:02d}"
                for leg, (t_, g, c, gr, cr) in rec.items():
                    registra("b2", f"b2 {hh} k{k:g} {leg} {usc}", 100, np.array(t_, "int64"),
                             np.array(g), np.array(c), np.array(gr), np.array(cr),
                             controllo=hh, k=k, gamba=leg, uscita=usc)


# ---------------------------------------------------------------- (c) tabelle giornaliere
def date_locali(idx: pd.DatetimeIndex, tz: str) -> pd.DatetimeIndex:
    d = pd.DatetimeIndex(np.unique(idx.tz_convert(tz).tz_localize(None).normalize()))
    return d[d.dayofweek < 5]


def tab_indice(sim: str) -> pd.DataFrame:
    d = carica(sim)
    idx, o, c = d.index.asi8, d.open.values, d.close.values
    U = date_locali(d.index, NY)
    t930, t1400, t1600 = utc_ns(U, 570, NY), utc_ns(U, 840, NY), utc_ns(U, 960, NY)
    po = open_at(idx, o, t930, 0)
    p14 = open_at(idx, o, t1400, 0)
    pc = close_before(idx, c, t1600, 15 * MIN)
    del d
    gc.collect()
    return pd.DataFrame({"r_cash": np.log(pc / po), "r_2h": np.log(pc / p14)}, index=U)


def prossimo_feriale(U: pd.DatetimeIndex) -> pd.DatetimeIndex:
    n = U + pd.Timedelta(days=1)
    n = n + pd.to_timedelta(np.where(n.dayofweek == 5, 2, np.where(n.dayofweek == 6, 1, 0)), unit="D")
    return n


def tab_dax() -> pd.DataFrame:
    d = carica("GRXEUR")
    idx, o, c = d.index.asi8, d.open.values, d.close.values
    B = date_locali(d.index, BER)
    out = pd.DataFrame(index=B)
    o9 = open_at(idx, o, utc_ns(B, 540, BER), 5 * MIN)
    out["o_b"] = o9
    out["c_b10"] = close_before(idx, c, utc_ns(B, 600, BER), 15 * MIN)
    out["c_b1730"] = close_before(idx, c, utc_ns(B, 1050, BER), 15 * MIN)
    base = B.tz_localize("UTC").as_unit("ns").asi8
    out["o_u7"] = open_at(idx, o, base + 7 * 60 * MIN, 5 * MIN)
    out["c_u8"] = close_before(idx, c, base + 8 * 60 * MIN, 15 * MIN)
    out["c_u12"] = close_before(idx, c, base + 12 * 60 * MIN, 15 * MIN)
    del d
    gc.collect()
    return out


def tab_metallo(sim: str, U: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(1) per etichetta 22-22 D: Asia [D-1 22, D 07) e Londra 07-08 / 07-12 UTC;
    (2) per data USA U: entrata alla chiusura USA (16:00 NY), uscita alle 07/12 UTC
    del giorno feriale dopo."""
    d = carica(sim)
    idx, o, c = d.index.asi8, d.open.values, d.close.values
    D = pd.DatetimeIndex(np.unique((d.index + pd.Timedelta(hours=2)).tz_localize(None).normalize()))
    D = D[D.dayofweek < 5]
    base = D.tz_localize("UTC").as_unit("ns").asi8
    t1 = pd.DataFrame(index=D)
    a_o = open_at(idx, o, base - 2 * 60 * MIN, 120 * MIN)
    a_c = close_before(idx, c, base + 7 * 60 * MIN, 15 * MIN)
    t1["r_asia"] = np.log(a_c / a_o)
    t1["o_u7"] = open_at(idx, o, base + 7 * 60 * MIN, 5 * MIN)
    t1["c_u8"] = close_before(idx, c, base + 8 * 60 * MIN, 15 * MIN)
    t1["c_u12"] = close_before(idx, c, base + 12 * 60 * MIN, 15 * MIN)
    nx = prossimo_feriale(U).tz_localize("UTC").as_unit("ns").asi8
    t2 = pd.DataFrame(index=U)
    t2["o_us"] = open_at(idx, o, utc_ns(U, 960, NY), 15 * MIN)
    t2["c_u7"] = close_before(idx, c, nx + 7 * 60 * MIN, 15 * MIN)
    t2["c_u12"] = close_before(idx, c, nx + 12 * 60 * MIN, 15 * MIN)
    del d
    gc.collect()
    return t1, t2


def z60(r: pd.Series) -> pd.Series:
    r = r.dropna()
    return r / r.rolling(60, min_periods=40).std().shift(1)


def parte_c() -> None:
    sp = tab_indice("SPXUSD")
    nq = tab_indice("NSXUSD")
    dax = tab_dax()
    U = sp.index.union(nq.index)
    xa1, xa2 = tab_metallo("XAUUSD", U)
    xg1, xg2 = tab_metallo("XAGUSD", U)
    # mappa data USA -> prossima giornata DAX (entro 4 giorni)
    def verso_dax(Us: pd.DatetimeIndex) -> pd.DataFrame:
        pos = np.searchsorted(dax.index.values, Us.values, side="right")
        ok = pos < len(dax)
        p2 = np.minimum(pos, len(dax) - 1)
        ok &= (dax.index.values[p2] - Us.values) <= np.timedelta64(4, "D")
        out = dax.iloc[p2].copy()
        out.index = Us
        out[~ok] = np.nan
        return out

    coppie = [
        ("c1", "S&P cash", z60(sp.r_cash), "DAX", "us_dax", [("9-10 Ber", "o_b", "c_b10"), ("9-17:30 Ber", "o_b", "c_b1730")]),
        ("c2", "Nasdaq cash", z60(nq.r_cash), "DAX", "us_dax", [("9-10 Ber", "o_b", "c_b10"), ("9-17:30 Ber", "o_b", "c_b1730")]),
        ("c3", "S&P 14-16 NY", z60(sp.r_2h), "DAX", "us_dax", [("9-10 Ber", "o_b", "c_b10"), ("9-17:30 Ber", "o_b", "c_b1730")]),
        ("c4", "S&P cash", z60(sp.r_cash), "XAUUSD", xa2, [("USclose-07", "o_us", "c_u7"), ("USclose-12", "o_us", "c_u12")]),
        ("c5", "S&P cash", z60(sp.r_cash), "XAGUSD", xg2, [("USclose-07", "o_us", "c_u7"), ("USclose-12", "o_us", "c_u12")]),
        ("c6", "oro Asia", z60(xa1.r_asia), "XAUUSD", xa1, [("07-08", "o_u7", "c_u8"), ("07-12", "o_u7", "c_u12")]),
        ("c7", "oro Asia", z60(xa1.r_asia), "XAGUSD", xg1, [("07-08", "o_u7", "c_u8"), ("07-12", "o_u7", "c_u12")]),
        ("c8", "oro Asia", z60(xa1.r_asia), "GRXEUR", dax, [("07-08", "o_u7", "c_u8"), ("07-12", "o_u7", "c_u12")]),
        ("c9", "argento Asia", z60(xg1.r_asia), "XAUUSD", xa1, [("07-08", "o_u7", "c_u8"), ("07-12", "o_u7", "c_u12")]),
    ]
    for cid, snome, z, tsim, tab, finestre in coppie:
        z = z.dropna()
        if isinstance(tab, str):
            tt = verso_dax(z.index)
            tsim = "GRXEUR"
        else:
            tt = tab.reindex(z.index)
        cst = COSTO[tsim]
        t_sig = z.index.tz_localize("UTC").as_unit("ns").asi8
        for fn, co, cc in finestre:
            pe, px = tt[co].values, tt[cc].values
            ok = np.isfinite(pe) & np.isfinite(px)
            rt = np.log(px / pe) * 1e4
            zz = z.values
            DESCR.append(dict(tipo="c_corr", chiave=f"{cid} {snome} -> {tsim} {fn}", n=int(ok.sum()),
                              corr=np.corrcoef(zz[ok], rt[ok])[0, 1],
                              corr_forti=np.corrcoef(zz[ok & (np.abs(zz) >= 1)], rt[ok & (np.abs(zz) >= 1)])[0, 1]))
            for k in [1.0, 1.5]:
                m = ok & (np.abs(zz) >= k)
                for dr_n, dr in [("CONT", 1), ("REV", -1)]:
                    g = dr * np.sign(zz[m]) * rt[m]
                    c = cst / pe[m] * 1e4
                    registra("c", f"{cid} {snome}->{tsim} {fn} k{k:g} {dr_n}", 100, t_sig[m], g, c,
                             coppia=cid, finestra=fn, k=k, direzione=dr_n)


# ---------------------------------------------------------------- main
def main() -> None:
    RISULTATI.mkdir(parents=True, exist_ok=True)
    parte_a()
    print("a fatta", flush=True)
    sp5, nq5 = carica("SPXUSD"), carica("NSXUSD")
    parte_b1(sp5, nq5)
    parte_b2(sp5, nq5)
    del sp5, nq5
    gc.collect()
    print("b fatta", flush=True)
    parte_c()
    print("c fatta", flush=True)
    for nome, s1, s2 in [("S&P-Nasdaq", "SPXUSD", "NSXUSD"), ("oro-argento", "XAUUSD", "XAGUSD"),
                         ("S&P-DAX", "SPXUSD", "GRXEUR"), ("S&P-oro", "SPXUSD", "XAUUSD")]:
        ccf(nome, s1, s2)
        gc.collect()

    v = pd.DataFrame(RES)
    v["promossa"] = ((v.netto_bp > 0) & (v.t >= 3) & (v.quota_anni >= 0.75) & (v.p < 0.01)
                     & (v.n >= v.nmin) & (v.netto_rit_bp.fillna(1) > 0))
    v.to_parquet(RISULTATI / "f6_varianti.parquet")
    pd.concat(OPS, ignore_index=True).to_parquet(RISULTATI / "f6_operazioni.parquet")
    de = pd.DataFrame(DESCR)
    de.to_parquet(RISULTATI / "f6_descr.parquet")

    print(f"\nvarianti: {len(v)} per famiglia: {v.fam.value_counts().to_dict()}")
    print("t<=-3 per famiglia:", v[v.t <= -3].fam.value_counts().to_dict())
    print(f"promosse: {int(v.promossa.sum())}  t>=3: {(v.t >= 3).sum()}  t<=-3: {(v.t <= -3).sum()}  "
          f"t>=2: {(v.t >= 2).sum()}  p<0.01: {(v.p < 0.01).sum()}")
    col = ["variante", "n", "lordo_bp", "costo_bp", "netto_bp", "netto_x_costo", "t", "anni_pos", "anni_tot", "p",
           "netto_rit_bp", "t_rit"]
    print("\nmigliori 12 per t")
    print(v.sort_values("t", ascending=False)[col].head(12).round(3).to_string(index=False))
    print("\npeggiori 6 per t")
    print(v.sort_values("t")[col].head(6).round(3).to_string(index=False))
    print("\nmigliori per LORDO (t sul lordo), b1")
    b1 = v[v.fam == "b1"].copy()
    print(b1.sort_values("lordo_bp", ascending=False)[col].head(8).round(3).to_string(index=False))
    print("\ndescrittive")
    print(de[de.tipo == "a_ar1"][["chiave", "phi", "emivita", "n"]].round(3).to_string(index=False))
    print(de[de.tipo == "a_scomp"][["chiave", "n", "oro_bp", "arg_bp", "durata_g", "corr"]].round(3).to_string(index=False))
    print(de[de.tipo == "a_zfut"][["chiave", "corr", "bp_per_z", "anni_neg", "anni", "n"]].round(3).to_string(index=False))
    cc = de[de.tipo == "ccf"][["chiave", "n"] + [f"L{L:+d}" for L in range(-3, 4)]]
    print(cc.round(3).to_string(index=False))
    print(de[de.tipo == "c_corr"][["chiave", "n", "corr", "corr_forti"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
