#!/usr/bin/env python3
"""Dati macro e di posizionamento allineati all'oro, SENZA informazioni future.

Protocollo: docs/macro-oro-registrazione.md. Uscite (separate come sempre):

    D:\\ricerca_macro\\scoperta\\MACRO_D1.parquet   (giornate fino al 2017)
    D:\\ricerca_macro\\verifica\\MACRO_D1.parquet   (dal 2018)
    D:\\ricerca_macro\\scoperta|verifica\\COT_SETTIMANALE.parquet

Giornata dell'oro D = 22:00 UTC di D-1 -> 22:00 UTC di D (paniere D1). Una
decisione presa alla CHIUSURA della giornata D (22:00 UTC) puo' usare solo
valori gia' pubblicati a quell'ora. Regole fisse (prudenti):

- VIX, GVZ (chiusura CBOE 16:15 New York <= 21:15 UTC): valore della data D.
- Tesoro (tassi reali e nominali, pubblicati in serata a New York), Fed funds
  effettivo (pubblicato la mattina dopo), ETF GLD (aggiornato dopo la
  chiusura USA): valore della data **D-1** (ultimo giorno USA precedente).
- Indice del dollaro sintetico: dai cambi del paniere alla stessa chiusura
  22:00 UTC (e' prezzo, non macro): data D. Pesi ICE DXY senza la corona
  svedese, rinormalizzati: EUR 57,6 JPY 13,6 GBP 11,9 CAD 9,1 CHF 3,6.
- COT (posizioni del martedi', pubblicate il venerdi' alle 15:30 New York):
  utilizzabile dalla chiusura della giornata del **venerdi'** di pubblicazione
  (se il venerdi' e' festivo il CFTC pubblica il lunedi': si usa la data di
  pubblicazione = martedi' + 3 giorni lavorativi, prudente).
"""
from __future__ import annotations

import glob
import io
import os
import zipfile

import numpy as np
import pandas as pd

DATI = r"D:\ricerca_macro\dati"
OUT = r"D:\ricerca_macro"
PAN = r"D:\ricerca_multi"
TAGLIO = pd.Timestamp("2018-01-01")
DXY = {"EURUSD": (-0.576 / 0.958), "USDJPY": 0.136 / 0.958, "GBPUSD": -0.119 / 0.958,
       "USDCAD": 0.091 / 0.958, "USDCHF": 0.036 / 0.958}


def paniere():
    p = pd.concat([pd.read_parquet(os.path.join(PAN, c, "PANIERE_D1.parquet"))
                   for c in ("scoperta", "verifica")], ignore_index=True)
    oro = p[p.mercato == "XAUUSD"].set_index("giorno")[["open", "high", "low", "close", "valida"]]
    fx = p[p.mercato.isin(list(DXY))].pivot(index="giorno", columns="mercato", values="close")
    logdxy = sum(w * np.log(fx[m]) for m, w in DXY.items())
    oro["dxy_sint"] = np.exp(logdxy - logdxy.dropna().iloc[0]) * 100
    return oro.sort_index()


def tesoro():
    out = {}
    for tipo in ("reali", "nominali"):
        fr = []
        for f in sorted(glob.glob(os.path.join(DATI, "tesoro", f"{tipo}_*.csv"))):
            d = pd.read_csv(f)
            d["Date"] = pd.to_datetime(d["Date"], format="%m/%d/%Y")
            fr.append(d.set_index("Date"))
        t = pd.concat(fr).sort_index()
        t = t[~t.index.duplicated()]
        out[tipo] = t
    r, n = out["reali"], out["nominali"]
    d = pd.DataFrame({"reale10": r["10 YR"], "reale5": r["5 YR"],
                      "nom10": n["10 Yr"], "nom2": n["2 Yr"]})
    d["breakeven10"] = d["nom10"] - d["reale10"]
    return d


def cboe(nome):
    d = pd.read_csv(os.path.join(DATI, "cboe", f"{nome}_History.csv"))
    d["DATE"] = pd.to_datetime(d["DATE"], format="%m/%d/%Y")
    col = "CLOSE" if "CLOSE" in d.columns else d.columns[-1]
    return d.set_index("DATE")[col].rename(nome.lower())


