# KeltnerImpulseBot — MT5

Expert Advisor in forward su conto demo. **Il vantaggio non e' dimostrato**: i
backtest su tick reali sono negativi e il forward e' troppo corto per dire
qualcosa. Il forward serve a raccogliere dati, non a validare.

## Cosa fa

Canale di Keltner su XAUUSD M10. Entra sull'impulso quando il prezzo raggiunge
una percentuale dell'obiettivo del canale, con stop sulla struttura e obiettivo
a rapporto fisso.

Sorgente di verita': `KeltnerImpulseBot_MT5.mq5` in questa cartella (v2 con
filtro HTF). **Non** la copia che sta in `Documents` sul PC di origine.

## Stato

| | |
|---|---|
| conto | **demo, mai reale** (regola di progetto) |
| forward dal | 05/07/2026 |
| broker | FP Trading LLC, conto demo hedge |
| capitale | ~100.000 € — il broker ne ha dati 100k invece dei 1.000 previsti |
| strumento | XAUUSD, M10 |

**I risultati si misurano SOLO in R, mai in euro**: il capitale del conto demo
non e' quello che si userebbe davvero, quindi qualunque cifra in valuta e'
priva di significato.

## Parametri in uso

| input | valore |
|---|---|
| ImpulseTargetPercent | 80 |
| RiskReward | 1.2 |
| tipo ATR | Exponential |
| MinStopPrice | 0 |
| UseTrendFilter | **false** (il filtro HTF esiste ma e' spento) |
| CommissionPerLotRT | 6 |
| magic | 20260702 |
| rischio per operazione | 1% del balance, size dalla distanza dello stop, arrotondata per difetto |
| equity guard | 50% |

Non esistono file `.set`: per generarli, trascinare l'EA sul grafico → tab
Ingressi → Salva.

## Risultati noti

**Forward demo al 24/07/2026**: 21 operazioni, 57,1% vincenti, **+5,13 R**
(media +0,24 R).

L'intervallo di confidenza su 21 operazioni e' compatibile con il pareggio:
**questo numero non dice nulla**. Servono circa 80 operazioni perche' inizi a
significare qualcosa.

**Backtest su tick reali storici — negativi**:

| periodo | operazioni vincenti | esito |
|---|---|---|
| 8 mesi 2022-23 | 40,9% (pareggio a 45,5%) | sotto il break-even |
| 2 anni 2024-26 | 42,4% | **-49,8 R** |

## Analisi dei CSV del forward

`forward/ANALISI.md` legge i CSV che l'EA scrive da solo. Tre risultati:

- il pareggio (misurato, non dai parametri) e' a **46,1%** di operazioni
  vincenti; osservato 57,1% ma con intervallo di confidenza **36,5% - 75,5%**.
  L'intervallo contiene il pareggio: un bot senza vantaggio fa cosi' o meglio
  **una volta su cinque**.
- **il broker demo quota uno spread finto**: su 21 riempimenti solo tre valori
  distinti (0,23 · 0,24 · 0,50), diciannove volte esattamente 0,23. Dukascopy
  negli stessi istanti: da 0,53 a 7,15 $. Col costo vero il forward scende da
  +5,13 a **+3,77 R** e la probabilita' che sia caso passa dal 21% al **30%**.
- **le cinque operazioni serali (19-23 UTC) sono in perdita** e pagano quattro
  volte il costo delle altre: i picchi di spread cadono nell'ora del cambio
  giornata. Limitando le operazioni alla finestra 7-19 UTC — quella della
  strategia in `trading/`, fissata prima e validata su sette anni — il forward
  sale a +4,14 R su 15 operazioni (+0,276 per operazione).
- delle 91 righe di scarti, 77 sono `REPLACED` e **non sono occasioni perse**.
  Le altre contano: 8 ordini scaduti e **4 segnali persi il 7 luglio perche' il
  trading automatico era disattivato nel terminale**.

## Cosa NON e' verificato

- **Il vantaggio.** Backtest negativi su tick reali, forward positivo ma troppo
  corto. Allo stato: edge non dimostrato.
- Il filtro HTF: presente nel codice ma disattivato, quindi mai messo alla prova
  in forward.
- **Bug noto, in correzione (v2.1)**: l'esito di `OrderDelete` non viene
  verificato, e a mercato chiuso restano ordini orfani.
