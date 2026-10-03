# Consegna: avviare i bot sul VPS — 04/08/2026

> **CORREZIONE 04/10/2026.** La tabella del paragrafo 1 veniva da
> `verifica_bot.py`, che aveva due difetti: cercava la chiusura di fine
> giornata nella candela delle 21:00 UTC, che con l'ora legale USA non esiste
> (d'estate "in uso" e 1:2 restavano aperte per giorni), e la A non chiudeva
> mai il venerdi'. Corretti (commit f32f32f; dettaglio in
> `docs/studies/verifica-bot-discrepanze.md`), i numeri coincidono con quelli
> del motore ufficiale. La B non cambia. Cambiano: in uso da +214,7 a
> **+163,2 R** (DD 20,8 -> 16,3, 23 -> **11** perdite di fila, 6/7 -> **7/7**),
> A da +206,2 a **+181,3 R** (DD 26,3 -> 15,9, 24 -> 15 di fila), 1:2 da +86,6
> a **+71,3 R** (6/7 -> **5/7**). **Conclusioni cambiate**: la B resta la prima
> da avviare (miglior R/DD), ma non e' piu' "l'unica senza un anno in
> perdita" (lo sono anche in uso e A) e la 1:2 ha due anni negativi, non uno.

Questo file esiste per una cosa sola: permettere a una sessione nuova di
**mettere in produzione le strategie senza rifare la ricerca**. La ricerca e'
finita e i suoi esiti sono qui sotto in forma corta. Chi vuole i dettagli
trova tutto in `docs/studies/rr-intraday-study.md`, appendici da BJ a CC.

Leggere in quest'ordine: questo file, poi `bots/SCHEDE-STRATEGIE.md` (che e'
la specifica implementativa completa, con l'aggiornamento del 04/08 in fondo),
poi `docs/vps.md` per la macchina.

---

## 1. Cosa si avvia

Quattro varianti dello **stesso ingresso** (reclaim del VWAP giornaliero su
M6, sette condizioni, tutte in `bots/SCHEDE-STRATEGIE.md`). Cambia solo la
gestione dell'uscita. Numeri su **2020-2026, 333 operazioni, spread vero**:

| | R totale | R/op | vinte% | DD R | R/DD | anni+ | anno peggiore | mesi+ | perdite di fila |
|---|---|---|---|---|---|---|---|---|---|
| **B** — 1:8, trail MFE−2 da +3R, weekend se >+1R | +174,6 | 0,52 | 38,4% | 12,6 | **13,85** | **7/7** | +11,9 R | **55,1%** | 12 |
| in uso — 1:10, pareggio +3R, EOD 21 UTC | +163,2 | 0,49 | 35,7% | 16,3 | 10,02 | **7/7** | +8,4 R | 49,3% | 11 |
| A — 1:8, pareggio +3R, chiude venerdi' | **+181,3** | **0,54** | 24,0% | 15,9 | 11,44 | **7/7** | **+12,9 R** | 43,5% | 15 |
| 1:2 secco, niente pareggio, EOD | +71,3 | 0,21 | **48,1%** | **10,9** | 6,52 | 5/7 | −2,6 R | 52,2% | **7** |

**Da avviare per prima: la B.** Non e' quella che rende di piu' in R (e' la A),
e' quella che rende di piu' per unita' di sofferenza (R/DD 13,85 contro 11,44
della A e 10,02 della in uso) e con piu' mesi positivi. Non e' piu' l'unica
senza un anno in perdita: con i numeri corretti anche in uso e A sono 7/7, e
la A ha l'anno peggiore migliore (+12,9 R). Per un 6% annuo: rischio **0,24%
per operazione**, perdita massima attesa **3,0% del conto**.

I numeri della in uso coincidono con quelli del motore ufficiale (tabella
2020-2026 di `bots/SCHEDE-STRATEGIE.md`, +171,97 R con spread 0,30); per A e
B quella tabella include lo swap, che qui non c'e'.

