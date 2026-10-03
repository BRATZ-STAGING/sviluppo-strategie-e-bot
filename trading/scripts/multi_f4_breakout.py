"""Famiglia 4 multi-giorno — Breakout con stop larghi (scoperta 2010-2017).

Protocollo: docs/multigiorno-paniere-registrazione.md.
Rapporto:   docs/studies/multi/f4-breakout.md

Dati: SOLO D:\\ricerca_multi\\scoperta\\PANIERE_D1.parquet (giornata 22->22 UTC)
e D:\\ricerca_multi\\costi.csv; le M5 di D:\\ricerca_zero|ricerca_fx\\scoperta\\
servono solo a risolvere la giornata di entrata degli ordini stop (quale livello
viene toccato per primo, stop toccato dopo l'entrata nella stessa giornata).

Griglia (288 regole, dichiarata nel rapporto prima del calcolo):
  livello  N = 5, 10, 20 giorni validi precedenti, W = settimana precedente
  entrata  R = ordine stop al livello, C = chiusura oltre il livello
  stop     m = 1, 2, 3 x ATR20
  uscita   T2, T3 = trailing k x ATR20 dal massimo/minimo dall'entrata;
           D5, D10, D20 = chiusura del 5/10/20esimo giorno dopo l'entrata;
           OPP = ordine stop alla rottura opposta di N/2 giorni (5->3, 10->5,
           20->10, W->3)
  filtro   0 = nessuno, 1 = ATR20/ATR100 < 1

Uso:
  python multi_f4_breakout.py simula    # un mercato alla volta -> operazioni
  python multi_f4_breakout.py aggrega   # misure per regola e ambito, placebo
  python multi_f4_breakout.py           # tutto
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)

BASE = Path(r"D:\ricerca_multi")
PANIERE = BASE / "scoperta" / "PANIERE_D1.parquet"
RIS = BASE / "risultati"
M5DIR = {"XAUUSD": r"D:\ricerca_zero", "XAGUSD": r"D:\ricerca_zero",
         "SPXUSD": r"D:\ricerca_zero", "NSXUSD": r"D:\ricerca_zero",
         "GRXEUR": r"D:\ricerca_zero"}
MERCATI = ["XAUUSD", "XAGUSD", "SPXUSD", "NSXUSD", "GRXEUR", "EURUSD", "USDJPY",
           "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "EURJPY"]
GRUPPI = {"indici": ["SPXUSD", "NSXUSD", "GRXEUR"],
          "metalli": ["XAUUSD", "XAGUSD"],
          "cambi": ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "EURJPY"]}
SPREAD_ORO = {2020: 0.35, 2021: 0.349, 2022: 0.395, 2023: 0.334,
              2024: 0.384, 2025: 0.632, 2026: 0.631}   # da verifica_bot.py
LIVELLI = [5, 10, 20, "W"]
N2 = {5: 3, 10: 5, 20: 10, "W": 3}
MODI = ["R", "C"]
STOPM = [1, 2, 3]
USCITE = ["T2", "T3", "D5", "D10", "D20", "OPP"]
FILTRI = [0, 1]
INIZIO = pd.Timestamp("2010-01-01")
FINE = pd.Timestamp("2017-12-31")
ANNI = list(range(2010, 2018))
MESI = pd.period_range("2010-01", "2017-12", freq="M")
NPLACEBO = 1000
SEED = 20261004
SWAP_ANNUO = 0.03            # del nominale, long e short, per notte /360
ORO_LONG, ORO_SHORT, ORO_RIF = -0.715, 0.325, 4156.98


def regole():
    return [(lv, mo, m, ex, f) for lv in LIVELLI for mo in MODI for m in STOPM
            for ex in USCITE for f in FILTRI]


def nome(r):
    lv, mo, m, ex, f = r
    return f"{'N'+str(lv) if lv != 'W' else 'W'} {mo} S{m} {ex} F{f}"


def costo_rt(mercato, anno, costi):
    if mercato == "XAUUSD" and anno >= 2020:
        return SPREAD_ORO.get(anno, 0.40) + 0.06
    return costi[mercato]


# --------------------------------------------------------------------------
# preparazione di un mercato (solo D1)
# --------------------------------------------------------------------------

def prepara(d):
    """d: righe D1 del mercato ordinate (anche non valide). Serie causali."""
    d = d.reset_index(drop=True)
    v = d[d["valida"]].copy()
    pc = v["close"].shift(1)
    tr = np.maximum(v["high"], pc) - np.minimum(v["low"], pc)
    tr.iloc[0] = v["high"].iloc[0] - v["low"].iloc[0]
    v["atr20"] = tr.rolling(20).mean()
    v["atr100"] = tr.rolling(100).mean()
    v["atr20_pre"] = v["atr20"].shift(1)
    v["atr100_pre"] = v["atr100"].shift(1)
    v["pc"] = pc
    for n in (5, 10, 20):
        v[f"H{n}"] = v["high"].rolling(n).max().shift(1)
        v[f"L{n}"] = v["low"].rolling(n).min().shift(1)
    for n in (3, 5, 10):
        v[f"lo{n}"] = v["low"].rolling(n).min()       # inclusa la giornata
        v[f"hi{n}"] = v["high"].rolling(n).max()
    sett = v["giorno"] - pd.to_timedelta(v["giorno"].dt.dayofweek, unit="D")
    ws = v.groupby(sett).agg(wh=("high", "max"), wl=("low", "min"))
    ws_prev = ws.shift(1)
    v["HW"] = ws_prev["wh"].reindex(sett).to_numpy()
    v["LW"] = ws_prev["wl"].reindex(sett).to_numpy()
    cols = [c for c in v.columns if c not in d.columns]
    d = d.join(v[cols])
    # valori "alla chiusura" validi anche per le righe non valide (ultimo noto)
    for c in ["atr20"] + [f"lo{n}" for n in (3, 5, 10)] + [f"hi{n}" for n in (3, 5, 10)]:
        d[c + "_ff"] = d[c].ffill()
    return d


def calendario_swap(d):
    giorni = pd.bdate_range(d["giorno"].iloc[0], d["giorno"].iloc[-1])
    chiu = d.set_index("giorno")["close"].reindex(giorni).ffill().to_numpy(float)
    molt = np.where(giorni.dayofweek == 2, 3.0, 1.0)
    cum = np.concatenate([[0.0], np.cumsum(molt * chiu)])
    return giorni, cum


# --------------------------------------------------------------------------
# M5 della giornata di entrata (ordini stop)
# --------------------------------------------------------------------------

def carica_m5(mercato):
    base = M5DIR.get(mercato, r"D:\ricerca_fx")
    m = pd.read_parquet(Path(base) / "scoperta" / f"{mercato}_M5.parquet",
                        columns=["open", "high", "low", "close"])
    ts = m.index.tz_convert("UTC").tz_localize(None).values
    lab = (ts + np.timedelta64(2, "h")).astype("datetime64[D]")
    return (lab, m["open"].to_numpy(float), m["high"].to_numpy(float),
            m["low"].to_numpy(float))


def giorno_entrata(bo, bh, bl, i0, entry, dist, y):
    """Esito nella giornata di entrata per la direzione y.

    Ritorna (uscito, prezzo_uscita, estremo favorevole dopo l'entrata).
    La M5 di entrata conta per intero (prudente: il suo estremo avverso vale).
    """
    if y > 0:
        stop = entry - dist
        hit = np.nonzero(bl[i0:] <= stop)[0]
        if hit.size:
            j = hit[0] + i0
            return True, (stop if j == i0 else min(stop, bo[j])), np.nan
        return False, np.nan, bh[i0:].max()
    stop = entry + dist
    hit = np.nonzero(bh[i0:] >= stop)[0]
    if hit.size:
        j = hit[0] + i0
        return True, (stop if j == i0 else max(stop, bo[j])), np.nan
    return False, np.nan, bl[i0:].min()


def avanti(O, H, L, C, A, CH, s, stop, hh, D, k):
    """Gestione lunga (prezzi eventualmente negati) dal giorno s+1.

    stop/hh gia' aggiornati alla chiusura di s. CH: canale opposto (o None).
    Apertura oltre lo stop = uscita all'apertura; stop prima del tempo.
    """
    T = len(O)
    for t in range(s + 1, T):
        if O[t] <= stop:
            return t, O[t]
        if L[t] <= stop:
            return t, stop
        if D and t == s + D:
            return t, C[t]
        if k:
            if H[t] > hh:
                hh = H[t]
            v = hh - k * A[t]
            if v > stop:
                stop = v
        elif CH is not None:
            v = CH[t]
            if v > stop:
                stop = v
    return T - 1, C[T - 1]


def simula_mercato(mercato, pan, costi):
    t0 = time.time()
    d = prepara(pan[pan["mercato"] == mercato].sort_values("giorno"))
    giorni_sw, cum_sw = calendario_swap(d)
    T = len(d)
    gio = d["giorno"].to_numpy("datetime64[D]")
    o, h, l, c = (d[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    A = d["atr20_ff"].to_numpy(float)
    # versioni lunghe (y=+1) e negate (y=-1) come liste Python (ciclo veloce)
    P = {+1: [o.tolist(), h.tolist(), l.tolist(), c.tolist()],
         -1: [(-o).tolist(), (-l).tolist(), (-h).tolist(), (-c).tolist()]}
    CHAN = {}
    for n in (3, 5, 10):
        CHAN[(+1, n)] = d[f"lo{n}_ff"].to_numpy(float).tolist()
        CHAN[(-1, n)] = (-d[f"hi{n}_ff"].to_numpy(float)).tolist()
    Al = A.tolist()
    valida = d["valida"].to_numpy(bool)
    dentro = (d["giorno"] >= INIZIO).to_numpy() & valida

    lab, bo, bh, bl = carica_m5(mercato)
    controllo = {"R_eventi": 0, "R_ambigui": 0, "R_incoerenti": 0}

    # ---- eventi: (lv, modo) -> lista di dict
    eventi = {}
    for lv in LIVELLI:
        Hc, Lc = ("HW", "LW") if lv == "W" else (f"H{lv}", f"L{lv}")
        Hp, Lp = d[Hc].to_numpy(float), d[Lc].to_numpy(float)
        pcv = d["pc"].to_numpy(float)
        # modo R: ordini stop sulla giornata s (livelli e ATR noti alla chiusura prima)
        apre, a100p = d["atr20_pre"].to_numpy(float), d["atr100_pre"].to_numpy(float)
        ok = (dentro & np.isfinite(Hp) & np.isfinite(Lp) & np.isfinite(apre)
              & np.isfinite(a100p) & (pcv < Hp) & (pcv > Lp))
        evR = []
        for s in np.nonzero(ok & ((h >= Hp) | (l <= Lp)))[0]:
            controllo["R_eventi"] += 1
            i, j = np.searchsorted(lab, gio[s], "left"), np.searchsorted(lab, gio[s], "right")
            sh, sl, so = bh[i:j], bl[i:j], bo[i:j]
            tl = np.nonzero(sh >= Hp[s])[0]
            ts_ = np.nonzero(sl <= Lp[s])[0]
            iL = tl[0] if tl.size else 10**9
            iS = ts_[0] if ts_.size else 10**9
            if iL == 10**9 and iS == 10**9:
                controllo["R_incoerenti"] += 1
                continue
            if iL == iS:
                controllo["R_ambigui"] += 1
                continue
            if iL < iS:
                x, i0, entry = 1, iL, max(Hp[s], so[iL])
            else:
                x, i0, entry = -1, iS, min(Lp[s], so[iS])
            e = {"s": int(s), "x": x, "entry": float(entry), "atr": float(apre[s]),
                 "comp": bool(apre[s] / a100p[s] < 1), "gday": {}}
            for m in STOPM:
                for y in (1, -1):
                    e["gday"][(m, y)] = giorno_entrata(so, sh, sl, i0, entry, m * apre[s], y)
            evR.append(e)
        eventi[(lv, "R")] = evR
        # modo C: chiusura oltre il livello, entrata alla chiusura
        a20, a100 = d["atr20"].to_numpy(float), d["atr100"].to_numpy(float)
        ok = (dentro & np.isfinite(Hp) & np.isfinite(Lp) & np.isfinite(a20)
              & np.isfinite(a100) & (pcv <= Hp) & (pcv >= Lp))
        evC = []
        for s in np.nonzero(ok & ((c > Hp) | (c < Lp)))[0]:
            evC.append({"s": int(s), "x": 1 if c[s] > Hp[s] else -1, "entry": float(c[s]),
                        "atr": float(a20[s]), "comp": bool(a20[s] / a100[s] < 1), "gday": None})
        eventi[(lv, "C")] = evC
    del lab, bo, bh, bl

    def esito(e, lv, m, ex, y):
        """(indice uscita, prezzo uscita reale) per la direzione y."""
        s, dist = e["s"], m * e["atr"]
        O, H, L, C = P[y]
        entry_n = y * e["entry"]
        stop = entry_n - dist
        if e["gday"] is not None:
            usc, px, fav = e["gday"][(m, y)]
            if usc:
                return s, px
            hh = y * fav
        else:
            hh = entry_n
        k = {"T2": 2, "T3": 3}.get(ex, 0)
        D = {"D5": 5, "D10": 10, "D20": 20}.get(ex, 0)
        CH = CHAN[(y, N2[lv])] if ex == "OPP" else None
        if k:
            stop = max(stop, hh - k * Al[s])
        elif CH is not None:
            stop = max(stop, CH[s])
        t, pxn = avanti(O, H, L, C, Al, CH, s, stop, hh, D, k)
        return t, y * pxn

    righe = []
    cache = {}
    for lv in LIVELLI:
        for mo in MODI:
            ev = eventi[(lv, mo)]
            for m in STOPM:
                for ex in USCITE:
                    for f in FILTRI:
                        ultimo = -1
                        for q, e in enumerate(ev):
                            if e["s"] <= ultimo or e["s"] >= T - 1 or (f and not e["comp"]):
                                continue
                            key = (lv, mo, q, m, ex)
                            if key not in cache:
                                cache[key] = (esito(e, lv, m, ex, e["x"]),
                                              esito(e, lv, m, ex, -e["x"]))
                            (tr_, pr), (tm, pm) = cache[key]
                            ultimo = tr_
                            righe.append((lv, mo, m, ex, f, e["s"], e["x"], e["entry"],
                                          m * e["atr"], tr_, pr, tm, pm))
    del cache
    t = pd.DataFrame(righe, columns=["lv", "modo", "m", "uscita", "filtro", "s", "dir",
                                     "entrata", "dist", "u_idx", "u_px", "um_idx", "um_px"])
    t["lv"] = t["lv"].astype(str)
    t["mercato"] = mercato
    t["g_entrata"] = d["giorno"].to_numpy()[t["s"].to_numpy()]
    t["g_uscita"] = d["giorno"].to_numpy()[t["u_idx"].to_numpy()]
    t["gm_uscita"] = d["giorno"].to_numpy()[t["um_idx"].to_numpy()]
    x = t["dir"].to_numpy(float)
    t["lordo_R"] = x * (t["u_px"] - t["entrata"]) / t["dist"]
    t["lordo_m_R"] = -x * (t["um_px"] - t["entrata"]) / t["dist"]
    t["costo_R"] = np.array([costo_rt(mercato, a, costi) for a in t["g_entrata"].dt.year]) / t["dist"].to_numpy()
    # swap: notti dei giorni feriali in [entrata, uscita), mercoledi' x3, al prezzo del giorno
    ie = giorni_sw.searchsorted(t["g_entrata"])
    fattore = cum_sw[giorni_sw.searchsorted(t["g_uscita"])] - cum_sw[ie]
    fattore_m = cum_sw[giorni_sw.searchsorted(t["gm_uscita"])] - cum_sw[ie]

    def tasso(dirz):
        if mercato == "XAUUSD":
            return np.where(dirz > 0, ORO_LONG, ORO_SHORT) / ORO_RIF
        return np.full(len(dirz), -SWAP_ANNUO / 360.0)
    t["swap_R"] = tasso(x) * fattore / t["dist"]
    t["swap_m_R"] = tasso(-x) * fattore_m / t["dist"]
    t["giorni"] = t["u_idx"] - t["s"]
    t = t.drop(columns=["s", "u_idx", "um_idx"])
    print(f"{mercato}: {len(d)} giornate, eventi R {controllo['R_eventi']} "
          f"(ambigui {controllo['R_ambigui']}, incoerenti {controllo['R_incoerenti']}), "
          f"operazioni {len(t)}, {time.time() - t0:.0f}s", flush=True)
    return t


def simula():
    RIS.mkdir(parents=True, exist_ok=True)
    pan = pd.read_parquet(PANIERE)
    costi = pd.read_csv(BASE / "costi.csv").set_index("mercato")["costo_rt"].to_dict()
    for mk in MERCATI:
        t = simula_mercato(mk, pan, costi)
        t.to_parquet(RIS / f"f4_operazioni_{mk}.parquet", index=False)
        del t


# --------------------------------------------------------------------------
# aggregazione
# --------------------------------------------------------------------------

def max_dd(x):
    cum = np.cumsum(x)
    picco = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:]
    return float(np.max(picco - cum)) if len(cum) else 0.0


def misure(g):
    net = (g["lordo_R"] - g["costo_R"] + g["swap_R"]).to_numpy()
    net15 = (g["lordo_R"] - 1.5 * g["costo_R"] + g["swap_R"]).to_numpy()
    mese = g["g_uscita"].dt.to_period("M")
    mens = pd.Series(net, index=mese).groupby(level=0).sum().reindex(MESI, fill_value=0.0)
    sd = mens.std(ddof=1)
    tt = mens.mean() / sd * np.sqrt(len(mens)) if sd > 0 else 0.0
    anno = pd.Series(net, index=g["g_uscita"].dt.year).groupby(level=0).sum()
    anni = int((anno.reindex(ANNI, fill_value=0.0) > 0).sum())
    ordine = np.argsort(g["g_uscita"].to_numpy(), kind="stable")
    lordo_tot = g["lordo_R"].sum()
    return dict(n=len(g), op_mese=len(g) / len(MESI), lordo_R=g["lordo_R"].mean(),
                netto_R=net.mean(), netto_tot=net.sum(), t=tt, anni=anni,
                netto15_R=net15.mean(), netto15_tot=net15.sum(),
                swap_R=g["swap_R"].mean(), costo_R=g["costo_R"].mean(),
                giorni=g["giorni"].mean(), dd=max_dd(net[ordine]))


def aggrega():
    t = pd.concat([pd.read_parquet(RIS / f"f4_operazioni_{mk}.parquet") for mk in MERCATI],
                  ignore_index=True)
    t = t[t["g_entrata"] <= FINE]
    t["net"] = t["lordo_R"] - t["costo_R"] + t["swap_R"]
    t["net_m"] = t["lordo_m_R"] - t["costo_R"] + t["swap_m_R"]
    ambiti = {"paniere": MERCATI, **GRUPPI,
              "senza_oro": [m for m in MERCATI if m != "XAUUSD"],
              **{m: [m] for m in MERCATI}}
    out = []
    chiavi = ["lv", "modo", "m", "uscita", "filtro"]
    for r, g in t.groupby(chiavi, sort=False):
        g = g.reset_index(drop=True)
        rng = np.random.default_rng(SEED)
        scelta = rng.random((NPLACEBO, len(g))) < 0.5
        reale, spec = g["net"].to_numpy(), g["net_m"].to_numpy()
        val = np.where(scelta, reale, spec)          # direzione casuale
        mk = g["mercato"].to_numpy()
        for amb, lst in ambiti.items():
            sel = np.isin(mk, lst)
            if not sel.any():
                continue
            mm = misure(g[sel])
            plac = val[:, sel].sum(axis=1)
            mm["p"] = (1 + (plac >= reale[sel].sum()).sum()) / (1 + NPLACEBO)
            out.append({"regola": nome((r[0] if r[0] == "W" else int(r[0]),) + r[1:]),
                        "ambito": amb, **dict(zip(chiavi, r)), **mm})
    v = pd.DataFrame(out)
    v["passa"] = ((v["netto_tot"] > 0) & (v["netto15_tot"] > 0) & (v["t"] >= 3)
                  & (v["anni"] >= 6) & (v["p"] < 0.01))
    v.to_parquet(RIS / "f4_varianti.parquet", index=False)
    stampa(v)


def stampa(v):
    prom = v[v["ambito"].isin(["paniere", "indici", "metalli", "cambi"])]
    print(f"\nRegole {v['regola'].nunique()}, valutazioni promuovibili {len(prom)} "
          f"(paniere + 3 gruppi), per mercato {len(v[~v['ambito'].isin(['paniere','indici','metalli','cambi','senza_oro'])])}")
    riass = prom.groupby("ambito").agg(
        netto_pos=("netto_tot", lambda s: (s > 0).sum()), t3=("t", lambda s: (s >= 3).sum()),
        t_neg3=("t", lambda s: (s <= -3).sum()), anni6=("anni", lambda s: (s >= 6).sum()),
        p01=("p", lambda s: (s < 0.01).sum()), passa=("passa", "sum"),
        t_med=("t", "median"), t_max=("t", "max"))
    print(riass.round(2).to_string())
    col = ["regola", "ambito", "n", "op_mese", "lordo_R", "netto_R", "netto_tot", "t", "anni",
           "netto15_tot", "swap_R", "dd", "p", "passa"]
    print("\nMigliori 15 per t (paniere e gruppi):")
    print(prom.sort_values("t", ascending=False)[col].head(15).round(3).to_string(index=False))


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "tutto"
    if arg in ("simula", "tutto"):
        simula()
    if arg in ("aggrega", "tutto"):
        aggrega()
