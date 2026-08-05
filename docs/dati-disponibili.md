# Quali dati esistono, e cosa coprono

Risposta alla prima domanda di qualunque campagna di backtest: **su cosa sto
girando?** Aggiornato al 30/07/2026.

## 1. Candele M1 — nel repository

`data/XAUUSD_M1/XAUUSD_M1_<anno>.parquet`, un file per anno.

| | |
|---|---|
| periodo | **2009-01-01 → 2026-07-06** |
| righe | **6,24 milioni** |
| prezzi | **BID** |
| fuso | UTC, candele etichettate all'APERTURA |
| peso | 109 MB |

Fonte Dukascopy. E' la base di tutti gli studi in `docs/studies/`.

Gli anni **2009-2019** sono stati aggiunti il 03/08/2026 con
`trading/scripts/estendi_storico.py`, dallo stesso endpoint giornaliero
`BID_candles_min_1.bi5`. Verifica del convertitore prima di usarli: sul
2020-06-10, giorno gia' in archivio, riproduce le 1.379 candele con
differenza massima **0,0** su tutte e cinque le colonne; copertura 309-314
giornate l'anno e 1.130-1.170 minuti al giorno, come nel 2020-2026. Riscontro
esterno: massimo **1920,66 il 06/09/2011** e minimo **1046,23 nel 2015**,
entrambi al centesimo.

**Attenzione agli studi vecchi**: da adesso `load_m1` senza argomenti carica
anche il 2009-2019, quindi i numeri pubblicati prima dell'estensione non si
riproducono per caso. Con `XAU_ANNI=2020-2026` si riottengono esatti (348
operazioni, +171,1 R). Ogni caricamento stampa su stderr il periodo usato.
Cosa dicono gli undici anni nuovi: `docs/studies/rr-intraday-study.md`,
appendici AU e AV.

## 2. Tick bid+ask — sul PC, NON nel repository

Convertiti in Parquet mensili con `trading/scripts/build_tick_parquet.py`, in
`C:\dukascopy\parquet_out` sul PC di origine (piu' la cache `.bi5` originale in
`C:\dukascopy\ticks_cache`).

| | |
|---|---|
| periodo | **2022-11-01 → 2026-07-06** (45 mesi) |
| tick | **222.378.654** |
| peso | 1.244 MB |
| ore mancanti | **zero** (le 528 di luglio 2026 sono il mese non ancora concluso) |
| verifica ask ≥ bid | superata su tutti i tick |

`INDICE.csv` nella stessa cartella riporta per ogni mese: numero di tick, spread
mediano, ore mancanti, peso.

**In corso**: backfill 2020-01 → 2022-10 (34 mesi). Riavviabile, non riscarica
cio' che ha in cache.

### Lo spread mediano, misurato

| periodo | spread |
|---|---|
| 2023 | 0,32 - 0,34 $ |
| 2024 | 0,33 → 0,44 $ |
| 2025 | 0,51 → 0,70 $ |
| 2026 | 0,58 → **0,89 $** (massimo: febbraio 2026) |

**Lo spread e' triplicato in tre anni.** Qualunque backtest con spread fisso
sopravvaluta i periodi recenti. Dettagli e impatto misurato in
`docs/studies/rr-intraday-study.md`, appendice N.

## 3. Cache tick del broker FP dentro MT5

44 mesi circa, secondo gli appunti del progetto. **Non verificata** in questo
repository: copertura, buchi e trattamento dello spread sono da accertare prima
di usarla per qualcosa. Se una campagna di backtest si appoggia a questa cache,
il primo passo e' confrontarla con i tick Dukascopy sulla finestra comune.

### Verifica incrociata FP contro Dukascopy sulle candele M1 (01/08/2026)

