"""Ritorno alla media intragiornaliero: entrare CONTRO uno scatto rapido.

Ipotesi pre-registrata (testo integrale in
/workspace/dati_grezzi/ritorno_media/IPOTESI.txt, scritto PRIMA dei numeri):
dopo uno scatto di |X| >= S*ATR in N minuti si entra contro, con lo stop
appena oltre l'estremo dello scatto e obiettivo a 1,5R o 2R, chiudendo entro
120 minuti e comunque entro la sessione giornaliera.

Punti di attenzione (ognuno nasce da un errore gia' costato una misura):
- l'evento e' la CHIUSURA della candela t, l'ingresso e' l'APERTURA di t+1;
- lo stop vince i pareggi nello stesso minuto;
- niente operazioni sovrapposte;
- le sessioni sono ricavate dai buchi > 30 minuti nell'indice, quindi nessuna
  operazione attraversa lo stacco giornaliero (niente swap, niente prezzi di
  rollover) e "chiuso in giornata" e' garantito per costruzione;
- il costo e' 0,30 $ / distanza_di_stop espresso in R, sottratto sempre;
- risultati riportati separati per 2009-2019 e 2020-2026.

Uso:  python3 trading/scripts/prova_ritorno_media.py
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
FUORI = "/workspace/dati_grezzi/ritorno_media"

SPREAD = 0.30          # $ andata e ritorno
CUSCINETTO_ATR = 0.05  # stop oltre l'estremo dello scatto, in ATR
ORIZZONTE = 120        # minuti massimi di permanenza
MIN_RESIDUO = 30       # minuti minimi che devono restare nel segmento
BUCO_SEGMENTO = 30     # un buco > 30 minuti separa due sessioni

N_LISTA = (5, 15, 30)
S_LISTA = (0.20, 0.30, 0.50)
RR_LISTA = (1.5, 2.0)

PRIMARIA = dict(n=15, s=0.20, rr=1.5)

pd.set_option("display.width", 200)


# --------------------------------------------------------------------------
# preparazione dei vettori
# --------------------------------------------------------------------------
def prepara(m1: pd.DataFrame) -> dict:
    """Vettori numpy allineati al minuto + identificativo di segmento."""
    atr = daily_atr(m1, 14)
    giorni = m1.index.normalize()
    atr_min = atr.reindex(giorni).to_numpy(dtype="float64")

    idx = m1.index
    passo = np.diff(idx.view("int64")) // 60_000_000_000
    nuovo = np.concatenate([[True], passo > BUCO_SEGMENTO])
    seg = np.cumsum(nuovo) - 1

    d = dict(
        ts=idx,
        o=m1.open.to_numpy("float64"),
        h=m1.high.to_numpy("float64"),
        l=m1.low.to_numpy("float64"),
        c=m1.close.to_numpy("float64"),
        atr=atr_min,
        seg=seg.astype("int64"),
        anno=idx.year.to_numpy("int64"),
        ora=idx.hour.to_numpy("int64"),
    )
    # ora locale di New York (l'orologio del mercato e' locale, non UTC)
    ny = idx.tz_convert("America/New_York")
    d["ora_ny"] = ny.hour.to_numpy("int64")
    d["mezzora_ny"] = (ny.hour * 2 + (ny.minute >= 30)).to_numpy("int64")
    # ultimo indice di ciascun segmento
    fine = np.empty_like(d["seg"])
    bordi = np.flatnonzero(np.concatenate([np.diff(d["seg"]) != 0, [True]]))
    prec = 0
    for b in bordi:
        fine[prec:b + 1] = b
        prec = b + 1
    d["fine_seg"] = fine
    return d


def segnali(d: dict, n: int, s: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Indici dei minuti di segnale, verso dello scatto, estremo, |X|/ATR.

    Tutto causale: X usa solo close fino a t, l'estremo solo high/low fino a t.
    """
    c = d["c"]
    seg = d["seg"]
    x = np.full(c.shape, np.nan)
    x[n:] = c[n:] - c[:-n]
    # la finestra deve stare tutta nello stesso segmento
    stesso = np.zeros(c.shape, dtype=bool)
    stesso[n:] = seg[n:] == seg[:-n]

    ser_h = pd.Series(d["h"])
    ser_l = pd.Series(d["l"])
    hmax = ser_h.rolling(n).max().to_numpy()
    lmin = ser_l.rolling(n).min().to_numpy()

    atr = d["atr"]
    ampiezza = np.abs(x) / atr
    ok = stesso & np.isfinite(ampiezza) & (ampiezza >= s)
    # deve esserci una candela successiva nello stesso segmento e spazio residuo
    ok[:-1] &= (seg[1:] == seg[:-1])
    ok[-1] = False
    idx = np.flatnonzero(ok)
    idx = idx[(d["fine_seg"][idx] - idx) >= MIN_RESIDUO]

    verso = np.where(x[idx] > 0, -1, 1).astype("int64")   # -1 short, +1 long
    estremo = np.where(verso == -1, hmax[idx], lmin[idx])
    return idx, verso, estremo, ampiezza[idx]


