"""Mappa "orologio" di XAUUSD: struttura oraria e settimanale, nessuna strategia.

Che cosa misura, separatamente su 2009-2019 (ricerca) e 2020-2026 (verifica):

  * escursione mediana al minuto (in dollari e in punti base, perche' l'oro e'
    passato da ~900$ a ~3500$ e i dollari non sono confrontabili fra periodi);
  * rendimento medio dell'ora / della giornata, con t di Student calcolato
    sulle somme giornaliere (osservazioni indipendenti, non sui minuti);
  * quota di minuti in salita (e di minuti piatti);
  * rapporto di varianza VR(k) = Var(r_k) / (k * Var(r_1)) per k = 5, 15, 60:
    sopra 1 il moto e' persistente (l'ora "va"), sotto 1 torna indietro. E'
    QUESTA la misura di direzionalita', non l'efficienza |somma|/somma|.| che
    e' invariante all'ordine dei minuti (la riporto lo stesso come indice di
    concentrazione, ma non dice nulla sul fatto che il moto sia direzionale);
  * movimento disponibile: mediana del |movimento| nei 60 minuti successivi,
    in dollari e in punti base, ora per ora;
  * ora in cui si forma il massimo e il minimo della giornata;
  * persistenza: autocorrelazione del SEGNO del rendimento a 5, 15, 60 minuti e
    guadagno lordo in punti base di chi segue il segno precedente
    (sign(r_passato) * r_futuro), che e' la forma tradeable della stessa cosa;
  * profilo minuto per minuto delle aperture di sessione (Londra 07-08 UTC,
    New York 13-14 UTC) e della finestra del rollover giornaliero;
  * confronto fra orologio UTC e orologio locale di New York, per capire se le
    ore "calde" seguono l'ora legale americana (in tal caso l'ora UTC le sfoca).

CAUSALITA': l'istante di ogni misura e' la CHIUSURA del minuto t. Il passato usa
close(t) - close(t-k), il futuro close(t+k) - close(t); entrambi validi solo se i
minuti sono davvero contigui (nessun salto di weekend o di rollover dentro la
finestra). Nessuna media usa dati successivi all'istante a cui e' attribuita.

Il dettaglio grezzo finisce in /workspace/dati_grezzi/mappa_orologio/, in chat
solo tabelle compatte.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

REPO = "/workspace/sviluppo-strategie-e-bot"
sys.path.insert(0, os.path.join(REPO, "trading"))

from framework.data import load_m1  # noqa: E402

USCITA = "/workspace/dati_grezzi/mappa_orologio"
PERIODI = {"2009-2019": (2009, 2019), "2020-2026": (2020, 2026)}
ORIZZONTI = (5, 15, 60)
GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
SPREAD_USD = 0.30  # andata e ritorno

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 60)
pd.set_option("display.float_format", lambda v: f"{v:9.3f}")


# ---------------------------------------------------------------- preparazione
def prepara(m1: pd.DataFrame) -> pd.DataFrame:
    """Tabella al minuto con rendimenti, escursione e finestre passato/futuro.

    Tutto in punti base sul prezzo (1 bp = 0,01%): e' l'unica unita' in cui il
    2009 e il 2026 si possono confrontare.
    """
    df = m1.reset_index().rename(columns={"index": "timestamp"})
    ts = df["timestamp"]
    c = df["close"].to_numpy()

    # rendimento del minuto: valido solo se il minuto precedente e' contiguo
    dt_prev = ts.diff().dt.total_seconds().to_numpy() / 60.0
    prev_ok = dt_prev == 1
    ret_bp = np.full(len(df), np.nan)
    ret_bp[1:] = 1e4 * (c[1:] - c[:-1]) / c[:-1]
    ret_bp[~prev_ok] = np.nan
    df["ret_bp"] = ret_bp

    df["rng_usd"] = df["high"] - df["low"]
    df["rng_bp"] = 1e4 * df["rng_usd"] / df["close"]

    df["anno"] = ts.dt.year
    df["data"] = ts.dt.date
    df["ora"] = ts.dt.hour
    df["minuto"] = ts.dt.minute
    df["dow"] = ts.dt.dayofweek
    df["mod"] = df["ora"] * 60 + df["minuto"]  # minuto del giorno UTC

    # orologio locale di New York (per separare l'ora legale americana)
    ny = ts.dt.tz_convert("America/New_York")
    df["mod_ny"] = ny.dt.hour * 60 + ny.dt.minute

    # finestre passato/futuro: contiguita' verificata sui timestamp, non sulle righe
    # minuti trascorsi dall'inizio: i Parquet sono datetime64[ms], quindi mai
    # convertire "a occhio" in nanosecondi (le finestre risulterebbero tutte
    # non contigue e la persistenza uscirebbe vuota)
    tsv = (ts - ts.iloc[0]).dt.total_seconds().to_numpy() / 60.0
    for k in ORIZZONTI:
        rp = np.full(len(df), np.nan)
        rp[k:] = 1e4 * (c[k:] - c[:-k]) / c[:-k]
        rp[k:][(tsv[k:] - tsv[:-k]) != k] = np.nan
        rp[:k] = np.nan
        df[f"pas{k}"] = rp
        df[f"fut{k}"] = np.concatenate([rp[k:], np.full(k, np.nan)])
    return df


def t_stat(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 30:
        return np.nan
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def agg_persistenza(g: pd.DataFrame) -> pd.Series:
    """Autocorrelazione del segno e guadagno lordo del 'seguire il segno'."""
    out = {}
    for k in ORIZZONTI:
        p, f = g[f"pas{k}"], g[f"fut{k}"]
        ok = p.notna() & f.notna() & (p != 0) & (f != 0)
        if ok.sum() < 200:
            out[f"acorr{k}"] = np.nan
            out[f"cont{k}"] = np.nan
            out[f"t_cont{k}"] = np.nan
            continue
        sp, sf = np.sign(p[ok]), np.sign(f[ok])
        out[f"acorr{k}"] = float(np.corrcoef(sp, sf)[0, 1])
        cont = sp * f[ok]
        out[f"cont{k}"] = float(cont.mean())
        out[f"t_cont{k}"] = t_stat(cont)
    return pd.Series(out)


# ------------------------------------------------------------------ aggregatori
def per_ora(df: pd.DataFrame) -> pd.DataFrame:
    """Una riga per ora UTC: volatilita', deriva, efficienza."""
    # somme orarie (una osservazione per giorno-ora) per t di Student ed efficienza
    gh = df.dropna(subset=["ret_bp"]).groupby(["data", "ora"])
    ore = pd.DataFrame({
        "somma": gh["ret_bp"].sum(),
        "assoluti": gh["ret_bp"].apply(lambda s: s.abs().sum()),
        "n": gh["ret_bp"].size(),
    }).reset_index()
    ore = ore[ore["n"] >= 50]  # ore monche (rollover, festivi) fuori
    ore["eff"] = np.where(ore["assoluti"] > 0, ore["somma"].abs() / ore["assoluti"], np.nan)

    a = ore.groupby("ora").agg(
        giorni=("somma", "size"),
        ret_ora_bp=("somma", "mean"),
        t=("somma", t_stat),
        eff_med=("eff", "median"),
    )
    b = df.groupby("ora").agg(
        n_min=("rng_bp", "size"),
        rng_bp=("rng_bp", "median"),
        rng_usd=("rng_usd", "median"),
    )
    su = df.groupby("ora")["ret_bp"].apply(lambda s: 100 * (s > 0).sum() / s.notna().sum())
    piatti = df.groupby("ora")["ret_bp"].apply(lambda s: 100 * (s == 0).sum() / s.notna().sum())
    pers = df.groupby("ora").apply(agg_persistenza, include_groups=False)
    out = b.join(a).join(su.rename("su_pct")).join(piatti.rename("piatti_pct")).join(pers)
    return out


