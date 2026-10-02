"""Ricerca da zero, famiglia 3: range di apertura e massimi/minimi precedenti.

Protocollo: docs/ricerca-da-zero-registrazione.md. Usa SOLO
D:\\ricerca_zero\\scoperta\\<SIM>_M5.parquet. Varianti dichiarate in
docs/studies/zero/f3-range.md (1620 = 756 parte a + 864 parte b).

Controllo fusi: lo script stampa l'ora UTC della M5 piu' volatile in inverno
e in estate USA (attesi: metalli 13:30/12:30, S&P e Nasdaq 14:30/13:30, DAX
08:00/07:00). La prima versione dei file HistData aveva le etichette avanti di
1 ora durante l'ora legale di New York; i file sono stati rigenerati alla
fonte e lo script NON applica correzioni proprie: se il controllo fallisce si
ferma.

Uscite: D:\\ricerca_zero\\risultati\\f3_varianti.parquet (una riga per
variante) e f3_dettaglio_<SIM>.parquet (una riga per operazione).
"""
from __future__ import annotations

import gc
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCOPERTA = Path(r"D:\ricerca_zero\scoperta")
RISULTATI = Path(r"D:\ricerca_zero\risultati")
SIMBOLI = ["XAUUSD", "XAGUSD", "SPXUSD", "NSXUSD", "GRXEUR"]
PICCO_ATTESO = {"XAUUSD": ("13:30", "12:30"), "XAGUSD": ("13:30", "12:30"), "SPXUSD": ("14:30", "13:30"),
                "NSXUSD": ("14:30", "13:30"), "GRXEUR": ("08:00", "07:00")}
COSTO = {"XAUUSD": 0.40, "XAGUSD": 0.025, "SPXUSD": 0.55, "NSXUSD": 1.50, "GRXEUR": 1.50}
METALLI = {"XAUUSD", "XAGUSD"}
# sessioni cash degli indici (fuso, apertura, chiusura in ora locale)
CASH = {"SPXUSD": ("America/New_York", "09:30", "16:00"),
        "NSXUSD": ("America/New_York", "09:30", "16:00"),
        "GRXEUR": ("Europe/Berlin", "09:00", "17:30")}
OR_MIN = [15, 30, 60]
N_PLACEBO = 1000
SEED = 12345
MIN_R_COSTI = 2.0  # rischio minimo = 2 x costo round trip
TAGLIO_SEGNALI = pd.Timedelta(minutes=60)
M5 = pd.Timedelta(minutes=5)
NS = 10**9


# ---------------------------------------------------------------- dati
def carica(sim: str) -> pd.DataFrame:
    d = pd.read_parquet(SCOPERTA / f"{sim}_M5.parquet", columns=["open", "high", "low", "close"])
    d = d[~d.index.duplicated()].sort_index()
    d.index = d.index.as_unit("ns")
    return d


def controllo_fuso(sim: str, d: pd.DataFrame) -> str:
    """Ora UTC della M5 piu' volatile, inverno vs estate USA."""
    r = (d.high - d.low) / d.close
    us_dst = d.index.tz_convert("America/New_York").strftime("%z") == "-0400"
    picchi = []
    for m in (~us_dst, us_dst):
        x = r[m]
        picchi.append(x.groupby(x.index.strftime("%H:%M")).mean().idxmax())
    if tuple(picchi) != PICCO_ATTESO[sim]:
        raise SystemExit(f"{sim}: picco di volatilita' {picchi}, atteso {PICCO_ATTESO[sim]}: fuso errato")
    return f"inv {picchi[0]}, est {picchi[1]}"


def giornaliero(d: pd.DataFrame) -> pd.DataFrame:
    g = d.groupby(d.index.floor("D")).agg(open=("open", "first"), high=("high", "max"),
                                          low=("low", "min"), close=("close", "last"),
                                          n=("close", "size"))
    g = g[g.n >= 0.5 * g.n.median()].copy()
    g.index = g.index.as_unit("ns")
    pc = g.close.shift(1)
    tr = np.maximum(g.high - g.low, np.maximum((g.high - pc).abs(), (g.low - pc).abs()))
    g["atr14"] = tr.rolling(14).mean()  # include il giorno stesso: si usa solo dal giorno dopo
    g["rng"] = g.high - g.low
    return g


