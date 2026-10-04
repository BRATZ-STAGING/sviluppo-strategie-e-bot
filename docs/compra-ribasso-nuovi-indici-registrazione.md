# "Compra il ribasso" su indici mai usati — registrazione (04/10/2026)

Scritto **prima** di scaricare i dati. Decisione dell'utente del 04/10/2026.

## Perche'

Fra ~43.000 regole provate (intraday, cambi, multi-giorno) l'unico fenomeno
che in verifica 2018-2026 non ha cambiato segno e' il candidato **M1** della
ricerca multi-giorno (`docs/multigiorno-paniere-candidati.md`): comprare i
ribassi dell'S&P sopra la media 200. In verifica: +0,136 R/op, t 1,56, p
0,027 — positivo ma non dimostrato. Un test pulito che resta: **la stessa
regola, invariata, su indici azionari che nessuno ha mai usato**, sull'intero
periodo disponibile (tutto fuori campione per questa regola).

## Dati

HistData M1 BID, 2010 -> 09/2026, ora di New York con ora legale -> UTC
(`trading/scripts/scarica_histdata.py`), su D: solo per uso personale:
**JPXJPY (Nikkei 225), UKXGBP (FTSE 100), ETXEUR (Euro Stoxx 50), FRXEUR
(CAC 40)**. Giornata 22 -> 22 UTC come il paniere
(`trading/scripts/prepara_paniere_d1.py`). Prima di qualunque calcolo si
controllano i livelli di prezzo anno per anno (il DAX di HistData conteneva un
altro indice per tre anni): un tratto anomalo si esclude e si dichiara.

## La regola (M1, invariata, codice `multi_f2_ritorno.py`)

1R = 2 x ATR20; segnale alla chiusura della giornata; entrata all'apertura
della giornata dopo; uscita alla chiusura della 5a giornata; stop 2 x ATR20;
una posizione alla volta per mercato. Long se la variazione su 5 giornate e'
<= -1,5 x ATR20 e la chiusura e' sopra la media 200; short simmetrico sotto la
media 200. Le prime 200 giornate servono solo agli indicatori.

## Costi (round trip, punti indice) e swap

Nikkei 10; FTSE 1,5; Euro Stoxx 2,0; CAC 1,5 (prudenti rispetto ai CFD FP),
x1 e x1,5. Swap come da protocollo multi-giorno: 3% annuo del nominale, long e
short, x3 il mercoledi'.

## Ipotesi unica e criterio

**Ipotesi primaria: il portafoglio dei 4 indici a rischio uguale.** Passa se:
netto > 0 a x1 e x1,5; **t >= 2** sui rendimenti mensili; anni positivi >= 2/3;
placebo p < 0,05 sia a direzione casuale sia a date casuali (stessa direzione,
date estratte fra le giornate nello stesso stato rispetto alla media 200).
Per indice si riporta tutto, senza verdetto separato.

## Emendamento 1 — qualita' del dato (04/10/2026, prima di qualunque calcolo della regola)

Trovato preparando i dati, senza calcolare segnali ne' risultati:
- **ETXEUR dal 17/12/2018 non e' l'Euro Stoxx 50** (salto a ~8.900 punti,
  livello dell'IBEX 35); HistData non ha ETXEUR dopo il 2019. Si usa
  **11/2010 -> 14/12/2018**. Gli altri tre indici: livelli plausibili; i salti
  bruschi sono eventi veri (Fukushima 15/03/2011, Brexit 24/06/2016, marzo
  2020).
- **Giornata valida**: su HistData questi indici quotano meno ore dei mercati
  del paniere (M5 mediane per giornata: Euro Stoxx ~124, CAC ~167, FTSE
  ~168, Nikkei ~227) e la soglia fissa di 150 M5 scartava l'80% delle
  giornate dell'Euro Stoxx. Si sostituisce con: **valida se le M5 della
  giornata sono almeno l'80% della mediana di quel mercato**. Le M5 si
  contano come nel paniere (intervalli di 5 minuti con almeno un dato).

## Previsioni

1. Il lato long e' positivo su almeno 3 indici su 4.
2. Il portafoglio NON arriva a t 2 (poche operazioni: ~1 al mese per indice).
