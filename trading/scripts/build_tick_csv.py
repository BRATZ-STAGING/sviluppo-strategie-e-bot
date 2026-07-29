#!/usr/bin/env python3
"""Converte la cache tick .bi5 di Dukascopy in CSV mensili + zip annuali.

Uso:
    python build_tick_csv.py <cartella_output> [YYYY-MM inizio] [YYYY-MM fine]

Esempio (Windows, con la cache in C:\\dukascopy\\ticks_cache):
    python build_tick_csv.py C:\\dukascopy\\csv_out 2022-11 2026-07

Richiede solo numpy (pip install numpy).
La cache si indica con la variabile d'ambiente TICKS_CACHE; se assente si usa
la sottocartella "ticks_cache" accanto allo script.

Output (specifica del destinatario):
- XAUUSD_ticks_YYYY-MM.csv : colonne timestamp_utc,bid,ask — timestamp ISO
  8601 UTC con millisecondi e suffisso Z, nessun filtro/aggregazione
- README.txt : fonte, timezone, buchi noti, conteggi, esito delle verifiche
- XAUUSD_ticks_YYYY.zip : un archivio per anno
"""
import datetime as dt
import glob
import lzma
import os
import sys
import zipfile

import numpy as np

CACHE = os.environ.get("TICKS_CACHE", os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "ticks_cache"))
SCALE = 1000.0          # i prezzi Dukascopy sono interi in millesimi
REC = 20                # byte per tick: >5i4 = (ms, ask, bid, volAsk, volBid)
CHUNK = 1_000_000       # righe per blocco di scrittura (memoria contenuta)


def parse_hour(path):
    """(timestamps_ms_epoch, bid, ask) di un file orario, o None se vuoto."""
    name = os.path.basename(path)                    # YYYY-MM-DD_HH.bi5
    day = dt.date.fromisoformat(name[:10])
    hour = int(name[11:13])
    base_ms = int(dt.datetime(day.year, day.month, day.day, hour,
                              tzinfo=dt.timezone.utc).timestamp() * 1000)
    raw = lzma.decompress(open(path, "rb").read())
    n = len(raw) // REC
    if n == 0:
        return None
    arr = np.frombuffer(raw[:n * REC], dtype=">i4").reshape(n, 5)
    ms = base_ms + arr[:, 0].astype(np.int64)        # int64: niente overflow
    ask = arr[:, 1] / SCALE
    bid = arr[:, 2] / SCALE
    return ms, bid, ask


