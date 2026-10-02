# Famiglia 3 — Range di apertura e del giorno prima (scoperta 2009/2010-2017)

Protocollo: `docs/ricerca-da-zero-registrazione.md`. Script:
`trading/scripts/zero_f3_range.py`. Dati: solo `D:\ricerca_zero\scoperta\` (M5).

## Varianti dichiarate PRIMA del calcolo (02/10/2026)

Regole fisse per tutte le varianti (non sono dimensioni di ricerca):
segnale sulla chiusura di una candela M5, entrata all'apertura della candela
M5 successiva; gestione su M5; se nella stessa candela si toccano stop e
obiettivo vale lo stop; apertura oltre lo stop = uscita all'apertura; una sola
operazione per sessione per regola (per lato nella parte b); segnali solo fino
a 60 minuti prima della fine della finestra; uscita forzata alla chiusura
dell'ultima M5 della finestra; operazione scartata se il rischio < 2 volte il
costo round trip; costi round trip: oro 0,40, argento 0,025, S&P 0,55,
Nasdaq 1,50, DAX 1,50. ATR14 = media del true range dei 14 giorni UTC validi
precedenti (causale). Regime: rapporto (range di apertura / ATR14 in a;
range del giorno prima / ATR14 in b) contro i terzili dei 250 valori
precedenti dello stesso mercato-sessione (minimo 60): piccolo <= terzile
basso, grande >= terzile alto, tutti = nessun filtro.

**(a) Range di apertura — 756 varianti**
- 7 mercati-sessione: oro Londra 7-12 UTC, oro NY 12-21 UTC, argento Londra,
  argento NY, S&P 9:30-16:00 New York, Nasdaq 9:30-16:00 New York, DAX
  9:00-17:30 Berlino (ora legale vera con zoneinfo)
- 3 durate del range: 15, 30, 60 minuti
- 2 regole: ROTTURA (prima chiusura M5 fuori dal range -> nella direzione
  della rottura) e RIENTRO (dopo la prima chiusura fuori, prima chiusura di
  nuovo dentro -> direzione opposta alla rottura)
- 2 stop: ROTTURA: S1 altro lato del range, S2 meta' del range; RIENTRO:
  S1 estremo raggiunto fuori dal range, S2 lato rotto +/- 0,5 x range
- 3 uscite: fine sessione; obiettivo a 1 o 2 x range (ROTTURA) / 0,5 o 1 x
  range (RIENTRO) dall'entrata, altrimenti fine sessione
- 3 regimi: tutti, piccolo, grande
- 7 x 3 x 2 x 2 x 3 x 3 = **756**

**(b) Massimo/minimo del giorno e della sessione precedente — 864 varianti**
- 12 combinazioni livello-finestra: metalli (oro, argento) x {giorno UTC
  precedente in finestra 7-21 UTC; Asia 0-7 UTC in finestra Londra 7-12;
  Londra 7-12 in finestra NY 12-21}; indici (S&P, Nasdaq, DAX) x {giorno UTC
  precedente; sessione cash precedente} in finestra sessione cash
- un lato si considera solo se la finestra apre dentro i livelli
- 4 regole: TS tocco-segui (prima candela che tocca -> direzione della
  rottura), TR tocco-rientro (stessa candela -> direzione opposta), CS
  chiusura oltre il livello -> segui, FR falsa rottura (dopo una chiusura
  oltre, prima chiusura di nuovo dentro -> direzione opposta)
- 2 stop: 0,10 e 0,25 x ATR14 dall'entrata
- 3 uscite: fine finestra, obiettivo 1R, obiettivo 2R
- 3 regimi: tutti, piccolo, grande
- 12 x 4 x 2 x 3 x 3 = **864**

**Totale dichiarato: 1620 varianti.** Placebo per ogni variante: stessi
istanti, stessa gestione speculare, direzione casuale, 1000 serie, seed 12345.
Promozione: netto > 0, t >= 3, anni positivi >= 75%, p placebo < 0,01,
n >= 100 (al massimo una operazione per sessione e lato: regola giornaliera).

## Risultati (dati rigenerati con orari corretti, 02/10/2026)

Controllo fusi superato (M5 piu' volatile, inverno/estate USA, UTC): metalli
13:30/12:30, S&P e Nasdaq 14:30/13:30, DAX 08:00/07:00. Motore di gestione
confrontato con un ciclo candela per candela su 400 operazioni casuali:
differenza 0,0.

**Varianti provate: 1620** (756 parte a + 864 parte b), tutte valutate; 1608
con n >= 100. Filtri singoli: netto > 0 in 94, t >= 3 in **0**, anni >= 75%
in 11, p placebo < 0,01 in 121. **Candidati: nessuno.** Netto mediano delle
1620 varianti -0,159 R; il 94% ha t < 0.

### Le migliori 10 per t (nessuna passa)

| variante | n | netto R/op | netto / costo | t | anni + | anni | p placebo |
|---|---|---|---|---|---|---|---|
| a DAX OR15 ROTTURA S2 E0 grande | 586 | 0,148 | 3,15 | 1,69 | 4 | 7 | 0,119 |
| a DAX OR30 ROTTURA S2 E2 grande | 578 | 0,107 | 4,04 | 1,66 | 6 | 7 | 0,040 |
| b oro Asia>Londra TS K25 E2 piccolo | 683 | 0,053 | 0,71 | 1,65 | 7 | 9 | 0,001 |
| a DAX OR30 ROTTURA S2 E1 grande | 578 | 0,084 | 3,20 | 1,65 | 5 | 7 | 0,018 |
| a DAX OR30 ROTTURA S2 E0 grande | 578 | 0,094 | 3,13 | 1,33 | 5 | 7 | 0,030 |
| b DAX giorno prec. CS K10 E0 grande | 254 | 0,281 | 2,08 | 1,28 | 4 | 7 | 0,035 |
| b oro Londra>NY FR K25 E0 piccolo | 672 | 0,063 | 0,77 | 1,21 | 7 | 9 | 0,015 |
| b oro Asia>Londra CS K25 E2 piccolo | 610 | 0,039 | 0,61 | 1,20 | 7 | 9 | 0,001 |
| b DAX giorno prec. FR K10 E2 tutti | 767 | 0,061 | 0,53 | 1,17 | 5 | 8 | 0,012 |
| b oro Asia>Londra CS K25 E1 piccolo | 610 | 0,034 | 0,65 | 1,17 | 5 | 9 | 0,001 |

"netto / costo" = netto medio in prezzo diviso il costo round trip. Il p del
placebo misura la direzione contro la direzione casuale con gli stessi costi
(il placebo paga il costo due volte la media, per questo p e' piccolo anche con
t vicino a 1): da solo non basta, serve anche t >= 3 sul netto.

### Dove c'e' qualcosa al LORDO (diagnostica, non candidati)

| regola | n | lordo R/op | t lordo | costo in R | netto R/op |
|---|---|---|---|---|---|
| oro Londra, rottura range 15', stop altro lato, fine sessione | 2236 | 0,145 | 3,75 | 0,217 | -0,072 |
| oro Londra, rottura range 60', idem | 2112 | 0,071 | 3,03 | 0,128 | -0,057 |
| oro NY, tocco del max/min di Londra -> contro, stop 0,25 ATR | 3054 | 0,083 | 3,23 | 0,091 | -0,008 |
| oro NY, falsa rottura del max/min di Londra, stop 0,25 ATR | 2233 | 0,089 | 3,17 | 0,091 | -0,002 |
| argento NY, tocco del max/min di Londra -> contro | 2684 | 0,092 | 3,27 | 0,210 | -0,119 |
| S&P cash, rientro nel range 30' | 1247 | 0,136 | 2,43 | 0,212 | -0,076 |
| Nasdaq cash, rientro nel range 30' | 1261 | 0,147 | 2,33 | 0,224 | -0,077 |

Osservazioni:
1. **Oro a Londra: la rottura del range di apertura prosegue** (lordo +0,145
   R/op, t 3,75 con il range di 15'; segno coerente a 15/30/60'), ma il costo
   (0,40 $ = 0,22 R con lo stop dall'altro lato del range) se lo mangia
   tutto. A New York la stessa rottura ha segno opposto.
2. **Metalli a New York: il massimo/minimo di Londra respinge** (tocco
   -> contro e falsa rottura, t lordo 3,2-3,3 su oro e argento, segno uguale
   sui due metalli). Sull'oro il netto e' a zero (-0,002/-0,008 R/op), cioe'
   il vantaggio lordo vale quasi esattamente lo spread; sull'argento il costo
   in R e' doppio.
3. **Indici USA: il range della prima mezz'ora rientra, non prosegue**: la
   rottura ha lordo negativo su S&P e Nasdaq a tutte le durate, il rientro
   positivo (t lordo 2,1-2,4), ma il netto resta negativo. Il DAX e' l'unico
   indice dove la rottura nei giorni di range di apertura grande e' positiva
   al netto (+0,15 R/op), con t 1,7 e 4 anni su 7: rumore secondo il
   protocollo.

Le stesse idee con stop piu' larghi (costo in R minore) NON sono state
provate: sarebbero varianti a posteriori e andrebbero dichiarate in una nuova
registrazione.

### Candidati

Nessuno: nessuna delle 1620 varianti raggiunge t >= 3 sul netto (massimo
1,69). Niente da congelare in `docs/ricerca-da-zero-candidati.md` per la
famiglia 3.

Dettaglio: `D:\ricerca_zero\risultati\f3_varianti.parquet` (una riga per
variante), `f3_dettaglio_<SIM>.parquet` (una riga per operazione, con l'esito
nella direzione opposta per il placebo), `f3_lordo_diagnostica.parquet`.