def info_giorno_prec(g: pd.DataFrame, date_utc: pd.DatetimeIndex) -> pd.DataFrame:
    """Per ogni data (00:00 UTC) i dati dell'ultimo giorno valido precedente."""
    pos = np.searchsorted(g.index.values, date_utc.values, side="left") - 1
    ok = pos >= 0
    pos = np.where(ok, pos, 0)
    out = pd.DataFrame({"pdh": g.high.values[pos], "pdl": g.low.values[pos],
                        "prng": g.rng.values[pos], "atr": g.atr14.values[pos]}, index=date_utc)
    out.loc[~ok] = np.nan
    return out


def terzili_causali(x: pd.Series) -> pd.Series:
    """'piccolo' / 'grande' / 'medio' / '' rispetto ai 250 valori precedenti."""
    prev = x.shift(1)
    q1 = prev.rolling(250, min_periods=60).quantile(1 / 3)
    q2 = prev.rolling(250, min_periods=60).quantile(2 / 3)
    lab = np.where(q1.isna() | x.isna(), "", np.where(x <= q1, "piccolo", np.where(x >= q2, "grande", "medio")))
    return pd.Series(lab, index=x.index)


# ------------------------------------------------------------ simulazione
def simula(o, h, l, c, e, z, d, R, T):
    """Ritorna (prezzo uscita - entrata) * d. e = indice entrata (apertura),
    z = ultimo indice incluso (uscita alla chiusura). Stop prima del target
    nella stessa candela; apertura oltre il livello = uscita all'apertura."""
    n = len(e)
    if n == 0:
        return np.zeros(0)
    L = int((z - e).max()) + 1
    k = np.arange(L)
    ix = np.minimum(e[:, None] + k[None, :], len(o) - 1)
    valid = k[None, :] <= (z - e)[:, None]
    sgn = d[:, None]
    # trasforma in "long": per i short si negano i prezzi
    oo = o[ix] * sgn
    hh = np.where(sgn > 0, h[ix], -l[ix])
    ll = np.where(sgn > 0, l[ix], -h[ix])
    ent = o[e] * d
    sp = (ent - R)[:, None]
    tp = (ent + T)[:, None]
    hs = valid & (ll <= sp)
    ht = valid & (hh >= tp)
    fs = np.where(hs.any(1), hs.argmax(1), L)
    ft = np.where(ht.any(1), ht.argmax(1), L)
    rows = np.arange(n)
    exit_ = c[z] * d  # chiusura dell'ultima candela
    o_fs = oo[rows, np.minimum(fs, L - 1)]
    o_ft = oo[rows, np.minimum(ft, L - 1)]
    stop_px = np.where(fs > 0, np.minimum(o_fs, ent - R), ent - R)
    targ_px = np.where(ft > 0, np.maximum(o_ft, ent + T), ent + T)
    usa_s = (fs < L) & (fs <= ft)
    usa_t = (ft < L) & (ft < fs)
    exit_ = np.where(usa_s, stop_px, np.where(usa_t, targ_px, exit_))
    return exit_ - ent


# ------------------------------------------------------------- segnali
def finestre_metalli(date_utc, ini_h, fine_h):
    s = date_utc + pd.Timedelta(hours=ini_h)
    f = date_utc + pd.Timedelta(hours=fine_h)
    return s.as_unit("ns"), f.as_unit("ns")


def finestre_cash(sim, t0, t1):
    tz, a, b = CASH[sim]
    giorni = pd.date_range(t0.tz_convert(tz).normalize().tz_localize(None),
                           t1.tz_convert(tz).normalize().tz_localize(None), freq="B")
    s = pd.DatetimeIndex([pd.Timestamp(f"{g.date()} {a}").tz_localize(tz) for g in giorni]).tz_convert("UTC")
    f = pd.DatetimeIndex([pd.Timestamp(f"{g.date()} {b}").tz_localize(tz) for g in giorni]).tz_convert("UTC")
    return s.as_unit("ns"), f.as_unit("ns")


def sessioni_valide(t, s, f, esatta=True):
    i0 = np.searchsorted(t, s.asi8 if hasattr(s, "asi8") else s)
    i1 = np.searchsorted(t, f.asi8)
    attesi = (f - s) / M5
    nb = i1 - i0
    ok = (nb >= 0.5 * attesi.values) & (i0 < len(t))
    first = t[np.minimum(i0, len(t) - 1)]
    if esatta:
        ok &= first == s.asi8
    else:
        ok &= (first - s.asi8) <= 15 * 60 * NS
    return i0, i1, ok


