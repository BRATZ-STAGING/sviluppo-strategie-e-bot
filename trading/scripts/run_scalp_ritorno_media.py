#!/usr/bin/env python3
"""Scalp XAUUSD: ritorno alla media di brevissimo periodo. Ricerca da ZERO.

Si riparte dal prezzo grezzo. NIENTE order block, NIENTE reclaim del VWAP,
NIENTE allineamento di struttura multi-timeframe: sono cose gia' misurate in
questo progetto e qui non entrano. L'unica domanda e': dopo un allungo veloce
il prezzo torna indietro abbastanza da pagare uno scalp?

IPOTESI PRE-REGISTRATE (tutte scritte PRIMA di guardare i risultati, tutte
riportate dopo, anche quelle che perdono).

  1) STREAK: N candele M1 consecutive nella stessa direzione (close>open per
     salita, close<open per discesa), con N = 4, 6, 8. Si entra CONTRO: dopo
     N candele in salita si vende, dopo N in discesa si compra.
  2) SPIKE: una candela con escursione (high-low) superiore a K volte il
     "respiro recente", con K = 3 e 5, sia su M1 sia su M3. Si entra CONTRO il
     corpo della candela (candela verde -> short, candela rossa -> long).
     Respiro recente = media dell'escursione delle ultime 30 candele dello
     stesso timeframe, con .shift(1) (la candela del segnale NON entra nella
     sua stessa soglia).
  3) BANDA: distanza della chiusura M5 dalla sua media mobile a 20 periodi
     superiore a K deviazioni standard (20 periodi), con K = 2 e 3. Media e
     deviazione calcolate con .shift(1), quindi su dati fino alla candela
     precedente. Sopra la banda -> short, sotto -> long.
  4) COMBO: 1 e 3 insieme e nella stessa direzione (allungo veloce E lontano
     dalla media): streak M1 >= 4 con |z| >= 2, e streak M1 >= 6 con |z| >= 2,
     dove z e' lo z-score della banda M5 disponibile all'ultima candela M5
     GIA' CHIUSA (portato su M1 con ffill: nessun lookahead).

  In totale 11 varianti di segnale: streak4, streak6, streak8, spikeM1_k3,
  spikeM1_k5, spikeM3_k3, spikeM3_k5, banda_k2, banda_k3, combo4_z2,
  combo6_z2.

IL VINCOLO ARITMETICO (e' questo che decide tutto, va letto prima dei numeri).
Lo spread vero dell'oro misurato su 6,1 milioni di tick e' 0,33 $ fino al 2024
e 0,63 $ dal 2025. Costo per operazione, in frazione del rischio:

    stop 3 $  ->  0,33/3 = 11% di R  fino al 2024,  0,63/3 = 21% dal 2025
    stop 5 $  ->  0,33/5 =  7% di R  fino al 2024,  0,63/5 = 13% dal 2025

Quindi il vantaggio LORDO deve superare 0,10-0,20 R/op, altrimenti lo scalp
NON esiste: non e' una questione di ottimizzare, e' aritmetica. Lordo e netto
sono sempre riportati separati, insieme al costo in %R.
Spread per anno usati (dollari):
  2020 0,350  2021 0,349  2022 0,395  2023 0,334  2024 0,384  2025 0,632
  2026 0,631
Il costo e' sottratto una volta per operazione (giro completo): i prezzi sono
BID, si compra a BID+spread e si vende a BID, quindi costo_R = spread/stop.

PROTOCOLLO.
- Periodo: 2020-2026. RICERCA 2020-2022, VERIFICA 2023-2026. Entrambi sempre
  riportati, nessuna scelta fatta guardando la verifica.
- 6 celle di gestione (il massimo consentito): stop 3 $ con obiettivo 1:1,5 e
  1:2; stop 5 $ con 1:1,5 e 1:2; stop pari a 1,5 volte il respiro M1 (media
  escursione ultime 30 candele M1, .shift(1)) con 1:1,5 e 1:2.
- NIENTE lookahead: ogni media/deviazione/respiro con .shift(1); la decisione
  si prende alla CHIUSURA della candela di segnale, l'ingresso al prezzo di
  APERTURA della candela M1 successiva.
- A parita' di minuto lo STOP prevale sull'obiettivo (ipotesi conservativa).
- Uscita a tempo dopo 120 minuti se non e' stato toccato nulla: si chiude alla
  chiusura della candela e il risultato e' (uscita-ingresso)/stop.
- Filtri operativi: solo ingressi fra le 07:00 e le 21:00 UTC, almeno 15
  minuti fra un ingresso e il successivo, massimo 5 operazioni per giorno.
  Il filtro e' applicato alla lista dei segnali, quindi le 6 celle di
  gestione lavorano tutte sulle STESSE operazioni.

PLACEBO OBBLIGATORIO. Per ogni variante si costruisce un gemello finto: stesso
numero di operazioni, STESSI orari di ingresso, stessa gestione, ma direzione
tirata a caso (seme fisso 20260804). Se il placebo va come le ipotesi vere,
allora quello che si misura e' la forma della gestione e non un vantaggio del
segnale: nelle appendici BP, BU, BV, BY di questo progetto il placebo ha gia'
battuto TUTTE le ipotesi vere, e se succede ancora va detto e basta.

CONTROLLO DI ASSURDITA'. Con obiettivo lontano (1:2) e stop vicino, lo stop
deve essere colpito piu' spesso dell'obiettivo. Se non e' cosi' il motore e'
rotto e i numeri non valgono nulla: viene stampato il confronto.

Uso: python3 run_scalp_ritorno_media.py [out.parquet]
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1, resample  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ANNI = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
RICERCA = (2020, 2022)
VERIFICA = (2023, 2026)
SPREAD = {2020: 0.35, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}

ORA_MIN, ORA_MAX = 7, 21          # ingressi ammessi in [07:00, 21:00) UTC
PAUSA_MIN = 15                    # minuti minimi fra due ingressi
MAX_GIORNO = 5                    # operazioni per giorno
ORIZZONTE = 120                   # minuti massimi in posizione
RESPIRO_N = 30                    # candele per il respiro
SEME = 20260804

# 6 celle di gestione: (etichetta, tipo stop, valore, obiettivo in R)
CELLE = [
    ("3r15", "fisso", 3.0, 1.5), ("3r20", "fisso", 3.0, 2.0),
    ("5r15", "fisso", 5.0, 1.5), ("5r20", "fisso", 5.0, 2.0),
    ("Br15", "respiro", 1.5, 1.5), ("Br20", "respiro", 1.5, 2.0),
]


def filtra(idx_seg, dir_seg, ts_seg):
    """Applica orario, pausa minima e tetto giornaliero alla lista dei segnali."""
    ok_ora = (ts_seg.hour >= ORA_MIN) & (ts_seg.hour < ORA_MAX)
    idx_seg, dir_seg, ts_seg = idx_seg[ok_ora], dir_seg[ok_ora], ts_seg[ok_ora]
    minuti = ts_seg.asi8 // 60_000_000_000
    giorni = ts_seg.normalize().asi8
    tieni = np.zeros(len(idx_seg), dtype=bool)
    ultimo, giorno_cur, quanti = -10**9, -1, 0
    for i in range(len(idx_seg)):
        if giorni[i] != giorno_cur:
            giorno_cur, quanti = giorni[i], 0
        if quanti >= MAX_GIORNO or minuti[i] - ultimo < PAUSA_MIN:
            continue
        tieni[i] = True
        ultimo, quanti = minuti[i], quanti + 1
    return idx_seg[tieni], dir_seg[tieni], ts_seg[tieni]


def simula(op, hi, lo, cl, ts_ns, stop_d, rr):
    """Barriere vettorizzate su una finestra di ORIZZONTE candele M1.

    Ritorna (lordo in R, esito) con esito 0=stop, 1=obiettivo, 2=tempo.
    Lo stop prevale sull'obiettivo nello stesso minuto.
    """
    n = len(op["idx"])
    if n == 0:
        return np.zeros(0), np.zeros(0, dtype=np.int8)
    pos = op["idx"][:, None] + np.arange(ORIZZONTE)[None, :]
    pos = np.minimum(pos, len(cl) - 1)
    H, L, C, T = hi[pos], lo[pos], cl[pos], ts_ns[pos]
    # una candela e' valida se e' entro ORIZZONTE minuti dall'ingresso
    valida = (T - ts_ns[op["idx"]][:, None]) <= ORIZZONTE * 60_000_000_000
    d = op["dir"][:, None]
    entry = op["entry"][:, None]
    sd = stop_d[:, None]
    liv_stop = entry - d * sd
    liv_tgt = entry + d * sd * rr
    colpo_stop = np.where(d == 1, L <= liv_stop, H >= liv_stop) & valida
    colpo_tgt = np.where(d == 1, H >= liv_tgt, L <= liv_tgt) & valida
    i_stop = np.where(colpo_stop.any(1), colpo_stop.argmax(1), ORIZZONTE + 1)
    i_tgt = np.where(colpo_tgt.any(1), colpo_tgt.argmax(1), ORIZZONTE + 1)
    ultimo = valida.shape[1] - 1 - valida[:, ::-1].argmax(1)
    uscita_tempo = C[np.arange(n), ultimo]
    lordo = op["dir"] * (uscita_tempo - op["entry"]) / stop_d
    esito = np.full(n, 2, dtype=np.int8)
    fa_tgt = (i_tgt < i_stop) & (i_tgt <= ORIZZONTE)
    fa_stop = (i_stop <= i_tgt) & (i_stop <= ORIZZONTE)
    lordo = np.where(fa_stop, -1.0, np.where(fa_tgt, rr, lordo))
    esito = np.where(fa_stop, 0, np.where(fa_tgt, 1, 2)).astype(np.int8)
    return lordo, esito


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "docs", "studies", "dati", "scalp_ritorno_media.parquet")
    pd.set_option("display.width", 230)
    pd.set_option("display.max_columns", 60)

    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"), years=ANNI)
    # i Parquet hanno risoluzione in millisecondi: si porta tutto a nanosecondi
    # una volta sola, altrimenti ogni conto sui timestamp e' sbagliato di 10^6
    m1.index = m1.index.as_unit("ns")
    op_, hi, lo, cl = (m1.open.to_numpy(), m1.high.to_numpy(),
                       m1.low.to_numpy(), m1.close.to_numpy())
    ts = m1.index
    ts_ns = ts.asi8
    n_m1 = len(m1)

    rng_m1 = m1.high - m1.low
    respiro = rng_m1.rolling(RESPIRO_N).mean().shift(1)
    respiro_np = respiro.to_numpy()

    # --- ipotesi 1: streak di candele M1 nella stessa direzione ---------
    su = (m1.close > m1.open).to_numpy()
    giu = (m1.close < m1.open).to_numpy()
    streak_su = np.zeros(n_m1, dtype=np.int32)
    streak_giu = np.zeros(n_m1, dtype=np.int32)
    for i in range(1, n_m1):
        streak_su[i] = streak_su[i - 1] + 1 if su[i] else 0
        streak_giu[i] = streak_giu[i - 1] + 1 if giu[i] else 0
    streak_su[0] = 1 if su[0] else 0
    streak_giu[0] = 1 if giu[0] else 0

    # --- ipotesi 3: banda M5 (media 20 e deviazione 20, con shift(1)) ----
    m5 = resample(m1, "5min")
    med5 = m5.close.rolling(20).mean().shift(1)
    dev5 = m5.close.rolling(20).std().shift(1)
    z5 = (m5.close - med5) / dev5
    # lo z e' noto alla CHIUSURA della candela M5, cioe' 5 minuti dopo l'apertura
    z5_noto = pd.Series(z5.to_numpy(), index=m5.index + pd.Timedelta("5min"))
    z_su_m1 = z5_noto.reindex(ts, method="ffill").to_numpy()

    segnali = {}

    def aggiungi(nome, mask_short, mask_long, idx_dec):
        """idx_dec = posizione M1 della candela di DECISIONE; ingresso a idx+1."""
        d = np.where(mask_short, -1, np.where(mask_long, 1, 0))
        sel = (d != 0) & (idx_dec + 1 < n_m1)
        i_dec = idx_dec[sel]
        i_ing = i_dec + 1
        dd = d[sel]
        ok = np.isfinite(respiro_np[i_dec]) & (respiro_np[i_dec] > 0)
        i_dec, i_ing, dd = i_dec[ok], i_ing[ok], dd[ok]
        i_dec, dd_f, ts_f = filtra(i_dec, dd, ts[i_ing])
        segnali[nome] = {"dec": i_dec, "idx": i_dec + 1, "dir": dd_f,
                         "entry": op_[i_dec + 1], "ts": ts_f}

    tutti = np.arange(n_m1)
    for N in (4, 6, 8):
        aggiungi(f"streak{N}", streak_su >= N, streak_giu >= N, tutti)

    for K in (3, 5):
        grande = rng_m1.to_numpy() > K * respiro_np
        aggiungi(f"spikeM1_k{K}", grande & su, grande & giu, tutti)

    m3 = resample(m1, "3min")
    rng_m3 = (m3.high - m3.low)
    respiro3 = rng_m3.rolling(RESPIRO_N).mean().shift(1)
    su3 = (m3.close > m3.open).to_numpy()
    giu3 = (m3.close < m3.open).to_numpy()
    # decisione alla chiusura M3 = apertura + 3 minuti; posizione M1 corrispondente
    chiusura_m3 = m3.index + pd.Timedelta("3min")
    pos_m3 = ts.get_indexer(chiusura_m3, method=None)
    valido3 = pos_m3 > 0
    for K in (3, 5):
        g3 = (rng_m3.to_numpy() > K * respiro3.to_numpy()) & valido3
        # la candela di decisione M1 e' quella PRIMA della riapertura
        aggiungi(f"spikeM3_k{K}", (g3 & su3)[valido3], (g3 & giu3)[valido3],
                 pos_m3[valido3] - 1)

    pos_m5 = ts.get_indexer(m5.index + pd.Timedelta("5min"))
    valido5 = pos_m5 > 0
    z_dec = z5.to_numpy()[valido5]
    for K in (2, 3):
        aggiungi(f"banda_k{K}", z_dec > K, z_dec < -K, pos_m5[valido5] - 1)

    for N in (4, 6):
        aggiungi(f"combo{N}_z2", (streak_su >= N) & (z_su_m1 >= 2),
                 (streak_giu >= N) & (z_su_m1 <= -2), tutti)

    # ------------------------------------------------------------------
    righe = []
    rs = np.random.default_rng(SEME)
    for nome, s in segnali.items():
        if len(s["idx"]) == 0:
            continue
        anni = s["ts"].year.to_numpy()
        spread = np.array([SPREAD[a] for a in anni])
        dir_fake = rs.choice([-1, 1], size=len(s["idx"]))
        for et, tipo, val, rr in CELLE:
            stop_d = (np.full(len(s["idx"]), val) if tipo == "fisso"
                      else val * respiro_np[s["dec"]])
            for vero, dd in ((1, s["dir"]), (0, dir_fake)):
                opz = {"idx": s["idx"], "dir": dd, "entry": s["entry"]}
                lordo, esito = simula(opz, hi, lo, cl, ts_ns, stop_d, rr)
                costo = spread / stop_d
                righe.append(pd.DataFrame({
                    "spec": nome, "cella": et, "vero": vero,
                    "ts": s["ts"], "anno": anni, "dir": dd,
                    "stop_d": stop_d, "rr": rr, "lordo": lordo,
                    "costo_r": costo, "netto": lordo - costo, "esito": esito,
                }))
    det = pd.concat(righe, ignore_index=True)
    det["periodo"] = np.where(det.anno <= RICERCA[1], "ric", "ver")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    det.to_parquet(out, index=False)

    # ------------------------ stampa compatta --------------------------
    ordine = [c[0] for c in CELLE]
    specs = list(segnali.keys())
    v = det[det.vero == 1]
    pl = det[det.vero == 0]

    n_op = v[v.cella == "3r15"].groupby(["spec", "periodo"]).size().unstack()
    n_op = n_op.reindex(specs)

    def piv(d, col):
        p = d.pivot_table(index="spec", columns=["periodo", "cella"],
                          values=col, aggfunc="mean")
        return p.reindex(index=specs,
                         columns=pd.MultiIndex.from_product([["ric", "ver"], ordine]))

    print("SCALP RITORNO ALLA MEDIA - XAUUSD 2020-2026 | ric=2020-22 ver=2023-26")
    cst = det.groupby(["periodo", "cella"]).costo_r.mean().unstack()[ordine]
    print("costo dello spread in frazione di R (media):")
    print(cst.round(3).to_string())
    lordo_t = piv(v, "lordo").round(3)
    lordo_t.insert(0, ("n", "ric"), n_op["ric"])
    lordo_t.insert(1, ("n", "ver"), n_op["ver"])
    print("\nLORDO R/op (nessun costo) - celle: stop 3/5/Respiro x obiettivo 1:1,5 e 1:2")
    print(lordo_t.to_string())
    print("\nNETTO R/op (lordo meno spread)")
    print(piv(v, "netto").round(3).to_string())
    plp = piv(pl, "lordo")
    print("\nPLACEBO lordo R/op (stessi orari, direzione a caso): media e massimo per cella")
    print(pd.concat([plp.mean().rename("media"), plp.max().rename("max"),
                     piv(v, "lordo").mean().rename("vero_media")],
                    axis=1).T.round(3).to_string())

    # celle che superano la soglia richiesta in ENTRAMBI i periodi
    lo_ = piv(v, "lordo")
    passa = [(sp, ce) for sp in specs for ce in ordine
             if lo_.loc[sp, ("ric", ce)] > 0.15 and lo_.loc[sp, ("ver", ce)] > 0.15]
    ne_ = piv(v, "netto")
    passa_net = [(sp, ce) for sp in specs for ce in ordine
                 if ne_.loc[sp, ("ric", ce)] > 0 and ne_.loc[sp, ("ver", ce)] > 0]
    print(f"\ncelle con LORDO > 0,15 R/op in ENTRAMBI i periodi: {len(passa)} {passa[:6]}")
    print(f"celle con NETTO > 0 in ENTRAMBI i periodi: {len(passa_net)} {passa_net[:6]}")
    diff = (lo_ - piv(pl, "lordo"))
    batte = int(((diff[("ric",)] > 0).sum().sum()) + ((diff[("ver",)] > 0).sum().sum()))
    print(f"celle (su {len(specs) * len(ordine) * 2}) in cui il VERO batte il placebo: {batte}")
    print(f"placebo lordo R/op medio: ric {pl[pl.periodo == 'ric'].lordo.mean():.3f} "
          f"ver {pl[pl.periodo == 'ver'].lordo.mean():.3f} | "
          f"vero: ric {v[v.periodo == 'ric'].lordo.mean():.3f} "
          f"ver {v[v.periodo == 'ver'].lordo.mean():.3f}")

    # il vantaggio lordo migliore vale qualcosa? errore standard e anni positivi
    mig = v.groupby(["spec", "cella"]).lordo.mean().idxmax()
    b = v[(v.spec == mig[0]) & (v.cella == mig[1])]
    anni_pos = int((b.groupby("anno").lordo.mean() > 0).sum())
    print(f"\nmigliore cella per lordo: {mig[0]} {mig[1]} -> {b.lordo.mean():.3f} "
          f"+/- {b.lordo.std() / np.sqrt(len(b)):.3f} R/op (n={len(b)}), "
          f"anni positivi {anni_pos}/7, netto {b.netto.mean():.3f}")

    ass = v[v.rr == 2.0].groupby("cella").esito.value_counts(normalize=True).unstack()
    ass.columns = ["stop", "obiettivo", "tempo"][:ass.shape[1]]
    print("\nCONTROLLO DI ASSURDITA' (obiettivo 1:2): quota esiti")
    print(ass.round(3).to_string())
    print(f"stop piu' frequente dell'obiettivo in tutte le celle 1:2: "
          f"{bool((ass['stop'] > ass['obiettivo']).all())}")
    print(f"\ndettaglio: {out} ({len(det)} righe)")


if __name__ == "__main__":
    main()
