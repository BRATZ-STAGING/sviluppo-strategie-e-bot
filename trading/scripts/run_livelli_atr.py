#!/usr/bin/env python3
"""Appendice AZ: tutti i livelli del progetto su 18 anni, misurati in ATR.

Le famiglie di livelli che l'utente usa davvero, ciascuna resa una BANDA di
prezzo e ciascuna misurata in unita' di ATR giornaliero, cosi' la stessa
regola vale con l'oro a 1.000 e a 5.000 dollari:

  ob pieno / ob raffinato   zone order block (definizione del progetto)
  poc ieri                  prezzo piu' scambiato della giornata precedente
  va ieri                   estremi dell'area di valore (70% del volume)
  vuoto ieri                fasce a volume basso, i "buchi" di liquidita'

Tre modi di interagire con una banda, tutti causali e decisi alla chiusura
della candela:

  reazione   il prezzo entra nella banda e chiude fuori, dal lato di partenza
  rottura    il prezzo chiude oltre la banda venendo dall'altra parte
  retest     dopo una rottura torna sulla banda e chiude di nuovo oltre

Stop e obiettivo in ATR: stop = q x ATR giornaliero, obiettivo = rr volte lo
stop. Uscita a fine giornata come nella strategia in vigore (niente swap).

PROTOCOLLO, fissato prima di guardare i numeri:
  1. la ricerca si fa sul 2009-2019, la verifica sul 2020-2026;
  2. ogni cella ha il suo PLACEBO: gli stessi livelli spostati a caso di
     0,2-0,6 ATR, che conserva quante volte il prezzo ci passa vicino ma
     distrugge il significato del livello;
  3. si contano i sopravvissuti, non si racconta il migliore.

Uso: python3 run_livelli_atr.py [anno_da anno_a]
Scrive docs/studies/dati/livelli_atr.parquet (eventi) e ..._celle.parquet
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
# il dettaglio per evento pesa decine di MB: fuori dal repository
GREZZI = os.environ.get("GREZZI", os.path.join(ROOT, "..", "dati_grezzi"))
TF_USATI = ["M33", "M66", "H2", "H6"]
MODI = ["reazione", "rottura", "retest"]
STOP_ATR = [0.25, 0.5, 1.0]           # stop in frazioni di ATR giornaliero
OBIETTIVI = [2.0, 3.0, 5.0, 10.0]
BANDA_ATR = 0.05                      # spessore dato ai livelli puntuali
VALIDITA = 30                         # candele di vita di una zona OB
FINESTRA_RETEST = 10                  # candele entro cui un ritorno e' retest
ATTESA = 60                           # minuti fra due eventi della stessa famiglia
ORA_DA, ORA_A, ORA_CHIUSURA = 7, 19, 21
SEME = 20260804


# --------------------------------------------------------------------------
# livelli
def profilo_giorno(m1, atr_g):
    """Per ogni giornata: POC, estremi dell'area di valore, fasce vuote.

    Tutto in bin larghi 0,05 ATR, cosi' la risoluzione del profilo segue la
    volatilita' invece di essere fissa in dollari.
    """
    out = {}
    tipico = ((m1.high + m1.low + m1.close) / 3).values
    vol = m1.volume.values.astype(float)
    vol[~np.isfinite(vol) | (vol <= 0)] = 1.0
    giorni = m1.index.normalize()
    for g, sel in m1.groupby(giorni).indices.items():
        a = atr_g.get(g, np.nan)
        if not np.isfinite(a) or a <= 0 or len(sel) < 200:
            continue
        passo = a * BANDA_ATR
        liv = np.round(tipico[sel] / passo).astype(np.int64)
        unici, inv = np.unique(liv, return_inverse=True)
        somme = np.zeros(len(unici))
        np.add.at(somme, inv, vol[sel])
        prezzi = unici * passo
        poc = float(prezzi[somme.argmax()])
        # area di valore: i bin piu' scambiati fino al 70% del volume
        ordine = np.argsort(somme)[::-1]
        cumulato = np.cumsum(somme[ordine])
        dentro = prezzi[ordine[:np.searchsorted(cumulato, .7 * somme.sum()) + 1]]
        # fasce vuote: sotto il 15% del massimo, unite se contigue
        soglia = somme.max() * .15
        vuoti, ini = [], None
        for i, p in enumerate(prezzi):
            basso = somme[i] < soglia
            if basso and ini is None:
                ini = p
            if not basso and ini is not None:
                if prezzi[i - 1] - ini >= a * .10:
                    vuoti.append((ini, float(prezzi[i - 1])))
                ini = None
        out[g] = {"poc": poc, "val": float(dentro.min()),
                  "vah": float(dentro.max()), "vuoti": vuoti, "atr": float(a)}
    return out


def scostamento(rng, atr):
    """Lo spostamento del placebo: 0,2-0,6 ATR da una parte o dall'altra.

    Due tarature imparate a spese di misure sbagliate. Va estratto UNA VOLTA
    per livello: estrarlo a ogni barra fa ballare la banda e le condizioni che
    guardano la barra precedente non si formano mai. E deve essere PICCOLO: a
    0,5-2 ATR il livello finto finisce spesso fuori dal range della giornata,
    il placebo produce un quarto degli eventi e il confronto non vale niente.
    Un POC spostato di un terzo di ATR non e' piu' il POC, ma sta ancora dove
    il prezzo passa.
    """
    return rng.uniform(.2, .6) * atr * rng.choice([-1., 1.])


def bande_per_giorno(prof, atr_di_giorno, finto, rng):
    """Le bande non-OB di ogni giornata; quelle di g vengono dal giorno PRIMA."""
    out = {}
    for g, p in prof.items():
        atr = atr_di_giorno.get(g)
        if atr is None or not np.isfinite(atr) or atr <= 0:
            continue
        mezzo = atr * BANDA_ATR / 2
        b = [("poc ieri", p["poc"] - mezzo, p["poc"] + mezzo),
             ("va ieri", p["val"] - mezzo, p["val"] + mezzo),
             ("va ieri", p["vah"] - mezzo, p["vah"] + mezzo)]
        b += [("vuoto ieri", v[0], v[1]) for v in p["vuoti"]]
        if finto:
            b = [(f, lo + (d := scostamento(rng, atr)), hi + d) for f, lo, hi in b]
        out[g] = [(f, lo, hi, 0) for f, lo, hi in b]
    return out


def bande_ob(tfd, tf, finto, rng, atr_bar):
    """Zone order block del timeframe, piene e raffinate, con validita'."""
    passo = pd.Timedelta(TIMEFRAMES[tf])
    z = zone_ob(tfd, T.frattale_k, passo, validita=VALIDITA)
    vuoto = pd.DataFrame(columns=["famiglia", "da", "a", "basso", "alto", "lato"])
    if z.empty:
        return vuoto
    scad = z.attiva_da + VALIDITA * passo
    posizione = {t: i for i, t in enumerate(tfd.index)}
    righe = []
    for k, r in z.iterrows():
        d = 0.0
        if finto:
            i = posizione.get(r.attiva_da - passo, 0)
            a_ = atr_bar[min(i, len(atr_bar) - 1)]
            if not np.isfinite(a_) or a_ <= 0:
                continue
            d = scostamento(rng, a_)
        righe.append({"famiglia": "ob pieno", "da": r.attiva_da, "a": scad[k],
                      "basso": r.basso + d, "alto": r.alto + d,
                      "lato": int(r.lato)})
        if np.isfinite(r.rbasso) and np.isfinite(r.ralto):
            righe.append({"famiglia": "ob raffinato", "da": r.attiva_da,
                          "a": scad[k], "basso": float(r.rbasso) + d,
                          "alto": float(r.ralto) + d, "lato": int(r.lato)})
    return pd.DataFrame(righe) if righe else vuoto


