# La B sul primo fuori campione vero, luglio-ottobre 2026 (06/10/2026)

Registrazione: `docs/b-fuori-campione-2026-registrazione.md` con
l'emendamento 1 (dati MT5, scritto prima del calcolo). Script:
`trading/scripts/run_b_fuori_campione.py`, validato sul primo semestre 2026
con i dati Dukascopy: 23 operazioni su 23 identiche al motore verificato.
Dettaglio: `docs/studies/dati/b_fuori_campione_2026.parquet`.

**Fonte**: MT5, conto demo MetaQuotes, XAUUSD. **Periodo**: 07/07/2026 ->
05/10/2026 23:59 UTC (ultima giornata completa alla lettura).

## Le operazioni

| ingresso (UTC) | lato | uscita | notti | R | R con swap |
|---|---|---|---|---|---|
| 10/08 13:18 | long | stop | 0 | -1,05 | -1,05 |
| 10/08 14:24 | long | protetto | 1 | +2,03 | +2,00 |
| 24/08 16:06 | long | stop | 0 | -1,03 | -1,03 |
| 25/08 15:24 | long | stop | 1 | -1,04 | -1,10 |
| 24/09 13:36 | short | stop | 0 | -1,04 | -1,04 |
| 24/09 18:36 | short | stop | 0 | -1,06 | -1,06 |
| 25/09 08:06 | short | stop | 0 | -1,09 | -1,09 |

**7 operazioni, -4,29 R (-0,61 R/op), con lo swap -4,38 R; 1 vinta su 7.**
Calo massimo dal 07/07: 5,3 R (lo spegnimento a 15 R non scatta).

## Confronto registrato

| | percentile della somma | mediana delle finestre di 7 operazioni |
|---|---|---|
| finestre 2020-2026 | **11** | +1,9 R |
| finestre 2009-2019 | 40 | -2,9 R |

Rapporto di verosimiglianza 2020-2026 / 2009-2019: **0,46**, cioe' la somma
osservata e' un po' piu' tipica del 2009-2019 che del 2020-2026.

**Lettura, come registrata: ne' allarme ne' coerenza piena.** Non e' allarme
(percentile 11, sopra il 5; calo 5,3 R, sotto i 15). Non e' coerenza piena
(percentile fra 5 e 95, ma rapporto di verosimiglianza sotto 1).

## Da tenere presente

- **Sette operazioni non dicono niente sul vantaggio**: anche nel 2020-2026
  l'11% delle finestre di sette operazioni fa peggio di cosi'.
- **Poche operazioni**: 7 in tre mesi, contro circa 11-12 a trimestre nel
  primo semestre 2026 e una media di circa 12 nel 2020-2026; nessuna dal 7
  luglio al 10 agosto. Puo' essere il mercato o la fonte: con i prezzi e il
  `tick_volume` di un altro broker i segnali al limite delle soglie possono
  sparire. Lo si sapra' rifacendo il calcolo con Dukascopy.
- Le tre operazioni di fine settembre sono **short**, come 12 delle 14 della
  discesa del 2026 (`docs/studies/crolli-b.md`): nel 2020-2026 lo short e' la
  fascia peggiore, anche se non in modo significativo.

## Da fare

Rifare lo stesso calcolo con `FONTE=dukascopy` quando l'archivio 2026 sara'
esteso oltre il 06/07 (scaricamento lento in corso per i limiti del feed).
