# Esplorazione descrittiva dell'oro 2009-2014 (sessione Claude Code, 02/10/2026)

**Non e' una famiglia del protocollo e non produce candidati.** E' un primo
sguardo all'oro fatto da una sessione parallela prima di sapere che
`docs/ricerca-da-zero-registrazione.md` era gia' registrato. L'utente ha poi
deciso di **unire le due ricerche sotto quel protocollo** (scoperta 2009-2017,
verifica dal 2018): queste misure sono solo un'indicazione per le famiglie 1, 2
e 5. Tutti i dati vengono dal periodo di scoperta (2009-2014), nessuno dal
periodo di verifica.

Script: `trading/scripts/ricerca_zero_scoperta.py` (panoramica) e
`ricerca_zero_approfondisci.py` (secondo passaggio). Dettaglio in
`D:\ricerca_zero\scoperta_2009_2014\`. Prezzi BID Dukascopy M1, nessun costo
nelle misure lorde. Spread di riferimento 0,35 $.

**Prove fatte** (contano per la correzione se qualcosa viene ripreso): 24 ore,
6 giorni, 5 TF x 5 statistiche di persistenza, 6 celle shock x 4 orizzonti,
5 coppie di finestre di sessione, 2 gruppi di gap, 5 fasce orarie, 7 gruppi
shock: circa **110**.

## Cosa si vede

| fenomeno | misura | t | anni concordi | nota |
|---|---|---|---|---|
| deriva Asia 23-07 UTC (long) | +4,39 pb/giorno, ~0,61 $ | +4,2 | 6/6 | positiva anche nel 2013 (oro -38%); al netto di 0,35-0,40 $ resta ~0,2 $ |
| Londra 07-12 UTC | -3,26 pb/giorno, ~-0,46 $ | -2,7 | 5/6 | meno del costo |
| rollover 21-23 UTC | +0,22 pb/giorno | +0,5 | 4/6 | neutro: la deriva asiatica NON e' l'artefatto dello spread sul BID |
| ora 23 UTC da sola | +2,17 pb | +4,9 | 6/6 | il pezzo piu' forte della deriva |
| dopo H1 con \|z\|>=3, 6 ore nel verso | +0,95 $ medio, 0,36 $ mediano | +2,4 | 5/6 | 712 casi, vinte 50%: vive delle code; ore NY 12-17 +1,26 $ t+2,7 6/6, NY tarda 17-23 al contrario |
| gap della riapertura settimanale | chiuso entro 4h nell'84% | +1,9 | 5/6 | gap mediano 0,62 $ sul BID: in gran parte spread di riapertura |

## Cosa NON c'e'

- **Persistenza da M1 a H1: nulla.** Autocorrelazione al primo passo fra
  -0,007 e -0,001, variance ratio fra 0,96 e 1,01. H4 a 16 passi 1,09
  (leggera continuazione a piu' giorni, coerente col trend 2009-2012).
- **Sotto i 15 minuti il movimento e' piu' piccolo dello spread**: mediana
  |variazione| 2014 di 0,11 $ in 1 minuto (0,31 spread), 0,27 $ in 5 (0,76),
  0,47 $ in 15 (1,34), 0,96 $ in 60 (2,76). Un'idea su M1 muore sui costi
  prima ancora di essere una regola.
- **La prima ora non predice il resto della sessione** (Asia->Londra,
  Londra 7-8, NY 12-13, NY 13-14: |t| <= 1,8).
- **Giorno della settimana**: solo il venerdi' (+13,5 pb, t 2,0) e lo
  spezzone della domenica sera (t 4,2, che e' gia' la deriva asiatica).

## Da verificare dentro il protocollo

La deriva asiatica e' la piu' robusta e va confrontata con l'appendice di
`rr-intraday-study.md` sulla deriva della riapertura delle 18:00 ET (22-23
UTC), probabilmente lo stesso fenomeno. Il suo limite e' il costo: un lordo
di ~0,6 $ al giorno non sopravvive agli spread 2025-26 (0,6-0,9 $).
