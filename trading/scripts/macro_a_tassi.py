#!/usr/bin/env python3
"""Famiglia A — tassi reali, breakeven, 2 anni e dollaro contro l'oro (scoperta 2009-2017).

Protocollo: docs/macro-oro-registrazione.md; griglia dichiarata in
docs/studies/macro/a-tassi.md prima del calcolo. Dati: SOLO
D:\\ricerca_macro\\scoperta\\MACRO_D1.parquet (gia' sfasato: la riga s contiene
solo cio' che era noto alla chiusura della giornata d'oro s).

1) mappa: variazioni su k giornate contro il rendimento dell'oro nelle h
   giornate SUCCESSIVE (entrata all'apertura di s+1), con il riferimento
   contemporaneo (stesse date di calendario, non negoziabile);
2) regole VARIAZIONE (z-score causale della variazione) e REGIME (medie
   f/l), placebo direzione e date, criteri di promozione.

Dettaglio in D:\\ricerca_macro\\risultati\\a_*.parquet; in chat solo aggregati.
"""
from __future__ import annotations

import itertools
import os

import numpy as np
import pandas as pd

SRC = r"D:\ricerca_macro\scoperta\MACRO_D1.parquet"
OUT = r"D:\ricerca_macro\risultati"
VARS = ("reale10", "breakeven10", "nom2", "dxy_sint")
SEGNO_ECON = {"reale10": -1, "breakeven10": 1, "nom2": -1, "dxy_sint": -1}  # +1: salita = buona per l'oro
KS = HS = (1, 5, 20)
CS = (0.5, 1.0, 1.5)
MEDIE = ((5, 20), (20, 60))
COSTO = 0.46
ORO_LONG, ORO_SHORT, ORO_RIF = -0.715, 0.325, 4156.98
NPLAC, SEED = 1000, 12345
ANNI = list(range(2009, 2018))
pd.set_option("display.width", 200)


# ---------------------------------------------------------------- dati
def carica():
    d = pd.read_parquet(SRC)
    d = d[d["valida"]].copy()
    for v in ("reale10", "breakeven10", "nom2"):
        d[v + "_u"] = d[v] * 100.0                       # punti base
    d["dxy_sint_u"] = np.log(d["dxy_sint"]) * 100.0      # % (log)
    for v in VARS:                                       # buchi isolati: ultimo valore noto (causale)
        d[v + "_u"] = d[v + "_u"].ffill(limit=5)
    return d


def notti_cum(date):
    """F(d) tale che notti fra d0 e d1 compresi = F(d1+1) - F(d0) (mercoledi' x3)."""
    base = np.datetime64("2000-01-03")
    dd = date.astype("datetime64[D]")
    return np.busday_count(base, dd) + 2 * np.busday_count(base, dd, weekmask="0010000")


class Motore:
    def __init__(self, d):
        self.d = d
        self.o, self.h, self.l, self.c = (d[x].to_numpy(float) for x in ("open", "high", "low", "close"))
        self.date = d.index.to_numpy("datetime64[D]")
        self.n = len(d)
        cp = np.r_[np.nan, self.c[:-1]]
        tr = np.where(np.isnan(cp), self.h - self.l,
                      np.maximum(self.h - self.l, np.maximum(abs(self.h - cp), abs(self.l - cp))))
        self.atr = pd.Series(tr).rolling(20).mean().to_numpy()
        self.R = 2 * self.atr                             # rischio del giorno del segnale s
        self.anno = d.index.year.to_numpy()
        self.mese = (d.index.year * 12 + d.index.month - 1).to_numpy()
        self.F = notti_cum(self.date)
        self.F1 = notti_cum(self.date + np.timedelta64(1, "D"))

    def esito(self, a, b, s, verso):
        """Operazioni con entrata apertura a, uscita chiusura b, rischio da s, verso +-1 (array)."""
        ent = self.o[a]
        R = self.R[s]
        lordo_d = verso * (self.c[b] - ent)
        notti = self.F1[b] - self.F[a]
        swap_d = np.where(verso > 0, ORO_LONG, ORO_SHORT) * ent / ORO_RIF * notti
        return pd.DataFrame({
            "s": s, "a": a, "b": b, "verso": verso, "R": R,
            "lordo": lordo_d / R, "swap": swap_d / R, "costo": COSTO / R,
            "netto": (lordo_d + swap_d - COSTO) / R,
            "netto15": (lordo_d + swap_d - 1.5 * COSTO) / R,
            "netto_usd": lordo_d + swap_d - COSTO,
            "lordo_long": (self.c[b] - ent) / R,
            "swap_long": ORO_LONG * ent / ORO_RIF * notti / R,
            "swap_short": ORO_SHORT * ent / ORO_RIF * notti / R,
            "anno": self.anno[b], "mese": self.mese[b],
        })

    def entrate_possibili(self, H):
        s = np.arange(self.n - H)                       # s+H <= n-1
        return s[~np.isnan(self.R[s])]


