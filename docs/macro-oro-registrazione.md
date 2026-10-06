# Oro: macro, paura, posizionamento, flussi ed eventi — protocollo registrato (06/10/2026)

Richiesta dell'utente: cercare un vantaggio sull'oro con informazioni che NON
sono il prezzo (tutte le ricerche precedenti usavano solo il prezzo e sono
fallite: ~43.000 regole). Scritto prima di qualunque calcolo su questi dati.

## Dati (D:\ricerca_macro, preparati da `trading/scripts/prepara_macro.py`)

| fonte | serie | uso |
|---|---|---|
| Tesoro USA | rendimento reale TIPS 5 e 10 anni, nominale 2 e 10 anni, breakeven 10 anni | tassi reali e attese d'inflazione |
| Fed di New York | Fed funds effettivo | politica monetaria |
| CBOE | VIX, GVZ (volatilita' implicita dell'oro) | paura, premio per la volatilita' |
| CFTC COT disaggregato | managed money, produttori, swap dealer, **piccoli trader** (proxy del retail), open interest | posizionamento "grandi contro piccoli" |
| SPDR GLD | tonnellate d'oro detenute | flussi istituzionali |
| cambi del paniere | indice del dollaro sintetico (pesi DXY senza SEK) | dollaro |
| calendari pubblici (Fed, BLS) | date FOMC, CPI, NFP 2009-2026 (li costruisce l'agente E) | eventi |

**Regole d'informazione** (scritte in `prepara_macro.py`, vincolanti): alla
chiusura della giornata d'oro D (22:00 UTC) si possono usare VIX/GVZ della
data D, Tesoro/Fed funds/GLD della data **D-1**, il COT dalla chiusura del
**venerdi' di pubblicazione** (martedi' + 3 giorni lavorativi). Entrata
all'apertura della giornata successiva. Gli eventi si usano solo con date
note in anticipo (calendario), mai con l'esito del dato.

**Periodi**: scoperta **2009-2017**, verifica **2018 -> 07/2026**, separate
fisicamente (`D:\ricerca_macro\scoperta|verifica\`). Per queste regole il
2018-2026 dell'oro e' pulito: nessuna regola fin qui ha usato dati macro.

## Costi

Prezzo dell'oro dal paniere D1 (BID Dukascopy). Round trip 0,46 $ fino al
2019, poi `SPREAD` di `verifica_bot.py` + 0,06 $; anche x1,5. Swap FP
(appendice AQ) riscalato sul prezzo, x3 il mercoledi'. Operazioni intraday
sulle M5 di `D:\ricerca_zero\scoperta\XAUUSD_M5.parquet` se servono.

## Famiglie (un agente ciascuna)

- **A — Tassi e dollaro**: variazioni dei tassi reali, del breakeven, del 2
  anni e del dollaro su 1-20 giorni predicono l'oro nei 1-20 giorni dopo?
  Regimi (es. oro long solo con tassi reali in calo sulle ultime 20-60
  giornate).
- **B — Paura e volatilita'**: oro dopo i picchi di VIX (bene rifugio o
  liquidazione?), livello e variazioni del GVZ, GVZ contro volatilita'
  realizzata come filtro.
- **C — Posizionamento COT**: managed money e piccoli trader netti in % dell'open
  interest, estremi (percentili sui 3 anni precedenti) come segnale contrarian
  o di tendenza; variazioni settimanali; produttori come "mani forti".
- **D — Flussi ETF GLD**: variazione delle tonnellate su 1, 5, 20 giorni;
  flussi estremi; divergenza fra flussi e prezzo.
- **E — Eventi macro**: comportamento dell'oro prima/dopo FOMC, CPI, NFP
  (deriva, volatilita', rientro), con date da calendario.

## Promozione (sulla sola scoperta)

Netto > 0 a x1 e x1,5 con swap; **t >= 3** (rendimenti mensili o operazioni
non sovrapposte); anni positivi >= 7/9; placebo p < 0,01 (stessi istanti con
direzione casuale, e per le regole "solo long" date casuali nello stesso
regime); al massimo 3 candidati per famiglia. Ogni agente dichiara prima la
griglia e il numero di varianti.

## Verifica (una volta sola)

Soglia di t per numero di candidati k: 2 (k=1), 2,4 (2-3), 2,6 (4-5), 2,8
(6-10), 3,0 (oltre); netto > 0 a x1 e x1,5; anni positivi >= 2/3; placebo
p < 0,05.

## Previsioni

1. I tassi reali spiegano l'oro nello stesso giorno ma non lo anticipano:
   famiglia A senza candidati.
2. Il COT (estremi del managed money, contrarian) e' la famiglia piu'
   probabile a dare un candidato.
3. Gli eventi (E) mostreranno volatilita' prevedibile ma non direzione.
4. Al massimo un candidato passa la verifica.
