import numpy as np
import pandas as pd
import pytest

from framework.regime import efficiency_ratio, regime_series
from conftest import make_m1


class TestEfficiencyRatio:
    def test_trend_perfetto(self):
        # salita monotona: direzione == percorso -> ER = 1
        c = pd.Series(np.arange(30, dtype=float))
        er = efficiency_ratio(c, n=10)
        assert er.iloc[-1] == pytest.approx(1.0)

    def test_range_perfetto(self):
        # oscillazione che torna al punto di partenza -> ER ~ 0
        c = pd.Series([100, 110] * 15, dtype=float)
        er = efficiency_ratio(c, n=10)
        assert er.iloc[-1] == pytest.approx(0.0)

    def test_finestra_insufficiente(self):
        er = efficiency_ratio(pd.Series([1.0, 2.0, 3.0]), n=10)
        assert er.isna().all()


class TestRegimeSeries:
    def _m1_from_daily_closes(self, closes, start_day="2024-01-01"):
        days = []
        day = pd.Timestamp(start_day, tz="UTC")
        for c in closes:
            days.append(make_m1(day + pd.Timedelta(hours=8),
                                [(c, c + 1, c - 1, c)] * 60))
            day += pd.Timedelta(days=1)
        return pd.concat(days)

    def test_trend_riconosciuto(self):
        m1 = self._m1_from_daily_closes(list(range(2000, 2030)))
        reg = regime_series(m1, n=10, threshold=0.35)
        assert reg.iloc[-1] == "trend"

    def test_range_riconosciuto(self):
        m1 = self._m1_from_daily_closes([2000, 2010] * 15)
        reg = regime_series(m1, n=10, threshold=0.35)
        assert reg.iloc[-1] == "range"

    def test_causale(self):
        # il regime del giorno D non cambia se cambiano i dati del giorno D
        closes = list(range(2000, 2030))
        m1a = self._m1_from_daily_closes(closes)
        closes_mod = closes[:-1] + [1900]  # ultimo giorno stravolto
        m1b = self._m1_from_daily_closes(closes_mod)
        rega, regb = regime_series(m1a, n=10), regime_series(m1b, n=10)
        assert rega.iloc[-1] == regb.iloc[-1]

    def test_primi_giorni_na(self):
        m1 = self._m1_from_daily_closes(list(range(2000, 2008)))
        reg = regime_series(m1, n=10)
        assert (reg == "na").all()
