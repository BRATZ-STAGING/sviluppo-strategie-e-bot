import pandas as pd
import pytest

from framework import levels as lv
from conftest import flat_bars, make_m1, walk_bars

AT = pd.Timestamp("2024-01-03", tz="UTC")


class TestRoundLevels:
    def test_step_50(self):
        out = lv.round_levels(1980, 2120, 50, "round_50", AT)
        assert [l.price for l in out] == [2000, 2050, 2100]
        assert all(l.kind == "round_50" for l in out)

    def test_estremi_inclusi(self):
        out = lv.round_levels(2000, 2100, 50, "round_50", AT)
        assert [l.price for l in out] == [2000, 2050, 2100]

    def test_step_non_positivo(self):
        with pytest.raises(ValueError):
            lv.round_levels(1, 2, 0, "x", AT)


class TestPrevDay:
    def test_valori(self, two_days, day3):
        out = lv.prev_day_levels(two_days, day3)
        by_kind = {l.kind: l.price for l in out}
        assert by_kind == {"pdh": 2010.0, "pdl": 1990.0, "pdc": 2005.0}

    def test_primo_giorno_vuoto(self, two_days):
        assert lv.prev_day_levels(two_days, pd.Timestamp("2024-01-02", tz="UTC")) == []

    def test_salta_weekend(self, two_days):
        # il giorno precedente al lunedì 8/1 è il 3/1 nei dati; avendo poche
        # candele (sessione parziale) viene fuso con il 2/1
        out = lv.prev_day_levels(two_days, pd.Timestamp("2024-01-08", tz="UTC"))
        by_kind = {l.kind: l.price for l in out}
        assert by_kind["pdh"] == 2010.0 and by_kind["pdl"] == 1990.0
        assert by_kind["pdc"] == 2004.0  # l'ultima chiusura resta quella del 3/1

    def test_sessione_parziale_fusa_col_giorno_pieno(self):
        friday = make_m1("2024-01-05 00:00", [(2000, 2010, 1990, 2005)] * 350)
        sunday = make_m1("2024-01-07 22:00", [(2016, 2020, 2015, 2018)] * 60)
        df = pd.concat([friday, sunday])
        out = lv.prev_day_levels(df, pd.Timestamp("2024-01-08", tz="UTC"))
        by_kind = {l.kind: l.price for l in out}
        # PDH/PDL del lunedì coprono venerdì+domenica, PDC è la chiusura di domenica
        assert by_kind == {"pdh": 2020.0, "pdl": 1990.0, "pdc": 2018.0}

    def test_giorno_pieno_non_fuso(self):
        thursday = make_m1("2024-01-04 00:00", [(2030, 2040, 2025, 2035)] * 350)
        friday = make_m1("2024-01-05 00:00", [(2000, 2010, 1990, 2005)] * 350)
        out = lv.prev_day_levels(pd.concat([thursday, friday]),
                                 pd.Timestamp("2024-01-08", tz="UTC"))
        by_kind = {l.kind: l.price for l in out}
        assert by_kind == {"pdh": 2010.0, "pdl": 1990.0, "pdc": 2005.0}


class TestPrevWeek:
    def test_valori(self):
        week1 = make_m1("2024-01-01 00:00", [(2000, 2050, 1950, 2020)])
        week2 = flat_bars("2024-01-08 00:00", 3, price=2020)
        df = pd.concat([week1, week2])
        out = lv.prev_week_levels(df, pd.Timestamp("2024-01-10", tz="UTC"))
        by_kind = {l.kind: l.price for l in out}
        assert by_kind == {"pwh": 2050.0, "pwl": 1950.0}

    def test_senza_settimana_precedente(self):
        df = flat_bars("2024-01-08 00:00", 3)
        assert lv.prev_week_levels(df, pd.Timestamp("2024-01-10", tz="UTC")) == []


class TestAsiaSession:
    def test_valori_e_attivazione(self):
        asia = make_m1("2024-01-03 02:00", [(2000, 2015, 1995, 2010)])
        london = flat_bars("2024-01-03 08:00", 3, price=2010)
        out = lv.asia_session_levels(pd.concat([asia, london]),
                                     pd.Timestamp("2024-01-03", tz="UTC"))
        by_kind = {l.kind: l for l in out}
        assert by_kind["asia_h"].price == 2015.0
        assert by_kind["asia_l"].price == 1995.0
        assert by_kind["asia_h"].active_from == pd.Timestamp("2024-01-03 07:00", tz="UTC")

    def test_solo_dati_asia(self):
        # candele solo in sessione london: nessun livello asia
        df = flat_bars("2024-01-03 08:00", 3)
        assert lv.asia_session_levels(df, pd.Timestamp("2024-01-03", tz="UTC")) == []


class TestSwing:
    def _m1_with_pivot(self, mitigated=False):
        # 9 ore H1: pivot high a 2050 alla 5ª ora (k=3 candele per lato)
        closes = [2000, 2005, 2010, 2020, 2050, 2020, 2010, 2005,
                  2052 if mitigated else 2000]
        rows = []
        for c in closes:
            rows.extend([(c, c + 1, c - 1, c)] * 60)  # 60 min per "ora"
        return make_m1("2024-01-02 00:00", rows)

    def test_pivot_trovato(self):
        m1 = self._m1_with_pivot()
        out = lv.swing_levels(m1, pd.Timestamp("2024-01-03", tz="UTC"), k=3)
        highs = [l for l in out if l.kind == "swing_h"]
        assert len(highs) == 1
        assert highs[0].price == 2051.0  # high della candela pivot

    def test_pivot_mitigato_escluso(self):
        m1 = self._m1_with_pivot(mitigated=True)
        out = lv.swing_levels(m1, pd.Timestamp("2024-01-03", tz="UTC"), k=3)
        assert [l for l in out if l.kind == "swing_h" and l.price == 2051.0] == []

    def test_dati_insufficienti(self):
        m1 = flat_bars("2024-01-02 00:00", 60)
        assert lv.swing_levels(m1, pd.Timestamp("2024-01-03", tz="UTC")) == []


class TestLevelsForDay:
    def test_filtro_include(self, two_days, day3):
        out = lv.levels_for_day(two_days, day3, include={"pdh", "pdl"})
        assert {l.kind for l in out} == {"pdh", "pdl"}

    def test_round_presenti_e_deduplicati(self, two_days, day3):
        out = lv.levels_for_day(two_days, day3)
        r100 = [l.price for l in out if l.kind == "round_100"]
        r50 = [l.price for l in out if l.kind == "round_50"]
        # 2000 è un multiplo di 100: appartiene a round_100 e NON a round_50
        assert 2000.0 in r100
        assert 2000.0 not in r50

    def test_nessun_lookahead(self, two_days, day3):
        # i livelli del giorno D (esclusa asia, che usa D stesso) non devono
        # cambiare se si eliminano i dati da D in poi
        kinds = {"pdh", "pdl", "pdc", "pwh", "pwl", "swing_h", "swing_l",
                 "round_50", "round_100"}
        full = lv.levels_for_day(two_days, day3, include=kinds)
        truncated = lv.levels_for_day(two_days[two_days.index < day3], day3,
                                      include=kinds)
        key = lambda ls: sorted((l.kind, l.price) for l in ls)
        assert key(full) == key(truncated)
