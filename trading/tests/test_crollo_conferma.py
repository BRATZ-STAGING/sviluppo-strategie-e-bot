"""Crollo -> conferma -> entrata (docs/crollo-conferma-registrazione.md).

Serie sintetiche costruite a mano: entrata C1 alla barra giusta, frattale
invisibile prima di 2 barre, stop in gap all'apertura, short = specchio del
long, nessun lookahead (troncare la serie non cambia i segnali passati).
"""
import numpy as np
import pytest

from framework import crollo_conferma as cc


def barre_a_mano(ohlc, atr=10.0, passo=60):
    a = np.array(ohlc, dtype=float)
    o, h, l, c = a.T
    n = len(o)
    t = np.arange(n, dtype=np.int64) * passo + 10 * 1440
    return cc.Barre(t=t, fine=t + passo, o=o, h=h, l=l, c=c, vwap=np.full(n, np.nan),
                    ema=cc.ema(c), atr=np.full(n, atr), atr_ap=np.full(n, atr),
                    giorno=np.zeros(n, np.int64), i5=np.arange(n), i5_fine=np.arange(n))


# crollo da 110 (barra 2), fondo 97,5 (barra 8), massimo relativo 107,5 (barra 5)
CROLLO = [
    (100, 101, 99, 100),        # 0
    (100, 105, 99.5, 104),      # 1
    (104, 110, 103, 109),       # 2  H
    (107, 107, 103, 104),       # 3
    (104, 104.5, 100.5, 101),   # 4
    (101, 107.5, 100.8, 105),   # 5  frattale alto (noto alla chiusura di 7)
    (105, 105.5, 101, 102),     # 6
    (102, 102.5, 98, 99),       # 7  110 - 98 = 12 >= 1 x ATR: crollo
    (99, 101, 97.5, 100),       # 8  nuovo minimo L
    (100, 104, 99.5, 103),      # 9
    (103, 106, 102.5, 105),     # 10 chiusura sopra il 50% (103,75): C3c
    (105, 108.5, 104.5, 108),   # 11 chiusura 108 > 107,5: C1 (rottura di struttura)
    (108, 109, 107, 108.5),     # 12 entrata all'apertura
    (108.5, 109, 107.5, 108),   # 13
]


def test_crollo_con_bos_entra_alla_barra_giusta():
    B = barre_a_mano(CROLLO)
    s = cc.segnali(B, 1.0, "C1", "intraday")
    assert len(s) == 1
    s = s[0]
    assert (s.inizio, s.conferma, s.iH, s.iL) == (7, 11, 2, 8)
    assert s.H == 110 and s.L == 97.5
    # entrata all'apertura della barra dopo la conferma, stop L - 0,1 ATR
    m5 = (B.t, B.o, B.h, B.l, B.c)
    op = cc.operazioni(cc.segnali(B, 1.0, "C1", "intraday"), B, m5, "intraday", 1, 0.46)
    assert op["e"][0] == 12 and op["ent"][0] == 108
    assert op["R"][0] == pytest.approx(108 - 96.5)
    # stessa serie, conferma C3c (recupero del 50%) alla barra 10
    assert [x.conferma for x in cc.segnali(B, 1.0, "C3c", "intraday")] == [10]
    # senza conferma: entrata alla barra dopo il fronte del crollo
    r = cc.segnali(B, 1.0, "NESSUNA", "intraday")
    assert [(x.conferma, x.L) for x in r] == [(7, 98)]


def test_crollo_scaduto_non_entra():
    # la stessa rottura, ma 9 ore dopo il minimo (finestra 8 ore): nessuna entrata
    B = barre_a_mano(CROLLO, passo=180)
    assert cc.segnali(B, 1.0, "C1", "intraday") == []


def test_frattale_invisibile_prima_di_due_barre():
    h = np.array([1, 2, 5, 3, 2, 1, 1.5, 1], float)
    l = h - 0.5
    fh, fl = cc.frattali(h, l)
    assert fh.tolist() == [False, False, True, False, False, False, False, False]
    u = cc.ultimo_noto(fh)
    assert u[2] == -1 and u[3] == -1          # all'estremo e una barra dopo: ignoto
    assert u[4] == 2 and u[7] == 2            # noto alla chiusura di f + 2
    # un frattale che "si forma" solo con barre future non deve cambiare il passato
    fh2, _ = cc.frattali(h[:4], l[:4])
    assert not fh2.any()


