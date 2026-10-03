#!/usr/bin/env python3
"""Famiglia 2 multi-giorno: ritorno alla media di qualche giorno sul paniere.

Protocollo: docs/multigiorno-paniere-registrazione.md; griglia dichiarata in
docs/studies/multi/f2-ritorno.md PRIMA del calcolo. Solo scoperta.

Segnale alla chiusura della giornata s (22->22 UTC), entrata all'apertura di
s+1, uscita alla chiusura di s+H, oppure allo stop a 2 x ATR20. 1R = 2 x
ATR20. Costi round trip da costi.csv (x1 e x1,5), swap per notte (x3 il
mercoledi'). Placebo a direzione casuale e a date casuali (stesso mercato,
stessa direzione, stessa gestione), 1000 serie, seed 12345.

Scrive in D:\\ricerca_multi\\risultati\\:
    f2_operazioni.parquet  una riga per operazione (regola x mercato)
    f2_varianti.parquet    una riga per regola x universo con tutte le misure
    f2_deriva.parquet      diagnostica: netto medio di long/short a date casuali
Stampa solo aggregati compatti.
"""
from __future__ import annotations

import itertools
import math
import os

import numpy as np
import pandas as pd

DATI = r"D:\ricerca_multi\scoperta\PANIERE_D1.parquet"
COSTI = r"D:\ricerca_multi\costi.csv"
OUT = r"D:\ricerca_multi\risultati"

GRUPPI = {
    "indici": ["SPXUSD", "NSXUSD", "GRXEUR"],
    "metalli": ["XAUUSD", "XAGUSD"],
    "cambi": ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "EURJPY"],
}
MERCATI = [m for g in GRUPPI.values() for m in g]
ANNO0, ANNO1 = 2010, 2017
TENUTE = [1, 3, 5, 10]
STOP_ATR = 2.0
SWAP_ANNUO = 0.03
ORO_LONG, ORO_SHORT, ORO_RIF = -0.715, 0.325, 4156.98
NPLAC = 1000
SEED = 12345

SEGNALI = ([("SERIE", n, None) for n in (2, 3, 4)]
           + [("MOSSA", L, k) for L in (1, 3, 5) for k in (1.0, 1.5, 2.0)])
REGOLE = list(itertools.product(range(len(SEGNALI)), TENUTE, (0, 1), (0, 1)))


def nome_segnale(i):
    t, a, b = SEGNALI[i]
    return f"SERIE{a}" if t == "SERIE" else f"MOSSA{a}g{b:g}ATR"


def notti_cum(date):
    """F(d) tale che notti fra d0 e d1 compresi = F(d1+1) - F(d0)."""
    base = np.datetime64("2000-01-03")
    d = date.astype("datetime64[D]")
    return (np.busday_count(base, d)
            + 2 * np.busday_count(base, d, weekmask="0010000"))


