"""Verifica 2018 -> fine dati del candidato C1 (intraday cambi, notte asiatica).

Candidato congelato: docs/fx-intraday-candidati.md (commit 22e6f4d).
Regola = codice di fx_a_notte.py, importato e usato senza modifiche:
DEV N48 0,10 | finestra C | obiettivo CENTRO | stop 0,10 ATRd | filtro USAalto/tutte,
coppie EURUSD, GBPUSD, USDCHF.

Fasi (una coppia alla volta):
  python fx_verifica.py riproduci  -> rifa' C1 sulla scoperta 2010-2017 e lo confronta coi numeri congelati
  python fx_verifica.py confine    -> prova del confine DENTRO la scoperta: coda 2015-16 + 2017,
                                      le operazioni 2017 devono coincidere con quelle della scoperta intera
  python fx_verifica.py verifica   -> UNA sola esecuzione su D:\\ricerca_fx\\verifica (2018 -> fine dati)

Per la verifica gli indicatori (ATRd 14 giorni, terzile del range USA sulle 250 notti precedenti,
SMA48) richiedono storia del 2017: si concatena la coda della scoperta (400 giorni) davanti ai dati
di verifica, solo per gli indicatori; contano le operazioni delle notti datate dal 2018-01-01
(entrate dalle 00:00 UTC del 2018-01-01 in poi).
"""
import sys
import numpy as np
import pandas as pd

import fx_a_notte as fa

SCOPERTA = r"D:\ricerca_fx\scoperta"
VERIFICA = r"D:\ricerca_fx\verifica"
RIS = r"D:\ricerca_fx\risultati"
COPPIE_C1 = ["EURUSD", "GBPUSD", "USDCHF"]
C0 = [i for i in range(fa.NCFG) if fa.nome_cfg(i) == "DEV N48 0.10 | C | CENTRO | S0.10"][0]
F_USA = fa.VOL.index("USAalto") * 2          # USAalto / tutte le notti
CODA_GIORNI = 400
ATTESI = dict(n=3619, op_giorno=1.76, netto_op=0.742, netto15_op=0.277, t=3.00, anni_pos=8)

# ---------------------------------------------------------------- lettura concatenata
# fa.prepara legge f"{fa.DATI}\\{coppia}_<TF>.parquet": con fa.DATI = "CONCAT" la lettura
# passa da qui e restituisce la concatenazione dei pezzi in _PEZZI (cartella, da, a).
_PEZZI = []
_read_orig = pd.read_parquet


def _read(path, *a, **k):
    if isinstance(path, str) and path.startswith("CONCAT\\"):
        nome = path.split("\\")[-1]
        parti = []
        for cartella, da, a_ in _PEZZI:
            df = _read_orig(f"{cartella}\\{nome}")
            parti.append(df[(df.index >= da) & (df.index < a_)])
        out = pd.concat(parti)
        assert out.index.is_monotonic_increasing and out.index.is_unique, nome
        return out
    return _read_orig(path, *a, **k)


pd.read_parquet = _read


def imposta(dati, notti, pezzi=None):
    """Imposta i globali di fx_a_notte usati da prepara (cartella dati e calendario notti)."""
    global _PEZZI
    fa.DATI = dati
    fa.NOTTI = notti
    fa.NN = len(notti)
    fa.ANNI = notti.year.values - notti.year.values.min()
    _PEZZI = pezzi or []


