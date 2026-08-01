#!/usr/bin/env python3
"""Appendice AE: obiettivo appoggiato ai livelli strutturali.

Per ognuna delle 348 operazioni ufficiali cerca il livello piu' vicino oltre
l'ingresso (per famiglia: swing non superati M33/H2/H6, bordo della zona OB
contraria M33, estremi del giorno precedente, estremi della sessione Asia,
numeri tondi) e ricalcola l'esito col TP a 0,10 $ dal livello, stesso motore
conservativo (stop batte obiettivo, pareggio +3R, chiusura alle 21).

Controllo decisivo: placebo a distanze uguali — le stesse distanze in R
rimescolate fra le operazioni. Se una famiglia non batte il suo placebo, il
livello non aggiunge nulla oltre alla propria distribuzione di distanze.

Uso: python3 run_tp_livelli.py
Scrive docs/studies/dati/tp-livelli.parquet (una riga per op x famiglia).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf     # noqa: E402
from framework.gestione import chiusura_fine_giornata, esito_indice  # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

from export_lab import zone_ob                                   # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OFFSET = 0.10            # il TP sta 10 centesimi PRIMA del livello
K = 3


def swing_vivi(tfd):
    """Per lato: liste (conferma_ns, livello, rotto_ns) dei swing confermati.

    ``rotto_ns`` e' la chiusura che supera il livello (inf se mai rotto):
    un livello e' resistenza/supporto solo finche' non e' stato superato.
    """
    h, l, c = tfd.high.values, tfd.low.values, tfd.close.values
    tempi = tfd.index.asi8
    passo = int((tfd.index[1] - tfd.index[0]).value)
    out = {}
    for lato, serie in ((1, h), (-1, l)):
        voci = []
        n = len(tfd)
        for i in range(2 * K, n):
            j = i - K
            if lato == 1:
                if not ((serie[j-K:j] < serie[j]).all() and (serie[j+1:i+1] < serie[j]).all()):
                    continue
            else:
                if not ((serie[j-K:j] > serie[j]).all() and (serie[j+1:i+1] > serie[j]).all()):
                    continue
            lev = float(serie[j])
            oltre = np.flatnonzero((c[i+1:] > lev) if lato == 1 else (c[i+1:] < lev))
            rotto = tempi[i+1+oltre[0]] + passo if len(oltre) else np.iinfo(np.int64).max
            voci.append((tempi[i] + passo, lev, rotto))
        out[lato] = voci
    return out


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [op for op in genera(m1, T)
           if all(op[f"c_{tf}"] for tf in T.conferme)
           and all(not op[f"c_{tf}"] for tf in T.ritracciamento)]
    print(f"operazioni ufficiali: {len(ops)}", flush=True)

    sw = {tf: swing_vivi(resample_tf(m1, tf)) for tf in ("M33", "H2", "H6")}
    zone = zone_ob(resample_tf(m1, "M33"), K, TIMEFRAMES["M33"])
    z_att = pd.DatetimeIndex(pd.to_datetime(zone.attiva_da, utc=True)).as_unit("ns").asi8
    z_sca = pd.DatetimeIndex(pd.to_datetime(zone.scade_il, utc=True)).as_unit("ns").asi8
    z_inv = pd.DatetimeIndex(pd.to_datetime(zone.invalidata_il, utc=True)).as_unit("ns").asi8
    z_ok = zone.invalidata_il.isna().values
    d1 = m1.resample("1D").agg({"high": "max", "low": "min"}).dropna()
    asia = m1.between_time("00:00", "06:59").resample("1D").agg({"high": "max", "low": "min"})

    def livello(fam, op):
        """Prezzo del livello piu' vicino oltre l'entry, o None."""
        t_in = pd.Timestamp(op["time"]).tz_convert("UTC")
        e = op["entry"]
        lato = 1 if op["lato"] == "long" else -1
        ns = t_in.value
        if fam.startswith("swing_"):
            cand = [lev for conf, lev, rotto in sw[fam[6:]][lato]
                    if conf <= ns < rotto and (lev > e if lato == 1 else lev < e)]
        elif fam == "ob_contrario":
            viva = ((zone.lato.values == -lato) & (z_att <= ns) & (z_sca > ns)
                    & (z_ok | (z_inv > ns)))
            bordi = np.where(zone.lato.values == -1, zone.basso.values, zone.alto.values)
            cand = [float(b) for b, v in zip(bordi, viva)
                    if v and (b > e if lato == 1 else b < e)]
        elif fam == "giorno_prima":
            g = t_in.normalize() - pd.Timedelta(days=1)
            while g not in d1.index and g > d1.index[0]:
                g -= pd.Timedelta(days=1)
            if g not in d1.index:
                return None
            cand = [x for x in (float(d1.loc[g, "high"]), float(d1.loc[g, "low"]))
                    if (x > e if lato == 1 else x < e)]
        elif fam == "asia":
            g = t_in.normalize()
            if g not in asia.index or asia.loc[g].isna().any():
                return None
            cand = [x for x in (float(asia.loc[g, "high"]), float(asia.loc[g, "low"]))
                    if (x > e if lato == 1 else x < e)]
        elif fam.startswith("tondi_"):
            p = float(fam[6:])
            cand = [np.floor(e / p) * p + p] if lato == 1 else [np.ceil(e / p) * p - p]
        else:
            raise ValueError(fam)
        if not cand:
            return None
        return min(cand) if lato == 1 else max(cand)

    FAMIGLIE = ["swing_M33", "swing_H2", "swing_H6", "ob_contrario",
                "giorno_prima", "asia", "tondi_10", "tondi_25"]
    righe = []
    for op_id, op in enumerate(ops):
        lato = 1 if op["lato"] == "long" else -1
        for fam in FAMIGLIE:
            lev = livello(fam, op)
            rr = None
            if lev is not None:
                tp = lev - OFFSET if lato == 1 else lev + OFFSET
                rr = (tp - op["entry"]) / op["rischio"] * lato
                if rr <= 0.1:
                    rr = None            # livello attaccato all'entry: inutile
            righe.append({"op_id": op_id, "anno": op["anno"], "famiglia": fam,
                          "rr_liv": np.nan if rr is None else float(rr)})
    df = pd.DataFrame(righe)
    dest = os.path.join(ROOT, "docs", "studies", "dati", "tp-livelli.parquet")
    df.to_parquet(dest, index=False)

    # esiti: per ogni famiglia e variante di distanza minima, totale R
    def esito_con_rr(op, rr):
        r, mo, _ = esito_indice(op["fav"], op["sfav"], rr, be=T.pareggio, costo=0.0)
        if r is None:
            r = chiusura_fine_giornata(op["r_eod"], T.pareggio, False, op["mfe"], 0.0)
            mo = 2
        return r - op["costo"], mo

    base = np.array([esito_con_rr(op, T.obiettivo)[0] for op in ops])
    print(f"base 1:10 riprodotta: {base.sum():+.1f} R", flush=True)
    rng = np.random.default_rng(20260801)
    print(f"{'famiglia':14s} {'min':>4s} {'con liv.':>8s} {'rr med':>7s} {'R tot':>7s} "
          f"{'TP%':>5s} {'anni+':>6s} {'placebo (media +- sd)':>22s}")
    for fam in FAMIGLIE:
        rrs = df[df.famiglia == fam].set_index("op_id").rr_liv
        for minimo in (0.0, 3.0):
            rr_op = np.array([rrs.get(i, np.nan) for i in range(len(ops))])
            rr_op = np.where(np.isfinite(rr_op) & (rr_op >= max(minimo, 0.1)),
                             rr_op, np.nan)
            usati = np.isfinite(rr_op)
            if usati.sum() < 30:
                continue
            r = base.copy(); tp = 0
            for i, op in enumerate(ops):
                if usati[i]:
                    r[i], mo = esito_con_rr(op, float(rr_op[i]))
                    tp += mo == 1
            anni = np.array([op["anno"] for op in ops])
            ap = sum(1 for y in np.unique(anni) if r[anni == y].sum() > 0)
            # placebo: stesse distanze, rimescolate fra le op che hanno livello
            tot_pl = []
            idx_usati = np.flatnonzero(usati)
            for _ in range(200):
                mescolo = rng.permutation(rr_op[idx_usati])
                rp = base.copy()
                for pos, i in enumerate(idx_usati):
                    rp[i], _ = esito_con_rr(ops[i], float(mescolo[pos]))
                tot_pl.append(rp.sum())
            tot_pl = np.array(tot_pl)
            quota = float((tot_pl >= r.sum()).mean())
            print(f"{fam:14s} {minimo:4.0f} {usati.sum():8d} "
                  f"{np.nanmedian(rr_op):7.1f} {r.sum():+7.1f} "
                  f"{tp/len(ops)*100:4.0f}% {ap:3d}/7 "
                  f"{tot_pl.mean():+8.1f} +-{tot_pl.std():5.1f}  p={quota:.3f}",
                  flush=True)


if __name__ == "__main__":
    main()
