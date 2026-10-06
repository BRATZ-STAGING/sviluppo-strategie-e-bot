#!/usr/bin/env python3
"""Famiglia C — posizionamento COT (grandi contro piccoli) sull'oro, SOLO scoperta.

Protocollo: docs/macro-oro-registrazione.md. Rapporto: docs/studies/macro/c-cot.md.
Dati: D:\\ricerca_macro\\scoperta\\MACRO_D1.parquet e COT_SETTIMANALE.parquet.
Dettaglio: D:\\ricerca_macro\\risultati\\c_*.parquet.

Regole fisse:
- solo giornate d'oro valide; ATR20 = media del true range delle 20 giornate
  valide fino alla giornata del segnale compresa;
- misure COT: netto % OI = (long - short) / OI x 100 per managed money (mm),
  produttori (prod), non segnalati (pic); percentile del valore sulle 156
  settimane PRECEDENTI (min 52), variazione settimanale e suo percentile;
- data utilizzabile del COT (prudente) = max(pubblicato del file, martedi' + 3
  giorni lavorativi del calendario federale USA, venerdi' della settimana del
  rapporto); rapporti 01/10-12/11/2013 (chiusura del governo, pubblicati in
  ritardo) utilizzabili solo dal 22/11/2013;
- giornata di decisione s = prima giornata d'oro valida con data >= data
  utilizzabile; segnale alla chiusura di s, entrata all'apertura di s+1;
  se due rapporti cadono sulla stessa s vale l'ultimo;
- decisioni 2009-2017 (COT 2006-2008 solo per i percentili);
- tenuta 5/10/20 giornate (uscita alla chiusura di s+H; scartata se oltre i
  dati) oppure fino al primo rapporto col segnale opposto (uscita alla
  chiusura della sua giornata di decisione; a fine dati chiusura all'ultima);
- una posizione per regola; segnali ignorati mentre e' aperta; nuova entrata
  possibile dalla decisione presa alla chiusura della giornata d'uscita;
- 1R = 2 x ATR20(s); stop (se c'e') a 2 x ATR20 dall'entrata, tocco su
  minimo/massimo D1, uscita allo stop o all'apertura se apre gia' oltre;
- costi 0,46 $ round trip (anche x1,5); swap long -0,715, short +0,325
  $/oncia/notte x P_entrata/4156,98; notti = giorni lun-ven dall'entrata
  all'uscita compresi, il mercoledi' vale 3.
"""
from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

SC = r"D:\ricerca_macro\scoperta"
RIS = r"D:\ricerca_macro\risultati"
COSTO = 0.46
SWL, SWS, PREF = -0.715, 0.325, 4156.98
SEED, NPL = 12345, 1000
FIN = 156
MIN_STORIA = 52
ANNI = list(range(2009, 2018))
GRUPPI = {"mm": ("mm_long", "mm_short"), "prod": ("prod_long", "prod_short"),
          "pic": ("piccoli_long", "piccoli_short")}
pd.set_option("display.width", 200)


# ---------------------------------------------------------------- dati
def oro():
    m = pd.read_parquet(os.path.join(SC, "MACRO_D1.parquet"))
    m = m[m["valida"]][["open", "high", "low", "close"]].sort_index()
    pc = m["close"].shift(1)
    tr = pd.concat([m["high"] - m["low"], (m["high"] - pc).abs(), (m["low"] - pc).abs()], axis=1).max(axis=1)
    tr.iloc[0] = m["high"].iloc[0] - m["low"].iloc[0]
    m["atr20"] = tr.rolling(20).mean()
    return m


def percentile_storico(v: np.ndarray) -> np.ndarray:
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        if np.isnan(v[i]):
            continue
        prev = v[max(0, i - FIN):i]
        prev = prev[~np.isnan(prev)]
        if len(prev) < MIN_STORIA:
            continue
        out[i] = ((prev < v[i]).sum() + 0.5 * (prev == v[i]).sum()) / len(prev)
    return out


