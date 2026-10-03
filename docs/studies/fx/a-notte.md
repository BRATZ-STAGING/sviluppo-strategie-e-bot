# Famiglia 1 — Notte asiatica: ritorno alla media 22:15-06:00 UTC (scoperta 2010-2017)

Protocollo: `docs/fx-intraday-registrazione.md`. Script:
`trading/scripts/fx_a_notte.py`. Dati: solo `D:\ricerca_fx\scoperta\` (M5 e
D1 BID, indice UTC all'apertura). Coppie: EURUSD, USDJPY, GBPUSD, AUDUSD,
USDCHF, USDCAD, EURJPY. 1 pip = 0,0001 (0,01 per le coppie JPY).

## Varianti dichiarate PRIMA del calcolo (03/10/2026)

Regole fisse (non sono dimensioni di ricerca):

- **Notte**: candele M5 da 22:10 a 05:55 UTC; la notte prende la data del
  giorno in cui finisce (lun-ven; la notte di "lunedi'" e' quella che apre la
  domenica sera).
- **Segnale** sulla chiusura di una M5, **entrata all'apertura della M5
  successiva**; gestione su M5; stop prima dell'obiettivo nella stessa
  candela; apertura oltre lo stop = uscita all'apertura; obiettivo eseguito al
  suo livello (nessun miglioramento); se nessuno dei due, uscita forzata alla
  chiusura dell'ultima M5 prima dell'ora d'uscita.
- **Una posizione alla volta per coppia e regola**; dopo l'uscita si puo'
  rientrare al segnale successivo (segnale sulla chiusura della candela
  d'uscita o dopo). Operazioni della stessa coppia quindi mai sovrapposte.
- **ATRd** = media del true range dei 14 giorni UTC validi (lun-ven, >= 600
  minuti) **conclusi prima del giorno in cui la notte inizia** (causale,
  fisso per tutta la notte). Distanze di segnale, stop e obiettivi in
  frazioni di ATRd.
- **Costi** round trip FP Raw: EURUSD 0,8; GBPUSD 1,0; AUDUSD 0,9; USDCHF 1,0;
  USDCAD 1,2; USDJPY 1,2; EURJPY 1,4 pip; **x2 per entrate 22:15-23:59 UTC**;
  nessuna entrata 20:45-22:15; tutto misurato anche con costi **x1,5**.
  Nessuno swap: si entra dopo il rollover e si esce entro le 06:00.
- Segnale scartato se la distanza dall'entrata all'obiettivo e' < 1 costo
  round trip (base) o se l'apertura d'entrata ha gia' superato l'obiettivo.

Dimensioni della griglia:

1. **Segnale (15)**
   - DEV (9): scarto della chiusura dalla media semplice delle ultime N
     chiusure M5 > k x ATRd -> contro (sopra = vendi, sotto = compra);
     N in {12, 24, 48} candele (1, 2, 4 ore), k in {0,06; 0,10; 0,15}.
   - CAN (6): chiusura oltre il massimo (minimo) delle N candele
     precedenti di almeno x x ATRd -> contro; N in {12, 24, 48},
     x in {0; 0,05}.
2. **Obiettivo (3)**: CENTRO (media N per DEV, centro del canale N per CAN,
   livello fissato al segnale); 0,04 x ATRd; 0,08 x ATRd dall'entrata.
3. **Stop (3)**: 0,10; 0,20; 0,40 x ATRd dall'entrata.
4. **Finestra (3)**: A entrate 22:15-03:55, uscita forzata 05:00;
   B entrate 00:00-03:55, uscita 05:00; C entrate 00:00-05:25, uscita 06:00.
5. **Filtro di volatilita' (5)**: tutti; ATRd basso / alto (terzile del
   rango di ATRd fra le 250 notti precedenti della coppia, minimo 60);
   range della sessione USA precedente (13:00-20:45 UTC dell'ultimo giorno
   feriale <= inizio notte) / ATRd basso / alto (stessi terzili).
6. **Giorno (2)**: tutte le notti; escluse la notte di lunedi' (apertura
   della domenica) e quella di venerdi' (gio->ven).

**Regole: 15 x 3 x 3 x 3 x 5 x 2 = 4050**, ciascuna misurata sulle 7 coppie
(**28350 celle regola-coppia**). Una regola si valuta sull'insieme delle
coppie dove il suo netto x1 e' > 0 (insieme scelto a posteriori: la
promozione lo congela per la verifica) e, per onesta', anche sulle 7 coppie.

Statistiche: n; operazioni per giornata di borsa (per coppia e sommate);
netto medio in pip e in multipli del costo pagato; **t sul netto calcolato
sulle somme per notte** (somma delle coppie dell'insieme: tiene conto della
correlazione fra coppie e fra operazioni della stessa notte; per coppia le
operazioni non si sovrappongono); anni positivi su 8; netto x1,5; placebo
(stessi istanti, stessa gestione speculare, direzione casuale, 1000 serie,
seed 20261003) p; peggior perdita singola, peggior serie di perdite
consecutive e massimo drawdown in pip. Il placebo esatto si calcola per le
regole che passano gli altri criteri e per le migliori per t; per tutte le
altre si riporta l'approssimazione normale (z).

Promozione: netto > 0 a x1 e x1,5; t >= 3; anni >= 6/8; p < 0,01;
>= 1 operazione per giornata di borsa sommando le coppie della regola; al
massimo 3 candidati.

## Risultati (03/10/2026)

Motore confrontato con un ciclo candela per candela su 400 operazioni
EURUSD a caso: differenza 0,0000 pip; nessuna operazione sovrapposta nella
stessa regola; nessuna entrata fra 20:45 e 22:15 UTC. 2055 notti valide per
coppia.

**Regole provate: 4050 (28350 celle regola-coppia)**, tutte valutate.

| filtro | celle regola-coppia | regole, insieme coppie positive | regole, tutte 7 |
|---|---|---|---|
| lordo > 0 | 20229 (71%) | — | — |
| netto > 0 (x1) | 3936 (14%) | 2050 | 123 |
| netto > 0 con x1,5 | — | 759 | 25 |
| t >= 3 | 27 | 12 | **0** (max 2,28) |
| anni >= 6/8 | — | 694 | 44 |
| >= 1 op/giorno | — | 291 | 3663 |
| tutto tranne placebo | — | **1** | 0 |
| + placebo p < 0,01 | — | **1** | 0 |

### Le migliori 12 per t (insieme delle coppie dove la regola e' positiva)

Tutte e 12 le regole con t >= 3 usano il filtro "sessione USA precedente
ampia". Coppie: EU = EURUSD, GB = GBPUSD, CHF = USDCHF, CAD = USDCAD.

| regola (segnale / finestra / obiettivo / stop / filtro) | coppie | n | op/giorno | netto pip/op | netto/costo | netto x1,5 | t | anni + | p | peggiore pip | serie perse | DD pip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEV N48 0,15 / C / CENTRO / 0,40 / USAalto | EU,CHF | 852 | 0,41 | 2,34 | 2,61 | 1,89 | 3,42 | 8 | 0,001 | -90,3 | 11 | 306 |
| DEV N48 0,10 / C / 0,08 / 0,40 / USAalto | EU,CHF | 2010 | 0,98 | 1,02 | 1,14 | 0,57 | 3,34 | 8 | 0,001 | -90,3 | 6 | 309 |
| DEV N24 0,15 / A / CENTRO / 0,10 / USAalto | EU,GB,CHF | 1582 | 0,77 | 1,34 | 1,14 | 0,75 | 3,29 | 7 | 0,001 | -33,9 | 23 | 397 |
| CAN N24 0,05 / C / CENTRO / 0,20 / USAalto | EU,GB,CHF,CAD | 1188 | 0,58 | 1,70 | 1,69 | 1,20 | 3,22 | 7 | 0,001 | -45,6 | 8 | 390 |
| DEV N48 0,15 / B / CENTRO / 0,20 / USAalto | EU,CHF | 861 | 0,42 | 1,81 | 2,03 | 1,37 | 3,16 | 8 | 0,001 | -45,6 | 9 | 310 |
| CAN N24 0,05 / C / CENTRO / 0,20 / USAalto, no lun/ven | EU,GB,CHF | 507 | 0,25 | 2,52 | 2,72 | 2,06 | 3,14 | 7 | 0,001 | -39,1 | 6 | 270 |
| DEV N24 0,15 / A / CENTRO / 0,40 / USAalto | EU,CHF | 695 | 0,34 | 2,42 | 2,11 | 1,85 | 3,11 | 8 | 0,001 | -91,1 | 6 | 301 |
| DEV N48 0,15 / B / CENTRO / 0,40 / USAalto | EU,CHF | 754 | 0,37 | 2,06 | 2,31 | 1,62 | 3,08 | 8 | 0,001 | -90,3 | 11 | 306 |
| CAN N24 0,05 / C / CENTRO / 0,40 / USAalto, no lun/ven | EU,GB,CHF,CAD | 652 | 0,32 | 2,35 | 2,34 | 1,85 | 3,06 | 7 | 0,001 | -77,4 | 7 | 233 |
| DEV N48 0,15 / C / CENTRO / 0,10 / USAalto | EU,GB,CHF | 1931 | 0,94 | 1,15 | 1,24 | 0,68 | 3,04 | 8 | 0,001 | -32,9 | 21 | 449 |
| DEV N24 0,15 / C / CENTRO / 0,10 / USAalto | EU,GB,CHF | 1438 | 0,70 | 1,41 | 1,53 | 0,95 | 3,01 | 8 | 0,001 | -23,7 | 20 | 359 |
| **DEV N48 0,10 / C / CENTRO / 0,10 / USAalto** | **EU,GB,CHF** | **3619** | **1,76** | **0,74** | **0,80** | **0,28** | **3,00** | **8** | **0,001** | **-32,9** | **21** | **420** |

"netto/costo" = netto totale / costo totale pagato. p = placebo esatto (1000
serie; 0,001 e' il minimo). Solo l'ultima riga raggiunge anche 1 operazione
al giorno. Senza scegliere le coppie (tutte 7) la regola migliore e'
DEV N48 0,15 / A / CENTRO / 0,40 / ATR alto, no lun/ven: +1,64 pip/op,
0,85 op/giorno, t 2,28, peggiore -143 pip.

### Diagnostica per dimensione (mediane sulle 28350 celle)

| dimensione | valore | lordo pip/op | netto pip/op | quota netto > 0 | op/giorno |
|---|---|---|---|---|---|
| coppia | GBPUSD | 0,90 | -0,19 | 37% | 0,34 |
| | USDCHF | 0,72 | -0,37 | 26% | 0,36 |
| | EURJPY | 0,40 | -1,12 | 6% | 0,59 |
| | EURUSD | 0,33 | -0,55 | 18% | 0,39 |
| | USDCAD | 0,31 | -0,98 | 5% | 0,39 |
| | USDJPY | -0,07 | -1,37 | 3% | 0,71 |
| | AUDUSD | -0,10 | -1,05 | 2% | 0,80 |
| obiettivo | CENTRO / 0,08 / 0,04 ATR | 0,50 / 0,35 / 0,23 | -0,70 / -0,85 / -0,96 | 24% / 13% / 4% | |
| filtro vol. | USA alto | 0,58 | -0,63 | 25% | 0,44 |
| | ATR alto | 0,49 | -0,66 | 22% | 0,32 |
| | tutti | 0,37 | -0,82 | 10% | 1,25 |
| | ATR basso | 0,27 | -0,95 | 9% | 0,58 |
| | USA basso | -0,01 | -1,18 | 4% | 0,38 |

Finestre (A 0,45 / B 0,30 / C 0,25 lordo) e stop (0,10 / 0,20 / 0,40: 0,31 /
0,34 / 0,37) cambiano poco; A ha il lordo piu' alto ma paga il costo x2
prima di mezzanotte.

### Candidato 1 (unico): DEV48-C-USAalto su EURUSD, GBPUSD, USDCHF

Specifica esatta ed eseguibile (prezzi BID M5, orari UTC all'apertura
della candela):

- **Coppie**: EURUSD, GBPUSD, USDCHF (insieme congelato).
- **ATRd**: media del true range degli ultimi 14 giorni UTC validi (lun-ven,
  >= 600 minuti di dati) conclusi **prima** del giorno di calendario in cui
  la notte inizia (per la notte domenica->lunedi': fino al venerdi').
- **Filtro di notte**: R = (massimo - minimo) delle M5 13:00-20:40
  (sessione 13:00-20:45) dell'ultimo giorno feriale <= giorno d'inizio
  della notte (almeno 60 candele), diviso ATRd. Si opera la notte solo se R
  e' >= al 66,7-esimo percentile dei valori di R delle 250 notti valide
  precedenti della stessa coppia (servono almeno 60 valori). Tutti i giorni
  della settimana.
- **Segnale**: alla chiusura di ogni M5 dalle 23:55 alle 05:20,
  SMA48 = media delle ultime 48 chiusure M5 (serie continua, candela
  corrente inclusa). Se chiusura - SMA48 > 0,10 x ATRd -> **vendi**; se
  < -0,10 x ATRd -> **compra**. Entrata a mercato all'apertura della M5
  successiva (entrate 00:00-05:25).
- **Obiettivo**: limite al valore di SMA48 della candela del segnale
  (senza miglioramento). Segnale scartato se all'entrata la distanza
  dall'obiettivo e' < 1 costo round trip o l'obiettivo e' gia' superato.
- **Stop**: 0,10 x ATRd dall'entrata (circa 9-14 pip su EURUSD); se una M5
  apre oltre lo stop, uscita all'apertura; stop e obiettivo nella stessa
  candela = stop.
- **Uscita forzata**: chiusura della M5 delle 05:55 (06:00 UTC).
- **Una posizione alla volta per coppia**; dopo l'uscita si rientra al
  primo segnale successivo (anche sulla chiusura della candela d'uscita).
- **Costo**: 0,8 / 1,0 / 1,0 pip round trip (entrate tutte dopo mezzanotte:
  x1). Nessuno swap.

| misura | valore |
|---|---|
| n (2010-2017) | 3619 |
| operazioni per giornata di borsa | **1,76** (EURUSD 0,62; GBPUSD 0,56; USDCHF 0,58) |
| netto x1 | **+0,742 pip/op** = 0,80 volte il costo pagato |
| netto x1,5 | **+0,277 pip/op** |
| t sul netto (somme per notte) | **3,00** |
| anni positivi | 8/8 a x1; **6/8 a x1,5** (2012 e 2017 negativi) |
| placebo p | 0,001 |
| vinte | 48%, media +12,6 pip; perse media -10,1 pip |
| uscite | 43% stop, 33% obiettivo, 25% a tempo (+4,4 pip medi) |
| peggiore operazione | -32,9 pip (apertura oltre lo stop) |
| peggiore serie | 21 perdite di fila, -419 pip |
| drawdown massimo | 420 pip = 1,25 anni di utile medio (335 pip/anno sulle tre coppie); a x1,5 579 pip = 4,6 anni (125 pip/anno) |
| per coppia (netto pip/op, t, anni) | EURUSD +1,40, 3,68, 8/8; GBPUSD +0,59, 1,67, 5/8; USDCHF +0,19, 0,63, 4/8 |
| per anno, netto pip (x1) | 2010 +754, 2011 +607, 2012 +34, 2013 +280, 2014 +203, 2015 +314, 2016 +482, 2017 +10 |
| per ora d'entrata, netto pip/op | 00h +1,84 (1165 op), 01h 0,00, 02h -0,83, 03h +0,83, 04h +2,64, 05h -0,63 |

**Giudizio**: passa i criteri formali, ma **sulla soglia** e con tre segnali
d'allarme: (1) t = 3,001 dopo 4050 regole e dopo aver scelto le coppie a
posteriori — la stessa regola sulle 7 coppie fa -0,14 pip/op (t -0,9) e
senza il filtro USA sulle stesse 3 coppie +0,14 (t 0,9); (2) il vantaggio
viene quasi tutto da EURUSD (le altre due coppie servono alla frequenza) e
dalle entrate fra 00:00 e 00:55, l'ora in cui lo spread reale puo' essere
ancora sopra la media del protocollo; (3) a x1,5 il netto scende a
+0,28 pip/op con due anni negativi e un drawdown pari a 4,6 anni di utile. La
previsione 3 del protocollo vale qui con forza: la verifica 2018-2026
probabilmente lo respinge.

Nessun altro candidato: le altre 11 regole con t >= 3 restano sotto
1 operazione al giorno (0,25-0,98).

### Osservazioni

1. **Il ritorno alla media notturno esiste al lordo, il costo lo mangia.**
   Il 71% delle 28350 celle e' positivo al lordo (mediana +0,35 pip/op), solo
   il 14% al netto (mediana -0,85). Gli obiettivi piccoli (0,04 x ATRd, lo
   "scalping" vero) sono i peggiori: 4% delle celle positive. Conferma la
   previsione 1 del protocollo: molti effetti lordi, perdite rare e grandi
   (stop 0,40: peggiori -90/-143 pip), estrema sensibilita' ai costi.
2. **La notte rientra di piu' dopo una sessione USA agitata.** Il filtro sul
   range USA precedente e' la dimensione piu' forte: lordo mediano +0,58
   pip/op con range alto contro -0,01 con range basso, e tutte le 12 regole
   con t >= 3 lo usano. L'ATR giornaliero alto va nella stessa direzione ma
   piu' debolmente.
3. **Le coppie "asiatiche" non rientrano.** USDJPY e AUDUSD, le piu' attive
   di notte, hanno lordo mediano zero o negativo (e il maggior numero di
   segnali: in Asia si muovono davvero, con direzione); il rientro e' una
   proprieta' delle coppie europee ferme di notte (GBPUSD, USDCHF, EURUSD),
   dove pero' muovendosi poco il vantaggio per operazione resta vicino al
   costo.

Dettaglio in `D:\ricerca_fx\risultati\`: `a_notte_regole.parquet` (una riga
per regola e insieme di coppie), `a_notte_coppie.parquet` (una riga per
regola-coppia), `a_notte_operazioni_<COPPIA>.parquet` (una riga per
operazione, con l'esito della direzione opposta per il placebo),
`a_notte_notti_<COPPIA>.parquet` (ATRd e ranghi dei filtri per notte),
`a_notte_scelte.parquet` (placebo esatto e rischio delle 20 regole
approfondite), `a_notte_candidato1_operazioni.parquet`.
