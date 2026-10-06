# Crollo -> conferma -> entrata, SWING v2 (stop S1, S2, S3 senza tetto) — scoperta 2009-2017

Protocollo VINCOLANTE: `docs/crollo-conferma-swing-v2-registrazione.md`
(commit bf9a30b); il resto come la v1 (`docs/crollo-conferma-registrazione.md`,
interpretazioni 1-19 in `docs/studies/conferme/scoperta.md`, invariate).
Motore: `trading/framework/crollo_conferma.py` (nuovo parametro `stop` di
`operazioni`, default "v1" = comportamento della v1); test:
`trading/tests/test_crollo_conferma.py` (23 della v1 + 22 nuovi, 45/45);
script: `trading/scripts/crollo_conferma_swing_v2.py` (circa 25 s).
Dettaglio in `D:\ricerca_conferme\risultati\v2_operazioni.parquet`,
`v2_varianti.parquet`, `v2_verifica_motore.parquet`, `v2_controlli.parquet`.

Dati: solo `D:\ricerca_zero\scoperta\XAUUSD_M5|D1.parquet` e il VWAP dalle
M1 2009-2017 (cache della v1). **Nessun dato di verifica aperto.**

**Esito: 0 candidati su 1.008 varianti.** Nessuna arriva a t 3 (massimo
2,60, con 26 operazioni); nessuna variante con almeno 40 operazioni arriva a
t 2. La verifica 2018 -> 07/2026 e il trasferimento su argento, S&P 500 ed
EUR/USD **non si eseguono**.

## Interpretazioni aggiunte (oltre alle 19 della v1)

20. **S2**: "ultimo minimo frattale confermato dopo L e sopra L" = l'ultimo
    frattale basso (2 barre per lato) **noto alla chiusura della barra di
    conferma** (f + 2 <= conferma), con f dopo la barra di L e minimo > L;
    se l'ultimo noto e' prima di L, non esiste -> stop come S1. Per il
    riferimento senza conferma lo stesso, alla barra del fronte del crollo.
21. **S3**: stop = entrata -/+ 1,5 x ATR20 noto all'apertura della barra
    d'entrata (lo stesso ATR della v1).
22. S1, S2, S3 scartano solo se 1R < 2 x 0,46 $ (o entrata gia' oltre lo
    stop). Gli obiettivi 1R/2R/3R seguono il 1R dello stop scelto; "H" no.
23. **Meta' positive** = netto totale > 0 **in R e in $** (x1) sia nel
    2009-2012 sia nel 2013-2017.
24. Riferimenti senza conferma: uno per stop (2 TF x 3 k x 3 stop x 4
    obiettivi x 2 lati = 144), confrontati con le varianti dello stesso stop.
    Placebo: 2.000 serie, seed 12345 + indice della variante (come la v1).

## Controlli

| controllo | esito |
|---|---|
| test pytest del modulo (23 v1 invariati + S2 sul minimo crescente noto, S2 senza frattale = S1, S1 senza tetto / v1 con tetto, short = specchio del long per S1-S3 su 5 conferme, minimo crescente senza lookahead) | 45/45 |
| stop "v1" del motore nuovo = conteggi della v1 pubblicata (216 righe swing) | identici |
| troncamento sui dati veri (C1, C2, C5, senza conferma; H4/D1; 2 lati): segnali e minimo crescente prima del taglio | 16/16, 1.128 segnali |
| 300 operazioni rifatte con il ciclo barra per barra | differenza 0,00 $, 0 barre |

## Operazioni per variante (previsione 1: 50-150)

| TF | stop | mediana | min | max | quota 50-150 | quota >= 40 |
|---|---|---|---|---|---|---|
| D1 | S1 | 37 | 7 | 150 | 32% | 45% |
| D1 | S2 | 37,5 | 7 | 150 | 32% | 46% |
| D1 | S3 | 37,5 | 7 | 138 | 35% | 45% |
| H4 | S1 | 84,5 | 12 | 247 | 52% | 83% |
| H4 | S2 | 92,5 | 12 | 262 | 49% | 83% |
| H4 | S3 | 85,5 | 12 | 172 | 61% | 83% |

Tutte 1.008 hanno operazioni (v1: 72 su 336 swing senza nessuna); mediana
51, 43% nell'intervallo 50-150, 64% con almeno 40. In D1 la media sale da 26
(v1) a 45 operazioni. **Previsione 1: vera per H4, falsa per D1** (mediana
37: C4 resta a 7-26 operazioni perche' la candela di inversione e' rara).

## Criteri di promozione (su 1.008)

| criterio | varianti |
|---|---|
| netto > 0 a x1 e x1,5 (R e $) | 357 |
| t >= 3 | **0** |
| anni positivi >= 7/9 | 58 |
| positivo in 2009-2012 e 2013-2017 | 114 |
| placebo p < 0,01 | 13 |
| migliore del riferimento a x1 e x1,5 | 754 |
| n >= 40 | 649 |
| **tutti** | **0** |

