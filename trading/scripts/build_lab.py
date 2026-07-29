#!/usr/bin/env python3
"""Costruisce la pagina del laboratorio dal template e dai dati.

Prima questa sostituzione si faceva a mano ogni volta, con il rischio di
pubblicare una pagina costruita in modo diverso dalla precedente. Ora e' un
comando, e la pagina porta scritto da quale versione del repository viene.

Uso:
    python build_lab.py <lab.json> <lab.html>          pagina con dati dentro
    python build_lab.py --vuoto <lab.html>             pagina per l'applicazione

La forma ``--vuoto`` lascia il segnaposto ``__DATA__``: la pagina in quel caso
chiede i dati a ``/api/dati``, cioe' al server locale. Il front-end e' lo
stesso nei due casi, vedi ``docs/piano-app.md``.
"""
import os
import subprocess
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(QUI, "lab_template.html")
SEGNAPOSTO = "__DATA__"


def versione():
    """Commit corrente del repository, per sapere cosa si sta guardando."""
    try:
        out = subprocess.run(["git", "-C", QUI, "describe", "--always", "--dirty"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "sconosciuta"
    except (OSError, subprocess.SubprocessError):
        return "sconosciuta"


def costruisci(dati: str | None, out_path: str) -> None:
    with open(TEMPLATE, encoding="utf-8") as f:
        pagina = f.read()
    if SEGNAPOSTO not in pagina:
        raise SystemExit(f"{TEMPLATE}: manca il segnaposto {SEGNAPOSTO}")
    pagina = pagina.replace(SEGNAPOSTO, dati if dati is not None else SEGNAPOSTO, 1)
    pagina = pagina.replace("<!--VERSIONE-->", f"<!-- build {versione()} -->", 1)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(pagina)


def main():
    argomenti = sys.argv[1:]
    if not argomenti:
        print(__doc__)
        sys.exit(1)

    if argomenti[0] == "--vuoto":
        if len(argomenti) < 2:
            raise SystemExit("serve il percorso di uscita")
        costruisci(None, argomenti[1])
        print(f"{argomenti[1]}: pagina senza dati (li chiedera' a /api/dati)")
        return

    if len(argomenti) < 2:
        raise SystemExit("serve <lab.json> <lab.html>")
    json_path, out_path = argomenti[0], argomenti[1]
    with open(json_path, encoding="utf-8") as f:
        dati = f.read().strip()
    if not dati.startswith("{"):
        raise SystemExit(f"{json_path} non sembra un JSON")
    costruisci(dati, out_path)
    mb = os.path.getsize(out_path) / 1e6
    print(f"{out_path}: {mb:.2f} MB  (build {versione()})")


if __name__ == "__main__":
    main()
