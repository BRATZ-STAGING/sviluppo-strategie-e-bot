"""Famiglia 1 FX — Notte asiatica: ritorno alla media 22:15-06:00 UTC.

Protocollo: docs/fx-intraday-registrazione.md. Rapporto: docs/studies/fx/a-notte.md.
Dati: SOLO D:\\ricerca_fx\\scoperta\\<COPPIA>_<M5|D1>.parquet (2010-2017, BID, UTC).

Fasi (una coppia alla volta, niente multiprocessing):
  python fx_a_notte.py simula      -> a_notte_operazioni_<COPPIA>.parquet, a_notte_notti_<COPPIA>.parquet
  python fx_a_notte.py aggrega     -> a_notte_regole.parquet, a_notte_coppie.parquet
  python fx_a_notte.py approfondisci -> a_notte_scelte.parquet (placebo esatto, rischio)
  python fx_a_notte.py controllo   -> confronto del motore con un ciclo candela per candela
"""
import sys
import time
import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)

DATI = r"D:\ricerca_fx\scoperta"
RIS = r"D:\ricerca_fx\risultati"
COPPIE = ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "EURJPY"]
COSTO = {"EURUSD": 0.8, "GBPUSD": 1.0, "AUDUSD": 0.9, "USDCHF": 1.0,
         "USDCAD": 1.2, "USDJPY": 1.2, "EURJPY": 1.4}
PIP = {p: (0.01 if p.endswith("JPY") else 0.0001) for p in COPPIE}

# griglia notturna: slot 0 = 22:10 UTC ... slot 93 = 05:55 UTC
NS = 94
SLOT_MEZZANOTTE = 22          # entrate con slot < 22 (22:15-23:55) pagano costo x2

SEGNALI = ([("DEV", N, k) for N in (12, 24, 48) for k in (0.06, 0.10, 0.15)]
           + [("CAN", N, x) for N in (12, 24, 48) for x in (0.0, 0.05)])
OBIETTIVI = ["CENTRO", 0.04, 0.08]
STOP = [0.10, 0.20, 0.40]
# finestra: (primo slot d'entrata, ultimo slot d'entrata, ultimo slot di gestione)
FINESTRE = {"A": (1, 69, 81), "B": (22, 69, 81), "C": (22, 87, 93)}
VOL = ["tutti", "ATRbasso", "ATRalto", "USAbasso", "USAalto"]
GIORNO = ["tutte", "noLunVen"]

CONFIG = []
for _s in SEGNALI:
    for _w in FINESTRE:
        for _t in OBIETTIVI:
            for _sl in STOP:
                CONFIG.append((_s, _w, _t, _sl))
NCFG = len(CONFIG)                       # 405
NFILT = len(VOL) * len(GIORNO)           # 10
NOTTI = pd.bdate_range("2010-01-04", "2017-12-29")
NN = len(NOTTI)
ANNI = NOTTI.year.values - 2010          # 0..7
SEED = 20261003


def nome_cfg(i):
    (tipo, N, par), w, t, sl = CONFIG[i]
    t_s = "CENTRO" if t == "CENTRO" else f"T{t:.2f}"
    return f"{tipo} N{N} {par:.2f} | {w} | {t_s} | S{sl:.2f}"


def nome_filtro(f):
    return f"{VOL[f // 2]}/{GIORNO[f % 2]}"