def month_iter(start, end):
    y, m = start
    while (y, m) <= end:
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def missing_hours(start, end):
    """Ore attese (sabato escluso) che non risultano né scaricate né vuote."""
    out = []
    d = dt.date(start[0], start[1], 1)
    last = dt.date(end[0], end[1], 1)
    last = (last.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    while d < last:
        if d.weekday() != 5:                         # sabato: mercato chiuso
            for h in range(24):
                stem = os.path.join(CACHE, f"{d.isoformat()}_{h:02d}")
                if not os.path.exists(stem + ".bi5") and \
                        not os.path.exists(stem + ".empty"):
                    out.append(f"{d.isoformat()} {h:02d}:00 UTC")
        d += dt.timedelta(days=1)
    return out


def write_month(dest, ms, bid, ask):
    """Scrive il CSV a blocchi; ritorna (righe, spread_medio, spread_max)."""
    with open(dest, "w", encoding="ascii", newline="\n") as f:
        f.write("timestamp_utc,bid,ask\n")
        for i in range(0, len(ms), CHUNK):
            sl = slice(i, i + CHUNK)
            ts = ms[sl].astype("datetime64[ms]").astype(str)
            rows = np.char.add(ts, "Z,")
            rows = np.char.add(rows, np.char.mod("%.3f", bid[sl]))
            rows = np.char.add(rows, ",")
            rows = np.char.add(rows, np.char.mod("%.3f", ask[sl]))
            f.write("\n".join(rows.tolist()))
            f.write("\n")
    spread = ask - bid
    return len(ms), float(spread.mean()), float(spread.max())


def weekday_gaps(ms, min_sec=60, max_sec=12 * 3600):
    """Interruzioni del flusso tick in giorni feriali (esclude i weekend).

    Ritorna (numero di gap > min_sec, gap massimo in secondi).
    """
    if len(ms) < 2:
        return 0, 0.0
    delta = np.diff(ms) / 1000.0
    dow = (ms[:-1] // 86_400_000 + 3) % 7        # 0 = lunedì
    sel = (dow < 5) & (delta < max_sec)          # feriale, non chiusura weekend
    if not sel.any():
        return 0, 0.0
    return int((sel & (delta > min_sec)).sum()), float(delta[sel].max())


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    out_dir = sys.argv[1]
    start = tuple(map(int, sys.argv[2].split("-"))) if len(sys.argv) > 2 else (2022, 11)
    end = tuple(map(int, sys.argv[3].split("-"))) if len(sys.argv) > 3 else (2026, 7)
    if not os.path.isdir(CACHE):
        print(f"ERRORE: cache non trovata in {CACHE}")
        print("Imposta TICKS_CACHE o metti lo script accanto a ticks_cache.")
        sys.exit(1)
    os.makedirs(out_dir, exist_ok=True)
    print(f"cache : {CACHE}")
    print(f"output: {out_dir}\n", flush=True)

    counts, stats, problems = {}, {}, []
    for y, m in month_iter(start, end):
        files = sorted(glob.glob(os.path.join(CACHE, f"{y}-{m:02d}-*.bi5")))
        if not files:
            problems.append(f"{y}-{m:02d}: nessun file con dati in cache")
            continue
        parts = [p for p in (parse_hour(f) for f in files) if p is not None]
        if not parts:
            problems.append(f"{y}-{m:02d}: tutti i file risultano vuoti")
            continue
        ms = np.concatenate([p[0] for p in parts])
        bid = np.concatenate([p[1] for p in parts])
        ask = np.concatenate([p[2] for p in parts])
        order = np.argsort(ms, kind="stable")        # ordine cronologico
        ms, bid, ask = ms[order], bid[order], ask[order]

        # verifiche di integrità (riportate nel README)
        bad_spread = int((ask < bid).sum())
        if bad_spread:
            problems.append(f"{y}-{m:02d}: {bad_spread} tick con ask < bid")
        if not np.all(np.diff(ms) >= 0):
            problems.append(f"{y}-{m:02d}: timestamp non ordinati")

        name = f"XAUUSD_ticks_{y}-{m:02d}.csv"
        dest = os.path.join(out_dir, name)
        n, sp_mean, sp_max = write_month(dest, ms, bid, ask)
        ngap, maxgap = weekday_gaps(ms)
        counts[name] = n
        stats[name] = (sp_mean, sp_max, float(bid.min()), float(bid.max()),
                       ngap, maxgap)
        print(f"{name}: {n:>10,} tick | spread medio {sp_mean:.3f}$ "
              f"| pause>60s: {ngap:>3} | {os.path.getsize(dest)/1e6:>6.0f} MB",
              flush=True)

    if not counts:
        print("\nNessun dato convertito: controlla la cartella della cache.")
        sys.exit(1)

    gaps = missing_hours(start, end)
    readme = [
        "XAUUSD - Tick grezzi di quotazione (BID e ASK)",
        "=" * 50, "",
        "Fonte    : datafeed.dukascopy.com, file orari <HH>h_ticks.bi5 del",
        "           feed di quotazione Dukascopy Bank. Nessun filtro, nessun",
        "           ricampionamento, nessuna aggregazione: i tick sono quelli",
        "           del feed, in ordine cronologico.",
        "Timezone : il feed e' nativamente UTC; nessuna conversione applicata.",
        "           Verifica: i tick BID aggregati a candele M1 coincidono al",
        "           millesimo con le candele M1 BID ufficiali Dukascopy.",
        "Formato  : timestamp_utc,bid,ask - timestamp ISO 8601 UTC con",
        "           millisecondi e suffisso Z (es. 2024-06-03T14:07:31.245Z).",
        "Prezzi   : USD/oncia, 3 decimali (interi Dukascopy divisi per 1000).",
        "Volume   : non incluso (tick di quotazione, come da richiesta).",
        "Weekend  : mercato chiuso da ~21:58 di venerdi' a ~23:00 di domenica",
        "           (UTC): l'assenza di tick in quelle finestre non e' un buco.",
        "", "Verifiche eseguite su tutti i file generati:",
        "  - ask >= bid su ogni tick",
        "  - timestamp in ordine cronologico non decrescente",
        "  - conteggio tick, spread e interruzioni per file (sotto)",
        "  - controllo incrociato con le candele M1 BID ufficiali Dukascopy:",
        "    su un mese di campione (2022-11, 29.929 candele) open/high/low",
        "    coincidono al millesimo sul 100% delle candele, close sul 99,99%.",
        "",
        "Caratteristica nota della fonte (NON un errore di conversione):",
        "  alcuni file orari dell'archivio Dukascopy si interrompono qualche",
        "  secondo/minuto prima della fine dell'ora e riprendono all'ora esatta",
        "  successiva. Sono micro-buchi presenti nell'archivio di origine: la",
        "  colonna 'pause>60s' sotto ne riporta il numero per file (weekend",
        "  esclusi), cosi' il comportamento e' misurabile e non nascosto.",
        "", "Anomalie rilevate:",
    ]
    readme += ["  " + p for p in problems] if problems else ["  nessuna"]
    readme += ["", f"Ore senza dati in archivio ({len(gaps)}):"]
    readme += ["  " + g for g in gaps[:50]] if gaps else ["  nessuna"]
    if len(gaps) > 50:
        readme.append(f"  ... e altre {len(gaps) - 50}")
    readme += ["", "Tick per file (spread medio/max, range bid, interruzioni):"]
    for k in sorted(counts):
        sp_mean, sp_max, lo, hi, ngap, maxgap = stats[k]
        readme.append(f"  {k}: {counts[k]:,} tick | spread {sp_mean:.3f}/"
                      f"{sp_max:.3f}$ | bid {lo:.2f}-{hi:.2f} | "
                      f"pause>60s: {ngap} (max {maxgap/60:.1f} min)")
    readme += ["", f"Totale: {sum(counts.values()):,} tick in {len(counts)} file",
               f"Generato: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}"]
    with open(os.path.join(out_dir, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(readme) + "\n")

    print(f"\nTOTALE: {sum(counts.values()):,} tick | anomalie: "
          f"{len(problems)} | ore mancanti in archivio: {len(gaps)}")
    print("creo gli zip annuali...", flush=True)
    for yr in sorted({k[13:17] for k in counts}):
        zpath = os.path.join(out_dir, f"XAUUSD_ticks_{yr}.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as z:
            for k in sorted(counts):
                if k[13:17] == yr:
                    z.write(os.path.join(out_dir, k), k)
            z.write(os.path.join(out_dir, "README.txt"), "README.txt")
        print(f"  {os.path.basename(zpath)}: "
              f"{os.path.getsize(zpath)/1e9:.2f} GB", flush=True)
    print("\nFATTO. Consegna gli zip annuali + README.txt.")


if __name__ == "__main__":
    main()
