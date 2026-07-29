"""Strategie di riferimento costruite sui livelli.

:class:`LevelBounceStrategy` implementa l'operatività suggerita dallo studio
di reazione: al tocco di un livello del profilo si entra nella direzione del
rimbalzo, stop oltre il livello, target a ``rr * stop``.
"""
from __future__ import annotations

import pandas as pd

from .backtest import Context, Order
from .data import session_of
from .profiles import TradingProfile, daily_plan


class LevelBounceStrategy:
    """Rimbalzo sui livelli del profilo.

    Regole:
    - si opera solo nelle sessioni permesse dal profilo
    - una posizione alla volta, al massimo ``max_trades_per_day`` ingressi
    - al primo tocco di un livello (candela che lo attraversa) si entra
      market nella direzione del rimbalzo: buy se il prezzo arrivava da
      sopra (test di supporto), sell se arrivava da sotto
    - stop a ``stop_usd`` oltre il livello, target a ``rr * stop_usd``
    - ogni livello è tradabile una sola volta al giorno
    """

    def __init__(self, m1: pd.DataFrame, profile: TradingProfile):
        self.m1 = m1
        self.profile = profile
        self._levels: list = []
        self._traded: set[float] = set()
        self._trades_today = 0
        self._prev_close: float | None = None

    def on_day_start(self, ctx: Context, day: pd.Timestamp) -> None:
        plan = daily_plan(self.m1, day, self.profile)
        self._levels = plan.levels
        self._traded = set()
        self._trades_today = 0

    def on_bar(self, ctx: Context, time: pd.Timestamp, bar) -> None:
        prev_close = self._prev_close
        self._prev_close = bar.close
        if prev_close is None:
            return
        if session_of(time) not in self.profile.sessions:
            return
        if ctx.positions:
            return
        if self._trades_today >= self.profile.max_trades_per_day:
            return
        p_stop = self.profile.stop_usd
        for lv in self._levels:
            p = lv.price
            if p in self._traded or lv.active_from > time:
                continue
            if not (bar.low <= p <= bar.high):
                continue
            if prev_close == p:
                continue
            if prev_close > p:
                side, sl, tp = "buy", p - p_stop, p + self.profile.target_usd
            else:
                side, sl, tp = "sell", p + p_stop, p - self.profile.target_usd
            ctx.submit(Order(side=side, type="market", sl=sl, tp=tp,
                             tag=f"{lv.kind}@{p:g}"))
            self._traded.add(p)
            self._trades_today += 1
            break
