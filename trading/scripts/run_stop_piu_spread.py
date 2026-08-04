#!/usr/bin/env python3
"""Appendice CA: lo stop in punti PIU' lo spread — la proposta dell'utente.

*"Aggiungi allo stop in punti lo spread"*: se lo stop nominale e' 3 punti e lo
spread e' 0,6, lo stop va messo a 3,6 dal prezzo d'ingresso.

NON E' LA STESSA COSA di quello che facevo prima, ed e' la ragione per cui
vale la pena misurarlo. Negli studi precedenti lo stop stava a 3 $ dal prezzo e
lo spread veniva sottratto come costo: la perdita su uno stop era quindi
1 + 0,63/3 = **1,21 R**, ma lo stop veniva **toccato piu' spesso**, perche' era
piu' vicino. Con la proposta dell'utente la perdita torna a 1 R esatto e lo
stop e' piu' lontano, quindi scatta meno. Sono due strategie diverse:

  vecchio   stop a 3,00 dal prezzo, perdita 1,21 R, colpito piu' spesso
  nuovo     stop a 3,63 dal prezzo, perdita 1,00 R, colpito meno spesso

Chi vince non e' ovvio a priori: dipende da quanto rumore c'e' fra 3,00 e 3,63.
Ecco perche' si misura invece di ragionarci.

MODELLO DI ESECUZIONE, esplicito perche' e' tutto qui. Per un acquisto si
compra alla LETTERA (bid + spread) e si esce al DENARO. Lo stop e' un livello
di prezzo denaro posto a ``nominale + spread`` sotto il denaro d'ingresso: cosi'
la perdita effettiva, spread compreso, e' esattamente il nominale. L'obiettivo
si misura dallo stesso punto, quindi il rapporto rischio/rendimento dichiarato
e' quello vero, non quello prima dei costi.

IPOTESI PRE-REGISTRATE:
  A. allontanare lo stop dello spread riduce la percentuale di stop di qualche
     punto (meccanico: lo stop e' piu' lontano);
  B. il risultato netto MIGLIORA rispetto al modello vecchio a parita' di
     nominale, ma NON abbastanza da rendere positivo il 2023-2026 con nominali
     di 3-5 punti. L'appendice BZ ha misurato che li' il vantaggio e' negativo
     e il divario e' di 0,03-0,06 R/op: lo spread vale 0,63 su 3 $, cioe' il
     21% del rischio, e spostarlo non lo fa sparire — lo sposta soltanto;
  C. il confine fra nominali che perdono e nominali che guadagnano si abbassa
     un poco rispetto ai 5-6 $ di BZ, ma resta sopra i 4.

Uso: XAU_ANNI=2020-2026 python3 run_stop_piu_spread.py
Scrive docs/studies/dati/stop_piu_spread.parquet
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
GIORNI_MAX = 5
NOMINALI = [3, 4, 5, 6, 8, 10, 12]
OBIETTIVI = [1.5, 2.0, 3.0]
SPREAD = {2020: 0.35, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}
RICERCA, VERIFICA = (2020, 2022), (2023, 2026)


def percorri(bh, bl, bc, entry, stop, bers, verso):
    """Minuto per minuto sul denaro. Lo stop prevale sull'obiettivo."""
    if verso == 1:
        ks = np.flatnonzero(bl <= stop)
        kt = np.flatnonzero(bh >= bers)
    else:
        ks = np.flatnonzero(bh >= stop)
        kt = np.flatnonzero(bl <= bers)
    a = ks[0] if len(ks) else None
    b = kt[0] if len(kt) else None
    if a is not None and (b is None or a <= b):
        return -1.0, "stop", a
    if b is not None:
        return abs(bers - entry) / abs(entry - stop), "obiettivo", b
    return (bc[-1] - entry) * verso / abs(entry - stop), "scadenza", len(bc) - 1


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    tutte = genera(m1, T, mediana_atr=MEDIANA_ATR)
    ops = [o for o in tutte
           if all(o[f"c_{tf}"] for tf in T.conferme)
           and all(not o[f"c_{tf}"] for tf in T.ritracciamento)]
    print(f"operazioni ufficiali: {len(ops)}", flush=True)
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    hi, lo, cl = m1.high.values, m1.low.values, m1.close.values

    righe = []
    for o in ops:
        t_in = pd.Timestamp(o["time"]).tz_convert("UTC")
        verso = 1 if o["lato"] == "long" else -1
        e = float(o["entry"])
        s = SPREAD.get(o["anno"], 0.40)
        a = int(np.searchsorted(idx, t_in.value))
        b = int(np.searchsorted(idx, (t_in + pd.Timedelta(days=GIORNI_MAX)).value))
        if b - a < 5:
            continue
        bh, bl, bc = hi[a:b], lo[a:b], cl[a:b]
        for nom in NOMINALI:
            for rr in OBIETTIVI:
                for modo in ("vecchio", "piu' spread"):
                    # UN SOLO modello di esecuzione, uguale per i due modi, ed e'
                    # quello vero: si COMPRA alla lettera (denaro + spread) e si
                    # esce al denaro. Lo stop e' un livello di DENARO a distanza
                    # ``d`` sotto il denaro d'ingresso, quindi la perdita reale
                    # vale d + spread — lo spread si paga sempre, anche quando
                    # lo stop e' lontano. La prima versione di questo script non
                    # lo addebitava al modo "piu' spread" e lo faceva sembrare
                    # molto migliore di quanto sia: era un falso positivo.
                    d = nom if modo == "vecchio" else nom + s
                    rischio = d + s
                    ingresso = e + verso * s              # si entra alla lettera
                    stop = e - verso * d
                    bers = ingresso + verso * rr * rischio
                    r, motivo, _ = percorri(bh, bl, bc, ingresso, stop, bers, verso)
                    righe.append({"anno": o["anno"], "nominale": nom,
                                  "rr": rr, "modo": modo, "spread": s,
                                  "stop$": rischio, "lordo": r,
                                  "netto": r, "motivo": motivo})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "stop_piu_spread.parquet"), index=False)
    pd.set_option("display.width", 240)

    print("\n=== netto R/op (normalizzato sulla perdita VERA in dollari)")
    for rr in OBIETTIVI:
        print(f"\n  obiettivo 1:{rr:g}")
        f = []
        for nom in NOMINALI:
            r = {"nominale $": nom}
            for modo in ("vecchio", "piu' spread"):
                for eti, (da, aa) in [("ric.", RICERCA), ("ver.", VERIFICA)]:
                    x = t[(t.nominale == nom) & (t.rr == rr) & (t.modo == modo)
                          & (t.anno >= da) & (t.anno <= aa)]
                    if x.empty:
                        continue
                    k = "vecchio" if modo == "vecchio" else "+spread"
                    r[f"{k} {eti}"] = x.netto.mean()
                    r[f"{k} stop%"] = (x.motivo == "stop").mean() * 100
            f.append(r)
        print(pd.DataFrame(f).set_index("nominale $").round(3).to_string())

    print("\n=== ipotesi A: lo stop piu' lontano scatta meno?")
    g = t.groupby(["nominale", "modo"]).motivo.apply(
        lambda x: (x == "stop").mean() * 100).unstack().round(1)
    g["differenza"] = g["piu' spread"] - g["vecchio"]
    print(g.to_string())


if __name__ == "__main__":
    main()
