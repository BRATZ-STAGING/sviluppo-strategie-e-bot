# Le tre strategie da portare sul bot

> **CORREZIONE 04/10/2026.** Le tabelle dell'aggiornamento del 04/08 e delle
> sezioni sulla sfida venivano da `verifica_bot.py` e da tre script con la
> stessa copia del motore (`sfida_prop.py`, `portafoglio_quattro.py`,
> `run_pareggio_sopra.py`). Due difetti: la chiusura delle 21:00 UTC cercava
> una candela che con l'ora legale USA non esiste (d'estate "in uso", 1:2 e
> "in uso +0,50R" restavano aperte per giorni) e la A non chiudeva mai il
> venerdi'. Corretti (commit f32f32f e 1adeb9f; dettaglio in
> `docs/studies/verifica-bot-discrepanze.md`) coincidono col motore ufficiale:
> la tabella "I numeri" qui sotto (spread 0,30, con swap) era gia' giusta e ora
> le due tabelle dicono la stessa cosa. **La B non cambia.** In uso: +214,7 ->
> **+163,2 R**, DD 20,8 -> 16,3, 23 -> **11** perdite di fila, 6/7 -> **7/7**.
> A: +206,2 -> **+181,3 R**, DD 26,3 -> 15,9, 24 -> 15 di fila. 1:2: +86,6 ->
> **+71,3 R**, 6/7 -> **5/7**. **Conclusioni cambiate**: (1) la B batte la in
> uso anche in R assoluti (+7%, non −19%) e non e' piu' l'unica 7/7; (2) la in
> uso ha la striscia di perdite piu' corta dopo la 1:2 (11), quindi la tabella
> dei margini e il "non oltre lo 0,50%" vanno riletti (par. 7); (3) il pareggio
> a +0,50R **non** dimezza piu' le serie della in uso (11 -> 11) e non ne
> cambia il drawdown; resta utile sulla A; (4) la "Nota sui conteggi" in fondo
> era sbagliata: 23-24 perdite di fila e 21% di vinte erano il difetto, non
> una convenzione; (5) le taglie della configurazione finale non pareggiano
> piu' il drawdown (C 0,85% e in uso +0,50R 0,55% con la stessa regola). Le
> regole delle strategie e le taglie in vigore non sono state cambiate.

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

*(04/10/2026: con `verifica_bot.py` corretto, alla stessa parita' di spread e
swap, le due tabelle 2020-2026 coincidono: in uso +171,97 identica; la B di
`verifica_bot` senza swap fa +183,34, cioe' questa +173,89 piu' i 9,45 R di
swap; la A resta entro 1,4 R per la chiusura del venerdi' d'inverno, vedi
`docs/studies/verifica-bot-discrepanze.md`.)*

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
| in uso 1:10, pareggio +3R, EOD | +163,2 | 0,49 | 35,7% | 16,3 | 10,02 | **7/7** | +8,4 R | 49,3% | 11 |
| A · 1:8, pareggio +3R, chiude venerdi' | **+181,3** | **0,54** | 24,0% | 15,9 | 11,44 | **7/7** | **+12,9 R** | 43,5% | 15 |
| **B · 1:8, trail MFE−2 da +3R, weekend se >+1R** | +174,6 | 0,52 | 38,4% | 12,6 | **13,85** | **7/7** | +11,9 R | **55,1%** | 12 |
| **1:2 secco, niente pareggio, EOD** (nuova) | +71,3 | 0,21 | **48,1%** | **10,9** | 6,52 | 5/7 | −2,6 R | 52,2% | **7** |

*(Corretta il 04/10/2026. Prima: in uso +214,7 / 21,3% / DD 20,8 / 10,33 /
6/7 / −3,6 R / 44,9% / 23 di fila; A +206,2 / 16,8% / 26,3 / 7,84 / +7,5 R /
24 di fila; 1:2 +86,6 / 46,9% / 12,3 / 7,02 / 6/7.)*

La correzione del costo vale **il 5%** del totale (in uso: da +171,97 a
+163,19).
E' poco, e il motivo e' importante: lo **stop strutturale cresce da solo** con
la volatilita' — mediana 4,2 $ nel 2020, 14,8 $ nel 2026 — quindi il costo
relativo resta al 9,8% invece di salire. Una strategia a stop fisso non ha
questa protezione: con 3 $ fissi il costo e' passato dal 10% al 21%.

## 3. Quale avviare: **la B**, non quella in uso

Su quasi ogni misura che conta per un conto da far vedere a qualcuno, la B
vince:

