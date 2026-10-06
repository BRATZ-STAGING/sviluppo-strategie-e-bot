#!/usr/bin/env python3
"""Oro con i costi veri FP Markets Raw: F3, F4 e crollo -> conferma intraday.

Registrazione VINCOLANTE: docs/costi-fp-raw-oro-registrazione.md (commit
4e59d3f). Rapporto: docs/studies/oro-fp/f3f4c.md.

Rifa' SOLO per XAUUSD, con griglie, regole, placebo e semi IDENTICI agli
originali, importando le loro funzioni (gli script originali non si toccano):
  f3      trading/scripts/zero_f3_range.py          (432 varianti oro)
  f4      trading/scripts/zero_f4_volatilita.py     (104 varianti oro)
  crollo  trading/scripts/crollo_conferma_scoperta.py, parte intraday M15/H1
          (336 varianti + 48 riferimenti "senza conferma")
Cambia solo il costo round trip dell'oro:
  vecchio  F3/F4 0,40 $; crollo 0,46 $ (x1,5 = 0,69 $)  -> deve riprodurre
           i numeri dei rapporti originali
  c020     0,20 $ (base)
  c030     0,30 $ (prova di resistenza; per il crollo e' il suo "x1,5")
Il filtro "rischio < 2 x costo" usa il costo base dello scenario (0,40/0,46
per il vecchio, 0,20 per entrambi i nuovi: stesse operazioni a 0,20 e 0,30,
come il crollo originale che filtrava col costo x1).

Dati: solo D:\\ricerca_zero\\scoperta\\XAUUSD_*.parquet e
data/XAUUSD_M1/XAUUSD_M1_2009..2017.parquet (tramite la cache VWAP del crollo,
costruita da quegli anni). Dettaglio in D:\\ricerca_oro_fp\\risultati\\.

Uso: python oro_fp_f3f4c.py f3|f4|crollo|sintesi   (una parte alla volta: poca RAM)
"""
from __future__ import annotations

import gc
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))
sys.path.insert(0, str(QUI.parent))
import zero_f3_range as zf3  # noqa: E402
import zero_f4_volatilita as zf4  # noqa: E402
import crollo_conferma_scoperta as ccs  # noqa: E402
from framework import crollo_conferma as cc  # noqa: E402

OUT = Path(r"D:\ricerca_oro_fp\risultati")
SIM = "XAUUSD"
# (scenario, costo del filtro di rischio minimo, costo applicato)
SCEN = [("vecchio", 0.40, 0.40), ("c020", 0.20, 0.20), ("c030", 0.20, 0.30)]
H4_VID = "c|XAUUSD/22-22|CMP|S2|X1"   # H4: esclusa dalla promozione (esito gia' noto)
MAX_CAND = 3
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)


# ====================================================================== F3
def _valuta_f3(sim, arr, sig, ses_date, regime, costo, tag, stops, uscite, righe, dett):
    """Come zero_f3_range.valuta, ma per i tre scenari di costo (stessa
    simulazione, stesso placebo con seed fisso per variante)."""
    t, o, h, l, c = arr
    for sn, fs in stops.items():
        for un, fu in uscite.items():
            if len(sig) == 0:
                for scen, _, cst in SCEN:
                    for rg in ("tutti", "piccolo", "grande"):
                        righe.append(dict(variante="|".join(tag + [sn, un, rg]), scenario=scen, parte=tag[0],
                                          simbolo=sim, **zf3.statistiche(np.zeros(0), np.zeros(0), np.zeros(0),
                                                                         np.zeros(0), cst)))
                continue
            e, z, d, q = sig.e.values, sig.z.values, sig.d.values, sig.q.values
            reg = regime[q]
            anni = ses_date[q].year.values
            R = fs(sig)
            T = fu(sig, R)
            cache = {}
            for scen, filt, cst in SCEN:
                if filt not in cache:
                    okr = np.isfinite(R) & (R >= zf3.MIN_R_COSTI * filt)
                    ee, zz, dd, RR, TT = e[okr], z[okr], d[okr], R[okr], T[okr]
                    g1 = zf3.simula(o, h, l, c, ee, zz, dd, RR, TT)
                    g2 = zf3.simula(o, h, l, c, ee, zz, -dd, RR, TT)
                    cache[filt] = (okr, g1, g2, RR, dd)
                    dett.append(pd.DataFrame({"variante": "|".join(tag + [sn, un]), "filtro_costo": filt,
                                              "data": ses_date[q[okr]], "dir": dd.astype(np.int8),
                                              "rischio": RR, "lordo_usd": g1, "lordo_usd_opposto": g2,
                                              "regime": reg[okr]}))
                okr, g1, g2, RR, dd = cache[filt]
                net, alt, netp = (g1 - cst) / RR, (g2 - cst) / RR, g1 - cst
                rr, yy = reg[okr], anni[okr]
                for rg in ("tutti", "piccolo", "grande"):
                    m = np.ones(len(net), bool) if rg == "tutti" else (rr == rg)
                    righe.append(dict(variante="|".join(tag + [sn, un, rg]), scenario=scen, parte=tag[0],
                                      simbolo=sim, **zf3.statistiche(net[m], alt[m], yy[m], netp[m], cst),
                                      lordo_usd=g1[m].mean() if m.any() else np.nan,
                                      lordo_R=(g1[m] / RR[m]).mean() if m.any() else np.nan,
                                      rischio_med=np.median(RR[m]) if m.any() else np.nan))