Netto, meta', anni e riferimento insieme: 24; con anche p < 0,01: 4 (tutte
con n < 40); con anche n >= 40: 7, t massimo 1,86. Le 13 con p < 0,01 sono
12 C4 su D1 (11 long, k 2-3) e una C4 D1 k=4 short, tutte con 12-26
operazioni.

## Migliori 15 per t (nessuna passa)

t = min(t operazioni, t mensile); R e $ netti per operazione (x1, con swap);
R m1/m2 = netto totale in R nel 2009-2012 / 2013-2017.

| TF | k | conf. | stop | obiettivo | lato | n | vinte | R x1 | R x1,5 | $ x1 | t op | t mese | anni+ | R m1 | R m2 | p | R rif. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 2 | C4 | S1 | 1R | long | 26 | 69% | 0,449 | 0,440 | 13,11 | 2,98 | 2,60 | 7 | 3,06 | 8,62 | 0,002 | -0,107 |
| D1 | 2 | C4 | S2 | 1R | long | 26 | 69% | 0,449 | 0,440 | 13,11 | 2,98 | 2,60 | 7 | 3,06 | 8,62 | 0,003 | -0,107 |
| D1 | 3 | C2 | S3 | 2R | short | 24 | 63% | 0,741 | 0,733 | 26,75 | 2,64 | 2,41 | 6 | -0,08 | 17,87 | 0,027 | 0,021 |
| D1 | 2 | C2 | S3 | 3R | short | 29 | 59% | 0,781 | 0,773 | 24,81 | 2,56 | 2,39 | 6 | -1,67 | 24,31 | 0,048 | -0,039 |
| D1 | 2 | C2 | S2 | 3R | short | 28 | 61% | 0,687 | 0,681 | 26,57 | 2,55 | 2,38 | 6 | -1,14 | 20,38 | 0,045 | -0,283 |
| D1 | 3 | C2 | S3 | 3R | short | 24 | 63% | 0,812 | 0,804 | 27,22 | 2,55 | 2,35 | 6 | 0,30 | 19,18 | 0,065 | 0,081 |
| D1 | 2 | C2 | S3 | 2R | short | 29 | 59% | 0,652 | 0,644 | 22,44 | 2,49 | 2,34 | 6 | -2,05 | 20,96 | 0,030 | -0,023 |
| D1 | 4 | C4 | S1 | 1R | short | 12 | 83% | 0,658 | 0,646 | 22,44 | 2,86 | 2,31 | 7 | 2,98 | 4,91 | 0,006 | -0,249 |
| D1 | 4 | C4 | S2 | 1R | short | 12 | 83% | 0,658 | 0,646 | 22,44 | 2,86 | 2,31 | 7 | 2,98 | 4,91 | 0,006 | -0,249 |
| D1 | 2 | C4 | S2 | 3R | long | 25 | 56% | 0,812 | 0,803 | 22,77 | 2,55 | 2,31 | 6 | 11,33 | 8,97 | 0,003 | -0,256 |
| D1 | 2 | C4 | S1 | 3R | long | 25 | 56% | 0,812 | 0,803 | 22,77 | 2,55 | 2,31 | 6 | 11,33 | 8,97 | 0,002 | -0,256 |
| D1 | 2 | C2 | S2 | 2R | short | 28 | 61% | 0,541 | 0,535 | 24,95 | 2,44 | 2,29 | 6 | -0,15 | 15,30 | 0,037 | -0,299 |
| D1 | 4 | C5 | S3 | 3R | short | 30 | 57% | 0,662 | 0,653 | 24,67 | 2,28 | 2,26 | 7 | 1,63 | 18,23 | 0,134 | 0,014 |
| D1 | 4 | C5 | S3 | 2R | short | 30 | 57% | 0,593 | 0,584 | 22,69 | 2,29 | 2,25 | 8 | 2,78 | 15,00 | 0,072 | -0,005 |
| D1 | 4 | C2 | S3 | 2R | short | 16 | 63% | 0,892 | 0,884 | 36,66 | 2,50 | 2,21 | 6 | 0,07 | 14,21 | 0,046 | -0,005 |

Tutte D1 con 12-30 operazioni in nove anni. C4 ha S1 = S2 (la candela di
inversione conferma sul minimo: nessun frattale dopo L). Gli short C2/C5
vincono quasi solo nel 2013-2017 (oro in calo): R m1 vicino a zero o
negativo.

## Conferma contro senza conferma, per stop

Medie sulle varianti; rif = riferimento senza conferma con stesso TF, k,
stop, obiettivo e lato; "meglio" = quota con R migliore del riferimento a
x1 e x1,5.

