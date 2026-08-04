#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prova dell'ipotesi "estremi-del-giorno" su XAUUSD M1, 2009-2026.

Massimo e minimo della giornata precedente (giornata VERA 18:00->17:00 ET),
della sessione asiatica di oggi e della sessione di New York di ieri, usati
come livelli operativi con tre regole: rottura, falsa rottura, primo tocco.

L'ipotesi pre-registrata (scritta prima di guardare i numeri) sta in
/workspace/dati_grezzi/ipotesi_estremi_giorno.txt.

Regole non negoziabili rispettate qui:
 - causalita': la decisione avviene alla CHIUSURA della candela M1, l'ingresso
   all'apertura della M1 successiva. I livelli usano solo periodi conclusi.
 - costi: 0,30 $ andata e ritorno, in R = 0,30/rischio_in_dollari. Nessuno
   swap perche' si chiude entro le 20:00 UTC.
 - nello stesso minuto lo STOP prevale sull'obiettivo.
 - risultati in R, sempre separati 2009-2019 e 2020-2026.
 - placebo obbligatorio: livello spostato di U(0,2;0,6) ATR, segno casuale.

Uso:  python3 trading/scripts/prova_estremi_giorno.py
Il dettaglio per operazione finisce in /workspace/dati_grezzi/, in chat solo
tabelle compatte.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

REPO = "/workspace/sviluppo-strategie-e-bot"
sys.path.insert(0, os.path.join(REPO, "trading"))

from framework.data import load_m1                      # noqa: E402
from framework.volatility import daily_atr              # noqa: E402

USCITA = "/workspace/dati_grezzi"
SPREAD = 0.30            # $ andata e ritorno
ORA_INIZIO = 7           # primi ingressi (UTC)
ORA_FINE_INGRESSI = 16   # ultimo ingresso (UTC, escluso)
ORA_USCITA = 20          # chiusura forzata (UTC)
BUFFER_ROTTURA = 0.02    # ATR oltre il livello per dire "rotto"
BUFFER_STOP = (0.10, 0.25)   # ATR: distanza dello stop dal livello
OBIETTIVI = (1.5, 2.0)
RISCHIO_MIN = 0.05       # ATR: sotto e' incoerente col costo
RISCHIO_MAX = 0.60       # ATR: sopra non e' piu' un semi-scalp
MIN_BARRE_GIORNO = 300   # sessioni parziali (domenica) escluse


