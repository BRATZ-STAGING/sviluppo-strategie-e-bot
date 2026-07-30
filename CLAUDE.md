# Trading Framework XAUUSD — guida per le sessioni

## Stato del progetto (leggere PRIMA di riscoprire qualcosa)

- **Stato corrente e storia**: `docs/sessions/` (nota più recente = verità),
  `docs/master-spec.md` (architettura e fasi), `docs/studies/` (risultati:
  NON rifare studi già fatti, i numeri sono lì).
- Codice in `trading/framework/`, script in `trading/scripts/`, test:
  `cd trading && python3 -m pytest tests/ -q` (134 test al 2026-07-07).
- Dati M1 2020→2026 in `data/XAUUSD_M1/*.parquet` (BID, UTC, un file/anno).
- Dipendenze: `pip install pandas pyarrow pytest tabulate` (non in repo).

## Il laboratorio (`trading/scripts/`)

`build_lab.py` costruisce la pagina dal template: `<lab.json> <lab.html>` per la
pagina con i dati dentro (pubblicabile), `--vuoto <lab.html>` per la versione
che chiede i dati a `/api/dati`. **Non sostituire il payload a mano.**

Il front-end e' uno solo per la pagina pubblicata e per la futura applicazione
di gestione: la pagina prova il payload incorporato e, se assente, lo chiede al
server locale. Piano completo e tappe in `docs/piano-app.md`.

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
  con la confluenza asia, vedi `docs/studies/rr-intraday-study.md` §2).
- Non fare grid-mining di filtri: ipotesi pre-registrate e verifica per anno.
- Push frequenti: i container sono effimeri, il lavoro non pushato muore.

## La taratura ufficiale (`trading/framework/taratura.py`)

Un solo posto per i numeri della strategia: `UFFICIALE = Taratura()`. Gli
script la importano, i test la bloccano. Configurazione scelta e verificata
fuori campione (misure in `docs/studies/rr-intraday-study.md`):

- ingresso M6 su reclaim del VWAP giornaliero, H6 e H2 allineati
- conferme: **M33 e H12 allineati**, **M12 contrario** (ritracciamento)
- filtro di fondo: chiusura D1 contro media 50 giorni
- obiettivo **1:10**, stop a **pareggio a +3R**, rischio **1%**
- soglie in dollari nei mesi normali, riscalate sull'ATR in quelli ad alta
  volatilita' (fattore 1,5)

Risultato: +171,1R su 348 operazioni, **7 anni positivi su 7**, perdita
massima 16%, 49.321 EUR da 10.000. Cambiare un numero qui cambia tutti gli
studi: farlo solo dopo una verifica per anno e fuori campione.

## Strade gia' misurate e respinte (non ripercorrerle)

- **Stessa regola su timeframe piu' piccoli** (ingresso M3 o M1, obiettivi
  1:3-1:5): il vantaggio lordo si dimezza scendendo di TF e lo spread pesa il
  doppio in R. La migliore delle varianti piccole rende +0,20 R/op contro
  +0,49, guadagna solo dal 2022 in poi, e affiancata all'ufficiale DIMEZZA il
  conto a parita' di drawdown (correlazione mensile +0,776). Vedi appendice M.
- **Stop fissi piccoli (2/3/5 $) su ingressi M3-M6 con obiettivi 1:3-1:5**:
  respinti su 72 celle. Tutte le regolarita' puntano nella direzione opposta a
  quella proposta: lo stop largo vince sempre (a 2 $ negativo quasi ovunque,
  su M3 in tutte le celle), M6 batte M3 in ogni cella, senza filtri perde in
  tutte e 24. La cella migliore (+0,443 R/op) e' peggiore della taratura in
  vigore (+0,492 su tre volte le operazioni e 7 anni su 7). Appendice Q.
- **Ritracciamenti di Fibonacci come livelli** (e lo scalping su di essi):
  respinti col placebo su due timeframe. I livelli finti alla stessa profondita'
  reagiscono uguale (4 confronti a 4 su M12; su M6 la differenza e' un
  decimillesimo di ATR con il 49% di probabilita' di essere caso). Il rapporto
  reazione/penetrazione e' 1,06-1,10, mentre lo scalping con stop da 2 $
  richiede il 66% di operazioni vinte solo per coprire lo spread. Appendice O.
- **Obiettivo variabile col regime di volatilita'**: inutile, 1:10 e' il
  migliore in entrambi i regimi (appendice K).
- **Chiusura parziale a meta' posizione**: costa il 27% del rendimento
  (appendice L).

## Order block: primo risultato positivo (appendice P)

Definiti come l'utente li usa: zona dal minimo dell'ombra all'apertura per le
rialziste, simmetrica per le ribassiste; causali dalla chiusura della candela
che rompe. Su **M33** gli ingressi dentro una zona attiva e concorde rendono
**+0,640 R/op contro +0,087** (probabilita' 0,3% che sia caso, meglio in 6 anni
su 7, e migliora fuori campione). Robusto a ogni margine provato, e presente
**anche sulle operazioni che le conferme scartano**, quindi aggiunge
informazione invece di ripetere quella esistente.

**Non ancora adottato**: va misurato come filtro sul risultato complessivo, e va
escluso che sia un travestimento dell'impulso minimo. Codice in
`trading/scripts/run_order_block.py`.

## Aperti / da fare (non perdere)

- **Order block e altri livelli**: il bot target non usa solo il VWAP ma anche
  order block e altri livelli, ANCORA NON BEN DEFINITI. Vanno specificati con
  l'utente prima di implementarli (definizione operativa: quale candela, quale
  mitigazione, quale validita' temporale).
- **Parametri in unita' di volatilita'**: le soglie sono in dollari fissi
  (impulso 4$, rischio 1-10$, buffer 0.3$) ma il range M1 mediano e' passato da
  ~0.45$ (2020-24) a 1.05$ (2025) e 2.27$ (2026). Riparametrizzare in ATR.
- **Bug confermati dalla ri-validazione 2026-07**: resample_tf M33/M66 dipende
  dagli anni caricati; resample('1D') conta lo spezzone domenicale come giornata
  piena (17% di D1 monchi); da verificare la chiusura EOD del venerdi'.
- Timeframe: i TF grandi servono al contesto, i piccoli SOLO per l'entry precisa.
- **RR variabile in base alla qualita' del livello** (da specificare e testare):
  rischio 1-2% per operazione, RR da 1:3 fino a 1:10 a seconda di DOVE si
  entra. Esempio dell'utente: 1:10 su uno swing H6 confermato da H3, H2, M66,
  M33. Serve un punteggio di qualita' del setup (quante conferme, su quali TF)
  e una mappa punteggio -> obiettivo. Nota dai dati gia' raccolti: l'MFE
  raggiunge 5R nel 17% dei casi e 8R nel 9,5% (break-even a 1:10 = 9,1%),
  quindi un 1:10 indiscriminato perde: deve valere SOLO per il sottoinsieme
  di alta qualita', ed e' proprio questo che va dimostrato.
- **Lato short**: implementato (`run_long_short.py`). Da solo perde; con il
  filtro macro (chiusura D1 vs media 50gg) il sistema completo batte il solo
  long su rendimento e drawdown. Vedi Appendice 7.
