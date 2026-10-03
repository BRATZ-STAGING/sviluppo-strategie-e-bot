# Famiglia 3 — Forza relativa fra mercati (scoperta 2010-2017)

Protocollo: `docs/multigiorno-paniere-registrazione.md`. Script:
`trading/scripts/multi_f3_forza.py`. Dati: solo
`D:\ricerca_multi\scoperta\PANIERE_D1.parquet` (giornate 22->22 UTC, si usano
solo le giornate `valida`) e `D:\ricerca_multi\costi.csv`. Dettaglio in
`D:\ricerca_multi\risultati\f3_*.parquet`.

## Varianti dichiarate PRIMA del calcolo (04/10/2026)

Regole fisse (non sono dimensioni di ricerca):
- calendario = unione dei giorni validi; segnale sulla chiusura dell'ultimo
  giorno della settimana (W) o del mese (M); esecuzione all'**apertura del
  giorno dopo** (domenica 22:00 UTC per W); uscita/ribilanciamento
  all'apertura del giorno dopo il segnale successivo. Rendimento del periodo
  = apertura -> apertura;
- punteggio = ln(C[t-s] / C[t-L]) / sigma60, con sigma60 = deviazione dei
  rendimenti logaritmici giornalieri degli ultimi 60 giorni validi del
  mercato (causale); L e s in giorni validi del mercato
  (1 settimana = 5, 1 mese = 21, 3 = 63, 6 = 126, 12 = 252);
- mercato disponibile se ha punteggio, sigma60 e apertura nei due istanti di
  esecuzione; periodo saltato se i disponibili sono meno di 2k (cosi' i primi
  e gli ultimi non si sovrappongono, anche nelle varianti solo long/solo
  short);
- **rischio uguale**: 1 R = 2 x deviazione delle variazioni giornaliere di
  prezzo (60 giorni validi) alla data del segnale di entrata; ogni posizione
  vale 1 R di rischio;
- un mercato che resta dalla stessa parte al ribilanciamento **resta aperto**
  (nessun costo, dimensione d'entrata invariata); entrata nuova o inversione =
  un'operazione con costo round trip (`costi.csv`; oro 0,46 $ = base
  2009-2019) caricato all'entrata; ogni regola anche con costi x1,5;
