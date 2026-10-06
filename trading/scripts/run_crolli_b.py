#!/usr/bin/env python3
"""Perche' la B crolla: esecuzione alla lettera di docs/crolli-b-registrazione.md.

Dati: le 712 operazioni B di docs/studies/dati/b_operazioni_2009_2026.parquet
(NON rigenerate). Le misure di mercato vengono dall'archivio M1 intero,
caricato una volta sola, e sono note all'ingresso: D1 fino a IERI (giornata
vera di ``framework.volatility.daily_bars``, senza lo spezzone della domenica),
piu' il prezzo d'ingresso, il rischio in $ e lo spread dell'anno.

  Domanda 1  come perde: motivi d'uscita, R medio di vinte e perse,
             scomposizione della differenza di R/op fra le epoche
  Domanda 2  quando perde: nove fattori all'ingresso, terzi sulle 712,
             fascia peggiore per epoca, placebo per giornata (2.000, seme
             20261006), soglia 0,05/9 = 0,0056
  Domanda 3  le tre discese del 2020-2026: in che fasce cadono
  Controllo di causalita': ogni fattore ricalcolato da un M1 TRONCATO
             all'istante d'ingresso deve coincidere con quello dell'archivio
             intero.

Uso: python trading/scripts/run_crolli_b.py
Dettaglio per operazione: docs/studies/dati/crolli_b.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(QUI, ".."))
sys.path.insert(0, QUI)

from framework.data import load_m1                      # noqa: E402
from framework.volatility import daily_atr, daily_bars  # noqa: E402
from verifica_bot import SPREAD                         # noqa: E402

ROOT = os.path.abspath(os.path.join(QUI, "..", ".."))
INGRESSO = os.path.join(ROOT, "docs", "studies", "dati", "b_operazioni_2009_2026.parquet")
USCITA = os.path.join(ROOT, "docs", "studies", "dati", "crolli_b.parquet")

SEME = 20261006
N_PLACEBO = 2000
ALFA = 0.05 / 9
SPREAD_PRIMA_2020 = 0.40
# date di docs/crolli-b-registrazione.md (inizio = massimo, fine = recupero)
DISCESE = {"2024": ("2024-07-16", "2024-10-22"),
           "2025": ("2025-04-11", "2025-09-03"),
           "2026": ("2026-01-28", "2026-06-24")}
MOTIVI = ["stop", "protetto", "obiettivo", "gap", "chiusa il venerdi'", "scadenza"]
# nome -> (etichetta, continuo?) nell'ordine della registrazione
FATTORI = {
    "volatilita": ("1 volatilita' ATR14/prezzo", True),
    "tendenza": ("2 tendenza pendenza MA200", True),
    "distanza_ma50": ("3 distanza da MA50 (segno lato)", True),
    "lato": ("4 lato", False),
    "ora": ("5 ora UTC", False),
    "giorno_sett": ("6 giorno settimana", False),
    "ampiezza_stop": ("7 ampiezza stop rischio/ATR14", True),
    "peso_costo": ("8 peso costo spread/rischio", True),
    "nfp": ("9 venerdi' buste paga", False),
}
TERZI = ["basso", "medio", "alto"]
GIORNI = ["lun", "mar", "mer", "gio", "ven"]

pd.set_option("display.width", 200)


# ----------------------------------------------------------------------------
# D1 e fattori
# ----------------------------------------------------------------------------
def indicatori_d1(m1: pd.DataFrame) -> pd.DataFrame:
    """Giornate vere (daily_bars) con ATR14, MA50, MA200 e MA200 di 20 giornate prima.

    Il valore sulla riga del giorno D usa le giornate fino a D INCLUSA: va letto
    sulla riga di IERI rispetto all'ingresso (vedi ``riga_di_ieri``).
    """
    d1 = daily_bars(m1)
    prev = d1["close"].shift(1)
    tr = pd.concat([d1["high"] - d1["low"], (d1["high"] - prev).abs(),
                    (d1["low"] - prev).abs()], axis=1).max(axis=1)
    out = pd.DataFrame(index=d1.index)
    out["close"] = d1["close"]
    out["atr14"] = tr.rolling(14).mean()
    out["ma50"] = d1["close"].rolling(50).mean()
    out["ma200"] = d1["close"].rolling(200).mean()
    out["ma200_20"] = out["ma200"].shift(20)
    return out


def riga_di_ieri(d1: pd.DataFrame, istanti: pd.Series) -> pd.DataFrame:
    """Per ogni istante d'ingresso, l'ultima giornata vera STRETTAMENTE precedente al giorno d'ingresso."""
    giorno = pd.DatetimeIndex(istanti).normalize()
    pos = d1.index.searchsorted(giorno, side="left") - 1
    if (pos < 0).any():
        raise ValueError("operazione senza giornata precedente nell'archivio")
    r = pd.DataFrame({"ieri": d1.index[pos], **{c: d1[c].to_numpy()[pos] for c in d1.columns}},
                     index=istanti.index)
    assert (pd.DatetimeIndex(r["ieri"]) < giorno).all(), "lookahead: giornata D1 non precedente all'ingresso"
    return r


