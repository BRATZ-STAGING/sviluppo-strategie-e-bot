"""Ricerca da zero: verifica 2018 -> fine dati delle cinque ipotesi congelate.

Specifica vincolante: docs/ricerca-da-zero-candidati.md (commit b2c6202).
Ogni regola si calcola con le funzioni degli script di scoperta, importate e
NON modificate (zero_f1_orologio, zero_f2_momentum, zero_f4_volatilita,
zero_f5_calendario). Qui ci sono solo:
  - la scelta della cartella dati (scoperta, oppure coda della scoperta
    concatenata DAVANTI alla verifica, per gli indicatori causali al confine);
  - il taglio: in verifica contano solo le operazioni che ENTRANO dal
    2018-01-01 (i segnali prima del taglio si scartano prima della selezione
    delle operazioni non sovrapposte: il sistema "parte" il 2018-01-01);
  - il costo per anno dell'oro (0,40 nel 2018-2019, poi SPREAD di verifica_bot);
  - il riporto per operazione e il placebo riscritto per accettare un costo per
    operazione. Con costo costante e' identico a quello di scoperta: lo
    controlla il passo 'riproduci' (n, netto, t, anni e p esatti).

Uso (un mercato alla volta, niente multiprocessing):
  python trading/scripts/zero_verifica.py riproduci  # passo 1: solo scoperta
  python trading/scripts/zero_verifica.py prova      # percorso di verifica provato sulla scoperta (taglio 2015)
  python trading/scripts/zero_verifica.py verifica   # passo 2: UNA volta
  python trading/scripts/zero_verifica.py controllo  # passo 3: strategia ufficiale, gestione B

Uscite in D:\\ricerca_zero\\risultati\\verifica_*.parquet
"""
from __future__ import annotations

import gc
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)

import zero_f1_orologio as f1        # noqa: E402
import zero_f2_momentum as f2        # noqa: E402
import zero_f4_volatilita as f4      # noqa: E402
import zero_f5_calendario as f5      # noqa: E402

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

SCOP = Path(r"D:\ricerca_zero\scoperta")
VER = Path(r"D:\ricerca_zero\verifica")
RIS = Path(r"D:\ricerca_zero\risultati")
TMP = Path(r"D:\ricerca_zero\tmp_verifica")
CODA = pd.Timedelta(days=400)            # coda di scoperta davanti alla verifica
COSTO = {"XAUUSD": 0.40, "SPXUSD": 0.55, "NSXUSD": 1.50}
# copia di trading/scripts/verifica_bot.py (SPREAD); controllata in main()
SPREAD = {2020: 0.35, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}
SOGLIA_T = 2.6
MIN_OP_ANNO_VER = 10


@dataclass
class Periodo:
    nome: str
    cartella: Path
    inizio: pd.Timestamp | None          # UTC; None = nessun taglio
    costo_per_anno: bool

    def costo(self, sym: str, anni) -> np.ndarray:
        anni = np.asarray(anni, dtype=np.int64)
        if not self.costo_per_anno or sym != "XAUUSD":
            return np.full(len(anni), COSTO[sym], float)
        return np.array([0.40 if a <= 2019 else SPREAD[int(a)] for a in anni], float)


def costruisci(nome: str, prima: Path, dopo: Path | None, taglio: pd.Timestamp,
               simboli=("XAUUSD", "SPXUSD", "NSXUSD")) -> Periodo:
    """Cartella temporanea: coda di `prima` (CODA prima del taglio) + `dopo`."""
    out = TMP / nome
    out.mkdir(parents=True, exist_ok=True)
    for sym in simboli:
        for tf in ("M5", "D1"):
            a = pd.read_parquet(prima / f"{sym}_{tf}.parquet")
            coda = a[(a.index >= taglio - CODA) & (a.index < taglio)]
            if dopo is None:
                b = a[a.index >= taglio]
            else:
                b = pd.read_parquet(dopo / f"{sym}_{tf}.parquet")
                assert b.index[0] >= taglio
            x = pd.concat([coda, b])
            x = x[~x.index.duplicated()].sort_index()
            x.to_parquet(out / f"{sym}_{tf}.parquet")
            del a, b, coda, x
            gc.collect()
    return Periodo(nome, out, taglio, True)


