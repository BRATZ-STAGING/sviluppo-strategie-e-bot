import pandas as pd
import pytest

from framework import backtest as bt
from framework.profiles import TradingProfile
from framework.strategies import LevelBounceStrategy
from conftest import make_m1

CFG = bt.BacktestConfig(spread=0.0, initial_equity=10_000, risk_per_trade=0.01)

PROFILE = TradingProfile(
    name="test", sessions=frozenset({"london"}),
    level_kinds=frozenset({"pdl", "pdh"}),
    stop_usd=2.0, rr=2.0, max_trades_per_day=2,
)


def two_day_df(day2_closes, start_hour=8):
    """Giorno 1 fissa pdl=1990/pdh=2010; giorno 2 con le chiusure date."""
    d1 = make_m1("2024-01-02 08:00", [
        (2000, 2010, 1990, 2005),
        (2005, 2006, 2004, 2005),
    ])
    d2 = make_m1(f"2024-01-03 {start_hour:02d}:00",
                 [(c, c + 0.4, c - 0.4, c) for c in day2_closes])
    return pd.concat([d1, d2])


class TestLevelBounce:
    def test_buy_su_pdl(self):
        closes = [1995, 1993, 1990.2, 1992, 1994, 1994]
        df = two_day_df(closes)
        strat = LevelBounceStrategy(df, PROFILE)
        res = bt.run_backtest(df, strat, CFG)
        assert len(res.trades) == 1
        t = res.trades.iloc[0]
        assert t.side == "buy"
        assert t.tag == "pdl@1990"

    def test_sell_su_pdh(self):
        closes = [2005, 2008, 2009.8, 2008, 2006, 2006]
        df = two_day_df(closes)
        res = bt.run_backtest(df, LevelBounceStrategy(df, PROFILE), CFG)
        assert len(res.trades) == 1
        assert res.trades.iloc[0].side == "sell"
        assert res.trades.iloc[0].tag == "pdh@2010"

    def test_fuori_sessione_niente_trade(self):
        closes = [1995, 1993, 1990.2, 1992, 1994, 1994]
        df = two_day_df(closes, start_hour=13)  # sessione NY, profilo london
        res = bt.run_backtest(df, LevelBounceStrategy(df, PROFILE), CFG)
        assert len(res.trades) == 0

    def test_livello_tradato_una_sola_volta(self):
        # due tocchi del pdl nello stesso giorno: un solo trade su quel livello
        closes = [1995, 1990.2, 1994, 1994, 1990.2, 1994, 1994, 1994]
        df = two_day_df(closes)
        res = bt.run_backtest(df, LevelBounceStrategy(df, PROFILE), CFG)
        assert list(res.trades.tag) == ["pdl@1990"]

    def test_stop_e_target_dal_profilo(self):
        closes = [1995, 1993, 1990.2, 1992, 1994, 1994]
        df = two_day_df(closes)

        captured = {}
        orig = bt.Engine.submit
        def spy(self, order):
            captured["order"] = order
            orig(self, order)
        bt.Engine.submit = spy
        try:
            bt.run_backtest(df, LevelBounceStrategy(df, PROFILE), CFG)
        finally:
            bt.Engine.submit = orig
        o = captured["order"]
        assert o.sl == 1990.0 - 2.0
        assert o.tp == 1990.0 + 4.0

    def test_una_posizione_alla_volta(self):
        # pdl e pdh toccati in rapida successione: il secondo ingresso è
        # bloccato finché la prima posizione è aperta
        closes = [1995, 1990.2, 1995, 2005, 2009.8, 2005, 2005]
        df = two_day_df(closes)
        profile = TradingProfile(
            name="wide", sessions=frozenset({"london"}),
            level_kinds=frozenset({"pdl", "pdh"}),
            stop_usd=50.0, rr=2.0, max_trades_per_day=5,
        )
        res = bt.run_backtest(df, LevelBounceStrategy(df, profile), CFG)
        assert list(res.trades.tag) == ["pdl@1990"]
