import numpy as np
import pytest

from framework import gestione
from framework.gestione import FINE_GIORNATA, OBIETTIVO, PAREGGIO, STOP, esito


def percorso(*passi):
    """Percorso al minuto: ogni passo e' (favorevole, contrario) in R."""
    fav = np.array([p[0] for p in passi], dtype=float)
    sfav = np.array([p[1] for p in passi], dtype=float)
    return fav, sfav


class TestStopFisso:
    def test_obiettivo_raggiunto(self):
        fav, sfav = percorso((0.5, 0.2), (1.5, 0.2), (3.0, 0.2))
        assert esito(fav, sfav, 3.0) == (3.0, OBIETTIVO)

    def test_stop_colpito(self):
        fav, sfav = percorso((0.5, 0.2), (0.6, 1.0))
        assert esito(fav, sfav, 3.0) == (-1.0, STOP)

    def test_stop_vince_sull_obiettivo_nello_stesso_minuto(self):
        # conservativo: nello stesso minuto non sappiamo l'ordine, vince lo stop
        fav, sfav = percorso((3.0, 1.0),)
        assert esito(fav, sfav, 3.0) == (-1.0, STOP)

    def test_ne_stop_ne_obiettivo(self):
        fav, sfav = percorso((0.5, 0.4), (1.2, 0.4))
        assert esito(fav, sfav, 3.0) == (None, FINE_GIORNATA)

    def test_costo_sottratto_sempre(self):
        fav, sfav = percorso((3.0, 0.1),)
        assert esito(fav, sfav, 3.0, costo=0.1) == (pytest.approx(2.9), OBIETTIVO)
        fav, sfav = percorso((0.1, 1.0),)
        assert esito(fav, sfav, 3.0, costo=0.1) == (pytest.approx(-1.1), STOP)


class TestPareggio:
    def test_stop_prima_di_armare(self):
        fav, sfav = percorso((1.0, 0.3), (1.2, 1.0))
        assert esito(fav, sfav, 10.0, be=2.0) == (-1.0, STOP)

    def test_uscita_a_pareggio(self):
        # arma a +2R, poi il prezzo torna sull'ingresso
        fav, sfav = percorso((2.0, 0.0), (2.1, 0.0), (2.1, 0.5))
        assert esito(fav, sfav, 10.0, be=2.0) == (0.0, PAREGGIO)

    def test_pareggio_non_scatta_prima_di_armare(self):
        # il prezzo passa sotto l'ingresso PRIMA di arrivare a +2R: irrilevante
        fav, sfav = percorso((0.1, 0.9), (2.0, 0.0), (10.0, 0.0))
        assert esito(fav, sfav, 10.0, be=2.0) == (10.0, OBIETTIVO)

    def test_soglia_mai_raggiunta_equivale_a_stop_fisso(self):
        fav, sfav = percorso((0.5, 0.4), (1.0, 0.4))
        assert esito(fav, sfav, 10.0, be=2.0) == (None, FINE_GIORNATA)

    def test_obiettivo_nello_stesso_minuto_dell_armamento(self):
        fav, sfav = percorso((10.0, 0.0),)
        assert esito(fav, sfav, 10.0, be=2.0) == (10.0, OBIETTIVO)

    def test_pareggio_vince_sull_obiettivo_nello_stesso_minuto(self):
        fav, sfav = percorso((2.0, 0.0), (10.0, 0.5))
        assert esito(fav, sfav, 10.0, be=2.0) == (0.0, PAREGGIO)


class TestParziale:
    def test_meta_incassata_e_resto_a_pareggio(self):
        fav, sfav = percorso((2.0, 0.0), (3.0, 0.0), (3.0, 0.5))
        r, motivo = esito(fav, sfav, 10.0, be=2.0, parziale=True)
        assert motivo == PAREGGIO and r == pytest.approx(1.0)   # 0,5 x 2R

    def test_meta_incassata_e_resto_all_obiettivo(self):
        fav, sfav = percorso((2.0, 0.0), (10.0, 0.0))
        r, motivo = esito(fav, sfav, 10.0, be=2.0, parziale=True)
        assert motivo == OBIETTIVO and r == pytest.approx(6.0)  # 1R + 5R

    def test_stop_pieno_se_non_arriva_alla_soglia(self):
        fav, sfav = percorso((1.0, 0.2), (1.0, 1.0))
        assert esito(fav, sfav, 10.0, be=2.0, parziale=True) == (-1.0, STOP)


class TestChiusuraFineGiornata:
    def test_senza_parziale(self):
        assert gestione.chiusura_fine_giornata(2.5, None, False, 3.0, 0.1) == \
            pytest.approx(2.4)

    def test_con_parziale_gia_incassato(self):
        # meta' chiusa a +2R, il resto chiude a +1R: (2 + 1) / 2
        assert gestione.chiusura_fine_giornata(1.0, 2.0, True, 3.0, 0.1) == \
            pytest.approx(1.4)

    def test_con_parziale_mai_armato(self):
        assert gestione.chiusura_fine_giornata(1.0, 2.0, True, 0.5, 0.1) == \
            pytest.approx(0.9)


class TestIndiceDiUscita:
    def test_indice_stop(self):
        fav, sfav = percorso((0.5, 0.2), (0.6, 1.0), (0.6, 1.2))
        assert gestione.esito_indice(fav, sfav, 3.0)[2] == 1

    def test_indice_obiettivo(self):
        fav, sfav = percorso((0.5, 0.2), (3.0, 0.2))
        assert gestione.esito_indice(fav, sfav, 3.0)[2] == 1

    def test_indice_pareggio_dopo_armamento(self):
        fav, sfav = percorso((2.0, 0.0), (2.1, 0.0), (2.1, 0.5))
        r, motivo, i = gestione.esito_indice(fav, sfav, 10.0, be=2.0)
        assert (motivo, i) == (PAREGGIO, 2)

    def test_nessun_indice_a_fine_giornata(self):
        fav, sfav = percorso((0.5, 0.4), (1.2, 0.4))
        assert gestione.esito_indice(fav, sfav, 3.0)[2] is None


class TestValuta:
    def operazione(self, *passi, r_eod=0.0, costo=0.0):
        fav, sfav = percorso(*passi)
        return {"fav": fav, "sfav": sfav, "r_eod": r_eod, "costo": costo,
                "mfe": float(fav.max())}

    def test_scioglie_la_fine_giornata(self):
        op = self.operazione((0.5, 0.3), (1.2, 0.3), r_eod=1.1, costo=0.05)
        assert gestione.valuta(op, 10.0) == (pytest.approx(1.05), FINE_GIORNATA)

    def test_stop_resta_stop(self):
        op = self.operazione((0.5, 0.3), (0.5, 1.0), r_eod=-1.0, costo=0.05)
        assert gestione.valuta(op, 10.0) == (pytest.approx(-1.05), STOP)

    def test_pareggio_con_soglia(self):
        op = self.operazione((3.0, 0.0), (3.1, 0.0), (3.1, 0.4), r_eod=0.0, costo=0.05)
        assert gestione.valuta(op, 10.0, be=3.0) == (pytest.approx(-0.05), PAREGGIO)