def segnali_orb(arr, s, f, i0, i1, ok, m):
    """Per ogni sessione valida: segnali ROTTURA e RIENTRO del range di m minuti."""
    t, o, h, l, c = arr
    out = {"ROTTURA": [], "RIENTRO": []}
    ratio_rows = []
    s_ns, f_ns = s.asi8, f.asi8
    for q in np.flatnonzero(ok):
        a, b = i0[q], i1[q]
        ore = np.searchsorted(t, s_ns[q] + m * 60 * NS)
        if ore - a != m // 5:
            continue
        H, Lw = h[a:ore].max(), l[a:ore].min()
        W = H - Lw
        if W <= 0:
            continue
        ratio_rows.append((q, W))
        js = np.searchsorted(t, f_ns[q] - TAGLIO_SEGNALI.value)
        if js <= ore:
            continue
        cc = c[ore:js]
        fuori = (cc > H) | (cc < Lw)
        if not fuori.any():
            continue
        k = ore + int(fuori.argmax())
        dirb = 1 if c[k] > H else -1
        if k + 1 < b:
            out["ROTTURA"].append((q, k + 1, b - 1, dirb, H, Lw, W, np.nan))
        dentro = (c[k + 1:js] <= H) & (c[k + 1:js] >= Lw)
        if dentro.any():
            j = k + 1 + int(dentro.argmax())
            if j + 1 < b:
                ext = h[k:j + 1].max() if dirb > 0 else l[k:j + 1].min()
                out["RIENTRO"].append((q, j + 1, b - 1, -dirb, H, Lw, W, ext))
    cols = ["q", "e", "z", "d", "H", "L", "W", "ext"]
    return {r: pd.DataFrame(v, columns=cols) for r, v in out.items()}, pd.DataFrame(ratio_rows, columns=["q", "W"])


def segnali_livelli(arr, s, f, i0, i1, ok, H, Lv):
    """Regole TS, TR, CS, FR su entrambi i lati; H, Lv livelli per sessione."""
    t, o, h, l, c = arr
    f_ns = f.asi8
    out = {"TS": [], "TR": [], "CS": [], "FR": []}
    for q in np.flatnonzero(ok & np.isfinite(H) & np.isfinite(Lv)):
        a, b = i0[q], i1[q]
        js = np.searchsorted(t, f_ns[q] - TAGLIO_SEGNALI.value)
        if js <= a:
            continue
        for lato, lev in ((1, H[q]), (-1, Lv[q])):
            if lato > 0:
                if not o[a] < lev:
                    continue
                tocca = h[a:js] >= lev
                oltre = c[a:js] > lev
            else:
                if not o[a] > lev:
                    continue
                tocca = l[a:js] <= lev
                oltre = c[a:js] < lev
            if tocca.any():
                j = a + int(tocca.argmax())
                if j + 1 < b:
                    out["TS"].append((q, j + 1, b - 1, lato))
                    out["TR"].append((q, j + 1, b - 1, -lato))
            if oltre.any():
                j = a + int(oltre.argmax())
                if j + 1 < b:
                    out["CS"].append((q, j + 1, b - 1, lato))
                rientra = (c[j + 1:js] < lev) if lato > 0 else (c[j + 1:js] > lev)
                if rientra.any():
                    j2 = j + 1 + int(rientra.argmax())
                    if j2 + 1 < b:
                        out["FR"].append((q, j2 + 1, b - 1, -lato))
    return {r: pd.DataFrame(v, columns=["q", "e", "z", "d"]) for r, v in out.items()}


# ------------------------------------------------------------- statistiche
def statistiche(net, alt, anni, netp, costo, rng_seed=SEED):
    n = len(net)
    if n < 2:
        return dict(n=n, netto_R=np.nan, t=np.nan, x_costo=np.nan, anni_pos=0, anni=0, p_placebo=np.nan, vinte=np.nan)
    m = net.mean()
    sd = net.std(ddof=1)
    tt = m / (sd / np.sqrt(n)) if sd > 0 else np.nan
    ys = pd.Series(net).groupby(anni).sum()
    rng = np.random.default_rng(rng_seed)
    lancio = rng.random((N_PLACEBO, n)) < 0.5
    pm = np.where(lancio, net[None, :], alt[None, :]).mean(1)
    p = (1 + (pm >= m).sum()) / (1 + N_PLACEBO)
    return dict(n=n, netto_R=m, t=tt, x_costo=netp.mean() / costo, anni_pos=int((ys > 0).sum()),
                anni=int(len(ys)), p_placebo=p, vinte=(net > 0).mean())


