# Trading Framework XAUUSD — Master Spec

> **Nota storica**: la prima versione del framework (fasi A–F, 71 test) è
> andata persa: era stata sviluppata in una sessione remota il cui branch non
> è mai stato pushato. Questa spec descrive la **ricostruzione** del
> 2026-07-07, riprogettata da zero. Da qui in avanti: committare e pushare a
> ogni fase completata.

## Obiettivo

Framework Python per lo studio e il backtesting di strategie su XAUUSD
basate su livelli di prezzo, con dati reali Dukascopy.

## Struttura del repository

```
data/XAUUSD_M1/          # Parquet M1 (BID), un file per anno + README
docs/master-spec.md      # questo documento
docs/sessions/           # note di passaggio di consegne tra sessioni
docs/studies/            # output degli studi (classifiche, report)
trading/framework/       # package Python
trading/scripts/         # download dati, studi, demo
trading/tests/           # suite pytest
```

## Dati

- Fonte: `datafeed.dukascopy.com` — candele M1 **BID** ufficiali
  (`BID_candles_min_1.bi5`, LZMA, record da 24 byte
  `>5if` = offset-secondi, open, close, low, high, volume; prezzi in
  millesimi di USD; mesi 0-based negli URL; orari UTC).
- Copertura: 2020-01-01 → oggi. I minuti senza scambi sono rimossi.
- Nota: lo storico tick grezzo (~40.000 file orari) non è praticabile
  dall'ambiente remoto per il rate limiting del feed; le M1 usate sono
  l'aggregazione ufficiale Dukascopy degli stessi tick.

## Fasi

| Fase | Contenuto | Modulo | Stato |
|------|-----------|--------|-------|
| A | Data layer: load Parquet, validazione, resampling, sessioni | `framework/data.py` | ✅ ricostruita |
| B | Livelli: round, PDH/PDL/PDC, PWH/PWL, range asiatico, swing H1 | `framework/levels.py` | ✅ ricostruita |
| C | Studio di reazione: tocchi, bounce/penetrazione, classifica | `framework/reaction.py` | ✅ ricostruita |
| D | Profili operativi e workflow giornaliero | `framework/profiles.py` | ✅ ricostruita |
| E | Strategie di riferimento (level bounce) | `framework/strategies.py` | ✅ ricostruita |
| F | Suite di test | `trading/tests/` | ✅ 90 test |
| G | Simulatore di backtest event-driven | `framework/backtest.py` | ✅ implementata |
| H | Ottimizzazione parametri e walk-forward | — | ⬜ da fare |
| I | Report performance per profilo/sessione | — | ⬜ da fare |

## Convenzioni chiave

- Tutti i timestamp sono **UTC**; le candele sono etichettate con l'orario di
  apertura.
- Sessioni (ore UTC): asia 00–07, london 07–12, ny 12–21, late 21–24.
- **Nessun lookahead**: i livelli del giorno D usano solo dati < D (il range
  asiatico si attiva alle 07:00 di D).
- Backtest conservativo: prezzi BID, spread come costo fisso per round-trip,
  ordini market eseguiti all'apertura della candela successiva, nella stessa
  candela lo stop prevale sul take profit, ordini rifiutati se il fill è a
  meno di `min_stop_distance` dallo stop (evita size esplosive).
- Studio di reazione: successo = rimbalzo ≥ `bounce_target` prima che la
  penetrazione superi `stop_penetration` (default 3.0 / 1.5 USD, finestra 60').

## Comandi

```bash
cd trading
python3 -m pytest tests/ -q                    # suite di test
python3 scripts/download_m1.py                 # scarica/aggiorna dati (riavviabile)
python3 scripts/build_parquet.py ../data/XAUUSD_M1   # bi5 → Parquet annuali
python3 scripts/run_reaction_study.py          # studio di reazione → docs/studies/
python3 scripts/run_backtest_demo.py           # demo backtest fase G
```
