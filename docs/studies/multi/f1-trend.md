# Famiglia 1 — Trend following sul paniere, regole canoniche (scoperta 2010-2017)

Protocollo: `docs/multigiorno-paniere-registrazione.md`. Script:
`trading/scripts/multi_f1_trend.py`. Dati: solo
`D:\ricerca_multi\scoperta\PANIERE_D1.parquet` (giornate 22->22 UTC, quelle
con `valida = False` saltate) e `D:\ricerca_multi\costi.csv`. Dettaglio:
`D:\ricerca_multi\risultati\f1_*.parquet`. Nessun dato intraday usato.

## Regole dichiarate PRIMA del calcolo (04/10/2026)

Regole fisse (non sono dimensioni di ricerca):
- decisione alla **chiusura** D1, esecuzione all'**apertura** della giornata
  valida successiva; una posizione per mercato e per regola, niente
  piramidazione; rischio uguale per mercato: ogni operazione vale 1R;
- stop (dove previsto) fisso dall'entrata, toccato dentro la giornata ed
  eseguito al livello; se l'apertura lo supera, all'apertura;
- ATR20 = media del true range delle 20 giornate valide fino a quella della
  decisione compresa; sigma60 = deviazione standard delle ultime 60 variazioni
  di chiusura (in unita' di prezzo) fino alla decisione;
- operazioni con entrata dal 01/01/2010 (l'oro 2009 serve solo a scaldare gli
  indicatori); le posizioni aperte al 29/12/2017 si chiudono a quella
  chiusura; indici dal 15/11/2010 (inizio dei loro dati);
- costi: round trip di `costi.csv` per operazione (ogni ribilanciamento
  mensile e' un'operazione nuova, anche se il verso non cambia), meta' sul
  giorno di entrata e meta' su quello di uscita; misura anche con costi x1,5;
- swap per ogni notte tenuta (fine di ogni giorno lun-ven del calendario fra
  entrata compresa e uscita esclusa, x3 il mercoledi'; prezzo = ultima
  chiusura valida): 3%/365 del nominale long e short per cambi, argento,
  indici; oro -0,715 $ long / +0,325 $ short per oncia e notte riscalati per
  prezzo / 4.156,98 (lo short sull'oro incassa);
- R del portafoglio contabilizzato giorno per giorno (mark-to-market sulle
  chiusure), sommato per mese: t sui 96 mesi 2010-2017 meno quelli prima
  della prima posizione della regola; drawdown in R sulla curva giornaliera;
  anni positivi = anni solari con R netto > 0 (su 8, o 7 se la regola parte
  nel 2011);
- placebo: stesse entrate, stesse uscite (istante e prezzo), direzione a caso
  (p = 0,5) per ogni operazione, stessi costi, swap secondo il verso estratto;
  2000 serie, seed 12345; p = (1 + #placebo con R netto totale >= reale) /
  2001;
- tutto anche **senza l'oro** (11 mercati), con un placebo proprio.

Le 7 regole (parametri canonici, nessuna griglia):

| # | regola | segnale | uscita | 1R |
|---|---|---|---|---|
| 1 | TSMOM 1 | ultima chiusura del mese: segno del rendimento dell'ultimo mese (chiusura di fine mese contro quella di fine mese precedente) | apertura dopo la chiusura di fine mese successiva (nuova operazione) | 2 x sigma60 (**dimensionamento a volatilita' 60 giorni**, nessuno stop) |
| 2 | TSMOM 3 | come 1 con 3 mesi | idem | idem |
| 3 | TSMOM 12 | come 1 con 12 mesi | idem | idem |
| 4 | Donchian 20/10 | chiusura > massimo dei 20 massimi precedenti (long) / < minimo dei 20 minimi (short) | chiusura sotto il minimo dei 10 minimi precedenti (long) / sopra il massimo dei 10 (short), oppure stop | stop 2 x ATR20 |
| 5 | Donchian 55/20 | come 4 con 55 | come 4 con 20 | stop 2 x ATR20 |
| 6 | Medie 50/200 sempre a mercato | verso = segno(SMA50 - SMA200) delle chiusure; al cambio si inverte | inversione | nominale 2 x ATR20 alla decisione, **nessuno stop** |
| 7 | Medie 50/200 con stop | incrocio di SMA50 su SMA200 (come appendice CD, F3) | incrocio opposto (che apre l'inverso) o stop; dopo lo stop si aspetta l'incrocio successivo | stop 2 x ATR20 |

Nei Donchian, se nella stessa chiusura scatta l'uscita e il segnale opposto,
si esce e si entra nel verso opposto alla stessa apertura; dopo uno stop si
rientra solo con un nuovo segnale di chiusura.

Promozione (protocollo, regole canoniche): netto > 0 a costi x1 e x1,5,
t >= 2 sui rendimenti mensili, anni positivi >= 5, placebo p < 0,05, sul
portafoglio di 12 mercati; il risultato senza l'oro si riporta accanto e, se
li' la regola non passa, il candidato e' segnalato "con riserva". Al massimo
3 candidati, in ordine di t.

## Risultati (04/10/2026)

Controlli: contabilita' giornaliera = somma delle operazioni (asserzione nel
codice, scarto < 1e-6); stop pieni a esattamente -1,000 R lordo; 240
operazioni estratte a caso ricontrollate a mano su un'altra strada (segnale
Donchian sulla chiusura del giorno prima, entrata all'apertura, segno TSMOM
dai fine mese): 0 errori; swap ricalcolato a parte su TSMOM 1 EURUSD:
rapporto 1,001. Prime entrate: cambi e argento 05/02/2010, indici 22/12/2010,
oro 04/01/2010.

**Regole provate: 7, tutte sul paniere di 12 mercati e su quello senza oro.
Candidati: nessuno.** Nessuna regola ha nemmeno il netto > 0 con t >= 1.

### Portafoglio, 12 mercati (R netto con swap; "senza swap" = solo diagnostica)

| regola | n | op/mese | lordo R | costi R | swap R | netto R | netto/op | netto x1,5 | t mensile | anni + | DD R | p placebo | senza swap R / t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TSMOM 1 | 1086 | 11,3 | -8,5 | 15,9 | 206,8 | **-231,2** | -0,213 | -239,2 | -1,96 | 1/8 | 277,9 | 0,549 | -24,5 / -0,21 |
| TSMOM 3 | 1077 | 11,2 | +100,2 | 15,8 | 205,9 | **-121,6** | -0,113 | -129,5 | -0,94 | 4/8 | 202,9 | 0,132 | +84,3 / 0,65 |
| TSMOM 12 | 978 | 10,3 | +168,6 | 14,6 | 191,4 | **-37,3** | -0,038 | -44,6 | -0,31 | 4/8 | 125,0 | **0,020** | +154,1 / 1,27 |
| Donchian 20/10 | 798 | 8,3 | -4,5 | 7,7 | 93,4 | **-105,5** | -0,132 | -109,4 | -1,37 | 2/8 | 118,9 | 0,543 | -12,1 / -0,16 |
| Donchian 55/20 | 402 | 4,2 | +29,3 | 4,0 | 74,1 | **-48,9** | -0,122 | -50,9 | -0,71 | 3/8 | 77,0 | 0,263 | +25,3 / 0,36 |
| Medie 50/200 sempre | 137 | 1,4 | +89,9 | 1,2 | 131,1 | **-42,4** | -0,310 | -43,0 | -0,47 | 2/8 | 105,9 | 0,075 | +88,7 / 0,98 |
| Medie 50/200 con stop | 125 | 1,4 | +69,4 | 1,2 | 58,8 | **+9,5** | +0,076 | +8,9 | 0,18 | 3/8 | 69,2 | 0,074 | +68,3 / 1,30 |

### Portafoglio senza l'oro (11 mercati)

| regola | n | netto R | netto x1,5 | t | anni + | DD R | p | senza swap R / t |
|---|---|---|---|---|---|---|---|---|
| TSMOM 1 | 990 | -212,4 | -219,4 | -1,93 | 1/8 | 254,5 | 0,522 | -14,6 / -0,13 |
| TSMOM 3 | 981 | -105,8 | -112,8 | -0,89 | 4/8 | 167,0 | 0,095 | +90,4 / 0,76 |
| TSMOM 12 | 883 | -48,9 | -55,3 | -0,44 | 3/7 | 119,4 | 0,024 | +133,0 / 1,19 |
| Donchian 20/10 | 732 | -104,9 | -108,3 | -1,47 | 2/8 | 117,5 | 0,573 | -15,3 / -0,21 |
| Donchian 55/20 | 365 | -46,5 | -48,3 | -0,74 | 3/8 | 75,4 | 0,261 | +24,3 / 0,38 |
| Medie 50/200 sempre | 124 | -38,5 | -39,0 | -0,47 | 3/8 | 100,5 | 0,092 | +86,9 / 1,05 |
| Medie 50/200 con stop | 113 | +21,8 | +21,3 | 0,43 | 3/8 | 65,6 | 0,048 | +79,5 / 1,54 |

Placebo (2000 serie): mediana del netto fra -60 e -221 R secondo la regola
(una direzione a caso paga tutti i costi e tutto lo swap senza vantaggio).
"Sempre long negli stessi istanti" (riferimento): fra -6,5 e -55,8 R.

### Anni (R netto, 12 mercati)

| regola | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 |
|---|---|---|---|---|---|---|---|---|
| TSMOM 1 | -33,2 | -18,8 | -21,7 | +21,5 | -44,4 | -84,3 | -46,0 | -4,5 |
| TSMOM 3 | +32,7 | +26,6 | -98,4 | +73,6 | +0,5 | -81,0 | -25,9 | -49,7 |
| TSMOM 12 | +12,0 | -17,5 | -55,0 | +94,8 | -10,7 | +35,2 | -96,7 | +0,6 |
| Donchian 20/10 | +4,4 | -20,6 | +7,4 | -5,7 | -6,2 | -23,5 | -45,1 | -16,2 |
| Donchian 55/20 | +7,7 | -31,3 | -3,1 | +21,6 | +13,1 | -36,2 | -10,6 | -10,0 |
| Medie 50/200 sempre | +12,7 | -5,9 | -51,5 | +51,4 | -1,3 | -5,9 | -23,4 | -18,5 |
| Medie 50/200 con stop | -1,1 | +1,5 | -19,0 | +52,9 | +24,3 | -19,0 | -15,2 | -14,9 |

(TSMOM 12 nel 2010 ha solo l'oro: senza oro parte nel 2011.)

### Contributo per mercato (R netto con swap, costi x1)

| mercato | TSMOM 1 | TSMOM 3 | TSMOM 12 | Don 20/10 | Don 55/20 | MA sempre | MA stop |
|---|---|---|---|---|---|---|---|
| AUDUSD | -49,5 | -52,9 | -8,9 | -1,7 | -3,3 | -28,1 | -8,4 |
| EURJPY | +15,4 | +7,0 | +8,6 | -4,0 | -2,3 | -15,1 | -0,2 |
| EURUSD | -7,6 | +8,7 | -21,9 | -7,8 | +8,7 | -0,8 | +12,6 |
| GBPUSD | -49,0 | -15,8 | -44,1 | -19,0 | -16,7 | -16,3 | +1,0 |
| GRXEUR | -13,4 | -1,1 | +10,0 | -8,0 | -5,2 | +7,3 | +2,6 |
| NSXUSD | -25,5 | +10,2 | +39,2 | -18,4 | -3,7 | +15,7 | +22,0 |
| SPXUSD | -3,6 | +4,3 | +26,8 | -16,1 | -7,6 | +17,5 | -5,7 |
| USDCAD | -24,7 | -37,1 | -18,3 | -8,5 | -11,6 | -22,6 | -4,4 |
| USDCHF | -30,7 | -5,3 | -37,6 | -22,5 | -12,8 | -4,3 | -11,9 |
| USDJPY | -17,3 | +9,0 | +24,7 | -13,8 | +8,7 | -3,7 | +10,0 |
| XAGUSD | -6,5 | -33,0 | -27,3 | +15,0 | -0,9 | +11,9 | +4,0 |
| XAUUSD | -18,9 | -15,8 | +11,6 | -0,6 | -2,3 | -4,0 | -12,3 |

t mensile per mercato: l'unico |t| >= 2 positivo e' NSXUSD in TSMOM 12
(+2,16); negativi oltre -2 AUDUSD (TSMOM 3), GBPUSD (TSMOM 1), XAUUSD (MA con
stop). Swap per mercato: 7-25 R nelle TSMOM (circa 0,2 R al mese per
posizione: 3% annuo contro un R di 2 sigma60, cioe' ~1-1,5% del prezzo nei
cambi).

### Osservazioni

1. **Lo swap prudente del protocollo decide tutto.** Senza swap (solo costi
   di transazione) cinque regole su sette sono positive (TSMOM 12 +154 R,
   medie +69/+89, TSMOM 3 +84), ma con il 3% annuo pagato su entrambi i lati
   il trend lento, che tiene sempre 12 posizioni, paga 190-207 R di swap in
   8 anni e diventa negativo. I costi di transazione sono irrilevanti
   (x1,5 sposta il netto di 1-8 R).
2. **Anche senza swap il t non arriva a 2** (massimo 1,30 con l'oro, 1,54
   senza, medie con stop): previsione 1 del protocollo confermata (lordo
   positivo, t fra 1 e 2 con 12 mercati). Le regole veloci (TSMOM 1, Donchian
   20/10) sono negative gia' al lordo: nel 2010-2017 il paniere non ha trend
   di un mese/quattro settimane sfruttabili.
3. **La direzione di TSMOM 12 batte il caso (p 0,020; 0,024 senza oro)**, ma
   il vantaggio sulla direzione (+167 R sopra la mediana placebo) non copre lo
   swap. Il risultato e' concentrato in due anni (2013 +94,8, 2015 +35,2) e in
   pochi mercati (Nasdaq, S&P, USDJPY: il trend degli indici e dello yen
   2012-2015); i cambi con il dollaro (GBP, CHF, CAD, AUD) perdono in quasi
   tutte le regole. L'oro non cambia il quadro (senza oro i netti si muovono
   fra -12 e +19 R); le medie con stop sono anzi migliori senza (+21,8 R, p 0,048,
   ma t 0,43 e 3/8 anni).

**Verdetto: famiglia 1 chiusa in scoperta, nessun candidato per la
verifica 2018-2026.**
