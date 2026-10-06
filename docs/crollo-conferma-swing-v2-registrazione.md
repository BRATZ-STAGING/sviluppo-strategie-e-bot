# Crollo -> conferma -> entrata, SWING versione 2 — registrazione (06/10/2026)

Decisione dell'utente del 06/10/2026. **Correzione dichiarata DOPO aver visto
i risultati** della versione 1 (`docs/crollo-conferma-registrazione.md`,
rapporto `docs/studies/conferme/scoperta.md`): il vincolo "1R <= 1,5 x ATR"
scartava quasi tutte le operazioni swing (su D1 la conferma arriva in media
2,3-2,8 ATR sopra il minimo L; C1 su D1 passava 3 volte su 229 segnali), cioe'
la parte con il segnale migliore (vincite 35% contro 29% senza conferma) e'
stata misurata su pochissimi casi. Poiche' la scoperta 2009-2017 dello swing
e' gia' stata vista, le soglie di promozione si alzano (sotto).

## Cosa resta identico alla versione 1

Motore `trading/framework/crollo_conferma.py` (stessi crolli, minimo L,
frattali confermati, conferme C1, C2, C3a/b/c, C4, C5, entrate, obiettivi
1R/2R/3R/ritorno al massimo d'inizio crollo, tenuta massima 20 giornate, costi,
swap, riferimento "senza conferma", short = specchio). Solo swing: TF **H4 e
D1**, k in {2; 3; 4} ATR in 10 giornate.

## Cosa cambia: lo stop (tre varianti, nessun tetto alla distanza)

- **S1** sotto il minimo del crollo: L - 0,1 x ATR, senza il limite 1R <= 1,5
  ATR (si scarta solo se 1R < 2 x costo).
- **S2** sotto l'ultimo minimo crescente: ultimo minimo frattale confermato
  dopo L e sopra L, meno 0,1 x ATR; se non esiste, come S1.
- **S3** stop fisso a 1,5 x ATR dal prezzo d'entrata.

Varianti: 2 TF x 3 k x 7 conferme x 3 stop x 4 obiettivi x 2 lati = **1.008**.

## Promozione (scoperta oro 2009-2017) — piu' severa della v1

Netto > 0 a x1 e x1,5 (R e $); **t >= 3**; anni positivi >= 7/9; **positivo
in entrambe le meta' 2009-2012 e 2013-2017**; placebo p < 0,01; netto migliore
del riferimento senza conferma a x1 e x1,5; **almeno 40 operazioni**. Al
massimo 5 candidati.

## Verifica (una volta sola)

1. **Oro 2018 -> 07/2026** (decide il verdetto). Soglia t per k candidati: 2
   (k=1), 2,4 (2-3), 2,6 (4-5); netto > 0 a x1 e x1,5; anni >= 2/3; placebo
   p < 0,05.
2. **Trasferimento** (rafforza o indebolisce): argento, S&P 500, EUR/USD,
   HistData **2010 -> 09/2026 intero** (per questa famiglia mai visti), VWAP a
   peso uniforme (senza volume), costi dei rispettivi protocolli (argento
   0,025 $, S&P 0,55, EUR/USD 0,8 pip; swap 3% annuo per S&P/argento/EURUSD).

## Previsioni

1. Con lo stop libero le operazioni swing salgono a 50-150 per variante.
2. Nessun candidato raggiunge t 3 (operazioni ancora poche, effetto piccolo).
3. Se ce n'e' uno, non passa la verifica.
