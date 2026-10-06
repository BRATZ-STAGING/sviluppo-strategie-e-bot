# Crollo -> conferma di ripresa -> entrata (e lo specchio short) — protocollo registrato (06/10/2026)

Richiesta dell'utente: non prevedere l'oro ma "capirlo e muoversi dopo": dopo un
crollo aspettare che risalga ed entrare solo dopo conferme. Le conferme le ha
scelte l'utente (tutte e quattro), su **intraday e swing**, **long e short**.
Scritto prima di qualunque calcolo di queste regole. Nessuno studio precedente
del progetto ha testato questo schema (gli studi di ritorno alla media
entravano subito, senza conferma; il VWAP reclaim usa una sola conferma ed e'
gia' bocciato: qui compare solo come uno dei livelli).

## Dati e periodi

- Oro M1 Dukascopy `data/XAUUSD_M1/` (con volume, per il VWAP) e M5/H1/D1 in
  `D:\ricerca_zero\scoperta\`. **Scoperta 2009-2017** (si caricano solo quegli
  anni). **Verifica oro 2018 -> 07/2026**, una volta sola.
- **Controllo di trasferimento** (solo dopo la verifica dell'oro, stesse regole
  invariate): argento, S&P 500, EUR/USD (HistData, 2010-2026, VWAP a peso
  uniforme perche' senza volume). Non decide il verdetto: lo rafforza o lo
  indebolisce.

## Definizioni (vincolanti)

ATR = ATR20 giornaliero (causale). Orizzonti e timeframe del segnale:
- **intraday**: TF M15 e H1; crollo = discesa >= k x ATR dal massimo delle
  ultime 24 ore, k in {0,75; 1,0; 1,5}; conferma entro 8 ore dal minimo;
  posizioni chiuse entro le 20:55 UTC; nessuna entrata 20:45-22:15 UTC.
- **swing**: TF H4 e D1; crollo = discesa >= k x ATR dal massimo delle ultime
  10 giornate, k in {2; 3; 4}; conferma entro 10 giornate dal minimo; tenuta
  massima 20 giornate.

Minimo del crollo L = minimo da inizio crollo fino alla conferma (si aggiorna
se il prezzo fa nuovi minimi prima della conferma). Swing high/low = frattali
a 2 barre per lato, **confermati** (noti solo 2 barre dopo).

Conferme (alla CHIUSURA di una barra del TF):
- **C1 rottura di struttura**: chiusura sopra l'ultimo massimo relativo
  (frattale) formatosi dopo l'inizio del crollo.
- **C2 minimo crescente**: dopo L si conferma un minimo frattale > L, poi
  chiusura sopra il massimo fra L e quel minimo.
- **C3 recupero di un livello**: chiusura sopra (a) VWAP giornaliero, (b)
  media esponenziale 20 del TF, (c) 50% del crollo; tre varianti.
- **C4 candela di inversione**: una barra con minimo <= L (spazzata) e
  chiusura nel terzo alto della barra con ombra inferiore >= 2 x corpo
  (martello), oppure engulfing rialzista; entrata se la barra successiva chiude
  sopra il massimo della candela.
- **C5 almeno due conferme** fra C1, C2, C3a, C4 entro la finestra.

Entrata all'apertura della barra successiva alla conferma. **Stop** = L - 0,1
x ATR (1R = distanza entrata-stop; si scarta se 1R > 1,5 x ATR o < 2 x costo).
**Obiettivi**: 1R, 2R, 3R, ritorno al massimo d'inizio crollo; altrimenti
uscita a fine giornata (intraday) o dopo 20 giornate (swing). Una posizione
alla volta per direzione. **Short = specchio esatto** (impennata -> conferma
d'inversione -> vendita).

**Riferimento obbligatorio "senza conferma"**: entrata al primo istante in cui
il crollo raggiunge la soglia k, stesso stop (sotto il minimo successivo:
L corrente - 0,1 x ATR all'entrata) e stessi obiettivi. Misura quanto la
conferma aggiunge.

## Costi

Spread oro 0,46 $ round trip fino al 2019, poi `SPREAD` di `verifica_bot.py` +
0,06 $; anche x1,5. Swap FP (appendice AQ) riscalato sul prezzo, x3 il
mercoledi', per le posizioni oltre le 21:00 UTC.

## Varianti (dichiarate)

2 orizzonti x 2 TF x 3 k x 7 conferme (C1, C2, C3a, C3b, C3c, C4, C5) x 4
obiettivi x 2 lati (long, short) = **672**, piu' i 48 riferimenti "senza
conferma" (2 x 2 x 3 x 4 x 2... riportati, non promossi).

## Promozione (scoperta 2009-2017)

Netto > 0 a x1 e x1,5; **t >= 3** (operazioni non sovrapposte o mensile);
anni positivi >= 7/9; placebo p < 0,01 (stessi istanti con direzione
casuale); **e** netto per operazione migliore del riferimento "senza
conferma" corrispondente. Al massimo 5 candidati.

## Verifica (una volta sola, oro 2018 -> 07/2026)

Soglia di t per k candidati: 2 (k=1), 2,4 (2-3), 2,6 (4-5); netto > 0 a x1 e
x1,5; anni >= 2/3; placebo p < 0,05.

## Previsioni

1. La conferma alza la percentuale di vincite ma abbassa il rapporto
   rischio/rendimento: il netto per operazione resta vicino a quello senza
   conferma.
2. Lo swing fa meglio dell'intraday (costi relativi minori).
3. Al massimo un candidato passa la verifica.
