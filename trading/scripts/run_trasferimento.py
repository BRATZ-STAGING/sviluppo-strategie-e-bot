#!/usr/bin/env python3
"""Trasferimento del VWAP reclaim su un altro mercato, come da registrazione.

Implementa alla lettera ``docs/trasferimento-indici-registrazione.md``
(scritto prima dei dati): stesse regole d'ingresso (``UFFICIALE``), prezzi
riscalati di un solo fattore ``f`` perche' le soglie in dollari dell'oro
valgano lo stesso in unita' di volatilita', spread vero per anno, le quattro
gestioni di ``verifica_bot.py`` (primaria: B), 200 placebo, verdetto secondo
il criterio registrato.

DATI
  XAUUSD  ``data/XAUUSD_M1/`` (``load_m1``, solo BID). Lo spread non si misura:
          si usa il dizionario ``SPREAD`` di ``verifica_bot`` (2020-2026) e
          0,40 $ per gli anni precedenti, lo stesso default di
          ``verifica_bot`` (``SPREAD.get(anno, 0.40)``) e dell'appendice BS.
  indici  ``<SIMBOLO>/{BID,ASK}_<anno>*.parquet`` di ``scarica_indice.py``
          (un anno puo' essere diviso in piu' file), cercati nell'ordine in
          ``$IDX_OUT`` (se impostata), ``data/indici``, ``D:\\dati_grezzi\\indici``:
          vale la prima cartella che ha dei BID del simbolo.

SCALA  ``f = 25,5968 / mediana ATR14 D1 del 2020-2024``, calcolata come quella
       dell'oro: ``daily_atr`` sulle sole candele 2020-2024 (caricando solo
       quegli anni l'oro da' esattamente 25,5968). Per l'oro il protocollo
       fissa f = 1: il valore calcolato si stampa solo come controllo.

QUALITA' (Emendamento 1, solo indici; per l'oro non c'e' ASK e non si
       applica)  giornata UTC **sana** se ha scambi (volume BID e ASK > 0) in
       >= 95% degli 840 minuti 7-21 UTC (un minuto assente dal file conta
       come senza scambi) e ASK > BID in >= 90% dei minuti 7-21 presenti su
       entrambi i lati. Stessa definizione di ``qualita_indici.py``. Nelle giornate non
       sane non si apre nulla (ne' vero ne' placebo); le candele restano per
       gli indicatori. Gli anni con < 100 giornate sane si riportano a parte
       e non entrano nel criterio degli anni positivi.

SPREAD (indici)  mediana annua di ASK close - BID close sui minuti 7-21 UTC
       presenti in entrambi i lati, nelle sole giornate sane, moltiplicata
       per ``f``.

PLACEBO (§5)  200 serie, seme fisso. Per ogni anno tante operazioni quante la
       gestione B ne ha valutate; istanti estratti a caso (senza ripetizione
       dentro la serie) fra le chiusure M6 delle candele aperte nelle ore
       ammesse ``[ora_inizio, ora_fine)``, con almeno due minuti prima della
       chiusura delle 21 come richiede ``genera``; ingresso alla chiusura M6;
       direzione a caso; rischio estratto dai rischi veri DELLO STESSO ANNO
       (lo spread in R dipende dal rischio, e il rischio dall'epoca);
       gestione B, stesso costo.

USCITA  ``docs/studies/dati/trasferimento_<SIMBOLO>[_<da>-<a>].parquet``:
       righe ``tipo='vero'`` = un'operazione per gestione (R netto);
       righe ``tipo='placebo'`` = una per serie e anno (``n`` operazioni,
       ``R`` somma). Il suffisso c'e' solo se gli anni sono dati a mano.

Uso:  python trading/scripts/run_trasferimento.py SIMBOLO [anno_da anno_a]
"""
from __future__ import annotations

import gc
import glob
import os
import sys
import time

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(QUI, ".."))
sys.path.insert(0, QUI)

from framework.data import load_m1, resample_tf, validate_ohlcv   # noqa: E402
from framework.segnali import genera                              # noqa: E402
from framework.taratura import UFFICIALE as T                     # noqa: E402
from framework.volatility import daily_atr                        # noqa: E402
from verifica_bot import (BOT, MEDIANA_ATR, SPREAD, Percorsi,     # noqa: E402
                          filtra, misure, valuta)

