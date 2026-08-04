"""Effetti di CALENDARIO su XAUUSD (2009-2026): direzione, ampiezza, operativita'.

Ipotesi pre-registrata in /workspace/dati_grezzi/IPOTESI_calendario.txt PRIMA
di guardare qualunque numero. In sintesi: mi aspetto che i giorni di
calendario cambino l'AMPIEZZA (NFP e FOMC molto piu' larghi) ma NON la
DIREZIONE, e che nessuna operazione 1:1,5-1:2 costruita sul calendario
sopravviva allo spread su entrambi i periodi. Primaria dichiarata:
turn-of-month LONG.

Categorie misurate (tutte note in ANTICIPO, nessun lookahead):
  - giorno della settimana (lun-ven);
  - indice del giorno di contrattazione nel mese, dall'inizio (+1..+5) e
    dalla fine (-1..-5);
  - primo / ultimo giorno di contrattazione del mese;
  - turn of month = ultimo giorno del mese precedente + primi 3 del mese;
  - primo venerdi' del mese (proxy NFP, dato alle 08:30 ET);
  - mercoledi'/giorni FOMC (lista di date pubblicate, comunicato alle 14:00 ET);
  - vigilia dei festivi USA principali (4 luglio, Ringraziamento, Natale);
  - mese dell'anno.

Convenzioni rispettate:
  - CAUSALITA': ogni decisione e' presa alla CHIUSURA di una candela M1 e
    l'ingresso avviene a quel prezzo; la corsa fra le barriere parte dalla
    candela SUCCESSIVA. L'ATR e' ``daily_atr(m1,14)``, gia' shiftato.
  - COSTI: 0,30 $ andata+ritorno, sottratti come 0,30/stop_in_dollari in R.
    L'operazione chiude entro le 16:55 ET, quindi non paga mai swap.
  - STOP PRIMA DELL'OBIETTIVO: nello stesso minuto vince lo stop.
  - RISULTATO IN R, sempre.
  - DIVISIONE 2009-2019 / 2020-2026 su ogni tabella.
  - CONTROLLO DI ASSURDITA': viene stampata la scomposizione obiettivo /
    stop / scadenza e verificato che l'obiettivo lontano sia colpito MENO
    dello stop vicino.
  - PLACEBO: per ogni categoria, 400 estrazioni di giorni finti appaiati per
    giorno della settimana; si riporta la banda 5-95% e il p empirico.

L'orologio e' quello di NEW YORK (America/New_York), come indicato dalla
ricognizione: le finestre in UTC sdoppiano gli eventi macro.

Uso:
    python3 trading/scripts/prova_calendario.py
Dettaglio per giornata in /workspace/dati_grezzi/calendario_giorni.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/workspace/sviluppo-strategie-e-bot/trading")

from framework.data import load_m1  # noqa: E402
from framework.volatility import daily_atr  # noqa: E402

DATI = "/workspace/sviluppo-strategie-e-bot/data/XAUUSD_M1"
GREZZI = "/workspace/dati_grezzi"
SPREAD = 0.30            # dollari, andata e ritorno
MIN_BARRE = 600          # candele M1 minime perche' la giornata sia "vera"
STOP_ATR = 0.25          # stop pre-registrato, in ATR (sopra il pavimento 0,20)
RR = (1.5, 2.0)          # obiettivi pre-registrati
FINE_ET = 16 * 60 + 55   # 16:55 ET: si chiude prima della pausa delle 17:00
N_PLACEBO = 400
SEME = 20260804
PERIODI = {"2009-2019": (2009, 2019), "2020-2026": (2020, 2026)}

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)
pd.set_option("display.float_format", lambda v: f"{v:.3f}")

# ---------------------------------------------------------------------------
# Date FOMC (giorno del comunicato, 14:00 ET). Lista da calendario pubblicato,
# validata piu' sotto contro la firma di volatilita' delle 14:00-14:30 ET: se
# la firma non c'e', l'etichetta e' sbagliata e i risultati non valgono.
# ---------------------------------------------------------------------------
FOMC = [
    "2009-01-28", "2009-03-18", "2009-04-29", "2009-06-24", "2009-08-12",
    "2009-09-23", "2009-11-04", "2009-12-16",
    "2010-01-27", "2010-03-16", "2010-04-28", "2010-06-23", "2010-08-10",
    "2010-09-21", "2010-11-03", "2010-12-14",
    "2011-01-26", "2011-03-15", "2011-04-27", "2011-06-22", "2011-08-09",
    "2011-09-21", "2011-11-02", "2011-12-13",
    "2012-01-25", "2012-03-13", "2012-04-25", "2012-06-20", "2012-08-01",
    "2012-09-13", "2012-10-24", "2012-12-12",
    "2013-01-30", "2013-03-20", "2013-05-01", "2013-06-19", "2013-07-31",
    "2013-09-18", "2013-10-30", "2013-12-18",
    "2014-01-29", "2014-03-19", "2014-04-30", "2014-06-18", "2014-07-30",
    "2014-09-17", "2014-10-29", "2014-12-17",
    "2015-01-28", "2015-03-18", "2015-04-29", "2015-06-17", "2015-07-29",
    "2015-09-17", "2015-10-28", "2015-12-16",
    "2016-01-27", "2016-03-16", "2016-04-27", "2016-06-15", "2016-07-27",
    "2016-09-21", "2016-11-02", "2016-12-14",
    "2017-02-01", "2017-03-15", "2017-05-03", "2017-06-14", "2017-07-26",
    "2017-09-20", "2017-11-01", "2017-12-13",
    "2018-01-31", "2018-03-21", "2018-05-02", "2018-06-13", "2018-08-01",
    "2018-09-26", "2018-11-08", "2018-12-19",
    "2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19", "2019-07-31",
    "2019-09-18", "2019-10-30", "2019-12-11",
    "2020-01-29", "2020-03-03", "2020-04-29", "2020-06-10", "2020-07-29",
    "2020-09-16", "2020-11-05", "2020-12-16",
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28",
    "2021-09-22", "2021-11-03", "2021-12-15",
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27",
    "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26",
    "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31",
    "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
    "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
]


# ---------------------------------------------------------------------------
# 1. preparazione: giornate vere, orologio di New York, etichette di calendario
# ---------------------------------------------------------------------------
def prepara(m1: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ritorna (m1 arricchito sulle giornate vere, tabella per giornata)."""
    ny = m1.index.tz_convert("America/New_York")
    m1 = m1.copy()
    m1["gior"] = pd.DatetimeIndex(ny.normalize().tz_localize(None))
    m1["met"] = ny.hour * 60 + ny.minute          # minuto del giorno, ora ET

    barre = m1.groupby("gior").size()
    vere = barre[barre >= MIN_BARRE].index
    m1 = m1[m1.gior.isin(vere)]

    g = m1.groupby("gior")
    gg = pd.DataFrame({"barre": g.size()})
    gg["anno"] = gg.index.year
    gg["dow"] = gg.index.dayofweek
    gg["mese"] = gg.index.month

    # indice del giorno di contrattazione DENTRO il mese (dall'inizio e dalla fine)
    per_mese = gg.groupby([gg.index.year, gg.index.month]).cumcount() + 1
    tot_mese = gg.groupby([gg.index.year, gg.index.month])["barre"].transform("size")
    gg["td"] = per_mese.values
    gg["td_fine"] = (per_mese - tot_mese - 1).values      # -1 = ultimo giorno

    # ampiezza e deriva della sessione 08:00-17:00 ET (finestra operativa)
    sess = m1[(m1.met >= 8 * 60) & (m1.met < 17 * 60)]
    s = sess.groupby("gior")
    gg["sess_max"] = s.high.max()
    gg["sess_min"] = s.low.min()
    gg["sess_open"] = s.open.first()
    gg["sess_close"] = s.close.last()
    gg["sess_range"] = gg.sess_max - gg.sess_min
    gg["sess_var"] = gg.sess_close - gg.sess_open

    # ampiezza dell'intera giornata quotata (per contesto)
    gg["gg_range"] = g.high.max() - g.low.min()

    # ATR causale (indicizzato per giorno UTC): riportato sull'indice ET con
    # l'ultimo valore NOTO, quindi mai in avanti
    atr = daily_atr(m1.drop(columns=["gior", "met"]), 14).dropna()
    atr.index = pd.DatetimeIndex(atr.index.tz_convert("UTC").tz_localize(None)).normalize()
    gg["atr"] = atr.reindex(gg.index.union(atr.index)).ffill().reindex(gg.index)
    gg = gg[gg.atr.notna() & (gg.atr > 0)]
    m1 = m1[m1.gior.isin(gg.index)]

    gg["range_atr"] = gg.sess_range / gg.atr
    gg["var_atr"] = gg.sess_var / gg.atr
    gg["var_bp"] = 1e4 * gg.sess_var / gg.sess_open

    # --- etichette di calendario ------------------------------------------
    gg["primo_mese"] = gg.td == 1
    gg["ultimo_mese"] = gg.td_fine == -1
    # turn of month: ultimo giorno del mese precedente + primi 3 del mese
    gg["tom"] = gg.ultimo_mese | (gg.td <= 3)
    # primo venerdi' del mese (proxy NFP)
    gg["nfp"] = (gg.dow == 4) & (gg.index.day <= 7)
    gg["fomc"] = gg.index.isin(pd.DatetimeIndex(FOMC))
    gg["vigilia_festa"] = vigilie(gg.index)
    return m1, gg


