import pandas as pd
import pytest

from framework import backtest as bt
from conftest import make_m1


class Noop:
    def on_day_start(self, ctx, day): pass
    def on_bar(self, ctx, time, bar): pass


class SubmitOnce(Noop):
    """Invia un ordine alla prima candela."""
    def __init__(self, order):
        self.order = order
        self.sent = False

    def on_bar(self, ctx, time, bar):
        if not self.sent:
            ctx.submit(self.order)
            self.sent = True


CFG = bt.BacktestConfig(spread=0.0, initial_equity=10_000, risk_per_trade=0.01)


class TestOrderValidation:
    def test_side_non_valido(self):
        with pytest.raises(ValueError):
            bt.Order(side="long", sl=1)

    def test_type_non_valido(self):
        with pytest.raises(ValueError):
            bt.Order(side="buy", type="stop", sl=1)

    def test_limit_senza_prezzo(self):
        with pytest.raises(ValueError):
            bt.Order(side="buy", type="limit", sl=1)

    def test_sl_obbligatorio(self):
        with pytest.raises(ValueError):
            bt.Order(side="buy")


class TestExecution:
    def test_market_riempie_ad_apertura_successiva(self):
        df = make_m1("2024-01-02 08:00", [
            (2000, 2001, 1999, 2000),
            (2002, 2003, 2001, 2002),   # fill atteso a 2002
            (2002, 2003, 2001, 2002),
        ])
        strat = SubmitOnce(bt.Order(side="buy", sl=1990.0))
        res = bt.run_backtest(df, strat, CFG)
        assert len(res.trades) == 1
        assert res.trades.iloc[0].entry == 2002.0

    def test_sizing_dal_rischio(self):
        df = make_m1("2024-01-02 08:00", [(2000, 2001, 1999, 2000)] * 3)
        strat = SubmitOnce(bt.Order(side="buy", sl=1998.0))  # stop a 2 USD
        res = bt.run_backtest(df, strat, CFG)
        # rischio 1% di 10000 = 100 USD / 2 USD = 50 unità
        assert res.trades.iloc[0]["size"] == pytest.approx(50.0)

    def test_limit_buy_riempie_al_limite(self):
        df = make_m1("2024-01-02 08:00", [
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1994, 1996),   # low 1994 <= limite 1995
            (1996, 1997, 1995, 1996),
        ])
        strat = SubmitOnce(bt.Order(side="buy", type="limit", price=1995.0, sl=1990.0))
        res = bt.run_backtest(df, strat, CFG)
        assert res.trades.iloc[0].entry == 1995.0

    def test_limit_buy_gap_migliorativo(self):
        df = make_m1("2024-01-02 08:00", [
            (2000, 2001, 1999, 2000),
            (1990, 1991, 1989, 1990),   # apre sotto il limite: fill a 1990
            (1990, 1991, 1989, 1990),
        ])
        strat = SubmitOnce(bt.Order(side="buy", type="limit", price=1995.0, sl=1980.0))
        res = bt.run_backtest(df, strat, CFG)
        assert res.trades.iloc[0].entry == 1990.0

    def test_limit_non_toccato_resta_pendente(self):
        df = make_m1("2024-01-02 08:00", [(2000, 2001, 1999, 2000)] * 3)
        strat = SubmitOnce(bt.Order(side="buy", type="limit", price=1900.0, sl=1890.0))
        res = bt.run_backtest(df, strat, CFG)
        assert len(res.trades) == 0

    def test_sell_limit(self):
        df = make_m1("2024-01-02 08:00", [
            (2000, 2001, 1999, 2000),
            (2000, 2006, 2000, 2004),   # high 2006 >= limite 2005
            (2004, 2005, 2003, 2004),
        ])
        strat = SubmitOnce(bt.Order(side="sell", type="limit", price=2005.0, sl=2015.0))
        res = bt.run_backtest(df, strat, CFG)
        assert res.trades.iloc[0].entry == 2005.0
        assert res.trades.iloc[0].side == "sell"


