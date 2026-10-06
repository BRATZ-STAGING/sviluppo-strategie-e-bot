# Tick bid+ask come segnale (microstruttura, scalp su oro) — protocollo registrato (06/10/2026)

Richiesta dell'utente (piano di lavoro, "Direzione scelta"): un'ultima scommessa
sui **tick bid+ask** come segnale, coerente con l'obiettivo **scalp/intraday
>= 1-2 operazioni al giorno su FP Markets Raw**, vincolante finche' la strada
non e' bloccata. Scritto prima di qualunque calcolo sui tick (nessuna
statistica, campione o grafico guardato); rivisto dal `verificatore` il
06/10/2026 prima del lancio, sempre senza dati. I tick sono l'unica classe di
dati mai usata come segnale; scalp M1 respinto (rr-intraday app. U: il costo e'
lo spread), TF piccoli (app. M), win rate come leva (app. BC); le soglie in ATR
sono respinte per i filtri della B (app. AV), non per normalizzare un segnale.

## Dati e periodi

- Tick Dukascopy XAUUSD bid+ask in ms, Parquet mensili
  `C:\dukascopy\parquet_out\XAUUSD_ticks_YYYY-MM.parquet` (`timestamp` ms UTC,
  `bid`, `ask` float32; `INDICE.csv` con tick, spread mediano, ore mancanti).
  Sono **quote**, non scambi: nessun lato aggressore, nessun volume. Prezzi
  portati in float64 e arrotondati al millesimo prima di ogni confronto; tick
  duplicati (stesso ms, stessi bid e ask) ridotti a uno.