def parte_f3():
    zf3.RISULTATI = OUT                 # il dettaglio non sovrascrive quello originale
    zf3.valuta = _valuta_f3
    righe = []
    fuso = zf3.studia(SIM, righe)       # scrive OUT/f3_dettaglio_XAUUSD.parquet
    os.replace(OUT / f"f3_dettaglio_{SIM}.parquet", OUT / "f3_operazioni.parquet")
    r = pd.DataFrame(righe)
    r["anni_frac"] = r.anni_pos / r.anni.where(r.anni > 0)
    r["passa_orig"] = ((r.netto_R > 0) & (r.t >= 3) & (r.anni_frac >= 0.75) & (r.p_placebo < 0.01) & (r.n >= 100))
    r.to_parquet(OUT / "f3_varianti.parquet", index=False)
    # riproduzione
    o = pd.read_parquet(r"D:\ricerca_zero\risultati\f3_varianti.parquet")
    o = o[o.simbolo == SIM].set_index("variante")
    v = r[r.scenario == "vecchio"].set_index("variante").loc[o.index]
    print(f"F3 fuso {fuso}; varianti oro {len(v)} (originale {len(o)})")
    for c_ in ("n", "netto_R", "t", "anni_pos", "anni", "p_placebo"):
        dd = (v[c_].astype(float) - o[c_].astype(float)).abs().max()
        print(f"  riproduzione {c_:10s} scarto max {dd:.2e}")


