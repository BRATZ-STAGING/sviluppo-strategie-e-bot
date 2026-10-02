# Famiglia 1 — Orologio e sessioni (scoperta 2009/2010-2017)

Protocollo: `docs/ricerca-da-zero-registrazione.md`. Dati: solo `D:\ricerca_zero\scoperta\`.
Script: `trading/scripts/zero_f1_orologio.py`. Dettaglio: `D:\ricerca_zero\risultati\f1_*.parquet`.

## Varianti dichiarate PRIMA del calcolo (02/10/2026)

Convenzioni comuni: entrata all'apertura della prima candela M5 dall'istante
d'entrata (tolleranza 15 min), uscita alla chiusura dell'ultima candela M5 che
termina entro l'istante d'uscita (tolleranza 15 min); segnali calcolati solo su
chiusure gia' note (il segnale chiude sulla candela prima dell'entrata). Costo
round trip: oro 0,40; S&P 0,55; Nasdaq 1,50; DAX 1,50; argento 0,025. Nessuno
stop (regole a tempo). Sessioni UTC fisse: Asia 0-7, Londra 7-12, NY 12-21.
Cash locali con ora legale vera (zoneinfo): S&P/Nasdaq 9:30-16:00
America/New_York, DAX 9:00-17:30 Europe/Berlin. Notte = chiusura cash del giorno
di borsa precedente -> apertura cash (giorno = data dell'apertura).

| blocco | descrizione | conteggio |
|---|---|---|
| R1 | ora UTC h (candela H1), long e short; 5 mercati x 24 ore x 2 | 240 |
| R2 | sessione UTC intera, long/short; oro, argento, S&P, Nasdaq 3 sessioni, DAX 2 (no Asia) | 28 |
| R3 | cash locale e notte, long/short; S&P, Nasdaq, DAX | 12 |
| R4a | persistenza: segno del primo tratto L in {30,60} min decide il resto della sessione; 6 modi (segui, inverti, segui solo long, segui solo short, inverti solo long, inverti solo short); 17 sessioni (oro 3, argento 3, S&P 4, Nasdaq 4, DAX 3) | 204 |
| R4b | prima mezz'ora (o notte + prima mezz'ora) -> ultima mezz'ora / ultima ora della cash; segui/inverti; S&P, Nasdaq, DAX | 24 |
| R4c | sessione precedente -> successiva (Asia->Londra, Londra->NY, notte->cash), segui/inverti; oro 2, argento 2, S&P 3, Nasdaq 3, DAX 2 | 24 |
| R5 | giorno della settimana x sessione (UTC, cash, notte), long/short; 20 sessioni x 5 giorni x 2 | 200 |
| **totale** | | **732** |

Descrittive (non regole, non contano come prove): rendimento medio, deviazione
standard ed escursione per ora UTC e ora locale; griglia giorno x ora (conteggio
celle |t|>3 contro l'atteso per caso).

Placebo: per ogni variante con t >= 2 e per le prime 10 per t, 1000 serie con
direzione casuale sugli stessi istanti (seed fisso 20261002 + indice), p =
(1 + #placebo con netto medio >= reale) / 1001.

Nota d'esecuzione (fedele alla dichiarazione): la notte esce sul **primo
prezzo della cash** (apertura della candela delle 9:30/9:00), non sulla
chiusura della candela precedente; il segnale notte->cash entra quindi alla
candela successiva (9:35/9:05).

## ATTENZIONE — ora sbagliata nelle serie HistData (S&P, Nasdaq, argento, DAX)

Le etichette "UTC" delle serie HistData in `scoperta\` sono **1 ora in
ritardo quando New York e' in ora legale** (sono ora di New York + 5 h fisse).
Prove: senza correzione l'apertura cash S&P/Nasdaq cade alle 14:30 "UTC" sia
d'estate sia d'inverno; il picco d'apertura del DAX cade alle 09:00 "UTC" nelle
settimane in cui gli USA sono gia' in ora legale e l'Europa no (vero: 08:00);
il picco dei dati USA sull'argento non si sposta d'estate mentre quello
dell'oro (Dukascopy) si'. Dopo la correzione (`correggi_ora` nello script) i
picchi tornano dove devono (S&P/Nasdaq 9:30 New York, DAX 9:00 Berlino, argento
12:30 UTC d'estate) e la riapertura domenicale cade alle 22:00 UTC d'estate.
**Tutti i numeri sotto sono con la correzione.** Va corretta anche a monte
(`prepara_ricerca_zero.py` o la conversione HistData), e quasi certamente
riguarda anche `verifica\` e le altre famiglie.

## Risultato

- **732 varianti dichiarate**, 716 calcolabili (16 ore UTC senza dati: DAX
  di notte, ora 22 di S&P/Nasdaq).
- **Nessun candidato.** Nessuna variante arriva a t >= 3 sul netto; la migliore
  ha t = 2,40. Solo 1 variante su 716 ha t >= 2 e 64 hanno netto > 0.
- Sul **lordo** 40 varianti hanno |t| >= 3 (atteso per caso ~2): gli effetti
  d'orologio esistono, ma sono piu' piccoli del costo (prima previsione del
  protocollo confermata).

### Migliori 10 per t sul netto (nessuna passa)

| # | blocco | mercato | variante | n | netto | x costo | bp | t | anni + | p placebo |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | R4a | XAUUSD | Asia primi 60m -> resto, inverti solo long | 1199 | 0.346 | 0.86 | 2.7 | 2.40 | 7/9 | 0.001 |
| 2 | R3 | GRXEUR | notte long | 1798 | 2.797 | 1.86 | 3.2 | 1.84 | 7/8 | 0.005 |
| 3 | R4a | XAUUSD | Asia primi 30m -> resto, inverti solo long | 1222 | 0.280 | 0.70 | 2.5 | 1.83 | 6/9 | 0.001 |
| 4 | R5 | GRXEUR | notte g2 long | 365 | 5.034 | 3.36 | 6.5 | 1.80 | 7/8 | 0.014 |
| 5 | R5 | GRXEUR | Londra g2 long | 365 | 5.484 | 3.66 | 6.9 | 1.64 | 7/8 | 0.009 |
| 6 | R5 | XAUUSD | Londra g0 short | 464 | 0.488 | 1.22 | 3.6 | 1.64 | 5/9 | 0.003 |
| 7 | R5 | XAUUSD | NY g4 long | 454 | 0.892 | 2.23 | 6.9 | 1.60 | 6/9 | 0.016 |
| 8 | R4a | SPXUSD | NY primi 60m -> resto, inverti solo long | 811 | 0.678 | 1.23 | 4.0 | 1.59 | 6/8 | 0.005 |
| 9 | R4a | XAUUSD | Londra primi 30m -> resto, segui solo short | 1177 | 0.234 | 0.58 | 1.0 | 1.46 | 4/9 | 0.001 |
| 10 | R4a | GRXEUR | cash primi 30m -> resto, segui | 1790 | 2.653 | 1.77 | 3.4 | 1.35 | 5/8 | 0.017 |

g0 = lunedi' ... g4 = venerdi'. "x costo" = netto medio / costo round trip.
Il p del placebo e' piccolo anche dove t e' basso perche' il placebo a
direzione casuale paga il costo con lordo nullo: dice "c'e' un lordo", non
"c'e' un netto". Il filtro che taglia tutto e' t >= 3.

Specifica della prima (NON promossa, solo per memoria): oro, M5, sessione Asia
00:00-07:00 UTC; se la chiusura della candela 00:55 e' sotto l'apertura delle
00:00, long all'apertura delle 01:00, uscita alla chiusura della candela 06:55;
nessuno stop; costo 0,40 $.

### Notte contro giorno sugli indici (long, lordo per giorno, punti)

| mercato | notte lordo | t lordo | cash lordo | t lordo | notte netto (x costo) | anni + notte |
|---|---|---|---|---|---|---|
| S&P | +0,60 | 2,64 | +0,37 | 1,38 | +0,05 (0,08) | 4/8 |
| Nasdaq | +2,16 | 4,05 | +0,64 | 0,93 | +0,66 (0,44) | 6/8 |
| DAX | +4,30 | 2,82 | -0,77 | -0,37 | +2,80 (1,87) | 7/8 |

Il rendimento degli indici nel 2010-2017 sta quasi tutto **fuori** dalla
sessione cash (DAX: la cash e' negativa), ma con un'entrata e un'uscita al
giorno il costo se ne mangia la gran parte; il DAX notte e' il piu' vicino
(t 1,84) e resta lontano da 3.

## Osservazioni utili (non strategie)

1. **Volatilita' per ora** (escursione media H1, in multipli del costo):
   oro massima 12-15 UTC (6,3 $ = 16x costo; 13h e 14h = 22% della varianza
   giornaliera), minima alle 21 (1,7 $) e 3 UTC; argento uguale (13-15 UTC);
   S&P/Nasdaq picco nella mezz'ora 9:30 New York (M5 2,8x la mediana del
   giorno) e nell'ultima ora, minima 3-4 UTC (3x costo per S&P, 2,4x per
   Nasdaq: di notte il costo e' un terzo dell'escursione oraria); DAX picco
   9:00 Berlino e 15:30-16:30 (apertura USA), escursione oraria sempre >= 10x
   costo nelle ore di cash.
2. **Oro: sale in Asia, scende a Londra.** Lordo per giorno Asia +0,39 $
   (t 3,2), Londra -0,44 $ (t -3,5); 0 anni positivi su 9 per il long a
   Londra. Ma ogni lato vale circa un costo (0,40 $): netto ~0. Nella stessa
   linea, dopo una prima ora d'Asia negativa il resto dell'Asia sale (+0,75 $
   lordo, t lordo 5,2): e' il miglior effetto della famiglia, a 0,86 costi
   netti.
3. **Ore di riapertura (21-23 UTC) su oro e argento**: ora 21 fortemente
   negativa e 22-23 positive (|t| fino a 6,6 sul lordo), e la griglia giorno x
   ora trova 10 celle |t|>=3 sull'oro e 9 sull'argento (atteso 0,3), in gran
   parte in queste ore. E' quasi certamente l'**artefatto dei prezzi BID
   durante l'allargamento dello spread al rollover**, non un'opportunita':
   in quelle ore l'escursione e' 2-4 costi e lo spread reale e' massimo.
   Sugli indici e sul DAX la griglia giorno x ora e' compatibile col caso
   (0-2 celle).
4. **Persistenza intraday assente**: il segno della prima mezz'ora/ora non
   predice il resto della sessione su nessun mercato (|t lordo| <= 2,8 sui 34
   "segui"), e la prima mezz'ora (o notte + prima mezz'ora) non predice
   l'ultima mezz'ora/ora della cash su S&P, Nasdaq e DAX (|t| < 1,8). Nemmeno
   la sessione precedente predice la successiva (R4c, |t| < 1,5).

## Limiti

- DAX: i dati finiscono alle 21:00 UTC d'inverno e alle 20:00 d'estate, quindi
  la sessione NY 12-21 UTC del DAX e' misurabile solo d'inverno (n 741).
- S&P/Nasdaq hanno candele M5 rade di notte (HistData): entrata/uscita entro
  15 minuti dall'istante teorico, altrimenti il giorno salta.
- Nessuno stop, nessuno swap notturno (le regole notte pagherebbero lo swap:
  sarebbero ancora peggio).

## File

- `D:\ricerca_zero\risultati\f1_varianti.parquet` — 732 righe, tutte le varianti
- `f1_operazioni_t2.parquet` — operazioni delle varianti con t >= 2
- `f1_descrittive_ora.parquet`, `f1_escursione_ora_locale.parquet`,
  `f1_giorno_ora.parquet` — descrittive
