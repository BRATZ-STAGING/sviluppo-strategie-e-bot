# Storico XAUUSD — Candele M1 (Dukascopy)

Candele M1 **BID** di XAUUSD scaricate dal datafeed pubblico Dukascopy
(`datafeed.dukascopy.com`), un file Parquet per anno.

## Copertura

- Periodo: 2020-01-01 → 2026-07-06 (UTC)
- Fonte: file giornalieri `BID_candles_min_1.bi5` (candele M1 aggregate da
  Dukascopy a partire dai tick del proprio feed)
- I minuti senza scambi (mercato chiuso: sabato, festività, gap del weekend)
  sono stati rimossi.

## Schema

| colonna     | tipo                 | note                          |
|-------------|----------------------|-------------------------------|
| `timestamp` | timestamp UTC (ns)   | apertura del minuto           |
| `open`      | float64              | prezzo BID                    |
| `high`      | float64              | prezzo BID                    |
| `low`       | float64              | prezzo BID                    |
| `close`     | float64              | prezzo BID                    |
| `volume`    | float64              | volume Dukascopy (milioni di unità) |

Compressione: zstd. Lettura: `pd.read_parquet("XAUUSD_M1_2024.parquet")`.

## Note

- I prezzi originali Dukascopy sono interi in millesimi (scala 1/1000).
- Il feed usa mesi 0-based negli URL (`/2024/00/…` = gennaio 2024).
- Lo storico tick grezzo (file orari `..h_ticks.bi5`) è disponibile dalla
  stessa fonte ma non è versionato qui per dimensioni; queste M1 sono
  l'aggregazione ufficiale Dukascopy degli stessi tick.
