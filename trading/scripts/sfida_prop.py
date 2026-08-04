#!/usr/bin/env python3
"""La sfida FundingPips: quale strategia la passa, e con che taglia.

L'utente valuta una sfida da 5.000 $: fase 1 obiettivo **+10%**, fase 2 **+6%**,
perdita massima **12%**, perdita giornaliera **4%**, nessun minimo di giornate.

E' UN PROBLEMA DIVERSO DA TUTTI QUELLI DI OGGI, e va detto subito perche'
cambia quale strategia conviene. Fino a qui il criterio era "6% annuo col
drawdown piu' piccolo": un problema di rendimento per unita' di sofferenza,
su orizzonte lungo. Una sfida e' una **corsa a due traguardi**: arrivare a
+10% prima di toccare −12%, senza mai perdere il 4% in una sola giornata. Non
conta il rendimento annuo: conta la probabilita' di arrivare in fondo.

E' per questo che il vincolo che decide non e' la perdita massima, ma le
**perdite consecutive** — la misura che nel confronto per i clienti sembrava
secondaria:

  in uso  23 di fila     A  24 di fila     B  12 di fila     1:2  7 di fila

Con il 12% di margine totale, 23 perdite di fila costringono a rischiare meno
dello 0,52% per operazione; 7 ne permettono l'1,7%. E chi puo' rischiare di
piu' arriva prima al traguardo. La stessa proprieta' che rendeva la 1:2 meno
interessante per un conto lungo la rende la piu' adatta a una sfida.

COME SI SIMULA. Non con una formula: con i percorsi veri. Si prende la
sequenza storica delle operazioni e si fa partire la sfida da **ogni possibile
punto d'inizio**, come se il conto fosse stato aperto quel giorno. Ogni partenza
finisce in uno di tre modi: obiettivo raggiunto, violato (perdita massima o
giornaliera), oppure i dati finiscono prima. Il conto delle tre cose e' la
risposta.

REGOLE MODELLATE, dichiarate perche' i dettagli contano:
  - taglia in percentuale del saldo CORRENTE (composta), come la maggior parte
    degli EA. Con taglia sul saldo iniziale i numeri cambiano poco;
  - perdita massima **statica** dal saldo iniziale (88% del capitale di
    partenza). Se il fornitore la calcola in modo dinamico e' piu' severa: e'
    la variante da verificare con lui prima di comprare;
  - perdita giornaliera sul saldo di **inizio giornata**, giornate UTC;
  - le operazioni si contano alla chiusura, che e' quando il conto le vede;
  - costi: spread vero per anno (appendice BN), gia' dentro i risultati.

Uso: XAU_ANNI=2020-2026 python3 sfida_prop.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import load_m1                               # noqa: E402
from framework.segnali import genera                             # noqa: E402
from framework.taratura import UFFICIALE as T                    # noqa: E402

from verifica_bot import (CHIUSURA_MIN, GIORNI_MAX, MEDIANA_ATR,  # noqa: E402
                          SPREAD, cammina)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OBIETTIVO = 0.10          # fase 1
PERDITA_MAX = 0.12
PERDITA_GIORNO = 0.04
RISCHI = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

BOT = [("in uso", 10.0, 3.0, None, False, None),
       ("A", 8.0, 3.0, None, True, -99.0),
       ("B", 8.0, None, (3.0, 2.0), True, 1.0),
       ("1:2", 2.0, None, None, False, None)]


def sfida(r, giorni, rischio, obiettivo=OBIETTIVO):
    """Una partenza: torna 'passata', 'violata' o 'aperta' e i giorni impiegati.

    Il saldo parte da 1. La perdita giornaliera si misura contro il saldo di
    inizio giornata, quella massima contro il saldo iniziale: sono due vincoli
    diversi e nelle sfide si violano per motivi diversi — il primo per una
    giornata storta, il secondo per una serie lunga.
    """
    saldo = 1.0
    minimo = 1.0 - PERDITA_MAX
    g_corrente, saldo_giorno = None, 1.0
    for i in range(len(r)):
        g = giorni[i]
        if g != g_corrente:
            g_corrente, saldo_giorno = g, saldo
        saldo += r[i] * rischio * saldo
        if saldo <= minimo:
            return "violata", (giorni[i] - giorni[0]).days
        if saldo <= saldo_giorno * (1 - PERDITA_GIORNO):
            return "violata", (giorni[i] - giorni[0]).days
        if saldo >= 1.0 + obiettivo:
            return "passata", (giorni[i] - giorni[0]).days
    return "aperta", (giorni[-1] - giorni[0]).days if len(giorni) else 0


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ops = [o for o in genera(m1, T, mediana_atr=MEDIANA_ATR)
           if all(o[f"c_{tf}"] for tf in T.conferme)
           and all(not o[f"c_{tf}"] for tf in T.ritracciamento)]
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values

    serie, giorni = {n: [] for n, *_ in BOT}, []
    for o in ops:
        t_in = pd.Timestamp(o["time"]).tz_convert("UTC")
        segno = 1 if o["lato"] == "long" else -1
        e, k = o["entry"], float(o["rischio"])
        a = int(np.searchsorted(idx, t_in.value))
        b = int(np.searchsorted(idx, (t_in + pd.Timedelta(days=GIORNI_MAX)).value))
        if b - a < 2:
            continue
        o_, h_, l_, c_ = ap_[a:b], hi[a:b], lo[a:b], cl[a:b]
        if segno == 1:
            apri, fav, sfav, chiu = ((o_ - e) / k, (h_ - e) / k,
                                     (e - l_) / k, (c_ - e) / k)
        else:
            apri, fav, sfav, chiu = ((e - o_) / k, (e - l_) / k,
                                     (h_ - e) / k, (e - c_) / k)
        t_abs = pd.DatetimeIndex(idx[a:b].astype("datetime64[ns]"), tz="UTC")
        fine_gio = set(np.flatnonzero(
            (t_abs.hour == T.ora_chiusura) & (t_abs.minute == 0)).tolist())
        d = np.diff(idx[a:b]) / 60_000_000_000
        buchi = set(np.flatnonzero(d > CHIUSURA_MIN).tolist())
        s = SPREAD.get(o["anno"], 0.40) / k
        for nome, rr, pareggio, trail, oltre, soglia in BOT:
            x, _ = cammina(apri, fav, sfav, chiu, buchi, fine_gio,
                           rr, pareggio, trail, oltre, soglia)
            serie[nome].append(x - s)
        giorni.append(t_in.normalize())
    giorni = pd.DatetimeIndex(giorni)
    pd.set_option("display.width", 240)
    print(f"operazioni: {len(giorni)}  ({giorni[0]:%Y-%m} -> {giorni[-1]:%Y-%m})")

    print(f"\n=== fase 1: +{OBIETTIVO*100:.0f}% prima di −{PERDITA_MAX*100:.0f}% "
          f"(o −{PERDITA_GIORNO*100:.0f}% in giornata)")
    print("   percentuale di partenze che PASSANO, per taglia\n")
    for nome, *_ in BOT:
        r = np.array(serie[nome])
        f = []
        for rischio in RISCHI:
            esiti = [sfida(r[i:], giorni[i:], rischio / 100) for i in range(len(r))]
            tipi = pd.Series([e[0] for e in esiti])
            gg = [e[1] for e in esiti if e[0] == "passata"]
            f.append({"rischio/op %": rischio,
                      "passate %": (tipi == "passata").mean() * 100,
                      "violate %": (tipi == "violata").mean() * 100,
                      "aperte %": (tipi == "aperta").mean() * 100,
                      "giorni mediani": float(np.median(gg)) if gg else np.nan})
        d = pd.DataFrame(f).set_index("rischio/op %")
        migliore = d["passate %"].idxmax()
        print(f"  {nome}   (miglior taglia: {migliore}% -> "
              f"{d.loc[migliore, 'passate %']:.0f}% di successo, "
              f"{d.loc[migliore, 'giorni mediani']:.0f} giorni)")
        print(d.round(1).to_string().replace("\n", "\n  "))
        print()

    print("=== le due fasi di fila (10% poi 6%), alla taglia migliore di ciascuna")
    for nome, *_ in BOT:
        r = np.array(serie[nome])
        meglio, best = None, -1
        for rischio in RISCHI:
            due = 0
            for i in range(len(r)):
                e1, _ = sfida(r[i:], giorni[i:], rischio / 100, OBIETTIVO)
                if e1 != "passata":
                    continue
                # la fase 2 riparte da un conto nuovo: stesso vincolo, obiettivo 6%
                j = i + 1
                e2, _ = sfida(r[j:], giorni[j:], rischio / 100, 0.06)
                due += (e2 == "passata")
            q = due / len(r) * 100
            if q > best:
                meglio, best = rischio, q
        print(f"  {nome:<8} miglior taglia {meglio}% -> {best:.0f}% delle partenze "
              f"passa ENTRAMBE le fasi")


if __name__ == "__main__":
    main()
