# Trading Framework XAUUSD

Framework Python per lo studio e il backtesting di strategie su XAUUSD
basate su livelli di prezzo, con dati reali Dukascopy.

- Spec completa: [`docs/master-spec.md`](../docs/master-spec.md)
- Dati: [`data/XAUUSD_M1/`](../data/XAUUSD_M1/) (Parquet M1, un file per anno)
- Studi: [`docs/studies/`](../docs/studies/)

## Requisiti

```bash
pip install pandas pyarrow pytest
```

## Quick start

```bash
cd trading
python3 -m pytest tests/ -q                          # 90 test
python3 scripts/run_reaction_study.py                # classifica reazione livelli
python3 scripts/run_backtest_demo.py london-reversal # demo backtest (fase G)
```

## Moduli

| Modulo | Contenuto |
|--------|-----------|
| `framework/data.py` | caricamento Parquet, validazione, resampling, sessioni |
| `framework/levels.py` | livelli: round, PDH/PDL/PDC, PWH/PWL, range asiatico, swing H1 |
| `framework/reaction.py` | studio di reazione: tocchi, bounce/penetrazione, classifica |
| `framework/profiles.py` | profili operativi e piano giornaliero |
| `framework/strategies.py` | strategia di riferimento LevelBounce |
| `framework/backtest.py` | simulatore event-driven M1 (fase G) |
