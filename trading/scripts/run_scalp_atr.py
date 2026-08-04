#!/usr/bin/env python3
"""Appendice BO: obiettivi piu' larghi (max 10 $) e stop scritti in volatilita'.

Richiesta dell'utente dopo l'appendice BM: *"proviamo con tp piu' larghi
massimo 10 pt in base alla situazione del momento, volatilita' ecc"*.

Risolve anche il difetto che BM aveva trovato da sola: uno stop di 3 $ fissi
non e' lo stesso strumento ogni anno (dal 54% al 70% di stop fra il 2023 e il
2026, con l'escursione mediana dell'M1 passata da 0,45 $ a 2,27 $). Qui stop e
obiettivo si scrivono in **respiro corrente**, cioe' l'escursione media delle
ultime 30 candele M1 prima dell'ingresso — una misura causale, che non guarda
avanti di un solo minuto.

Il tetto di 10 $ sull'obiettivo e' dell'utente e resta: e' quello che tiene
l'operazione dentro la giornata invece di trasformarla nel 1:10 della
strategia lunga.

COSA SI CONFRONTA (sei celle, tutte riportate, nessuna scelta a posteriori):
  stop  1,0 e 1,5 volte il respiro
  obiettivo  2, 3 e 5 volte il respiro, **tagliato a 10 $**
piu' i tre riferimenti: l'ufficiale 1:10, e i due a punti fissi di BM.

IPOTESI PRE-REGISTRATE:
  A. scrivere stop e obiettivo in volatilita' rende la regola STABILE fra gli
     anni: la percentuale di stop smette di crescere. Questa e' la parte che
     mi aspetto funzioni, ed e' un miglioramento del metodo comunque;
  B. la stabilita' NON basta a renderla profittevole: il costo dello spread
     resta ~0,30 $ su stop di pochi dollari, e in BM il vantaggio lordo era la
     meta' del costo. Mi aspetto netto ancora negativo sul campione largo;
  C. il tetto di 10 $ sull'obiettivo taglia la coda che paga: mi aspetto che
     l'ufficiale 1:10 resti davanti a tutte le celle.
Se A e' vera e B e' falsa, e' una scoperta e va guardata due volte.

Uso: python3 run_scalp_atr.py
Scrive docs/studies/dati/scalp_atr.parquet
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

from run_scalp_scaglioni import cammina_uno                      # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GIORNI_MAX = 30
RESPIRO = 30               # candele M1 su cui si misura l'escursione corrente
TETTO = 10.0               # il massimo dell'obiettivo, in dollari: e' dell'utente
RICERCA, VERIFICA = (2020, 2022), (2023, 2026)


def respiro_m1(m1, n=RESPIRO):
    """Escursione media delle ultime n candele M1, spostata di uno.

    Lo shift(1) e' quello che rende la misura utilizzabile: al minuto in cui si
    decide, la candela in corso non e' ancora chiusa e il suo massimo non si
    conosce. Senza, si guadagnerebbe un minuto di futuro a ogni operazione.
    """
    return (m1.high - m1.low).rolling(n).mean().shift(1)


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    resp = respiro_m1(m1)
    tutte = genera(m1, T)
    ufficiali = [o for o in tutte
                 if all(o[f"c_{tf}"] for tf in T.conferme)
                 and all(not o[f"c_{tf}"] for tf in T.ritracciamento)]
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values
    rv = resp.values
    print(f"largo {len(tutte)} | ufficiali {len(ufficiali)} | "
          f"respiro M1 mediano {np.nanmedian(rv):.3f} $", flush=True)

    # (etichetta, stop $ o ("atr", k), obiettivo: ("rr", x) | ("atr", k) | None)
    PROVE = [("ufficiale 1:10 strutturale", None, ("rr", 10.0), 3.0)]
    # 2,0x e' la taglia che l'utente usa davvero: stop 4,5 $ con il respiro M1
    # del 2026 intorno a 2,3 $. Non e' una cella in piu' pescata a caso, e' la
    # misura di un'operazione vera descritta mentre era aperta.
    for ks in (1.0, 1.5, 2.0):
        for ko in (2.0, 3.0, 5.0):
            PROVE.append((f"stop {ks:g}x respiro, obiettivo {ko:g}x (max 10 $)",
                          ("atr", ks), ("atr", ko), None))
    PROVE += [("rif. stop 3 $ obiettivo 5 $", 3.0, ("rr", 5 / 3), None),
              ("rif. stop 5 $ obiettivo 8 $", 5.0, ("rr", 8 / 5), None)]

    righe = []
    for eti_c, ops in [("ufficiali", ufficiali), ("largo", tutte)]:
        for eti, stopdef, obdef, pareggio in PROVE:
            for o in ops:
                t_in = pd.Timestamp(o["time"]).tz_convert("UTC")
                segno = 1 if o["lato"] == "long" else -1
                e = o["entry"]
                a = int(np.searchsorted(idx, t_in.value))
                b = int(np.searchsorted(idx, (t_in + pd.Timedelta(days=GIORNI_MAX)).value))
                r_now = rv[a] if a < len(rv) else np.nan
                if stopdef is None:
                    k = float(o["rischio"])
                elif isinstance(stopdef, tuple):
                    if not np.isfinite(r_now) or r_now <= 0:
                        continue
                    k = float(stopdef[1]) * float(r_now)
                else:
                    k = float(stopdef)
                if k < 0.5:            # sotto mezzo dollaro lo spread e' il 60%
                    continue           # dello stop: non e' un'operazione, e' una tassa
                if obdef[0] == "rr":
                    rr = float(obdef[1])
                else:
                    rr = min(float(obdef[1]) * float(r_now), TETTO) / k
                o_, h_, l_, c_ = ap_[a:b], hi[a:b], lo[a:b], cl[a:b]
                if len(c_) < 2:
                    continue
                if segno == 1:
                    apri, fav, sfav, chiu = ((o_ - e) / k, (h_ - e) / k,
                                             (e - l_) / k, (c_ - e) / k)
                else:
                    apri, fav, sfav, chiu = ((e - o_) / k, (e - l_) / k,
                                             (h_ - e) / k, (e - c_) / k)
                r, motivo = cammina_uno(apri, fav, sfav, chiu, rr, pareggio)
                righe.append({"campione": eti_c, "gestione": eti, "anno": o["anno"],
                              "rischio$": k, "rr": rr, "costo": T.spread / k,
                              "lordo": r, "netto": r - T.spread / k, "motivo": motivo})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "scalp_atr.parquet"), index=False)
    pd.set_option("display.width", 250)

    def riassunto(x):
        n = x.netto.values
        cum = np.cumsum(n)
        dd = float((np.maximum.accumulate(cum) - cum).max()) if len(n) else 0.0
        pa = x.netto.groupby(x.anno).sum()
        return pd.Series({"op": len(n), "stop$": x["rischio$"].median(),
                          "RR": x.rr.median(), "costo%R": x.costo.mean() * 100,
                          "lordo R/op": x.lordo.mean(), "netto R/op": n.mean(),
                          "netto R": n.sum(), "vinte%": (n > 0).mean() * 100,
                          "stop%": (x.motivo == "stop").mean() * 100,
                          "DD R": dd, "R/DD": n.sum() / dd if dd > 0 else np.nan,
                          "anni+": int((pa > 0).sum()), "anni": pa.size})

    for eti_c in ("ufficiali", "largo"):
        print(f"\n=== campione {eti_c}, tutto il periodo")
        print(t[t.campione == eti_c].groupby("gestione", sort=False)
              .apply(riassunto).round(3).to_string())

    print("\n\n=== ipotesi A: la regola in volatilita' e' stabile fra i periodi?")
    for eti, (da, aa) in [(f"ricerca {RICERCA}", RICERCA), (f"verifica {VERIFICA}", VERIFICA)]:
        p = t[(t.campione == "largo") & (t.anno >= da) & (t.anno <= aa)]
        print(f"\n  {eti}")
        print(p.groupby("gestione", sort=False)
              .apply(lambda x: pd.Series({"op": len(x), "stop$": x["rischio$"].median(),
                                          "stop%": (x.motivo == "stop").mean() * 100,
                                          "lordo R/op": x.lordo.mean(),
                                          "netto R/op": x.netto.mean()}))
              .round(3).to_string())

    print("\n=== stop% anno per anno: il difetto di BM e' rientrato?")
    p = t[(t.campione == "largo")
          & (t.gestione.str.startswith("stop 1x respiro, obiettivo 3x"))]
    q = t[(t.campione == "largo") & (t.gestione == "rif. stop 3 $ obiettivo 5 $")]
    a = pd.DataFrame({
        "respiro stop%": p.groupby("anno").motivo.apply(lambda x: (x == "stop").mean() * 100),
        "respiro stop$": p.groupby("anno")["rischio$"].median(),
        "respiro R/op": p.groupby("anno").netto.mean(),
        "3$ fissi stop%": q.groupby("anno").motivo.apply(lambda x: (x == "stop").mean() * 100),
        "3$ fissi R/op": q.groupby("anno").netto.mean()})
    print(a.round(2).to_string())


if __name__ == "__main__":
    main()
