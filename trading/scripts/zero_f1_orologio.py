"""Ricerca da zero, famiglia 1: orologio e sessioni (solo periodo di scoperta).

Protocollo: docs/ricerca-da-zero-registrazione.md. Varianti dichiarate prima del
calcolo in docs/studies/zero/f1-orologio.md (732).

Legge SOLO D:\\ricerca_zero\\scoperta\\<SIMBOLO>_<TF>.parquet (indice UTC
all'apertura). Un mercato alla volta. Salva il dettaglio in
D:\\ricerca_zero\\risultati\\f1_*.parquet e stampa solo aggregati compatti.

Convenzioni: entrata = apertura della prima candela M5 con inizio >= istante di
entrata (entro 15 min); uscita = chiusura dell'ultima candela M5 che termina
entro l'istante d'uscita (entro 15 min). I segnali usano solo chiusure di
candele che terminano entro l'istante d'entrata. Netto = direzione*movimento -
costo round trip (unita' di prezzo).
"""
import gc
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

SRC = r"D:\ricerca_zero\scoperta"
OUT = r"D:\ricerca_zero\risultati"
COST = {"XAUUSD": 0.40, "SPXUSD": 0.55, "NSXUSD": 1.50, "GRXEUR": 1.50, "XAGUSD": 0.025}
MKTS = ["XAUUSD", "XAGUSD", "SPXUSD", "NSXUSD", "GRXEUR"]
MIN = 60 * 10**9
TOL = 15 * MIN
BAR = 5 * MIN
NY, BER = ZoneInfo("America/New_York"), ZoneInfo("Europe/Berlin")
CASH = {"SPXUSD": (NY, (9, 30), (16, 0)), "NSXUSD": (NY, (9, 30), (16, 0)),
        "GRXEUR": (BER, (9, 0), (17, 30))}
UTC_SESS = {"Asia": (0, 7), "Londra": (7, 12), "NY": (12, 21)}
N_PLACEBO = 1000
SEED = 20261002
pd.set_option("display.width", 200)
# Le serie HistData in scoperta hanno l'etichetta UTC = ora di New York + 5 h
# fissa: quando New York e' in ora legale sono 1 ora IN RITARDO. Prove: il
# picco d'apertura DAX cade alle 09:00 "UTC" nelle settimane in cui gli USA sono
# gia' in ora legale e l'Europa no (08:00 vero); S&P/Nasdaq mostrano l'apertura
# alle 14:30 tutto l'anno; dopo la correzione la riapertura domenicale cade alle
# 22:00 UTC d'estate (18:00 New York). Dukascopy (oro) e' gia' corretto.
HISTDATA = {"SPXUSD", "NSXUSD", "XAGUSD", "GRXEUR"}