# ---------------------------------------------------------------- simulazione C1
def simula_c1():
    """Operazioni C1 sulle 3 coppie per tutto il calendario fa.NOTTI (filtro applicato)."""
    parti, notti_c = [], {}
    for coppia in COPPIE_C1:
        M, notti = fa.prepara(coppia)
        atr = np.where(notti["valida"].values, notti["atr"].values, np.nan)
        pip, cb = fa.PIP[coppia], fa.COSTO[coppia]
        n, e, xs, d, pnl, pm, tipo = fa.simula_cfg(M, atr, C0, {}, cb * pip)
        # stessi tipi della fase "simula" di fx_a_notte (g, gm, c in float32)
        op = pd.DataFrame({
            "notte": n.astype(np.int16), "e": e.astype(np.int8), "x": xs.astype(np.int8),
            "dir": d.astype(np.int8), "g": (pnl / pip).astype(np.float32),
            "gm": (pm / pip).astype(np.float32),
            "c": np.where(e < fa.SLOT_MEZZANOTTE, 2 * cb, cb).astype(np.float32), "tipo": tipo})
        mk = fa.maschere_filtri(notti)[F_USA]
        op = op[mk[op["notte"].values]]
        parti.append(op.assign(coppia=coppia))
        notti_c[coppia] = notti
        del M
    ops = pd.concat(parti, ignore_index=True)
    ops["data"] = fa.NOTTI[ops["notte"].values]
    return ops, notti_c


# ---------------------------------------------------------------- statistiche
def t_notti(net, notte, sel, nv):
    """t sul netto con somme per notte (stesso calcolo di fa.statistiche_notte)."""
    x = np.bincount(notte, weights=net, minlength=fa.NN)[sel]
    _, t = fa.statistiche_notte(x, nv)
    return float(t)


def misura(ops, notti_c, da, a_, placebo=True):
    sel = (fa.NOTTI >= da) & (fa.NOTTI < a_)
    q = ops[(ops["data"] >= da) & (ops["data"] < a_)].sort_values(["notte", "e", "coppia"])
    V = {c: notti_c[c]["valida"].values & sel for c in COPPIE_C1}
    nv_p = {c: int(V[c].sum()) for c in COPPIE_C1}
    nv_any = int(np.logical_or.reduce([V[c] for c in COPPIE_C1]).sum())
    g, gm, c = (q[k].values.astype(float) for k in ("g", "gm", "c"))
    net, net15 = g - c, g - 1.5 * c
    notte = q["notte"].values.astype(int)
    anni = pd.Series(net).groupby(q["data"].dt.year.values).sum()
    anni15 = pd.Series(net15).groupby(q["data"].dt.year.values).sum()
    r = dict(n=len(q), notti_valide=nv_any,
             op_giorno=sum(((q["coppia"] == k).sum() / nv_p[k]) for k in COPPIE_C1),
             lordo_op=g.mean(), netto_op=net.mean(), netto15_op=net15.mean(),
             netto_su_costo=net.sum() / c.sum(), t=t_notti(net, notte, sel, nv_any),
             t15=t_notti(net15, notte, sel, nv_any),
             anni_pos=int((anni > 0).sum()), anni_tot=len(anni), anni15_pos=int((anni15 > 0).sum()),
             pareggio_x=g.sum() / c.sum())
    if placebo:
        rng = np.random.default_rng(fa.SEED)
        att, cnt = net.mean(), 0
        for _ in range(10):
            ch = rng.random((100, len(g))) < 0.5
            cnt += ((np.where(ch, g, gm) - c).mean(1) >= att).sum()
        r["p_placebo"] = (cnt + 1) / 1001
    w1, sk, ss, dd = fa.rischio(net)
    _, _, _, dd15 = fa.rischio(net15)
    tp = q["tipo"].value_counts(normalize=True)
    r.update(vinte=(net > 0).mean(), media_vinta=net[net > 0].mean(), media_persa=net[net <= 0].mean(),
             peggiore=w1, serie_perse=sk, serie_pip=ss, dd_pip=dd, dd15_pip=dd15,
             quota_stop=tp.get(0, 0), quota_obiettivo=tp.get(1, 0), quota_tempo=tp.get(2, 0))
    return r, q, anni, anni15, nv_p, sel


def per_coppia(q, notti_c, sel):
    righe = []
    for k in COPPIE_C1:
        z = q[q["coppia"] == k]
        V = notti_c[k]["valida"].values & sel
        g, c = z["g"].values.astype(float), z["c"].values.astype(float)
        net = g - c
        an = pd.Series(net).groupby(z["data"].dt.year.values).sum()
        righe.append(dict(coppia=k, n=len(z), op_giorno=len(z) / V.sum(), netto_op=net.mean(),
                          netto15_op=(g - 1.5 * c).mean(), netto_tot=net.sum(),
                          t=t_notti(net, z["notte"].values.astype(int), sel, int(V.sum())),
                          anni_pos=int((an > 0).sum()), anni_tot=len(an), pareggio_x=g.sum() / c.sum()))
    return pd.DataFrame(righe)


