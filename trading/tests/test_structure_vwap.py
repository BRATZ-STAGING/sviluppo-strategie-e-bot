import numpy as np
import pandas as pd
import pytest

from framework.structure import state_at, trend_events, trend_state_series
from framework.vwap import anchored_vwap
from conftest import make_m1


def htf_from_closes(closes, start="2024-01-02 00:00", freq="2h", rng=1.0):
    idx = pd.date_range(start=start, periods=len(closes), freq=freq, tz="UTC")
    c = np.asarray(closes, dtype=float)
    df = pd.DataFrame({"open": c, "high": c + rng, "low": c - rng,
                       "close": c, "volume": 1.0}, index=idx)
    return df


class TestTrendEvents:
    def test_bos_up_dopo_swing_confermato(self):
        # swing high a 2010 (indice 2, k=2), poi rottura al rialzo
        closes = [2000, 2005, 2010, 2004, 2000, 2003, 2006, 2013, 2014]
        df = htf_from_closes(closes)
        ev = trend_events(df, k=2, freq="2h")
        ups = ev[ev.event.str.endswith("up")]
        assert len(ups) == 1
        e = ups.iloc[0]
        # swing high = high di indice 2 = 2011; rotto alla candela 7 (close 2013)
        assert e.level == 2011.0
        assert e.known_from == df.index[7] + pd.Timedelta("2h")
        assert e.state == 1

    def test_choch_down_dopo_uptrend(self):
        # uptrend confermato, poi swing low rotto → CHOCH_down
        closes = [2000, 2005, 2010, 2004, 2000, 2003, 2006, 2013, 2014,
                  2010, 2005, 2008, 2009, 1997, 1996]
        df = htf_from_closes(closes)
        ev = trend_events(df, k=2, freq="2h")
        assert list(ev.event) == ["BOS_up", "CHOCH_down"]
        assert list(ev.state) == [1, -1]

    def test_nessun_evento_su_pochi_dati(self):
        df = htf_from_closes([2000, 2001, 2002])
        assert trend_events(df, k=2).empty

    def test_state_at_causale(self):
        closes = [2000, 2005, 2010, 2004, 2000, 2003, 2006, 2013, 2014]
        df = htf_from_closes(closes)
        states = trend_state_series(df, k=2, freq="2h")
        known = states.index[0]
        t = pd.DatetimeIndex([known - pd.Timedelta("1min"), known,
                              known + pd.Timedelta("3h")])
        assert list(state_at(states, t)) == [0, 1, 1]

    def test_state_at_senza_eventi(self):
        states = trend_state_series(htf_from_closes([1, 2, 3]), k=2)
        t = pd.DatetimeIndex([pd.Timestamp("2024-01-02", tz="UTC")])
        assert list(state_at(states, t)) == [0]


class TestAnchoredVwap:
    def test_calcolo_manuale(self):
        df = make_m1("2024-01-02 00:00", [
            (10, 12, 8, 10),    # tp = 10, vol 1
            (10, 22, 14, 18),   # tp = 18, vol 1
        ])
        v = anchored_vwap(df, "day")
        assert v.iloc[0] == pytest.approx(10.0)
        assert v.iloc[1] == pytest.approx(14.0)  # (10 + 18) / 2

    def test_riazzera_a_ogni_giorno(self):
        d1 = make_m1("2024-01-02 00:00", [(10, 12, 8, 10)])
        d2 = make_m1("2024-01-03 00:00", [(50, 52, 48, 50)])
        v = anchored_vwap(pd.concat([d1, d2]), "day")
        assert v.iloc[1] == pytest.approx(50.0)  # non contaminato dal giorno prima

    def test_ancora_settimanale(self):
        # lunedì e martedì della stessa settimana: cumulato; lunedì successivo: reset
        mon = make_m1("2024-01-08 00:00", [(10, 12, 8, 10)])
        tue = make_m1("2024-01-09 00:00", [(30, 32, 28, 30)])
        mon2 = make_m1("2024-01-15 00:00", [(100, 102, 98, 100)])
        v = anchored_vwap(pd.concat([mon, tue, mon2]), "week")
        assert v.iloc[1] == pytest.approx(20.0)
        assert v.iloc[2] == pytest.approx(100.0)

    def test_volume_zero(self):
        df = make_m1("2024-01-02 00:00", [(10, 12, 8, 10)], volume=0.0)
        assert anchored_vwap(df, "day").isna().all()

    def test_anchor_sconosciuta(self):
        df = make_m1("2024-01-02 00:00", [(10, 12, 8, 10)])
        with pytest.raises(ValueError):
            anchored_vwap(df, "month")
