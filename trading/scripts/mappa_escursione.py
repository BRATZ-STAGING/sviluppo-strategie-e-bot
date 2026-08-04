"""Mappa dell'escursione giornaliera di XAUUSD (nessuna strategia, solo misure).

Domande a cui risponde, separatamente per 2009-2019 (ricerca) e 2020-2026
(verifica):

  1. quanta parte del range giornaliero e' gia' stata percorsa alla fine di
     ogni ora UTC, e quanto range resta da fare (in ATR);
  2. quando si formano il massimo e il minimo della giornata;
  3. quanto valgono i primi 15/30/60 minuti di ogni sessione (asia 0-7,
     london 7-12, ny 12-21, late 21-24) in dollari, in ATR e in frazione di
     range giornaliero;
  4. che rapporto ha quel range d'apertura con l'escursione del RESTO della
     giornata: di quanti "range d'apertura" il prezzo si allunga dopo, sopra
     e sotto, e con che probabilita'.

Convenzioni e cautele:

  - giornata = giorno di calendario UTC con almeno ``MIN_BARRE`` candele M1.
    Lo spezzone della domenica sera e i mezzi festivi restano fuori: sono
    proprio quelli che gonfiano le frazioni orarie (poche ore, range piccolo).
  - l'ATR e' ``volatility.daily_atr(m1, 14)``, gia' causale (noto a inizio
    giornata): si puo' usare come unita' di misura senza guardare avanti.
  - le finestre d'apertura e le estensioni successive sono CAUSALI: la
    finestra si chiude alla fine del suo ultimo minuto, l'estensione guarda
    solo i minuti seguenti.
  - le frazioni di range orario (punto 1) sono invece DESCRITTIVE: il
    denominatore e' il range dell'intera giornata, che a quell'ora non e'
    ancora noto. Servono a descrivere la forma della giornata, non a decidere.
  - lo spread di 0,30 $ andata+ritorno e' riportato come costo in R nel caso
    in cui lo stop valga quanto il range d'apertura: e' il modo piu' onesto
    di dire se una finestra e' troppo stretta per essere tradata.

Uso:
    python3 trading/scripts/mappa_escursione.py
Il dettaglio per giornata finisce in /workspace/dati_grezzi/mappa_escursione*.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/workspace/sviluppo-strategie-e-bot/trading")

from framework.data import SESSIONS, load_m1  # noqa: E402
from framework.volatility import daily_atr  # noqa: E402

DATI = "/workspace/sviluppo-strategie-e-bot/data/XAUUSD_M1"
GREZZI = "/workspace/dati_grezzi"
SPREAD = 0.30           # dollari, andata e ritorno
MIN_BARRE = 600         # candele M1 minime perche' la giornata sia "vera"
FINESTRE = (15, 30, 60)  # minuti di apertura misurati
PERIODI = {"2009-2019": (2009, 2019), "2020-2026": (2020, 2026)}

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)


# --------------------------------------------------------------------------
# preparazione
# --------------------------------------------------------------------------
def prepara(m1: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ritorna (m1 filtrato sulle giornate vere, tabella per giornata)."""
    giorno = m1.index.normalize()
    barre = pd.Series(1, index=m1.index).groupby(giorno).size()
    vere = barre[barre >= MIN_BARRE].index

    m1 = m1[pd.Index(giorno).isin(vere)].copy()
    m1["giorno"] = m1.index.normalize()
    m1["mod"] = m1.index.hour * 60 + m1.index.minute   # minuto del giorno
    m1["ora"] = m1.index.hour

    g = m1.groupby("giorno")
    gg = pd.DataFrame({
        "max_g": g.high.max(),
        "min_g": g.low.min(),
        "open_g": g.open.first(),
        "close_g": g.close.last(),
        "barre": g.size(),
    })
    gg["range_g"] = gg.max_g - gg.min_g
    # ora di formazione degli estremi (minuto del giorno del primo tocco)
    gg["mod_max"] = m1.loc[g.high.idxmax(), "mod"].values
    gg["mod_min"] = m1.loc[g.low.idxmin(), "mod"].values
    gg["ora_max"] = gg.mod_max // 60
    gg["ora_min"] = gg.mod_min // 60
    gg["max_prima"] = gg.mod_max < gg.mod_min
    gg["anno"] = gg.index.year

    atr = daily_atr(m1, 14)
    gg["atr"] = atr.reindex(gg.index).values
    gg["barre_scartate"] = 0
    return m1, gg


