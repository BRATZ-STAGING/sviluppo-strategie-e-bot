# Famiglia 2 — Momentum contro ritorno alla media (scoperta, da zero)

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
`f2_faseb.parquet` (regole). Tempo totale ~30 s.

| voce | numero |
|---|---|
| test Fase A (360 celle x 5) | 1800 |
| celle consistenti (t assoluto >= 2 su pendenza o coda) | 126 |
| varianti di regola Fase B (126 x 12) | 1512 (180 senza operazioni, 679 con n < 30) |
| **totale varianti provate** | **3312** |
| regole con netto > 0 | 477 |
| regole con t >= 3 | 3 (tutte con n = 2-5: rumore) |
| **candidati promossi** | **0** |

GRXEUR non ha quotazioni nella sessione Asia (celle "x").

## 2. Mappa segno/forza (Fase A, t della pendenza Newey-West)

Ogni cella: Asia Londra NY. `++`/`--` |t| >= 3, `+`/`-` 2 <= |t| < 3,
`.` non significativo; `+` = momentum, `-` = ritorno alla media.

| L -> H | XAUUSD | SPXUSD | NSXUSD | XAGUSD | GRXEUR |
|---|---|---|---|---|---|
| 5m -> 5m | . . . | . . - | . . . | -- -- -- | x . -- |
| 5m -> 15m | . -- - | . . - | . . . | - -- . | x . -- |
| 15m -> 5m | . -- - | . . -- | . . . | -- -- . | x . -- |
| 15m -> 15m | . -- . | . . . | . . . | - -- . | x . . |
| 15m -> 1h | . . . | . . . | . . . | - . . | x . . |
| 1h -> 5m | . -- . | . . . | . . . | -- -- . | x . . |
| 1h -> 15m | . - . | . . . | . . . | -- - . | x . . |
| 1h -> 1h | . . . | + . . | + . + | - . . | x . . |
| 1h -> 4h | . . . | . . . | . - . | - - . | x . . |
| 4h -> 5m | . . . | . . . | . . . | -- - . | x . . |
| 4h -> 15m | . . . | . . . | . . . | -- . . | x . . |
| 4h -> 1h | . . . | . - . | . - . | - . . | x x . |
| 4h -> 4h | . . . | . . . | . - . | . . . | x x . |
| 1g -> 5m | + . + | . - . | . - . | . . . | x . . |
| 1g -> 15m | + . + | . -- . | . - . | . . . | x . . |
| 1g -> 1h | + . + | . - . | . - . | + . . | x . . |
| 1g -> 4h | + + . | - -- . | . -- - | + . . | x . . |
| 1g -> 1g | . . . | -- -- . | -- -- . | . . . | x . . |
| 5g -> 5m | . + ++ | . - . | . - . | . . . | x . . |
| 5g -> 15m | . + ++ | . - . | . - . | . . . | x . + |
| 5g -> 1h | . + + | . - . | . - . | . . . | x . + |
| 5g -> 4h | . ++ + | -- - . | . -- . | . ++ . | x . + |
| 5g -> 1g | + . + | -- -- - | - - - | . . . | x . . |
| 5g -> 5g | + + + | - - - | - - - | ++ ++ ++ | x . . |

Effetto tipico: pendenze normalizzate fra -0,02 e -0,03 sotto l'ora,
-0,08/-0,11 sull'1g->1g degli indici, +0,08/+0,13 sul 5g dei metalli.

## 3. Migliori 10 regole per t (n >= 30; nessuna passa)

Le tre regole con t >= 3 hanno 2-5 operazioni e sono escluse. Netto in unita'
di prezzo, `netto_costi` = netto / costo round trip.

