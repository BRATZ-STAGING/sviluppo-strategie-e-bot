# Le tre strategie da portare sul bot

Specifica congelata per l'implementazione. Tutto quello che serve a scrivere
un Expert Advisor senza tornare a chiedere. I numeri vengono da
`trading/framework/taratura.py` e dalle misure in
`docs/studies/rr-intraday-study.md`.

> **Da leggere prima.** Le tre strategie sono state scelte e misurate sul
> **2020-2026**, dove rendono tutte e tre in ogni anno. Sullo storico esteso
> al 2009 **perdono tutte e tre** (in uso -39,6 R, A -45,1, B -88,4 su undici
> anni). Le tre verifiche fatte per spiegarlo — filtro di regime, rinuncia
> allo short, taratura invertita — sono negative, e solo l'1% delle
> configurazioni scelte sul periodo recente resta positivo su quello vecchio
> (appendici AU-AY). Metterle in esercizio e' una **scommessa sul fatto che il
> regime del 2020-2026 continui**, non l'applicazione di un vantaggio
> dimostrato. Il dimensionamento va fatto sulla perdita massima VERA
> (51,7 R per la strategia in uso, 87,4 per la B), non su quella del periodo
> buono.

## Cosa hanno in comune tutte e tre

### Il segnale d'ingresso

Valutato **alla chiusura di ogni candela M6**, mai su quella in corso.
Si entra **a mercato** al prezzo di chiusura di quella candela.

| # | condizione | dettaglio |
|---|---|---|
| 1 | orario | l'**apertura** della candela M6 sta fra le **07:00 e le 19:00 UTC** |
| 2 | struttura | **H6 e H2** entrambi nella direzione dell'operazione |
| 3a | conferme | **M33 e H12** entrambi nella direzione |
| 3b | ritracciamento | **M12 NON allineato** alla direzione (contrario o neutro) |
| 4a | impulso | nella giornata il prezzo si e' allontanato dal VWAP di almeno **4,00 $** (massimo del giorno prima di questa candela, per un long) |
| 4b | reclaim | la candela **tocca il VWAP e chiude oltre**, e chiude anche oltre l'estremo della candela precedente |
| 5 | filtro di fondo | la chiusura D1 di **ieri** sta sopra la sua media a **50 giornate** per i long, sotto per gli short |
| 6 | rischio | la distanza dallo stop cade fra **1,00 e 10,00 $** |
| 7 | frequenza | massimo **3 operazioni al giorno**, almeno **30 minuti** fra una e l'altra |

Long e short sono simmetrici. Se una condizione manca, non si entra.

### VWAP, struttura, stop

- **VWAP**: ancorato alla giornata (riparte a **00:00 UTC**), calcolato sulle
  **candele M6**, prezzo tipico (H+L+C)/3 pesato per il volume. Non sui minuti:
  e' una linea diversa.
- **Struttura** di un timeframe: stato di trend causale. Uno swing è confermato
  **3 candele** dopo l'estremo (`frattale_k = 3`); lo stato passa rialzista
  quando una chiusura supera l'ultimo massimo confermato, ribassista al
  contrario. Lo stato vale **dalla chiusura** della candela che rompe.
- **Stop**: sotto il minimo delle ultime **5 candele M6** della giornata
  (sopra il massimo per uno short), piu' **0,30 $** di margine.
- **Obiettivo e gestione**: cambiano fra le tre, vedi sotto.

### Soglie riscalate nei mesi agitati

Le quattro soglie in dollari (**impulso 4,00 · margine stop 0,30 · rischio
minimo 1,00 · rischio massimo 10,00**) valgono nei mesi normali. In un mese
riconosciuto **ad alta volatilita'** vengono moltiplicate per
`ATR_del_giorno / mediana_di_riferimento`.

