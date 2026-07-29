"""Rilevamento livelli di prezzo.

Nota: tutte le funzioni richiedono un DataFrame M1 con indice DatetimeIndex
UTC ordinato e un ``day`` timezone-aware.

Ogni detector produce livelli *attivi per un giorno di trading* usando SOLO
dati precedenti a quel giorno (nessun lookahead). Un livello è un
:class:`Level` con prezzo, tipo e istante di creazione.

Tipi di livello:
- ``round_xx``   : numeri tondi (multipli di 10/25/50/100 USD)
- ``pdh/pdl/pdc``: high/low/close del giorno precedente
- ``pwh/pwl``    : high/low della settimana precedente
- ``asia_h/asia_l``: estremi della sessione asiatica del giorno stesso
                     (disponibili solo dopo le 07:00 UTC)
- ``swing_h/swing_l``: pivot frattali H1 non ancora mitigati
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from .data import resample


@dataclass(frozen=True)
class Level:
    price: float
    kind: str
    created_at: pd.Timestamp
    # istante da cui il livello è utilizzabile (default: created_at)
    active_from: pd.Timestamp = field(default=None)  # type: ignore[assignment]

    def __post_init__(self):
        if self.active_from is None:
            object.__setattr__(self, "active_from", self.created_at)


def round_levels(low: float, high: float, step: float, kind: str,
                 at: pd.Timestamp) -> list[Level]:
    """Numeri tondi multipli di ``step`` dentro [low, high]."""
    if step <= 0:
        raise ValueError("step deve essere positivo")
    first = math.ceil(low / step) * step
    out = []
    price = first
    while price <= high + 1e-9:
        out.append(Level(round(price, 2), kind, at))
        price += step
    return out


def _slice(m1: pd.DataFrame, start: pd.Timestamp | None,
           end: pd.Timestamp | None) -> pd.DataFrame:
    """Slice [start, end) via searchsorted (l'indice è ordinato)."""
    lo = m1.index.searchsorted(start) if start is not None else 0
    hi = m1.index.searchsorted(end) if end is not None else len(m1)
    return m1.iloc[lo:hi]


# sotto questa soglia di candele un "giorno" è una sessione parziale
# (es. apertura della domenica sera) e viene fuso col giorno pieno precedente
MIN_FULL_DAY_BARS = 300


def prev_day_levels(m1: pd.DataFrame, day: pd.Timestamp) -> list[Level]:
    """PDH/PDL/PDC: estremi e chiusura dell'ultimo giorno di trading precedente.

    Se l'ultimo giorno precedente è una sessione parziale (meno di
    ``MIN_FULL_DAY_BARS`` candele, tipicamente la domenica sera), i suoi
    estremi vengono fusi con il giorno pieno che la precede: il PDH/PDL del
    lunedì copre venerdì+domenica, il PDC resta l'ultima chiusura disponibile.
    """
    day = pd.Timestamp(day).tz_convert("UTC").normalize()
    cut = m1.index.searchsorted(day)
    if cut == 0:
        return []
    last_day = m1.index[cut - 1].normalize()
    d = _slice(m1, last_day, day)
    pdc = float(d.close.iloc[-1])
    if len(d) < MIN_FULL_DAY_BARS:
        start_i = m1.index.searchsorted(last_day)
        if start_i > 0:
            full_day = m1.index[start_i - 1].normalize()
            d = _slice(m1, full_day, day)
    return [
        Level(float(d.high.max()), "pdh", day),
        Level(float(d.low.min()), "pdl", day),
        Level(pdc, "pdc", day),
    ]


def prev_week_levels(m1: pd.DataFrame, day: pd.Timestamp) -> list[Level]:
    """PWH/PWL: estremi della settimana ISO precedente a quella di ``day``."""
    day = pd.Timestamp(day).tz_convert("UTC").normalize()
    week_start = day - pd.Timedelta(days=day.weekday())  # lunedì della settimana di `day`
    prev_start = week_start - pd.Timedelta(days=7)
    w = _slice(m1, prev_start, week_start)
    if w.empty:
        return []
    return [
        Level(float(w.high.max()), "pwh", week_start),
        Level(float(w.low.min()), "pwl", week_start),
    ]


def asia_session_levels(m1: pd.DataFrame, day: pd.Timestamp) -> list[Level]:
    """Estremi della sessione asiatica (00:00–07:00 UTC) di ``day``.

    Attivi solo da fine sessione (07:00) per evitare lookahead.
    """
    day = pd.Timestamp(day).tz_convert("UTC").normalize()
    end = day + pd.Timedelta(hours=7)
    s = _slice(m1, day, end)
    if s.empty:
        return []
    return [
        Level(float(s.high.max()), "asia_h", day, active_from=end),
        Level(float(s.low.min()), "asia_l", day, active_from=end),
    ]


def swing_levels(m1: pd.DataFrame, day: pd.Timestamp, k: int = 3,
                 lookback_days: int = 20) -> list[Level]:
    """Pivot frattali H1 non mitigati nel lookback prima di ``day``.

    Un pivot high è una candela H1 con high strettamente maggiore delle ``k``
    candele prima e dopo; simmetrico per i pivot low. Un pivot è "mitigato"
    se il prezzo lo ha ritoccato dopo la formazione (high successivo >= pivot
    high, o low successivo <= pivot low).
    """
    day = pd.Timestamp(day).tz_convert("UTC").normalize()
    start = day - pd.Timedelta(days=lookback_days)
    window = _slice(m1, start, day)
    if window.empty:
        return []
    h1 = resample(window, "1h")
    if len(h1) < 2 * k + 1:
        return []
    highs = h1.high.values
    lows = h1.low.values
    out: list[Level] = []
    for i in range(k, len(h1) - k):
        t = h1.index[i]
        if highs[i] == max(highs[i - k:i + k + 1]) and \
                (highs[i - k:i] < highs[i]).all() and (highs[i + 1:i + k + 1] < highs[i]).all():
            if not (highs[i + k + 1:] >= highs[i]).any():
                out.append(Level(float(highs[i]), "swing_h", t, active_from=day))
        if lows[i] == min(lows[i - k:i + k + 1]) and \
                (lows[i - k:i] > lows[i]).all() and (lows[i + 1:i + k + 1] > lows[i]).all():
            if not (lows[i + k + 1:] <= lows[i]).any():
                out.append(Level(float(lows[i]), "swing_l", t, active_from=day))
    return out


def levels_for_day(m1: pd.DataFrame, day: pd.Timestamp,
                   round_steps: dict[str, float] | None = None,
                   include: set[str] | None = None) -> list[Level]:
    """Tutti i livelli attivi per il giorno ``day``.

    ``round_steps`` mappa kind→step, default {'round_50': 50, 'round_100': 100}.
    ``include`` filtra i kind restituiti (None = tutti).
    """
    day = pd.Timestamp(day).tz_convert("UTC").normalize()
    if round_steps is None:
        round_steps = {"round_50": 50.0, "round_100": 100.0}
    out: list[Level] = []
    out += prev_day_levels(m1, day)
    out += prev_week_levels(m1, day)
    out += asia_session_levels(m1, day)
    out += swing_levels(m1, day)
    cut = m1.index.searchsorted(day)
    if cut > 0:
        last_day = _slice(m1, m1.index[cut - 1].normalize(), day)
        lo, hi = float(last_day.low.min()), float(last_day.high.max())
        margin = max(hi - lo, 10.0)  # estende il range al possibile movimento odierno
        seen: set[float] = set()
        # dallo step più grande al più piccolo: un prezzo appartiene solo al
        # kind più "importante" (2000 è round_100, non anche round_50)
        for kind, step in sorted(round_steps.items(), key=lambda kv: -kv[1]):
            for lv in round_levels(lo - margin, hi + margin, step, kind, day):
                if lv.price not in seen:
                    seen.add(lv.price)
                    out.append(lv)
    if include is not None:
        out = [lv for lv in out if lv.kind in include]
    return out
