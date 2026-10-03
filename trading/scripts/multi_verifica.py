"""Verifica 2018 -> fine dati dei quattro candidati multi-giorno sul paniere.

Candidati congelati: docs/multigiorno-paniere-candidati.md (commit 8445ca6).
Regole = codice di scoperta importato e usato SENZA modifiche:
  M1-M3  multi_f2_ritorno.py  (prepara, segnali_mercato, operazioni, misure)
  M4     multi_f4_breakout.py (simula_mercato, misure, costo_rt), regola N20 R S3 D5 F1
Si adatta solo la lettura dei dati (D1 concatenate, M5 concatenate) e il periodo
(globali ANNO0/ANNO1, INIZIO, MESI, ANNI dei due moduli).

Fasi:
  python multi_verifica.py riproduci  -> rifa' M1-M4 sulla scoperta e li confronta coi numeri
                                         congelati (+ operazioni salvate dalla scoperta);
                                         prova del confine DENTRO la scoperta (coda 2015-16 + 2017)
  python multi_verifica.py verifica   -> riproduzione + confine (devono passare), poi UNA sola
                                         esecuzione su D:\\ricerca_multi\\verifica (2018 -> fine dati)

Confine: gli indicatori (media 200, ATR20, ATR100, canale a 20 giornate) richiedono storia del
2017: per ogni mercato si concatenano le ultime CODA giornate della scoperta davanti alla verifica
(solo per indicatori e stato della posizione); contano le operazioni con entrata dal 2018-01-01.
"""
import ast
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import multi_f2_ritorno as f2          # noqa: E402
import multi_f4_breakout as f4         # noqa: E402

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

BASE = Path(r"D:\ricerca_multi")
SCOP = BASE / "scoperta" / "PANIERE_D1.parquet"
VERI = BASE / "verifica" / "PANIERE_D1.parquet"
RIS = BASE / "risultati"
M5_SCOP, M5_VERI = Path(r"D:\ricerca_zero\scoperta"), Path(r"D:\ricerca_zero\verifica")
CODA = 400                      # giornate della scoperta davanti al periodo (>= 300)
T_SOGLIA = 2.6                  # k = 4 candidati
P_SOGLIA = 0.05

F2_CAND = {   # id: (mercati, segnale, H, stop, filtro)
    "M1": (["SPXUSD"], ("MOSSA", 5, 1.5), 5, 1, 1),
    "M2": (["SPXUSD", "NSXUSD", "GRXEUR"], ("MOSSA", 5, 2.0), 3, 0, 1),
    "M3": (["NSXUSD"], ("MOSSA", 3, 1.5), 3, 1, 1),
}
F2_UNIV = {"M1": "SPXUSD", "M2": "indici", "M3": "NSXUSD"}
F4_REGOLA = (20, "R", 3, "D5", 1)
F4_NOME = "N20 R S3 D5 F1"
METALLI = ["XAUUSD", "XAGUSD"]

ATTESI = {   # docs/multigiorno-paniere-candidati.md
    "M1": dict(n=65, netto_R=0.396, t=4.85, anni_pos=7, p=0.001),
    "M2": dict(n=156, netto_R=0.237, t=4.56, anni_pos=7, p=0.001),
    "M3": dict(n=71, netto_R=0.289, t=3.99, anni_pos=6, p=0.001),
    "M4": dict(n=256, netto_R=0.153, t=3.42, anni_pos=7, p=0.001),
}

# regola M4 sola: i globali della griglia sono letti da simula_mercato al momento della chiamata;
# ogni regola e' indipendente (stato "ultimo" per regola), quindi restringere la griglia non
# cambia le sue operazioni (lo controlla il confronto col file della scoperta)
f4.LIVELLI, f4.MODI, f4.STOPM, f4.USCITE, f4.FILTRI = [20], ["R"], [3], ["D5"], [1]


def controlla_spread_oro():
    """Il costo dell'oro dal 2020 deve essere SPREAD di verifica_bot.py (+0,06 in costo_rt)."""
    testo = (Path(__file__).resolve().parent / "verifica_bot.py").read_text(encoding="utf-8")
    i = testo.index("SPREAD = {")
    j = testo.index("}", i)
    spread = ast.literal_eval(testo[i + len("SPREAD = "):j + 1])
    assert spread == f4.SPREAD_ORO, (spread, f4.SPREAD_ORO)
    assert abs(f4.costo_rt("XAUUSD", 2022, {}) - (spread[2022] + 0.06)) < 1e-12
    return spread