- Copertura oggi 2022-11 -> 2026-07 (zero ore mancanti fino a giugno 2026;
  luglio 2026 e' parziale, fino al 06/07); backfill 2020-01 ->
  2022-10 in corso (blocco 2 Dati), eventuale estensione pre-2020. **Prima del
  lancio** `verifica_cache_tick.py` deve essere pulito; un'ora feriale marcata
  `.empty` e' un **buco**, non un'ora senza scambi.
- **Verifica = 2025-01-01 -> ultimo giorno disponibile**, aperta una volta
  sola e **solo se la scoperta produce almeno un candidato**: altrimenti resta
  vergine (vedi criterio di blocco). E' il regime di spread (0,5-0,9 $) in cui
  si opererebbe davvero.
- **Scoperta = tutto il disponibile prima del 2025-01-01**: minimo 2022-11 ->
  2024-12; se all'avvio il backfill 2020-01 -> 2022-10 e' completo (zero ore
  mancanti su `INDICE.csv`), 2020-01 -> 2024-12. Mai un backfill a meta'.
- **Tick pre-2020** (se arriveranno): controllo secondario di robustezza anno
  per anno, stesse 144 varianti e costi; **non decide**. Un mese vale se ha ore
  mancanti (incluse le `.empty` feriali) <= 2 % delle ore feriali e zero tick
  con ask < bid; un anno vale con >= 10 mesi validi; i semestri seguono la
  stessa regola di validita' del resto (<= 10 % di giorni non decidibili).
- **Congelamento**: il giorno del lancio si legge `docs/registro-dati.md` e si
  scrive il periodo effettivo in testa a `docs/studies/tick-microstruttura.md`
  **prima del primo calcolo**. Cartelle separate `D:\ricerca_tick\scoperta\` e
  `...\verifica\` come in `ricerca_zero`.
- **Giorno di borsa** = giorno feriale con almeno un tick nella finestra
  operativa. Nessun giorno viene escluso con informazione di fine giornata.

## Istante di decisione e causalita' (vincolante)

Decisioni su una **griglia di 1 secondo** (istanti interi UTC) con i soli tick
con `timestamp < t_dec`: il tick con timestamp uguale e' futuro, cosi' i
pareggi in ms sono risolti per costruzione. `mid` = (bid+ask)/2 dell'ultimo
tick prima di t_dec; `mid` a t_dec - W = ultimo tick con timestamp < t_dec - W.
**Non si decide** (regole tutte causali) se: l'ultimo tick ha piu' di 60 s
(feed fermo, inizio di un buco); la finestra W contiene un buco > 60 s; i tick
dell'ultima ora (60 min prima di t_dec) sono **< 25 % della mediana** dei tick
della stessa ora del giorno nei 20 giorni di borsa precedenti (feed povero).
Un **giorno non decidibile** = meno del 50 % dei secondi della finestra
operativa era decidibile; serve solo alla validita' dei semestri, non a
escludere il giorno (che resta nel denominatore di t e della frequenza).
La decidibilita' dipende solo dal feed, non dalle varianti: la **tabella dei
semestri validi si calcola e si scrive al congelamento, prima del primo
segnale**. Servono **>= 3 semestri validi in scoperta e >= 2 in verifica**;
altrimenti lo studio e' **NON DECIDIBILE**: torna all'area Dati e **non chiude
ne' apre la strada**.

**Soglie = quantili causali**: quantile q della statistica campionata sulla
griglia di 1 s dentro la finestra operativa dei **20 giorni di borsa
precedenti**, calcolato alle 00:00 UTC e **congelato per la giornata**. Mai sul
campione intero, mai sulla giornata in corso. I 20 giorni precedenti valgono
anche se appartengono alla scoperta (per la verifica sono passato); i primi 20
giorni della scoperta non operano.

Il segnale scatta **all'attraversamento**: statistica **< soglia** al secondo
prima e **>= soglia** ora; non finche' resta sopra. **Una posizione alla
volta** per variante; ogni variante e' simulata da sola.

## Le quattro famiglie (ognuna in due versi)

Parametri comuni **W in {5 s, 30 s, 120 s}**, **q in {0,95; 0,99}**. Direzione
d del segnale; verso **continuazione** = si opera in direzione d, verso
**ritorno** = contro d. Una "variazione del mid" conta solo se |delta mid| >=
0,001 $ (i mezzi passi da un solo lato della quota non contano: scelta
dichiarata); sotto, la direzione e' zero e non c'e' segnale.
- **(a) Squilibrio**: tick-rule sui cambi del mid negli ultimi W s, S =
  (rialzi - ribassi)/(rialzi + ribassi) con >= 10 cambi; soglia = quantile q di
  |S|; d = segno di S.
- **(b) Spread**: shock = spread dell'ultimo tick >= quantile q dello spread;
  rientro = entro W s dall'inizio dello shock lo spread torna <= mediana dei 20
  giorni. Segnale al rientro; d = segno dello spostamento del mid dal primo tick
  dello shock al rientro.
- **(c) Intensita'**: N = tick negli ultimi W s; soglia = quantile q di N; d =
  segno della variazione del mid negli stessi W s.
- **(d) Velocita'**: V = (mid_t - mid_{t-W}) / sigma_W, sigma_W = dev. std
  delle variazioni del mid a W s campionate sulla griglia negli ultimi 60 min
  (>= 30 campioni); soglia = quantile q di |V|; d = segno di V.

## Orizzonti, stop, finestra operativa

- **Uscita a tempo H in {30 s, 2 min, 10 min}**, ordine a t_ingresso + H
  (t_ingresso = istante del fill) eseguito con la latenza. Niente griglie di
  stop/obiettivi, trailing o chiusure parziali (respinti).
- **Stop di sicurezza** unico: 0,20 % del prezzo d'ingresso (~7 $ a 3.500 $),
  solo contro gli estremi. Scatta al primo tick con bid (long) <= livello /
  ask (short) >= livello; si esegue con la latenza al prezzo della quota in
  vigore, **mai al livello**.
- **Finestra**: ingressi 07:00:00-20:44:59 UTC; posizioni aperte chiuse al
  primo tick >= 20:55. Niente rollover 20:45-22:15, apertura domenicale o
  chiusura del venerdi' (fuori finestra per costruzione).
- **Buchi del feed**: si smette di decidere dall'inizio del buco (regola dei
  60 s); una posizione aperta esce al primo tick dopo il buco, al suo prezzo,
  e **conta** come ogni altra operazione. Nessuna esclusione a posteriori.

## Costi istante per istante (FP Markets Raw, nessun credito)

- Long: ingresso all'**ask** e uscita al **bid**; short simmetrico. Piu'
  **0,06 $/oncia** round trip (commissione Raw).
- **Latenza base 500 ms**, **stress 1 s**, su ogni ordine (ingresso, uscita a
  tempo, stop). Due convenzioni di fill, entrambe calcolate: **"quota in
  vigore"** = prezzo dell'ultimo tick con `timestamp <= t_ordine + latenza`
  (fill a t_ordine + latenza; e' la convenzione di riferimento, causale);
  **"primo tick successivo"** = primo tick con `timestamp >= t_ordine +
  latenza` (fill al suo timestamp). La promozione richiede netto > 0 sulla
  **peggiore** delle due.
- **Spread x1,5**: fill a mid +/- 0,75 x spread della quota usata.
- Quattro scenari per variante: x1/500 ms, x1,5/500 ms, x1/1 s, x1,5/1 s.
  Sono scenari, non varianti. **Scenario di riferimento** per t, semestri,
  placebo e classifica: **x1,5/500 ms, quota in vigore**.
- **Scelta conservativa dichiarata e limite**: FP quota +0,195 $ sopra il bid
  Dukascopy (livello, non spread) e il suo spread istante per istante **non e'
  misurabile** (niente tick FP): nessun credito per uno spread FP piu' stretto.
  **Secondo limite**: intensita', shock di spread e tick-rule sono proprieta'
  del **feed Dukascopy**; su FP lo stesso istante puo' non produrre il segnale
  (altri tick, altra cadenza). Si misura solo in demo (sotto).

## Varianti (dichiarate)

4 famiglie x 2 versi x 3 W x 2 q x 3 H = **144 varianti**, cioe' **72 coppie
speculari**: continuazione e ritorno della stessa cella hanno lordo opposto
(G_exe di una = -G_exe dell'altra a meno di latenza e stop di sicurezza) e differiscono solo per
i costi; le ipotesi indipendenti sono 72 segni, non 144. Tutte in scoperta,
ognuna sotto i 4 scenari x 2 convenzioni di fill. Nessun altro parametro:
niente filtri d'orario o di volatilita', niente combinazioni fra famiglie. Un
parametro in piu' dopo = studio nuovo, non ammesso da questo protocollo.

## Misura lorda prima della netta (cuore del criterio di blocco)

Per variante e periodo, oltre al netto: **G_dec** = movimento medio mid-to-mid
nel verso operato dal mid di decisione al mid d'uscita; **G_exe** = idem dal
mid della quota d'ingresso (G_dec - G_exe = costo della latenza); **C_seg** =
mezzo spread della quota d'ingresso + mezzo spread della quota d'uscita + 0,06
$; **allargamento** = spread della quota d'ingresso / spread mediano dei 20
giorni (gli spread si allargano quando il segnale scatta: va misurato). Se
G_exe < C_seg per tutte le 144 varianti la conclusione e' gia' presa.

## Promozione (sulla sola scoperta)

Candidata se, in scoperta, valgono **tutte**:
1. netto > 0 in **tutti e quattro** gli scenari, sulla peggiore delle due
   convenzioni di fill (8 combinazioni);
2. **t >= 3** nello scenario di riferimento: t = media / (dev. std / sqrt n)
   sui totali netti per giorno di borsa, giorni a zero operazioni inclusi (le
   operazioni non si sovrappongono; i totali giornalieri assorbono
   l'autocorrelazione intraday);
3. **semestri validi positivi >= 2/3** arrotondato per eccesso, nello scenario
   di riferimento; semestri solari, un parziale sotto i 3 mesi si fonde col
   vicino; un semestre con **> 10 % di giorni non decidibili non e' valido**
   (esce dal conteggio, ne' positivo ne' negativo, e si riporta);
4. **frequenza >= 1 operazione per giorno di borsa** in media;
5. **placebo di direzione p < 0,01**: stessi istanti e fill, direzione casuale,
   1.000 ripetizioni (netto = +/- G_exe - costo), seme 20261006;
6. **placebo d'orario p < 0,01**: ogni segnale spostato a un istante casuale
   della stessa ora del giorno in un altro giorno di borsa, stessa direzione,
   fill ricalcolati sui tick veri, 200 ripetizioni, seme 20261007.
Al massimo **5 candidati**, per t decrescente nello scenario di riferimento.

## Verifica (una volta sola, 2025-01-01 -> fine dati)

Si apre **solo** con >= 1 candidato e si girano **solo i candidati**; le altre
varianti non si calcolano sul periodo. Per k candidati t >= 2 (k = 1), 2,4
(2-3), 2,6 (4-5) nello scenario di riferimento; netto > 0 negli 8 scenari x
convenzioni; semestri validi positivi >= 2/3; frequenza >= 1/giorno; entrambi i
placebo p < 0,05 (stessi semi). Semestri: 2025 H1, 2025 H2, 2026 H1 + luglio
2026 (parziale, si fonde con 2026 H1) = 3 semestri, quindi >= 2 positivi; mesi
oltre luglio scaricati prima del congelamento entrano con la stessa regola di
fusione. Si riportano tutti i candidati; se ne passa piu' d'uno, va avanti
**solo il migliore per t nello scenario di riferimento**, gli altri si
riportano e basta.

## Potenza e natura della decisione

La verifica ha ~400 giorni di borsa. Un candidato con l'effetto vero minimo
richiesto in scoperta ha in verifica: con la scoperta minima (t = 3 su ~560
giorni) t atteso ~2,5, **potenza ~70 % a soglia 2 e ~50 % a 2,6**; con la
scoperta estesa 2020-2024 (t = 3 su ~1.250 giorni, effetto piu' piccolo) t
atteso ~1,7, **potenza ~38 % a soglia 2 e ~20 % a 2,6**. Stime ottimistiche:
t = 3 e' il massimo su 72 coppie, quindi gonfiato dalla selezione.

Severita' dei costi, dichiarata: gli 8 scenari sono annidati e il vincolo
effettivo e' **x1,5 / 1 s sulla convenzione di fill peggiore** (costo al
segnale ~0,6-0,7 $ nel 2023-24, ~0,9-1,4 $ nel 2025-26, piu' la latenza). Si
promuove quindi solo un vantaggio lordo di almeno **~2 volte il costo reale**:
e' una scelta di prudenza, non una misura, e con la previsione 3 il protocollo
prevede la propria chiusura. Non chiude per costruzione (un lordo di 1-2 $ a
10 min passerebbe).

Quindi "zero candidati
passano" **chiude la strada come decisione pre-registrata**, con una
probabilita' dichiarata di scartare un vantaggio vero; non e' la prova che il
vantaggio non esista. Si accetta in anticipo: e' il prezzo di non prolungare la
ricerca.

## Criterio di blocco della strada scalp (non reinterpretabile)

**Se la scoperta non produce candidati, oppure nessun candidato passa la
verifica con i costi Raw come sopra, l'obiettivo scalp/intraday vincolante
(>= 1-2 operazioni al giorno) e' CHIUSO nel suo insieme**: a minuti lo era gia'
(app. U, M), a livello di tick lo chiude questo studio. La Regia successiva
rinegozia l'obiettivo (frequenze piu' basse) o chiude la ricerca di nuove
strategie, come da piano. Nel primo caso la verifica non si apre e resta
vergine. L'unica uscita diversa e' lo studio **NON DECIDIBILE** per mancanza
di semestri validi (sezione causalita'), stabilito al congelamento prima di
ogni segnale: allora si torna ai Dati e il criterio non scatta.

Non basta e non riapre nulla: passare in lordo (G_dec o G_exe > 0) ma non in
netto; passare in alcuni scenari o in una sola convenzione di fill; passare
solo in scoperta, o in verifica senza essere stati candidati; un solo
semestre positivo o un netto fatto da un semestre solo; passare in una
sotto-finestra oraria, su un sottoinsieme di giorni, con W, q, H fuori lista o
con una "variante successiva" della stessa famiglia; passare ipotizzando uno
spread FP piu' stretto di Dukascopy.

**Se passa la verifica** (uno o piu': avanza solo il migliore) la strada non
e' "aperta": il candidato va in **forward demo** FP (paper) con spread FP
registrato tick per tick dal terminale e conteggio dei segnali sul feed FP
confrontato con quello sui tick Dukascopy degli stessi giorni. Durata: **>= 60
giorni di borsa E n >= max(1.000; (2 sigma/mu)^2)** operazioni, con mu = netto
per operazione atteso dalla verifica e sigma la sua dev. std (cioe' errore
standard < meta' dell'atteso). **Durata massima 250 giorni di borsa**: se n
non e' raggiunto entro allora la demo e' fallita e l'obiettivo resta chiuso.
Regole di spegnimento scritte prima dell'avvio:
netto demo < 0 raggiunto n; netto per operazione < 50 % di mu; costo medio
misurato > C_seg della verifica x1,5; segnali sul feed FP < 50 % di quelli
Dukascopy. Solo una demo che le supera tutte fa dire "obiettivo riaperto".

**Riapertura legata ai costi, unica scappatoia**: sia G* il miglior G_exe per
operazione **dei soli candidati promossi in scoperta, misurato in verifica**
(scenario x1/500 ms, quota in vigore). Senza candidati dalla scoperta non
esiste G* e la strada e' chiusa senza appello. Con candidati, la strada si
riapre **solo** se il costo medio round trip misurato sul conto FP, con tick
FP registrati per **20 giorni di borsa consecutivi da una data fissata per
iscritto prima della misura**, agli stessi orari, risulta **C_FP <= G*/2**. In
quel caso si rigira **questo protocollo** sui candidati, riscalando lo spread
Dukascopy istante per istante col rapporto FP/Dukascopy misurato per fascia
oraria; nessuna famiglia nuova. Un candidato che passa la rigirata va comunque
in **forward demo** con le stesse regole (durata, spegnimenti, 250 giorni):
la rigirata da sola non riapre nulla. Nient'altro riapre la strada.

**Perimetro, con onesta'**: i tick sono solo dell'oro; per i cambi non
esistono tick nel progetto e non si scaricano. Il verdetto dell'oro chiude
l'**obiettivo vincolante nel suo insieme** (oro e cambi), perche' il piano lo
lega a "nessuna regola sui tick passa la verifica". `docs/fx-intraday-
registrazione.md` (cambi a minuti) resta un protocollo in coda che la Regia puo'
far girare, ma il suo esito **non riapre l'obiettivo vincolante**: al massimo
alimenta una rinegoziazione gia' decisa.

## Trappole di lookahead dei tick (test unitari prima del lancio)

In `trading/tests/test_tick_micro.py`, con tick sintetici, prima del primo
calcolo sui dati veri: (1) fill nel futuro: nessun fill usa un tick con
timestamp > t_ordine + latenza in "quota in vigore" (che puo' essere l'ultimo
tick prima di t_dec se il prezzo non e' cambiato); in "primo tick successivo"
il timestamp e' >= t_ordine + latenza;
(2) quantili sul campione intero: cambiare i tick futuri non cambia la soglia
di oggi, identica per tutti i secondi della giornata; (3) timestamp uguali:
tick con timestamp == t_dec esclusi; (4) duplicati (stesso ms e prezzi)
ridotti a uno; (5) buchi weekend/feed e ore `.empty` feriali = buco: nessun
segnale se W o il tick precedente attraversano un buco > 60 s (una velocita'
sopra un buco e' un segnale falso); (6) regola del 25 % dei tick dell'ultima
ora calcolata solo sul passato; (7) sessione: nessun ingresso fuori
07:00-20:44:59, nessuna posizione dopo le 20:55 ne' la domenica; (8) stop al
prezzo della quota, mai al livello; (9) tick con ask < bid scartati e contati,
e con spread zero G_exe e netto differiscono solo di 0,06 $ (coerenza); (10)
ordinamento stabile, storia di 20 giorni e finestra W attraversano i file
mensili senza troncarsi; (11) float32: differenze in float64 arrotondato al
millesimo e tick-rule solo su |delta mid| >= 0,001 $; (12) attraversamento con
"< prima, >= ora"; (13) coppie speculari: con lo stop di sicurezza
disattivato, G_dec(continuazione) = -G_dec(ritorno) esattamente.

## Previsioni

1. Allargamento medio al segnale >= 1,3 per intensita' e velocita', <= 1,15
   per lo squilibrio.
2. Continuazione a 30 s in (c) e (d): G_exe positivo ma piccolo (0,05-0,15 $),
   sotto C_seg (>= 0,40 $ nel 2023-24, >= 0,65 $ nel 2025-26); almeno il 90 %
   delle 144 varianti e' negativo gia' a x1/500 ms.
3. **Segno**: la continuazione batte il ritorno in lordo a 30 s e 2 min
   (momento di pochi secondi); a 10 min il ritorno torna in pari o leggermente
   sopra. Nessun lordo oltre 0,30 $ per operazione.
4. **Famiglia (a)**: la piu' debole, |G_exe| < 0,03 $ in tutte le celle: il
   tick-rule sulle quote conta aggiornamenti dei market maker, non pressione.
5. Ritorno a 10 min: G_exe intorno a zero; la latenza costa di piu' con W = 5 s
   (G_dec - G_exe >= 0,05 $).
6. Zero candidati in scoperta negli 8 scenari x convenzioni; se uno passa la
   scoperta, nessuno passa la verifica (spread 2025-26 circa doppio del 2023).
7. La frequenza non e' il vincolo: decine di segnali al giorno anche a q = 0,99.

## Output dichiarati

Motore `trading/framework/tick_micro.py` (non tocca `taratura.py`), script
`trading/scripts/run_tick_micro.py`, test `trading/tests/test_tick_micro.py`.
Operazioni dettagliate (milioni di righe) in `D:\ricerca_tick\<periodo>\`, fuori
dal repo; aggregati per variante x scenario x convenzione x semestre in
`docs/studies/dati/tick_micro_scoperta.parquet` e `tick_micro_verifica.parquet`;
a video solo le migliori per famiglia x verso (<= 20 righe: G_dec, G_exe, C_seg,
allargamento, netto x1 e x1,5, t, op/giorno, semestri validi, placebo). Studio
in `docs/studies/tick-microstruttura.md` con periodo congelato in testa.
