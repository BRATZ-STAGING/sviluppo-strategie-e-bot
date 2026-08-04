# Trading Framework XAUUSD — guida per le sessioni

## Stato del progetto (leggere PRIMA di riscoprire qualcosa)

- **Stato corrente e storia**: `docs/sessions/` (nota più recente = verità),
  `docs/master-spec.md` (architettura e fasi), `docs/studies/` (risultati:
  NON rifare studi già fatti, i numeri sono lì).
- Codice in `trading/framework/`, script in `trading/scripts/`, test:
  `cd trading && python3 -m pytest tests/ -q` (134 test al 2026-07-07).
- Dati M1 **2009→2026** in `data/XAUUSD_M1/*.parquet` (BID, UTC, un file/anno),
  6,24 milioni di candele. `XAU_ANNI=2020-2026` limita gli anni caricati senza
  toccare il codice: serve a riprodurre i numeri pubblicati prima
  dell'estensione. Ogni `load_m1` stampa su stderr il periodo effettivo.
- Dipendenze: `pip install pandas pyarrow pytest tabulate` (non in repo).

## Il laboratorio (`trading/scripts/`)

`build_lab.py` costruisce la pagina dal template: `<lab.json> <lab.html>` per la
pagina con i dati dentro (pubblicabile), `--vuoto <lab.html>` per la versione
che chiede i dati a `/api/dati`. **Non sostituire il payload a mano.**

Il front-end e' uno solo per la pagina pubblicata e per la futura applicazione
di gestione: la pagina prova il payload incorporato e, se assente, lo chiede al
server locale. Piano completo e tappe in `docs/piano-app.md`.

## Bot in esercizio (`bots/`)

Il codice che opera davvero, separato dalla ricerca in `trading/`: Expert
Advisor MT5 in `bots/mt5/`, cBot cTrader in `bots/ctrader/`. Convenzioni e
scheda richiesta per ogni bot in `bots/README.md`. Mai committare eseguibili
compilati ne' credenziali o numeri di conto.

Un backtest fatto dentro MT5 o cTrader NON e' confrontabile con i numeri di
`docs/studies/`: convenzioni diverse su fill, spread e ordine fra stop e
obiettivo. Per confrontare, il bot va rigirato con il motore di questo
repository.

## Regole per NON sprecare token nelle analisi

1. **Mai stampare dati grezzi in chat**: gli script salvano il dettaglio in
   Parquet (scratchpad o `docs/studies/`) e stampano SOLO aggregati compatti
   (max ~20 righe, 3 decimali, `pd.set_option("display.width", 200)`).
2. **Salvare i risultati intermedi** su parquet e ricaricarli nelle analisi
   successive invece di rieseguire lo studio (gli studi completi girano in
   15-60s ma producono output lunghi).
3. Ogni studio nuovo va appuntato in `docs/studies/` in forma tabellare
   compatta: è la memoria tra sessioni, la chat non lo è.
4. I download (M1, tick) sono **riavviabili**: cache su disco, mai ripartire
   da zero. Vedi `trading/scripts/download_*.py`.
5. Preferire un solo comando python con output finale asciutto a molte
   invocazioni esplorative.

## Convenzioni tecniche (fonte di bug note)

- Tutti i timestamp UTC; candele etichettate all'APERTURA del periodo.
- Feed Dukascopy: URL con **mese 0-based**; prezzi interi in millesimi;
  rate limiting sui burst (usare i downloader esistenti con backoff).
- Sessioni UTC: asia 0-7, london 7-12, ny 12-21, late 21-24.
- NO lookahead: livelli asia attivi dalle 07:00; swing confermati k barre
  dopo l'estremo; stato di trend causale via `structure.trend_state_series`.
- Backtest conservativo: nella stessa candela lo stop prevale sul take;
  fill dei market all'apertura della candela successiva.
- Timeframe canonici in `data.TIMEFRAMES` (inclusi M33/M66 non nativi MT5).

## Cosa NON fare