def misure(m, op, mese0):
    """Aggregati di una serie di operazioni."""
    n = len(op)
    mesi = np.arange(mese0, 2017 * 12 + 12)
    if n == 0:
        return dict(n=0, op_mese=0.0, netto_R=np.nan, netto15_R=np.nan, tot_R=0.0, tot15_R=0.0,
                    tot_usd=0.0, lordo_R=np.nan, swap_R=np.nan, t_mese=np.nan, t_op=np.nan,
                    anni_pos=0, dd_R=0.0, quota_long=np.nan)
    mens = op.groupby("mese")["netto"].sum().reindex(mesi, fill_value=0.0).to_numpy()
    t_m = mens.mean() / mens.std(ddof=1) * np.sqrt(len(mens)) if mens.std(ddof=1) > 0 else np.nan
    x = op["netto"].to_numpy()
    t_o = x.mean() / x.std(ddof=1) * np.sqrt(n) if n > 1 and x.std(ddof=1) > 0 else np.nan
    an = op.groupby("anno")["netto"].sum().reindex(ANNI, fill_value=0.0)
    cum = np.cumsum(op.sort_values("b")["netto"].to_numpy())
    dd = float(np.max(np.maximum.accumulate(np.r_[0, cum]) - np.r_[0, cum]))
    return dict(n=n, op_mese=n / len(mesi), netto_R=x.mean(), netto15_R=op["netto15"].mean(),
                tot_R=x.sum(), tot15_R=op["netto15"].sum(), tot_usd=op["netto_usd"].sum(),
                lordo_R=op["lordo"].mean(), swap_R=op["swap"].mean(), t_mese=t_m, t_op=t_o,
                anni_pos=int((an > 0).sum()), dd_R=dd, quota_long=(op["verso"] > 0).mean(),
                **{f"a{y}": an[y] for y in ANNI})


def p_direzione(op, rng):
    """Stesse operazioni, verso casuale."""
    if len(op) == 0:
        return np.nan
    gl, sl, ss, co = (op[k].to_numpy() for k in ("lordo_long", "swap_long", "swap_short", "costo"))
    seg = rng.choice((-1, 1), size=(NPLAC, len(op)))
    tot = np.where(seg > 0, gl + sl, -gl + ss).sum(1) - co.sum()
    return (1 + np.sum(tot >= op["netto"].sum())) / (NPLAC + 1)


# ---------------------------------------------------------------- 1. mappa
def nw_t(x, y, L):
    xd = x - x.mean()
    b = (xd * y).sum() / (xd ** 2).sum()
    e = y - y.mean() - b * xd
    u = xd * e
    S = (u ** 2).sum()
    for j in range(1, L + 1):
        S += 2 * (1 - j / (L + 1)) * (u[j:] * u[:-j]).sum()
    return b / np.sqrt(S / (xd ** 2).sum() ** 2)


def cella(X, Y, anni, L, passo):
    ok = ~(np.isnan(X) | np.isnan(Y))
    X, Y, an = X[ok], Y[ok], anni[ok]
    r = np.corrcoef(X, Y)[0, 1]
    t = nw_t(X, Y, L)
    Xn, Yn = X[::passo], Y[::passo]
    rn = np.corrcoef(Xn, Yn)[0, 1]
    tn = rn * np.sqrt((len(Xn) - 2) / (1 - rn ** 2))
    ry = [np.corrcoef(X[an == a], Y[an == a])[0, 1] for a in ANNI if (an == a).sum() > 30]
    stesso = int(np.sum(np.sign(ry) == np.sign(r)))
    return dict(n=len(X), r=r, t_nw=t, r_nonsovr=rn, t_nonsovr=tn, n_nonsovr=len(Xn),
                anni_stesso_segno=stesso, anni_validi=len(ry))


