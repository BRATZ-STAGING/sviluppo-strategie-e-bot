#!/usr/bin/env python3
"""Appendice AI: order block + profilo volume + Fibonacci, cercati insieme.

Calcola per ogni operazione del campione largo tre famiglie di caratteristiche
(tutte causali al minuto d'ingresso) e poi percorre una griglia di 450
combinazioni CERCANDO SOLO SU 2020-2023. La cella scelta viene poi misurata
una volta sola su 2024-2026, mai guardato durante la ricerca.

Caratteristiche:
  ob / obr      dentro una zona order block M33 (piena / raffinata), a due
                margini (0,5 e 1,0 volte il rischio)
  vp            terzile del profilo volume causale della giornata nel punto
                d'ingresso (basso = buco di liquidita', alto = eccesso)
  fib           distanza dell'ingresso dai ritracciamenti della gamba M33
                (50 / 61,8 / 70,5 / 78,6 per cento), in unita' di rischio
  ext127/ext161 obiettivo alternativo: estensione di Fibonacci della gamba,
                espressa in multipli del rischio

Uso: python3 run_combinata.py
Scrive docs/studies/dati/combinata.parquet (caratteristiche per operazione).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf     # noqa: E402
from framework.gestione import chiusura_fine_giornata, esito_indice  # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

from export_lab import in_zona, zone_ob                          # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
K = 3
RITR = {"50": 0.500, "61.8": 0.618, "70.5": 0.705, "78.6": 0.786}
BIN = 0.5                 # larghezza dei livelli del profilo volume, in $
RICERCA = (2020, 2023)    # gli unici anni che la ricerca puo' vedere


def gambe_m33(tfd):
    """Per ogni candela: (inizio, fine) dell'ultima gamba nota, causale.

    Una gamba e' il tratto fra gli ultimi due swing confermati opposti; il
    verso dice se e' salita (fine > inizio) o discesa.
    """
    h, l = tfd.high.values, tfd.low.values
    n = len(tfd)
    out = np.full((n, 2), np.nan)
    ultimo_h = ultimo_l = None
    th = tl = -1
    for i in range(n):
        j = i - K
        if j >= K:
            if (h[j-K:j] < h[j]).all() and (h[j+1:j+K+1] < h[j]).all():
                ultimo_h, th = float(h[j]), j
            if (l[j-K:j] > l[j]).all() and (l[j+1:j+K+1] > l[j]).all():
                ultimo_l, tl = float(l[j]), j
        if ultimo_h is not None and ultimo_l is not None:
            out[i] = (ultimo_l, ultimo_h) if tl < th else (ultimo_h, ultimo_l)
    return out


def profilo_terzili(m1):
    """Per ogni minuto: terzile del volume scambiato al prezzo corrente,
    calcolato sul profilo della giornata FINO a quel minuto (causale)."""
    prezzo = ((m1.high + m1.low + m1.close) / 3).values
    vol = np.where(np.isfinite(m1.volume.values) & (m1.volume.values > 0),
                   m1.volume.values, 1.0)
    giorno = m1.index.normalize().asi8
    livello = np.round(prezzo / BIN).astype(np.int64)
    out = np.full(len(m1), -1, dtype=np.int8)
    conta = {}
    corrente = giorno[0]
    for i in range(len(m1)):
        if giorno[i] != corrente:
            conta = {}
            corrente = giorno[i]
        if conta:
            v = np.fromiter(conta.values(), float)
            mio = conta.get(livello[i], 0.0)
            q = (v <= mio).mean()
            out[i] = 0 if q <= 1/3 else (1 if q <= 2/3 else 2)
        conta[livello[i]] = conta.get(livello[i], 0.0) + vol[i]
    return out


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = genera(m1, T)
    print(f"campione largo: {len(ops)} operazioni", flush=True)

    m33 = resample_tf(m1, "M33")
    zone = zone_ob(m33, K, TIMEFRAMES["M33"])
    gambe = gambe_m33(m33)
    passo = pd.Timedelta(TIMEFRAMES["M33"])
    fine_barra = pd.DatetimeIndex(m33.index + passo).as_unit("ns").asi8
    terzili = profilo_terzili(m1)
    idx_m1 = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    print("caratteristiche pronte", flush=True)

    righe = []
    for op_id, op in enumerate(ops):
        t_in = pd.Timestamp(op["time"]).tz_convert("UTC")
        ns = t_in.value
        lato = 1 if op["lato"] == "long" else -1
        e, k = op["entry"], op["rischio"]
        r = {"op_id": op_id, "anno": op["anno"], "k": k}
        for nome, marg, raff in (("ob05", 0.5, False), ("ob10", 1.0, False),
                                 ("obr05", 0.5, True), ("obr10", 1.0, True)):
            r[nome] = int(in_zona(zone, t_in, e, lato, marg * k, raffinata=raff))
        r["vp"] = int(terzili[min(int(np.searchsorted(idx_m1, ns)),
                                  len(terzili) - 1)])
        # gamba nota: ultima barra M33 CHIUSA prima dell'ingresso
        b = int(np.searchsorted(fine_barra, ns)) - 1
        ini, fin = (gambe[b] if 0 <= b < len(gambe) else (np.nan, np.nan))
        for nome, q in RITR.items():
            r[f"fib{nome}"] = np.nan
            if np.isfinite(ini) and fin != ini:
                liv = fin - q * (fin - ini)
                r[f"fib{nome}"] = abs(e - liv) / k
        for nome, q in (("ext127", 1.272), ("ext161", 1.618)):
            r[nome] = np.nan
            if np.isfinite(ini) and fin != ini:
                bersaglio = ini + q * (fin - ini)
                rr = (bersaglio - e) / k * lato
                r[nome] = rr if rr > 0.5 else np.nan
        # esiti precalcolati per i tre obiettivi e i due pareggi
        for be_nome, be in (("no", None), ("be3", 3.0)):
            for nome, rr in (("rr10", 10.0),):
                x, mo, _ = esito_indice(op["fav"], op["sfav"], rr, be=be, costo=0.0)
                if x is None:
                    x = chiusura_fine_giornata(op["r_eod"], be, False, op["mfe"], 0.0)
                    mo = 2
                r[f"r_{nome}_{be_nome}"] = x - op["costo"]
                r[f"m_{nome}_{be_nome}"] = mo
            for nome in ("ext127", "ext161"):
                rr = r[nome]
                if not np.isfinite(rr):
                    r[f"r_{nome}_{be_nome}"] = np.nan
                    r[f"m_{nome}_{be_nome}"] = -1
                    continue
                be_ok = be if (be is None or be < rr) else None
                x, mo, _ = esito_indice(op["fav"], op["sfav"], rr, be=be_ok, costo=0.0)
                if x is None:
                    x = chiusura_fine_giornata(op["r_eod"], be_ok, False,
                                               op["mfe"], 0.0)
                    mo = 2
                r[f"r_{nome}_{be_nome}"] = x - op["costo"]
                r[f"m_{nome}_{be_nome}"] = mo
        righe.append(r)

    df = pd.DataFrame(righe)
    dest = os.path.join(ROOT, "docs", "studies", "dati", "combinata.parquet")
    df.to_parquet(dest, index=False)
    print(f"caratteristiche salvate: {dest}", flush=True)

    # ---- griglia: si cerca SOLO su 2020-2023 -----------------------------
    ric = df[(df.anno >= RICERCA[0]) & (df.anno <= RICERCA[1])]
    ver = df[df.anno > RICERCA[1]]
    celle = []
    for ob in ("nessuno", "ob05", "ob10", "obr05", "obr10"):
        for vp in (-1, 0, 1, 2):
            for fib in ["nessuno"] + list(RITR):
                for obiettivo in ("rr10", "ext127", "ext161"):
                    for be in ("no", "be3"):
                        celle.append((ob, vp, fib, obiettivo, be))

    def seleziona(d, ob, vp, fib):
        m = np.ones(len(d), bool)
        if ob != "nessuno":
            m &= d[ob].values == 1
        if vp >= 0:
            m &= d["vp"].values == vp
        if fib != "nessuno":
            m &= d[f"fib{fib}"].values <= 0.5
        return m

    ris = []
    for ob, vp, fib, obiettivo, be in celle:
        m = seleziona(ric, ob, vp, fib)
        r = ric[f"r_{obiettivo}_{be}"].values[m]
        r = r[np.isfinite(r)]
        if len(r) < 60:
            continue
        ris.append({"ob": ob, "vp": vp, "fib": fib, "obiettivo": obiettivo,
                    "be": be, "n_ric": len(r), "rop_ric": r.mean(),
                    "tot_ric": r.sum()})
    tab = pd.DataFrame(ris).sort_values("rop_ric", ascending=False)
    base_ric = ric["r_rr10_be3"].values
    print(f"\ncelle valutabili: {len(tab)} su {len(celle)}")
    print(f"riferimento in ricerca (tutte, 1:10, +3R): {base_ric.mean():+.3f} R/op "
          f"su {len(base_ric)} operazioni")
    print(f"celle che lo battono IN RICERCA: {(tab.rop_ric > base_ric.mean()).sum()}")

    # fuori campione, per le prime 10
    print(f"\n{'#':>2s} {'ob':>6s} {'vp':>3s} {'fib':>7s} {'obiettivo':>9s} {'be':>4s} "
          f"{'n ric':>6s} {'R/op ric':>9s} | {'n ver':>6s} {'R/op ver':>9s} {'tot ver':>8s}")
    base_ver = ver["r_rr10_be3"].values
    for pos, (_, c) in enumerate(tab.head(10).iterrows(), 1):
        m = seleziona(ver, c.ob, c.vp, c.fib)
        r = ver[f"r_{c.obiettivo}_{c.be}"].values[m]
        r = r[np.isfinite(r)]
        print(f"{pos:2d} {c.ob:>6s} {c.vp:3d} {c.fib:>7s} {c.obiettivo:>9s} {c.be:>4s} "
              f"{c.n_ric:6d} {c.rop_ric:+9.3f} | {len(r):6d} "
              f"{(r.mean() if len(r) else float('nan')):+9.3f} "
              f"{(r.sum() if len(r) else float('nan')):+8.1f}")
    print(f"\nriferimento FUORI campione (tutte, 1:10, +3R): {base_ver.mean():+.3f} R/op "
          f"su {len(base_ver)} operazioni")


if __name__ == "__main__":
    main()
