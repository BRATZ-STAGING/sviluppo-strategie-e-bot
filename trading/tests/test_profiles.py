import pandas as pd
import pytest

from framework import profiles as pf


class TestTradingProfile:
    def base(self, **kw):
        args = dict(name="x", sessions=frozenset({"london"}),
                    level_kinds=frozenset({"pdh"}))
        args.update(kw)
        return pf.TradingProfile(**args)

    def test_valido(self):
        p = self.base()
        assert p.target_usd == p.rr * p.stop_usd

    def test_sessione_sconosciuta(self):
        with pytest.raises(ValueError, match="sconosciute"):
            self.base(sessions=frozenset({"tokyo"}))

    def test_rischio_fuori_range(self):
        with pytest.raises(ValueError):
            self.base(risk_per_trade=0.10)
        with pytest.raises(ValueError):
            self.base(risk_per_trade=0.0)

    def test_rr_e_stop_positivi(self):
        with pytest.raises(ValueError):
            self.base(rr=0)
        with pytest.raises(ValueError):
            self.base(stop_usd=-1)

    def test_profili_default_validi(self):
        assert set(pf.DEFAULT_PROFILES) == {"london-reversal", "ny-levels", "swing-daily"}
        for name, p in pf.DEFAULT_PROFILES.items():
            assert p.name == name


class TestDailyPlan:
    def test_filtra_e_ordina(self, two_days, day3):
        p = pf.TradingProfile(name="t", sessions=frozenset({"london"}),
                              level_kinds=frozenset({"pdh", "pdl"}))
        plan = pf.daily_plan(two_days, day3, p)
        assert plan.day == day3
        assert [l.kind for l in plan.levels] == ["pdl", "pdh"]  # ordinati per prezzo
        assert [l.price for l in plan.levels] == [1990.0, 2010.0]
