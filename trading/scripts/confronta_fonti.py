#!/usr/bin/env python3
"""Confronta le candele M1 del repository (Dukascopy) con un'altra fonte.

Serve a rispondere a "ma i dati Dukascopy sono giusti?": prende le stesse
candele M1 da un'altra banca dati e misura le differenze minuto per minuto.
Gira sul PC, non nel container (le altre fonti non sono raggiungibili da li').

Due sorgenti:

    python confronta_fonti.py mt5 2024
        Chiede le candele al terminale MT5 aperto (feed del broker, es. FP).
        Richiede:  pip install MetaTrader5   e il terminale MT5 avviato.

    python confronta_fonti.py histdata DAT_ASCII_XAUUSD_M1_2024.csv
        Legge il CSV di histdata.com (scaricato a mano dal browser:
        ascii / 1-minute bar quotes / XAU/USD / anno; dentro lo zip).

Il fuso orario dell'altra fonte NON si assume: lo stima il programma
provando tutti gli scostamenti a ore intere (-12..+12) e tenendo quello che
minimizza la differenza mediana delle chiusure. MT5 usa l'ora del server del
broker (spesso UTC+2/+3 con ora legale), histdata usa EST fissa (UTC-5):
tutti casi coperti dalla stima.

Output compatto: copertura, differenze per mese, verdetto. I prezzi del
repository sono BID; anche MT5 e histdata quotano barre sul bid, quindi il
confronto e' omogeneo. Differenze mediane sotto i 10-20 centesimi sono
normali fra liquidity provider diversi su XAUUSD.
"""
import os
import sys

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(QUI, "..", ".."))


def carica_repo(anno: int) -> pd.DataFrame:
    percorso = os.path.join(REPO, "data", "XAUUSD_M1", f"XAUUSD_M1_{anno}.parquet")
    if not os.path.exists(percorso):
        raise SystemExit(f"manca {percorso}: questo anno non e' nel repository")
    df = pd.read_parquet(percorso)
    if "timestamp" in df.columns:
        df = df.set_index("timestamp")
    df.index = pd.to_datetime(df.index, utc=True)
    return df[["open", "high", "low", "close"]]


