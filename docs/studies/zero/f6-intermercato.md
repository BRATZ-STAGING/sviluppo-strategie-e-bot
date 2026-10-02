# Famiglia 6 — Fra mercati (scoperta 2010-2017)

Protocollo: `docs/ricerca-da-zero-registrazione.md`. Script:
`trading/scripts/zero_f6_intermercato.py`. Dati: solo `D:\ricerca_zero\scoperta\`
(M5 e H1; al massimo due mercati in memoria alla volta).

## Varianti dichiarate PRIMA del calcolo (02/10/2026)

**Regole fisse (non dimensioni di ricerca).** Coppie allineate solo sugli
istanti presenti in ENTRAMBE le serie (intersezione degli indici, nessun
riempimento in avanti). Rendimenti in log; netto in punti base (bp) del prezzo
d'entrata e in multipli del costo round trip. Costi round trip: oro 0,40,
argento 0,025, S&P 0,55, Nasdaq 1,50, DAX 1,50; una coppia paga ENTRAMBI i
costi (gambe di pari nozionale: costo = c1/P1 + c2/P2). Entrata all'apertura
della barra successiva al segnale; nessuno stop (uscite a tempo o al rientro
dello z); al massimo una posizione per variante (non sovrapposte). Rolling
sempre causali (fino alla barra del segnale inclusa, mai oltre). Barre
"liquide" per i rendimenti di b1 e delle correlazioni incrociate: `minuti >= 4`
(M5) o >= 80% della barra (M15, H1) in entrambe le serie, e barra precedente
comune esattamente un TF prima.

**(a) Oro/argento, spread s = ln(oro) - ln(argento) — 78 varianti**
- H1 (54): z = (s - media_W)/dev_W sulle ultime W barre H1 comuni,
  W in {24, 120, 480}; soglia |z| >= {1,5; 2,0; 2,5}; uscita Z0 (z torna a
  0, max W barre) o F (tempo fisso W/4 barre: 6, 30, 120 h); gamba PAIR
  (vende la ricca, compra la povera), SOLO ORO (z alto -> short oro), SOLO
  ARGENTO (z alto -> long argento). 3 x 3 x 2 x 3 = 54. Promozione n >= 200.
- Giornaliera (24): s alla chiusura della H1 delle 19:00 UTC, entrata
  all'apertura della H1 delle 20:00; W in {20, 60} giorni; soglia {1,5; 2,0};
  uscita Z0 (controllo giornaliero, max 20 giorni) o F5 (5 giorni); 3 gambe.
  2 x 2 x 2 x 3 = 24. Promozione n >= 100.

**(b) S&P / Nasdaq — 132 varianti**
- b1 anticipo/ritardo (96): barra del leader con rendimento |r| >= q x
  dev. std (ultime 2000 barre comuni, causale). TF in {M5, M15, H1};
  q in {1, 2}; verso {S&P -> Nasdaq, Nasdaq -> S&P}; segnale LEAD (mossa
  del leader, si compra/vende il seguace nella stessa direzione) o GAP
  (g = r_lead/dev_lead - r_seg/dev_seg, |g| >= q con segno di r_lead: il
  seguace e' rimasto indietro, si opera il seguace nel segno di g); tenuta
  1 o 3 barre del TF; sessione TUTTE o CASH (barra di segnale dentro 9:30-16:00
  New York). 3 x 2 x 2 x 2 x 2 x 2 = 96. Entrata all'apertura della M5 del
  seguace che inizia alla chiusura della barra di segnale. Promozione n >= 200.
- b2 divergenza nella sessione cash (36): D = r_Nasdaq - r_S&P dalla
  apertura delle 9:30 New York; z = D / dev. std di D a fine sessione negli
  ultimi 60 giorni (min 40). Controllo alle 10:30, 11:30 o 13:30 NY (3);
  soglia |z| >= {1,0; 1,5}; gamba PAIR (short la piu' forte, long la piu'
  debole), SOLO S&P (S&P nel segno di D: recupera), SOLO NASDAQ (Nasdaq
  contro D: rientra); uscita EOD (chiusura 16:00 NY) o Z0 (D torna a 0,
  altrimenti EOD). 3 x 2 x 3 x 2 = 36. Promozione n >= 100 (una al giorno).

**(c) Mossa forte di un mercato -> sessione successiva di un altro — 72 varianti**
Segnale: rendimento della finestra |r| >= k x dev. std della stessa finestra
negli ultimi 60 giorni validi (min 40), k in {1,0; 1,5}; direzione CONT
(stesso segno) o REV. 9 coppie x 2 finestre bersaglio x 2 k x 2 dir = 72.
| # | segnale | bersaglio (2 finestre) |
|---|---|---|
| c1 | S&P cash 9:30-16:00 NY | DAX giorno dopo: 9:00-10:00 / 9:00-17:30 Berlino |
| c2 | Nasdaq cash | DAX come c1 |
| c3 | S&P ultime 2 ore 14:00-16:00 NY | DAX come c1 |
| c4 | S&P cash | oro dalla chiusura USA alle 07:00 / alle 12:00 UTC del giorno feriale dopo |
| c5 | S&P cash | argento come c4 |
| c6 | oro Asia 22:00-07:00 UTC | oro Londra 07-08 / 07-12 UTC |
| c7 | oro Asia | argento 07-08 / 07-12 UTC |
| c8 | oro Asia | DAX 07-08 / 07-12 UTC |
| c9 | argento Asia | oro 07-08 / 07-12 UTC |
Promozione n >= 100 (regole giornaliere).

**Totale dichiarato: 282 varianti** (a 78, b 132, c 72).

**Placebo e controlli.** Per ogni variante: stessi istanti e uscite, direzione
casuale, 1000 serie, seed 12345; p = (1 + #placebo con media >= reale)/1001.
t = media / dev. std x radice(n) sulle operazioni non sovrapposte. Anni con
almeno 5 operazioni. Per le regole intraday fra fonti/mercati (a H1, b1, b2):
controllo a RITARDO ARTIFICIALE, stessa regola con entrata una barra dopo
(a H1: una H1; b1 e b2: una M5, 5 minuti), uscita invariata: se il vantaggio sparisce con una barra di ritardo e' un effetto di
sincronizzazione (fonti diverse, prezzi non sincroni) e la variante non si
promuove. Descrittive (non sono prove): emivita AR(1) dello spread oro/argento,
correlazione z -> variazione futura dello spread, correlazione incrociata M5
ai ritardi -3..+3 (S&P-Nasdaq, oro-argento, S&P-DAX, S&P-oro) anche con una
serie spostata artificialmente di 1 barra, correlazione segnale -> bersaglio
delle coppie (c).

## Risultati (calcolati sui file di scoperta del 02/10, 23:16)

Varianti calcolate: **282** (a 78, b1 96, b2 36, c 72), tutte quelle
dichiarate. **Promosse: 0.** t >= 3: 0; t >= 2: 2; t <= -3: 96 (b1 65, a 13,
b2 10, c 8); netto > 0: 36. Dettaglio in `D:\ricerca_zero\risultati\`:
`f6_varianti.parquet`, `f6_operazioni.parquet`, `f6_descr.parquet`.
Costo round trip in bp del prezzo: oro ~3,0, argento ~12, S&P ~3,2,
Nasdaq ~4,4, DAX ~1,7; coppia oro+argento ~15, S&P+Nasdaq ~7,6.

### Migliori per t (nessuna passa)

| variante | n | lordo bp | netto bp | netto / costo | t | anni | p placebo | netto con 1 barra di ritardo |
|---|---|---|---|---|---|---|---|---|
| a D1 W20 k1,5 Z0 SOLO ORO | 109 | +76,8 | +73,7 | +24,4 | 2,35 | 6/8 | 0,007 | +75,2 (t 2,38) |
| a H1 W480 k2,5 F SOLO ORO | 108 | +47,7 | +44,7 | +15,0 | 2,12 | 7/8 | 0,012 | +42,9 |
| a D1 W20 k1,5 F5 SOLO ORO | 194 | +33,8 | +30,8 | +10,3 | 1,86 | 7/8 | 0,020 | +32,4 |
| a D1 W20 k2,0 Z0 SOLO ORO | 75 | +76,0 | +73,0 | +24,2 | 1,77 | 5/8 | 0,037 | +74,0 |
| a D1 W20 k2,0 F5 SOLO ORO | 98 | +36,7 | +33,8 | +11,3 | 1,47 | 7/8 | 0,048 | +33,9 |
| c8 oro Asia -> DAX 07-12 UTC k1,5 CONT | 219 | +11,1 | +9,4 | +5,4 | 1,41 | 6/8 | 0,039 | - |

t mediano per parte: a -1,44 (max 2,34), b1 -5,77 (max 1,01), b2 -1,40
(max 0,21), c -1,08 (max 1,41).

### (a) Oro/argento: lo spread NON rientra su giorni e settimane

- AR(1) del log-rapporto giornaliero: phi 0,998, emivita ~384 giorni
  (per anno da 8 giorni nel 2015 a infinito nel 2010): quasi passeggiata
  casuale.
- z dello spread H1 -> variazione futura dello spread (corr; anni con segno
  negativo = rientro): W24 a 1 h -0,028 (7/8 anni), a 6 h -0,013 (6/8);
  W480 a 24 h +0,028, a 120 h +0,050 (4/8 e 3/8 negativi). Rientro solo di
  breve (ore); a 1-5 giorni lieve momentum, non costante fra gli anni.
- Il rientro di breve esiste al lordo ma non paga i costi: PAIR W24 k1,5 F
  (6 h) lordo +4,0 bp (t lordo 3,5, p 0,001) contro 15 bp di costo, netto
  -11,2 bp, t -9,8, 0/8 anni. Per la gamba singola il lordo si divide:
  solo oro +0,6 bp (costo 3), solo argento +3,4 bp (costo 12).
- **"Solo la gamba economica"**: l'oro costa 4 volte meno dell'argento in bp,
  e tutte le migliori varianti sono SOLO ORO; ma PAIR e SOLO ARGENTO sono
  negative quasi ovunque (t mediano D1/H1: PAIR -0,7/-2,8, argento -1,3/-2,3; massimi 0,2 e 0,3). La
  scomposizione (diagnostica a posteriori) mostra che SOLO ORO non sfrutta
  un rientro: z alto del rapporto coincide con l'oro in calo nei 20 giorni
  prima (corr -0,325), quindi "short oro se il rapporto e' alto" e' un
  **trend following sull'oro** con l'argento come amplificatore. Nel
  migliore (D1 W20 k1,5 Z0) l'oro guadagna in entrambe le direzioni (+67,5 bp
  short, n 56; +86,6 long, n 53) mentre l'argento perde (-88,5 e -164,5):
  lo spread continua, non rientra. Tenuta mediana 18-21 giorni (lo z quasi
  mai torna a 0 entro 20). Anni: 2016 e 2017 negativi. Coerente con la
  famiglia trend dell'oro gia' respinta (appendice CD) e con t 2,35 < 3.

### (b) S&P / Nasdaq: nessun anticipo sfruttabile

- Correlazione incrociata M5 (barre liquide, 253 mila): contemporanea 0,913;
  ritardi +-1: -0,010 / -0,007, +-2: -0,011 / -0,007. Nessun mercato
  anticipa l'altro di 5 minuti; il lieve segno negativo e' rimbalzo. Il
  controllo con una serie spostata artificialmente di una barra sposta
  esattamente il picco a +1 (0,914): il metodo vede un ritardo vero se c'e'.
- b1: lordo mediano -0,06 bp (M5), -0,05 (M15), +0,59 (H1) contro un costo
  di 3,7 bp. 65 varianti su 96 con t <= -3; la migliore (H1 N>S GAP q2
  CASH h1) ha 12 operazioni. Con entrata ritardata di una M5 la tenuta di 1
  M5 diventa nulla (entrata = uscita): controllo non informativo li', ma non
  c'e' nulla da salvare.
- b2 divergenza nella sessione cash: rientra un poco al lordo per la gamba
  S&P (lordo mediano +0,8 bp) e non per il Nasdaq (-1,7); PAIR -0,2 bp
  lordo contro 7,6 di costo (t mediano -5,6). Migliore: 10:30 k1,5 SOLO S&P
  Z0, n 74, +2,0 bp, t 0,21.

### (c) Mossa forte -> sessione successiva di un altro mercato

Correlazione fra z del segnale e rendimento del bersaglio (tutti i giorni; fra
parentesi solo |z| >= 1):

| coppia | finestra 1 | finestra 2 |
|---|---|---|
| c1 S&P cash -> DAX 9-10 / 9-17:30 Berlino | -0,007 (-0,015) | -0,008 (-0,019) |
| c2 Nasdaq cash -> DAX | +0,006 (+0,010) | -0,002 (-0,002) |
| c3 S&P 14-16 NY -> DAX | -0,039 (-0,085) | -0,023 (-0,056) |
| c4 S&P cash -> oro chiusura USA-07 / -12 UTC | -0,021 (-0,020) | -0,003 (-0,005) |
| c5 S&P cash -> argento | -0,014 (-0,006) | +0,041 (+0,069) |
| c6 oro Asia -> oro 07-08 / 07-12 UTC | -0,064 (-0,096) | -0,030 (-0,044) |
| c7 oro Asia -> argento | -0,061 (-0,094) | -0,011 (+0,005) |
| c8 oro Asia -> DAX | +0,038 (+0,098) | +0,014 (+0,075) |
| c9 argento Asia -> oro | -0,062 (-0,094) | -0,016 (+0,006) |

La chiusura USA non dice nulla sulla sessione DAX (il gap d'apertura la
incorpora gia'); le ultime 2 ore USA forti rientra leggermente nella
prima ora DAX (-0,04/-0,085) ma il migliore c3 REV fa +1,6 bp netti, t 0,56.
La notte asiatica dei metalli rientra nella prima ora di Londra (-0,06/-0,10,
su oro e argento e in croce), ma il rientro vale pochi bp contro 3 (oro) o 12
(argento) di costo: c6/c7/c9 REV tutte con t < 0,6 o negative.

### Controllo di sincronizzazione fra fonti (Dukascopy contro HistData)

Correlazione incrociata M5 oro (Dukascopy) - argento (HistData): contemporanea
0,732, ritardo -1 +0,007, +1 -0,001 (14-20 UTC: 0,755; +0,008 / -0,005).
L'asimmetria e' circa 1% della correlazione contemporanea: un eventuale
sfasamento fra le due fonti e' dell'ordine di pochi secondi e non crea
anticipi sfruttabili. S&P-DAX (stessa fonte): 0,771, +-1 -0,004 / -0,007;
S&P-oro: 0,013 (14-20 UTC 0,037), nessun ritardo. Le varianti H1 di (a)
restano uguali con un'ora di ritardo all'entrata (+75,2 contro +73,7 bp
nella migliore): nessun effetto di sincronizzazione.

## Candidati

**Nessuno.** Nessuna delle 282 varianti ha t >= 3 (massimo 2,35, n 109).
La migliore (solo oro sul segnale del rapporto oro/argento) e' un trend
dell'oro travestito, non un rientro dello spread. Non si congela nulla.

## Osservazioni

1. Il rapporto oro/argento NON e' a ritorno alla media su giorni e settimane
   (emivita ~1 anno, lieve momentum a 1-5 giorni): rientra solo nelle prime ore
   (+4 bp lordi a 6 h, t lordo 3,5), troppo poco contro i 15 bp di una
   coppia o i 12 dell'argento da solo. L'argento costa 4 volte l'oro in bp.
2. S&P e Nasdaq si muovono insieme al 91% a 5 minuti e nessuno dei due
   anticipa l'altro, nemmeno su M15/H1: il lordo delle regole d'anticipo e'
   zero e il costo (3-4 bp) le rende tutte negative (65 su 96 con t <= -3).
3. Fra sessioni l'unico segno ricorrente e' il RIENTRO della notte asiatica
   dei metalli nella prima ora di Londra (corr -0,06/-0,10, coerente fra
   oro e argento e in croce) e un lieve rientro della fine USA nella prima ora
   DAX: entrambi sono effetti da pochi bp, sotto i costi.
