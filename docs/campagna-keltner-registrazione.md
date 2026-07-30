# Campagna backtest Keltner — registrazione preventiva

Scritto **prima** di eseguire qualunque test. Serve a distinguere un esperimento
da una pesca a strascico: le previsioni sono qui sopra, e alla fine si guarda
quante ne sono state azzeccate.

Perche' e' necessario: su questo progetto il grid-mining e' gia' stato misurato.
Nell'appendice M la configurazione migliore in campione rendeva +0,63 R/op e
fuori campione **+0,03**. Con 75 combinazioni su un bot il cui vantaggio non e'
dimostrato, qualcosa "vincera'" per forza.

## Prima di tutto: validare il motore

Nessun numero di questa campagna vale niente se il motore non riproduce l'EA.

**Requisito**: un run MT5 su tick reali con finestra e input noti, e lo stesso
periodo rigirato con il motore di questo repository. Devono uscire **gli stessi
segnali** (stessi istanti, stessa direzione, stessi livelli di ingresso, stop e
obiettivo), con tolleranza minima sui riempimenti.

Se i segnali non coincidono, si ferma tutto e si capisce perche' prima di
proseguire. Le differenze attese e accettabili sono solo sui fill; una
differenza nei **segnali** e' un errore di implementazione.

Attenzione ai punti gia' noti in `bots/DISCREPANZE.md`: lo smoothing dell'ATR
differisce fra le due versioni (Exponential su MT5, Wilder su cTrader) e produce
bande diverse, quindi segnali diversi. Va fissato esplicitamente.

## La griglia

Baseline = la configurazione in demo adesso: **M10, RR 1:1,2, impulso 80%**.

| dimensione | valori | n |
|---|---|---|
| timeframe | M3, M6, M10, M12, M15 | 5 |
| Risk/Reward | 1,2 · 1,5 · 2,0 | 3 |
| Target % impulso | 60 · 70 · 80 · 90 · 120 | 5 |
| **finestra oraria** | tutte le ore · **solo 7-19 UTC** | 2 |

150 configurazioni. La quarta dimensione non era nella richiesta ma va aggiunta:
e' la sola su cui esiste gia' un'evidenza (vedi previsione 3).

## Le tre previsioni, dichiarate ora

### 1. I timeframe piccoli faranno peggio (M3, M6 sotto M10-M15)

Non e' un'ipotesi nuova: e' misurato sulla nostra strategia nell'appendice M.
Scendendo di timeframe accadono due cose, entrambe contrarie:

- il vantaggio **lordo** si dimezza (+0,141 R/op su M6 → +0,092 su M3)
- lo spread, fisso in dollari, pesa **il doppio** in R (0,075 → 0,171)

Sul Keltner il meccanismo e' lo stesso: timeframe piu' piccolo → impulso piu'
piccolo → stop piu' stretto → spread piu' pesante in proporzione.

### 2. Le percentuali alte faranno meglio (120 sopra 60), per pura aritmetica

Nel codice `tpDist = ImpulseTargetPercent/100 * impulse` e
`slDist = tpDist / RiskReward`: la percentuale scala **entrambi**, quindi il
rapporto rischio/rendimento non cambia. Cambia l'**ampiezza assoluta** dello
stop, e con essa il peso dello spread.

