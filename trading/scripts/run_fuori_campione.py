#!/usr/bin/env python3
"""Appendice AU: le tre candidate su 2009-2019, storia mai vista.

Tutto quello che c'e' in ``docs/studies/`` e' stato misurato sul 2020-2026:
la strategia e' stata tarata li' dentro, quindi anche le verifiche "per anno"
condividono lo stesso mercato — oro in rialzo, con due strappi. Lo storico
esteso a ritroso (appendice AU, dati dal 2009) offre undici anni che nessuna
scelta di questo progetto ha mai visto, e che contengono i regimi mancanti:
il picco del 2011, il crollo 2012-2015, il laterale 2016-2018.

Confronta le tre gestioni finaliste sui due periodi separati:
  in uso : pari a +3R, obiettivo 1:10, chiusura di sera (nessuno swap)
  A      : pari a +3R, obiettivo 1:8, chiusura il venerdi', swap reale
  B      : trailing MFE-2, obiettivo 1:8, attraversa il fine settimana solo
           se sopra +1R, swap reale

In coda una verifica: la mediana ATR di riferimento e' quella del 2020-2024
(``Taratura.calibrazione``), cioe' un dato che nel 2009 non esisteva. Si
rifa' il conto con la mediana presa dal 2009-2013 per vedere se il risultato
del periodo nuovo dipende da quella costante.

Uso: python3 run_fuori_campione.py
Scrive docs/studies/dati/fuori_campione.parquet
"""
import dataclasses
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

from run_scale_trailing import GESTIONI, esito                   # noqa: E402
from run_filtro_weekend import CHIUSURA_MIN, GIORNI_MAX, cammina  # noqa: E402
from run_swap_reale import CONTRATTO, SWAP_LONG, SWAP_SHORT, notti  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RISCHIO = 100.0            # euro fissi per operazione: ogni operazione pesa uguale
PERIODI = [("fuori campione", 2009, 2019),
           ("in campione", 2020, 2026),
           ("tutto", 2009, 2026)]


def scala_di(nome):
    return next((s, t) for n, s, t in GESTIONI if n == nome)


PARI3, TRAIL2 = scala_di("pari a +3R (in uso)"), scala_di("trail MFE-2 da +3R")


def misure(r, anni, mesi):
    """Le stesse misure di run_stabilita, piu' i conteggi che servono qui."""
    cum = np.cumsum(r)
    sotto = np.maximum.accumulate(cum) - cum
    perse = vinte = pmax = vmax = 0
    for x in r:
        perse = perse + 1 if x < 0 else 0
        vinte = vinte + 1 if x > 0 else 0
        pmax, vmax = max(pmax, perse), max(vmax, vinte)
    per_anno = np.array([r[anni == a].sum() for a in np.unique(anni)])
    per_mese = np.array([r[mesi == m].sum() for m in np.unique(mesi)])
    persa = -r[r < 0].sum()
    return {
        "ops": len(r), "r_tot": r.sum(), "r_op": r.mean(),
        "vinte_pct": (r > 0).mean() * 100,
        "perdite_fila": pmax, "vittorie_fila": vmax,
        "dd_r": sotto.max(), "recupero": r.sum() / max(sotto.max(), 1e-9),
        "mesi_pos_pct": (per_mese > 0).mean() * 100,
        "anni_pos": int((per_anno > 0).sum()), "anni": len(per_anno),
        "anno_peggiore": per_anno.min(), "anno_migliore": per_anno.max(),
        "profit_factor": r[r > 0].sum() / max(persa, 1e-9),
    }


def prepara(m1, tar):
    """Operazioni con le conferme richieste, piu' gli indici del minuto."""
    ops = [op for op in genera(m1, tar)
           if all(op[f"c_{tf}"] for tf in tar.conferme)
           and all(not op[f"c_{tf}"] for tf in tar.ritracciamento)]
    return ops