# ---------------------------------------------------------------- preparazione
def prepara(coppia):
    m = pd.read_parquet(f"{DATI}\\{coppia}_M5.parquet")
    d1 = pd.read_parquet(f"{DATI}\\{coppia}_D1.parquet")
    idx = m.index
    o, h, l, c = (m[k].values for k in ("open", "high", "low", "close"))
    ind = {}
    for N in (12, 24, 48):
        ind[("SMA", N)] = m["close"].rolling(N).mean().values
        ind[("HI", N)] = m["high"].rolling(N).max().shift(1).values
        ind[("LO", N)] = m["low"].rolling(N).min().shift(1).values

    tod = idx.hour.values * 60 + idx.minute.values
    notte = (tod >= 22 * 60 + 10) | (tod < 6 * 60)
    slot = ((tod - 1330) % 1440) // 5
    data_n = (idx + pd.Timedelta(minutes=110)).tz_localize(None).normalize()
    pos = NOTTI.searchsorted(data_n)
    ok = notte & (pos < NN)
    ok[ok] = NOTTI[pos[ok]] == data_n[ok]
    r, s = pos[ok], slot[ok]

    def mat(v):
        A = np.full((NN, NS), np.nan)
        A[r, s] = v[ok]
        return A

    M = {"O": mat(o), "H": mat(h), "L": mat(l), "C": mat(c)}
    for k, v in ind.items():
        M[k] = mat(v)
    Cf = pd.DataFrame(M["C"]).ffill(axis=1).values
    M["Cf"] = Cf
    valida = np.isfinite(M["O"]).sum(1) >= 30

    # ATR giornaliero causale
    d1 = d1[(d1.index.dayofweek < 5) & (d1["minuti"] >= 600)]
    pc = d1["close"].shift(1)
    tr = np.maximum(d1["high"] - d1["low"],
                    np.maximum((d1["high"] - pc).abs(), (d1["low"] - pc).abs()))
    atr = tr.rolling(14).mean()
    giorni_atr = d1.index.tz_localize(None).normalize()
    inizio = NOTTI - pd.Timedelta(days=1)           # giorno in cui la notte inizia
    j = giorni_atr.searchsorted(inizio, side="left") - 1   # ultimo giorno < inizio
    atr_n = np.where(j >= 0, atr.values[np.clip(j, 0, None)], np.nan)

    # range della sessione USA (13:00-20:45 UTC) dell'ultimo giorno feriale <= inizio
    usa = (tod >= 13 * 60) & (tod < 20 * 60 + 45) & (idx.dayofweek.values < 5)
    mu = m[usa]
    g = mu.index.tz_localize(None).normalize()
    ur = mu.groupby(g).agg(hi=("high", "max"), lo=("low", "min"), k=("high", "size"))
    ur = ur[ur["k"] >= 60]
    j2 = ur.index.searchsorted(inizio, side="right") - 1
    usr = np.where(j2 >= 0, (ur["hi"] - ur["lo"]).values[np.clip(j2, 0, None)], np.nan)
    us_rap = usr / atr_n

    def rango(v):
        out = np.full(NN, np.nan)
        storia = []
        for i in range(NN):
            if valida[i] and np.isfinite(v[i]):
                w = storia[-250:]
                if len(w) >= 60:
                    out[i] = np.mean(np.array(w) < v[i])
                storia.append(v[i])
        return out

    notti = pd.DataFrame({"data": NOTTI, "valida": valida & np.isfinite(atr_n),
                          "atr": atr_n, "us_rap": us_rap,
                          "pct_atr": rango(atr_n), "pct_usa": rango(us_rap),
                          "dow": NOTTI.dayofweek})
    return M, notti


def maschere_filtri(notti):
    v = notti["valida"].values
    pa, pu = notti["pct_atr"].values, notti["pct_usa"].values
    vol = [np.ones(NN, bool), pa <= 1 / 3, pa >= 2 / 3, pu <= 1 / 3, pu >= 2 / 3]
    dow = [np.ones(NN, bool), ~notti["dow"].isin([0, 4]).values]
    out = np.zeros((NFILT, NN), bool)
    for a in range(len(VOL)):
        for b in range(len(GIORNO)):
            out[a * 2 + b] = v & vol[a] & dow[b]
    return out


# ---------------------------------------------------------------- motore
def esito(M, n, e, d, P, dT, SL, L):
    """Esito di operazioni (vettoriale). Ritorna pnl in prezzo, slot d'uscita, tipo."""
    w = L + 1 - e.min()
    cols = e[:, None] + np.arange(w)[None, :]
    valid = cols <= L
    cc = np.minimum(cols, L)
    nn = n[:, None]
    Hm, Lm, Om = M["H"][nn, cc], M["L"][nn, cc], M["O"][nn, cc]
    dd = d[:, None]
    lungo = dd > 0
    worst = np.where(lungo, Lm, Hm)
    best = np.where(lungo, Hm, Lm)
    with np.errstate(invalid="ignore"):
        hs = (dd * (worst - P[:, None]) <= -SL[:, None]) & valid
        ht = (dd * (best - P[:, None]) >= dT[:, None]) & valid
    BIG = 10_000
    fs = np.where(hs.any(1), hs.argmax(1), BIG)
    ft = np.where(ht.any(1), ht.argmax(1), BIG)
    stop = (fs < BIG) & (fs <= ft)
    tgt = (~stop) & (ft < BIG)
    rr = np.arange(len(n))
    pnl = d * (M["Cf"][n, L] - P)
    xs = np.full(len(n), L)
    tipo = np.full(len(n), 2, np.int8)
    if stop.any():
        k = fs[stop]
        og = d[stop] * (Om[rr[stop], k] - P[stop])
        ps = -SL[stop]
        gap = (k > 0) & np.isfinite(og) & (og < ps)
        pnl[stop] = np.where(gap, og, ps)
        xs[stop] = e[stop] + k
        tipo[stop] = 0
    if tgt.any():
        pnl[tgt] = dT[tgt]
        xs[tgt] = e[tgt] + ft[tgt]
        tipo[tgt] = 1
    return pnl, xs, tipo