def mappa(d):
    c, o = d["close"].to_numpy(), d["open"].to_numpy()
    anni = d.index.year.to_numpy()
    righe = []
    for v in VARS:
        x = d[v + "_u"]
        x_cal = x.shift(-1) if v != "dxy_sint" else x       # stesse date di calendario
        for k in KS:
            X = (x - x.shift(k)).to_numpy()
            for h in HS:
                Y = np.full(len(d), np.nan)
                Y[:-h] = np.log(c[h:] / o[1:len(d) - h + 1])
                righe.append(dict(var=v, tipo="predittiva", k=k, h=h,
                                  **cella(X, Y, anni, h + k - 1, max(h, k))))
            Xc = (x_cal - x_cal.shift(k)).to_numpy()
            Yc = np.log(c / pd.Series(c).shift(k).to_numpy())
            righe.append(dict(var=v, tipo="contemporanea", k=k, h=0,
                              **cella(Xc, Yc, anni, k - 1 if k > 1 else 0, k)))
    m = pd.DataFrame(righe)
    m["consistente"] = ((m["t_nw"].abs() >= 2) & (np.sign(m["r_nonsovr"]) == np.sign(m["r"]))
                        & (m["anni_stesso_segno"] >= 7))
    return m


# ---------------------------------------------------------------- 2. regole
def zscore(d, v, N):
    x = d[v + "_u"]
    sd = x.diff().rolling(250, min_periods=60).std()
    return ((x - x.shift(N)) / (sd * np.sqrt(N))).to_numpy()


def variazione(M, g, c, H, modo):
    """Operazioni senza sovrapposizione. g = punteggio favorevole all'oro (z col segno economico)."""
    lim = M.n - H
    if modo == "L+":
        sig = np.where(g >= c, 1, 0)
    elif modo == "L-":
        sig = np.where(g <= -c, 1, 0)
    else:
        sig = np.where(g >= c, 1, np.where(g <= -c, -1, 0))
    sig[np.isnan(g) | np.isnan(M.R)] = 0
    ss, vv = [], []
    libero = 0
    for s in np.flatnonzero(sig[:lim]):
        if s >= libero:
            ss.append(s)
            vv.append(sig[s])
            libero = s + H
    ss = np.array(ss, dtype=int)
    return M.esito(ss + 1, ss + H, ss, np.array(vv, dtype=float))


def tratti(M, pos):
    """pos[d] = verso tenuto nella giornata d (0 = fuori). Un tratto continuo = un'operazione."""
    p = np.r_[0, pos, 0]
    cambio = np.flatnonzero(np.diff(p) != 0)
    a = cambio[:-1]
    b = cambio[1:] - 1
    verso = pos[a] if len(a) else np.array([])
    keep = (verso != 0) & (b < M.n - 1)          # l'ultimo tratto ancora aperto si scarta
    a, b, verso = a[keep], b[keep], verso[keep]
    keep = ~np.isnan(M.R[a - 1])
    a, b, verso = a[keep], b[keep], verso[keep]
    return M.esito(a, b, a - 1, verso.astype(float))


def regime_maschera(d, v, f, l, segno):
    x = d[v + "_u"]
    mf, ml = x.rolling(f).mean(), x.rolling(l).mean()
    favorevole = (mf - ml) * SEGNO_ECON[v] > 0
    reg = favorevole if segno > 0 else ~favorevole
    definito = (mf.notna() & ml.notna()).to_numpy()
    return reg.to_numpy() & definito, definito


def pos_da_maschera(m, definito, modo):
    pos = np.zeros(len(m))
    if modo == "LS+":
        val = np.where(m, 1.0, -1.0)
        val[~definito] = 0
    else:
        val = m.astype(float)
    pos[1:] = val[:-1]
    return pos


