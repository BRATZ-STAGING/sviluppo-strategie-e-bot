#!/usr/bin/env python3
"""Appendice AZ, parte 2: scrematura delle celle e prova delle confluenze.

Legge gli eventi prodotti da ``run_livelli_atr.py`` e applica il protocollo
fissato prima di guardare i numeri:

  1. una CELLA e' (timeframe, famiglia, modo, stop in ATR, obiettivo);
  2. si sceglie sul 2009-2019 chiedendo tre cose insieme: almeno MIN_OP
     operazioni, risultato per operazione positivo, e vantaggio sul proprio
     PLACEBO di almeno MARGINE R per operazione;
  3. le celle scelte si verificano sul 2020-2026, che non ha partecipato;
  4. si conta quante sopravvivono e si confronta con quante ne sopravvivrebbero
     per solo effetto del caso (le stesse tre condizioni applicate al placebo).

In coda la domanda dell'utente sulle confluenze: quando piu' famiglie di
livelli si accendono insieme, dalla stessa parte e a pochi minuti di
distanza, il risultato migliora?

Uso: python3 analizza_livelli.py
Scrive docs/studies/dati/livelli_celle.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATI = os.path.join(ROOT, "docs", "studies", "dati")
VECCHIO, NUOVO = (2009, 2019), (2020, 2026)
MIN_OP = 80                 # sotto questa soglia una cella non e' misurabile
MARGINE = 0.05              # vantaggio minimo sul placebo, in R per operazione
FINESTRA_CONF = 30          # minuti entro cui due livelli sono "insieme"
VICINO = 0.25               # ATR entro cui due livelli sono "sullo stesso prezzo"


def chiave(t):
    return (t.tf + " · " + t.famiglia + " · " + t.modo + " · stop "
            + t["q"].astype(str) + " ATR · 1:" + t.rr.astype(str))


def per_cella(t, periodo):
    """Una riga per cella. Dodici raggruppamenti sulla tabella degli eventi,
    non uno solo su quella distesa: distendere 293.000 eventi per dodici
    colonne fa 3,5 milioni di righe e l'aggregazione non finisce piu'."""
    p = t[(t.anno >= periodo[0]) & (t.anno <= periodo[1])]
    chiavi = ["tf", "famiglia", "modo", "vero"]
    fuori = []
    for c in [x for x in t.columns if x.startswith("r|")]:
        q, rr = (float(x) for x in c[2:].split("|"))
        d = p[chiavi + ["anno", c]].dropna(subset=[c]).rename(columns={c: "r"})
        if d.empty:
            continue
        d["vinta"] = d.r > 0
        g = d.groupby(chiavi, observed=True).agg(
            op=("r", "size"), R=("r", "sum"), r_op=("r", "mean"),
            vinte=("vinta", "mean"))
        g["vinte"] *= 100
        anni = d.groupby(chiavi + ["anno"], observed=True).r.sum().reset_index()
        anni["pos"] = anni.r > 0
        a = anni.groupby(chiavi, observed=True).agg(
            anni_pos=("pos", "sum"), anni=("pos", "size"))
        fuori.append(g.join(a).reset_index().assign(q=q, rr=rr))
    return pd.concat(fuori, ignore_index=True)


def affianca(g):
    """Mette vero e placebo sulla stessa riga."""
    v = g[g.vero].drop(columns="vero")
    f = g[~g.vero].drop(columns="vero")
    return v.merge(f, on=["tf", "famiglia", "modo", "q", "rr"],
                   suffixes=("", "_pl"), how="left")


def scrematura(t):
    vec, nuo = affianca(per_cella(t, VECCHIO)), affianca(per_cella(t, NUOVO))
    tutto = vec.merge(nuo, on=["tf", "famiglia", "modo", "q", "rr"],
                      suffixes=("_v", "_n"), how="inner")
    scelte = tutto[(tutto.op_v >= MIN_OP) & (tutto.r_op_v > 0)
                   & (tutto.r_op_v - tutto.r_op_pl_v.fillna(0) >= MARGINE)]
    # quante celle passerebbero gli stessi tre filtri applicati al PLACEBO:
    # e' il numero di sopravvissuti attesi per solo effetto del caso
    caso = tutto[(tutto.op_pl_v >= MIN_OP) & (tutto.r_op_pl_v > 0)
                 & (tutto.r_op_pl_v - tutto.r_op_v >= MARGINE)]
    return tutto, scelte, caso


def confluenze(t):
    """Quante famiglie diverse si accendono insieme SULLO STESSO PREZZO.

    Contarle guardando solo il tempo non dice niente: con 169.000 eventi in
    diciotto anni, dentro mezz'ora ci sono quasi sempre tutte e cinque le
    famiglie, e la misura viene piatta. Una confluenza vera vuole i livelli
    allo stesso PREZZO: qui due eventi contano insieme se distano meno di
    ``VICINO`` ATR e meno di ``FINESTRA_CONF`` minuti.
    """
    v = t[t.vero].sort_values("time").reset_index(drop=True).copy()
    v["min"] = v.time.astype("int64") // 60_000_000_000
    v["cesto"] = np.round(v.entry.values / (v.atr.values * VICINO)).astype(np.int64)
    v["conf"] = 1
    fam_num = {f: i for i, f in enumerate(v.famiglia.unique())}
    for (_, _), g in v.groupby(["lato", "cesto"], sort=False):
        if len(g) < 2:
            continue
        minuti = g["min"].values
        visti = np.zeros((len(g), len(fam_num)), bool)
        for f, k in fam_num.items():
            mf = np.sort(minuti[g.famiglia.values == f])
            if not len(mf):
                continue
            a = np.searchsorted(mf, minuti - FINESTRA_CONF, "left")
            b = np.searchsorted(mf, minuti + FINESTRA_CONF, "right")
            visti[:, k] = b > a
        v.loc[g.index, "conf"] = visti.sum(axis=1)
    return v


def main():
    t = pd.read_parquet(os.path.join(DATI, "livelli_atr.parquet"))
    pd.set_option("display.width", 240)
    print("caricato", flush=True)
    print(f"eventi: {int(t.vero.sum())} veri, {int((~t.vero).sum())} placebo, "
          f"{t.anno.min()}-{t.anno.max()}")
    tutto, scelte, caso = scrematura(t)
    tutto.to_parquet(os.path.join(DATI, "livelli_celle.parquet"), index=False)

    print("celle calcolate", flush=True)
    grandi = tutto[tutto.op_v >= MIN_OP]
    delta = (grandi.r_op_v - grandi.r_op_pl_v.fillna(0))
    print(f"\n=== celle misurabili: {len(tutto)}, di cui {len(grandi)} con almeno "
          f"{MIN_OP} operazioni sul {VECCHIO[0]}-{VECCHIO[1]}")
    print(f"  con R/op > 0 sul periodo di ricerca: {int((grandi.r_op_v > 0).sum())}"
          f" ({(grandi.r_op_v > 0).mean() * 100:.0f}%)")
    print(f"  positive su ENTRAMBI i periodi: "
          f"{int(((grandi.r_op_v > 0) & (grandi.r_op_n > 0)).sum())}")
    print(f"  vantaggio sul placebo, R/op: mediana {delta.median():+.4f}, "
          f"p90 {delta.quantile(.9):+.4f}, massimo {delta.max():+.4f}")
    print(f"scelte sul {VECCHIO[0]}-{VECCHIO[1]} (>= {MIN_OP} op, R/op > 0, "
          f"+{MARGINE} R/op sul placebo): {len(scelte)}")
    print(f"stesse condizioni sul placebo (quante ne darebbe il caso): {len(caso)}")
    if len(scelte):
        reggono = scelte[scelte.r_op_n > 0]
        print(f"delle {len(scelte)} scelte, sopravvivono sul {NUOVO[0]}-{NUOVO[1]}: "
              f"{len(reggono)} ({len(reggono) / len(scelte) * 100:.0f}%)")
        col = ["tf", "famiglia", "modo", "q", "rr", "op_v", "r_op_v", "r_op_pl_v",
               "anni_pos_v", "anni_v", "op_n", "r_op_n", "R_n", "anni_pos_n", "anni_n"]
        print("\n  le scelte, ordinate per risultato sul periodo di verifica")
        print(scelte.sort_values("r_op_n", ascending=False)[col]
              .head(15).round(3).to_string(index=False))

    print("\n=== la cella migliore su TUTTI i 18 anni (per curiosita', non e' una scelta)")
    g = affianca(per_cella(t, (2009, 2026)))
    g = g[g.op >= MIN_OP * 2]
    col2 = ["tf", "famiglia", "modo", "q", "rr", "op", "R", "r_op", "vinte",
            "anni_pos", "anni", "r_op_pl"]
    print(g.nlargest(8, "r_op")[col2].round(3).to_string(index=False))

    print(f"\n=== confluenze: famiglie diverse entro {VICINO} ATR e "
          f"{FINESTRA_CONF} minuti, stessa direzione", flush=True)
    v = confluenze(t)
    col3 = [c for c in t.columns if c.startswith("r|")]
    for cella in ["r|0.5|3.0", "r|0.5|5.0", "r|1.0|3.0"]:
        if cella not in col3:
            continue
        r = v[["conf", cella, "anno"]].dropna()
        agg = r.groupby(r.conf.clip(upper=4)).agg(
            op=(cella, "size"), r_op=(cella, "mean"), R=(cella, "sum"))
        agg["anni_pos"] = r.groupby([r.conf.clip(upper=4), r.anno])[cella].sum(
            ).gt(0).groupby(level=0).sum()
        print(f"\n  {cella.replace('r|', 'stop ').replace('|', ' ATR, obiettivo 1:')}")
        print(agg.round(3).to_string())


if __name__ == "__main__":
    main()
