# Discrepanze fra i sorgenti e la documentazione

Trovate leggendo i sorgenti al momento del caricamento nel repository
(30/07/2026). Nessuna e' un'opinione: sono confronti fra quello che dice il
codice e quello che dicono gli appunti del progetto.

## 1. I default dell'EA MT5 NON sono i parametri del forward

`KeltnerImpulseBot_MT5.mq5`, righe 43-44:

```
input double ImpulseTargetPercent = 50.0;  // [report10=50]
input double RiskReward           = 1.5;   // [report10=1.5]
```

Il forward gira con **80** e **1.2**. Chi carica l'EA senza preset ottiene
50/1.5, cioe' **una strategia diversa** da quella in esercizio.

Non esistono file `.set`, quindi la configurazione del forward vive solo negli
appunti. **Va salvato un preset** (trascinare l'EA sul grafico → tab Ingressi →
Salva) e committato in `parametri/`: e' l'unico modo di rendere riproducibile il
forward.

## 2. La versione MT5 e quella cTrader non sono equivalenti a default

Confronto dei default fra il "porting" MT5 e l'"originale" cTrader:

| parametro | MT5 | cTrader |
|---|---|---|
| ImpulseTargetPercent | 50 | 80 |
| RiskReward | 1.5 | 1.2 |
| **ATR smoothing** | **Exponential** | **WilderSmoothing** |
| RiskPercent | 1.0 | **2.0** |
| Min SL | 0 | 0 (il run 8 usa 500 pip) |

Due differenze pesano piu' delle altre:

- **lo smoothing dell'ATR e' diverso**: Wilder e Exponential producono bande
  diverse, quindi **segnali diversi**. Non e' una sfumatura: cambia quali
  candele chiudono fuori banda.
- **il rischio a default e' doppio** su cTrader (2% contro 1%).

Conseguenza operativa: un confronto MT5 contro cTrader fatto con i default
confronta due strategie diverse, non due implementazioni della stessa. Per la
validazione del motore (confrontare gli stessi trade) i parametri vanno
allineati esplicitamente, tutti e cinque.

## 3. Il bug OrderDelete e' piu' ampio di come e' annotato

Negli appunti risulta come "esito OrderDelete non verificato → ordini orfani a
mercato chiuso". In realta' `trade.OrderDelete` non viene verificato in **tre**
punti, e uno ha una conseguenza diversa:

| punto | riga circa | conseguenza se la cancellazione fallisce |
|---|---|---|
| scadenza dell'ordine | 284 | ordine orfano, come annotato |
| equity guard | 222 | il bot si ferma ma l'ordine resta a mercato |
| **sostituzione del setup** | **341** | **due ordini pendenti contemporanei** |

Il terzo e' il piu' serio. In `PlaceSetup` la sequenza e': cancella il vecchio
ordine, poi piazza il nuovo. Se la cancellazione fallisce silenziosamente, il
nuovo viene piazzato comunque e restano **due limit attivi**. E `FindOurPending`
ritorna il primo che trova:

```
ulong FindOurPending()
{
   for(int i=OrdersTotal()-1; i>=0; i--)
      ... return tk;      // il primo, non "quello giusto"
}
```

Il secondo ordine diventa invisibile alla logica del bot: non scade, non viene
sostituito, e se si riempie apre una posizione che il bot non sa di avere.
Con `RiskPercent = 1` questo significa **rischio 2% su un trade**.

Da correggere nella v2.1 assieme al resto. La stessa struttura e' presente in
`KeltnerDD_MT5.mq5` (righe 286, 342, 395).

## 4. Il MidReversion non ha l'equity guard

`KeltnerImpulseBot.cs` e `KeltnerImpulseBot_MT5.mq5` hanno
`EquityGuardPercent = 50`, che ferma il bot se il balance scende sotto la
meta'. `KeltnerMidReversionBot.cs` **non ha alcun guard**, e il rischio a
default e' **2%**.

Su un bot mai backtestato, con reversione a rapporto 1:1, senza salvavita e al
2% per operazione: prima di metterlo anche solo in demo va aggiunto il guard e
portato il rischio all'1%, per coerenza con gli altri due.

## Cosa NON ho verificato

Non ho eseguito nulla: sono osservazioni sul codice. In particolare non ho
verificato se il `Comment` dell'ordine sopravvive al broker (la versione
cTrader ci mappa i trade e stampa un avviso se non li trova, quindi il
problema e' noto), ne' se `ExpAtr()` con finestra `AtrPeriod*20` converge allo
stesso valore dell'ATR di cTrader a regime.
