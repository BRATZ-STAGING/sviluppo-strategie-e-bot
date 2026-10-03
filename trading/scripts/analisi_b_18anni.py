#!/usr/bin/env python3
"""Gestione B sui diciotto anni, prima della demo (docs/esperimento-b-registrazione.md).

Nessuna regola nuova: le operazioni sono quelle di ``verifica_bot.py`` (stesso
``genera``, stesso ``filtra``, stessa ``cammina``), la gestione e' la B, il
costo e' lo spread vero per anno (0,40 $ prima del 2020). Misura quello che i
documenti non dicono ancora:

  1. risultato per anno 2009-2026
  2. i drawdown: profondita', DURATA (giorni e operazioni sotto il massimo),
     date di inizio, fondo e recupero
  3. le serie di perdite
  4. lo spegnimento a -15 R: chi avesse avviato la B al primo giorno di un
     mese qualunque, quando si sarebbe fermato e quanto avrebbe perso

Uso: python trading/scripts/analisi_b_18anni.py
Dettaglio: docs/studies/dati/b_operazioni_2009_2026.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(QUI, ".."))
sys.path.insert(0, QUI)

from framework.data import load_m1                                     # noqa: E402
from framework.segnali import genera                                   # noqa: E402
from framework.taratura import UFFICIALE as T                          # noqa: E402
from verifica_bot import BOT, MEDIANA_ATR, SPREAD, Percorsi, filtra, valuta  # noqa: E402

ROOT = os.path.abspath(os.path.join(QUI, "..", ".."))
USCITA = os.path.join(ROOT, "docs", "studies", "dati", "b_operazioni_2009_2026.parquet")
SPEGNI = 15.0          # R dal massimo, docs/esperimento-b-registrazione.md
RISCHIO = 0.24         # % del conto per operazione

pd.set_option("display.width", 200)


def drawdown(r: pd.Series) -> pd.DataFrame:
    """Ogni discesa sotto il massimo: inizio, fondo, recupero, profondita', durata."""
    cum = r.cumsum()
    # il massimo parte dal capitale iniziale (0 R), non dalla prima operazione:
    # se la prima perde, il calo comincia gia' li' (trovato dal verificatore)
    picco = cum.cummax().clip(lower=0)
    sotto = cum < picco - 1e-9
    righe, i, t = [], 0, r.index
    while i < len(r):
        if not sotto.iloc[i]:
            i += 1
            continue
        j = i
        while j < len(r) and sotto.iloc[j]:
            j += 1
        tratto = cum.iloc[i:j]
        fondo = tratto.idxmin()
        righe.append({"inizio": t[i - 1] if i else t[i], "fondo": fondo,
                      "recupero": t[j] if j < len(r) else pd.NaT,
                      "R": float(picco.iloc[i] - tratto.min()),
                      "operazioni": j - i,
                      "giorni": ((t[j] if j < len(r) else t[-1]) - (t[i - 1] if i else t[i])).days})
        i = j
    return pd.DataFrame(righe)


def serie_perdite(r: pd.Series) -> tuple[int, float]:
    peggio = corrente = 0
    costo = costo_peggio = 0.0
    for v in r:
        if v <= 0:
            corrente += 1
            costo += v
            if corrente > peggio:
                peggio, costo_peggio = corrente, costo
        else:
            corrente, costo = 0, 0.0
    return peggio, costo_peggio


