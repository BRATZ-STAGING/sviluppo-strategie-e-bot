# Gestione B sui diciotto anni, prima della demo (03/10/2026)

Punto 2 di `docs/esperimento-b-registrazione.md`. Nessuna regola nuova: stesse
operazioni di `verifica_bot.py` (genera + filtra + cammina), gestione B
(1:8, trailing MFE-2R da +3R, weekend solo sopra +1R), spread vero per anno
(0,40 $ prima del 2020). Archivio M1 2009-01-01 -> 2026-07-06 caricato intero.

Script: `trading/scripts/analisi_b_18anni.py` (2 min 35 s).
Dettaglio: `docs/studies/dati/b_operazioni_2009_2026.parquet` (712 operazioni)
e `..._spegnimento.parquet` (204 partenze simulate).

## 1. Per anno (R)

| 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 |
|---|---|---|---|---|---|---|---|---|---|---|
| -12,9 | -20,2 | +10,2 | -25,4 | -8,5 | -11,1 | -5,3 | -5,8 | -3,6 | -3,3 | -5,5 |

| 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 (6 mesi) |
|---|---|---|---|---|---|---|
| +28,9 | +19,7 | +28,1 | +10,3 | +21,9 | +50,5 | +14,8 |

## 2. Periodi

| periodo | spread | op | R | R/op | vinte | DD max | giorni sotto il massimo (max) | perdite di fila | anni + |
|---|---|---|---|---|---|---|---|---|---|
| 2009-2019 | vero | 374 | **-91,4** | -0,24 | 23,0% | **90,3** | 3.968 | **21** (-23,2 R) | **1/11** |
| 2009-2019 | 0,30 | 374 | -77,6 | -0,21 | 23,3% | 76,6 | 3.968 | 21 | 1/11 |
| 2020-2026 | vero | 338 | +174,3 | +0,52 | 37,3% | 13,1 | 309 | 12 | 7/7 |
| 2009-2026 | vero | 712 | +82,9 | +0,12 | 29,8% | 90,3 | 5.526 | 21 | 8/18 |

**Perche' i documenti davano 87,4 e 89,8 R.** Sono misure dello stesso
drawdown prese in momenti diversi del progetto: cambiano lo spread usato
(0,30 contro quello vero) e il campione (382 operazioni prima della correzione
delle domeniche dell'appendice BD, 374 dopo). Con le regole e lo spread di
oggi il numero e' **90,3 R** (76,6 R con lo spread a 0,30).

## 3. La discesa: una sola, lunga quindici anni

| inizio | fondo | recupero | R | operazioni | giorni |
|---|---|---|---|---|---|
| 13/01/2009 | 25/11/2019 | **01/03/2024** | **90,3** | 556 | 5.526 |
| 28/01/2026 | 09/06/2026 | 24/06/2026 | 12,6 | 14 | 146 |
| 11/04/2025 | 12/08/2025 | 03/09/2025 | 9,9 | 17 | 145 |

Chi avesse cominciato nel gennaio 2009 sarebbe tornato in pari nel **marzo
2024**. Allo 0,24% per operazione il fondo vale -21,7% del conto.

## 4. Lo spegnimento a -15 R

Partenza simulata il primo di ogni mese; stop quando il calo dal massimo
raggiunto dopo la partenza tocca 15 R.

| partenze | quante | lo stop scatta | mesi mediani prima dello stop | R allo stop (mediana / peggiore) |
|---|---|---|---|---|
| 2009-2019 | 132 | **126 (95%)** | 10,8 | -10,5 / -16,2 |
| 2020-2025 | 72 | **0** | — | — |

Allo 0,24% per operazione, lo stop costa in mediana il **2,5%** del conto
(peggiore 3,9%). Nel periodo buono non sarebbe mai scattato (la discesa
peggiore, 12,6 R nel 2026, resta sotto la soglia). Esempi: partenza 01/01/2009
-> stop 07/10/2009 dopo 19 operazioni a -15,6 R; partenza 01/01/2018 -> stop
12/11/2019 a -7,6 R; partenza 01/01/2020 -> mai.

## Cosa dice

1. La B **non ha un anno cattivo isolato**: ha un'epoca. Dal 2009 al 2019 un
   solo anno positivo su undici.
2. Lo spegnimento a -15 R fa quello che deve: separa le due epoche quasi
   perfettamente (95% contro 0%) e limita il danno a ~2,5% del conto. Il suo
   costo e' l'altra faccia: chi si fosse fermato nel 2009-2019 non sarebbe
   stato dentro quando la strategia ha ripreso a funzionare nel 2020.
3. In demo il rischio e' zero; il numero da tenere a mente per un eventuale
   conto vero e' il -2,5% / -3,9% dello stop, non il -21,7% della discesa
   intera.

Nessuna conclusione di validita': e' una descrizione della strategia gia'
nota, misurata con le regole di oggi.