def vigilie(idx: pd.DatetimeIndex) -> np.ndarray:
    """Ultimo giorno di contrattazione prima di 4 luglio, Ringraziamento, Natale."""
    feste = []
    for anno in sorted(set(idx.year)):
        feste.append(pd.Timestamp(anno, 7, 4))
        nov = pd.date_range(f"{anno}-11-01", f"{anno}-11-30")
        feste.append(nov[nov.dayofweek == 3][3])      # 4o giovedi' di novembre
        feste.append(pd.Timestamp(anno, 12, 25))
        feste.append(pd.Timestamp(anno, 1, 1))
    out = np.zeros(len(idx), dtype=bool)
    for f in feste:
        prima = idx[idx < f]
        if len(prima):
            out[idx.get_loc(prima[-1])] = True
    return out


# ---------------------------------------------------------------------------
# 2. corsa fra le barriere, una operazione al giorno
# ---------------------------------------------------------------------------
def corse(m1: pd.DataFrame, gg: pd.DataFrame, minuto_et: int) -> pd.DataFrame:
    """Per ogni giornata: esito della corsa long e short, per ogni RR.

    Decisione alla CHIUSURA della candela M1 che apre a ``minuto_et``;
    ingresso a quel prezzo; la corsa usa le candele SUCCESSIVE fino alle
    16:55 ET. Stop = ``STOP_ATR`` x ATR; nello stesso minuto vince lo stop.
    """
    fin = m1[(m1.met >= minuto_et) & (m1.met <= FINE_ET)]
    ris = {}
    for gior, blocco in fin.groupby("gior", sort=True):
        if blocco.met.iloc[0] != minuto_et or len(blocco) < 30:
            continue                       # minuto d'ingresso mancante
        entry = float(blocco.close.iloc[0])
        hi = blocco.high.values[1:]
        lo = blocco.low.values[1:]
        if len(hi) < 20:
            continue
        fine = float(blocco.close.values[-1])
        d = STOP_ATR * float(gg.atr.loc[gior])
        riga = {"entry": entry, "stop_d": d, "costo": SPREAD / d, "n_min": len(hi)}
        for verso, nome in ((1, "long"), (-1, "short")):
            if verso == 1:
                t_stop = primo(lo <= entry - d)
            else:
                t_stop = primo(hi >= entry + d)
            for rr in RR:
                if verso == 1:
                    t_tgt = primo(hi >= entry + rr * d)
                else:
                    t_tgt = primo(lo <= entry - rr * d)
                if t_stop >= 0 and (t_tgt < 0 or t_stop <= t_tgt):
                    r, esito = -1.0, "stop"
                elif t_tgt >= 0:
                    r, esito = rr, "obiettivo"
                else:
                    r, esito = verso * (fine - entry) / d, "scadenza"
                riga[f"r_{nome}_{rr}"] = r - riga["costo"]
                riga[f"e_{nome}_{rr}"] = esito
        ris[gior] = riga
    out = pd.DataFrame.from_dict(ris, orient="index")
    out.index.name = "gior"
    return out


