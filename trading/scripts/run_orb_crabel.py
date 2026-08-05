#!/usr/bin/env python3
"""Appendice BI: l'ORB ORIGINALE di Crabel, non una versione riscritta per l'oro.

Richiesta dell'utente: non adattare la strategia, implementarla **com'e'** e
farci il bot; migliorarla dopo, se si puo'.

LA REGOLA ORIGINALE (Crabel 1990, "Day Trading with Short Term Price Patterns
and Opening Range Breakout"), presa alla lettera:

1. Si parte dal prezzo di APERTURA della giornata.
2. Si calcola lo **Stretch**: per ciascuno degli ultimi 10 giorni si prende il
   MINORE fra |apertura - massimo| e |apertura - minimo|, e se ne fa la media.
   E' la distanza tipica che il prezzo percorre dal lato "sbagliato" prima di
   decidersi: sotto quella soglia il movimento non e' informativo.
3. Si piazzano DUE ordini stop: acquisto a apertura + Stretch, vendita a
   apertura - Stretch.
4. Il primo che viene toccato apre la posizione. **L'altro diventa lo stop**
   di protezione. Una sola operazione al giorno.
5. Si chiude alla fine della giornata di contrattazione.

Nessun obiettivo: la versione accademica dell'ORB (Holmberg, Lonnbark,
Lundstrom 2013) e' esplicitamente una scommessa sul momentum intraday fino
alla chiusura, non una regola a bersaglio fisso.

QUAL E' L'APERTURA DELL'ORO. Qui non c'e' scelta da ottimizzare: la giornata
di contrattazione dell'oro va da **18:00 a 17:00 di New York** (ora locale,
quindi con l'ora legale che si sposta da sola). E' la pausa giornaliera vera,
misurata: l'unico momento in cui il mercato si ferma davvero. La ricognizione
sui diciotto anni ha anche trovato che i 120 minuti dopo quella riapertura
sono l'unica deriva che sopravvive al placebo, il che rende l'ancoraggio ancor
piu' difendibile.

IPOTESI PRE-REGISTRATE, scritte prima di guardare:
  A. la regola originale, presa alla lettera, ha risultato per operazione
     positivo al netto dei costi su entrambi i periodi;
  B. (dalla letteratura: Lundstrom, e Gao et al. sul Journal of Financial
     Economics) il vantaggio vive nei giorni ad ALTA volatilita' e sparisce o
     e' negativo in quelli tranquilli. Se questa struttura non c'e', il
     segnale probabilmente non c'e' nemmeno.

Le varianti con obiettivo 1:1,5 e 1:2 sono dichiarate SECONDARIE: servono a
rispondere alla domanda dell'utente sul semi-scalp, non sono la strategia
originale.

Uso: python3 run_orb_crabel.py [anno_da anno_a]
Scrive docs/studies/dati/orb_crabel.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FUSO = "America/New_York"
APERTURA, CHIUSURA = 18, 17        # la giornata dell'oro, in ora di New York
GIORNI_STRETCH = 10                # la media di Crabel
OBIETTIVI = [None, 1.5, 2.0]       # None = originale, gli altri sono secondari


def giornate(m1):
    """Spezza la serie nelle giornate VERE dell'oro: 18:00 -> 17:00 di New York.

    L'ora locale non e' un vezzo: la pausa cade sempre alle 17:00 di New York,
    quindi in UTC si sposta di un'ora con l'ora legale. Ancorare a un orario
    UTC fisso taglierebbe la giornata nel posto sbagliato per meta' dell'anno.
    """
    ny = m1.index.tz_convert(FUSO)
    # la giornata di contrattazione che comincia alle 18:00 porta la data del
    # giorno DOPO, come nella convenzione dei futures
    etichetta = (ny + pd.Timedelta(hours=24 - APERTURA)).normalize()
    return pd.Series(etichetta.tz_localize(None), index=m1.index)


def profilo_giornaliero(m1, etichette):
    """Apertura, massimo, minimo, chiusura di ogni giornata di contrattazione."""
    g = m1.groupby(etichette.values)
    d = pd.DataFrame({
        "apertura": g.open.first(), "massimo": g.high.max(),
        "minimo": g.low.min(), "chiusura": g.close.last(),
        "minuti": g.size(),
    })
    return d[d.minuti >= 600]          # scarta le giornate monche (festivita')


def stretch(d):
    """La misura di Crabel: media a 10 giorni del minore fra i due scarti
    dall'apertura. Calcolata sui giorni PRECEDENTI, mai su quello in corso."""
    minore = np.minimum((d.apertura - d.massimo).abs(),
                        (d.apertura - d.minimo).abs())
    return minore.rolling(GIORNI_STRETCH).mean().shift(1)


