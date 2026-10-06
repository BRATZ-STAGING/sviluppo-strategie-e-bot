"""Oro con i costi veri FP Markets Raw: rifacimento di F1 (orologio) e F2 (momentum).

Registrazione vincolante: docs/costi-fp-raw-oro-registrazione.md (commit 4e59d3f).
Solo XAUUSD, solo D:\\ricerca_zero\\scoperta\\XAUUSD_*.parquet (2009-2017).
Le funzioni sono quelle di zero_f1_orologio.py e zero_f2_momentum.py, importate
e NON modificate: qui si cambia solo il costo dell'oro nei loro dizionari
(f1.COST, f2.COSTO) e si scrive in una cartella di risultati separata.

Passi:
  1. costo originale 0,40 -> deve coincidere con D:\\ricerca_zero\\risultati
     (f1_varianti, f2_fasea, f2_faseb, righe XAUUSD): controllo esatto;
  2. costo 0,20 (base) e 0,30 (prova di resistenza);
  3. promozione: netto > 0 a 0,20 E a 0,30; t >= 3, anni >= 75%, placebo
     p < 0,01 al costo base 0,20; n minimo dell'originale (F1: 100 come in
     zero_f1_orologio.main; F2: 200, 100 se L o H >= 1 giorno); esclusa H3;
     massimo 3 per famiglia (migliori per t a 0,20).

Uso: python trading/scripts/oro_fp_f1f2.py
Uscite: D:\\ricerca_oro_fp\\risultati\\f1f2_*.parquet
"""
from __future__ import annotations

import gc
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)

import zero_f1_orologio as f1        # noqa: E402
import zero_f2_momentum as f2        # noqa: E402

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)

SYM = "XAUUSD"
ORIG = Path(r"D:\ricerca_zero\risultati")
OUT = Path(r"D:\ricerca_oro_fp\risultati")
COSTI = [0.40, 0.20, 0.30]                # 0,40 = originale (riproduzione)
BASE, STRESS = 0.20, 0.30
# H3 (gia' verificata 2018-2026): esclusa dalla promozione
H3 = ("R4a", "Asia primi 60m -> resto, inverti solo long")

assert f1.SRC == r"D:\ricerca_zero\scoperta" and str(f2.SCOP).replace("/", "\\") == r"D:\ricerca_zero\scoperta"


def uguali(a: pd.DataFrame, b: pd.DataFrame, cols) -> list[str]:
    """Colonne che differiscono (NaN == NaN, tolleranza 1e-9)."""
    bad = []
    for c in cols:
        x, y = a[c].to_numpy(float), b[c].to_numpy(float)
        ok = (np.isnan(x) & np.isnan(y)) | np.isclose(x, y, rtol=0, atol=1e-9)
        if not ok.all():
            bad.append(f"{c}({int((~ok).sum())})")
    return bad


# ---------------------------------------------------------------- F1
def esegui_f1():
    h1 = f1.correggi_ora(pd.read_parquet(f"{f1.SRC}\\{SYM}_H1.parquet"), SYM)
    m5 = f1.correggi_ora(pd.read_parquet(f"{f1.SRC}\\{SYM}_M5.parquet"), SYM)
    px = f1.Px(m5)
    del m5
    tabs, ops = [], []
    for c in COSTI:
        f1.COST[SYM] = c
        f1.RES.clear()
        f1.KEEP.clear()                       # vid parte da 0 come nell'originale (XAUUSD e' il primo mercato)
        f1.regole(SYM, h1, px)
        r = pd.DataFrame(f1.RES)
        r["costo"] = c
        tabs.append(r)
        for k, v in f1.KEEP.items():
            ops.append(v.assign(id=k, costo=c))
    f1.COST[SYM] = 0.40
    del h1, px
    gc.collect()
    R = pd.concat(tabs, ignore_index=True)
    # riproduzione
    o = pd.read_parquet(ORIG / "f1_varianti.parquet")
    o = o[o.mercato == SYM].sort_values("id").reset_index(drop=True)
    q = R[R.costo == 0.40].sort_values("id").reset_index(drop=True)
    assert len(o) == len(q) and (o.variante == q.variante).all() and (o.blocco == q.blocco).all()
    bad = uguali(o, q, ["n", "lordo", "netto", "netto_bp", "t", "t_lordo", "anni_pos", "anni", "p"])
    print(f"F1 riproduzione 0,40: {len(q)} varianti, differenze: {bad or 'nessuna'}", flush=True)
    R = R.rename(columns={"p": "p_placebo"})
    R["chiave"] = R.blocco + " | " + R.variante
    R["nmin"] = 100
    R["anni_frac"] = R.anni_pos / R.anni
    R["h3"] = (R.blocco == H3[0]) & (R.variante == H3[1])
    R.to_parquet(OUT / "f1f2_f1_varianti.parquet")
    if ops:
        pd.concat(ops).to_parquet(OUT / "f1f2_f1_operazioni_t2.parquet")
    return R, not bad


