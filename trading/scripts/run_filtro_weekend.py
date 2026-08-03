#!/usr/bin/env python3
"""Appendice AT: filtro sul fine settimana e stop portato alla chiusura.

Due idee dell'utente per rendere sostenibile il tenere aperto:

1. **filtro**: attraversare il fine settimana SOLO se l'operazione e' gia'
   sopra una soglia (+3R o +5R); altrimenti si chiude il venerdi'. Se il
   margine e' grande, un salto contrario fa meno danno.
2. **stop alla chiusura**: prima del fine settimana lo stop viene portato al
   prezzo di chiusura del venerdi', per congelare quello che si e' guadagnato.

Motore completo: gap pagati al prezzo di riapertura (appendice AS) e swap
reale di FP (appendice AQ).

Uso: python3 run_filtro_weekend.py
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
from run_swap_reale import (CONTRATTO, SWAP_LONG, SWAP_SHORT,    # noqa: E402
                            notti)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GIORNI_MAX = 30
CHIUSURA_MIN = 120        # oltre due ore fra due candele = mercato chiuso


def cammina(apri, fav, sfav, chiu, buchi, rr, scala, trail,
            soglia=None, blocca=False):
    """Percorre l'operazione minuto per minuto.

    ``buchi`` sono gli indici DOPO i quali il mercato chiude (fine settimana).
    ``soglia``: si resta aperti solo se a quel punto si e' sopra quella soglia,
    altrimenti si esce alla chiusura. ``blocca`` puo' essere "chiusura" (stop
    al prezzo del venerdi', che azzera il margine) oppure "pareggio" (stop al
    prezzo d'ingresso: garantisce di non perdere e lascia intatto il margine).
    """
    livello = -1.0
    mfe = 0.0
    for i in range(len(fav)):
        if apri[i] <= livello:                    # riapre gia' oltre lo stop
            return apri[i], 5, i
        if apri[i] >= rr:                         # riapre gia' oltre l'obiettivo
            return apri[i], 1, i
        if sfav[i] >= -livello:
            return livello, (0 if livello <= -1 else (3 if livello == 0 else 4)), i
        if fav[i] >= rr:
            return float(rr), 1, i
        mfe = max(mfe, fav[i])
        for s_, dv in scala:
            if mfe >= s_:
                livello = max(livello, float(dv))
        if trail is not None and mfe >= trail[0]:
            livello = max(livello, mfe - trail[1])
        if i in buchi:                            # si va verso il fine settimana
            if soglia is not None and chiu[i] < soglia:
                return chiu[i], 6, i              # chiusa prima della sosta
            if blocca == "chiusura":
                livello = max(livello, chiu[i])
            elif blocca == "pareggio":
                livello = max(livello, 0.0)
            elif isinstance(blocca, (int, float)):
                livello = max(livello, float(blocca))
    return max(chiu[-1], livello), 2, len(fav) - 1


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [op for op in genera(m1, T)
           if all(op[f"c_{tf}"] for tf in T.conferme)
           and all(not op[f"c_{tf}"] for tf in T.ritracciamento)]
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = (m1.open.values, m1.high.values, m1.low.values,
                       m1.close.values)
    anni = np.array([o["anno"] for o in ops])
    print(f"operazioni: {len(ops)}\n", flush=True)

    PROVE = [
        ("chiude venerdi'",              None, None,       True),
        ("sempre aperta",                None, None,       False),
        ("solo sopra +1R",               1.0,  None,       False),
        ("solo sopra +3R",               3.0,  None,       False),
        ("+3R e stop a +1R (proposta)",  3.0,  1.0,        False),
        ("+3R e stop a pareggio",        3.0,  "pareggio", False),
        ("+1R e stop a pareggio",        1.0,  "pareggio", False),
    ]
    scala, trail = next((s, t) for n, s, t in GESTIONI
                        if n == "trail MFE-2 da +3R")

    for eti, soglia, blocca, solo_venerdi in PROVE:
        R, S, motivi = [], [], []
        for o in ops:
            t_in = pd.Timestamp(o["time"]).tz_convert("UTC")
            segno = 1 if o["lato"] == "long" else -1
            e, k = o["entry"], o["rischio"]
            g = t_in.normalize()
            fine = (g + pd.Timedelta(days=(4 - g.weekday()) % 7)
                    + pd.Timedelta(hours=T.ora_chiusura) if solo_venerdi
                    else t_in + pd.Timedelta(days=GIORNI_MAX))
            a = int(np.searchsorted(idx, t_in.value))
            b = int(np.searchsorted(idx, fine.value))
            o_, h_, l_, c_ = ap_[a:b], hi[a:b], lo[a:b], cl[a:b]
            if segno == 1:
                apri, fav, sfav = (o_ - e) / k, (h_ - e) / k, (e - l_) / k
                chiu = (c_ - e) / k
            else:
                apri, fav, sfav = (e - o_) / k, (e - l_) / k, (h_ - e) / k
                chiu = (e - c_) / k
            d = np.diff(idx[a:b]) / 60_000_000_000
            buchi = set(np.flatnonzero(d > CHIUSURA_MIN).tolist())
            x, m, j = cammina(apri, fav, sfav, chiu, buchi, 8.0, scala, trail,
                              soglia, blocca)
            t_out = pd.Timestamp(idx[a + j], unit="ns", tz="UTC")
            p = notti(t_in, t_out)
            R.append(x - o["costo"])
            S.append(p * (SWAP_LONG if segno == 1 else SWAP_SHORT) / (CONTRATTO * k))
            motivi.append(m)
        R, S = np.array(R), np.array(S)
        mo = np.array(motivi)
        netto = R + S
        cum = np.cumsum(netto)
        dd = (np.maximum.accumulate(cum) - cum).max()
        ap = sum(1 for y in np.unique(anni) if netto[anni == y].sum() > 0)
        print(f"{eti}")
        print(f"   netto {netto.sum():+7.1f} R ({10000 + 100*netto.sum():,.0f} EUR)"
              .replace(",", ".") +
              f" | swap {S.sum():+6.1f} | vinte {(netto>0).mean()*100:4.1f}% | "
              f"DD {dd:5.1f} R | anni+ {ap}/7")
        print(f"   uscite: stop {int((mo==0).sum()):3d} · obiettivo "
              f"{int((mo==1).sum()):3d} · in utile {int((mo==4).sum()):3d} · "
              f"gap {int((mo==5).sum()):2d} · chiuse dal filtro "
              f"{int((mo==6).sum()):2d} · scadenza {int((mo==2).sum()):3d}\n")


if __name__ == "__main__":
    main()
