# Perche' la B crolla: le condizioni delle perdite (06/10/2026)

Esecuzione alla lettera di `docs/crolli-b-registrazione.md` (commit 1c74323,
scritto prima di calcolare). Nessun fattore aggiunto, nessuna soglia cambiata.

- Operazioni: le 712 B di `docs/studies/dati/b_operazioni_2009_2026.parquet`,
  usate cosi' come sono (374 nel 2009-2019, 338 nel 2020-2026).
- Misure di mercato: archivio M1 intero 2009-01-01 -> 2026-07-06 (6.236.648
  candele), caricato una volta; giornate vere di `volatility.daily_bars`
  (>= 300 candele, senza lo spezzone della domenica).
- Script: `trading/scripts/run_crolli_b.py` (un comando, ~10 s). Dettaglio
  per operazione con i nove fattori, le fasce, l'epoca e la discesa:
  `docs/studies/dati/crolli_b.parquet` (712 righe, 32 colonne); tabella della
  domanda 2 in `crolli_b_domanda2.parquet`.

## 1. Domanda 1 — come perde (descrittiva)

| gruppo | op | R | R/op | vinte | R vinte | R perse | stop | protetto | obiettivo | gap | venerdi' | scadenza |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2009-2019 | 374 | -91,4 | -0,244 | 23,0% | +2,74 | -1,13 | 72,7% | 17,9% | 1,9% | 2,4% | 5,1% | 0 |
| 2020-2026 | 338 | +174,2 | +0,516 | 37,3% | +3,22 | -1,09 | 61,8% | 29,3% | 5,6% | 0,0% | 3,3% | 0 |
| discesa 16/07-22/10/2024 | 18 | -1,2 | -0,065 | 27,8% | +2,60 | -1,09 | 72,2% | 27,8% | 0 | 0 | 0 | 0 |
| discesa 11/04-03/09/2025 | 17 | -0,4 | -0,023 | 23,5% | +3,45 | -1,09 | 76,5% | 17,6% | 5,9% | 0 | 0 | 0 |
| discesa 28/01-24/06/2026 | 14 | -5,7 | -0,407 | 7,1% | +7,96 | -1,05 | 92,9% | 0 | 7,1% | 0 | 0 | 0 |
| tre discese insieme | 49 | -7,3 | -0,148 | 20,4% | +3,47 | -1,08 | 79,6% | 16,3% | 4,1% | 0 | 0 | 0 |

Scomposizione esatta della differenza di R/op fra le epoche (2009-2019 meno
2020-2026), con R/op = w·Rv + (1-w)·Rp e medie fra le epoche come pesi:

| differenza R/op | piu' perdenti (w: 23,0% vs 37,3%) | vincenti piu' piccole (Rv: 2,74 vs 3,22) | perdenti piu' grandi (Rp: -1,13 vs -1,09) |
|---|---|---|---|
| **-0,760** | **-0,584 (77%)** | -0,145 (19%) | -0,031 (4%) |

