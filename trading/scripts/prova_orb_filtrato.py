"""Opening range breakout con FILTRI DI CONTESTO (XAUUSD, 2009-2026).

La rottura NUDA del range di apertura e' gia' stata misurata su questi dati e
respinta: e' indistinguibile da un cammino casuale e non batte una banda
spostata a caso. Qui NON si rifa' quella misura e NON si cerca la cella
migliore di una griglia: si mette alla prova UNA ipotesi, cioe' che il
vantaggio stia nel CONTESTO in cui la rottura avviene.

Ipotesi pre-registrata in /workspace/dati_grezzi/orb_filtrato_IPOTESI.txt
(scritta prima di eseguire questo script).

Cinque filtri, uno per volta, dichiarati prima:
  F1 ampiezza dell'apertura rispetto all'ATR (stretta contro larga)  <- l'ipotesi
  F2 direzione della notte precedente (rottura concorde contro discorde)
  F3 giorno della settimana (CONTROLLO: deve fallire la verifica)
  F4 regime di volatilita' (terzile causale dell'ATR)
  F5 concordanza con la sessione precedente

Metodo: il RAMO del filtro si sceglie sul 2009-2019, il numero che conta e'
quello del 2020-2026. Per sapere quanti filtri sopravviverebbero PER CASO si
ripete la stessa procedura con maschere casuali della stessa selettivita'.

Convenzioni rispettate (ognuna e' una regola del progetto):
  - finestre sull'OROLOGIO LOCALE, non UTC: 08:00-08:30 Europe/London e
    09:30-10:00 America/New_York. L'orologio del mercato e' locale.
  - ingresso: ordine stop appoggiato al bordo del range (fill al bordo, o
    all'apertura del minuto se ha gia' scavalcato). Variante severa
    (decisione a candela M1 chiusa, ingresso alla chiusura) come controllo.
  - stop sul bordo opposto; nello stesso minuto lo STOP prevale sull'obiettivo.
  - uscita a mercato alle 16:00 ora di New York: sempre un'ora prima della
    pausa giornaliera, quindi nessuno swap e nessun rollover attraversato.
  - costo: spread 0,30 $ andata+ritorno, cioe' 0,30/rischio espresso in R.
  - tutto in R; 2009-2019 (ricerca) e 2020-2026 (verifica) sempre separati.
  - ATR causale (framework.volatility.daily_atr, gia' shiftato di un giorno);
    tutte le soglie di contesto sono causali (mediane e quantili espansivi o
    a finestra mobile sui soli giorni precedenti).

Uso:
    python3 trading/scripts/prova_orb_filtrato.py
Il dettaglio per operazione finisce in /workspace/dati_grezzi/orb_filtrato/.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/workspace/sviluppo-strategie-e-bot/trading")

from framework.data import load_m1            # noqa: E402
from framework.volatility import daily_atr    # noqa: E402

DATI = "/workspace/sviluppo-strategie-e-bot/data/XAUUSD_M1"
GREZZI = "/workspace/dati_grezzi/orb_filtrato"
SPREAD = 0.30                 # dollari, andata e ritorno
BERSAGLI = (1.5, 2.0)         # obiettivi in R richiesti dalla campagna
USCITA_ET = 16 * 60           # 16:00 ora di New York: chiusura obbligata
MIN_BARRE_OR = 20             # candele minime nella finestra di apertura (su 30)
MIN_BARRE_DOPO = 60           # minuti minimi disponibili dopo l'apertura
FIN_ANNO_VECCHIO = 2019
PERIODI = ("2009-2019", "2020-2026")
N_FINTI = 200                 # maschere casuali per la conta "quanti per caso"

# Finestre di apertura, definite sull'orologio LOCALE del mercato.
#   a, b  = minuti dalla mezzanotte LOCALE (inizio e fine della finestra)
#   prec  = inizio della "sessione precedente", in minuti dalla mezzanotte di
#           New York (negativo = giorno prima). -360 e' la riapertura serale
#           delle 18:00 ET, 180 e' l'apertura di Londra (03:00 ET).
FINESTRE = {
    "londra_08:00": dict(tz="Europe/London", a=8 * 60, b=8 * 60 + 30, prec=-360),
    "ny_09:30": dict(tz="America/New_York", a=9 * 60 + 30, b=10 * 60, prec=180),
}

GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
INF = 1 << 30


# --------------------------------------------------------------------------
# costruzione delle operazioni
# --------------------------------------------------------------------------
def _ns(di: pd.DatetimeIndex) -> np.ndarray:
    """Interi in NANOSECONDI da un DatetimeIndex, qualunque sia la sua unita'.

    ``asi8`` restituisce l'unita' interna dell'oggetto (ms per l'archivio,
    us per i riferimenti costruiti a mano): confrontarli direttamente fa
    cadere ogni ricerca fuori dall'array. E' costato una prima misura
    sbagliata, con l'uscita di fatto a mezzanotte locale invece che alle
    16:00 di New York.
    """
    return di.as_unit("ns").asi8


def _posizioni(ns: np.ndarray, naive: pd.DatetimeIndex, tz: str) -> np.ndarray:
    """Indice della prima candela con timestamp >= all'orario locale richiesto.

    ``naive`` sono orari di parete (senza fuso) nel fuso ``tz``: localizzarli
    dopo l'aritmetica e' l'unico modo di non sbagliare di un'ora nei giorni di
    cambio dell'ora legale.
    """
    bersaglio = naive.tz_localize(tz, ambiguous=True, nonexistent="shift_forward")
    return np.searchsorted(ns, _ns(bersaglio), side="left")


def costruisci(m1: pd.DataFrame, spec: dict, placebo: bool = False,
               ingresso: str = "livello", seed: int = 20260804) -> pd.DataFrame:
    """Una operazione per giornata: prima rottura del range di apertura.

    Con ``placebo=True`` la banda ha la stessa larghezza ma e' spostata a caso
    di 0,25-1,2 larghezze (mantenendo il prezzo dentro): se il risultato non
    peggiora, non e' il bordo del range a lavorare ma solo la sua distanza.
    """
    idx = m1.index
    ns = _ns(idx)
    hi, lo, opn, cl = (m1.high.values, m1.low.values,
                       m1.open.values, m1.close.values)

    loc = idx.tz_convert(spec["tz"])
    min_loc = (loc.hour * 60 + loc.minute).values.astype(np.int32)
    chiave = loc.normalize().tz_localize(None).values      # data locale
    cambi = np.flatnonzero(np.r_[True, chiave[1:] != chiave[:-1]])
    inizi, fini = cambi, np.r_[cambi[1:], len(chiave)]

    a, b = spec["a"], spec["b"]
    n = len(cambi)
    i0 = np.empty(n, np.int64)
    i1 = np.empty(n, np.int64)
    for k in range(n):
        s, e = inizi[k], fini[k]
        ml = min_loc[s:e]                    # crescente dentro la data locale
        i0[k] = s + np.searchsorted(ml, a)
        i1[k] = s + np.searchsorted(ml, b)

    # giornate utilizzabili: finestra piena e almeno un'ora di mercato dopo
    ok = (i1 - i0 >= MIN_BARRE_OR) & (i1 < fini) & (i0 < fini)
    ok &= np.where(ok, min_loc[np.clip(i0, 0, len(min_loc) - 1)] < a + 10, False)

    # orari di riferimento in ora di NEW YORK, per ogni giornata utilizzabile
    et_naive = idx.tz_convert("America/New_York").tz_localize(None)
    mezza = pd.DatetimeIndex(et_naive[np.clip(i1, 0, len(et_naive) - 1)]).normalize()
    p_uscita = _posizioni(ns, mezza + pd.Timedelta(minutes=USCITA_ET),
                          "America/New_York")
    p_riap = _posizioni(ns, mezza - pd.Timedelta(hours=6), "America/New_York")
    p_mezza = _posizioni(ns, mezza, "America/New_York")
    p_prec = _posizioni(ns, mezza + pd.Timedelta(minutes=spec["prec"]),
                        "America/New_York")

    i2 = np.minimum(p_uscita, fini)
    ok &= (i2 - i1 >= MIN_BARRE_DOPO)

    rng = np.random.default_rng(seed)
    tol = 90 * 60 * 10 ** 9        # 90 minuti in ns: tolleranza sui riferimenti
    righe = []
    for k in range(n):
        if not ok[k]:
            continue
        ia, ib, ic = int(i0[k]), int(i1[k]), int(i2[k])
        or_hi, or_lo = hi[ia:ib].max(), lo[ia:ib].min()
        larghezza = or_hi - or_lo
        if larghezza <= 0:
            continue
        if placebo:
            rif = cl[ib - 1]
            for _ in range(40):
                u = rng.uniform(-1.2, 1.2)
                if abs(u) < 0.25:
                    continue
                c_hi, c_lo = or_hi + u * larghezza, or_lo + u * larghezza
                if c_lo < rif < c_hi:
                    or_hi, or_lo = c_hi, c_lo
                    break
            else:
                continue

        H, L, O, C = hi[ib:ic], lo[ib:ic], opn[ib:ic], cl[ib:ic]
        su = np.flatnonzero(H >= or_hi)
        giu = np.flatnonzero(L <= or_lo)
        j_su = int(su[0]) if su.size else INF
        j_giu = int(giu[0]) if giu.size else INF

        # contesto: tutto calcolato con candele PRECEDENTI all'ingresso
        pr_riap = cl[int(p_riap[k])] if 0 < p_riap[k] < len(cl) else np.nan
        pr_mez = cl[int(p_mezza[k])] if 0 < p_mezza[k] < len(cl) else np.nan
        pr_prec = cl[int(p_prec[k])] if 0 < p_prec[k] < len(cl) else np.nan
        # scarto i riferimenti troppo lontani dall'orario richiesto (festivi)
        if 0 < p_riap[k] < len(ns):
            att = (mezza[k] - pd.Timedelta(hours=6)).tz_localize(
                "America/New_York", ambiguous=True, nonexistent="shift_forward")
            if abs(ns[int(p_riap[k])] - att.as_unit("ns").value) > tol:
                pr_riap = np.nan

        giorno_et = mezza[k]
        base = {
            "giorno": giorno_et, "anno": giorno_et.year,
            "dow": giorno_et.dayofweek,
            "larghezza": larghezza,
            "notte": (pr_mez - pr_riap) if np.isfinite(pr_mez + pr_riap) else np.nan,
            "sess_prec": (cl[ib - 1] - pr_prec) if np.isfinite(pr_prec) else np.nan,
        }
        if j_su == INF and j_giu == INF:
            righe.append({**base, "esito": "nessuna_rottura"})
            continue
        if j_su == j_giu:      # stesso minuto sui due bordi: ordine ignoto
            righe.append({**base, "esito": "ambiguo"})
            continue

        severo = ingresso == "chiusura"
        if j_su < j_giu:
            lato, j = 1, j_su
            entry = C[j] if severo else max(or_hi, O[j])
            stop = or_lo
        else:
            lato, j = -1, j_giu
            entry = C[j] if severo else min(or_lo, O[j])
            stop = or_hi
        rischio = (entry - stop) if lato > 0 else (stop - entry)
        if severo:
            j += 1
            if j >= len(H):
                continue
        if rischio <= 0:
            continue

        colpo = (np.flatnonzero(L[j:] <= stop) if lato > 0
                 else np.flatnonzero(H[j:] >= stop))
        if colpo.size:
            t = j + int(colpo[0])
            # regola: nel minuto t vince lo stop, quel massimo non conta
            if t > j:
                estremo = H[j:t].max() if lato > 0 else L[j:t].min()
                mfe = (estremo - entry) if lato > 0 else (entry - estremo)
            else:
                mfe = 0.0
            stoppato, uscita = True, stop
        else:
            estremo = H[j:].max() if lato > 0 else L[j:].min()
            mfe = (estremo - entry) if lato > 0 else (entry - estremo)
            stoppato, uscita = False, C[-1]
        r_scad = ((uscita - entry) if lato > 0 else (entry - uscita)) / rischio
        righe.append({**base, "esito": "rottura", "lato": lato,
                      "rischio": rischio, "mfe_R": max(mfe, 0.0) / rischio,
                      "stoppato": stoppato, "r_scadenza": r_scad,
                      "spread_R": SPREAD / rischio})

    df = pd.DataFrame(righe)
    df["stoppato"] = df.get("stoppato", pd.Series(dtype=object)).fillna(False).astype(bool)
    df["periodo"] = np.where(df.anno <= FIN_ANNO_VECCHIO, PERIODI[0], PERIODI[1])
    return df


def aggiungi_contesto(df: pd.DataFrame, atr: pd.Series) -> pd.DataFrame:
    """Colonne di contesto, tutte causali (solo giornate precedenti)."""
    df = df.sort_values("giorno").reset_index(drop=True)
    g = pd.DatetimeIndex(df.giorno).normalize()
    a = atr.copy()
    a.index = a.index.tz_localize(None) if a.index.tz is not None else a.index
    df["atr"] = a.reindex(g).ffill().values
    df["larg_atr"] = df.larghezza / df.atr
    # soglia CAUSALE: mediana delle 250 giornate precedenti (mai la corrente)
    df["soglia_larg"] = df.larg_atr.rolling(250, min_periods=100).median().shift(1)
    # terzili CAUSALI dell'ATR (finestra espansiva sui soli giorni passati)
    df["q33"] = df.atr.expanding(250).quantile(1 / 3).shift(1)
    df["q66"] = df.atr.expanding(250).quantile(2 / 3).shift(1)
    return df


# --------------------------------------------------------------------------
# valutazione
# --------------------------------------------------------------------------
def netto_di(r: pd.DataFrame, bersaglio: float):
    """R lordo e netto per operazione, con la scomposizione degli esiti."""
    vinta = r.mfe_R.values >= bersaglio
    stoppato = r.stoppato.values.astype(bool)
    persa = (~vinta) & stoppato
    scad = (~vinta) & (~stoppato)
    lordo = np.where(vinta, bersaglio, np.where(persa, -1.0, r.r_scadenza.values))
    return lordo, lordo - r.spread_R.values, vinta, persa, scad


def sintesi(r: pd.DataFrame, bersaglio: float) -> dict:
    if len(r) == 0:
        return {"op": 0, "obiettivo_%": np.nan, "stop_%": np.nan,
                "scadenza_%": np.nan, "spread_R": np.nan, "R_lordo": np.nan,
                "R_netto": np.nan, "es": np.nan}
    lordo, netto, vinta, persa, scad = netto_di(r, bersaglio)
    return {"op": len(r), "obiettivo_%": 100 * vinta.mean(),
            "stop_%": 100 * persa.mean(), "scadenza_%": 100 * scad.mean(),
            "spread_R": float(np.median(r.spread_R.values)),
            "R_lordo": lordo.mean(), "R_netto": netto.mean(),
            "es": netto.std(ddof=1) / np.sqrt(len(netto))}


def anni_positivi(r: pd.DataFrame, bersaglio: float) -> tuple[int, int]:
    if len(r) == 0:
        return 0, 0
    _, netto, _, _, _ = netto_di(r, bersaglio)
    s = pd.Series(netto, index=r.anno.values).groupby(level=0).mean()
    return int((s > 0).sum()), int(len(s))


# --------------------------------------------------------------------------
# filtri
# --------------------------------------------------------------------------
def maschere(r: pd.DataFrame) -> dict:
    """Ogni filtro e' una coppia di rami mutuamente esclusivi (nome -> maschera)."""
    lato = r.lato.values
    f = {}
    f["F1 ampiezza"] = {
        "stretta": (r.larg_atr < r.soglia_larg).values,
        "larga": (r.larg_atr >= r.soglia_larg).values,
    }
    seg_notte = np.sign(r.notte.values)
    f["F2 notte"] = {
        "concorde": (seg_notte == lato) & np.isfinite(r.notte.values),
        "discorde": (seg_notte == -lato) & np.isfinite(r.notte.values),
    }
    f["F4 regime ATR"] = {
        "alto": (r.atr > r.q66).values,
        "basso": (r.atr <= r.q33).values,
    }
    seg_prec = np.sign(r.sess_prec.values)
    f["F5 sess.prec"] = {
        "concorde": (seg_prec == lato) & np.isfinite(r.sess_prec.values),
        "discorde": (seg_prec == -lato) & np.isfinite(r.sess_prec.values),
    }
    return f