# ====================================================================== F4
def parte_f4():
    d = zf4.carica(SIM)
    zf4.O, zf4.H, zf4.L, zf4.C = (d[c].values.astype(np.float64) for c in ("open", "high", "low", "close"))
    zf4.TS = d.index
    g = zf4.tabella_giorni(d, "22-22", SIM)
    mg = f"{SIM}/22-22"
    fA, reg = zf4.filtri(g)
    ev0 = zf4.eventi_rottura(g, 0.0)
    ev0["anno"] = g.anno.values[ev0.k.values + 1]
    ev0["data"] = g.data.values[ev0.k.values + 1]
    rngs = {s: np.random.default_rng(zf4.SEED) for s, _, _ in SCEN}   # stessa sequenza dell'originale
    varianti, operazioni = [], []

    def riga(vid, parte, filtro, stop, usc, tr, scen, cst):
        st = zf4.statistiche(tr, cst, rngs[scen])
        varianti.append({"vid": vid, "scenario": scen, "parte": parte, "filtro": filtro, "stop": stop,
                         "uscita": usc, **st, "lordo_usd": tr.lordo.mean() if len(tr) else np.nan})
        operazioni.append(tr.assign(vid=vid, scenario=scen))

    for stop in zf4.STOP_A:
        for xn, (ng, tgt) in zf4.USCITE_A.items():
            evs = {s: zf4.esiti(zf4.prepara_rottura(g, ev0, stop, ng, f), c_, tgt) for s, f, c_ in SCEN}
            for fn, fm in fA.items():
                for s, _, c_ in SCEN:
                    ev = evs[s]
                    riga(f"a|{mg}|{fn}|{stop}|{xn}", "a", fn, stop, xn,
                         zf4.non_sovrapposte(ev[fm[ev.k.values]]), s, c_)
            if xn in ("X1", "X3"):
                for rn, rm in reg.items():
                    for s, _, c_ in SCEN:
                        ev = evs[s]
                        riga(f"c|{mg}|{rn}|{stop}|{xn}", "c", rn, stop, xn,
                             zf4.non_sovrapposte(ev[rm[ev.k.values]]), s, c_)
    for en_, (kind, kk) in zf4.ESTREMI.items():
        if kind == "rng":
            m = (g.rng > kk * g.atr_pre).values
            sg = np.sign(g.C - g.O).values
        else:
            ret = (g.C - g.C.shift(1)).values
            m = np.abs(ret) > kk * g.atr_pre.values
            sg = np.sign(ret)
        ks = np.flatnonzero(m & (sg != 0))
        ks = ks[(ks >= 20) & (ks < len(g) - 1)]
        for sm in zf4.STOP_B:
            for ng in zf4.USCITE_B:
                kk2 = ks + ng
                ok = kk2 < len(g)
                evb = pd.DataFrame({"k": ks[ok], "i0": g.st.values[ks[ok] + 1], "iend": g.en.values[kk2[ok]],
                                    "dir": sg[ks[ok]].astype(int), "R": sm * g.atr_pre.values[ks[ok]]})
                evb["anno"] = g.anno.values[evb.k.values + 1]
                evb["data"] = g.data.values[evb.k.values + 1]
                for s, f, c_ in SCEN:
                    evs_ = evb[evb.R >= zf4.MIN_R_COSTI * f]
                    for dn, ds in (("CONT", 1), ("REV", -1)):
                        e2 = zf4.non_sovrapposte(zf4.esiti(evs_.assign(dir=evs_.dir * ds), c_, None))
                        riga(f"b|{SIM}/22-22|{en_}|{dn}|{sm}ATR|X{ng}", "b", f"{en_}-{dn}", f"{sm}ATR",
                             f"X{ng}", e2, s, c_)
    V = pd.DataFrame(varianti)
    V["passa_orig"] = ((V.netR > 0) & (V.t >= 3) & (V.frac_anni >= 0.75) & (V.p < 0.01) & (V.n >= 100))
    V.to_parquet(OUT / "f4_varianti.parquet")
    OP = pd.concat(operazioni, ignore_index=True)
    OP[["vid", "scenario", "k", "data", "anno", "i0", "iend", "jexit", "dir", "entrata", "R", "lordo", "netR",
        "netR_opp"]].to_parquet(OUT / "f4_operazioni.parquet")
    o = pd.read_parquet(r"D:\ricerca_zero\risultati\f4_varianti.parquet")
    o = o[o.mercato == SIM].set_index("vid")
    v = V[V.scenario == "vecchio"].set_index("vid").loc[o.index]
    print(f"F4 varianti oro {len(v)} (originale {len(o)})")
    for c_ in ("n", "netR", "t", "anni_pos", "anni", "p", "lordoR"):
        dd = (v[c_].astype(float) - o[c_].astype(float)).abs().max()
        print(f"  riproduzione {c_:10s} scarto max {dd:.2e}")


