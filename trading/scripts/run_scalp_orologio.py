#!/usr/bin/env python3
"""Scalp XAUUSD a partire da zero: la famiglia di ipotesi e' L'OROLOGIO.

Nessun livello, nessun VWAP, nessuna struttura: solo il calendario e
l'orologio. La domanda e': esistono momenti fissi della giornata (o del mese)
in cui il prezzo dell'oro si muove in modo abbastanza prevedibile da pagare
uno scalp?

MISURE PRE-REGISTRATE (scritte PRIMA di guardare i dati)
-------------------------------------------------------
1. DERIVA DOPO ORARI FISSI. Orari UTC: apertura di Londra 07:00, apertura di
   New York 13:30, fixing pomeridiano di Londra 15:00, chiusura del Comex
   18:30, ultima ora prima della chiusura giornaliera 20:00. Per ciascuno si
   misura il movimento medio a 15, 30 e 60 minuti, in dollari, con la
   convenzione "long" (positivo = il prezzo sale). Si misura due volte:
   a) senza filtro di direzione;
   b) con filtro di CONTINUAZIONE: il segno della sessione precedente, che e'
      noto prima dell'orario e quindi non e' lookahead. Finestre precedenti:
      Londra 07:00 <- 00:00-07:00; New York 13:30 <- 07:00-13:30; fixing
      15:00 <- 13:30-15:00; Comex 18:30 <- 15:00-18:30; ultima ora
      20:00 <- 12:00-20:00.
2. RANGE DI APERTURA DI LONDRA. Massimo e minimo dei primi 30 minuti
   (07:00-07:30) e dei primi 60 (07:00-08:00). Dalla fine del range fino alle
   12:00 si cerca la PRIMA candela M1 che chiude oltre il bordo. Due ipotesi
   opposte e simmetriche: CONTINUAZIONE (si entra nel verso della rottura) e
   RIENTRO/FADE (si entra contro). Ingresso all'apertura della candela
   SUCCESSIVA a quella che chiude oltre il bordo.
3. GIORNO DELLA SETTIMANA E GIORNO DEL MESE. Rendimento della giornata
   (prezzo alle 00:00 -> prezzo alle 21:00 UTC) per giorno della settimana, e
   per primo/ultimo giorno lavorativo del mese.
4. ULTIMA ORA PRIMA DELLA CHIUSURA (20:00-21:00 UTC): e' il punto 1 con
   orario 20:00 e orizzonte 60 minuti.

IL VINCOLO ARITMETICO CHE DECIDE TUTTO
--------------------------------------
Lo spread vero dell'oro, misurato su 6,1 milioni di tick, e' 0,33 $ fino al
2024 e 0,63 $ dal 2025. Con uno stop da 3 $ il costo di andata e ritorno vale
il 10-21% del rischio; con uno stop da 5 $ il 6,6-12,6%. Quindi il vantaggio
LORDO deve superare 0,10-0,20 R per operazione, altrimenti lo scalp non
esiste nemmeno come idea. Costo per anno, in dollari, sottratto una volta per
operazione (si compra al denaro+spread e si vende al denaro):
  2020 0,350 | 2021 0,349 | 2022 0,395 | 2023 0,334 | 2024 0,384 |
  2025 0,632 | 2026 0,631
Lordo e netto sono SEMPRE riportati separatamente, insieme al costo in %R.

PROTOCOLLO
----------
- Periodo 2020-2026 (XAU_ANNI=2020-2026). Ricerca 2020-2022, verifica
  2023-2026: entrambi riportati sempre, nessuna scelta fatta guardando la
  verifica.
- Gestione, sei celle e non una di piu': stop 3 $ e 5 $ per obiettivo 1:1,5 e
  1:2 (durata massima 120 minuti, poi chiusura a mercato), piu' due varianti
  senza obiettivo con chiusura a orario fisso dopo 60 minuti.
- Chiusura obbligatoria alle 21:00 UTC (rollover) in ogni caso.
- NIENTE LOOKAHEAD. Le candele sono etichettate all'APERTURA del minuto: la
  candela delle 07:00 copre 07:00-07:01 e la sua chiusura si conosce solo
  alle 07:01. Per questo:
  * gli ingressi "a orologio" avvengono all'APERTURA della candela dell'orario
    (decisione che non richiede alcuna informazione: e' una sveglia);
  * gli ingressi da rottura richiedono la CHIUSURA della candela che rompe e
    quindi entrano all'APERTURA della candela successiva;
  * il filtro di continuazione usa solo minuti che precedono l'orario.
- A parita' di minuto lo STOP prevale sull'obiettivo (ipotesi conservativa).
- PLACEBO. Ogni configurazione e' ripetuta su ORARI CASUALI: stessi giorni,
  stesso numero di operazioni, stesso segno di direzione, stessa durata
  massima disponibile fino alle 21:00, stesse celle di gestione, seme fisso.
  Cambia solo QUANDO. Se il placebo pareggia o batte l'ipotesi vera, l'ora
  non contiene informazione e il risultato dello studio e' questo.
- CONTROLLO DI ASSURDITA': con stop 3 $ e obiettivo 6 $ lo stop vicino DEVE
  essere colpito piu' spesso dell'obiettivo lontano. Se non lo e', il motore
  ha un baco. Stampato.

Uso: XAU_ANNI=2020-2026 python3 run_scalp_orologio.py
Dettaglio aggregato in docs/studies/dati/scalp_orologio.parquet.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "docs", "studies", "dati", "scalp_orologio.parquet")

SPREAD = {2020: 0.350, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}
RIC, VER = (2020, 2022), (2023, 2026)
SEED = 20260804
MIN_NS = 60 * 10 ** 9
TOL = 5 * MIN_NS                      # tolleranza di allineamento sui buchi
CHIUSURA_MIN = 21 * 60                # 21:00 UTC in minuti dalla mezzanotte

# sei celle di gestione: (nome, stop $, moltiplicatore obiettivo, durata max)
CELLE = [
    ("s3_1:1.5", 3.0, 1.5, 120),
    ("s3_1:2", 3.0, 2.0, 120),
    ("s5_1:1.5", 5.0, 1.5, 120),
    ("s5_1:2", 5.0, 2.0, 120),
    ("s3_tempo60", 3.0, None, 60),
    ("s5_tempo60", 5.0, None, 60),
]

# orario -> (ora, minuto, inizio finestra precedente in minuti dalla mezzanotte)
OROLOGI = {
    "LON_0700": (7, 0, 0),
    "NY_1330": (13, 30, 7 * 60),
    "FIX_1500": (15, 0, 13 * 60 + 30),
    "COMEX_1830": (18, 30, 15 * 60),
    "EOD_2000": (20, 0, 12 * 60),
}


# --------------------------------------------------------------- utilita' --
def pos_di(iv, t_ns):
    """Posizione della candela che apre a ``t_ns`` (o la prima entro TOL)."""
    p = np.searchsorted(iv, t_ns, side="left")
    ok = (p < len(iv)) & (iv[np.minimum(p, len(iv) - 1)] - t_ns <= TOL)
    return p, ok


def esito(a, fine, dirz, stop_usd, tp_usd, o, h, l_, c):
    """Esito lordo in R di un'operazione aperta all'apertura della barra ``a``.

    ``fine`` e' l'indice ESCLUSIVO oltre il quale si chiude a mercato. Nella
    stessa candela lo stop prevale sull'obiettivo.
    """
    entry = o[a]
    hh, ll = h[a:fine], l_[a:fine]
    if dirz > 0:
        sl, tp = entry - stop_usd, (entry + tp_usd if tp_usd else None)
        m_sl, m_tp = ll <= sl, (hh >= tp if tp_usd else None)
    else:
        sl, tp = entry + stop_usd, (entry - tp_usd if tp_usd else None)
        m_sl, m_tp = hh >= sl, (ll <= tp if tp_usd else None)
    i_sl = int(np.argmax(m_sl)) if m_sl.any() else None
    i_tp = (int(np.argmax(m_tp)) if (m_tp is not None and m_tp.any()) else None)
    if i_sl is not None and (i_tp is None or i_sl <= i_tp):
        return -1.0, "stop"
    if i_tp is not None:
        return (tp_usd / stop_usd), "obiettivo"
    uscita = o[fine] if fine < len(o) else c[len(c) - 1]
    return float((uscita - entry) * dirz / stop_usd), "tempo"


def simula(eventi, iv, o, h, l_, c):
    """Applica le sei celle a una lista di eventi (pos, dir, anno, cap_ns)."""
    righe = []
    n = len(iv)
    for nome, stop_usd, rr, dur in CELLE:
        tp_usd = None if rr is None else stop_usd * rr
        for a, dirz, anno, cap_ns in eventi:
            fine_ns = min(iv[a] + dur * MIN_NS, cap_ns)
            fine = int(np.searchsorted(iv, fine_ns, side="left"))
            fine = min(max(fine, a + 1), n)
            r, come = esito(a, fine, dirz, stop_usd, tp_usd, o, h, l_, c)
            righe.append((nome, stop_usd, anno, r, come))
    return pd.DataFrame(righe, columns=["cella", "stop", "anno", "lordo", "come"])


def aggrega(det, setup, tipo):
    """Aggregati per cella e periodo, con costo dello spread per anno."""
    det = det.copy()
    det["costo"] = det["anno"].map(SPREAD) / det["stop"]
    det["netto"] = det["lordo"] - det["costo"]
    det["periodo"] = np.where(det["anno"] <= RIC[1], "ric", "ver")
    g = det.groupby(["cella", "periodo"], as_index=False).agg(
        n=("lordo", "size"), lordo=("lordo", "mean"), netto=("netto", "mean"),
        costo=("costo", "mean"),
        stop_pct=("come", lambda s: (s == "stop").mean()),
        tp_pct=("come", lambda s: (s == "obiettivo").mean()))
    g.insert(0, "setup", setup)
    g.insert(1, "tipo", tipo)
    return g


# ------------------------------------------------------------------ main --
def main():
    pd.set_option("display.width", 200)
    df = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    iv = df.index.values.astype("datetime64[ns]").astype(np.int64)
    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    l_ = df["low"].to_numpy()
    c = df["close"].to_numpy()
    n = len(iv)

    giorni = pd.DatetimeIndex(sorted(set(df.index.normalize())))
    giorni = giorni[giorni.dayofweek < 5]
    g_ns = giorni.values.astype("datetime64[ns]").astype(np.int64)
    anni = giorni.year.to_numpy()
    cap_ns = g_ns + CHIUSURA_MIN * MIN_NS          # chiusura obbligatoria 21:00

    def prezzo_a(minuti):
        """Prezzo di apertura al minuto ``minuti`` di ogni giornata (NaN se manca)."""
        p, ok = pos_di(iv, g_ns + minuti * MIN_NS)
        v = np.where(ok, o[np.minimum(p, n - 1)], np.nan)
        return v, p, ok

    # ------------------------------------------------ 1. deriva e direzione --
    drift, eventi_orologio = [], {}
    for nome, (hh, mm, prev0) in OROLOGI.items():
        m0 = hh * 60 + mm
        p0, pos0, ok0 = prezzo_a(m0)
        pprev, _, okp = prezzo_a(prev0)
        pm1, _, okm1 = prezzo_a(m0 - 1)             # ultimo minuto NOTO prima
        segno = np.sign(np.nan_to_num(p0 * 0 + (pm1 - pprev)))
        for orizz in (15, 30, 60):
            if m0 + orizz > CHIUSURA_MIN:
                mv = np.full(len(giorni), np.nan)
            else:
                p1, _, ok1 = prezzo_a(m0 + orizz)
                mv = np.where(ok0 & ok1, p1 - p0, np.nan)
            for per, (a0, a1) in (("ric", RIC), ("ver", VER)):
                sel = (anni >= a0) & (anni <= a1) & ~np.isnan(mv)
                for filt, msk in (("nessuno", sel), ("cont", sel & (segno != 0))):
                    v = mv[msk] * (1 if filt == "nessuno" else segno[msk])
                    drift.append((nome, filt, orizz, per, int(len(v)),
                                  float(np.mean(v)) if len(v) else np.nan,
                                  float(np.mean(v) / (np.std(v, ddof=1) / np.sqrt(len(v))))
                                  if len(v) > 2 and np.std(v) > 0 else np.nan))
        buoni = ok0 & okp & okm1 & (segno != 0)
        eventi_orologio[nome] = (pos0, buoni, segno)

    drift = pd.DataFrame(drift, columns=["evento", "filtro", "orizz", "periodo",
                                         "n", "media_usd", "t"])

    # -------------------------------------------- 2. range di apertura LON --
    or_eventi = {}
    for durata in (30, 60):
        pa, oka = pos_di(iv, g_ns + 7 * 60 * MIN_NS)
        pb, okb = pos_di(iv, g_ns + (7 * 60 + durata) * MIN_NS)
        pfine, _ = pos_di(iv, g_ns + 12 * 60 * MIN_NS)
        pos_r, dirz_r = [], []
        for k in range(len(giorni)):
            if not (oka[k] and okb[k]) or pb[k] <= pa[k]:
                pos_r.append(-1); dirz_r.append(0); continue
            hi = h[pa[k]:pb[k]].max(); lo = l_[pa[k]:pb[k]].min()
            seg = slice(pb[k], min(pfine[k], n))
            cc = c[seg]
            su = np.flatnonzero(cc > hi); giu = np.flatnonzero(cc < lo)
            i_su = su[0] if len(su) else 10 ** 9
            i_giu = giu[0] if len(giu) else 10 ** 9
            if min(i_su, i_giu) == 10 ** 9:
                pos_r.append(-1); dirz_r.append(0); continue
            i = min(i_su, i_giu)
            entrata = pb[k] + i + 1                 # apertura della SUCCESSIVA
            if entrata >= min(pfine[k], n):
                pos_r.append(-1); dirz_r.append(0); continue
            pos_r.append(entrata)
            dirz_r.append(1 if i_su < i_giu else -1)
        or_eventi[durata] = (np.array(pos_r), np.array(dirz_r))

    # ---------------------------------- 3. giorno della settimana e del mese --
    p00, _, ok00 = prezzo_a(0)
    p21, _, ok21 = prezzo_a(CHIUSURA_MIN)
    gg = pd.DataFrame({"data": giorni, "anno": anni,
                       "dow": giorni.dayofweek, "rend": np.where(ok00 & ok21, p21 - p00, np.nan)})
    gg["periodo"] = np.where(gg["anno"] <= RIC[1], "ric", "ver")
    gg["ym"] = gg["data"].dt.to_period("M")
    gg["primo"] = gg.groupby("ym")["data"].transform("min") == gg["data"]
    gg["ultimo"] = gg.groupby("ym")["data"].transform("max") == gg["data"]

    # ------------------------------------------------ setup -> lista eventi --
    setup = {}
    for nome, (pos0, buoni, segno) in eventi_orologio.items():
        base = [(int(pos0[k]), 1, int(anni[k]), int(cap_ns[k]))
                for k in range(len(giorni)) if buoni[k] and pos0[k] < n]
        setup[nome + "|long"] = base
        setup[nome + "|cont"] = [(int(pos0[k]), int(segno[k]), int(anni[k]), int(cap_ns[k]))
                                 for k in range(len(giorni)) if buoni[k] and pos0[k] < n]
    for durata, (pos_r, dirz_r) in or_eventi.items():
        val = [k for k in range(len(giorni)) if pos_r[k] >= 0]
        setup[f"ORB{durata}|rottura"] = [(int(pos_r[k]), int(dirz_r[k]), int(anni[k]),
                                          int(cap_ns[k])) for k in val]
        setup[f"ORB{durata}|rientro"] = [(int(pos_r[k]), -int(dirz_r[k]), int(anni[k]),
                                          int(cap_ns[k])) for k in val]

    # ------------------------------------------------------------- placebo --
    rng = np.random.default_rng(SEED)
    giorno_di = {int(g_ns[k]): k for k in range(len(giorni))}

    def placebo(eventi):
        """Stessi giorni, stesso segno, stessa durata utile: minuto a caso."""
        out = []
        for a, dirz, anno, cap in eventi:
            gday = int(iv[a] // (86400 * 10 ** 9)) * 86400 * 10 ** 9
            k = giorno_di.get(gday)
            if k is None:
                continue
            utile = (cap - iv[a]) // MIN_NS          # minuti fino alle 21:00
            hi = CHIUSURA_MIN - utile
            for _ in range(6):
                m = int(rng.integers(0, max(hi, 1)))
                p, ok = pos_di(iv, np.array([g_ns[k] + m * MIN_NS]))
                if ok[0] and p[0] < n:
                    out.append((int(p[0]), dirz, anno, int(iv[p[0]] + utile * MIN_NS)))
                    break
        return out

    # ------------------------------------------------------------ simulazione --
    tutti = []
    for nome, ev in setup.items():
        if len(ev) < 50:
            continue
        tutti.append(aggrega(simula(ev, iv, o, h, l_, c), nome, "vero"))
        tutti.append(aggrega(simula(placebo(ev), iv, o, h, l_, c), nome, "placebo"))
    agg = pd.concat(tutti, ignore_index=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pd.concat([agg.assign(blocco="griglia"),
               drift.assign(blocco="deriva")], ignore_index=True).to_parquet(OUT)

    # --------------------------------------------------------------- stampa --
    f3 = "{:.3f}".format
    print("\n=== A. DERIVA DOPO ORARI FISSI (media $, convenzione long; t fra parentesi) ===")
    piv = drift.pivot_table(index=["evento", "filtro"], columns=["periodo", "orizz"],
                            values="media_usd")
    piv = piv.reindex(columns=pd.MultiIndex.from_product([["ric", "ver"], [15, 30, 60]]))
    print(piv.to_string(float_format=f3, na_rep="-"))
    tmax = drift.loc[drift["t"].abs().idxmax()]
    print(f"t massimo in valore assoluto: {tmax['evento']}/{tmax['filtro']}/"
          f"{tmax['orizz']}min/{tmax['periodo']} t={tmax['t']:.2f} n={tmax['n']}")

    print("\n=== B. GIORNO (rendimento 00:00->21:00, media $ e t di Student) ===")

    def mt(s):
        s = s.dropna()
        if len(s) < 3 or s.std() == 0:
            return np.nan, np.nan, len(s)
        return s.mean(), s.mean() / (s.std(ddof=1) / np.sqrt(len(s))), len(s)

    nomi = {0: "lun", 1: "mar", 2: "mer", 3: "gio", 4: "ven"}
    for d in range(5):
        parti = []
        for p in ("ric", "ver"):
            m, t, k = mt(gg[(gg["dow"] == d) & (gg["periodo"] == p)]["rend"])
            parti.append(f"{p} {m:7.3f} (t {t:5.2f}, n={k})")
        print(f"{nomi[d]}: " + " | ".join(parti))
    for et, col in (("primo giorno lav.", "primo"), ("ultimo giorno lav.", "ultimo")):
        parti = []
        for p in ("ric", "ver"):
            m, t, k = mt(gg[gg[col] & (gg["periodo"] == p)]["rend"])
            parti.append(f"{p} {m:7.3f} (t {t:5.2f}, n={k})")
        print(f"{et}: " + " | ".join(parti))

    print("\n=== C. GRIGLIA: per ogni setup la cella migliore sulla RICERCA ===")
    v = agg[agg["tipo"] == "vero"]
    ric = v[v["periodo"] == "ric"].set_index(["setup", "cella"])
    ver = v[v["periodo"] == "ver"].set_index(["setup", "cella"])
    pla = agg[agg["tipo"] == "placebo"].set_index(["setup", "cella", "periodo"])
    righe = []
    for s in sorted(ric.index.get_level_values(0).unique()):
        sub = ric.loc[s]
        best = sub["lordo"].idxmax()
        r, w = sub.loc[best], (ver.loc[(s, best)] if (s, best) in ver.index else None)
        righe.append({
            "setup": s, "cella": best, "n_ric": int(r["n"]),
            "lordo_ric": r["lordo"], "netto_ric": r["netto"],
            "costo%R": 100 * r["costo"],
            "lordo_ver": w["lordo"] if w is not None else np.nan,
            "netto_ver": w["netto"] if w is not None else np.nan,
            "plac_ric": pla.loc[(s, best, "ric"), "lordo"],
            "plac_ver": pla.loc[(s, best, "ver"), "lordo"]})
    tab = pd.DataFrame(righe).sort_values("lordo_ric", ascending=False)
    print(tab.to_string(index=False, float_format=f3))

    print("\n=== D. VERDETTO ===")
    soglia = 0.15
    ok = tab[(tab["lordo_ric"] > soglia) & (tab["lordo_ver"] > soglia)]
    print(f"setup con LORDO > {soglia} R/op in ENTRAMBI i periodi: "
          f"{len(ok)}" + (" -> " + ", ".join(ok['setup']) if len(ok) else " (nessuno)"))
    netti = tab[(tab["netto_ric"] > 0) & (tab["netto_ver"] > 0)]
    print(f"setup con NETTO positivo in entrambi i periodi: {len(netti)}"
          + (" -> " + ", ".join(netti["setup"]) if len(netti) else ""))
    batte = tab[(tab["lordo_ric"] > tab["plac_ric"]) & (tab["lordo_ver"] > tab["plac_ver"])]
    print(f"setup che battono il proprio PLACEBO in entrambi i periodi: {len(batte)}/"
          f"{len(tab)}" + (" -> " + ", ".join(batte["setup"]) if len(batte) else ""))
    pl = agg[agg["tipo"] == "placebo"]
    mv, mp = v["lordo"].mean(), pl["lordo"].mean()
    print(f"media su TUTTE le {len(v)} celle-periodo: vero {mv:.3f} R/op, "
          f"placebo {mp:.3f} R/op")
    print(f"perche': agli orari veri lo stop e' preso nel "
          f"{100*v['stop_pct'].mean():.1f}% dei casi contro il "
          f"{100*pl['stop_pct'].mean():.1f}% a orari a caso "
          f"(obiettivo {100*v['tp_pct'].mean():.1f}% contro "
          f"{100*pl['tp_pct'].mean():.1f}%): gli orari fissi selezionano i "
          f"minuti volatili, e uno stop stretto li paga.")

    print("\n=== E. CONTROLLO DI ASSURDITA' (stop 3 $ contro obiettivo 6 $) ===")
    ck = v[v["cella"] == "s3_1:2"]
    print(f"stop preso {100*ck['stop_pct'].mean():.1f}% dei casi, obiettivo "
          f"{100*ck['tp_pct'].mean():.1f}%, tempo "
          f"{100*(1-ck['stop_pct'].mean()-ck['tp_pct'].mean()):.1f}%; "
          f"celle in cui l'obiettivo lontano batte lo stop vicino: "
          f"{int((ck['tp_pct'] > ck['stop_pct']).sum())}/{len(ck)}")
    print(f"\ndettaglio: {OUT}")


if __name__ == "__main__":
    main()
