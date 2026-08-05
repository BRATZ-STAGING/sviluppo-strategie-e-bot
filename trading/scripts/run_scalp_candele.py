#!/usr/bin/env python3
"""Scalp XAUUSD dal grafico pulito: FORMA DELLE CANDELE e VOLUME.

Ripartenza da zero. Niente order block, niente reclaim del VWAP, niente
struttura multi-timeframe: solo la roba piu' classica del mondo, quella che in
questo progetto non e' mai stata misurata. Tutte le ipotesi sono scritte qui
PRIMA di guardare i risultati, e vengono riportate TUTTE, anche quelle che
fanno schifo.

=====================================================================
IPOTESI PRE-REGISTRATE (cinque famiglie, sedici combinazioni)
=====================================================================
1. CANDELA DI INVERSIONE (pin bar), su M3, M5, M15.
   corpo  = |chiusura - apertura|
   ombra superiore = massimo - max(apertura, chiusura)
   ombra inferiore = min(apertura, chiusura) - minimo
   pin rialzista: ombra inferiore > 2 x corpo E > ombra superiore -> LUNGO
   pin ribassista: ombra superiore > 2 x corpo E > ombra inferiore -> CORTO
   Si richiede corpo > 0 (altrimenti la doji perfetta soddisfa "> 2 x 0"
   sempre e la famiglia diventa un contatore di doji).

2. INGLOBANTE (engulfing), su M3, M5, M15.
   Il corpo della candela i copre INTERAMENTE il corpo della i-1
   (min corpo i <= min corpo i-1 E max corpo i >= max corpo i-1) e i due
   corpi hanno verso opposto. Verso dell'operazione = verso del corpo i.

3. INSIDE BAR seguita da ROTTURA, su M5, M15.
   Candela i interna alla i-1 (massimo i <= massimo i-1, minimo i >= minimo
   i-1). La candela i+1 chiude sopra il massimo della interna -> LUNGO,
   chiude sotto il minimo -> CORTO. Il segnale nasce alla CHIUSURA di i+1.

4. PICCO DI VOLUME, su M3, M5, M15, con K = 3 e K = 5.
   volume(i) > K x mediana dei volumi delle 60 candele PRECEDENTI dello
   stesso timeframe (rolling(60).median().shift(1): la mediana non vede
   mai la candela che sta giudicando). Verso = verso del corpo della
   candela i; corpo nullo -> segnale scartato.

5. DIVERGENZA VOLUME/MOVIMENTO, su M5, M15.
   Nuovo massimo a 20 candele con volume MINORE del volume registrato sul
   precedente nuovo massimo a 20 candele -> CORTO (spinta che si esaurisce).
   Simmetrico sui minimi -> LUNGO.

SUL VOLUME: il campo ``volume`` dell'archivio Dukascopy NON e' volume
scambiato, e' un conteggio di tick (quante quotazioni sono arrivate nel
minuto). E' informazione reale ma indiretta: dice quanta attivita' c'e'
stata, non quanti contratti sono passati. Per questo va usata solo in modo
RELATIVO — rapporti fra una candela e la mediana recente, confronti fra due
estremi — e mai come livello assoluto. Tutte le ipotesi 4 e 5 sono scritte
come rapporti proprio per questo.

=====================================================================
IL VINCOLO ARITMETICO (decide tutto, scritto prima di misurare)
=====================================================================
Lo spread vero dell'oro, misurato su 6,1 milioni di tick di questo archivio,
e' 0,33 $ fino al 2024 e 0,63 $ dal 2025. Con uno stop di 3 $ il costo di
andata e ritorno vale 0,11-0,21 R per operazione; con uno stop di 5 $ vale
0,07-0,13 R. Quindi:

    IL VANTAGGIO LORDO DEVE SUPERARE 0,10-0,20 R/OPERAZIONE
    O LO SCALP NON ESISTE.

Un pattern che rende +0,05 R/op lordo non e' "quasi buono": e' una perdita.
Lordo e netto sono sempre riportati separati, e il costo in %R e' stampato
accanto, cosi' non si puo' barare con se stessi.

Spread applicato per anno (dollari, dalla misura sui tick):
  2020 0,350 | 2021 0,349 | 2022 0,395 | 2023 0,334
  2024 0,384 | 2025 0,632 | 2026 0,631

=====================================================================
PROTOCOLLO
=====================================================================
- Periodo: 2020-2026 (XAU_ANNI=2020-2026). RICERCA 2020-2022,
  VERIFICA 2023-2026. Entrambe sempre riportate, mai una sola.
- NIENTE LOOKAHEAD: il pattern si riconosce alla CHIUSURA della candela di
  segnale; l'ingresso e' all'APERTURA della candela successiva (in pratica
  il primo minuto M1 che comincia dopo la chiusura del segnale). Le mediane
  mobili del volume sono .shift(1).
- Sei celle di gestione, non una di piu':
    stop 3 $  x obiettivo 1:1,5 e 1:2
    stop 5 $  x obiettivo 1:1,5 e 1:2
    stop oltre l'estremo della candela di segnale (+0,30 $ di cuscinetto)
              x obiettivo 1:1,5 e 1:2
  Sullo stop strutturale si accettano solo rischi fra 0,5 $ e 15 $.
- A parita' di minuto lo STOP prevale sull'obiettivo (conservativo).
- Simulazione minuto per minuto su M1; chiusura forzata alle 21:00 UTC al
  prezzo di chiusura del minuto (nessuna posizione tenuta di notte).
- Limiti operativi: massimo 5 operazioni al giorno per famiglia, almeno 15
  minuti fra un ingresso e il successivo, ingressi solo fra le 07:00 e le
  21:00 UTC.
- SCELTA DELLA CELLA: per ogni famiglia si sceglie la cella col LORDO
  migliore sul solo periodo di RICERCA, e si riporta il periodo di VERIFICA
  come esce. Regola dichiarata prima: nessuna cella scelta col senno di poi.

PLACEBO: per ogni famiglia si costruisce un gemello finto con lo stesso
numero di operazioni negli stessi giorni, ingressi a minuti CASUALI dentro
la stessa finestra 07:00-21:00, VERSO CASUALE, stessi stop, stessi
obiettivi, stessi limiti, stesso seme fisso. Nelle appendici BP, BU, BV, BY
di questo progetto il placebo ha battuto tutte le ipotesi vere: se succede
di nuovo, quello E' il risultato e va detto.

CONTROLLO DI ASSURDITA': con stop 3 $ e obiettivo 1:2 la distanza dello
stop e' la meta' di quella dell'obiettivo, quindi lo stop DEVE essere
colpito piu' spesso. Se una cella mostra il contrario c'e' un bug, e viene
stampato a schermo.

Uso: XAU_ANNI=2020-2026 python3 run_scalp_candele.py
Salva: docs/studies/dati/scalp_candele.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1, resample                      # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "docs", "studies", "dati", "scalp_candele.parquet")

SPREAD = {2020: 0.350, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}
RICERCA = (2020, 2022)
VERIFICA = (2023, 2026)
ORA_DA, ORA_A = 7, 21
MAX_AL_GIORNO = 5
PAUSA_MIN = 15
BUFFER = 0.30
RISCHIO_MIN, RISCHIO_MAX = 0.5, 15.0
SEME = 20260804

# (nome, rischio fisso in $ o None per strutturale, obiettivo in R)
CELLE = [("s3_r15", 3.0, 1.5), ("s3_r20", 3.0, 2.0),
         ("s5_r15", 5.0, 1.5), ("s5_r20", 5.0, 2.0),
         ("est_r15", None, 1.5), ("est_r20", None, 2.0)]

TF_RULE = {"M3": "3min", "M5": "5min", "M15": "15min"}
TF_MIN = {"M3": 3, "M5": 5, "M15": 15}


# ---------------------------------------------------------------- segnali
def seg_pin(tf: pd.DataFrame) -> np.ndarray:
    o, h, l, c = tf.open.values, tf.high.values, tf.low.values, tf.close.values
    corpo = np.abs(c - o)
    sup = h - np.maximum(o, c)
    inf = np.minimum(o, c) - l
    d = np.zeros(len(tf), dtype=np.int8)
    d[(corpo > 0) & (inf > 2 * corpo) & (inf > sup)] = 1
    d[(corpo > 0) & (sup > 2 * corpo) & (sup > inf)] = -1
    return d


def seg_engulf(tf: pd.DataFrame) -> np.ndarray:
    o, c = tf.open.values, tf.close.values
    bmin, bmax = np.minimum(o, c), np.maximum(o, c)
    d = np.zeros(len(tf), dtype=np.int8)
    copre = np.zeros(len(tf), dtype=bool)
    copre[1:] = (bmin[1:] <= bmin[:-1]) & (bmax[1:] >= bmax[:-1])
    su = np.zeros(len(tf), dtype=bool)
    giu = np.zeros(len(tf), dtype=bool)
    su[1:] = (c[1:] > o[1:]) & (c[:-1] < o[:-1])
    giu[1:] = (c[1:] < o[1:]) & (c[:-1] > o[:-1])
    d[copre & su] = 1
    d[copre & giu] = -1
    return d


def seg_inside(tf: pd.DataFrame) -> np.ndarray:
    """Segnale sulla candela di ROTTURA (i+1): chiude fuori dalla interna."""
    h, l, c = tf.high.values, tf.low.values, tf.close.values
    d = np.zeros(len(tf), dtype=np.int8)
    interna = np.zeros(len(tf), dtype=bool)
    interna[1:] = (h[1:] <= h[:-1]) & (l[1:] >= l[:-1])
    # la rottura e' la candela successiva alla interna
    rot = np.zeros(len(tf), dtype=bool)
    rot[1:] = interna[:-1]
    su = np.zeros(len(tf), dtype=bool)
    giu = np.zeros(len(tf), dtype=bool)
    su[1:] = c[1:] > h[:-1]
    giu[1:] = c[1:] < l[:-1]
    d[rot & su] = 1
    d[rot & giu] = -1
    return d


def seg_volume(tf: pd.DataFrame, k: float) -> np.ndarray:
    v = tf.volume
    med = v.rolling(60).median().shift(1)
    o, c = tf.open.values, tf.close.values
    picco = (v.values > k * med.values) & np.isfinite(med.values)
    d = np.zeros(len(tf), dtype=np.int8)
    d[picco & (c > o)] = 1
    d[picco & (c < o)] = -1
    return d


def seg_divergenza(tf: pd.DataFrame, n: int = 20) -> np.ndarray:
    """Nuovo estremo a n candele con volume minore del precedente estremo."""
    h, l, v = tf.high.values, tf.low.values, tf.volume.values
    maxprec = pd.Series(h).rolling(n).max().shift(1).values
    minprec = pd.Series(l).rolling(n).min().shift(1).values
    nuovo_max = np.isfinite(maxprec) & (h > maxprec)
    nuovo_min = np.isfinite(minprec) & (l < minprec)
    d = np.zeros(len(tf), dtype=np.int8)
    v_prec_max = v_prec_min = np.nan
    for i in range(len(tf)):
        if nuovo_max[i]:
            if np.isfinite(v_prec_max) and v[i] < v_prec_max:
                d[i] = -1
            v_prec_max = v[i]
        if nuovo_min[i]:
            if np.isfinite(v_prec_min) and v[i] < v_prec_min:
                d[i] = 1
            v_prec_min = v[i]
    return d


FAMIGLIE = []
for _tf in ("M3", "M5", "M15"):
    FAMIGLIE.append((f"pin_{_tf}", _tf, seg_pin))
for _tf in ("M3", "M5", "M15"):
    FAMIGLIE.append((f"engulf_{_tf}", _tf, seg_engulf))
for _tf in ("M5", "M15"):
    FAMIGLIE.append((f"inside_{_tf}", _tf, seg_inside))
for _k in (3, 5):
    for _tf in ("M3", "M5", "M15"):
        FAMIGLIE.append((f"volK{_k}_{_tf}", _tf,
                         (lambda k: lambda t: seg_volume(t, k))(_k)))
for _tf in ("M5", "M15"):
    FAMIGLIE.append((f"diverg_{_tf}", _tf, seg_divergenza))


# ------------------------------------------------------------- simulazione
def prepara_m1(m1: pd.DataFrame):
    idx = m1.index.values.astype("datetime64[ns]")
    fine = {}
    giorno = m1.index.normalize()
    stop21 = (giorno + pd.Timedelta(hours=ORA_A)).values.astype("datetime64[ns]")
    fine_i = np.searchsorted(idx, stop21, side="left")
    return (idx, m1.open.values, m1.high.values, m1.low.values,
            m1.close.values, fine_i, fine)


def simula(op, hi, lo, cl, ei, direzione, rischio, rr, fine_i):
    """R lordo e motivo (0=stop, 1=obiettivo, 2=fine giornata)."""
    entry = op[ei]
    b = max(int(fine_i[ei]), ei + 1)
    if direzione > 0:
        stop, tgt = entry - rischio, entry + rr * rischio
        s = lo[ei:b] <= stop
        t = hi[ei:b] >= tgt
    else:
        stop, tgt = entry + rischio, entry - rr * rischio
        s = hi[ei:b] >= stop
        t = lo[ei:b] <= tgt
    i_s = int(np.argmax(s)) if s.any() else -1
    i_t = int(np.argmax(t)) if t.any() else -1
    if i_s >= 0 and (i_t < 0 or i_s <= i_t):
        return -1.0, 0
    if i_t >= 0:
        return rr, 1
    return direzione * (cl[b - 1] - entry) / rischio, 2


def filtra(ingressi):
    """Applica finestra oraria, pausa minima e massimo giornaliero."""
    out = []
    ultimo = None
    contatore = {}
    for ts, ei, direz, est in ingressi:
        if not (ORA_DA <= ts.hour < ORA_A):
            continue
        if ultimo is not None and (ts - ultimo) < pd.Timedelta(minutes=PAUSA_MIN):
            continue
        g = ts.date()
        if contatore.get(g, 0) >= MAX_AL_GIORNO:
            continue
        contatore[g] = contatore.get(g, 0) + 1
        ultimo = ts
        out.append((ts, ei, direz, est))
    return out


def esegui(ingressi, m1v, etichetta, famiglia):
    idx, op, hi, lo, cl, fine_i, _ = m1v
    righe = []
    for nome, fisso, rr in CELLE:
        for ts, ei, direz, est in ingressi:
            if fisso is not None:
                rischio = fisso
            else:
                rischio = (op[ei] - est) if direz > 0 else (est - op[ei])
                rischio += BUFFER
                if not (RISCHIO_MIN <= rischio <= RISCHIO_MAX):
                    continue
            r, motivo = simula(op, hi, lo, cl, ei, direz, rischio, rr, fine_i)
            anno = ts.year
            righe.append((famiglia, etichetta, nome, anno, direz, rischio,
                          r, SPREAD[anno] / rischio, motivo))
    return righe


def main() -> None:
    pd.set_option("display.width", 200)
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    m1v = prepara_m1(m1)
    idx = m1v[0]
    rng = np.random.default_rng(SEME)

    tutte = []
    for famiglia, tf_nome, fn in FAMIGLIE:
        tf = resample(m1, TF_RULE[tf_nome])
        d = fn(tf)
        pos = np.flatnonzero(d != 0)
        if len(pos) == 0:
            continue
        chiusura = (tf.index[pos] + pd.Timedelta(minutes=TF_MIN[tf_nome]))
        ei = np.searchsorted(idx, chiusura.values.astype("datetime64[ns]"),
                             side="left")
        ok = ei < len(idx) - 1
        pos, ei = pos[ok], ei[ok]
        ts_e = pd.DatetimeIndex(idx[ei]).tz_localize("UTC")
        direz = d[pos]
        # estremo della candela di segnale, per lo stop strutturale
        est = np.where(direz > 0, tf.low.values[pos], tf.high.values[pos])
        ingressi = filtra(list(zip(ts_e, ei, direz, est)))
        if not ingressi:
            continue
        tutte += esegui(ingressi, m1v, "vero", famiglia)

        # ---- placebo: stessi giorni, stesso numero, minuti e verso a caso
        per_giorno = {}
        for ts, _, _, _ in ingressi:
            per_giorno[ts.normalize()] = per_giorno.get(ts.normalize(), 0) + 1
        fake = []
        for g, n in per_giorno.items():
            a = int(np.searchsorted(idx, (g + pd.Timedelta(hours=ORA_DA)).to_datetime64()))
            b = int(np.searchsorted(idx, (g + pd.Timedelta(hours=ORA_A)).to_datetime64()))
            if b - a < 60:
                continue
            scelti = np.sort(rng.choice(np.arange(a, b), size=min(n, b - a),
                                        replace=False))
            for j in scelti:
                dz = 1 if rng.random() < 0.5 else -1
                # estremo "di segnale" del placebo: l'ultima candela TF
                # gia' CHIUSA prima del minuto d'ingresso (niente lookahead:
                # la candela in corso non e' ancora nota)
                k = int(tf.index.searchsorted(pd.Timestamp(idx[j], tz="UTC"),
                                              side="right")) - 2
                k = max(k, 0)
                e = tf.low.values[k] if dz > 0 else tf.high.values[k]
                fake.append((pd.Timestamp(idx[j], tz="UTC"), j, dz, e))
        fake = filtra(sorted(fake))
        tutte += esegui(fake, m1v, "placebo", famiglia)

    df = pd.DataFrame(tutte, columns=["famiglia", "tipo", "cella", "anno",
                                      "verso", "rischio", "r_lordo",
                                      "costo_r", "motivo"])
    df["r_netto"] = df.r_lordo - df.costo_r
    df["periodo"] = np.where(df.anno <= RICERCA[1], "ricerca", "verifica")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_parquet(OUT, index=False)

    # ------------------------------------------------------------ sintesi
    g = df.groupby(["tipo", "famiglia", "cella", "periodo"]).agg(
        n=("r_lordo", "size"), lordo=("r_lordo", "mean"),
        netto=("r_netto", "mean"), costo=("costo_r", "mean")).reset_index()
    piv = g.pivot_table(index=["tipo", "famiglia", "cella"], columns="periodo",
                        values=["n", "lordo", "netto", "costo"])
    piv.columns = [f"{a}_{b[:3]}" for a, b in piv.columns]
    piv = piv.reset_index()

    vero = piv[piv.tipo == "vero"].copy()
    plac = piv[piv.tipo == "placebo"].set_index(["famiglia", "cella"])
    # cella scelta sul LORDO del periodo di ricerca (regola dichiarata prima)
    scelte = vero.sort_values("lordo_ric", ascending=False).groupby(
        "famiglia", as_index=False).head(1).sort_values("famiglia")
    scelte["pl_lor_ver"] = [
        plac.lordo_ver.get((f, c), np.nan)
        for f, c in zip(scelte.famiglia, scelte.cella)]
    tab = scelte[["famiglia", "cella", "n_ric", "lordo_ric", "n_ver",
                  "lordo_ver", "netto_ver", "costo_ver", "pl_lor_ver"]]
    tab.columns = ["famiglia", "cella", "n_ric", "lord_ric", "n_ver",
                   "lord_ver", "net_ver", "cost%R", "plac_ver"]
    tab = tab.copy()
    tab["cost%R"] = tab["cost%R"] * 100

    print(f"\n{'='*104}\nSCALP DA ZERO: forma delle candele e volume — "
          f"ricerca {RICERCA[0]}-{RICERCA[1]}, verifica {VERIFICA[0]}-{VERIFICA[1]}"
          f"\n{'='*104}")
    print("Cella scelta sul LORDO di ricerca; verifica riportata come esce. "
          "R/operazione, 3 decimali.")
    print(tab.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n-- tutte e sei le celle, aggregato su tutte le famiglie --")
    cel = df[df.tipo == "vero"].groupby(["cella", "periodo"]).agg(
        n=("r_lordo", "size"), lordo=("r_lordo", "mean"),
        netto=("r_netto", "mean")).reset_index()
    cp = cel.pivot_table(index="cella", columns="periodo",
                         values=["n", "lordo", "netto"])
    cp.columns = [f"{a}_{b[:3]}" for a, b in cp.columns]
    print(cp.to_string(float_format=lambda x: f"{x:.3f}"))

    print("\n-- placebo, stesse sei celle --")
    cpl = df[df.tipo == "placebo"].groupby(["cella", "periodo"]).agg(
        lordo=("r_lordo", "mean"), netto=("r_netto", "mean")).reset_index()
    cq = cpl.pivot_table(index="cella", columns="periodo",
                         values=["lordo", "netto"])
    cq.columns = [f"{a}_{b[:3]}" for a, b in cq.columns]
    print(cq.to_string(float_format=lambda x: f"{x:.3f}"))

    # ---------------------------------------- controllo di assurdita'
    v = df[df.tipo == "vero"]
    ass = v.groupby("cella").apply(
        lambda x: pd.Series({"stop%": (x.motivo == 0).mean() * 100,
                             "obiett%": (x.motivo == 1).mean() * 100,
                             "eod%": (x.motivo == 2).mean() * 100}),
        include_groups=False)
    print("\n-- controllo di assurdita' (lo stop vicino DEVE battere "
          "l'obiettivo lontano) --")
    print(ass.to_string(float_format=lambda x: f"{x:.1f}"))
    rotte = [c for c in ass.index if ass.loc[c, "stop%"] <= ass.loc[c, "obiett%"]]
    print("celle che violano il controllo:", rotte if rotte else "nessuna (ok)")

    # ------------------------------------------------------- verdetto
    soglia = 0.15
    passa = tab[(tab.lord_ric > soglia) & (tab.lord_ver > soglia)]
    print(f"\nfamiglie con LORDO > {soglia} R/op in ENTRAMBI i periodi: "
          f"{len(passa)} su {len(tab)}"
          + ("" if len(passa) == 0 else "\n" + passa.to_string(
              index=False, float_format=lambda x: f"{x:.3f}")))
    meglio = int((tab.plac_ver > tab.lord_ver).sum())
    print(f"famiglie in cui il PLACEBO batte il vero (lordo, verifica): "
          f"{meglio} su {len(tab)}")
    print(f"salvato: {OUT}  ({len(df):,} righe)")


if __name__ == "__main__":
    main()
