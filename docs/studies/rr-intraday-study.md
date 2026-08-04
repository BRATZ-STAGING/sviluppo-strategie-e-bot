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

## Appendice Z: tocco dell'OB valido solo dopo un allontanamento minimo (registrazione)

Idea dell'utente: il fill dell'order block vale solo se prima il prezzo si e'
allontanato dalla zona di almeno 50 punti sui TF medio-alti e 10/20 su quelli
medio-bassi. Regole registrate prima di misurare:

- Zone `zone_ob` (piene) su M33, M66, H2, H3; operazioni del campione largo
  full (1897), esito ufficiale (strutturale, +3R, 1:10, spread 0,30).
- ESCURSIONE di una zona al momento del tocco: quanto il prezzo si e' spinto
  oltre il bordo della zona NEL VERSO della rottura, dall'attivazione al
  minuto d'ingresso (rialzista: massimo dei massimi M1 - bordo alto; opposto
  per la ribassista). Per ogni operazione in zona (margine 0,5 x rischio, come
  sempre) si tiene l'escursione MASSIMA fra le zone concordi che la
  contengono. Tutto causale.
- Soglie D: 0 (base attuale) / 10 / 20 / 50 $, misurate su TUTTI e quattro i
  TF: la mappa dell'utente (50 sui medio-alti, 10-20 sui medio-bassi) e'
  l'ipotesi da confermare, non una griglia da minare.
- Test: fra le operazioni IN zona, delta R/op fra tocco con escursione >= D e
  tocco con escursione < D, con permutazione; controllo che la base D=0 su
  M33 riproduca i flag del laboratorio; verifica avversariale su un TF.

Previsioni: (1) plausibile che il vantaggio degli OB si concentri nei tocchi
con un minimo di escursione (il ritorno DOPO l'allontanamento e' il retest
"vero") - 50/50 che regga la permutazione; (2) D=50 sui TF piccoli lascera'
pochissime operazioni, stime instabili; (3) se non discrimina, il filtro
attuale resta com'e'.

## Appendice AA: entrare SUL livello invece che alla chiusura (registrazione)

Critica dell'utente, la piu' fondata ricevuta finora: «non stai usando bene i
miei livelli, ci sono un sacco di OB su M6/M12/M33/H3/H6; ci sono operazioni
valide ma non entra bene sui livelli, quindi le apre storpiate, sono meno e
troppe in perdita».

Ha ragione su un fatto: la strategia entra **a mercato alla chiusura della
candela M6 del segnale**, cioe' dove il prezzo si trova in quel momento, non
dove sta il livello. Gli order block finora sono stati usati solo come
ETICHETTA (l'ingresso cadeva o no dentro una zona), mai come **prezzo di
ingresso**. Questo studio prova la sua versione.

### Regole registrate PRIMA dei risultati

- Zone `zone_ob` su CINQUE timeframe: M6, M12, M33, H3, H6 (quelli citati).
- Segnale invariato (reclaim del VWAP con contesto H6+H2), due campioni:
  (A) regola ufficiale completa, (B) campione largo senza le conferme.
- Ingresso: NON al prezzo di chiusura. Ordine LIMITE sul bordo vicino della
  zona concorde piu' vicina dalla parte del ritracciamento (long: zona sotto,
  limite sul bordo alto). Distanza massima ammessa dal prezzo di segnale:
  5 / 10 / 20 $. Valido fino a fine giornata: se non riempito, niente
  operazione.
- Stop: lato lontano della zona ± 0,30 di margine; rischio accettato 0,5-20 $.
- Obiettivi 1:3 / 1:5 / 1:10, pareggio nessuno e +3R, spread 0,30 e 0,63.
- Conservativo: nello stesso minuto lo stop prevale sull'obiettivo.

### Previsioni (scritte prima di misurare)

1. Il rischio medio per operazione SCENDE (stop sulla zona invece che sulla
   struttura): e' il meccanismo vero che l'utente intuisce, e da solo alza il
   rendimento in R a parita' di movimento del prezzo.
2. Il numero di operazioni scende rispetto al campione di partenza: parte dei
   segnali non trova zona vicina, parte non viene mai riempita.
3. Contro-effetto: entrando in ritracciamento si PERDONO i vincitori che
   scappano senza tornare indietro, che nella strategia in vigore sono quelli
   che pagano tutto (il 3,2% che tocca 1:10 fa il grosso del +171R).
4. Saldo netto incerto, 50/50. La percentuale di stop presi salira' (stop piu'
   stretto), quindi la domanda giusta NON e' «quanti stop prendo» ma «quanto
   rende per operazione».

### Risultati (misurati dopo la registrazione qui sopra)

46.667 zone sui cinque timeframe, 1.897 segnali. Confronto sulla regola
ufficiale (spread 0,30, esito ufficiale):

| versione | op | R/op | R tot | stop presi | anni + |
|---|---|---|---|---|---|
| **a mercato (in vigore)** | 348 | **+0,492** | **+171,1** | 54% | **7/7** |
| sul livello, stop sulla zona (10 $, 1:10) | 206 | +0,288 | +59,3 | 72% | 4/7 |
| sul livello, stop strutturale (10 $, 1:10, +3R) | 189 | +0,367 | +69,4 | 64% | 4/7 |

Previsione 1 CONFERMATA: il rischio mediano crolla da 4,23 a ~2,2 $. Lo stop
strutturale batte quello appoggiato alla zona (+0,367 contro +0,288): il bordo
e' fragile, il prezzo lo penetra di qualche dollaro e torna. Ma entrambe
perdono contro la versione a mercato, e la costanza per anno crolla a 4/7.

### Perche': il ritracciamento SELEZIONA i fallimenti

Il risultato decisivo. Delle 348 operazioni ufficiali, 222 tornano su un
livello (e quindi verrebbero riempite da un ordine limite), 126 no. Nella
strategia IN VIGORE, quelle stesse operazioni rendono:

| gruppo | op | R/op | R tot |
|---|---|---|---|
| tornano sul livello | 222 | **-0,387** | **-85,9** |
| non tornano mai | 126 | **+2,040** | **+257,0** |

**Il ritracciamento e' un segnale negativo, non un'occasione di prezzo
migliore.** Su questa strategia il vantaggio sta tutto nella prosecuzione
immediata: le 12 operazioni che superano +8R valgono +117,5 R, il 69% del
risultato di sette anni, e solo 3 di esse tornano su un livello. Aspettare il
livello significa, sistematicamente, farsi riempire dalle operazioni che
stanno fallendo e restare fuori da quelle che pagano.

Non e' un difetto di taratura ne' un caso: e' la logica del segnale. Il
reclaim del VWAP con la struttura allineata cattura una ripartenza; se il
prezzo torna indietro fino a un order block, la ripartenza non c'e' stata.

**Conseguenza operativa**: l'ordine limite sul livello e' respinto per QUESTA
strategia. Resta valido l'uso degli order block come FILTRO (appendice P) —
ingresso a mercato, ma sapendo di essere dentro una zona. E resta l'avvertenza
per l'operativita' manuale: su questo segnale, l'ingresso in ritracciamento
non e' un prezzo migliore, e' un'operazione diversa e peggiore.

## Appendice AB: strategia AVWAP a eventi — scrematura (registrazione)

Proposta dell'utente, strategia NUOVA da zero su XAUUSD: AVWAP ancorati agli
estremi non rotti con tre livelli (VWAP e bande), session volume profile,
segnali = tocco del livello / rottura con chiusura oltre / retest / incrocio
delle bande dei due AVWAP; estensioni di Fibonacci e vuoti di liquidita' come
zone TP. Scrematura su M3/M6/M12/M20/M33/M66/H2/H3/H6.

Avvertenze registrate: la VICINANZA all'AVWAP e' gia' morta contro placebo
(app. Y), il volume profile come discriminante pure (app. V), i ritracciamenti
Fibo pure (app. O). La parte mai testata sono gli EVENTI DINAMICI: rotture,
retest, incroci di bande. La scrematura decide su quelli.

### Regole registrate PRIMA dei risultati

- Ancore come in appendice Y (swing k=3, non rotti da chiusure del TF,
  ri-ancoraggio causale). AVWAP su M1 (tipico, peso volume tick) + sigma
  pesata causale. Livelli per ancora: VWAP, +-1, +-2, +-3 sigma.
- Eventi per candela del TF, tutti causali (livello noto alla candela
  precedente):
  - TOCCO: la candela tocca il livello e chiude dallo stesso lato di prima.
    Ipotesi: il livello tiene, il prezzo riparte dal lato di provenienza.
  - ROTTURA: chiusura oltre il livello (lato diverso dalla candela prima).
    Ipotesi: continuazione nel verso della rottura.
  - RETEST: dopo una rottura del VWAP (entro 30 candele), primo ritorno sul
    livello con chiusura ancora dal lato della rottura. Ipotesi: riparte nel
    verso della rottura.
  - COMPRESSIONE: le bande 1-sigma dei due AVWAP (ancora alta e bassa)
    iniziano a sovrapporsi. Ipotesi non direzionale: espansione del movimento.
- Esito: spostamento della chiusura a 5 e 20 candele, in unita' di ATR
  giornaliero, nel verso dell'ipotesi (assoluto per la compressione).
- PLACEBO integrale: stessa pipeline con ancore su swing confermati scelti a
  caso con eta' simile (seme fisso). Un evento sopravvive solo se batte SIA
  il caso SIA il placebo.
- Soglia di sopravvivenza: ~144 celle testate (9 TF x 2 ancore x famiglie),
  quindi p < 0,0003 (Bonferroni) su entrambi gli orizzonti E delta positivo
  contro placebo. Sotto soglia = bocciato, senza appello ne' seconde griglie.
- Fibo-estensioni e vuoti di liquidita' come TP: SOLO per gli eventi
  sopravvissuti, in una fase 2 con placebo dedicato. Niente "ecc": quello che
  non e' scritto qui non viene testato.

Previsione: i tocchi faranno la fine dell'appendice Y (placebo li replica);
per rotture e retest 60/40 che non sopravviva nulla alla soglia; la
compressione e' la piu' plausibile come segnale di volatilita' (non di
direzione). M20 aggiunto ai timeframe canonici per questo studio.

### Risultati (misurati dopo la registrazione qui sopra)

8,7 milioni di eventi su nove timeframe (implementazione unica in
`run_avwap_eventi.py`; conteggio degli swing identico a quello trovato dagli
agenti indipendenti dell'appendice Y sui TF in comune: controllo incrociato
superato). 261 celle contro la soglia registrata.

**Eventi direzionali: bocciatura totale, zero celle su 232.** Nessun tocco,
nessuna rottura, nessun retest, su nessun livello (VWAP o bande 1/2/3 sigma),
nessuna ancora e nessun timeframe supera p<0,0003 con delta positivo sul
placebo. La cella direzionale migliore in assoluto (tocco banda -2 sigma H6,
ancora alta) fa p 0,03 sull'orizzonte corto: sarebbe bocciata anche senza
correzione per i test multipli. Previsione 1 confermata; la 60/40 su rotture
e retest si e' risolta sul lato "niente".

**Compressione: quattro celle passano il criterio formale, ma e' un artefatto
del criterio.** L'esito della compressione e' uno spostamento ASSOLUTO,
sempre positivo per costruzione: il test "batte il caso" e' privo di senso su
una grandezza assoluta, e infatti "passa" con qualunque n grande. Il
confronto che conta e' col placebo: da +0,003 a +0,007 ATR, cioe' 10-20
centesimi di dollaro su XAUUSD — meno di un terzo dello spread reale. Sui TF
alti il segno del delta oscilla pure (H2 e M66 negativi). Nessun segnale
sfruttabile; al massimo conferma l'ovvio, che bande compresse precedono
espansione, con un'entita' indistinguibile dal placebo.

**Conclusione**: la strategia "AVWAP a eventi" non ha superato la scrematura
in nessuna componente. La fase 2 (Fibo-estensioni, vuoti di liquidita' come
TP) non si apre: era condizionata ai sopravvissuti, e non ce ne sono. Grezzi
ricalcolabili con lo script; nel repo resta l'aggregato
(`avwap-eventi-aggregato.parquet`, 522 righe).

## Appendice AC: audit di sensibilita' di TUTTI i parametri (registrazione)

Richiesta dell'utente: "testa tutto e valutiamo tutti i parametri". Non e' una
ri-taratura: e' la mappa dell'altopiano. Ogni parametro della taratura
ufficiale viene mosso UNO ALLA VOLTA (26 varianti registrate qui sotto, prima
di misurare) e si osserva il risultato 2020-2026 con esito ufficiale.

Varianti: ora_inizio 6/8; ora_fine 17/18/20; ora_chiusura 20/22; max
operazioni/giorno 2/5; attesa 0/60 minuti; media macro 30/100; fattore alta
volatilita' 1,3/1,7; k dei frattali 2/4; buffer 0,15/0,60; impulso minimo
3/5; rischio minimo 0,5/2; rischio massimo 7/15; barre dello stop 3/8.
(RR, pareggio, conferme e tipi di stop: gia' misurati, appendici K/L/Q/T.)

Interpretazione REGISTRATA: un parametro e' FRAGILE se una variante adiacente
taglia il totale oltre il 40% o fa passare gli anni positivi sotto 6/7. La
taratura NON cambia in base a questo audit, qualunque cosa esca: una cella
migliore del base qui non e' una scoperta, e' rumore di vicinato finche' non
passa la procedura fuori campione. Lo scopo e' sapere se il bot poggia su un
altopiano o su una punta.

### Risultati: ALTOPIANO, zero parametri fragili su 26 varianti

Base riprodotta al decimale (348 op, +171,1R, 7/7, conto 49.321). Tutte le 26
varianti restano positive, fra +121 e +186 R totali; nessuna taglia oltre il
40% ne' scende sotto 6 anni positivi su 7. Perdita massima sempre fra il 12 e
il 19,6%.

I parametri piu' sensibili (e comunque dentro l'altopiano):

| variante | n | R tot | delta | anni+ |
|---|---|---|---|---|
| frattale_k 3→4 | 360 | +121,1 | -29% | 6/7 |
| impulso_min 4→5 | 290 | +125,5 | -27% | 6/7 |
| ora_inizio 7→8 | 316 | +143,7 | -16% | 7/7 |
| buffer 0,30→0,60 | 347 | +149,0 | -13% | 6/7 |

Lettura: le due leve vere della strategia sono la DEFINIZIONE della struttura
(k dei frattali) e la SOGLIA di impulso — sensato, sono il cuore del segnale.
Orari, macro, cooldown, limiti di rischio, barre dello stop e fattore di
volatilita' spostano poco o nulla (il fattore alta volatilita' quasi zero:
1,3/1,5/1,7 danno lo stesso risultato).

Cinque varianti escono sopra il base (massimo +9%: frattale_k=2, attesa 0,
impulso 3, macro 100, ora_fine 18). Come registrato: rumore di vicinato, la
taratura NON cambia. Se mai, sono candidati per una futura verifica fuori
campione — non adesso, non su questi dati.

**Conclusione per il bot**: la strategia poggia su un altopiano largo. Un EA
che sbagliasse di poco un orario, una soglia o un parametro strutturale
resterebbe profittevole: il rischio di implementazione e' basso. Dati in
`sensibilita.parquet`.

## Appendice AD: k=2 governata dal livello preciso dell'OB — non aggiunge

Idea dell'utente dopo l'audit AC: tenere la k=3 (7/7) ma recuperare la
variante k=2 usando la zona raffinata dell'order block come cancello di
qualita'. Due forme, misurate subito dopo la registrazione in chat:

| configurazione | n | R tot | R/op | anni+ |
|---|---|---|---|---|
| ufficiale k=3 | 348 | +171,1 | +0,492 | **7/7** |
| k=2 tutte | 331 | +186,1 | +0,562 | 6/7 |
| A: k=2 solo in zona piena | 77 | +27,3 | +0,355 | 5/7 |
| A': k=2 solo in zona raffinata | 31 | +24,3 | +0,785 | 4/7 |
| segnali solo-k2 (non visti dalla k=3) | 117 | +33,0 | +0,282 | 4/7 |
| — di questi, in zona piena | 27 | **-6,9** | -0,257 | 2/7 |
| — di questi, in zona raffinata | 9 | +0,6 | +0,071 | — |
| B: innesto k3 + solo-k2 in piena | 375 | +164,2 | +0,438 | 7/7 |
| B': innesto k3 + solo-k2 in raffinata | 357 | +171,7 | +0,481 | 7/7 |