def maschera_periodo(indice: pd.DatetimeIndex, periodo: str) -> np.ndarray:
    a, b = PERIODI[periodo]
    anni = indice.year
    return (anni >= a) & (anni <= b)


def q(s: pd.Series, p: float) -> float:
    s = s.dropna()
    return float(np.nan) if s.empty else float(s.quantile(p))


# --------------------------------------------------------------------------
# 1. profilo orario: quanta escursione e' gia' fatta
# --------------------------------------------------------------------------
def profilo_orario(m1: pd.DataFrame, gg: pd.DataFrame):
    """Massimo/minimo correnti alla fine di ogni ora UTC, per giornata."""
    ph = m1.groupby(["giorno", "ora"]).agg(hi=("high", "max"), lo=("low", "min"))
    hi = ph["hi"].unstack("ora").reindex(columns=range(24))
    lo = ph["lo"].unstack("ora").reindex(columns=range(24))
    cum_hi = hi.cummax(axis=1).ffill(axis=1)
    cum_lo = lo.cummin(axis=1).ffill(axis=1)
    cum_range = cum_hi - cum_lo

    gg = gg.reindex(cum_range.index)
    frazione = cum_range.div(gg.range_g, axis=0)
    residuo_atr = (gg.range_g.values[:, None] - cum_range).div(gg.atr, axis=0)
    max_fatto = cum_hi.ge(gg.max_g, axis=0)
    min_fatto = cum_lo.le(gg.min_g, axis=0)
    cum_atr = cum_range.div(gg.atr, axis=0)

    righe = []
    for periodo in PERIODI:
        m = maschera_periodo(cum_range.index, periodo)
        for h in range(24):
            attive = cum_range.loc[m, h].notna()
            n = int(attive.sum())
            if n == 0:
                continue
            righe.append({
                "periodo": periodo, "ora": h, "gg": n,
                "frazione_mediana": frazione.loc[m, h].median(),
                "frazione_media": frazione.loc[m, h].mean(),
                "cum_range_atr": cum_atr.loc[m, h].median(),
                "residuo_atr": residuo_atr.loc[m, h].median(),
                "max_gia_fatto_%": 100 * max_fatto.loc[m, h].mean(),
                "min_gia_fatto_%": 100 * min_fatto.loc[m, h].mean(),
                "entrambi_%": 100 * (max_fatto.loc[m, h] & min_fatto.loc[m, h]).mean(),
            })
    return pd.DataFrame(righe), cum_range


# --------------------------------------------------------------------------
# 2. ora di formazione degli estremi
# --------------------------------------------------------------------------
def ore_estremi(gg: pd.DataFrame) -> pd.DataFrame:
    righe = []
    for periodo in PERIODI:
        sub = gg[maschera_periodo(gg.index, periodo)]
        n = len(sub)
        for h in range(24):
            righe.append({
                "periodo": periodo, "ora": h,
                "max_%": 100 * (sub.ora_max == h).mean(),
                "min_%": 100 * (sub.ora_min == h).mean(),
                "estremo_%": 100 * ((sub.ora_max == h).mean() + (sub.ora_min == h).mean()) / 2,
                "gg": n,
            })
    return pd.DataFrame(righe)


def estremi_per_sessione(gg: pd.DataFrame) -> pd.DataFrame:
    righe = []
    for periodo in PERIODI:
        sub = gg[maschera_periodo(gg.index, periodo)]
        for nome, (a, b) in SESSIONS.items():
            dentro_max = (sub.ora_max >= a) & (sub.ora_max < b)
            dentro_min = (sub.ora_min >= a) & (sub.ora_min < b)
            righe.append({
                "periodo": periodo, "sessione": nome, "ore": f"{a:02d}-{b:02d}",
                "max_%": 100 * dentro_max.mean(),
                "min_%": 100 * dentro_min.mean(),
                "un_estremo_%": 100 * (dentro_max | dentro_min).mean(),
                "entrambi_%": 100 * (dentro_max & dentro_min).mean(),
            })
    return pd.DataFrame(righe)


