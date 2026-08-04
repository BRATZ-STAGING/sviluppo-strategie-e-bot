#!/usr/bin/env python3
"""Appendice BV: la confluenza fra zone di timeframe diversi — l'idea dell'utente.

*"Di questi ventisettemila dobbiamo ancora scremare una buona parte. Prendere
per buoni solo quelli che hanno piu' di un riferimento: un ritraccio su M12 con
un pullback, poi vedere se magari anche su M33 o H1, oppure una zona molto
specifica."*

E' la domanda giusta al momento giusto. L'appendice BQ ha misurato che il
ritracciamento in zona raffinata, preso come regola generale, ha vantaggio
lordo zero (+0,040 R/op contro +0,049 del campione senza zone). L'appendice BP
ha spiegato perche' non si poteva rispondere prima: con 1.290 operazioni mezzo
R di separazione apparente nasce dal nulla. Qui gli eventi sono 27.127, e la
domanda "le zone sovrapposte valgono piu' di quelle isolate" diventa
finalmente misurabile.

C'E' UN PRECEDENTE CONTRARIO e va detto subito: l'appendice AZ ha provato 720
configurazioni di confluenza e non ne e' sopravvissuta nessuna. Ma AZ misurava
le confluenze come FILTRO sui segnali VWAP, un campione piccolo e un ingresso
diverso. Qui la confluenza e' il selettore PRIMARIO su un campione ventun volte
piu' grande. E' una domanda diversa, non una ripetizione — ed e' proprio la
numerosita' che rende sensato riaprirla.

COSA SI MISURA. Per ogni ritracciamento, quante ALTRE zone raffinate — di
qualunque timeframe, dello stesso lato — sono attive nello stesso momento e si
sovrappongono in prezzo alla zona toccata. Tre misure separate perche'
dicono cose diverse:

  n_confluenze  quante zone si sovrappongono (0 = zona isolata)
  n_tf          su quanti timeframe DISTINTI (2 zone M6 non sono una conferma:
                sono la stessa cosa vista due volte)
  tf_max        il timeframe piu' grande fra quelli in confluenza (l'utente:
                *"su M33 o H2"* — un H2 che concorda pesa piu' di un M6)

CAUSALITA'. Una zona conta solo se e' gia' attiva all'istante del tocco
(``attiva_da <= tocco``) e non e' ancora scaduta ne' invalidata a quell'istante.
Usare le zone create dopo sarebbe futuro, ed e' esattamente il tipo di errore
che in questo progetto ha gia' prodotto quattro risultati spettacolari e falsi.

IPOTESI PRE-REGISTRATE, scritte prima di guardare:
  A. il vantaggio lordo cresce col numero di timeframe distinti in confluenza,
     e la crescita si ripete in verifica. Se cresce solo in ricerca, e' rumore;
  B. la confluenza con un timeframe GRANDE (H2, M66) vale piu' di quella con
     timeframi piccoli a parita' di numero;
  C. le zone isolate (zero confluenze) rendono meno della media.

CONTROLLI OBBLIGATORI:
  - un PLACEBO (numero casuale in terzi) per tarare il rumore;
  - il controllo di assurdita': stop vicino colpito piu' dell'obiettivo lontano;
  - ricerca 2020-2022 contro verifica 2023-2026, sempre entrambe riportate.

Uso: python3 run_confluenza_zone.py
Scrive docs/studies/dati/confluenza_zone.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf       # noqa: E402
from framework.taratura import UFFICIALE as T                     # noqa: E402

from export_lab import zone_ob                                    # noqa: E402
from run_scalp_scaglioni import cammina_uno                       # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TF_ZONE = ["M6", "M12", "M33", "M66", "H2", "H6"]
PESO_TF = {"M6": 1, "M12": 2, "M33": 3, "M66": 4, "H2": 5, "H6": 6}
K_SWING = 3
VALIDITA = 30
RESPIRO = 30
TETTO = 10.0
MARGINE = 2.0                 # lo stop 2 $ oltre la zona, regola dell'utente
ORE = (7, 21)
GIORNI_MAX = 3
RICERCA, VERIFICA = (2020, 2022), (2023, 2026)
SPREAD = {2020: 0.35, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}


def zone_tutte(m1):
    fuori = []
    for tf in TF_ZONE:
        d = resample_tf(m1, tf)
        z = zone_ob(d, K_SWING, TIMEFRAMES[tf], validita=VALIDITA)
        if z.empty:
            continue
        z = z[np.isfinite(z.rbasso) & np.isfinite(z.ralto)].copy()
        z["tf"] = tf
        fuori.append(z)
        print(f"  {tf}: {len(z)}", flush=True)
    z = pd.concat(fuori, ignore_index=True)
    z["attiva_da"] = pd.to_datetime(z.attiva_da, utc=True)
    z["scade_il"] = pd.to_datetime(z.scade_il, utc=True)
    z["invalidata_il"] = pd.to_datetime(z.invalidata_il, utc=True, errors="coerce")
    # la fine vera della zona: la prima fra scadenza e invalidazione
    z["fine"] = z[["scade_il", "invalidata_il"]].min(axis=1)
    return z.sort_values("attiva_da").reset_index(drop=True)


class Cercatore:
    """Trova le zone in confluenza senza scorrerle tutte a ogni evento.

    Fatta in modo diretto la ricerca sarebbe quadratica: 40.000 zone per 40.000
    eventi. Due limiti la rendono lineare, e nessuno dei due cambia il
    risultato:

    - a DESTRA: le zone sono ordinate per nascita, quindi quelle nate dopo
      l'istante del tocco stanno tutte in coda e si tagliano con una ricerca
      binaria. E' anche il vincolo di causalita': una zona nata dopo non e' una
      conferma, e' una notizia del futuro;
    - a SINISTRA: nessuna zona vive piu' di VALIDITA candele del suo timeframe,
      quindi oltre la durata massima (H6 x 30 = 7,5 giorni) sono tutte gia'
      finite. Il taglio e' conservativo: si tiene il doppio del necessario e
      poi si verifica comunque ``fine > quando``.
    """

    def __init__(self, z):
        self.att = z.attiva_da.values.astype("datetime64[ns]")
        self.fine = z.fine.values.astype("datetime64[ns]")
        self.rb = z.rbasso.values
        self.ra = z.ralto.values
        self.lato = z.lato.values.astype(np.int8)
        self.peso = z.tf.map(PESO_TF).values.astype(np.int8)
        durata = max(pd.Timedelta(TIMEFRAMES[tf]) for tf in TF_ZONE) * VALIDITA
        self.finestra = np.timedelta64(int(durata.total_seconds() * 2), "s")

    def conta(self, i, quando):
        q = np.datetime64(quando.tz_localize(None), "ns")
        alto = int(np.searchsorted(self.att, q, side="right"))
        basso = int(np.searchsorted(self.att, q - self.finestra, side="left"))
        if alto <= basso:
            return 0, 0, 0
        s = slice(basso, alto)
        viva = (self.fine[s] > q) & (self.lato[s] == self.lato[i])
        sovr = (self.rb[s] <= self.ra[i]) & (self.ra[s] >= self.rb[i])
        m = viva & sovr
        if i >= basso and i < alto:
            m[i - basso] = False                  # la zona non conferma se stessa
        if not m.any():
            return 0, 0, 0
        pesi = np.unique(self.peso[s][m])
        pesi = pesi[pesi != self.peso[i]]         # altri timeframe, non il proprio
        return int(m.sum()), int(len(pesi)), int(pesi.max()) if len(pesi) else 0


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    resp = (m1.high - m1.low).rolling(RESPIRO).mean().shift(1)
    print("zone:", flush=True)
    z = zone_tutte(m1)
    print(f"totale {len(z)} zone raffinate", flush=True)

    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values
    rv = resp.values
    rng = np.random.default_rng(777)

    cerca = Cercatore(z)
    righe = []
    for i in range(len(z)):
        r = z.iloc[i]
        t0, t1 = r.attiva_da, r.fine
        if pd.isna(t1) or t1 <= t0:
            continue
        a = int(np.searchsorted(idx, t0.value))
        b = int(np.searchsorted(idx, t1.value))
        if b - a < 2:
            continue
        if r.lato == 1:
            dentro = np.flatnonzero(lo[a:b] <= r.ralto)
        else:
            dentro = np.flatnonzero(hi[a:b] >= r.rbasso)
        if not len(dentro):
            continue
        k = a + int(dentro[0])
        t_in = pd.Timestamp(idx[k], unit="ns", tz="UTC")
        if not (ORE[0] <= t_in.hour < ORE[1]):
            continue
        if k >= len(rv):
            continue
        r_now = rv[k]
        if not np.isfinite(r_now) or r_now <= 0:
            continue
        prezzo = float(r.ralto if r.lato == 1 else r.rbasso)
        stop = (r.rbasso - MARGINE) if r.lato == 1 else (r.ralto + MARGINE)
        kk = abs(prezzo - stop)
        if kk < 0.5 or kk > 25:
            continue
        b2 = int(np.searchsorted(idx, (t_in + pd.Timedelta(days=GIORNI_MAX)).value))
        if b2 - k < 5:
            continue
        o_, h_, l_, c_ = ap_[k:b2], hi[k:b2], lo[k:b2], cl[k:b2]
        if r.lato == 1:
            apri, fav, sfav, chiu = ((o_ - prezzo) / kk, (h_ - prezzo) / kk,
                                     (prezzo - l_) / kk, (c_ - prezzo) / kk)
        else:
            apri, fav, sfav, chiu = ((prezzo - o_) / kk, (prezzo - l_) / kk,
                                     (h_ - prezzo) / kk, (prezzo - c_) / kk)
        x, motivo = cammina_uno(apri, fav, sfav, chiu, TETTO / kk)
        n_conf, n_tf, tf_max = cerca.conta(i, t_in)
        costo = SPREAD.get(t_in.year, 0.40) / kk
        righe.append({"anno": t_in.year, "tf": r.tf, "lato": int(r.lato),
                      "n_conf": n_conf, "n_tf": n_tf, "tf_max": tf_max,
                      "stop$": kk, "lordo": x, "netto": x - costo,
                      "motivo": motivo, "placebo": float(rng.random())})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "confluenza_zone.parquet"), index=False)
    pd.set_option("display.width", 240)
    print(f"\nritracciamenti: {len(t)} | lordo medio {t.lordo.mean():+.3f} "
          f"| netto medio {t.netto.mean():+.3f}", flush=True)

    def tabella(col, fasce):
        f = []
        for eti, (da, aa) in [("ricerca", RICERCA), ("verifica", VERIFICA)]:
            p = t[(t.anno >= da) & (t.anno <= aa)].copy()
            p["f"] = fasce(p)
            g = p.groupby("f", observed=True).agg(
                op=("lordo", "size"), lordo=("lordo", "mean"),
                netto=("netto", "mean"))
            for k2, riga in g.iterrows():
                f.append({"fascia": k2, "periodo": eti, "op": int(riga.op),
                          "lordo": riga.lordo, "netto": riga.netto})
        d = pd.DataFrame(f)
        return d.pivot(index="fascia", columns="periodo",
                       values=["op", "lordo", "netto"])

    def verdetto(tab):
        try:
            lr = tab["lordo"]["ricerca"].dropna()
            lv = tab["lordo"]["verifica"].dropna()
            com = [x for x in lr.index if x in lv.index]
            if len(com) < 2:
                return "  (troppe poche fasce)"
            br, bv = max(com, key=lambda x: lr[x]), max(com, key=lambda x: lv[x])
            return (f"  migliore in ricerca: {br} ({lr[br]:+.3f}) | in verifica: "
                    f"{bv} ({lv[bv]:+.3f}) | "
                    f"{'REGGE' if br == bv else 'non regge'}")
        except Exception as e:                     # noqa: BLE001
            return f"  (verdetto non calcolabile: {e})"

    print("\n=== ipotesi A: quanti TIMEFRAME DISTINTI in confluenza")
    tab = tabella("n_tf", lambda p: p.n_tf.clip(upper=3).map(
        {0: "0 isolata", 1: "1 tf", 2: "2 tf", 3: "3+ tf"}))
    print(tab.round(3).to_string())
    print(verdetto(tab))

    print("\n=== ipotesi B: il timeframe PIU' GRANDE in confluenza")
    inv = {v: k for k, v in PESO_TF.items()}
    tab = tabella("tf_max", lambda p: p.tf_max.map(
        lambda x: "nessuno" if x == 0 else inv.get(x, "?")))
    print(tab.round(3).to_string())
    print(verdetto(tab))

    print("\n=== ipotesi C: numero di zone sovrapposte (qualunque tf)")
    tab = tabella("n_conf", lambda p: p.n_conf.clip(upper=4).map(
        {0: "0", 1: "1", 2: "2", 3: "3", 4: "4+"}))
    print(tab.round(3).to_string())
    print(verdetto(tab))

    print("\n=== PLACEBO (numero casuale, stesso trattamento)")
    tab = tabella("placebo", lambda p: pd.qcut(
        p.placebo, 4, labels=["q1", "q2", "q3", "q4"]))
    print(tab.round(3).to_string())
    print(verdetto(tab))

    print("\n=== controllo di assurdita' e sanita' del campione")
    s = (t.motivo == "stop").mean() * 100
    ob = (t.motivo == "obiettivo").mean() * 100
    print(f"  stop {s:.1f}%  obiettivo {ob:.1f}%  "
          + ("ok" if s > ob else "*** GUARDARE"))
    print(f"  distribuzione n_tf: "
          + "  ".join(f"{k}:{v}" for k, v in
                      t.n_tf.clip(upper=3).value_counts().sort_index().items()))


if __name__ == "__main__":
    main()
