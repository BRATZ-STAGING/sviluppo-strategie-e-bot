#!/usr/bin/env python3
"""Famiglia E macro: calendario degli eventi 2009-2026 da fonti ufficiali.

Fonti (pagine pubbliche, nessun account, cache su disco riavviabile):
  federalreserve.gov  monetarypolicy/fomccalendars.htm (2021-2027)
                      monetarypolicy/fomchistorical{2008..2020}.htm
  bls.gov             bls/news-release/cpi.htm, empsit.htm (archivio release)
                      news.release/archives/{cpi|empsit}_MMDDYYYY.htm (riga
                      "embargoed until 8:30 a.m. (ET) <giorno>, <data>": data
                      e ora verificate release per release)
                      schedule/news_release/{cpi|empsit}.htm (date future 2026)

Il sito BLS rifiuta i client senza un contatto nello User-Agent: si usa un
indirizzo segnaposto (example.com), nessun dato personale.

Orari dei comunicati FOMC (le pagine pre-2013 dicono "For immediate release"
senza ora; regola storica nota, controllata poi sui dati M5 in
macro_e_eventi.py): 2009 -> 2012 alle 14:15 NY, con conferenza stampa
(aprile 2011 -> dicembre 2012) alle 12:30 NY; dal 2013 alle 14:00 NY.
Verbali: 14:00 NY. CPI e NFP: 08:30 NY (verificato sulla riga d'embargo).

Riunioni straordinarie (conference call, "unscheduled", notation vote): non
sono annunciate in anticipo -> elencate con straordinaria=True e
annunciata_prima=False; da escludere dalle regole.

Scrive D:\\ricerca_macro\\dati\\eventi\\calendario_2009_2026.csv
Colonne: tipo (FOMC, VERBALI, CPI, NFP), data_ny, ora_ny, dt_ny, dt_utc,
riferimento, straordinaria, annunciata_prima, stimata, conferenza, nota.
Stampa solo il controllo per anno e le anomalie.
"""
from __future__ import annotations

import os
import re
import time
import urllib.request
from datetime import datetime, timedelta

import pandas as pd

DIR = r"D:\ricerca_macro\dati\eventi"
CACHE = os.path.join(DIR, "cache")
OUT = os.path.join(DIR, "calendario_2009_2026.csv")
UA_FED = "Mozilla/5.0 (calendario-ricerca)"
UA_BLS = "calendario-ricerca/1.0 (ricerca@example.com)"
MESI = {m: i + 1 for i, m in enumerate(
    "January February March April May June July August September October November December".split())}
ANNI = range(2009, 2027)
SHUTDOWN = [("2013-10-22", "NFP"), ("2013-10-30", "CPI"), ("2013-11-08", "NFP"), ("2013-11-20", "CPI"),
            ("2025-10-24", "CPI"), ("2025-11-20", "NFP"), ("2025-12-16", "NFP"), ("2025-12-18", "CPI")]
FONTI = {"pagina": 0, "sched": 0, "file": 0}


def leggi(url, nome, ua, obbligatorio=True):
    p = os.path.join(CACHE, nome)
    if os.path.exists(p) and os.path.getsize(p) > 2000:
        return open(p, encoding="utf8", errors="replace").read()
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html"})
    for prova in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                t = r.read().decode("utf8", errors="replace")
            open(p, "w", encoding="utf8").write(t)
            time.sleep(0.4)
            return t
        except Exception as e:  # noqa: BLE001
            err = e
            if getattr(e, "code", None) == 404:
                break
            time.sleep(2 + 3 * prova)
    if obbligatorio:
        raise RuntimeError(f"{url}: {err}")
    return None


def testo(html):
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t.replace("&#160;", " ").replace("&nbsp;", " "))


def data_lunga(s):
    m = re.match(r"([A-Za-z]+)\.? (\d+), (\d{4})", s.strip())
    mese = [v for k, v in MESI.items() if k.startswith(m.group(1)[:3])][0]
    return datetime(int(m.group(3)), mese, int(m.group(2))).date()


def mese_n(s):
    return [v for k, v in MESI.items() if k.startswith(s[:3])][0]


def ora_fomc(d, conferenza):
    if d.year >= 2013:
        return "14:00"
    if conferenza and d >= datetime(2011, 4, 1).date():
        return "12:30"
    return "14:15"


