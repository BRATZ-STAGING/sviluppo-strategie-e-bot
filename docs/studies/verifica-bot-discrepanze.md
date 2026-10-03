# verifica_bot.py contro il motore ufficiale: le discrepanze (03/10/2026)

Verifica richiesta dopo la revisione avversariale del 03/10. Lo script
`trading/scripts/verifica_bot.py` produce i numeri delle quattro gestioni citati
in `docs/CONSEGNA-BOT-2026-08.md`, `docs/AVVIO-MT5-VPS.md` e
`bots/SCHEDE-STRATEGIE.md`; il suo motore (`Percorsi`/`cammina`) e' anche quello
di `analisi_b_18anni.py`, e sara' il riferimento per l'EA della B.

Metodo: stesse 712 operazioni (`genera` + `filtra`, archivio 2009-01-01 ->
2026-07-06) valutate **operazione per operazione** con i due motori, piu' una
seconda passata con `XAU_ANNI=2020-2026` (333 operazioni: e' l'archivio con cui
sono stati prodotti i numeri pubblicati). Motore ufficiale: `run_scale_trailing.
esito` sui percorsi `fav/sfav` di `genera` (gestioni EOD), `run_fuori_campione.
lunga` per A e B. Dettaglio per operazione nello scratchpad della sessione
(`vb_confronto_tutto.parquet`, `vb_confronto_2020.parquet`, 44 colonne: R, motivo e
istante d'uscita per ogni gestione e motore; script `vb_confronto.py`,
`vb_analisi.py`). I numeri pubblicati sono riprodotti alla terza cifra.

## 1. Causa della differenza -47,6 / -39,6 (in uso, 2009-2019, spread 0,30)

**La chiusura di fine giornata di `verifica_bot` dipende dal calendario dei
dati.** `Percorsi.eod` segna come fine giornata la candela con `hour == 21 and
minute == 0`. Ma l'oro chiude alle **21:00 UTC quando a New York vige l'ora
legale** (aprile-ottobre): in quei mesi la candela delle 21:00 **non esiste**
(nell'archivio: tutto l'anno nel 2009-2012, sparisce progressivamente nel
2013-2015, mai da aprile a ottobre dal 2016). Allora `cammina` non trova
`fine_gio`, e la posizione "in uso" resta aperta la notte e i giorni seguenti
fino a stop, pareggio o obiettivo (durata massima 19-23 giorni; 64 operazioni
su 333 oltre un giorno nel 2020-2026). Nei mesi invernali chiude invece alla
candela delle 21:00 (prezzo delle 21:01) trattando un minuto in piu', mentre il
motore ufficiale chiude all'ultima candela **prima** delle 21:00 (20:59).

Le uscite "fine giornata" di `verifica_bot` cadono infatti solo nei mesi 1, 2,
3, 11, 12 (2020-2026). Scomposizione operazione per operazione (R lordo):

| periodo | op | uguali | diverse | uscita in un giorno dopo | stesso giorno (minuto 21:00) |
|---|---|---|---|---|---|
| 2009-2019 | 374 | 232 | 142 | 52 op, **-7,29 R** | 90 op, -0,77 R |
| 2020-2026 (archivio 2009-2026) | 338 | 221 | 117 | 79 op, **+25,16 R** | 38 op, +0,40 R |
| 2020-2026 (archivio 2020-2026) | 333 | 213 | 120 | 81 op, **+45,51 R** | 39 op, +5,96 R |