ROOT = os.path.abspath(os.path.join(QUI, "..", ".."))
CARTELLE_IDX = ([os.environ["IDX_OUT"]] if os.environ.get("IDX_OUT") else []) + [
    os.path.join(ROOT, "data", "indici"), r"D:\dati_grezzi\indici"]
SPREAD_ORO_VECCHI = 0.40      # verifica_bot: SPREAD.get(anno, 0.40); appendice BS
N_PLACEBO = 200
SEME = 20261002
ORE_SPREAD = (7, 21)          # [inizio, fine) UTC, anche per la qualita'
MINUTI_SESSIONE = (ORE_SPREAD[1] - ORE_SPREAD[0]) * 60
MIN_COPERTURA = 0.95          # Emendamento 1 (= appendice BL)
MIN_DUE_LATI = 0.90
MIN_GIORNI_SANI = 100
NOMI = ["in uso", "A", "B", "1:2"]
PRIMARIA = "B"


# --------------------------------------------------------------------------
# dati
# --------------------------------------------------------------------------
def cartella(simbolo: str) -> str:
    for d in CARTELLE_IDX:
        if glob.glob(os.path.join(d, simbolo, "BID_*.parquet")):
            return os.path.join(d, simbolo)
    raise FileNotFoundError(f"nessun BID di {simbolo} in {CARTELLE_IDX}")


def leggi_lato(simbolo: str, lato: str, anno: int) -> pd.DataFrame | None:
    fs = sorted(glob.glob(os.path.join(cartella(simbolo), f"{lato}_{anno}*.parquet")))
    if not fs:
        return None
    d = pd.concat([pd.read_parquet(f) for f in fs])
    d.index = pd.DatetimeIndex(d.index)
    if d.index.tz is None:
        d.index = d.index.tz_localize("UTC")
    d.index = d.index.tz_convert("UTC").as_unit("ms")
    d.index.name = "timestamp"
    d = d[["open", "high", "low", "close", "volume"]].astype("float64")
    d = d[d.index.year == anno]
    return d[~d.index.duplicated(keep="first")].sort_index()


def anni_indice(simbolo: str) -> list[int]:
    fs = glob.glob(os.path.join(cartella(simbolo), "BID_*.parquet"))
    return sorted({int(os.path.basename(f)[4:8]) for f in fs})


def qualita_anno(bid: pd.DataFrame, ask: pd.DataFrame | None):
    """Giornate sane dell'anno e spread grezzo (prezzi non riscalati).

    Restituisce (giornate sane, spread mediano sulle sane o NaN, giornate con
    dati nelle ore 7-21). Senza ASK nessuna giornata e' sana.
    """
    s = bid[(bid.index.hour >= ORE_SPREAD[0]) & (bid.index.hour < ORE_SPREAD[1])]
    giorni_dati = s.index.normalize().unique()
    if ask is None or ask.empty:
        return pd.DatetimeIndex([], tz="UTC"), float("nan"), len(giorni_dati)
    j = s[["close", "volume"]].join(ask[["close", "volume"]], how="inner",
                                    rsuffix="_ask")
    g = j.index.normalize()
    scambi = (j.volume.values > 0) & (j.volume_ask.values > 0)
    due = (j.close_ask.values - j.close.values) > 0
    q = pd.DataFrame({"scambi": scambi, "due": due}, index=g).groupby(level=0).agg(
        scambi=("scambi", "sum"), due=("due", "mean"))
    q["scambi"] = q.scambi / MINUTI_SESSIONE     # sugli 840 minuti, non sui presenti
    sane = q[(q.scambi >= MIN_COPERTURA) & (q.due >= MIN_DUE_LATI)].index
    dentro = g.isin(sane)
    spread = (float(np.median(j.close_ask.values[dentro] - j.close.values[dentro]))
              if dentro.any() else float("nan"))
    return sane, spread, len(giorni_dati)


