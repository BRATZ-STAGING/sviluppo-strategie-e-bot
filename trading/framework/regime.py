"""Classificazione del regime di mercato (trend vs range), causale.

Feature principale: **efficiency ratio** di Kaufman su chiusure giornaliere:
ER = |C_t - C_{t-n}| / somma(|C_i - C_{i-1}|). Vicino a 1 = movimento
direzionale pulito (trend), vicino a 0 = rumore (range).

La serie è indicizzata dal giorno per cui il regime è valido e usa SOLO
chiusure di giorni precedenti (shift di 1 giorno).
"""
from __future__ import annotations

import pandas as pd

from .data import resample


def efficiency_ratio(daily_close: pd.Series, n: int = 20) -> pd.Series:
    """ER di Kaufman sulle chiusure giornaliere (0..1)."""
    direction = (daily_close - daily_close.shift(n)).abs()
    path = daily_close.diff().abs().rolling(n).sum()
    return direction / path


def regime_series(m1: pd.DataFrame, n: int = 20,
                  threshold: float = 0.35) -> pd.Series:
    """Serie causale di regime per giorno: 'trend' oppure 'range'.

    Il valore del giorno D è calcolato con le chiusure fino a D-1 incluso.
    """
    d1 = resample(m1, "1D")
    er = efficiency_ratio(d1.close, n).shift(1)  # noto a inizio giornata
    reg = pd.Series("range", index=er.index, dtype=object, name="regime")
    reg[er > threshold] = "trend"
    reg[er.isna()] = "na"
    reg.index = reg.index.normalize()
    return reg
