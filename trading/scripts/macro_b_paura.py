#!/usr/bin/env python3
"""Famiglia B macro: paura e volatilita' (VIX, GVZ) sull'oro. Solo scoperta.

Protocollo: docs/macro-oro-registrazione.md; griglia (536 varianti) dichiarata
in docs/studies/macro/b-paura.md PRIMA del calcolo.

Dati: D:\\ricerca_macro\\scoperta\\MACRO_D1.parquet (gia' sfasato: ogni riga
contiene solo cio' che era noto alla chiusura della giornata d'oro 22->22).
Segnale alla chiusura di s; finestra (a, b): entrata all'apertura di s+a,
uscita alla chiusura di s+b o allo stop a 2 x ATR20(s). 1R = 2 x ATR20(s).
Costi 0,46 $ round trip (x1, x1,5); swap FP riscalato, x3 il mercoledi'.
Placebo: direzione casuale; date casuali nel regime; date qualsiasi.
1000 serie, seed 12345.

Scrive in D:\\ricerca_macro\\risultati\\:
    b_operazioni.parquet   una riga per operazione e regola
    b_varianti.parquet     una riga per regola con tutte le misure e i p
    b_eventi_vix.parquet   studio d'evento descrittivo dopo i picchi di VIX
    b_sempre_long.parquet  netto medio di un long a ogni giornata, per finestra
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
FIN_B1 = [(1, 1), (1, 3), (1, 5), (1, 10), (1, 20), (4, 10), (6, 20)]
FIN_EV = [(1, 1), (1, 5), (1, 10), (1, 20)]
FINESTRE = sorted(set(FIN_B1 + FIN_EV + [(1, 1), (1, 5), (1, 10), (1, 20)]))


def notti_cum(date):
    base = np.datetime64("2000-01-03")
    d = date.astype("datetime64[D]")
    return np.busday_count(base, d) + 2 * np.busday_count(base, d, weekmask="0010000")


def pct(x, q):
    """Quantile q dei 252 valori precedenti (s escluso), almeno 200 presenti."""
    return pd.Series(x).rolling(252, min_periods=200).quantile(q).shift(1).to_numpy()


def inizio(cond):
    c = np.asarray(cond, bool)
    return c & ~np.r_[False, c[:-1]]


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
    return dict(o=o, c=c, atr=atr, date=d.index, n=n, es=es)


def indicatori(d, P):
    c = P["c"]
    vix = d["vix"].to_numpy(float)
    gvz = d["gvz"].to_numpy(float)
    lr = np.r_[np.nan, np.diff(np.log(c))]
    rv20 = pd.Series(lr).rolling(20).std().to_numpy() * math.sqrt(252) * 100
    vrp = gvz - rv20
    rap = gvz / vix
    mossa5 = np.sign(c - np.r_[np.full(5, np.nan), c[:-5]])
    mossa5 = np.nan_to_num(mossa5).astype(int)
    hi20 = pd.Series(c).rolling(20).max().shift(1).to_numpy()
    lo20 = pd.Series(c).rolling(20).min().shift(1).to_numpy()
    with np.errstate(invalid="ignore"):
        brk = np.where(c > hi20, 1, np.where(c < lo20, -1, 0))
    I = dict(vix=vix, gvz=gvz, rv20=rv20, vrp=vrp, rap=rap, mossa5=mossa5, brk=brk)
    for nome, x in (("vix", vix), ("gvz", gvz), ("vrp", vrp), ("rap", rap)):
        for q in (5, 10, 33, 50, 67, 90, 95, 99):
            I[f"{nome}_p{q}"] = pct(x, q / 100)
    return I


def gt(x, y):
    with np.errstate(invalid="ignore"):
        return np.nan_to_num(x, nan=-np.inf) > np.nan_to_num(y, nan=np.inf)


def lt(x, y):
    with np.errstate(invalid="ignore"):
        return np.nan_to_num(x, nan=np.inf) < np.nan_to_num(y, nan=-np.inf)


def griglia(I, n):
    """Lista di regole: dict con nome, famiglia, dirz (per s), finestra, stop, regime, avvio."""
    vix, gvz = I["vix"], I["gvz"]
    def_vixp = ~np.isnan(I["vix_p90"])
    def_gvzp = ~np.isnan(I["gvz_p90"])
    reg_vix = gt(vix, I["vix_p50"])
    reg_gvz = gt(gvz, I["gvz_p50"])
    regole = []

    # B1: picchi di VIX
    ev = {}
    for q in (90, 95, 99):
        ev[f"VIX>p{q}"] = (inizio(gt(vix, I[f"vix_p{q}"])), def_vixp)
    for L in (1, 3, 5):
        prev = np.r_[np.full(L, np.nan), vix[:-L]]
        for k in (0.2, 0.4):
            ev[f"VIXsalto{L}g>{int(k*100)}%"] = (inizio(gt(vix / prev - 1, k)), ~np.isnan(prev))
    for nome, (e, dfn) in ev.items():
        for dzn, dz in (("long", 1), ("short", -1)):
            dirz = np.where(e, dz, 0)
            for (a, b) in FIN_B1:
                for st in (0, 1):
                    regole.append(dict(fam="B1", evento=nome, dir=dzn, a=a, b=b, stop=st,
                                       dirz=dirz, regime=reg_vix, definito=dfn, eventi=e))
    # B2a: eventi GVZ
    prevg = np.r_[np.full(5, np.nan), gvz[:-5]]
    evg = {"GVZ>p90": inizio(gt(gvz, I["gvz_p90"])), "GVZ>p95": inizio(gt(gvz, I["gvz_p95"])),
           "GVZ<p10": inizio(lt(gvz, I["gvz_p10"])), "GVZsalto5g>20%": inizio(gt(gvz / prevg - 1, 0.2))}
    dfg = {"GVZsalto5g>20%": ~np.isnan(prevg)}
    m5 = I["mossa5"]
    for nome, e in evg.items():
        for dzn in ("long", "short", "rientro", "segue"):
            dz = {"long": np.ones(n, int), "short": -np.ones(n, int), "rientro": -m5, "segue": m5}[dzn]
            dirz = np.where(e, dz, 0)
            for (a, b) in FIN_EV:
                for st in (0, 1):
                    regole.append(dict(fam="B2a", evento=nome, dir=dzn, a=a, b=b, stop=st,
                                       dirz=dirz, regime=reg_gvz, definito=dfg.get(nome, def_gvzp),
                                       eventi=e))
    # B2b: GVZ / VRP come filtro di regime
    regimi = {"nessuno": np.ones(n, bool),
              "VRPalto": gt(I["vrp"], I["vrp_p67"]), "VRPbasso": lt(I["vrp"], I["vrp_p33"]),
              "GVZalto": gt(gvz, I["gvz_p67"]), "GVZbasso": lt(gvz, I["gvz_p33"])}
    def_vrp = ~np.isnan(I["vrp_p67"])
    for base, H in (("LONG", 1), ("LONG", 5), ("LONG", 20), ("BRK20", 5), ("BRK20", 10), ("BRK20", 20)):
        dz0 = np.ones(n, int) if base == "LONG" else I["brk"]
        for rn, rm in regimi.items():
            dfn = (def_vrp if rn.startswith("VRP") else def_gvzp) if rn != "nessuno" else def_vrp
            for st in (0, 1):
                regole.append(dict(fam="B2b", evento=f"{base}|{rn}", dir="long" if base == "LONG" else "brk",
                                   a=1, b=H, stop=st, dirz=np.where(rm, dz0, 0), regime=rm,
                                   definito=dfn, eventi=rm & (dz0 != 0)))
    # B3: interazione VIX/GVZ
    vix90 = gt(vix, I["vix_p90"])
    evi = {"VIX>p90&GVZ<=p50": inizio(vix90 & ~gt(gvz, I["gvz_p50"]) & def_gvzp),
           "VIX>p90&GVZ>p90": inizio(vix90 & gt(gvz, I["gvz_p90"])),
           "GVZ/VIX>p95": inizio(gt(I["rap"], I["rap_p95"])),
           "GVZ/VIX<p5": inizio(lt(I["rap"], I["rap_p5"]))}
    def_rap = ~np.isnan(I["rap_p95"])
    for nome, e in evi.items():
        for dzn in ("long", "short", "rientro"):
            dz = {"long": np.ones(n, int), "short": -np.ones(n, int), "rientro": -m5}[dzn]
            dirz = np.where(e, dz, 0)
            for (a, b) in FIN_EV:
                for st in (0, 1):
                    regole.append(dict(fam="B3", evento=nome, dir=dzn, a=a, b=b, stop=st, dirz=dirz,
                                       regime=reg_vix, definito=def_rap if "/" in nome else def_gvzp,
                                       eventi=e))
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


def valuta(P, R, rng):
    es, n, date = P["es"], P["n"], P["date"]
    a, b, st = R["a"], R["b"], R["stop"]
    s, dz = operazioni(P, R)
    elig = ~np.isnan(es[(a, b, st, 1)]["netto"]) & R["definito"]
    if not elig.any():
        return None, None
    s0 = int(np.argmax(elig))
    mesi = pd.period_range(date[s0].to_period("M"), "2017-12", freq="M")
    sl = es[(a, b, st, 1)]["netto"][elig]
    r = dict(fam=R["fam"], evento=R["evento"], dir=R["dir"], a=a, b=b, stop=st, n=len(s),
             op_mese=len(s) / len(mesi), sempre_long_R=float(np.mean(sl)),
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
    # placebo date (nel regime e qualsiasi): stessa direzione e gestione
    out = {}
    for nome, pool_mask in (("reg", elig & R["regime"]), ("tutte", elig)):
        pool = np.nonzero(pool_mask)[0]
        if len(pool) < 20:
            out[nome] = np.full(NPLAC, np.inf)
            continue
        pick = pool[rng.integers(0, len(pool), (NPLAC, len(s)))]
        nl = es[(a, b, st, 1)]["netto"][pick]
        ns = es[(a, b, st, -1)]["netto"][pick]
        out[nome] = np.where(dz[None, :] == 1, nl, ns).sum(1)
    r["p_dir"] = (1 + (pdir >= tot).sum()) / (NPLAC + 1)
    r["p_reg"] = (1 + (out["reg"] >= tot).sum()) / (NPLAC + 1)
    r["p_date"] = (1 + (out["tutte"] >= tot).sum()) / (NPLAC + 1)
    r["plac_reg_medio_R"] = float(np.mean(out["reg"]) / len(s))
    return r, op


def studio_eventi(P, I, regole):
    """Rendimento lordo in R (close->close) dopo gli eventi B1, per tratti."""
    c, atr, n = P["c"], P["atr"], P["n"]
    tratti = [(0, 1), (1, 3), (3, 5), (5, 10), (10, 20), (0, 5), (0, 20)]
    eventi = {}
    for R in regole:
        if R["fam"] == "B1":
            eventi[R["evento"]] = (R["eventi"], R["definito"])
    righe = []
    base = np.arange(n)
    valido = (~np.isnan(atr)) & (base + 20 < n)
    for nome, (e, dfn) in eventi.items():
        s = np.nonzero(e & valido & dfn)[0]
        ep = episodi(s)
        prima = s[np.r_[True, np.diff(ep) > 0]] if len(s) else s
        tutti_def = np.nonzero(valido & dfn)[0]
        for (k0, k1) in tratti:
            ret = lambda ii: (c[ii + k1] - c[ii + k0]) / (2 * atr[ii])
            x = ret(prima)
            u = ret(tutti_def)
            righe.append(dict(evento=nome, tratto=f"{k0+1}-{k1}", n_eventi=len(s), episodi=len(prima),
                              medio_R=x.mean(), t=x.mean() / x.std(ddof=1) * math.sqrt(len(x)) if len(x) > 2 else np.nan,
                              quota_su=(x > 0).mean(), incond_R=u.mean(),
                              medio_tutti_R=ret(s).mean()))
    return pd.DataFrame(righe), {k: P["date"][np.nonzero(v[0] & valido & v[1])[0]] for k, v in eventi.items()}


def main():
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    os.makedirs(OUT, exist_ok=True)
    d = carica()
    P = esiti(d)
    I = indicatori(d, P)
    regole = griglia(I, P["n"])
    print(f"regole: {len(regole)}  per famiglia: "
          + str(pd.Series([R['fam'] for R in regole]).value_counts().to_dict()))
    rng = np.random.default_rng(SEED)
    righe, ops = [], []
    for i, R in enumerate(regole):
        r, op = valuta(P, R, rng)
        if r is None:
            continue
        r["id"] = i
        righe.append(r)
        if op is not None:
            op["id"] = i
            ops.append(op)
    V = pd.DataFrame(righe)
    O = pd.concat(ops, ignore_index=True)
    fissa = V["dir"].isin(["long", "short"])
    V["passa"] = ((V["netto_R"] > 0) & (V["netto15_R"] > 0) & (V["t_mens"] >= 3) & (V["anni_pos"] >= 7)
                  & (V["p_dir"] < 0.01) & (~fissa | (V["p_reg"] < 0.01)))
    V.to_parquet(os.path.join(OUT, "b_varianti.parquet"))
    O.to_parquet(os.path.join(OUT, "b_operazioni.parquet"))
    E, date_ev = studio_eventi(P, I, regole)
    E.to_parquet(os.path.join(OUT, "b_eventi_vix.parquet"))
    # sempre long per finestra (2010-2017, stessa gestione)
    sl = []
    for (a, b) in FINESTRE:
        for st in (0, 1):
            x = P["es"][(a, b, st, 1)]
            ok = ~np.isnan(x["netto"]) & (P["date"].year >= 2010)
            sl.append(dict(a=a, b=b, stop=st, netto_R=np.nanmean(x["netto"][ok]),
                           netto_usd=np.nanmean(x["usd"][ok]), n=int(ok.sum())))
    SL = pd.DataFrame(sl)
    SL.to_parquet(os.path.join(OUT, "b_sempre_long.parquet"))

    # --- stampa compatta
    V["tot"] = 1
    g = V.groupby("fam").agg(var=("tot", "sum"), netpos=("netto_R", lambda x: (x > 0).mean()),
                             t_med=("t_mens", "median"), t_max=("t_mens", "max"), t_min=("t_mens", "min"),
                             t3=("t_mens", lambda x: (x >= 3).sum()), tm3=("t_mens", lambda x: (x <= -3).sum()),
                             passa=("passa", "sum"))
    print(g.round(3).to_string())
    cols = ["fam", "evento", "dir", "a", "b", "stop", "n", "episodi", "netto_R", "netto15_R", "netto_usd",
            "t_mens", "t_ep", "anni_pos", "dd_R", "p_dir", "p_reg", "sl"]
    V["t_ep"] = V["t_episodi"]
    V["sl"] = V["sempre_long_R"]
    print("-- migliori 12 per t mensile")
    print(V.sort_values("t_mens", ascending=False)[cols].head(12).round(3).to_string(index=False))
    print("-- peggiori 5")
    print(V.sort_values("t_mens")[cols].head(5).round(3).to_string(index=False))
    print("-- passano:", int(V["passa"].sum()))
    print("-- episodi indipendenti per evento B1 (gap > 20 giornate):")
    print({k: (len(v), int(episodi(np.searchsorted(P['date'], v)).max()) if len(v) else 0,
               sorted(set(v.year))) for k, v in date_ev.items()})
    print("-- studio d'evento (primo evento di ogni episodio), medio_R / t")
    pv = E.pivot(index="evento", columns="tratto", values="medio_R")
    pt = E.pivot(index="evento", columns="tratto", values="t")
    print(pv[["1-1", "2-3", "4-5", "6-10", "11-20", "1-20"]].round(3).to_string())
    print(pt[["1-1", "2-3", "4-5", "6-10", "11-20", "1-20"]].round(2).to_string())
    print("incond:", E.groupby("tratto")["incond_R"].first().round(3).to_dict())
    print("-- sempre long 2010-2017")
    print(SL.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