# --------------------------------------------------------------------------
# simulazione
# --------------------------------------------------------------------------
def simula(d: dict, idx, verso, estremo, ampiezza, rr: float,
           stop_alt: np.ndarray | None = None,
           spostamento: np.ndarray | None = None) -> pd.DataFrame:
    """Percorso minuto per minuto, niente sovrapposizioni, stop vince i pari.

    ``stop_alt``    placebo A: distanza di stop imposta dall'esterno.
    ``spostamento`` placebo B: minuti di anticipo dell'ingresso (evento finto).
    """
    o, h, l, c = d["o"], d["h"], d["l"], d["c"]
    atr, seg, fine = d["atr"], d["seg"], d["fine_seg"]

    m = len(idx)
    ing_i = np.empty(m, dtype="int64")
    ris_r = np.empty(m)
    ris_costo = np.empty(m)
    ris_tipo = np.empty(m, dtype="int64")   # 1 obiettivo, -1 stop, 0 scadenza
    ris_stop = np.empty(m)
    ris_min = np.empty(m, dtype="int64")
    validi = np.zeros(m, dtype=bool)

    libero_da = -1
    for k in range(m):
        t = idx[k]
        e = t + 1
        if spostamento is not None:
            e = t + 1 - int(spostamento[k])
            if e <= 0 or seg[e] != seg[t] or (fine[e] - e) < MIN_RESIDUO:
                continue
        if e < libero_da:
            continue
        v = verso[k]
        p_ing = o[e]
        cusc = CUSCINETTO_ATR * atr[t]
        if stop_alt is not None:
            dist = float(stop_alt[k])
        else:
            if v == -1:
                dist = max(estremo[k] + cusc - p_ing, cusc)
            else:
                dist = max(p_ing - (estremo[k] - cusc), cusc)
        if not np.isfinite(dist) or dist <= 0:
            continue

        if v == -1:
            p_stop = p_ing + dist
            p_obj = p_ing - rr * dist
        else:
            p_stop = p_ing - dist
            p_obj = p_ing + rr * dist

        ultimo = min(e + ORIZZONTE - 1, fine[e])
        tipo = 0
        uscita = c[ultimo]
        j_fine = ultimo
        for j in range(e, ultimo + 1):
            if v == -1:
                colpo_stop = h[j] >= p_stop
                colpo_obj = l[j] <= p_obj
            else:
                colpo_stop = l[j] <= p_stop
                colpo_obj = h[j] >= p_obj
            if colpo_stop:            # lo stop vince sempre i pareggi
                tipo, uscita, j_fine = -1, p_stop, j
                break
            if colpo_obj:
                tipo, uscita, j_fine = 1, p_obj, j
                break

        r = (p_ing - uscita) / dist if v == -1 else (uscita - p_ing) / dist
        ing_i[k] = e
        ris_r[k] = r
        ris_costo[k] = SPREAD / dist
        ris_tipo[k] = tipo
        ris_stop[k] = dist
        ris_min[k] = j_fine - e + 1
        validi[k] = True
        libero_da = j_fine + 1

    sel = np.flatnonzero(validi)
    e_i = ing_i[sel]
    return pd.DataFrame({
        "ts": d["ts"][e_i],
        "anno": d["anno"][e_i],
        "ora": d["ora"][e_i],
        "ora_ny": d["ora_ny"][e_i],
        "mezzora_ny": d["mezzora_ny"][e_i],
        "verso": verso[sel],
        "ampiezza": ampiezza[sel],
        "stop_dollari": ris_stop[sel],
        "stop_atr": ris_stop[sel] / d["atr"][idx[sel]],
        "minuti": ris_min[sel],
        "tipo": ris_tipo[sel],
        "r_lordo": ris_r[sel],
        "costo": ris_costo[sel],
        "r_netto": ris_r[sel] - ris_costo[sel],
    })


# --------------------------------------------------------------------------
# riepiloghi
# --------------------------------------------------------------------------
def periodo(anni: np.ndarray) -> np.ndarray:
    return np.where(anni <= 2019, "2009-2019", "2020-2026")


