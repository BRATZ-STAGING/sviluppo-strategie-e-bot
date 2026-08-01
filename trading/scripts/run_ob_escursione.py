#!/usr/bin/env python3
"""Appendice Z: escursione del prezzo prima del tocco di un order block.

Ricostruisce le operazioni del campione largo e, per ogni timeframe, misura
quanto il prezzo si era allontanato dalla zona PRIMA di tornarci dentro:

    zona rialzista: max(high M1 da attiva_da a t_in) - bordo alto
    zona ribassista: bordo basso - min(low M1 nello stesso intervallo)

Per ogni operazione si tiene l'escursione MASSIMA fra le zone concordi che ne
contengono il prezzo d'ingresso (margine 0,5 x rischio, come sempre). Tutto
causale: solo minuti precedenti l'ingresso.

Salva docs/studies/dati/ob-escursione.parquet con op_id, tf, anno, r, exc.
Uso: python3 run_ob_escursione.py [out.json opzionale per il laboratorio]
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf     # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

from export_lab import (CALIB, genera, macro_trend, prepara,      # noqa: E402
                        zone_ob)
from framework.volatility import high_volatility_months           # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TFS = ["M33", "M66", "H2", "H3"]


def escursioni(m1, trades, tf):
    """Per ogni operazione: escursione massima delle zone che la contengono."""
    z = zone_ob(resample_tf(m1, tf), 3, TIMEFRAMES[tf])
    # tutti i tempi come interi in nanosecondi: confronti fra fusi o unita'
    # diverse producono silenziosamente finestre sbagliate (gia' successo).
    # as_unit e' obbligatorio: asi8 restituisce gli interi nell'unita' propria
    # dell'array, e le zone nascono in microsecondi mentre le M1 sono in ns
    ns = lambda s: pd.DatetimeIndex(pd.to_datetime(s, utc=True)).as_unit("ns").asi8
    idx = ns(m1.index)
    hi, lo = m1.high.values, m1.low.values

    att, sca = ns(z.attiva_da), ns(z.scade_il)
    inv = ns(z.invalidata_il)                  # NaT -> il minimo di int64
    viva_sempre = z.invalidata_il.isna().values
    lat, basso, alto = z.lato.values, z.basso.values, z.alto.values

    out = []
    for tr in trades:
        t_in = pd.Timestamp(tr["t_in"]).tz_convert("UTC").value
        segno = 1 if tr["lato"] == "long" else -1
        marg = 0.5 * tr["risk"]
        prezzo = tr["entry"]
        viva = ((lat == segno) & (att <= t_in) & (sca > t_in)
                & (viva_sempre | (inv > t_in))
                & (basso - marg <= prezzo) & (prezzo <= alto + marg))
        if not viva.any():
            out.append(np.nan)
            continue
        fine = int(np.searchsorted(idx, t_in))      # t_in escluso: causale
        best = 0.0
        for j in np.flatnonzero(viva):
            ini = int(np.searchsorted(idx, att[j]))
            if fine <= ini:
                continue
            if lat[j] == 1:
                e = float(hi[ini:fine].max()) - alto[j]
            else:
                e = basso[j] - float(lo[ini:fine].min())
            best = max(best, max(e, 0.0))
        out.append(best)
    return np.array(out), len(z)


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    m6, atr = prepara(m1)
    mask = (atr.index.year >= CALIB[0]) & (atr.index.year <= CALIB[1])
    med = float(atr[mask].median())
    k = {"imp": T.impulso_min / med, "buf": T.buffer / med,
         "rmin": T.rischio_min / med, "rmax": T.rischio_max / med}
    alto = high_volatility_months(
        atr, sorted({pd.Period(x.strftime("%Y-%m"), "M") for x in m6.index}),
        T.fattore_alta_volatilita)
    zone_m33 = zone_ob(resample_tf(m1, "M33"), 3, TIMEFRAMES["M33"])
    trades = genera(m1, m6, alto, k, macro_trend(m1), zone_m33)
    print(f"operazioni: {len(trades)}", flush=True)

    # esito ufficiale: stop strutturale, pareggio +3R, obiettivo 1:10
    r = np.array([tr["esiti"][0][2][4][1] - T.spread / tr["risk"] for tr in trades])
    anno = np.array([tr["anno"] for tr in trades])

    righe = []
    for tf in TFS:
        exc, nz = escursioni(m1, trades, tf)
        dentro = ~np.isnan(exc)
        if not dentro.any():
            raise SystemExit(f"{tf}: nessuna operazione in zona su {nz} zone. "
                             "Non e' un risultato, e' un errore di confronto "
                             "fra tempi: controllare unita' e fusi.")
        print(f"{tf}: {nz} zone, {dentro.sum()} operazioni in zona, "
              f"escursione mediana {np.nanmedian(exc):.2f} $", flush=True)
        righe.append(pd.DataFrame({"op_id": np.arange(len(trades)), "tf": tf,
                                   "anno": anno, "r": r, "exc": exc}))
    out = pd.concat(righe, ignore_index=True)
    dest = os.path.join(ROOT, "docs", "studies", "dati", "ob-escursione.parquet")
    out.to_parquet(dest, index=False)
    print(f"\n{dest}")


if __name__ == "__main__":
    main()
