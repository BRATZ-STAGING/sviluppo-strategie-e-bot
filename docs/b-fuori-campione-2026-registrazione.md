# Gestione B sul primo fuori campione vero: luglio-ottobre 2026 — registrazione (06/10/2026)

Scritto **prima** di scaricare i dati: l'archivio si ferma al 06/07/2026 e
nessuno studio del progetto ha mai visto un minuto successivo.

## Cosa si misura

- **Periodo**: dal 07/07/2026 all'ultima giornata di mercato completa
  disponibile su Dukascopy al momento del download (la data esatta si scrive
  nel risultato).
- **Dati**: M1 Dukascopy BID, stessi file giornalieri dell'archivio
  (`trading/scripts/estendi_storico.py 2026 2026 --rifai`).
- **Operazioni e gestione**: identiche a `trading/scripts/analisi_b_18anni.py`
  (genera + filtra + B con `cammina`, archivio 2009-2026 caricato intero,
  spread vero 2026 = 0,631 $). Nessun parametro cambia.
- Anche, a parte: il risultato con lo swap FP (long -0,715 $ a notte, short
  +0,325 $, mercoledi' triplo, rollover alle 21 UTC), come in
  `docs/studies/verifica-bot-discrepanze.md`.

## Confronto (descrittivo: con circa 20 operazioni non c'e' test che decida)

Con n = numero di operazioni del periodo:
1. somma R del periodo contro la distribuzione delle somme di **n operazioni
   consecutive** nel 2020-2026 e nel 2009-2019 (tutte le finestre mobili):
   percentile del periodo in ciascuna delle due;
2. rapporto di verosimiglianza approssimato: quanto e' piu' probabile la somma
   osservata sotto la distribuzione 2020-2026 che sotto quella 2009-2019
   (densita' delle finestre mobili, kernel gaussiano);
3. calo massimo dal massimo dentro il periodo, e stato dello spegnimento a -15 R
   per chi fosse partito il 07/07/2026.

## Lettura decisa ora

- **Allarme**: somma sotto il 5° percentile delle finestre 2020-2026, oppure
  calo di 15 R o piu'.
- **Coerente col regime 2020-2026**: percentile fra 5 e 95 nel 2020-2026 e
  rapporto di verosimiglianza > 1.
- Qualunque esito, **non e' una conferma**: venti operazioni non distinguono
  un vantaggio di 0,5 R/op dal caso. Serve solo a sapere se la strategia sta
  gia' cambiando comportamento.
