#!/usr/bin/env python3
"""Famiglia D macro: flussi istituzionali dell'ETF GLD sull'oro. Solo scoperta.

Protocollo: docs/macro-oro-registrazione.md; griglia (408 varianti + mappa
descrittiva) dichiarata in docs/studies/macro/d-gld.md PRIMA del calcolo.

Dati: D:\\ricerca_macro\\scoperta\\MACRO_D1.parquet (gia' sfasato:
gld_tonnellate della riga D = dato del giorno USA precedente, noto alla
chiusura della giornata d'oro D). Segnale alla chiusura di s; finestra (a, b):
entrata all'apertura di s+a, uscita alla chiusura di s+b o allo stop a
2 x ATR20(s). 1R = 2 x ATR20(s). Costi 0,46 $ round trip (x1, x1,5); swap FP
riscalato, x3 il mercoledi'. Placebo: direzione casuale; date casuali con lo
stesso segno del momentum di prezzo a 20 giornate; date qualsiasi.
1000 serie, seed 12345.

Scrive in D:\\ricerca_macro\\risultati\\:
    d_mappa.parquet        celle della mappa flussi -> rendimento successivo
    d_quintili.parquet     media in R per quintile di flusso
    d_contemporanea.parquet relazione flussi/prezzo stesso periodo e ritardi
    d_operazioni.parquet   una riga per operazione e regola
    d_varianti.parquet     una riga per regola con tutte le misure e i p
    d_sempre_long.parquet  netto medio di un long a ogni giornata, per finestra
Stampa solo aggregati compatti.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd

DATI = r"D:\ricerca_macro\scoperta\MACRO_D1.parquet"
OUT = r"D:\ricerca_macro\risultati"
RT = 0.46
ORO_LONG, ORO_SHORT, ORO_RIF = -0.715, 0.325, 4156.98
NPLAC = 1000
SEED = 12345
ANNI = list(range(2009, 2018))
LS = (1, 5, 20)
FINESTRE = [(1, 1), (1, 5), (1, 10), (1, 20)]


def notti_cum(date):
    base = np.datetime64("2000-01-03")
    d = date.astype("datetime64[D]")
    return np.busday_count(base, d) + 2 * np.busday_count(base, d, weekmask="0010000")


def pct(x, q):
    """Quantile q dei 252 valori precedenti (s escluso), almeno 200 presenti."""
    return pd.Series(x).rolling(252, min_periods=200).quantile(q).shift(1).to_numpy()


def rango(x):
    """Quota dei 252 valori precedenti sotto x(s) (pareggi a meta'), min 200."""
    out = np.full(len(x), np.nan)
    for s in range(200, len(x)):
        if np.isnan(x[s]):
            continue
        w = x[max(0, s - 252):s]
        w = w[~np.isnan(w)]
        if len(w) < 200:
            continue
        out[s] = ((w < x[s]).sum() + 0.5 * (w == x[s]).sum()) / len(w)
    return out


def inizio(cond):
    c = np.asarray(cond, bool)
    return c & ~np.r_[False, c[:-1]]


def gt(x, y):
    with np.errstate(invalid="ignore"):
        return np.nan_to_num(x, nan=-np.inf) > np.nan_to_num(y, nan=np.inf)


def lt(x, y):
    with np.errstate(invalid="ignore"):
        return np.nan_to_num(x, nan=np.inf) < np.nan_to_num(y, nan=-np.inf)


def ritardo(x, L):
    return np.r_[np.full(L, np.nan), x[:-L]] if L > 0 else np.r_[x[-L:], np.full(-L, np.nan)]


def carica():
    d = pd.read_parquet(DATI)
    d = d[d["valida"]].copy()
    d.index = pd.to_datetime(d.index)
    return d


def esiti(d):
    """Esito di un'entrata per ogni segnale s, finestra, stop e direzione."""
    o, h, l, c = (d[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    date = d.index.values.astype("datetime64[D]")
    n = len(d)
    cp = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(cp), h - l, np.maximum(h - l, np.maximum(abs(h - cp), abs(l - cp))))
    atr = pd.Series(tr).rolling(20).mean().to_numpy()
    F = notti_cum(date)
    F1 = notti_cum(date + np.timedelta64(1, "D"))
    es = {}
    for (a, b) in FINESTRE:
        idx = np.where((~np.isnan(atr)) & (np.arange(n) + b < n))[0]
        ri = 2 * atr[idx]
        ent = o[idx + a]
        for st in (0, 1):
            for dz in (1, -1):
                stop = ent - dz * ri
                usc = c[idx + b].copy()
                jex = idx + b
                fatto = np.zeros(len(idx), bool)
                if st:
                    for j in range(a, b + 1):
                        jj = idx + j
                        tocco = (~fatto) & ((l[jj] <= stop) if dz == 1 else (h[jj] >= stop))
                        if j == a:
                            px = stop
                        else:
                            px = np.minimum(o[jj], stop) if dz == 1 else np.maximum(o[jj], stop)
                        usc[tocco] = px[tocco]
                        jex = np.where(tocco, jj, jex)
                        fatto |= tocco
                notti = F1[jex] - F[idx + a]
                sw_usd = (ORO_LONG if dz == 1 else ORO_SHORT) * ent / ORO_RIF * notti
                lordo_usd = dz * (usc - ent)
                r = {}
                full = np.full(n, np.nan)
                for k, v in (("lordo", lordo_usd / ri), ("swap", sw_usd / ri), ("costo", RT / ri),
                             ("usd", lordo_usd + sw_usd - RT), ("uscita", jex.astype(float)),
                             ("stopp", fatto.astype(float))):
                    x = full.copy()
                    x[idx] = v
                    r[k] = x
                r["netto"] = r["lordo"] + r["swap"] - r["costo"]
                r["netto15"] = r["lordo"] + r["swap"] - 1.5 * r["costo"]
                es[(a, b, st, dz)] = r
    return dict(o=o, h=h, l=l, c=c, atr=atr, date=d.index, n=n, es=es)


def indicatori(d, P):
    c = P["c"]
    T = d["gld_tonnellate"].to_numpy(float)
    I = dict(T=T)
    for L in LS:
        Tp = ritardo(T, L)
        I[f"F{L}"] = T - Tp
        I[f"Fp{L}"] = (T - Tp) / Tp * 100
        I[f"rk{L}"] = rango(I[f"Fp{L}"])
        for q in (5, 10, 33, 67, 90, 95):
            I[f"Fp{L}_p{q}"] = pct(I[f"Fp{L}"], q / 100)
        I[f"ret{L}"] = c / ritardo(c, L) - 1
        for q in (33, 67):
            I[f"ret{L}_p{q}"] = pct(I[f"ret{L}"], q / 100)
    I["mom20"] = np.sign(np.nan_to_num(c - ritardo(c, 20))).astype(int)
    return I


# ---------------------------------------------------------------- mappa D1
def spear(x, y):
    return pd.Series(x).rank().corr(pd.Series(y).rank())


def t_hac(y, x, lag):
    """Pendenza OLS di y su x (x standardizzato) e t con errori HAC di Bartlett."""
    m = ~(np.isnan(x) | np.isnan(y))
    x, y = x[m], y[m]
    x = (x - x.mean()) / x.std()
    X = np.c_[np.ones(len(x)), x]
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    u = y - X @ beta
    Xu = X * u[:, None]
    S = Xu.T @ Xu
    for k in range(1, lag + 1):
        w = 1 - k / (lag + 1)
        G = Xu[k:].T @ Xu[:-k]
        S += w * (G + G.T)
    XtXi = np.linalg.inv(X.T @ X)
    V = XtXi @ S @ XtXi
    return beta[1], beta[1] / math.sqrt(V[1, 1]), int(m.sum())


def mappa(P, I):
    o, c, atr, n = P["o"], P["c"], P["atr"], P["n"]
    righe, quint = [], []
    for H in (1, 5, 20):
        fwd = np.full(n, np.nan)
        ii = np.arange(n - H)
        fwd[ii] = (c[ii + H] - o[ii + 1]) / (2 * atr[ii])
        for L in LS:
            base = ~np.isnan(I[f"rk{L}"])  # stesso campione per le tre misure
            for mis, x in (("tonn", I[f"F{L}"]), ("perc", I[f"Fp{L}"]), ("rango", I[f"rk{L}"])):
                xx = np.where(base, x, np.nan)
                m = ~(np.isnan(xx) | np.isnan(fwd))
                rho = pd.Series(xx[m]).rank().corr(pd.Series(fwd[m]).rank())
                b, t, nn = t_hac(fwd, xx, H + L)
                q = pd.qcut(pd.Series(xx[m]).rank(method="first"), 5, labels=False).to_numpy()
                qm = pd.Series(fwd[m]).groupby(q).mean()
                righe.append(dict(L=L, misura=mis, H=H, n=nn, spearman=rho, pend_R=b, t_hac=t,
                                  q1=qm[0], q5=qm[4], q5_q1=qm[4] - qm[0]))
                for k in range(5):
                    quint.append(dict(L=L, misura=mis, H=H, quintile=k + 1, medio_R=qm[k],
                                      x_medio=float(np.mean(xx[m][q == k]))))
    # relazione contemporanea e inversa
    cont = []
    for L in LS:
        x = I[f"Fp{L}"]
        base = ~np.isnan(I[f"rk{L}"])
        stesso = ritardo(c, 1) / ritardo(c, L + 1) - 1          # chiusura s-L-1 -> s-1
        prima = ritardo(c, L + 1) / ritardo(c, 2 * L + 1) - 1    # le L giornate prima
        incl = c / ritardo(c, L) - 1                             # chiusura s-L -> s
        for nome, y in (("stessa finestra (s-L-1 -> s-1)", stesso), ("finestra prima", prima),
                        ("finestra con s (s-L -> s)", incl)):
            m = base & ~np.isnan(x) & ~np.isnan(y)
            rho = spear(x[m], y[m])
            pear = np.corrcoef(x[m], y[m])[0, 1]
            _, t, _ = t_hac(x, np.where(m, y, np.nan), 2 * L)
            cont.append(dict(tipo="finestra", L=L, rendimento=nome, k=np.nan, spearman=rho,
                             pearson=pear, t_hac=t, n=int(m.sum())))
    r1 = np.r_[np.nan, np.diff(np.log(c))]
    x = I["Fp1"]
    for k in range(-5, 11):
        y = ritardo(r1, k)
        m = ~np.isnan(x) & ~np.isnan(y) & ~np.isnan(I["rk1"])
        cont.append(dict(tipo="ritardo F1", L=1, rendimento="r(s-k)", k=k,
                         spearman=spear(x[m], y[m]),
                         pearson=np.corrcoef(x[m], y[m])[0, 1], t_hac=np.nan, n=int(m.sum())))
    return pd.DataFrame(righe), pd.DataFrame(quint), pd.DataFrame(cont)


# ---------------------------------------------------------------- griglia
def griglia(I, n):
    regole = []
    # D2: flussi estremi
    for L in LS:
        x = I[f"Fp{L}"]
        dfn = ~np.isnan(I[f"Fp{L}_p90"])
        ev = {f"F{L}>p90": (inizio(gt(x, I[f"Fp{L}_p90"])), 1),
              f"F{L}>p95": (inizio(gt(x, I[f"Fp{L}_p95"])), 1),
              f"F{L}<p10": (inizio(lt(x, I[f"Fp{L}_p10"])), -1),
              f"F{L}<p5": (inizio(lt(x, I[f"Fp{L}_p5"])), -1)}
        for nome, (e, lato) in ev.items():
            for dzn, sg in (("prosegue", 1), ("rientra", -1)):
                dirz = np.where(e, lato * sg, 0)
                for (a, b) in FINESTRE:
                    for st in (0, 1):
                        regole.append(dict(fam="D2", evento=nome, dir=dzn, a=a, b=b, stop=st,
                                           dirz=dirz, definito=dfn, eventi=e, fissa=True))
    # D3: divergenza flussi / prezzo
    for L in (5, 20):
        x, r = I[f"Fp{L}"], I[f"ret{L}"]
        dfn = ~np.isnan(I[f"Fp{L}_p67"]) & ~np.isnan(I[f"ret{L}_p67"])
        cond = {"segno": (gt(r, 0) & lt(x, 0), lt(r, 0) & gt(x, 0)),
                "forte": (gt(r, I[f"ret{L}_p67"]) & lt(x, I[f"Fp{L}_p33"]),
                          lt(r, I[f"ret{L}_p33"]) & gt(x, I[f"Fp{L}_p67"]))}
        for intens, (su_usc, giu_ent) in cond.items():
            e_su, e_giu = inizio(su_usc), inizio(giu_ent)
            tipi = {"prezzo su/uscite": (e_su, np.zeros(n, bool)),
                    "prezzo giu/entrate": (np.zeros(n, bool), e_giu),
                    "entrambe": (e_su, e_giu)}
            for tipo, (a_su, a_giu) in tipi.items():
                e = a_su | a_giu
                for dzn in ("segue flussi", "segue prezzo"):
                    # segue flussi: uscite -> short, entrate -> long
                    v_su, v_giu = (-1, 1) if dzn == "segue flussi" else (1, -1)
                    dirz = np.where(a_su, v_su, np.where(a_giu, v_giu, 0))
                    for (a, b) in FINESTRE[1:]:
                        for st in (0, 1):
                            regole.append(dict(fam="D3", evento=f"L{L} {intens} {tipo}", dir=dzn,
                                               a=a, b=b, stop=st, dirz=dirz, definito=dfn, eventi=e,
                                               fissa=tipo != "entrambe"))
    # D4: segno dei flussi come regola continua
    for L in LS:
        x = I[f"Fp{L}"]
        sg = np.where(gt(x, 0), 1, np.where(lt(x, 0), -1, 0))
        dfn = ~np.isnan(x) & ~np.isnan(I[f"Fp{L}_p90"])
        modi = {"segue": sg, "contro": -sg, "long con entrate": np.where(sg == 1, 1, 0),
                "long con uscite": np.where(sg == -1, 1, 0)}
        for mn, dz in modi.items():
            dz = np.where(dfn, dz, 0)
            for H in (1, 5, 20):
                for st in (0, 1):
                    regole.append(dict(fam="D4", evento=f"F{L} segno", dir=mn, a=1, b=H, stop=st,
                                       dirz=dz, definito=dfn, eventi=dz != 0,
                                       fissa=mn.startswith("long")))
    return regole


def operazioni(P, R):
    es = P["es"]
    a, b, st = R["a"], R["b"], R["stop"]
    ok = ~np.isnan(es[(a, b, st, 1)]["netto"])
    libero = 0
    ss, dd = [], []
    for s in np.nonzero(R["dirz"])[0]:
        if s + a < libero or not ok[s]:
            continue
        dz = int(R["dirz"][s])
        ss.append(s)
        dd.append(dz)
        libero = int(es[(a, b, st, dz)]["uscita"][s]) + 1
    return np.array(ss, int), np.array(dd, int)


def episodi(s, gap=20):
    if len(s) == 0:
        return np.array([], int)
    return np.cumsum(np.r_[True, np.diff(s) > gap])


def valuta(P, I, R, rng):
    es, date = P["es"], P["date"]
    a, b, st = R["a"], R["b"], R["stop"]
    s, dz = operazioni(P, R)
    elig = ~np.isnan(es[(a, b, st, 1)]["netto"]) & R["definito"]
    if not elig.any():
        return None, None
    s0 = int(np.argmax(elig))
    mesi = pd.period_range(date[s0].to_period("M"), "2017-12", freq="M")
    sl = es[(a, b, st, 1)]["netto"][elig]
    r = dict(fam=R["fam"], evento=R["evento"], dir=R["dir"], a=a, b=b, stop=st, fissa=R["fissa"],
             n=len(s), op_mese=len(s) / len(mesi), sempre_long_R=float(np.mean(sl)),
             n_eventi=int(R["eventi"][elig].sum()))
    if len(s) == 0:
        return r, None
    get = lambda k: np.array([es[(a, b, st, x)][k][i] for i, x in zip(s, dz)])
    op = pd.DataFrame({"s": s, "dir": dz, "segnale_data": date[s], "netto": get("netto"),
                       "netto15": get("netto15"), "lordo": get("lordo"), "swap": get("swap"),
                       "costo": get("costo"), "usd": get("usd"), "stopp": get("stopp"),
                       "uscita_data": date[get("uscita").astype(int)],
                       "netto_opp": np.array([es[(a, b, st, -x)]["netto"][i] for i, x in zip(s, dz)])})
    op["episodio"] = episodi(s)
    net = op["netto"].to_numpy()
    tot = net.sum()
    mm = op.groupby(op["uscita_data"].dt.to_period("M"))["netto"].sum().reindex(mesi, fill_value=0.0)
    ya = op.groupby(op["uscita_data"].dt.year)["netto"].sum().reindex(ANNI, fill_value=0.0)
    ep = op.groupby("episodio")["netto"].sum()
    eq = op.sort_values("uscita_data")["netto"].cumsum().to_numpy()
    tt = lambda x: x.mean() / x.std(ddof=1) * math.sqrt(len(x)) if len(x) > 1 and x.std(ddof=1) > 0 else 0.0
    r.update(netto_R=net.mean(), totale_R=tot, netto15_R=op["netto15"].mean(),
             totale15_R=op["netto15"].sum(), lordo_R=op["lordo"].mean(), swap_R=op["swap"].mean(),
             netto_usd=op["usd"].mean(), totale_usd=op["usd"].sum(), quota_stop=op["stopp"].mean(),
             quota_long=(dz == 1).mean(), t_mens=tt(mm), t_op=tt(net), episodi=int(len(ep)),
             t_episodi=tt(ep), anni_pos=int((ya > 0).sum()),
             dd_R=float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max()))
    for y in ANNI:
        r[f"y{y}"] = float(ya[y])
    # placebo direzione
    scelta = rng.random((NPLAC, len(s))) < 0.5
    pdir = np.where(scelta, net, op["netto_opp"].to_numpy()).sum(1)
    nl_all = es[(a, b, st, 1)]["netto"]
    ns_all = es[(a, b, st, -1)]["netto"]
    # placebo date nel regime: stesso segno del momentum 20 al segnale
    mom = I["mom20"]
    plac_reg = np.zeros(NPLAC)
    for sg in (-1, 0, 1):
        k = np.nonzero(mom[s] == sg)[0]
        if len(k) == 0:
            continue
        pool = np.nonzero(elig & (mom == sg))[0] if sg != 0 else np.nonzero(elig)[0]
        if len(pool) < 20:
            pool = np.nonzero(elig)[0]
        pick = pool[rng.integers(0, len(pool), (NPLAC, len(k)))]
        plac_reg += np.where(dz[k][None, :] == 1, nl_all[pick], ns_all[pick]).sum(1)
    pool = np.nonzero(elig)[0]
    pick = pool[rng.integers(0, len(pool), (NPLAC, len(s)))]
    plac_tutte = np.where(dz[None, :] == 1, nl_all[pick], ns_all[pick]).sum(1)
    r["p_dir"] = (1 + (pdir >= tot).sum()) / (NPLAC + 1)
    r["p_reg"] = (1 + (plac_reg >= tot).sum()) / (NPLAC + 1)
    r["p_date"] = (1 + (plac_tutte >= tot).sum()) / (NPLAC + 1)
    r["plac_reg_medio_R"] = float(np.mean(plac_reg) / len(s))
    return r, op


def controllo_motore(P, rng, k=400):
    """Confronto del motore vettoriale con un ciclo giornata per giornata."""
    o, h, l, c, atr, date = P["o"], P["h"], P["l"], P["c"], P["atr"], P["date"]
    dmax = 0.0
    for _ in range(k):
        a, b = FINESTRE[rng.integers(0, len(FINESTRE))]
        st, dz = int(rng.integers(0, 2)), int(rng.choice([1, -1]))
        x = P["es"][(a, b, st, dz)]
        ok = np.nonzero(~np.isnan(x["netto"]))[0]
        s = int(rng.choice(ok))
        ri = 2 * atr[s]
        ent = o[s + a]
        stop = ent - dz * ri
        usc, j_ex = c[s + b], s + b
        if st:
            for j in range(s + a, s + b + 1):
                if (dz == 1 and l[j] <= stop) or (dz == -1 and h[j] >= stop):
                    usc = stop if j == s + a else (min(o[j], stop) if dz == 1 else max(o[j], stop))
                    j_ex = j
                    break
        notti = 0
        g = date[s + a].normalize()
        while g <= date[j_ex].normalize():
            if g.dayofweek < 5:
                notti += 3 if g.dayofweek == 2 else 1
            g += pd.Timedelta(days=1)
        sw = (ORO_LONG if dz == 1 else ORO_SHORT) * ent / ORO_RIF * notti
        net = (dz * (usc - ent) + sw - RT) / ri
        dmax = max(dmax, abs(net - x["netto"][s]))
    return dmax


def main():
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    os.makedirs(OUT, exist_ok=True)
    d = carica()
    P = esiti(d)
    I = indicatori(d, P)
    print("controllo motore, differenza massima:", controllo_motore(P, np.random.default_rng(7)))

    M, Q, C = mappa(P, I)
    M.to_parquet(os.path.join(OUT, "d_mappa.parquet"))
    Q.to_parquet(os.path.join(OUT, "d_quintili.parquet"))
    C.to_parquet(os.path.join(OUT, "d_contemporanea.parquet"))

    regole = griglia(I, P["n"])
    print(f"regole: {len(regole)}  per famiglia: "
          + str(pd.Series([R['fam'] for R in regole]).value_counts().to_dict()))
    rng = np.random.default_rng(SEED)
    righe, ops = [], []
    for i, R in enumerate(regole):
        r, op = valuta(P, I, R, rng)
        if r is None:
            continue
        r["id"] = i
        righe.append(r)
        if op is not None:
            op["id"] = i
            ops.append(op)
    V = pd.DataFrame(righe)
    O = pd.concat(ops, ignore_index=True)
    V["passa"] = ((V["netto_R"] > 0) & (V["netto15_R"] > 0) & (V["t_mens"] >= 3) & (V["anni_pos"] >= 7)
                  & (V["p_dir"] < 0.01) & (~V["fissa"] | (V["p_reg"] < 0.01)))
    V.to_parquet(os.path.join(OUT, "d_varianti.parquet"))
    O.to_parquet(os.path.join(OUT, "d_operazioni.parquet"))
    sl = []
    for (a, b) in FINESTRE:
        for st in (0, 1):
            x = P["es"][(a, b, st, 1)]
            ok = ~np.isnan(x["netto"]) & ~np.isnan(I["Fp20_p90"])
            sl.append(dict(a=a, b=b, stop=st, netto_R=np.nanmean(x["netto"][ok]),
                           netto_usd=np.nanmean(x["usd"][ok]), n=int(ok.sum())))
    SL = pd.DataFrame(sl)
    SL.to_parquet(os.path.join(OUT, "d_sempre_long.parquet"))

    # --- stampa compatta
    print("-- mappa (spearman / t_hac / Q5-Q1 R), misura = perc")
    mp = M[M.misura == "perc"]
    print(mp.pivot(index="L", columns="H", values="spearman").round(3).to_string())
    print(mp.pivot(index="L", columns="H", values="t_hac").round(2).to_string())
    print(mp.pivot(index="L", columns="H", values="q5_q1").round(3).to_string())
    print("-- mappa |t_hac| massimo per misura:", M.groupby("misura")["t_hac"].apply(lambda x: x.abs().max()).round(2).to_dict())
    print("-- contemporanea")
    print(C[C.tipo == "finestra"][["L", "rendimento", "spearman", "pearson", "t_hac", "n"]].round(3).to_string(index=False))
    rr = C[C.tipo == "ritardo F1"].set_index("k")["spearman"].round(3)
    print("ritardi F1 (k: spearman):", rr.to_dict())
    V["tot"] = 1
    g = V.groupby("fam").agg(var=("tot", "sum"), netpos=("netto_R", lambda x: (x > 0).mean()),
                             t_med=("t_mens", "median"), t_max=("t_mens", "max"), t_min=("t_mens", "min"),
                             t2=("t_mens", lambda x: (x >= 2).sum()), t3=("t_mens", lambda x: (x >= 3).sum()),
                             pd01=("p_dir", lambda x: (x < 0.01).sum()), passa=("passa", "sum"))
    print(g.round(3).to_string())
    cols = ["fam", "evento", "dir", "a", "b", "stop", "n", "episodi", "netto_R", "netto15_R", "netto_usd",
            "t_mens", "t_episodi", "anni_pos", "dd_R", "p_dir", "p_reg", "sempre_long_R"]
    print("-- migliori 12 per t mensile")
    print(V.sort_values("t_mens", ascending=False)[cols].head(12).round(3).to_string(index=False))
    print("-- peggiori 5")
    print(V.sort_values("t_mens")[cols].head(5).round(3).to_string(index=False))
    print("-- passano:", int(V["passa"].sum()))
    print("-- sempre long")
    print(SL.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
