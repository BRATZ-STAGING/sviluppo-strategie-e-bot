# Quali dati esistono, e cosa coprono

Risposta alla prima domanda di qualunque campagna di backtest: **su cosa sto
girando?** Aggiornato al 30/07/2026.

## 1. Candele M1 — nel repository

`data/XAUUSD_M1/XAUUSD_M1_<anno>.parquet`, un file per anno.

| | |
|---|---|
| periodo | 2020-01-01 → 2026-07-06 |
| righe | 2,31 milioni |
| prezzi | **BID** |
| fuso | UTC, candele etichettate all'APERTURA |
| peso | 39 MB |

Fonte Dukascopy. E' la base di tutti gli studi in `docs/studies/`.

## 2. Tick bid+ask — sul PC, NON nel repository

Convertiti in Parquet mensili con `trading/scripts/build_tick_parquet.py`, in
`C:\dukascopy\parquet_out` sul PC di origine (piu' la cache `.bi5` originale in
`C:\dukascopy\ticks_cache`).

| | |
|---|---|
| periodo | **2022-11-01 → 2026-07-06** (45 mesi) |
| tick | **222.378.654** |
| peso | 1.244 MB |
| ore mancanti | **zero** (le 528 di luglio 2026 sono il mese non ancora concluso) |
| verifica ask ≥ bid | superata su tutti i tick |

`INDICE.csv` nella stessa cartella riporta per ogni mese: numero di tick, spread
mediano, ore mancanti, peso.

**In corso**: backfill 2020-01 → 2022-10 (34 mesi). Riavviabile, non riscarica
cio' che ha in cache.

### Lo spread mediano, misurato

| periodo | spread |
|---|---|
| 2023 | 0,32 - 0,34 $ |
| 2024 | 0,33 → 0,44 $ |
| 2025 | 0,51 → 0,70 $ |
| 2026 | 0,58 → **0,89 $** (massimo: febbraio 2026) |

**Lo spread e' triplicato in tre anni.** Qualunque backtest con spread fisso
sopravvaluta i periodi recenti. Dettagli e impatto misurato in
`docs/studies/rr-intraday-study.md`, appendice N.

## 3. Cache tick del broker FP dentro MT5

44 mesi circa, secondo gli appunti del progetto. **Non verificata** in questo
repository: copertura, buchi e trattamento dello spread sono da accertare prima
di usarla per qualcosa. Se una campagna di backtest si appoggia a questa cache,
il primo passo e' confrontarla con i tick Dukascopy sulla finestra comune.

### Verifica incrociata FP contro Dukascopy sulle candele M1 (01/08/2026)

Fatta con `trading/scripts/confronta_fonti.py mt5 2026` sul PC, 73.896 minuti
comuni (22/04 - 31/07/2026, il piu' indietro concesso dal terminale):

| | |
|---|---|
| scostamento orario server FP | UTC+3, rilevato automaticamente |
| differenza mediana delle chiusure | 0,205 $ |
| di cui SISTEMATICA | **+0,195 $** (FP quota sopra il bid Dukascopy) |
| p95 | 0,415 $ |
| minuti oltre 0,5 $ | 2,6% |
| massimo | 21,4 $ (un minuto isolato, maggio) |

Lettura: quasi tutta la differenza e' uno scostamento di LIVELLO costante
(~20 centesimi, cioe' FP sta dentro lo spread Dukascopy), non rumore. Tolto
quello, il residuo tipico e' sotto i 10 centesimi: **le due fonti raccontano
lo stesso mercato**. Uno scostamento costante non tocca la strategia (ingresso,
stop e obiettivo si spostano insieme); la coda di minuti oltre 0,5 $ sono i
picchi di news, ed e' un motivo in piu' per cui gli stop da 2-3 punti erano
fragili. Per confrontare anche 2024-2025 serve alzare "Max barre nel grafico"
a Unlimited e RIAVVIARE MT5 (il tetto da 100.000 barre tronca anche l'API).

## Perche' importa quale si usa

Le tre fonti non sono interscambiabili.

- Le **candele M1** non dicono cosa succede dentro il minuto: su un bot con stop
  piu' piccoli di una candela i fill sono ottimistici. Misura fatta sul bot
  Keltner: 47% di operazioni vincenti su M1 contro 31% su tick.
- I **tick Dukascopy** hanno bid e ask veri, quindi lo spread reale variabile —
  ma coprono solo da novembre 2022 (per ora).
- La **cache FP** e' del broker su cui si opera davvero, quindi in teoria e' la
  piu' fedele, ma non e' stata verificata.

Un confronto fra due backtest su fonti diverse non vale niente. Prima si fissa
la fonte, poi si confrontano le varianti.
