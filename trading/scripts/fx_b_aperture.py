"""Famiglia 2 FX — Aperture di sessione (scoperta 2010-2017).

Protocollo: docs/fx-intraday-registrazione.md. Rapporto: docs/studies/fx/b-aperture.md
Dati: SOLO D:\\ricerca_fx\\scoperta\\<COPPIA>_<M5|D1>.parquet (BID, indice UTC all'apertura).

Uso:
  python fx_b_aperture.py controlli   # fusi orari + motore vettoriale vs ciclo
  python fx_b_aperture.py simula      # una coppia alla volta -> dettaglio per operazione
  python fx_b_aperture.py aggrega     # 1080 regole x 7 coppie + aggregati, placebo
  python fx_b_aperture.py             # tutto
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)

SCOP = Path(r"D:\ricerca_fx\scoperta")
RIS = Path(r"D:\ricerca_fx\risultati")
COPPIE = ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "EURJPY"]
COSTO = {"EURUSD": 0.8, "GBPUSD": 1.0, "AUDUSD": 0.9, "USDCHF": 1.0,
         "USDCAD": 1.2, "USDJPY": 1.2, "EURJPY": 1.4}
ANNI = list(range(2010, 2018))
NPLACEBO = 1000
SEED = 12345
M5 = 300 * 10**9  # 5 minuti in ns
LON, NY, UTC = "Europe/London", "America/New_York", "UTC"

# setup: (parte, tipo, inizio range/ora, fine range/ora, inizio finestra, fine finestra, uscite a tempo)
# orari: (fuso, ora, minuto); 'UP' = UTC del giorno prima
SETUP = {
    "A1": ("a", "range", (LON, 0, 0), (LON, 7, 0), (LON, 7, 0), (LON, 8, 0),
           {"E0": (LON, 16, 0), "E2045": (UTC, 20, 45)}),
    "A2": ("a", "range", ("UP", 22, 15), (LON, 8, 0), (LON, 8, 0), (LON, 9, 0),
           {"E0": (LON, 16, 0), "E2045": (UTC, 20, 45)}),
    "B1": ("b", "range", (LON, 8, 0), (NY, 8, 0), (NY, 8, 0), (NY, 9, 30),
           {"E0": (UTC, 20, 45)}),
    "B2": ("b", "range", (LON, 8, 0), (NY, 9, 30), (NY, 9, 30), (NY, 10, 30),
           {"E0": (UTC, 20, 45)}),
    "CL": ("c", "ora", (LON, 8, 0), (LON, 9, 0), None, None, {"E0": (LON, 16, 0)}),
    "CN1": ("c", "ora", (NY, 8, 0), (NY, 9, 0), None, None, {"E0": (UTC, 20, 45)}),
    "CN2": ("c", "ora", (NY, 9, 30), (NY, 10, 30), None, None, {"E0": (UTC, 20, 45)}),
}
REGOLE = {"range": ["ROTTURA", "RIENTRO"], "ora": ["SEGUI", "CONTRO"]}
STOP = ["S1", "S2", "S3"]
OBIETTIVI = ["1R", "2R", "RNG"]
REGIMI = ["tutti", "piccolo", "grande"]
GIORNI = ["tutti", "mar-gio"]


def pip(c):
    return 0.01 if "JPY" in c else 0.0001


def carica(c):
    m = pd.read_parquet(SCOP / f"{c}_M5.parquet")
    d = pd.read_parquet(SCOP / f"{c}_D1.parquet")
    return m, d


def atr14(d):
    """ATR14 causale: per una data D usa i 14 giorni UTC validi (>=600 minuti) prima di D."""
    d = d[d["minuti"] >= 600].copy()
    pc = d["close"].shift(1)
    tr = np.maximum(d["high"] - d["low"], np.maximum((d["high"] - pc).abs(), (d["low"] - pc).abs()))
    roll = tr.rolling(14).mean()
    giorni = d.index.tz_convert(None).normalize()
    return giorni.values.astype("datetime64[ns]"), roll.values, len(d)


def istanti(date, spec):
    tz, h, mi = spec
    if tz == "UP":
        naive = date - pd.Timedelta(days=1) + pd.Timedelta(hours=h, minutes=mi)
        return naive.tz_localize(UTC).as_unit("ns").asi8
    naive = date + pd.Timedelta(hours=h, minutes=mi)
    return naive.tz_localize(tz).tz_convert(UTC).as_unit("ns").asi8


# ---------------------------------------------------------------- motore
def simula_vett(o, h, l, c, j0, jend, d, risk, tgt):
    """Lordo in prezzo per operazioni entrate all'apertura della barra j0, uscita forzata
    alla chiusura di jend. Stop prevale; apertura oltre lo stop = uscita all'apertura;
    obiettivo limite senza miglioramento. tgt = nan -> nessun obiettivo."""
    n = len(j0)
    if n == 0:
        return np.zeros(0)
    L = int((jend - j0).max()) + 1
    off = np.arange(L)
    idx = np.minimum(j0[:, None] + off[None, :], len(o) - 1)
    valid = off[None, :] <= (jend - j0)[:, None]
    e = o[j0][:, None]
    dd = d[:, None]
    H, Lo, O = h[idx], l[idx], o[idx]
    adv = np.where(dd > 0, e - Lo, H - e)
    fav = np.where(dd > 0, H - e, e - Lo)
    oadv = np.where(dd > 0, e - O, O - e)
    sh = (adv >= risk[:, None]) & valid
    with np.errstate(invalid="ignore"):
        th = (fav >= tgt[:, None]) & valid
    BIG = L + 10
    js = np.where(sh.any(1), sh.argmax(1), BIG)
    jt = np.where(th.any(1), th.argmax(1), BIG)
    fin = d * (c[jend] - o[j0])
    oa = oadv[np.arange(n), np.minimum(js, L - 1)]
    pnl_stop = -np.maximum(risk, oa)
    out = np.where((js < BIG) & (js <= jt), pnl_stop, np.where(jt < BIG, tgt, fin))
    return out


def simula_ciclo(o, h, l, c, j0, jend, d, risk, tgt):
    """Controllo indipendente candela per candela, con livelli di prezzo."""
    out = []
    for k in range(len(j0)):
        e = o[j0[k]]
        st = e - d[k] * risk[k]
        tp = None if np.isnan(tgt[k]) else e + d[k] * tgt[k]
        res = None
        for j in range(j0[k], jend[k] + 1):
            if d[k] > 0:
                if l[j] <= st:
                    px = o[j] if (j > j0[k] and o[j] < st) else st
                    res = px - e
                elif tp is not None and h[j] >= tp:
                    res = tp - e
            else:
                if h[j] >= st:
                    px = o[j] if (j > j0[k] and o[j] > st) else st
                    res = e - px
                elif tp is not None and l[j] <= tp:
                    res = e - tp
            if res is not None:
                break
        if res is None:
            res = d[k] * (c[jend[k]] - e)
        out.append(res)
    return np.array(out)


# ---------------------------------------------------------------- segnali
def genera(c, m, dd):
    """Per una coppia: lista di operazioni base (setup, regola, giorno) con i tre stop."""
    T = m.index.as_unit("ns").asi8
    o, h, l, cl = (m[k].to_numpy() for k in ("open", "high", "low", "close"))
    pp = pip(c)
    costo = COSTO[c]
    adate, aval, ngiorni = atr14(dd)
    first = m.index[0].tz_convert(LON).normalize().tz_localize(None)
    last = m.index[-1].tz_convert(LON).normalize().tz_localize(None)
    date = pd.date_range(first, last, freq="D")
    date = date[date.dayofweek < 5]
    dn = date.values.astype("datetime64[ns]")
    ia = np.searchsorted(adate, dn, "left") - 1
    atr = np.where(ia >= 13, aval[np.clip(ia, 0, None)], np.nan)
    t2045 = istanti(date, (UTC, 20, 45))
    S = lambda t: np.searchsorted(T, t, "left")
    righe = []
    for sid, (parte, tipo, rs, re_, ws, we, fini) in SETUP.items():
        t_rs, t_re = istanti(date, rs), istanti(date, re_)
        i_rs, i_re = S(t_rs), S(t_re)
        attese = (t_re - t_rs) // M5
        okr = (i_re - i_rs) >= 0.8 * attese
        fine_idx = {}
        for k, spec in fini.items():
            tf = np.minimum(istanti(date, spec), t2045)
            fine_idx[k] = S(tf) - 1  # ultima barra che apre prima della fine
        jE0 = fine_idx["E0"]
        if tipo == "range":
            i_ws, i_we = S(istanti(date, ws)), S(istanti(date, we))
        # regime: rapporto range/ATR sui giorni validi, terzili dei 250 precedenti
        ratio = np.full(len(date), np.nan)
        hi_a = np.full(len(date), np.nan)
        lo_a = np.full(len(date), np.nan)
        for g in np.nonzero(okr & (i_re > i_rs))[0]:
            hi_a[g] = h[i_rs[g]:i_re[g]].max()
            lo_a[g] = l[i_rs[g]:i_re[g]].min()
        ratio = (hi_a - lo_a) / atr
        rs_ = pd.Series(ratio).dropna()
        q1 = rs_.shift(1).rolling(250, min_periods=60).quantile(1 / 3)
        q2 = rs_.shift(1).rolling(250, min_periods=60).quantile(2 / 3)
        reg = np.full(len(date), -9, dtype=np.int8)
        rv = rs_.values
        lab = np.where(q1.isna(), -9, np.where(rv <= q1.values, -1, np.where(rv >= q2.values, 1, 0)))
        reg[rs_.index.values] = lab
        for g in np.nonzero(~np.isnan(ratio))[0]:
            hi, lo = hi_a[g], lo_a[g]
            rng = hi - lo
            if rng <= 0 or np.isnan(atr[g]):
                continue
            if tipo == "range":
                br, bdir = None, 0
                for i in range(i_ws[g], i_we[g]):
                    if cl[i] > hi:
                        br, bdir = i, 1
                        break
                    if cl[i] < lo:
                        br, bdir = i, -1
                        break
                if br is None:
                    continue
                cand = []
                # ROTTURA
                cand.append(("ROTTURA", br, bdir, None))
                # RIENTRO
                for k in range(br + 1, min(br + 13, len(cl))):
                    if T[k] - T[br] > 12 * M5:
                        break
                    if lo <= cl[k] <= hi:
                        ext = h[br:k + 1].max() if bdir > 0 else l[br:k + 1].min()
                        cand.append(("RIENTRO", k, -bdir, ext))
                        break
            else:
                a, b = i_rs[g], i_re[g]
                if cl[b - 1] == o[a]:
                    continue
                hdir = 1 if cl[b - 1] > o[a] else -1
                cand = [("SEGUI", b - 1, hdir, None), ("CONTRO", b - 1, -hdir, hi if hdir > 0 else lo)]
            for regola, isig, dr, ext in cand:
                j = isig + 1
                if j >= len(T) or T[j] - (T[isig] + M5) > 3 * M5 or j > jE0[g]:
                    continue
                mod = ((T[j] // 60_000_000_000) % 1440)
                if 20 * 60 + 45 <= mod < 22 * 60 + 15:
                    continue
                mult = 2.0 if mod >= 22 * 60 + 15 else 1.0
                e = o[j]
                mid = (hi + lo) / 2
                if regola in ("ROTTURA", "SEGUI"):
                    s1 = e - lo if dr > 0 else hi - e
                    s2 = dr * (e - mid)
                else:
                    # dr e' la direzione dell'operazione (contro la rottura / l'ora)
                    s1 = (e - ext) if dr > 0 else (ext - e)
                    lato = lo - 0.5 * rng if dr > 0 else hi + 0.5 * rng
                    s2 = (e - lato) if dr > 0 else (lato - e)
                s3 = 0.25 * atr[g]
                righe.append((sid, parte, regola, g, j, dr, s1, s2, s3, rng, mult, reg[g]))
    base = pd.DataFrame(righe, columns=["setup", "parte", "regola", "g", "j", "dir", "S1", "S2", "S3",
                                        "rng", "mult", "regime"])
    base["data"] = date[base["g"].values]
    # indici di fine per ogni operazione
    ends = {}
    for sid, (_, _, _, _, _, _, fini) in SETUP.items():
        for k, spec in fini.items():
            tf = np.minimum(istanti(date, spec), t2045)
            ends[(sid, k)] = S(tf) - 1
    base["jE0"] = [ends[(s, "E0")][g] for s, g in zip(base["setup"], base["g"])]
    base["jE2045"] = [ends[(s, "E2045")][g] if (s, "E2045") in ends else -1
                      for s, g in zip(base["setup"], base["g"])]
    return base, (o, h, l, cl), ngiorni


def dettaglio_coppia(c):
    t0 = time.time()
    m, dd = carica(c)
    base, (o, h, l, cl), ngiorni = genera(c, m, dd)
    pp = pip(c)
    costo = COSTO[c]
    out = []
    for (sid, regola), b in base.groupby(["setup", "regola"], sort=False):
        parte = SETUP[sid][0]
        uscite = ["E0", "E2045"] if parte == "a" else ["E0"]
        j0 = b["j"].to_numpy()
        d = b["dir"].to_numpy()
        for st in STOP:
            risk = b[st].to_numpy()
            ok = (risk >= 2 * costo * pp) & np.isfinite(risk)
            if not ok.any():
                continue
            bb = b[ok]
            r, jj, dv = risk[ok], j0[ok], d[ok]
            for ex in uscite + OBIETTIVI:
                if ex in ("E0", "E2045"):
                    je = bb["j" + ex].to_numpy()
                    tg = np.full(len(r), np.nan)
                else:
                    je = bb["jE0"].to_numpy()
                    tg = {"1R": r, "2R": 2 * r, "RNG": bb["rng"].to_numpy()}[ex]
                g1 = simula_vett(o, h, l, cl, jj, je, dv, r, tg) / pp
                g2 = simula_vett(o, h, l, cl, jj, je, -dv, r, tg) / pp
                out.append(pd.DataFrame({
                    "coppia": c, "parte": parte, "setup": sid, "regola": regola, "stop": st, "uscita": ex,
                    "data": bb["data"].values, "dir": dv.astype(np.int8),
                    "rischio_pip": (r / pp).astype(np.float32), "lordo_pip": g1.astype(np.float32),
                    "lordo_opp_pip": g2.astype(np.float32),
                    "costo_pip": (costo * bb["mult"].to_numpy()).astype(np.float32),
                    "regime": bb["regime"].to_numpy().astype(np.int8),
                }))
    det = pd.concat(out, ignore_index=True)
    for k in ("coppia", "parte", "setup", "regola", "stop", "uscita"):
        det[k] = det[k].astype("category")
    det.to_parquet(RIS / f"fx_b_dettaglio_{c}.parquet")
    nb = len(base)
    print(f"{c}: operazioni base {nb}, righe dettaglio {len(det)}, giornate {ngiorni}, {time.time()-t0:.0f}s")
    return ngiorni


# ---------------------------------------------------------------- statistiche
def placebo_p(Rr, Ro, rng_seed=SEED):
    """p sul netto medio in R: direzione casuale per operazione, stessa gestione speculare."""
    n = len(Rr)
    rng = np.random.default_rng(rng_seed)
    nbytes = (NPLACEBO * n + 7) // 8
    bits = np.unpackbits(np.frombuffer(rng.bytes(nbytes), np.uint8))[:NPLACEBO * n]
    bits = bits.reshape(NPLACEBO, n).astype(np.float32)
    diff = (Rr - Ro).astype(np.float32)
    pm = (Ro.sum() + bits @ diff) / n
    return (1 + (pm >= Rr.mean() - 1e-12).sum()) / (NPLACEBO + 1)


def stats(df, ngiorni_tot, con_placebo=True):
    n = len(df)
    if n < 2:
        return None
    rp = df["rischio_pip"].to_numpy(np.float64)
    gp = df["lordo_pip"].to_numpy(np.float64)
    go = df["lordo_opp_pip"].to_numpy(np.float64)
    cp = df["costo_pip"].to_numpy(np.float64)
    net = gp - cp
    R = net / rp
    R15 = (gp - 1.5 * cp) / rp
    Ro = (go - cp) / rp
    sd = R.std(ddof=1)
    t = R.mean() / (sd / np.sqrt(n)) if sd > 0 else 0.0
    anno = df["data"].dt.year.to_numpy()
    yr = pd.Series(R).groupby(anno).sum()
    anni_pos = int(sum(yr.get(a, 0) > 0 for a in ANNI))
    res = dict(n=n, op_giorno=n / ngiorni_tot, lordo_R=(gp / rp).mean(), netto_pip=net.mean(),
               netto_R=R.mean(), netto_costo=(net / cp).mean(), t=t, anni_pos=anni_pos,
               netto_R_x15=R15.mean(), netto_pip_x15=(gp - 1.5 * cp).mean(), costo_R=(cp / rp).mean())
    res["p"] = placebo_p(R, Ro) if con_placebo else np.nan
    return res


def aggrega():
    t0 = time.time()
    giorni = {}
    for c in COPPIE:
        _, dd = carica(c)
        giorni[c] = int(((dd["minuti"] >= 600) & (dd.index.dayofweek < 5)).sum())
    det = pd.concat([pd.read_parquet(RIS / f"fx_b_dettaglio_{c}.parquet") for c in COPPIE], ignore_index=True)
    for k in ("coppia", "parte", "setup", "regola", "stop", "uscita"):
        det[k] = det[k].astype(str).astype("category")
    det["mg"] = det["data"].dt.dayofweek.isin([1, 2, 3])
    righe = []
    for (sid, regola, st, ex), b in det.groupby(["setup", "regola", "stop", "uscita"], observed=True, sort=True):
        for reg in REGIMI:
            br = b if reg == "tutti" else b[b["regime"] == (-1 if reg == "piccolo" else 1)]
            for gg in GIORNI:
                bg = br if gg == "tutti" else br[br["mg"]]
                nome = f"{SETUP[sid][0]} {sid} {regola} {st} {ex} {reg} {gg}"
                pos = []
                for c, bc in bg.groupby("coppia", observed=True):
                    s = stats(bc, giorni[c])
                    if s is None:
                        continue
                    s.update(variante=nome, parte=SETUP[sid][0], setup=sid, regola=regola, stop=st,
                             uscita=ex, regime=reg, giorni=gg, coppia=c)
                    righe.append(s)
                    if s["netto_R"] > 0:
                        pos.append(c)
                if pos:
                    bp = bg[bg["coppia"].isin(pos)]
                    s = stats(bp, 1)
                    s["op_giorno"] = sum((bg["coppia"] == c).sum() / giorni[c] for c in pos)
                    s.update(variante=nome, parte=SETUP[sid][0], setup=sid, regola=regola, stop=st,
                             uscita=ex, regime=reg, giorni=gg, coppia="POS:" + ",".join(sorted(pos)))
                    righe.append(s)
    v = pd.DataFrame(righe)
    v["aggregato"] = v["coppia"].str.startswith("POS:")
    v.to_parquet(RIS / "fx_b_varianti.parquet")
    print(f"aggregazione {time.time()-t0:.0f}s")
    return v


def promuovi(v):
    a = v[v["aggregato"]].copy()
    a["passa"] = ((a["netto_R"] > 0) & (a["netto_R_x15"] > 0) & (a["t"] >= 3) & (a["anni_pos"] >= 6)
                  & (a["p"] < 0.01) & (a["op_giorno"] >= 1))
    return a


def riepilogo(v):
    pc = v[~v["aggregato"]]
    a = promuovi(v)
    print(f"regole: {v['variante'].nunique()}  varianti per coppia: {len(pc)}  aggregati: {len(a)}")
    print("per coppia: netto>0", int((pc.netto_R > 0).sum()), " t>=3", int((pc.t >= 3).sum()),
          " t<=-3", int((pc.t <= -3).sum()), " anni>=6", int((pc.anni_pos >= 6).sum()),
          " p<0,01", int((pc.p < 0.01).sum()))
    print("aggregati: netto>0 x1,5", int((a.netto_R_x15 > 0).sum()), " t>=3", int((a.t >= 3).sum()),
          " anni>=6", int((a.anni_pos >= 6).sum()), " p<0,01", int((a.p < 0.01).sum()),
          " freq>=1", int((a.op_giorno >= 1).sum()), " PASSANO", int(a.passa.sum()))
    cols = ["variante", "coppia", "n", "op_giorno", "netto_pip", "netto_R", "netto_costo", "t", "anni_pos",
            "netto_R_x15", "p"]
    print("\nmigliori 12 aggregati per t:")
    print(a.sort_values("t", ascending=False)[cols].head(12).round(3).to_string(index=False))
    print("\nmigliori 12 aggregati per t con frequenza >= 1/giorno:")
    print(a[a.op_giorno >= 1].sort_values("t", ascending=False)[cols].head(12).round(3).to_string(index=False))


def diagnostica():
    """Lordo e netto della regola su TUTTE e 7 le coppie insieme (nessuna scelta delle coppie),
    regime e giorni = tutti. Solo diagnostica, non promuove nulla."""
    det = pd.concat([pd.read_parquet(RIS / f"fx_b_dettaglio_{c}.parquet") for c in COPPIE], ignore_index=True)
    det["lR"] = det["lordo_pip"] / det["rischio_pip"]
    det["nR"] = (det["lordo_pip"] - det["costo_pip"]) / det["rischio_pip"]
    det["lordo_pos"] = det["lordo_pip"]
    g = det.groupby(["setup", "regola", "stop", "uscita"], observed=True)
    d = g.agg(n=("lR", "size"), lordo_R=("lR", "mean"), sd_l=("lR", "std"), netto_R=("nR", "mean"),
              sd_n=("nR", "std"), costo_R=("costo_pip", "mean"), rischio_pip=("rischio_pip", "median"))
    d["t_lordo"] = d.lordo_R / (d.sd_l / np.sqrt(d.n))
    d["t_netto"] = d.netto_R / (d.sd_n / np.sqrt(d.n))
    # coppie con lordo > 0 (stessa regola base)
    pc = det.groupby(["setup", "regola", "stop", "uscita", "coppia"], observed=True)["lR"].mean()
    d["coppie_lordo_pos"] = (pc > 0).groupby(level=[0, 1, 2, 3]).sum()
    d = d.drop(columns=["sd_l", "sd_n", "costo_R"]).reset_index()
    d.to_parquet(RIS / "fx_b_lordo_diagnostica.parquet")
    cols = ["setup", "regola", "stop", "uscita", "n", "rischio_pip", "lordo_R", "t_lordo", "netto_R", "t_netto",
            "coppie_lordo_pos"]
    print("7 coppie insieme, migliori 10 per t lordo:")
    print(d.sort_values("t_lordo", ascending=False)[cols].head(10).round(3).to_string(index=False))
    print("peggiori 5 per t lordo:")
    print(d.sort_values("t_lordo")[cols].head(5).round(3).to_string(index=False))
    print("regole base con t_netto >= 2 su 7 coppie:", int((d.t_netto >= 2).sum()), "su", len(d))


def controlli():
    # 1) fusi: ora UTC della M5 piu' volatile (media |close-open|) in gennaio e luglio, EURUSD
    m, _ = carica("EURUSD")
    r = (m["close"] - m["open"]).abs()
    hh = m.index.hour * 100 + m.index.minute
    for mese in (1, 7):
        s = r[m.index.month == mese].groupby(hh[m.index.month == mese]).mean()
        top = s.sort_values(ascending=False).head(4).index.tolist()
        print(f"EURUSD mese {mese}: M5 piu' volatili (UTC hhmm) {top}")
    # 2) motore vettoriale vs ciclo su 400 operazioni casuali
    o, h, l, c = (m[k].to_numpy() for k in ("open", "high", "low", "close"))
    rng = np.random.default_rng(1)
    j0 = rng.integers(0, len(o) - 300, 400)
    jend = j0 + rng.integers(0, 200, 400)
    d = rng.choice([-1, 1], 400)
    risk = rng.uniform(5, 40, 400) * 1e-4
    tgt = np.where(rng.random(400) < 0.3, np.nan, rng.uniform(5, 60, 400) * 1e-4)
    a = simula_vett(o, h, l, c, j0, jend, d, risk, tgt)
    b = simula_ciclo(o, h, l, c, j0, jend, d, risk, tgt)
    print(f"motore: differenza massima vettoriale-ciclo {np.abs(a-b).max():.2e} prezzo")


def main():
    RIS.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tutto"
    if cmd in ("controlli", "tutto"):
        controlli()
    if cmd in ("simula", "tutto"):
        for c in COPPIE:
            dettaglio_coppia(c)
    if cmd in ("aggrega", "tutto"):
        riepilogo(aggrega())
    if cmd in ("diagnostica", "tutto"):
        diagnostica()
    if cmd == "riepilogo":
        riepilogo(pd.read_parquet(RIS / "fx_b_varianti.parquet"))


if __name__ == "__main__":
    main()
