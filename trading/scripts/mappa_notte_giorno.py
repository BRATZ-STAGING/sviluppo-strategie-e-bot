"""Mappa "notte-giorno" di XAUUSD: dove nasce il movimento e cosa predice cosa.

Nessuna strategia: solo misure, separate su 2009-2019 (ricerca) e 2020-2026
(verifica), con i numeri accanto a ogni fatto.

DEFINIZIONI (fissate dal committente, non negoziabili)
  GIORNO(D)  = 07:00 -> 21:00 UTC della giornata D
  NOTTE(D)   = 21:00 UTC della giornata di borsa PRECEDENTE -> 07:00 UTC di D

  Gli ancoraggi sono CHIUSURE di minuto: ancora07(D) = close dell'ultimo minuto
  prima delle 07:00, ancora21(D) = close dell'ultimo minuto prima delle 21:00.
  Quindi:
      notte(D)  = ancora07(D)  - ancora21(D-1)
      giorno(D) = ancora21(D)  - ancora07(D)
  e la somma delle due e' ESATTAMENTE la variazione da chiusura a chiusura
  (21:00 -> 21:00): la scomposizione non perde e non inventa un centesimo.

  La notte del lunedi' contiene tutto il fine settimana (venerdi' 21:00 ->
  lunedi' 07:00, ~58 ore, riapertura della domenica sera inclusa): e' un'altra
  cosa rispetto a una notte feriale e viene SEMPRE riportata separata.

  Nota sull'orario: il mercato dell'oro chiude un'ora al giorno alle 21:00 UTC
  da marzo a ottobre e alle 22:00 UTC da novembre a febbraio (segue l'ora legale
  di New York). Il confine delle 21:00 cade quindi sulla chiusura vera in
  estate e un'ora prima in inverno; l'ora 21-22 invernale e' contata nella
  notte, coerentemente con la sessione "late" del progetto.

CAUSALITA' (regola 1)
  Ogni misura e' ancorata alla CHIUSURA del minuto, mai all'apertura. Le
  variabili predittive sono note prima dell'inizio della finestra prevista:
  notte(D) e' nota alle 07:00 di D, la prima ora e' nota alle 08:00, il giorno
  precedente e' noto alle 21:00 di D-1. L'ATR usato per normalizzare e'
  ``daily_atr``, gia' shiftato di una giornata.

UNITA' (regola 4)
  Le somme storiche sono in punti base (1 bp = 0,01% del prezzo), perche' l'oro
  e' passato da ~900$ a ~3500$ e i dollari non sono confrontabili fra periodi.
  Le misure "da operativo" sono in unita' di ATR giornaliero causale: con uno
  stop pari a k*ATR, R = mossa/(k*ATR) e il costo di spread e' 0.30/(k*ATR).
  Le tabelle riportano k=1 (cioe' ATR puro): chi vuole uno stop piu' stretto
  moltiplica per 1/k, che e' la stessa cosa per ricavo e per costo.

COSTI (regola 2)
  Spread 0,30 $ andata+ritorno. Swap long -71,5 $ per lotto (100 once) per
  notte = -0,715 $ per oncia per notte: e' l'ostacolo che qualunque rendimento
  notturno deve superare, ed e' misurato in bp accanto al rendimento notturno.

Il dettaglio grezzo va in /workspace/dati_grezzi/mappa_notte_giorno/, in chat
solo tabelle compatte.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

REPO = "/workspace/sviluppo-strategie-e-bot"
sys.path.insert(0, os.path.join(REPO, "trading"))

from framework.data import load_m1            # noqa: E402
from framework.volatility import daily_atr    # noqa: E402

USCITA = "/workspace/dati_grezzi/mappa_notte_giorno"
PERIODI = {"2009-2019": (2009, 2019), "2020-2026": (2020, 2026)}
SPREAD_USD = 0.30       # andata e ritorno
SWAP_LONG_LOTTO = -71.5  # $ per lotto (100 once) per notte
SWAP_LONG_ONCIA = SWAP_LONG_LOTTO / 100.0
ORA_GIORNO = 7          # inizio del giorno, UTC
ORA_NOTTE = 21          # inizio della notte, UTC
MIN_MINUTI_GIORNO = 500  # su 840 possibili: sotto e' mezza giornata di festa
MIN_MINUTI_NOTTE = 350   # su ~540 effettivi (una l'ora di stacco)
N_PLACEBO = 400
GIORNI = ["lun", "mar", "mer", "gio", "ven"]

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)
pd.set_option("display.float_format", lambda v: f"{v:8.3f}")


# --------------------------------------------------------------- utilita' base
def t_student(x: np.ndarray) -> float:
    """t sulle osservazioni giornaliere (indipendenti), non sui minuti."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 3 or x.std(ddof=1) == 0:
        return np.nan
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def periodo_di(anni: pd.Series) -> pd.Series:
    p = pd.Series(index=anni.index, dtype=object)
    for nome, (a, b) in PERIODI.items():
        p[(anni >= a) & (anni <= b)] = nome
    return p


def corr(x: np.ndarray, y: np.ndarray) -> float:
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 30:
        return np.nan
    return float(np.corrcoef(x[m], y[m])[0, 1])


