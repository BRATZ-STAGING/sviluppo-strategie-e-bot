# Cambi intraday — strategia combinata di segnali rari, registrata (04/10/2026)

Decisione dell'utente del 04/10/2026: combinare piu' segnali rari ma solidi
per avvicinarsi a 1 operazione al giorno. Scritto **prima** di eseguire queste
tre regole sul 2018-2026. Il periodo di verifica dei cambi e' stato aperto una
volta (03/10) solo per il candidato C1 (rientro notturno, bocciato): queste tre
regole su quegli anni non sono mai state calcolate.

Onesta': le tre componenti NON hanno superato la promozione della scoperta
(per frequenza o per t), e le coppie di ciascuna sono state scelte sugli stessi
dati 2010-2017 (t e p di scoperta gonfiati). La verifica dice se reggono.

## Le tre componenti (specifica = codice di scoperta invariato)

| id | regola | coppie (congelate) | script | scoperta |
|---|---|---|---|---|
| **S1** | range asiatico A1 (00:00-07:00 Londra), finestra 07:00-08:00 Londra: dopo la prima chiusura M5 fuori dal range, prima chiusura di nuovo dentro entro 12 M5 -> entra CONTRO la rottura; stop S3 = 0,25 x ATR14 dall'entrata; obiettivo 1R, altrimenti uscita 16:00 Londra; solo regime "piccolo" (range/ATR14 <= terzile basso dei 250 precedenti); solo mar-mer-gio | AUDUSD, EURJPY, EURUSD, GBPUSD, USDCHF | `fx_b_aperture.py` (a A1 RIENTRO S3 1R piccolo mar-gio) | 869 op, 0,42/g, +3,70 pip, +0,123 R, t 3,75, 7/8, x1,5 +0,102 R |
| **S2** | a ogni chiusura M5 a Londra (07-12 UTC), se il movimento degli ultimi 15 minuti e' >= 3 s_L (s = ATR14 x sqrt(min/1440)) e il regime di volatilita' e' alto, entra CONTRO; uscita dopo 30 minuti, stop 2 s_H, obiettivo 1 s_H | USDJPY, AUDUSD | `fx_c_media_momentum.py` (L15 H30 Londra k3 stop2/obj1 regime alto, contro) | 85 op, 0,04/g, +6,1 pip, t 4,6, 7/8 |
| **S3** | ultima giornata di borsa del mese: vendi dollaro alle 15:00 Londra, uscita alle 16:00 Londra (fixing WM/R), solo uscita a tempo | USDJPY, GBPUSD, AUDUSD, USDCHF | `fx_d_orari_fissi.py` (LDF PRE FIX- 60' fine mese) | 384 op, 0,19/g, +5,74 pip, t 3,26, 6/8 |

Costi FP Raw del protocollo (`docs/fx-intraday-registrazione.md`), x1 e x1,5.

## Come si combinano

- Ogni componente gira in modo indipendente con le sue regole (una posizione
  alla volta per componente e coppia). Posizioni di componenti diverse sulla
  stessa coppia possono coesistere (conti come ordini separati).
- **Unita' comune: R**, rischio uguale per operazione. S1 e S2 hanno lo stop:
  R = distanza dallo stop. S3 non ha stop: per il dimensionamento si usa
  R = 0,15 x ATR14 (solo unita' di misura, nessuno stop).
- Il risultato della strategia e' la somma in R di tutte le operazioni.

## Criterio di verifica (ipotesi primaria unica: la strategia combinata)

Sul 2018 -> fine dati passa se valgono tutte:
- netto > 0 a costi x1 **e** x1,5 (in R, somma su tutte le operazioni);
- t >= 2 sul netto giornaliero (somme per giornata);
- anni positivi >= 2/3;
- placebo p < 0,01 (direzione casuale su tutte le operazioni insieme, stessa
  gestione, >= 1000 serie, seed fisso);
- frequenza >= 0,5 operazioni per giornata di borsa (target dichiarato: ~0,65).

Le componenti si riportano anche una per una (n, netto, t, anni), solo come
informazione: non decidono il verdetto.

## Previsioni

1. La combinata NON passa.
2. S3 (fixing di fine mese) e' la componente piu' probabile a restare positiva.
3. S2 ha troppe poche operazioni per dire qualcosa da sola.
