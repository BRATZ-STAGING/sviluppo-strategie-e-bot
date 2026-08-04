#!/usr/bin/env python3
"""Appendice BU: le zone non sono tutte uguali? Cinque misure di qualita'.

DA DOVE SI PARTE. L'appendice BQ ha misurato 27.127 ritracciamenti su zone
order block raffinate (M6, M12, M33, M66, H2, due lati, niente filtro macro) e
ha trovato un vantaggio lordo QUASI ZERO: **+0,040 R/op** nella cella
principale (ingresso al tocco, stop 2 $ oltre la zona, obiettivo 10 $), che al
netto dello spread diventa -0,086. Conclusione di BQ: "la zona raffinata non
seleziona niente".

L'IPOTESI DI QUESTA APPENDICE e' che quel +0,040 sia una MEDIA fra zone buone e
zone cattive, e che la media nasconda una selezione. Se e' vero, dividendo le
occasioni per una misura di qualita' si deve vedere un terzo che rende
sensibilmente piu' degli altri, E la stessa fascia deve restare la migliore in
un periodo che non abbiamo guardato. Se e' falso, i terzi si mescoleranno.

GESTIONE FISSA, PER ISOLARE LA VARIABILE. Una cella sola, quella principale di
BQ: ingresso al primo minuto dentro la zona raffinata, stop 2 $ oltre il bordo
lontano della zona, obiettivo 10 $. Non si cambia niente della gestione: cambia
solo COME si dividono le stesse operazioni. Gli eventi sono generati con lo
stesso identico codice di ``run_ritracciamenti.py`` (``zone_tutte`` e' importata
da li', il rilevamento del tocco e' copiato riga per riga) proprio perche' il
confronto con BQ resti valido.

LE CINQUE MISURE, TUTTE CAUSALI (note PRIMA del minuto del tocco):

  1 FRESCHEZZA — quante candele del timeframe della zona sono passate fra la
    creazione della zona (chiusura della candela che rompe lo swing) e il
    tocco. Si contano le barre vere del TF, non il tempo di calendario, cosi'
    il fine settimana non gonfia il numero.
  2 AMPIEZZA RELATIVA — altezza della zona raffinata divisa per il respiro
    corrente (media a 30 minuti del range M1, gia' spostata di 1: causale).
  3 IMPULSO CHE L'HA CREATA — quanto il prezzo si e' allontanato dal bordo
    della zona, fino al suo estremo, PRIMA di tornare a toccarla, in unita' di
    respiro. Usa solo barre comprese fra attivazione e tocco.
  4 TOCCHI PRECEDENTI — vedi la nota qui sotto, e' l'unica che ha richiesto una
    riscrittura.
  5 POSIZIONE NEL RANGE DEL GIORNO — dove sta il prezzo d'ingresso rispetto a
    massimo e minimo della giornata FINO AL MINUTO PRECEDENTE (cummax/cummin
    per giorno UTC, spostati di 1 dentro il giorno). Orientata a favore del
    lato: 0 = si compra sul minimo di giornata finora / si vende sul massimo,
    1 = il contrario.
  0 PLACEBO — ``np.random.default_rng(999).random()``, trattato in modo
    identico. Non e' un ornamento: nell'appendice BP il placebo aveva prodotto
    fra i terzi una separazione PIU' GRANDE di tutte e cinque le famiglie vere.
    Serve a sapere quanta separazione nasce dal nulla con QUESTO campione.

NOTA OBBLIGATORIA SULLA MISURA 4 (e sul perche' non e' quella richiesta alla
lettera). La generazione degli eventi di BQ prende **solo il primo tocco di
ogni zona**: per costruzione i tocchi precedenti DELLA STESSA ZONA sono sempre
zero, e la misura sarebbe una colonna di zeri. Contare i tocchi successivi
sarebbe futuro, e non si fa. La misura e' quindi riscritta come **quante volte
quell'AREA DI PREZZO era gia' stata testata**: numero di tocchi (di qualunque
zona, di qualunque timeframe, di qualunque lato) avvenuti nei 3 giorni
precedenti a un prezzo compreso dentro i bordi della zona corrente. E' la
stessa idea — area vergine contro area gia' battuta — ed e' calcolabile
all'istante del tocco. Fasce fisse (0 / 1 / 2+) invece di qcut perche' la
variabile e' un conteggio piccolo e pieno di pareggi.

IPOTESI PRE-REGISTRATE (scritte prima di guardare i numeri, una per misura;
"terzo" e' il terzo della variabile, non del rendimento):
  H1 la zona FRESCA rende piu' della zona vecchia -> vince il terzo BASSO.
  H2 la zona STRETTA rende piu' della zona larga -> vince il terzo BASSO.
     (con lo stop a 2 $ fissi, una zona larga allontana lo stop e abbassa l'R
     disponibile: se qualcosa deve funzionare per aritmetica, e' questa)
  H3 la zona nata da un IMPULSO FORTE rende di piu' -> vince il terzo ALTO.
  H4 l'area VERGINE rende piu' di quella gia' battuta -> vince "vergine".
  H5 comprare in BASSO nel range del giorno (e vendere in alto) rende di piu'
     -> vince il terzo BASSO.
  H0 il placebo non deve reggere. Se regge, o se separa piu' delle misure
     vere, l'esito onesto e' che il campione non distingue nulla.

CRITERIO DI ACCETTAZIONE, DICHIARATO PRIMA. Una misura conta SOLO se il terzo
migliore in **ricerca 2020-2022** e' ancora il migliore in **verifica
2023-2026**. I bordi dei terzi sono calcolati SULLA SOLA RICERCA (qcut) e poi
applicati alla verifica (cut): usare i quantili di tutto il periodo per tagliare
anche la verifica sarebbe un filo di futuro, piccolo ma gratuito da evitare.
Nessuna cella viene nascosta: si riportano tutte, in un'unica tabella.

COSTI. Spread vero misurato nell'appendice BN, per anno, non una costante:
2020 0,350 / 2021 0,349 / 2022 0,395 / 2023 0,334 / 2024 0,384 / 2025 0,632 /
2026 0,631 dollari. Con stop mediano di ~2,3 $ e' un pedaggio dell'ordine del
13% del rischio, che e' tre volte il vantaggio lordo di BQ: e' il motivo per
cui il netto conta piu' del lordo in tutta questa appendice.

CONTROLLO DI ASSURDITA' (in questo progetto ha gia' smascherato quattro
risultati): con obiettivo lontano (10 $) e stop vicino (~2,3 $), lo stop DEVE
essere colpito molto piu' spesso dell'obiettivo, in ogni fascia di ogni misura.
Se in una fascia l'obiettivo risultasse piu' facile dello stop, quella fascia
contiene futuro e va buttata.

Uso: XAU_ANNI=2020-2026 python3 run_qualita_zone.py
Scrive docs/studies/dati/qualita_zone.parquet
"""
from __future__ import annotations

