"""Mappa "orologio" di XAUUSD: struttura oraria e settimanale, nessuna strategia.

Che cosa misura, separatamente su 2009-2019 (ricerca) e 2020-2026 (verifica):

  * escursione mediana al minuto (in dollari e in punti base, perche' l'oro e'
    passato da ~900$ a ~3500$ e i dollari non sono confrontabili fra periodi);
  * rendimento medio dell'ora / della giornata, con t di Student calcolato
    sulle somme giornaliere (osservazioni indipendenti, non sui minuti);
  * quota di minuti in salita (e di minuti piatti);
  * rapporto di varianza VR(k) = Var(somma di k rendimenti) / k, calcolato sui
    rendimenti STANDARDIZZATI: sopra 1 il moto e' persistente (l'ora "va"),
    sotto 1 torna indietro. Due trappole gia' cadute e corrette qui:
      - senza standardizzare, una finestra di 60 minuti che parte alle 11:00
        finisce dentro le 12-13 (tre volte piu' agitate) e il VR risulta > 1
        per la sola salita della volatilita', non per direzionalita'. I
        rendimenti sono quindi divisi per la loro deviazione standard per
        (anno, blocco di 10 minuti del giorno), che toglie sia la gobba
        intraday sia il fatto che l'oro nel 2026 si muove 4 volte il 2009;
      - l'efficienza |somma| / somma|.| non serve a niente come misura di
        direzionalita': e' INVARIANTE all'ordine dei minuti. Non e' riportata.
    N.B. la standardizzazione usa tutto il campione: e' una statistica
    descrittiva, nessuna regola operativa puo' appoggiarcisi;
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
    lon = ts.dt.tz_convert("Europe/London")
    df["mod_lon"] = lon.dt.hour * 60 + lon.dt.minute

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
    # stesso movimento a 60 minuti, ma in dollari (per ragionare su stop e target)
    df["fut60_usd"] = df["fut60"] * df["close"] / 1e4

    # rendimenti standardizzati per (anno, blocco di 10 minuti del giorno):
    # senza questo il rapporto di varianza misura la gobba della volatilita'
    df["bin10"] = df["mod"] // 10
    sigma = df.groupby(["anno", "bin10"])["ret_bp"].transform("std")
    df["z"] = df["ret_bp"] / sigma
    z = df["z"].to_numpy()
    n = len(df)
    zc = np.concatenate([[0.0], np.cumsum(np.nan_to_num(z))])  # zc[m] = somma di z[0..m-1]
    for k in ORIZZONTI:
        s = np.full(n, np.nan)
        s[:n - k] = zc[k + 1:n + 1] - zc[1:n - k + 1]  # somma di z su (i, i+k]
        s[:-k][(tsv[k:] - tsv[:-k]) != k] = np.nan
        df[f"zfut{k}"] = s
    return df


def t_stat(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 30:
        return np.nan
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def agg_persistenza(g: pd.DataFrame) -> pd.Series:
    """Autocorrelazione del segno, guadagno lordo del 'seguire il segno', VR(k).

    acorr e cont sono calcolati su finestre NON sovrapposte (un'osservazione
    ogni k minuti): con le finestre sovrapposte il t di Student risulta gonfiato
    di circa sqrt(k) e una differenza di rumore sembra una scoperta.
    """
    out = {}
    for k in ORIZZONTI:
        sep = g[g["minuto"] % k == 0]  # finestre affiancate, non sovrapposte
        p, f = sep[f"pas{k}"], sep[f"fut{k}"]
        ok = p.notna() & f.notna() & (p != 0) & (f != 0)
        if ok.sum() < 200:
            out[f"acorr{k}"] = np.nan
            out[f"cont{k}"] = np.nan
            out[f"t_cont{k}"] = np.nan
        else:
            sp, sf = np.sign(p[ok]), np.sign(f[ok])
            out[f"acorr{k}"] = float(np.corrcoef(sp, sf)[0, 1])
            cont = sp * f[ok]
            out[f"cont{k}"] = float(cont.mean())
            out[f"t_cont{k}"] = t_stat(cont)
        # rapporto di varianza sui rendimenti standardizzati: 1 = passeggiata,
        # >1 il moto prosegue, <1 rientra
        zk = g[f"zfut{k}"].dropna()
        out[f"vr{k}"] = float(zk.var() / k) if len(zk) > 500 else np.nan
    # movimento disponibile nell'ora successiva
    f60 = g["fut60"].dropna()
    out["mov60_bp"] = float(f60.abs().median()) if len(f60) > 500 else np.nan
    f60u = g["fut60_usd"].dropna()
    out["mov60_usd"] = float(f60u.abs().median()) if len(f60u) > 500 else np.nan
    return pd.Series(out)


def ora_degli_estremi(df: pd.DataFrame) -> pd.DataFrame:
    """In quale ora UTC si formano il massimo e il minimo della giornata.

    Solo giornate feriali "piene" (>= 1000 minuti): lo spezzone della domenica e
    i mezzi giorni festivi falserebbero il conteggio. E' una statistica ex-post,
    descrittiva: dice DOVE stanno gli estremi, non come prenderli.
    """
    d = df[(df["dow"] < 5)]
    pieni = d.groupby("data")["close"].size()
    pieni = pieni[pieni >= 1000].index
    d = d[d["data"].isin(pieni)]
    imax = d.loc[d.groupby("data")["high"].idxmax(), ["data", "ora"]]
    imin = d.loc[d.groupby("data")["low"].idxmin(), ["data", "ora"]]
    n = len(pieni)
    out = pd.DataFrame({
        "max_pct": 100 * imax["ora"].value_counts().sort_index() / n,
        "min_pct": 100 * imin["ora"].value_counts().sort_index() / n,
    }).fillna(0.0)
    out["estremi_pct"] = out["max_pct"] + out["min_pct"]
    out.index.name = "ora"
    return out


# ------------------------------------------------------------------ aggregatori
def per_ora(df: pd.DataFrame) -> pd.DataFrame:
    """Una riga per ora UTC: volatilita', deriva, ampiezza."""
    # somme orarie: una osservazione per giorno-ora, cosi' il t di Student non
    # e' calcolato su minuti che si sovrappongono fra loro
    gh = df.dropna(subset=["ret_bp"]).groupby(["data", "ora"])
    ore = pd.DataFrame({"somma": gh["ret_bp"].sum(), "n": gh["ret_bp"].size()}).reset_index()
    ore = ore[ore["n"] >= 50]  # ore monche (rollover, festivi) fuori

    a = ore.groupby("ora").agg(
        giorni=("somma", "size"),
        ret_ora_bp=("somma", "mean"),
        t=("somma", t_stat),
    )
    # escursione dell'ora intera (massimo-minimo): e' la scala naturale di uno
    # stop, molto piu' del range al minuto
    ampiezza = df.groupby(["data", "ora"]).agg(hi=("high", "max"), lo=("low", "min"),
                                               n=("close", "size")).reset_index()
    ampiezza = ampiezza[ampiezza["n"] >= 50]
    ampiezza["amp"] = ampiezza["hi"] - ampiezza["lo"]
    a = a.join(ampiezza.groupby("ora")["amp"].median().rename("amp_ora_usd"))
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
    gg = df.groupby("data").agg(hi=("high", "max"), lo=("low", "min"), dow=("dow", "first"),
                                n=("close", "size"))
    gg = gg[gg["n"] >= 1000]
    b = b.join((gg["hi"] - gg["lo"]).groupby(gg["dow"]).median().rename("amp_gg_usd"))
    su = df.groupby("dow")["ret_bp"].apply(lambda s: 100 * (s > 0).sum() / s.notna().sum())
    pers = df.groupby("dow").apply(agg_persistenza, include_groups=False)
    out = b.join(a).join(su.rename("su_pct")).join(pers)
    out.index = [GIORNI[i] for i in out.index]
    return out