Riprodurre i numeri: `XAU_ANNI=2020-2026 python3 trading/scripts/verifica_bot.py`

---

## 2. Le tre cose da decidere PRIMA di avviare

### a) La regola di spegnimento

Va scritta prima di partire, non dopo il primo drawdown. Proposta:
**fermarsi a −15 R** di perdita dal massimo. E' oltre il peggio del periodo
buono (12,6 R per la B) ed entro il peggio del periodo cattivo (87,4 R).
Senza una soglia decisa a freddo, la decisione la prende la paura.

### b) Il dimensionamento

Sulla perdita massima del **periodo cattivo** (2009-2019: 51,7 R per la
strategia in uso, 87,4 per la B), non su quella del periodo buono. Con lo 0,24%
per operazione, 87 R di drawdown farebbero il 21% del conto: sopportabile.
Con l'1% farebbero l'87%: non sopportabile.

### c) Il broker

Lo spread e' il parametro piu' importante che NON dipende da noi. Misurato su
6,1 milioni di tick Dukascopy: **0,63 $ nel 2025-2026**, raddoppiato dal 2023.
Chiedere al broker lo spread medio su XAUUSD e in quali orari. Sotto 0,20 $
cambiano molte cose; sopra 0,50 $ e' quello con cui abbiamo fatto i conti.

---

## 3. Il registro in avanti — la cosa piu' importante di questa consegna

`grafico_live.py` scrive ogni segnale su `registro_segnali.jsonl`: l'istante in
cui e' stato **visto**, bid e ask reali, entry, stop, rischio, lo stato di
struttura di tutti i timeframe, e quali condizioni erano vere. Registra anche i
**"vicino"** (una sola condizione mancante).

Perche' conta piu' di qualunque altro studio: il 2009-2019 e' stato escluso per
decisione e il 2023-2026 e' servito a scegliere le configurazioni. **Non resta
nessun fuori campione.** Ogni numero di questo repository e' ormai dentro il
campione su cui e' stato scelto. Il registro e' l'unico modo di produrne uno
nuovo, e produce dati solo se gira.

**Farlo girare sul VPS accanto ai bot.** Variabile `REGISTRO_SEGNALI` per
cambiare il percorso; `AVVISO_URL` per il webhook Telegram.

---

## 4. Cosa NON rifare (misurato oggi, esito negativo)

Otto strade chiuse. Riaprirne una senza un'idea nuova e' tempo perso.

| strada | appendice | esito |
|---|---|---|
| gestione a scaglioni (3 uscite 1/1,5/2) | BM | −80% di rendimento per −20% di drawdown (corretto 04/10/2026; prima: −85% / −32%) |
| stop e obiettivi a punti fissi | BM, BO | il costo e' il doppio del vantaggio lordo |
| soglie in unita' di volatilita' | BO, BX | stabilizza la regola, non crea vantaggio |
| conferme fini su M1/M3 (5 famiglie) | BP | nessuna regge; il placebo separa piu' di tutte. **Corretto 04/10/2026, appendice BP**: con la chiusura delle 21 ne reggono quattro su cinque e il placebo no; la distanza dal VWAP (terzo medio +0,377 / +0,382 R/op) si stacca dal placebo. Solo 2020-2026: da verificare sui 18 anni |
| ritracciamenti in zona (27.127 eventi) | BQ | vantaggio lordo zero |
| confluenza fra zone di TF diversi | BV | il placebo regge, le ipotesi vere no |
| qualita' delle zone (5 misure) | BU | il placebo separa piu' di tutte e cinque |
| allargare la zona raffinata | BY | il vantaggio lordo scende |
| scalp da zero: media, orologio, candele, livelli | CB, CC | il solo effetto vero (ritorno alla media) e' 5-10 volte sotto la soglia dei costi |
| ORB di Crabel su oro e su S&P | BJ, BK, BL | l'autore stesso dice che e' rotta; misurato, non basta |