| mercato | L | H | sessione | k | regime | direzione | n | netto | netto_costi | t | t_rob | anni_pos | anni | p_placebo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| XAGUSD | 5g | 5g | asia | 1.0 | basso | a favore | 49 | 0.287 | 11.469 | 2.961 | nan | 6.0 | 7.0 | 0.001 |
| XAGUSD | 5g | 5g | londra | 1.0 | basso | a favore | 51 | 0.26 | 10.382 | 2.909 | nan | 5.0 | 7.0 | 0.002 |
| NSXUSD | 5g | 5g | asia | 1.0 | medio | contro | 51 | 30.827 | 20.551 | 2.726 | nan | 6.0 | 7.0 | 0.007 |
| SPXUSD | 1g | 1g | asia | 1.0 | tutti | contro | 326 | 2.735 | 4.972 | 2.635 | 2.405 | 7.0 | 7.0 | 0.003 |
| XAGUSD | 5g | 5g | ny | 1.0 | basso | a favore | 66 | 0.274 | 10.95 | 2.557 | nan | 7.0 | 7.0 | 0.002 |
| GRXEUR | 1h | 4h | ny | 2.0 | basso | a favore | 138 | 13.453 | 8.969 | 2.549 | 2.145 | 5.0 | 6.0 | 0.003 |
| SPXUSD | 5g | 4h | asia | 1.0 | medio | contro | 117 | 0.738 | 1.343 | 2.371 | 1.971 | 4.0 | 7.0 | 0.001 |
| SPXUSD | 1h | 1h | asia | 2.0 | tutti | a favore | 33 | 5.302 | 9.641 | 2.246 | nan | 4.0 | 6.0 | 0.005 |
| XAGUSD | 4h | 4h | ny | 2.0 | alto | a favore | 63 | 0.111 | 4.431 | 2.237 | nan | 4.0 | 6.0 | 0.005 |
| XAGUSD | 1h | 4h | ny | 2.0 | alto | a favore | 100 | 0.093 | 3.72 | 2.211 | 1.954 | 4.0 | 6.0 | 0.001 |

Motivi di bocciatura: le prime tre e la quinta hanno n ~50 (orizzonte 5g non
sovrapposto: al massimo ~350 operazioni in 7 anni, con soglia e regime ~50);
la quarta (S&P) fallisce solo su t (2,64 < 3).

## 4. Candidati

**Nessuno.** Nessuna delle 1512 regole soddisfa insieme t >= 3, anni >= 75%,
p < 0,01, n minimo e netto > 0. Niente da congelare in
`docs/ricerca-da-zero-candidati.md` per la famiglia 2.

Il "quasi candidato" (NON promosso, solo per memoria): S&P, decisione a ogni
ora piena fra 00:00 e 06:00 UTC, se la variazione delle ultime 24 ore di borsa
(chiusura M5 di adesso contro la stessa ora del giorno feriale prima) supera
1 ATR14 giornaliero, entra CONTRO all'apertura della M5 successiva, esci alla
stessa ora del giorno feriale dopo; costo 0,55. n 326, netto +2,74 punti
(5,0 costi), t 2,64, 7/7 anni, placebo p 0,003. A Londra lo stesso fa t 1,90
(7/8 anni), a NY sparisce; il Nasdaq ha lo stesso segno ma t 1,44.

## 5. Osservazioni

1. **Il ritorno alla media di brevissimo e' l'effetto statisticamente piu'
   forte, ed e' inutilizzabile.** Argento (tutte le sessioni), DAX a NY, oro a
   Londra, S&P a NY: dopo 5-15 minuti il prezzo restituisce il 2-3% del
   movimento (|t| fino a 5,3 su ~200 mila osservazioni). Ma il lordo delle
   regole con H <= 15m vale in mediana 0,08 volte il costo (massimo 1,8 su 241
   operazioni): il costo e' 10-15 volte il vantaggio. Parte puo' essere rumore
   di quotazione dei dati, non un movimento negoziabile.
2. **Indici: ritorno alla media giornaliero, solo misurato fuori dal cash
   americano.** S&P e Nasdaq 1g->1g e 5g->1g/4h negativi (t -3,3/-3,9) se la
   decisione cade in Asia o a Londra, nulli a NY; piu' forte nei regimi a
   volatilita' bassa/media, nullo in quella alta. E' l'unico effetto che
   copre i costi con margine (3-5 costi) e regge 7 anni su 7, ma non arriva
   a t 3. Contraddice la previsione 2 del protocollo (momentum sugli indici):
   nel 2011-2017 gli indici comprano i ribassi.
3. **Metalli: momentum lento, non ritorno alla media.** Oro 5g->5m/15m/1h/4h
   e 1g->intraday positivi (t fino a 4,8 a Londra), argento 5g->5g positivo in
   tutte e tre le sessioni (t 3,3-3,6), entrambi solo in volatilita'
   bassa/media e spenti in quella alta. Il lordo copre 9-11 costi per
   operazione, ma un orizzonte di 5 giorni non sovrapposto da' ~50
   operazioni in 7-9 anni: la soglia di 100 lo rende non promuovibile per
   costruzione. Il ritorno alla media dei metalli previsto dal protocollo
   esiste solo sotto i 15 minuti, dove i costi lo annullano.
