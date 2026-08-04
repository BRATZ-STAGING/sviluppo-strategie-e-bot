# Il grafico live: leggerlo e usarlo per entrare a mercato

`trading/scripts/grafico_live.py` mostra il prezzo in tempo reale da MT5 con
sopra i livelli del progetto. Questa e' la guida operativa: cosa guardare, in
che ordine, e come si apre un'operazione.

> **Da leggere prima di operare (04/08/2026).** Le regole descritte qui sono
> state misurate sul 2020-2026. Sullo storico esteso al 2009 la stessa identica
> strategia **perde**: -39,3 R su 382 operazioni, 3 anni positivi su 11,
> perdita massima 47,8 R invece di 17,6. Tre verifiche successive — filtro di
> regime, rinuncia allo short, taratura invertita — sono tutte negative, e solo
> l'1% delle configurazioni scelte sul 2020-2026 resta positivo sul periodo
> vecchio. Appendici AU-AY in `docs/studies/rr-intraday-study.md`. Questa guida
> resta valida come descrizione di **cosa fa la strategia e come si legge il
> grafico**; non e' piu' una raccomandazione a metterci soldi sopra.

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
| barra in alto | bid, spread, VWAP, numero di segnali, struttura di ogni TF |
| pannelli LONG / SHORT | le cinque condizioni adesso, si o no una per una |
| pannello CONFLUENZE | livelli entro mezzo ATR dal prezzo, con quanto valgono |
| triangoli | segnali passati: pieno = conferme ufficiali, vuoto = campione largo |
| bande verdi | zone BUY (sotto il prezzo), rosse: zone SELL (sopra) |
| parte scura dentro la banda | **zona raffinata**: e' quella che conta |
| linea gialla tratteggiata | il bid adesso |
| linea viola | VWAP della giornata, uguale su ogni timeframe |
| barre a sinistra | volume scambiato oggi per prezzo, colorato per sessione |
| riga chiara tratteggiata | il livello piu' scambiato della giornata |
| fasce appena schiarite | i vuoti, dove il prezzo e' passato di corsa |
| tabella in basso | tutte le zone attive, ordinate per distanza |

Passa il mouse su una banda per il nome e i prezzi; **clic per fissarlo**.

### Muoversi sul grafico

| gesto | effetto |
|---|---|
| **rotellina** | zoom, tenendo fermo il punto sotto il puntatore |
| **trascinare** | scorre avanti e indietro nel tempo |
| **doppio clic** o «torna a ora» | riporta la vista sull'ultima candela |
| pulsanti M1 … H6 | cambia timeframe (la vista si riporta a ora) |

Il bordo destro **non e' incollato all'ultima candela**: resta un po' di spazio
vuoto, come su TradingView, cosi' si vede dove sta andando il prezzo. Se hai
scorso indietro, l'arrivo di una candela nuova non ti sposta la vista.

**M1 non serve a operare** — l'ingresso si valuta su M6 — serve solo a vedere
con precisione dove sta il prezzo adesso rispetto a un livello, per esempio se
e' appena dentro o appena fuori una zona.

## I tre pannelli in alto

### LONG e SHORT: le cinque condizioni, adesso

Sono le stesse cinque della sequenza qui sotto, valutate sull'**ultima candela
M6 chiusa** — non su quella in corso, che cambierebbe idea a ogni tick. Ogni
riga dice si/no; quando sono tutte vere il riquadro si accende e compare
**SEGNALE**.

La riga «spinta dal VWAP» mostra due numeri: quanto il prezzo si e' allontanato
dal VWAP oggi e la soglia da superare. Serve a capire **quanto manca**, non
solo che manca. La riga «filtro di fondo D1» puo' dire «—» nei primi giorni
dopo l'avvio, se non ci sono ancora 50 giornate di storia.

Questo pannello e' la parte che serve davvero per operare: non dice soltanto se
c'e' un segnale, dice **quale condizione manca**.

### CONFLUENZE: cosa c'e' intorno al prezzo, e quanto vale

Elenca i livelli entro **mezzo ATR** dal prezzo attuale, ordinati per distanza,
ciascuno con la distanza in ATR e un peso:

- **voto** — solo la zona **OB raffinata**: e' l'unica famiglia che abbia mai
  mostrato un vantaggio misurabile (e che comunque non regge sui diciotto anni,
  appendice BA);
- **contesto** — tutto il resto: OB pieno fuori dalla parte raffinata, POC di
  ieri, estremi dell'area di valore, vuoti di volume. Nessun vantaggio
  misurato.

**Le confluenze non aprono un'operazione, e il pannello lo dice.** E' una scelta
deliberata: misurate su diciotto anni, 168.833 eventi e 720 configurazioni, non
ne sopravvive nessuna (appendice AZ), e contate allo stesso prezzo la
confluenza non e' nemmeno un caso raro — 167.808 eventi su 168.833 hanno gia'
quattro famiglie sovrapposte, perche' i livelli stanno tutti dove il prezzo ha
lavorato. Un pannello che accendesse un segnale su una confluenza mostrerebbe
come regola qualcosa che le misure hanno bocciato.

Quindi: **si entra con le cinque condizioni**; una zona raffinata concorde dice
solo che l'occasione e' migliore della media.

### I segnali sul grafico

Il selettore «segnali off / ufficiali / tutti» disegna i segnali passati come
triangoli all'altezza del prezzo d'ingresso:

- **triangolo pieno** = passa anche le conferme ufficiali (M33+H12 allineati,
  M12 contrario);
- **triangolo vuoto** = campione largo, cioe' il segnale c'era ma le conferme
  no.

Sull'ultimo segnale vengono disegnati anche **stop** e **obiettivo**
tratteggiati, con i prezzi.

