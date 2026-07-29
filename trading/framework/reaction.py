"""Studio di reazione dei livelli.

Per ogni livello attivo in una giornata individua i *tocchi* (candele M1 che
attraversano il prezzo del livello) e misura la reazione successiva in una
finestra di ``window_min`` minuti:

- ``bounce``      : massima escursione favorevole (rimbalzo) rispetto al livello
- ``penetration`` : massima escursione avversa oltre il livello
- ``success``     : il rimbalzo raggiunge ``bounce_target`` PRIMA che la
                    penetrazione superi ``stop_penetration`` (nella stessa
                    candela vale la convenzione conservativa: prima l'avverso)

La classifica aggrega i tocchi per tipo di livello.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .levels import Level, levels_for_day


@dataclass
class StudyConfig:
    window_min: int = 60          # finestra di osservazione post-tocco (minuti)
    bounce_target: float = 3.0    # USD di rimbalzo per considerare "successo"
    stop_penetration: float = 1.5 # USD di penetrazione che invalida la reazione
    cooldown_min: int = 60        # minuti di attesa tra tocchi dello stesso livello
    min_touches: int = 30         # tocchi minimi perché un kind entri in classifica


@dataclass
class Touch:
    time: pd.Timestamp
    level: Level
    side: str            # 'above' = prezzo arriva da sopra (test di supporto)
    bounce: float
    penetration: float
    success: bool


def _measure(bars_h: np.ndarray, bars_l: np.ndarray, price: float, side: str,
             cfg: StudyConfig) -> tuple[float, float, bool]:
    """Misura bounce/penetration/success su una finestra di candele."""
    if side == "above":
        fav = bars_h - price   # rimbalzo verso l'alto
        adv = price - bars_l   # penetrazione sotto il livello
    else:
        fav = price - bars_l
        adv = bars_h - price
    bounce = float(max(fav.max(), 0.0))
    penetration = float(max(adv.max(), 0.0))
    success = False
    for f, a in zip(fav, adv):
        if a > cfg.stop_penetration:
            break  # stop violato prima del target (convenzione conservativa)
        if f >= cfg.bounce_target:
            success = True
            break
    return bounce, penetration, success


def touches_for_day(m1: pd.DataFrame, day: pd.Timestamp,
                    levels: list[Level] | None = None,
                    cfg: StudyConfig | None = None) -> list[Touch]:
    """Tutti i tocchi dei livelli attivi nel giorno ``day``."""
    cfg = cfg or StudyConfig()
    day = pd.Timestamp(day).tz_convert("UTC").normalize()
    if levels is None:
        levels = levels_for_day(m1, day)
    day_end = day + pd.Timedelta(days=1)
    # include la finestra post-tocco anche oltre la mezzanotte
    lo_i = m1.index.searchsorted(day)
    hi_i = m1.index.searchsorted(day_end + pd.Timedelta(minutes=cfg.window_min))
    scan = m1.iloc[lo_i:hi_i]
    idx = scan.index
    n_day = int(idx.searchsorted(day_end))
    if n_day == 0:
        return []
    highs, lows, closes = scan.high.values, scan.low.values, scan.close.values
    out: list[Touch] = []
    for lv in levels:
        p = lv.price
        start_i = 0
        if lv.active_from > day:
            start_i = int(idx.searchsorted(lv.active_from))
        touched = (lows[:n_day] <= p) & (highs[:n_day] >= p)
        cooldown_until = -1
        for i in np.nonzero(touched)[0]:
            if i < max(start_i, 1):  # serve la candela precedente per la direzione
                continue
            if i <= cooldown_until:
                continue
            prev_close = closes[i - 1]
            if prev_close == p:
                continue  # direzione ambigua
            side = "above" if prev_close > p else "below"
            j = min(i + cfg.window_min, len(scan) - 1)
            if j <= i:
                continue
            bounce, pen, success = _measure(highs[i:j + 1], lows[i:j + 1], p, side, cfg)
            out.append(Touch(idx[i], lv, side, bounce, pen, success))
            cooldown_until = i + cfg.cooldown_min
    return out


def run_study(m1: pd.DataFrame, cfg: StudyConfig | None = None,
              days: pd.DatetimeIndex | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Esegue lo studio su tutti i giorni disponibili.

    Ritorna ``(classifica, touches_df)``: la classifica per tipo di livello e
    il dettaglio di tutti i tocchi.
    """
    cfg = cfg or StudyConfig()
    if days is None:
        days = pd.DatetimeIndex(sorted(m1.index.normalize().unique()))
    rows = []
    for day in days:
        for t in touches_for_day(m1, day, cfg=cfg):
            rows.append({
                "time": t.time, "kind": t.level.kind, "price": t.level.price,
                "side": t.side, "bounce": t.bounce, "penetration": t.penetration,
                "success": t.success,
            })
    touches = pd.DataFrame(rows)
    if touches.empty:
        return pd.DataFrame(), touches
    grp = touches.groupby("kind")
    ranking = pd.DataFrame({
        "touches": grp.size(),
        "success_rate": grp.success.mean(),
        "median_bounce": grp.bounce.median(),
        "median_penetration": grp.penetration.median(),
    })
    # atteso per tocco, in USD, con target/stop della config
    ranking["expectancy"] = (ranking.success_rate * cfg.bounce_target
                             - (1 - ranking.success_rate) * cfg.stop_penetration)
    ranking = ranking[ranking.touches >= cfg.min_touches]
    ranking = ranking.sort_values(["success_rate", "touches"], ascending=False)
    return ranking, touches
