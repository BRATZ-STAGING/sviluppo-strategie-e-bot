#!/usr/bin/env python3
"""Rompe apposta il nucleo dell'EA, per vedere se il confronto se ne accorge.

`confronta.py` ha detto "nessuna divergenza" al primo colpo. Un confronto che
dice sempre di si' e' peggio di nessun confronto: sembra una verifica. Questo
script introduce nel nucleo, uno alla volta, gli errori tipici — quelli che le
schede elencano come trappole — e pretende che il confronto FALLISCA. Se una
mutazione passa inosservata, il confronto non sta misurando quella cosa e va
detto.

E' la stessa regola degli script per il PC (`CLAUDE.md`): "gira" non e' una
prova, il numero va falsificato.

Uso:
    python3 falsifica.py          # usa la finestra breve, 2023-2026

Richiede: pandas, pyarrow, g++.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

QUI = Path(__file__).resolve().parent

# Ogni mutazione: (nome, da cercare, sostituto[, atteso]). "atteso" vale
# "scoperta" (l'errore DEVE far fallire il confronto) oppure "equivalente"
# (la mutazione non cambia il comportamento su questi dati, e il confronto
# giustamente non la vede: e' un fatto misurato, non una scusa).
# Sono gli errori che AVVIO-MT5-VPS.md §2 elenca come gia' costati una misura.
MUTAZIONI = [
    ("M33 ancorato alla mezzanotte invece che all'epoch",
     "datetime AggBin(const datetime t, const int secondi)\n{\n   return (datetime)((t / secondi) * secondi);\n}",
     "datetime AggBin(const datetime t, const int secondi)\n{\n   const datetime g = (datetime)((t / 86400) * 86400);\n   return (datetime)(g + ((t - g) / secondi) * secondi);\n}"),

    ("stop calcolato su 4 candele invece di 5",
     "   p.barreStop    = 5;",
     "   p.barreStop    = 4;"),

    ("finestra oraria 07-18 invece di 07-19",
     "   p.oraFine      = 19;",
     "   p.oraFine      = 18;"),

    # EQUIVALENTE, e va spiegato invece di lasciare il test rosso per sempre.
    # Il 3b chiede che M12 NON sia allineato: uno stato neutro va bene. Scritto
    # "== -lato" pretenderebbe il contrario esatto. Le due scritture cadono
    # d'accordo ovunque tranne quando M12 e' neutro, e su 682 segnali grezzi
    # del 2023-2026 NESSUN timeframe e' mai neutro: dopo la prima rottura
    # strutturale lo stato non torna piu' a zero. Misurato, non supposto.
    # Resta scritto "!= lato" perche' e' quello che fa il motore, e perche' a
    # terminale appena avviato lo stato E' zero — ma li' l'EA non opera
    # ancora, gli mancano le 250 giornate di riscaldamento.
    ("ritracciamento preteso contrario invece che non-allineato",
     "      const bool ritr  = (e.stM12 != lato);",
     "      const bool ritr  = (e.stM12 == -lato);", "equivalente"),

    ("swing confermato a 2 candele invece di 3",
     "   p.frattaleK    = 3;",
     "   p.frattaleK    = 2;"),

    ("soglie mai riscalate sull'ATR nei mesi agitati",
     "   if(m.meseAgitato)\n   {\n      double atrOggi = 0.0;",
     "   if(false)\n   {\n      double atrOggi = 0.0;"),

    ("il tetto giornaliero conta solo le operazioni aperte",
     "      if(e.consuma) { segnali++; MotoreRegistraIngresso(m, e.istante); }",
     "      if(e.apre) { MotoreRegistraIngresso(m, e.istante); }\n      if(e.consuma) segnali++;"),
]

ANNI = ("2023", "2026", "2025-01", "2026-06")


def esegui(cartella: Path) -> int:
    """Lancia confronta.py su una copia del bot; ritorna il codice d'uscita."""
    r = subprocess.run([sys.executable, str(cartella / "verifica" / "confronta.py"),
                        *ANNI], capture_output=True, text=True,
                       env={**os.environ, "SCRATCH": os.environ.get("SCRATCH", "/tmp")})
    return r.returncode, r.stdout


def main():
    repo = QUI.parents[3]
    esiti = []

    # 1. il nucleo intatto deve passare
    codice, _ = esegui(QUI.parent)
    esiti.append(("nucleo intatto", codice == 0, "passa" if codice == 0 else "FALLISCE"))

    # 2. ogni mutazione deve far fallire il confronto
    for voce in MUTAZIONI:
        nome, prima, dopo = voce[0], voce[1], voce[2]
        atteso = voce[3] if len(voce) > 3 else "scoperta"
        with tempfile.TemporaryDirectory() as tmp:
            finto = Path(tmp) / "bots" / "mt5" / "vwap-reclaim"
            finto.parent.mkdir(parents=True)
            shutil.copytree(QUI.parent, finto)
            # confronta.py risale di quattro cartelle per trovare il repository:
            # il ponte serve a fargli trovare data/ e trading/ veri
            for nome_link in ("data", "trading"):
                (Path(tmp) / nome_link).symlink_to(repo / nome_link)
            for f in (finto / "VwapReclaimCore.mqh", finto / "verifica" / "banco.cpp"):
                testo = f.read_text()
                if prima in testo:
                    f.write_text(testo.replace(prima, dopo, 1))
                    break
            else:
                esiti.append((nome, False, "MUTAZIONE NON APPLICATA"))
                continue
            (finto / "verifica" / "banco").unlink(missing_ok=True)
            codice, _ = esegui(finto)
            vista = (codice != 0)
            if atteso == "equivalente":
                esiti.append((nome, not vista,
                              "equivalente, invisibile come atteso" if not vista
                              else "ORA SI VEDE: rileggere il commento"))
            else:
                esiti.append((nome, vista,
                              "scoperta" if vista else "NON SCOPERTA"))

    print(f"\n{'=' * 72}")
    larghezza = max(len(n) for n, _, _ in esiti)
    for nome, ok, nota in esiti:
        print(f"  {'OK ' if ok else 'NO '} {nome:<{larghezza}}  {nota}")
    falliti = sum(1 for _, ok, _ in esiti if not ok)
    print(f"{'=' * 72}")
    if falliti:
        print(f"{falliti} controlli non superati: il confronto non misura tutto "
              f"quello che dovrebbe.")
    else:
        print("Il confronto scopre ogni errore che gli e' stato messo davanti.")
    return 1 if falliti else 0


if __name__ == "__main__":
    sys.exit(main())
