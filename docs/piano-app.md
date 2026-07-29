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

## C'e' un VPS attivo 24 ore su 24: cambia dove gira l'applicazione

I bot girano su un VPS, non sul PC. Questo sposta il disegno, e in meglio.

**Conseguenza diretta**: i CSV che i bot scrivono stanno **sul VPS**. Un server
locale sul PC non li vede. Sincronizzarli sarebbe lavoro inutile: conviene far
girare il monitor **dove stanno i dati**, cioe' sul VPS.

E allora l'obiettivo "applicazione desktop" va riletto. Quello che serve
davvero non e' un programma installato sul PC, e' **una pagina raggiungibile dal
browser** — dal PC, e anche dal telefono. Per guardare come vanno i bot mentre
si e' fuori, una pagina web batte un'applicazione desktop.

L'applicazione desktop resta sensata per il **laboratorio** (ricerca, gira sui
dati storici, non ha bisogno di essere raggiungibile). Sono due cose diverse e
possono stare separate, con lo stesso front-end.

### Il problema da non sottovalutare: chi puo' vedere la pagina

Una pagina che mostra lo stato di un conto di trading **non va esposta su
internet senza protezione**. Tre strade, in ordine di semplicita':

1. **Solo dentro il VPS**: il server ascolta su `localhost`, la pagina si guarda
   dalla sessione remota con cui si accede al VPS. Zero configurazione, zero
   rischio. Ma niente telefono.
2. **Tunnel**: il server resta su `localhost` e si raggiunge attraverso il
   canale di accesso al VPS. Sicuro, un po' scomodo.
3. **Esposta con autenticazione e HTTPS**: comoda, raggiungibile dal telefono,
   ma va fatta per bene (password, certificato, firewall che accetta solo gli
   indirizzi noti).

Si parte dalla 1, che e' gratis. Alla 3 si passa solo quando c'e' un motivo, e
sapendo che va fatta con attenzione.

### Il VPS serve anche a un'altra cosa

La campagna di backtest sui Keltner e' fatta di sweep lunghi e ripetitivi. Un
VPS acceso sempre e' il posto giusto per farli girare mentre si fa altro,
scrivendo i risultati su file. Non serve nessun server web per questo, basta
lanciare gli script.

**Cosa il VPS NON puo' fare**: scaricare i tick da Dukascopy. Il feed filtra gli
indirizzi dei datacenter, ed e' esattamente il motivo per cui il download e'
fallito dal cloud e ha funzionato dal PC di casa. I tick continuano a passare
dal PC.

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

Due pezzi, non uno:

- **monitor**, sul VPS dove stanno i bot e i loro CSV: server Python, in ascolto
  su `localhost`, guardato dalla sessione remota. Se poi si vuole dal telefono,
  si aggiunge autenticazione e HTTPS.
- **laboratorio**, sul PC: ricerca sui dati storici, avvio da `.bat`.

Stesso front-end, tre viste: **laboratorio** (ricerca), **monitor** (i bot
adesso), **confronto** (bot contro strategia).

## Una domanda da chiudere prima della tappa 4

L'applicazione deve solo **guardare**, o anche **comandare** i bot (avviare,
fermare, cambiare parametri)?

Le due cose hanno un costo e un rischio molto diversi. Guardare e' leggere file:
non puo' rompere nulla. Comandare significa che un difetto dell'applicazione
diventa un ordine sbagliato sul conto — e vuole conferme, un registro delle
azioni e limiti espliciti su cosa puo' fare.

Si puo' decidere alla tappa 4, ma va deciso **prima** di costruirla, non dopo.

## Lo stato del VPS e' accertato

Vedi `docs/vps.md`: Windows Server 2022, accesso solo via RDP, Python 3.12, e
tre processi attivi di cui uno solo riguarda il trading. Tre cose cambiano
rispetto a quanto scritto sopra:

- **la porta 8080 e' occupata** da un altro bot: il monitor parte da 8090
- **i CSV dell'Expert Advisor stanno nella cartella comune** di MetaTrader
  (`Terminal\Common\Files`), non in quella del singolo terminale: lo dice il
  flag `FILE_COMMON` nel sorgente, non serve cercarli
- **il tunnel Cloudflare esiste gia'** per un altro bot, quindi la pagina
  raggiungibile dal telefono e' molto piu' vicina di quanto stimato — a
  condizione di metterci davanti un'autenticazione

## Da accertare sul VPS, prima di scrivere codice

1. **Sistema operativo**: Windows (probabile, se ci gira MT5) o Linux.
   Determina come si avvia il server e come si legge la cartella dei CSV.
2. **Come ci si accede**: sessione remota grafica, oppure riga di comando.
   Determina quale delle tre strade di accesso alla pagina e' praticabile.
3. **Cosa ci gira davvero adesso**: quali dei quattro bot, con quali parametri,
   e dove finiscono i loro CSV.
4. **Se c'e' Python**, e quale versione.
