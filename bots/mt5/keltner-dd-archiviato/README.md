# KeltnerDD — MT5 · ARCHIVIATO

Variante di `keltner-impulse` con una martingala a un livello: in drawdown dello
0,5% aggiunge una posizione. **Idea bocciata**, il file resta solo come
riferimento di cosa e' stato provato.

## Cosa cambia rispetto all'originale

Stessa base, piu' un ingresso aggiuntivo quando la posizione va in perdita dello
0,5%. Magic 20260706.

## Perche' e' archiviato

Test A/B su tick reali, stessa finestra e stessi input, unica differenza
l'aggiunta:

| variante | esito |
|---|---|
| senza aggiunta | +1,3 R |
| **con aggiunta** | **-21,6 R** |

L'aggiunta in drawdown peggiora il risultato di 23 R. Non e' un caso limite ne'
una questione di taratura: mediare in perdita trasforma perdite piccole in
perdite grandi, ed e' esattamente quello che si misura qui.

Non riprovare questa strada su varianti dello stesso bot.