# --------------------------------------------------------------------------
# costruzione dei livelli
# --------------------------------------------------------------------------
def prepara(m1: pd.DataFrame) -> tuple[dict, dict, np.ndarray]:
    """Restituisce (livelli per data, indici finestra per data, array numpy).

    La giornata operativa e' 18:00 ET -> 17:00 ET: assegnando a ogni minuto
    la data di (ora_ET + 6h) si ottiene esattamente quel taglio, e la parte
    diurna (07-20 UTC) ricade sulla data di calendario UTC dello stesso
    giorno, quindi le due chiavi coincidono dove serve.
    """
    idx = m1.index
    et = idx.tz_convert("America/New_York")
    giorno_vero = (et + pd.Timedelta(hours=6)).normalize().tz_localize(None)
    data_utc = idx.normalize().tz_localize(None)
    ora = idx.hour.values

    df = pd.DataFrame({
        "high": m1.high.values, "low": m1.low.values,
        "open": m1.open.values, "close": m1.close.values,
        "gv": giorno_vero, "du": data_utc, "ora": ora,
    })

    # massimo/minimo della giornata vera (solo giornate con abbastanza minuti)
    g = df.groupby("gv")
    est_gv = g.agg(hi=("high", "max"), lo=("low", "min"), n=("high", "size"))
    est_gv = est_gv[est_gv.n >= MIN_BARRE_GIORNO]

    # sessione asiatica di oggi (00-07 UTC) e New York (12-21 UTC), per data UTC
    asia = df[df.ora < 7].groupby("du").agg(hi=("high", "max"),
                                            lo=("low", "min"),
                                            n=("high", "size"))
    asia = asia[asia.n >= 200]
    ny = df[(df.ora >= 12) & (df.ora < 21)].groupby("du").agg(
        hi=("high", "max"), lo=("low", "min"), n=("high", "size"))
    ny = ny[ny.n >= 300]

    # ATR giornaliero causale, indicizzato per data
    atr = daily_atr(m1, 14)
    atr.index = atr.index.tz_localize(None)
    atr = atr.dropna()

    # finestra operativa 07:00-20:00 UTC per data di calendario
    mask = (df.ora >= ORA_INIZIO) & (df.ora < ORA_USCITA)
    pos = np.flatnonzero(mask.values)
    finestre: dict[pd.Timestamp, tuple[int, int]] = {}
    if len(pos):
        d = df.du.values[pos]
        cambi = np.flatnonzero(np.r_[True, d[1:] != d[:-1]])
        bordi = np.r_[cambi, len(pos)]
        for k in range(len(cambi)):
            a, b = bordi[k], bordi[k + 1]
            if b - a >= 200:
                finestre[pd.Timestamp(d[a])] = (int(pos[a]), int(pos[b - 1]))

    # livelli disponibili per ciascuna data operativa
    gv_dates = list(est_gv.index)
    gv_prev = {gv_dates[i]: gv_dates[i - 1] for i in range(1, len(gv_dates))}
    ny_dates = list(ny.index)
    ny_prev = {ny_dates[i]: ny_dates[i - 1] for i in range(1, len(ny_dates))}

    livelli: dict[pd.Timestamp, dict] = {}
    for data in finestre:
        if data not in atr.index:
            continue
        a = float(atr.loc[data])
        if not np.isfinite(a) or a <= 0:
            continue
        voci = {}
        p = gv_prev.get(data)
        if p is not None:
            voci["PD"] = (float(est_gv.hi[p]), float(est_gv.lo[p]))
        if data in asia.index:
            voci["ASIA"] = (float(asia.hi[data]), float(asia.lo[data]))
        pn = ny_prev.get(data)
        if pn is not None:
            voci["PNY"] = (float(ny.hi[pn]), float(ny.lo[pn]))
        if voci:
            livelli[data] = {"atr": a, "voci": voci}

    arr = np.column_stack([df.open.values, df.high.values,
                           df.low.values, df.close.values])
    return livelli, finestre, arr


# --------------------------------------------------------------------------
# percorso: stop / obiettivo / scadenza
# --------------------------------------------------------------------------
def percorri(arr, i0, i_fine, entrata, stop, obiettivo, lungo):
    """Esito di un'operazione: (R_lordo, codice) con 0=obiettivo 1=stop 2=scad.

    Scandisce dalla candela di ingresso alla scadenza. Nella stessa candela lo
    stop vince sempre.
    """
    hi = arr[i0:i_fine + 1, 1]
    lo = arr[i0:i_fine + 1, 2]
    rischio = abs(entrata - stop)
    if lungo:
        cs, ct = lo <= stop, hi >= obiettivo
    else:
        cs, ct = hi >= stop, lo <= obiettivo
    js = int(np.argmax(cs)) if cs.any() else None
    jt = int(np.argmax(ct)) if ct.any() else None
    if js is not None and (jt is None or js <= jt):
        return -1.0, 1
    if jt is not None:
        return abs(obiettivo - entrata) / rischio, 0
    fine = arr[i_fine, 3]
    r = (fine - entrata) / rischio if lungo else (entrata - fine) / rischio
    return float(r), 2


