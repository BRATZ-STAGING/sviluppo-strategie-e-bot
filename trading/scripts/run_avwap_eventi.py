#!/usr/bin/env python3
"""Appendice AB: eventi sugli AVWAP ancorati — scrematura per timeframe.

Per il TF dato costruisce le due ancore (ultimo massimo/minimo swing non
rotto, come appendice Y), l'AVWAP con sigma pesata, e registra gli eventi:
tocco / rottura / retest del VWAP e delle bande, piu' la compressione fra le
bande 1-sigma delle due ancore. Ogni evento porta lo spostamento successivo a
5 e 20 candele in unita' di ATR giornaliero, nel verso dell'ipotesi.

Pipeline identica anche per il PLACEBO (ancore su swing confermati scelti a
caso con eta' simile, seme fisso): un evento conta solo se batte entrambi.

Uso: python3 run_avwap_eventi.py <TF>
Scrive docs/studies/dati/avwap-eventi-<TF>.parquet
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf     # noqa: E402
from framework.volatility import atr_at, daily_atr               # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
K = 3                    # candele per lato per confermare uno swing
RETEST_ENTRO = 30        # candele dalla rottura entro cui vale il retest
ORIZZONTI = (5, 20)
SEME = 20260801


def swing_confermati(h, l, k=K):
    """(candela_estremo, candela_conferma, livello) per alti e bassi, strict."""
    alti, bassi = [], []
    n = len(h)
    for i in range(2 * k, n):
        j = i - k
        if (h[j - k:j] < h[j]).all() and (h[j + 1:i + 1] < h[j]).all():
            alti.append((j, i, float(h[j])))
        if (l[j - k:j] > l[j]).all() and (l[j + 1:i + 1] > l[j]).all():
            bassi.append((j, i, float(l[j])))
    return alti, bassi


def percorso_ancore(sw, cl, lato, n):
    """Per ogni candela i: candela-estremo dell'ancora viva (o -1), stato
    valutato DOPO la chiusura di i. Ancora = swing confermato piu' recente il
    cui livello non e' stato superato da una chiusura dalla conferma in poi."""
    vivi = []           # [candela_estremo, livello]
    per_conferma = {}
    for j, c, lev in sw:
        per_conferma.setdefault(c, []).append((j, lev))
    out = np.full(n, -1, dtype=np.int64)
    for i in range(n):
        for j, lev in per_conferma.get(i, []):
            vivi.append([j, lev])
        if lato == 1:
            vivi = [v for v in vivi if not cl[i] > v[1]]
        else:
            vivi = [v for v in vivi if not cl[i] < v[1]]
        if vivi:
            out[i] = max(vivi, key=lambda v: v[0])[0]
    return out


def percorso_placebo(sw, reale, n, rng):
    """Come il reale, ma ogni segmento usa uno swing confermato a caso con
    eta' (in candele) simile a quella del segmento vero."""
    if not len(sw):
        return np.full(n, -1, dtype=np.int64)
    conf = np.array([c for _, c, _ in sw])
    estr = np.array([j for j, _, _ in sw])
    out = np.full(n, -1, dtype=np.int64)
    corrente = -1
    scelto = -1
    eta_vere = []
    for i in range(n):
        if reale[i] >= 0:
            eta_vere.append(i - reale[i])
    eta_vere = np.array(eta_vere) if eta_vere else np.array([10])
    for i in range(n):
        if reale[i] < 0:
            corrente = -1
            continue
        if reale[i] != corrente:            # nuovo segmento: nuova ancora finta
            corrente = reale[i]
            bersaglio = i - int(rng.choice(eta_vere))
            ok = np.flatnonzero(conf <= i)
            if len(ok):
                scelto = int(estr[ok[np.argmin(np.abs(estr[ok] - bersaglio))]])
            else:
                scelto = -1
        out[i] = scelto
    return out


def livelli_avwap(m1, tfd, ancora, minuto_estremo):
    """AVWAP e sigma per candela, dall'estremo dell'ancora alla chiusura."""
    p = ((m1.high + m1.low + m1.close) / 3).values
    w = m1.volume.values.copy()
    w[~np.isfinite(w) | (w <= 0)] = 1.0
    W = np.concatenate([[0.0], np.cumsum(w)])
    WP = np.concatenate([[0.0], np.cumsum(w * p)])
    WP2 = np.concatenate([[0.0], np.cumsum(w * p * p)])
    chiusure = pd.DatetimeIndex(tfd.index + (tfd.index[1] - tfd.index[0]))
    pos_chiusura = np.searchsorted(m1.index.asi8, chiusure.asi8)   # esclusivo
    av = np.full(len(tfd), np.nan)
    sd = np.full(len(tfd), np.nan)
    for i in range(len(tfd)):
        a = ancora[i]
        if a < 0:
            continue
        s, e = minuto_estremo[a], pos_chiusura[i]
        if e <= s:
            continue
        ww = W[e] - W[s]
        m = (WP[e] - WP[s]) / ww
        v = (WP2[e] - WP2[s]) / ww - m * m
        av[i] = m
        sd[i] = np.sqrt(max(v, 0.0))
    return av, sd


