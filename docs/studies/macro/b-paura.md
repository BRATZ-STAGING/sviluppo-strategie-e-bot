# Famiglia B — Paura e volatilita' (VIX, GVZ) sull'oro (scoperta 2009-2017)

Protocollo: `docs/macro-oro-registrazione.md`. Script:
`trading/scripts/macro_b_paura.py`. Dati: solo
`D:\ricerca_macro\scoperta\MACRO_D1.parquet` (giornata dell'oro 22->22 UTC,
colonne gia' sfasate: VIX e GVZ della data D sono noti alla chiusura di D).
Il GVZ esiste dal 18/09/2009; le regole con percentili sui 252 giorni
precedenti partono quindi da gennaio 2010 (VIX) e da settembre 2010 (GVZ).

## Varianti dichiarate PRIMA del calcolo (06/10/2026)

Regole fisse (non sono dimensioni di ricerca):
- solo giornate `valida = True`; ATR20 = media del true range delle 20
  giornate valide fino al segnale s compreso; percentile p "sui 252 giorni
  precedenti" = quantile p dei 252 valori delle giornate valide s-252..s-1
  (s escluso; almeno 200 valori presenti); RV20 = deviazione standard dei 20
  rendimenti logaritmici di chiusura fino a s, x radice(252) x 100 (stessa
  unita' del GVZ); VRP = GVZ(s) - RV20(s);
- segnale alla chiusura di s; finestra (a, b): entrata a mercato
  all'apertura della giornata s+a, uscita alla chiusura di s+b (a = 1 e'
  l'entrata "il giorno dopo"; a = 4 o 6 salta i primi giorni dopo il picco);
- stop (quando c'e') a 2 x ATR20(s) dall'entrata, toccato se il minimo (long)
  / massimo (short) lo raggiunge; uscita allo stop, o all'apertura se la
  giornata apre gia' oltre; 1R = 2 x ATR20(s) in tutte le varianti;
- eventi = **inizio** della condizione (vera in s, falsa in s-1); una sola
  posizione per regola, segnali ignorati mentre e' aperta; operazione scartata
  se l'uscita cade oltre il 29/12/2017;
- costi 0,46 $ round trip (x1 e x1,5); swap long -0,715, short +0,325
  $/oncia/notte x close/4156,98, notti = giorni lun-ven dall'entrata
  all'uscita compresi, mercoledi' x3 (come `multi_f2_ritorno.py`).

**B1 — picchi di VIX (252 regole).** Eventi (9): VIX(s) > percentile 90 / 95 /
99 dei 252 giorni precedenti (3); salto VIX(s)/VIX(s-L) - 1 > k con L = 1, 3,
5 giornate e k = 20%, 40% (6). Direzione: long (rifugio) / short
(liquidazione) (2). Finestre (a, b): (1,1) (1,3) (1,5) (1,10) (1,20) (4,10)
(6,20) (7). Stop: no / 2 x ATR20 (2). 9 x 2 x 7 x 2 = **252**.

**B2a — eventi GVZ (128 regole).** Eventi (4): GVZ > p90, GVZ > p95, GVZ < p10
(252 precedenti), salto GVZ(s)/GVZ(s-5) - 1 > 20%. Direzione (4): long, short,
rientro (contro il segno di close(s) - close(s-5)), segue (nel verso di
close(s) - close(s-5)). Finestre (1,1) (1,5) (1,10) (1,20) x stop no/si'.
4 x 4 x 4 x 2 = **128**.

**B2b — GVZ e VRP come filtro di regime (60 regole).** Basi (6): LONG
continuo con tenuta 1, 5, 20 (si rientra alla prima giornata libera);
BREAKOUT 20 (close(s) > massimo delle 20 chiusure precedenti -> long, <
minimo -> short) con tenuta 5, 10, 20. Stop no/si' (2). Regime al segnale (5):
nessuno, VRP alto (> p67 dei 252 precedenti del VRP), VRP basso (< p33), GVZ
alto (> p67), GVZ basso (< p33). 6 x 2 x 5 = **60**.

**B3 — interazione VIX/GVZ (96 regole).** Eventi (4): VIX > p90 e GVZ <= p50
(paura azionaria, oro calmo); VIX > p90 e GVZ > p90 (paura su entrambi);
rapporto GVZ/VIX > p95; GVZ/VIX < p5 (percentili sui 252 precedenti).
Direzione (3): long, short, rientro. Finestre (1,1) (1,5) (1,10) (1,20) x
stop (2). 4 x 3 x 4 x 2 = **96**.

**Totale: 252 + 128 + 60 + 96 = 536 varianti**, tutte promuovibili.

Misure per regola: n, operazioni al mese, episodi indipendenti (segnali a piu'
di 20 giornate dal precedente aprono un episodio nuovo), netto medio e totale
in R (x1 e x1,5, con swap) e in $/oncia, t sui rendimenti mensili (somma per
mese d'uscita, mesi vuoti = 0, dal primo mese in cui la regola puo'
segnalare) e t sulle operazioni (non sovrapposte per costruzione), anni
positivi su 9 (2009-2017; un anno senza operazioni non e' positivo),
drawdown in R, "sempre long" nella stessa finestra e gestione (netto medio di
un long a ogni giornata ammessa dello stesso periodo). Placebo, 1000 serie,
seed 12345, statistica = netto totale R a x1, p = (1 + #placebo >= reale)/1001:
DIREZIONE (stesse entrate, direzione casuale, stop speculare); DATE NEL
REGIME (stessa direzione e gestione, data casuale fra le giornate dello stesso
regime: VIX > mediana dei 252 precedenti per B1 e B3, GVZ > mediana per B2a,
il filtro stesso per B2b); DATE QUALSIASI (riferimento).

Promozione: netto > 0 a x1 e x1,5; t mensile >= 3; anni positivi >= 7 su 9;
p direzione < 0,01 e, per le regole a direzione fissa (long o short), anche p
date nel regime < 0,01. Al massimo 3 candidati in ordine di t. Analisi
descrittiva (non promuovibile): rendimento dell'oro in R dopo gli eventi B1,
separato per giornate 1, 2-3, 4-5, 6-10, 11-20, contato sul primo evento di
ogni episodio.

## Risultati (06/10/2026)

Controlli: motore confrontato con un ciclo giornata per giornata su 400
entrate casuali (finestra, stop, direzione, notti di swap, costo): differenza
massima 1e-15. Calcolo completo 6 s.

**Varianti provate: 536, tutte valutate. Promosse: 0. Nessun candidato.**
t mensile massimo 2,08 (nessuna variante con t >= 3, solo 2 con t >= 2 e 16
con t <= -2); p direzione < 0,01 in 0 varianti su 536 (attese ~5 per caso);
anni positivi >= 7 in 4 varianti (long dopo salti del VIX a 3-5 giorni
ritardato/10 giornate, breakout 20 con VRP alto), tutte con t <= 1,14.

| famiglia | varianti | netto > 0 | t mediano | t min / max | t >= 3 | passano |
|---|---|---|---|---|---|---|
| B1 picchi VIX | 252 | 41% | -0,15 | -2,19 / 1,76 | 0 | 0 |
| B2a eventi GVZ | 128 | 41% | -0,28 | -2,19 / 2,08 | 0 | 0 |
| B2b filtro GVZ/VRP | 60 | 33% | -0,63 | -2,56 / 1,71 | 0 | 0 |
| B3 VIX x GVZ | 96 | 54% | 0,03 | -2,31 / 1,60 | 0 | 0 |

### Quanti episodi ci sono davvero (segnali a > 20 giornate l'uno dall'altro)

| evento | eventi | episodi | anni con eventi |
|---|---|---|---|
| VIX > p90 / p95 / p99 | 44 / 29 / 12 | 18 / 10 / 8 | 8 / 7 / 5 |
| salto VIX 1g > 20% / > 40% | 39 / 6 | 20 / 6 | 8 / 5 |
| salto VIX 3g > 20% / > 40% | 74 / 15 | 28 / 13 | 9 / 6 |
| salto VIX 5g > 20% / > 40% | 81 / 26 | 39 / 18 | 9 / 7 |
| GVZ > p90 / > p95 / < p10 / salto 5g > 20% | | 12 / 9 / 29 / 27 | |
| VIX>p90 e GVZ<=p50 / VIX>p90 e GVZ>p90 | | 9 / 9 | |

Gli eventi "di vera paura" (p95, p99, salto di un giorno > 40%) sono 6-10
episodi in nove anni: nessuna statistica su di essi puo' arrivare a t >= 3
con anni positivi >= 7, anche se l'effetto fosse reale.

### Studio d'evento: oro dopo i picchi di VIX (lordo in R, primo evento di ogni episodio)

| evento (episodi) | giorno 1 | 2-3 | 4-5 | 6-10 | 11-20 | 1-20 |
|---|---|---|---|---|---|---|
| VIX > p90 (18) | -0,05 (t -0,6) | -0,20 (-1,6) | -0,11 (-0,7) | -0,03 | +0,08 | -0,31 (-0,7) |
| VIX > p95 (10) | +0,06 | -0,02 | -0,19 (-1,1) | +0,27 (1,1) | +0,43 (1,0) | +0,56 (1,1) |
| VIX > p99 (8) | +0,05 | +0,10 | +0,01 | +0,38 (1,1) | -0,03 | +0,51 (0,7) |
| salto 1g > 20% (20) | +0,04 | +0,10 | -0,08 | +0,35 (2,4) | +0,13 | +0,54 (1,2) |
| salto 1g > 40% (6) | +0,07 | -0,07 | +0,33 (2,5) | +0,66 (1,5) | +0,20 | +1,19 (1,7) |
| salto 5g > 20% (39) | +0,06 (1,2) | -0,05 | -0,01 | +0,09 | +0,19 (1,0) | +0,29 (1,2) |
| incondizionato | +0,004 | +0,008 | +0,007 | +0,023 | +0,062 | +0,104 |

Nei primi 1-5 giorni l'oro non fa nulla di riconoscibile (|medio| <= 0,2 R,
|t| <= 1,6, segno che cambia fra soglie vicine). Dal 6o giorno la media e'
quasi sempre positiva (+0,1/+0,7 R) ma con t <= 2,5 su 6-20 episodi.

### Regole B1 (t mensile mediano sui 9 eventi x 2 stop)

| direzione | (1,1) | (1,3) | (1,5) | (1,10) | (1,20) | (4,10) | (6,20) |
|---|---|---|---|---|---|---|---|
| long (rifugio) | -0,25 | -0,30 | -0,30 | 0,07 | 0,29 | 0,29 | 0,49 |
| short (liquidazione) | -0,20 | 0,11 | -0,36 | -0,87 | -0,69 | -0,62 | -0,68 |

Netto medio mediano del long: (1,1) -0,024 R, (1,20) +0,089 R, (6,20)
+0,136 R; "sempre long" nelle stesse finestre (2010-2017): -0,020 / -0,106 /
-0,076 R (l'oro 2011-2015 scende, lo swap long costa). Il long ritardato
batte il "sempre long" di ~0,2 R per operazione, ma su 6-39 episodi: t <= 1,8.

### GVZ ed interazione (t mensile mediano per evento e direzione)

| evento | long | short | rientro | segue |
|---|---|---|---|---|
| GVZ > p90 | -0,07 | 0,04 | -1,43 | 1,16 |
| GVZ > p95 | 0,81 | -0,87 | -0,97 | 0,84 |
| GVZ < p10 | -0,37 | -0,23 | -0,09 | -0,49 |
| salto GVZ 5g > 20% | -1,24 | 0,68 | -0,91 | 0,26 |
| VIX>p90 e GVZ<=p50 | -0,13 | 0,07 | 0,98 | |
| VIX>p90 e GVZ>p90 | 0,71 | -0,90 | -1,59 | |
| GVZ/VIX > p95 | -0,76 | 0,30 | 0,60 | |
| GVZ/VIX < p5 | 0,15 | -0,58 | 0,08 | |

Filtro di regime B2b (netto medio R, senza / con stop; t mensile senza stop):

| base | nessuno | VRP alto | VRP basso | GVZ alto | GVZ basso |
|---|---|---|---|---|---|
| LONG tenuta 1 | -0,017 / -0,016 (t -2,5) | -0,037 (-2,1) | -0,024 (-2,1) | -0,010 (-0,6) | -0,027 (-2,3) |
| LONG tenuta 20 | -0,052 / -0,009 (-0,9) | -0,389 (-1,6) | -0,158 (-1,0) | -0,147 (-0,6) | -0,126 (-0,6) |
| BREAKOUT20 tenuta 5 | +0,049 / +0,055 (1,0) | +0,097 (1,1) | -0,077 (-1,1) | +0,077 (0,8) | +0,091 (1,2) |
| BREAKOUT20 tenuta 10 | +0,070 / +0,038 (0,8) | +0,193 (1,0) | -0,135 (-1,1) | +0,169 (0,9) | +0,124 (1,0) |
| BREAKOUT20 tenuta 20 | -0,236 / -0,082 (-1,3) | +0,217 (0,8) | -0,429 (-2,6) | +0,081 (0,3) | -0,295 (-1,1) |

Le migliori 3 varianti (nessuna promossa):

| regola | n / episodi | netto R x1 / x1,5 | $/op | t mens / episodi | anni + | DD R | p dir / regime |
|---|---|---|---|---|---|---|---|
| GVZ > p95, segue (verso dei 5 giorni), (1,5), stop | 14 / 8 | 0,604 / 0,599 | +34,2 | 2,08 / 3,03 | 4 | 1,0 | 0,023 / 0,002 |
| GVZ > p90, segue, (1,5), senza stop | 20 / 10 | 0,431 / 0,426 | +18,0 | 1,78 / 1,51 | 5 | 1,5 | 0,042 / 0,006 |
| salto VIX 1g > 40%, long, (4,10) | 6 / 6 | 0,900 / 0,894 | +44,0 | 1,76 / 2,26 | 4 | 0,2 | 0,029 / 0,009 |

### Osservazioni

1. **I picchi di paura non danno all'oro una direzione nei primi giorni.**
   Ne' rifugio ne' liquidazione: giorno 1-5 dopo VIX > p90/p95/p99 o dopo un
   salto del VIX la media e' fra -0,2 e +0,3 R con |t| <= 2,5 e segno
   instabile fra soglie vicine. Il seguito (giorni 6-20) e' positivo in quasi
   tutti gli eventi (+0,1/+0,7 R, il long ritardato batte il "sempre long" di
   ~0,2 R a operazione) ma poggia su 6-39 episodi concentrati nel 2010-2011,
   2014-2015: non e' distinguibile dal caso (t <= 1,8, anni positivi <= 5).
2. **Il GVZ alto e' prosecuzione, non rientro.** Dopo un GVZ sopra il p90/p95
   la regola "nel verso degli ultimi 5 giorni" e' la migliore della famiglia
   (+0,4/+0,6 R, +18/+34 $ a operazione) e il "rientro" e' negativo; ma sono
   8-12 episodi, 4-5 anni positivi su 9 e p direzione 0,02-0,04. Coerente con
   il risultato F2 sui metalli (prosecuzione), non e' un'informazione nuova.
3. **Il premio per la volatilita' (GVZ - realizzata) non e' un filtro utile.**
   Nessun regime rende positivo il long (tutti i "LONG" sono negativi, peggio
   del non filtrato con VRP alto); sul breakout 20 il VRP alto e' un po'
   meglio del VRP basso (+0,1/+0,2 R contro -0,1/-0,4) ma con t <= 1,1. Nessuna
   delle 536 varianti ha p direzione < 0,01. Previsione per la famiglia B:
   nessun candidato verso la verifica 2018-2026.

Dettaglio in `D:\ricerca_macro\risultati\`: `b_varianti.parquet` (una riga
per regola con misure, anni, p), `b_operazioni.parquet` (una riga per
operazione e regola, con l'esito nella direzione opposta), `b_eventi_vix.parquet`
(studio d'evento per evento e tratto), `b_sempre_long.parquet` (netto medio
di un long a ogni giornata per finestra e stop, 2010-2017).
