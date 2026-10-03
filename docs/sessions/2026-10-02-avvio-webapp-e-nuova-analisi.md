# 02/10/2026 — Passaggio da Cowork a Claude Code: web app + analisi da zero

> **Questionario UNA TANTUM.** La prima sessione Claude Code che legge questa
> nota pone il questionario qui sotto con lo strumento AskUserQuestion (domande
> raggruppate, max 4 per schermata), scrive le risposte nella sezione
> "Risposte" e da quel momento il questionario NON va piu' riproposto.
> Le sessioni successive leggono solo le risposte.

## Cosa ha chiesto l'utente (in Cowork)

- **Bot su XAU/USD**: per ora solo **analisi/segnali + backtest**. L'esecuzione
  via API del broker c'e' gia' come strada, si fa dopo.
- **Strategia**: ne ha una definita e altre da definire, ma vuole **ripartire
  da zero**: Claude analizza il grafico pulito e dice cosa vede.
- **Timeframe dichiarati**: intraday (M5-H1) e scalping (M1).
- **Web app simil TradingView**, solo per lei: grafici + indicatori +
  strumenti di disegno + segnali e backtest del bot sopra il grafico.
- Vuole usare il credito cloud di Claude Code (250 $, scade il 04/11/2026)
  per i lavori lunghi.

## Attriti con lo stato del repository (da chiarire nel questionario)

1. **Scalping M1 gia' respinto** (CLAUDE.md, appendice U: 47 celle su 48
   negative, lo spread e' la perdita; appendice M: scendere di TF dimezza il
   vantaggio). Ripartire "da zero" non deve ripercorrere questa strada.
2. **"Da zero" coincide con la strada (a) di CLAUDE.md**: un'idea di ingresso
   nuova, misurata dal primo giorno sui 18 anni 2009-2026. La strada (b) e'
   la scommessa sul regime 2020-2026.
3. **Campagna trend multi-giorno: registrata ed ESEGUITA il 02/10**, nessuna
   famiglia passa (appendice CD in `docs/studies/rr-intraday-study.md`, gia'
   tra le strade respinte in CLAUDE.md). Non riproporla.
4. **Un grafico live esiste gia'**: `trading/scripts/grafico_live.py` (prezzi
   da MT5, zoom/drag tipo TradingView, livelli, segnali) + il laboratorio
   pubblicato + `docs/piano-app.md` (stesso front-end, app sul VPS).
   Mancano gli strumenti di disegno e un pannello backtest generico.
5. **Working tree**: al 02/10 `git status` mostra ~184 file modificati, ma
   `git diff --ignore-cr-at-eol --ignore-all-space` e' VUOTO: e' solo il fine
   riga (CRLF/LF), nessun contenuto cambiato. Non committare quel cambio:
   non usare `git add -A`/`git add .`, aggiungere solo i file toccati.
   Su questa cartella montata da Cowork git non riesce a cancellare
   `.git/index.lock`: se un comando git dice che il lock esiste e nessun git
   e' in esecuzione, il file vuoto va rimosso a mano.

## Questionario

1. **Priorita' dei prossimi giorni** — (a) analisi "a grafico pulito" per
   un'idea di ingresso nuova sui 18 anni; (b) web app; (c) entrambe, in che
   ordine.
2. **Analisi "da zero": orizzonte** — dato che lo scalping M1 e' gia' chiuso
   (app. U), su cosa: intraday M5-H1 / multi-giorno H4-D1 / entrambi /
   "voglio comunque riprovare M1 con un'idea diversa" (dire quale).
3. **Analisi "da zero": cosa resta fuori** — Claude deve ignorare anche VWAP,
   order block e livelli gia' studiati (analisi davvero cieca), oppure puo'
   usare quello che i dati hanno gia' detto (sessioni, volatilita', spread)?
4. **Web app: base di partenza** — (a) far evolvere `grafico_live.py` +
   laboratorio (stesso front-end, come da `piano-app.md`); (b) app nuova con
   una libreria che ha gia' disegno e indicatori (es. KLineChart);
   (c) decide Claude dopo aver letto il codice esistente.
5. **Web app: dove gira** — PC con MT5 aperto / VPS 24h (come da
   `piano-app.md`) / entrambi.
6. **Strumenti di disegno indispensabili** — trendline, linee orizzontali,
   rettangoli/zone, Fibonacci, testo/note, misura rischio-rendimento; salvati
   per timeframe o comuni a tutti?
7. **Backtest nella web app** — quali strategie mostrare: taratura ufficiale,
   bot Keltner, campagna trend, nuove idee; e se deve poter LANCIARE un
   backtest dall'app o solo mostrarne i risultati.
8. **Segnali in tempo reale** — servono avvisi (Telegram? altro?) o basta il
   grafico?