def eventi_livello(tfd, av, sd, atrn, nome_ancora, placebo):
    """Tocchi e rotture su VWAP e bande, retest sul VWAP, per una ancora."""
    h, l, c = tfd.high.values, tfd.low.values, tfd.close.values
    n = len(tfd)
    righe = []
    livelli = [("vwap", av)]
    for j in (1, 2, 3):
        livelli += [(f"b{j}su", av + j * sd), (f"b{j}giu", av - j * sd)]
    for nome, lev in livelli:
        rotture = []                       # (candela, verso) per i retest
        for i in range(1, n - max(ORIZZONTI)):
            if not (np.isfinite(lev[i]) and np.isfinite(lev[i - 1])):
                continue
            lato_prima = np.sign(c[i - 1] - lev[i - 1])
            lato_dopo = np.sign(c[i] - lev[i])
            if lato_prima == 0 or atrn[i] <= 0:
                continue
            tocca = l[i] <= lev[i] <= h[i]
            ev = None
            if tocca and lato_dopo == lato_prima:
                ev, verso = "tocco", lato_prima
            elif lato_dopo != 0 and lato_dopo != lato_prima:
                ev, verso = "rottura", lato_dopo
                if nome == "vwap":
                    rotture.append((i, lato_dopo))
            if ev:
                riga = {"famiglia": f"{ev}_{nome}", "ancora": nome_ancora,
                        "placebo": placebo, "i": i}
                for hz in ORIZZONTI:
                    riga[f"f{hz}"] = verso * (c[i + hz] - c[i]) / atrn[i]
                righe.append(riga)
            if nome == "vwap" and ev is None and tocca and rotture:
                i0, verso = rotture[-1]
                if 0 < i - i0 <= RETEST_ENTRO and lato_prima == verso:
                    riga = {"famiglia": "retest_vwap", "ancora": nome_ancora,
                            "placebo": placebo, "i": i}
                    for hz in ORIZZONTI:
                        riga[f"f{hz}"] = verso * (c[i + hz] - c[i]) / atrn[i]
                    righe.append(riga)
    return righe


def eventi_compressione(tfd, avA, sdA, avB, sdB, atrn, placebo):
    """Inizio della sovrapposizione fra le bande 1-sigma delle due ancore."""
    c = tfd.close.values
    n = len(tfd)
    sopra = np.minimum(avA + sdA, avB + sdB)
    sotto = np.maximum(avA - sdA, avB - sdB)
    dentro = np.isfinite(sopra) & np.isfinite(sotto) & (sotto <= sopra)
    righe = []
    for i in range(1, n - max(ORIZZONTI)):
        if dentro[i] and not dentro[i - 1] and atrn[i] > 0:
            riga = {"famiglia": "compressione", "ancora": "coppia",
                    "placebo": placebo, "i": i}
            for hz in ORIZZONTI:
                riga[f"f{hz}"] = abs(c[i + hz] - c[i]) / atrn[i]
            righe.append(riga)
    return righe


def main():
    tf = sys.argv[1]
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    tfd = resample_tf(m1, tf)
    atr = daily_atr(m1, 14)
    atrn = atr_at(atr, tfd.index).values
    h, l = tfd.high.values, tfd.low.values
    cl = tfd.close.values
    n = len(tfd)

    # primo minuto in cui la candela tocca il proprio estremo
    apertura = np.searchsorted(m1.index.asi8, tfd.index.asi8)
    chiusura = np.append(apertura[1:], len(m1))
    minuto_alto = np.array([apertura[i] + int(np.argmax(m1.high.values[apertura[i]:chiusura[i]]))
                            for i in range(n)])
    minuto_basso = np.array([apertura[i] + int(np.argmin(m1.low.values[apertura[i]:chiusura[i]]))
                             for i in range(n)])

    alti, bassi = swing_confermati(h, l)
    rng = np.random.default_rng(SEME)
    righe = []
    serie = {}
    for nome_anc, sw, minuti in (("alta", alti, minuto_alto),
                                 ("bassa", bassi, minuto_basso)):
        reale = percorso_ancore(sw, cl, 1 if nome_anc == "alta" else -1, n)
        # l'ancora usata dalla candela i e' quella nota alla chiusura di i-1
        usata = np.concatenate([[-1], reale[:-1]])
        av, sd = livelli_avwap(m1, tfd, usata, minuti)
        serie[("reale", nome_anc)] = (av, sd)
        righe += eventi_livello(tfd, av, sd, atrn, nome_anc, 0)
        finta = percorso_placebo(sw, reale, n, rng)
        usata_p = np.concatenate([[-1], finta[:-1]])
        av_p, sd_p = livelli_avwap(m1, tfd, usata_p, minuti)
        serie[("placebo", nome_anc)] = (av_p, sd_p)
        righe += eventi_livello(tfd, av_p, sd_p, atrn, nome_anc, 1)
        print(f"{tf} {nome_anc}: {len(sw)} swing, ancora presente sul "
              f"{(reale >= 0).mean() * 100:.0f}% delle candele", flush=True)
    for etichetta, pl in (("reale", 0), ("placebo", 1)):
        avA, sdA = serie[(etichetta, "alta")]
        avB, sdB = serie[(etichetta, "bassa")]
        righe += eventi_compressione(tfd, avA, sdA, avB, sdB, atrn, pl)

    out = pd.DataFrame(righe)
    out["tf"] = tf
    out["anno"] = tfd.index.year.values[out["i"].values]
    dest = os.path.join(ROOT, "docs", "studies", "dati", f"avwap-eventi-{tf}.parquet")
    out.to_parquet(dest, index=False)
    print(f"{tf}: {len(out)} eventi ({(out.placebo == 0).sum()} reali, "
          f"{(out.placebo == 1).sum()} placebo) -> {dest}", flush=True)


if __name__ == "__main__":
    main()
