# Intraday cambi — candidati congelati per la verifica (03/10/2026)

Scritto **prima** di aprire `D:\ricerca_fx\verifica\` (2018 -> 09/2026).
Protocollo: `docs/fx-intraday-registrazione.md` (commit 1c40ac5).

## Scoperta 2010-2017: varianti provate

| famiglia | varianti | candidati |
|---|---|---|
| A notte asiatica (`fx_a_notte.py`) | 4.050 regole x 7 coppie | **1** |
| B aperture di sessione (`fx_b_aperture.py`) | 7.560 | 0 |
| C media/momentum 5-60' (`fx_c_media_momentum.py`) | 15.056 | 0 |
| D orari fissi (`fx_d_orari_fissi.py`) | 4.722 | 0 |

**k = 1 candidato -> soglia di verifica t >= 2** (tabella del protocollo).

## C1 — Rientro notturno dopo una sessione USA agitata

Specifica = codice di `trading/scripts/fx_a_notte.py`, invariato.

- **Coppie**: EURUSD, GBPUSD, USDCHF (M5 BID, UTC). Una posizione alla volta
  per coppia.
- **ATRd**: media del true range dei 14 giorni validi (lun-ven, >= 600
  minuti) conclusi prima del giorno in cui inizia la notte.
- **Filtro**: si opera la notte solo se il range 13:00-20:45 UTC dell'ultimo
  giorno feriale, diviso ATRd, e' nel **terzile alto** delle 250 notti
  precedenti della coppia (servono almeno 60 valori).
- **Segnale**: alla chiusura di ogni M5 dalle 23:55 alle 05:20 UTC: se
  chiusura - media delle ultime 48 chiusure M5 > 0,10 x ATRd -> vendi; se
  < -0,10 x ATRd -> compra; entrata all'apertura della M5 successiva.
- **Obiettivo**: limite al valore della media della candela del segnale; il
  segnale si scarta se all'entrata la distanza dall'obiettivo e' sotto un
  costo.
- **Stop**: 0,10 x ATRd. Stop e obiettivo nella stessa candela -> stop;
  apertura oltre lo stop -> uscita all'apertura.
- **Uscita forzata**: chiusura della M5 delle 05:55 UTC.
- **Costi**: 0,8 / 1,0 / 1,0 pip (x1) e x1,5; nessuno swap.

Scoperta: 3.619 operazioni (1,76/giorno), +0,742 pip/op a x1, +0,277 a x1,5,
t 3,00, 8/8 anni (6/8 a x1,5), placebo p 0,001; peggiore serie 21 perdite
(-419 pip), drawdown 420 pip.

## Criterio di verifica

Passa se valgono tutte: netto > 0 a costi x1 **e** x1,5; t >= 2 sul netto
(stesso metodo della scoperta: somme per notte); anni positivi >= 2/3;
placebo p < 0,01; frequenza >= 1 operazione per giornata di borsa.

## Previsioni

1. C1 non passa (concentrato su EURUSD e sull'ora 00:00-01:00, al limite
   della soglia, fragile ai costi).
2. Se passa a x1, cade a x1,5.