# ----------------------------------------------------------------- FOMC
def fomc():
    righe = []
    # storico 2008-2020: blocchi fra intestazioni <h5>
    for y in range(2008, 2021):
        h = leggi(f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm",
                  f"fomchistorical{y}.htm", UA_FED)
        pos = [(m.start(), testo(m.group(1)).strip()) for m in re.finditer(r"<h5[^>]*>(.*?)</h5>", h, re.S)]
        for k, (p0, tit) in enumerate(pos):
            blk = h[p0: pos[k + 1][0] if k + 1 < len(pos) else len(h)]
            righe.append(_riunione(y, tit, blk))
    # 2021-2026 dalla pagina corrente
    h = leggi("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", "fomccalendars.htm", UA_FED)
    for y in range(2021, 2027):
        i = h.find(f"{y} FOMC Meetings")
        j = h.find("FOMC Meetings", i + 20)
        blk = h[i: j if j > 0 else len(h)]
        parti = re.split(r'(?=<div class="[^"]*row fomc-meeting")', blk)
        for pz in parti[1:]:
            m = re.search(r"fomc-meeting__month[^>]*>\s*<strong>(.*?)</strong>.*?fomc-meeting__date[^>]*>(.*?)</div>", pz, re.S)
            if not m:
                continue
            mese = testo(m.group(1)).strip().split("/")[-1]
            tit = f"{mese} {testo(m.group(2)).strip()} Meeting - {y}"
            righe.append(_riunione(y, tit, pz))
    df = pd.DataFrame([r for r in righe if r])
    return df


def _riunione(y, tit, blk):
    tit2 = re.sub(r"^([A-Za-z]+) (\d+)-([A-Za-z]+) (\d+)", r"\1/\3 \2-\4", tit)  # "July 31-August 1"
    m = re.match(r"([A-Za-z]+)(?:/([A-Za-z]+))? (\d+)(?:-(\d+))?\*?\s*(.*?)\s*-\s*\d{4}$", tit2)
    if not m:
        print("titolo non letto:", tit)
        return None
    resto = m.group(5).lower()
    straord = any(k in resto for k in ("unscheduled", "conference call", "notation vote"))
    if "cancelled" in resto:
        return dict(titolo=tit, cancellata=True)
    mese2 = m.group(2) or m.group(1)
    g = int(m.group(4) or m.group(3))
    fine = datetime(y, mese_n(mese2), g).date()
    st = sorted(set(re.findall(r"monetary(\d{8})a\.htm", blk)))
    st_d = [datetime.strptime(s, "%Y%m%d").date() for s in st]
    st_d = [d for d in st_d if abs((d - fine).days) <= 2]
    stat = st_d[-1] if st_d else None
    conf = "Press Conference" in blk or "fomcpresconf" in blk
    mins = re.findall(r"\(Released ([A-Za-z]+ \d+, \d{4})\)", testo(blk))
    return dict(titolo=tit, cancellata=False, fine=fine, statement=stat, straordinaria=straord,
                conferenza=conf, verbali=data_lunga(mins[0]) if mins else None)


# ------------------------------------------------------------------ BLS
def bls(tipo):
    k = "cpi" if tipo == "CPI" else "empsit"
    h = leggi(f"https://www.bls.gov/bls/news-release/{k}.htm", f"bls_{k}_archivio.htm", UA_BLS)
    voci = re.findall(rf'href="(?:https://www\.bls\.gov)?/news\.release/archives/({k}_[0-9]+)\.htm">\s*([A-Za-z]+ \d{{4}})', h)
    righe = []
    for f, rif in voci:
        ry = int(rif.split()[-1])
        if ry < 2008 or ry > 2026 or rif == "December 2026":  # uscita nel 2027
            continue
        t = leggi(f"https://www.bls.gov/news.release/archives/{f}.htm", f"bls_{f}.htm", UA_BLS, obbligatorio=False)
        d = ora = None
        if t:
            tt = testo(t)
            m = re.search(r"(?i:embargoed).{0,60}?(\d{1,2}:\d{2})\s*([apAP])\.?[mM]\.?.{0,90}?"
                          r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? ?\d{4})", tt)
            if m:
                hh, mm = map(int, m.group(1).split(":"))
                if m.group(2).lower() == "p" and hh < 12:
                    hh += 12
                ora = f"{hh:02d}:{mm:02d}"
                d = data_lunga(m.group(3).replace(",", ", ").replace(",  ", ", ").replace(" ,", ","))
        mfile = re.match(rf"{k}_(\d{{2}})(\d{{2}})(\d{{4}})$", f)
        dfile = datetime(int(mfile.group(3)), int(mfile.group(1)), int(mfile.group(2))).date() if mfile else None
        righe.append(dict(tipo=tipo, riferimento=rif, file=f, data_pagina=d, ora_pagina=ora, data_file=dfile))
    df = pd.DataFrame(righe)
    # calendario delle uscite future (anno corrente)
    s = leggi(f"https://www.bls.gov/schedule/news_release/{k}.htm", f"bls_sched_{k}.htm", UA_BLS)
    sc = re.findall(r"([A-Za-z]+ \d{4})\s+([A-Z][a-z]{2})\.? (\d{2}), (\d{4})\s+(\d{2}:\d{2}) ([AP])M", testo(s))
    fut = []
    for rif, mon, dd, yy, hm, ap in sc:
        mese = [m for m in MESI if m.startswith(mon)][0]
        fut.append(dict(riferimento=rif, data_sched=datetime(int(yy), MESI[mese], int(dd)).date(), ora_sched=hm))
    return df, pd.DataFrame(fut)


