# Famiglia 2 — Ritorno alla media di qualche giorno (scoperta 2010-2017)

Protocollo: `docs/multigiorno-paniere-registrazione.md`. Script:
`trading/scripts/multi_f2_ritorno.py`. Dati: solo
`D:\ricerca_multi\scoperta\PANIERE_D1.parquet` (giornata 22->22 UTC, 12
mercati) e `D:\ricerca_multi\costi.csv`. Le M5 non servono: senza obiettivo
non c'e' ordine stop/obiettivo da risolvere e lo stop si controlla su massimo
e minimo D1 (la giornata intera e' dopo l'entrata, che avviene all'apertura).

## Varianti dichiarate PRIMA del calcolo (04/10/2026)

Regole fisse (non sono dimensioni di ricerca):
- si usano solo le giornate `valida = True`; ATR20 = media del true range
  delle 20 giornate valide fino a quella del segnale compresa; media 200 =
  media delle 200 chiusure valide fino al segnale compreso (causali);
- segnale sulla chiusura della giornata s, entrata all'apertura della
  giornata s+1, uscita alla chiusura della giornata s+H (H giornate tenute);
- entrate solo con data 2010-2017 per tutti i mercati (l'oro 2009 serve solo
  da riscaldamento, cosi' gli anni sono 8 per tutti); operazione scartata se
  l'uscita cade oltre la fine dei dati di scoperta;
- una sola posizione per regola e per mercato: i segnali arrivati mentre la
  posizione e' aperta si ignorano (nessuna piramide); nuova entrata possibile
  dall'apertura successiva all'uscita;
- 1R = 2 x ATR20 del giorno del segnale, in tutte le varianti (anche quelle
  senza stop): rischio uguale per operazione e per mercato;
- stop (quando c'e') a 2 x ATR20 dall'entrata; tocco se il minimo (long) o
  il massimo (short) della giornata lo raggiunge; uscita allo stop, o
  all'apertura se la giornata apre gia' oltre;
- costi round trip di `costi.csv` (oro 0,46 $ = 0,40 + 0,06 per gli anni
  pre-2020), anche x1,5; swap per notte = 3%/365 del prezzo d'entrata, a
  carico sia del long sia dello short (cambi, argento, indici); oro: long
  -0,715 x P/4156,98, short +0,325 x P/4156,98 $/oncia/notte; notti = giornate
  di calendario lun-ven dall'entrata all'uscita comprese (prudente: anche la
  tenuta di 1 giornata paga 1 notte), il mercoledi' vale 3;
- verso di una giornata = segno di chiusura meno chiusura precedente.

Segnali (12):
- SERIE N (N = 2, 3, 4): almeno N giornate consecutive in rialzo -> short;
  in ribasso -> long;
- MOSSA L,k (L = 1, 3, 5 giornate; k = 1, 1,5, 2): chiusura(s) -
  chiusura(s-L) >= k x ATR20(s) -> short; <= -k x ATR20(s) -> long.

Gestione: tenuta H = 1, 3, 5, 10 giornate (4) x uscita solo a tempo / a tempo
con stop 2 x ATR20 (2) x filtro di tendenza nessuno / media 200 (solo long
con chiusura sopra la media 200, solo short sotto) (2).

**Regole: 12 x 4 x 2 x 2 = 192.** Universi: 12 mercati + 3 gruppi (indici
SPX, NSX, DAX; metalli oro, argento; cambi 7 coppie) + paniere = 16.
**Varianti: 192 x 16 = 3072**, tutte promuovibili.

Misure per variante: n, operazioni al mese, netto medio e totale in R (x1 e
x1,5), t sui rendimenti mensili (somma in R delle operazioni per mese di
uscita, mesi senza operazioni = 0, dal primo mese con entrate possibili a
dicembre 2017) e, per riferimento, t sulle operazioni; anni positivi
2010-2017; swap medio in R e quota dello swap sul lordo; drawdown massimo in
R (somma cumulata in ordine di uscita). Placebo, 1000 serie, seed 12345,
statistica = netto totale in R a costi x1, p = (1 + #placebo >= reale)/1001:
- DIREZIONE: stesse operazioni (stesse entrate, tenute, stop speculare),
  direzione casuale;
- DATE: per ogni operazione una data d'entrata casuale (uniforme fra le
  entrate possibili dello stesso mercato nel 2010-2017), stessa direzione,
  stessa tenuta e stessa gestione; per gruppi e paniere si sommano le serie
  dei mercati. Controlla che il long "contro i ribassi" sugli indici non
  guadagni solo per il trend.

Promozione: netto > 0 a x1 e x1,5, t mensile >= 3, anni positivi >= 6 (su 8;
per gli indici, che partono a novembre 2010, >= 6 sugli anni con
operazioni), p < 0,01 su entrambi i placebo. Al massimo 3 candidati, in
ordine di t, non piu' di uno per universo.

## Risultati (04/10/2026)

Controlli: motore vettoriale confrontato con un ciclo giornata per giornata
su 400 operazioni casuali (prezzo d'uscita, stop, notti di swap, costo):
differenza massima 0. Segnali dei tre candidati ricontrollati uno per uno
sui prezzi (variazione su L giornate, ATR20, media 200): 0 errori. 370.012
operazioni (regola x mercato), tempo di calcolo 40 s.

**Varianti provate: 192 regole x 16 universi = 3072**, tutte valutate.
Netto > 0 nel 35,8%; t mensile >= 3 in 52, <= -3 in 38. **Tutti i criteri
insieme: 43**, tutte sugli indici e tutte con il filtro media 200
(SPXUSD 18, NSXUSD 13, gruppo indici 12; DAX da solo 0, cambi 0, metalli 0,
paniere 0). Segnali delle promosse: quasi solo MOSSA a 3-5 giornate
(41 su 43), tenuta 3-5 giornate (36 su 43).

| universo | netto > 0 senza / con m200 | t mediano senza / con | t massimo senza / con | passano |
|---|---|---|---|---|
| SPXUSD | 82% / 95% | 0,74 / 1,65 | 2,61 / 4,85 | 18 |
| NSXUSD | 72% / 98% | 0,71 / 2,07 | 2,84 / 3,99 | 13 |
| GRXEUR (DAX) | 23% / 67% | -0,75 / 0,48 | 1,27 / 2,48 | 0 |
| gruppo indici | 71% / 95% | 0,42 / 2,11 | 1,85 / 4,56 | 12 |
| gruppo cambi | 4% / 23% | -1,41 / -0,71 | 0,50 / 2,26 | 0 |
| gruppo metalli | 0% / 14% | -2,06 / -1,02 | -1,14 / 0,34 | 0 |
| paniere | 2% / 53% | -1,50 / 0,15 | 0,10 / 2,70 | 0 |

Cambi per coppia: t massimo 1,5-2,8 (USDJPY con m200), nessuna promossa.
Oro e argento: netto > 0 nel 5% e 0% delle varianti senza filtro.

### Vicinato sul gruppo indici, con filtro media 200 (t mensile)

| segnale | H1 | H3 | H3 stop | H5 | H5 stop | H10 |
|---|---|---|---|---|---|---|
| MOSSA 3g 1 ATR | 2,6 | 2,9 | 2,2 | 3,5 | 3,3 | 1,4 |
| MOSSA 3g 1,5 ATR | 2,7 | 3,5 | 3,3 | 3,4 | 2,9 | 2,1 |
| MOSSA 3g 2 ATR | 2,2 | 3,0 | 3,0 | 3,2 | 2,4 | 2,5 |
| MOSSA 5g 1 ATR | 2,9 | 2,9 | 2,9 | 3,5 | 3,0 | 1,5 |
| MOSSA 5g 1,5 ATR | 2,7 | 3,3 | 3,0 | 3,5 | 3,1 | 2,4 |
| MOSSA 5g 2 ATR | 2,2 | 4,6 | 4,5 | 4,1 | 2,9 | 2,3 |
| MOSSA 1g 1-2 ATR | 0,0-1,2 | 1,3-1,6 | 0,8-1,3 | 1,7-2,4 | 1,3-1,7 | 0,6-3,6 |
| SERIE 2 / 3 / 4 | 0,9 / 1,8 / 2,0 | -0,7 / 2,7 / 1,7 | | 0,4 / 3,1 / 2,1 | | |

Le celle MOSSA 3-5g con tenuta 3-5 SENZA filtro hanno t fra 0,4 e 1,7: il
filtro e' decisivo.

### Deriva (placebo a date casuali): netto medio in R di un long / short a caso, uscita a tempo

| mercato | long H1 | long H5 | long H10 | short H5 | short H10 |
|---|---|---|---|---|---|
| SPXUSD | 0,000 | +0,050 | +0,116 | -0,137 | -0,261 |
| NSXUSD | +0,001 | +0,073 | +0,166 | -0,153 | -0,295 |
| GRXEUR | 0,000 | +0,034 | +0,071 | -0,086 | -0,165 |
| cambi (intervallo) | -0,019/-0,008 | -0,067/-0,005 | -0,135/+0,006 | -0,088/-0,014 | -0,173/-0,029 |

### Candidati (in ordine di t, uno per universo)

Specifica comune: giornate 22:00->22:00 UTC, solo giornate valide; ATR20 =
media del true range delle 20 giornate valide fino a s compresa; media 200 =
media delle ultime 200 chiusure fino a s compresa; segnale alla chiusura della
giornata s; entrata a mercato all'apertura della giornata s+1; uscita a
mercato alla chiusura della giornata s+H; 1R = 2 x ATR20(s); una sola
posizione per mercato, segnali ignorati mentre e' aperta.

- **C1 — SPXUSD, MOSSA 5g 1,5 ATR, H5, stop, m200**: long se
  chiusura(s) - chiusura(s-5) <= -1,5 x ATR20(s) e chiusura(s) > media200(s);
  short se chiusura(s) - chiusura(s-5) >= +1,5 x ATR20(s) e chiusura(s) <
  media200(s). Stop a 2 x ATR20(s) dall'entrata (all'apertura se la giornata
  apre oltre), altrimenti uscita alla chiusura della 5a giornata.
- **C2 — gruppo indici (SPXUSD, NSXUSD, GRXEUR, 1R ciascuno), MOSSA 5g 2 ATR,
  H3, solo tempo, m200**: come C1 con soglia 2 x ATR20, nessuno stop, uscita
  alla chiusura della 3a giornata.
- **C3 — NSXUSD, MOSSA 3g 1,5 ATR, H3, stop, m200**: come C1 con variazione
  su 3 giornate (chiusura(s) - chiusura(s-3)), soglia 1,5 x ATR20, stop
  2 x ATR20, uscita alla chiusura della 3a giornata.

| | C1 SPX | C2 indici | C3 NSX |
|---|---|---|---|
| n / op al mese | 65 / 0,77 | 156 / 1,84 | 71 / 0,84 |
| long | 83% | 82% | 92% |
| netto medio R (x1 / x1,5) | 0,396 / 0,389 | 0,237 / 0,231 | 0,289 / 0,281 |
| lordo medio R | 0,437 | 0,262 | 0,319 |
| netto totale R | 25,7 | 37,0 | 20,5 |
| t mensile / t operazioni | 4,85 / 4,45 | 4,56 / 4,74 | 3,99 / 3,66 |
| anni positivi | 7 su 7 | 7 su 7 | 6 su 7 |
| swap medio R / quota sul lordo | -0,027 / 6% | -0,013 / 5% | -0,014 / 4% |
| stop presi | 5% | - | 6% |
| drawdown R | 1,6 | 3,1 | 1,9 |
| p direzione / date / date nello stato del filtro | 0,001 / 0,001 / 0,001 | 0,001 / 0,001 / 0,001 | 0,001 / 0,001 / 0,001 |
| netto medio R del placebo a date casuali | -0,001 | +0,010 | +0,023 |

Anni (netto R): C1 2011 +1,4, 2012 +4,2, 2013 +5,5, 2014 +4,1, 2015 +3,3,
2016 +4,0, 2017 +3,2. C2 2011 +1,5, 2012 +6,5, 2013 +8,5, 2014 +4,7,
2015 +6,2, 2016 +4,6, 2017 +5,0 (per mercato: SPX +0,31 R su 50, NSX +0,26
su 47, DAX +0,16 su 59). C3 2011 -0,2, poi +2,2/+4,8 ogni anno. Il 2010 non ha
operazioni (la media 200 si forma solo nel 2011: gli anni sono 7). Lato
short quasi nullo: C1 +0,09 R su 11, C2 +0,05 su 28, C3 0,00 su 6.
Correlazione mensile: C1-C2 0,26, C2-C3 0,45, C1-C3 0,10.

### Osservazioni

1. **Il ritorno alla media di qualche giorno esiste solo sugli indici
   americani, e solo comprando i ribassi dentro una tendenza rialzista**
   (filtro media 200): previsione 2 del protocollo confermata (indici si',
   cambi no). Le celle promosse stanno su un altopiano (MOSSA su 3-5
   giornate, tenuta 3-5, t 2,9-4,6 sul gruppo), non su un picco isolato; senza
   filtro le stesse celle hanno t <= 1,7. Il DAX va nello stesso verso ma
   piu' debole (t massimo 2,5).
2. **Non e' il trend a pagare.** Un long a caso tenuto 5 giorni sull'S&P
   rende +0,05 R, sul Nasdaq +0,07; i candidati rendono +0,24/+0,40 R per
   operazione e battono anche il placebo piu' severo (date casuali scelte solo
   fra le giornate sopra la media 200, p 0,001). Costi e swap pesano poco con
   1R = 2 x ATR20 (costo ~0,015 R, swap 4-6% del lordo), per questo x1,5 non
   cambia nulla. Il limite e' la frequenza: 0,8-1,8 operazioni al mese, 65-156
   operazioni in sette anni, tutte in un mercato rialzista (2011-2017).
3. **Cambi e metalli non ritornano.** Cambi: netto > 0 solo nel 4% delle
   varianti di gruppo senza filtro; il meglio (MOSSA 3g 1,5 ATR, H1, m200,
   7,5 op/mese) fa +0,03 R con t 2,3. Metalli: prosecuzione, non ritorno —
   la peggiore (MOSSA 5g 1 ATR, H1) fa -0,04 R netto con t -3,7 e 0 anni
   positivi su 8; argento negativo in tutte le varianti senza filtro. Il
   paniere intero quindi diluisce l'effetto (t massimo 2,7) e non promuove
   nulla: per questa famiglia il paniere non serve, servono gli indici.

Avvertenze per la verifica: i tre candidati sono LO STESSO fenomeno (C2
contiene C1 e C3 come mercati), scelti come i migliori di 3072 varianti; il
t del migliore di un altopiano e' gonfiato, il valore atteso e' piu' vicino
a quello mediano dell'altopiano (t ~3). Soglia di verifica con 3 candidati:
t >= 2,4. Nel 2018 -> fine dati il DAX finisce il 14/06/2020. L'entrata alle
22:00 UTC sugli indici avviene nell'ora piu' sottile della sessione futures:
il costo 0,55 / 1,50 del protocollo potrebbe essere ottimista proprio li'
(ma il margine sul costo e' ampio: con costo x5 il netto resta +0,34 / +0,19 /
+0,22 R per C1 / C2 / C3).

Dettaglio in `D:\ricerca_multi\risultati\`: `f2_operazioni.parquet` (una
riga per operazione, regola e mercato, con l'esito nella direzione opposta
per il placebo), `f2_varianti.parquet` (una riga per regola e universo, con
tutte le misure e i p), `f2_deriva.parquet` (netto medio di long e short a
date casuali per mercato, tenuta e stop).
