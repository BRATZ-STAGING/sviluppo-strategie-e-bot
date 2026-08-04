#!/usr/bin/env python3
"""Appendice BW: il regime dell'oro — misurarlo, e sapere QUANDO e' cambiato.

Decisione dell'utente: *"ricalcola solo sul periodo 2020 perche' da quell'anno
il mercato e' cambiato; sugli anni passati dobbiamo cercare altre strategie,
cosi' se cambiasse di nuovo abbiamo delle riserve pronte da testare."*

E' una posizione difendibile e cambia lo stato di due risultati:

- l'appendice BS (l'1:2 perde -0,27 R/op sul 2009-2019) smette di essere una
  bocciatura e diventa la descrizione di un ALTRO regime;
- il candidato da clienti dell'appendice BR — ingresso ufficiale, obiettivo
  1:2, rischio 0,47% -> 6% annuo con 5,7% di drawdown — torna in gioco.

Ma la posizione ha un prezzo, e va scritto una volta sola con chiarezza: **non
si puo' verificare l'ipotesi di un cambio di regime restando dentro il
regime.** Se si accetta che il 2009-2019 non conti, l'unico fuori campione
rimasto e' il futuro. Il che rende necessarie due cose che questo studio
fornisce:

  1. una misura OGGETTIVA del regime, calcolabile in tempo reale, che dica in
     quale stato siamo adesso invece di deciderlo a occhio;
  2. la risposta alla domanda che decide tutto: **quel segnale sarebbe scattato
     in tempo?** Se l'indicatore avesse detto "regime nuovo" solo nel 2024, non
     serve a nulla; se lo avesse detto nel 2020, e' utilizzabile.

Senza (2), "abbiamo riserve pronte" e' un proposito, non un piano: le riserve
servono solo se qualcuno suona la campana.

COSA SI MISURA, tutto causale (medie mobili spostate di uno, mai il futuro):
  - escursione: ATR giornaliero e ampiezza mediana della candela M1;
  - persistenza: quanto la prima meta' della giornata predice la seconda —
    e' il meccanismo su cui vive una strategia di continuazione;
  - notte contro giorno: quanta parte dell'escursione si forma fuori dalle ore
    di Londra e New York. E' l'indicatore che la letteratura sull'ORB indica
    come causa della morte della strategia (Crabel: i mercati 24 ore hanno
    tolto valore all'apertura);
  - direzionalita': quanto il prezzo si sposta rispetto a quanto si agita
    (spostamento netto diviso percorso totale, sui 20 giorni).

IPOTESI PRE-REGISTRATE:
  A. almeno una delle misure separa il 2009-2019 dal 2020-2026 in modo netto,
     non graduale (se la separazione e' graduale, "regime" e' una parola per
     dire "e' cambiato lentamente" e non ci si puo' costruire un interruttore);
  B. l'interruttore costruito su quella misura sarebbe scattato entro il 2020,
     cioe' in tempo per essere utile;
  C. il rendimento della strategia ufficiale segue l'interruttore: positivo
     quando e' acceso, negativo quando e' spento. Se non lo segue, l'indicatore
     misura qualcosa di vero ma di irrilevante.

Uso: XAU_ANNI=2009-2026 python3 run_regime_oro.py
Scrive docs/studies/dati/regime_oro.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.volatility import daily_atr, daily_bars           # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GIORNO_ORE = (7, 21)          # londra + new york, il resto e' "notte"
FINESTRA = 250                # un anno di borsa, per le medie lunghe


def misure(m1):
    """Le quattro misure del regime, una riga per giornata."""
    d1 = daily_bars(m1)
    atr = daily_atr(m1, 14)
    g = m1.index.normalize()

    # ampiezza mediana della candela M1: il "respiro" del mercato
    resp = (m1.high - m1.low).groupby(g).median()

    # notte contro giorno: quanta escursione si forma fuori da Londra+NY
    ore = m1.index.hour
    giorno = (ore >= GIORNO_ORE[0]) & (ore < GIORNO_ORE[1])
    esc_gio = (m1[giorno].high.groupby(g[giorno]).max()
               - m1[giorno].low.groupby(g[giorno]).min())
    esc_tot = d1.high - d1.low
    quota_notte = 1 - (esc_gio / esc_tot)

    # persistenza: la prima meta' della giornata predice la seconda?
    # si misura come correlazione mobile fra i due movimenti, ed e' il
    # meccanismo su cui vive qualunque strategia di continuazione
    meta = ore < 14
    p_apre = m1[meta].open.groupby(g[meta]).first()
    p_meta = m1[meta].close.groupby(g[meta]).last()
    p_fine = m1[~meta].close.groupby(g[~meta]).last()
    m1_mov = (p_meta - p_apre)
    m2_mov = (p_fine - p_meta)

    # direzionalita': spostamento netto diviso percorso, sui 20 giorni
    netto = (d1.close - d1.close.shift(20)).abs()
    percorso = (d1.close - d1.close.shift(1)).abs().rolling(20).sum()

    d = pd.DataFrame({
        "atr": atr, "respiro": resp, "quota_notte": quota_notte,
        "mov1": m1_mov, "mov2": m2_mov,
        "direzionalita": netto / percorso.replace(0, np.nan),
        "chiusura": d1.close,
    }).dropna(subset=["atr"])
    d["anno"] = d.index.year
    # persistenza mobile: correlazione a 60 giorni fra prima e seconda meta',
    # spostata di uno cosi' e' nota la mattina in cui serve
    d["persistenza"] = d.mov1.rolling(60).corr(d.mov2).shift(1)
    # l'escursione RELATIVA al prezzo: l'oro e' passato da 1.200 a 4.000 $,
    # quindi l'ATR in dollari cresce anche senza che cambi niente. Questa e'
    # la misura che toglie quell'effetto e resta confrontabile fra epoche
    d["atr_rel"] = (d.atr / d.chiusura * 100).rolling(20).mean().shift(1)
    return d


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    d = misure(m1)
    d.to_parquet(os.path.join(ROOT, "docs", "studies", "dati", "regime_oro.parquet"))
    pd.set_option("display.width", 230)

    print("=== ipotesi A: le misure separano i due periodi? (mediana per anno)")
    a = d.groupby("anno").agg(
        giorni=("atr", "size"), atr=("atr", "median"),
        **{"atr% del prezzo": ("atr_rel", "median")},
        respiro=("respiro", "median"),
        **{"quota notte": ("quota_notte", "median"),
           "persistenza": ("persistenza", "median"),
           "direzionalita": ("direzionalita", "median")})
    print(a.round(3).to_string())

    print("\n=== separazione fra i due regimi")
    for col in ("atr_rel", "respiro", "quota_notte", "persistenza", "direzionalita"):
        v = d[d.anno <= 2019][col].dropna()
        n = d[d.anno >= 2020][col].dropna()
        if not len(v) or not len(n):
            continue
        # quanto si sovrappongono: la frazione del vecchio regime che cade
        # dentro l'intervallo centrale del nuovo. Poca sovrapposizione =
        # interruttore possibile; molta = differenza solo in media
        lo_, hi_ = n.quantile(.1), n.quantile(.9)
        sovr = ((v >= lo_) & (v <= hi_)).mean() * 100
        print(f"  {col:<15} 2009-19 mediana {v.median():7.3f} | "
              f"2020-26 {n.median():7.3f} | sovrapposizione {sovr:5.1f}%")

    print("\n=== ipotesi B: un interruttore causale sarebbe scattato in tempo?")
    # regola semplice e senza parametri pescati: il regime e' NUOVO quando
    # l'escursione relativa a 20 giorni supera la sua mediana degli ultimi
    # FINESTRA giorni per almeno 20 sedute di fila. Tutto noto il giorno stesso.
    rif = d.atr_rel.rolling(FINESTRA, min_periods=120).median().shift(1)
    sopra = (d.atr_rel > rif).astype(float)
    acceso = sopra.rolling(20).min() == 1          # venti sedute consecutive
    d["acceso"] = acceso.fillna(False)
    cambi = d.acceso.astype(int).diff()
    accensioni = d.index[cambi == 1]
    spegnimenti = d.index[cambi == -1]
    print(f"  accensioni: {len(accensioni)} | spegnimenti: {len(spegnimenti)}")
    print("  prime accensioni dopo il 2019: "
          + ", ".join(x.strftime("%Y-%m-%d")
                      for x in accensioni[accensioni >= "2019-06-01"][:6]))
    print("  quota di giornate accese per anno:")
    print(d.groupby("anno").acceso.mean().mul(100).round(1).to_string())


if __name__ == "__main__":
    main()
