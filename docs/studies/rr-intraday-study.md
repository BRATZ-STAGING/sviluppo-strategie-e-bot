# Studio RR 1:5 intraday — XAUUSD (2020 → 2026-07)

Obiettivo: strategia intraday (no scalp, no overnight) sui livelli, stop
piccoli, RR 1:5. Dati: 2,31M candele M1 BID Dukascopy. Tutti i risultati sono
al netto dello spread (0,30$).

## Percorso e risultati

### 1. Tocco naive con limit sul livello (10.580 primi tocchi)

Stop fissi 0,75–3$, target 5R, uscita EOD 21:00. **Tutte le combinazioni
tipo×stop sono negative** (migliore: round_100, -0,08R). Break-even a 5R con
stop 1$ ≈ 21,7%, ottenuto max 20,2%.

Segnali direzionali reali e coerenti su tutto il campione:
- **supporti > resistenze** (long meglio degli short ovunque, ~+0,15R di gap)
- **sweep profondi > sfioramenti**
- london/ny > asia per follow-through

### 2. Trappola scoperta e corretta: confluenza con lookahead

La prima versione del flag "confluenza" usava anche i livelli asia (noti solo
dalle 07:00) per tocchi notturni: il minimo asiatico si forma spesso proprio
toccando il livello → il flag codificava "il livello ha tenuto".
Con quel bias: pdc+confluenza+long = +0,72R, 7/7 anni positivi (!).
**Con la confluenza onesta (solo livelli già attivi al tocco): +0,16R, 4/7
anni — non robusto.** La confluenza onesta non discrimina (-0,18 vs -0,20).

### 3. Quale TP sostengono i dati (scala MFE sui reclaim long ai supporti)

| TP | raggiunto | break-even lordo |
|----|-----------|------------------|
| 1R | 51,2% | 50,0% |
| 2R | 34,9% | 33,3% |
| 3R | 25,8% | 25,0% |
| 5R | 16,8% | 16,7% |
| 8R | 9,5% | 11,1% |

Il mercato è quasi perfettamente efficiente su queste entrate: **nessun TP
fisso rende profittevole un'entrata senza edge**. Il TP non è la leva; la
leva è il filtro d'ingresso.

### 4. Sweep & reclaim + filtri (modello finale implementato)

Meccanica: penetrazione del livello → chiusura di recupero entro 30' →
entrata, stop sotto il minimo dello sweep (+0,3$ buffer, rischio 0,8–3$),
target 5R, chiusura forzata 21:00. Filtri: solo long ai supporti, profondità
sweep ≥ 1$, sessioni london+ny, momentum D1 rialzista (close ieri > close di
5 sedute prima — ipotesi pre-registrata, confermata: +0,30R vs -0,11R del
controllo ribassista).

**Backtest col motore event-driven** (spread 0,30$, rischio 1%, una posizione
alla volta): 191 trade, PF 1,31, +85% totale, max DD 32,5%. Per anno:

| Anno | n | Win | PnL ($, su 10k) |
|------|---|-----|-----------------|
| 2020 | 31 | 39% | +2.897 |
| 2021 | 29 | 31% | +1.787 |
| 2022 | 26 | 38% | +3.192 |
| 2023 | 30 | 33% | +4.048 |
| 2024 | 43 | 16% | **-2.680** |
| 2025 | 30 | 20% | **-322** |
| 2026 | 2 | 0% | **-421** |

## Verdetto

**Non tradabile così com'è.** L'edge del mean-reversion sui livelli è
esistito nel 2020-2023 ed è morto nel 2024-2026: nel regime di trend forte
recente né i long ai supporti né gli short alle resistenze pagano a 1:5.
Un backtest "medio" sul periodo intero (+85%) sarebbe fuorviante: gli ultimi
2,5 anni — gli unici che contano per il futuro prossimo — sono in perdita.

## Prossimi passi (fase H)

1. **Setup di continuazione** per regime di trend (breakout-retest: solo 75
   casi nel campione reclaim, serve una definizione dedicata, non è conclusa).
2. **Regime switch**: classificatore trend/range su D1-H4 che decide QUALE
   meccanica usare (reversion nel range, continuation nel trend), con
   walk-forward reale.
3. Qualità della conferma (volume/momentum della candela di reclaim).
4. La strategia è già parametrica (`ReclaimStrategyConfig`): ogni variante
   futura è una riga di config, non nuovo codice.

---

# Appendice — Studio multi-timeframe (continuazione)

Modello proposto (sequenza H6→H2→M10→M6, VWAP ancorati al posto di EMA/fibo):
implementati `framework/structure.py` (swing frattali causali, BOS/CHOCH,
stato di trend per TF) e `framework/vwap.py` (VWAP ancorati giorno/settimana).
Registro TF completo in `data.TIMEFRAMES` (inclusi M33/M66 non nativi MT5).

## Esperimento A — reclaim sui livelli + contesto strutturale H6/H2

Il filtro migliora monotonicamente (-0,11 → -0,02R) ma nessuna cella è
robusta e il 2024-26 resta negativo ovunque: la reversion sui livelli statici
è morta nel regime recente anche con il contesto giusto.

## Esperimento B — continuazione: pullback al VWAP in doppio uptrend

Setup: H6 e H2 in uptrend strutturale, pullback M6 che tocca il VWAP
giornaliero, candela di conferma (close > VWAP e > massimo precedente),
stop sotto il minimo del pullback (+0,3$ buffer, rischio 1-10$, mediano
~3,8$), TP a griglia, EOD 21:00. 1.205 setup long in 6,5 anni.

| Filtro | n | 3R expR | anni+ | 2024-26 (3R) |
|--------|---|---------|-------|--------------|
| tutti | 1.205 | -0,026 | 2/7 | +0,088 |
| impulso ≥ 4$ | 990 | **+0,040** | 4/7 | **+0,137** |

Per anno (3R, tutti): 2020 -0,10 · 2021 -0,24 · 2022 -0,01 · 2023 -0,01 ·
2024 +0,00 · 2025 **+0,28** · 2026 -0,41 (n=33, campione piccolo).

## La scoperta strutturale

Le due meccaniche sono **immagini speculari nei regimi**:

| Regime | Reversion (reclaim livelli) | Continuation (VWAP pullback) |
|--------|------------------------------|-------------------------------|
| 2020-2023 | ✅ +0,3/+0,9R per anno | ❌ ~0 / negativa |
| 2024-2026 | ❌ negativa ovunque | ✅ positiva (2024-25) |

Nessuna delle due è un edge standalone; il pattern "dietro ai trend
vincenti" è il **regime**. Direzione fase H: classificatore di regime
(trend/range su D1-H4) che seleziona la meccanica, walk-forward reale,
e raffinamento del trigger M6 (displacement/FVG, qualità del pullback M10)
testato senza data mining.

---

# Appendice 2 — Precisione dell'entrata (studio appaiato, 1.037 setup)

Confronto appaiato sugli stessi setup di continuazione (impulso ≥4$),
TP 3R, EOD 21:00. Script: `scripts/run_entry_study.py`.

## Come entrare

| Entrata | Fill | Rischio med. | expR/trade | expR/setup | 2024-26 |
|---------|------|--------------|-----------|------------|---------|
| **market al close conferma** | 100% | 4,37$ | **+0,046** | **+0,046** | **+0,132** |
| stop-buy sopra conferma | 89% | 4,71$ | +0,010 | +0,008 | +0,102 |
| limit 50% conferma | 83% | 3,39$ | +0,036 | +0,030 | +0,069 |
| limit al VWAP | 81% | 3,44$ | +0,018 | +0,015 | +0,060 |

**Vince l'entrata immediata.** Aspettare il retracement è selezione avversa
(i movimenti migliori partono senza di te); chiedere conferma extra costa
più di quanto rende.

## Dove mettere lo stop

| Stop | Rischio med. | expR |
|------|--------------|------|
| **sotto il minimo del pullback** | 4,37$ | **+0,046** |
| sotto la candela di conferma | 2,33$ | -0,115 |
| sotto il VWAP -0,5$ | 1,27$ | -0,312 |

E per distanza entry→stop: <3,5$ → -0,02 · 3,5-5,5$ → **+0,09** · >5,5$ → +0,07.

**La precisione NON è lo stop stretto**: comprimere lo stop sotto la
struttura distrugge l'expectancy. Lo stop va al minimo strutturale del
pullback; gli "stop piccoli" giusti arrivano dalla selezione del setup
(sweet spot 3,5-5,5$), non dalla compressione.

## Note

- Sorpresa displacement: conferme modeste (corpo <50% del range) rendono
  più delle esplosive (+0,074 vs +0,040; n=186, da riverificare).
- Baseline per anno: 2020 -0,12 · 2021 -0,17 · 2022 +0,18 · 2023 +0,11 ·
  2024 +0,07 · 2025 +0,29 · 2026 -0,41 (n=33). Il 2026 resta il campanello
  d'allarme: prima del live serve il walk-forward con classificatore di
  regime.

---

# Appendice 3 — Fase H: selettore di meccanica in walk-forward

Moduli: `framework/regime.py` (efficiency ratio di Kaufman, serie di regime
causale), `scripts/run_walkforward.py`. Due flussi di trade:
REVERSION (sweep&reclaim long supporti, depth≥1$, london+ny, 5R) e
CONTINUATION (pullback VWAP in doppio uptrend, impulso≥4$, market@close, 3R).

Selezione mensile con SOLO dati passati (trailing 6 mesi, ≥12 trade,
expR>0 richiesta; nessuna meccanica valida → flat).

| Sistema | n | expR | tot R | max DD | 2024-26 |
|---------|---|------|-------|--------|---------|
| solo continuation | 1.037 | +0,046 | +48R | 73R | +54R |
| solo reversion | 402 | +0,103 | +42R | 84R | **-36R** |
| entrambe sempre | 1.439 | +0,062 | +89R | 61R | +19R |
| **trailing-switch (WF)** | 625 | **+0,115** | +72R | **38R** | **+44R** |
| regime-switch (ER fisso) | 630 | +0,065 | +41R | 104R | +11R |

Per anno (trailing-switch): 2020 -1R · 2021 +17R · 2022 +32R · 2023 **-21R**
(anno di transizione: il trailing insegue il regime con ritardo) · 2024 +0R ·
2025 +55R · 2026 -11R (n=14). Il selettore è migrato da sola-reversion
(2020-21) a sola-continuation (2024-26) da solo, ed è rimasto flat 19 mesi
su 78.

## Conclusioni fase H

1. Il **meta-sistema batte ogni componente**: più expectancy, metà drawdown,
   e sopravvive al cambio di regime che uccide le singole meccaniche.
2. Il selettore semplice (performance trailing) batte la feature di regime
   a soglia fissa.
3. Costi onesti: ritardo di transizione (2023) e recente 2026 ancora debole.
4. **Avvertenza metodologica**: i filtri interni dei due flussi sono stati
   scelti sull'intero campione; il walk-forward valida la regola di
   switching. Prima del live: paper trading / dati nuovi per validare i
   setup out-of-sample.

## Backtest del meta-sistema nel motore (fill, costi, una posizione alla volta)

`framework/meta.py` (MetaSignalStrategy), 134 test. Spread 0,30$, rischio
1%/trade, equity iniziale 10.000$:

- 451 trade (le collisioni di posizione filtrano ~28% dei segnali)
- **win rate 31,9%** — win medio 364$ vs perdita media 145$ (2,52:1)
- **profit factor 1,18** · expectancy +17,8$/trade
- **+80,2%** totale (10.000 → 18.020) ≈ +9,5%/anno composto
- **max drawdown 19,4%**
- per meccanica: continuation +5.593$ (302 trade), reversion +2.427$ (149)
- per anno: 2020 -97 · 2021 +1.274 · 2022 +3.515 · 2023 -1.458 ·
  2024 +870 · 2025 +5.738 · 2026 -1.822 (13 trade)

Il vantaggio del walk-forward è sopravvissuto agli attriti di esecuzione.
Restano: transizioni di regime costose (2023), 2026 debole, e la nota
metodologica sui filtri scelti in-sample → serve forward test.

---

