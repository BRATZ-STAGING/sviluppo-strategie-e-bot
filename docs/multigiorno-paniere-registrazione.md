# Orizzonti multi-giorno su un paniere di mercati — protocollo registrato (04/10/2026)

Richiesta dell'utente: dopo il fallimento dell'intraday, provare orizzonti piu'
larghi (giorni-settimane). Scritto prima di qualunque calcolo di queste regole.

## Paniere e periodi

12 mercati, rischio uguale per mercato:
- Dukascopy: **XAUUSD**; HistData: **XAGUSD, SPXUSD, NSXUSD, GRXEUR**
  (DAX solo fino al 14/06/2020: dopo la serie e' corrotta), **EURUSD, USDJPY,
  GBPUSD, AUDUSD, USDCHF, USDCAD, EURJPY**.
- File: `D:\ricerca_zero\scoperta|verifica\` (metalli e indici) e
  `D:\ricerca_fx\scoperta|verifica\` (cambi), M5/M15/H1/D1, UTC.
- **Scoperta 2010-2017 (oro 2009-2017). Verifica 2018 -> fine dati**, una
  volta sola. Per questi anni sono state aperte finora solo regole intraday
  (e, sull'oro, il trend multi-giorno dell'appendice CD sull'intero
  2009-2026: per l'oro le regole di trend NON sono pulite e si riportano anche
  senza l'oro).
- Giornata: 22:00 -> 22:00 UTC per cambi e metalli (chiusura alle 21:55-22:00),
  e per gli indici la stessa giornata 22->22 (dichiarato; niente sessioni cash).

## Costi (tutti obbligatori)

- Round trip per operazione: cambi come in `docs/fx-intraday-registrazione.md`
  (EURUSD 0,8 pip ... EURJPY 1,4); oro `SPREAD` annuo + 0,06 $; argento
  0,025 $; S&P 0,55; Nasdaq 1,50; DAX 1,50. Ribilanciamenti = nuove operazioni.
- **Swap/finanziamento** per ogni notte tenuta (x3 il mercoledi'): stima
  prudente **3% annuo del valore nominale, sia long sia short**, per cambi,
  argento e indici; oro: listino FP dell'appendice AQ riscalato sul prezzo
  (-0,715 / +0,325 $/oncia/notte a 4.156,98 $).
- Ogni regola si misura anche con costi di transazione x1,5 (swap invariato).

## Famiglie (un agente ciascuna)

1. **Trend following sul paniere**: TSMOM 1, 3, 12 mesi; Donchian 20/10 e
   55/20; medie 50/200 — parametri **canonici**, nessuna griglia; posizione
   per mercato a rischio uguale (stop 2 x ATR20 o dimensionamento sulla
   volatilita' a 60 giorni).
2. **Ritorno alla media di qualche giorno**: dopo N giorni consecutivi nello
   stesso verso o un movimento di k x ATR in 1-5 giorni, entra contro e tieni
   1-10 giorni; con e senza filtro di tendenza di fondo (media 200).
3. **Forza relativa fra mercati**: ogni settimana/mese ordina i mercati per
   rendimento passato aggiustato per la volatilita' (1-12 mesi); long i
   primi, short gli ultimi (e variante solo long/solo short).
4. **Breakout multi-giorno con stop larghi**: rottura del massimo/minimo di N
   giorni o della settimana precedente, stop e uscita in ATR o a trailing,
   tenuta fino a qualche settimana.

## Promozione (sulla sola scoperta)

Misura principale: **somma in R del portafoglio per mese** (rischio uguale per
operazione).
- Regole **canoniche** (famiglia 1 e le varianti di letteratura dichiarate
  come tali, al massimo 10 in tutto): netto > 0 a x1 e x1,5, **t >= 2** sui
  rendimenti mensili, anni positivi >= 5/8, placebo p < 0,05.
- Regole **da griglia** (famiglie 2-4): netto > 0 a x1 e x1,5, **t >= 3**,
  anni >= 6/8, placebo p < 0,01.
- Placebo: stessi istanti e durate con direzione casuale (e per la famiglia 3
  classifiche casuali); >= 1000 serie, seed fisso.
- Al massimo 3 candidati per famiglia. Si riportano anche numero di
  operazioni al mese e drawdown in R.

## Verifica (una volta sola, 2018 -> fine dati)

Netto > 0 a x1 e x1,5 con swap; t >= 2 (k = 1) o soglia di Bonferroni sul
numero di candidati (2,4 se k = 2-3; 2,6 se 4-5; 2,8 fino a 10); anni
positivi >= 2/3; placebo come in scoperta.

## Previsioni

1. Il trend following sul paniere sara' positivo al lordo, ma con 12 mercati
   il t restera' fra 1 e 2 (la letteratura usa 50+ mercati).
2. Il ritorno alla media di qualche giorno funzionera' sugli indici (lo hanno
   visto F2-F4 della ricerca da zero) e non sui cambi.
3. Al massimo un candidato passera' la verifica.
