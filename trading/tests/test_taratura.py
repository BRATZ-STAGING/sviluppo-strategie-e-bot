import dataclasses

import pytest

from framework.taratura import UFFICIALE, Taratura


class TestTaraturaUfficiale:
    def test_valori_verificati_fuori_campione(self):
        # se uno di questi cambia, cambiano TUTTI gli studi: il test e' qui
        # apposta per costringere a passare da una verifica esplicita
        t = UFFICIALE
        assert t.conferme == ("M33", "H12")
        assert t.ritracciamento == ("M12",)
        assert (t.obiettivo, t.pareggio) == (10.0, 3.0)
        assert t.rischio_per_operazione == 0.01

    def test_e_immutabile(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            UFFICIALE.obiettivo = 3.0

    def test_timeframes_senza_duplicati_e_in_ordine(self):
        assert UFFICIALE.timeframes == ("H6", "H2", "M33", "H12", "M12")


class TestInvarianti:
    def test_rischio_fuori_range(self):
        with pytest.raises(ValueError, match="rischio_per_operazione"):
            Taratura(rischio_per_operazione=0.10)

    def test_rischio_min_maggiore_del_max(self):
        with pytest.raises(ValueError, match="rischio_min"):
            Taratura(rischio_min=20.0, rischio_max=10.0)

    def test_pareggio_oltre_l_obiettivo(self):
        with pytest.raises(ValueError, match="pareggio"):
            Taratura(obiettivo=3.0, pareggio=5.0)

    def test_pareggio_assente_e_lecito(self):
        assert Taratura(pareggio=None).pareggio is None

    def test_orari_incoerenti(self):
        with pytest.raises(ValueError, match="orari"):
            Taratura(ora_inizio=19, ora_fine=7)

    def test_stesso_tf_conferma_e_ritracciamento(self):
        with pytest.raises(ValueError, match="ritracciamento"):
            Taratura(conferme=("M33", "M12"), ritracciamento=("M12",))


class TestSoglie:
    def test_in_dollari_senza_atr(self):
        s = UFFICIALE.soglie()
        assert s["impulso"] == 4.0 and s["buffer"] == 0.3
        assert (s["rischio_min"], s["rischio_max"]) == (1.0, 10.0)

    def test_riscalate_sulla_volatilita(self):
        # ATR doppio della mediana => soglie doppie
        s = UFFICIALE.soglie(atr=4.0, mediana=2.0)
        assert s["impulso"] == pytest.approx(8.0)
        assert s["rischio_max"] == pytest.approx(20.0)

    def test_mediana_mancante(self):
        with pytest.raises(ValueError, match="mediana"):
            UFFICIALE.soglie(atr=4.0)