- swap per ogni notte (fine di ogni giorno di calendario tenuto, x3 il
  mercoledi'): 3% annuo / 365 del nominale, long e short, per cambi, argento,
  indici; oro long -0,715 e short +0,325 $/oncia/notte riscalati con
  prezzo / 4.156,98; swap invariato a costi x1,5;
- misura: somma in R del portafoglio per mese (mese dell'esecuzione); t sui
  mesi dal primo ribilanciamento a dic 2017; anni positivi sugli anni con
  dati (al massimo 8; con L = 12 mesi sono 7);
- placebo: a ogni ribilanciamento classifica casuale fra gli stessi mercati
  disponibili, stesso k e stessa modalita', stessa regola di tenuta; 1000
  serie, seed 12345 + indice della variante. Statistica: R totale **al lordo
  dei costi di transazione (swap incluso)**, perche' le classifiche casuali
  girano molto piu' spesso e pagherebbero piu' costi (sul netto il placebo
  sarebbe troppo facile). p = (1 + #placebo >= reale) / 1001.

Griglia:
- universo: TUTTI (12 mercati, k = 2, 3), CAMBI (7 coppie, k = 2, 3),
  MI = metalli + indici (oro, argento, S&P, Nasdaq, DAX: 5 mercati, k = 1, 2,
  perche' 2 x 3 > 5);
- ribilanciamento: W, M;
- finestra/salto (9): 1s/0, 1m/0, 1m/1s, 3m/0, 3m/1m, 6m/0, 6m/1m, 12m/0,
  12m/1m;
- modalita' MOMENTUM (tutte le 9 finestre): LS (long primi k, short ultimi
  k), L (solo long primi), S (solo short ultimi);
- modalita' CONTRO (solo 1s/0, 1m/0, 1m/1s): LS (long ultimi, short primi),
  L (long ultimi), S (short primi);
- per universo: 2 ribil. x 2 k x (9 x 3 + 3 x 3) = 144; **totale 3 x 144 =
  432 varianti**, tutte candidabili.

Promozione (regole da griglia): netto > 0 a x1 e x1,5; t >= 3 sui mesi;
anni positivi >= 6; p placebo < 0,01. Al massimo 3 candidati, in ordine di t.

## Risultati (04/10/2026)

Controlli: motore vettoriale confrontato con un ciclo periodo per periodo
indipendente (tenuta, costi all'entrata, swap con mercoledi' x3, oro
asimmetrico) su 3 varianti (TUTTI W 1m CONTRO-LS k3, TUTTI M 12m/1m MOM-LS
k2, MI M 3m MOM-L k1): R netto e numero di entrate identici (differenza 0).
Periodi: 417 settimane, 96 mesi; con L = 12 mesi i mesi valutati sono 84
(7 anni). Indici e DAX entrano dal 2011 (dati da 11/2010 + finestra).
Tempo di calcolo 127 s (432 varianti x 1000 placebo).

**Varianti provate: 432**, tutte valutate. Netto > 0 a x1 e x1,5: 121;
**t >= 3: 0** (t >= 2: 0; massimo 1,93); t <= -2: 40; anni >= 6: 31;
p < 0,01: 35. **Tutti i criteri insieme: 0. Candidati: nessuno.**

| universo | tipo | n | netto > 0 | t mediano | t max | t min | p < 0,01 | p < 0,05 |
|---|---|---|---|---|---|---|---|---|
| TUTTI | MOM | 108 | 45 | -0,23 | 1,30 | -3,08 | 9 | 28 |
| TUTTI | CONTRO | 36 | 4 | -1,07 | 0,70 | -2,90 | 0 | 0 |
| CAMBI | MOM | 108 | 5 | -0,59 | 0,43 | -3,06 | 0 | 9 |
| CAMBI | CONTRO | 36 | 0 | -1,46 | -0,24 | -2,98 | 0 | 0 |
| MI | MOM | 108 | 64 | 0,36 | 1,93 | -2,29 | 26 | 48 |
| MI | CONTRO | 36 | 10 | -0,86 | 1,15 | -2,61 | 0 | 0 |

t mediano per modalita': MOM L / LS / S = TUTTI 0,44 / -0,20 / -0,99;
CAMBI -0,28 / -0,65 / -0,72; MI 1,23 / 0,57 / -0,92. CONTRO LS / S sempre
negativi (mediane da -1,1 a -2,0). Per finestra (MOM-LS, t mediano TUTTI /
CAMBI / MI): 1s -1,93 / -2,61 / -0,09; 1m -1,08 / -0,72 / -0,52; 6m 0,67 /
-0,69 / 1,27; 12m/1m 0,04 / -0,42 / 1,35.

### Migliori per t (nessuna passa)

pos = posizioni aperte in media; ent/mese = entrate (cambi di posizione) al
mese; netto/op = netto in R per posizione aperta; prezzo = R dal solo
movimento dei prezzi; swap e costi = R totali (negativi = pagati).

| regola | pos | ent/mese | netto/op | netto R | x1,5 R | prezzo R | swap R | costi R | t | anni + | DD R | p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MI M 3m/0 MOM-L k1 | 1 | 0,46 | 1,44 | 60,5 | 60,0 | 78,3 | -16,8 | 1,0 | 1,93 | 7/8 | 10,6 | 0,017 |
| MI M 6m/1m MOM-L k1 | 1 | 0,32 | 2,27 | 65,9 | 65,6 | 83,8 | -17,2 | 0,7 | 1,84 | 7/8 | 19,2 | 0,008 |
| MI M 6m/1m MOM-L k2 | 2 | 0,47 | 2,24 | 82,8 | 82,4 | 111,8 | -28,3 | 0,8 | 1,82 | 5/7 | 15,8 | 0,001 |
| MI M 6m/0 MOM-L k1 | 1 | 0,29 | 2,49 | 64,6 | 64,3 | 83,5 | -18,2 | 0,6 | 1,81 | 7/8 | 15,3 | 0,014 |
| MI M 12m/1m MOM-L k2 | 2 | 0,45 | 2,14 | 70,6 | 70,3 | 98,0 | -26,7 | 0,7 | 1,79 | 5/7 | 16,4 | 0,003 |
| TUTTI M 6m/0 MOM-L k3 | 3 | 0,90 | 1,06 | 85,9 | 85,2 | 149,8 | -62,7 | 1,2 | 1,30 | 4/8 | 34,3 | 0,005 |
| TUTTI M 6m/0 MOM-LS k2 | 4 | 1,48 | 0,54 | 71,8 | 70,7 | 149,9 | -76,0 | 2,1 | 0,91 | 6/8 | 76,4 | 0,002 |
| CAMBI M 1m/1s MOM-L k2 | 2 | 1,38 | 0,16 | 20,3 | 19,7 | 66,1 | -44,6 | 1,2 | 0,43 | 4/8 | 28,3 | 0,032 |
| MI W 1m/1s CONTRO-L k2 | 2 | 2,58 | 0,22 | 47,3 | 44,8 | 78,2 | -26,1 | 4,9 | 1,15 | 4/7 | 48,4 | 0,055 |

Le regole "da manuale" (long/short, 12 mesi saltando l'ultimo, mensile):

| regola | pos | ent/mese | netto R | prezzo R | swap R | t | anni + | DD R | p |
|---|---|---|---|---|---|---|---|---|---|
| TUTTI M 12m/1m MOM-LS k3 | 6 | 1,38 | -13,7 | 77,2 | -89,2 | -0,16 | 4/7 | 63,6 | 0,062 |
| TUTTI M 12m/1m MOM-LS k2 | 4 | 1,41 | 26,9 | 91,7 | -62,8 | 0,38 | 4/7 | 59,7 | 0,018 |
| CAMBI M 12m/1m MOM-LS k2 | 4 | 1,04 | -30,7 | 52,2 | -82,1 | -0,43 | 2/7 | 60,8 | 0,159 |
| MI M 12m/1m MOM-LS k1 | 2 | 0,57 | 38,8 | 57,6 | -17,8 | 1,27 | 6/7 | 25,9 | 0,014 |
| TUTTI W 1s/0 CONTRO-LS k3 | 6 | 18,7 | -118,0 | 13,8 | -107,5 | -1,66 | 1/8 | 147,3 | 0,464 |
| CAMBI W 1s/0 CONTRO-LS k2 | 4 | 12,2 | -50,2 | 48,5 | -88,3 | -0,81 | 4/8 | 105,0 | 0,192 |

Le peggiori: TUTTI M 1s/0 MOM-S k3 t -3,08 (1/8 anni), CAMBI W 1s/0 MOM-LS
k3 t -3,06, CAMBI M 1m/1s CONTRO-LS k3 t -2,98: lo short perde in quasi
tutte le combinazioni (prezzi in salita su indici 2011-2017 + swap).

### Senza l'oro (diagnostica, stesse regole)

| regola | t con oro | netto con | t senza | netto senza | anni + senza |
|---|---|---|---|---|---|
| MI M 3m/0 MOM-L k1 | 1,93 | 60,5 | 0,93 | 23,0 | 4 |
| MI M 6m/1m MOM-L k1 | 1,84 | 65,9 | 1,87 | 42,7 | 5 |
| MI M 6m/1m MOM-L k2 | 1,82 | 82,8 | 1,66 | 67,2 | 5 |
| TUTTI M 6m/0 MOM-L k3 | 1,30 | 85,9 | 1,01 | 62,0 | 4 |

Contributo per mercato (netto R) di TUTTI M 6m/0 MOM-L k3: Nasdaq 25,8,
USDJPY 21,5, argento 16,8, oro 16,1, S&P 14,0, DAX 9,7; cambi esclusi USDJPY
ed EURJPY tutti negativi (da -0,8 a -7,8).

### Osservazioni

1. **Nessun candidato**: il t massimo e' 1,93 su 432 varianti (soglia 3).
   Il placebo da' p < 0,01 a 35 varianti, quasi tutte su MI: la classifica
   batte la scelta casuale, ma il guadagno non e' abbastanza regolare nel
   tempo (t < 2). Su MI il placebo stesso e' positivo (long a caso su indici
   in salita = +17/+27 R): buona parte del risultato e' la deriva rialzista
   2011-2017, non la forza relativa.
2. **Lo swap decide sui cambi**: con il 3% annuo su entrambi i lati e R = 2
   deviazioni giornaliere, ogni posizione su un cambio paga ~0,2 R al mese.
   Il momentum LS sui cambi e' positivo sul prezzo (12m/1m k2 +52 R) ma lo
   swap (-82 R) lo rende negativo; i costi di transazione sono trascurabili
   (1-2 R in 8 anni a frequenza mensile, x1,5 cambia poco).
3. **Il "contro" trasversale non esiste qui** (CONTRO-LS e -S sempre a t < 0;
   1 settimana CONTRO-LS t -1,7 su TUTTI); il momentum a 1 settimana e' il
   peggiore (CAMBI LS t -2,6): a orizzonti brevi la classifica non contiene
   informazione e il ribilanciamento settimanale moltiplica swap e costi.
   La previsione 1 del protocollo (positivo al lordo, t fra 1 e 2) vale anche
   per il momentum trasversale sui metalli e indici; sui cambi no.

File: `f3_varianti.parquet` (432 righe, tutte le misure e p),
`f3_mensili.parquet` (R netto mensile per variante), `f3_senza_oro.parquet`
in `D:\ricerca_multi\risultati\`.
