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

---

# AGGIORNAMENTO 04/08/2026 — prima di avviare, leggere questo

Una giornata di verifiche ha cambiato tre cose di questo documento. Le regole
d'ingresso e di gestione descritte sopra **non cambiano**: cambiano i numeri
attesi, l'avvertenza, e quale delle strategie conviene davvero.

## 1. Il costo era sottostimato

Le tabelle sopra usano lo spread della taratura, **0,30 $**. Misurato su
**6,1 milioni di tick** denaro-lettera (appendice BN):

| anno | 2021 | 2022 | 2023 | 2024 | **2025** | **2026** |
|---|---|---|---|---|---|---|
| spread vero $ | 0,349 | 0,395 | 0,334 | 0,384 | **0,632** | **0,631** |

Lo spread e' **raddoppiato dal 2025**. La forma oraria esiste ma e' piccola:
minimo 0,330 alle 15 UTC, massimo 0,456 alle 22, il 38% di escursione.

## 2. I numeri veri delle quattro strategie (2020-2026, 333 operazioni)

| strategia | R totale | R/op | vinte% | DD R | **R/DD** | anni+ | anno peggiore | mesi+ | perdite di fila |
|---|---|---|---|---|---|---|---|---|---|
| in uso 1:10, pareggio +3R, EOD | +214,7 | 0,64 | 21,3% | 20,8 | 10,33 | 6/7 | **−3,6 R** | 44,9% | **23** |
| A · 1:8, pareggio +3R, chiude venerdi' | +206,2 | 0,62 | 16,8% | 26,3 | 7,84 | **7/7** | +7,5 R | 43,5% | **24** |
| **B · 1:8, trail MFE−2 da +3R, weekend se >+1R** | **+174,6** | 0,52 | 38,4% | **12,6** | **13,85** | **7/7** | **+11,9 R** | **55,1%** | **12** |
| **1:2 secco, niente pareggio, EOD** (nuova) | +86,6 | 0,26 | **46,9%** | 12,3 | 7,02 | 6/7 | −2,6 R | 52,2% | **7** |

La correzione del costo vale **il 4%** del totale (in uso: da +223,4 a +214,7).
E' poco, e il motivo e' importante: lo **stop strutturale cresce da solo** con
la volatilita' — mediana 4,2 $ nel 2020, 14,8 $ nel 2026 — quindi il costo
relativo resta al 9,8% invece di salire. Una strategia a stop fisso non ha
questa protezione: con 3 $ fissi il costo e' passato dal 10% al 21%.

## 3. Quale avviare: **la B**, non quella in uso

Su ogni misura che conta per un conto da far vedere a qualcuno, la B vince:

| | in uso | **B** |
|---|---|---|
| anni positivi | 6/7 | **7/7** |
| anno peggiore | −3,6 R | **+11,9 R** (nessun anno in perdita) |
| perdita massima | 20,8 R | **12,6 R** |
| rendimento per unita' di perdita | 10,33 | **13,85** |
| mesi positivi | 44,9% | **55,1%** |
| perdite consecutive | 23 | **12** |

Rende il 19% in meno in R assoluti e li restituisce tutti in sopportabilita'.

**Dimensionamento per un 6% annuo**: rischio **0,24% per operazione**, che
porta la perdita massima attesa al **3,0% del conto**. Per un 10% annuo:
rischio 0,40%, perdita massima 5,0%.

La **1:2 secca** e' l'alternativa se serve il tasso di vincite piu' alto
(46,9% contro 38,4%) e la striscia di perdite piu' corta (7 contro 12): costa
un anno negativo su sette e un drawdown doppio a parita' di rendimento.

## 4. L'avvertenza va rafforzata, non ammorbidita

La scheda diceva che avviarle e' "una scommessa sul fatto che il regime del
2020-2026 continui". Le misure di oggi rendono quella frase piu' scoperta:

- **il regime non e' mai cambiato** (appendice BW). In rapporto al prezzo,
  ATR giornaliero 1,351% nel 2009-2019 contro 1,393% nel 2020-2026; spread
  relativo identico; quota di escursione notturna e persistenza sovrapposte
  per oltre il 90%. L'unica cosa cambiata e' il **prezzo dell'oro**, da 950 a
  4.676 $;
