# Ricerca da zero su cinque mercati — protocollo registrato (02/10/2026)

Richiesta dell'utente: ripartire **da zero**, senza i concetti del progetto
(VWAP, order block, volume profile, livelli, Fibonacci, Keltner), guardando il
mercato con i concetti base del trading, per sessione e per mercato. Solo alla
fine, su cio' che regge, si valuteranno i parametri dell'utente.

## Dati e separazione dei periodi

Candele M5, M15, H1, D1 (UTC, etichettate all'apertura) preparate da
`trading/scripts/prepara_ricerca_zero.py`:

| mercato | fonte | scoperta | verifica |
|---|---|---|---|
| XAUUSD oro | Dukascopy | 2009-2017 | 2018-07/2026 |
| SPXUSD S&P 500 | HistData | 11/2010-2017 | 2018-09/2026 |
| NSXUSD Nasdaq 100 | HistData | 11/2010-2017 | 2018-09/2026 |
| XAGUSD argento | HistData | 2010-2017 | 2018-09/2026 |
| GRXEUR DAX | HistData | 11/2010-2017 | 2018-06/2020 (poi la serie e' corrotta) |

**Separazione fisica**: `D:\ricerca_zero\scoperta\` e `D:\ricerca_zero\verifica\`.
Gli agenti di scoperta ricevono SOLO la prima cartella. La verifica si apre
una volta sola, a candidati congelati.

## Costi (round trip, in unita' di prezzo; nessuna operazione e' gratis)

oro 0,40 $ (2009-2019) poi il `SPREAD` di `verifica_bot.py`; S&P 0,55 punti;
Nasdaq 1,50; DAX 1,50; argento 0,025 $. Entrata all'apertura della candela
dopo il segnale; stop e obiettivi toccati dentro la candela; se nella stessa
candela si toccano entrambi, vale lo stop.

## Famiglie di concetti (una per agente)

1. **Orologio e sessioni**: direzione media, volatilita', persistenza per ora
   e per sessione (Asia 0-7, Londra 7-12, New York 12-21 UTC; per gli indici
   anche la sessione cash locale con l'ora legale vera); notte contro giorno.
2. **Momentum contro ritorno alla media** su orizzonti da 5 minuti a 5 giorni:
   il rendimento passato predice quello futuro, e con che segno, per sessione?
3. **Range di apertura e del giorno prima**: rottura o rientro del primo
   tratto di sessione e dei massimi/minimi del giorno precedente.
4. **Volatilita'**: compressione ed espansione (giornate strette, inside day,
   range relativo all'ATR), cosa succede dopo le giornate estreme.
5. **Calendario**: giorno della settimana, inizio/fine mese, prima e dopo
   il fine settimana.
6. **Fra mercati**: oro contro argento, S&P contro Nasdaq (anticipo/ritardo,
   divergenze che rientrano).

## Regole della scoperta

- Ogni agente dichiara **prima di calcolare** l'elenco delle varianti che
  provera' e ne riporta il numero esatto: il totale di tutte le famiglie e' il
  numero di prove per la correzione.
- Ogni effetto si misura **netto dei costi**, per operazione e per anno.
- Placebo obbligatorio (stessi istanti con direzione casuale, o la stessa
  regola su istanti casuali) per ogni candidato.

## Promozione a candidato (tutte vere, sul solo periodo di scoperta)

- netto medio per operazione > 0 dopo i costi;
- **t >= 3** sul netto (soglia per prove multiple, Harvey-Liu-Zhu 2016);
- anni positivi >= 6 su 8 (>= 75%);
- placebo p < 0,01;
- almeno 200 operazioni (100 per regole giornaliere o piu' lente);
- non piu' di 3 candidati per famiglia, 10 in tutto (i migliori per t).

Ogni candidato si congela in `docs/ricerca-da-zero-candidati.md` con la
specifica esatta, prima di aprire la verifica.

## Verifica (una volta sola, 2018-2026)

Passa se: netto > 0, t >= 2, anni positivi >= 2/3. Si riportano tutti i
candidati, anche quelli che falliscono. Un agente avversario controlla
lookahead, fusi orari e costi prima di dare i numeri all'utente.

## Previsioni

1. La maggior parte degli effetti "per ora del giorno" sara' volatilita', non
   direzione: utile per scegliere QUANDO operare, non da sola una strategia.
2. Gli effetti piu' probabili da sopravvivere: momentum/rendimento notturno
   sugli indici, ritorno alla media di breve sui metalli; nessuno sopra 1-2
   punti base netti per operazione.
3. Meno di 3 candidati su 10 passeranno la verifica.
