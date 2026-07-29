"""Profili operativi e workflow giornaliero.

Un :class:`TradingProfile` descrive COME si opera (sessioni permesse, tipi di
livello usati, rischio, rapporto rischio/rendimento). Il workflow giornaliero
(:func:`daily_plan`) traduce il profilo nel piano operativo del giorno: i
livelli attivi filtrati e ordinati.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .data import SESSIONS
from .levels import Level, levels_for_day


@dataclass(frozen=True)
class TradingProfile:
    name: str
    sessions: frozenset[str]          # sessioni in cui è permesso entrare
    level_kinds: frozenset[str]       # tipi di livello considerati
    risk_per_trade: float = 0.01      # frazione dell'equity rischiata per trade
    rr: float = 2.0                   # take profit = rr * stop
    stop_usd: float = 1.5             # distanza stop dal livello (USD)
    max_trades_per_day: int = 3

    def __post_init__(self):
        unknown = self.sessions - set(SESSIONS)
        if unknown:
            raise ValueError(f"sessioni sconosciute: {sorted(unknown)}")
        if not 0 < self.risk_per_trade <= 0.05:
            raise ValueError("risk_per_trade fuori range (0, 0.05]")
        if self.rr <= 0 or self.stop_usd <= 0:
            raise ValueError("rr e stop_usd devono essere positivi")

    @property
    def target_usd(self) -> float:
        return self.rr * self.stop_usd


DEFAULT_PROFILES: dict[str, TradingProfile] = {
    "london-reversal": TradingProfile(
        name="london-reversal",
        sessions=frozenset({"london"}),
        level_kinds=frozenset({"pdh", "pdl", "asia_h", "asia_l"}),
    ),
    "ny-levels": TradingProfile(
        name="ny-levels",
        sessions=frozenset({"ny"}),
        level_kinds=frozenset({"pdh", "pdl", "pdc", "round_50", "round_100"}),
    ),
    "swing-daily": TradingProfile(
        name="swing-daily",
        sessions=frozenset({"london", "ny"}),
        level_kinds=frozenset({"pwh", "pwl", "swing_h", "swing_l"}),
        rr=3.0,
        stop_usd=3.0,
        max_trades_per_day=1,
    ),
}


@dataclass
class DailyPlan:
    day: pd.Timestamp
    profile: TradingProfile
    levels: list[Level] = field(default_factory=list)


def daily_plan(m1: pd.DataFrame, day: pd.Timestamp,
               profile: TradingProfile) -> DailyPlan:
    """Piano del giorno: livelli attivi filtrati per il profilo."""
    day = pd.Timestamp(day).tz_convert("UTC").normalize()
    levels = levels_for_day(m1, day, include=set(profile.level_kinds))
    levels.sort(key=lambda lv: lv.price)
    return DailyPlan(day=day, profile=profile, levels=levels)