class TestStopTake:
    def _run(self, bars, order):
        df = make_m1("2024-01-02 08:00", bars)
        return bt.run_backtest(df, SubmitOnce(order), CFG)

    def test_stop_loss(self):
        res = self._run([
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1999, 2000),         # fill 2000
            (2000, 2001, 1994, 1995),         # sl 1995 colpito
        ], bt.Order(side="buy", sl=1995.0, tp=2010.0))
        t = res.trades.iloc[0]
        assert t.reason == "sl" and t.exit == 1995.0
        assert t.pnl == pytest.approx(-5.0 * t["size"])

    def test_take_profit(self):
        res = self._run([
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1999, 2000),
            (2000, 2011, 2000, 2010),         # tp 2010 colpito
        ], bt.Order(side="buy", sl=1995.0, tp=2010.0))
        t = res.trades.iloc[0]
        assert t.reason == "tp" and t.exit == 2010.0

    def test_stessa_candela_vince_lo_stop(self):
        res = self._run([
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1999, 2000),
            (2000, 2015, 1990, 2000),         # sl e tp entrambi raggiungibili
        ], bt.Order(side="buy", sl=1995.0, tp=2010.0))
        assert res.trades.iloc[0].reason == "sl"

    def test_gap_oltre_lo_stop(self):
        res = self._run([
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1999, 2000),
            (1985, 1986, 1984, 1985),         # apre sotto lo stop: esce a 1985
        ], bt.Order(side="buy", sl=1995.0, tp=2010.0))
        assert res.trades.iloc[0].exit == 1985.0

    def test_short_stop_e_take(self):
        res = self._run([
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1989, 1990),         # tp short a 1990
        ], bt.Order(side="sell", sl=2005.0, tp=1990.0))
        t = res.trades.iloc[0]
        assert t.side == "sell" and t.reason == "tp" and t.exit == 1990.0
        assert t.pnl > 0

    def test_chiusura_forzata_a_fine_dati(self):
        res = self._run([
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1999, 2003),
        ], bt.Order(side="buy", sl=1990.0))
        t = res.trades.iloc[0]
        assert t.reason == "close" and t.exit == 2003.0


class TestMinStopDistance:
    def test_fill_troppo_vicino_allo_stop_rifiutato(self):
        # decisione con stop a 2 USD, ma il mercato apre a 0.2 dallo stop
        df = make_m1("2024-01-02 08:00", [
            (2000, 2001, 1999, 2000),
            (1998.2, 1999, 1998, 1998.5),   # fill 1998.2, sl 1998 → dist 0.2 < 0.5
            (1998.5, 1999, 1998, 1998.5),
        ])
        strat = SubmitOnce(bt.Order(side="buy", sl=1998.0))
        res = bt.run_backtest(df, strat, CFG)
        assert len(res.trades) == 0

    def test_fill_oltre_lo_stop_rifiutato(self):
        # gap: il fill è già sotto lo stop del buy
        df = make_m1("2024-01-02 08:00", [
            (2000, 2001, 1999, 2000),
            (1990, 1991, 1989, 1990),       # fill 1990 < sl 1995
            (1990, 1991, 1989, 1990),
        ])
        strat = SubmitOnce(bt.Order(side="buy", sl=1995.0))
        res = bt.run_backtest(df, strat, CFG)
        assert len(res.trades) == 0

    def test_short_fill_vicino_allo_stop_rifiutato(self):
        df = make_m1("2024-01-02 08:00", [
            (2000, 2001, 1999, 2000),
            (2004.8, 2005, 2004, 2004.9),   # sell: sl 2005 - fill 2004.8 = 0.2
            (2004.9, 2005, 2004, 2004.9),
        ])
        strat = SubmitOnce(bt.Order(side="sell", sl=2005.0))
        res = bt.run_backtest(df, strat, CFG)
        assert len(res.trades) == 0


