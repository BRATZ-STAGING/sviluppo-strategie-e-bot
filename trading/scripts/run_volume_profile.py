#!/usr/bin/env python3
"""Session volume profile: l'ingresso in un buco di liquidita' cambia l'esito?

STUDIO PRE-REGISTRATO, ESPLORATIVO. Nessuna direzione dichiarata: non sappiamo
se entrare in un LVN (poco volume scambiato a quel prezzo) aiuti o danneggi.
Test a DUE code con permutazione (10000), soglia 5%.

AVVERTENZA: il volume delle candele M1 e' TICK volume (numero di variazioni di
prezzo nel minuto), non volume scambiato. Sullo spot e' l'approssimazione
standard, ma va tenuto presente nel leggere i risultati.

Metodo
- operazioni dalla taratura UFFICIALE, esito con valuta(o, T.obiettivo,
  be=T.pareggio);
- profilo CAUSALE della giornata: candele M1 dalla mezzanotte UTC fino
  all'istante d'ingresso ESCLUSO; bin di prezzo da 0,50 $; volume del bin =
  somma del tick volume delle candele il cui prezzo medio (h+l)/2 cade nel bin;
  servono almeno 120 candele prima dell'ingresso, altrimenti si scarta;
- classe dell'ingresso: volume del bin dell'entry contro i terzili dei bin
  coperti -> LVN (terzile basso) / HVN (terzile alto) / medio;
- R/op per classe su "tutte" e su "regola completa" (M33+H12 allineati, M12
  contrario); delta LVN-HVN sul campione "tutte" con p di permutazione.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/workspace/sviluppo-strategie-e-bot/trading")
from framework.data import load_m1                              # noqa: E402
from framework.gestione import valuta                           # noqa: E402
from framework.segnali import genera                            # noqa: E402
from framework.taratura import UFFICIALE as T                   # noqa: E402

pd.set_option("display.width", 200)

BIN = 0.50           # ampiezza del bin di prezzo, in dollari
MIN_CANDELE = 120    # candele minime prima dell'ingresso
N_PERM = 10000
SEED = 20260801
SCRATCH = ("/tmp/claude-0/-home-user-staging-bratz/"
           "12ee8316-94ec-5738-a776-0652fa6537d9/scratchpad")


def classifica(m1_idx, mid, vol, o):
    """Classe dell'ingresso rispetto al profilo volumetrico causale.

    Ritorna (classe, percentile del volume del bin d'entry) o None se prima
    dell'ingresso ci sono meno di MIN_CANDELE candele.
    """
    g = o["time"].normalize()
    a = int(m1_idx.searchsorted(g))
    b = int(m1_idx.searchsorted(o["time"]))    # label < time: chiuse all'entry
    if b - a < MIN_CANDELE:
        return None
    bins = np.floor(mid[a:b] / BIN).astype(np.int64)
    b0 = int(bins.min())
    volumi = np.bincount(bins - b0, weights=vol[a:b])
    coperti = volumi[volumi > 0] if (volumi > 0).any() else volumi
    q33, q67 = np.quantile(coperti, [1 / 3, 2 / 3])
    k = int(np.floor(o["entry"] / BIN)) - b0
    v = float(volumi[k]) if 0 <= k < len(volumi) else 0.0
    if v <= q33:
        classe = "LVN"
    elif v >= q67:
        classe = "HVN"
    else:
        classe = "medio"
    perc = float(((coperti < v).sum() + 0.5 * (coperti == v).sum()) / len(coperti))
    return classe, perc


def main():
    m1 = load_m1("/workspace/sviluppo-strategie-e-bot/data/XAUUSD_M1")
    m1_idx = m1.index
    mid = ((m1.high.values + m1.low.values) / 2).astype(np.float64)
    vol = m1.volume.values.astype(np.float64)

    ops = genera(m1, T)
    righe, scartate = [], 0
    for o in ops:
        esito = classifica(m1_idx, mid, vol, o)
        if esito is None:
            scartate += 1
            continue
        classe, perc = esito
        r, _ = valuta(o, T.obiettivo, be=T.pareggio)
        righe.append({"time": o["time"], "anno": o["anno"], "lato": o["lato"],
                      "classe": classe, "perc_volume_bin": perc, "r": r,
                      "regola": bool(o["c_M33"] and o["c_H12"] and not o["c_M12"])})
    d = pd.DataFrame(righe)
    d[["time", "classe", "perc_volume_bin"]].to_parquet(f"{SCRATCH}/vp_flags.parquet")

    print("AVVERTENZA: volume M1 = TICK volume (variazioni di prezzo), non "
          "volume scambiato.\n")
    print(f"operazioni generate {len(ops)}, scartate (<{MIN_CANDELE} candele) "
          f"{scartate}, classificate {len(d)} "
          f"(regola completa: {int(d.regola.sum())})\n")

    out = []
    for nome, sub in (("tutte", d), ("regola completa", d[d.regola])):
        g = sub.groupby("classe").r.agg(n="size", r_op="mean")
        for classe in ("LVN", "medio", "HVN"):
            if classe in g.index:
                out.append({"campione": nome, "classe": classe,
                            "n": int(g.loc[classe, "n"]),
                            "r_op": float(g.loc[classe, "r_op"])})
    tab = pd.DataFrame(out)
    print(tab.to_string(index=False, float_format=lambda x: f"{x:+.3f}"))

    # delta LVN-HVN sul campione "tutte", permutazione a due code
    lvn = d[d.classe == "LVN"].r.values
    hvn = d[d.classe == "HVN"].r.values
    delta = float(lvn.mean() - hvn.mean())
    pool = np.concatenate([lvn, hvn])
    rng = np.random.default_rng(SEED)
    conta = 0
    for _ in range(N_PERM):
        perm = rng.permutation(pool)
        if abs(perm[:len(lvn)].mean() - perm[len(lvn):].mean()) >= abs(delta):
            conta += 1
    p = conta / N_PERM
    print(f"\ndelta LVN-HVN (tutte): {delta:+.3f} R/op   "
          f"p permutazione (2 code, {N_PERM}): {p:.4f}")
    print("→ " + ("oltre il rumore (p<5%)" if p < 0.05 else
                  "NON distinguibile dal rumore (p>=5%)"))
    return tab, len(d), delta, p


if __name__ == "__main__":
    main()