def valuta(sim, arr, sig, ses_date, regime, costo, tag, stops, uscite, righe, dett):
    """sig: DataFrame segnali (q,e,z,d,...); stops: {nome: funzione -> R}; uscite: {nome: funzione -> T}."""
    t, o, h, l, c = arr
    if len(sig) == 0:
        for sn in stops:
            for un in uscite:
                for rg in ("tutti", "piccolo", "grande"):
                    righe.append(dict(variante="|".join(tag + [sn, un, rg]), parte=tag[0], simbolo=sim,
                                      **statistiche(np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0), costo)))
        return
    e, z, d = sig.e.values, sig.z.values, sig.d.values
    q = sig.q.values
    reg = regime[q]
    anni = ses_date[q].year.values
    for sn, fs in stops.items():
        R = fs(sig)
        okr = np.isfinite(R) & (R >= MIN_R_COSTI * costo)
        for un, fu in uscite.items():
            T = fu(sig, R)
            ee, zz, dd, RR, TT = e[okr], z[okr], d[okr], R[okr], T[okr]
            g1 = simula(o, h, l, c, ee, zz, dd, RR, TT)
            g2 = simula(o, h, l, c, ee, zz, -dd, RR, TT)
            net = (g1 - costo) / RR
            alt = (g2 - costo) / RR
            netp = g1 - costo
            rr = reg[okr]
            yy = anni[okr]
            for rg in ("tutti", "piccolo", "grande"):
                m = np.ones(len(net), bool) if rg == "tutti" else (rr == rg)
                vid = "|".join(tag + [sn, un, rg])
                righe.append(dict(variante=vid, parte=tag[0], simbolo=sim,
                                  **statistiche(net[m], alt[m], yy[m], netp[m], costo)))
            dett.append(pd.DataFrame({"variante": "|".join(tag + [sn, un]), "data": ses_date[q[okr]],
                                      "dir": dd.astype(np.int8), "rischio": RR, "netto_R": net,
                                      "netto_R_opposto": alt, "regime": rr}))


