import pandas as pd
import pytest

from framework import backtest as bt
from framework.meta import MetaConfig, MetaSignalStrategy, monthly_picks
from conftest import make_m1


def stream(times_r):
    return pd.DataFrame({
        "time": [pd.Timestamp(t, tz="UTC") for t, _ in times_r],
        "sl": 1.0, "tp": 2.0,
        "r_est": [r for _, r in times_r],
    })


class TestMonthlyPicks:
    def test_sceglie_la_migliore(self):
        # gennaio-giugno: cont positiva, rev negativa -> a luglio sceglie cont
        cont = stream([(f"2024-0{m}-10 08:00", 0.5) for m in range(1, 7)] * 3)
        rev = stream([(f"2024-0{m}-11 08:00", -0.5) for m in range(1, 7)] * 3)
        picks = monthly_picks({"cont": cont, "rev": rev}, 6, 12)
        assert picks[pd.Period("2024-06")] == "cont"

    def test_flat_se_nessuna_positiva(self):
        cont = stream([(f"2024-0{m}-10 08:00", -0.2) for m in range(1, 7)] * 3)
        rev = stream([(f"2024-0{m}-11 08:00", -0.5) for m in range(1, 7)] * 3)
        picks = monthly_picks({"cont": cont, "rev": rev}, 6, 12)
        assert picks[pd.Period("2024-06")] is None

    def test_flat_se_campione_insufficiente(self):
        cont = stream([("2024-01-10 08:00", 1.0), ("2024-02-10 08:00", 1.0)])
        picks = monthly_picks({"cont": cont}, 6, 12)
        # con soli 2 trade nel trailing nessun mese raggiunge min_trades
        assert all(v is None for v in picks.values())


class TestMetaSignalStrategy:
    def _run(self, picks_value):
        # segnale alle 08:02 (decisione al close della candela 08:01)
        df = make_m1("2024-01-03 08:00", [
            (2000, 2001, 1999, 2000),
            (2000, 2001, 1999, 2000.5),
            (2000.5, 2002, 2000, 2001),   # fill atteso qui (open 2000.5)
            (2001, 2007, 2000.5, 2006),   # tp 2005 colpito
            (2006, 2007, 2005, 2006),
        ])
        signals = {"cont": pd.DataFrame({
            "time": [pd.Timestamp("2024-01-03 08:02", tz="UTC")],
            "sl": [1995.0], "tp": [2005.0], "r_est": [1.0],
        })}
        picks = {pd.Period("2024-01"): picks_value}
        strat = MetaSignalStrategy(df, signals=signals, picks=picks)
        return bt.run_backtest(df, strat, bt.BacktestConfig(spread=0.0))

    def test_esegue_il_segnale_della_meccanica_attiva(self):
        res = self._run("cont")
        assert len(res.trades) == 1
        t = res.trades.iloc[0]
        assert t.entry == 2000.5 and t.reason == "tp" and t.tag == "cont"

    def test_ignora_se_mese_flat(self):
        res = self._run(None)
        assert len(res.trades) == 0

    def test_ignora_se_meccanica_diversa(self):
        res = self._run("rev")
        assert len(res.trades) == 0

    def test_chiusura_eod(self):
        bars = [(2000, 2001, 1999, 2000.5)] * 3 + [(2000.5, 2001, 2000, 2000.8)] * 3
        df = make_m1("2024-01-03 20:57", bars)
        signals = {"cont": pd.DataFrame({
            "time": [pd.Timestamp("2024-01-03 20:58", tz="UTC")],
            "sl": [1995.0], "tp": [2050.0], "r_est": [1.0],
        })}
        strat = MetaSignalStrategy(df, signals=signals,
                                   picks={pd.Period("2024-01"): "cont"})
        res = bt.run_backtest(df, strat, bt.BacktestConfig(spread=0.0))
        assert len(res.trades) == 1
        t = res.trades.iloc[0]
        assert t.reason == "close" and t.close_time.hour == 21