def cot():
    c = pd.read_parquet(os.path.join(SC, "COT_SETTIMANALE.parquet")).sort_index()
    d = pd.DataFrame(index=c.index)
    salto = c.index.to_series().diff().dt.days
    for g, (lo, sh) in GRUPPI.items():
        n = (c[lo] - c[sh]) / c["oi"] * 100
        d[f"net_{g}"] = n
        d[f"d_{g}"] = n.diff().where(salto <= 8)
        d[f"pct_{g}"] = percentile_storico(n.values)
        d[f"pctd_{g}"] = percentile_storico(d[f"d_{g}"].values)
    cday = CustomBusinessDay(calendar=USFederalHolidayCalendar())
    pub_fed = c.index + 3 * cday
    venerdi = c.index + pd.to_timedelta((4 - c.index.dayofweek) % 7, unit="D")
    pub = np.maximum(np.maximum(c["pubblicato"].values.astype("datetime64[ns]"),
                                np.asarray(pub_fed, dtype="datetime64[ns]")),
                     np.asarray(venerdi, dtype="datetime64[ns]"))
    pub = pd.DatetimeIndex(pub)
    chiuso = (c.index >= "2013-10-01") & (c.index <= "2013-11-12")
    pub = pub.where(~chiuso, pd.Timestamp("2013-11-22"))
    d["utilizzabile"] = pub
    d["pubblicato_file"] = c["pubblicato"].values
    return d


def segnali(d: pd.DataFrame) -> dict[str, np.ndarray]:
    """Direzione grezza (+1/-1/0) per settimana: dichiarate PRIMA del calcolo."""
    def estremi(p, q, segno):
        s = np.where(p <= q, 1, np.where(p >= 1 - q, -1, 0)) * segno
        return np.where(np.isnan(p), 0, s)

    def segno_var(x, segno):
        return np.where(np.isnan(x), 0, np.sign(x)) * segno

    S = {}
    for q in (0.1, 0.2):
        S[f"MM_CONTRA_q{q}"] = estremi(d["pct_mm"].values, q, +1)      # (1)
        S[f"MM_SEGUI_q{q}"] = estremi(d["pct_mm"].values, q, -1)       # (2)
        S[f"PIC_CONTRA_q{q}"] = estremi(d["pct_pic"].values, q, +1)    # (3)
        S[f"PROD_FORTI_q{q}"] = estremi(d["pct_prod"].values, q, -1)   # (4) meno coperti -> long
    S["MM_VAR_SEGUI"] = segno_var(d["d_mm"].values, +1)                # (2)
    S["MM_VAR_ESTR_q0.2"] = estremi(d["pctd_mm"].values, 0.2, -1)      # (2)
    S["PIC_VAR_CONTRA"] = segno_var(d["d_pic"].values, -1)             # (3)
    S["PROD_VAR_SEGUI"] = segno_var(d["d_prod"].values, +1)            # (4)
    return {k: v.astype(int) for k, v in S.items()}


# ---------------------------------------------------------------- motore
class Motore:
    def __init__(self, m: pd.DataFrame, S_idx: np.ndarray):
        self.O, self.H, self.L, self.C = (m[c].values for c in ("open", "high", "low", "close"))
        self.ATR = m["atr20"].values
        self.date = m.index.values.astype("datetime64[D]")
        self.N = len(m)
        self.S = S_idx
        self.cache = {}

    def tab(self, Hd: int, d: int, stop: bool):
        """Esito di un'operazione per OGNI settimana (decisione S[k]), tenuta nominale Hd."""
        key = (Hd, d, stop)
        if key in self.cache:
            return self.cache[key]
        S, N = self.S, self.N
        ok = S + Hd < N
        Sx = np.where(ok, S, 0)
        e = Sx + 1
        entry = self.O[e]
        R = 2 * self.ATR[Sx]
        xn = Sx + Hd
        exit_px = self.C[xn].copy()
        exit_i = xn.copy()
        stopped = np.zeros(len(S), bool)
        if stop:
            idx = np.clip(e[:, None] + np.arange(Hd)[None, :], 0, N - 1)
            lvl = entry - d * R
            hit = (self.L[idx] <= lvl[:, None]) if d > 0 else (self.H[idx] >= lvl[:, None])
            stopped = hit.any(axis=1)
            j = idx[np.arange(len(S)), hit.argmax(axis=1)]
            op = self.O[j]
            px = np.minimum(op, lvl) if d > 0 else np.maximum(op, lvl)
            exit_px = np.where(stopped, px, exit_px)
            exit_i = np.where(stopped, j, exit_i)
        de, dx = self.date[e], self.date[exit_i] + np.timedelta64(1, "D")
        notti = np.busday_count(de, dx) + 2 * np.busday_count(de, dx, weekmask="0010000")
        swap = notti * (SWL if d > 0 else SWS) * entry / PREF
        lordo = d * (exit_px - entry)
        out = dict(ok=ok, lordo=lordo, swap=swap, R=R, exit_i=exit_i, stopped=stopped,
                   net1=(lordo + swap - COSTO) / R, net15=(lordo + swap - 1.5 * COSTO) / R,
                   net_usd=lordo + swap - COSTO, entry=entry)
        self.cache[key] = out
        return out