def percorri(apri, alti, bassi, chiu, sopra, sotto, obiettivo):
    """La giornata minuto per minuto, con le due soglie di Crabel.

    Il primo ordine toccato apre; l'altro e' lo stop. A parita' di minuto lo
    stop prevale sull'obiettivo, come in tutto il resto del progetto.
    """
    su = np.flatnonzero(alti >= sopra)
    giu = np.flatnonzero(bassi <= sotto)
    k_su = su[0] if len(su) else None
    k_giu = giu[0] if len(giu) else None
    if k_su is None and k_giu is None:
        return None                      # giornata senza rottura: niente
    if k_giu is None or (k_su is not None and k_su <= k_giu):
        verso, k, entry, stop = 1, k_su, sopra, sotto
    else:
        verso, k, entry, stop = -1, k_giu, sotto, sopra
    rischio = abs(entry - stop)
    if rischio <= 0:
        return None
    h_, l_, c_ = alti[k + 1:], bassi[k + 1:], chiu[k + 1:]
    if len(c_) < 2:
        return None
    if verso == 1:
        colpo_stop = np.flatnonzero(l_ <= stop)
        bersaglio = entry + obiettivo * rischio if obiettivo else None
        colpo_tp = np.flatnonzero(h_ >= bersaglio) if bersaglio else []
    else:
        colpo_stop = np.flatnonzero(h_ >= stop)
        bersaglio = entry - obiettivo * rischio if obiettivo else None
        colpo_tp = np.flatnonzero(l_ <= bersaglio) if bersaglio else []
    k_stop = colpo_stop[0] if len(colpo_stop) else None
    k_tp = colpo_tp[0] if len(colpo_tp) else None
    if k_stop is not None and (k_tp is None or k_stop <= k_tp):
        r, motivo = -1.0, "stop"
    elif k_tp is not None:
        r, motivo = float(obiettivo), "obiettivo"
    else:
        r, motivo = (c_[-1] - entry) * verso / rischio, "chiusura"
    return {"verso": verso, "entry": float(entry), "stop": float(stop),
            "rischio": float(rischio), "r": r - T.spread / rischio,
            "motivo": motivo}


def main():
    anni = None
    if len(sys.argv) > 2:
        anni = list(range(int(sys.argv[1]), int(sys.argv[2]) + 1))
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"), years=anni)
    et = giornate(m1)
    d = profilo_giornaliero(m1, et)
    d["stretch"] = stretch(d)
    # regime di volatilita': terzili dell'ampiezza dei 10 giorni precedenti,
    # noti PRIMA che la giornata cominci (ipotesi B della letteratura)
    amp = (d.massimo - d.minimo).rolling(10).mean().shift(1)
    # il regime va misurato CONTRO IL PROPRIO PASSATO RECENTE, non contro
    # diciotto anni: la volatilita' dell'oro e' cresciuta di due volte, quindi
    # terzili globali etichetterebbero "alto" quasi solo gli anni recenti e la
    # domanda della letteratura resterebbe senza risposta
    rango = amp.rolling(250, min_periods=120).rank(pct=True)
    d["regime"] = pd.cut(rango, [0, 1 / 3, 2 / 3, 1.01],
                         labels=["basso", "medio", "alto"])
    print(f"giornate di contrattazione: {len(d)}", flush=True)

    valori = m1[["open", "high", "low", "close"]].values
    et_v = et.values
    righe = []
    for giorno, riga in d.iterrows():
        s = riga.stretch
        if not np.isfinite(s) or s <= 0:
            continue
        sel = np.flatnonzero(et_v == np.datetime64(giorno))
        if len(sel) < 600:
            continue
        v = valori[sel]
        for ob in OBIETTIVI:
            e = percorri(v[:, 0], v[:, 1], v[:, 2], v[:, 3],
                         riga.apertura + s, riga.apertura - s, ob)
            if e is None:
                continue
            righe.append({"giorno": giorno, "anno": giorno.year,
                          "obiettivo": "originale" if ob is None else f"1:{ob}",
                          "stretch": float(s), "regime": riga.regime, **e})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "orb_crabel.parquet"), index=False)
    pd.set_option("display.width", 220)

    def riassunto(x):
        r = x.r
        pa = r.groupby(x.anno).sum() if "anno" in x.columns else r
        return pd.Series({"op": len(r), "R": r.sum(), "r_op": r.mean(),
                          "vinte%": (r > 0).mean() * 100,
                          "stop%": (x.motivo == "stop").mean() * 100,
                          "anni+": int((pa > 0).sum()), "anni": pa.size})

    print("\n=== ipotesi A: la regola originale, e le varianti con obiettivo")
    for eti, (da, a) in [("2009-2019", (2009, 2019)), ("2020-2026", (2020, 2026))]:
        p = t[(t.anno >= da) & (t.anno <= a)]
        print(f"\n  {eti}")
        print(p.groupby("obiettivo").apply(riassunto)
              .round(3).to_string())

    print("\n=== ipotesi B: il vantaggio vive nei giorni ad alta volatilita'?")
    for eti, (da, a) in [("2009-2019", (2009, 2019)), ("2020-2026", (2020, 2026))]:
        p = t[(t.anno >= da) & (t.anno <= a) & (t.obiettivo == "originale")]
        print(f"\n  {eti} (solo regola originale)")
        print(p.groupby("regime", observed=True).apply(riassunto)
              .round(3).to_string())

    print("\n=== per anno, regola originale")
    p = t[t.obiettivo == "originale"]
    print(p.groupby("anno").apply(riassunto).round(2).to_string())


if __name__ == "__main__":
    main()
