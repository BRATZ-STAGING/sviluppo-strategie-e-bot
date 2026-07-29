import pandas as pd
import pytest

from framework import backtest as bt
from framework.reclaim_strategy import ReclaimStrategyConfig, SweepReclaimStrategy
from conftest import make_m1

CFG_BT = bt.BacktestConfig(spread=0.0, initial_equity=10_000, risk_per_trade=0.01,
                           min_stop_distance=0.1)


def cfg(**kw):
    base = dict(kinds=frozenset({"pdl"}), sessions=frozenset({"london", "ny"}),
                min_depth=0.5, reclaim_margin=0.2, stop_buffer=0.3,
                min_stop=0.3, max_stop=5.0, max_wait=10, d1_filter=False)
    base.update(kw)
    return ReclaimStrategyConfig(**base)


def with_prev_day(day2_bars, start="2024-01-03 08:00"):
    """Giorno 1 con pdl=1990; giorno 2 con le candele date (o,h,l,c)."""
    d1 = make_m1("2024-01-02 08:00", [
        (2000, 2010, 1990, 2005),
        (2005, 2006, 2004, 2005),
    ])
    d2 = make_m1(start, day2_bars)
    return pd.concat([d1, d2])


SWEEP_RECLAIM = [
    (1995, 1996, 1994, 1995),     # arriva da sopra
    (1995, 1995, 1988.5, 1989),   # sweep: buca 1990, minimo 1988.5
    (1989, 1990.5, 1988.8, 1990.4),  # reclaim: close 1990.4 > 1990.2
    (1990.5, 1991, 1990, 1990.8),    # fill del market qui (open 1990.5)
    (1990.8, 2004, 1990.5, 2003),    # corsa verso il target
    (2003, 2004, 2002, 2003),
]


class TestSweepReclaim:
    def test_ingresso_con_stop_e_target(self):
        df = with_prev_day(SWEEP_RECLAIM)
        strat = SweepReclaimStrategy(df, cfg())
        res = bt.run_backtest(df, strat, CFG_BT)
        assert len(res.trades) == 1
        t = res.trades.iloc[0]
        assert t.side == "buy" and t.tag == "pdl@1990"
        assert t.entry == 1990.5  # apertura successiva al reclaim
        # stop sotto il minimo dello sweep: 1988.5 - 0.3
        sl_expected = 1988.2
        # target: close reclaim 1990.4 + 5 * (1990.4 - 1988.2) = 2001.4
        assert t.reason == "tp"
        assert t.exit == pytest.approx(1990.4 + 5 * (1990.4 - sl_expected))

    def test_sweep_troppo_superficiale_scartato(self):
        bars = [
            (1995, 1996, 1994, 1995),
            (1995, 1995, 1989.7, 1989.8),   # buca di soli 0.3 < min_depth 0.5
            (1989.8, 1990.5, 1989.7, 1990.4),
            (1990.5, 2010, 1990, 2005),
        ]
        df = with_prev_day(bars)
        res = bt.run_backtest(df, SweepReclaimStrategy(df, cfg()), CFG_BT)
        assert len(res.trades) == 0

    def test_reclaim_oltre_deadline_scartato(self):
        bars = [(1995, 1996, 1994, 1995),
                (1995, 1995, 1988.5, 1989)] + \
               [(1989, 1989.5, 1988.8, 1989)] * 11 + \
               [(1989, 1990.5, 1989, 1990.4),    # reclaim ma dopo max_wait=10
                (1990.5, 2010, 1990, 2005)]
        df = with_prev_day(bars)
        res = bt.run_backtest(df, SweepReclaimStrategy(df, cfg()), CFG_BT)
        assert len(res.trades) == 0

    def test_fuori_sessione_scartato(self):
        df = with_prev_day(SWEEP_RECLAIM, start="2024-01-03 02:00")  # asia
        res = bt.run_backtest(df, SweepReclaimStrategy(df, cfg()), CFG_BT)
        assert len(res.trades) == 0

    def test_chiusura_eod(self):
        # ingresso che non tocca ne' stop ne' target: chiuso alle 21
        bars = SWEEP_RECLAIM[:4] + [(1990.8, 1991.5, 1990.5, 1991)] * 6
        df = with_prev_day(bars, start="2024-01-03 20:53")
        # sweep/reclaim prima delle 21, le ultime candele sono alle 21:00+
        res = bt.run_backtest(df, SweepReclaimStrategy(df, cfg(last_entry_hour=21,
                                                               eod_close_hour=21)), CFG_BT)
        assert len(res.trades) == 1
        t = res.trades.iloc[0]
        assert t.reason == "close"
        assert t.close_time.hour == 21  # chiuso dalla logica EOD, non a fine dati
        assert t.close_time < df.index[-1]

    def test_filtro_d1(self):
        # stesso scenario: con trend D1 ribassista il filtro blocca il trade,
        # senza filtro il trade viene eseguito (controllo)
        down_days = []
        for k, c in enumerate([2100, 2080, 2060, 2040, 2020, 2010, 2005]):
            down_days.append(make_m1(f"2024-01-{15+k:02d} 08:00",
                                     [(c + 5, c + 6, c - 1, c)] * 400))
        d2 = make_m1("2024-01-22 08:00", [
            (2005, 2006, 2004, 2005),
            (2005, 2005, 1998, 1999),        # sweep di round_100 a 2000
            (1999, 2001.5, 1998.8, 2001),    # reclaim: close 2001 > 2000.2
            (2001.5, 2002, 2001, 2001.8),
            (2001.8, 2020, 2001, 2019),
        ])
        df = pd.concat(down_days + [d2])
        base = dict(kinds=frozenset({"round_100"}), min_depth=0.0, min_stop=0.1)
        with_filter = bt.run_backtest(
            df, SweepReclaimStrategy(df, cfg(d1_filter=True, **base)), CFG_BT)
        without = bt.run_backtest(
            df, SweepReclaimStrategy(df, cfg(d1_filter=False, **base)), CFG_BT)
        assert len(with_filter.trades) == 0
        assert len(without.trades) == 1
