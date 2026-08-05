#!/usr/bin/env python3
"""Appendice AH: togliere la chiusura serale, tenere solo quella del venerdi'.

Domanda dell'utente (ottica prop firm): se la posizione non viene chiusa alle
21 UTC ma lasciata correre fino a stop, obiettivo o chiusura del venerdi',
quante arrivano davvero all'obiettivo e quante muoiono?

Tre regimi confrontati sulle stesse 348 operazioni ufficiali:
  giornaliera  chiusura alle 21 UTC dello stesso giorno (in vigore)
  settimanale  chiusura al venerdi' 21 UTC
  aperta       nessuna chiusura per tempo (fino a stop/obiettivo, tetto 30 giorni)

Conservativo come sempre: nello stesso minuto lo stop prevale sull'obiettivo,
spread sottratto in R, nessuna stima dei gap (i prezzi M1 li contengono gia').
Misura anche le posizioni sovrapposte, che con la tenuta lunga diventano il
vincolo vero: piu' posizioni aperte insieme = rischio moltiplicato.

Uso: python3 run_tenuta_lunga.py
Scrive docs/studies/dati/tenuta-lunga.parquet
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.gestione import esito_indice                      # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OBIETTIVI = [3.0, 5.0, 10.0]
MOTIVI = {0: "stop", 1: "obiettivo", 2: "scadenza", 3: "pareggio"}


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [op for op in genera(m1, T)
           if all(op[f"c_{tf}"] for tf in T.conferme)
           and all(not op[f"c_{tf}"] for tf in T.ritracciamento)]
    print(f"operazioni ufficiali: {len(ops)}", flush=True)

    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    hi, lo, cl = m1.high.values, m1.low.values, m1.close.values
    righe = []
    for op_id, op in enumerate(ops):
        t_in = pd.Timestamp(op["time"]).tz_convert("UTC")
        segno = 1 if op["lato"] == "long" else -1
        e, k = op["entry"], op["rischio"]
        giorno = t_in.normalize()
        # venerdi' della settimana corrente (weekday 4), alle 21 UTC
        venerdi = giorno + pd.Timedelta(days=(4 - giorno.weekday()) % 7)
        limiti = {
            "giornaliera": giorno + pd.Timedelta(hours=T.ora_chiusura),
            "settimanale": venerdi + pd.Timedelta(hours=T.ora_chiusura),
            "aperta": t_in + pd.Timedelta(days=30),
        }
        a = int(np.searchsorted(idx, t_in.value))
        for regime, fine in limiti.items():
            b = int(np.searchsorted(idx, fine.value))
            if b - a < 2:
                continue
            h_, l_, c_ = hi[a:b], lo[a:b], cl[a:b]
            if segno == 1:
                fav, sfav = (h_ - e) / k, (e - l_) / k
            else:
                fav, sfav = (e - l_) / k, (h_ - e) / k
            for rr in OBIETTIVI:
                r, motivo, j = esito_indice(fav, sfav, rr, be=T.pareggio, costo=0.0)
                if r is None:                     # ancora aperta al limite
                    r = ((float(c_[-1]) - e) if segno == 1
                         else (e - float(c_[-1]))) / k
                    motivo, j = 2, len(c_) - 1
                righe.append({
                    "op_id": op_id, "anno": op["anno"], "regime": regime,
                    "rr": rr, "r": float(r) - op["costo"], "motivo": int(motivo),
                    "minuti": int(j), "uscita": idx[a + j]})

    df = pd.DataFrame(righe)
    dest = os.path.join(ROOT, "docs", "studies", "dati", "tenuta-lunga.parquet")
    df.to_parquet(dest, index=False)

    pd.set_option("display.width", 200)
    print(f"\n{'regime':13s} {'rr':>4s} {'R tot':>7s} {'R/op':>7s} "
          f"{'stop':>11s} {'obiettivo':>11s} {'pareggio':>11s} {'scadenza':>11s} "
          f"{'ore med':>8s} {'anni+':>6s}")
    n = len(ops)
    for regime in ("giornaliera", "settimanale", "aperta"):
        for rr in OBIETTIVI:
            s = df[(df.regime == regime) & (df.rr == rr)]
            if s.empty:
                continue
            q = lambda m: f"{(s.motivo == m).sum():3d} ({(s.motivo == m).mean()*100:4.1f}%)"
            ap = sum(1 for y in s.anno.unique() if s[s.anno == y].r.sum() > 0)
            print(f"{regime:13s} {rr:4.0f} {s.r.sum():+7.1f} {s.r.mean():+7.3f} "
                  f"{q(0):>11s} {q(1):>11s} {q(3):>11s} {q(2):>11s} "
                  f"{s.minuti.mean()/60:8.1f} {ap:3d}/{s.anno.nunique()}")

    # posizioni sovrapposte: il vincolo vero di una prop firm
    print("\nposizioni aperte contemporaneamente (obiettivo 1:10):")
    for regime in ("giornaliera", "settimanale", "aperta"):
        s = df[(df.regime == regime) & (df.rr == 10.0)].sort_values("op_id")
        inizi = np.array([pd.Timestamp(ops[i]["time"]).tz_convert("UTC").value
                          for i in s.op_id])
        fini = s.uscita.values
        insieme = [int(((inizi <= t) & (fini > t)).sum()) for t in inizi]
        print(f"  {regime:13s} media {np.mean(insieme):4.1f}  massimo {max(insieme):3d}  "
              f"giorni di tenuta medi {s.minuti.mean()/60/24:.2f}")
    print(f"\n{dest}")


if __name__ == "__main__":
    main()