- Non committare CSV/tick nel repo (solo Parquet M1 annuali + codice + docs).
- Non fidarsi di risultati "troppo belli": cercare lookahead (è già successo
  con la confluenza asia, vedi `docs/studies/rr-intraday-study.md` §2, e con
  l'istante degli eventi sui livelli, appendice BB).
- **Il placebo che va bene quanto il vero e' un ALLARME, non una conferma**:
  se una zona spostata a caso rende come una vera, non e' la zona che
  funziona. E' cosi' che si e' scoperto il lookahead dell'appendice BB.
- Negli studi sui livelli, l'istante di un evento e' la **chiusura** della
  candela, mai l'apertura: registrare l'apertura significa entrare al prezzo
  di chiusura e ripercorrere la candela sapendo gia' come finisce, e il
  vantaggio finto cresce col timeframe. Bloccato da `test_eventi_livelli.py`.
- Non fare grid-mining di filtri: ipotesi pre-registrate e verifica per anno.
- Push frequenti: i container sono effimeri, il lavoro non pushato muore.

## La taratura ufficiale (`trading/framework/taratura.py`)

Un solo posto per i numeri della strategia: `UFFICIALE = Taratura()`. Gli
script la importano, i test la bloccano. Configurazione scelta e verificata
fuori campione (misure in `docs/studies/rr-intraday-study.md`):

- ingresso M6 su reclaim del VWAP giornaliero, H6 e H2 allineati
- conferme: **M33 e H12 allineati**, **M12 contrario** (ritracciamento)
- filtro di fondo: chiusura D1 contro media 50 giorni
- obiettivo **1:10**, stop a **pareggio a +3R**, rischio **1%**
- soglie in dollari nei mesi normali, riscalate sull'ATR in quelli ad alta
  volatilita' (fattore 1,5)

Risultato sul 2020-2026: +171,1R su 348 operazioni, **7 anni positivi su 7**,
perdita massima 16%, 49.321 EUR da 10.000. Cambiare un numero qui cambia tutti
gli studi: farlo solo dopo una verifica per anno e fuori campione.

### ATTENZIONE — sul 2009-2019 la stessa taratura PERDE (appendici AU-AY)

Undici anni mai visti, aggiunti all'archivio il 03/08/2026: **-39,3 R su 382
operazioni, 3 anni positivi su 11, perdita massima 47,8 R** (contro 17,6 nel
periodo di casa). Le candidate A e B fanno peggio (-47,5 e -90,8). Non e' un
problema di soglie in dollari: normalizzando tutto all'ATR peggiora (-67,1 e
-105,3, ipotesi pre-registrata respinta, appendice AV).

Le tre verifiche successive sono tutte negative:

- **AW** nessun regime salva il periodo vecchio. Il filtro definito sul
  2020-2026 (volatilita', distanza dalle medie 50 e 200) lascia il 2009-2019
  a -15,9/-23,3 R: dentro e fuori perdono entrambi.
- **AX** togliere il lato corto migliora il rischio (DD da 54,5 a 39,2 sui
  diciotto anni, +0,58 R/op invece di +0,45 sul 2020-2026) ma **non cambia il
  segno**: il 2009-2019 solo long fa -29,5 R, per operazione peggio del
  sistema completo.
- **AY** la stessa ricerca su **2.268 celle** ripetuta sui due periodi: il
  meglio che si trova sul 2009-2019 e' +6,9 R su undici anni (nulla), mentre
  i vincitori trovati sul 2020-2026 valgono +223 R li' e -107 R altrove.
  **Solo l'1% delle celle scelte sul 2020-2026 resta positivo sul 2009-2019**,
  contro il 64% nel verso opposto. E' la firma del sovradattamento, e la
  taratura in vigore e' uno di quei vincitori.

**Conseguenza operativa**: il 2020-2026 non e' piu' un giudice sufficiente.
Ogni prova futura va chiusa sui diciotto anni. Quello che resta valido non e'
la strategia ma il METODO di misura (motore causale, spread e swap reali, gap
pagati alla riapertura, placebo e permutazioni): va applicato a un'idea nuova,
non a un'altra variante di questa.

## Strade gia' misurate e respinte (non ripercorrerle)

- **Stessa regola su timeframe piu' piccoli** (ingresso M3 o M1, obiettivi
  1:3-1:5): il vantaggio lordo si dimezza scendendo di TF e lo spread pesa il
  doppio in R. La migliore delle varianti piccole rende +0,20 R/op contro
  +0,49, guadagna solo dal 2022 in poi, e affiancata all'ufficiale DIMEZZA il
  conto a parita' di drawdown (correlazione mensile +0,776). Vedi appendice M.