def fasce(q):
    ora_min = (q["e"].astype(int) * 5 + 1330) % 1440          # minuto UTC d'entrata
    fascia = np.where(ora_min < 60, "00:00-00:55", "01:00-05:25")
    out = []
    for f in ("00:00-00:55", "01:00-05:25"):
        z = q[fascia == f]
        g, c = z["g"].values.astype(float), z["c"].values.astype(float)
        out.append(dict(fascia=f, n=len(z), lordo_op=g.mean(), netto_op=(g - c).mean(),
                        netto15_op=(g - 1.5 * c).mean(), pareggio_x=g.sum() / c.sum()))
    return pd.DataFrame(out)


# ---------------------------------------------------------------- fasi
def calendario_scoperta():
    return pd.bdate_range("2010-01-04", "2017-12-29")


def fase_riproduci(stampa=True):
    imposta(SCOPERTA, calendario_scoperta())
    ops, notti_c = simula_c1()
    r, q, anni, anni15, nv_p, sel = misura(ops, notti_c, pd.Timestamp("2010-01-01"), pd.Timestamp("2018-01-01"))
    # t anche con le notti valide di tutte le 7 coppie (come in fase_aggrega)
    V7 = np.zeros(fa.NN, bool)
    for k in fa.COPPIE:
        V7 |= pd.read_parquet(f"{RIS}\\a_notte_notti_{k}.parquet")["valida"].values
    net = (q["g"].values.astype(float) - q["c"].values.astype(float))
    r["t_nv7"] = t_notti(net, q["notte"].values.astype(int), sel, int(V7.sum()))
    # confronto operazione per operazione col file della scoperta
    ref = pd.read_parquet(f"{RIS}\\a_notte_candidato1_operazioni.parquet")
    k = ["coppia", "notte", "e", "x", "dir"]
    m = q.merge(ref[k + ["g", "c"]], on=k, how="outer", suffixes=("", "_ref"), indicator=True)
    r["uguali_op"] = int((m["_merge"] == "both").sum())
    r["diff_g_max"] = float((m["g"] - m["g_ref"]).abs().max())
    ok = (r["n"] == ATTESI["n"]
          and abs(r["netto_op"] / ATTESI["netto_op"] - 1) < 0.01
          and abs(r["netto15_op"] / ATTESI["netto15_op"] - 1) < 0.01
          and abs(r["t"] / ATTESI["t"] - 1) < 0.01 and r["anni_pos"] == ATTESI["anni_pos"])
    r["riprodotto"] = ok
    if stampa:
        print("RIPRODUZIONE scoperta 2010-2017")
        print(pd.Series(r).to_string())
        print("notti valide per coppia:", nv_p)
        print(per_coppia(q, notti_c, sel).round(3).to_string(index=False))
        print(pd.DataFrame({"x1": anni, "x1,5": anni15}).round(1).T.to_string())
    return ok, r


def fase_confine():
    """Prova dentro la scoperta: indicatori da una coda di 400 giorni del 2015-16 + dati 2017."""
    inizio = pd.Timestamp("2017-01-01", tz="UTC")
    pezzi = [(SCOPERTA, inizio - pd.Timedelta(days=CODA_GIORNI), inizio),
             (SCOPERTA, inizio, pd.Timestamp("2100-01-01", tz="UTC"))]
    imposta("CONCAT", pd.bdate_range((inizio - pd.Timedelta(days=CODA_GIORNI)).tz_localize(None),
                                     "2017-12-29"), pezzi)
    ops, _ = simula_c1()
    a = ops[ops["data"] >= "2017-01-01"]
    ref = pd.read_parquet(f"{RIS}\\a_notte_candidato1_operazioni.parquet")
    ref = ref[ref["anno"] == 2017]
    k = ["coppia", "e", "x", "dir"]
    a = a.assign(giorno=a["data"].values)
    ref = ref.assign(giorno=calendario_scoperta()[ref["notte"].values])
    m = a.merge(ref[k + ["giorno", "g"]], on=k + ["giorno"], how="outer", suffixes=("", "_ref"),
                indicator=True)
    print(f"prova del confine 2017: operazioni coda+2017 {len(a)}, scoperta 2017 {len(ref)}, "
          f"in comune {(m['_merge'] == 'both').sum()}, diff g max {(m['g'] - m['g_ref']).abs().max():.6f}")
    return len(a) == len(ref) == (m["_merge"] == "both").sum()