def scegli_e_verifica(r: pd.DataFrame, bersaglio: float) -> pd.DataFrame:
    """Sceglie il ramo sul 2009-2019, riporta il verdetto sul 2020-2026."""
    vecchio = r.periodo == PERIODI[0]
    righe = []
    for nome, rami in maschere(r).items():
        punteggi = {}
        for ramo, m in rami.items():
            s = sintesi(r[m & vecchio.values], bersaglio)
            punteggi[ramo] = (s["R_netto"] if s["op"] >= 150 else -9.0, s)
        ramo = max(punteggi, key=lambda k: punteggi[k][0])
        m = rami[ramo]
        sv = punteggi[ramo][1]
        sn = sintesi(r[m & (~vecchio).values], bersaglio)
        ap, at = anni_positivi(r[m], bersaglio)
        righe.append({"filtro": nome, "ramo": ramo,
                      "op_v": sv["op"], "R_v": sv["R_netto"],
                      "op_n": sn["op"], "R_n": sn["R_netto"],
                      "es_n": sn.get("es", np.nan),
                      "anni+": f"{ap}/{at}",
                      "sopravvive": bool(sv["R_netto"] > 0 and sn["R_netto"] > 0)})
    # F3 giorno della settimana: si scelgono i due giorni migliori sul 2009-2019
    per_g = {}
    for d in range(5):
        m = (r.dow == d).values
        per_g[d] = sintesi(r[m & vecchio.values], bersaglio)["R_netto"]
    top2 = sorted(per_g, key=lambda d: -per_g[d])[:2]
    m = r.dow.isin(top2).values
    sv = sintesi(r[m & vecchio.values], bersaglio)
    sn = sintesi(r[m & (~vecchio).values], bersaglio)
    ap, at = anni_positivi(r[m], bersaglio)
    righe.append({"filtro": "F3 giorno", "ramo": "+".join(GIORNI[d] for d in top2),
                  "op_v": sv["op"], "R_v": sv["R_netto"], "op_n": sn["op"],
                  "R_n": sn["R_netto"], "es_n": sn.get("es", np.nan),
                  "anni+": f"{ap}/{at}",
                  "sopravvive": bool(sv["R_netto"] > 0 and sn["R_netto"] > 0)})
    return pd.DataFrame(righe)


