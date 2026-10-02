# Famiglia 2 — Momentum contro ritorno alla media (scoperta, da zero)

> **VERSIONE RIGENERATA (02/10/2026, sera).** La prima versione usava file
> SPXUSD/NSXUSD/XAGUSD/GRXEUR sfasati di +1 ora quando New York e' in ora
> legale (HistData e' in ora di New York con ora legale). I file sono stati
> rigenerati alle 23:16 con orari corretti; XAUUSD era gia' giusto e i suoi
> numeri non cambiano. Stesso piano, stesse varianti, nessuna aggiunta.
> Cosa cambia rispetto alla prima versione:
> - le celle con l'ora estiva corretta passano da 126 a 131 consistenti, quindi
>   1572 regole invece di 1512; totale varianti 3372 invece di 3312;
> - celle che cambiano classe di segno/forza: DAX 28, argento 9, Nasdaq 6,
>   S&P 1, oro 0 (il DAX ora ha anche qualche quotazione prima delle 7 UTC);
> - **il quasi-candidato S&P (contro il movimento delle 24 ore, decisione
>   00-06 UTC) si indebolisce**: t da 2,64 a 2,06, anni da 7/7 a 6/7, netto da
>   +2,74 a +2,00 punti (3,6 costi), placebo p da 0,003 a 0,006. Nella mappa
>   statistica l'effetto resta (t -3,8 in Asia, -3,6 a Londra), ma la regola
>   non e' piu' vicina alla promozione;
> - le conclusioni qualitative restano le stesse; candidati: ancora **zero**.

## 0. Piano registrato PRIMA del calcolo (02/10/2026)

Dati: solo `D:\ricerca_zero\scoperta\<SIMBOLO>_M5.parquet` (prezzi) e
`<SIMBOLO>_D1.parquet` (ATR). Mercati: XAUUSD, SPXUSD, NSXUSD, XAGUSD, GRXEUR.
Costi round trip: oro 0,40; S&P 0,55; Nasdaq 1,50; DAX 1,50; argento 0,025.

Definizioni (causali):
- istante di decisione t = chiusura di una M5 (bordo di candela); sessione
  dall'ora UTC di t: Asia [0,7), Londra [7,12), NY [12,21). Fuori: scartato.
- passato: x = C(t) - C(t-L), C = ultima chiusura nota a quell'istante;
  L in {5m, 15m, 1h, 4h, 1g, 5g}; 1g/5g = stessa ora 1/5 giorni feriali prima.
- futuro: y = O(t+H) - O(t), O = apertura della prima M5 con etichetta >= istante
  (ingresso all'apertura della candela dopo il segnale, uscita a tempo).
- scala: ATR14 giornaliero (D1 feriali, solo giorni precedenti) x sqrt(L/1380 min).
- regime: percentile dell'ATR/prezzo nei 252 giorni precedenti, terzili 1/3, 2/3.

Coppie (L,H) con H <= 4L e H in {5m,15m,1h,4h,1g,5g}: 2+3+4+4+5+6 = **24**.

**Fase A (mappa statistica)**: 24 coppie x 3 sessioni x 5 mercati = 360 celle.
Per cella 5 test: pendenza di y/scala su x/scala (t con errori Newey-West,
griglia di campionamento min(H,1h)), coda (|x| nel decile alto: media di
sign(x)*y, t NW), pendenza in ciascun terzile di volatilita' (3).
Totale Fase A: 360 x 5 = **1800 test**.

**Fase B (regole)**: solo celle "consistenti" = |t| >= 2 nella pendenza o nella
coda. Direzione fissata dal segno (coda se |t_coda| >= 2, altrimenti pendenza):
positivo = a favore (momentum), negativo = contro (ritorno alla media).
Regola: controllo ogni min(L,1h) (bordi allineati); se |x| >= k x scala e la
sessione/regime corrispondono e non c'e' posizione aperta, entra all'apertura
della candela successiva, esci all'apertura della prima candela >= t+H; nessuno
stop. Varianti per cella: k in {1, 2, 3} x regime in {tutti, basso, medio, alto}
= 12. Totale Fase B = 12 x (celle selezionate), riportato a consuntivo.
Massimo teorico se tutte le celle passassero la selezione: 360 x 12 = 4320.

Metriche per regola: n (non sovrapposte), netto medio (prezzo e multipli del
costo), t sul netto, anni positivi / anni con operazioni, placebo 1000 serie a
direzione casuale sugli stessi istanti (seed 20261002), p = quota placebo >= vero.
Promozione: netto > 0, t >= 3, anni >= 75%, p < 0,01, n >= 200 (100 se L o H
>= 1 giorno). Massimo 3 candidati (i migliori per t).

## 1. Consuntivo

Script `trading/scripts/zero_f2_momentum.py` (`AB` calcola, `R` scrive le
tabelle). Dettaglio: `D:/ricerca_zero/risultati/f2_fasea.parquet` (360 celle),
`f2_faseb.parquet` (regole); la prima versione e' conservata come `*_v1.parquet`.

| voce | numero |
|---|---|
| test Fase A (360 celle x 5) | 1800 |
| celle consistenti (t assoluto >= 2 su pendenza o coda) | 131 |
| varianti di regola Fase B (131 x 12) | 1572 (200 senza operazioni, 698 con n < 30) |
| **totale varianti provate** | **3372** |
| regole con netto > 0 | 466 |
| regole con t >= 3 | 7 (tutte con n = 2-6: rumore) |
| **candidati promossi** | **0** |

Celle "x": nessuna quotazione in quella sessione (DAX in Asia quasi assente).

## 2. Mappa segno/forza (Fase A, t della pendenza Newey-West)

Ogni cella: Asia Londra NY. `++`/`--` |t| >= 3, `+`/`-` 2 <= |t| < 3,
`.` non significativo; `+` = momentum, `-` = ritorno alla media.

| L -> H | XAUUSD | SPXUSD | NSXUSD | XAGUSD | GRXEUR |
|---|---|---|---|---|---|
| 5m -> 5m | . . . | . . - | . . . | - -- -- | - . -- |
| 5m -> 15m | . -- - | . . - | . . . | - -- . | - . -- |
| 15m -> 5m | . -- - | . . -- | . . . | - -- . | - . -- |
| 15m -> 15m | . -- . | . . . | . . . | - -- . | . . . |
| 15m -> 1h | . . . | . . . | . . . | - - . | x . . |
| 1h -> 5m | . -- . | . . . | . . . | - -- . | x . . |
| 1h -> 15m | . - . | . . . | . . . | - -- . | x . . |
| 1h -> 1h | . . . | + . . | + . + | -- . . | x . . |
| 1h -> 4h | . . . | . . . | . . . | - - . | x . . |
| 4h -> 5m | . . . | . . . | . . . | -- -- . | x . . |
| 4h -> 15m | . . . | . - . | . - . | - - . | x . . |
| 4h -> 1h | . . . | . - . | . - . | . . . | x - + |
| 4h -> 4h | . . . | . . . | . - . | . . . | x . . |
| 1g -> 5m | + . + | . - . | . . . | + . + | . . . |
| 1g -> 15m | + . + | . - . | . . . | + . + | . . . |
| 1g -> 1h | + . + | . - . | . . . | + . . | x . . |
| 1g -> 4h | + + . | - -- . | . -- . | . . . | x . . |
| 1g -> 1g | . . . | -- -- . | -- -- . | . . . | x . . |
| 5g -> 5m | . + ++ | . - . | . - . | . . . | . . + |
| 5g -> 15m | . + ++ | . - . | . - . | . . . | . . + |
| 5g -> 1h | . + + | . - . | . - . | . . . | x . + |
| 5g -> 4h | . ++ + | -- - . | . - . | . ++ . | x . ++ |
| 5g -> 1g | + . + | -- -- - | - - - | . . + | x . . |
| 5g -> 5g | + + + | - - - | - - - | ++ ++ ++ | x . . |

Effetto tipico: pendenze normalizzate fra -0,02 e -0,04 sotto l'ora,
-0,08/-0,11 sull'1g->1g degli indici, +0,08/+0,13 sul 5g dei metalli.

## 3. Migliori 10 regole per t (n >= 30; nessuna passa)

Le sette regole con t >= 3 hanno 2-6 operazioni e sono escluse. Netto in unita'
di prezzo, `netto_costi` = netto / costo round trip.

| mercato | L | H | sessione | k | regime | direzione | n | netto | netto_costi | t | t_rob | anni_pos | anni | p_placebo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| XAGUSD | 5g | 5g | asia | 1.0 | basso | a favore | 49 | 0.285 | 11.386 | 2.995 | nan | 7.0 | 7.0 | 0.001 |
| NSXUSD | 5g | 5g | asia | 1.0 | medio | contro | 53 | 31.503 | 21.002 | 2.729 | nan | 6.0 | 7.0 | 0.002 |
| NSXUSD | 1g | 4h | londra | 2.0 | tutti | contro | 35 | 14.436 | 9.624 | 2.702 | nan | 7.0 | 7.0 | 0.005 |
| XAGUSD | 5g | 5g | ny | 1.0 | basso | a favore | 65 | 0.285 | 11.394 | 2.631 | nan | 7.0 | 7.0 | 0.004 |
| XAGUSD | 5g | 5g | londra | 1.0 | basso | a favore | 51 | 0.23 | 9.209 | 2.564 | nan | 5.0 | 7.0 | 0.002 |
| SPXUSD | 5g | 4h | asia | 1.0 | medio | contro | 121 | 0.73 | 1.327 | 2.306 | 1.89 | 4.0 | 7.0 | 0.002 |
| NSXUSD | 5g | 5g | londra | 1.0 | tutti | contro | 120 | 15.763 | 10.509 | 2.132 | 1.735 | 5.0 | 7.0 | 0.014 |
| SPXUSD | 1h | 1h | asia | 2.0 | tutti | a favore | 34 | 4.924 | 8.953 | 2.122 | nan | 3.0 | 6.0 | 0.007 |
| XAGUSD | 5g | 5g | londra | 1.0 | tutti | a favore | 129 | 0.231 | 9.23 | 2.105 | 1.6 | 6.0 | 8.0 | 0.006 |
| NSXUSD | 5g | 5g | ny | 1.0 | basso | contro | 52 | 18.85 | 12.567 | 2.084 | nan | 4.0 | 6.0 | 0.013 |

Motivi di bocciatura: tutte sotto t 3; le regole sull'orizzonte 5g hanno
n ~50-130 (5 giorni non sovrapposti: al massimo ~350 operazioni in 7 anni).

## 4. Candidati

**Nessuno.** Nessuna delle 1572 regole soddisfa insieme t >= 3, anni >= 75%,
p < 0,01, n minimo e netto > 0. Niente da congelare in
`docs/ricerca-da-zero-candidati.md` per la famiglia 2.

Ex quasi-candidato della prima versione (NON promosso): S&P, decisione a ogni
ora piena fra 00:00 e 06:00 UTC; se la variazione delle ultime 24 ore di borsa
(chiusura M5 di adesso contro la stessa ora del giorno feriale prima) supera
1 ATR14 giornaliero, entra CONTRO all'apertura della M5 successiva, esci alla
stessa ora del giorno feriale dopo; costo 0,55. Con gli orari corretti:
n 325, netto +2,00 punti (3,6 costi), t 2,06, 6/7 anni, placebo p 0,006.
A Londra t 1,77 (7/8 anni); Nasdaq stesso segno ma t 1,26.

## 5. Osservazioni

1. **Il ritorno alla media di brevissimo e' l'effetto statisticamente piu'
   forte, ed e' inutilizzabile.** Argento (soprattutto Londra, t fino a -5,9),
   DAX a NY, oro a Londra, S&P a NY: dopo 5-15 minuti il prezzo restituisce il
   2-4% del movimento. Ma il lordo delle regole con H <= 15m vale in mediana
   0,07 volte il costo (massimo 1,8): il costo e' 10-15 volte il vantaggio.
   Parte puo' essere rumore di quotazione, non un movimento negoziabile.
2. **Indici: ritorno alla media giornaliero, misurato solo fuori dal cash
   americano.** S&P e Nasdaq 1g->1g e 5g->1g/4h negativi (t -3,2/-3,8) con
   decisione in Asia o a Londra, nulli a NY, spenti in volatilita' alta.
   Statisticamente robusto alla correzione dell'ora, ma come regola vale 2-3,6
   costi e t ~2: non basta. Contraddice la previsione 2 del protocollo
   (momentum sugli indici): nel 2011-2017 gli indici comprano i ribassi.
3. **Metalli (e DAX): momentum lento, non ritorno alla media.** Oro 5g->intraday
   e 1g->intraday positivi (t fino a 4,8 a Londra), argento 5g->5g positivo in
   tutte e tre le sessioni, DAX 5g->4h a NY t >= 3; solo in volatilita'
   bassa/media. Il lordo dell'argento copre 9-11 costi per operazione, ma 5
   giorni non sovrapposti danno ~50 operazioni in 7 anni: la soglia di 100 lo
   rende non promuovibile per costruzione. Il ritorno alla media dei metalli
   previsto dal protocollo esiste solo sotto i 15 minuti, dove i costi lo
   annullano.
