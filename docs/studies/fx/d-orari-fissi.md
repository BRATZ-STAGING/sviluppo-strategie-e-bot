# Famiglia 4 — Orari fissi del mercato dei cambi (scoperta 2010-2017)

Protocollo: `docs/fx-intraday-registrazione.md`. Script:
`trading/scripts/fx_d_orari_fissi.py`. Dati: solo `D:\ricerca_fx\scoperta\`
(M5 per segnali e gestione, D1 per l'ATR14), 7 coppie: EURUSD, USDJPY, GBPUSD,
AUDUSD, USDCHF, USDCAD, EURJPY. Prezzi BID, indice UTC all'apertura della candela.

## Varianti dichiarate PRIMA del calcolo (03/10/2026)

Ancore (ora locale vera con zoneinfo):

| sigla | evento | ora locale | UTC |
|---|---|---|---|
| TKF | fixing di Tokyo | 09:55 Asia/Tokyo | 00:55 sempre |
| LDF | fixing WM/R di Londra | 16:00 Europe/London | 15:00 estate / 16:00 inverno |
| TKO | apertura borsa di Tokyo | 09:00 Asia/Tokyo | 00:00 |
| TKC | chiusura borsa di Tokyo | 15:00 Asia/Tokyo | 06:00 |
| EUO | apertura Francoforte = apertura Londra | 09:00 Europe/Berlin = 08:00 Londra | 07:00 / 08:00 |
| LNC | chiusura borsa di Londra | 16:30 Europe/London | 15:30 / 16:30 |
| USD | dati USA | 08:30 America/New_York | 12:30 / 13:30 |
| NYO | apertura New York | 09:30 America/New_York | 13:30 / 14:30 |

Francoforte 9:00 e Londra 8:00 sono lo stesso istante tutto l'anno (UE e Regno
Unito cambiano ora negli stessi giorni): un'ancora sola. La chiusura di New
York (16:00 NY = 21:00 UTC d'inverno) cade nella fascia del rollover vietata
dal protocollo: esclusa.

Regole fisse (non sono dimensioni di ricerca):
- segnale sulla chiusura di una candela M5, entrata all'apertura della M5
  successiva; uscita a tempo alla chiusura dell'ultima M5 della durata;
  gestione su M5, stop e obiettivo nella stessa candela = stop; apertura oltre
  lo stop = uscita all'apertura; obiettivo come ordine limite senza
  miglioramento di prezzo;
- al massimo 1 operazione al giorno per regola e per coppia: la frequenza si
  raggiunge **solo sommando le coppie** (massimo 7 operazioni al giorno);
- costi round trip FP Raw del protocollo (pip): EURUSD 0,8, GBPUSD 1,0,
  AUDUSD 0,9, USDCHF 1,0, USDCAD 1,2, USDJPY 1,2, EURJPY 1,4; x2 per entrate
  22:15-23:59 UTC (nessuna regola entra li'), nessuna entrata 20:45-22:15 UTC;
  ogni regola misurata anche con costi x1,5; 1 pip = 0,0001 (0,01 JPY);
- tutte le operazioni chiudono entro le 18:45 UTC: niente swap;
- giornata = giorno UTC lun-ven con almeno 600 minuti nel D1 della coppia (la
  data locale coincide con quella UTC per tutte le ancore); ancora valida se
  la sua M5 e quella d'entrata hanno dati;
- ATR14 = media del true range dei 14 giorni validi precedenti (causale);
- direzione fissa "FIX+" = dollaro in acquisto (USDJPY, USDCHF, USDCAD lunghi;
  EURUSD, GBPUSD, AUDUSD corti); per EURJPY al fixing di Tokyo FIX+ = yen in
  vendita (EURJPY lungo); al fixing di Londra le regole FIX escludono EURJPY;
  "FIX-" = direzione opposta;
- SEGUI / CONTRO = nella direzione del movimento del segnale o contro;
  movimento nullo = nessuna operazione;
- gestione G: **T** solo uscita a tempo; **S** stop a 0,15 x ATR14 e uscita a
  tempo; **ST** stop e obiettivo entrambi a 0,15 x ATR14, altrimenti a tempo;
- gotobi: giorni 5, 10, 15, 20, 25 e ultimo del mese, spostati al venerdi'
  precedente se cadono nel fine settimana (festivi giapponesi ignorati);
  fine mese = ultima giornata di borsa del mese (festivi inglesi ignorati);
- filtro "grande": |movimento del segnale| >= mediana dei 250 valori
  precedenti della stessa coppia e ancora (minimo 60; causale).

**(a) Fixing di Tokyo TKF — 120 regole**
- PRE: entrata 30 o 60 minuti prima (00:25 UTC / 23:55 UTC del giorno
  prima); direzione FIX+ / FIX-; uscita all'istante del fixing (00:55 UTC);
  gestione T; filtro tutti / gotobi / non gotobi: 2 x 2 x 3 = **12**
- POST: entrata 01:00 UTC (dopo la M5 del fixing); direzione FIX+,
  FIX-, SEGUI, CONTRO il movimento 00:25 -> 01:00 (mezz'ora prima del fixing
  piu' la M5 del fixing); durata 30 / 60 / 120 minuti; gestione T / S / ST;
  filtro 3: 4 x 3 x 3 x 3 = **108**
- 7 coppie (FIX su EURJPY = yen in vendita) -> 840 varianti

Nota PRE di Tokyo: 60 minuti prima del fixing = 23:55 UTC del giorno prima,
cioe' nella fascia 22:15-23:59: quella variante paga costo x2 come da
protocollo (dichiarato qui prima del calcolo).

**(b) Fixing WM/R di Londra LDF — 132 regole**
- PRE fisso: entrata 30 o 60 minuti prima (15:30 / 15:00 Londra), FIX+ /
  FIX-, uscita alle 16:00 Londra, gestione T, filtro tutti / fine mese / non
  fine mese: 2 x 2 x 3 = **12** (6 coppie)
- PRE dinamico: stessa entrata e uscita, SEGUI / CONTRO il movimento dalle
  08:00 Londra all'entrata: 2 x 2 x 3 = **12** (7 coppie)
- POST: entrata 16:05 Londra, FIX+ / FIX- (6 coppie) e SEGUI / CONTRO il
  movimento 15:30 -> 16:05 Londra (7 coppie); durata 30 / 60 / 120; gestione
  T / S / ST; filtro 3: 4 x 3 x 3 x 3 = **108**
- varianti: 66 regole x 6 coppie + 66 x 7 = 858

**(c) Aperture, chiusure, dati USA — 6 ancore x 72 = 432 regole**
- ancore TKO, TKC, EUO, LNC, USD, NYO; segnale = movimento nei primi k = 5 o
  15 minuti dopo l'ancora, entrata all'ancora + k; SEGUI / CONTRO; durata
  30 / 60 / 120; gestione T / S / ST; filtro tutti / grande:
  2 x 2 x 3 x 3 x 2 = **72** per ancora
- 7 coppie -> 3024 varianti

**Totale: 684 regole, 4722 varianti regola x coppia**, piu' per ogni regola
due aggregati: "TUTTE" (tutte le coppie ammesse, nessuna scelta) e "POS"
(solo le coppie dove la regola ha netto medio > 0 a costi x1: scelta sugli
stessi dati, **gonfia t e p**). In tutto fino a 1368 aggregati.

Statistiche: netto medio in pip e in multipli del costo; t sul netto (per
coppia per operazione; per gli aggregati sulle **somme giornaliere** delle
coppie, perche' le coppie con il dollaro operano lo stesso giorno e sono
correlate); anni positivi su 8 (somma annua del netto); netto con costi x1,5.
Placebo: per ogni regola e coppia 1000 serie, seed 12345 + numero della
regola; in ogni serie e per ogni giornata con operazione un'entrata a caso fra
le M5 valide nella fascia +/- 2 ore attorno all'entrata reale (stessa durata,
stessa gestione, stessi stop/obiettivi in ATR, nessuna entrata 20:45-22:15 e
uscita entro le 20:45 UTC) e una direzione casuale (direzione reale per un
segno casuale); slot e segno sono **gli stessi per tutte le coppie nella
stessa data**, cosi' l'aggregato conserva la correlazione fra coppie;
p = (1 + #placebo >= reale) / 1001 sul netto medio per operazione, placebo
con lo stesso costo dell'operazione reale.

Promozione (sull'aggregato): netto > 0 con costi x1 e x1,5; t >= 3; anni
positivi >= 6 su 8; p < 0,01; operazioni per giornata di borsa sommando le
coppie >= 1. Al massimo 3 candidati in ordine di t, non piu' di uno per
combinazione ancora-tipo-segnale.

## Risultati (03/10/2026)

Controlli (`python fx_d_orari_fissi.py controlli`): EURUSD, M5 piu' volatile
13:30 UTC in gennaio e 12:30 UTC in luglio (8:30 New York con l'ora legale);
Francoforte 9:00 = Londra 8:00 in tutte le 2074 giornate; fixing di Tokyo
sempre alle 00:55 UTC, quello di Londra alle 15:00 o 16:00 UTC; motore
vettoriale contro ciclo candela per candela su ~400 operazioni (con stop +
obiettivo e con solo stop): differenza 0. Giornate di borsa 2073-2074 per
coppia; gotobi 571, fine mese 96 (EURUSD).

**Varianti provate: 684 regole, 4722 varianti regola x coppia**, tutte con
placebo; 860 aggregati (684 TUTTE + 176 POS: le altre 508 regole non sono
positive su nessuna coppia). Per coppia: netto > 0 in 313 (6,6%), t >= 3 in
**4**, t <= -3 in 2312, anni >= 6/8 in 76, p < 0,01 in 322; netto mediano
-1,05 pip, cioe' circa un costo: **il lordo mediano e' fra -0,04 e +0,04 pip
per ogni ancora**. Aggregati: t >= 3 in 1, frequenza >= 1/giorno in 661,
tutti i criteri tranne la frequenza in 1, **tutti i criteri insieme: 0**.
**Candidati: nessuno.**

### Migliori aggregati per t (nessuno passa)

"coppie" = coppie dove la regola e' positiva a costi x1 (POS: scelte sugli
stessi dati, t e p gonfiati) oppure tutte (TUTTE). op/g = operazioni per
giornata di borsa sommando le coppie. Netto in pip per operazione; t sulle
somme giornaliere delle coppie.

| regola | agg. | coppie | n | op/g | lordo | netto | netto/costo | netto x1,5 | t | anni + | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LDF PRE FIX- 60' fine mese (dollaro venduto 15:00-16:00 Londra) | POS | JPY,GBP,AUD,CHF | 384 | 0,19 | 6,77 | 5,74 | 5,60 | 5,23 | **3,26** | 6 | 0,001 |
| TKF POST FIX- 120' S tutti (dollaro venduto 01:00-03:00 UTC) | POS | EUR,JPY,GBP,AUD | 8214 | **3,96** | 1,53 | 0,56 | 0,57 | 0,07 | 2,34 | 7 | 0,001 |
| TKC POST CONTRO 5' 120' T grande | POS | EUR,CHF | 1893 | 0,91 | 2,35 | 1,45 | 1,61 | 1,00 | 2,31 | 7 | 0,002 |
| LDF POST FIX+ 120' T fine mese (dollaro comprato 16:05-18:05) | POS | 5 coppie USD | 480 | 0,23 | 3,96 | 2,98 | 3,04 | 2,49 | 2,29 | 8 | 0,012 |
| TKF POST FIX- 120' T non gotobi | POS | EUR,JPY,GBP | 4460 | 2,15 | 1,71 | 0,71 | 0,71 | 0,21 | 2,22 | 7 | 0,001 |
| TKF POST FIX- 120' S non gotobi | POS | EUR,JPY,GBP | 4460 | 2,15 | 1,64 | 0,64 | 0,64 | 0,14 | 2,20 | 8 | 0,001 |
| LDF POST FIX+ 120' T fine mese | TUTTE | 6 coppie USD | 576 | 0,28 | 3,44 | 2,43 | 2,39 | 1,92 | 1,92 | 8 | 0,017 |
| TKF PRE FIX+ 30' T tutti (dollaro comprato 00:25-00:55) | POS | EUR,GBP | 4107 | 1,98 | 1,16 | 0,26 | 0,29 | -0,19 | 1,71 | 4 | 0,001 |

Con frequenza >= 1/giorno la migliore e' **TKF POST FIX- 120' stop 0,15 ATR**
su EURUSD, USDJPY, GBPUSD, AUDUSD: 3,96 op/g, +0,56 pip netti, t 2,34,
7 anni su 8, p 0,001, ma con costi x1,5 resta +0,07 pip (0,07 costi): t
sotto 3 e margine sul costo nullo. Senza scelta delle coppie (TUTTE, 7 coppie,
6,9 op/g) la stessa regola con uscita a tempo fa -0,10 pip, t -0,45.

Per coppia le uniche quattro con t >= 3 (tutte < 0,5 op/g):

| regola | coppia | n | op/g | netto | netto x1,5 | t | anni + | p |
|---|---|---|---|---|---|---|---|---|
| LDF PRE FIX- 60' fine mese | GBPUSD | 96 | 0,05 | 12,76 | 12,26 | 3,64 | 7 | 0,001 |
| LDF PRE FIX- 60' fine mese | AUDUSD | 96 | 0,05 | 6,76 | 6,31 | 3,12 | 7 | 0,001 |
| TKC POST CONTRO 5' 120' T grande | EURUSD | 953 | 0,46 | 2,53 | 2,13 | 3,06 | 7 | 0,001 |
| TKC POST CONTRO 5' 120' ST grande | EURUSD | 953 | 0,46 | 1,61 | 1,21 | 3,05 | 8 | 0,001 |

### Fixing senza scelta delle coppie (aggregato TUTTE, uscita a tempo)

| regola | n | op/g | lordo | netto | t | anni + | p |
|---|---|---|---|---|---|---|---|
| TKF PRE dollaro comprato 00:25-00:55, tutti | 14363 | 6,93 | **+0,77** | -0,30 | -2,86 | 2 | 0,001 |
| idem solo gotobi | 3968 | 1,91 | +0,93 | -0,14 | -0,74 | 4 | 0,001 |
| TKF POST dollaro venduto 01:00-03:00, tutti | 14370 | 6,93 | **+0,97** | -0,10 | -0,45 | 3 | 0,001 |
| LDF PRE dollaro venduto 15:30-16:00 Londra, fine mese | 576 | 0,28 | +1,22 | +0,20 | 0,14 | 4 | 0,11 |
| LDF POST dollaro comprato 16:05-18:05, fine mese | 576 | 0,28 | **+3,44** | +2,43 | 1,92 | 8 | 0,017 |
| LDF POST dollaro comprato 16:05-18:05, non fine mese | 11773 | 5,68 | -0,59 | -1,61 | -4,98 | 1 | 0,95 |

Netto annuo (pip, somma delle coppie) di TKF PRE dollaro comprato 30':
2010 +1138, 2011 +288, poi negativo ogni anno dal 2012 al 2017 (-495 ...
-2115). TKF POST dollaro venduto 120': +872, -1324, +1387, -79, -633, -2001,
-499, +808.

### Osservazioni

1. **Il fixing di Tokyo esiste ma non paga il costo.** Il dollaro sale nella
   mezz'ora prima delle 09:55 Tokyo (+0,77 pip lordi per operazione su 7
   coppie, +0,93 nei gotobi) e riscende nelle due ore dopo (+0,97 pip lordi
   vendendolo alle 01:00 UTC): placebo p = 0,001, cioe' l'orario conta davvero.
   Ma il movimento vale meno di un costo round trip (0,8-1,4 pip), e il
   vantaggio pre-fixing e' concentrato nel 2010-2011 e negativo netto in tutti
   gli anni 2012-2017: l'effetto si e' consumato. Il gotobi lo rafforza poco
   (+0,16 pip) e dimezza la frequenza.
2. **Il fixing di Londra conta solo a fine mese**, ed e' l'unico effetto
   grande in pip: l'ultimo giorno del mese il dollaro scende nell'ora prima
   delle 16:00 Londra (GBPUSD +12,8 pip netti, t 3,6) e risale nelle due ore
   dopo (+3,4 pip lordi su 6 coppie, 8 anni su 8). Ma e' un giorno al mese:
   0,05 op/g per coppia, 0,19-0,28 sommando le coppie. Negli altri giorni il
   fixing di Londra non ha direzione (lordo -0,6/+0,4 pip, segno opposto a
   fine mese). Per la frequenza richiesta servirebbero 4-5 regole del genere
   sommate, che non esistono.
3. **Aperture, chiusure e dati USA a orario fisso: niente.** Il lordo medio
   delle regole semplici e' fra -0,55 e +0,55 pip per ogni ancora, sempre
   sotto il costo; nessun aggregato TUTTE ha t > 0 sul netto. La sola traccia
   e' il rientro dopo la chiusura di Tokyo (TKC CONTRO, lordo +0,44 pip su 7
   coppie, t 3,1 su EURUSD con filtro "grande", 0,46 op/g) e dopo i dati USA
   (CONTRO +0,4/+0,55 pip lordi): rientro di breve, ampio meta' del costo.
   L'apertura di Londra/Francoforte, gia' vista nella famiglia 2, non da'
   direzione nei primi 5-15 minuti.

Non provate (sarebbero varianti a posteriori, da registrare a parte):
la combinazione "dollaro comprato prima del fixing di Tokyo + venduto dopo"
come regola unica (paga due costi per ~1,7 pip lordi); le regole di fine
mese di Londra su piu' giorni (ultimi 2-3) per alzare la frequenza.

### Candidati

Nessuno. L'unico aggregato con t >= 3 (LDF PRE FIX- 60' fine mese, 4 coppie
scelte, t 3,26, p 0,001, x1,5 +5,2 pip) fa 0,19 operazioni al giorno; la
migliore regola con frequenza >= 1 (TKF POST FIX- 120' stop 0,15 ATR, 3,96
op/g) ha t 2,34 e con costi x1,5 guadagna 0,07 pip. Niente da congelare per
la famiglia 4.

Dettaglio in `D:\ricerca_fx\risultati\`: `d_orari_regole.parquet` (684
regole), `d_orari_varianti_coppia.parquet` (4722 righe regola x coppia, con
netto per anno e p), `d_orari_aggregati.parquet` (860 aggregati),
`d_orari_esiti_<COPPIA>.parquet` (per giornata e configurazione di
simulazione: lordo lungo/corto all'orario reale), `d_orari_segnali_<COPPIA>.parquet`
(movimenti dei segnali e filtri per giornata), `d_orari_placebo_<COPPIA>.npz`
(somme delle 1000 serie placebo e netto giornaliero per regola).
