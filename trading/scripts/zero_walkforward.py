"""Ricerca da zero: walk-forward dal 2009 sulle famiglie 1-5 dell'oro.

Protocollo vincolante: docs/walkforward-registrazione.md (commit 4cdfcca,
conteggio dell'universo in 66ca0f4). Studio: docs/studies/zero/walkforward.md.

Le operazioni di ogni variante si generano con le funzioni degli script di
scoperta, importate e NON modificate (zero_f1_orologio, zero_f2_momentum,
zero_f3_range, zero_f4_volatilita, zero_f5_calendario), sulla serie continua
dell'oro 2009-01-01 -> 2026-07-06 (scoperta + verifica concatenate). Qui ci
sono solo: la costruzione della serie, la cattura delle singole operazioni
(dove lo script di scoperta tiene solo gli aggregati), il costo per anno
d'ingresso (0,40 $ fino al 2019, poi SPREAD di verifica_bot.py), la procedura
walk-forward (regole P e S), il placebo finale e il "compra e tieni".

Uso (un solo comando per l'intero studio):
  python trading/scripts/zero_walkforward.py tutto
Passi singoli: dati | universo | riproduci | operazioni | walkforward

Uscite in D:\\ricerca_zero\\walkforward\\ (dati\\ per la serie concatenata).
"""
from __future__ import annotations

import gc
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)

import zero_f1_orologio as f1        # noqa: E402
import zero_f2_momentum as f2        # noqa: E402
import zero_f3_range as f3           # noqa: E402
import zero_f4_volatilita as f4      # noqa: E402
import zero_f5_calendario as f5      # noqa: E402

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

SYM = "XAUUSD"
SCOP = Path(r"D:\ricerca_zero\scoperta")
VER = Path(r"D:\ricerca_zero\verifica")
RIS = Path(r"D:\ricerca_zero\risultati")
WF = Path(r"D:\ricerca_zero\walkforward")
DATI = WF / "dati"
TMP_RIPRODUCI = WF / "tmp_riproduci"
# copia di trading/scripts/verifica_bot.py (SPREAD); controllata in main()
SPREAD = {2020: 0.35, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}
COSTO_BASE = 0.40
ANNI_WF = list(range(2012, 2027))
MIN_OP_ANNO = 10           # anni che contano nella regola P (>= 10 operazioni)
SEED_PLACEBO = 20261003
N_PLACEBO = 1000
FAMIGLIE = ["f1", "f2", "f3", "f4", "f5"]
COLONNE = ["famiglia", "variante", "nmin", "ts", "ts_uscita", "anno", "dir", "entrata",
           "lordo", "lordo_opp", "costo", "netto", "netto_pct", "netto_opp_pct"]


def costo_anno(anni, per_anno: bool) -> np.ndarray:
    anni = np.asarray(anni, dtype=np.int64)
    if not per_anno:
        return np.full(len(anni), COSTO_BASE, float)
    return np.array([COSTO_BASE if a <= 2019 else SPREAD[int(a)] for a in anni], float)


def anno_di(ts_ns) -> np.ndarray:
    return pd.to_datetime(np.asarray(ts_ns, dtype=np.int64), utc=True).year.to_numpy()


def chiudi(fam, variante, nmin, ts, ts_uscita, dirz, entrata, lordo, lordo_opp, costo) -> pd.DataFrame:
    """Tabella operazioni con lo schema comune (ts in ns UTC)."""
    ts = np.asarray(ts, dtype=np.int64)
    if ts_uscita is None:
        ts_uscita = np.full(len(ts), np.iinfo(np.int64).min)      # NaT
    op = pd.DataFrame({"famiglia": fam, "variante": variante, "nmin": int(nmin),
                       "ts": pd.to_datetime(ts, utc=True),
                       "ts_uscita": pd.to_datetime(np.asarray(ts_uscita, dtype=np.int64), utc=True),
                       "anno": anno_di(ts), "dir": np.asarray(dirz, float),
                       "entrata": np.asarray(entrata, float), "lordo": np.asarray(lordo, float),
                       "lordo_opp": np.asarray(lordo_opp, float), "costo": np.asarray(costo, float)})
    op["netto"] = op.lordo - op.costo
    op["netto_pct"] = op.netto / op.entrata * 100
    op["netto_opp_pct"] = (op.lordo_opp - op.costo) / op.entrata * 100
    return op[COLONNE]


# ================================================================ dati
def dati():
    """Serie continua 2009 -> 2026: scoperta + verifica, un timeframe alla volta."""
    DATI.mkdir(parents=True, exist_ok=True)
    for tf in ("M5", "M15", "H1", "D1"):
        a = pd.read_parquet(SCOP / f"{SYM}_{tf}.parquet")
        b = pd.read_parquet(VER / f"{SYM}_{tf}.parquet")
        assert a.index[-1] < b.index[0]
        x = pd.concat([a, b])
        x = x[~x.index.duplicated()].sort_index()
        x.to_parquet(DATI / f"{SYM}_{tf}.parquet")
        print(f"{tf}: {len(x)} candele {x.index[0]} -> {x.index[-1]} (scoperta {len(a)} + verifica {len(b)})")
        del a, b, x
        gc.collect()


