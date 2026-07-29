"""Generazione dei segnali: reclaim del VWAP giornaliero, parametrizzata.

Un solo generatore per tutte le varianti della strategia. Cosa cambia fra una
variante e l'altra sta tutto nella :class:`~framework.taratura.Taratura`:
quale timeframe si guarda per l'ingresso, quali strutture devono essere
allineate, quanto stretto puo' essere lo stop, quante operazioni al giorno.

La regola d'ingresso, uguale per tutte le varianti:
1. le strutture di ``tf_struttura`` sono tutte allineate alla direzione
2. il prezzo si e' allontanato dal VWAP di almeno l'impulso minimo nel corso
   della giornata, poi torna a toccarlo
3. la candela chiude dalla parte giusta del VWAP e oltre l'estremo della
   precedente

Stop sotto (o sopra) il minimo delle ultime ``barre_stop`` candele piu' il
buffer; niente lookahead: ogni struttura e' valutata alla CHIUSURA della
candela d'ingresso, gli swing sono confermati k barre dopo l'estremo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import TIMEFRAMES, resample_tf
from .structure import state_at, trend_state_series
from .taratura import Taratura
from .volatility import atr_at, daily_atr, high_volatility_months
from .vwap import anchored_vwap


def stati(m1: pd.DataFrame, tfs, istanti, k: int) -> dict[str, np.ndarray]:
    """Stato di trend causale di ogni timeframe, valutato agli istanti dati."""
    out = {}
    for tf in tfs:
        serie = resample_tf(m1, tf)
        out[tf] = state_at(
            trend_state_series(serie, k, pd.Timedelta(TIMEFRAMES[tf])), istanti)
    return out


def filtro_macro(m1: pd.DataFrame, n: int) -> dict:
    """Chiusura giornaliera sopra o sotto la sua media, spostata di un giorno."""
    d1 = m1.close.resample("1D").last().dropna()
    sopra = (d1 > d1.rolling(n).mean()).shift(1)
    sopra.index = sopra.index.normalize()
    return sopra.to_dict()


def genera(m1: pd.DataFrame, t: Taratura, tf_extra=()) -> list[dict]:
    """Tutte le operazioni della variante ``t``, con i percorsi al minuto.

    Ogni voce contiene ingresso, stop, rischio, i percorsi ``fav``/``sfav`` in
    multipli del rischio e lo stato di ogni timeframe richiesto. Il calcolo
    dell'esito NON e' qui: lo fa :mod:`framework.gestione`, cosi' la stessa
    operazione puo' essere valutata con obiettivi e gestioni diverse.

    ``tf_extra`` aggiunge timeframe da registrare senza usarli come filtro:
    serve agli studi che vogliono misurare conferme non ancora adottate.
    """
    passo = pd.Timedelta(TIMEFRAMES[t.tf_ingresso])
    base = resample_tf(m1, t.tf_ingresso)
    base["vwap"] = anchored_vwap(base, "day")
    chiusure = base.index + passo
    tfs = tuple(dict.fromkeys(t.timeframes + tuple(tf_extra)))
    st = stati(m1, tfs, chiusure, t.frattale_k)

    atr = daily_atr(m1, 14)
    atr_bar = atr_at(atr, base.index).values
    anni = (atr.index.year >= t.calibrazione[0]) & (atr.index.year <= t.calibrazione[1])
    mediana = float(atr[anni].median())
    mesi = sorted({pd.Period(x.strftime("%Y-%m"), "M") for x in base.index})
    alta = high_volatility_months(atr, mesi, t.fattore_alta_volatilita)
    macro = filtro_macro(m1, t.media_macro)

    idx = base.index
    ore, giorni = idx.hour, idx.normalize()
    hi, lo, cl = base.high.values, base.low.values, base.close.values
    vwap = base.vwap.values
    mese = pd.PeriodIndex(idx, freq="M")
    strut = [st[tf] for tf in t.tf_struttura]

    m1_idx = m1.index
    m1h, m1l, m1c = m1.high.values, m1.low.values, m1.close.values
    fissa = t.soglie()

    out, ultimo, per_giorno, inizio = [], None, {}, 0
    for i in range(1, len(base)):
        g = giorni[i]
        if g != giorni[i - 1]:
            inizio = i
        if not (t.ora_inizio <= ore[i] < t.ora_fine):
            continue
        if np.isnan(vwap[i]) or per_giorno.get(g, 0) >= t.max_operazioni_giorno:
            continue
        quando = idx[i] + passo
        if ultimo is not None and (quando - ultimo) < pd.Timedelta(minutes=t.attesa_minuti):
            continue

        if alta.get(mese[i], False):
            u = atr_bar[i]
            if np.isnan(u) or u <= 0:
                continue
            s = t.soglie(atr=float(u), mediana=mediana)
        else:
            s = fissa

        lato = None
        for segno, avanti in ((1, True), (-1, False)):
            if any(x[i] != segno for x in strut):
                continue
            if avanti:
                tocca = lo[i] <= vwap[i] and cl[i] > vwap[i] and cl[i] > hi[i - 1]
                spinta = float(hi[inizio:i].max() - vwap[i]) if i > inizio else 0.0
            else:
                tocca = hi[i] >= vwap[i] and cl[i] < vwap[i] and cl[i] < lo[i - 1]
                spinta = float(vwap[i] - lo[inizio:i].min()) if i > inizio else 0.0
            if tocca and spinta >= s["impulso"]:
                lato = segno
                break
        if lato is None:
            continue
        if macro.get(g, False) != (lato == 1):
            continue

        entry = float(cl[i])
        j0 = max(inizio, i - t.barre_stop)
        stop = (float(lo[j0:i + 1].min() - s["buffer"]) if lato == 1
                else float(hi[j0:i + 1].max() + s["buffer"]))
        rischio = (entry - stop) if lato == 1 else (stop - entry)
        if not (s["rischio_min"] <= rischio <= s["rischio_max"]):
            continue

        a = int(m1_idx.searchsorted(quando))
        b = int(m1_idx.searchsorted(g + pd.Timedelta(hours=t.ora_chiusura)))
        if b - a < 2:
            continue
        ultimo = quando
        per_giorno[g] = per_giorno.get(g, 0) + 1

        h_, l_, c_ = m1h[a:b], m1l[a:b], m1c[a:b]
        if lato == 1:
            fav, sfav = (h_ - entry) / rischio, (entry - l_) / rischio
        else:
            fav, sfav = (entry - l_) / rischio, (h_ - entry) / rischio
        fine = float(c_[-1])
        out.append({
            "time": quando, "anno": int(idx[i].year),
            "lato": "long" if lato == 1 else "short",
            "entry": entry, "stop": stop, "rischio": rischio,
            "costo": t.spread / rischio,
            "volalta": bool(alta.get(mese[i], False)),
            "fav": fav, "sfav": sfav, "mfe": float(fav.max()),
            "r_eod": ((fine - entry) if lato == 1 else (entry - fine)) / rischio,
            **{f"c_{tf}": int(st[tf][i] == lato) for tf in tfs},
        })
    return out
