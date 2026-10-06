#!/usr/bin/env python3
"""Crollo -> conferma -> entrata, SWING v2 (stop S1, S2, S3 senza tetto): SCOPERTA 2009-2017.

Protocollo VINCOLANTE: docs/crollo-conferma-swing-v2-registrazione.md (commit
bf9a30b); tutto il resto come la v1 (docs/crollo-conferma-registrazione.md,
interpretazioni in docs/studies/conferme/scoperta.md). Motore:
trading/framework/crollo_conferma.py (parametro ``stop`` di ``operazioni``).
Rapporto: docs/studies/conferme/swing-v2.md.

Dati (solo scoperta): D:\\ricerca_zero\\scoperta\\XAUUSD_M5|D1.parquet e
data/XAUUSD_M1/XAUUSD_M1_2009..2017.parquet (solo il VWAP, dalla cache della
v1 se coincide). Caricamento, barre H4/D1, VWAP, statistiche e placebo sono
quelli dello script v1 (``crollo_conferma_scoperta``), importati.

Varianti: 2 TF (H4, D1) x 3 k (2, 3, 4) x 7 conferme x 3 stop x 4 obiettivi x
2 lati = 1.008, piu' 144 riferimenti "senza conferma" (stesso stop).
Promozione v2: netto > 0 a x1 e x1,5 (R e $), t >= 3, anni positivi >= 7/9,
positivo (R e $ a x1) sia nel 2009-2012 sia nel 2013-2017, placebo p < 0,01,
R migliore del riferimento a x1 e x1,5, n >= 40; al massimo 5 (per t).

Scrive in D:\\ricerca_conferme\\risultati\\:
    v2_operazioni.parquet       una riga per operazione tenuta
    v2_varianti.parquet         una riga per variante (1.008 + 144 riferimenti)
    v2_verifica_motore.parquet  300 operazioni rifatte con un ciclo barra per barra
    v2_controlli.parquet        troncamento (anche il minimo crescente di S2)
                                e confronto stop "v1" con la v1 pubblicata
Stampa solo aggregati compatti.
"""
from __future__ import annotations

import gc
import os
import sys
import time

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(QUI, ".."))
sys.path.insert(0, QUI)
from framework import crollo_conferma as cc  # noqa: E402
import crollo_conferma_scoperta as sc  # noqa: E402

OUT = sc.OUT
COSTO = sc.COSTO                       # 0,46 $ RT (scoperta 2009-2017)
TFS = ("H4", "D1")
K = (2.0, 3.0, 4.0)
STOPS = ("S1", "S2", "S3")
ORIZ = "swing"
META1 = range(2009, 2013)
META2 = range(2013, 2018)
pd.set_option("display.width", 200)


def righe_operazioni(op, keep, ti, dz, t5, tf, k, conf, stop, ob, vid):
    e, ent, R = op["e"][keep], op["ent"][keep], op["R"][keep]
    x = op["x"][keep, ti]
    px, nt = op["px"][keep, ti], op["notti"][keep, ti]
    usd = cc.esito_usd(dz, ent, px, nt, COSTO)
    usd15 = cc.esito_usd(dz, ent, px, nt, COSTO, 1.5)
    usdf = cc.esito_usd(-dz, ent, op["pxf"][keep, ti], op["nottif"][keep, ti], COSTO)
    sw = (cc.SWAP_LONG if dz == 1 else cc.SWAP_SHORT) * ent / cc.SWAP_RIF * nt
    te = pd.to_datetime(t5[e] * 60, unit="s", utc=True)
    return pd.DataFrame(dict(
        vid=vid, tf=tf, k=k, conferma=conf, stop_modo=stop, obiettivo=ob,
        lato="long" if dz == 1 else "short", e=e, uscita=x, ent=ent, stop=op["stop"][keep],
        obj=op["obj"][keep, ti], R=R, R_atr=R / op["atr"][keep], fr=op["fr"][keep], px=px,
        motivo=op["mot"][keep, ti], notti=nt, usd=usd, usd15=usd15, netR=usd / R,
        netR15=usd15 / R, netRf=usdf / R, lordoR=dz * (px - ent) / R, swapR=sw / R,
        anno=te.year, mese=(te.year - 2009) * 12 + te.month - 1,
        tenuta_h=(t5[x] - t5[e]) / 60.0))


