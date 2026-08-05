#!/usr/bin/env python3
"""Confronta il nucleo dell'EA col motore Python, operazione per operazione.

E' il passo 3 di `docs/AVVIO-MT5-VPS.md`, fatto qui invece che dentro MT5:
il nucleo dell'EA (`VwapReclaimCore.mqh`) viene compilato con g++ e alimentato
con le STESSE candele M1 che legge `framework.segnali.genera`. Poi si
confrontano i due elenchi: stesso istante, stesso lato, stesso stop, stesso
rischio.

Non sostituisce il backtest dentro MT5 — quello misura anche fill, spread e
ordine fra stop e obiettivo, che qui non esistono — ma esaurisce la parte che
si puo' falsificare senza il terminale: la LOGICA DEL SEGNALE. Se qui ci sono
divergenze, dentro MT5 ci sarebbero le stesse piu' le altre.

Uso:
    python3 confronta.py                    # 2020-2026, confronto sul 2025-01/2026-06
    python3 confronta.py 2023 2026 2025-01 2026-06

Richiede: pandas, pyarrow, g++ (gia' presenti nel container).
"""
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

QUI = Path(__file__).resolve().parent
REPO = QUI.parents[3]
sys.path.insert(0, str(REPO / "trading"))

from framework.data import load_m1                       # noqa: E402
from framework.segnali import genera                     # noqa: E402
from framework.taratura import UFFICIALE as T            # noqa: E402

# La mediana ATR di riferimento e' congelata sul 2020-2024 e nell'EA e' un
# parametro: il terminale non ha abbastanza storia per calcolarla. Qui va
# passata esplicitamente a genera(), altrimenti il Python la ricalcola dagli
# anni presenti nella serie e i due motori userebbero due numeri diversi nei
# mesi ad alta volatilita'.
MEDIANA_ATR = 25.5968

SCRATCH = Path(os.environ.get("SCRATCH", "/tmp")) / "vwap-reclaim"


def esporta_m1(m1: pd.DataFrame, path: Path) -> None:
    """Le stesse candele, nel formato che legge il banco: epoch,o,h,l,c,v."""
    # NON dividere per 10**9 dando per scontati i nanosecondi: l'archivio e'
    # in datetime64[ms] e il risultato sarebbe 1672 invece di 1672700400,
    # cioe' il 1970. Il banco leggeva date assurde e non chiudeva mai una
    # candela. Convertire ai secondi in modo esplicito non dipende dall'unita'.
    epoch = m1.index.tz_convert(None).astype("datetime64[s]").astype("int64")
    out = pd.DataFrame({
        "epoch": epoch,
        "open": m1.open.values, "high": m1.high.values,
        "low": m1.low.values, "close": m1.close.values,
        "volume": m1.volume.values,
    })
    out.to_csv(path, index=False, header=False,
               float_format="%.5f", lineterminator="\n")


def esegui_banco(csv_m1: Path, out: Path) -> pd.DataFrame:
    banco = QUI / "banco"
    sorgente = QUI / "banco.cpp"
    if not banco.exists() or banco.stat().st_mtime < sorgente.stat().st_mtime:
        subprocess.run(["g++", "-O2", "-o", str(banco), str(sorgente)],
                       check=True, cwd=QUI)
    with open(out, "w") as f:
        r = subprocess.run([str(banco), str(csv_m1)], stdout=f, check=True,
                           stderr=subprocess.PIPE, text=True)
    print("banco:", r.stderr.strip())
    d = pd.read_csv(out, parse_dates=["time", "barra"])
    if len(d) == 0:                       # niente da localizzare, e va detto
        print("ATTENZIONE: il banco non ha prodotto nessun segnale")
        d["time"] = pd.to_datetime([], utc=True)
        return d
    d["time"] = d.time.dt.tz_localize("UTC")
    return d


def riferimento(m1: pd.DataFrame) -> pd.DataFrame:
    """I segnali del motore Python: grezzi, piu' il flag delle conferme.

    genera() NON applica le conferme M33/H12 ne' il ritracciamento M12: le
    registra come colonne c_<tf> e il filtro lo mette chi consuma il risultato
    (prepara_verifiche.py). Il tetto di tre al giorno e l'attesa di trenta
    minuti sono percio' consumati anche dai segnali che le conferme
    scarteranno, ed e' per questo che il nucleo dell'EA distingue "consuma"
    da "apre".
    """
    ops = genera(m1, T, mediana_atr=MEDIANA_ATR)
    d = pd.DataFrame([{k: o[k] for k in ("time", "lato", "entry", "stop",
                                         "rischio")}
                      | {f"c_{tf}": o[f"c_{tf}"] for tf in T.timeframes}
                      for o in ops])
    d["ufficiale"] = (d[[f"c_{tf}" for tf in T.conferme]].all(axis=1)
                      & ~d[[f"c_{tf}" for tf in T.ritracciamento]].any(axis=1))
    return d