def riepiloga(tr: pd.DataFrame) -> pd.DataFrame:
    tr = tr.assign(per=periodo(tr.anno.to_numpy()))
    g = tr.groupby("per")
    out = pd.DataFrame({
        "op": g.size(),
        "r_lordo": g.r_lordo.mean(),
        "costo": g.costo.mean(),
        "r_netto": g.r_netto.mean(),
        "err": g.r_netto.std() / np.sqrt(g.size()),
        "p_obj": g.tipo.apply(lambda s: (s == 1).mean()),
        "p_stop": g.tipo.apply(lambda s: (s == -1).mean()),
        "p_scad": g.tipo.apply(lambda s: (s == 0).mean()),
        "stop_atr": g.stop_atr.median(),
        "min": g.minuti.median(),
    })
    return out.round(3)


def per_anno(tr: pd.DataFrame) -> pd.DataFrame:
    g = tr.groupby("anno")
    return pd.DataFrame({"op": g.size(), "r_netto": g.r_netto.mean().round(3)})


def diagnostica(d: dict) -> None:
    """POST-HOC (non pre-registrata): perche' la regola muore.

    Lo stop ancorato all'estremo dello scatto vale ~0,068 ATR mediani: lo
    spread da 0,30 $ costa allora 0,15-0,26 R. Qui allargo lo stop a distanze
    fisse in ATR, tenendo gli STESSI segnali, per vedere se il vantaggio
    lordo del contrastare sopravvive quando il costo scende sotto 0,10 R.
    """
    n, s = PRIMARIA["n"], PRIMARIA["s"]
    idx, verso, estremo, ampiezza = segnali(d, n, s)
    print("\n=== DIAGNOSTICA POST-HOC: stop allargato a distanza fissa in ATR ===")
    righe = []
    for k in (0.10, 0.20, 0.35):
        dist = k * d["atr"][idx]
        for rr in RR_LISTA:
            tr = simula(d, idx, verso, estremo, ampiezza, rr, stop_alt=dist)
            for per, r in riepiloga(tr).iterrows():
                righe.append(dict(stop_atr=k, RR=rr, per=per,
                                  op=r["op"], r_lordo=r["r_lordo"],
                                  costo=r["costo"], r_netto=r["r_netto"],
                                  err=r["err"], p_obj=r["p_obj"],
                                  p_stop=r["p_stop"], p_scad=r["p_scad"]))
    tab = pd.DataFrame(righe)
    tab.to_parquet(f"{FUORI}/diagnostica_stop.parquet")
    print(tab.set_index(["stop_atr", "RR", "per"]).round(3).to_string())