def da_mt5(anno: int) -> pd.DataFrame:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        raise SystemExit("manca il pacchetto: pip install MetaTrader5")
    import datetime as dt
    import time
    if not mt5.initialize():
        raise SystemExit(f"MT5 non risponde (il terminale e' aperto?): {mt5.last_error()}")
    try:
        # il simbolo puo' chiamarsi diversamente da broker a broker
        nomi = [s.name for s in mt5.symbols_get()
                if "XAU" in s.name.upper() or "GOLD" in s.name.upper()]
        if not nomi:
            raise SystemExit("nessun simbolo XAU/GOLD presso questo broker")
        simbolo = "XAUUSD" if "XAUUSD" in nomi else nomi[0]
        mt5.symbol_select(simbolo, True)
        print(f"simbolo: {simbolo}  (trovati: {', '.join(nomi[:6])})")

        # per POSIZIONE, non per data: copy_rates_range soffre di conversioni
        # di fuso sballate su alcune versioni (restituiva 1 barra a chiamata);
        # chiedere "le N barre prima della posizione P" non passa da nessuna
        # data e spinge comunque il terminale a scaricare lo storico dal server
        PASSO = 50_000
        pezzi = []
        pos = 0
        limite = dt.datetime(anno, 1, 1) - dt.timedelta(days=2)
        while True:
            barre = None
            for _ in range(6):
                barre = mt5.copy_rates_from_pos(simbolo, mt5.TIMEFRAME_M1, pos, PASSO)
                if barre is not None and len(barre) > 0:
                    break
                time.sleep(2)
            if barre is None or len(barre) == 0:
                break
            pezzi.append(pd.DataFrame(barre))
            prima = dt.datetime.utcfromtimestamp(int(barre[0]["time"]))
            print(f"  ...indietro fino al {prima:%Y-%m-%d} "
                  f"({sum(len(x) for x in pezzi):,} barre)".replace(",", "."))
            if prima < limite or len(barre) < PASSO:
                break
            pos += len(barre)
    finally:
        mt5.shutdown()
    if not pezzi:
        raise SystemExit("il broker non ha fornito nessuna barra M1")
    df = pd.concat(pezzi).drop_duplicates(subset="time")
    epoca = df["time"].astype("int64")
    ini = int(dt.datetime(anno, 1, 1).timestamp()) - 86400 * 2
    fine = int(dt.datetime(anno + 1, 1, 1).timestamp()) + 86400 * 2
    df = df[(epoca >= ini) & (epoca <= fine)]
    if len(df) < 1000:
        raise SystemExit(
            f"solo {len(df)} barre nel {anno}: lo storico M1 del broker non "
            "arriva cosi' indietro. Riprova con un anno piu' recente (es. 2026) "
            "e, se serve, alza 'Max barre nel grafico' in "
            "Strumenti > Opzioni > Grafici e riavvia MT5")
    # l'orario e' quello del SERVER del broker: lo scostamento vero lo stima
    # stima_scostamento(), qui basta un indice coerente
    df["ts"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.set_index("ts")[["open", "high", "low", "close"]]


def da_histdata(percorso: str) -> pd.DataFrame:
    df = pd.read_csv(percorso, sep=";", header=None,
                     names=["ts", "open", "high", "low", "close", "vol"])
    df["ts"] = pd.to_datetime(df["ts"], format="%Y%m%d %H%M%S", utc=True)
    return df.set_index("ts")[["open", "high", "low", "close"]]


def stima_scostamento(repo: pd.DataFrame, altra: pd.DataFrame) -> int:
    """Ore da AGGIUNGERE all'altra fonte perche' combaci con l'UTC del repo."""
    migliore, minimo = 0, np.inf
    for ore in range(-12, 13):
        spostata = altra.index + pd.Timedelta(hours=ore)
        comune = repo.index.intersection(spostata)
        if len(comune) < 1000:
            continue
        diff = (altra.set_axis(spostata).loc[comune, "close"]
                - repo.loc[comune, "close"]).abs().median()
        if diff < minimo:
            migliore, minimo = ore, diff
    if not np.isfinite(minimo):
        raise SystemExit("meno di 1000 minuti in comune con qualunque fuso: "
                         "l'altra fonte copre davvero questo anno?")
    return migliore


def confronta(repo: pd.DataFrame, altra: pd.DataFrame, nome: str) -> None:
    pd.set_option("display.width", 200)
    ore = stima_scostamento(repo, altra)
    altra = altra.set_axis(altra.index + pd.Timedelta(hours=ore))
    comune = repo.index.intersection(altra.index)
    a, b = repo.loc[comune], altra.loc[comune]

    print(f"scostamento orario stimato di {nome}: {ore:+d} h rispetto all'UTC")
    print(f"minuti: comuni {len(comune):,}  solo Dukascopy {len(repo) - len(comune):,}"
          f"  solo {nome} {len(altra) - len(comune):,}".replace(",", "."))

    diff = (b["close"] - a["close"])
    righe = []
    for mese, d in diff.groupby(diff.index.tz_localize(None).to_period("M")):
        righe.append([str(mese), len(d), d.abs().median(), d.abs().quantile(0.95),
                      d.abs().max(), (d.abs() > 0.50).mean() * 100])
    tab = pd.DataFrame(righe, columns=["mese", "minuti", "med $", "p95 $", "max $", ">0,5$ %"])
    print(tab.round(3).to_string(index=False))

    med = diff.abs().median()
    print(f"\nTOTALE  mediana {med:.3f} $  p95 {diff.abs().quantile(0.95):.3f} $"
          f"  sistematico {diff.median():+.3f} $ (>0 = {nome} quota piu' alto)")
    if med <= 0.20:
        print("verdetto: differenze da normale pluralita' di liquidity provider, "
              "le due fonti raccontano lo stesso mercato")
    elif med <= 0.50:
        print("verdetto: differenze percettibili ma compatibili; da tenere d'occhio "
              "sugli stop stretti")
    else:
        print("verdetto: differenze GROSSE, da capire prima di fidarsi di "
              "qualunque backtest")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    modo = sys.argv[1]
    if modo == "mt5":
        anno = int(sys.argv[2])
        confronta(carica_repo(anno), da_mt5(anno), "broker MT5")
    elif modo == "histdata":
        altra = da_histdata(sys.argv[2])
        anno = int(altra.index[len(altra) // 2].year)
        confronta(carica_repo(anno), altra, "histdata")
    else:
        raise SystemExit(f"modo sconosciuto: {modo} (uso: mt5 <anno> | histdata <csv>)")


if __name__ == "__main__":
    main()