Sono ricalcolati ogni cinque minuti (la pillola in alto dice a che ora), non a
ogni aggiornamento: ripercorrere quindici mesi di minuti costa decine di
secondi. Per sapere cosa sta succedendo **adesso** si guarda il pannello delle
condizioni, non i triangoli.

Nota tecnica: per calcolare i segnali con le regole vere servono quindici mesi
di storia (il filtro di fondo vuole 50 giornate, il riconoscimento dei mesi
agitati ne pretende 250), e il terminale ne da' sei settimane. Lo script
antepone quindi l'archivio del repository ai dati MT5. Se l'archivio manca,
all'avvio compare un avviso: senza, i segnali sarebbero calcolati con regole
piu' blande di quelle degli studi.

## I livelli: cosa sono e a cosa servono davvero

Ci sono **tre famiglie di livelli** sul grafico, e fanno tre mestieri diversi.
E' la confusione fra i tre che rende difficile usarli.

### 1. Il VWAP giornaliero (linea viola) — questo E' il segnale

E' il prezzo medio della giornata pesato per i volumi, che riparte da zero ogni
giorno a mezzanotte UTC. **E' l'unico livello su cui si entra.** Il segnale non
e' "il prezzo tocca il VWAP": e' il prezzo che lo tocca **e lo riprende**,
chiudendo dall'altra parte. Vedi il punto 4 della sequenza qui sotto.

Nota: e' calcolato una volta sui minuti e letto alla chiusura di ogni candela,
quindi la linea viola e' **la stessa identica** su M6, su H2 o su H6. Cambiare
timeframe non cambia il livello, cambia solo ogni quanto si verifica se la
condizione e' scattata.

### 2. Le zone order block (bande verdi e rosse) — questo e' un voto di qualita'

Una zona nasce cosi': si prende l'ultima candela **contraria** prima di un
movimento che rompe la struttura, e si segna la fascia di prezzo fra il minimo
della sua ombra e la sua apertura (simmetrico per le ribassiste). E' la zona
dove chi ha spinto il mercato aveva ancora ordini non riempiti.

- **banda chiara** = la zona piena;
- **parte scura dentro la banda** = la **zona raffinata**, cioe' la fetta dove
  la base della candela OB e quella della candela successiva si sovrappongono.
  E' l'unica parte che porta vantaggio misurato: fuori da li' la zona piena
  vale quanto non averla.

**Come si usano: NON come punto d'ingresso.** Misurato e respinto: entrare al
tocco di una zona da' 48 celle su 48 negative (appendice W), e mettere un
ordine limite dentro la zona aspettando il ritracciamento seleziona proprio le
operazioni che stanno fallendo (-0,387 R contro +2,040, appendice AA).

Si usano **dopo** che il segnale VWAP e' scattato, per rispondere a una sola
domanda: *questa occasione e' migliore della media?* Se il prezzo d'ingresso
cade dentro una zona **raffinata e concorde** (verde per un BUY, rossa per un
SELL), e' l'occasione migliore che la strategia produca. Se non ci cade,
l'operazione resta valida lo stesso.

La colonna **distanza** nella tabella dice quanto manca al prezzo per arrivare
alla zona: positiva = il prezzo e' oltre (per una BUY, sopra la zona);
serve solo a capire quali zone sono vicine, non e' un ordine di entrare.

### 3. Il profilo volume (barre a sinistra) — questo non decide niente

Dice dove il mercato ha lavorato oggi: la riga chiara tratteggiata e' il prezzo
piu' scambiato, le fasce schiarite sono i vuoti dove il prezzo e' passato di
corsa. **Non e' un segnale**: provato come discriminante, non separa nulla
(p 0,85). Sta li' perche' aiuta a capire cosa e' successo, non a decidere.

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

### Le cinque condizioni in una riga

> orario 07-19 UTC · H6 e H2 dalla stessa parte · M33 e H12 dalla stessa parte
> e M12 dalla parte opposta · il prezzo riprende il VWAP su M6 dopo essersene
> allontanato di 4 $ · (la zona raffinata dice solo se l'occasione e' buona)

Le prime quattro sono **obbligatorie e vanno verificate in quest'ordine**,
perche' le prime tre si leggono in un secondo dalla barra in alto e la quarta
richiede di guardare il grafico. La quinta non e' una condizione: e' un voto.

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

## E il fine settimana?

Con la strategia come e' tarata **la domanda non si pone**: si chiude tutto
alle 21:00 UTC di ogni giorno, quindi non si arriva mai al venerdi' con
qualcosa di aperto. E' anche il motivo per cui non si paga mai swap: il
rollover del broker cade esattamente alle 21:00 UTC.

Se pero' capita di tenere aperto (operativita' manuale, o una variante che
tiene le posizioni piu' a lungo), la regola misurata e' una sola:

**si attraversa il fine settimana solo se l'operazione e' gia' sopra +1R.
Sotto quella soglia si chiude il venerdi'. Lo stop non si tocca.**

Perche' proprio cosi': il filtro alza il risultato medio di 5,5 R e soprattutto
migliora le storie sfortunate (il decimo percentile passa da 36,5 a 46,5 R su
20.000 simulazioni con salti pescati dai fine settimana reali). Spostare lo
stop — a pareggio o al prezzo del venerdi' — non aggiunge nulla una volta
applicato il filtro, e portarlo al prezzo del venerdi' fa danno perche' azzera
il margine che serve ad assorbire il salto.

Il salto del lunedi' e' mediamente 1,31 $, ma una volta su venti supera i
19,59 $ e il massimo osservato in sette anni e' 111,94 $ — piu' di venti volte
lo stop tipico. Con lo stop non si scappa: se il mercato riapre oltre, si esce
al prezzo di riapertura, non allo stop.

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