def main() -> None:
    os.makedirs(FUORI, exist_ok=True)
    m1 = load_m1(DATI)
    d = prepara(m1)
    del m1

    if "--diagnostica" in sys.argv:
        diagnostica(d)
        return

    righe = []
    dettagli = {}
    for n in N_LISTA:
        for s in S_LISTA:
            idx, verso, estremo, ampiezza = segnali(d, n, s)
            for rr in RR_LISTA:
                tr = simula(d, idx, verso, estremo, ampiezza, rr)
                dettagli[(n, s, rr)] = tr
                ris = riepiloga(tr)
                for per, r in ris.iterrows():
                    righe.append(dict(N=n, S=s, RR=rr, per=per, **r.to_dict()))
            print(f"  fatto N={n} S={s}", file=sys.stderr)

    tab = pd.DataFrame(righe)
    tab.to_parquet(f"{FUORI}/griglia.parquet")

    print("\n=== TUTTE LE 18 CONFIGURAZIONI (nessuna nascosta) ===")
    piv = tab.pivot_table(index=["N", "S", "RR"], columns="per",
                          values=["op", "r_lordo", "costo", "r_netto"])
    piv = piv.reorder_levels([1, 0], axis=1).sort_index(axis=1)
    print(piv.round(3).to_string())

    n, s, rr = PRIMARIA["n"], PRIMARIA["s"], PRIMARIA["rr"]
    tr = dettagli[(n, s, rr)]
    tr.to_parquet(f"{FUORI}/primaria.parquet")

    print(f"\n=== PRIMARIA N={n} S={s} RR=1:{rr} ===")
    print(riepiloga(tr).to_string())

    print("\n--- per anno (R netto) ---")
    pa = per_anno(tr)
    print(pa.T.to_string())
    pos = int((pa.r_netto > 0).sum())
    print(f"anni positivi: {pos}/{len(pa)}")

    print("\n--- per ora UTC (R netto), solo ore con >=200 op per periodo ---")
    tr2 = tr.assign(per=periodo(tr.anno.to_numpy()))
    po = tr2.pivot_table(index="ora", columns="per", values="r_netto", aggfunc="mean")
    no = tr2.pivot_table(index="ora", columns="per", values="r_netto", aggfunc="size")
    po = po.where(no >= 200)
    print(pd.concat([po.round(3), no.rename(columns=lambda c: "n_" + c[:4])],
                    axis=1).to_string())

    print("\n--- per ora locale New York (R netto) ---")
    pny = tr2.pivot_table(index="ora_ny", columns="per", values="r_netto", aggfunc="mean")
    nny = tr2.pivot_table(index="ora_ny", columns="per", values="r_netto", aggfunc="size")
    print(pd.concat([pny.where(nny >= 200).round(3),
                     nny.rename(columns=lambda c: "n_" + c[:4])], axis=1).to_string())

    print("\n--- mezz'ora del dato macro (08:30 ET) contro il resto ---")
    tr2 = tr2.assign(macro=np.where(tr2.mezzora_ny == 17, "08:30 ET", "resto"))
    gm = tr2.groupby(["per", "macro"])
    print(pd.DataFrame({"op": gm.size(), "r_lordo": gm.r_lordo.mean(),
                        "r_netto": gm.r_netto.mean()}).round(3).to_string())

    print("\n--- per fascia di ampiezza dello scatto (|X|/ATR) ---")
    fasce = pd.cut(tr2.ampiezza, [0.2, 0.3, 0.5, 1.0, 99],
                   labels=[".20-.30", ".30-.50", ".50-1.0", ">1.0"])
    gf = tr2.groupby(["per", fasce], observed=True)
    print(pd.DataFrame({"op": gf.size(), "r_lordo": gf.r_lordo.mean(),
                        "costo": gf.costo.mean(),
                        "r_netto": gf.r_netto.mean()}).round(3).to_string())

    # ---------------- placebo ----------------
    idx, verso, estremo, ampiezza = segnali(d, n, s)
    rng = np.random.default_rng(20260804)

    # A: livello finto -> distanza di stop presa a caso da un altro evento
    cusc = CUSCINETTO_ATR * d["atr"][idx]
    p_ing_ip = d["o"][idx + 1]
    dist_vera = np.where(verso == -1,
                         np.maximum(estremo + cusc - p_ing_ip, cusc),
                         np.maximum(p_ing_ip - (estremo - cusc), cusc))
    # mescolata DENTRO l'anno, per non spostare la scala dei dollari
    dist_finta = dist_vera.copy()
    anni_ev = d["anno"][idx]
    for a in np.unique(anni_ev):
        m = anni_ev == a
        dist_finta[m] = rng.permutation(dist_vera[m])
    tr_a = simula(d, idx, verso, estremo, ampiezza, rr, stop_alt=dist_finta)

    # B: evento finto -> stessa direzione e stessa distanza, ingresso spostato
    spost = rng.integers(60, 301, size=len(idx))
    tr_b = simula(d, idx, verso, estremo, ampiezza, rr,
                  stop_alt=dist_vera, spostamento=spost)

    print("\n=== PLACEBO (configurazione primaria) ===")
    conf = pd.concat([
        riepiloga(tr).assign(caso="vero"),
        riepiloga(tr_a).assign(caso="A livello finto"),
        riepiloga(tr_b).assign(caso="B evento finto"),
    ]).set_index("caso", append=True)
    print(conf[["op", "r_lordo", "costo", "r_netto", "err",
                "p_obj", "p_stop", "p_scad"]].to_string())

    tr_a.to_parquet(f"{FUORI}/placebo_a.parquet")
    tr_b.to_parquet(f"{FUORI}/placebo_b.parquet")

    # ---------------- controllo di assurdita' ----------------
    print("\n=== CONTROLLO DI ASSURDITA' ===")
    for rr_c in RR_LISTA:
        t = dettagli[(n, s, rr_c)]
        po_ = (t.tipo == 1).mean()
        ps_ = (t.tipo == -1).mean()
        stato = "OK" if po_ < ps_ else "ALLARME: obiettivo lontano colpito piu' dello stop"
        print(f"  RR 1:{rr_c}  p_obiettivo={po_:.3f}  p_stop={ps_:.3f}  "
              f"p_scadenza={(t.tipo == 0).mean():.3f}  -> {stato}")
    print(f"  operazioni al giorno (primaria): "
          f"{len(tr) / tr.ts.dt.normalize().nunique():.2f}")
    print(f"  dettaglio salvato in {FUORI}/")


if __name__ == "__main__":
    main()
