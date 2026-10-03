# Avvio su MT5 e VPS — consegna del 05/08/2026

Documento operativo. Chi lo legge deve poter portare le strategie su MT5 e
avviarle **senza tornare a chiedere niente**. La ricerca e' chiusa; qui c'e'
solo cosa fare e in che ordine.

Da leggere prima: `bots/SCHEDE-STRATEGIE.md` (specifica completa dell'ingresso,
con l'aggiornamento del 04-05/08 in fondo) e `docs/vps.md` (la macchina).
Contesto e limiti della ricerca: `docs/CONSEGNA-BOT-2026-08.md`.

> **CORREZIONE 04/10/2026.** I numeri di C e D di questo documento venivano da
> script con due difetti (`verifica_bot.py` e le sue copie in `sfida_prop.py`
> e nei calcoli dei profili): la chiusura delle 21:00 UTC cercava una candela
> che con l'ora legale USA non esiste, quindi d'estate C e D restavano aperte
> per giorni. Corretti (commit f32f32f e 1adeb9f; dettaglio in
> `docs/studies/verifica-bot-discrepanze.md`), coincidono col motore
> ufficiale. **La B non cambia.** C: +86,6 -> **+71,3 R**, DD 12,33 -> 10,92,
> anni+ 6/7 -> **5/7**, fase 1 88% -> 88%, giorni 258 -> **272**. D (solo
> long): +220,7 -> **+144,9 R**, DD 18,71 -> **11,64**, perdite di fila 11 -> 9,
> fase 1 90% -> **92%**, giorni 221 -> **242**. La vecchia colonna D mescolava
> numeri solo long e dei due lati: ora e' tutta solo long. **Conclusioni
> cambiate**: (1) gli short della D **non perdono** (+20,6 R, 4/7): togliere
> lo short non e' piu' "una correzione" ma una scelta (meno R, meno drawdown,
> miglior R/DD, un anno negativo); (2) sulla C il combinato non batte piu' il
> solo long; (3) le taglie in vigore (0,75 / 0,75 / 0,53%) **non pareggiano
> piu' il drawdown**: con la stessa regola sarebbero 0,75 / 0,85 / 0,80%. Le
> regole e le taglie non sono state cambiate: la scelta resta all'utente.

---

## 1. I tre profili da avviare

Stesso identico ingresso per tutti e tre: **reclaim del VWAP giornaliero su M6**,
sette condizioni, tutte in `bots/SCHEDE-STRATEGIE.md`. Cambia solo l'uscita.

| | **B** | **C** | **D** (in uso migliorata) |
|---|---|---|---|
| obiettivo | 1:8 | 1:2 | 1:10 |
| pareggio | — | **nessuno** | stop a **+0,50 R** quando l'MFE tocca +3R |
| trailing | da +3R lo stop segue l'MFE a distanza **2R** | — | — |
| chiusura per tempo | oltre la giornata; il fine settimana si attraversa **solo sopra +1R** | **21:00 UTC** | **21:00 UTC** |
| **lati** | long e short | long e short | **SOLO LONG** |
| **rischio per operazione** | **0,75%** | **0,75%** | **0,53%** |
| Swap Free | **necessario** | non serve | non serve |

### Perche' la D e' solo long

Separando i due lati (con il filtro D1 attivo, cioe' la configurazione viva):

| | | op | R | R/op | vinte% | DD R | R/DD | anni+ |
|---|---|---|---|---|---|---|---|---|
| **B** | long | 232 | +155,9 | 0,67 | 41,8% | **10,94** | **14,26** | **7/7** |
| | short | 101 | +18,6 | 0,18 | 30,7% | 19,29 | **0,97** | 5/7 |
| **C** | long | 232 | +63,6 | 0,27 | 50,4% | 9,57 | 6,64 | 5/7 |
| | short | 101 | +7,7 | 0,08 | 42,6% | 10,42 | **0,74** | 4/7 |
| **D** | long | 232 | **+144,9** | **0,62** | 46,6% | **11,64** | **12,45** | 6/7 |
| | short | 101 | +20,6 | 0,20 | 34,7% | 17,33 | **1,19** | 4/7 |

*(Corretto il 04/10/2026: prima C long +74,6 / short +12,1, D long +220,7 /
short −10,7 con 2 anni positivi su 7.)*

Con i numeri corretti gli short della D **guadagnano** (+20,6 R su 101
operazioni, 4 anni positivi su 7), ma si portano dietro un drawdown (17,33 R)
piu' grande di quello dell'intera strategia (16,29). Solo long: **+144,9 R con
DD 11,64** contro +165,5 con DD 16,29 — **rende il 12% in meno e ha il 29% di
drawdown in meno** (R/DD 12,45 contro 10,16), ma perde il 7/7: il 2026 solo
long e' −1,1 R. Non e' piu' una correzione ma **una scelta**; la regola resta
solo long finche' l'utente non decide altrimenti. La taglia era salita da
0,50% a 0,53% per tenere lo stesso drawdown in percentuale (−9,9%); con il
drawdown corretto lo 0,53% fa −6,2% (vedi sotto).

Sulla **B** gli short sono marginali: guadagnano quanto il buco che scavano
(R/DD 0,97). Solo long sarebbe leggermente meglio (R/DD 14,26 contro 13,85,
drawdown da 12,60 a 10,94 R, taglia fino a 0,86%). **Restano entrambi i lati**
perche' il margine e' piccolo e la B e' 7/7 con tutti e due (con i numeri
corretti lo e' anche la D a due lati, non la C); chi avvia puo' scegliere
solo-long sapendo che e' difendibile.

Sulla **C** gli short non pagano piu' il loro spazio come sembrava: R/DD 0,74,
e il combinato (6,52) e' appena sotto il solo long (6,64), mentre prima lo
batteva (7,02 contro 6,62). La differenza e' piccola come sulla B e **restano**
(regola non cambiata), ma la ragione data allora non regge piu'.

**Il caveat, che va detto:** il 2020-2026 e' un mercato toro dell'oro, da 1.775
a 4.676 $. Un solo-long in un toro *deve* sembrare buono, e in questo campione
l'oro non ha mai girato davvero. Togliere gli short e' ottimizzare su un
regime. L'unica cosa che rende la scelta meno sospetta e' che **"lo short da
solo perde" era gia' documentato nell'appendice 7**, prima di questa analisi:
e' la conferma di un fatto noto, non un risultato pescato oggi.

Attese misurate su 333 operazioni (la D sulle sue 232 long), 2020-2026,
spread reale:

| | B | C | D |
|---|---|---|---|
| R totale | **+174,6** | +71,3 | +144,9 |
| R per operazione | 0,52 | 0,21 | **0,62** |
| win rate | 38,4% | **48,1%** | 46,6% |
| drawdown massimo | 12,60 R -> **−9,45%** (0,75%) | 10,92 R -> **−8,19%** (0,75%) | 11,64 R -> **−6,17%** (0,53%) |
| perdite consecutive | 12 | **7** | 9 |
| anni positivi | **7/7** | 5/7 | 6/7 |
| anno peggiore | **+11,9 R** | −2,6 R | −1,1 R |
| sfida FundingPips, fase 1 | **97%** | 88% | 92% |
| giorni mediani per passarla | **156** | 272 | 242 |

*(Corretto il 04/10/2026; la colonna D ora e' tutta solo long, prima mescolava
numeri solo long e dei due lati. Vecchi valori: C +86,6 / 0,26 / 46,9% / DD
12,33 / 6/7 / fase 1 88% / 258 giorni; D +220,7 / 0,95 / 39,0% / DD 18,71 /
11 di fila / 6/7 / −2,6 / 90% / 221 giorni.)*

Le tre taglie erano state scelte diverse **perche' i drawdown sono diversi**,
pareggiando il rischio in percentuale di conto (allora fra −9,25% e −9,89%).
Con i drawdown corretti le taglie in vigore **non pareggiano piu'**: B −9,45%,
C −8,19%, D −6,17%, cioe' 2,6 / 3,8 / 5,8 punti di margine sul limite del 12%.
Con la stessa regola (drawdown al livello della B) le taglie sarebbero
**C 0,85%** (−9,28%; fase 1 88%, 233 giorni) e **D 0,80%** (−9,31%; fase 1 93%,
204 giorni), zero violazioni in entrambi i casi. Non sono state cambiate qui:
la decisione e' dell'utente.

### Sotto il lotto minimo, l'operazione si salta

Con 5.000 $ allo 0,75% si rischiano 37,50 $; con lo stop mediano di 10-15 $
sono 0,03-0,04 lotti. Nei mesi agitati lo stop sale a 25-30 $ e si scende al
minimo negoziabile. In una sfida il vincolo e' sopravvivere, non fare numero:
**se il lotto calcolato e' sotto il minimo, l'operazione non si apre.**

---

## 2. L'EA: cosa scrivere

**Un solo Expert Advisor** con il profilo come parametro (`ENUM` a tre valori),
installato in tre istanze su tre conti. L'ingresso e' identico: scriverlo tre
volte significa tre modi diversi di sbagliarlo.

L'EA **non esiste ancora**. La specifica completa e' in
`bots/SCHEDE-STRATEGIE.md`; per le convenzioni del progetto (gruppi di input,
magic number, guardia sull'equity, log CSV) seguire
`bots/mt5/keltner-impulse/KeltnerImpulseBot_MT5.mq5`. Il motore di riferimento
in Python e' `trading/framework/segnali.py` e `trading/framework/structure.py`:
**l'EA deve produrre le stesse operazioni**.

### Le sette trappole, ognuna gia' costata un errore misurato

1. **L'ora del server non e' UTC.** MT5 da' l'ora del broker (FP: UTC+2/+3 con
   l'ora legale). Le soglie della strategia (07:00-19:00 per entrare, 21:00 per
   chiudere) sono UTC. Lo scarto va calcolato a runtime da
   `TimeGMT()`/`TimeCurrent()`, **mai un offset fisso**. Un errore identico ha
   reso irreali il **62% dei segnali** disegnati sul grafico.
2. **M33 e M66 non esistono in MT5.** Vanno aggregati da M1 (33 e 66 minuti,
   allineati all'inizio della giornata UTC, candela etichettata all'APERTURA).
   M6, M12, H2, H6, H12 sono nativi. Se l'aggregazione e' sbagliata, sbagliano
   le condizioni 2, 3a e 3b, cioe' quasi tutto.
3. **Struttura causale**: swing confermato **3 candele dopo** l'estremo; lo
   stato passa rialzista quando una **chiusura** supera l'ultimo massimo
   confermato; vale dalla chiusura della candela che rompe. Usare l'estremo
   prima della conferma e' leggere il futuro.
4. **VWAP sulle candele M6**, ancorato a 00:00 UTC, prezzo tipico (H+L+C)/3
   pesato per il volume. **Non sui minuti**: e' una linea diversa e faceva
   aprire operazioni inesistenti.
5. **Si decide sulla candela M6 CHIUSA**, barra 1, mai la 0.
6. **Il filtro D1** usa la chiusura di ieri contro la sua media a 50 giornate.
   Le giornate sono quelle vere: lo spezzone della domenica sera non e' una
   giornata (contarlo cambiava il 5,1% delle classificazioni).
7. **La riscalatura ATR** vale **solo** nei mesi ad alta volatilita' (mediana
   ATR dei 21 giorni prima dell'inizio del mese > 1,5 x la mediana di
   riferimento **25,5968 $**, congelata sul 2020-2024). Negli altri mesi le
   soglie restano in dollari.

### Una cosa da sapere sulla B prima di implementarla

La B tocca l'obiettivo 1:8 solo nel **4%** delle operazioni; il **29%** le
chiude lo **stop mobile in guadagno**. Non e' una strategia a bersaglio, e' una
strategia di trailing. **Se il trailing e' implementato male la B non perde
qualche punto: smette di funzionare.**

### Log obbligatorio

CSV di **ogni segnale valutato**, non solo di quelli aperti: istante UTC, lato,
quali delle sette condizioni erano vere, VWAP, stop, rischio, spread del
momento. Senza questo non si puo' fare il passo 3, che e' il piu' importante.

---

## 3. Il confronto contro il motore Python — non saltarlo

Prima di mettere l'EA su qualunque conto, anche demo:

1. far girare l'EA in backtest MT5 su un periodo di cui si hanno i dati
   (per esempio 2025-01 -> 2026-06);
2. far girare il motore Python sugli stessi giorni;
3. **confrontare le operazioni una per una**: stesso minuto, stesso lato,
   stesso stop, stesso rischio.

In questa sessione fra pannello e motore sono emerse **nove divergenze**, e
ognuna faceva aprire operazioni che non esistevano: VWAP calcolato sui minuti
invece che sulle M6, soglie non riscalate, banda del rischio non controllata,
attesa e tetto giornaliero mancanti, orario letto dall'orologio invece che
dalla candela, ritracciamento preteso contrario invece che non-allineato,
mediana ATR NaN che azzerava i segnali in silenzio, candela scelta per
posizione invece che per istante, struttura letta "adesso" invece che
all'istante della decisione.

Un EA scritto da specifica e mai confrontato ha la stessa probabilita' di
sbagliare. **Nessuna divergenza residua e' accettabile prima di partire.**

---

## 4. Sul VPS

Vedi `docs/vps.md` per la macchina (Windows Server 2022, accesso solo RDP,
niente SSH; MT5 gia' installato; porta 8080 occupata da un altro progetto,
usare la **8090**).

Ordine di avvio:

1. copiare l'EA in `MQL5/Experts/`, compilare, verificare che non ci siano
   warning;
2. **prima istanza in demo** con il profilo B, e lasciarla girare almeno due
   settimane confrontando il suo CSV col registro del grafico;
3. solo dopo, le tre istanze sui tre conti;
4. far girare **anche `grafico_live.py`** accanto ai bot (vedi punto 5).

### La regola di spegnimento, da decidere prima di partire

Proposta: **fermarsi a −15 R** di perdita dal massimo. E' oltre il peggio del
periodo buono (12,6 R per la B) ed entro il peggio del periodo cattivo
(87,4 R). Senza una soglia decisa a freddo, la decisione la prende la paura.

### Due cose da verificare con FundingPips prima di comprare

1. **La perdita massima del 12% e' statica o dinamica?** Le taglie qui sopra
   la assumono **statica** dal saldo iniziale. Se e' calcolata sul massimo
   raggiunto e' piu' severa e le taglie vanno abbassate.
2. **Swap Free per la B.** Tiene le posizioni oltre la giornata e attraversa il
   fine settimana; sull'oro lo swap long di FP e' −71,5 punti a notte,
   **triplicati il mercoledi'**. Per C e D, che chiudono alle 21 UTC, non serve.

---

## 5. Il registro in avanti — la cosa piu' importante da non dimenticare

`grafico_live.py` scrive ogni segnale su `registro_segnali.jsonl`: l'istante in
cui e' stato **visto**, bid e ask reali, entry, stop, rischio, lo stato di
struttura di tutti i timeframe, quali condizioni erano vere. Registra anche i
**"vicino"** (una sola condizione mancante). Variabile `REGISTRO_SEGNALI` per
il percorso, `AVVISO_URL` per il webhook Telegram.

Perche' conta piu' di qualunque altra cosa in questo documento: il 2009-2019 e'
stato escluso per decisione, il 2023-2026 e' servito a scegliere le
configurazioni. **Non resta nessun fuori campione.** Ogni numero di questo
repository e' dentro il campione su cui e' stato scelto. Il registro e' l'unico
modo di produrne uno nuovo — e produce dati solo se gira.

Con la B che impiega 156 giorni mediani a passare la fase 1, il registro avra'
qualcosa da dire molto prima che la sfida finisca.

---

## 6. Cosa aspettarsi, detto onestamente

Le tre strategie rendono nel 2020-2026 (la B in ogni anno, la C in cinque su
sette, la D solo long in sei su sette) e **perdono in undici anni su undici
prima**. Non e' stata trovata **nessuna** grandezza misurabile
del mercato che cambi insieme al risultato: volatilita' relativa al prezzo,
spread relativo, quota di escursione notturna, persistenza infragiornaliera,
direzionalita' e tendenza di fondo sono uguali nei due periodi (appendici BW e
BX).

Restano due possibilita' che da qui non si possono distinguere: il vantaggio e'
reale e legato a qualcosa che non abbiamo saputo misurare, oppure e' il
risultato di aver cercato dentro il 2020-2026. Le misure disponibili — l'1% di
configurazioni che sopravvivono al cambio di periodo contro il 64% nel verso
opposto — puntano verso la seconda.

E c'e' un dato di tempistica che va guardato in faccia: **la peggiore serie
della B in sette anni e' quella appena finita** (febbraio-giugno 2026, un mese
prima della fine dei dati). Chi comincia adesso comincia subito dopo il peggior
momento che quella strategia abbia mai avuto. Puo' voler dire che e' passata,
o che sta degradando: non c'e' modo di saperlo prima.

Avviarle in demo, o con soldi che si possono perdere e una regola di
spegnimento scritta prima, e' legittimo. Chiamarle un vantaggio dimostrato no.
