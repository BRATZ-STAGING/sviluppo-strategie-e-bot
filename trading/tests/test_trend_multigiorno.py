"""Trend multi-giorno (``scripts/run_trend_multigiorno.py``): casi costruiti a mano.

Bloccano le regole del protocollo registrato: entrata all'apertura del giorno
dopo la decisione, stop in gap all'apertura, stop prevalente nella seduta,
ATR classico, conteggio delle notti di swap, assenza di lookahead.
"""
import os
import sys

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(QUI, "..", "scripts"))

import run_trend_multigiorno as T  # noqa: E402


def d1(o, h, l, c, start="2020-01-06"):
    idx = pd.bdate_range(start, periods=len(c), tz="UTC")
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c},
                        index=idx, dtype=float)


def piatto_con_breakout(n=90, k=70):
    """Sedute piatte (100 +- 1) e una chiusura a 105 nella seduta k."""
    o = np.full(n, 100.0)
    h = np.full(n, 101.0)
    lo = np.full(n, 99.0)
    c = np.full(n, 100.0)
    h[k], c[k] = 106.0, 105.0
    o[k + 1:], h[k + 1:], lo[k + 1:], c[k + 1:] = 105.0, 106.0, 104.0, 105.0
    return d1(o, h, lo, c)


def test_atr_true_range_classico_con_gap():
    o = [100.0] * 21 + [110.0]
    h = [101.0] * 21 + [111.0]
    lo = [99.0] * 21 + [109.0]
    c = [100.0] * 21 + [110.0]
    a = T.atr20(d1(o, h, lo, c))
    assert np.isnan(a.iloc[18]) and a.iloc[19] == 2.0
    # ultimo TR = |111 - 100| = 11 (gap), non 111 - 109 = 2
    assert np.isclose(a.iloc[21], (19 * 2.0 + 11.0) / 20)


def test_donchian_entra_long_il_giorno_dopo_il_breakout():
    df = piatto_con_breakout()
    ops = T.simula_f2(df)
    prima = ops.iloc[0]
    assert prima["direzione"] == 1
    assert prima["data_decisione"] == df.index[70]
    assert prima["data_entrata"] == df.index[71]
    assert prima["prezzo_entrata"] == df["open"].iloc[71]
    r = 2 * T.atr20(df).iloc[70]
    assert np.isclose(prima["R_dollari"], r)
    assert np.isclose(prima["stop"], 105.0 - r)


def test_stop_in_gap_eseguito_all_apertura():
    df = piatto_con_breakout()
    r = 2 * T.atr20(df).iloc[70]
    stop = 105.0 - r
    # seduta 73 apre sotto lo stop
    df.iloc[73] = [stop - 5, stop - 4, stop - 8, stop - 6]
    ops = T.simula_f2(df)
    op = ops.iloc[0]
    assert op["motivo"] == "stop" and op["data_uscita"] == df.index[73]
    assert op["prezzo_uscita"] == stop - 5


def test_stop_intraday_al_livello_e_prevale_sul_segnale_di_chiusura():
    df = piatto_con_breakout()
    r = 2 * T.atr20(df).iloc[70]
    stop = 105.0 - r
    # apre sopra lo stop, lo tocca, chiude sotto il minimo delle 20 sedute:
    # vale lo stop nella stessa seduta, non l'uscita del giorno dopo
    df.iloc[73] = [104.0, 104.5, stop - 3, 98.0]
    ops = T.simula_f2(df)
    op = ops.iloc[0]
    assert op["motivo"] == "stop" and op["data_uscita"] == df.index[73]
    assert np.isclose(op["prezzo_uscita"], stop)


def test_uscita_donchian_20_all_apertura_successiva():
    df = piatto_con_breakout(n=110)
    # chiusura sotto il minimo delle 20 sedute (104) senza toccare lo stop
    r = 2 * T.atr20(df).iloc[70]
    assert 105.0 - r < 103.0
    df.iloc[100] = [105.0, 105.0, 103.5, 103.6]
    ops = T.simula_f2(df)
    op = ops.iloc[0]
    assert op["motivo"] == "segnale"
    assert op["data_uscita"] == df.index[101]
    assert op["prezzo_uscita"] == df["open"].iloc[101]


