#!/usr/bin/env python3
"""Famiglia E macro: oro attorno a FOMC, verbali FOMC, CPI, NFP. Solo scoperta.

Protocollo: docs/macro-oro-registrazione.md; griglia (464 varianti) dichiarata
in docs/studies/macro/e-eventi.md PRIMA del calcolo.

Dati: D:\\ricerca_zero\\scoperta\\XAUUSD_M5.parquet (M5 BID, UTC all'apertura),
D:\\ricerca_macro\\scoperta\\MACRO_D1.parquet (giornata dell'oro, chiude alle
17:00 New York), calendario D:\\ricerca_macro\\dati\\eventi\\calendario_2009_2026.csv
(macro_e_calendario.py). Solo data/ora degli eventi, mai il valore del dato.

Convenzioni: tempi in minuti dal 2009-01-01 00:00 UTC; prezzo all'istante t =
chiusura dell'ultima M5 terminata entro t. Intraday 1R = 0,5 x ATR20 (stop
alla stessa distanza); piu' giorni 1R = 2 x ATR20 (motore famiglia B).
Costi 0,46 $ RT + 2 x 0,46 $ per gamba in [T-5m, T+5m]; x1 e x1,5. Swap FP
riscalato su ogni 21:00 UTC lun-ven attraversata, x3 il mercoledi'.

Scrive in D:\\ricerca_macro\\risultati\\:
    e_istanze.parquet      eventi e giorni di controllo (stessa ora UTC)
    e_descrittiva.parquet  rendimento e volatilita' per tipo e finestra
    e_operazioni.parquet   una riga per evento e regola (esito reale)
    e_varianti.parquet     una riga per regola con misure, anni e p
Stampa solo aggregati compatti.
"""
from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd

M5 = r"D:\ricerca_zero\scoperta\XAUUSD_M5.parquet"
D1 = r"D:\ricerca_macro\scoperta\MACRO_D1.parquet"
CAL = r"D:\ricerca_macro\dati\eventi\calendario_2009_2026.csv"
OUT = r"D:\ricerca_macro\risultati"
RT = 0.46
EXTRA = 2 * RT          # gamba nei 5 minuti attorno all'annuncio: spread x3
ORO_LONG, ORO_SHORT, ORO_RIF = -0.715, 0.325, 4156.98
NPLAC, SEED = 1000, 12345
ANNI = list(range(2009, 2018))
TIPI = ["FOMC", "VERBALI", "CPI", "NFP"]
T0 = pd.Timestamp("2009-01-01", tz="UTC")
KCTRL = 8               # settimane prima/dopo per i giorni di controllo
pd.set_option("display.width", 200)


