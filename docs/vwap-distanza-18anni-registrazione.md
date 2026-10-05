# Distanza dal VWAP all'ingresso sul 2009-2019 — registrazione (05/10/2026)

Richiesta dell'utente del 05/10/2026: verificare sui diciotto anni la sola
famiglia che, dopo la correzione della fine giornata (04/10), si stacca dal
placebo nell'appendice BP. Scritto **prima** di calcolare qualunque numero sul
2009-2019, che nessuna misura di questa famiglia ha mai toccato.

## Cosa si misura (identico a BP, `trading/scripts/run_selezione_fine.py`)

- **Operazioni**: `genera(m1, T)` (campione largo, nessun filtro sulle
  conferme), gestione ufficiale (1:10, pareggio a +3R) con `cammina_uno`, chiusura
  all'ultima candela prima delle 21:00 UTC del giorno d'ingresso, costo
  `o["costo"]` come in BP.
- **Misura**: `|entry - VWAP| / respiro`, con VWAP = `anchored_vwap(m1, "day")`
  letto al minuto d'ingresso e respiro = media dell'escursione M1 dei 30
  minuti precedenti (`shift(1)`).
- **Terzi CONGELATI** dal 2020-2026 corretto (1.290 operazioni,
  `selezione_fine.parquet` del 04/10): **basso < 0,6895 <= medio < 1,5879 <=
  alto**. Non si ricalcolano sul 2009-2019. La misura e' in respiri, quindi non
  dipende dal livello del prezzo.

Controllo prima del calcolo: con `XAU_ANNI=2020-2026` lo script nuovo deve
riprodurre BP (1.290 operazioni; terzo medio +0,377 in ricerca e +0,382 in
verifica). Se non coincide, ci si ferma.

## Ipotesi (due, dichiarate ora; soglia di Bonferroni alfa = 0,05/2)

- **H1, quella di BP**: nel 2009-2019 il terzo **medio** rende piu' degli altri
  due.
- **H2, la forma che i numeri 2023-2026 suggeriscono di piu'**: nel 2009-2019 il
  terzo **basso** rende meno degli altri due.

Statistica e placebo: per H1 la differenza R/op medio meno media del resto;
per H2 la media del resto meno il basso. Il placebo rimescola le fasce fra le
operazioni del 2009-2019, 2.000 volte con seme 20261005; p = quota di
rimescolamenti con differenza almeno uguale.

## Criterio

Un'ipotesi **regge** se valgono tutte:
1. la differenza ha il segno atteso;
2. p del placebo < 0,025;
3. la differenza ha il segno atteso in almeno 7 degli 11 anni.

La fascia diventa **utilizzabile come filtro** solo se, in piu', il suo
netto R/op sul 2009-2019 e' > 0 (per H1 il terzo medio, per H2 i terzi medio e
alto insieme).

Si riportano anche, senza che entrino nel verdetto: il 2009-2026 intero, lo
spread a 0,40 $ sul 2009-2019 e il campione ufficiale (conferme filtrate).

## Previsioni

1. H1 non regge: il massimo nel terzo di mezzo e' non monotono e nel
   2023-2026 medio e alto erano gia' pari (+0,382 contro +0,375).
2. H2 ha piu' probabilita' di H1 ma non passa il placebo a 0,025.
3. In ogni caso nessuna fascia ha netto positivo sul 2009-2019, perche' la
   gestione ufficiale perde in quegli anni (-39,6 R nel campione ufficiale).
