# Famiglia A — Tassi e dollaro contro l'oro (scoperta 2009-2017)

Protocollo: `docs/macro-oro-registrazione.md`. Script:
`trading/scripts/macro_a_tassi.py`. Dati: solo
`D:\ricerca_macro\scoperta\MACRO_D1.parquet` (giornata d'oro 22->22 UTC;
Tesoro della data D-1, dollaro sintetico della data D, gia' sfasati da
`prepara_macro.py`). Nessun dato di verifica aperto.

## Griglia dichiarata PRIMA del calcolo (06/10/2026)

Regole fisse:
- solo giornate `valida = True` (4 scartate); "giornata" = riga valida;
- variabili: reale10, breakeven10, nom2 (variazioni in punti base),
  dxy_sint (variazione del logaritmo, in %); D_k x(s) = x(s) - x(s-k) con i
  valori della riga s, cioe' noti alla chiusura della giornata s;
- ATR20 = media del true range delle 20 giornate fino a s compresa;
  1R = 2 x ATR20(s) in tutte le regole;
- segnale alla chiusura di s, entrata all'apertura di s+1, uscita alla
  chiusura di s+H; una sola posizione per regola (segnali ignorati mentre e'
  aperta); entrate 2009-2017, scartata l'operazione che esce oltre i dati;
- costi: 0,46 $ round trip (x1 e x1,5); swap long -0,715, short +0,325
  $/oncia/notte x prezzo d'entrata / 4156,98; notti = giorni lun-ven
  dall'entrata all'uscita compresi, il mercoledi' vale 3 (convenzione f2).

**1. Mappa statistica** (non negoziabile, solo misura). Variabile (4) x
finestra del segnale k = 1, 5, 20 (3) x orizzonte h = 1, 5, 20 (3) = **36
celle predittive**: X = D_k x(s), Y = ln(chiusura(s+h) / apertura(s+1)).
Riferimento **contemporaneo** (4 x 3 = 12 celle): Y = ln(chiusura(s) /
chiusura(s-k)) contro la variazione della variabile sulle STESSE date di
calendario (Tesoro: valori della riga successiva, perche' la riga s contiene
il dato di D-1; dollaro: riga s). Per cella: r di Pearson su tutte le
giornate, t di Newey-West della pendenza (Bartlett, ritardo h+k-1), r sul
campione non sovrapposto (una giornata ogni max(h,k)), anni con r dello
stesso segno (su 9). **Consistente** = |t NW| >= 2, r non sovrapposto dello
stesso segno, stesso segno in >= 7 anni su 9.

**2. Regole** (calcolate tutte, per tutte le variabili, qualunque sia la
mappa: tutte contano come varianti).
- VARIAZIONE: z_N(s) = D_N x(s) / (dev. standard delle variazioni di una
  giornata sulle 250 giornate fino a s, minimo 60, x radice(N)). Segno "+"
  (direzione economica): reale10, nom2, dxy z <= -c -> long oro, z >= +c ->
  short; breakeven10 al contrario. Segno "-": l'opposto. Griglia: 4 variabili
  x N = 1, 5, 20 x c = 0,5, 1, 1,5 x H = 1, 5, 20 x modo (solo long segno +,
  solo long segno -, long e short segno +) = **324**.
- REGIME: in regime alla chiusura di s se media_f(x) < media_l(x) (reale10,
  nom2, dxy in calo; breakeven10 in salita: >); segno "-" = condizione
  opposta. Posizione tenuta nella giornata d se in regime alla chiusura di
  d-1; ogni tratto continuo = un'operazione (1R = 2 x ATR20 della giornata
  prima dell'entrata). (f, l) = (5, 20), (20, 60). Modi: solo long segno +,
  solo long segno -, long in regime e short fuori segno + -> 4 x 2 x 3 =
  **24**.

**Varianti: 324 + 24 = 348**, tutte promuovibili.

Misure: n, operazioni al mese, netto medio e totale in R (x1, x1,5, con
swap), netto totale in $/oncia, t sui rendimenti mensili (somma R per mese
d'uscita, mesi vuoti = 0) e sulle operazioni, anni positivi su 9 (anno senza
operazioni = non positivo), drawdown massimo in R. Riferimento "sempre long"
nello stesso periodo: per VARIAZIONE operazioni long consecutive con la
stessa tenuta H; per REGIME il long tenuto sempre (in $) e il rendimento
medio giornaliero dentro e fuori dal regime.

