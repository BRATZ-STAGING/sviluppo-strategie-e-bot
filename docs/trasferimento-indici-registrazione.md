# Trasferimento su altri mercati — registrazione preventiva (02/10/2026)

Scritto e pubblicato **prima** di eseguire qualunque test su questi dati.
Nessun numero degli indici sotto e' stato guardato al momento della stesura.

## La domanda

La strategia VWAP reclaim rende in ogni anno 2020-2026 e perde in undici anni
su undici nel 2009-2019 (appendici AU, AW, BS; cappello onesto in
`docs/CONSEGNA-BOT-2026-08.md` §7). Due spiegazioni restano aperte: un
vantaggio reale legato a qualcosa che non abbiamo misurato, oppure il frutto di
aver cercato dentro il 2020-2026.

Gli indici azionari non sono **mai** stati usati per scegliere nulla di questa
strategia (sull'S&P e' stato misurato solo l'ORB, appendici BJ-BL). Se le
stesse regole, **senza toccare un parametro**, rendono su mercati diversi, la
prima spiegazione guadagna peso. Se no, la seconda.

## Dati

Dukascopy, candele M1 BID e ASK, `trading/scripts/scarica_indice.py`:

| simbolo | mercato | periodo |
|---|---|---|
| USA500IDXUSD | S&P 500 (CFD) | 2012 → 2026 (dal primo giorno disponibile) |
| USATECHIDXUSD | Nasdaq 100 (CFD) | idem |
| DEUIDXEUR | DAX 40 (CFD) | idem |

Controllo: **XAUUSD 2009-2026** con la stessa pipeline.

## Le regole del trasferimento (fissate ora, non modificabili dopo)

1. **Ingresso identico** a `framework/taratura.py` (`UFFICIALE`): reclaim del
   VWAP giornaliero su M6, H6+H2 allineati, M33+H12 allineati, M12 contrario,
   filtro D1 contro media 50, orari 7-19 UTC, chiusura 21 UTC, max 3
   operazioni al giorno, 30 minuti fra segnali. Stessi orari UTC per tutti i
   mercati: nessun adattamento alle sessioni locali.
2. **Unita' di volatilita'.** I prezzi dell'indice (BID, e ASK per lo spread)
   si moltiplicano per un solo fattore `f = 25,5968 / mediana ATR14 D1
   dell'indice sul 2020-2024`, cioe' la stessa finestra e la stessa misura da
   cui viene la mediana dell'oro (`MEDIANA_ATR` in `verifica_bot.py`). Dopo la
   riscalatura le soglie in dollari dell'oro (impulso 4, buffer 0,3, rischio
   1-10, alta volatilita' a 1,5x la mediana) si applicano tali e quali. Il
   risultato in R e' invariante alla scala; il fattore serve solo a tradurre
   le soglie. Se un indice non copre tutto il 2020-2024, `f` si calcola sugli
   anni del 2020-2024 disponibili, e lo si dichiara.
3. **Costo.** Spread vero = mediana annua di (ASK close − BID close) sui minuti
   7-21 UTC, riscalata per `f`, applicata come costo di andata e ritorno come
   fa `verifica_bot.py` con il dizionario `SPREAD`. Nessuna commissione
   aggiuntiva (i CFD indice Dukascopy la includono nello scarto).
4. **Gestioni**: le quattro di `verifica_bot.py` (in uso, A, B, 1:2), senza
   modifiche. **Gestione primaria: B** (quella indicata per la produzione).
   Le altre si riportano tutte, nessuna si sceglie a posteriori.
5. **Placebo** (obbligatorio, CONSEGNA §4): per ogni mercato, 200 serie di
   ingressi casuali con lo stesso numero di operazioni per anno, gli stessi
   orari ammessi, direzione a caso, rischio campionato dalla distribuzione dei
   rischi dei segnali veri, gestione B. p = quota di placebo con R/op >= reale.

## Criterio di successo (per mercato, gestione B, intero periodo)

Un mercato **passa** se valgono tutte e tre:
- R/op netto > 0
- p placebo < 0,05
- anni positivi >= 2/3 degli anni con almeno 10 operazioni

Lettura complessiva:
- **2 o 3 indici passano** → l'idea si trasferisce: il vantaggio sull'oro
  2020-2026 diventa plausibilmente reale. Il 2009-2019 resta da spiegare.
- **1 indice passa** → inconcludente; quel mercato va messo in forward come
  qualunque altro candidato, senza conclusioni sull'oro.
- **nessuno passa** → conferma la seconda spiegazione del §7 della consegna.

## Controllo della pipeline (prima di guardare gli indici)

La stessa pipeline su XAUUSD 2020-2026 con `f = 1` deve riprodurre i numeri di
`verifica_bot.py` (B: +174,6 R su 333 operazioni) entro l'1%. Se non li
riproduce, i risultati sugli indici non si guardano finche' non li riproduce.

## Previsioni dichiarate (chi scrive, prima dei dati)

1. Almeno 2 indici su 3 **non** passano (R/op netto <= 0 o p >= 0,05).
2. Il placebo sugli indici avra' R/op mediano negativo di circa lo spread in R
   (il caso puro paga il costo).
3. Se un indice passa, sara' l'S&P 500, perche' ha il costo relativo piu'
   basso (CONSEGNA §5).

## Emendamento 1 — qualita' del dato (02/10/2026, PRIMA di qualunque dato)

Scritto dopo aver riletto l'appendice BL e prima che un solo file degli indici
fosse in cache (il primo tentativo di scarico e' stato respinto dal server con
429, zero file ottenuti). Non dipende da nessun risultato.

L'appendice BL ha mostrato che il feed indice Dukascopy dei primi anni e'
bucato (2012: ASK identico al BID, minuti mancanti) e che una serie bucata
**gonfia il risultato in R da sola** (+0,74 R/op sull'ORB 2012, "era il dato,
non la strategia"). Si adotta lo stesso filtro di BL, invariato:

- una giornata e' **sana** se ha scambi in >= 95% dei minuti 7-21 UTC e
  ASK > BID in >= 90% di quei minuti;
- nelle giornate non sane **non si apre** nessuna operazione (le candele
  restano nella serie per gli indicatori, che sono causali);
- lo spread annuo si misura sulle sole giornate sane;
- un anno con meno di 100 giornate sane si riporta a parte e **non conta**
  nel criterio degli anni positivi; il totale in R lo include.

## Emendamento 2 — fonte HistData, argento, VWAP senza volume (02/10/2026, PRIMA dei risultati)

Scritto quando il datafeed Dukascopy rispondeva a un file ogni 1-2 minuti
(429/503 anche da un altro indirizzo). Unico dato guardato finora: lo ZIP
SPXUSD 2015 di HistData, solo per verificare formato e fuso (distribuzione dei
minuti per ora UTC). Nessun segnale e nessun risultato calcolato.

**Fonte.** histdata.com, M1 ASCII, BID, orari EST fisso (UTC-5 tutto l'anno)
convertiti in UTC; `trading/scripts/scarica_histdata.py`, parquet in
`data/histdata/<SIMBOLO>/`. Periodo **2010 -> 2026**. Simboli: SPXUSD (S&P
500), NSXUSD (Nasdaq 100), GRXEUR (DAX) e **XAGUSD (argento)**, aggiunto ora
come quarto mercato: e' il piu' vicino all'oro e non e' mai stato usato.
Se i dati Dukascopy arrivano completi, si riporta il confronto fra le due
fonti, ma il verdetto e' quello di HistData (registrato qui per primo).

**VWAP.** HistData non ha volume (sempre 0): ogni minuto presente pesa **1**
(media del prezzo tipico nel tempo). Tutto il resto della regola e' invariato.
**Controllo obbligatorio** prima di guardare gli indici: XAUUSD 2020-2026 con
peso 1 al posto del volume Dukascopy, gestione B. Il test su HistData e'
**valido** solo se quel controllo resta positivo in almeno 6 anni su 7 e con
R/op entro +-35% di +0,52. Se non lo e', i risultati degli indici si
riportano ma il trasferimento si dichiara **non misurabile con questa fonte**.

**Spread** (niente ASK; valori prudenti fissati ora, in unita' del mercato,
poi riscalati per `f` come da protocollo):

| mercato | spread round trip | motivo |
|---|---|---|
| S&P 500 | 0,55 punti | >= ogni mediana annua Dukascopy misurata in BL (0,43-0,54) |
| Nasdaq 100 | 1,50 punti | FP oggi 1,00; margine per gli anni passati |
| DAX | 1,50 punti | FP oggi 0,80; margine per gli anni passati |
| argento | 0,025 $ | ordine di grandezza dei conti ECN; sensibilita' a 0,015 e 0,035 |

**Qualita' del dato** (sostituisce l'Emendamento 1 per questa fonte, che non
ha ASK): giornata sana se ha dati in >= 95% dei minuti 7-21 UTC. Resto
invariato (nessuna apertura nei giorni non sani, anni con < 100 giorni sani
fuori dal criterio).

**Previsione aggiuntiva per l'argento**: non passa, perche' a parita' di
volatilita' il suo spread pesa circa il doppio di quello dell'oro.

## Cosa NON si fa

- Nessun parametro tarato sugli indici, nessuna griglia, nessuna variante
  scelta dopo aver visto i numeri. Varianti eventuali = nuovo documento di
  registrazione, con dati nuovi.
- Nessun anno escluso a posteriori.
- I risultati negativi si scrivono con lo stesso spazio di quelli positivi.
