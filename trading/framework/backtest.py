"""Fase G — Simulatore di backtest event-driven su candele M1.

Modello di esecuzione (documentato e volutamente conservativo):

- I prezzi delle candele sono BID. Lo spread è un costo fisso per round-trip
  (``spread * size``) sottratto al PnL del trade.
- Ordini market inviati durante ``on_bar`` (candela chiusa) vengono eseguiti
  all'apertura della candela successiva.
- Ordini limit: un buy-limit riempie quando ``low <= price``, un sell-limit
  quando ``high >= price``; prezzo di riempimento = prezzo limite (se
  l'apertura salta oltre il limite, si usa l'apertura, che è migliorativa).
- Stop loss e take profit sono valutati su high/low della candela; se nella
  stessa candela sono raggiungibili entrambi vale la convenzione peggiore:
  PRIMA lo stop.
- Position sizing: ``size = equity * risk_per_trade / distanza_stop``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import pandas as pd


@dataclass
class BacktestConfig:
    spread: float = 0.30            # USD per unità, costo round-trip
    initial_equity: float = 10_000.0
    risk_per_trade: float = 0.01
    max_positions: int = 1
    # distanza minima fill→stop: se il prezzo di riempimento è più vicino di
    # così allo stop (o già oltre), l'ordine viene rifiutato. Evita posizioni
    # enormi quando il mercato si muove verso lo stop tra decisione e fill.
    min_stop_distance: float = 0.5


@dataclass
class Order:
    side: str                 # 'buy' | 'sell'
    type: str = "market"      # 'market' | 'limit'
    price: float | None = None  # richiesto per i limit
    sl: float | None = None
    tp: float | None = None
    tag: str = ""

    def __post_init__(self):
        if self.side not in ("buy", "sell"):
            raise ValueError(f"side non valido: {self.side}")
        if self.type not in ("market", "limit"):
            raise ValueError(f"type non valido: {self.type}")
        if self.type == "limit" and self.price is None:
            raise ValueError("un ordine limit richiede price")
        if self.sl is None:
            raise ValueError("stop loss obbligatorio (sizing basato sul rischio)")


@dataclass
class Position:
    side: str
    entry: float
    sl: float
    tp: float | None
    size: float
    open_time: pd.Timestamp
    tag: str = ""


@dataclass
class Trade:
    side: str
    entry: float
    exit: float
    size: float
    open_time: pd.Timestamp
    close_time: pd.Timestamp
    pnl: float
    reason: str               # 'sl' | 'tp' | 'close'
    tag: str = ""


class Strategy(Protocol):
    def on_day_start(self, ctx: "Context", day: pd.Timestamp) -> None: ...
    def on_bar(self, ctx: "Context", time: pd.Timestamp, bar) -> None: ...


class Context:
    """API esposta alla strategia durante il backtest."""

    def __init__(self, engine: "Engine"):
        self._engine = engine

    @property
    def equity(self) -> float:
        return self._engine.equity

    @property
    def positions(self) -> list[Position]:
        return list(self._engine.positions)

    @property
    def pending(self) -> list[Order]:
        return list(self._engine.pending)

    @property
    def trades(self) -> list[Trade]:
        return list(self._engine.trades)

    def submit(self, order: Order) -> None:
        self._engine.submit(order)

    def cancel_all(self) -> None:
        self._engine.pending.clear()

    def close_all(self) -> None:
        self._engine.close_requested = True


@dataclass
class Result:
    trades: pd.DataFrame
    equity_curve: pd.Series
    config: BacktestConfig

    def summary(self) -> dict:
        t = self.trades
        eq = self.equity_curve
        out = {
            "trades": len(t),
            "final_equity": float(eq.iloc[-1]) if len(eq) else self.config.initial_equity,
            "total_return": float(eq.iloc[-1] / self.config.initial_equity - 1) if len(eq) else 0.0,
        }
        if len(t):
            wins = t[t.pnl > 0]
            losses = t[t.pnl <= 0]
            gross_win = wins.pnl.sum()
            gross_loss = -losses.pnl.sum()
            out.update({
                "win_rate": len(wins) / len(t),
                "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
                "expectancy": float(t.pnl.mean()),
                "max_drawdown": float(((eq.cummax() - eq) / eq.cummax()).max()),
            })
        return out


class Engine:
    def __init__(self, cfg: BacktestConfig | None = None):
        self.cfg = cfg or BacktestConfig()
        self.equity = self.cfg.initial_equity
        self.positions: list[Position] = []
        self.pending: list[Order] = []
        self.trades: list[Trade] = []
        self._market_queue: list[Order] = []
        self.close_requested = False

    def submit(self, order: Order) -> None:
        if order.type == "market":
            self._market_queue.append(order)
        else:
            self.pending.append(order)

    def _size_for(self, entry: float, sl: float) -> float:
        dist = abs(entry - sl)
        if dist <= 0:
            return 0.0
        return self.equity * self.cfg.risk_per_trade / dist

    def _open(self, order: Order, fill: float, time: pd.Timestamp) -> None:
        if len(self.positions) >= self.cfg.max_positions:
            return
        # distanza fill→stop firmata: negativa se il fill è già oltre lo stop
        dist = fill - order.sl if order.side == "buy" else order.sl - fill
        if dist < self.cfg.min_stop_distance:
            return
        size = self._size_for(fill, order.sl)
        if size <= 0:
            return
        self.positions.append(Position(order.side, fill, order.sl, order.tp,
                                       size, time, order.tag))

    def _close(self, pos: Position, price: float, time: pd.Timestamp, reason: str) -> None:
        direction = 1.0 if pos.side == "buy" else -1.0
        pnl = (price - pos.entry) * direction * pos.size - self.cfg.spread * pos.size
        self.equity += pnl
        self.trades.append(Trade(pos.side, pos.entry, price, pos.size,
                                 pos.open_time, time, pnl, reason, pos.tag))
        self.positions.remove(pos)

    def _process_bar(self, time: pd.Timestamp, o: float, h: float, lo: float, c: float) -> None:
        # 1) market in coda dalla candela precedente: fill all'apertura
        for order in self._market_queue:
            self._open(order, o, time)
        self._market_queue.clear()
        # 2) limit pendenti
        still = []
        for order in self.pending:
            hit = (order.side == "buy" and lo <= order.price) or \
                  (order.side == "sell" and h >= order.price)
            if hit:
                if order.side == "buy":
                    fill = min(order.price, o)  # gap sotto il limite → apertura
                else:
                    fill = max(order.price, o)
                self._open(order, fill, time)
            else:
                still.append(order)
        self.pending = still
        # 3) stop/take sulle posizioni aperte (convenzione: prima lo stop)
        for pos in list(self.positions):
            if pos.side == "buy":
                sl_hit = lo <= pos.sl
                tp_hit = pos.tp is not None and h >= pos.tp
                if sl_hit:
                    self._close(pos, min(pos.sl, o), time, "sl")
                elif tp_hit:
                    self._close(pos, max(pos.tp, o), time, "tp")
            else:
                sl_hit = h >= pos.sl
                tp_hit = pos.tp is not None and lo <= pos.tp
                if sl_hit:
                    self._close(pos, max(pos.sl, o), time, "sl")
                elif tp_hit:
                    self._close(pos, min(pos.tp, o), time, "tp")
        # 4) chiusura richiesta dalla strategia (al close della candela)
        if self.close_requested:
            for pos in list(self.positions):
                self._close(pos, c, time, "close")
            self.close_requested = False


def run_backtest(m1: pd.DataFrame, strategy: Strategy,
                 cfg: BacktestConfig | None = None) -> Result:
    engine = Engine(cfg)
    ctx = Context(engine)
    idx = m1.index
    opens, highs, lows, closes = (m1.open.values, m1.high.values,
                                  m1.low.values, m1.close.values)
    days = idx.normalize()
    equity_marks: list[tuple[pd.Timestamp, float]] = []
    current_day = None
    for i, row in enumerate(m1.itertuples()):
        t = idx[i]
        if days[i] != current_day:
            if current_day is not None:
                equity_marks.append((current_day, engine.equity))
            current_day = days[i]
            strategy.on_day_start(ctx, current_day)
        engine._process_bar(t, opens[i], highs[i], lows[i], closes[i])
        strategy.on_bar(ctx, t, row)
    # chiusura forzata a fine dati
    if len(m1):
        last_t, last_c = idx[-1], closes[-1]
        for pos in list(engine.positions):
            engine._close(pos, last_c, last_t, "close")
        equity_marks.append((current_day, engine.equity))
    trades = pd.DataFrame([vars(tr) for tr in engine.trades])
    curve = pd.Series(dict(equity_marks), name="equity", dtype=float).sort_index() \
        if equity_marks else pd.Series(dtype=float, name="equity")
    return Result(trades=trades, equity_curve=curve, config=engine.cfg)
