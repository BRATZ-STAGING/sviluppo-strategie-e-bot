# Il VPS — stato accertato al 30/07/2026

## Macchina e accesso

| | |
|---|---|
| sistema | Windows Server 2022 (VPS Contabo) |
| accesso | Desktop remoto (RDP), utente `administrator` |
| SSH | **non configurato** — la riga di comando si usa dentro la sessione RDP |
| Python | 3.12, con un ambiente isolato (`.venv`) per ogni bot |

L'indirizzo IP del VPS non e' scritto qui di proposito: e' un dato di accesso e
non va in un repository.

## Cosa ci gira (avvio e login automatici)

| processo | cartella | cosa fa |
|---|---|---|
| **MetaTrader 5** | — | l'Expert Advisor di trading |
| bot Telegram | `Desktop\bot-telegram` | aiogram in polling, avviato da `AVVIA-BOT-Windows.bat` |
| bot Meta | `Desktop\bot-meta` | server aiohttp su **`localhost:8080`**, dietro un tunnel Cloudflare |

I bot Telegram e Meta **non c'entrano con il trading**: sono di un altro
progetto, e salvano su SQLite (`data\*.db` nella propria cartella), non su CSV.
Qualunque CSV sul VPS viene dall'Expert Advisor di MT5.

Avvertenza registrata: Telegram ammette **una sola istanza per token**, quindi
due processi del bot Telegram producono `TelegramConflictError`. Non e' un
problema del trading, ma e' un modo facile di rompere qualcosa d'altro
riavviando le cose a caso.

## Tre conseguenze per il monitor

### 1. La porta 8080 e' occupata

Il bot Meta e' in ascolto la'. Il monitor deve usare un'altra porta — **8090**
come valore di partenza, verificando che sia libera.

### 2. I CSV dell'Expert Advisor stanno nella cartella COMUNE

Non serve cercarli: lo dice il codice. In `KeltnerImpulseBot_MT5.mq5` i file si
aprono con il flag `FILE_COMMON`:

```
FileOpen(tradesFile, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON)
```

quindi il percorso e' la cartella comune di MetaTrader, **non** quella del
singolo terminale:

    C:\Users\<utente>\AppData\Roaming\MetaQuotes\Terminal\Common\Files

Dentro: `trades_XAUUSD_PERIOD_M10.csv` e `skips_XAUUSD_PERIOD_M10.csv`. La
variante archiviata scrive nella sottocartella `keltnerdd\`.

Comando diretto, invece di una ricerca ricorsiva:

```powershell
dir "$env:APPDATA\MetaQuotes\Terminal\Common\Files" -Recurse -Include *.csv |
  Select-Object FullName, Length, LastWriteTime | Format-Table -AutoSize
```

### 3. Il tunnel Cloudflare c'e' gia': la pagina dal telefono e' vicina

Nel piano avevo messo "raggiungibile dal telefono" come la strada piu' lontana,
da fare solo con autenticazione e HTTPS fatti per bene. Ma **quel pezzo di
infrastruttura esiste gia'** per il bot Meta: un tunnel Cloudflare fornisce
HTTPS e non richiede di aprire porte sul firewall.

Aggiungere un secondo percorso per il monitor e' quindi molto meno lavoro del
previsto. **Con una condizione**: davanti va messa un'autenticazione. Un tunnel
senza autenticazione e' una pagina pubblica, e questa mostrerebbe lo stato di un
conto. Cloudflare Access serve esattamente a quello.

Ordine consigliato: prima `localhost` dentro RDP (funziona subito, zero
rischio), poi il tunnel con autenticazione quando il monitor mostra qualcosa che
vale la pena guardare dal telefono.

## Ancora da accertare

Quale dei quattro bot gira davvero su MT5 e con quali parametri. Il dato utile
e' il **magic number**, che identifica l'Expert Advisor senza ambiguita':

| magic | bot |
|---|---|
| 20260702 | `mt5/keltner-impulse` |
| 20260706 | `mt5/keltner-dd-archiviato` (non dovrebbe girare) |

Si legge dai CSV o dalla scheda dell'EA nel terminale. Serve anche per un
motivo pratico: se sul VPS gira la variante archiviata, va spenta.
