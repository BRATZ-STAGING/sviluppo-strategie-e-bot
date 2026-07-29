"""Meta-sistema: generazione segnali delle due meccaniche + selettore mensile.

I generatori producono segnali CAUSALI (ogni segnale usa solo dati fino al
proprio istante). Il selettore mensile sceglie la meccanica da tradare nel
mese M usando esclusivamente i trade dei ``trailing_months`` precedenti.
``MetaSignalStrategy`` esegue i segnali della meccanica attiva nel motore
event-driven (fill, costi, una posizione alla volta).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import Context, Order
from .data import resample_tf
from .rr_study import ReclaimConfig, run_reclaim_study
from .structure import state_at, trend_state_series
from .vwap import anchored_vwap

SPREAD, BUF = 0.30, 0.3
REV_KINDS = ["pdl", "pdc", "swing_l", "asia_l", "round_100", "round_50", "pwl"]


def continuation_signals(m1: pd.DataFrame) -> pd.DataFrame:
    """Segnali continuation: time (istante decisione), entry_ref, sl, tp, r_est.

    Setup: H6+H2 uptrend, pullback M6 sul VWAP giornaliero, candela di
    conferma, impulso di giornata >= 4$, rischio 1-10$, TP 3R, max 3/giorno.
    ``r_est`` è l'esito netto stimato a livello di studio (per il trailing).
    """
    m6 = resample_tf(m1, "M6")
    m6["vwap_d"] = anchored_vwap(m6, "day")
    h6 = state_at(trend_state_series(resample_tf(m1, "H6"), 3, "6h"),
                  m6.index + pd.Timedelta("6min"))
    h2 = state_at(trend_state_series(resample_tf(m1, "H2"), 3, "2h"),
                  m6.index + pd.Timedelta("6min"))
    m1_idx = m1.index
    m1h, m1l, m1c = m1.high.values, m1.low.values, m1.close.values
    hi, lo, cl = m6.high.values, m6.low.values, m6.close.values
    vd = m6.vwap_d.values
    idx = m6.index
    hours, days = idx.hour, idx.normalize()
    rows, last_sig, day_count, day_start_i = [], None, {}, 0
    for i in range(1, len(m6)):
        if days[i] != days[i - 1]:
            day_start_i = i
        if not (7 <= hours[i] < 19) or h6[i] != 1 or h2[i] != 1 or np.isnan(vd[i]):
            continue
        if day_count.get(days[i], 0) >= 3:
            continue
        t_sig = idx[i] + pd.Timedelta("6min")
        if last_sig is not None and (t_sig - last_sig) < pd.Timedelta("30min"):
            continue
        if not (lo[i] <= vd[i] and cl[i] > vd[i] and cl[i] > hi[i - 1]):
            continue
        imp = float(hi[day_start_i:i].max() - vd[i]) if i > day_start_i else 0.0
        if imp < 4.0:
            continue
        j0 = max(day_start_i, i - 5)
        entry = float(cl[i])
        stop = float(lo[j0:i + 1].min() - BUF)
        risk = entry - stop
        if not (1.0 <= risk <= 10.0):
            continue
        i0 = int(m1_idx.searchsorted(t_sig))
        i1 = int(m1_idx.searchsorted(days[i] + pd.Timedelta(hours=21)))
        if i1 - i0 < 2:
            continue
        last_sig = t_sig
        day_count[days[i]] = day_count.get(days[i], 0) + 1
        target = entry + 3.0 * risk
        h_, l_ = m1h[i0:i1], m1l[i0:i1]
        hit_sl, hit_tp = l_ <= stop, h_ >= target
        i_sl = int(np.argmax(hit_sl)) if hit_sl.any() else None
        i_tp = int(np.argmax(hit_tp)) if hit_tp.any() else None
        if i_sl is not None and (i_tp is None or i_sl <= i_tp):
            r = -1.0
        elif i_tp is not None:
            r = 3.0
        else:
            r = float((m1c[i1 - 1] - entry) / risk)
        rows.append({"time": t_sig, "entry_ref": entry, "sl": stop,
                     "tp": target, "r_est": r - SPREAD / risk})
    return pd.DataFrame(rows)


def reversion_signals(m1: pd.DataFrame) -> pd.DataFrame:
    """Segnali reversion (sweep&reclaim long supporti, depth>=1$, london+ny, 5R)."""
    cfg = ReclaimConfig()
    df = run_reclaim_study(m1, cfg)
    if df.empty:
        return pd.DataFrame(columns=["time", "entry_ref", "sl", "tp", "r_est"])
    sel = df[(df.side == "above") & df.kind.isin(REV_KINDS)
             & (df.sweep_depth >= 1.0) & df.session.isin(["london", "ny"])].copy()
    # ricostruzione di entry/stop/target dal dettaglio dello studio:
    # stop = minimo sweep - buffer = (price - depth) - buffer; entry = stop + risk
    sel["sl"] = (sel.price - sel.sweep_depth) - cfg.stop_buffer
    sel["entry_ref"] = sel.sl + sel.risk_usd
    sel["tp"] = sel.entry_ref + cfg.rr * sel.risk_usd
    out = sel[["time", "entry_ref", "sl", "tp", "r_net"]] \
        .rename(columns={"r_net": "r_est"})
    # il time dello studio è il label (apertura) della candela di reclaim:
    # la decisione avviene alla sua chiusura
    out["time"] = out.time + pd.Timedelta("1min")
    return out.sort_values("time").reset_index(drop=True)


def monthly_picks(streams: dict[str, pd.DataFrame], trailing_months: int = 6,
                  min_trades: int = 12) -> dict[pd.Period, str | None]:
    """Meccanica scelta per ogni mese usando solo i mesi precedenti."""
    monthly = {}
    for name, df in streams.items():
        monthly[name] = df.assign(month=df.time.dt.tz_localize(None)
                                  .dt.to_period("M"))
    months = sorted(set().union(*[set(d.month) for d in monthly.values()]))
    picks: dict[pd.Period, str | None] = {}
    for m in months:
        best, best_exp = None, 0.0
        for name, d in monthly.items():
            trail = d[(d.month < m) & (d.month >= m - trailing_months)]
            if len(trail) >= min_trades and trail.r_est.mean() > best_exp:
                best, best_exp = name, float(trail.r_est.mean())
        picks[m] = best
    return picks


@dataclass
class MetaConfig:
    trailing_months: int = 6
    min_trades: int = 12
    eod_close_hour: int = 21
    signal_tolerance_min: int = 4   # minuti di tolleranza per bar mancanti


class MetaSignalStrategy:
    """Esegue nel motore i segnali della meccanica attiva del mese.

    ``signals`` (dict nome -> DataFrame time/sl/tp) e ``picks`` possono
    essere iniettati per i test; di default vengono calcolati da ``m1``.
    """

    def __init__(self, m1: pd.DataFrame, cfg: MetaConfig | None = None,
                 signals: dict[str, pd.DataFrame] | None = None,
                 picks: dict | None = None):
        self.cfg = cfg or MetaConfig()
        if signals is None:
            signals = {"cont": continuation_signals(m1),
                       "rev": reversion_signals(m1)}
        self.signals = signals
        self.picks = picks if picks is not None else \
            monthly_picks(signals, self.cfg.trailing_months, self.cfg.min_trades)
        # coda unica ordinata: (istante decisione, meccanica, sl, tp)
        rows = []
        for name, df in signals.items():
            for _, r in df.iterrows():
                rows.append((r.time, name, float(r.sl), float(r.tp)))
        rows.sort(key=lambda x: x[0])
        self._queue = rows
        self._qi = 0
        self._eod_done = False

    def on_day_start(self, ctx: Context, day: pd.Timestamp) -> None:
        self._eod_done = False

    def on_bar(self, ctx: Context, time: pd.Timestamp, bar) -> None:
        cfg = self.cfg
        if time.hour >= cfg.eod_close_hour:
            if not self._eod_done and (ctx.positions or ctx.pending):
                ctx.cancel_all()
                ctx.close_all()
                self._eod_done = True
            return
        bar_close_t = time + pd.Timedelta("1min")
        tol = pd.Timedelta(minutes=cfg.signal_tolerance_min)
        while self._qi < len(self._queue) and self._queue[self._qi][0] <= bar_close_t:
            t_sig, mech, sl, tp = self._queue[self._qi]
            self._qi += 1
            if bar_close_t - t_sig > tol:
                continue  # segnale scaduto (candele mancanti)
            month = t_sig.tz_localize(None).to_period("M") if t_sig.tz else \
                t_sig.to_period("M")
            if self.picks.get(month) != mech:
                continue
            if ctx.positions or ctx.pending:
                continue  # una posizione alla volta: segnale perso
            if bar.close - sl < 0.5:
                continue
            ctx.submit(Order(side="buy", type="market", sl=sl, tp=tp, tag=mech))
