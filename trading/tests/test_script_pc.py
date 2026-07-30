"""Prova gli script che girano sul PC dell'utente, eseguendoli davvero.

Questi script non sono coperti dagli altri test: non importano ``framework``,
vivono fuori dal repository (cache tick da 1,2 GB, Windows, PowerShell) e finora
venivano consegnati senza essere mai stati eseguiti. E' costato due volte:

1. codice che non partiva proprio;
2. peggio, ``misura_spread.py`` che partiva, stampava 0,700 $ per tutte e 21 le
   operazioni e sembrava una misura. Erano istanti oltre l'ultimo tick del file:
   ``searchsorted`` restituiva l'ultima posizione e lo spread era quello
   dell'ultimo tick disponibile, uguale per tutti.

Da qui la regola: un numero plausibile non e' una prova. Ogni script destinato
al PC deve avere qui almeno un caso normale, un caso in cui i dati NON bastano,
e la verifica che nel secondo taccia invece di inventare.

I dati sono sintetici e minuscoli (qualche centinaio di tick), gli script sono
lanciati come sottoprocessi: e' esattamente quello che succede sul PC, meno la
dimensione.
"""
import lzma
import os
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

# Script che l'utente esegue sul proprio PC, fuori dal repository.
SCRIPT_PC = ["misura_spread.py", "build_tick_parquet.py", "build_tick_csv.py",
             "verifica_cache_tick.py", "download_ticks.py"]

MESE = "2026-07"
PRIMO_TICK = pd.Timestamp("2026-07-01 00:00:00", tz="UTC")
N_TICK = 600                      # un tick al secondo per dieci minuti
SPREAD_DENTRO = 0.20
SPREAD_ULTIMO = 0.70              # il valore che l'altra volta e' finito su tutto


def esegui(script, *argomenti, env=None):
    """Lancia lo script come farebbe l'utente. Restituisce il CompletedProcess."""
    ambiente = dict(os.environ)
    ambiente.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, argomenti)],
                          capture_output=True, text=True, env=ambiente, timeout=180)


def scrivi_tick(cartella, mese=MESE):
    """Un Parquet mensile di tick finti: spread 0,20 $ tranne l'ultimo, 0,70 $."""
    ts = PRIMO_TICK + pd.to_timedelta(np.arange(N_TICK), unit="s")
    bid = np.full(N_TICK, 2000.0)
    ask = bid + SPREAD_DENTRO
    ask[-1] = bid[-1] + SPREAD_ULTIMO
    df = pd.DataFrame({"timestamp": ts, "bid": bid.astype("float32"),
                       "ask": ask.astype("float32")})
    path = Path(cartella) / f"XAUUSD_ticks_{mese}.parquet"
    df.to_parquet(path, index=False)
    return path


def scrivi_operazioni(path, istanti, rischio=2.0):
    pd.DataFrame({"time": [pd.Timestamp(t, tz="UTC").isoformat() for t in istanti],
                  "rischio": rischio}).to_csv(path, index=False)
    return path