- **Scalp su M1 con stop 1-3 punti e TP 5-10** (anche con contesto M6+M3):
  47 celle su 48 negative, con stop da 1 punto la percentuale di vinte coincide
  con il caso puro e la perdita e' il costo dello spread. Il contesto M6+M3 e'
  peggiore di H6+H2. Appendice U.
- **Stop fissi piccoli (2/3/5 $) su ingressi M3-M6 con obiettivi 1:3-1:5**:
  respinti su 72 celle. Tutte le regolarita' puntano nella direzione opposta a
  quella proposta: lo stop largo vince sempre (a 2 $ negativo quasi ovunque,
  su M3 in tutte le celle), M6 batte M3 in ogni cella, senza filtri perde in
  tutte e 24. La cella migliore (+0,443 R/op) e' peggiore della taratura in
  vigore (+0,492 su tre volte le operazioni e 7 anni su 7). Appendice Q.
- **Ritracciamenti di Fibonacci come livelli** (e lo scalping su di essi):
  respinti col placebo su due timeframe. I livelli finti alla stessa profondita'
  reagiscono uguale (4 confronti a 4 su M12; su M6 la differenza e' un
  decimillesimo di ATR con il 49% di probabilita' di essere caso). Il rapporto
  reazione/penetrazione e' 1,06-1,10, mentre lo scalping con stop da 2 $
  richiede il 66% di operazioni vinte solo per coprire lo spread. Appendice O.
- **Obiettivo appoggiato ai livelli** (swing non superati M33/H2/H6, OB
  contrario, estremi del giorno prima e della sessione Asia, numeri tondi;
  con e senza distanza minima 3R): nessuna famiglia batte il 1:10 fisso. I
  TP presi salgono fino al 24% ma proprio le famiglie con piu' TP sono le
  peggiori (asia -14 R, tondi 10 $ -31,7 R contro +171,1). Solo lo swing H6
  batte il proprio placebo a distanze uguali (+173 contro +129, p<0,005): sa
  dove NON mettere l'obiettivo, ma pareggia soltanto il 1:10 con 6/7 anni.
  Appendice AE.
- **Stop strutturale scalato x obiettivo** (moltiplicatore 0,5-2,0 sullo stop
  x RR 2-20, 84 celle): la riga m=1 domina la griglia per ogni obiettivo da
  1:3 in su. Stringere lo stop porta gli stop presi al 77%, allargarlo costa
  il 25-40% perche' ogni R vale meno. L'unica cella sopra il base (m=0,5,
  1:20: +187,9 R) ha il doppio del drawdown e in euro rende meno.
  Appendice AF.
- **Scale di trailing a gradini** (3>0 poi 5>2 poi 7>4, e trailing continuo a
  MFE-k), incrociate con obiettivi 1:5-1:12: 84 celle, nessuna batte il
  pareggio a +3R da solo. Ogni gradino in piu' toglie (-9,1 R il secondo,
  -25,7 R il terzo); il trailing continuo perde il 28% ed e' piatto su tutti
  gli obiettivi. Fra 1:5 e 1:9 la curva e' liscia, l'ottimo resta 1:10.
  Appendice AL.
- **Tenere aperto oltre la sera** (chiusura al venerdi' o nessuna chiusura,
  con le gestioni migliori): con lo SWAP REALE di FP (long -71,5 punti a
  notte, mercoledi' triplo, cioe' 0,151 R a notte con lo stop mediano) il
  vantaggio sparisce. La candidata migliore scende da +172,3 a +163,0 R,
  sotto la configurazione in vigore. Il rollover cade alle 21 UTC: chiudere
  a fine giornata costa zero swap. Appendici AO, AP, AQ.