- ATR: media a **14 giornate** del true range, calcolata sulle **giornate
  vere** (si scartano le sessioni sotto le 300 candele: la domenica sera non
  e' una giornata), e **spostata di un giorno** in avanti.
- Mese ad alta volatilita': la mediana dell'ATR degli ultimi **21 giorni** di
  borsa prima dell'inizio del mese supera **1,5 volte** la mediana di tutta la
  storia precedente. Sotto 250 giornate di storia si risponde "normale".
- Mediana di riferimento: mediana dell'ATR giornaliero sugli anni
  **2020-2024**. E' una costante: **va messa nei parametri dell'EA**, perche'
  il terminale non ha abbastanza storia per calcolarla. Vale
  **25,5968 $** (misurata sull'archivio, ATR a 14 giornate vere).

### Dimensionamento

    lotti = (capitale x rischio%) / (distanza_stop_in_$ x 100)

arrotondato **per difetto** al passo del broker. Rischio **1%** per operazione.
Se il calcolo scende sotto il lotto minimo, **si salta l'operazione**: non la
si forza a 0,01, si rischierebbe il triplo del previsto.

### Costi da mettere in conto

- **Spread**: 0,30 $ per andata e ritorno era la misura del 2020-2023; nel
  2026 e' arrivato a **0,89 $**. Va letto dal terminale, non fissato.
- **Swap FP** (misurato 03/08/2026): long **-71,5 punti** per lotto e per
  notte, short **+32,5**, mercoledi' **x3**. Un punto = 1 $ per lotto. Con lo
  stop mediano di 4,72 $ una notte di long costa **0,151 R**.
- **Rollover alle 00:00 del server = 21:00 UTC**: chi chiude entro quell'ora
  non paga mai swap.

## Le tre gestioni

### 1. IN USO — chiude ogni sera

| | |
|---|---|
| obiettivo | **1:10** |
| pareggio | a **+3R** lo stop va al prezzo d'ingresso, e non si tocca piu' |
| chiusura forzata | **21:00 UTC** ogni giorno, in utile o in perdita |
| fine settimana | non si pone: non si arriva mai al venerdi' con posizioni aperte |
| swap pagato | **zero** |

E' la piu' semplice da implementare e l'unica che non ha esposizione notturna.

### 2. A — lascia correre in settimana, chiude il venerdi'

| | |
|---|---|
| obiettivo | **1:8** |
| pareggio | a **+3R** stop al prezzo d'ingresso |
| chiusura forzata | **venerdi' alle 21:00 UTC** (nessuna chiusura serale infrasettimanale) |
| fine settimana | mai attraversato |
| swap pagato | tutte le notti da lunedi' a giovedi' |

### 3. B — resta aperta, attraversa il weekend solo se avanti

| | |
|---|---|
| obiettivo | **1:8** |
| gestione | **trailing**: da quando l'operazione tocca **+3R**, lo stop segue a **MFE - 2R** (MFE = massimo favorevole raggiunto) |
| chiusura forzata | nessuna, salvo la regola del fine settimana |
| fine settimana | il venerdi' alle 21:00 UTC: se l'operazione e' **sopra +1R** resta aperta, altrimenti si chiude. **Lo stop non si tocca** |
| scadenza | dopo **30 giorni** si chiude comunque |
| swap pagato | tutte le notti, weekend compresi quando resta aperta |

Perche' +1R e non +3R: sono state misurate entrambe, +1R rende 9 R in piu' e
azzera comunque le uscite per gap. Perche' lo stop non si tocca: sopra +3R il
trailing lo ha gia' portato ad almeno +1R da solo, e portarlo alla chiusura
del venerdi' azzera il margine che serve ad assorbire il salto del lunedi'
(appendice AT).

## I numeri

Sul **2020-2026**, rischio fisso, spread 0,30 $, swap reale dove si applica:

| | in uso | A | B |
|---|---|---|---|
| operazioni | 333 | 333 | 333 |
| risultato | **+171,97 R** | **+178,47 R** | **+173,89 R** |
| per operazione | +0,52 | +0,54 | +0,52 |
| operazioni vinte | 35,7% | 25,8% | **38,4%** |
| perdita massima | 15,60 R | **12,32 R** | **12,32 R** |
| risultato / perdita max | 11,0 | **14,5** | 14,1 |
| anni positivi | **7/7** | **7/7** | **7/7** |
| anno peggiore | +9,02 R | **+13,28 R** | +10,92 R |
| profit factor | **1,86** | 1,78 | 1,79 |
| perdite di fila | 11 | 12 | 12 |

Sullo storico completo **2009-2026**, con i suoi undici anni mai visti:

| | in uso | A | B |
|---|---|---|---|
| 2009-2019 | **-39,61 R** (2/11 anni) | **-45,09 R** (4/11) | **-88,42 R** (1/11) |
| perdita massima 2009-2019 | **51,69 R** | 62,24 R | **87,37 R** |
| 2009-2026 | +115,12 R | +121,56 R | +85,19 R |

**La perdita massima da usare per il dimensionamento e' quella della riga
2009-2019**, non quella del periodo buono: al rischio dell'1% per operazione
sono 52 punti di conto per la strategia in uso e 87 per la B.

## Le trappole dell'implementazione

1. **M6, M12, M33, M66 non esistono in MT5.** Vanno costruiti dai minuti
   dentro l'EA, ancorati all'**epoch** (non alla mezzanotte): M33 e M66 non
   dividono il giorno, e senza ancoraggio le candele cambiano a seconda di
   quando parte la serie.
2. **Il terminale non da' UTC**, da' l'ora del server (UTC+3 per FP) dentro un
   campo che sembra un epoch. Va convertita, altrimenti il VWAP si ancora alle
   21:00 e la finestra 07-19 diventa 04-16. Lo scarto si ricava dal tick
   confrontandolo con l'orologio di sistema. **Questo errore e' gia' costato
   una misura sbagliata sul grafico dal vivo**: il 62% dei segnali disegnati
   non erano quelli veri.
3. **Riscaldamento**: l'EA non deve operare finche' non ha 50 giornate D1 per
   il filtro di fondo, 14 per l'ATR, e abbastanza candele H12 per la
   struttura. In pratica servono **almeno tre mesi** di storia caricata.
4. **La mediana ATR di riferimento (2020-2024) va passata come parametro**: il
   terminale non ha abbastanza storia per calcolarla, e senza di essa nei mesi
   agitati le soglie diventano indefinite e l'EA non aprirebbe piu' niente
   **in silenzio**.
5. **Un terminale = un conto.** Per far girare le tre strategie su conti
   separati servono tre installazioni MT5 (o tre cartelle dati in modalita'
   portable), ciascuna col suo EA. Sulla stessa macchina si puo' fare; ognuna
   consuma la sua CPU e la sua connessione.
6. **Magic number diverso per ciascuna**, e ciascuna gestisce solo le proprie
   posizioni: se due EA finissero sullo stesso conto senza distinguerle si
   chiuderebbero le operazioni a vicenda.
7. **Ordine fra stop e obiettivo**: se entrambi cadono nella stessa candela, la
   ricerca conta lo **stop**. Un backtest MT5 che conta il take darebbe numeri
   piu' belli e non confrontabili.

## Prima di andare in reale

- Girare in **demo** almeno un mese e confrontare le operazioni aperte con
  quelle che il motore di ricerca produce sugli stessi minuti: devono
  coincidere una per una. `trading/scripts/grafico_live.py` mostra il pannello
  delle sette condizioni proprio per questo confronto.
- Ricordare che le tre sono **fortemente correlate** (stesso segnale
  d'ingresso, cambia solo l'uscita): farle girare insieme non e'
  diversificazione, e' la stessa scommessa in triplice copia.