Prova: sostituendo `eod` con "ultima candela prima delle 21:00 della propria
giornata" (il `b-1` del motore ufficiale) la "in uso" di `cammina` coincide con
l'ufficiale su **338/338 e 333/333** operazioni nel 2020-2026 e su **370/374**
nel 2009-2019; le 4 residue sono fill all'apertura gia' oltre lo stop (`gap`,
-0,025 R in tutto, convenzione piu' prudente di `cammina`). Totale 2009-2019:
-39,61 R / DD 51,70 contro -39,58 / 51,68 dell'ufficiale. Lo stesso vale per la
1:2 (0 differenze nel 2020-2026, 4 nel 2009-2019).

Escluse come cause: anni caricati e `MEDIANA_ATR` (25,5968 fissa contro
25,4127 calcolata sull'archivio intero: stesse 712 operazioni), finestra
`GIORNI_MAX`, campione filtrato, costo (identico nei due motori).

## 2. Impatto sulle quattro gestioni

Spread 0,30 salvo indicazione; "uff" = motore ufficiale; A e B ufficiali senza
swap, salvo "con swap" (FP: long -71,5 / short +32,5 punti a notte).

### 2009-2019 (374 operazioni, archivio intero)

| gestione | verifica_bot | ufficiale | nota |
|---|---|---|---|
| in uso | **-47,64 R, DD 79,47** | **-39,58 R, DD 51,68** | EOD solo d'inverno |
| in uso, spread vero (0,40) | -61,39, DD 87,04 | -53,33, DD 61,46 | |
| A | -21,80, DD 62,91 | -35,45, DD 60,17 (con swap -45,09, DD 62,24) | A di verifica_bot non chiude mai il venerdi' (par. 3) |
| B | -77,63, DD 77,63 | -77,63, DD 77,63 (con swap -88,39, DD 88,39) | **identiche** |
| B, spread vero | -91,38, DD 91,38 | idem | |
| 1:2 | -58,98, DD 74,60 | -55,00, DD 73,17 | EOD solo d'inverno |

### 2020-2026, archivio 2020-2026, 333 operazioni, spread vero (i numeri pubblicati)

| gestione | pubblicato (verifica_bot) | ufficiale, stesso spread | scarto |
|---|---|---|---|
| in uso | **+214,67 R, DD 20,78** | **+163,19 R, DD 16,29** | **+51,5 R (+32%)**, DD +4,5 |
| A | **+206,19, DD 26,30** | +182,73, DD 12,60 (A corretta in verifica_bot: +181,31, DD 15,85) | **+23,5 R**, DD doppio |
| B | +174,57, DD 12,60 | +174,57, DD 12,60 | **0**; con swap +165,1 |
| 1:2 | **+86,62, DD 12,34** | +71,26, DD 10,92 | **+15,4 R (+22%)** |

Con spread 0,30 l'ufficiale da' +171,97 (in uso), +178,47 (A con swap),
+173,89 (B con swap): sono esattamente i numeri della tabella 2020-2026 di
`bots/SCHEDE-STRATEGIE.md`, che quindi vengono dal motore ufficiale, mentre la
tabella della consegna viene da `verifica_bot`. **Le due tabelle non sono
confrontabili fra loro**, e la differenza non e' lo spread: e' la gestione.

Sull'archivio intero (338 operazioni 2020-2026) il quadro e' lo stesso: in uso
+171,59 contro +146,02 (spread vero), A +191,00 contro +170,32, B identiche,
1:2 +77,30 contro +64,67.

In sintesi: nel 2020-2026 tenere la "in uso" aperta la notte d'estate ha reso
+45-51 R (mercato in salita), nel 2009-2019 e' costato 7-8 R e ha quasi
raddoppiato il drawdown (51,7 -> 79,5). **I numeri pubblicati di in uso, A e
1:2 descrivono gestioni diverse da quelle dichiarate**; quelli della B sono
giusti, al netto dello swap non modellato (-9,45 R sul 2020-2026, -10,76 sul
2009-2019).

## 3. Un secondo difetto: la A di verifica_bot non chiude mai il venerdi'

`BOT` definisce la A con `soglia_weekend = -99.0`, e `cammina` chiude prima del
fine settimana solo se `chiu[i] < soglia_weekend`: con -99 la condizione non e'
mai vera. Prova: zero uscite "chiusa il venerdi'" su 712 operazioni, 24+31
operazioni oltre tre giorni (massimo 20). La A di verifica_bot e' quindi
"pareggio +3R, 1:8, nessuna chiusura, scadenza a 30 giorni". Con
`soglia_weekend = +inf` coincide con l'ufficiale su 702/712 operazioni; le 10-12
residue sono il venerdi' d'inverno, dove `cammina` chiude all'ultima candela
prima del buco (21:59 UTC) e l'ufficiale tronca alle 21:00 (scarto +1,9 / -0,9 R).

## 4. La gestione B di `cammina`: nessun difetto rispetto all'ufficiale

R identico su **712/712** operazioni (esito, motivo e istante d'uscita) fra
`cammina` di verifica_bot e `run_filtro_weekend.cammina` usato da
`run_fuori_campione`. Due osservazioni, non difetti, da tenere presenti per
l'EA:

- la regola del fine settimana scatta prima di **qualunque** buco oltre 120
  minuti, non solo del venerdi': 2 casi su 712 (17/02/2014 e 04/07/2022, festivi
  USA); identico nell'ufficiale;
- la chiusura "del venerdi'" avviene all'ultima candela prima del buco: 20:59
  UTC con l'ora legale USA, 21:59 con quella solare;
- lo swap non c'e' in verifica_bot (vale -9,45 R sul 2020-2026 ai tassi FP).

## 5. Quale motore e' giusto e perche'

**Il motore ufficiale.** (1) Fa quello che la regola dice: chiusura di tutte le
posizioni alle 21:00 UTC, cioe' all'ultima candela prima delle 21; la A chiude
il venerdi'. (2) Il comportamento di `verifica_bot` cambia con la stagione e con
il calendario del fornitore dei dati (nel 2009-2012 chiudeva tutto l'anno, dal
2016 solo d'inverno): non e' una gestione, e' un artefatto. (3) Corretto il solo
`eod`, i due motori coincidono operazione per operazione: non c'e' nient'altro
che li distingua. Sull'uscita per gap all'apertura `cammina` e' piu' prudente
dell'ufficiale (fill al prezzo d'apertura oltre lo stop invece che al livello):
e' una differenza legittima e vale 0,025 R su undici anni.

## 6. Correzione proposta (NON applicata: cambierebbe i numeri pubblicati)

In `Percorsi.__init__`, al posto di `hour == 21 & minute == 0`:

```python
t = pd.DatetimeIndex(m1.index).as_unit("ns")
t21 = (t.normalize() + pd.Timedelta(hours=ora_chiusura)).as_unit("ns").asi8
succ = np.append(t.asi8[1:], np.iinfo(np.int64).max)
self.eod = (t.asi8 < t21) & (succ >= t21)   # ultima candela prima delle 21:00
```

e per la A `soglia_weekend = np.inf` (chiude sempre prima del fine settimana).
Dopo la correzione vanno rifatte le tabelle 2020-2026 di in uso, A e 1:2 nella
consegna e in AVVIO-MT5-VPS; la B non cambia. Se si vuole la confrontabilita'
con `run_fuori_campione`, aggiungere lo swap ad A e B.

Applicato invece il solo `misure()`: il massimo dell'equity parte dal capitale
iniziale 0 e non dalla prima operazione. Sul 2020-2026 **non cambia nessuna
delle otto celle** (quattro gestioni x due spread, entrambi gli archivi: il
drawdown massimo non parte dalla prima operazione). Sul 2009-2019 cambia solo
dove la serie apre in perdita e non risale mai: B 76,58 -> 77,63 (spread 0,30),
90,31 -> 91,38 (spread vero), 1:2 spread vero 82,28 -> 82,35.

## 7. Origine di 87,4 R

**Rintracciata.** E' `dd_r = 87,367` della riga "fuori campione / B" di
`docs/studies/dati/fuori_campione.parquet`, prodotto da `run_fuori_campione.py`
(appendice AU rifatta dopo la correzione delle domeniche, BD): gestione B con il
motore ufficiale, **spread 0,30 e swap reale**, 374 operazioni 2009-2019,
r_tot -88,418. Il drawdown e' calcolato da `misure()` di quello script con il
massimo che parte dalla prima operazione (stesso difetto di verifica_bot): la
prima operazione (13/01/2009) perde 1,051 R e 88,418 - 1,051 = 87,367. Da
capitale 0 sarebbe **88,42 R**, che coincide con la perdita totale. Il numero e'
entrato in `bots/SCHEDE-STRATEGIE.md` con il commit 0eaf085 (04/08/2026, riga
"perdita massima 2009-2019: 51,69 / 62,24 / 87,37", insieme a -39,61 / -45,09 /
-88,42) e da li' nella consegna. Non era riproducibile con verifica_bot perche'
verifica_bot non modella lo swap: senza swap la B da' 77,63 (spread 0,30) e
91,38 (spread vero).

Scala dei quattro numeri della B sul 2009-2019: 87,4 = ufficiale con swap,
spread 0,30, DD dalla prima operazione; 88,4 lo stesso da capitale 0; 89,8 =
appendice AU prima della correzione BD (382 operazioni); 90,3 / 91,4 = spread
vero senza swap, prima e dopo la correzione del drawdown.
