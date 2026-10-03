# Cambi intraday — verifica 2018 -> 09/2026 della strategia combinata S1+S2+S3 (04/10/2026)

Registrazione vincolante: `docs/fx-combinata-registrazione.md` (commit d0c20ca).
Protocollo dei costi: `docs/fx-intraday-registrazione.md`. Script:
`trading/scripts/fx_verifica_combinata.py`: importa `fx_b_aperture.py` (S1),
`fx_c_media_momentum.py` (S2) e `fx_d_orari_fissi.py` (S3) e ne usa le
funzioni senza modificarle. Come in `fx_verifica.py`, cambia solo la lettura
dei dati (cartella "CONCAT" intercettata in `pd.read_parquet`). Dati:
`D:\ricerca_fx\scoperta\` e `D:\ricerca_fx\verifica\` (M5 e D1 BID, UTC).

| id | regola | coppie | R (unita' comune) |
|---|---|---|---|
| S1 | a A1 RIENTRO S3 1R piccolo mar-gio | AUDUSD, EURJPY, EURUSD, GBPUSD, USDCHF | stop = 0,25 x ATR14 |
| S2 | L15 H30 Londra k3, stop 2/obiettivo 1, regime alto, contro | USDJPY, AUDUSD | stop = 2 s_H |
| S3 | LDF PRE FIX- 60' fine mese (dollaro venduto 15:00-16:00 Londra) | USDJPY, GBPUSD, AUDUSD, USDCHF | 0,15 x ATR14 (solo misura, nessuno stop) |

## Passo 1 — riproduzione sulla scoperta 2010-2017

Le tre componenti coincidono con i numeri registrati, ciascuna con il t
definito come nel suo script di origine: S1 t per operazione in R; S2 e S3 t
sulle somme giornaliere in pip dei giorni con operazioni.

| | n (reg./ripr.) | netto pip | netto R | t | anni + | esito |
|---|---|---|---|---|---|---|
| S1 | 869 / **869** | 3,70 / 3,7007 | 0,123 / 0,1227 | 3,75 / 3,7524 | 7 / 7 | coincide |
| S2 | 85 / **85** | 6,11 / 6,1105 | — / 0,1796 | 4,621 / 4,6210 | 7 / 7 | coincide |
| S3 | 384 / **384** | 5,74 / 5,7411 | — / 0,4087 | 3,26 / 3,2637 | 6 / 6 | coincide |

**Prova del confine** (dentro la scoperta): ho calcolato gli indicatori su
una coda di 400 giorni concatenata davanti al 2017. Le operazioni 2017
coincidono una per una con quelle della scoperta intera: S1 120, S2 1, S3 48,
con differenza 0,0 sia sul lordo sia sul rischio. Quindi 400 giorni bastano
per ATR14, terzili sui 250 precedenti (S1) e regime sui 252 giorni (S2).

**Combinata sulla scoperta (solo riferimento)**: n 1338, **0,645 op/giorno**
(2074 giornate), netto **+0,208 R/op** (+278,9 R totali), a x1,5 +0,182 R/op
(+244,0 R), t giornaliero 4,55 (x1,5 4,01), 7/8 anni positivi (x1,5 6/8),
placebo p 0,0001, peggiore operazione -6,1 R, peggiore serie 13 perdite
(-21,8 R), drawdown 31,5 R (x1,5 35,5), costo di pareggio x5,0. Questi numeri
sono gonfiati: le coppie di ciascuna componente sono state scelte sugli
stessi anni.

## Passo 2 — verifica (una sola esecuzione)

Indicatori calcolati sulla coda della scoperta (dal 27/11/2016) concatenata
ai dati di verifica. Contano le entrate dal 01/01/2018 00:00 UTC. Prima
operazione 02/01/2018, ultima 22/09/2026 (i dati finiscono il 24/09/2026).
Giornate di borsa 2263 (unione delle 6 coppie).

| misura | scoperta 2010-2017 | **verifica 2018-09/2026** | criterio | esito |
|---|---|---|---|---|
| n | 1338 | **1549** (S1 1033, S2 121, S3 395) | — | |
| operazioni/giorno | 0,645 | **0,684** | >= 0,5 | passa |
| lordo R/op | +0,261 | +0,079 | — | |
| costo R/op | 0,052 | 0,063 | — | |
| netto x1 R/op (totale) | +0,208 (+278,9 R) | **+0,016 (+24,6 R)** | > 0 | passa (di poco) |
| netto x1,5 R/op (totale) | +0,182 (+244,0 R) | **-0,016 (-24,4 R)** | > 0 | **no** |
| t sul netto giornaliero | 4,55 | **0,32** (x1,5: -0,31) | >= 2 | **no** |
| anni positivi | 7/8 | **6/9** (2026 parziale; x1,5 6/9; senza il 2026 5/8) | >= 6/9 | passa (al limite) |
| placebo p (10000 serie) | 0,0001 | **0,0076** | < 0,01 | passa |
| vinte | 60% | 52% | | |
| peggiore operazione | -6,1 R | -10,7 R (S3 GBPUSD 30/11/2021) | | |
| peggiore serie | 13 perdite, -21,8 R | 11 perdite, -39,7 R | | |
| drawdown massimo | 31,5 R | **106,7 R** (x1,5: 130,9 R) | | |

**Verdetto: la strategia combinata NON PASSA la verifica.** Fallisce due
criteri: netto negativo a costi x1,5 e t 0,32, molto sotto 2. A costi x1 il
netto e' appena positivo (+0,016 R per operazione) e dipende dal 2026
parziale: fino al 2025 il totale e' -1,6 R. Il placebo (p 0,0076) dice che le
direzioni scelte fanno meglio di direzioni casuali, che perdono in media
-109 R. Ma il vantaggio non supera i costi: il lordo e' di +0,079 R contro un
costo di 0,063 R.

### R per anno (netto, costi x1; 2026 = fino al 22/09)

| | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|---|
| n | 178 | 184 | 163 | 173 | 228 | 168 | 182 | 153 | 120 |
| **combinata x1** | +13,9 | +8,6 | +30,2 | **-63,5** | -8,6 | +22,3 | -34,6 | +30,0 | +26,2 |
| combinata x1,5 | +8,4 | +1,5 | +24,8 | -69,8 | -13,7 | +17,9 | -40,6 | +25,0 | +22,1 |
| S1 | -2,2 | -1,1 | -3,8 | +1,3 | -0,7 | +3,4 | -6,5 | -6,4 | -8,7 |
| S2 | -1,2 | +0,7 | -2,4 | -1,6 | -9,2 | -0,4 | -2,1 | -4,9 | +4,1 |
| S3 | +17,2 | +9,0 | +36,3 | -63,2 | +1,3 | +19,3 | -26,0 | +41,4 | +30,8 |

### Componenti (solo informative)

t orig. = definizione dello script di origine (S1 per operazione in R; S2 e
S3 somme giornaliere in pip dei giorni con operazioni). t R = somme
giornaliere in R su tutte le giornate.

| | n | op/g | netto pip | netto R | netto R x1,5 | totale R | t orig. | t R | anni + | pareggio | scoperta (netto R / t) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 1033 | 0,457 | -0,42 | -0,024 | -0,050 | -24,6 | -0,78 | -0,72 | 2/9 | x0,55 | +0,123 / 3,75 |
| S2 | 121 | 0,054 | -5,49 | -0,140 | -0,160 | -17,0 | -1,78 | -1,80 | 2/9 | lordo < 0 | +0,180 / 4,62 |
| S3 | 395 | 0,175 | +2,21 | +0,168 | +0,119 | +66,3 | 1,13 | 0,97 | 6/9 (in R 7/9) | x2,71 | +0,409 / 3,26 |

Per coppia (netto R per operazione / totale R): S1 AUDUSD +0,039 / +5,3;
EURJPY -0,162 / -28,5; EURUSD +0,002 / +0,5; GBPUSD +0,016 / +3,6; USDCHF
-0,024 / -5,5. S2 AUDUSD -0,073 / -3,3; USDJPY -0,181 / -13,7. S3 AUDUSD
+0,037 / +3,6; GBPUSD +0,376 / +37,6; USDCHF +0,263 / +26,0; USDJPY
-0,010 / -1,0.

- **S1** (rientro del range asiatico): il lordo scende da +4,7 a +0,6 pip.
  E' vicino a zero su quattro coppie su cinque, e su EURJPY e' negativo.
  Pesa due terzi delle operazioni e annulla il contributo di S3.
- **S2**: negativa (-5,5 pip per operazione, lordo negativo), ma con 121
  operazioni il t di -1,8 non basta per dire molto.
- **S3** (fine mese, fixing di Londra): e' l'unica componente positiva, con
  +66 R. Resta positiva anche a x1,5, ma ha t 1,1 e le perdite senza stop
  sono grandi. Il 30/11/2021 alle 15:00 UTC (coincide con l'audizione di
  Powell al Senato) le quattro coppie perdono insieme -36,5 R in un'ora
  (da -7,2 a -10,7 R ciascuna). Il 2021 di S3 (-63 R) e' quasi tutto in
  quel giorno.

## Diagnostica (non cambia il verdetto)

**Costo di pareggio della combinata**: lordo R totale / costo R totale =
**x1,25** del costo del protocollo. In scoperta era x5,0. Con costi solo
del 25% piu' alti di quelli FP Raw dichiarati il netto si azzera. Per
componente: S1 x0,55, S2 nessuno (lordo negativo), S3 x2,71.

## Previsioni della registrazione

1. "La combinata NON passa": **confermata** (netto x1,5 < 0, t 0,32).
2. "S3 e' la componente piu' probabile a restare positiva": **confermata**.
   E' l'unica positiva (+0,168 R/op, 6/9 anni), ma non significativa (t 1,1).
3. "S2 ha troppe poche operazioni per dire qualcosa da sola": **confermata**.
   121 operazioni con netto negativo, t -1,8.

## File

`D:\ricerca_fx\risultati\`:
- `verifica_comb_operazioni.parquet`: una riga per operazione 2018-2026, con
  componente, coppia, entrata, direzione, rischio, lordo, lordo della
  direzione opposta, costo e valori in R;
- `verifica_comb_riepilogo.parquet`, `verifica_comb_componenti.parquet`,
  `verifica_comb_anni.parquet`, `verifica_comb_coppie.parquet`;
- `verifica_comb_log.txt`: uscita dell'esecuzione;
- riferimento della scoperta: `verifica_comb_scoperta_operazioni.parquet`,
  `verifica_comb_scoperta_riepilogo.parquet`,
  `verifica_comb_scoperta_componenti.parquet`.

## Scelte interpretative

- **t della combinata**: somme di R per giornata su tutte le giornate di
  borsa dell'unione delle 6 coppie, con zero nei giorni senza operazioni
  (come per C1). Sui soli giorni con operazioni il t e' 0,318: nessuna
  differenza.
- **Frequenza**: operazioni / giornate dell'unione = 0,6845. La somma per
  coppia (n_coppia / giornate_coppia, come negli script di scoperta) da'
  0,6845.
- **Anni**: 9 anni di calendario, con il 2026 parziale. La soglia dei 2/3 e'
  quindi 6/9.
- **Placebo**: a ogni operazione do una direzione casuale. Per la direzione
  opposta uso l'esito calcolato dallo stesso motore di origine, con stop e
  obiettivo speculari: il "lordo opposto" di `simula_vett`, `esiti` di fx_c e
  `griglia` di fx_d. Statistica: R netto totale a x1. 10000 serie, seed
  20261004, p = (1 + #placebo >= reale) / 10001. Per S3 questo placebo e'
  diverso da quello di `fx_d`, che cambiava a caso anche l'istante
  d'entrata: la registrazione chiede solo la direzione casuale.
- **Fine mese di S3**: i dati finiscono giovedi' 24/09/2026, mentre l'ultima
  giornata di borsa di settembre e' il 30/09. Senza correzione, `fine_mese`
  di fx_d segnerebbe il 24/09 come fine mese. L'ho escluso, perche' un
  operatore non poteva saperlo quel giorno. In scoperta la correzione non
  cambia nulla (29/12/2017 era davvero l'ultima giornata del mese).
- **Data dell'operazione**: giorno UTC dell'entrata. Contano le entrate dal
  01/01/2018 00:00 UTC.
- **R**: S1 usa l'ATR14 di `fx_b.atr14`, S3 l'ATR14 di `fx_d.carica`
  (entrambi causali, ciascuno quello del proprio script).
- **Peggiore serie**: la sequenza piu' lunga di operazioni perdenti
  consecutive, in ordine di entrata. A parita' d'istante l'ordine e'
  componente e poi coppia.
- **Esecuzione unica**: lo script rifiuta una seconda esecuzione della fase
  `verifica` se il file delle operazioni esiste gia'.
