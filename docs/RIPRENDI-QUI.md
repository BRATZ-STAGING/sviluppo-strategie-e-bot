# Riprendi qui — stato al 04/08/2026

> **La ricerca e' in pausa. Si passa alla produzione.**
> Per portare le strategie su MT5 e avviarle sul VPS: **`docs/AVVIO-MT5-VPS.md`**
> — i tre profili con le taglie, le sette trappole dell'implementazione, il
> confronto obbligatorio contro il motore Python, e l'ordine di avvio.
> Per avviare i bot sul VPS leggere **`docs/CONSEGNA-BOT-2026-08.md`**: contiene
> i numeri veri (spread misurato), quale strategia avviare per prima e perche',
> le tre decisioni da prendere prima di partire, e le dieci strade gia' chiuse
> che non vanno ripercorse. Questo file resta come storia di come ci si e'
> arrivati.


Passaggio di consegne da una sessione precedente. Chi apre questo repository
per la prima volta legge questo file, poi `CLAUDE.md`.

## Cosa esiste e a che punto e'

### La strategia di ricerca: tarata e validata

`trading/framework/taratura.py` contiene la configurazione ufficiale. Reclaim
del VWAP giornaliero su M6, contesto H6+H2, conferme M33 e H12 allineati con
M12 in ritracciamento, obiettivo 1:10, stop a pareggio a +3R, rischio 1%.

| | |
|---|---|
| periodo | gen 2020 - lug 2026 |
| operazioni | 348 |
| risultato | **+171,1 R** (+0,492 per operazione) |
| anni positivi | **7 su 7** |
| perdita massima | 16,3% |
| conto da 10.000 € | 49.321 € |
| con lo spread reale (da nov 2022) | -4%, cinque anni positivi su cinque |

**Non cambiare questi parametri senza una verifica fuori campione.** Il test
`trading/tests/test_taratura.py` li blocca proprio per costringere a passare da
una verifica esplicita.

### I bot in esercizio: nessun vantaggio dimostrato

Quattro bot Keltner in `bots/`, con sorgenti, schede e discrepanze. Il migliore
(`mt5/keltner-impulse`) e' in forward demo da 21 operazioni con +5,13R, ma i
backtest su tick reali sono **negativi** (2024-26: 42,4% vincenti, -49,8R).
Leggere `bots/DISCREPANZE.md` prima di toccarli: i default dei sorgenti non
sono i parametri in esercizio, e c'e' un bug che puo' portare a due ordini
pendenti contemporanei.

### I dati

`docs/dati-disponibili.md` dice esattamente cosa copre cosa. In sintesi:

- **candele M1** nel repository, 2020-2026, complete
- **tick bid+ask** sul PC dell'utente (non nel repository, 1,2 GB): nov 2022 -
  lug 2026, 222 milioni di tick, zero ore mancanti
- backfill tick gen 2020 - ott 2022 in corso sul PC
- cache tick del broker FP dentro MT5: **non verificata**

## Il laboratorio pubblicato

La pagina interattiva del laboratorio e' pubblicata qui:

    https://claude.ai/code/artifact/b107a757-b34e-446e-95e1-70932ea9de46

Si apre con la taratura ufficiale gia' impostata. Per aggiornarla: rigenerare
con `build_lab.py` e ripubblicare **passando quell'indirizzo**, altrimenti si
crea una pagina nuova e il link vecchio resta indietro.

## Prompt di apertura per una sessione nuova

Da incollare come primo messaggio:

> Leggi `docs/RIPRENDI-QUI.md`, poi `CLAUDE.md`. Se il compito e' la campagna
> backtest sui Keltner, leggi anche `docs/campagna-keltner-registrazione.md` e
> seguila: e' un protocollo registrato prima dei test, non una proposta.
>
> Tre vincoli che non vanno violati: non cambiare `framework/taratura.py` senza
> verifica fuori campione; non ripercorrere le strade elencate come respinte in
> `CLAUDE.md`; pushare spesso, perche' i container vengono ricreati e il lavoro
> non pushato sparisce.
>
> Dimmi da dove parti prima di iniziare.

