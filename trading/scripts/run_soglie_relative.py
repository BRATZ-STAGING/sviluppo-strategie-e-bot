#!/usr/bin/env python3
"""Appendice BX: e se il crollo fuori campione fosse un problema di UNITA'?

L'appendice BW ha misurato una cosa che ribalta il quadro. Fra il 2009 e il
2026 l'oro e' passato da **950 a 4.676 dollari**, cioe' quasi cinque volte. Ma
in rapporto al prezzo:

  ATR giornaliero      2009-2019: 1,351%   2020-2026: 1,393%
  escursione M1        2009-2019: 0,214‰   2020-2026: 0,239‰
  spread               2021-2023: ~0,19‰   2024-2026: ~0,16‰

**Il mercato dell'oro non e' cambiato. E' cambiato il prezzo.** Tutto cio' che
sembrava un cambio di regime — "la volatilita' e' triplicata", "lo spread e'
raddoppiato" — sparisce dividendo per il livello del prezzo.

DA CUI L'IPOTESI DI QUESTO STUDIO. La taratura ufficiale ha soglie in DOLLARI
FISSI: impulso 4 $, rischio fra 1 e 10 $, buffer 0,30 $. Sono state scelte sul
2020-2026, quando l'oro stava fra 1.800 e 4.700. Applicate al 2009-2019, con
l'oro fra 950 e 1.660, le stesse cifre valgono in termini relativi **due o tre
volte tanto**: un impulso di 4 $ su un oro a 1.000 e' il quadruplo di un
impulso di 4 $ su un oro a 4.000.

Quindi il -39,3 R del 2009-2019 potrebbe non essere sovradattamento. Potrebbe
essere una strategia giusta misurata con il righello sbagliato.

E' un'ipotesi che va presa sul serio ma con diffidenza, perche' e' esattamente
il tipo di spiegazione che fa comodo. Percio' il disegno e' severo:

  - le soglie si riscalano sull'ATR corrente **in ogni mese**, non solo in
    quelli agitati (era gia' il meccanismo previsto dalla taratura, applicato a
    meta'). Un solo interruttore, nessun parametro nuovo, niente da tarare;
  - la mediana ATR di riferimento resta quella congelata del 2020-2024
    (25,5968 $): NON si ricalcola sul periodo in esame, altrimenti si
    starebbe tarando la strategia sui dati su cui la si verifica;
  - si riportano SEMPRE tutti e tre i periodi: 2009-2019 (il fuori campione),
    2020-2022, 2023-2026;
  - si riporta anche la versione a soglie fisse, cosi' il confronto e' diretto.

IPOTESI PRE-REGISTRATE:
  A. con le soglie relative il 2009-2019 smette di essere negativo. Se resta
     negativo, l'unita' non era il problema e il sovradattamento resta la
     spiegazione;
  B. il 2020-2026 NON peggiora in modo sostanziale. Se migliorasse molto anche
     li', sarebbe sospetto: vorrebbe dire che sto guadagnando da un secondo
     grado di liberta' e non da una correzione di unita';
  C. il numero di operazioni per anno diventa piu' stabile fra le epoche. E' il
     controllo meccanico dell'ipotesi: se le soglie sono giuste, la strategia
     deve trovare piu' o meno le stesse occasioni in ogni epoca. Se nel
     2009-2019 le operazioni restano molte meno, le soglie sono ancora sbagliate.

Uso: XAU_ANNI=2009-2026 python3 run_soglie_relative.py
Scrive docs/studies/dati/soglie_relative.parquet
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
MEDIANA_ATR = 25.5968
GIORNI_MAX = 30
PERIODI = [("2009-2019", 2009, 2019), ("2020-2022", 2020, 2022),
           ("2023-2026", 2023, 2026)]
# spread misurato (appendice BN). Prima del 2021 non e' misurato: si usa lo
# stesso valore RELATIVO al prezzo, che BW ha trovato costante. E' l'unica
# ipotesi di questo studio, ed e' conservativa
SPREAD_REL = 0.00019          # frazione del prezzo


def esiti(ops, m1, gestione):
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values
    righe = []
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
        rr, pareggio = gestione
        r, motivo = cammina_uno(apri, fav, sfav, chiu, rr, pareggio)
        costo = (SPREAD_REL * e) / k
        righe.append({"anno": o["anno"], "data": t_in, "rischio$": k,
                      "prezzo": e, "costo": costo, "lordo": r,
                      "netto": r - costo, "motivo": motivo})
    return pd.DataFrame(righe)


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    fuori = []
    for eti, scala in [("soglie fisse in dollari", False),
                       ("soglie relative all'ATR", True)]:
        tutte = genera(m1, T, mediana_atr=MEDIANA_ATR, sempre_scalate=scala)
        uff = [o for o in tutte
               if all(o[f"c_{tf}"] for tf in T.conferme)
               and all(not o[f"c_{tf}"] for tf in T.ritracciamento)]
        print(f"{eti}: {len(tutte)} largo, {len(uff)} ufficiali", flush=True)
        for eti_g, gestione in [("1:10 pareggio +3R", (10.0, 3.0)),
                                ("1:2", (2.0, None))]:
            for eti_c, ops in [("ufficiali", uff), ("largo", tutte)]:
                d = esiti(ops, m1, gestione)
                if d.empty:
                    continue
                d["soglie"], d["gestione"], d["campione"] = eti, eti_g, eti_c
                fuori.append(d)
    t = pd.concat(fuori, ignore_index=True)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "soglie_relative.parquet"), index=False)
    pd.set_option("display.width", 250)

    def riga(x):
        if x.empty:
            return None
        pa = x.netto.groupby(x.anno).sum()
        cum = np.cumsum(x.netto.values)
        dd = float((np.maximum.accumulate(cum) - cum).max())
        return {"op": len(x), "op/anno": len(x) / max(pa.size, 1),
                "stop$": x["rischio$"].median(), "costo%R": x.costo.mean() * 100,
                "lordo R/op": x.lordo.mean(), "netto R/op": x.netto.mean(),
                "netto R": x.netto.sum(),
                "anni+": f"{int((pa > 0).sum())}/{pa.size}",
                "R/DD": x.netto.sum() / dd if dd > 0 else np.nan}

    for eti_g in ("1:10 pareggio +3R", "1:2"):
        for eti_c in ("ufficiali", "largo"):
            print(f"\n=== {eti_c}, gestione {eti_g}")
            f = []
            for eti_p, da, a in PERIODI:
                for eti_s in ("soglie fisse in dollari", "soglie relative all'ATR"):
                    x = t[(t.gestione == eti_g) & (t.campione == eti_c)
                          & (t.soglie == eti_s) & (t.anno >= da) & (t.anno <= a)]
                    r = riga(x)
                    if r:
                        f.append({"periodo": eti_p, "soglie": eti_s, **r})
            if f:
                print(pd.DataFrame(f).set_index(["periodo", "soglie"])
                      .round(3).to_string())

    print("\n=== ipotesi C: le operazioni per anno si stabilizzano?")
    p = t[(t.gestione == "1:10 pareggio +3R") & (t.campione == "ufficiali")]
    a = p.groupby(["anno", "soglie"]).size().unstack()
    a["stop$ relative"] = (p[p.soglie == "soglie relative all'ATR"]
                           .groupby("anno")["rischio$"].median())
    print(a.round(2).to_string())


if __name__ == "__main__":
    main()