# ================================================================ crollo
def parte_crollo():
    t0 = time.time()
    t5, o5, h5, l5, c5, fg, g5, atr_f = ccs.carica()
    m5 = (t5, o5, h5, l5, c5)
    vw5 = ccs.vwap_m5(t5)   # cache costruita dalle M1 2009-2017
    corse = {"vecchio": ccs.COSTO, "nuovo": 0.20}
    assert abs(ccs.COSTO - 0.46) < 1e-12
    pezzi = {r: [] for r in corse}
    for tf in ccs.TFS["intraday"]:
        B = ccs.costruisci_tf(tf, *m5, vw5, fg, g5, atr_f)
        print(f"{tf}: {len(B.c):,} barre, scarto dai Parquet {ccs.controlla_parquet(tf, B):.1e}")
        for dz in (1, -1):
            Bx = B if dz == 1 else cc.specchio(B)
            for k in ccs.K["intraday"]:
                for conf in list(cc.CONFERME) + ["NESSUNA"]:
                    sg = cc.segnali(Bx, k, conf, "intraday")
                    for corsa, COSTO in corse.items():
                        op = cc.operazioni(sg, B, m5, "intraday", dz, COSTO, fg, g5)
                        if len(op["e"]) == 0:
                            continue
                        e, ent, R = op["e"], op["ent"], op["R"]
                        for ti, ob in enumerate(cc.OBIETTIVI):
                            x = op["x"][:, ti]
                            keep = cc.una_alla_volta(e, x)
                            px, nt = op["px"][keep, ti], op["notti"][keep, ti]
                            ee, en, RR = e[keep], ent[keep], R[keep]
                            usd = cc.esito_usd(dz, en, px, nt, COSTO)
                            usd15 = cc.esito_usd(dz, en, px, nt, COSTO, 1.5)
                            usdf = cc.esito_usd(-dz, en, op["pxf"][keep, ti], op["nottif"][keep, ti], COSTO)
                            sw = (cc.SWAP_LONG if dz == 1 else cc.SWAP_SHORT) * en / cc.SWAP_RIF * nt
                            te = pd.to_datetime(t5[ee] * 60, unit="s", utc=True)
                            pezzi[corsa].append(pd.DataFrame(dict(
                                orizzonte="intraday", tf=tf, k=k, conferma=conf, obiettivo=ob,
                                lato="long" if dz == 1 else "short", e=ee, uscita=x[keep], ent=en,
                                stop=op["stop"][keep], obj=op["obj"][keep, ti], R=RR, px=px,
                                motivo=op["mot"][keep, ti], notti=nt, usd=usd, usd15=usd15,
                                netR=usd / RR, netR15=usd15 / RR, netRf=usdf / RR,
                                lordoR=dz * (px - en) / RR, lordo_usd=dz * (px - en), swapR=sw / RR,
                                anno=te.year, mese=(te.year - 2009) * 12 + te.month - 1,
                                tenuta_h=(t5[x[keep]] - t5[ee]) / 60.0)))
        del B
        gc.collect()
        print(f"  {tf} fatto ({time.time() - t0:.0f}s)")
    chiavi = ["orizzonte", "tf", "k", "conferma", "obiettivo", "lato"]
    tutte = []
    for corsa in corse:
        O = pd.concat(pezzi[corsa], ignore_index=True)
        pezzi[corsa] = None
        O.to_parquet(OUT / f"crollo_operazioni_{corsa}.parquet")
        righe = []
        for i, (key, g) in enumerate(O.groupby(chiavi, sort=False)):
            rng = np.random.default_rng(ccs.SEED + i)     # stesso seme dell'originale (intraday per primo)
            gs = g.sort_values("e")
            righe.append(dict(zip(chiavi, key), **ccs.misure(gs, rng), lordo_usd=gs["lordo_usd"].mean(),
                              R_med_usd=gs["R"].median()))
        V = pd.DataFrame(righe)
        ref = V[V["conferma"] == "NESSUNA"].set_index(["orizzonte", "tf", "k", "obiettivo", "lato"])
        for c_ in ("R", "R15", "usd", "vinte"):
            V[f"rif_{c_}"] = [ref[c_].get((a, b, k, d, e), np.nan) for a, b, k, d, e in
                              zip(V["orizzonte"], V["tf"], V["k"], V["obiettivo"], V["lato"])]
        V["meglio_rif"] = (V["R"] > V["rif_R"]) & (V["R15"] > V["rif_R15"])
        V["passa"] = ((V["R"] > 0) & (V["R15"] > 0) & (V["usd"] > 0) & (V["usd15"] > 0) & (V["t"] >= 3)
                      & (V["anni_pos"] >= 7) & (V["p"] < 0.01) & V["meglio_rif"] & (V["conferma"] != "NESSUNA"))
        V["corsa"] = corsa
        V["costo"] = corse[corsa]
        tutte.append(V)
        del O
        gc.collect()
    V = pd.concat(tutte, ignore_index=True)
    V.to_parquet(OUT / "crollo_varianti.parquet")
    o = pd.read_parquet(r"D:\ricerca_conferme\risultati\varianti.parquet")
    o = o[o.orizzonte == "intraday"].set_index(chiavi)
    v = V[V.corsa == "vecchio"].set_index(chiavi).loc[o.index]
    print(f"Crollo intraday varianti {len(v)} (originale {len(o)})")
    for c_ in ("n", "R", "R15", "usd", "t", "anni_pos", "p", "rif_R"):
        dd = (v[c_].astype(float) - o[c_].astype(float)).abs().max()
        print(f"  riproduzione {c_:8s} scarto max {dd:.2e}")
    print(f"Tempo {time.time() - t0:.0f}s")


# =============================================================== sintesi
def _tabella(df, cols, n=10):
    return df[cols].head(n).round(3).to_string(index=False)


