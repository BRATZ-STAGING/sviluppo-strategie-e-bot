#!/usr/bin/env python3
"""Verifica 2018 -> 06/07/2026 dei candidati macro E-C1 e E-C2 (FOMC, segui il primo movimento).

Candidati congelati: docs/macro-oro-candidati.md (commit d06ed26). Regola = codice di
macro_e_eventi.py, importato e usato SENZA modifiche (Griglia, carica_d1, esiti_d1, istanze,
operazione, misure, placebo, pesi_swap). Qui si adatta solo:
  - la lettura dei dati (globali M5, D1, ANNI del modulo; D1 di verifica con la coda della
    scoperta concatenata davanti SOLO per l'ATR20);
  - il costo per anno (globali RT ed EXTRA del modulo impostati anno per anno: RT 0,46 $ fino
    al 2019, poi SPREAD di verifica_bot.py + 0,06 $; EXTRA = 2 x RT come nel codice congelato);
  - il calcolo, che ripete per le sole due regole le righe di main() della famiglia E2
    (FOMC, d5/d15, segue, filtro 0, uscita 20:55 UTC, senza stop).

Fasi:
  python macro_verifica.py riproduci -> rifa' E-C1/E-C2 sulla scoperta e li confronta coi numeri
                                       congelati e con e_operazioni.parquet (operazione per operazione)
  python macro_verifica.py verifica  -> ripete la riproduzione (si ferma se non coincide), poi UNA
                                       sola esecuzione sul 2018 -> 06/07/2026

Le M5 di verifica si usano da sole (anche per i giorni di controllo del placebo: i controlli
del dicembre 2017 non hanno barre e restano fuori). Contano gli eventi con T dal 2018-01-01.

Scrive in D:\\ricerca_macro\\risultati\\:
    verifica_operazioni.parquet  una riga per operazione (E-C1, E-C2) nel 2018-2026
    verifica_riepilogo.parquet   una riga per candidato con misure, anni, p, diagnostica
    verifica_periodi.parquet     2018-2021 e 2022-2026 separati
"""
from __future__ import annotations

import gc
import os
import sys

import numpy as np
import pandas as pd

import macro_e_eventi as me
from verifica_bot import SPREAD

SCOP_M5 = r"D:\ricerca_zero\scoperta\XAUUSD_M5.parquet"
VER_M5 = r"D:\ricerca_zero\verifica\XAUUSD_M5.parquet"
SCOP_D1 = r"D:\ricerca_macro\scoperta\MACRO_D1.parquet"
VER_D1 = r"D:\ricerca_macro\verifica\MACRO_D1.parquet"
OUT = me.OUT
CODA_D1 = "2017-09-01"          # coda della scoperta davanti alla verifica, solo per l'ATR20
INIZIO_VER = pd.Timestamp("2018-01-01", tz="UTC")
REGOLE = {"E-C1": 5, "E-C2": 15}
NOMI_SCOP = {"E-C1": "E2 FOMC d5 segue filt0 eod stop0", "E-C2": "E2 FOMC d15 segue filt0 eod stop0"}
ATTESI = {"E-C1": dict(n=71, netto=0.368046, netto15=0.289103, usd=3.895944, t=3.046168, anni_pos=9,
                       p_ora=0.000999, p_dir=0.000999),
          "E-C2": dict(n=70, netto=0.31904, netto15=0.292783, usd=3.061614, t=3.00438, anni_pos=7,
                       p_ora=0.000999, p_dir=0.001998)}
SOGLIA_T = 2.4                  # k = 2 candidati
pd.set_option("display.width", 200)

# ------------------------------------------------------------- lettura concatenata del D1
_read_orig = pd.read_parquet


def _read(path, *a, **k):
    if path == "CONCAT_D1":
        s = _read_orig(SCOP_D1)
        v = _read_orig(VER_D1)
        out = pd.concat([s[s.index >= CODA_D1], v])
        assert out.index.is_monotonic_increasing and out.index.is_unique
        return out
    return _read_orig(path, *a, **k)


pd.read_parquet = _read


def rt_anno(anno):
    return 0.46 if anno <= 2019 else SPREAD[anno] + 0.06


