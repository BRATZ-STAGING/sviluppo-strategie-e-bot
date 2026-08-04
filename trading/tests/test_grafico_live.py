"""Il pannello dal vivo deve dire le stesse cose del motore di backtest.

Il rischio vero del grafico non e' che si rompa: e' che mostri "SEGNALE"
quando ``segnali.genera`` non aprirebbe niente, o che taccia quando invece
aprirebbe. Sono due conti scritti in due posti diversi, e qui si verifica che
diano lo stesso risultato sugli stessi dati.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

from framework.data import TIMEFRAMES, resample_tf
from framework.segnali import genera
from framework.taratura import UFFICIALE as T

import grafico_live as G


@pytest.fixture(scope="module")
def storico():
    """Un anno vero di minuti: serve storia per macro, ATR e regime."""
    cartella = os.path.join(G.ROOT, "data", "XAUUSD_M1")
    if not os.path.isdir(cartella):
        pytest.skip("archivio M1 non presente")
    from framework.data import load_m1
    return load_m1(cartella, years=[2023])


def stato_ai(m1, quando, tfs):
    """Lo stato di struttura di ogni TF come lo vede il grafico a quell'ora."""
    from framework.structure import trend_state_series
    from framework.data import TIMEFRAMES
    fuori = {}
    for tf in tfs:
        d = resample_tf(m1, tf)
        passo = pd.Timedelta(TIMEFRAMES[tf])
        st = trend_state_series(d, T.frattale_k, passo)
        st = st[st.index <= quando]
        fuori[tf] = int(st.iloc[-1]) if len(st) else 0
    return fuori


class TestCoerenzaColMotore:
    def test_il_pannello_riconosce_i_segnali_del_motore(self, storico):
        """Su ogni operazione trovata dal motore, il pannello deve accendersi.

        Si tronca la serie all'istante dell'ingresso — che e' esattamente cio'
        che il grafico ha a disposizione dal vivo — e si chiede al pannello
        cosa vede. Deve vedere il segnale, dallo stesso lato.
        """
        ops = [o for o in genera(storico, T)
               if all(o[f"c_{tf}"] for tf in T.conferme)
               and all(not o[f"c_{tf}"] for tf in T.ritracciamento)]
        assert len(ops) > 20, "campione troppo piccolo per essere una prova"

        passo = pd.Timedelta("6min")
        controllate = 0
        for o in ops[::3]:                      # un campione ogni tre
            quando = pd.Timestamp(o["time"])    # chiusura della candela M6
            m1 = storico[storico.index < quando]
            if len(m1) < 100_000:
                continue
            barra = quando - passo
            struttura = stato_ai(m1, barra, set(T.timeframes))
            c = G.condizioni_ora(m1, G.vwap_motore(m1), struttura,
                                 quando)
            assert c is not None
            assert c["candela"] == barra.strftime("%d/%m %H:%M"), (
                "il pannello guarda una candela diversa da quella del segnale")
            lato = o["lato"]
            assert c["lati"][lato]["reclaim"], f"reclaim mancante su {quando}"
            assert c["lati"][lato]["spinta_ok"], f"spinta sotto soglia su {quando}"
            assert c["lati"][lato]["macro"] is True, f"macro discorde su {quando}"
            assert c["lati"][lato]["pronto"], f"pannello spento su {quando}"
            controllate += 1
        assert controllate >= 10, f"solo {controllate} operazioni verificate"

    def test_usa_lultima_candela_chiusa(self, storico):
        """Mai la candela in corso: cambierebbe idea a ogni tick."""
        m1 = storico.iloc[:200_000]
        m6 = resample_tf(m1, T.tf_ingresso)
        aperta = m6.index[-1]
        # a meta' dell'ultima candela si deve guardare quella prima
        c = G.condizioni_ora(m1, G.vwap_motore(m1), {},
                             aperta + pd.Timedelta("3min"))
        assert c["candela"] == m6.index[-2].strftime("%d/%m %H:%M")

    def test_prende_la_candela_appena_chiusa(self, storico):
        """Nel minuto in cui una candela chiude, la successiva non esiste
        ancora nel terminale: il pannello deve comunque vedere quella nuova."""
        m1 = storico.iloc[:200_000]
        m6 = resample_tf(m1, T.tf_ingresso)
        appena = m6.index[-1] + pd.Timedelta(TIMEFRAMES[T.tf_ingresso])
        c = G.condizioni_ora(m1, G.vwap_motore(m1), {}, appena)
        assert c["candela"] == m6.index[-1].strftime("%d/%m %H:%M")

    def test_soglie_riscalate_nei_mesi_agitati(self, storico):
        """Le soglie devono seguire l'ATR quando il motore lo fa."""
        m1 = storico.iloc[:200_000]
        s, alta = G.soglie_ora(m1, m1.index[-1])
        assert set(s) == {"impulso", "buffer", "rischio_min", "rischio_max"}
        if not alta:
            assert s["impulso"] == pytest.approx(T.impulso_min)
        else:
            assert s["impulso"] != pytest.approx(T.impulso_min)


class TestUnisci:
    def _giorno(self, inizio, n, vol):
        i = pd.date_range(inizio, periods=n, freq="1min", tz="UTC")
        return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0,
                             "close": 1.0, "volume": vol}, index=i)

    def test_taglia_a_mezzanotte(self):
        """Nessuna giornata puo' risultare mista fra le due fonti: il volume
        e' misurato in modo diverso e il VWAP e' pesato sui volumi."""
        storia = self._giorno("2026-07-01 00:00", 3000, 0.01)
        vivo = self._giorno("2026-07-02 08:00", 600, 120.0)
        unito, buco = G.unisci(storia, vivo)
        giorni = unito.index.normalize()
        for g in giorni.unique():
            v = unito.volume[giorni == g]
            assert v.nunique() == 1, f"giornata {g} presa da due fonti diverse"
        assert buco == 0

    def test_segnala_il_buco(self):
        storia = self._giorno("2026-06-01 00:00", 600, 0.01)
        vivo = self._giorno("2026-06-10 00:00", 600, 120.0)
        _, buco = G.unisci(storia, vivo)
        assert buco == 8

    def test_senza_archivio(self):
        vivo = self._giorno("2026-06-10 00:00", 600, 120.0)
        unito, buco = G.unisci(None, vivo)
        assert unito.equals(vivo) and buco is None

    def test_niente_duplicati(self):
        storia = self._giorno("2026-07-01 00:00", 3000, 0.01)
        vivo = self._giorno("2026-07-01 12:00", 600, 120.0)
        unito, _ = G.unisci(storia, vivo)
        assert not unito.index.has_duplicates
        assert unito.index.is_monotonic_increasing
