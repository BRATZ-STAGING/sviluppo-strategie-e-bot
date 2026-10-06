#!/usr/bin/env python3
"""Crollo -> conferma di ripresa -> entrata (e specchio short): SCOPERTA 2009-2017.

Protocollo VINCOLANTE: docs/crollo-conferma-registrazione.md (commit 5a2ea2b).
Motore: trading/framework/crollo_conferma.py. Rapporto:
docs/studies/conferme/scoperta.md.

Dati (solo scoperta): D:\\ricerca_zero\\scoperta\\XAUUSD_M5|M15|H1|D1.parquet
e data/XAUUSD_M1/XAUUSD_M1_2009..2017.parquet (solo per il VWAP giornaliero,
che richiede il volume). Le barre del segnale (M15, H1, H4, D1) si
costruiscono dalle M5 (H4 = 4 ore UTC etichettate all'apertura; D1 = giornata
UTC, con le giornate < 300 minuti unite alla successiva); M15 e H1 sono
controllate contro i Parquet.

Scrive in D:\\ricerca_conferme\\risultati\\:
    operazioni.parquet     una riga per operazione tenuta (variante, esito)
    varianti.parquet       una riga per variante (672 + 96 riferimenti)
    verifica_motore.parquet 300 operazioni rifatte con un ciclo barra per barra
Stampa solo aggregati compatti.
"""
from __future__ import annotations

import gc
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from framework import crollo_conferma as cc  # noqa: E402
from framework.data import load_m1  # noqa: E402
from framework.vwap import anchored_vwap  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SC = r"D:\ricerca_zero\scoperta"
OUT = r"D:\ricerca_conferme\risultati"
CACHE = r"D:\ricerca_conferme\cache"
ANNI = list(range(2009, 2018))
MESI = 108
NPLAC, SEED = 2000, 12345
COSTO = cc.costo_rt(2017)          # 0,46 $ RT per tutta la scoperta
EPOCA = pd.Timestamp("1970-01-01", tz="UTC")
K = {"intraday": (0.75, 1.0, 1.5), "swing": (2.0, 3.0, 4.0)}
TFS = {"intraday": ("M15", "H1"), "swing": ("H4", "D1")}
pd.set_option("display.width", 200)