def candidati(M, atr, sig, w, t, costo_px):
    tipo, N, par = sig
    e_lo, e_hi, L = FINESTRE[w]
    C = M["C"]
    A = atr[:, None]
    with np.errstate(invalid="ignore"):
        if tipo == "DEV":
            centro = M[("SMA", N)]
            dev = (C - centro) / A
            dirm = np.where(dev > par, -1, np.where(dev < -par, 1, 0))
        else:
            hi, lo = M[("HI", N)], M[("LO", N)]
            centro = (hi + lo) / 2
            dirm = np.where(C > hi + par * A, -1, np.where(C < lo - par * A, 1, 0))
    dirm[:, : e_lo - 1] = 0
    dirm[:, e_hi:] = 0
    dirm[~np.isfinite(atr)] = 0
    n, s = np.nonzero(dirm)
    e = s + 1
    P = M["O"][n, e]
    d = dirm[n, s].astype(np.int8)
    if t == "CENTRO":
        dT = d * (centro[n, s] - P)
    else:
        dT = t * atr[n]
    with np.errstate(invalid="ignore"):
        keep = np.isfinite(P) & np.isfinite(dT) & (dT >= costo_px)
    return n[keep], s[keep], e[keep], d[keep], P[keep], dT[keep], L


def simula_cfg(M, atr, ci, cand_cache, costo_px):
    sig, w, t, sl = CONFIG[ci]
    key = (sig, w, t)
    if key not in cand_cache:
        cand_cache.clear()
        cand_cache[key] = candidati(M, atr, sig, w, t, costo_px)
    n, s, e, d, P, dT, L = cand_cache[key]
    Mc = len(n)
    if Mc == 0:
        return None
    keys = n.astype(np.int64) * 128 + s
    primo = np.r_[True, n[1:] != n[:-1]]
    cur = np.nonzero(primo)[0]
    out = []
    while len(cur):
        SL = sl * atr[n[cur]]
        pnl, xs, tipo = esito(M, n[cur], e[cur], d[cur], P[cur], dT[cur], SL, L)
        pm, _, _ = esito(M, n[cur], e[cur], -d[cur], P[cur], dT[cur], SL, L)
        out.append((n[cur], e[cur], xs, d[cur], pnl, pm, tipo))
        nk = n[cur].astype(np.int64) * 128 + xs
        nxt = np.searchsorted(keys, nk, side="left")
        ok = nxt < Mc
        ok[ok] = n[nxt[ok]] == n[cur][ok]
        cur = nxt[ok]
    cat = [np.concatenate(z) for z in zip(*out)]
    return cat


def fase_simula():
    for coppia in COPPIE:
        t0 = time.time()
        M, notti = prepara(coppia)
        atr = np.where(notti["valida"].values, notti["atr"].values, np.nan)
        pip = PIP[coppia]
        cb = COSTO[coppia]
        cache = {}
        parti = []
        for ci in range(NCFG):
            r = simula_cfg(M, atr, ci, cache, cb * pip)
            if r is None:
                continue
            n, e, xs, d, pnl, pm, tipo = r
            parti.append(pd.DataFrame({
                "cfg": np.int16(ci), "notte": n.astype(np.int16), "e": e.astype(np.int8),
                "x": xs.astype(np.int8), "dir": d.astype(np.int8),
                "g": (pnl / pip).astype(np.float32), "gm": (pm / pip).astype(np.float32),
                "c": np.where(e < SLOT_MEZZANOTTE, 2 * cb, cb).astype(np.float32),
                "tipo": tipo}))
        op = pd.concat(parti, ignore_index=True)
        op.to_parquet(f"{RIS}\\a_notte_operazioni_{coppia}.parquet")
        notti.to_parquet(f"{RIS}\\a_notte_notti_{coppia}.parquet")
        print(f"{coppia}: notti valide {int(notti['valida'].sum())}, operazioni {len(op):,}, "
              f"{time.time() - t0:.0f}s")
        del M, op, parti