# ---------------------------------------------------------------- dati
def concatena(scop, dopo, inizio):
    """Per ogni mercato: ultime CODA giornate della scoperta prima di `inizio` + `dopo`."""
    parti = []
    for mk, g in scop.groupby("mercato", sort=False):
        g = g.sort_values("giorno")
        parti.append(g[g["giorno"] < inizio].tail(CODA))
        parti.append(dopo[dopo["mercato"] == mk].sort_values("giorno"))
    out = pd.concat(parti, ignore_index=True)
    for mk, g in out.groupby("mercato"):
        assert g["giorno"].is_monotonic_increasing and g["giorno"].is_unique, mk
    return out


_M5_PEZZI = None
_carica_m5_orig = f4.carica_m5


def _carica_m5(mercato):
    """Come f4.carica_m5 ma su M5 concatenate: coda della scoperta + verifica."""
    if _M5_PEZZI is None:
        return _carica_m5_orig(mercato)
    da = _M5_PEZZI
    a = pd.read_parquet(M5_SCOP / f"{mercato}_M5.parquet", columns=["open", "high", "low", "close"])
    a = a[a.index >= da]
    b = pd.read_parquet(M5_VERI / f"{mercato}_M5.parquet", columns=["open", "high", "low", "close"])
    b = b[b.index > a.index.max()]
    m = pd.concat([a, b])
    del a, b
    assert m.index.is_monotonic_increasing and m.index.is_unique
    ts = m.index.tz_convert("UTC").tz_localize(None).values
    lab = (ts + np.timedelta64(2, "h")).astype("datetime64[D]")
    return (lab, m["open"].to_numpy(float), m["high"].to_numpy(float), m["low"].to_numpy(float))


f4.carica_m5 = _carica_m5


# ---------------------------------------------------------------- M1-M3 (F2)
def isig_di(seg):
    return f2.SEGNALI.index(seg)


def ops_f2(dval, costi, cid, da, a, anno0, anno1):
    """Operazioni del candidato cid con entrata in [da, a) + dati per il placebo."""
    mercati, seg, H, st, filt = F2_CAND[cid]
    isig = isig_di(seg)
    f2.ANNO0, f2.ANNO1 = anno0, anno1
    out, PP = [], {}
    for m in mercati:
        g = dval[dval["mercato"] == m]
        if g.empty:
            continue
        P = f2.prepara(g, {"rt": costi[m], "oro": m == "XAUUSD"})
        es = P["es"]
        dirz = f2.segnali_mercato(P, isig, filt)
        ent, dr = f2.operazioni(P, dirz, H, st)
        L, S = es[(H, st, 1)], es[(H, st, -1)]

        def pick(k, e=ent, q=dr):
            return np.where(q == 1, L[k][e], S[k][e])
        op = pd.DataFrame({
            "candidato": cid, "mercato": m, "dir": dr, "ent_idx": ent,
            "entrata_data": pd.to_datetime(P["date"][ent]),
            "uscita_data": pd.to_datetime(P["date"][pick("uscita").astype(int)]) if len(ent) else pd.to_datetime([]),
            "lordo": pick("lordo"), "swap": pick("swap"), "costo": pick("costo"),
            "netto": pick("netto"), "stopp": pick("stopp"),
            "netto_opposto": np.where(dr == 1, S["netto"][ent], L["netto"][ent]),
        })
        op["netto15"] = op["netto"] - 0.5 * op["costo"]
        op = op[(op["entrata_data"] >= da) & (op["entrata_data"] < a)].reset_index(drop=True)
        out.append(op)
        PP[m] = P
    return pd.concat(out, ignore_index=True), PP


