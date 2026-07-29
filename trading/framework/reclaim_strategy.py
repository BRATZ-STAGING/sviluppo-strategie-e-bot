"""Strategia sweep & reclaim intraday sul motore event-driven.

Meccanica (per i long; short simmetrico se abilitato):

1. il prezzo arriva da sopra e buca un livello del set configurato
2. entro ``max_wait`` minuti una candela chiude sopra ``livello + reclaim_margin``
3. ingresso market (fill all'apertura successiva), stop sotto il minimo dello
   sweep - ``stop_buffer``, target a ``rr`` volte il rischio
4. il rischio deve stare in [``min_stop``, ``max_stop``] e lo sweep deve
   essere profondo almeno ``min_depth``
5. niente ingressi dopo ``last_entry_hour``; chiusura forzata di tutto a
   ``eod_close_hour`` (niente overnight)
6. filtro opzionale di momentum D1: long solo se il close di ieri è sopra
   il close di ``d1_lookback`` sedute prima
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .backtest import Context, Order
from .data import resample, session_of
from .levels import levels_for_day


@dataclass
class ReclaimStrategyConfig:
    kinds: frozenset[str] = frozenset({"pdl", "pdc", "swing_l", "asia_l",
                                       "round_100", "round_50", "pwl"})
    sessions: frozenset[str] = frozenset({"london", "ny"})
    long_only: bool = True
    rr: float = 5.0
    min_depth: float = 1.0       # profondità minima dello sweep (USD)
    reclaim_margin: float = 0.2
    stop_buffer: float = 0.3
    min_stop: float = 0.8
    max_stop: float = 3.0
    max_wait: int = 30           # minuti tra sweep e reclaim
    last_entry_hour: int = 19    # UTC
    eod_close_hour: int = 21     # UTC: chiusura forzata
    max_trades_per_day: int = 3
    d1_filter: bool = True       # momentum giornaliero
    d1_lookback: int = 5


class _LevelState:
    __slots__ = ("level", "swept_extreme", "deadline", "done")

    def __init__(self, level):
        self.level = level
        self.swept_extreme: float | None = None
        self.deadline: pd.Timestamp | None = None
        self.done = False


class SweepReclaimStrategy:
    def __init__(self, m1: pd.DataFrame, cfg: ReclaimStrategyConfig | None = None):
        self.m1 = m1
        self.cfg = cfg or ReclaimStrategyConfig()
        if not self.cfg.long_only:
            raise NotImplementedError("lato short non ancora implementato")
        self._states: list[_LevelState] = []
        self._trades_today = 0
        self._prev_close: float | None = None
        self._d1_ok = True
        self._eod_done = False

    def _momentum_ok(self, day: pd.Timestamp) -> bool:
        if not self.cfg.d1_filter:
            return True
        cut = self.m1.index.searchsorted(day)
        past = self.m1.iloc[max(0, cut - 60_000):cut]  # ~40 sedute di M1 bastano
        if past.empty:
            return False
        d1 = resample(past, "1D")
        if len(d1) < self.cfg.d1_lookback + 1:
            return False
        return bool(d1.close.iloc[-1] > d1.close.iloc[-1 - self.cfg.d1_lookback])

    def on_day_start(self, ctx: Context, day: pd.Timestamp) -> None:
        levels = levels_for_day(self.m1, day, include=set(self.cfg.kinds))
        self._states = [_LevelState(lv) for lv in levels]
        self._trades_today = 0
        self._d1_ok = self._momentum_ok(day)
        self._eod_done = False

    def on_bar(self, ctx: Context, time: pd.Timestamp, bar) -> None:
        cfg = self.cfg
        prev_close = self._prev_close
        self._prev_close = bar.close
        # chiusura forzata EOD (una sola volta al giorno)
        if time.hour >= cfg.eod_close_hour:
            if not self._eod_done and (ctx.positions or ctx.pending):
                ctx.cancel_all()
                ctx.close_all()
                self._eod_done = True
            return
        if prev_close is None or not self._d1_ok:
            return
        entering_allowed = (
            time.hour < cfg.last_entry_hour
            and session_of(time) in cfg.sessions
            and not ctx.positions
            and self._trades_today < cfg.max_trades_per_day
        )
        for st in self._states:
            if st.done:
                continue
            p = st.level.price
            if st.level.active_from > time:
                continue
            if st.swept_extreme is None:
                # in attesa dello sweep: il prezzo deve arrivare da sopra
                if bar.low < p and prev_close > p:
                    st.swept_extreme = bar.low
                    st.deadline = time + pd.Timedelta(minutes=cfg.max_wait)
                continue
            # sweep in corso: aggiorna l'estremo e cerca il reclaim
            st.swept_extreme = min(st.swept_extreme, bar.low)
            if time > st.deadline:
                st.done = True
                continue
            if bar.close > p + cfg.reclaim_margin:
                st.done = True
                depth = p - st.swept_extreme
                stop_price = st.swept_extreme - cfg.stop_buffer
                risk = bar.close - stop_price
                if depth < cfg.min_depth or not (cfg.min_stop <= risk <= cfg.max_stop):
                    continue
                if not entering_allowed:
                    continue
                target = bar.close + cfg.rr * risk
                ctx.submit(Order(side="buy", type="market", sl=stop_price,
                                 tp=target, tag=f"{st.level.kind}@{p:g}"))
                self._trades_today += 1
                entering_allowed = False