def correggi_ora(df, mkt):
    if mkt not in HISTDATA:
        return df
    wall = df.index.tz_localize(None) - pd.Timedelta(hours=5)
    vero = wall.tz_localize(NY, ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
    df = df.set_axis(vero)
    df = df[df.index.notna()]
    return df[~df.index.duplicated()].sort_index()


class Px:
    """Accesso puntuale ai prezzi M5 (tempi in ns UTC)."""

    def __init__(self, df):
        self.t = df.index.as_unit("ns").asi8
        self.o = df["open"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.n = len(self.t)

    def oa(self, T):
        i = np.searchsorted(self.t, T, "left")
        ok = i < self.n
        i = np.minimum(i, self.n - 1)
        ok &= (self.t[i] - T) < TOL
        return i, ok

    def cb(self, T):
        j = np.searchsorted(self.t, T, "left") - 1
        ok = j >= 0
        j = np.maximum(j, 0)
        ok &= (T - (self.t[j] + BAR)) < TOL
        return j, ok

    def move(self, Ta, Tb):
        """Apertura a Ta -> chiusura entro Tb. Ritorna movimento, prezzo, ok."""
        i, oki = self.oa(Ta)
        j, okj = self.cb(Tb)
        ok = oki & okj & (j >= i)
        m = np.where(ok, self.c[j] - self.o[i], np.nan)
        return m, np.where(ok, self.o[i], np.nan), ok

    def move_oo(self, Ta, Tb):
        """Apertura a Ta -> apertura a Tb (notte: si esce sul primo prezzo cash)."""
        i, oki = self.oa(Ta)
        j, okj = self.oa(Tb)
        ok = oki & okj & (j > i)
        m = np.where(ok, self.o[j] - self.o[i], np.nan)
        return m, np.where(ok, self.o[i], np.nan), ok

    def sig_oc(self, Ta, Tb):
        """Segnale apertura a Ta -> chiusura entro Tb."""
        return self.move(Ta, Tb)[0]

    def sig_cc(self, Ta, Tb):
        """Segnale chiusura entro Ta -> chiusura entro Tb."""
        ia, oka = self.cb(Ta)
        jb, okb = self.cb(Tb)
        ok = oka & okb & (jb > ia)
        return np.where(ok, self.c[jb] - self.c[ia], np.nan)


def local_times(days, tz, hm):
    naive = pd.DatetimeIndex(days) + pd.Timedelta(hours=hm[0], minutes=hm[1])
    return naive.tz_localize(tz).tz_convert("UTC").as_unit("ns").asi8


# ---------------------------------------------------------------- statistiche
RES, KEEP = [], {}


def record(blocco, mkt, nome, m, d, price, ts):
    """m movimento grezzo, d direzione (+1/-1/0), ts tempi d'entrata (ns)."""
    sel = np.isfinite(m) & (d != 0) & np.isfinite(price)
    m, d, price, ts = m[sel], d[sel].astype(float), price[sel], ts[sel]
    cost = COST[mkt]
    vid = len(RES)
    row = dict(id=vid, blocco=blocco, mercato=mkt, variante=nome, n=int(len(m)))
    if len(m) < 30:
        RES.append(row)
        return
    net = d * m - cost
    mu, sd = net.mean(), net.std(ddof=1)
    yrs = pd.to_datetime(ts, utc=True).year
    ys = pd.Series(net).groupby(np.asarray(yrs)).sum()
    row.update(lordo=(d * m).mean(), netto=mu, netto_costi=mu / cost,
               netto_bp=(net / price).mean() * 1e4, t=mu / sd * np.sqrt(len(m)),
               t_lordo=(d * m).mean() / sd * np.sqrt(len(m)),
               anni_pos=int((ys > 0).sum()), anni=int(len(ys)), p=np.nan)
    if mu > 0:  # placebo: stessi istanti, direzione casuale
        rng = np.random.default_rng(SEED + vid)
        hits = 0
        for _ in range(N_PLACEBO // 200):
            s = rng.choice(np.array([-1.0, 1.0]), size=(200, len(m)))
            hits += int(((s * m).mean(1) - cost >= mu).sum())
        row["p"] = (1 + hits) / (1 + N_PLACEBO)
    if row["t"] >= 2:
        KEEP[vid] = pd.DataFrame(dict(ts=pd.to_datetime(ts, utc=True), dir=d,
                                      mov=m, prezzo=price, netto=net))
    RES.append(row)


# ---------------------------------------------------------------- descrittive
DESC_H, DESC_WH, DESC_LOC = [], [], []


def descrittive(mkt, h1, m5):
    cost = COST[mkt]
    r = (h1["close"] - h1["open"]) / h1["open"] * 1e4
    rng_ = h1["high"] - h1["low"]
    g = pd.DataFrame(dict(r=r, rng=rng_, h=h1.index.hour, wd=h1.index.dayofweek))
    tot_var = (g.r ** 2).sum()
    a = g.groupby("h").agg(n=("r", "size"), media_bp=("r", "mean"), sd_bp=("r", "std"),
                           escursione=("rng", "mean"))
    a["t"] = a.media_bp / a.sd_bp * np.sqrt(a.n)
    a["escursione_costi"] = a.escursione / cost
    a["quota_var"] = g.groupby("h").r.apply(lambda x: (x ** 2).sum()) / tot_var
    a["mercato"] = mkt
    DESC_H.append(a.reset_index())
    w = g.groupby(["wd", "h"]).r.agg(["size", "mean", "std"])
    w = w[w["size"] >= 50]
    w["t"] = w["mean"] / w["std"] * np.sqrt(w["size"])
    w["mercato"] = mkt
    DESC_WH.append(w.reset_index())
    if mkt in CASH:
        tz = CASH[mkt][0]
        loc = m5.index.tz_convert(tz)
        b = (loc.hour * 60 + loc.minute) // 30 * 30
        x = pd.DataFrame(dict(b=b, rng=(m5["high"] - m5["low"]).to_numpy()))
        q = x.groupby("b").rng.agg(["size", "mean"])
        q = q[q["size"] >= 1000].reset_index()
        q["ora_locale"] = q.b.map(lambda v: f"{v // 60:02d}:{v % 60:02d}")
        q["mercato"] = mkt
        DESC_LOC.append(q[["mercato", "ora_locale", "size", "mean"]])


# ---------------------------------------------------------------- regole
def sessioni(mkt, px, days_utc, days_loc):
    """Ritorna dict nome -> (S, E, giorni, prevE o None) in ns UTC."""
    out = {}
    for nm, (h0, h1) in UTC_SESS.items():
        if mkt == "GRXEUR" and nm == "Asia":
            continue
        S = days_utc.as_unit("ns").asi8 + h0 * 60 * MIN
        E = days_utc.as_unit("ns").asi8 + h1 * 60 * MIN
        out[nm] = (S, E, days_utc, None)
    if mkt in CASH:
        tz, a, b = CASH[mkt]
        S, E = local_times(days_loc, tz, a), local_times(days_loc, tz, b)
        # chiusura cash del giorno di borsa precedente valido (<= 4 giorni prima)
        _, okc = px.cb(E)
        idx = np.where(okc, np.arange(len(E)), -1)
        prev = np.maximum.accumulate(idx)
        prev = np.concatenate([[-1], prev[:-1]])
        gap_ok = prev >= 0
        pe = np.where(gap_ok, E[np.maximum(prev, 0)], 0)
        gap_ok &= (S - pe) < 4 * 24 * 60 * MIN
        pe = np.where(gap_ok, pe, S - 10**15)  # invalida
        out["cash"] = (S, E, days_loc, pe)
        out["notte"] = (pe, S, days_loc, None)
    return out


def regole(mkt, h1, px):
    cost = COST[mkt]
    first = px.t[0]
    d0 = pd.Timestamp(first, tz="UTC").normalize().tz_localize(None)
    d1 = pd.Timestamp(px.t[-1], tz="UTC").normalize().tz_localize(None)
    days_utc = pd.bdate_range(d0, d1).tz_localize("UTC")
    days_loc = pd.bdate_range(d0, d1)
    ss = sessioni(mkt, px, days_utc, days_loc)

    # R1: ora UTC, long e short (candela H1)
    m_all = (h1["close"] - h1["open"]).to_numpy()
    o_all = h1["open"].to_numpy()
    ts_all = h1.index.as_unit("ns").asi8
    hr = h1.index.hour
    for h in range(24):
        k = hr == h
        for dd, lab in ((1, "long"), (-1, "short")):
            record("R1", mkt, f"ora {h:02d} UTC {lab}", m_all[k], np.full(k.sum(), dd),
                   o_all[k], ts_all[k])

    # R2/R3: sessione intera long/short; R5: per giorno della settimana
    for nm, (S, E, days, _) in ss.items():
        m, p, ok = px.move_oo(S, E) if nm == "notte" else px.move(S, E)
        blk = "R3" if nm in ("cash", "notte") else "R2"
        wd = np.asarray(days.dayofweek)
        for dd, lab in ((1, "long"), (-1, "short")):
            record(blk, mkt, f"{nm} {lab}", m, np.full(len(m), dd), p, S)
            for w in range(5):
                k = wd == w
                record("R5", mkt, f"{nm} g{w} {lab}", m[k], np.full(k.sum(), dd), p[k], S[k])

    # R4a: persistenza primo tratto -> resto della sessione
    modi = {"segui": lambda s: s, "inverti": lambda s: -s,
            "segui solo long": lambda s: np.where(s > 0, 1, 0),
            "segui solo short": lambda s: np.where(s < 0, -1, 0),
            "inverti solo long": lambda s: np.where(s < 0, 1, 0),
            "inverti solo short": lambda s: np.where(s > 0, -1, 0)}
    for nm, (S, E, days, _) in ss.items():
        if nm == "notte":
            continue
        for L in (30, 60):
            SL = S + L * MIN
            f = px.sig_oc(S, SL)
            m, p, ok = px.move(SL, E)
            s = np.sign(np.nan_to_num(f))
            for mn, fn in modi.items():
                record("R4a", mkt, f"{nm} primi {L}m -> resto, {mn}", m, fn(s), p, SL)

    # R4b: prima mezz'ora (o notte+prima mezz'ora) -> ultima mezz'ora/ora (cash)
    if "cash" in ss:
        S, E, days, pe = ss["cash"]
        preds = {"prima 30m": px.sig_oc(S, S + 30 * MIN),
                 "notte+prima 30m": px.sig_oc(pe, S + 30 * MIN)}
        for pn, f in preds.items():
            s = np.sign(np.nan_to_num(f))
            for tl in (30, 60):
                m, p, ok = px.move(E - tl * MIN, E)
                for mn in ("segui", "inverti"):
                    record("R4b", mkt, f"{pn} -> ultimi {tl}m cash, {mn}", m,
                           s if mn == "segui" else -s, p, E - tl * MIN)

    # R4c: sessione precedente -> successiva
    pairs = [("Asia", "Londra"), ("Londra", "NY")]
    if "cash" in ss:
        pairs.append(("notte", "cash"))
    for a, b in pairs:
        if a not in ss or b not in ss:
            continue
        Sa, Ea = ss[a][0], ss[a][1]
        Sb, Eb = ss[b][0], ss[b][1]
        if a == "notte":  # segnale noto all'apertura cash: entrata alla candela dopo
            f = px.move_oo(Sa, Ea)[0]
            Sb = Sb + BAR
        else:
            f = px.sig_oc(Sa, Ea)
        m, p, ok = px.move(Sb, Eb)
        s = np.sign(np.nan_to_num(f))
        for mn in ("segui", "inverti"):
            record("R4c", mkt, f"{a} -> {b}, {mn}", m, s if mn == "segui" else -s, p, Sb)


def main():
    for mkt in MKTS:
        h1 = correggi_ora(pd.read_parquet(f"{SRC}\\{mkt}_H1.parquet"), mkt)
        m5 = correggi_ora(pd.read_parquet(f"{SRC}\\{mkt}_M5.parquet"), mkt)
        px = Px(m5)
        descrittive(mkt, h1, m5)
        regole(mkt, h1, px)
        del h1, m5, px
        gc.collect()
        print(f"{mkt}: fatto, varianti finora {len(RES)}", flush=True)

    res = pd.DataFrame(RES)
    res["anni_frac"] = res.anni_pos / res.anni
    res["passa"] = ((res.netto > 0) & (res.t >= 3) & (res.anni_frac >= 0.75)
                    & (res.p < 0.01) & (res.n >= 100))
    res.to_parquet(f"{OUT}\\f1_varianti.parquet")
    pd.concat(DESC_H).to_parquet(f"{OUT}\\f1_descrittive_ora.parquet")
    pd.concat(DESC_WH).to_parquet(f"{OUT}\\f1_giorno_ora.parquet")
    pd.concat(DESC_LOC).to_parquet(f"{OUT}\\f1_escursione_ora_locale.parquet")
    tr = [v.assign(id=k) for k, v in KEEP.items()]
    if tr:
        pd.concat(tr).to_parquet(f"{OUT}\\f1_operazioni_t2.parquet")

    cols = ["id", "blocco", "mercato", "variante", "n", "netto", "netto_costi",
            "netto_bp", "t", "anni_pos", "anni", "p", "passa"]
    print("\nvarianti totali:", len(res), "| per blocco:", res.blocco.value_counts().to_dict())
    print("calcolabili (n>=30):", int(res.t.notna().sum()), "| passano:", int(res.passa.sum()))
    print("\nmigliori 10 per t:")
    print(res.sort_values("t", ascending=False)[cols].head(10).round(3).to_string(index=False))
    # quante con |t|>=3 rispetto all'atteso per caso (normale, due code 0,27%)
    nt = int(res.t.notna().sum())
    print(f"\nt netto>=3: {int((res.t >= 3).sum())} su {nt}; |t lordo|>=3: "
          f"{int((res.t_lordo.abs() >= 3).sum())} (atteso per caso ~{nt * 0.0027:.1f}; "
          f"ogni effetto conta due volte, long e short)")


if __name__ == "__main__":
    main()