# --------------------------------------------------------------------------
# individuazione dei segnali
# --------------------------------------------------------------------------
def segnali_giorno(arr, i0, i_ult, i_max_ing, livello, atr, alto):
    """Indici di segnale per le tre regole su un livello.

    ``alto=True``: livello resistenza (massimo). Restituisce un dizionario
    regola -> (indice_decisione, dati extra). L'indice e' quello della candela
    la cui CHIUSURA genera il segnale; si entra all'apertura della successiva.
    """
    op, hi, lo, cl = arr[i0:i_ult + 1, 0], arr[i0:i_ult + 1, 1], \
        arr[i0:i_ult + 1, 2], arr[i0:i_ult + 1, 3]
    n_ing = i_max_ing - i0 + 1          # oltre questo indice non si entra piu'
    if n_ing <= 1:
        return {}
    b = BUFFER_ROTTURA * atr
    out = {}

    if alto:
        # deve partire DENTRO (sotto il livello)
        if cl[0] >= livello:
            return {}
        rotto = cl > livello + b
        idx_r = int(np.argmax(rotto)) if rotto.any() else None
        # R1 rottura: prima chiusura oltre
        if idx_r is not None and idx_r < n_ing - 1:
            out["R1"] = (idx_r, None)
        # R2 falsa rottura: dopo la rottura, prima chiusura rientrata
        if idx_r is not None:
            dentro = cl[idx_r + 1:] < livello
            if dentro.any():
                j = idx_r + 1 + int(np.argmax(dentro))
                if j < n_ing - 1:
                    estremo = float(hi[idx_r:j + 1].max())
                    out["R2"] = (j, estremo)
        # R3 primo tocco: high raggiunge il livello ma la chiusura resta sotto
        tocca = (hi >= livello) & (cl < livello)
        if tocca.any():
            j = int(np.argmax(tocca))
            # solo se non c'e' gia' stata una rottura confermata prima
            if (idx_r is None or j <= idx_r) and j < n_ing - 1:
                out["R3"] = (j, None)
    else:
        if cl[0] <= livello:
            return {}
        rotto = cl < livello - b
        idx_r = int(np.argmax(rotto)) if rotto.any() else None
        if idx_r is not None and idx_r < n_ing - 1:
            out["R1"] = (idx_r, None)
        if idx_r is not None:
            dentro = cl[idx_r + 1:] > livello
            if dentro.any():
                j = idx_r + 1 + int(np.argmax(dentro))
                if j < n_ing - 1:
                    estremo = float(lo[idx_r:j + 1].min())
                    out["R2"] = (j, estremo)
        tocca = (lo <= livello) & (cl > livello)
        if tocca.any():
            j = int(np.argmax(tocca))
            if (idx_r is None or j <= idx_r) and j < n_ing - 1:
                out["R3"] = (j, None)
    return out


def esegui(arr, i0, i_ult, seg, livello, atr, alto, buf, rr):
    """Da un segnale alla riga di risultato. None se non eseguibile."""
    regola, (j, extra) = seg
    i_ing = i0 + j + 1                      # apertura della candela dopo
    entrata = float(arr[i_ing, 0])
    if regola == "R1":                      # si segue la rottura
        lungo = alto
        stop = livello - buf * atr if alto else livello + buf * atr
    elif regola == "R2":                    # si contrasta la rottura fallita
        lungo = not alto
        stop = extra + buf * atr if alto else extra - buf * atr
    else:                                   # R3, respinta sul primo tocco
        lungo = not alto
        stop = livello + buf * atr if alto else livello - buf * atr

    rischio = (entrata - stop) if lungo else (stop - entrata)
    if rischio <= 0:
        return None
    if not (RISCHIO_MIN * atr <= rischio <= RISCHIO_MAX * atr):
        return None
    obiettivo = entrata + rr * rischio if lungo else entrata - rr * rischio
    r, codice = percorri(arr, i_ing, i_ult, entrata, stop, obiettivo, lungo)
    return r, codice, rischio