9. **Dove lavorare** — sessioni in locale (tick sul PC, MT5) o nel cloud col
   credito (solo cio' che e' nel repo GitHub: M1 si', tick no)?

## Risposte

Raccolte il 02/10/2026 nella prima sessione Claude Code. **Il questionario
e' chiuso: non riproporlo.**

1. **Priorita'**: prima l'analisi, poi la web app.
2. **Orizzonte dell'analisi**: intraday M5-H1 **e** riprovare M1 con un'idea
   diversa. L'idea M1 non e' stata specificata: deve emergere dall'analisi, e
   va confrontata subito con lo spread reale (e' cio' che ha ucciso
   l'appendice U).
3. **Cosa resta fuori**: prima un'analisi **davvero cieca** (ignora VWAP,
   order block, livelli e tutto lo studiato) — l'utente vuole "un parere al di
   fuori delle mie conoscenze". Solo dopo si confronta quanto emerso con cio'
   che i dati hanno gia' detto e con le strade respinte in CLAUDE.md.
4. **Base della web app**: **app nuova con una libreria** che ha gia' disegno
   e indicatori (es. KLineChart), non l'evoluzione di `grafico_live.py`.
5. **Dove gira**: test sul PC, poi VPS 24h.
6. **Strumenti di disegno**: tutti — trendline + orizzontali, rettangoli/zone
   + testo, Fibonacci, misura rischio-rendimento. Disegni **comuni a tutti i
   timeframe, con visibilita' regolabile per TF** (come TradingView).
7. **Backtest nell'app**: quali strategie mostrare e' **ancora da decidere**.
   Prima versione: **mostrare** i risultati gia' calcolati; il lancio dall'app
   in una tappa successiva.
8. **Segnali**: basta il grafico, nessun avviso.
9. **Dove lavorare**: misto — cloud col credito (scade 04/11/2026) per i
   lavori lunghi sulle M1 del repo, locale per tick, MT5 e la web app.

## Decisioni successive (02/10/2026, sera)

- Taglio scelto dall'utente per l'analisi: scoperta **2009-2014**, solo oro.
- Una sessione parallela ha registrato nello stesso momento
  `docs/ricerca-da-zero-registrazione.md` (cinque mercati, scoperta
  2009-2017, verifica dal 2018). **L'utente ha deciso di unire le due
  ricerche sotto quel protocollo.** L'esplorazione dell'oro 2009-2014 fatta
  qui e' in `docs/studies/zero/esplorazione-oro-2009-2014.md`, come
  indicazione per le famiglie, non come candidati.
- Questa sessione passa alla **web app** (fase 3 del piano).

## Strada (a) o (b): confronto consegnato il 03/10 (decisione dell'utente aperta)

Dopo la ricerca da zero (sei famiglie, cinque mercati, nessun candidato;
verifica 2018-2026: nessuna delle cinque ipotesi passa):
- (a) idea d'ingresso nuova: con i soli prezzi le idee classiche sono finite
  (circa 7.300 varianti da zero + le campagne precedenti). Ha senso solo con
  un'informazione nuova (calendario macro, tassi reali/dollaro, flusso tick).
- (b) scommessa sul regime con la gestione B: 2020-2026 +174,6 R, DD 12,6 R;
  2009-2019 -90,8 R, DD 89,8 R. A 0,24% per operazione: ~+6,4%/anno se il
  2020-2026 continua, ~-2%/anno se torna il 2009-2019; spegnimento a -15 R =
  -3,6% di conto. Per confermarla in avanti servono ~90 operazioni (t 2,
  R/op 0,53, deviazione 2,5 R), cioe' quasi due anni.
- Il registro dei segnali in avanti (`registro_segnali.jsonl`) NON esiste sul
  PC al 03/10: il fuori campione nuovo non si sta accumulando.

## Web app: prima versione (02/10/2026)

In `app/` (istruzioni in `app/README.md`). Provata nel browser: candele
M1-D1 dall'archivio con caricamento della storia trascinando a sinistra,
tutti gli strumenti di disegno chiesti (zona e rischio/rendimento scritti su
misura), visibilita' per timeframe, salvataggio su disco, indicatori, tema
chiaro/scuro, backtest della taratura ufficiale (348 ingressi) con elenco
cliccabile.

**`--mt5` provato il 03/10** con il conto demo MetaQuotes: 99.000 candele
M1 (dal 19/06), attaccate all'archivio dal 07/07 senza buchi. Tre lezioni:
- la libreria MetaTrader5 blocca l'interprete fino a 60 s ("IPC timeout")
  se il terminale non e' collegato a un conto: per questo legge in un
  processo separato
- il fuso del broker dal solo ultimo tick sbaglia a mercato chiuso (sabato:
  -19,8 h); a mercato chiuso si ricava dalla chiusura delle 17:00 di NY.
  Lo stesso difetto e' in `trading/scripts/grafico_live.py`
- il terminale da' al massimo 100.000 barre (impostazione `maxbars`)

Da fare:
- scegliere quali strategie mettere nel catalogo dei backtest (decisione
  dell'utente ancora aperta); il file della taratura ha solo ingressi e
  stop, servono uscite e R per il riepilogo
- installazione sul VPS (porta 8095, solo localhost, poi eventuale tunnel
  con autenticazione)
- lancio dei backtest dall'app: tappa successiva
