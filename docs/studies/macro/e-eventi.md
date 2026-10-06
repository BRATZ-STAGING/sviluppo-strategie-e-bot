# Famiglia E — Eventi macro (FOMC, verbali, CPI, NFP) sull'oro (scoperta 2009-2017)

Protocollo: `docs/macro-oro-registrazione.md`. Script:
`trading/scripts/macro_e_calendario.py` (calendario),
`trading/scripts/macro_e_eventi.py` (studio). Dati: solo
`D:\ricerca_zero\scoperta\XAUUSD_M5.parquet` (M5 BID, indice UTC
all'apertura) e `D:\ricerca_macro\scoperta\MACRO_D1.parquet` (giornata
dell'oro che chiude alle 17:00 New York). Si usano solo data e ora degli
eventi (note in anticipo), mai il valore del dato.

## Varianti dichiarate PRIMA del calcolo (06/10/2026)

Regole fisse (non sono dimensioni di ricerca):
- T = istante dell'annuncio in UTC (dal calendario, ora legale americana
  inclusa). Prezzo all'istante t = chiusura dell'ultima M5 terminata entro t
  (P(T) = chiusura della barra T-5m -> T, quindi prima dell'annuncio).
  Evento scartato se mancano barre vere nei 30 minuti prima di T o nella
  barra di T (mercato chiuso, es. Venerdi' Santo) o all'istante d'entrata;
- eventi: solo quelli annunciati in anticipo (FOMC straordinari esclusi);
- ATR20 = media del true range delle 20 giornate valide D1 chiuse prima
  dell'entrata. Regole intraday: **1R = 0,5 x ATR20**, stop (quando c'e') a
  0,5 x ATR20 dall'entrata sulle M5 (lo stop prevale; uscita allo stop o
  all'apertura se la barra apre oltre). Regole di piu' giorni: 1R = 2 x ATR20
  della giornata dell'evento, stop a 2 x ATR20 (motore della famiglia B);
- costi 0,46 $ round trip (x1 e x1,5) + **extra annuncio**: ogni entrata o
  uscita che cade in [T-5m, T+5m] paga 2 x 0,46 $ in piu' (spread x3 su
  quella gamba), anch'esso x1,5 nello scenario x1,5;
- swap FP -0,715 (long) / +0,325 (short) $/oncia/notte x close/4156,98, solo
  se la posizione attraversa le 21:00 UTC di un giorno lun-ven, x3 il
  mercoledi'; regole di piu' giorni come la famiglia B;
- una regola fa al massimo un'operazione per evento: **8 (FOMC, verbali) o
  12 (CPI, NFP) operazioni l'anno**, ~70-108 in nove anni.

**E1 — deriva pre-annuncio (48 regole).** Entrata a T-24h / T-4h / T-1h (3),
uscita a T-10m (prima dell'annuncio, senza extra). Direzione long / short (2).
Stop no / si' (2). Eventi FOMC, VERBALI, CPI, NFP (4). 4 x 3 x 2 x 2 = **48**.

**E2 — primo movimento post-annuncio (288 regole).** Primo movimento
m = P(T+d) - P(T) con d = 5 / 15 / 30 minuti (3); entrata a T+d (a T+5m paga
l'extra) nel verso di m (segue) o contro (rientro) (2); filtro: nessuno /
|m| >= 0,15 x ATR20 (2); uscita a T+1h / T+4h / 20:55 UTC dello stesso
giorno (3); stop no / si' (2); 4 eventi. 4 x 3 x 2 x 2 x 3 x 2 = **288**.

**E3 — giorni dopo l'evento (128 regole).** Giornata dell'evento s (quella
che contiene T); entrata all'apertura di s+a, uscita alla chiusura di s+b,
finestre (1,1) (1,3) (1,5) (1,10) (4); direzione long, short, segue (segno di
close(s) - close(s-1)), rientro (4); stop no / 2 x ATR20 (2); 4 eventi.
4 x 4 x 4 x 2 = **128**.

**Totale: 48 + 288 + 128 = 464 varianti**, tutte promuovibili.

Misure per regola: n, netto medio in R e in $/oncia a x1 e x1,5, t sulle
operazioni (eventi indipendenti, non sovrapposte), anni positivi su 9,
drawdown in R. Placebo, 1000 serie, seed 12345, statistica = netto totale R
a x1, p = (1 + #placebo >= reale)/1001: **ORA** (ogni evento sostituito da
un giorno senza eventi, stesso giorno della settimana entro +-8 settimane,
stessa ora UTC, stessa regola) e **DIREZIONE** (stessi eventi, direzione
casuale). Promozione: netto > 0 a x1 e x1,5, t >= 3, anni positivi >= 7/9,
p ORA < 0,01 e p DIREZIONE < 0,01; massimo 3 candidati in ordine di t.

Descrittiva (non promuovibile): per ogni tipo d'evento, rendimento e
volatilita' dell'oro su [T-24h, T], [T-4h, T], [T-1h, T], [T, T+5m],
[T, T+1h], [T, T+4h], [T, T+1 giorno lavorativo], [T, T+5 giorni lavorativi]
(stessa ora), contro i giorni di controllo (stessa definizione del placebo
ORA): media con segno (punti base, t), |rendimento| medio evento / controllo.
Controllo dell'ora dei comunicati FOMC 2009-2012 sulle M5 (12:30 / 14:00 /
14:15 New York).

## Calendario (passo 0, 06/10/2026)

`D:\ricerca_macro\dati\eventi\calendario_2009_2026.csv` (724 righe; colonne
tipo, data e ora New York, istante NY e UTC, riferimento, straordinaria,
annunciata_prima, stimata, conferenza, nota) e `calendario_anomalie.csv`.
Pagine in cache in `D:\ricerca_macro\dati\eventi\cache\` (rilancio senza rete).

| tipo | per anno 2009-2026 | eccezioni |
|---|---|---|
| FOMC (comunicato) | 8 | 2020: 7 (17-18 marzo cancellata) |
| verbali | 8 | 2025: 9 (verbali di dicembre usciti il 30/12/2025) |
| CPI | 12 | 2025: 11 (ottobre 2025 mai pubblicato) |
| NFP | 12 | 2025: 11 (ottobre e novembre 2025 insieme il 16/12) |

- **FOMC straordinari** con comunicato, esclusi e segnalati (nessuno
  annunciato in anticipo): 3/3/2020 e 15/3/2020 (unscheduled), notation vote
  23/3, 31/3, 27/8/2020 e 22/8/2025.
- **Ora del comunicato FOMC**: 14:15 NY 2009-2012, **12:30 NY** nelle 8
  riunioni con conferenza stampa apr. 2011 - dic. 2012, 14:00 NY dal 2013. Le
  pagine Fed pre-2013 non riportano l'ora: controllata sulle M5 (|rendimento|
  a 5 minuti evento/controllo: riunioni "12:30" -> 5,1 alle 12:30 e 1,9 alle
  14:15; riunioni "14:15" -> 4,2 alle 14:15 e 0,7 alle 12:30). Il protocollo
  diceva "14:00": nel 2009-2012 sarebbe stato sbagliato.
- **Verbali** alle 14:00 NY; i verbali delle riunioni straordinarie di marzo
  2020 escono l'8/4 con gli altri. Date future 2026 stimate a +21 giorni
  (colonna `stimata`).
- **CPI e NFP**: tutte alle 08:30 NY, data e ora lette sulla riga "embargoed
  until 8:30 a.m." di ogni release (446 pagine; 1 dal nome del file, CPI
  16/6/2016, pagina vuota; 2 dal calendario BLS futuro). Nome del file e
  data d'embargo coincidono sempre.
- **Chiusure del governo**: ottobre 2013 -> NFP 22/10 (martedi') e 8/11, CPI
  30/10 e 20/11 (spostati, annotati in `nota`); 2018-19 **nessun effetto**
  (BLS finanziato: date regolari, 12/12); ottobre-novembre 2025 -> CPI di
  ottobre mai pubblicato, CPI di settembre il 24/10, NFP di settembre il
  20/11, ottobre+novembre il 16/12.
- NFP di giovedi' per il 4 luglio (2009, 2014, 2015, 2020, 2025, 2026):
  normali. NFP del Venerdi' Santo 3/4/2015 e CPI 14/4/2017 a mercato
  dell'oro chiuso: scartati nello studio.

## Risultati (06/10/2026)

Eventi validi in scoperta: FOMC 72, verbali 72, CPI 107, NFP 107; giorni di
controllo per evento: mediana 12. Motore intraday confrontato con un ciclo
barra per barra su 300 operazioni casuali: differenza massima 4e-16.
Calcolo completo 4 s.

**Varianti provate: 464, tutte valutate. Promosse: 2** (la stessa idea con
due istanti di decisione).

### Descrittiva: oro attorno agli eventi

Rendimento medio con segno in punti base (t sugli eventi):

| evento | -24h | -4h | -1h | +5m | +1h | +4h | +1 giorno | +5 giorni |
|---|---|---|---|---|---|---|---|---|
| FOMC | +2,6 (0,3) | +1,2 (0,3) | +2,7 (1,1) | +4,5 (0,9) | +23,1 (1,9) | +29,9 (1,4) | -19,3 (-0,8) | -16,9 (-0,5) |
| verbali | +6,3 (0,5) | +3,8 (0,6) | +1,4 (0,5) | -1,6 | -1,4 | -3,6 | +24,4 (1,7) | +16,4 (0,6) |
| CPI | +6,7 (0,7) | +1,2 | -4,1 (-1,7) | -0,9 | -1,3 | -2,8 | -3,8 | -9,4 |
| NFP | **-19,1 (-2,0)** | **-8,4 (-3,0)** | -4,8 (-2,3) | +9,7 (1,7) | +9,1 (1,1) | +14,3 (1,4) | +23,1 (1,7) | **+62,2 (2,9)** |

Volatilita': |rendimento| medio evento / controllo (stessa ora UTC, stesso
giorno della settimana, +-8 settimane, giorni senza eventi):

| evento | -24h | -4h | -1h | +5m | +1h | +4h | +1 giorno | +5 giorni |
|---|---|---|---|---|---|---|---|---|
| FOMC | 0,85 | 0,69 | 0,92 | **6,49** | **5,43** | 3,16 | 2,19 | 1,29 |
| verbali | 0,99 | 0,94 | 1,15 | 4,60 | 2,35 | 1,16 | 1,24 | 0,90 |
| CPI | 1,09 | 1,10 | 0,97 | 1,78 | 1,04 | 0,97 | 1,20 | 1,06 |
| NFP | 0,95 | 0,71 | 0,86 | 5,01 | 2,81 | 1,79 | 1,41 | 1,03 |

### Regole: t mediano / massimo per famiglia, evento e direzione

| famiglia | direzione | FOMC | verbali | CPI | NFP |
|---|---|---|---|---|---|
| E1 pre-annuncio | long | -0,59 / 0,04 | -0,39 / -0,17 | -0,63 / 0,19 | -2,59 / -2,11 |
| E1 pre-annuncio | short | -1,73 / -0,72 | -0,97 / -0,04 | -1,03 / -0,41 | 0,06 / 1,71 |
| E2 primo movimento | segue | **2,19 / 3,05** | -1,14 / 0,02 | -2,14 / -0,64 | -0,23 / 1,67 |
| E2 primo movimento | rientro | -3,43 / -1,57 | -1,53 / -0,42 | -0,12 / 1,84 | -1,57 / -0,52 |
| E3 giorni dopo | long | -1,25 / -0,93 | 0,79 / 2,81 | -1,28 / -0,89 | 1,07 / 2,07 |
| E3 giorni dopo | short | 0,66 / 1,91 | -1,24 / -0,15 | 0,35 / 0,78 | -1,62 / -0,67 |
| E3 giorni dopo | segue | 1,36 / 1,54 | 0,75 / 1,26 | 0,93 / 1,56 | -0,86 / -0,28 |
| E3 giorni dopo | rientro | -1,99 / -1,64 | -1,31 / -0,55 | -1,85 / -1,43 | 0,03 / 1,15 |

t >= 3: 2 varianti su 464; p ORA < 0,01: 63; p DIREZIONE < 0,01: 30 (27 sono
"FOMC segue"); anni positivi >= 7: 44. Le 36 varianti "FOMC segue" sono
tutte nette positive.

E2 FOMC "segue", t per decisione/filtro/uscita (senza stop / con stop):

| decisione | uscita 1h | uscita 4h | uscita 20:55 UTC |
|---|---|---|---|
| +5m | 2,14 / 1,43 | 2,70 / 2,06 | **3,05** / 2,38 |
| +15m | 1,37 / 1,73 | 2,59 / 2,53 | **3,00** / 2,96 |
| +30m | 0,86 / 0,46 | 1,98 / 2,08 | 2,27 / 2,42 |
| +5m, filtro 0,15 ATR | 2,20 / 1,09 | 2,18 / 1,24 | 2,49 / 1,55 |
| +15m, filtro | 0,98 / 1,25 | 2,26 / 2,45 | 2,68 / 2,83 |
| +30m, filtro | 1,50 / 1,25 | 2,11 / 2,56 | 2,44 / 2,97 |

### Candidati (2)

**E-C1 — FOMC, segui i primi 5 minuti fino a sera.** Ogni comunicato FOMC
programmato (calendario, `straordinaria = False`), istante T dal calendario
(14:00 NY dal 2013; 14:15 NY 2009-2012, 12:30 NY con conferenza stampa apr.
2011 - dic. 2012). P0 = chiusura BID della M5 che termina a T; P5 =
chiusura della M5 [T, T+5m). Se P5 > P0 compra a mercato a T+5m, se P5 < P0
vendi, se uguali niente. Nessuno stop. Uscita a mercato alle 20:55 UTC dello
stesso giorno (chiusura della M5 20:50-20:55). Una operazione per riunione
(8 l'anno).

**E-C2 — come E-C1 con decisione ed entrata a T+15m** (P15 = chiusura della
M5 [T+10m, T+15m) confrontata con P0), uscita alle 20:55 UTC, senza stop.

| candidato | n | netto R x1 / x1,5 | $/oncia x1 / x1,5 | t | anni + | DD R | p ORA / DIR |
|---|---|---|---|---|---|---|---|
| E-C1 (+5m) | 71 | 0,368 / 0,289 | 3,90 / 3,21 | 3,05 | 9/9 | 2,7 | 0,001 / 0,001 |
| E-C2 (+15m) | 70 | 0,319 / 0,293 | 3,06 / 2,83 | 3,00 | 7/9 | 4,6 | 0,001 / 0,002 |

1R = 0,5 x ATR20 (solo misura: nessuno stop). E-C1 paga l'extra annuncio
all'entrata (0,46 + 0,92 = 1,38 $ a x1): lordo ~5,3 $/oncia, resta positivo
finche' il costo reale dell'operazione sta sotto ~5 $. Per anno (R, E-C1):
2009 +1,8, 2010 +1,9, 2011 +4,0, 2012 +2,4, 2013 +5,1, 2014 +2,1, 2015 +3,1,
2016 +2,2, 2017 +3,7; E-C2: 2009 -0,7, 2010 -1,9, poi tutti positivi. Vince
il 62% / 59% delle volte; le 5 migliori operazioni fanno il 46% del totale
(senza di loro t ~2,0). E-C1 per epoca: 2009-2012 +0,33 R (31 operazioni),
2013-2017 +0,40 R (40). Sono la stessa scommessa (prosecuzione del primo
movimento dopo il FOMC): alla verifica contano k = 2 ma sono fortemente
correlate. Prima della verifica serve il `verificatore` (CLAUDE.md).

### Osservazioni

1. **Il FOMC e' l'unico evento con una direzione sfruttabile, e solo come
   prosecuzione.** Dopo il comunicato l'oro continua nel verso dei primi
   5-15 minuti fino a sera: tutte le 36 varianti "segue" sul FOMC sono nette
   positive (t mediano 2,2), le "rientro" tutte negative (t fino a -6,3).
   Verbali, CPI e NFP no (t mediano "segue" fra -2,1 e -0,2); il CPI muove
   poco l'oro (+5m vol x1,8 contro x5-6,5 di FOMC e NFP).
2. **Nessuna deriva pre-annuncio sfruttabile.** Prima del FOMC l'oro non
   sale (+1/+3 punti base, t <= 1,1: la "deriva pre-FOMC" delle azioni non
   c'e' sull'oro) ed e' piu' calmo del normale (vol 0,69-0,92). Prima
   dell'NFP l'oro scende (-8,4 pb nelle 4 ore, t -3,0; long pre-4h t -3,5),
   ma il movimento vale quanto il costo: lo short pre-4h netto e' ~0 R (t
   0,2); lo short da -24h ha t 1,7, anni 7/9, p 0,006 / 0,021: non promosso.
3. **Volatilita' prevedibile, come previsto dal protocollo.** Nei 5 minuti
   dopo l'annuncio |rendimento| x6,5 (FOMC), x5,0 (NFP), x4,6 (verbali),
   x1,8 (CPI); dopo il FOMC resta x2,2 il giorno dopo. Nei giorni successivi
   nessuna regola passa: le migliori sono "long il giorno dopo i verbali" (t
   2,2-2,8, anni 8-9/9, p 0,006-0,02) e "long 3-5 giorni dopo l'NFP" (+62 pb
   a 5 giorni nella descrittiva, t 2,9; come regola t <= 2,1, anni <= 6).

Dettaglio in `D:\ricerca_macro\risultati\`: `e_istanze.parquet` (eventi e
giorni di controllo), `e_descrittiva.parquet`, `e_varianti.parquet` (una
riga per regola con misure, anni, p), `e_operazioni.parquet` (una riga per
evento e regola).