def simula(mo: Motore, raw: np.ndarray, lato: str, tenuta, stop: bool):
    """Ritorna lista di operazioni (k, d, Hd, exit_i, fine_dati)."""
    S, K = mo.S, len(mo.S)
    ops = []
    libero = -1
    for k in range(K):
        s = S[k]
        if s < libero:
            continue
        d = raw[k]
        if d == 0 or (lato == "L" and d < 0) or (lato == "S" and d > 0):
            continue
        if s + 1 >= mo.N:
            continue
        fine = False
        if tenuta == "OPP":
            opp = np.nonzero(raw[k + 1:] == -d)[0]
            xn = S[k + 1 + opp[0]] if len(opp) else mo.N - 1
            fine = not len(opp)
            Hd = xn - s
            if Hd < 1:
                continue
        else:
            Hd = tenuta
            if s + Hd >= mo.N:
                continue
        t = mo.tab(Hd, d, stop)
        ops.append((k, d, Hd, int(t["exit_i"][k]), fine))
        libero = int(t["exit_i"][k])
    return ops


# ---------------------------------------------------------------- misure
def t_stat(x):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return np.nan
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x))


def misure(mo, ops, date_mesi, rng, settimane_ok):
    if not ops:
        return None, None
    k = np.array([o[0] for o in ops]); dd = np.array([o[1] for o in ops])
    Hd = np.array([o[2] for o in ops]); xi = np.array([o[3] for o in ops])
    rows = []
    for kk, d, h, x, fine in ops:
        t = mo.tab(h, d, STOP_CUR)
        to = mo.tab(h, -d, STOP_CUR)
        rows.append((kk, d, h, x, fine, t["net1"][kk], t["net15"][kk], t["net_usd"][kk], t["swap"][kk] / t["R"][kk],
                     t["lordo"][kk] / t["R"][kk], t["stopped"][kk], to["net1"][kk]))
    op = pd.DataFrame(rows, columns=["k", "dir", "Hd", "exit_i", "fine_dati", "net1", "net15", "net_usd",
                                     "swapR", "lordoR", "stop_preso", "net1_opposto"])
    op["entrata"] = mo.date[mo.S[op.k] + 1]
    op["uscita"] = mo.date[op.exit_i]
    mese = pd.to_datetime(op["uscita"]).dt.to_period("M")
    mens = op.groupby(mese)["net1"].sum().reindex(date_mesi, fill_value=0.0)
    anno = pd.to_datetime(op["uscita"]).dt.year
    ann = op.groupby(anno)["net1"].sum().reindex(ANNI, fill_value=0.0)
    cum = op["net1"].cumsum().values
    dd_ = np.max(np.maximum.accumulate(np.concatenate([[0], cum]))[1:] - cum) if len(cum) else 0
    reale = op["net1"].sum()
    # placebo direzione
    segno = rng.integers(0, 2, size=(NPL, len(op))).astype(bool)
    pl_dir = np.where(segno, op["net1"].values, op["net1_opposto"].values).sum(axis=1)
    # placebo date: stessa direzione, stessa tenuta nominale, settimana casuale
    pl_date = np.zeros(NPL)
    for h, d in set(zip(op.Hd, op.dir)):
        t = mo.tab(int(h), int(d), STOP_CUR)
        cand = np.nonzero(t["ok"] & settimane_ok)[0]
        nn = int(((op.Hd == h) & (op.dir == d)).sum())
        if len(cand) == 0:
            continue
        pl_date += t["net1"][cand[rng.integers(0, len(cand), size=(NPL, nn))]].sum(axis=1)
    mis = dict(n=len(op), op_mese=len(op) / len(date_mesi), long=(op.dir > 0).mean(),
               netR=op.net1.mean(), netR15=op.net15.mean(), totR=reale, totR15=op.net15.sum(),
               net_usd=op.net_usd.mean(), tot_usd=op.net_usd.sum(), lordoR=op.lordoR.mean(),
               swapR=op.swapR.mean(), t_mese=t_stat(mens.values), t_op=t_stat(op.net1.values),
               anni_pos=int((ann > 0).sum()), dd=dd_, stop_presi=op.stop_preso.mean(),
               tenuta_media=op.Hd.mean(), fine_dati=int(op.fine_dati.sum()),
               p_dir=(1 + (pl_dir >= reale).sum()) / (NPL + 1),
               p_date=(1 + (pl_date >= reale).sum()) / (NPL + 1),
               placebo_date_medio=pl_date.mean() / len(op),
               **{f"a{a}": ann[a] for a in ANNI})
    return mis, op


