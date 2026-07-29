"""Struttura di mercato multi-timeframe: swing, BOS/CHOCH, stato di trend.

Tutto è **causale**: uno swing con ``k`` candele per lato è confermato solo
alla chiusura della k-esima candela successiva al suo estremo; una rottura
(BOS) esiste solo alla chiusura della candela che rompe. Lo stato di trend
riferito a un istante ``t`` usa esclusivamente informazione disponibile a
``t``.

Convenzioni:
- stato +1 = uptrend (ultima rottura strutturale verso l'alto)
- stato -1 = downtrend
- stato  0 = indeterminato (nessuna rottura ancora)
- CHOCH = rottura contraria allo stato corrente; BOS = rottura a favore
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def trend_events(htf: pd.DataFrame, k: int = 3,
                 freq: str | pd.Timedelta = "1h") -> pd.DataFrame:
    """Eventi strutturali su un DataFrame OHLC di un timeframe superiore.

    Ritorna un DataFrame con colonne ``known_from`` (istante da cui l'evento
    è noto: chiusura della candela che rompe), ``event`` (BOS_up/CHOCH_up/
    BOS_down/CHOCH_down), ``level`` (lo swing rotto), ``state`` (stato dopo
    l'evento).
    """
    freq = pd.Timedelta(freq)
    highs, lows, closes = htf.high.values, htf.low.values, htf.close.values
    idx = htf.index
    n = len(htf)
    last_sh = last_sl = None
    state = 0
    rows = []
    for i in range(n):
        j = i - k
        if j >= k:
            hj = highs[j]
            if (highs[j - k:j] < hj).all() and (highs[j + 1:j + k + 1] < hj).all():
                last_sh = hj
            lj = lows[j]
            if (lows[j - k:j] > lj).all() and (lows[j + 1:j + k + 1] > lj).all():
                last_sl = lj
        c = closes[i]
        if last_sh is not None and c > last_sh:
            event = "CHOCH_up" if state == -1 else "BOS_up"
            rows.append((idx[i] + freq, event, float(last_sh), 1))
            state = 1
            last_sh = None
        if last_sl is not None and c < last_sl:
            event = "CHOCH_down" if state == 1 else "BOS_down"
            rows.append((idx[i] + freq, event, float(last_sl), -1))
            state = -1
            last_sl = None
    return pd.DataFrame(rows, columns=["known_from", "event", "level", "state"])


def trend_state_series(htf: pd.DataFrame, k: int = 3,
                       freq: str | pd.Timedelta = "1h") -> pd.Series:
    """Serie dello stato di trend indicizzata da quando lo stato è noto."""
    ev = trend_events(htf, k, freq)
    if ev.empty:
        return pd.Series(dtype="int64", name="state")
    s = ev.set_index("known_from").state
    return s[~s.index.duplicated(keep="last")]


def state_at(states: pd.Series, times: pd.DatetimeIndex | pd.Series) -> np.ndarray:
    """Stato di trend vigente a ciascun istante (0 se nessun evento ancora)."""
    if len(states) == 0:
        return np.zeros(len(times), dtype=int)
    t = pd.DatetimeIndex(times)
    pos = states.index.searchsorted(t, side="right") - 1
    out = np.where(pos >= 0, states.values[np.clip(pos, 0, None)], 0)
    return out.astype(int)