| | in uso | **B** |
|---|---|---|
| anni positivi | **7/7** | **7/7** |
| anno peggiore | +8,4 R | **+11,9 R** |
| perdita massima | 16,3 R | **12,6 R** |
| rendimento per unita' di perdita | 10,02 | **13,85** |
| mesi positivi | 49,3% | **55,1%** |
| perdite consecutive | **11** | 12 |

Con i numeri corretti la B rende anche il **7% in piu'** in R assoluti (174,6
contro 163,2); la in uso ha solo una perdita consecutiva in meno. *(Prima della
correzione del 04/10/2026 la in uso sembrava rendere il 19% in piu', con 6/7
anni, DD 20,8 e 23 perdite di fila.)*

**Dimensionamento per un 6% annuo**: rischio **0,24% per operazione**, che
porta la perdita massima attesa al **3,0% del conto**. Per un 10% annuo:
rischio 0,40%, perdita massima 5,0%.

La **1:2 secca** e' l'alternativa se serve il tasso di vincite piu' alto
(48,1% contro 38,4%) e la striscia di perdite piu' corta (7 contro 12): costa
due anni negativi su sette (2023 −0,3 R, 2026 −2,6 R) e un drawdown piu' che
doppio a parita' di rendimento (6,4% contro 3,0% del conto per un 6% annuo).

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
  41-64) ma **non restituisce il vantaggio**: il 2009-2019 resta a +0,013 R/op
  lordo contro +0,54 del 2023-2026 (corretto 04/10/2026, appendice BX; prima
  +0,046 contro +0,72, con la finestra di 30 giorni senza chiusura alle 21);
- **non e' la tendenza di fondo**: condizionando sulla pendenza a 200 giorni,
  la fascia "sale forte" rende −0,001 netto nel 2009-2019 e +0,580 nel
  2020-2026 (numeri della finestra di 30 giorni, non rifatti dopo la
  correzione del 04/10/2026: vedi appendice BX).

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
| **in uso** | 1,000 | 0,816 | 0,751 | 0,662 |
| **A** | 0,816 | 1,000 | 0,807 | 0,588 |
| **B** | 0,751 | 0,807 | 1,000 | 0,689 |
| **1:2** | 0,662 | 0,588 | 0,689 | 1,000 |

Nel **51,4%** delle operazioni perdono **tutte e quattro**. Nel 23% guadagnano
tutte e quattro. *(Corretto il 04/10/2026: prima 52,6% e 15%, correlazione in
uso/B 0,683.)* Condividono lo stesso ingresso: aprono nello stesso minuto,
sullo stesso strumento, nella stessa direzione.

### A parita' di rendimento, quattro insieme e' PEGGIO della sola B

| obiettivo | solo B | tutte e quattro |
|---|---|---|
| 6% annuo | rischio 0,24%/op, **DD 3,03%** | 0,071%/op ciascuna, DD 3,54% |
| 12% annuo | rischio 0,48%/op, **DD 6,06%** | 0,142%/op ciascuna, DD 7,09% |
| 24% annuo | rischio 0,96%/op, **DD 12,13%** | 0,285%/op ciascuna, DD 14,18% |

La diversificazione vale **zero**, anzi meno di zero: a ogni livello di
rendimento la sola B ha il drawdown piu' piccolo. E lo fa con **una posizione
alla volta invece di quattro**, cioe' con un quarto della complessita'
operativa e un quarto delle cose che possono rompersi.

**Per avere piu' rendimento la strada e' aumentare la taglia della B, non
aggiungere le altre tre.**

### L'errore da non fare in nessun caso

Avviarle con la taglia da 6% annuo di ciascuna (in uso 0,26% · A 0,23% · B
0,24% · 1:2 0,59%) significa rischiare **1,32% del conto a ogni segnale**, non
il 6% annuo che ciascuna promette: il risultato e' **24% annuo con 16,0% di
perdita massima**. Puo' anche andare bene, ma va scelto, non subito.

Per restare al 6% annuo con tutte e quattro attive, ogni taglia va **divisa
per quattro**: in uso 0,064% · A 0,058% · B 0,060% · 1:2 0,147%, per un rischio
totale di 0,33% a segnale. *(Corretto il 04/10/2026: prima 0,20/0,20/0,24/0,48%,
1,12% a segnale, 13,7% di perdita massima.)*

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
| 0,50% | 90,7% | 91,3% | 91,3% | 85,0% |
| **0,75%** | 94,0% | 96,7% | **97,0%** | 88,0% |
| **1,00%** | 95,5% | 96,7% | **99,1%** | 88,6% |
| 1,25% | 54,1% | **61,6%** | 61,3% | 57,4% |
| 1,50% | 58,3% | **64,9%** | 63,7% | 62,5% |

