#!/usr/bin/env python3
"""Livelli ATTIVI adesso: zone order block e contesto, dal terminale MT5.

Risponde alla domanda operativa "dove sta il prossimo livello buono per
comprare (o vendere)?" applicando le regole gia' misurate del progetto ai
prezzi VERI del momento, presi dal terminale aperto. Non e' una previsione:
e' il calcolo delle zone che la ricerca ha trovato valide (appendice AJ: il
vantaggio sta nella zona RAFFINATA, +1,342 R/op su sette anni).

Mostra, per ogni timeframe richiesto:
  - stato della struttura (rialzista/ribassista/indeterminata), causale
  - le zone order block ATTIVE, non invalidate e non scadute, con la zona
    raffinata evidenziata e la distanza dal prezzo corrente

Uso:  python3 livelli_ora.py            (M33 H2 H6, i timeframe dello studio)
      python3 livelli_ora.py M33 H3
Richiede il terminale MT5 aperto e il pacchetto MetaTrader5.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, resample_tf                # noqa: E402
from framework.structure import trend_state_series                # noqa: E402
from framework.taratura import UFFICIALE as T                     # noqa: E402

from export_lab import zone_ob                                    # noqa: E402

BARRE_M1 = 200_000        # storico M1 da chiedere: copre ~5 mesi
VALIDITA = 30             # candele di vita di una zona, come negli studi


def da_mt5():
    """M1 recenti e prezzo corrente dal terminale aperto."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        raise SystemExit("manca il pacchetto: pip install MetaTrader5")
    if not mt5.initialize():
        raise SystemExit(f"MT5 non risponde (il terminale e' aperto?): {mt5.last_error()}")
    try:
        nomi = [s.name for s in mt5.symbols_get()
                if "XAU" in s.name.upper() or "GOLD" in s.name.upper()]
        if not nomi:
            raise SystemExit("nessun simbolo XAU/GOLD presso questo broker")
        simbolo = "XAUUSD" if "XAUUSD" in nomi else nomi[0]
        mt5.symbol_select(simbolo, True)
        barre = mt5.copy_rates_from_pos(simbolo, mt5.TIMEFRAME_M1, 0, BARRE_M1)
        tick = mt5.symbol_info_tick(simbolo)
        prezzo = float(tick.bid) if tick else float(barre[-1]["close"])
        spread = (float(tick.ask) - float(tick.bid)) if tick else float("nan")
    finally:
        mt5.shutdown()
    if barre is None or len(barre) == 0:
        raise SystemExit("il terminale non ha restituito barre M1")
    df = pd.DataFrame(barre)
    df["ts"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("ts")[["open", "high", "low", "close", "tick_volume"]]
    df.columns = ["open", "high", "low", "close", "volume"]
    return simbolo, df, prezzo, spread


def main():
    tfs = sys.argv[1:] or ["M33", "H2", "H6"]
    for tf in tfs:
        if tf not in TIMEFRAMES:
            raise SystemExit(f"timeframe sconosciuto: {tf}")
    simbolo, m1, prezzo, spread = da_mt5()
    # l'orario del server non e' UTC: lo si stima dall'ultima candela nota
    print(f"{simbolo}  prezzo {prezzo:.2f}  spread {spread:.2f} $  "
          f"ultima candela {m1.index[-1]:%Y-%m-%d %H:%M} (ora del server)")
    print(f"storico caricato: {len(m1):,} minuti\n".replace(",", "."))

    for tf in tfs:
        tfd = resample_tf(m1, tf)
        stato = trend_state_series(tfd, T.frattale_k, pd.Timedelta(TIMEFRAMES[tf]))
        s = int(stato.iloc[-1]) if len(stato) else 0
        verso = {1: "rialzista", -1: "ribassista", 0: "indeterminata"}[s]
        z = zone_ob(tfd, T.frattale_k, TIMEFRAMES[tf])
        adesso = tfd.index[-1] + pd.Timedelta(TIMEFRAMES[tf])
        if z.empty:
            print(f"--- {tf}: struttura {verso} — nessuna zona\n")
            continue
        # la scadenza va ricalcolata: zone_ob la tronca all'ultima candela
        # disponibile, quindi al BORDO DESTRO (che e' il caso di quando si
        # opera dal vivo) le zone appena nate risulterebbero gia' scadute
        passo = pd.Timedelta(TIMEFRAMES[tf])
        scadenza = z.attiva_da + VALIDITA * passo
        vive = z[(z.attiva_da <= adesso) & (scadenza > adesso)
                 & (z.invalidata_il.isna() | (z.invalidata_il > adesso))].copy()
        vive["scade_il"] = scadenza[vive.index]
        print(f"--- {tf}: struttura {verso} — {len(vive)} zone attive")
        if vive.empty:
            print()
            continue
        righe = []
        for _, r in vive.iterrows():
            lato = "BUY" if r.lato == 1 else "SELL"
            # per una zona buy il prezzo deve SCENDERE al bordo alto
            bordo = r.alto if r.lato == 1 else r.basso
            dist = (prezzo - bordo) if r.lato == 1 else (bordo - prezzo)
            raff = (f"{r.rbasso:.2f}-{r.ralto:.2f}"
                    if np.isfinite(r.rbasso) else "—")
            righe.append({"lato": lato, "zona": f"{r.basso:.2f}-{r.alto:.2f}",
                          "RAFFINATA": raff, "distanza $": round(dist, 2),
                          "attiva da": r.attiva_da.strftime("%d/%m %H:%M"),
                          "scade": r.scade_il.strftime("%d/%m %H:%M")})
        tab = pd.DataFrame(righe).sort_values("distanza $", key=abs)
        pd.set_option("display.width", 200)
        print(tab.to_string(index=False))
        print()

    print("Come leggerlo: la colonna RAFFINATA e' la zona che conta (appendice")
    print("AJ). Distanza positiva = il prezzo deve tornare indietro fino li'.")
    print("Una zona NON e' un segnale da sola (appendice W): serve il segnale")
    print("della strategia, e la struttura del timeframe deve essere concorde.")


if __name__ == "__main__":
    main()
