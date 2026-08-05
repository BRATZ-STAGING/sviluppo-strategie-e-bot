#!/usr/bin/env python3
"""Appendice BM: lo scalp a punti fissi e l'uscita in tre scaglioni.

Specifica dell'utente, presa alla lettera:
  - entrare "anche da pochi punti": stop 3 $ / obiettivo 5 $, oppure stop 5 $ /
    obiettivo 8 $, invece dello stop strutturale;
  - oppure **tre operazioni da 0,25% di rischio**: la prima chiude a 1:1, e
    quando chiude le altre due vanno a **pareggio** con obiettivi 1:1,5 e 1:2.

IL NUMERO DA GUARDARE PRIMA DI TUTTO. Lo spread dell'oro nella taratura vale
**0,30 $ andata e ritorno**. Su uno stop di 3 $ e' il **10% del rischio**; su
5 $ e' il 6%. Un'operazione che punta a 1:1,67 (3 e 5 punti) pareggia al 37,5%
di vincite lorde ma al **41,3% nette**: quasi quattro punti di percentuale
regalati al broker prima ancora di cominciare. Questo studio serve a misurare
se quel regalo si puo' permettere, non a sperare che si possa.

C'e' un precedente diretto e va ricordato: l'appendice M ha gia' misurato la
stessa regola su timeframe piu' piccoli (M3, M1) con obiettivi 1:3-1:5, e il
vantaggio lordo si dimezzava mentre lo spread raddoppiava in R. Qui la novita'
non e' il timeframe — sono lo **stop a punti fissi** e la **scala in tre
uscite**, che l'appendice M non aveva provato.

IPOTESI PRE-REGISTRATE, scritte prima di guardare:
  A. lo stop a punti fissi peggiora il risultato rispetto allo stop
     strutturale, perche' non ha relazione con dove il mercato respira;
  B. la scala in tre uscite riduce il rendimento (l'appendice L ha gia'
     misurato -27% per una sola chiusura parziale) ma riduce anche la perdita
     massima: la domanda vera e' se il cambio conviene, cioe' se il rapporto
     rendimento/perdita massima migliora;
  C. uno stop in dollari fissi si comporta in modo DIVERSO anno per anno,
     perche' l'escursione mediana dell'M1 e' passata da ~0,45 $ (2020-24) a
     1,05 $ (2025) e 2,27 $ (2026): 3 $ nel 2021 e 3 $ nel 2026 non sono la
     stessa operazione. Se la percentuale di stop cresce di anno in anno, la
     regola non e' tarabile e va scritta in ATR.

Uso: python3 run_scalp_scaglioni.py
Scrive docs/studies/dati/scalp_scaglioni.parquet
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
GIORNI_MAX = 30
SCAGLIONI = [1.0, 1.5, 2.0]        # gli obiettivi dei tre terzi, come chiesti


def cammina_uno(apri, fav, sfav, chiu, rr, pareggio=None):
    """Un solo obiettivo. Lo stop prevale sull'obiettivo a parita' di minuto."""
    livello = -1.0
    mfe = 0.0
    for i in range(len(fav)):
        if apri[i] <= livello:
            return apri[i], "gap"
        if apri[i] >= rr:
            return apri[i], "gap+"
        if sfav[i] >= -livello:
            return livello, ("stop" if livello <= -1 else
                             ("pareggio" if livello == 0 else "protetto"))
        if fav[i] >= rr:
            return float(rr), "obiettivo"
        mfe = max(mfe, fav[i])
        if pareggio is not None and mfe >= pareggio:
            livello = max(livello, 0.0)
    return chiu[-1], "scadenza"


def cammina_scaglioni(apri, fav, sfav, chiu, obiettivi):
    """Tre terzi con obiettivi diversi; quando il primo incassa, gli altri
    vanno a pareggio.

    Il risultato torna in unita' di rischio TOTALE: se tutti e tre si fermano
    fa -1R, se prendono tutti gli obiettivi fa (1 + 1,5 + 2)/3 = +1,5R. Le
    quote sono uguali, come nella proposta (0,25% ciascuna su 0,75% totale).

    Attenzione a una cosa sola, ed e' quella che rende il conto onesto: il
    pareggio arriva DOPO che il primo scaglione ha chiuso, quindi nel minuto in
    cui il prezzo tocca +1R gli altri due non sono ancora protetti. Proteggerli
    nello stesso minuto vorrebbe dire sapere che il primo ha gia' incassato
    mentre la candela e' ancora aperta: e' futuro, e falserebbe tutto in meglio.
    """
    n = len(obiettivi)
    quota = 1.0 / n
    livello = [-1.0] * n            # lo stop di ciascun terzo, in R
    chiuso = [None] * n
    primo_fatto = False
    for i in range(len(fav)):
        for j, ob in enumerate(obiettivi):
            if chiuso[j] is not None:
                continue
            if apri[i] <= livello[j]:
                chiuso[j] = apri[i]
            elif apri[i] >= ob:
                chiuso[j] = apri[i]
            elif sfav[i] >= -livello[j]:
                chiuso[j] = livello[j]
            elif fav[i] >= ob:
                chiuso[j] = float(ob)
        if not primo_fatto and chiuso[0] is not None and chiuso[0] > 0:
            primo_fatto = True                    # solo ORA gli altri due si alzano
            for j in range(1, n):
                if chiuso[j] is None:
                    livello[j] = max(livello[j], 0.0)
        if all(c is not None for c in chiuso):
            break
    tot = 0.0
    for j in range(n):
        tot += quota * (chiuso[j] if chiuso[j] is not None else chiu[-1])
    return tot, ("stop" if all(c is not None and c <= -1 for c in chiuso)
                 else "pieno" if all(c is not None and c > 0 for c in chiuso)
                 else "misto")


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    tutte = genera(m1, T)
    ufficiali = [o for o in tutte
                 if all(o[f"c_{tf}"] for tf in T.conferme)
                 and all(not o[f"c_{tf}"] for tf in T.ritracciamento)]
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values
    print(f"campione largo {len(tutte)} | ufficiali {len(ufficiali)}", flush=True)

    # (etichetta, stop in dollari o None=strutturale, gestione)
    PROVE = [
        ("ufficiale 1:10, pareggio +3R", None, ("uno", 10.0, 3.0)),
        ("strutturale, 3 scaglioni 1/1,5/2", None, ("scala", None, None)),
        ("stop 3 $, obiettivo 5 $", 3.0, ("uno", 5.0 / 3.0, None)),
        ("stop 5 $, obiettivo 8 $", 5.0, ("uno", 8.0 / 5.0, None)),
        ("stop 3 $, 3 scaglioni 1/1,5/2", 3.0, ("scala", None, None)),
        ("stop 5 $, 3 scaglioni 1/1,5/2", 5.0, ("scala", None, None)),
    ]

    righe = []
    for eti_campione, ops in [("ufficiali", ufficiali), ("largo", tutte)]:
        for eti, punti, (modo, rr, pareggio) in PROVE:
            for o in ops:
                t_in = pd.Timestamp(o["time"]).tz_convert("UTC")
                segno = 1 if o["lato"] == "long" else -1
                e = o["entry"]
                k = float(punti) if punti else float(o["rischio"])
                a = int(np.searchsorted(idx, t_in.value))
                b = int(np.searchsorted(idx, (t_in + pd.Timedelta(days=GIORNI_MAX)).value))
                o_, h_, l_, c_ = ap_[a:b], hi[a:b], lo[a:b], cl[a:b]
                if len(c_) < 2:
                    continue
                if segno == 1:
                    apri, fav, sfav, chiu = ((o_ - e) / k, (h_ - e) / k,
                                             (e - l_) / k, (c_ - e) / k)
                else:
                    apri, fav, sfav, chiu = ((e - o_) / k, (e - l_) / k,
                                             (h_ - e) / k, (e - c_) / k)
                if modo == "uno":
                    r, motivo = cammina_uno(apri, fav, sfav, chiu, rr, pareggio)
                else:
                    r, motivo = cammina_scaglioni(apri, fav, sfav, chiu, SCAGLIONI)
                righe.append({"campione": eti_campione, "gestione": eti,
                              "anno": o["anno"], "lato": o["lato"],
                              "rischio$": k, "costo": T.spread / k,
                              "lordo": r, "netto": r - T.spread / k,
                              "motivo": motivo})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "scalp_scaglioni.parquet"), index=False)
    pd.set_option("display.width", 240)

    def riassunto(x):
        n = x.netto.values
        cum = np.cumsum(n)
        dd = float((np.maximum.accumulate(cum) - cum).max()) if len(n) else 0.0
        pa = x.netto.groupby(x.anno).sum()
        return pd.Series({
            "op": len(n), "costo%R": x.costo.mean() * 100,
            "lordo R/op": x.lordo.mean(), "netto R/op": n.mean(),
            "netto R": n.sum(), "vinte%": (n > 0).mean() * 100,
            "stop%": (x.motivo == "stop").mean() * 100,
            "DD R": dd, "R/DD": n.sum() / dd if dd > 0 else np.nan,
            "anni+": int((pa > 0).sum()), "anni": pa.size})

    for eti_campione in ("ufficiali", "largo"):
        print(f"\n=== campione {eti_campione}")
        p = t[t.campione == eti_campione]
        print(p.groupby("gestione", sort=False).apply(riassunto).round(3).to_string())

    print("\n=== ipotesi C: uno stop in dollari fissi e' la stessa cosa ogni anno?")
    p = t[(t.campione == "largo") & (t.gestione == "stop 3 $, obiettivo 5 $")]
    a = p.groupby("anno").agg(op=("netto", "size"),
                              stop_pc=("motivo", lambda x: (x == "stop").mean() * 100),
                              netto_op=("netto", "mean"), netto_R=("netto", "sum"))
    print(a.round(2).to_string())


if __name__ == "__main__":
    main()