- **non era un problema di unita' di misura** (appendice BX). Riscrivere tutte
  le soglie in ATR stabilizza le occasioni fra le epoche (da 17-80 l'anno a
  41-64) ma **non restituisce il vantaggio**: il 2009-2019 resta a +0,046 R/op
  lordo contro +0,72 del 2023-2026;
- **non e' la tendenza di fondo**: condizionando sulla pendenza a 200 giorni,
  la fascia "sale forte" rende −0,001 netto nel 2009-2019 e +0,580 nel
  2020-2026.

Cioe': **il vantaggio compare nel 2020 e nessuna grandezza misurabile del
mercato cambia insieme a lui.** La spiegazione piu' parsimoniosa resta che la
regola sia stata trovata cercando dentro il 2020-2026.

Questo non impedisce di avviarla. Impone due cose:
1. dimensionare sulla perdita massima del **periodo cattivo** (51,7 R per la
   strategia in uso, 87,4 per la B), non su quella del periodo buono;
2. avere una **regola di spegnimento** decisa prima di partire — per esempio
   fermarsi a −15 R, che e' oltre il drawdown peggiore del periodo buono e
   dentro quello del periodo cattivo.

## 5. Il registro in avanti e' attivo

`grafico_live.py` scrive ora ogni segnale su `registro_segnali.jsonl`: istante
in cui e' stato **visto**, bid e ask reali, entry, stop, rischio, stato di
struttura di tutti i timeframe, quali condizioni erano vere. Registra anche i
"vicino" (una condizione mancante), che servono a misurare quanto vale
ciascuna condizione — cosa che lo storico non puo' dire, perche' li' le
condizioni sono gia' imposte.

Facendolo girare sul VPS accanto ai bot, fra sei mesi ci sara' **l'unico fuori
campione non contaminato** che questo progetto possa ancora produrre. Vale piu'
di qualunque altro studio sugli stessi dati.

---

## 6. Tutte e quattro insieme: misurato, e non conviene

Richiesta dell'utente: avviarle tutte e quattro. La domanda che nessuna scheda
si era posta e' se quattro **diversifichino**. Misurato su tutte le 333
operazioni (`trading/scripts/portafoglio_quattro.py`):

### Non sono quattro strategie, e' una strategia con quattro uscite

| correlazione | in uso | A | B | 1:2 |
|---|---|---|---|---|
| **in uso** | 1,000 | 0,876 | 0,683 | 0,547 |
| **A** | 0,876 | 1,000 | 0,782 | 0,570 |
| **B** | 0,683 | 0,782 | 1,000 | 0,707 |
| **1:2** | 0,547 | 0,570 | 0,707 | 1,000 |

Nel **52,6%** delle operazioni perdono **tutte e quattro**. Nel 15% guadagnano
tutte e quattro. Condividono lo stesso ingresso: aprono nello stesso minuto,
sullo stesso strumento, nella stessa direzione.

### A parita' di rendimento, quattro insieme e' PEGGIO della sola B

| obiettivo | solo B | tutte e quattro |
|---|---|---|
| 6% annuo | rischio 0,24%/op, **DD 3,03%** | 0,062%/op ciascuna, DD 3,20% |
| 12% annuo | rischio 0,48%/op, **DD 6,06%** | 0,123%/op ciascuna, DD 6,41% |
| 24% annuo | rischio 0,96%/op, **DD 12,13%** | 0,246%/op ciascuna, DD 12,81% |

La diversificazione vale **zero**, anzi meno di zero: a ogni livello di
rendimento la sola B ha il drawdown piu' piccolo. E lo fa con **una posizione
alla volta invece di quattro**, cioe' con un quarto della complessita'
operativa e un quarto delle cose che possono rompersi.

**Per avere piu' rendimento la strada e' aumentare la taglia della B, non
aggiungere le altre tre.**

### L'errore da non fare in nessun caso

Avviarle con la taglia scritta nelle rispettive schede (in uso 0,20% · A 0,20%
· B 0,24% · 1:2 0,48%) significa rischiare **1,12% del conto a ogni segnale**,
non il 6% annuo che ciascuna promette: il risultato e' **24% annuo con 13,7%
di perdita massima**. Puo' anche andare bene, ma va scelto, non subito.