def effr():
    d = pd.read_csv(os.path.join(DATI, "nyfed", "EFFR.csv"))
    d["data"] = pd.to_datetime(d["Effective Date"], format="%m/%d/%Y")
    return d.set_index("data")["Rate (%)"].sort_index().rename("effr")


def gld():
    d = pd.read_excel(os.path.join(DATI, "gld", "GLD_archivio.xlsx"), "US GLD Historical Archive")
    d["data"] = pd.to_datetime(d["Date"], format="%d-%b-%Y", errors="coerce")
    d = d.dropna(subset=["data"]).set_index("data").sort_index()
    t = pd.to_numeric(d["Tonnes of Gold"], errors="coerce").rename("gld_tonnellate")
    return t[t > 0]


def allinea(oro, serie, ritardo_giorni):
    """Valore noto alla chiusura della giornata D: ultimo dato con data <= D - ritardo."""
    s = serie.dropna().sort_index()
    chiavi = oro.index - pd.Timedelta(days=ritardo_giorni)
    idx = s.index.searchsorted(chiavi, side="right") - 1
    v = np.where(idx >= 0, s.values[np.clip(idx, 0, None)], np.nan)
    return pd.Series(v, index=oro.index, name=serie.name)


def cot():
    righe = []
    for f in sorted(glob.glob(os.path.join(DATI, "cftc", "fut_disagg_txt_*.zip"))):
        with zipfile.ZipFile(f) as z:
            for n in z.namelist():
                d = pd.read_csv(io.BytesIO(z.read(n)), low_memory=False)
                d = d[d["Market_and_Exchange_Names"].str.startswith("GOLD - COMMODITY EXCHANGE")]
                righe.append(d)
    dis = pd.concat(righe)
    data_col = "Report_Date_as_YYYY-MM-DD"
    dis["data"] = pd.to_datetime(dis[data_col])
    dis = dis.drop_duplicates("data").set_index("data").sort_index()
    out = pd.DataFrame({
        "oi": dis["Open_Interest_All"],
        "mm_long": dis["M_Money_Positions_Long_All"], "mm_short": dis["M_Money_Positions_Short_All"],
        "prod_long": dis["Prod_Merc_Positions_Long_All"], "prod_short": dis["Prod_Merc_Positions_Short_All"],
        "swap_long": dis["Swap_Positions_Long_All"], "swap_short": dis["Swap__Positions_Short_All"]
        if "Swap__Positions_Short_All" in dis.columns else dis["Swap_Positions_Short_All"],
        "piccoli_long": dis["NonRept_Positions_Long_All"], "piccoli_short": dis["NonRept_Positions_Short_All"],
    })
    # pubblicazione: martedi' + 3 giorni lavorativi (di norma il venerdi')
    out["pubblicato"] = out.index + pd.offsets.BDay(3)
    return out


def main():
    oro = paniere()
    t = tesoro()
    for c in t.columns:
        oro[c] = allinea(oro, t[c], 1)
    oro["effr"] = allinea(oro, effr(), 1)
    oro["gld_tonnellate"] = allinea(oro, gld(), 1)
    for nome in ("VIX", "GVZ"):
        oro[nome.lower()] = allinea(oro, cboe(nome), 0)
    oro = oro[oro.index >= "2009-01-01"]
    c = cot()
    for cart, m in (("scoperta", oro.index < TAGLIO), ("verifica", oro.index >= TAGLIO)):
        os.makedirs(os.path.join(OUT, cart), exist_ok=True)
        oro[m].to_parquet(os.path.join(OUT, cart, "MACRO_D1.parquet"))
        mc = (c["pubblicato"] < TAGLIO) if cart == "scoperta" else (c["pubblicato"] >= TAGLIO)
        c[mc].to_parquet(os.path.join(OUT, cart, "COT_SETTIMANALE.parquet"))
        print(f"== {cart}: {m.sum()} giornate, COT {mc.sum()} settimane")
        print(oro[m].notna().mean().round(3).to_string())


if __name__ == "__main__":
    main()