Fatta con `trading/scripts/confronta_fonti.py mt5 2026` sul PC, 73.896 minuti
comuni (22/04 - 31/07/2026, il piu' indietro concesso dal terminale):

| | |
|---|---|
| scostamento orario server FP | UTC+3, rilevato automaticamente |
| differenza mediana delle chiusure | 0,205 $ |
| di cui SISTEMATICA | **+0,195 $** (FP quota sopra il bid Dukascopy) |
| p95 | 0,415 $ |
| minuti oltre 0,5 $ | 2,6% |
| massimo | 21,4 $ (un minuto isolato, maggio) |

Lettura: quasi tutta la differenza e' uno scostamento di LIVELLO costante
(~20 centesimi, cioe' FP sta dentro lo spread Dukascopy), non rumore. Tolto
quello, il residuo tipico e' sotto i 10 centesimi: **le due fonti raccontano
lo stesso mercato**. Uno scostamento costante non tocca la strategia (ingresso,
stop e obiettivo si spostano insieme); la coda di minuti oltre 0,5 $ sono i
picchi di news, ed e' un motivo in piu' per cui gli stop da 2-3 punti erano
fragili. Per confrontare anche 2024-2025 serve alzare "Max barre nel grafico"
a Unlimited e RIAVVIARE MT5 (il tetto da 100.000 barre tronca anche l'API).

## Perche' importa quale si usa

Le tre fonti non sono interscambiabili.

- Le **candele M1** non dicono cosa succede dentro il minuto: su un bot con stop
  piu' piccoli di una candela i fill sono ottimistici. Misura fatta sul bot
  Keltner: 47% di operazioni vincenti su M1 contro 31% su tick.
- I **tick Dukascopy** hanno bid e ask veri, quindi lo spread reale variabile —
  ma coprono solo da novembre 2022 (per ora).
- La **cache FP** e' del broker su cui si opera davvero, quindi in teoria e' la
  piu' fedele, ma non e' stata verificata.

Un confronto fra due backtest su fonti diverse non vale niente. Prima si fissa
la fonte, poi si confrontano le varianti.

## Verifica dello storico 2009-2019 contro una fonte indipendente (04/08/2026)

Domanda giusta e che mancava: gli anni aggiunti sono corretti? I controlli
fatti al momento del download — il convertitore che riproduce un giorno gia'
in archivio, la copertura per anno, due punti noti — erano **interni** o
aneddotici. Nessuno confrontava con un'altra banca dati.

Il proxy di questo ambiente blocca quasi tutti gli host (stooq, FRED, Yahoo,
lbma.org.uk: 403 sulla CONNECT). Passa `raw.githubusercontent.com`, e li' c'e'
il **prezzo LBMA** — il fixing ufficiale di Londra, che non ha niente a che
vedere con Dukascopy.

### Confronto con il fixing LBMA, 210 mesi

| | |
|---|---|
| periodo | 2009-01 → 2026-06 |
| differenza mediana | **+0,34 $ (+0,023%)** |
| differenza media | +0,25 $, scarto tipo 3,23 $ |
| correlazione | **0,999991** |
| mesi oltre l'1% | **0 su 210** |
| scostamento massimo | 0,73% (maggio 2025) |

E soprattutto, diviso per periodo:

| | mesi | mediana | scarto medio | massimo |
|---|---|---|---|---|
| **2009-2019** | 132 | +0,026% | **0,091%** | 0,652% |
| 2020-2026 | 78 | +0,018% | 0,104% | 0,726% |

**Gli anni vecchi aderiscono a LBMA leggermente MEGLIO di quelli nuovi.**
(La differenza residua e' attesa: LBMA e' la media dei fixing giornalieri,
l'archivio la media di tutti i minuti.)

### Gli eventi noti, con l'ora

La media mensile valida il livello, non la struttura intraday. Sei giornate
che chiunque puo' verificare:

| giorno | apertura | massimo | ora | minimo | ora | escursione |
|---|---|---|---|---|---|---|
| 2011-09-06 record dell'epoca | 1897,6 | **1920,7** | 06:29 | 1863,0 | 17:51 | 57,7 |
| 2013-04-15 crollo di aprile | 1489,9 | 1495,5 | 00:28 | **1334,6** | 20:16 | **160,9** |
| 2016-06-24 Brexit | 1267,3 | **1358,2** | **03:52** | 1264,0 | 00:18 | 94,2 |
| 2016-11-09 elezioni USA | 1273,4 | **1337,3** | **05:10** | 1268,8 | 00:59 | 68,5 |
| 2020-03-16 liquidazione Covid | 1557,9 | 1560,7 | 00:06 | **1451,1** | 13:03 | 109,6 |
| 2020-08-06 massimo 2020 | 2036,3 | **2074,8** | 22:21 | 2034,4 | 00:01 | 40,4 |

Tutti presenti, con la grandezza giusta e **all'ora giusta**: il picco Brexit
alle 03:52 UTC quando arrivavano gli spogli, quello delle elezioni alle 05:10
seguito dal crollo, il minimo Covid nel pomeriggio americano.

### La struttura oraria

Escursione mediana al minuto, per ora UTC, nei due periodi:

| ora | 2009-2019 | 2020-2026 | rapporto |
|---|---|---|---|
| 04 (fondo asiatico) | 0,170 | 0,310 | 1,82 |
| 07-08 (apertura Londra) | 0,306 | 0,620 | 2,03 |
| **13-14 (sovrapposizione Londra-NY)** | **0,510** | **1,120** | 2,20 |
| 17 | 0,325 | 0,554 | 1,70 |
| 21 (rollover) | **0,159** | **0,257** | 1,62 |

Stessa forma esatta — massimo alle 13-14, secondo picco all'apertura di
Londra, minimo alle 21 — con il periodo recente semplicemente due volte piu'
mosso a ogni ora. Un archivio sbagliato o disallineato non riprodurrebbe la
struttura delle sessioni ora per ora.

### Conclusione

I dati 2009-2019 reggono il confronto con una fonte indipendente e
autorevole, e non sono meno affidabili di quelli 2020-2026 gia' in uso. **Il
risultato negativo su quegli anni non e' un problema di dati.**

Resta un limite: LBMA e' mensile, quindi valida il livello e (insieme agli
eventi e alla struttura oraria) la coerenza intraday, ma non e' un confronto
minuto per minuto. Per quello servirebbe una seconda fonte tick, che da questo
ambiente non e' raggiungibile.

### Secondo riscontro: confronto GIORNALIERO e ORARIO (04/08/2026)

Il confronto con LBMA valida il livello ma e' mensile. Una caccia con agenti
paralleli ha trovato otto fonti indipendenti raggiungibili su
`raw.githubusercontent.com`; la piu' utile e' `ejtraderLabs/historical-data`,
un feed di broker con XAUUSD giornaliero e orario dal 2012 al 2022 — cioe' in
pieno nel periodo sotto esame.

**Giornaliero, 2.399 giornate (2012-2022):**

| | scarto mediano | p95 | oltre 5 $ |
|---|---|---|---|
| chiusura | 0,32 $ | 1,35 $ | 2 giorni (0,1%) |
| **massimo** | **0,06 $** | 0,31 $ | 4 giorni (0,2%) |
| **minimo** | **0,07 $** | 0,76 $ | 8 giorni (0,3%) |

Correlazione ≥ 0,9999 in ogni singolo anno. Il dato piu' forte sono massimo e
minimo: sono gli **estremi intraday**, e coincidono a sei centesimi. La
chiusura scarta un po' di piu' solo perche' dipende dal minuto esatto in cui
cade il confine di giornata.

**Orario, 52.214 ore (2013-2021):** scarto mediano 0,105 $, correlazione
0,9999720. Il 10% di ore oltre i 2 $ ha una spiegazione precisa, ed e' un
riscontro in piu' invece che un problema: lo scostamento migliore e'

| mese | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| server | +2 | +2 | +2 | **+3** | +3 | +3 | +3 | +3 | +3 | +3 | +2 | +2 |

cioe' **esattamente il calendario dell'ora legale**. Usando per ogni mese il
suo scostamento, lo scarto mediano scende a **0,048 $ all'ora**, con **zero
mesi sopra 0,5 $ su 108**.

Che una fonte indipendente riproduca il passaggio dell'ora legale mese per
mese non e' una coincidenza: e' la prova che le due serie descrivono lo stesso
mercato e che i timestamp dell'archivio sono davvero UTC.

**Verdetto**: lo storico 2009-2019 e' validato su tre livelli — mensile contro
il fixing ufficiale LBMA, giornaliero e orario contro un feed di broker
indipendente. Il risultato negativo della strategia su quegli anni non e' un
problema di dati.
