# Esperimento B in demo — registrazione (03/10/2026)

Decisione dell'utente del 03/10/2026: dopo la ricerca da zero (nessun
candidato) si prende la **strada (b)**, cioe' la strategia ufficiale come
scommessa sul regime, **solo in demo per ora**. Scopo: produrre il primo fuori
campione vero del progetto, a rischio zero.

## Cosa si avvia

- **Strategia**: reclaim del VWAP giornaliero su M6, sette condizioni, gestione
  **B** (obiettivo 1:8, trailing a MFE-2R da +3R, fine settimana attraversato
  solo sopra +1R), long e short. Specifica: `bots/SCHEDE-STRATEGIE.md`;
  trappole: `docs/AVVIO-MT5-VPS.md` §2.
- **Conto**: demo. Preferibilmente demo FP (stesso spread e swap del conto su
  cui si andrebbe), altrimenti si annota quale.
- **Rischio**: 0,24% per operazione, la taglia prevista per un eventuale conto
  vero (perdita massima del 2009-2019, 87-90 R, = ~21% del conto).

## Prima di partire (ordine deciso dall'utente il 03/10)

1. **Walk-forward** dal 2009 (`docs/walkforward-registrazione.md`): si decide
   se andare in demo solo dopo averlo visto.
2. **Analisi della B nel motore Python**, su 2009-2026 con lo spread vero (il
   backtest si fa qui, dove ci sono tutti i dati; il Tester di MT5 serve dopo,
   solo per confronto): risultato per anno, perdita massima (chiarire perche'
   i documenti riportano 87,4 R e 89,8 R), **durata** dei drawdown, serie di
   perdite, e la regola di spegnimento a -15 R simulata sugli anni cattivi:
   quando sarebbe scattata e quanto sarebbe costata.
3. **L'EA non esiste ancora**: va scritto (un solo EA, profilo come parametro).
4. Confronto **operazione per operazione** col motore Python su 2025-01 ->
   2026-06: stesso minuto, lato, stop, rischio. Nessuna divergenza accettata.
5. Log CSV di ogni segnale valutato (condizioni vere, VWAP, stop, rischio,
   spread): e' il registro in avanti.

## Regole decise ORA, non dopo

- **Spegnimento**: -15 R dal massimo (oltre il peggio del 2020-2026, 12,6 R).
- **Riesame**: dopo **90 operazioni** (circa un anno e mezzo). Con R/op 0,53 e
  deviazione 2,5 R servono ~90 operazioni per t = 2.
- **Esito**: se a 90 operazioni il netto per operazione e' > 0 con t >= 2, si
  valuta il conto vero allo 0,24%. Se si tocca -15 R, ci si ferma e si scrive
  perche'. In mezzo non si cambia nessun parametro.
- I numeri attesi (2020-2026): +0,52 R/op, 38% vinte, 12 perdite di fila al
  peggio. Il confronto si fa con questi, non con quelli migliori trovati dopo.

## Cosa NON e'

Non e' un vantaggio dimostrato: su undici anni indipendenti (2009-2019) la
stessa regola perde (-90,8 R con la B). E' una prova in avanti a costo zero.
