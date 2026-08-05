#!/usr/bin/env python3
"""Il pareggio spostato uno o due dollari SOPRA l'ingresso.

Proposta dell'utente, nata dalla scoperta che la strategia "in uso" chiude 60
operazioni su 333 esattamente a pareggio: dopo lo spread sono leggermente
negative, e sono quelle che allungano le serie perdenti da 11 a 23.

L'IDEA. Invece di portare lo stop AL prezzo d'ingresso, portarlo uno o due
dollari OLTRE. Cosi' quelle uscite smettono di essere pareggi e diventano
piccole vittorie: la serie perdente si spezza davvero, non per convenzione di
conteggio.

IL COSTO, che va misurato e non ipotizzato. Uno stop sopra l'ingresso e' piu'
VICINO al prezzo di uno stop all'ingresso. Quindi viene toccato piu' spesso, e
alcune operazioni che sarebbero corse fino all'obiettivo vengono tagliate a
+1 o +2 dollari. Si guadagna sulle sessanta che erano pareggi, si perde sulle
poche che sarebbero diventate 1:8 o 1:10 — e quelle valgono otto o dieci volte
tanto. Il saldo non e' ovvio a priori: dipende da quante ne taglia.

VARIANTI, in dollari (la proposta) e in R (la stessa idea resa indipendente
dalla taglia dello stop, che va da 1 a 15 $ secondo la volatilita'):
  0 $ (attuale) · +1 $ · +2 $ · +0,25R · +0,50R

Applicate a tutte e quattro le gestioni, cosi' si vede anche l'effetto sulla C
(1:2 secco), che oggi non ha nessuno spostamento dello stop.

IPOTESI PRE-REGISTRATE:
  A. le serie perdenti si accorciano in modo netto per "in uso" e A;
  B. il rendimento totale CALA, perche' la coda tagliata vale piu' dei
     pareggi recuperati;
  C. il rapporto rendimento/perdita massima migliora comunque, perche' la
     perdita massima cala piu' di quanto cali il rendimento. Se C e' falsa, la
     proposta va scartata; se e' vera, e' un miglioramento per una sfida anche
     se rende meno.

Uso: XAU_ANNI=2020-2026 python3 run_pareggio_sopra.py
"""
from __future__ import annotations
import os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from framework.data import load_m1                               # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402
from verifica_bot import (CHIUSURA_MIN, GIORNI_MAX, MEDIANA_ATR,  # noqa: E402
                          SPREAD)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BOT = [("in uso", 10.0, 3.0, None, False, None),
       ("A", 8.0, 3.0, None, True, -99.0),
       ("B", 8.0, None, (3.0, 2.0), True, 1.0),
       ("C 1:2", 2.0, 1.0, None, False, None)]   # C con pareggio a +1R, per vedere l'effetto


def cammina(apri, fav, sfav, chiu, buchi, fine_gio, rr, pareggio, trail,
            oltre_giorno, soglia_weekend, sopra):
    """Come verifica_bot.cammina, ma il pareggio si ferma a ``sopra`` R e non a 0."""
    livello, mfe = -1.0, 0.0
    for i in range(len(fav)):
        if apri[i] <= livello:
            return apri[i], "gap"
        if apri[i] >= rr:
            return apri[i], "gap+"
        if sfav[i] >= -livello:
            return livello, ("stop" if livello <= -1
                             else "pareggio" if livello <= 0 else "protetto")
        if fav[i] >= rr:
            return float(rr), "obiettivo"
        mfe = max(mfe, fav[i])
        if pareggio is not None and mfe >= pareggio:
            livello = max(livello, float(sopra))
        if trail is not None and mfe >= trail[0]:
            livello = max(livello, mfe - trail[1])
        if not oltre_giorno and i in fine_gio:
            return chiu[i], "fine giornata"
        if i in buchi and soglia_weekend is not None and chiu[i] < soglia_weekend:
            return chiu[i], "chiusa venerdi'"
    return max(chiu[-1], livello), "scadenza"


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [o for o in genera(m1, T, mediana_atr=MEDIANA_ATR)
           if all(o[f"c_{tf}"] for tf in T.conferme)
           and all(not o[f"c_{tf}"] for tf in T.ritracciamento)]
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values
    VAR = [("0 $ (attuale)", "fisso", 0.0), ("+1 $", "dollari", 1.0),
           ("+2 $", "dollari", 2.0), ("+0,25 R", "erre", 0.25),
           ("+0,50 R", "erre", 0.50)]
    righe = []
    for o in ops:
        t = pd.Timestamp(o["time"]).tz_convert("UTC")
        sg = 1 if o["lato"] == "long" else -1
        e, k = o["entry"], float(o["rischio"])
        a = int(np.searchsorted(idx, t.value))
        b = int(np.searchsorted(idx, (t + pd.Timedelta(days=GIORNI_MAX)).value))
        if b - a < 2:
            continue
        o_, h_, l_, c_ = ap_[a:b], hi[a:b], lo[a:b], cl[a:b]
        if sg == 1:
            A, F, S, C = (o_-e)/k, (h_-e)/k, (e-l_)/k, (c_-e)/k
        else:
            A, F, S, C = (e-o_)/k, (e-l_)/k, (h_-e)/k, (e-c_)/k
        ta = pd.DatetimeIndex(idx[a:b].astype("datetime64[ns]"), tz="UTC")
        fg = set(np.flatnonzero((ta.hour == T.ora_chiusura) & (ta.minute == 0)).tolist())
        dd = np.diff(idx[a:b]) / 60_000_000_000
        bu = set(np.flatnonzero(dd > CHIUSURA_MIN).tolist())
        s = SPREAD.get(o["anno"], 0.40) / k
        for n, rr, pa, tr, ol, so in BOT:
            for eti, modo, v in VAR:
                sopra = 0.0 if modo == "fisso" else (v / k if modo == "dollari" else v)
                x, mot = cammina(A, F, S, C, bu, fg, rr, pa, tr, ol, so, sopra)
                righe.append({"bot": n, "variante": eti, "anno": o["anno"],
                              "netto": x - s, "motivo": mot})
    t = pd.DataFrame(righe)
    pd.set_option("display.width", 240)

    def m(x):
        n = x.netto.values
        cum = np.cumsum(n)
        dd_ = float((np.maximum.accumulate(cum) - cum).max())
        pa = x.netto.groupby(x.anno).sum()
        cur = best = 0
        curR = bestR = 0.0
        for v in n:
            if v <= 0:
                cur += 1; curR += v
            else:
                best = max(best, cur); bestR = min(bestR, curR); cur = 0; curR = 0.0
        best = max(best, cur); bestR = min(bestR, curR)
        return pd.Series({"R": n.sum(), "R/op": n.mean(), "vinte%": (n > 0).mean()*100,
                          "DD R": dd_, "R/DD": n.sum()/dd_ if dd_ > 0 else np.nan,
                          "perdite fila": best, "costo serie R": bestR,
                          "anni+": int((pa > 0).sum())})
    for n, *_ in BOT:
        print(f"\n=== {n}")
        print(t[t.bot == n].groupby("variante", sort=False).apply(m).round(2).to_string())


if __name__ == "__main__":
    main()