Placebo, 1000 serie, seed 12345, statistica = netto totale R a x1, p = (1 +
#placebo >= reale) / 1001: DIREZIONE (stesse operazioni, verso casuale) per
tutte; per le solo long anche DATE: VARIAZIONE = entrate casuali uniformi fra
quelle possibili con la stessa tenuta; REGIME = la serie del regime
spostata circolarmente di un numero casuale di giornate (60 .. n-60), che
tiene durata e numero dei tratti.

Promozione: netto > 0 a x1 e x1,5, t mensile >= 3, anni positivi >= 7/9,
p < 0,01 su tutti i placebo applicabili; al massimo 3 candidati in ordine di
t, non piu' di uno per variabile.

## Risultati (06/10/2026)

Controlli: motore confrontato con un ciclo esplicito su 300 operazioni
casuali (ATR20, prezzo d'uscita, notti di swap, costo): differenza massima 0.
Allineamento: la variazione giornaliera di reale10 presa dalla riga s+1
(stessa data di calendario della giornata d'oro s) ha r -0,27 con l'oro del
giorno; dalla riga s -0,06, dalla riga s+2 -0,02: lo sfasamento di
`prepara_macro.py` e' quello dichiarato. Il dollaro sintetico manca nel 2009
(cambi del paniere dal 2010): per dxy gli anni sono 8 (criterio resta 7/9).
2329 giornate valide, 4 scartate; buchi isolati riempiti con l'ultimo valore
noto. Tempo di calcolo 13 s.

**Varianti provate: 348** (324 VARIAZIONE + 24 REGIME), tutte valutate.
Netto > 0 nel 35,6%; t mensile: 5% -2,09, mediana -0,35, 95% +1,29;
**t >= 3 in 0**, <= -3 in 3. p direzione < 0,01 in 6. **Promosse: 0.**

### Mappa: contemporanea (riferimento, non negoziabile) contro predittiva

| variabile | contemporanea r (k = 1 / 5 / 20) | t NW (k = 1 / 5 / 20) | anni stesso segno | predittiva: r piu' forte (k, h) | t NW | consistente |
|---|---|---|---|---|---|---|
| reale10 | -0,270 / -0,363 / -0,462 | -10,5 / -9,1 / -6,6 | 9 / 9 / 9 | -0,070 (5, 5) | -1,78 | no (7/9, t < 2) |
| nom2 | -0,213 / -0,267 / -0,328 | -9,0 / -7,5 / -4,7 | 9 / 9 / 8 | -0,092 (5, 5) | -2,84 | si' |
| dxy_sint | -0,325 / -0,362 / -0,338 | -11,2 / -9,2 / -4,2 | 8 / 8 / 7 (su 8) | -0,074 (20, 20) | -1,44 | no |
| breakeven10 | +0,057 / +0,149 / +0,155 | +2,1 / +3,6 / +2,0 | 5 / 6 / 7 | +0,038 (5, 20) | +0,87 | no |

Celle predittive consistenti: **3 su 36**, tutte del 2 anni e tutte nel
verso della relazione contemporanea (2 anni in salita -> oro in calo dopo):
nom2 (k1, h5) r -0,043 t -2,3; (k5, h1) -0,050 t -2,4; (k5, h5) -0,092 t
-2,8, 9/9 anni. Ma sul campione NON sovrapposto il segnale quasi sparisce
(r -0,007, -0,026, -0,091 con t -0,1 / -0,6 / -2,0): la cella migliore e'
al limite, le altre due dipendono dalla sovrapposizione. Le altre 33 celle:
|t NW| < 1,9, r fra -0,07 e +0,04.

Nota fuori protocollo (solo misura): la variazione di reale10 della data
D-1, che il protocollo rende utilizzabile solo alla chiusura di D, ha r
-0,059 (t NW -2,6, 7/9 anni) con la giornata d'oro D stessa: la poca
informazione "in ritardo" dei tassi reali si consuma nella giornata che la
regola prudente salta.

### Regole VARIAZIONE (t mensile, tenuta H x soglia c, segnale su N giornate)

| variabile / modo / N | H1 c0,5-1-1,5 | H5 c0,5-1-1,5 | H20 c0,5-1-1,5 |
|---|---|---|---|
| reale10 L+ N1 | -0,4 / -0,4 / 0,3 | 0,0 / 0,2 / 0,1 | 0,3 / 0,7 / 0,2 |
| reale10 L+ N5 | 0,1 / 1,0 / 1,6 | 0,3 / 0,4 / **2,7** | 0,0 / -0,1 / 0,7 |
| reale10 L+ N20 | -1,1 / 0,5 / 0,4 | -1,2 / -0,2 / 1,0 | -0,3 / -1,4 / 0,9 |
| reale10 LS+ N5 | 1,1 / 1,2 / 1,3 | 0,6 / 1,0 / 2,5 | 0,1 / -0,7 / 0,4 |
| nom2 LS+ N1 | 0,4 / -0,8 / -0,4 | 1,4 / 1,7 / 1,3 | -0,3 / 1,1 / -0,7 |
| nom2 LS+ N5 | 0,3 / 1,5 / 2,4 | 0,7 / 1,8 / 1,9 | 0,1 / 0,6 / 1,3 |
| nom2 L+ N5 | 0,1 / 0,0 / 0,7 | 0,7 / 0,1 / 0,9 | 0,1 / -0,1 / 0,7 |

Per gruppo (t mensile mediano / massimo): reale10 L+ 0,18 / 2,74, LS+
0,56 / 2,53, L- -1,25 / 0,52; nom2 L+ 0,12 / 1,09, LS+ 0,26 / 2,44, L-
-0,92 / 0,71; breakeven10 da -0,52 a -0,35 di mediana, massimo 1,32; dxy
mediane -0,89 / -0,13, massimo 1,37.

Le migliori (nessuna passa t >= 3):

| | reale10 N5 c1,5 H5 L+ | reale10 N5 c1,5 H5 LS+ | nom2 N5 c1,5 H1 LS+ | nom2 N5 c1,5 H5 LS+ |
|---|---|---|---|---|
| n / op al mese | 48 / 0,47 | 100 / 0,95 | 178 / 1,66 | 86 / 0,80 |
| netto medio R (x1 / x1,5) | 0,285 / 0,278 | 0,175 / 0,169 | 0,052 / 0,046 | 0,151 / 0,145 |
| netto totale R / $ per oncia | 13,7 / 454 | 17,5 / 599 | 9,3 / 307 | 13,0 / 460 |
| t mensile | 2,74 | 2,53 | 2,44 | 1,89 |
| anni positivi | 8 su 9 | 7 su 9 | 5 su 9 | 7 su 9 |
| drawdown R | 1,7 | 4,2 | 2,9 | 3,2 |
| p direzione / date | 0,002 / 0,005 | 0,005 / - | 0,005 / - | 0,015 / - |

Anni (R): reale10 L+ 2009 0, 2010 +4,2, 2011 +2,2, 2012 +1,1, 2013 +0,1,
2014 +0,3, 2015 +1,1, 2016 +3,6, 2017 +1,2. nom2 H1 LS+: 2010-2013 tutti
negativi (-0,2 circa), 2015-2017 +2,1/+3,4: il 2 anni conta solo dopo la
fine dei tassi a zero (prima non si muoveva).

**Sempre long nello stesso periodo** (operazioni consecutive): H1 -0,017 R
per operazione (lordo +0,005, swap -0,009), H5 -0,027, H20 -0,052; un long a
caso perde perche' lo swap long (-0,173 R a 20 giornate) supera la deriva
dell'oro 2009-2017 (+0,135 R lordi). Il long tenuto sempre (da febbraio-aprile 2009, secondo la media) fa
-143 / -128 $/oncia netti, swap compreso.

### Regole REGIME (medie 5/20 e 20/60)

Nessuna con t > 0,8; netto > 0 solo per breakeven10 5/20 (L+ +0,10 R, t
0,51; LS+ +0,12 R, t 0,79, p direzione 0,13) e reale10 20/60 LS+ (+0,03 R,
t 0,10). Il regime "tassi reali in calo" NON migliora il long: con 5/20 l'oro
rende in media +0,9 bp al giorno dentro il regime e +2,2 fuori; con 20/60
+1,9 dentro e +1,0 fuori (differenze piccole e di verso opposto fra le due
medie). In $ per oncia: reale10 20/60 L+ -170 contro -128 del sempre long
nello stesso periodo; reale10 5/20 L+ -334 contro -143. Dollaro: tutte e 6
negative (t da -0,66 a -0,14).

### Candidati

**Nessuno.** La regola piu' vicina (reale10 sceso di almeno 1,5 deviazioni
standard in 5 giornate -> long 5 giornate) ha netto, anni (8/9) e placebo
(p 0,002 / 0,005) da promozione ma t mensile 2,74 < 3, su 48 operazioni, ed
e' una cella isolata: le vicine con c = 1 o H = 1/20 hanno t 0,4-1,6.

### Osservazioni

1. **Previsione 1 del protocollo confermata**: i tassi reali e il dollaro
   spiegano l'oro nello stesso periodo (r -0,27/-0,46 per reale10, -0,33/-0,36
   per il dollaro, 9/9 anni) ma non lo anticipano (|r| predittivo <= 0,07,
   t NW < 1,9). Il breakeven e' debole anche contemporaneamente (r +0,06/+0,16,
   5-7 anni su 9).
2. **L'unico residuo predittivo e' il 2 anni**, nel verso della relazione
   contemporanea (2 anni in salita -> oro piu' debole nei 1-5 giorni dopo),
   ma regge male sul campione non sovrapposto e nasce quasi tutto nel
   2015-2017 (fine dei tassi a zero): non e' un effetto stabile su 9 anni.
3. **I regimi di tendenza dei tassi non servono come filtro del long**: la
   differenza di rendimento dentro/fuori e' piccola e cambia segno fra le
   medie 5/20 e 20/60; nessuna regola regime batte il "sempre long" in modo
   significativo (p direzione >= 0,13). Sull'oro 2009-2017 lo swap long
   (circa -0,04 R ogni 5 giornate) basta ad azzerare la deriva: un filtro
   deve essere molto selettivo per pagare, e quelli di questa famiglia non lo
   sono.

Dettaglio in `D:\ricerca_macro\risultati\`: `a_mappa.parquet` (48 celle:
36 predittive + 12 contemporanee, con r, t NW, r non sovrapposto, anni),
`a_varianti.parquet` (una riga per variante: misure, anni, p),
`a_operazioni.parquet` (una riga per operazione e variante),
`a_sempre_long.parquet` (riferimento per tenuta).