# ---------------------------------------------------------------- utilita'
def riassunto(op: pd.DataFrame, t_col: str, min_anno_scop: int, tutti_gli_anni=False) -> dict:
    """Netto in prezzo, %, multipli del costo; anni con le due regole."""
    a = op.groupby("anno").agg(n=("netto", "size"), netto=("netto", "sum"),
                               netto_pct=("netto_pct", "sum"), tcol=(t_col, "sum"))
    sc = a[a.n >= min_anno_scop]
    ve = a if tutti_gli_anni else a[a.n >= MIN_OP_ANNO_VER]
    x = op[t_col].to_numpy(float)
    return {"n": len(op), "netto_px": op.netto.mean(), "netto_pct": op.netto_pct.mean(),
            "netto_costi": (op.netto / op.costo).mean(), "costo_medio": op.costo.mean(),
            "t": x.mean() / x.std(ddof=1) * np.sqrt(len(x)),
            "anni_pos_scop": int((sc.tcol > 0).sum()), "anni_scop": len(sc),
            "anni_pos_ver": int((ve.tcol > 0).sum()), "anni_ver": len(ve)}


def per_anno(op: pd.DataFrame, ipotesi: str, extra: str | None = None) -> pd.DataFrame:
    agg = dict(n=("netto", "size"), netto_tot=("netto", "sum"), netto_medio=("netto", "mean"),
               netto_pct_tot=("netto_pct", "sum"))
    if extra:
        agg["R_tot"] = (extra, "sum")
    return op.groupby("anno").agg(**agg).reset_index().assign(ipotesi=ipotesi)