def filtri_finti(r: pd.DataFrame, bersaglio: float, quote: list[float],
                 seed: int = 7) -> pd.DataFrame:
    """Quanti filtri SOPRAVVIVEREBBERO PER CASO.

    Stessa procedura (scegli il ramo migliore sul 2009-2019, verifica sul
    2020-2026) applicata a maschere casuali della stessa selettivita'. E' il
    metro con cui leggere la colonna 'sopravvive' dei filtri veri.
    """
    rng = np.random.default_rng(seed)
    vecchio = (r.periodo == PERIODI[0]).values
    out = []
    for q in quote:
        conta = 0
        for _ in range(N_FINTI):
            u = rng.random(len(r))
            rami = {"A": u < q, "B": u >= q}
            best, sv = None, None
            for nome, m in rami.items():
                s = sintesi(r[m & vecchio], bersaglio)
                if s["op"] >= 150 and (sv is None or s["R_netto"] > sv):
                    best, sv = m, s["R_netto"]
            if best is None or sv is None or sv <= 0:
                continue
            sn = sintesi(r[best & (~vecchio)], bersaglio)
            conta += int(sn["R_netto"] > 0)
        out.append({"quota_ON": round(q, 2), "sopravvissuti_%": 100 * conta / N_FINTI})
    return pd.DataFrame(out)


