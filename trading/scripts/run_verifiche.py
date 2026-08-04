#!/usr/bin/env python3
"""Appendici AW-AY: le tre verifiche dopo il crollo fuori campione.

Tutte e tre leggono ``verifiche_base.parquet`` (un solo passaggio sui
diciotto anni, vedi ``prepara_verifiche.py``), quindi girano in un secondo.

AW  **filtro di regime**. Il vantaggio del 2020-2026 potrebbe vivere in un
    regime preciso. Il filtro si DEFINISCE sul periodo buono (dove sta il
    banco di prova fra il 10simo e il 90simo percentile della misura) e si
    APPLICA al 2009-2019, che resta intatto. Se la parte di 2009-2019 che
    somiglia al 2020-2026 guadagna, la spiegazione "regime" regge.

AX  **rinuncia al lato corto**. Su diciotto anni lo short rende +6,2 R su 259
    operazioni. Qui si guarda cosa succede al sistema togliendolo.

AY  **taratura invertita**. Non e' una ricerca di parametri migliori: e' una
    prova del METODO. Si ripete la stessa identica ricerca (12 gestioni x 7
    obiettivi x 27 combinazioni di conferme = 2.268 celle) prima sul
    2009-2019 e poi sul 2020-2026, e ogni volta si verifica il vincitore
    sull'altro periodo. Se una ricerca cosi' produce vincitori che non
    reggono dall'altra parte, il problema non e' la taratura scelta: e' il
    modo di sceglierla.

Uso: python3 run_verifiche.py
Scrive docs/studies/dati/verifiche.parquet
"""
import itertools
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.taratura import UFFICIALE as T                    # noqa: E402

from run_scale_trailing import GESTIONI, OBIETTIVI               # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BASE = os.path.join(ROOT, "docs", "studies", "dati", "verifiche_base.parquet")
UFF = "r|pari a +3R (in uso)|10"
VECCHIO, NUOVO = (2009, 2019), (2020, 2026)
LIBERI = ["M33", "H12", "M12"]         # H6 e H2 sono gia' la struttura
MIN_OP = 60                            # sotto questa soglia un vincitore non conta


def periodo(t, quale):
    return (t.anno >= quale[0]) & (t.anno <= quale[1])


def sintesi(r, anni):
    if len(r) == 0:
        return {"op": 0, "R": 0.0, "R/op": 0.0, "vinte%": 0.0, "DD": 0.0,
                "anni+": 0, "anni": 0}
    cum = np.cumsum(r)
    pa = np.array([r[anni == a].sum() for a in np.unique(anni)])
    return {"op": len(r), "R": r.sum(), "R/op": r.mean(),
            "vinte%": (r > 0).mean() * 100,
            "DD": (np.maximum.accumulate(cum) - cum).max(),
            "anni+": int((pa > 0).sum()), "anni": len(pa)}


def ufficiali(t):
    """La selezione delle conferme in vigore: M33 e H12 allineate, M12 contrario."""
    ok = np.ones(len(t), bool)
    for tf in T.conferme:
        ok &= t[f"c_{tf}"].values == 1
    for tf in T.ritracciamento:
        ok &= t[f"c_{tf}"].values == 0
    return ok


# --------------------------------------------------------------------------
def aw_regime(t):
    print("\n=== AW · filtro di regime: la parte di 2009-2019 che somiglia al 2020+")
    u = t[ufficiali(t)].dropna(subset=["atr_pct", "sopra50", "sopra200"])
    vec, nuo = u[periodo(u, VECCHIO)], u[periodo(u, NUOVO)]
    print(f"  riferimento: {len(nuo)} operazioni 2020-2026, "
          f"banco di prova {len(vec)} del 2009-2019")
    righe = []
    for mis, eti in [("atr_pct", "volatilita' (ATR in % del prezzo)"),
                     ("sopra50", "distanza dalla media 50 (in ATR)"),
                     ("sopra200", "distanza dalla media 200 (in ATR)")]:
        lo, hi = np.percentile(nuo[mis], [10, 90])
        dentro = (vec[mis] >= lo) & (vec[mis] <= hi)
        a = sintesi(vec[UFF].values[dentro.values], vec.anno.values[dentro.values])
        b = sintesi(vec[UFF].values[~dentro.values], vec.anno.values[~dentro.values])
        righe.append({"misura": eti, "da": round(lo, 2), "a": round(hi, 2),
                      **{f"dentro_{k}": v for k, v in a.items()},
                      **{f"fuori_{k}": v for k, v in b.items()}})
        print(f"  {eti:34s} [{lo:6.2f},{hi:6.2f}] "
              f"dentro {a['op']:3d} op {a['R']:+7.1f} R ({a['R/op']:+.2f}/op, "
              f"{a['anni+']}/{a['anni']} anni) · fuori {b['op']:3d} op {b['R']:+7.1f} R")
    # tutte e tre insieme
    m = np.ones(len(vec), bool)
    for mis in ("atr_pct", "sopra50", "sopra200"):
        lo, hi = np.percentile(nuo[mis], [10, 90])
        m &= (vec[mis].values >= lo) & (vec[mis].values <= hi)
    a = sintesi(vec[UFF].values[m], vec.anno.values[m])
    print(f"  {'tutte e tre le condizioni':34s} {'':15s} "
          f"dentro {a['op']:3d} op {a['R']:+7.1f} R ({a['R/op']:+.2f}/op, "
          f"{a['anni+']}/{a['anni']} anni)")
    righe.append({"misura": "tutte e tre", "da": None, "a": None,
                  **{f"dentro_{k}": v for k, v in a.items()}})
    return pd.DataFrame(righe).assign(verifica="AW")


