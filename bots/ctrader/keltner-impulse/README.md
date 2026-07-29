# KeltnerImpulseBot — cTrader

L'**originale** della logica: la versione MT5 in `bots/mt5/keltner-impulse/` ne
e' la trasposizione. Solo backtest, nessun forward attivo.

## Cosa fa

Canale di Keltner su XAUUSD M10, ingresso sull'impulso a una percentuale
dell'obiettivo del canale. Stessa logica dell'Expert Advisor MT5.

## Stato

| | |
|---|---|
| conto | demo, solo backtest |
| broker | FP, conto demo da 1.000 € |
| strumento | XAUUSD, M10 |
| forward | **nessuno** |

## Parametri del run di riferimento ("run 8")

| parametro | valore |
|---|---|
| Target | 80% |
| RiskReward | 1.2 |
| Min SL | 500 pip |
| rischio per operazione | 1% |
| equity guard | 50% |
| spread | **fisso, 25** |

## Risultato del run 8

Quattro anni, modalita' m1-bars: **+164,6%**, profit factor 1,25, drawdown
28,1%.

**Questo numero non va usato.** Tre motivi, tutti sufficienti da soli:

1. e' **in campione**: i parametri sono stati scelti guardando lo stesso periodo
2. i **fill sono ottimistici**: la modalita' m1-bars non riproduce cosa succede
   dentro la candela, e su un bot con stop stretti e' la differenza fra vincere
   e perdere
3. lo **spread e' fisso a 25**, mentre la misura sui tick reali mostra che lo
   spread su XAUUSD e' triplicato fra il 2023 e il 2026 (vedi
   `docs/studies/rr-intraday-study.md`, appendice N)

**Su tick reali non si e' confermato.** Il +164,6% e' un artefatto delle
condizioni del test, non un risultato.

## Cosa NON e' verificato

Tutto quello che conta: il vantaggio fuori campione, il comportamento con fill
realistici, e il comportamento con lo spread vero.