# Appendice 4 — Ri-validazione da zero e riparametrizzazione in ATR

## Ri-validazione indipendente (2026-07)

Due sviluppatori indipendenti hanno reimplementato la strategia continuation
da una specifica in prosa, senza accesso al codice ne' ai risultati:

| | segnali | R medio | a obiettivo |
|---|---|---|---|
| implementazione originale | 1.037 | +0,046 | 20,3% |
| replica 1 | 1.038 | +0,047 | 20,0% |
| replica 2 | 1.013 | +0,044 | 19,9% |

Concordanza anche anno per anno. **I numeri della continuation sono confermati.**

Audit paralleli (dati, look-ahead, motore, riproducibilita'): nessun
look-ahead trovato nei moduli; confermati tre difetti reali —
`resample_tf` M33/M66 dipende dagli anni caricati, `resample('1D')` conta lo
spezzone domenicale come giornata piena (17% di D1 monchi, inquina il regime),
e un sospetto non ancora verificato sulla chiusura EOD del venerdi'.

## La scoperta: rottura del regime di volatilita'

ATR14 mediano per anno: 2020 27,6&#36; · 2021 23,2 · 2022 24,5 · 2023 23,7 ·
2024 33,2 · **2025 49,5** · **2026 120,7**. Il range mediano di una candela
M1 e' passato da ~0,45&#36; (2020-24) a 1,05 (2025) e 2,27 (2026).
Tutte le soglie della strategia erano in **dollari fissi**.

## Esperimento pre-registrato: soglie in unita' di ATR

Ipotesi fissata prima di guardare gli esiti: se il problema sono i parametri
fissi, riesprimerli in ATR deve sistemare il 2026 senza peggiorare il resto.
Nessun parametro ottimizzato: i coefficienti derivano da
`k = soglia_in_$ / ATR mediano 2020-2024`, quindi nel periodo di calibrazione
le due varianti sono equivalenti per costruzione.

| Anno | expR dollari | expR ATR | delta |
|---|---|---|---|
| 2020 | -0,120 | -0,082 | +0,037 |
| 2021 | -0,170 | -0,225 | -0,055 |
| 2022 | +0,180 | +0,096 | -0,084 |
| 2023 | +0,108 | -0,085 | **-0,193** |
| 2024 | +0,068 | +0,026 | -0,041 |
| 2025 | +0,293 | +0,351 | +0,058 |
| 2026 | **-0,413** | **-0,091** | **+0,322** |

2025-2026: +0,187 → **+0,240** R · 2020-2024: +0,008 → **-0,057** R
Totale: +47,6R (1.037 trade) → +19,1R (1.129 trade).

## Verdetto onesto

L'ipotesi e' **confermata solo in parte**. La riparametrizzazione in ATR
recupera quasi tutto il danno del 2026 (-0,41 → -0,09) e triplica la
partecipazione (33 → 71 trade): la diagnosi sulla volatilita' era giusta.
Ma peggiora il periodo 2020-2024, dove le soglie fisse erano — va detto —
scelte guardando quello stesso campione: parte del loro vantaggio li' e'
in-sample.

Il punto che conta: **entrambe le varianti restano vicine allo zero.**
+0,046 e +0,017 R per operazione non sono un vantaggio su cui costruire.
Il collo di bottiglia non e' piu' la parametrizzazione ma **la qualita' del
criterio d'ingresso**: il tocco del VWAP con conferma e' un filtro troppo
debole. E' esattamente il punto in cui entrano order block e livelli
strutturali, ancora da definire operativamente.

---

# Appendice 5 — Le due parametrizzazioni coesistono: switch causale

Le varianti "dollari fissi" e "unita' di ATR" non si escludono: si puo'
scegliere quale usare mese per mese. Vincolo: la scelta deve usare solo
informazione disponibile in quel momento. Script: `run_param_switch.py`.

Regole confrontate (tutte causali tranne l'oracolo):
- **switch performance**: variante con expR trailing 6 mesi migliore
- **switch volatilita'**: usa ATR quando la volatilita' dell'ultimo mese
  supera di 1,5x la mediana storica NOTA FINO A QUEL PUNTO (finestra
  espansiva, fattore pre-registrato)
- **oracolo**: sceglie col senno di poi la variante migliore di ogni anno.
  Non e' una strategia: e' il tetto massimo di qualsiasi regola di switch.

| Sistema | n | expR | tot R | max DD | anni+ |
|---|---|---|---|---|---|
| sempre dollari | 1.037 | +0,046 | +47,6 | 73,4 | 4/7 |
| sempre ATR | 1.129 | +0,017 | +19,1 | 84,6 | 3/7 |
| switch performance | 1.077 | +0,028 | +30,1 | 74,7 | 4/7 |
| **switch volatilita'** | 1.094 | **+0,073** | **+79,7** | **68,2** | 4/7 |
| oracolo (senno di poi) | 1.107 | +0,072 | +80,0 | 70,7 | 4/7 |

expR per anno (switch volatilita'): 2020 -0,120 · 2021 -0,170 · 2022 **+0,222**
· 2023 +0,108 · 2024 +0,057 · 2025 **+0,366** · 2026 **-0,091**

Lo switch sceglie da solo: dollari dal 2020 al 2024 (con pochi mesi ATR nel
2022 e 2024), ATR dal 2025 in poi. **Ha individuato il cambio di regime senza
che nessuno gliel'abbia detto**, usando solo dati passati.

## Robustezza della soglia

Il fattore 1,5 non e' un punto fortunato: l'effetto e' un plateau, non un picco.

| fattore | 1,2 | 1,3 | 1,4 | **1,5** | 1,6 | 1,8 | 2,0 | 2,5 | 3,0 |
|---|---|---|---|---|---|---|---|---|---|
| tot R | +79,8 | +84,3 | +84,3 | **+79,7** | +78,7 | +75,1 | +68,2 | +56,2 | +57,7 |

Per ogni valore fra 1,2 e 3,0 il risultato batte sia "sempre dollari" sia
"sempre ATR": la regola non dipende dalla taratura.

## Verdetto

Lo switch **funziona e raggiunge il tetto teorico** (+79,7 contro +80,0
dell'oracolo, con drawdown minore). Il motivo per cui non e' curve fitting:
la regola e' meccanicistica — riflette la causa che avevamo gia' misurato
(la volatilita' e' quadruplicata) invece di inseguire i rendimenti.

Resta pero' un vantaggio modesto: **+0,073 R per operazione**, ~12R l'anno,
due anni su sette ancora negativi. E' un buon impianto, non ancora un edge
robusto. La conferma vera richiede dati che il modello non ha mai visto.
Il collo di bottiglia resta il criterio d'ingresso: order block e livelli
strutturali, ancora da definire operativamente.

---

# Appendice 6 — La critica giusta, e cosa dicono i controlli

## La critica (fondata)

Il totale +79,7R dello switch e' concentrato in un solo anno:

| Anno | R | quota del totale |
|---|---|---|
| 2020 | -22,0 | -28% |
| 2021 | -25,6 | -32% |
| 2022 | +29,0 | +36% |
| 2023 | +16,7 | +21% |
| 2024 | +10,8 | +14% |
| **2025** | **+77,2** | **+97%** |
| 2026 | -6,4 | -8% |

**Senza il 2025: +2,4R su 883 operazioni, cioe' zero.** Tre anni in perdita.
Nel 2025 l'oro ha fatto +64,6% e la strategia e' solo long: il sospetto
ovvio e' che non ci sia vantaggio, solo esposizione direzionale.

## Il test del placebo (150 simulazioni)

Stessi giorni, stesso numero di operazioni, stessa finestra oraria, stesso
stop, stesso obiettivo, stessa uscita, stesso spread. Cambia SOLO il momento
d'ingresso: a caso invece che al segnale. Script: `run_placebo_test.py`.

- placebo: mediana **-102,4R**, 5°-95° percentile [-175,2 · -29,5]
- reale: **+79,7R**
- **0 placebo su 150 batte il reale**

Il reale batte la mediana dei placebo in 6 anni su 7 (2020 81%, 2021 33%,
2022 99%, 2023 97%, 2024 89%, 2025 100%, 2026 75%). Anche negli anni in
perdita, perde MENO del caso.

**Il criterio d'ingresso ha valore predittivo reale.** Entrare a caso nelle
stesse finestre perde oltre 100R: il segnale vale ~180R rispetto al caso.
Il sospetto "e' solo il toro del 2025" e' smentito.

## Dove finiscono i soldi

| | R |
|---|---|
| lordo, prima dei costi | **+161,7** |
| costo dello spread a 0,30&#36; | **-82,0** |
| netto | +79,7 |
| netto con lo spread reale misurato sui tick (~0,40&#36;) | **+52,3** |

Lo spread si mangia **metà del risultato lordo**: con un rischio mediano di
4,61&#36; per operazione, 0,30&#36; di spread sono il 6,5% del rischio, pagati su
tutte e 1.094 le operazioni.

Selezionando i setup con stop piu' ampio (dove lo spread pesa meno in
proporzione) il rendimento per operazione sale in modo monotono:
rischio >=3&#36; → +0,109 · >=4&#36; → +0,116 · >=5&#36; → +0,160 R per trade.

## Conclusione

Due cose vere insieme: **il segnale funziona** (il placebo lo dimostra) ma
**il sistema non e' tradabile cosi'** (tre anni negativi, 97% in un anno).
Il divario fra le due non e' l'idea: e' la struttura dell'operazione — costi
e dimensionamento dello stop. Le leve, in ordine di impatto misurato:

1. **Costi**: lo spread e' metà del lordo. Rischio per operazione piu' ampio
   e/o esecuzione migliore cambiano il risultato piu' di qualsiasi filtro.
2. **Selezione per ampiezza dello stop**: monotona nei dati, va verificata
   con ipotesi pre-registrata prima di adottarla.
3. **Qualita' dell'ingresso** (order block e livelli): il segnale attuale
   funziona ma e' grezzo.

---

# Appendice 7 — Il lato short: l'intuizione giusta, con una condizione

Osservazione: la strategia era solo long, quindi cieca a meta' dei movimenti,
e i tre anni in perdita includono due anni in cui l'oro e' sceso.

Implementato lo short come immagine speculare esatta (doppio downtrend H6+H2,
risalita sul VWAP e chiusura sotto, sotto il minimo precedente; stop sopra il
massimo del pullback; stessi parametri, nessuna soglia nuova).

| Sistema | n | expR | tot R | max DD | anni+ |
|---|---|---|---|---|---|
| solo long | 1.094 | +0,073 | +79,7 | 68,2 | 4/7 |
| solo short | 803 | -0,046 | -36,9 | 66,4 | 3/7 |
| long + short | 1.897 | +0,023 | +42,7 | 91,0 | 3/7 |
| short + filtro macro | 512 | -0,028 | -14,3 | 47,8 | 3/7 |
| **long + short + filtro macro** | 1.344 | +0,067 | **+90,1** | **49,8** | 3/7 |

Lo short "puro" perde, e perde dove ci si aspetta: 2020 -18, 2024 -16,7,
2025 -31,2 — cioe' negli anni di forte salita dell'oro. Guadagna nel 2021
(+2,5), 2022 (+10,9) e 2023 (+17,6), gli anni piatti o deboli. Non e' il lato
short a non funzionare: e' che shortare dentro un toro secolare significa
combattere la deriva del mercato.

**Filtro macro pre-registrato** (nessuna taratura sugli esiti): chiusura
giornaliera sopra/sotto la propria media a 50 giorni, nota il giorno prima.
Long solo sopra, short solo sotto.

Il sistema completo con filtro batte il solo-long su **entrambi** i fronti:
+90,1R contro +79,7R, con drawdown **49,8R contro 68,2R**. Aggiungere lo
short nel contesto giusto migliora il rendimento E riduce il rischio: e'
esattamente cio' che ci si aspetta dalla diversificazione di direzione.

Resta la concentrazione: il 2025 vale +63,4 dei +90,1 (70%, era il 97%).
Senza il 2025: +26,7R su ~1.130 operazioni. Migliorato ma ancora sottile.

---

# Appendice 8 — Laboratorio interattivo e la scoperta sull'obiettivo

`export_lab.py` precalcola, per ogni operazione, l'esito di OGNI obiettivo
della griglia (1:2, 1:3, 1:5, 1:8, 1:10) risolvendo stop e target al minuto
(stop prioritario a parita' di minuto). La pagina puo' cosi' ricomputare
esattamente qualunque combinazione di direzione, filtro macro, obiettivo e
rischio percentuale. Verificato: i numeri coincidono con quelli degli studi.

## L'obiettivo a 3R stava lasciando molto sul tavolo

Sistema long+short con filtro macro, 1.344 operazioni:

| Obiettivo | tot R | R/operazione | a obiettivo | break-even | anni+ |
|---|---|---|---|---|---|
| 1:2 | +34,6 | +0,026 | 29,8% | 33,3% | 3/7 |
| 1:3 | +90,1 | +0,067 | 19,4% | 25,0% | 3/7 |
| 1:5 | +88,4 | +0,066 | 8,3% | 16,7% | 4/7 |
| 1:8 | +181,6 | +0,135 | 3,6% | 11,1% | **5/7** |
| **1:10** | **+194,2** | **+0,144** | 2,3% | 9,1% | **5/7** |

Sembra un paradosso: a 1:10 l'obiettivo viene raggiunto solo nel 2,3% dei
casi, sotto il break-even del 9,1%. Il profitto non arriva dall'obiettivo:

| | a 1:3 | a 1:10 |
|---|---|---|
| stop | 59,4% · -861,6R | 63,8% · -926,4R |
| obiettivo | 19,4% · +760,8R | 2,3% · +306,5R |
| **fine giornata** | 21,1% · +191,0R | **33,9% · +814,1R** |

Con l'obiettivo lontano l'operazione resta aperta e viene chiusa dalla regola
di fine giornata: quelle uscite rendono in media **+1,79R** (mediana +1,36).
A 1:3 i movimenti migliori vengono tagliati a +3 e nel secchio "fine
giornata" restano solo i mediocri (+0,67R medio). Il costo del target
lontano e' reale (piu' stop: 63,8% contro 59,4%) ma e' abbondantemente
ripagato.

**Non e' un effetto di code**: togliendo il 2% di uscite piu' grandi restano
+769R su 842. E la progressione e' regolare (34 · 90 · 88 · 182 · 194), non
un picco isolato.

## Cosa significa

Il sistema migliore trovato finora non e' "rischio 1 per guadagnare 3": e'
**lascia correre con lo stop, chiudi a fine giornata**. L'intuizione
dell'utente sul RR alto e' confermata dai dati, con una precisazione: a
1:10 il target quasi non serve, il vero motore e' l'uscita temporale.

Da verificare prima di fidarsi: 2020 resta negativo (-40R) e la
concentrazione per anno va guardata con l'uscita EOD come regola primaria.
Prossimo passo naturale: trattare l'uscita temporale come parametro
(chiusura a fine giornata vs trailing stop) invece che come vincolo.

---

# Appendice 9 — L'obiettivo deve dipendere dalle conferme (ipotesi dell'utente)

Osservazione dell'utente: un obiettivo unico per tutte le operazioni non ha
senso; il RR va scelto operazione per operazione in base a quante strutture
confermano. Punteggio = quante fra **H3, M66, M33** sono allineate alla
direzione (H6 e H2 lo sono già per costruzione). Script: `run_conferme.py`.

Prima corretto un bug che rendeva instabili proprio M33/M66: `resample` ora
ancora i bin all'epoch, quindi le candele non dipendono più da quali anni si
caricano.

## 1. I setup più confermati corrono davvero di più?

| punteggio | n | MFE mediana | ≥3R | ≥5R | ≥8R | ≥10R |
|---|---|---|---|---|---|---|
| 0 | 31 | 0,73 | 0,0% | 0,0% | 0,0% | 0,0% |
| 1 | 274 | 0,70 | 17,5% | 6,2% | 1,8% | 0,4% |
| 2 | 425 | 0,90 | 15,8% | 6,6% | 3,3% | 2,8% |
| 3 | 614 | **1,08** | **23,8%** | **10,7%** | **4,9%** | 2,9% |

Sì: la distanza percorsa cresce col punteggio. **L'ipotesi regge.**

## 2. Di conseguenza cresce anche l'obiettivo ottimale

R medio per obiettivo e punteggio:

| punteggio | 1:2 | 1:3 | 1:5 | 1:8 | 1:10 | migliore |
|---|---|---|---|---|---|---|
| 0 | -0,386 | -0,511 | -0,511 | -0,511 | -0,511 | nessuno (sempre in perdita) |
| 1 | -0,076 | +0,020 | +0,053 | **+0,077** | +0,050 | 1:8 |
| 2 | +0,006 | -0,009 | +0,003 | +0,095 | **+0,138** | 1:10 |
| 3 | +0,105 | +0,169 | +0,144 | +0,222 | **+0,224** | 1:10 |

## 3. Sistemi a confronto (obiettivo 1:10 salvo dove indicato)

| Filtro conferme | n | R/op | tot R | max DD | anni+ |
|---|---|---|---|---|---|
| nessuno, obiettivo 1:3 | 1.344 | +0,067 | +90,1 | 49,8R | 3/7 |
| nessuno | 1.344 | +0,144 | +194,2 | 57,6R | 5/7 |
| almeno 1 | 1.313 | +0,160 | +210,0 | 57,2R | 5/7 |
| **almeno 2** | 1.039 | +0,189 | +196,3 | **42,4R** | **6/7** |
| **tutte e 3** | 614 | **+0,224** | +137,7 | **23,4R** | **6/7** |
| obiettivo per punteggio (1:8/1:10/1:10) | 1.313 | +0,166 | +217,3 | 57,2R | 5/7 |

Rapporto rendimento/drawdown: 1,2 (punto di partenza) → 3,4 (1:10 secco) →
**5,9 con "tutte e 3"**.

## 4. La conferma che pesa davvero: M33

| | n | R medio | R totale |
|---|---|---|---|
| M33 allineato | 698 | **+0,298** | **+208,2** |
| M33 non allineato | 646 | -0,022 | -14,1 |

Praticamente **tutto il risultato viene dalle operazioni in cui M33 conferma**.
M66 discrimina meno (+0,164 contro +0,088) e H3, da solo, non discrimina.

## Avvertenza

La mappa punteggio→obiettivo è stata LETTA da questi stessi dati: il
risultato robusto è **il verso della relazione** (più conferme → corsa più
lunga → obiettivo più ampio), non i valori esatti delle soglie. Il 2020
resta negativo in ogni configurazione.

---

# Appendice 10 — Scala completa di conferme: quali timeframe servono davvero

Estesa la scala a **H12, H3, M66, M33, M12, M6, M3** (H6 e H2 restano la
condizione d'ingresso). Aggiunto H12 al registro dei timeframe.

## Non tutti confermano: alcuni fanno danno

Potere discriminante di ogni timeframe (R medio a 1:10, allineato vs contrario):

| Timeframe | allineato | contrario | differenza |
|---|---|---|---|
| **M33** | +0,298 | -0,022 | **+0,320** |
| **H12** | +0,180 | -0,100 | **+0,279** |
| M66 | +0,164 | +0,088 | +0,076 |
| M3 | +0,106 | +0,206 | -0,100 |
| M6 | +0,087 | +0,216 | -0,129 |
| H3 | +0,136 | +0,291 | -0,155 |
| M12 | +0,035 | +0,237 | **-0,202** |

**I timeframe veloci allineati peggiorano il risultato.** Ha senso: se anche
M3, M6 e M12 sono già girati nella direzione del trade, il movimento e' gia'
partito e si entra tardi. Quando invece sono in ritracciamento contro il
trend, l'ingresso e' migliore. E' la logica del "comprare la debolezza"
misurata invece che raccontata.

Conseguenza: **sommare tutte le conferme peggiora le cose** (punteggio 0-7
non mostra alcuna relazione monotona), perche' mescola segnali utili e
dannosi.

## Verifica FUORI CAMPIONE della selezione

La scelta "M33 + H12" e' stata fatta guardando i dati: rischio di data
mining. Controllo: classifica dei timeframe calcolata **solo sul 2020-2023**,
poi applicata al 2024-2026 mai usato per sceglierli. Sul solo 2020-2023 i
primi due risultano comunque M33 (+0,317) e H12 (+0,231).

| 2024-2026 (mai usato per la selezione) | n | R/op | tot R | max DD | anni+ |
|---|---|---|---|---|---|
| nessun filtro | 526 | +0,210 | +110,6 | 49,1R | 3/3 |
| **M33 + H12 allineati** | 268 | **+0,386** | +103,5 | **30,6R** | 3/3 |

Il filtro **quasi raddoppia il rendimento per operazione e riduce il
drawdown del 38%** su dati mai visti in fase di selezione. **La selezione
regge fuori campione.**

## Sistemi (obiettivo 1:10, rischio 1%, conto da 10.000 €)

| Conferme | n | R/op | tot R | max DD | conto | anni+ |
|---|---|---|---|---|---|---|
| nessuna | 1.344 | +0,144 | +194,2 | 48% | 49.245 € | 5/7 |
| M33 | 698 | +0,298 | +208,2 | 29% | 64.078 € | 6/7 |
| **M33 + H12** | 627 | +0,344 | **+215,8** | 27% | **70.385 €** | **7/7** |
| M33+H12, M12 in pullback | 348 | **+0,447** | +155,6 | **16%** | 42.163 € | **7/7** |

Rapporto rendimento/rischio: 1,2 all'inizio della sessione → **7,1** con
M33+H12 → **8,8** aggiungendo il ritracciamento su M12.

## Il 2026 (appendice K): il colpevole e' l'obiettivo, non le conferme

Il 2026 restava l'unico anno negativo in molte configurazioni del laboratorio.
Diagnosi, misurata sull'insieme completo di operazioni (filtro macro attivo,
long e short):

| Conferme | 1:2 | 1:3 | 1:5 | 1:8 | 1:10 |
|---|---|---|---|---|---|
| nessuna | -14,9 | -10,6 | +4,9 | +13,1 | **+17,4** |
| q>=3 su 4 | -6,8 | -2,7 | +6,8 | +10,5 | **+10,8** |
| M33+H12+M66, M12 in pullback | -3,0 | -5,0 | +0,6 | +7,7 | **+8,0** |

**In ogni configurazione il 2026 perde a 1:2 e 1:3 e guadagna da 1:5 in su.**
Non e' un problema di selezione dei segnali: gli stessi segnali, con un
obiettivo lungo, sono profittevoli.

Perche': nel 2026 il rischio mediano per operazione e' **14,47 $** contro
3,5-4,4 $ del 2020-2024, e **il 100% delle operazioni 2026 cade in mesi ad
alta volatilita'**. Quando la volatilita' e' alta il prezzo corre: chiudere a
1:3 paga lo spread e restituisce il movimento.

### Obiettivo per regime di volatilita' (R/op, regola completa)

| regime | n | 1:2 | 1:3 | 1:5 | 1:8 | 1:10 |
|---|---|---|---|---|---|---|
| normale | 166 | +0,156 | +0,275 | +0,361 | +0,409 | **+0,488** |
| alta volatilita' | 63 | +0,311 | +0,312 | +0,356 | +0,550 | **+0,598** |

L'ipotesi "obiettivo variabile col regime" e' **respinta come inutile**: 1:10
e' il migliore in *entrambi* i regimi, quindi il mix non aggiunge nulla.
Confronto dei sistemi sulla regola completa (M33+H12+M66 allineati, M12 e M6
in ritracciamento):

| sistema | R tot | R/op | max DD | anni+ | 2026 |
|---|---|---|---|---|---|
| **fisso 1:10** | **+118,7** | **+0,52** | 11,7R | **7/7** | **+16,2** |
| mix 1:8 normale / 1:10 alta vol | +105,5 | +0,46 | 11,7R | 7/7 | +16,2 |
| fisso 1:8 | +102,6 | +0,45 | 11,7R | 7/7 | +15,9 |
| fisso 1:5 | +82,3 | +0,36 | 11,7R | 7/7 | +8,8 |
| fisso 1:3 | +65,3 | +0,29 | 11,5R | 7/7 | +3,2 |

**Conclusione operativa**: l'obiettivo non va mai sotto 1:8; la regola
completa a 1:10 e' positiva in tutti e sette gli anni, 2026 incluso
(+16,2R), con il drawdown piu' basso mai misurato (11,7R = 11%).
Nessuna regola nuova, nessun parametro in piu': va solo tolta l'opzione
"obiettivo corto", che e' quella che rompeva il 2026.

## Appendice L: tutte le conferme (M3..H12) e obiettivi da 1:2 a 1:10

Dataset: `run_conferme_full.py` -> 1.344 operazioni, stato di trend causale
dei nove timeframe M3, M6, M12, M33, M66, H2, H3, H6, H12, ogni obiettivo da
1:2 a 1:10 con il MOTIVO dell'uscita (stop / obiettivo / fine giornata).

**H6 e H2 non possono confermare niente**: sono la condizione d'ingresso,
quindi risultano allineati nel 100% dei casi. H3 lo e' nel 94,3%, H12 nell'
87,4%. Restano davvero informativi solo M3, M6, M12, M33, M66 (e H12).

### Potere discriminante dei singoli timeframe (obiettivo 1:10)

| TF | n allineato | R/op allineato | R/op contrario | delta | %stop allin. | %stop contr. |
|---|---|---|---|---|---|---|
| M33 | 698 | +0,298 | -0,022 | **+0,320** | 63,8% | 63,8% |
| H12 | 1.174 | +0,180 | -0,100 | **+0,279** | 62,5% | 72,4% |
| M66 | 1.001 | +0,164 | +0,088 | +0,076 | 63,9% | 63,3% |
| M3 | 828 | +0,106 | +0,206 | -0,100 | 61,5% | 67,4% |
| M6 | 748 | +0,087 | +0,216 | -0,129 | 63,4% | 64,3% |
| H3 | 1.267 | +0,136 | +0,291 | -0,155 | 64,6% | 50,6% |
| M12 | 614 | +0,035 | +0,237 | -0,202 | 66,3% | 61,6% |

Confermato: **M33 e H12 sono le uniche due conferme vere**. M3, M6, M12 e H3
hanno delta NEGATIVO: allineati rendono meno di quando sono contrari. Il
timeframe piccolo allineato significa che il movimento e' gia' partito; il
timeframe piccolo contrario significa che si entra su un ritracciamento.

### Ricerca sistematica (3.816 configurazioni: 3^7 filtri x 9 obiettivi)

Selezione su 2020-2023, verifica su 2024-2026 mai usato per scegliere.

| filtro | RR | R/op in campione | R/op fuori campione |
|---|---|---|---|
| M3 M6 M33 H3 H12 (il migliore in campione) | 1:10 | **+0,63** | **+0,03** |
| M3 M6 M33 H12 | 1:10 | +0,61 | +0,07 |
| M3 M6 M33 H3 H12 | 1:8 | +0,59 | +0,06 |
| **M33 H12** (pre-registrato) | 1:10 | +0,31 | **+0,39** |
| **M33 H12, M12 in ritracciamento** | 1:10 | +0,40 | **+0,51** |

**Le configurazioni migliori in campione crollano fuori campione** (+0,63 ->
+0,03): e' data mining puro, esattamente cio' che la regola del progetto
vieta. Le due regole pre-registrate rendono di piu' fuori campione che
dentro. Restano quelle.

Delle 3.816 configurazioni solo 146 hanno 7 anni positivi su 7, e in cima ci
sono `M33 H12` (+215,8R) e `M33 H12 !M12` (+155,6R, DD 17,6R).

### Gli stop non si riducono con le conferme

Il tasso di stop resta fra il **60% e il 64% in ogni combinazione** e con
ogni obiettivo lungo. Nessun filtro strutturale lo sposta: le conferme
cambiano il rendimento, non la frequenza degli stop. Abbassarlo richiede di
agire sulla **gestione della posizione** (`framework/gestione.py`,
`run_gestione.py`).

### Stop a pareggio: regola completa, obiettivo 1:10 (n = 348)

| gestione | R/op | R tot | max DD | %stop | %pareggio | anni+ | 2026 |
|---|---|---|---|---|---|---|---|
| base (stop fisso) | +0,45 | +155,6 | 17,6R | 59,8% | — | 7/7 | +7,0 |
| pareggio a +1R | +0,30 | +104,2 | 15,2R | **40,5%** | 31,9% | 5/7 | +10,4 |
| pareggio a +1,5R | +0,34 | +119,9 | 14,1R | 46,6% | 21,8% | 6/7 | +10,0 |
| pareggio a +2R | +0,44 | +151,9 | **15,6R** | **49,4%** | 14,7% | **7/7** | +9,0 |
| **pareggio a +3R** | **+0,49** | **+171,1** | 17,6R | 54,3% | 6,9% | **7/7** | +7,0 |
| pareggio a +4R | +0,46 | +161,8 | 17,6R | 58,1% | 2,3% | 7/7 | +7,0 |
| meta' a +2R, resto a pareggio | +0,33 | +113,5 | 13,9R | 49,4% | 14,7% | 7/7 | +2,5 |
| meta' a +3R, resto a pareggio | +0,40 | +139,8 | 17,4R | 54,3% | 6,9% | 7/7 | +0,5 |

**Chiudere meta' posizione costa caro** (-27% di rendimento a +2R): la meta'
chiusa presto e' proprio quella che avrebbe pagato il 1:10.

**Lo stop a pareggio a +3R invece e' gratis, anzi guadagna**: +10% di
rendimento, stop dal 59,8% al 54,3%, stesso drawdown, 7 anni su 7. Non e' un
picco isolato: +2R e +4R migliorano entrambi, quindi e' un altopiano.
Verifica fuori campione:

| gestione | R/op 2020-23 | %stop | R/op 2024-26 | %stop |
|---|---|---|---|---|
| base | +0,396 | 57,2% | +0,506 | 62,7% |
| pareggio a +2R | +0,384 | **47,6%** | +0,498 | **51,6%** |
| **pareggio a +3R** | **+0,437** | 51,9% | **+0,556** | 57,1% |

### Conto da 10.000 EUR, rischio 1% composto (regola completa, 1:10)

| gestione | conto | max DD | annuo | rendimento/rischio |
|---|---|---|---|---|
| base | 42.162 € | 16,3% | 24,8% | 19,7 |
| pareggio a +2R | 41.178 € | **14,6%** | 24,3% | 21,4 |
| **pareggio a +3R** | **49.321 €** | 16,3% | **27,8%** | **24,1** |

**Conclusione**: le conferme sono gia' al massimo di quello che possono dare
(M33 + H12 + ritracciamento su M12); aggiungerne altre e' data mining. Gli
stop si tagliano con lo stop a pareggio: **+2R se si vuole il minimo di
stop** (dal 60% al 49%, drawdown piu' basso, rendimento invariato),
**+3R se si vuole il massimo rendimento** (stop al 54% e +10% di profitto).

### +2R o +3R? Il confronto a parita' di rischio

A rischio 1% fisso il +3R rende di piu' (+171,1R contro +151,9R). Ma il
confronto giusto e' a **parita' di perdita massima**: si alza il rischio per
operazione finche' le due curve hanno lo stesso drawdown.

| pareggio | rischio ammesso | conto | perdita max | serie di perdite max | operazioni sott'acqua |
|---|---|---|---|---|---|
| nessuno | 1,00% | 42.205 € | 16,3% | 13 | 33 |
| +1,5R | 1,25% | 38.641 € | 16,3% | 13 | **50** |
| +2R | **1,13%** | 48.599 € | 16,3% | 13 | 49 |
| **+3R** | **1,00%** | **49.376 €** | 16,3% | 13 | **33** |
| +4R | 1,00% | 44.920 € | 16,3% | 13 | 33 |

**In soldi sono pari** (48.599 € contro 49.376 €, 1,6% di differenza). Le
differenze vere sono altre due:

1. il +2R ci arriva **alzando il rischio a 1,13%**, cioe' tarando la size sul
   drawdown gia' osservato; il +3R ci arriva a rischio 1%. A parita' di
   risultato e' preferibile non tarare la size sul passato.
2. il +3R passa **33 operazioni sotto il massimo precedente**, il +2R ne passa
   **49**: e' il +3R, non il +2R, ad avere il profilo piu' regolare, malgrado
   prenda piu' stop.

Nota: l'uscita a pareggio non e' esattamente zero, costa lo spread (circa
-0,08R), quindi conta come una piccola perdita. Il +1,5R e' l'unica soglia da
evitare: perde il 2021 (-6,2R) perche' scatta prima che il movimento parta.

## Appendice M: la variante sui timeframe piccoli (1:3-1:5) — RESPINTA

Ipotesi pre-registrata: la stessa regola d'ingresso applicata piu' in basso
nella scala dei timeframe fa piu' operazioni con stop piu' stretti, e con
obiettivi corti (1:3-1:5) resta profittevole. Cinque varianti, generate con
lo stesso `framework/segnali.py` cambiando solo la taratura.

### Vantaggio LORDO (senza spread) contro NETTO, senza conferme

| variante | n | rischio mediano | costo spread | lordo 1:5 | netto 1:5 |
|---|---|---|---|---|---|
| A · struttura M66+M33, ingresso M3 | 1.727 | 2,56 $ | 0,129 R | -0,024 | -0,153 |
| B · struttura H6+H2, ingresso M3 | 2.323 | 2,63 $ | 0,127 R | +0,003 | -0,124 |
| C · struttura H6+H2, ingresso M1 | 3.615 | 1,97 $ | **0,171 R** | +0,063 | -0,108 |
| D · H6+H2, ingresso M3, soglie invariate | 2.428 | 3,38 $ | 0,099 R | +0,092 | -0,007 |
| **E · ufficiale (M6)** | 1.344 | 4,57 $ | **0,075 R** | **+0,141** | **+0,066** |

Due effetti separati, entrambi contrari:

1. **il vantaggio lordo si dimezza** scendendo di timeframe (+0,141 su M6 →
   +0,092 su M3 → +0,003 stringendo anche le soglie). Non e' solo un problema
   di costi: il segnale vale meno cercato piu' in piccolo.
2. **lo spread raddoppia in proporzione**: 0,075R su M6, 0,171R su M1. E'
   fisso in dollari, quindi pesa in R quanto piu' lo stop e' stretto.

Il costo per R cresce in modo netto al restringersi dello stop (0,234R sotto
1,5 $, 0,030R sopra 7 $). Il vantaggio lordo per fascia di stop invece **non
mostra una soglia pulita**: le fasce sono rumorose e non individuano
un'ampiezza minima precisa. Vale la comparazione fra varianti, non un numero
di sbarramento.

Conferma del principio gia' registrato: la variante **A**, l'unica che abbassa
anche il CONTESTO, e' la peggiore di tutte. I timeframe grandi servono al
contesto, i piccoli solo all'ingresso.

### La migliore delle piccole (D) con le conferme validate

| obiettivo | n | R/op | R tot | DD | %stop | anni+ |
|---|---|---|---|---|---|---|
| 1:3 | 601 | +0,12 | +70,3 | 40,7R | 63,1% | 5/7 |
| 1:5 | 601 | +0,20 | +118,8 | 51,7R | 67,7% | 5/7 |
| 1:5 pareggio +3R | 601 | +0,21 | +123,4 | 52,5R | 63,1% | 5/7 |
| **ufficiale 1:10 pareggio +3R** | 348 | **+0,49** | +171,1 | **17,6R** | 54,3% | **7/7** |

D fa il 73% di operazioni in piu' ed e' profittevole. Ma:

**Il vantaggio e' tutto recente.** Fuori campione la variante piccola va nella
direzione sbagliata rispetto all'ufficiale:

| sistema | 2020-2023 | 2024-2026 |
|---|---|---|
| piccola 1:5 | **+0,05 R/op** | +0,38 R/op |
| ufficiale | +0,44 R/op | +0,56 R/op |

Il 2020 (-22,2R) e il 2021 (-27,1R) sono negativi: la variante non ha
guadagnato nulla nella prima meta' della storia. L'ufficiale rende uguale
nelle due meta'.

### Affiancarla all'ufficiale peggiora il sistema

Le operazioni sono distinte, ma la correlazione dei risultati **mensili** e'
**+0,776**: non e' diversificazione, e' la stessa idea presa piu' spesso.
A parita' di perdita massima (16,3%):

| sistema | n | rischio ammesso | conto | anni+ | peggior anno |
|---|---|---|---|---|---|
| **solo ufficiale** | 348 | **1,00%** | **49.376 €** | **7/7** | +6,9R |
| solo piccola | 601 | 0,34% | 14.699 € | 5/7 | -27,1R |
| tutte e due | 949 | 0,39% | 29.566 € | 5/7 | -17,3R |

Sommare i due sistemi **dimezza il conto** rispetto al solo ufficiale: la
piccola porta un drawdown che costringe a ridurre la size da 1,00% a 0,39%, e
trasforma 2020 e 2021 da positivi in negativi.

**Conclusione: variante respinta.** Piu' operazioni non valgono meno vantaggio
per operazione, e il conteggio a parita' di rischio lo dimostra. Non riprovare
la strada "stessa regola su timeframe piu' piccoli": e' misurata.

## Appendice N: lo spread vero contro i 0,30 $ assunti

Prima misura fatta su **tick reali bid+ask** (Dukascopy, 222 milioni di tick,
novembre 2022 - luglio 2026, 45 mesi). Fino a qui ogni numero del progetto
assumeva uno spread fisso di 0,30 $.

### Lo spread e' triplicato in tre anni

| periodo | spread mediano |
|---|---|
| 2023 | 0,32 - 0,34 $ |
| 2024 | 0,33 → 0,44 $ |
| 2025 | 0,51 → 0,70 $ |
| 2026 | 0,58 → **0,89 $** (massimo: febbraio 2026) |

### Ma il risultato regge: -4%

Ricalcolo delle 218 operazioni del periodo coperto, sostituendo al costo
assunto lo spread mediano del mese in cui l'operazione e' avvenuta.

| anno | con 0,30 $ | spread reale | differenza |
|---|---|---|---|
| 2022 (nov-dic) | +20,5 | +20,2 | -0,3 |
| 2023 | +27,7 | +27,2 | -0,5 |
| 2024 | +38,4 | +37,3 | -1,0 |
| 2025 | +44,1 | +40,7 | -3,4 |
| 2026 | +7,0 | +6,3 | -0,7 |
| **totale** | **+137,7** | **+131,8** | **-5,9 (-4%)** |

Cinque anni positivi su cinque anche con lo spread vero; conto da 36.326 a
34.254 €. Il costo per operazione e' pero' molto piu' alto di quello assunto:
+121% nel 2026, +88% nel 2025.

**Perche' l'impatto resta piccolo**: cresce anche lo stop. Il rischio mediano
passa da 3,43 $ (2023) a 15,99 $ (2026). Spread e ampiezza dello stop seguono
entrambi la volatilita' e in proporzione si compensano quasi del tutto — il
costo in R passa da 0,093 a 0,049, cioe' **scende**.

Approssimazione dichiarata: e' lo spread **mediano del mese**, non quello
dell'istante d'ingresso. Si entra fra le 7 e le 19 UTC (ore liquide, spread
piu' stretto della mediana sulle 24 ore) ma su movimenti impulsivi (spread piu'
largo). La misura esatta richiede i Parquet dei tick a portata di calcolo.

### Serve scaricare i tick 2020-01 → 2022-10?

Quel periodo (130 operazioni su 348) non ha tick. Quanto spread reggerebbe
prima di andare in perdita:

| anno | n | rischio mediano | R con 0,30 $ | spread che azzera l'anno |
|---|---|---|---|---|
| **2020** | 48 | 4,85 $ | +6,93 | **0,90 $** |
| **2021** | 54 | 3,68 $ | +9,82 | **0,90 $** |
| 2022 | 37 | 3,60 $ | +37,20 | 3,60 $ |

Simulazione sul totale, ipotizzando uno spread X per tutto il periodo scoperto:

| spread ipotizzato | R totale | anni positivi | 2020 | 2021 |
|---|---|---|---|---|
| 0,30 $ | +171,1 | 7/7 | +6,9 | +9,8 |
| 0,50 $ | +163,8 | 7/7 | +4,6 | +6,5 |
| 0,80 $ | +152,9 | 7/7 | +1,1 | +1,6 |
| 1,00 $ | +145,7 | **5/7** | -1,2 | -1,7 |

**Il risultato non cambia** finche' lo spread 2020-2022 e' stato sotto 0,90 $.
Il massimo mai misurato e' 0,887 $, e in un mese (febbraio 2026) di volatilita'
estrema; nel 2020-2021 la volatilita' dell'oro era molto piu' bassa e la misura
mostra che lo spread la segue. Un valore intorno a 0,90 $ per due anni interi
non e' plausibile.

**Conclusione**: i tick 2020-2022 non servono a validare la strategia, il
risultato e' robusto a qualunque spread verosimile. Restano utili per altro
(fill infra-minuto su tutta la storia, e il bot con ordini limite del
collaboratore), quindi vanno scaricati con calma, non con urgenza.

### Appendice N-bis: la misura esatta, istante per istante

La stima dell'appendice N usava lo spread **mediano del mese**. Ora c'e' la
misura al minuto d'ingresso di ognuna delle 218 operazioni coperte dai tick
(`docs/spread-misurato-taratura.csv`, prodotto da `misura_spread.py`).

| anno | 0,30 $ fissi | spread esatto | spread peggiore del minuto | differenza |
|---|---|---|---|---|
| 2022 (nov-dic) | +20,52 | +20,20 | +19,98 | -0,32 |
| 2023 | +27,69 | +27,26 | +26,46 | -0,42 |
| 2024 | +38,36 | +37,42 | +36,77 | -0,93 |
| 2025 | +44,12 | +40,70 | +39,17 | **-3,41** |
| 2026 | +6,99 | +6,43 | +5,90 | -0,57 |
| **totale** | **+137,67** | **+132,02** | **+128,29** | **-5,65** |

**La stima era buona**: -5,65 R misurati contro -5,9 R stimati dalla mediana
mensile. La conclusione dell'appendice N resta valida senza correzioni.

| | R/op | R tot | anni+ | conto | DD |
|---|---|---|---|---|---|
| 0,30 $ fissi | +0,631 | +137,7 | 5/5 | 36.326 € | 17,6R |
| **spread esatto** | **+0,606** | **+132,0** | **5/5** | **34.338 €** | 18,3R |
| spread peggiore del minuto | +0,588 | +128,3 | 5/5 | 33.089 € | 18,8R |

La terza riga e' un caso pessimo deliberato: come se ogni ingresso fosse
avvenuto nel momento **peggiore** del minuto precedente. Costa altri 3,7 R, e
resta positivo in tutti gli anni. Il risultato non dipende dalla fortuna
sull'esecuzione.

### Il costo cresce, ma il rischio cresce di piu'

| anno | n | rischio mediano | spread mediano | costo assunto | costo vero | in piu' |
|---|---|---|---|---|---|---|
| 2022 | 9 | 3,11 $ | 0,415 $ | 0,098 | 0,133 | +36% |
| 2023 | 48 | 3,43 $ | 0,330 $ | 0,093 | 0,102 | +9% |
| 2024 | 54 | 4,38 $ | 0,380 $ | 0,079 | 0,096 | +22% |
| 2025 | 82 | 7,26 $ | 0,555 $ | 0,047 | 0,089 | **+88%** |
| 2026 | 25 | 15,99 $ | 0,600 $ | 0,022 | 0,045 | **+102%** |

Nel 2026 il costo vero e' il **doppio** di quello assunto, e nonostante questo
in R **scende** (0,045 contro 0,102 del 2023): il rischio mediano per operazione
e' quintuplicato nello stesso periodo. E' il meccanismo che rende la strategia
robusta all'allargarsi dello spread, ora misurato e non ipotizzato.

### Dove lo spread morde davvero

Le operazioni piu' colpite non sono quelle nei mesi peggiori, sono quelle con lo
**stop piu' stretto**:

| anno | rischio | spread | costo in R |
|---|---|---|---|
| 2025 | 1,90 $ | 0,674 $ | **0,356** |
| 2025 | 2,15 $ | 0,550 $ | 0,256 |
| 2025 | 2,33 $ | 0,587 $ | 0,252 |
| 2025 | 2,59 $ | 0,610 $ | 0,235 |
| 2023 | 1,51 $ | 0,340 $ | 0,225 |

Su un'operazione con 1,90 $ di rischio lo spread si mangia **un terzo di R**.
E' la conferma indipendente di quanto misurato nell'appendice M sulla variante
sui timeframe piccoli: sotto una certa ampiezza di stop il costo fisso diventa
decisivo. Qui succede a taratura invariata, sulle poche operazioni in cui lo
stop e' minimo.

## Appendice O: i ritracciamenti di Fibonacci — RESPINTI col placebo

Domanda deliberatamente piu' piccola di "lo scalping su Fibonacci funziona":
**i livelli di Fibonacci reagiscono?** Si misura la reazione al tocco, senza
stop, senza obiettivo, senza costi. Se i livelli veri non battono livelli finti
alla stessa profondita', qualunque strategia costruita sopra e' morta prima di
pagare lo spread.

Disegno (`trading/scripts/run_fibo_placebo.py`): gambe fra swing frattali
confermati k barre dopo l'estremo, utilizzabili solo da quando il secondo
estremo e' confermato; primo tocco del livello dopo l'attivazione; reazione =
massima escursione favorevole nei 60 minuti successivi, in ATR.
**Placebo**: livelli a percentuali NON di Fibonacci (23 · 34 · 44 · 56 · 67 · 84)
misurati in modo identico.

### Fibonacci contro placebo

| timeframe | tocchi fibo | tocchi finti | reazione fibo | reazione finta | differenza | probabilita' che sia caso |
|---|---|---|---|---|---|---|
| M12 | 9.662 | 11.913 | 0,1185 | 0,1134 | +0,0031 | **16,9%** |
| M6 | 7.479 | 9.240 | 0,1326 | 0,1296 | +0,0001 | **49,2%** |

Su M6 la differenza e' **un decimillesimo di ATR** con probabilita' del 49% di
essere caso: una moneta.

### Accoppiando ogni livello di Fibonacci con un finto alla stessa profondita' (M12)

| Fibonacci | finto | reazione fibo | reazione finta | vince |
|---|---|---|---|---|
| 38,2 | 34,0 | 0,1083 | 0,1064 | fibo |
| 38,2 | 44,0 | 0,1083 | 0,1158 | finto |
| 50,0 | 44,0 | 0,1177 | 0,1158 | fibo |
| 50,0 | 56,0 | 0,1177 | 0,1185 | finto |
| 61,8 | 56,0 | 0,1194 | 0,1185 | fibo |
| 61,8 | 67,0 | 0,1194 | 0,1201 | finto |
| 70,5 | 67,0 | 0,1207 | 0,1201 | fibo |
| 78,6 | 84,0 | 0,1293 | 0,1300 | finto |

**Quattro a quattro.** Su M12 il livello che reagisce meglio di tutti e' il
finto **84%**, non il 78,6.

### L'effetto profondita' NON e' stabile

Su M12 la reazione cresce in modo perfettamente monotono con la profondita' del
ritracciamento (correlazione **+0,965**), veri e finti mescolati: sembrava un
effetto meccanico utilizzabile — piu' profondo il livello, piu' spazio per
rimbalzare.

Su M6 quella regolarita' **non c'e'**: correlazione **+0,341**, con un massimo
intorno al 56% e reazioni che calano oltre il 67%. Il livello migliore su M6 e'
il finto 56.

Due timeframe, due forme diverse: **non e' una regolarita' su cui costruire.**

### Il numero che chiude anche lo scalping

| timeframe | reazione | penetrazione | rapporto |
|---|---|---|---|
| M12 | 0,1155 ATR | 0,1093 ATR | **1,057** |
| M6 | 0,1326 ATR | 0,1207 ATR | **1,098** |

Il rimbalzo supera il movimento contrario del 6-10%: praticamente una moneta.
E lo scalping su XAUUSD, con lo spread reale misurato di 0,63 $, richiede:

| stop | costo in R | pareggio a RR 1:1 | a RR 1:2 |
|---|---|---|---|
| 2 $ | 0,315 | **65,8%** | 43,8% |
| 3 $ | 0,210 | 60,5% | 40,3% |
| 5 $ | 0,126 | 56,3% | 37,5% |

Formula: `pareggio = (1 + costo) / (1 + RR)`. Con un rapporto reazione/
penetrazione di 1,06 non si arriva da nessuna parte vicino al 66%.

**Conclusione: strada respinta.** Non e' un problema di taratura, e' che il
segnale non c'e'. Non riprovare Fibonacci come generatore di livelli, ne' su
timeframe piu' piccoli: e' misurato, con placebo, su due timeframe.

## Appendice P: gli order block funzionano (primo risultato positivo su un'idea nuova)

Definizione data dall'utente, il suo bot li usa cosi':

- **rialzista**: l'ultima candela con chiusura sotto l'apertura prima del
  movimento che rompe uno swing high. Zona **dal minimo dell'ombra
  all'apertura**, cioe' al bordo superiore del corpo: l'ombra in alto non fa
  parte della zona.
- **ribassista**: simmetrico. Zona dall'apertura (bordo inferiore del corpo) al
  massimo dell'ombra.
- **causale**: la zona esiste solo dalla chiusura della candela che rompe. Prima
  non si sapeva che ci sarebbe stata una rottura: usarla prima e' lookahead.
- **invalidata** alla prima chiusura oltre il lato lontano; **scade** dopo 30
  candele.

Ipotesi pre-registrata: gli ingressi che cadono dentro un order block attivo e
concorde rendono di piu', perche' e' dove stanno gli ordini in attesa.

### Il risultato, su tutte le 1.344 operazioni

| timeframe della zona | n dentro | R/op dentro | R/op fuori | delta | probabilita' per caso | anni meglio |
|---|---|---|---|---|---|---|
| **M33** | 160 | **+0,640** | +0,087 | **+0,553** | **0,3%** | **6/7** |
| H2 | 99 | +0,146 | +0,153 | -0,007 | 50,0% | 3/7 |

Su M33 l'effetto e' forte e regge per anno. Su H2 non c'e' niente: le zone dei
timeframe alti sono troppo poche e troppo larghe.

### Regge fuori campione, e migliora

| periodo | dentro | fuori | delta |
|---|---|---|---|
| selezione 2020-2023 | +0,436 (n=92) | +0,100 (n=726) | +0,336 |
| **verifica 2024-2026** | **+0,916** (n=68) | +0,066 (n=458) | **+0,850** |

E' il contrario della firma da sovradattamento, dove il fuori campione crolla.

### E' robusto al parametro che ho scelto io

Il margine (quanto vicino alla zona basta essere) e' l'unico numero arbitrario:

| margine | n dentro | R/op dentro | R/op fuori | delta | probabilita' per caso |
|---|---|---|---|---|---|
| 0,00 (dentro esatto) | 42 | +0,833 | +0,131 | **+0,702** | 3,1% |
| 0,25 x rischio | 86 | +0,779 | +0,110 | +0,669 | 0,7% |
| 0,50 x rischio | 160 | +0,640 | +0,087 | +0,553 | 0,3% |
| 0,75 x rischio | 249 | +0,489 | +0,076 | +0,412 | 0,6% |
| 1,00 x rischio | 337 | +0,421 | +0,063 | +0,359 | 0,7% |
| 1,50 x rischio | 459 | +0,393 | +0,028 | +0,365 | 0,4% |

**Monotono**: piu' si e' vicini alla zona, piu' grande l'effetto. E' un
altopiano, non un picco: significativo a ogni margine. E' la forma che ha un
effetto vero, non un parametro fittato.

### E' indipendente dalle conferme

| campione | n dentro | delta | probabilita' per caso | anni meglio |
|---|---|---|---|---|
| tutte le operazioni | 160 | +0,553 | 0,3% | 6/7 |
| solo la regola completa | 69 | +0,378 | 14,1% | 4/7 |
| **solo le operazioni che la regola SCARTA** | 91 | **+0,537** | **1,6%** | **6/7** |

La terza riga e' la piu' informativa: l'effetto c'e' anche sulle operazioni che
le conferme M33+H12+M12 rifiutano. **Gli order block non sono un altro modo di
dire la stessa cosa delle conferme**: aggiungono informazione loro.

Sul solo sottoinsieme della regola completa il test non passa (14,1%), ma con 69
operazioni la potenza non basta: il campione grande e il sottoinsieme scartato
dicono la stessa cosa e sono la prova.

### Cosa resta da fare prima di adottarli

1. **misurarli come filtro sul risultato complessivo**, non solo come differenza
   fra due gruppi: quante operazioni si perdono, come cambiano drawdown e conto
2. **provare altri timeframe fra M33 e H2** (M66) e altre durate di validita'
3. **verificare che non sia un travestimento dell'impulso minimo**: entrambi
   chiedono che il prezzo si sia mosso prima di tornare
4. **rifarlo con lo spread reale** dai tick

Il punto 3 e' il rischio piu' serio: se le due condizioni selezionano le stesse
operazioni, l'order block non aggiunge nulla, misura solo di nuovo l'impulso.

## Appendice Q: stop fissi piccoli su timeframe bassi — la direzione e' sbagliata

Specifica dell'utente: 0,01 lotti su XAU, dove un punto vale un dollaro, quindi
stop di **2 / 3 / 5 dollari** con obiettivi **1:3 e 1:5**, su ingressi M3 e M6.
Lo stop non e' strutturale ma un valore fisso: meccanica diversa da quella della
taratura, e va misurata a parte.

Costi con lo spread reale misurato (0,63 $):

| stop | costo in R | pareggio a 1:3 | a 1:5 |
|---|---|---|---|
| 2 $ | **0,315** | 32,9% | 21,9% |
| 3 $ | 0,210 | 30,3% | 20,2% |
| 5 $ | 0,126 | 28,2% | 18,8% |

72 celle provate (2 timeframe x 3 stop x 2 obiettivi x 4 filtri). Le celle
singole non contano — contano le **regolarita'**, che sono quattro e valgono su
tutte e 72.

### 1. Lo stop piu' largo vince sempre

R/op con conferme e order block:

| ingresso | 2 $ | 3 $ | 5 $ |
|---|---|---|---|
| M6, 1:3 | -0,061 | +0,273 | **+0,443** |
| M6, 1:5 | +0,090 | +0,270 | +0,292 |
| M3, 1:3 | -0,235 | +0,104 | **+0,299** |
| M3, 1:5 | -0,099 | +0,204 | +0,170 |

Monotono in **ogni** filtro e su entrambi i timeframe. Il tasso di stop passa dal
72% con 2 $ al 42-48% con 5 $.

**A 2 $ il risultato e' negativo quasi ovunque**, e su M3 in tutte e otto le
celle. "Tante piccole operazioni" non compensa: il costo si paga per operazione,
quindi piu' se ne fanno piu' se ne paga, e con lo stop stretto il rumore tira
fuori piu' spesso.

### 2. M6 batte M3 in ogni cella comparabile

Con conferme e order block, stop 5 $ e obiettivo 1:3: **+0,443** su M6 contro
**+0,299** su M3. Terza misura indipendente che dice la stessa cosa
(appendici M e O sono le altre due).

### 3. Senza filtri perde in ogni combinazione

Tutti i segnali, nessun filtro: da -0,058 a -0,323 R/op. Ventiquattro celle su
ventiquattro negative, su entrambi i timeframe.

### 4. L'order block migliora quasi tutte le celle

Coerente con l'appendice P, e su un campione diverso da quello in cui era stato
trovato.

### Il confronto che chiude la questione

| sistema | n | R/op | anni+ | drawdown |
|---|---|---|---|---|
| miglior cella qui (M6, conferme+OB, 5 $, 1:3) | 127 | +0,443 | 5/7 | non misurato |
| **taratura ufficiale** (M6 strutturale, 1:10, pareggio +3R) | **348** | **+0,492** | **7/7** | **16,3%** |

La cella migliore di 72 e' **peggiore** della taratura in vigore, su un terzo
delle operazioni e con due anni negativi. E quel +0,443 e' scelto a posteriori
fra 72: il suo valore vero e' piu' basso.

**Conclusione: la direzione e' sbagliata.** Tutte le regolarita' misurate
puntano verso stop piu' larghi e timeframe piu' alti, cioe' verso dove la
taratura ufficiale si trova gia'. Lo stop strutturale (minimo delle ultime
candele piu' un buffer, banda 1-10 $, mediana 3,4-16 $ a seconda dell'anno) sta
nella zona buona, e ci sta arrivando da una regola invece che da un numero
fisso.

## Appendice R: pareggio precoce e prova sui due anni completi

### Il pareggio a +1 punto azzera il vantaggio

Idea dell'utente: portare lo stop a pareggio appena l'operazione va di un punto
(un dollaro) in vantaggio. Misurato su ingressi M6, spread reale 0,63 $:

| filtro | stop | RR | senza pareggio | **+1 $** | +2 $ | +3 $ | +5 $ |
|---|---|---|---|---|---|---|---|
| conferme+OB | 5 $ | 1:3 | **+0,443** | **+0,003** | +0,106 | +0,137 | +0,277 |
| conferme+OB | 3 $ | 1:3 | +0,273 | +0,003 | +0,108 | +0,135 | +0,135 |
| conferme+OB | 5 $ | 1:5 | +0,292 | **-0,045** | +0,080 | +0,102 | +0,245 |
| tutti i segnali | 5 $ | 1:5 | -0,058 | -0,120 | -0,128 | -0,132 | -0,114 |

**A +1 $ il 74% delle operazioni esce a pareggio.** Con uno stop da 5 $ armare a
+1 $ significa armare a +0,2 R: il prezzo torna sull'ingresso in tre casi su
quattro. E il pareggio non e' zero, costa lo spread (-0,126 R), quindi si
trasforma il 74% delle operazioni in piccole perdite.

Il pattern e' **monotono**: piu' tardi si arma, meglio va. E' identico a quanto
misurato nell'appendice L sulla taratura ufficiale, dove +1R era la soglia
peggiore e +3R la migliore. Due meccaniche diverse, stessa risposta: **il
pareggio va armato tardi.**

### La cella migliore, anno per anno

M6, conferme e order block, stop 5 $, obiettivo 1:3, nessun pareggio:

| anno | n | R/op | R totale |
|---|---|---|---|
| 2020 | 19 | -0,057 | -1,1 |
| 2021 | 26 | +0,425 | +11,0 |
| 2022 | 13 | +0,955 | +12,4 |
| 2023 | 36 | +0,320 | +11,5 |
| 2024 | 19 | +0,715 | +13,6 |
| 2025 | 13 | +0,767 | +10,0 |
| **2026** | **1** | -1,126 | -1,1 |

### I due anni completi piu' recenti

| | n | R/op | R totale | drawdown | conto da 10.000 € |
|---|---|---|---|---|---|
| 2024 | 19 | +0,715 | +13,6 | 5,6R | 11.413 € |
| 2025 | 13 | +0,767 | +10,0 | 3,4R | 11.022 € |
| 2024+2025 | 32 | +0,736 | +23,6 | 5,6R | 12.579 € |

### Il confronto che conta

| anno | operazioni piccola | R piccola | operazioni ufficiale | R ufficiale |
|---|---|---|---|---|
| 2024 | 19 | +13,6 | 54 | **+38,4** |
| 2025 | 13 | +10,0 | 82 | **+44,1** |

**Per operazione la variante e' pari o meglio** (+0,715 contro +0,710 nel 2024;
+0,767 contro +0,538 nel 2025). **In soldi rende un terzo**, perche' fa 20
operazioni l'anno contro 54.

E' la lezione che vale piu' del numero: **il R per operazione non e' quello che
paga, il R totale lo e'.** Un sistema piu' selettivo puo' avere un'ottima media e
guadagnare meno, perche' non capitalizza.

Il 2026 con **una** operazione chiude il discorso sull'affidabilita': con
campioni annuali da 13 a 36 operazioni non si distingue nulla.

**Conclusione**: la variante non si adotta. Quello che resta di valore da questo
studio e' l'order block (appendice P), che qui si e' confermato su un campione
diverso da quello in cui era stato trovato.

## Appendice S: win rate al 70% e dieci operazioni al giorno — due specifiche impossibili

Due richieste dell'utente, misurate sulle stesse operazioni della taratura
ufficiale. Entrambe sono specifiche su **variabili che non si possono scegliere**.

### Il 70% di operazioni vinte si ottiene, ed e' dove si perde di piu'

Stesse 348 operazioni, cambia solo l'obiettivo:

| obiettivo | % vinte | R/op | R totale | anni positivi |
|---|---|---|---|---|
| 1:0,25 | **70,4%** | **-0,14** | -48,0 | **0/7** |
| 1:0,4 | **71,6%** | **-0,13** | -45,1 | **0/7** |
| 1:0,5 | 67,5% | -0,12 | -42,5 | 1/7 |
| 1:0,75 | 62,4% | -0,06 | -19,6 | 3/7 |
| 1:1 | 56,6% | -0,02 | -8,3 | 3/7 |
| 1:2 | 46,8% | +0,14 | +47,7 | 6/7 |
| 1:3 | 42,0% | +0,23 | +81,0 | 6/7 |
| **1:10** | **36,2%** | **+0,37** | **+128,1** | 6/7 |

La relazione e' **monotona**: piu' sale il win rate, piu' scende il guadagno.

Perche' non e' aggirabile. Perche' il 70% sia profittevole serve un obiettivo
sopra 0,6 (con stop da 5 $ e spread reale: `0,70 x RR - 0,30 - 0,126 > 0`).
Ma sui dati, mettendo l'obiettivo a 0,75 il win rate **scende al 62,4%**, e a
1,0 scende al 56,6%. **Le due grandezze non sono indipendenti**: il mercato da'
la coppia, non i due numeri separatamente, e su questi dati non esiste nessuna
coppia con vinte >= 70% e attesa positiva.

**Il win rate non e' una specifica, e' una conseguenza dell'obiettivo.** Le
specifiche sensate sono la perdita massima e la regolarita', e la taratura in
vigore le ha buone (16,3% e 7 anni su 7) proprio grazie al 36% di vinte.

### Dieci operazioni al giorno non esistono, e a otto il vantaggio non copre i costi

Allentando progressivamente ogni condizione (impulso, filtro macro, limite
giornaliero, attesa fra segnali), obiettivo 1:3, spread reale 0,63 $:

| ingresso | op/giorno | lordo | netto 3 $ | netto 5 $ | netto 15 $ |
|---|---|---|---|---|---|
| M6 impulso 4 (taratura) | 2,15 | +0,026 | -0,184 | -0,085 | +0,000 |
| M6 impulso 1, no macro | 3,35 | -0,009 | -0,219 | -0,071 | +0,029 |
| M3 impulso 1, no macro | 4,72 | +0,022 | -0,188 | -0,066 | +0,029 |
| M1 impulso 1, no macro | 7,02 | -0,022 | -0,232 | -0,120 | +0,007 |
| **M1 impulso 0,5** | **7,98** | -0,015 | -0,225 | -0,119 | **+0,011** |

1. **Il massimo raggiungibile e' 7,98 al giorno**, non 10: oltre non c'e' piu'
   niente da allentare.
2. **Il vantaggio lordo senza filtri va da +0,006 a +0,071 R**, mentre il costo
   di uno stop da 5 $ e' 0,126. Sedici celle su sedici in perdita con stop da 3
   e 5 dollari.
3. Diventa positivo **solo con stop da 15 $**, e di un filo: +0,011 R/op a otto
   operazioni al giorno.

Quel +0,011 su 8 al giorno per 250 giorni fa **+22 R l'anno**. La taratura
ufficiale ne fa **26 con 54 operazioni**: stessi soldi, quaranta volte le
operazioni. E il margine e' un filo di lama — con spread 0,70 invece di 0,63
(il livello del 2026) il costo a 15 $ sale a 0,047 e il netto diventa negativo.

### La regolarita' che lega tutte le appendici da M a S

Il vantaggio viene dai **filtri**, e i filtri tagliano la frequenza. Aumentare
la frequenza non moltiplica il vantaggio: lo diluisce e moltiplica i costi, che
si pagano per operazione. Cinque studi indipendenti (M, O, P, Q, S) misurano
sempre la stessa cosa.

Il vincolo di fondo: l'informazione che si estrae dalle candele (struttura,
VWAP, order block) e' a **bassa frequenza**. Dice qualcosa sulle prossime ore,
non sui prossimi minuti. I sistemi che fanno decine di operazioni al giorno e
guadagnano vivono di costi quasi nulli (rebate, market making) e di informazione
sul flusso degli ordini, che nei dati a candele non c'e'.

## Appendice T: stop fissi in punti con pareggio — griglia completa degli esiti

155 celle: stop 3/5/10/15/20 punti x obiettivi 1:1,5-1:20 x pareggio
(nessuno, +1R, +2R, +3R, +5R), sui 348 segnali con le conferme, spread reale
0,63 $. Pipeline verificata ricalcolando tre celle gia' misurate (coincidono).
Dettaglio completo in `docs/studies/dati/griglia-stop-fissi-pareggio.parquet`.

### Correzione all'appendice Q

A parita' di perdita massima (16,3%) la miglior cella a stop fisso NON e'
5 pt 1:20 ma **5 pt 1:5 senza pareggio**: drawdown 14 R (il piu' basso della
griglia), quindi rischio ammesso 1,20% e conto **30.057 €**. Il divario con la
taratura in vigore e' **-16%**, non -35% come scritto in Q (dove il confronto a
parita' copriva solo gli obiettivi da 1:10 in su).

| sistema | % vinte | R tot | conto (DD 16,3%) | anni+ |
|---|---|---|---|---|
| strutturale 1:10 pareggio +3R | 35,1% | +143,7 | **35.816 €** | **7/7** |
| **5 pt 1:5 senza pareggio** | 37,1% | +100,7 | **30.057 €** | 6/7 |
| 5 pt 1:20 pareggio +5R | 35,1% | +138,6 | 26.038 € | 6/7 |
| 10 pt 1:2 senza | 53,4% | +69,7 | 23.488 € | 4/7 |

La strutturale resta davanti e resta l'unica 7/7.

### Il pareggio sugli stop fissi: al massimo neutro

Esiti su stop 5 pt (SL / TP / pareggio / fine giornata):

| RR | pareggio | % vinte | %SL | %TP | %BE | %fine gg | R tot | conto |
|---|---|---|---|---|---|---|---|---|
| 1:5 | nessuno | 37,1 | 58,3 | 11,8 | — | 29,9 | +100,7 | 30.057 |
| 1:5 | +1R | 21,8 | 42,5 | 6,6 | **32,2** | 18,7 | +18,5 | 11.184 |
| 1:5 | +3R | 34,8 | 57,5 | 10,9 | 3,2 | 28,4 | +81,5 | 20.916 |
| 1:10 | nessuno | 35,6 | 59,8 | 1,7 | — | 38,5 | +106,8 | 24.307 |
| 1:10 | +1R | 21,3 | 42,5 | 0,6 | **32,8** | 24,1 | +28,9 | 11.651 |
| 1:10 | +5R | 35,3 | 58,3 | 1,7 | 1,7 | 38,2 | +106,9 | 22.071 |

La meccanica: il pareggio a +1R toglie 17 punti di %SL ma li trasforma in un
33% di uscite a pareggio, che pagano lo spread e rubano le operazioni che
sarebbero finite in guadagno a fine giornata (a 1:10 solo l'1,7% tocca il TP:
il profitto sta nel 38,5% di chiusure EOD, ed e' esattamente cio' che il
pareggio precoce ammazza). Le vinte crollano dal 36% al 21%.

**Terza conferma indipendente della stessa legge** (dopo le appendici L e R):
+1R distruttivo, +2/+3R toglie il 20-30%, +5R neutro. Sulla strutturale il
+3R aggiungeva il 10%; sugli stop fissi al massimo non toglie. Il pareggio si
arma tardi o non si arma.

## Appendice U: scalp su M1 (stop 1-3 punti, TP 5-10) — le tre previsioni confermate

Registrate PRIMA della misura: (1) stop da 1 punto in perdita pesante ovunque,
perche' il costo e' 0,63 R a operazione e la probabilita' casuale di fare +5
prima di -1 e' ~17% contro il 27% che servirebbe; (2) le celle meno peggio a
stop 3 / TP 10 con i filtri; (3) nessuna cella batte la variante 5 pt 1:5.

Due contesti (M6+M3 proposta dell'utente; H6+H2 classico), ingresso M1,
impulso 2 $, filtro macro, spread reale 0,63. Verifica indipendente: 4 celle
su 4 coincidono.

### Esito (R/op; 48 celle totali)

| | M6+M3 (3.481 segnali, 3,3/gg) | H6+H2 (5.114 segnali, 6,8/gg) |
|---|---|---|
| stop 1, senza filtri | **-0,635** (vinte 17,3% = caso) | -0,619 (vinte 17,4% = caso) |
| stop 2, senza filtri | -0,300 | -0,333 |
| stop 3, senza filtri | -0,235 | -0,242 |
| stop 3 TP 10, conferme | -0,091 | -0,078 |
| stop 3 TP 10, conferme+OB | -0,163 | **+0,059** |

1. **Con stop da 1 punto il segnale sparisce**: la percentuale di vinte
   coincide con il caso puro (random walk ~1/6). La perdita e' esattamente il
   costo dello spread. Confermata la previsione 1.
2. **47 celle su 48 negative.** L'unica positiva (H6+H2, stop 3, TP 10,
   conferme+OB: +0,059 su 358 op, 4/7 anni) e' 1 su 48 con test multipli:
   compatibile con il rumore, e comunque un QUINTO della variante 5 pt 1:5
   (+0,289) e un settimo della strutturale. Previsioni 2 e 3 confermate.
3. **Il contesto M6+M3 e' PEGGIORE di H6+H2** in quasi ogni cella: quarta
   conferma indipendente che il contesto va tenuto sui timeframe alti.

Avvertenza sui dati: candele BID, spread applicato come costo; con stop da 1-2
punti il percorso reale sull'ask e' peggiore di quello misurato. Questi numeri
sono un TETTO, e sono gia' negativi.

**Strada chiusa: scalp su M1 con stop 1-3 punti.** Con lo spread di XAU la
matematica non lascia spazio: e' la quarta misura (M, Q, S, U) che converge.

## Appendice V: la zona raffinata degli order block AGGIUNGE; il volume profile no

Due studi pre-registrati, eseguiti in parallelo con verifica indipendente.

### La zona raffinata (idea dell'utente)

Definizione: dentro l'order block, il sotto-intervallo dove la base della
candela OB e la base della candela successiva combaciano
([max dei minimi, min dei corpi bassi]; speculare per il ribassista). Esiste
per 4.801 delle 5.017 zone M33. Ipotesi dichiarata: e' il cuore della domanda,
e deve rendere piu' della zona piena.

| campione | gruppo | n | R/op | delta | p permutazione |
|---|---|---|---|---|---|
| tutte (1.344) | zona piena | 160 | +0,640 | +0,553 | 0,003 |
| tutte | zona raffinata | 64 | **+1,304** | +1,209 | **0,0001** |
| tutte | **testa-a-testa** (raffinata vs solo-piena, fra le 160) | 64 | +1,304 | **+1,106** | **0,0054** |
| regola completa (348) | zona raffinata | 30 | +1,178 | +0,751 | 0,072 |
| regola completa | testa-a-testa | 30 | +1,178 | +0,677 | 0,152 |

**Sul campione largo la raffinazione aggiunge davvero**: il testa-a-testa —
fra le operazioni gia' dentro la zona piena, quelle nel cuore contro le altre —
passa la permutazione (p 0,005). Non e' la zona che si ripete: e' informazione
in piu' dentro la zona.

Sul sottoinsieme della regola completa i numeri puntano nella stessa direzione
(+1,178 R/op) ma 30 operazioni non bastano per la significativita' (p 0,15),
e per anno fa 5/7 (2020 e 2026 lievemente negativi su 2-6 operazioni l'anno).

**Verifica indipendente** (implementazione da zero): n=30, +1,1776, delta
+0,7506 — coincide alla quarta cifra. Scelte ambigue dichiarate dal
verificatore: se la candela OB coincide con quella di rottura la successiva
non e' ancora chiusa (lookahead) e la raffinata non esiste (15 zone;
sensibilita' misurata: zero). Il laboratorio mostra 29 operazioni contro le 30
dello studio: un caso limite di bordo, ininfluente.

**Stato**: promossa come opzione nel laboratorio (filtro "in zona raffinata").
NON adottata nella taratura: su 30 operazioni non si taratura niente. La
strada giusta per usarla e' l'OB COME INGRESSO (tocco della zona = segnale),
dove le operazioni sono molte di piu': studio in corso.

### Il session volume profile NON discrimina

Ipotesi esplorativa senza direzione dichiarata: la classe di liquidita' del
punto d'ingresso (bin del profilo volume causale della giornata: LVN = terzile
basso, HVN = alto) discrimina gli esiti?

| campione | classe | n | R/op |
|---|---|---|---|
| tutte | LVN (buco) | 150 | +0,119 |
| tutte | medio | 360 | +0,155 |
| tutte | HVN (eccesso) | 834 | +0,158 |

Delta LVN-HVN = -0,038 con p di permutazione **0,85**: rumore puro. Nota
strutturale: l'83% degli ingressi cade in zone medio-alte del profilo — ovvio a
posteriori, il reclaim del VWAP avviene dove si e' scambiato.

**Conseguenze**: il profilo resta nel laboratorio come strumento VISIVO (i
buchi si vedono), ma come segnale non ha mostrato nulla. E l'idea naturale per
l'obiettivo adattivo ("TP guidato dalla mappa di liquidita'") parte con la
premessa gia' falsificata: qualunque studio futuro sull'obiettivo adattivo
deve dichiarare un meccanismo diverso e battere il 1:10 fisso, che ha gia'
resistito all'obiettivo per regime (appendice K) e per qualita' del setup.
Avvertenza: volume TICK, non volume scambiato (standard sullo spot, ma va detto).

## Appendice W: l'order block come SEGNALE D'INGRESSO non funziona (48 celle su 48 negative)

Domanda dell'utente: la strategia apre troppo poco; l'OB toccato puo' diventare
il segnale d'ingresso vero e proprio su M33/M66/H2/H3, con 1-5 operazioni a
settimana? Regole pre-registrate, identiche per i quattro timeframe:

- zone OB con `zone_ob` di `export_lab` (candela contraria + rottura, causale,
  scadenza 30 barre, invalidazione oltre il lato lontano);
- primo tocco M1 della zona attiva = fill limite sul bordo della zona;
- stop sul lato lontano + 0,30 $ di margine (rischio accettato 0,5-20 $);
- RR 2/3/5/10; filtri: nessuno / contesto H6+H2 allineato / contesto+macro;
- spread 0,63 $ (quello reale attuale), finestra 7-19 UTC, max 3/giorno,
  chiusura forzata alle 21.

### Risultato: la frequenza c'e', il vantaggio no

La frequenza chiesta e' raggiungibile (M33 filtrato 1,7-2,5/settimana, M66
1,1-3,4, H2/H3 0,5-1,8). Ma **tutte le 48 celle perdono**, da -0,11 a -0,30 R
per operazione. La migliore per timeframe:

| tf | zone | tocchi | miglior cella | n | op/sett | R/op | anni pos su 7 |
|---|---|---|---|---|---|---|---|
| M33 | 5.017 | 2.037 | contesto+macro, 1:10 | 579 | 1,7 | **-0,112** | 3 |
| M66 | 2.512 | 1.144 | nessun filtro, 1:5 | 1.144 | 3,4 | **-0,139** | 2 |
| H3 | 955 | 447 | contesto H6+H2, 1:2 | 265 | 0,8 | **-0,149** | 2 |
| H2 | 1.369 | 620 | contesto+macro, 1:2 | 259 | 0,8 | **-0,161** | 1 |

Verifica avversariale (reimplementazione da zero, agente indipendente):
M33 contesto+macro 1:3 → -0,149 contro -0,148 del calcolo principale (n 582
contro 579, bordo); H2 nessuno 1:5 → -0,224 contro -0,220. Confermato.

### Lettura

Coerente con tutto il resto dello studio: **l'OB e' un filtro, non un
ingresso**. Il tocco della zona da solo non ha vantaggio (qui: -0,15 R/op
mediano); e' il tocco della zona SUL segnale gia' validato (reclaim del VWAP
con conferme) che seleziona le operazioni buone (appendice P: +0,640 contro
+0,087). Ennesima conferma della legge sulla frequenza (appendice S): piu'
operazioni = vantaggio diluito sotto il costo. La strada "piu' operazioni
tramite OB come trigger" e' chiusa; la strada aperta resta "OB come filtro
di qualita'" gia' nel laboratorio.

Dati completi (48 celle): `docs/studies/dati/ob-come-ingresso.parquet`.

## Appendice X: proteggersi dai drawdown — cosa regge e cosa no

Domanda dell'utente guardando la curva del conto: "nella fase finale c'e'
troppa escursione, dobbiamo proteggerci". Tre fatti misurati sulla serie
ufficiale (348 operazioni, pareggio +3R, spread 0,30).

**1. L'escursione finale e' in gran parte ottica.** Col rendimento composto il
capitale a fine storico e' piu' che raddoppiato: la stessa oscillazione in R
appare doppia in euro. In R la fase ottobre 2025 - giugno 2026 e' il DD massimo
storico (17,6 R in 27 operazioni) ma dello stesso ordine degli altri anni
(13,4 R nel 2024, 10,3 nel 2025): non un cambio di regime della strategia.

**2. Gli esiti si raggruppano un po', i mesi no.** Autocorrelazione lag-1 del
segno +0,119 (p 0,03); autocorrelazione dei risultati mensili -0,005 (p 0,97).
Quindi uno stop mensile ("fermati dopo un mese a -8R") non ha alcuna base — e
infatti misurato non aggiunge nulla (+0,0% a parita' di DD).

**3. Le regole di riduzione del rischio non superano il controllo di
permutazione.** Confronto onesto: ogni regola contro la base, A PARITA' di
drawdown massimo (bisezione sul rischio), vince chi fa piu' capitale. Poi lo
stesso confronto su 200 serie rimescolate, dove il raggruppamento e' distrutto:
quel che sopravvive al rimescolamento e' vantaggio meccanico, non segnale.

| regola | vantaggio osservato | parte meccanica (perm.) | p |
|---|---|---|---|
| dimezza dopo 2 perdite di fila | +17,5% | +3,9% | 0,15 |
| dimezza quando il DD supera 8R | +19,4% | +10,3% | 0,32 |
| stop mensile a -8R | +0,0% | — | — |

"Dimezza dopo 2 perdite" e' la piu' promettente (il grosso del vantaggio non e'
meccanico) ma p 0,15 non basta — stesso metro dell'appendice V: suggestivo,
non dimostrato. Da rivedere quando lo storico si allunga.

**Conseguenza operativa**: la protezione dimostrata e' il selettore del
rischio (0,5% → DD storico ~9%), piu' l'aspettativa giusta: 13 perdite di fila
e 33 operazioni senza nuovi massimi SONO nel copione. Le regole dinamiche
restano fuori dalla taratura.

## Appendice Y: VWAP ancorato agli estremi non rotti (registrazione)

Idea dell'utente: VWAP ancorato all'ultimo massimo NON ancora rotto e
all'ultimo minimo non rotto, esteso in avanti, su tutti i timeframe, per
valutare le confluenze.

### Regole registrate PRIMA dei risultati

- TF: M33, M66, H2, H3, H6, H12. Su ciascuno: swing k=3 per lato, confermato
  alla chiusura della k-esima candela dopo l'estremo (come `structure.py`).
- Ancora ALTA = ultimo swing high confermato non superato da una chiusura di
  quel TF; rotta la chiusura sopra, si passa al successivo confermato (anche
  nessuno, finche' non ne nasce uno). Simmetrico per l'ancora BASSA.
- AVWAP su M1 (prezzo tipico HLC/3 pesato col volume tick) dall'estremo
  dell'ancora; utilizzabile solo dalla conferma in poi. Tutto causale.
- Appartenenza: |ingresso - AVWAP| <= 0,5 x rischio dell'operazione (stessa
  convenzione degli order block). 12 serie (6 TF x alto/basso); confluenza =
  quante serie entro il margine.
- Campione: le operazioni del campione largo full:H6 con esito della
  configurazione ufficiale (strutturale, pareggio +3R, 1:10, spread 0,30);
  sotto-analisi sulla regola completa.
- PLACEBO obbligatorio: ancore finte scelte a caso tra gli swing confermati
  dello stesso TF con la stessa distribuzione di eta'. Se il delta reale non
  batte il placebo, l'effetto e' "vicino a una media qualunque" (fine che ha
  fatto Fibonacci, appendice O).
- Test: delta dentro/fuori con permutazione; placebo; monotonia della
  confluenza; valore incrementale sulle operazioni gia' accettate dalle
  conferme e su quelle scartate.

### Previsioni (scritte prima di misurare)

1. Copertura 25-45% (il segnale nasce sul VWAP giornaliero: le medie si
   assomigliano).
2. Delta reale piccolo, 0 / +0,3 R per operazione; 50/50 che passi p<0,05.
3. Il rischio principale e' che il placebo sopravviva: "vicino a un AVWAP"
   potrebbe essere solo "prezzo in equilibrio", comunque ancorato.
4. Confluenza non monotona (le code hanno campioni minuscoli).

### Risultati (misurati dopo la registrazione qui sopra)

Campione largo full:H6, 1897 operazioni, esito ufficiale, margine 0,5 x rischio.
Sette agenti (uno per TF + verifica avversariale H2 reimplementata da zero:
coperture identiche alla seconda cifra, delta -0,193 riprodotto).

| tf | copertura | delta dentro/fuori | p | placebo | p |
|---|---|---|---|---|---|
| M33 | 78% | **+0,255** | 0,034 | **+0,261** | 0,030 |
| M66 | 84% | +0,095 | 0,48 | -0,254 | 0,046 |
| H2 | 69% | **-0,193** | 0,08 | **-0,216** | 0,033 |
| H3 | 51% | -0,170 | 0,08 | -0,111 | 0,28 |
| H6 | 28% | +0,046 | 0,69 | +0,039 | 0,77 |
| H12 | 12% | -0,179 | 0,25 | -0,010 | 0,95 |

- Dove il delta reale sembra dire qualcosa (M33 positivo, H2 negativo), il
  PLACEBO fa esattamente lo stesso: l'informazione non sta nell'ancora agli
  estremi non rotti, sta nell'essere vicini a una media ancorata qualunque
  (proxy di "prezzo in equilibrio"). Stessa fine di Fibonacci (appendice O).
- Confluenza NON monotona, come previsto: 0 serie -0,218; 1-2 serie +0,211;
  3-4 +0,067; 5+ +0,077.
- ">=1 serie su 12" copre il 93,7% degli ingressi (placebo 95,1%): inutile
  come filtro per costruzione.
- Sottoinsieme ufficiale (348): segni instabili fra TF (M33 +0,50 dentro vs
  +0,43 fuori; H2 invertito +0,28 vs +0,83). Nessun filtro adottabile.

**Conclusione**: previsioni 3 e 4 della registrazione confermate; la copertura
reale (fino al 94%) e' persino sopra la previsione 1. L'AVWAP ancorato agli
estremi non rotti NON discrimina oltre il placebo su nessun timeframe: non
entra ne' nella strategia ne' nel laboratorio come criterio. Dati per
operazione in `avwapf_<TF>.parquet` (scratchpad di sessione, ricalcolabili
con le regole registrate).
