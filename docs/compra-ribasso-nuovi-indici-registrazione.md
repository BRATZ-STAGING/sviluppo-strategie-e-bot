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

## Previsioni

1. Il lato long e' positivo su almeno 3 indici su 4.
2. Il portafoglio NON arriva a t 2 (poche operazioni: ~1 al mese per indice).
