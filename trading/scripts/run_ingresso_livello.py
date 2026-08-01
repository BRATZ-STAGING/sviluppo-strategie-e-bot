#!/usr/bin/env python3
"""Appendice AA: entrare SUL livello (order block) invece che alla chiusura.

La strategia in vigore entra a mercato alla chiusura della candela M6 del
segnale. Qui il segnale resta identico, ma l'ingresso diventa un ordine
LIMITE sul bordo della zona order block piu' vicina dalla parte del
ritracciamento, con lo stop sul lato lontano della zona.

Zone costruite su cinque timeframe (M6, M12, M33, H3, H6). Se nessuna zona
concorde sta entro la distanza massima, o se l'ordine non viene riempito
entro la fine della giornata, l'operazione non esiste.

Convenzioni conservative di sempre: nello stesso minuto lo stop prevale
sull'obiettivo, tutto causale, spread sottratto in R.

Salva docs/studies/dati/ingresso-livello.parquet.
Uso: python3 run_ingresso_livello.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf     # noqa: E402
from framework.gestione import esito_indice                      # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402
from framework.volatility import high_volatility_months          # noqa: E402

from export_lab import (CALIB, genera, macro_trend, prepara,      # noqa: E402
                        zone_ob)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TF_ZONE = ["M6", "M12", "M33", "H3", "H6"]
DISTANZE = [5.0, 10.0, 20.0]        # quanto lontano puo' stare il livello
RR = [3.0, 5.0, 10.0]
BE = [None, 3.0]
SPREAD = [0.30, 0.63]
MARGINE = 0.30                       # margine dello stop oltre la zona
RISK_MIN, RISK_MAX = 0.5, 20.0


def carica_zone(m1):
    """Tutte le zone dei cinque timeframe, con i tempi in interi ns.

    as_unit e' obbligatorio: asi8 restituisce gli interi nell'unita' propria
    dell'array, e le zone nascono in microsecondi mentre le M1 sono in ns.
    """
    ns = lambda s: pd.DatetimeIndex(pd.to_datetime(s, utc=True)).as_unit("ns").asi8
    pezzi = []
    for tf in TF_ZONE:
        z = zone_ob(resample_tf(m1, tf), 3, TIMEFRAMES[tf])
        z["tf"] = tf
        pezzi.append(z)
    z = pd.concat(pezzi, ignore_index=True)
    return {"att": ns(z.attiva_da), "sca": ns(z.scade_il), "inv": ns(z.invalidata_il),
            "viva": z.invalidata_il.isna().values, "lato": z.lato.values,
            "basso": z.basso.values, "alto": z.alto.values,
            "tf": z.tf.values, "n": len(z)}


def livello(Z, t_sig, prezzo, segno, dist_max):
    """Bordo vicino della zona concorde piu' vicina, e lato lontano (stop).

    Long: la zona sta SOTTO il prezzo, si compra sul bordo alto e lo stop va
    sotto il bordo basso. Speculare per lo short.
    """
    viva = ((Z["lato"] == segno) & (Z["att"] <= t_sig) & (Z["sca"] > t_sig)
            & (Z["viva"] | (Z["inv"] > t_sig)))
    if segno == 1:
        ok = viva & (Z["alto"] < prezzo) & (prezzo - Z["alto"] <= dist_max)
        cand = np.flatnonzero(ok)
        if not len(cand):
            return None
        j = cand[np.argmax(Z["alto"][cand])]        # la piu' vicina al prezzo
        return float(Z["alto"][j]), float(Z["basso"][j]) - MARGINE, Z["tf"][j]
    ok = viva & (Z["basso"] > prezzo) & (Z["basso"] - prezzo <= dist_max)
    cand = np.flatnonzero(ok)
    if not len(cand):
        return None
    j = cand[np.argmin(Z["basso"][cand])]
    return float(Z["basso"][j]), float(Z["alto"][j]) + MARGINE, Z["tf"][j]


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    m6, atr = prepara(m1)
    mask = (atr.index.year >= CALIB[0]) & (atr.index.year <= CALIB[1])
    med = float(atr[mask].median())
    k = {"imp": T.impulso_min / med, "buf": T.buffer / med,
         "rmin": T.rischio_min / med, "rmax": T.rischio_max / med}
    alto_vol = high_volatility_months(
        atr, sorted({pd.Period(x.strftime("%Y-%m"), "M") for x in m6.index}),
        T.fattore_alta_volatilita)
    zone_m33 = zone_ob(resample_tf(m1, "M33"), 3, TIMEFRAMES["M33"])
    segnali = genera(m1, m6, alto_vol, k, macro_trend(m1), zone_m33)
    print(f"segnali: {len(segnali)}", flush=True)

    Z = carica_zone(m1)
    print(f"zone sui cinque timeframe: {Z['n']}", flush=True)

    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    hi, lo = m1.high.values, m1.low.values

    righe = []
    for op_id, s in enumerate(segnali):
        segno = 1 if s["lato"] == "long" else -1
        t_sig = pd.Timestamp(s["t_in"]).tz_convert("UTC").value
        giorno = pd.Timestamp(s["t_in"]).tz_convert("UTC").normalize()
        t_end = (giorno + pd.Timedelta(hours=T.ora_chiusura)).value
        a = int(np.searchsorted(idx, t_sig))
        b = int(np.searchsorted(idx, t_end))
        if b - a < 2:
            continue
        ufficiale = bool(s["macro"] == (s["lato"] == "long")
                         and s["cf"]["M33"] and s["cf"]["H12"]
                         and not s["cf"]["M12"])
        for dist in DISTANZE:
            liv = livello(Z, t_sig, s["entry"], segno, dist)
            if liv is None:
                continue
            entrata, stop_zona, tf_z = liv
            # riempimento: il prezzo deve arrivare al limite entro fine giornata
            h_, l_ = hi[a:b], lo[a:b]
            tocca = (l_ <= entrata) if segno == 1 else (h_ >= entrata)
            w = np.flatnonzero(tocca)
            if not len(w):
                continue
            f = int(w[0])
            h2, l2 = h_[f:], l_[f:]
            fine_g = float(m1.close.values[b - 1])
            # due stop a confronto: stretto sulla zona (versione dell'utente) e
            # quello strutturale del segnale, che con l'ingresso piu' basso
            # costa comunque meno rischio dell'operazione a mercato
            for tipo, stop in (("zona", stop_zona), ("strutturale", s["sl"])):
                risk = abs(entrata - stop)
                if not (RISK_MIN <= risk <= RISK_MAX):
                    continue
                if segno == 1:
                    fav, sfav = (h2 - entrata) / risk, (entrata - l2) / risk
                else:
                    fav, sfav = (entrata - l2) / risk, (h2 - entrata) / risk
                for rr in RR:
                    for be in BE:
                        r, motivo, _ = esito_indice(fav, sfav, rr, be=be, costo=0.0)
                        if r is None:        # ancora aperta a fine giornata
                            r = ((fine_g - entrata) if segno == 1
                                 else (entrata - fine_g)) / risk
                            motivo = 2
                        righe.append({
                            "op_id": op_id, "anno": s["anno"],
                            "ufficiale": ufficiale, "stop": tipo,
                            "dist": dist, "rr": rr,
                            "be": -1.0 if be is None else be,
                            "tf_zona": tf_z, "risk": risk,
                            "risk_uff": s["risk"], "r_lordo": float(r),
                            "motivo": int(motivo)})
    out = pd.DataFrame(righe)
    dest = os.path.join(ROOT, "docs", "studies", "dati", "ingresso-livello.parquet")
    out.to_parquet(dest, index=False)
    n_op = out.op_id.nunique() if len(out) else 0
    print(f"operazioni riempite (almeno una distanza): {n_op}")
    print(f"\n{dest}")


if __name__ == "__main__":
    main()
