#!/usr/bin/env python3
"""Order block: definizione operativa e test come quarta conferma.

DEFINIZIONE (data dall'utente, il suo bot li usa cosi')
- rialzista: l'ultima candela con chiusura sotto l'apertura prima del movimento
  che rompe uno swing high. Zona = dal MINIMO dell'ombra all'APERTURA, cioe' al
  bordo superiore del corpo: l'ombra in alto non fa parte della zona.
- ribassista: simmetrico. Ultima candela con chiusura sopra l'apertura prima
  della rottura al ribasso. Zona = dall'APERTURA (bordo inferiore del corpo) al
  MASSIMO dell'ombra.
- causale: la zona esiste solo dalla CHIUSURA della candela che rompe. Prima
  non si sapeva che ci sarebbe stata una rottura, quindi usarla prima e'
  lookahead.
- invalidata quando una candela chiude oltre il lato lontano della zona
  (sotto il minimo, per una rialzista).
- scade dopo un numero fissato di candele.

IPOTESI PRE-REGISTRATA: gli ingressi che cadono dentro un order block attivo e
concorde alla direzione rendono di piu', perche' e' dove stanno gli ordini in
attesa. Se non si vede differenza, l'idea si scarta.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/workspace/sviluppo-strategie-e-bot/trading")
from framework.data import TIMEFRAMES, load_m1, resample_tf     # noqa: E402
from framework.gestione import valuta                           # noqa: E402
from framework.segnali import genera                            # noqa: E402
from framework.taratura import UFFICIALE as T                   # noqa: E402

pd.set_option("display.width", 220)
INDIETRO = 10        # quante candele si guarda indietro per trovare la candela
VALIDITA = 30        # dopo quante candele la zona scade


def order_blocks(df, k=3, freq="1h", indietro=INDIETRO, validita=VALIDITA):
    """Zone di order block su un timeframe, causali.

    Ritorna un DataFrame con: attiva_da (istante), lato (+1/-1), basso, alto,
    scade_il (istante), invalidata_il (istante o NaT).
    """
    freq = pd.Timedelta(freq)
    hi, lo = df.high.values, df.low.values
    op, cl = df.open.values, df.close.values
    idx = df.index
    n = len(df)
    ultimo_sh = ultimo_sl = None
    zone = []
    for i in range(n):
        j = i - k
        if j >= k:
            if (hi[j - k:j] < hi[j]).all() and (hi[j + 1:j + k + 1] < hi[j]).all():
                ultimo_sh = hi[j]
            if (lo[j - k:j] > lo[j]).all() and (lo[j + 1:j + k + 1] > lo[j]).all():
                ultimo_sl = lo[j]
        for lato, rotto in ((1, ultimo_sh is not None and cl[i] > ultimo_sh),
                            (-1, ultimo_sl is not None and cl[i] < ultimo_sl)):
            if not rotto:
                continue
            # la candela: l'ultima contraria al movimento, guardando indietro
            trovata = None
            for b in range(i, max(-1, i - indietro), -1):
                contraria = (cl[b] < op[b]) if lato == 1 else (cl[b] > op[b])
                if contraria:
                    trovata = b
                    break
            if trovata is not None:
                # zona asimmetrica: il lato "interno" e' il corpo, quello
                # "esterno" e' l'ombra. Rialzista: [minimo, apertura].
                # Ribassista: [apertura, massimo].
                if lato == 1:
                    basso, alto = float(lo[trovata]), float(op[trovata])
                else:
                    basso, alto = float(op[trovata]), float(hi[trovata])
                zone.append({"attiva_da": idx[i] + freq, "lato": lato,
                             "basso": basso, "alto": alto,
                             "scade_il": idx[min(i + validita, n - 1)] + freq,
                             "barra_rottura": i})
            if lato == 1:
                ultimo_sh = None
            else:
                ultimo_sl = None

    z = pd.DataFrame(zone)
    if z.empty:
        return z
    # invalidazione: prima chiusura oltre il lato lontano, dopo l'attivazione
    inval = []
    for _, r in z.iterrows():
        i0 = int(r.barra_rottura) + 1
        if r.lato == 1:
            oltre = np.where(cl[i0:] < r.basso)[0]
        else:
            oltre = np.where(cl[i0:] > r.alto)[0]
        inval.append(idx[i0 + oltre[0]] + freq if len(oltre) else pd.NaT)
    z["invalidata_il"] = inval
    return z


def dentro_una_zona(z, quando, prezzo, lato, margine=0.0):
    """C'e' una zona attiva, concorde, che contiene il prezzo a quell'istante?"""
    if z.empty:
        return False
    m = ((z.lato == lato) & (z.attiva_da <= quando) & (z.scade_il > quando)
         & (z.invalidata_il.isna() | (z.invalidata_il > quando))
         & (z.basso - margine <= prezzo) & (prezzo <= z.alto + margine))
    return bool(m.any())


def main():
    m1 = load_m1("/workspace/sviluppo-strategie-e-bot/data/XAUUSD_M1")
    tf_prova = ["M33", "H2", "H6", "H12"]
    zone = {}
    for tf in tf_prova:
        s = resample_tf(m1, tf)
        zone[tf] = order_blocks(s, T.frattale_k, TIMEFRAMES[tf])
        print(f"{tf}: {len(zone[tf])} order block trovati, "
              f"{int(zone[tf].invalidata_il.notna().sum())} poi invalidati", flush=True)

    righe = []
    for o in genera(m1, T, tf_extra=("M66",)):
        if not (o["c_M33"] and o["c_H12"] and not o["c_M12"]):
            continue
        r, mo = valuta(o, T.obiettivo, be=T.pareggio)
        segno = 1 if o["lato"] == "long" else -1
        rec = {"anno": o["anno"], "r": r, "rischio": o["rischio"], "lato": o["lato"]}
        for tf in tf_prova:
            rec[f"ob_{tf}"] = int(dentro_una_zona(zone[tf], o["time"], o["entry"], segno))
            # variante larga: entro mezzo rischio dalla zona
            rec[f"obL_{tf}"] = int(dentro_una_zona(zone[tf], o["time"], o["entry"],
                                                   segno, margine=o["rischio"] * 0.5))
        righe.append(rec)
    d = pd.DataFrame(righe)
    d.to_parquet("/tmp/claude-0/-home-user-staging-bratz/"
                 "12ee8316-94ec-5738-a776-0652fa6537d9/scratchpad/ob.parquet")

    print(f"\noperazioni: {len(d)}   R totale {d.r.sum():+.1f}\n")
    print("=== L'INGRESSO CADE DENTRO UN ORDER BLOCK? ===")
    out = []
    for tf in tf_prova:
        for etichetta, col in ((f"{tf} esatto", f"ob_{tf}"),
                               (f"{tf} +mezzo rischio", f"obL_{tf}")):
            g = d.groupby(col).r.agg(n="size", medio="mean", tot="sum")
            if len(g) < 2:
                out.append({"zona": etichetta, "n dentro": int(g.iloc[0]["n"]),
                            "nota": "mai/sempre"})
                continue
            out.append({"zona": etichetta, "n dentro": int(g.loc[1, "n"]),
                        "R/op dentro": g.loc[1, "medio"],
                        "R/op fuori": g.loc[0, "medio"],
                        "delta": g.loc[1, "medio"] - g.loc[0, "medio"],
                        "R tot dentro": g.loc[1, "tot"]})
    print(pd.DataFrame(out).to_string(index=False, float_format=lambda x: f"{x:+.3f}"))


if __name__ == "__main__":
    main()
