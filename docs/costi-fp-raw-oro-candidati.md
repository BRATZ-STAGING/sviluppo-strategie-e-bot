# Oro intraday con costi FP Raw — candidato congelato per la verifica (06/10/2026)

Scritto **prima** di eseguire la regola sul 2018 -> 07/2026. Protocollo:
`docs/costi-fp-raw-oro-registrazione.md` (commit 4e59d3f). Rapporti di
scoperta: `docs/studies/oro-fp/f1f2.md` (0 candidati) e `f3f4c.md` (1).

**k = 1 -> soglia di verifica t >= 2.**

## F3-ORO-1 — tocco del range asiatico nella mattina di Londra, nel verso del tocco

Specifica = codice di `zero_f3_range.py` (variante
`b|XAUUSD|ASIA>LON|TS|K25|E2|piccolo`) richiamato da `oro_fp_f3f4c.py`, invariato.

- Livelli: massimo e minimo delle M5 fra 00:00 e 07:00 UTC dello stesso giorno.
- Finestra: 07:00-12:00 UTC; segnali solo sulle M5 che aprono prima delle 11:00.
- Long: solo se la finestra apre sotto il massimo asiatico; alla prima M5 che lo
  tocca, entrata long all'apertura della M5 successiva. Short: specchio sul
  minimo asiatico. Lati indipendenti.
- Stop 0,25 x ATR14 (giorni UTC validi fino al precedente); obiettivo 2R;
  altrimenti uscita alla chiusura dell'ultima M5 delle 12:00. Stop prima
  dell'obiettivo nella stessa candela; apertura oltre un livello = uscita
  all'apertura.
- Filtro: range del giorno precedente / ATR14 nel terzile basso dei 250
  valori precedenti (minimo 60).
- Scarto se rischio < 2 x 0,20 $. Costi 0,20 $ (base) e 0,30 $; nessuno swap.

Scoperta 2009-2017: 683 operazioni (~0,3 al giorno), lordo 0,685 $/op;
a 0,20 $: +0,098 R/op, t 3,06, 8/9 anni, p 0,001; a 0,30 $: +0,075 R, t 2,36,
7/9. Con i costi vecchi (0,40): t 1,65.

## Criterio di verifica

Netto > 0 a 0,20 **e** 0,30 $; **t >= 2** (metodo della scoperta, a 0,20 $);
anni positivi >= 2/3; placebo p < 0,05.

## Avvertenze dichiarate prima

- E' il migliore di 432 varianti F3 con t appena sopra 3; le varianti vicine
  stanno fra t 2,5 e 2,8.
- Il lordo viene soprattutto dallo short (1,00 $ contro 0,41 $ del long).
- Il costo 0,20 $ e' la media pubblicata da FP oggi; negli anni passati e nei
  minuti dei tocchi lo spread reale puo' essere stato maggiore.

## Previsione

Non passa a t 2 (picco di un campo con t 2,5-2,8 nelle vicine).
