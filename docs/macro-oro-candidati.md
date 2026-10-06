# Oro macro — candidati congelati per la verifica (06/10/2026)

Scritto **prima** di eseguire queste regole sul 2018 -> 07/2026. Protocollo:
`docs/macro-oro-registrazione.md` (commit 8a771ce).

## Scoperta 2009-2017

| famiglia | varianti | candidati |
|---|---|---|
| A tassi e dollaro (`macro_a_tassi.py`) | 348 | 0 |
| B paura e volatilita' (`macro_b_paura.py`) | 536 | 0 |
| C posizionamento COT (`macro_c_cot.py`) | 288 | 0 |
| D flussi ETF GLD (`macro_d_gld.py`) | 408 | 0 |
| E eventi macro (`macro_e_eventi.py`) | 464 | **2** (stessa idea) |

**k = 2 -> soglia di verifica t >= 2,4.**

## Candidati (specifica = codice `macro_e_eventi.py` invariato)

Calendario: `D:\ricerca_macro\dati\eventi\calendario_2009_2026.csv` (comunicati
FOMC programmati, con l'ora vera: 14:15 NY nel 2009-2012, 12:30 NY nelle
riunioni con conferenza stampa 04/2011-12/2012, poi 14:00 NY; riunioni
straordinarie escluse). Prezzi: M5 BID Dukascopy.

| id | regola | scoperta |
|---|---|---|
| **E-C1** | a ogni comunicato FOMC programmato all'ora T: P0 = chiusura della M5 che termina a T; se la chiusura a T+5m e' sopra P0 compra a T+5m, se sotto vendi, se uguale niente; nessuno stop; uscita alle 20:55 UTC dello stesso giorno | n 71, +0,368 R (x1,5 +0,289), +3,90 $/oncia, t 3,05, 9/9, p 0,001/0,001 |
| **E-C2** | identica con decisione ed entrata a T+15m | n 70, +0,319 R (x1,5 +0,293), t 3,00, 7/9 |

Costi come in scoperta: spread round trip (0,46 $ fino al 2019, poi `SPREAD` di
`verifica_bot.py` + 0,06 $) **piu' un extra x3 dello spread sull'entrata**
vicina all'annuncio; x1 e x1,5.

## Criterio di verifica (per candidato)

Netto > 0 a x1 e x1,5; **t >= 2,4**; anni positivi >= 2/3; placebo p < 0,05
(stessa ora in giorni senza FOMC; direzione casuale).

## Avvertenze dichiarate prima

- Poche operazioni: 8 l'anno (circa 68 in verifica). Le 5 migliori della
  scoperta fanno il 46% del totale: senza di loro t ~ 2.
- Esecuzione: negli istanti dopo un comunicato FOMC lo spread reale e lo
  slittamento possono superare l'extra stimato. Il guadagno lordo in scoperta
  e' ~5,3 $/oncia: la regola regge finche' il costo reale per operazione resta
  sotto ~5 $.

## Previsioni

1. E-C1 resta positivo ma sotto t 2,4 (poche operazioni).
2. Se uno dei due passa, passa anche l'altro (sono la stessa idea).