def placebo_f2(op, PP, cid, da, a, seed):
    """Stessi tre placebo della scoperta, con le date casuali prese fra le entrate del periodo."""
    _, _, H, st, _ = F2_CAND[cid]
    rng = np.random.default_rng(seed)
    pdir = np.zeros(f2.NPLAC)
    pdat = np.zeros(f2.NPLAC)
    pflt = np.zeros(f2.NPLAC)
    for m, P in PP.items():
        q = op[op["mercato"] == m]
        n = len(q)
        if n == 0:
            continue
        es = P["es"]
        L, S = es[(H, st, 1)], es[(H, st, -1)]
        dr = q["dir"].to_numpy()
        vr, vo = q["netto"].to_numpy(), q["netto_opposto"].to_numpy()
        mask = rng.random((f2.NPLAC, n)) < 0.5
        pdir += vr.sum() + mask.astype(float) @ (vo - vr)
        eleg = es[(H, st, "eleg")]
        de = P["date"][eleg]
        eleg = eleg[(de >= np.datetime64(da.date())) & (de < np.datetime64(a.date()))]
        pos = eleg[rng.integers(0, len(eleg), size=(f2.NPLAC, n))]
        pdat += np.where(dr[None, :] == 1, L["netto"][pos], S["netto"][pos]).sum(1)
        cs, ss = P["c"][eleg - 1], P["sma"][eleg - 1]
        with np.errstate(invalid="ignore"):
            eL, eS = eleg[cs > ss], eleg[cs < ss]
        u = rng.random((f2.NPLAC, n))
        vL = L["netto"][eL[(u * len(eL)).astype(int)]] if len(eL) else 0
        vS = S["netto"][eS[(u * len(eS)).astype(int)]] if len(eS) else 0
        pflt += np.where(dr[None, :] == 1, vL, vS).sum(1)
    return pdir, pdat, pflt


# ---------------------------------------------------------------- M4 (F4)
def ops_f4(pan, costi, inizio_sim, da, a, m5_da=None):
    """Operazioni N20 R S3 D5 F1 su oro e argento con entrata in [da, a)."""
    global _M5_PEZZI
    f4.INIZIO = inizio_sim
    _M5_PEZZI = m5_da
    parti = []
    for mk in METALLI:
        t = f4.simula_mercato(mk, pan, costi)
        lv, mo, m, ex, fl = F4_REGOLA
        t = t[(t["lv"] == str(lv)) & (t["modo"] == mo) & (t["m"] == m) & (t["uscita"] == ex)
              & (t["filtro"] == fl)]
        parti.append(t)
    _M5_PEZZI = None
    t = pd.concat(parti, ignore_index=True)
    t = t[(t["g_entrata"] >= da) & (t["g_entrata"] < a)].reset_index(drop=True)
    t["net"] = t["lordo_R"] - t["costo_R"] + t["swap_R"]
    t["net_m"] = t["lordo_m_R"] - t["costo_R"] + t["swap_m_R"]
    t["net15"] = t["lordo_R"] - 1.5 * t["costo_R"] + t["swap_R"]
    return t


def misure_f4(t, mercati):
    """f4.misure + placebo a direzione casuale (seed della scoperta) sul sottoinsieme."""
    rng = np.random.default_rng(f4.SEED)
    scelta = rng.random((f4.NPLACEBO, len(t))) < 0.5
    reale, spec = t["net"].to_numpy(), t["net_m"].to_numpy()
    val = np.where(scelta, reale, spec)
    sel = t["mercato"].isin(mercati).to_numpy()
    g = t[sel]
    r = f4.misure(g)
    plac = val[:, sel].sum(axis=1)
    r["p"] = (1 + (plac >= reale[sel].sum()).sum()) / (1 + f4.NPLACEBO)
    return r


# ---------------------------------------------------------------- riepilogo comune
def anni_R(uscita, net, anni):
    return pd.Series(net, index=uscita.dt.year.to_numpy()).groupby(level=0).sum().reindex(anni, fill_value=0.0)


def riepilogo_f2(op, mesi, anni, pdir, pdat, pflt):
    r = f2.misure(op, mesi, pdir, pdat)
    tot = op["netto"].sum()
    r["p_date_filtro"] = (1 + (pflt >= tot).sum()) / (f2.NPLAC + 1)
    r["totale15_R"] = op["netto15"].sum()
    r["peggiore_R"] = op["netto"].min()
    r["long"] = (op["dir"] == 1).mean()
    ya = anni_R(op["uscita_data"], op["netto"].to_numpy(), anni)
    r["anni_pos"] = int((ya > 0).sum())
    r["anni_tot"] = len(anni)
    return r, ya