class TestCosts:
    def test_spread_sottratto(self):
        cfg = bt.BacktestConfig(spread=0.5, initial_equity=10_000, risk_per_trade=0.01)
        df = make_m1("2024-01-02 08:00", [
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1999, 2000),
            (2000, 2011, 2000, 2010),
        ])
        strat = SubmitOnce(bt.Order(side="buy", sl=1995.0, tp=2010.0))
        res = bt.run_backtest(df, strat, cfg)
        t = res.trades.iloc[0]
        assert t.pnl == pytest.approx((2010 - 2000) * t["size"] - 0.5 * t["size"])


class TestLimits:
    def test_max_positions(self):
        class TwoOrders(Noop):
            def __init__(self):
                self.n = 0
            def on_bar(self, ctx, time, bar):
                if self.n < 2:
                    ctx.submit(bt.Order(side="buy", sl=bar.close - 5))
                    self.n += 1
        df = make_m1("2024-01-02 08:00", [(2000, 2001, 1999, 2000)] * 5)
        res = bt.run_backtest(df, TwoOrders(), CFG)
        assert len(res.trades) == 1  # la seconda è rifiutata da max_positions=1

    def test_close_all(self):
        class CloseAtBar3(Noop):
            def __init__(self):
                self.i = 0
            def on_bar(self, ctx, time, bar):
                if self.i == 0:
                    ctx.submit(bt.Order(side="buy", sl=bar.close - 5))
                if self.i == 3:
                    ctx.close_all()
                self.i += 1
        df = make_m1("2024-01-02 08:00", [
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1999, 2001),
            (2001, 2002, 2000, 2002),
            (2002, 2004, 2001, 2004),   # close_all eseguito su questa candela
            (2004, 2005, 2003, 2004),
        ])
        res = bt.run_backtest(df, CloseAtBar3(), CFG)
        t = res.trades.iloc[0]
        assert t.reason == "close" and t.exit == 2004.0

    def test_cancel_all(self):
        class CancelNext(Noop):
            def __init__(self):
                self.i = 0
            def on_bar(self, ctx, time, bar):
                if self.i == 0:
                    ctx.submit(bt.Order(side="buy", type="limit", price=1900.0, sl=1890.0))
                if self.i == 1:
                    assert len(ctx.pending) == 1
                    ctx.cancel_all()
                self.i += 1
        df = make_m1("2024-01-02 08:00", [(2000, 2001, 1999, 2000)] * 4)
        res = bt.run_backtest(df, CancelNext(), CFG)
        assert len(res.trades) == 0


class TestResult:
    def test_summary_metriche(self):
        df = make_m1("2024-01-02 08:00", [
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1999, 2000),
            (2000, 2011, 2000, 2010),
        ])
        strat = SubmitOnce(bt.Order(side="buy", sl=1995.0, tp=2010.0))
        res = bt.run_backtest(df, strat, CFG)
        s = res.summary()
        assert s["trades"] == 1
        assert s["win_rate"] == 1.0
        assert s["final_equity"] > 10_000
        assert s["max_drawdown"] >= 0.0

    def test_senza_trade(self):
        df = make_m1("2024-01-02 08:00", [(2000, 2001, 1999, 2000)] * 3)
        res = bt.run_backtest(df, Noop(), CFG)
        s = res.summary()
        assert s["trades"] == 0
        assert s["final_equity"] == 10_000
        assert s["total_return"] == 0.0

    def test_equity_curve_giornaliera(self):
        d1 = make_m1("2024-01-02 08:00", [(2000, 2001, 1999, 2000)] * 2)
        d2 = make_m1("2024-01-03 08:00", [(2000, 2001, 1999, 2000)] * 2)
        res = bt.run_backtest(pd.concat([d1, d2]), Noop(), CFG)
        assert len(res.equity_curve) == 2
