# Oro intraday con i costi veri del conto FP Markets Raw — registrazione (06/10/2026)

## Il fatto nuovo (misurato, non scelto)

Tutti gli studi intraday sull'oro hanno usato lo spread **Dukascopy**: 0,33-0,40 $
fino al 2024, **0,63 $** nel 2025-26 (+ 0,06 $ di commissione in alcuni). Il conto
dell'utente e' **FP Markets Raw**, che pubblica per XAUUSD (pagina "Metal CFD
Spreads" di fpmarkets.eu, letta il 06/10/2026): **spread medio 0,11 $ (Raw),
0,25 $ (Standard), minimo 0,06 $**. I tick veri di un altro demo (MetaQuotes)
danno 0,17 $ di mediana nel 2025-26 (0,32 $ al 90° percentile). Lo storico FP
non e' leggibile ora (il terminale e' collegato a un altro server, usato da
un'altra sessione).

Con commissione (~0,07 $/oncia andata e ritorno) il costo reale Raw e' circa
**0,18 $**, contro 0,46-0,69 $ usati: i costi dell'oro erano sovrastimati di
2,5-4 volte. Questo puo' cambiare il verdetto di regole intraday con vantaggio
lordo fra 0,2 e 0,6 $.

## Costi da usare (oro, round trip, ogni anno)

- **Base: 0,20 $** (spread medio Raw 0,11 + commissione 0,07, arrotondato).
- **Prova di resistenza: 0,30 $** (spread del 90° percentile).
- Il verdetto richiede netto > 0 con **entrambi**. Per riferimento si riporta
  anche il risultato con i costi vecchi.
- Negli istanti di annunci macro e fra 20:45 e 22:15 UTC restano le regole
  degli studi originali (rollover vietato o x2).

## Cosa si rifa' (solo oro, griglie e regole IDENTICHE agli studi originali)

| studio | script | griglia |
|---|---|---|
| ricerca da zero F1 orologio | `zero_f1_orologio.py` | varianti XAUUSD |
| ricerca da zero F2 momentum/rientro | `zero_f2_momentum.py` | varianti XAUUSD |
| ricerca da zero F3 range | `zero_f3_range.py` | varianti XAUUSD |
| ricerca da zero F4 volatilita' | `zero_f4_volatilita.py` | varianti XAUUSD |
| crollo -> conferma, parte intraday | `crollo_conferma_scoperta.py` | M15, H1 |

Scoperta **2009-2017**, stessi criteri di promozione degli studi originali
(t >= 3, anni >= 75%, placebo p < 0,01, netto > 0 con entrambi i costi), stessi
placebo e semi. **Esclusi** dalla promozione, perche' gia' verificati sul
2018-2026 e quindi con esito noto: H2 (oro long il venerdi'), H3 (oro long
notte asiatica dopo prima ora in calo), H4 (rottura con ATR5/ATR60 < 0,8).

## Verifica (una volta sola, oro 2018 -> 07/2026)

Soglia di t per numero di candidati k: 2 (k=1), 2,4 (2-3), 2,6 (4-5), 2,8
(6-10). Netto > 0 a 0,20 e 0,30 $; anni >= 2/3; placebo come in scoperta.

## Previsioni

1. Con 0,20 $ compaiono candidati nelle famiglie di rientro di breve (F2) e
   nel range di apertura di Londra (F3), dove il lordo era 0,15-0,35 $.
2. Meno della meta' dei candidati regge a 0,30 $.
3. Al massimo uno passa la verifica.
