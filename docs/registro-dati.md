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

- **File di cache finiti nel posto sbagliato** (causa trovata e corretta il
  06/10/2026): nel file di configurazione di curl le barre `\` del percorso
  Windows sono lette come caratteri speciali, e curl salvava nella cartella
  corrente con nomi storpiati. Corretti `estendi_storico.py`,
  `scarica_indice.py` e `run_spread_orario.py` (percorsi con `/`), con prova.
  I **121 file della cartella del repo sono stati spostati** in
  `C:\Users\gabri\cache_m1` col nome giusto. **Restano da spostare** i 414
  `cache_indici*.bi5` nella radice di `D:\` (vengono da `scarica_indice.py`).
- **M1 oro 2026 oltre il 06/07: incompleto.** Archivio fino al 06/07/2026. In
  `C:\Users\gabri\cache_m1` ci sono 122 file giornalieri 2026: gennaio-luglio
  sparsi, 07/07-17/07 completi e il 12/08. Dukascopy limita (429 e timeout
  per ore dal 06/10). Per finire: `python trading/scripts/riempi_m1_lento.py
  2026-07-18` (un file alla volta, attese crescenti), poi
  `python trading/scripts/estendi_storico.py 2026 2026 --rifai` quando la
  cache copre tutto il 2026. Serve al fuori campione della B con Dukascopy
  (`docs/studies/b-fuori-campione-2026.md`).
- **Registro in avanti** (`grafico_live.py`, avviato il 06/10/2026 sul PC):
  scrive `C:\Users\gabri\dati_grezzi\registro_segnali.jsonl` finche' il PC
  e MT5 (demo MetaQuotes) sono accesi; si ferma a ogni riavvio.

## Script di download

`trading/scripts/`: `download_m1.py`, `download_ticks.py`,
`riempi_cache_indice.py`, `scarica_histdata.py`, `verifica_cache_tick.py`.
Tutti riavviabili (cache su disco): mai ripartire da zero.