def fase_verifica():
    ok, _ = fase_riproduci(stampa=False)
    assert ok, "riproduzione non coincide: la verifica non si apre"
    inizio = pd.Timestamp("2018-01-01", tz="UTC")
    pezzi = [(SCOPERTA, inizio - pd.Timedelta(days=CODA_GIORNI), inizio),
             (VERIFICA, inizio, pd.Timestamp("2100-01-01", tz="UTC"))]
    ultimo = _read_orig(f"{VERIFICA}\\EURUSD_D1.parquet").index[-1].tz_localize(None)
    notti = pd.bdate_range((inizio - pd.Timedelta(days=CODA_GIORNI)).tz_localize(None),
                           ultimo + pd.Timedelta(days=1))
    imposta("CONCAT", notti, pezzi)
    ops, notti_c = simula_c1()
    da, a_ = pd.Timestamp("2018-01-01"), pd.Timestamp("2100-01-01")
    r, q, anni, anni15, nv_p, sel = misura(ops, notti_c, da, a_)
    pc = per_coppia(q, notti_c, sel)
    fa_ = fasce(q)
    # x1,5 per coppia/anno e costo di pareggio in pip
    pc["pareggio_pip"] = [fa.COSTO[k] * x for k, x in zip(pc["coppia"], pc["pareggio_x"])]
    soglia_anni = int(np.ceil(2 / 3 * r["anni_tot"]))
    r["verdetto"] = bool(r["netto_op"] > 0 and r["netto15_op"] > 0 and r["t"] >= 2
                         and r["anni_pos"] >= soglia_anni and r["p_placebo"] < 0.01
                         and r["op_giorno"] >= 1)
    r["soglia_anni"] = soglia_anni
    r["prima_notte"] = str(q["data"].min().date()); r["ultima_notte"] = str(q["data"].max().date())
    print("VERIFICA C1 2018 -> fine dati")
    print(pd.Series(r).to_string())
    print("notti valide per coppia:", nv_p)
    print(pc.round(3).to_string(index=False))
    an = pd.DataFrame({"x1": anni, "x1,5": anni15,
                       "n": q.groupby(q["data"].dt.year).size()})
    for k in COPPIE_C1:
        z = q[q["coppia"] == k]
        an[k] = (z["g"] - z["c"]).groupby(z["data"].dt.year).sum()
    print(an.round(1).T.to_string())
    print(fa_.round(3).to_string(index=False))
    ora = (q["e"].astype(int) * 5 + 1330) // 60 % 24
    print(q.assign(net=q["g"] - q["c"], ora=ora).groupby("ora")["net"].agg(["size", "mean"]).round(2).T.to_string())
    q.to_parquet(f"{RIS}\\verifica_C1_operazioni.parquet")
    pd.DataFrame([r]).to_parquet(f"{RIS}\\verifica_C1_riepilogo.parquet")
    pc.to_parquet(f"{RIS}\\verifica_C1_coppie.parquet")
    an.reset_index(names="anno").to_parquet(f"{RIS}\\verifica_C1_anni.parquet")
    fa_.to_parquet(f"{RIS}\\verifica_C1_fasce.parquet")


if __name__ == "__main__":
    fase = sys.argv[1] if len(sys.argv) > 1 else "riproduci"
    {"riproduci": fase_riproduci, "confine": fase_confine, "verifica": fase_verifica}[fase]()