# --------------------------------------------------------------------------
# ciclo principale
# --------------------------------------------------------------------------
def analisi(op: pd.DataFrame):
    """Errori standard, confronto vero/placebo, anni positivi. Solo aggregati."""
    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 200)

    def es(x):
        return x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan

    print("\n### errore standard: e' distinguibile da zero il LORDO?")
    t = op[op.tipo == "vero"].groupby(["regola", "buffer", "periodo"]).agg(
        n=("r_lordo", "size"), lordo=("r_lordo", "mean"),
        es=("r_lordo", es), costo=("costo_r", "mean"),
        netto=("r_netto", "mean"))
    t["t"] = t.lordo / t.es
    print(t.round(3).to_string())

    print("\n### vero meno placebo sul LORDO (il livello fa qualcosa?)")
    g = op.groupby(["regola", "buffer", "periodo", "tipo"]).agg(
        m=("r_lordo", "mean"), e=("r_lordo", es), n=("r_lordo", "size"))
    v, p = g.xs("vero", level="tipo"), g.xs("placebo", level="tipo")
    d = pd.DataFrame({"n_vero": v.n, "n_plac": p.n,
                      "lordo_vero": v.m, "lordo_plac": p.m})
    d["diff"] = d.lordo_vero - d.lordo_plac
    d["es_diff"] = np.sqrt(v.e ** 2 + p.e ** 2)
    d["t"] = d["diff"] / d.es_diff
    print(d.round(3).to_string())

    print("\n### anni con R netto positivo (su 18) — livello vero")
    a = op[op.tipo == "vero"].groupby(
        ["regola", "buffer", "obiettivo", "anno"]).r_netto.mean().unstack()
    pos = (a > 0).sum(axis=1)
    print(pd.DataFrame({"anni_positivi": pos.astype(str) + "/18",
                        "r_netto_medio": a.mean(axis=1).round(3)}).to_string())

    print("\n### la cella meno peggiore per periodo (nessuna e' positiva in due)")
    c = op[op.tipo == "vero"].groupby(
        ["regola", "famiglia", "buffer", "obiettivo", "periodo"]
    ).r_netto.mean().unstack("periodo")
    c["min_due"] = c.min(axis=1)
    print(c.sort_values("min_due", ascending=False).head(6).round(3).to_string())
    print("celle (su %d) positive in ENTRAMBI i periodi: %d"
          % (len(c), int((c.min_due > 0).sum())))