STOP_CUR = False


def main():
    global STOP_CUR
    t0 = time.time()
    os.makedirs(RIS, exist_ok=True)
    m = oro()
    d = cot()
    gdate = m.index.values
    s_idx = np.searchsorted(gdate, d["utilizzabile"].values.astype(gdate.dtype), side="left")
    d["s"] = s_idx
    d = d[d.s < len(m)]
    d = d[~d.s.duplicated(keep="last")]
    d["decisione"] = m.index[d.s.values]
    sett = d[(d.decisione >= "2009-01-01") & (d.decisione <= "2017-12-31")].copy()
    sett = sett[~np.isnan(m["atr20"].values[sett.s.values])]
    mo = Motore(m, sett.s.values.astype(int))
    SG = segnali(sett)
    settimane_ok = np.ones(len(sett), bool)
    primo = pd.Timestamp(mo.date[mo.S[0] + 1]).to_period("M")
    date_mesi = pd.period_range(primo, "2017-12", freq="M")
    print(f"settimane di decisione 2009-2017: {len(sett)}; prima {sett.decisione.iloc[0].date()}; "
          f"ritardo medio data utilizzabile vs file {((sett.utilizzabile - pd.to_datetime(sett.pubblicato_file)).dt.days).mean():.3f} gg")
    for nome, v in SG.items():
        sett[f"sg_{nome}"] = v
    sett.to_parquet(os.path.join(RIS, "c_settimane.parquet"))

    # ------------------------------------------------ griglia
    righe, opers = [], []
    rng = np.random.default_rng(SEED)
    for nome, raw in SG.items():
        for lato in ("LS", "L", "S"):
            for ten in (5, 10, 20, "OPP"):
                for stop in (False, True):
                    STOP_CUR = stop
                    ops = simula(mo, raw, lato, ten, stop)
                    mis, op = misure(mo, ops, date_mesi, rng, settimane_ok)
                    vid = f"{nome}|{lato}|{ten}|{'stop' if stop else 'tempo'}"
                    base = dict(variante=vid, segnale=nome, lato=lato, tenuta=str(ten), stop=stop)
                    if mis is None:
                        righe.append(base | dict(n=0))
                        continue
                    righe.append(base | mis)
                    op["variante"] = vid
                    opers.append(op)
    # riferimento: sempre long
    rif = []
    for ten in (5, 10, 20):
        for stop in (False, True):
            STOP_CUR = stop
            ops = simula(mo, np.ones(len(sett), int), "L", ten, stop)
            mis, op = misure(mo, ops, date_mesi, rng, settimane_ok)
            rif.append(dict(variante=f"SEMPRE_LONG|L|{ten}|{'stop' if stop else 'tempo'}") | mis)
    V = pd.DataFrame(righe)
    RF = pd.DataFrame(rif)
    V["passa"] = ((V.totR > 0) & (V.totR15 > 0) & (V.t_mese >= 3) & (V.anni_pos >= 7)
                  & (V.p_dir < 0.01) & (V.p_date < 0.01))
    V.to_parquet(os.path.join(RIS, "c_varianti.parquet"))
    RF.to_parquet(os.path.join(RIS, "c_sempre_long.parquet"))
    pd.concat(opers, ignore_index=True).drop(columns=["k", "exit_i"]).to_parquet(
        os.path.join(RIS, "c_operazioni.parquet"))

    # ------------------------------------------------ controllo motore (ciclo esplicito)
    rr = np.random.default_rng(7)
    err = 0.0
    for _ in range(400):
        k = rr.integers(0, len(mo.S)); h = int(rr.choice([1, 5, 10, 20, 37])); dr = int(rr.choice([-1, 1]))
        st = bool(rr.integers(0, 2))
        s = mo.S[k]
        if s + h >= mo.N:
            continue
        e = s + 1; ent = mo.O[e]; R = 2 * mo.ATR[s]; lvl = ent - dr * R; px = mo.C[s + h]; xi = s + h
        if st:
            for j in range(e, s + h + 1):
                if (dr > 0 and mo.L[j] <= lvl) or (dr < 0 and mo.H[j] >= lvl):
                    px = min(mo.O[j], lvl) if dr > 0 else max(mo.O[j], lvl); xi = j; break
        nt = 0
        for g in pd.date_range(pd.Timestamp(mo.date[e]), pd.Timestamp(mo.date[xi])):
            if g.dayofweek < 5:
                nt += 3 if g.dayofweek == 2 else 1
        net = (dr * (px - ent) + nt * (SWL if dr > 0 else SWS) * ent / PREF - COSTO) / R
        err = max(err, abs(net - mo.tab(h, dr, st)["net1"][k]))
    print(f"controllo motore: differenza massima {err:.2e}; tempo {time.time() - t0:.0f} s")

    # ------------------------------------------------ sintesi
    print(f"varianti: {len(V)}; con operazioni {int((V.n > 0).sum())}; netto>0 {(V.totR > 0).mean():.3f}; "
          f"t>=3 {(V.t_mese >= 3).sum()}; t<=-3 {(V.t_mese <= -3).sum()}; passano {int(V.passa.sum())}")
    V["ipotesi"] = V.segnale.str.split("_").str[0] + "_" + V.segnale.str.split("_").str[1]
    g = V[V.n > 0].groupby("segnale").agg(netpos=("totR", lambda x: (x > 0).mean()), t_med=("t_mese", "median"),
                                          t_max=("t_mese", "max"), t_min=("t_mese", "min"), passa=("passa", "sum"))
    print(g.round(2).to_string())
    col = ["variante", "n", "op_mese", "netR", "netR15", "totR", "t_mese", "t_op", "anni_pos", "dd", "p_dir", "p_date"]
    print(V.sort_values("t_mese", ascending=False)[col].head(12).round(3).to_string(index=False))
    print(RF[col[:-2] + ["p_dir"]].round(3).to_string(index=False))
    print(V[V.n > 0].pivot_table(index="segnale", columns="lato", values="t_mese", aggfunc="median").round(2).to_string())
    descrittive(m, d, sett, mo)