def fattori(ops: pd.DataFrame, d1: pd.DataFrame) -> pd.DataFrame:
    """I nove fattori della registrazione, calcolati all'ingresso."""
    f = ops.copy()
    ieri = riga_di_ieri(d1, f["time"])
    for c in ("ieri", "atr14", "ma50", "ma200", "ma200_20"):
        f[c + "_ieri" if c != "ieri" else c] = ieri[c]      # stesso indice: conserva l'UTC
    t = pd.DatetimeIndex(f["time"])
    segno = np.where(f["lato"] == "long", 1.0, -1.0)
    f["volatilita"] = f["atr14_ieri"] / f["entry"]
    f["tendenza"] = (f["ma200_ieri"] - f["ma200_20_ieri"]) / f["atr14_ieri"]
    f["distanza_ma50"] = (f["entry"] - f["ma50_ieri"]) / f["atr14_ieri"] * segno
    f["ora"] = t.hour
    f["giorno_sett"] = t.dayofweek
    f["ampiezza_stop"] = f["rischio"] / f["atr14_ieri"]
    f["spread"] = f["anno"].map(lambda a: SPREAD.get(int(a), SPREAD_PRIMA_2020))
    f["peso_costo"] = f["spread"] / f["rischio"]
    f["nfp"] = (t.dayofweek == 4) & (t.day <= 7)
    return f


def fasce(f: pd.DataFrame) -> pd.DataFrame:
    """Fasce: terzi sulle 712 operazioni insieme (continui), categorie (discreti)."""
    for nome, (_, continuo) in FATTORI.items():
        if continuo:
            f["f_" + nome] = pd.qcut(f[nome], 3, labels=TERZI).astype(object)
    f["f_lato"] = f["lato"]
    ora = f["ora"]
    f["f_ora"] = np.select([ora.between(7, 11), ora.between(12, 16), ora.between(17, 19)],
                           ["07-11", "12-16", "17-19"], default=None)
    assert f["f_ora"].notna().all(), "ingresso fuori dalle fasce orarie 07-19"
    f["f_giorno_sett"] = f["giorno_sett"].map(dict(enumerate(GIORNI)))
    assert f["f_giorno_sett"].notna().all(), "ingresso nel fine settimana"
    f["f_nfp"] = np.where(f["nfp"], "primo ven", "altro")
    return f


# ----------------------------------------------------------------------------
# Epoche e discese
# ----------------------------------------------------------------------------
def segna_discese(f: pd.DataFrame) -> pd.Series:
    """Le operazioni delle tre discese: quelle con il cumulato STRETTAMENTE sotto il
    massimo precedente (stessa definizione di ``drawdown`` in analisi_b_18anni.py),
    identificate per data d'inizio (massimo) e di recupero della registrazione."""
    s = f.sort_values("time")
    cum = s["R"].cumsum()
    picco = cum.cummax().clip(lower=0)
    sotto = (cum < picco - 1e-9).values
    t = pd.DatetimeIndex(s["time"])
    etichetta = pd.Series(index=s.index, dtype=object)
    i = 0
    while i < len(s):
        if not sotto[i]:
            i += 1
            continue
        j = i
        while j < len(s) and sotto[j]:
            j += 1
        inizio = t[i - 1].date() if i else t[i].date()
        recupero = t[j].date() if j < len(s) else None
        for nome, (a, z) in DISCESE.items():
            if str(inizio) == a and str(recupero) == z:
                etichetta.iloc[i:j] = nome
        i = j
    return etichetta.reindex(f.index)


