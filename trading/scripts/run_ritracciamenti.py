#!/usr/bin/env python3
"""Appendice BQ: prendere i ritracciamenti buy e sell durante la giornata.

Richiesta dell'utente: *"possiamo cercare una strategia per prendere i vari
ritracciamenti buy e sell durante la giornata"*, con lo stop **2-3 punti sotto
la zona** e l'obiettivo largo ma non oltre 10 $.

E' la strategia che l'utente sta gia' facendo a mano: nell'esempio dal vivo,
entrata sulla zona raffinata M33 a ~4075,3, stop 4,5 punti, prezzo a +7 punti.
Qui la si misura su sette anni invece che su un'occasione.

PERCHE' QUESTA E' LA STRADA GIUSTA E LE ALTRE NO. L'appendice BM ha fissato il
conto: perche' uno scalp con stop di pochi dollari si paghi, il vantaggio
lordo deve passare da 0,05 a oltre 0,20 R/op. L'appendice BO ha escluso che ci
si arrivi cambiando stop e obiettivo. Ma l'appendice AJ ha gia' misurato che
la **zona raffinata** vale +1,342 R/op: e' quattro volte quel che serve. Il
problema della zona raffinata non e' il vantaggio, e' la **frequenza** — 63
occasioni in sette anni, nove l'anno. Questo studio chiede: allargando dai
soli segnali VWAP a TUTTI i ritracciamenti in zona, quante occasioni vengono
fuori e quanto vantaggio resta?

DIFFERENZA IMPORTANTE dalla strategia ufficiale: qui NON c'e' il filtro macro
e si prendono i due lati. L'utente vuole i ritracciamenti buy E sell della
giornata, non una direzione sola.

COSA SI CONFRONTA (tutte le celle riportate, nessuna scelta a posteriori):
  innesco   "tocco"      entra al primo minuto dentro la zona raffinata
            "chiusura"   entra alla chiusura della prima M6 che chiude fuori
                         dalla zona dalla parte giusta (l'utente: *"la chiusura
                         dentro la zona in tf piu' grandi e' una conferma
                         migliore"*)
  stop      "2 $ oltre"  la regola dell'utente, in dollari
            "1 respiro"  la stessa cosa scritta in volatilita'
  obiettivo 10 $ tondi, e per riferimento 1:2 e l'ufficiale 1:10

IPOTESI PRE-REGISTRATE:
  A. il ritracciamento in zona raffinata batte il campione largo dell'appendice
     BM (+0,049 R/op lordo). Se non lo batte, la zona non seleziona niente e
     l'appendice AJ era un artefatto della coincidenza col segnale VWAP;
  B. l'innesco "chiusura" batte "tocco": il tocco prende anche i coltelli che
     cadono, la chiusura aspetta la reazione. Costa qualche punto di entrata;
  C. le occasioni sono molte di piu' di nove l'anno — altrimenti resta una
     strategia da poche operazioni e lo scalp non esiste comunque.

CONTROLLO DI ASSURDITA' obbligatorio (in questo progetto ha gia' smascherato
quattro risultati): con obiettivo lontano e stop vicino, lo stop DEVE essere
colpito piu' spesso dell'obiettivo. Se non lo e', c'e' futuro nel calcolo.

Uso: python3 run_ritracciamenti.py
Scrive docs/studies/dati/ritracciamenti.parquet
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
TF_ZONE = ["M6", "M12", "M33", "M66", "H2"]      # i piccoli: piu' occasioni
K_SWING = 3
VALIDITA = 30
RESPIRO = 30
TETTO = 10.0
ORE = (7, 21)                 # londra + new york: fuori di li' non si scalpa
GIORNI_MAX = 3                # e' intraday: oltre tre giorni non e' piu' quello
RICERCA, VERIFICA = (2020, 2022), (2023, 2026)


def zone_tutte(m1):
    """Le zone raffinate di tutti i timeframe piccoli, in una tabella sola."""
    fuori = []
    for tf in TF_ZONE:
        d = resample_tf(m1, tf)
        z = zone_ob(d, K_SWING, TIMEFRAMES[tf], validita=VALIDITA)
        if z.empty:
            continue
        z = z[np.isfinite(z.rbasso) & np.isfinite(z.ralto)].copy()
        z["tf"] = tf
        fuori.append(z)
        print(f"  {tf}: {len(z)} zone raffinate", flush=True)
    z = pd.concat(fuori, ignore_index=True).sort_values("attiva_da")
    z["invalidata_il"] = pd.to_datetime(z.invalidata_il, utc=True, errors="coerce")
    return z


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    resp = (m1.high - m1.low).rolling(RESPIRO).mean().shift(1)
    m6 = resample_tf(m1, "M6")
    print("zone:", flush=True)
    z = zone_tutte(m1)
    print(f"totale {len(z)} zone raffinate", flush=True)

    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values
    rv = resp.values
    m6_idx = pd.DatetimeIndex(m6.index).as_unit("ns").asi8
    m6_cl, m6_hi, m6_lo = m6.close.values, m6.high.values, m6.low.values

    eventi = []
    for _, r in z.iterrows():
        t0 = pd.Timestamp(r.attiva_da)
        t1 = min(pd.Timestamp(r.scade_il),
                 pd.Timestamp(r.invalidata_il) if pd.notna(r.invalidata_il)
                 else pd.Timestamp(r.scade_il))
        if t1 <= t0:
            continue
        a = int(np.searchsorted(idx, t0.value))
        b = int(np.searchsorted(idx, t1.value))
        if b - a < 2:
            continue
        # "tocco": il primo minuto in cui il prezzo entra nella zona raffinata
        if r.lato == 1:
            dentro = np.flatnonzero(lo[a:b] <= r.ralto)
        else:
            dentro = np.flatnonzero(hi[a:b] >= r.rbasso)
        if not len(dentro):
            continue
        k = a + int(dentro[0])
        t_tocco = pd.Timestamp(idx[k], unit="ns", tz="UTC")
        # "chiusura": la prima M6 che, DOPO il tocco, chiude fuori dalla zona
        # dalla parte giusta. Si entra alla sua chiusura, mai prima: dentro la
        # candela non si sa ancora come chiudera'
        j = int(np.searchsorted(m6_idx, t_tocco.value))
        t_chiu, p_chiu = None, None
        for jj in range(j, min(j + 20, len(m6_cl))):
            fuori_ok = (m6_cl[jj] > r.ralto) if r.lato == 1 else (m6_cl[jj] < r.rbasso)
            tocca = (m6_lo[jj] <= r.ralto) if r.lato == 1 else (m6_hi[jj] >= r.rbasso)
            if tocca and fuori_ok:
                t_chiu = pd.Timestamp(m6_idx[jj], unit="ns", tz="UTC") + TIMEFRAMES["M6"]
                p_chiu = float(m6_cl[jj])
                break
        eventi.append({"tf": r.tf, "lato": int(r.lato),
                       "rbasso": float(r.rbasso), "ralto": float(r.ralto),
                       "t_tocco": t_tocco, "p_tocco": float(r.ralto if r.lato == 1
                                                            else r.rbasso),
                       "t_chiusura": t_chiu, "p_chiusura": p_chiu})
    ev = pd.DataFrame(eventi)
    print(f"ritracciamenti in zona: {len(ev)}", flush=True)

    PROVE = [("tocco", "2 $ oltre", TETTO), ("tocco", "1 respiro", TETTO),
             ("chiusura", "2 $ oltre", TETTO), ("chiusura", "1 respiro", TETTO),
             ("chiusura", "2 $ oltre", "rr2"), ("chiusura", "2 $ oltre", "rr10")]
    righe = []
    for innesco, stopdef, obdef in PROVE:
        for _, e in ev.iterrows():
            t_in = e.t_tocco if innesco == "tocco" else e.t_chiusura
            prezzo = e.p_tocco if innesco == "tocco" else e.p_chiusura
            if t_in is None or prezzo is None or not np.isfinite(prezzo):
                continue
            if not (ORE[0] <= t_in.hour < ORE[1]):
                continue
            a = int(np.searchsorted(idx, t_in.value))
            b = int(np.searchsorted(idx, (t_in + pd.Timedelta(days=GIORNI_MAX)).value))
            if b - a < 5 or a >= len(rv):
                continue
            r_now = rv[a]
            if not np.isfinite(r_now) or r_now <= 0:
                continue
            margine = 2.0 if stopdef == "2 $ oltre" else float(r_now)
            stop = (e.rbasso - margine) if e.lato == 1 else (e.ralto + margine)
            k = abs(prezzo - stop)
            if k < 0.5 or k > 25:            # sotto mezzo dollaro e' una tassa,
                continue                     # sopra 25 non e' piu' un ritracciamento
            rr = (TETTO / k if obdef == TETTO else
                  2.0 if obdef == "rr2" else 10.0)
            o_, h_, l_, c_ = ap_[a:b], hi[a:b], lo[a:b], cl[a:b]
            if e.lato == 1:
                apri, fav, sfav, chiu = ((o_ - prezzo) / k, (h_ - prezzo) / k,
                                         (prezzo - l_) / k, (c_ - prezzo) / k)
            else:
                apri, fav, sfav, chiu = ((prezzo - o_) / k, (prezzo - l_) / k,
                                         (h_ - prezzo) / k, (prezzo - c_) / k)
            x, motivo = cammina_uno(apri, fav, sfav, chiu, rr)
            righe.append({
                "cella": f"{innesco} · stop {stopdef} · "
                         + ("obiettivo 10 $" if obdef == TETTO else
                            "obiettivo 1:2" if obdef == "rr2" else "obiettivo 1:10"),
                "innesco": innesco, "tf": e.tf, "lato": e.lato,
                "anno": t_in.year, "giorno": t_in.normalize(),
                "stop$": k, "rr": rr, "costo": T.spread / k,
                "lordo": x, "netto": x - T.spread / k, "motivo": motivo})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "ritracciamenti.parquet"), index=False)
    pd.set_option("display.width", 250)

    def riassunto(x):
        n = x.netto.values
        cum = np.cumsum(n)
        dd = float((np.maximum.accumulate(cum) - cum).max()) if len(n) else 0.0
        pa = x.netto.groupby(x.anno).sum()
        giorni = x.giorno.nunique()
        return pd.Series({"op": len(n), "op/giorno": len(n) / max(giorni, 1),
                          "stop$": x["stop$"].median(), "costo%R": x.costo.mean() * 100,
                          "lordo R/op": x.lordo.mean(), "netto R/op": n.mean(),
                          "netto R": n.sum(), "vinte%": (n > 0).mean() * 100,
                          "stop%": (x.motivo == "stop").mean() * 100,
                          "obiett.%": (x.motivo == "obiettivo").mean() * 100,
                          "R/DD": n.sum() / dd if dd > 0 else np.nan,
                          "anni+": int((pa > 0).sum()), "anni": pa.size})

    print("\n=== tutte le celle, tutto il periodo")
    print(t.groupby("cella", sort=False).apply(riassunto).round(3).to_string())

    print("\n=== ipotesi A e B: ricerca contro verifica")
    for eti, (da, aa) in [(f"ricerca {RICERCA}", RICERCA), (f"verifica {VERIFICA}", VERIFICA)]:
        p = t[(t.anno >= da) & (t.anno <= aa)]
        print(f"\n  {eti}")
        print(p.groupby("cella", sort=False)
              .apply(lambda x: pd.Series({
                  "op": len(x), "lordo R/op": x.lordo.mean(),
                  "netto R/op": x.netto.mean(), "netto R": x.netto.sum(),
                  "anni+": int((x.netto.groupby(x.anno).sum() > 0).sum())}))
              .round(3).to_string())

    print("\n=== per timeframe della zona (cella principale dell'utente)")
    p = t[t.cella == "chiusura · stop 2 $ oltre · obiettivo 10 $"]
    print(p.groupby("tf").apply(riassunto).round(3).to_string())

    print("\n=== controllo di assurdita': lo stop vicino e' colpito piu' "
          "dell'obiettivo lontano?")
    for cella, x in t.groupby("cella", sort=False):
        s, ob = (x.motivo == "stop").mean() * 100, (x.motivo == "obiettivo").mean() * 100
        nota = "ok" if s > ob else "*** GUARDARE: obiettivo piu' facile dello stop"
        print(f"  {cella:<52} stop {s:5.1f}%  obiettivo {ob:5.1f}%  {nota}")


if __name__ == "__main__":
    main()