def concordanza(tabelle: dict, valore: str, tstat: str | None, soglia: float = 1.8) -> pd.DataFrame:
    """Righe in cui i due periodi dicono la STESSA cosa, con abbastanza forza.

    Con 24 ore per 3 orizzonti per 2 periodi si fanno 144 confronti: qualche |t|
    sopra 2 esce per forza dal caso. Tengo solo cio' che ha lo stesso segno nei
    due periodi e almeno un |t| oltre la soglia, l'altro almeno 1.
    """
    a, b = list(tabelle.values())
    na, nb = list(tabelle.keys())
    d = pd.DataFrame({f"{valore}_{na}": a[valore], f"{valore}_{nb}": b[valore]})
    if tstat:
        d[f"t_{na}"] = a[tstat]
        d[f"t_{nb}"] = b[tstat]
        stesso = np.sign(d.iloc[:, 0]) == np.sign(d.iloc[:, 1])
        forte = ((d[f"t_{na}"].abs() >= soglia) & (d[f"t_{nb}"].abs() >= 1.0)) | \
                ((d[f"t_{nb}"].abs() >= soglia) & (d[f"t_{na}"].abs() >= 1.0))
        return d[stesso & forte]
    return d


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


def deriva_riapertura(df: pd.DataFrame, settimanale: bool, scarto: int = 0) -> pd.DataFrame:
    """Deriva nei minuti dopo la riapertura, allineata alla riapertura stessa.

    La pausa giornaliera NON e' a un'ora UTC fissa (21-22 d'estate, 22-23
    d'inverno), quindi guardarla sull'orologio UTC la spalma su due ore. Qui
    l'origine e' il primo minuto scambiato dopo la pausa.

    Causalita': il prezzo di riferimento e' la CHIUSURA del primo minuto dopo la
    riapertura, non la sua apertura: quel primo minuto contiene il salto, e
    prenderlo all'apertura significherebbe incassare un salto gia' avvenuto.
    """
    ts = df["timestamp"]
    tsv = (ts - ts.iloc[0]).dt.total_seconds().to_numpy() / 60.0
    salto = np.diff(tsv, prepend=np.nan)
    if settimanale:
        idx = np.where(salto >= 300)[0]
    else:
        idx = np.where((salto > 5) & (salto < 300))[0]
    c = df["close"].to_numpy()
    n = len(df)

    def riga(t0: np.ndarray, da: int, a: int) -> pd.Series:
        """Rendimento fra t0+da e t0+a, solo dove entrambi i minuti esistono."""
        out = np.full(len(t0), np.nan)
        for off, dest in ((da, "b"), (a, "e")):
            pos = np.searchsorted(tsv, t0 + off)
            pos = np.minimum(pos, n - 1)
            valido = tsv[pos] == t0 + off
            if dest == "b":
                pb, vb = pos, valido
            else:
                pe, ve = pos, valido
        ok = vb & ve
        out[ok] = 1e4 * (c[pe[ok]] - c[pb[ok]]) / c[pb[ok]]
        return pd.Series(out).dropna()

    # `scarto` sposta l'ancora di N minuti: e' il placebo (stessa regola su un
    # istante finto). Se il finto va come il vero, non e' la riapertura a lavorare.
    t0 = tsv[idx] + scarto
    righe = []
    for da, a in [(0, 5), (5, 15), (15, 30), (30, 60), (60, 120), (5, 120), (0, 120)]:
        s = riga(t0, da, a)
        righe.append({"minuti": f"{da}->{a}", "n": len(s), "ret_bp": s.mean(),
                      "t": t_stat(s), "su_pct": 100 * (s > 0).mean()})
    return pd.DataFrame(righe).set_index("minuti")


