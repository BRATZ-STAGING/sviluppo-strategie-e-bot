# Ricerca da zero — ipotesi congelate per la verifica (03/10/2026)

Scritto **prima** di aprire `D:\ricerca_zero\verifica\` (2018-2026), che a
questa data nessuno ha letto. Decisione dell'utente del 03/10/2026.

## Perche' esiste questo file

Il protocollo (`docs/ricerca-da-zero-registrazione.md`) chiedeva candidati con
t >= 3 in scoperta: **nessuna delle ~7.370 varianti** delle sei famiglie (piu'
~110 misure descrittive della sessione parallela, a775c6c) ci arriva. Il
periodo di verifica si usa allora per le **cinque ipotesi su cui piu' prove
indipendenti convergono**, congelate qui sotto. Non sono "candidati promossi":
sono ipotesi che la scoperta suggerisce, da confermare o smentire una volta
sola su anni mai visti. Con 5 prove la soglia di t sale da 2 a **2,6**
(Bonferroni, alfa bilaterale 0,05/5 = 0,01).

## Le cinque ipotesi (specifica = codice di scoperta, invariato)

Ogni regola si esegue con **le stesse funzioni** dello script di scoperta
indicato, cambiando solo la cartella dei dati (scoperta -> verifica). Costi
round trip: oro 0,40 $ nel 2018-2019 poi il `SPREAD` annuo di
`trading/scripts/verifica_bot.py`; S&P 0,55; Nasdaq 1,50.

| id | ipotesi | mercato | regola (dalla scoperta) | script | scoperta |
|---|---|---|---|---|---|
| **H1** | gli indici USA rientrano su base giornaliera | S&P | a ogni ora piena 00-06 UTC, se la variazione sulle 24 h di borsa supera 1 ATR14 D1, entra CONTRO all'apertura della M5 successiva, esci alla stessa ora del giorno feriale dopo; operazioni non sovrapposte | `zero_f2_momentum.py` | n 325, t 2,06, 6/7 |
| **H2** | l'oro sale il venerdi' | oro | giornata 22-22 UTC, long dalla chiusura del giorno valido precedente alla chiusura del venerdi' (CC) | `zero_f5_calendario.py` | n 463, t 2,54, 8/9 |
| **H3** | l'oro sale nella notte asiatica | oro | se la chiusura della M5 delle 00:55 UTC e' sotto l'apertura delle 00:00, long all'apertura delle 01:00, uscita alla chiusura della M5 delle 06:55; nessuno stop | `zero_f1_orologio.py` (R4a, 60 min, solo long) | n 1199, t 2,40, 7/9 |
| **H4** | in volatilita' in calo la rottura dell'oro prosegue | oro | giornata 22-22; regime ATR5/ATR60 < 0,8 a fine giorno k; nel giorno k+1 prima chiusura M5 oltre massimo/minimo di k -> entra nel verso della rottura; stop a meta' del range di k; uscita all'ultima M5 del giorno k+1 | `zero_f4_volatilita.py` (c, CMP, S2, X1) | n 434, t 2,67, 8/9 |
| **H5** | il Nasdaq sale nella settimana dopo le scadenze | Nasdaq | sessione cash, long dalla chiusura del venerdi' delle scadenze (terzo venerdi') alla chiusura dell'ultimo giorno valido della settimana dopo | `zero_f5_calendario.py` (d, OWP) | n 85, t 3,27, 7/7 |

## Criterio (per ipotesi, 2018 -> fine dati)

Passa se valgono tutte:
- netto medio per operazione > 0;
- **t >= 2,6** sul netto (operazioni non sovrapposte o errori robusti, come
  in scoperta);
- anni positivi >= 2/3 degli anni con almeno 10 operazioni (H5: tutti gli
  anni, una operazione al mese);
- placebo p < 0,01 (stesso placebo dello script di scoperta).

Si riportano **tutte e cinque**, comprese quelle che falliscono. Nessuna
variante, filtro o parametro diverso da quello sopra.

## Previsioni

1. Al massimo una ipotesi su cinque passa.
2. H5 (poche operazioni, t alto in scoperta) e' la piu' probabile a sgonfiarsi.
3. H1 mantiene il segno ma non la soglia.

## Controllo con i parametri dell'utente (deciso dall'utente: solo controllo)

La strategia ufficiale dell'utente (VWAP reclaim, `framework/taratura.py`,
gestione B) si riporta sullo stesso periodo come **termine di paragone**, con
l'avvertenza che per lei il 2020-2026 e' dentro il campione su cui e' stata
scelta. Per le ipotesi sull'oro (H2-H4) si misura anche la correlazione del
risultato giornaliero con quello della strategia ufficiale: se e' alta, non
aggiungono nulla di indipendente. I parametri dell'utente **non** si applicano
alle ipotesi.