def riepilogo_f4(t, mercati, anni):
    r = misure_f4(t, mercati)
    g = t[t["mercato"].isin(mercati)]
    r.update(netto_R=r["netto_R"], totale_R=r["netto_tot"], totale15_R=r["netto15_tot"],
             t_mens=r["t"], dd_R=r["dd"], peggiore_R=g["net"].min(), p_dir=r["p"],
             long=(g["dir"] == 1).mean(), quota_stop=(g["giorni"] == 0).mean())
    ya = anni_R(g["g_uscita"], g["net"].to_numpy(), anni)
    r["anni_pos"] = int((ya > 0).sum())
    r["anni_tot"] = len(anni)
    return r, ya


# ---------------------------------------------------------------- fasi
def leggi():
    costi = pd.read_csv(BASE / "costi.csv").set_index("mercato")["costo_rt"].to_dict()
    return pd.read_parquet(SCOP), costi


def fase_riproduci():
    controlla_spread_oro()
    scop, costi = leggi()
    sval = scop[scop["valida"]]
    da, a = pd.Timestamp("2010-01-01"), pd.Timestamp("2018-01-01")
    anni = list(range(2010, 2018))
    ok_tutto = True
    ref_op = pd.read_parquet(RIS / "f2_operazioni.parquet",
                             columns=["regola", "mercato", "entrata_data", "dir", "netto"])
    print("RIPRODUZIONE sulla scoperta 2010-2017")
    righe = []
    for cid in F2_CAND:
        op, PP = ops_f2(sval, costi, cid, da, a, 2010, 2017)
        mercati, seg, H, st, filt = F2_CAND[cid]
        primo = min(pd.Timestamp(PP[m]["date"][PP[m]["base_ok"]][0]).to_period("M") for m in PP)
        mesi = pd.period_range(primo, "2017-12", freq="M")
        pdir, pdat, pflt = placebo_f2(op, PP, cid, da, a, f2.SEED)
        r, ya = riepilogo_f2(op, mesi, anni, pdir, pdat, pflt)
        # confronto con le operazioni salvate dalla scoperta
        reg = f"{f2.nome_segnale(isig_di(seg))} H{H} {'stop' if st else 'tempo'} {'m200' if filt else 'tutti'}"
        rf = ref_op[(ref_op["regola"] == reg) & ref_op["mercato"].isin(mercati)]
        mm = op.merge(rf, on=["mercato", "entrata_data", "dir"], how="outer", indicator=True,
                      suffixes=("", "_ref"))
        uguali = int((mm["_merge"] == "both").sum())
        dmax = float((mm["netto"] - mm["netto_ref"]).abs().max())
        e = ATTESI[cid]
        ok = (r["n"] == e["n"] and abs(r["netto_R"] / e["netto_R"] - 1) < 0.01
              and abs(r["t_mens"] / e["t"] - 1) < 0.01 and r["anni_pos"] == e["anni_pos"]
              and r["p_dir"] <= e["p"] + 1e-9 and r["p_date"] <= e["p"] + 1e-9
              and uguali == len(op) == len(rf) and dmax < 1e-9)
        ok_tutto &= ok
        righe.append(dict(id=cid, n=r["n"], netto_R=r["netto_R"], t=r["t_mens"], anni=r["anni_pos"],
                          p_dir=r["p_dir"], p_date=r["p_date"], p_date_filtro=r["p_date_filtro"],
                          op_salvate=len(rf), uguali=uguali, diff_max=dmax, ok=ok))
    # M4
    t = ops_f4(scop, costi, pd.Timestamp("2010-01-01"), da, a)
    f4.MESI = pd.period_range("2010-01", "2017-12", freq="M")
    f4.ANNI = anni
    r, _ = riepilogo_f4(t, METALLI, anni)
    rs, _ = riepilogo_f4(t, ["XAGUSD"], anni)
    rf = pd.concat([pd.read_parquet(RIS / f"f4_operazioni_{mk}.parquet") for mk in METALLI])
    rf = rf[(rf["lv"] == "20") & (rf["modo"] == "R") & (rf["m"] == 3) & (rf["uscita"] == "D5")
            & (rf["filtro"] == 1) & (rf["g_entrata"] <= f4.FINE)]
    mm = t.merge(rf[["mercato", "g_entrata", "dir", "lordo_R"]], on=["mercato", "g_entrata", "dir"],
                 how="outer", indicator=True, suffixes=("", "_ref"))
    uguali = int((mm["_merge"] == "both").sum())
    dmax = float((mm["lordo_R"] - mm["lordo_R_ref"]).abs().max())
    e = ATTESI["M4"]
    ok = (r["n"] == e["n"] and abs(r["netto_R"] / e["netto_R"] - 1) < 0.01
          and abs(r["t"] / e["t"] - 1) < 0.01 and r["anni"] == e["anni_pos"]
          and r["p"] <= e["p"] + 1e-9 and uguali == len(t) == len(rf) and dmax < 1e-9
          and rs["n"] == 127 and abs(rs["t"] / 2.894 - 1) < 0.01)
    ok_tutto &= ok
    righe.append(dict(id="M4", n=r["n"], netto_R=r["netto_R"], t=r["t"], anni=r["anni"], p_dir=r["p"],
                      p_date=np.nan, p_date_filtro=np.nan, op_salvate=len(rf), uguali=uguali,
                      diff_max=dmax, ok=ok))
    righe.append(dict(id="M4 solo XAG", n=rs["n"], netto_R=rs["netto_R"], t=rs["t"], anni=rs["anni"],
                      p_dir=rs["p"], p_date=np.nan, p_date_filtro=np.nan, op_salvate=np.nan,
                      uguali=np.nan, diff_max=np.nan, ok=ok))
    print(pd.DataFrame(righe).round(4).to_string(index=False))
    ok_conf = fase_confine(scop, costi)
    print(f"RIPRODUZIONE {'OK' if ok_tutto else 'NON COINCIDE'}; CONFINE {'OK' if ok_conf else 'NON COINCIDE'}")
    return ok_tutto and ok_conf