def misure_v2(g: pd.DataFrame, rng) -> dict:
    m = sc.misure(g, rng)
    m1, m2 = g["anno"].isin(META1), g["anno"].isin(META2)
    m.update(R_m1=g.loc[m1, "netR"].sum(), R_m2=g.loc[m2, "netR"].sum(),
             usd_m1=g.loc[m1, "usd"].sum(), usd_m2=g.loc[m2, "usd"].sum(),
             R_atr=g["R_atr"].mean(), quota_fr=g["fr"].mean())
    return m


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    t5, o5, h5, l5, c5, fg, g5, atr_f = sc.carica()
    assert pd.Timestamp(int(t5[-1]) * 60, unit="s") < pd.Timestamp("2018-01-01")
    m5 = (t5, o5, h5, l5, c5)
    vw5 = sc.vwap_m5(t5)
    print(f"M5 {len(t5):,} barre (fino a {pd.Timestamp(int(t5[-1]) * 60, unit='s'):%Y-%m-%d}), "
          f"giornate {len(fg)}")
    pezzi, controlli, n_v1 = [], [], []
    vid = 0
    for tf in TFS:
        B = sc.costruisci_tf(tf, *m5, vw5, fg, g5, atr_f)
        for dz in (1, -1):
            Bx = B if dz == 1 else cc.specchio(B)
            for k in K:
                for conf in list(cc.CONFERME) + ["NESSUNA"]:
                    sg = cc.segnali(Bx, k, conf, ORIZ)
                    # controllo: stop "v1" = conteggi della v1 pubblicata
                    opv = cc.operazioni(sg, B, m5, ORIZ, dz, COSTO, fg, g5, stop="v1")
                    for ti, ob in enumerate(cc.OBIETTIVI):
                        nk = int(cc.una_alla_volta(opv["e"], opv["x"][:, ti]).sum()) if len(opv["e"]) else 0
                        n_v1.append(dict(tf=tf, k=k, conferma=conf, obiettivo=ob,
                                         lato="long" if dz == 1 else "short", n_v1=nk))
                    for stop in STOPS:
                        op = cc.operazioni(sg, B, m5, ORIZ, dz, COSTO, fg, g5, stop=stop)
                        for ti, ob in enumerate(cc.OBIETTIVI):
                            if len(op["e"]):
                                keep = cc.una_alla_volta(op["e"], op["x"][:, ti])
                                pezzi.append(righe_operazioni(op, keep, ti, dz, t5, tf, k, conf, stop, ob,
                                                              vid if conf != "NESSUNA" else -1))
                            if conf != "NESSUNA":
                                vid += 1
                # troncamento (nessun lookahead), compreso il minimo crescente di S2
                if k == 3.0:
                    taglio = len(B.c) * 2 // 3
                    n5 = B.i5[taglio]
                    Bt = sc.costruisci_tf(tf, t5[:n5], o5[:n5], h5[:n5], l5[:n5], c5[:n5],
                                          vw5[:n5], fg, g5[:n5], atr_f)
                    Bt = Bt if dz == 1 else cc.specchio(Bt)
                    for conf in ("C1", "C2", "C5", "NESSUNA"):
                        key = lambda s: (s.inizio, s.conferma, s.L, -1.0 if np.isnan(s.F) else s.F)
                        a = [key(s) for s in cc.segnali(Bx, k, conf, ORIZ) if s.conferma < taglio]
                        b = [key(s) for s in cc.segnali(Bt, k, conf, ORIZ) if s.conferma < taglio]
                        controlli.append(dict(controllo="troncamento", tf=tf, dz=dz, conf=conf,
                                              n=len(a), ok=a == b))
        del B
        gc.collect()
        print(f"  {tf} fatto ({time.time() - t0:.0f}s)")
    assert vid == 1008, vid
    O = pd.concat(pezzi, ignore_index=True)
    del pezzi
    gc.collect()
    O["vid"] = O["vid"].astype(np.int32)
    O.to_parquet(os.path.join(OUT, "v2_operazioni.parquet"))

    # ---- stop "v1" contro la v1 pubblicata (varianti swing)
    N1 = pd.DataFrame(n_v1)
    V1 = pd.read_parquet(os.path.join(OUT, "varianti.parquet"))
    V1 = V1[V1["orizzonte"] == "swing"].set_index(["tf", "k", "conferma", "obiettivo", "lato"])["n"]
    N1["n_pubbl"] = [int(V1.get(tuple(r), 0)) for r in
                     N1[["tf", "k", "conferma", "obiettivo", "lato"]].itertuples(index=False)]
    ok_v1 = bool((N1["n_v1"] == N1["n_pubbl"]).all())
    controlli.append(dict(controllo="stop v1 = v1 pubblicata", n=int(N1["n_v1"].sum()), ok=ok_v1))
    Tc = pd.DataFrame(controlli)
    tr = Tc[Tc["controllo"] == "troncamento"]
    print(f"Troncamento (segnali e minimo crescente prima del taglio identici): "
          f"{int(tr['ok'].sum())}/{len(tr)} casi, {int(tr['n'].sum())} segnali")
    print(f"Stop 'v1' = v1 pubblicata (n per variante swing, 168+48 righe): {ok_v1}")

    # ---- verifica del motore con il ciclo barra per barra
    rng0 = np.random.default_rng(7)
    camp = O.iloc[rng0.choice(len(O), 300, replace=False)]
    diff, dx, vr = 0.0, 0, []
    for r in camp.itertuples():
        dz = 1 if r.lato == "long" else -1
        xx, px, usd = sc.lento(t5, o5, h5, l5, c5, g5, int(r.e), dz, r.stop, r.obj, ORIZ)
        diff, dx = max(diff, abs(usd - r.usd)), max(dx, abs(xx - r.uscita))
        vr.append(dict(e=r.e, stop_modo=r.stop_modo, uscita=r.uscita, uscita_lento=xx, usd=r.usd,
                       usd_lento=usd))
    pd.DataFrame(vr).to_parquet(os.path.join(OUT, "v2_verifica_motore.parquet"))
    controlli.append(dict(controllo="motore = ciclo (300 op.)", n=300, ok=diff < 1e-9 and dx == 0))
    pd.DataFrame(controlli).to_parquet(os.path.join(OUT, "v2_controlli.parquet"))
    print(f"Verifica motore (300 operazioni): differenza netto {diff:.2e} $, uscita {dx} barre")

    # ---- misure per variante
    chiavi = ["tf", "k", "conferma", "stop_modo", "obiettivo", "lato"]
    righe = []
    for i, (key, g) in enumerate(O.groupby(chiavi, sort=False)):
        righe.append(dict(zip(chiavi, key), **misure_v2(g.sort_values("e"), np.random.default_rng(sc.SEED + i))))
    V = pd.DataFrame(righe)
    rk = ["tf", "k", "stop_modo", "obiettivo", "lato"]
    ref = V[V["conferma"] == "NESSUNA"].set_index(rk)
    for c in ("R", "R15", "usd", "vinte", "n"):
        V[f"rif_{c}"] = [ref[c].get(tuple(r), np.nan) for r in V[rk].itertuples(index=False)]
    V["meglio_rif"] = (V["R"] > V["rif_R"]) & (V["R15"] > V["rif_R15"])
    V["netto_pos"] = (V["R"] > 0) & (V["R15"] > 0) & (V["usd"] > 0) & (V["usd15"] > 0)
    V["meta_pos"] = (V["R_m1"] > 0) & (V["R_m2"] > 0) & (V["usd_m1"] > 0) & (V["usd_m2"] > 0)
    V["passa"] = (V["netto_pos"] & (V["t"] >= 3) & (V["anni_pos"] >= 7) & V["meta_pos"] & (V["p"] < 0.01)
                  & V["meglio_rif"] & (V["n"] >= 40) & (V["conferma"] != "NESSUNA"))
    V.to_parquet(os.path.join(OUT, "v2_varianti.parquet"))
    Vc = V[V["conferma"] != "NESSUNA"]

    print(f"\nVarianti con operazioni: {len(Vc)} su 1008 (+ {int((V['conferma'] == 'NESSUNA').sum())} "
          f"riferimenti su 144)")
    print("Operazioni per variante (n): mediana [min-max], quota 50-150, quota >= 40")
    q = Vc.groupby(["tf", "stop_modo"])["n"].agg(
        mediana="median", minimo="min", massimo="max",
        q50_150=lambda s: ((s >= 50) & (s <= 150)).mean(), q40=lambda s: (s >= 40).mean())
    print(q.round(2).to_string())
    print(f"Tutte: mediana {Vc['n'].median():.0f}, 50-150 {((Vc.n >= 50) & (Vc.n <= 150)).mean():.2f}, "
          f">= 40 {(Vc.n >= 40).mean():.2f}; varianti senza operazioni {1008 - len(Vc)}")
    print(f"\nCriteri (su {len(Vc)}): netto>0 x1 e x1,5 {int(Vc.netto_pos.sum())}, t>=3 {int((Vc.t >= 3).sum())}, "
          f"anni>=7 {int((Vc.anni_pos >= 7).sum())}, meta' positive {int(Vc.meta_pos.sum())}, "
          f"p<0,01 {int((Vc.p < 0.01).sum())}, meglio del rif {int(Vc.meglio_rif.sum())}, "
          f"n>=40 {int((Vc.n >= 40).sum())}, TUTTI {int(Vc.passa.sum())}")
    col = ["tf", "k", "conferma", "stop_modo", "obiettivo", "lato", "n", "vinte", "R", "R15", "usd", "t_op",
           "t_mese", "anni_pos", "R_m1", "R_m2", "p", "rif_R"]
    print("\nMigliori 15 per t:")
    print(Vc.sort_values("t", ascending=False).head(15)[col].round(3).to_string(index=False))

    def gruppo(D, by):
        return D.groupby(by).agg(var=("n", "size"), n=("n", "mean"), vinte=("vinte", "mean"),
                                 vinte_rif=("rif_vinte", "mean"), R=("R", "mean"), R_rif=("rif_R", "mean"),
                                 usd=("usd", "mean"), usd_rif=("rif_usd", "mean"),
                                 meglio=("meglio_rif", "mean"), t_max=("t", "max"))
    print("\nConferma contro senza conferma, per stop e TF:")
    print(gruppo(Vc, ["stop_modo", "tf"]).round(3).to_string())
    print("\nPer conferma e stop:")
    print(gruppo(Vc, ["conferma", "stop_modo"]).round(3).to_string())
    print("\nRiferimenti senza conferma per stop e TF:")
    Vr = V[V["conferma"] == "NESSUNA"]
    print(Vr.groupby(["stop_modo", "tf"]).agg(var=("n", "size"), n=("n", "mean"), vinte=("vinte", "mean"),
                                              R=("R", "mean"), usd=("usd", "mean"),
                                              t_max=("t", "max")).round(3).to_string())
    tutte = O.assign(conf=np.where(O["conferma"] == "NESSUNA", "senza", "con")).groupby(
        ["stop_modo", "conf"]).agg(op=("netR", "size"), vinte=("netR", lambda s: (s > 0).mean()),
                                   R=("netR", "mean"), lordoR=("lordoR", "mean"), usd=("usd", "mean"),
                                   R_atr=("R_atr", "mean"), fr=("fr", "mean"))
    print("\nTutte le operazioni insieme:")
    print(tutte.round(3).to_string())
    C = Vc[Vc["passa"]].sort_values("t", ascending=False).head(5)
    print(f"\nCandidati: {len(C)}")
    if len(C):
        print(C[col].round(3).to_string(index=False))
    print(f"\nTempo {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
