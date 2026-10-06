#!/usr/bin/env python3
"""La B sul primo fuori campione vero: dal 07/07/2026 in poi.

Registrazione: docs/b-fuori-campione-2026-registrazione.md (con l'emendamento
1: dati MT5). Archivio Dukascopy fino al 06/07/2026, poi M1 dal terminale MT5
letto come in app/server.py (ora del server riportata a UTC). Operazioni e
gestione B identiche a analisi_b_18anni.py / verifica_bot.py.

Uso: python trading/scripts/run_b_fuori_campione.py      (MT5 aperto)
     FONTE=dukascopy python ...                            (archivio gia' esteso)
Scrive docs/studies/dati/b_fuori_campione_2026.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(QUI, "..", ".."))
sys.path.insert(0, os.path.join(QUI, ".."))
sys.path.insert(0, QUI)
sys.path.insert(0, os.path.join(ROOT, "app"))

from framework.data import load_m1                                     # noqa: E402
from framework.segnali import genera                                   # noqa: E402
from framework.taratura import UFFICIALE as T                          # noqa: E402
from verifica_bot import BOT, MEDIANA_ATR, SPREAD, Percorsi, filtra    # noqa: E402

INIZIO = pd.Timestamp(os.environ.get("INIZIO", "2026-07-07"), tz="UTC")
FONTE = os.environ.get("FONTE", "mt5")
SPEGNI = 15.0
SWAP_LONG, SWAP_SHORT = -0.715, 0.325   # $ a notte, mercoledi' x3, rollover 21 UTC
STORICO = os.path.join(ROOT, "docs", "studies", "dati", "b_operazioni_2009_2026.parquet")


def serie_m1() -> tuple[pd.DataFrame, str]:
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    if FONTE != "mt5":
        return m1, "Dukascopy"
    import server                                                     # app/server.py
    simbolo, vivo = server.leggi_mt5(server.BARRE_MT5)
    oggi = pd.Timestamp.now("UTC").normalize()
    vivo = vivo[(vivo.index >= INIZIO) & (vivo.index < oggi)]
    if vivo.empty or vivo.index[0] > INIZIO + pd.Timedelta(days=3):
        sys.exit(f"STOP: i dati MT5 non coprono l'inizio del periodo ({vivo.index[:1]})")
    vecchio = m1[m1.index < INIZIO][["open", "high", "low", "close", "volume"]]
    unito = pd.concat([vecchio, vivo[["open", "high", "low", "close", "volume"]]]).sort_index()
    return unito[~unito.index.duplicated(keep="last")], f"MT5 {simbolo}"


def uscita_e_notti(percorsi: Percorsi, t_in, segno, e, k) -> tuple[float, str, pd.Timestamp, int, bool]:
    """Come Percorsi.esito per la B, ma con istante d'uscita, notti di swap e
    'aperta' se i dati finiscono prima dell'uscita."""
    _, rr, pareggio, trail, oltre, soglia = next(g for g in BOT if g[0].startswith("B"))
    a = int(np.searchsorted(percorsi.idx, t_in.value))
    # come verifica_bot: al massimo GIORNI_MAX giorni, poi "scadenza"
    b30 = int(np.searchsorted(percorsi.idx, (t_in + pd.Timedelta(days=30)).value))
    b = min(b30, len(percorsi.idx))
    o_, h_, l_, c_ = percorsi.o[a:b], percorsi.h[a:b], percorsi.l[a:b], percorsi.c[a:b]
    if segno == 1:
        apri, fav, sfav, chiu = (o_ - e) / k, (h_ - e) / k, (e - l_) / k, (c_ - e) / k
    else:
        apri, fav, sfav, chiu = (e - o_) / k, (e - l_) / k, (h_ - e) / k, (e - c_) / k
    buchi = percorsi.buco[a:b - 1]
    livello, mfe, uscita, perche, i = -1.0, 0.0, None, None, 0
    for i in range(len(fav)):                       # stessa logica di verifica_bot.cammina
        if apri[i] <= livello:
            uscita, perche = apri[i], "gap"; break
        if apri[i] >= rr:
            uscita, perche = apri[i], "gap+"; break
        if sfav[i] >= -livello:
            uscita = livello
            perche = "stop" if livello <= -1 else "pareggio" if livello == 0 else "protetto"; break
        if fav[i] >= rr:
            uscita, perche = float(rr), "obiettivo"; break
        mfe = max(mfe, fav[i])
        if trail is not None and mfe >= trail[0]:
            livello = max(livello, mfe - trail[1])
        if i < len(buchi) and buchi[i] and chiu[i] < soglia:
            uscita, perche = chiu[i], "chiusa il venerdi'"; break
    aperta = uscita is None and b == len(percorsi.idx)
    if uscita is None:
        uscita, perche = max(chiu[-1], livello), ("aperta" if aperta else "scadenza")
    t_out = pd.Timestamp(percorsi.idx[a + i], tz="UTC")
    # notti: rollover alle 21 UTC attraversati, il mercoledi' vale tre
    notti = 0
    r = t_in.normalize() + pd.Timedelta(hours=21)
    if r <= t_in:
        r += pd.Timedelta(days=1)
    while r < t_out:
        if r.dayofweek < 5:
            notti += 3 if r.dayofweek == 2 else 1
        r += pd.Timedelta(days=1)
    return float(uscita), perche, t_out, notti, aperta