class TestMisuraSpread:
    """Lo script che misura lo spread reale all'istante di ogni operazione."""

    def test_misura_le_operazioni_dentro_la_copertura(self, tmp_path):
        tick = tmp_path / "tick"
        tick.mkdir()
        scrivi_tick(tick)
        ops = scrivi_operazioni(tmp_path / "ops.csv",
                                ["2026-07-01 00:05:00", "2026-07-01 00:08:00"])
        out = tmp_path / "misurato.csv"

        r = esegui("misura_spread.py", tick, ops, out)
        assert r.returncode == 0, r.stderr

        m = pd.read_csv(out)
        assert list(m.tick_trovato) == [1, 1]
        # tolleranza larga: i tick sono float32, 0,20 $ non e' rappresentabile esatto
        assert m.spread_ingresso.tolist() == pytest.approx([SPREAD_DENTRO] * 2, abs=1e-3)
        # il costo in R usa la colonna rischio: 0,20 $ su 2 $ di rischio = 0,10 R
        assert "0.100" in r.stdout

    def test_istante_oltre_l_ultimo_tick_non_e_misurato(self, tmp_path):
        """La regressione del numero falso: NaN, non lo spread dell'ultimo tick."""
        tick = tmp_path / "tick"
        tick.mkdir()
        scrivi_tick(tick)
        # 00:30 e' dentro il mese ma trenta minuti dopo la fine dei tick
        ops = scrivi_operazioni(tmp_path / "ops.csv",
                                ["2026-07-01 00:05:00", "2026-07-01 00:30:00"])
        out = tmp_path / "misurato.csv"

        r = esegui("misura_spread.py", tick, ops, out)
        assert r.returncode == 0, r.stderr

        m = pd.read_csv(out)
        assert list(m.tick_trovato) == [1, 0]
        assert m.spread_ingresso[0] == pytest.approx(SPREAD_DENTRO, abs=1e-3)
        assert pd.isna(m.spread_ingresso[1]), "istante fuori copertura: deve restare vuoto"
        assert "fuori dalla copertura" in r.stdout

    def test_se_nessuna_operazione_e_misurabile_lo_dice_e_non_fa_statistiche(self, tmp_path):
        tick = tmp_path / "tick"
        tick.mkdir()
        scrivi_tick(tick)
        ops = scrivi_operazioni(tmp_path / "ops.csv",
                                ["2026-07-01 02:00:00", "2026-07-01 03:00:00"])

        r = esegui("misura_spread.py", tick, ops, tmp_path / "misurato.csv")
        assert r.returncode == 0, r.stderr
        assert "NESSUNA operazione misurata" in r.stdout
        # nessuna riga di statistica: e' proprio quella che l'altra volta mentiva
        assert "spread all'ingresso" not in r.stdout
        assert "costo in R" not in r.stdout

    def test_mese_senza_parquet_e_segnalato(self, tmp_path):
        tick = tmp_path / "tick"
        tick.mkdir()
        scrivi_tick(tick)                                  # solo 2026-07
        ops = scrivi_operazioni(tmp_path / "ops.csv",
                                ["2026-07-01 00:05:00", "2026-06-15 10:00:00"])

        r = esegui("misura_spread.py", tick, ops, tmp_path / "misurato.csv")
        assert r.returncode == 0, r.stderr
        assert "2026-06" in r.stdout and "mesi senza Parquet" in r.stdout

    def test_senza_argomenti_spiega_come_si_usa(self, tmp_path):
        r = esegui("misura_spread.py")
        assert r.returncode == 1
        assert "Uso" in r.stdout


def bi5(cartella, giorno, ora, tick):
    """Scrive un'ora di cache Dukascopy. tick: (ms nell'ora, bid, ask)."""
    corpo = b"".join(
        struct.pack(">3i2f", ms, round(ask * 1000), round(bid * 1000), 1.0, 1.0)
        for ms, bid, ask in tick)                          # ask PRIMA del bid
    path = Path(cartella) / f"{giorno}_{ora:02d}.bi5"
    path.write_bytes(lzma.compress(corpo))
    return path


