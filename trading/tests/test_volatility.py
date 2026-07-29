import numpy as np
import pandas as pd
import pytest

from framework.volatility import (atr_at, daily_atr, daily_bars,
                                  high_volatility_months)
from conftest import make_m1


def day_of(price_open, high, low, close, day, bars=400):
    """Una giornata piena costruita per avere OHLC noti."""
    rows = [(price_open, price_open, price_open, price_open)]
    rows += [(high, high, high, high), (low, low, low, low)]
    rows += [(close, close, close, close)] * (bars - 3)
    return make_m1(f"{day} 00:00", rows)


class TestDailyBars:
    def test_esclude_sessione_parziale(self):
        pieno = day_of(2000, 2010, 1990, 2005, "2024-01-02")
        parziale = make_m1("2024-01-07 23:00", [(2100, 2110, 2090, 2100)] * 60)
        d1 = daily_bars(pd.concat([pieno, parziale]))
        assert len(d1) == 1
        assert d1.index[0].strftime("%Y-%m-%d") == "2024-01-02"

    def test_ohlc_giornalieri(self):
        d1 = daily_bars(day_of(2000, 2010, 1990, 2005, "2024-01-02"))
        r = d1.iloc[0]
        assert (r.open, r.high, r.low, r.close) == (2000, 2010, 1990, 2005)


class TestDailyAtr:
    def _serie(self, n=20):
        parts = []
        for k in range(n):
            day = pd.Timestamp("2024-01-01") + pd.Timedelta(days=k)
            base = 2000 + k * 5
            parts.append(day_of(base, base + 10, base - 10, base + 2,
                                day.strftime("%Y-%m-%d")))
        return pd.concat(parts)

    def test_valore_positivo_dopo_la_finestra(self):
        atr = daily_atr(self._serie(20), n=5)
        assert atr.dropna().gt(0).all()
        assert atr.iloc[:5].isna().all()      # finestra non ancora piena + shift

    def test_causale(self):
        # l'ATR del giorno D non cambia se cambiano i dati del giorno D
        s = self._serie(20)
        atr_a = daily_atr(s, n=5)
        last_day = s.index[-1].normalize()
        s2 = s.copy()
        mask = s2.index >= last_day
        s2.loc[mask, "high"] = s2.loc[mask, "high"] + 500   # giornata stravolta
        atr_b = daily_atr(s2, n=5)
        assert atr_a.iloc[-1] == pytest.approx(atr_b.iloc[-1])

    def test_atr_at_riporta_ultimo_noto(self):
        atr = daily_atr(self._serie(20), n=5)
        giorni = pd.DatetimeIndex([atr.index[-1] + pd.Timedelta(hours=9)])
        assert atr_at(atr, giorni).iloc[0] == pytest.approx(atr.iloc[-1])

    def test_serie_troppo_corta(self):
        atr = daily_atr(self._serie(3), n=14)
        assert atr.isna().all()


class TestHighVolatilityMonths:
    def _atr(self, valori, start="2020-01-01"):
        idx = pd.date_range(start, periods=len(valori), freq="D", tz="UTC")
        return pd.Series(valori, index=idx, dtype=float)

    def test_storia_insufficiente_e_regime_normale(self):
        atr = self._atr([20.0] * 100)
        mesi = [pd.Period("2020-04", "M")]
        assert high_volatility_months(atr, mesi) == {mesi[0]: False}

    def test_riconosce_esplosione_di_volatilita(self):
        # 400 giorni calmi, poi un mese a volatilità tripla
        atr = self._atr([20.0] * 400 + [60.0] * 30)
        m = pd.Period((atr.index[-1] + pd.Timedelta(days=1)).strftime("%Y-%m"), "M")
        mese_dopo = m + 1
        assert high_volatility_months(atr, [mese_dopo])[mese_dopo] is True

    def test_volatilita_stabile_resta_normale(self):
        atr = self._atr([20.0] * 500)
        m = pd.Period("2021-04", "M")
        assert high_volatility_months(atr, [m])[m] is False

    def test_causale_ignora_il_mese_stesso(self):
        # un'esplosione DENTRO il mese non deve cambiare la decisione di quel mese
        base = [20.0] * 400
        m = pd.Period((self._atr(base).index[-1] + pd.Timedelta(days=1))
                      .strftime("%Y-%m"), "M")
        calmo = high_volatility_months(self._atr(base + [20.0] * 30), [m])[m]
        esploso = high_volatility_months(self._atr(base + [200.0] * 30), [m])[m]
        assert calmo == esploso

    def test_fattore_piu_alto_e_piu_selettivo(self):
        atr = self._atr([20.0] * 400 + [35.0] * 30)
        m = pd.Period((atr.index[-1] + pd.Timedelta(days=1)).strftime("%Y-%m"), "M") + 1
        assert high_volatility_months(atr, [m], factor=1.5)[m] is True
        assert high_volatility_months(atr, [m], factor=3.0)[m] is False
