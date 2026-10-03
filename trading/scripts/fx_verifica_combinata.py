"""Verifica 2018 -> fine dati della strategia combinata sui cambi (S1 + S2 + S3, unita' R).

Registrazione vincolante: docs/fx-combinata-registrazione.md (commit d0c20ca).
Rapporto: docs/studies/fx/verifica-combinata.md.

Le tre componenti sono il codice di scoperta, importato e usato SENZA modifiche:
  S1 = fx_b_aperture.py       a A1 RIENTRO S3 1R piccolo mar-gio   (AUDUSD, EURJPY, EURUSD, GBPUSD, USDCHF)
       (carica, genera, simula_vett, pip, COSTO)
  S2 = fx_c_media_momentum.py L15 H30 londra contro k3 s2o1 alto   (USDJPY, AUDUSD)
       (prepara, esiti, avido, fascia_di, COSTO)
  S3 = fx_d_orari_fissi.py    LDF PRE FIX- p60 h60 T fine-mese     (USDJPY, GBPUSD, AUDUSD, USDCHF)
       (carica, eventi_ancora, griglia, fine_mese, USDSEGNO, COSTO)
Unita' R: S1 R = stop (0,25 x ATR14), S2 R = stop (2 s_H), S3 R = 0,15 x ATR14 (solo misura).

Fasi (una coppia alla volta, niente multiprocessing):
  python fx_verifica_combinata.py riproduci  -> componenti e combinata sulla scoperta 2010-2017
  python fx_verifica_combinata.py confine    -> prova del confine DENTRO la scoperta (coda 400 g + 2017)
  python fx_verifica_combinata.py verifica   -> UNA sola esecuzione su D:\\ricerca_fx\\verifica

Lettura dei dati: come in fx_verifica.py, la cartella dei moduli punta a "CONCAT" e pd.read_parquet
restituisce la concatenazione dei pezzi (coda della scoperta per gli indicatori + verifica).
Contano le operazioni entrate dal 2018-01-01 00:00 UTC.
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import fx_b_aperture as fb
import fx_c_media_momentum as fc
import fx_d_orari_fissi as fd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

SCOPERTA = Path(r"D:\ricerca_fx\scoperta")
VERIFICA = Path(r"D:\ricerca_fx\verifica")
RIS = Path(r"D:\ricerca_fx\risultati")
CODA_GIORNI = 400
SEED = 20261004
NPLAC = 10000
NS = 10**9

S1_COPPIE = ["AUDUSD", "EURJPY", "EURUSD", "GBPUSD", "USDCHF"]
S2_COPPIE = ["USDJPY", "AUDUSD"]
S3_COPPIE = ["USDJPY", "GBPUSD", "AUDUSD", "USDCHF"]
TUTTE = sorted(set(S1_COPPIE + S2_COPPIE + S3_COPPIE))

# numeri della scoperta riportati nella registrazione (t con la definizione dello script di origine)
ATTESI = {
    "S1": dict(n=869, netto_pip=3.70, netto_R=0.123, t=3.75, anni_pos=7, netto_R_x15=0.102),
    "S2": dict(n=85, netto_pip=6.11, t=4.621, anni_pos=7),
    "S3": dict(n=384, netto_pip=5.74, t=3.26, anni_pos=6),
}

# ---------------------------------------------------------------- lettura concatenata
_PEZZI = []
_read_orig = pd.read_parquet


def _read(path, *a, **k):
    p = Path(path) if isinstance(path, (str, Path)) else None
    if p is not None and p.parts and p.parts[0] == "CONCAT":
        parti = []
        for cartella, da, a_ in _PEZZI:
            df = _read_orig(cartella / p.name)
            parti.append(df[(df.index >= da) & (df.index < a_)])
        out = pd.concat(parti)
        assert out.index.is_monotonic_increasing and out.index.is_unique, p.name
        return out
    return _read_orig(path, *a, **k)


pd.read_parquet = _read


def imposta(cartella, pezzi=None):
    """Cartella dei dati per i tre moduli di scoperta (Path vera oppure 'CONCAT')."""
    global _PEZZI
    fb.SCOP = cartella
    fc.SC = cartella
    fd.SCOP = cartella
    _PEZZI = pezzi or []


def giornate_borsa(c):
    """Giorni UTC lun-ven con >= 600 minuti nel D1 (stessa definizione dei tre script)."""
    d = pd.read_parquet(fb.SCOP / f"{c}_D1.parquet")
    d = d[(d["minuti"] >= 600) & (d.index.dayofweek < 5)]
    return d.index.tz_convert(None).normalize()


# ---------------------------------------------------------------- componenti
def comp_S1(c):
    m, dd = fb.carica(c)
    base, (o, h, l, cl), _ = fb.genera(c, m, dd)
    pp, costo = fb.pip(c), fb.COSTO[c]
    b = base[(base["setup"] == "A1") & (base["regola"] == "RIENTRO")]
    risk = b["S3"].to_numpy()
    ok = (risk >= 2 * costo * pp) & np.isfinite(risk)
    bb, r = b[ok], risk[ok]
    jj, dv, je = bb["j"].to_numpy(), bb["dir"].to_numpy(), bb["jE0"].to_numpy()
    g1 = fb.simula_vett(o, h, l, cl, jj, je, dv, r, r) / pp          # obiettivo 1R
    g2 = fb.simula_vett(o, h, l, cl, jj, je, -dv, r, r) / pp
    sel = (bb["regime"].to_numpy() == -1) & bb["data"].dt.dayofweek.isin([1, 2, 3]).to_numpy()
    T = m.index.as_unit("ns").asi8
    out = pd.DataFrame({
        "comp": "S1", "coppia": c, "t_entrata": T[jj[sel]], "dir": dv[sel].astype(np.int8),
        "rischio_pip": (r[sel] / pp).astype(np.float32), "lordo_pip": g1[sel].astype(np.float32),
        "lordo_opp_pip": g2[sel].astype(np.float32),
        "costo_pip": (costo * bb["mult"].to_numpy()[sel]).astype(np.float32)})
    return out


def comp_S2(c):
    P = fc.prepara(c)
    pip, cbase = (0.01 if "JPY" in c else 0.0001), fc.COSTO[c]
    L, H, iF = 15, 30, fc.FASCE.index("londra")
    N, ar, base, fas, reg, atr = P["N"], P["ar"], P["base"], P["fascia"], P["reg"], P["atr"]
    cpr, o = P["c"], P["o"]
    costo_i = np.where(P["tm"] >= 22 * 60 + 15, 2.0, 1.0) * cbase
    sL = L // 5
    x = np.full(N, np.nan)
    x[sL:] = cpr[sL:] - cpr[:-sL]
    okL = base & (ar - sL >= P["ss"])
    zxr = x / (atr * np.sqrt(L / 1440))
    jn = np.minimum(ar + 1, N - 1)
    ex = np.minimum(jn + H // 5, P["n2045"][jn])
    y = o[ex] - o[jn]
    sHv = atr * np.sqrt(H / 1440)
    zyr = y / sHv
    msk = okL & (fas == iF) & np.isfinite(zxr) & np.isfinite(zyr)
    idx = np.flatnonzero(msk)
    S = idx[np.abs(zxr[idx]) >= 1.0]
    ES = fc.esiti(P, S, H, sHv[S])
    sgn = -1 * np.sign(x[S])                       # cella "contro" (dcell = -1)
    pL, pS, fL, fS = ES["s2o1"]
    gp = np.where(sgn > 0, pL, pS) / pip
    op = np.where(sgn > 0, pS, pL) / pip
    fr = np.where(sgn > 0, fL, fS)
    J = S + 1
    sel = (np.abs(zxr[S]) >= 3.0) & (reg[S] == 2)  # k = 3, regime alto
    si = np.flatnonzero(sel)
    tk = si[fc.avido(J[si], fr[si])]
    Sk = S[tk]
    tmin = P["tday"][Sk].astype(np.int64) * 1440 + P["tm"][Sk]   # chiusura del segnale = entrata
    out = pd.DataFrame({
        "comp": "S2", "coppia": c, "t_entrata": tmin * 60 * NS, "dir": sgn[tk].astype(np.int8),
        "rischio_pip": (2.0 * sHv[Sk] / pip).astype(np.float32), "lordo_pip": gp[tk].astype(np.float32),
        "lordo_opp_pip": op[tk].astype(np.float32), "costo_pip": costo_i[Sk].astype(np.float32)})
    return out


def comp_S3(c):
    D = fd.carica(c)
    pp, costo = fd.pip(c), fd.COSTO[c]
    g = D["giorni"]
    a, ok, _ = fd.eventi_ancora(D, "LDF")
    off, h = -60, 60
    gl, gs, V, mult = fd.griglia(D, a, ok, off, h, "T", D["atr"], pp)
    fm = fd.fine_mese(g)
    # ultimo mese dei dati incompleto: il suo ultimo giorno disponibile non e' fine mese
    ult = g[-1]
    if ult < ult + pd.offsets.BMonthEnd(0):
        fm = fm & ~(g.to_period("M") == ult.to_period("M"))
    dr = -fd.USDSEGNO[c]                           # FIX- = dollaro venduto
    sel = V[:, fd.FASCIA] & fm
    idx = np.nonzero(sel)[0]
    lo, co = gl[idx, fd.FASCIA].astype(float), gs[idx, fd.FASCIA].astype(float)
    lordo = lo if dr > 0 else co
    opp = co if dr > 0 else lo
    ient = a[idx] + off // 5
    out = pd.DataFrame({
        "comp": "S3", "coppia": c, "t_entrata": D["t0"] + ient * fd.NS5, "dir": np.int8(dr),
        "rischio_pip": (fd.G_STOP * D["atr"][idx] / pp).astype(np.float32),
        "lordo_pip": lordo.astype(np.float32), "lordo_opp_pip": opp.astype(np.float32),
        "costo_pip": (costo * mult[idx]).astype(np.float32)})
    return out


def tutte_le_operazioni():
    parti, giorni = [], {}
    for c in TUTTE:
        t0 = time.time()
        if c in S1_COPPIE:
            parti.append(comp_S1(c))
        if c in S2_COPPIE:
            parti.append(comp_S2(c))
        if c in S3_COPPIE:
            parti.append(comp_S3(c))
        giorni[c] = giornate_borsa(c)
        print(f"  {c} fatto {time.time() - t0:.0f}s", flush=True)
    ops = pd.concat(parti, ignore_index=True)
    ops["entrata"] = pd.to_datetime(ops["t_entrata"], utc=True)
    ops["data"] = ops["entrata"].dt.tz_convert(None).dt.normalize()
    ops = ops.drop(columns="t_entrata").sort_values(["entrata", "comp", "coppia"]).reset_index(drop=True)
    ops["lordo_R"] = ops["lordo_pip"] / ops["rischio_pip"]
    ops["costo_R"] = ops["costo_pip"] / ops["rischio_pip"]
    ops["netto_R"] = ops["lordo_R"] - ops["costo_R"]
    ops["netto15_R"] = ops["lordo_R"] - 1.5 * ops["costo_R"]
    ops["netto_opp_R"] = (ops["lordo_opp_pip"] - ops["costo_pip"]) / ops["rischio_pip"]
    ops["netto_pip"] = ops["lordo_pip"] - ops["costo_pip"]
    return ops, giorni


# ---------------------------------------------------------------- statistiche
def t_giorni(val, date, cal):
    """t sul netto giornaliero, somme per giornata, su TUTTE le giornate del calendario (zeri inclusi)."""
    s = pd.Series(val).groupby(date.values).sum().reindex(cal, fill_value=0.0).to_numpy()
    n = len(s)
    return s.mean() / (s.std(ddof=1) / np.sqrt(n))


def t_attive(val, date):
    """t sulle somme giornaliere dei soli giorni con operazioni (definizione di fx_c / fx_d)."""
    s = pd.Series(val).groupby(date.values).sum()
    return s.mean() / s.std(ddof=1) * np.sqrt(len(s))


def rischio(net):
    eq = np.cumsum(net)
    dd = (np.maximum.accumulate(np.r_[0, eq])[1:] - eq).max()
    best_k, best_s, k, s = 0, 0.0, 0, 0.0
    for v in net:
        if v < 0:
            k += 1
            s += v
            best_k = max(best_k, k)
            best_s = min(best_s, s)
        else:
            k, s = 0, 0.0
    return net.min(), best_k, best_s, dd


def placebo(net, opp, seed=SEED, nser=NPLAC):
    """Direzione casuale per ogni operazione (stessa gestione speculare), totale netto in R a x1."""
    rng = np.random.default_rng(seed)
    dlt = (opp - net).astype(np.float64)
    tot = np.empty(nser)
    blk = 500
    for a in range(0, nser, blk):
        B = rng.integers(0, 2, size=(blk, len(dlt)), dtype=np.int8).astype(np.float64)
        tot[a:a + blk] = net.sum() + B @ dlt
    p = (1 + (tot >= net.sum() - 1e-9).sum()) / (nser + 1)
    return p, tot.mean(), np.percentile(tot, 99)


def calendario(giorni, coppie, da, a_):
    cal = None
    for c in coppie:
        g = giorni[c]
        g = g[(g >= da) & (g < a_)]
        cal = g if cal is None else cal.union(g)
    return cal


def misura_comb(q, giorni, da, a_, con_placebo=True):
    cal = calendario(giorni, TUTTE, da, a_)
    net, n15 = q["netto_R"].to_numpy(float), q["netto15_R"].to_numpy(float)
    anni = q.groupby(q["data"].dt.year)["netto_R"].sum()
    anni15 = q.groupby(q["data"].dt.year)["netto15_R"].sum()
    w1, sk, ss, dd = rischio(net)
    _, sk15, ss15, dd15 = rischio(n15)
    r = dict(n=len(q), giornate=len(cal), op_giorno=len(q) / len(cal),
             op_giorno_coppie=sum(((q["coppia"] == c) & (q["comp"] == k)).sum() / len(calendario(giorni, [c], da, a_))
                                  for k, cc in (("S1", S1_COPPIE), ("S2", S2_COPPIE), ("S3", S3_COPPIE))
                                  for c in cc),
             lordo_R=q["lordo_R"].mean(), costo_R=q["costo_R"].mean(),
             netto_R=net.mean(), netto_tot_R=net.sum(), netto15_R=n15.mean(), netto15_tot_R=n15.sum(),
             t=t_giorni(net, q["data"], cal), t15=t_giorni(n15, q["data"], cal),
             t_attive=t_attive(net, q["data"]), t_operazione=net.mean() / net.std(ddof=1) * np.sqrt(len(net)),
             anni_pos=int((anni > 0).sum()), anni_tot=len(anni), anni15_pos=int((anni15 > 0).sum()),
             vinte=(net > 0).mean(), peggiore_R=w1, serie_perse=sk, serie_R=ss, dd_R=dd,
             serie15_perse=sk15, serie15_R=ss15, dd15_R=dd15,
             pareggio_x=q["lordo_R"].sum() / q["costo_R"].sum())
    if con_placebo:
        r["p"], r["placebo_media_R"], r["placebo_p99_R"] = placebo(net, q["netto_opp_R"].to_numpy(float))
    return r, anni, anni15


def misura_comp(q, giorni, comp, coppie, da, a_):
    """Statistiche di una componente; t_orig = definizione dello script di origine."""
    z = q[q["comp"] == comp]
    cal = calendario(giorni, TUTTE, da, a_)
    net = z["netto_R"].to_numpy(float)
    anni = z.groupby(z["data"].dt.year)["netto_R"].sum()
    anni_pip = z.groupby(z["data"].dt.year)["netto_pip"].sum()
    giorni_c = {c: len(calendario(giorni, [c], da, a_)) for c in coppie}
    if comp == "S1":      # fx_b: t per operazione in R
        t_orig = net.mean() / net.std(ddof=1) * np.sqrt(len(net))
        anni_orig = int((anni > 0).sum())
    else:                 # fx_c / fx_d: t sulle somme giornaliere in pip dei giorni con operazioni
        t_orig = t_attive(z["netto_pip"].to_numpy(float), z["data"])
        anni_orig = int((anni_pip > 0).sum())
    return dict(comp=comp, n=len(z), op_giorno=sum((z["coppia"] == c).sum() / giorni_c[c] for c in coppie),
                lordo_pip=z["lordo_pip"].mean(), netto_pip=z["netto_pip"].mean(),
                netto15_pip=(z["lordo_pip"] - 1.5 * z["costo_pip"]).mean(),
                rischio_pip_med=z["rischio_pip"].median(),
                netto_R=net.mean(), netto_tot_R=net.sum(), netto15_R=z["netto15_R"].mean(),
                t_orig=t_orig, t_R_giorni=t_giorni(net, z["data"], cal), anni_pos=anni_orig,
                anni_pos_R=int((anni > 0).sum()), anni_tot=len(anni),
                pareggio_x=z["lordo_R"].sum() / z["costo_R"].sum())


def per_coppia(q):
    g = q.groupby(["comp", "coppia"])
    return g.agg(n=("netto_R", "size"), netto_pip=("netto_pip", "mean"), netto_R=("netto_R", "mean"),
                 netto_tot_R=("netto_R", "sum")).reset_index()


def tabella_anni(q):
    an = pd.DataFrame({"n": q.groupby(q["data"].dt.year).size(),
                       "x1": q.groupby(q["data"].dt.year)["netto_R"].sum(),
                       "x1,5": q.groupby(q["data"].dt.year)["netto15_R"].sum()})
    for k in ("S1", "S2", "S3"):
        z = q[q["comp"] == k]
        an[k] = z.groupby(z["data"].dt.year)["netto_R"].sum()
    return an.fillna(0.0)


# ---------------------------------------------------------------- fasi
def fase_riproduci(stampa=True):
    imposta(SCOPERTA)
    ops, giorni = tutte_le_operazioni()
    da, a_ = pd.Timestamp("2010-01-01"), pd.Timestamp("2018-01-01")
    q = ops[(ops["data"] >= da) & (ops["data"] < a_)]
    comp = pd.DataFrame([misura_comp(q, giorni, k, cc, da, a_)
                         for k, cc in (("S1", S1_COPPIE), ("S2", S2_COPPIE), ("S3", S3_COPPIE))])
    ok = True
    righe = []
    for _, r in comp.iterrows():
        att = ATTESI[r["comp"]]
        e = dict(comp=r["comp"], n=r["n"], n_att=att["n"], netto_pip=r["netto_pip"], netto_pip_att=att["netto_pip"],
                 t=r["t_orig"], t_att=att["t"], anni=r["anni_pos"], anni_att=att["anni_pos"])
        e["ok"] = bool(r["n"] == att["n"] and abs(r["netto_pip"] / att["netto_pip"] - 1) < 0.01
                       and abs(r["t_orig"] / att["t"] - 1) < 0.01 and r["anni_pos"] == att["anni_pos"])
        if "netto_R" in att:
            e["netto_R"], e["netto_R_att"] = r["netto_R"], att["netto_R"]
            e["ok"] &= bool(abs(r["netto_R"] / att["netto_R"] - 1) < 0.01)
        ok &= e["ok"]
        righe.append(e)
    rip = pd.DataFrame(righe)
    if stampa:
        print("\nRIPRODUZIONE componenti sulla scoperta 2010-2017")
        print(rip.round(4).to_string(index=False))
        print(comp.round(4).to_string(index=False))
        print(per_coppia(q).round(3).to_string(index=False))
        r, anni, anni15 = misura_comb(q, giorni, da, a_)
        print("\nCOMBINATA sulla scoperta (riferimento)")
        print(pd.Series(r).to_string())
        print(tabella_anni(q).round(2).T.to_string())
        q.to_parquet(RIS / "verifica_comb_scoperta_operazioni.parquet")
        pd.DataFrame([r]).to_parquet(RIS / "verifica_comb_scoperta_riepilogo.parquet")
        comp.to_parquet(RIS / "verifica_comb_scoperta_componenti.parquet")
    print("\nriprodotto:", ok)
    return ok


def fase_confine():
    """Dentro la scoperta: indicatori da una coda di 400 giorni, operazioni del 2017 confrontate
    con quelle calcolate sulla scoperta intera."""
    imposta(SCOPERTA)
    ref, _ = tutte_le_operazioni()
    ref = ref[ref["entrata"] >= pd.Timestamp("2017-01-01", tz="UTC")]
    inizio = pd.Timestamp("2017-01-01", tz="UTC")
    imposta(Path("CONCAT"), [(SCOPERTA, inizio - pd.Timedelta(days=CODA_GIORNI), inizio),
                             (SCOPERTA, inizio, pd.Timestamp("2100-01-01", tz="UTC"))])
    a, _ = tutte_le_operazioni()
    a = a[a["entrata"] >= inizio]
    k = ["comp", "coppia", "entrata", "dir"]
    m = a.merge(ref[k + ["lordo_pip", "rischio_pip"]], on=k, how="outer", suffixes=("", "_ref"), indicator=True)
    print("\nprova del confine 2017 (coda", CODA_GIORNI, "giorni)")
    print(m.groupby(["comp", "_merge"], observed=True).size().unstack(fill_value=0).to_string())
    print("diff lordo max", float((m["lordo_pip"] - m["lordo_pip_ref"]).abs().max()),
          " diff rischio max", float((m["rischio_pip"] - m["rischio_pip_ref"]).abs().max()))
    ok = bool((m["_merge"] == "both").all())
    print("confine ok:", ok)
    return ok


def fase_verifica():
    fout = RIS / "verifica_comb_operazioni.parquet"
    assert not fout.exists(), "la verifica e' gia' stata eseguita (una sola esecuzione)"
    assert fase_riproduci(stampa=False), "riproduzione non coincide: la verifica non si apre"
    inizio = pd.Timestamp("2018-01-01", tz="UTC")
    imposta(Path("CONCAT"), [(SCOPERTA, inizio - pd.Timedelta(days=CODA_GIORNI), inizio),
                             (VERIFICA, inizio, pd.Timestamp("2100-01-01", tz="UTC"))])
    ops, giorni = tutte_le_operazioni()
    q = ops[ops["entrata"] >= inizio].reset_index(drop=True)
    da, a_ = pd.Timestamp("2018-01-01"), pd.Timestamp("2100-01-01")
    r, anni, anni15 = misura_comb(q, giorni, da, a_)
    soglia = int(np.ceil(2 / 3 * r["anni_tot"]))
    r["soglia_anni"] = soglia
    r["verdetto"] = bool(r["netto_R"] > 0 and r["netto15_R"] > 0 and r["t"] >= 2 and r["anni_pos"] >= soglia
                         and r["p"] < 0.01 and r["op_giorno"] >= 0.5)
    r["prima_op"], r["ultima_op"] = str(q["entrata"].min()), str(q["entrata"].max())
    comp = pd.DataFrame([misura_comp(q, giorni, k, cc, da, a_)
                         for k, cc in (("S1", S1_COPPIE), ("S2", S2_COPPIE), ("S3", S3_COPPIE))])
    an = tabella_anni(q)
    pc = per_coppia(q)
    print("\nVERIFICA combinata 2018 -> fine dati")
    print(pd.Series(r).to_string())
    print(comp.round(4).to_string(index=False))
    print(pc.round(3).to_string(index=False))
    print(an.round(2).T.to_string())
    q.to_parquet(fout)
    pd.DataFrame([r]).to_parquet(RIS / "verifica_comb_riepilogo.parquet")
    comp.to_parquet(RIS / "verifica_comb_componenti.parquet")
    an.reset_index(names="anno").to_parquet(RIS / "verifica_comb_anni.parquet")
    pc.to_parquet(RIS / "verifica_comb_coppie.parquet")


if __name__ == "__main__":
    RIS.mkdir(parents=True, exist_ok=True)
    fase = sys.argv[1] if len(sys.argv) > 1 else "riproduci"
    {"riproduci": fase_riproduci, "confine": fase_confine, "verifica": fase_verifica}[fase]()