# ------------------------------------------------------------------- main
def studia(sim, righe):
    d = carica(sim)
    fuso = controllo_fuso(sim, d)
    t = d.index.asi8
    arr = (t, d.open.values, d.high.values, d.low.values, d.close.values)
    g = giornaliero(d)
    costo = COSTO[sim]
    dett = []
    del d
    gc.collect()

    # ---------------- parte a: range di apertura
    if sim in METALLI:
        date = pd.DatetimeIndex(g.index)
        sess_a = {"LON": finestre_metalli(date, 7, 12), "NY": finestre_metalli(date, 12, 21)}
    else:
        sess_a = {"CASH": finestre_cash(sim, g.index[0], g.index[-1])}
    for sn, (s, f) in sess_a.items():
        i0, i1, ok = sessioni_valide(t, s, f, esatta=True)
        ses_date = s.tz_convert("UTC").floor("D")
        prev = info_giorno_prec(g, ses_date)
        for m in OR_MIN:
            sig, wr = segnali_orb(arr, s, f, i0, i1, ok, m)
            ratio = pd.Series(np.nan, index=np.arange(len(s)))
            ratio[wr.q.values] = wr.W.values / prev.atr.values[wr.q.values]
            rs = ratio.dropna()
            reg = np.full(len(s), "", dtype=object)
            reg[rs.index.values] = terzili_causali(rs).values
            stops_r = {"S1": lambda x: np.where(x.d > 0, (arr[1][x.e] - x.L), (x.H - arr[1][x.e])).astype(float),
                       "S2": lambda x: np.where(x.d > 0, arr[1][x.e] - (x.H + x.L) / 2,
                                                (x.H + x.L) / 2 - arr[1][x.e]).astype(float)}
            stops_f = {"S1": lambda x: np.where(x.d > 0, arr[1][x.e] - x.ext, x.ext - arr[1][x.e]).astype(float),
                       "S2": lambda x: np.where(x.d > 0, arr[1][x.e] - (x.L - 0.5 * x.W),
                                                (x.H + 0.5 * x.W) - arr[1][x.e]).astype(float)}
            usc_r = {"E0": lambda x, R: np.full(len(x), np.inf), "E1": lambda x, R: 1.0 * x.W.values,
                     "E2": lambda x, R: 2.0 * x.W.values}
            usc_f = {"E0": lambda x, R: np.full(len(x), np.inf), "E1": lambda x, R: 0.5 * x.W.values,
                     "E2": lambda x, R: 1.0 * x.W.values}
            valuta(sim, arr, sig["ROTTURA"], ses_date, reg, costo, ["a", sim, sn, f"OR{m}", "ROTTURA"],
                   stops_r, usc_r, righe, dett)
            valuta(sim, arr, sig["RIENTRO"], ses_date, reg, costo, ["a", sim, sn, f"OR{m}", "RIENTRO"],
                   stops_f, usc_f, righe, dett)

    # ---------------- parte b: livelli precedenti
    if sim in METALLI:
        date = pd.DatetimeIndex(g.index)
        combos = {}
        s, f = finestre_metalli(date, 7, 21)
        combos["GP"] = (s, f, None)
        combos["ASIA>LON"] = (*finestre_metalli(date, 7, 12), finestre_metalli(date, 0, 7))
        combos["LON>NY"] = (*finestre_metalli(date, 12, 21), finestre_metalli(date, 7, 12))
    else:
        s, f = finestre_cash(sim, g.index[0], g.index[-1])
        combos = {"GP": (s, f, None), "SP": (s, f, "cash")}
    for cn, (s, f, lev) in combos.items():
        i0, i1, ok = sessioni_valide(t, s, f, esatta=False)
        ses_date = s.tz_convert("UTC").floor("D")
        prev = info_giorno_prec(g, ses_date)
        reg_ser = terzili_causali(pd.Series(prev.prng.values / prev.atr.values))
        reg = reg_ser.values.astype(object)
        if lev is None:
            H, Lv = prev.pdh.values, prev.pdl.values
        elif lev == "cash":
            H = np.full(len(s), np.nan)
            Lv = np.full(len(s), np.nan)
            hv, lv = arr[2], arr[3]
            val = np.flatnonzero(ok)
            for a_, b_ in zip(val[:-1], val[1:]):
                H[b_] = hv[i0[a_]:i1[a_]].max()
                Lv[b_] = lv[i0[a_]:i1[a_]].min()
        else:
            ps, pf = lev
            j0, j1, okp = sessioni_valide(t, ps, pf, esatta=False)
            H = np.full(len(s), np.nan)
            Lv = np.full(len(s), np.nan)
            for qq in np.flatnonzero(okp):
                H[qq] = arr[2][j0[qq]:j1[qq]].max()
                Lv[qq] = arr[3][j0[qq]:j1[qq]].min()
        atr = prev.atr.values
        sig = segnali_livelli(arr, s, f, i0, i1, ok, H, Lv)
        stops = {"K10": lambda x: 0.10 * atr[x.q.values], "K25": lambda x: 0.25 * atr[x.q.values]}
        usc = {"E0": lambda x, R: np.full(len(x), np.inf), "E1": lambda x, R: 1.0 * R,
               "E2": lambda x, R: 2.0 * R}
        for rn, sg in sig.items():
            valuta(sim, arr, sg, ses_date, reg, costo, ["b", sim, cn, rn], stops, usc, righe, dett)

    pd.concat(dett, ignore_index=True).to_parquet(RISULTATI / f"f3_dettaglio_{sim}.parquet", index=False)
    del dett, arr, t, g
    gc.collect()
    return fuso


def main():
    RISULTATI.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)
    righe = []
    for sim in SIMBOLI:
        fuso = studia(sim, righe)
        print(f"{sim}: picco volatilita' UTC {fuso}", file=sys.stderr)
    r = pd.DataFrame(righe)
    r["anni_frac"] = r.anni_pos / r.anni.where(r.anni > 0)
    r["passa"] = ((r.netto_R > 0) & (r.t >= 3) & (r.anni_frac >= 0.75) & (r.p_placebo < 0.01) & (r.n >= 100))
    r.to_parquet(RISULTATI / "f3_varianti.parquet", index=False)
    print(f"varianti valutate: {len(r)}  (con n>=100: {(r.n >= 100).sum()})")
    for k, cond in {"netto>0": r.netto_R > 0, "t>=3": r.t >= 3, "anni>=75%": r.anni_frac >= 0.75,
                    "p<0.01": r.p_placebo < 0.01, "TUTTI": r.passa}.items():
        print(f"  {k:10s} {int(cond.sum())}")
    cols = ["variante", "n", "netto_R", "x_costo", "t", "anni_pos", "anni", "p_placebo", "vinte", "passa"]
    print(r.sort_values("t", ascending=False)[cols].head(15).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
