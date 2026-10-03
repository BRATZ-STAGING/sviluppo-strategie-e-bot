# Intraday/scalp su cambi e oro — protocollo registrato (03/10/2026)

Richiesta dell'utente: una strategia **scalp o intraday con almeno 1-2
operazioni al giorno**, su oro o cambi principali, conto **FP Markets Raw**.
Scritto prima di guardare qualunque dato dei cambi (download in corso).

## Mercati e dati

HistData M1 BID 2010 -> 09/2026 (ora di New York con ora legale convertita in
UTC), parquet in `D:\histdata_parquet\<SIMBOLO>\`: **EURUSD, USDJPY, GBPUSD,
AUDUSD, USDCHF, USDCAD, EURJPY** — mai usati nel progetto. Oro (Dukascopy) si
puo' includere, ma l'intraday sull'oro e' gia' stato studiato a fondo (molte
appendici + ricerca da zero F1-F6) e la sua verifica 2018-2026 e' gia' stata
aperta il 03/10: un candidato sull'oro vale meno di uno sui cambi.

- **Scoperta: 2010-2017.** **Verifica: 2018 -> fine dati**, aperta una volta
  sola, con separazione fisica delle cartelle come in `D:\ricerca_zero\`.

## Costi FP Markets Raw (round trip, in pip; commissione 6 $/lotto incluso)

| coppia | spread medio Raw | commissione in pip | **costo usato** |
|---|---|---|---|
| EURUSD | 0,15 | 0,60 | **0,8** |
| GBPUSD | 0,35 | 0,60 | **1,0** |
| AUDUSD | 0,25 | 0,60 | **0,9** |
| USDCHF | 0,40 | ~0,55 | **1,0** |
| USDCAD | 0,40 | ~0,80 | **1,2** |
| USDJPY | 0,25 | ~0,90 | **1,2** |
| EURJPY | 0,50 | ~0,90 | **1,4** |
| oro | `SPREAD` annuo di verifica_bot | 0,06 $ | spread + 0,06 $ |

- Gli spread dei primi anni (2010-2014) erano piu' larghi: **ogni candidato
  deve restare positivo anche con costi x1,5**.
- **Rollover**: nessuna entrata fra 20:45 e 22:15 UTC (gli spread si allargano
  di molte volte); entrate fra 22:15 e 23:59 UTC pagano **costo x2**.
- Swap: le posizioni intraday si chiudono prima delle 20:45 UTC, oppure pagano
  uno swap stimato prudente se attraversano il rollover (da dichiarare).
- Esecuzione: entrata all'apertura della candela dopo il segnale; stop e
  obiettivi dentro la candela, se entrambi nella stessa candela vale lo stop;
  ordini stop/limite senza miglioramento di prezzo.

## Vincolo dell'utente: frequenza

Una regola e' ammissibile se produce **in media almeno 1 operazione per
giornata di borsa**, contando la stessa regola su piu' coppie (es. 0,3/giorno
su 4 coppie = 1,2/giorno). Regole piu' rare si riportano, ma non si promuovono.

## Famiglie (una per agente; concetti base, niente concetti del progetto)

1. **Notte asiatica**: range e ritorno alla media fra 22:15 e 06:00 UTC
   (lo "scalping notturno"), con stop e obiettivi in pip o in frazioni di ATR.
2. **Aperture di sessione**: rottura o rientro del range asiatico a Londra
   (07:00 UTC) e del range di Londra a New York; prima ora di sessione.
3. **Ritorno alla media e momentum di breve dentro la giornata** (5-60
   minuti), con filtri di volatilita' e d'orario.
4. **Orari fissi del mercato dei cambi**: fixing di Tokyo (00:55 UTC), fixing
   di Londra WM/R (16:00 Londra), aperture/chiusure dei mercati azionari.

## Promozione (sulla sola scoperta)

Netto > 0 con costi x1 **e** x1,5; t >= 3 sul netto; anni positivi >= 6 su 8;
placebo p < 0,01; frequenza come sopra; al massimo 3 candidati per famiglia.
Ogni agente dichiara prima le varianti e ne riporta il numero.

## Verifica (una volta sola)

Netto > 0 con costi x1 e x1,5; t >= soglia di Bonferroni sul numero di
candidati k (t >= 2 se k = 1; 2,4 se k = 2-3; 2,6 se k = 4-5; 2,8 fino a 10);
anni positivi >= 2/3; placebo p < 0,01. Si riportano tutti i candidati.

## Previsioni

1. La notte asiatica sara' la famiglia con piu' effetti netti positivi in
   scoperta, ma con perdite rare e grandi (code) e molto sensibile ai costi.
2. Le rotture d'apertura avranno segno instabile fra coppie.
3. Al massimo un candidato su cinque passera' la verifica.
