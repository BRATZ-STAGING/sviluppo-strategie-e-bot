"""Ricerca da zero, famiglia 4: volatilita' (compressione/espansione, giornate
estreme, regimi di volatilita').

Protocollo: docs/ricerca-da-zero-registrazione.md. Usa SOLO
D:\\ricerca_zero\\scoperta\\<SIM>_M5.parquet (indice UTC all'apertura).
Varianti dichiarate in docs/studies/zero/f4-volatilita.md prima del calcolo:
736 = 448 (a) + 160 (b) + 128 (c).

Giornate costruite dalle M5: "22-22" = [D-1 22:00, D 22:00) UTC etichettata D;
per gli indici anche "cash" (S&P/Nasdaq 9:30-16:00 New York, DAX 9:00-17:30
Berlino, ora legale vera).

Uscite in D:\\ricerca_zero\\risultati\\:
  f4_varianti.parquet   una riga per variante (statistiche e placebo)
  f4_operazioni.parquet una riga per operazione (tutte le varianti)
  f4_info.parquet       ATR e costo in % del rischio per mercato/anno
  f4_descr.parquet      descrittive (espansione dopo compressione, giorno
                        dopo le giornate estreme, persistenza della volatilita')
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
SIMBOLI = ["XAUUSD", "XAGUSD", "SPXUSD", "NSXUSD", "GRXEUR"]
COSTO = {"XAUUSD": 0.40, "XAGUSD": 0.025, "SPXUSD": 0.55, "NSXUSD": 1.50, "GRXEUR": 1.50}
CASH = {"SPXUSD": ("America/New_York", 9 * 60 + 30, 16 * 60),
        "NSXUSD": ("America/New_York", 9 * 60 + 30, 16 * 60),
        "GRXEUR": ("Europe/Berlin", 9 * 60, 17 * 60 + 30)}
N_PLACEBO = 1000
SEED = 12345
MIN_R_COSTI = 2.0
MARGINE_SEGNALE = 12          # M5 che devono restare nella giornata dopo il segnale
MIN_OP_ANNO = 5
FILTRI_A = ["TUTTI", "NR4", "NR7", "ID", "IDNR4", "R50", "R75"]
STOP_A = ["S1", "S2"]
USCITE_A = {"X1": (1, None), "X1T2": (1, 2.0), "X3": (3, None), "X5": (5, None)}
ESTREMI = {"RNG15": ("rng", 1.5), "RNG20": ("rng", 2.0), "RET10": ("ret", 1.0), "RET15": ("ret", 1.5)}
STOP_B = [0.5, 1.0]
USCITE_B = [1, 3]
REGIMI = ["VB", "VA", "CMP", "ESP"]

# array M5 del mercato corrente (globali per la simulazione)
O = H = L = C = None
TS = None


# ---------------------------------------------------------------- dati
def carica(sim: str) -> pd.DataFrame:
    d = pd.read_parquet(SCOPERTA / f"{sim}_M5.parquet", columns=["open", "high", "low", "close"])
    d = d[~d.index.duplicated()].sort_index()
    d.index = d.index.as_unit("ns")
    return d


def tabella_giorni(d: pd.DataFrame, tipo: str, sim: str) -> pd.DataFrame:
    """Una riga per giornata valida: st/en indici M5 (inclusivi), O H L C."""
    idx = d.index
    if tipo == "22-22":
        lab = (idx + pd.Timedelta(hours=2)).tz_convert("UTC").normalize().tz_localize(None)
        pos = np.arange(len(d))
        lab = lab.values
    else:
        tz, a, b = CASH[sim]
        loc = idx.tz_convert(tz)
        mm = loc.hour * 60 + loc.minute
        ok = (mm >= a) & (mm < b) & (loc.dayofweek < 5)
        pos = np.flatnonzero(ok)
        lab = loc[ok].tz_localize(None).normalize().values
    cambi = np.r_[0, np.flatnonzero(lab[1:] != lab[:-1]) + 1]
    st = pos[cambi]
    en = pos[np.r_[cambi[1:] - 1, len(pos) - 1]]
    n = np.diff(np.r_[cambi, len(pos)])
    hh = np.maximum.reduceat(H[pos], cambi)
    ll = np.minimum.reduceat(L[pos], cambi)
    g = pd.DataFrame({"data": pd.to_datetime(lab[cambi]), "st": st, "en": en, "n": n,
                      "O": O[st], "H": hh, "L": ll, "C": C[en]})
    g = g[g.data.dt.dayofweek < 5]
    g = g[g.n >= 0.5 * g.n.median()].reset_index(drop=True)
    g["anno"] = g.data.dt.year
    g["rng"] = g.H - g.L
    cp = g.C.shift(1)
    g["tr"] = np.maximum(g.H, cp.fillna(g.H)) - np.minimum(g.L, cp.fillna(g.L))
    g["atr_pre"] = g.tr.rolling(14).mean().shift(1)          # k escluso
    g["atr_fino"] = g.tr.rolling(14).mean()                   # k incluso
    g["atr5"] = g.tr.rolling(5).mean()
    g["atr60"] = g.tr.rolling(60).mean()
    # percentile dell'ATR14 fino a k fra i 250 valori precedenti (min 100)
    a = g.atr_fino.values
    pct = np.full(len(g), np.nan)
    for k in range(len(g)):
        prev = a[max(0, k - 250):k]
        prev = prev[~np.isnan(prev)]
        if len(prev) >= 100 and not np.isnan(a[k]):
            pct[k] = (prev < a[k]).mean()
    g["atr_pct"] = pct
    return g


# ---------------------------------------------------------------- simulazione
def simula(i0: int, iend: int, d: int, R: float, tgt: float | None):
    """Entrata all'apertura di i0; ritorna (prezzo uscita, indice uscita)."""
    e = O[i0]
    hh = H[i0:iend + 1]
    ll = L[i0:iend + 1]
    if d > 0:
        stop = e - R
        hs = ll <= stop
        tg = e + tgt * R if tgt else np.inf
        ht = hh >= tg
    else:
        stop = e + R
        hs = hh >= stop
        tg = e - tgt * R if tgt else -np.inf
        ht = ll <= tg
    js = int(np.argmax(hs)) if hs.any() else 10**9
    jt = int(np.argmax(ht)) if (tgt and ht.any()) else 10**9
    j = min(js, jt)
    if j == 10**9:
        return C[iend], iend
    o = O[i0 + j]
    if d > 0:
        if o <= stop:
            px = o
        elif tgt and o >= tg:
            px = o
        elif js == j:
            px = stop
        else:
            px = tg
    else:
        if o >= stop:
            px = o
        elif tgt and o <= tg:
            px = o
        elif js == j:
            px = stop
        else:
            px = tg
    return px, i0 + j


