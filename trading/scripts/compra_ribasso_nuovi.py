#!/usr/bin/env python3
""""Compra il ribasso" (M1 invariata) su quattro indici mai usati.

Registrazione VINCOLANTE: docs/compra-ribasso-nuovi-indici-registrazione.md
(con l'Emendamento 1; commit 769dfbf). Regola = candidato M1 di
docs/multigiorno-paniere-candidati.md, codice di scoperta multi_f2_ritorno.py
importato e usato SENZA modifiche (prepara, segnali_mercato, operazioni,
misure); si adattano solo la lettura dei dati e il periodo (globali ANNO0/ANNO1).

M1: MOSSA 5 giornate 1,5 x ATR20, tenuta 5, stop 2 x ATR20, filtro media 200
(long sopra, short sotto), 1R = 2 x ATR20; costi x1 e x1,5; swap 3% annuo del
nominale long e short, x3 il mercoledi'.

Fasi:
  python compra_ribasso_nuovi.py controllo -> riproduce M1 sull'S&P della scoperta
                                              (65 op, +0,396 R, t 4,853) e le operazioni
                                              salvate da f2_operazioni.parquet
  python compra_ribasso_nuovi.py test      -> controllo (deve coincidere), poi UNA sola
                                              esecuzione su D:\\ricerca_multi\\nuovi

Ipotesi primaria: portafoglio dei 4 indici a rischio uguale (somma in R).
Placebo (1000 serie, seed 12345, statistica = netto totale R a costi x1):
  direzione casuale (stesse operazioni), date casuali con la stessa direzione
  estratte fra le giornate nello stesso stato rispetto alla media 200 (criterio);
  date casuali senza stato (solo riferimento).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import multi_f2_ritorno as f2          # noqa: E402

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

BASE = Path(r"D:\ricerca_multi")
SCOP = BASE / "scoperta" / "PANIERE_D1.parquet"
NUOVI = BASE / "nuovi" / "PANIERE_D1.parquet"
COSTI_NUOVI = BASE / "nuovi" / "costi.csv"
RIS = BASE / "risultati"

SEG, H, ST, FILT = ("MOSSA", 5, 1.5), 5, 1, 1          # M1, invariata
ISIG = f2.SEGNALI.index(SEG)
REGOLA = f"{f2.nome_segnale(ISIG)} H{H} {'stop' if ST else 'tempo'} {'m200' if FILT else 'tutti'}"
MERCATI = ["JPXJPY", "UKXGBP", "ETXEUR", "FRXEUR"]
NOMI = {"JPXJPY": "Nikkei", "UKXGBP": "FTSE", "ETXEUR": "Euro Stoxx", "FRXEUR": "CAC"}
T_SOGLIA, P_SOGLIA = 2.0, 0.05
ATTESO_M1 = dict(n=65, netto_R=0.396, t=4.853)


# ---------------------------------------------------------------- motore (codice di scoperta)
def ops_mercato(dval, mercato, costo, anno0, anno1):
    """Operazioni M1 su un mercato con le funzioni di multi_f2_ritorno, senza modifiche."""
    f2.ANNO0, f2.ANNO1 = anno0, anno1
    g = dval[dval["mercato"] == mercato]
    P = f2.prepara(g, {"rt": costo, "oro": False})
    es = P["es"]
    dirz = f2.segnali_mercato(P, ISIG, FILT)
    ent, dr = f2.operazioni(P, dirz, H, ST)
    L, S = es[(H, ST, 1)], es[(H, ST, -1)]

    def pick(k):
        return np.where(dr == 1, L[k][ent], S[k][ent])
    op = pd.DataFrame({
        "mercato": mercato, "dir": dr, "ent_idx": ent,
        "segnale_data": pd.to_datetime(P["date"][ent - 1]),
        "entrata_data": pd.to_datetime(P["date"][ent]),
        "uscita_data": pd.to_datetime(P["date"][pick("uscita").astype(int)]) if len(ent) else pd.to_datetime([]),
        "prezzo_entrata": g.sort_values("giorno")["open"].to_numpy(float)[ent],
        "rischio_punti": f2.STOP_ATR * P["atr"][ent - 1],      # 1R = 2 x ATR20 del segnale
        "lordo": pick("lordo"), "swap": pick("swap"), "costo": pick("costo"),
        "netto": pick("netto"), "stopp": pick("stopp"),
        "netto_opposto": np.where(dr == 1, S["netto"][ent], L["netto"][ent]),
    })
    op["netto15"] = op["netto"] - 0.5 * op["costo"]
    return op, P


def placebo_matrici(op, P, rng, solo_dopo_m200):
    """Matrici NPLAC x n (una colonna per operazione): direzione casuale, date casuali
    (stessa direzione) senza stato e nello stesso stato rispetto alla media 200.
    La somma delle colonne di un sottoinsieme da' il placebo di quel sottoinsieme."""
    n = len(op)
    es = P["es"]
    L, S = es[(H, ST, 1)], es[(H, ST, -1)]
    dr = op["dir"].to_numpy()
    vr, vo = op["netto"].to_numpy(), op["netto_opposto"].to_numpy()
    mask = rng.random((f2.NPLAC, n)) < 0.5
    pdir = np.where(mask, vo[None, :], vr[None, :])
    eleg = es[(H, ST, "eleg")]
    cs, ss = P["c"][eleg - 1], P["sma"][eleg - 1]
    if solo_dopo_m200:                       # le prime 200 giornate servono solo agli indicatori
        eleg_u = eleg[~np.isnan(ss)]
    else:
        eleg_u = eleg
    pos = eleg_u[rng.integers(0, len(eleg_u), size=(f2.NPLAC, n))]
    pdat = np.where(dr[None, :] == 1, L["netto"][pos], S["netto"][pos])
    with np.errstate(invalid="ignore"):
        eL, eS = eleg[cs > ss], eleg[cs < ss]
    u = rng.random((f2.NPLAC, n))
    vL = L["netto"][eL[(u * len(eL)).astype(int)]] if len(eL) else np.zeros((f2.NPLAC, n))
    vS = S["netto"][eS[(u * len(eS)).astype(int)]] if len(eS) else np.zeros((f2.NPLAC, n))
    pflt = np.where(dr[None, :] == 1, vL, vS)
    return pdir, pdat, pflt


