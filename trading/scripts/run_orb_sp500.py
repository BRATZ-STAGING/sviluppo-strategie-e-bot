#!/usr/bin/env python3
"""Appendice BJ: l'ORB di Crabel sul mercato per cui e' stato inventato.

L'utente ha ragione su un punto decisivo: l'ORB non va adattato all'oro, va
misurato dove funziona. E dove funziona lo dice la letteratura — futures e
indici azionari, cioe' mercati con una vera **asta di apertura**. Sull'oro
spot quell'apertura non esiste, ed e' proprio la ragione per cui Crabel dice
che la sua strategia ha smesso di funzionare quando i mercati sono passati a
ventiquattro ore.

DATI: S&P 500 a un minuto, novembre 2010 - dicembre 2018, 2.117.667 barre,
da HistData tramite il repository pubblico FutureSharks/financial-data.
Fonte indipendente da tutto il resto del progetto.

Il fuso e' stato determinato per misura, non per fiducia: il minuto piu'
agitato cade alle 09:30 sia nei mesi invernali sia in quelli estivi, quindi i
timestamp seguono gia' l'ora di New York con l'ora legale (se fossero EST
fisso, d'estate il picco cadrebbe alle 08:30).

LA REGOLA, presa alla lettera da Crabel (1990):
  1. apertura della sessione di cassa, 09:30 New York;
  2. Stretch = media a 10 giorni del MINORE fra |apertura - massimo| e
     |apertura - minimo| della sessione;
  3. ordine di acquisto stop a apertura + Stretch, di vendita a apertura -
     Stretch;
  4. il primo toccato apre, l'altro diventa lo stop. Una operazione al giorno;
  5. chiusura a fine sessione, 16:00 New York. Nessun obiettivo.

IPOTESI PRE-REGISTRATE:
  A. la regola originale ha risultato per operazione positivo al netto dei
     costi, sul periodo di ricerca E su quello di verifica;
  B. il vantaggio vive nei giorni ad alta volatilita' (Lundstrom; Gao et al.,
     Journal of Financial Economics) e sparisce in quelli tranquilli.

LIMITE DA DICHIARARE SUBITO: i dati finiscono nel 2018. Crabel sostiene che
il decadimento e' recente, quindi questo test **non puo'** dire se l'ORB
funziona oggi: puo' solo dire se funzionava fino al 2018.

Uso: python3 run_orb_sp500.py
Scrive docs/studies/dati/orb_sp500.parquet
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATI = os.environ.get("SPX_CSV", os.path.join(ROOT, "..", "dati_grezzi", "spx"))
FUSO = "America/New_York"
APERTURA, CHIUSURA = (9, 30), (16, 0)     # sessione di cassa
GIORNI_STRETCH = 10
COSTO = 0.5                # punti indice per andata e ritorno (prudente)
RICERCA, VERIFICA = (2011, 2014), (2015, 2018)
FINESTRE = [None, 5, 15, 30, 60]          # None = Stretch di Crabel


def carica():
    """I CSV di HistData: data;apertura;massimo;minimo;chiusura;volume."""
    file = sorted(glob.glob(os.path.join(DATI, "*.csv")))
    if not file:
        raise SystemExit(f"nessun CSV in {DATI}")
    d = pd.concat([pd.read_csv(f, sep=";", header=None,
                               names=["t", "open", "high", "low", "close", "vol"])
                   for f in file], ignore_index=True)
    t = pd.to_datetime(d.t, format="%Y%m%d %H%M%S")
    # i timestamp seguono gia' l'ora di New York, ora legale compresa: e' stato
    # verificato guardando dove cade il minuto piu' agitato in inverno e in
    # estate. ambiguous/nonexistent gestiscono i due minuti del cambio d'ora.
    d = d.set_index(t.dt.tz_localize(FUSO, ambiguous="NaT",
                                     nonexistent="shift_forward"))
    d = d[d.index.notna()].drop(columns="t").sort_index()
    return d[~d.index.duplicated(keep="first")]


def sessioni(d):
    """Solo la sessione di cassa, spezzata per giornata."""
    o = d.index.hour * 60 + d.index.minute
    dentro = (o >= APERTURA[0] * 60 + APERTURA[1]) & (o <= CHIUSURA[0] * 60 + CHIUSURA[1])
    s = d[dentro].copy()
    s["giorno"] = s.index.normalize().tz_localize(None)
    return s


def percorri(alti, bassi, chiu, sopra, sotto, da):
    """Le due soglie di Crabel: il primo toccato apre, l'altro e' lo stop."""
    h_, l_ = alti[da:], bassi[da:]
    su = np.flatnonzero(h_ >= sopra)
    giu = np.flatnonzero(l_ <= sotto)
    k_su = su[0] if len(su) else None
    k_giu = giu[0] if len(giu) else None
    if k_su is None and k_giu is None:
        return None
    if k_giu is None or (k_su is not None and k_su <= k_giu):
        verso, k, entry, stop = 1, k_su, sopra, sotto
    else:
        verso, k, entry, stop = -1, k_giu, sotto, sopra
    rischio = abs(entry - stop)
    if rischio <= 0:
        return None
    dopo_h, dopo_l, dopo_c = h_[k + 1:], l_[k + 1:], chiu[da:][k + 1:]
    if len(dopo_c) < 2:
        return None
    colpo = (np.flatnonzero(dopo_l <= stop) if verso == 1
             else np.flatnonzero(dopo_h >= stop))
    if len(colpo):
        r, motivo = -1.0, "stop"
    else:
        r, motivo = (dopo_c[-1] - entry) * verso / rischio, "chiusura"
    return {"verso": verso, "entry": float(entry), "rischio": float(rischio),
            "r": r - COSTO / rischio, "motivo": motivo}


def main():
    d = carica()
    print(f"{len(d):,} barre, {d.index.min():%Y-%m-%d} -> {d.index.max():%Y-%m-%d}"
          .replace(",", "."), flush=True)
    s = sessioni(d)
    g = s.groupby("giorno")
    prof = pd.DataFrame({"apertura": g.open.first(), "massimo": g.high.max(),
                         "minimo": g.low.min(), "minuti": g.size()})
    prof = prof[prof.minuti >= 300]           # sessioni piene
    minore = np.minimum((prof.apertura - prof.massimo).abs(),
                        (prof.apertura - prof.minimo).abs())
    prof["stretch"] = minore.rolling(GIORNI_STRETCH).mean().shift(1)
    amp = (prof.massimo - prof.minimo).rolling(10).mean().shift(1)
    prof["regime"] = pd.cut(amp.rolling(250, min_periods=120).rank(pct=True),
                            [0, 1 / 3, 2 / 3, 1.01],
                            labels=["basso", "medio", "alto"])
    print(f"sessioni: {len(prof)}", flush=True)

    righe = []
    for giorno, gruppo in s.groupby("giorno"):
        if giorno not in prof.index:
            continue
        riga = prof.loc[giorno]
        alti, bassi, chiu = (gruppo.high.values, gruppo.low.values,
                             gruppo.close.values)
        for f in FINESTRE:
            if f is None:
                st = riga.stretch
                if not np.isfinite(st) or st <= 0:
                    continue
                sopra, sotto, da = riga.apertura + st, riga.apertura - st, 0
            else:
                if len(gruppo) <= f + 5:
                    continue
                sopra, sotto, da = alti[:f].max(), bassi[:f].min(), f
                if sopra <= sotto:
                    continue
            e = percorri(alti, bassi, chiu, sopra, sotto, da)
            if e is None:
                continue
            righe.append({"giorno": giorno, "anno": giorno.year,
                          "finestra": "Stretch" if f is None else f"{f} min",
                          "regime": riga.regime, **e})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "orb_sp500.parquet"), index=False)
    pd.set_option("display.width", 220)

    def riassunto(x):
        r = x.r
        pa = r.groupby(x.anno).sum() if "anno" in x.columns else r
        return pd.Series({"op": len(r), "R": r.sum(), "r_op": r.mean(),
                          "vinte%": (r > 0).mean() * 100,
                          "stop%": (x.motivo == "stop").mean() * 100,
                          "anni+": int((pa > 0).sum()), "anni": pa.size})

    print("\n=== ipotesi A: la regola originale e le finestre classiche")
    for eti, (da, a) in [("ricerca " + str(RICERCA), RICERCA),
                         ("verifica " + str(VERIFICA), VERIFICA)]:
        p = t[(t.anno >= da) & (t.anno <= a)]
        print(f"\n  {eti}")
        print(p.groupby("finestra").apply(riassunto).round(3).to_string())

    print("\n=== ipotesi B: il vantaggio vive nei giorni volatili? (solo Stretch)")
    for eti, (da, a) in [("ricerca", RICERCA), ("verifica", VERIFICA)]:
        p = t[(t.anno >= da) & (t.anno <= a) & (t.finestra == "Stretch")]
        print(f"\n  {eti}")
        print(p.groupby("regime", observed=True).apply(riassunto).round(3).to_string())

    print("\n=== per anno, regola originale")
    print(t[t.finestra == "Stretch"].groupby("anno").apply(riassunto)
          .round(2).to_string())


if __name__ == "__main__":
    main()
