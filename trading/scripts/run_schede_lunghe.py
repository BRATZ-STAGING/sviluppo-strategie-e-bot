#!/usr/bin/env python3
"""Appendice AP: scheda completa delle due candidate senza chiusura serale.

Le due combinazioni che nell'appendice AO migliorano SENZA pagare in rischio:

    A  pareggio a +3R, obiettivo 1:8, chiusura al venerdi' sera
    B  trailing a MFE-2 da +3R, obiettivo 1:8, nessuna chiusura per tempo

Qui si tira fuori tutto quello che serve per deciderle: esiti, anni, mesi,
serie, drawdown, durata delle operazioni, notti e fine settimana attraversati
(cioe' l'esposizione allo swap e ai gap, i due costi non modellati) e le
posizioni aperte contemporaneamente.

Uso: python3 run_schede_lunghe.py
Scrive docs/studies/dati/schede-lunghe.parquet
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

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GIORNI_MAX = 30
MOTIVI = {0: "stop pieno", 1: "obiettivo", 2: "scadenza", 3: "pareggio",
          4: "stop in utile"}

CANDIDATE = [
    ("A · pari +3R, 1:8, venerdi'", "pari a +3R (in uso)", 8, "settimanale"),
    ("B · trail MFE-2, 1:8, aperta", "trail MFE-2 da +3R", 8, "aperta"),
    ("in uso · pari +3R, 1:10, sera", "pari a +3R (in uso)", 10, "giornaliera"),
]


def esito_i(fav, sfav, r_eod, rr, scala, trail):
    """Come ``esito`` ma ritorna anche il MINUTO di uscita."""
    livello = -1.0
    mfe = 0.0
    for i in range(len(fav)):
        if sfav[i] >= -livello:
            return livello, (0 if livello <= -1 else (3 if livello == 0 else 4)), i
        if fav[i] >= rr:
            return float(rr), 1, i
        mfe = max(mfe, fav[i])
        for soglia, dove in scala:
            if mfe >= soglia:
                livello = max(livello, float(dove))
        if trail is not None and mfe >= trail[0]:
            livello = max(livello, mfe - trail[1])
    return max(r_eod, livello), 2, len(fav) - 1


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [op for op in genera(m1, T)
           if all(op[f"c_{tf}"] for tf in T.conferme)
           and all(not op[f"c_{tf}"] for tf in T.ritracciamento)]
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    hi, lo, cl = m1.high.values, m1.low.values, m1.close.values
    print(f"operazioni: {len(ops)}", flush=True)

    righe = []
    for eti, nome, rr, regime in CANDIDATE:
        scala, trail = next((s, t) for n, s, t in GESTIONI if n == nome)
        r, mo, dur, ingressi, uscite = [], [], [], [], []
        for op in ops:
            t_in = pd.Timestamp(op["time"]).tz_convert("UTC")
            segno = 1 if op["lato"] == "long" else -1
            e, k = op["entry"], op["rischio"]
            g = t_in.normalize()
            fine = {"giornaliera": g + pd.Timedelta(hours=T.ora_chiusura),
                    "settimanale": g + pd.Timedelta(days=(4 - g.weekday()) % 7)
                    + pd.Timedelta(hours=T.ora_chiusura),
                    "aperta": t_in + pd.Timedelta(days=GIORNI_MAX)}[regime]
            a = int(np.searchsorted(idx, t_in.value))
            b = int(np.searchsorted(idx, fine.value))
            h_, l_, c_ = hi[a:b], lo[a:b], cl[a:b]
            if segno == 1:
                fav, sfav = (h_ - e) / k, (e - l_) / k
            else:
                fav, sfav = (e - l_) / k, (h_ - e) / k
            r_eod = ((float(c_[-1]) - e) if segno == 1 else (e - float(c_[-1]))) / k
            x, m, j = esito_i(fav, sfav, r_eod, rr, scala, trail)
            r.append(x - op["costo"])
            mo.append(m)
            t_out = pd.Timestamp(idx[a + j], unit="ns", tz="UTC")
            dur.append((t_out - t_in).total_seconds() / 3600)
            ingressi.append(t_in)
            uscite.append(t_out)
        r = np.array(r)
        mo = np.array(mo)
        dur = np.array(dur)
        anni = np.array([o["anno"] for o in ops])
        mesi = np.array([pd.Timestamp(o["time"]).strftime("%Y-%m") for o in ops])

        cum = np.cumsum(r)
        sotto = np.maximum.accumulate(cum) - cum
        lung = corr = 0
        for v in sotto:
            corr = corr + 1 if v > 1e-9 else 0
            lung = max(lung, corr)
        fv = fp = cv = cp = 0
        for v in r:
            cv, cp = (cv + 1, 0) if v > 0 else ((0, cp + 1) if v < 0 else (0, 0))
            fv, fp = max(fv, cv), max(fp, cp)
        # notti e fine settimana attraversati: e' l'esposizione a swap e gap
        notti = np.array([len(pd.date_range(i.normalize(), o.normalize(), freq="D")) - 1
                          for i, o in zip(ingressi, uscite)])
        weekend = np.array([((pd.date_range(i.normalize(), o.normalize(), freq="D")
                              .weekday == 5).sum()) for i, o in zip(ingressi, uscite)])
        ini = np.array([i.value for i in ingressi])
        fin = np.array([o.value for o in uscite])
        insieme = np.array([int(((ini <= t) & (fin > t)).sum()) for t in ini])

        d = {"scheda": eti, "n": len(r), "r_tot": r.sum(), "r_op": r.mean(),
             "vinte": int((r > 0).sum()), "perse": int((r < 0).sum()),
             "vinte_pct": (r > 0).mean() * 100,
             "media_v": r[r > 0].mean(), "media_p": r[r < 0].mean(),
             "pf": r[r > 0].sum() / max(-r[r < 0].sum(), 1e-9),
             "fila_v": fv, "fila_p": fp,
             "dd_r": sotto.max(), "sottomax": lung,
             "mesi_pos": int(sum(r[mesi == m].sum() > 0 for m in np.unique(mesi))),
             "mesi_tot": len(np.unique(mesi)),
             "anni_pos": int(sum(r[anni == y].sum() > 0 for y in np.unique(anni))),
             "anno_peg": min(r[anni == y].sum() for y in np.unique(anni)),
             "ore_mediana": np.median(dur), "ore_media": dur.mean(),
             "giorni_max": dur.max() / 24,
             "oltre_notte_pct": (notti > 0).mean() * 100,
             "notti_tot": int(notti.sum()),
             "weekend_tot": int(weekend.sum()),
             "insieme_max": int(insieme.max()), "insieme_medio": insieme.mean(),
             "conto_fisso": 10000 + 100 * r.sum()}
        for k, v in MOTIVI.items():
            d[f"n_{v.replace(' ', '_')}"] = int((mo == k).sum())
        for y in range(2020, 2027):
            d[f"r_{y}"] = r[anni == y].sum() if (anni == y).any() else 0.0
        righe.append(d)
        print(f"  {eti}", flush=True)

    df = pd.DataFrame(righe)
    df.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                               "schede-lunghe.parquet"), index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 100)
    print()
    print(df.set_index("scheda").T.round(2).to_string())


if __name__ == "__main__":
    main()