# --------------------------------------------------------------------------
# eventi
def eventi_tf(tfd, tf, bande_giorno, atr_bar, ob):
    """Tutti gli eventi di interazione con una banda, su un timeframe."""
    idx = tfd.index
    hi, lo, cl = tfd.high.values, tfd.low.values, tfd.close.values
    giorni = idx.normalize()
    ore = idx.hour
    tempi = idx.values.astype("datetime64[ns]")
    if len(ob):
        ob_da = ob.da.values.astype("datetime64[ns]")
        ob_a = ob.a.values.astype("datetime64[ns]")
        ob_v = ob[["basso", "alto", "lato"]].values
        ob_f = ob.famiglia.values
    rotture = {}                       # chiave del livello -> ultima barra rotta
    ultimo = {}                        # (famiglia, modo, lato) -> ultimo minuto
    out = []
    for i in range(1, len(tfd)):
        if not (ORA_DA <= ore[i] < ORA_A):
            continue
        a_ = atr_bar[i]
        if not np.isfinite(a_) or a_ <= 0:
            continue
        bande = list(bande_giorno.get(giorni[i], ()))
        if len(ob):
            for k in np.flatnonzero((ob_da <= tempi[i]) & (ob_a > tempi[i])):
                bande.append((ob_f[k], ob_v[k, 0], ob_v[k, 1], int(ob_v[k, 2])))
        for fam, b, t, lato_zona in bande:
            chiave = (fam, round(b, 2), round(t, 2))
            for modo in MODI:
                seg = interazione(modo, hi, lo, cl, i, b, t,
                                  rotture.get(chiave))
                if seg == 0:
                    continue
                if lato_zona and seg != lato_zona:
                    continue           # su una zona OB si opera solo concordi
                q = ultimo.get((fam, modo, seg))
                if q is not None and (tempi[i] - q) / np.timedelta64(1, "m") < ATTESA:
                    continue
                ultimo[(fam, modo, seg)] = tempi[i]
                # l'istante e' la CHIUSURA della candela, non l'apertura: e'
                # allora che si conosce il prezzo d'ingresso. Con l'apertura
                # l'operazione ripercorrerebbe la candela stessa sapendo gia'
                # come finisce, e il vantaggio cresce col timeframe.
                out.append({"tf": tf, "famiglia": fam, "modo": modo,
                            "lato": seg, "barra": i,
                            "time": idx[i] + pd.Timedelta(TIMEFRAMES[tf]),
                            "entry": float(cl[i]), "atr": float(a_)})
            if cl[i] > t and cl[i - 1] <= t:
                rotture[chiave] = i
            elif cl[i] < b and cl[i - 1] >= b:
                rotture[chiave] = i
    return out


