# Sessione 2026-07-10/11 — Download tick e consegna (PASSAGGIO DI CONSEGNE)

## Contesto per la prossima sessione (leggere PER PRIMO)

Il cliente (Gabriele) ha chiesto i **tick grezzi XAUUSD bid+ask** da Dukascopy
per validare un bot con ordini limit e SL/TP piccoli (i backtest su M1 gonfiano
i fill: WR 47% su M1 vs 31% su tick, misurato da lui). Specifica completa in
`docs/sessions/` precedenti e nella richiesta originale.

### Dove siamo ESATTAMENTE

- **Download in corso sul PC di Gabriele** (Windows, cartella `C:\dukascopy`),
  NON in questo ambiente cloud. Il cloud NON riesce a scaricare: IP proxy
  bannato + container effimero. Il PC di casa sì, ma solo con la **firma TLS
  Chrome** (`curl_cffi`): il datafeed Dukascopy lascia in timeout i client
  non-browser. Questa è la scoperta chiave, già nel downloader v3.
- **Stato**: finestra prioritaria 2022-11-01→2026-07-06 completata a
  `ok=10670 empty=2930 fail=48` su 27.648 ore. I ~48 fail sono ore sparse
  (rate-limiter), IRRILEVANTI per il backtest: si annotano come "buchi noti".
- Ultimo tentativo di recupero dei 48: rilancio con `PACING=4`,
  `BREAK_AFTER=999` (disattiva il circuit-breaker, ritenta costante).

### Prossimi passi (nell'ordine)

1. Gabriele comprime `C:\dukascopy\ticks_cache` in **ZIP** e la carica su
   **Google Drive** (Drive è collegato a queste sessioni via MCP). Poi scrive
   "caricato".
2. Scaricare lo zip da Drive (mcp Google_Drive: search_files +
   download_file_content), estrarlo in scratchpad.
3. Eseguire `trading/scripts/build_tick_csv.py <out_dir> 2022-11 2026-07`
   (TICKS_CACHE = cartella estratta). Genera CSV mensili
   `XAUUSD_ticks_YYYY-MM.csv` (colonne `timestamp_utc,bid,ask`, ISO ms Z),
   README con conteggi/buchi, zip annuali.
4. **Verifiche obbligatorie** prima di consegnare: ask>=bid su tutto;
   cross-check tick→M1 con `data/XAUUSD_M1/*.parquet` (i bid aggregati a M1
   devono ridare le candele — già verificato su un campione, rifarlo dopo il
   build); conteggio tick per file coerente (~25-30M/anno).
5. Consegnare gli zip annuali con SendUserFile (status proactive).
6. **Seconda tranche** (se il cliente conferma): backfill 2020-01→2022-10,
   stesso metodo dal PC.

### Trappole già viste (NON ripetere)

- Il downloader nel cloud è inutile (ban IP). NON rilanciarlo qui, NON
  ri-armare trigger di check-in cloud (il trigger orario è già disattivato).
- `build_tick_csv.py` ha già il fix int64 sui timestamp (bug overflow int32).
- Formato tick Dukascopy: record 20B `>3i2f` = (ms_offset, ask, bid, volAsk,
  volBid), prezzi /1000. ATTENZIONE ordine: p1=ask, p2=bid.

## Fase H del framework: COMPLETATA (indipendente dai tick)

Meta-sistema `framework/meta.py` (MetaSignalStrategy) + walk-forward:
backtest nel motore = WR 31,9%, PF 1,18, +80% su 6,5 anni, maxDD 19,4%,
134 test verdi. Tutto pushato. I tick serviranno a ri-validare con fill
realistici (fase futura). Dettagli in `docs/studies/rr-intraday-study.md`.
