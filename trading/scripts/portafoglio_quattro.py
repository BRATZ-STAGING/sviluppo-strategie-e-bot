#!/usr/bin/env python3
"""Le quattro strategie insieme: quanto rischio si somma davvero.

Decisione dell'utente: avviarle tutte e quattro. La domanda che nessuna scheda
si era ancora posta e' se metterne quattro invece di una **diversifichi**.

LA RISPOSTA E' NO, E IL MOTIVO E' STRUTTURALE. Le quattro strategie condividono
lo stesso identico ingresso: le stesse 333 operazioni, gli stessi minuti, lo
stesso verso. Cambia solo come si esce. Quindi:

  - aprono TUTTE E QUATTRO nello stesso istante, quattro posizioni sullo stesso
    strumento nella stessa direzione;
  - quando l'ingresso e' sbagliato, tutte e quattro perdono, nella stessa
    giornata;
  - la perdita massima del portafoglio non e' la peggiore delle quattro: e'
    quasi la somma.

Questo script lo misura invece di ragionarci: costruisce la curva del
portafoglio sommando i quattro risultati operazione per operazione, e calcola
la correlazione fra le quattro serie.

COSA SIGNIFICA IN PRATICA. Se ognuna e' dimensionata per rendere il 6% annuo
"da sola", il portafoglio non rende il 6%: ne rende circa 24, con un drawdown
proporzionalmente quadruplicato. Chi le avvia tutte e quattro con la taglia
scritta nelle schede sta rischiando quattro volte tanto senza saperlo. La
taglia va divisa.

Uso: XAU_ANNI=2020-2026 python3 portafoglio_quattro.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

from verifica_bot import (CHIUSURA_MIN, GIORNI_MAX, MEDIANA_ATR,  # noqa: E402
                          SPREAD, cammina)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OBIETTIVO_ANNUO = 6.0

BOT = [("in uso", 10.0, 3.0, None, False, None),
       ("A", 8.0, 3.0, None, True, -99.0),
       ("B", 8.0, None, (3.0, 2.0), True, 1.0),
       ("1:2", 2.0, None, None, False, None)]


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [o for o in genera(m1, T, mediana_atr=MEDIANA_ATR)
           if all(o[f"c_{tf}"] for tf in T.conferme)
           and all(not o[f"c_{tf}"] for tf in T.ritracciamento)]
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values

    serie, date, anni = {n: [] for n, *_ in BOT}, [], []
    for o in ops:
        t_in = pd.Timestamp(o["time"]).tz_convert("UTC")
        segno = 1 if o["lato"] == "long" else -1
        e, k = o["entry"], float(o["rischio"])
        a = int(np.searchsorted(idx, t_in.value))
        b = int(np.searchsorted(idx, (t_in + pd.Timedelta(days=GIORNI_MAX)).value))
        if b - a < 2:
            continue
        o_, h_, l_, c_ = ap_[a:b], hi[a:b], lo[a:b], cl[a:b]
        if segno == 1:
            apri, fav, sfav, chiu = ((o_ - e) / k, (h_ - e) / k,
                                     (e - l_) / k, (c_ - e) / k)
        else:
            apri, fav, sfav, chiu = ((e - o_) / k, (e - l_) / k,
                                     (h_ - e) / k, (e - c_) / k)
        t_abs = pd.DatetimeIndex(idx[a:b].astype("datetime64[ns]"), tz="UTC")
        fine_gio = set(np.flatnonzero(
            (t_abs.hour == T.ora_chiusura) & (t_abs.minute == 0)).tolist())
        d = np.diff(idx[a:b]) / 60_000_000_000
        buchi = set(np.flatnonzero(d > CHIUSURA_MIN).tolist())
        s = SPREAD.get(o["anno"], 0.40) / k
        for nome, rr, pareggio, trail, oltre, soglia in BOT:
            x, _ = cammina(apri, fav, sfav, chiu, buchi, fine_gio,
                           rr, pareggio, trail, oltre, soglia)
            serie[nome].append(x - s)
        date.append(t_in)
        anni.append(o["anno"])
    d = pd.DataFrame(serie, index=pd.DatetimeIndex(date))
    anni = np.array(anni)
    pd.set_option("display.width", 220)

    print(f"operazioni comuni a tutte e quattro: {len(d)}")
    print("\n=== quanto si somigliano (correlazione fra i risultati)")
    print(d.corr().round(3).to_string())
    print("\n  giornate in cui perdono TUTTE E QUATTRO: "
          f"{(d < 0).all(axis=1).mean()*100:.1f}% delle operazioni")
    print("  giornate in cui guadagnano tutte e quattro: "
          f"{(d > 0).all(axis=1).mean()*100:.1f}%")

    def conto(n):
        cum = np.cumsum(n)
        dd = float((np.maximum.accumulate(cum) - cum).max())
        pa = pd.Series(n).groupby(anni).sum()
        return pa.mean(), dd

    print("\n=== la taglia per fare il 6% annuo, da sole e insieme")
    f = []
    for nome, *_ in BOT:
        r_anno, dd = conto(d[nome].values)
        taglia = OBIETTIVO_ANNUO / r_anno
        f.append({"strategia": nome, "R/anno": r_anno, "DD R": dd,
                  "rischio/op da sola": taglia, "DD% da sola": dd * taglia})
    somma = d.sum(axis=1).values
    r_anno_p, dd_p = conto(somma)
    taglia_p = OBIETTIVO_ANNUO / r_anno_p
    f.append({"strategia": "TUTTE E QUATTRO", "R/anno": r_anno_p, "DD R": dd_p,
              "rischio/op da sola": taglia_p, "DD% da sola": dd_p * taglia_p})
    print(pd.DataFrame(f).set_index("strategia").round(3).to_string())

    print("\n=== l'errore da non fare")
    tag = {n: OBIETTIVO_ANNUO / conto(d[n].values)[0] for n, *_ in BOT}
    tot = sum(tag.values())
    scalato = sum(d[n].values * tag[n] for n, *_ in BOT)
    cum = np.cumsum(scalato)
    dd_s = float((np.maximum.accumulate(cum) - cum).max())
    pa = pd.Series(scalato).groupby(anni).sum()
    print(f"  se ognuna parte con la SUA taglia da 6% ({', '.join(f'{n} {v:.2f}%' for n, v in tag.items())}):")
    print(f"    rischio totale per segnale: {tot:.2f}% del conto")
    print(f"    rendimento: {pa.mean():.1f}% annuo | perdita massima: {dd_s:.1f}% "
          f"| anno peggiore: {pa.min():+.1f}%")
    print(f"  per restare al 6% annuo TUTTE INSIEME, ogni taglia va divisa per "
          f"{pa.mean()/OBIETTIVO_ANNUO:.1f}:")
    for n, v in tag.items():
        print(f"    {n:<8} {v/(pa.mean()/OBIETTIVO_ANNUO):.3f}% per operazione")
    print(f"    rischio totale per segnale: {tot/(pa.mean()/OBIETTIVO_ANNUO):.2f}% "
          f"| perdita massima {dd_s/(pa.mean()/OBIETTIVO_ANNUO):.1f}%")

    print("\n=== e conviene? quattro insieme contro la sola B")
    r_b, dd_b = conto(d["B"].values)
    t_b = OBIETTIVO_ANNUO / r_b
    print(f"  solo B al 6% annuo:        perdita massima {dd_b*t_b:.2f}%  "
          f"(rischio {t_b:.2f}% per operazione, una posizione alla volta)")
    print(f"  tutte e quattro al 6%:     perdita massima {dd_p*taglia_p:.2f}%  "
          f"(quattro posizioni contemporanee)")


if __name__ == "__main__":
    main()