def minuti(idx) -> np.ndarray:
    return ((idx - EPOCA) // pd.Timedelta("1min")).to_numpy().astype(np.int64)


# ------------------------------------------------------------------ dati
def carica():
    m5 = pd.read_parquet(os.path.join(SC, "XAUUSD_M5.parquet"))
    assert m5.index[-1] < pd.Timestamp("2018-01-01", tz="UTC")
    t5 = minuti(m5.index)
    o5, h5, l5, c5 = (m5[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    d1 = pd.read_parquet(os.path.join(SC, "XAUUSD_D1.parquet"))
    fg = cc.giornate(minuti(d1.index), d1["minuti"].to_numpy())
    keep = t5 < fg[-1]
    t5, o5, h5, l5, c5 = (a[keep] for a in (t5, o5, h5, l5, c5))
    g5 = cc.giorno_di(fg, t5)
    # giornate unite -> ATR20 noto alla fine di ogni giornata
    i0 = np.r_[0, np.nonzero(np.diff(g5))[0] + 1]
    assert len(i0) == len(fg), "giornate senza M5"
    i1 = np.r_[i0[1:] - 1, len(g5) - 1]
    atr_f = cc.atr_giornaliero(o5[i0], np.maximum.reduceat(h5, i0),
                               np.minimum.reduceat(l5, i0), c5[i1])
    return t5, o5, h5, l5, c5, fg, g5, atr_f


def vwap_m5(t5: np.ndarray) -> np.ndarray:
    """VWAP giornaliero (UTC, volume Dukascopy) alla chiusura di ogni M5."""
    f = os.path.join(CACHE, "vwap_m5.npz")
    if os.path.exists(f):
        z = np.load(f)
        if len(z["t"]) == len(t5) and (z["t"] == t5).all():
            return z["v"]
    out = np.full(len(t5), np.nan)
    for y in ANNI:
        m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"), years=[y])
        v = anchored_vwap(m1, "day").to_numpy()
        tm = minuti(m1.index)
        del m1
        sel = (t5 >= tm[0]) & (t5 <= tm[-1])
        j = np.searchsorted(tm, t5[sel] + 4, side="right") - 1
        out[sel] = v[j]
        del v, tm
        gc.collect()
    os.makedirs(CACHE, exist_ok=True)
    np.savez(f, t=t5, v=out)
    return out


def costruisci_tf(tf, t5, o5, h5, l5, c5, vw5, fg, g5, atr_f) -> cc.Barre:
    if tf == "D1":
        return cc.barre_da_m5(t5, o5, h5, l5, c5, g5, 1440, vw5, fg, atr_f, fine=fg[np.unique(g5)])
    dur = {"M15": 15, "H1": 60, "H4": 240}[tf]
    return cc.barre_da_m5(t5, o5, h5, l5, c5, t5 // dur, dur, vw5, fg, atr_f)


def controlla_parquet(tf, B):
    p = pd.read_parquet(os.path.join(SC, f"XAUUSD_{tf}.parquet"))
    t = minuti(p.index)
    assert len(t) == len(B.t) and (t == B.t).all(), tf
    d = max(np.abs(p[k].to_numpy() - getattr(B, k[0])).max() for k in ("open", "high", "low", "close"))
    return d


# ------------------------------------------------------------- statistiche
def tstat(x):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return 0.0
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x))


def misure(g: pd.DataFrame, rng) -> dict:
    x = g["netR"].to_numpy()
    n = len(x)
    if n == 0:
        return dict(n=0)
    mese = g.groupby("mese")["netR"].sum().reindex(range(MESI), fill_value=0.0).to_numpy()
    anno = g.groupby("anno")["netR"].sum().reindex(ANNI, fill_value=0.0)
    cum = np.r_[0, np.cumsum(x)]
    # placebo: stessi istanti, direzione casuale (stesse regole specchiate)
    xf = g["netRf"].to_numpy()
    d = (x - xf).astype(np.float64)
    tot = np.empty(NPLAC)
    for a in range(0, NPLAC, 500):
        s = rng.random((min(500, NPLAC - a), n)) < 0.5
        tot[a:a + len(s)] = xf.sum() + s.astype(np.float64) @ d
    p = (1 + (tot >= x.sum() - 1e-9).sum()) / (NPLAC + 1)
    t_op, t_m = tstat(x), tstat(mese)
    return dict(n=n, op_mese=n / MESI, vinte=(x > 0).mean(), R=x.mean(), R15=g["netR15"].mean(),
                usd=g["usd"].mean(), usd15=g["usd15"].mean(), lordoR=g["lordoR"].mean(),
                swapR=g["swapR"].mean(), t_op=t_op, t_mese=t_m, t=min(t_op, t_m),
                anni_pos=int((anno > 0).sum()), dd=float((np.maximum.accumulate(cum) - cum).max()),
                totR=x.sum(), p=p, tenuta_h=g["tenuta_h"].mean(),
                **{f"a{a}": v for a, v in anno.items()})


# ---------------------------------------------------------- controllo lento
def lento(t5, o5, h5, l5, c5, g5, e, dz, stop, tg, oriz):
    """Ciclo barra per barra indipendente: limite, uscita, swap e netto."""
    ts = pd.Timestamp(int(t5[e]) * 60, unit="s", tz="UTC")
    if oriz == "intraday":
        tx = ts.normalize() + pd.Timedelta("20h55min")
        if ts.time() >= pd.Timestamp("22:15").time():
            tx += pd.Timedelta("1D")
    ent = o5[e]
    x, last = e, e
    esito = None
    if (tg - ent) * dz <= 0:
        esito = (e, ent)
    while esito is None:
        if x >= len(t5):
            break
        if oriz == "intraday":
            if pd.Timestamp(int(t5[x]) * 60 + 300, unit="s", tz="UTC") > tx:
                break
        elif g5[x] > g5[e] + 19:
            break
        if dz == 1:
            if x > e and o5[x] <= stop:
                esito = (x, o5[x]); break
            if l5[x] <= stop:
                esito = (x, stop); break
            if h5[x] >= tg:
                esito = (x, tg); break
        else:
            if x > e and o5[x] >= stop:
                esito = (x, o5[x]); break
            if h5[x] >= stop:
                esito = (x, stop); break
            if l5[x] <= tg:
                esito = (x, tg); break
        last = x
        x += 1
    if esito is None:
        esito = (last, c5[last])
    xx, px = esito
    t_in = ts
    t_out = pd.Timestamp(int(t5[xx]) * 60, unit="s", tz="UTC")
    notti = 0
    d = t_in.normalize()
    while d <= t_out:
        T = d + pd.Timedelta("21h")
        if T.weekday() < 5 and t_in < T <= t_out:
            notti += 3 if T.weekday() == 2 else 1
        d += pd.Timedelta("1D")
    return xx, px, cc.esito_usd(dz, ent, px, notti, COSTO)


# ------------------------------------------------------------------ main
def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    t5, o5, h5, l5, c5, fg, g5, atr_f = carica()
    m5 = (t5, o5, h5, l5, c5)
    vw5 = vwap_m5(t5)
    print(f"M5 {len(t5):,} barre, giornate {len(fg)}, VWAP mancante {np.isnan(vw5).mean():.4f}")
    pezzi, verif_pool = [], []
    righe_tronc = []
    vid = 0
    for oriz in ("intraday", "swing"):
        for tf in TFS[oriz]:
            B = costruisci_tf(tf, *m5, vw5, fg, g5, atr_f)
            if tf in ("M15", "H1"):
                print(f"{tf}: {len(B.c):,} barre, scarto max dai Parquet {controlla_parquet(tf, B):.2e}")
            else:
                print(f"{tf}: {len(B.c):,} barre")
            for dz in (1, -1):
                Bx = B if dz == 1 else cc.specchio(B)
                for k in K[oriz]:
                    for conf in list(cc.CONFERME) + ["NESSUNA"]:
                        sg = cc.segnali(Bx, k, conf, oriz)
                        op = cc.operazioni(sg, B, m5, oriz, dz, COSTO, fg, g5)
                        if len(op["e"]) == 0:
                            continue
                        e, ent, R = op["e"], op["ent"], op["R"]
                        for ti, ob in enumerate(cc.OBIETTIVI):
                            x = op["x"][:, ti]
                            keep = cc.una_alla_volta(e, x)
                            px, nt = op["px"][keep, ti], op["notti"][keep, ti]
                            ee, en, RR = e[keep], ent[keep], R[keep]
                            usd = cc.esito_usd(dz, en, px, nt, COSTO)
                            usd15 = cc.esito_usd(dz, en, px, nt, COSTO, 1.5)
                            usdf = cc.esito_usd(-dz, en, op["pxf"][keep, ti], op["nottif"][keep, ti], COSTO)
                            sw = (cc.SWAP_LONG if dz == 1 else cc.SWAP_SHORT) * en / cc.SWAP_RIF * nt
                            te = pd.to_datetime(t5[ee] * 60, unit="s", utc=True)
                            stop, tg = op["stop"][keep], op["obj"][keep, ti]
                            pz = pd.DataFrame(dict(
                                vid=vid if conf != "NESSUNA" else -1, orizzonte=oriz, tf=tf, k=k,
                                conferma=conf, obiettivo=ob, lato="long" if dz == 1 else "short",
                                e=ee, uscita=x[keep], ent=en, stop=stop, obj=tg, R=RR, px=px,
                                motivo=op["mot"][keep, ti], notti=nt, usd=usd, usd15=usd15,
                                netR=usd / RR, netR15=usd15 / RR, netRf=usdf / RR,
                                lordoR=dz * (px - en) / RR, swapR=sw / RR,
                                anno=te.year, mese=(te.year - 2009) * 12 + te.month - 1,
                                tenuta_h=(t5[x[keep]] - t5[ee]) / 60.0))
                            pezzi.append(pz)
                            if conf != "NESSUNA":
                                vid += 1
                    # controllo di troncamento (nessun lookahead) su un caso per TF
                    if k == K[oriz][1]:
                        for conf in ("C1", "C5"):
                            full = [(s.inizio, s.conferma, s.L) for s in cc.segnali(Bx, k, conf, oriz)]
                            taglio = len(B.c) * 2 // 3
                            n5 = B.i5[taglio]
                            Bt = costruisci_tf(tf, t5[:n5], o5[:n5], h5[:n5], l5[:n5], c5[:n5],
                                               vw5[:n5], fg, g5[:n5], atr_f)
                            Bt = Bt if dz == 1 else cc.specchio(Bt)
                            tr = [(s.inizio, s.conferma, s.L) for s in cc.segnali(Bt, k, conf, oriz)]
                            a = [s for s in full if s[1] < taglio]
                            b = [s for s in tr if s[1] < taglio]
                            righe_tronc.append(dict(tf=tf, dz=dz, conf=conf, n=len(a), uguali=a == b))
            del B
            gc.collect()
            print(f"  {tf} fatto ({time.time() - t0:.0f}s)")
    O = pd.concat(pezzi, ignore_index=True)
    del pezzi
    gc.collect()
    O["vid"] = O["vid"].astype(np.int32)
    O.to_parquet(os.path.join(OUT, "operazioni.parquet"))
    T = pd.DataFrame(righe_tronc)
    print(f"\nControllo troncamento (segnali prima del taglio identici): "
          f"{int(T['uguali'].sum())}/{len(T)} casi, {int(T['n'].sum())} segnali")

    # ------------------------------------------------ verifica del motore
    rng0 = np.random.default_rng(7)
    camp = O.iloc[rng0.choice(len(O), 300, replace=False)]
    diff, dx = 0.0, 0
    vr = []
    for r in camp.itertuples():
        dz = 1 if r.lato == "long" else -1
        xx, px, usd = lento(t5, o5, h5, l5, c5, g5, int(r.e), dz, r.stop, r.obj, r.orizzonte)
        diff = max(diff, abs(usd - r.usd))
        dx = max(dx, abs(xx - r.uscita))
        vr.append(dict(e=r.e, uscita=r.uscita, uscita_lento=xx, usd=r.usd, usd_lento=usd))
    pd.DataFrame(vr).to_parquet(os.path.join(OUT, "verifica_motore.parquet"))
    print(f"Verifica motore (300 operazioni, ciclo barra per barra): differenza massima netto "
          f"{diff:.2e} $, uscita {dx} barre")

    # ------------------------------------------------ misure per variante
    chiavi = ["orizzonte", "tf", "k", "conferma", "obiettivo", "lato"]
    righe = []
    for i, (key, g) in enumerate(O.groupby(chiavi, sort=False)):
        rng = np.random.default_rng(SEED + i)
        righe.append(dict(zip(chiavi, key), **misure(g.sort_values("e"), rng)))
    V = pd.DataFrame(righe)
    ref = V[V["conferma"] == "NESSUNA"].set_index(["orizzonte", "tf", "k", "obiettivo", "lato"])
    for c in ("R", "R15", "usd", "vinte"):
        V[f"rif_{c}"] = [ref[c].get((a, b, k, d, e), np.nan) for a, b, k, d, e in
                         zip(V["orizzonte"], V["tf"], V["k"], V["obiettivo"], V["lato"])]
    V["meglio_rif"] = (V["R"] > V["rif_R"]) & (V["R15"] > V["rif_R15"])
    V["passa"] = ((V["R"] > 0) & (V["R15"] > 0) & (V["usd"] > 0) & (V["usd15"] > 0) & (V["t"] >= 3)
                  & (V["anni_pos"] >= 7) & (V["p"] < 0.01) & V["meglio_rif"] & (V["conferma"] != "NESSUNA"))
    V.to_parquet(os.path.join(OUT, "varianti.parquet"))
    Vc = V[V["conferma"] != "NESSUNA"]
    print(f"\nVarianti con operazioni: {len(Vc)} su 672 (+ {int((V['conferma'] == 'NESSUNA').sum())} riferimenti)")
    print(f"criteri: netto>0 x1 e x1,5 {int(((Vc.R > 0) & (Vc.R15 > 0) & (Vc.usd > 0) & (Vc.usd15 > 0)).sum())}, "
          f"t>=3 {int((Vc.t >= 3).sum())}, anni>=7 {int((Vc.anni_pos >= 7).sum())}, "
          f"p<0,01 {int((Vc.p < 0.01).sum())}, meglio del rif {int(Vc.meglio_rif.sum())}, "
          f"TUTTI {int(Vc.passa.sum())}")
    col = ["orizzonte", "tf", "k", "conferma", "obiettivo", "lato", "n", "op_mese", "vinte", "R", "R15",
           "usd", "t_op", "t_mese", "anni_pos", "dd", "p", "rif_R"]
    print("\nMigliori 15 per t (= min fra t operazioni e t mensile):")
    print(Vc.sort_values("t", ascending=False).head(15)[col].round(3).to_string(index=False))

    def gruppo(by):
        a = Vc.groupby(by).agg(var=("n", "size"), n_medio=("n", "mean"), vinte=("vinte", "mean"),
                               R=("R", "mean"), rifR=("rif_R", "mean"), usd=("usd", "mean"),
                               rif_usd=("rif_usd", "mean"), meglio=("meglio_rif", "mean"),
                               pos=("R15", lambda s: (s > 0).mean()), t_max=("t", "max"))
        return a
    print("\nPer conferma (medie sulle varianti; rif = senza conferma corrispondente):")
    print(gruppo("conferma").round(3).to_string())
    print("\nPer orizzonte e lato:")
    print(gruppo(["orizzonte", "lato"]).round(3).to_string())
    C = Vc[Vc["passa"]].sort_values("t", ascending=False).head(5)
    print(f"\nCandidati: {len(C)}")
    if len(C):
        print(C[col].round(3).to_string(index=False))
    print(f"\nTempo {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