def carica(simbolo: str, anni: list[int]):
    """M1 BID nello schema di ``load_m1`` (indice UTC 'timestamp', float64).

    Per gli indici restituisce anche, per anno, (giornate sane, spread grezzo,
    giornate con dati) dell'Emendamento 1; per l'oro ``None``. L'ASK si legge
    un anno alla volta e si butta subito.
    """
    if simbolo == "XAUUSD":
        return load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"), anni), None
    pezzi, qual = [], {}
    for a in anni:
        bid = leggi_lato(simbolo, "BID", a)
        if bid is None or bid.empty:
            continue
        ask = leggi_lato(simbolo, "ASK", a)
        qual[a] = qualita_anno(bid, ask)
        del ask
        pezzi.append(bid)
    if not pezzi:
        raise FileNotFoundError(f"nessun BID per {simbolo} {anni}")
    m1 = pd.concat(pezzi).sort_index()
    del pezzi
    gc.collect()
    try:
        validate_ohlcv(m1)
    except ValueError as e:
        raise ValueError(f"{simbolo}: {e}") from None
    print(f"[M1] {m1.index[0]:%Y-%m-%d} -> {m1.index[-1]:%Y-%m-%d}, "
          f"{len(m1):,} candele", file=sys.stderr)
    return m1, qual


def carica_bid(simbolo: str, anni: list[int]) -> pd.DataFrame:
    """Solo il BID, senza qualita' (serve al fattore di scala)."""
    if simbolo == "XAUUSD":
        return load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"), anni)
    pezzi = [x for x in (leggi_lato(simbolo, "BID", a) for a in anni) if x is not None]
    return pd.concat(pezzi).sort_index()


def mediana_atr(m1: pd.DataFrame, t=T) -> float:
    """Mediana ATR14 D1 sugli anni di calibrazione, come per l'oro.

    ``m1`` deve contenere SOLO le candele degli anni di calibrazione: e' cosi'
    che si ottiene 25,5968 sull'oro (con il 2019 caricato verrebbe 25,41).
    """
    atr = daily_atr(m1, 14)
    sel = (atr.index.year >= t.calibrazione[0]) & (atr.index.year <= t.calibrazione[1])
    return float(atr[sel].median())


def fattore(simbolo: str, m1: pd.DataFrame, anni: list[int]) -> tuple[float, list[int]]:
    cal = list(range(T.calibrazione[0], T.calibrazione[1] + 1))
    if set(cal) <= set(anni):
        sub = m1[(m1.index.year >= cal[0]) & (m1.index.year <= cal[-1])]
        usati = cal
    else:
        disp = cal if simbolo == "XAUUSD" else [a for a in cal if a in anni_indice(simbolo)]
        if not disp:
            raise FileNotFoundError(f"{simbolo}: nessun anno di calibrazione {cal}")
        sub = carica_bid(simbolo, disp)
        usati = disp
    med = mediana_atr(sub)
    del sub
    gc.collect()
    return MEDIANA_ATR / med, usati


# --------------------------------------------------------------------------
# placebo
# --------------------------------------------------------------------------
def candidati_placebo(m1: pd.DataFrame, sane=None, t=T) -> pd.DataFrame:
    """Chiusure M6 nelle ore ammesse, con lo stesso vincolo di ``genera``.

    ``sane``: se data, solo le giornate sane (Emendamento 1).
    """
    passo = pd.Timedelta("6min")
    base = resample_tf(m1, t.tf_ingresso)
    base = base[(base.index.hour >= t.ora_inizio) & (base.index.hour < t.ora_fine)]
    quando = base.index + passo
    fine = base.index.normalize() + pd.Timedelta(hours=t.ora_chiusura)
    a = m1.index.searchsorted(quando)
    b = m1.index.searchsorted(fine)
    ok = (b - a) >= 2
    if sane is not None:
        ok &= base.index.normalize().isin(sane)
    return pd.DataFrame({"time": quando[ok], "entry": base.close.values[ok],
                         "anno": base.index.year[ok]})