# ----------------------------------------------------------------------------
# Domanda 1
# ----------------------------------------------------------------------------
def descrivi(x: pd.DataFrame) -> dict:
    vinte, perse = x[x["R"] > 0], x[x["R"] <= 0]
    d = {"op": len(x), "R": x["R"].sum(), "R/op": x["R"].mean(), "vinte%": len(vinte) / len(x) * 100,
         "R vinte": vinte["R"].mean(), "R perse": perse["R"].mean()}
    q = x["uscita"].value_counts(normalize=True) * 100
    for m in MOTIVI:
        d[m + "%"] = q.get(m, 0.0)
    return d


def scomposizione(a: dict, b: dict) -> dict:
    """R/op = w*Rv + (1-w)*Rp. Differenza A-B scomposta esattamente (medie fra le epoche):
    piu' perdenti (w), vincenti piu' piccole (Rv), perdenti piu' grandi (Rp)."""
    wa, wb = a["vinte%"] / 100, b["vinte%"] / 100
    w, rv, rp = (wa + wb) / 2, (a["R vinte"] + b["R vinte"]) / 2, (a["R perse"] + b["R perse"]) / 2
    piu_perdenti = (wa - wb) * (rv - rp)
    vinc_piccole = w * (a["R vinte"] - b["R vinte"])
    perd_grandi = (1 - w) * (a["R perse"] - b["R perse"])
    tot = a["R/op"] - b["R/op"]
    assert abs(piu_perdenti + vinc_piccole + perd_grandi - tot) < 1e-9
    return {"differenza R/op": tot, "piu' perdenti": piu_perdenti,
            "vincenti piu' piccole": vinc_piccole, "perdenti piu' grandi": perd_grandi}


# ----------------------------------------------------------------------------
# Domanda 2: placebo per giornata
# ----------------------------------------------------------------------------
def differenze(codici: np.ndarray, R: np.ndarray, k: int) -> np.ndarray:
    """R/op della fascia meno R/op del resto, per ogni fascia (NaN se vuota)."""
    s = np.bincount(codici, weights=R, minlength=k)
    c = np.bincount(codici, minlength=k).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        d = s / c - (R.sum() - s) / (len(R) - c)
    d[(c == 0) | (c == len(R))] = np.nan
    return d


def placebo(f: pd.DataFrame, nome: str, rng: np.random.Generator) -> dict:
    """Fascia peggiore e p del placebo che rimescola le fasce per GIORNATA.

    Tutte le operazioni dello stesso giorno restano insieme: le etichette di
    una giornata si spostano in blocco su un'altra giornata con lo stesso numero
    di operazioni (permutazione dei blocchi, stratificata per numero di
    operazioni del giorno). Statistica: la differenza minima (peggiore meno il
    resto) fra le fasce; p = (1 + #placebo <= osservato) / (N + 1).
    """
    x = f.dropna(subset=["f_" + nome])
    livelli = sorted(x["f_" + nome].unique(), key=str)
    cod = np.array([livelli.index(v) for v in x["f_" + nome]])
    R = x["R"].to_numpy(float)
    k = len(livelli)
    d_oss = differenze(cod, R, k)
    peggiore = int(np.nanargmin(d_oss))
    stat_oss = d_oss[peggiore]

    giorno = pd.DatetimeIndex(x["time"]).normalize()
    gcod = pd.factorize(giorno)[0]
    blocchi = {}
    for g in np.unique(gcod):
        pos = np.flatnonzero(gcod == g)
        blocchi.setdefault(len(pos), []).append(pos)
    matrici = [np.array(v) for v in blocchi.values()]       # (n_giorni, n_op) per taglia

    n_min = n_fissa = 0
    for _ in range(N_PLACEBO):
        nuovo = cod.copy()
        for m in matrici:
            nuovo[m] = cod[m[rng.permutation(len(m))]]
        d = differenze(nuovo, R, k)
        n_min += np.nanmin(d) <= stat_oss
        n_fissa += (not np.isnan(d[peggiore])) and d[peggiore] <= stat_oss
    conteggi = np.bincount(cod, minlength=k)
    medie = np.bincount(cod, weights=R, minlength=k) / np.where(conteggi == 0, np.nan, conteggi)
    return {"peggiore": livelli[peggiore], "diff": float(stat_oss),
            "p": (1 + n_min) / (N_PLACEBO + 1), "p fascia fissa": (1 + n_fissa) / (N_PLACEBO + 1),
            "n peggiore": int(conteggi[peggiore]), "n": len(x), "n.d.": int(len(f) - len(x)),
            "medie": dict(zip(livelli, medie)), "conteggi": dict(zip(livelli, conteggi))}


