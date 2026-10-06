# Famiglia D — Flussi istituzionali dell'ETF GLD sull'oro (scoperta 2009-2017)

Protocollo: `docs/macro-oro-registrazione.md`. Script:
`trading/scripts/macro_d_gld.py`. Dati: solo
`D:\ricerca_macro\scoperta\MACRO_D1.parquet` (giornata dell'oro 22->22 UTC;
`gld_tonnellate` della riga D = tonnellate pubblicate per il giorno USA
precedente, gia' sfasate da `prepara_macro.py`). Prima di dichiarare la
griglia ho guardato solo copertura e frequenza della serie: nessun valore
mancante sulle giornate valide, tonnellate invariate nel 52% delle giornate
(nessuna creazione/rimborso, o festivo USA), |variazione giornaliera| p90
6,1 t, p99 18,4 t; 1134 t a fine 2009, massimo 1351 t a fine 2012, 644 t a
fine 2015.

## Varianti dichiarate PRIMA del calcolo (06/10/2026)

Regole fisse (non sono dimensioni di ricerca):
- solo giornate `valida = True`; T(s) = `gld_tonnellate` della riga s;
  flusso F_L(s) = T(s) - T(s-L) in tonnellate e F%_L(s) = F_L(s) / T(s-L) x
  100, L = 1, 5, 20 giornate valide; percentile p "sui 252 giorni precedenti"
  = quantile p dei 252 valori delle giornate s-252..s-1 (s escluso, almeno
  200 presenti); rango percentile = quota dei 252 precedenti < valore (pareggi
  a meta');
- ATR20 = media del true range delle 20 giornate valide fino a s; 1R = 2 x
  ATR20(s) in tutte le varianti; segnale alla chiusura di s, finestra (a, b):
  entrata all'apertura di s+a, uscita alla chiusura di s+b; stop (se c'e') a
  2 x ATR20(s) dall'entrata, uscita allo stop o all'apertura se la giornata
  apre gia' oltre;
- eventi = **inizio** della condizione (vera in s, falsa in s-1); una
  posizione per regola, segnali ignorati mentre e' aperta; operazione
  scartata se l'uscita cade oltre i dati (29/12/2017);
- costi 0,46 $ round trip (x1 e x1,5); swap long -0,715, short +0,325
  $/oncia/notte x close/4156,98, notti = giorni lun-ven dall'entrata
  all'uscita compresi, mercoledi' x3 (motore identico a `macro_b_paura.py`).

**D1 — mappa descrittiva (non promuovibile).** Segnale X in 3 misure (F_L in
tonnellate, F%_L, rango percentile di F%_L) x L = 1, 5, 20 contro il
rendimento successivo apertura(s+1) -> chiusura(s+H) in R, H = 1, 5, 20: 27
celle; per ciascuna correlazione di Spearman, pendenza OLS su X
standardizzato con t HAC (Bartlett, ritardo H + L), media in R per quintile
di X e Q5 - Q1. Relazione contemporanea e inversa (i flussi seguono il
prezzo?): correlazione di F%_L(s) con il rendimento dell'oro sulla stessa
finestra del dato (chiusura s-L-1 -> chiusura s-1), con le L giornate prima
di quella (prezzo -> flussi futuri) e profilo dei ritardi di F_1(s) con il
rendimento giornaliero di s-k, k = -5..10.

**D2 — flussi estremi (192 regole).** Eventi (12): L = 1, 5, 20 (3) x
{entrate F%_L > p90, > p95, uscite F%_L < p10, < p5} (4). Direzione (2):
prosegue (entrate -> long, uscite -> short) / rientra (opposto). Finestre
(1,1) (1,5) (1,10) (1,20) (4). Stop no/si' (2). 12 x 2 x 4 x 2 = **192**.

**D3 — divergenza flussi/prezzo (144 regole).** L = 5, 20 (2). Intensita'
(2): segno (rendimento close(s)/close(s-L) - 1 > 0 con F%_L < 0, o < 0 con
F%_L > 0; flusso nullo escluso) / forte (rendimento > p67 dei propri 252
precedenti con F%_L < p33, o rendimento < p33 con F%_L > p67). Tipo (3):
prezzo su e uscite / prezzo giu' e entrate / entrambe. Direzione (2): segue i
flussi / segue il prezzo. Finestre (1,5) (1,10) (1,20) (3). Stop no/si' (2).
2 x 2 x 3 x 2 x 3 x 2 = **144**.

**D4 — segno dei flussi come regola continua (72 regole).** L = 1, 5, 20 (3).
Modo (4): segue (long se F%_L > 0, short se < 0), contro (opposto), long solo
con entrate, long solo con uscite (nessuna posizione se F%_L = 0). Tenuta H =
1, 5, 20 (finestra (1, H), si rientra alla prima giornata libera) (3). Stop
no/si' (2). 3 x 4 x 3 x 2 = **72**.

**Totale: 192 + 144 + 72 = 408 varianti** promuovibili (+ 27 celle
descrittive della mappa).

Misure per regola: n, operazioni al mese, episodi (segnali a piu' di 20
giornate dal precedente aprono un episodio nuovo), netto medio e totale in R
(x1 e x1,5, con swap) e in $/oncia, t sui rendimenti mensili (somma per mese
d'uscita, mesi vuoti = 0, dal primo mese in cui la regola puo' segnalare) e
t sulle operazioni (non sovrapposte per costruzione) e sugli episodi, anni
positivi su 9 (2009-2017; anno senza operazioni = non positivo), drawdown in
R, "sempre long" (netto medio di un long a ogni giornata ammessa con la
stessa finestra e gestione). Placebo, 1000 serie, seed 12345, statistica =
netto totale R a x1, p = (1 + #placebo >= reale)/1001: DIREZIONE (stesse
entrate, direzione casuale, stop speculare); DATE NEL REGIME (stessa
direzione e gestione, per ogni operazione una data casuale fra le giornate
ammesse con lo stesso segno del movimento di prezzo a 20 giornate: controlla
che il flusso aggiunga qualcosa al momentum del prezzo, visto che i flussi
seguono il prezzo); DATE QUALSIASI (riferimento).

Promozione: netto > 0 a x1 e x1,5; t mensile >= 3; anni positivi >= 7 su 9;
p direzione < 0,01 e, per le regole a direzione fissa (tutte le D2, D3 con
tipo singolo, D4 "long solo"), anche p date nel regime < 0,01. Al massimo 3
candidati in ordine di t mensile.

## Risultati (06/10/2026)

Controlli: motore confrontato con un ciclo giornata per giornata su 400
entrate casuali (finestra, stop, direzione, notti di swap, costo): differenza
massima 9e-16. Percentili definiti da fine 2009 / inizio 2010 (252 giornate
precedenti, minimo 200). Calcolo completo 8 s.

**Varianti provate: 408, tutte valutate. Promosse: 0. Nessun candidato.**
t mensile massimo 2,53 (nessuna variante con t >= 3; 6 con t >= 2, 23 con
t <= -2, quasi tutte regole con molte operazioni che pagano costo e swap
pieni); p direzione < 0,01 in 3 varianti su 408 (attese ~4 per caso); anni
positivi >= 7 in 8 varianti.

| famiglia | varianti | netto > 0 | t mediano | t min / max | t >= 2 | p dir < 0,01 | passano |
|---|---|---|---|---|---|---|---|
| D2 flussi estremi | 192 | 41% | -0,24 | -2,31 / 1,77 | 0 | 0 | 0 |
| D3 divergenza flussi/prezzo | 144 | 44% | -0,24 | -3,16 / 2,53 | 6 | 3 | 0 |
| D4 segno dei flussi | 72 | 17% | -0,91 | -3,34 / 1,47 | 0 | 0 | 0 |

### D1 — Mappa: i flussi seguono il prezzo, non lo anticipano

Relazione contemporanea e inversa (F%_L(s) contro il rendimento dell'oro;
Spearman, t HAC; ~2.120 giornate 2010-2017):

| L | stessa finestra del dato (s-L-1 -> s-1) | finestra precedente (prezzo -> flussi) | finestra fino a s |
|---|---|---|---|
| 1 | 0,150 (t 6,2) | 0,088 (t 4,7) | 0,003 (t 1,7) |
| 5 | 0,249 (t 6,3) | 0,239 (t 5,3) | 0,190 (t 4,9) |
| 20 | 0,427 (t 5,2) | 0,411 (t 4,2) | 0,389 (t 4,9) |

Profilo dei ritardi di F%_1(s) con il rendimento giornaliero r(s-k): k = 1
(giorno USA del dato) 0,150; k = 2 0,088; k = 3..10 fra 0,04 e 0,06 (tutti
positivi); k = 0 (la giornata della decisione) 0,003; k = -1..-5 (futuro)
fra -0,03 e +0,03. Le entrate arrivano lo stesso giorno del rialzo e
continuano per 1-2 settimane dopo: i flussi sono una media mobile ritardata
del prezzo.

Flusso -> rendimento successivo (apertura s+1 -> chiusura s+H, in R; 27
celle): Spearman fra -0,038 e +0,030, |t HAC| <= 1,56 in tutte le misure
(massimo: tonnellate 0,90, % 0,70, rango 1,56).

| F%_L | Spearman H=1 / 5 / 20 | t HAC H=1 / 5 / 20 | Q5 - Q1 in R, H=1 / 5 / 20 |
|---|---|---|---|
| L=1 | 0,030 / 0,000 / -0,020 | 0,70 / 0,37 / 0,34 | +0,036 / +0,048 / +0,036 |
| L=5 | -0,011 / -0,007 / -0,035 | 0,56 / 0,55 / 0,17 | -0,008 / +0,028 / +0,080 |
| L=20 | -0,007 / -0,019 / -0,030 | 0,50 / 0,16 / 0,38 | +0,013 / +0,020 / +0,224 |

I quintili non sono monotoni (es. L=20, H=20: +0,03 / -0,01 / +0,06 / +0,04 /
+0,26 R): l'unico scarto visibile, Q5 dopo 20 giornate di forti entrate, ha
t HAC 0,38 perche' poggia su pochi episodi sovrapposti. Per L=1 i quintili
centrali sono in gran parte giornate a flusso zero (52% delle giornate).

### D2 — Flussi estremi (t mensile mediano sulle 4 finestre x 2 stop)

| evento (eventi / episodi max) | prosegue | rientra |
|---|---|---|
| F1 > p90 (165 / 57) | -0,17 | -0,64 |
| F1 > p95 (101 / 36) | -0,31 | -0,51 |
| F1 < p10 (188 / 65) | 0,22 | -1,03 |
| F1 < p5 (101 / 46) | -0,73 | -0,02 |
| F5 > p90 (52 / 32) | 0,10 | -0,50 |
| F5 > p95 (39 / 23) | 1,08 | -1,21 |
| F5 < p10 (60 / 35) | -0,35 | 0,03 |
| F5 < p5 (40 / 23) | 0,23 | -0,48 |
| F20 > p90 (20 / 15) | 0,73 | -0,98 |
| F20 > p95 (20 / 13) | -0,57 | 1,00 |
| F20 < p10 (26 / 20) | -0,12 | 0,04 |
| F20 < p5 (19 / 12) | 0,13 | -0,57 |

Netto medio mediano per finestra (1,1) / (1,5) / (1,10) / (1,20): prosegue
-0,012 / -0,018 / +0,011 / +0,031 R; rientra -0,011 / -0,027 / -0,101 /
-0,073 R. Il rientro e' un po' peggio del proseguimento (coerente con "i
flussi seguono il prezzo" + momentum), ma nessuna regola ha t >= 1,8.

### D3 — Divergenza (t mensile mediano sulle 3 finestre x 2 stop; tra parentesi netto medio mediano R)

| divergenza (eventi / episodi) | segue i flussi | segue il prezzo |
|---|---|---|
| L5 segno, prezzo giu' + entrate (114 / 56) | -2,34 (-0,219) | **1,58 (+0,173)** |
| L5 forte, prezzo giu' + entrate (68 / 38) | -1,74 (-0,182) | 1,49 (+0,172) |
| L5 segno, prezzo su + uscite (168 / 66) | -0,17 (-0,031) | 0,00 (+0,017) |
| L5 forte, prezzo su + uscite (81 / 42) | -1,23 (-0,161) | 0,71 (+0,093) |
| L5 forte, entrambe (149 / 60) | -1,93 (-0,174) | 1,54 (+0,130) |
| L20 segno, prezzo giu' + entrate (53 / 35) | -1,03 (-0,160) | 0,47 (+0,065) |
| L20 segno, prezzo su + uscite (95 / 47) | 1,26 (+0,094) | -1,41 (-0,109) |
| L20 forte, prezzo giu' + entrate (32 / 16) | -1,25 (-0,117) | 0,65 (+0,088) |
| L20 forte, prezzo su + uscite (42 / 24) | 0,35 (+0,042) | -0,82 (-0,128) |

A 5 giornate vince il prezzo (momentum); a 20 giornate, per "prezzo su +
uscite", vincono le uscite: segni incoerenti, non un meccanismo stabile.

### D4 — Segno dei flussi come regola continua (netto medio R senza stop; t mensile mediano)

| regola | tenuta 1 | tenuta 5 | tenuta 20 |
|---|---|---|---|
| F1 segue (L/S) | +0,004 (0,46) | +0,004 (0,24) | +0,031 (-0,10) |
| F1 long con entrate / con uscite | -0,011 / -0,044 | -0,044 / -0,124 | -0,178 / -0,183 |
| F5 segue (L/S) | -0,011 (-1,51) | -0,024 (-0,70) | -0,063 (-0,27) |
| F20 segue (L/S) | -0,015 (-1,87) | +0,023 (0,33) | +0,068 (0,81) |
| F20 long con entrate / con uscite | -0,021 / -0,019 | -0,052 / -0,032 | -0,139 / -0,039 |
| sempre long, stesse finestre (2010-2017) | -0,020 | -0,041 | -0,114 |

Nessun regime di flusso rende positivo il long (swap -0,02/-0,11 R per
operazione e oro in calo 2011-2015); "long con entrate" non batte il
"sempre long". Il peggiore della famiglia (F1 contro, tenuta 1, t -3,3) e'
solo costo pieno su 1.053 operazioni: lo specchio "segue" e' +0,004 R.

Le migliori 3 varianti (nessuna promossa):

| regola | n / episodi | op/mese | netto R x1 / x1,5 | $/op | t mens / episodi | anni + | DD R | p dir / regime / date |
|---|---|---|---|---|---|---|---|---|
| D3 L5 segno, prezzo giu' + entrate -> short, (1,5), senza stop | 104 / 42 | 1,05 | 0,191 / 0,184 | +7,1 | 2,53 / 3,13 | 8 | 3,7 | 0,003 / 0,011 / 0,005 |
| D3 L5 forte, prezzo giu' + entrate -> short, (1,10), stop | 50 / 36 | 0,51 | 0,305 / 0,299 | +13,6 | 2,30 / 2,43 | 6 | 4,8 | 0,015 / 0,014 / 0,021 |
| D3 L20 segno, prezzo giu' + entrate -> short, (1,5), senza stop | 47 / 34 | 0,48 | 0,193 / 0,187 | +7,4 | 2,15 / 2,22 | 7 | 1,8 | 0,014 / 0,040 / 0,047 |

La prima manca la promozione su t mensile (2,53 < 3) e p regime (0,011 >=
0,01); anni 2009-2017 in R: +1,8 -1,1 +4,4 +1,2 +3,2 +1,6 +4,0 +0,3 +4,4.

### Osservazioni

1. **I flussi del GLD sono un'eco del prezzo.** Correlazione col rendimento
   dello stesso periodo 0,15 (1 giorno), 0,25 (5), 0,43 (20), e il prezzo
   delle settimane precedenti anticipa i flussi (0,09 / 0,24 / 0,41; ritardi
   da 2 a 10 giorni tutti positivi). Nessuna misura di flusso anticipa
   l'oro: 27 celle con |Spearman| <= 0,038 e |t HAC| <= 1,56. Il dato arriva
   gia' sfasato di un giorno e contiene solo prezzo passato.
2. **Gli estremi di flusso non sono ne' capitolazione ne' segnale.** Dopo
   entrate o uscite oltre il p90/p95 (1, 5, 20 giorni) il proseguimento e'
   piatto (netto mediano -0,02/+0,03 R) e il rientro leggermente negativo;
   nessuna delle 192 regole D2 ha t >= 1,8 o p direzione < 0,01.
3. **L'unica traccia e' "prezzo in calo con entrate nell'ETF -> l'oro
   continua a scendere"** (short a 5 giornate, +0,19 R e +7 $/operazione,
   8 anni positivi su 9, p direzione 0,003; lo specchio "segue i flussi" ha
   t -3,2). Ma t mensile 2,5 < 3, p regime 0,011, e l'effetto sparisce o si
   inverte su "prezzo su + uscite" e a 20 giornate: e' momentum di prezzo a
   breve, gia' esplorato e respinto nelle ricerche sul solo prezzo, non
   un'informazione propria dei flussi. Previsione per la famiglia D: nessun
   candidato verso la verifica 2018-2026.

Dettaglio in `D:\ricerca_macro\risultati\`: `d_varianti.parquet` (una riga
per regola con misure, anni, p), `d_operazioni.parquet` (una riga per
operazione e regola, con l'esito nella direzione opposta), `d_mappa.parquet`
e `d_quintili.parquet` (flussi -> rendimento successivo),
`d_contemporanea.parquet` (stesso periodo, prezzo -> flussi, ritardi),
`d_sempre_long.parquet` (netto medio di un long a ogni giornata per finestra
e stop, 2010-2017).
