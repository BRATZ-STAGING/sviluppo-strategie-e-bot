# Trading Framework XAUUSD — guida per le sessioni

## Stato del progetto (leggere PRIMA di riscoprire qualcosa)

- **Stato corrente e storia**: `docs/sessions/` (nota più recente = verità),
  `docs/master-spec.md` (architettura e fasi), `docs/studies/` (risultati:
  NON rifare studi già fatti, i numeri sono lì).
- Codice in `trading/framework/`, script in `trading/scripts/`, test:
  `cd trading && python3 -m pytest tests/ -q` (134 test al 2026-07-07).
- Dati M1 **2009→2026** in `data/XAUUSD_M1/*.parquet` (BID, UTC, un file/anno),
  6,24 milioni di candele. `XAU_ANNI=2020-2026` limita gli anni caricati senza
  toccare il codice: serve a riprodurre i numeri pubblicati prima
  dell'estensione. Ogni `load_m1` stampa su stderr il periodo effettivo.
- Dipendenze: `pip install pandas pyarrow pytest tabulate` (non in repo).

## Chat per aree e "chiudi il blocco"

Ogni chat fa UN blocco di un'area (Regia, Ricerca, Backtest, Dati, App):
regole e prompt di apertura in `docs/COME-USARE-LE-CHAT.md`. Piano in
`docs/piano-di-lavoro.md`, dati in `docs/registro-dati.md`.

Quando l'utente scrive **"chiudi il blocco"**:
1. aggiornare il file di stato dell'area (studio in `docs/studies/`, MASTER
   del bot, `docs/registro-dati.md` o `app/README.md`);
2. aggiungere una riga al registro di `docs/piano-di-lavoro.md` e aggiornare
   `docs/RIPRENDI-QUI.md` se cambia il punto di ripresa;
3. commit locale dei soli file toccati (niente push);
4. dire all'utente in 3 righe cosa e' stato fatto, il prossimo blocco
   consigliato e che puo' archiviare la chat.

## Smistamento del lavoro (sotto-agenti in `.claude/agents/`)

La sessione principale (Opus, impegno alto: `.claude/settings.json`) pianifica
e smista; modello e impegno di ogni lavoro li fissa il sotto-agente.

| lavoro | sotto-agente | modello / impegno |
|---|---|---|
| controllare se uno studio e' gia' fatto o respinto | `archivista` | Haiku |
| nuove idee, analisi, registrazioni preventive, studi | `ricercatore-quant` | Fable / xhigh |
| revisione avversariale, cercare falle, validare risultati | `verificatore` | Fable / high |
| web app `app/` e grafico live | `sviluppatore-webapp` | Sonnet / high |
| script, test, rigenerazioni, modifiche meccaniche | `esecutore` | Sonnet / medium |

Regole: (1) `archivista` PRIMA di ogni nuovo studio; (2) `verificatore` PRIMA
di dichiarare valido un risultato o chiudere un progetto; (3) il lavoro lungo
ma meccanico va all'`esecutore`, non alla sessione principale. Se Fable non e'
disponibile, usare `opus` con lo stesso impegno.

## Il laboratorio (`trading/scripts/`)

`build_lab.py` costruisce la pagina dal template: `<lab.json> <lab.html>` per la
pagina con i dati dentro (pubblicabile), `--vuoto <lab.html>` per la versione
che chiede i dati a `/api/dati`. **Non sostituire il payload a mano.**

Il front-end e' uno solo per la pagina pubblicata e per la futura applicazione
di gestione: la pagina prova il payload incorporato e, se assente, lo chiede al
server locale. Piano completo e tappe in `docs/piano-app.md`.

## Web app del grafico (`app/`)

Grafico simil TradingView (KLineChart 10) con disegni e backtest sopra il
grafico: `python app/server.py [--mt5]`, porta 8095. Indipendente dal
laboratorio; istruzioni e formato dei backtest in `app/README.md`.

## Bot in esercizio (`bots/`)

Il codice che opera davvero, separato dalla ricerca in `trading/`: Expert
Advisor MT5 in `bots/mt5/`, cBot cTrader in `bots/ctrader/`. Convenzioni e
scheda richiesta per ogni bot in `bots/README.md`. Mai committare eseguibili
compilati ne' credenziali o numeri di conto.

Un backtest fatto dentro MT5 o cTrader NON e' confrontabile con i numeri di
`docs/studies/`: convenzioni diverse su fill, spread e ordine fra stop e
obiettivo. Per confrontare, il bot va rigirato con il motore di questo
repository.

