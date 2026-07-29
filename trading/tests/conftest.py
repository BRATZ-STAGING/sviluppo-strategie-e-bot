import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def make_m1(start, ohlc, volume=1.0):
    """Costruisce un DataFrame M1 da una lista di tuple (o, h, l, c)."""
    idx = pd.date_range(start=start, periods=len(ohlc), freq="1min", tz="UTC")
    df = pd.DataFrame(ohlc, columns=["open", "high", "low", "close"], index=idx,
                      dtype=float)
    df["volume"] = volume
    df.index.name = "timestamp"
    return df


def flat_bars(start, n, price=2000.0, volume=1.0):
    """n candele M1 piatte al prezzo dato."""
    return make_m1(start, [(price, price, price, price)] * n, volume)


def walk_bars(start, closes, spread=0.5, volume=1.0):
    """Candele M1 da una sequenza di chiusure; open = close precedente."""
    closes = np.asarray(closes, dtype=float)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    highs = np.maximum(opens, closes) + spread
    lows = np.minimum(opens, closes) - spread
    return make_m1(start, list(zip(opens, highs, lows, closes)), volume)


@pytest.fixture
def two_days():
    """Due giorni di trading: 2024-01-02 (range 1990–2010, close 2005) e 2024-01-03."""
    d1 = make_m1("2024-01-02 00:00", [
        (2000, 2001, 1999, 2000.5),
        (2000.5, 2010, 2000, 2008),
        (2008, 2009, 1990, 1995),
        (1995, 2006, 1994, 2005),
    ])
    d2 = make_m1("2024-01-03 00:00", [
        (2005, 2006, 2004, 2005.5),
        (2005.5, 2007, 2003, 2004),
    ])
    return pd.concat([d1, d2])


@pytest.fixture
def day3():
    return pd.Timestamp("2024-01-03", tz="UTC")
