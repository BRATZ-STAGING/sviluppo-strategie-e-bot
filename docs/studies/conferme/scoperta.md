# Crollo -> conferma di ripresa -> entrata (e specchio short) — scoperta 2009-2017

Protocollo VINCOLANTE: `docs/crollo-conferma-registrazione.md` (commit
5a2ea2b), non modificato. Motore: `trading/framework/crollo_conferma.py`
(funzioni pure); test: `trading/tests/test_crollo_conferma.py` (23 test);
script: `trading/scripts/crollo_conferma_scoperta.py` (circa 40 s). Dettaglio
in `D:\ricerca_conferme\risultati\` (`operazioni.parquet`,
`varianti.parquet`, `verifica_motore.parquet`).

Dati: solo `D:\ricerca_zero\scoperta\XAUUSD_M5|M15|H1|D1.parquet` e
`data/XAUUSD_M1/XAUUSD_M1_2009..2017.parquet` (solo per il volume del VWAP).
Nessuna cartella di verifica aperta, nessun anno >= 2018 caricato.

**Esito: 0 candidati su 672 varianti.** Nessuna variante arriva a t >= 3;
la migliore ha t 2,48 su 11 operazioni in nove anni.

## Interpretazioni scelte (punti ambigui -> lettura prudente)

1. **Giornata e ATR20**: giornata = giorno UTC; i giorni con meno di 300
   minuti (domenica sera, festivi) si uniscono alla giornata valida
   successiva (2.329 giornate). ATR20 = media semplice di 20 true range;
   vale quello dell'ultima giornata **chiusa** prima dell'istante.
2. **Barre del segnale** costruite dalle M5: M15 e H1 coincidono con i
   Parquet (scarto 0); H4 = blocchi di 4 ore UTC etichettati all'apertura;
   D1 = giornata del punto 1. L'entrata "all'apertura della barra
   successiva" e' l'apertura di una M5.
3. **Crollo**: alla chiusura della barra i, massimo della finestra (24 ore di
   barre per l'intraday; giornata corrente + 9 precedenti per lo swing) meno
   il **minimo della barra i** >= k x ATR. Un episodio parte solo sul
   **fronte** (condizione vera in i e falsa in i-1) e solo se non ce n'e' uno
   in corso: dopo uno stop o una scadenza, lo stesso crollo non si
   ricompra finche' il prezzo non torna sopra la soglia per almeno una barra.
4. **Inizio crollo** = barra del massimo della finestra (la piu' recente a
   parita'); H = quel massimo, fisso per l'episodio (obiettivo "ritorno al
   massimo"). L = minimo dalla barra di H, aggiornato a ogni nuovo minimo.
5. **Scadenza**: la barra di conferma deve chiudere entro 8 ore (intraday)
   o entro 10 giornate (swing) dalla barra dell'**ultimo** minimo L.
6. **Frattali** a 2 barre per lato con estremo stretto, visibili solo alla
   chiusura di f + 2. C1: ultimo frattale alto noto con f dopo la barra di
   H. C2: ultimo frattale basso noto con f dopo la barra di L e minimo > L;
   livello = massimo delle barre da L a f incluse.
7. **C3 "recupero"** = incrocio dal basso (chiusura precedente <= livello,
   chiusura attuale > livello), non la semplice chiusura sopra (altrimenti
   C3a/C3b scatterebbero subito quando il livello e' gia' sotto il prezzo).
   C3a: VWAP del giorno UTC (volume Dukascopy) alla chiusura della barra;
   C3b: EMA20 delle chiusure del TF; C3c: L + 50% (H - L) con L corrente.
8. **C4**: la candela deve toccare il minimo corrente (minimo = L dopo
   l'aggiornamento) ed essere un martello (chiusura nel terzo alto, ombra
   inferiore >= 2 x corpo) o un engulfing rialzista (corpo che avvolge il
   corpo ribassista precedente); conferma solo se la **barra subito dopo**
   chiude sopra il suo massimo.
9. **C5**: almeno due fra C1, C2, C3a, C4 avvenute **dopo l'ultimo nuovo
   minimo** (un nuovo minimo azzera i conteggi).
10. **Stop e rischio**: stop = L - 0,1 x ATR noto all'entrata; si scarta se
    1R > 1,5 x ATR o 1R < 2 x 0,46 $ (filtro sul costo x1, stesse operazioni
    nei due scenari di costo).
11. **Gestione su M5**: lo stop prevale nella stessa candela; apertura oltre
    lo stop = uscita all'apertura; apertura oltre l'obiettivo = uscita
    all'**obiettivo** (non al prezzo migliore). Obiettivo H gia' superato
    all'entrata = uscita immediata (perdita del costo).
12. **Intraday**: entrate vietate se l'apertura cade in [20:45, 22:15) UTC
    (il segnale si perde, non si rimanda); uscita al prezzo delle 20:55 UTC
    (chiusura dell'ultima M5 terminata entro le 20:55) dello stesso giorno, o
    del giorno dopo per le entrate dopo le 22:15. Nessuna intraday paga swap.
13. **Swing**: uscita alla chiusura della giornata (entrata + 19), cioe' al
    massimo 20 giornate di calendario di trading.
14. **Una posizione alla volta per direzione** per variante (gli episodi
    sono generati dal prezzo; un segnale che arriva con la posizione aperta
    si salta).
15. **Swap FP**: -0,715 $ (long) / +0,325 $ (short) per oncia e per notte x
    prezzo d'entrata / 4156,98; notte = 21:00 UTC lun-ven con la posizione
    aperta alle 21:00 (uscita in una M5 che apre alle 21:00 o dopo),
    mercoledi' x3. Costo 0,46 $ RT (x1) e 0,69 $ (x1,5).
16. **Riferimento "senza conferma"**: entrata all'apertura della barra dopo
    il fronte del crollo (stesso TF), stop L corrente - 0,1 x ATR
    all'entrata, stessi obiettivi e stessa gestione.
17. **t di promozione** = il **minore** fra t sulle operazioni (non
    sovrapposte per costruzione) e t mensile (108 mesi, mesi vuoti = 0).
    "Netto > 0" richiesto in R **e** in $ a x1 e x1,5. "Migliore del
    riferimento" = netto medio in R maggiore a x1 **e** a x1,5.
18. **Placebo**: stessi istanti d'entrata, direzione casuale per ogni
    operazione (la direzione opposta ha stop e obiettivi specchiati e il
    proprio swap), 2.000 serie, seed 12345 + indice della variante;
    statistica = netto totale in R a x1; p = (1 + #placebo >= reale)/2001.
19. **Conteggio riferimenti**: il protocollo scrive "48 riferimenti" ma la
    sua formula (2 x 2 x 3 x 4 x 2) da' **96** (48 per lato): calcolati
    tutti e 96, riportati, mai promossi.

## Controlli

| controllo | esito |
|---|---|
| test pytest (C1 alla barra giusta, scadenza, frattale invisibile prima di 2 barre, stop in gap all'apertura, swap, short = specchio esatto del long per tutte le conferme, troncamento senza lookahead, motore vettoriale = ciclo) | 23/23 |
| M15/H1 costruite dalle M5 contro i Parquet | scarto 0 |
| troncamento sui dati veri (C1 e C5, 4 TF, 2 lati: segnali prima del taglio identici) | 16/16 casi, 2.891 segnali |
| motore su 300 operazioni rifatte con un ciclo barra per barra indipendente (limite di tenuta, uscita, swap contato giorno per giorno) | differenza 0,00 $ e 0 barre |

## Varianti

672 dichiarate (2 orizzonti x 2 TF x 3 k x 7 conferme x 4 obiettivi x 2
lati) + 96 riferimenti. **600 varianti hanno operazioni; 72 nessuna**, tutte
swing: il limite 1R <= 1,5 x ATR elimina quasi tutte le conferme su D1
(dopo un crollo di 2-4 ATR la conferma arriva in media 2,3-2,8 ATR sopra L;
su D1 restano 3 operazioni C1 su 229 segnali, 0 C2 su 124, 80 C3b su 388).
Segnali scartati per entrata nella fascia vietata (intraday): 2-6%.

Criteri superati (su 600): netto > 0 a x1 e x1,5 (R e $) 134; t >= 3
**0**; anni positivi >= 7/9 3; placebo p < 0,01 9; meglio del riferimento
406; **tutti 0**.

## Migliori 15 per t (nessuna passa)

t = min(t operazioni, t mensile); R e $ netti per operazione con swap.

| oriz. | TF | k | conf. | obiettivo | lato | n | op/mese | vinte | R x1 | R x1,5 | $ x1 | t op | t mese | anni+ | DD R | p | R rif. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| swing | D1 | 3 | C3b | 1R | long | 11 | 0,10 | 82% | 0,646 | 0,637 | 18,25 | 3,39 | 2,48 | 5 | 1,02 | 0,013 | -0,091 |
| swing | D1 | 3 | C4 | 1R | long | 10 | 0,09 | 80% | 0,631 | 0,619 | 14,62 | 2,89 | 2,24 | 6 | 1,11 | 0,021 | -0,091 |
| swing | D1 | 2 | C4 | 1R | long | 13 | 0,12 | 77% | 0,553 | 0,542 | 11,19 | 2,56 | 2,18 | 5 | 1,11 | 0,018 | -0,175 |
| intraday | M15 | 1,5 | C3c | 1R | short | 32 | 0,30 | 53% | 0,241 | 0,227 | 5,75 | 2,65 | 2,05 | 6 | 1,71 | 0,003 | -0,139 |
| intraday | M15 | 1,5 | C3c | 2R | short | 32 | 0,30 | 50% | 0,255 | 0,241 | 6,64 | 2,05 | 2,08 | 6 | 2,28 | 0,011 | -0,149 |
| swing | D1 | 4 | C4 | 1R | long | 4 | 0,04 | 100% | 0,945 | 0,934 | 25,54 | 61,0 | 2,03 | 4 | 0,00 | 0,068 | -0,003 |
| intraday | M15 | 1,5 | C3c | H | short | 33 | 0,31 | 55% | 0,191 | 0,178 | 4,47 | 2,52 | 1,99 | 7 | 1,70 | 0,002 | -0,071 |
| swing | D1 | 3 | C5 | 3R | long | 10 | 0,09 | 60% | 1,369 | 1,358 | 31,33 | 2,27 | 1,93 | 4 | 2,18 | 0,013 | -0,197 |
| swing | D1 | 3 | C4 | 3R | long | 10 | 0,09 | 60% | 1,355 | 1,343 | 31,33 | 2,22 | 1,91 | 4 | 2,33 | 0,015 | -0,197 |
| swing | D1 | 3 | C3b | H | long | 11 | 0,10 | 64% | 0,874 | 0,865 | 28,68 | 2,17 | 1,90 | 4 | 1,20 | 0,003 | -0,226 |
| swing | D1 | 4 | C5 | 1R | short | 7 | 0,07 | 86% | 0,703 | 0,691 | 16,37 | 2,43 | 1,88 | 6 | 1,04 | 0,021 | -0,239 |
| swing | D1 | 2 | C5 | 3R | long | 13 | 0,12 | 54% | 1,083 | 1,071 | 24,90 | 1,99 | 1,82 | 4 | 3,21 | 0,009 | -0,294 |
| swing | D1 | 3 | C3b | 2R | long | 11 | 0,10 | 64% | 0,803 | 0,794 | 25,25 | 2,03 | 1,81 | 4 | 1,20 | 0,004 | -0,120 |
| swing | D1 | 3 | C5 | H | long | 10 | 0,09 | 60% | 1,480 | 1,469 | 31,99 | 2,05 | 1,80 | 4 | 2,18 | 0,016 | -0,226 |
| swing | D1 | 2 | C3b | 1R | long | 31 | 0,29 | 68% | 0,315 | 0,303 | 5,58 | 1,92 | 1,80 | 5 | 5,43 | 0,020 | -0,175 |

Dodici delle 15 sono swing D1 con 4-13 operazioni in nove anni (una ogni
8-27 mesi): sono i pochi crolli in cui la conferma arriva vicino al minimo
(1R <= 1,5 ATR). Statisticamente non distinguibili dal caso; anni positivi
4-6 su 9 perche' in 3-5 anni non c'e' nessuna operazione.

## Conferma contro "senza conferma" (medie sulle varianti)

vinte e R netti x1 per operazione; rif = riferimento senza conferma con
stesso orizzonte, TF, k, obiettivo e lato; "meglio" = quota di varianti con
R migliore del riferimento a x1 e x1,5. I $ swing pesano molto piu' degli
intraday (1R swing di decine di $).

| orizzonte | conferma | varianti | n medio | vinte | vinte rif | R | R rif | $ | $ rif | meglio |
|---|---|---|---|---|---|---|---|---|---|---|
| intraday | C1 | 48 | 391 | 40,7% | 40,0% | -0,105 | -0,119 | -0,76 | -0,43 | 60% |
| intraday | C2 | 48 | 257 | 39,3% | 40,0% | -0,159 | -0,119 | -1,08 | -0,43 | 42% |
| intraday | C3a | 48 | 504 | 40,5% | 40,0% | -0,119 | -0,119 | -0,82 | -0,43 | 50% |
| intraday | C3b | 48 | 481 | 42,0% | 40,0% | -0,080 | -0,119 | -0,46 | -0,43 | 69% |
| intraday | C3c | 48 | 229 | 44,8% | 40,0% | -0,001 | -0,119 | 0,43 | -0,43 | 90% |
| intraday | C4 | 48 | 118 | 37,9% | 40,0% | -0,145 | -0,119 | -1,09 | -0,43 | 48% |
| intraday | C5 | 48 | 390 | 40,3% | 40,0% | -0,109 | -0,119 | -0,72 | -0,43 | 60% |
| swing | C1 | 36 | 49 | 25,3% | 29,5% | -0,315 | -0,179 | -7,31 | -0,15 | 58% |
| swing | C2 | 24 | 50 | 31,9% | 29,3% | -0,103 | -0,167 | -3,25 | -0,02 | 67% |
| swing | C3a | 48 | 116 | 32,1% | 28,6% | -0,084 | -0,198 | -0,06 | -0,38 | 79% |
| swing | C3b | 44 | 56 | 44,2% | 29,3% | 0,202 | -0,182 | 9,52 | -0,31 | 84% |
| swing | C3c | 16 | 18 | 37,5% | 28,1% | -0,160 | -0,248 | -6,80 | -1,40 | 63% |
| swing | C4 | 48 | 18 | 46,1% | 28,6% | 0,342 | -0,198 | 9,81 | -0,38 | 83% |
| swing | C5 | 48 | 50 | 45,1% | 28,6% | 0,343 | -0,198 | 9,02 | -0,38 | 90% |

Tutte le operazioni insieme (non per variante):

| orizzonte | | operazioni | vinte | R x1 | $ x1 |
|---|---|---|---|---|---|
| intraday | con conferma | 113.741 | 40,4% | -0,098 | -0,66 |
| intraday | senza conferma | 44.322 | 40,5% | -0,109 | -0,36 |
| swing | con conferma | 14.589 | 35,3% | -0,029 | 0,21 |
| swing | senza conferma | 6.220 | 29,3% | -0,194 | -0,52 |

## Intraday contro swing, long contro short (medie sulle varianti)

| gruppo | varianti | n medio | vinte | R | R rif | $ | quota R x1,5 > 0 | t max |
|---|---|---|---|---|---|---|---|---|
| intraday M15 | 168 | 464 | 40,0% | -0,108 | -0,127 | -0,57 | 5% | 2,05 |
| intraday H1 | 168 | 213 | 41,6% | -0,098 | -0,111 | -0,72 | 9% | 1,07 |
| swing H4 | 152 | 77 | 34,4% | -0,050 | -0,169 | -0,60 | 36% | 1,46 |
| swing D1 | 112 | 26 | 43,8% | 0,259 | -0,226 | 8,57 | 63% | 2,48 |
| long | 308 | 207 | 41,0% | 0,012 | -0,146 | 1,45 | 23% | 2,48 |
| short | 292 | 221 | 38,4% | -0,058 | -0,158 | 0,71 | 26% | 2,05 |

Riferimenti senza conferma: tutti negativi in R (da -0,10 a -0,26 per
gruppo TF x lato), t massimo 0,57.

## Candidati

**Nessuno** (0 su 672). Nessuna specifica va congelata per la verifica
2018 -> 07/2026, che quindi non si esegue per questa famiglia.

## Previsioni registrate

1. "La conferma alza le vincite ma il netto resta vicino al senza
   conferma": **vera per l'intraday** (vinte 40,4% contro 40,5%, R -0,10
   contro -0,11: la conferma non aggiunge niente); **falsa per lo swing**,
   dove la conferma alza sia le vincite (35% contro 29%) sia il netto (R
   -0,03 contro -0,19), ma sempre senza forza statistica.
2. "Lo swing fa meglio dell'intraday": **vera** in media (R +0,08 contro
   -0,10), ma la parte buona (D1) ha 4-31 operazioni per variante.
3. "Al massimo un candidato passa la verifica": nessun candidato arriva
   alla verifica.

## Osservazioni

1. **Intraday: la conferma non aggiunge niente.** Le 336 varianti intraday
   perdono in media 0,10 R, quanto l'entrata immediata (-0,12 R); solo C3c
   (recupero del 50%) arriva a zero (R -0,001) e solo in M15 k=1,5 short
   tocca t 2,05 con p placebo 0,003. Il lordo e' quasi nullo in entrambi i
   casi (con conferma -0,03 R long / -0,05 short; senza +0,015 / +0,02) e il
   costo vale 0,06-0,12 R: la conferma peggiora appena il lordo e lo
   compensa solo con un 1R piu' largo (costo relativo minore).
2. **Swing: la conferma migliora il riferimento ma il filtro di rischio la
   rende rarissima.** Con stop sotto L e 1R <= 1,5 ATR, sulle D1 dopo un
   crollo di 2-4 ATR passano solo le conferme arrivate quasi sul minimo
   (C4, C3b, C5): 4-13 operazioni in nove anni, R medio +0,3/+1,5 ma t <= 2,5
   e anni positivi <= 6 (in 3-5 anni la variante non opera affatto). E'
   l'area da guardare con sospetto, non da promuovere.
3. **Il placebo direzione e' spesso significativo dove t non lo e'** (9
   varianti con p < 0,01, t fra 1,3 e 2,1): la direzione long dopo un crollo
   conta piu' del caso nelle stesse date, ma il guadagno e' troppo piccolo o
   troppo raro per superare t 3. Il lato short e' peggiore del long anche
   nel lordo (con conferma: intraday -0,05 contro -0,03 R, swing -0,01
   contro +0,06 R; vinte 38% contro 41%), e lo swap FP positivo dello short
   (+0,03 R nello swing) non basta a compensare.