def esiti(ev: pd.DataFrame, costo: float, tgt: float | None) -> pd.DataFrame:
    """Per ogni evento (i0, iend, dir, R) esito nella direzione reale e opposta."""
    out = np.zeros((len(ev), 4))
    for n, (i0, iend, d, R) in enumerate(zip(ev.i0.values, ev.iend.values, ev.dir.values, ev.R.values)):
        e = O[i0]
        pa, ja = simula(i0, iend, d, R, tgt)
        pb, _ = simula(i0, iend, -d, R, tgt)
        out[n] = (d * (pa - e), -d * (pb - e), ja, e)
    ev = ev.copy()
    ev["lordo"] = out[:, 0]
    ev["netR"] = (out[:, 0] - costo) / ev.R
    ev["netR_opp"] = (out[:, 1] - costo) / ev.R
    ev["jexit"] = out[:, 2].astype(np.int64)
    ev["entrata"] = out[:, 3]
    return ev


def non_sovrapposte(ev: pd.DataFrame) -> pd.DataFrame:
    ev = ev.sort_values("i0")
    keep = np.zeros(len(ev), bool)
    ultimo = -1
    for n, (i0, je) in enumerate(zip(ev.i0.values, ev.jexit.values)):
        if i0 > ultimo:
            keep[n] = True
            ultimo = je
    return ev[keep]


