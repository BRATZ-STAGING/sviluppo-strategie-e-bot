# Famiglia 3 (FX) — Ritorno alla media e momentum di breve (5-60 minuti), scoperta 2010-2017

Protocollo vincolante: `docs/fx-intraday-registrazione.md`.

## 0. Piano registrato PRIMA del calcolo (03/10/2026)

Dati: solo `D:\ricerca_fx\scoperta\<COPPIA>_M5.parquet` (prezzi BID) e
`<COPPIA>_D1.parquet` (ATR). Coppie: EURUSD, USDJPY, GBPUSD, AUDUSD, USDCHF,
USDCAD, EURJPY. Pip 0,0001 (0,01 JPY). Costo round trip (pip): EURUSD 0,8;
GBPUSD 1,0; AUDUSD 0,9; USDCHF 1,0; USDCAD 1,2; USDJPY 1,2; EURJPY 1,4;
x2 per entrate 22:15-23:59 UTC; ogni regola anche a costi x1,5.

Definizioni (tutte causali):
- griglia M5 continua (candele mancanti = ultima chiusura nota); istante di
  decisione t = chiusura di una M5 = apertura della successiva = istante di
  entrata. Valido solo se l'ultima candela reale e' entro 30 minuti e la
  finestra [t-L, t] non attraversa una pausa > 2 ore (fine settimana, festivi).
- fasce (ora UTC di t): Asia [22:15, 07:00), Londra [07:00, 12:00),
  sovrapposizione [12:00, 16:00), pomeriggio NY [16:00, 20:45). Nessuna
  entrata 20:45-22:15. **Ogni posizione si chiude al piu' tardi all'apertura
  della M5 delle 20:45** (anche il futuro y della mappa e' troncato li').
- passato x = C(t) - C(t-L); futuro y = O(t+H) - O(t); L, H in {5, 15, 30, 60} min.
- scala attesa: ATR14 giornaliero (D1 dei soli giorni completi precedenti,
  esclusi i pezzi della domenica) x sqrt(minuti/1440): s_L per x, s_H per y,
  stop e obiettivo.
- regime: percentile di ATR14/prezzo nei 252 giorni precedenti (min 60);
  terzili basso < 1/3 <= medio < 2/3 <= alto.

**Fase A (mappa statistica)**: 7 coppie x 4 L x 4 H x 4 fasce = 448 celle.
Per cella 5 test: pendenza di y/s_H su x/s_L (valori normalizzati tagliati a
+-10, t Newey-West con ritardi H/5, tutte le decisioni ogni 5 minuti), coda
(|x|/s_L nel decile alto della cella: media di sign(x)*y, t NW; riportata anche
in pip e in multipli del costo = lordo della coda), pendenza in ciascun
terzile di regime (3). Totale Fase A: 448 x 5 = **2240 test**.

**Fase B (regole)**: solo celle consistenti (|t| >= 2 su pendenza o coda;
direzione dal segno della coda se |t_coda| >= 2, altrimenti della pendenza:
positivo = a favore/momentum, negativo = contro/ritorno alla media).
Regola: a ogni chiusura M5 nella fascia, se |x| >= k*s_L, regime ammesso e
nessuna posizione aperta, entra all'apertura della M5 successiva nella
direzione della cella; uscita a obiettivo, stop o dopo H (o alle 20:45).
Gestione su M5: stop e obiettivo controllati su massimo/minimo di ogni candela
dall'entrata; stop prima dell'obiettivo nella stessa candela; stop eseguito al
peggiore fra livello e apertura della candela, obiettivo al livello.
Varianti per cella: k in {1, 2, 3} x uscita in {solo tempo; stop 1/obiettivo 1;
stop 2/obiettivo 1; stop 1/obiettivo 2 (multipli di s_H)} x regime in {tutti,
basso, medio, alto} = **48**. Totale Fase B = 48 x celle consistenti (massimo
teorico 448 x 48 = 21504), a consuntivo.

