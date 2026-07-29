import numpy as np
import pandas as pd
import pytest

from framework import reaction as rx
from framework.levels import Level
from conftest import make_m1

DAY = pd.Timestamp("2024-01-03", tz="UTC")
CFG = rx.StudyConfig(window_min=10, bounce_target=3.0, stop_penetration=1.5,
                     cooldown_min=5, min_touches=1)


def level(price, kind="pdl", active_from=None):
    return Level(price, kind, DAY, active_from=active_from)


class TestMeasure:
    def test_rimbalzo_prima_dello_stop(self):
        h = np.array([2000.5, 2002.0, 2004.0])
        l = np.array([1999.5, 2001.0, 2003.0])
        bounce, pen, ok = rx._measure(h, l, 2000.0, "above", CFG)
        assert ok and bounce == 4.0 and pen == 0.5

    def test_stop_prima_del_target(self):
        h = np.array([2000.5, 2001.0, 2005.0])
        l = np.array([1999.5, 1998.0, 2003.0])  # penetra 2.0 > 1.5 alla 2ª candela
        bounce, pen, ok = rx._measure(h, l, 2000.0, "above", CFG)
        assert not ok and pen == 2.0

    def test_stessa_candela_conservativo(self):
        # target e stop entrambi nella stessa candela: vale lo stop
        h = np.array([2004.0])
        l = np.array([1998.0])
        _, _, ok = rx._measure(h, l, 2000.0, "above", CFG)
        assert not ok

    def test_lato_below(self):
        h = np.array([2000.5, 1999.0])
        l = np.array([1999.5, 1996.0])
        bounce, pen, ok = rx._measure(h, l, 2000.0, "below", CFG)
        assert ok and bounce == 4.0 and pen == 0.5


class TestTouchesForDay:
    def _df(self, closes, start="2024-01-03 08:00"):
        return make_m1(start, [(c, c + 0.4, c - 0.4, c) for c in closes])

    def test_tocco_da_sopra(self):
        closes = [2005, 2003, 2000.2, 2002, 2004, 2006] + [2006] * 5
        df = self._df(closes)
        out = rx.touches_for_day(df, DAY, [level(2000.0)], CFG)
        assert len(out) == 1
        t = out[0]
        assert t.side == "above" and t.success
        assert t.time == df.index[2]

    def test_tocco_da_sotto(self):
        closes = [1995, 1997, 1999.8, 1998, 1996, 1994] + [1994] * 5
        out = rx.touches_for_day(self._df(closes), DAY, [level(2000.0)], CFG)
        assert len(out) == 1
        assert out[0].side == "below" and out[0].success

    def test_cooldown(self):
        # due tocchi ravvicinati: il secondo entro il cooldown viene ignorato
        closes = [2005, 2000.2, 2003, 2000.2, 2003, 2003, 2003, 2000.2, 2005, 2005, 2005]
        out = rx.touches_for_day(self._df(closes), DAY, [level(2000.0)], CFG)
        assert [t.time.minute for t in out] == [1, 7]

    def test_livello_non_ancora_attivo(self):
        closes = [2005, 2000.2, 2003, 2004, 2005, 2005]
        df = self._df(closes)
        active = df.index[3]
        out = rx.touches_for_day(df, DAY, [level(2000.0, active_from=active)], CFG)
        assert out == []

    def test_serve_candela_precedente(self):
        # tocco alla prima candela del giorno: direzione ignota, scartato
        closes = [2000.2, 2005, 2005, 2005]
        out = rx.touches_for_day(self._df(closes, start="2024-01-03 00:00"),
                                 DAY, [level(2000.0)], CFG)
        assert out == []

    def test_finestra_oltre_mezzanotte(self):
        # tocco all'ultima candela del giorno: la reazione usa le candele del giorno dopo
        d1 = self._df([2005, 2000.2], start="2024-01-03 23:58")
        d2 = self._df([2002, 2004, 2006, 2006], start="2024-01-04 00:00")
        df = pd.concat([d1, d2])
        out = rx.touches_for_day(df, DAY, [level(2000.0)], CFG)
        assert len(out) == 1 and out[0].success

    def test_giorno_senza_dati(self):
        df = self._df([2005, 2000.2, 2003], start="2024-01-05 08:00")
        assert rx.touches_for_day(df, DAY, [level(2000.0)], CFG) == []


class TestRunStudy:
    def test_classifica(self):
        closes = [2005, 2003, 2000.2, 2002, 2004, 2006] + [2006] * 60
        df = make_m1("2024-01-03 08:00", [(c, c + 0.4, c - 0.4, c) for c in closes])
        # pdl a 2000 dal giorno precedente: servono 2 giorni
        prev = make_m1("2024-01-02 08:00", [(2004, 2010, 2000, 2005)] * 3)
        full = pd.concat([prev, df])
        cfg = rx.StudyConfig(window_min=10, bounce_target=3.0,
                             stop_penetration=1.5, cooldown_min=5, min_touches=1)
        ranking, touches = rx.run_study(full, cfg)
        assert not ranking.empty
        assert "pdl" in ranking.index
        row = ranking.loc["pdl"]
        assert row.touches >= 1
        assert 0 <= row.success_rate <= 1
        expected = row.success_rate * 3.0 - (1 - row.success_rate) * 1.5
        assert row.expectancy == pytest.approx(expected)

    def test_min_touches_filtra(self):
        closes = [2005, 2003, 2000.2, 2002, 2004, 2006] + [2006] * 60
        df = make_m1("2024-01-03 08:00", [(c, c + 0.4, c - 0.4, c) for c in closes])
        prev = make_m1("2024-01-02 08:00", [(2004, 2010, 2000, 2005)] * 3)
        cfg = rx.StudyConfig(window_min=10, min_touches=1000)
        ranking, touches = rx.run_study(pd.concat([prev, df]), cfg)
        assert ranking.empty and not touches.empty

    def test_vuoto(self):
        df = make_m1("2024-01-02 08:00", [(2004, 2005, 2003, 2004)])
        ranking, touches = rx.run_study(df)
        assert ranking.empty and touches.empty
