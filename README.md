# Sviluppo strategie e bot — XAUUSD

Framework di ricerca e backtest per strategie intraday su XAUUSD (oro), con la
disciplina che serve perche' i risultati siano credibili: nessun lookahead,
ipotesi scritte prima di guardare i numeri, verifica su dati mai usati per
scegliere i parametri.

## Da dove partire

| dove | cosa c'e' |
|---|---|
| `docs/RIPRENDI-QUI.md` | **stato attuale, cosa e' aperto, come si lavora. Leggere per primo.** |
| `CLAUDE.md` | stato del progetto, convenzioni, strade gia' respinte. **Leggere per primo.** |
| `docs/studies/rr-intraday-study.md` | tutte le misure fatte, appendici A-N. I numeri stanno qui, non in chat. |
| `docs/master-spec.md` | architettura e fasi |
| `trading/framework/taratura.py` | la configurazione ufficiale della strategia, in un solo posto |

## La strategia, in breve

Reclaim del VWAP giornaliero su candele M6, con il contesto su H6 e H2.
Si entra quando il prezzo si e' allontanato dal VWAP nel corso della giornata
e poi ci ritorna, chiudendo dalla parte giusta.

- **conferme**: M33 e H12 allineati, **M12 contrario** (si entra sul ritracciamento)
- **filtro di fondo**: chiusura giornaliera contro la sua media a 50 giorni
- **obiettivo** 1:10, **stop a pareggio** a +3R, **rischio** 1% per operazione
- soglie in dollari nei mesi normali, riscalate sull'ATR in quelli ad alta volatilita'

Risultato su gennaio 2020 - luglio 2026: **+171,1 R** su 348 operazioni,
**7 anni positivi su 7**, perdita massima 16,3%, da 10.000 a 49.321 €.
Con lo spread reale misurato sui tick (novembre 2022 in poi): -4%, cinque anni
positivi su cinque.

## Come si lavora qui

```bash
pip install pandas pyarrow pytest tabulate
cd trading && python3 -m pytest tests/ -q          # 182 test
```

I dati M1 (bid, UTC, 2020-2026, un Parquet per anno) sono in `data/XAUUSD_M1/`.
I tick bid+ask **non** stanno nel repository: pesano oltre un gigabyte, e come
si trasferiscono e si usano e' spiegato in `docs/consegna-tick.md`.

Gli script in `trading/scripts/` producono gli studi. Ognuno salva il
dettaglio su Parquet e stampa solo aggregati compatti: le regole per non
sprecare contesto nelle analisi sono in `CLAUDE.md`.

## Cosa NON fare

Le strade gia' misurate e respinte sono elencate in `CLAUDE.md`. Non
ripercorrerle: i numeri ci sono, ripetere lo studio costa tempo e non cambia
la risposta.
