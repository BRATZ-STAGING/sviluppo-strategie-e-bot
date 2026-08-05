#!/usr/bin/env python3
"""Appendice BZ: la scalp sul solo 2020-2026, giudicata col criterio del cliente.

Decisione dell'utente: *"torniamo al periodo 2020-2026 dove avevamo gia' buoni
dati e ripartiamo da li' per la strategia scalp"*.

Questo studio non aggiunge nessuna idea nuova. Rimette insieme cio' che le
appendici di oggi hanno gia' misurato, applicando finalmente **il criterio
giusto** — quello dell'appendice BR: non "chi rende di piu'" ma "chi arriva al
6% annuo con il buco piu' piccolo e la strada meno spaventosa".

PERCHE' SERVIVA RIFARLO. L'appendice BT ha misurato la curva della larghezza
dello stop su tre periodi e l'ha giudicata sul criterio vecchio (netto R/op
positivo su TUTTI e tre), bocciando tutto per colpa del 2009-2019. Ma dentro
il solo 2020-2026 quella curva racconta un'altra storia, e non era stata
guardata:

    stop 8 $, obiettivo 1:2   -> +0,132 (2020-22) e +0,075 (2023-26)
    stop 8 $, obiettivo 1:3   -> +0,167 e +0,159
    stop 12 $, obiettivo 1:2  -> +0,139 e +0,118

cioe' un **altopiano** positivo in entrambi i sottoperiodi, non una cella
isolata. Un altopiano largo e' molto piu' difendibile di un massimo puntuale:
se il risultato dipendesse dal caso, le celle adiacenti non sarebbero
d'accordo fra loro.

IL PREZZO DA PAGARE, dichiarato subito: a queste larghezze **non e' piu' uno
scalp**. La durata mediana passa da 1 ora (stop 3 $) a 7,5 ore (8 $) e 23 ore
(13 $). Lo studio riporta durata e quota di operazioni tenute oltre la
giornata per ogni cella, cosi' la scelta e' informata invece che nascosta.

COSA SI MISURA, per ogni cella (larghezza x obiettivo):
  - il vantaggio in ricerca 2020-2022 e in verifica 2023-2026, sempre entrambi;
  - poi, per le sole celle positive in ENTRAMBI, le misure da prodotto:
    la taglia che porta al 6% annuo, il drawdown che ne risulta, i mesi
    positivi, le perdite consecutive e la durata tipica.

Nessuna cella viene scelta qui dentro: si riporta la mappa completa e si lascia
vedere dove sta l'altopiano.

Uso: python3 run_scalp_2020.py
Legge docs/studies/dati/larghezza_stop.parquet (prodotto dall'appendice BT)
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OBIETTIVO_ANNUO = 6.0
RICERCA, VERIFICA = (2020, 2022), (2023, 2026)
LARGHEZZE = [3, 4, 5, 6, 8, 10, 12, 14, 16]


def misure(x):
    """Le misure da prodotto, riscalate perche' rendano il 6% annuo."""
    n = x.netto.values
    per_anno = x.netto.groupby(x.anno).sum()
    r_anno = per_anno.mean()
    if r_anno <= 0:
        return None
    cum = np.cumsum(n)
    dd = float((np.maximum.accumulate(cum) - cum).max())
    if dd <= 0:
        return None
    taglia = OBIETTIVO_ANNUO / r_anno
    peggio = corrente = 0
    for v in n:
        corrente = corrente + 1 if v <= 0 else 0
        peggio = max(peggio, corrente)
    mesi = pd.Series(n, index=pd.DatetimeIndex(x.data)).resample("ME").sum()
    mesi = mesi[mesi != 0]
    return {"op/anno": len(n) / per_anno.size, "netto R/op": n.mean(),
            "vinte%": (n > 0).mean() * 100,
            "rischio/op%": taglia, "DD max%": dd * taglia,
            "anno peggiore%": per_anno.min() * taglia,
            "anni+": f"{int((per_anno > 0).sum())}/{per_anno.size}",
            "mesi+%": (mesi > 0).mean() * 100, "perdite di fila": peggio,
            "ore mediane": x.minuti.median() / 60,
            "oltre 1 giorno%": (x.minuti > 60 * 24).mean() * 100,
            "rend/DD": OBIETTIVO_ANNUO / (dd * taglia)}


def main():
    t = pd.read_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                                     "larghezza_stop.parquet"))
    t = t[t.anno >= 2020]
    pd.set_option("display.width", 250)
    print(f"operazioni-cella sul 2020-2026: {len(t):,}".replace(",", "."))

    for eti_c, uff in [("ufficiali", True), ("largo", False)]:
        p = t[t.ufficiale == uff]
        print(f"\n\n=== campione {eti_c} — mappa del netto R/op "
              f"(ricerca {RICERCA} | verifica {VERIFICA})")
        righe = []
        for rr in sorted(p.rr.unique()):
            for w in LARGHEZZE:
                x = p[(p.rr == rr) & (p["stop$"] == w)]
                if x.empty:
                    continue
                a = x[(x.anno >= RICERCA[0]) & (x.anno <= RICERCA[1])]
                b = x[(x.anno >= VERIFICA[0]) & (x.anno <= VERIFICA[1])]
                if a.empty or b.empty:
                    continue
                righe.append({
                    "obiettivo": f"1:{rr:g}", "stop $": w,
                    "op/anno": len(x) / x.anno.nunique(),
                    "costo%R": x.costo.mean() * 100,
                    "ricerca": a.netto.mean(), "verifica": b.netto.mean(),
                    "entrambi+": "si" if (a.netto.mean() > 0 and b.netto.mean() > 0) else "",
                    "ore mediane": x.minuti.median() / 60})
        m = pd.DataFrame(righe)
        print(m.round(3).to_string(index=False))

        buone = m[m["entrambi+"] == "si"]
        if buone.empty:
            print("  nessuna cella positiva in entrambi i sottoperiodi")
            continue
        print(f"\n  --- le {len(buone)} celle positive in entrambi, "
              f"riscalate al {OBIETTIVO_ANNUO:.0f}% annuo su tutto il 2020-2026")
        f = []
        for _, r in buone.iterrows():
            rr = float(r["obiettivo"].split(":")[1])
            x = p[(p.rr == rr) & (p["stop$"] == r["stop $"])].sort_values("data")
            mm = misure(x)
            if mm:
                f.append({"cella": f"stop {r['stop $']:g} $ · {r['obiettivo']}", **mm})
        if f:
            print(pd.DataFrame(f).set_index("cella").round(2).to_string())


if __name__ == "__main__":
    main()