# ---------------------------------------------------------------- F2
def esegui_f2():
    P = f2.prepara(SYM)
    A = pd.DataFrame(f2.fase_a(SYM, P))
    oa = pd.read_parquet(ORIG / "f2_fasea.parquet")
    oa = oa[oa.mercato == SYM].reset_index(drop=True)
    assert len(oa) == len(A) and (oa[["L", "H", "sessione"]].values == A[["L", "H", "sessione"]].values).all()
    bad_a = uguali(oa, A, ["b", "t_pend", "n", "coda_m", "t_coda", "n_coda", "t_basso", "t_medio", "t_alto"])
    A.to_parquet(OUT / "f1f2_f2_fasea.parquet")
    S = f2.selezione(A)
    righe = []
    for c in COSTI:
        f2.COSTO[SYM] = c
        for _, cl in S.iterrows():
            for k in f2.KS:
                for rg in f2.REGIMI:
                    r = f2.regola(P, SYM, cl.L, cl.H, cl.sessione, k, rg, int(cl.segno))
                    if r is None:
                        r = dict(mercato=SYM, L=cl.L, H=cl.H, sessione=cl.sessione, k=k, regime=rg,
                                 direzione="a favore" if cl.segno > 0 else "contro", n=0)
                    r["costo"] = c
                    righe.append(r)
        print(f"F2 costo {c:.2f}: fatto", flush=True)
    f2.COSTO[SYM] = 0.40
    del P
    gc.collect()
    B = pd.DataFrame(righe)
    ob = pd.read_parquet(ORIG / "f2_faseb.parquet")
    ob = ob[ob.mercato == SYM].reset_index(drop=True)
    q = B[B.costo == 0.40].reset_index(drop=True)
    kc = ["L", "H", "sessione", "k", "regime", "direzione"]
    assert len(ob) == len(q) and (ob[kc].values == q[kc].values).all()
    bad_b = uguali(ob, q, ["n", "netto", "lordo", "t", "t_rob", "anni_pos", "anni", "p_placebo"])
    print(f"F2 riproduzione 0,40: fase A {len(A)} celle diff {bad_a or 'nessuna'}; "
          f"fase B {len(q)} regole ({len(S)} celle) diff {bad_b or 'nessuna'}", flush=True)
    B["chiave"] = (B.L + "->" + B.H + " " + B.sessione + " k" + B.k.astype(str) + " " + B.regime
                   + " " + B.direzione)
    lento = B.L.isin(["1g", "5g"]) | B.H.isin(["1g", "5g"])
    B["nmin"] = np.where(lento, 100, 200)
    B["h3"] = False
    B["anni_frac"] = B.quota_anni
    B.to_parquet(OUT / "f1f2_f2_faseb.parquet")
    return B, not (bad_a or bad_b)


# ---------------------------------------------------------------- confronto costi e promozione
def larga(R: pd.DataFrame) -> pd.DataFrame:
    """Una riga per variante: numeri al costo base + netto/t agli altri costi."""
    b = R[R.costo == BASE].set_index("chiave")
    out = b[["n", "nmin", "h3", "lordo", "netto", "t", "anni_pos", "anni", "anni_frac", "p_placebo"]].copy()
    for c, s in ((0.40, "040"), (STRESS, "030")):
        x = R[R.costo == c].set_index("chiave")
        out[f"netto_{s}"] = x.netto
        out[f"t_{s}"] = x.t
        out[f"anni_pos_{s}"] = x.anni_pos
    out = out.rename(columns={"netto": "netto_020", "t": "t_020"})
    out["promossa"] = ((out.netto_020 > 0) & (out.netto_030 > 0) & (out.t_020 >= 3)
                       & (out.anni_frac >= 0.75) & (out.p_placebo < 0.01) & (out.n >= out.nmin) & ~out.h3)
    return out


def riassunto(nome, W):
    calc = W[W.t_020.notna()]
    pos = {s: int((W[f"netto_{s}"] > 0).sum()) for s in ("040", "020", "030")}
    print(f"\n{nome}: varianti {len(W)} (calcolabili n>=30: {len(calc)}); netto>0 a 0,40/0,20/0,30: "
          f"{pos['040']}/{pos['020']}/{pos['030']}; t>=3 a 0,20: {int((W.t_020 >= 3).sum())}; "
          f"t>=2 a 0,20: {int((W.t_020 >= 2).sum())}; promosse: {int(W.promossa.sum())}")
    cols = ["n", "lordo", "netto_040", "netto_020", "netto_030", "t_040", "t_020", "t_030",
            "anni_pos", "anni", "p_placebo", "promossa"]
    print(calc.sort_values("t_020", ascending=False)[cols].head(10).round(3).to_string())
    return pos


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    R1, ok1 = esegui_f1()
    B2, ok2 = esegui_f2()
    W1, W2 = larga(R1), larga(B2)
    W1.to_parquet(OUT / "f1f2_f1_confronto.parquet")
    W2.to_parquet(OUT / "f1f2_f2_confronto.parquet")
    print(f"\nriproduzione esatta: F1 {ok1}, F2 {ok2}")
    riassunto("F1 orologio", W1)
    riassunto("F2 momentum", W2[W2.n > 0])
    for nm, W in (("F1", W1), ("F2", W2)):
        c = W[W.promossa].sort_values("t_020", ascending=False).head(3)
        print(f"\ncandidati {nm}: {len(c)}" + ("" if c.empty else "\n" + c.round(3).to_string()))


if __name__ == "__main__":
    main()