def fase_confine(scop, costi):
    """Dentro la scoperta: coda di CODA giornate prima del 2017 + 2017; operazioni 2017 identiche."""
    inizio = pd.Timestamp("2017-01-01")
    fine = pd.Timestamp("2018-01-01")
    pan = concatena(scop, scop[scop["giorno"] >= inizio], inizio)
    pval = pan[pan["valida"]]
    sval = scop[scop["valida"]]
    anno0 = int(pan["giorno"].dt.year.min())
    righe, ok = [], True
    for cid in F2_CAND:
        a1, _ = ops_f2(pval, costi, cid, inizio, fine, anno0, 2017)
        a0, _ = ops_f2(sval, costi, cid, inizio, fine, 2010, 2017)
        mm = a1.merge(a0, on=["mercato", "entrata_data", "dir"], how="outer", indicator=True)
        u = int((mm["_merge"] == "both").sum())
        d = float((mm["netto_x"] - mm["netto_y"]).abs().max())
        righe.append(dict(id=cid, coda_2017=len(a1), scoperta_2017=len(a0), in_comune=u, diff_max=d))
        ok &= (len(a1) == len(a0) == u) and d < 1e-9
    t1 = ops_f4(pan, costi, pan["giorno"].min(), inizio, fine)
    t0 = ops_f4(scop, costi, pd.Timestamp("2010-01-01"), inizio, fine)
    mm = t1.merge(t0, on=["mercato", "g_entrata", "dir"], how="outer", indicator=True)
    u = int((mm["_merge"] == "both").sum())
    d = float((mm["net_x"] - mm["net_y"]).abs().max())
    righe.append(dict(id="M4", coda_2017=len(t1), scoperta_2017=len(t0), in_comune=u, diff_max=d))
    ok &= (len(t1) == len(t0) == u) and d < 1e-9
    print(f"CONFINE dentro la scoperta (coda {CODA} giornate + 2017, coda dal {pan['giorno'].min().date()})")
    print(pd.DataFrame(righe).to_string(index=False))
    return ok


