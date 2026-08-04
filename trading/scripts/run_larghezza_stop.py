#!/usr/bin/env python3
"""Appendice BT: la CURVA del risultato in funzione della larghezza dello stop.

LA DOMANDA DELL'UTENTE, alla lettera: *"invece che 3 punti mettere 4 punti di
stop va benissimo, qual e' la larghezza giusta?"*.

Fin qui il progetto ha misurato tre punti isolati di questa curva e li ha
riportati come verdetti separati:
  - appendice BM: stop 3 $ / obiettivo 5 $ e stop 5 $ / obiettivo 8 $, netto
    negativo sul campione largo (-0,051 e -0,011 R/op);
  - appendice BO: stop scritto in volatilita' (0,89 $ mediano), netto molto
    peggiore ancora (-0,19 / -0,37 R/op), perche' lo spread si mangia il 33%
    del rischio;
  - appendice BN: lo spread VERO e' 0,33-0,40 $ fino al 2024 e 0,63 $ dal
    2025, non lo 0,30 ipotizzato nella taratura.

Tre punti non sono una curva, e una curva e' esattamente quello che serve per
rispondere: il netto in funzione della larghezza dello stop e' monotono
crescente (allora "la larghezza giusta" e' semplicemente "la piu' larga
possibile", cioe' lo stop strutturale che gia' abbiamo), oppure ha un massimo
interno (allora esiste davvero un numero da scegliere, e va detto quale).

COSA VARIA E COSA RESTA FERMO. Cambia SOLO la gestione dell'uscita: le
operazioni sono sempre le stesse prodotte da ``framework.segnali.genera`` con
la taratura ufficiale, cosi' il confronto isola una variabile sola e i numeri
restano confrontabili con BM, BO e BR. Lo stop e' FISSO in dollari, da 2 a 20
a passi di 1 (venti dollari e' gia' oltre lo stop strutturale mediano di quasi
tutti gli anni: serve a vedere dove la curva smette di salire, non perche' sia
una proposta).

PERCHE' SOLO 1:2 E 1:3, e non una griglia di obiettivi. Perche' l'appendice BR
ha gia' misurato che, fra gli obiettivi vicini, **1:2 e' l'unico che
sopravvive** a parita' di rendimento (45,7% di vincite, drawdown 5,7%, 7
perdite di fila contro le 25 dell'ufficiale). 1:3 e' tenuto come controllo, per
sapere se l'eventuale conclusione dipende dall'obiettivo scelto o e' una
proprieta' della larghezza dello stop. Aggiungere altri obiettivi sarebbe
grid-mining, che CLAUDE.md vieta e che l'appendice BP ha appena tarato: con
questi campioni mezzo R di separazione apparente nasce dal nulla.

COSTI. Spread vero per anno dall'appendice BN, non lo 0,30 della taratura. Per
gli anni 2009-2019, che BN non ha misurato (i tick Dukascopy usati partivano dal
2021), si usa 0,40 $: e' il massimo degli anni misurati prima del salto del
2025, quindi la scelta e' PRUDENTE nel senso giusto — se il vecchio storico
esce positivo, non e' per uno spread regalato. Se fosse uscito negativo solo
per quello, sarebbe stato un problema; si vedra' nei numeri.

TRE PERIODI, dichiarati prima: 2009-2019 (undici anni mai usati per tarare
nulla: l'oro laterale del 2013-2018, un mondo diverso), 2020-2022 (il periodo
di ricerca di tutto il progetto) e 2023-2026 (la verifica fuori campione, e
l'unico che contiene il regime di volatilita' e di spread di oggi). Una
larghezza di stop che vada bene deve andare bene in tutti e tre: se e'
positiva solo dove e' stata cercata, e' una coincidenza.

IPOTESI PRE-REGISTRATE (scritte prima di guardare i risultati):

  A. La curva del netto e' **monotona crescente** nella larghezza dello stop,
     senza massimo interno. Motivo: il costo in %R vale spread/stop, quindi
     scende come 1/larghezza (dal 17,5% a 2 $ all'1,75% a 20 $), mentre il
     vantaggio lordo dell'ingresso non ha ragione di peggiorare allargando lo
     stop — al piu' resta piatto, perche' uno stop piu' largo toglie solo le
     uscite per rumore. Se A e' vera, la risposta all'utente e' che "3 o 4
     punti" e' la domanda sbagliata: non esiste una larghezza giusta stretta,
     esiste solo un limite inferiore sotto il quale non si paga lo spread.

  B. Esiste una **soglia di pareggio**, cioe' la larghezza sotto la quale il
     netto e' negativo e sopra la quale e' positivo. Stima a priori dai numeri
     gia' noti: il vantaggio lordo di questo ingresso con obiettivi vicini vale
     0,04-0,05 R/op (BM), e a 1:2 il costo vale spread/stop; con spread 0,45 $
     medio il pareggio cade intorno a 0,45/0,045 = **10 $ di stop**. Sotto i
     10 $ mi aspetto netto negativo, sopra positivo ma piccolo.

  C. La soglia di pareggio e' **piu' alta nel 2023-2026** che negli altri due
     periodi, perche' li' lo spread e' quasi doppio (0,63 contro 0,33-0,40) e
     l'escursione dell'M1 e' quintuplicata. Se C e' vera, la larghezza che
     "andava bene" negli anni vecchi e' proprio quella che oggi non paga piu',
     ed e' la ragione tecnica per cui l'idea dei pochi punti continua a
     sembrare buona quando si guarda lo storico lungo.

  D. Nessuna larghezza sara' positiva su tutti e tre i periodi con entrambi gli
     obiettivi. E' la previsione piu' esposta e la piu' facile da smentire: se
     un numero esce positivo ovunque, va detto chiaramente e va preso sul
     serio.

NIENTE LOOKAHEAD. Non ci sono feature rolling calcolate qui (lo stop e'
costante e l'obiettivo e' un multiplo dello stop, entrambi noti al momento
dell'ingresso); l'unica finestra mobile del motore, l'ATR che riscala le soglie
nei mesi agitati, e' gia' causale dentro ``genera``. Il percorso
dell'operazione e' letto minuto per minuto in avanti, e a parita' di minuto lo
**stop prevale sull'obiettivo**, come impone la regola conservativa del
progetto. L'apertura della candela e' controllata per prima, cosi' un salto di
prezzo che scavalca lo stop viene incassato al prezzo vero e non al livello
teorico.

UNA NOTA SUL MOTORE. La funzione di riferimento e' ``cammina_uno`` di
run_scalp_scaglioni.py, un ciclo Python minuto per minuto. Qui servono
19 larghezze x 2 obiettivi x qualche migliaio di operazioni x fino a 30 giorni
di candele: il ciclo diretto sarebbe un'ora. ``cammina_veloce`` fa la stessa
cosa con quattro ricerche binarie su inviluppi cumulativi (il massimo corrente
del favorevole, il peggio corrente dello sfavorevole e i due estremi delle
aperture sono monotoni per costruzione, quindi il primo minuto in cui una
soglia viene toccata si trova con searchsorted). Le due funzioni sono
confrontate su un campione casuale a ogni esecuzione e lo script si ferma se
non danno lo stesso risultato: e' l'unico modo onesto di usare la versione
veloce.

ORIZZONTE, ed e' la trappola di questo studio. 30 giorni di calendario
dall'ingresso, lo stesso di BM, BO e BR, per restare confrontabili. Ma uno
stop fisso di 16 $ nel 2013, con l'oro a 1.300 e l'escursione M1 a 0,1 $, non
e' la stessa cosa di 16 $ nel 2026: e' uno stop enorme, e l'operazione puo'
restare aperta per giorni. Un risultato "positivo" ottenuto tenendo la
posizione una settimana NON risponde alla domanda dell'utente, che parla di
uno scalp. Per questo ogni blocco riporta la **durata mediana in ore** e la
percentuale di operazioni che sopravvivono **oltre un giorno** di mercato
(1.440 candele M1): senza quelle due righe la tabella del netto si legge male.

Uso: cd <repo> && XAU_ANNI=2009-2026 python3 trading/scripts/run_larghezza_stop.py
Scrive docs/studies/dati/larghezza_stop.parquet
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

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GIORNI_MAX = 30                  # orizzonte, come in BM/BO/BR
MEDIANA_ATR = 25.5968            # riferimento 2020-2024, congelato nelle schede
LARGHEZZE = list(range(2, 21))   # stop fisso in dollari, da 2 a 20
OBIETTIVI = [2.0, 3.0]           # RR 1:2 (il superstite di BR) e 1:3 (controllo)
# spread vero misurato tick per tick nell'appendice BN; per il 2009-2019, non
# coperto da quella misura, si usa 0,40 $ = il peggiore degli anni misurati
# prima del raddoppio del 2025 (scelta prudente, vedi docstring)
SPREAD = {2020: 0.35, 2021: 0.349, 2022: 0.395, 2023: 0.334,
          2024: 0.384, 2025: 0.632, 2026: 0.631}
SPREAD_VECCHIO = 0.40
PERIODI = [("2009-2019", 2009, 2019), ("2020-2022", 2020, 2022),
           ("2023-2026", 2023, 2026)]


def cammina_uno(apri, fav, sfav, chiu, rr):
    """Riferimento: un solo obiettivo, minuto per minuto (da run_scalp_scaglioni).

    Percorsi in unita' di rischio. Lo stop prevale sull'obiettivo a parita' di
    minuto, e l'apertura viene guardata prima degli estremi della candela.
    Torna anche il minuto di uscita, che serve a sapere se l'operazione e'
    ancora intraday o e' diventata una posizione tenuta per giorni.
    Serve solo a validare ``cammina_veloce``: e' troppo lenta per lo studio.
    """
    for i in range(len(fav)):
        if apri[i] <= -1.0:
            return apri[i], "gap", i
        if apri[i] >= rr:
            return apri[i], "gap+", i
        if sfav[i] >= 1.0:
            return -1.0, "stop", i
        if fav[i] >= rr:
            return float(rr), "obiettivo", i
    return chiu[-1], "scadenza", len(fav) - 1


def inviluppi(apri, fav, sfav):
    """I quattro inviluppi monotoni che rendono la ricerca binaria lecita.

    In dollari, non in R: cosi' si calcolano UNA volta per operazione e valgono
    per tutte e diciannove le larghezze di stop. Sono monotoni per costruzione
    (sono massimi/minimi correnti), quindi il primo minuto in cui una soglia
    viene superata e' un ``searchsorted``.
    """
    return (-np.minimum.accumulate(apri),      # quanto sotto ha aperto, al peggio
            np.maximum.accumulate(apri),       # quanto sopra ha aperto, al meglio
            np.maximum.accumulate(sfav),       # escursione contraria peggiore
            np.maximum.accumulate(fav))        # escursione a favore migliore


def cammina_veloce(env, apri, chiu, k, rr):
    """Stessa semantica di ``cammina_uno``, con quattro ricerche binarie.

    ``k`` e' lo stop in dollari, l'obiettivo e' ``rr*k`` dollari. L'ordine di
    priorita' a parita' di minuto e' quello del ciclo di riferimento: salto
    oltre lo stop, salto oltre l'obiettivo, stop, obiettivo.
    """
    giu, su, peggio, meglio = env
    n = len(apri)
    ob = rr * k
    i_gs = int(np.searchsorted(giu, k))          # apertura sotto lo stop
    i_gt = int(np.searchsorted(su, ob))          # apertura oltre l'obiettivo
    i_s = int(np.searchsorted(peggio, k))        # minimo/massimo contrario
    i_t = int(np.searchsorted(meglio, ob))       # minimo/massimo a favore
    m = min(i_gs, i_gt, i_s, i_t)
    if m >= n:
        return chiu[-1] / k, "scadenza", n - 1
    if i_gs == m:
        return apri[m] / k, "gap", m
    if i_gt == m:
        return apri[m] / k, "gap+", m
    if i_s == m:
        return -1.0, "stop", m
    return float(rr), "obiettivo", m


def verifica_motore(percorsi, quanti=250, seme=12345):
    """Confronta veloce e riferimento su combinazioni casuali (op, stop, RR).

    Senza questo controllo la versione veloce sarebbe una scorciatoia di cui
    fidarsi sulla parola, e questo progetto ha gia' pagato un lookahead
    scoperto tardi.
    """
    rng = np.random.default_rng(seme)
    diff = 0
    for _ in range(quanti):
        j = int(rng.integers(len(percorsi)))
        k = float(rng.choice(LARGHEZZE))
        rr = float(rng.choice(OBIETTIVI))
        env, apri, fav, sfav, chiu = percorsi[j]
        r1, m1_, i1 = cammina_veloce(env, apri, chiu, k, rr)
        r2, m2_, i2 = cammina_uno(apri / k, fav / k, sfav / k, chiu / k, rr)
        if m1_ != m2_ or abs(r1 - r2) > 1e-9 or i1 != i2:
            diff += 1
    return quanti - diff, quanti


def etichetta_periodo(anno):
    for nome, da, a in PERIODI:
        if da <= anno <= a:
            return nome
    return "fuori"


def main():
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"))
    # La mediana ATR di riferimento e' quella del 2020-2024 congelata nelle
    # schede. Va passata a mano: ricalcolarla su 2009-2026 vorrebbe dire
    # cambiare le soglie di TUTTO il progetto dentro uno studio sull'uscita.
    tutte = genera(m1, T, mediana_atr=MEDIANA_ATR)
    ufficiale = [bool(all(o[f"c_{tf}"] for tf in T.conferme)
                      and all(not o[f"c_{tf}"] for tf in T.ritracciamento))
                 for o in tutte]
    print(f"campione largo {len(tutte)} | ufficiali {sum(ufficiale)}", flush=True)

    idx = pd.DatetimeIndex(m1.index).as_unit("ns").asi8
    ap_, hi, lo, cl = m1.open.values, m1.high.values, m1.low.values, m1.close.values

    # Fase 1: i percorsi in dollari, una volta sola per operazione. Il costo di
    # tutto lo studio sta qui; le 38 celle per operazione sono poi ricerche
    # binarie sugli stessi inviluppi.
    percorsi, meta = [], []
    for o, uff in zip(tutte, ufficiale):
        t_in = pd.Timestamp(o["time"]).tz_convert("UTC")
        a = int(np.searchsorted(idx, t_in.value))
        b = int(np.searchsorted(idx, (t_in + pd.Timedelta(days=GIORNI_MAX)).value))
        if b - a < 2:
            continue
        e = o["entry"]
        o_, h_, l_, c_ = ap_[a:b], hi[a:b], lo[a:b], cl[a:b]
        if o["lato"] == "long":
            apri, fav, sfav, chiu = o_ - e, h_ - e, e - l_, c_ - e
        else:
            apri, fav, sfav, chiu = e - o_, e - l_, h_ - e, e - c_
        percorsi.append((inviluppi(apri, fav, sfav), apri, fav, sfav, chiu))
        meta.append((int(o["anno"]), bool(uff), t_in))

    ok, tot = verifica_motore(percorsi)
    print(f"verifica motore veloce contro riferimento: {ok}/{tot} identiche",
          flush=True)
    if ok != tot:
        raise SystemExit("motore veloce non equivalente: studio interrotto")

    # Fase 2: la griglia. 19 larghezze x 2 obiettivi su ogni operazione.
    righe = []
    for (env, apri, fav, sfav, chiu), (anno, uff, quando) in zip(percorsi, meta):
        spread = SPREAD.get(anno, SPREAD_VECCHIO)
        for k in LARGHEZZE:
            costo = spread / k
            for rr in OBIETTIVI:
                r, motivo, i = cammina_veloce(env, apri, chiu, float(k), rr)
                righe.append({"stop$": k, "rr": rr, "anno": anno,
                              "periodo": etichetta_periodo(anno),
                              "ufficiale": uff, "data": quando,
                              "costo": costo, "lordo": r, "netto": r - costo,
                              "motivo": motivo, "minuti": int(i)})
    t = pd.DataFrame(righe)
    t.to_parquet(os.path.join(ROOT, "docs", "studies", "dati",
                              "larghezza_stop.parquet"), index=False)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)
    col = [str(k) for k in LARGHEZZE]

    def per_larghezza(x, f):
        """Una riga della curva: la funzione ``f`` valutata a ogni larghezza."""
        return pd.Series({str(k): f(x[x["stop$"] == k]) for k in LARGHEZZE})

    # quante operazioni ci sono, per campione e periodo: non dipende ne' dallo
    # stop ne' dall'obiettivo, quindi si conta su una cella qualunque
    una = t[(t["stop$"] == LARGHEZZE[0]) & (t.rr == OBIETTIVI[0])]
    conte = []
    for eti, sel in [("ufficiali", una[una.ufficiale]), ("largo", una)]:
        r = {nome: int((sel.periodo == nome).sum()) for nome, _, _ in PERIODI}
        r["tutti"] = len(sel)
        conte.append(pd.Series(r, name=eti))
    print("\n=== operazioni disponibili (indipendenti dalla larghezza dello stop)")
    print(pd.DataFrame(conte).to_string())

    # il costo NON dipende dall'obiettivo: una sola riga per campione, presa su
    # un solo RR per non contare due volte le stesse operazioni
    base = t[t.rr == OBIETTIVI[0]]
    print("\n=== il costo: spread vero / stop, in % del rischio (colonne = stop $)")
    costi = pd.DataFrame(
        [per_larghezza(base[base.ufficiale], lambda x: x.costo.mean() * 100),
         per_larghezza(base, lambda x: x.costo.mean() * 100)],
        index=["costo%R uff", "costo%R largo"])[col]
    print(costi.round(2).to_string())

    for eti, sel_all in [("ufficiali", t[t.ufficiale]), ("largo", t)]:
        for rr in OBIETTIVI:
            x = sel_all[sel_all.rr == rr]
            blocco = pd.DataFrame([
                per_larghezza(x, lambda y: y.lordo.mean()),
                per_larghezza(x, lambda y: y.netto.mean()),
                per_larghezza(x, lambda y: (y.netto > 0).mean() * 100),
                per_larghezza(x, lambda y: y.netto.sum()),
                per_larghezza(x, lambda y: y.minuti.median() / 60.0),
                per_larghezza(x, lambda y: (y.minuti > 1440).mean() * 100),
            ], index=["lordo R/op", "netto R/op", "vinte%", "netto R tot",
                      "durata h med", "oltre 1g%"])[col]
            print(f"\n=== campione {eti}, obiettivo 1:{rr:.0f} "
                  f"(colonne = larghezza dello stop in $)")
            print(blocco.round(3).to_string())

    # LA RISPOSTA. Non basta che il totale sia positivo: deve esserlo in tutti
    # e tre i periodi, altrimenti e' un numero che ha funzionato in un regime.
    print("\n=== la risposta: MINIMO del netto R/op fra i tre periodi "
          "(>0 = positivo ovunque)")
    nomi_periodi = [nome for nome, _, _ in PERIODI]

    def minimo_tre(y):
        """Il peggiore dei tre periodi. Se un periodo manca il risultato e' NaN.

        Senza questa reindicizzazione, caricare meno anni farebbe passare per
        "positivo ovunque" un numero misurato in un solo regime: e' proprio
        l'errore che questo studio deve evitare.
        """
        m = y.groupby("periodo").netto.mean().reindex(nomi_periodi)
        return m.min(skipna=False)

    minimi, vincenti = [], []
    for eti, sel_all in [("uff", t[t.ufficiale]), ("largo", t)]:
        for rr in OBIETTIVI:
            x = sel_all[sel_all.rr == rr]
            nome = f"{eti} 1:{rr:.0f}"
            s = per_larghezza(x, minimo_tre)
            s.name = nome
            minimi.append(s)
            for k in LARGHEZZE:
                if s[str(k)] > 0:
                    vincenti.append((nome, k, float(s[str(k)])))
    print(pd.DataFrame(minimi)[col].round(3).to_string())

    if not vincenti:
        print("\nRISPOSTA: NO. Nessuna larghezza fra 2 e 20 $ e' netta positiva "
              "su tutti e tre i periodi, con nessuno dei due obiettivi.")
    else:
        print(f"\nRISPOSTA: SI, {len(vincenti)} combinazioni positive in tutti "
              f"e tre i periodi. Le migliori:")
        for nome, k, v in sorted(vincenti, key=lambda z: -z[2])[:6]:
            print(f"  {nome} stop {k} $ -> minimo fra i periodi {v:+.3f} R/op")

    # Il dettaglio per periodo della cella migliore serve a capire SE il numero
    # e' positivo con margine o per un pelo: una differenza che cambia la
    # risposta pratica da dare all'utente.
    print("\n=== netto R/op | durata mediana in ore, per periodo, campione largo")
    for rr in OBIETTIVI:
        x = t[(t.rr == rr) & t["stop$"].isin([3, 4, 5, 8, 12, 16, 20])]
        p = x.pivot_table(index="stop$", columns="periodo", values="netto",
                          aggfunc="mean")
        d = x.pivot_table(index="stop$", columns="periodo", values="minuti",
                          aggfunc="median") / 60.0
        print(f"-- obiettivo 1:{rr:.0f}")
        print(p.round(3).join(d.round(1), lsuffix=" R/op", rsuffix=" h")
              .to_string())
    print(f"\nscadenza a {GIORNI_MAX} giorni: al massimo "
          f"{(t.motivo == 'scadenza').groupby([t['stop$'], t.rr]).mean().max()*100:.1f}%"
          " delle celle; il dettaglio per operazione e' nel parquet.")


if __name__ == "__main__":
    main()