def a_utc(d, hhmm):
    loc = pd.Timestamp(f"{d} {hhmm}").tz_localize("America/New_York")
    return loc, loc.tz_convert("UTC")


def main():
    os.makedirs(CACHE, exist_ok=True)
    righe, anomalie = [], []
    oggi = datetime(2026, 10, 6).date()

    F = fomc()
    canc = F[F["cancellata"]]
    for t in canc["titolo"]:
        anomalie.append(f"FOMC cancellata: {t}")
    F = F[~F["cancellata"]]
    for _, r in F.iterrows():
        if r["fine"].year not in ANNI:
            pass
        d = r["statement"]
        stimata = False
        if pd.isna(d):
            if r["straordinaria"]:
                continue  # notation vote / call senza comunicato
            d, stimata = r["fine"], r["fine"] > oggi
        if d.year in ANNI:
            ora = "14:00" if d.year >= 2013 else ora_fomc(d, r["conferenza"])
            if r["straordinaria"]:
                ora = ""
            nota = r["titolo"]
            righe.append(dict(tipo="FOMC", data_ny=d, ora_ny=ora, riferimento=r["titolo"],
                              straordinaria=r["straordinaria"], annunciata_prima=not r["straordinaria"],
                              stimata=stimata, conferenza=bool(r["conferenza"]), nota=nota))
        if not r["straordinaria"] or (not pd.isna(r["verbali"]) and r["verbali"] >= r["fine"] + timedelta(days=14)):
            v = r["verbali"]
            vst = False
            if pd.isna(v):
                v, vst = r["fine"] + timedelta(days=21), True
            if v.year in ANNI:
                righe.append(dict(tipo="VERBALI", data_ny=v, ora_ny="14:00", riferimento=r["titolo"],
                                  straordinaria=False, annunciata_prima=True, stimata=vst and v > oggi,
                                  conferenza=False, nota="data stimata (+21 giorni)" if vst else ""))

    for tipo in ("CPI", "NFP"):
        B, S = bls(tipo)
        Smap = dict(zip(S["riferimento"], zip(S["data_sched"], S["ora_sched"])))
        for _, r in B.iterrows():
            d, ora, nota = r["data_pagina"], r["ora_pagina"], ""
            FONTI["pagina" if not pd.isna(d) else ("sched" if r["riferimento"] in Smap else "file")] += 1
            if pd.isna(d):
                if r["riferimento"] in Smap:
                    d, ora = Smap[r["riferimento"]]
                    nota = "data dal calendario BLS (release non ancora pubblicata)"
                elif not pd.isna(r["data_file"]):
                    d, ora, nota = r["data_file"], "08:30", "data dal nome del file (pagina non letta)"
                else:
                    anomalie.append(f"{tipo} {r['riferimento']}: data non trovata")
                    continue
            elif not pd.isna(r["data_file"]) and r["data_file"] != d:
                anomalie.append(f"{tipo} {r['riferimento']}: file {r['data_file']} != embargo {d}")
            if ora != "08:30":
                anomalie.append(f"{tipo} {r['riferimento']}: ora {ora}")
            if d.year in ANNI:
                righe.append(dict(tipo=tipo, data_ny=d, ora_ny=ora, riferimento=r["riferimento"],
                                  straordinaria=False, annunciata_prima=True, stimata=d > oggi,
                                  conferenza=False, nota=nota))
        noti = set(B["riferimento"])
        for rif, (d, ora) in Smap.items():
            if rif not in noti and d.year in ANNI:
                righe.append(dict(tipo=tipo, data_ny=d, ora_ny=ora, riferimento=rif, straordinaria=False,
                                  annunciata_prima=True, stimata=d > oggi, conferenza=False,
                                  nota="data dal calendario BLS"))

    C = pd.DataFrame(righe).drop_duplicates(["tipo", "data_ny", "riferimento"])
    # un verbale per data (le riunioni straordinarie del 2020 escono nello stesso documento)
    C = C.sort_values("straordinaria").drop_duplicates(["tipo", "data_ny"], keep="first")
    # date spostate dalle chiusure del governo federale (ottobre 2013, ottobre-novembre 2025):
    # rese note dal BLS alcuni giorni prima, restano "annunciate in anticipo"
    for d, t in SHUTDOWN:
        k = (C["tipo"] == t) & (pd.to_datetime(C["data_ny"]) == pd.Timestamp(d))
        C.loc[k, "nota"] = (C.loc[k, "nota"] + " " if k.any() else "") + "data spostata dalla chiusura del governo"
    print(f"Date BLS: dalla riga d'embargo {FONTI['pagina']}, dal calendario BLS {FONTI['sched']}, "
          f"dal nome del file {FONTI['file']}")
    dt_ny, dt_utc = [], []
    for _, r in C.iterrows():
        if r["ora_ny"]:
            a, b = a_utc(r["data_ny"], r["ora_ny"])
            dt_ny.append(a.isoformat())
            dt_utc.append(b.strftime("%Y-%m-%d %H:%M"))
        else:
            dt_ny.append("")
            dt_utc.append("")
    C["dt_ny"], C["dt_utc"] = dt_ny, dt_utc
    C["anno"] = pd.to_datetime(C["data_ny"]).dt.year
    C = C.sort_values(["data_ny", "tipo"]).reset_index(drop=True)
    cols = ["tipo", "data_ny", "ora_ny", "dt_ny", "dt_utc", "riferimento", "straordinaria",
            "annunciata_prima", "stimata", "conferenza", "nota"]
    C[cols].to_csv(OUT, index=False)

    # controllo
    reg = C[~C["straordinaria"]]
    tab = reg.pivot_table(index="anno", columns="tipo", values="data_ny", aggfunc="count").fillna(0).astype(int)
    tab["FOMC_straord"] = C[C["straordinaria"]].groupby("anno").size().reindex(tab.index).fillna(0).astype(int)
    tab["stimati"] = C[C["stimata"]].groupby("anno").size().reindex(tab.index).fillna(0).astype(int)
    print(tab.to_string())
    for tipo, att in (("FOMC", 8), ("VERBALI", 8), ("CPI", 12), ("NFP", 12)):
        for a, n in tab[tipo].items():
            if n != att:
                anomalie.append(f"{tipo} {a}: {n} eventi (attesi {att})")
    # mesi senza release o con due release (chiusure del governo)
    for tipo in ("CPI", "NFP"):
        x = reg[reg["tipo"] == tipo].copy()
        x["mese"] = pd.to_datetime(x["data_ny"]).dt.to_period("M")
        dup = x.groupby("mese").size()
        for m_, n in dup[dup > 1].items():
            anomalie.append(f"{tipo}: {n} release nel mese {m_}")
        tutti = pd.period_range("2009-01", "2026-12", freq="M")
        for m_ in tutti.difference(dup.index):
            anomalie.append(f"{tipo}: nessuna release nel mese {m_}")
        # giorno della settimana insolito per NFP (non venerdi')
        if tipo == "NFP":
            wd = pd.to_datetime(x["data_ny"]).dt.dayofweek
            for d in x.loc[wd != 4, "data_ny"]:
                anomalie.append(f"NFP non di venerdi': {d}")
    for _, r in C[C["straordinaria"]].iterrows():
        anomalie.append(f"FOMC straordinaria (esclusa): {r['data_ny']} {r['riferimento']}")
    for _, r in C[(C["tipo"] == "FOMC") & (C["ora_ny"] != "14:00") & ~C["straordinaria"]].iterrows():
        pass
    print(f"\nEventi: {len(C)}; anomalie: {len(anomalie)}")
    for a in anomalie:
        print(" -", a)
    pd.Series(anomalie, name="anomalia").to_csv(os.path.join(DIR, "calendario_anomalie.csv"), index=False)


if __name__ == "__main__":
    main()