def fase_verifica():
    assert fase_riproduci(), "riproduzione o confine non coincidono: la verifica non si apre"
    scop, costi = leggi()
    veri = pd.read_parquet(VERI)
    inizio = pd.Timestamp("2018-01-01")
    fine = pd.Timestamp("2100-01-01")
    pan = concatena(scop, veri, inizio)
    pval = pan[pan["valida"]]
    anno0 = int(pan["giorno"].dt.year.min())
    ultimo = veri["giorno"].max()
    mesi = pd.period_range("2018-01", ultimo.to_period("M"), freq="M")
    anni = list(range(2018, ultimo.year + 1))
    print(f"\nVERIFICA 2018 -> {ultimo.date()} (mesi {len(mesi)}, anni {anni[0]}-{anni[-1]}, "
          f"{ultimo.year} parziale); coda dal {pan['giorno'].min().date()}")
    print(veri.groupby("mercato")["giorno"].agg(["min", "max"]).loc[["SPXUSD", "NSXUSD", "GRXEUR"] + METALLI])

    righe, anni_t, ops_all = [], {}, []
    for cid in F2_CAND:
        op, PP = ops_f2(pval, costi, cid, inizio, fine, anno0, ultimo.year)
        pdir, pdat, pflt = placebo_f2(op, PP, cid, inizio, fine, f2.SEED)
        r, ya = riepilogo_f2(op, mesi, anni, pdir, pdat, pflt)
        r["id"] = cid
        righe.append(r)
        anni_t[cid] = ya
        ops_all.append(op.assign(netto15=op["netto15"]))
        print(f"\n{cid} per mercato:")
        print(op.groupby("mercato").agg(n=("netto", "size"), netto_R=("netto", "mean"),
                                        tot=("netto", "sum"), long=("dir", lambda x: (x == 1).mean()),
                                        ultima=("entrata_data", "max")).round(3).to_string())
        print(f"{cid} lato: " + ", ".join(f"{'long' if k == 1 else 'short'} n {len(g)} netto {g['netto'].mean():+.3f}"
                                          for k, g in op.groupby("dir")))

    f4.MESI, f4.ANNI = mesi, anni
    # M5: coda della scoperta dall'inizio della coda dei metalli + verifica
    t = ops_f4(pan, costi, pan["giorno"].min(), inizio, fine,
               m5_da=pd.Timestamp(pan[pan["mercato"].isin(METALLI)]["giorno"].min(), tz="UTC")
               - pd.Timedelta(days=1))
    for amb, mk in (("M4", METALLI), ("M4 solo XAG", ["XAGUSD"]), ("M4 solo XAU", ["XAUUSD"])):
        r, ya = riepilogo_f4(t, mk, anni)
        r["id"] = amb
        r["p_date"] = r["p_date_filtro"] = np.nan
        righe.append(r)
        anni_t[amb] = ya
    ops_all.append(t.assign(candidato="M4"))
    print("\nM4 lato: " + ", ".join(f"{m} {'long' if k == 1 else 'short'} n {len(g)} netto {g['net'].mean():+.3f}"
                                   for (m, k), g in t.groupby(["mercato", "dir"])))

    V = pd.DataFrame(righe).set_index("id")
    V["soglia_anni"] = [math.ceil(2 / 3 * x) for x in V["anni_tot"]]
    V["anni_pos_senza_ultimo"] = [int((anni_t[i].drop(anni[-1]) > 0).sum()) for i in V.index]
    pmax = V[["p_dir", "p_date"]].max(axis=1, skipna=True)
    V["verdetto"] = np.where((V["netto_R"] > 0) & (V["netto15_R"] > 0) & (V["t_mens"] >= T_SOGLIA)
                             & (V["anni_pos"] >= V["soglia_anni"]) & (pmax < P_SOGLIA), "PASSA", "NON PASSA")
    col = ["n", "op_mese", "long", "netto_R", "netto15_R", "totale_R", "totale15_R", "t_mens", "anni_pos",
           "anni_tot", "soglia_anni", "anni_pos_senza_ultimo", "p_dir", "p_date", "p_date_filtro",
           "dd_R", "peggiore_R", "swap_R", "costo_R", "verdetto"]
    print("\nRIEPILOGO (costi x1 e x1,5 con swap; t sui rendimenti mensili)")
    print(V[col].round(3).T.to_string())
    A = pd.DataFrame(anni_t).T
    A.columns = [str(c) + ("*" if c == anni[-1] else "") for c in A.columns]
    print("\nR netti per anno di uscita (* = parziale)")
    print(A.round(1).to_string())

    RIS.mkdir(parents=True, exist_ok=True)
    o2 = pd.concat(ops_all[:-1], ignore_index=True)
    o2.to_parquet(RIS / "verifica_operazioni_M1M3.parquet", index=False)
    t.to_parquet(RIS / "verifica_operazioni_M4.parquet", index=False)
    V.reset_index().to_parquet(RIS / "verifica_riepilogo.parquet", index=False)
    A.reset_index(names="id").to_parquet(RIS / "verifica_anni.parquet", index=False)


if __name__ == "__main__":
    fase = sys.argv[1] if len(sys.argv) > 1 else "riproduci"
    {"riproduci": fase_riproduci, "verifica": fase_verifica}[fase]()