# ---------------------------------------------------------------- aggregazione
def statistiche_notte(x, nv):
    """t su somme per notte (x: (..., NN)), nv = numero di notti valide."""
    s = x.sum(-1)
    m = s / nv
    var = ((x ** 2).sum(-1) - nv * m ** 2) / (nv - 1)
    return s, m / np.sqrt(np.maximum(var, 1e-12) / nv)


def fase_aggrega():
    P = len(COPPIE)
    G = np.zeros((NCFG, P, NN)); Cc = np.zeros_like(G); Nt = np.zeros_like(G)
    GM = np.zeros_like(G); D2 = np.zeros_like(G)
    FM = np.zeros((NFILT, P, NN), bool)
    V = np.zeros((P, NN), bool)
    for pi, coppia in enumerate(COPPIE):
        op = pd.read_parquet(f"{RIS}\\a_notte_operazioni_{coppia}.parquet")
        notti = pd.read_parquet(f"{RIS}\\a_notte_notti_{coppia}.parquet")
        FM[:, pi] = maschere_filtri(notti)
        V[pi] = notti["valida"].values
        k = op["cfg"].values.astype(np.int64) * NN + op["notte"].values
        g = op["g"].values.astype(float); gm = op["gm"].values.astype(float)
        for A, wv in ((G, g), (Cc, op["c"].values.astype(float)), (Nt, None),
                      (GM, gm), (D2, ((g - gm) / 2) ** 2)):
            A[:, pi, :] = np.bincount(k, weights=wv, minlength=NCFG * NN).reshape(NCFG, NN)
        del op
    nv_p = V.sum(1).astype(float)                   # notti valide per coppia
    nv_any = V.any(0).sum()
    Y = np.zeros((NN, 8)); Y[np.arange(NN), ANNI] = 1

    righe_r, righe_c = [], []
    for f in range(NFILT):
        Mk = FM[f][None].astype(float)
        Gf, Cf_, Nf, GMf, D2f = G * Mk, Cc * Mk, Nt * Mk, GM * Mk, D2 * Mk
        net1 = Gf - Cf_
        n = Nf.sum(-1); s1, t1 = statistiche_notte(net1, nv_p)
        s15 = (Gf - 1.5 * Cf_).sum(-1); sg = Gf.sum(-1); sc = Cf_.sum(-1)
        yr = net1 @ Y
        ypos = (yr > 0).sum(-1)
        zsum = ((Gf - GMf) / 2).sum(-1); d2 = D2f.sum(-1)
        for ci in range(NCFG):
            for pi, coppia in enumerate(COPPIE):
                righe_c.append((ci, f, coppia, n[ci, pi], n[ci, pi] / nv_p[pi], sg[ci, pi],
                                s1[ci, pi], s15[ci, pi], sc[ci, pi], t1[ci, pi], ypos[ci, pi],
                                zsum[ci, pi] / np.sqrt(max(d2[ci, pi], 1e-12))))
        for insieme in ("positive", "tutte"):
            sel = (s1 > 0) if insieme == "positive" else np.ones_like(s1, bool)
            sw = sel.astype(float)
            pool = np.einsum("cpn,cp->cn", net1, sw)
            ps1, pt = statistiche_notte(pool, nv_any)
            pool15 = np.einsum("cpn,cp->cn", Gf - 1.5 * Cf_, sw)
            pyr = pool @ Y
            pn = (n * sw).sum(1)
            pfreq = (n / nv_p * sw).sum(1)
            pz = (zsum * sw).sum(1) / np.sqrt(np.maximum((d2 * sw).sum(1), 1e-12))
            for ci in range(NCFG):
                coppie_sel = ",".join(c for c, b in zip(COPPIE, sel[ci]) if b)
                righe_r.append((ci, f, insieme, coppie_sel, int(sel[ci].sum()), pn[ci], pfreq[ci],
                                (sg[ci] * sw[ci]).sum(), ps1[ci], pool15[ci].sum(),
                                (sc[ci] * sw[ci]).sum(), pt[ci], int((pyr[ci] > 0).sum()), pz[ci]))
        del Gf, Cf_, Nf, GMf, D2f, net1
    cols_c = ["cfg", "filtro", "coppia", "n", "op_giorno", "lordo", "netto1", "netto15", "costo",
              "t", "anni_pos", "z_placebo"]
    dc = pd.DataFrame(righe_c, columns=cols_c)
    cols_r = ["cfg", "filtro", "insieme", "coppie", "k_coppie", "n", "op_giorno", "lordo",
              "netto1", "netto15", "costo", "t", "anni_pos", "z_placebo"]
    dr = pd.DataFrame(righe_r, columns=cols_r)
    for d_ in (dc, dr):
        d_["netto_op"] = d_["netto1"] / d_["n"].where(d_["n"] > 0)
        d_["netto15_op"] = d_["netto15"] / d_["n"].where(d_["n"] > 0)
        d_["lordo_op"] = d_["lordo"] / d_["n"].where(d_["n"] > 0)
        d_["netto_su_costo"] = d_["netto1"] / d_["costo"].where(d_["costo"] > 0)
    dr["regola"] = [nome_cfg(c) + " | " + nome_filtro(f) for c, f in zip(dr["cfg"], dr["filtro"])]
    dc.to_parquet(f"{RIS}\\a_notte_coppie.parquet")
    dr.to_parquet(f"{RIS}\\a_notte_regole.parquet")

    pos = dr[dr["insieme"] == "positive"]
    tut = dr[dr["insieme"] == "tutte"]
    print(f"regole {len(pos)} | celle regola-coppia {len(dc)} (netto>0: {(dc['netto1'] > 0).sum()}, "
          f"lordo>0: {(dc['lordo'] > 0).sum()}, t>=3: {(dc['t'] >= 3).sum()})")
    for nome, d_ in (("insieme positive", pos), ("tutte 7", tut)):
        c1 = d_["netto1"] > 0; c15 = d_["netto15"] > 0; ct = d_["t"] >= 3
        ca = d_["anni_pos"] >= 6; cf = d_["op_giorno"] >= 1
        print(f"{nome}: netto>0 {c1.sum()}, x1.5>0 {c15.sum()}, t>=3 {ct.sum()}, anni>=6 {ca.sum()}, "
              f"freq>=1 {cf.sum()}, tutti tranne placebo {(c1 & c15 & ct & ca & cf).sum()}")
    mostra = ["regola", "k_coppie", "n", "op_giorno", "netto_op", "netto_su_costo", "netto15_op",
              "t", "anni_pos", "z_placebo"]
    print(pos.sort_values("t", ascending=False)[mostra].head(15).round(3).to_string(index=False))
    print(tut.sort_values("t", ascending=False)[mostra].head(8).round(3).to_string(index=False))


