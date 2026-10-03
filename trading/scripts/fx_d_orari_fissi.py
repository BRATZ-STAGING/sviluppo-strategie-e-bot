"""Famiglia 4 FX — Orari fissi del mercato dei cambi (scoperta 2010-2017).

Protocollo: docs/fx-intraday-registrazione.md. Rapporto: docs/studies/fx/d-orari-fissi.md
Dati: SOLO D:\\ricerca_fx\\scoperta\\<COPPIA>_<M5|D1>.parquet (BID, indice UTC all'apertura).

Ancore (ora locale vera con zoneinfo):
  TKF fixing di Tokyo 09:55 Tokyo      LDF fixing WM/R 16:00 Londra
  TKO apertura Tokyo 09:00             TKC chiusura Tokyo 15:00
  EUO apertura Francoforte 09:00 Berlino (= 08:00 Londra = apertura Londra)
  LNC chiusura Londra 16:30            USD dati USA 08:30 New York
  NYO apertura New York 09:30

Uso:
  python fx_d_orari_fissi.py controlli   # fusi orari + motore vettoriale vs ciclo
  python fx_d_orari_fissi.py calcola     # una coppia alla volta: regole + placebo
  python fx_d_orari_fissi.py aggrega     # aggregati, promozione, tabelle
  python fx_d_orari_fissi.py diagnostica # lordo dei fixing per filtro e anno
  python fx_d_orari_fissi.py             # tutto
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
# segno "dollaro in acquisto" (per EURJPY al fixing di Tokyo: yen in vendita = EURJPY lungo)
USDSEGNO = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1, "USDJPY": 1, "USDCHF": 1,
            "USDCAD": 1, "EURJPY": 1}
ANNI = list(range(2010, 2018))
NPLACEBO = 1000
SEED = 12345
NS5 = 300 * 10**9
TKY, LON, NY, BER = "Asia/Tokyo", "Europe/London", "America/New_York", "Europe/Berlin"
FASCIA = 24          # placebo: +/- 24 barre M5 (2 ore) attorno all'entrata reale
G_STOP = 0.15        # stop (e obiettivo) in frazione di ATR14
DATE0 = pd.Timestamp("2010-01-01")
NDATE = (pd.Timestamp("2018-01-01") - DATE0).days

ANCORE = {  # nome: (fuso, ora, minuto, tipo)
    "TKF": (TKY, 9, 55, "fix"), "LDF": (LON, 16, 0, "fix"),
    "TKO": (TKY, 9, 0, "ora"), "TKC": (TKY, 15, 0, "ora"),
    "EUO": (BER, 9, 0, "ora"), "LNC": (LON, 16, 30, "ora"),
    "USD": (NY, 8, 30, "ora"), "NYO": (NY, 9, 30, "ora"),
}
HOLD = [30, 60, 120]
GEST = ["T", "S", "ST"]   # T solo tempo; S stop 0,15 ATR; ST stop + obiettivo 0,15 ATR


def pip(c):
    return 0.01 if "JPY" in c else 0.0001


# ---------------------------------------------------------------- griglia di regole
def regole():
    """Elenco completo delle regole (dichiarato prima del calcolo)."""
    R = []
    for anc, (_, _, _, tipo) in ANCORE.items():
        if tipo == "fix":
            filtri = ["tutti", "gotobi", "non-gotobi"] if anc == "TKF" else ["tutti", "fine-mese", "non-fine-mese"]
            for w in (30, 60):
                for s in ("FIX+", "FIX-"):
                    for f in filtri:
                        R.append(dict(ancora=anc, tipo="PRE", seg=s, par=w, h=w, G="T", filtro=f))
            if anc == "LDF":
                for w in (30, 60):
                    for s in ("SEGUI", "CONTRO"):
                        for f in filtri:
                            R.append(dict(ancora=anc, tipo="PRE", seg=s, par=w, h=w, G="T", filtro=f))
            for s in ("FIX+", "FIX-", "SEGUI", "CONTRO"):
                for h in HOLD:
                    for g in GEST:
                        for f in filtri:
                            R.append(dict(ancora=anc, tipo="POST", seg=s, par=30, h=h, G=g, filtro=f))
        else:
            for k in (5, 15):
                for s in ("SEGUI", "CONTRO"):
                    for h in HOLD:
                        for g in GEST:
                            for f in ("tutti", "grande"):
                                R.append(dict(ancora=anc, tipo="POST", seg=s, par=k, h=h, G=g, filtro=f))
    df = pd.DataFrame(R)
    df["rid"] = np.arange(len(df))
    # offset di entrata (minuti rispetto all'ancora) e chiave della griglia di simulazione
    df["off"] = np.where(df.tipo == "PRE", -df.par,
                         np.where(df.ancora.isin(["TKF", "LDF"]), 5, df.par))
    df["key"] = df.ancora + "|" + df.off.astype(str) + "|" + df.h.astype(str) + "|" + df.G
    df["nome"] = (df.ancora + " " + df.tipo + " " + df.seg + " p" + df.par.astype(str) + " h"
                  + df.h.astype(str) + " " + df.G + " " + df.filtro)
    return df


def coppie_regola(r):
    if r.ancora == "LDF" and r.seg.startswith("FIX"):
        return [c for c in COPPIE if c != "EURJPY"]
    return COPPIE


# ---------------------------------------------------------------- dati
def carica(c):
    m = pd.read_parquet(SCOP / f"{c}_M5.parquet")
    d = pd.read_parquet(SCOP / f"{c}_D1.parquet")
    t0 = m.index[0]
    T = ((m.index - t0) // pd.Timedelta(minutes=5)).to_numpy().astype(np.int64)
    N = T[-1] + 1
    cl = np.full(N, np.nan)
    cl[T] = m["close"].to_numpy()
    cl = pd.Series(cl).ffill().to_numpy()
    o = cl.copy(); h = cl.copy(); l = cl.copy(); c_ = cl.copy()
    o[T] = m["open"].to_numpy(); h[T] = m["high"].to_numpy(); l[T] = m["low"].to_numpy()
    real = np.zeros(N, bool)
    real[T] = m["minuti"].to_numpy() > 0
    t0ns = t0.as_unit("ns").value
    # giornate di borsa: giorno UTC lun-ven con >= 600 minuti; ATR14 causale
    dv = d[(d["minuti"] >= 600) & (d.index.dayofweek < 5)].copy()
    pc = dv["close"].shift(1)
    tr = np.maximum(dv["high"] - dv["low"], np.maximum((dv["high"] - pc).abs(), (dv["low"] - pc).abs()))
    atr = tr.rolling(14).mean().shift(1)
    giorni = dv.index.tz_convert(None).normalize()
    return dict(o=o, h=h, l=l, c=c_, real=real, t0=t0ns, N=N, giorni=giorni,
                atr=atr.to_numpy())


def istante(giorni, tz, hh, mm):
    naive = giorni + pd.Timedelta(hours=hh, minutes=mm)
    return naive.tz_localize(tz).tz_convert("UTC").as_unit("ns").asi8


def gotobi_set(giorni):
    s = set()
    for y in range(2009, 2019):
        for mo in range(1, 13):
            ultimo = (pd.Timestamp(y, mo, 1) + pd.offsets.MonthEnd(0)).day
            for dd in (5, 10, 15, 20, 25, ultimo):
                t = pd.Timestamp(y, mo, dd)
                while t.dayofweek >= 5:
                    t -= pd.Timedelta(days=1)
                s.add(t)
    return np.array([g in s for g in giorni])


def fine_mese(giorni):
    per = giorni.to_period("M")
    last = pd.Series(giorni).groupby(per).transform("max").to_numpy()
    return giorni.values == last


# ---------------------------------------------------------------- motore
def esiti(D, ient, Hb, s, tg):
    """Lordo in prezzo (lungo, corto) per entrate all'apertura di ient, uscita a tempo
    alla chiusura della barra ient+Hb-1. Stop prevale sull'obiettivo nella stessa candela;
    apertura oltre lo stop = uscita all'apertura; obiettivo limite senza miglioramento."""
    o, h, l, c = D["o"], D["h"], D["l"], D["c"]
    J = ient[:, None] + np.arange(Hb)[None, :]
    e = o[ient]
    fin = c[ient + Hb - 1]
    Om, Hm, Lm = o[J], h[J], l[J]
    BIG = Hb + 5
    out = []
    for d in (1, -1):
        st = e - d * s
        tp = e + d * tg
        hs = (Lm <= st[:, None]) if d > 0 else (Hm >= st[:, None])
        ht = (Hm >= tp[:, None]) if d > 0 else (Lm <= tp[:, None])
        fs = np.where(hs.any(1), hs.argmax(1), BIG)
        ft = np.where(ht.any(1), ht.argmax(1), BIG)
        os_ = Om[np.arange(len(ient)), np.minimum(fs, Hb - 1)]
        px_s = np.minimum(os_, st) if d > 0 else np.maximum(os_, st)
        ex = np.where((fs < BIG) & (fs <= ft), px_s, np.where(ft < BIG, tp, fin))
        out.append(d * (ex - e))
    return out[0], out[1]


