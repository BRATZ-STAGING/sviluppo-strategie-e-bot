#!/usr/bin/env python3
"""Appendice BE: il VUOTO di volume come obiettivo, non come ingresso.

L'idea dell'utente, arrivata con un'operazione vera: order block su M12 come
innesco, e sopra una fascia a volume quasi nullo "da riempire" come bersaglio.

E' diversa da tutto quello gia' misurato. L'appendice AZ ha provato i vuoti
come INGRESSO (respinti). L'appendice AE ha provato l'obiettivo appoggiato ai
livelli, ma quelli strutturali: swing, order block contrari, estremi del
giorno prima, numeri tondi — **mai i vuoti di volume**, che nell'appendice AB
erano rimasti come "fase 2 mai aperta".

Il meccanismo dichiarato: dove il mercato ha scambiato poco il prezzo passa in
fretta, quindi un obiettivo posto oltre un vuoto viene raggiunto piu' spesso
di un obiettivo alla stessa distanza messo dove il volume c'e'.

IPOTESI PRE-REGISTRATA, e come si falsifica. Due controlli, non uno:

- **vuoto finto**: il profilo del giorno spostato a caso di 0,2-0,6 ATR. Tiene
  la forma dell'istogramma ma sposta dove sono i buchi.
- **distanza rimescolata**: obiettivo alla stessa distanza di un ALTRO evento
  scelto a caso, senza nessun vuoto sotto. Questo e' il controllo che conta:
  se il vuoto vero non batte una distanza qualunque uguale alla sua, allora
  non e' il vuoto a lavorare, e' solo il modo in cui sceglie quanto lontano
  mettere l'obiettivo.

Confrontare a parita' di RR non basta da solo: dentro la stessa fascia le
distanze non sono identiche, e il bordo lontano di un vuoto vero cade per
costruzione dove il volume riprende, cioe' su un prezzo gia' frequentato.

Il profilo e' costruito **minuto per minuto solo con il passato**: al momento
dell'ingresso si conosce solo cio' che e' stato scambiato fino a quel minuto.

Uso: python3 run_vuoto_obiettivo.py [anno_da anno_a]
Scrive <dati_grezzi>/vuoto_obiettivo.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf       # noqa: E402
from framework.taratura import UFFICIALE as T                     # noqa: E402
from framework.volatility import daily_atr                        # noqa: E402

from export_lab import zone_ob                                    # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GREZZI = os.environ.get("GREZZI", os.path.join(ROOT, "..", "dati_grezzi"))
TF_ZONE = ["M12", "M33"]
STOP_ATR = [0.25, 0.5]
BIN_ATR = 0.05             # larghezza dei livelli del profilo, in ATR
VUOTO_SOGLIA = 0.15        # sotto questa frazione del massimo e' "vuoto"
VUOTO_MIN = 0.10           # spessore minimo di un vuoto, in ATR
MIN_PROFILO = 60           # minuti di scambi prima di fidarsi del profilo
ORA_DA, ORA_A, ORA_FINE = 7, 19, 21
SEME = 20260806


def vuoti_da(conteggio, prezzi, atr):
    """Le fasce a volume basso di un istogramma, dal basso verso l'alto.

    ATTENZIONE: si guarda SOLO il tratto gia' scambiato. L'istogramma copre
    l'intera escursione della giornata, futuro compreso: la parte sotto al
    minimo toccato finora e' tutta a zero, viene chiusa dal primo livello
    scambiato e verrebbe registrata come un vuoto il cui bordo lontano e'
    esattamente il MINIMO FUTURO del giorno — un prezzo che la giornata
    raggiungera' per definizione. E' cosi' che uno short su quel "vuoto"
    sembrava rendere +0,47 R/op contro -0,40, mentre il long, che non ha
    l'equivalente (la coda in alto non viene mai chiusa), restava negativo.
    """
    massimo = conteggio.max()
    if massimo <= 0:
        return []
    visti = np.flatnonzero(conteggio > 0)
    a, b = int(visti[0]), int(visti[-1]) + 1
    conteggio, prezzi = conteggio[a:b], prezzi[a:b]
    basso = conteggio < massimo * VUOTO_SOGLIA
    fuori, ini = [], None
    for i, b in enumerate(basso):
        if b and ini is None:
            ini = i
        if not b and ini is not None:
            if prezzi[i - 1] - prezzi[ini] >= atr * VUOTO_MIN:
                fuori.append((prezzi[ini], prezzi[i - 1]))
            ini = None
    return fuori


def bersaglio(vuoti, prezzo, verso):
    """Il bordo lontano del vuoto piu' vicino nella direzione dell'operazione."""
    if verso == 1:
        sopra = [v for v in vuoti if v[0] > prezzo]
        return min(sopra, key=lambda v: v[0])[1] if sopra else None
    sotto = [v for v in vuoti if v[1] < prezzo]
    return max(sotto, key=lambda v: v[1])[0] if sotto else None


def tocchi_m12(tfd, tf, z):
    """Chiusure dentro una zona attiva e concorde: l'innesco dell'utente."""
    if z.empty:
        return []
    passo = pd.Timedelta(TIMEFRAMES[tf])
    tempi, cl = tfd.index, tfd.close.values
    fuori = []
    for _, zona in z.iterrows():
        i0 = int(tempi.searchsorted(zona.attiva_da))
        i1 = min(len(tempi), i0 + 400)
        if i1 - i0 < 2:
            continue
        c = cl[i0:i1]
        dentro = (c >= zona.basso) & (c <= zona.alto)
        oltre = (c < zona.basso) if zona.lato == 1 else (c > zona.alto)
        fine = int(np.flatnonzero(oltre)[0]) if oltre.any() else len(c)
        nuovo = dentro & ~np.r_[False, dentro[:-1]]
        for k in np.flatnonzero(nuovo):
            if k > fine:
                break
            fuori.append((tempi[i0 + k] + passo, int(zona.lato)))
    return fuori


def esito(m1v, idx_ns, quando, entry, verso, stop_prezzo, obiettivo, fine):
    """Percorso al minuto: vince lo stop a parita' di minuto, uscita a fine giornata."""
    a = int(np.searchsorted(idx_ns, quando.value))
    b = int(np.searchsorted(idx_ns, fine.value))
    if b - a < 2:
        return None
    hi, lo, cl = m1v
    h_, l_, c_ = hi[a:b], lo[a:b], cl[a:b]
    rischio = abs(entry - stop_prezzo)
    if rischio <= 0:
        return None
    if verso == 1:
        giu = np.flatnonzero(l_ <= stop_prezzo)
        su = np.flatnonzero(h_ >= obiettivo)
    else:
        giu = np.flatnonzero(h_ >= stop_prezzo)
        su = np.flatnonzero(l_ <= obiettivo)
    k_stop = giu[0] if len(giu) else None
    k_tp = su[0] if len(su) else None
    if k_stop is not None and (k_tp is None or k_stop <= k_tp):
        r = -1.0
    elif k_tp is not None:
        r = abs(obiettivo - entry) / rischio
    else:
        r = (c_[-1] - entry) * verso / rischio
    return r - T.spread / rischio