def prepara(g, costo):
    """Esiti di tutte le entrate possibili per tenuta, stop e direzione."""
    g = g.sort_values("giorno").reset_index(drop=True)
    o, h, l, c = (g[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    date = g["giorno"].to_numpy("datetime64[D]")
    n = len(g)
    cp = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(cp), h - l,
                  np.maximum(h - l, np.maximum(abs(h - cp), abs(l - cp))))
    atr = pd.Series(tr).rolling(20).mean().to_numpy()
    sma = pd.Series(c).rolling(200).mean().to_numpy()
    anni = date.astype("datetime64[Y]").astype(int) + 1970
    rischio = np.r_[np.nan, STOP_ATR * atr[:-1]]          # ATR del segnale (s = i-1)
    base_ok = (~np.isnan(rischio)) & (anni >= ANNO0) & (anni <= ANNO1)
    F = notti_cum(date)
    F1 = notti_cum(date + np.timedelta64(1, "D"))
    oro = costo["oro"]
    es = {}
    for H, st in itertools.product(TENUTE, (0, 1)):
        ok = base_ok & (np.arange(n) + H - 1 < n)
        idx = np.where(ok)[0]
        ri = rischio[idx]
        ent = o[idx]
        for d in (1, -1):
            stop = ent - d * ri
            usc = np.full(len(idx), np.nan)
            jex = idx + H - 1
            fatto = np.zeros(len(idx), bool)
            if st:
                for j in range(H):
                    jj = idx + j
                    tocco = (~fatto) & ((l[jj] <= stop) if d == 1 else (h[jj] >= stop))
                    if j == 0:
                        px = stop
                    else:
                        px = np.minimum(o[jj], stop) if d == 1 else np.maximum(o[jj], stop)
                    usc[tocco] = px[tocco]
                    jex[tocco] = jj[tocco]
                    fatto |= tocco
            usc[~fatto] = c[idx + H - 1][~fatto]
            lordo = d * (usc - ent) / ri
            notti = F1[jex] - F[idx]
            if oro:
                swap = (ORO_LONG if d == 1 else ORO_SHORT) * ent / ORO_RIF * notti / ri
            else:
                swap = -SWAP_ANNUO / 365 * ent * notti / ri
            c1 = costo["rt"] / ri
            full = np.full(n, np.nan)
            ris = {}
            for k, v in (("lordo", lordo), ("swap", swap), ("costo", c1),
                         ("uscita", jex.astype(float)), ("stopp", fatto.astype(float))):
                a = full.copy()
                a[idx] = v
                ris[k] = a
            ris["netto"] = ris["lordo"] + ris["swap"] - ris["costo"]
            es[(H, st, d)] = ris
        es[(H, st, "eleg")] = idx
    return dict(date=date, c=c, atr=atr, sma=sma, es=es, n=n,
                anni=anni, base_ok=base_ok)


def segnali_mercato(P, isig, filtro):
    """Direzione (+1 long, -1 short, 0) del segnale per ogni giornata s."""
    c, atr, sma = P["c"], P["atr"], P["sma"]
    t, a, b = SEGNALI[isig]
    dirz = np.zeros(P["n"], int)
    if t == "SERIE":
        verso = np.sign(np.r_[0.0, np.diff(c)])
        su = np.zeros(P["n"], int)
        giu = np.zeros(P["n"], int)
        for i in range(1, P["n"]):
            su[i] = su[i - 1] + 1 if verso[i] > 0 else 0
            giu[i] = giu[i - 1] + 1 if verso[i] < 0 else 0
        dirz[su >= a] = -1
        dirz[giu >= a] = 1
    else:
        mossa = c - np.r_[np.full(a, np.nan), c[:-a]]
        with np.errstate(invalid="ignore"):
            dirz[mossa >= b * atr] = -1
            dirz[mossa <= -b * atr] = 1
    if filtro:
        with np.errstate(invalid="ignore"):
            dirz[(dirz == 1) & ~(c > sma)] = 0
            dirz[(dirz == -1) & ~(c < sma)] = 0
    return dirz


def operazioni(P, dirz, H, st):
    es = P["es"]
    ok = ~np.isnan(es[(H, st, 1)]["netto"])
    libero = 0
    ent, dr = [], []
    for s in np.nonzero(dirz)[0]:
        i = s + 1
        if i < libero or i >= P["n"] or not ok[i]:
            continue
        d = dirz[s]
        ent.append(i)
        dr.append(d)
        libero = int(es[(H, st, d)]["uscita"][i]) + 1
    return np.array(ent, int), np.array(dr, int)


def misure(op, mesi, plac_dir, plac_dat):
    n = len(op)
    r = {"n": n, "op_mese": n / len(mesi)}
    if n == 0:
        return r
    net = op["netto"].to_numpy()
    r.update(netto_R=net.mean(), totale_R=net.sum(),
             netto15_R=op["netto15"].mean(), lordo_R=op["lordo"].mean(),
             swap_R=op["swap"].mean(), costo_R=op["costo"].mean(),
             quota_swap=(-op["swap"].sum() / op["lordo"].sum()
                         if op["lordo"].sum() > 0 else np.nan),
             quota_stop=op["stopp"].mean())
    mm = op.groupby(op["uscita_data"].dt.to_period("M"))["netto"].sum()
    mm = mm.reindex(mesi, fill_value=0.0)
    r["t_mens"] = mm.mean() / mm.std(ddof=1) * math.sqrt(len(mm)) if mm.std() > 0 else 0
    r["t_op"] = net.mean() / net.std(ddof=1) * math.sqrt(n) if n > 1 and net.std() > 0 else 0
    ya = op.groupby(op["uscita_data"].dt.year)["netto"].sum()
    r["anni_pos"] = int((ya > 0).sum())
    r["anni"] = int(len(ya))
    eq = op.sort_values("uscita_data")["netto"].cumsum().to_numpy()
    r["dd_R"] = float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
    tot = net.sum()
    r["p_dir"] = (1 + (plac_dir >= tot).sum()) / (NPLAC + 1)
    r["p_date"] = (1 + (plac_dat >= tot).sum()) / (NPLAC + 1)
    r["plac_date_medio_R"] = plac_dat.mean() / n
    return r


def main():
    pd.set_option("display.width", 200)
    os.makedirs(OUT, exist_ok=True)
    d = pd.read_parquet(DATI)
    d = d[d["valida"]]
    costi = pd.read_csv(COSTI).set_index("mercato")["costo_rt"].to_dict()
    PM = {m: prepara(d[d["mercato"] == m],
                     {"rt": costi[m], "oro": m == "XAUUSD"}) for m in MERCATI}

    # diagnostica: deriva (long/short a date casuali = media su tutte le entrate)
    der = []
    for m in MERCATI:
        for H, st in itertools.product(TENUTE, (0, 1)):
            for dd in (1, -1):
                v = PM[m]["es"][(H, st, dd)]["netto"]
                der.append({"mercato": m, "H": H, "stop": st, "dir": dd,
                            "netto_R": np.nanmean(v), "lordo_R": np.nanmean(PM[m]["es"][(H, st, dd)]["lordo"])})
    pd.DataFrame(der).to_parquet(os.path.join(OUT, "f2_deriva.parquet"))

    # mesi per universo: dal primo mese con entrate possibili a dicembre 2017
    primo = {m: pd.Timestamp(PM[m]["date"][PM[m]["base_ok"]][0]).to_period("M") for m in MERCATI}
    fine = pd.Period(f"{ANNO1}-12", "M")
    universi = {m: [m] for m in MERCATI}
    universi.update(GRUPPI)
    universi["paniere"] = MERCATI
    mesi_u = {u: pd.period_range(min(primo[m] for m in ms), fine, freq="M")
              for u, ms in universi.items()}

    rng = np.random.default_rng(SEED)
    tutte_op, righe = [], []
    for (isig, H, st, filt) in REGOLE:
        reg = f"{nome_segnale(isig)} H{H} {'stop' if st else 'tempo'} {'m200' if filt else 'tutti'}"
        opm, pdir, pdat, pflt = {}, {}, {}, {}
        for m in MERCATI:
            P = PM[m]
            es = P["es"]
            dirz = segnali_mercato(P, isig, filt)
            ent, dr = operazioni(P, dirz, H, st)
            L, S = es[(H, st, 1)], es[(H, st, -1)]
            pick = lambda k, e=ent, q=dr: np.where(q == 1, L[k][e], S[k][e])
            op = pd.DataFrame({
                "regola": reg, "mercato": m, "segnale": nome_segnale(isig), "H": H,
                "stop": st, "filtro": filt, "dir": dr,
                "entrata_data": pd.to_datetime(P["date"][ent]),
                "uscita_data": pd.to_datetime(P["date"][pick("uscita").astype(int)]) if len(ent) else pd.to_datetime([]),
                "lordo": pick("lordo"), "swap": pick("swap"), "costo": pick("costo"),
                "netto": pick("netto"), "stopp": pick("stopp"),
                "netto_opposto": np.where(dr == 1, S["netto"][ent], L["netto"][ent]),
            })
            op["netto15"] = op["netto"] - 0.5 * op["costo"]
            opm[m] = op
            n = len(ent)
            if n == 0:
                pdir[m] = np.zeros(NPLAC)
                pdat[m] = np.zeros(NPLAC)
                pflt[m] = np.zeros(NPLAC)
                continue
            # placebo direzione: stesse operazioni, direzione casuale
            vr, vo = op["netto"].to_numpy(), op["netto_opposto"].to_numpy()
            mask = rng.random((NPLAC, n)) < 0.5
            pdir[m] = vr.sum() + mask.astype(float) @ (vo - vr)
            # placebo date: stessa direzione e gestione, data casuale
            eleg = es[(H, st, "eleg")]
            pos = eleg[rng.integers(0, len(eleg), size=(NPLAC, n))]
            pdat[m] = np.where(dr[None, :] == 1, L["netto"][pos], S["netto"][pos]).sum(1)
            # diagnostica (non criterio): date casuali nello stesso stato del
            # filtro media 200 (long fra le giornate sopra la media, short sotto)
            if filt:
                cs, ss = P["c"][eleg - 1], P["sma"][eleg - 1]
                with np.errstate(invalid="ignore"):
                    eL, eS = eleg[cs > ss], eleg[cs < ss]
                u = rng.random((NPLAC, n))
                pL = eL[(u * len(eL)).astype(int)] if len(eL) else eleg[:1].repeat(1)
                pS = eS[(u * len(eS)).astype(int)] if len(eS) else eleg[:1].repeat(1)
                pflt[m] = np.where(dr[None, :] == 1, L["netto"][pL] if len(eL) else 0,
                                   S["netto"][pS] if len(eS) else 0).sum(1)
            else:
                pflt[m] = pdat[m]
        tutte_op.extend(opm.values())
        for u, ms in universi.items():
            op = pd.concat([opm[m] for m in ms], ignore_index=True)
            r = misure(op, mesi_u[u], sum(pdir[m] for m in ms), sum(pdat[m] for m in ms))
            if len(op):
                r["p_date_filtro"] = (1 + (sum(pflt[m] for m in ms) >= op["netto"].sum()).sum()) / (NPLAC + 1)
            r.update(regola=reg, universo=u, segnale=nome_segnale(isig), H=H,
                     stop=st, filtro=filt)
            righe.append(r)

    ops = pd.concat(tutte_op, ignore_index=True)
    ops.to_parquet(os.path.join(OUT, "f2_operazioni.parquet"))
    V = pd.DataFrame(righe)
    V["livello"] = np.where(V["universo"].isin(MERCATI), "mercato",
                            np.where(V["universo"] == "paniere", "paniere", "gruppo"))
    V["passa"] = ((V["netto_R"] > 0) & (V["netto15_R"] > 0) & (V["t_mens"] >= 3)
                  & (V["anni_pos"] >= 6) & (V["p_dir"] < 0.01) & (V["p_date"] < 0.01))
    V.to_parquet(os.path.join(OUT, "f2_varianti.parquet"))

    print(f"varianti: {len(V)} (regole {len(REGOLE)} x universi {len(universi)}); "
          f"operazioni salvate {len(ops)}")
    s = V.groupby("livello").agg(n=("n", "size"), netto_pos=("netto_R", lambda x: (x > 0).mean()),
                                 t3=("t_mens", lambda x: (x >= 3).sum()),
                                 tneg3=("t_mens", lambda x: (x <= -3).sum()),
                                 pdir=("p_dir", lambda x: (x < 0.01).sum()),
                                 pdate=("p_date", lambda x: (x < 0.01).sum()),
                                 passa=("passa", "sum"))
    print(s.round(3).to_string())
    col = ["regola", "universo", "n", "op_mese", "netto_R", "netto15_R", "t_mens",
           "anni_pos", "swap_R", "dd_R", "p_dir", "p_date", "p_date_filtro"]
    print(V[V["passa"]].sort_values("t_mens", ascending=False)[col].head(15).round(3).to_string())


if __name__ == "__main__":
    main()
