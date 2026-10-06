# Perche' la B crolla: le condizioni delle perdite — registrazione (06/10/2026)

Richiesta dell'utente del 06/10/2026: capire a cosa sono dovuti i momenti in
cui la strategia crolla. Scritto **prima** di calcolare. Controllo
dell'archivista dello stesso giorno: la separazione fra le due epoche con
regimi di mercato e' gia' stata cercata (AU-AY, BW, BX: negativa). Sono nuove
la meccanica delle perdite, le discese dentro il 2020-2026, i fattori
all'ingresso misurati in entrambe le epoche e la pendenza della media a 200
giorni (in BX "non verificata": definizione mai scritta; la si scrive qui).

## Dati

Le 712 operazioni B 2009-2026 di `docs/studies/dati/b_operazioni_2009_2026.parquet`
(`analisi_b_18anni.py`: genera + filtra + `cammina` di verifica_bot, spread
vero). Nessuna operazione nuova. Le misure di mercato si calcolano dall'archivio
M1 e sono **note all'ingresso** (solo dati precedenti all'istante d'ingresso;
D1 fino a ieri, con la giornata vera, senza lo spezzone della domenica).

## Domanda 1 — COME perde (descrittiva, nessun test)

Per tre gruppi: 2009-2019; 2020-2026; le tre discese del 2020-2026
(11/04-03/09/2025, 16/07-22/10/2024, 28/01-24/06/2026, date di
`b-prima-della-demo.md`):
- quota di uscite per motivo (stop, protetto/trailing, obiettivo, gap, chiusa
  il venerdi', scadenza), R medio delle vinte e delle perse, quota di vinte;
- scomposizione della differenza di R/op fra le epoche in "piu' perdenti" e
  "vincenti piu' piccole".

## Domanda 2 — QUANDO perde: nove fattori all'ingresso, dichiarati ora

1. **volatilita'**: ATR14 D1 / prezzo
2. **tendenza di fondo**: pendenza della media a 200 giorni, (MA200 di ieri -
   MA200 di 20 giornate prima) / ATR14 di ieri
3. **distanza dalla media a 50 giorni**: (prezzo d'ingresso - MA50 di ieri) /
   ATR14, col segno del lato (positivo = l'operazione va nel verso della
   distanza)
4. **lato**: long / short (binario)
5. **ora d'ingresso UTC**: 07-11, 12-16, 17-19
6. **giorno della settimana** (lunedi'-venerdi', cinque fasce)
7. **ampiezza dello stop**: rischio in $ / ATR14
8. **peso del costo**: spread dell'anno / rischio in $
9. **venerdi' delle buste paga USA**: ingresso nel primo venerdi' del mese
   (approssimazione dichiarata del calendario NFP, che a volte cade il secondo;
   FOMC e CPI fuori, perche' il calendario non e' nel repository)

Fattori continui (1, 2, 3, 7, 8): terzi calcolati sulle 712 operazioni insieme.

**Criterio, uguale per tutti.** Un fattore **spiega i crolli** se:
- la stessa fascia e' la peggiore in **entrambe** le epoche, 2009-2019 e
  2020-2026;
- in ciascuna epoca la differenza R/op (peggiore meno il resto) ha p < 0,0056
  (0,05/9, Bonferroni). Il placebo rimescola le fasce **per giornata** (tutte
  le operazioni dello stesso giorno restano insieme), 2.000 volte, seme
  20261006.

Un fattore che separa una sola epoca si riporta come "solo 2009-2019" o "solo
2020-2026", e non spiega niente: e' quello che il caso produce.

## Domanda 3 — le discese del 2020-2026 (descrittiva)

Le operazioni delle tre discese contro il resto del 2020-2026, sugli stessi
nove fattori: si riporta in che fasce cadono. Nessun test: sono 14-18
operazioni per discesa.

## Previsioni

1. Nessuno dei nove fattori spiega i crolli in entrambe le epoche (coerente con
   BW: il mercato misurato in modo relativo e' lo stesso).
2. La differenza fra le epoche sta soprattutto nelle **vincenti piu' piccole e
   piu' rare** (meno trailing e obiettivi), non in stop piu' frequenti.
3. Se un fattore separa, sara' la tendenza di fondo o il lato (la strategia
   guadagna dove l'oro sale), e solo nel 2020-2026.