def interazione(modo, hi, lo, cl, i, b, t, rotta):
    """+1 long, -1 short, 0 niente. Tutto deciso alla chiusura della barra i."""
    if modo == "reazione":
        if lo[i] <= t and cl[i] > t and cl[i - 1] > t:
            return 1
        if hi[i] >= b and cl[i] < b and cl[i - 1] < b:
            return -1
        return 0
    if modo == "rottura":
        if cl[i] > t and cl[i - 1] <= t:
            return 1
        if cl[i] < b and cl[i - 1] >= b:
            return -1
        return 0
    # retest: la rottura c'e' gia' stata di recente, ora si torna e si respinge
    if rotta is None or i - rotta > FINESTRA_RETEST or i == rotta:
        return 0
    if cl[rotta] > t and lo[i] <= t and cl[i] > t:
        return 1
    if cl[rotta] < b and hi[i] >= b and cl[i] < b:
        return -1
    return 0


def esiti(ev, m1, idx_ns):
    """Per ogni evento l'esito di ogni coppia (stop in ATR, obiettivo)."""
    hi, lo = m1.high.values, m1.low.values
    # ATTENZIONE: asi8 restituisce interi nell'unita' PROPRIA dell'indice. Se
    # questi timestamp non sono in nanosecondi come idx_ns, ogni ricerca cade a
    # zero e tutti gli esiti restano vuoti senza che niente segnali l'errore.
    quando = pd.DatetimeIndex([e["time"] for e in ev]).as_unit("ns")
    fine_g = (quando.normalize() + pd.Timedelta(hours=ORA_CHIUSURA)).as_unit("ns")
    inizio = (quando + pd.Timedelta(minutes=1)).as_unit("ns")
    a = np.searchsorted(idx_ns, inizio.asi8)
    b = np.searchsorted(idx_ns, fine_g.asi8)
    cl = m1.close.values
    fuori = {f"{q}|{rr}": np.full(len(ev), np.nan)
             for q in STOP_ATR for rr in OBIETTIVI}
    for n, e in enumerate(ev):
        i0, i1 = int(a[n]), int(b[n])
        if i1 - i0 < 2:
            continue
        h_, l_, c_ = hi[i0:i1], lo[i0:i1], cl[i0:i1]
        segno = e["lato"]
        if segno == 1:
            su, giu = h_ - e["entry"], e["entry"] - l_
        else:
            su, giu = e["entry"] - l_, h_ - e["entry"]
        finale = (c_[-1] - e["entry"]) * segno
        for q in STOP_ATR:
            r = q * e["atr"]
            if r <= 0:
                continue
            costo = T.spread / r
            fav, sfav = su / r, giu / r
            colpo_stop = np.flatnonzero(sfav >= 1.0)
            k_stop = colpo_stop[0] if len(colpo_stop) else None
            for rr in OBIETTIVI:
                colpo_tp = np.flatnonzero(fav >= rr)
                k_tp = colpo_tp[0] if len(colpo_tp) else None
                if k_stop is not None and (k_tp is None or k_stop <= k_tp):
                    x = -1.0
                elif k_tp is not None:
                    x = rr
                else:
                    x = finale / r
                fuori[f"{q}|{rr}"][n] = x - costo
    return fuori