def main():
    os.makedirs(OUT, exist_ok=True)
    d = carica()
    M = Motore(d)
    rng = np.random.default_rng(SEED)

    # ---- mappa
    mp = mappa(d)
    mp.to_parquet(os.path.join(OUT, "a_mappa.parquet"))
    pr = mp[mp.tipo == "predittiva"]
    print("== MAPPA predittiva: t Newey-West (r) per variabile x k (righe) e h (colonne)")
    tab = pr.assign(cel=pr.apply(lambda q: f"{q.t_nw:+.2f} ({q.r:+.3f}){'*' if q.consistente else ''}", axis=1)
                    ).pivot(index=["var", "k"], columns="h", values="cel")
    print(tab.to_string())
    co = mp[mp.tipo == "contemporanea"]
    print("== CONTEMPORANEA (stesse date): r / t NW / anni stesso segno")
    print(co.assign(cel=co.apply(lambda q: f"{q.r:+.3f} / {q.t_nw:+.1f} / {q.anni_stesso_segno}", axis=1)
                    ).pivot(index="var", columns="k", values="cel").to_string())
    print(f"celle predittive consistenti: {int(pr.consistente.sum())} su {len(pr)}")

    # ---- riferimento: sempre long, tenuta H
    rif = []
    for H in HS:
        sp = M.entrate_possibili(H)
        tutte = M.esito(sp + 1, sp + H, sp, np.ones(len(sp)))
        cat = sp[::H]
        catena = M.esito(cat + 1, cat + H, cat, np.ones(len(cat)))
        mm = misure(M, catena, M.mese[cat[0] + 1])
        rif.append(dict(H=H, netto_medio_tutte=tutte["netto"].mean(), lordo_medio_tutte=tutte["lordo"].mean(),
                        swap_medio_tutte=tutte["swap"].mean(), **{k: mm[k] for k in
                        ("n", "netto_R", "tot_R", "tot_usd", "t_mese", "anni_pos")}))
    rif = pd.DataFrame(rif)
    rif.to_parquet(os.path.join(OUT, "a_sempre_long.parquet"))
    print("== SEMPRE LONG (catena di operazioni con tenuta H; 'tutte' = media su ogni entrata possibile)")
    print(rif.round(3).to_string(index=False))
    pool = {}
    for H in HS:
        sp = M.entrate_possibili(H)
        pool[H] = M.esito(sp + 1, sp + H, sp, np.ones(len(sp)))["netto"].to_numpy()

    # ---- regole
    varianti, operazioni = [], []
    vid = 0
    for v, N, c, H, modo in itertools.product(VARS, KS, CS, HS, ("L+", "L-", "LS+")):
        g = SEGNO_ECON[v] * zscore(d, v, N)
        op = variazione(M, g, c, H, modo)
        mese0 = M.mese[np.flatnonzero(~np.isnan(g) & ~np.isnan(M.R))[0] + 1]
        r = dict(id=vid, tipo="VARIAZIONE", var=v, N=N, c=c, H=H, f=np.nan, l=np.nan, modo=modo,
                 **misure(M, op, mese0))
        r["p_dir"] = p_direzione(op, rng)
        if modo != "LS+" and len(op):
            draw = rng.integers(0, len(pool[H]), size=(NPLAC, len(op)))
            r["p_date"] = (1 + np.sum(pool[H][draw].sum(1) >= op["netto"].sum())) / (NPLAC + 1)
            r["placebo_date_medio"] = pool[H].mean()
        varianti.append(r)
        operazioni.append(op.assign(id=vid))
        vid += 1
    regime_info = []
    for v, (f, l), modo in itertools.product(VARS, MEDIE, ("L+", "L-", "LS+")):
        segno = -1 if modo == "L-" else 1
        m, definito = regime_maschera(d, v, f, l, segno)
        op = tratti(M, pos_da_maschera(m, definito, modo))
        i0 = np.flatnonzero(definito)[0]
        r = dict(id=vid, tipo="REGIME", var=v, N=np.nan, c=np.nan, H=np.nan, f=f, l=l, modo=modo,
                 **misure(M, op, M.mese[i0 + 1]))
        r["p_dir"] = p_direzione(op, rng)
        # sempre long sullo stesso periodo (in $/oncia) e rendimento giornaliero dentro/fuori
        a, b = i0 + 1, M.n - 1
        bh = M.esito(np.array([a]), np.array([b]), np.array([a - 1]), np.array([1.0]))
        r["sempre_long_usd"] = float(bh["netto_usd"].iloc[0])
        lr = np.r_[np.nan, np.log(M.c[1:] / M.c[:-1])]
        dentro = np.r_[False, m[:-1]] & np.r_[False, definito[:-1]]
        fuori = ~np.r_[False, m[:-1]] & np.r_[False, definito[:-1]]
        r["rend_giorno_dentro_bp"] = np.nanmean(lr[dentro]) * 1e4
        r["rend_giorno_fuori_bp"] = np.nanmean(lr[fuori]) * 1e4
        r["quota_giorni_dentro"] = dentro.sum() / (dentro.sum() + fuori.sum())
        if modo != "LS+" and len(op):
            idx = np.flatnonzero(definito)
            stat = []
            for _ in range(NPLAC):
                k = rng.integers(60, len(idx) - 60)
                mm = np.zeros(M.n, dtype=bool)
                mm[idx] = np.roll(m[idx], k)
                stat.append(tratti(M, pos_da_maschera(mm, definito, modo))["netto"].sum())
            r["p_date"] = (1 + np.sum(np.array(stat) >= op["netto"].sum())) / (NPLAC + 1)
            r["placebo_date_medio"] = float(np.mean(stat))
        varianti.append(r)
        operazioni.append(op.assign(id=vid))
        vid += 1

    V = pd.DataFrame(varianti)
    O = pd.concat(operazioni, ignore_index=True)
    O["giorno_segnale"] = d.index[O["s"].to_numpy()]
    V.to_parquet(os.path.join(OUT, "a_varianti.parquet"))
    O.to_parquet(os.path.join(OUT, "a_operazioni.parquet"))

    pdate_ok = V["p_date"].isna() | (V["p_date"] < 0.01)
    V["promossa"] = ((V.netto_R > 0) & (V.netto15_R > 0) & (V.t_mese >= 3) & (V.anni_pos >= 7)
                     & (V.p_dir < 0.01) & pdate_ok)
    print(f"\n== VARIANTI: {len(V)}  (VARIAZIONE {sum(V.tipo == 'VARIAZIONE')}, REGIME {sum(V.tipo == 'REGIME')})")
    print(f"netto>0 x1: {(V.netto_R > 0).mean():.1%}  t_mese>=3: {(V.t_mese >= 3).sum()}  "
          f"t_mese<=-3: {(V.t_mese <= -3).sum()}  promosse: {int(V.promossa.sum())}")
    agg = V.groupby(["tipo", "var", "modo"]).agg(
        netto_pos=("netto_R", lambda s: (s > 0).mean()), t_med=("t_mese", "median"),
        t_max=("t_mese", "max"), t_min=("t_mese", "min"), p_dir_min=("p_dir", "min"))
    print(agg.round(3).to_string())
    col = ["id", "tipo", "var", "N", "c", "H", "f", "l", "modo", "n", "netto_R", "netto15_R", "tot_R",
           "tot_usd", "t_mese", "anni_pos", "dd_R", "p_dir", "p_date"]
    print("== migliori 12 per t mensile")
    print(V.sort_values("t_mese", ascending=False)[col].head(12).round(3).to_string(index=False))
    rg = V[V.tipo == "REGIME"][["var", "f", "l", "modo", "n", "netto_R", "tot_usd", "sempre_long_usd",
                                "rend_giorno_dentro_bp", "rend_giorno_fuori_bp", "quota_giorni_dentro",
                                "t_mese", "anni_pos", "p_dir", "p_date"]]
    print("== REGIME (tutti)")
    print(rg.round(3).to_string(index=False))
    cand = V[V.promossa].sort_values("t_mese", ascending=False).drop_duplicates("var").head(3)
    print("== CANDIDATI")
    print(cand[col].round(3).to_string(index=False) if len(cand) else "nessuno")


if __name__ == "__main__":
    main()