def anni_R(op, anni):
    return op.groupby(op["uscita_data"].dt.year)["netto"].sum().reindex(anni, fill_value=0.0)


def riepilogo(op, mesi, anni, pdir, pdat, pflt):
    """f2.misure (t mensile, dd, ...) + p dei tre placebo + anni sul periodo dichiarato."""
    tot = op["netto"].sum()
    r = f2.misure(op, mesi, pdir.sum(1), pdat.sum(1))
    r["p_date_senza_stato"] = r.pop("p_date")
    r["p_date_stato"] = (1 + (pflt.sum(1) >= tot).sum()) / (f2.NPLAC + 1)
    r["plac_date_stato_medio_R"] = pflt.sum(1).mean() / max(len(op), 1)
    r["totale15_R"] = op["netto15"].sum()
    r["peggiore_R"] = op["netto"].min() if len(op) else np.nan
    r["long"] = (op["dir"] == 1).mean() if len(op) else np.nan
    ya = anni_R(op, anni)
    r["anni_pos"] = int((ya > 0).sum())
    r["anni_tot"] = len(anni)
    r["mesi"] = len(mesi)
    return r, ya


# ---------------------------------------------------------------- PASSO 1
def fase_controllo():
    scop = pd.read_parquet(SCOP)
    sval = scop[scop["valida"]]
    costi = pd.read_csv(BASE / "costi.csv").set_index("mercato")["costo_rt"].to_dict()
    op, P = ops_mercato(sval, "SPXUSD", costi["SPXUSD"], 2010, 2017)
    primo = pd.Timestamp(P["date"][P["base_ok"]][0]).to_period("M")   # convenzione della scoperta
    mesi = pd.period_range(primo, "2017-12", freq="M")
    rng = np.random.default_rng(f2.SEED)
    pdir, pdat, pflt = placebo_matrici(op, P, rng, solo_dopo_m200=False)
    r, ya = riepilogo(op, mesi, list(range(2011, 2018)), pdir, pdat, pflt)
    ref = pd.read_parquet(RIS / "f2_operazioni.parquet",
                          columns=["regola", "mercato", "entrata_data", "uscita_data", "dir", "netto", "netto15"])
    ref = ref[(ref["regola"] == REGOLA) & (ref["mercato"] == "SPXUSD")]
    mm = op.merge(ref, on=["mercato", "entrata_data", "dir"], how="outer", indicator=True, suffixes=("", "_ref"))
    uguali = int((mm["_merge"] == "both").sum())
    dmax = float(np.nanmax(np.abs(mm["netto"] - mm["netto_ref"])))
    dusc = int((mm["uscita_data"] != mm["uscita_data_ref"]).sum())
    ok = (r["n"] == ATTESO_M1["n"] and round(r["netto_R"], 3) == ATTESO_M1["netto_R"]
          and round(r["t_mens"], 3) == ATTESO_M1["t"] and uguali == len(op) == len(ref)
          and dmax < 1e-12 and dusc == 0)
    print(f"CONTROLLO DEL CODICE: M1 ({REGOLA}) su SPXUSD, scoperta 2010-2017, mesi {mesi[0]} -> {mesi[-1]} ({len(mesi)})")
    print(f"  n {r['n']}  netto {r['netto_R']:.4f} R (x1,5 {r['netto15_R']:.4f})  totale {r['totale_R']:.2f} R  "
          f"t mensile {r['t_mens']:.4f}  anni + {r['anni_pos']}/7  dd {r['dd_R']:.2f}  "
          f"p dir {r['p_dir']:.3f}  p date {r['p_date_senza_stato']:.3f}  p date stato {r['p_date_stato']:.3f}")
    print(f"  operazioni salvate dalla scoperta {len(ref)}, uguali {uguali}, differenza netto max {dmax:.1e}, "
          f"uscite diverse {dusc}")
    print(f"  attesi: n 65, netto +0,396, t 4,853 -> {'COINCIDE' if ok else 'NON COINCIDE'}")
    return ok, r


