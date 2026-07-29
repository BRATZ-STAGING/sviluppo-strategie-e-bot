# Sessione 2026-07-07 — Ricostruzione del framework

## Cosa è successo

La sessione doveva "riprendere" il framework dalle fasi A–F (71 test) citate
nella nota `docs/sessions/2026-07-07-profili-workflow.md`. **Quel lavoro non
esiste nel repository**: il branch della sessione precedente non è mai stato
pushato e il container remoto è stato riciclato. Verificati: storia git
completa, branch remoti, Google Drive. Nulla di recuperabile.

Il framework è stato **riprogettato e reimplementato da zero** (vedi
`docs/master-spec.md`). L'architettura non è identica a quella persa.

## Stato a fine sessione

- ✅ `datafeed.dukascopy.com` raggiungibile (rate limiting aggressivo sui
  burst; lo storico tick completo non è praticabile dall'ambiente remoto —
  si usano le candele M1 BID ufficiali Dukascopy, stessa fonte).
- ✅ Download M1 2020-01-01 → 2026-07-06 con script riavviabile
  (`trading/scripts/download_m1.py`).
- ✅ Parquet annuali in `data/XAUUSD_M1/`.
- ✅ Fasi A–F ricostruite + fase G (simulatore backtest) — **90 test verdi**.
- ✅ Studio di reazione sui dati reali (37.514 tocchi, 2020→2026): classifica
  in `docs/studies/reaction-ranking.md`. Primi: round_50 (32,6%) e round_100
  (32,4%); ultimo: pdc (24,2%). Break-even teorico con target 3$/stop 1,5$ =
  33,3%: nessun kind è profittevole "naive", i round sono i più vicini.
- ✅ Demo backtest (london-reversal, 2024): win rate 33%, PF 0,69 — perde,
  come previsto dallo studio. Il motore ha rivelato e ora gestisce il caso
  "fill troppo vicino allo stop" (min_stop_distance, default 0,5$): senza la
  guardia il sizing esplodeva quando il prezzo correva verso lo stop tra
  decisione e fill.

## Lezioni operative

1. **Pushare sempre** a fine sessione: i container remoti sono effimeri.
2. Commit incrementali a ogni fase, non un commit unico finale.
3. Il feed Dukascopy limita i burst (~7 richieste rapide → 503): il
   downloader usa 6 worker con backoff esponenziale.

## Prossimi passi (fasi H–I)

- Ottimizzazione parametri (target/stop dello studio, RR dei profili) con
  walk-forward per evitare overfitting.
- Report performance per profilo/sessione/anno.
- Eventuale estensione dei detector di livelli (open giornaliero/settimanale,
  VWAP di sessione).

## Aggiornamento — ridefinizione strategia (stessa giornata)

Richiesta: intraday no scalp, stop piccoli, RR 1:5. Svolto:
- Studio RR su 10.580 primi tocchi + 5.435 sweep&reclaim: vedi
  `docs/studies/rr-intraday-study.md` (verdetto onesto: edge 2020-2023,
  morto 2024-2026; scoperto e corretto un lookahead nella confluenza che
  gonfiava i risultati; la scala MFE mostra che il TP non è la leva).
- Nuovi moduli: `framework/rr_study.py` (studio RR + sweep&reclaim con
  MFE/profondità), `framework/reclaim_strategy.py` (SweepReclaimStrategy
  parametrica). Suite a 107 test.
- Fase H avviata: prossimo lavoro = setup di continuazione + regime switch
  con walk-forward (dettagli nel documento di studio).