# --------------------------------------------------------------------------
def ax_solo_long(t):
    print("\n=== AX · togliere il lato corto")
    u = t[ufficiali(t)]
    righe = []
    for eti, quale in [("2009-2019", VECCHIO), ("2020-2026", NUOVO),
                       ("2009-2026", (2009, 2026))]:
        p = u[periodo(u, quale)]
        for lato, sel in [("long+short", np.ones(len(p), bool)),
                          ("solo long", (p.lato == "long").values),
                          ("solo short", (p.lato == "short").values)]:
            s = sintesi(p[UFF].values[sel], p.anno.values[sel])
            righe.append({"periodo": eti, "selezione": lato, **s})
            print(f"  {eti} {lato:11s} {s['op']:4d} op {s['R']:+7.1f} R "
                  f"({s['R/op']:+.2f}/op) DD {s['DD']:5.1f} "
                  f"anni+ {s['anni+']}/{s['anni']}")
    return pd.DataFrame(righe).assign(verifica="AX")


# --------------------------------------------------------------------------
def combinazioni():
    """27 modi di usare i tre TF liberi: allineato, contrario, ignorato."""
    for stati in itertools.product((1, 0, None), repeat=len(LIBERI)):
        yield dict(zip(LIBERI, stati))


def maschera(t, comb):
    ok = np.ones(len(t), bool)
    for tf, st in comb.items():
        if st is not None:
            ok &= t[f"c_{tf}"].values == st
    return ok


def cerca(t, quale):
    """La griglia completa su un periodo; ritorna la tabella ordinata."""
    p = t[periodo(t, quale)]
    righe = []
    for comb in combinazioni():
        m = maschera(p, comb)
        if m.sum() < MIN_OP:
            continue
        anni = p.anno.values[m]
        for nome, _, _ in GESTIONI:
            for rr in OBIETTIVI:
                r = p[f"r|{nome}|{rr}"].values[m]
                righe.append({"conferme": "·".join(
                    f"{tf}{'+' if s == 1 else '-'}" for tf, s in comb.items()
                    if s is not None) or "nessuna",
                    "gestione": nome, "rr": rr, **sintesi(r, anni)})
    return pd.DataFrame(righe).sort_values("R", ascending=False)


def ay_invertita(t):
    print(f"\n=== AY · taratura invertita: stessa ricerca sui due periodi "
          f"({len(list(combinazioni())) * len(GESTIONI) * len(OBIETTIVI)} celle, "
          f"minimo {MIN_OP} operazioni)")
    righe = []
    for eti, cerca_su, verifica_su in [("2009-2019", VECCHIO, NUOVO),
                                       ("2020-2026", NUOVO, VECCHIO)]:
        g = cerca(t, cerca_su)
        print(f"\n  ricerca su {eti}: {len(g)} celle valide, le prime tre")
        for _, v in g.head(3).iterrows():
            p = t[periodo(t, verifica_su)]
            m = maschera(p, {tf: (1 if f"{tf}+" in v.conferme else
                                  (0 if f"{tf}-" in v.conferme else None))
                             for tf in LIBERI})
            fuori = sintesi(p[f"r|{v.gestione}|{int(v.rr)}"].values[m],
                            p.anno.values[m])
            print(f"    {v.conferme:22s} {v.gestione:20s} 1:{v.rr:<4.0f} "
                  f"scelta {v.R:+7.1f} R su {v.op:3d} op ({v['R/op']:+.2f}, "
                  f"{v['anni+']}/{v['anni']} anni) -> "
                  f"altrove {fuori['R']:+7.1f} R su {fuori['op']:3d} op "
                  f"({fuori['R/op']:+.2f}, {fuori['anni+']}/{fuori['anni']} anni)")
            righe.append({"cercata_su": eti, "conferme": v.conferme,
                          "gestione": v.gestione, "rr": v.rr,
                          **{f"scelta_{k}": v[k] for k in
                             ("op", "R", "R/op", "vinte%", "DD", "anni+", "anni")},
                          **{f"altrove_{k}": x for k, x in fuori.items()}})
        # quante celle positive in entrambi i periodi
        buone = 0
        for _, v in g.iterrows():
            p = t[periodo(t, verifica_su)]
            m = maschera(p, {tf: (1 if f"{tf}+" in v.conferme else
                                  (0 if f"{tf}-" in v.conferme else None))
                             for tf in LIBERI})
            if m.sum() >= MIN_OP and p[f"r|{v.gestione}|{int(v.rr)}"].values[m].sum() > 0:
                buone += 1
        print(f"    celle positive anche sull'altro periodo: {buone}/{len(g)} "
              f"({buone / max(len(g), 1) * 100:.0f}%)")
    return pd.DataFrame(righe).assign(verifica="AY")


def main():
    t = pd.read_parquet(BASE)
    print(f"base: {len(t)} segnali grezzi, {int(ufficiali(t).sum())} con le "
          f"conferme in vigore, {t.anno.min()}-{t.anno.max()}")
    parti = [aw_regime(t), ax_solo_long(t), ay_invertita(t)]
    pd.concat(parti, ignore_index=True).to_parquet(
        os.path.join(ROOT, "docs", "studies", "dati", "verifiche.parquet"),
        index=False)


if __name__ == "__main__":
    main()