Le perse sono uguali nelle due epoche (-1,13 e -1,09: stop pieno piu' costo).
La B perde nel 2009-2019 perche' **vince 14 punti in meno**: lo stop pieno e'
il 72,7% delle uscite contro il 61,8%, il trailing (protetto) il 17,9% contro
il 29,3%, l'obiettivo l'1,9% contro il 5,6%. Le vincenti sono anche piu'
piccole, ma pesano un quinto della differenza. Le tre discese del 2020-2026
hanno la stessa forma dell'epoca cattiva (stop 72-93%, vinte 7-28%).

## 2. Domanda 2 — quando perde: nove fattori all'ingresso

Fasce peggiori per epoca e p del placebo per giornata (2.000 rimescolamenti,
seme 20261006, soglia 0,05/9 = 0,0056). "diff" = R/op della fascia peggiore
meno R/op del resto dell'epoca.

| fattore | peggiore 2009-2019 | diff | p | peggiore 2020-2026 | diff | p | verdetto |
|---|---|---|---|---|---|---|---|
| 1 volatilita' ATR14/prezzo | alto | -0,22 | 0,548 | medio | -0,38 | 0,332 | nessuna separazione |
| 2 tendenza (pendenza MA200) | medio | -0,27 | 0,468 | medio | -0,24 | 0,665 | nessuna separazione |
| 3 distanza da MA50 (segno lato) | basso | -0,17 | 0,652 | medio | -0,33 | 0,461 | nessuna separazione |
| 4 lato | short | -0,17 | 0,447 | short | -0,46 | 0,153 | nessuna separazione |
| 5 ora UTC | 17-19 | -0,33 | 0,235 | 17-19 | -0,29 | 0,536 | nessuna separazione |
| 6 giorno della settimana | gio | -0,63 | 0,034 | lun | -0,67 | 0,160 | nessuna separazione |
| 7 ampiezza stop rischio/ATR14 | basso | -0,23 | 0,425 | basso | -0,46 | 0,191 | nessuna separazione |
| 8 peso costo spread/rischio | alto | -0,07 | 0,909 | medio | -0,17 | 0,802 | nessuna separazione |
| 9 venerdi' buste paga | altro | -0,69 | 0,502 | altro | -1,70 | 0,056 | nessuna separazione |

**Nessuno dei nove fattori spiega i crolli; nessuno separa neanche una sola
epoca.** Il p piu' basso e' 0,034 (giovedi', 2009-2019), sei volte sopra la
soglia, e nell'altra epoca il giovedi' e' la seconda fascia migliore. Il
venerdi' delle buste paga va nel verso opposto all'atteso: le 19 operazioni
del primo venerdi' rendono di piu' (+0,44 e +2,15 R/op), non di meno.

R/op per fascia nelle due epoche (n operazioni):

| fattore | fascia | 2009-2019 | 2020-2026 | fattore | fascia | 2009-2019 | 2020-2026 |
|---|---|---|---|---|---|---|---|
| 1 volatilita' | basso | -0,26 (134) | +1,02 (103) | 5 ora | 07-11 | -0,18 (106) | +0,48 (170) |
| | medio | -0,04 (106) | +0,28 (131) | | 12-16 | -0,22 (221) | +0,61 (143) |
| | alto | -0,38 (133) | +0,31 (104) | | 17-19 | -0,53 (47) | +0,25 (25) |
| 2 tendenza | basso | -0,19 (165) | +0,82 (64) | 6 giorno | lun | -0,33 (82) | -0,04 (59) |
| | medio | -0,39 (122) | +0,35 (107) | | mar | -0,11 (87) | +0,86 (58) |
| | alto | +0,07 (62) | +0,50 (167) | | mer | -0,13 (62) | +0,39 (81) |
| 3 distanza MA50 | basso | -0,35 (136) | +0,40 (101) | | gio | -0,76 (65) | +0,65 (68) |
| | medio | -0,33 (130) | +0,29 (107) | | ven | +0,04 (78) | +0,71 (72) |
| | alto | +0,01 (107) | +0,79 (130) | 7 ampiezza stop | basso | -0,40 (117) | +0,22 (120) |
| 4 lato | long | -0,17 (222) | +0,65 (238) | | medio | -0,20 (117) | +0,32 (120) |
| | short | -0,35 (152) | +0,19 (100) | | alto | -0,14 (139) | +1,12 (98) |
| 8 peso costo | basso | -0,18 (69) | +0,63 (169) | 9 buste paga | altro | -0,25 (369) | +0,45 (324) |
| | medio | -0,23 (128) | +0,40 (109) | | primo ven | +0,44 (5) | +2,15 (14) |
| | alto | -0,28 (177) | +0,40 (60) | | | | |

Soglie dei terzi (sulle 712 insieme): volatilita' 0,01217 / 0,01502;
tendenza 0,080 / 1,097; distanza MA50 2,286 / 4,214; ampiezza stop 0,1328 /
0,1901; peso costo 0,0858 / 0,1362. Operazioni senza fattore (inizio 2009,
storia D1 insufficiente): 25 per la tendenza, 1 per volatilita', distanza e
ampiezza, tutte nel 2009-2019; escluse solo da quel fattore.

Il quadro per fascia e' quello di BW: in ogni fascia di ogni fattore il
2009-2019 e' intorno a -0,2 e il 2020-2026 intorno a +0,5. Il salto fra le
epoche (~0,7-0,8 R/op) e' lo stesso dentro ogni fascia; nessuna fascia lo
spiega. Dove il 2020-2026 guadagna di piu' (volatilita' bassa +1,02, stop
largo +1,12, buste paga +2,15) il 2009-2019 non e' migliore del suo resto.

## 3. Domanda 3 — le tre discese del 2020-2026 (descrittiva, 49 operazioni)

Quota di operazioni per fascia: tre discese insieme contro il resto del
2020-2026 (289 operazioni); fra parentesi le operazioni per discesa
2024 / 2025 / 2026.

| fattore | fascia | resto 20-26 | tre discese | per discesa |
|---|---|---|---|---|
| 1 volatilita' | basso / medio / alto | 29,8 / 41,9 / 28,4 | 34,7 / 20,4 / **44,9** | alto: 1 / 7 / **14** |
| 2 tendenza | basso / medio / alto | 22,1 / 34,3 / 43,6 | **0,0** / 16,3 / **83,7** | alto: 18 / 14 / 9 |
| 3 distanza MA50 | basso / medio / alto | 30,8 / 29,1 / 40,1 | 24,5 / 46,9 / 28,6 | medio: 9 / 4 / 10 |
| 4 lato | long / short | 70,9 / 29,1 | 67,3 / 32,7 | short: 0 / 4 / **12** |
| 5 ora | 07-11 / 12-16 / 17-19 | 46,7 / 44,6 / 8,7 | **71,4** / 28,6 / 0,0 | 07-11: 10 / 16 / 9 |
| 6 giorno | lun / mar / mer / gio / ven | 19,0 / 15,6 / 24,2 / 20,4 / 20,8 | 8,2 / 26,5 / 22,4 / 18,4 / 24,5 | — |
| 7 ampiezza stop | basso / medio / alto | 34,6 / 34,3 / 31,1 | 40,8 / 42,9 / 16,3 | alto: 4 / 2 / 2 |
| 8 peso costo | basso / medio / alto | 48,1 / 32,5 / 19,4 | 61,2 / 30,6 / 8,2 | basso: 9 / 10 / 11 |
| 9 buste paga | altro / primo ven | 96,2 / 3,8 | 93,9 / 6,1 | primo ven: 0 / 1 / 2 |

Le tre discese cadono quasi tutte con la **tendenza di fondo alta** (41 su 49,
nessuna con tendenza bassa) e con ingresso **al mattino** (35 su 49). Sono le
fasce dove sta la maggioranza del 2020-2026 recente e dove l'epoca rende bene
(+0,50 e +0,48 R/op): le discese sono avvenute dentro il regime favorevole,
non in un regime diverso. La discesa del 2026 e' particolare: 14 operazioni
su 14 in volatilita' alta e 12 su 14 short, con una sola vinta (+7,96 R).
Nessun test, come registrato: 14-18 operazioni per discesa.

## 4. Esito delle tre previsioni

1. **Confermata.** Nessun fattore spiega i crolli; nessuno separa neanche una
   epoca sola. Coerente con BW: misurato in modo relativo, il mercato delle
   due epoche e' lo stesso.
2. **Smentita nella parte quantitativa.** Il 77% della differenza di R/op
   viene da **piu' perdenti** (stop pieno 72,7% contro 61,8%), il 19% dalle
   vincenti piu' piccole. E' vero che trailing e obiettivi sono piu' rari
   (17,9% e 1,9% contro 29,3% e 5,6%) e le vinte piu' piccole (2,74 contro
   3,22), ma la componente principale e' la quota di vinte, cioe' gli stop
   piu' frequenti: l'opposto di quanto previsto.