def per_giorno(df: pd.DataFrame) -> pd.DataFrame:
    """Una riga per giorno della settimana."""
    gd = df.dropna(subset=["ret_bp"]).groupby(["data"])
    gi = pd.DataFrame({
        "somma": gd["ret_bp"].sum(),
        "n": gd["ret_bp"].size(),
        "dow": gd["dow"].first(),
    }).reset_index()
    a = gi.groupby("dow").agg(
        giorni=("somma", "size"),
        min_medi=("n", "mean"),
        ret_gg_bp=("somma", "mean"),
        t=("somma", t_stat),
    )
    b = df.groupby("dow").agg(rng_bp=("rng_bp", "median"), rng_usd=("rng_usd", "median"))
    su = df.groupby("dow")["ret_bp"].apply(lambda s: 100 * (s > 0).sum() / s.notna().sum())
    pers = df.groupby("dow").apply(agg_persistenza, include_groups=False)
    out = b.join(a).join(su.rename("su_pct")).join(pers)
    out.index = [GIORNI[i] for i in out.index]
    return out


def profilo_minuti(df: pd.DataFrame, colonna: str, da: int, a: int, passo: int) -> pd.DataFrame:
    """Profilo a blocchi di `passo` minuti nella finestra [da, a) dell'orologio."""
    sel = df[(df[colonna] >= da) & (df[colonna] < a)].copy()
    sel["blocco"] = (sel[colonna] // passo) * passo
    g = sel.groupby("blocco")
    out = pd.DataFrame({
        "n_min": g["rng_bp"].size(),
        "rng_bp": g["rng_bp"].median(),
        "ret_bp": g["ret_bp"].mean() * passo,   # rendimento medio del blocco
        "su_pct": g["ret_bp"].apply(lambda s: 100 * (s > 0).sum() / max(s.notna().sum(), 1)),
    })
    out.index = [f"{b // 60:02d}:{b % 60:02d}" for b in out.index]
    return out


def copertura_rollover(df: pd.DataFrame) -> pd.DataFrame:
    """Quanti minuti esistono davvero per ogni minuto del giorno, ore 20-23."""
    giorni_feriali = df[df["dow"] < 5]
    n_gg = giorni_feriali["data"].nunique()
    sel = giorni_feriali[(giorni_feriali["ora"] >= 20) & (giorni_feriali["ora"] <= 23)]
    q = sel.groupby(["ora", "minuto"]).size().groupby("ora").agg(["min", "max", "mean"])
    q = 100 * q / n_gg
    q.columns = ["min_pct", "max_pct", "media_pct"]
    q["rng_bp_mediano"] = sel.groupby("ora")["rng_bp"].median()
    return q


# ------------------------------------------------------------------------ main
def main() -> None:
    os.makedirs(USCITA, exist_ok=True)
    m1 = load_m1(os.path.join(REPO, "data", "XAUUSD_M1"), years=list(range(2009, 2027)))

    tab_ora, tab_dow, tab_ses, tab_roll = {}, {}, {}, {}
    prof = {}
    riepilogo = []

    for nome, (y0, y1) in PERIODI.items():
        sub = m1[(m1.index.year >= y0) & (m1.index.year <= y1)]
        df = prepara(sub)
        df.to_parquet(f"{USCITA}/minuti_{nome}.parquet", index=False)

        tab_ora[nome] = per_ora(df)
        tab_dow[nome] = per_giorno(df)
        prof[nome] = {
            "londra": profilo_minuti(df, "mod", 6 * 60 + 30, 8 * 60 + 30, 10),
            "newyork": profilo_minuti(df, "mod", 12 * 60, 15 * 60, 15),
            "ny_locale": profilo_minuti(df, "mod_ny", 8 * 60, 11 * 60, 15),
        }
        tab_roll[nome] = copertura_rollover(df)

        # ora UTC x giorno: rendimento medio orario, per la mappa a scacchiera
        gh = df.dropna(subset=["ret_bp"]).groupby(["data", "ora"])
        ore = pd.DataFrame({"somma": gh["ret_bp"].sum(), "n": gh["ret_bp"].size(),
                            "dow": gh["dow"].first()}).reset_index()
        ore = ore[ore["n"] >= 50]
        tab_ses[nome] = ore.pivot_table(index="ora", columns="dow", values="somma", aggfunc="mean")
        tab_ses[nome].columns = [GIORNI[c] for c in tab_ses[nome].columns]

        prezzo = float(df["close"].median())
        riepilogo.append({
            "periodo": nome,
            "minuti": len(df),
            "giorni": df["data"].nunique(),
            "prezzo_mediano": prezzo,
            "rng_min_mediano_usd": float(df["rng_usd"].median()),
            "rng_min_mediano_bp": float(df["rng_bp"].median()),
            "spread_bp": 1e4 * SPREAD_USD / prezzo,
        })

    riep = pd.DataFrame(riepilogo).set_index("periodo")
    print("\n=== CONTESTO (lo spread di 0,30$ vale meno bp oggi che nel 2009) ===")
    print(riep)

    for nome in PERIODI:
        print(f"\n=== ORE UTC — {nome} — volatilita' e deriva ===")
        cols = ["n_min", "rng_usd", "rng_bp", "ret_ora_bp", "t", "su_pct", "piatti_pct", "eff_med", "giorni"]
        print(tab_ora[nome][cols])

    for nome in PERIODI:
        print(f"\n=== ORE UTC — {nome} — persistenza (acorr = segno vs segno; cont = bp lordi seguendo il segno) ===")
        cols = ["acorr5", "cont5", "t_cont5", "acorr15", "cont15", "t_cont15", "acorr60", "cont60", "t_cont60"]
        print(tab_ora[nome][cols])

    for nome in PERIODI:
        print(f"\n=== GIORNI DELLA SETTIMANA — {nome} ===")
        cols = ["giorni", "min_medi", "rng_usd", "rng_bp", "ret_gg_bp", "t", "su_pct",
                "acorr5", "cont5", "acorr15", "cont15", "acorr60", "cont60"]
        print(tab_dow[nome][cols])

    for nome in PERIODI:
        print(f"\n=== SCACCHIERA ora UTC x giorno — rendimento medio dell'ora in bp — {nome} ===")
        print(tab_ses[nome])

    for nome in PERIODI:
        print(f"\n=== APERTURA LONDRA (blocchi di 10 min, orologio UTC) — {nome} ===")
        print(prof[nome]["londra"])

    for nome in PERIODI:
        print(f"\n=== POMERIGGIO USA (blocchi di 15 min, orologio UTC) — {nome} ===")
        print(prof[nome]["newyork"])

    for nome in PERIODI:
        print(f"\n=== POMERIGGIO USA (blocchi di 15 min, orologio LOCALE di New York) — {nome} ===")
        print(prof[nome]["ny_locale"])

    print("\n=== NITIDEZZA: escursione mediana del blocco piu' agitato, UTC vs ora di New York ===")
    nit = []
    for nome in PERIODI:
        u, l = prof[nome]["newyork"], prof[nome]["ny_locale"]
        base_u = u["rng_bp"].median()
        base_l = l["rng_bp"].median()
        nit.append({
            "periodo": nome,
            "picco_utc_bp": u["rng_bp"].max(), "blocco_utc": u["rng_bp"].idxmax(),
            "picco_utc_su_mediana": u["rng_bp"].max() / base_u,
            "picco_ny_bp": l["rng_bp"].max(), "blocco_ny": l["rng_bp"].idxmax(),
            "picco_ny_su_mediana": l["rng_bp"].max() / base_l,
        })
    print(pd.DataFrame(nit).set_index("periodo"))

    for nome in PERIODI:
        print(f"\n=== ROLLOVER: quota di giorni feriali in cui il minuto esiste (ore 20-23 UTC) — {nome} ===")
        print(tab_roll[nome])

    # stabilita' interna: mezzo periodo contro mezzo periodo, sulle sole ore
    print("\n=== STABILITA': rendimento medio dell'ora (bp) per sotto-periodo ===")
    pezzi = {"2009-2014": (2009, 2014), "2015-2019": (2015, 2019),
             "2020-2022": (2020, 2022), "2023-2026": (2023, 2026)}
    colonne = {}
    for nome, (y0, y1) in pezzi.items():
        sub = m1[(m1.index.year >= y0) & (m1.index.year <= y1)]
        d = prepara(sub)
        gh = d.dropna(subset=["ret_bp"]).groupby(["data", "ora"])
        ore = pd.DataFrame({"somma": gh["ret_bp"].sum(), "n": gh["ret_bp"].size()}).reset_index()
        ore = ore[ore["n"] >= 50]
        colonne[nome] = ore.groupby("ora")["somma"].mean()
    stab = pd.DataFrame(colonne)
    print(stab)

    print("\n=== STABILITA': cont15 (bp lordi seguendo il segno a 15 min) per sotto-periodo ===")
    colonne = {}
    for nome, (y0, y1) in pezzi.items():
        sub = m1[(m1.index.year >= y0) & (m1.index.year <= y1)]
        d = prepara(sub)
        colonne[nome] = d.groupby("ora").apply(agg_persistenza, include_groups=False)["cont15"]
    print(pd.DataFrame(colonne))

    for nome in PERIODI:
        tab_ora[nome].to_parquet(f"{USCITA}/ore_{nome}.parquet")
        tab_dow[nome].to_parquet(f"{USCITA}/giorni_{nome}.parquet")
        tab_ses[nome].to_parquet(f"{USCITA}/scacchiera_{nome}.parquet")
    print(f"\n[dettaglio in {USCITA}]")


if __name__ == "__main__":
    main()