def esiti_ciclo(D, ient, Hb, s, tg, d):
    o, h, l, c = D["o"], D["h"], D["l"], D["c"]
    res = []
    for k in range(len(ient)):
        e = o[ient[k]]
        st, tp = e - d * s[k], e + d * tg[k]
        r = None
        for j in range(ient[k], ient[k] + Hb):
            if (d > 0 and l[j] <= st) or (d < 0 and h[j] >= st):
                px = st
                if d > 0 and o[j] < st:
                    px = o[j]
                if d < 0 and o[j] > st:
                    px = o[j]
                r = d * (px - e)
                break
            if (d > 0 and h[j] >= tp) or (d < 0 and l[j] <= tp):
                r = d * (tp - e)
                break
        if r is None:
            r = d * (c[ient[k] + Hb - 1] - e)
        res.append(r)
    return np.array(res)


# ---------------------------------------------------------------- per coppia
def eventi_ancora(D, anc):
    """Indici delle barre (ancora, inizio 08:00 Londra) e validita' per giornata."""
    tz, hh, mm, _ = ANCORE[anc]
    g = D["giorni"]
    tA = istante(g, tz, hh, mm)
    a = (tA - D["t0"]) // NS5
    ok = (a > 30) & (a < D["N"] - 40)
    a = np.clip(a, 30, D["N"] - 40)
    ok &= D["real"][a]
    i08 = np.clip((istante(g, LON, 8, 0) - D["t0"]) // NS5, 0, D["N"] - 1)
    return a.astype(np.int64), ok, i08.astype(np.int64)


def griglia(D, a, ok, off, h, G, atr, pp):
    """Esiti lungo/corto per ogni giornata e ogni slot della fascia (+/- 2 ore)."""
    Hb = h // 5
    ireal = a + off // 5
    offs = np.arange(-FASCIA, FASCIA + 1)
    I0 = ireal[:, None] + offs[None, :]
    I = np.clip(I0, 0, D["N"] - Hb - 1)
    tod = ((D["t0"] // 60_000_000_000) + I * 5) % 1440   # minuti UTC del giorno
    V = D["real"][I] & ~((tod >= 1245) & (tod < 1335)) & ~((tod < 1245) & (tod + h > 1245))
    V &= ok[:, None] & ~np.isnan(atr)[:, None] & (I0 == I)
    s = np.full(I.shape, np.inf)
    tg = np.full(I.shape, np.inf)
    if G in ("S", "ST"):
        s = np.repeat((G_STOP * atr)[:, None], I.shape[1], 1)
    if G == "ST":
        tg = s.copy()
    gl = np.full(I.shape, np.nan, np.float32)
    gs = np.full(I.shape, np.nan, np.float32)
    m = V
    L_, S_ = esiti(D, I[m], Hb, s[m], tg[m])
    gl[m] = L_ / pp
    gs[m] = S_ / pp
    tod_real = tod[:, FASCIA]
    mult = np.where(tod_real >= 1335, 2.0, 1.0)
    return gl, gs, V, mult


def calcola_coppia(c, RG):
    t1 = time.time()
    D = carica(c)
    pp, costo = pip(c), COSTO[c]
    g = D["giorni"]
    dix = ((g - DATE0).days).to_numpy()
    anno = g.year.to_numpy()
    got = gotobi_set(g)
    fm = fine_mese(g)
    nd = len(g)
    righe, ev_rows, sig_rows = [], [], []
    pl_sum = {}
    daily = {}
    for anc in ANCORE:
        a, ok, i08 = eventi_ancora(D, anc)
        o, cl = D["o"], D["c"]
        # segnali
        sig = {}
        if ANCORE[anc][3] == "fix":
            sig[("POST", 30)] = cl[a] - o[a - 6]                     # A-30 -> fine barra del fixing
            for w in (30, 60):
                e = a - w // 5
                sig[("PRE", w)] = np.where(i08 < e, cl[e - 1] - o[i08], np.nan)  # 08:00 Londra -> entrata
        else:
            for k in (5, 15):
                sig[("POST", k)] = cl[a + k // 5 - 1] - o[a]
        grande = {}
        for kk, sv in sig.items():
            x = pd.Series(np.where(ok & (sv != 0), np.abs(sv), np.nan))
            thr = x.dropna().rolling(250, min_periods=60).median().shift(1).reindex(x.index)
            grande[kk] = (np.abs(sv) >= thr.to_numpy())
        sig_rows.append(pd.DataFrame({"data": g, "ancora": anc, "ok": ok, "gotobi": got, "fine_mese": fm,
                                      **{f"sig_{t}{p}": v / pp for (t, p), v in sig.items()}}))
        sub = RG[RG.ancora == anc]
        for key, rk in sub.groupby("key"):
            r0 = rk.iloc[0]
            gl, gs, V, mult = griglia(D, a, ok, int(r0.off), int(r0.h), r0.G, D["atr"], pp)
            ev_rows.append(pd.DataFrame({"data": g, "chiave": key, "lordo_lungo": gl[:, FASCIA],
                                         "lordo_corto": gs[:, FASCIA]}))
            nval = V.sum(1)
            vlist = np.argsort(~V, axis=1, kind="stable")
            for _, r in rk.iterrows():
                if c not in coppie_regola(r):
                    continue
                if r.seg.startswith("FIX"):
                    dr = np.full(nd, USDSEGNO[c] * (1 if r.seg == "FIX+" else -1), float)
                    sk = None
                else:
                    sk = (r.tipo, int(r.par))
                    dr = np.sign(sig[sk]) * (1 if r.seg == "SEGUI" else -1)
                    dr = np.nan_to_num(dr)
                f = r.filtro
                fl = np.ones(nd, bool)
                if f == "gotobi":
                    fl = got
                elif f == "non-gotobi":
                    fl = ~got
                elif f == "fine-mese":
                    fl = fm
                elif f == "non-fine-mese":
                    fl = ~fm
                elif f == "grande":
                    fl = grande[sk]
                m = V[:, FASCIA] & fl & (dr != 0)
                idx = np.nonzero(m)[0]
                n = len(idx)
                if n == 0:
                    continue
                d_ = dr[idx]
                lordo = np.where(d_ > 0, gl[idx, FASCIA], gs[idx, FASCIA]).astype(float)
                cst = costo * mult[idx]
                net = lordo - cst
                # placebo: per giorno slot casuale nella fascia e direzione casuale (condivisi fra coppie)
                rng = np.random.default_rng(SEED + int(r.rid))
                U = rng.random((2, NPLACEBO, NDATE), dtype=np.float32)
                us = U[0][:, dix[idx]]
                fl_ = np.where(U[1][:, dix[idx]] < 0.5, -1.0, 1.0)
                kk = np.minimum((us * nval[idx][None, :]).astype(np.int64), nval[idx][None, :] - 1)
                slot = vlist[idx[None, :], kk]
                dd = d_[None, :] * fl_
                pg = np.where(dd > 0, gl[idx[None, :], slot], gs[idx[None, :], slot])
                pl_sum[(int(r.rid), c)] = (pg - cst[None, :]).sum(1)
                dv = np.zeros(NDATE, np.float32)
                np.add.at(dv, dix[idx], net)
                daily[(int(r.rid), c)] = dv
                anni = np.array([net[anno[idx] == y].sum() for y in ANNI])
                sd = net.std(ddof=1) if n > 1 else np.nan
                righe.append(dict(rid=int(r.rid), coppia=c, n=n, giornate=nd, opg=n / nd,
                                  lordo=lordo.mean(), netto=net.mean(), costo=cst.mean(),
                                  netto15=(net - 0.5 * cst).mean(), sd=sd,
                                  t=net.mean() / sd * np.sqrt(n) if n > 1 else np.nan,
                                  anni_pos=int((anni > 0).sum()),
                                  **{f"a{y}": v for y, v in zip(ANNI, anni)}))
    RIS.mkdir(parents=True, exist_ok=True)
    pd.concat(ev_rows).to_parquet(RIS / f"d_orari_esiti_{c}.parquet")
    pd.concat(sig_rows).to_parquet(RIS / f"d_orari_segnali_{c}.parquet")
    res = pd.DataFrame(righe)
    for col in ("p",):
        res[col] = np.nan
    pv = []
    for rr in res.itertuples():
        S = pl_sum[(rr.rid, c)] / rr.n
        pv.append((1 + (S >= rr.netto).sum()) / (NPLACEBO + 1))
    res["p"] = pv
    np.savez_compressed(RIS / f"d_orari_placebo_{c}.npz",
                        rid=np.array([k[0] for k in pl_sum]),
                        somme=np.array(list(pl_sum.values()), np.float32),
                        giorni=np.array(list(daily.values()), np.float32))
    print(f"{c}: {len(res)} regole, giornate {nd}, {time.time() - t1:.0f}s", flush=True)
    return res


# ---------------------------------------------------------------- controlli
def controlli():
    D = carica("EURUSD")
    g = D["giorni"]
    # 1) fusi: barra M5 piu' volatile (media |close-open|) in gennaio e in luglio
    r = np.abs(D["c"] - D["o"])
    tod = ((D["t0"] // 60_000_000_000) + np.arange(D["N"]) * 5) % 1440
    ts = pd.to_datetime(D["t0"] + np.arange(D["N"]) * NS5, utc=True)
    out = {}
    for mese in (1, 7):
        mm = (ts.month == mese) & D["real"]
        s = pd.Series(r[mm]).groupby(tod[mm]).mean()
        out[mese] = f"{s.idxmax() // 60:02d}:{s.idxmax() % 60:02d} UTC"
    print("EURUSD barra piu' volatile: gennaio", out[1], "luglio", out[7], "(attese 13:30 / 12:30 = 8:30 NY)")
    # 2) Francoforte 9:00 Berlino == Londra 8:00 su tutte le giornate
    print("Francoforte 9:00 == Londra 8:00:", bool((istante(g, BER, 9, 0) == istante(g, LON, 8, 0)).all()))
    # 3) Tokyo 09:55 = 00:55 UTC tutto l'anno
    t = pd.to_datetime(istante(g, TKY, 9, 55), utc=True)
    print("fixing Tokyo sempre 00:55 UTC:", bool(((t.hour == 0) & (t.minute == 55)).all()))
    tl = pd.to_datetime(istante(g, LON, 16, 0), utc=True)
    print("fixing Londra in UTC:", sorted(set(tl.hour)))
    # 4) motore vettoriale contro ciclo
    rng = np.random.default_rng(1)
    ient = rng.integers(1000, D["N"] - 100, 400)
    ient = ient[D["real"][ient]]
    s = np.abs(rng.normal(0.0010, 0.0004, len(ient)))
    for Hb, tg in ((24, s), (12, np.full(len(ient), np.inf))):
        L_, S_ = esiti(D, ient, Hb, s, tg)
        dl = np.abs(L_ - esiti_ciclo(D, ient, Hb, s, tg, 1)).max()
        ds = np.abs(S_ - esiti_ciclo(D, ient, Hb, s, tg, -1)).max()
        print(f"motore vs ciclo (H={Hb}): diff max lungo {dl:.1e} corto {ds:.1e}")
    print("giornate di borsa EURUSD:", len(g), "gotobi:", int(gotobi_set(g).sum()),
          "fine mese:", int(fine_mese(g).sum()))


def calcola():
    RG = regole()
    RG.to_parquet(RIS / "d_orari_regole.parquet")
    n_var = sum(len(coppie_regola(r)) for r in RG.itertuples())
    print(f"regole {len(RG)}, varianti regola x coppia {n_var}")
    out = []
    for c in COPPIE:
        out.append(calcola_coppia(c, RG))
    V = pd.concat(out, ignore_index=True)
    V.to_parquet(RIS / "d_orari_varianti_coppia.parquet")


def aggrega():
    RG = regole().set_index("rid")
    V = pd.read_parquet(RIS / "d_orari_varianti_coppia.parquet")
    PL, DY = {}, {}
    for c in COPPIE:
        with np.load(RIS / f"d_orari_placebo_{c}.npz") as z:
            rids, som, gio = z["rid"], z["somme"], z["giorni"]
        for i, rid in enumerate(rids):
            PL[(int(rid), c)] = som[i]
            DY[(int(rid), c)] = gio[i]
    anno_d = (DATE0 + pd.to_timedelta(np.arange(NDATE), "D")).year.to_numpy()
    righe = []
    for rid, grp in V.groupby("rid"):
        for nome_ag, sel in (("TUTTE", grp), ("POS", grp[grp.netto > 0])):
            if len(sel) == 0:
                continue
            n = sel.n.sum()
            netto = (sel.netto * sel.n).sum() / n
            costo = (sel.costo * sel.n).sum() / n
            lordo = (sel.lordo * sel.n).sum() / n
            dy = sum(DY[(rid, c)] for c in sel.coppia).astype(float)
            # t sulle somme giornaliere delle coppie (le coppie dello stesso giorno sono correlate)
            act = np.zeros(NDATE, bool)
            for c in sel.coppia:
                act |= DY[(rid, c)] != 0
            x = dy[act]
            t_g = x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 2 else np.nan
            anni = np.array([dy[anno_d == y].sum() for y in ANNI])
            S = sum(PL[(rid, c)] for c in sel.coppia) / n
            p = (1 + (S >= netto).sum()) / (NPLACEBO + 1)
            righe.append(dict(rid=rid, aggr=nome_ag, coppie=",".join(sel.coppia), ncoppie=len(sel),
                              n=n, opg=sel.opg.sum(), lordo=lordo, netto=netto, costo=costo,
                              netto_costo=netto / costo, netto15=netto - 0.5 * costo,
                              t=t_g, anni_pos=int((anni > 0).sum()), p=p))
    A = pd.DataFrame(righe).join(RG[["nome", "ancora", "tipo", "seg"]], on="rid")
    A.to_parquet(RIS / "d_orari_aggregati.parquet")
    V = V.join(RG[["nome", "ancora", "tipo", "seg"]], on="rid")
    # ---- riepilogo per coppia
    print(f"\nVARIANTI per coppia: {len(V)}")
    print(f" netto>0 {int((V.netto > 0).sum())} ({(V.netto > 0).mean():.1%}), t>=3 {int((V.t >= 3).sum())},"
          f" t<=-3 {int((V.t <= -3).sum())}, anni>=6 {int((V.anni_pos >= 6).sum())},"
          f" p<0,01 {int((V.p < 0.01).sum())}, netto mediano {V.netto.median():.3f} pip")
    tutti = (V.netto > 0) & (V.netto15 > 0) & (V.t >= 3) & (V.anni_pos >= 6) & (V.p < 0.01)
    print(f" per coppia tutti i criteri tranne frequenza: {int(tutti.sum())}")
    print(V.groupby("ancora").apply(lambda d: pd.Series(dict(
        var=len(d), pos=(d.netto > 0).mean(), t3=(d.t >= 3).sum(), tm3=(d.t <= -3).sum(),
        lordo_med=d.lordo.median(), netto_med=d.netto.median()))).round(3))
    # ---- aggregati
    A["promo"] = ((A.netto > 0) & (A.netto15 > 0) & (A.t >= 3) & (A.anni_pos >= 6)
                  & (A.p < 0.01) & (A.opg >= 1))
    print(f"\nAGGREGATI: {len(A)} (TUTTE {int((A["aggr"] == 'TUTTE').sum())}, POS {int((A["aggr"] == 'POS').sum())});"
          f" t>=3 {int((A.t >= 3).sum())}, opg>=1 {int((A.opg >= 1).sum())},"
          f" tutti tranne frequenza {int(((A.netto > 0) & (A.netto15 > 0) & (A.t >= 3) & (A.anni_pos >= 6) & (A.p < 0.01)).sum())},"
          f" promossi {int(A.promo.sum())}")
    cols = ["nome", "aggr", "coppie", "n", "opg", "lordo", "netto", "netto_costo", "netto15", "t", "anni_pos", "p"]
    print("\nmigliori aggregati per t:")
    print(A.sort_values("t", ascending=False)[cols].head(15).round(3).to_string(index=False))
    print("\nmigliori aggregati con opg>=1:")
    print(A[A.opg >= 1].sort_values("t", ascending=False)[cols].head(10).round(3).to_string(index=False))
    print("\nmigliori per coppia (t):")
    print(V.sort_values("t", ascending=False)[["nome", "coppia", "n", "opg", "lordo", "netto", "netto15", "t", "anni_pos", "p"]]
          .head(10).round(3).to_string(index=False))
    # candidati: max 3, in ordine di t, uno per ancora-tipo-segnale
    P = A[A.promo].sort_values("t", ascending=False)
    cand, visti = [], set()
    for r in P.itertuples():
        k = (r.ancora, r.tipo, r.seg)
        if k in visti:
            continue
        visti.add(k)
        cand.append(r)
        if len(cand) == 3:
            break
    print("\nCANDIDATI:", len(cand))
    for r in cand:
        print(" ", r.nome, r.aggr, r.coppie, f"n {r.n} opg {r.opg:.2f} netto {r.netto:.2f} x1,5 {r.netto15:.2f} t {r.t:.2f} anni {r.anni_pos} p {r.p:.3f}")


def diagnostica():
    """Lordo dei fixing per filtro e per anno (aggregato TUTTE, gestione T), senza scelte."""
    RG = regole().set_index("rid")
    A = pd.read_parquet(RIS / "d_orari_aggregati.parquet").join(RG[["par", "h", "G", "filtro"]], on="rid")
    T = A[(A["aggr"] == "TUTTE") & (A.G == "T") & A.ancora.isin(["TKF", "LDF"]) & A.seg.str.startswith("FIX")]
    T = T[((T.tipo == "PRE") & (T.par == 30)) | ((T.tipo == "POST") & (T.h == 120))]
    print("\nFIXING, aggregato TUTTE, gestione T (PRE 30 min, POST 120 min):")
    print(T[["nome", "n", "opg", "lordo", "netto", "netto15", "t", "anni_pos", "p"]].round(3).to_string(index=False))
    V = pd.read_parquet(RIS / "d_orari_varianti_coppia.parquet").join(RG[["nome"]], on="rid")
    sel = ["TKF PRE FIX+ p30 h30 T tutti", "TKF POST FIX- p30 h120 T tutti", "LDF PRE FIX- p60 h60 T fine-mese"]
    rows = []
    for nm in sel:
        d = V[V.nome == nm]
        rows.append({"regola": nm, **{str(y): d[f"a{y}"].sum() for y in ANNI}})
    print("\nnetto annuo in pip, somma su tutte le coppie ammesse (costi x1):")
    print(pd.DataFrame(rows).round(1).to_string(index=False))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tutto"
    if cmd in ("controlli", "tutto"):
        controlli()
    if cmd in ("calcola", "tutto"):
        calcola()
    if cmd in ("aggrega", "tutto"):
        aggrega()
    if cmd in ("diagnostica", "tutto"):
        diagnostica()
