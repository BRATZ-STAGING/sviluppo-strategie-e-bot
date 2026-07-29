#!/usr/bin/env python3
"""Demo della fase G: backtest della LevelBounceStrategy su dati reali.

Uso: python3 run_backtest_demo.py [profilo] [anni...]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from framework.backtest import BacktestConfig, run_backtest
from framework.data import load_m1
from framework.profiles import DEFAULT_PROFILES
from framework.strategies import LevelBounceStrategy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def main():
    profile_name = sys.argv[1] if len(sys.argv) > 1 else "london-reversal"
    years = [int(y) for y in sys.argv[2:]] or None
    profile = DEFAULT_PROFILES[profile_name]
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"), years=years)
    print(f"profilo: {profile_name} — candele: {len(m1):,} "
          f"({m1.index[0]:%Y-%m-%d} -> {m1.index[-1]:%Y-%m-%d})")
    cfg = BacktestConfig(spread=0.30)
    res = run_backtest(m1, LevelBounceStrategy(m1, profile), cfg)
    for k, v in res.summary().items():
        print(f"{k:>15}: {v:,.4f}" if isinstance(v, float) else f"{k:>15}: {v}")
    if len(res.trades):
        print("\nper tipo di livello:")
        by_kind = res.trades.assign(kind=res.trades.tag.str.split("@").str[0]) \
            .groupby("kind").pnl.agg(["count", "sum", "mean"])
        print(by_kind.to_string(float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