# --------------------------------------------------------------------------
# 3-4. range d'apertura di sessione ed estensione successiva
# --------------------------------------------------------------------------
def aperture(m1: pd.DataFrame, gg: pd.DataFrame):
    """Per ogni (sessione, finestra): range d'apertura e cosa succede dopo."""
    dettaglio = []
    for sess, (h0, h1) in SESSIONS.items():
        inizio, fine_sess = h0 * 60, h1 * 60
        for w in FINESTRE:
            fin = m1[(m1["mod"] >= inizio) & (m1["mod"] < inizio + w)]
            if fin.empty:
                continue
            g = fin.groupby("giorno")
            tab = pd.DataFrame({
                "or_hi": g.high.max(), "or_lo": g.low.min(),
                "or_close": g.close.last(), "or_barre": g.size(),
            })
            tab = tab[tab.or_barre >= max(5, w // 3)]   # finestra sostanzialmente piena
            tab["or"] = tab.or_hi - tab.or_lo

            # resto della GIORNATA dopo la finestra (causale: solo minuti seguenti)
            dopo = m1[m1["mod"] >= inizio + w]
            gd = dopo.groupby("giorno")
            tab["dopo_hi"] = gd.high.max().reindex(tab.index)
            tab["dopo_lo"] = gd.low.min().reindex(tab.index)
            tab["dopo_barre"] = gd.size().reindex(tab.index)
            # resto della SESSIONE dopo la finestra
            ds = m1[(m1["mod"] >= inizio + w) & (m1["mod"] < fine_sess)]
            gs = ds.groupby("giorno")
            tab["sess_hi"] = gs.high.max().reindex(tab.index)
            tab["sess_lo"] = gs.low.min().reindex(tab.index)

            tab["resto_range"] = tab.dopo_hi - tab.dopo_lo
            tab["resto_sess_range"] = tab.sess_hi - tab.sess_lo
            tab["est_su"] = (tab.dopo_hi - tab.or_hi).clip(lower=0)
            tab["est_giu"] = (tab.or_lo - tab.dopo_lo).clip(lower=0)
            tab["sessione"] = sess
            tab["finestra"] = w
            dettaglio.append(tab)

    det = pd.concat(dettaglio)
    det = det.join(gg[["range_g", "atr", "max_g", "min_g"]], on=det.index.name or None) \
        if False else det.join(gg[["range_g", "atr", "max_g", "min_g"]])
    det["or_atr"] = det["or"] / det.atr
    det["or_su_range"] = det["or"] / det.range_g
    det["resto_su_or"] = det.resto_range / det["or"]
    det["resto_atr"] = det.resto_range / det.atr
    det["est_su_or"] = det.est_su / det["or"]
    det["est_giu_or"] = det.est_giu / det["or"]
    det["est_max_or"] = det[["est_su_or", "est_giu_or"]].max(axis=1)
    det["est_min_or"] = det[["est_su_or", "est_giu_or"]].min(axis=1)
    det["spread_R"] = SPREAD / det["or"]     # costo se lo stop vale un range d'apertura
    det["anno"] = det.index.year

    righe = []
    for periodo in PERIODI:
        m = maschera_periodo(det.index, periodo)
        sub = det[m]
        for sess in SESSIONS:
            for w in FINESTRE:
                s = sub[(sub.sessione == sess) & (sub.finestra == w)]
                if s.empty:
                    continue
                righe.append({
                    "periodo": periodo, "sessione": sess, "min": w, "gg": len(s),
                    "or_$": s["or"].median(),
                    "or/ATR": s.or_atr.median(),
                    "or/range_g": s.or_su_range.median(),
                    "resto/or": s.resto_su_or.median(),
                    "resto_ATR": s.resto_atr.median(),
                    "estSU/or": s.est_su_or.median(),
                    "estGIU/or": s.est_giu_or.median(),
                    "est_max/or": s.est_max_or.median(),
                    "est_min/or": s.est_min_or.median(),
                    "spread_R": s.spread_R.median(),
                })
    riass = pd.DataFrame(righe)

    # probabilita' di estensione oltre k range d'apertura, per lato
    soglie = (0.5, 1.0, 1.5, 2.0, 3.0)
    righe = []
    for periodo in PERIODI:
        sub = det[maschera_periodo(det.index, periodo)]
        for sess in SESSIONS:
            for w in FINESTRE:
                s = sub[(sub.sessione == sess) & (sub.finestra == w)]
                if s.empty:
                    continue
                r = {"periodo": periodo, "sessione": sess, "min": w, "gg": len(s)}
                for k in soglie:
                    r[f"1lato>={k}"] = 100 * (s.est_max_or >= k).mean()
                    r[f"2lati>={k}"] = 100 * (s.est_min_or >= k).mean()
                righe.append(r)
    prob = pd.DataFrame(righe)
    return det, riass, prob


def stabilita_annuale(det: pd.DataFrame, sess: str, w: int) -> pd.DataFrame:
    s = det[(det.sessione == sess) & (det.finestra == w)]
    out = s.groupby("anno").agg(
        gg=("or", "size"),
        or_dollari=("or", "median"),
        or_atr=("or_atr", "median"),
        resto_su_or=("resto_su_or", "median"),
        est_max_or=("est_max_or", "median"),
        p_1lato_1=("est_max_or", lambda x: 100 * (x >= 1).mean()),
        p_2lati_1=("est_min_or", lambda x: 100 * (x >= 1).mean()),
        spread_R=("spread_R", "median"),
    )
    return out


# --------------------------------------------------------------------------
def main() -> None:
    os.makedirs(GREZZI, exist_ok=True)
    m1 = load_m1(DATI)
    tot_barre = len(m1)
    m1, gg = prepara(m1)
    print(f"\n[giornate] {len(gg)} giornate vere (>= {MIN_BARRE} barre M1); "
          f"{tot_barre - len(m1):,} candele scartate su {tot_barre:,}")
    base = gg.groupby(gg.index.year.map(
        lambda y: "2009-2019" if y <= 2019 else "2020-2026")).agg(
        gg=("range_g", "size"),
        barre_mediane=("barre", "median"),
        range_$=("range_g", "median"),
        atr_$=("atr", "median"),
        range_su_atr=("range_g", "median"),
    )
    base["range_su_atr"] = gg.assign(r=gg.range_g / gg.atr).groupby(
        gg.index.year.map(lambda y: "2009-2019" if y <= 2019 else "2020-2026")).r.median()
    print("\n=== BASE (mediane per giornata) ===")
    print(base.round(3).to_string())

    prof, _ = profilo_orario(m1, gg)
    print("\n=== 1. PROFILO ORARIO: escursione gia' fatta a fine ora (frazione del range del giorno) ===")
    for periodo in PERIODI:
        p = prof[prof.periodo == periodo].set_index("ora").drop(columns=["periodo"])
        print(f"\n-- {periodo} --")
        print(p.round(3).to_string())

    oe = ore_estremi(gg)
    print("\n=== 2a. ORA DI FORMAZIONE DEGLI ESTREMI (% giornate) ===")
    piv = oe.pivot(index="ora", columns="periodo", values=["max_%", "min_%"])
    print(piv.round(2).to_string())
    es = estremi_per_sessione(gg)
    print("\n=== 2b. ESTREMI PER SESSIONE ===")
    print(es.round(2).to_string(index=False))

    det, riass, prob = aperture(m1, gg)
    print("\n=== 3. RANGE D'APERTURA DI SESSIONE (mediane) ===")
    for periodo in PERIODI:
        print(f"\n-- {periodo} --")
        print(riass[riass.periodo == periodo].drop(columns=["periodo"])
              .round(3).to_string(index=False))

    print("\n=== 4. PROBABILITA' DI ESTENSIONE OLTRE k RANGE D'APERTURA (% giornate) ===")
    print("   1lato = almeno un lato sfondato di k*OR ; 2lati = entrambi i lati")
    for periodo in PERIODI:
        p = prob[prob.periodo == periodo].drop(columns=["periodo"])
        print(f"\n-- {periodo} --")
        print(p.round(1).to_string(index=False))

    print("\n=== 5. STABILITA' ANNUALE (london 30 min) ===")
    print(stabilita_annuale(det, "london", 30).round(3).to_string())
    print("\n=== 5b. STABILITA' ANNUALE (ny 30 min) ===")
    print(stabilita_annuale(det, "ny", 30).round(3).to_string())

    gg.to_parquet(f"{GREZZI}/mappa_escursione_giornate.parquet")
    prof.to_parquet(f"{GREZZI}/mappa_escursione_orario.parquet")
    det.drop(columns=["sessione"]).assign(sessione=det.sessione.astype("category")) \
        .to_parquet(f"{GREZZI}/mappa_escursione_aperture.parquet")
    print(f"\n[dettaglio] {GREZZI}/mappa_escursione_*.parquet")


if __name__ == "__main__":
    main()
