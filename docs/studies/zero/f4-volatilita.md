# Famiglia 4 — Volatilita' (scoperta 2009/2010-2017)

Protocollo: `docs/ricerca-da-zero-registrazione.md`. Script:
`trading/scripts/zero_f4_volatilita.py`. Dati: solo `D:\ricerca_zero\scoperta\`
(M5; le giornate si costruiscono dalle M5, le D1 a mezzanotte UTC non si usano).

## Varianti dichiarate PRIMA del calcolo (02/10/2026)

**Giornate.** Giornata "22-22": M5 con apertura in [D-1 22:00, D 22:00) UTC,
etichettata D (la sera della domenica va nel lunedi'; per il DAX coincide con
il giorno UTC perche' non ci sono dati fra le 21 e le 7). Per gli indici anche
la giornata "cash": S&P e Nasdaq 9:30-16:00 New York, DAX 9:00-17:30 Berlino,
ora legale vera (zoneinfo). Giornata valida se ha almeno il 50% delle M5 della
mediana del mercato-giornata; le non valide si saltano (il "giorno prima" e' il
valido precedente; le loro M5 servono solo a gestire posizioni aperte).
TR = max(H, C prec.) - min(L, C prec.). `atr_pre[k]` = media TR dei 14 giorni
validi PRIMA di k (k escluso): causale.

**Regole fisse (non dimensioni di ricerca).** Gestione su M5; entrata
all'apertura della M5 dopo il segnale; se nella stessa M5 si toccano stop e
obiettivo vale lo stop; apertura oltre lo stop = uscita all'apertura (idem
obiettivo); al massimo una posizione aperta per variante (operazioni non
sovrapposte: un segnale con posizione aperta si salta); operazione scartata
se rischio < 2 x costo round trip; segnali di rottura solo se restano almeno
12 M5 della giornata dopo la candela di segnale. Costi round trip: oro 0,40,
argento 0,025, S&P 0,55, Nasdaq 1,50, DAX 1,50. R = distanza entrata-stop.

**(a) Compressione -> espansione — 448 varianti**
- 8 mercati-giornata: oro 22-22, argento 22-22, S&P 22-22, S&P cash,
  Nasdaq 22-22, Nasdaq cash, DAX 22-22, DAX cash
- 7 filtri sul giorno k (il giorno di setup): TUTTI (nessun filtro, controllo),
  NR4 (range < minimo dei 3 precedenti), NR7 (< minimo dei 6 precedenti),
  ID inside day (H <= H prec. e L >= L prec.), ID+NR4, R50 (range < 0,5 x
  atr_pre), R75 (range < 0,75 x atr_pre)
- regola: nel giorno k+1, prima chiusura M5 sopra H[k] -> long, sotto L[k]
  -> short (la prima delle due)
- 2 stop: S1 altro lato del range di k, S2 meta' del range di k
- 4 uscite: X1 chiusura dell'ultima M5 del giorno k+1; X1T2 obiettivo 2R
  altrimenti X1; X3 fine del 3o giorno (k+3); X5 fine del 5o giorno (k+5)
- 8 x 7 x 2 x 4 = **448**

**(b) Dopo le giornate estreme — 160 varianti** (giornata 22-22)
- 5 mercati
- 4 definizioni di giornata estrema k: RNG15 range > 1,5 x atr_pre,
  RNG20 range > 2,0 x atr_pre (direzione = segno di C-O del giorno),
  RET10 |C - C prec.| > 1,0 x atr_pre, RET15 > 1,5 x atr_pre (direzione =
  segno del rendimento)
- 2 direzioni: CONT (segue) e REV (contro), entrata all'apertura della prima
  M5 del giorno k+1
- 2 stop: 0,5 e 1,0 x atr_pre[k]
- 2 uscite: fine giorno k+1, fine giorno k+3
- 5 x 4 x 2 x 2 x 2 = **160**
- piu' una tabella descrittiva (non e' una prova): probabilita' che k+1
  continui, rendimento k+1 in ATR, range k+1 / atr rispetto alla norma.

**(c) Regimi di volatilita' per scegliere QUANDO operare — 128 varianti**
- 8 mercati-giornata come in (a)
- 4 regole base: rottura del giorno prima senza filtro (TUTTI) x {S1, S2} x
  {X1, X3}
- 4 regimi decisi alla fine del giorno k: VB/VA = ATR14 (fino a k) nel terzile
  basso/alto dei 250 valori precedenti (minimo 100); CMP/ESP = ATR5/ATR60
  (fino a k) < 0,8 / > 1,2
- 8 x 4 x 4 = **128**

**Totale dichiarato: 736 varianti** (nessuna scartata prima del calcolo).
Placebo per ogni variante: stessi istanti, stessa gestione (stop e obiettivo
speculari alla stessa distanza, stessa uscita a tempo), direzione casuale,
1000 serie, seed 12345; p = (1 + #placebo con media >= reale) / 1001.
t = media / dev. std x radice(n) sulle operazioni non sovrapposte.
Anni: si contano gli anni con almeno 5 operazioni.
Promozione: netto > 0, t >= 3, anni positivi >= 75%, p < 0,01, n >= 100
(regole giornaliere). Massimo 3 candidati.

## Risultati (calcolati sui file di scoperta rigenerati alle 23:16 del 02/10, orari HistData corretti)

Varianti calcolate: **736** (a 448, b 160, c 128), tutte quelle dichiarate.
**Promosse: 0.** Varianti con t >= 3: 0; con t <= -3: 67 (quasi tutte rotture
del giorno prima sugli indici USA). t >= 2: 9; p placebo < 0,01: 10.
Dettaglio: `D:\ricerca_zero\risultati\f4_varianti.parquet`,
`f4_operazioni.parquet`, `f4_info.parquet`, `f4_descr.parquet`.

### Migliori 10 per t (nessuna passa)

Netto in R e in multipli del costo round trip per operazione; anni = anni
positivi / anni con >= 5 operazioni; costo/R = mediana del costo in % del rischio.

| variante | n | netto R | netto / costo | t | anni | p placebo | costo/R |
|---|---|---|---|---|---|---|---|
| c oro 22-22, regime CMP (ATR5/ATR60 < 0,8), S2, X1 | 434 | +0,196 | +2,9 | 2,67 | 8/9 | 0,002 | 5,5% |
| a oro 22-22, R50 (range < 0,5 ATR), S2, X1 | 154 | +0,464 | +5,2 | 2,61 | 6/8 | 0,033 | 8,1% |
| a oro 22-22, R50, S2, X1T2 | 154 | +0,278 | +3,0 | 2,46 | 7/8 | 0,009 | 8,1% |
| c oro 22-22, CMP, S2, X3 | 293 | +0,305 | +6,0 | 2,27 | 7/9 | 0,051 | 5,7% |
| a argento 22-22, R50, S2, X1 | 130 | +0,386 | +1,8 | 2,12 | 7/8 | 0,015 | 17,5% |
| a oro 22-22, R75, S2, X1 | 691 | +0,122 | +1,6 | 2,10 | 7/9 | 0,006 | 6,3% |
| a oro 22-22, R50, S2, X3 | 142 | +0,603 | +6,5 | 2,10 | 7/8 | 0,034 | 8,0% |
| a oro 22-22, R75, S2, X3 | 549 | +0,213 | +3,2 | 2,08 | 7/9 | 0,031 | 6,3% |
| c oro 22-22, CMP, S1, X1 | 435 | +0,085 | +2,8 | 2,05 | 7/9 | 0,007 | 2,9% |
| a oro 22-22, R75, S2, X5 | 471 | +0,255 | +3,5 | 1,89 | 7/9 | 0,101 | 6,4% |

Peggiori: S&P 22-22 rottura del giorno prima TUTTI S1 X1 n 1515, -0,079 R,
t -4,9, 0/8 anni positivi (lordo -0,048 R: perde anche senza costi); R75 S2 X1
t -5,2; regime CMP S2 X1 t -4,9.

t medio per filtro (parti a e c; righe = mercato-giornata):

| | TUTTI | NR4 | NR7 | ID | IDNR4 | R50 | R75 | VB | VA | CMP | ESP |
|---|---|---|---|---|---|---|---|---|---|---|---|
| oro 22-22 | 0,6 | 1,1 | 1,2 | 1,1 | 1,0 | 1,7 | 1,8 | 0,3 | 0,3 | 2,1 | -0,2 |
| argento 22-22 | -1,9 | -0,3 | 0,6 | -0,4 | 0,4 | 1,1 | -0,5 | -0,9 | 0,0 | 0,7 | -1,7 |
| S&P 22-22 | -3,9 | -1,9 | -1,3 | -1,7 | -1,2 | -3,0 | -3,5 | -3,3 | -0,6 | -4,0 | -1,1 |
| S&P cash | -3,0 | -1,4 | -1,4 | -2,1 | -1,8 | -0,8 | -2,1 | -2,5 | 0,0 | -3,3 | -0,9 |
| Nasdaq 22-22 | -2,3 | -1,9 | -1,1 | -1,7 | -1,8 | -1,3 | -2,0 | -2,5 | -0,1 | -1,6 | -1,1 |
| Nasdaq cash | -1,7 | -0,9 | -1,6 | -1,2 | -1,0 | -2,7 | -1,8 | -2,5 | 0,0 | -2,0 | -0,7 |
| DAX 22-22 | -0,4 | -0,7 | 0,5 | 0,6 | 0,0 | 0,1 | -0,2 | -0,9 | 0,4 | -1,5 | -0,7 |
| DAX cash | -0,4 | -0,5 | -0,5 | -0,5 | 0,4 | -0,1 | -0,9 | -1,0 | 0,4 | -0,9 | -0,7 |

### Descrittive

**Compressione -> espansione? No.** Range del giorno dopo / atr_pre:
dopo R50 0,65-0,78 sugli indici e 0,94-0,99 sui metalli (norma ~1,0);
dopo NR7 0,73-0,89 sugli indici. La giornata stretta e' seguita da un'altra
giornata stretta (persistenza), non da un'esplosione. Ma la frazione di giorni
che rompe ENTRAMBI i lati del giorno prima sale da 0,09-0,13 (TUTTI) a
0,19-0,32 (NR7, IDNR4, R50): piu' falsi segnali, e lo stop all'altro lato
viene preso piu' spesso.

**Giorno dopo una giornata estrema** (k+1 nella direzione di k; range k+1 /
atr_pre[k], norma ~1,0):

| mercato | RNG20 n | p continua | rend. k+1 in ATR | range k+1 | RET15 n | p continua | rend. k+1 | range k+1 |
|---|---|---|---|---|---|---|---|---|
| oro | 90 | 0,54 | +0,06 | 1,32 | 85 | 0,55 | +0,10 | 1,29 |
| argento | 90 | 0,49 | +0,04 | 1,53 | 79 | 0,56 | +0,12 | 1,52 |
| S&P | 79 | 0,46 | -0,02 | 1,58 | 70 | 0,44 | -0,14 | 1,54 |
| Nasdaq | 80 | 0,40 | -0,17 | 1,53 | 74 | 0,45 | -0,15 | 1,46 |
| DAX | 75 | 0,51 | -0,01 | 1,30 | 81 | 0,57 | +0,08 | 1,15 |

Il giorno dopo e' soprattutto PIU' VOLATILE (+30-58% di range); direzione:
leggero rientro sugli indici USA, leggera continuazione sui metalli, nessuna
regola di trading (b) arriva a t 2 (migliore: DAX RET10 REV 0,5ATR X3, t 1,75).

**Persistenza** (correlazione a 1 giorno del log range): oro 0,34, argento
0,63, S&P 0,52, Nasdaq 0,53, DAX 0,49. Al netto del livello recente
(log range/atr_pre): S&P 0,32, Nasdaq 0,29, DAX 0,19, argento 0,10, oro 0,02.

### ATR14 e costo in % del rischio, per mercato e anno

ATR14 mediano (giornata 22-22, unita' di prezzo) e, fra parentesi, in % del prezzo:

| | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 |
|---|---|---|---|---|---|---|---|---|---|
| oro | 16,5 (1,74) | 18,5 (1,52) | 20,9 (1,35) | 22,7 (1,36) | 24,5 (1,79) | 16,2 (1,27) | 16,1 (1,38) | 17,2 (1,37) | 12,5 (0,99) |
| argento | | 0,51 (2,78) | 1,37 (3,90) | 0,79 (2,48) | 0,66 (2,94) | 0,40 (2,07) | 0,39 (2,46) | 0,40 (2,37) | 0,29 (1,72) |
| S&P | | 14,5 (1,17) | 20,4 (1,60) | 16,4 (1,19) | 16,5 (1,00) | 18,2 (0,94) | 24,1 (1,16) | 22,1 (1,05) | 15,8 (0,65) |
| Nasdaq | | 28,1 (1,27) | 41,5 (1,80) | 37,5 (1,42) | 34,3 (1,14) | 44,9 (1,17) | 61,9 (1,40) | 59,8 (1,32) | 51,3 (0,89) |
| DAX | | 88 (1,26) | 129 (1,84) | 113 (1,65) | 100 (1,21) | 133 (1,39) | 223 (2,03) | 178 (1,74) | 120 (0,97) |

(2010 = solo novembre-dicembre per i mercati HistData.)

Costo round trip in % del rischio tipico (rischio = range del giorno prima,
cioe' lo stop S1 della rottura; mediana) e, fra parentesi, in % dell'ATR14:

| | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 |
|---|---|---|---|---|---|---|---|---|---|
| oro | 2,4 (2,4) | 2,2 (2,2) | 1,7 (1,9) | 2,0 (1,8) | 1,8 (1,6) | 2,8 (2,5) | 2,8 (2,5) | 2,5 (2,3) | 3,3 (3,2) |
| argento | | 4,7 (4,9) | 2,0 (1,8) | 3,4 (3,2) | 4,0 (3,8) | 7,2 (6,2) | 7,5 (6,4) | 6,9 (6,2) | 9,0 (8,5) |
| S&P | | 6,9 (3,8) | 2,4 (2,7) | 3,4 (3,3) | 3,7 (3,3) | 3,1 (3,0) | 2,1 (2,3) | 2,7 (2,5) | 3,8 (3,5) |
| Nasdaq | | 9,0 (5,3) | 3,5 (3,6) | 4,3 (4,0) | 4,8 (4,4) | 3,4 (3,3) | 2,5 (2,4) | 2,8 (2,5) | 3,3 (2,9) |
| DAX | | 3,5 (1,7) | 1,1 (1,2) | 1,4 (1,3) | 1,5 (1,5) | 1,1 (1,1) | 0,7 (0,7) | 0,9 (0,8) | 1,3 (1,2) |

Sulla giornata cash degli indici il costo pesa ~10-15% in piu' (range minore).
Con stop piu' stretti (S2 = meta' range, 0,5 ATR) il peso raddoppia: argento
2017 ~18% del rischio.

## Candidati

**Nessuno.** Nessuna delle 736 varianti soddisfa t >= 3 (massimo 2,67). Il
gruppo piu' vicino e' la rottura del range del giorno prima sull'oro con stop a
meta' range in fase di volatilita' in calo (CMP, R50, R75): netto positivo, 7-8
anni su 9 positivi, ma t 2,1-2,7. Non si congela nulla; non va promosso a
posteriori ritoccando soglie.

## Osservazioni

1. La compressione NON annuncia espansione: dopo giornate strette il giorno
   dopo resta stretto (range 0,65-0,8 ATR sugli indici); aumenta solo la
   probabilita' di rompere entrambi i lati (da ~11% a 20-30%), cioe' i falsi
   segnali.
2. Sugli indici USA la rottura del giorno prima perde in modo sistematico
   (S&P t fino a -5, 0/8 anni positivi, negativa anche al lordo), soprattutto
   in volatilita' bassa o in calo (VB, CMP); in volatilita' alta (VA) e' piatta.
   E' un indizio di ritorno alla media giornaliero sugli indici, coerente col
   rientro dopo le giornate estreme (p continua 0,40-0,46): non era una
   variante dichiarata qui, va eventualmente dichiarata come prova nuova.
3. Dopo una giornata estrema il giorno dopo e' +30-58% piu' ampio della norma,
   ma senza direzione sfruttabile: la volatilita' serve a dimensionare lo stop
   e a scegliere QUANDO operare, non da sola come segnale. L'oro e' l'unico
   mercato dove la rottura del giorno prima ha netto positivo quasi ovunque.
