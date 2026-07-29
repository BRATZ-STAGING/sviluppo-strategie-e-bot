"""Misura di volatilità giornaliera (ATR), causale.

L'ATR del giorno D usa solo giornate precedenti a D: è quindi utilizzabile
come unità di misura per le soglie della strategia senza look-ahead.

Nota: il resampling giornaliero grezzo conta come "giornata" anche lo
spezzone della domenica sera (23:00-23:59 UTC), che ha pochissime candele.
Quelle sessioni parziali vengono escluse dal calcolo (`min_bars`), altrimenti
il true range risulta artificialmente compresso.
"""
from __future__ import annotations

import pandas as pd

from .data import OHLCV_AGG

MIN_BARS_FULL_DAY = 300      # sotto questa soglia è una sessione parziale


def daily_bars(m1: pd.DataFrame, min_bars: int = MIN_BARS_FULL_DAY) -> pd.DataFrame:
    """Candele giornaliere, escluse le sessioni parziali (domenica sera)."""
    g = m1.resample("1D")
    d1 = g.agg(OHLCV_AGG).dropna(subset=["open"])
    counts = g.size()
    return d1[counts.reindex(d1.index).values >= min_bars]


def daily_atr(m1: pd.DataFrame, n: int = 14) -> pd.Series:
    """ATR a ``n`` giorni, indicizzato per giornata e noto a inizio giornata.

    Il valore associato al giorno D è calcolato con le sole giornate fino a
    D-1 inclusa (shift di 1), quindi è disponibile prima di operare in D.
    """
    d1 = daily_bars(m1)
    prev_close = d1.close.shift(1)
    tr = pd.concat([
        d1.high - d1.low,
        (d1.high - prev_close).abs(),
        (d1.low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(n).mean().shift(1)
    atr.index = atr.index.normalize()
    atr.name = f"atr{n}"
    return atr


def atr_at(atr: pd.Series, days: pd.DatetimeIndex) -> pd.Series:
    """ATR vigente per ciascuna giornata richiesta (ultimo valore noto)."""
    return atr.reindex(pd.DatetimeIndex(days).normalize()).ffill()


def high_volatility_months(atr: pd.Series, months, factor: float = 1.5,
                           min_history: int = 250,
                           recent_days: int = 21) -> dict:
    """Per ogni mese: la volatilità recente è in regime alto? (causale)

    Confronta la mediana dell'ATR dell'ultimo mese di borsa con la mediana di
    TUTTA la storia precedente (finestra espansiva). Entrambe usano solo
    giornate antecedenti all'inizio del mese, quindi la risposta è
    disponibile prima di operare in quel mese.

    Finché non c'è almeno ``min_history`` giornate di storia risponde False
    (regime "normale" come default prudente).
    """
    out = {}
    for m in months:
        start = m.start_time
        if atr.index.tz is not None and start.tz is None:
            start = start.tz_localize(atr.index.tz)
        past = atr[atr.index < start].dropna()
        if len(past) < min_history:
            out[m] = False
            continue
        out[m] = bool(past.tail(recent_days).median() > factor * past.median())
    return out