L'ultima riga serve a verificare che abbia letto: se riassume male lo stato,
conviene correggerlo subito invece di scoprirlo tre ore dopo.

## Cosa e' aperto

1. **Spread misurato: fatto per 218 operazioni su 348, mancano le prime 130.**
   `docs/spread-misurato-taratura.csv` copre da novembre 2022 (i tick iniziano
   li'): tutti gli anni dal 2023 in poi sono verificati, il 2020, il 2021 e il
   2022 fino a ottobre **no**. Il forward del bot e' invece completo
   (`bots/mt5/keltner-impulse/forward/spread-dukascopy.csv`, 21 su 21).

   | anni | operazioni | con spread misurato |
   |---|---|---|
   | 2020 - ott 2022 | 130 | **0** |
   | nov 2022 - 2026 | 218 | 218 |

   Chiuderlo dipende dal backfill tick 2020 - ott 2022 sul PC dell'utente. Ordine
   dei comandi, uno alla volta: `copertura_cache.py` (cosa c'e'),
   `verifica_cache_tick.py` (e' leggibile), `build_tick_parquet.py` sui mesi
   nuovi, `misura_spread.py` con `docs/operazioni-taratura-ufficiale.csv`.
   Torna indietro un CSV di poche decine di KB: i tick restano sul suo PC.

2. **Order block.** Il bot dell'utente li usa ma **non sono mai stati definiti
   operativamente**. Serve deciderlo con lui: quale candela li genera, quando si
   considerano consumati, quanto restano validi. Finche' non e' definito non si
   possono testare.

3. **Campagna backtest storico sui Keltner.** Griglia e protocollo sono
   **registrati preventivamente** in `docs/campagna-keltner-registrazione.md`,
   con tre previsioni dichiarate prima di eseguire i test. Leggere quel
   documento e seguirlo: non e' una proposta, e' il piano concordato. In
   sintesi: validare prima il motore contro un run MT5 noto, poi 15 run una
   dimensione alla volta, la griglia completa da 150 solo se le singole
   dimensioni mostrano qualcosa, selezione su 2022-11→2024-12 e verifica su
   2025-01→2026-07 mai usato per scegliere, spread reale dai tick istante per
   istante.

4. **Correzioni ai bot**: il bug OrderDelete (tre punti, vedi DISCREPANZE), il
   preset del forward da salvare come `.set`, e l'equity guard mancante sul
   MidReversion.

5. Verificare che la chiusura di fine giornata non scatti di venerdi'
   (posizioni portate sul weekend). Controllo mai fatto.

## Come si lavora qui

Le regole stanno in `CLAUDE.md` e non sono decorative: sono state pagate.

- **Mai stampare dati grezzi in chat.** Gli script salvano su Parquet e stampano
  aggregati compatti.
- **Ipotesi pre-registrate**, verifica per anno, selezione su un periodo e
  conferma su un periodo mai usato per scegliere. Il grid-mining di filtri
  produce configurazioni che crollano fuori campione: misurato, la migliore in
  campione faceva +0,63 R/op e fuori campione +0,03.
- **Confronti a parita' di perdita massima**, non di percentuale rischiata.
- **Le strade respinte sono elencate in `CLAUDE.md`**: non ripercorrerle, i
  numeri ci sono.
- **Push frequenti.** I container sono effimeri: durante la sessione precedente
  se ne sono ricreati cinque, e ogni volta il lavoro non pushato e' sparito.

## Un dato di contesto sull'utente

Lavora da PowerShell su Windows, e i passaggi tecnici vanno dati **un comando
alla volta**, aspettando l'esito prima del successivo. Gli script destinati al
suo PC vanno provati qui prima di consegnarli: e' gia' capitato due volte, e la
seconda lo script girava benissimo e produceva un numero falso che sembrava
vero (lo spread di 0,700 $ su 21 operazioni, in realta' l'ultimo tick del file
ripetuto). La regola completa e' in `CLAUDE.md`, sezione "L'ambiente
dell'utente"; le prove stanno in `trading/tests/test_script_pc.py` ed
eseguono davvero quegli script su dati finti, compreso il caso in cui i dati
non bastano.