**La lezione di metodo**: in questo progetto il placebo — un numero casuale
trattato come un'ipotesi — ha battuto o pareggiato le ipotesi vere in
**quattro studi su cinque**. Con qualche migliaio di operazioni, 0,1-0,5 R/op
di separazione apparente nasce dal nulla. Qualunque idea nuova va misurata
contro un placebo, o non e' stata misurata.

---

## 5. La sola direzione che si e' mossa nella direzione giusta

**Lo stesso tipo di strategia sull'indice S&P invece che sull'oro.**

| | oro | indice S&P |
|---|---|---|
| spread | 0,33 -> **0,63 $** (raddoppiato dal 2025) | **0,507 punti, fermo da dieci anni** |
| rischio tipico | 4,5 $ | 7 -> 32 punti |
| **costo in % del rischio** | **7,6-9,8%** | **2,8-3,8%, e in calo** |

L'indice e' passato da 2.100 a 6.400 punti con lo spread immobile: il costo
relativo continua a scendere (≈1,6% nel 2026). L'oro peggiora. **A parita' di
vantaggio lordo l'indice rende due-tre volte di piu'** — ed e' esattamente il
parametro che ha ucciso ogni tentativo di scalp sull'oro.

Prima di lavorarci: `trading/scripts/scarica_indice.py` aveva due bug che
hanno perso interi anni (`--fail-early` marcava i giorni come vuoti per
sempre; i file troncati sparivano senza un secondo tentativo). **Corretti ma
non rilanciati**: vanno cancellati i marcatori `.empty` degli anni mancanti
(BID 2022, 2024, 2026 e ASK 2025) e rifatto lo scarico.

---

## 6. Note operative

- **Il container e' effimero e si e' gia' ripristinato due volte** durante la
  sessione del 04/08, riportando il checkout indietro di dodici commit. Il
  lavoro era salvo solo perche' era stato pushato. Pushare spesso non e' una
  buona abitudine in questo progetto: e' l'unica difesa.
- MT5 gira sul VPS Windows, accesso solo RDP (niente SSH) e il pacchetto
  `MetaTrader5` e' solo Windows. Da un container Linux non ci si arriva: gli
  script che leggono il terminale vanno lanciati dentro la sessione RDP.
- La porta 8080 sul VPS e' occupata dal bot Meta di un altro progetto: usare
  la 8090.
- Test: `cd trading && python3 -m pytest tests/ -q`.

---

## 7. Il cappello onesto

Le strategie rendono in ogni anno dal 2020 al 2026 (tutte tranne la 1:2, che
ha due anni negativi) e perdono tutte sul 2009-2019, anche se non in ogni anno: in uso -39,6 R (2 anni positivi su 11), A -45,1 R (4 su 11), B -88,4 R (1 su 11), 1:2 -55,0 R (motore ufficiale, spread 0,30, swap reale; prima del 04/10 qui c'era scritto "perdono in undici anni su undici", che era falso). Non ho trovato **nessuna** grandezza misurabile del mercato che
cambi insieme al risultato: volatilita' relativa al prezzo, spread relativo,
quota di escursione notturna, persistenza infragiornaliera, direzionalita' e
tendenza di fondo sono uguali nei due periodi.

Questo lascia due possibilita', e nessuna delle due si puo' escludere da qui:
il vantaggio e' reale e legato a qualcosa che non abbiamo saputo misurare,
oppure e' il risultato di aver cercato dentro il 2020-2026. Le misure
disponibili — l'1% di configurazioni che sopravvivono al cambio di periodo
contro il 64% nel verso opposto — puntano verso la seconda.

Avviarle e' legittimo, con soldi che si possono perdere e una regola di
spegnimento scritta prima. Chiamarle un vantaggio dimostrato no.
