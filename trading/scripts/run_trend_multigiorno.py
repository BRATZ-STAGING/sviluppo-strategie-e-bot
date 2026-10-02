"""Trend following multi-giorno sull'oro (protocollo registrato).

Implementa alla lettera ``docs/trend-multigiorno-registrazione.md`` (02/10/2026)
sulle candele D1 BID 2009-2026 (``docs/studies/dati/XAUUSD_D1_2009-2026.parquet``):

- F1 TSMOM: all'ultima chiusura del mese, segno del rendimento a 252 sedute,
  posizione per il mese successivo, nessuno stop;
- F2 Donchian 55/20 con stop 1R;
- F3 incrocio medie 50/200 con stop 1R.

Decisione alla chiusura D1, esecuzione all'apertura del giorno dopo.
1R = 2 x ATR20 (True Range classico, media semplice a 20) alla decisione.
Stop intraday eseguito al livello, o all'apertura se il gap lo supera.

Interpretazioni scelte sui punti non specificati (la piu' prudente, dichiarata
anche nell'output):

- notti di swap: un rollover per ogni giorno feriale (lun-ven) dal giorno di
  entrata (incluso) al giorno di uscita (escluso); mercoledi' x3, venerdi'
  conta 1 (il x3 del mercoledi' copre gia' il fine settimana). Fra due sedute
  consecutive e' esattamente "un rollover fra una seduta e la successiva";
  i giorni feriali assenti nei dati (festivi, sedute parziali escluse) si
  contano comunque, come fa il broker. Riscalato col prezzo di chiusura del
  giorno del rollover (ultima chiusura nota se il giorno manca);
- spread: un round trip per operazione, il maggiore fra l'anno di entrata e
  quello di uscita;
- anno di un'operazione = anno della data di ENTRATA (anche per le meta');
- posizione ancora aperta alla fine dei dati: chiusa all'ultima chiusura;
- anni positivi: positivi fra gli anni con >= 2 operazioni, richiesti >= 2/3;
  per TSMOM "tutti" letto come TUTTI gli anni positivi (lettura severa);
  si stampa anche l'altra lettura (2/3 su tutti gli anni);
- placebo: stesse date e stessi prezzi di entrata e uscita di ogni operazione
  reale, direzione a caso (+-1 con probabilita' 1/2), spread uguale, swap
  ricalcolato con la direzione del placebo; generatore
  ``np.random.default_rng(20261002)`` ricreato per ogni famiglia;
  p = quota di placebo con R netto totale >= reale (definizione del
  protocollo, senza +1);
- benchmark sempre-long: le stesse date mensili di F1, tutte long, stessi
  costi e stesso R.

Uso: python run_trend_multigiorno.py
Dettaglio operazioni in docs/studies/dati/trend_multigiorno_<famiglia>.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
sys.path.insert(0, os.path.join(QUI, ".."))

from verifica_bot import SPREAD                                  # noqa: E402

ROOT = os.path.abspath(os.path.join(QUI, "..", ".."))
DATI = os.path.join(ROOT, "docs", "studies", "dati")
FILE_D1 = os.path.join(DATI, "XAUUSD_D1_2009-2026.parquet")

SPREAD_VECCHIO = 0.40          # 2009-2019
SWAP_LONG = -0.715             # $/oncia/notte al prezzo di riferimento
SWAP_SHORT = 0.325
PREZZO_RIF = 4156.98
SEED = 20261002
N_PLACEBO = 500
MESI_TSMOM = 252
DONCHIAN_IN, DONCHIAN_OUT = 55, 20
MEDIA_BREVE, MEDIA_LUNGA = 50, 200
ATR_N = 20
R_MULT = 2.0


# --------------------------------------------------------------------------
# indicatori (tutti causali: il valore in i usa solo le candele <= i)
# --------------------------------------------------------------------------

def atr20(df: pd.DataFrame, n: int = ATR_N) -> pd.Series:
    """ATR con True Range classico e media semplice a n."""
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - prev).abs(),
                    (df["low"] - prev).abs()], axis=1).max(axis=1)
    tr.iloc[0] = df["high"].iloc[0] - df["low"].iloc[0]
    return tr.rolling(n, min_periods=n).mean()


def spread_anno(anno: int) -> float:
    return SPREAD_VECCHIO if anno < 2020 else SPREAD.get(anno, SPREAD_VECCHIO)


# --------------------------------------------------------------------------
# simulazione
# --------------------------------------------------------------------------

def _operazione(fam, dec, ent, usc, d, p_in, p_out, r, stop, motivo, date):
    return dict(famiglia=fam, data_decisione=date[dec], data_entrata=date[ent],
                data_uscita=date[usc], direzione=int(d), prezzo_entrata=p_in,
                prezzo_uscita=p_out, R_dollari=r, stop=stop, motivo=motivo)


def simula_regole(df, entra_long, entra_short, esci_long, esci_short,
                  famiglia, con_stop=True):
    """Motore comune F2/F3: una posizione alla volta.

    Ordine dentro la seduta i: (1) apertura: si eseguono gli ordini decisi
    alla chiusura di i-1 (prima l'uscita, poi l'eventuale entrata);
    (2) stop intraday (gap oltre lo stop -> apertura, altrimenti al livello);
    (3) chiusura: nuove decisioni. Se nella seduta si tocca lo stop, lo stop
    vale e il segnale di chiusura di quella seduta trova la posizione chiusa.
    """
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    atr = atr20(df).to_numpy(float)
    date = df.index
    n = len(df)
    ops = []
    pos, stop, p_in, r, i_ent, i_dec = 0, np.nan, np.nan, np.nan, -1, -1
    ord_uscita, ord_entrata, r_ord, dec_ord = False, 0, np.nan, -1
    for i in range(n):
        # (1) apertura
        if ord_uscita and pos != 0:
            ops.append(_operazione(famiglia, i_dec, i_ent, i, pos, p_in, o[i],
                                   r, stop, "segnale", date))
            pos = 0
        ord_uscita = False
        if ord_entrata != 0:
            pos, p_in, r, i_ent, i_dec = ord_entrata, o[i], r_ord, i, dec_ord
            stop = p_in - pos * r if con_stop else np.nan
            ord_entrata = 0
        # (2) stop intraday
        if pos != 0 and con_stop:
            colpito, px = False, np.nan
            if pos > 0:
                if o[i] <= stop:
                    colpito, px = True, o[i]
                elif lo[i] <= stop:
                    colpito, px = True, stop
            else:
                if o[i] >= stop:
                    colpito, px = True, o[i]
                elif h[i] >= stop:
                    colpito, px = True, stop
            if colpito:
                ops.append(_operazione(famiglia, i_dec, i_ent, i, pos, p_in, px,
                                       r, stop, "stop", date))
                pos = 0
        # (3) chiusura: decisioni da eseguire all'apertura di i+1
        if i == n - 1:
            break
        if pos > 0 and esci_long[i]:
            ord_uscita = True
        elif pos < 0 and esci_short[i]:
            ord_uscita = True
        piatto = pos == 0 or ord_uscita
        if piatto and np.isfinite(atr[i]) and atr[i] > 0:
            if entra_long[i]:
                ord_entrata, r_ord, dec_ord = 1, R_MULT * atr[i], i
            elif entra_short[i]:
                ord_entrata, r_ord, dec_ord = -1, R_MULT * atr[i], i
    if pos != 0:
        ops.append(_operazione(famiglia, i_dec, i_ent, n - 1, pos, p_in, c[-1],
                               r, stop, "fine_dati", date))
    return pd.DataFrame(ops)


def segnali_donchian(df):
    """Entrata: chiusura oltre max/min delle 55 sedute PRECEDENTI; uscita 20."""
    c = df["close"]
    max55 = df["high"].shift(1).rolling(DONCHIAN_IN, min_periods=DONCHIAN_IN).max()
    min55 = df["low"].shift(1).rolling(DONCHIAN_IN, min_periods=DONCHIAN_IN).min()
    max20 = df["high"].shift(1).rolling(DONCHIAN_OUT, min_periods=DONCHIAN_OUT).max()
    min20 = df["low"].shift(1).rolling(DONCHIAN_OUT, min_periods=DONCHIAN_OUT).min()
    el = (c > max55).to_numpy()
    es = (c < min55).to_numpy()
    xl = (c < min20).to_numpy()
    xs = (c > max20).to_numpy()
    return el, es, xl, xs


def segnali_medie(df):
    c = df["close"]
    m50 = c.rolling(MEDIA_BREVE, min_periods=MEDIA_BREVE).mean()
    m200 = c.rolling(MEDIA_LUNGA, min_periods=MEDIA_LUNGA).mean()
    sopra = m50 > m200
    sotto = m50 < m200
    valido = m50.notna() & m200.notna() & m50.shift(1).notna() & m200.shift(1).notna()
    su = (valido & sopra & (m50.shift(1) <= m200.shift(1))).to_numpy()
    giu = (valido & sotto & (m50.shift(1) >= m200.shift(1))).to_numpy()
    return su, giu, giu, su


def simula_f2(df):
    el, es, xl, xs = segnali_donchian(df)
    return simula_regole(df, el, es, xl, xs, "F2_donchian")


def simula_f3(df):
    su, giu, xl, xs = segnali_medie(df)
    return simula_regole(df, su, giu, xl, xs, "F3_medie")


def fine_mese(df):
    """Indici delle ultime sedute del mese (confermate dalla seduta dopo)."""
    m = df.index.month.to_numpy()
    idx = np.where(m[:-1] != m[1:])[0]
    return idx


def direzioni_tsmom(df):
    """Serie (indice = seduta di fine mese) della direzione decisa."""
    c = df["close"].to_numpy(float)
    out = {}
    for i in fine_mese(df):
        if i >= MESI_TSMOM:
            out[df.index[i]] = 1 if c[i] / c[i - MESI_TSMOM] - 1 > 0 else -1
    return pd.Series(out, dtype=int)


def simula_f1(df, sempre_long=False, famiglia="F1_tsmom"):
    o = df["open"].to_numpy(float)
    c = df["close"].to_numpy(float)
    atr = atr20(df).to_numpy(float)
    date = df.index
    n = len(df)
    fm = [i for i in fine_mese(df) if i >= MESI_TSMOM and np.isfinite(atr[i])]
    ops = []
    for k, i in enumerate(fm):
        d = 1 if (sempre_long or c[i] / c[i - MESI_TSMOM] - 1 > 0) else -1
        ent = i + 1
        if k + 1 < len(fm):
            usc, px, mot = fm[k + 1] + 1, o[fm[k + 1] + 1], "fine_mese"
        else:
            usc, px, mot = n - 1, c[-1], "fine_dati"
        ops.append(_operazione(famiglia, i, ent, usc, d, o[ent], px,
                               R_MULT * atr[i], np.nan, mot, date))
    return pd.DataFrame(ops)


# --------------------------------------------------------------------------
# costi
# --------------------------------------------------------------------------

def fattori_swap(df):
    """Giorni feriali e somma cumulata dei fattori di rollover.

    fattore(giorno) = moltiplicatore (3 il mercoledi', 1 altrimenti) x
    chiusura del giorno / PREZZO_RIF. cum[k] = somma dei fattori dei giorni
    feriali < giorni[k].
    """
    giorni = pd.bdate_range(df.index[0].tz_localize(None).normalize(),
                            df.index[-1].tz_localize(None).normalize())
    chiu = df["close"].copy()
    chiu.index = chiu.index.tz_localize(None).normalize()
    chiu = chiu.reindex(giorni).ffill()
    molt = np.where(giorni.dayofweek == 2, 3.0, 1.0)
    f = molt * chiu.to_numpy(float) / PREZZO_RIF
    cum = np.concatenate([[0.0], np.cumsum(f)])
    nott = np.concatenate([[0.0], np.cumsum(molt)])
    return giorni, cum, nott


def applica_costi(ops, df):
    if ops.empty:
        return ops
    giorni, cum, nott = fattori_swap(df)
    e = giorni.searchsorted(ops["data_entrata"].dt.tz_localize(None).dt.normalize())
    u = giorni.searchsorted(ops["data_uscita"].dt.tz_localize(None).dt.normalize())
    ops = ops.copy()
    ops["fattore_swap"] = cum[u] - cum[e]
    ops["notti"] = nott[u] - nott[e]
    ops["anno"] = ops["data_entrata"].dt.year
    sp = [max(spread_anno(a), spread_anno(b)) for a, b in
          zip(ops["data_entrata"].dt.year, ops["data_uscita"].dt.year)]
    ops["spread_dollari"] = sp
    r = ops["R_dollari"]
    ops["g_long_R"] = (ops["prezzo_uscita"] - ops["prezzo_entrata"]) / r
    ops["lordo_R"] = ops["direzione"] * ops["g_long_R"]
    ops["spread_R"] = ops["spread_dollari"] / r
    tasso = np.where(ops["direzione"] > 0, SWAP_LONG, SWAP_SHORT)
    ops["swap_R"] = tasso * ops["fattore_swap"] / r
    ops["netto_senza_swap_R"] = ops["lordo_R"] - ops["spread_R"]
    ops["netto_R"] = ops["netto_senza_swap_R"] + ops["swap_R"]
    return ops


# --------------------------------------------------------------------------
# misure
# --------------------------------------------------------------------------

ANNI = list(range(2009, 2027))


def max_dd(x):
    cum = np.cumsum(np.asarray(x, float))
    picco = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:]
    return float(np.max(picco - cum)) if len(cum) else 0.0


def metriche(ops, col="netto_R", tsmom=False):
    x = ops[col].to_numpy(float)
    per_anno = ops.groupby("anno")[col].sum().reindex(ANNI, fill_value=0.0)
    conta = ops.groupby("anno").size().reindex(ANNI, fill_value=0)
    validi = conta >= 2
    pos = int((per_anno[validi] > 0).sum())
    tot_anni = int(validi.sum())
    if tsmom:
        anni_ok = pos == tot_anni                       # lettura severa
    else:
        anni_ok = pos >= 2.0 / 3.0 * tot_anni
    h1 = float(ops.loc[ops["anno"] <= 2017, col].sum())
    h2 = float(ops.loc[ops["anno"] >= 2018, col].sum())
    return dict(R_tot=float(x.sum()), R_op=float(x.mean()) if len(x) else 0.0,
                n=len(x), vinte=100.0 * float((x > 0).mean()) if len(x) else 0.0,
                dd=max_dd(x), anni_pos=pos, anni_tot=tot_anni, anni_ok=anni_ok,
                anni_ok_23=pos >= 2.0 / 3.0 * tot_anni,
                h1=h1, h2=h2, per_anno=per_anno)


def placebo(ops, n=N_PLACEBO, seed=SEED):
    """Totali netti (con swap) di n serie a direzione casuale."""
    rng = np.random.default_rng(seed)
    d = rng.choice(np.array([-1.0, 1.0]), size=(n, len(ops)))
    g = ops["g_long_R"].to_numpy(float)
    sp = ops["spread_R"].to_numpy(float)
    fs = (ops["fattore_swap"] / ops["R_dollari"]).to_numpy(float)
    swap = np.where(d > 0, SWAP_LONG, SWAP_SHORT) * fs
    return (d * g - sp + swap).sum(axis=1)


def verdetto(m, p):
    mancano = []
    if not (m["R_tot"] > 0 and m["R_op"] > 0):
        mancano.append("R<=0")
    if not p < 0.05:
        mancano.append("p")
    if not m["anni_ok"]:
        mancano.append("anni")
    if not (m["h1"] > 0 and m["h2"] > 0):
        mancano.append("meta'")
    if mancano:
        return "NON PASSA (" + ",".join(mancano) + ")"
    if p >= 0.05 / 3:
        return "PASSA al limite (Bonferroni)"
    return "PASSA"


def main():
    pd.set_option("display.width", 200)
    df = pd.read_parquet(FILE_D1)[["open", "high", "low", "close"]]
    fam = {"F1_tsmom": simula_f1(df), "F2_donchian": simula_f2(df),
           "F3_medie": simula_f3(df)}
    righe, per_anno = [], {}
    for nome, ops in fam.items():
        ops = applica_costi(ops, df)
        ops.to_parquet(os.path.join(DATI, f"trend_multigiorno_{nome}.parquet"))
        tsm = nome.startswith("F1")
        m = metriche(ops, tsmom=tsm)
        m0 = metriche(ops, "netto_senza_swap_R", tsmom=tsm)
        pl = placebo(ops)
        p = float((pl >= m["R_tot"]).mean())
        tutte_long = ops.assign(direzione=1)
        tl = float((tutte_long["g_long_R"] - tutte_long["spread_R"]
                    + SWAP_LONG * tutte_long["fattore_swap"]
                    / tutte_long["R_dollari"]).sum())
        per_anno[nome] = m["per_anno"]
        righe.append({"famiglia": nome, "R_tot": m["R_tot"], "R/op": m["R_op"],
                      "n": m["n"], "vinte%": m["vinte"], "DD_R": m["dd"],
                      "anni+": f"{m['anni_pos']}/{m['anni_tot']}",
                      "09-17": m["h1"], "18-26": m["h2"], "p": p,
                      "pl_med": float(np.median(pl)),
                      "pl_95": float(np.quantile(pl, 0.95)),
                      "R_noswap": m0["R_tot"], "tutte_long": tl,
                      "long%": 100.0 * float((ops["direzione"] > 0).mean()),
                      "verdetto": verdetto(m, p),
                      "anni_2/3": "si" if m["anni_ok_23"] else "no"})
    bench = applica_costi(simula_f1(df, sempre_long=True, famiglia="sempre_long"), df)
    mb = metriche(bench)
    mb0 = metriche(bench, "netto_senza_swap_R")
    per_anno["sempre_long"] = mb["per_anno"]
    t = pd.DataFrame(righe).set_index("famiglia")
    print("Trend multi-giorno XAUUSD D1 2009-2026, costi con swap (verdetto) "
          "| placebo 500 serie seed 20261002")
    print(t.drop(columns=["verdetto", "anni_2/3"]).round(3).to_string())
    print(t[["verdetto", "anni_2/3"]].to_string())
    print(f"benchmark sempre-long mensile (date F1): R_tot {mb['R_tot']:.3f}  "
          f"R/op {mb['R_op']:.3f}  n {mb['n']}  DD {mb['dd']:.3f}  "
          f"anni+ {mb['anni_pos']}/{mb['anni_tot']}  09-17 {mb['h1']:.3f}  "
          f"18-26 {mb['h2']:.3f}  senza swap {mb0['R_tot']:.3f}")
    print("R per anno (con swap, anno di entrata):")
    print(pd.DataFrame(per_anno).round(2).T.to_string())


if __name__ == "__main__":
    main()