def sintesi():
    out = []
    # ------------------------------------------------ F3
    r = pd.read_parquet(OUT / "f3_varianti.parquet")
    w = r.pivot_table(index="variante", columns="scenario",
                      values=["netto_R", "t", "anni_frac", "anni_pos", "anni", "p_placebo", "n", "lordo_usd",
                              "lordo_R", "x_costo", "rischio_med"], aggfunc="first")
    w.columns = [f"{a}_{b}" for a, b in w.columns]
    w = w.reset_index()
    w["promossa"] = ((w.netto_R_c020 > 0) & (w.netto_R_c030 > 0) & (w.t_c020 >= 3) & (w.anni_frac_c020 >= 0.75)
                     & (w.p_placebo_c020 < 0.01) & (w.n_c020 >= 100))
    w.to_parquet(OUT / "f3_sintesi.parquet")
    out.append(("F3", w, "variante", "netto_R", "p_placebo", "anni_frac", "n"))
    # ------------------------------------------------ F4
    V = pd.read_parquet(OUT / "f4_varianti.parquet")
    w = V.pivot_table(index="vid", columns="scenario",
                      values=["netR", "t", "frac_anni", "anni_pos", "anni", "p", "n", "lordo_usd", "lordoR",
                              "R_med"], aggfunc="first")
    w.columns = [f"{a}_{b}" for a, b in w.columns]
    w = w.reset_index()
    w["promossa"] = ((w.netR_c020 > 0) & (w.netR_c030 > 0) & (w.t_c020 >= 3) & (w.frac_anni_c020 >= 0.75)
                     & (w.p_c020 < 0.01) & (w.n_c020 >= 100) & (w.vid != H4_VID))
    w.to_parquet(OUT / "f4_sintesi.parquet")
    out.append(("F4", w, "vid", "netR", "p", "frac_anni", "n"))
    for nome, w, idc, net, p, fa, n in out:
        print(f"\n===== {nome}: {len(w)} varianti")
        for s in ("vecchio", "c020", "c030"):
            print(f"  netto>0 {s}: {int((w[f'{net}_{s}'] > 0).sum())}   t>=3: {int((w[f't_{s}'] >= 3).sum())}"
                  f"   p<0,01: {int((w[f'{p}_{s}'] < 0.01).sum())}   anni>=75%: {int((w[f'{fa}_{s}'] >= 0.75).sum())}")
        print(f"  netto>0 a 0,20 E 0,30: {int(((w[f'{net}_c020'] > 0) & (w[f'{net}_c030'] > 0)).sum())};"
              f" promosse: {int(w.promossa.sum())}")
        cols = [idc, f"{n}_c020", f"lordo_usd_c020", f"{net}_vecchio", f"{net}_c020", f"{net}_c030",
                "t_vecchio", "t_c020", "t_c030", f"anni_pos_c020", "anni_c020", f"{p}_c020", "promossa"]
        print(_tabella(w.sort_values("t_c020", ascending=False), cols, 10))
    # ------------------------------------------------ crollo
    V = pd.read_parquet(OUT / "crollo_varianti.parquet")
    Vc = V[V.conferma != "NESSUNA"]
    vo, vn = Vc[Vc.corsa == "vecchio"], Vc[Vc.corsa == "nuovo"]
    print(f"\n===== crollo intraday: {len(vo)} varianti (+48 riferimenti)")
    print(f"  netto>0 R vecchio (0,46): {int((vo.R > 0).sum())}  (R e $ a 0,46 e 0,69: "
          f"{int(((vo.R > 0) & (vo.R15 > 0) & (vo.usd > 0) & (vo.usd15 > 0)).sum())})")
    print(f"  netto>0 R a 0,20: {int((vn.R > 0).sum())}; a 0,30: {int((vn.R15 > 0).sum())}; "
          f"R e $ a 0,20 e 0,30: {int(((vn.R > 0) & (vn.R15 > 0) & (vn.usd > 0) & (vn.usd15 > 0)).sum())}")
    print(f"  t>=3 {int((vn.t >= 3).sum())}, anni>=7 {int((vn.anni_pos >= 7).sum())}, p<0,01 {int((vn.p < 0.01).sum())},"
          f" meglio rif {int(vn.meglio_rif.sum())}, PASSA {int(vn.passa.sum())}")
    m = vo.set_index(["tf", "k", "conferma", "obiettivo", "lato"])
    vn2 = vn.set_index(["tf", "k", "conferma", "obiettivo", "lato"]).assign(t_vecchio=m.t, R_vecchio=m.R)
    vn2 = vn2.reset_index().sort_values("t", ascending=False)
    cols = ["tf", "k", "conferma", "obiettivo", "lato", "n", "lordo_usd", "R_med_usd", "R_vecchio", "R", "R15",
            "usd", "t_vecchio", "t_op", "t_mese", "anni_pos", "p", "rif_R", "passa"]
    print(_tabella(vn2, cols, 10))
    vn2.to_parquet(OUT / "crollo_sintesi.parquet")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    parte = sys.argv[1] if len(sys.argv) > 1 else "sintesi"
    {"f3": parte_f3, "f4": parte_f4, "crollo": parte_crollo, "sintesi": sintesi}[parte]()
