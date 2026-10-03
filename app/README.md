# Grafico XAUUSD (web app)

Grafico simil TradingView, solo per uso personale: candele dall'archivio M1
del repository, disegni salvati, risultati dei backtest sopra il grafico.
Libreria grafica: [KLineChart](https://github.com/klinecharts/KLineChart) 10.0.3
(Apache-2.0), caricata da jsDelivr.

## Avvio

Doppio clic su `app\avvia.bat`, oppure:

    python app\server.py            solo archivio
    python app\server.py --mt5      archivio + ultime settimane dal terminale MT5

Poi `http://127.0.0.1:8095` (porta cambiabile con `APP_PORTA`). Con `--mt5`
il server apre il terminale se e' chiuso: per questo non e' acceso di default.

Il server ascolta solo su `127.0.0.1`. **Non esporlo su internet** senza
autenticazione e HTTPS (vedi `docs/piano-app.md`). Sul VPS la porta 8080 e'
occupata.

## Cosa c'e'

- timeframe da M1 a MN1 (anche M33 e M66 del progetto, ancorati all'epoch).
  Nella barra ci sono i preferiti; l'elenco completo e' nel menu accanto, e
  la stella mette o toglie un timeframe dalla barra (scelta salvata nel
  browser). D1, W1 e MN1 come li mostra il broker: la giornata va dalle 17:00
  alle 17:00 di New York (la domenica sera e' gia' lunedi'), la settimana da
  domenica sera a venerdi', il mese raccoglie le giornate con quella data
- zoom: rotellina in largo, MAIUSC+rotellina (o sulla scala dei prezzi) in
  alto, CTRL+rotellina tutti e due; pulsanti nella barra e "Adatta" per la
  scala automatica
- indicatori: MA, EMA, Bollinger, SAR sul prezzo; volume, RSI, MACD sotto
- disegni: trendline, semiretta, retta, orizzontali, verticale, canale,
  zona (con etichetta), nota, Fibonacci, rischio/rendimento (tre clic:
  ingresso, stop, obiettivo). Valgono su tutti i timeframe; dal riquadro a
  destra si sceglie dove nasconderli. Salvati in `app/dati/disegni.json`
  (fuori da git)
- backtest: elenco in `app/backtest/catalogo.json`

## Aggiungere un backtest

Una voce nel catalogo:

```json
{"id": "nome-breve", "nome": "Nome nel menu", "file": "percorso/dal/repo.csv", "rr": 10}
```

Il file (CSV o Parquet) ha una riga per operazione. Colonne obbligatorie:
`time` (ingresso, UTC), `lato` (long/short), `entry`. Facoltative: `stop`,
`target`, `exit_time`, `exit_price`, `R`. Se `R` manca ma ci sono uscita e
stop, si calcola. `rr` disegna l'obiettivo quando il file ha solo lo stop.

Prima versione: l'app **mostra** i risultati, non lancia backtest.