def descrittive(m, d, sett, mo):
    """Che cosa fanno i piccoli rispetto ai fondi (solo descrittivo, nessuna regola)."""
    out = {}
    dd = d[[f"d_{g}" for g in GRUPPI]].dropna()
    cr = dd.corr()
    out["corr_var_mm_pic"] = cr.loc["d_mm", "d_pic"]
    out["corr_var_mm_prod"] = cr.loc["d_mm", "d_prod"]
    out["corr_var_pic_prod"] = cr.loc["d_pic", "d_prod"]
    lv = d[[f"net_{g}" for g in GRUPPI]]
    out["corr_liv_mm_pic"] = lv.corr().loc["net_mm", "net_pic"]
    out["corr_liv_mm_prod"] = lv.corr().loc["net_mm", "net_prod"]
    for g in GRUPPI:
        out[f"net_{g}_medio"] = lv[f"net_{g}"].mean()
        out[f"net_{g}_min"] = lv[f"net_{g}"].min()
        out[f"net_{g}_max"] = lv[f"net_{g}"].max()
    # oro nella stessa settimana del rapporto (martedi'->martedi', contemporaneo, NON negoziabile)
    c = m["close"]
    pos = c.index.searchsorted(d.index, side="right") - 1
    r = pd.Series(np.log(c.values[pos]), index=d.index).diff().where(d.index >= "2009-01-08")
    z = pd.concat([r.rename("oro"), d[[f"d_{g}" for g in GRUPPI]]], axis=1).dropna()
    for g in GRUPPI:
        out[f"corr_oro_stessa_sett_{g}"] = z["oro"].corr(z[f"d_{g}"])
    # oro DOPO (entrata s+1, 20 giornate, lordo in R) per quintile di percentile
    t = mo.tab(20, +1, False)
    fw = pd.Series(np.where(t["ok"], t["lordo"] / t["R"], np.nan), index=sett.index)
    fw5 = mo.tab(5, +1, False)
    fw5 = pd.Series(np.where(fw5["ok"], fw5["lordo"] / fw5["R"], np.nan), index=sett.index)
    q = {}
    for g in GRUPPI:
        b = pd.cut(sett[f"pct_{g}"], [0, .2, .4, .6, .8, 1.0001], labels=[1, 2, 3, 4, 5], include_lowest=True)
        q[f"{g}_4sett"] = fw.groupby(b, observed=False).mean()
        q[f"{g}_1sett"] = fw5.groupby(b, observed=False).mean()
    Q = pd.DataFrame(q)
    Q.index.name = "quintile_percentile"
    pd.Series(out).to_frame("valore").to_parquet(os.path.join(RIS, "c_descrittive.parquet"))
    Q.to_parquet(os.path.join(RIS, "c_quintili.parquet"))
    print(pd.Series(out).round(3).to_string())
    print("lordo R di un long dopo la settimana, per quintile di percentile (1 = piu' corti del solito)")
    print(Q.round(3).to_string())


if __name__ == "__main__":
    main()