def verdetto(a: dict, b: dict) -> str:
    sa, sb = a["p"] < ALFA, b["p"] < ALFA
    if sa and sb and a["peggiore"] == b["peggiore"]:
        return "spiega i crolli"
    if sa and not sb:
        return "solo 2009-2019"
    if sb and not sa:
        return "solo 2020-2026"
    if sa and sb:
        return "nessuna separazione (fasce peggiori diverse)"
    return "nessuna separazione"


# ----------------------------------------------------------------------------
# Controllo di causalita'
# ----------------------------------------------------------------------------
def controllo_causalita(m1: pd.DataFrame, f: pd.DataFrame, d1: pd.DataFrame, n: int = 40) -> dict:
    """1) Per un campione di operazioni ricalcola i quattro valori D1 da un M1
    TRONCATO all'istante d'ingresso (solo candele < t): devono coincidere.
    2) Per TUTTE le operazioni l'ATR14 usato deve coincidere con
    ``framework.volatility.daily_atr`` letto sul giorno d'ingresso (shift di 1).
    3) La giornata D1 usata e' sempre precedente al giorno d'ingresso."""
    rng = np.random.default_rng(SEME)
    idx = np.unique(np.concatenate([rng.choice(len(f), n, replace=False), [0, 1, 2, len(f) - 3, len(f) - 2, len(f) - 1]]))
    scarti, nan_coerenti = [], 0
    for i in idx:
        r = f.iloc[i]
        t = pd.Timestamp(r["time"])
        tronco = m1[(m1.index >= t - pd.Timedelta(days=500)) & (m1.index < t)]
        assert tronco.index[-1] < t
        d = indicatori_d1(tronco)
        d = d[d.index < t.normalize()].iloc[-1]
        assert d.name == r["ieri"], "giornata D1 diversa fra archivio intero e tronco"
        mio = np.array([r["atr14_ieri"], r["ma50_ieri"], r["ma200_ieri"], r["ma200_20_ieri"]], float)
        suo = np.array([d["atr14"], d["ma50"], d["ma200"], d["ma200_20"]], float)
        assert (np.isnan(mio) == np.isnan(suo)).all(), "valori n.d. diversi fra archivio intero e tronco"
        ok = ~np.isnan(mio)
        nan_coerenti += int((~ok).sum())
        scarti.append(np.abs(mio[ok] - suo[ok]).max() if ok.any() else 0.0)
    scarti = np.array(scarti, dtype=float)
    atr_fw = daily_atr(m1)
    giorno = pd.DatetimeIndex(f["time"]).normalize()
    confronto = atr_fw.reindex(giorno).to_numpy()
    ok = ~np.isnan(confronto)
    scarto_fw = np.nanmax(np.abs(confronto[ok] - f["atr14_ieri"].to_numpy()[ok]))
    anticipo = (giorno - pd.DatetimeIndex(f["ieri"])).days
    return {"campione": len(idx), "scarto max tronco": float(scarti.max()),
            "valori n.d. coerenti (n.d. in entrambi)": nan_coerenti,
            "op confrontate con daily_atr": int(ok.sum()), "scarto max daily_atr": float(scarto_fw),
            "giorni fra ieri e ingresso: min/mediana/max": (int(anticipo.min()), float(np.median(anticipo)), int(anticipo.max()))}


