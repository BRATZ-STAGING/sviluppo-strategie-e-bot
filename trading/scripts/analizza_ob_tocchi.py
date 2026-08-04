#!/usr/bin/env python3
"""Appendice BB, parte 2: le quattro domande sulla ridefinizione degli OB.

Legge ``ob_tocchi.parquet`` e risponde a quello che l'utente ha chiesto:

1. **la scadenza a 30 candele buttava via zone buone?** Si guarda il
   rendimento in funzione dell'ETA' della zona al momento del tocco. Se le
   zone vecchie rendono quanto le fresche, la scadenza toglieva soltanto
   occasioni; se rendono meno, la scadenza aveva un senso.
2. **il primo tocco vale piu' del secondo e del terzo?** E' la differenza fra
   "order block" e "supporto o resistenza".
3. **quale definizione di tocco?** chiusura sul timeframe della zona, su M12,
   su M6, oppure l'ombra.
4. **la zona rotta muore o si ribalta?** I tocchi dopo l'invalidazione,
   operati al contrario, valgono qualcosa?

Ogni risposta e' affiancata al PLACEBO (la stessa zona spostata a caso) e
divisa fra periodo di ricerca (2009-2019) e di verifica (2020-2026).

Uso: python3 analizza_ob_tocchi.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATI = os.path.join(ROOT, "docs", "studies", "dati")
GREZZI = os.environ.get("GREZZI", os.path.join(ROOT, "..", "dati_grezzi"))
VECCHIO, NUOVO = (2009, 2019), (2020, 2026)
MIN_OP = 60
CELLA = "r|0.5|3.0"           # riferimento: stop mezzo ATR, obiettivo 1:3


def sintesi(d, col):
    r = d[col].dropna()
    if len(r) < 5:
        return None
    anni = d.loc[r.index, "anno"]
    per_anno = r.groupby(anni).sum()
    return {"op": len(r), "R": r.sum(), "r_op": r.mean(),
            "vinte": (r > 0).mean() * 100,
            "anni_pos": int((per_anno > 0).sum()), "anni": len(per_anno)}


def confronta(t, chiavi, col=CELLA, minimo=MIN_OP):
    """Per ogni gruppo: vero contro placebo, sui due periodi."""
    righe = []
    for valori, g in t.groupby(chiavi, observed=True):
        if not isinstance(valori, tuple):
            valori = (valori,)
        riga = dict(zip(chiavi, valori))
        ok = True
        for eti, (da, a) in (("v", VECCHIO), ("n", NUOVO)):
            p = g[(g.anno >= da) & (g.anno <= a)]
            for chi, sel in (("", p[p.vero]), ("_pl", p[~p.vero])):
                s = sintesi(sel, col)
                if s is None or (chi == "" and s["op"] < minimo):
                    ok = False
                    break
                for k, v in s.items():
                    riga[f"{k}_{eti}{chi}"] = v
            if not ok:
                break
        if ok:
            riga["delta_v"] = riga["r_op_v"] - riga["r_op_v_pl"]
            riga["delta_n"] = riga["r_op_n"] - riga["r_op_n_pl"]
            righe.append(riga)
    return pd.DataFrame(righe)


def mostra(df, chiavi, titolo):
    print(f"\n=== {titolo}")
    if df.empty:
        print("  nessun gruppo con abbastanza operazioni")
        return
    col = chiavi + ["op_v", "r_op_v", "r_op_v_pl", "delta_v", "anni_pos_v",
                    "op_n", "r_op_n", "r_op_n_pl", "delta_n", "anni_pos_n"]
    print(df[col].round(3).to_string(index=False))


def main():
    t = pd.read_parquet(os.path.join(GREZZI, "ob_tocchi.parquet"))
    pd.set_option("display.width", 250)
    print(f"tocchi: {int(t.vero.sum())} veri, {int((~t.vero).sum())} placebo, "
          f"{t.anno.min()}-{t.anno.max()}")
    vivi = t[~t.dopo_invalidazione]          # variante "la zona muore"

    # 1 - eta' della zona al tocco
    fasce = pd.cut(vivi.eta, [-1, 5, 15, 30, 60, 120, 10 ** 9],
                   labels=["0-5", "6-15", "16-30", "31-60", "61-120", "oltre 120"])
    q = vivi.assign(fascia=fasce)
    mostra(confronta(q[q.definizione == "chiusura tf"], ["fascia"]),
           ["fascia"],
           "1 · eta' della zona al tocco, in candele (la scadenza era a 30)")

    # 2 - numero del tocco
    mostra(confronta(vivi[vivi.definizione == "chiusura tf"], ["tocco"]),
           ["tocco"], "2 · quale tocco e' (4 = quarto o oltre)")
    mostra(confronta(vivi[vivi.definizione == "chiusura tf"], ["tf", "tocco"]),
           ["tf", "tocco"], "2b · per timeframe")

    # 3 - definizione di tocco
    mostra(confronta(vivi, ["definizione"]), ["definizione"],
           "3 · cosa conta come tocco")
    mostra(confronta(vivi[vivi.tocco == 1], ["definizione", "tf"]),
           ["definizione", "tf"], "3b · solo il primo tocco, per timeframe")

    # 4 - dopo l'invalidazione: la zona si ribalta?
    mostra(confronta(t[t.dopo_invalidazione], ["definizione"]), ["definizione"],
           "4 · tocchi DOPO l'invalidazione, operati al contrario")

    # quadro d'insieme su tutte le combinazioni di stop e obiettivo
    print("\n=== il quadro completo: quante celle battono il placebo")
    fuori = []
    for c in [x for x in t.columns if x.startswith("r|")]:
        d = confronta(vivi, ["tf", "definizione", "tocco"], col=c)
        if d.empty:
            continue
        d["cella"] = c
        fuori.append(d)
    tutto = pd.concat(fuori, ignore_index=True) if fuori else pd.DataFrame()
    if tutto.empty:
        print("  niente da contare")
        return
    scelte = tutto[(tutto.r_op_v > 0) & (tutto.delta_v >= 0.05)]
    reggono = scelte[scelte.r_op_n > 0]
    print(f"  celle misurabili: {len(tutto)}")
    print(f"  positive e sopra il placebo sul 2009-2019: {len(scelte)}")
    print(f"  di queste, ancora positive sul 2020-2026: {len(reggono)}")
    if len(scelte):
        col = ["tf", "definizione", "tocco", "cella", "op_v", "r_op_v",
               "delta_v", "anni_pos_v", "op_n", "r_op_n", "delta_n", "anni_pos_n"]
        print(scelte.sort_values("r_op_n", ascending=False)[col]
              .head(12).round(3).to_string(index=False))
    tutto.to_parquet(os.path.join(DATI, "ob_tocchi_celle.parquet"), index=False)


if __name__ == "__main__":
    main()
