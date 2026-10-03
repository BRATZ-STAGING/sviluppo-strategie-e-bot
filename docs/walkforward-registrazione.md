# Walk-forward dal 2009 — protocollo registrato (03/10/2026)

Richiesta dell'utente: cercare una costante di lungo periodo **partendo dal
2009 e andando in avanti**, cioe' scegliendo ogni anno solo con gli anni gia'
passati. Scelte dell'utente: universo = famiglie della ricerca da zero; finestra
= tutta la storia dal 2009 (ancorata, espansiva).

Scritto **prima** di calcolare qualunque risultato walk-forward.

## Cosa si mette alla prova

Non una strategia, ma il **metodo di scelta**: "ogni 1 gennaio prendo le regole
che sulla storia fin li' hanno passato il criterio, e le opero per l'anno
dopo senza toccarle". Se la curva degli anni operati e' positiva, esiste un
processo che si adatta; se no, la risposta e' no.

## Universo

- Mercato: **solo oro (XAUUSD, Dukascopy)**. Gli indici e l'argento HistData
  restano fuori (scelta dell'utente del 02/10: solo oro).
- Varianti: **esattamente** quelle dichiarate per l'oro nelle famiglie 1-5 di
  `docs/studies/zero/` (orologio, momentum, range, volatilita', calendario),
  con le stesse definizioni e le stesse funzioni degli script `zero_f*.py`,
  che non si modificano. La famiglia 6 (fra mercati) e' fuori perche' usa
  l'argento HistData. Il numero esatto di varianti si scrive qui sotto prima
  di calcolare i risultati.
- **Conteggio (03/10/2026 21:40, prima di qualunque calcolo walk-forward)**:
  **1114 varianti** dell'oro = F1 orologio 124 (R1 48, R2 6, R4a 36, R4c 4,
  R5 30) + F2 momentum 396 (33 celle consistenti in scoperta x 12 regole,
  direzione fissata dalla scoperta, come in `f2_faseb.parquet`) + F3 range 432
  (a 216, b 216) + F4 volatilita' 104 (a 56, b 32, c 16) + F5 calendario 58
  (a 10, b 38, c 10). Contate sui parquet di scoperta `D:\ricerca_zero\risultati\`
  filtrati a XAUUSD e verificate con il conteggio combinatorio delle
  dichiarazioni. Il 2018-2026 e' gia' stato aperto una volta per le 5 ipotesi
  di `docs/ricerca-da-zero-candidati.md` (commit b2c6202; esito in
  `docs/studies/zero/verifica-2018-2026.md`: nessuna passa): per quelle 5
  regole non e' piu' "mai visto". Contatore delle prove multiple del progetto:
  circa 7.370 varianti in scoperta, circa 110 descrittive, 5 in verifica.
- Dati: le candele M5/M15/H1/D1 dell'oro 2009-01-01 -> 2026-07-06 come
  un'unica serie continua (scoperta + verifica concatenate), indicatori
  calcolati in modo causale sulla serie intera.
- Costi round trip: 0,40 $ fino al 2019, poi lo `SPREAD` annuo di
  `trading/scripts/verifica_bot.py` (come nel protocollo della ricerca da zero).

## Procedura, uguale ogni anno

Per ogni anno Y dal **2012** al **2026** (2009-2011 servono solo da storia):

1. si guardano solo le operazioni con ingresso **prima del 1 gennaio di Y**;
2. **regola P (principale)**: si promuovono le varianti con netto medio > 0,
   t >= 3, anni positivi >= 75% degli anni con almeno 10 operazioni, almeno
   200 operazioni (100 per regole giornaliere o piu' lente); al massimo 3 per
   famiglia e 10 in tutto, le migliori per t. Se nessuna passa, l'anno Y non si
   opera (risultato zero, e si dice);
3. **regola S (secondaria, sempre operativa)**: le 5 varianti con t piu' alto
   fra quelle con netto > 0 e almeno 100 operazioni, senza soglia di t;
4. le varianti scelte si operano per tutto l'anno Y con le loro regole; il
   risultato dell'anno e' la media, per operazione, del netto in **percentuale
   del prezzo d'ingresso** (unita' comune a tutte le famiglie).

Il placebo non entra nella scelta annuale (troppo costoso); si fa una volta
sola sulla curva finale: stessi istanti d'ingresso, direzione casuale, 1000
ripetizioni.

## Criterio finale (2012 -> 2026, solo anni operati)

Il metodo **funziona** se, per la regola considerata, valgono tutte:
- netto medio per operazione > 0;
- t >= 2 sul netto di tutte le operazioni fuori campione;
- anni positivi >= 2/3 degli anni operati;
- placebo p < 0,01.

Si riportano entrambe le regole, P e S, anche se falliscono.

## Previsioni (prima di calcolare)

1. La regola P non trova nulla nella maggior parte degli anni: nella scoperta
   2009-2017 nessuna variante arrivava a t 3.
2. La regola S opera ogni anno ma il suo netto fuori campione e' <= 0 o con
   t < 2: le scelte di un anno non reggono l'anno dopo.
3. Se qualcosa regge, sara' una regola lenta (giornaliera) e lunga sull'oro,
   cioe' la deriva rialzista: andra' confrontata col semplice "compra e tieni".

## Avvertenze dichiarate

- L'universo delle varianti e' stato scritto il 02/10/2026, da chi conosceva
  la letteratura e (per il 2009-2017) aveva visto i risultati di scoperta:
  il walk-forward controlla la scelta fra le varianti, non la scelta
  dell'universo.
- Il 2015-2026 e' gia' stato guardato da altre ricerche; qui nessuna soglia
  viene ritoccata dopo aver visto i risultati.