# ------------------------------------------------------------------ dati
class Griglia:
    """M5 su griglia regolare: slot k = barra che apre a T0 + 5k minuti."""

    def __init__(self):
        m = pd.read_parquet(M5)
        k = ((m.index - T0) // pd.Timedelta("5min")).to_numpy()
        n = k.max() + 1
        self.n = n
        self.O, self.H, self.L, self.C = (np.full(n, np.nan) for _ in range(4))
        for arr, col in ((self.O, "open"), (self.H, "high"), (self.L, "low"), (self.C, "close")):
            arr[k] = m[col].to_numpy(float)
        self.has = ~np.isnan(self.C)
        self.cff = pd.Series(self.C).ffill().to_numpy()
        self.cumhas = np.r_[0, np.cumsum(self.has)]

    def slot(self, t):
        return (np.asarray(t) // 5).astype(np.int64)

    def px(self, t):
        """Prezzo all'istante t (minuti, multiplo di 5)."""
        k = self.slot(t) - 1
        return np.where((k >= 0) & (k < self.n), self.cff[np.clip(k, 0, self.n - 1)], np.nan)

    def barre(self, a, b):
        """Numero di barre vere negli slot [slot(a), slot(b))."""
        ka = np.clip(self.slot(a), 0, self.n)
        kb = np.clip(self.slot(b), 0, self.n)
        return self.cumhas[kb] - self.cumhas[ka]


def carica_d1():
    d = pd.read_parquet(D1)
    d = d[d["valida"]].copy()
    d.index = pd.to_datetime(d.index)
    fine = (d.index + pd.Timedelta("17h")).tz_localize("America/New_York").tz_convert("UTC")
    d["fine_min"] = ((fine - T0) // pd.Timedelta("1min")).astype(np.int64)
    return d


def pesi_swap(ndays):
    """Peso cumulato delle 21:00 UTC lun-ven (mercoledi' x3) dal giorno 0."""
    dow = (np.arange(ndays) + T0.dayofweek) % 7  # 0 = lunedi'
    w = np.where(dow >= 5, 0, np.where(dow == 2, 3, 1))
    return np.r_[0, np.cumsum(w)]


# --------------------------------------------------------------- istanze
def istanze(G):
    cal = pd.read_csv(CAL)
    cal["data_ny"] = pd.to_datetime(cal["data_ny"]).dt.date
    date_evento = set(cal["data_ny"])
    ev = cal[cal["tipo"].isin(TIPI) & cal["annunciata_prima"] & cal["dt_utc"].notna()].copy()
    ev["T"] = ((pd.to_datetime(ev["dt_utc"]).dt.tz_localize("UTC") - T0) // pd.Timedelta("1min")).astype(np.int64)
    ev = ev[(ev["T"] > 1440) & (ev["T"] < G.n * 5 - 10 * 1440)].reset_index(drop=True)
    righe = []
    for i, r in ev.iterrows():
        righe.append(dict(tipo=r["tipo"], evento=i, T=r["T"], vero=True, data_ny=r["data_ny"],
                          ora_ny=r["ora_ny"]))
        for k in list(range(-KCTRL, 0)) + list(range(1, KCTRL + 1)):
            dc = r["data_ny"] + pd.Timedelta(days=7 * k)
            if dc in date_evento:
                continue
            righe.append(dict(tipo=r["tipo"], evento=i, T=r["T"] + 7 * k * 1440, vero=False,
                              data_ny=dc, ora_ny=r["ora_ny"]))
    I = pd.DataFrame(righe)
    I = I[(I["T"] > 1440) & (I["T"] < G.n * 5 - 10 * 1440)].reset_index(drop=True)
    T = I["T"].to_numpy()
    I["ok"] = (G.barre(T - 30, T) >= 3) & (G.barre(T, T + 5) == 1)
    I["anno"] = (T0 + pd.to_timedelta(I["T"], unit="min")).dt.year
    return I


# ------------------------------------------------------ motore intraday
def operazione(G, W, ent_t, ex_t, dz, R, stop_on, T):
    """Esito di operazioni intraday vettoriali. Restituisce dict di array."""
    n = len(ent_t)
    ent = G.px(ent_t)
    ki, ke = G.slot(ent_t), G.slot(ex_t)
    usc = G.px(ex_t)
    kx = ke.copy()  # slot d'uscita (inizio)
    fatto = np.zeros(n, bool)
    if stop_on:
        stop = ent - dz * R
        Lmax = int(np.nanmax(ke - ki)) if n else 0
        for j in range(Lmax):
            kk = ki + j
            att = (~fatto) & (kk < ke)
            if not att.any():
                continue
            kc = np.clip(kk, 0, G.n - 1)
            lo, hi, op = G.L[kc], G.H[kc], G.O[kc]
            tocco = att & np.where(dz == 1, lo <= stop, hi >= stop)
            tocco &= ~np.isnan(lo)
            px = np.where(dz == 1, np.minimum(op, stop), np.maximum(op, stop))
            usc = np.where(tocco, px, usc)
            kx = np.where(tocco, kk, kx)
            fatto |= tocco
    t_usc = np.where(fatto, kx * 5, ex_t)
    notti = W[np.maximum((t_usc - 1260) // 1440 + 1, 0)] - W[np.maximum((ent_t - 1260) // 1440 + 1, 0)]
    sw = np.where(dz == 1, ORO_LONG, ORO_SHORT) * ent / ORO_RIF * notti
    gambe = (np.abs(ent_t - T) <= 5).astype(int) + (np.abs(t_usc - T) <= 5).astype(int)
    costo = RT + EXTRA * gambe
    lordo = dz * (usc - ent)
    return dict(lordo=lordo / R, swap=sw / R, costo=costo / R, usd=lordo + sw - costo,
                usd15=lordo + sw - 1.5 * costo, stopp=fatto, gambe=gambe, notti=notti)


def lento(G, W, ent_t, ex_t, dz, R, stop_on, T):
    """Controllo: stesso esito con un ciclo barra per barra."""
    ent = G.px(np.array([ent_t]))[0]
    usc, t_usc = G.px(np.array([ex_t]))[0], ex_t
    stop = ent - dz * R
    if stop_on:
        for k in range(ent_t // 5, ex_t // 5):
            if np.isnan(G.L[k]):
                continue
            if (dz == 1 and G.L[k] <= stop) or (dz == -1 and G.H[k] >= stop):
                usc = min(G.O[k], stop) if dz == 1 else max(G.O[k], stop)
                t_usc = k * 5
                break
    notti = 0
    for t in range(ent_t + 1, t_usc + 1):
        if t % 1440 == 1260:
            dow = (T0 + pd.Timedelta(minutes=int(t))).dayofweek
            notti += 0 if dow >= 5 else (3 if dow == 2 else 1)
    sw = (ORO_LONG if dz == 1 else ORO_SHORT) * ent / ORO_RIF * notti
    g = int(abs(ent_t - T) <= 5) + int(abs(t_usc - T) <= 5)
    return (dz * (usc - ent) + sw - RT - EXTRA * g) / R


# ----------------------------------------------------- motore piu' giorni
def esiti_d1(d):
    o, h, l, c = (d[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    date = d.index.values.astype("datetime64[D]")
    n = len(d)
    cp = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(cp), h - l, np.maximum(h - l, np.maximum(abs(h - cp), abs(l - cp))))
    atr = pd.Series(tr).rolling(20).mean().to_numpy()

    def notti_cum(x):
        base = np.datetime64("2000-01-03")
        return np.busday_count(base, x) + 2 * np.busday_count(base, x, weekmask="0010000")

    F, F1 = notti_cum(date), notti_cum(date + np.timedelta64(1, "D"))
    es = {}
    for (a, b) in [(1, 1), (1, 3), (1, 5), (1, 10)]:
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
                        px = stop if j == a else (np.minimum(o[jj], stop) if dz == 1 else np.maximum(o[jj], stop))
                        usc[tocco] = np.broadcast_to(px, usc.shape)[tocco]
                        jex = np.where(tocco, jj, jex)
                        fatto |= tocco
                notti = F1[jex] - F[idx + a]
                sw = (ORO_LONG if dz == 1 else ORO_SHORT) * ent / ORO_RIF * notti
                lordo = dz * (usc - ent)
                net = np.full(n, np.nan)
                net15, usd, uscita = net.copy(), net.copy(), net.copy()
                net[idx] = (lordo + sw - RT) / ri
                net15[idx] = (lordo + sw - 1.5 * RT) / ri
                usd[idx] = lordo + sw - RT
                uscita[idx] = jex
                es[(a, b, st, dz)] = dict(netto=net, netto15=net15, usd=usd, uscita=uscita)
    return es, atr, c


# ------------------------------------------------------------ statistiche
def misure(net, net15, usd, anni):
    m = ~np.isnan(net)
    x = net[m]
    n = len(x)
    if n < 3:
        return dict(n=n)
    sd = x.std(ddof=1)
    per_anno = pd.Series(x).groupby(anni[m]).sum().reindex(ANNI).fillna(0)
    cum = np.cumsum(x)
    return dict(n=n, netto=x.mean(), netto15=np.nanmean(net15[m]), usd=np.nanmean(usd[m]),
                t=x.mean() / sd * np.sqrt(n) if sd > 0 else 0.0, anni_pos=int((per_anno > 0).sum()),
                dd=float((np.maximum.accumulate(np.r_[0, cum]) - np.r_[0, cum]).max()),
                totale=x.sum(), **{f"a{a}": v for a, v in per_anno.items()})


def placebo(reale_tot, ctrl, flip_l, flip_s, rng):
    """ctrl: matrice eventi x K di netti dei controlli (nan = non valido,
    0 = regola senza operazione); flip_l/flip_s: netti long/short sugli
    eventi veri (nan = nessuna operazione). p = (1 + #>=)/1001."""
    ne = ctrl.shape[0]
    cnt = (~np.isnan(ctrl)).sum(1)
    cz = np.nan_to_num(ctrl)
    u = rng.random((NPLAC, ne))
    j = np.minimum((u * cnt).astype(int), np.maximum(cnt - 1, 0))
    # j-esimo controllo valido di ogni evento
    ordine = np.argsort(np.isnan(ctrl), axis=1, kind="stable")
    sel = np.take_along_axis(np.broadcast_to(ordine, (NPLAC,) + ordine.shape),
                             j[:, :, None], axis=2)[:, :, 0]
    val = np.take_along_axis(np.broadcast_to(cz, (NPLAC,) + cz.shape), sel[:, :, None], axis=2)[:, :, 0]
    val = np.where(cnt > 0, val, 0.0)
    p_ora = (1 + (val.sum(1) >= reale_tot - 1e-12).sum()) / (NPLAC + 1)
    s = rng.random((NPLAC, len(flip_l))) < 0.5
    tot = np.where(s, np.nan_to_num(flip_l), np.nan_to_num(flip_s)).sum(1)
    p_dir = (1 + (tot >= reale_tot - 1e-12).sum()) / (NPLAC + 1)
    return p_ora, p_dir


# ------------------------------------------------------------------ main
def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    G = Griglia()
    W = pesi_swap(G.n * 5 // 1440 + 30)
    d = carica_d1()
    fine_min = d["fine_min"].to_numpy()
    es1, atr_d, c_d = esiti_d1(d)
    I = istanze(G)
    T = I["T"].to_numpy()
    # ATR20 dell'ultima giornata chiusa prima dell'istante
    def atr_prima(t):
        j = np.searchsorted(fine_min, t, side="right") - 1
        return np.where(j >= 0, atr_d[np.clip(j, 0, None)], np.nan)

    # giornata dell'oro che contiene T
    I["s"] = np.searchsorted(fine_min, T, side="left")
    ev = I[I["vero"]]
    print(f"eventi nel calendario (scoperta): {ev.groupby('tipo').size().to_dict()}; "
          f"validi: {ev[ev['ok']].groupby('tipo').size().to_dict()}")
    scart = ev[~ev["ok"]]
    if len(scart):
        print("scartati (mercato chiuso):", ", ".join(f"{a} {b}" for a, b in zip(scart["tipo"], scart["data_ny"])))
    print(f"controlli validi per evento (mediana): "
          f"{I[~I['vero'] & I['ok']].groupby('evento').size().median():.0f}")
    I.to_parquet(os.path.join(OUT, "e_istanze.parquet"))

    # ---------------- controllo dell'ora FOMC 2009-2012 (|r| 5m, evento / controllo)
    righe = []
    fo = I[(I["tipo"] == "FOMC") & I["ok"] & (I["anno"] <= 2012)]
    for ora in ("12:30", "14:00", "14:15"):
        # sposta T all'ora NY indicata dello stesso giorno (stesso offset UTC)
        hh, mm = map(int, ora.split(":"))
        off = np.array([(hh * 60 + mm) - (int(o[:2]) * 60 + int(o[3:])) for o in fo["ora_ny"]])
        t = fo["T"].to_numpy() + off
        r = np.abs(np.log(G.px(t + 5) / G.px(t))) * 1e4
        x = pd.DataFrame(dict(gruppo=fo["ora_ny"].to_numpy(), vero=fo["vero"].to_numpy(), r=r))
        g = x.groupby(["gruppo", "vero"])["r"].mean().unstack()
        for gr in g.index:
            righe.append(dict(ora_dichiarata=gr, barra_ny=ora, rapporto=g.loc[gr, True] / g.loc[gr, False]))
    chk = pd.DataFrame(righe).pivot(index="ora_dichiarata", columns="barra_ny", values="rapporto")
    print("\nControllo ora FOMC 2009-2012: |r| 5m evento / controllo per barra NY")
    print(chk.dropna(how="all").round(2).to_string())

    # ---------------- descrittiva
    orizz = {"-24h": (-1440, 0), "-4h": (-240, 0), "-1h": (-60, 0), "+5m": (0, 5), "+1h": (0, 60),
             "+4h": (0, 240)}
    dow = ((T // 1440) + T0.dayofweek) % 7
    piu1 = np.where(dow == 4, 3 * 1440, 1440)
    desc = []
    for nome, ab in list(orizz.items()) + [("+1g", None), ("+5g", None)]:
        if nome == "+1g":
            ta, tb = T, T + piu1
        elif nome == "+5g":
            ta, tb = T, T + 7 * 1440
        else:
            ta, tb = T + ab[0], T + ab[1]
        r = np.log(G.px(tb) / G.px(ta)) * 1e4
        ok = I["ok"].to_numpy() & (G.barre(ta - 15, ta) >= 1) & (G.barre(tb - 15, tb) >= 1)
        I["r"] = np.where(ok, r, np.nan)
        for tipo in TIPI:
            x = I[I["tipo"] == tipo]
            e = x[x["vero"]].set_index("evento")["r"]
            cm = x[~x["vero"]].groupby("evento")["r"].mean()
            ca = x[~x["vero"]].assign(a=lambda z: z["r"].abs()).groupby("evento")["a"].mean()
            z = pd.DataFrame(dict(e=e, cm=cm, ca=ca)).dropna()
            dv = z["e"].abs() - z["ca"]
            desc.append(dict(tipo=tipo, finestra=nome, n=len(z), medio_bp=z["e"].mean(),
                             t=z["e"].mean() / z["e"].std() * np.sqrt(len(z)),
                             pos=(z["e"] > 0).mean(), ctrl_bp=z["cm"].mean(),
                             abs_ev=z["e"].abs().mean(), abs_ctrl=z["ca"].mean(),
                             rapp_vol=z["e"].abs().mean() / z["ca"].mean(),
                             t_vol=dv.mean() / dv.std() * np.sqrt(len(z))))
    D = pd.DataFrame(desc)
    D.to_parquet(os.path.join(OUT, "e_descrittiva.parquet"))
    print("\nDescrittiva: rendimento medio (bp, t) e rapporto di volatilita' evento/controllo")
    pm = D.pivot(index="tipo", columns="finestra", values="medio_bp").reindex(TIPI)
    pt = D.pivot(index="tipo", columns="finestra", values="t").reindex(TIPI)
    pv = D.pivot(index="tipo", columns="finestra", values="rapp_vol").reindex(TIPI)
    cols = ["-24h", "-4h", "-1h", "+5m", "+1h", "+4h", "+1g", "+5g"]
    print("medio bp\n" + pm[cols].round(1).to_string())
    print("t\n" + pt[cols].round(2).to_string())
    print("vol ratio\n" + pv[cols].round(2).to_string())

    # ---------------- regole
    ok = I["ok"].to_numpy()
    R_i = 0.5 * atr_prima(T)
    regole, oper = [], []
    vero = I["vero"].to_numpy()
    ev_id = I["evento"].to_numpy()
    anni_i = I["anno"].to_numpy()
    tipo_i = I["tipo"].to_numpy()
    ctrl_slots = {}  # per tipo: matrice eventi x K di indici di istanze di controllo
    for tipo in TIPI:
        e_idx = np.where(vero & (tipo_i == tipo))[0]
        mat = np.full((len(e_idx), 2 * KCTRL), -1)
        pos = {e: k for k, e in enumerate(ev_id[e_idx])}
        cnt = np.zeros(len(e_idx), int)
        for ii in np.where(~vero & (tipo_i == tipo) & ok)[0]:
            k = pos[ev_id[ii]]
            mat[k, cnt[k]] = ii
            cnt[k] += 1
        ctrl_slots[tipo] = (e_idx, mat)

    def valuta(nome, fam, tipo, net, net15, usd, net_l, net_s, extra):
        e_idx, mat = ctrl_slots[tipo]
        ne = net[e_idx]
        # una sola operazione alla volta: per le regole intraday gli eventi non si sovrappongono
        m = misure(ne, net15[e_idx], usd[e_idx], anni_i[e_idx])
        if m.get("n", 0) < 3:
            return
        cm = np.where(mat >= 0, np.nan_to_num(net[np.maximum(mat, 0)]), np.nan)
        rng = np.random.default_rng(SEED)
        p_ora, p_dir = placebo(np.nansum(ne), cm, net_l[e_idx], net_s[e_idx], rng)
        regole.append(dict(regola=nome, famiglia=fam, tipo=tipo, p_ora=p_ora, p_dir=p_dir, **extra, **m))
        for k, ii in enumerate(e_idx):
            if not np.isnan(net[ii]):
                oper.append((nome, tipo, I.at[ii, "data_ny"], anni_i[ii], net[ii], net15[ii], usd[ii]))

    def pack(r, R, sel):
        """netti in R x1, x1,5 e $ per le istanze sel (altrove nan)."""
        out = []
        for k in ("netto", "netto15", "usd"):
            out.append(np.full(len(I), np.nan))
        lordo_sw = r["lordo"] + r["swap"]
        out[0][sel] = (lordo_sw - r["costo"])[sel]
        out[1][sel] = (lordo_sw - 1.5 * r["costo"])[sel]
        out[2][sel] = r["usd"][sel]
        return out

    # verifica del motore intraday contro il ciclo lento
    rng0 = np.random.default_rng(7)
    diff = 0.0
    cand = np.where(ok & ~np.isnan(R_i))[0]
    for _ in range(300):
        ii = rng0.choice(cand)
        a = int(rng0.choice([-1440, -240, -60, 5, 15, 30]))
        b = int(rng0.choice([-10, 60, 240])) if a > 0 else -10
        dz = int(rng0.choice([1, -1]))
        st = int(rng0.integers(0, 2))
        ta, tb = np.array([T[ii] + a]), np.array([T[ii] + b])
        r = operazione(G, W, ta, tb, np.array([dz]), np.array([R_i[ii]]), st, np.array([T[ii]]))
        v1 = (r["lordo"] + r["swap"] - r["costo"])[0]
        v2 = lento(G, W, int(ta[0]), int(tb[0]), dz, R_i[ii], st, int(T[ii]))
        if not (np.isnan(v1) and np.isnan(v2)):
            diff = max(diff, abs(v1 - v2))
    print(f"\nControllo motore intraday (300 operazioni casuali): differenza massima {diff:.2e}")

    # E1 deriva pre-annuncio
    for h in (1440, 240, 60):
        ta, tb = T - h, T - 10
        R_h = 0.5 * atr_prima(ta)  # ATR noto all'entrata
        valido = ok & (G.barre(ta - 15, ta) >= 1) & ~np.isnan(R_h)
        res = {}
        for st in (0, 1):
            for dz in (1, -1):
                r = operazione(G, W, ta, tb, np.full(len(T), dz), R_h, st, T)
                res[(st, dz)] = pack(r, R_h, valido)
            for dz, nd in ((1, "long"), (-1, "short")):
                for tipo in TIPI:
                    n1, n15, us = res[(st, dz)]
                    valuta(f"E1 {tipo} pre{h // 60}h {nd} stop{st}", "E1", tipo, n1, n15, us,
                           res[(st, 1)][0], res[(st, -1)][0],
                           dict(param=f"pre{h // 60}h", direzione=nd, stop=st))

    # E2 primo movimento
    eod = (T // 1440) * 1440 + 20 * 60 + 55
    for dmin in (5, 15, 30):
        p0, pd_ = G.px(T), G.px(T + dmin)
        mv = pd_ - p0
        val0 = ok & (G.barre(T, T + dmin) >= 1) & ~np.isnan(R_i) & (mv != 0) & ~np.isnan(mv)
        sgn = np.sign(np.nan_to_num(mv)).astype(int)
        for uscita, tb in (("1h", T + 60), ("4h", T + 240), ("eod", eod)):
            valido = val0 & (tb > T + dmin + 5)
            for st in (0, 1):
                rl = operazione(G, W, T + dmin, tb, np.ones(len(T), int), R_i, st, T)
                rs = operazione(G, W, T + dmin, tb, -np.ones(len(T), int), R_i, st, T)
                L_, S_ = pack(rl, R_i, valido), pack(rs, R_i, valido)
                for verso, nv in ((1, "segue"), (-1, "rientro")):
                    dirz = sgn * verso
                    comb = [np.where(dirz == 1, L_[k], S_[k]) for k in range(3)]
                    for filt in (0, 1):
                        f = np.ones(len(T), bool) if filt == 0 else (np.abs(np.nan_to_num(mv)) >= 0.15 * 2 * R_i)
                        sel = [np.where(f, c_, np.nan) for c_ in comb]
                        # i controlli senza segnale contano 0 nel placebo ORA (vedi valuta)
                        for tipo in TIPI:
                            valuta(f"E2 {tipo} d{dmin} {nv} filt{filt} {uscita} stop{st}", "E2", tipo,
                                   sel[0], sel[1], sel[2],
                                   np.where(f, L_[0], np.nan), np.where(f, S_[0], np.nan),
                                   dict(param=f"d{dmin} filt{filt} {uscita}", direzione=nv, stop=st))

    # E3 giorni dopo l'evento (giornate D1)
    s_i = I["s"].to_numpy()
    s_ok = (s_i >= 1) & (s_i < len(d)) & ok
    s_c = np.clip(s_i, 1, len(d) - 1)
    mv1 = np.where(s_ok, np.sign(c_d[s_c] - c_d[s_c - 1]), 0).astype(int)
    for (a, b) in [(1, 1), (1, 3), (1, 5), (1, 10)]:
        for st in (0, 1):
            L_ = [es1[(a, b, st, 1)][k][s_c] for k in ("netto", "netto15", "usd")]
            S_ = [es1[(a, b, st, -1)][k][s_c] for k in ("netto", "netto15", "usd")]
            ux = es1[(a, b, st, 1)]["uscita"][s_c]
            for nd in ("long", "short", "segue", "rientro"):
                dirz = {"long": np.ones(len(T), int), "short": -np.ones(len(T), int),
                        "segue": mv1, "rientro": -mv1}[nd]
                comb = [np.where(s_ok & (dirz == 1), L_[k], np.where(s_ok & (dirz == -1), S_[k], np.nan))
                        for k in range(3)]
                for tipo in TIPI:
                    # nessuna sovrapposizione fra eventi veri dello stesso tipo
                    c0 = [x.copy() for x in comb]
                    e_idx = np.where(vero & (tipo_i == tipo))[0]
                    occ = -1
                    for ii in e_idx[np.argsort(T[e_idx])]:
                        if np.isnan(c0[0][ii]):
                            continue
                        if s_c[ii] + a <= occ:
                            for x in c0:
                                x[ii] = np.nan
                        else:
                            occ = ux[ii]
                    valuta(f"E3 {tipo} ({a},{b}) {nd} stop{st}", "E3", tipo, c0[0], c0[1], c0[2],
                           np.where(s_ok, L_[0], np.nan), np.where(s_ok, S_[0], np.nan),
                           dict(param=f"({a},{b})", direzione=nd, stop=st))

    V = pd.DataFrame(regole)
    V.to_parquet(os.path.join(OUT, "e_varianti.parquet"))
    pd.DataFrame(oper, columns=["regola", "tipo", "data_ny", "anno", "netto", "netto15", "usd"]).astype(
        {"data_ny": str}).to_parquet(os.path.join(OUT, "e_operazioni.parquet"))

    V["passa"] = ((V["netto"] > 0) & (V["netto15"] > 0) & (V["t"] >= 3) & (V["anni_pos"] >= 7)
                  & (V["p_ora"] < 0.01) & (V["p_dir"] < 0.01))
    print(f"\nVarianti valutate: {len(V)} (dichiarate 464); promosse: {int(V['passa'].sum())}")
    s = V.groupby(["famiglia", "tipo"]).agg(var=("t", "size"), pos=("netto", lambda x: (x > 0).mean()),
                                            t_med=("t", "median"), t_min=("t", "min"), t_max=("t", "max"),
                                            t3=("t", lambda x: (x >= 3).sum()),
                                            pdir01=("p_dir", lambda x: (x < 0.01).sum()),
                                            pora01=("p_ora", lambda x: (x < 0.01).sum()),
                                            anni7=("anni_pos", lambda x: (x >= 7).sum()),
                                            passa=("passa", "sum"))
    print(s.round(2).to_string())
    top = V.sort_values("t", ascending=False).head(12)
    print("\nMigliori 12 per t:")
    print(top[["regola", "n", "netto", "netto15", "usd", "t", "anni_pos", "dd", "p_ora", "p_dir"]]
          .round(3).to_string(index=False))
    bot = V.sort_values("t").head(5)
    print("\nPeggiori 5 per t:")
    print(bot[["regola", "n", "netto", "usd", "t", "anni_pos", "p_ora", "p_dir"]].round(3).to_string(index=False))
    print(f"\n{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
