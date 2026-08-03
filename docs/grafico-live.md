# Il grafico live: come si legge, come si usa

`trading/scripts/grafico_live.py` mostra il prezzo in tempo reale preso da MT5
con sopra i livelli misurati dal progetto. Non e' un altro TradingView: mostra
poche cose, ma ognuna ha dietro un numero verificato su sette anni.

## Avviarlo

Serve il terminale MT5 **aperto e connesso** (e' da li' che arrivano i prezzi).

    cd C:\Users\Administrator\sviluppo-strategie-e-bot
    python trading\scripts\grafico_live.py

Poi nel browser: **http://127.0.0.1:8765**. La finestra di PowerShell resta
occupata: e' il server, se la chiudi il grafico si ferma.

Per vederlo da fuori (telefono, altro PC), in una SECONDA finestra:

    & "$env:USERPROFILE\cloudflared.exe" tunnel --protocol http2 --url http://127.0.0.1:8765

Stampa un indirizzo `https://....trycloudflare.com`. Cambia a ogni riavvio del
tunnel ed e' pubblico senza password: non contiene credenziali ne' comandi di
trading, ma non va condiviso.

## Cosa c'e' sullo schermo

**Barra in alto**: bid, spread del momento, ora dell'ultimo aggiornamento e lo
stato della struttura di ogni timeframe (rialzista / ribassista). La struttura
e' causale: uno swing e' confermato tre candele dopo il suo estremo, mai prima.

**Bande orizzontali**: le zone order block attive. Verdi = BUY (zona sotto il
prezzo, nata da un impulso rialzista), rosse = SELL. La parte **piu' scura
dentro la banda e' la zona raffinata**: e' quella che porta il vantaggio
misurato. Passa il mouse su una banda per vederne nome e prezzi; **clic per
fissare** l'etichetta, clic di nuovo per toglierla. Col pulsante «nomi sempre»
si mostrano tutte insieme.

**Profilo volume (a sinistra)**: quanto e' stato scambiato a ogni livello di
prezzo OGGI, diviso per sessione — viola asia, ocra londra, verde new york,
grigio sera. La riga tratteggiata chiara e' il **livello piu' scambiato**; le
fasce appena schiarite sono i **vuoti**, dove il prezzo e' passato di corsa.

**Linea gialla tratteggiata**: il bid attuale. **Linea viola**: VWAP della
giornata (solo sul grafico M6).

**Tabella in basso**: tutte le zone attive ordinate per distanza dal prezzo,
con la zona raffinata, quando e' nata e quando scade (30 candele del suo
timeframe).

## Come si usa davvero, e come NON si usa

Tre risultati misurati che cambiano il modo di guardare questo grafico.

**Una zona non e' un segnale.** Il tocco di una zona, da solo, perde su tutti i
timeframe e tutti gli obiettivi provati: 48 celle su 48 negative, da -0,11 a
-0,30 R per operazione (appendice W). Serve il segnale della strategia, con la
struttura del timeframe concorde.

**Non mettere un ordine limite sulla zona e aspettare.** E' il risultato piu'
importante di tutti: delle 348 operazioni della strategia, le 222 che tornano
indietro su un livello rendono **-0,387 R**, le 126 che non ci tornano mai
**+2,040 R** (appendice AA). Il ritracciamento non e' un prezzo migliore: e' il
segnale che l'operazione sta fallendo. Le 12 operazioni sopra +8R valgono da
sole il 69% di sette anni, e solo 3 tornano su un livello.

**Il profilo volume serve agli occhi, non alle decisioni.** Vuoti ed eccessi
non discriminano gli esiti: differenza -0,038 R con probabilita' 0,85 che sia
caso (appendice V). Guardalo per capire dove il mercato ha lavorato, non per
decidere se entrare.

**Quello che invece conta**: essere DENTRO una zona raffinata quando arriva il
segnale. Su sette anni le operazioni in zona raffinata rendono +1,342 R contro
+0,153 del campione senza filtro, con 7 anni positivi su 7 e il 9,5% che arriva
all'obiettivo pieno contro il 2,2% (appendice AJ). Fuori dalla zona raffinata,
**nessuna** operazione ha mai raggiunto l'obiettivo pieno.

## Se qualcosa non va

| cosa vedi | cosa significa |
|---|---|
| «MT5 non risponde» | terminale chiuso o non connesso: riparte da solo appena torna |
| nessuna zona attiva | e' normale: le zone durano 30 candele e spesso non ce ne sono |
| il prezzo non si muove | mercato chiuso (fine settimana) o terminale disconnesso |
| la pagina non si apre | il server e' stato chiuso: rilancia lo script |

## Tenerlo sempre acceso

Utilita' di pianificazione → Crea attivita' → *Esegui indipendentemente dalla
connessione dell'utente* → attivazione *All'avvio del sistema* → azione
`python` con argomento il percorso dello script → in Impostazioni spunta
*Riavvia se l'attivita' non riesce*.

Con la stessa procedura conviene pianificare anche `aggiorna_dati.py` ogni 15
minuti: tiene aggiornato l'archivio Dukascopy su cui girano studi e
laboratorio. Attenzione alla differenza: **MT5 e' in tempo reale, Dukascopy
pubblica un'ora per volta a ora conclusa** (fino a un'ora di ritardo).
