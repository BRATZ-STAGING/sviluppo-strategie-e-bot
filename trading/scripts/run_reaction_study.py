#!/usr/bin/env python3
"""Esegue lo studio di reazione dei livelli sui dati reali.

Uso: python3 run_reaction_study.py [cartella_dati] [anni...]
Output: classifica su stdout + docs/studies/reaction-ranking.md + CSV.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from framework.data import load_m1
from framework.reaction import StudyConfig, run_study

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "XAUUSD_M1")
    years = [int(y) for y in sys.argv[2:]] or None
    m1 = load_m1(data_dir, years=years)
    print(f"candele M1: {len(m1):,}  ({m1.index[0]} -> {m1.index[-1]})")
    cfg = StudyConfig()
    ranking, touches = run_study(m1, cfg)
    print(f"tocchi totali: {len(touches):,}\n")
    print(ranking.to_string(float_format=lambda x: f"{x:.3f}"))

    out_dir = os.path.join(ROOT, "docs", "studies")
    os.makedirs(out_dir, exist_ok=True)
    ranking.to_csv(os.path.join(out_dir, "reaction-ranking.csv"))
    with open(os.path.join(out_dir, "reaction-ranking.md"), "w") as f:
        f.write("# Studio di reazione dei livelli — XAUUSD M1\n\n")
        f.write(f"- Periodo: {m1.index[0]} → {m1.index[-1]}\n")
        f.write(f"- Candele: {len(m1):,} — Tocchi analizzati: {len(touches):,}\n")
        f.write(f"- Config: finestra {cfg.window_min}', target {cfg.bounce_target}$, "
                f"stop {cfg.stop_penetration}$, cooldown {cfg.cooldown_min}', "
                f"min {cfg.min_touches} tocchi\n\n")
        f.write("Successo = rimbalzo ≥ target prima che la penetrazione superi lo stop.\n\n")
        f.write(ranking.to_markdown(floatfmt=".3f"))
        f.write("\n")
    print(f"\nsalvato in {out_dir}/reaction-ranking.{{md,csv}}")


if __name__ == "__main__":
    main()
