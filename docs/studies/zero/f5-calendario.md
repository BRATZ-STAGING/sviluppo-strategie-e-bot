# Famiglia 5 — Calendario (scoperta 2009/2010-2017)

Protocollo: `docs/ricerca-da-zero-registrazione.md`. Script:
`trading/scripts/zero_f5_calendario.py`. Dati: solo `D:\ricerca_zero\scoperta\`
(M5; le giornate si costruiscono dalle M5, le D1 a mezzanotte UTC non si usano).

## Varianti dichiarate PRIMA del calcolo (02/10/2026)

**Giornate.** 8 mercati-giornata come in f4: "22-22" = M5 con apertura in
[D-1 22:00, D 22:00) UTC etichettata D (la sera della domenica va nel lunedi';
per il DAX coincide col giorno UTC) per oro, argento, S&P, Nasdaq, DAX; "cash"
= S&P e Nasdaq 9:30-16:00 New York, DAX 9:00-17:30 Berlino, ora legale vera
(zoneinfo). Giornata valida = giorno feriale con almeno il 50% delle M5 della
mediana; i "giorni di borsa" del mese e della settimana sono le giornate valide.

**Prezzi di riferimento (eseguibili, il calendario e' noto in anticipo).**
Chiusura del giorno = apertura dell'ULTIMA M5 della giornata (segnale sulla
penultima, entrata all'apertura della successiva, come da protocollo);
apertura = apertura della prima M5; "ultime 2 ore" = apertura della M5 che
inizia 2 h prima dell'ultima; "prime 2 ore" = apertura della prima M5 >= prima
+ 2 h. Costi round trip: oro 0,40, argento 0,025, S&P 0,55, Nasdaq 1,50,
DAX 1,50 (un costo per operazione). Rendimento netto in % = (uscita -
entrata) x direzione / entrata - costo / entrata. Le operazioni di una stessa
variante non si sovrappongono per costruzione.

**(a) Giorno della settimana — 110 varianti**
- 5 giorni (lun-ven) x 2 direzioni (long, short)
- 22-22 (5 mercati): tenuta CC = chiusura del giorno valido precedente ->
  chiusura del giorno (il lunedi' include il fine settimana): 5 x 5 x 2 = 50
- cash (3 mercati): tenuta CC e OC (apertura -> chiusura della sessione cash):
  3 x 5 x 2 x 2 = 60

**(b) Fine/inizio mese — 304 varianti**
- finestra (k, j): entrata alla chiusura del giorno di borsa TD-(k+1) (TD-1 =
  ultimo del mese), uscita alla chiusura di TD+j del mese successivo; include
  quindi gli ultimi k e i primi j giorni. k in {0,1,2,3}, j in {0,...,4},
  esclusa (0,0): 19 finestre
- 8 mercati-giornata x 19 x 2 direzioni = 304
- una operazione al mese: **per costruzione non arrivano a 100 operazioni**
  argento (95 mesi) e indici (85 mesi); solo l'oro (107 mesi) puo' arrivarci.

**(c) Prima/dopo il fine settimana — 80 varianti**
- coppia = ultimo giorno valido della settimana (di solito venerdi') e primo
  della successiva (di solito lunedi')
- 5 finestre: WG chiusura ven -> apertura lun (solo il buco del fine
  settimana); WF2 ultime 2 ore del venerdi'; WFG ultime 2 ore del venerdi' ->
  apertura lun; WM2 prime 2 ore del lunedi'; WGM2 chiusura ven -> apertura lun
  + 2 ore
- 8 mercati-giornata x 5 x 2 direzioni = 80
- (la tenuta chiusura ven -> chiusura lun coincide con il lunedi' CC di (a):
  non si ripete)

**(d) Settimana delle scadenze mensili delle opzioni USA — 24 varianti**
- terzo venerdi' del mese (se festivo, l'ultimo giorno valido <= terzo venerdi'
  della stessa settimana); S&P e Nasdaq, 22-22 e cash (4 mercati-giornata)
- 3 finestre: OW chiusura dell'ultimo giorno valido prima della settimana ->
  chiusura del venerdi' delle scadenze; OWP chiusura del venerdi' delle
  scadenze -> chiusura dell'ultimo giorno valido della settimana dopo; OF solo
  il venerdi' delle scadenze (CC)
- 4 x 3 x 2 direzioni = 24
- una operazione al mese: **per costruzione < 100 operazioni (85 mesi)**.

**(e) Descrittive (non sono prove):** volatilita' per giorno della settimana
(range / atr_pre e |rendimento CC| per giorno, 22-22 e cash); rendimento medio
per mese dell'anno (chiusura ultimo giorno del mese prima -> chiusura ultimo
giorno del mese) con anni positivi; rendimento medio per posizione del giorno
nel mese (TD-5 ... TD+5).

**Totale dichiarato: 110 + 304 + 80 + 24 = 518 varianti.**

**Statistiche.** n; netto medio in prezzo, in % e in multipli del costo; t =
media / dev. std x radice(n) sul netto in %; anni positivi (somma del netto %
> 0) sugli anni con almeno 5 operazioni (anno = anno di entrata).
**Placebo (due, seed 12345, 1000 serie ciascuno):**
- DATE: stesso numero di operazioni, stessa finestra (stessa durata in giorni di
  borsa per CC, stesso tratto della giornata per OC/WG/WF2/...), stessa
  direzione, su giornate di ancoraggio estratte a caso fra tutte quelle valide
  dello stesso mercato-giornata; confronta l'effetto con la deriva del mercato.
- DIREZIONE: stesse operazioni con direzione casuale.
p = (1 + #placebo con netto medio >= reale) / 1001. Promozione: netto > 0,
t >= 3, anni positivi >= 75%, p DATE < 0,01 e p DIREZIONE < 0,01, n >= 100.
Massimo 3 candidati (i migliori per t).

## Risultati (calcolati il 02/10/2026 sui file di scoperta)

Varianti calcolate: **518** (a 110, b 304, c 80, d 24), tutte quelle dichiarate.
**Promosse: 0.** t >= 3: 2 (entrambe con n 85 < 100 per costruzione);
t >= 2: 14; t <= -3: 27; p DATE < 0,01: 6. Varianti sotto 100 operazioni per
costruzione: 290 (tutte le (b) tranne l'oro, tutte le (d)).
Dettaglio: `D:\ricerca_zero\risultati\f5_varianti.parquet`,
`f5_operazioni.parquet`, `f5_descr.parquet`. Lo script gira in ~10 s.

### Migliori 10 per t (nessuna passa)

Netto per operazione in prezzo, in % e in multipli del costo round trip;
anni = anni positivi / anni con >= 5 operazioni.

| variante | n | netto | netto % | / costo | t | anni | p DATE | p DIR |
|---|---|---|---|---|---|---|---|---|
| d Nasdaq cash, OWP (settimana DOPO le scadenze) long | 85* | +26,5 | +0,706 | +17,7 | 3,27 | 7/7 | 0,023 | 0,001 |
| d Nasdaq 22-22, OWP long | 85* | +26,5 | +0,703 | +17,6 | 3,18 | 7/7 | 0,037 | 0,001 |
| c oro 22-22, WF2 ultime 2 ore del venerdi' long | 469 | +0,36 | +0,026 | +0,9 | 2,66 | 8/9 | 0,001 | 0,001 |
| a oro 22-22, venerdi' CC long | 463 | +1,57 | +0,128 | +3,9 | 2,54 | 8/9 | 0,004 | 0,001 |
| b Nasdaq cash, TOM k3 j3 long | 84* | +17,2 | +0,606 | +11,4 | 2,49 | 6/7 | 0,160 | 0,007 |
| a Nasdaq 22-22, martedi' CC long | 367 | +3,26 | +0,119 | +2,2 | 2,32 | 6/8 | 0,030 | 0,001 |
| b S&P cash, TOM k3 j3 long | 84* | +7,13 | +0,481 | +13,0 | 2,20 | 6/7 | 0,148 | 0,010 |
| b Nasdaq cash, TOM k3 j4 long | 84* | +17,5 | +0,609 | +11,6 | 2,19 | 6/7 | 0,230 | 0,011 |
| b Nasdaq cash, TOM k3 j2 long | 84* | +15,0 | +0,479 | +10,0 | 2,13 | 7/7 | 0,201 | 0,012 |
| b S&P cash, TOM k3 j0 long | 84* | +5,15 | +0,345 | +9,4 | 2,06 | 6/7 | 0,084 | 0,016 |

\* sotto 100 operazioni per costruzione (una al mese, 85 mesi): non
promuovibili. Fra le varianti con n >= 100 la migliore resta oro WF2 (t 2,66);
poi oro venerdi' CC (2,54), Nasdaq martedi' (2,32), S&P 22-22 martedi' (2,03,
p DATE 0,073); per l'oro TOM la migliore e' k1 j4 long (n 107, +5,08 $ =
12,7 costi, t 1,91, 5/9 anni, p DATE 0,049).

Peggiori: quasi tutte (c) finestre brevi del fine settimana su metalli e indici
USA (argento WF2 short t -12,5, 0/8 anni; oro WF2 short -9,1), dove il lordo
e' una frazione del costo, e short degli indici USA (deriva rialzista
2011-2017).

### t per giorno della settimana (long; (a))

| | lun | mar | mer | gio | ven | OC lun | OC mar | OC mer | OC gio | OC ven |
|---|---|---|---|---|---|---|---|---|---|---|
| oro 22-22 | -2,0 | -0,2 | -0,9 | -0,5 | **2,5** | | | | | |
| argento 22-22 | -1,5 | -1,1 | -1,9 | -2,4 | 0,7 | | | | | |
| S&P 22-22 | -0,8 | 2,0 | -0,2 | 1,6 | -0,9 | | | | | |
| S&P cash | -0,9 | 1,7 | 0,4 | 0,6 | -0,1 | -0,6 | 1,0 | -1,0 | 0,2 | -0,5 |
| Nasdaq 22-22 | 0,0 | **2,3** | -0,0 | 0,7 | -0,9 | | | | | |
| Nasdaq cash | -0,1 | 1,8 | 0,7 | 0,0 | -0,3 | -0,2 | 0,8 | -1,1 | -0,9 | -1,1 |
| DAX 22-22 | -1,1 | 1,5 | 1,0 | 0,8 | -0,0 | | | | | |
| DAX cash | -0,8 | 0,9 | 1,2 | 0,5 | 0,2 | -0,6 | 0,2 | -0,3 | -0,7 | -0,9 |

Rendimento CC medio lordo per giorno (%): oro lun -0,065 / ven +0,159;
argento ven +0,191 / gio -0,104; S&P mar +0,122 / lun -0,006; Nasdaq mar
+0,163; DAX lun -0,064 / mar +0,109. Il martedi' e' il giorno migliore su
tutti e tre gli indici, il lunedi' il peggiore su DAX e oro.

### Fine settimana ((c), long): t e, fra parentesi, netto in multipli del costo

| | WG | WF2 | WFG | WM2 | WGM2 |
|---|---|---|---|---|---|
| oro 22-22 | -5,4 (-1,5) | 2,7 (+0,9) | 0,9 (+0,4) | 1,7 (+0,9) | 0,7 (+0,5) |
| argento 22-22 | -4,4 (-0,5) | -1,7 (-0,0) | 0,5 (+0,5) | -1,7 (-0,5) | -0,4 (-0,0) |
| S&P 22-22 | -3,4 (-1,7) | -2,2 (-1,1) | -2,8 (-1,8) | -2,7 (-1,0) | -2,8 (-1,7) |
| S&P cash | -1,1 (-1,0) | -2,5 (-1,1) | -1,2 (-1,1) | -1,6 (-1,0) | -1,1 (-1,1) |
| Nasdaq 22-22 | -3,4 (-1,3) | -3,8 (-1,3) | -3,5 (-1,6) | -3,3 (-0,8) | -2,7 (-1,1) |
| Nasdaq cash | -0,9 (-0,6) | -3,7 (-1,4) | -1,4 (-1,0) | -0,8 (-0,5) | -0,3 (-0,1) |
| DAX 22-22 | -1,2 (-2,0) | -0,1 (-0,0) | -0,7 (-1,1) | 0,7 (+1,8) | -0,1 (+0,9) |
| DAX cash | -0,5 (-0,2) | -0,3 (-0,8) | -0,5 (-0,0) | 0,9 (+2,1) | 0,5 (+3,0) |

Lordo medio del buco del fine settimana (WG): oro -0,19 $, argento +0,012 $,
S&P -0,41 / -0,01 (22-22 / cash), Nasdaq -0,45 / +0,66, DAX -1,5 / +1,2:
tutti sotto il costo. Nota sul placebo DATE di WG/WFG/WGM2 sulla giornata
22-22: il "buco" di un giorno feriale qualsiasi dura 5 minuti (21:55 -> 22:00),
quindi li' il placebo misura solo il costo; e' informativo sulle giornate cash
(buco notturno vero) e per WF2/WM2.

### Fine/inizio mese ((b), long, t)

Sugli indici USA il t sale con k (giorni di fine mese inclusi) e non con j;
sui metalli e' piatto, sull'oro sale con j:

| | k0 j1 | k0 j3 | k1 j0 | k1 j3 | k3 j0 | k3 j3 | k3 j4 |
|---|---|---|---|---|---|---|---|
| oro | 1,0 | 1,5 | 0,7 | 1,9 | -0,8 | 0,8 | 1,0 |
| argento | 0,3 | 0,3 | -0,7 | 0,2 | -0,6 | 0,1 | 0,2 |
| S&P 22-22 / cash | 0,4 / -0,2 | 0,6 / 0,7 | -0,5 / 0,0 | 0,4 / 0,8 | 1,3 / 2,1 | 1,6 / 2,2 | 1,6 / 2,0 |
| Nasdaq 22-22 / cash | 0,7 / 0,3 | 0,8 / 1,2 | -0,3 / -0,2 | 0,7 / 1,1 | 1,4 / 2,0 | 1,8 / 2,5 | 1,8 / 2,2 |
| DAX 22-22 / cash | 0,1 / -0,0 | -1,1 / -1,3 | 0,2 / 0,8 | -0,9 / -0,7 | 1,1 / 1,5 | 0,0 / 0,2 | -0,1 / -0,0 |

Ma i p DATE della finestra k3 sugli indici sono 0,08-0,23: e' la deriva
rialzista del periodo (long a caso per 3-7 giorni rende quasi uguale), non un
effetto calendario. Per giorno singolo (t del rendimento CC, descrittiva):
TD-3 e' il solo giorno forte sugli indici (S&P 2,2 / 2,6, Nasdaq 2,3 / 2,7,
DAX 2,1 / 1,6; 22-22 / cash), mentre TD-1 e TD+1..+3 (l'effetto classico)
sono 0-1,5; DAX TD+2 -2,3/-2,5; oro TD-3 -2,5 e TD-5 +2,4. Media di tutti i
giorni: t 2,2-2,8 sugli indici USA (deriva), 1,0 oro, 0,4 argento.

### Settimana delle scadenze opzioni ((d), long; tutte n 85-86 < 100)

Netto in punti, t, anni positivi, p DATE:

| | OW settimana delle scadenze | OWP settimana dopo | OF venerdi' delle scadenze |
|---|---|---|---|
| S&P 22-22 | +4,8, t 1,04, 6/7, 0,52 | +5,7, t 1,59, 7/7, 0,27 | -2,0, t -1,24, 4/7, 0,90 |
| S&P cash | +4,8, t 1,09, 6/7, 0,52 | +6,2, t 1,79, 7/7, 0,24 | -2,0, t -1,15, 4/7, 0,89 |
| Nasdaq 22-22 | +12,4, t 0,64, 6/7, 0,72 | +26,5, t 3,18, 7/7, 0,037 | -5,1, t -1,57, 3/7, 0,95 |
| Nasdaq cash | +12,5, t 0,68, 6/7, 0,70 | +26,5, t 3,27, 7/7, 0,023 | -4,9, t -1,45, 3/7, 0,94 |

La settimana delle scadenze NON e' migliore di una settimana qualsiasi (p DATE
0,5-0,7); il venerdi' delle scadenze e' debole (-0,10/-0,16% contro +0,02 di
un giorno medio); la settimana dopo e' la piu' forte, ma solo sul Nasdaq batte
la deriva (p 0,02-0,04, non < 0,01) e non puo' avere 100 operazioni.

### Descrittive

**Volatilita' per giorno** (range della giornata / atr_pre; norma ~1,0):

| | lun | mar | mer | gio | ven |
|---|---|---|---|---|---|
| oro 22-22 | 0,93 | 1,01 | 1,02 | 1,05 | 1,06 |
| argento 22-22 | 0,96 | 1,00 | 1,00 | 1,05 | 1,07 |
| S&P 22-22 / cash | 0,94 / 0,82 | 1,00 / 0,89 | 1,05 / 0,95 | 1,07 / 0,96 | 1,03 / 0,86 |
| Nasdaq 22-22 / cash | 0,97 / 0,87 | 1,01 / 0,92 | 1,04 / 0,96 | 1,06 / 0,95 | 1,02 / 0,89 |
| DAX 22-22 / cash | 0,96 / 0,89 | 0,98 / 0,92 | 0,98 / 0,90 | 1,06 / 1,00 | 0,96 / 0,92 |

Il lunedi' e' il giorno piu' calmo ovunque (-5/-15% sul range), il giovedi'
il piu' mosso sugli indici, il venerdi' sui metalli: |rendimento CC| medio
oro 0,72% lun contro 0,78% gio-ven, argento 1,18 contro 1,36.

**Mesi dell'anno** (rendimento % del mese, chiusura ultimo giorno ->
chiusura ultimo giorno; fra parentesi anni positivi / anni; 22-22). Solo 7-9
anni per mese: nessuna regola.

| | gen | feb | mar | apr | mag | giu | lug | ago | set | ott | nov | dic |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| oro | 3,1 (5/8) | 2,1 (6/9) | -0,9 (3/9) | 1,2 (6/9) | -1,0 (4/9) | -0,3 (4/9) | 1,1 (6/9) | 3,6 (7/9) | -1,2 (4/9) | 0,6 (4/9) | -0,4 (4/9) | -2,2 (3/9) |
| argento | 5,1 (5/7) | 4,2 (6/8) | 0,8 (4/8) | 2,4 (3/8) | -5,8 (2/8) | -0,4 (3/8) | 1,9 (5/8) | 4,2 (5/8) | -3,9 (3/8) | 2,4 (5/8) | -2,4 (2/8) | -2,3 (3/8) |
| S&P | 0,3 (4/7) | 3,2 (6/7) | 1,5 (4/7) | 1,1 (6/7) | 0,1 (5/7) | -0,1 (3/7) | 1,6 (5/7) | -1,3 (3/7) | -1,0 (3/7) | 3,6 (5/7) | 1,9 (7/7) | 1,2 (6/8) |
| Nasdaq | 1,2 (4/7) | 3,5 (6/7) | 1,4 (4/7) | 0,8 (4/7) | 1,4 (5/7) | -0,9 (2/7) | 3,8 (7/7) | 0,1 (4/7) | -0,3 (3/7) | 3,9 (5/7) | 1,5 (6/7) | 0,4 (4/8) |
| DAX | 1,7 (5/7) | 2,3 (5/7) | 2,1 (5/7) | 0,4 (5/7) | 0,2 (5/7) | -1,8 (2/7) | 1,0 (4/7) | -3,5 (3/7) | 0,7 (3/7) | 4,7 (6/7) | 2,4 (5/7) | 0,6 (4/8) |

Indici: giugno e agosto-settembre deboli, ottobre-febbraio forti; ma 7
osservazioni per cella.

## Candidati

**Nessuno.** Nessuna delle 518 varianti soddisfa tutti i criteri. Le due con
t >= 3 (Nasdaq settimana dopo le scadenze, long) hanno 85 operazioni per
costruzione e p DATE 0,02-0,04 (non battono abbastanza la deriva rialzista).
Fra le regole con n >= 100 il massimo e' t 2,66 (oro, ultime 2 ore del
venerdi' long, netto +0,36 $ = 0,9 costi). Non si congela nulla.

## Osservazioni

1. **Oro il venerdi'**: l'unico effetto giornaliero che batte entrambi i
   placebo (p 0,001-0,004) e regge 8 anni su 9 (venerdi' CC +1,57 $ netti =
   3,9 costi, t 2,54; ultime 2 ore +0,36 $, t 2,66), ma resta sotto t 3. Il
   lunedi' e' il simmetrico negativo (t -2,0) e il buco del fine settimana e'
   negativo al lordo (-0,19 $): il long del venerdi' va chiuso prima del fine
   settimana. Da tenere come filtro di direzione/tempo, non da solo.
2. **Gli effetti di calendario degli indici USA sono quasi tutti deriva**:
   fine mese (TOM k3), settimana delle scadenze e martedi' hanno t 2-2,5 ma il
   placebo su date casuali li spiega (p DATE 0,03-0,23). Restano solo il
   giorno TD-3 (t 2,2-2,7, descrittiva) e la settimana DOPO le scadenze sul
   Nasdaq; il venerdi' delle scadenze e' negativo. Le regole mensili non
   possono raggiungere 100 operazioni in 7 anni: anche un effetto vero non
   passerebbe la soglia.
3. **Il calendario serve piu' per la volatilita' che per la direzione**: il
   lunedi' ha il 5-15% di range in meno su tutti i mercati, il giovedi'
   (indici) e il venerdi' (metalli) il piu' alto. Le finestre brevi del fine
   settimana (2 ore, buco) hanno lordi di una frazione del costo: le 27
   varianti con t <= -3 sono quasi tutte queste (argento WF2 short -12,5) o
   short degli indici USA.
