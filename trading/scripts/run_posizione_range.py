#!/usr/bin/env python3
"""Appendice BF: il vuoto e' un travestimento della POSIZIONE nel range?

Dall'appendice BE e' uscito un effetto grosso: sugli stessi inneschi (tocco di
un order block M12/M33), chiedere che nella direzione dell'operazione ci sia
una fascia a volume quasi nullo porta il risultato da -0,20 a +0,50 R/op con
obiettivo fisso 1:2, e regge su tutti e diciotto gli anni.

Prima di crederci va spiegato il MECCANISMO, perche' il tasso di obiettivo
raggiunto (38%) e' piu' del doppio di quello di un ingresso a caso (17%) e
lo stop viene toccato meno (33% contro 43%). Un vantaggio simile non nasce
dal nulla.

L'ipotesi da falsificare: **il vuoto non aggiunge niente, e' solo un modo per
dire che il prezzo sta in basso nel range gia' scambiato oggi**. Perche' un
vuoto SOPRA il prezzo puo' esistere solo se il mercato ha gia' scambiato piu'
in alto oggi ed e' tornato indietro; e in quel caso l'obiettivo a due stop
cade dentro un territorio gia' battuto, che il prezzo tende a rivisitare.

Se e' cosi', "comprare in basso nel range di oggi" deve rendere come il vuoto,
**senza order block e senza profilo**. Sarebbe una strategia piu' semplice e
piu' robusta, non una scoperta piu' debole.

Si misura tutto sugli stessi eventi: ogni chiusura M12 nella finestra
operativa, con la posizione nel range causale (solo cio' che e' stato
scambiato fino a quel minuto), la presenza del vuoto e il tocco di un order
block. Stop 0,25 ATR, obiettivo 1:2, uscita a fine giornata.

Uso: python3 run_posizione_range.py [anno_da anno_a]
Scrive <dati_grezzi>/posizione_range.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf       # noqa: E402
from framework.taratura import UFFICIALE as T                     # noqa: E402
from framework.volatility import daily_atr                        # noqa: E402

from export_lab import zone_ob                                    # noqa: E402
from run_vuoto_obiettivo import (BIN_ATR, MIN_PROFILO, ORA_A,     # noqa: E402
                                 ORA_DA, ORA_FINE, esito,
                                 tocchi_m12, vuoti_da)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GREZZI = os.environ.get("GREZZI", os.path.join(ROOT, "..", "dati_grezzi"))
Q = 0.25                   # stop, in ATR
RR = 2.0                   # obiettivo, in multipli dello stop
PASSO_EVENTI = "M12"       # si valuta a ogni chiusura M12


def main():
    anni = None
    if len(sys.argv) > 2:
        anni = list(range(int(sys.argv[1]), int(sys.argv[2]) + 1))
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"), years=anni)
    atr = {k: float(v) for k, v in daily_atr(m1, 14).items()}
    idx_ns = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    m1v = (m1.high.values, m1.low.values, m1.close.values)
    tipico = ((m1.high + m1.low + m1.close) / 3).values
    vol = m1.volume.values.astype(float)
    vol[~np.isfinite(vol) | (vol <= 0)] = 1.0
    giorni_m1 = m1.index.normalize()

    # gli order block, per marcare quali eventi sono anche un tocco
    tocchi = {}
    for tf in ("M12", "M33"):
        tfd = resample_tf(m1, tf)
        z = zone_ob(tfd, T.frattale_k, pd.Timedelta(TIMEFRAMES[tf]),
                    validita=10 ** 6)
        for quando, verso in tocchi_m12(tfd, tf, z):
            tocchi.setdefault((quando, verso), set()).add(tf)
    print(f"tocchi di order block: {len(tocchi)}", flush=True)

    m12 = resample_tf(m1, PASSO_EVENTI)
    passo = pd.Timedelta(TIMEFRAMES[PASSO_EVENTI])
    chiusure = m12.index + passo
    per_giorno = {}
    for t in chiusure:
        if ORA_DA <= t.hour < ORA_A:
            per_giorno.setdefault(t.normalize(), []).append(t)

    righe = []
    for giorno, quandi in sorted(per_giorno.items()):
        a_ = atr.get(giorno)
        if a_ is None or not np.isfinite(a_) or a_ <= 0:
            continue
        sel = np.flatnonzero(giorni_m1 == giorno)
        if len(sel) < 200:
            continue
        passo_bin = a_ * BIN_ATR
        liv = np.round(tipico[sel] / passo_bin).astype(np.int64)
        base, n = liv.min(), int(liv.max() - liv.min()) + 1
        conteggio = np.zeros(n)
        prezzi = (base + np.arange(n)) * passo_bin
        tempi_m1 = m1.index[sel]
        fine = giorno + pd.Timedelta(hours=ORA_FINE)
        prossimo = 0
        for quando in quandi:
            while prossimo < len(sel) and tempi_m1[prossimo] < quando:
                conteggio[liv[prossimo] - base] += vol[sel[prossimo]]
                prossimo += 1
            if prossimo < MIN_PROFILO:
                continue
            entry = float(m1.close.values[sel[prossimo - 1]])
            # posizione nel range SCAMBIATO FINORA, non in quello del giorno
            visti = np.flatnonzero(conteggio > 0)
            basso, alto = prezzi[visti[0]], prezzi[visti[-1]]
            if alto - basso < a_ * 0.1:
                continue
            posizione = (entry - basso) / (alto - basso)
            vuoti = vuoti_da(conteggio, prezzi, a_)
            for verso in (1, -1):
                sopra = [v for v in vuoti if v[0] > entry]
                sotto = [v for v in vuoti if v[1] < entry]
                c_e = bool(sopra) if verso == 1 else bool(sotto)
                stop_prezzo = entry - verso * Q * a_
                r = esito(m1v, idx_ns, quando, entry, verso, stop_prezzo,
                          entry + verso * RR * Q * a_, fine)
                if r is None:
                    continue
                righe.append({
                    "time": quando, "anno": quando.year, "lato": verso,
                    "posizione": posizione, "vuoto": c_e,
                    "ob": bool(tocchi.get((quando, verso))),
                    "atr": a_, "r": r})
    d = pd.DataFrame(righe)
    os.makedirs(GREZZI, exist_ok=True)
    d.to_parquet(os.path.join(GREZZI, "posizione_range.parquet"), index=False)
    print(f"{len(d)} righe", flush=True)
    if d.empty:
        return

    pd.set_option("display.width", 220)
    # per i long conta stare in basso, per gli short stare in alto: si guarda
    # sempre "quanto lontano dal bordo verso cui si opera"
    d["dal_bordo"] = np.where(d.lato == 1, d.posizione, 1 - d.posizione)
    d["fascia"] = pd.cut(d.dal_bordo, [-0.01, .2, .4, .6, .8, 1.01],
                         labels=["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"])
    print("\n=== posizione nel range gia' scambiato (0% = sul bordo da cui si opera)")
    print(d.groupby("fascia", observed=True).agg(
        op=("r", "size"), r_op=("r", "mean"),
        vinte=("r", lambda x: (x > 0).mean() * 100)).round(3).to_string())
    print("\n=== il vuoto aggiunge qualcosa DENTRO la stessa fascia di posizione?")
    print(d.groupby(["fascia", "vuoto"], observed=True).agg(
        op=("r", "size"), r_op=("r", "mean")).round(3).to_string())
    print("\n=== e l'order block?")
    print(d.groupby(["fascia", "ob"], observed=True).agg(
        op=("r", "size"), r_op=("r", "mean")).round(3).to_string())


if __name__ == "__main__":
    main()
