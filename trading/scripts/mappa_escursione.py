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

# combinazioni usate per la geometria della rottura (sezione 6)
COMBI = [("asia", 60), ("london", 15), ("london", 30), ("london", 60),
         ("ny", 15), ("ny", 30), ("ny", 60)]
FINE_OPERATIVA = 21 * 60   # 21:00 UTC: oltre si paga lo swap, quindi si chiude qui
BERSAGLI = (1.0, 1.5, 2.0, 3.0)

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
    det = det.join(gg[["range_g", "atr", "max_g", "min_g"]])
    det["or_atr"] = det["or"] / det.atr
    det["or_su_range"] = det["or"] / det.range_g
    det["resto_su_or"] = det.resto_range / det["or"]
    det["resto_atr"] = det.resto_range / det.atr
    det["sess_range"] = det[["or_hi", "sess_hi"]].max(axis=1) - det[["or_lo", "sess_lo"]].min(axis=1)
    det["or_su_sess"] = det["or"] / det.sess_range
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
                    "or/range_sess": s.or_su_sess.median(),
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


# --------------------------------------------------------------------------
# 6. geometria della rottura del range d'apertura (NON e' una strategia:
#    e' la misura di quanto si allunga il prezzo dopo aver superato il bordo,
#    con lo stop sul bordo opposto, cioe' 1 R = larghezza della finestra)
# --------------------------------------------------------------------------
def geometria_rottura(m1: pd.DataFrame, placebo: bool = False,
                      seed: int = 20260804) -> pd.DataFrame:
    """Una sola operazione per giornata e per combinazione (prima rottura).

    Regole rispettate: ingresso al bordo (o all'apertura del minuto se e' gia'
    oltre), stop sul bordo opposto, nello stesso minuto lo STOP prevale, uscita
    a mercato alle 21:00 UTC (niente swap), costo spread 0,30 $ = 0.30/rischio R.
    Con ``placebo=True`` la banda ha la stessa larghezza ma e' spostata a caso:
    se i risultati non peggiorano, non e' il bordo del range a lavorare.
    """
    mod = m1["mod"].values
    hi, lo = m1.high.values, m1.low.values
    op, cl = m1.open.values, m1.close.values
    giorni_arr = m1["giorno"].values
    cambi = np.flatnonzero(np.r_[True, giorni_arr[1:] != giorni_arr[:-1]])
    inizi, fini = cambi, np.r_[cambi[1:], len(giorni_arr)]
    giorni = pd.DatetimeIndex(giorni_arr[cambi])
    rng = np.random.default_rng(seed)
    INF = 1 << 30

    righe = []
    for sess, w in COMBI:
        a = SESSIONS[sess][0] * 60
        b = a + w
        for k in range(len(giorni)):
            s, e = inizi[k], fini[k]
            md = mod[s:e]
            i0 = s + int(np.searchsorted(md, a))
            i1 = s + int(np.searchsorted(md, b))
            i2 = s + int(np.searchsorted(md, FINE_OPERATIVA))
            if i1 - i0 < max(5, w // 3) or i2 - i1 < 60:
                continue
            or_hi, or_lo = hi[i0:i1].max(), lo[i0:i1].min()
            larghezza = or_hi - or_lo
            if larghezza <= 0:
                continue
            if placebo:
                rif = cl[i1 - 1]
                for _ in range(30):
                    u = rng.uniform(-1.2, 1.2)
                    if abs(u) < 0.25:
                        continue
                    c_hi, c_lo = or_hi + u * larghezza, or_lo + u * larghezza
                    if c_lo < rif < c_hi:
                        or_hi, or_lo = c_hi, c_lo
                        break
                else:
                    continue

            H, L, O, C = hi[i1:i2], lo[i1:i2], op[i1:i2], cl[i1:i2]
            su = np.flatnonzero(H >= or_hi)
            giu = np.flatnonzero(L <= or_lo)
            j_su = int(su[0]) if su.size else INF
            j_giu = int(giu[0]) if giu.size else INF
            base = {"giorno": giorni[k], "sessione": sess, "finestra": w,
                    "larghezza": larghezza, "anno": giorni[k].year}
            if j_su == INF and j_giu == INF:
                righe.append({**base, "esito": "nessuna_rottura"})
                continue
            if j_su == j_giu:          # stesso minuto su entrambi i bordi: ordine ignoto
                righe.append({**base, "esito": "ambiguo"})
                continue

            if j_su < j_giu:
                lato, j = 1, j_su
                entry = max(or_hi, O[j])
                stop = or_lo
                rischio = entry - stop
                colpo = np.flatnonzero(L[j:] <= stop)
            else:
                lato, j = -1, j_giu
                entry = min(or_lo, O[j])
                stop = or_hi
                rischio = stop - entry
                colpo = np.flatnonzero(H[j:] >= stop)
            if rischio <= 0:
                continue
            if colpo.size:
                t = j + int(colpo[0])
                # regola 3: nel minuto t vince lo stop, quel massimo non conta
                if t > j:
                    estremo = H[j:t].max() if lato > 0 else L[j:t].min()
                    mfe = (estremo - entry) if lato > 0 else (entry - estremo)
                else:
                    mfe = 0.0
                stoppato, uscita = True, stop
            else:
                estremo = H[j:].max() if lato > 0 else L[j:].min()
                mfe = (estremo - entry) if lato > 0 else (entry - estremo)
                stoppato, uscita = False, C[-1]
            r_scadenza = ((uscita - entry) if lato > 0 else (entry - uscita)) / rischio
            righe.append({**base, "esito": "rottura", "lato": lato,
                          "rischio": rischio, "mfe_R": max(mfe, 0.0) / rischio,
                          "stoppato": stoppato, "r_scadenza": r_scadenza,
                          "spread_R": SPREAD / rischio,
                          "ora_rottura": (mod[i1 + j] // 60)})
    op_df = pd.DataFrame(righe).set_index("giorno")
    op_df["periodo"] = np.where(op_df.index.year <= 2019, "2009-2019", "2020-2026")
    return op_df


def riassunto_rottura(op_df: pd.DataFrame) -> pd.DataFrame:
    righe = []
    for periodo in PERIODI:
        p = op_df[op_df.periodo == periodo]
        for sess, w in COMBI:
            s = p[(p.sessione == sess) & (p.finestra == w)]
            if s.empty:
                continue
            r = s[s.esito == "rottura"]
            riga = {"periodo": periodo, "sessione": sess, "min": w,
                    "gg": len(s),
                    "rotto_%": 100 * (s.esito == "rottura").mean(),
                    "no_rott_%": 100 * (s.esito == "nessuna_rottura").mean(),
                    "ambiguo_%": 100 * (s.esito == "ambiguo").mean(),
                    "lato_su_%": 100 * (r.lato > 0).mean(),
                    "mfe_R_med": r.mfe_R.median(),
                    "spread_R": r.spread_R.median()}
            for k in BERSAGLI:
                riga[f"P(mfe>={k})"] = 100 * (r.mfe_R >= k).mean()
            righe.append(riga)
    return pd.DataFrame(righe)


def scomposizione(op_df: pd.DataFrame, bersaglio: float) -> pd.DataFrame:
    """obiettivo / stop / scadenza + R medio per operazione, lordo e netto."""
    righe = []
    for periodo in PERIODI:
        p = op_df[(op_df.periodo == periodo) & (op_df.esito == "rottura")]
        for sess, w in COMBI:
            r = p[(p.sessione == sess) & (p.finestra == w)]
            if r.empty:
                continue
            vinta = r.mfe_R >= bersaglio
            persa = (~vinta) & r.stoppato
            scad = (~vinta) & (~r.stoppato)
            lordo = np.where(vinta, bersaglio, np.where(persa, -1.0, r.r_scadenza))
            netto = lordo - r.spread_R.values
            righe.append({
                "periodo": periodo, "sessione": sess, "min": w, "op": len(r),
                "obiettivo_%": 100 * vinta.mean(),
                "stop_%": 100 * persa.mean(),
                "scadenza_%": 100 * scad.mean(),
                "R_scad_med": r.r_scadenza[scad].mean() if scad.any() else np.nan,
                "R_lordo": lordo.mean(),
                "R_netto": netto.mean(),
            })
    return pd.DataFrame(righe)


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
    gg["periodo"] = np.where(gg.index.year <= 2019, "2009-2019", "2020-2026")
    gg["range_su_atr"] = gg.range_g / gg.atr
    base = gg.groupby("periodo").agg(
        giornate=("range_g", "size"),
        barre_mediane=("barre", "median"),
        range_dollari=("range_g", "median"),
        atr_dollari=("atr", "median"),
        range_su_atr=("range_su_atr", "median"),
        spread_su_range=("range_g", lambda x: SPREAD / x.median()),
    )
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
    det.to_parquet(f"{GREZZI}/mappa_escursione_aperture.parquet")
    print(f"\n[dettaglio] {GREZZI}/mappa_escursione_*.parquet")


if __name__ == "__main__":
    main()
