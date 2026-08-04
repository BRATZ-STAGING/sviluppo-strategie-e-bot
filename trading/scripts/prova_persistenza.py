#!/usr/bin/env python3
"""Prova dell'ipotesi "persistenza": seguire la direzione, senza livelli.

Regola nuda: se negli ultimi N minuti il prezzo si e' mosso di almeno X (in
ATR giornaliero causale) si entra NELLA STESSA DIREZIONE all'apertura del
minuto successivo alla chiusura del minuto di segnale. Stop a S ATR,
obiettivo a RR*S ATR, scadenza a H minuti, chiusura forzata alle 21:00 UTC.

Serve a stabilire se esiste un vantaggio direzionale grezzo in qualche
momento della giornata. Non c'e' nessun livello, nessun VWAP, nessun profilo.

Convenzioni rispettate (ognuna e' gia' costata una misura sbagliata):
  - CAUSALITA': il segnale e' letto alla CHIUSURA del minuto, l'ingresso e'
    all'APERTURA del minuto dopo; l'ATR e' quello di daily_atr, gia' shiftato.
  - COSTO: 0,30 $ andata+ritorno, cioe' 0,30/(S*ATR) in R, sempre sottratto.
  - Nello stesso minuto lo STOP vince sull'obiettivo.
  - Tutto in R. Divisione obbligatoria 2009-2019 / 2020-2026.
  - Scomposizione obiettivo / stop / scadenza sempre riportata, piu' il
    controllo di assurdita' (un obiettivo lontano non puo' essere raggiunto
    piu' spesso di uno stop vicino).
  - PLACEBO: stessi istanti di ingresso, direzione tirata a sorte. Qui non
    c'e' un livello da spostare, quindi il finto giusto e' la direzione.

Uso:  python3 trading/scripts/prova_persistenza.py
Il dettaglio per operazione va in /workspace/dati_grezzi/persistenza/.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/workspace/sviluppo-strategie-e-bot/trading")

from framework.data import load_m1  # noqa: E402
from framework.volatility import daily_atr  # noqa: E402

DATI = "/workspace/sviluppo-strategie-e-bot/data/XAUUSD_M1"
USCITA = "/workspace/dati_grezzi/persistenza"

SPREAD = 0.30          # dollari, andata e ritorno
ORIZZONTE = 120        # minuti di scadenza
FINE_GIORNO = 21 * 60  # 21:00 UTC: oltre c'e' il rollover, niente swap
ORE_AMMESSE = range(0, 20)

# griglia dichiarata in anticipo
ENNE = [5, 15, 30, 60, 120]
ICS = [0.05, 0.10, 0.20, 0.40]
STOP = [0.10, 0.20]
RRS = [1.5, 2.0]

# configurazione primaria pre-registrata (NON scelta guardando i risultati)
PRIM = dict(n=30, x=0.20, s=0.20, rr=1.5, ore=(12, 13, 14, 15))

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)


# --------------------------------------------------------------------------
# 1. griglia al minuto continua (i buchi diventano NaN: nessun tocco possibile)
# --------------------------------------------------------------------------

def costruisci_griglia():
    m1 = load_m1(DATI)
    t = m1.index.astype("int64").to_numpy() // 60_000  # minuti interi da epoch
    t0, t1 = t[0], t[-1]
    n = int(t1 - t0) + 1 + ORIZZONTE + 2
    pos = (t - t0).astype(np.int64)

    g = {}
    for c in ("open", "high", "low", "close"):
        a = np.full(n, np.nan)
        a[pos] = m1[c].to_numpy(dtype=float)
        g[c] = a

    # prezzo di riferimento per il rendimento passato e per l'uscita a
    # scadenza: ultimo prezzo noto (riempimento in avanti, causale)
    chiuso = pd.Series(g["close"]).ffill().to_numpy()

    # ATR giornaliero causale mappato sul minuto
    atr = daily_atr(m1, 14)
    giorno_min = (np.arange(n, dtype=np.int64) + t0) // 1440   # giorni da epoch
    gio_atr = (atr.index.astype("int64").to_numpy() // 86_400_000)
    mappa = np.full(int(giorno_min.max()) + 2, np.nan)
    ok = (gio_atr >= 0) & (gio_atr < len(mappa))
    mappa[gio_atr[ok]] = atr.to_numpy(dtype=float)[ok]
    atr_min = mappa[giorno_min]

    minuto_assoluto = np.arange(n, dtype=np.int64) + t0
    minuto_del_giorno = (minuto_assoluto % 1440).astype(np.int32)
    ora_assoluta = minuto_assoluto // 60
    anno = pd.to_datetime(minuto_assoluto * 60_000_000_000,
                          utc=True).year.to_numpy().astype(np.int16)

    return g, chiuso, atr_min, minuto_del_giorno, ora_assoluta, anno, n


# --------------------------------------------------------------------------
# 2. segnali: primo segnale di ogni ora solare
# --------------------------------------------------------------------------

def genera_segnali(chiuso, atr_min, mdg, ora_abs, n, enne, ics):
    """Indici di INGRESSO (minuto successivo al segnale) e verso."""
    r = np.full(n, np.nan)
    r[enne:] = chiuso[enne:] - chiuso[:-enne]
    soglia = ics * atr_min

    lungo = r >= soglia
    corto = r <= -soglia
    vivo = np.isfinite(r) & np.isfinite(atr_min) & (lungo | corto)

    idx_seg = np.flatnonzero(vivo)
    if idx_seg.size == 0:
        return idx_seg, idx_seg
    idx_ent = idx_seg + 1                       # ingresso al minuto dopo
    buono = (
        np.isfinite(chiuso[idx_seg])            # il minuto di segnale e' quotato
        & np.isfinite(atr_min[idx_ent])
        & (mdg[idx_seg] // 60 < 20)             # ore ammesse
        & (mdg[idx_ent] < FINE_GIORNO)          # resta spazio prima delle 21
    )
    idx_seg, idx_ent = idx_seg[buono], idx_ent[buono]

    # un solo ingresso per ora solare: si prende il PRIMO segnale dell'ora
    _, primo = np.unique(ora_abs[idx_seg], return_index=True)
    idx_seg, idx_ent = idx_seg[primo], idx_ent[primo]

    verso = np.where(lungo[idx_seg], 1.0, -1.0)
    return idx_ent, verso


# --------------------------------------------------------------------------
# 3. corsa fra barriere
# --------------------------------------------------------------------------

def corri(g, chiuso, atr_min, mdg, idx_ent, verso, s, rr, blocco=25_000):
    """Ritorna R lordo, esito (0 obiettivo, 1 stop, 2 scadenza) e costo in R."""
    ne = idx_ent.size
    r_lordo = np.empty(ne)
    esito = np.empty(ne, dtype=np.int8)
    ingresso = g["open"][idx_ent]
    rischio = s * atr_min[idx_ent]
    lun = np.minimum(ORIZZONTE, FINE_GIORNO - mdg[idx_ent]).astype(np.int64)

    stop = ingresso - verso * rischio
    obiet = ingresso + verso * rr * rischio
    jj = np.arange(ORIZZONTE)

    for a in range(0, ne, blocco):
        b = min(a + blocco, ne)
        sl = idx_ent[a:b, None] + jj[None, :]
        hi = g["high"][sl]
        lo = g["low"][sl]
        dentro = jj[None, :] < lun[a:b, None]

        v = verso[a:b, None]
        # con v=+1: obiettivo su high, stop su low; con v=-1 si scambiano
        tocco_ob = np.where(v > 0, hi >= obiet[a:b, None], lo <= obiet[a:b, None])
        tocco_st = np.where(v > 0, lo <= stop[a:b, None], hi >= stop[a:b, None])
        tocco_ob &= dentro
        tocco_st &= dentro

        j_ob = np.where(tocco_ob.any(1), tocco_ob.argmax(1), ORIZZONTE + 1)
        j_st = np.where(tocco_st.any(1), tocco_st.argmax(1), ORIZZONTE + 1)

        # lo stop vince i pareggi: <= e non <
        vince_st = j_st <= j_ob
        prima_ob = (j_ob <= ORIZZONTE) & ~vince_st
        prima_st = (j_st <= ORIZZONTE) & vince_st
        scaduto = ~(prima_ob | prima_st)

        idx_fine = idx_ent[a:b] + lun[a:b] - 1
        r_sc = verso[a:b] * (chiuso[idx_fine] - ingresso[a:b]) / rischio[a:b]

        blk = np.where(prima_ob, rr, np.where(prima_st, -1.0, r_sc))
        r_lordo[a:b] = blk
        esito[a:b] = np.where(prima_ob, 0, np.where(prima_st, 1, 2))

    costo = SPREAD / rischio
    return r_lordo, esito, costo


# --------------------------------------------------------------------------
# 4. aggregazione
# --------------------------------------------------------------------------

def riassunto(df, etichetta=""):
    out = []
    for nome, per in (("2009-2019", (2009, 2019)), ("2020-2026", (2020, 2026))):
        d = df[(df.anno >= per[0]) & (df.anno <= per[1])]
        if len(d) == 0:
            continue
        out.append(dict(
            campo=etichetta, periodo=nome, n=len(d),
            r_lordo=d.r_lordo.mean(), r_netto=d.r_netto.mean(),
            es=d.r_netto.std(ddof=1) / np.sqrt(len(d)),
            costo=d.costo.mean(),
            p_ob=(d.esito == 0).mean(), p_st=(d.esito == 1).mean(),
            p_sc=(d.esito == 2).mean(),
        ))
    return out


def main():
    os.makedirs(USCITA, exist_ok=True)
    g, chiuso, atr_min, mdg, ora_abs, anno, n = costruisci_griglia()

    # ---------------- griglia completa N x X x S x RR, per ora ----------------
    righe_griglia = []
    righe_ora = []
    dett_primaria = None

    for enne in ENNE:
        for ics in ICS:
            idx_ent, verso = genera_segnali(chiuso, atr_min, mdg, ora_abs, n, enne, ics)
            if idx_ent.size == 0:
                continue
            ora = (mdg[idx_ent] // 60).astype(np.int8)
            an = anno[idx_ent]
            for s in STOP:
                for rr in RRS:
                    r_l, es, co = corri(g, chiuso, atr_min, mdg, idx_ent, verso, s, rr)
                    ok = np.isfinite(r_l)
                    df = pd.DataFrame(dict(
                        anno=an[ok], ora=ora[ok], verso=verso[ok],
                        r_lordo=r_l[ok], costo=co[ok], esito=es[ok],
                    ))
                    df["r_netto"] = df.r_lordo - df.costo

                    for pe, (a0, a1) in (("vecchio", (2009, 2019)),
                                         ("nuovo", (2020, 2026))):
                        d = df[(df.anno >= a0) & (df.anno <= a1)]
                        if not len(d):
                            continue
                        righe_griglia.append(dict(
                            N=enne, X=ics, S=s, RR=rr, periodo=pe, n=len(d),
                            r_lordo=d.r_lordo.mean(), r_netto=d.r_netto.mean(),
                            es=d.r_netto.std(ddof=1) / np.sqrt(len(d)),
                        ))
                        # dettaglio per ora solo sulla forma primaria di S/RR
                        if s == PRIM["s"] and rr == PRIM["rr"]:
                            for o, dd in d.groupby("ora"):
                                righe_ora.append(dict(
                                    N=enne, X=ics, periodo=pe, ora=int(o),
                                    n=len(dd), r_lordo=dd.r_lordo.mean(),
                                    r_netto=dd.r_netto.mean(),
                                ))
                    if (enne == PRIM["n"] and ics == PRIM["x"]
                            and s == PRIM["s"] and rr == PRIM["rr"]):
                        dett_primaria = df

    grid = pd.DataFrame(righe_griglia)
    ore = pd.DataFrame(righe_ora)
    grid.to_parquet(f"{USCITA}/griglia.parquet")
    ore.to_parquet(f"{USCITA}/per_ora.parquet")
    dett_primaria.to_parquet(f"{USCITA}/primaria_operazioni.parquet")

    # ---------------- configurazione primaria ----------------
    p = dett_primaria[dett_primaria.ora.isin(PRIM["ore"])].copy()
    p.to_parquet(f"{USCITA}/primaria_ore1215.parquet")

    print("\n=== IPOTESI PRIMARIA PRE-REGISTRATA ===")
    print(f"N={PRIM['n']}' X={PRIM['x']} ATR S={PRIM['s']} ATR RR=1:{PRIM['rr']} "
          f"ore {PRIM['ore'][0]}-{PRIM['ore'][-1]+1} UTC, orizzonte {ORIZZONTE}'")
    print(pd.DataFrame(riassunto(p, "seguire")).round(4).to_string(index=False))

    # controllo di assurdita': con RR>1 l'obiettivo deve essere piu' raro
    for nome, (a0, a1) in (("2009-2019", (2009, 2019)), ("2020-2026", (2020, 2026))):
        d = p[(p.anno >= a0) & (p.anno <= a1)]
        assurdo = (d.esito == 0).mean() > (d.esito == 1).mean()
        print(f"  controllo assurdita' {nome}: p_obiettivo({(d.esito==0).mean():.3f})"
              f" > p_stop({(d.esito==1).mean():.3f}) ? {'ALLARME' if assurdo else 'no, ok'}")

    # ---------------- rovescio e placebo ----------------
    idx_ent, verso = genera_segnali(chiuso, atr_min, mdg, ora_abs, n,
                                    PRIM["n"], PRIM["x"])
    ora = (mdg[idx_ent] // 60).astype(np.int8)
    sel = np.isin(ora, PRIM["ore"])
    controlli = []
    rng = np.random.default_rng(20260804)
    varianti = {
        "seguire": verso,
        "contrastare": -verso,
        "placebo (verso a caso)": rng.choice([-1.0, 1.0], size=verso.size),
    }
    for nome, v in varianti.items():
        r_l, es, co = corri(g, chiuso, atr_min, mdg, idx_ent, v, PRIM["s"], PRIM["rr"])
        ok = np.isfinite(r_l) & sel
        df = pd.DataFrame(dict(anno=anno[idx_ent][ok], r_lordo=r_l[ok],
                               costo=co[ok], esito=es[ok]))
        df["r_netto"] = df.r_lordo - df.costo
        controlli += riassunto(df, nome)
    ctrl = pd.DataFrame(controlli)
    print("\n=== ROVESCIO E PLACEBO (stessi istanti, stesse barriere) ===")
    print(ctrl.round(4).to_string(index=False))

    # confronto APPAIATO seguire - placebo: stessi ingressi, stesse barriere,
    # cambia solo il verso. E' il test che dice se il verso porta informazione.
    r_vero, _, _ = corri(g, chiuso, atr_min, mdg, idx_ent, verso,
                         PRIM["s"], PRIM["rr"])
    r_plac, _, _ = corri(g, chiuso, atr_min, mdg, idx_ent,
                         varianti["placebo (verso a caso)"], PRIM["s"], PRIM["rr"])
    r_uno, _, _ = corri(g, chiuso, atr_min, mdg, idx_ent,
                        np.ones_like(verso), PRIM["s"], PRIM["rr"])
    an_e = anno[idx_ent]
    print("\n=== CONFRONTO APPAIATO seguire - placebo (lordo) e deriva incondizionata ===")
    for nome, (a0, a1) in (("2009-2019", (2009, 2019)), ("2020-2026", (2020, 2026))):
        m = sel & (an_e >= a0) & (an_e <= a1) & np.isfinite(r_vero) & np.isfinite(r_plac)
        d = r_vero[m] - r_plac[m]
        es_d = d.std(ddof=1) / np.sqrt(m.sum())
        mu = sel & (an_e >= a0) & (an_e <= a1) & np.isfinite(r_uno)
        print(f"  {nome}: differenza {d.mean():+.4f} R (es {es_d:.4f}, "
              f"t={d.mean()/es_d:+.2f}, n={m.sum()}) | sempre-long lordo "
              f"{r_uno[mu].mean():+.4f} R  (controllo: deve essere piccolo)")

    # ---------------- ore locali di New York ----------------
    # l'orologio del mercato e' locale: le ore UTC sdoppiano gli eventi
    ora_ny = (pd.DatetimeIndex(pd.to_datetime(ora_abs[idx_ent] * 3_600_000_000_000,
                                              utc=True))
              .tz_convert("America/New_York").hour.to_numpy())
    dfl = pd.DataFrame(dict(anno=an_e, ora_ny=ora_ny, r_lordo=r_vero,
                            costo=SPREAD / (PRIM["s"] * atr_min[idx_ent])))
    dfl = dfl[np.isfinite(dfl.r_lordo)]
    dfl["r_netto"] = dfl.r_lordo - dfl.costo
    dfl["periodo"] = np.where(dfl.anno <= 2019, "vecchio", "nuovo")
    tl = dfl.pivot_table(index="ora_ny", columns="periodo",
                         values=["r_lordo", "r_netto"], aggfunc="mean")
    tl[("n", "vecchio")] = dfl[dfl.periodo == "vecchio"].groupby("ora_ny").size()
    tl[("n", "nuovo")] = dfl[dfl.periodo == "nuovo"].groupby("ora_ny").size()
    print("\n=== R PER ORA LOCALE DI NEW YORK (N=30, X=0,20, S=0,20, RR=1:1,5) ===")
    print(tl.round(3).to_string())
    cl = dfl.pivot_table(index="ora_ny", columns="periodo", values="r_netto")
    bl = cl[(cl.get("vecchio", 0) > 0) & (cl.get("nuovo", 0) > 0)]
    print("ore NY con netto positivo in ENTRAMBI i periodi:",
          list(bl.index) if len(bl) else "nessuna")
    dfl.to_parquet(f"{USCITA}/primaria_ore_ny.parquet")

    # ---------------- anno per anno, primaria ----------------
    ann = p.groupby("anno").agg(n=("r_netto", "size"), r_lordo=("r_lordo", "mean"),
                                r_netto=("r_netto", "mean"))
    ann["somma_R"] = p.groupby("anno").r_netto.sum()
    print("\n=== PRIMARIA ANNO PER ANNO (netto) ===")
    print(ann.round(3).T.to_string())
    pos = int((ann.r_netto > 0).sum())
    print(f"anni positivi: {pos}/{len(ann)}")

    # ---------------- mappa per ora (forma primaria N,X) ----------------
    mo = ore[(ore.N == PRIM["n"]) & (ore.X == PRIM["x"])]
    tab = mo.pivot_table(index="ora", columns="periodo",
                         values=["n", "r_lordo", "r_netto"])
    print("\n=== R PER ORA UTC (N=30, X=0,20, S=0,20, RR=1:1,5) ===")
    print(tab.round(3).to_string())

    conc = mo.pivot_table(index="ora", columns="periodo", values="r_netto")
    both = conc[(conc["vecchio"] > 0) & (conc["nuovo"] > 0)]
    print("ore con netto positivo in ENTRAMBI i periodi:",
          list(both.index) if len(both) else "nessuna")

    # ---------------- griglia compatta ----------------
    print("\n=== GRIGLIA: R NETTO per operazione (S=0,20 ATR, RR=1:1,5, ore 0-19) ===")
    gg = grid[(grid.S == 0.20) & (grid.RR == 1.5)]
    print(gg.pivot_table(index="N", columns=["periodo", "X"],
                         values="r_netto").round(3).to_string())
    print("\n=== GRIGLIA: R LORDO per operazione (stessa fetta) ===")
    print(gg.pivot_table(index="N", columns=["periodo", "X"],
                         values="r_lordo").round(3).to_string())
    print("\ncelle con netto positivo su ENTRAMBI i periodi, su tutta la griglia:")
    pv = grid.pivot_table(index=["N", "X", "S", "RR"], columns="periodo",
                          values=["r_netto", "n"])
    ent = pv[(pv[("r_netto", "vecchio")] > 0) & (pv[("r_netto", "nuovo")] > 0)]
    print(ent.round(3).to_string() if len(ent) else "  NESSUNA su 80 combinazioni")
    print(f"\nscritto il dettaglio in {USCITA}/")


if __name__ == "__main__":
    main()