- **I livelli come INGRESSO, tutti, in unita' di ATR** (ob pieno e raffinato,
  POC di ieri, estremi dell'area di valore, vuoti di volume; M33/M66/H2/H6;
  reazione, rottura, retest; stop 0,25-1 ATR; obiettivi 1:2-1:10): 168.833
  eventi su diciotto anni, **720 configurazioni, zero sopravvissuti** alla
  scrematura pre-registrata. R/op medio fra -0,15 e -0,22 per OGNI famiglia in
  ENTRAMBI i periodi, vinte al 48% (testa o croce), vantaggio mediano sul
  placebo +0,003 R/op. Le **confluenze** non selezionano: contate allo stesso
  prezzo, 167.808 eventi su 168.833 hanno gia' quattro famiglie sovrapposte,
  perche' i livelli stanno tutti dove il prezzo ha lavorato. Appendice AZ.
- **Order block ridefiniti come li usa l'utente** (validi finche' non toccati
  invece che 30 candele, tocco = chiusura dentro invece che ombra, conteggio
  dei tocchi, ribaltamento in supporto/resistenza dopo l'invalidazione):
  1.228.881 tocchi su 18 anni, tutte e quattro le domande NEGATIVE. Le zone
  oltre 120 candele rendono **peggio** (-0,094 R/op, 0 anni positivi su 11),
  non meglio; il secondo tocco vale come il primo e il terzo e' il peggiore;
  la chiusura dentro non batte l'ombra; i tocchi dopo l'invalidazione operati
  al contrario danno -0,023/-0,031 con differenza dal placebo fra 0,000 e
  0,005. Su 720 celle, 22 passano la ricerca e 5 sopravvivono: quello che
  darebbe il caso. Appendice BB.
- **Puntare a un win rate sopra il 50%**: e' una leva finta. Allargando lo
  stop la quota di vinte sale dal 41,8% al 48,8%, ma l'obiettivo 1:2 passa da
  14,2% a **0,2%** e il risultato resta negativo; il placebo ha le stesse
  quote. A RR 1:2, delle 180 celle misurate 9 superano il 50% di vinte e
  **nessuna** ha risultato positivo. L'unico numero che conta e' R/op.
  Appendice BC.
- **Soglie normalizzate all'ATR invece che in dollari** (ipotesi
  pre-registrata per spiegare il crollo fuori campione): respinta. Sul
  2009-2019 peggiora da -39,3 a -67,1 R con il riferimento ufficiale e a
  -105,3 con la mediana nota all'epoca; il 2020-2026 resta positivo in tutte
  e tre le versioni. Appendice AV.
- **Obiettivo variabile col regime di volatilita'**: inutile, 1:10 e' il
  migliore in entrambi i regimi (appendice K).
- **Chiusura parziale a meta' posizione**: costa il 27% del rendimento
  (appendice L).
- **Strategia "AVWAP a eventi"** (tocco/rottura/retest di VWAP ancorati e
  bande 1-3 sigma, compressione fra le bande, 9 TF da M3 a H6): scrematura su
  8,7 milioni di eventi, zero celle direzionali su 232 alla soglia
  registrata; la compressione supera il criterio formale solo per un
  artefatto (esito assoluto) e contro placebo vale 10-20 centesimi, sotto lo
  spread. Fase 2 (Fibo-estensioni, vuoti di liquidita' come TP) mai aperta.
  Appendice AB.
- **VWAP ancorato agli estremi non rotti (6 TF, con confluenze)**: dove un
  delta appare, il placebo con ancore a caso lo riproduce esattamente
  (M33 +0,255 vs +0,261; H2 -0,193 vs -0,216): proxy di "prezzo in
  equilibrio", nessuna informazione nell'ancora. Confluenza non monotona.
  Appendice Y.
- **Ordine limite sul livello invece che a mercato** (order block di
  M6/M12/M33/H3/H6, stop sulla zona o strutturale, distanze 5/10/20 $):
  respinto. Il rischio si dimezza (4,23 -> 2,2 $) ma la migliore versione
  rende +0,367 R/op su 189 operazioni e 4 anni su 7, contro +0,492 su 348 e
  7 su 7. Motivo misurato: **il ritracciamento seleziona i fallimenti** — le
  222 operazioni che tornano su un livello rendono -0,387 R/op nella
  strategia in vigore, le 126 che non tornano +2,040. Appendice AA.
- **Order block come segnale d'INGRESSO** (tocco della zona = entry, su
  M33/M66/H2/H3, RR 2-10, con e senza contesto/macro): 48 celle su 48
  negative, da -0,11 a -0,30 R/op, verifica avversariale confermata. La
  frequenza chiesta (1-5/settimana) si ottiene, il vantaggio no. L'OB e' un
  filtro sul segnale validato, non un ingresso. Appendice W.