def test_notti_di_swap_mercoledi_triplo_weekend_una():
    df = d1([T.PREZZO_RIF] * 10, [T.PREZZO_RIF] * 10, [T.PREZZO_RIF] * 10,
            [T.PREZZO_RIF] * 10, start="2024-01-01")       # lunedi'
    i = df.index
    ops = pd.DataFrame([
        dict(data_entrata=i[0], data_uscita=i[3], direzione=1),   # lun->gio
        dict(data_entrata=i[4], data_uscita=i[5], direzione=1),   # ven->lun
        dict(data_entrata=i[1], data_uscita=i[1], direzione=-1),  # stessa seduta
    ])
    ops["prezzo_entrata"] = ops["prezzo_uscita"] = T.PREZZO_RIF
    ops["R_dollari"] = 10.0
    out = T.applica_costi(ops, df)
    assert list(out["notti"]) == [5.0, 1.0, 0.0]
    assert np.isclose(out["swap_R"].iloc[0], 5 * T.SWAP_LONG / 10.0)
    assert np.isclose(out["swap_R"].iloc[1], T.SWAP_LONG / 10.0)
    # spread 2024 dal dizionario reale
    assert np.isclose(out["spread_dollari"].iloc[0], T.SPREAD[2024])


def test_tsmom_entra_alla_prima_apertura_del_mese_dopo():
    n = 320
    c = 100.0 + np.arange(n) * 0.1                         # sempre in salita
    df = d1(c, c + 0.5, c - 0.5, c, start="2020-01-01")
    ops = T.simula_f1(df)
    fm = [i for i in T.fine_mese(df) if i >= 252]
    assert (ops["direzione"] == 1).all()
    assert ops.iloc[0]["data_decisione"] == df.index[fm[0]]
    assert ops.iloc[0]["data_entrata"] == df.index[fm[0] + 1]
    assert df.index[fm[0] + 1].month != df.index[fm[0]].month
    # se il segno non cambia i mesi restano operazioni separate
    assert len(ops) == len(fm)


def test_nessun_lookahead_futuro_alterato_non_cambia_il_passato():
    rng = np.random.default_rng(1)
    n, D = 1600, 1200
    c = 1000 + np.cumsum(rng.normal(0, 8, n))
    o = np.concatenate([[c[0]], c[:-1]]) + rng.normal(0, 2, n)
    h = np.maximum(o, c) + rng.uniform(0, 6, n)
    lo = np.minimum(o, c) - rng.uniform(0, 6, n)
    df = d1(o, h, lo, c, start="2015-01-01")
    alt = df.copy()
    sc = 1 + rng.normal(0, 0.05, n - D - 1).cumsum()[:, None]
    alt.iloc[D + 1:] = alt.iloc[D + 1:].to_numpy() * np.abs(sc)
    alt["high"] = alt[["open", "high", "low", "close"]].max(axis=1)
    alt["low"] = alt[["open", "high", "low", "close"]].min(axis=1)
    lim = df.index[D]
    assert T.atr20(df).iloc[:D + 1].equals(T.atr20(alt).iloc[:D + 1])
    for f in (T.simula_f1, T.simula_f2, T.simula_f3):
        a, b = f(df), f(alt)
        a = a[a["data_uscita"] <= lim].reset_index(drop=True)
        b = b[b["data_uscita"] <= lim].reset_index(drop=True)
        assert len(a) > 0
        pd.testing.assert_frame_equal(a, b)
    # anche la decisione presa alla chiusura D (eseguita in D+1) e' identica
    for f in (T.segnali_donchian, T.segnali_medie):
        for x, y in zip(f(df), f(alt)):
            assert np.array_equal(x[:D + 1], y[:D + 1])


def test_placebo_riproducibile_e_stessi_costi():
    df = piatto_con_breakout(n=110)
    ops = T.applica_costi(T.simula_f2(df), df)
    p1, p2 = T.placebo(ops, n=50), T.placebo(ops, n=50)
    assert np.array_equal(p1, p2)
    # con direzione tutta long il placebo coincide col calcolo reale
    tutte_long = ops[ops["direzione"] == 1]
    g = tutte_long["g_long_R"] - tutte_long["spread_R"] + \
        T.SWAP_LONG * tutte_long["fattore_swap"] / tutte_long["R_dollari"]
    assert np.allclose(g, tutte_long["netto_R"])


def test_verdetto_bonferroni():
    m = dict(R_tot=10.0, R_op=0.1, anni_ok=True, h1=1.0, h2=1.0)
    assert T.verdetto(m, 0.01) == "PASSA"
    assert T.verdetto(m, 0.03).startswith("PASSA al limite")
    assert T.verdetto(m, 0.05).startswith("NON PASSA")