Entrambe le fasi di fila, alla taglia migliore di ciascuna: in uso **95%**
(1,00%), A **96%** (0,75%), **B 99%** (1,00%), 1:2 **89%** (1,00%). All'1,00%
in uso e A violano gia' nel 2,4% delle partenze, la B mai.

*(Corretta il 04/10/2026; la colonna B non cambia. Prima: in uso 89,8 / 88,9 /
85,6 / 60,4 / 61,0%, A 91,6 / 91,6 / 89,8 / 54,4 / 60,4%, 1:2 85,3 / 88,3 /
88,6 / 51,7 / 56,5%; due fasi in uso 90%, A 91%.)*

### La B vince, e non per il motivo che sembrava

L'intuizione era che contassero le **perdite consecutive** (1:2 ne ha 7, B ne
ha 12) e che quindi la 1:2 potesse rischiare di piu'. E' vero come principio,
ma non basta: la B raggiunge il traguardo in **114 giorni mediani** contro i
**204** della 1:2, perche' rende piu' del doppio in R (24,9 contro 10,2 R
l'anno).
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
zero rischio di gap nel fine settimana. *(04/10/2026: con i numeri corretti
anche la in uso chiude alle 21 UTC e passa il 94% allo 0,75%, ma il suo
drawdown di 16,29 R a quella taglia fa 12,2%, sopra il limite: vedi sotto.)*

### Quanto margine lascia ogni taglia (striscia peggiore contro il limite del 12%)

La striscia peggiore mai vista costa −11,59 R alla "in uso" e −12,60 R alla B.
Tradotto in percentuale del conto, e confrontato col limite del 12%:

| rischio/op | in uso: costo | margine | **B: costo** | **margine** |
|---|---|---|---|---|
| 0,40% | 4,6% | +7,4% | **5,0%** | **+7,0%** |
| 0,50% | 5,8% | +6,2% | **6,3%** | **+5,7%** |
| 0,60% | 7,0% | +5,0% | 7,6% | +4,4% |
| 0,75% | 8,7% | +3,3% | **9,5%** | **+2,5%** |
| 1,00% | 11,6% | +0,4% | 12,6% | **−0,6%** |

*(Corretta il 04/10/2026: la striscia peggiore della in uso era data a −20,77 R,
che era il suo drawdown col difetto, e la conclusione era "la in uso non puo'
andare oltre lo 0,50%".)* Sulla sola striscia la in uso regge piu' della B.
Ma il suo **drawdown** (16,29 R) e' piu' lungo della striscia: allo 0,75% fa
12,2%, sopra il limite, e la regola della taglia sul drawdown (piu' sotto) la
tiene sotto lo 0,74%. La B regge fino a 0,75% con 2,5 punti di margine —
circa tre operazioni perdenti in piu' di quante ne siano mai capitate di
fila.

### Due sfide insieme aggiungono meno di quanto sembri

| coppia | entrambe passano | **almeno una** | nessuna | almeno una violata |
|---|---|---|---|---|
| in uso 0,50% + B 0,50% | 91% | **91%** | 9% | 0% |
| **in uso 0,50% + B 0,75%** | **91%** | **97%** | 3% | **0%** |
| in uso 0,75% + B 0,75% | 94% | 97% | 3% | 0% |

*(Corretta il 04/10/2026: prima 90 / 90 / 89% entrambe e 2% di violazioni
nell'ultima riga. La in uso allo 0,75% non viola nella simulazione, ma il suo
drawdown a quella taglia e' 12,2%: vedi sopra.)*

Il confronto che conta: **la sola B a 0,75% da' gia' il 97%.** Comprare anche
la seconda sfida non alza la probabilita' di essere finanziati — le due
strategie condividono l'ingresso (correlazione 0,75) e falliscono insieme.

Quindi:
- **se l'obiettivo e' passare**, basta la B a 0,75%: 97%, zero violazioni. La
  seconda sfida e' 28 € che non comprano probabilita';
- **se l'obiettivo sono due conti finanziati**, allora si comprano entrambe e
  nel 91% dei casi passano tutte e due. La seconda sfida raddoppia il premio,
  non riduce il rischio;
- **mai** mettere le due allo 0,50% "per prudenza": la coppia scende al 91%,
  peggio della sola B a 0,75%. Abbassare la taglia della B costa piu' di quanto
  renda abbassare quella della "in uso".

---

# CONFIGURAZIONE FINALE PER LA SFIDA — 05/08/2026 (rivista)

Tre profili su tre conti separati. **Le taglie sono state scelte diverse
perche' i drawdown sono diversi**: si pareggia il rischio in percentuale di
conto, non la percentuale per operazione. Tre conti tutti allo 0,75% avrebbero
avuto rischi molto diversi senza che si vedesse.

*(Corretta il 04/10/2026. Con i drawdown corretti le taglie in vigore non
pareggiano piu': B −9,45%, C −8,19%, in uso +0,50R −8,15%. Con la stessa regola
sarebbero C 0,85% (−9,28%, fase 1 88%) e in uso +0,50R 0,55% (−8,96%, fase 1
92%). Le taglie della tabella non sono state cambiate: decide l'utente. In
`docs/AVVIO-MT5-VPS.md` il terzo profilo diventa D, solo long, allo 0,53%.)*

| | **B** | **C** | **in uso +0,50R** |
|---|---|---|---|
| obiettivo | 1:8 | 1:2 secco | 1:10 |
| gestione | trailing MFE−2 da +3R | nessuno spostamento dello stop | stop a **+0,50 R** quando l'MFE tocca +3R |
| chiusura | oltre la giornata, weekend solo sopra +1R | 21:00 UTC | 21:00 UTC |
| **rischio per operazione** | **0,75%** | **0,75%** | **0,50%** |
| drawdown massimo | 12,60 R -> **−9,45%** | 10,92 R -> **−8,19%** | 16,29 R -> **−8,15%** |
| margine sul limite del 12% | 2,55 punti | 3,81 punti | 3,85 punti |
| **fase 1 superata** | **97%** | 88% | 91% |
| violazioni | 0% | 0% | 0% |
| giorni mediani | **156** | 272 | 255 |
| **win rate** | 38,4% | **48,1%** | 42,9% |
| **perdite di fila** | 12 | **7** | 11 |
| costo di quella serie | −12,60 R | −8,00 R | −11,59 R |
| anni positivi | **7/7** | 5/7 | **7/7** |

*(Prima della correzione: C DD 12,33 R / −9,25% / 2,75 punti / 258 giorni /
46,9% / 6/7; in uso +0,50R DD 19,77 R / −9,89% / 2,11 punti / 90% / 221
giorni / 39,0% / 6/7.)*
| Swap Free | **necessario** | non serve | non serve |

## Correzione a una versione precedente di questa scheda

Una stesura precedente dava alla C **1,00%** di rischio e "6,0 punti di
margine". Sbagliato due volte: il margine era calcolato sul **costo della
serie** (−8,00 R) invece che sul **drawdown** (12,33 R), e allo 0,75% invece
che all'1,00%. All'1,00% la C sta a −12,33%, cioe' **sopra il limite**. Le
zero violazioni della simulazione non la salvavano: significano solo che
nessuna partenza era capitata dentro quella discesa prima di arrivare a +10%.

E' lo stesso errore descritto qui sotto, commesso mentre lo si documentava.
Vale la pena lasciarlo scritto: **la taglia si calcola SEMPRE sul drawdown**.

# CONFIGURAZIONE PRECEDENTE (superata, tenuta per storia)

*(Numeri di allora, prima della correzione del 04/10/2026: la C oggi da' 88%
di fase 1 in 272 giorni allo 0,75% e 89% in 204 giorni all'1,00%.)*

Scelta dell'utente dopo la simulazione: si avviano **due** profili, su due conti
separati.

| | **B** | **C** |
|---|---|---|
| obiettivo | 1:8 | **1:2 secco** |
| gestione | da +3R lo stop insegue l'MFE a distanza 2R | **nessuno spostamento dello stop** |
| chiusura | oltre la giornata; il fine settimana si attraversa solo sopra +1R | ogni sera alle **21:00 UTC** |
| **rischio per operazione** | **0,75%** | **1,00%** |
| fase 1 superata | **97%** | 88% |
| violazioni | **0%** | **0%** |
| giorni mediani | 156 | 258 |
| margine sul limite del 12% | 2,5 punti | **6,0 punti** |
| perdite consecutive | 12 | **7** |
| Swap Free | **necessario** | non serve |

Sotto il lotto minimo negoziabile l'operazione si **salta**: in una sfida il
vincolo e' sopravvivere, non fare numero. Con 5.000 $ allo 0,75% si rischiano
37,50 $ per operazione, che con lo stop mediano di 10-15 $ fanno 0,03-0,04
lotti; nei mesi agitati lo stop sale a 25-30 $ e si arriva al minimo.

## Cosa NON fare su queste due

- **Non aggiungere un pareggio alla C.** Misurato: portando lo stop a +1R la C
  passa da **+71,3 a +41,5 R**, cioe' perde il 42% (prima della correzione del
  04/10/2026: da +86,6 a +47,3, −45%). Il 1:2 secco vive delle
  operazioni che vanno dritte al bersaglio, e qualunque stop mosso per strada
  le taglia prima.
- **Non spostare il pareggio della B.** Il suo trailing porta gia' lo stop a
  +1R quando l'MFE tocca +3R: la modifica e' gia' dentro, ed e' il motivo per
  cui la B non ha uscite a pareggio.

## Il pareggio sopra l'ingresso: dove invece serve

Proposta dell'utente, misurata su tutte e quattro. Portare lo stop a **+0,50 R**
sopra l'ingresso invece che esattamente a pareggio:

| | R | vinte% | perdite di fila | costo serie | DD R | R/DD |
|---|---|---|---|---|---|---|
| in uso, pareggio a 0 | 163,2 | 35,7% | 11 | −11,59 R | 16,29 | 10,02 |
| **in uso, pareggio +0,50R** | 165,5 | **42,9%** | 11 | −11,59 R | 16,29 | **10,16** |
| A, pareggio a 0 | 181,3 | 24,0% | 15 | −12,60 R | 15,85 | 11,44 |
| **A, pareggio +0,50R** | **188,7** | **38,7%** | **12** | −12,60 R | **12,60** | **14,97** |

*(Corretta il 04/10/2026. Prima: in uso 214,7 / 21,3% / 23 / −20,77 / 20,77 /
10,33 e con +0,50R 209,9 / 39,0% / 11 / −11,59 / 19,77 / 10,62; A 206,2 /
16,8% / 24 / −16,18 / 26,30 / 7,84 e con +0,50R 216,7 / 36,6% / 12 / −12,60 /
16,80 / 12,90.)*

Su **A rende di piu' e rischia meno**, il che e' raro. Su **in uso**, con i
numeri corretti, rende l'1% in piu' e alza le vinte dal 36% al 43%, ma **non
accorcia la serie peggiore (11 in entrambi) e non cambia il drawdown**: la
serie di 23 che dimezzava era il difetto della chiusura di fine giornata.
**+0,50 R batte sia +1 $ sia +2 $**:
due dollari sopra uno stop da 2 $ sono un intero R, sopra uno da 15 $ sono un
settimo — in dollari fissi si applica una regola diversa ogni mese.

Per un conto normale e' un miglioramento netto sulla A e marginale sulla in
uso. **Per la sfida non serve**: allo 0,50% la percentuale di successo resta
91% con e senza, perche' quello che fa saltare il conto non e' la serie, e' il
drawdown — e quello non cambia (16,29 R in entrambi).

## La lezione di metodo che ne esce

**Contare le perdite consecutive non basta a dimensionare.** Serie perdente e
drawdown massimo coincidono solo quando la discesa e' ininterrotta:

| | costo serie peggiore | drawdown massimo |
|---|---|---|
| **B** | −12,60 R | **12,60 R** (coincidono) |
| in uso + pareggio 0,5R | −11,59 R | **16,29 R** (non coincidono) |

Il drawdown della "in uso" e' una discesa lunga **spezzata da piccole vittorie
che non recuperano**: il contatore delle serie si azzera, il conto no. La
taglia va sempre calcolata sul drawdown.

## Nota sui conteggi, per non ricascarci

*(Riscritta il 04/10/2026: la versione precedente era sbagliata.)*

Le tabelle delle sessioni precedenti riportavano **13-14 perdite di fila per
tutte le gestioni** e tassi di vincita intorno al 35%. Quelle del 04/08
dicevano 23-24 e 21%, e questa nota le spiegava con la convenzione sui
pareggi (60 uscite a pareggio su 333 per la "in uso"). **Non era una
convenzione, era un difetto**: `verifica_bot.py` cercava la chiusura di fine
giornata nella candela delle 21:00 UTC, che con l'ora legale USA non esiste,
quindi d'estate la "in uso" restava aperta per giorni e finiva a pareggio o
allo stop invece che alla chiusura serale; e la A non chiudeva mai il
venerdi'. Corretto: la "in uso" chiude 24 operazioni a pareggio, fa 35,7% di
vinte e 11 perdite di fila, la A 15 — vicino ai numeri delle sessioni
precedenti. Le altre differenze restano: 348 operazioni contro 333 per la
correzione del filtro D1 (appendice BD) e lo spread vero al posto dello 0,30
della taratura (drawdown 17,6 R allora, 16,29 oggi).

**Su B e C la convenzione sui pareggi non conta**: non hanno uscite a
pareggio, quindi 12 e 7 valgono con qualunque convenzione.
