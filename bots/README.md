# Bot in esercizio

I bot che girano davvero, uno per cartella. Il framework in `trading/` serve a
fare ricerca; qui sta il codice che opera sul mercato, con abbastanza contorno
da poterlo confrontare con i risultati della ricerca.

## Struttura

    bots/
      mt5/<nome>/        Expert Advisor MQL5
      ctrader/<nome>/    cBot cTrader (C#)

Ogni cartella contiene:

| file | cosa |
|---|---|
| il sorgente | `.mq5` / `.mqh` per MT5, `.cs` per cTrader |
| `parametri/` | i preset in uso (`.set` per MT5, `.xml` o screenshot per cTrader) |
| `README.md` | la scheda del bot, vedi sotto |
| `backtest/` | report esportati, se ci sono (HTML, CSV) |

**Non committare**: gli eseguibili compilati (`.ex5`, `.dll`, `.algo`) — si
rigenerano dal sorgente e sono binari inutili in un repository. Ne' credenziali,
numeri di conto o token dei broker.

## La scheda di ogni bot (`README.md`)

Va scritta perche' fra sei mesi nessuno si ricorda com'era tarato. Serve:

- **cosa fa**, in tre righe: quale segnale cerca, come entra, come esce
- **strumento e timeframe** su cui gira
- **stato**: demo o reale, da quando, su che capitale
- **parametri in uso**, con i valori (non "quelli di default")
- **rischio per operazione** e come e' calcolata la size
- **risultati noti**: periodo, numero di operazioni, risultato, perdita massima
- **cosa non e' stato verificato**: la parte piu' utile della scheda

## Perche' stanno qui

Con il sorgente e i parametri nel repository si possono fare due cose che
altrimenti restano impossibili:

1. **Confrontarli con la strategia tarata** sugli stessi dati e con le stesse
   convenzioni conservative (stop che vince sull'obiettivo, spread di andata e
   ritorno, nessun lookahead). Un confronto fra un backtest fatto in MT5 e uno
   fatto qui non vale niente se le convenzioni non sono le stesse.
2. **Ri-verificarli sui tick reali** invece che sulle candele. Sui bot con
   ordini limite e stop piu' piccoli di una candela M1 la differenza e' grossa:
   la misura fatta dal collaboratore dava 47% di operazioni vincenti su M1
   contro 31% su tick.

## I bot presenti

| cartella | stato | vantaggio dimostrato? |
|---|---|---|
| `mt5/keltner-impulse` | forward demo dal 05/07/2026, 21 operazioni | **no** — backtest su tick reali negativi |
| `mt5/keltner-dd-archiviato` | archiviato | no, idea bocciata (-21,6 R contro +1,3 R) |
| `ctrader/keltner-impulse` | solo backtest, l'originale della logica | no, il +164,6% e' in campione e su fill ottimistici |
| `ctrader/keltner-mid-reversion` | mai backtestato | mai misurato |

Nessuno dei bot in esercizio ha un vantaggio dimostrato. La strategia in
`trading/` invece si', su sette anni e fuori campione: il confronto sta in
`docs/studies/rr-intraday-study.md`.