def primo(mask: np.ndarray) -> int:
    """Indice del primo True, -1 se nessuno."""
    w = np.flatnonzero(mask)
    return int(w[0]) if len(w) else -1


# ---------------------------------------------------------------------------
# 3. riepiloghi
# ---------------------------------------------------------------------------
def t_stat(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 5 or x.std(ddof=1) == 0:
        return np.nan
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def descrittiva(gg: pd.DataFrame, categorie: dict) -> pd.DataFrame:
    """Ampiezza e deriva della sessione 08-17 ET per categoria e periodo."""
    righe = []
    for nome, (a, b) in PERIODI.items():
        sub = gg[(gg.anno >= a) & (gg.anno <= b)]
        base_amp = sub.range_atr.median()
        for cat, mask in categorie.items():
            s = sub[mask.reindex(sub.index, fill_value=False)]
            if len(s) < 20:
                continue
            righe.append({
                "periodo": nome, "categoria": cat, "n": len(s),
                "amp_atr": s.range_atr.median(),
                "amp_rel": s.range_atr.median() / base_amp,
                "deriva_bp": s.var_bp.mean(),
                "t": t_stat(s.var_bp),
                "pos%": 100 * (s.sess_var > 0).mean(),
            })
    return pd.DataFrame(righe)


def operativa(gg: pd.DataFrame, cor: pd.DataFrame, categorie: dict,
              rr: float) -> pd.DataFrame:
    """R netto per operazione e scomposizione, per categoria/verso/periodo."""
    tab = gg.join(cor, how="inner")
    righe = []
    for nome, (a, b) in PERIODI.items():
        sub = tab[(tab.anno >= a) & (tab.anno <= b)]
        for cat, mask in categorie.items():
            s = sub[mask.reindex(sub.index, fill_value=False)]
            if len(s) < 20:
                continue
            for verso in ("long", "short"):
                r = s[f"r_{verso}_{rr}"]
                e = s[f"e_{verso}_{rr}"]
                righe.append({
                    "periodo": nome, "categoria": cat, "verso": verso,
                    "n": len(s), "r_op": r.mean(), "t": t_stat(r),
                    "obiettivo%": 100 * (e == "obiettivo").mean(),
                    "stop%": 100 * (e == "stop").mean(),
                    "scadenza%": 100 * (e == "scadenza").mean(),
                    "costo_R": s.costo.mean(),
                })
    return pd.DataFrame(righe)


def placebo(gg: pd.DataFrame, cor: pd.DataFrame, mask: pd.Series, colonna: str,
            periodo: tuple[int, int], rng: np.random.Generator) -> dict:
    """Giorni finti appaiati per giorno della settimana: banda 5-95% e p."""
    tab = gg.join(cor, how="inner")
    a, b = periodo
    sub = tab[(tab.anno >= a) & (tab.anno <= b)]
    veri = sub[mask.reindex(sub.index, fill_value=False)]
    if len(veri) < 20:
        return {}
    conteggi = veri.dow.value_counts().to_dict()
    pool = {d: sub.index[(sub.dow == d)] for d in conteggi}
    finti = []
    for _ in range(N_PLACEBO):
        scelti = []
        for d, k in conteggi.items():
            p = pool[d]
            scelti.append(rng.choice(p, size=min(k, len(p)), replace=False))
        idx = pd.DatetimeIndex(np.concatenate(scelti))
        finti.append(sub.loc[idx, colonna].mean())
    finti = np.array(finti)
    vero = veri[colonna].mean()
    return {"vero": vero, "p05": np.quantile(finti, 0.05),
            "p50": np.quantile(finti, 0.50), "p95": np.quantile(finti, 0.95),
            "p_bilat": 2 * min((finti >= vero).mean(), (finti <= vero).mean())}


# ---------------------------------------------------------------------------
def main() -> None:
    os.makedirs(GREZZI, exist_ok=True)
    m1 = load_m1(DATI)
    m1, gg = prepara(m1)
    rng = np.random.default_rng(SEME)

    print("\n=== 0. campione ===")
    print(f"giornate vere: {len(gg)}  ({(gg.anno<=2019).sum()} + {(gg.anno>=2020).sum()})"
          f"  candele M1 usate: {len(m1):,}")

    # --- 0b. validazione delle etichette NFP e FOMC -----------------------
    print("\n=== 0b. firma di volatilita' delle etichette (controllo) ===")
    righe = []
    for nome, (a, b) in PERIODI.items():
        sub = m1[(m1.gior.dt.year >= a) & (m1.gior.dt.year <= b)]
        for etich, minuti, riferim in (
            ("NFP 08:30-09:00 ET", (8 * 60 + 30, 9 * 60), gg.dow == 4),
            ("FOMC 14:00-14:30 ET", (14 * 60, 14 * 60 + 30), gg.dow == 2),
        ):
            fin = sub[(sub.met >= minuti[0]) & (sub.met < minuti[1])]
            amp = (fin.groupby("gior").high.max() - fin.groupby("gior").low.min())
            amp = amp / gg.atr.reindex(amp.index)
            colonna = gg.nfp if etich.startswith("NFP") else gg.fomc
            ev = amp[colonna.reindex(amp.index, fill_value=False)]
            ctr = amp[riferim.reindex(amp.index, fill_value=False)
                      & ~colonna.reindex(amp.index, fill_value=False)]
            righe.append({"periodo": nome, "finestra": etich, "n_ev": len(ev),
                          "amp_ev_atr": ev.median(), "n_ctr": len(ctr),
                          "amp_ctr_atr": ctr.median(),
                          "rapporto": ev.median() / ctr.median()})
    print(pd.DataFrame(righe).to_string(index=False))

    # --- categorie ---------------------------------------------------------
    categorie = {
        "tutti": pd.Series(True, index=gg.index),
        "lunedi": gg.dow == 0, "martedi": gg.dow == 1, "mercoledi": gg.dow == 2,
        "giovedi": gg.dow == 3, "venerdi": gg.dow == 4,
        "primo giorno mese": gg.primo_mese, "ultimo giorno mese": gg.ultimo_mese,
        "turn of month": gg.tom, "resto del mese": ~gg.tom,
        "td +2": gg.td == 2, "td +3": gg.td == 3,
        "td -2": gg.td_fine == -2, "td -3": gg.td_fine == -3,
        "NFP (1o ven)": gg.nfp, "venerdi non NFP": (gg.dow == 4) & ~gg.nfp,
        "FOMC": gg.fomc, "mercoledi non FOMC": (gg.dow == 2) & ~gg.fomc,
        "vigilia festa": pd.Series(gg.vigilia_festa.values, index=gg.index),
    }

    print("\n=== 1. ampiezza e deriva della sessione 08:00-17:00 ET ===")
    print("amp_rel = ampiezza mediana in ATR / ampiezza mediana di tutte le giornate")
    d = descrittiva(gg, categorie)
    for p in PERIODI:
        print(f"\n-- {p} --")
        print(d[d.periodo == p].drop(columns="periodo").to_string(index=False))

    print("\n=== 2. deriva per mese dell'anno (bp, sessione 08-17 ET) ===")
    mesi = {f"m{m:02d}": gg.mese == m for m in range(1, 13)}
    dm = descrittiva(gg, mesi)
    print(dm.pivot(index="categoria", columns="periodo",
                   values=["deriva_bp", "t", "amp_rel"]).to_string())

    # --- 3. operativita' ---------------------------------------------------
    cor_open = corse(m1, gg, 8 * 60)          # 08:00 ET: categorie generiche
    cor_nfp = corse(m1, gg, 8 * 60 + 30)      # 08:30 ET: dopo il dato NFP
    cor_fomc = corse(m1, gg, 14 * 60)         # 14:00 ET: dopo il comunicato FOMC

    gen = {k: v for k, v in categorie.items() if k not in ("NFP (1o ven)", "FOMC")}
    for rr in RR:
        print(f"\n=== 3. una operazione al giorno, ingresso 08:00 ET, "
              f"stop {STOP_ATR} ATR, obiettivo 1:{rr} ===")
        o = operativa(gg, cor_open, gen, rr)
        for p in PERIODI:
            print(f"\n-- {p} --")
            print(o[o.periodo == p].drop(columns="periodo").to_string(index=False))

    print(f"\n=== 4. eventi macro, ingresso DOPO l'evento, stop {STOP_ATR} ATR ===")
    for rr in RR:
        for etich, cor, cat in (("NFP 08:30 ET", cor_nfp, "NFP (1o ven)"),
                                ("FOMC 14:00 ET", cor_fomc, "FOMC")):
            sotto = {cat: categorie[cat],
                     "controllo stesso dow": (gg.dow == (4 if cat.startswith("NFP") else 2))
                     & ~categorie[cat]}
            o = operativa(gg, cor, sotto, rr)
            print(f"\n-- {etich}, obiettivo 1:{rr} --")
            print(o.to_string(index=False))

    # --- 5. placebo --------------------------------------------------------
    print(f"\n=== 5. placebo: {N_PLACEBO} estrazioni di giorni finti "
          f"appaiati per giorno della settimana ===")
    righe = []
    prove = [("turn of month", categorie["turn of month"], cor_open, "r_long_2.0"),
             ("turn of month", categorie["turn of month"], cor_open, "r_short_2.0"),
             ("primo giorno mese", categorie["primo giorno mese"], cor_open, "r_long_2.0"),
             ("ultimo giorno mese", categorie["ultimo giorno mese"], cor_open, "r_long_2.0"),
             ("NFP (1o ven)", categorie["NFP (1o ven)"], cor_nfp, "r_long_2.0"),
             ("NFP (1o ven)", categorie["NFP (1o ven)"], cor_nfp, "r_short_2.0"),
             ("FOMC", categorie["FOMC"], cor_fomc, "r_long_2.0"),
             ("FOMC", categorie["FOMC"], cor_fomc, "r_short_2.0")]
    for cat, mask, cor, col in prove:
        for p, (a, b) in PERIODI.items():
            res = placebo(gg, cor, mask, col, (a, b), rng)
            if res:
                righe.append({"categoria": cat, "misura": col, "periodo": p, **res})
    print(pd.DataFrame(righe).to_string(index=False))

    # --- 6. tenuta per anno della primaria e dei candidati -----------------
    print("\n=== 6. R per operazione anno per anno (obiettivo 1:2) ===")
    tab = gg.join(cor_open, how="inner")
    tab_nfp = gg.join(cor_nfp, how="inner")
    tab_fomc = gg.join(cor_fomc, how="inner")
    colonne = {}
    colonne["TOM long"] = tab[tab.tom.values].groupby("anno")["r_long_2.0"].mean()
    colonne["tutti long"] = tab.groupby("anno")["r_long_2.0"].mean()
    colonne["NFP long"] = tab_nfp[tab_nfp.nfp.values].groupby("anno")["r_long_2.0"].mean()
    colonne["NFP short"] = tab_nfp[tab_nfp.nfp.values].groupby("anno")["r_short_2.0"].mean()
    colonne["FOMC long"] = tab_fomc[tab_fomc.fomc.values].groupby("anno")["r_long_2.0"].mean()
    colonne["FOMC short"] = tab_fomc[tab_fomc.fomc.values].groupby("anno")["r_short_2.0"].mean()
    peranno = pd.DataFrame(colonne)
    print(peranno.to_string())
    print("\nanni positivi su 18:")
    print((peranno > 0).sum().to_string())

    # --- 7. scomposizione e controllo di assurdita' ------------------------
    print("\n=== 7. controllo di assurdita' (obiettivo lontano vs stop vicino) ===")
    righe = []
    for etich, t in (("08:00 ET", tab), ("08:30 ET", tab_nfp), ("14:00 ET", tab_fomc)):
        for p, (a, b) in PERIODI.items():
            s = t[(t.anno >= a) & (t.anno <= b)]
            for verso in ("long", "short"):
                for rr in RR:
                    e = s[f"e_{verso}_{rr}"]
                    righe.append({"ingresso": etich, "periodo": p, "verso": verso,
                                  "rr": rr, "n": len(s),
                                  "obiettivo%": 100 * (e == "obiettivo").mean(),
                                  "stop%": 100 * (e == "stop").mean(),
                                  "scadenza%": 100 * (e == "scadenza").mean()})
    ass = pd.DataFrame(righe)
    ass["ok"] = ass["obiettivo%"] < ass["stop%"]
    print(ass.to_string(index=False))
    print(f"\ncelle che superano il controllo: {int(ass.ok.sum())}/{len(ass)}")

    # --- salvataggio -------------------------------------------------------
    gg.join(cor_open.add_prefix("o8_")).join(cor_nfp.add_prefix("o830_")) \
      .join(cor_fomc.add_prefix("o14_")) \
      .to_parquet(os.path.join(GREZZI, "calendario_giorni.parquet"))
    print(f"\ndettaglio -> {GREZZI}/calendario_giorni.parquet")


if __name__ == "__main__":
    main()
