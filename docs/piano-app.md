# Dal laboratorio all'applicazione di gestione

Obiettivo dichiarato: un laboratorio **stabile**, che si aggiorna e migliora nel
tempo invece di essere rigenerato da zero, e che alla fine diventi
un'applicazione desktop per gestire i bot.

Questo documento fissa **una** decisione di architettura, perche' costa poco
adesso e molto dopo, e divide il resto in tappe che hanno senso una per una.

## La decisione: da dove arrivano i dati

Oggi `lab_template.html` legge i dati da un blocco incorporato nella pagina:

```html
<script id="payload" type="application/json">__DATA__</script>
```

`export_lab.py` ci sostituisce dentro 1,2 MB di JSON. Funziona, ed e' l'unico
modo possibile per una pagina pubblicata (la politica di sicurezza degli
artifact blocca qualunque richiesta verso l'esterno).

Un'applicazione di gestione ha invece bisogno di dati **che cambiano**: i CSV
che i bot scrivono mentre operano.

La soluzione e' non scegliere: **la pagina prova prima il blocco incorporato, e
se non c'e' chiede i dati al server locale.**

```js
const payload = document.getElementById("payload").textContent.trim();
const DATA = payload && payload !== "__DATA__"
  ? JSON.parse(payload)                 // pagina pubblicata: dati incorporati
  : await (await fetch("/api/dati")).json();   // applicazione: dati vivi
```

Sono cinque righe, e comprano tre cose:

1. lo **stesso front-end** serve la pagina condivisibile e l'applicazione: si
   scrive e si migliora una volta sola
2. l'applicazione puo' ricaricare i dati senza rigenerare un file da 1,2 MB
3. il giorno in cui si vuole un vero eseguibile installabile, Tauri o Electron
   avvolgono **questo** front-end senza riscriverlo

Da fare per prima cosa, prima di aggiungere qualunque funzione nuova.

## Perche' non Electron subito

Un'applicazione desktop "vera" con Electron o Tauri richiede una catena di
strumenti (Node o Rust), un processo di build e una distribuzione. Non e'
difficile, e' **prematuro**: si pagherebbe quel costo prima di sapere cosa
l'applicazione deve fare.

L'alternativa che da' il 90% del risultato con il 10% del lavoro: un **server
locale in Python** che serve la pagina e legge i CSV dei bot, avviato da un file
`.bat`. Cliccando il `.bat` si apre il browser sull'applicazione. Per chi la usa
la differenza con un programma installato e' quasi nulla, e Python e' gia' sul
PC.

Quando l'applicazione sara' matura e ci sara' un motivo concreto per volerla
installabile (icona, avvio automatico, distribuzione a qualcun altro), si
avvolge il front-end esistente. Non si butta niente.

## Le tappe

### Tappa 1 — il laboratorio diventa stabile

Oggi il laboratorio e' un artifact ripubblicato a mano. Va reso un prodotto del
repository:

- `trading/scripts/build_lab.py`: un comando che rigenera la pagina dal
  template e dai dati. Oggi la sostituzione del payload si fa a mano.
- la doppia sorgente di dati descritta sopra
- il numero di versione visibile nella pagina, per sapere cosa si sta guardando

Risultato: `python build_lab.py` e la pagina e' pronta, sempre uguale a se
stessa.

### Tappa 2 — il monitor del forward

I bot **scrivono gia'** quello che serve, e nessuno lo sta leggendo:

| dove | cosa |
|---|---|
| `Common\Files\trades_XAUUSD_*.csv` (MT5) | ogni operazione: ingresso, uscita, R, motivo |
| `Common\Files\skips_XAUUSD_*.csv` (MT5) | ogni segnale scartato e perche' |
| `C:\cTraderData\` | gli stessi file per i cBot |
| `Common\Files\keltnerdd\` | idem per la variante archiviata |

Le colonne sono identiche fra MT5 e cTrader (scelta deliberata di chi ha scritto
i bot), quindi **un solo lettore vale per tutti**.

Una pagina che li legge risponde a domande che oggi richiedono di aprire il
terminale: quante operazioni, quanti R, quali segnali sono stati scartati e
perche', come si confronta il forward con il backtest. E i CSV degli scarti sono
il pezzo piu' interessante: dicono cosa il bot **non** ha fatto.

### Tappa 3 — confronto fra bot e strategia, sulle stesse regole

Il pezzo che oggi manca del tutto: rigirare la logica dei bot con il motore di
questo repository, con le sue convenzioni conservative, per confrontarli con la
strategia tarata su una scala comune. Prima serve la validazione del motore
contro un run MT5 noto (vedi `docs/RIPRENDI-QUI.md`, punto 3).

### Tappa 4 — l'applicazione

Server locale Python, `.bat` di avvio, tre viste: **laboratorio** (ricerca),
**monitor** (i bot adesso), **confronto** (bot contro strategia).

## Una domanda da chiudere prima della tappa 4

L'applicazione deve solo **guardare**, o anche **comandare** i bot (avviare,
fermare, cambiare parametri)?

Le due cose hanno un costo e un rischio molto diversi. Guardare e' leggere file:
non puo' rompere nulla. Comandare significa che un difetto dell'applicazione
diventa un ordine sbagliato sul conto — e vuole conferme, un registro delle
azioni e limiti espliciti su cosa puo' fare.

Si puo' decidere alla tappa 4, ma va deciso **prima** di costruirla, non dopo.