def placebo(m1, percorsi, veri: pd.DataFrame, gestione, costo, sane=None, t=T):
    """R/op delle serie placebo e il loro dettaglio per serie e anno."""
    cand = candidati_placebo(m1, sane, t)
    rng = np.random.default_rng(SEME)
    per_anno = {a: g for a, g in cand.groupby("anno")}
    rischi = {a: g.rischio.values for a, g in veri.groupby("anno")}
    conta = veri.groupby("anno").size()
    righe, rop = [], []
    for s in range(N_PLACEBO):
        tot_r, tot_n = 0.0, 0
        for anno, n in conta.items():
            c = per_anno[anno]
            pick = rng.choice(len(c), size=min(n, len(c)), replace=False)
            lati = rng.choice((1, -1), size=len(pick))
            ks = rng.choice(rischi[anno], size=len(pick), replace=True)
            r_anno, n_anno = 0.0, 0
            for j, segno, k in zip(pick, lati, ks):
                t_in = c.time.iat[j]
                x, _ = percorsi.esito(t_in, int(segno), float(c.entry.iat[j]),
                                      float(k), gestione)
                if x is None:
                    continue
                r_anno += x - costo(anno) / k
                n_anno += 1
            righe.append({"tipo": "placebo", "gestione": PRIMARIA, "serie": s,
                          "anno": int(anno), "n": n_anno, "R": r_anno})
            tot_r += r_anno
            tot_n += n_anno
        rop.append(tot_r / tot_n if tot_n else np.nan)
    return np.array(rop), pd.DataFrame(righe)


# --------------------------------------------------------------------------
def picco_ram_mb() -> float:
    """Picco del working set del processo (Windows), in MB; NaN altrove."""
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        k = ctypes.WinDLL("kernel32")
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC),
                                              wintypes.DWORD]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        if not k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(pmc),
                                         pmc.cb):
            return float("nan")
        return pmc.PeakWorkingSetSize / 2**20
    except Exception:
        return float("nan")


