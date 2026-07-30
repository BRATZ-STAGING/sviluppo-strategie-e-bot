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

## Misurato: il broker demo quota uno spread finto

Spread negli **stessi 21 istanti** di riempimento, dalle due fonti:

| fonte | mediano | medio | massimo |
|---|---|---|---|
| broker FP (demo) | **0,230 $** | 0,243 $ | 0,500 $ |
| Dukascopy (tick reali) | **0,630 $** | 0,971 $ | **7,150 $** |

Ma il numero che chiude la questione non e' il rapporto fra le mediane. E'
questo: **su 21 riempimenti il broker ha registrato solo tre valori distinti di
spread** — 0,23 · 0,24 · 0,50. Diciannove volte su ventuno esattamente 0,23.

Uno spread di mercato non si ferma sullo stesso valore diciannove volte.
Dukascopy negli stessi istanti va da 0,53 a 7,15. **La demo quota uno spread
sostanzialmente fisso**: e' sintetico, non e' il costo che si pagherebbe.

### I 21 esiti ricalcolati col costo vero

| | R totale | R/op | vinte | pareggio a | probabilita' per caso |
|---|---|---|---|---|---|
| come registrato dal broker | **+5,13** | +0,244 | 12/21 (57%) | 46,1% | 21% |
| **con lo spread Dukascopy** | **+3,77** | +0,179 | 12/21 (57%) | 48,9% | **30%** |

Il forward perde **1,36 R**, cioe' il **27%** del risultato. Nessuna operazione
cambia segno — il costo non e' abbastanza grande da ribaltarne una — ma il punto
di pareggio sale al 48,9% e la probabilita' che un bot senza vantaggio faccia
altrettanto passa da una volta su cinque a **una volta su tre**.

L'operazione piu' colpita ha pagato 7,15 $ di spread su 11,35 $ di rischio:
**0,61 R di costo aggiuntivo** su una sola operazione. Era vinta (+1,193) e
resta vinta (+0,583).

## Il risultato inatteso: le operazioni serali

Dividendo per fascia oraria si vede una cosa che nessuno cercava:

| fascia (UTC) | n | spread mediano | spread massimo | R col broker | R col costo vero |
|---|---|---|---|---|---|
| notte 0-6 | 1 | 0,870 $ | 0,870 $ | +1,20 | +1,15 |
| **giorno 7-18** | **15** | **0,590 $** | 0,700 $ | **+4,69** | **+4,14** |
| **sera 19-23** | **5** | 0,820 $ | **7,150 $** | **-0,75** | **-1,53** |

Le cinque operazioni serali sono **in perdita** e pagano un costo aggiuntivo
quattro volte piu' alto delle altre (0,155 R contro 0,037). I due picchi di
spread — 7,15 $ e 1,09 $ — cadono entrambi verso le 22 UTC, nell'ora del
cambio giornata, e in entrambi i casi nei 60 secondi precedenti **non c'era
nessun tick**: il mercato era fermo.

Escludendo le ore fuori dalla finestra 7-19:

| | n | R totale | R/op | probabilita' per caso |
|---|---|---|---|---|
| tutte le ore, costo vero | 21 | +3,77 | +0,179 | 30% |
| **solo 7-19, costo vero** | **15** | **+4,14** | **+0,276** | **24%** |

Sei operazioni escluse valgono **-0,37 R**: togliendole il risultato migliora.

**Perche' conta piu' di quanto sembri.** La finestra 7-19 UTC non e' stata
scelta guardando questi dati: e' la finestra della strategia in `trading/`,
fissata molto prima e validata fuori campione su sette anni. Trovare che
funziona anche su un bot diverso, con una logica diversa, misurata con una
fonte di dati diversa, e' una conferma indipendente — non un ritocco sui
numeri. Su cinque operazioni serali non e' una prova, ma e' l'unica modifica al
bot che poggia su qualcosa di gia' verificato altrove.

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
