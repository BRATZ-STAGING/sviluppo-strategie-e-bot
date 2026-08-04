#!/usr/bin/env python3
"""Scalp su LIVELLI OGGETTIVI: rimbalzo contro rottura, misurato da zero.

Si riparte dal grafico pulito. Niente order block, niente reclaim del VWAP,
niente allineamento di struttura: sono gia' stati misurati in cinque studi e
non selezionano. Qui restano SOLO i livelli che non richiedono
interpretazione, quelli che chiunque disegna allo stesso modo e dove per
ipotesi si accumula la liquidita'.

FAMIGLIE DI LIVELLI (pre-registrate, nessuna aggiunta dopo aver guardato)
  PDHL  massimo e minimo della giornata PRECEDENTE
  SESS  massimo e minimo della SESSIONE precedente (l'ultima chiusa: asia
        0-7 per le ore 7-12, londra 7-12 per le ore 12-21)
  R10   numeri tondi multipli di 10 dollari
  R50   numeri tondi multipli di 50 dollari
  OPEN  apertura della giornata (00:00 UTC) e apertura della settimana
  H24   massimo e minimo delle ultime 24 ore mobili (1440 barre M1)

DUE IPOTESI OPPOSTE PER OGNI FAMIGLIA (il mercato ne premia al massimo una)
  RIMBALZO il prezzo tocca il livello e torna indietro: si entra CONTRO il
           verso di avvicinamento, all'apertura della barra successiva al
           tocco
  ROTTURA  il prezzo lo attraversa e continua: si entra A FAVORE del verso di
           avvicinamento, all'apertura della barra successiva alla prima che
           CHIUDE oltre il livello, se accade entro 30 minuti dal tocco

DEFINIZIONE DI TOCCO
  la barra M1 contiene il livello mentre la precedente non lo conteneva; il
  verso di avvicinamento e' il segno di (livello - chiusura precedente). Per
  le griglie di numeri tondi il livello toccato e' quello adiacente alla
  chiusura precedente, il piu' vicino se la barra ne attraversa due.
  Il contatore dei tocchi e' per SINGOLO livello dentro il giorno di mercato
  (altrimenti sulle griglie di numeri tondi il "primo tocco" sarebbe il primo
  numero tondo qualsiasi, non il primo tocco di QUEL numero): si separa
  sempre il PRIMO tocco di un livello dai suoi ritocchi. Il conteggio parte
  dall'attivazione del livello, quindi include le ore notturne in cui non si
  opera: un livello arrivato alle 07:00 gia' testato risulta "succ".

IL VINCOLO ARITMETICO CHE DECIDE TUTTO
  lo spread vero dell'oro misurato su 6,1 milioni di tick e' 0,33 $ fino al
  2024 e 0,63 $ dal 2025. Su uno stop di 3 $ il costo di andata e ritorno
  vale il 10-21% del rischio, su uno stop di 5 $ il 7-13%. Quindi il
  vantaggio LORDO deve superare 0,10-0,20 R/op: sotto quella soglia lo scalp
  NON esiste, per quanto sia alta la percentuale di vincita. Lordo e netto
  sono sempre riportati separati, con il costo in %R.

COSTI (dollari di spread per anno, sottratti come spread/stop in R)
  2020 0,350  2021 0,349  2022 0,395  2023 0,334  2024 0,384
  2025 0,632  2026 0,631

PROTOCOLLO
  periodo 2020-2026, ricerca 2020-2022 e verifica 2023-2026 sempre entrambe
  riportate; gestione a 4 celle (stop 3 e 5 dollari, obiettivo 1:1,5 e 1:2),
  tabella principale sulla cella di riferimento stop 3 / 1:1,5; uscita per
  tempo dopo 240 minuti o alle 21:00 UTC; a parita' di minuto lo STOP
  prevale sull'obiettivo; massimo 5 operazioni al giorno per famiglia e
  ipotesi, almeno 15 minuti fra una e l'altra, ingressi solo fra le 7 e le
  21 UTC.

NIENTE LOOKAHEAD
  il giorno di mercato e' delimitato dalle 21:00 UTC (lo spezzone domenicale
  finisce dentro il lunedi', altrimenti il massimo del giorno precedente
  sarebbe quello di un troncone di tre ore); i livelli del giorno precedente
  sono noti solo dopo la sua chiusura; quelli di sessione solo dopo la
  chiusura della sessione; il massimo mobile delle 24 ore e' calcolato con
  shift(1) e non contiene la barra corrente; l'apertura di settimana e' la
  prima barra della settimana di mercato.

PLACEBO OBBLIGATORIO (seme fisso 20260804)
  per PDHL, SESS, OPEN, H24 il livello finto e' statico e vale, per ogni
  giorno, la chiusura di riferimento delle 07:00 piu' una distanza estratta
  senza reimmissione dalle distanze vere degli altri giorni: stesso numero di
  livelli, stessa distribuzione di distanza dal prezzo, nessuna roundness.
  Per R10 e R50 il finto e' la stessa griglia traslata di un offset casuale
  diverso ogni giorno: conserva esattamente numero e distribuzione delle
  distanze e distrugge solo il fatto che i livelli siano tondi.
  Nelle appendici BP, BU, BV, BY di questo progetto il placebo ha battuto
  TUTTE le ipotesi vere: se accade di nuovo va detto, ed e' il risultato.

CONTROLLO DI ASSURDITA'
  con obiettivo 1:1,5 lo stop e' piu' vicino dell'obiettivo, quindi deve
  essere colpito PIU' spesso. Se una riga mostrasse il contrario ci sarebbe
  un errore di simulazione, non un vantaggio: il controllo e' stampato.

IPOTESI PRE-REGISTRATA: nessuna famiglia produce un lordo superiore a
0,15 R/op stabile nei due periodi. Si scarta tutto cio' che non lo supera.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/workspace/sviluppo-strategie-e-bot/trading")
from framework.data import load_m1  # noqa: E402

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

DATI = "/workspace/sviluppo-strategie-e-bot/data/XAUUSD_M1"
OUT = "/workspace/sviluppo-strategie-e-bot/docs/studies/dati/scalp_livelli.parquet"

SPREAD = {2020: 0.350, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}
ANNI_RIC = {2020, 2021, 2022}
CELLE = [(3.0, 1.5), (3.0, 2.0), (5.0, 1.5), (5.0, 2.0)]
CELLA_RIF = "s3.0_rr1.5"
MAXBAR = 240          # minuti di durata massima
CONFERMA = 30         # minuti entro cui la rottura deve chiudere oltre
GAP_MIN = 15          # minuti minimi fra due ingressi
MAX_GIORNO = 5        # operazioni al giorno per famiglia e ipotesi
SEME = 20260804


# --------------------------------------------------------------- rilevazione

def _prec(a):
    out = np.empty_like(a)
    out[0] = np.nan
    out[1:] = a[:-1]
    return out


def eventi_serie(L, valido, hi, lo, cl):
    """Tocchi di una serie di livelli: (indice, livello, verso)."""
    ph, pl, pc = _prec(hi), _prec(lo), _prec(cl)
    dentro = (lo <= L) & (hi >= L)
    dentro_prec = (pl <= L) & (ph >= L)
    tocco = dentro & ~dentro_prec & valido & np.isfinite(pc) & np.isfinite(L)
    i = np.flatnonzero(tocco)
    verso = np.where(L[i] > pc[i], 1, -1).astype(np.int8)
    return i, L[i], verso


def eventi_griglia(step, off, hi, lo, cl):
    """Tocchi di una griglia di passo ``step`` traslata di ``off`` (per barra)."""
    ph, pl, pc = _prec(hi), _prec(lo), _prec(cl)
    k = np.floor((pc - off) / step)
    lup = off + (k + 1) * step
    ldn = off + k * step
    tup = (hi >= lup) & (ph < lup) & np.isfinite(pc)
    tdn = (lo <= ldn) & (pl > ldn) & np.isfinite(pc)
    piu_vicino_up = (lup - pc) <= (pc - ldn)
    su = tup & (~tdn | piu_vicino_up)
    giu = tdn & ~su
    i_su, i_giu = np.flatnonzero(su), np.flatnonzero(giu)
    i = np.concatenate([i_su, i_giu])
    lv = np.concatenate([lup[i_su], ldn[i_giu]])
    vs = np.concatenate([np.ones(len(i_su), np.int8), -np.ones(len(i_giu), np.int8)])
    o = np.argsort(i, kind="stable")
    return i[o], lv[o], vs[o]


# ------------------------------------------------------------------ ingressi

def ingressi(idx_t, liv, verso, ipotesi, cl, opn, ora, n):
    """Da tocco a ingresso: indice della barra di ingresso e direzione."""
    if ipotesi == "rimbalzo":
        e = idx_t + 1
        d = (-verso).astype(np.int8)
        ok = e < n
        return e[ok], d[ok], ok
    fuori_e, fuori_d, ok = [], [], np.zeros(len(idx_t), bool)
    for a in range(len(idx_t)):
        t, L, v = int(idx_t[a]), liv[a], int(verso[a])
        b = min(t + CONFERMA, n - 1)
        seg = cl[t:b + 1]
        oltre = seg > L if v == 1 else seg < L
        if not oltre.any():
            continue
        u = t + int(np.argmax(oltre))
        if u + 1 >= n:
            continue
        fuori_e.append(u + 1)
        fuori_d.append(v)
        ok[a] = True
    return (np.array(fuori_e, np.int64), np.array(fuori_d, np.int8), ok)


def filtra(e, d, extra, ora, giorno):
    """Ore 7-21, almeno GAP_MIN minuti di distanza, MAX_GIORNO al giorno."""
    o = np.argsort(e, kind="stable")
    e, d = e[o], d[o]
    extra = {k: v[o] for k, v in extra.items()}
    m = (ora[e] >= 7) & (ora[e] < 21)
    e, d = e[m], d[m]
    extra = {k: v[m] for k, v in extra.items()}
    tieni = np.zeros(len(e), bool)
    ultimo, corrente, quanti = -10 ** 9, None, 0
    for a in range(len(e)):
        g = giorno[e[a]]
        if g != corrente:
            corrente, quanti, ultimo = g, 0, -10 ** 9
        if quanti >= MAX_GIORNO or e[a] - ultimo < GAP_MIN:
            continue
        tieni[a] = True
        quanti += 1
        ultimo = e[a]
    return e[tieni], d[tieni], {k: v[tieni] for k, v in extra.items()}


# --------------------------------------------------------------- simulazione

def simula(e, d, hi, lo, cl, opn, fine, n):
    m, k = len(e), len(CELLE)
    R = np.zeros((m, k))
    esito = np.zeros((m, k), np.int8)
    for a in range(m):
        i, dd = int(e[a]), int(d[a])
        j = min(i + MAXBAR, int(fine[i]), n - 1)
        if j < i:
            continue
        p = opn[i]
        H, Lo = hi[i:j + 1], lo[i:j + 1]
        for b, (st, rr) in enumerate(CELLE):
            sp, tp = p - dd * st, p + dd * st * rr
            if dd == 1:
                a_st, a_tp = Lo <= sp, H >= tp
            else:
                a_st, a_tp = H >= sp, Lo <= tp
            i_st = int(np.argmax(a_st)) if a_st.any() else 10 ** 9
            i_tp = int(np.argmax(a_tp)) if a_tp.any() else 10 ** 9
            if i_st == 10 ** 9 and i_tp == 10 ** 9:
                R[a, b] = (cl[j] - p) * dd / st
            elif i_st <= i_tp:
                R[a, b], esito[a, b] = -1.0, -1
            else:
                R[a, b], esito[a, b] = rr, 1
    return R, esito


# ------------------------------------------------------------------ livelli

def costruisci(m1):
    idx = m1.index
    hi, lo, cl, opn = (m1.high.values, m1.low.values,
                       m1.close.values, m1.open.values)
    n = len(idx)
    ora = idx.hour.values
    data = idx.normalize()
    md = (idx + pd.Timedelta(hours=3)).normalize()          # giorno di mercato
    md_code = pd.factorize(md)[0]

    fam = {}

    # PDHL: massimo/minimo del giorno di mercato precedente
    g = pd.DataFrame({"h": hi, "l": lo}).groupby(md_code).agg(["max", "min"])
    pdh = g[("h", "max")].shift(1).reindex(md_code).values
    pdl = g[("l", "min")].shift(1).reindex(md_code).values
    fam["PDHL"] = [(pdh, np.isfinite(pdh)), (pdl, np.isfinite(pdl))]

    # SESS: ultima sessione chiusa (asia per le 7-12, londra per le 12-21)
    dcode = pd.factorize(data)[0]
    asia = (ora < 7)
    lon = (ora >= 7) & (ora < 12)
    def estremi(mask):
        s = pd.DataFrame({"h": np.where(mask, hi, np.nan),
                          "l": np.where(mask, lo, np.nan)}).groupby(dcode)
        return s.h.max().reindex(dcode).values, s.l.min().reindex(dcode).values
    ah, al = estremi(asia)
    lh, ll = estremi(lon)
    sh = np.where((ora >= 7) & (ora < 12), ah, np.where((ora >= 12) & (ora < 21), lh, np.nan))
    sl = np.where((ora >= 7) & (ora < 12), al, np.where((ora >= 12) & (ora < 21), ll, np.nan))
    fam["SESS"] = [(sh, np.isfinite(sh)), (sl, np.isfinite(sl))]

    # OPEN: apertura del giorno (00:00 UTC) e della settimana di mercato
    apg = pd.Series(opn).groupby(dcode).first().reindex(dcode).values
    wk = pd.factorize(md.tz_localize(None).to_period("W"))[0]
    aps = pd.Series(opn).groupby(wk).first().reindex(wk).values
    fam["OPEN"] = [(apg, np.isfinite(apg)), (aps, np.isfinite(aps))]

    # H24: massimo/minimo delle ultime 1440 barre, esclusa la corrente
    h24 = pd.Series(hi).rolling(1440).max().shift(1).values
    l24 = pd.Series(lo).rolling(1440).min().shift(1).values
    fam["H24"] = [(h24, np.isfinite(h24)), (l24, np.isfinite(l24))]

    return dict(idx=idx, hi=hi, lo=lo, cl=cl, opn=opn, n=n, ora=ora,
                md_code=md_code, dcode=dcode, fam=fam)


def placebo_statico(L, valido, ctx, rng):
    """Livello finto statico: chiusura di riferimento + distanza permutata."""
    ora, dcode, cl, n = ctx["ora"], ctx["dcode"], ctx["cl"], ctx["n"]
    m = valido & (ora >= 7) & (ora < 21) & np.isfinite(L)
    if not m.any():
        return np.full(n, np.nan), np.zeros(n, bool)
    df = pd.DataFrame({"g": dcode[m], "d": (L - cl)[m], "c": cl[m]})
    primo = df.groupby("g").first()
    dist = primo["d"].values.copy()
    rng.shuffle(dist)
    mapp = pd.Series(primo["c"].values + dist, index=primo.index)
    fin = mapp.reindex(dcode).values
    val = np.isfinite(fin) & valido
    return fin, val


def main():
    os.environ.setdefault("XAU_ANNI", "2020-2026")
    m1 = load_m1(DATI)
    ctx = costruisci(m1)
    idx, hi, lo, cl, opn, n = (ctx["idx"], ctx["hi"], ctx["lo"], ctx["cl"],
                               ctx["opn"], ctx["n"])
    ora, md_code = ctx["ora"], ctx["md_code"]
    cutoff = (idx.normalize() + pd.Timedelta(hours=21)).values
    fine = np.searchsorted(idx.values, cutoff, side="left") - 1
    anno = idx.year.values
    rng = np.random.default_rng(SEME)

    # sorgenti di tocchi: (famiglia, vero/placebo) -> (indici, livelli, versi)
    sorgenti = {}
    for nome, serie in ctx["fam"].items():
        for etichetta, prendi in (("vero", False), ("placebo", True)):
            ii, ll, vv = [], [], []
            for L, val in serie:
                if prendi:
                    L, val = placebo_statico(L, val, ctx, rng)
                a, b, c = eventi_serie(L, val, hi, lo, cl)
                ii.append(a); ll.append(b); vv.append(c)
            i = np.concatenate(ii); l_ = np.concatenate(ll); v = np.concatenate(vv)
            o = np.argsort(i, kind="stable")
            sorgenti[(nome, etichetta)] = (i[o], l_[o], v[o])

    for nome, step in (("R10", 10.0), ("R50", 50.0)):
        z = np.zeros(n)
        sorgenti[(nome, "vero")] = eventi_griglia(step, z, hi, lo, cl)
        ng = ctx["dcode"].max() + 1
        off_g = rng.uniform(0.0, step, ng)
        sorgenti[(nome, "placebo")] = eventi_griglia(step, off_g[ctx["dcode"]],
                                                     hi, lo, cl)

    righe = []
    for (nome, etichetta), (it, lv, vs) in sorgenti.items():
        # tocchi dello STESSO livello entro il giorno di mercato (pre-filtri)
        tocco_n = (pd.Series(np.ones(len(it)), dtype=int)
                   .groupby([md_code[it], np.round(lv, 2)]).cumcount().values + 1)
        for ipo in ("rimbalzo", "rottura"):
            e, d, ok = ingressi(it, lv, vs, ipo, cl, opn, ora, n)
            tn = tocco_n[ok]
            e, d, extra = filtra(e, d, {"tocco_n": tn}, ora, md_code)
            if len(e) == 0:
                continue
            R, esito = simula(e, d, hi, lo, cl, opn, fine, n)
            r = pd.DataFrame({"famiglia": nome, "tipo": etichetta,
                              "ipotesi": ipo, "ts": idx[e], "dir": d,
                              "anno": anno[e], "tocco_n": extra["tocco_n"]})
            for b, (st, rr) in enumerate(CELLE):
                key = f"s{st}_rr{rr}"
                r[f"lordo_{key}"] = R[:, b]
                r[f"netto_{key}"] = R[:, b] - r.anno.map(SPREAD).values / st
                r[f"esito_{key}"] = esito[:, b]
            righe.append(r)

    T = pd.concat(righe, ignore_index=True)
    T["periodo"] = np.where(T.anno.isin(ANNI_RIC), "ric", "ver")
    T["primo"] = np.where(T.tocco_n == 1, "1o", "succ")
    T.to_parquet(OUT, index=False)

    lo_c, ne_c, es_c = f"lordo_{CELLA_RIF}", f"netto_{CELLA_RIF}", f"esito_{CELLA_RIF}"
    print(f"\nM1 {idx[0]:%Y-%m-%d} -> {idx[-1]:%Y-%m-%d}  operazioni totali "
          f"{len(T):,}  cella di riferimento {CELLA_RIF}\n")

    # --- A) famiglia x ipotesi, vero contro placebo -------------------------
    def piv(sub, col):
        return sub.groupby(["famiglia", "ipotesi", "periodo"])[col].agg(["size", "mean"])
    V = piv(T[T.tipo == "vero"], lo_c)
    Vn = piv(T[T.tipo == "vero"], ne_c)["mean"]
    P = piv(T[T.tipo == "placebo"], lo_c)
    A = pd.DataFrame({
        "n_ric": V.xs("ric", level=2)["size"], "lordo_ric": V.xs("ric", level=2)["mean"],
        "n_ver": V.xs("ver", level=2)["size"], "lordo_ver": V.xs("ver", level=2)["mean"],
        "netto_ver": Vn.xs("ver", level=2),
        "plc_ric": P.xs("ric", level=2)["mean"], "plc_ver": P.xs("ver", level=2)["mean"],
    })
    print("A) LORDO R/op per famiglia e ipotesi (vero) contro placebo")
    print(A.round(3).to_string())

    # --- B) effetto delle celle di gestione --------------------------------
    fila = []
    for st, rr in CELLE:
        k = f"s{st}_rr{rr}"
        v = T[T.tipo == "vero"]
        costo = np.mean([SPREAD[a] for a in v.anno]) / st
        fila.append({"cella": k, "costo_%R": 100 * costo,
                     "%stop": 100 * (v[f"esito_{k}"] == -1).mean(),
                     "%obiettivo": 100 * (v[f"esito_{k}"] == 1).mean(),
                     "%tempo": 100 * (v[f"esito_{k}"] == 0).mean(),
                     "lordo": v[f"lordo_{k}"].mean(), "netto": v[f"netto_{k}"].mean()})
    B = pd.DataFrame(fila).set_index("cella")
    print("\nB) celle di gestione (tutte le famiglie vere insieme)")
    print(B.round(3).to_string())
    print("   controllo di assurdita' (stop vicino colpito piu' dell'obiettivo): "
          + ", ".join(f"{r.Index}={'OK' if r._2 > r._3 else 'ANOMALO'}"
                      for r in B.itertuples()))

    # --- C) primo tocco contro successivi ----------------------------------
    C = (T[T.tipo == "vero"].pivot_table(index=["famiglia", "ipotesi"],
                                         columns="primo", values=lo_c,
                                         aggfunc=["size", "mean"]))
    C.columns = [f"{a}_{b}" for a, b in C.columns]
    print("\nC) lordo R/op primo tocco del giorno contro successivi (2020-2026)")
    print(C.round(3).to_string())

    # --- D) tenuta anno per anno delle due righe migliori -------------------
    top = A.lordo_ver.sort_values(ascending=False).head(2).index
    v = T[T.tipo == "vero"].set_index(["famiglia", "ipotesi"]).loc[list(top)]
    D = v.pivot_table(index=["famiglia", "ipotesi"], columns="anno",
                      values=[lo_c, ne_c], aggfunc="mean")
    print("\nD) lordo (sopra) e netto (sotto) anno per anno delle due righe migliori")
    print(D.round(3).to_string())

    # --- verdetto -----------------------------------------------------------
    sog = A[(A.lordo_ric > 0.15) & (A.lordo_ver > 0.15)]
    print(f"\nVERDETTO lordo > 0,15 R/op in ENTRAMBI i periodi: "
          f"{'SI -> ' + str(list(sog.index)) if len(sog) else 'NO, nessuna famiglia'}")
    mig = A.lordo_ver.idxmax()
    print(f"  migliore in verifica: {mig} lordo {A.lordo_ver.max():.3f} "
          f"netto {A.loc[mig, 'netto_ver']:.3f}")
    batte = A[(A.plc_ric > A.lordo_ric) & (A.plc_ver > A.lordo_ver)]
    print(f"  placebo meglio del vero in entrambi i periodi: {len(batte)}/{len(A)} righe")
    print(f"  media lordo vero {A[['lordo_ric', 'lordo_ver']].values.mean():.3f} "
          f"contro placebo {A[['plc_ric', 'plc_ver']].values.mean():.3f}")
    print(f"\ndettaglio in {OUT}")


if __name__ == "__main__":
    main()
