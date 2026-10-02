# Trend following multi-giorno sull'oro — registrazione preventiva (02/10/2026)

Scritto e pubblicato **prima** di eseguire qualunque test di queste regole.
Nessun risultato di queste tre famiglie esiste nel repository a questa data
(controllato: nessuno studio di trend following multi-giorno in `docs/studies/`).

## Perche'

Tutte le strade chiuse del progetto sono **intraday**, e quasi tutte sono
morte sullo stesso punto: con stop di pochi dollari lo spread (0,33 -> 0,63 $)
pesa il 7-10% del rischio e mangia un vantaggio lordo piccolo. Un sistema
multi-giorno ha stop di decine di dollari: lo spread diventa trascurabile e il
costo vero diventa lo **swap** (appendice AQ). Il trend following e' la
famiglia con la letteratura piu' lunga sulle materie prime (Moskowitz, Ooi,
Pedersen 2012 "Time series momentum"; i sistemi Turtle anni '80). Nessun
parametro qui sotto e' scelto da noi: sono quelli canonici della letteratura.

## Dati

`data/XAUUSD_M1/` 2009-01-01 -> 2026-07-06, BID, ridotto a candele D1 con
`framework.volatility.daily_bars` (sessioni parziali escluse), salvato in
`docs/studies/dati/XAUUSD_D1_2009-2026.parquet` (4.525 sedute). Le decisioni si
prendono alla **chiusura** D1 e si eseguono all'**apertura** del giorno dopo.
Tutto il periodo e' fuori campione per queste regole: nessuna selezione.

## Le tre famiglie (parametri fissati ora, non modificabili)

Unita' di rischio comune: **1R = 2 x ATR20 D1** misurato alla decisione.

- **F1 — Time-series momentum (TSMOM).** All'ultima chiusura di ogni mese:
  se il rendimento degli ultimi 12 mesi (252 sedute) e' > 0 si e' long per il
  mese successivo, altrimenti short. Nessuno stop. Un'operazione = un mese
  (se il segno non cambia, si contano comunque mesi separati).
- **F2 — Breakout di Donchian (Turtle "System 2").** Entrata long alla
  chiusura sopra il massimo delle 55 sedute precedenti, short sotto il minimo.
  Uscita alla chiusura sotto il minimo delle 20 sedute (long) / sopra il
  massimo delle 20 (short), oppure stop a 1R dall'entrata (toccato intraday,
  eseguito al livello; se il gap lo supera, all'apertura). Una posizione alla
  volta, niente piramidazione.
- **F3 — Incrocio di medie 50/200.** Long quando la media semplice a 50
  chiusure incrocia sopra quella a 200, short quando incrocia sotto; sempre a
  mercato, uscita all'incrocio opposto (che apre la posizione inversa). Stop a
  1R come F2.

## Costi (obbligatori)

- **Spread**: un round trip per operazione; 0,40 $ nel 2009-2019, dal 2020 il
  dizionario `SPREAD` di `trading/scripts/verifica_bot.py`.
- **Swap**: listino FP (appendice AQ) **-0,715 $/oncia/notte long, +0,325
  short, x3 il mercoledi'**, riscalato in proporzione al prezzo dell'oro
  rispetto al prezzo di riferimento **4.156,98 $** (ultima chiusura D1 nei
  dati, 06/07/2026: il listino e' del 03/08/2026, un mese dopo) (cioe' un costo annuo
  costante in percentuale del prezzo). E' una stima prudente per il
  2009-2021, quando i tassi erano vicini a zero. Si riporta **anche** il
  risultato senza swap, come sensibilita', ma il verdetto usa lo swap.

## Misure

Per famiglia: R netto totale, R/op, operazioni, vinte%, DD in R, anni positivi,
R per anno, e le due meta' **2009-2017** e **2018-2026** separate.

## Placebo (obbligatorio)

Per famiglia, 500 serie con le stesse date di entrata e la stessa durata di
ogni operazione reale ma **direzione a caso**, stessi costi. p = quota di
placebo con R netto totale >= reale. (Misura se la DIREZIONE scelta dalla
regola vale qualcosa oltre all'esposizione all'oro.) In piu' si riporta il
benchmark "sempre long" con lo stesso swap.

## Criterio di successo (per famiglia)

Passa se valgono tutte:
- R netto totale > 0 e R/op > 0, con swap;
- p placebo < 0,05;
- anni positivi >= 2/3 degli anni con almeno 2 operazioni (TSMOM: tutti);
- entrambe le meta' (2009-2017 e 2018-2026) positive.

Con tre famiglie la soglia di p e' gia' generosa: una che passa con p fra
0,0167 e 0,05 va segnalata come "al limite" (correzione di Bonferroni).

## Previsioni dichiarate

1. Al massimo una famiglia su tre passa.
2. La meta' 2009-2017 sara' negativa o quasi per tutte e tre (2013-2018 e'
   stato un lungo laterale/ribasso dell'oro), quindi il criterio delle due
   meta' sara' quello che boccia piu' spesso.
3. Lo swap long trasforma in perdita almeno una famiglia che senza swap
   sarebbe positiva.

## Cosa NON si fa

Nessuna griglia di parametri, nessuna lunghezza diversa da 12 mesi / 55-20 /
50-200, nessun filtro aggiunto dopo aver visto i numeri. Varianti = nuovo
documento di registrazione. I risultati negativi si scrivono come quelli
positivi.