# ---------------------------------------------------------------- PASSO 2
def fase_test():
    ok, rc = fase_controllo()
    assert ok, "il controllo del codice non coincide: il test non si apre"
    d = pd.read_parquet(NUOVI)
    costi = pd.read_csv(COSTI_NUOVI).set_index("mercato")["costo_rt"].to_dict()
    assert sorted(d["mercato"].unique()) == sorted(MERCATI), d["mercato"].unique()
    # Emendamento 1: valida = M5 >= 80% della mediana del mercato (gia' nel file): si ricontrolla
    for m, g in d.groupby("mercato"):
        assert (g["valida"] == (g["barre"] >= 0.8 * g["barre"].median())).all(), m
    assert d[d["mercato"] == "ETXEUR"]["giorno"].max() <= pd.Timestamp("2018-12-14")
    dval = d[d["valida"]]
    ultimo = d["giorno"].max()
    anno1 = ultimo.year

    print(f"\nTEST su {NUOVI} (ultima giornata {ultimo.date()})")
    print(d.groupby("mercato").agg(giornate=("giorno", "size"), valide=("valida", "sum"),
                                   da=("giorno", "min"), a=("giorno", "max"),
                                   M5_mediana=("barre", "median")).loc[MERCATI].to_string())

    rng = np.random.default_rng(f2.SEED)
    ops, PM, PL, inizio = [], {}, {}, {}
    for m in MERCATI:
        op, P = ops_mercato(dval, m, costi[m], 2010, anno1)
        # prima giornata con media 200 (la 200a valida): le entrate possibili partono dal giorno dopo
        i200 = int(np.argmax(~np.isnan(P["sma"])))
        inizio[m] = pd.Timestamp(P["date"][i200 + 1])
        assert (op["entrata_data"] >= inizio[m]).all()
        PM[m] = P
        PL[m] = placebo_matrici(op, P, rng, solo_dopo_m200=True)
        ops.append(op)
    op_all = pd.concat(ops, ignore_index=True)
    col_m = {m: (op_all["mercato"] == m).to_numpy() for m in MERCATI}
    PD = np.concatenate([PL[m][0] for m in MERCATI], axis=1)
    PU = np.concatenate([PL[m][1] for m in MERCATI], axis=1)
    PF = np.concatenate([PL[m][2] for m in MERCATI], axis=1)

    fine_m = ultimo.to_period("M")
    p0 = min(inizio.values()).to_period("M")
    mesi_port = pd.period_range(p0, fine_m, freq="M")
    anni_port = list(range(p0.year, anno1 + 1))

    def periodo(m):
        fm = d[d["mercato"] == m]["giorno"].max().to_period("M")
        pm = inizio[m].to_period("M")
        return pd.period_range(pm, fm, freq="M"), list(range(pm.year, fm.year + 1))

    righe, anni_t = [], {}

    def aggiungi(nome, sel, mesi, anni):
        o = op_all[sel].reset_index(drop=True)
        r, ya = riepilogo(o, mesi, anni, PD[:, sel], PU[:, sel], PF[:, sel])
        r["ambito"] = nome
        r["periodo"] = f"{mesi[0]} -> {mesi[-1]}"
        righe.append(r)
        anni_t[nome] = ya

    tutti = np.ones(len(op_all), bool)
    lng, sht = (op_all["dir"] == 1).to_numpy(), (op_all["dir"] == -1).to_numpy()
    aggiungi("PORTAFOGLIO", tutti, mesi_port, anni_port)
    aggiungi("portafoglio long", lng, mesi_port, anni_port)
    aggiungi("portafoglio short", sht, mesi_port, anni_port)
    for m in MERCATI:
        mesi, anni = periodo(m)
        aggiungi(m, col_m[m], mesi, anni)
        aggiungi(f"{m} long", col_m[m] & lng, mesi, anni)
        aggiungi(f"{m} short", col_m[m] & sht, mesi, anni)
    V = pd.DataFrame(righe).set_index("ambito")
    V["soglia_anni"] = [math.ceil(2 / 3 * x) for x in V["anni_tot"]]

    # anni positivi senza gli anni parziali (primo anno, se il periodo non parte a gennaio; 2026)
    def senza_parziali(nome, mesi):
        ya = anni_t[nome]
        drop = [a for a in (mesi[0].year, mesi[-1].year)
                if (a == mesi[0].year and mesi[0].month != 1) or (a == mesi[-1].year and mesi[-1].month != 12)]
        y = ya.drop(drop, errors="ignore")
        return f"{int((y > 0).sum())}/{len(y)}"
    V["anni_pos_interi"] = [senza_parziali(i, pd.period_range(*V.loc[i, "periodo"].split(" -> "), freq="M"))
                            for i in V.index]

    P_ = V.loc["PORTAFOGLIO"]
    crit = {
        "netto > 0 a x1": P_["netto_R"] > 0,
        "netto > 0 a x1,5": P_["netto15_R"] > 0,
        f"t mensile >= {T_SOGLIA:g}": P_["t_mens"] >= T_SOGLIA,
        "anni positivi >= 2/3": P_["anni_pos"] >= P_["soglia_anni"],
        "p direzione < 0,05": P_["p_dir"] < P_SOGLIA,
        "p date (stesso stato m200) < 0,05": P_["p_date_stato"] < P_SOGLIA,
    }
    verdetto = "PASSA" if all(crit.values()) else "NON PASSA"

    col = ["periodo", "n", "op_mese", "long", "netto_R", "netto15_R", "totale_R", "totale15_R", "lordo_R",
           "swap_R", "costo_R", "t_mens", "t_op", "anni_pos", "anni_tot", "soglia_anni", "anni_pos_interi",
           "p_dir", "p_date_stato", "p_date_senza_stato", "plac_date_stato_medio_R", "plac_date_medio_R",
           "quota_stop", "dd_R", "peggiore_R"]
    print(f"\nPORTAFOGLIO dei 4 indici a rischio uguale (mesi {mesi_port[0]} -> {mesi_port[-1]}, {len(mesi_port)}; "
          f"anni {anni_port[0]}-{anni_port[-1]}, primo e ultimo parziali)")
    print(V.loc[["PORTAFOGLIO", "portafoglio long", "portafoglio short"], col].round(3).T.to_string())
    print("\nCRITERIO (registrazione):")
    for k, v in crit.items():
        print(f"  {k}: {'si' if v else 'NO'}")
    print(f"VERDETTO: {verdetto}")
    print("\nPER INDICE E PER LATO (senza verdetto)")
    print(V.drop(index=["PORTAFOGLIO", "portafoglio long", "portafoglio short"])[col].round(3).T.to_string())
    A = pd.DataFrame(anni_t).T
    print("\nR netti per anno di uscita (primo anno da settembre circa, ultimo parziale)")
    print(A.round(1).to_string())

    # previsioni
    long_pos = [m for m in MERCATI if V.loc[f"{m} long", "netto_R"] > 0]
    print("\nPREVISIONI")
    print(f"  1. lato long positivo su almeno 3 indici su 4: {len(long_pos)}/4 {long_pos} -> "
          f"{'confermata' if len(long_pos) >= 3 else 'sbagliata'}")
    print(f"  2. il portafoglio NON arriva a t 2: t {P_['t_mens']:.2f} -> "
          f"{'confermata' if P_['t_mens'] < 2 else 'sbagliata'}")

    # sensibilita' (non criterio): mesi con la convenzione della scoperta (dal primo mese con ATR20)
    pS = min(pd.Timestamp(PM[m]["date"][PM[m]["base_ok"]][0]) for m in MERCATI).to_period("M")
    rS = f2.misure(op_all, pd.period_range(pS, fine_m, freq="M"), PD.sum(1), PU.sum(1))
    print(f"\n(riferimento) t mensile con i mesi dal primo ATR20 ({pS}), come nella scoperta: {rS['t_mens']:.3f}")

    # diagnostica 2020 / mese peggiore
    mm = op_all.groupby(op_all["uscita_data"].dt.to_period("M"))["netto"].sum()
    print("mesi peggiori del portafoglio:", ", ".join(f"{k} {v:+.1f}" for k, v in mm.nsmallest(5).items()))

    RIS.mkdir(parents=True, exist_ok=True)
    op_all.drop(columns=["ent_idx"]).assign(regola=REGOLA).to_parquet(RIS / "nuovi_operazioni.parquet", index=False)
    V.reset_index().assign(verdetto=np.where(V.index == "PORTAFOGLIO", verdetto, "")) \
        .to_parquet(RIS / "nuovi_riepilogo.parquet", index=False)
    A.columns = [str(c) for c in A.columns]
    A.reset_index(names="ambito").to_parquet(RIS / "nuovi_anni.parquet", index=False)
    mens = mm.reindex(mesi_port, fill_value=0.0)
    pd.DataFrame({"mese": mens.index.astype(str), "netto_R": mens.to_numpy()}) \
        .to_parquet(RIS / "nuovi_mensili.parquet", index=False)
    print(f"\nscritti: {RIS}\\nuovi_operazioni|nuovi_riepilogo|nuovi_anni|nuovi_mensili.parquet")


if __name__ == "__main__":
    fase = sys.argv[1] if len(sys.argv) > 1 else "controllo"
    {"controllo": fase_controllo, "test": fase_test}[fase]()