Numeri dal forward (stop mediano 11,92 $ all'80%, spread Dukascopy 0,63 $):

| Target % | stop mediano stimato | costo spread in R |
|---|---|---|
| 60 | 8,9 $ | 0,071 |
| 80 (attuale) | 11,9 $ | 0,053 |
| 120 | 17,9 $ | 0,035 |

Solo per i costi, passare da 60 a 120 vale **0,036 R per operazione**. Va in
direzione opposta un effetto reale: con obiettivi piu' lontani il prezzo li
raggiunge meno spesso. Se il risultato **non** migliora salendo, significa che
questo secondo effetto e' piu' forte del risparmio sui costi — ed e'
un'informazione, non un fallimento.

### 3. La finestra 7-19 UTC fara' meglio di tutte le ore

Misurato sul forward: le cinque operazioni fra le 19 e le 23 UTC sono in perdita
(-1,53 R col costo vero) e pagano un costo quattro volte piu' alto. I picchi di
spread cadono verso le 22 UTC, nell'ora del cambio giornata, con zero tick nei
60 secondi precedenti.

Sono cinque operazioni, quindi da sole non provano nulla. Ma la finestra 7-19 e'
quella della strategia in `trading/`, fissata prima e validata fuori campione su
sette anni: e' una conferma indipendente, non un ritocco.

### Cosa NON si prevede

Il **Risk/Reward** e' l'unica dimensione senza previsione, e per questo la piu'
interessante. Due effetti opposti:

- salendo di RR lo stop si stringe (`slDist = tpDist/RR`), quindi lo spread pesa
  piu' in R e gli stop scattano piu' spesso
- ma la soglia di pareggio scende: 45,5% a RR 1,2, 40% a 1,5, **33,3% a 2,0**

Quale dei due vinca non e' deducibile a priori. Qui il test serve davvero.

## Protocollo

**Divisione dei dati** (vincolata dalla copertura dei tick, che parte da
novembre 2022):

| | periodo |
|---|---|
| selezione | 2022-11 → 2024-12 |
| **verifica** | **2025-01 → 2026-07** (mai usato per scegliere) |

Il backfill 2020-01 → 2022-10 in corso, quando sara' pronto, allarga la
selezione — **non** la verifica. La verifica resta intoccata.

**Costi**: spread **reale dai tick**, istante per istante, mai un valore fisso.
Piu' la commissione (6 $/lotto round-turn). Motivo: lo spread e' triplicato fra
il 2023 e il 2026 e la verifica cade proprio nel periodo largo — con uno spread
fisso una variante puo' fallire per i costi e non per la logica.

**Soglia minima**: almeno 60 operazioni in selezione e 40 in verifica. Sotto
questa soglia la configurazione si scarta senza commento: non e' misurabile.

**Come si legge il risultato.** Con 150 configurazioni, a caso ne "passano"
circa 7-8 al 5% di significativita'. Quindi:

1. una configurazione sopravvive solo se e' positiva **in selezione E in
   verifica**
2. la classifica finale si fa sul **R/op in verifica**, non in selezione
3. si riporta **quante configurazioni sono passate** e quante ne passerebbero
   per caso: se ne passano 8 su 150, non e' un risultato
4. si riportano **anche i negativi**, incluse le previsioni sbagliate

**Ordine di esecuzione**: prima le tre dimensioni una alla volta partendo dalla
baseline (5 + 3 + 5 + 2 = 15 run, interpretabili), poi la griglia completa solo
se le singole dimensioni mostrano qualcosa. Fare 150 run per primi rende
impossibile capire cosa ha causato cosa.

## Aspettativa dichiarata sul risultato complessivo

I backtest esistenti su tick reali sono **negativi**: 2024-26 con 42,4% di
operazioni vincenti e -49,8 R. Il forward e' positivo ma con il 30% di
probabilita' di essere caso.

**L'aspettativa e' che nessuna configurazione mostri un vantaggio solido.** Se
la campagna si chiude con "nessuna variante regge la verifica", non e' un
fallimento: e' la risposta, ed e' quella che permette di smettere di
lavorarci. Il risultato da temere e' l'opposto: una variante che sembra
eccellente e che nessuno ha verificato abbastanza.

## L'altra strategia

Quella in `trading/` **non entra in questa campagna**. E' gia' tarata e
validata (`framework/taratura.py`), e attende dati nuovi: gli order block, mai
definiti operativamente. Vedi `docs/RIPRENDI-QUI.md` punto 2.
