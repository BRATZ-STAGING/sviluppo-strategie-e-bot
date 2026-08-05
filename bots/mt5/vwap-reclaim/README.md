# VWAP Reclaim — Expert Advisor MT5 (profili B, C, D)

## Cosa fa

Cerca il **reclaim del VWAP giornaliero su candele M6**: dopo che il prezzo si
e' allontanato dal VWAP di almeno 4 $ nella giornata, una candela lo torna a
toccare e ci chiude oltre, con la struttura di H6 e H2 nella stessa direzione,
M33 e H12 a confermare e M12 in ritracciamento. Entra **a mercato alla chiusura
della candela M6**, stop sotto il minimo delle ultime 5 candele M6 della
giornata piu' 0,30 $. Esce in tre modi diversi a seconda del profilo.

Le sette condizioni per esteso sono in `bots/SCHEDE-STRATEGIE.md`; il motore di
riferimento e' `trading/framework/segnali.py`.

## Strumento e timeframe

XAUUSD. L'EA si mette su **un grafico M1** e costruisce da solo tutti i
timeframe che gli servono (M6, M12, M33, H2, H6, H12): non usa quelli del
terminale, perche' M33 non esiste in MT5 e perche' i tagli del broker non
coincidono con quelli del motore di ricerca.

## I tre profili

Un solo sorgente, il profilo e' un parametro. **Tre istanze su tre conti
separati**, ciascuna con il suo `MagicNumber`.

| | **B** | **C** | **D** |
|---|---|---|---|
| obiettivo | 1:8 | 1:2 secco | 1:10 |
| gestione | da +3R lo stop insegue l'MFE a distanza 2R | nessuno spostamento | a +3R di MFE lo stop va a **+0,50 R** |
| chiusura | oltre la giornata; il venerdi' alle 21:00 UTC resta aperta solo sopra +1R | 21:00 UTC | 21:00 UTC |
| scadenza | 30 giorni | — | — |
| lati | long e short | long e short | **solo long** |
| **rischio per operazione** | **0,75%** | **0,75%** | **0,53%** |
| Swap Free | **necessario** | non serve | non serve |

Le taglie sono diverse **perche' i drawdown sono diversi**: pareggiando il
rischio in percentuale di conto tutte e tre atterrano fra −9,25% e −9,92%, con
2,1-2,8 punti di margine sul limite del 12% della sfida.

**Sulla B il trailing non e' un dettaglio.** L'obiettivo 1:8 viene toccato nel
4% delle operazioni; il 29% le chiude lo stop mobile in guadagno. Se il
trailing e' implementato male la B non perde qualche punto, smette di
funzionare.

## Parametri in uso

Da impostare per ciascuna istanza (gli altri restano ai valori di default, che
sono quelli della taratura ufficiale):

| istanza | `Profilo` | `MagicNumber` | rischio |
|---|---|---|---|
| conto 1 | `PROFILO_B` | 20260805 | 0,75% (automatico) |
| conto 2 | `PROFILO_C` | 20260806 | 0,75% (automatico) |
| conto 3 | `PROFILO_D` | 20260807 | 0,53% (automatico) |

`RischioPerOp = 0` lascia decidere al profilo. `MedianaAtrRif = 25.5968` e' la
mediana ATR 2020-2024 **congelata**: senza di essa, nei mesi ad alta
volatilita' le soglie diventerebbero indefinite e l'EA smetterebbe di aprire in
silenzio — per questo l'EA si rifiuta di partire se e' <= 0.

`GiorniStoria = 420` non e' un capriccio: sotto **250 giornate vere** la
classificazione dei mesi agitati risponde "normale" per costruzione, e l'EA
userebbe soglie in dollari dove il motore le riscala. Con meno storia l'EA non
apre e lo scrive nel log.

## Rischio e size

    lotti = (equity x rischio%) / (distanza_stop_in_$ / tickSize x tickValue)

arrotondato **per difetto** al passo del broker. **Sotto il lotto minimo
l'operazione si salta**: forzarla a 0,01 significherebbe rischiare il triplo
del previsto, e in una sfida il vincolo e' sopravvivere, non fare numero.

Spegnimento: `LimiteEquityPct` (saldo sotto il 50% iniziale) e
`FermaADrawdownR = 15`. Quest'ultima e' la **proposta** di
`docs/AVVIO-MT5-VPS.md` §4, non una decisione presa: −15 R e' oltre il peggio
del periodo buono (12,6 R per la B) ed entro il peggio del periodo cattivo
(87,4 R). Va confermata prima di partire.