## Order block: il risultato positivo NON regge sui 18 anni (appendice BA)

Definiti come l'utente li usa: zona dal minimo dell'ombra all'apertura per le
rialziste, simmetrica per le ribassiste; causali dalla chiusura della candela
che rompe. Sul 2020-2026 la **zona raffinata** (basi di OB e candela
successiva che combaciano) sembrava l'unico vantaggio solido del progetto:
+1,106 R/op nel testa-a-testa, verificato indipendentemente.

**Rimisurato sui diciotto anni non c'e' piu'.** Su M33 il segno si ribalta
fra i periodi (+0,400 sul 2009-2019, -0,595 sul 2020-2026); su cinque
timeframe su sei la differenza fra dentro e fuori e' negativa. Il motivo e'
nei conteggi: sul campione ufficiale, **in diciotto anni**, gli ingressi
dentro una zona raffinata sono 20 su M12, 12 su M33, 5 su M66, 4 su H2, 4 su
H3, 3 su H6. Il risultato migliore del progetto poggiava su qualche decina di
operazioni.

Codice in `trading/scripts/run_order_block.py` e `run_ob_18anni.py`.

## Aperti / da fare (non perdere)

- **Order block e altri livelli**: il bot target non usa solo il VWAP ma anche
  order block e altri livelli, ANCORA NON BEN DEFINITI. Vanno specificati con
  l'utente prima di implementarli (definizione operativa: quale candela, quale
  mitigazione, quale validita' temporale).
- **Parametri in unita' di volatilita'**: le soglie sono in dollari fissi
  (impulso 4$, rischio 1-10$, buffer 0.3$) ma il range M1 mediano e' passato da
  ~0.45$ (2020-24) a 1.05$ (2025) e 2.27$ (2026). Riparametrizzare in ATR.
  Nota: la riparametrizzazione secca **non** risolve il fuori campione
  (appendice AV), quindi vale come igiene, non come rimedio.
- **PRIORITA': la domanda aperta dopo AU-AY**. Le tre piste (regime, solo
  long, taratura invertita) sono state battute tutte e tre e sono negative:
  la risposta e' sovradattamento, non regime. Quindi NON ha senso cercare
  un'altra variante di questa famiglia. Le strade che restano sono due, e
  vanno decise con l'utente: (a) un'idea di ingresso diversa, misurata dal
  primo giorno sui diciotto anni; (b) accettare che il vantaggio esista solo
  in condizioni tipo 2020-2026 e trattarlo come scommessa sul regime, con
  dimensionamento tarato sulla perdita massima VERA (47,8 R, non 16).
- **Bug confermati dalla ri-validazione 2026-07**: resample_tf M33/M66 dipende
  dagli anni caricati; resample('1D') conta lo spezzone domenicale come giornata
  piena (17% di D1 monchi); da verificare la chiusura EOD del venerdi'.
- Timeframe: i TF grandi servono al contesto, i piccoli SOLO per l'entry precisa.
- **RR variabile in base alla qualita' del livello** (da specificare e testare):
  rischio 1-2% per operazione, RR da 1:3 fino a 1:10 a seconda di DOVE si
  entra. Esempio dell'utente: 1:10 su uno swing H6 confermato da H3, H2, M66,
  M33. Serve un punteggio di qualita' del setup (quante conferme, su quali TF)
  e una mappa punteggio -> obiettivo. Nota dai dati gia' raccolti: l'MFE
  raggiunge 5R nel 17% dei casi e 8R nel 9,5% (break-even a 1:10 = 9,1%),
  quindi un 1:10 indiscriminato perde: deve valere SOLO per il sottoinsieme
  di alta qualita', ed e' proprio questo che va dimostrato.
- **Lato short**: implementato (`run_long_short.py`). Da solo perde; con il
  filtro macro (chiusura D1 vs media 50gg) il sistema completo batte il solo
  long su rendimento e drawdown. Vedi Appendice 7.