# ---------------------------------------------------------------- approfondimento
def rischio(net):
    eq = np.cumsum(net)
    dd = (np.maximum.accumulate(np.r_[0, eq])[1:] - eq).max()
    perso = net < 0
    best_k, best_s, k, s = 0, 0.0, 0, 0.0
    for v, p in zip(net, perso):
        if p:
            k += 1; s += v
            best_k = max(best_k, k); best_s = min(best_s, s)
        else:
            k, s = 0, 0.0
    return net.min(), best_k, best_s, dd


def fase_approfondisci():
    dr = pd.read_parquet(f"{RIS}\\a_notte_regole.parquet")
    pos = dr[dr["insieme"] == "positive"]
    passa = pos[(pos["netto1"] > 0) & (pos["netto15"] > 0) & (pos["t"] >= 3)
                & (pos["anni_pos"] >= 6) & (pos["op_giorno"] >= 1)]
    scelte = pd.concat([passa, pos.nlargest(15, "t"),
                        dr[dr["insieme"] == "tutte"].nlargest(5, "t")]).drop_duplicates(
        subset=["cfg", "filtro", "insieme"])
    print(f"regole da approfondire: {len(scelte)} (di cui passano tutto tranne placebo: {len(passa)})")
    raccolta = {i: [] for i in scelte.index}
    for coppia in COPPIE:
        op = pd.read_parquet(f"{RIS}\\a_notte_operazioni_{coppia}.parquet")
        notti = pd.read_parquet(f"{RIS}\\a_notte_notti_{coppia}.parquet")
        FMk = maschere_filtri(notti)
        for i, r in scelte.iterrows():
            if coppia not in r["coppie"].split(","):
                continue
            q = op[op["cfg"] == r["cfg"]]
            q = q[FMk[r["filtro"], q["notte"].values]]
            raccolta[i].append(q.assign(coppia=coppia))
        del op
    rng = np.random.default_rng(SEED)
    out = []
    for i, r in scelte.iterrows():
        q = pd.concat(raccolta[i]).sort_values(["notte", "e", "coppia"])
        g, gm, c = q["g"].values.astype(float), q["gm"].values.astype(float), q["c"].values.astype(float)
        att = (g - c).mean()
        cnt = 0
        for _ in range(10):
            ch = rng.random((100, len(g))) < 0.5
            mp = (np.where(ch, g, gm) - c).mean(1)
            cnt += (mp >= att).sum()
        p = (cnt + 1) / 1001
        net = g - c
        w1, sk, ss, dd = rischio(net)
        _, _, _, dd15 = rischio(g - 1.5 * c)
        tp = q["tipo"].value_counts(normalize=True)
        out.append(dict(regola=r["regola"], insieme=r["insieme"], coppie=r["coppie"], n=len(q),
                        op_giorno=r["op_giorno"], netto_op=att, netto15_op=(g - 1.5 * c).mean(),
                        t=r["t"], anni_pos=r["anni_pos"], p_placebo=p,
                        vinte=(net > 0).mean(), media_vinta=net[net > 0].mean(),
                        media_persa=net[net <= 0].mean(), peggiore=w1, serie_perse=sk,
                        serie_pip=ss, dd_pip=dd, dd15_pip=dd15,
                        quota_obiettivo=tp.get(1, 0), quota_stop=tp.get(0, 0), quota_tempo=tp.get(2, 0),
                        cfg=r["cfg"], filtro=r["filtro"]))
    so = pd.DataFrame(out)
    so.to_parquet(f"{RIS}\\a_notte_scelte.parquet")
    so["promossa"] = ((so["insieme"] == "positive") & (so["netto_op"] > 0) & (so["netto15_op"] > 0)
                      & (so["t"] >= 3) & (so["anni_pos"] >= 6) & (so["p_placebo"] < 0.01)
                      & (so["op_giorno"] >= 1))
    c1 = ["regola", "insieme", "n", "op_giorno", "netto_op", "netto15_op", "t", "anni_pos",
          "p_placebo", "promossa"]
    c2 = ["regola", "coppie", "vinte", "media_vinta", "media_persa", "peggiore", "serie_perse",
          "serie_pip", "dd_pip", "dd15_pip", "quota_stop", "quota_tempo"]
    print(so[c1].round(3).to_string(index=False))
    print(so[c2].round(2).to_string(index=False))