def main():
    t0 = time.time()
    if len(sys.argv) not in (2, 4):
        raise SystemExit(__doc__)
    simbolo = sys.argv[1].upper()
    a_mano = len(sys.argv) == 4
    if a_mano:
        anni = list(range(int(sys.argv[2]), int(sys.argv[3]) + 1))
    elif simbolo == "XAUUSD":
        fs = glob.glob(os.path.join(ROOT, "data", "XAUUSD_M1", "XAUUSD_M1_*.parquet"))
        anni = sorted(int(os.path.basename(f)[10:14]) for f in fs)
    else:
        anni = anni_indice(simbolo)
    pd.set_option("display.width", 200)

    m1, qual = carica(simbolo, anni)
    anni = sorted(set(m1.index.year))
    f_calc, anni_f = fattore(simbolo, m1, anni)
    # protocollo, controllo della pipeline: sull'oro f = 1
    f = 1.0 if simbolo == "XAUUSD" else f_calc
    print(f"{simbolo} {anni[0]}-{anni[-1]}  f = {f:.6f}  (calcolato {f_calc:.6f}: "
          f"mediana ATR14 D1 {anni_f[0]}-{anni_f[-1]} = {MEDIANA_ATR / f_calc:.4f})"
          + ("" if len(anni_f) == 5 else f"  ATTENZIONE: solo anni {anni_f}"))
    if qual is None:
        spread = {a: SPREAD.get(a, SPREAD_ORO_VECCHI) for a in anni}
        sane, n_sane = None, None
        print("spread (verifica_bot.SPREAD, 0,40 prima del 2020; filtro di qualita' "
              "non applicato, niente ASK): "
              + "  ".join(f"{a % 100:02d}:{v:.3f}" for a, v in spread.items()))
    else:
        spread = {a: qual[a][1] * f for a in anni}
        n_sane = {a: len(qual[a][0]) for a in anni}
        sane = pd.DatetimeIndex(np.concatenate([qual[a][0].values for a in anni])
                                ).tz_localize("UTC")
        print("spread x f (mediana ASK-BID 7-21 UTC, giornate sane) e giornate "
              "sane/con dati per anno:")
        print("  " + "  ".join(f"{a % 100:02d}:{spread[a]:.3f}" for a in anni))
        print("  " + "  ".join(f"{a % 100:02d}:{n_sane[a]}/{qual[a][2]}"
                               + ("*" if n_sane[a] < MIN_GIORNI_SANI else "")
                               for a in anni)
              + f"   (* < {MIN_GIORNI_SANI} sane: fuori dal criterio anni+)")
    if f != 1.0:
        for c in ("open", "high", "low", "close"):
            m1[c] = m1[c] * f

    ops = filtra(genera(m1, T, mediana_atr=MEDIANA_ATR))
    for o in ops:                    # i percorsi servono solo a genera
        o.pop("fav", None)
        o.pop("sfav", None)
    if sane is not None:             # Emendamento 1: nessuna apertura nei giorni non sani
        tot = len(ops)
        ops = [o for o in ops if pd.Timestamp(o["time"]).normalize() in sane]
        print(f"segnali in giornate non sane scartati: {tot - len(ops)} su {tot}")
    gc.collect()
    percorsi = Percorsi(m1)
    costo = spread.__getitem__

    righe, tab, veri_b = [], [], None
    for nome, g in zip(NOMI, BOT):
        det = []
        R, date, anni_op = valuta(ops, percorsi, g, costo, dettaglio=det)
        mis = misure(R, date, anni_op)
        tab.append({"gestione": nome, "op": mis["op"], "R tot": mis["R"],
                    "R/op": mis["R/op"], "vinte%": mis["vinte%"],
                    "DD R": mis["DD R"], "anni+": mis["anni+"]})
        d = pd.DataFrame(det)
        d["R"] = R
        d["tipo"], d["gestione"], d["serie"], d["n"] = "vero", nome, -1, 1
        righe.append(d)
        if nome == PRIMARIA:
            veri_b = d
    print("\n" + pd.DataFrame(tab).set_index("gestione").round(3).to_string())

    pa = veri_b.groupby("anno").R.agg(op="size", R="sum", Rop="mean",
                                      vinte=lambda x: (x > 0).mean() * 100)
    pa = pa.rename(columns={"Rop": "R/op", "vinte": "vinte%"})
    pa.insert(0, "spread", [spread[a] for a in pa.index])
    if n_sane is not None:
        pa["gg sane"] = [n_sane[a] for a in pa.index]
    pa["conta"] = True if n_sane is None else [n_sane[a] >= MIN_GIORNI_SANI
                                               for a in pa.index]
    print(f"\nGestione {PRIMARIA} per anno (spread in prezzo riscalato):")
    print((pa.drop(columns="conta") if n_sane is None else pa).round(3).to_string())

    gest_b = BOT[NOMI.index(PRIMARIA)]
    rop_p, det_p = placebo(m1, percorsi, veri_b, gest_b, costo, sane)
    reale = float(veri_b.R.mean())
    p = float(np.mean(rop_p >= reale))
    print(f"\nPlacebo {N_PLACEBO} serie, gestione {PRIMARIA}: R/op mediana "
          f"{np.nanmedian(rop_p):+.3f} (5%-95%: {np.nanpercentile(rop_p, 5):+.3f}"
          f" / {np.nanpercentile(rop_p, 95):+.3f})  reale {reale:+.3f}  p = {p:.3f}")

    # criterio di successo registrato (+ Emendamento 1: anni con < 100
    # giornate sane fuori dal conteggio degli anni positivi)
    validi = pa[(pa.op >= 10) & pa.conta]
    pos = int((validi.R > 0).sum())
    c1, c2, c3 = reale > 0, p < 0.05, 3 * pos >= 2 * len(validi) and len(validi) > 0
    esito = "PASSA" if (c1 and c2 and c3) else "NON PASSA"
    print(f"\nVERDETTO {simbolo}: {esito}  [R/op>0: {'si' if c1 else 'no'} "
          f"({reale:+.3f}) | p<0,05: {'si' if c2 else 'no'} ({p:.3f}) | "
          f"anni+ >= 2/3 degli anni con >=10 op"
          + ("" if qual is None else f" e >={MIN_GIORNI_SANI} gg sane")
          + f": {'si' if c3 else 'no'} ({pos}/{len(validi)})]")

    out = pd.concat(righe + [det_p], ignore_index=True)
    out["simbolo"], out["f"] = simbolo, f
    out["spread"] = out.anno.map(spread)
    nome_f = f"trasferimento_{simbolo}" + (f"_{anni[0]}-{anni[-1]}" if a_mano else "")
    dest = os.path.join(ROOT, "docs", "studies", "dati", nome_f + ".parquet")
    out.to_parquet(dest, index=False)
    print(f"[dettaglio] {os.path.relpath(dest, ROOT)}  "
          f"[tempo] {time.time() - t0:.0f} s  [picco RAM] {picco_ram_mb():.0f} MB",
          file=sys.stderr)


if __name__ == "__main__":
    main()
