#!/usr/bin/env python3
"""Le tre strategie da mettere in produzione, ricontrollate con lo spread VERO.

Le schede in ``bots/SCHEDE-STRATEGIE.md`` sono state scritte quando il costo
era la costante della taratura, **0,30 $**. L'appendice BN ha poi misurato lo
scarto denaro-lettera su 6,1 milioni di tick e ha trovato che il costo vero e'
0,33-0,40 $ fino al 2024 e **0,63 $ dal 2025**. Prima di far girare qualcosa
con soldi veri i numeri delle schede vanno rifatti con quel costo, altrimenti
si parte con un'aspettativa ottimistica del 5-6%.

Questo script non cambia nessuna regola: rigenera le stesse operazioni e
riapplica le stesse tre gestioni, sostituendo solo il costo. In piu' riporta le
misure che servono a chi deve DECIDERE se avviarlo — drawdown, mesi positivi,
perdite consecutive — e non solo il totale in R.

LE TRE GESTIONI, come congelate nelle schede:
  in uso  obiettivo 1:10, stop a pareggio da +3R, chiusura EOD alle 21 UTC
  A       obiettivo 1:8, stop a pareggio da +3R, si tiene oltre la giornata ma
          si chiude il venerdi' sera
  B       obiettivo 1:8, da +3R lo stop insegue l'MFE a distanza 2R, e si
          attraversa il fine settimana solo se si e' gia' sopra +1R
piu' la quarta emersa oggi (appendice BR), che le schede non contengono:
  1:2     obiettivo 1:2 secco, niente pareggio, chiusura EOD

Uso: XAU_ANNI=2020-2026 python3 verifica_bot.py
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

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MEDIANA_ATR = 25.5968
GIORNI_MAX = 30
CHIUSURA_MIN = 120        # oltre due ore fra due candele = mercato chiuso
SPREAD = {2020: 0.35, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}


def cammina(apri, fav, sfav, chiu, buchi, fine_gio, rr, pareggio, trail,
            oltre_giorno, soglia_weekend):
    """Un'operazione minuto per minuto.

    ``fine_gio`` sono gli indici dopo i quali scatta la chiusura EOD;
    ``buchi`` quelli dopo cui il mercato chiude per il fine settimana.
    A parita' di minuto lo stop prevale sull'obiettivo, come in tutto il
    progetto.
    """
    livello, mfe = -1.0, 0.0
    for i in range(len(fav)):
        if apri[i] <= livello:
            return apri[i], "gap"
        if apri[i] >= rr:
            return apri[i], "gap+"
        if sfav[i] >= -livello:
            return livello, ("stop" if livello <= -1
                             else "pareggio" if livello == 0 else "protetto")
        if fav[i] >= rr:
            return float(rr), "obiettivo"
        mfe = max(mfe, fav[i])
        if pareggio is not None and mfe >= pareggio:
            livello = max(livello, 0.0)
        if trail is not None and mfe >= trail[0]:
            livello = max(livello, mfe - trail[1])
        if not oltre_giorno and i in fine_gio:
            return chiu[i], "fine giornata"
        if i in buchi and soglia_weekend is not None and chiu[i] < soglia_weekend:
            return chiu[i], "chiusa il venerdi'"
    return max(chiu[-1], livello), "scadenza"


def misure(n, date, anni):
    cum = np.cumsum(n)
    dd = float((np.maximum.accumulate(cum) - cum).max())
    pa = pd.Series(n).groupby(anni).sum()
    peggio = corrente = 0
    for v in n:
        corrente = corrente + 1 if v <= 0 else 0
        peggio = max(peggio, corrente)
    mesi = pd.Series(n, index=pd.DatetimeIndex(date)).resample("ME").sum()
    mesi = mesi[mesi != 0]
    return {"op": len(n), "R": n.sum(), "R/op": n.mean(),
            "vinte%": (n > 0).mean() * 100, "DD R": dd,
            "R/DD": n.sum() / dd if dd > 0 else np.nan,
            "anni+": f"{int((pa > 0).sum())}/{pa.size}",
            "anno peggiore R": pa.min(), "mesi+%": (mesi > 0).mean() * 100,
            "perdite di fila": peggio,
            "rischio per 6%/anno": 6.0 / pa.mean() if pa.mean() > 0 else np.nan,
            "DD% a quel rischio": dd * 6.0 / pa.mean() if pa.mean() > 0 else np.nan}


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [o for o in genera(m1, T, mediana_atr=MEDIANA_ATR)
           if all(o[f"c_{tf}"] for tf in T.conferme)
           and all(not o[f"c_{tf}"] for tf in T.ritracciamento)]
    print(f"operazioni: {len(ops)}", flush=True)
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values

    # (nome, rr, pareggio, trail, oltre_giorno, soglia_weekend)
    BOT = [("in uso  1:10, pareggio +3R, EOD", 10.0, 3.0, None, False, None),
           ("A       1:8, pareggio +3R, chiude venerdi'", 8.0, 3.0, None, True, -99.0),
           ("B       1:8, trail MFE-2 da +3R, weekend se >+1R", 8.0, None, (3.0, 2.0), True, 1.0),
           ("1:2     secco, niente pareggio, EOD", 2.0, None, None, False, None)]

    pd.set_option("display.width", 250)
    for costo_vero in (False, True):
        eti = "spread VERO per anno" if costo_vero else "spread 0,30 delle schede"
        f = []
        for nome, rr, pareggio, trail, oltre, soglia in BOT:
            R, date, anni = [], [], []
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
                x, _ = cammina(apri, fav, sfav, chiu, buchi, fine_gio,
                               rr, pareggio, trail, oltre, soglia)
                s = SPREAD.get(o["anno"], 0.40) if costo_vero else T.spread
                R.append(x - s / k)
                date.append(t_in)
                anni.append(o["anno"])
            f.append({"bot": nome, **misure(np.array(R), date, np.array(anni))})
        print(f"\n=== {eti}")
        print(pd.DataFrame(f).set_index("bot").round(2).to_string())


if __name__ == "__main__":
    main()
