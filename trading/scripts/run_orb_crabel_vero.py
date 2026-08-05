#!/usr/bin/env python3
"""Appendice BK: l'ORB di Crabel COMPLETO — i pattern di contrazione, non solo la rottura.

PERCHE' QUESTO SCRIPT ESISTE. Nell'appendice BJ ho implementato solo meta'
della strategia: la rottura dello Stretch, presa tutti i giorni. Il titolo del
libro di Crabel e' pero' "Day Trading with **Short Term Price Patterns** and
Opening Range Breakout": la rottura e' il grilletto, i pattern sono la
selezione. Prendere l'ORB ogni singolo giorno non e' il metodo di Crabel, e'
il metodo di Crabel privato della parte che sceglie quando operare.

E la selezione qui e' decisiva, perche' il conto dell'appendice BJ dice che:
  - LORDO  +0,051 R/op, +97 R, 7 anni positivi su 9  -> il vantaggio esiste
  - NETTO  -0,028 R/op                               -> i costi se lo mangiano
  - pareggio a ~0,32 punti indice di costo tondo
Con rischio mediano di 6,5 punti, mezzo punto di costo e' il 7,8% del rischio.
Un vantaggio di quella taglia non sopravvive a 230 operazioni l'anno: deve
essere concentrato su meno giornate, ed e' esattamente cio' che i pattern di
contrazione dichiarano di fare.

I PATTERN, presi dal libro (nessuno inventato qui, nessuna griglia):
  - NR4  : la giornata di ieri ha l'escursione piu' stretta delle ultime 4
  - NR7  : idem sulle ultime 7
  - ID   : inside day, ieri sta tutto dentro l'altroieri
  - ID/NR4: le due cose insieme (il setup piu' citato di Crabel)
L'idea e' una sola: la contrazione dell'escursione precede l'espansione. Si
opera dopo che il mercato si e' compresso, non tutti i giorni.

USCITE MESSE A CONFRONTO:
  - "chiusura": l'originale accademico, si tiene fino a fine sessione
  - "1:1"     : obiettivo a distanza pari al rischio (ipotesi dell'utente)

COSTI: non piu' un numero solo. Il risultato viene riportato a 0,25 / 0,35 /
0,50 punti indice tondi, perche' l'appendice BJ ha mostrato che e' li' che si
decide tutto e nascondere l'ipotesi dentro un numero fisso sarebbe disonesto.
Riferimento: sull'E-mini S&P lo spread e' quasi sempre un tick (0,25 punti) e
la commissione tonda vale ~0,08 punti; 0,25 e' quindi l'ottimista senza
slittamento, 0,35 il realistico, 0,50 il pessimista.

IPOTESI PRE-REGISTRATE, scritte prima di guardare:
  A. i giorni di contrazione hanno R/op LORDO piu' alto dei giorni qualunque
     (se no, il pattern non seleziona niente e la strategia e' morta);
  B. quel R/op resta positivo a 0,35 punti di costo su ricerca E verifica;
  C. l'uscita a fine sessione batte l'1:1 (l'ORB e' una scommessa sul momentum
     che continua, tagliarlo a 1:1 dovrebbe togliere la coda che paga).

Uso: python3 run_orb_crabel_vero.py
Scrive docs/studies/dati/orb_crabel_vero.parquet
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATI = os.environ.get("SPX_CSV", os.path.join(ROOT, "..", "dati_grezzi", "spx"))
FUSO = "America/New_York"
APERTURA, CHIUSURA = (9, 30), (16, 0)
GIORNI_STRETCH = 10
COSTI = [0.25, 0.35, 0.50]          # punti indice, andata e ritorno
RISCHIO_CONTO = 0.01                # 1% del conto per operazione, per il % annuo
RICERCA, VERIFICA = (2011, 2014), (2015, 2018)


def carica():
    file = sorted(glob.glob(os.path.join(DATI, "*.csv")))
    if not file:
        raise SystemExit(f"nessun CSV in {DATI}")
    d = pd.concat([pd.read_csv(f, sep=";", header=None,
                               names=["t", "open", "high", "low", "close", "vol"])
                   for f in file], ignore_index=True)
    t = pd.to_datetime(d.t, format="%Y%m%d %H%M%S")
    d = d.set_index(t.dt.tz_localize(FUSO, ambiguous="NaT",
                                     nonexistent="shift_forward"))
    d = d[d.index.notna()].drop(columns="t").sort_index()
    return d[~d.index.duplicated(keep="first")]


def sessioni(d):
    o = d.index.hour * 60 + d.index.minute
    dentro = (o >= APERTURA[0] * 60 + APERTURA[1]) & (o <= CHIUSURA[0] * 60 + CHIUSURA[1])
    s = d[dentro].copy()
    s["giorno"] = s.index.normalize().tz_localize(None)
    return s


def pattern(d):
    """I pattern di contrazione di Crabel, tutti misurati su giornate CHIUSE.

    Lo shift(1) non e' un dettaglio: il pattern deve essere noto la sera prima,
    altrimenti si sta leggendo il futuro. Qui NR4 su una riga significa "ieri
    aveva l'escursione piu' stretta delle sue ultime 4", ed e' un fatto gia'
    scritto quando la giornata di oggi apre.
    """
    r = d.massimo - d.minimo
    fuori = pd.DataFrame(index=d.index)
    fuori["NR4"] = (r == r.rolling(4).min())
    fuori["NR7"] = (r == r.rolling(7).min())
    fuori["ID"] = ((d.massimo <= d.massimo.shift(1)) & (d.minimo >= d.minimo.shift(1)))
    fuori["ID/NR4"] = fuori.ID & fuori.NR4
    return fuori.shift(1).fillna(False)


def percorri(alti, bassi, chiu, sopra, sotto, obiettivo):
    """Le due soglie: il primo toccato apre, l'altro e' lo stop.

    A parita' di minuto lo stop prevale sull'obiettivo, come ovunque nel
    progetto. Il risultato torna LORDO: i costi si applicano dopo, cosi' si
    puo' vedere quanto pesano invece di doverli credere sulla fiducia.
    """
    su = np.flatnonzero(alti >= sopra)
    giu = np.flatnonzero(bassi <= sotto)
    k_su = su[0] if len(su) else None
    k_giu = giu[0] if len(giu) else None
    if k_su is None and k_giu is None:
        return None
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
        k_stop = np.flatnonzero(l_ <= stop)
        bers = entry + obiettivo * rischio if obiettivo else None
        k_tp = np.flatnonzero(h_ >= bers) if bers else []
    else:
        k_stop = np.flatnonzero(h_ >= stop)
        bers = entry - obiettivo * rischio if obiettivo else None
        k_tp = np.flatnonzero(l_ <= bers) if bers else []
    ks = k_stop[0] if len(k_stop) else None
    kt = k_tp[0] if len(k_tp) else None
    if ks is not None and (kt is None or ks <= kt):
        r, motivo = -1.0, "stop"
    elif kt is not None:
        r, motivo = float(obiettivo), "obiettivo"
    else:
        r, motivo = (c_[-1] - entry) * verso / rischio, "chiusura"
    return {"verso": verso, "rischio": float(rischio), "lordo": r, "motivo": motivo}


def main():
    d = carica()
    s = sessioni(d)
    g = s.groupby("giorno")
    prof = pd.DataFrame({"apertura": g.open.first(), "massimo": g.high.max(),
                         "minimo": g.low.min(), "minuti": g.size()})
    prof = prof[prof.minuti >= 300]
    minore = np.minimum((prof.apertura - prof.massimo).abs(),
                        (prof.apertura - prof.minimo).abs())
    prof["stretch"] = minore.rolling(GIORNI_STRETCH).mean().shift(1)
    prof = prof.join(pattern(prof))
    nomi = ["NR4", "NR7", "ID", "ID/NR4"]
    print(f"sessioni {len(prof)} | frequenza dei pattern: "
          + "  ".join(f"{n} {prof[n].mean()*100:.1f}%" for n in nomi), flush=True)

    righe = []
    for giorno, gruppo in s.groupby("giorno"):
        if giorno not in prof.index:
            continue
        riga = prof.loc[giorno]
        st = riga.stretch
        if not np.isfinite(st) or st <= 0:
            continue
        alti, bassi, chiu = gruppo.high.values, gruppo.low.values, gruppo.close.values
        for eti, ob in [("chiusura", None), ("1:1", 1.0)]:
            e = percorri(alti, bassi, chiu, riga.apertura + st, riga.apertura - st, ob)
            if e is None:
                continue
            righe.append({"giorno": giorno, "anno": giorno.year, "uscita": eti,
                          **{n: bool(riga[n]) for n in nomi}, **e})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "orb_crabel_vero.parquet"), index=False)
    pd.set_option("display.width", 230)

    def conto(x, costo):
        """R/op al netto di un costo dato, e cosa vale in % annuo sul conto."""
        if not len(x):
            return None
        r = x.lordo - costo / x.rischio
        anni = x.anno.nunique()
        pa = r.groupby(x.anno).sum()
        return {"op": len(r), "op/anno": len(r) / anni, "R/op": r.mean(),
                "R": r.sum(), "%anno": r.sum() * RISCHIO_CONTO * 100 / anni,
                "anni+": int((pa > 0).sum()), "anni": anni}

    def tabella(sotto, costo):
        f = []
        for eti, sel in [("tutti i giorni", slice(None))] + [(n, n) for n in nomi]:
            x = sotto if isinstance(sel, slice) else sotto[sotto[sel]]
            c = conto(x, costo)
            if c:
                f.append({"selezione": eti, **c})
        return pd.DataFrame(f).set_index("selezione")

    print("\n=== ipotesi A: i pattern di contrazione selezionano davvero? (LORDO)")
    for eti, (da, a) in [("ricerca 2011-2014", RICERCA), ("verifica 2015-2018", VERIFICA)]:
        p = t[(t.anno >= da) & (t.anno <= a) & (t.uscita == "chiusura")]
        print(f"\n  {eti}, uscita a fine sessione, costo ZERO")
        print(tabella(p, 0.0).round(3).to_string())

    print("\n\n=== ipotesi B: regge ai costi veri? (uscita a fine sessione)")
    for costo in COSTI:
        print(f"\n  --- costo {costo:.2f} punti tondi")
        for eti, (da, a) in [("ricerca", RICERCA), ("verifica", VERIFICA)]:
            p = t[(t.anno >= da) & (t.anno <= a) & (t.uscita == "chiusura")]
            print(f"    {eti}")
            print(tabella(p, costo).round(3).to_string().replace("\n", "\n    "))

    print("\n\n=== ipotesi C: chiusura contro obiettivo 1:1 (costo 0,35)")
    for eti, (da, a) in [("ricerca", RICERCA), ("verifica", VERIFICA)]:
        print(f"\n  {eti}")
        for u in ("chiusura", "1:1"):
            p = t[(t.anno >= da) & (t.anno <= a) & (t.uscita == u)]
            tab = tabella(p, 0.35).round(3)
            print(f"    uscita {u}")
            print("    " + tab.to_string().replace("\n", "\n    "))


if __name__ == "__main__":
    main()
