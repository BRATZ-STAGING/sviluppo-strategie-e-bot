# Registro dati

Cosa c'e', dove sta, che difetti ha. Lo aggiorna la chat **Dati** a ogni
blocco chiuso. Prima di scaricare qualcosa, controllare qui se c'e' gia'.

## Dove stanno i dati

| dati | percorso | periodo | note |
|---|---|---|---|
| Oro M1 (Dukascopy, BID, UTC) | `data/XAUUSD_M1/*.parquet` | 2009-2026 | in GitHub; `XAU_ANNI` limita gli anni caricati |
| S&P, Nasdaq, DAX, argento M1 (HistData) | `data/histdata/<SIMBOLO>/` | 2010-11 → 2026-09 | **solo sul PC, mai pubblicare** (licenza personale); difetti in `data/histdata/README.md` |
| 7 cambi + Nikkei, FTSE, CAC, Euro Stoxx (HistData) | `D:\histdata_parquet\` | 2010-2026 | ~720 MB; solo sul PC |
| ZIP originali HistData | `D:\histdata\` | — | contiene anche `vecchi_parquet_utc_sbagliato` (NON usare) |
| Candele scoperta/verifica "ricerca da zero" | `D:\ricerca_zero\` | 2009-2017 / 2018-2026 | |
| Candele ricerca FX intraday | `D:\ricerca_fx\` | idem | periodo 2018-2026 dei cambi gia' consumato |
| Paniere multi-giorno (12 mercati) | `D:\ricerca_multi\` | | |
| Ricerca macro | `D:\ricerca_macro\` | | |
| Altro su D: | `D:\dukascopy\`, `D:\dati_grezzi\` | | da descrivere alla prima chat Dati |

## Difetti noti (leggere prima di usare)

- HistData e' in **ora di New York CON ora legale**, non EST fisso: gia'
  convertito in UTC nei parquet attuali.
- **GRXEUR 15/06/2020 → 03/12/2023 non e' il DAX** (e' un altro indice).
- **ETXEUR** contiene l'IBEX dal 17/12/2018.
- SPXUSD molto bucato fino al 2014 e nel 2017.
- Dukascopy: URL con mese 0-based; le raffiche danno 429/503 per ore → usare
  `trading/scripts/riempi_cache_indice.py` lento (PARALLELO basso, PAUSA).

## Problemi aperti

- **File di cache finiti nel posto sbagliato**: 121 file `.bi5` con nomi tipo
  `Usersgabrisviluppo-strategie-e-bot..cache_m1<data>.bi5` nella cartella
  principale del repo e 414 `cache_indici*.bi5` nella radice di `D:\`. Il
  percorso della cache perde le barre (probabile percorso Windows passato
  male da uno script/shell). Da sistemare in una chat Dati: correggere il
  percorso, spostare i file nella cache giusta, verificare che i downloader
  li ritrovino.

## Script di download

`trading/scripts/`: `download_m1.py`, `download_ticks.py`,
`riempi_cache_indice.py`, `scarica_histdata.py`, `verifica_cache_tick.py`.
Tutti riavviabili (cache su disco): mai ripartire da zero.
