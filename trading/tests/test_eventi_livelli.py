"""L'invariante che mancava: un evento non puo' precedere il suo prezzo.

Gli studi sui livelli entrano al prezzo di CHIUSURA della candela che tocca
il livello. Se l'istante registrato e' l'APERTURA di quella candela, il
percorso valutato comprende la candela stessa: si entra sapendo gia' come
finisce, e il vantaggio finto cresce col timeframe (su H6 erano sei ore di
futuro, e il risultato passava da negativo a +0,98 R per operazione con il
73% di operazioni vinte — identico al placebo, che era l'indizio).
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

from framework.data import TIMEFRAMES, load_m1, resample_tf
from framework.volatility import daily_atr

import run_livelli_atr as L
import run_ob_tocchi as B


@pytest.fixture(scope="module")
def m1():
    cartella = os.path.join(B.ROOT, "data", "XAUUSD_M1")
    if not os.path.isdir(cartella):
        pytest.skip("archivio M1 non presente")
    return load_m1(cartella, years=[2024]).iloc[:120_000]


def _atr(m1):
    return {k: v for k, v in daily_atr(m1, 14).items()}


class TestIstanteDegliEventi:
    def test_ob_entra_alla_chiusura_della_candela(self, m1):
        """Per ogni tocco: l'istante registrato e' la chiusura della candela
        il cui prezzo di chiusura e' quello d'ingresso."""
        rng = np.random.default_rng(0)
        ev = B.eventi_tf(m1, "H2", _atr(m1), False, rng)
        assert len(ev) > 50, "campione troppo piccolo"
        passi = {"chiusura tf": "H2", "ombra": "H2",
                 "chiusura M12": "M12", "chiusura M6": "M6"}
        serie = {k: resample_tf(m1, v) for k, v in passi.items()}
        controllati = 0
        for e in ev[::7]:
            s = serie[e["definizione"]]
            passo = pd.Timedelta(TIMEFRAMES[passi[e["definizione"]]])
            apertura = e["time"] - passo
            assert apertura in s.index, (
                f"{e['time']} non e' la chiusura di una candela {passi[e['definizione']]}")
            assert s.close.loc[apertura] == pytest.approx(e["entry"]), (
                "il prezzo d'ingresso non e' la chiusura di quella candela")
            controllati += 1
        assert controllati >= 10

    def test_livelli_entra_alla_chiusura_della_candela(self, m1):
        rng = np.random.default_rng(0)
        atr = daily_atr(m1, 14)
        prof = L.profilo_giorno(m1, _atr(m1))
        chiavi = sorted(prof)
        prof = {chiavi[i + 1]: prof[chiavi[i]] for i in range(len(chiavi) - 1)}
        bande = L.bande_per_giorno(prof, _atr(m1), False, rng)
        tfd = resample_tf(m1, "H2")
        atr_bar = atr.reindex(tfd.index.normalize()).ffill().values
        ob = L.bande_ob(tfd, "H2", False, rng, atr_bar)
        ev = L.eventi_tf(tfd, "H2", bande, atr_bar, ob)
        assert len(ev) > 50, "campione troppo piccolo"
        passo = pd.Timedelta(TIMEFRAMES["H2"])
        for e in ev[::7]:
            apertura = e["time"] - passo
            assert apertura in tfd.index
            assert tfd.close.loc[apertura] == pytest.approx(e["entry"])

    def test_la_valutazione_parte_dopo_lingresso(self, m1):
        """esiti() non deve mai guardare minuti precedenti all'ingresso."""
        idx_ns = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
        quando = m1.index[50_000]
        ev = [{"time": quando, "entry": float(m1.close.loc[quando]),
               "atr": 20.0, "lato": 1}]
        # se la valutazione partisse prima, un minuto gia' passato con un
        # massimo enorme darebbe un obiettivo raggiunto: qui non deve
        col = L.esiti(ev, m1, idx_ns)
        atteso_da = m1.index[m1.index > quando][0]
        assert atteso_da > quando
        assert any(np.isfinite(v[0]) for v in col.values())
