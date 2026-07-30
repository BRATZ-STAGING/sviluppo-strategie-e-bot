#!/usr/bin/env python3
"""I ritracciamenti di Fibonacci reagiscono, o sono rumore?

Domanda deliberatamente PIU' PICCOLA di "lo scalping su fibo funziona":
si misura la qualita' della reazione al livello, senza stop, senza obiettivo,
senza costi. Se i livelli veri non battono livelli finti alla stessa distanza,
qualunque strategia costruita sopra e' morta prima di pagare lo spread.

DISEGNO
- gli swing sono confermati k barre dopo l'estremo (causale)
- una gamba e' nota solo quando il secondo estremo e' confermato: da quel
  momento i suoi ritracciamenti sono utilizzabili
- un tocco e' la prima candela M1 che attraversa il livello dopo l'attivazione
- reazione = massima escursione favorevole (verso la direzione della gamba) nei
  minuti successivi, in dollari e in ATR
- PLACEBO: per ogni gamba, livelli finti a percentuali NON di Fibonacci
  (23, 34, 44, 56, 67, 84) misurati identicamente

IPOTESI PRE-REGISTRATA: se Fibonacci ha un contenuto, i livelli 50 / 61,8 /
70,5 / 78,6 devono reagire MEGLIO dei finti. Se la differenza e' nel rumore,
l'idea si scarta e non si costruisce niente sopra.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/workspace/sviluppo-strategie-e-bot/trading")
from framework.data import TIMEFRAMES, load_m1, resample_tf     # noqa: E402
from framework.volatility import atr_at, daily_atr              # noqa: E402

pd.set_option("display.width", 220)

FIB = [38.2, 50.0, 61.8, 70.5, 78.6]
FINTI = [23.0, 34.0, 44.0, 56.0, 67.0, 84.0]
FINESTRA = 60          # minuti di osservazione dopo il tocco
K = 3                  # barre di conferma dello swing
GAMBA_MIN_ATR = 0.5    # la gamba deve valere almeno mezzo ATR giornaliero


def swing_confermati(df, k=K):
    """(indice, prezzo, tipo, indice_di_conferma) degli swing frattali."""
    hi, lo = df.high.values, df.low.values
    n = len(df)
    out = []
    for j in range(k, n - k):
        if (hi[j - k:j] < hi[j]).all() and (hi[j + 1:j + k + 1] < hi[j]).all():
            out.append((j, float(hi[j]), 1, j + k))
        if (lo[j - k:j] > lo[j]).all() and (lo[j + 1:j + k + 1] > lo[j]).all():
            out.append((j, float(lo[j]), -1, j + k))
    out.sort(key=lambda x: x[0])
    return out


def gambe(df, atr_bar, k=K):
    """Gambe fra swing consecutivi opposti, con l'istante da cui sono note."""
    sw = swing_confermati(df, k)
    idx = df.index
    freq = idx[1] - idx[0] if len(idx) > 1 else pd.Timedelta("1min")
    fuori = []
    for a, b in zip(sw, sw[1:]):
        if a[2] == b[2]:
            continue                      # servono estremi opposti
        i0, p0, t0, _ = a
        i1, p1, t1, conf1 = b
        ampiezza = abs(p1 - p0)
        rif = atr_bar[i1]
        if not np.isfinite(rif) or rif <= 0 or ampiezza < GAMBA_MIN_ATR * rif:
            continue
        # direzione della gamba: +1 se sale (da minimo a massimo)
        direzione = 1 if t1 == 1 else -1
        fuori.append({"nota_da": idx[min(conf1, len(idx) - 1)] + freq,
                      "da": p0, "a": p1, "direzione": direzione,
                      "ampiezza": ampiezza, "atr": float(rif)})
    return pd.DataFrame(fuori)


def livello(g, perc):
    """Prezzo del ritracciamento al ``perc``% della gamba."""
    return g["a"] - g["direzione"] * g["ampiezza"] * perc / 100.0


