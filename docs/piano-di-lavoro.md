# Piano di lavoro

Lo aggiorna SOLO la chat di **Regia** (vedi `docs/COME-USARE-LE-CHAT.md`).
Le altre chat lo leggono per sapere cosa fare e segnano qui quando chiudono
un blocco (una riga nel registro in fondo).

## Dove siamo (aggiornare a ogni Regia)

- Al 06/10/2026: ~45.000 regole testate su oro, cambi, indici, paniere
  multi-giorno e dati macro (famiglie A-E, crollo->conferma: zero candidati);
  **nessuna strategia dimostrabile con costi retail** (`docs/strade-respinte.md`).
- La **B** e' l'unica cosa in piedi, come scommessa sul regime e non come
  vantaggio: +0,52 R/op nel 2020-2026, -0,24 nel 2009-2019, crolla nelle stesse
  condizioni in cui guadagna (`docs/studies/crolli-b.md`). Primo fuori campione
  vero lug-ott 2026 su dati MT5: 7 op, -4,3 R, ne' allarme ne' conferma
  (`docs/studies/b-fuori-campione-2026.md`).
- Unica classe di dati mai usata come segnale: **i tick bid+ask**
  (microstruttura). Oggi coprono solo nov 2022 -> lug 2026.

## Direzione scelta (Regia 06/10/2026)

**Due binari.**

1. **Produzione**: la B verso la demo come scommessa sul regime. Rischio
   tarato sulla perdita massima VERA dei 18 anni (91 R, non 13), spegnimento
   a -15 R dal massimo (`docs/studies/b-prima-della-demo.md`). Prima della
   demo: EA, confronto operazione per operazione col motore Python, e il
   fuori campione 2026 rifatto con Dukascopy.
2. **Ricerca**: **un'ultima scommessa sui tick come segnale** (squilibrio,
   spread, intensita', velocita'), coerente con l'obiettivo scalp. Protocollo
   registrato prima dei dati, chiuso sul periodo piu' lungo che i tick
   permettono.

**Vincolo dell'utente**: l'obiettivo scalp/intraday (>= 1-2 operazioni al
giorno, oro o cambi, FP Markets Raw) **resta vincolante finche' la strada
non e' completamente bloccata**. Criterio di blocco, da scrivere nella
registrazione dello studio tick: se nessuna regola sui tick passa la verifica
con i costi Raw, la strada scalp si considera chiusa e la Regia successiva
rinegozia l'obiettivo (frequenze piu' basse) o chiude la ricerca di nuove
strategie.

**In coda, non bloccanti** (protocolli gia' registrati, da eseguire solo se
c'e' tempo libero o se servono): fx-intraday, fx-combinata (verifica),
campagna Keltner. Niente nuove famiglie fuori da questi due binari.

## Prossimi blocchi (in ordine)

| # | area | blocco | stato |
|---|---|---|---|
| 1 | Regia | decidere la direzione | fatto 06/10 |
| 2 | Dati | inventario tick su D: (descrivere in `docs/registro-dati.md`) ed estensione Dukascopy XAUUSD bid+ask all'indietro verso il 2009 con `download_ticks.py` (riavviabile); completare anche le M1 2026 oltre il 06/07 | da fare |
| 3 | Ricerca | registrazione preventiva dello studio tick: segnali, orizzonti scalp, costi Raw istante per istante, scoperta/verifica, **criterio di blocco della strada scalp**. Prima `archivista`, poi `verificatore` sul protocollo | da fare (puo' partire mentre gira il blocco 2) |
| 4 | Backtest | EA della B per MT5 (`docs/AVVIO-MT5-VPS.md`, le sette trappole) e confronto operazione per operazione col motore Python | da fare (in parallelo a 2-3) |
| 5 | Ricerca | fuori campione B lug-ott 2026 rifatto con `FONTE=dukascopy` (dipende dal blocco 2) | in attesa dati |
| 6 | Ricerca | studio tick: scoperta, poi verifica una volta sola; `verificatore` prima del verdetto | dopo 2 e 3 |
| 7 | Backtest | avvio demo della B: rischio sulla perdita massima vera, spegnimento -15 R, regole scritte prima | dopo 4 e 5 |
| 8 | Regia | verdetto: strada scalp chiusa o aperta, cosa fare della B dopo la demo | dopo 6 |

## Registro dei blocchi chiusi

| data | area | blocco | esito in una riga | dove sono i dettagli |
|---|---|---|---|---|
| 06/10/2026 | Regia | direzione | due binari: B verso la demo come scommessa sul regime; ultima scommessa di ricerca sui tick, scalp vincolante finche' la strada non e' bloccata | questo file, "Direzione scelta" |