# ------------------------------------------------------- costruzione sessioni
def etichetta_sessioni(m1: pd.DataFrame) -> pd.DataFrame:
    """Assegna ogni minuto alla sessione (giornata, notte/giorno) che gli spetta.

    Due passate. La prima individua le GIORNATE DI BORSA vere (almeno
    ``MIN_MINUTI_GIORNO`` minuti fra le 07:00 e le 21:00): sabati, domeniche e
    festivi chiusi spariscono. La seconda costruisce i confini alternati
    07:00/21:00 delle sole giornate vere e ci colloca dentro ogni minuto con una
    ricerca binaria: cosi' la notte del lunedi' comprende davvero tutto il
    fine settimana (venerdi' 21:00 -> lunedi' 07:00, riapertura domenicale
    inclusa) invece di essere spezzata da confini di giorni senza mercato.
    """
    ora = m1.index.hour
    data = m1.index.normalize()

    # --- passata 1: quali date sono giornate di borsa
    dentro = (ora >= ORA_GIORNO) & (ora < ORA_NOTTE)
    minuti = pd.Series(1, index=data[dentro]).groupby(level=0).sum()
    giornate = minuti[minuti >= MIN_MINUTI_GIORNO].index.sort_values()

    # --- passata 2: confini alternati e collocazione dei minuti
    conf07 = giornate + pd.Timedelta(hours=ORA_GIORNO)
    conf21 = giornate + pd.Timedelta(hours=ORA_NOTTE)
    confini = np.empty(2 * len(giornate), dtype="datetime64[ns]")
    confini[0::2] = conf07.tz_localize(None).values
    confini[1::2] = conf21.tz_localize(None).values

    pos = np.searchsorted(confini, m1.index.tz_localize(None).values, side="right")
    # pos dispari -> il minuto sta in [07:00, 21:00) della giornata (pos-1)//2
    # pos pari    -> il minuto sta in [21:00, 07:00) della giornata pos//2
    e_giorno = (pos % 2) == 1
    idx_giornata = np.where(e_giorno, (pos - 1) // 2, pos // 2)
    valido = (pos > 0) & (idx_giornata < len(giornate))

    out = m1.loc[valido].copy()
    out["giornata"] = giornate.values[idx_giornata[valido]]
    out["sessione"] = np.where(e_giorno[valido], "giorno", "notte")
    return out


def tabella_giornaliera(m1: pd.DataFrame) -> pd.DataFrame:
    """Una riga per giornata di borsa con ancoraggi, escursioni e blocchi orari."""
    lab = etichetta_sessioni(m1)
    g = lab.groupby(["giornata", "sessione"])
    agg = g.agg(ultimo=("close", "last"), massimo=("high", "max"),
                minimo=("low", "min"), n=("close", "size")).unstack("sessione")

    t = pd.DataFrame(index=agg.index)
    t["chiusura_giorno"] = agg[("ultimo", "giorno")]   # close 20:59
    t["chiusura_notte"] = agg[("ultimo", "notte")]     # close 06:59
    t["max_notte"] = agg[("massimo", "notte")]
    t["min_notte"] = agg[("minimo", "notte")]
    t["max_giorno"] = agg[("massimo", "giorno")]
    t["min_giorno"] = agg[("minimo", "giorno")]
    t["n_giorno"] = agg[("n", "giorno")]
    t["n_notte"] = agg[("n", "notte")]

    # blocchi orari interni al giorno: chiusura dell'ultimo minuto di ogni ora
    solo_g = lab[lab.sessione == "giorno"]
    ore = solo_g.index.hour
    for h in range(ORA_GIORNO, ORA_NOTTE):
        s = solo_g.close[ore == h].groupby(solo_g.giornata[ore == h]).last()
        t[f"c{h:02d}"] = s.reindex(t.index)

    t = t.dropna(subset=["chiusura_giorno", "chiusura_notte"])
    t = t[(t.n_giorno >= MIN_MINUTI_GIORNO) & (t.n_notte >= MIN_MINUTI_NOTTE)]

    prec = t.chiusura_giorno.shift(1)
    t["giorni_gap"] = t.index.to_series().diff().dt.days
    # una notte con piu' di 4 giorni di stacco e' un ponte di festa: fuori
    t.loc[t.giorni_gap > 4, "giorni_gap"] = np.nan
    valida = t.giorni_gap.notna()

    t["p_partenza_notte"] = prec.where(valida)
    t["r_notte"] = t.chiusura_notte - t.p_partenza_notte
    t["r_giorno"] = t.chiusura_giorno - t.chiusura_notte
    t["r_totale"] = t.r_notte + t.r_giorno
    t["weekend"] = t.giorni_gap >= 2
    t["dow"] = t.index.dayofweek
    t["anno"] = t.index.year
    t["periodo"] = periodo_di(t.anno)

    # prima ora del giorno (07:00-08:00) e resto (08:00-21:00)
    t["r_ora1"] = t["c07"] - t.chiusura_notte
    t["r_resto"] = t.chiusura_giorno - t["c07"]
    t["r_ora12"] = t["c08"] - t.chiusura_notte
    t["r_resto12"] = t.chiusura_giorno - t["c08"]
    t["r_ora13"] = t["c09"] - t.chiusura_notte
    t["r_resto13"] = t.chiusura_giorno - t["c09"]
    # prima ora della sessione americana (12:00-13:00 UTC) e resto
    t["r_ny1"] = t["c12"] - t["c11"]
    t["r_ny_resto"] = t.chiusura_giorno - t["c12"]

    t["esc_notte"] = t.max_notte - t.min_notte
    t["esc_giorno"] = t.max_giorno - t.min_giorno
    return t


def aggiungi_scale(t: pd.DataFrame, m1: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge ATR causale e le versioni normalizzate (bp e unita' di ATR)."""
    atr = daily_atr(m1, 14)
    if atr.index.tz is not None:  # l'indice delle giornate qui e' senza fuso
        atr.index = atr.index.tz_localize(None)
    atr.index = atr.index.astype(t.index.dtype)
    t = t.copy()
    t["atr"] = atr.reindex(t.index).values
    t = t[t.atr.notna() & (t.atr > 0)]
    base = t.p_partenza_notte  # prezzo noto PRIMA della notte: nessun futuro
    for c in ["r_notte", "r_giorno", "r_totale", "r_ora1", "r_resto",
              "r_ora12", "r_resto12", "r_ora13", "r_resto13",
              "r_ny1", "r_ny_resto", "esc_notte", "esc_giorno"]:
        t[c + "_bp"] = 1e4 * t[c] / base
        t[c + "_atr"] = t[c] / t.atr
    t["spread_atr"] = SPREAD_USD / t.atr
    t["swap_bp"] = 1e4 * SWAP_LONG_ONCIA / base
    return t


# ---------------------------------------------------------------- misure (A-H)
def riga_riepilogo(x: pd.Series, xa: pd.Series) -> dict:
    return {
        "n": int(x.notna().sum()),
        "somma_bp": float(x.sum()),
        "media_bp": float(x.mean()),
        "media_atr": float(xa.mean()),
        "t": t_student(xa.values),
        "%pos": float((x > 0).mean() * 100),
    }


def tab_decomposizione(t: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """A) Quanto rendimento nasce di notte e quanto di giorno."""
    righe_anno, righe_per = [], []
    for chiave, gruppo in [("anno", t.groupby("anno")), ("periodo", t.groupby("periodo"))]:
        dest = righe_anno if chiave == "anno" else righe_per
        for k, g in gruppo:
            fer = g[~g.weekend]
            wke = g[g.weekend]
            dest.append({
                chiave: k, "n": len(g),
                "notte_bp": g.r_notte_bp.sum(),
                "  feriale": fer.r_notte_bp.sum(),
                "  weekend": wke.r_notte_bp.sum(),
                "giorno_bp": g.r_giorno_bp.sum(),
                "totale_bp": g.r_totale_bp.sum(),
                "notte/tot%": 100 * g.r_notte_bp.sum() / g.r_totale_bp.sum()
                if g.r_totale_bp.sum() != 0 else np.nan,
            })
    return (pd.DataFrame(righe_anno).set_index("anno"),
            pd.DataFrame(righe_per).set_index("periodo"))


def tab_statistica(t: pd.DataFrame) -> pd.DataFrame:
    """A-bis) Media per giornata, t di Student, quota di giornate positive."""
    righe = []
    for per, g in t.groupby("periodo"):
        for nome, sel in [("notte tutte", g),
                          ("notte feriale", g[~g.weekend]),
                          ("notte weekend", g[g.weekend]),
                          ("giorno", g)]:
            col = "r_notte" if nome.startswith("notte") else "r_giorno"
            r = riga_riepilogo(sel[col + "_bp"], sel[col + "_atr"])
            r.update({"periodo": per, "finestra": nome})
            righe.append(r)
    return pd.DataFrame(righe).set_index(["periodo", "finestra"])


def tab_costi(t: pd.DataFrame) -> pd.DataFrame:
    """B) Il rendimento notturno regge il costo di tenere aperto?"""
    righe = []
    for per, g in t.groupby("periodo"):
        fer = g[~g.weekend]
        righe.append({
            "periodo": per,
            "notte_media_bp": fer.r_notte_bp.mean(),
            "swap_long_bp": fer.swap_bp.mean(),
            "netto_long_bp": fer.r_notte_bp.mean() + fer.swap_bp.mean(),
            "netto_short_bp": -fer.r_notte_bp.mean() + fer.swap_bp.mean(),
            "spread_bp": 1e4 * SPREAD_USD / fer.p_partenza_notte.mean(),
            "spread_atr": fer.spread_atr.mean(),
        })
    return pd.DataFrame(righe).set_index("periodo")


def tab_escursione(t: pd.DataFrame) -> pd.DataFrame:
    """C) Dove sta il MOVIMENTO (non il rendimento): escursione delle finestre."""
    righe = []
    for per, g in t.groupby("periodo"):
        fer = g[~g.weekend]
        righe.append({
            "periodo": per, "n": len(fer),
            "esc_notte_bp": fer.esc_notte_bp.median(),
            "esc_giorno_bp": fer.esc_giorno_bp.median(),
            "esc_notte_atr": fer.esc_notte_atr.median(),
            "esc_giorno_atr": fer.esc_giorno_atr.median(),
            "quota_notte%": 100 * (fer.esc_notte / (fer.esc_notte + fer.esc_giorno)).median(),
            "|r|notte_atr": fer.r_notte_atr.abs().median(),
            "|r|giorno_atr": fer.r_giorno_atr.abs().median(),
        })
    return pd.DataFrame(righe).set_index("periodo")


def analisi_predittiva(t: pd.DataFrame, pred: str, targ: str,
                       etichetta: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """D/E) La variabile ``pred`` (nota prima) predice ``targ``?

    Restituisce (sintesi per periodo, quintili per periodo). Tutto in unita' di
    ATR, quindi confrontabile fra 2009 e 2026. Il "segui" e' la forma
    tradeable: media di sign(pred)*targ, lorda e al netto dello spread.
    """
    sint, quint = [], []
    for per, g in t.groupby("periodo"):
        x = g[pred + "_atr"].values
        y = g[targ + "_atr"].values
        m = np.isfinite(x) & np.isfinite(y)
        x, y, sp = x[m], y[m], g.spread_atr.values[m]
        segui = np.sign(x) * y
        sint.append({
            "periodo": per, "n": int(m.sum()), "coppia": etichetta,
            "corr": corr(x, y),
            "acc_segno%": 100 * float((np.sign(x) == np.sign(y)).mean()),
            "segui_atr": float(segui.mean()),
            "segui_t": t_student(segui),
            "segui_netto_atr": float((segui - sp).mean()),
        })
        q = pd.qcut(pd.Series(x), 5, labels=["Q1 giu", "Q2", "Q3", "Q4", "Q5 su"])
        d = pd.DataFrame({"q": q.values, "y": y, "x": x})
        for k, gg in d.groupby("q", observed=True):
            quint.append({
                "periodo": per, "coppia": etichetta, "quintile": k,
                "n": len(gg), "pred_medio_atr": gg.x.mean(),
                "targ_medio_atr": gg.y.mean(), "t": t_student(gg.y.values),
                "%targ_pos": 100 * float((gg.y > 0).mean()),
            })
    return (pd.DataFrame(sint).set_index(["coppia", "periodo"]),
            pd.DataFrame(quint).set_index(["coppia", "periodo", "quintile"]))


def placebo_accoppiamento(t: pd.DataFrame, pred: str, targ: str,
                          etichetta: str, seme: int = 7) -> pd.DataFrame:
    """Controllo (regola 7 adattata): la stessa misura su accoppiamenti FINTI.

    Non c'e' nessun livello da spostare, ma c'e' un accoppiamento da rompere:
    si abbina il predittore di una giornata al bersaglio di un'ALTRA giornata
    scelta a caso. Se il numero vero non esce dalla nuvola dei numeri finti,
    non e' la notte (o la prima ora) a lavorare: e' rumore.
    """
    rng = np.random.default_rng(seme)
    righe = []
    for per, g in t.groupby("periodo"):
        x = g[pred + "_atr"].values
        y = g[targ + "_atr"].values
        m = np.isfinite(x) & np.isfinite(y)
        x, y = x[m], y[m]
        vero_c = corr(x, y)
        vero_s = float((np.sign(x) * y).mean())
        finti_c = np.empty(N_PLACEBO)
        finti_s = np.empty(N_PLACEBO)
        for i in range(N_PLACEBO):
            yp = rng.permutation(y)
            finti_c[i] = np.corrcoef(x, yp)[0, 1]
            finti_s[i] = (np.sign(x) * yp).mean()
        righe.append({
            "coppia": etichetta, "periodo": per, "n": len(x),
            "corr_vera": vero_c,
            "corr_finta_p5": np.quantile(finti_c, 0.05),
            "corr_finta_p95": np.quantile(finti_c, 0.95),
            "p_bilat_corr": float((np.abs(finti_c) >= abs(vero_c)).mean()),
            "segui_vero": vero_s,
            "p_bilat_segui": float((np.abs(finti_s) >= abs(vero_s)).mean()),
        })
    return pd.DataFrame(righe).set_index(["coppia", "periodo"])


def tab_memoria(t: pd.DataFrame) -> pd.DataFrame:
    """F) Il segno di ieri predice quello di oggi? Matrice dei ritardi 1."""
    righe = []
    for per, g in t.groupby("periodo"):
        g = g.sort_index()
        # solo coppie di giornate consecutive vere (nessun salto di festivita')
        cons = g.giorni_gap.notna().values
        for pred, targ, nome in [
            ("r_giorno_atr", "r_giorno_atr", "giorno(D-1) -> giorno(D)"),
            ("r_giorno_atr", "r_notte_atr", "giorno(D-1) -> notte(D)"),
            ("r_notte_atr", "r_notte_atr", "notte(D-1) -> notte(D)"),
            ("r_totale_atr", "r_totale_atr", "totale(D-1)-> totale(D)"),
            ("r_giorno_atr", "r_totale_atr", "giorno(D-1) -> totale(D)"),
        ]:
            x = g[pred].shift(1).values
            y = g[targ].values
            m = np.isfinite(x) & np.isfinite(y) & cons
            xs, ys = x[m], y[m]
            segui = np.sign(xs) * ys
            righe.append({
                "periodo": per, "relazione": nome, "n": int(m.sum()),
                "corr": corr(xs, ys),
                "acc_segno%": 100 * float((np.sign(xs) == np.sign(ys)).mean()),
                "segui_atr": float(segui.mean()), "t": t_student(segui),
            })
    return pd.DataFrame(righe).set_index(["relazione", "periodo"])


def tab_rottura_notte(t: pd.DataFrame, m1: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """G) Il giorno rompe il range della notte? E cosa succede DOPO la rottura.

    Misura descrittiva, non una regola: per ogni giornata si guarda se la
    sessione 07:00-21:00 supera il massimo o il minimo della notte, chi dei due
    arriva prima, e - a partire dalla CHIUSURA del minuto che rompe (rule 1) -
    quanto si guadagna fino alle 21:00 e quali escursioni favorevole/avversa si
    incontrano. Se lo stesso minuto rompe entrambi i lati la giornata e'
    marcata "ambigua" ed esclusa dalle misure direzionali.
    """
    lab = etichetta_sessioni(m1)
    solo_g = lab[lab.sessione == "giorno"]
    liv = t[["max_notte", "min_notte", "atr", "chiusura_giorno"]]

    righe = []
    for giorno, blocco in solo_g.groupby("giornata", sort=True):
        if giorno not in liv.index:
            continue
        hi, lo, atr, cl = liv.loc[giorno, ["max_notte", "min_notte", "atr", "chiusura_giorno"]]
        h = blocco.high.values
        l = blocco.low.values
        c = blocco.close.values
        su = np.flatnonzero(h > hi)
        giu = np.flatnonzero(l < lo)
        i_su = su[0] if len(su) else 10**9
        i_giu = giu[0] if len(giu) else 10**9
        rec = {"giornata": giorno, "atr": atr,
               "rompe_su": len(su) > 0, "rompe_giu": len(giu) > 0,
               "ampiezza_notte_atr": (hi - lo) / atr}
        if i_su == 10**9 and i_giu == 10**9:
            rec["primo"] = "nessuno"
        elif i_su == i_giu:
            rec["primo"] = "ambiguo"
        else:
            k = min(i_su, i_giu)
            direzione = 1 if i_su < i_giu else -1
            rec["primo"] = "su" if direzione == 1 else "giu"
            ing = c[k]                      # chiusura del minuto che rompe
            rec["ora_rottura"] = blocco.index[k].hour
            rec["r_fino_chiusura_atr"] = direzione * (cl - ing) / atr
            if k + 1 < len(c):
                fut_h, fut_l = h[k + 1:], l[k + 1:]
                if direzione == 1:
                    rec["mfe_atr"] = (fut_h.max() - ing) / atr
                    rec["mae_atr"] = (ing - fut_l.min()) / atr
                else:
                    rec["mfe_atr"] = (ing - fut_l.min()) / atr
                    rec["mae_atr"] = (fut_h.max() - ing) / atr
        righe.append(rec)

    d = pd.DataFrame(righe).set_index("giornata")
    d["anno"] = d.index.year
    d["periodo"] = periodo_di(d.anno)
    d["spread_atr"] = SPREAD_USD / d.atr

    sint = []
    for per, g in d.groupby("periodo"):
        n = len(g)
        dir_ok = g[g.primo.isin(["su", "giu"])]
        sint.append({
            "periodo": per, "n": n,
            "ampiezza_notte_atr": g.ampiezza_notte_atr.median(),
            "%solo_su": 100 * ((g.rompe_su) & (~g.rompe_giu)).mean(),
            "%solo_giu": 100 * ((~g.rompe_su) & (g.rompe_giu)).mean(),
            "%entrambi": 100 * ((g.rompe_su) & (g.rompe_giu)).mean(),
            "%nessuno": 100 * (g.primo == "nessuno").mean(),
            "%ambiguo": 100 * (g.primo == "ambiguo").mean(),
            "ora_med_rottura": dir_ok.ora_rottura.median(),
            "r_chius_atr": dir_ok.r_fino_chiusura_atr.mean(),
            "r_netto_atr": (dir_ok.r_fino_chiusura_atr - dir_ok.spread_atr).mean(),
            "t": t_student(dir_ok.r_fino_chiusura_atr.values),
            "mfe_med_atr": dir_ok.mfe_atr.median(),
            "mae_med_atr": dir_ok.mae_atr.median(),
        })
    return d, pd.DataFrame(sint).set_index("periodo")


def tab_dow(t: pd.DataFrame) -> pd.DataFrame:
    """H) Struttura settimanale di notte e giorno."""
    righe = []
    for per, g in t.groupby("periodo"):
        for d, gg in g.groupby("dow"):
            if d > 4:
                continue
            righe.append({
                "periodo": per, "giorno": GIORNI[d], "n": len(gg),
                "notte_bp": gg.r_notte_bp.mean(),
                "notte_atr": gg.r_notte_atr.mean(),
                "notte_t": t_student(gg.r_notte_atr.values),
                "giorno_bp": gg.r_giorno_bp.mean(),
                "giorno_atr": gg.r_giorno_atr.mean(),
                "giorno_t": t_student(gg.r_giorno_atr.values),
            })
    return pd.DataFrame(righe).set_index(["periodo", "giorno"])


def tab_anni_positivi(t: pd.DataFrame) -> pd.DataFrame:
    """A-ter) Quanti anni chiudono in positivo: la costanza, non la somma."""
    a = t.groupby(["periodo", "anno"])[["r_notte_bp", "r_giorno_bp", "r_totale_bp"]].sum()
    righe = []
    for per, g in a.groupby(level=0):
        righe.append({
            "periodo": per, "anni": len(g),
            "notte_pos": int((g.r_notte_bp > 0).sum()),
            "giorno_pos": int((g.r_giorno_bp > 0).sum()),
            "totale_pos": int((g.r_totale_bp > 0).sum()),
        })
    return pd.DataFrame(righe).set_index("periodo")


def tab_ore(m1: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    """I) Profilo orario del rendimento: dove esattamente si accumula la deriva.

    Ancoraggio: ultimo close di ogni ora piena. Il rendimento dell'ora h e'
    close(fine di h) - close(fine di h-1), attribuito all'ora h. Si tengono
    solo le coppie di ancoraggi distanti esattamente un'ora, quindi lo stacco
    giornaliero e il fine settimana NON entrano (sono misurati a parte).
    L'ora 21 in inverno e' aperta e l'ora 22 no (e viceversa in estate): la
    colonna ``n`` mostra la copertura reale, non va letta come uniforme.
    """
    ore = m1.index.floor("h")
    anc = m1.close.groupby(ore).last()
    idx = anc.index
    passo = idx.to_series().diff()
    r = anc.diff()
    base = anc.shift(1)
    ok = (passo == pd.Timedelta(hours=1)) & r.notna()

    d = pd.DataFrame({"r": r[ok], "base": base[ok]})
    d["ora"] = d.index.hour
    d["giornata"] = d.index.normalize()
    scala = t[["atr"]].copy()
    scala.index = pd.DatetimeIndex(scala.index)
    if d.index.tz is not None:
        d["giornata"] = d["giornata"].dt.tz_localize(None)
    d["giornata"] = d["giornata"].astype(scala.index.dtype)
    d["atr"] = scala.atr.reindex(d.giornata).ffill().values
    d = d[d.atr.notna() & (d.atr > 0)]
    d["bp"] = 1e4 * d.r / d.base
    d["atr_u"] = d.r / d.atr
    d["anno"] = d.index.year
    d["periodo"] = periodo_di(d["anno"])

    out = []
    for ora, g in d.groupby("ora"):
        riga = {"ora": f"{ora:02d}-{(ora + 1) % 24:02d}",
                "fase": "notte" if (ora >= ORA_NOTTE or ora < ORA_GIORNO) else "giorno"}
        for per in PERIODI:
            gg = g[g.periodo == per]
            riga[f"n{per[2:4]}"] = len(gg)
            riga[f"bp{per[2:4]}"] = gg.bp.mean() if len(gg) else np.nan
            # milli-ATR: la stessa media in unita' di volatilita' (x1000)
            riga[f"mA{per[2:4]}"] = 1e3 * gg.atr_u.mean() if len(gg) else np.nan
            riga[f"t{per[2:4]}"] = t_student(gg.atr_u.values) if len(gg) else np.nan
        out.append(riga)
    return pd.DataFrame(out).set_index("ora")


def ancore_notturne(m1: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    """Chiusure orarie DENTRO la notte (21,22,23,00..06), una riga per giornata.

    Si guardano solo i minuti nelle 12 ore che precedono le 07:00: cosi' per il
    lunedi' si prende la sera di DOMENICA e non la coda del venerdi'.
    """
    lab = etichetta_sessioni(m1)
    notte = lab[lab.sessione == "notte"].copy()
    fine = pd.DatetimeIndex(notte.giornata) + pd.Timedelta(hours=ORA_GIORNO)
    idx = notte.index.tz_localize(None) if notte.index.tz is not None else notte.index
    notte = notte[idx.values >= (fine - pd.Timedelta(hours=12)).values]
    ore = (notte.index.tz_localize(None) if notte.index.tz is not None
           else notte.index).hour
    fuori = pd.DataFrame(index=t.index)
    for h in list(range(ORA_NOTTE, 24)) + list(range(0, ORA_GIORNO)):
        s = notte.close[ore == h].groupby(notte.giornata[ore == h]).last()
        fuori[f"n{h:02d}"] = s.reindex(fuori.index)
    return fuori


def tab_finestre_notturne(m1: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    """K) Finestre notturne "pulite": dentro la sessione, senza stacco.

    Chi entra DOPO la riapertura ed esce entro le 07:00 non attraversa il
    rollover delle 21:00 e quindi NON paga swap: paga solo lo spread. Sono le
    uniche finestre notturne il cui costo e' davvero 0,30 $. Il rendimento e'
    riportato lordo, in bp e in unita' di ATR, e netto dello spread in ATR.
    """
    a = ancore_notturne(m1, t)
    a["c07"] = t.chiusura_notte
    finestre = [("22->07", "n22", "c07"), ("23->07", "n23", "c07"),
                ("00->07", "n00", "c07"), ("23->03", "n23", "n03"),
                ("03->07", "n03", "c07"), ("01->06", "n01", "n06")]
    righe = []
    for nome, da, a_ in finestre:
        r = (a[a_] - a[da])
        d = pd.DataFrame({"r": r, "base": a[da], "atr": t.atr,
                          "anno": t.anno, "periodo": t.periodo,
                          "weekend": t.weekend}).dropna()
        for per, g in d.groupby("periodo"):
            bp = 1e4 * g.r / g.base
            ua = g.r / g.atr
            anni = (g.assign(bp=bp).groupby("anno").bp.sum() > 0)
            righe.append({
                "finestra": nome, "periodo": per, "n": len(g),
                "media_bp": bp.mean(), "media_atr": ua.mean(),
                "t": t_student(ua.values), "%pos": 100 * (g.r > 0).mean(),
                "netto_atr": (ua - SPREAD_USD / g.atr).mean(),
                "anni+": f"{int(anni.sum())}/{len(anni)}",
            })
    return pd.DataFrame(righe).set_index(["finestra", "periodo"])


def tab_stacco(m1: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    """J) Controllo di artefatto: la deriva notturna e' tutta nello STACCO?

    Ogni notte feriale contiene l'ora di chiusura giornaliera del mercato. La
    si individua come il salto piu' lungo fra minuti consecutivi dentro la
    sessione notturna e si scompone la notte in tre pezzi:
        pre    = 21:00 -> ultimo prezzo prima dello stacco (non nullo solo in
                 inverno, quando il mercato chiude alle 22:00)
        stacco = ultimo prezzo prima -> primo prezzo dopo la riapertura
        post   = riapertura -> 07:00
    Se la deriva stesse quasi tutta nello STACCO sarebbe un candidato artefatto
    (serie BID, spread allargato alla riapertura) e non un fatto di mercato.
    """
    lab = etichetta_sessioni(m1)
    notte = lab[lab.sessione == "notte"]
    feriali = set(t.index[~t.weekend])
    # istante dell'ancora delle 21:00 della giornata precedente
    inizio = pd.Series((t.index - pd.Timedelta(days=1)) + pd.Timedelta(hours=ORA_NOTTE),
                       index=t.index)

    righe = []
    for giorno, blocco in notte.groupby("giornata", sort=True):
        if giorno not in feriali:
            continue
        # la catena parte dall'ancora delle 21:00 (ultimo close del giorno
        # precedente): in estate il mercato chiude proprio li' e lo stacco cade
        # sul confine, in inverno chiude un'ora dopo e lo stacco e' interno.
        p0 = t.p_partenza_notte.loc[giorno]
        if not np.isfinite(p0):
            continue
        idx = blocco.index
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        ts = np.concatenate([np.array([inizio.loc[giorno].to_datetime64()],
                                      dtype="datetime64[ns]"),
                             idx.values.astype("datetime64[ns]")])
        c = np.concatenate([[p0], blocco.close.values])
        salti = np.diff(ts).astype("timedelta64[m]").astype(float)
        k = int(np.argmax(salti)) + 1
        if salti[k - 1] < 30:
            continue
        righe.append({
            "giornata": giorno, "stacco_min": salti[k - 1],
            "pre": c[k - 1] - p0,
            "stacco": c[k] - c[k - 1],
            "post": t.chiusura_notte.loc[giorno] - c[k],
            "base": p0, "atr": t.atr.loc[giorno],
        })
    d = pd.DataFrame(righe).set_index("giornata")
    d["periodo"] = periodo_di(pd.Series(d.index.year, index=d.index))

    out = []
    for per, g in d.groupby("periodo"):
        riga = {"periodo": per, "n": len(g), "stacco_min_med": g.stacco_min.median()}
        for pezzo in ["pre", "stacco", "post"]:
            riga[f"{pezzo}_bp"] = (1e4 * g[pezzo] / g.base).mean()
            riga[f"{pezzo}_t"] = t_student((g[pezzo] / g.atr).values)
        riga["somma_bp"] = sum(riga[f"{p}_bp"] for p in ["pre", "stacco", "post"])
        out.append(riga)
    return pd.DataFrame(out).set_index("periodo")


def tab_volatilita_prevista(t: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """L) La notte non predice la DIREZIONE del giorno: predice l'AMPIEZZA?

    Tutto e' gia' diviso per l'ATR causale, quindi una correlazione residua e'
    informazione che la notte AGGIUNGE all'ATR, non l'ATR stesso.
    """
    sint, quint = [], []
    for per, g in t.groupby("periodo"):
        en, eg = g.esc_notte_atr.values, g.esc_giorno_atr.values
        rn = np.abs(g.r_notte_atr.values)
        sint.append({
            "periodo": per, "n": len(g),
            "corr esc_notte~esc_giorno": corr(en, eg),
            "corr |r_notte|~esc_giorno": corr(rn, eg),
            "corr esc_notte~|r_giorno|": corr(en, np.abs(g.r_giorno_atr.values)),
        })
        q = pd.qcut(pd.Series(en), 5, labels=["Q1 stretta", "Q2", "Q3", "Q4", "Q5 larga"])
        d = pd.DataFrame({"q": q.values, "en": en, "eg": eg})
        for k, gg in d.groupby("q", observed=True):
            quint.append({"periodo": per, "quintile": k, "n": len(gg),
                          "esc_notte_atr": gg.en.median(),
                          "esc_giorno_atr_med": gg.eg.median()})
    return (pd.DataFrame(sint).set_index("periodo"),
            pd.DataFrame(quint).set_index(["periodo", "quintile"]))


# ------------------------------------------------------------------------ main
def main() -> None:
    os.makedirs(USCITA, exist_ok=True)
    m1 = load_m1(os.path.join(REPO, "data", "XAUUSD_M1"))
    t = aggiungi_scale(tabella_giornaliera(m1), m1)
    t.to_parquet(os.path.join(USCITA, "giornate.parquet"))

    print("\n=== 0. COPERTURA ===")
    cop = t.groupby("periodo").agg(
        giornate=("r_giorno", "size"),
        con_notte=("r_notte", "count"),
        notti_weekend=("weekend", "sum"),
        da_=("anno", "min"), a_=("anno", "max"))
    print(cop)
    print("controllo di identita' (regola 6): max |notte+giorno - (c21 - c21 prec)| =",
          f"{(t.r_totale - (t.chiusura_giorno - t.p_partenza_notte)).abs().max():.2e} $")

    per_anno, per_per = tab_decomposizione(t)
    print("\n=== A. DOVE NASCE IL RENDIMENTO (somme in bp, 1 bp = 0,01%) ===")
    print(per_per)
    print("\n--- per anno ---")
    print(per_anno)

    print("\n=== A-bis. MEDIA PER GIORNATA, t DI STUDENT, QUOTA POSITIVE ===")
    print(tab_statistica(t))

    print("\n=== A-ter. COSTANZA: ANNI CHIUSI IN POSITIVO ===")
    print(tab_anni_positivi(t))

    print("\n=== B. IL COSTO DI TENERE APERTO LA NOTTE (bp per notte feriale) ===")
    print(tab_costi(t))

    print("\n=== C. DOVE STA IL MOVIMENTO (mediane, notti feriali) ===")
    print(tab_escursione(t))

    coppie = [
        ("r_notte", "r_giorno", "notte -> giorno"),
        ("r_ora1", "r_resto", "ora1 (07-08) -> resto (08-21)"),
        ("r_ora12", "r_resto12", "ore1-2 (07-09) -> resto (09-21)"),
        ("r_ora13", "r_resto13", "ore1-3 (07-10) -> resto (10-21)"),
        ("r_ny1", "r_ny_resto", "ora NY (12-13) -> resto (13-21)"),
        ("r_notte", "r_ora1", "notte -> ora1 (07-08)"),
    ]
    sint_all, quint_all = [], []
    for p, q, nome in coppie:
        s, qq = analisi_predittiva(t, p, q, nome)
        sint_all.append(s)
        quint_all.append(qq)
    sint = pd.concat(sint_all)
    quint = pd.concat(quint_all)
    print("\n=== D/E. COSA PREDICE COSA (unita' di ATR; 'segui' = sign(pred)*targ) ===")
    print(sint)
    quint.to_parquet(os.path.join(USCITA, "quintili.parquet"))
    print("\n--- quintili delle due coppie principali ---")
    print(quint.loc[["notte -> giorno", "ora1 (07-08) -> resto (08-21)"]])

    # placebo sulle due coppie principali e sull'unica relazione che ha lo
    # stesso segno nei due periodi (notte -> prima ora)
    plac = pd.concat([placebo_accoppiamento(t, *coppie[i]) for i in (0, 1, 5)])
    print("\n=== D-bis. CONTROLLO SU ACCOPPIAMENTI FINTI (400 permutazioni) ===")
    print(plac)

    print("\n=== F. MEMORIA DA UN GIORNO ALL'ALTRO ===")
    print(tab_memoria(t))

    dett, sint_rot = tab_rottura_notte(t, m1)
    dett.to_parquet(os.path.join(USCITA, "rotture_notte.parquet"))
    print("\n=== G. IL GIORNO ROMPE IL RANGE DELLA NOTTE? ===")
    print(sint_rot)

    print("\n=== H. STRUTTURA SETTIMANALE ===")
    print(tab_dow(t))

    print("\n=== I. PROFILO ORARIO (media per ora, bp; t su unita' di ATR) ===")
    print(tab_ore(m1, t))

    print("\n=== J. LA DERIVA NOTTURNA E' TUTTA NELLO STACCO? (notti feriali) ===")
    print(tab_stacco(m1, t))

    print("\n=== K. FINESTRE NOTTURNE SENZA ROLLOVER (nessuno swap, solo spread) ===")
    print(tab_finestre_notturne(m1, t))

    lv, lq = tab_volatilita_prevista(t)
    print("\n=== L. LA NOTTE PREDICE L'AMPIEZZA DEL GIORNO? (tutto gia' su ATR) ===")
    print(lv)
    print(lq)

    print(f"\n[dettaglio in {USCITA}]")


if __name__ == "__main__":
    main()
