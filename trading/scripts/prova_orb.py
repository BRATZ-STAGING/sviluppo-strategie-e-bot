"""Opening Range Breakout (ORB) su XAUUSD, 2009-2026.

IPOTESI PRE-REGISTRATA (scritta PRIMA di guardare qualunque numero)
------------------------------------------------------------------
Si definisce il range dei primi N minuti di una sessione (N = 15, 30, 60).
Sessioni: apertura di Londra (07:00 UTC), apertura di New York (13:00 UTC),
mezzanotte UTC come riferimento; piu' due varianti a ORA LOCALE (Londra
08:00 Europe/London, New York 09:30 America/New_York) perche' la mappa
"orologio" ha misurato che l'orologio del mercato e' locale, non UTC.

Regola ROTTURA: alla PRIMA candela M1 che CHIUDE sopra il massimo del range
si compra, sotto il minimo si vende; ingresso all'apertura della candela
successiva; una sola operazione per sessione; chiusura forzata a fine
giornata (ultima candela prima delle 21:00 UTC).
Regola DISSOLVENZA: stessa identica innesco, direzione opposta, stessa
distanza di rischio (specchio esatto), per misurare se e' il verso a essere
sbagliato.

Stop: (a) lato opposto del range, (b) 0,15 ATR, (c) 0,30 ATR.
Obiettivi: 1:1, 1:1,5, 1:2, 1:3 (l'utente vuole 1:1,5-1:2).
Costo: 0,30 $ andata e ritorno, cioe' 0,30/distanza_stop in R.
Lo stop vince i pareggi dentro lo stesso minuto.

CELLA PRIMARIA pre-registrata (il verdetto si legge qui, non sulla cella
migliore della griglia): New York 13:00 UTC, N=30, stop sul lato opposto del
range, obiettivo 1:2, ROTTURA.

Cosa mi aspetto, scritto prima: la RESPINGO. La ricognizione ha gia'
misurato che (i) la rottura del range d'apertura con stop sul bordo opposto
e' indistinguibile da un cammino casuale e non batte una banda spostata a
caso, (ii) nessuna ora e' direzionale (rapporto di varianza <= 1 quasi
ovunque), (iii) dopo un impulso il prezzo contrasta invece di continuare.
Mi aspetto quindi R netto per operazione fra -0,10 e +0,02 sulla rottura,
non concorde fra i due periodi, e una dissolvenza speculare (lordo
leggermente positivo ma sotto il costo dello spread). Se la rottura risulta
nettamente positiva su ENTRAMBI i periodi devo sospettare un errore di
causalita' prima di crederci.

Uscita: dettaglio grezzo in /workspace/dati_grezzi/orb/, in chat solo
aggregati.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/workspace/sviluppo-strategie-e-bot/trading")
from framework.data import load_m1                      # noqa: E402
from framework.volatility import daily_atr              # noqa: E402

DATI = "/workspace/sviluppo-strategie-e-bot/data/XAUUSD_M1"
FUORI = "/workspace/dati_grezzi/orb"
SPREAD = 0.30              # $ andata e ritorno
ORA_STOP_INGRESSI = 20     # UTC: dopo non si apre piu'
ORA_CHIUSURA = 21          # UTC: si chiude prima del rollover
RR = [1.0, 1.5, 2.0, 3.0]
STOP_TIPI = ["range", "atr15", "atr30"]
ENNE = [15, 30, 60]

# sessioni: (nome, tipo, ora, minuto) - tipo "utc" oppure nome di fuso
SESSIONI = [
    ("LON07utc", "UTC", 7, 0),
    ("NY13utc", "UTC", 13, 0),
    ("MID00utc", "UTC", 0, 0),
    ("LON08loc", "Europe/London", 8, 0),
    ("NY0930loc", "America/New_York", 9, 30),
]


def aperture_sessione(giorni: pd.DatetimeIndex, tz: str, ora: int, minuto: int):
    """Istante UTC di apertura della sessione per ciascuna giornata."""
    naive = pd.DatetimeIndex(giorni.tz_localize(None)) + pd.Timedelta(
        hours=ora, minutes=minuto)
    if tz == "UTC":
        return naive.tz_localize("UTC")
    return naive.tz_localize(tz, nonexistent="shift_forward",
                             ambiguous=True).tz_convert("UTC")


def trova_operazioni(ts, op, hi, lo, cl, aperture, giorni, atr_gg, n_min,
                     scarto=None):
    """Innesco e percorso di ogni operazione (causale).

    ``scarto`` (in larghezze di range) sposta la banda: e' il PLACEBO.
    Ritorna un dizionario di array, uno per operazione.
    """
    out = {k: [] for k in ("giorno", "verso", "i_ing", "i_fine", "prezzo",
                           "d_range", "atr", "larg")}
    t_fine = pd.DatetimeIndex(giorni.tz_localize(None)) + pd.Timedelta(
        hours=ORA_CHIUSURA)
    t_fine = t_fine.tz_localize("UTC").values.astype("datetime64[ns]")
    t_ultimo_ing = pd.DatetimeIndex(giorni.tz_localize(None)) + pd.Timedelta(
        hours=ORA_STOP_INGRESSI)
    t_ultimo_ing = t_ultimo_ing.tz_localize("UTC").values.astype(
        "datetime64[ns]")
    ap = aperture.values.astype("datetime64[ns]")
    fine_range = (aperture + pd.Timedelta(minutes=n_min)).values.astype(
        "datetime64[ns]")
    i0 = np.searchsorted(ts, ap, side="left")
    i1 = np.searchsorted(ts, fine_range, side="left")
    i2 = np.searchsorted(ts, t_ultimo_ing, side="left")
    i3 = np.searchsorted(ts, t_fine, side="left") - 1
    min_barre = max(5, n_min // 2)
    for g in range(len(giorni)):
        a, b, c_, d = i0[g], i1[g], i2[g], i3[g]
        if b - a < min_barre or c_ <= b or d <= b:
            continue
        # la finestra del range deve stare davvero nella sessione richiesta
        if ts[a] < ap[g] or ts[b - 1] >= fine_range[g]:
            continue
        atr = atr_gg[g]
        if not np.isfinite(atr) or atr <= 0:
            continue
        alto = hi[a:b].max()
        basso = lo[a:b].min()
        larg = alto - basso
        if larg <= 0:
            continue
        if scarto is not None:
            alto += scarto[g] * larg
            basso += scarto[g] * larg
        fine_scan = min(c_, d)
        seg = cl[b:fine_scan]
        if seg.size == 0:
            continue
        su = seg > alto
        giu = seg < basso
        k_su = int(su.argmax()) if su.any() else 10 ** 9
        k_giu = int(giu.argmax()) if giu.any() else 10 ** 9
        if k_su == k_giu == 10 ** 9:
            continue
        if k_su <= k_giu:
            verso, k = 1, k_su
        else:
            verso, k = -1, k_giu
        i_seg = b + k                    # candela che CHIUDE oltre il bordo
        i_ing = i_seg + 1                # ingresso all'apertura della successiva
        if i_ing > d:
            continue
        prezzo = op[i_ing]
        d_range = (prezzo - basso) if verso == 1 else (alto - prezzo)
        out["giorno"].append(giorni[g])
        out["verso"].append(verso)
        out["i_ing"].append(i_ing)
        out["i_fine"].append(d)
        out["prezzo"].append(prezzo)
        out["d_range"].append(d_range)
        out["atr"].append(atr)
        out["larg"].append(larg)
    return {k: np.asarray(v) for k, v in out.items()}


def esiti(ops, hi, lo, cl):
    """Per ogni operazione e ogni (stop, obiettivo, modo) calcola l'esito.

    Usa i massimi/minimi cumulati del percorso: il primo tocco di una
    barriera si trova con una ricerca binaria, senza guardare oltre.
    """
    n = len(ops["prezzo"])
    righe = []
    for j in range(n):
        a, b = ops["i_ing"][j], ops["i_fine"][j]
        cmax = np.maximum.accumulate(hi[a:b + 1])
        cmin = np.minimum.accumulate(lo[a:b + 1])
        ncmin = -cmin
        chiusura = cl[b]
        prezzo = ops["prezzo"][j]
        for modo, sgn in (("rottura", 1), ("dissolvenza", -1)):
            verso = ops["verso"][j] * sgn
            for stipo in STOP_TIPI:
                if stipo == "range":
                    rischio = ops["d_range"][j]
                elif stipo == "atr15":
                    rischio = 0.15 * ops["atr"][j]
                else:
                    rischio = 0.30 * ops["atr"][j]
                if rischio <= 0:
                    continue
                costo = SPREAD / rischio
                for rr in RR:
                    if verso == 1:
                        liv_ob, liv_st = prezzo + rr * rischio, prezzo - rischio
                        t_ob = np.searchsorted(cmax, liv_ob, side="left")
                        t_st = np.searchsorted(ncmin, -liv_st, side="left")
                    else:
                        liv_ob, liv_st = prezzo - rr * rischio, prezzo + rischio
                        t_ob = np.searchsorted(ncmin, -liv_ob, side="left")
                        t_st = np.searchsorted(cmax, liv_st, side="left")
                    m = cmax.size
                    t_ob = t_ob if t_ob < m else 10 ** 9
                    t_st = t_st if t_st < m else 10 ** 9
                    if t_st <= t_ob and t_st < 10 ** 9:     # lo stop vince i pari
                        esito, r = "stop", -1.0
                    elif t_ob < 10 ** 9:
                        esito, r = "obiettivo", rr
                    else:
                        esito = "scadenza"
                        r = verso * (chiusura - prezzo) / rischio
                    righe.append((j, modo, stipo, rr, esito, r - costo, costo,
                                  rischio))
    d = pd.DataFrame(righe, columns=["j", "modo", "stop", "rr", "esito",
                                     "r_netto", "costo", "rischio"])
    d["giorno"] = ops["giorno"][d.j.values]
    d["anno"] = pd.DatetimeIndex(d.giorno).year
    d["periodo"] = np.where(d.anno <= 2019, "2009-2019", "2020-2026")
    return d


def main():
    os.makedirs(FUORI, exist_ok=True)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 400)
    m1 = load_m1(DATI)
    ts = m1.index.values.astype("datetime64[ns]")
    op = m1.open.to_numpy(float)
    hi = m1.high.to_numpy(float)
    lo = m1.low.to_numpy(float)
    cl = m1.close.to_numpy(float)
    atr = daily_atr(m1, 14)
    giorni = pd.DatetimeIndex(sorted(set(m1.index.normalize())))
    idx_atr = atr.index if atr.index.tz is not None else giorni.tz_localize(None)
    atr_gg = atr.reindex(giorni if idx_atr.tz is not None
                         else giorni.tz_localize(None)).to_numpy(float)

    rng = np.random.default_rng(20260804)
    # placebo: banda della stessa larghezza spostata di 0,25-1,2 larghezze
    scarto = rng.uniform(0.25, 1.2, len(giorni)) * rng.choice(
        [-1.0, 1.0], len(giorni))

    tutto = []
    for nome, tz, ora, minu in SESSIONI:
        ap = aperture_sessione(giorni, tz, ora, minu)
        for n_min in ENNE:
            for etichetta, sc in (("vero", None), ("placebo", scarto)):
                ops = trova_operazioni(ts, op, hi, lo, cl, ap, giorni,
                                       atr_gg, n_min, sc)
                if len(ops["prezzo"]) == 0:
                    continue
                d = esiti(ops, hi, lo, cl)
                d["sessione"] = nome
                d["N"] = n_min
                d["banda"] = etichetta
                tutto.append(d)
    res = pd.concat(tutto, ignore_index=True)
    res.drop(columns=["j"]).to_parquet(f"{FUORI}/orb_esiti.parquet")

    vero = res[res.banda == "vero"]
    print(f"\noperazioni totali (banda vera, per configurazione di sessione/N): "
          f"{len(vero[(vero.modo=='rottura')&(vero.stop=='range')&(vero.rr==2.0)])}")

    def tab(stop_tipo, modo):
        s = vero[(vero.stop == stop_tipo) & (vero.modo == modo) &
                 (vero.rr.isin([1.5, 2.0]))]
        p = s.pivot_table(index=["sessione", "N"], columns=["periodo", "rr"],
                          values="r_netto", aggfunc="mean")
        p.columns = [f"{a[:4]}_{b}" for a, b in p.columns]
        n = s[s.rr == 2.0].pivot_table(index=["sessione", "N"],
                                       columns="periodo", values="r_netto",
                                       aggfunc="size")
        n.columns = [f"n_{c[:4]}" for c in n.columns]
        return p.join(n).round(3)

    for stop_tipo in STOP_TIPI:
        for modo in ("rottura", "dissolvenza"):
            print(f"\n=== {modo.upper()} - stop {stop_tipo} - R netto/op ===")
            print(tab(stop_tipo, modo))

    # quante celle sono positive su ENTRAMBI i periodi?
    agg = vero.groupby(["sessione", "N", "modo", "stop", "rr", "periodo"]
                       ).r_netto.mean().unstack("periodo")
    both = (agg > 0).all(axis=1)
    print(f"\ncelle con R netto > 0 in ENTRAMBI i periodi: "
          f"{int(both.sum())} su {len(agg)}")
    print("le migliori per somma dei due periodi:")
    agg["somma"] = agg.sum(axis=1)
    print(agg.sort_values("somma", ascending=False).head(8).round(3))

    # cella primaria pre-registrata
    prim = vero[(vero.sessione == "NY13utc") & (vero.N == 30) &
                (vero.stop == "range") & (vero.rr == 2.0) &
                (vero.modo == "rottura")]
    print("\n=== CELLA PRIMARIA: NY 13:00 UTC, N=30, stop range, 1:2, rottura ===")
    print(prim.groupby("periodo").agg(
        n=("r_netto", "size"), r_op=("r_netto", "mean"),
        costo=("costo", "mean"), rischio=("rischio", "mean")).round(3))
    print("scomposizione degli esiti (%):")
    print((prim.groupby(["periodo", "esito"]).size().unstack(fill_value=0)
           .pipe(lambda x: 100 * x.div(x.sum(axis=1), axis=0))).round(1))
    ann = prim.groupby("anno").r_netto.agg(["size", "mean"]).round(3)
    print(f"anni con R netto/op positivo: {int((ann['mean']>0).sum())} su {len(ann)}")

    # controllo di assurdita': obiettivo lontano vs stop vicino
    print("\n=== CONTROLLO DI ASSURDITA' (rottura, stop range) ===")
    ctrl = vero[(vero.modo == "rottura") & (vero.stop == "range")]
    q = (ctrl.groupby(["periodo", "rr"]).esito
         .value_counts(normalize=True).unstack(fill_value=0) * 100).round(1)
    print(q)
    print("atteso: la quota obiettivo scende al crescere di rr e resta sotto "
          "la quota stop per rr>1")

    # placebo
    print("\n=== PLACEBO (banda spostata a caso) vs banda vera, rr 1:2 ===")
    pl = res[(res.rr == 2.0) & (res.stop.isin(["range", "atr15"]))]
    pv = pl.pivot_table(index=["modo", "stop", "periodo"], columns="banda",
                        values="r_netto", aggfunc="mean").round(3)
    pn = pl.pivot_table(index=["modo", "stop", "periodo"], columns="banda",
                        values="r_netto", aggfunc="size")
    print(pv.join(pn.add_prefix("n_")))

    # dettaglio per anno della cella primaria e della migliore
    ann.to_parquet(f"{FUORI}/orb_primaria_per_anno.parquet")
    print("\nper anno (cella primaria):")
    print(ann.T)


if __name__ == "__main__":
    main()
