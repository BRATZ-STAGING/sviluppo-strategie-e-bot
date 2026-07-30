# Il forward, letto dai CSV — analisi al 24/07/2026

Prodotta da `trading/scripts/analizza_forward.py` sui CSV che l'Expert Advisor
scrive da solo. Nessuna esecuzione del bot, nessuna stima: sono i suoi dati.

## Il vantaggio non e' dimostrato, e adesso c'e' il numero

| | |
|---|---|
| periodo | 7 - 24 luglio 2026 |
| operazioni | 21 (12 a obiettivo, 9 in stop) |
| R totale | **+5,13** (media +0,244) |
| vincita media | +1,195 R |
| perdita media | -1,023 R |

Da vincita e perdita medie **misurate** (non dai parametri) il punto di
pareggio e' **46,1%** di operazioni vincenti. Osservato: 57,1%.

Sembra sopra, ma:

| | |
|---|---|
| intervallo di confidenza 95% | **36,5% - 75,5%** |
| probabilita' di fare almeno cosi' bene per puro caso | **21,3%** |

**L'intervallo contiene il pareggio.** Un bot senza alcun vantaggio produce un
risultato cosi' o migliore una volta su cinque. Non e' una prova di niente — ma
non e' nemmeno una smentita: e' semplicemente troppo presto, e ora si sa di
quanto.

L'intervallo di confidenza e' calcolato con la formula di Wilson: su 21 casi la
formula ingenua darebbe un intervallo sbagliato.

## La scoperta: il broker ha lo spread un TERZO di Dukascopy

Lo spread registrato all'esecuzione di ogni operazione:

| | valore |
|---|---|
| mediano | **0,230 $** |
| medio | 0,243 $ |
| massimo | 0,500 $ (15 luglio 08:42) |

Confronto con la misura sui tick Dukascopy dello stesso mese
(`docs/studies/rr-intraday-study.md`, appendice N):

| fonte | spread luglio 2026 |
|---|---|
| **broker FP (demo)** | **0,23 $** |
| Dukascopy | 0,70 $ |
| assunzione usata in tutti i backtest | 0,30 $ |

**Tre volte di differenza.** Se il valore del broker e' quello vero, la
conclusione dell'appendice N ("lo spread e' triplicato, il risultato regge con
-4%") e' **pessimista**, non ottimista: l'assunzione di 0,30 $ sarebbe piu'
larga della realta', non piu' stretta.

Le spiegazioni possibili sono tre e vanno distinte, non scelte a naso:

1. lo spread di un **conto demo** puo' essere piu' stretto del reale
2. la mediana Dukascopy e' su **24 ore**, e comprende le ore illiquide; il bot
   entra a ogni ora ma non uniformemente
3. Dukascopy e' un'altra fonte di liquidita' e su XAUUSD quota davvero piu' largo

**Come si risolve.** Non a ragionamenti: misurando lo spread Dukascopy **negli
istanti esatti** dei 21 riempimenti. Gli istanti sono in `istanti-forward.csv`
in questa cartella, insieme allo spread che il broker ha riportato. Basta:

    python misura_spread.py <cartella parquet> istanti-forward.csv esito.csv

e confrontare `spread_ingresso` con `spread_broker`. Se i due valori si
somigliano, la spiegazione e' la 2 e la mediana mensile e' fuorviante. Se
Dukascopy resta il triplo, e' la 1 o la 3, e allora **la demo sta mentendo** —
cosa da sapere prima di credere a qualunque numero del forward.

## Cosa il bot NON ha fatto (il file degli scarti)

| motivo | righe |
|---|---|
| REPLACED | 77 |
| EXPIRED | 8 |
| PLACE_FAILED | 5 |
| PENDING_AT_STOP | 1 |

Le 77 righe `REPLACED` **non sono occasioni perse**: sono lo stesso setup
spostato in avanti quando una candela chiude oltre l'impulso. E' contabilita',
non opportunita' mancate. Chi guarda il conteggio grezzo degli scarti (91) si
fa un'idea sbagliata di quante volte il bot ha rinunciato.

Le altre 14 righe invece contano:

**8 ordini scaduti** senza essere eseguiti entro 20 candele. La mediana
dell'attesa dal segnale al riempimento e' **50 minuti** (5 candele) e il massimo
osservato e' **198 minuti** (circa 20 candele): la soglia `ExpiryBars = 20` sta
esattamente al limite. Alzarla catturerebbe piu' operazioni, ma sono proprio
quelle in cui il prezzo non e' tornato sulla media — plausibilmente le peggiori.
Da testare, non da decidere a naso.

**5 ordini rifiutati**, e quattro sono un problema operativo, non di strategia:

    2026-07-07 04:00 → 04:30   retcode 10027   "auto trading disabled by client"

Per mezz'ora il bot ha provato quattro volte a vendere e il terminale aveva il
trading automatico **disattivato**. Quattro segnali persi per un interruttore.
Il quinto e' un `10015 invalid price` (13 luglio 01:00), da guardare a parte.

**1 ordine pendente** ancora aperto quando l'Expert Advisor si e' fermato.

## Costi ed esecuzione

| | |
|---|---|
| commissione | 0,0065 R per operazione (145,92 in valuta su 21 operazioni) |
| swap | 2 operazioni tenute oltre la notte: **-0,154 R** e +0,027 R |
| rischio effettivo | 0,97% - 1,01% (obiettivo 1,00%) — il calcolo della size funziona |
| ampiezza dello stop | mediana 11,92 $, minima **5,07 $**, massima 25,45 $ |

Due cose da notare:

- lo **swap** e' piccolo in media ma concentrato: una singola operazione tenuta
  una notte e' costata 0,154 R, cioe' piu' di venti volte la commissione. Su un
  bot con obiettivo 1,2 R non e' trascurabile.
- lo **stop minimo e' 5,07 $** perche' `MinStopPrice = 0`. Su quell'operazione
  lo spread del broker pesa 0,045 R; con lo spread Dukascopy peserebbe 0,138 R.
  E' esattamente il caso in cui la domanda sullo spread cambia il risultato.

## Per direzione

| direzione | n | vinte | R medio | R totale |
|---|---|---|---|---|
| SHORT | 12 | 7 | +0,279 | +3,34 |
| LONG | 9 | 5 | +0,199 | +1,79 |

Equilibrato. Con questi numeri non si distingue nulla fra le due direzioni, ed
e' giusto cosi': 21 operazioni divise in due fanno 12 e 9.