# ================================================================ universo
def universo() -> pd.DataFrame:
    """Elenco delle varianti dell'oro per famiglia, dai parquet di scoperta."""
    v1 = pd.read_parquet(RIS / "f1_varianti.parquet")
    v1 = v1[v1.mercato == SYM]
    u1 = pd.DataFrame({"famiglia": "f1", "variante": (v1.blocco + "|" + v1.variante).values,
                       "id_scoperta": v1.id.astype(str).values, "nmin": 100})
    v2 = pd.read_parquet(RIS / "f2_faseb.parquet")
    v2 = v2[v2.mercato == SYM].reset_index(drop=True)
    lento = v2.L.isin(["1g", "5g"]) | v2.H.isin(["1g", "5g"])
    u2 = pd.DataFrame({"famiglia": "f2", "variante": nome_f2(v2), "id_scoperta": v2.index.astype(str),
                       "nmin": np.where(lento, 100, 200)})
    v3 = pd.read_parquet(RIS / "f3_varianti.parquet")
    v3 = v3[v3.simbolo == SYM]
    u3 = pd.DataFrame({"famiglia": "f3", "variante": v3.variante.values, "id_scoperta": v3.variante.values, "nmin": 100})
    v4 = pd.read_parquet(RIS / "f4_varianti.parquet")
    v4 = v4[v4.mercato == SYM]
    u4 = pd.DataFrame({"famiglia": "f4", "variante": v4.vid.values, "id_scoperta": v4.vid.values, "nmin": 100})
    v5 = pd.read_parquet(RIS / "f5_varianti.parquet")
    v5 = v5[v5.sim == SYM]
    u5 = pd.DataFrame({"famiglia": "f5", "variante": (v5.fam + "|" + v5.regola + "|" + v5.dir).values,
                       "id_scoperta": v5.id.astype(str).values, "nmin": 100})
    U = pd.concat([u1, u2, u3, u4, u5], ignore_index=True)
    assert U.variante.is_unique
    # conteggio combinatorio delle dichiarazioni (docs/studies/zero/f*.md)
    attesi = {"f1": 48 + 6 + 36 + 4 + 30, "f2": 33 * 12, "f3": 216 + 216, "f4": 56 + 32 + 16, "f5": 10 + 38 + 10}
    cnt = U.groupby("famiglia").size().to_dict()
    assert cnt == attesi, (cnt, attesi)
    print("universo oro:", cnt, "totale", len(U))
    return U


def nome_f2(v: pd.DataFrame) -> np.ndarray:
    return (v.L + "->" + v.H + "|" + v.sessione + "|k" + v.k.astype(float).map("{:.0f}".format)
            + "|" + v.regime + "|" + v.direzione).values


# ================================================================ famiglia 1
def ops_f1(cart: Path, per_anno: bool) -> pd.DataFrame:
    """f1.regole con una `record` che cattura le operazioni invece degli aggregati."""
    h1 = f1.correggi_ora(pd.read_parquet(cart / f"{SYM}_H1.parquet"), SYM)
    m5 = f1.correggi_ora(pd.read_parquet(cart / f"{SYM}_M5.parquet"), SYM)
    px = f1.Px(m5)
    del m5
    cattura = []

    def record(blocco, mkt, nome, m, d, price, ts):
        sel = np.isfinite(m) & (d != 0) & np.isfinite(price)
        cattura.append((f"{blocco}|{nome}", m[sel], d[sel].astype(float), price[sel], ts[sel]))

    orig = f1.record
    f1.record = record
    try:
        f1.regole(SYM, h1, px)
    finally:
        f1.record = orig
    del h1, px
    gc.collect()
    parti = []
    for nome, m, d, p, ts in cattura:
        c = costo_anno(anno_di(ts), per_anno)
        parti.append(chiudi("f1", nome, 100, ts, None, d, p, d * m, -d * m, c))
    return pd.concat(parti, ignore_index=True)