# ---------------------------------------------------------------- controllo motore
def fase_controllo():
    coppia = "EURUSD"
    M, notti = prepara(coppia)
    atr = np.where(notti["valida"].values, notti["atr"].values, np.nan)
    pip = PIP[coppia]
    op = pd.read_parquet(f"{RIS}\\a_notte_operazioni_{coppia}.parquet")
    rng = np.random.default_rng(1)
    q = op.sample(400, random_state=1)
    diff = []
    for _, r in q.iterrows():
        sig, w, t, sl = CONFIG[int(r["cfg"])]
        L = FINESTRE[w][2]
        n, e, d = int(r["notte"]), int(r["e"]), int(r["dir"])
        P = M["O"][n, e]
        # ricostruzione dT
        tipo, N, par = sig
        s = e - 1
        if t == "CENTRO":
            cen = M[("SMA", N)][n, s] if tipo == "DEV" else (M[("HI", N)][n, s] + M[("LO", N)][n, s]) / 2
            dT = d * (cen - P)
        else:
            dT = t * atr[n]
        SL = sl * atr[n]
        stop, tgt = P - d * SL, P + d * dT
        pnl = None
        for j in range(e, L + 1):
            o_, h_, l_ = M["O"][n, j], M["H"][n, j], M["L"][n, j]
            if not np.isfinite(o_):
                continue
            adv = l_ if d > 0 else h_
            fav = h_ if d > 0 else l_
            if d * (adv - stop) <= 0:
                pnl = d * (o_ - P) if (j > e and d * (o_ - stop) < 0) else -SL
                break
            if d * (fav - tgt) >= 0:
                pnl = dT
                break
        if pnl is None:
            pnl = d * (M["Cf"][n, L] - P)
        diff.append(abs(pnl / pip - r["g"]))
    diff = np.array(diff)
    print(f"controllo motore {coppia}: 400 operazioni, differenza max {diff.max():.4f} pip, "
          f"media {diff.mean():.5f}")
    # controllo causalita' / sovrapposizioni
    o2 = op.sort_values(["cfg", "notte", "e"])
    stesso = (o2["cfg"].values[1:] == o2["cfg"].values[:-1]) & (o2["notte"].values[1:] == o2["notte"].values[:-1])
    sovr = (o2["e"].values[1:] <= o2["x"].values[:-1]) & stesso
    print(f"operazioni sovrapposte nella stessa regola: {int(sovr.sum())}; "
          f"entrate fuori orario (20:45-22:15): {int((op['e'] < 1).sum())}")