3. **Non si applica**: nessun fattore separa. Il verso e' quello atteso (lo
   short e' la fascia peggiore in entrambe le epoche, -0,17 e -0,46), ma con
   p 0,45 e 0,15 e' quello che il caso produce. La tendenza di fondo non
   separa (p 0,47 e 0,67).

## 5. Controllo di causalita' (come e' stato verificato)

Tre controlli, nello script (`controllo_causalita`), eseguiti a ogni run:

1. **Ricalcolo da un M1 troncato.** Per 46 operazioni (40 estratte a caso con
   seme 20261006 piu' le prime tre e le ultime tre) i quattro valori D1 usati
   (ATR14, MA50, MA200, MA200 di 20 giornate prima) sono stati ricalcolati da
   un archivio che contiene **solo candele con istante < istante d'ingresso**
   (finestra dei 500 giorni precedenti). Stessa giornata D1 scelta in tutti i
   46 casi; scarto massimo 9e-13 (aritmetica in virgola mobile); i 12 valori
   non disponibili (inizio 2009) sono n.d. in entrambe le versioni. Se un
   fattore avesse letto la candela del giorno d'ingresso o successive, il
   troncamento l'avrebbe cambiato.
2. **Confronto con la funzione ufficiale.** Per tutte le 711 operazioni con
   ATR definito, l'ATR14 usato coincide esattamente (scarto 0,0) con
   `framework.volatility.daily_atr` letto sul giorno d'ingresso, che per
   costruzione usa le giornate fino a ieri (shift di 1).
3. **Giornata D1 sempre precedente.** Asserzione su tutte le 712: la riga D1
   usata e' strettamente anteriore al giorno d'ingresso (1 giorno nella
   mediana, 4 al massimo dopo le festivita').

Gli altri fattori usano solo prezzo d'ingresso, rischio in $, istante
d'ingresso e spread dell'anno: noti all'ingresso per costruzione.

## 6. Scelte interpretative (punti non coperti dalla registrazione)

1. **"Ieri"** = ultima giornata vera (`daily_bars`, >= 300 candele)
   strettamente precedente al giorno UTC d'ingresso; ATR14 = media semplice
   del true range su 14 giornate, MA50/MA200 = medie semplici delle chiusure;
   "20 giornate prima" = 20 righe D1 prima di ieri.
2. **Prezzo** del fattore 1 = prezzo d'ingresso (noto all'ingresso); la
   distanza dalla MA50 usa anch'essa il prezzo d'ingresso, come scritto.
3. Operazioni con fattore **non disponibile** (storia D1 insufficiente a
   inizio 2009) escluse solo dal calcolo di quel fattore (terzi e test);
   contate e riportate.
4. Terzi con `pd.qcut` sulle operazioni con fattore disponibile.
5. Fasce orarie: 07-11 = ore 7..11, 12-16 = 12..16, 17-19 = 17..19 (una sola
   operazione alle 19). Buste paga = venerdi' con giorno del mese <= 7.
6. Spread: `SPREAD` di `verifica_bot.py`, 0,40 prima del 2020.
7. **Placebo per giornata**: permutazione a blocchi delle etichette di
   fascia, dove il blocco e' la giornata d'ingresso UTC e i blocchi si
   scambiano solo fra giornate con lo stesso numero di operazioni (245
   giornate con 1, 124 con 2, 73 con 3), cosi' tutte le operazioni dello
   stesso giorno restano insieme. Statistica: in ogni rimescolamento la
   **differenza minima fra le fasce** (peggiore meno il resto), che tiene
   conto della scelta della fascia peggiore (piu' conservativa della fascia
   fissa). p = (1 + #placebo <= osservato) / (N + 1). Un solo generatore,
   seme 20261006, ordine fattori 1..9 x (2009-2019, poi 2020-2026). La p a
   fascia fissa e' stampata dallo script ma non usata: minimo 0,011
   (giovedi' 2009-2019), comunque sopra la soglia.
8. **Operazioni delle discese**: quelle con il cumulato strettamente sotto il
   massimo precedente (`drawdown()` di `analisi_b_18anni.py`), individuate per
   data d'inizio (massimo) e di recupero della registrazione: 18 / 17 / 14.
   L'operazione che fa il massimo e quella che recupera sono escluse; con le
   date inclusive sarebbero 20 / 20 / 18.
9. Scomposizione a tre termini (esatta): il terzo, "perdenti piu' grandi",
   non e' nella registrazione ma serve perche' la somma torni.
10. Vinte = R > 0; perse = R <= 0. "Scadenza" non compare fra i motivi del
    parquet: 0.
11. Il verdetto "spiega i crolli" richiede stessa fascia peggiore e p sotto
    soglia in entrambe le epoche; se entrambe le p fossero sotto soglia con
    fasce diverse si sarebbe scritto "nessuna separazione (fasce peggiori
    diverse)". Non e' successo.

## 7. Limiti

- 712 operazioni, 374 e 338 per epoca; fasce da 5 a 25 operazioni (17-19 nel
  2020-2026: 25; primo venerdi': 5 e 14). Con Bonferroni su nove fattori la
  potenza e' bassa: un effetto reale ma modesto (per esempio giovedi' nel
  2009-2019, p 0,034) non verrebbe rilevato. Lo studio dice che nessun
  fattore **separa** con la forza richiesta, non che l'effetto sia zero.
- I fattori sono quelli dichiarati, a livello D1 piu' ora, giorno e costo:
  niente di intraday, niente calendario FOMC/CPI (non nel repository); le
  buste paga sono approssimate al primo venerdi'.
- La domanda 3 e' descrittiva su 49 operazioni; le quote per discesa non
  vanno lette come effetti.
- Le operazioni vengono dal parquet della B con lo spread vero per anno (senza
  swap); i fattori 7 e 8 dipendono dal rischio in $ di quelle operazioni.
- Il placebo stratificato per numero di operazioni del giorno non scambia le
  giornate con un numero di operazioni unico (nessuna qui: le taglie sono 1,
  2, 3, tutte con molte giornate).

## Cosa dice

La B nel 2009-2019 non perde in condizioni diverse: perde **nelle stesse
condizioni** in cui nel 2020-2026 guadagna. Nessuno dei nove fattori
all'ingresso (volatilita', tendenza, distanza dalla media, lato, ora, giorno,
ampiezza dello stop, costo, buste paga) separa le operazioni buone dalle
cattive in modo coerente fra le epoche, e nessuno lo fa neanche in una sola.
La meccanica e' semplice: stesse perse (stop pieno), **vinte piu' rare** (23%
contro 37%) e un po' piu' piccole. Le tre discese del 2020-2026 sono fatte
della stessa stoffa (stop 72-93%) e avvengono dentro il regime favorevole
(tendenza alta, mattino), non fuori.

Sapere QUANDO la B crollera' resta fuori portata con questi fattori; lo
spegnimento a -15 R di `b-prima-della-demo.md` resta l'unico strumento
misurato. Il risultato va alla verifica avversariale prima di essere
dichiarato valido.