def test_stop_in_gap_si_esegue_all_apertura():
    # long entrato a 100, stop 98: la seconda M5 apre a 95 (sotto lo stop)
    o = np.array([100, 95, 96.0])
    h = np.array([101, 96, 97.0])
    l = np.array([99, 94, 95.0])
    c = np.array([100.5, 95.5, 96.5])
    res = cc.gestisci(o, h, l, c, 0, 2, 1, 98.0, [102.0])
    assert res[0][:3] == (1, 95.0, 0)
    assert cc.gestisci_barra_per_barra(o, h, l, c, 0, 2, 1, 98.0, 102.0) == (1, 95.0, 0)
    # stop e obiettivo nella stessa candela: prevale lo stop
    o2 = np.array([100, 100.0])
    h2 = np.array([100.5, 103.0])
    l2 = np.array([99.5, 97.0])
    assert cc.gestisci(o2, h2, l2, o2, 0, 1, 1, 98.0, [102.0])[0] == (1, 98.0, 0)
    # short: apertura sopra lo stop -> uscita all'apertura
    assert cc.gestisci(-o[::1] + 200, -l + 200, -h + 200, -c + 200, 0, 2, -1, 102.0,
                       [98.0])[0] == (1, 105.0, 0)


def test_notti_swap():
    t = lambda s: int(np.datetime64(s, "m").astype(np.int64))
    # lunedi' 20:00 -> martedi' 20:00: una notte; martedi' -> giovedi': 1 + 3
    assert cc.notti_swap(t("2015-03-02T20:00"), t("2015-03-03T20:00")) == 1
    assert cc.notti_swap(t("2015-03-03T20:00"), t("2015-03-05T20:00")) == 4
    # venerdi' 20:00 -> lunedi' 20:00: solo il venerdi'
    assert cc.notti_swap(t("2015-03-06T20:00"), t("2015-03-09T20:00")) == 1
    # alle 21:00 esatte la posizione e' ancora aperta
    assert cc.notti_swap(t("2015-03-02T20:55"), t("2015-03-02T21:00")) == 1
    assert cc.notti_swap(t("2015-03-02T21:00"), t("2015-03-02T23:00")) == 0


# ------------------------------------------------- serie casuale su M5
def m5_casuale(seed=3, n=12000, base=1000.0):
    rng = np.random.default_rng(seed)
    passi = rng.choice([-2, -1, 0, 1, 2], size=n, p=[.1, .25, .3, .25, .1]) * 0.125
    passi += np.where(rng.random(n) < 0.002, rng.choice([-1, 1], n) * 4.0, 0)
    c = base + np.cumsum(passi)
    o = np.r_[base, c[:-1]]
    h = np.maximum(o, c) + rng.integers(0, 3, n) * 0.125
    l = np.minimum(o, c) - rng.integers(0, 3, n) * 0.125
    t = np.datetime64("2015-01-05T00:00", "m").astype(np.int64) + 5 * np.arange(n)
    return t, o, h, l, c


