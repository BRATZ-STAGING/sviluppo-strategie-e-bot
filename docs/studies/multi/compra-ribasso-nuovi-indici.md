# "Compra il ribasso" su indici mai usati — test fuori campione (04/10/2026)

Registrazione VINCOLANTE: `docs/compra-ribasso-nuovi-indici-registrazione.md` (con
l'Emendamento 1; commit 769dfbf). Regola: M1 di `docs/multigiorno-paniere-candidati.md`,
INVARIATA. Script: `trading/scripts/compra_ribasso_nuovi.py` (importa
`multi_f2_ritorno.py` senza modificarlo: `prepara`, `segnali_mercato`, `operazioni`,
`misure`; si adattano solo la lettura dei dati e i globali del periodo, come in
`multi_verifica.py`). Dati: `D:\ricerca_multi\nuovi\PANIERE_D1.parquet`, `costi.csv`
(round trip 10 / 1,5 / 2,0 / 1,5 punti). Una sola esecuzione, nessun ritocco.

## Esito in breve

**NON PASSA, e non per poco: il portafoglio perde.** 550 operazioni in 15 anni, netto
-0,043 R per operazione (-23,5 R in totale), t mensile -1,08, 5 anni positivi su 16,
placebo p 0,58 (direzione) e 0,27 (date nello stesso stato). Il lato long e' circa zero
(+0,013 R, t 0,25); il lato short perde (-0,153 R, t -2,65). Su questi quattro indici,
comprare i ribassi sopra la media 200 non ha prodotto nulla: si salva solo il Nikkei long
(+0,122 R su 104, t 1,52, p direzione 0,007), ed e' un risultato su 12 righe guardate.

## Passo 1 — controllo del codice

M1 (MOSSA 5g 1,5 ATR, H5, stop, m200) sull'S&P della scoperta 2010-2017 con le funzioni
importate: **65 operazioni, netto +0,3960 R, t mensile 4,8530**, 7/7 anni, p 0,001 su
tutti e tre i placebo; operazioni uguali una per una a quelle salvate in
`f2_operazioni.parquet` (65/65, differenza 0, stesse uscite). Coincide: il test si apre.

## Passo 2 — test (entrate dal giorno dopo la 200a giornata valida -> 25/09/2026)

Giornate valide (Emendamento 1, M5 >= 80% della mediana del mercato; ricontrollato nello
script): Nikkei 3830/4093, FTSE 4002/4040, Euro Stoxx 2029/2065 (fino al 14/12/2018),
CAC 3902/4057. Prime entrate possibili: Euro Stoxx 08/2011, FTSE e CAC 09/2011, Nikkei
10/2011.

### Portafoglio dei 4 indici a rischio uguale (ipotesi primaria)

Mesi 2011-08 -> 2026-09 (182, mesi senza operazioni = 0); anni 2011-2026 (16; 2011 da
agosto e 2026 fino a settembre, parziali), soglia anni ceil(2/3 x 16) = 11.

| | portafoglio | criterio |
|---|---|---|
| n / op al mese | 550 / 3,02 (long 66%) | |
| netto medio R x1 / x1,5 | **-0,043 / -0,049** | > 0: **no / no** |
| netto totale R x1 / x1,5 | -23,5 / -27,0 | |
| lordo / swap / costo R per op | -0,011 / -0,019 / 0,013 | |
| **t mensile** (t sulle operazioni) | **-1,08** (-1,36) | >= 2: **no** |
| anni positivi (solo anni interi) | **5/16** (4/14) | >= 11: **no** |
| p direzione casuale | **0,578** | < 0,05: **no** |
| p date casuali nello stesso stato m200 | **0,272** | < 0,05: **no** |
| p date casuali senza stato (riferimento) | 0,719 | |
| netto medio R del placebo a date nello stato | -0,061 | |
| stop presi | 19% (scoperta S&P: 5%) | |
| drawdown R | 37,5 | |
| peggiore operazione R | -1,41 (CAC long) | |
| **verdetto** | **NON PASSA** (tutti e sei i punti mancati) | |

### Per indice e per lato (senza verdetto)

| | n | op/mese | netto R x1 / x1,5 | totale R | t mens | anni + | p dir | p date stato | dd R | peggiore R |
|---|---|---|---|---|---|---|---|---|---|---|
| portafoglio long | 366 | 2,01 | +0,013 / +0,006 | +4,6 | 0,25 | 6/16 | 0,123 | 0,137 | 16,3 | -1,41 |
| portafoglio short | 184 | 1,01 | -0,153 / -0,159 | -28,2 | -2,65 | 2/16 | 0,994 | 0,714 | 30,9 | -1,09 |
| Nikkei | 157 | 0,87 | +0,051 / +0,044 | +8,0 | 0,85 | 8/16 | 0,050 | 0,064 | 5,7 | -1,09 |
| Nikkei long | 104 | 0,58 | +0,122 / +0,115 | +12,7 | 1,52 | 7/16 | 0,007 | 0,074 | 5,0 | -1,08 |
| Nikkei short | 53 | 0,29 | -0,088 / -0,095 | -4,7 | -1,01 | 6/16 | 0,746 | 0,239 | 5,7 | -1,09 |
| FTSE | 146 | 0,81 | -0,074 / -0,078 | -10,8 | -1,20 | 6/16 | 0,747 | 0,425 | 17,6 | -1,06 |
| FTSE long | 102 | 0,56 | -0,030 / -0,035 | -3,0 | -0,39 | 5/16 | 0,400 | 0,342 | 10,8 | -1,06 |
| FTSE short | 44 | 0,24 | -0,175 / -0,179 | -7,7 | -1,83 | 3/16 | 0,981 | 0,564 | 8,4 | -1,04 |
| Euro Stoxx (2011-2018) | 82 | 0,92 | -0,147 / -0,158 | -12,1 | -1,99 | 2/8 | 0,868 | 0,808 | 13,4 | -1,08 |
| Euro Stoxx long | 48 | 0,54 | -0,123 / -0,135 | -5,9 | -1,24 | 2/8 | 0,708 | 0,686 | 7,5 | -1,08 |
| Euro Stoxx short | 34 | 0,38 | -0,182 / -0,191 | -6,2 | -1,74 | 1/8 | 0,863 | 0,773 | 6,9 | -1,06 |
| CAC | 165 | 0,91 | -0,053 / -0,058 | -8,7 | -0,95 | 6/16 | 0,713 | 0,544 | 11,9 | -1,41 |
| CAC long | 112 | 0,62 | +0,008 / +0,002 | +0,9 | 0,11 | 7/16 | 0,421 | 0,309 | 4,6 | -1,41 |
| CAC short | 53 | 0,29 | -0,182 / -0,185 | -9,6 | -2,41 | 2/16 | 0,965 | 0,817 | 10,3 | -1,04 |

Swap -0,016/-0,026 R e costo 0,009/0,021 R per operazione (Euro Stoxx il piu' caro): x1,5
cambia il netto di 0,004-0,011 R. Il lordo e' gia' negativo per FTSE, Euro Stoxx e CAC.

### R netti per anno di uscita

| | 2011* | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **portafoglio** | +1,9 | -3,4 | +6,2 | -6,2 | -1,1 | -4,7 | +6,1 | **-17,3** | -5,2 | -1,6 | +9,6 | -2,7 | -6,6 | -2,4 | +5,0 | -1,3 |
| long | 0,0 | +1,0 | +6,5 | -3,8 | +1,8 | -2,8 | +6,1 | -8,6 | -1,9 | -1,2 | +10,2 | -5,0 | -4,2 | -0,2 | +7,8 | -1,1 |
| short | +1,9 | -4,4 | -0,4 | -2,4 | -2,9 | -1,9 | 0,0 | -8,7 | -3,3 | -0,4 | -0,6 | +2,3 | -2,4 | -2,2 | -2,8 | -0,2 |
| Nikkei | +0,6 | -4,0 | +7,2 | -2,6 | +1,9 | -0,8 | +5,0 | -2,4 | -1,8 | +0,8 | +1,9 | -1,2 | -0,8 | -1,5 | +3,8 | +1,8 |
| FTSE | +0,2 | +1,6 | -0,0 | -2,2 | +0,7 | -0,6 | -0,5 | -5,1 | -1,9 | -1,2 | +4,6 | -1,5 | -5,6 | -0,3 | +0,4 | +0,7 |
| Euro Stoxx | +0,6 | -0,6 | -1,7 | -2,4 | -1,6 | -1,9 | +1,5 | -5,9 | | | | | | | | |
| CAC | +0,5 | -0,4 | +0,7 | +0,9 | -2,1 | -1,4 | +0,2 | -3,9 | -1,5 | -1,1 | +3,2 | -0,0 | -0,2 | -0,6 | +0,8 | -3,8 |

\* parziale (2011 da agosto-ottobre secondo l'indice; 2026 fino al 25/09). Mesi peggiori del
portafoglio: 10/2014 -5,6, 06/2013 -5,5, 04/2018 -5,2, 02/2018 -4,9, 04/2025 -3,8 R.

### Osservazioni

1. **Il fenomeno non si trasferisce.** Sull'S&P la stessa regola faceva +0,40 R in scoperta e
   +0,14 in verifica; qui il long sui quattro indici fa +0,013 R, appena sopra il placebo a
   date casuali nello stesso stato (-0,030 R per un long a caso sopra la media 200, che paga
   swap, costo e stop). Il lato short (sotto la media 200) perde ovunque, 2 anni positivi su 16.
2. **Il 2018 e' di nuovo l'anno peggiore** (-17,3 R, entrambi i lati, tutti e quattro gli
   indici), come per M1-M3 nella verifica sull'S&P.
3. **Il Nikkei long e' l'unica riga positiva sensata** (+0,122 R, t 1,52, p direzione 0,007 ma
   p date nello stato 0,074): da solo non dimostra nulla (una riga su 12, senza verdetto per
   registrazione), e il portafoglio, che era l'unica ipotesi, e' negativo.
4. Lo stop a 2 x ATR20 entra nel 19% delle operazioni (18-21% su ogni indice; S&P scoperta 5%,
   verifica 23,5%): i ribassi comprati proseguono spesso.

## Previsioni della registrazione

1. "Il lato long e' positivo su almeno 3 indici su 4": **sbagliata** — positivo su 2 (Nikkei
   +0,122, CAC +0,008, quasi zero); FTSE -0,030, Euro Stoxx -0,123.
2. "Il portafoglio NON arriva a t 2": **confermata**, ma per una ragione diversa da quella
   attesa: non per poche operazioni (sono 3 al mese) ma perche' il netto e' negativo (t -1,08).

## Scelte interpretative

- **Inizio del periodo**: per ogni indice le entrate partono dal giorno dopo la 200a giornata
  valida (prima la media 200 non esiste e il codice non da' segnali). Mesi per il t: dal primo
  mese con entrate possibili del portafoglio (2011-08) a 2026-09; per indice, dal suo primo
  mese all'ultimo dei suoi dati (Euro Stoxx 2011-08 -> 2018-12). Con la convenzione della
  scoperta (mesi dal primo ATR20, 2010-12) il t del portafoglio non cambia (-1,077).
- **Anni**: per data di uscita; contati tutti, compresi i parziali 2011 e 2026 (anno senza
  operazioni = non positivo), soglia ceil(2/3 x anni). Il conteggio sui soli anni interi e'
  riportato e non cambia nulla.
- **Portafoglio a rischio uguale** = somma in R delle operazioni dei 4 indici (1R per
  operazione ovunque); dal 2019 e' di tre indici (Euro Stoxx finito il 14/12/2018).
- **Placebo**: 1000 serie, seed 12345, un solo generatore (indici nell'ordine Nikkei, FTSE,
  Euro Stoxx, CAC); per ogni operazione si estrae un valore e il placebo di un sottoinsieme
  (portafoglio, indice, lato) e' la somma delle sue colonne. Direzione: stesse operazioni,
  direzione casuale. **Date (criterio, come da registrazione)**: stessa direzione, data
  d'entrata casuale fra le entrate possibili dello stesso indice la cui giornata di segnale
  e' nello stesso stato (sopra la media 200 per i long, sotto per gli short), stessa tenuta e
  stop. Le date casuali senza stato (fra le entrate dopo la 200a giornata) sono solo
  riferimento. Statistica: netto totale R a costi x1; p = (1 + #placebo >= reale)/1001.
- **Costi** in punti di indice di `nuovi/costi.csv`, x1,5 = netto - 0,5 x costo; swap 3%/365
  del prezzo d'entrata per notte, long e short, mercoledi' x3 (codice di scoperta).
- Mediana delle M5 dell'Euro Stoxx nel file (2010 -> 14/12/2018): 165, non ~124 come scritto
  nell'Emendamento (il valore citato li' includeva probabilmente il tratto 2019 non valido);
  la regola dell'emendamento (80% della mediana del mercato) e' applicata cosi' come scritta e
  ricontrollata nello script.

## File

`D:\ricerca_multi\risultati\`: `nuovi_operazioni.parquet` (una riga per operazione: indice,
direzione, date di segnale/entrata/uscita, prezzo d'entrata, 1R in punti, lordo/swap/costo/
netto, netto x1,5, esito opposto), `nuovi_riepilogo.parquet` (portafoglio, lati, indici e
indice x lato con tutte le misure e i p; verdetto sulla riga del portafoglio),
`nuovi_anni.parquet` (R per anno), `nuovi_mensili.parquet` (R mensili del portafoglio).