## Stato

**Mai girato su nessun conto**, nemmeno demo. Scritto il 05/08/2026.

## Risultati noti

Nessuno prodotto da questo EA. I numeri attesi vengono dal motore di ricerca
sul 2020-2026 (333 operazioni, spread reale):

| | B | C | D (solo long) |
|---|---|---|---|
| R totale | +174,6 | +86,6 | +220,7 |
| R per operazione | 0,52 | 0,26 | 0,95 |
| operazioni vinte | 38,4% | 46,9% | 39,0% |
| perdita massima | 12,60 R | 12,33 R | 18,71 R |
| anni positivi | 7/7 | 6/7 | 6/7 |

**Questi numeri non sono di questo EA**: sono del motore Python, con le sue
convenzioni. Un backtest MT5 dara' numeri diversi, e la differenza non e'
necessariamente un errore.

## Cosa e' stato verificato

Il **nucleo del segnale** (`VwapReclaimCore.mqh`) non chiama niente del
terminale, quindi si compila anche con g++ e si puo' far girare sulle stesse
candele M1 del motore Python. Fatto:

    cd verifica && python3 confronta.py 2023 2026 2025-01 2026-06

| | motore Python | nucleo EA | divergenze |
|---|---|---|---|
| segnali grezzi 2025-01 → 2026-06 | 309 | 309 | **0** |
| operazioni con le conferme | 96 | 96 | **0** |

Confrontati istante, lato, entry, stop e rischio di ognuna.

E il confronto e' stato a sua volta messo alla prova (`falsifica.py`):
introducendo nel nucleo, una alla volta, sei delle trappole elencate in
`AVVIO-MT5-VPS.md`, **tutte e sei fanno fallire il confronto**. La settima —
scrivere il ritracciamento come "M12 contrario" invece di "M12 non allineato" —
non lo fa fallire, ed e' corretto: su 682 segnali nessun timeframe e' mai
neutro, quindi le due scritture coincidono. Misurato, non supposto.

## Cosa NON e' stato verificato — la parte utile

1. **L'EA non e' mai stato compilato.** Qui non c'e' MetaEditor: e' stato
   compilato il nucleo con g++, non il `.mq5`. Errori di sintassi MQL5 nel
   guscio (ordini, gestione, log) sono possibili e vanno visti al primo
   `Compile`.
2. **Le uscite non sono confrontate con niente.** Il confronto copre gli
   ingressi. La gestione B (trailing MFE−2R da +3R, weekend sopra +1R,
   scadenza 30 giorni) e' stata scritta seguendo `cammina()` in
   `trading/scripts/run_filtro_weekend.py`, ma nessuno l'ha misurata: e' il
   primo controllo da fare col backtest MT5.
3. **Fill, spread e ordine fra stop e obiettivo** non esistono nel confronto.
   Se stop e obiettivo cadono nella stessa candela la ricerca conta lo stop;
   un backtest MT5 che conti il take darebbe numeri piu' belli e non
   confrontabili.
4. **Lo scarto server-UTC** e' calcolato a runtime da `TimeCurrent()` e
   `TimeGMT()` e arrotondato alla mezz'ora, ma non e' mai stato provato contro
   un broker vero. E' la trappola che ha gia' reso irreali il 62% dei segnali:
   al primo avvio, controllare nel log la riga "scarto server-UTC" e che sia
   quello atteso (FP: +2h o +3h).
5. **Il riavvio con una posizione aperta** usa le variabili globali del
   terminale per non perdere il rischio iniziale. Mai provato.
6. **Lo swap** non e' modellato da nessuna parte: sulla B, che attraversa le
   notti e i fine settimana, incide (long −71,5 punti a notte su FP,
   triplicati il mercoledi').

## Prima di metterlo su un conto

L'ordine sta in `docs/AVVIO-MT5-VPS.md` §3 e §4, e il passo 3 non si salta:
backtest MT5 su 2025-01 → 2026-06, motore Python sugli stessi giorni, confronto
operazione per operazione. Il CSV che l'EA scrive (`ScriviCsv = true`) contiene
**ogni segnale valutato** con quali delle sette condizioni erano vere: serve
esattamente a quello. Delle divergenze, senza quel file, si vedrebbe l'effetto
e mai la causa.
