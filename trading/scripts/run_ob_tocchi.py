#!/usr/bin/env python3
"""Appendice BB: gli order block ridefiniti — validi finche' non toccati.

L'obiezione dell'utente al modo in cui li segnavamo: una zona non dovrebbe
morire dopo trenta candele, dovrebbe restare buona **finche' non viene
toccata**; e una gia' toccata, se il prezzo ci torna una seconda o terza
volta, non e' piu' un order block ma un supporto o una resistenza.

Il tocco e' la **chiusura dentro la zona**, non l'ombra che la sfiora: la
chiusura su un timeframe grande e' una conferma piu' forte. Si provano quattro
definizioni: chiusura sul timeframe della zona, su M12, su M6, e l'ombra (che
e' quello che di fatto contava prima) come termine di paragone.

Un tocco NUOVO richiede che il prezzo sia prima uscito: due chiusure di fila
dentro la zona sono una visita sola, non due.

La zona vive finche' non viene **invalidata**, cioe' finche' il prezzo non
chiude oltre il lato lontano. Cosa succede dopo e' la domanda che l'utente non
ha deciso, quindi si misurano entrambe le risposte:
  - "muore": la zona esce di scena;
  - "si ribalta": diventa un livello del lato opposto (il supporto rotto
    diventa resistenza), e da li' in poi i tocchi si operano al contrario.

Per ogni tocco si registra un'operazione nel verso della zona, con stop in ATR
e uscita a fine giornata, e si annota **quale tocco era** (primo, secondo,
terzo o oltre) e **quanto era vecchia** la zona. Ogni cosa ha il suo placebo:
la stessa zona spostata a caso di 0,2-0,6 ATR.

Uso: python3 run_ob_tocchi.py [anno_da anno_a]
Scrive docs/studies/dati/ob_tocchi.parquet
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
from run_livelli_atr import STOP_ATR, OBIETTIVI, esiti, scostamento  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# il dettaglio per tocco pesa centinaia di MB: sta FUORI dal repository,
# dove restano solo gli aggregati. GREZZI lo sposta dove serve.
GREZZI = os.environ.get("GREZZI", os.path.join(ROOT, "..", "dati_grezzi"))
TF_ZONE = ["M33", "M66", "H2", "H6"]
DEFINIZIONI = ["chiusura tf", "chiusura M12", "chiusura M6", "ombra"]
MAX_BARRE = 3000           # tetto alla vita di una zona, per non scandire tutto
ORA_DA, ORA_A = 7, 19      # stessa finestra operativa degli altri studi
SEME = 20260805


def zone_grezze(tfd, tf):
    """Le zone del timeframe, senza scadenza: la scadenza e' cio' che si prova."""
    passo = pd.Timedelta(TIMEFRAMES[tf])
    z = zone_ob(tfd, T.frattale_k, passo, validita=10 ** 6)
    if z.empty:
        return z
    return z.reset_index(drop=True)


def tocchi_di(zona, tempi, chiusure, alti, bassi, definizione):
    """Gli istanti in cui la zona viene toccata, nell'ordine, col numero.

    Un tocco comincia quando il prezzo ENTRA: se la barra precedente era gia'
    dentro, e' la stessa visita.

    I tocchi DOPO l'invalidazione sono marcati: chi vuole la variante "la zona
    muore" li scarta, chi vuole "si ribalta" li opera al contrario. Calcolarli
    una volta sola invece che due dimezza il lavoro e garantisce che le due
    varianti guardino esattamente gli stessi eventi.
    """
    b, a, lato = zona["basso"], zona["alto"], int(zona["lato"])
    # l'indice resta CON FUSO: convertirlo in datetime64 lo perde, e ogni
    # ricerca per giorno (ATR, ora) va poi a vuoto senza dire niente
    i0 = int(tempi.searchsorted(zona["attiva_da"]))
    i1 = min(len(tempi), i0 + MAX_BARRE)
    if i1 - i0 < 2:
        return []
    c = chiusure[i0:i1]
    if definizione == "ombra":
        dentro = (alti[i0:i1] >= b) & (bassi[i0:i1] <= a)
    else:
        dentro = (c >= b) & (c <= a)
    # invalidazione: chiusura oltre il lato lontano
    oltre = (c < b) if lato == 1 else (c > a)
    k_inval = int(np.flatnonzero(oltre)[0]) if oltre.any() else None

    nuovo = dentro & ~np.r_[False, dentro[:-1]]
    fuori = []
    for k in np.flatnonzero(nuovo):
        dopo = k_inval is not None and k > k_inval
        verso = -lato if dopo else lato   # supporto rotto = resistenza
        fuori.append((i0 + k, verso, bool(dopo), len(fuori) + 1, k))
    return fuori


def eventi_tf(m1, tf, atr_di_giorno, finto, rng):
    """Tutti i tocchi di tutte le zone del timeframe, per ogni definizione."""
    tfd = resample_tf(m1, tf)
    z = zone_grezze(tfd, tf)
    if z.empty:
        return []
    serie = {"chiusura tf": tfd, "ombra": tfd,
             "chiusura M12": resample_tf(m1, "M12"),
             "chiusura M6": resample_tf(m1, "M6")}
    pronte = {k: (v.index, v.close.values, v.high.values, v.low.values)
              for k, v in serie.items()}
    giorni = {k: v[0].normalize() for k, v in pronte.items()}
    ore = {k: v[0].hour for k, v in pronte.items()}

    if finto:                              # placebo: zona spostata una volta
        spost = []
        for _, r in z.iterrows():
            a_ = atr_di_giorno.get(pd.Timestamp(r.attiva_da).normalize(), np.nan)
            spost.append(scostamento(rng, a_) if np.isfinite(a_) and a_ > 0 else 0.0)
        z = z.assign(basso=z.basso.values + np.array(spost),
                     alto=z.alto.values + np.array(spost))

    fuori = []
    for definizione in DEFINIZIONI:
        tempi, cl, hi, lo = pronte[definizione]
        gg, oo = giorni[definizione], ore[definizione]
        for _, zona in z.iterrows():
            for k, verso, dopo, n, eta in tocchi_di(zona, tempi, cl, hi, lo,
                                                    definizione):
                if not (ORA_DA <= oo[k] < ORA_A):
                    continue
                a_ = atr_di_giorno.get(gg[k], np.nan)
                if not np.isfinite(a_) or a_ <= 0:
                    continue
                fuori.append({
                    "tf": tf, "definizione": definizione,
                    "dopo_invalidazione": dopo, "tocco": min(n, 4), "eta": eta,
                    "lato": verso, "time": pd.Timestamp(tempi[k]),
                    "entry": float(cl[k]), "atr": float(a_)})
    return fuori


def raccogli(m1, finto, seme):
    rng = np.random.default_rng(seme)
    atr = daily_atr(m1, 14)
    atr_g = {k: v for k, v in atr.items()}
    idx_ns = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    tutti = []
    for tf in TF_ZONE:
        ev = eventi_tf(m1, tf, atr_g, finto, rng)
        if not ev:
            continue
        col = esiti(ev, m1, idx_ns)
        t = pd.DataFrame(ev)
        for k, v in col.items():
            t[f"r|{k}"] = v
        if t[[f"r|{k}" for k in col]].notna().sum().sum() == 0:
            raise SystemExit(f"{tf}: nessun esito calcolato, controllare gli indici")
        t["anno"] = t.time.dt.year
        tutti.append(t)
        print(f"  {tf}: {len(ev)} tocchi", flush=True)
    return pd.concat(tutti, ignore_index=True) if tutti else pd.DataFrame()


def main():
    anni = None
    if len(sys.argv) > 2:
        anni = list(range(int(sys.argv[1]), int(sys.argv[2]) + 1))
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"), years=anni)
    print("zone vere:", flush=True)
    veri = raccogli(m1, False, SEME)
    print("placebo:", flush=True)
    falsi = raccogli(m1, True, SEME + 1)
    veri["vero"], falsi["vero"] = True, False
    t = pd.concat([veri, falsi], ignore_index=True)
    os.makedirs(GREZZI, exist_ok=True)
    fuori = os.path.join(GREZZI, "ob_tocchi.parquet")
    t.to_parquet(fuori, index=False)
    print(f"\n{len(veri)} tocchi veri, {len(falsi)} placebo -> {fuori}")


if __name__ == "__main__":
    main()