class TestBuildTickParquet:
    """Il convertitore da cache .bi5 a Parquet mensili."""

    def test_converte_ordina_e_tiene_ask_sopra_bid(self, tmp_path):
        cache, out = tmp_path / "cache", tmp_path / "out"
        cache.mkdir()
        # due ore, scritte in ordine sparso dentro l'ora per provare l'ordinamento
        bi5(cache, "2026-07-01", 9, [(2000, 2000.0, 2000.3), (500, 1999.0, 1999.2)])
        bi5(cache, "2026-07-01", 10, [(0, 2001.0, 2001.4)])

        r = esegui("build_tick_parquet.py", out, MESE, MESE,
                   env={"TICKS_CACHE": str(cache)})
        assert r.returncode == 0, r.stderr

        df = pd.read_parquet(out / f"XAUUSD_ticks_{MESE}.parquet")
        assert len(df) == 3
        assert df.timestamp.is_monotonic_increasing
        assert (df.ask > df.bid).all(), "ask e bid invertiti nella lettura del record"
        assert df.timestamp.iloc[0] == pd.Timestamp("2026-07-01 09:00:00.500", tz="UTC")
        assert df.bid.iloc[0] == pytest.approx(1999.0, abs=1e-3)
        assert "verifica ask >= bid: superata" in r.stdout
        assert (out / "INDICE.csv").exists()

    def test_file_corrotto_saltato_senza_fermare_la_conversione(self, tmp_path):
        cache, out = tmp_path / "cache", tmp_path / "out"
        cache.mkdir()
        bi5(cache, "2026-07-01", 9, [(0, 2000.0, 2000.3)])
        (cache / "2026-07-01_10.bi5").write_bytes(b"non e' lzma")

        r = esegui("build_tick_parquet.py", out, MESE, MESE,
                   env={"TICKS_CACHE": str(cache)})
        assert r.returncode == 0, r.stderr
        assert len(pd.read_parquet(out / f"XAUUSD_ticks_{MESE}.parquet")) == 1

    def test_cache_inesistente_e_un_errore_non_un_risultato_vuoto(self, tmp_path):
        r = esegui("build_tick_parquet.py", tmp_path / "out", MESE, MESE,
                   env={"TICKS_CACHE": str(tmp_path / "non-esiste")})
        assert r.returncode == 1
        assert "cache non trovata" in r.stdout


class TestVerificaCacheTick:
    """Il controllo di integrita' della cache, con e senza --ripara."""

    def _cache(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        bi5(cache, "2026-07-01", 9, [(0, 2000.0, 2000.3)])
        (cache / "2026-07-01_10.bi5").write_bytes(b"tronco")     # illeggibile
        (cache / "2026-07-01_11.bi5").write_bytes(b"")           # vuoto
        return cache

    def test_elenca_i_guasti_senza_cancellare_nulla(self, tmp_path):
        cache = self._cache(tmp_path)
        r = esegui("verifica_cache_tick.py", env={"TICKS_CACHE": str(cache)})
        assert r.returncode == 0, r.stderr
        assert "illeggibile" in r.stdout and "vuoto" in r.stdout
        assert len(list(cache.glob("*.bi5"))) == 3, "senza --ripara non tocca i file"

    def test_ripara_cancella_solo_i_guasti(self, tmp_path):
        cache = self._cache(tmp_path)
        (cache / "mezzo.tmp").write_bytes(b"scarto")
        r = esegui("verifica_cache_tick.py", "--ripara",
                   env={"TICKS_CACHE": str(cache)})
        assert r.returncode == 0, r.stderr
        rimasti = sorted(p.name for p in cache.iterdir())
        assert rimasti == ["2026-07-01_09.bi5"]

    def test_cache_vuota_e_un_errore(self, tmp_path):
        vuota = tmp_path / "vuota"
        vuota.mkdir()
        r = esegui("verifica_cache_tick.py", env={"TICKS_CACHE": str(vuota)})
        assert r.returncode == 1
        assert "nessun .bi5" in r.stdout


class TestPortabilita:
    """Vincoli che il PC dell'utente impone e che qui non si vedrebbero."""

    @pytest.mark.parametrize("nome", SCRIPT_PC)
    def test_non_dipende_dal_repository(self, nome):
        """Girano da soli, in una cartella qualsiasi: niente import framework."""
        testo = (SCRIPTS / nome).read_text(encoding="utf-8")
        assert "framework" not in testo, (
            f"{nome} gira fuori dal repository: non puo' importare framework")

    @pytest.mark.parametrize("nome", SCRIPT_PC)
    def test_dichiara_cosa_serve_installare(self, nome):
        """La prima riga di aiuto che l'utente legge deve dire uso e requisiti."""
        doc = (SCRIPTS / nome).read_text(encoding="utf-8").split('"""')[1]
        assert "Uso" in doc or "uso" in doc, f"{nome}: manca la riga d'uso"
        assert any(s in doc for s in ("Richiede", "Requisito", "pip install")), (
            f"{nome}: il docstring non dice cosa installare prima di eseguirlo")