def misura(m1_idx, hi, lo, g, prezzo, da_quando, finestra=FINESTRA):
    """Primo tocco del livello dopo l'attivazione, e reazione successiva.

    Ritorna (reazione favorevole in dollari, penetrazione contraria) o None.
    """
    a = int(m1_idx.searchsorted(da_quando))
    b = min(a + 24 * 60 * 3, len(m1_idx))       # cerca il tocco entro 3 giorni
    if b - a < 2:
        return None
    tocca = (lo[a:b] <= prezzo) & (hi[a:b] >= prezzo)
    if not tocca.any():
        return None
    t = a + int(np.argmax(tocca))
    f0, f1 = t, min(t + finestra, len(m1_idx))
    if f1 - f0 < 2:
        return None
    if g["direzione"] == 1:                     # gamba al rialzo: ci si aspetta
        rea = float(hi[f0:f1].max() - prezzo)   # un rimbalzo verso l'alto
        pen = float(prezzo - lo[f0:f1].min())
    else:
        rea = float(prezzo - lo[f0:f1].min())
        pen = float(hi[f0:f1].max() - prezzo)
    return rea, pen


def main():
    tf = sys.argv[1] if len(sys.argv) > 1 else "M12"
    m1 = load_m1("/workspace/sviluppo-strategie-e-bot/data/XAUUSD_M1")
    s = resample_tf(m1, tf)
    atr = daily_atr(m1, 14)
    atr_bar = atr_at(atr, s.index).values
    G = gambe(s, atr_bar)
    print(f"timeframe {tf}: {len(s):,} candele, {len(G)} gambe utilizzabili\n", flush=True)

    m1_idx = m1.index
    hi, lo = m1.high.values, m1.low.values
    righe = []
    for _, g in G.iterrows():
        for tipo, perc_list in (("fibo", FIB), ("finto", FINTI)):
            for perc in perc_list:
                p = livello(g, perc)
                m = misura(m1_idx, hi, lo, g, p, g["nota_da"])
                if m is None:
                    continue
                rea, pen = m
                righe.append({"tipo": tipo, "perc": perc, "atr": g["atr"],
                              "reazione": rea, "penetrazione": pen,
                              "rea_atr": rea / g["atr"], "pen_atr": pen / g["atr"],
                              "netta_atr": (rea - pen) / g["atr"]})
    d = pd.DataFrame(righe)
    d.to_parquet("/tmp/claude-0/-home-user-staging-bratz/"
                 "12ee8316-94ec-5738-a776-0652fa6537d9/scratchpad/fib.parquet")

    print("=== REAZIONE PER LIVELLO (finestra 60 minuti dopo il tocco) ===")
    g = d.groupby(["tipo", "perc"]).agg(
        tocchi=("reazione", "size"),
        reazione_ATR=("rea_atr", "median"),
        penetrazione_ATR=("pen_atr", "median"),
        netta_ATR=("netta_atr", "median"),
        rea_su_pen=("reazione", lambda s: np.nan))
    g["rea_su_pen"] = (d.groupby(["tipo", "perc"]).rea_atr.median()
                       / d.groupby(["tipo", "perc"]).pen_atr.median())
    print(g.to_string(float_format=lambda x: f"{x:.3f}"))

    print("\n=== FIBONACCI CONTRO PLACEBO ===")
    c = d.groupby("tipo").agg(tocchi=("reazione", "size"),
                              reazione_ATR=("rea_atr", "median"),
                              penetrazione_ATR=("pen_atr", "median"),
                              netta_ATR=("netta_atr", "median"))
    c["rea_su_pen"] = c.reazione_ATR / c.penetrazione_ATR
    print(c.to_string(float_format=lambda x: f"{x:.4f}"))
    f, n = d[d.tipo == "fibo"], d[d.tipo == "finto"]
    diff = f.netta_atr.median() - n.netta_atr.median()
    # significativita' per permutazione: mescolo le etichette
    rng = np.random.default_rng(12345)
    tutti = d.netta_atr.values
    nf = len(f)
    conta = 0
    for _ in range(2000):
        perm = rng.permutation(tutti)
        if (np.median(perm[:nf]) - np.median(perm[nf:])) >= diff:
            conta += 1
    print(f"\ndifferenza mediana (fibo - finto), in ATR: {diff:+.4f}")
    print(f"probabilita' di ottenerla mescolando le etichette: {conta/2000*100:.1f}%")
    if conta / 2000 > 0.05:
        print("→ NON distinguibile dal rumore: Fibonacci non aggiunge nulla qui")
    else:
        print("→ differenza oltre il rumore")


if __name__ == "__main__":
    main()
