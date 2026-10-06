# Famiglia C — Posizionamento COT, grandi contro piccoli (scoperta 2009-2017)

Protocollo: `docs/macro-oro-registrazione.md`. Script:
`trading/scripts/macro_c_cot.py`. Dati: solo
`D:\ricerca_macro\scoperta\MACRO_D1.parquet` (oro, giornata 22->22 UTC) e
`D:\ricerca_macro\scoperta\COT_SETTIMANALE.parquet` (CFTC disaggregato, dal
06/2006; le settimane 2006-2008 servono solo per i percentili). Le M5 non
servono: lo stop si controlla su massimo e minimo D1 come in
`docs/studies/multi/f2-ritorno.md`.

## Varianti dichiarate PRIMA del calcolo (06/10/2026)

Regole fisse (non sono dimensioni di ricerca):
- misure per settimana di rapporto: netto % OI = (long - short) / open
  interest x 100 per managed money (MM), produttori/commerciali (PROD), non
  segnalati (PIC, proxy del retail); percentile del valore sulle 156
  settimane PRECEDENTI (min 52; pareggi a meta'); variazione settimanale del
  netto % e suo percentile (stessa finestra);
- data utilizzabile del COT (prudente) = la piu' tarda fra `pubblicato` del
  file, martedi' + 3 giorni lavorativi del calendario federale USA (festivi
  infrasettimanali -> lunedi') e venerdi' della settimana del rapporto.
  Rapporti 01/10/2013-12/11/2013 (chiusura del governo, pubblicati in
  ritardo: il file li da' come usciti il venerdi' solito) utilizzabili solo
  dal 22/11/2013. Ritardo medio aggiunto: 0,2 giorni per settimana;
- giornata di decisione s = prima giornata d'oro valida con data >= data
  utilizzabile; segnale alla chiusura di s, entrata all'apertura di s+1; se
  due rapporti cadono sulla stessa s vale l'ultimo. Decisioni 2009-2017: 459
  settimane (prima 30/01/2009, quando c'e' l'ATR20);
- tenuta H = 5, 10, 20 giornate valide (1, 2, 4 settimane; uscita alla
  chiusura di s+H, scartata se oltre i dati) oppure OPP = fino al primo
  rapporto col segnale opposto (uscita alla chiusura della sua giornata di
  decisione, rientro all'apertura dopo se il lato lo consente; a fine dati
  chiusura all'ultima giornata);
- una posizione per regola; segnali ignorati mentre e' aperta;
- 1R = 2 x ATR20(s) in tutte le varianti; stop (se c'e') a 2 x ATR20
  dall'entrata, uscita allo stop o all'apertura se la giornata apre oltre;
- costi 0,46 $ round trip, anche x1,5; swap long -0,715 x P/4156,98, short
  +0,325 x P/4156,98 $/oncia/notte; notti = giorni lun-ven dall'entrata
  all'uscita compresi, mercoledi' x3 (stessa convenzione di f2).

Segnali (12), direzione per settimana:
- (1) MM_CONTRA q (q = 0,1, 0,2): long se percentile MM <= q, short se >= 1-q;
- (2) MM_SEGUI q (q = 0,1, 0,2): il contrario (seguire gli estremi);
  MM_VAR_SEGUI: segno della variazione settimanale del netto MM;
  MM_VAR_ESTR 0,2: long se la variazione e' nel 20% piu' alto della storia,
  short nel 20% piu' basso;
- (3) PIC_CONTRA q (q = 0,1, 0,2): long se percentile PIC <= q, short se
  >= 1-q; PIC_VAR_CONTRA: contro il segno della variazione dei piccoli;
- (4) PROD_FORTI q (q = 0,1, 0,2): long se percentile PROD >= 1-q (produttori
  coperti meno del solito: netto meno corto), short se <= q; PROD_VAR_SEGUI:
  segno della variazione del netto PROD.

Gestione: lato entrambi / solo long / solo short (3; "solo long" = lo short
diventa flat) x tenuta 5, 10, 20, OPP (4) x senza / con stop (2).

**Varianti: 12 x 3 x 4 x 2 = 288**, tutte promuovibili. Riferimento (non
conteggiato): SEMPRE LONG ogni settimana, tenute 5/10/20, con e senza stop.

Misure per variante: n, operazioni al mese, netto medio R (x1, x1,5) e in $
per oncia, netto totale R, t sui rendimenti mensili (somma R per mese
d'uscita, mesi vuoti = 0, 02/2009-12/2017 = 107 mesi) e t sulle operazioni
(mai sovrapposte), anni positivi 2009-2017 per anno d'uscita, drawdown R.
Placebo, 1000 serie, seed 12345, statistica = netto totale R a x1,
p = (1 + #placebo >= reale)/1001: DIREZIONE (stesse operazioni, direzione
casuale, stop speculare) e DATE (per ogni operazione una settimana di
decisione casuale fra le 459, stessa direzione, stessa tenuta nominale e
gestione). Promozione: netto > 0 a x1 e x1,5, t mensile >= 3, anni >= 7/9,
p < 0,01 su entrambi i placebo; al massimo 3 candidati.

## Risultati (06/10/2026)

Controllo: motore vettoriale confrontato con un ciclo giornata per giornata
(prezzo d'uscita, stop, notti di swap, costo) su 400 operazioni casuali:
differenza massima 0. Tempo di calcolo 5 s.

**Varianti provate: 288. Promosse: 0.** Netto > 0 nel 30,2%; t mensile fra
-1,99 e +1,09 (5%-95%: -1,40 / +0,74, mediano -0,33): nessuna variante ha
|t| >= 2. Anni positivi >= 7 in 3 varianti (tutte PROD_FORTI 0,2 LS, t
-0,2/+0,5); p direzione < 0,01 in 1 (PROD_FORTI 0,1 S OPP stop, 9
operazioni, t 0,18); p date < 0,01 in nessuna.

| segnale | netto > 0 | t mediano | t massimo | t minimo | t mediano L / LS / S |
|---|---|---|---|---|---|
| MM_CONTRA 0,1 | 4% | -0,76 | 0,04 | -1,99 | -0,78 / -0,93 / -0,66 |
| MM_CONTRA 0,2 | 42% | -0,11 | 0,78 | -0,53 | 0,00 / -0,15 / -0,29 |
| MM_SEGUI 0,1 | 75% | 0,42 | 1,09 | -0,40 | 0,42 / 0,56 / 0,15 |
| MM_SEGUI 0,2 | 21% | -0,47 | 0,36 | -1,27 | -0,23 / -0,53 / -0,32 |
| MM_VAR_SEGUI | 54% | 0,05 | 0,84 | -1,19 | 0,05 / 0,25 / -0,29 |
| MM_VAR_ESTR 0,2 | 17% | -0,93 | 0,33 | -1,67 | -0,68 / -1,32 / -0,82 |
| PIC_CONTRA 0,1 | 21% | -0,62 | 0,78 | -1,69 | -1,31 / -0,92 / -0,01 |
| PIC_CONTRA 0,2 | 25% | -0,53 | 0,37 | -1,86 | -0,84 / -0,43 / 0,25 |
| PIC_VAR_CONTRA | 4% | -0,93 | 0,63 | -1,89 | -0,81 / -1,14 / -0,93 |
| PROD_FORTI 0,1 | 42% | -0,16 | 0,96 | -1,28 | -0,96 / 0,00 / 0,80 |
| PROD_FORTI 0,2 | 38% | -0,26 | 0,88 | -1,04 | -0,47 / -0,23 / 0,17 |
| PROD_VAR_SEGUI | 21% | -0,20 | 0,47 | -0,93 | -0,06 / -0,34 / -0,40 |

### La migliore per ipotesi e il riferimento

| variante | n | op/mese | netto R x1 / x1,5 | netto $/oz | tot R | t mese / op | anni + | DD R | p dir / date |
|---|---|---|---|---|---|---|---|---|---|
| MM_SEGUI 0,1, LS, H10, stop | 91 | 0,85 | 0,144 / 0,137 | 2,70 | 13,1 | 1,09 / 1,00 | 5 | 8,0 | 0,19 / 0,10 |
| PROD_FORTI 0,1, S, H20, stop | 35 | 0,33 | 0,214 / 0,207 | 8,82 | 7,5 | 0,96 / 0,97 | 3 | 3,1 | 0,09 / 0,11 |
| MM_VAR_SEGUI, LS, H20 | 110 | 1,03 | 0,132 / 0,126 | 3,66 | 14,5 | 0,84 / 0,87 | 5 | 9,5 | 0,11 / 0,10 |
| MM_CONTRA 0,2, L, OPP | 6 | 0,06 | 1,142 / 1,135 | -38,0 | 6,9 | 0,78 / 0,75 | 4 | 4,8 | 0,17 / 0,18 |
| PIC_CONTRA 0,1, S, H20 | 22 | 0,21 | 0,243 / 0,236 | 10,66 | 5,3 | 0,78 / 0,77 | 4 | 3,8 | 0,18 / 0,17 |
| MM_CONTRA 0,1, LS, H20 (l'ipotesi "attesa") | 50 | 0,47 | -0,153 | | -7,7 | -0,69 | 3 | | 0,66 / 0,65 |
| SEMPRE LONG H5 | 425 | 3,97 | -0,011 / -0,018 | | -4,7 | -0,28 / -0,30 | 4 | 29,9 | |
| SEMPRE LONG H10 / H20 | 217 / 110 | | -0,029 / -0,040 | | -6,2 / -4,4 | -0,33 / -0,27 | 4 / 4 | 33,2 / 29,7 | |
| SEMPRE LONG H20 stop | 141 | 1,32 | -0,019 | | -2,7 | -0,17 | 5 | 25,5 | |

(MM_CONTRA 0,2 L OPP: R positivo e $ negativi perche' 6 operazioni lunghe
mesi con ATR diversi; esempio di perche' le OPP con pochi casi non contano.)
Il "sempre long" 2009-2017 e' leggermente negativo: l'oro sale fino al 2011
e scende fino al 2015, e lo swap long (~ -0,04 R a settimana) mangia il resto.

### Che cosa fanno i piccoli rispetto ai fondi (descrittivo, 2006-2017)

| misura | MM | PIC | PROD |
|---|---|---|---|
| netto % OI medio (min / max) | +25,4 (-7,0 / +45,6) | +5,1 (-3,5 / +12,7) | -25,7 (-46,0 / +3,2) |
| deviazione della variazione settimanale (punti % OI) | 3,42 | 0,87 | 2,03 |
| correlazione della variazione con l'oro della stessa settimana (mar->mar) | +0,49 | +0,36 | -0,42 |

Correlazioni: livelli MM-PIC +0,70, MM-PROD -0,73; variazioni MM-PIC +0,32
(stesso segno nel 62% delle settimane), MM-PROD -0,74, PIC-PROD -0,49.
Ritardo: variazione PIC con quella MM della settimana prima +0,16; MM con PIC
della settimana prima +0,07. Estremi insieme: MM nel 20% alto 114 settimane,
PIC 115, entrambe 54; nel 20% basso MM 150, PIC 100, entrambe 83.

Lordo R di un long dopo il rapporto, per quintile del percentile (1 = piu'
corti del solito), 459 settimane, finestre sovrapposte (solo indicativo):

| quintile | MM 1 sett / 4 sett | PROD 1 / 4 | PIC 1 / 4 |
|---|---|---|---|
| 1 | +0,05 / +0,14 | -0,05 / -0,04 | -0,01 / +0,08 |
| 2 | +0,02 / +0,19 | +0,18 / +0,18 | +0,12 / +0,27 |
| 3 | +0,00 / +0,04 | +0,08 / +0,52 | -0,06 / -0,14 |
| 4 | +0,01 / +0,18 | +0,00 / +0,28 | +0,16 / +0,55 |
| 5 | +0,03 / +0,18 | -0,02 / -0,07 | -0,03 / +0,05 |

Nessuna monotonia: gli estremi (quintili 1 e 5) non si staccano dal centro.

### Candidati

**Nessuno.** Nessuna delle 288 varianti si avvicina ai criteri (t massimo
1,09 contro 3; p minimo sul placebo a date 0,097).

### Osservazioni

1. **Gli estremi del managed money non sono un segnale contrarian sull'oro
   2009-2017**: MM_CONTRA 0,1 ha netto > 0 solo nel 4% delle varianti
   (t mediano -0,76); il verso opposto (seguire gli estremi, MM_SEGUI 0,1) e'
   positivo nel 75% ma con t massimo 1,09. Previsione 2 del protocollo ("il
   COT e' la famiglia piu' probabile") smentita; se c'e' qualcosa, e' una
   debolissima prosecuzione, non un ritorno.
2. **I piccoli trader non fanno il contrario dei fondi: li seguono, in
   piccolo.** Netto medio +5% dell'OI contro +25% dei fondi, livelli
   correlati +0,70, variazioni nello stesso verso nel 62% delle settimane;
   entrambi comprano nelle settimane in cui l'oro sale (+0,36 i piccoli,
   +0,49 i fondi) e vendono quando scende: inseguono il prezzo della stessa
   settimana. La controparte vera dei fondi sono i produttori/swap
   (variazioni -0,74). Il ritardo dei piccoli sui fondi e' minimo (+0,16).
   Andare contro i piccoli non rende (PIC_CONTRA netto > 0 nel 21-25%,
   PIC_VAR_CONTRA nel 4%).
3. **Il COT descrive, non anticipa.** Le variazioni settimanali spiegano
   l'oro della stessa settimana (|correlazione| 0,36-0,49 per tutti e tre i
   gruppi) ma, pubblicate il venerdi' con tre giorni di ritardo, non danno
   direzione dopo: quintili senza ordine, t delle regole fra -2 e +1,1,
   distribuzione dei t piu' stretta di quella attesa per caso con 288 prove
   (la regola migliore non batte nemmeno il placebo a date, p 0,10). Le
   "mani forti" (PROD_FORTI) sono le uniche con 7 anni positivi su 9 in
   qualche variante, ma con netto ~0.

Avvertenze: (a) `prepara_macro.py` calcola `pubblicato` = martedi' + 3
giorni lavorativi senza festivi ne' chiusure del governo: per la scoperta lo
script corregge (festivi federali, 10/2013-11/2013), ma **per la verifica la
chiusura 22/12/2018-25/01/2019 ha ritardato i rapporti COT fino a marzo
2019**: chi usa il COT in verifica deve correggere quelle date o avra'
informazione futura. (b) Le varianti OPP con lati estremi hanno 5-30
operazioni lunghe mesi: numeri instabili, nessuna conta. (c) I placebo a
date usano tutte le 459 settimane: per le regole "solo long" coincidono con
il "sempre long" della stessa tenuta.

Dettaglio in `D:\ricerca_macro\risultati\`: `c_settimane.parquet` (una riga
per settimana di decisione: misure, percentili, data utilizzabile, segnali),
`c_varianti.parquet` (288 righe, tutte le misure, anni e p),
`c_operazioni.parquet` (una riga per operazione e variante, con l'esito nella
direzione opposta per il placebo), `c_sempre_long.parquet`,
`c_descrittive.parquet`, `c_quintili.parquet`.
