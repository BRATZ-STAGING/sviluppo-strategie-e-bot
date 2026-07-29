"""Studio RR intraday: entrata limit sul livello, stop piccolo, target rr*stop.

Modello per ogni tocco (primo tocco del livello nella giornata):

- entrata al prezzo del livello (fill del limit al tocco)
- stop a ``stop`` USD oltre il livello, target a ``rr * stop``
- niente overnight: uscita forzata alla candela di ``eod_hour`` UTC al close
- convenzione conservativa: se nella stessa candela sono raggiungibili sia
  stop che target, vale lo stop
- outcome espresso in **R** (multipli dello stop), al netto dello spread

Il risultato per tocco porta con sé le dimensioni di analisi: tipo di
livello, sessione del tocco, confluenza con altri livelli, anno.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import session_of
from .levels import Level, levels_for_day


@dataclass
class RRConfig:
    stop: float = 1.0        # USD oltre il livello
    rr: float = 5.0          # target = rr * stop
    spread: float = 0.30     # USD per round-trip
    eod_hour: int = 21       # uscita forzata (UTC): fine sessione NY
    last_entry_hour: int = 19  # niente ingressi dopo quest'ora (tempo per sviluppare)
    confluence_tol: float = 2.0  # USD: distanza per considerare due livelli in confluenza


def _first_touch_outcome(highs, lows, closes, i_touch, i_eod, price, side,
                         cfg: RRConfig) -> tuple[float, str]:
    """Outcome in R lordo e motivo ('sl'|'tp'|'eod') per un singolo tocco."""
    target = cfg.rr * cfg.stop
    h = highs[i_touch:i_eod]
    l = lows[i_touch:i_eod]
    if side == "above":          # long al supporto
        fav = h - price
        adv = price - l
    else:                        # short alla resistenza
        fav = price - l
        adv = h - price
    hit_sl = adv >= cfg.stop
    hit_tp = fav >= target
    i_sl = int(np.argmax(hit_sl)) if hit_sl.any() else None
    i_tp = int(np.argmax(hit_tp)) if hit_tp.any() else None
    if i_sl is not None and (i_tp is None or i_sl <= i_tp):
        return -1.0, "sl"        # stessa candela: vale lo stop (conservativo)
    if i_tp is not None:
        return float(cfg.rr), "tp"
    # uscita EOD al close dell'ultima candela della finestra
    last_close = closes[i_eod - 1]
    r = (last_close - price) / cfg.stop if side == "above" else (price - last_close) / cfg.stop
    return float(r), "eod"


def day_outcomes(m1: pd.DataFrame, day: pd.Timestamp,
                 levels: list[Level] | None = None,
                 cfg: RRConfig | None = None) -> list[dict]:
    """Outcome del primo tocco di ogni livello nel giorno ``day``."""
    cfg = cfg or RRConfig()
    day = pd.Timestamp(day).tz_convert("UTC").normalize()
    if levels is None:
        levels = levels_for_day(m1, day)
    lo_i = m1.index.searchsorted(day)
    hi_i = m1.index.searchsorted(day + pd.Timedelta(hours=cfg.eod_hour))
    scan = m1.iloc[lo_i:hi_i]
    if len(scan) < 2:
        return []
    idx = scan.index
    highs, lows, closes = scan.high.values, scan.low.values, scan.close.values
    n = len(scan)
    last_entry = int(idx.searchsorted(day + pd.Timedelta(hours=cfg.last_entry_hour)))
    out = []
    for lv in levels:
        p = lv.price
        start_i = max(1, int(idx.searchsorted(lv.active_from)) if lv.active_from > day else 1)
        touched = (lows[start_i:last_entry] <= p) & (highs[start_i:last_entry] >= p)
        if not touched.any():
            continue
        i = start_i + int(np.argmax(touched))
        prev_close = closes[i - 1]
        if prev_close == p:
            continue
        side = "above" if prev_close > p else "below"
        r_gross, reason = _first_touch_outcome(highs, lows, closes, i, n, p, side, cfg)
        # confluenza: un altro livello entro confluence_tol GIÀ ATTIVO al
        # momento del tocco (i livelli asia esistono solo dalle 07:00 —
        # usarli prima sarebbe lookahead)
        t_touch = idx[i]
        near = [o for o in levels
                if o.price != p and abs(o.price - p) <= cfg.confluence_tol
                and o.active_from <= t_touch]
        out.append({
            "day": day, "time": idx[i], "kind": lv.kind, "price": p,
            "side": side, "session": session_of(idx[i]),
            "confluence": bool(near),
            "r_gross": r_gross, "reason": reason,
            "r_net": r_gross - cfg.spread / cfg.stop,
        })
    return out


@dataclass
class ReclaimConfig:
    rr: float = 5.0
    spread: float = 0.30
    eod_hour: int = 21
    last_entry_hour: int = 19
    confluence_tol: float = 2.0
    max_wait: int = 30        # minuti massimi tra tocco e reclaim
    reclaim_margin: float = 0.2  # il close deve superare il livello di così
    stop_buffer: float = 0.3  # stop oltre l'estremo dello sweep
    min_stop: float = 0.8     # sotto: rumore, sopra: non è più "stop piccolo"
    max_stop: float = 3.0


def day_reclaim_outcomes(m1: pd.DataFrame, day: pd.Timestamp,
                         levels: list[Level] | None = None,
                         cfg: ReclaimConfig | None = None) -> list[dict]:
    """Outcome sweep&reclaim: penetrazione del livello + chiusura di recupero.

    Long: prima candela che buca il livello (low < level), poi entro
    ``max_wait`` minuti una chiusura sopra ``level + reclaim_margin``.
    Entrata al close del reclaim, stop sotto il minimo dello sweep
    (- ``stop_buffer``), target a ``rr`` volte il rischio, uscita EOD.
    Short simmetrico. Un solo tentativo per livello al giorno (il primo).
    """
    cfg = cfg or ReclaimConfig()
    day = pd.Timestamp(day).tz_convert("UTC").normalize()
    if levels is None:
        levels = levels_for_day(m1, day)
    lo_i = m1.index.searchsorted(day)
    hi_i = m1.index.searchsorted(day + pd.Timedelta(hours=cfg.eod_hour))
    scan = m1.iloc[lo_i:hi_i]
    if len(scan) < 3:
        return []
    idx = scan.index
    highs, lows, closes = scan.high.values, scan.low.values, scan.close.values
    n = len(scan)
    last_entry = int(idx.searchsorted(day + pd.Timedelta(hours=cfg.last_entry_hour)))
    out = []
    for lv in levels:
        p = lv.price
        start_i = max(1, int(idx.searchsorted(lv.active_from)) if lv.active_from > day else 1)
        for side in ("above", "below"):
            if side == "above":   # sweep del supporto → long
                pierced = lows[start_i:last_entry] < p
            else:                 # sweep della resistenza → short
                pierced = highs[start_i:last_entry] > p
            if not pierced.any():
                continue
            i = start_i + int(np.argmax(pierced))
            # il prezzo deve arrivare dal lato giusto
            if side == "above" and closes[i - 1] <= p:
                continue
            if side == "below" and closes[i - 1] >= p:
                continue
            # cerca il reclaim entro max_wait
            j_end = min(i + cfg.max_wait + 1, last_entry)
            entry_i = None
            for j in range(i, j_end):
                if side == "above" and closes[j] > p + cfg.reclaim_margin:
                    entry_i = j
                    break
                if side == "below" and closes[j] < p - cfg.reclaim_margin:
                    entry_i = j
                    break
            if entry_i is None or entry_i + 1 >= n:
                continue
            entry = closes[entry_i]
            if side == "above":
                swept = lows[i:entry_i + 1].min()
                stop_price = swept - cfg.stop_buffer
                risk = entry - stop_price
            else:
                swept = highs[i:entry_i + 1].max()
                stop_price = swept + cfg.stop_buffer
                risk = stop_price - entry
            if not (cfg.min_stop <= risk <= cfg.max_stop):
                continue
            target = entry + cfg.rr * risk if side == "above" else entry - cfg.rr * risk
            # walk dal bar successivo all'entrata
            h, l = highs[entry_i + 1:n], lows[entry_i + 1:n]
            if side == "above":
                hit_sl, hit_tp = l <= stop_price, h >= target
            else:
                hit_sl, hit_tp = h >= stop_price, l <= target
            i_sl = int(np.argmax(hit_sl)) if hit_sl.any() else None
            i_tp = int(np.argmax(hit_tp)) if hit_tp.any() else None
            if i_sl is not None and (i_tp is None or i_sl <= i_tp):
                r_gross, reason = -1.0, "sl"
            elif i_tp is not None:
                r_gross, reason = float(cfg.rr), "tp"
            else:
                last_close = closes[n - 1]
                r_gross = (last_close - entry) / risk if side == "above" \
                    else (entry - last_close) / risk
                reason = "eod"
            # MFE in R prima dello stop (o fino a EOD): quale TP era raggiungibile
            fav = (h - entry) if side == "above" else (entry - l)
            fav_window = fav[:i_sl] if i_sl is not None else fav
            mfe_r = float(fav_window.max() / risk) if len(fav_window) else 0.0
            t_touch = idx[i]
            near = [o for o in levels
                    if o.price != p and abs(o.price - p) <= cfg.confluence_tol
                    and o.active_from <= t_touch]
            out.append({
                "day": day, "time": idx[entry_i], "kind": lv.kind, "price": p,
                "side": side, "session": session_of(idx[entry_i]),
                "confluence": bool(near), "risk_usd": float(risk),
                "wait_min": int(entry_i - i),
                "sweep_depth": float(p - swept) if side == "above" else float(swept - p),
                "mfe_r": mfe_r,
                "r_gross": r_gross, "reason": reason,
                "r_net": r_gross - cfg.spread / risk,
            })
    return out


def run_reclaim_study(m1: pd.DataFrame,
                      cfg: ReclaimConfig | None = None) -> pd.DataFrame:
    """Studio sweep&reclaim su tutti i giorni."""
    cfg = cfg or ReclaimConfig()
    days = pd.DatetimeIndex(sorted(m1.index.normalize().unique()))
    rows = []
    for day in days:
        rows.extend(day_reclaim_outcomes(m1, day, cfg=cfg))
    df = pd.DataFrame(rows)
    if not df.empty:
        df["year"] = df.time.dt.year
        df["win"] = df.reason == "tp"
    return df


def run_rr_study(m1: pd.DataFrame, cfg: RRConfig | None = None) -> pd.DataFrame:
    """Outcome di tutti i primi tocchi su tutti i giorni. Ritorna un DataFrame."""
    cfg = cfg or RRConfig()
    days = pd.DatetimeIndex(sorted(m1.index.normalize().unique()))
    rows = []
    for day in days:
        rows.extend(day_outcomes(m1, day, cfg=cfg))
    df = pd.DataFrame(rows)
    if not df.empty:
        df["year"] = df.time.dt.year
        df["win"] = df.reason == "tp"
    return df


def aggregate(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Aggrega gli outcome: n, win rate, expectancy netta in R, stabilità annua."""
    if df.empty:
        return pd.DataFrame()
    grp = df.groupby(by)
    out = pd.DataFrame({
        "n": grp.size(),
        "win_rate": grp.win.mean(),
        "exp_r_net": grp.r_net.mean(),
        "eod_share": grp.reason.apply(lambda s: (s == "eod").mean()),
    })
    # in quanti anni l'expectancy netta è positiva (robustezza)
    yearly = df.groupby(by + ["year"]).r_net.mean().unstack("year")
    out["anni_positivi"] = (yearly > 0).sum(axis=1)
    out["anni_totali"] = yearly.notna().sum(axis=1)
    return out.sort_values("exp_r_net", ascending=False)
