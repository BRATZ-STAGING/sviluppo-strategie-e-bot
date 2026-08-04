"""Mappa della CONTINUAZIONE di XAUUSD a orizzonti da scalp (nessuna strategia).

Domanda: dopo un movimento di X ATR compiuto negli ultimi N minuti, il prezzo
CONTINUA nella stessa direzione o TORNA INDIETRO nei 30/60/120 minuti
successivi? E questo dipende dall'ora del giorno e dal regime di volatilita'?

La risposta e' una mappa, non una strategia: per ogni combinazione
(N, ampiezza del movimento, orizzonte, ora, regime) si misurano

  - la DERIVA: rendimento medio nella direzione del movimento, in ATR;
  - il RAPPORTO DI CONTINUAZIONE: deriva / ampiezza del movimento (>0 =
    continua, <0 = ritorna);
  - la CORSA fra due barriere (obiettivo e stop) con la scomposizione
    obiettivo / stop / uscita a scadenza, al netto dello spread.

Convenzioni e cautele (ogni riga nasce da un errore possibile):

  - CAUSALITA'. L'evento e' registrato alla CHIUSURA della candela M1 al
    minuto t: il movimento e' close[t] - close[t-N], entrambi noti a t.
    L'ingresso teorico e' l'APERTURA della candela t+1 (fill dei market alla
    candela successiva) e il percorso misurato parte da t+1: nessun minuto
    gia' noto viene ripercorso.
  - L'ATR e' ``volatility.daily_atr(m1, 14)``, noto a inizio giornata.
  - Il regime di volatilita' e' causale: terzili ESPANSIVI dell'ATR calcolati
    sulle sole giornate precedenti (nessun terzile "di tutta la storia").
  - STOP PRIMA DELL'OBIETTIVO: se obiettivo e stop cadono nello stesso minuto
    vince lo stop.
  - COSTI: 0,30 $ andata+ritorno, convertiti in R come 0,30/(stop in dollari).
  - Nessuna posizione oltre le 21:00 UTC (swap): gli eventi e i percorsi sono
    troncati li'. Un orizzonte che non ci sta e' scartato, non accorciato.
  - Il lookback resta dentro la stessa giornata UTC (t >= N): i primi N minuti
    di ogni giornata non generano eventi.
  - CONTROLLO. Il fascione |X| < 0,05 ATR e' la deriva INCONDIZIONATA della
    stessa ora e dello stesso periodo: e' il metro con cui si giudica se il
    movimento aggiunge informazione. In piu' si stampa il controllo a segno
    mescolato, che deve dare zero.

Uso:
    python3 trading/scripts/mappa_continuazione.py
Dettaglio per evento in /workspace/dati_grezzi/continuazione/eventi_<anno>.parquet
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
GREZZI = "/workspace/dati_grezzi/continuazione"

SPREAD = 0.30            # dollari, andata e ritorno
MIN_BARRE = 600          # candele M1 minime perche' la giornata sia "vera"
FINE = 21 * 60           # 21:00 UTC: oltre si paga lo swap
PASSO = 5                # si campiona un evento ogni 5 minuti
NS = (5, 15, 30, 60)     # minuti di lookback del movimento
HS = (30, 60, 120)       # minuti di orizzonte in avanti
HMAX = 120
COPERTURA_MIN = 0.80     # frazione minima di minuti reali nell'orizzonte

# barriere in ATR: da queste si ricostruisce QUALSIASI coppia (stop, obiettivo)
BARRIERE = (0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30)
MAI = 9999               # codice "barriera mai toccata entro HMAX"

# fasce di ampiezza del movimento, in ATR
BIN_BORDI = [0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, np.inf]
BIN_NOMI = ["<.05", ".05-.10", ".10-.15", ".15-.20", ".20-.30", ".30-.50", ">.50"]

PERIODI = {"2009-2019": (2009, 2019), "2020-2026": (2020, 2026)}

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 50)
pd.set_option("display.float_format", lambda v: f"{v:8.3f}")


# --------------------------------------------------------------------------
# costruzione degli eventi
# --------------------------------------------------------------------------
def griglia_giorno(sub: pd.DataFrame):
    """Porta una giornata su una griglia fissa di 1440 minuti.

    Ritorna (open, high, low, close, close_riempito, valido) come array di
    lunghezza 1440. I minuti senza candela restano NaN: non vengono inventati.
    """
    pos = (sub.index.hour * 60 + sub.index.minute).values
    o = np.full(1440, np.nan)
    h = np.full(1440, np.nan)
    lo = np.full(1440, np.nan)
    c = np.full(1440, np.nan)
    o[pos] = sub.open.values
    h[pos] = sub.high.values
    lo[pos] = sub.low.values
    c[pos] = sub.close.values
    valido = ~np.isnan(c)
    # close riempito in avanti: ultimo prezzo scambiato noto (serve al lookback
    # e all'uscita a scadenza, mai a "vedere" un minuto futuro)
    cf = pd.Series(c).ffill().values
    return o, h, lo, c, cf, valido


def finestre_avanti(h: np.ndarray, lo: np.ndarray):
    """Matrici (1440, HMAX) dei massimi/minimi dei minuti t+1 ... t+HMAX.

    I minuti mancanti diventano -inf (massimi) e +inf (minimi): non possono
    far scattare nessuna barriera, cosi' un buco di quotazioni non si traduce
    in un tocco fantasma.
    """
    hp = np.concatenate([np.where(np.isnan(h[1:]), -np.inf, h[1:]),
                         np.full(HMAX, -np.inf)])
    lp = np.concatenate([np.where(np.isnan(lo[1:]), np.inf, lo[1:]),
                         np.full(HMAX, np.inf)])
    swv = np.lib.stride_tricks.sliding_window_view
    return swv(hp, HMAX)[:1440], swv(lp, HMAX)[:1440]


def eventi_giorno(giorno, sub: pd.DataFrame, atr: float, regime: int) -> pd.DataFrame | None:
    """Tutti gli eventi campionati di una giornata, gia' misurati in avanti."""
    o, h, lo, c, cf, valido = griglia_giorno(sub)
    hi_w, lo_w = finestre_avanti(h, lo)

    # copertura: quanti minuti reali ci sono in ciascun tratto in avanti
    cum = np.concatenate([[0], np.cumsum(valido.astype(np.int32))])

    # colonne oltre le 21:00 UTC: rese inoffensive (nessun tocco, nessuna uscita)
    off = np.arange(HMAX)

    righe = []
    for n in NS:
        # minuti candidati: multipli di PASSO, lookback dentro la giornata,
        # candela chiusa davvero a t e ingresso disponibile a t+1
        t = np.arange(0, FINE, PASSO)
        t = t[t >= n]
        t = t[valido[t] & valido[np.minimum(t + 1, 1439)] & (t + 1 < FINE)]
        if t.size == 0:
            continue

        mossa = cf[t] - cf[t - n]
        # NaN quando la giornata comincia con un buco e il lookback ci cade
        # dentro: quei minuti non hanno un prezzo di riferimento, si scartano
        # (senza questo filtro np.sign(NaN) produce direzioni inventate).
        ok = np.isfinite(mossa) & (mossa != 0)
        t, mossa = t[ok], mossa[ok]
        if t.size == 0:
            continue

        direzione = np.sign(mossa)
        x = mossa / atr
        entrata = o[t + 1]

        # percorso in avanti, troncato alle 21:00
        colonne = t[:, None] + 1 + off[None, :]
        fuori = colonne >= FINE
        hw = np.where(fuori, -np.inf, hi_w[t])
        lw = np.where(fuori, np.inf, lo_w[t])
        run_max = np.maximum.accumulate(hw, axis=1)
        run_min = np.minimum.accumulate(lw, axis=1)

        # escursione pro/contro direzione, in dollari, minuto per minuto
        d = direzione[:, None]
        e = entrata[:, None]
        esc_pro = np.where(d > 0, run_max - e, e - run_min)
        esc_con = np.where(d > 0, e - run_min, run_max - e)

        rec = {
            "anno": np.full(t.size, giorno.year, dtype=np.int16),
            "ora": (t // 60).astype(np.int8),
            "n": np.full(t.size, n, dtype=np.int8),
            "regime": np.full(t.size, regime, dtype=np.int8),
            "atr": np.full(t.size, atr, dtype=np.float32),
            "x": x.astype(np.float32),
            "dir": direzione.astype(np.int8),
            "t": t.astype(np.int16),
        }

        # primo minuto di tocco di ogni barriera (monotonia della corsa:
        # l'argmax del booleano e' davvero il PRIMO tocco)
        for b in BARRIERE:
            soglia = b * atr
            for nome, esc in (("p", esc_pro), ("c", esc_con)):
                tocca = esc >= soglia
                mai = ~tocca.any(axis=1)
                idx = tocca.argmax(axis=1).astype(np.int32)
                idx[mai] = MAI
                rec[f"{nome}{b:g}".replace(".", "")] = idx.astype(np.int16)

        # rendimento a scadenza e copertura, per ciascun orizzonte
        for hh in HS:
            fine_h = t + hh
            valida = fine_h < FINE
            cop = (cum[np.minimum(fine_h, 1439) + 1] - cum[t + 1]) / hh
            uscita = cf[np.minimum(fine_h, 1439)]
            ret = (uscita - entrata) * direzione / atr
            ret = np.where(valida & (cop >= COPERTURA_MIN), ret, np.nan)
            rec[f"ret{hh}"] = ret.astype(np.float32)

        righe.append(pd.DataFrame(rec))

    return pd.concat(righe, ignore_index=True) if righe else None


def costruisci(m1: pd.DataFrame) -> None:
    """Genera i Parquet annuali degli eventi (idempotente: salta cio' che c'e')."""
    os.makedirs(GREZZI, exist_ok=True)

    giorno = m1.index.normalize()
    barre = pd.Series(1, index=m1.index).groupby(giorno).size()
    vere = set(barre[barre >= MIN_BARRE].index)

    atr = daily_atr(m1, 14)
    # regime causale: terzili ESPANSIVI, noti prima della giornata
    q33 = atr.expanding(min_periods=250).quantile(0.33).shift(1)
    q67 = atr.expanding(min_periods=250).quantile(0.67).shift(1)
    reg = pd.Series(1, index=atr.index, dtype="int8")
    reg[atr <= q33] = 0
    reg[atr >= q67] = 2
    reg[q33.isna()] = -1

    anni = sorted({d.year for d in vere})
    for anno in anni:
        out = os.path.join(GREZZI, f"eventi_{anno}.parquet")
        if os.path.exists(out):
            continue
        pezzo = m1[m1.index.year == anno]
        blocchi = []
        for g, sub in pezzo.groupby(pezzo.index.normalize(), sort=True):
            if g not in vere:
                continue
            a = atr.get(g, np.nan)
            if not np.isfinite(a) or a <= 0:
                continue
            ev = eventi_giorno(g, sub, float(a), int(reg.get(g, -1)))
            if ev is not None:
                blocchi.append(ev)
        if blocchi:
            pd.concat(blocchi, ignore_index=True).to_parquet(out, index=False)
        print(f"  {anno}: {sum(len(b) for b in blocchi):>8d} eventi", flush=True)


def carica(colonne: list[str]) -> pd.DataFrame:
    """Rilegge gli eventi, solo le colonne servite, e aggiunge fascia/periodo."""
    files = sorted(f for f in os.listdir(GREZZI) if f.startswith("eventi_"))
    df = pd.concat(
        [pd.read_parquet(os.path.join(GREZZI, f), columns=colonne) for f in files],
        ignore_index=True,
    )
    df["periodo"] = pd.Categorical(
        np.where(df.anno <= 2019, "2009-2019", "2020-2026"),
        categories=list(PERIODI))
    if "x" in df.columns:
        df["fascia"] = pd.cut(df.x.abs(), BIN_BORDI, labels=BIN_NOMI, right=False)
    return df


# --------------------------------------------------------------------------
# lettura della corsa fra barriere
# --------------------------------------------------------------------------
def col_barriera(lato: str, b: float) -> str:
    return f"{lato}{round(b, 6):g}".replace(".", "")


def corsa(df: pd.DataFrame, b_stop: float, rr: float, h: int,
          verso: str = "segui") -> pd.DataFrame:
    """Esito della corsa obiettivo/stop entro ``h`` minuti, in R al netto dei costi.

    ``verso='segui'`` apre NELLA direzione del movimento, ``verso='contrasta'``
    nella direzione opposta: e' lo stesso percorso letto a specchio, quindi le
    due letture usano esattamente gli stessi eventi e sono confrontabili.

    Regole: lo stop vince i pareggi di minuto; se nessuna barriera e' toccata
    si esce al prezzo di scadenza; lo spread e' 0,30 $ diviso lo stop in
    dollari. Ritorna le colonne esito ('obiettivo'/'stop'/'scadenza') e r.
    """
    b_obj = round(b_stop * rr, 6)
    if b_obj not in {round(b, 6) for b in BARRIERE}:
        raise ValueError(f"obiettivo {b_obj} non fra le barriere misurate")
    lato_obj, lato_stop = ("p", "c") if verso == "segui" else ("c", "p")
    segno = 1.0 if verso == "segui" else -1.0
    t_obj = df[col_barriera(lato_obj, b_obj)].to_numpy()
    t_stop = df[col_barriera(lato_stop, b_stop)].to_numpy()
    ret = df[f"ret{h}"].to_numpy() * segno

    colpo_obj = t_obj < h
    colpo_stop = t_stop < h
    # stop prima dell'obiettivo, pareggi inclusi
    vince_stop = colpo_stop & (~colpo_obj | (t_stop <= t_obj))
    vince_obj = colpo_obj & ~vince_stop

    r = np.where(vince_stop, -1.0, np.where(vince_obj, rr, ret / b_stop))
    costo = SPREAD / (b_stop * df.atr.to_numpy())
    esito = np.where(vince_stop, "stop", np.where(vince_obj, "obiettivo", "scadenza"))
    # la scadenza richiede un rendimento valido (orizzonte dentro le 21:00)
    buono = colpo_obj | colpo_stop | np.isfinite(ret)
    return pd.DataFrame({"esito": esito, "r": r - costo, "buono": buono}, index=df.index)


# --------------------------------------------------------------------------
# tabelle
# --------------------------------------------------------------------------
def riga(msg: str) -> None:
    print(f"\n{'=' * 108}\n{msg}\n{'=' * 108}")


def tab_deriva() -> None:
    d = carica(["anno", "n", "x", "ret30", "ret60", "ret120"])
    riga("1. DERIVA: rendimento medio NELLA DIREZIONE del movimento, in ATR x100 "
         "(H=60 min)\n   righe = ampiezza del movimento in ATR, colonne = minuti di lookback N.\n"
         "   La riga '<.05' e' il controllo incondizionato: se le altre righe non se ne\n"
         "   discostano, il movimento non sta dicendo nulla.")
    for p, g in d.groupby("periodo"):
        piv = g.pivot_table(index="fascia", columns="n", values="ret60",
                            aggfunc="mean", observed=True) * 100
        cnt = g.pivot_table(index="fascia", columns="n", values="ret60",
                            aggfunc="count", observed=True)
        piv["n_eventi"] = cnt.sum(axis=1).astype(int)
        print(f"\n[{p}]")
        print(piv.round(3))

    riga("2. RAPPORTO DI CONTINUAZIONE: deriva / ampiezza media del movimento.\n"
         "   >0 il prezzo prosegue, <0 rimbalza indietro. N = 15 minuti.")
    q = d[d.n == 15]
    out = []
    for p, g in q.groupby("periodo"):
        for h in HS:
            agg = g.groupby("fascia", observed=True).apply(
                lambda s, h=h: pd.Series({
                    "rapp": s[f"ret{h}"].mean() / s.x.abs().mean(),
                    "deriva_x100": s[f"ret{h}"].mean() * 100,
                    "n": s[f"ret{h}"].count(),
                }), include_groups=False)
            agg["periodo"], agg["H"] = p, h
            out.append(agg.reset_index())
    r = pd.concat(out).pivot_table(index="fascia", columns=["periodo", "H"],
                                   values="rapp", observed=True)
    print(r.round(3))
    nn = pd.concat(out).pivot_table(index="fascia", columns="periodo", values="n",
                                    aggfunc="max", observed=True)
    print("\neventi per fascia (H=30):")
    print(nn.astype(int))


def tab_ora_regime() -> None:
    d = carica(["anno", "n", "x", "ora", "regime", "ret60"])
    d = d[d.n == 15]
    riga("3. DERIVA PER ORA UTC (ATR x100, N=15, H=60).\n"
         "   'grande' = movimenti |X| >= 0,15 ATR; 'tutti' = controllo incondizionato\n"
         "   della stessa ora. La differenza e' cio' che aggiunge il movimento.")
    d["grande"] = d.x.abs() >= 0.15
    t = d.pivot_table(index="ora", columns=["periodo", "grande"], values="ret60",
                      aggfunc="mean") * 100
    t.columns = [f"{p[:4]}_{'grande' if g else 'tutti'}" for p, g in t.columns]
    cnt = d[d.grande].pivot_table(index="ora", columns="periodo", values="ret60",
                                  aggfunc="count")
    t["n_gr_09"] = cnt.get("2009-2019")
    t["n_gr_20"] = cnt.get("2020-2026")
    print(t.round(3))

    riga("4. DERIVA PER REGIME DI VOLATILITA' (terzili espansivi causali dell'ATR).\n"
         "   N=15, H=60, ATR x100. 0=basso 1=medio 2=alto.")
    g = d[d.regime >= 0]
    t2 = g.pivot_table(index="regime", columns=["periodo", "grande"], values="ret60",
                       aggfunc="mean") * 100
    t2.columns = [f"{p[:4]}_{'grande' if q else 'tutti'}" for p, q in t2.columns]
    t2["n_09"] = g[g.periodo == "2009-2019"].groupby("regime").size()
    t2["n_20"] = g[g.periodo == "2020-2026"].groupby("regime").size()
    print(t2.round(3))


def tab_corse() -> None:
    cols = (["anno", "n", "x", "atr", "ora", "ret30", "ret60", "ret120"]
            + [col_barriera(l, b) for l in "pc" for b in BARRIERE])
    d = carica(cols)
    riga("5. CORSA FRA BARRIERE, seguendo il movimento (N=15, H=60).\n"
         "   stop 0,10 ATR. R medio al netto di 0,30 $ di spread. Scomposizione\n"
         "   obbligatoria obiettivo/stop/scadenza: un obiettivo PIU' LONTANO dello\n"
         "   stop deve essere colpito MENO spesso, altrimenti c'e' del futuro dentro.")
    q = d[d.n == 15]
    out = []
    for p, g in q.groupby("periodo", observed=True):
        for verso in ("segui", "contrasta"):
            for rr in (1.0, 1.5, 2.0):
                e = corsa(g, 0.10, rr, 60, verso)
                e = e[e.buono]
                gg = g.loc[e.index]
                costo = SPREAD / (0.10 * gg.atr)
                for f, idx in gg.groupby("fascia", observed=True).groups.items():
                    ee = e.loc[idx]
                    if len(ee) < 300:
                        continue
                    vc = ee.esito.value_counts(normalize=True)
                    out.append({"periodo": p, "verso": verso, "RR": rr, "fascia": f,
                                "p_obj": vc.get("obiettivo", 0.0),
                                "p_stop": vc.get("stop", 0.0),
                                "p_scad": vc.get("scadenza", 0.0),
                                "R_lordo": ee.r.mean() + costo.loc[idx].mean(),
                                "R_netto": ee.r.mean(),
                                "err": ee.r.std() / np.sqrt(len(ee)),
                                "n": len(ee)})
    o = pd.DataFrame(out)
    for p, g in o.groupby("periodo", observed=True):
        print(f"\n[{p}]  R LORDO (prima dello spread), stop 0,10 ATR")
        print(g.pivot_table(index="fascia", columns=["verso", "RR"],
                            values="R_lordo", observed=True).round(3))
    print("\nscomposizione obiettivo/stop/scadenza, RR=1:1,5 (verifica di assurdita':\n"
          "l'obiettivo, piu' lontano dello stop, deve essere colpito MENO spesso):")
    print(o[o.RR == 1.5].set_index(["periodo", "verso", "fascia"])[
        ["p_obj", "p_stop", "p_scad", "R_lordo", "R_netto", "err", "n"]].round(3).to_string())

    riga("6. R LORDO e COSTO al variare di stop e orizzonte (N=15, |X| >= 0,20 ATR,\n"
         "   RR 1:1,5). Il costo dello spread e' quasi sempre piu' grande del segnale.")
    q2 = d[(d.n == 15) & (d.x.abs() >= 0.20)]
    out2 = []
    for p, g in q2.groupby("periodo", observed=True):
        for verso in ("segui", "contrasta"):
            for bs in (0.05, 0.10, 0.20):
                for h in HS:
                    e = corsa(g, bs, 1.5, h, verso)
                    e = e[e.buono]
                    costo = (SPREAD / (bs * g.loc[e.index].atr)).mean()
                    out2.append({"periodo": p, "verso": verso, "stop_ATR": bs, "H": h,
                                 "R_lordo": e.r.mean() + costo, "R_netto": e.r.mean(),
                                 "err": e.r.std() / np.sqrt(len(e)),
                                 "costo_R": costo, "n": len(e)})
    o2 = pd.DataFrame(out2)
    print(o2.pivot_table(index=["stop_ATR", "H"], columns=["periodo", "verso"],
                         values="R_lordo", observed=True).round(3))
    print("\ncosto dello spread in R (identico per i due versi) ed errore standard:")
    print(o2[o2.verso == "segui"].pivot_table(
        index=["stop_ATR", "H"], columns="periodo",
        values=["costo_R", "err"], observed=True).round(3))


def tab_dove() -> None:
    """Dove vive (se vive) il vantaggio lordo del CONTRASTARE: N, ora, regime."""
    cols = (["anno", "n", "x", "atr", "ora", "regime", "ret30", "ret60", "ret120"]
            + [col_barriera(l, b) for l in "pc" for b in (0.10, 0.15)])
    d = carica(cols)
    d = d[d.x.abs() >= 0.20]

    def lordo(g):
        e = corsa(g, 0.10, 1.5, 60, "contrasta")
        e = e[e.buono]
        costo = (SPREAD / (0.10 * g.loc[e.index].atr))
        rl = e.r.mean() + costo.mean()
        return pd.Series({
            "R_lordo": rl,
            "err": e.r.std() / np.sqrt(len(e)),
            # lo stesso vantaggio espresso in DOLLARI per operazione: e' l'unita'
            # in cui va confrontato con lo spread di 0,30 $
            "dollari": rl * 0.10 * g.loc[e.index].atr.mean(),
            "costo_R": costo.mean(),
            "n": float(len(e)),
        })

    riga("9. VANTAGGIO LORDO DEL CONTRASTARE (stop 0,10 ATR, RR 1:1,5, H=60,\n"
         "   |X| >= 0,20 ATR) per minuti di lookback N. 'dollari' = lo stesso\n"
         "   vantaggio in $/operazione, da confrontare con i 0,30 $ di spread.")
    t = d.groupby(["periodo", "n"], observed=True).apply(lordo, include_groups=False)
    print(t.unstack(0).round(3))

    riga("10. LO STESSO, PER ORA UTC (N=15). Se il vantaggio fosse informazione\n"
         "    dovrebbe concentrarsi in qualche ora e reggere su entrambi i periodi.")
    q = d[d.n == 15]
    t2 = q.groupby(["periodo", "ora"], observed=True).apply(lordo, include_groups=False)
    o = t2.unstack(0)[["R_lordo", "dollari", "n"]]
    o.columns = [f"{a}_{b[2:4]}" for a, b in o.columns]
    print(o.round(3).to_string())

    riga("11. LO STESSO, PER REGIME DI VOLATILITA' (N=15, terzili causali).")
    t3 = q[q.regime >= 0].groupby(["periodo", "regime"], observed=True).apply(
        lordo, include_groups=False)
    print(t3.unstack(0).round(3))

    riga("12. TENUTA PER ANNO del vantaggio lordo del contrastare (N=15).\n"
         "    In R e in dollari. Se e' un effetto di microstruttura resta ~fisso in\n"
         "    dollari mentre l'ATR cresce, e quindi si assottiglia in R.")
    t4 = q.groupby("anno", observed=True).apply(lordo, include_groups=False)
    t4["atr_medio"] = q.groupby("anno").atr.mean()
    print(t4.round(3).to_string())


def tab_controlli() -> None:
    d = carica(["anno", "n", "x", "atr", "ora", "dir", "ret60"])
    riga("7. CONTROLLI.\n"
         "   (a) segno mescolato: la stessa regola con direzione casuale deve dare 0;\n"
         "   (b) simmetria long/short: se la deriva vive solo su un lato e' il trend\n"
         "       del metallo, non la continuazione.")
    d = d[d.n == 15]
    rng = np.random.default_rng(7)
    finto = rng.choice([-1.0, 1.0], size=len(d))
    # il rendimento e' gia' orientato: rigirarlo a caso azzera qualsiasi deriva vera
    d["ret_finto"] = d.ret60 * finto
    grande = d.x.abs() >= 0.15
    g = d[grande].groupby("periodo", observed=True)
    t = pd.DataFrame({
        "vero_x100": g.ret60.mean() * 100,
        "err_x100": g.ret60.std() / np.sqrt(g.ret60.count()) * 100,
        "mescolato_x100": g.ret_finto.mean() * 100,
        "err_mesc": g.ret_finto.std() / np.sqrt(g.ret_finto.count()) * 100,
        "n": g.size(),
    })
    t["sigma"] = t.vero_x100 / t.err_x100
    print(t.round(3))
    print("\nLettura: la deriva 'vera' va confrontata con il proprio errore standard\n"
          "E con il controllo a segno mescolato. Se i due sono dello stesso ordine,\n"
          "seguire il movimento non e' distinguibile dal lanciare una moneta.")

    lato = d[grande].groupby(["periodo", "dir"]).agg(
        deriva_x100=("ret60", lambda s: s.mean() * 100), n=("ret60", "size"))
    print("\nper lato (dir +1 = movimento al rialzo, si seguirebbe long):")
    print(lato.round(3))

    riga("8. TENUTA PER ANNO del fatto principale (N=15, |X| >= 0,15 ATR, H=60).\n"
         "   deriva in ATR x100, anno per anno: un fatto che vive in 3 anni non e' un fatto.")
    a = d[d.x.abs() >= 0.15].groupby("anno").agg(
        deriva_x100=("ret60", lambda s: s.mean() * 100), n=("ret60", "size"))
    a["segno"] = np.where(a.deriva_x100 > 0, "+", "-")
    print(a.round(3).to_string())


def main() -> None:
    os.makedirs(GREZZI, exist_ok=True)
    if not any(f.startswith("eventi_") for f in os.listdir(GREZZI)):
        print("costruzione eventi (una tantum)...", flush=True)
        m1 = load_m1(DATI)
        costruisci(m1)
        del m1
    tab_deriva()
    tab_ora_regime()
    tab_corse()
    tab_dove()
    tab_controlli()


if __name__ == "__main__":
    main()