def spegnimento(r: pd.Series, partenza: pd.Timestamp):
    """Dalla partenza in poi: quando il calo dal massimo tocca SPEGNI R."""
    x = r[r.index >= partenza]
    if x.empty:
        return None
    cum = x.cumsum()
    calo = cum.cummax().clip(lower=0) - cum
    scatta = calo[calo >= SPEGNI]
    if scatta.empty:
        return {"partenza": partenza, "scatta": pd.NaT, "mesi": np.nan,
                "op": len(x), "R allo stop": float(cum.iloc[-1]), "R se continuava": float(cum.iloc[-1])}
    q = scatta.index[0]
    return {"partenza": partenza, "scatta": q, "mesi": (q - partenza).days / 30.44,
            "op": int((x.index <= q).sum()), "R allo stop": float(cum.loc[q]),
            "R se continuava": float(cum.iloc[-1])}


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = filtra(genera(m1, T, mediana_atr=MEDIANA_ATR))
    percorsi = Percorsi(m1)
    del m1
    b = next(g for g in BOT if g[0].startswith("B"))
    righe = {}
    for nome, costo in (("vero", lambda a: SPREAD.get(a, 0.40)), ("0,30", lambda a: T.spread)):
        det = []
        R, date, anni = valuta(ops, percorsi, b, costo, dettaglio=det)
        righe[nome] = pd.Series(R, index=pd.DatetimeIndex(date)).sort_index()
        if nome == "vero":
            d = pd.DataFrame(det)
            d["R"] = R
            d.to_parquet(USCITA)
    r = righe["vero"]

    print(f"operazioni {len(r)}  (B, spread vero per anno, 0,40 $ prima del 2020)")
    pa = r.groupby(r.index.year).agg(op="size", R="sum", vinte=lambda x: (x > 0).mean() * 100)
    print("\n== 1. per anno (R)")
    print(" ".join(f"{a}:{v:+.1f}" for a, v in pa["R"].items()))
    print(" ".join(f"{a}:{n}" for a, n in pa["op"].items()) + "  (operazioni)")

    print("\n== periodi")
    tab = []
    for nome, a, z in (("2009-2019", 2009, 2019), ("2020-2026", 2020, 2026), ("2009-2026", 2009, 2026)):
        for spread, s in righe.items():
            x = s[(s.index.year >= a) & (s.index.year <= z)]
            dd = drawdown(x)
            perdite, costo = serie_perdite(x)
            tab.append({"periodo": nome, "spread": spread, "op": len(x), "R": x.sum(), "R/op": x.mean(),
                        "vinte%": (x > 0).mean() * 100, "DD R": dd["R"].max() if len(dd) else 0,
                        "DD giorni max": dd["giorni"].max() if len(dd) else 0,
                        "perdite di fila": perdite, "costo serie R": costo,
                        "anni+": f"{int((x.groupby(x.index.year).sum() > 0).sum())}/{x.index.year.nunique()}"})
    print(pd.DataFrame(tab).set_index(["periodo", "spread"]).round(2).to_string())

    print("\n== 2. le cinque discese piu' profonde (2009-2026, spread vero)")
    dd = drawdown(r).sort_values("R", ascending=False).head(5)
    for c in ("inizio", "fondo", "recupero"):
        dd[c] = pd.to_datetime(dd[c]).dt.strftime("%Y-%m-%d").fillna("mai")
    print(dd.round(1).to_string(index=False))
    print(f"(a {RISCHIO}% per operazione: 10 R = {10 * RISCHIO:.1f}% del conto)")

    print(f"\n== 3. spegnimento a -{SPEGNI:.0f} R: partenza il primo di ogni mese")
    sc = pd.DataFrame([s for p in pd.date_range("2009-01-01", "2025-12-01", freq="MS", tz="UTC")
                       if (s := spegnimento(r, p)) is not None])
    sc.to_parquet(USCITA.replace(".parquet", "_spegnimento.parquet"))
    for nome, a, z in (("partenze 2009-2019", 2009, 2019), ("partenze 2020-2025", 2020, 2025)):
        x = sc[(sc["partenza"].dt.year >= a) & (sc["partenza"].dt.year <= z)]
        s = x.dropna(subset=["scatta"])
        print(f"{nome}: {len(x)} partenze, lo stop scatta in {len(s)} ({len(s) / len(x):.0%}); "
              f"mesi mediani prima dello stop {s['mesi'].median():.1f}; "
              f"R allo stop mediano {s['R allo stop'].median():+.1f} (peggiore {s['R allo stop'].min():+.1f}); "
              f"senza stop sarebbe finita a {x['R se continuava'].median():+.1f} R (mediana)")
    for anno in (2009, 2012, 2016, 2018, 2020, 2024):
        s = spegnimento(r, pd.Timestamp(f"{anno}-01-01", tz="UTC"))
        quando = "mai" if pd.isna(s["scatta"]) else f"{s['scatta']:%Y-%m-%d} dopo {s['op']} op"
        print(f"  partenza 01/01/{anno}: stop {quando}, R allo stop {s['R allo stop']:+.1f}, "
              f"fino a oggi senza stop {s['R se continuava']:+.1f}")


if __name__ == "__main__":
    main()
