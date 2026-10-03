# Famiglia 4 multi-giorno — Breakout con stop larghi (scoperta 2010-2017)

Protocollo: `docs/multigiorno-paniere-registrazione.md`. Script:
`trading/scripts/multi_f4_breakout.py`. Dati: solo
`D:\ricerca_multi\scoperta\PANIERE_D1.parquet` (giornata 22->22 UTC) e
`D:\ricerca_multi\costi.csv`; le M5 di `D:\ricerca_zero\scoperta\` e
`D:\ricerca_fx\scoperta\` servono SOLO a risolvere la giornata di entrata
degli ordini stop. 12 mercati: XAUUSD, XAGUSD, SPXUSD, NSXUSD, GRXEUR,
EURUSD, USDJPY, GBPUSD, AUDUSD, USDCHF, USDCAD, EURJPY.

## Varianti dichiarate PRIMA del calcolo (04/10/2026)

Regole fisse (non sono dimensioni di ricerca):
- giornate valide = `valida` del file (>= 150 M5); livelli, ATR e segnali
  solo dalle giornate valide; la gestione delle posizioni aperte usa tutte le
  giornate (anche le non valide: stop controllati, prudente);
- TR = max(H, C prec.) - min(L, C prec.) sulle valide; ATR20 e ATR100 medie
  semplici; operazioni con entrata dal 01/01/2010 (l'oro 2009 serve solo da
  riscaldamento), uscite entro il 29/12/2017 (posizione ancora aperta: chiusa
  all'ultima chiusura; nessuna entrata nell'ultima giornata dei dati);
- una sola posizione per mercato e per regola; un nuovo ingresso solo dalla
  giornata DOPO l'uscita;
- ordine/segnale ammesso solo se la chiusura valida precedente e' ancora
  dentro i livelli (per la settimana precedente evita di "rompere" un livello
  gia' superato; per N giorni e' sempre vero);
- R = m x ATR20 (distanza entrata-stop), rischio uguale per operazione e per
  mercato; risultati in R;
- giorno di entrata degli ordini stop risolto sulle M5: livello toccato per
  primo (stessa M5 per entrambi = evento scartato, 2 casi su ~34 mila);
  entrata al livello o all'apertura della M5 se la supera; stop toccato dopo
  l'entrata nella stessa giornata = uscita allo stop (la M5 di entrata conta
  per intero: prudente); dal giorno dopo gestione su D1 (stop unico per lato,
  nessun obiettivo: nessuna ambiguita'); apertura oltre lo stop = uscita
  all'apertura;
- costi round trip di `costi.csv` in prezzo / R (oro 0,46 $ nel 2010-2017);
  swap per ogni giorno feriale in [entrata, uscita), mercoledi' x3, al prezzo
  di chiusura del giorno: 3%/360 del nominale long e short (cambi, argento,
  indici), oro -0,715 / +0,325 $ per oncia a 4.156,98 $ riscalati; ogni regola
  anche con costi x1,5 (swap invariato).

Griglia: 
- livello (4): massimo/minimo dei N = 5, 10, 20 giorni validi precedenti, o
  della settimana precedente (lun-ven) W;
- entrata (2): R = ordine stop al livello (ATR e filtro alla chiusura prima);
  C = chiusura oltre il livello, entrata alla chiusura (ATR e filtro alla
  stessa chiusura);
- stop iniziale (3): m = 1, 2, 3 x ATR20;
- uscita (6): T2 / T3 = trailing k x ATR20 corrente dal massimo (minimo)
  raggiunto dopo l'entrata, aggiornato a fine giornata, mai allargato;
  D5 / D10 / D20 = chiusura della 5a/10a/20a giornata dopo l'entrata;
  OPP = ordine stop alla rottura opposta di N/2 giornate (5->3, 10->5,
  20->10, W->3), dal giorno dopo; lo stop iniziale resta sempre attivo;
- filtro (2): F0 nessuno, F1 solo se ATR20/ATR100 < 1.
- **4 x 2 x 3 x 6 x 2 = 288 regole**, ciascuna valutata su 4 ambiti
  promuovibili (paniere, indici, metalli, cambi) = **1152 varianti**; in piu'
  (solo diagnostica) i 12 mercati singoli e il paniere senza oro.

Misure per regola e ambito: n, operazioni al mese, netto medio in R e totale,
t sui 96 rendimenti mensili (somma in R per mese di USCITA, mesi senza
operazioni = 0), anni positivi su 8 (anno di uscita), netto con costi x1,5,
swap medio in R, drawdown in R (operazioni in ordine di uscita), placebo:
stessi istanti e prezzi di entrata, stessa gestione applicata alla direzione
estratta a caso (stop speculare alla stessa distanza, trailing/canale nella
nuova direzione, swap ricalcolato), 1000 serie, seed 20261004,
p = (1 + #placebo >= reale) / 1001 sul netto totale.
Promozione: netto > 0 a x1 e x1,5, t >= 3, anni >= 6/8, p < 0,01; al massimo
3 candidati.

## Risultati (04/10/2026)

Controlli: 33.751 giornate di ordine stop risolte sulle M5, nessuna
incoerenza fra D1 e M5 (livello toccato sulla D1 ma non sulle M5: 0); entrata
= max(livello, apertura) e ATR/filtro/livello ricalcolati da zero coincidono
sulle operazioni della candidata (XAGUSD e SPXUSD); uscite a tempo
ricalcolate con un ciclo indipendente su 1407 operazioni: identiche.
Operazioni simulate: 30-38 mila per mercato (tutte le regole).

**Varianti provate: 1152 (288 regole x 4 ambiti)**.

| ambito | netto > 0 | t >= 3 | t <= -3 | anni >= 6 | p < 0,01 | passano tutto | t mediano | t max |
|---|---|---|---|---|---|---|---|---|
| paniere | 0 | 0 | 1 | 0 | 0 | 0 | -1,49 | -0,10 |
| indici | 1 | 0 | 81 | 0 | 0 | 0 | -2,55 | 0,25 |
| metalli | 284 | 1 | 0 | 185 | 77 | **1** | 1,50 | 3,42 |
| cambi | 0 | 0 | 3 | 0 | 0 | 0 | -1,55 | -0,20 |

Mediane sulle 288 regole (R per operazione):

| ambito | lordo | costo | swap | netto | op/mese | DD (R) |
|---|---|---|---|---|---|---|
| paniere | +0,009 | 0,010 | -0,065 | -0,059 | 13,7 | 94,6 |
| senza oro | -0,003 | 0,010 | -0,069 | -0,078 | — | — |
| indici | -0,109 | 0,013 | -0,050 | -0,171 | 3,0 | 58,4 |
| metalli | +0,183 | 0,020 | -0,031 | +0,130 | 2,4 | 10,8 |
| cambi | +0,005 | 0,006 | -0,081 | -0,077 | 8,2 | 67,5 |

Per mercato (mediana del netto, quota di regole con netto > 0): XAGUSD
+0,162 (100%), XAUUSD +0,094 (87%); tutti gli altri negativi: SPXUSD -0,228
(0%), NSXUSD -0,192 (0%), GRXEUR -0,087 (12%), cambi da -0,022 (EURJPY, 28%)
a -0,120 (GBPUSD, 3%). Lordo mediano positivo solo su EURUSD e EURJPY
(+0,042), USDJPY (+0,024) e metalli.

Lordo mediano per dimensione (metalli / indici): uscita T3 +0,273 / -0,151,
OPP +0,211 / -0,122, D5 +0,111 / -0,078; entrata R +0,193 / -0,107,
C +0,166 / -0,112; filtro F1 +0,234 / -0,167, F0 +0,149 / -0,079. Il filtro
di compressione AMPLIFICA il segno di ciascun gruppo (meglio sui metalli,
peggio sugli indici).

### Migliori per t (paniere e gruppi)

| regola | ambito | n | op/mese | lordo R | netto R | netto tot | t | anni + | netto x1,5 tot | swap R | DD R | p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **N20 R S3 D5 F1** | metalli | 256 | 2,67 | 0,177 | 0,153 | 39,1 | **3,42** | 7 | 37,2 | -0,010 | 3,3 | 0,001 |
| W R S2 T2 F1 | metalli | 214 | 2,23 | 0,321 | 0,273 | 58,5 | 2,98 | 7 | 56,2 | -0,027 | 7,4 | 0,002 |
| W R S3 T2 F1 | metalli | 214 | 2,23 | 0,212 | 0,181 | 38,6 | 2,94 | 7 | 37,1 | -0,018 | 4,9 | 0,001 |
| N10 R S2 D10 F1 | metalli | 248 | 2,58 | 0,273 | 0,227 | 56,3 | 2,75 | 7 | 53,6 | -0,025 | 5,6 | 0,004 |
| N20 R S2 D5 F1 | metalli | 258 | 2,69 | 0,226 | 0,190 | 48,9 | 2,74 | 7 | 46,1 | -0,015 | 6,5 | 0,001 |
| N20 R S3 D5 F0 | metalli | 348 | 3,63 | 0,120 | 0,096 | 33,5 | 2,68 | 7 | 31,2 | -0,010 | 5,3 | 0,001 |
| N20 R S1 T2 F1 | paniere | 1029 | 10,7 | 0,102 | -0,009 | -8,9 | -0,10 | 4 | -20,0 | -0,089 | 76,2 | 0,143 |
| N5 R S2 OPP F1 | cambi | 1224 | 12,8 | 0,043 | -0,006 | -7,0 | -0,20 | 4 | -11,0 | -0,042 | 32,7 | 0,099 |
| W R S3 D20 F0 | indici | 257 | 2,68 | 0,081 | 0,017 | 4,5 | 0,25 | 5 | 3,4 | -0,056 | 12,1 | 0,093 |

Sui metalli: 279 regole su 288 positive anche a x1,5, 53 con t >= 2, una
sola con t >= 3. Nell'intorno della candidata (N20 R, D5/D10, m 1-3, F0/F1)
il t va da 1,50 a 3,42: la candidata e' il picco di un campo tutto positivo.

### Candidata: N20 R S3 D5 F1 sui metalli, dettaglio

| ambito | n | netto R | netto tot | t | anni + | x1,5 tot | p |
|---|---|---|---|---|---|---|---|
| metalli | 256 | 0,153 | 39,1 | 3,42 | 7 | 37,2 | 0,001 |
| solo XAUUSD | 129 | 0,146 | 18,8 | 2,97 | 8 | 18,2 | 0,002 |
| solo XAGUSD (= senza oro) | 127 | 0,159 | 20,2 | 2,89 | 7 | 19,0 | 0,001 |
| paniere intero (diagnostica) | 1349 | -0,017 | -23,6 | -0,84 | 4 | -28,6 | 0,204 |

Per anno (R netti, metalli): 2010 +4,9, 2011 +5,7, 2012 +5,0, 2013 +9,8,
2014 +2,4, 2015 -1,6, 2016 +6,3, 2017 +6,6. Long e short: argento +0,173 /
+0,147 R, oro +0,081 / +0,225 R per operazione (lo short dell'oro incassa lo
swap positivo). Vinte 61,7%; stop toccato prima dei 5 giorni nell'1,2% dei
casi: in pratica e' "dopo la rottura del massimo/minimo di 20 giorni in
compressione, tieni 5 giorni". Costo 0,014 R, swap -0,010 R per operazione
(il 6% del lordo).

### Osservazioni

1. **Il breakout multi-giorno funziona solo sui metalli.** Oro e argento sono
   positivi in quasi tutta la griglia (284/288 regole, lordo mediano
   +0,18 R), gli indici sono negativi ovunque (lordo -0,11 R, 81 regole con
   t <= -3: dopo una rottura gli indici rientrano, coerente con la previsione
   2 del protocollo), i cambi sono a lordo circa zero. Il paniere a rischio
   uguale e' quindi negativo in tutte le 288 regole (t massimo -0,10): i 10
   mercati non metallici annullano i 2 metallici.
2. **Sui cambi decide lo swap, non il segnale.** Il 3% annuo long e short
   costa 0,08 R per operazione (mediana), 13 volte il costo di transazione;
   EURUSD, EURJPY e USDJPY hanno lordo leggermente positivo (+0,02/+0,04 R)
   ma netto negativo. Con stop larghi e tenute di 5-20 giorni lo swap prudente
   del protocollo e' l'ostacolo principale fuori dai metalli (sui metalli pesa
   -0,03 R).
3. **Il filtro di compressione (ATR20/ATR100 < 1) amplifica il segno del
   gruppo** invece di creare un vantaggio: alza il lordo dei metalli (+0,234
   contro +0,149) e peggiora gli indici (-0,167 contro -0,079). La candidata
   e' il picco (t 3,42) di un campo positivo in cui la regola mediana ha t 1,5:
   una sola su 1152 varianti supera tutti i criteri, il che e' vicino a
   quanto ci si aspetta dal caso dato il campo positivo; il placebo (p 0,001)
   dice che conta la direzione, non solo l'esposizione.

Non provate (sarebbero varianti a posteriori, da registrare a parte): il
breakout sui soli metalli con altre tenute; il breakout "al contrario" sugli
indici (e' la famiglia 2); un paniere di soli metalli+cambi senza swap.

### Candidati

**Uno: N20 R S3 D5 F1 sul gruppo metalli** (XAUUSD + XAGUSD, rischio uguale).
Specifica esatta ed eseguibile:
- mercati XAUUSD e XAGUSD, giornate 22:00 -> 22:00 UTC (valide se >= 150 M5);
- ogni giornata valida s, se il mercato e' flat: H = massimo dei 20 massimi
  delle giornate valide precedenti, L = minimo dei 20 minimi; ATR20 e ATR100 =
  medie semplici del TR delle giornate valide fino alla chiusura di s-1;
  condizioni: ATR20/ATR100 < 1 e chiusura valida di s-1 strettamente fra L e H;
- ordine buy stop a H e sell stop a L per la giornata s: il primo toccato
  entra (al livello, o all'apertura se la supera), l'altro si annulla;
- stop iniziale = entrata -/+ 3 x ATR20 (quello di s-1), attivo subito; nessun
  trailing; apertura oltre lo stop = uscita all'apertura;
- uscita alla chiusura della 5a giornata dopo quella di entrata (contando
  tutte le giornate del mercato), se lo stop non e' stato preso prima;
- dimensione: 1R = 3 x ATR20 per operazione, uguale per i due mercati; nuova
  entrata solo dalla giornata dopo l'uscita.

Per la verifica (2018 -> fine dati, una volta, k = 1: t >= 2) va riportata
anche senza l'oro (solo XAGUSD), perche' per l'oro le regole di trend non
sono pulite (appendice CD).

Dettaglio in `D:\ricerca_multi\risultati\`: `f4_operazioni_<MERCATO>.parquet`
(una riga per operazione e regola, con l'esito della direzione opposta per il
placebo) e `f4_varianti.parquet` (una riga per regola e ambito, compresi i
mercati singoli e il paniere senza oro).