def costruisci(t, o, h, l, c, regola=60):
    giorni = np.unique(t // 1440)
    fine_g = (giorni + 1) * 1440
    atr_f = np.full(len(fine_g), 3.0)
    tp = (h + l + c) / 3
    d = t // 1440
    vw = np.empty(len(t))
    for g in giorni:            # media cumulata del prezzo tipico nel giorno
        m = d == g
        vw[m] = np.cumsum(tp[m]) / np.arange(1, m.sum() + 1)
    return cc.barre_da_m5(t, o, h, l, c, t // regola, regola, vw, fine_g, atr_f), fine_g


@pytest.mark.parametrize("conf", list(cc.CONFERME) + ["NESSUNA"])
def test_short_specchio_del_long(conf):
    t, o, h, l, c = m5_casuale()
    K = 2000.0
    B, fg = costruisci(t, o, h, l, c)
    Bs, _ = costruisci(t, K - o, K - l, K - h, K - c)
    g5 = cc.giorno_di(fg, t)
    for orizz in ("intraday", "swing"):
        k = 1.0 if orizz == "intraday" else 2.0
        sl = cc.segnali(B, k, conf, orizz)
        ss = cc.segnali(cc.specchio(Bs), k, conf, orizz)
        assert [(a.inizio, a.conferma, a.iL) for a in sl] == [(a.inizio, a.conferma, a.iL) for a in ss]
        ol = cc.operazioni(sl, B, (t, o, h, l, c), orizz, 1, 0.46, fg, g5)
        os_ = cc.operazioni(ss, Bs, (t, K - o, K - l, K - h, K - c), orizz, -1, 0.46, fg, g5)
        assert len(ol["e"]) == len(os_["e"])
        np.testing.assert_array_equal(ol["e"], os_["e"])
        np.testing.assert_array_equal(ol["x"], os_["x"])
        np.testing.assert_array_equal(ol["mot"], os_["mot"])
        np.testing.assert_allclose(ol["R"], os_["R"], atol=1e-9)
        gl = (ol["px"] - ol["ent"][:, None]) / ol["R"][:, None]
        gs = -(os_["px"] - os_["ent"][:, None]) / os_["R"][:, None]
        np.testing.assert_allclose(gl, gs, atol=1e-9)


def test_ci_sono_segnali_nella_serie_casuale():
    t, o, h, l, c = m5_casuale()
    B, _ = costruisci(t, o, h, l, c)
    for conf in cc.CONFERME:
        assert len(cc.segnali(B, 1.0, conf, "intraday")) > 0, conf


@pytest.mark.parametrize("conf", list(cc.CONFERME) + ["NESSUNA"])
def test_nessun_lookahead_troncando(conf):
    t, o, h, l, c = m5_casuale(seed=11)
    B, _ = costruisci(t, o, h, l, c)
    full = [(a.inizio, a.conferma, a.L, a.H) for a in cc.segnali(B, 1.0, conf, "intraday")]
    assert full
    for taglio in (len(B.c) // 3, len(B.c) // 2, len(B.c) - 7):
        n5 = B.i5[taglio]
        Bt, _ = costruisci(t[:n5], o[:n5], h[:n5], l[:n5], c[:n5])
        tr = [(a.inizio, a.conferma, a.L, a.H) for a in cc.segnali(Bt, 1.0, conf, "intraday")]
        # i segnali confermati prima del taglio sono identici
        assert [x for x in full if x[1] < taglio] == [x for x in tr if x[1] < taglio]


def test_motore_vettoriale_uguale_al_ciclo():
    t, o, h, l, c = m5_casuale(seed=5)
    rng = np.random.default_rng(1)
    for _ in range(300):
        e = int(rng.integers(0, len(t) - 400))
        lim = e + int(rng.integers(0, 399))
        dz = int(rng.choice([1, -1]))
        R = float(rng.uniform(0.5, 4))
        stop = o[e] - dz * R
        tg = o[e] + dz * R * float(rng.choice([1, 2, 3, -0.5]))
        a = cc.gestisci(o, h, l, c, e, lim, dz, stop, [tg])[0]
        b = cc.gestisci_barra_per_barra(o, h, l, c, e, lim, dz, stop, tg)
        assert a == b


# ------------------------------------------- swing v2: stop S1, S2, S3
# docs/crollo-conferma-swing-v2-registrazione.md (commit bf9a30b)
# stesso crollo; dopo L (barra 8) un minimo crescente 99 (barra 11, noto alla
# chiusura di 13) e un massimo relativo 103,5 (barra 10, noto alla 12)
CROLLO_S2 = CROLLO[:9] + [
    (100, 103, 99.5, 102),      # 9
    (102, 103.5, 100, 101),     # 10 frattale alto 103,5
    (101, 102, 99, 100),        # 11 frattale basso 99 > L
    (100, 103, 100.5, 102.5),   # 12
    (102.5, 105, 101.5, 104.5), # 13 chiusura 104,5 > 103,5: C1; frattale 11 noto
    (104.5, 105, 104, 104.8),   # 14 entrata all'apertura (104,5)
    (104.8, 105.5, 104.2, 105), # 15
]


def test_stop_s2_usa_il_minimo_crescente_noto():
    B = barre_a_mano(CROLLO_S2)
    s = cc.segnali(B, 1.0, "C1", "intraday")
    assert [(x.conferma, x.iL, x.L, x.F) for x in s] == [(13, 8, 97.5, 99.0)]
    m5 = (B.t, B.o, B.h, B.l, B.c)
    r = {st: cc.operazioni(s, B, m5, "intraday", 1, 0.46, stop=st) for st in ("S1", "S2", "S3")}
    assert r["S1"]["stop"][0] == pytest.approx(96.5) and r["S1"]["R"][0] == pytest.approx(8.0)
    assert r["S2"]["stop"][0] == pytest.approx(98.0) and r["S2"]["R"][0] == pytest.approx(6.5)
    assert r["S2"]["fr"][0] == 1 and r["S1"]["fr"][0] == 0
    assert r["S3"]["stop"][0] == pytest.approx(89.5) and r["S3"]["R"][0] == pytest.approx(15.0)
    # obiettivi in R seguono lo stop scelto
    assert r["S2"]["obj"][0, 0] == pytest.approx(104.5 + 6.5)
    # il default resta il protocollo v1
    v1 = cc.operazioni(s, B, m5, "intraday", 1, 0.46)
    assert v1["stop"][0] == r["S1"]["stop"][0]


def test_stop_s2_senza_minimo_crescente_come_s1():
    # serie originale: nessun minimo frattale noto dopo L alla conferma
    B = barre_a_mano(CROLLO)
    s = cc.segnali(B, 1.0, "C1", "intraday")
    assert np.isnan(s[0].F)
    m5 = (B.t, B.o, B.h, B.l, B.c)
    a = cc.operazioni(s, B, m5, "intraday", 1, 0.46, stop="S1")
    b = cc.operazioni(s, B, m5, "intraday", 1, 0.46, stop="S2")
    assert a["stop"][0] == b["stop"][0] == pytest.approx(96.5) and b["fr"][0] == 0


def test_s1_senza_tetto_v1_con_tetto():
    from dataclasses import replace
    B = barre_a_mano(CROLLO)
    s = cc.segnali(B, 1.0, "C1", "intraday")
    Bp = replace(B, atr_ap=np.full(len(B.c), 5.0))     # 1R = 11 > 1,5 x 5
    m5 = (B.t, B.o, B.h, B.l, B.c)
    assert len(cc.operazioni(s, Bp, m5, "intraday", 1, 0.46)["e"]) == 0
    op = cc.operazioni(s, Bp, m5, "intraday", 1, 0.46, stop="S1")
    assert op["R"][0] == pytest.approx(108 - 97.0)
    # resta il filtro sul costo: 1R < 2 x costo si scarta
    assert len(cc.operazioni(s, Bp, m5, "intraday", 1, 6.0, stop="S1")["e"]) == 0
    assert cc.rischio_valido(20, 10, 0.46) is False
    assert cc.rischio_valido(20, 10, 0.46, tetto=False) is True
    with pytest.raises(ValueError):
        cc.operazioni(s, B, m5, "intraday", 1, 0.46, stop="S9")


@pytest.mark.parametrize("stop", ["S1", "S2", "S3"])
@pytest.mark.parametrize("conf", ["C1", "C2", "C4", "C5", "NESSUNA"])
def test_short_specchio_del_long_stop_v2(conf, stop):
    t, o, h, l, c = m5_casuale()
    K = 2000.0
    B, fg = costruisci(t, o, h, l, c)
    Bs, _ = costruisci(t, K - o, K - l, K - h, K - c)
    g5 = cc.giorno_di(fg, t)
    n_fr = 0
    for orizz in ("intraday", "swing"):
        k = 1.0 if orizz == "intraday" else 2.0
        sl = cc.segnali(B, k, conf, orizz)
        ss = cc.segnali(cc.specchio(Bs), k, conf, orizz)
        np.testing.assert_allclose([a.F for a in sl], [a.F + K for a in ss], atol=1e-9)
        ol = cc.operazioni(sl, B, (t, o, h, l, c), orizz, 1, 0.46, fg, g5, stop=stop)
        os_ = cc.operazioni(ss, Bs, (t, K - o, K - l, K - h, K - c), orizz, -1, 0.46, fg, g5, stop=stop)
        assert len(ol["e"]) > 0
        np.testing.assert_array_equal(ol["e"], os_["e"])
        np.testing.assert_array_equal(ol["x"], os_["x"])
        np.testing.assert_array_equal(ol["mot"], os_["mot"])
        np.testing.assert_array_equal(ol["fr"], os_["fr"])
        np.testing.assert_allclose(ol["R"], os_["R"], atol=1e-9)
        np.testing.assert_allclose(ol["stop"], K - os_["stop"], atol=1e-9)
        gl = (ol["px"] - ol["ent"][:, None]) / ol["R"][:, None]
        gs = -(os_["px"] - os_["ent"][:, None]) / os_["R"][:, None]
        np.testing.assert_allclose(gl, gs, atol=1e-9)
        n_fr += int(ol["fr"].sum())
    if stop == "S2" and conf != "C4":   # C4 conferma sul minimo: nessun frattale dopo L
        assert n_fr > 0          # il caso con minimo crescente e' esercitato


@pytest.mark.parametrize("conf", ["C1", "C2", "C5", "NESSUNA"])
def test_minimo_crescente_senza_lookahead(conf):
    t, o, h, l, c = m5_casuale(seed=11)
    B, _ = costruisci(t, o, h, l, c)
    full = [(a.inizio, a.conferma, a.L, a.F) for a in cc.segnali(B, 1.0, conf, "intraday")]
    assert any(np.isfinite(x[3]) for x in full)
    for taglio in (len(B.c) // 3, len(B.c) // 2, len(B.c) - 7):
        n5 = B.i5[taglio]
        Bt, _ = costruisci(t[:n5], o[:n5], h[:n5], l[:n5], c[:n5])
        tr = [(a.inizio, a.conferma, a.L, a.F) for a in cc.segnali(Bt, 1.0, conf, "intraday")]
        a = [x for x in full if x[1] < taglio]
        b = [x for x in tr if x[1] < taglio]
        assert len(a) == len(b)
        for x, y in zip(a, b):
            assert x[:3] == y[:3] and (x[3] == y[3] or (np.isnan(x[3]) and np.isnan(y[3])))
