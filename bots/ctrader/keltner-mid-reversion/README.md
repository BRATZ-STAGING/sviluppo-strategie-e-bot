# KeltnerMidReversionBot — cTrader

**Mai backtestato.** Solo codice: non esiste un singolo numero su questo bot.

## Cosa fa

Entra a mercato sulla candela che chiude fuori dalla banda di Keltner,
scommettendo sul rientro. Obiettivo sulla linea mediana del canale, rapporto
rischio/rendimento 1.

## Stato

| | |
|---|---|
| backtest | **nessuno** |
| forward | **nessuno** |
| parametri in uso | nessuno, mai messo in esercizio |

## Cosa serve prima di prenderlo in considerazione

Un backtest su tick reali con spread reale, con la stessa disciplina usata per
la strategia in `trading/`: selezione su un periodo e verifica su un periodo mai
usato per scegliere.

Nota di merito: e' una **reversione alla media con rapporto 1:1**. Con quel
rapporto serve piu' del 50% di operazioni vincenti solo per pareggiare, prima
dei costi. Aggiungendo spread e commissioni la soglia sale ancora — e su XAUUSD
lo spread misurato e' arrivato a 0,89 $. E' la struttura del bot, non un
dettaglio di taratura: va verificata per prima, perche' se il tasso di successo
non e' molto alto il resto non conta.