| stop | TF | n | vinte | vinte rif | R | R rif | $ | $ rif | meglio | t max |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | D1 | 45 | 46,3% | 29,6% | 0,098 | -0,211 | 1,73 | -0,61 | 86% | 2,60 |
| S1 | H4 | 92 | 37,4% | 30,1% | -0,051 | -0,166 | -1,05 | -0,09 | 79% | 1,35 |
| S2 | D1 | 45 | 46,2% | 29,6% | 0,105 | -0,211 | 1,98 | -0,60 | 82% | 2,60 |
| S2 | H4 | 97 | 35,5% | 29,8% | -0,042 | -0,149 | -0,74 | -0,49 | 76% | 1,35 |
| S3 | D1 | 45 | 46,3% | 40,4% | 0,141 | -0,033 | 4,25 | -0,06 | 73% | 2,41 |
| S3 | H4 | 82 | 39,7% | 38,9% | -0,049 | -0,062 | -1,15 | -0,32 | 54% | 1,77 |

Tutte le operazioni insieme (non per variante; R_atr = 1R in ATR; fr =
quota S2 con minimo crescente):

| stop | | operazioni | vinte | R x1 | lordo R | $ x1 | 1R/ATR | fr |
|---|---|---|---|---|---|---|---|---|
| S1 | con conferma | 22.920 | 39,2% | -0,026 | 0,019 | -0,48 | 1,55 | - |
| S1 | senza | 6.425 | 30,8% | -0,178 | -0,087 | -0,30 | 0,60 | - |
| S2 | con conferma | 23.763 | 38,1% | -0,019 | 0,029 | -0,28 | 1,31 | 37% |
| S2 | senza | 6.378 | 30,7% | -0,163 | -0,067 | -0,49 | 0,55 | 10% |
| S3 | con conferma | 21.390 | 41,4% | -0,006 | 0,033 | 0,01 | 1,50 | - |
| S3 | senza | 4.462 | 40,6% | -0,043 | -0,006 | -0,12 | 1,50 | - |

Per conferma (R x1 medio, minimo/massimo fra i tre stop): C4 +0,23/+0,26 (22
operazioni medie), C5 +0,06/+0,07, C3c 0,00/+0,04, C3b 0,00/+0,03, C2
-0,03/+0,03, C1 -0,05/-0,03, C3a -0,08/-0,04; riferimenti fra -0,05 (S3) e
-0,19 (S1).

Long contro short (medie sulle varianti, R x1 / $ x1): S1 long +0,016 /
-3,22, short +0,032 / +3,90; S3 long -0,007 / -1,58, short +0,100 / +4,68.
Lo short guadagna in $ soprattutto nel 2013-2017 e con lo swap FP positivo.

## Candidati

**Nessuno** (0 su 1.008). Non si congela nessuna specifica:
`docs/crollo-conferma-swing-v2-candidati.md` non esiste, nessun file di
`D:\ricerca_zero\verifica\`, nessun anno >= 2018 dell'oro e nessun file
HistData (argento, S&P, EUR/USD) sono stati aperti. Verifica e
trasferimento non si eseguono.

## Previsioni registrate

1. "Operazioni swing 50-150 per variante": **vera per H4** (mediana 85-93),
   **falsa per D1** (mediana 37); nel complesso mediana 51.
2. "Nessun candidato raggiunge t 3": **vera** (t massimo 2,60).
3. "Se ce n'e' uno, non passa la verifica": non applicabile.

## Cosa aggiunge la conferma

1. **Lo stop senza tetto non crea il vantaggio, lo diluisce.** Le
   operazioni aggiunte (conferme lontane dal minimo) valgono circa zero: la
   migliore della v1 (D1 k=3 C3b 1R long: 11 operazioni, +0,65 R, t 2,48)
   con S1/S2/S3 ha 58-61 operazioni e R +0,00/+0,03 (t <= 0,22). Le D1
   restano positive in media (R +0,10/+0,14) per merito di poche varianti
   rare; le H4 sono in media negative con ogni stop. Il t massimo passa da
   2,48 (v1) a 2,60.
2. **La conferma migliora il lordo, non abbastanza da pagare il resto.**
   Con lo stesso stop fisso (S3, confronto pulito: stesso 1R in ATR) la
   conferma porta il lordo da -0,006 a +0,033 R e il netto da -0,043 a
   -0,006 R: circa +0,04 R per operazione, positivo in 7 conferme su 7 ma
   piccolo. Con S1/S2 il salto in R (-0,18 -> -0,02) e' in gran parte un
   effetto di scala: senza conferma 1R e' 0,6 ATR (stop vicinissimo a L),
   con la conferma 1,3-1,5 ATR; in $ per operazione S1 con conferma
   (-0,48) e' peggio del senza (-0,30).
3. **L'unico punto con segnale coerente resta C4 su D1** (candela di
   inversione che spazza il minimo, poi chiusura sopra il suo massimo):
   long k=2 1R, 26 operazioni, 69% vinte, +0,45 R, 7 anni positivi su 9,
   entrambe le meta' positive, p 0,002, ma t 2,60 e n 26 < 40. Era gia' fra
   le migliori della v1 (k=2 C4 1R: 13 operazioni, t 2,18): togliere il
   tetto ne ha raddoppiato i casi senza alzare t a 3. Da non inseguire con
   altre varianti (sarebbe grid-mining sullo stesso campione).
