import pandas as pd
import pytest

from framework import data
from conftest import flat_bars, make_m1


class TestLoadM1:
    def test_roundtrip(self, tmp_path):
        df = flat_bars("2024-01-02 00:00", 10)
        df.reset_index().to_parquet(tmp_path / "XAUUSD_M1_2024.parquet", index=False)
        out = data.load_m1(str(tmp_path))
        assert len(out) == 10
        assert str(out.index.tz) == "UTC"
        assert list(out.columns) == ["open", "high", "low", "close", "volume"]

    def test_filtro_anni(self, tmp_path):
        for year in (2023, 2024):
            df = flat_bars(f"{year}-06-03 00:00", 5)
            df.reset_index().to_parquet(tmp_path / f"XAUUSD_M1_{year}.parquet", index=False)
        out = data.load_m1(str(tmp_path), years=[2024])
        assert out.index[0].year == 2024
        assert len(out) == 5

    def test_concatena_e_ordina(self, tmp_path):
        for year in (2023, 2024):
            df = flat_bars(f"{year}-06-03 00:00", 5)
            df.reset_index().to_parquet(tmp_path / f"XAUUSD_M1_{year}.parquet", index=False)
        out = data.load_m1(str(tmp_path))
        assert len(out) == 10
        assert out.index.is_monotonic_increasing

    def test_cartella_vuota(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            data.load_m1(str(tmp_path))


class TestValidate:
    def test_ok(self):
        data.validate_ohlcv(flat_bars("2024-01-02", 5))

    def test_colonna_mancante(self):
        df = flat_bars("2024-01-02", 5).drop(columns=["volume"])
        with pytest.raises(ValueError, match="mancanti"):
            data.validate_ohlcv(df)

    def test_non_ordinato(self):
        df = flat_bars("2024-01-02", 5).iloc[::-1]
        with pytest.raises(ValueError, match="ordinato"):
            data.validate_ohlcv(df)

    def test_duplicati(self):
        df = flat_bars("2024-01-02", 3)
        df = pd.concat([df, df.iloc[[1]]]).sort_index()
        with pytest.raises(ValueError, match="duplicati"):
            data.validate_ohlcv(df)

    def test_ohlc_incoerente(self):
        df = flat_bars("2024-01-02", 3)
        df.iloc[1, df.columns.get_loc("high")] = df.iloc[1]["low"] - 1
        with pytest.raises(ValueError, match="incoerenti"):
            data.validate_ohlcv(df)


class TestResample:
    def test_m5(self):
        df = make_m1("2024-01-02 00:00", [
            (10, 12, 9, 11), (11, 15, 10, 14), (14, 14, 8, 9),
            (9, 10, 8, 9.5), (9.5, 11, 9, 10),
        ])
        out = data.resample(df, "5min")
        assert len(out) == 1
        row = out.iloc[0]
        assert row.open == 10 and row.high == 15 and row.low == 8 and row.close == 10
        assert row.volume == 5.0

    def test_bin_vuoti_scartati(self):
        a = flat_bars("2024-01-02 00:00", 5)
        b = flat_bars("2024-01-02 03:00", 5)
        out = data.resample(pd.concat([a, b]), "5min")
        assert len(out) == 2


class TestTimeframes:
    def test_registro_completo(self):
        # tutti i TF operativi del progetto, inclusi i non-nativi MT5
        assert {"M1", "M3", "M6", "M10", "M12", "M33", "M66",
                "H2", "H3", "H6", "H12", "D1"} == set(data.TIMEFRAMES)

    def test_resample_m33(self):
        df = flat_bars("2024-01-02 00:00", 66)
        out = data.resample_tf(df, "M33")
        # i bin sono ancorati all'epoch, non alla mezzanotte: 66 minuti a
        # partire da 00:00 ricadono in tre finestre da 33', non due
        assert out.volume.sum() == 66.0
        minuti = (out.index - pd.Timestamp(0, tz="UTC")).total_seconds() // 60
        assert (minuti % 33 == 0).all()

    def test_tf_sconosciuto(self):
        df = flat_bars("2024-01-02 00:00", 3)
        with pytest.raises(ValueError, match="sconosciuto"):
            data.resample_tf(df, "M15")

    def test_m33_indipendente_dai_dati_caricati(self):
        # le candele M33/M66 devono essere le stesse a prescindere da dove
        # inizia la serie: senza ancoraggio all'epoch gli studi non sarebbero
        # riproducibili caricando anni diversi
        lungo = flat_bars("2024-01-02 00:00", 300)
        corto = lungo.iloc[97:]
        a = data.resample_tf(lungo, "M33")
        b = data.resample_tf(corto, "M33")
        comuni = a.index.intersection(b.index)
        assert len(comuni) > 3
        assert (a.loc[comuni].index == b.loc[comuni].index).all()
        assert b.index.isin(a.index).all()


class TestSessions:
    @pytest.mark.parametrize("hour,expected", [
        (0, "asia"), (6, "asia"), (7, "london"), (11, "london"),
        (12, "ny"), (20, "ny"), (21, "late"), (23, "late"),
    ])
    def test_session_of(self, hour, expected):
        ts = pd.Timestamp(f"2024-01-02 {hour:02d}:30", tz="UTC")
        assert data.session_of(ts) == expected

    def test_add_sessions(self):
        df = flat_bars("2024-01-02 06:58", 5)  # 06:58–07:02
        out = data.add_sessions(df)
        assert list(out.session) == ["asia", "asia", "london", "london", "london"]
