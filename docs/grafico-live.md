# Il grafico live: leggerlo e usarlo per entrare a mercato

`trading/scripts/grafico_live.py` mostra il prezzo in tempo reale da MT5 con
sopra i livelli del progetto. Questa e' la guida operativa: cosa guardare, in
che ordine, e come si apre un'operazione.

## Avviarlo

Serve MT5 **aperto e connesso**: i prezzi arrivano da li'.

    cd C:\Users\Administrator\sviluppo-strategie-e-bot
    python trading\scripts\grafico_live.py

Nel browser: **http://127.0.0.1:8765**. La finestra di PowerShell resta
occupata, e' il server. Per vederlo da fuori, in una seconda finestra:

    & "$env:USERPROFILE\cloudflared.exe" tunnel --protocol http2 --url http://127.0.0.1:8765

## Cosa c'e' sullo schermo

| elemento | cosa dice |
|---|---|
| barra in alto | bid, spread del momento, struttura di ogni timeframe |
| bande verdi | zone BUY (sotto il prezzo), rosse: zone SELL (sopra) |
| parte scura dentro la banda | **zona raffinata**: e' quella che conta |
| linea gialla tratteggiata | il bid adesso |
| linea viola | VWAP della giornata, uguale su ogni timeframe |
| barre a sinistra | volume scambiato oggi per prezzo, colorato per sessione |
| riga chiara tratteggiata | il livello piu' scambiato della giornata |
| fasce appena schiarite | i vuoti, dove il prezzo e' passato di corsa |
| tabella in basso | tutte le zone attive, ordinate per distanza |

Passa il mouse su una banda per il nome e i prezzi; **clic per fissarlo**.

## La sequenza per entrare

Si entra **solo** quando tutte e cinque le condizioni sono vere insieme.
Nell'ordine in cui conviene controllarle:

**1. Orario.** Fra le **07:00 e le 19:00 UTC**. Fuori da quella finestra non si
apre niente. Alle 21:00 UTC si chiude tutto quello che e' aperto.

**2. Struttura allineata (barra in alto).** Per un BUY servono **H6 e H2
entrambi rialzisti**; per un SELL entrambi ribassisti. Se i due si
contraddicono, si sta fermi: e' il filtro che da solo taglia meta' delle
occasioni sbagliate.

**3. Conferme.** **M33 e H12 dalla stessa parte** dell'operazione, e **M12
dalla parte opposta** (il ritracciamento in corso su cui si entra).

**4. Il segnale, sul grafico M6.** (Il VWAP e' ancorato alla giornata, quindi
la linea e' la stessa su qualunque grafico: M6 stabilisce solo ogni quanto si
verifica la condizione, ed e' il timeframe che ha reso di piu' fra quelli
provati.) Il prezzo scende a toccare il VWAP
giornaliero (la linea viola) e **chiude sopra**, sopra anche il massimo della
candela precedente, dopo essersi allontanato di almeno 4 $ dal VWAP durante la
giornata. Specularmente per il SELL. **Si entra a mercato alla chiusura di
quella candela M6**, al prezzo che c'e' in quel momento.

**5. Dove sei rispetto alle zone.** Guarda la tabella: se l'ingresso cade
**dentro una zona raffinata concorde**, e' l'occasione migliore che questa
strategia produca. Se non ci sei dentro, l'operazione resta valida — la zona
non e' obbligatoria, e' un indicatore di qualita'.

## Stop, obiettivo, gestione

**Stop**: sotto il minimo delle ultime 5 candele M6 (sopra il massimo per un
SELL), piu' 0,30 $ di margine. Non e' un numero fisso: tipicamente 3-5 $ nei
periodi normali, 6-12 $ in quelli agitati. Se viene sotto 1 $ o sopra 10 $
(riscalati quando la volatilita' e' alta), **l'operazione si salta**.

**Dimensione**: `lotti = (capitale x rischio%) / (distanza stop in $ x 100)`,
arrotondata per difetto. Con 10.000 EUR allo 0,5% e stop da 4,72 $: 0,10 lotti.
Se il calcolo scende sotto il lotto minimo del broker, **salta l'operazione**:
non forzarla a 0,01, rischieresti il triplo del previsto.

**Obiettivo**: 10 volte la distanza dello stop. Non e' un bersaglio realistico
— ci arriva il 3% delle operazioni — ma serve a non mettere un tetto alle
corse, che sono quelle che pagano.

**Pareggio**: quando l'operazione arriva a **+3 volte il rischio**, sposta lo
stop al prezzo d'ingresso. Non prima: a +1R o +2R si salvano piu' operazioni ma
si guadagna meno.

**Fine giornata**: alle 21:00 UTC si chiude quello che e' ancora aperto, in
utile o in perdita. Un terzo delle operazioni finisce cosi', ed e' da queste
che arriva la maggior parte del guadagno.

## Quando NON si entra

- **Non si aspetta il ritracciamento su una zona.** Se il segnale e' arrivato,
  si entra a mercato subito. Mettere un ordine limite piu' in basso e aspettare
  che il prezzo torni significa farsi riempire quasi solo dalle operazioni che
  stanno fallendo, e restare fuori da quelle che corrono.
- **Una zona toccata non e' un segnale.** Le bande da sole non valgono niente:
  se non c'e' il reclaim del VWAP con la struttura allineata, non c'e'
  operazione.
- **Il profilo volume non decide gli ingressi.** Serve a vedere dove il mercato
  ha lavorato oggi; entrare in un vuoto o in un eccesso non cambia gli esiti.
- **Mai piu' di 3 operazioni al giorno**, e almeno 30 minuti fra una e l'altra.
- **Mai muovere lo stop se non a pareggio**, mai chiudere a meta', mai
  aggiungere alla posizione.

## Se qualcosa non va

| cosa vedi | cosa significa |
|---|---|
| «MT5 non risponde» | terminale chiuso o disconnesso: riparte da solo |
| nessuna zona attiva | normale: durano 30 candele, spesso non ce ne sono |
| il prezzo non si muove | mercato chiuso o terminale disconnesso |
| la pagina non si apre | il server e' stato chiuso: rilancia lo script |