# ------------------------------------------------------------------- calcolo delle regole
def calcola(periodo):
    """Esegue E-C1 ed E-C2 con il codice di macro_e_eventi sul periodo indicato."""
    if periodo == "scoperta":
        me.M5, me.D1, me.ANNI = SCOP_M5, SCOP_D1, list(range(2009, 2018))
    else:
        me.M5, me.D1, me.ANNI = VER_M5, "CONCAT_D1", list(range(2018, 2027))
    G = me.Griglia()
    W = me.pesi_swap(G.n * 5 // 1440 + 30)
    d = me.carica_d1()
    fine_min = d["fine_min"].to_numpy()
    _, atr_d, _ = me.esiti_d1(d)
    I = me.istanze(G)
    if periodo == "verifica":
        t_ev = I[I["vero"]].set_index("evento")["T"]
        t0v = int((INIZIO_VER - me.T0) // pd.Timedelta("1min"))
        I = I[I["evento"].map(t_ev) >= t0v].reset_index(drop=True)
    T = I["T"].to_numpy()
    ok = I["ok"].to_numpy()
    vero = I["vero"].to_numpy()
    ev_id = I["evento"].to_numpy()
    anni_i = I["anno"].to_numpy()
    tipo_i = I["tipo"].to_numpy()

    def atr_prima(t):                       # come in main()
        j = np.searchsorted(fine_min, t, side="right") - 1
        return np.where(j >= 0, atr_d[np.clip(j, 0, None)], np.nan)

    R_i = 0.5 * atr_prima(T)
    # matrice dei controlli FOMC (come ctrl_slots di main())
    e_idx = np.where(vero & (tipo_i == "FOMC"))[0]
    mat = np.full((len(e_idx), 2 * me.KCTRL), -1)
    pos = {e: k for k, e in enumerate(ev_id[e_idx])}
    cnt = np.zeros(len(e_idx), int)
    for ii in np.where(~vero & (tipo_i == "FOMC") & ok)[0]:
        k = pos[ev_id[ii]]
        mat[k, cnt[k]] = ii
        cnt[k] += 1
    ev = I.iloc[e_idx]
    info = dict(eventi=len(e_idx), eventi_ok=int(ev["ok"].sum()),
                scartati=", ".join(str(x) for x in ev.loc[~ev["ok"], "data_ny"]),
                ctrl_mediana=float(np.median(cnt)))

    def opera(ent_t, ex_t, dz):
        """operazione() con il costo dell'anno di ogni istanza (globali RT/EXTRA del modulo)."""
        out = None
        for a in np.unique(anni_i):
            me.RT = rt_anno(a) if periodo == "verifica" else 0.46
            me.EXTRA = 2 * me.RT
            r = me.operazione(G, W, ent_t, ex_t, dz, R_i, 0, T)
            r["rt"] = np.full(len(T), me.RT)
            if out is None:
                out = {k: v.copy() for k, v in r.items()}
            sel = anni_i == a
            for k in out:
                out[k][sel] = r[k][sel]
        me.RT, me.EXTRA = 0.46, 2 * 0.46
        return out

    def pack(r, sel):                       # come pack() di main()
        out = [np.full(len(I), np.nan) for _ in range(3)]
        lordo_sw = r["lordo"] + r["swap"]
        out[0][sel] = (lordo_sw - r["costo"])[sel]
        out[1][sel] = (lordo_sw - 1.5 * r["costo"])[sel]
        out[2][sel] = r["usd"][sel]
        return out

    eod = (T // 1440) * 1440 + 20 * 60 + 55
    risultati, operazioni = {}, []
    for cid, dmin in REGOLE.items():
        p0, pd_ = G.px(T), G.px(T + dmin)
        mv = pd_ - p0
        val0 = ok & (G.barre(T, T + dmin) >= 1) & ~np.isnan(R_i) & (mv != 0) & ~np.isnan(mv)
        sgn = np.sign(np.nan_to_num(mv)).astype(int)
        valido = val0 & (eod > T + dmin + 5)
        rl = opera(T + dmin, eod, np.ones(len(T), int))
        rs = opera(T + dmin, eod, -np.ones(len(T), int))
        L_, S_ = pack(rl, valido), pack(rs, valido)
        comb = [np.where(sgn == 1, L_[k], S_[k]) for k in range(3)]   # segue, filtro 0
        net, net15, usd = comb
        ne = net[e_idx]
        m = me.misure(ne, net15[e_idx], usd[e_idx], anni_i[e_idx])
        cm = np.where(mat >= 0, np.nan_to_num(net[np.maximum(mat, 0)]), np.nan)
        rng = np.random.default_rng(me.SEED)
        p_ora, p_dir = me.placebo(np.nansum(ne), cm, L_[0][e_idx], S_[0][e_idx], rng)
        m.update(p_ora=p_ora, p_dir=p_dir)
        risultati[cid] = m
        # dettaglio per operazione sugli eventi veri
        for ii in e_idx:
            if np.isnan(net[ii]):
                continue
            r = rl if sgn[ii] == 1 else rs
            R = R_i[ii]
            costo_usd = r["costo"][ii] * R
            operazioni.append(dict(
                candidato=cid, data_ny=str(I.at[ii, "data_ny"]), ora_ny=I.at[ii, "ora_ny"],
                anno=int(anni_i[ii]), T_utc=me.T0 + pd.Timedelta(minutes=int(T[ii])), dir=int(sgn[ii]),
                R_usd=R, entrata=G.px(np.array([T[ii] + dmin]))[0], uscita=G.px(np.array([eod[ii]]))[0],
                lordo_usd=(r["lordo"][ii] + r["swap"][ii]) * R, costo_usd=costo_usd, rt=r["rt"][ii],
                netto=net[ii], netto15=net15[ii], usd=usd[ii], usd15=usd[ii] - 0.5 * costo_usd))
    del G
    gc.collect()
    return risultati, pd.DataFrame(operazioni), info


# ------------------------------------------------------------------------ riproduzione
def riproduci():
    ris, ops, info = calcola("scoperta")
    print(f"Scoperta: eventi FOMC {info['eventi']}, validi {info['eventi_ok']}, "
          f"controlli (mediana) {info['ctrl_mediana']:.0f}")
    O = pd.read_parquet(os.path.join(OUT, "e_operazioni.parquet"))
    tutto_ok = True
    for cid, att in ATTESI.items():
        m = ris[cid]
        righe = []
        for k, v in att.items():
            x = m[k]
            if k in ("n", "anni_pos"):
                good = x == v
            elif k.startswith("p_"):
                good = abs(x - v) < 1e-6
            else:
                good = abs(x - v) <= 0.01 * abs(v)
            tutto_ok &= bool(good)
            righe.append(f"{k} {x:.4f}/{v:.4f}{'' if good else ' NO'}")
        o = O[O["regola"] == NOMI_SCOP[cid]].sort_values("data_ny")
        q = ops[ops["candidato"] == cid].sort_values("data_ny")
        same = (len(o) == len(q) and (o["data_ny"].to_numpy() == q["data_ny"].to_numpy()).all()
                and np.allclose(o["netto"].to_numpy(), q["netto"].to_numpy(), atol=1e-9))
        tutto_ok &= bool(same)
        print(f"{cid}: " + ", ".join(righe) + f"; operazioni identiche a e_operazioni: {same}")
    print("RIPRODUZIONE:", "OK" if tutto_ok else "NON COINCIDE")
    return tutto_ok


# --------------------------------------------------------------------------- verifica
def estese(q, m, anni):
    """Misure aggiuntive su un insieme di operazioni (q ordinato per data)."""
    x = q["netto"].to_numpy()
    top5 = np.sort(x)[::-1][:5].sum()
    pareggio_usd = q["lordo_usd"].mean()                                   # costo $ che azzera il netto in $
    pareggio_R = (q["lordo_usd"] / q["R_usd"]).sum() / (1 / q["R_usd"]).sum()  # costo $ che azzera il netto in R
    return dict(usd15=q["usd15"].mean(), lordo_usd=q["lordo_usd"].mean(), costo_usd=q["costo_usd"].mean(),
                peggiore_R=x.min(), peggiore_usd=q["usd"].min(), migliore_R=x.max(),
                quota_top5=top5 / x.sum() if x.sum() != 0 else np.nan,
                t_senza_top5=_t(np.sort(x)[:-5]), vince=(x > 0).mean(),
                pareggio_usd=pareggio_usd, pareggio_R_usd=pareggio_R,
                pareggio_x=pareggio_usd / q["costo_usd"].mean())


def _t(x):
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 2 else np.nan


def verifica():
    if not riproduci():
        sys.exit("Riproduzione non coincidente: la verifica non si apre.")
    gc.collect()
    print("\n=== VERIFICA 2018 -> 06/07/2026 (una sola esecuzione)")
    ris, ops, info = calcola("verifica")
    print(f"eventi FOMC programmati {info['eventi']}, validi {info['eventi_ok']}"
          + (f" (scartati: {info['scartati']})" if info["scartati"] else "")
          + f"; controlli validi per evento (mediana) {info['ctrl_mediana']:.0f}")
    ops.to_parquet(os.path.join(OUT, "verifica_operazioni.parquet"))
    anni = me.ANNI
    righe, periodi = [], []
    for cid in REGOLE:
        m = ris[cid]
        q = ops[ops["candidato"] == cid].sort_values("data_ny")
        e = estese(q, m, anni)
        anni_attivi = sorted(q["anno"].unique())
        pos9 = m["anni_pos"]
        pos8 = int(sum(m[f"a{a}"] > 0 for a in anni if a <= 2025))
        criteri = dict(netto_x1=m["netto"] > 0, netto_x15=m["netto15"] > 0, t=m["t"] >= SOGLIA_T,
                       anni=pos9 >= int(np.ceil(2 / 3 * len(anni_attivi))),
                       placebo=(m["p_ora"] < 0.05) and (m["p_dir"] < 0.05))
        righe.append(dict(candidato=cid, **{k: v for k, v in m.items()}, **e, anni_tot=len(anni_attivi),
                          anni_pos_2018_2025=pos8, **{f"ok_{k}": v for k, v in criteri.items()},
                          passa=all(criteri.values())))
        for nome, a, b in (("2018-2021", 2018, 2021), ("2022-2026", 2022, 2026)):
            s = q[(q["anno"] >= a) & (q["anno"] <= b)]
            x = s["netto"].to_numpy()
            periodi.append(dict(candidato=cid, periodo=nome, n=len(s), netto=x.mean(),
                                netto15=s["netto15"].mean(), usd=s["usd"].mean(), usd15=s["usd15"].mean(),
                                t=_t(x), lordo_usd=s["lordo_usd"].mean(), costo_usd=s["costo_usd"].mean(),
                                anni_pos=int((s.groupby("anno")["netto"].sum() > 0).sum()),
                                anni=s["anno"].nunique()))
    Rz = pd.DataFrame(righe)
    P = pd.DataFrame(periodi)
    Rz.to_parquet(os.path.join(OUT, "verifica_riepilogo.parquet"))
    P.to_parquet(os.path.join(OUT, "verifica_periodi.parquet"))
    c1 = ["n", "netto", "netto15", "usd", "usd15", "t", "anni_pos", "anni_tot", "p_ora", "p_dir", "dd",
          "peggiore_R", "quota_top5", "passa"]
    print(Rz.set_index("candidato")[c1].round(3).to_string())
    print("\nR per anno:")
    print(Rz.set_index("candidato")[[f"a{a}" for a in anni]].round(2).to_string())
    print("\nDiagnostica (costi $/oncia):")
    print(Rz.set_index("candidato")[["lordo_usd", "costo_usd", "pareggio_usd", "pareggio_R_usd", "pareggio_x",
                                      "vince", "t_senza_top5", "anni_pos_2018_2025",
                                      "ok_netto_x1", "ok_netto_x15", "ok_t", "ok_anni", "ok_placebo"]]
          .round(3).to_string())
    print("\nPer periodo:")
    print(P.round(3).to_string(index=False))


if __name__ == "__main__":
    fase = sys.argv[1] if len(sys.argv) > 1 else "riproduci"
    {"riproduci": riproduci, "verifica": verifica}[fase]()
