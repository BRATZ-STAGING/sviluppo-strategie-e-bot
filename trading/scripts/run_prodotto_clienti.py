#!/usr/bin/env python3
"""Appendice BR: il criterio giusto — 5-7% annuo, drawdown piccolo, buon rate.

L'utente ha cambiato la domanda, e la nuova e' molto piu' sensata della
vecchia: *"non mi interessa moltiplicare i conti. Voglio una strategia stabile
con un buon rate, poche perdite, drawdown basso. La banca da' il 4% annuo: se
diamo il 5, 6, 7% va benissimo."*

Fin qui ho ottimizzato R per operazione e R/DD, che sono le misure giuste per
massimizzare. Per un prodotto da clienti la misura giusta e' un'altra:
**quanto drawdown costa un 6% annuo**, e quanto e' sopportabile la strada per
arrivarci. Tutto cambia, perche' entra in gioco la **taglia della posizione**,
che finora era fissa all'1% e non era una variabile.

L'ARITMETICA CHE RIBALTA IL PROBLEMA. Con 48 operazioni l'anno e l'1% di
rischio, +0,10 R/op fanno il 4,8% annuo. Con 0,1% di rischio, la stessa
strategia che rende +67 R l'anno ne fa il 6,7%. **Un rendimento del 6% non
richiede un vantaggio grande: richiede un vantaggio POSITIVO e un drawdown
piccolo.** La domanda non e' piu' "chi rende di piu'" ma "chi arriva al 6% con
il buco piu' piccolo e la strada meno spaventosa".

Per questo qui ogni candidata viene **riscalata** perche' renda esattamente il
6% annuo, e poi si confrontano a parita' di rendimento:
  - drawdown massimo, in percentuale del conto;
  - percentuale di operazioni vincenti (il "rate" che l'utente vuole alto);
  - la sequenza di perdite consecutive piu' lunga (quel che fa scappare i
    clienti davvero, piu' del drawdown in se');
  - mesi positivi su totale, e l'anno peggiore.

COSTI VERI: si usa lo spread misurato nell'appendice BN anno per anno (0,33 $
fino al 2024, 0,63 dal 2025), non lo 0,30 della taratura.

UNA GESTIONE NUOVA, e nasce da tutto quel che si e' misurato oggi: **meta' a
1:1, meta' che corre a 1:10 con lo stop a pareggio**. L'appendice BM ha
mostrato che tagliare TUTTA la posizione vicino uccide il rendimento (la coda
paga tutto), e l'appendice BQ che gli obiettivi lontani battono i vicini in
ogni singolo confronto. Ma il rate alto lo da' proprio l'incasso vicino. Meta'
e meta' e' il compromesso che le due misure suggeriscono: si compra il rate
con meta' posizione invece che con tutta.

Uso: python3 run_prodotto_clienti.py
Scrive docs/studies/dati/prodotto_clienti.parquet
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
OBIETTIVO_ANNUO = 6.0            # il bersaglio dell'utente, in percento
# spread vero misurato nell'appendice BN, per anno
SPREAD = {2020: 0.35, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}


def cammina(apri, fav, sfav, chiu, tranche):
    """Percorre l'operazione con una o piu' tranche.

    ``tranche`` e' una lista di (quota, obiettivo, pareggio_da). Ogni tranche
    ha il suo obiettivo; ``pareggio_da`` alza lo stop a zero quando l'MFE
    supera quella soglia. Il risultato torna in unita' di rischio TOTALE.

    Le tranche si muovono insieme sullo stesso percorso di prezzo, ma ognuna
    chiude per conto suo: e' il modo corretto di modellare una posizione
    aperta in una volta e chiusa in piu' pezzi.
    """
    n = len(tranche)
    livello = [-1.0] * n
    chiuso = [None] * n
    mfe = 0.0
    for i in range(len(fav)):
        for j, (_, ob, _) in enumerate(tranche):
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
        mfe = max(mfe, fav[i])
        for j, (_, _, pareggio) in enumerate(tranche):
            if chiuso[j] is None and pareggio is not None and mfe >= pareggio:
                livello[j] = max(livello[j], 0.0)
        if all(c is not None for c in chiuso):
            break
    tot = sum(q * (chiuso[j] if chiuso[j] is not None else chiu[-1])
              for j, (q, _, _) in enumerate(tranche))
    vinte = tot > 0
    return tot, vinte


def misure(serie, date, anni):
    """Le misure che contano per un prodotto, non per una gara di rendimento."""
    cum = np.cumsum(serie)
    dd_R = float((np.maximum.accumulate(cum) - cum).max()) if len(serie) else 0.0
    per_anno = pd.Series(serie).groupby(anni).sum()
    r_anno = per_anno.mean()
    if r_anno <= 0 or dd_R <= 0:
        return None
    # la taglia che porta il rendimento medio esattamente al bersaglio.
    # ATTENZIONE all'unita': ``taglia`` e' gia' "percento di conto per ogni R",
    # quindi rischio per operazione = taglia, NON taglia*100. Moltiplicarla
    # faceva leggere 20% di rischio per operazione dove sono 0,2%.
    taglia = OBIETTIVO_ANNUO / r_anno
    # la striscia di perdite consecutive piu' lunga
    peggio = corrente = 0
    for x in serie:
        corrente = corrente + 1 if x <= 0 else 0
        peggio = max(peggio, corrente)
    mesi = pd.Series(serie, index=pd.DatetimeIndex(date)).resample("ME").sum()
    mesi = mesi[mesi != 0]
    return {
        "op/anno": len(serie) / per_anno.size,
        "R/op": float(np.mean(serie)),
        "vinte%": float((np.asarray(serie) > 0).mean() * 100),
        "rischio/op%": taglia,
        "rendimento%": OBIETTIVO_ANNUO,
        "DD max%": dd_R * taglia,
        "anno peggiore%": float(per_anno.min() * taglia),
        "anni+": int((per_anno > 0).sum()), "anni": per_anno.size,
        "mesi+%": float((mesi > 0).mean() * 100),
        "perdite di fila": peggio,
        "rend/DD": OBIETTIVO_ANNUO / (dd_R * taglia),
    }


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    tutte = genera(m1, T)
    ufficiali = [o for o in tutte
                 if all(o[f"c_{tf}"] for tf in T.conferme)
                 and all(not o[f"c_{tf}"] for tf in T.ritracciamento)]
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values

    # (etichetta, [(quota, obiettivo, pareggio_da), ...])
    GESTIONI = [
        ("ufficiale: tutto a 1:10, pareggio +3R", [(1.0, 10.0, 3.0)]),
        ("meta' a 1:1, meta' a 1:10 con pareggio", [(0.5, 1.0, None), (0.5, 10.0, 0.0)]),
        ("meta' a 1:1,5, meta' a 1:10 con pareggio", [(0.5, 1.5, None), (0.5, 10.0, 0.0)]),
        ("meta' a 1:2, meta' a 1:10 con pareggio", [(0.5, 2.0, None), (0.5, 10.0, 0.0)]),
        ("tre scaglioni 1 / 1,5 / 2 (proposta)",
         [(1 / 3, 1.0, None), (1 / 3, 1.5, 0.0), (1 / 3, 2.0, 0.0)]),
        ("tutto a 1:1", [(1.0, 1.0, None)]),
        ("tutto a 1:2", [(1.0, 2.0, None)]),
        ("tutto a 1:3, pareggio +1R", [(1.0, 3.0, 1.0)]),
    ]

    righe = []
    for eti_c, ops in [("ufficiali", ufficiali), ("largo", tutte)]:
        for eti, tranche in GESTIONI:
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
                r, _ = cammina(apri, fav, sfav, chiu, tranche)
                costo = SPREAD.get(o["anno"], 0.40) / k
                righe.append({"campione": eti_c, "gestione": eti,
                              "data": t_in, "anno": o["anno"],
                              "netto": r - costo})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "prodotto_clienti.parquet"), index=False)
    pd.set_option("display.width", 250)

    for eti_c in ("ufficiali", "largo"):
        print(f"\n=== campione {eti_c} — tutte riscalate al {OBIETTIVO_ANNUO:.0f}% annuo")
        f = []
        for eti, _ in GESTIONI:
            x = t[(t.campione == eti_c) & (t.gestione == eti)].sort_values("data")
            if not len(x):
                continue
            m = misure(x.netto.values, x.data.values, x.anno.values)
            if m is None:
                f.append({"gestione": eti, "op/anno": len(x) / x.anno.nunique(),
                          "R/op": x.netto.mean(),
                          "vinte%": (x.netto > 0).mean() * 100,
                          "rischio/op%": np.nan, "DD max%": np.nan,
                          "anno peggiore%": np.nan, "anni+": np.nan,
                          "mesi+%": np.nan, "perdite di fila": np.nan,
                          "rend/DD": np.nan})
                continue
            f.append({"gestione": eti, **{k2: v for k2, v in m.items()
                                          if k2 != "rendimento%"}})
        d = pd.DataFrame(f).set_index("gestione")
        print(d.round(2).to_string())
        print("  (le righe senza numeri sono in perdita: non esiste una taglia "
              "che le porti al 6%)")

    # LA VERIFICA CHE CONTA. Ho provato otto gestioni: se ne scelgo una guardando
    # la tabella qui sopra, sto pescando, ed e' proprio l'errore che l'appendice
    # BP ha appena tarato (mezzo R di separazione nasce dal nulla). L'unica cosa
    # che rende una scelta difendibile e' che regga su due periodi separati che
    # non si sono guardati a vicenda.
    print("\n\n=== verifica: ricerca 2020-2022 contro verifica 2023-2026")
    for eti_c in ("ufficiali", "largo"):
        f = []
        for eti, _ in GESTIONI:
            riga = {"gestione": eti}
            for nome, (da, aa) in [("ricerca", (2020, 2022)), ("verifica", (2023, 2026))]:
                x = t[(t.campione == eti_c) & (t.gestione == eti)
                      & (t.anno >= da) & (t.anno <= aa)].sort_values("data")
                if not len(x):
                    continue
                pa = x.netto.groupby(x.anno).sum()
                cum = np.cumsum(x.netto.values)
                dd = float((np.maximum.accumulate(cum) - cum).max())
                riga[f"{nome} R/op"] = x.netto.mean()
                riga[f"{nome} R/anno"] = pa.mean()
                riga[f"{nome} vinte%"] = (x.netto > 0).mean() * 100
                riga[f"{nome} R/DD"] = pa.sum() / dd if dd > 0 else np.nan
                riga[f"{nome} anni+"] = f"{int((pa > 0).sum())}/{pa.size}"
            f.append(riga)
        print(f"\n  campione {eti_c}")
        print(pd.DataFrame(f).set_index("gestione").round(3).to_string())


if __name__ == "__main__":
    main()