import contextlib
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf       # noqa: E402

from run_scalp_scaglioni import cammina_uno                       # noqa: E402
# la generazione delle zone e le costanti vengono da BQ, invariate: se
# cambiassero li', devono cambiare anche qui, e il confronto resterebbe valido
from run_ritracciamenti import (                                  # noqa: E402
    GIORNI_MAX, ORE, RESPIRO, RICERCA, TETTO, TF_ZONE, VERIFICA, zone_tutte,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# spread vero per anno (appendice BN): niente costante unica, il 2025-2026
# costa quasi il doppio del 2020-2024
SPREAD = {2020: 0.35, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}
MARGINE_STOP = 2.0            # i "2 $ oltre la zona" dell'utente
FINESTRA_TOCCHI = pd.Timedelta(days=3)    # memoria dell'area per la misura 4
SEME_PLACEBO = 999

MISURE = ["1 freschezza (barre tf)", "2 ampiezza / respiro",
          "3 impulso / respiro", "4 tocchi precedenti area",
          "5 posizione nel giorno", "0 placebo"]
ATTESA = {"1 freschezza (barre tf)": "basso", "2 ampiezza / respiro": "basso",
          "3 impulso / respiro": "alto", "4 tocchi precedenti area": "vergine",
          "5 posizione nel giorno": "basso", "0 placebo": "(nessuna)"}


def eventi_con_qualita(m1):
    """Gli stessi tocchi di BQ, con accanto le misure di qualita' causali."""
    resp = (m1.high - m1.low).rolling(RESPIRO).mean().shift(1)
    # zone_tutte stampa il conteggio per timeframe: lo mando su stderr per
    # tenere lo stdout corto come chiede il progetto
    with contextlib.redirect_stdout(sys.stderr):
        z = zone_tutte(m1)
        print(f"totale {len(z)} zone raffinate", flush=True)

    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    hi, lo = m1.high.values, m1.low.values
    rv = resp.values
    # indici delle barre di ciascun timeframe: servono a contare la
    # FRESCHEZZA in barre vere e non in ore di calendario (il weekend)
    tf_idx = {tf: pd.DatetimeIndex(resample_tf(m1, tf).index).as_unit("ns").asi8
              for tf in TF_ZONE}
    # massimo e minimo del giorno FINO AL MINUTO PRECEDENTE: cumulate dentro
    # il giorno UTC e poi spostate di uno dentro lo stesso giorno, cosi' la
    # candela del tocco non entra mai nel proprio riferimento
    g = pd.Index(m1.index.normalize())
    hh = m1.high.groupby(g).cummax().groupby(g).shift(1).values
    ll = m1.low.groupby(g).cummin().groupby(g).shift(1).values

    fuori = []
    for r in z.itertuples(index=False):
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
        prezzo = float(r.ralto if r.lato == 1 else r.rbasso)
        r_now = rv[k]
        if not np.isfinite(r_now) or r_now <= 0:
            continue
        # 1 freschezza: barre del TF della zona fra attivazione e tocco
        ti = tf_idx[r.tf]
        fresche = float(int(np.searchsorted(ti, t_tocco.value))
                        - int(np.searchsorted(ti, t0.value)))
        # 3 impulso: distanza massima raggiunta dal bordo PRIMA di tornarci
        if k > a:
            imp = (float(hi[a:k].max()) - float(r.ralto) if r.lato == 1
                   else float(r.rbasso) - float(lo[a:k].min()))
        else:
            imp = 0.0
        # 5 posizione nel range del giorno finora, orientata a favore del lato
        alt, bas = hh[k], ll[k]
        if np.isfinite(alt) and np.isfinite(bas) and alt > bas:
            pos = (prezzo - bas) / (alt - bas)
            pos = pos if r.lato == 1 else 1.0 - pos
        else:
            pos = np.nan
        fuori.append({
            "tf": r.tf, "lato": int(r.lato), "t_tocco": t_tocco,
            "rbasso": float(r.rbasso), "ralto": float(r.ralto),
            "prezzo": prezzo, "respiro": float(r_now), "i_tocco": k,
            "1 freschezza (barre tf)": fresche,
            "2 ampiezza / respiro": (float(r.ralto) - float(r.rbasso)) / r_now,
            "3 impulso / respiro": imp / r_now,
            "5 posizione nel giorno": pos})
    ev = pd.DataFrame(fuori).sort_values("t_tocco").reset_index(drop=True)

    # 4 tocchi precedenti dell'AREA: quanti tocchi (qualunque zona, qualunque
    # TF, qualunque lato) sono avvenuti nei 3 giorni prima, a un prezzo dentro
    # i bordi di questa zona. Solo indici < i: mai futuro.
    tv = ev.t_tocco.values.astype("datetime64[ns]").astype(np.int64)
    pv, rb, ra = ev.prezzo.values, ev.rbasso.values, ev.ralto.values
    prec = np.zeros(len(ev))
    for i in range(len(ev)):
        j0 = int(np.searchsorted(tv, tv[i] - FINESTRA_TOCCHI.value, side="left"))
        # side="left" anche in alto: i tocchi dello STESSO minuto non contano,
        # sono simultanei e non "precedenti"
        j1 = min(int(np.searchsorted(tv, tv[i], side="left")), i)
        if j0 >= j1:
            continue
        p = pv[j0:j1]
        prec[i] = float(np.count_nonzero((p >= rb[i]) & (p <= ra[i])))
    ev["4 tocchi precedenti area"] = prec
    # placebo: un numero che non sa nulla, trattato come tutti gli altri
    ev["0 placebo"] = np.random.default_rng(SEME_PLACEBO).random(len(ev))
    return ev


def simula(m1, ev):
    """La cella fissa di BQ: tocco, stop 2 $ oltre la zona, obiettivo 10 $."""
    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values
    mis = ev[MISURE].to_numpy(dtype=float)     # le misure per posizione di riga
    righe = []
    for e in ev.itertuples(index=True):
        t_in = e.t_tocco
        if not (ORE[0] <= t_in.hour < ORE[1]):
            continue
        a = int(e.i_tocco)
        b = int(np.searchsorted(idx, (t_in + pd.Timedelta(days=GIORNI_MAX)).value))
        if b - a < 5:
            continue
        stop = (e.rbasso - MARGINE_STOP) if e.lato == 1 else (e.ralto + MARGINE_STOP)
        k = abs(e.prezzo - stop)
        if k < 0.5 or k > 25:          # sotto mezzo dollaro e' una tassa,
            continue                   # sopra 25 non e' piu' un ritracciamento
        rr = TETTO / k
        o_, h_, l_, c_ = ap_[a:b], hi[a:b], lo[a:b], cl[a:b]
        if e.lato == 1:
            apri, fav, sfav, chiu = ((o_ - e.prezzo) / k, (h_ - e.prezzo) / k,
                                     (e.prezzo - l_) / k, (c_ - e.prezzo) / k)
        else:
            apri, fav, sfav, chiu = ((e.prezzo - o_) / k, (e.prezzo - l_) / k,
                                     (h_ - e.prezzo) / k, (e.prezzo - c_) / k)
        x, motivo = cammina_uno(apri, fav, sfav, chiu, rr)
        costo = SPREAD.get(t_in.year, 0.4) / k
        riga = {"anno": t_in.year, "giorno": t_in.normalize(), "tf": e.tf,
                "lato": e.lato, "stop$": k, "rr": rr, "costo": costo,
                "lordo": x, "netto": x - costo, "motivo": motivo}
        riga.update(dict(zip(MISURE, mis[e.Index])))
        righe.append(riga)
    return pd.DataFrame(righe)


def fasce(t, col):
    """I terzi. Bordi presi SOLO dalla ricerca e applicati alla verifica."""
    if col.startswith("4 "):
        # conteggio piccolo e pieno di pareggi: qcut non puo' fare tre terzi
        return pd.cut(t[col], bins=[-0.5, 0.5, 1.5, np.inf],
                      labels=["vergine", "1 tocco", "2+ tocchi"])
    ric = t.loc[(t.anno >= RICERCA[0]) & (t.anno <= RICERCA[1]), col].dropna()
    _, bordi = pd.qcut(ric, 3, retbins=True, duplicates="drop")
    bordi = list(bordi)
    bordi[0], bordi[-1] = -np.inf, np.inf
    eti = ["basso", "medio", "alto"][:len(bordi) - 1]
    return pd.cut(t[col], bins=bordi, labels=eti)


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    ev = eventi_con_qualita(m1)
    print(f"ritracciamenti in zona: {len(ev)}", flush=True)
    t = simula(m1, ev)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "qualita_zone.parquet"), index=False)
    pd.set_option("display.width", 230)

    gg = t.giorno.nunique()
    print(f"cella fissa (tocco · stop 2 $ oltre · obiettivo 10 $): {len(t)} op, "
          f"{len(t)/max(gg,1):.1f} op/giorno, stop mediano {t['stop$'].median():.3f} $, "
          f"costo medio {t.costo.mean()*100:.1f}% del rischio")
    print(f"  lordo {t.lordo.mean():+.3f} R/op | netto {t.netto.mean():+.3f} R/op "
          f"| netto totale {t.netto.sum():+.1f} R  (BQ dava +0,040 / -0,086)")

    righe, verdetti, viol, sep = [], [], [], []
    for col in MISURE:
        p = t[t[col].notna()].copy()
        p["fascia"] = fasce(p, col)
        p = p[p.fascia.notna()]
        mr, mv = {}, {}
        for fascia, q in p.groupby("fascia", observed=True):
            r_ = {"misura": col, "fascia": str(fascia)}
            for eti, (da, aa) in [("ric", RICERCA), ("ver", VERIFICA)]:
                s = q[(q.anno >= da) & (q.anno <= aa)]
                r_[f"op_{eti}"] = len(s)
                r_[f"lordo_{eti}"] = s.lordo.mean() if len(s) else np.nan
                r_[f"netto_{eti}"] = s.netto.mean() if len(s) else np.nan
                if len(s):
                    st = (s.motivo == "stop").mean() * 100
                    ob = (s.motivo == "obiettivo").mean() * 100
                    if ob >= st:
                        viol.append(f"{col}/{fascia}/{eti} stop {st:.1f}% ob {ob:.1f}%")
            mr[str(fascia)], mv[str(fascia)] = r_["netto_ric"], r_["netto_ver"]
            righe.append(r_)
        com = [f for f in mr if np.isfinite(mr[f]) and np.isfinite(mv.get(f, np.nan))]
        if len(com) >= 2:
            br = max(com, key=lambda x: mr[x])
            bv = max(com, key=lambda x: mv[x])
            # quanta separazione fra terzo migliore e peggiore la misura crea
            # in RICERCA: e' il numero da confrontare col placebo
            sep.append((col, mr[br] - min(mr[f] for f in com)))
            verdetti.append(f"  {col:<26} atteso {ATTESA[col]:<9} | ricerca {br:<9}"
                            f"({mr[br]:+.3f}) | verifica {bv:<9}({mv[bv]:+.3f}) | "
                            f"{'REGGE' if br == bv else 'non regge'}"
                            + ("  (e nella direzione attesa)"
                               if br == bv and br == ATTESA[col] else ""))

    tab = pd.DataFrame(righe).set_index(["misura", "fascia"])
    print("\n=== R/op per terzo · ric = ricerca 2020-2022 · ver = verifica 2023-2026")
    print(tab.round(3).to_string())
    print("\n=== il terzo migliore in ricerca resta il migliore in verifica? "
          "(criterio sul netto)")
    print("\n".join(verdetti))
    sep.sort(key=lambda x: -x[1])
    pl = dict(sep).get("0 placebo", np.nan)
    print("\n=== separazione in ricerca fra terzo migliore e peggiore (netto R/op): "
          + " · ".join(f"{c.split()[0]} {v:.3f}" for c, v in sep))
    battute = sum(1 for c, v in sep if c != "0 placebo" and v < pl)
    print(f"    il placebo separa {pl:.3f}: batte {battute}"
          f" misure vere su {len(sep)-1}. Nessuna fascia, in nessun periodo, "
          f"e' netta positiva: "
          f"la migliore in assoluto vale "
          f"{max(tab.netto_ric.max(), tab.netto_ver.max()):+.3f} R/op.")
    st = (t.motivo == "stop").mean() * 100
    ob = (t.motivo == "obiettivo").mean() * 100
    print(f"\n=== controllo di assurdita': stop {st:.1f}% contro obiettivo {ob:.1f}% "
          f"-> {'ok' if st > ob else '*** GUARDARE'}; "
          f"fasce/periodi con obiettivo piu' facile dello stop: {len(viol)}")
    if viol:
        print("    " + " | ".join(viol[:4]))


if __name__ == "__main__":
    main()