# ---------------------------------------------------------------- diagnostica
def fase_diagnostica():
    dc = pd.read_parquet(f"{RIS}\\a_notte_coppie.parquet")
    dr = pd.read_parquet(f"{RIS}\\a_notte_regole.parquet")
    dc["segnale"] = [CONFIG[c][0][0] for c in dc["cfg"]]
    dc["finestra"] = [CONFIG[c][1] for c in dc["cfg"]]
    dc["obiettivo"] = [str(CONFIG[c][2]) for c in dc["cfg"]]
    dc["stop"] = [CONFIG[c][3] for c in dc["cfg"]]
    dc["vol"] = [VOL[f // 2] for f in dc["filtro"]]
    agg = dict(celle=("n", "size"), lordo_op=("lordo_op", "median"), netto_op=("netto_op", "median"),
               quota_netto_pos=("netto1", lambda s: (s > 0).mean()), quota_t3=("t", lambda s: (s >= 3).mean()),
               op_giorno=("op_giorno", "median"))
    for k in ("coppia", "segnale", "finestra", "obiettivo", "stop", "vol"):
        print(dc.groupby(k).agg(**agg).round(3).to_string())
    # il candidato e i suoi vicini
    c0 = [i for i in range(NCFG) if nome_cfg(i) == "DEV N48 0.10 | C | CENTRO | S0.10"][0]
    f_usa = VOL.index("USAalto") * 2
    q = dc[(dc["cfg"] == c0) & (dc["filtro"].isin([0, f_usa]))]
    print(q[["filtro", "coppia", "n", "op_giorno", "lordo_op", "netto_op", "netto15_op", "t", "anni_pos"]]
          .round(3).to_string(index=False))
    r = dr[(dr["cfg"] == c0)]
    print(r[["regola", "insieme", "k_coppie", "n", "op_giorno", "netto_op", "netto15_op", "t", "anni_pos"]]
          .round(3).to_string(index=False))
    # anni del candidato (insieme congelato)
    coppie = ["EURUSD", "GBPUSD", "USDCHF"]
    parti = []
    for coppia in coppie:
        op = pd.read_parquet(f"{RIS}\\a_notte_operazioni_{coppia}.parquet", filters=[("cfg", "==", c0)])
        notti = pd.read_parquet(f"{RIS}\\a_notte_notti_{coppia}.parquet")
        mk = maschere_filtri(notti)[f_usa]
        op = op[mk[op["notte"].values]]
        parti.append(op.assign(coppia=coppia, anno=NOTTI.year.values[op["notte"].values]))
    q = pd.concat(parti)
    q["net"] = q["g"] - q["c"]; q["net15"] = q["g"] - 1.5 * q["c"]
    print(q.groupby("anno").agg(n=("net", "size"), netto=("net", "sum"), netto15=("net15", "sum"),
                                 lordo=("g", "sum")).round(1).T.to_string())
    print(q.groupby("tipo").agg(n=("net", "size"), media=("net", "mean")).round(2).to_string())
    q["ora"] = (q["e"].astype(int) * 5 + 1330) // 60 % 24
    print(q.groupby("ora").agg(n=("net", "size"), media=("net", "mean")).round(2).T.to_string())
    q.to_parquet(f"{RIS}\\a_notte_candidato1_operazioni.parquet")


if __name__ == "__main__":
    fase = sys.argv[1] if len(sys.argv) > 1 else "simula"
    {"simula": fase_simula, "aggrega": fase_aggrega,
     "approfondisci": fase_approfondisci, "controllo": fase_controllo,
     "diagnostica": fase_diagnostica}[fase]()