# ----------------------------------------------------------------------------
def main():
    ops = pd.read_parquet(INGRESSO).sort_values("time").reset_index(drop=True)
    assert len(ops) == 712
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    d1 = indicatori_d1(m1)
    f = fasce(fattori(ops, d1))
    f["epoca"] = np.where(f["anno"] <= 2019, "2009-2019", "2020-2026")
    f["discesa"] = segna_discese(f)

    print("== controllo di causalita'")
    for k_, v in controllo_causalita(m1, f, d1).items():
        print(f"  {k_}: {v}")
    del m1

    A, B = f[f["epoca"] == "2009-2019"], f[f["epoca"] == "2020-2026"]
    gruppi = {"2009-2019": A, "2020-2026": B}
    for nome in sorted(DISCESE):
        gruppi["discesa " + nome] = f[f["discesa"] == nome]
    gruppi["tre discese"] = f[f["discesa"].notna()]

    print("\n== domanda 1: come perde")
    d1tab = pd.DataFrame({k_: descrivi(v) for k_, v in gruppi.items()}).T
    print(d1tab.round(3).to_string())
    sc = scomposizione(descrivi(A), descrivi(B))
    print("scomposizione R/op (2009-2019 meno 2020-2026): " + "  ".join(f"{k_} {v:+.3f}" for k_, v in sc.items()))

    print("\n== domanda 2: quando perde (p del placebo per giornata, N=%d, seme %d, soglia %.4f)" % (N_PLACEBO, SEME, ALFA))
    rng = np.random.default_rng(SEME)
    righe, dettaglio = [], []
    for nome, (etich, _) in FATTORI.items():
        ra, rb = placebo(A, nome, rng), placebo(B, nome, rng)
        righe.append({"fattore": etich, "peggiore 09-19": ra["peggiore"], "diff 09-19": ra["diff"], "p 09-19": ra["p"],
                      "peggiore 20-26": rb["peggiore"], "diff 20-26": rb["diff"], "p 20-26": rb["p"],
                      "p fissa 09-19": ra["p fascia fissa"], "p fissa 20-26": rb["p fascia fissa"],
                      "n.d. 09-19": ra["n.d."], "n.d. 20-26": rb["n.d."], "verdetto": verdetto(ra, rb)})
        for liv in sorted(set(ra["medie"]) | set(rb["medie"]), key=str):
            dettaglio.append({"fattore": etich, "fascia": liv,
                              "n 09-19": ra["conteggi"].get(liv, 0), "R/op 09-19": ra["medie"].get(liv, np.nan),
                              "n 20-26": rb["conteggi"].get(liv, 0), "R/op 20-26": rb["medie"].get(liv, np.nan)})
    tab2 = pd.DataFrame(righe).set_index("fattore")
    print(tab2[["peggiore 09-19", "diff 09-19", "p 09-19", "peggiore 20-26", "diff 20-26", "p 20-26", "verdetto"]].round(4).to_string())
    print("(p fascia fissa, non usata per il verdetto: " + "; ".join(
        f"{r['fattore'][:2]}:{r['p fissa 09-19']:.3f}/{r['p fissa 20-26']:.3f}" for r in righe) + ")")
    print("(operazioni senza fattore, n.d.: " + "; ".join(f"{r['fattore'][:2]}:{r['n.d. 09-19']}/{r['n.d. 20-26']}" for r in righe if r["n.d. 09-19"] + r["n.d. 20-26"]) + ")")
    tab2b = pd.DataFrame(dettaglio).set_index(["fattore", "fascia"])
    print(tab2b.round(3).to_string())

    print("\n== domanda 3: le tre discese, quota di operazioni per fascia (%)")
    resto = B[B["discesa"].isna()]
    righe3 = []
    for nome, (etich, _) in FATTORI.items():
        col = "f_" + nome
        for liv in sorted(B[col].dropna().unique(), key=str):
            r = {"fattore": etich, "fascia": liv, "resto 20-26": (resto[col] == liv).mean() * 100,
                 "tre discese": (gruppi["tre discese"][col] == liv).mean() * 100}
            for dn in sorted(DISCESE):
                r["n " + dn] = int((gruppi["discesa " + dn][col] == liv).sum())
            righe3.append(r)
    tab3 = pd.DataFrame(righe3).set_index(["fattore", "fascia"])
    print(tab3.round(1).to_string())
    print("operazioni per discesa: " + ", ".join(f"{dn}: {len(gruppi['discesa ' + dn])}" for dn in sorted(DISCESE))
          + f"; resto 2020-2026: {len(resto)}")

    # soglie dei terzi (per riprodurre le fasce)
    print("\n== soglie dei terzi (sulle 712)")
    for nome, (etich, continuo) in FATTORI.items():
        if continuo:
            q = f[nome].quantile([1 / 3, 2 / 3]).to_numpy()
            print(f"  {etich}: {q[0]:.5f} | {q[1]:.5f}   (n.d. {int(f[nome].isna().sum())})")

    f.to_parquet(USCITA)
    tab2.to_parquet(USCITA.replace(".parquet", "_domanda2.parquet"))
    print(f"\nsalvato {USCITA} ({len(f)} operazioni, {len(f.columns)} colonne)")


if __name__ == "__main__":
    main()