Metriche per regola e coppia: n (non sovrapposte per costruzione), operazioni
per giornata di borsa (giorni feriali completi del D1), netto medio in pip e in
multipli del costo, lordo in multipli del costo, t sul netto, anni positivi su
8 (anno senza operazioni = non positivo), netto con costi x1,5, placebo (stessi
istanti e stessa gestione, direzione casuale per operazione, 1000 serie, seed
20261003; p = (#placebo >= vero + 1)/1001), calcolato per le regole con netto > 0.

**Aggregato fra coppie** (vincolo di frequenza del protocollo): per ogni regola
(L, H, fascia, direzione, k, uscita, regime) si sommano le coppie in cui esiste
(cella consistente con quella direzione) e ha netto > 0 a costi x1. Del
portafoglio: n, operazioni/giorno sommate, netto medio in pip e in costi, netto
a x1,5, t sul netto giornaliero (somma delle coppie per giorno: tiene conto della
correlazione fra coppie), anni positivi, placebo (direzioni casuali indipendenti
su tutte le operazioni). La scelta delle coppie "positive" e' fatta sugli stessi
dati: e' una selezione, va tenuta presente.

Promozione (protocollo): netto > 0 a x1 e x1,5, t >= 3, anni >= 6/8,
p < 0,01, >= 1 operazione per giornata di borsa sommando le coppie; massimo 3
candidati (i migliori per t giornaliero del portafoglio).

## 1. Consuntivo

Script `trading/scripts/fx_c_media_momentum.py` (`calcola` per coppia, `aggrega`
per il portafoglio, `tabelle`). Dettaglio in `D:/ricerca_fx/risultati/`:
`c_mappa_<COPPIA>.parquet` (64 celle per coppia), `c_regole_<COPPIA>.parquet`
(regole), `c_giorni_<COPPIA>.parquet` e `c_placebo_<COPPIA>.npz` (netto
giornaliero e totali placebo delle regole positive), `c_portafoglio.parquet`
(aggregato fra coppie), `c_tabelle.md`. Tempo di calcolo: ~1 minuto.

| voce | numero |
|---|---|
| test Fase A (448 celle x 5) | 2240 |
| celle consistenti (t assoluto >= 2 su pendenza o coda) | 267 (EURUSD 31, USDJPY 33, GBPUSD 42, AUDUSD 44, USDCHF 31, USDCAD 45, EURJPY 41) |
| varianti di regola Fase B (267 x 48) | 12816 (0 senza operazioni, 391 con n < 30) |
| **totale varianti provate** | **15056** (piu' 1246 aggregazioni di portafoglio delle stesse regole) |
| regole per coppia con netto > 0 a x1 / a x1,5 | 1925 / 1201 |
| regole per coppia con t >= 3 | 3 (2 con n >= 30), tutte con 0,02-0,03 operazioni/giorno |
| regole di portafoglio con >= 1 operazione/giorno | 27 (4 positive anche a x1,5; t giornaliero massimo 1,92) |
| **candidati promossi** | **0** |

## 2. Mappa statistica (Fase A)

Ogni cella: Asia Londra Sovrapposizione NY. `++`/`--` |t| >= 3, `+`/`-`
2 <= |t| < 3, `.` non significativo; `+` = momentum, `-` = ritorno alla media.

**Pendenza** (y/s_H su x/s_L, t Newey-West):

| L -> H | EURUSD | USDJPY | GBPUSD | AUDUSD | USDCHF | USDCAD | EURJPY |
|---|---|---|---|---|---|---|---|
| 5m -> 5m | -- -- -- -- | - -- - -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- -- -- -- |
| 5m -> 15m | -- - . -- | - -- - -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- - . -- |
| 5m -> 30m | -- . . -- | . -- . -- | -- - -- -- | -- -- -- -- | -- . . -- | -- -- - -- | - . . -- |
| 5m -> 60m | - . . - | . -- . . | - - - - | -- -- -- . | -- . . . | -- -- - -- | - . . -- |
| 15m -> 5m | -- -- . -- | - -- - -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- - . -- |
| 15m -> 15m | -- . . . | . - . - | -- - -- -- | -- -- -- . | -- - . - | -- -- . -- | -- . . -- |
| 15m -> 30m | - . . . | . -- . . | . . . - | - -- - . | -- . . . | -- -- . - | - . . -- |
| 15m -> 60m | . . . . | . -- . . | . . . . | - -- . . | -- . . . | - -- . . | . . . -- |
| 30m -> 5m | -- . . -- | . -- . -- | -- . -- -- | -- -- -- -- | -- - . -- | -- -- . -- | -- . . -- |
| 30m -> 15m | -- . . . | . -- . . | - . - -- | -- -- - . | -- . . . | -- -- . - | - . . -- |
| 30m -> 30m | . . . . | . -- . . | . . . . | . -- . . | -- . . . | -- -- . . | . . . - |
| 30m -> 60m | . . . . | . - . . | . . . . | . - . . | -- . . . | . - . . | . . . -- |
| 60m -> 5m | - . . - | . -- . . | -- - - - | -- -- -- . | -- . . - | -- -- - - | - . . -- |
| 60m -> 15m | . . . . | . -- . . | - . . . | - -- . . | -- . . . | - -- . . | . . . -- |
| 60m -> 30m | . . . . | . - . . | - . . . | . - . . | -- . . . | . - . . | . . . -- |
| 60m -> 60m | . . . . | . . . . | . . . . | . . . . | - . . . | . . . . | . . . - |

**Coda** (decile alto di |x|/s_L: media di sign(x)*y, t Newey-West):

| L -> H | EURUSD | USDJPY | GBPUSD | AUDUSD | USDCHF | USDCAD | EURJPY |
|---|---|---|---|---|---|---|---|
| 5m -> 5m | -- - - -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- -- -- -- |
| 5m -> 15m | -- . . -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- . . -- |
| 5m -> 30m | -- . . - | - - . -- | -- - - -- | -- -- -- -- | -- . . - | -- -- -- -- | -- . . -- |
| 5m -> 60m | -- . . - | . - . . | -- . - -- | -- - -- - | -- . . . | -- -- -- - | -- . . -- |
| 15m -> 5m | -- . . -- | - -- -- -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- -- -- -- | -- . . -- |
| 15m -> 15m | -- . . . | - -- . - | -- . . -- | -- -- - . | -- . . - | -- -- . -- | -- . . -- |
| 15m -> 30m | -- . . . | . - . . | -- . . - | -- -- . . | -- . . . | -- -- . - | - + + - |
| 15m -> 60m | -- . . . | . - . . | -- . . . | - . . . | -- . . . | - - . . | . + + -- |
| 30m -> 5m | -- . . -- | -- -- . - | -- . . -- | -- -- -- - | -- . . - | -- -- - -- | -- . . -- |
| 30m -> 15m | -- . . . | - - . . | -- . . . | -- -- . . | -- . . . | -- -- . -- | -- . . - |
| 30m -> 30m | - . + . | . - . . | -- . . . | - -- . . | -- . . . | -- -- . . | - + . - |
| 30m -> 60m | - . . . | . . . . | -- . . . | . . . . | -- . . . | . . . . | - + . - |
| 60m -> 5m | -- . . . | - -- . . | -- . - - | -- -- -- . | -- . . - | -- -- - - | -- . . -- |
| 60m -> 15m | -- . + . | . -- . . | -- . . . | . - . . | -- . . . | -- -- . . | - . . - |
| 60m -> 30m | -- . + . | . - . . | -- . . . | . . . . | -- . . . | . - . . | - . . - |
| 60m -> 60m | - + . . | . - . . | -- . . . | . . . . | -- . . . | . . . . | - . . - |

Sintesi per fascia e orizzonte (mediane sulle 7 coppie x 4 L; `coda_pip` =
lordo medio del decile alto nel verso del movimento passato, negativo = il
prezzo torna indietro; `coda_costi` = stesso numero in multipli del costo;
`coda_costi_max` = massimo assoluto; `n_cons` = celle consistenti su 28):

| fascia | H | pend_med | t_pend_med | coda_pip_med | coda_costi_med | coda_costi_max | n_cons |
|---|---|---|---|---|---|---|---|
| asia | 5 | -0.029 | -4.504 | -0.194 | -0.163 | 0.31 | 28 |
| asia | 15 | -0.028 | -3.351 | -0.365 | -0.292 | 0.481 | 27 |
| asia | 30 | -0.022 | -2.099 | -0.384 | -0.287 | 0.533 | 23 |
| asia | 60 | -0.016 | -1.391 | -0.442 | -0.346 | 0.816 | 19 |
| londra | 5 | -0.018 | -4.166 | -0.134 | -0.13 | 0.379 | 22 |
| londra | 15 | -0.015 | -2.745 | -0.177 | -0.161 | 0.435 | 18 |
| londra | 30 | -0.006 | -1.251 | -0.117 | -0.102 | 0.501 | 15 |
| londra | 60 | -0.005 | -1.157 | -0.088 | -0.083 | 1.241 | 14 |
| sovrapp | 5 | -0.014 | -2.678 | -0.21 | -0.182 | 0.51 | 18 |
| sovrapp | 15 | -0.005 | -0.833 | -0.122 | -0.109 | 0.734 | 10 |
| sovrapp | 30 | -0.002 | -0.295 | -0.034 | -0.03 | 0.999 | 7 |
| sovrapp | 60 | -0.002 | -0.307 | 0.064 | 0.053 | 1.318 | 4 |
| ny | 5 | -0.03 | -4.69 | -0.223 | -0.221 | 0.558 | 26 |
| ny | 15 | -0.022 | -2.547 | -0.269 | -0.236 | 0.642 | 16 |
| ny | 30 | -0.013 | -1.51 | -0.247 | -0.236 | 0.699 | 12 |
| ny | 60 | -0.006 | -0.643 | -0.273 | -0.293 | 0.741 | 8 |

Per coppia: nessuna cella di pendenza con t >= 2 in positivo (momentum), da 21
a 44 celle su 64 con t <= -2; t minimo da -5,5 (USDJPY) a -9,2 (AUDUSD).

## 3. Regole (Fase B)

Lordo in multipli del costo, regole per coppia con n >= 30 (gia' selezionate
nel verso giusto della cella, quindi ottimiste):

| H | uscita | count | 50% | 90% | max |
|---|---|---|---|---|---|
| 5 | s1o1 | 1118.0 | -0.075 | 0.276 | 1.577 |
| 5 | s1o2 | 1118.0 | 0.168 | 0.661 | 2.845 |
| 5 | s2o1 | 1118.0 | -0.06 | 0.288 | 2.001 |
| 5 | tempo | 1118.0 | 0.238 | 1.094 | 8.018 |
| 15 | s1o1 | 830.0 | 0.199 | 0.76 | 3.052 |
| 15 | s1o2 | 829.0 | 0.345 | 1.249 | 4.26 |
| 15 | s2o1 | 825.0 | 0.202 | 0.925 | 3.446 |
| 15 | tempo | 818.0 | 0.384 | 1.748 | 9.088 |
| 30 | s1o1 | 659.0 | 0.305 | 1.376 | 6.93 |
| 30 | s1o2 | 658.0 | 0.378 | 2.037 | 6.793 |
| 30 | s2o1 | 655.0 | 0.348 | 1.539 | 7.118 |
| 30 | tempo | 641.0 | 0.378 | 2.094 | 9.535 |
| 60 | s1o1 | 517.0 | 0.446 | 1.856 | 5.859 |
| 60 | s1o2 | 514.0 | 0.544 | 2.436 | 6.801 |
| 60 | s2o1 | 515.0 | 0.456 | 2.124 | 6.821 |
| 60 | tempo | 492.0 | 0.474 | 2.501 | 10.877 |

Migliori 12 regole per coppia per t (n >= 30). Netto in pip; `opd` =
operazioni per giornata di borsa; `lordo_costi`/`netto_costi` = per
operazione in multipli del costo medio pagato:

| coppia | L | H | fascia | dir | k | uscita | regime | n | opd | netto_pip | netto15_pip | lordo_costi | netto_costi | t | anni_pos | p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EURJPY | 60 | 60 | ny | contro | 2.0 | s2o1 | medio | 67 | 0.032 | 8.15 | 7.45 | 6.821 | 5.821 | 3.491 | 8 | 0.002 |
| USDJPY | 15 | 30 | londra | contro | 3.0 | s2o1 | alto | 48 | 0.023 | 7.341 | 6.741 | 7.118 | 6.118 | 3.458 | 7 | 0.001 |
| USDJPY | 15 | 30 | londra | contro | 3.0 | tempo | alto | 40 | 0.019 | 10.243 | 9.643 | 9.535 | 8.535 | 2.927 | 7 | 0.001 |
| AUDUSD | 15 | 60 | londra | contro | 3.0 | s1o1 | basso | 64 | 0.031 | 4.134 | 3.684 | 5.593 | 4.593 | 2.795 | 7 | 0.001 |
| AUDUSD | 15 | 5 | londra | contro | 3.0 | tempo | basso | 87 | 0.042 | 1.695 | 1.245 | 2.884 | 1.884 | 2.793 | 5 | 0.001 |
| AUDUSD | 15 | 60 | londra | contro | 3.0 | s2o1 | basso | 61 | 0.029 | 4.467 | 4.017 | 5.964 | 4.964 | 2.778 | 7 | 0.004 |
| AUDUSD | 15 | 30 | londra | contro | 3.0 | s2o1 | basso | 63 | 0.03 | 2.989 | 2.539 | 4.321 | 3.321 | 2.712 | 6 | 0.002 |
| AUDUSD | 15 | 30 | londra | contro | 3.0 | tempo | basso | 60 | 0.029 | 3.568 | 3.118 | 4.965 | 3.965 | 2.617 | 5 | 0.001 |
| AUDUSD | 15 | 15 | londra | contro | 3.0 | tempo | basso | 61 | 0.029 | 2.51 | 2.06 | 3.789 | 2.789 | 2.587 | 6 | 0.003 |
| AUDUSD | 5 | 60 | sovrapp | contro | 2.0 | tempo | alto | 362 | 0.175 | 3.408 | 2.958 | 4.786 | 3.786 | 2.569 | 5 | 0.001 |
| AUDUSD | 5 | 60 | sovrapp | contro | 2.0 | s1o2 | alto | 440 | 0.212 | 2.899 | 2.449 | 4.221 | 3.221 | 2.555 | 4 | 0.003 |
| AUDUSD | 15 | 30 | londra | contro | 3.0 | s2o1 | tutti | 131 | 0.063 | 2.753 | 2.303 | 4.059 | 3.059 | 2.552 | 7 | 0.006 |

Portafoglio (somma delle coppie dove la regola e' positiva a x1; t sul netto
giornaliero sommato): migliori 15 per t:

| L | H | fascia | dir | k | uscita | regime | coppie | n | opd | netto_pip | netto15_pip | lordo_costi | netto_costi | t_giorno | anni_pos | p | promossa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | 30 | londra | contro | 3.0 | s2o1 | alto | USDJPY,AUDUSD | 85 | 0.041 | 6.11 | 5.576 | 6.714 | 5.714 | 4.621 | 7 | 0.001 | False |
| 60 | 5 | asia | contro | 3.0 | s1o2 | medio | USDCAD | 21 | 0.01 | 2.222 | 1.508 | 2.555 | 1.555 | 3.926 | 2 | 0.042 | False |
| 15 | 30 | asia | contro | 3.0 | tempo | alto | EURUSD,USDCHF | 46 | 0.022 | 9.485 | 8.926 | 9.488 | 8.488 | 3.492 | 8 | 0.001 | False |
| 60 | 60 | ny | contro | 2.0 | s2o1 | medio | EURJPY | 67 | 0.032 | 8.15 | 7.45 | 6.821 | 5.821 | 3.385 | 8 | 0.002 | False |
| 60 | 15 | londra | contro | 3.0 | s2o1 | medio | USDCAD | 11 | 0.005 | 3.186 | 2.586 | 3.655 | 2.655 | 3.315 | 4 | 0.044 | False |
| 60 | 15 | londra | contro | 3.0 | s1o1 | medio | USDCAD | 12 | 0.006 | 2.821 | 2.221 | 3.351 | 2.351 | 3.277 | 4 | 0.068 | False |
| 15 | 30 | londra | contro | 3.0 | tempo | alto | USDJPY,AUDUSD | 72 | 0.035 | 7.751 | 7.218 | 8.267 | 7.267 | 3.106 | 7 | 0.001 | False |
| 15 | 60 | asia | contro | 2.0 | s1o2 | tutti | GBPUSD | 488 | 0.235 | 2.807 | 2.222 | 3.399 | 2.399 | 2.97 | 5 | 0.008 | False |
| 60 | 60 | ny | contro | 2.0 | s1o1 | medio | EURJPY | 77 | 0.037 | 5.53 | 4.83 | 4.95 | 3.95 | 2.884 | 8 | 0.001 | False |
| 5 | 15 | londra | contro | 3.0 | s2o1 | medio | USDCAD | 53 | 0.026 | 2.77 | 2.17 | 3.308 | 2.308 | 2.845 | 5 | 0.004 | False |
| 30 | 30 | ny | contro | 3.0 | s1o1 | medio | EURJPY | 25 | 0.012 | 4.455 | 3.755 | 4.182 | 3.182 | 2.82 | 7 | 0.035 | False |
| 5 | 60 | sovrapp | contro | 2.0 | s1o2 | alto | AUDUSD | 440 | 0.212 | 2.899 | 2.449 | 4.221 | 3.221 | 2.82 | 4 | 0.003 | False |
| 15 | 5 | londra | contro | 3.0 | s1o2 | basso | AUDUSD | 87 | 0.042 | 1.315 | 0.865 | 2.461 | 1.461 | 2.783 | 7 | 0.001 | False |
| 60 | 30 | londra | contro | 3.0 | tempo | alto | USDJPY,AUDUSD,USDCAD | 48 | 0.023 | 6.367 | 5.807 | 6.691 | 5.691 | 2.737 | 5 | 0.001 | False |
| 60 | 60 | ny | contro | 3.0 | s2o1 | medio | EURJPY | 13 | 0.006 | 13.42 | 12.72 | 10.586 | 9.586 | 2.672 | 5 | 0.052 | False |

Portafoglio con almeno 1 operazione per giornata di borsa (vincolo dell'utente):
migliori 10 per t:

| L | H | fascia | dir | k | uscita | regime | coppie | n | opd | netto_pip | netto15_pip | lordo_costi | netto_costi | t_giorno | anni_pos | p | promossa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 60 | asia | contro | 2.0 | s1o2 | tutti | EURUSD,GBPUSD,USDCHF | 2229 | 1.075 | 0.78 | 0.24 | 1.723 | 0.723 | 1.917 | 3 | 0.001 | False |
| 30 | 30 | sovrapp | favore | 2.0 | s2o1 | tutti | EURUSD | 2132 | 1.028 | 0.523 | 0.123 | 1.653 | 0.653 | 1.568 | 5 | 0.001 | False |
| 30 | 60 | asia | contro | 1.0 | s1o2 | tutti | GBPUSD | 2189 | 1.055 | 0.559 | -0.018 | 1.485 | 0.485 | 1.556 | 4 | 0.001 | False |
| 30 | 30 | sovrapp | favore | 2.0 | s1o1 | tutti | EURUSD | 2325 | 1.121 | 0.401 | 0.001 | 1.501 | 0.501 | 1.417 | 5 | 0.001 | False |
| 5 | 60 | asia | contro | 1.0 | s1o2 | alto | GBPUSD,USDCHF | 2411 | 1.162 | 0.425 | -0.144 | 1.374 | 0.374 | 1.213 | 4 | 0.001 | False |
| 60 | 60 | asia | contro | 1.0 | tempo | tutti | GBPUSD,USDCHF | 2559 | 1.234 | 0.692 | 0.122 | 1.607 | 0.607 | 1.205 | 4 | 0.001 | False |
| 5 | 5 | sovrapp | contro | 2.0 | tempo | alto | USDJPY,GBPUSD,AUDUSD | 2124 | 1.024 | 0.293 | -0.225 | 1.283 | 0.283 | 1.175 | 6 | 0.001 | False |
| 60 | 60 | asia | contro | 1.0 | s2o1 | tutti | GBPUSD,USDCHF | 2741 | 1.322 | 0.301 | -0.274 | 1.262 | 0.262 | 0.962 | 4 | 0.001 | False |
| 60 | 60 | asia | contro | 1.0 | s1o2 | tutti | GBPUSD,USDCHF | 2882 | 1.39 | 0.277 | -0.299 | 1.24 | 0.24 | 0.943 | 4 | 0.001 | False |
| 15 | 5 | sovrapp | contro | 2.0 | tempo | alto | GBPUSD,AUDUSD,USDCHF | 2369 | 1.142 | 0.22 | -0.269 | 1.225 | 0.225 | 0.894 | 6 | 0.001 | False |

Motivi di bocciatura: le regole con t >= 3 (EURJPY 60m->60m NY; USDJPY e
AUDUSD 15m->30m Londra in volatilita' alta; EURUSD+USDCHF 15m->30m Asia in
volatilita' alta) operano da una volta al mese a una ogni due settimane
(0,02-0,04/giorno, anche sommando le coppie): 25-50 volte sotto la frequenza
richiesta. Le regole che raggiungono 1 operazione/giorno hanno t <= 1,92,
3-6 anni positivi su 8 e quasi sempre netto <= 0 a costi x1,5.

## 4. Candidati

**Nessuno.** Nessuna delle 12816 regole (ne' delle 1246 aggregazioni fra
coppie) soddisfa insieme netto > 0 a x1 e x1,5, t >= 3, anni >= 6/8,
p < 0,01 e >= 1 operazione per giornata di borsa. Niente da portare in verifica
per la famiglia 3.

Per memoria (NON promossi, solo frequenza insufficiente; specifiche esatte
ricavabili dalle righe del portafoglio): contro un movimento di 15 minuti
>= 3 s_L a Londra in volatilita' alta, uscita a 30 minuti con stop 2 s_H e
obiettivo 1 s_H su USDJPY+AUDUSD: n 85 in 8 anni (0,04/giorno), +6,1 pip
(5,7 costi), x1,5 +5,6, t 4,6, 7/8 anni, p 0,001. Scelto fra 15056 varianti e
con le coppie selezionate in campione: va letto come indizio, non come regola.

## 5. Osservazioni

1. **Il ritorno alla media di breve sui cambi e' ovunque e fortissimo come
   statistica, ma vale meno del costo.** 267 celle consistenti su 448: 257 di ritorno alla media,
   10 di momentum (solo in coda); t fino a -9. Nessuna coppia ha
   momentum in pendenza. L'effetto e' massimo in Asia e nel pomeriggio di New
   York (mercato sottile) e minimo nella sovrapposizione Londra-New York,
   dove si spegne gia' oltre i 15 minuti. Ma il decile dei movimenti grandi
   restituisce in mediana 0,1-0,4 pip, cioe' 0,1-0,35 volte il costo; anche
   le regole selezionate con soglia k >= 2 hanno lordo mediano 0,24 costi a
   5 minuti e 0,38-0,47 a 15-60 minuti. Parte dell'effetto sotto i 15 minuti
   e' rumore di quotazione BID (rimbalzo fra quote), non un movimento
   negoziabile.
2. **Forza e frequenza sono in conflitto per costruzione.** Il lordo copre i
   costi solo dopo movimenti estremi (k = 3, spesso in volatilita' alta o
   media): li' si arriva a 4-9 costi per operazione e t 3-4,6, ma con
   0,02-0,04 operazioni al giorno. Abbassando la soglia per arrivare a 1
   operazione al giorno il lordo scende a 1,2-1,7 costi e il netto a x1,5
   diventa nullo o negativo. Il placebo a direzione casuale da' p 0,001 quasi
   ovunque: la direzione c'e', e' l'ammontare che manca.
3. **Unica eccezione di momentum: EURUSD ed EURJPY a Londra e nella
   sovrapposizione, 15-60 minuti, solo nella coda** (10 celle, t coda 2,1-2,8,
   nessuna pendenza con t >= 2), con lordo del decile alto 0,4-1,0 costi. Come
   regola (EURUSD 30m->30m sovrapposizione a favore, k = 2, 1,0-1,1
   operazioni/giorno) rende +0,4/+0,5 pip netti con t 1,4-1,6, 5/8 anni e
   netto a x1,5 quasi nullo: debole e non promuovibile. I cambi sono piu' "da
   ritorno alla media" di quanto un costo Raw permetta di sfruttare sotto
   l'ora.
