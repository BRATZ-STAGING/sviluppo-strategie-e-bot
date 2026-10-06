# Oro con i costi veri FP Raw — F3 range, F4 volatilita', crollo -> conferma intraday (scoperta 2009-2017)

Registrazione VINCOLANTE: `docs/costi-fp-raw-oro-registrazione.md` (commit
4e59d3f). Script: `trading/scripts/oro_fp_f3f4c.py` (importa le funzioni di
`zero_f3_range.py`, `zero_f4_volatilita.py`, `crollo_conferma_scoperta.py` e
`framework/crollo_conferma.py`, che NON sono stati modificati; cambia solo il
costo dell'oro). Esecuzione: `python oro_fp_f3f4c.py f3|f4|crollo|sintesi`
(40 s, 10 s, 57 s). Dettaglio in `D:\ricerca_oro_fp\risultati\`.

Dati: solo `D:\ricerca_zero\scoperta\XAUUSD_M5|M15|H1|D1.parquet` e le M1
2009-2017 (tramite la cache VWAP del crollo, costruita da quegli anni).
Nessuna cartella di verifica aperta, nessun anno >= 2018 caricato.

## Scelte (dichiarate)

- Scenari: **vecchio** (F3/F4 0,40 $; crollo 0,46 $, x1,5 = 0,69 $),
  **0,20 $** (base) e **0,30 $** (prova di resistenza; per il crollo e'
  esattamente il suo "x1,5" del costo base).
- Il filtro "rischio < 2 x costo" usa il costo dello scenario base: 0,40/0,46
  nel vecchio, **0,20 per entrambi i nuovi** (stesse operazioni a 0,20 e 0,30,
  come il crollo originale che filtrava col costo x1). Sull'oro conta poco
  (rischi tipici 3-15 $); cambia n solo in poche varianti F3 a range stretto.
- Placebo e semi identici: F3 seed 12345 per variante; F4 un generatore
  seed 12345 consumato nello stesso ordine dell'originale (uno per scenario);
  crollo seed 12345 + indice del gruppo (l'intraday viene per primo, quindi gli
  indici coincidono con l'originale).
- Promozione F3/F4: netto > 0 a 0,20 **e** 0,30; t >= 3, anni >= 75%, p
  placebo < 0,01, n >= 100 misurati a 0,20. Crollo: i criteri della sua
  registrazione con costo x1 = 0,20 e x1,5 = 0,30 (netto > 0 in R e $ con
  entrambi, t = min(t operazioni, t mensile) >= 3, anni >= 7/9, p < 0,01,
  meglio del riferimento "senza conferma").
- Esclusioni: **H4** = F4 `c|XAUUSD/22-22|CMP|S2|X1`. H2 (venerdi', F5) e
  H3 (notte asiatica, F1) non hanno varianti identiche in F3, F4 o crollo.

## Riproduzione con il costo originale

| famiglia | varianti oro | confronto con | scarto massimo (n, netto, t, anni, p) |
|---|---|---|---|
| F3 | 432 | `D:\ricerca_zero\risultati\f3_varianti.parquet` | 0 |
| F4 | 104 | `D:\ricerca_zero\risultati\f4_varianti.parquet` | 0 |
| crollo intraday | 336 + 48 rif. | `D:\ricerca_conferme\risultati\varianti.parquet` | 0 |

Coincide anche con le righe oro dei rapporti (es. F3 Asia>Londra TS K25 E2
piccolo n 683, 0,053 R, t 1,65; F4 CMP S2 X1 n 434, t 2,67; crollo M15 k1,5
C3c 1R short n 32, t 2,05). Controllo fusi F3: picco 13:30/12:30 UTC; M15/H1
costruite dalle M5 = Parquet (scarto 0).

## Conteggi (netto medio per operazione > 0)

| famiglia | varianti | vecchio | 0,20 $ | 0,30 $ | > 0 a 0,20 e 0,30 | t >= 3 a 0,20 | promosse |
|---|---|---|---|---|---|---|---|
| F3 range | 432 | 23 | 76 | 48 | 48 | 1 | **1** |
| F4 volatilita' | 104 | 76 | 78 | 77 | 77 | 1 (H4) | **0** (H4 esclusa) |
| crollo intraday | 336 | 26 | 46 | 38 | 38 (R e $) | 0 | **0** |

t medio delle varianti: F3 -4,29 -> -2,23 (0,20) -> -3,48 (0,30); F4 0,44 ->
0,72 -> 0,57; crollo -2,05 -> -1,41. Il costo piu' basso sposta poco: le
regole oro con rischi di 3-15 $ pagavano gia' solo 2-10% del rischio.

## F3 — migliori 10 per t a 0,20 $

Netto in R per operazione; lordo in $/oncia per operazione.

| variante | n | lordo $ | R vecchio | R 0,20 | R 0,30 | t vecchio | t 0,20 | t 0,30 | anni + (0,20) | p |
|---|---|---|---|---|---|---|---|---|---|---|
| b Asia>Londra TS K25 E2 piccolo | 683 | 0,685 | 0,053 | 0,098 | 0,075 | 1,65 | **3,06** | 2,36 | 8/9 | 0,001 |
| b Asia>Londra TS K25 E1 piccolo | 683 | 0,625 | 0,032 | 0,077 | 0,055 | 1,17 | 2,80 | 1,98 | 7/9 | 0,001 |
| b Asia>Londra CS K25 E1 piccolo | 610 | 0,659 | 0,034 | 0,079 | 0,056 | 1,17 | 2,72 | 1,95 | 7/9 | 0,001 |
| b Londra>NY TR K25 E1 grande | 993 | 0,588 | 0,034 | 0,080 | 0,057 | 1,14 | 2,72 | 1,93 | 8/9 | 0,001 |
| b Asia>Londra CS K25 E2 piccolo | 610 | 0,642 | 0,039 | 0,084 | 0,062 | 1,20 | 2,56 | 1,88 | 7/9 | 0,001 |
| b Asia>Londra TS K25 E0 piccolo | 683 | 0,611 | 0,034 | 0,079 | 0,057 | 1,09 | 2,51 | 1,80 | 7/9 | 0,001 |
| b Londra>NY TS K10 E0 piccolo | 979 | 0,528 | 0,114 | 0,226 | 0,170 | 1,16 | 2,31 | 1,74 | 9/9 | 0,160 |
| b Asia>Londra CS K25 E0 piccolo | 610 | 0,609 | 0,030 | 0,075 | 0,052 | 0,91 | 2,28 | 1,60 | 7/9 | 0,001 |
| b Londra>NY CS K10 E0 piccolo | 875 | 0,546 | 0,110 | 0,223 | 0,166 | 1,10 | 2,24 | 1,67 | 8/9 | 0,036 |
| b Londra>NY TR K25 E2 grande | 993 | 0,593 | 0,034 | 0,080 | 0,057 | 0,87 | 2,09 | 1,48 | 7/9 | 0,001 |

Il range di apertura di Londra (parte a), che la registrazione indicava come
il posto piu' probabile, **non** arriva: rottura OR15 stop altro lato fine
sessione lordo +0,289 $ (0,145 R, n 2.303) ma netto 0,032 R a 0,20 (t 0,81) e
-0,025 R a 0,30, 4/9 anni; il rischio (meta' del range dei primi 15', ~2 $) e'
troppo piccolo. Parte a: varianti positive 2 (vecchio) / 18 (0,20) / 8 (0,30),
nessuna con t > 2. Il "respingimento" del max/min di Londra a New York (TR/FR
K25 E0 tutti) passa da netto ~0 a +0,04 R a 0,20, ma t 1,4-1,5.

## F4 — migliori 10 per t a 0,20 $

| variante | n | lordo $ | R vecchio | R 0,20 | R 0,30 | t vecchio | t 0,20 | t 0,30 | anni + (0,20) | p |
|---|---|---|---|---|---|---|---|---|---|---|
| c CMP S2 X1 (**= H4, esclusa**) | 435 | 1,564 | 0,196 | 0,222 | 0,207 | 2,67 | 3,01 | 2,82 | 8/9 | 0,002 |
| a R50 S2 X1T2 | 156 | 1,595 | 0,278 | 0,318 | 0,295 | 2,46 | 2,82 | 2,62 | 9/9 | 0,009 |
| a R50 S2 X1 | 156 | 2,426 | 0,464 | 0,482 | 0,459 | 2,61 | 2,73 | 2,60 | 8/9 | 0,029 |
| a R75 S2 X1 | 693 | 1,030 | 0,122 | 0,150 | 0,133 | 2,10 | 2,60 | 2,31 | 7/9 | 0,015 |
| a R75 S2 X1T2 | 693 | 0,863 | 0,084 | 0,117 | 0,100 | 1,82 | 2,54 | 2,17 | 7/9 | 0,002 |
| c CMP S2 X3 | 294 | 2,798 | 0,305 | 0,330 | 0,314 | 2,27 | 2,45 | 2,34 | 7/9 | 0,068 |
| c CMP S1 X1 | 435 | 1,535 | 0,085 | 0,101 | 0,093 | 2,05 | 2,42 | 2,24 | 8/9 | 0,007 |
| a R75 S1 X1 | 693 | 1,082 | 0,063 | 0,081 | 0,072 | 1,86 | 2,39 | 2,12 | 7/9 | 0,015 |
| a R75 S2 X3 | 550 | 1,676 | 0,213 | 0,244 | 0,227 | 2,08 | 2,38 | 2,22 | 7/9 | 0,052 |
| a R75 S1 X1T2 | 693 | 1,011 | 0,055 | 0,073 | 0,064 | 1,74 | 2,32 | 2,03 | 7/9 | 0,014 |

Tutte rotture del giorno prima sull'oro (giornata 22-22). Solo H4 supera t 3
(a 0,20; 2,82 a 0,30) e passerebbe tutti i criteri, ma e' esclusa per
registrazione. La seconda (R50 S2 X1T2) si ferma a t 2,82 con 156 operazioni.

## Crollo -> conferma intraday — migliori 10 per t a 0,20 $

t = min(t operazioni, t mensile); lordo in $ per operazione; 1R mediano in $.

| TF | k | conf. | obiettivo | lato | n | lordo $ | 1R $ | R vecchio | R 0,20 | R 0,30 | t vecchio | t op | t mese | anni+ | p | R rif. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M15 | 1,5 | C3c | 2R | short | 32 | 7,10 | 15,9 | 0,255 | 0,270 | 0,264 | 2,05 | 2,18 | 2,19 | 6 | 0,011 | -0,071 |
| M15 | 1,5 | C3c | 1R | short | 32 | 6,21 | 15,9 | 0,241 | 0,257 | 0,251 | 2,05 | 2,83 | 2,17 | 6 | 0,003 | -0,060 |
| M15 | 1,5 | C3c | H | short | 33 | 4,93 | 16,5 | 0,191 | 0,207 | 0,201 | 1,99 | 2,73 | 2,12 | 7 | 0,002 | 0,008 |
| M15 | 1,5 | C3c | 3R | short | 31 | 6,51 | 15,3 | 0,231 | 0,247 | 0,241 | 1,72 | 1,85 | 2,33 | 6 | 0,037 | -0,059 |
| H1 | 1,5 | C3b | 1R | short | 52 | 2,38 | 13,2 | 0,077 | 0,097 | 0,089 | 1,07 | 1,36 | 1,69 | 7 | 0,080 | -0,060 |
| H1 | 1,5 | C3b | 3R | short | 52 | 2,09 | 13,2 | 0,052 | 0,072 | 0,064 | 0,74 | 1,03 | 1,28 | 7 | 0,031 | -0,102 |
| H1 | 1,5 | C3b | 2R | short | 52 | 2,09 | 13,2 | 0,052 | 0,072 | 0,064 | 0,74 | 1,03 | 1,28 | 7 | 0,031 | -0,064 |
| H1 | 1,5 | C3c | 2R | short | 23 | 3,92 | 19,9 | 0,139 | 0,153 | 0,147 | 0,89 | 0,98 | 1,00 | 4 | 0,169 | -0,064 |
| H1 | 1,5 | C3b | H | short | 52 | 1,63 | 13,2 | 0,038 | 0,059 | 0,051 | 0,57 | 0,87 | 1,09 | 6 | 0,052 | -0,086 |
| H1 | 0,75 | C2 | H | long | 97 | 1,08 | 10,6 | 0,047 | 0,071 | 0,062 | 0,52 | 0,81 | 0,80 | 5 | 0,364 | -0,095 |

Con 1R di 10-20 $ il costo pesava gia' solo 2-4% del rischio: scendere da
0,46 a 0,20 $ aggiunge ~0,02 R per operazione. Criteri a 0,20/0,30: t >= 3
**0**, anni >= 7/9 5, p < 0,01 2, meglio del riferimento 144; tutti 0.

## Previsioni della registrazione (parte F3)

1. "Con 0,20 $ compaiono candidati ... nel range di apertura di Londra (F3)":
   **falsa nella forma**: compare un candidato F3, ma sui livelli della
   sessione asiatica toccati a Londra (parte b), non sul range di apertura
   (parte a, t massimo < 2).
2. "Meno della meta' dei candidati regge a 0,30 $": il candidato ha netto > 0
   a 0,30 (richiesto), ma t scende da 3,06 a 2,36.

## Candidati

**Uno** (F3), nessuno in F4 (H4 esclusa) e nel crollo intraday. Non e' stato
verificato. E' il migliore di 432 varianti F3 oro con t appena sopra la
soglia (3,06), circondato da parenti a t 2,5-2,8 (stessa idea, uscite e
regola d'entrata vicine): e' un'idea coerente, non un punto isolato, ma resta
al margine. Lordo concentrato sul lato short (1,00 $ contro 0,41 $ del long);
2015 negativo, 2010 a zero.

### F3-ORO-1 — tocco del massimo/minimo asiatico a Londra, segui, regime "giorno prima stretto"

Variante `b|XAUUSD|ASIA>LON|TS|K25|E2|piccolo`; codice = `zero_f3_range.py`
(`studia`, parte b, combinazione `ASIA>LON`, regola `TS`, stop `K25`, uscita
`E2`, regime `piccolo`) con costo 0,20 $ (0,30 $ di resistenza), invariato.

- **Dati**: M5 oro, UTC, etichettate all'apertura.
- **Giornate e ATR14**: giorni UTC costruiti dalle M5, validi se hanno almeno
  il 50% delle M5 della mediana; TR con la chiusura del giorno valido
  precedente; ATR14 = media dei TR dei 14 giorni validi fino al giorno valido
  **precedente** la sessione (incluso), quindi noto prima delle 00:00.
- **Livelli**: AH/AL = massimo/minimo delle M5 con apertura in [00:00, 07:00)
  UTC dello stesso giorno (sessione valida se la prima M5 e' entro 15' dalle
  00:00 e ci sono almeno 42 M5).
- **Finestra**: Londra [07:00, 12:00) UTC (valida se la prima M5 e' entro 15'
  dalle 07:00 e ci sono almeno 30 M5); a = prima M5 della finestra.
- **Regime "piccolo"**: x = range del giorno UTC valido precedente / ATR14
  (lo stesso giorno incluso); x <= terzile basso dei 250 valori precedenti
  della serie per sessione (minimo 60 valori); altrimenti nessuna operazione.
- **Segnale**: si cercano le M5 con apertura in [a, 11:00) UTC.
  Lato long solo se l'apertura di a e' < AH: prima M5 con massimo >= AH ->
  **long**. Lato short solo se l'apertura di a e' > AL: prima M5 con minimo
  <= AL -> **short**. I due lati sono indipendenti (si possono avere due
  operazioni nella stessa sessione, 47 casi su 683 operazioni).
- **Entrata**: apertura della M5 successiva alla candela del tocco (se e'
  ancora dentro la finestra).
- **Stop**: 0,25 x ATR14 dall'entrata (1R). **Obiettivo**: 2R dall'entrata.
  **Uscita forzata**: chiusura dell'ultima M5 della finestra (11:55-12:00).
  Stop e obiettivo nella stessa M5 -> vale lo stop; apertura oltre lo stop
  o l'obiettivo -> uscita all'apertura.
- **Scarto**: rischio < 2 x 0,20 $ (mai attivo: 1R da 3,1 a 7,3 $, 10°-90°
  percentile, mediana 4,38 $).
- **Costi**: 0,20 $ round trip (base), 0,30 $ (resistenza); niente swap
  (posizione chiusa alle 12:00).
- **Statistiche**: t sul netto in R delle operazioni; anni positivi su anni
  con operazioni; placebo = stesse entrate con direzione casuale per
  operazione (gestione speculare), 1000 serie, seed 12345,
  p = (1 + #medie placebo >= reale) / 1001.

Numeri di scoperta 2009-2017:

| costo | n | lordo $/op | lordo R | netto R/op | netto / costo | t | anni + | p | vinte |
|---|---|---|---|---|---|---|---|---|---|
| 0,40 (vecchio) | 683 | 0,685 | 0,143 | 0,053 | 0,71 | 1,65 | 7/9 | 0,001 | 49,6% |
| **0,20** | 683 | 0,685 | 0,143 | **0,098** | 2,43 | **3,06** | **8/9** | **0,001** | 52,1% |
| 0,30 | 683 | 0,685 | 0,143 | 0,075 | 1,28 | 2,36 | 7/9 | 0,001 | 50,8% |

t lordo 4,47; t per sessione (somma delle operazioni dello stesso giorno)
3,11 a 0,20. Netto R a 0,20 per anno: 2009 +0,31, 2010 +0,01, 2011 +0,08,
2012 +0,07, 2013 +0,22, 2014 +0,17, 2015 -0,09, 2016 +0,10, 2017 +0,13.

**Verifica** (non eseguita): oro 2018 -> 07/2026, una volta sola, con la
soglia di t della registrazione per il numero TOTALE di candidati di tutte le
famiglie rifatte (2 se resta l'unico; 2,4 con 2-3), netto > 0 a 0,20 e 0,30,
anni >= 2/3, placebo come in scoperta.