# --------------------------------------------------------------------------
def raccogli(m1, finto, seme):
    rng = np.random.default_rng(seme)
    atr = daily_atr(m1, 14)
    atr_g = {k: v for k, v in atr.items()}
    prof_ieri = profilo_giorno(m1, atr_g)
    # il profilo di UNA giornata si usa il giorno dopo: si sposta avanti
    chiavi = sorted(prof_ieri)
    prof = {chiavi[i + 1]: prof_ieri[chiavi[i]] for i in range(len(chiavi) - 1)}
    bande_giorno = bande_per_giorno(prof, atr_g, finto, rng)
    idx_ns = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    tutti = []
    for tf in TF_USATI:
        tfd = resample_tf(m1, tf)
        atr_bar = atr.reindex(tfd.index.normalize()).ffill().values
        ob = bande_ob(tfd, tf, finto, rng, atr_bar)
        ev = eventi_tf(tfd, tf, bande_giorno, atr_bar, ob)
        if not ev:
            continue
        col = esiti(ev, m1, idx_ns)
        t = pd.DataFrame(ev)
        for k, v in col.items():
            t[f"r|{k}"] = v
        vuoti = t[[f"r|{k}" for k in col]].notna().sum().sum()
        if vuoti == 0:                 # meglio fermarsi che pubblicare zeri
            raise SystemExit(f"{tf}: nessun esito calcolato, controllare gli indici")
        t["anno"] = t.time.dt.year
        tutti.append(t)
        print(f"  {tf}: {len(ev)} eventi", flush=True)
    return pd.concat(tutti, ignore_index=True) if tutti else pd.DataFrame()


def main():
    anni = None
    if len(sys.argv) > 2:
        anni = list(range(int(sys.argv[1]), int(sys.argv[2]) + 1))
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"), years=anni)
    print("livelli veri:", flush=True)
    veri = raccogli(m1, False, SEME)
    print("placebo:", flush=True)
    falsi = raccogli(m1, True, SEME + 1)
    veri["vero"], falsi["vero"] = True, False
    t = pd.concat([veri, falsi], ignore_index=True)
    d = os.path.join(ROOT, "docs", "studies", "dati")
    os.makedirs(GREZZI, exist_ok=True)
    t.to_parquet(os.path.join(GREZZI, "livelli_atr.parquet"), index=False)
    print(f"\n{len(veri)} eventi veri, {len(falsi)} placebo -> livelli_atr.parquet")


if __name__ == "__main__":
    main()
