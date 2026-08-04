#!/usr/bin/env python3
"""Appendice BP: cercare la selezione nel dettaglio M1/M3 — cinque famiglie e un placebo.

Richiesta dell'utente: *"miglioriamo la selezione, ma dentro M3 ed M1 trova
nuovi livelli, altri tipi di conferme o indicatori"*.

IL PROBLEMA E' MISURATO, NON OPINABILE. L'appendice BM ha stabilito il conto
esatto: perche' uno scalp con stop di pochi dollari si paghi, il vantaggio
lordo dell'ingresso deve passare da **0,05 a oltre 0,20 R/op**. Non serve una
gestione migliore e non basta uno spread migliore: serve che l'ingresso scelga
meglio. Questo studio cerca quel fattore quattro.

METODO, e vale piu' delle famiglie stesse. Le operazioni sono quelle che gia'
ci sono (campione largo, gestione ufficiale invariata): cambia solo COSA si
tiene. Ogni famiglia produce una misura continua, si divide in terzi, e si
guarda il rendimento dei tre terzi su **due periodi separati** — 2020-2022 per
cercare, 2023-2026 per verificare. Una famiglia conta solo se l'ordine dei
terzi si ripete nel secondo periodo. Riportate tutte le celle: non si sceglie
niente dopo aver guardato.

E c'e' un **placebo**: un numero casuale trattato esattamente come le altre
famiglie. Serve a sapere quanta separazione fra i terzi nasce dal nulla con
questo numero di operazioni. In questo progetto il placebo ha gia' smascherato
quattro risultati spettacolari e sbagliati; una famiglia che non lo batte non
e' una scoperta.

LE CINQUE FAMIGLIE, ciascuna con il suo perche':

1. VOLUME RELATIVO — il volume dei 15 minuti dell'impulso contro la mediana
   della STESSA ora nei 20 giorni precedenti. E' l'unico filtro che la
   letteratura sull'ORB documenti come funzionante davvero (Zarattini-Barbon-
   Aziz, le "Stocks in Play": si opera solo dove il volume di apertura supera
   il normale). Meccanismo: partecipazione vera contro movimento vuoto.

2. CONTRAZIONE PRECEDENTE — l'escursione M1 dell'ora prima del segnale contro
   quella delle quattro ore precedenti. E' l'idea di Crabel (la compressione
   precede l'espansione) portata dentro la giornata; l'appendice BK ha visto
   che nella sua forma giornaliera raddoppiava il vantaggio lordo.

3. DISTANZA DAL VWAP — quanto e' lontano il prezzo dal VWAP all'ingresso, in
   unita' di respiro M1. Meccanismo: riprendere il VWAP dopo due respiri o
   dopo dieci non e' lo stesso gesto, e la strategia oggi non distingue.

4. LIVELLI VICINI — distanza dal livello ovvio piu' prossimo (massimo e minimo
   di ieri, apertura del giorno, decine tonde), in respiri. Meccanismo: la
   liquidita' sta li'; entrare appena PRIMA di un muro e' peggio che entrare
   appena dopo averlo passato.

5. STRUTTURA FINE M3 — se l'M3 ha gia' girato davvero (minimo piu' alto degli
   ultimi tre, per i long). Nasce da un'obiezione dell'utente al pannello:
   *"ma quello e' gia' il ritracciamento, lateralizza, parte, ritraccia"* — lo
   stato strutturale M12 e' una misura grossa e in ritardo di quel gesto.

Uso: python3 run_selezione_fine.py
Scrive docs/studies/dati/selezione_fine.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1, resample_tf                  # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402
from framework.volatility import daily_bars                      # noqa: E402
from framework.vwap import anchored_vwap                         # noqa: E402

from run_scalp_scaglioni import cammina_uno                      # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GIORNI_MAX = 30
RESPIRO = 30
RICERCA, VERIFICA = (2020, 2022), (2023, 2026)
SEME = 12345


def prepara(m1):
    """Tutte le serie ausiliarie, calcolate una volta e sempre causali."""
    a = {}
    a["respiro"] = (m1.high - m1.low).rolling(RESPIRO).mean().shift(1)
    a["esc_1h"] = (m1.high - m1.low).rolling(60).mean().shift(1)
    a["esc_4h"] = (m1.high - m1.low).rolling(240).mean().shift(1)
    a["vol15"] = m1.volume.rolling(15).sum().shift(1)
    # mediana del volume della stessa ora nei 20 giorni precedenti: e' il
    # riferimento contro cui "molto volume" vuol dire qualcosa. Confrontare con
    # la media del giorno direbbe solo che le 14 UTC sono piu' attive delle 3.
    # una riga per giornata, una colonna per ora: cosi' il rolling scorre sui
    # GIORNI dentro ciascuna ora, che e' il confronto giusto. Farlo con un
    # groupby annidato produceva un indice che poi non si riusciva a
    # interrogare, e la famiglia intera restava vuota senza dirlo.
    vol_dh = (m1.volume.groupby([m1.index.normalize(), m1.index.hour]).sum()
              .unstack(fill_value=0.0))
    a["_per_ora"] = vol_dh.rolling(20, min_periods=10).median().shift(1)
    d1 = daily_bars(m1)
    a["_ieri_alto"] = d1.high.shift(1)
    a["_ieri_basso"] = d1.low.shift(1)
    a["_apertura"] = d1.open
    return a


def livello_vicino(prezzo, ieri_a, ieri_b, apertura):
    """Distanza in dollari dal livello ovvio piu' vicino."""
    cand = [x for x in (ieri_a, ieri_b, apertura) if x is not None and np.isfinite(x)]
    cand.append(round(prezzo / 10.0) * 10.0)          # la decina tonda
    return min(abs(prezzo - c) for c in cand)


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    aux = prepara(m1)
    vwap = anchored_vwap(m1, "day")
    m3 = resample_tf(m1, "M3")
    ops = genera(m1, T)
    print(f"operazioni: {len(ops)}", flush=True)

    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values
    resp, e1, e4, v15 = (aux["respiro"].values, aux["esc_1h"].values,
                         aux["esc_4h"].values, aux["vol15"].values)
    vw = vwap.reindex(m1.index).values
    m3_lo, m3_hi = m3.low.values, m3.high.values
    m3_idx = pd.DatetimeIndex(m3.index).as_unit("ns").asi8
    rng = np.random.default_rng(SEME)

    righe = []
    for o in ops:
        t_in = pd.Timestamp(o["time"]).tz_convert("UTC")
        segno = 1 if o["lato"] == "long" else -1
        e, k = o["entry"], float(o["rischio"])
        a = int(np.searchsorted(idx, t_in.value))
        b = int(np.searchsorted(idx, (t_in + pd.Timedelta(days=GIORNI_MAX)).value))
        if b - a < 2 or a >= len(resp):
            continue
        r_now = resp[a]
        if not np.isfinite(r_now) or r_now <= 0:
            continue
        o_, h_, l_, c_ = ap_[a:b], hi[a:b], lo[a:b], cl[a:b]
        if segno == 1:
            apri, fav, sfav, chiu = ((o_ - e) / k, (h_ - e) / k,
                                     (e - l_) / k, (c_ - e) / k)
        else:
            apri, fav, sfav, chiu = ((e - o_) / k, (e - l_) / k,
                                     (h_ - e) / k, (e - c_) / k)
        r, motivo = cammina_uno(apri, fav, sfav, chiu, 10.0, 3.0)

        g = t_in.normalize()
        po = aux["_per_ora"]
        rif = (po.at[g, t_in.hour]
               if (g in po.index and t_in.hour in po.columns) else np.nan)
        # 5: l'M3 ha davvero girato? minimo piu' alto dei tre precedenti (long)
        j = int(np.searchsorted(m3_idx, t_in.value))
        girato = np.nan
        if 4 <= j <= len(m3_lo):
            fin = m3_lo[j - 4:j] if segno == 1 else m3_hi[j - 4:j]
            if len(fin) == 4:
                girato = float(fin[-1] > fin[:-1].min() if segno == 1
                               else fin[-1] < fin[:-1].max())
        righe.append({
            "anno": o["anno"], "lato": o["lato"], "netto": r - o["costo"],
            "motivo": motivo,
            "1 volume relativo": (v15[a] / rif) if (np.isfinite(rif) and rif > 0) else np.nan,
            "2 contrazione": (e1[a] / e4[a]) if (np.isfinite(e4[a]) and e4[a] > 0) else np.nan,
            "3 distanza vwap": (abs(e - vw[a]) / r_now) if np.isfinite(vw[a]) else np.nan,
            "4 livello vicino": livello_vicino(
                e, aux["_ieri_alto"].get(g, np.nan),
                aux["_ieri_basso"].get(g, np.nan), aux["_apertura"].get(g, np.nan)) / r_now,
            "5 M3 ha girato": girato,
            "0 placebo": float(rng.random())})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "selezione_fine.parquet"), index=False)
    pd.set_option("display.width", 250)
    famiglie = [c for c in t.columns if c[0].isdigit()]
    print(f"utili: {len(t)} | netto totale {t.netto.sum():+.1f} R "
          f"({t.netto.mean():+.3f} R/op)\n", flush=True)

    def terzi(x, col):
        v = x[col]
        if v.dropna().nunique() <= 2:                 # e' binaria (famiglia 5)
            return v.map({0.0: "no", 1.0: "si"})
        return pd.qcut(v, 3, labels=["basso", "medio", "alto"], duplicates="drop")

    for col in famiglie:
        p = t[t[col].notna()]
        if len(p) < 60:
            print(f"--- {col}: troppo pochi dati ({len(p)})\n")
            continue
        p = p.assign(fascia=terzi(p, col))
        f = []
        for eti, (da, aa) in [("ricerca", RICERCA), ("verifica", VERIFICA)]:
            q = p[(p.anno >= da) & (p.anno <= aa)]
            g = q.groupby("fascia", observed=True).netto.agg(["size", "mean", "sum"])
            for fascia, riga in g.iterrows():
                f.append({"periodo": eti, "fascia": fascia, "op": int(riga["size"]),
                          "R/op": riga["mean"], "R": riga["sum"]})
        tab = pd.DataFrame(f).pivot(index="fascia", columns="periodo",
                                    values=["op", "R/op"])
        print(f"--- {col}")
        print(tab.round(3).to_string())
        # l'ordine dei terzi si ripete? e' l'unica domanda che conta
        mr = {x["fascia"]: x["R/op"] for x in f if x["periodo"] == "ricerca"}
        mv = {x["fascia"]: x["R/op"] for x in f if x["periodo"] == "verifica"}
        com = [x for x in mr if x in mv]
        if len(com) >= 2:
            best_r = max(com, key=lambda x: mr[x])
            best_v = max(com, key=lambda x: mv[x])
            print(f"    migliore in ricerca: {best_r} ({mr[best_r]:+.3f}) | "
                  f"in verifica: {best_v} ({mv[best_v]:+.3f}) | "
                  f"{'REGGE' if best_r == best_v else 'non regge'}")
        print()


if __name__ == "__main__":
    main()
