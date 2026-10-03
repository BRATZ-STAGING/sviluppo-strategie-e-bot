# Multi-giorno sul paniere — candidati congelati per la verifica (04/10/2026)

Scritto **prima** di eseguire queste regole su `D:\ricerca_multi\verifica\`
(2018 -> fine dati). Protocollo: `docs/multigiorno-paniere-registrazione.md`
(commit a806f1d).

## Scoperta 2010-2017

| famiglia | varianti | candidati |
|---|---|---|
| F1 trend canonico (`multi_f1_trend.py`) | 7 regole x 2 | 0 |
| F2 ritorno alla media (`multi_f2_ritorno.py`) | 3.072 | 3 (stesso fenomeno) |
| F3 forza relativa (`multi_f3_forza.py`) | 432 | 0 |
| F4 breakout (`multi_f4_breakout.py`) | 1.152 | 1 |

**k = 4 -> soglia di verifica t >= 2,6** (tabella del protocollo).

## Candidati (specifica = codice di scoperta invariato)

Regole comuni F2: 1R = 2 x ATR20; segnale alla chiusura della giornata 22->22
UTC, entrata all'apertura della giornata dopo, uscita alla chiusura della
giornata H; una posizione alla volta per mercato. Long se la variazione su L
giornate e' <= -k x ATR20 **e** la chiusura e' sopra la media 200; short
simmetrico sotto la media 200.

| id | universo | regola | scoperta |
|---|---|---|---|
| **M1** | S&P (SPXUSD) | L=5, k=1,5, tenuta 5, stop 2 x ATR20 | 65 op, +0,396 R, t 4,85, 7/7, p 0,001 |
| **M2** | S&P + Nasdaq + DAX (rischio uguale) | L=5, k=2, tenuta 3, nessuno stop | 156 op, +0,237 R, t 4,56, 7/7 |
| **M3** | Nasdaq (NSXUSD) | L=3, k=1,5, tenuta 3, stop 2 x ATR20 | 71 op, +0,289 R, t 3,99, 6/7 |
| **M4** | oro + argento (rischio uguale) | F4 "N20 R S3 D5 F1": giornata valida, flat, ATR20/ATR100 < 1 alla chiusura del giorno prima, chiusura del giorno prima strettamente dentro il canale delle 20 giornate precedenti; buy stop al massimo e sell stop al minimo a 20 giornate (il primo toccato, l'altro annullato; all'apertura se la supera); stop 3 x ATR20 (1R) attivo subito; uscita alla chiusura della 5a giornata dopo l'entrata; nuova entrata dal giorno dopo l'uscita | 256 op, +0,153 R, t 3,42, 7/8, p 0,001 |

Note: M1-M3 sono lo stesso fenomeno (comprare i ribassi degli indici sopra la
media 200) su universi che si sovrappongono; il loro t di scoperta e' il
picco di un altopiano (atteso ~3). Il DAX nella verifica c'e' solo fino al
12/06/2020 (serie corrotta dopo): M2 in verifica e' di fatto S&P + Nasdaq
dal 2020. M4 si riporta anche **senza l'oro** (solo argento), perche' il trend
dell'oro 2009-2026 e' gia' stato visto (appendice CD).

## Criterio di verifica (per candidato, 2018 -> fine dati)

Passa se valgono tutte: netto > 0 a costi x1 e x1,5 con swap; **t >= 2,6**
(stesso metodo della scoperta: rendimenti mensili); anni positivi >= 2/3;
placebo p < 0,05 (stessi placebo della scoperta; per M1-M3 entrambi, direzione
e date casuali).

## Previsioni

1. Almeno uno fra M1-M3 resta positivo, ma sotto t 2,6 (operazioni poche:
   ~0,8-1,8 al mese).
2. M4 non passa (picco di un campo con t mediano 1,5).
3. Il 2020 (crollo di marzo) sara' l'anno peggiore per M1-M3.