# ================================================================ famiglia 2
def ops_f2(cart: Path, per_anno: bool, controlla: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stessa selezione di f2.regola (copiata riga per riga, come in zero_verifica.h1),
    con le singole operazioni; `controlla` confronta n e lordo con f2.regola stessa."""
    f2.SCOP = cart
    P = f2.prepara(SYM)
    del P["Y"], P["TEX"]
    gc.collect()
    lab, o, *_ = f2.carica(SYM)
    ent_all, _ = f2.o_fwd(lab, o, P["t"], 30)
    del lab, o
    gc.collect()
    V = pd.read_parquet(RIS / "f2_faseb.parquet")
    V = V[V.mercato == SYM].reset_index(drop=True)
    nomi = nome_f2(V)
    parti, ctrl = [], []
    for i, r in V.iterrows():
        L, H, sn, k, regime = r.L, r.H, r.sessione, float(r.k), r.regime
        segno = 1 if r.direzione == "a favore" else -1
        nmin = 100 if (L in ("1g", "5g") or H in ("1g", "5g")) else 200
        j = list(f2.SESS).index(sn)
        step = min(f2.ORIZ[L][0] if f2.ORIZ[L][1] == 0 else 60, 60)
        x, g = P["X"][L], P["YR"][H]
        m = (P["t"] % step == 0) & (P["sess"] == j) & np.isfinite(x) & np.isfinite(g) & (np.abs(x) >= k)
        if regime != "tutti":
            m &= P["reg"] == f2.REGIMI.index(regime) - 1
        idx = np.flatnonzero(m)
        if len(idx) == 0:
            ctrl.append(dict(variante=nomi[i], n=0, n_regola=0, lordo=np.nan, lordo_regola=np.nan))
            continue
        ts, exl = P["t"][idx], P["EXLAB"][H][idx]
        pres, q = [], 0
        while q < len(idx):
            pres.append(q)
            q = int(np.searchsorted(ts, exl[q], side="left"))
            if q <= pres[-1]:
                q = pres[-1] + 1
        sel = idx[np.asarray(pres)]
        d = np.sign(x[sel]) * segno
        mov = g[sel]
        ts_ent = P["entlab"][sel] * 60 * 10**9
        ts_usc = P["EXLAB"][H][sel] * 60 * 10**9
        c = costo_anno(anno_di(ts_ent), per_anno)
        op = chiudi("f2", nomi[i], nmin, ts_ent, ts_usc, d, ent_all[sel], d * mov, -d * mov, c)
        parti.append(op)
        if controlla:
            u = f2.regola(P, SYM, L, H, sn, k, regime, segno)
            ctrl.append(dict(variante=nomi[i], n=len(op), n_regola=u["n"], lordo=op.lordo.mean(), lordo_regola=u["lordo"]))
    del P, ent_all
    gc.collect()
    return pd.concat(parti, ignore_index=True), pd.DataFrame(ctrl)


# ================================================================ famiglia 3
def ops_f3(cart: Path, per_anno: bool, out: Path) -> pd.DataFrame:
    """f3.studia con una `valuta` che cattura le operazioni (simulazione = f3.simula)."""
    def valuta(sim, arr, sig, ses_date, regime, costo, tag, stops, uscite, righe, dett):
        t, o, h, l, c = arr
        if len(sig) == 0:
            return
        e, z, d, q = sig.e.values, sig.z.values, sig.d.values, sig.q.values
        reg = regime[q].astype(str)
        ts_e = t[e]
        cst = costo_anno(anno_di(ts_e), per_anno)
        for sn, fs in stops.items():
            R = fs(sig)
            okr = np.isfinite(R) & (R >= f3.MIN_R_COSTI * cst)
            for un, fu in uscite.items():
                T = fu(sig, R)
                ee, zz, dd, RR, TT = e[okr], z[okr], d[okr], R[okr], T[okr]
                g1 = f3.simula(o, h, l, c, ee, zz, dd, RR, TT)
                g2 = f3.simula(o, h, l, c, ee, zz, -dd, RR, TT)
                dett.append(pd.DataFrame({"base": "|".join(tag + [sn, un]), "ts": ts_e[okr],
                                          "ts_fine": t[zz] + f3.M5.value, "dir": dd.astype(float),
                                          "entrata": o[ee], "R": RR, "lordo": g1, "lordo_opp": g2,
                                          "costo": cst[okr], "regime": reg[okr]}))

    orig_v, orig_s, orig_r = f3.valuta, f3.SCOPERTA, f3.RISULTATI
    f3.valuta, f3.SCOPERTA, f3.RISULTATI = valuta, cart, out
    try:
        fuso = f3.studia(SYM, [])
    finally:
        f3.valuta, f3.SCOPERTA, f3.RISULTATI = orig_v, orig_s, orig_r
    print(f"  f3 controllo fuso: {fuso}")
    D = pd.read_parquet(out / f"f3_dettaglio_{SYM}.parquet")
    parti = []
    for rg in ("tutti", "piccolo", "grande"):
        x = D if rg == "tutti" else D[D.regime == rg]
        op = chiudi("f3", (x.base + "|" + rg).values, 100, x.ts.values, x.ts_fine.values, x.dir.values,
                    x.entrata.values, x.lordo.values, x.lordo_opp.values, x.costo.values)
        op["R"] = x.R.values
        parti.append(op)
    del D
    gc.collect()
    return pd.concat(parti, ignore_index=True)


# ================================================================ famiglia 4
def ops_f4(cart: Path, per_anno: bool) -> pd.DataFrame:
    """Ciclo di f4.main per oro/22-22 con le funzioni di f4; costo per anno d'ingresso.
    f4.esiti e f4.prepara_rottura si chiamano con costo 0 (danno lordo e lordo opposto);
    lo scarto 'rischio < 2 costi' e il netto si applicano qui con il costo dell'anno."""
    f4.SCOPERTA = cart
    d = f4.carica(SYM)
    f4.O, f4.H, f4.L, f4.C = (d[c].values.astype(np.float64) for c in ("open", "high", "low", "close"))
    f4.TS = d.index
    g = f4.tabella_giorni(d, "22-22", SYM)
    del d
    gc.collect()
    TSns = f4.TS.as_unit("ns").asi8
    fA, reg = f4.filtri(g)
    ev0 = f4.eventi_rottura(g, 0.0)
    mg = f"{SYM}/22-22"
    parti = []

    def raccogli(tr, vid):
        if len(tr) == 0:
            return
        ts = TSns[tr.i0.values]
        c = costo_anno(anno_di(ts), per_anno)
        op = chiudi("f4", vid, 100, ts, TSns[tr.jexit.values] + 5 * 60 * 10**9, tr.dir.values,
                    tr.entrata.values, tr.lordo.values, tr.netR_opp.values * tr.R.values, c)
        op["R"] = tr.R.values
        parti.append(op)

    for stop in f4.STOP_A:
        for xn, (ng, tgt) in f4.USCITE_A.items():
            ev = f4.prepara_rottura(g, ev0, stop, ng, 0.0)
            cst = costo_anno(anno_di(TSns[ev.i0.values]), per_anno)
            ev = ev[ev.R.values >= f4.MIN_R_COSTI * cst]
            ev = f4.esiti(ev, 0.0, tgt)
            for fn, fm in fA.items():
                raccogli(f4.non_sovrapposte(ev[fm[ev.k.values]]), f"a|{mg}|{fn}|{stop}|{xn}")
            if xn in ("X1", "X3"):
                for rn, rm in reg.items():
                    raccogli(f4.non_sovrapposte(ev[rm[ev.k.values]]), f"c|{mg}|{rn}|{stop}|{xn}")
    # (b) giornate estreme: stesso codice di f4.main
    for en_, (kind, kk) in f4.ESTREMI.items():
        if kind == "rng":
            m = (g.rng > kk * g.atr_pre).values
            sg = np.sign(g.C - g.O).values
        else:
            ret = (g.C - g.C.shift(1)).values
            m = np.abs(ret) > kk * g.atr_pre.values
            sg = np.sign(ret)
        ks = np.flatnonzero(m & (sg != 0))
        ks = ks[(ks >= 20) & (ks < len(g) - 1)]
        for sm in f4.STOP_B:
            for ng in f4.USCITE_B:
                kk2 = ks + ng
                ok = kk2 < len(g)
                evb = pd.DataFrame({"k": ks[ok], "i0": g.st.values[ks[ok] + 1],
                                    "iend": g.en.values[kk2[ok]], "dir": sg[ks[ok]].astype(int),
                                    "R": sm * g.atr_pre.values[ks[ok]]})
                cst = costo_anno(anno_di(TSns[evb.i0.values]), per_anno)
                evb = evb[evb.R.values >= f4.MIN_R_COSTI * cst]
                for dn, ds in (("CONT", 1), ("REV", -1)):
                    e2 = evb.assign(dir=evb.dir * ds)
                    e2 = f4.non_sovrapposte(f4.esiti(e2, 0.0, None))
                    raccogli(e2, f"b|{mg}|{en_}|{dn}|{sm}ATR|X{ng}")
    f4.O = f4.H = f4.L = f4.C = f4.TS = None
    del g, ev0
    gc.collect()
    return pd.concat(parti, ignore_index=True)


# ================================================================ famiglia 5
def ops_f5(cart: Path, per_anno: bool) -> pd.DataFrame:
    """Finestre e ancoraggi di f5 (oro, giornata 22-22), operazioni singole con costo per anno."""
    f5.SCOPERTA = cart
    d = f5.carica(SYM)
    ts = d.index.as_unit("ns").asi8
    g = f5.giornate(d, "22-22", SYM)
    del d
    gc.collect()
    F = f5.Finestre(g, COSTO_BASE)
    st, en = g.st.values, g.en.values
    i_l2 = np.searchsorted(ts, ts[en] - f5.DUE_ORE, side="left")
    i_f2 = np.searchsorted(ts, ts[st] + f5.DUE_ORE, side="left")
    idx_prezzo = {"Pc": en, "Po": st, "Pl2": np.minimum(i_l2, len(ts) - 1), "Pf2": np.minimum(i_f2, len(ts) - 1)}
    parti = []
    for (fam, nome), (wt, anc, Ls) in f5.ancoraggi(g).items():
        if fam == "a" and wt == "OC":
            continue                      # giornata 22-22: solo CC (come f5.main)
        if fam == "d":
            continue                      # solo S&P/Nasdaq
        pe, pu = f5.TIPI[wt]
        for dirz in (1, -1):
            ent, usc, lg, ie, iu = [], [], [], [], []
            for a, L in zip(anc, Ls):
                e, u, lordo, _, ok = F.arr(wt, int(L))
                if 0 <= a < F.N and ok[a]:
                    ent.append(e[a]); usc.append(u[a]); lg.append(lordo[a])
                    ie.append(idx_prezzo[pe][a]); iu.append(idx_prezzo[pu][a + L])
            if len(ent) < 2:
                continue
            ent, usc = np.array(ent), np.array(usc)
            ts_e, ts_u = ts[np.array(ie)], ts[np.array(iu)]
            c = costo_anno(anno_di(ts_e), per_anno)
            lordo_px = dirz * (usc - ent)
            vid = f"{fam}|{nome}|{'long' if dirz > 0 else 'short'}"
            parti.append(chiudi("f5", vid, 100, ts_e, ts_u, np.full(len(ent), float(dirz)), ent,
                                lordo_px, -lordo_px, c))
    del g, F
    gc.collect()
    return pd.concat(parti, ignore_index=True)


# ================================================================ generazione e confronto
def genera(cart: Path, per_anno: bool, out: Path, controlla_f2: bool) -> tuple[dict, pd.DataFrame]:
    out.mkdir(parents=True, exist_ok=True)
    ops, ctrl2 = {}, None
    for fam in FAMIGLIE:
        t0 = time.time()
        if fam == "f1":
            o = ops_f1(cart, per_anno)
        elif fam == "f2":
            o, ctrl2 = ops_f2(cart, per_anno, controlla_f2)
        elif fam == "f3":
            o = ops_f3(cart, per_anno, out)
        elif fam == "f4":
            o = ops_f4(cart, per_anno)
        else:
            o = ops_f5(cart, per_anno)
        o.to_parquet(out / f"operazioni_{fam}.parquet", index=False)
        ops[fam] = o
        print(f"  {fam}: {o.variante.nunique()} varianti, {len(o)} operazioni, "
              f"{o.ts.min():%Y-%m-%d} -> {o.ts.max():%Y-%m-%d} ({time.time() - t0:.0f}s)", flush=True)
        gc.collect()
    return ops, ctrl2


def confronto_scoperta(ops: dict, U: pd.DataFrame, fine: pd.Timestamp | None) -> pd.DataFrame:
    """Per ogni variante: n e netto (unita' dello script di scoperta, costo 0,40) delle operazioni
    con ingresso < `fine` contro i parquet di scoperta. Ritorna una riga per variante."""
    righe = []
    for fam in FAMIGLIE:
        o = ops[fam]
        if fine is not None:
            o = o[o.ts < fine]
        o = o.assign(netto040=o.lordo - COSTO_BASE)
        if fam == "f1":
            V = pd.read_parquet(RIS / "f1_varianti.parquet")
            V = V[V.mercato == SYM].assign(variante=lambda v: v.blocco + "|" + v.variante)[["variante", "n", "netto"]]
            mio = o.groupby("variante").netto040.agg(n_mio="size", netto_mio="mean")
        elif fam == "f2":
            V = pd.read_parquet(RIS / "f2_faseb.parquet")
            V = V[V.mercato == SYM].reset_index(drop=True)
            V = pd.DataFrame({"variante": nome_f2(V), "n": V.n.values, "netto": V.netto.values})
            mio = o.groupby("variante").netto040.agg(n_mio="size", netto_mio="mean")
        elif fam == "f3":
            V = pd.read_parquet(RIS / "f3_varianti.parquet")
            V = V[V.simbolo == SYM][["variante", "n", "netto_R"]].rename(columns={"netto_R": "netto"})
            mio = (o.netto040 / o.R).groupby(o.variante).agg(n_mio="size", netto_mio="mean")
        elif fam == "f4":
            V = pd.read_parquet(RIS / "f4_varianti.parquet")
            V = V[V.mercato == SYM][["vid", "n", "netR"]].rename(columns={"vid": "variante", "netR": "netto"})
            mio = (o.netto040 / o.R).groupby(o.variante).agg(n_mio="size", netto_mio="mean")
        else:
            V = pd.read_parquet(RIS / "f5_varianti.parquet")
            V = V[V.sim == SYM]
            V = pd.DataFrame({"variante": (V.fam + "|" + V.regola + "|" + V.dir).values, "n": V.n.values,
                              "netto": V.netto_px.values})
            mio = o.groupby("variante").netto040.agg(n_mio="size", netto_mio="mean")
        x = U[U.famiglia == fam][["famiglia", "variante"]].merge(V, on="variante", how="left")
        x = x.merge(mio.reset_index(), on="variante", how="left")
        x["n_mio"] = x.n_mio.fillna(0).astype(int)
        x["n"] = x.n.fillna(0).astype(int)
        x["coincide"] = (x.n == x.n_mio) & ((x.netto - x.netto_mio).abs().fillna(0) < 1e-9)
        x.loc[(x.n == 0) & (x.n_mio == 0), "coincide"] = True
        righe.append(x)
    return pd.concat(righe, ignore_index=True)


def stampa_confronto(C: pd.DataFrame, titolo: str):
    print(f"\n{titolo}")
    s = C.groupby("famiglia").agg(varianti=("variante", "size"), coincidono=("coincide", "sum"),
                                  n_scop=("n", "sum"), n_mio=("n_mio", "sum"))
    s["max_diff_n"] = C.assign(d=(C.n - C.n_mio).abs()).groupby("famiglia").d.max()
    s["max_diff_netto"] = C.assign(d=(C.netto - C.netto_mio).abs()).groupby("famiglia").d.max()
    print(s.round(6).to_string())
    print("TUTTE COINCIDONO" if C.coincide.all() else f"NON coincidono {int((~C.coincide).sum())} varianti")


def riproduci():
    """Passo di controllo: operazioni sulla sola cartella scoperta, costo 0,40, contro i parquet di scoperta."""
    U = universo()
    print("riproduzione sulla sola scoperta (costo costante 0,40):")
    ops, ctrl2 = genera(SCOP, False, TMP_RIPRODUCI, controlla_f2=True)
    C = confronto_scoperta(ops, U, None)
    C.to_parquet(WF / "riproduzione.parquet", index=False)
    stampa_confronto(C, "confronto con i parquet di scoperta (n e netto nell'unita' di ogni script):")
    ok2 = ((ctrl2.n == ctrl2.n_regola) & ((ctrl2.lordo - ctrl2.lordo_regola).abs().fillna(0) < 1e-9)).all()
    print(f"f2: selezione copiata contro f2.regola sulle stesse P: {'identica' if ok2 else 'DIVERSA'} su {len(ctrl2)} regole")
    if not C.coincide.all():
        print(C[~C.coincide].head(20).round(6).to_string(index=False))
    del ops
    gc.collect()
    return bool(C.coincide.all() and ok2)


def operazioni():
    """Operazioni 2009-2026 di tutte le varianti sulla serie continua, costo per anno d'ingresso."""
    U = universo()
    U.to_parquet(WF / "varianti.parquet", index=False)
    print("operazioni sulla serie continua 2009-2026 (costo per anno):")
    ops, ctrl2 = genera(DATI, True, WF, controlla_f2=False)
    C = confronto_scoperta(ops, U, pd.Timestamp("2018-01-01", tz="UTC"))
    C.to_parquet(WF / "confronto_2009_2017.parquet", index=False)
    stampa_confronto(C, "operazioni 2009-2017 della serie continua contro la scoperta (costo 0,40 in entrambe):")
    if not C.coincide.all():
        d = C[~C.coincide]
        print("  varianti diverse per famiglia:", d.groupby("famiglia").size().to_dict(),
              "| differenza totale di n:", int((d.n_mio - d.n).sum()))
    del ops
    gc.collect()


# ================================================================ walk-forward
def aggregati_variante_anno() -> pd.DataFrame:
    """Per (variante, anno): n, somma e somma dei quadrati del netto %."""
    parti = []
    for fam in FAMIGLIE:
        o = pd.read_parquet(WF / f"operazioni_{fam}.parquet", columns=["famiglia", "variante", "nmin", "anno", "netto_pct"])
        a = o.groupby(["famiglia", "variante", "nmin", "anno"]).netto_pct.agg(n="size", s="sum").reset_index()
        a["s2"] = o.assign(q=o.netto_pct ** 2).groupby(["famiglia", "variante", "nmin", "anno"]).q.sum().values
        parti.append(a)
        del o
        gc.collect()
    return pd.concat(parti, ignore_index=True)


def statistiche_storia(A: pd.DataFrame, fino_a: int) -> pd.DataFrame:
    """Statistiche di ogni variante sulle operazioni con ingresso negli anni < fino_a."""
    h = A[A.anno < fino_a]
    g = h.groupby(["famiglia", "variante", "nmin"]).agg(n=("n", "sum"), s=("s", "sum"), s2=("s2", "sum")).reset_index()
    g["netto"] = g.s / g.n
    var = (g.s2 - g.n * g.netto ** 2) / (g.n - 1).clip(lower=1)
    g["t"] = np.where((g.n > 1) & (var > 0), g.netto / np.sqrt(var.clip(lower=1e-300)) * np.sqrt(g.n), np.nan)
    ha = h[h.n >= MIN_OP_ANNO]
    ya = ha.assign(pos=ha.s > 0).groupby("variante").pos.agg(anni_pos="sum", anni="size")
    g = g.merge(ya.reset_index(), on="variante", how="left")
    g["anni_pos"] = g.anni_pos.fillna(0).astype(int)
    g["anni"] = g.anni.fillna(0).astype(int)
    g["frac_anni"] = np.where(g.anni > 0, g.anni_pos / g.anni.clip(lower=1), np.nan)
    return g.drop(columns=["s", "s2"])


def scegli_P(S: pd.DataFrame) -> pd.DataFrame:
    ok = S[(S.netto > 0) & (S.t >= 3) & (S.frac_anni >= 0.75) & (S.n >= S.nmin)].sort_values("t", ascending=False)
    ok = ok.groupby("famiglia", sort=False).head(3)
    return ok.sort_values("t", ascending=False).head(10)


def scegli_S(S: pd.DataFrame) -> pd.DataFrame:
    ok = S[(S.netto > 0) & (S.n >= 100)].sort_values("t", ascending=False)
    return ok.head(5)


def carica_ops(scelte: pd.DataFrame, anno: int) -> pd.DataFrame:
    parti = []
    for fam, v in scelte.groupby("famiglia"):
        o = pd.read_parquet(WF / f"operazioni_{fam}.parquet",
                            filters=[("anno", "==", int(anno)), ("variante", "in", list(v.variante))])
        parti.append(o)
    return pd.concat(parti, ignore_index=True) if parti else pd.DataFrame(columns=COLONNE)


def t_di(x: np.ndarray) -> float:
    x = np.asarray(x, float)
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 1 and x.std(ddof=1) > 0 else np.nan


def placebo(op: pd.DataFrame, seed: int) -> float:
    """Stessi istanti, direzione casuale (esito opposto simulato dove c'e' uno stop), 1000 serie."""
    if len(op) == 0:
        return np.nan
    rng = np.random.default_rng(seed)
    a, b = op.netto_pct.to_numpy(float), op.netto_opp_pct.to_numpy(float)
    mu, hits = a.mean(), 0
    for _ in range(N_PLACEBO // 100):
        s = rng.random((100, len(a))) < 0.5
        hits += int((np.where(s, a[None, :], b[None, :]).mean(1) >= mu).sum())
    return (1 + hits) / (1 + N_PLACEBO)


def compra_e_tieni() -> pd.DataFrame:
    """Oro, giornata D1 (UTC): rendimento % per anno e per giorno, 2012-2026, senza costi."""
    d1 = pd.read_parquet(DATI / f"{SYM}_D1.parquet", columns=["close"])
    d1 = d1[d1.index.dayofweek < 5]
    r = d1.close.pct_change() * 100
    righe = []
    for y in ANNI_WF:
        x = r[r.index.year == y].dropna()
        c = d1.close[d1.index.year == y]
        prev = d1.close[d1.index.year == y - 1]
        tot = (c.iloc[-1] / prev.iloc[-1] - 1) * 100 if len(prev) else np.nan
        righe.append(dict(anno=y, giorni=len(x), rend_anno_pct=tot, medio_giorno_pct=x.mean(), t_giorno=t_di(x.values)))
    B = pd.DataFrame(righe)
    x = r[(r.index.year >= 2012)].dropna()
    tot = (d1.close.iloc[-1] / d1.close[d1.index.year == 2011].iloc[-1] - 1) * 100
    B = pd.concat([B, pd.DataFrame([dict(anno=0, giorni=len(x), rend_anno_pct=tot, medio_giorno_pct=x.mean(),
                                         t_giorno=t_di(x.values))])], ignore_index=True)
    return B


def walkforward():
    assert (WF / "varianti.parquet").exists(), "prima: operazioni"
    A = aggregati_variante_anno()
    A.to_parquet(WF / "aggregati_variante_anno.parquet", index=False)
    U = pd.read_parquet(WF / "varianti.parquet")
    assert A.variante.nunique() <= len(U)
    print(f"varianti con operazioni: {A.variante.nunique()} su {len(U)}; anni {A.anno.min()}-{A.anno.max()}")
    scelte, anni, ops_out = [], [], {"P": [], "S": []}
    for Y in ANNI_WF:
        S = statistiche_storia(A, Y)
        S.to_parquet(WF / f"storia_fino_{Y}.parquet", index=False)
        for regola, fn in (("P", scegli_P), ("S", scegli_S)):
            sc = fn(S)
            sc = sc.assign(regola=regola, anno_operato=Y)
            scelte.append(sc)
            if len(sc) == 0:
                anni.append(dict(regola=regola, anno=Y, varianti=0, n=0, netto_pct=0.0, t=np.nan, operato=False, famiglie=""))
                continue
            op = carica_ops(sc, Y)
            op = op.assign(regola=regola)
            ops_out[regola].append(op)
            anni.append(dict(regola=regola, anno=Y, varianti=len(sc), n=len(op),
                             netto_pct=op.netto_pct.mean() if len(op) else 0.0, t=t_di(op.netto_pct.values),
                             operato=True, famiglie=",".join(sorted(sc.famiglia.unique())),
                             t_storia_min=sc.t.min(), t_storia_max=sc.t.max()))
        print(f"  {Y}: P {len(scelte[-2])} varianti, S {len(scelte[-1])}", flush=True)
    SC = pd.concat(scelte, ignore_index=True)
    AN = pd.DataFrame(anni)
    SC.to_parquet(WF / "wf_scelte.parquet", index=False)
    AN.to_parquet(WF / "wf_anni.parquet", index=False)
    sintesi = []
    for regola in ("P", "S"):
        op = pd.concat(ops_out[regola], ignore_index=True) if ops_out[regola] else pd.DataFrame(columns=COLONNE)
        op.to_parquet(WF / f"wf_operazioni_{regola}.parquet", index=False)
        a = AN[(AN.regola == regola) & AN.operato]
        anni_pos = int((a.netto_pct > 0).sum()) if len(a) else 0
        # anno operato con zero operazioni = non positivo (scelta conservativa)
        n_anni = len(a)
        r = dict(regola=regola, anni_operati=n_anni, anni_non_operati=len(AN[AN.regola == regola]) - n_anni,
                 anni_pos=anni_pos, frac_anni=anni_pos / n_anni if n_anni else np.nan,
                 n=len(op), netto_pct=op.netto_pct.mean() if len(op) else np.nan,
                 netto_px=op.netto.mean() if len(op) else np.nan, lordo_pct=(op.lordo / op.entrata * 100).mean() if len(op) else np.nan,
                 t=t_di(op.netto_pct.values) if len(op) else np.nan,
                 p_placebo=placebo(op, SEED_PLACEBO + (0 if regola == "P" else 1)),
                 varianti_distinte=int(SC[SC.regola == regola].variante.nunique()))
        r["funziona"] = bool(n_anni > 0 and r["netto_pct"] > 0 and r["t"] >= 2 and r["frac_anni"] >= 2 / 3 and r["p_placebo"] < 0.01)
        # t sulla somma giornaliera (robustezza, solo descrittiva: le varianti scelte si sovrappongono)
        if len(op):
            gg = op.groupby(op.ts.dt.tz_convert("UTC").dt.normalize()).netto_pct.sum()
            r["t_giornaliero"] = t_di(gg.values)
            r["giorni_operati"] = len(gg)
        sintesi.append(r)
    SI = pd.DataFrame(sintesi)
    SI.to_parquet(WF / "wf_sintesi.parquet", index=False)
    B = compra_e_tieni()
    B.to_parquet(WF / "compra_e_tieni.parquet", index=False)
    # ------------- stampa compatta
    print("\nanni (netto medio % per operazione, t sull'anno):")
    tab = AN.pivot(index="anno", columns="regola", values=["varianti", "n", "netto_pct", "t"])
    tab.columns = [f"{a}_{b}" for a, b in tab.columns]
    tab = tab.join(B.set_index("anno")[["rend_anno_pct"]].rename(columns={"rend_anno_pct": "oro_B&H_%"}))
    print(tab.round(3).to_string())
    print("\nsintesi 2012-2026 (solo anni operati):")
    print(SI.round(4).T.to_string())
    print("\ncompra e tieni oro (D1, senza costi), 2012-2026 nel complesso (anno=0):")
    print(B[B.anno == 0].round(3).to_string(index=False))
    print("\nfamiglie scelte (quante volte una variante della famiglia e' stata scelta):")
    print(SC.groupby(["regola", "famiglia"]).size().unstack(fill_value=0).to_string())
    print("\nvarianti scelte piu' spesso:")
    print(SC.groupby(["regola", "variante"]).size().sort_values(ascending=False).groupby(level=0).head(6).to_string())


def main():
    import verifica_bot as vb
    assert vb.SPREAD == SPREAD, "SPREAD diverso da verifica_bot.py"
    passo = sys.argv[1] if len(sys.argv) > 1 else ""
    WF.mkdir(parents=True, exist_ok=True)
    if passo == "dati":
        dati()
    elif passo == "universo":
        universo()
    elif passo == "riproduci":
        riproduci()
    elif passo == "operazioni":
        operazioni()
    elif passo == "walkforward":
        walkforward()
    elif passo == "tutto":
        t0 = time.time()
        dati()
        if not riproduci():
            raise SystemExit("riproduzione della scoperta NON riuscita: fermo qui")
        operazioni()
        walkforward()
        print(f"\ntotale {time.time() - t0:.0f}s")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
