# Walk-forward dal 2009 sulle famiglie da zero dell'oro (03/10/2026)

Protocollo vincolante: `docs/walkforward-registrazione.md` (commit 4cdfcca;
conteggio dell'universo in 66ca0f4, scritto prima dei calcoli). Script:
`trading/scripts/zero_walkforward.py` (un comando: `python
trading/scripts/zero_walkforward.py tutto`, ~2 min; importa le funzioni degli
script `zero_f1..f5` senza modificarli). Dettaglio: `D:\ricerca_zero\walkforward\`.

**Esito: il metodo di scelta NON funziona, ne' con la regola P ne' con la S.**
P (soglie di promozione della scoperta, riapplicate ogni 1 gennaio) non trova
nulla in 7 anni su 15 e dove opera perde: 433 operazioni, −0,025% per
operazione, t −0,80, 3 anni positivi su 8, placebo p 0,47. S (le 5 migliori
per t, sempre operativa) e' positiva (+0,034%, t 2,43, placebo 0,001) ma con
9 anni positivi su 15 (0,60 < 2/3) e vive del 2025: senza quell'anno t 1,00;
nel 2012-2017 t 0,38. Dal 2020 sceglie quasi solo finestre long di fine mese:
e' la deriva rialzista dell'oro, non una regola.

## 1. Universo e dati

| famiglia | varianti oro | con operazioni 2009-2026 | soglia n (P) |
|---|---|---|---|
| F1 orologio (R1 48, R2 6, R4a 36, R4c 4, R5 30) | 124 | 124 | 100 |
| F2 momentum (33 celle consistenti x 12) | 396 | 381 | 200 (100 se L o H >= 1g) |
| F3 range (a 216, b 216) | 432 | 432 | 100 |
| F4 volatilita' (a 56, b 32, c 16) | 104 | 104 | 100 |
| F5 calendario (a 10, b 38, c 10) | 58 | 58 | 100 |
| **totale** | **1114** | 1099 | |

Dati: M5/M15/H1/D1 dell'oro 2009-01-01 -> 2026-07-06 (1.255.497 M5), serie
unica `scoperta` + `verifica` in `D:\ricerca_zero\walkforward\dati\`;
indicatori causali sulla serie intera. Costo round trip per anno d'ingresso:
0,40 $ fino al 2019, poi `SPREAD` di `verifica_bot.py` (0,334-0,632). Netto in
% del prezzo d'ingresso per tutte le famiglie: 2.004.608 operazioni in
`operazioni_f*.parquet`.

### Controllo di riproduzione (obbligatorio)

Lo stesso codice sulla sola cartella `scoperta\` con costo 0,40 ridà **tutte e
1114 le varianti** con n e netto identici (differenza 0) ai parquet di
scoperta `f1_varianti`, `f2_faseb`, `f3_varianti`, `f4_varianti`,
`f5_varianti` (unita' di ogni script: prezzo, prezzo, R, R, prezzo); per F2 la
selezione copiata coincide con `f2.regola` su tutte le 396 regole
(`riproduzione.parquet`). Sulla serie continua, le operazioni 2009-2017
coincidono per 1046 varianti; 68 (F2 12, F4 8, F5 48) hanno **esattamente +1
operazione**, tutte ancorate nell'ultima settimana del 2017 e possibili solo
con i dati di gennaio 2018 (uscita nel 2018, o esistenza del giorno/mese
successivo per le finestre WF2 e TOM j0 di F5). Nessun'altra differenza
(`confronto_2009_2017.parquet`).

## 2. Scelte anno per anno

Storia = operazioni con ingresso prima del 1 gennaio di Y. P: netto > 0,
t >= 3, anni positivi >= 75% degli anni con >= 10 operazioni, n >= soglia,
max 3 per famiglia e 10 in tutto. S: le 5 con t piu' alto fra netto > 0 e
n >= 100. Risultato dell'anno = media del netto % su tutte le operazioni
delle varianti scelte (t sull'anno fra parentesi dove n >= 2).

| Y | P: varianti scelte (t storia) | n | netto % | S: famiglie delle 5 scelte (t storia min-max) | n | netto % | oro B&H % |
|---|---|---|---|---|---|---|---|
| 2012 | F5 WM2 long (3,01) | 53 | +0,048 (1,3) | F5 x3, F1, F4 (2,31-3,01) | 318 | +0,033 (1,1) | +7,0 |
| 2013 | F5 WM2 long (3,29) | 52 | −0,041 (−0,8) | F5 x3, F1, F3 (2,01-3,29) | 515 | −0,000 (0,0) | −28,0 |
| 2014 | F1 Asia 60m inverti solo long (3,13), F5 WF2 long (3,03) | 175 | −0,018 (−0,8) | F1 x2, F5 x2, F4 (1,94-3,13) | 393 | +0,002 (0,1) | −1,8 |
| 2015 | nessuna | 0 | 0 | F1 x2, F5, F4 x2 (2,39-2,89) | 385 | +0,027 (1,3) | −10,4 |
| 2016 | F5 WF2 long (3,08) | 52 | +0,039 (1,0) | F1 x2, F5, F4 x2 (2,46-3,08) | 363 | +0,014 (0,5) | +8,4 |
| 2017 | F5 WF2 long (3,21) | 52 | −0,043 (−2,4) | F1 x2, F5, F4 x2 (2,39-3,21) | 401 | −0,044 (−3,4) | +13,2 |
| 2018 | nessuna | 0 | 0 | F5 x2, F1, F4 x2 (2,31-2,63) | 275 | −0,053 (−2,4) | −1,6 |
| 2019 | nessuna | 0 | 0 | F5 x2, F4 x3 (2,07-2,51) | 168 | +0,060 (1,2) | +18,3 |
| 2020 | nessuna | 0 | 0 | F4 x2, F5 x3 (2,30-2,49) | 140 | +0,161 (1,4) | +25,1 |
| 2021 | nessuna | 0 | 0 | F4, F5 TOM x4 (2,51-2,90) | 68 | −0,064 (−0,3) | −3,6 |
| 2022 | nessuna | 0 | 0 | F4 x2, F5 TOM x3 (2,48-2,97) | 54 | +0,436 (2,0) | −0,3 |
| 2023 | F4 R50 S2 X1 (3,04) | 14 | −0,068 (−0,7) | F4, F5 TOM x4 (2,68-3,04) | 62 | −0,187 (−1,2) | +13,1 |
| 2024 | nessuna | 0 | 0 | F4 x2, F5 TOM x3 (2,54-2,93) | 58 | +0,380 (1,9) | +27,2 |
| 2025 | F4 R50 S2 X1 (3,03) | 13 | +0,330 (1,0) | F4, F5 TOM x4 (2,70-3,03) | 61 | **+1,137 (5,2)** | +64,6 |
| 2026* | F4 R50 S2 X1 (3,20), F5 TOM k1j2 long (3,32), TOM k0j1 long (3,03) | 22 | −0,499 (−1,0) | F5 TOM x5 (3,23-3,41) | 30 | −0,438 (−0,6) | −3,7 |

\* fino al 06/07/2026. B&H = variazione % della chiusura D1 nell'anno, senza
costi. Varianti con t >= 3 nella storia disponibile a ogni 1 gennaio: 9, 5, 3,
1, 3, 2, 1, 1, 0, 0, 0, 1, 0, 1, 11 (2012 -> 2026): dal 2020 al 2024 quasi
nessuna; nel 2026 ne compaiono 11 (le finestre di fine mese long dopo il
2025), ma 8 non arrivano al 75% di anni positivi. Elenco completo in
`wf_scelte.parquet`.

## 3. Criterio finale (2012-2026, solo anni operati)

| | P | S | soglia |
|---|---|---|---|
| anni operati / non operati | 8 / 7 | 15 / 0 | |
| operazioni fuori campione | 433 | 3291 | |
| netto medio % per operazione | **−0,025** | +0,034 | > 0 |
| netto medio in $ | −1,21 | +0,71 | |
| lordo medio % / costo medio % | +0,004 / 0,029 | +0,063 / 0,029 | |
| t sul netto % | **−0,80** | 2,43 | >= 2 |
| anni positivi | 3/8 = 0,375 | **9/15 = 0,600** | >= 2/3 |
| placebo (stessi istanti, direzione casuale, 1000 serie, seme 20261003/4) | 0,466 | 0,001 | < 0,01 |
| **verdetto** | **NON FUNZIONA** (3 criteri su 4 falliti) | **NON FUNZIONA** (anni positivi) | |
| varianti distinte usate | 6 | 19 | |
| quota di operazioni long | 0,965 | 0,898 | |
| t sulla somma giornaliera (descrittivo) | −0,80 | 1,86 | |
| senza il 2025: n, netto %, t | 420, −0,036, −1,18 | 3230, +0,014, **1,00** | |
| 2012-2017: n, netto %, t | 384, −0,008, −0,52 | 2375, +0,004, 0,38 | |
| 2018-2026: n, netto %, t | 49, −0,156, −0,63 | 916, +0,113, 2,60 | |

Contributo per famiglia alla curva S (somma del netto % su 3291 operazioni):
F5 +94,1 (1099 op, +0,086/op), F4 +12,2 (497), F1 +10,6 (1472, +0,007/op),
F3 −4,0 (223). Tutto il risultato di S sta nelle finestre di calendario long
dell'oro (venerdi', ultime 2 ore del venerdi', prime 2 ore del lunedi',
fine/inizio mese) e per il 2018-2026 quasi solo nelle finestre di fine mese
(TOM k0-k2, j2-j4 long), scelte 4-5 alla volta dal 2021: sono la stessa
posizione contata piu' volte, da cui il t giornaliero 1,86 contro 2,43 per
operazione.

### Compra e tieni (previsione 3, solo confronto descrittivo)

Oro, chiusure D1 feriali, senza costi: 2012-2026 **+165,6%**, 0,031% al
giorno (3766 giorni), t 1,90; per anno vedi l'ultima colonna della tabella
2. Il netto per operazione di S (+0,034%, durata mediana 7,8 h, media 29,6 h)
e' dello stesso ordine della deriva giornaliera dell'oro, e la sua curva segue
gli anni dell'oro: il 2025 (+64,6% l'oro) e' l'unico anno di S con t > 2 e da
solo porta il t complessivo da 1,00 a 2,43; il 2013 (−28%) e il 2018 sono i
peggiori per entrambe.

## 4. Previsioni del protocollo

| previsione | esito |
|---|---|
| 1. P non trova nulla nella maggior parte degli anni | **quasi**: non opera in 7 anni su 15 (non la maggioranza stretta), nei restanti 8 opera con 1-3 varianti e perde (−0,025%, t −0,80, 3/8 anni). Nel 2020-2022 e 2024 nessuna variante ha t >= 3 nella storia |
| 2. S opera ogni anno ma netto <= 0 o t < 2 | **smentita nella forma, confermata nella sostanza**: S e' positiva con t 2,43, ma 9/15 anni e il t regge solo grazie al 2025 (senza: 1,00; 2012-2017: 0,38). Le scelte di un anno non reggono l'anno dopo nel 2012-2019; dal 2020 reggono perche' sono long sull'oro in anni di rialzo |
| 3. Se qualcosa regge e' una regola lenta e lunga = deriva rialzista | **confermata**: S e' long al 90%, dal 2020 sceglie finestre di calendario long di 2-6 giorni (F5 TOM) e la rottura del giorno stretto (F4 R50); il suo 2018-2026 (+0,113%/op, t 2,6) coincide con l'oro da 1.300 a 3.300 $. Compra e tieni: +165,6% |

## 5. Scelte interpretative (non coperte alla lettera dal protocollo)

1. **Unita' della scelta**: netto, t e anni positivi di ogni variante si
   calcolano sul netto in % del prezzo d'ingresso, la stessa unita' del
   risultato dell'anno (gli script di scoperta usavano prezzo, R o %). Le
   soglie registrate non cambiano.
2. **Soglia di operazioni per P**: quella che ogni script di scoperta usava
   nella propria promozione: 100 per F1, F3, F4, F5 (al massimo un'operazione
   per giorno/sessione/lato), 200 per F2 salvo 100 se L o H >= 1 giorno.
3. **Anno di un'operazione** = anno dell'istante d'ingresso (timestamp UTC),
   per il taglio della storia, per l'anno operato e per il costo. Per F4/F5 la
   giornata 22-22 etichetta Dec 31 22:00 come 1 gennaio: lo scarto riguarda due
   ore all'anno. L'esito di un'operazione entrata a fine dicembre e uscita a
   gennaio entra nella storia dell'anno dopo come dice il protocollo
   (ingresso prima del 1 gennaio); per il confine 2017/2018 sono 68
   operazioni su 1114 varianti (sezione 1).
4. **Anni che contano nella regola P**: anni con >= 10 operazioni; una
   variante senza alcun anno con >= 10 operazioni non e' promuovibile.
   Massimo 3 per famiglia prese per t, poi le 10 migliori per t.
5. **Anno operato con zero operazioni**: contato come operato e non positivo
   (non e' capitato).
6. **Costi**: anche lo scarto "rischio < 2 x costo" di F3/F4 usa il costo
   dell'anno d'ingresso (`esiti`/`prepara_rottura` di F4 chiamate con costo 0,
   lordo e lordo opposto, netto applicato qui: identico con costo costante,
   come mostra la riproduzione).
7. **Placebo**: direzione casuale per operazione; per F3/F4 l'esito opposto e'
   quello simulato con stop e obiettivo speculari (come nei placebo di
   scoperta), per F1/F2/F5 e' −lordo; costo uguale. Semi 20261003 (P) e
   20261004 (S). Calcolato una sola volta sulla curva finale, come registrato.
8. **F2**: le 396 regole sono quelle con cella consistente e direzione fissata
   dalla Fase A della scoperta 2009-2017 (`f2_faseb.parquet`): per il
   2012-2017 l'universo di F2 incorpora quindi informazione di tutta la
   scoperta (avvertenza gia' dichiarata nel protocollo). 15 regole non hanno
   mai un'operazione.
9. **Il 2018-2026 non e' "mai visto" per 5 regole**: e' stato aperto una
   volta per le 5 ipotesi di `docs/ricerca-da-zero-candidati.md` (commit
   b2c6202, esito in `verifica-2018-2026.md`: nessuna passa). Tre sono in
   questo universo (oro venerdi' CC long, Asia 60m inverti solo long, F4 CMP S2
   X1) e vengono scelte da S in alcuni anni. Contatore delle prove multiple del
   progetto: circa 7.370 varianti in scoperta, circa 110 descrittive, 5 in
   verifica; qui 1114 varianti x 15 scelte annuali, due regole di scelta.

## 6. Limiti

- Il walk-forward mette alla prova la scelta fra le varianti, non l'universo:
  l'universo e' stato scritto da chi conosceva la letteratura e i risultati di
  scoperta 2009-2017, e il 2015-2026 e' gia' stato guardato da altre ricerche.
- Le varianti scelte insieme sono spesso quasi identiche (4-5 finestre di fine
  mese sugli stessi giorni, due versioni della stessa rottura): il t "per
  operazione" conta la stessa posizione piu' volte; il t sulla somma
  giornaliera di S e' 1,86. Il protocollo prescriveva il t per operazione: e'
  riportato cosi', con la versione giornaliera come descrittiva.
- Nessuno swap sulle operazioni che tengono la notte (F5 TOM 2-6 giorni, F4
  X3/X5, F2 1g/5g): con lo swap reale sarebbero peggiori.
- Il 2026 e' parziale (fino al 6 luglio); i costi 2020-2026 sono gli spread
  misurati, 0,40 $ e' una stima per il 2009-2019.
- Il placebo a direzione casuale con costi dice che la direzione delle scelte
  di S non e' casuale (p 0,001): e' il long sull'oro che da' il segno, non la
  regola; il placebo registrato non confronta con "long a caso" (il placebo
  DATE di F5), che in verifica aveva gia' spiegato il venerdi' dell'oro.

## 7. File

`D:\ricerca_zero\walkforward\`: `dati\XAUUSD_{M5,M15,H1,D1}.parquet` (serie
continua), `varianti.parquet` (universo), `operazioni_f1..f5.parquet`
(2.004.608 operazioni, schema comune: ts, ts_uscita, anno, dir, entrata, lordo,
lordo_opp, costo, netto, netto_pct, netto_opp_pct), `riproduzione.parquet`,
`confronto_2009_2017.parquet`, `aggregati_variante_anno.parquet`,
`storia_fino_<Y>.parquet` (statistiche di ogni variante al 1 gennaio di Y),
`wf_scelte.parquet`, `wf_anni.parquet`, `wf_operazioni_P.parquet`,
`wf_operazioni_S.parquet`, `wf_sintesi.parquet`, `compra_e_tieni.parquet`;
`tmp_riproduci\` (operazioni sulla sola scoperta).

## Verifica avversariale (03/10/2026) — verdetto: il NON FUNZIONA regge, e si rafforza

Script di prova nello scratchpad della sessione, nessun file del progetto toccato.

| controllo | esito |
|---|---|
| t di S senza sovrapposizioni | per operazione 2,43; somma giornaliera 1,86; settimanale 1,63; mensile 1,65; per cluster (giorno, famiglia, verso) 1,65; sulle 15 medie annuali 1,07; bootstrap a blocchi annuali p(media <= 0) = 0,068. **Con qualunque aggregazione S fallisce anche t >= 2**: i criteri falliti sono due, non uno |
| placebo "long a caso, stesso anno, stesse durate" | su tutto S lo batte (le op F1 intraday pagano solo il costo), ma dove sta il risultato no: 2018-2026 placebo +0,065 contro +0,113 (p 0,13); solo F5 p 0,08; F4+F5 p 0,07; 2025 p 0,016. Meta' del 2018-2026 e' deriva pura dell'oro |
| swap FP (−0,715 $/notte long, +0,325 short, mercoledi' x3) | 3.079 notti su 1.059 operazioni: S scende a **+0,0055 %/op, t 0,39** (giornaliero 0,30), 8/15 anni. Quasi zero |
| scelta su uscita < Y invece che ingresso < Y | 852 op su 2.004.608 escono nell'anno dopo; rifatto: S +0,036 %, t 2,63, 9/15; P −0,030 %, t −0,70, 3/8. Verdetto invariato |
| fedelta' al protocollo e riproduzione | soglie, minimi, anni, unita' e costi verificati; scelte riprodotte identiche; 1114/1114 varianti; ingressi controllati sui prezzi M5 (causali) |

Per un eventuale studio futuro dello stesso tipo, da registrare prima: t
aggregato per giorno, swap nel netto, placebo "long a caso stesso anno".
