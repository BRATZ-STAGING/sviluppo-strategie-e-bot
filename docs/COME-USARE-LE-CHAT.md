# Come usare le chat

**Le aree sono fisse, le chat no.** Ogni chat fa UN blocco di lavoro e poi si
archivia. La memoria tra una chat e l'altra sta nei file, non nella
conversazione: ogni turno di una chat lunga rilegge tutto e costa sempre di
piu'.

## Regole

1. Aprire la chat nella cartella `C:\Users\gabri\sviluppo-strategie-e-bot`
   (non in `C:\`) e metterla nel gruppo **Bot trading**.
2. Nome con il prefisso dell'area: `[Regia] ...`, `[Ricerca] ...`,
   `[Backtest] ...`, `[Dati] ...`, `[App] ...`.
3. Massimo **2 chat in parallelo**, su aree diverse (lavorano nella stessa
   cartella: due chat sugli stessi file si pestano i piedi).
4. Modello: Opus per Regia e Ricerca; **Sonnet** basta per Dati e App
   (consuma meno dei limiti; si sceglie dal selettore del modello).
5. Fine lavoro: scrivere **"chiudi il blocco"** (procedura in `CLAUDE.md`),
   poi archiviare la chat.

## Le aree e il prompt di apertura (copia e incolla)

### [Regia] — decidere cosa fare
File di stato: `docs/piano-di-lavoro.md`

> Area Regia. Leggi `docs/RIPRENDI-QUI.md`, `docs/piano-di-lavoro.md` e il
> riassunto in `docs/strade-respinte.md`. Non lanciare studi: aiutami a
> decidere la direzione e i prossimi blocchi, poi aggiorna il piano.

### [Ricerca] — una sola ipotesi, fino al verdetto
File di stato: `docs/studies/` e `docs/strade-respinte.md`

> Area Ricerca. Leggi `docs/RIPRENDI-QUI.md` e `docs/piano-di-lavoro.md`.
> Ipotesi: <SCRIVI L'IDEA>. Segui il metodo: archivista prima, registrazione
> preventiva, studio sui diciotto anni, verificatore prima del verdetto.
> Output su file, in chat solo aggregati.

### [Backtest] — un bot concreto su MT5/cTrader
File di stato: il MASTER del bot in
`C:\Users\gabri\Claude\Projects\MASTER BOT TRADING\` (hub:
`TradingBots_MASTER.md`) e il codice in `bots/`

> Area Backtest. Bot: <NOME BOT>. Leggi l'hub `TradingBots_MASTER.md` e il
> MASTER del bot. Compito: <COSA>. CSV e log su file: leggine solo il
> riepilogo. Ricorda che un backtest MT5/cTrader non si confronta coi numeri
> di `docs/studies/`.

### [Dati] — scaricare, convertire, controllare dati
File di stato: `docs/registro-dati.md`

> Area Dati. Leggi `docs/registro-dati.md`. Compito: <COSA>. Prima controlla
> se i dati ci sono gia'; download lenti, riavviabili e in background.
> Aggiorna il registro alla fine.

### [App] — web app e grafico live
File di stato: `app/README.md`

> Area App. Leggi `app/README.md` e la sezione "Web app del grafico" di
> `CLAUDE.md`. Compito: <COSA>.