def giorno_permutato(r: pd.DataFrame, bersaglio: float, quanti: int,
                     seed: int = 11) -> float:
    """F3 con le etichette del giorno MESCOLATE: quante volte sopravvive.

    Stessa procedura del filtro vero (scegli i ``quanti`` giorni migliori sul
    2009-2019, verifica sul 2020-2026) applicata a etichette permutate: e' la
    probabilita' che un "giorno della settimana" senza alcun contenuto passi
    comunque la verifica. E' il metro con cui leggere F3.
    """
    rng = np.random.default_rng(seed)
    vecchio = (r.periodo == PERIODI[0]).values
    _, netto, _, _, _ = netto_di(r, bersaglio)
    dow = r.dow.values
    conta = 0
    for _ in range(N_FINTI):
        finto = rng.permutation(dow)
        med = {d: netto[vecchio & (finto == d)].mean() for d in range(5)}
        top = sorted(med, key=lambda d: -med[d])[:quanti]
        m = np.isin(finto, top)
        if netto[vecchio & m].mean() > 0 and netto[(~vecchio) & m].mean() > 0:
            conta += 1
    return 100 * conta / N_FINTI


# --------------------------------------------------------------------------
def main() -> None:
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 40)
    os.makedirs(GREZZI, exist_ok=True)

    m1 = load_m1(DATI)
    atr = daily_atr(m1, 14)
    print(f"M1 caricate: {len(m1):,} da {m1.index[0]:%Y-%m-%d} a {m1.index[-1]:%Y-%m-%d}")

    tabelle = {}
    for nome, spec in FINESTRE.items():
        for etichetta, kw in (("vero", {}), ("placebo", {"placebo": True}),
                              ("severo", {"ingresso": "chiusura"})):
            df = aggiungi_contesto(costruisci(m1, spec, **kw), atr)
            df.to_parquet(f"{GREZZI}/orb_{nome.replace(':', '')}_{etichetta}.parquet")
            tabelle[(nome, etichetta)] = df

    # ---- 1. base: la rottura nuda, per confronto -------------------------
    print("\n=== 1. ORB NUDA (orologio locale), per periodo e obiettivo ===")
    righe = []
    for nome in FINESTRE:
        d = tabelle[(nome, "vero")]
        r = d[d.esito == "rottura"]
        for per in PERIODI:
            rp = r[r.periodo == per]
            g = d[d.periodo == per]
            if len(rp) == 0:
                continue
            for k in BERSAGLI:
                s = sintesi(rp, k)
                righe.append({"finestra": nome, "periodo": per, "obiettivo": k,
                              "gg": len(g),
                              "rotto_%": 100 * (g.esito == "rottura").mean(),
                              **{x: s[x] for x in ("op", "obiettivo_%", "stop_%",
                                                   "scadenza_%", "spread_R",
                                                   "R_lordo", "R_netto")}})
                # controllo di assurdita': un obiettivo piu' lontano non puo'
                # essere raggiunto piu' spesso di uno piu' vicino
                assert (rp.mfe_R >= k).mean() <= (rp.mfe_R >= k / 2).mean() + 1e-12
                assert s["obiettivo_%"] <= 100 - s["stop_%"] + 1e-9
    base = pd.DataFrame(righe)
    print(base.round(3).to_string(index=False))

    # ---- 2. filtri, scelti sul 2009-2019 e verificati sul 2020-2026 -----
    print("\n=== 2. FILTRI (ramo scelto sul 2009-2019, verifica sul 2020-2026) ===")
    tutti = []
    for nome in FINESTRE:
        d = tabelle[(nome, "vero")]
        r = d[d.esito == "rottura"].reset_index(drop=True)
        for k in BERSAGLI:
            t = scegli_e_verifica(r, k)
            t.insert(0, "obiettivo", k)
            t.insert(0, "finestra", nome)
            tutti.append(t)
    filt = pd.concat(tutti, ignore_index=True)
    print(filt.round(3).to_string(index=False))
    n_sopr = int(filt.sopravvive.sum())
    print(f"\nsopravvissuti: {n_sopr} su {len(filt)} combinazioni")

    # ---- 3. quanti ne sopravvivrebbero per caso -------------------------
    print("\n=== 3. FILTRI FINTI: quanti sopravvivono per puro caso ===")
    finti = []
    for nome in FINESTRE:
        d = tabelle[(nome, "vero")]
        r = d[d.esito == "rottura"].reset_index(drop=True)
        for k in BERSAGLI:
            t = filtri_finti(r, k, [0.33, 0.5])
            t.insert(0, "obiettivo", k)
            t.insert(0, "finestra", nome)
            finti.append(t)
    finti = pd.concat(finti, ignore_index=True)
    print(finti.round(1).to_string(index=False))
    # ---- 4. il filtro dell'ipotesi, in dettaglio ------------------------
    print("\n=== 4. F1 AMPIEZZA in dettaglio (l'ipotesi pre-registrata) ===")
    righe = []
    for nome in FINESTRE:
        for etichetta in ("vero", "placebo", "severo"):
            d = tabelle[(nome, etichetta)]
            r = d[d.esito == "rottura"]
            for ramo, m in (("stretta", r.larg_atr < r.soglia_larg),
                            ("larga", r.larg_atr >= r.soglia_larg)):
                for per in PERIODI:
                    rp = r[m.values & (r.periodo == per).values]
                    for k in BERSAGLI:
                        s = sintesi(rp, k)
                        righe.append({"finestra": nome, "banda": etichetta,
                                      "ramo": ramo, "periodo": per, "obiettivo": k,
                                      "op": s["op"], "obiettivo_%": s.get("obiettivo_%"),
                                      "stop_%": s.get("stop_%"),
                                      "scad_%": s.get("scadenza_%"),
                                      "R_lordo": s.get("R_lordo"),
                                      "R_netto": s["R_netto"],
                                      "es": s.get("es")})
    det = pd.DataFrame(righe)
    det.to_parquet(f"{GREZZI}/dettaglio_F1.parquet")
    print(det[det.banda == "vero"].round(3).to_string(index=False))
    print("\n--- placebo (banda della stessa larghezza, spostata a caso) ---")
    print(det[det.banda == "placebo"].round(3).to_string(index=False))
    print("\n--- ingresso severo (decisione a M1 chiusa) ---")
    print(det[det.banda == "severo"].round(3).to_string(index=False))

    # ---- 5. anno per anno del ramo dell'ipotesi -------------------------
    print("\n=== 5. R netto per anno, F1=stretta, obiettivo 1.5R ===")
    righe = []
    for nome in FINESTRE:
        d = tabelle[(nome, "vero")]
        r = d[(d.esito == "rottura") & (d.larg_atr < d.soglia_larg)]
        _, netto, _, _, _ = netto_di(r, 1.5)
        s = pd.Series(netto, index=r.anno.values).groupby(level=0).agg(["mean", "size"])
        righe.append(s["mean"].rename(nome))
    ann = pd.concat(righe, axis=1)
    print(ann.round(3).to_string())
    print("anni positivi:", {c: f"{int((ann[c] > 0).sum())}/{ann[c].notna().sum()}"
                             for c in ann.columns})

    # ---- 6. F3 giorno della settimana: l'unico sopravvissuto -------------
    print("\n=== 6. F3 GIORNO DELLA SETTIMANA (era il CONTROLLO) ===")
    righe = []
    for nome in FINESTRE:
        d = tabelle[(nome, "vero")]
        r = d[d.esito == "rottura"].reset_index(drop=True)
        for k in BERSAGLI:
            _, netto, _, _, _ = netto_di(r, k)
            vecchio = (r.periodo == PERIODI[0]).values
            for dd in range(5):
                m = (r.dow == dd).values
                x_v, x_n = netto[m & vecchio], netto[m & ~vecchio]
                righe.append({
                    "finestra": nome, "obiettivo": k, "giorno": GIORNI[dd],
                    "op_v": len(x_v), "R_v": x_v.mean(),
                    "op_n": len(x_n), "R_n": x_n.mean(),
                    "t_n": x_n.mean() / (x_n.std(ddof=1) / np.sqrt(len(x_n)))})
    gg = pd.DataFrame(righe)
    print(gg.round(3).to_string(index=False))

    print("\n--- permutazione delle etichette: quante volte un giorno FINTO passa ---")
    righe = []
    for nome in FINESTRE:
        d = tabelle[(nome, "vero")]
        r = d[d.esito == "rottura"].reset_index(drop=True)
        for k in BERSAGLI:
            righe.append({"finestra": nome, "obiettivo": k,
                          "1_giorno_%": giorno_permutato(r, k, 1),
                          "2_giorni_%": giorno_permutato(r, k, 2)})
    print(pd.DataFrame(righe).round(1).to_string(index=False))

    print(f"\ndettaglio grezzo in {GREZZI}/")


if __name__ == "__main__":
    main()
