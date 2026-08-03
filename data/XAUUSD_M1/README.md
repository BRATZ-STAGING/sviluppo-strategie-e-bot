# Storico XAUUSD — Candele M1 (Dukascopy)

Candele M1 **BID** di XAUUSD scaricate dal datafeed pubblico Dukascopy
(`datafeed.dukascopy.com`), un file Parquet per anno.

## Copertura

- Periodo: **2009-01-01 → 2026-07-06** (UTC), 6,24 milioni di candele
- Fonte: file giornalieri `BID_candles_min_1.bi5` (candele M1 aggregate da
  Dukascopy a partire dai tick del proprio feed)
- I minuti senza scambi (mercato chiuso: sabato, festività, gap del weekend)
  sono stati rimossi.
- Gli anni **2009-2019** sono stati aggiunti il 03/08/2026 con
  `trading/scripts/estendi_storico.py`, che percorre lo stesso identico
  endpoint: sul giorno di controllo 2020-06-10 riproduce le 1.379 candele
  già in archivio con differenza massima **0,0** su tutte e cinque le
  colonne. Copertura 309-314 giornate l'anno e 1.130-1.170 minuti al giorno,
  gli stessi valori del 2020-2026.
- Riscontro con la storia nota dell'oro: massimo **1920,66 il 06/09/2011** e
  minimo **1046,23 nel 2015**, entrambi al centesimo.
- `XAU_ANNI` limita gli anni caricati da `framework.data.load_m1` senza
  toccare il codice di uno studio: `XAU_ANNI=2020-2026` riproduce i numeri
  pubblicati prima dell'estensione.

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