def statistiche(tr: pd.DataFrame, costo: float, rng: np.random.Generator) -> dict:
    n = len(tr)
    if n < 2:
        return {"n": n}
    x = tr.netR.values
    m, s = x.mean(), x.std(ddof=1)
    t = m / s * np.sqrt(n) if s > 0 else np.nan
    anni = tr.groupby(tr.anno).netR.agg(["sum", "size"])
    anni = anni[anni["size"] >= MIN_OP_ANNO]
    mask = rng.random((N_PLACEBO, n)) < 0.5
    pl = np.where(mask, x[None, :], tr.netR_opp.values[None, :]).mean(1)
    p = (1 + (pl >= m).sum()) / (N_PLACEBO + 1)
    return {"n": n, "netR": m, "t": t, "lordoR": (tr.lordo / tr.R).mean(),
            "net_costi": ((tr.lordo - costo) / costo).mean(), "vinc": (x > 0).mean(),
            "anni_pos": int((anni["sum"] > 0).sum()), "anni": len(anni),
            "frac_anni": (anni["sum"] > 0).mean() if len(anni) else np.nan,
            "p": p, "R_med": tr.R.median(), "costo_R": (costo / tr.R).median()}


# ---------------------------------------------------------------- eventi
def eventi_rottura(g: pd.DataFrame, costo: float) -> pd.DataFrame:
    """Per ogni giorno di setup k: prima chiusura M5 oltre H[k]/L[k] nel giorno k+1."""
    rows = []
    gst, gen, gh, gl = g.st.values, g.en.values, g.H.values, g.L.values
    for k in range(20, len(g) - 1):
        st, en = int(gst[k + 1]), int(gen[k + 1])
        lim = en - MARGINE_SEGNALE
        if lim < st:
            continue
        cc = C[st:lim + 1]
        hk, lk = gh[k], gl[k]
        f = np.flatnonzero((cc > hk) | (cc < lk))
        if len(f) == 0:
            continue
        j = st + int(f[0])
        d = 1 if C[j] > hk else -1
        rows.append((k, j + 1, d, hk, lk))
    ev = pd.DataFrame(rows, columns=["k", "i0", "dir", "Hk", "Lk"])
    return ev


def filtri(g: pd.DataFrame) -> dict:
    r = g.rng
    nr4 = r < pd.concat([r.shift(i) for i in (1, 2, 3)], axis=1).min(axis=1)
    nr7 = r < pd.concat([r.shift(i) for i in range(1, 7)], axis=1).min(axis=1)
    idd = (g.H <= g.H.shift(1)) & (g.L >= g.L.shift(1))
    rr = r / g.atr_pre
    f = {"TUTTI": pd.Series(True, index=g.index), "NR4": nr4, "NR7": nr7, "ID": idd,
         "IDNR4": idd & nr4, "R50": rr < 0.5, "R75": rr < 0.75}
    rap = g.atr5 / g.atr60
    reg = {"VB": g.atr_pct <= 1 / 3, "VA": g.atr_pct >= 2 / 3, "CMP": rap < 0.8, "ESP": rap > 1.2}
    return {k: v.fillna(False).values for k, v in f.items()}, {k: v.fillna(False).values for k, v in reg.items()}


def prepara_rottura(g, ev, stop, ngiorni, costo):
    """Aggiunge R, iend al set di eventi; scarta quelli non validi."""
    ev = ev.copy()
    e = O[ev.i0.values]
    if stop == "S1":
        st_px = np.where(ev.dir > 0, ev.Lk, ev.Hk)
    else:
        st_px = (ev.Hk + ev.Lk) / 2
    ev["R"] = ev.dir * (e - st_px)
    kk = ev.k.values + ngiorni
    ok = kk < len(g)
    ev = ev[ok]
    ev["iend"] = g.en.values[kk[ok]]
    ev = ev[(ev.R >= MIN_R_COSTI * costo) & (ev.iend >= ev.i0)]
    return ev


