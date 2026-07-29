"""VWAP ancorati (giornaliero e settimanale).

VWAP = somma cumulata di (prezzo tipico × volume) / somma cumulata del
volume, riazzerata a ogni ancora. Il prezzo tipico è (H+L+C)/3. Causale per
costruzione: il valore alla candela ``i`` usa solo candele ≤ ``i`` della
stessa finestra di ancoraggio.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _anchor_key(index: pd.DatetimeIndex, anchor: str) -> pd.Index:
    if anchor == "day":
        return index.normalize()
    if anchor == "week":
        return (index - pd.to_timedelta(index.weekday, unit="D")).normalize()
    raise ValueError(f"anchor sconosciuta: {anchor} (usa 'day' o 'week')")


def anchored_vwap(df: pd.DataFrame, anchor: str = "day") -> pd.Series:
    """VWAP ancorato per ogni candela di ``df`` (indice DatetimeIndex UTC)."""
    key = _anchor_key(df.index, anchor)
    tp = (df.high + df.low + df.close) / 3.0
    pv = (tp * df.volume).groupby(key).cumsum()
    vv = df.volume.groupby(key).cumsum()
    out = pv / vv.replace(0.0, np.nan)
    out.name = f"vwap_{anchor}"
    return out