def main():
    anni = None
    if len(sys.argv) > 2:
        anni = list(range(int(sys.argv[1]), int(sys.argv[2]) + 1))
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"), years=anni)
    rng = np.random.default_rng(SEME)
    atr = daily_atr(m1, 14)
    atr_g = {k: float(v) for k, v in atr.items()}
    idx_ns = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    m1v = (m1.high.values, m1.low.values, m1.close.values)
    tipico = ((m1.high + m1.low + m1.close) / 3).values
    vol = m1.volume.values.astype(float)
    vol[~np.isfinite(vol) | (vol <= 0)] = 1.0
    giorni_m1 = m1.index.normalize()

    inneschi = {}
    for tf in TF_ZONE:
        tfd = resample_tf(m1, tf)
        z = zone_ob(tfd, T.frattale_k, pd.Timedelta(TIMEFRAMES[tf]), validita=10 ** 6)
        for quando, verso in tocchi_m12(tfd, tf, z):
            inneschi.setdefault(quando.normalize(), []).append((quando, verso, tf))
    print(f"inneschi: {sum(len(v) for v in inneschi.values())}", flush=True)

    righe = []
    for giorno, elenco in sorted(inneschi.items()):
        a_ = atr_g.get(giorno)
        if a_ is None or not np.isfinite(a_) or a_ <= 0:
            continue
        sel = np.flatnonzero(giorni_m1 == giorno)
        if len(sel) < 200:
            continue
        passo = a_ * BIN_ATR
        liv = np.round(tipico[sel] / passo).astype(np.int64)
        base = liv.min()
        n = int(liv.max() - base) + 1
        conteggio = np.zeros(n)
        prezzi = (base + np.arange(n)) * passo
        # spostamento del profilo finto: estratto UNA volta per giornata
        salto = int(round(rng.uniform(.2, .6) * a_ / passo)) * rng.choice([-1, 1])
        tempi_m1 = m1.index[sel]
        fine = giorno + pd.Timedelta(hours=ORA_FINE)
        prossimo = 0
        for quando, verso, tf in sorted(elenco):
            if not (ORA_DA <= quando.hour < ORA_A):
                continue
            # si accumula il profilo SOLO fino al minuto dell'ingresso
            while prossimo < len(sel) and tempi_m1[prossimo] < quando:
                conteggio[liv[prossimo] - base] += vol[sel[prossimo]]
                prossimo += 1
            if prossimo < MIN_PROFILO:
                continue
            entry = float(m1.close.values[sel[prossimo - 1]])
            # riferimento: lo stesso innesco con obiettivo fisso a 2R, che
            # esista o no un vuoto. Serve a capire se il vantaggio sta nel
            # vuoto o gia' nell'innesco (o nella condizione "esiste un vuoto")
            for q in STOP_ATR:
                stop_prezzo = entry - verso * q * a_
                r = esito(m1v, idx_ns, quando, entry, verso, stop_prezzo,
                          entry + verso * 2 * q * a_, fine)
                if r is not None:
                    righe.append({"tipo": "innesco 1:2 fisso", "tf": tf, "q": q,
                                  "lato": verso, "time": quando,
                                  "anno": quando.year, "atr": a_, "entry": entry,
                                  "distanza_atr": 2 * q, "rr": 2.0, "r": r})
            veri = vuoti_da(conteggio, prezzi, a_)
            finti = vuoti_da(np.roll(conteggio, salto), prezzi, a_)
            for eti, vuoti in (("vero", veri), ("vuoto finto", finti)):
                b = bersaglio(vuoti, entry, verso)
                if b is None:
                    continue
                distanza = abs(b - entry)
                if not (0.05 * a_ <= distanza <= 3 * a_):
                    continue
                for q in STOP_ATR:
                    stop_prezzo = entry - verso * q * a_
                    r = esito(m1v, idx_ns, quando, entry, verso,
                              stop_prezzo, b, fine)
                    if r is None:
                        continue
                    righe.append({
                        "tipo": eti, "tf": tf, "q": q, "lato": verso,
                        "time": quando, "anno": quando.year, "atr": a_,
                        "entry": entry,
                        "distanza_atr": distanza / a_,
                        "rr": distanza / (q * a_), "r": r,
                        "chiave": len(righe)})
    d = pd.DataFrame(righe)
    # controllo decisivo: stessa distanza, ma presa da un altro evento
    veri = d[d.tipo == "vero"] if len(d) else d
    if len(veri) > 20:
        mescolate = rng.permutation(veri.distanza_atr.values)
        extra = []
        for (_, riga), dist in zip(veri.iterrows(), mescolate):
            a_ = riga.atr
            entry_r = float(riga.get("entry", np.nan))
            if not np.isfinite(entry_r):
                continue
            b = entry_r + riga.lato * dist * a_
            stop_prezzo = entry_r - riga.lato * riga.q * a_
            r = esito(m1v, idx_ns, pd.Timestamp(riga.time), entry_r,
                      int(riga.lato), stop_prezzo, b,
                      pd.Timestamp(riga.time).normalize()
                      + pd.Timedelta(hours=ORA_FINE))
            if r is None:
                continue
            e = riga.to_dict()
            e.update({"tipo": "distanza a caso", "distanza_atr": dist,
                      "rr": dist / riga.q, "r": r})
            extra.append(e)
        d = pd.concat([d, pd.DataFrame(extra)], ignore_index=True)
    os.makedirs(GREZZI, exist_ok=True)
    fuori = os.path.join(GREZZI, "vuoto_obiettivo.parquet")
    d.to_parquet(fuori, index=False)
    print(f"{len(d)} righe -> {fuori}")
    if d.empty:
        return
    pd.set_option("display.width", 220)
    d["fascia"] = pd.cut(d.rr, [0, 1, 2, 3, 5, 100],
                         labels=["<1", "1-2", "2-3", "3-5", ">5"])
    g = d.groupby(["fascia", "tipo"], observed=True).agg(
        op=("r", "size"), r_op=("r", "mean"), vinte=("r", lambda x: (x > 0).mean() * 100))
    print("\n=== a parita' di distanza (in RR), il vuoto VERO batte quello finto?")
    print(g.round(3).to_string())


if __name__ == "__main__":
    main()
