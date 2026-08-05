#!/usr/bin/env python3
"""Appendice AS: A e B con i gap CONTRARI pagati davvero.

Difetto del modello usato finora, segnalato dall'utente: quando il prezzo
riapre oltre lo stop (fine settimana, o un salto violento), l'uscita non
avviene al livello dello stop ma al prezzo di riapertura, che e' peggiore. Il
motore assumeva il riempimento esatto al livello, quindi contava i gap
favorevoli (l'obiettivo saltato viene incassato) senza pagare quelli contrari.

Qui si guarda l'APERTURA di ogni minuto: se la candela apre gia' oltre lo stop
si esce li'; se apre gia' oltre l'obiettivo si incassa li'. Simmetrico e
onesto.

La configurazione in vigore non e' toccata dal problema — apre fra le 7 e le
19 e chiude alle 21 dello stesso giorno, quindi non attraversa mai una
riapertura — ma viene ricalcolata lo stesso come controllo.

Uso: python3 run_gap_reali.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

from run_scale_trailing import GESTIONI                          # noqa: E402
from run_swap_reale import (CONTRATTO, GIORNI_MAX, SWAP_LONG,    # noqa: E402
                            SWAP_SHORT, notti)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

PROVE = [
    ("in uso · 1:10, sera",        "pari a +3R (in uso)", 10, "giornaliera"),
    ("A · pari +3R 1:8, venerdi'", "pari a +3R (in uso)", 8,  "settimanale"),
    ("B · trail 1:8, venerdi'",    "trail MFE-2 da +3R",  8,  "settimanale"),
    ("B · trail 1:8, aperta",      "trail MFE-2 da +3R",  8,  "aperta"),
]


def esito_gap(apri, fav, sfav, r_eod, rr, scala, trail):
    """Esito con i salti pagati: conta l'apertura di ogni minuto.

    Ritorna (R, motivo, minuto, R_perso_nel_gap). L'ultimo valore e' quanto
    l'uscita e' stata peggiore del livello previsto: e' il costo dei gap.
    """
    livello = -1.0
    mfe = 0.0
    for i in range(len(fav)):
        # 1) la candela apre gia' oltre lo stop? si esce li', non al livello
        if apri[i] <= livello:
            return apri[i], (0 if livello <= -1 else 5), i, livello - apri[i]
        # 2) apre gia' oltre l'obiettivo? si incassa li' (gap a favore)
        if apri[i] >= rr:
            return apri[i], 1, i, 0.0
        # 3) poi il normale ordine: stop, obiettivo, protezione
        if sfav[i] >= -livello:
            return livello, (0 if livello <= -1 else (3 if livello == 0 else 4)), i, 0.0
        if fav[i] >= rr:
            return float(rr), 1, i, 0.0
        mfe = max(mfe, fav[i])
        for soglia, dove in scala:
            if mfe >= soglia:
                livello = max(livello, float(dove))
        if trail is not None and mfe >= trail[0]:
            livello = max(livello, mfe - trail[1])
    return max(r_eod, livello), 2, len(fav) - 1, 0.0


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [op for op in genera(m1, T)
           if all(op[f"c_{tf}"] for tf in T.conferme)
           and all(not op[f"c_{tf}"] for tf in T.ritracciamento)]
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    op_, hi, lo, cl = (m1.open.values, m1.high.values, m1.low.values,
                       m1.close.values)
    anni = np.array([o["anno"] for o in ops])
    print(f"operazioni: {len(ops)}\n", flush=True)

    for eti, nome, rr, regime in PROVE:
        scala, trail = next((s, t) for n, s, t in GESTIONI if n == nome)
        R, S, persi, n_gap = [], [], [], 0
        for o in ops:
            t_in = pd.Timestamp(o["time"]).tz_convert("UTC")
            segno = 1 if o["lato"] == "long" else -1
            e, k = o["entry"], o["rischio"]
            g = t_in.normalize()
            fine = {"giornaliera": g + pd.Timedelta(hours=T.ora_chiusura),
                    "settimanale": g + pd.Timedelta(days=(4 - g.weekday()) % 7)
                    + pd.Timedelta(hours=T.ora_chiusura),
                    "aperta": t_in + pd.Timedelta(days=GIORNI_MAX)}[regime]
            a = int(np.searchsorted(idx, t_in.value))
            b = int(np.searchsorted(idx, fine.value))
            o_, h_, l_, c_ = op_[a:b], hi[a:b], lo[a:b], cl[a:b]
            if segno == 1:
                apri, fav, sfav = (o_ - e) / k, (h_ - e) / k, (e - l_) / k
            else:
                apri, fav, sfav = (e - o_) / k, (e - l_) / k, (h_ - e) / k
            r_eod = ((float(c_[-1]) - e) if segno == 1 else (e - float(c_[-1]))) / k
            x, m, j, perso = esito_gap(apri, fav, sfav, r_eod, rr, scala, trail)
            t_out = pd.Timestamp(idx[a + j], unit="ns", tz="UTC")
            p = notti(t_in, t_out)
            R.append(x - o["costo"])
            S.append(p * (SWAP_LONG if segno == 1 else SWAP_SHORT) / (CONTRATTO * k))
            persi.append(perso)
            n_gap += perso > 1e-9
        R, S, persi = np.array(R), np.array(S), np.array(persi)
        netto = R + S
        cum = np.cumsum(netto)
        dd = (np.maximum.accumulate(cum) - cum).max()
        ap = sum(1 for y in np.unique(anni) if netto[anni == y].sum() > 0)
        print(f"{eti}")
        print(f"   netto {netto.sum():+7.1f} R  ({10000 + 100*netto.sum():,.0f} EUR)"
              .replace(",", ".") +
              f" | swap {S.sum():+6.1f} | GAP CONTRARI {persi.sum():+6.1f} R su "
              f"{n_gap} operazioni")
        print(f"   vinte {(netto>0).mean()*100:4.1f}% | DD {dd:5.1f} R | anni+ {ap}/7 | "
              f"peggiore {min(netto[anni==y].sum() for y in np.unique(anni)):+6.1f} R | "
              f"gap peggiore {persi.max():.1f} R\n")


if __name__ == "__main__":
    main()
