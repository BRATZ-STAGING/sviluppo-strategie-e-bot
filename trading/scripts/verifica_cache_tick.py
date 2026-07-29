#!/usr/bin/env python3
"""Controlla che ogni file della cache tick sia leggibile, e ripara i guasti.

Serve dopo un download interrotto male, o dopo che due processi hanno scaricato
lo stesso periodo insieme: in quel caso possono aver scritto lo stesso file
temporaneo e rinominato un file incompleto.

Un file corrotto e' insidioso perche' NON risulta mancante: esiste, quindi il
downloader lo salta e il convertitore lo scarta come se fosse un'ora vuota.
L'ora sparisce in silenzio.

Uso:
    python verifica_cache_tick.py              solo controllo
    python verifica_cache_tick.py --ripara     cancella i file illeggibili

Dopo ``--ripara``, rilanciare ``download_ticks.py`` sullo stesso periodo: le ore
cancellate vengono riscaricate, il resto viene saltato.

Richiede solo la libreria standard.
"""
import glob
import lzma
import os
import sys

CACHE = os.environ.get("TICKS_CACHE", os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "ticks_cache"))
REC = 20


def controlla(path):
    """(esito, numero di tick). Esito: 'ok', 'vuoto', 'illeggibile', 'tronco'."""
    try:
        with open(path, "rb") as f:
            grezzo = f.read()
    except OSError:
        return "illeggibile", 0
    if not grezzo:
        return "vuoto", 0
    try:
        dati = lzma.decompress(grezzo)
    except (lzma.LZMAError, EOFError):
        return "illeggibile", 0
    if len(dati) % REC:
        return "tronco", len(dati) // REC
    return "ok", len(dati) // REC


def main():
    ripara = "--ripara" in sys.argv
    files = sorted(glob.glob(os.path.join(CACHE, "*.bi5")))
    if not files:
        print(f"nessun .bi5 in {CACHE} — imposta TICKS_CACHE")
        sys.exit(1)

    print(f"cache: {CACHE}\n{len(files)} file da controllare", flush=True)
    conteggi = {"ok": 0, "vuoto": 0, "illeggibile": 0, "tronco": 0}
    tick = 0
    guasti = []
    temporanei = glob.glob(os.path.join(CACHE, "*.tmp"))

    for i, path in enumerate(files, 1):
        esito, n = controlla(path)
        conteggi[esito] += 1
        if esito == "ok":
            tick += n          # solo i file integri: gli altri vanno riscaricati
        if esito != "ok":
            guasti.append((path, esito))
        if i % 5000 == 0:
            print(f"  {i}/{len(files)}...", flush=True)

    print(f"\nleggibili   {conteggi['ok']:>6}   ({tick:,} tick)")
    for k in ("vuoto", "illeggibile", "tronco"):
        if conteggi[k]:
            print(f"{k:<11} {conteggi[k]:>6}")
    if temporanei:
        print(f"file .tmp rimasti a meta': {len(temporanei)}")

    if not guasti and not temporanei:
        print("\ncache integra: nessun file da riscaricare")
        return

    if not ripara:
        print("\nda cancellare e riscaricare:")
        for path, esito in guasti[:20]:
            print(f"  {os.path.basename(path)}  ({esito})")
        if len(guasti) > 20:
            print(f"  ...e altri {len(guasti)-20}")
        print("\nrilancia con --ripara per cancellarli, "
              "poi riesegui download_ticks.py sullo stesso periodo")
        return

    for path, _ in guasti:
        os.remove(path)
    for path in temporanei:
        os.remove(path)
    print(f"\ncancellati {len(guasti)} file corrotti e {len(temporanei)} temporanei")
    print("ora riesegui download_ticks.py sullo stesso periodo")


if __name__ == "__main__":
    main()
