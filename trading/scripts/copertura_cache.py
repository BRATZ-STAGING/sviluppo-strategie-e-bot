#!/usr/bin/env python3
"""Dice cosa copre davvero la cache tick, prima di convertirla.

Serve a rispondere in un colpo solo a "cosa ho scaricato finora?": quali anni,
da che giorno a che giorno, e quante ore risultano mai tentate. Non converte
niente e non tocca niente, legge solo i nomi dei file: gira in un secondo anche
su una cache di decine di migliaia di ore.

Uso (Windows, PowerShell):
    $env:TICKS_CACHE = "C:\\dukascopy\\ticks_cache"
    python copertura_cache.py

Richiede: solo la libreria standard.

Un'ora e' considerata coperta se esiste ``YYYY-MM-DD_HH.bi5`` (ci sono tick)
oppure ``YYYY-MM-DD_HH.empty`` (scaricata, mercato fermo). Mancante significa
ne' l'uno ne' l'altro: mai scaricata. I sabati non contano, il mercato e'
chiuso. Le ore mancanti sono cercate solo fra il primo e l'ultimo giorno
presenti nell'anno: un anno scaricato a meta' non viene contato come pieno di
buchi.

Che i file siano leggibili e' un'altra domanda, e la risponde
``verifica_cache_tick.py``: qui un .bi5 corrotto risulta comunque presente.
"""
import datetime as dt
import glob
import os
import sys

CACHE = os.environ.get("TICKS_CACHE", os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "ticks_cache"))
MAX_MESI = 15                      # righe di dettaglio, per non allagare la chat


def scansiona(cache):
    """{(anno, mese, giorno, ora): 'tick'|'vuota'} da tutti i nomi di file."""
    ore = {}
    for suffisso, etichetta in ((".bi5", "tick"), (".empty", "vuota")):
        for path in glob.glob(os.path.join(cache, "*" + suffisso)):
            nome = os.path.basename(path)[:-len(suffisso)]
            try:                                   # YYYY-MM-DD_HH
                giorno = dt.date.fromisoformat(nome[:10])
                ora = int(nome[11:13])
            except (ValueError, IndexError):
                continue
            if 0 <= ora <= 23:
                ore.setdefault((giorno, ora), etichetta)
    return ore


def attese(primo, ultimo):
    """Le ore feriali fra due date comprese: quelle che ha senso aspettarsi."""
    giorno, totale = primo, 0
    while giorno <= ultimo:
        if giorno.weekday() != 5:                  # sabato: mercato chiuso
            totale += 24
        giorno += dt.timedelta(days=1)
    return totale


def main():
    if not os.path.isdir(CACHE):
        print(f"ERRORE: cache non trovata in {CACHE}")
        print("Imposta TICKS_CACHE con la cartella dei file .bi5.")
        sys.exit(1)

    ore = scansiona(CACHE)
    print(f"cache: {CACHE}")
    if not ore:
        print("nessun file .bi5 o .empty: qui non c'e' niente di scaricato.")
        sys.exit(1)

    anni, mesi = {}, {}
    for (giorno, _ora), tipo in ore.items():
        for chiave, dove in ((giorno.year, anni), ((giorno.year, giorno.month), mesi)):
            d = dove.setdefault(chiave, {"tick": 0, "vuota": 0,
                                         "primo": giorno, "ultimo": giorno})
            d[tipo] += 1
            d["primo"] = min(d["primo"], giorno)
            d["ultimo"] = max(d["ultimo"], giorno)

    print(f"{len(ore)} ore in cache\n")
    print("anno    dal          al           ore tick   ore vuote   mai scaricate")
    totale_buchi = 0
    for anno in sorted(anni):
        d = anni[anno]
        buchi = attese(d["primo"], d["ultimo"]) - d["tick"] - d["vuota"]
        totale_buchi += max(buchi, 0)
        print(f"{anno}    {d['primo']}   {d['ultimo']}   {d['tick']:>8}   "
              f"{d['vuota']:>9}   {max(buchi, 0):>13}")

    incompleti = []
    for (anno, mese) in sorted(mesi):
        d = mesi[(anno, mese)]
        buchi = attese(d["primo"], d["ultimo"]) - d["tick"] - d["vuota"]
        if buchi > 0:
            incompleti.append((f"{anno}-{mese:02d}", buchi))
    if incompleti:
        print(f"\nmesi con ore mai scaricate ({len(incompleti)}):")
        for nome, buchi in incompleti[:MAX_MESI]:
            print(f"  {nome}  {buchi} ore")
        if len(incompleti) > MAX_MESI:
            print(f"  ...e altri {len(incompleti) - MAX_MESI} mesi")
        print("\nsono ore fra il primo e l'ultimo giorno presenti, mai tentate:")
        print("rilancia download_ticks.py su quel periodo, salta cio' che c'e' gia'.")
    else:
        print("\nnessuna ora mai scaricata fra il primo e l'ultimo giorno di ogni anno.")
    print("\nper sapere se i file sono anche leggibili: python verifica_cache_tick.py")


if __name__ == "__main__":
    main()
