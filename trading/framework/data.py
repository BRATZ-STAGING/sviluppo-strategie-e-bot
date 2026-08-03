"""Data layer: caricamento Parquet M1, resampling, sessioni.

Convenzioni:
- indice DatetimeIndex UTC, colonne open/high/low/close/volume (float64)
- le candele sono etichettate con l'orario di APERTURA del periodo
"""
from __future__ import annotations

import glob
import os
import sys

import pandas as pd

OHLCV_AGG = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
}

# Sessioni in ore UTC [inizio, fine)
SESSIONS = {
    "asia": (0, 7),
    "london": (7, 12),
    "ny": (12, 21),
    "late": (21, 24),
}

# Timeframe canonici del progetto. Include i TF NON nativi di MT5 (M33, M66):
# qui sono cittadini di prima classe, per MT5 andranno esportati come custom.
TIMEFRAMES = {
    "M1": "1min", "M3": "3min", "M6": "6min", "M10": "10min", "M12": "12min",
    "M20": "20min", "M33": "33min", "M66": "66min",
    "H1": "1h", "H2": "2h", "H3": "3h", "H6": "6h", "H12": "12h", "D1": "1D",
}


def anni_da_env() -> list[int] | None:
    """Anni richiesti via ``XAU_ANNI`` ("2020-2026" oppure "2020,2021"), o None.

    Serve a fissare la finestra di uno studio SENZA toccarne il codice: da
    quando l'archivio contiene anche il 2009-2019, ``load_m1`` senza argomenti
    caricherebbe tutto e i numeri pubblicati (calcolati sul 2020-2026) non
    sarebbero piu' riproducibili.
    """
    spec = os.environ.get("XAU_ANNI", "").strip()
    if not spec:
        return None
    anni: list[int] = []
    for pezzo in spec.split(","):
        pezzo = pezzo.strip()
        if "-" in pezzo:
            a, b = pezzo.split("-", 1)
            anni.extend(range(int(a), int(b) + 1))
        elif pezzo:
            anni.append(int(pezzo))
    return sorted(set(anni))


def load_m1(path: str, years: list[int] | None = None) -> pd.DataFrame:
    """Carica le candele M1 dai Parquet annuali.

    ``path`` è la cartella con i file ``XAUUSD_M1_<anno>.parquet``.
    ``years`` limita gli anni caricati; se è None si usa la variabile
    d'ambiente ``XAU_ANNI``, e in sua assenza tutti gli anni presenti.
    """
    if years is None:
        years = anni_da_env()
    files = sorted(glob.glob(os.path.join(path, "XAUUSD_M1_*.parquet")))
    if years is not None:
        wanted = {str(y) for y in years}
        files = [f for f in files if os.path.basename(f)[10:14] in wanted]
    if not files:
        raise FileNotFoundError(f"nessun Parquet M1 in {path} (years={years})")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df = df.set_index("timestamp").sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    validate_ohlcv(df)
    # riga su stderr: nessun risultato deve restare ambiguo su QUALE storico
    # e' stato usato, ora che l'archivio copre 2009-2026
    print(f"[M1] {df.index[0]:%Y-%m-%d} -> {df.index[-1]:%Y-%m-%d}, "
          f"{len(df):,} candele", file=sys.stderr)
    return df


def validate_ohlcv(df: pd.DataFrame) -> None:
    """Verifica invarianti di base; solleva ValueError se violate."""
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"colonne mancanti: {missing}")
    if not df.index.is_monotonic_increasing:
        raise ValueError("indice non ordinato")
    if df.index.has_duplicates:
        raise ValueError("timestamp duplicati")
    bad = ~(
        (df.high >= df.low)
        & (df.high >= df.open)
        & (df.high >= df.close)
        & (df.low <= df.open)
        & (df.low <= df.close)
    )
    if bad.any():
        raise ValueError(f"{int(bad.sum())} candele con OHLC incoerenti")


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resampling OHLCV (es. '5min', '33min', '2h', '1D'); scarta i bin vuoti.

    I bin sono ancorati all'epoch: per timeframe che non dividono il giorno
    (M33, M66) questo garantisce che le candele siano SEMPRE le stesse, a
    prescindere da quali anni si caricano. Senza ancoraggio pandas parte dal
    primo timestamp presente e gli studi non sarebbero riproducibili.
    """
    out = df.resample(rule, origin="epoch").agg(OHLCV_AGG).dropna(subset=["open"])
    return out


def resample_tf(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Resampling su un timeframe canonico del progetto (chiave di TIMEFRAMES)."""
    if tf not in TIMEFRAMES:
        raise ValueError(f"timeframe sconosciuto: {tf} (validi: {sorted(TIMEFRAMES)})")
    return resample(df, TIMEFRAMES[tf])


def session_of(ts: pd.Timestamp) -> str:
    """Sessione di appartenenza di un timestamp UTC."""
    h = ts.hour
    for name, (start, end) in SESSIONS.items():
        if start <= h < end:
            return name
    raise ValueError(f"ora fuori range: {ts}")


def add_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge la colonna 'session' (asia/london/ny/late) in base all'ora UTC."""
    out = df.copy()
    hours = out.index.hour
    session = pd.Series("late", index=out.index, dtype=object)
    for name, (start, end) in SESSIONS.items():
        session[(hours >= start) & (hours < end)] = name
    out["session"] = session
    return out
