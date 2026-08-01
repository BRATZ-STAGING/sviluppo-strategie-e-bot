#!/usr/bin/env python3
"""Esporta i dati per il laboratorio visivo: variabili modificabili a schermo.

Genera UN insieme completo di operazioni (long e short, senza filtro macro,
parametrizzazione = switch su volatilità) e per ciascuna precalcola tutto ciò
che serve a ricomputare l'esito con obiettivi diversi:

- indice della candela d'ingresso, lato, se il giorno era sopra/sotto la media
  di fondo (filtro macro), rischio in dollari, prezzi di ingresso e stop
- indice della candela in cui lo stop viene colpito (se accade)
- indice e risultato dell'uscita di fine giornata
- per ogni obiettivo della griglia RR, l'indice in cui viene raggiunto

Con questi campi la pagina può calcolare esattamente, senza approssimare:
direzione, filtro macro, obiettivo RR e rischio percentuale.

Nota verificata: i limiti "max 3 al giorno" e "30 minuti fra un segnale e
l'altro" non si attivano quasi mai (1.897 operazioni su ~1.700 giornate),
quindi filtrare a schermo per lato dà gli stessi identici numeri che
rigenerare la strategia con quel solo lato.

Uso: python3 export_lab.py <out.json> full:H6 2025-10 2026-01
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf     # noqa: E402
from framework.gestione import (chiusura_fine_giornata,          # noqa: E402
                                esito_indice)
from framework.structure import state_at, trend_state_series     # noqa: E402
from framework.taratura import UFFICIALE as T                     # noqa: E402
from framework.volatility import (atr_at, daily_atr,             # noqa: E402
                                  high_volatility_months)
from framework.vwap import anchored_vwap                         # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPREAD, BUF = T.spread, T.buffer
MIN_RISK, MAX_RISK, MIN_IMPULSE = T.rischio_min, T.rischio_max, T.impulso_min
CALIB = T.calibrazione
RR_GRID = [2.0, 3.0, 5.0, 8.0, 10.0]
BE_GRID = [None, 2.0, 3.0]     # pareggio: +1,5R rompe un anno, +4R e' come +3R
STOP_MODES = [None, 3.0, 5.0, 10.0]    # None = strutturale; poi punti fissi
SPREADS = [0.30, 0.63]       # storico assunto / reale misurato sui tick
MAX_GIORNO, COOLDOWN, SMA = T.max_operazioni_giorno, T.attesa_minuti, T.media_macro
CONFERME = ["M33", "H12", "M66", "M12"]   # M33 e H12 sono le due che
                                     # discriminano davvero (verificato fuori campione)


def zone_ob(df, k, freq, indietro=10, validita=30):
    """Order block su un timeframe: zona piena e zona raffinata.

    Piena (rialzista): dal minimo all'apertura dell'ultima candela contraria
    prima della rottura di uno swing. Raffinata (definizione dell'utente):
    intersezione fra la base di quella candela e la base della successiva
    [max dei minimi, min dei corpi bassi]; se vuota non esiste. Speculare per
    la ribassista. Causali: attive dalla chiusura della candela che rompe.
    """
    freq = pd.Timedelta(freq)
    hi, lo = df.high.values, df.low.values
    op, cl = df.open.values, df.close.values
    idx = df.index
    n = len(df)
    ultimo_sh = ultimo_sl = None
    zone = []
    for i in range(n):
        j = i - k
        if j >= k:
            if (hi[j-k:j] < hi[j]).all() and (hi[j+1:j+k+1] < hi[j]).all():
                ultimo_sh = hi[j]
            if (lo[j-k:j] > lo[j]).all() and (lo[j+1:j+k+1] > lo[j]).all():
                ultimo_sl = lo[j]
        for lato, rotto in ((1, ultimo_sh is not None and cl[i] > ultimo_sh),
                            (-1, ultimo_sl is not None and cl[i] < ultimo_sl)):
            if not rotto:
                continue
            trovata = None
            for b in range(i, max(-1, i - indietro), -1):
                contraria = (cl[b] < op[b]) if lato == 1 else (cl[b] > op[b])
                if contraria:
                    trovata = b
                    break
            if trovata is not None:
                if lato == 1:
                    basso, alto = float(lo[trovata]), float(op[trovata])
                else:
                    basso, alto = float(op[trovata]), float(hi[trovata])
                rb = ra = float("nan")
                d = trovata + 1
                if d <= i:
                    if lato == 1:
                        rb = max(lo[trovata], lo[d])
                        ra = min(min(op[trovata], cl[trovata]),
                                 min(op[d], cl[d]))
                    else:
                        rb = max(max(op[trovata], cl[trovata]),
                                 max(op[d], cl[d]))
                        ra = min(hi[trovata], hi[d])
                    if not rb < ra:
                        rb = ra = float("nan")
                zone.append({"attiva_da": idx[i] + freq, "lato": lato,
                             "basso": basso, "alto": alto,
                             "rbasso": float(rb), "ralto": float(ra),
                             "scade_il": idx[min(i + validita, n - 1)] + freq,
                             "barra_rottura": i})
            if lato == 1:
                ultimo_sh = None
            else:
                ultimo_sl = None
    z = pd.DataFrame(zone)
    if z.empty:
        return z
    inval = []
    for _, r in z.iterrows():
        i0 = int(r.barra_rottura) + 1
        if r.lato == 1:
            oltre = np.where(cl[i0:] < r.basso)[0]
        else:
            oltre = np.where(cl[i0:] > r.alto)[0]
        inval.append(idx[i0 + oltre[0]] + freq if len(oltre) else pd.NaT)
    z["invalidata_il"] = inval
    return z


def in_zona(z, quando, prezzo, lato, margine, raffinata=False):
    """C'e' una zona attiva e concorde che contiene il prezzo?"""
    if z.empty:
        return False
    lo_c = z.rbasso if raffinata else z.basso
    hi_c = z.ralto if raffinata else z.alto
    m = ((z.lato == lato) & (z.attiva_da <= quando) & (z.scade_il > quando)
         & (z.invalidata_il.isna() | (z.invalidata_il > quando))
         & (lo_c - margine <= prezzo) & (prezzo <= hi_c + margine))
    return bool(m.fillna(False).any())


def prepara(m1):
    m6 = resample_tf(m1, "M6")
    m6["vwap"] = anchored_vwap(m6, "day")
    closes = m6.index + pd.Timedelta("6min")
    m6["h6"] = state_at(trend_state_series(resample_tf(m1, "H6"), T.frattale_k, "6h"), closes)
    m6["h2"] = state_at(trend_state_series(resample_tf(m1, "H2"), T.frattale_k, "2h"), closes)
    for tf in CONFERME:                       # strutture di conferma, causali
        s_tf = resample_tf(m1, tf)
        m6[tf] = state_at(trend_state_series(s_tf, T.frattale_k, pd.Timedelta(TIMEFRAMES[tf])),
                          closes)
    atr = daily_atr(m1, 14)
    m6["atr"] = atr_at(atr, m6.index).values
    return m6, atr


def macro_trend(m1, n=SMA):
    d1 = m1.close.resample("1D").last().dropna()
    sopra = (d1 > d1.rolling(n).mean()).shift(1)
    sopra.index = sopra.index.normalize()
    return sopra.to_dict()


def genera(m1, m6, alto_vol, k, macro, zone):
    """Tutte le operazioni (long e short), con gli esiti per ogni obiettivo."""
    idx = m6.index
    hours, days = idx.hour, idx.normalize()
    hi, lo, cl = m6.high.values, m6.low.values, m6.close.values
    vd, h6, h2, atrv = m6.vwap.values, m6.h6.values, m6.h2.values, m6.atr.values
    conf = {tf: m6[tf].values for tf in CONFERME}
    m1_idx = m1.index
    m1h, m1l, m1c = m1.high.values, m1.low.values, m1.close.values
    mese = pd.PeriodIndex(idx, freq="M")

    out, last_sig, day_count, day_start = [], None, {}, 0
    for i in range(1, len(m6)):
        d = days[i]
        if d != days[i - 1]:
            day_start = i
        if not (T.ora_inizio <= hours[i] < T.ora_fine) or np.isnan(vd[i]):
            continue
        if day_count.get(d, 0) >= MAX_GIORNO:
            continue
        t_sig = idx[i] + pd.Timedelta("6min")
        if last_sig is not None and (t_sig - last_sig) < pd.Timedelta(minutes=COOLDOWN):
            continue
        if alto_vol.get(mese[i], False):
            u = atrv[i]
            if np.isnan(u) or u <= 0:
                continue
            imp_min, buf = k["imp"] * u, k["buf"] * u
            r_min, r_max = k["rmin"] * u, k["rmax"] * u
        else:
            imp_min, buf, r_min, r_max = MIN_IMPULSE, BUF, MIN_RISK, MAX_RISK

        lato = None
        if h6[i] == 1 and h2[i] == 1 and lo[i] <= vd[i] and cl[i] > vd[i] \
                and cl[i] > hi[i - 1]:
            if (float(hi[day_start:i].max() - vd[i]) if i > day_start else 0) >= imp_min:
                lato = "long"
        if lato is None and h6[i] == -1 and h2[i] == -1 and hi[i] >= vd[i] \
                and cl[i] < vd[i] and cl[i] < lo[i - 1]:
            if (float(vd[i] - lo[day_start:i].min()) if i > day_start else 0) >= imp_min:
                lato = "short"
        if lato is None:
            continue

        entry = float(cl[i])
        j0 = max(day_start, i - T.barre_stop)
        if lato == "long":
            stop = float(lo[j0:i + 1].min() - buf); risk = entry - stop
        else:
            stop = float(hi[j0:i + 1].max() + buf); risk = stop - entry
        if not (r_min <= risk <= r_max):
            continue
        a = int(m1_idx.searchsorted(t_sig))
        b = int(m1_idx.searchsorted(d + pd.Timedelta(hours=T.ora_chiusura)))
        if b - a < 2:
            continue
        last_sig = t_sig
        day_count[d] = day_count.get(d, 0) + 1

        h_, l_, c_ = m1h[a:b], m1l[a:b], m1c[a:b]
        if lato == "long":
            fav, sfav = (h_ - entry) / risk, (entry - l_) / risk
        else:
            fav, sfav = (entry - l_) / risk, (h_ - entry) / risk
        fine = float(c_[-1])
        r_eod = ((fine - entry) if lato == "long" else (entry - fine)) / risk
        costo = SPREAD / risk
        mfe = float(fav.max())

        # per ogni tipo di stop, soglia di pareggio e obiettivo: quando esce,
        # con che risultato LORDO e per quale motivo. Risolto al minuto.
        # Lo spread si sottrae a schermo (non cambia il percorso, solo l'esito
        # in R), cosi' la pagina puo' mostrare sia 0,30 che 0,63.
        esiti = []
        for stop_fisso in STOP_MODES:
            sc = 1.0 if stop_fisso is None else risk / stop_fisso
            f_, s_, eod_, mfe_ = fav * sc, sfav * sc, r_eod * sc, mfe * sc
            per_modo = []
            for be in BE_GRID:
                riga = []
                for rr in RR_GRID:
                    r, motivo, j = esito_indice(f_, s_, rr, be=be, costo=0.0)
                    if r is None:
                        r = chiusura_fine_giornata(eod_, be, False, mfe_, 0.0)
                    riga.append([m1_idx[a + j] if j is not None else m1_idx[b - 1],
                                 round(float(r), 3), motivo])
                per_modo.append(riga)
            esiti.append(per_modo)

        segno = 1 if lato == "long" else -1
        out.append({
            "ob": int(in_zona(zone, t_sig, entry, segno, 0.5 * risk)),
            "obr": int(in_zona(zone, t_sig, entry, segno, 0.5 * risk,
                               raffinata=True)),
            "q": sum(1 for tf in CONFERME if conf[tf][i] == segno),
            "cf": {tf: int(conf[tf][i] == segno) for tf in CONFERME},
            "t_in": t_sig, "anno": int(idx[i].year), "lato": lato,
            "macro": bool(macro.get(d, False)),
            "entry": round(entry, 2), "sl": round(stop, 2), "risk": round(risk, 3),
            "t_eod": m1_idx[b - 1], "r_eod": round(float(r_eod), 3),
            "esiti": esiti, "costo": round(costo, 4),
        })
    return out


def pack(series, trades, vol=None, label=""):
    base = float(np.floor(series.low.min()))
    cent = lambda s: [int(round((float(v) - base) * 100)) for v in s]
    idx = series.index
    barra = lambda t: (-1 if t is None
                       else int(np.clip(idx.searchsorted(t, side="right") - 1,
                                        0, len(idx) - 1)))
    per = {
        "id": label, "t0": int(idx[0].timestamp() * 1000), "base": base,
        "t": [int((x - idx[0]).total_seconds() // 60) for x in idx],
        "o": cent(series.open), "h": cent(series.high),
        "l": cent(series.low), "c": cent(series.close),
        "tv": [int(x) for x in series.volume],
        "v": ([None if np.isnan(x) else int(round((x - base) * 100))
               for x in series.vwap] if "vwap" in series else [None] * len(idx)),
        "s": ([int(a) * 3 + int(b) for a, b in zip(series.h6, series.h2)]
              if "h6" in series else [0] * len(idx)),
        "trades": [],
    }
    for tr in trades:
        i = barra(tr["t_in"])
        if i < 0 or not (idx[0] <= tr["t_in"] <= idx[-1] + pd.Timedelta(days=1)):
            continue
        # gli esiti sono già risolti al minuto (stop, obiettivo, pareggio,
        # fine giornata): qui si mappano solo sulle barre del grafico
        esiti = [[[[barra(t), r, mo] for t, r, mo in riga] for riga in modo]
                 for modo in tr["esiti"]]
        per["trades"].append({
            "i": i, "y": tr["anno"], "L": 1 if tr["lato"] == "long" else 0,
            "M": 1 if tr["macro"] else 0, "q": tr["q"],
            "f": [tr["cf"]["M33"], tr["cf"]["H12"], tr["cf"]["M66"], tr["cf"]["M12"]],
            "e": tr["entry"], "s": tr["sl"], "k": tr["risk"], "c": tr["costo"],
            "b": [tr["ob"], tr["obr"]],
            "x": esiti,   # [stop][pareggio][RR]: [barra uscita, R lordo, motivo]
        })
    if vol is not None:
        per["vol"] = [round(float(vol.get(x.normalize(), np.nan)), 3)
                      if not np.isnan(vol.get(x.normalize(), np.nan)) else None
                      for x in idx]
    return per


def main():
    out_path = sys.argv[1]
    specs = sys.argv[2:] or ["full:H6"]
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    m6, atr = prepara(m1)
    mask = (atr.index.year >= CALIB[0]) & (atr.index.year <= CALIB[1])
    med = float(atr[mask].median())
    k = {"imp": MIN_IMPULSE / med, "buf": BUF / med,
         "rmin": MIN_RISK / med, "rmax": MAX_RISK / med}
    alto = high_volatility_months(
        atr, sorted({pd.Period(x.strftime("%Y-%m"), "M") for x in m6.index}),
        T.fattore_alta_volatilita)
    macro = macro_trend(m1)
    zone = zone_ob(resample_tf(m1, "M33"), 3, TIMEFRAMES["M33"])
    print(f"order block M33: {len(zone)} zone, "
          f"{int(zone.rbasso.notna().sum())} con zona raffinata", flush=True)
    trades = genera(m1, m6, alto, k, macro, zone)
    nl = sum(1 for t in trades if t["lato"] == "long")
    print(f"operazioni generate: {len(trades)} ({nl} long, {len(trades)-nl} short)",
          flush=True)

    vol = (m1.high - m1.low).groupby(m1.index.normalize()).median()
    periods = []
    for spec in specs:
        if spec.startswith("full:"):
            tf = spec.split(":", 1)[1]
            s = resample_tf(m1, tf)
            s["vwap"] = np.nan; s["h6"] = 0; s["h2"] = 0
            periods.append(pack(s, trades, vol=vol, label=f"full:{tf}"))
        else:
            month = pd.Period(spec, "M")
            lo_m = month.start_time.tz_localize("UTC")
            hi_m = (month + 1).start_time.tz_localize("UTC")
            s = m6[(m6.index >= lo_m) & (m6.index < hi_m)]
            sub = [t for t in trades if lo_m <= t["t_in"] < hi_m]
            periods.append(pack(s, sub, label=spec))
        p = periods[-1]
        print(f"  {p['id']}: {len(p['t']):,} candele, {len(p['trades'])} operazioni",
              flush=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"periods": periods, "rr": RR_GRID, "be": BE_GRID,
                   "stops": ["strutturale", "3 pt", "5 pt", "10 pt"],
                   "stop_punti": [None, 3, 5, 10],
                   "spread": SPREADS}, f, separators=(",", ":"))
    print(f"\n{out_path}: {os.path.getsize(out_path)/1e6:.2f} MB")


if __name__ == "__main__":
    main()