## Regole per NON sprecare token nelle analisi

1. **Mai stampare dati grezzi in chat**: gli script salvano il dettaglio in
   Parquet (scratchpad o `docs/studies/`) e stampano SOLO aggregati compatti
   (max ~20 righe, 3 decimali, `pd.set_option("display.width", 200)`).
2. **Salvare i risultati intermedi** su parquet e ricaricarli nelle analisi
   successive invece di rieseguire lo studio (gli studi completi girano in
   15-60s ma producono output lunghi).
3. Ogni studio nuovo va appuntato in `docs/studies/` in forma tabellare
   compatta: è la memoria tra sessioni, la chat non lo è.
4. I download (M1, tick) sono **riavviabili**: cache su disco, mai ripartire
   da zero. Vedi `trading/scripts/download_*.py`.
5. Preferire un solo comando python con output finale asciutto a molte
   invocazioni esplorative.
6. **Leggere i file in modo mirato**: grep/offset invece di aprire per intero
   file lunghi (es. `docs/studies/rr-intraday-study.md`, migliaia di righe).
   Log e CSV di MT5/cTrader: solo `tail`, conteggi o righe d'errore.
7. **Esplorazioni ampie ai sotto-agenti**: tornano solo con la conclusione e
   la chat principale resta leggera (ogni turno rilegge tutto il contesto).
8. **Una sessione per blocco di lavoro**: a fine blocco aggiornare
   `docs/sessions/` e consigliare all'utente di aprire una chat nuova invece
   di continuare la stessa.

## Convenzioni tecniche (fonte di bug note)

- Tutti i timestamp UTC; candele etichettate all'APERTURA del periodo.
- Feed Dukascopy: URL con **mese 0-based**; prezzi interi in millesimi;
  rate limiting sui burst (usare i downloader esistenti con backoff).
- Sessioni UTC: asia 0-7, london 7-12, ny 12-21, late 21-24.
- NO lookahead: livelli asia attivi dalle 07:00; swing confermati k barre
  dopo l'estremo; stato di trend causale via `structure.trend_state_series`.
- Backtest conservativo: nella stessa candela lo stop prevale sul take;
  fill dei market all'apertura della candela successiva.
- Timeframe canonici in `data.TIMEFRAMES` (inclusi M33/M66 non nativi MT5).

## Cosa NON fare

- Non committare CSV/tick nel repo (solo Parquet M1 annuali + codice + docs).
- Non fidarsi di risultati "troppo belli": cercare lookahead (è già successo
  con la confluenza asia, vedi `docs/studies/rr-intraday-study.md` §2, e con
  l'istante degli eventi sui livelli, appendice BB).
- **Il placebo che va bene quanto il vero e' un ALLARME, non una conferma**:
  se una zona spostata a caso rende come una vera, non e' la zona che
  funziona. E' cosi' che si e' scoperto il lookahead dell'appendice BB.
- Negli studi sui livelli, l'istante di un evento e' la **chiusura** della
  candela, mai l'apertura: registrare l'apertura significa entrare al prezzo
  di chiusura e ripercorrere la candela sapendo gia' come finisce, e il
  vantaggio finto cresce col timeframe. Bloccato da `test_eventi_livelli.py`.
- Non fare grid-mining di filtri: ipotesi pre-registrate e verifica per anno.
- Niente push durante il lavoro: solo commit locali dei file toccati; push
  solo a fine blocco e solo se l'utente lo chiede (piu' sessioni condividono
  questo checkout).

## Taratura, strade respinte, punti aperti → `docs/strade-respinte.md`

Archivio completo (taratura ufficiale, ~20 strade misurate e respinte, order
block, punti aperti). **Leggerlo PRIMA di proporre o progettare un nuovo
studio**; non serve per lavori meccanici. In sintesi:

- La taratura ufficiale (`trading/framework/taratura.py`, VWAP reclaim M6,
  1:10) vince sul 2020-2026 ma **perde sul 2009-2019**: e' sovradattamento.
  Ogni prova si chiude sui diciotto anni; non cercare varianti di questa
  famiglia. Cambiare un numero della taratura cambia tutti gli studi.
- Respinti (non ripercorrere): TF piu' piccoli e scalp M1, stop fissi
  piccoli, Fibonacci, livelli/order block/VWAP ancorati come ingresso o
  obiettivo, trailing a gradini, tenere oltre la sera, win rate >50%, soglie
  in ATR, chiusure parziali, limit sul livello, trend following multi-giorno.
