#!/usr/bin/env python3
"""Appendice BY: allargare la zona raffinata sopra e sotto — quanto conta.

Richiesta dell'utente: *"possiamo anche provare ad allargare sopra e sotto di
0,5 pt la zona raffinata e vedere che succede"*.

PERCHE' LA DOMANDA HA SENSO, e non e' un parametro pescato a caso.
Le zone raffinate sono strettissime. Un esempio reale, preso dal grafico dal
vivo dell'utente: zona M33 raffinata 4075,22-4075,47, cioe' larga **0,25
dollari**. Lo spread vero dell'oro nel 2025-2026 e' **0,63 dollari**, misurato
su 6,1 milioni di tick (appendice BN). Una zona piu' STRETTA dello spread e' un
bersaglio che il prezzo puo' attraversare senza che l'operatore riesca a
entrarci: il "tocco" nel backtest diventa un evento quasi casuale, e nella
realta' l'ordine o non viene eseguito o viene eseguito a un prezzo diverso da
quello scritto. Allargarla e' quindi una **correzione di buon senso** sulla
definizione dell'evento, non l'ennesimo parametro da ottimizzare.

COSA SI CONFRONTA (quattro celle fisse, tutte riportate, nessuna scelta a
posteriori). L'allargamento e' applicato sopra E sotto la zona raffinata:

    0 $ (riferimento, la zona com'e' oggi in BQ e BV) · 0,25 $ · 0,5 $ · 1 $

Piu' una **variante relativa** come controllo: allargamento pari a 0,5 volte il
respiro M1 corrente (media dell'escursione delle ultime 30 candele M1, con
.shift(1)). Serve perche' 0,5 $ fissi valgono cose diverse con l'oro a 1.800 e
con l'oro a 4.700: il respiro M1 mediano e' passato da ~0,45 $ (2020-24) a
1,05 $ (2025) e 2,27 $ (2026) — vedi appendice BW. Se l'allargamento porta
informazione vera, la versione scritta in volatilita' dovrebbe fare almeno
quanto quella in dollari fissi.

GESTIONE FISSA, per isolare la sola variabile in esame:
  ingresso   al TOCCO della zona ALLARGATA, al prezzo del bordo allargato
             (per una zona rialzista si compra a ralto + w). E' la scelta
             conservativa: allargando si viene eseguiti PRIMA e a un prezzo
             PEGGIORE, ed e' esattamente quello che succede sul serio;
  stop       2 $ oltre il bordo della zona **ORIGINALE** non allargata. Lo
             stop non si muove: allargare l'ingresso non deve regalare anche
             uno stop piu' comodo, altrimenti si confrontano due strategie
             diverse invece che due definizioni della stessa zona;
  obiettivo  10 $ tondi, come in BQ.

CONSEGUENZA ARITMETICA DA TENERE A MENTE nel leggere i numeri (scritta prima
di guardare i risultati, non dopo): allargando, la distanza dallo stop cresce
di w e il rischio in dollari passa da ~2,25 $ a ~3,25 $. Quindi:
  - il costo dello spread in %R **scende** meccanicamente (denominatore piu'
    grande): un miglioramento del netto NON e' di per se' una notizia;
  - il rapporto obiettivo/rischio **scende** da ~4,4 a ~3,1: ci si aspetta
    piu' vinte% e meno obiettivo% senza che nulla di reale sia cambiato.
Per questo si riporta anche il **lordo in dollari** per operazione, che non
dipende dalla scala del rischio ed e' l'unico confronto davvero omogeneo.

IPOTESI PRE-REGISTRATE (scritte prima di guardare i numeri):
  A. il numero di eventi cresce con l'allargamento. Ovvio e non e' un
     risultato: serve solo come controllo che il codice faccia quel che dice;
  B. il vantaggio LORDO per operazione NON cambia in modo apprezzabile. La
     zona raffinata, secondo BQ (27.127 ritracciamenti) e BV (confluenze), non
     seleziona niente: se non seleziona, allargarla o stringerla non puo'
     cambiare il vantaggio, puo' solo cambiare quante volte si opera. Se
     invece il lordo SALE in modo ordinato con w e la salita si ripete in
     entrambi i periodi, allora la larghezza della zona era davvero un difetto
     della misura e non del mercato;
  C. la variante relativa (0,5 respiro) non batte quella in dollari fissi,
     perche' se non c'e' informazione non c'e' in nessuna unita' di misura.

LA DOMANDA CHIAVE, riportata esplicitamente in fondo all'output: allargando
la zona aumentano gli eventi (ovvio), ma il vantaggio LORDO per operazione
sale, scende o resta uguale? Se sale in ENTRAMBI i periodi e' un risultato;
se sale solo in uno e' rumore.

CONTROLLI OBBLIGATORI:
  - PLACEBO: la stessa analisi con un allargamento CASUALE fra 0 e 1 $ (rng
    con seme fisso 4242), estratto per zona e trattato identicamente. Se il
    placebo si comporta come gli allargamenti veri, l'allargamento non porta
    informazione. Avviso onesto: nelle appendici BP, BV e BU il placebo ha
    battuto tutte le ipotesi vere. Aspettarselo anche qui;
  - CONTROLLO DI ASSURDITA', stampato per ogni cella: con obiettivo lontano
    (10 $) e stop vicino, lo stop DEVE essere colpito piu' spesso
    dell'obiettivo. Se non lo e', c'e' futuro nel calcolo;
  - due periodi separati e SEMPRE entrambi riportati: ricerca 2020-2022 e
    verifica 2023-2026;
  - costi con lo spread vero per anno (appendice BN), non con una media.

NIENTE LOOKAHEAD:
  - le zone valgono solo dalla loro attivazione (chiusura della candela che
    rompe) fino a scadenza o invalidazione, come in BQ e BV;
  - il respiro M1 e' una media mobile con .shift(1);
  - l'allargamento relativo e il placebo sono fissati all'istante di
    ATTIVAZIONE della zona, non a quello del tocco: l'ordine deve stare sul
    grafico prima che il prezzo arrivi, altrimenti si sceglie la larghezza
    sapendo gia' dove il prezzo e' andato;
  - nella stessa candela lo stop prevale sull'obiettivo (``cammina_uno``).

Uso: cd <repo> && XAU_ANNI=2020-2026 python3 trading/scripts/run_zona_allargata.py
Scrive docs/studies/dati/zona_allargata.parquet
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf       # noqa: E402

from export_lab import zone_ob                                    # noqa: E402
from run_scalp_scaglioni import cammina_uno                       # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TF_ZONE = ["M6", "M12", "M33", "M66", "H2"]      # gli stessi di BQ, per confronto
K_SWING = 3
VALIDITA = 30
RESPIRO = 30                  # candele M1 su cui si misura il respiro corrente
TETTO = 10.0                  # obiettivo in dollari
MARGINE = 2.0                 # lo stop 2 $ oltre il bordo della zona ORIGINALE
ORE = (7, 21)                 # londra + new york
GIORNI_MAX = 3                # e' intraday: oltre tre giorni non e' piu' quello
K_MIN, K_MAX = 0.5, 25.0      # sotto mezzo dollaro e' una tassa, sopra 25 non
                              # e' piu' un ritracciamento
RICERCA, VERIFICA = (2020, 2022), (2023, 2026)
SEME_PLACEBO = 4242
SPREAD = {2020: 0.35, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}

# nome, tipo, parametro. Il tipo dice come si calcola l'allargamento w:
#   "fisso"    -> w = parametro, in dollari
#   "relativo" -> w = parametro * respiro M1 all'attivazione della zona
#   "placebo"  -> w = numero casuale in [0, 1] $, estratto per zona
VARIANTI = [("0,00 $ riferimento", "fisso", 0.0),
            ("0,25 $", "fisso", 0.25),
            ("0,50 $", "fisso", 0.50),
            ("1,00 $", "fisso", 1.00),
            ("0,5 respiro M1", "relativo", 0.5),
            ("PLACEBO casuale 0-1 $", "placebo", 0.0)]


def zone_tutte(m1):
    """Le zone raffinate di tutti i timeframe, in una tabella sola."""
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


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    # respiro M1 causale: media delle ultime 30 escursioni, spostata di una
    # candela. Senza lo .shift(1) la candela in corso entrerebbe nella sua
    # stessa soglia, ed e' futuro
    resp = (m1.high - m1.low).rolling(RESPIRO).mean().shift(1)
    print("zone:", flush=True)
    z = zone_tutte(m1)
    print(f"totale {len(z)} zone raffinate", flush=True)

    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values
    rv = resp.values

    # il placebo si estrae UNA volta per zona, prima di sapere cosa fara' il
    # prezzo: e' lo stesso trattamento delle varianti vere
    rng = np.random.default_rng(SEME_PLACEBO)
    w_placebo = rng.random(len(z))

    lato_v = z.lato.values.astype(np.int8)
    rb_v, ra_v = z.rbasso.values, z.ralto.values
    tf_v = z.tf.values
    t0_v = z.attiva_da.values.astype("datetime64[ns]").astype(np.int64)
    t1_v = z.fine.values.astype("datetime64[ns]").astype(np.int64)

    righe = []
    for nome, tipo, par in VARIANTI:
        for i in range(len(z)):
            t0, t1 = t0_v[i], t1_v[i]
            if t1 <= t0:
                continue
            a = int(np.searchsorted(idx, t0))
            b = int(np.searchsorted(idx, t1))
            if b - a < 2 or a >= len(rv):
                continue
            # respiro all'ATTIVAZIONE della zona: e' l'istante in cui
            # l'operatore decide dove mettere l'ordine, e non sa ancora
            # quando (ne' se) il prezzo tornera'
            r0 = rv[a]
            if not np.isfinite(r0) or r0 <= 0:
                continue
            if tipo == "fisso":
                w = float(par)
            elif tipo == "relativo":
                w = float(par) * float(r0)
            else:
                w = float(w_placebo[i])
            rb, ra, lato = float(rb_v[i]), float(ra_v[i]), int(lato_v[i])
            # zona allargata sopra e sotto: e' il bersaglio dell'ordine
            rb_w, ra_w = rb - w, ra + w
            # tocco: primo minuto in cui il prezzo entra nella zona ALLARGATA
            if lato == 1:
                dentro = np.flatnonzero(lo[a:b] <= ra_w)
            else:
                dentro = np.flatnonzero(hi[a:b] >= rb_w)
            if not len(dentro):
                continue
            k0 = a + int(dentro[0])
            t_in = pd.Timestamp(idx[k0], unit="ns", tz="UTC")
            if not (ORE[0] <= t_in.hour < ORE[1]):
                continue
            # si entra sul bordo allargato: allargando si viene serviti prima
            # e peggio, non prima e meglio
            prezzo = ra_w if lato == 1 else rb_w
            # lo stop resta ancorato alla zona ORIGINALE, non a quella allargata
            stop = (rb - MARGINE) if lato == 1 else (ra + MARGINE)
            kk = abs(prezzo - stop)
            if kk < K_MIN or kk > K_MAX:
                continue
            b2 = int(np.searchsorted(idx, (t_in + pd.Timedelta(days=GIORNI_MAX)).value))
            if b2 - k0 < 5:
                continue
            o_, h_, l_, c_ = ap_[k0:b2], hi[k0:b2], lo[k0:b2], cl[k0:b2]
            if lato == 1:
                apri, fav, sfav, chiu = ((o_ - prezzo) / kk, (h_ - prezzo) / kk,
                                         (prezzo - l_) / kk, (c_ - prezzo) / kk)
            else:
                apri, fav, sfav, chiu = ((prezzo - o_) / kk, (prezzo - l_) / kk,
                                         (h_ - prezzo) / kk, (prezzo - c_) / kk)
            x, motivo = cammina_uno(apri, fav, sfav, chiu, TETTO / kk)
            costo = SPREAD.get(t_in.year, 0.40) / kk
            righe.append({"cella": nome, "tipo": tipo, "tf": tf_v[i], "lato": lato,
                          "anno": t_in.year, "giorno": t_in.normalize(),
                          "largh$": w, "stop$": kk, "rr": TETTO / kk,
                          "costo": costo, "lordo": x, "netto": x - costo,
                          "lordo$": x * kk, "motivo": motivo})
        print(f"  {nome}: fatto", flush=True)

    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "zona_allargata.parquet"), index=False)
    pd.set_option("display.width", 230)
    ordine = [v[0] for v in VARIANTI]

    def riassunto(x):
        n = x.netto.values
        return pd.Series({
            "op": len(n), "op/g": len(n) / max(x.giorno.nunique(), 1),
            "largh$": x["largh$"].median(), "stop$": x["stop$"].median(),
            "costo%R": x.costo.mean() * 100, "lordoR": x.lordo.mean(),
            "lordo$": x["lordo$"].mean(), "nettoR": n.mean(),
            "vinte%": (n > 0).mean() * 100,
            "stop%": (x.motivo == "stop").mean() * 100,
            "ob.%": (x.motivo == "obiettivo").mean() * 100})

    for eti, (da, aa) in [("RICERCA 2020-2022", RICERCA),
                          ("VERIFICA 2023-2026", VERIFICA)]:
        p = t[(t.anno >= da) & (t.anno <= aa)]
        g = p.groupby("cella").apply(riassunto).reindex(ordine)
        print(f"\n=== {eti}")
        print(g.round(3).to_string())

    print("\n=== controllo di assurdita' (stop vicino contro obiettivo lontano)")
    for cella in ordine:
        x = t[t.cella == cella]
        s = (x.motivo == "stop").mean() * 100
        ob = (x.motivo == "obiettivo").mean() * 100
        print(f"  {cella:<22} stop {s:5.1f}%  obiettivo {ob:5.1f}%  "
              + ("ok" if s > ob else "*** GUARDARE: obiettivo piu' facile"))

    # la domanda chiave: il lordo per operazione sale, scende o resta uguale?
    # Si guarda sia in R (che risente della scala del rischio) sia in dollari
    # (che non ne risente), e si pretende lo stesso verso nei DUE periodi
    print("\n=== DOMANDA CHIAVE: allargando, il vantaggio LORDO per operazione?")
    fissi = [v[0] for v in VARIANTI if v[1] == "fisso"]
    med = {}
    for eti, (da, aa) in [("ric", RICERCA), ("ver", VERIFICA)]:
        p = t[(t.anno >= da) & (t.anno <= aa)]
        med[eti] = p.groupby("cella")[["lordo", "lordo$"]].mean().reindex(ordine)
    for col, um in [("lordo", "R/op"), ("lordo$", "$/op")]:
        r = [med["ric"].loc[c, col] for c in fissi]
        v = [med["ver"].loc[c, col] for c in fissi]
        dr, dv = r[-1] - r[0], v[-1] - v[0]
        verso = ("SALE in entrambi" if dr > 0 and dv > 0 else
                 "SCENDE in entrambi" if dr < 0 and dv < 0 else
                 "discorde fra i due periodi -> RUMORE")
        print(f"  {um}: ricerca " + " ".join(f"{x:+.3f}" for x in r)
              + f" (delta {dr:+.3f}) | verifica " + " ".join(f"{x:+.3f}" for x in v)
              + f" (delta {dv:+.3f})  ->  {verso}")
        br = max(fissi, key=lambda c: med["ric"].loc[c, col])
        bv = max(fissi, key=lambda c: med["ver"].loc[c, col])
        print(f"        migliore in ricerca: {br} | in verifica: {bv}  ->  "
              + ("REGGE" if br == bv else "non regge"))

    print("\n=== il PLACEBO (allargamento casuale 0-1 $, seme fisso)")
    pl, rif = "PLACEBO casuale 0-1 $", "0,00 $ riferimento"
    for eti in ("ric", "ver"):
        m = med[eti]
        veri = [c for c in ordine if c not in (pl, rif)]
        migliore = max(veri, key=lambda c: m.loc[c, "lordo"])
        print(f"  {eti}: placebo {m.loc[pl, 'lordo']:+.3f} R/op | riferimento "
              f"{m.loc[rif, 'lordo']:+.3f} | migliore vera {migliore} "
              f"{m.loc[migliore, 'lordo']:+.3f}  ->  "
              + ("il placebo batte tutte le vere"
                 if m.loc[pl, "lordo"] >= m.loc[migliore, "lordo"]
                 else "le vere battono il placebo"))


if __name__ == "__main__":
    main()
