# Distanza dal VWAP all'ingresso sul 2009-2019 — esito (05/10/2026)

Registrazione: `docs/vwap-distanza-18anni-registrazione.md` (commit 652ec9e,
scritto prima del calcolo). Script: `trading/scripts/run_vwap_distanza_18anni.py`.
Dettaglio: `docs/studies/dati/vwap_distanza_2009-2026.parquet` e
`..._2020-2026.parquet`.

**Esito: NON REGGE.** Ne' H1 (il terzo medio rende di piu') ne' H2 (il terzo
basso rende di meno). Sul 2009-2019 l'ordine si ribalta: il terzo **basso** e'
il migliore dei tre, e tutti e tre sono negativi. La famiglia torna fra le
strade respinte.

## Controllo prima di aprire il 2009-2019

Con `XAU_ANNI=2020-2026` lo script riproduce BP corretta alla terza cifra:
1.290 operazioni; terzo medio +0,377 in ricerca e +0,382 in verifica; basso
-0,277 / +0,114; alto +0,062 / +0,375.

## 2009-2019, terzi congelati (0,6895 e 1,5879 respiri)

| terzo | operazioni | netto R/op |
|---|---|---|
| basso | 429 | **-0,112** |
| medio | 442 | -0,140 |
| alto | 518 | -0,172 |

| ipotesi | differenza R/op | placebo p (2.000, seme 20261005) | anni col segno atteso | verdetto |
|---|---|---|---|---|
| H1: medio - resto | +0,005 | 0,476 | 4/11 | **NON REGGE** |
| H2: resto - basso | **-0,045** (segno opposto) | 0,658 | 2/11 | **NON REGGE** |

Per anno (H1 / H2): 2009 +0,73/+0,69, 2010 +0,03/-0,18, 2011 -0,08/-0,19,
2012 -0,08/-0,12, 2013 +0,18/-0,08, 2014 -0,26/-0,25, 2015 +0,41/+0,17,
2016 -0,45/-0,21, 2017 -0,32/-0,12, 2018 -0,41/-0,13, 2019 -0,04/-0,80.

Nessuna fascia e' utilizzabile: il terzo medio fa -0,140 R/op, medio+alto
-0,157.

## Descrittivo (fuori dal verdetto)

| | basso | medio | alto |
|---|---|---|---|
| 2009-2019, spread 0,40 | -0,150 | -0,177 | -0,206 |
| 2009-2019, campione ufficiale (121/129/124 op) | -0,257 | -0,007 | -0,062 |
| 2020-2026 sull'archivio intero | -0,082 | +0,390 | +0,241 |
| 2009-2026 intero | -0,097 | +0,120 | +0,015 |

Sul campione ufficiale il terzo medio torna il migliore (-0,007), ma con circa
120 operazioni per terzo e senza nessuna fascia positiva: e' la stessa
dispersione del placebo di BP, non un segnale.

## Previsioni

1. H1 non regge: **confermata** (+0,005, p 0,48).
2. H2 piu' probabile di H1 ma non passa il placebo: **confermata nella forma,
   smentita nella sostanza**. H2 non e' solo debole: ha il segno opposto.
3. Nessuna fascia ha netto positivo sul 2009-2019: **confermata**.

## Cosa resta

H1 **non e' confermata e non si distingue dal rumore**, ma non e' smentita:
con una deviazione del nullo di circa 0,10 R/op il test vede solo differenze
oltre ~0,2 R/op, mentre l'effetto di BP nel 2023-2026 valeva +0,14 (medio
0,382 contro 0,240 del resto), dentro l'intervallo del 2009-2019 (bootstrap a
blocchi per giorno, IC95 H1 [-0,20; +0,23]). H2 invece e' smentita nel segno
(2 anni su 11). In pratica: nessuna prova che la distanza dal VWAP selezioni
qualcosa fuori dal 2020-2026, e nessuna fascia che guadagni sul 2009-2019.

## Verifica avversariale (05/10/2026): il NON REGGE regge

- Numeri riprodotti alla quarta cifra; fedelta' a BP e alla registrazione
  confermate; campione 2009-2019 causale, dati completi, nessun anno anomalo.
- **Un minuto nel futuro, ereditato da BP** (gravita' bassa): la misura legge
  il VWAP della candela che si apre all'istante d'ingresso, mentre l'entry e'
  la chiusura della candela prima. Con il VWAP della candela precedente
  cambiano 2 fasce su 1.389 e H1 diventa -0,011 (p 0,53): nessun effetto sul
  verdetto. Da correggere in `run_selezione_fine.py` se BP viene riaperta.
- Il placebo per operazione non e' stretto (operazioni dello stesso giorno
  correlate 0,52), ma le fasce variano dentro il giorno: il bootstrap per
  giorno da' la stessa dispersione. Per un eventuale risultato positivo futuro
  usare il placebo a livello di giorno.
- Le righe descrittive "2020-2026 sull'archivio intero" e "2009-2026 intero"
  NON sono BP: con undici anni di storia in piu' cambiano i mesi ad alta
  volatilita' e le soglie (1.288 operazioni contro 1.290, 656 con netto
  diverso).