def profilo_giornata(df: pd.DataFrame, colonna: str, passo: int = 5) -> pd.DataFrame:
    """Profilo dell'escursione su TUTTA la giornata, per un dato orologio."""
    d = df.copy()
    d["blocco"] = (d[colonna] // passo) * passo
    g = d.groupby("blocco")["rng_bp"]
    out = pd.DataFrame({"rng_bp": g.median(), "n": g.size()})
    out = out[out["n"] > 0.5 * out["n"].max()]  # niente blocchi nella pausa
    out.index = [f"{int(b) // 60:02d}:{int(b) % 60:02d}" for b in out.index]
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

    tab_ora, tab_dow, tab_ses, tab_roll, tab_estremi = {}, {}, {}, {}, {}
    tab_riap, tab_riap_set, prof_gg, tab_placebo = {}, {}, {}, {}
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
            "riapertura": profilo_minuti(df, "mod", 22 * 60, 24 * 60, 15),
            "londra_locale": profilo_minuti(df, "mod_lon", 6 * 60 + 30, 8 * 60 + 30, 10),
        }
        tab_roll[nome] = copertura_rollover(df)
        tab_estremi[nome] = ora_degli_estremi(df)
        tab_riap[nome] = deriva_riapertura(df, settimanale=False)
        tab_riap_set[nome] = deriva_riapertura(df, settimanale=True)
        # -6h e +3h: ancore finte scelte in modo che la finestra di 120 minuti
        # NON finisca dentro la pausa (a -3h ci finisce e il campione crolla)
        tab_placebo[nome] = {s: deriva_riapertura(df, settimanale=False, scarto=s)
                             for s in (0, -360, 180)}
        prof_gg[nome] = {"utc": profilo_giornata(df, "mod"),
                         "ny": profilo_giornata(df, "mod_ny"),
                         "lon": profilo_giornata(df, "mod_lon")}

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
        cols = ["n_min", "rng_usd", "rng_bp", "ret_ora_bp", "t", "su_pct", "piatti_pct", "giorni"]
        print(tab_ora[nome][cols])

    for nome in PERIODI:
        print(f"\n=== ORE UTC — {nome} — persistenza (acorr = segno vs segno; cont = bp lordi seguendo il segno) ===")
        cols = ["acorr5", "cont5", "t_cont5", "acorr15", "cont15", "t_cont15", "acorr60", "cont60", "t_cont60"]
        print(tab_ora[nome][cols])

    for nome in PERIODI:
        print(f"\n=== ORE UTC — {nome} — direzionalita' (VR>1 va dritto, VR<1 torna) e movimento disponibile a 60' ===")
        print(tab_ora[nome][["vr5", "vr15", "vr60", "mov60_bp", "mov60_usd", "amp_ora_usd"]])

    print("\n=== CIO' CHE REGGE SU ENTRAMBI I PERIODI (stesso segno e forza sufficiente) ===")
    for val, ts in [("ret_ora_bp", "t"), ("cont5", "t_cont5"), ("cont15", "t_cont15"),
                    ("cont60", "t_cont60")]:
        c = concordanza(tab_ora, val, ts)
        print(f"\n-- {val} --")
        print(c if len(c) else "   nessuna ora regge su entrambi i periodi")

    for nome in PERIODI:
        print(f"\n=== ORA UTC IN CUI SI FORMANO GLI ESTREMI DELLA GIORNATA (%) — {nome} ===")
        print(tab_estremi[nome].T)

    for nome in PERIODI:
        print(f"\n=== GIORNI DELLA SETTIMANA — {nome} ===")
        cols = ["giorni", "min_medi", "rng_usd", "amp_gg_usd", "ret_gg_bp", "t", "su_pct",
                "acorr5", "cont5", "acorr15", "cont15", "acorr60", "cont60"]
        print(tab_dow[nome][cols])

    for nome in PERIODI:
        print(f"\n=== SCACCHIERA ora UTC x giorno — rendimento medio dell'ora in bp — {nome} ===")
        print(tab_ses[nome])

    for nome in PERIODI:
        print(f"\n=== APERTURA LONDRA (blocchi di 10 min, orologio UTC) — {nome} ===")
        print(prof[nome]["londra"])

    for nome in PERIODI:
        print(f"\n=== APERTURA LONDRA (blocchi di 10 min, orologio LOCALE di Londra) — {nome} ===")
        print(prof[nome]["londra_locale"])

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

    for nome in PERIODI:
        print(f"\n=== RIAPERTURA DOPO IL ROLLOVER (blocchi di 15 min, UTC) — {nome} ===")
        print(prof[nome]["riapertura"])

    for nome in PERIODI:
        print(f"\n=== DERIVA DOPO LA RIAPERTURA GIORNALIERA (origine = chiusura del 1o minuto) — {nome} ===")
        print(tab_riap[nome])

    for nome in PERIODI:
        print(f"\n=== DERIVA DOPO LA RIAPERTURA SETTIMANALE (domenica sera) — {nome} ===")
        print(tab_riap_set[nome])

    print("\n=== PLACEBO della riapertura giornaliera: stessa misura ancorata 6 ore prima e 3 ore dopo ===")
    for nome in PERIODI:
        for scarto, etichetta in [(0, "vera"), (-360, "-6h"), (180, "+3h")]:
            r = tab_placebo[nome][scarto]
            print(f"{nome} ancora {etichetta:>5}: "
                  + "  ".join(f"{k}: {r.loc[k, 'ret_bp']:+.2f} bp (t={r.loc[k, 't']:+.1f}, "
                              f"n={int(r.loc[k, 'n'])})" for k in ("0->5", "5->120", "0->120")))

    print("\n=== QUALE OROLOGIO SEGUE IL MERCATO: profilo dell'escursione su tutto il giorno ===")
    for nome in PERIODI:
        for chiave, etichetta in [("utc", "UTC"), ("ny", "New York"), ("lon", "Londra")]:
            p = prof_gg[nome][chiave]
            top = p["rng_bp"].nlargest(5)
            print(f"{nome} — orologio {etichetta}: picco/mediana = "
                  f"{p['rng_bp'].max() / p['rng_bp'].median():.3f}, "
                  f"blocchi piu' agitati = {[f'{i} ({v:.2f} bp)' for i, v in top.items()]}")

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

    print("\n=== STABILITA': deriva dopo la riapertura giornaliera, per sotto-periodo ===")
    righe = []
    for nome, (y0, y1) in pezzi.items():
        sub = m1[(m1.index.year >= y0) & (m1.index.year <= y1)]
        r = deriva_riapertura(prepara(sub), settimanale=False)
        righe.append({"periodo": nome, "n": int(r.loc["0->120", "n"]),
                      "0->5": r.loc["0->5", "ret_bp"], "5->120": r.loc["5->120", "ret_bp"],
                      "0->120": r.loc["0->120", "ret_bp"], "t_0->120": r.loc["0->120", "t"],
                      "su_pct": r.loc["0->120", "su_pct"]})
    print(pd.DataFrame(righe).set_index("periodo"))

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