def lunga(op, idx, ap_, hi, lo, cl, rr, scala, trail, solo_venerdi, soglia):
    """Esito di un'operazione tenuta oltre la sera, swap reale compreso."""
    t_in = pd.Timestamp(op["time"]).tz_convert("UTC")
    segno = 1 if op["lato"] == "long" else -1
    e, k = op["entry"], op["rischio"]
    g = t_in.normalize()
    fine = (g + pd.Timedelta(days=(4 - g.weekday()) % 7)
            + pd.Timedelta(hours=T.ora_chiusura) if solo_venerdi
            else t_in + pd.Timedelta(days=GIORNI_MAX))
    a = int(np.searchsorted(idx, t_in.value))
    b = int(np.searchsorted(idx, fine.value))
    o_, h_, l_, c_ = ap_[a:b], hi[a:b], lo[a:b], cl[a:b]
    if segno == 1:
        apri, fav, sfav, chiu = ((o_ - e) / k, (h_ - e) / k,
                                 (e - l_) / k, (c_ - e) / k)
    else:
        apri, fav, sfav, chiu = ((e - o_) / k, (e - l_) / k,
                                 (h_ - e) / k, (e - c_) / k)
    d = np.diff(idx[a:b]) / 60_000_000_000
    buchi = set(np.flatnonzero(d > CHIUSURA_MIN).tolist())
    x, motivo, j = cammina(apri, fav, sfav, chiu, buchi, rr, scala, trail,
                           soglia, False)
    t_out = pd.Timestamp(idx[a + j], unit="ns", tz="UTC")
    swap = (notti(t_in, t_out) * (SWAP_LONG if segno == 1 else SWAP_SHORT)
            / (CONTRATTO * k))
    return x - op["costo"] + swap, motivo


def risultati(ops, m1):
    """Serie di R per ciascuna delle tre candidate."""
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = (m1.open.values, m1.high.values, m1.low.values,
                       m1.close.values)
    fuori = {}
    fuori["in uso"] = np.array(
        [esito(o["fav"], o["sfav"], o["r_eod"], 10.0, *PARI3)[0] - o["costo"]
         for o in ops])
    for nome, rr, gest, venerdi, soglia in [
        ("A", 8.0, PARI3, True, None),
        ("B", 8.0, TRAIL2, False, 1.0),
    ]:
        fuori[nome] = np.array(
            [lunga(o, idx, ap_, hi, lo, cl, rr, *gest, venerdi, soglia)[0]
             for o in ops])
    return fuori


def tabella(fuori, anni, mesi):
    righe = []
    for eti, da, a_ in PERIODI:
        sel = (anni >= da) & (anni <= a_)
        if not sel.any():
            continue
        for nome, r in fuori.items():
            righe.append({"periodo": eti, "da": da, "a": a_, "strategia": nome,
                          **misure(r[sel], anni[sel], mesi[sel])})
    return pd.DataFrame(righe)


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = prepara(m1, T)
    anni = np.array([o["anno"] for o in ops])
    mesi = np.array([pd.Timestamp(o["time"]).strftime("%Y-%m") for o in ops])
    print(f"operazioni: {len(ops)} ({(anni <= 2019).sum()} nel periodo nuovo, "
          f"{(anni >= 2020).sum()} in quello gia' studiato)", flush=True)

    fuori = risultati(ops, m1)
    df = tabella(fuori, anni, mesi)
    df.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                               "fuori_campione.parquet"), index=False)

    pd.set_option("display.width", 240)
    col = ["periodo", "strategia", "ops", "r_tot", "r_op", "vinte_pct",
           "perdite_fila", "vittorie_fila", "dd_r", "recupero", "mesi_pos_pct",
           "anni_pos", "anni", "anno_peggiore", "profit_factor"]
    print("\n=== le tre candidate, periodo nuovo contro periodo gia' studiato")
    print(df[col].round(2).to_string(index=False))

    print("\n=== risultato per anno, in R (lotti fissi)")
    per_anno = pd.DataFrame(
        {nome: [r[anni == y].sum() for y in np.unique(anni)]
         for nome, r in fuori.items()},
        index=np.unique(anni))
    per_anno["ops"] = [int((anni == y).sum()) for y in np.unique(anni)]
    print(per_anno.round(1).to_string())

    print("\n=== controllo: mediana ATR di riferimento presa dal 2009-2013 "
          "(nota all'epoca) invece che dal 2020-2024 (che nel 2009 non esisteva)")
    alt = dataclasses.replace(T, calibrazione=(2009, 2013))
    ops_a = prepara(m1, alt)
    anni_a = np.array([o["anno"] for o in ops_a])
    r_alt = np.array([esito(o["fav"], o["sfav"], o["r_eod"], 10.0, *PARI3)[0]
                      - o["costo"] for o in ops_a])
    for eti, da, a_ in PERIODI:
        s0, s1 = (anni >= da) & (anni <= a_), (anni_a >= da) & (anni_a <= a_)
        if not s1.any():
            continue
        print(f"  {eti:16s} ufficiale {fuori['in uso'][s0].sum():+7.1f} R su "
              f"{int(s0.sum()):4d} op | con mediana 2009-2013 "
              f"{r_alt[s1].sum():+7.1f} R su {int(s1.sum()):4d} op")


if __name__ == "__main__":
    main()