def confronta(py: pd.DataFrame, ea: pd.DataFrame, etichetta: str) -> int:
    """Allinea i due elenchi sull'istante e conta le divergenze."""
    a = py.set_index("time").sort_index()
    b = ea.set_index("time").sort_index()
    solo_py = a.index.difference(b.index)
    solo_ea = b.index.difference(a.index)
    comuni = a.index.intersection(b.index)

    diff_lato = diff_stop = diff_entry = diff_rischio = 0
    for t in comuni:
        ra, rb = a.loc[t], b.loc[t]
        if ra.lato != rb.lato:
            diff_lato += 1
        if abs(float(ra.entry) - float(rb.entry)) > 1e-4:
            diff_entry += 1
        if abs(float(ra.stop) - float(rb.stop)) > 1e-4:
            diff_stop += 1
        if abs(float(ra.rischio) - float(rb.rischio)) > 1e-4:
            diff_rischio += 1

    tot = len(solo_py) + len(solo_ea) + diff_lato + diff_entry + diff_stop + diff_rischio
    print(f"\n--- {etichetta} ---")
    print(f"motore Python {len(a):>5}   nucleo EA {len(b):>5}   in comune {len(comuni):>5}")
    print(f"solo Python {len(solo_py):>4} · solo EA {len(solo_ea):>4} · "
          f"lato {diff_lato} · entry {diff_entry} · stop {diff_stop} · "
          f"rischio {diff_rischio}")
    if tot == 0:
        print("NESSUNA DIVERGENZA")
    else:
        print(f"DIVERGENZE: {tot}")
        for t in list(solo_py)[:5]:
            print(f"  solo Python  {t}  {a.loc[t].lato}  stop {a.loc[t].stop:.2f}")
        for t in list(solo_ea)[:5]:
            print(f"  solo EA      {t}  {b.loc[t].lato}  stop {b.loc[t].stop:.2f}")
    return tot


def main():
    anni_da = int(sys.argv[1]) if len(sys.argv) > 1 else 2020
    anni_a = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    da = sys.argv[3] if len(sys.argv) > 3 else "2025-01"
    a = sys.argv[4] if len(sys.argv) > 4 else "2026-06"

    SCRATCH.mkdir(parents=True, exist_ok=True)
    m1 = load_m1(str(REPO / "data" / "XAUUSD_M1"),
                 years=list(range(anni_da, anni_a + 1)))

    csv_m1 = SCRATCH / f"m1_{anni_da}_{anni_a}.csv"
    if not csv_m1.exists() or csv_m1.stat().st_size == 0:
        esporta_m1(m1, csv_m1)
    print(f"M1 esportate in {csv_m1} ({csv_m1.stat().st_size/1e6:.0f} MB)")

    ea = esegui_banco(csv_m1, SCRATCH / "segnali_ea.csv")
    py = riferimento(m1)

    # la finestra di confronto: entrambi i motori hanno visto la stessa
    # storia PRIMA di questa finestra, altrimenti differirebbero solo perche'
    # uno dei due si e' riscaldato meno
    inizio = pd.Timestamp(da + "-01", tz="UTC")
    fine = (pd.Period(a, "M").end_time).tz_localize("UTC")
    py_f = py[(py.time >= inizio) & (py.time <= fine)]
    ea_f = ea[(ea.time >= inizio) & (ea.time <= fine)]

    n1 = confronta(py_f, ea_f[ea_f.consuma == 1],
                   f"segnali grezzi {da} -> {a} (quelli che consumano i posti)")
    n2 = confronta(py_f[py_f.ufficiale], ea_f[ea_f.apre == 1],
                   f"operazioni vere {da} -> {a} (con conferme M33+H12, M12 contrario)")

    print(f"\n{'=' * 60}")
    if n1 + n2 == 0:
        print("Nucleo EA e motore Python producono le stesse operazioni.")
    else:
        print(f"{n1 + n2} divergenze: l'EA NON va messo su nessun conto.")
    return 0 if n1 + n2 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