Per restare al 6% annuo con tutte e quattro attive, ogni taglia va **divisa
per quattro**: in uso 0,049% · A 0,051% · B 0,060% · 1:2 0,121%, per un rischio
totale di 0,28% a segnale.

---

## 7. La sfida FundingPips: quale strategia la passa

Sfida da 5.000 $: fase 1 **+10%**, fase 2 **+6%**, perdita massima **12%**,
perdita giornaliera **4%**, nessun minimo di giornate.

E' un problema diverso da tutti gli altri di questo documento e va detto:
finora il criterio era "6% annuo col drawdown piu' piccolo", cioe' rendimento
per unita' di sofferenza su orizzonte lungo. Una sfida e' una **corsa a due
traguardi** — arrivare a +10% prima di −12%, senza mai perdere il 4% in una
giornata. Il rendimento annuo non conta: conta la probabilita' di arrivarci.

Simulate tutte le partenze possibili sulla sequenza storica delle 333
operazioni (`trading/scripts/sfida_prop.py`): il conto si apre a ogni
operazione e si segue fino a superamento, violazione o fine dei dati.

### Percentuale di partenze che superano la fase 1

| rischio/op | in uso | A | **B** | 1:2 |
|---|---|---|---|---|
| 0,50% | 89,8% | 91,6% | 91,3% | 85,3% |
| **0,75%** | 88,9% | 91,6% | **97,0%** | 88,3% |
| **1,00%** | 85,6% | 89,8% | **99,1%** | 88,6% |
| 1,25% | 60,4% | 54,4% | **61,3%** | 51,7% |
| 1,50% | 61,0% | 60,4% | 63,7% | 56,5% |

Entrambe le fasi di fila, alla taglia migliore di ciascuna: in uso **90%**,
A **91%**, **B 99%**, 1:2 **89%**.

### La B vince, e non per il motivo che sembrava

L'intuizione era che contassero le **perdite consecutive** (1:2 ne ha 7, B ne
ha 12) e che quindi la 1:2 potesse rischiare di piu'. E' vero come principio,
ma non basta: la B raggiunge il traguardo in **114 giorni mediani** contro i
**174** della 1:2, perche' rende il doppio in R (24,9 contro 12,4 R l'anno).
In una corsa la velocita' pesa quanto la sicurezza, e la B ha entrambe.

La 1:2 non e' pericolosa — a 1% non viola mai nemmeno lei — e' **lenta**: nel
11,4% delle partenze non arriva al traguardo prima che finiscano i dati.

### ATTENZIONE alla taglia: l'1,00% e' sul bordo di un precipizio

| B, rischio | passate | violate |
|---|---|---|
| 0,75% | 97,0% | **0,0%** |
| 1,00% | 99,1% | **0,0%** |
| **1,25%** | 61,3% | **38,1%** |

Fra 1,00% e 1,25% il risultato crolla. Il motivo e' aritmetico: la peggiore
serie storica della B e' di **12 perdite consecutive**, che all'1% fanno circa
−11,4% — dentro il limite del 12% **per sei decimi di punto**. Non c'e' nessuna
ragione perche' la peggiore serie futura sia anch'essa di 12: se ne arriva una
di 13, all'1% la sfida e' persa.

**Taglia consigliata: 0,75%.** Costa due punti di probabilita' (97% invece di
99) e quaranta giorni in piu', e compra il margine per una serie peggiore di
quella mai vista. Il 99% dell'1,00% e' una misura sul filo, non una garanzia.

### Due cose da verificare col fornitore prima di comprare

1. **La perdita massima del 12% e' statica o dinamica?** Qui e' modellata
   statica dal saldo iniziale. Se e' calcolata sul massimo raggiunto e' piu'
   severa e la taglia va abbassata ancora.
2. **Lo swap.** Le strategie **A e B tengono le posizioni oltre la giornata e
   attraversano il fine settimana**: sull'oro lo swap long di FP e' −71,5 punti
   a notte, triplicati il mercoledi'. Con la B l'add-on "Swap Free" non e' un
   optional. Per "in uso" e "1:2", che chiudono alle 21 UTC, e' irrilevante.

Se lo Swap Free non e' disponibile o non conviene, la scelta si sposta sulla
**1:2 secca all'1%**: 89% di successo, nessuna violazione, zero notti aperte,
zero rischio di gap nel fine settimana.
