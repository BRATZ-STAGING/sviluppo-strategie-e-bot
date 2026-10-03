# Famiglia 2 — Aperture di sessione sui cambi (scoperta 2010-2017)

Protocollo: `docs/fx-intraday-registrazione.md`. Script:
`trading/scripts/fx_b_aperture.py`. Dati: solo `D:\ricerca_fx\scoperta\`
(M5 per la gestione, D1 per l'ATR), 7 coppie: EURUSD, USDJPY, GBPUSD, AUDUSD,
USDCHF, USDCAD, EURJPY. Prezzi BID, indice UTC all'apertura della candela.

## Varianti dichiarate PRIMA del calcolo (03/10/2026)

Regole fisse (non sono dimensioni di ricerca):
- segnale sulla chiusura di una candela M5, entrata all'apertura della M5
  successiva (scartata se arriva piu' di 15 minuti dopo la chiusura del
  segnale); gestione su M5; stop e obiettivo nella stessa candela = stop;
  apertura oltre lo stop = uscita all'apertura; obiettivo come ordine limite
  senza miglioramento di prezzo;
- una sola operazione per sessione, per regola e per coppia;
- costi round trip FP Raw del protocollo (pip): EURUSD 0,8, GBPUSD 1,0,
  AUDUSD 0,9, USDCHF 1,0, USDCAD 1,2, USDJPY 1,2, EURJPY 1,4; x2 per entrate
  22:15-23:59 UTC, nessuna entrata 20:45-22:15 UTC; ogni regola misurata anche
  con costi x1,5; 1 pip = 0,0001 (0,01 per le coppie JPY);
- nessuna posizione oltre le 20:45 UTC (uscita alla chiusura della M5 che
  apre alle 20:40 UTC): niente swap;
- operazione scartata se il rischio < 2 x costo round trip;
- orari con l'ora legale vera (zoneinfo Europe/London, America/New_York);
  giornate = date di Londra lun-ven; finestra del range valida solo se ha
  almeno l'80% delle M5 attese;
- ATR14 = media del true range dei 14 giorni UTC precedenti con almeno 600
  minuti di dati (causale, dal file D1);
- regime: rapporto range / ATR14 contro i terzili dei 250 valori precedenti
  della stessa coppia e dello stesso range (minimo 60): piccolo <= terzile
  basso, grande >= terzile alto, tutti = nessun filtro;
- giorno della settimana: tutti, oppure solo mar-mer-gio (data di Londra).

Regole di segnale:
- ROTTURA: prima chiusura M5 fuori dal range dentro la finestra -> nella
  direzione della rottura;
- RIENTRO: dopo la prima chiusura fuori (dentro la finestra), prima chiusura
  di nuovo dentro il range entro le 12 M5 successive -> contro la rottura;
- SEGUI / CONTRO (parte c): direzione della prima ora (chiusura dell'ultima
  M5 meno apertura della prima; ora piatta = niente) -> entrata all'apertura
  della M5 successiva, nella stessa direzione o contro.

Stop (3): ROTTURA / SEGUI: S1 altro lato del range (o dell'ora), S2 meta'
range, S3 0,25 x ATR14 dall'entrata. RIENTRO / CONTRO: S1 estremo raggiunto
(dalla rottura al rientro; per CONTRO l'estremo dell'ora), S2 lato rotto +/-
0,5 x range, S3 0,25 x ATR14 dall'entrata.
Obiettivi: 1R, 2R, 1 x range dall'entrata; se non toccati, uscita a fine
sessione. Risultati in pip, in R (rischio = distanza entrata-stop) e in
multipli del costo.

**(a) Range asiatico -> prima ora di Londra — 360 regole**
- 2 range: A1 = 00:00-07:00 Londra, finestra 07:00-08:00 Londra;
  A2 = 22:15 UTC del giorno prima - 08:00 Londra, finestra 08:00-09:00 Londra
- 2 regole (ROTTURA, RIENTRO) x 3 stop
- 5 uscite: fine sessione di Londra (16:00 Londra), 20:45 UTC, 1R, 2R,
  1 x range (gli obiettivi altrimenti escono alle 16:00 Londra)
- 3 regimi x 2 filtri giorno
- 2 x 2 x 3 x 5 x 3 x 2 = **360**

**(b) Range della mattina di Londra -> apertura di New York — 288 regole**
- 2 range: B1 = 08:00 Londra - 08:00 New York, finestra 08:00-09:30 NY;
  B2 = 08:00 Londra - 09:30 New York, finestra 09:30-10:30 NY
- 2 regole x 3 stop x 4 uscite (20:45 UTC, 1R, 2R, 1 x range) x 3 regimi x
  2 filtri giorno
- 2 x 2 x 3 x 4 x 3 x 2 = **288**

**(c) Direzione della prima ora -> resto della sessione — 432 regole**
- 3 sessioni: CL = prima ora 08:00-09:00 Londra, fine 16:00 Londra;
  CN1 = 08:00-09:00 NY, fine 20:45 UTC; CN2 = 09:30-10:30 NY, fine 20:45 UTC
- 2 regole (SEGUI, CONTRO) x 3 stop x 4 uscite (fine sessione, 1R, 2R,
  1 x range dell'ora) x 3 regimi (range dell'ora / ATR14) x 2 filtri giorno
- 3 x 2 x 3 x 4 x 3 x 2 = **432**

**Totale: 1080 regole x 7 coppie = 7560 varianti per coppia**, piu' 1080
aggregati "regola sulle coppie dove e' positiva" (netto medio in R > 0 con
costi x1). Placebo per ogni variante e aggregato: stessi istanti, stessa
gestione speculare (stesse distanze di stop e obiettivo), direzione casuale,
1000 serie, seed 12345; p = (1 + #placebo >= reale) / 1001 sul netto medio
in R. t calcolato sul netto in R per operazione.

Promozione (sull'aggregato della regola): netto > 0 con costi x1 e x1,5;
t >= 3; anni positivi >= 6 su 8; p placebo < 0,01; operazioni per giornata di
borsa sommando le coppie >= 1. Al massimo 3 candidati, in ordine di t, non
piu' di uno per combinazione parte-range-regola. Giornata di borsa = giorno
UTC lun-ven con almeno 600 minuti di dati nella coppia.

## Risultati (03/10/2026)

Controlli: fusi orari giusti (EURUSD, M5 piu' volatile 13:30 UTC in gennaio
e 12:30 UTC in luglio, cioe' 8:30 New York con l'ora legale); motore
vettoriale confrontato con un ciclo candela per candela su 400 operazioni
casuali: differenza massima 1e-16. Giornate di borsa 2073-2074 per coppia.
Operazioni base generate: 18-20 mila per coppia (tutti i setup e le regole).

**Varianti provate: 1080 regole x 7 coppie = 7560**, tutte valutate; 721
aggregati "regola sulle coppie dove e' positiva" (le altre 359 regole non
sono positive su nessuna coppia). Per coppia: netto > 0 in 1548 (20%),
t >= 3 in **2**, t <= -3 in 913, anni >= 6/8 in 344, p < 0,01 in 172; netto
mediano -0,060 R, il 79,5% ha t < 0. Quota positiva per parte: a 31%, b 20%,
c 12%. Aggregati: t >= 3 in 4, frequenza >= 1/giorno in 39, **tutti i criteri
insieme: 0**. **Candidati: nessuno.**

### Migliori aggregati per t (nessuno passa)

"coppie" = le coppie dove la regola e' positiva a costi x1 (scelte sui dati
stessi: t e p dell'aggregato sono gonfiati da questa scelta). op/g = operazioni
per giornata di borsa sommando quelle coppie. netto/costo = netto medio in pip
diviso il costo round trip.

| regola | coppie | n | op/g | netto pip | netto R | netto/costo | t | anni + | netto R x1,5 | p |
|---|---|---|---|---|---|---|---|---|---|---|
| a A1 RIENTRO S3 1R piccolo mar-gio | AUD,EURJPY,EUR,GBP,CHF | 869 | 0,42 | 3,70 | 0,123 | 3,78 | 3,75 | 7 | 0,102 | 0,001 |
| a A1 RIENTRO S3 RNG piccolo mar-gio | AUD,EURJPY,EUR,GBP,CHF | 869 | 0,42 | 3,34 | 0,105 | 3,43 | 3,48 | 7 | 0,084 | 0,001 |
| a A2 ROTTURA S1 1R tutti tutti | EURJPY,USDJPY | 1632 | 0,79 | 2,94 | 0,057 | 2,23 | 3,11 | 7 | 0,042 | 0,001 |
| a A2 RIENTRO S2 E0 piccolo tutti | EUR,GBP,CHF | 955 | 0,46 | 4,34 | 0,229 | 4,35 | 3,06 | 7 | 0,195 | 0,001 |
| a A1 RIENTRO S3 1R piccolo tutti | EUR,GBP,CHF | 1069 | 0,52 | 2,99 | 0,087 | 3,11 | 2,92 | 6 | 0,067 | 0,001 |
| a A2 RIENTRO S1 RNG piccolo mar-gio | EUR,GBP | 367 | 0,18 | 3,95 | 0,309 | 4,32 | 2,91 | 7 | 0,256 | 0,001 |

Le prime quattro passano TUTTO tranne la frequenza (massimo 0,79 op/giorno).
Con frequenza >= 1/giorno la migliore e' **a A2 ROTTURA S1 E2045 tutti tutti**
su EURJPY, EURUSD, USDJPY: 2738 operazioni, 1,32 op/g, +1,95 pip, +0,053 R,
t 2,36, 7 anni su 8, x1,5 +0,039 R, p 0,001 — t sotto 3. Seguono
c CL CONTRO S3 E0 piccolo (4 coppie, 1,29 op/g, t 2,33, p 0,017) e
c CN1 SEGUI S3 E0 grande (4 coppie, 1,29 op/g, t 2,10).

Per coppia le uniche due con t >= 3 sono entrambe **GBPUSD, A2 RIENTRO S2 E0
piccolo** (tutti i giorni: 318 op, 0,15 op/g, +9,4 pip, +0,46 R, t 3,24,
6 anni, p 0,001; mar-gio: t 3,10): frequenza lontanissima da 1.

Dettaglio delle quasi-candidate, per coppia (netto R / t):

| regola | AUD | EURJPY | EUR | GBP | CAD | CHF | USDJPY |
|---|---|---|---|---|---|---|---|
| A1 RIENTRO S3 1R piccolo mar-gio | 0,06 / 0,6 | 0,08 / 1,0 | 0,17 / 2,4 | 0,12 / 1,8 | -0,03 / -0,4 | 0,15 / 2,2 | -0,13 / -1,6 |
| A2 ROTTURA S1 1R tutti tutti | -0,03 / -1,0 | 0,07 / 2,6 | -0,01 / -0,3 | -0,05 / -2,0 | -0,05 / -1,9 | -0,04 / -1,7 | 0,04 / 1,7 |
| A2 RIENTRO S2 E0 piccolo tutti | -0,02 / -0,2 | -0,02 / -0,1 | 0,02 / 0,2 | 0,46 / 3,2 | -0,14 / -1,1 | 0,20 / 1,6 | -0,18 / -1,5 |

### Lordo, tutte e 7 le coppie insieme (diagnostica, non candidati)

Regola base con regime e giorni = tutti, nessuna scelta delle coppie
(`fx_b_lordo_diagnostica.parquet`, 180 regole base): **nessuna ha t netto
>= 2**.

| regola | n | rischio mediano pip | lordo R | t lordo | netto R | t netto | coppie lordo > 0 |
|---|---|---|---|---|---|---|---|
| A1 RIENTRO S1 obiettivo 1 x range | 4840 | 8,1 | 0,116 | 3,70 | -0,035 | -1,12 | 6/7 |
| CL CONTRO S1 fine sessione | 11214 | 6,9 | 0,132 | 3,53 | -0,054 | -1,44 | 6/7 |
| CL CONTRO S2 fine sessione | 14263 | 17,0 | 0,055 | 3,38 | -0,020 | -1,23 | 6/7 |
| CL CONTRO S3 fine sessione | 14273 | 24,7 | 0,043 | 3,38 | -0,004 | -0,35 | 6/7 |
| A1 RIENTRO S1 fine sessione | 4840 | 8,1 | 0,130 | 2,81 | -0,021 | -0,45 | 7/7 |
| CN2 CONTRO S1 obiettivo 1R | 11797 | 8,0 | -0,055 | -6,10 | -0,222 | -24,1 | 0/7 |

Segno per coppia della regola piu' semplice (stop S1, fine sessione, tutti):
la ROTTURA del range asiatico A2 ha lordo positivo su EURJPY, USDJPY,
EURUSD, USDCHF e negativo su GBPUSD, AUDUSD, USDCAD; il RIENTRO A2 e'
fortemente positivo su GBPUSD (+0,41 R lordo) e USDCHF e negativo su AUDUSD
e USDCAD. USDCAD e AUDUSD sono negative quasi ovunque nelle parti a e c.

### Osservazioni

1. **Il range asiatico a Londra tende a rientrare, non a proseguire**, sulle
   coppie europee: il RIENTRO A1 ha lordo positivo su 7 coppie su 7 (fine
   sessione) e la quasi-candidata migliore (A1 RIENTRO, stop 0,25 ATR,
   obiettivo 1R, range asiatico piccolo, mar-gio) ha t 3,75 e 7 anni su 8 su
   cinque coppie, ma fa 0,42 operazioni al giorno: la frequenza, non il
   segno, la esclude. La ROTTURA prosegue solo sulle coppie con lo yen
   (EURJPY, USDJPY: t 3,1 aggregato, 0,79 op/g). Previsione 2 del protocollo
   confermata: il segno cambia fra coppie (yen contro europee; AUD e CAD
   negative).
2. **Il costo decide quasi tutto.** Le regole con stop stretto (S1 nel
   RIENTRO/CONTRO, 7-9 pip) hanno lordo fino a +0,13 R ma il costo vale
   0,10-0,15 R; nelle 913 varianti con t <= -3 il costo mediano e' 0,131 R
   contro un lordo mediano di -0,05 R. Con stop larghi (S3, 25 pip) il costo
   scende a 0,04 R ma anche il lordo si riduce in proporzione.
3. **A Londra stop speculari in entrambe le direzioni guadagnano** (la somma
   lungo+corto della stessa operazione e' positiva, t 5,3-5,5 nella parte CL;
   a New York e' circa zero): la mattina di Londra ha espansione di
   volatilita' con prosecuzione, e una regola con stop e uscita a fine
   sessione guadagna qualunque direzione scelga. Per questo CL CONTRO e
   CL SEGUI hanno entrambe lordo positivo ma il placebo a direzione casuale
   fa quasi uguale (p 0,15-0,31 a frequenza >= 1): non e' direzione. New York
   (parte b e CN1/CN2) e' la zona peggiore: nessun lordo utile, CONTRO con
   obiettivo 1R fortemente negativo.

Non provate (sarebbero varianti a posteriori, da registrare a parte): la
"doppia" entrata a Londra (lungo e corto insieme, che sfrutterebbe
l'osservazione 3 pagando due costi); la regola A1 RIENTRO allargata ad altri
giorni o regimi per raggiungere la frequenza.

### Candidati

Nessuno: 4 aggregati passano netto x1/x1,5, t >= 3, anni >= 6/8 e p < 0,01,
ma hanno 0,42-0,79 operazioni al giorno; nessuna regola con frequenza >= 1
raggiunge t >= 3 (massimo 2,36). Niente da congelare per la famiglia 2.

Dettaglio in `D:\ricerca_fx\risultati\`: `fx_b_dettaglio_<COPPIA>.parquet`
(una riga per operazione e configurazione base, con l'esito nella direzione
opposta per il placebo), `fx_b_varianti.parquet` (una riga per regola e
coppia + aggregati POS), `fx_b_lordo_diagnostica.parquet`.