# ---------------------------------------------------------------- H1 (famiglia 2)
def h1(per: Periodo):
    """S&P, decisione a ogni ora piena in Asia, |24 h| >= 1 ATR14 -> CONTRO, uscita +1 giorno."""
    sym = "SPXUSD"
    f2.SCOP = per.cartella
    P = f2.prepara(sym)
    if per.inizio is not None:
        cut = per.inizio.value // (60 * 10**9)
        P["X"]["1g"] = np.where(P["t"] >= cut, P["X"]["1g"], np.nan)
    ufficiale = f2.regola(P, sym, "1g", "1g", "asia", 1.0, "tutti", -1)
    # stessa selezione di f2.regola, per avere le operazioni
    j = list(f2.SESS).index("asia")
    x, g = P["X"]["1g"], P["YR"]["1g"]
    m = (P["t"] % 60 == 0) & (P["sess"] == j) & np.isfinite(x) & np.isfinite(g) & (np.abs(x) >= 1.0)
    idx = np.flatnonzero(m)
    ts, exl = P["t"][idx], P["EXLAB"]["1g"][idx]
    pres, i = [], 0
    while i < len(idx):
        pres.append(i)
        i = int(np.searchsorted(ts, exl[i], side="left"))
        if i <= pres[-1]:
            i = pres[-1] + 1
    sel = idx[np.asarray(pres)]
    d = np.sign(x[sel]) * -1
    mov = g[sel]
    t_dec = P["t"][sel]
    exlab = P["EXLAB"]["1g"][sel]
    del P
    gc.collect()
    lab, o, *_ = f2.carica(sym)
    ent, entlab = f2.o_fwd(lab, o, t_dec, 30)
    del lab, o
    anni = (t_dec // f2.DAY).astype("datetime64[D]").astype("datetime64[Y]").astype(int) + 1970
    costo = per.costo(sym, anni)
    op = pd.DataFrame({"ipotesi": "H1", "ts": pd.to_datetime(entlab * 60 * 10**9, utc=True),
                       "ts_uscita": pd.to_datetime(exlab * 60 * 10**9, utc=True),
                       "anno": anni, "dir": d, "entrata": ent, "lordo": d * mov, "costo": costo})
    op["netto"] = op.lordo - op.costo
    op["netto_pct"] = op.netto / op.entrata * 100
    op["giorno"] = op.ts_uscita.dt.tz_localize(None).dt.normalize()
    st = riassunto(op, "netto", 1)
    # placebo di f2.regola (seed fisso, 1000 serie a direzione casuale), costo per operazione
    rng = np.random.default_rng(f2.SEED)
    cnt, mu, cm = 0, op.netto.mean(), costo.mean()
    for _ in range(f2.NPLACEBO // 100):
        s = rng.choice(np.array([-1.0, 1.0]), size=(100, len(mov)))
        cnt += int(((s * mov[None, :]).mean(axis=1) - cm >= mu).sum())
    st["p"] = (cnt + 1) / (f2.NPLACEBO + 1)
    st["controllo_regola"] = ufficiale
    return st, op


# ---------------------------------------------------------------- H3 (famiglia 1)
def h3(per: Periodo, vid=94):
    """Oro: se 00:00->00:55 chiude sotto l'apertura, long 01:00 -> chiusura 06:55."""
    sym = "XAUUSD"
    m5 = f1.correggi_ora(pd.read_parquet(per.cartella / f"{sym}_M5.parquet"), sym)
    px = f1.Px(m5)
    del m5
    d0 = pd.Timestamp(px.t[0], tz="UTC").normalize().tz_localize(None)
    d1 = pd.Timestamp(px.t[-1], tz="UTC").normalize().tz_localize(None)
    days = pd.bdate_range(d0, d1).tz_localize("UTC")
    S = days.as_unit("ns").asi8 + 0 * 60 * f1.MIN            # Asia 0-7 UTC
    E = days.as_unit("ns").asi8 + 7 * 60 * f1.MIN
    SL = S + 60 * f1.MIN
    f = px.sig_oc(S, SL)
    m, p, ok = px.move(SL, E)
    s = np.sign(np.nan_to_num(f))
    dd = np.where(s < 0, 1, 0)                                 # "inverti solo long"
    jx, _ = px.cb(E)
    sel = np.isfinite(m) & (dd != 0) & np.isfinite(p)
    if per.inizio is not None:
        sel &= SL >= per.inizio.value
    m, dd, p, ts = m[sel], dd[sel].astype(float), p[sel], SL[sel]
    tsx = px.t[jx[sel]] + f1.BAR
    anni = pd.to_datetime(ts, utc=True).year.to_numpy()
    costo = per.costo(sym, anni)
    op = pd.DataFrame({"ipotesi": "H3", "ts": pd.to_datetime(ts, utc=True),
                       "ts_uscita": pd.to_datetime(tsx, utc=True), "anno": anni, "dir": dd,
                       "entrata": p, "lordo": dd * m, "costo": costo})
    op["netto"] = op.lordo - op.costo
    op["netto_pct"] = op.netto / op.entrata * 100
    op["giorno"] = op.ts.dt.tz_localize(None).dt.normalize()
    st = riassunto(op, "netto", 1)
    rng = np.random.default_rng(f1.SEED + vid)
    hits, mu, cm = 0, op.netto.mean(), costo.mean()
    for _ in range(f1.N_PLACEBO // 200):
        sg = rng.choice(np.array([-1.0, 1.0]), size=(200, len(m)))
        hits += int(((sg * m).mean(1) - cm >= mu).sum())
    st["p"] = (1 + hits) / (1 + f1.N_PLACEBO)
    return st, op


# ---------------------------------------------------------------- H2, H5 (famiglia 5)
def valuta5(F, g, anc, Ls, tipo, dirz, rng, cost_day, pool_mask):
    """f5.valuta con costo per giornata d'ancoraggio e pool del placebo DATE limitato."""
    ent, usc, lg, keep = [], [], [], np.zeros(len(anc), bool)
    for j, (a, L) in enumerate(zip(anc, Ls)):
        e, u, lordo, _, ok = F.arr(tipo, int(L))
        if 0 <= a < F.N and ok[a]:
            keep[j] = True
            ent.append(e[a]); usc.append(u[a]); lg.append(lordo[a])
    anc, Ls = anc[keep], Ls[keep]
    n = len(anc)
    ent, usc, lg = np.array(ent), np.array(usc), np.array(lg)
    cs = cost_day[anc] / ent
    netto_pct = dirz * lg - cs
    netto_px = dirz * (usc - ent) - cost_day[anc]
    mu = netto_pct.mean()
    pl = np.zeros(f5.N_PLACEBO)
    for L in np.unique(Ls):
        c = int((Ls == L).sum())
        e, _, lordo, _, ok = F.arr(tipo, int(L))
        pool = np.flatnonzero(ok & pool_mask)
        r = rng.integers(0, len(pool), size=(f5.N_PLACEBO, c))
        a = pool[r]
        pl += (dirz * lordo[a] - cost_day[a] / e[a]).sum(axis=1)
    pl /= n
    p_date = (1 + (pl >= mu).sum()) / (f5.N_PLACEBO + 1)
    s = np.where(rng.random((f5.N_PLACEBO, n)) < 0.5, 1.0, -1.0)
    p_dir = (1 + ((s * lg - cs).mean(axis=1) >= mu).sum()) / (f5.N_PLACEBO + 1)
    op = pd.DataFrame({"i_en": g.en.values[anc], "data": g.data.values[anc],
                       "giorno": g.data.values[anc + Ls], "L": Ls,
                       "anno": g.anno.values[anc], "dir": dirz, "entrata": ent, "uscita": usc,
                       "lordo": dirz * (usc - ent), "costo": cost_day[anc],
                       "netto": netto_px, "netto_pct": netto_pct * 100})
    return op, p_date, p_dir, pl.mean() * 100


def f5_ipotesi(per: Periodo, nome: str, sym: str, tipo: str, chiave, dirz: int, rng,
               min_anno_scop=f5.MIN_OP_ANNO, tutti_gli_anni=False):
    f5.SCOPERTA = per.cartella
    d = f5.carica(sym)
    g = f5.giornate(d, tipo, sym)
    ix = d.index
    del d
    gc.collect()
    F = f5.Finestre(g, COSTO[sym])
    wt, anc, Ls = f5.ancoraggi(g)[chiave]
    if per.inizio is not None:
        dentro = (g.data >= per.inizio.tz_localize(None)).values
        k = dentro[anc]
        anc, Ls = anc[k], Ls[k]
    else:
        dentro = np.ones(len(g), bool)
    cost_day = per.costo(sym, g.anno.values)
    op, p_date, p_dir, plm = valuta5(F, g, anc, Ls, wt, dirz, rng, cost_day, dentro)
    op.insert(0, "ipotesi", nome)
    op.insert(1, "ts", ix[op.pop("i_en").values])      # entrata: apertura dell'ultima M5 del giorno d'ancoraggio
    st = riassunto(op, "netto_pct", min_anno_scop, tutti_gli_anni)
    st.update(p_date=p_date, p_dir=p_dir, p=max(p_date, p_dir), placebo_medio_pct=plm)
    return st, op


def h2(per, rng):
    return f5_ipotesi(per, "H2", "XAUUSD", "22-22", ("a", "CC ven"), 1, rng)


def h5(per, rng):
    return f5_ipotesi(per, "H5", "NSXUSD", "cash", ("d", "OWP"), 1, rng, tutti_gli_anni=True)


def rng_f5_prima_di(target_id: int):
    """Stato del generatore di f5.main appena prima della variante `target_id`
    (rifa' il ciclo di f5.main con f5.valuta originale, senza scrivere nulla)."""
    rng = np.random.default_rng(f5.SEED)
    f5.SCOPERTA = SCOP
    vid = 0
    for sim in f5.SIMBOLI:
        d = f5.carica(sim)
        for tipo in ["22-22"] + (["cash"] if sim in f5.CASH else []):
            g = f5.giornate(d, tipo, sim)
            F = f5.Finestre(g, f5.COSTO[sim])
            for (fam, nome), (wt, anc, Ls) in f5.ancoraggi(g).items():
                if fam == "a" and wt == "OC" and tipo == "22-22":
                    continue
                if fam == "d" and sim not in ("SPXUSD", "NSXUSD"):
                    continue
                for dirz in (1, -1):
                    if vid + 1 == target_id:
                        print(f"  rng f5 catturato prima di id {target_id}: {sim} {tipo} {nome} {dirz}")
                        return rng
                    st, _ = f5.valuta(F, anc, Ls, wt, dirz, rng)
                    if st is not None:
                        vid += 1
            del g, F
        del d
        gc.collect()
    raise RuntimeError("id non trovato")


# ---------------------------------------------------------------- H4 (famiglia 4)
def h4(per: Periodo, rng):
    """Oro 22-22, regime ATR5/ATR60 < 0,8, rottura del giorno prima, stop a meta' range, uscita fine giorno."""
    sym = "XAUUSD"
    f4.SCOPERTA = per.cartella
    d = f4.carica(sym)
    f4.O, f4.H, f4.L, f4.C = (d[c].values.astype(np.float64) for c in ("open", "high", "low", "close"))
    f4.TS = d.index
    g = f4.tabella_giorni(d, "22-22", sym)
    del d
    gc.collect()
    fA, reg = f4.filtri(g)
    ev0 = f4.eventi_rottura(g, COSTO[sym])
    ev0["anno"] = g.anno.values[ev0.k.values + 1]
    ev0["data"] = g.data.values[ev0.k.values + 1]
    if per.inizio is not None:
        ev0 = ev0[(f4.TS[ev0.i0.values] >= per.inizio)]
    cev = per.costo(sym, ev0.anno.values)
    parti = []
    for c in np.unique(cev):                      # stesso calcolo, un costo per volta
        e = f4.prepara_rottura(g, ev0[cev == c], "S2", 1, c)
        e = f4.esiti(e, c, None)
        parti.append(e.assign(costo=c))
    ev = pd.concat(parti)
    tr = f4.non_sovrapposte(ev[reg["CMP"][ev.k.values]])
    sf4 = f4.statistiche(tr, float(tr.costo.mean()), rng)
    op = pd.DataFrame({"ipotesi": "H4", "ts": f4.TS[tr.i0.values], "ts_uscita": f4.TS[tr.jexit.values] + pd.Timedelta(minutes=5),
                       "giorno": tr.data.values, "anno": tr.anno.values, "dir": tr.dir.values,
                       "entrata": tr.entrata.values, "R": tr.R.values, "lordo": tr.lordo.values,
                       "costo": tr.costo.values, "netR": tr.netR.values})
    op["netto"] = op.lordo - op.costo
    op["netto_pct"] = op.netto / op.entrata * 100
    st = riassunto(op, "netR", f4.MIN_OP_ANNO)
    st.update(netR=sf4["netR"], t_f4=sf4["t"], p=sf4["p"], anni_pos_f4=sf4["anni_pos"],
              anni_f4=sf4["anni"], costo_R=sf4["costo_R"])
    f4.O = f4.H = f4.L = f4.C = f4.TS = None
    return st, op


def rng_f4_prima_di(riga: int):
    """Stato del generatore di f4.main prima della riga `riga` di f4_varianti:
    ogni chiamata a f4.statistiche con n >= 2 estrae rng.random((1000, n))."""
    V = pd.read_parquet(RIS / "f4_varianti.parquet")
    rng = np.random.default_rng(f4.SEED)
    for n in V.n.values[:riga]:
        if n >= 2:
            rng.random((f4.N_PLACEBO, int(n)))
    return rng


# ---------------------------------------------------------------- passi
def tutte(per: Periodo, rngs: dict):
    out = {}
    for nome, fn in (("H1", lambda: h1(per)), ("H2", lambda: h2(per, rngs["H2"])),
                     ("H3", lambda: h3(per)), ("H4", lambda: h4(per, rngs["H4"])),
                     ("H5", lambda: h5(per, rngs["H5"]))):
        out[nome] = fn()
        gc.collect()
        print(f"  {nome} fatto: n {out[nome][0]['n']}", flush=True)
    return out


def riproduci():
    per = Periodo("scoperta", SCOP, None, False)
    rngs = {"H2": rng_f5_prima_di(9), "H5": rng_f5_prima_di(389), "H4": rng_f4_prima_di(45)}
    res = tutte(per, rngs)
    # numeri registrati: file candidati + parquet di scoperta
    rif = {"H1": dict(n=325, t=2.06, anni="6/7"), "H2": dict(n=463, t=2.54, anni="8/9"),
           "H3": dict(n=1199, t=2.40, anni="7/9"), "H4": dict(n=434, t=2.67, anni="8/9"),
           "H5": dict(n=85, t=3.27, anni="7/7")}
    V1 = pd.read_parquet(RIS / "f1_varianti.parquet").set_index("id").loc[94]
    V2 = pd.read_parquet(RIS / "f2_faseb.parquet")
    V2 = V2[(V2.mercato == "SPXUSD") & (V2.L == "1g") & (V2.H == "1g") & (V2.sessione == "asia")
            & (V2.k == 1) & (V2.regime == "tutti")].iloc[0]
    V4 = pd.read_parquet(RIS / "f4_varianti.parquet").iloc[45]
    V5 = pd.read_parquet(RIS / "f5_varianti.parquet").set_index("id")
    reg = {"H1": dict(n=V2.n, netto=V2.netto, t=V2.t, anni=f"{V2.anni_pos}/{V2.anni}", p=V2.p_placebo),
           "H2": dict(n=V5.loc[9].n, netto=V5.loc[9].netto_px, t=V5.loc[9].t,
                      anni=f"{V5.loc[9].anni_pos}/{V5.loc[9].anni}",
                      p=f"{V5.loc[9].p_date:.4f}/{V5.loc[9].p_dir:.4f}"),
           "H3": dict(n=V1.n, netto=V1.netto, t=V1.t, anni=f"{V1.anni_pos:.0f}/{V1.anni:.0f}", p=V1.p),
           "H4": dict(n=V4.n, netto=V4.netR, t=V4.t, anni=f"{V4.anni_pos}/{V4.anni}", p=V4.p),
           "H5": dict(n=V5.loc[389].n, netto=V5.loc[389].netto_px, t=V5.loc[389].t,
                      anni=f"{V5.loc[389].anni_pos}/{V5.loc[389].anni}",
                      p=f"{V5.loc[389].p_date:.4f}/{V5.loc[389].p_dir:.4f}")}
    righe = []
    for h, (st, op) in res.items():
        netto = st["netR"] if h == "H4" else st["netto_px"]
        p = f"{st['p_date']:.4f}/{st['p_dir']:.4f}" if h in ("H2", "H5") else st["p"]
        r = reg[h]
        ok = (st["n"] == r["n"] and abs(netto / r["netto"] - 1) < 0.01 and abs(st["t"] / r["t"] - 1) < 0.01)
        righe.append({"ipotesi": h, "n": st["n"], "n_reg": int(r["n"]), "netto": netto, "netto_reg": r["netto"],
                      "t": st["t"], "t_reg": r["t"], "t_candidati": rif[h]["t"],
                      "anni": f"{st['anni_pos_scop']}/{st['anni_scop']}", "anni_reg": r["anni"],
                      "anni_candidati": rif[h]["anni"], "p": str(p), "p_reg": str(r["p"]), "coincide": ok})
        if h == "H1":
            u = st["controllo_regola"]
            assert u["n"] == st["n"] and abs(u["netto"] - st["netto_px"]) < 1e-9 and abs(u["t"] - st["t"]) < 1e-9
    R = pd.DataFrame(righe)
    R.to_parquet(RIS / "verifica_riproduzione.parquet")
    print(R.round(4).to_string(index=False))
    print("TUTTE COINCIDONO" if R.coincide.all() else "NON COINCIDONO")


def esegui_verifica(nome: str, taglio: pd.Timestamp, dopo: Path | None, salva: bool):
    per = costruisci(nome, SCOP, dopo, taglio)
    rngs = {k: np.random.default_rng(12345) for k in ("H2", "H4", "H5")}
    res = tutte(per, rngs)
    righe, anni, ops = [], [], []
    for h, (st, op) in res.items():
        tcol = "netR" if h == "H4" else ("netto_pct" if h in ("H2", "H5") else "netto")
        netto_ref = st["netR"] if h == "H4" else st["netto_px"]
        frac = st["anni_pos_ver"] / st["anni_ver"] if st["anni_ver"] else np.nan
        passa = (netto_ref > 0) and (st["t"] >= SOGLIA_T) and (frac >= 2 / 3) and (st["p"] < 0.01)
        r = {k: v for k, v in st.items() if k != "controllo_regola"}
        r.update(ipotesi=h, colonna_t=tcol, frac_anni=frac, passa=passa,
                 dal=str(op.ts.min()), al=str(op.ts.max()))
        righe.append(r)
        anni.append(per_anno(op, h, "netR" if h == "H4" else None))
        ops.append(op)
    S = pd.DataFrame(righe)
    A = pd.concat(anni, ignore_index=True)
    O = pd.concat(ops, ignore_index=True)
    cols = ["ipotesi", "n", "netto_px", "netto_pct", "netto_costi", "netR", "t", "anni_pos_ver",
            "anni_ver", "p", "p_date", "p_dir", "passa", "dal", "al"]
    print(S[[c for c in cols if c in S]].round(4).to_string(index=False))
    print(A.round(3).to_string(index=False))
    if salva:
        S.to_parquet(RIS / "verifica_sintesi.parquet")
        A.to_parquet(RIS / "verifica_anni.parquet")
        O.to_parquet(RIS / "verifica_operazioni.parquet")


def controllo():
    """Strategia ufficiale, gestione B, XAU_ANNI=2018-2026; correlazione giornaliera con H2-H4."""
    os.environ["XAU_ANNI"] = "2018-2026"
    import verifica_bot as vb
    assert vb.SPREAD == SPREAD
    m1 = vb.load_m1(os.path.join(vb.ROOT, "data", "XAUUSD_M1"))
    ops = vb.filtra(vb.genera(m1, vb.T, mediana_atr=vb.MEDIANA_ATR))
    perc = vb.Percorsi(m1)
    del m1
    gc.collect()
    gest = vb.BOT[2]
    assert gest[0].startswith("B")
    costo = lambda anno: vb.SPREAD.get(anno, 0.40)  # noqa: E731  (come verifica_bot.main)
    R, date, anni = vb.valuta(ops, perc, gest, costo)
    mis = vb.misure(R, date, anni)
    U = pd.DataFrame({"ts": pd.DatetimeIndex(date), "anno": anni, "R": R})
    U["giorno"] = U.ts.dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
    U.to_parquet(RIS / "verifica_ufficiale_B_operazioni.parquet")
    pa = U.groupby("anno").R.agg(["size", "sum", "mean"])
    print(pd.Series(mis).to_string())
    print(pa.round(2).to_string())
    O = pd.read_parquet(RIS / "verifica_operazioni.parquet")
    # fine dei dati dell'oro (ultima operazione di H2-H4); la strategia ha 0 dopo la sua ultima
    fine = O[O.ipotesi.isin(["H2", "H3", "H4"])].giorno.max()
    giorni = pd.bdate_range("2018-01-01", fine)
    G = pd.DataFrame(index=giorni)
    G["ufficiale_R"] = U.groupby("giorno").R.sum().reindex(giorni).fillna(0.0)
    righe = []
    for h in ("H1", "H2", "H3", "H4", "H5"):
        x = O[O.ipotesi == h]
        G[f"{h}_netto"] = x.groupby("giorno").netto.sum().reindex(giorni).fillna(0.0)
        if h == "H4":
            G["H4_netR"] = x.groupby("giorno").netR.sum().reindex(giorni).fillna(0.0)
    for c in G.columns[1:]:
        both = (G[c] != 0) & (G.ufficiale_R != 0)
        righe.append({"serie": c, "corr_giornaliera": G[c].corr(G.ufficiale_R),
                      "giorni_attivi": int((G[c] != 0).sum()), "giorni_entrambi": int(both.sum()),
                      "corr_giorni_entrambi": G.loc[both, c].corr(G.loc[both, "ufficiale_R"])})
    C = pd.DataFrame(righe)
    G.to_parquet(RIS / "verifica_giornaliero.parquet")
    C.to_parquet(RIS / "verifica_correlazioni.parquet")
    pd.DataFrame([{**mis, "fine_giorni": str(fine)}]).astype(str).to_parquet(RIS / "verifica_ufficiale_B.parquet")
    print(C.round(3).to_string(index=False))
    print("giorni:", len(giorni), "fino a", fine.date())


if __name__ == "__main__":
    passo = sys.argv[1] if len(sys.argv) > 1 else ""
    if passo == "riproduci":
        riproduci()
    elif passo == "prova":
        esegui_verifica("prova", pd.Timestamp("2015-01-01", tz="UTC"), None, salva=False)
    elif passo == "verifica":
        esegui_verifica("verifica", pd.Timestamp("2018-01-01", tz="UTC"), VER, salva=True)
    elif passo == "controllo":
        controllo()
    else:
        print(__doc__)