# ---------------------------------------------------------------- principale
def main():
    global O, H, L, C, TS
    RISULTATI.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    varianti, operazioni, info, descr = [], [], [], []

    for sim in SIMBOLI:
        d = carica(sim)
        O, H, L, C = (d[c].values.astype(np.float64) for c in ("open", "high", "low", "close"))
        TS = d.index
        costo = COSTO[sim]
        tipi = ["22-22"] + (["cash"] if sim in CASH else [])
        for tipo in tipi:
            g = tabella_giorni(d, tipo, sim)
            mg = f"{sim}/{tipo}"
            fA, reg = filtri(g)
            ev0 = eventi_rottura(g, costo)
            ev0["anno"] = g.anno.values[ev0.k.values + 1]
            ev0["data"] = g.data.values[ev0.k.values + 1]
            # ---------- (a) e (c)
            for stop in STOP_A:
                for xn, (ng, tgt) in USCITE_A.items():
                    ev = prepara_rottura(g, ev0, stop, ng, costo)
                    ev = esiti(ev, costo, tgt)
                    for fn, fm in fA.items():
                        tr = non_sovrapposte(ev[fm[ev.k.values]])
                        vid = f"a|{mg}|{fn}|{stop}|{xn}"
                        varianti.append({"vid": vid, "parte": "a", "mercato": sim, "giornata": tipo,
                                         "filtro": fn, "stop": stop, "uscita": xn,
                                         **statistiche(tr, costo, rng)})
                        operazioni.append(tr.assign(vid=vid))
                    if xn in ("X1", "X3"):
                        for rn, rm in reg.items():
                            tr = non_sovrapposte(ev[rm[ev.k.values]])
                            vid = f"c|{mg}|{rn}|{stop}|{xn}"
                            varianti.append({"vid": vid, "parte": "c", "mercato": sim, "giornata": tipo,
                                             "filtro": rn, "stop": stop, "uscita": xn,
                                             **statistiche(tr, costo, rng)})
                            operazioni.append(tr.assign(vid=vid))
            # ---------- informazioni: ATR e costo in % del rischio
            base = prepara_rottura(g, ev0, "S1", 1, costo)
            gi = g.dropna(subset=["atr_pre"])
            inf = gi.groupby("anno").agg(atr=("atr_pre", "median"), prezzo=("C", "median"),
                                         rng=("rng", "median"))
            inf["atr_pct_prezzo"] = 100 * inf.atr / inf.prezzo
            inf["costo_pct_atr"] = 100 * costo / inf.atr
            rb = prepara_rottura(g, ev0, "S1", 1, 0.0)  # senza scarto per rischio minimo
            rb = rb.assign(anno=g.anno.values[rb.k.values + 1])
            inf["R_med_S1"] = rb.groupby("anno").R.median()
            inf["costo_pct_R_S1"] = 100 * costo / inf.R_med_S1
            inf["frac_scartate_S1"] = 1 - base.groupby(g.anno.values[base.k.values + 1]).size() / rb.groupby("anno").size()
            info.append(inf.reset_index().assign(mercato=sim, giornata=tipo))
            # ---------- descrittive (a): espansione dopo compressione
            rr_next = (g.rng.shift(-1) / g.atr_pre).values
            hk, lk = g.H.values, g.L.values
            entrambi = np.r_[(hk[1:] > hk[:-1]) & (lk[1:] < lk[:-1]), False]
            for fn, fm in list(fA.items()) + list(reg.items()):
                m = fm & ~np.isnan(rr_next) & ~np.isnan(g.atr_pre.values)
                descr.append({"tipo": "a_espansione", "mercato": sim, "giornata": tipo, "def": fn,
                              "n": int(m.sum()), "rng_dopo_atr": np.nanmean(rr_next[m]),
                              "frac_rompe_entrambi": entrambi[m].mean()})
            # persistenza della volatilita'
            lr = np.log(g.rng.values)
            rel = np.log((g.rng / g.atr_pre).values)
            okr = ~np.isnan(rel[:-1]) & ~np.isnan(rel[1:])
            descr.append({"tipo": "c_persistenza", "mercato": sim, "giornata": tipo, "def": "lag1",
                          "n": int(okr.sum()), "corr_log_range": np.corrcoef(lr[:-1], lr[1:])[0, 1],
                          "corr_log_range_su_atr": np.corrcoef(rel[:-1][okr], rel[1:][okr])[0, 1]})
            # ---------- (b) giornate estreme (solo 22-22)
            if tipo == "22-22":
                for en_, (kind, kk) in ESTREMI.items():
                    if kind == "rng":
                        m = (g.rng > kk * g.atr_pre).values
                        sg = np.sign(g.C - g.O).values
                    else:
                        ret = (g.C - g.C.shift(1)).values
                        m = np.abs(ret) > kk * g.atr_pre.values
                        sg = np.sign(ret)
                    ks = np.flatnonzero(m & (sg != 0))
                    ks = ks[(ks >= 20) & (ks < len(g) - 1)]
                    # descrittiva del giorno dopo
                    r1 = (g.C.values[ks + 1] - g.C.values[ks]) * sg[ks] / g.atr_pre.values[ks]
                    descr.append({"tipo": "b_giorno_dopo", "mercato": sim, "giornata": tipo, "def": en_,
                                  "n": len(ks), "p_continua": (r1 > 0).mean(), "ret_dopo_atr": r1.mean(),
                                  "rng_dopo_atr": np.mean(g.rng.values[ks + 1] / g.atr_pre.values[ks]),
                                  "rng_norma_atr": np.nanmean(g.rng.values[20:] / g.atr_pre.values[20:])})
                    for sm in STOP_B:
                        for ng in USCITE_B:
                            kk2 = ks + ng
                            ok = kk2 < len(g)
                            evb = pd.DataFrame({"k": ks[ok], "i0": g.st.values[ks[ok] + 1],
                                                "iend": g.en.values[kk2[ok]], "dir": sg[ks[ok]].astype(int),
                                                "R": sm * g.atr_pre.values[ks[ok]]})
                            evb["anno"] = g.anno.values[evb.k.values + 1]
                            evb["data"] = g.data.values[evb.k.values + 1]
                            evb = evb[evb.R >= MIN_R_COSTI * costo]
                            for dn, ds in (("CONT", 1), ("REV", -1)):
                                e2 = evb.assign(dir=evb.dir * ds)
                                e2 = non_sovrapposte(esiti(e2, costo, None))
                                vid = f"b|{sim}/22-22|{en_}|{dn}|{sm}ATR|X{ng}"
                                varianti.append({"vid": vid, "parte": "b", "mercato": sim, "giornata": tipo,
                                                 "filtro": f"{en_}-{dn}", "stop": f"{sm}ATR", "uscita": f"X{ng}",
                                                 **statistiche(e2, costo, rng)})
                                operazioni.append(e2.assign(vid=vid))
            del g
            gc.collect()
        print(f"{sim}: fatto ({len(varianti)} varianti finora)", flush=True)
        del d
        O = H = L = C = TS = None
        gc.collect()

    V = pd.DataFrame(varianti)
    OP = pd.concat(operazioni, ignore_index=True)
    OP = OP[["vid", "k", "data", "anno", "i0", "iend", "jexit", "dir", "entrata", "R", "lordo", "netR", "netR_opp"]]
    INF = pd.concat(info, ignore_index=True)
    DS = pd.DataFrame(descr)
    V["promosso"] = ((V.netR > 0) & (V.t >= 3) & (V.frac_anni >= 0.75) & (V.p < 0.01) & (V.n >= 100))
    V.to_parquet(RISULTATI / "f4_varianti.parquet")
    OP.to_parquet(RISULTATI / "f4_operazioni.parquet")
    INF.to_parquet(RISULTATI / "f4_info.parquet")
    DS.to_parquet(RISULTATI / "f4_descr.parquet")

    print(f"\nVarianti calcolate: {len(V)} (a={sum(V.parte=='a')}, b={sum(V.parte=='b')}, c={sum(V.parte=='c')})")
    print(f"Promosse: {int(V.promosso.sum())}; t>=3: {int((V.t >= 3).sum())}; t<=-3: {int((V.t <= -3).sum())}")
    col = ["vid", "n", "netR", "net_costi", "t", "anni_pos", "anni", "p", "costo_R", "promosso"]
    print("\nMigliori 10 per t:")
    print(V.sort_values("t", ascending=False)[col].head(10).round(3).to_string(index=False))
    print("\nPeggiori 5 per t:")
    print(V.sort_values("t")[col].head(5).round(3).to_string(index=False))
    top = V.sort_values("t", ascending=False).vid.head(3).tolist()
    pa = OP[OP.vid.isin(top)].pivot_table(index="vid", columns="anno", values="netR", aggfunc="sum")
    print("\nNetto R per anno (migliori 3 per t):")
    print(pa.round(1).to_string())


if __name__ == "__main__":
    main()
