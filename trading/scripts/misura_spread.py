#!/usr/bin/env python3
"""Misura lo spread reale nell'istante esatto di ogni operazione.

I Parquet dei tick pesano oltre un gigabyte e non ha senso spostarli: questo
script gira sul computer che li ha e produce un file di poche decine di KB,
con una riga per operazione. E' quello il dato che serve per rifare i conti.

Uso (Windows, PowerShell):
    python misura_spread.py C:\\dukascopy\\parquet_out operazioni.csv spread_misurato.csv

Ingresso: ``operazioni.csv`` con almeno le colonne ``time`` (ISO UTC) e
``rischio``. Uscita: lo stesso elenco piu'

- ``spread_ingresso``   spread dell'ultimo tick prima dell'ingresso
- ``spread_mediano_60s`` mediana dello spread nel minuto che precede
- ``spread_max_60s``    il peggiore dello stesso minuto
- ``tick_trovato``      0 se per quell'istante non ci sono tick in cache

Richiede: pip install pandas pyarrow numpy
"""
import os
import sys

import numpy as np
import pandas as pd


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    dir_tick = sys.argv[1]
    path_ops = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else "spread_misurato.csv"

    ops = pd.read_csv(path_ops)
    ops["time"] = pd.to_datetime(ops.time, utc=True)
    ops["mese"] = ops.time.dt.strftime("%Y-%m")
    for c in ("spread_ingresso", "spread_mediano_60s", "spread_max_60s"):
        ops[c] = np.nan
    ops["tick_trovato"] = 0

    print(f"{len(ops)} operazioni, {ops.mese.nunique()} mesi da controllare\n",
          flush=True)
    mancanti = []
    for mese, gruppo in ops.groupby("mese"):
        path = os.path.join(dir_tick, f"XAUUSD_ticks_{mese}.parquet")
        if not os.path.exists(path):
            mancanti.append(f"{mese} ({len(gruppo)} operazioni)")
            continue
        t = pd.read_parquet(path, columns=["timestamp", "bid", "ask"])
        ts = t.timestamp.values.astype("datetime64[ms]").astype("int64")
        spread = (t.ask.values - t.bid.values).astype("float64")
        primo, ultimo = int(ts[0]), int(ts[-1])
        trovate = fuori = 0
        for i, riga in gruppo.iterrows():
            fine = np.int64(riga.time.value // 1_000_000)     # ns -> ms
            inizio = fine - 60_000
            # L'istante deve stare DENTRO la copertura del file. Senza questo
            # controllo un istante successivo all'ultimo tick otterrebbe lo
            # spread dell'ultimo tick disponibile: una misura falsa, e tutta
            # uguale per ogni operazione fuori copertura.
            if not (primo <= fine <= ultimo):
                fuori += 1
                continue
            b = int(np.searchsorted(ts, fine, side="right"))
            a = int(np.searchsorted(ts, inizio, side="left"))
            if b == 0:
                continue
            ops.at[i, "spread_ingresso"] = float(spread[b - 1])
            finestra = spread[a:b]
            if len(finestra):
                ops.at[i, "spread_mediano_60s"] = float(np.median(finestra))
                ops.at[i, "spread_max_60s"] = float(finestra.max())
            ops.at[i, "tick_trovato"] = 1
            trovate += 1
        avviso = f"   ({fuori} fuori dalla copertura del file)" if fuori else ""
        if fuori:
            da = pd.Timestamp(primo, unit="ms", tz="UTC")
            al = pd.Timestamp(ultimo, unit="ms", tz="UTC")
            avviso += f"  [tick da {da:%d/%m %H:%M} a {al:%d/%m %H:%M}]"
        print(f"{mese}: {trovate}/{len(gruppo)} operazioni misurate{avviso}",
              flush=True)

    ops.drop(columns=["mese"]).to_csv(out, index=False)
    ok = ops[ops.tick_trovato == 1]
    print(f"\n{len(ok)}/{len(ops)} operazioni misurate -> {out}")
    if len(ok) == 0:
        print("NESSUNA operazione misurata: i tick non coprono questi istanti.")
        return
    if mancanti:
        print("mesi senza Parquet: " + ", ".join(mancanti))
    if len(ok):
        print(f"\nspread all'ingresso   mediano {ok.spread_ingresso.median():.3f} $   "
              f"medio {ok.spread_ingresso.mean():.3f} $   "
              f"massimo {ok.spread_ingresso.max():.3f} $")
        costo = ok.spread_ingresso / ok.rischio
        print(f"costo in R            mediano {costo.median():.3f}   "
              f"medio {costo.mean():.3f}   (assunto finora: 0,30 $ fissi)")


if __name__ == "__main__":
    main()
