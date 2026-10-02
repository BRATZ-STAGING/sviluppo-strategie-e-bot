"""Trasferimento su altri mercati (``scripts/run_trasferimento.py``).

Il protocollo (``docs/trasferimento-indici-registrazione.md``) si regge su
un'affermazione: moltiplicare i prezzi per una costante e le soglie in dollari
per la stessa costante non cambia nulla in R. Qui la si verifica sul
generatore e sulla gestione B, con un fattore potenza di due (aritmetica
esatta in virgola mobile) e con uno qualunque.
"""
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(QUI, "..", "scripts"))

from framework.segnali import genera                     # noqa: E402
from framework.taratura import UFFICIALE as T            # noqa: E402

import run_trasferimento as RT                           # noqa: E402
from verifica_bot import BOT, MEDIANA_ATR, Percorsi      # noqa: E402

DATI_XAU = os.path.join(QUI, "..", "..", "data", "XAUUSD_M1")


def serie_sintetica(giorni=60, seme=4):
    """M1 a passeggiata casuale con regimi di tendenza, solo giorni feriali."""
    rng = np.random.default_rng(seme)
    gg = pd.bdate_range("2024-03-04", periods=giorni, tz="UTC")
    idx = pd.DatetimeIndex(np.concatenate(
        [(g + pd.to_timedelta(np.arange(1380), unit="min")).values for g in gg]),
        tz="UTC")
    n = len(idx)
    deriva = np.repeat(rng.choice([-0.03, 0.03], size=n // 8000 + 1), 8000)[:n]
    close = 2000 + np.cumsum(deriva + rng.normal(0, 0.5, n))
    open_ = np.concatenate([[close[0]], close[:-1]])
    alto = np.maximum(open_, close) + rng.exponential(0.15, n)
    basso = np.minimum(open_, close) - rng.exponential(0.15, n)
    m1 = pd.DataFrame({"open": open_, "high": alto, "low": basso, "close": close,
                       "volume": rng.integers(1, 50, n).astype(float)}, index=idx)
    m1.index.name = "timestamp"
    return m1


def scala(m1, c):
    out = m1.copy()
    for k in ("open", "high", "low", "close"):
        out[k] = out[k] * c
    return out


def taratura_scalata(c):
    return replace(T, spread=T.spread * c, buffer=T.buffer * c,
                   impulso_min=T.impulso_min * c, rischio_min=T.rischio_min * c,
                   rischio_max=T.rischio_max * c)


@pytest.mark.parametrize("c", [4.0, 0.0371])
@pytest.mark.parametrize("sempre", [False, True])
def test_invarianza_in_R_alla_scala(c, sempre):
    m1 = serie_sintetica()
    a = genera(m1, T, mediana_atr=MEDIANA_ATR, sempre_scalate=sempre)
    m1c = scala(m1, c)
    b = genera(m1c, taratura_scalata(c), mediana_atr=MEDIANA_ATR * c,
               sempre_scalate=sempre)
    assert len(a) >= 5, "la serie sintetica deve produrre segnali"
    assert [o["time"] for o in a] == [o["time"] for o in b]
    assert [o["lato"] for o in a] == [o["lato"] for o in b]
    np.testing.assert_allclose([o["rischio"] * c for o in a],
                               [o["rischio"] for o in b], rtol=1e-9)
    np.testing.assert_allclose([o["costo"] for o in a], [o["costo"] for o in b],
                               rtol=1e-9)
    # gestione B (trail, oltre la giornata): stesso esito in R
    gb = BOT[2]
    pa, pb = Percorsi(m1), Percorsi(m1c)
    for oa, ob in zip(a, b):
        t_in = pd.Timestamp(oa["time"])
        s = 1 if oa["lato"] == "long" else -1
        xa, ma = pa.esito(t_in, s, oa["entry"], oa["rischio"], gb)
        xb, mb = pb.esito(t_in, s, ob["entry"], ob["rischio"], gb)
        assert ma == mb
        assert xa == pytest.approx(xb, abs=1e-9)


def test_finestra_breve_uguale_alla_intera(monkeypatch):
    """La scorciatoia della finestra breve non cambia nessun esito."""
    import verifica_bot as VB
    m1 = serie_sintetica()
    ops = genera(m1, T, mediana_atr=MEDIANA_ATR)
    p = Percorsi(m1)
    breve = [[p.esito(pd.Timestamp(o["time"]), 1 if o["lato"] == "long" else -1,
                      o["entry"], o["rischio"], g) for o in ops] for g in BOT]
    monkeypatch.setattr(VB, "FINESTRA_BREVE", 10**9)
    intera = [[p.esito(pd.Timestamp(o["time"]), 1 if o["lato"] == "long" else -1,
                       o["entry"], o["rischio"], g) for o in ops] for g in BOT]
    assert breve == intera


def test_qualita_giornata_sana_e_spread():
    """Emendamento 1: copertura >= 95% degli 840 minuti e ASK > BID >= 90%."""
    g1, g2, g3 = (pd.Timestamp(x, tz="UTC") for x in
                  ("2024-03-04", "2024-03-05", "2024-03-06"))
    minuti = pd.to_timedelta(np.arange(7 * 60, 21 * 60), unit="min")
    idx = pd.DatetimeIndex(np.concatenate([(g + minuti).values for g in (g1, g2, g3)]),
                           tz="UTC")
    bid = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0,
                        "volume": 1.0}, index=idx)
    ask = bid.copy()
    ask["close"] = 100.5
    ask.loc[ask.index.normalize() == g2, "close"] = 100.0     # ASK == BID: non sana
    # g3: mancano 60 minuti su 840 (copertura 0,929): non sana
    tolti = (idx.normalize() == g3) & (idx.hour == 10)
    bid, ask = bid[~tolti], ask[~tolti]
    sane, spread, n = RT.qualita_anno(bid, ask)
    assert list(sane) == [g1]
    assert spread == pytest.approx(0.5)
    assert n == 3
    vuote, sp, _ = RT.qualita_anno(bid, None)
    assert len(vuote) == 0 and np.isnan(sp)


@pytest.mark.skipif(not os.path.isdir(DATI_XAU), reason="mancano i dati XAUUSD M1")
def test_fattore_oro_vale_uno():
    m1 = RT.carica_bid("XAUUSD", list(range(2020, 2025)))
    f, anni = RT.fattore("XAUUSD", m1, list(range(2020, 2025)))
    assert anni == [2020, 2021, 2022, 2023, 2024]
    assert f == pytest.approx(1.0, abs=1e-5)
