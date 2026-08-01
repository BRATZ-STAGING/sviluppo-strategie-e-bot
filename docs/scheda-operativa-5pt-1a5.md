# Scheda operativa — stop fisso 5 punti, obiettivo 1:5

Variante a stop fisso della strategia validata. Stessi segnali, meccanica di
uscita semplificata per l'esecuzione manuale. Numeri misurati su 348 operazioni
2020-2026 con spread reale (0,63 $) e **verificati con ricalcolo indipendente**
(griglia completa in appendice T dello studio).

Non e' la configurazione migliore in assoluto — la taratura ufficiale
(stop strutturale, 1:10, pareggio +3R) rende di piu' (35.816 € contro 30.057 €
a parita' di drawdown) — ma e' la piu' semplice da eseguire a mano: stop fisso,
niente pareggio da gestire, un solo obiettivo.

## Le regole (tutte, non ce ne sono altre)

**Quando cercare il segnale**: solo dalle **7:00 alle 19:00 UTC** (9-21 ora
italiana estiva). Massimo **3 operazioni al giorno**, almeno 30 minuti fra due
segnali.

**Il segnale (long; lo short e' speculare)** — candela M6 che:
1. tocca il **VWAP giornaliero** dal basso della candela (il minimo va sotto o sul VWAP)
2. **chiude sopra** il VWAP e **sopra il massimo della candela precedente**
3. prima del tocco, nel corso della giornata, il prezzo si era allontanato dal
   VWAP di almeno **4 $** (nei mesi ad alta volatilita' la soglia scala con l'ATR)
4. struttura allineata: **H6, H2, M33 e H12 in trend rialzista** (ultimo BOS/CHOCH
   verso l'alto), **M12 in trend ribassista** (= stai comprando il ritracciamento)
5. chiusura del giorno precedente **sopra la media a 50 giorni** (per i long)

**Ingresso**: a mercato alla chiusura della candela segnale.

**Stop**: ingresso **− 5,00 $** esatti. Non si sposta MAI: niente pareggio,
niente trailing. (Misurato: il pareggio su questa configurazione toglie dal
20% al 70% del risultato a seconda della soglia. La colonna "senza" vince.)

**Obiettivo**: ingresso **+ 25,00 $** (1:5).

**Chiusura forzata alle 21:00 UTC** di ogni posizione ancora aperta. NON e'
opzionale: il 29,9% delle operazioni chiude cosi', e li' sta gran parte del
profitto. Saltare la chiusura serale cambia la strategia in un'altra, mai
misurata.

## La size

`lotti = (conto × rischio%) / 5`. Con 0,01 lotti, 5 $ di stop = 5 $ di rischio.

| conto | 0,5% | 1% |
|---|---|---|
| 1.000 € | 0,01 | 0,02 |
| 5.000 € | 0,05 | 0,10 |
| 10.000 € | 0,10 | **0,20** |

Una sola posizione alla volta. Se c'e' gia' una posizione aperta, i nuovi
segnali si ignorano.

## Cosa aspettarsi (leggere PRIMA di iniziare, rileggere durante)

Numeri misurati su 6,5 anni, non opinioni:

| | |
|---|---|
| operazioni vinte | **37,1%** — quasi due su tre sono stop o chiusure in perdita |
| esiti | 58,3% stop · 11,8% obiettivo · 29,9% chiusura serale |
| operazioni | 4-5 al mese (54 l'anno); **un mese su 11 senza segnali** |
| striscia di stop piu' lunga | **12 consecutivi** (storica); 8 e' normale in ogni blocco di 50 |
| finestre di 20 operazioni | il **36,5% sono negative**; intervallo normale da −6 a +25 R; la peggiore storica −10 R |
| tempo sotto il massimo | l'**84,5%** del tempo il conto e' sotto un massimo precedente |
| anni | 2020 +11,4 · **2021 −7,8** · 2022 +45,0 · 2023 +2,7 · 2024 +21,7 · 2025 +25,8 · 2026 +1,9 |

**Un anno intero puo' chiudere in perdita** (il 2021 lo fece) e un altro quasi
in pari (2023). Chi non regge un anno piatto non deve iniziare: mollare durante
la striscia e' l'unico modo sicuro di trasformare queste statistiche in perdita.

## Quando giudicare, e quando fermarsi

- **Non giudicare prima di 50 operazioni** (circa un anno). Sotto quella soglia
  qualunque risultato — buono o cattivo — e' compatibile con il caso.
- Dopo 20 operazioni: se sei **fra −6 e +25 R sei nella norma storica**.
  Sotto −10 R sei oltre la peggior finestra mai misurata: ferma e rivedi
  l'esecuzione (di solito il problema e' l'identificazione manuale del segnale,
  non la strategia).
- **Interruttore di emergenza**: drawdown oltre **20 R** (lo storico massimo e'
  14). Li' si ferma tutto e si confronta il diario con il backtest.

## Il diario (obbligatorio, non facoltativo)

Per ogni operazione: data/ora UTC, direzione, ingresso, stop, obiettivo, esito
(SL / TP / chiusura serale), R realizzato, e **una riga sul perche' il segnale
sembrava valido**. Senza diario non c'e' modo di distinguere "la strategia non
funziona" da "sto eseguendo un'altra strategia" — ed e' quasi sempre la seconda.

## Il punto debole, detto chiaro

Il backtest identifica i segnali con il codice; a mano, la lettura dei trend su
cinque timeframe divergera'. **Le prime 20 operazioni vanno fatte in demo**,
confrontando ogni segnale preso a mano con quelli che il framework avrebbe
preso (si verificano a posteriori con `trading/scripts/`). Se piu' di 5 su 20
non coincidono, il problema e' la lettura manuale e i numeri di questa scheda
non si applicano. La soluzione strutturale e' codificare il segnale in un
Expert Advisor: e' il passo successivo sensato se il forward manuale regge.