def main():
    cache = os.path.join(USCITA, "estremi_giorno_operazioni.parquet")
    if "--solo-analisi" in sys.argv and os.path.exists(cache):
        analisi(pd.read_parquet(cache))
        return
    print("carico M1 2009-2026 ...", flush=True)
    m1 = load_m1(os.path.join(REPO, "data/XAUUSD_M1"), years=list(range(2009, 2027)))
    print(f"  {len(m1):,} candele  {m1.index[0]} -> {m1.index[-1]}", flush=True)

    livelli, finestre, arr = prepara(m1)
    print(f"  giornate operative utilizzabili: {len(livelli)}", flush=True)
    del m1

    rng = np.random.default_rng(20260804)
    righe = []
    for data, info in livelli.items():
        i0, i_ult = finestre[data]
        atr = info["atr"]
        # ultimo indice ammesso per un INGRESSO (ora < ORA_FINE_INGRESSI)
        n = i_ult - i0 + 1
        i_max_ing = i0 + min(n - 2, (ORA_FINE_INGRESSI - ORA_INIZIO) * 60 - 1)
        anno = data.year
        for fam, (hi_lv, lo_lv) in info["voci"].items():
            for alto, base in ((True, hi_lv), (False, lo_lv)):
                # livello vero e livello finto (placebo)
                scarto = rng.uniform(0.2, 0.6) * atr * rng.choice([-1.0, 1.0])
                for tipo, lv in (("vero", base), ("placebo", base + scarto)):
                    segs = segnali_giorno(arr, i0, i_ult, i_max_ing, lv, atr, alto)
                    for regola, dati in segs.items():
                        for buf in BUFFER_STOP:
                            for rr in OBIETTIVI:
                                res = esegui(arr, i0, i_ult, (regola, dati),
                                             lv, atr, alto, buf, rr)
                                if res is None:
                                    continue
                                r, codice, rischio = res
                                righe.append((
                                    data, anno, fam, regola,
                                    "alto" if alto else "basso",
                                    tipo, buf, rr, r, codice,
                                    SPREAD / rischio, rischio, atr))
    op = pd.DataFrame(righe, columns=[
        "data", "anno", "famiglia", "regola", "lato", "tipo", "buffer",
        "obiettivo", "r_lordo", "esito", "costo_r", "rischio_usd", "atr"])
    op["r_netto"] = op.r_lordo - op.costo_r
    op["periodo"] = np.where(op.anno <= 2019, "2009-2019", "2020-2026")

    os.makedirs(USCITA, exist_ok=True)
    dest = os.path.join(USCITA, "estremi_giorno_operazioni.parquet")
    op.to_parquet(dest, index=False)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 200)

    def riassunto(g):
        return pd.Series({
            "n": len(g),
            "r_lordo": g.r_lordo.mean(),
            "r_netto": g.r_netto.mean(),
            "p_obj": (g.esito == 0).mean(),
            "p_stop": (g.esito == 1).mean(),
            "p_scad": (g.esito == 2).mean(),
            "costo": g.costo_r.mean(),
        })

    print("\n=== dettaglio salvato in", dest, f"({len(op):,} operazioni) ===")

    # --- tabella principale: livello vero, per regola x famiglia x periodo ---
    for rr in OBIETTIVI:
        for buf in BUFFER_STOP:
            sel = op[(op.tipo == "vero") & (op.obiettivo == rr) &
                     (op.buffer == buf)]
            if sel.empty:
                continue
            t = sel.groupby(["regola", "famiglia", "periodo"]).apply(
                riassunto, include_groups=False)
            pl = op[(op.tipo == "placebo") & (op.obiettivo == rr) &
                    (op.buffer == buf)].groupby(
                ["regola", "famiglia", "periodo"]).r_netto.mean()
            t["placebo"] = pl
            t["vero-plac"] = t.r_netto - t.placebo
            print(f"\n### obiettivo 1:{rr}  stop {buf} ATR  (livello VERO)")
            print(t.round(3).to_string())

    # --- controllo di assurdita': obiettivo lontano vs stop vicino ---
    print("\n### controllo di assurdita' (p_obj deve calare con l'obiettivo)")
    c = op[op.tipo == "vero"].groupby(["regola", "obiettivo", "periodo"]).apply(
        lambda g: pd.Series({"n": len(g), "p_obj": (g.esito == 0).mean(),
                             "p_stop": (g.esito == 1).mean(),
                             "p_scad": (g.esito == 2).mean()}),
        include_groups=False)
    print(c.round(3).to_string())

    # --- per anno, configurazione principale ---
    print("\n### R netto per anno (PD, stop 0.10 ATR, obiettivo 1:1.5)")
    a = op[(op.tipo == "vero") & (op.famiglia == "PD") & (op.buffer == 0.10) &
           (op.obiettivo == 1.5)].groupby(["anno", "regola"]).r_netto.mean()
    print(a.unstack().round(3).to_string())

    # --- sintesi finale su tutte le famiglie unite ---
    print("\n### sintesi: tutte le famiglie unite, vero vs placebo")
    s = op.groupby(["regola", "buffer", "obiettivo", "periodo", "tipo"]).agg(
        n=("r_netto", "size"), r_netto=("r_netto", "mean")).reset_index()
    s = s.pivot_table(index=["regola", "buffer", "obiettivo"],
                      columns=["periodo", "tipo"],
                      values="r_netto").round(3)
    print(s.to_string())

    analisi(op)


if __name__ == "__main__":
    main()
