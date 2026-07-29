# Consegna dei tick XAUUSD a un'altra sessione

Documento autosufficiente: chi lo legge deve poter lavorare sui tick senza
riscoprire nulla di quello che qui e' gia' costato tempo.

## 1. Cos'e' il dato

Tick bid+ask di XAUUSD da **Dukascopy**, feed nativo UTC, dal 2020 a oggi.
Circa **25-30 milioni di tick l'anno**. Sul PC di origine stanno come cache di
file orari `.bi5` (LZMA), un file per ora: e' la forma piu' compatta e va
trasferita cosi', non come CSV.

Struttura della cache prodotta da `download_ticks.py`: **tutti i file in
un'unica cartella**, uno per ora.

    ticks_cache/YYYY-MM-DD_HH.bi5      ora con scambi
    ticks_cache/YYYY-MM-DD_HH.empty    ora senza scambi (file vuoto, marcatore)

Attenzione a non confondere questa struttura con quella degli URL Dukascopy,
che sono annidati e usano il **mese 0-base** (gennaio e' `00`). La cache in
locale e' piatta; il mese 0-base riguarda solo il download.

Ogni record e' di **20 byte**, formato `>3i2f`:

| campo | tipo | nota |
|---|---|---|
| millisecondi | int32 big-endian | dall'inizio dell'ora del file |
| **ask** | int32 big-endian | in **millesimi** di dollaro (dividere per 1000) |
| **bid** | int32 big-endian | idem |
| volume ask | float32 | |
| volume bid | float32 | |

**L'ask viene prima del bid.** Invertirli produce spread negativi ovunque:
e' il controllo numero uno da fare dopo ogni conversione.

I millisecondi vanno sommati all'inizio dell'ora **in int64**: con int32 si va
in overflow (bug gia' capitato e corretto).

## 2. Come trasferirlo

I container delle sessioni cloud sono effimeri e vengono ricreati: qualunque
cosa non stia nel repository o su Drive va persa. Tre strade, in ordine di
convenienza.

### a) Google Drive (consigliata per una sessione cloud)

1. Sul PC: `python trading/scripts/build_tick_parquet.py <cartella_out>`
   con `TICKS_CACHE` puntato alla cache. Produce un Parquet al mese piu'
   `INDICE.csv`. Il Parquet e' molto piu' piccolo del CSV e si carica con
   `pd.read_parquet`.
2. Caricare la cartella su Google Drive, **un file per mese** (non un unico
   archivio: il connettore scarica meglio file piccoli, e la sessione tira
   giu' solo i mesi che le servono).
3. Nell'altra chat: cercare i file con il connettore Drive e scaricarli nella
   cartella di lavoro. Serve che quella sessione abbia il connettore Google
   Drive collegato.

### b) Claude Code sul PC (la piu' semplice, se possibile)

Se l'altra sessione puo' girare in locale invece che nel cloud, la cache e'
gia' li' e non si trasferisce niente. E' anche l'unico modo per **riscaricare**
dati mancanti: vedi il punto 4.

### c) Un repository dedicato

I Parquet mensili stanno abbondantemente sotto il limite di 100 MB per file di
GitHub, ma l'insieme e' dell'ordine del gigabyte: va bene un repository
separato solo per i dati, non questo. Da valutare solo se il trasferimento
deve essere ripetuto spesso.

**Da non fare**: consegnare i CSV. Sono parecchie volte piu' grandi a parita'
di contenuto e non aggiungono niente che il Parquet non abbia.

## 3. Verifiche obbligatorie dopo il trasferimento

Nessuna e' facoltativa: sono tutte fallite almeno una volta.

1. **`ask >= bid` su tutti i tick.** Se fallisce, i due campi sono invertiti.
2. **Cross-check contro le candele M1** gia' nel repository
   (`data/XAUUSD_M1/*.parquet`, che sono **BID**): aggregando i bid dei tick a
   candele di un minuto si devono riottenere le stesse OHLC. Verifica su un
   campione di giornate sparse, non su una sola.
3. **Conteggio per mese** coerente con `INDICE.csv` (~2-2,5 milioni di tick al
   mese; un mese molto sotto significa ore mancanti).
4. **Ore mancanti**: sono normali nei weekend e nei festivi. Fuori da quelli,
   qualche decina di ore sparse nell'arco di anni sono buchi noti del
   rate-limiter e non compromettono un backtest; centinaia no.

## 4. Se servono altri dati (o mancano dei pezzi)

Lo scaricamento **funziona solo da una connessione domestica**, non dal cloud:
gli IP dei container sono filtrati e il datafeed lascia in timeout i client che
non hanno una **firma TLS da browser**. Lo script
`trading/scripts/download_ticks.py` usa `curl_cffi` (`pip install curl_cffi`)
per presentarsi come Chrome; e' riavviabile (non riscarica cio' che e' in
cache) e ha un circuit-breaker: dopo alcuni errori consecutivi si ferma per
10-60 minuti, perche' insistere durante una penalita' del feed la allunga.

Non rilanciarlo mai da una sessione cloud: e' tempo perso.

## 5. Il metodo, se l'obiettivo e' rifare lo stesso lavoro

I tick da soli non bastano: quello che ha prodotto risultati affidabili in
questo progetto e' la disciplina, non i dati. In sintesi.

**Niente lookahead.** Ogni struttura si valuta alla CHIUSURA della candela su
cui si decide. Gli swing sono confermati k barre dopo l'estremo, non
all'estremo. Le mediane si calcolano su finestra espansiva, mai su tutta la
storia. Le serie giornaliere vanno spostate di un giorno (`.shift(1)`). Un
risultato troppo bello e' quasi sempre lookahead: e' gia' successo qui, con un
falso +0,72R su 7 anni su 7.

**Backtest conservativo.** Nella stessa candela (o nello stesso minuto) lo stop
vince sull'obiettivo. Gli ordini a mercato si riempiono all'apertura della
candela successiva. Lo spread si paga di andata e ritorno.

**Ipotesi pre-registrate.** Si scrive cosa ci si aspetta prima di guardare i
numeri, e si verifica anno per anno. Il grid-mining di filtri produce
configurazioni che crollano fuori campione: qui la migliore in campione faceva
+0,63 R/op e fuori campione +0,03.

**Verifica fuori campione.** Selezionare su un periodo (qui 2020-2023) e
verificare su un periodo mai usato per scegliere (2024-2026). Se il risultato
peggiora molto, era rumore.

**Confronti a parita' di rischio.** Due sistemi si confrontano a parita' di
perdita massima, non a parita' di percentuale rischiata: altrimenti vince
sempre quello che rischia di piu' senza dirlo.

**Cosa i tick aggiungono davvero.** Tutti i backtest di questo progetto usano
uno **spread fisso di 0,30 $**. Con i tick si puo' usare lo spread reale,
variabile, del momento esatto dell'ingresso. E' la verifica piu' importante che
resta da fare: se lo spread reale e' piu' largo di 0,30 $ proprio nei momenti in
cui si entra, una parte del vantaggio misurato e' ottimistica. Nel progetto lo
spread mangia gia' circa meta' del risultato lordo, quindi il margine di errore
conta.

## 6. File da portare con se'

Dal repository, cartella `trading/`:

| file | a cosa serve |
|---|---|
| `scripts/download_ticks.py` | scaricare tick da Dukascopy (solo da PC) |
| `scripts/build_tick_parquet.py` | cache `.bi5` → Parquet mensili |
| `scripts/build_tick_csv.py` | cache `.bi5` → CSV mensili, se un destinatario li pretende |
| `framework/data.py` | caricamento, resampling, timeframe canonici |
| `framework/structure.py` | swing e stato di trend causali |
| `framework/vwap.py`, `volatility.py` | VWAP ancorato, ATR, regimi di volatilita' |
| `framework/gestione.py` | esiti: stop, obiettivo, pareggio, fine giornata |
| `framework/segnali.py`, `taratura.py` | generazione dei segnali guidata dalla configurazione |
| `docs/studies/rr-intraday-study.md` | tutte le misure fatte, comprese le strade respinte |