def finestre(r: np.ndarray, n: int) -> np.ndarray:
    c = np.concatenate([[0.0], np.cumsum(r)])
    return c[n:] - c[:-n]


def densita(x: float, campione: np.ndarray) -> float:
    h = 1.06 * campione.std(ddof=1) * len(campione) ** -0.2
    return float(np.exp(-0.5 * ((x - campione) / h) ** 2).mean() / (h * np.sqrt(2 * np.pi)))


def main():
    m1, fonte = serie_m1()
    ops = [o for o in filtra(genera(m1, T, mediana_atr=MEDIANA_ATR))
           if pd.Timestamp(o["time"]).tz_convert("UTC") >= INIZIO]
    percorsi = Percorsi(m1)
    fine = m1.index[-1]
    del m1
    righe = []
    for o in ops:
        t_in = pd.Timestamp(o["time"]).tz_convert("UTC")
        segno, k = (1 if o["lato"] == "long" else -1), float(o["rischio"])
        x, perche, t_out, notti, aperta = uscita_e_notti(percorsi, t_in, segno, o["entry"], k)
        costo = SPREAD.get(o["anno"], 0.40)
        swap = notti * (SWAP_LONG if segno == 1 else SWAP_SHORT)
        righe.append({"time": t_in, "lato": o["lato"], "entry": o["entry"], "rischio": k,
                      "uscita": perche, "t_uscita": t_out, "notti": notti, "aperta": aperta,
                      "R": x - costo / k, "R_swap": x - costo / k + swap / k})
    d = pd.DataFrame(righe)
    d.to_parquet(os.path.join(ROOT, "docs", "studies", "dati", "b_fuori_campione_2026.parquet"), index=False)

    pd.set_option("display.width", 200)
    chiuse = d[~d.aperta] if len(d) else d
    print(f"fonte {fonte}; periodo {INIZIO:%d/%m/%Y} -> {fine:%d/%m/%Y %H:%M} UTC")
    print(f"operazioni {len(d)} (chiuse {len(chiuse)}, ancora aperte {int(d.aperta.sum()) if len(d) else 0})")
    if chiuse.empty:
        return
    print(chiuse.assign(t=chiuse.time.dt.strftime("%d/%m %H:%M"))[
        ["t", "lato", "uscita", "notti", "R", "R_swap"]].round(2).to_string(index=False))
    n, somma, somma_swap = len(chiuse), chiuse.R.sum(), chiuse.R_swap.sum()
    print(f"\nsomma {somma:+.2f} R ({somma / n:+.3f} R/op), con lo swap {somma_swap:+.2f} R; "
          f"vinte {(chiuse.R > 0).mean():.0%}")
    cum = chiuse.R.cumsum()
    calo = float((np.maximum.accumulate(np.concatenate([[0.0], cum])) - np.concatenate([[0.0], cum])).max())
    print(f"calo massimo dal {INIZIO:%d/%m}: {calo:.2f} R (spegnimento a {SPEGNI:.0f} R: "
          f"{'SCATTA' if calo >= SPEGNI else 'non scatta'})")

    s = pd.read_parquet(STORICO)
    s["time"] = pd.to_datetime(s["time"], utc=True)
    s = s.sort_values("time")
    buono = finestre(s[s.time.dt.year >= 2020].R.values, n)
    cattivo = finestre(s[s.time.dt.year <= 2019].R.values, n)
    p_b, p_c = (buono <= somma).mean() * 100, (cattivo <= somma).mean() * 100
    rv = densita(somma, buono) / max(densita(somma, cattivo), 1e-300)
    print(f"\nfinestre di {n} operazioni consecutive: percentile {p_b:.0f} nel 2020-2026 "
          f"(mediana {np.median(buono):+.1f} R), {p_c:.0f} nel 2009-2019 (mediana {np.median(cattivo):+.1f} R)")
    print(f"rapporto di verosimiglianza 2020-2026 / 2009-2019: {rv:.2f}")
    allarme = p_b < 5 or calo >= SPEGNI
    coerente = 5 <= p_b <= 95 and rv > 1
    print("LETTURA: " + ("ALLARME" if allarme else "coerente col regime 2020-2026" if coerente
                         else "ne' allarme ne' coerenza piena"))


if __name__ == "__main__":
    main()