Il filtro duro (A/A') decima il campione come sempre. L'innesto (B/B') non
danneggia ma non aggiunge: +0,6 R in sette anni con la raffinata, -6,9 con la
piena. Il dato interessante e' che il cancello OB, che sulle operazioni
UFFICIALI seleziona bene (appendice P), sui segnali extra della k=2 non
seleziona nulla (in piena addirittura sceglie peggio del mucchio): quei
segnali anticipati sono rumore strutturale che nessun livello ripulisce.

**Conclusione**: taratura invariata (k=3). La strada "recuperare segnali in
piu' con un cancello di qualita'" e' misurata e chiusa anche in questa forma.

## Appendice AE: obiettivo sui livelli strutturali (registrazione)

Richiesta dell'utente: tenere la taratura ufficiale e cercare livelli
(resistenze/supporti, OB, ecc.) su cui appoggiare l'obiettivo, per aumentare
i TP presi (oggi 11 su 348) ed essere piu' precisi.

Meccanismo dichiarato (vincolo dell'appendice V): il prezzo rigetta sui
livelli strutturali VISIBILI; obiettivo appena prima del livello = incassare
la corsa prima del rigetto. Diverso dalla mappa di liquidita' (falsificata).
Asticella: battere il 1:10 fisso, +171,1R sulle stesse 348 operazioni.

### Regole registrate PRIMA dei risultati

- Operazioni: le 348 ufficiali, stop e pareggio +3R invariati, spread 0,30.
- Famiglie di livelli (tutte causali al momento dell'ingresso), per i long il
  livello sta SOPRA l'entry, speculare per gli short:
  1. swing confermati (k=3) non ancora superati da una chiusura, su M33 / H2 / H6;
  2. bordo vicino della zona OB CONTRARIA attiva su M33 (per i long, zona
     ribassista sopra il prezzo);
  3. massimo/minimo del giorno precedente;
  4. massimo/minimo della sessione Asia del giorno (00-07 UTC);
  5. numeri tondi (multipli di 10 $ e di 25 $) — comparatore senza struttura.
- Obiettivo = livello piu' vicino oltre l'entry, meno 0,10 $ (long; +0,10
  short). Due varianti per famiglia: senza distanza minima, e distanza minima
  3R. Se nessun livello: si resta al 1:10 ufficiale.
- Esito ricalcolato al minuto con lo stesso motore (stop batte obiettivo,
  pareggio +3R, chiusura 21).
- PLACEBO A DISTANZE UGUALI, il controllo decisivo: per ogni famiglia, le
  stesse distanze in R rimescolate a caso fra le operazioni (500 giri, seme
  fisso). Se la famiglia non batte il suo placebo, il livello non aggiunge
  nulla oltre alla propria distribuzione di distanze.
- Metriche: R totale (asticella +171,1), % TP presi, anni positivi, delta
  contro placebo.

Previsioni: (1) i TP presi saliranno molto (ovvio: obiettivi piu' vicini);
(2) il totale NON batter'a il 1:10 per le famiglie vicine (decapitano le
corse, meccanismo appendice K); (3) l'unica con una chance e' lo swing H6 o
il giorno-prima con minimo 3R (lontani quanto basta); (4) 60/40 che nessuna
batta il placebo a distanze uguali.

### Risultati: nessuna famiglia batte il 1:10 fisso

Base riprodotta al decimale (+171,1 R, 11 TP = 3,2%). Otto famiglie, due
varianti di distanza minima; ``ob_contrario`` scartata (meno di 30 operazioni
con una zona contraria attiva sopra/sotto l'ingresso: gli OB contrari quasi
non esistono nel verso giusto al momento dell'ingresso).

| famiglia | min | n | rr med | R tot | TP presi | anni+ | placebo | p |
|---|---|---|---|---|---|---|---|---|
| asia | — | 292 | 1,2 | **-14,1** | 22% | 2/7 | -19,6 | 0,14 |
| tondi 10 $ | — | 324 | 1,0 | **-31,7** | 24% | 2/7 | -31,6 | 0,50 |
| giorno prima | — | 187 | 1,5 | +78,9 | 11% | 6/7 | +81,7 | 0,65 |
| tondi 25 $ | — | 335 | 2,5 | +73,6 | 18% | 4/7 | +38,4 | 0,00 |
| swing M33 | — | 336 | 193 | +121,4 | 7% | 5/7 | +117,0 | 0,47 |
| swing H2 | — | 342 | 184 | +150,5 | 6% | 5/7 | +120,4 | 0,04 |
| swing H6 | — | 346 | 177 | +173,2 | 5% | 6/7 | +128,8 | **0,00** |
| swing H6 | 3R | 277 | 335 | **+184,4** | 2% | 7/7 | +173,3 | 0,11 |
| tondi 25 $ | 3R | 138 | 4,8 | +182,8 | 5% | 7/7 | +156,0 | 0,01 |

Previsione 1 confermata in pieno: i TP presi salgono fino al 24% (asia 22%,
tondi 22-24%). Previsione 2 pure: **quelle stesse famiglie sono le peggiori**
— asia -14,1 R e tondi 10 $ -31,7 R, cioe' da +171 a sotto zero. Piu' TP
presi = strategia distrutta, con la relazione monotona: piu' e' vicino il
livello, peggio va (rr mediano 1,0 -> -31,7; 1,2 -> -14,1; 1,5 -> +78,9;
2,5 -> +73,6; 4,8 -> +182,8).

Le due celle che sfiorano il base sono un abbaglio da leggere bene: swing H6
e swing M33 con minimo 3R hanno **rr mediano 335 e 345**, cioe' un obiettivo
cosi' lontano da non essere mai raggiunto (TP 2%). Non sono "obiettivi sui
livelli": sono la strategia SENZA tetto, che infatti rende +181/+184 contro
+171. Il livello non c'entra — lo dice il placebo, che alle stesse distanze
fa +173/+181.

Un solo segnale genuino: **swing H6 senza minimo batte nettamente il proprio
placebo** (+173,2 contro +128,8 ± 18,6, p<0,005). Alle stesse distanze
casuali si perderebbero 45 R: il livello H6 sa dove NON mettere l'obiettivo.
Ma pareggia soltanto il 1:10 fisso (+173,2 contro +171,1) con meno anni
positivi (6/7 contro 7/7), quindi non e' adottabile. L'informazione c'e', il
vantaggio operativo no.

Nota di metodo: la famiglia dei numeri tondi — il comparatore SENZA struttura
— e' fra quelle con p piu' basso (0,00 e 0,01). Un comparatore nullo che
"vince" e' il segno che a queste distanze il confronto e' dominato dal
rumore, non che i numeri tondi funzionino.

**Conclusione**: l'obiettivo sui livelli e' respinto. Aumentare i TP presi si
puo' (fino al 24%) ma costa l'intera redditivita': il 1:10 resta, ed e' ormai
il quarto studio che lo conferma (K, V, AB, AE). Dati in
`tp-livelli.parquet`.

## Appendice AF: stop strutturale scalato x obiettivo (registrazione)

Ultima prova richiesta dall'utente su stop e RR. L'asse mai testato: non stop
fissi in punti (gia' fatto, app. Q/T) ma un MOLTIPLICATORE sullo stop
strutturale, incrociato con obiettivi fino a 1:20.

- 348 operazioni ufficiali, spread 0,30, chiusura 21, motore invariato.
- Moltiplicatore m dello stop: 0,50 / 0,75 / 1,00 / 1,25 / 1,50 / 2,00
  (m=1 = taratura in vigore). Il percorso in R si riscala di 1/m, e con esso
  il costo dello spread: uno stop doppio dimezza le R guadagnate ma dimezza
  anche il peso del costo.
- Obiettivo: 2 / 3 / 5 / 8 / 10 / 15 / 20. Pareggio: nessuno e +3R.
- 84 celle. Asticella: +171,1 R e 7 anni positivi su 7.

Previsioni: (1) m=1 vicino all'ottimo, con la campana gia' osservata sulla
larghezza dello stop; (2) m<1 peggiora molto (lo stop stretto viene preso dal
rumore: e' la lezione di Q, U e AA); (3) m>1 perde poco e potrebbe pareggiare
(meno stop presi, ma ogni R vale meno); (4) l'obiettivo migliore resta 10 o
sale a 15-20 quando lo stop e' largo, perche' in R l'obiettivo si avvicina;
(5) nessuna cella batte il base in modo netto E con 7/7.

### Risultati: m=1 e' il crinale, 84 celle su 84 confermano la taratura

R totale, pareggio +3R (la riga m=1,00 e' la taratura in vigore):

| m \ obiettivo | 1:2 | 1:3 | 1:5 | 1:8 | **1:10** | 1:15 | 1:20 |
|---|---|---|---|---|---|---|---|
| 0,50 | -75,6 | 22,4 | 28,4 | 51,5 | 66,9 | 94,9 | 118,1 |
| 0,75 | -34,3 | 55,7 | 83,3 | 92,5 | 98,9 | 113,4 | 114,3 |
| **1,00** | 17,4 | 108,4 | 126,9 | 151,0 | **171,1** | 168,0 | 173,0 |
| 1,25 | 16,3 | 91,3 | 95,3 | 126,8 | 122,3 | 127,3 | 132,3 |
| 1,50 | 30,9 | 91,9 | 95,5 | 111,6 | 112,0 | 117,0 | 121,4 |
| 2,00 | 40,8 | 79,8 | 99,1 | 100,6 | 104,6 | 109,8 | 109,8 |

Tutte e cinque le previsioni confermate. La riga m=1 domina l'intera griglia
per ogni obiettivo da 1:3 in su: **lo stop strutturale e' un crinale, non un
punto scelto a caso**. Sotto (m<1) si crolla — a m=0,50 gli stop presi vanno
al 77% — e sopra (m>1) si perde il 25-40% pur prendendo meno stop, perche'
ogni R vale meno. La colonna 1:2 e' negativa o quasi ovunque: e' la firma
della strategia, che vive delle corse lunghe.

Le uniche due celle sopra il base:

| cella | R tot | anni+ | DD | conto |
|---|---|---|---|---|
| m=0,50, 1:20, senza pareggio | **+187,9** | 6/7 | **30,0%** | 49.249 EUR |
| m=1,00, 1:20, pareggio +3R | +173,0 | 7/7 | 16,3% | **49.922 EUR** |
| **m=1,00, 1:10, +3R (in vigore)** | +171,1 | **7/7** | **16,3%** | 49.321 EUR |

La prima e' un miraggio da manuale: +10% di R ma con **il doppio del
drawdown** (30% contro 16,3%), un anno in perdita e il 77% di stop presi. A
parita' di dolore rende MENO del base, e in euro fa gia' meno (49.249 contro
49.321) perche' la composizione punisce i cali profondi.

La seconda e' la stessa taratura con l'obiettivo a 1:20 invece che 1:10:
+1,9 R e 600 EUR su sette anni, con TP presi allo 0,29% (una operazione su
348). Non e' un'altra strategia, e' il tetto alzato ancora di piu' — la
conferma finale che il 1:10 e' gia' "praticamente nessun tetto", e che oltre
quel punto non c'e' piu' niente da guadagnare.

**Conclusione**: taratura invariata, con la mappa completa alle spalle. Dati
in `stop-rr.parquet`.

## Appendice AG: la frontiera a parita' di drawdown (stabilita' contro rendimento)

Domanda dell'utente: col 1:10 solo il 3% tocca l'obiettivo; esistono
condizioni con piu' stabilita' e meno stop, magari anche piu' redditizie?
Confronto onesto: ogni cella (moltiplicatore stop x obiettivo x pareggio)
portata allo STESSO drawdown del base (16,3%) muovendo il rischio, poi
confrontata su conto finale e su tre misure di stabilita' (anni positivi,
anno peggiore, operazioni consecutive sotto il massimo precedente).

| cella | rischio | conto | stop presi | vinte | anni+ | anno peggiore | sotto-max |
|---|---|---|---|---|---|---|---|
| m1, 1:20, +3R | 1,00% | 49.929 | 54% | 35% | 7/7 | +4,2R | 33 |
| **m1, 1:10, +3R (in vigore)** | **1,00%** | **49.328** | 54% | 35% | **7/7** | **+6,9R** | **33** |
| m1, 1:10, +2R | 1,13% | 48.552 | **49%** | 32% | 7/7 | +2,4R | 49 |
| m1, 1:8, +3R | 1,00% | 41.027 | 54% | 35% | 7/7 | +6,7R | 33 |
| m1,5, 1:3, qualunque | 0,94% | 22.916 | **47%** | **47%** | 6/7 | **-7,6R** | 32 |

Il risultato che risponde alla domanda: **abbassare l'obiettivo compra
percentuali di successo, non stabilita'**. La cella con meno stop e piu'
operazioni vinte in assoluto (stop largo 1,5x, obiettivo 1:3: 47% di stop,
47% di vinte, TP toccato nel 17,5% dei casi) e' anche quella con l'unico
ANNO IN PERDITA (-7,6R) e con meno della meta' del conto finale (22.916
contro 49.328). Piu' vittorie, meno soldi, meno costanza: esattamente la
legge gia' vista in appendice S.

Il pareggio a +2R e' l'unico scambio reale disponibile: -5 punti di stop
presi (49% contro 54%) e anno peggiore piu' vicino a zero, pagati con il 2%
di conto e con 49 operazioni consecutive sotto il massimo invece di 33 —
cioe' MENO stabilita' nel senso che conta davvero, il tempo passato sotto
acqua. Il 1:20 fa 600 EUR in piu' del 1:10 con TP allo 0,29%: irrilevante.

**Conclusione**: sulla frontiera a pari drawdown la configurazione in vigore
e' gia' sul bordo efficiente. Non esiste, in 84 celle, una combinazione di
stop e obiettivo che dia insieme piu' soldi e piu' stabilita'.

## Appendice AH: togliere la chiusura serale (ottica prop firm)

Domanda dell'utente: senza chiusura giornaliera, tenendo solo quella del
venerdi', quante operazioni arrivano all'obiettivo e quante muoiono? Tre
regimi sulle stesse 348 operazioni, obiettivo 1:10, pareggio +3R, spread 0,30.

| regime | R tot | stop | obiettivo | pareggio | scadenza | ore medie | anni+ |
|---|---|---|---|---|---|---|---|
| giornaliera (in vigore) | +171,1 | 189 (54,3%) | **11 (3,2%)** | 24 (6,9%) | 124 (35,6%) | 4,2 | **7/7** |
| settimanale | +182,4 | 214 (61,5%) | **25 (7,2%)** | 56 (16,1%) | 53 (15,2%) | 11,2 | 6/7 |
| aperta (fino a stop/obiettivo) | **+224,1** | 221 (63,5%) | **47 (13,5%)** | 80 (23,0%) | 0 | 16,3 | 6/7 |

Risposta secca: **gli obiettivi pieni passano da 11 a 25 (settimanale) o 47
(nessuna scadenza)**, ma gli stop passano da 189 a 214-221 e i pareggi da 24 a
56-80. Le operazioni "morte" non spariscono, cambiano nome: la chiusura di
fine giornata (124 casi, +2,44 R medi) viene sostituita da stop e pareggi.

### Perche' non e' il regalo che sembra

A parita' di drawdown (bisezione sul rischio, bersaglio 16,3%):

| regime | rischio pari-DD | conto | DD a 1% | anno peggiore |
|---|---|---|---|---|
| giornaliera | 1,00% | **49.321** | **16,3%** | **+6,9 R** |
| settimanale | 0,81% | 39.399 | 19,7% | **-10,6 R** |
| aperta | 0,73% | 45.000 | 21,8% | **-10,6 R** |

Il +224 R della tenuta aperta e' comprato con volatilita': a parita' di dolore
rende MENO del base (45.000 contro 49.321), il drawdown a rischio uguale sale
al 21,8%, e in entrambi i regimi lunghi compare un anno in perdita (-10,6 R)
dove la chiusura serale ne ha sette positivi. La costanza si paga.

### Avvertenze non modellate (peggiorano i regimi lunghi, non il base)

- **Swap**: il 24% delle operazioni resterebbe aperto oltre sera; su XAU e' un
  costo reale per notte, qui non conteggiato.
- **Gap del fine settimana**: presenti nei prezzi M1, ma con lo stop che puo'
  essere saltato — il modello assume il fill al livello, ottimistico.
- **Posizioni sovrapposte**: media 1,4 e massimo 4 aperte insieme (contro 1,2
  e 3 del base): con rischio 1% ciascuna, fino al 4% esposto in un istante.

**Per una prop firm** il punto e' proprio questo: le regole tipiche puniscono
il drawdown giornaliero e l'esposizione simultanea, cioe' esattamente le due
cose che i regimi lunghi peggiorano. La chiusura serale non e' un limite da
togliere: e' il meccanismo che tiene 7 anni su 7 e il drawdown sotto controllo.

## Appendice AI: OB + volumetrica + Fibonacci insieme, ricerca libera (registrazione)

Richiesta dell'utente: rianalizzare order block, profilo volume, ritracciamenti
ED estensioni di Fibonacci INSIEME, scegliendo io i parametri migliori per i
livelli d'ingresso, per trovare una strategia solida e bilanciata nel tempo.

Precedenti da tenere presenti: Fibo respinto col placebo da solo (app. O),
profilo volume respinto come discriminante (app. V), OB respinto come
ingresso (app. W) ma valido come filtro (app. P). Mai provata la
COMBINAZIONE, ne' le estensioni Fibo come obiettivo.

### Protocollo registrato PRIMA di guardare i risultati

- Campione: le 1.897 operazioni del campione largo (contesto H6+H2 gia' nel
  segnale), esito al minuto, spread 0,30, chiusura 21 UTC.
- SEPARAZIONE OBBLIGATORIA: la ricerca dei parametri usa SOLO 2020-2023;
  2024-2026 non viene guardato finche' la scelta non e' congelata. Il verdetto
  e' il fuori campione, non la cella migliore in ricerca.
- Griglia (450 celle): OB M33 {nessuno, piena, raffinata} x margine {0,5R, 1R};
  profilo volume {nessuno, terzile basso, terzile alto}; ritracciamento Fibo
  della gamba M33 {nessuno, 50%, 61,8%, 70,5%, 78,6%} con tolleranza 0,5R;
  obiettivo {1:10 fisso, estensione 1,272, estensione 1,618}; pareggio
  {nessuno, +3R}.
- Scelta: la cella con R/op migliore in ricerca, con almeno 60 operazioni.
- Verdetto: quella cella sul 2024-2026, confrontata con l'ufficiale sullo
  stesso periodo. Si riportano anche le prime 10 celle, per far vedere quante
  sopravvivono al passaggio.
- Controllo del data mining: si dichiara quante celle battono il riferimento
  IN RICERCA (per costruzione saranno molte) e quante lo battono FUORI. Se la
  media delle prime 10 crolla fuori campione, la ricerca ha trovato rumore.

Previsione: molte celle brillanti in ricerca (e' il senso di 450 tentativi),
crollo fuori campione, e nessuna combinazione stabilmente sopra l'ufficiale.
Se invece una regge, va comunque considerata candidata e non adottata.

### Risultati: sopravvive l'order block, muore Fibonacci

136 celle valutabili (almeno 60 operazioni in ricerca) su 600. Riferimento:
tutte le operazioni con 1:10 e pareggio +3R, +0,138 R/op in ricerca e
+0,176 fuori campione. **49 celle su 136 battono il riferimento in ricerca**:
esattamente il numero che ci si aspetta cercando fra centinaia, ed e' il
motivo per cui il verdetto e' solo il fuori campione.

Le prime dieci celle scelte SOLO su 2020-2023, misurate su 2024-2026:

| # | order block | volume | fibo | R/op ricerca | n | **R/op fuori** | tot fuori |
|---|---|---|---|---|---|---|---|
| 1 | piena, margine 0,5R | terzile alto | — | +0,589 | 46 | **+1,168** | +53,7 |
| 3 | raffinata, margine 1R | terzile alto | — | +0,535 | 51 | **+1,139** | +58,1 |
| 5 | piena, margine 0,5R | qualunque | — | +0,436 | 68 | **+0,916** | +62,3 |
| 9 | nessuno | terzile medio | **50%** | +0,359 | 87 | **-0,092** | -8,0 |
| 10 | piena, margine 1R | terzile alto | — | +0,344 | 76 | +0,880 | +66,9 |

Lettura netta, e coerente con tutto lo studio:

1. **Le celle con l'order block reggono il passaggio fuori campione** e anzi
   migliorano (+0,59 in ricerca, +1,17 fuori). E' la conferma indipendente
   dell'appendice P, ora su un campione e un periodo diversi.
2. **L'unica cella con Fibonacci fra le prime dieci e' anche l'unica che
   CROLLA** (+0,359 in ricerca, -0,092 fuori). Terza falsificazione dopo il
   placebo dell'appendice O e la scrematura AB.
3. **Il profilo volume da solo non compare mai**; in coppia con l'OB il
   terzile alto sembra aggiungere (+1,168 contro +0,916 senza), ma su 46
   operazioni la differenza non e' distinguibile: resta un indizio.

### Verifica di causalita' (dubbio sollevato dall'utente)

Il motore e' a scorrimento: swing noti k barre DOPO l'estremo, zone attive
dalla chiusura della candela che rompe, ingresso su candele chiuse, uscita
risolta minuto per minuto con lo stop che prevale sull'obiettivo. Per
escludere una fuga di informazione sottile, la cella migliore e' stata
ricalcolata pretendendo le zone note con 33 e 66 minuti di RITARDO:

| ritardo imposto | n in zona | R/op ricerca | R/op fuori campione |
|---|---|---|---|
| nessuno | 160 | +0,589 | +1,168 |
| una candela M33 (33') | 157 | +0,592 | +1,168 |
| due candele M33 (66') | 151 | +0,649 | +0,962 |

Il risultato non dipende dal sapere le cose in anticipo: ritardando
l'informazione resta identico. Se ci fosse lookahead, crollerebbe.

**Conclusione**: la ricerca libera su tre famiglie di livelli riporta allo
stesso posto di sempre — l'order block come filtro funziona, Fibonacci no, il
volume al massimo accompagna. Nessuna adozione: 46-51 operazioni fuori
campione sono poche, e la strada corretta e' verificarlo in avanti.

## Appendice AJ: backtest completo 7 anni, zona piena contro zona raffinata

Richiesta dell'utente: backtest completo sui sette anni di OB pieno piu' OB
raffinato. Margine 0,5 x rischio, obiettivo 1:10, pareggio +3R, spread 0,30.

### Sulla regola ufficiale (348 operazioni)

| sottoinsieme | n | R tot | R/op | utile | stop | TP | DD | anni+ | PF |
|---|---|---|---|---|---|---|---|---|---|
| tutte | 348 | +171,1 | +0,492 | 35% | 54% | 3,2% | 16,3% | **7/7** | 1,81 |
| in zona piena | 69 | +54,8 | +0,795 | 45% | 43% | 4,3% | 8,0% | 5/7 | 2,63 |
| **in zona raffinata** | 29 | +36,4 | **+1,256** | 52% | 38% | **10,3%** | **4,3%** | 5/7 | **4,07** |
| piena ma NON raffinata | 40 | +18,4 | +0,461 | 40% | 48% | **0,0%** | 7,1% | 4/7 | 1,85 |

### Sul campione largo (1.344 operazioni)

| sottoinsieme | n | R tot | R/op | utile | stop | TP | DD | anni+ | PF |
|---|---|---|---|---|---|---|---|---|---|
| tutte | 1344 | +205,2 | +0,153 | 29% | 59% | 2,2% | 41,9% | 5/7 | 1,23 |
| in zona piena | 160 | +102,4 | +0,640 | 41% | 49% | 3,8% | 11,6% | 6/7 | 2,17 |
| **in zona raffinata** | 63 | +84,5 | **+1,342** | 56% | 35% | **9,5%** | **3,3%** | **7/7** | **4,50** |
| piena ma NON raffinata | 97 | +17,9 | +0,184 | 32% | 58% | **0,0%** | 16,9% | 4/7 | 1,28 |

### Il risultato che conta: e' la RAFFINATA a fare tutto

Separando le due parti della zona piena si vede che il vantaggio dell'order
block sta INTERAMENTE nella parte raffinata (la definizione dell'utente):

- campione largo: raffinata +1,342 R/op su 63 operazioni, il resto della zona
  piena +0,184 su 97 — praticamente il campione senza filtro.
- **zero TP pieni** fuori dalla zona raffinata, in entrambi i campioni: le
  corse fino a 1:10 avvengono solo dentro la zona stretta.
- la raffinata sul campione largo e' l'unico sottoinsieme con 7 anni positivi
  su 7, drawdown 3,3% e fattore di profitto 4,50.

Limite serio e dichiarato: 29 e 63 operazioni sono poche, circa 4-9 all'anno.
Come filtro DURO la raffinata butta il 92% del campione e chiude a +36,4 R
contro +171,1: non e' una strategia sostitutiva. Il suo posto e' altrove —
sovrappeso di rischio (appendice X: +26,7% a pari drawdown, p 0,06) e
selezione delle occasioni migliori nell'operativita' manuale.

## Appendice AK: si puo' arrivare a 100 operazioni l'anno?

Richiesta dell'utente: una configurazione con 100-120 operazioni l'anno che
porti allo stesso risultato. Scala di frequenza costruita allentando le
conferme sul campione largo (macro sempre attivo), obiettivi 5/8/10,
pareggio +3R. Confronto a PARITA' DI DRAWDOWN (16,3%, bisezione sul rischio):
e' l'unico modo onesto di confrontare configurazioni che oscillano di piu'.

| conferme | M12 | rr | n | op/anno | R tot | R/op | anni+ | DD a 1% | conto a 1% | **conto a pari DD** |
|---|---|---|---|---|---|---|---|---|---|---|
| **M33+H12 (in vigore)** | pullback | 10 | 348 | **53** | +171,1 | **+0,492** | **7/7** | **16,3%** | 49.321 | **49.321** |
| M33+H12+M66 | pullback | 10 | 320 | 49 | +149,8 | +0,468 | 7/7 | 16,3% | 40.292 | 40.336 |
| M33 | pullback | 10 | 388 | 60 | +169,4 | +0,437 | 7/7 | 18,8% | 47.971 | 38.682 |
| M33+H12 | — | 10 | 627 | **96** | **+238,3** | +0,380 | 7/7 | **26,7%** | **88.313** | 36.823 |
| H12 | pullback | 10 | 628 | 96 | +164,4 | +0,262 | 6/7 | 18,7% | 44.242 | 36.768 |
| nessuna | pullback | 10 | 730 | **112** | +171,8 | +0,235 | 6/7 | 19,9% | 46.267 | 35.522 |
| M33 | — | 10 | 698 | 107 | +236,7 | +0,339 | 6/7 | 28,5% | 85.406 | 33.143 |

Si arriva a 96-112 operazioni l'anno, e in R si fa anche molto di piu': la
riga M33+H12 senza il vincolo di pullback fa **+238,3 R e 88.313 EUR a
rischio 1%**, con 7 anni positivi. Ma il drawdown sale al **26,7%**, e a
parita' di dolore il conto scende a 36.823: **il 25% in meno del base**.

E' la legge della frequenza gia' vista tre volte (appendici M, S, W), qui
misurata sulla scala completa: ogni allentamento porta operazioni con meno
vantaggio per operazione (da +0,492 a +0,235), quindi per fare lo stesso
risultato serve piu' rischio, e il drawdown cresce piu' in fretta del
guadagno. **Nessuna delle 18 configurazioni da 90-140 op/anno batte la
taratura a parita' di drawdown.**

Nota per chi cerca volume di operazioni: la riga M33+H12 senza pullback e'
comunque la migliore di quella fascia, ed e' l'unica con 7/7 anni. Se un
giorno servisse frequenza (per un conto prop con obiettivi di attivita'),
quella e' la candidata — al prezzo dichiarato di un quarto del rendimento a
parita' di rischio.

## Appendice AL: scale di trailing x obiettivi 1:5-1:12

Richiesta dell'utente: verificare gli obiettivi fini da 1:5 a 1:9 e provare
vere SCALE di trailing (a +3R stop a pari, a +5R stop a +2R, ecc.), che
finora non erano mai state misurate — il pareggio era sempre stato provato
come soglia unica.

84 celle: 12 gestioni x 7 obiettivi, sulle 348 operazioni ufficiali, spread
0,30. Convenzione conservativa: dentro il minuto lo stop prevale
sull'obiettivo, e la scala si aggiorna DOPO il controllo dello stop.

### Conto a parita' di drawdown (16,3%), euro da 10.000

| gestione | 1:5 | 1:6 | 1:7 | 1:8 | 1:9 | **1:10** | 1:12 |
|---|---|---|---|---|---|---|---|
| **pari a +3R (in uso)** | 32.962 | 36.399 | 36.931 | 41.022 | 45.742 | **49.321** | 46.918 |
| pari a +2R | — | — | — | — | 45.559 | 48.545 | 46.266 |
| scala 3>0 5>2 | 32.962 | 34.562 | 34.877 | 38.381 | 42.404 | 45.305 | 43.704 |
| scala 3>0 5>2 7>4 | 32.962 | 34.562 | 34.877 | 37.552 | 39.583 | 38.764 | 37.338 |
| scala 2>0 4>2 6>4 | 29.169 | 32.486 | 34.478 | 36.288 | 37.311 | 37.631 | 35.088 |
| scala 5>0 8>4 | 28.518 | 31.491 | 31.952 | 35.492 | 37.759 | 37.318 | 35.446 |
| stop fisso | 28.518 | 31.430 | 31.571 | 35.068 | 39.103 | 42.162 | 40.108 |
| trail MFE-2 da +3R | 30.445 | 30.614 | 30.374 | 31.783 | 31.538 | 31.689 | 31.520 |
| trail MFE-3 da +4R | 29.891 | 30.713 | 31.317 | 33.342 | 35.149 | 35.437 | 32.200 |
| trail MFE-4 da +6R | 28.518 | 31.430 | 31.149 | 33.616 | 35.757 | 36.028 | 32.524 |

### Tre risultati

**1. Nessuna scala batte la soglia singola.** La configurazione in uso
(pareggio a +3R, nessun gradino successivo) e' la migliore di tutte e 84 le
celle, sia in R (+171,1) sia in euro a parita' di drawdown. Aggiungere il
secondo gradino (3>0 poi 5>2) costa **-9,1 R**; aggiungerne un terzo (7>4)
costa **-25,7 R**. Ogni gradino in piu' toglie, e toglie in modo monotono.

**2. Il trailing continuo e' il peggiore in assoluto.** Stop sempre a MFE-2:
+122,5 R contro +171,1, cioe' **-28%**, ed e' l'unica gestione che non migliora
alzando l'obiettivo (resta piatta a ~31.000 EUR da 1:5 a 1:12). Il motivo e'
quello di sempre: il trailing stretto taglia proprio le corse lunghe, che
sono il 69% del risultato. Piu' e' lasco (MFE-4) meno danneggia, e al limite
coincide con il non farlo.

**3. Fra 1:5 e 1:9 non c'e' niente di nascosto.** La colonna cresce in modo
regolare fino a 1:10 e poi cala a 1:12: 32.962 → 36.399 → 36.931 → 41.022 →
45.742 → **49.321** → 46.918. Nessun massimo intermedio, nessuna sorpresa
fra 1:5 e 1:9: l'ottimo e' 1:10 e la curva e' liscia.

**Conclusione**: taratura invariata. La domanda "il trailing migliora?" ha
risposta netta e negativa su 84 celle — e ora e' agli atti invece di essere
un'ipotesi mai verificata. Dati in `scale-trailing.parquet`.

## Appendice AM: stabilita' a lotti fissi (la costante di profitto)

Osservazione dell'utente: le tabelle mostrano quanto si guadagna, non quanto
si e' stabili, e il conto in euro col rischio percentuale confonde il
vantaggio con l'effetto della composizione. Rifatto tutto a **lotti fissi**:
10.000 EUR di conto, **100 EUR rischiati a ogni operazione, sempre**. Cosi'
ogni operazione pesa uguale e resta solo il vantaggio.

### La configurazione in uso, a lotti fissi

| | |
|---|---|
| risultato | +171,1 R = **27.111 EUR** (da 10.000, in 6 anni e mezzo) |
| costante annua | ~+26 R, cioe' **+2.600 EUR all'anno** a rischio 100 EUR |
| operazioni in perdita | 64,7% |
| perdite di fila (massimo) | 13 |
| perdita massima | **17,6 R** (1.762 EUR) |
| tempo sotto il massimo precedente | 33 operazioni |
| recupero (risultato / perdita massima) | **9,71** |
| mesi positivi | 50,7% |
| anni positivi | 7/7, il peggiore **+6,9 R** |
| fattore di profitto | 1,81 |

### Il confronto sulle misure di stabilita', non sul profitto

Nessuna delle 84 celle batte quella in uso su **tutte** le misure insieme.
Nel dettaglio:

- **65 celle hanno meno operazioni in perdita**, ma **nessuna di queste rende
  di piu'**. Il caso limite e' il trailing continuo MFE-2: perse 57,8% contro
  64,7% — sette punti in meno, esattamente quello che si cerca guardando le
  perdite — ma rende 122,5 R contro 171,1, cioe' **22.246 EUR contro 27.111**,
  e il rapporto recupero scende da 9,71 a 6,95. Meno perdite, meno soldi,
  meno robustezza.
- **Una sola cella ha un recupero migliore**: pareggio a +2R con 1:10, e per
  un soffio (9,720 contro 9,708). Ma paga con 49 operazioni sotto il massimo
  invece di 33 (cioe' quasi il doppio del tempo passato sott'acqua), con
  l'anno peggiore a +2,4 R invece di +6,9 e con meno mesi positivi (45,1%
  contro 50,7%). Un pareggio numerico che nella pratica e' peggiore.
- **Zero celle hanno un anno peggiore migliore** di +6,9 R.

### Cosa dice davvero questa tabella

La "costante di profitto" della strategia, ripulita dalla composizione, e'
**+26 R all'anno con una perdita massima di 17,6 R**: si guadagna circa una
volta e mezza il proprio peggior periodo, ogni anno. Il rapporto di recupero
9,71 su sette anni e' il numero piu' onesto che questo lavoro produce.

E la lezione ripetuta per l'ennesima volta, ora anche sulle misure di
stabilita': **la percentuale di operazioni in perdita non e' una leva da
migliorare**. Si puo' comprare (65 celle lo fanno) ma il prezzo e' sempre lo
stesso — meno risultato e meno robustezza. Dati in `stabilita.parquet`.

## Appendice AN: scrematura delle 84 gestioni, e dove cadono le serie

### Le celle che sopravvivono al confronto

Delle 84 combinazioni, **10 non sono dominate** da nessun'altra (cioe' non
esiste una cella che le batta insieme su risultato, drawdown in R, quota di
vinte, tempo sotto il massimo e anni positivi). Le altre 74 si possono
scartare senza pensarci: c'e' sempre qualcosa di meglio sotto ogni aspetto.

| gestione | rr | R tot | % vinte | DD R | sotto max | mesi+ | anni+ | peggiore | PF |
|---|---|---|---|---|---|---|---|---|---|
| **pari a +3R (in uso)** | 10 | **171,1** | 35,3 | 17,6 | 33 | 36 | 7 | **+6,9** | **1,81** |
| scala 3>0 5>2 | 10 | 162,0 | 36,2 | 17,6 | 33 | 35 | 7 | +0,8 | 1,77 |
| stop fisso | 10 | 155,6 | 36,5 | 17,6 | 33 | 35 | 7 | +4,8 | 1,68 |
| pari a +2R | 10 | 151,9 | 32,5 | **15,6** | 49 | 32 | 7 | +2,4 | 1,78 |
| scala 4>1 7>4 | 9 | 148,4 | 38,5 | 17,6 | 33 | 35 | 7 | +3,7 | 1,66 |
| trail MFE-2 da +3R | 8 | 122,7 | **42,2** | 17,6 | 45 | **37** | 7 | +1,2 | 1,59 |

(le altre quattro sono varianti peggiori delle stesse famiglie)

Solo tre scelte hanno senso: **massimo risultato** (quella in uso), **minimo
drawdown** (pari a +2R: 15,6 R contro 17,6, ma 49 operazioni sott'acqua invece
di 33 e 19 R in meno), **massima quota di vinte** (trailing MFE-2: 42,2%, al
prezzo di 48 R). Nessuna combinazione dà due cose insieme.

### Le serie sono un fatto del mercato, non della gestione

Osservazione dell'utente: le serie di vittorie e sconfitte sono identiche in
quasi tutte le celle. E' vero, e il motivo e' che **la gestione cambia quanto
rende un'operazione, non se e' vinta o persa**: rispetto alla configurazione
in uso, lo stop fisso cambia segno a 4 operazioni su 348, la scala a 16, il
trailing continuo a 24. Il resto e' identico.

Dove cadono, sulla configurazione in uso:

| serie | quando | durata | esito |
|---|---|---|---|
| **13 perdite di fila** | 24/02/2026 → 09/06/2026 | 105 giorni | -13,3 R |
| 6 vittorie di fila | 14/04/2020 → 29/06/2020 | 76 giorni | +7,9 R |

L'intuizione dell'utente e' corretta: la serie nera **e' esattamente il
drawdown massimo**. La curva era a +164,1 R (massimo +168,4), scende a
+150,8 R: sono i 17,6 R di perdita massima, e il periodo va dal 20/10/2025 al
09/06/2026, 27 operazioni in tutto.

Due cose che questo dice, e che valgono piu' di qualunque ottimizzazione:

1. **La peggiore attraversata dei sette anni e' l'ultima**, ancora in corso a
   fine campione. Non e' un guasto della strategia: e' il tipo di periodo che
   capita, e chi comincia adesso potrebbe partire proprio da li'.
2. **Tre mesi e mezzo con 13 perdite di fila sono nel copione.** Nessuna delle
   84 gestioni le riduce: il massimo di perdite consecutive e' 13 in TUTTE le
   celle. Si puo' cambiare quanto costano, non quante sono.

## Appendice AO: le otto gestioni senza la chiusura di fine giornata

Domanda dell'utente: se il conto non ha il vincolo prop sull'overnight, cosa
succede alle otto gestioni sopravvissute alla scrematura? Tre regimi: chiusura
alle 21 (in vigore), chiusura al venerdi' sera, nessuna chiusura per tempo
(tetto 30 giorni). Lotti fissi, 100 EUR per operazione.

| gestione | rr | giornaliera | settimanale | aperta | DD R (gio→apert) | anni+ |
|---|---|---|---|---|---|---|
| pari a +3R (in uso) | 10 | +171,1 | +182,4 | **+224,1** | 17,6 → **24,0** | 7 → **6** |
| pari a +3R | 9 | +162,8 | +187,3 | **+231,1** | 17,6 → 25,7 | 7 → 7 |
| **pari a +3R** | **8** | +151,0 | **+191,8** | +218,1 | 17,6 → **14,3** (sett.) | 7 → 7 |
| scala 3>0 5>2 | 10 | +162,0 | +142,4 | +184,1 | 17,6 → 20,7 | 7 → 6 |
| stop fisso | 10 | +155,6 | +172,9 | +221,1 | 17,6 → **38,6** | 7 → 6 |
| pari a +2R | 10 | +151,9 | +167,1 | +193,1 | 15,6 → 19,6 | 7 → 6 |
| **scala 4>1 7>4** | **9** | +148,4 | +176,4 | +178,1 | 17,6 → **16,5** | 7 → **7** |
| **trail MFE-2** | **8** | +122,7 | +161,4 | +172,3 | 17,6 → **14,3** | 7 → **7** |

### Il ribaltamento: senza chiusura serale servono gestioni diverse

Tenendo aperto, **le gestioni cambiano di ruolo**. Con la chiusura serale il
trailing era il peggiore di tutti (+122,7, ultimo su otto); senza chiusura
diventa una delle migliori scelte: +172,3 R con il **drawdown piu' basso in
assoluto (14,3 R contro i 24,0 della configurazione in uso)**, 37 mesi
positivi su 71 e 7 anni su 7. Il motivo e' evidente: quando la posizione puo'
restare aperta giorni, qualcuno deve proteggere il guadagno — di notte non c'e'
piu' la campanella a farlo.

Specularmente, il pareggio a +3R con 1:10 e' quello che guadagna di piu' in
assoluto senza chiusura (+224,1), ma il conto e' salato: drawdown da 17,6 a
**24,0 R**, la quota di operazioni vinte crolla dal 35,3% al **13,5%**, le
perdite di fila passano da 13 a **28**, e si perde un anno positivo. Lo stop
fisso e' il caso estremo: +221 R con **38,6 R di drawdown**, piu' del doppio.

### Le due combinazioni che migliorano su tutto

Solo due celle stanno meglio senza chiusura serale **senza pagare in rischio**:

- **pari a +3R con obiettivo 1:8, chiusura settimanale**: +191,8 R (contro
  151,0), drawdown **14,3 R invece di 17,6**, perdite di fila 15, 7 anni su 7,
  anno peggiore +11,4 R — il migliore di tutta la tabella.
- **trailing MFE-2 con 1:8, tenuta aperta**: +172,3 R (contro 122,7),
  drawdown 14,3, 34 operazioni sott'acqua, 37 mesi positivi.

Avvertenza obbligatoria, la stessa dell'appendice AH: **swap, gap del fine
settimana e posizioni sovrapposte non sono modellati**, e penalizzano solo i
regimi lunghi. Il 24% delle operazioni resterebbe aperto oltre sera, con fino
a 4 posizioni contemporanee: a rischio 1% ciascuna sono il 4% esposto in un
istante. Prima di adottare uno di questi due profili serve misurare lo swap
reale del broker e mettere un tetto alle posizioni contemporanee.

## Appendice AP: scheda completa delle due candidate senza chiusura serale

Tutto quello che serve per decidere fra le due combinazioni emerse
nell'appendice AO e quella in vigore. Lotti fissi, 100 EUR per operazione,
spread 0,30.

| | **A** pari +3R, 1:8, venerdi' | **B** trail MFE-2, 1:8, aperta | in uso: pari +3R, 1:10, sera |
|---|---|---|---|
| operazioni | 348 | 348 | 348 |
| **risultato** | **+191,8 R** (29.182 EUR) | +172,3 R (27.234) | +171,1 R (27.111) |
| per operazione | +0,55 | +0,50 | +0,49 |
| **vinte** | **81 (23,3%)** | 127 (36,5%) | 123 (35,3%) |
| media vinta / persa | **+5,27** / -0,88 | +3,22 / -1,07 | +3,11 / -0,94 |
| fattore di profitto | **1,82** | 1,73 | 1,81 |
| vittorie / perdite di fila | 3 / **15** | **7** / 14 | 6 / 13 |
| **perdita massima** | **14,3 R** | **14,3 R** | 17,6 R |
| operazioni sotto il massimo | **59** | 34 | 33 |
| mesi positivi | 32/71 | **37/71** | 36/71 |
| anni positivi | **7/7** | **7/7** | **7/7** |
| **anno peggiore** | **+11,5 R** | +10,4 R | +6,9 R |

### Come esce, ciascuna

| uscita | A | B | in uso |
|---|---|---|---|
| stop pieno | 214 | 221 | 189 |
| obiettivo | **36** | 17 | 11 |
| pareggio | 50 | 0 | 24 |
| stop in utile | 0 | **110** | 0 |
| scadenza (venerdi'/sera) | 48 | 0 | 124 |

Sono due meccanismi opposti. **A vince poco e grosso**: solo 81 operazioni in
utile su 348, ma la vincita media e' +5,27 R (contro +3,11) perche' le lascia
correre tutta la settimana. **B vince spesso e medio**: 127 operazioni in
utile, di cui 110 chiuse dal trailing a un livello gia' in guadagno — e' il
trailing a fare tutto il lavoro.

### I costi non modellati, misurati

| | A | B | in uso |
|---|---|---|---|
| durata mediana | 3,0 ore | 2,5 ore | 2,7 ore |
| durata media | 10,9 ore | 10,4 ore | 4,2 ore |
| operazione piu' lunga | 4,3 giorni | 5,8 giorni | 14 ore |
| operazioni oltre la notte | 25,0% | 24,1% | **0%** |
| **notti totali da pagare** | **128** | **141** | **0** |
| **fine settimana attraversati** | **0** | **22** | **0** |
| posizioni contemporanee (max) | **4** | 3 | 3 |

Numeri concreti per il conto: A paga **128 notti di swap** in sette anni, B ne
paga 141 e attraversa **22 fine settimana** col rischio di gap sopra lo stop.
Con uno swap tipico di 1-3 EUR per notte su 0,10 lotti, sono 130-400 EUR su
sette anni: poco rispetto ai ~9.000 EUR di differenza, ma va verificato sul
listino vero di FP, perche' su XAUUSD lo swap short e long non sono simmetrici
e in certi periodi sono molto piu' alti.

### Risultato per anno (R)

| anno | A | B | in uso |
|---|---|---|---|
| 2020 | +17,4 | **+27,0** | +6,9 |
| 2021 | +14,2 | +10,4 | +9,8 |
| 2022 | +34,2 | +28,3 | +37,2 |
| 2023 | +27,5 | +17,5 | +27,7 |
| 2024 | +26,4 | +20,6 | +38,4 |
| 2025 | **+60,7** | +55,2 | +44,1 |
| 2026 | +11,5 | +13,3 | +7,0 |

### Cosa manca prima di adottarle

1. **Swap reale di FP** su XAUUSD, long e short, e ricalcolo con quel costo.
2. **Gap del fine settimana**: il modello assume il fill esatto allo stop, che
   in un gap non avviene. Riguarda solo B (22 weekend).
3. **Tetto alle posizioni contemporanee**: A arriva a 4 aperte insieme, cioe'
   il 4% esposto a rischio 1% ciascuna. Va messo un limite esplicito.
4. **Verifica fuori campione**: queste due sono state scelte guardando gli
   stessi sette anni, quindi vale l'avvertenza di sempre — sono candidate,
   non adottate.

## Appendice AQ: lo swap reale di FP ribalta le candidate overnight

Specifiche del simbolo XAUUSD sul conto FP, lette dall'utente il 03/08/2026:
swap **in punti**, long **-71,5**, short **+32,5**, lotto 100 once,
coefficiente **x3 il mercoledi'**. Su XAUUSD un punto vale 0,01 $ di prezzo,
che su 100 once fa **1 $ per lotto**: una notte di long costa **71,50 $ per
lotto**, una di short ne rende 32,50.

Tradotto in multipli del rischio (swap_R = punti / (100 x stop in $)), con lo
stop mediano di 4,72 $: **una notte di long costa 0,151 R**, cioe' il 15% del
rischio dell'operazione. Il rollover cade alle 00:00 del server (UTC+3) = le
21:00 UTC, esattamente l'ora della chiusura di fine giornata: **chi chiude alle
21 non paga swap, mai**.

| configurazione | lordo | swap | **netto** | notti pesate | vinte | DD | anni+ | peggiore |
|---|---|---|---|---|---|---|---|---|
| **in uso: pari +3R 1:10, sera** | +171,1 | **0,0** | **+171,1** | 0 | 35,3% | 17,6 | 7/7 | +6,9 |
| A: pari +3R 1:8, venerdi' | +191,8 | **-13,4** | +178,4 | 230 | 25,6% | **14,3** | 7/7 | **+11,3** |
| B: trail MFE-2 1:8, aperta | +172,3 | -9,3 | +163,0 | 189 | 36,5% | **14,3** | 7/7 | +10,1 |
| B': trail MFE-2 1:8, venerdi' | +161,4 | -6,8 | +154,6 | 139 | 37,6% | **14,3** | 7/7 | **+12,8** |

### Cosa cambia

Lo swap **mangia da 7 a 13 R** e riordina la classifica:

- **B, la candidata che sembrava migliore, scende sotto la configurazione in
  vigore**: +163,0 contro +171,1. Il vantaggio apparente era swap non pagato.
- **B' (chiusura al venerdi', come chiesto dall'utente) e' ancora peggio**:
  +154,6 R. Chiudere il venerdi' evita i gap del fine settimana ma taglia
  anche le corse lunghe, e le notti restano comunque 139.
- **A resta sopra**: +178,4 contro +171,1, cioe' **+7,3 R in sette anni** —
  circa 730 EUR a lotti fissi, l'1% l'anno. In cambio di 230 notti di
  esposizione, gap non modellati e una quota di vinte che scende al 25,6%.

Da notare: il 69% delle operazioni e' long, cioe' proprio il lato che paga.
Se la strategia fosse prevalentemente short lo swap sarebbe un ricavo (+32,5
punti a notte) e la conclusione si rovescerebbe.

### Conclusione

**La chiusura alle 21 UTC non e' un vincolo da subire: e' gratis e vale
quanto tenere aperto.** Il piccolo vantaggio residuo di A (+4%) non ripaga
gap del weekend, fino a 4 posizioni contemporanee e 15 perdite di fila. La
taratura resta quella in vigore, e adesso lo si sa con il listino vero in
mano invece che con una stima.

### Le stesse tre, a rischio percentuale invece che a lotti fissi

Con reinvestimento (1% e 0,5% del capitale corrente, da 10.000 EUR), swap
reale gia' sottratto:

| | in uso 1:10 sera | A: pari +3R 1:8 venerdi' | B: trail 1:8 venerdi' |
|---|---|---|---|
| **conto all'1%** | 49.321 | **51.524** | 42.707 |
| rendimento | +393% | **+415%** | +327% |
| **perdita max** | 16% (7.901 EUR) | 13% (6.480) | **13% (5.371)** |
| conto allo 0,5% | 22.844 | **23.516** | 21.151 |
| perdita max allo 0,5% | 8% (1.914 EUR) | 7% (1.575) | **7% (1.417)** |
| mesi positivi | 36/71 | 31/71 | 36/71 |
| anno peggiore | +646 EUR | +1.267 | **+1.445** |

Per anno, a rischio 1% (euro):

| anno | in uso | A | B |
|---|---|---|---|
| 2020 | 646 | 1.544 | **2.083** |
| 2021 | 920 | 1.267 | **1.445** |
| 2022 | 4.971 | 4.851 | **5.206** |
| 2023 | **4.857** | 4.866 | 2.977 |
| 2024 | **9.251** | 5.374 | 3.363 |
| 2025 | 15.797 | **18.749** | 12.845 |
| 2026 | 2.878 | **4.873** | 4.788 |

Il quadro con la composizione e' lo stesso dei lotti fissi, con due sfumature
che contano:

- **A vince di 2.200 EUR su 6 anni e mezzo (+4,5%) e con drawdown minore**
  (13% contro 16%): a parita' di rischio percentuale e' la sola configurazione
  che migliora davvero, non solo in R.
- **B resta sotto** (42.707 contro 49.321) ma ha la perdita massima piu' bassa
  in assoluto (5.371 EUR contro 7.901) e l'anno peggiore piu' alto: e' il
  profilo piu' tranquillo, pagato con un quinto del rendimento.

Resta il motivo per cui nessuna delle due viene adottata: 230 e 139 notti di
esposizione a mercato non sorvegliato, fino a 4 posizioni contemporanee, e
soprattutto la scelta fatta guardando gli stessi sette anni. Il vantaggio di A
(+4,5%) e' dentro il margine di rumore di una selezione fra 84 celle.

## Appendice AR: vale la pena attraversare il fine settimana?

Domanda dell'utente su B: meglio farla correre anche nel weekend o chiudere il
venerdi'? Nel modello **correre rende di piu'**: +163,0 R contro +154,6, cioe'
chiudere il venerdi' costa 8,4 R. Ma quel guadagno sta esattamente dove il
modello e' cieco: i salti del lunedi'.

Misurati sui 340 fine settimana dello storico 2020-2026 (differenza fra
chiusura del venerdi' e apertura successiva, in valore assoluto):

| | dollari | in R con stop 4,72 $ |
|---|---|---|
| mediana | 1,31 | 0,28 |
| p75 | 3,52 | 0,75 |
| p90 | 13,15 | 2,79 |
| p95 | 19,59 | **4,15** |
| p99 | 59,22 | 12,55 |
| **massimo** | **111,94** | **23,72** |

Il 21% dei fine settimana apre oltre 1 R di distanza, il 12% oltre 2 R.

### Il conto

B attraversa 22 fine settimana in sette anni e ne ricava **+8,4 R, cioe'
+0,38 R per weekend**. Contro: quando il salto supera lo stop nella direzione
sbagliata, l'operazione non esce a -1 R ma alla riapertura, e i gap oltre 1 R
valgono in media **3,96 R**. Con 22 attraversamenti e il 21% di gap oltre 1 R,
l'attesa e' di circa 4-5 episodi: se anche solo uno o due cadono dalla parte
sbagliata di una posizione aperta, il guadagno di 8,4 R e' bruciato.

E c'e' l'asimmetria che conta di piu': il modello **conta i gap favorevoli**
(il prezzo salta verso l'obiettivo e l'operazione chiude meglio) ma **non
penalizza quelli contrari** oltre lo stop, perche' assume il fill esatto al
livello. Quindi i +8,4 R sono gonfiati proprio dal meccanismo che li rende
inaffidabili.

**Risposta: chiudere il venerdi'.** Si rinuncia a un guadagno modellato di
8,4 R (5%) per togliere una coda che nel caso peggiore osservato vale 23,7 R
su una singola operazione — piu' del drawdown massimo di tutta la strategia.
Vale comunque solo come nota di metodo: B in entrambe le versioni resta sotto
la configurazione in vigore.

## Appendice AS: i gap contrari, contati davvero

Difetto del motore segnalato dall'utente: quando il prezzo riapre OLTRE lo
stop, l'uscita non avviene al livello ma al prezzo di riapertura. Il modello
assumeva il riempimento esatto, quindi incassava i gap favorevoli senza pagare
quelli contrari. Corretto: ora si guarda l'APERTURA di ogni minuto — se apre
oltre lo stop si esce li', se apre oltre l'obiettivo si incassa li'.

### Il risultato non cambia, ma per un pelo

| configurazione | netto con gap pagati | gap contrari pagati |
|---|---|---|
| in uso 1:10 sera | +171,1 R | **0,0** (non attraversa mai una riapertura) |
| A pari +3R 1:8 venerdi' | +178,4 R | **0,0** (chiude prima del weekend) |
| B trail 1:8 venerdi' | +154,6 R | **0,0** |
| B trail 1:8 aperta | +163,0 R | **0,0** su 23 attraversamenti |

Zero non e' un errore: **solo 23 operazioni su 348 restano vive attraverso una
chiusura del mercato**, e in quelle 23 il lunedi' ha riaperto sempre sopra lo
stop (da +0,66 a +2,65 R). Ma e' fortuna, non robustezza.

### Quanto vale quella fortuna

Simulazione: agli stessi 23 attraversamenti si assegnano salti pescati a caso
dalla distribuzione reale dei 340 fine settimana dello storico (con segno),
20.000 storie alternative. Il margine mediano fra prezzo e stop al venerdi'
sera e' 1,58 R, il minimo 0,20 R.

| costo dei gap contrari | R |
|---|---|
| mediana | 2,6 |
| media | **5,4** |
| p90 | 14,5 |
| p99 | 32,2 |
| massimo osservato in simulazione | 74,9 |
| storie a costo zero | **14%** |
| **storie che bruciano gli 8,4 R di vantaggio** | **22%** |

La storia reale che abbiamo (costo zero) e' fra il 14% piu' fortunato. In una
storia media il costo sarebbe 5,4 R, cioe' i due terzi del vantaggio di
tenere aperto; una volta su cinque lo brucia del tutto, e nella coda peggiore
si perde piu' del drawdown massimo dell'intera strategia.

**Conclusione**: il vantaggio di attraversare il fine settimana (+8,4 R) e'
piu' piccolo della sua stessa incertezza (5,4 R di costo atteso, 32 R al
percentile 99). Confermata la scelta di chiudere il venerdi', e confermato
che la configurazione in vigore — che non attraversa neanche la notte — non
ha affatto questa esposizione.

## Appendice AT: filtro sul fine settimana e stop alla chiusura del venerdi'

Due proposte dell'utente per rendere sostenibile il tenere aperto: attraversare
il fine settimana solo se gia' sopra una soglia (+3R o +5R), e portare lo stop
al prezzo di chiusura del venerdi' per congelare il guadagno. Motore completo:
gap pagati al prezzo di riapertura, swap reale di FP.

| variante | netto | swap | vinte | uscite per gap | chiuse dal filtro |
|---|---|---|---|---|---|
| **sempre aperta** | **+163,0** | -9,3 | 36,5% | 0 | — |
| weekend solo sopra +3R | +158,5 | -8,7 | **37,9%** | **0** | 16 |
| weekend solo sopra +5R | +157,2 | -7,6 | **37,9%** | **0** | 22 |
| chiude sempre il venerdi' | +154,6 | -6,8 | 37,6% | 0 | — |
| +5R e stop a chiusura | +156,0 | -7,6 | 37,9% | 1 | 22 |
| +3R e stop a chiusura | +153,7 | -8,7 | 37,9% | **5** | 16 |
| stop a chiusura, senza filtro | +152,5 | -9,0 | 37,9% | **10** | — |

### Il filtro funziona come sperato, ma costa

Le due varianti con filtro fanno esattamente il loro mestiere: **zero uscite
per gap** e la quota di operazioni vinte sale al 37,9% (contro 36,5%). Il
prezzo e' 4,5-5,8 R rispetto al tenere sempre aperto — meno di quanto costava
chiudere sempre il venerdi' (8,4 R). Quindi il filtro **e' meglio di entrambe
le regole secche**: prende meta' del vantaggio del tenere aperto e ne toglie
quasi tutta l'esposizione.

### Lo stop portato alla chiusura fa il contrario di quello che si spera

L'idea era proteggere il guadagno; il risultato e' che **crea gli stop che
voleva evitare**. Senza filtro le uscite per gap passano da 0 a **10**, e il
netto scende da +163,0 a +152,5 — la peggiore di tutte le varianti. Il motivo
e' aritmetico: portando lo stop al prezzo del venerdi' si azzera il margine,
e a quel punto **qualunque riapertura anche solo di pochi centesimi sotto
chiude l'operazione**. Il margine mediano fra prezzo e stop era 1,58 R e
serviva proprio ad assorbire il salto.

Aggiunto al filtro il danno si riduce (5 uscite per gap con +3R, una sola con
+5R) ma resta un peggioramento: -4,8 e -1,2 R rispetto al solo filtro.

### Conclusione

Il filtro sopra +3R e' la versione migliore del tenere aperto: +158,5 R con
zero uscite per gap. Ma resta sotto la configurazione in vigore (+171,1 R con
zero notti, zero swap e zero esposizione) — quindi non cambia la conclusione,
migliora solo la comprensione: **se un giorno servisse tenere aperto, si tiene
solo quando si e' gia' avanti, e lo stop NON si porta alla chiusura**.

### Stop a PAREGGIO prima del fine settimana (precisazione dell'utente)

L'idea non era portare lo stop al prezzo del venerdi' ma **al prezzo
d'ingresso**: si garantisce di non perdere e si lascia intatto il margine che
serve ad assorbire il salto. E' una regola diversa, e infatti va molto meglio.

| variante | netto | vinte | uscite per gap | chiuse dal filtro |
|---|---|---|---|---|
| sempre aperta (riferimento) | +163,0 | 36,5% | 0 | — |
| **stop a pareggio nel weekend** | **+161,2** | 37,1% | 3 | — |
| **pareggio + solo sopra +1R** | **+160,8** | 37,4% | **0** | 11 |
| pareggio + solo sopra +3R | +158,5 | 37,9% | 0 | 16 |
| pareggio + solo sopra +5R | +157,2 | 37,9% | 0 | 22 |
| chiude sempre il venerdi' | +154,6 | 37,6% | 0 | — |
| stop alla chiusura del venerdi' | +152,5 | 37,9% | **10** | — |

Lo stop a pareggio costa **1,8 R** contro gli 8,4 del chiudere sempre: e' il
modo piu' economico di proteggersi. Da solo lascia ancora 3 uscite per gap
(operazioni che il lunedi' riaprono sotto il prezzo d'ingresso); **aggiungendo
il filtro sopra +1R le uscite per gap vanno a zero** e il costo totale resta
2,2 R.

La differenza con lo stop alla chiusura e' istruttiva: stessa intenzione, esiti
opposti (+161,2 contro +152,5, 3 uscite per gap contro 10). Il motivo e' il
margine: al pareggio resta tutto il guadagno accumulato come cuscinetto, alla
chiusura del venerdi' il cuscinetto e' zero.

**La regola migliore per tenere aperto** e' quindi: *stop a pareggio prima
della sosta, e si resta aperti solo se si e' almeno a +1R*. Costa 2,2 R su
163,0 (l'1,3%) e azzera l'esposizione ai gap. Resta comunque sotto la
configurazione in vigore (+171,1 R), ma e' la versione giusta se un giorno
servisse.

### Le stesse regole contro gap generici, non solo quelli capitati

Sui gap realmente accaduti tutte le regole con filtro escono a costo zero, ma
e' un campione di 23 attraversamenti: dice poco. Ripetuto il metodo
dell'appendice AS — salti pescati a caso dai 340 fine settimana dello storico,
20.000 storie alternative — su ciascuna regola:

| regola | attraversamenti | margine mediano | costo mediano | media | p90 | p99 | storie a costo zero |
|---|---|---|---|---|---|---|---|
| nessuna protezione | 23 | 1,58 R | 2,7 | 5,3 | 14,2 | 32,9 | 15% |
| stop a pareggio | 23 | 1,09 R | 5,5 | **8,1** | 18,1 | 37,3 | **0%** |
| **pareggio + solo sopra +1R** | **12** | 1,55 R | **0,0** | **2,1** | 7,2 | 23,8 | **56%** |
| pareggio + solo sopra +3R | 7 | 1,38 R | 0,0 | **1,6** | 4,8 | 24,0 | **66%** |
| stop alla chiusura | 23 | 0,00 R | 7,9 | 10,4 | 21,3 | 41,0 | 0% |

### Il risultato che rovescia la lettura di prima

Sui gap capitati lo stop a pareggio DA SOLO sembrava quasi gratis (1,8 R). Su
storie generiche e' **la seconda regola peggiore**: costo atteso 8,1 R, e in
nessuna delle 20.000 storie esce a zero. Il motivo si legge nella colonna del
margine: portando lo stop a pareggio si **riduce** il cuscinetto da 1,58 a
1,09 R, perche' le operazioni con lo stop gia' sopra il pareggio non
guadagnano nulla mentre quelle sotto perdono margine. Protegge dal caso
"chiudo in perdita" e peggiora il caso "gap oltre lo stop".

**Il filtro invece regge**, ed e' l'unico che regge: tenendo solo le
operazioni gia' sopra +1R gli attraversamenti scendono da 23 a 12, il costo
atteso crolla a **2,1 R** e piu' della meta' delle storie esce a zero. Con la
soglia a +3R si scende a 1,6 R ma restano solo 7 attraversamenti, quindi il
guadagno del tenere aperto si assottiglia.

**Conclusione rivista**: quello che protegge non e' spostare lo stop, e'
**non attraversare il fine settimana con le operazioni deboli**. Lo stop a
pareggio da solo e' controproducente; il filtro sopra +1R e' la regola giusta,
e va tenuta anche senza toccare lo stop.

### Correzione: la metrica giusta e' il risultato, non lo scarto dallo stop

Obiezione dell'utente, fondata: se il lunedi' riapre sotto lo stop, si esce al
prezzo di RIAPERTURA, non allo stop. Quindi due regole con stop diversi ma
entrambe superate dal salto **chiudono allo stesso prezzo**: il "costo rispetto
allo stop" misurato sopra non e' una differenza di soldi fra le regole, e' solo
lo scarto rispetto al piano. La tabella precedente esagerava le differenze.

Rifatto misurando il **risultato finale** delle sole 23 operazioni vive al fine
settimana, sulle stesse 20.000 storie (quando il salto non supera lo stop
l'operazione prosegue, col percorso reale traslato del salto):

| regola | reale | mediana | media | p10 | p90 |
|---|---|---|---|---|---|
| sempre aperta, stop dov'e' | 51,8 | 50,7 | 49,4 | 36,5 | 60,5 |
| stop a pareggio | 51,8 | 52,3 | **50,8** | 37,6 | 62,0 |
| **pareggio + solo sopra +1R** | **56,5** | 56,3 | **54,9** | **46,5** | 61,3 |
| **solo sopra +1R, stop invariato** | **56,5** | 56,3 | **54,9** | **46,4** | 61,2 |
| chiude sempre il venerdi' | 43,1 | 43,1 | 43,1 | 43,1 | 43,1 |

Tre correzioni alla lettura precedente:

1. **Lo stop a pareggio non e' controproducente**: aggiunge +1,4 R in media
   (50,8 contro 49,4). Poco, ma positivo — l'opposto di quanto diceva la
   metrica sbagliata. Serve nei casi in cui il salto e' piccolo e il prezzo
   torna indietro senza gap, non contro i gap grossi.
2. **Il filtro sopra +1R resta la regola che conta**, e da sola: +5,5 R di
   media rispetto al non filtrare, e soprattutto alza il decimo percentile da
   36,5 a 46,5 — cioe' migliora le storie sfortunate, che e' il punto.
3. **Stop a pareggio e filtro insieme valgono quanto il solo filtro** (54,9 in
   entrambi i casi): una volta tolte le operazioni deboli, spostare lo stop non
   aggiunge nulla. E' il filtro a fare tutto.

Confermata invece la conclusione di fondo: **chiudere sempre il venerdi' e' la
peggiore** (43,1 fisso contro 54,9 di media), ma e' anche l'unica senza
incertezza. La differenza fra tenere aperto col filtro e chiudere e' 11,8 R
sulle sole 23 operazioni interessate, con una dispersione fra 46,5 e 61,3.

### Controllo della variante proposta (filtro +3R con stop a +1R)

| variante | netto | vinte | uscite per gap | chiuse dal filtro |
|---|---|---|---|---|
| sempre aperta | +163,0 | 36,5% | 0 | — |
| **solo sopra +1R** | **+167,6** | 37,6% | **0** | 11 |
| +1R e stop a pareggio | +160,8 | 37,4% | 0 | 11 |
| solo sopra +3R | +158,5 | 37,9% | 0 | 16 |
| **+3R e stop a +1R** | **+158,5** | 37,9% | 0 | 16 |
| +3R e stop a pareggio | +158,5 | 37,9% | 0 | 16 |

Le tre righe con soglia +3R danno **lo stesso identico risultato**: quando
l'operazione e' gia' sopra +3R il trailing ha portato lo stop ad almeno +1R da
solo (MFE-2), quindi ordinare di spostarlo a +1R o a pareggio non cambia nulla.
La regola proposta e' gia' contenuta nel trailing.

**La soglia migliore e' +1R, non +3R**: +167,6 contro +158,5, cioe' 9 R di
differenza. A +3R si filtrano 16 operazioni invece di 11, e le 5 in piu' che
si chiudono erano mediamente in guadagno. Entrambe azzerano le uscite per gap.

## Appendice AU: undici anni mai visti — lo storico esteso al 2009

Tutto quello che sta sopra e' misurato sul 2020-2026. La strategia e' stata
costruita li' dentro: le verifiche "per anno" e i train/test 2020-2023 contro
2024-2026 condividono tutti lo stesso mercato, l'oro che sale da 1.500 a
5.500 con due strappi. Un fuori campione dentro il proprio periodo non e' un
fuori campione.

Il feed Dukascopy serve gli stessi file giornalieri fino al 2009, quindi
l'archivio si allunga senza cambiare fonte ne' formato:
`trading/scripts/estendi_storico.py`. Prima di fidarsi, la verifica: sul
2020-06-10, giorno gia' in archivio, il convertitore riproduce le 1.379
candele con **differenza massima 0,0** su tutte e cinque le colonne. E il
riscontro esterno torna al centesimo: massimo **1920,66 il 06/09/2011**,
minimo **1046,23 nel 2015**.

Sono **undici anni** (2009-2019, 3,93 milioni di candele) che nessuna scelta
di questo progetto ha mai visto, e contengono esattamente i regimi che
mancavano: il picco del 2011, il crollo 2012-2015, il laterale 2016-2019.

### Il risultato

| periodo | strategia | op | R | R/op | vinte | DD | anni+ | PF |
|---|---|---|---|---|---|---|---|---|
| **2009-2019** | **in uso** | 382 | **-39,3** | -0,10 | 28,0% | **47,8** | **3/11** | 0,86 |
| 2009-2019 | A | 382 | -47,5 | -0,12 | 17,0% | 71,1 | 4/11 | 0,86 |
| 2009-2019 | B | 382 | -90,8 | -0,24 | 22,5% | 89,8 | 2/11 | 0,72 |
| **2020-2026** | **in uso** | 350 | **+157,1** | +0,45 | 34,9% | 17,6 | 6/7 | 1,73 |
| 2020-2026 | A | 350 | +169,7 | +0,48 | 24,9% | 14,6 | 7/7 | 1,69 |
| 2020-2026 | B | 350 | +170,5 | +0,49 | 36,9% | 14,4 | 7/7 | 1,72 |
| 2009-2026 | in uso | 732 | +117,8 | +0,16 | 31,3% | 54,5 | 9/18 | 1,24 |

Tutte e tre le candidate **perdono** sugli undici anni nuovi. Non "guadagnano
meno": perdono, con tre anni positivi su undici e una perdita massima di 47,8
R contro i 17,6 del periodo di casa — quasi tre volte tanto, cioe' il 48% del
conto al rischio dell'1%.

### Per anno (R, lotti fissi)

| anno | in uso | A | B | op | | anno | in uso | A | B | op |
|---|---|---|---|---|---|---|---|---|---|---|
| 2009 | -6,5 | -16,5 | -13,8 | 35 | | 2018 | -14,8 | +9,8 | -2,2 | 25 |
| 2010 | -16,7 | -31,7 | -23,6 | 33 | | 2019 | -4,9 | -3,4 | -7,3 | 32 |
| 2011 | +22,7 | +37,2 | +6,2 | 49 | | 2020 | -6,5 | +10,4 | +25,7 | 55 |
| 2012 | -17,8 | -22,2 | -27,8 | 46 | | 2021 | +13,1 | +15,7 | +16,6 | 51 |
| 2013 | -3,7 | -16,3 | -8,1 | 48 | | 2022 | +37,2 | +33,7 | +30,7 | 37 |
| 2014 | -6,9 | -6,5 | -9,7 | 22 | | 2023 | +23,5 | +19,1 | +13,6 | 47 |
| 2015 | +2,5 | +15,5 | +5,5 | 29 | | 2024 | +38,9 | +24,5 | +19,9 | 53 |
| 2016 | +14,1 | +1,1 | -3,8 | 45 | | 2025 | +44,0 | +55,1 | +50,8 | 82 |
| 2017 | -7,3 | -14,5 | -6,3 | 18 | | 2026 | +7,0 | +11,3 | +13,2 | 25 |

La riga di separazione non e' graduale: **tutti gli anni dal 2021 in poi sono
positivi, otto degli undici precedenti sono negativi.** Non e' un
peggioramento progressivo, e' un interruttore.

### Dove sta davvero il vantaggio: nel lato lungo

| periodo | long | short |
|---|---|---|
| 2009-2019 | 230 op, **-29,5 R** (-0,13/op) | 152 op, -9,8 R (-0,06/op) |
| 2020-2026 | 243 op, **+141,1 R** (+0,58/op) | 107 op, +16,0 R (+0,15/op) |
| 2009-2026 | 473 op, +111,6 R (+0,24/op) | 259 op, **+6,2 R (+0,02/op)** |

Su diciotto anni il lato **corto non ha vantaggio**: +6,2 R su 259 operazioni,
cioe' due centesimi di R per operazione, indistinguibile da zero. E il 90% del
risultato del 2020-2026 viene dalle operazioni lunghe. Letto con calma: quello
che si e' misurato non e' una strategia che legge la struttura, e' un modo di
salire sul treno dell'oro mentre saliva.

### Nota sui numeri del periodo di casa

Caricando anche il 2009-2019, il 2020-2026 non da' piu' +171,1 R ma +157,1 su
350 operazioni invece di 348. Non e' un errore: `high_volatility_months` usa
una finestra **espansiva** sul passato, quindi con undici anni di storia in
piu' la mediana di riferimento cambia e qualche mese cambia regime. E' un
calcolo causale in entrambi i casi — quello nuovo e' semplicemente meglio
informato. Con `XAU_ANNI=2020-2026` si riottengono esattamente **348
operazioni e +171,1 R**, cioe' il numero pubblicato.

## Appendice AV: e' regime o unita' di misura? (ipotesi pre-registrata)

Prima di concludere qualcosa dall'appendice AU va escluso il sospetto ovvio.
Le soglie della taratura sono in **dollari**: impulso 4,00, buffer 0,30,
rischio fra 1,00 e 10,00. La conversione all'ATR scatta solo nei mesi ad alta
volatilita', quindi quasi mai prima del 2020. Quattro dollari valgono 0,16-0,34
ATR nel 2009-2019 e 0,03-0,17 ATR nel 2020-2026: la stessa soglia e' due o tre
volte piu' severa nel periodo vecchio.

**Ipotesi pre-registrata**: se il vantaggio appartiene alla strategia e non al
periodo, misurando TUTTE le soglie in ATR il 2009-2019 deve tornare positivo.

| variante | 2009-2019 | 2020-2026 | op tot |
|---|---|---|---|
| ufficiale (dollari) | **-39,3** (3/11 anni) | +157,1 | 732 |
| sempre ATR, rif. 2020-2024 | **-67,1** (3/11 anni) | +147,1 | 959 |
| sempre ATR, rif. 2009-2013 | **-105,3** (2/11 anni) | +142,8 | 810 |

**Ipotesi respinta.** Normalizzare all'ATR non recupera niente: peggiora, e
peggiora di piu' quanto piu' il riferimento e' onesto (mediana nota all'epoca
invece che presa dal futuro). Il periodo di casa resta positivo in tutte e tre
le versioni. Non e' un problema di unita' di misura.

### Cosa resta in piedi

1. **Il vantaggio misurato appartiene al 2020-2026**, non alla strategia. Su
   undici anni indipendenti la stessa identica regola perde.
2. **La perdita massima vera non e' 16-17 R ma almeno 47,8 R** (89,8 per B).
   Al rischio dell'1% per operazione sono 48 punti di conto, non 16. Qualunque
   dimensionamento tarato sul 2020-2026 e' ottimista di un fattore tre.
3. **Il lato corto e' da considerare senza vantaggio** finche' non lo si
   dimostra altrove: 259 operazioni su diciotto anni per +6,2 R.
4. Le conclusioni *relative* fra gestioni reggono anche fuori campione — A e B
   restano vicine fra loro e in uso, e l'ordine non si ribalta. Quello che non
   regge e' il segno.

Questo non dice che la strategia sia sbagliata: dice che **l'unica prova che
esiste a suo favore viene dal periodo su cui e' stata costruita**, e che gli
undici anni indipendenti dicono il contrario. Prima di metterla su un conto
reale — a maggior ragione su tre conti — la domanda da risolvere e' questa,
non quale variante di trailing renda mezzo R in piu'.

## Appendice AW: esiste un regime che salva il 2009-2019? No

Se il vantaggio del 2020-2026 vivesse in un regime preciso, la parte di
2009-2019 che somiglia a quel regime dovrebbe guadagnare. Il filtro si
**definisce sul periodo buono** (fra il 10simo e il 90simo percentile della
misura sulle 350 operazioni del 2020-2026) e si **applica al 2009-2019**, che
resta intatto. Tre misure, tutte causali e note all'apertura della giornata.

| misura | intervallo del 2020+ | dentro | fuori |
|---|---|---|---|
| volatilita' (ATR in % del prezzo) | 1,04 - 2,04 | 262 op, **-18,3 R** (4/11 anni) | 100 op, -11,5 R |
| distanza dalla media 50 (in ATR) | -2,80 - 5,88 | 298 op, **-20,9 R** (3/11) | 64 op, -8,9 R |
| distanza dalla media 200 (in ATR) | -2,24 - 11,76 | 249 op, **-23,3 R** (3/11) | 113 op, -6,6 R |
| tutte e tre insieme | — | 160 op, **-15,9 R** (3/11) | — |

**Nessun taglio funziona.** Dentro e fuori perdono entrambi, e la parte
"simile al 2020" perde piu' di quella diversa in tutte e tre le misure. Non
c'e' un sottoinsieme di condizioni che spieghi la differenza: il 2009-2019 non
e' un periodo sbagliato per la strategia, e' un periodo in cui la strategia non
ha vantaggio.

## Appendice AX: togliere il lato corto

| periodo | selezione | op | R | R/op | DD | anni+ |
|---|---|---|---|---|---|---|
| 2009-2019 | long+short | 382 | -39,3 | -0,10 | 47,8 | 3/11 |
| 2009-2019 | **solo long** | 230 | **-29,5** | **-0,13** | 30,8 | 5/11 |
| 2009-2019 | solo short | 152 | -9,8 | -0,06 | 25,2 | 4/11 |
| 2020-2026 | long+short | 350 | +157,1 | +0,45 | 17,6 | 6/7 |
| 2020-2026 | **solo long** | 243 | **+141,1** | **+0,58** | **12,9** | 5/7 |
| 2020-2026 | solo short | 107 | +16,0 | +0,15 | 21,2 | 4/7 |
| 2009-2026 | long+short | 732 | +117,8 | +0,16 | 54,5 | 9/18 |
| 2009-2026 | **solo long** | 473 | **+111,6** | **+0,24** | **39,2** | 10/18 |

Il solo long **migliora il rischio ma non cambia il segno**: sui diciotto anni
tiene il 95% del risultato con il 72% della perdita massima (39,2 contro 54,5)
e un anno positivo in piu'. Sul 2020-2026 rende di piu' per operazione (+0,58
contro +0,45) con un drawdown di 12,9 invece di 17,6. Ma sul 2009-2019 resta
negativo, e per operazione fa **peggio** del sistema completo (-0,13 contro
-0,10): lo short li' dentro faceva da ammortizzatore, non da zavorra.

Conclusione: rinunciare allo short e' una buona idea di igiene — 259 operazioni
in diciotto anni per +6,2 R non pagano il rischio — ma non e' il rimedio.

## Appendice AY: la taratura invertita, cioe' la prova del metodo

Non e' una ricerca di parametri migliori. E' la stessa identica ricerca
ripetuta sui due periodi: **12 gestioni x 7 obiettivi x 27 combinazioni di
conferme = 2.268 celle** (M33, H12 e M12 ciascuno allineato, contrario o
ignorato; H6 e H2 restano la struttura), minimo 60 operazioni per cella. Ogni
vincitore viene poi verificato sull'ALTRO periodo.

### Cercando sul 2009-2019 (1.932 celle valide)

| conferme | gestione | RR | dove e' stata scelta | verificata sul 2020-2026 |
|---|---|---|---|---|
| H12- · M12- | trail MFE-2 | 1:10 | **+6,9 R** su 100 op (5/11 anni) | -24,6 R su 98 op (1/7) |
| H12- · M12- | scala 2>0 4>2 6>4 | 1:10 | +6,7 R su 100 op (5/11) | -7,9 R su 98 op (3/7) |
| H12- · M12- | trail MFE-2 | 1:9 | +5,9 R su 100 op (5/11) | -24,6 R su 98 op (1/7) |

Il **migliore** di 1.932 modi di combinare la strategia su undici anni rende
**+6,9 R**, cioe' 0,07 R per operazione: dentro il costo dello spread. Non
esiste una taratura che funzioni sul 2009-2019 — non e' che abbiamo scelto
male i parametri, e' che li' dentro non c'e' niente da scegliere.

### Cercando sul 2020-2026 (2.016 celle valide)

| conferme | gestione | RR | dove e' stata scelta | verificata sul 2009-2019 |
|---|---|---|---|---|
| M33+ | pari a +3R | 1:10 | +223,4 R su 695 op (6/7 anni) | **-107,0 R** su 793 op (4/11) |
| M33+ · H12+ | pari a +3R | 1:10 | +221,6 R su 628 op (6/7) | **-85,6 R** su 685 op (5/11) |
| H12+ | pari a +3R | 1:10 | +219,4 R su 1.176 op (5/7) | **-183,0 R** su 1.250 op (2/11) |

### Il numero che chiude la questione

| ricerca fatta su | celle valide | positive anche sull'altro periodo |
|---|---|---|
| 2009-2019 | 1.932 | 1.231 (**64%**) |
| **2020-2026** | 2.016 | **17 (1%)** |

Cercando sul periodo vecchio, due celle su tre restano positive sul nuovo —
perche' nel 2020-2026 guadagnava quasi tutto. Cercando sul periodo nuovo,
**una cella su cento** resta positiva sul vecchio.

Questa asimmetria e' la diagnosi. Una ricerca su duemila celle dentro il
2020-2026 produce vincitori spettacolari (+223 R) che quasi mai sopravvivono
altrove: e' esattamente la firma del sovradattamento, e la taratura in vigore
e' uno di quei vincitori. Il problema non e' quale configurazione si e'
scelta, e' che **il 2020-2026 da solo non e' in grado di distinguere una
regola buona da una fortunata**.

### Cosa fare di questo

1. Il 2020-2026 non puo' piu' essere l'unico giudice: qualunque prova futura
   va chiusa sui diciotto anni, o almeno verificata sul 2009-2019.
2. Le tre verifiche chieste sono tutte negative: **AW** nessun regime salva il
   periodo vecchio, **AX** togliere lo short migliora il rischio ma non il
   segno, **AY** nessuna delle 2.268 configurazioni funziona sul 2009-2019.
3. Quello che resta in piedi non e' la strategia, e' il metodo di misura:
   motore causale, spread e swap reali, gap pagati alla riapertura, placebo e
   permutazioni. Serve applicarlo a un'idea nuova, non a un'altra variante di
   questa.

## Appendice AZ: tutti i livelli come INGRESSO, 18 anni, 720 configurazioni

Richiesta: usare i livelli del progetto — order block, vuoti di volume,
massimi di volume — con l'ATR a compensare la volatilita', e trovare una
combinazione vincente. Ogni famiglia diventa una banda misurata in ATR, cosi'
la stessa regola vale con l'oro a 1.000 e a 5.000 dollari.

| | |
|---|---|
| famiglie | ob pieno, ob raffinato, POC di ieri, estremi area di valore, vuoti |
| timeframe | M33, M66, H2, H6 |
| modi | reazione, rottura, retest (tutti decisi alla chiusura della candela) |
| stop | 0,25 · 0,5 · 1,0 ATR giornaliero |
| obiettivi | 1:2 · 1:3 · 1:5 · 1:10, uscita a fine giornata |
| eventi | **168.833 veri**, 124.225 placebo, 2009-2026 |

Protocollo fissato prima di guardare i numeri: ricerca sul 2009-2019,
verifica sul 2020-2026, ogni cella con il proprio placebo (lo stesso livello
spostato a caso di 0,2-0,6 ATR: resta dove il prezzo passa, ma non e' piu' il
livello).

### Il risultato

| | |
|---|---|
| celle misurabili (>= 80 operazioni) | 708 |
| con R/op > 0 sul periodo di ricerca | **8 (1%)** |
| positive su ENTRAMBI i periodi | **4** |
| vantaggio sul placebo, mediana | **+0,003 R/op** |
| che passano la scrematura pre-registrata | **0** |

R/op medio di TUTTE le celle, per famiglia:

| famiglia | 2009-2019 | 2020-2026 |
|---|---|---|
| ob pieno | -0,200 | -0,171 |
| ob raffinato | -0,202 | -0,162 |
| poc ieri | -0,194 | -0,157 |
| va ieri | -0,181 | -0,148 |
| vuoto ieri | -0,221 | -0,173 |

**Nessuna famiglia, su nessun timeframe, con nessuno stop e nessun obiettivo.**
Le quattro celle positive su entrambi i periodi sono la stessa (M66, ob pieno,
retest) contata per quattro obiettivi che non vengono mai raggiunti, e rende
+0,0008 e +0,0088 R/op: tre ordini di grandezza sotto il costo dello spread.
La percentuale di operazioni vinte si ferma al 48%, cioe' testa o croce.

### Le confluenze non selezionano niente

Domanda: quando piu' famiglie si accendono insieme, va meglio? Contate come
famiglie diverse **allo stesso prezzo** (entro 0,25 ATR) e nella stessa
mezz'ora, la risposta e' che la confluenza non e' un caso speciale ma **lo
stato normale**: 167.808 eventi su 168.833 hanno gia' quattro famiglie
sovrapposte. I livelli di famiglie diverse stanno uno sull'altro quasi
sempre, perche' sono tutti costruiti intorno a dove il prezzo ha lavorato. I
mille casi rari a bassa confluenza non vanno meglio degli altri.

Nota metodologica, due tarature del placebo imparate sbagliando: lo
spostamento va estratto UNA volta per livello (a ogni barra la banda balla e
le condizioni sulla barra precedente non si formano mai), e deve essere
PICCOLO — a 0,5-2 ATR il livello finto finisce fuori dal range della giornata
e il placebo produce un quarto degli eventi, rendendo il confronto inutile.

## Appendice BA: e la zona raffinata come filtro? Anche quella sparisce

L'appendice AZ prova i livelli come ingresso. Ma il risultato positivo del
progetto (appendici P e AJ) era un'altra cosa: la zona raffinata come **voto
di qualita' su un segnale gia' valido**, +1,342 R/op sul campione largo, sette
anni su sette. Misurato pero' solo sul 2020-2026 — il periodo che l'appendice
AY ha mostrato incapace di distinguere una regola buona da una fortunata.

Rifatta sui diciotto anni, campione largo, differenza fra dentro e fuori la
zona:

| tf | zona raffinata: 2009-2019 | 2020-2026 | 2009-2026 |
|---|---|---|---|
| M12 | -0,286 (27 op) | -0,252 (24 op) | **-0,274** (51 op) |
| M33 | **+0,400** (19 op) | **-0,595** (31 op) | **-0,171** (50 op) |
| M66 | -0,419 (19 op) | — | -0,315 (31 op) |
| H2 | — | +0,513 (15 op) | +0,065 (28 op) |
| H3 | — | — | -0,535 (18 op) |
| H6 | — | — | -0,339 (20 op) |

**Su M33 il segno si ribalta fra i due periodi**: +0,400 prima, -0,595 dopo.
Su diciotto anni cinque timeframe su sei danno differenza negativa, e l'unico
positivo (H2, +0,065) sta su 28 operazioni.

E il motivo per cui non ce ne eravamo accorti e' nei conteggi: sul campione
ufficiale, in **diciotto anni**, gli ingressi che cadono dentro una zona
raffinata sono **20 su M12, 12 su M33, 5 su M66, 4 su H2, 4 su H3, 3 su H6**.
Il risultato piu' promettente del progetto poggiava su qualche decina di
operazioni. Con numeri cosi' non si distingue un vantaggio dal rumore, e
infatti allungando la storia il vantaggio non c'e' piu'.

### Conclusione delle due appendici

I livelli — order block pieni e raffinati, POC, area di valore, vuoti di
volume — **non portano vantaggio misurabile su diciotto anni**, ne' come
ingresso (720 configurazioni, zero sopravvissuti) ne' come filtro (segno che
si ribalta, campioni da qualche decina). Anche normalizzando tutto all'ATR,
che era l'ipotesi da provare.

Con AU-AY questo chiude il quadro: non c'e' un pezzo di questa famiglia di
strategie che sopravviva alla storia lunga. Quello che regge e' il metodo di
misura, che ha appena bocciato il proprio risultato migliore.

## Appendice BB: gli order block ridefiniti come li usa l'utente

Obiezione dell'utente al modo in cui li segnavamo: una zona non deve morire
dopo trenta candele, deve restare buona **finche' non viene toccata**; e una
gia' toccata, se il prezzo ci torna una seconda o terza volta, non e' piu' un
order block ma un supporto o una resistenza. Il tocco e' la **chiusura dentro
la zona**, non l'ombra: su un timeframe grande e' una conferma piu' forte.

Misurato su **1.228.881 tocchi** in diciotto anni (M33, M66, H2, H6; quattro
definizioni di tocco; stop 0,25-1 ATR; obiettivi 1:2-1:10; uscita serale),
ciascuno col suo placebo — la stessa zona spostata a caso di 0,2-0,6 ATR.

### Prima: un errore mio, trovato e corretto

La prima versione registrava l'evento all'**apertura** della candela invece
che alla chiusura: si entrava al prezzo di chiusura e poi si ripercorreva la
candela stessa sapendo gia' come finiva. Su H6 sono sei ore di futuro
regalate, e il risultato era spettacolare — **+0,98 R/op, 73% di operazioni
vinte, 11 anni positivi su 11**. L'indizio che l'ha smascherato: **il placebo
faceva il 73,5%**, identico. Una zona spostata a caso non puo' funzionare
come una vera; se lo fa, non e' la zona che funziona. Corretto, e bloccato da
un test che verifica l'invariante (l'istante di un evento e' la chiusura
della candela il cui prezzo e' quello d'ingresso).

### 1. La scadenza a 30 candele buttava via zone buone? No

| eta' al tocco | R/op | placebo | anni positivi |
|---|---|---|---|
| 0-5 candele | -0,041 | -0,047 | 3/11 |
| 6-15 | -0,029 | -0,022 | 3/11 |
| 16-30 | -0,041 | -0,046 | 2/11 |
| 31-60 | -0,017 | -0,024 | 3/11 |
| 61-120 | -0,024 | -0,026 | 3/11 |
| **oltre 120** | **-0,094** | -0,099 | **0/11** |

Le zone vecchie non rendono quanto le fresche: rendono **peggio**, e la
fascia oltre le 120 candele non ha un solo anno positivo su undici. Tenerle
vive piu' a lungo aggiunge occasioni scadenti, non occasioni perse.

### 2. Il primo tocco vale piu' del secondo e del terzo? No

| tocco | R/op | placebo | operazioni |
|---|---|---|---|
| primo | -0,041 | -0,061 | 5.978 |
| secondo | -0,041 | -0,057 | 2.171 |
| terzo | -0,081 | +0,009 | 908 |
| quarto o oltre | -0,064 | -0,076 | 1.045 |

Nessuna progressione: il secondo tocco vale come il primo, il terzo e' il
peggiore. **Una zona ritoccata non diventa un supporto migliore.**

### 3. Quale definizione di tocco? Non cambia niente

| definizione | R/op | placebo | differenza |
|---|---|---|---|
| chiusura sul TF della zona | -0,047 | -0,056 | +0,009 |
| chiusura su M12 | -0,045 | -0,048 | +0,003 |
| chiusura su M6 | -0,050 | -0,046 | -0,004 |
| ombra | -0,039 | -0,051 | +0,011 |

La chiusura dentro, che doveva essere la conferma piu' forte, non batte
l'ombra. Tutte e quattro stanno a un passo dal proprio placebo.

### 4. La zona rotta si ribalta in supporto/resistenza? No

Su **circa 180.000 tocchi per definizione** dopo l'invalidazione, operati al
contrario: da -0,023 a -0,031 R/op, con differenze dal placebo fra +0,000 e
+0,005. Il supporto rotto non diventa resistenza in modo utilizzabile.

### Il quadro completo

720 celle (timeframe x definizione x tocco x stop x obiettivo). Positive e
sopra il placebo sul 2009-2019: **22**. Ancora positive sul 2020-2026: **5**.
Il 3% che passa il primo filtro e il 23% che sopravvive al secondo sono
esattamente quello che darebbe il caso, e la migliore rende +0,036 R/op su
292 operazioni.

## Appendice BC: perche' il win rate non e' una leva

Richiesta dell'utente: una strategia con **oltre il 50% di operazioni vinte a
RR 1:1,5-1:2**. La misura dice che la prima meta' e' facile e non serve a
niente. Decomposizione degli esiti sugli stessi 15.974 tocchi (zone OB,
chiusura sul TF, tutte le fasce):

| stop | RR | stop pieno | obiettivo preso | uscita serale | vinte | R/op | media vinta | media persa |
|---|---|---|---|---|---|---|---|---|
| 0,25 ATR | 1:2 | 42,1% | 14,2% | 43,7% | **41,8%** | -0,07 | +1,02 | -0,85 |
| 0,50 ATR | 1:2 | 20,3% | 3,6% | 76,1% | **47,5%** | -0,04 | +0,55 | -0,57 |
| 1,00 ATR | 1:2 | 5,4% | **0,2%** | 94,5% | **48,8%** | -0,03 | +0,28 | -0,32 |

Allargando lo stop la quota di operazioni vinte sale da 41,8% a 48,8% — ma
l'obiettivo 1:2 viene raggiunto nello **0,2% dei casi** invece che nel 14%, e
il risultato resta negativo. Le "vinte" diventano semplicemente chiusure
serali in leggero utile: la vincita media scende da +1,02 a +0,28 R e la
perdita media da -0,85 a -0,32.

**Il win rate si porta dove si vuole** stringendo o allargando lo stop, o
uscendo prima: e' una conseguenza della geometria, non una proprieta' del
vantaggio. Infatti il placebo ha le stesse quote (40,6% / 47,1% / 48,3%): una
zona finta produce lo stesso win rate di una vera.

A RR 1:2, delle 180 celle misurate **9 superano il 50% di operazioni vinte e
nessuna di quelle 9 ha risultato positivo**.

Il conto teorico dice che a 1:2 basterebbe il 33,3% di vinte per pareggiare,
e a 1:1,5 il 40%: sembrano soglie gia' superate. Non lo sono, perche' quel
conto vale solo se ogni operazione finisce a +RR o a -1R. Con l'uscita serale
la maggior parte finisce in mezzo, e allora l'unico numero che conta e' **R
per operazione**. Un obiettivo sensato non e' "oltre il 50% di vinte" ma
"R/op stabilmente sopra zero al netto di spread e swap", e la quota di vinte
che ne esce e' quello che e'.

## Appendice BD: il filtro di fondo contava le domeniche come giornate

Incoerenza nota del progetto, confermata dalla verifica avversariale:
``segnali.filtro_macro`` faceva ``resample("1D")`` senza soglia di barre
minime, mentre ``volatility.daily_bars`` — usata dall'ATR — scarta le sessioni
sotto le 300 candele perche' non sono giornate.

Misura sull'archivio: **il 17% delle giornate D1 grezze sono spezzoni**, e 104
su 108 sono domeniche sera (mediana 120 minuti di scambi alla riapertura).
Quindi la media a 50 giorni copriva ~42 giornate vere, e una volta a settimana
ci entrava un valore quasi identico alla chiusura del venerdi'.

| | come'era | senza domeniche |
|---|---|---|
| giornate classificate diversamente | — | **229 su 4.524 (5,1%)** |
| operazioni (2009-2026) | 732 | 712 |
| 2009-2019 | -39,3 R (-0,103/op) | -39,6 R (-0,106/op) |
| 2020-2026 | +157,1 R (+0,449/op) | +154,7 R (+0,458/op) |
| 2009-2026 | +117,8 R | +115,1 R |

Il difetto e' reale e il 5,1% di giornate ribaltate non e' poco, ma **nessuna
conclusione cambia**: il risultato per operazione e' identico a tre decimali
in tutti i periodi. Corretto in `framework/segnali.py`, con la misura scritta
nel docstring perche' i numeri pubblicati prima si spostano di poco e chi li
ritrova sappia perche'.

## Appendice BE: order block M12 + vuoto di volume, il setup dell'utente

Arrivato con un'operazione vera: innesco su un order block M12, e sopra una
fascia a volume quasi nullo "da riempire" come bersaglio. Richiesta: una
strategia semi-scalp intraday, una o piu' operazioni al giorno, RR 1:1,5-1:2.

Era l'unico pezzo mai misurato: l'appendice AZ aveva provato i vuoti come
INGRESSO, l'appendice AE l'obiettivo appoggiato ai livelli **strutturali** —
mai i vuoti di volume come bersaglio, rimasti dall'appendice AB come "fase 2
mai aperta".

### Il risultato che sembrava, e cosa era

La prima misura dava numeri fuori scala: sugli stessi inneschi, chiedere che
nella direzione dell'operazione esistesse un vuoto portava il risultato da
**-0,20 a +0,50 R/op** con obiettivo fisso 1:2, con **18 anni positivi su 18**,
+0,476 R/op sul 2009-2019 e +0,545 sul 2020-2026, ~340 operazioni l'anno e il
58-60% di operazioni vinte. Esattamente quello che era stato chiesto.

Tre controlli l'hanno smontato, nell'ordine in cui li ho fatti.

**1. L'aritmetica delle barriere.** Con lo stop a 0,25 ATR e l'obiettivo a
1,61 ATR (fascia oltre 5R), l'obiettivo risultava raggiunto nel **59%** dei
casi e lo stop nel **24%**. Una barriera sei volte piu' lontana non puo'
essere colpita piu' spesso di una vicina: nessun percorso di prezzo lo
permette. Il calcolo degli esiti e' stato riverificato con
un'implementazione indipendente su 200 operazioni — zero discordanze — quindi
l'errore stava a monte, nella selezione.

**2. Il confronto con ingressi a caso.** Stesse ore, stessa geometria, entrata
casuale: stop 43,5%, obiettivo 16,6%. Il sottoinsieme "con vuoto": stop 33,5%,
obiettivo 38,1%. Piu' del doppio, in una direzione che il caso non spiega.

**3. La divisione per LATO**, che ha dato la risposta:

| lato | senza vuoto | con vuoto | eventi con vuoto |
|---|---|---|---|
| short | -0,395 | **+0,468** | 19.460 |
| long | -0,145 | **-0,279** | 2.506 |

Tutto l'effetto stava sugli **short**, e i long — dieci volte meno numerosi —
andavano perfino peggio. Un'asimmetria del genere non e' un fatto di mercato,
e' la firma di un difetto.

### Il difetto

L'istogramma del profilo copriva **l'intera escursione della giornata, futuro
compreso**. I livelli sotto al minimo toccato fino a quel momento erano tutti
a zero; quella fascia veniva chiusa dal primo livello scambiato e registrata
come un vuoto, il cui bordo lontano era **il minimo futuro del giorno** — un
prezzo che la giornata avrebbe raggiunto per definizione. Verso l'alto la coda
non veniva mai chiusa, quindi i long non avevano l'equivalente: da qui
l'asimmetria.

Corretto limitando la ricerca al tratto **gia' scambiato**, e bloccato da un
test che verifica che nessun vuoto cada fuori da li'.

### I numeri veri

539.708 valutazioni su diciotto anni, ogni chiusura M12 nella finestra
operativa, stop 0,25 ATR, obiettivo 1:2, uscita serale.

| lato | senza vuoto | con vuoto |
|---|---|---|
| short | -0,016 (227.548 op) | **-0,090** (42.306) |
| long | -0,092 (251.881 op) | **-0,134** (17.973) |

**Il vuoto peggiora il risultato in entrambe le direzioni.** E dentro ogni
fascia di posizione nel range il quadro non cambia: da -0,057 a -0,154.

L'order block non aggiunge niente: -0,077 contro -0,082 sul bordo, -0,025
contro -0,063 a meta' range, -0,007 contro -0,051 piu' su.

Il **setup completo** (order block e vuoto concordi, 2.008 occasioni in
diciotto anni, circa 110 l'anno): **-0,050 R/op**, -0,097 sul 2009-2019 e
+0,042 sul 2020-2026, **6 anni positivi su 18**.

### Cosa resta

La posizione nel range gia' scambiato non e' un vantaggio (tutte le fasce fra
-0,041 e -0,082), il vuoto non lo e', l'order block nemmeno, e le tre cose
insieme neanche. L'idea era ben posta e l'unica parte non ancora misurata del
progetto: adesso e' misurata.

Vale la pena tenere il metodo che l'ha smontata, perche' e' piu' rapido di
qualunque backtest: **quando l'obiettivo lontano viene raggiunto piu' spesso
dello stop vicino, non serve cercare oltre — c'e' del futuro nel calcolo.**

## Appendice BG: appendici AZ e BA ricalcolate dopo la correzione dell'istante

Le appendici AZ e BA sono state calcolate PRIMA che si scoprisse il difetto
dell'appendice BB: l'istante di un evento veniva registrato all'apertura della
candela invece che alla chiusura, quindi l'operazione ripercorreva la candela
stessa sapendo gia' come finiva. L'errore GONFIA i risultati, quindi le
conclusioni negative reggevano a maggior ragione — ma le cifre no, e vanno
sostituite.

Ricalcolo completo, 168.833 eventi veri e 124.225 placebo su diciotto anni,
720 configurazioni (5 famiglie di livelli x 3 modi di interazione x 4
timeframe x 3 stop x 4 obiettivi):

| | |
|---|---|
| celle con almeno 80 operazioni sul 2009-2019 | 708 |
| con risultato per operazione positivo | 53 (7%) |
| positive su ENTRAMBI i periodi | 19 |
| vantaggio mediano sul placebo | **-0,005 R/op** |
| **scelte** (>= 80 op, R/op > 0, +0,05 sul placebo) | **11** |
| **quante ne darebbe il caso** (stessi filtri applicati al placebo) | **18** |
| delle 11 scelte, sopravvivono sul 2020-2026 | 5 (45%) |

Il numero che conta e' l'ultimo confronto: **le celle vere che superano la
scrematura sono 11, quelle finte 18**. La selezione sui livelli veri produce
MENO sopravvissuti del caso. Non c'e' niente da salvare, e stavolta il conto
e' pulito.

La cella migliore su tutti e diciotto gli anni — retest degli estremi
dell'area di valore di ieri su H6, stop 0,25 ATR — rende +0,071 R/op su **242
operazioni in diciotto anni**, cioe' tredici l'anno: troppo poche per
distinguerle dal rumore, e comunque sotto qualunque soglia operativa.

Conclusione invariata: **i livelli non funzionano come ingresso**, in nessuna
delle 720 configurazioni, ne' sul periodo di ricerca ne' su quello di
verifica.

## Appendice BH: ricognizione da zero su 18 anni, e cosa dice la letteratura sull'ORB

Campagna con undici agenti in parallelo: quattro a mappare la struttura grezza
dei diciotto anni senza proporre niente, sei a provare famiglie di ipotesi
pre-registrate, uno a cercare online cosa si sa davvero dell'Opening Range
Breakout. Vincolo comune: dividere sempre 2009-2019 (ricerca) da 2020-2026
(verifica), sottrarre i costi, e riportare la scomposizione degli esiti con il
controllo di assurdita' (uno stop vicino deve essere colpito piu' spesso di un
obiettivo lontano).

### La mappa: cinque fatti solidi

**1. La gobba di volatilita' e' il fatto piu' robusto del mercato.** Escursione
mediana al minuto: minimo alle 04 UTC (0,170 $ nel 2009-19, 0,310 $ nel
2020-26), massimo alle 13 UTC (0,510 $ e 1,120 $). Rapporto **3,12x e 3,44x**.
Ampiezza dell'ora intera: 10,11 $ alle 13 contro 2,90 $ alle 04.

**2. L'orologio del mercato e' LOCALE, non UTC.** Rapporto picco/mediana del
profilo a blocchi di 5 minuti: UTC 2,318 — New York 2,496 — Londra 2,492
(2009-19); UTC 2,700 — New York 2,906 — Londra 2,877 (2020-26). L'orologio
locale e' piu' nitido in **entrambi** i periodi. Caso da manuale: in UTC
l'apertura di Londra da' due picchi gemelli alle 07:00 e alle 08:00; sull'ora
di Londra ne da' **uno solo**, alle 08:00 locali.

> Conseguenza per il progetto: le sessioni del framework (asia 0-7, london
> 7-12, ny 12-21 UTC) e la candela D1 a mezzanotte UTC **tagliano la giornata
> nel posto sbagliato**. Schedulare in UTC spalma ogni evento su due ore e
> dimezza il contrasto fra ora calda e ora fredda. La giornata vera va da
> 18:00 a 17:00 di New York.

**3. Nessuna ora e' direzionale.** Rapporto di varianza sui rendimenti
standardizzati sotto 1 in **21 ore su 24** in entrambi i periodi. Le uniche
che arrivano a 1 sono le 12-14 UTC. Trappola in cui l'agente e' caduto e da
cui e' uscito: senza standardizzare, le 11 UTC sembravano l'ora piu'
direzionale (VR 1,67) — era solo la finestra che sconfinava nelle 12-13, tre
volte piu' agitate.

**4. Dopo un impulso il prezzo CONTRASTA, non continua** — in tutte e 14 le
celle fascia x periodo, senza una sola eccezione. Ma il vantaggio lordo e'
**sempre piu' piccolo dello spread**: con |X| >= 0,20 ATR il lordo vale +0,121
R contro un costo di 0,370 R. **R netto negativo in tutte e 42 le
combinazioni.** E ha tre invarianze insieme — indifferente alla velocita'
dell'impulso, indifferente all'orizzonte, vivo solo entro 0,10 ATR
dall'ingresso — che sono la firma della microstruttura, non di un
comportamento del mercato.

**5. Una sola deriva sopravvive al placebo: la riapertura giornaliera delle
18:00 ET.** I 120 minuti successivi rendono +2,89 bp (t=7,5) nel 2009-19 e
+2,90 bp (t=4,7) nel 2020-26, positiva in tutti e quattro i sotto-periodi. Il
placebo ancorato 6 ore prima o 3 dopo da' +1,10/+1,12 bp nel periodo vecchio e
-0,06/-0,65 nel nuovo. In dollari vale +0,37 e +0,56 $ contro 0,30 $ di spread
nominale — cioe' **il vantaggio e' dell'ordine di UNO spread**, e lo spread
vero al rollover e' molto piu' largo di quello medio. Unico spunto rimasto in
piedi, e va misurato con lo spread di quella finestra prima di crederci.

### Le sei ipotesi: tutte respinte

| ipotesi | 2009-2019 | 2020-2026 | anni positivi |
|---|---|---|---|
| opening range breakout | **-0,118** (2.813 op) | -0,005 (1.673) | 5/18 |
| ORB con filtri di contesto | -0,030 (1.342) | -0,015 (875) | 7/18 |
| ritorno alla media dopo impulso | -0,162 (20.393) | -0,122 (13.320) | **0/18** |
| estremi del giorno precedente | -0,017 (1.046) | -0,013 (690) | 7/18 |
| persistenza pura | -0,120 (6.426) | -0,043 (3.967) | 2/18 |
| calendario | -0,104 (525) | +0,063 (316) | 6/18 |

Nessuna e' arrivata alla fase di demolizione, e in ognuna la scomposizione e'
fisicamente sana (stop colpito piu' spesso dell'obiettivo): stavolta non
c'erano artefatti da smascherare, c'era solo assenza di vantaggio.

### Cosa si sa dell'ORB, davvero

**Esiste letteratura seria, ed e' positiva ma vecchia e circoscritta.**
Formalizzata da Toby Crabel (1990) sui futures. Misurata da Holmberg,
Lonnbark e Lundstrom (*Finance Research Letters* 2013) su petrolio e S&P 500:
rendimenti sopra i costi. Il meccanismo economico ha un nome ed e' pubblicato
sul *Journal of Financial Economics*: **momentum intraday** (Gao, Han, Li,
Zhou 2018) — la prima mezz'ora predice l'ultima, ed e' **piu' forte nei giorni
volatili, ad alto volume e con dati macro**. Lundstrom quantifica: 150-200
punti base al giorno di differenza fra terzile alto e basso di volatilita'.

**Ma tre cose vanno nella direzione opposta.**

1. **L'unico studio recente costruito per falsificare non trova niente.**
   Mesfin (2026), 947 giorni di MNQ 2021-2025, quattordici famiglie di segnali
   fra cui l'ORB, walk-forward con costi realistici: nessun segnale supera i
   criteri, il vantaggio lordo (0,07-1,50 punti) non copre i costi.
2. **L'inventore dice che e' rotta, e spiega perche'.** Crabel, 2025: l'ORB e'
   nel periodo peggiore dagli anni Sessanta, e la causa e' strutturale — i
   mercati 24 ore hanno cancellato il riferimento su cui era costruita.
   *"C'e' cosi' tanto volume nelle sessioni 24 ore che e' impossibile
   determinare quale sia l'apertura."*
3. **Sull'oro e sul forex non esiste NESSUNO studio serio.** Zero. La *London
   Breakout* — rottura del range asiatico all'apertura di Londra, che e' la
   versione oro/forex — e' materiale da blog di broker, senza eccezione.

**L'obiezione decisiva per il nostro caso.** L'ORB non e' una regola
geometrica: sfrutta un fatto istituzionale. Alle 9:30 di New York, dopo
diciassette ore in cui l'informazione si e' accumulata senza poter essere
scambiata, tutti gli ordini arrivano insieme su un prezzo unico osservato da
tutti. **L'oro spot non ha niente di tutto questo**: scambia in continuo, non
c'e' asta di apertura, non c'e' gap informativo da smaltire. Applicare l'ORB
all'oro vuol dire **scegliere un'ora e chiamarla apertura** — e le candidate
sono quattro (Londra, COMEX, mezzanotte UTC, apertura del broker), cioe'
quattro strategie diverse fra cui scegliere dopo aver visto i risultati e'
data snooping travestito da definizione.

C'e' anche la conferma empirica diretta: uno studio sui futures cinesi su oro
e argento (*Global Finance Journal* 2025) misura che **prima** dell'aggiunta
della sessione notturna era la prima mezz'ora diurna a predire l'ultima;
**dopo**, il predittore diventa la prima mezz'ora notturna. L'apertura che
conta e' quella dove arriva l'informazione nuova, e si sposta quando cambia
l'orario di negoziazione.

### Conclusione della campagna

Il test empirico e la letteratura dicono la stessa cosa, arrivandoci da
strade diverse: **l'ORB sull'oro parte senza il meccanismo che lo fa
funzionare altrove**, e infatti misurato da' -0,118 R/op sul periodo di
ricerca con 5 anni positivi su 18.

Restano due cose utili, nessuna delle quali e' una strategia:

- **la correzione dell'orologio** (sessioni e giornata da ridefinire in ora
  locale, non UTC), che e' un miglioramento del framework valido comunque;
- **la deriva della riapertura delle 18:00 ET**, unico effetto sopravvissuto
  al placebo, da misurare con lo spread vero di quella finestra prima di
  farci qualunque ipotesi.

---

## Appendice BJ: l'ORB dove dovrebbe funzionare (S&P 500), e cosa dice davvero la documentazione

Richiesta dell'utente: *"non su oro, io non so l'ORB su che mercato giri ma e'
su quello che dobbiamo stare"*. Giusto: l'ORB nasce sui futures su indici, che
hanno l'asta di apertura che l'oro spot non ha. Quindi va misurato li'.

### I dati

S&P 500 a un minuto, **2010-11 -> 2018-12, 2.117.667 barre**, da HistData
tramite il repository pubblico `FutureSharks/financial-data`. Fonte del tutto
indipendente dal resto del progetto. Il fuso e' stato determinato **per
misura**: il minuto piu' scambiato cade alle 09:30 sia in gennaio-febbraio sia
in giugno-agosto, quindi i timestamp seguono gia' l'ora di New York con l'ora
legale (se fossero EST fisso, d'estate il picco cadrebbe alle 08:30).

Sessione di cassa 09:30-16:00, 1.938 giornate piene, costo 0,5 punti indice
andata e ritorno. Ricerca 2011-2014, verifica 2015-2018 (`run_orb_sp500.py`).

### Ipotesi A: la regola originale di Crabel, e le finestre classiche

| finestra | ricerca R/op | verifica R/op | vinte% (ver.) | anni+ ricerca | anni+ verifica |
|---|---|---|---|---|---|
| 5 min   | -0,143 | -0,110 | 22,5 | 0/4 | 0/4 |
| 15 min  | -0,161 | -0,134 | 30,2 | 0/4 | 1/4 |
| 30 min  | -0,106 | -0,073 | 36,9 | 0/4 | 1/4 |
| 60 min  | -0,054 | -0,018 | 44,2 | 0/4 | 1/4 |
| Stretch | -0,026 | -0,029 | 40,5 | 0/4 | 2/4 |

**Ipotesi A respinta su tutta la linea.** Nessuna finestra e' positiva in
nessuno dei due periodi. Per anno la regola originale fa: 2011 -5,97 R, 2012
-3,51, 2013 -8,91, 2014 -5,71, 2015 +19,21, 2016 -21,63, 2017 -27,07, 2018
+1,88 -> **2 anni positivi su 8**, saldo -46 R su 1.679 operazioni.

Nota strutturale: piu' la finestra e' larga, meno si perde. E' la firma di una
strategia che paga solo il costo del falso segnale: allargando la soglia si
fanno meno rotture false, ma non compare mai un vantaggio. Lo Stretch, che e'
la soglia *adattiva* di Crabel, e' il meno peggio proprio perche' e' quello che
si adatta.

### Ipotesi B: il vantaggio vive nei giorni volatili?

| regime | ricerca R/op | verifica R/op |
|---|---|---|
| basso | -0,109 | -0,095 |
| medio | +0,114 | -0,003 |
| alto  | -0,066 | +0,004 |

La letteratura (Lundstrom; Gao et al., *JFE*) prevede vantaggio nei giorni
volatili. In ricerca il segno migliore e' nel regime **medio** (+0,114), in
verifica nel regime **alto** (+0,004, cioe' zero). **La struttura non si
replica**: il regime che "funziona" cambia fra i due periodi. Ipotesi B
respinta.

### Limiti da dichiarare

1. I dati finiscono nel **2018**. Crabel sostiene che il decadimento e'
   recente, quindi questo test non puo' dire se l'ORB funziona *oggi*: dice
   che gia' **non funzionava dal 2011**, il che e' un'informazione piu' forte,
   non piu' debole.
2. E' l'indice cash (CFD SPXUSD), non il future ES. Manca il volume vero e i
   costi reali del future sono diversi. Ma il *prezzo* e' lo stesso, e la
   regola di Crabel e' fatta solo di prezzi.

### Cosa dice la documentazione online, letta bene

La ricerca in rete cambia il quadro, e va riportata con precisione perche' e'
facile confondere tre cose diverse che si chiamano tutte "ORB".

**1. Crabel originale (1990), Stretch, futures.** Crabel stesso, intervistato
su *Futures Magazine* (nov. 2019) e ripreso nel 2025, dice che l'ORB **si e'
rotto**: il passaggio ai mercati 24 ore ha cancellato il punto di riferimento
su cui poggiava, cioe' l'apertura. Testuale: gli ultimi anni sono i peggiori
per l'ORB dagli anni Sessanta, e Crabel Capital ha riequilibrato il momentum
con la mean reversion. La nostra misura sull'S&P e' coerente e anzi anticipa
la data.

**2. ORB accademico su futures su indici (TORB, 2013-2019).** Lo studio
*Assessing the Profitability of Timely Opening Range Breakout on Index Futures
Markets* misura DJIA, S&P 500, NASDAQ, HSI, TAIEX dal 2003 al 2013 e trova
oltre 8% annuo con p-value < 3% su tutti e cinque, fino al 20,3% sul TAIEX.
Ma e' un ORB **filtrato e temporizzato** (da qui la T di *Timely*), non la
regola nuda, ed e' un periodo che finisce nel 2013 — cioe' proprio dove i
nostri numeri sull'S&P sono meno negativi.

**3. L'ORB che oggi viene documentato come profittevole NON e' quello di
Crabel e NON e' su un indice.** E' Zarattini-Barbon-Aziz, *A Profitable Day
Trading Strategy For The U.S. Equity Market* (SSRN 4729284, 2024-25), e gira
su **azioni singole americane**, non su un indice, non sull'oro. Regole:

- range di apertura = **prima barra da 5 minuti**; long se rompe il massimo
  quando la barra e' rialzista, short se rompe il minimo quando e' ribassista;
- **stop a 10% dell'ATR a 14 giorni** dall'entrata (non l'altro estremo);
- **nessun obiettivo**: si chiude a fine sessione;
- filtri di ammissibilita': prezzo > 5 $, volume medio 14 giorni > 1.000.000
  azioni, ATR 14 giorni > 0,50 $;
- **e qui sta tutto**: si opera solo dove il volume dei primi 5 minuti supera
  il 100% del normale (*relative volume*), e solo le **prime 20 azioni del
  giorno** per quel rapporto. Sono le "Stocks in Play", cioe' i titoli che
  quella mattina hanno una notizia.

Risultato dichiarato 2016-2023: +1.637% totale, 41,6% annuo, Sharpe 2,4, beta
~0 al netto delle commissioni.

**4. La versione su QQQ (Zarattini-Aziz 2023)** — quella con obiettivo a 10R e
+1.484% dal 2016 — e' la piu' citata ed e' quella con cui bisogna stare piu'
attenti: e' un solo strumento, un solo periodo, e la leva a 3x fa il grosso del
numero. Ha esattamente la forma dei risultati che in questo progetto abbiamo
gia' smontato quattro volte.

### Conclusione operativa

- **L'ORB alla Crabel e' morto**, e non solo sull'oro: sull'S&P 500 perde da
  almeno il 2011, e l'autore stesso lo dice. Non ci si costruisce un bot.
- **Il meccanismo che l'ORB sfruttava non e' l'apertura in se': e' la notizia
  che arriva quando il mercato e' chiuso.** Per questo oggi sopravvive dove la
  notizia c'e' — le singole azioni in giornata di news — e muore dove il
  prezzo si forma 24 ore su 24 (oro, e ormai anche gli indici).
- Se l'utente vuole comunque un ORB **da mettere in produzione**, l'unica
  versione documentata e replicabile e' la 3: azioni americane, filtro sul
  volume relativo dei primi 5 minuti, stop a 0,1 ATR, uscita a fine sessione,
  venti nomi al giorno. E' un'altra infrastruttura (serve il dato azionario
  intraday su migliaia di titoli, non un solo simbolo), e va **verificata da
  noi** prima di crederci, perche' il paper e' 2016-2023 e non ha fuori
  campione.

---

## Appendice BK: l'ORB completo di Crabel, e perche' il 9% della letteratura e' un numero LORDO

L'utente contesta l'appendice BJ con un argomento giusto: *"la strategia
originale prevede un rendimento annuo circa 9%"*. Aveva ragione su due cose e
la revisione le conferma entrambe.

### Errore 1: avevo implementato meta' strategia

Il libro si chiama *Day Trading with **Short Term Price Patterns** and Opening
Range Breakout*. La rottura dello Stretch e' il grilletto; i pattern di
contrazione sono la **selezione**. In BJ avevo preso la rottura tutti i giorni,
cioe' Crabel senza la parte che decide quando operare. Aggiunti i quattro
pattern del libro, misurati sulla giornata precedente (`shift(1)`, mai sul
giorno in corso): NR4, NR7, inside day, ID/NR4.

### Errore 2: il costo era nascosto dentro un numero fisso

Il rischio mediano e' **6,5 punti indice**. Mezzo punto di costo tondo e' il
**7,8% del rischio**. Con 235 operazioni l'anno, un'ipotesi sui costi non e' un
dettaglio: e' la strategia. Rifatto tutto riportando LORDO e NETTO a tre
livelli (0,25 = spread di un tick sull'E-mini senza slittamento; 0,35 =
realistico con commissione; 0,50 = pessimista).

### Il fatto centrale: il vantaggio lordo esiste, ed e' proprio ~9-12% annuo

| | ricerca 2011-14 | verifica 2015-18 |
|---|---|---|
| tutti i giorni, **lordo** | **+0,060 R/op** (931 op) | **+0,042 R/op** (966 op) |
| tutti i giorni, netto 0,25 | +0,017 | +0,007 |
| tutti i giorni, netto 0,35 | −0,000 | −0,007 |
| tutti i giorni, netto 0,50 | −0,026 | −0,029 |

A 235 operazioni l'anno e rischio 1% per operazione, il lordo vale
**+14,1% annuo in ricerca e +9,9% in verifica**. Ecco da dove viene il ~9%
della letteratura: **e' sostanzialmente il risultato lordo**. Il pareggio cade
a ~0,32 punti tondi. Sopra quella soglia non resta niente.

Questo cambia il verdetto di BJ: non e' vero che l'ORB sull'S&P "non c'e'". Il
segnale c'e' ed e' stabile su 1.897 operazioni e due periodi separati. E'
**della stessa taglia dei costi di esecuzione**, ed e' un'altra cosa.

### Ipotesi A: i pattern selezionano? Solo NR4, e non abbastanza

Lordo, uscita a fine sessione:

| | ricerca | verifica |
|---|---|---|
| tutti | +0,060 | +0,042 |
| **NR4** | **+0,116** | **+0,082** |
| NR7 | +0,093 | −0,014 |
| ID | +0,017 | −0,028 |
| ID/NR4 | +0,087 | −0,088 |

NR4 **raddoppia** il vantaggio lordo e lo fa in entrambi i periodi. Gli altri
tre funzionano in ricerca e crollano in verifica: sono rumore. Netto 0,35 NR4
resta +0,056 / +0,033 (65 operazioni l'anno, ~3,5% e ~2,2% annuo all'1%).

**Ma il placebo non lo assolve.** Cinquemila selezioni casuali della stessa
numerosita': NR4 batte solo il **79,7%** dei casuali in ricerca e il **71,2%**
in verifica. Tradotto: una selezione a caso di 250 giorni fa altrettanto bene
una volta su quattro. E anno per anno NR4 fa **5 positivi su 9**, con il 2011
(+16,4 R) che da solo vale piu' di tutto il resto messo insieme.

Verdetto onesto: NR4 punta nella direzione giusta — la contrazione precede
l'espansione, il gross raddoppia, e questo e' coerente su due periodi — ma
**non e' distinguibile dal caso** con questa numerosita'. Su quattro pattern
provati, uno sopravvive: e' esattamente cio' che ci si aspetta pescando.

### Ipotesi C: l'obiettivo 1:1 (proposta dell'utente) e' peggio

Costo 0,35, verifica: tutti i giorni **−0,049 R/op con 1:1** contro −0,007 con
uscita a fine sessione; NR4 **−0,055 con 1:1** contro +0,033. Zero anni
positivi su quattro per l'1:1 in verifica, su ogni selezione.

Conferma quello che dice la letteratura accademica: l'ORB e' una scommessa sul
**momentum che prosegue fino alla chiusura**, non una regola a bersaglio.
Tagliare a 1:1 elimina la coda lunga che paga tutte le perdite. Ipotesi C
confermata, proposta 1:1 respinta.

### Conclusione, corretta rispetto a BJ

1. **L'ORB sull'S&P 500 e' reale in lordo** (+0,05 R/op su 1.897 operazioni,
   stabile sui due periodi) e vale ~10-14% annuo all'1% di rischio. Il ~9%
   della letteratura non e' un errore: e' quel numero.
2. **Ma e' interamente dentro i costi.** Pareggio a 0,32 punti tondi. Sopra,
   zero; a 0,50, perdita netta. Un bot su questo non ha margine di sicurezza:
   basta un tick di slittamento sugli ordini stop per azzerarlo.
3. **I pattern di Crabel non lo salvano in modo dimostrabile.** Solo NR4
   sopravvive ai due periodi, ma non batte il caso e dipende da un anno.
4. Se si vuole insistere, la strada NON e' un altro filtro: e' **abbassare il
   costo in rapporto al rischio**. Due modi soli: uno strumento con Stretch
   piu' largo a parita' di spread, oppure entrare in limite invece che in stop
   (Crabel operava nel mercato a voce, dove la microstruttura era un'altra).
   Sono ipotesi da misurare, non conclusioni.
