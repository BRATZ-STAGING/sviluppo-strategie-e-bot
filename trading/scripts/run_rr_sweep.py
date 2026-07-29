#!/usr/bin/env python3
"""Sweep dello studio RR intraday: stop piccoli, target rr*stop, uscita EOD.

Uso: python3 run_rr_sweep.py [rr] [anni...]
Output: docs/studies/rr-sweep.md + rr-touches-<stop>.parquet in scratch.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from framework.data import load_m1
from framework.rr_study import RRConfig, aggregate, run_rr_study

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STOPS = [0.75, 1.0, 1.5, 2.0, 3.0]
MIN_N = 300


def main():
    rr = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    years = [int(y) for y in sys.argv[2:]] or None
    m1 = load_m1(os.path.join(ROOT, "data", "XAUUSD_M1"), years=years)
    print(f"candele: {len(m1):,}  rr=1:{rr:g}", flush=True)

    sections = []
    for stop in STOPS:
        cfg = RRConfig(stop=stop, rr=rr)
        df = run_rr_study(m1, cfg)
        be = (stop + cfg.spread) / (stop * (1 + rr))
        by_kind = aggregate(df, ["kind"])
        print(f"\n=== stop {stop}$ target {rr*stop:g}$ | tocchi {len(df):,} | "
              f"break-even netto ~{be:.1%} ===", flush=True)
        print(by_kind.to_string(float_format=lambda x: f"{x:.3f}"), flush=True)
        sections.append((stop, df, by_kind))

    out_dir = os.path.join(ROOT, "docs", "studies")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "rr-sweep.md"), "w") as f:
        f.write(f"# Sweep RR 1:{rr:g} intraday — XAUUSD\n\n")
        f.write(f"Entrata limit sul livello (primo tocco del giorno, entro le 19 UTC),\n"
                f"stop fisso oltre il livello, target {rr:g}R, uscita forzata alle 21 UTC.\n"
                f"`exp_r_net` = R medio per trade al netto dello spread (0.30$).\n\n")
        for stop, df, by_kind in sections:
            f.write(f"\n## Stop {stop}$ — target {rr*stop:g}$ ({len(df):,} tocchi)\n\n")
            f.write(by_kind.to_markdown(floatfmt=".3f"))
            f.write("\n\n### Per sessione (solo combinazioni con n ≥ {})\n\n".format(MIN_N))
            by_ks = aggregate(df, ["kind", "session"])
            f.write(by_ks[by_ks.n >= MIN_N].to_markdown(floatfmt=".3f"))
            f.write("\n\n### Per confluenza\n\n")
            f.write(aggregate(df, ["kind", "confluence"]).query(f"n >= {MIN_N}")
                    .to_markdown(floatfmt=".3f"))
            f.write("\n")
    # dettaglio tocchi per analisi successive
    scratch = os.environ.get("RR_TOUCHES_DIR")
    if scratch:
        for stop, df, _ in sections:
            df.to_parquet(os.path.join(scratch, f"rr-touches-{stop}.parquet"))
    print(f"\nsalvato in {out_dir}/rr-sweep.md")


if __name__ == "__main__":
    main()
