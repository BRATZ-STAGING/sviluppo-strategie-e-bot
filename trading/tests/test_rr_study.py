import numpy as np
import pandas as pd
import pytest

from framework import rr_study as rr
from framework.levels import Level
from conftest import make_m1

DAY = pd.Timestamp("2024-01-03", tz="UTC")
CFG = rr.RRConfig(stop=1.0, rr=5.0, spread=0.30, eod_hour=21, last_entry_hour=19)


def level(price, kind="pdl"):
    return Level(price, kind, DAY)


class TestFirstTouchOutcome:
    def test_target_raggiunto(self):
        h = np.array([2000.2, 2003.0, 2005.5])
        l = np.array([1999.8, 2000.0, 2003.0])
        c = np.array([2000.0, 2003.0, 2005.0])
        r, reason = rr._first_touch_outcome(h, l, c, 0, 3, 2000.0, "above", CFG)
        assert (r, reason) == (5.0, "tp")

    def test_stop_prima_del_target(self):
        h = np.array([2000.2, 2001.0, 2006.0])
        l = np.array([1999.8, 1998.9, 2001.0])   # adv 1.1 >= stop alla 2ª candela
        c = np.array([2000.0, 1999.0, 2005.0])
        r, reason = rr._first_touch_outcome(h, l, c, 0, 3, 2000.0, "above", CFG)
        assert (r, reason) == (-1.0, "sl")

    def test_stessa_candela_vale_lo_stop(self):
        h = np.array([2005.5])
        l = np.array([1998.5])
        c = np.array([2000.0])
        r, reason = rr._first_touch_outcome(h, l, c, 0, 1, 2000.0, "above", CFG)
        assert (r, reason) == (-1.0, "sl")

    def test_uscita_eod(self):
        h = np.array([2000.2, 2002.0])
        l = np.array([1999.8, 2000.0])
        c = np.array([2000.0, 2001.5])
        r, reason = rr._first_touch_outcome(h, l, c, 0, 2, 2000.0, "above", CFG)
        assert reason == "eod"
        assert r == pytest.approx(1.5)   # (2001.5 - 2000) / stop 1.0

    def test_short_alla_resistenza(self):
        h = np.array([2000.2, 1999.0])
        l = np.array([1999.8, 1994.5])
        c = np.array([2000.0, 1995.0])
        r, reason = rr._first_touch_outcome(h, l, c, 0, 2, 2000.0, "below", CFG)
        assert (r, reason) == (5.0, "tp")


class TestDayOutcomes:
    def _df(self, closes, start="2024-01-03 08:00"):
        return make_m1(start, [(c, c + 0.4, c - 0.4, c) for c in closes])

    def test_solo_primo_tocco(self):
        closes = [2005, 2000.2, 2003, 2000.2, 2003] + [2003] * 5
        out = rr.day_outcomes(self._df(closes), DAY, [level(2000.0)], CFG)
        assert len(out) == 1
        assert out[0]["time"].minute == 1

    def test_r_net_sottrae_lo_spread(self):
        closes = [2005, 2000.2, 2006] + [2006] * 3
        out = rr.day_outcomes(self._df(closes), DAY, [level(2000.0)], CFG)
        assert out[0]["r_net"] == pytest.approx(out[0]["r_gross"] - 0.30)

    def test_niente_ingressi_dopo_last_entry(self):
        cfg = rr.RRConfig(stop=1.0, last_entry_hour=9)
        closes = [2005, 2003, 2000.2, 2003, 2003]
        out = rr.day_outcomes(self._df(closes, start="2024-01-03 10:00"),
                              DAY, [level(2000.0)], cfg)
        assert out == []

    def test_confluenza(self):
        closes = [2005, 2000.2, 2003] + [2003] * 3
        levels = [level(2000.0, "pdl"), level(2001.5, "round_50"), level(2050.0, "pdh")]
        out = rr.day_outcomes(self._df(closes), DAY, levels, CFG)
        pdl = [o for o in out if o["kind"] == "pdl"][0]
        assert pdl["confluence"] is True  # round_50 a 1.5 USD di distanza

    def test_confluenza_ignora_livelli_non_ancora_attivi(self):
        # il partner è entro tolleranza ma si attiva DOPO il tocco (es. asia_l
        # noto solo dalle 07:00): non deve contare come confluenza
        closes = [2005, 2000.2, 2003] + [2003] * 3
        late = Level(2001.5, "asia_l", DAY,
                     active_from=pd.Timestamp("2024-01-03 07:00", tz="UTC"))
        out = rr.day_outcomes(self._df(closes, start="2024-01-03 02:00"), DAY,
                              [level(2000.0, "pdc"), late], CFG)
        pdc = [o for o in out if o["kind"] == "pdc"][0]
        assert pdc["confluence"] is False

    def test_run_rr_study_aggrega(self):
        prev = make_m1("2024-01-02 08:00", [(2004, 2010, 2000, 2005)] * 3)
        closes = [2005, 2003, 2000.2, 2002, 2004, 2006] + [2006] * 10
        df = pd.concat([prev, self._df(closes)])
        res = rr.run_rr_study(df, CFG)
        assert not res.empty
        assert {"kind", "session", "r_net", "win", "year"} <= set(res.columns)
        agg = rr.aggregate(res, ["kind"])
        assert "exp_r_net" in agg.columns and "anni_positivi" in agg.columns
