"""Ricerca da zero, famiglia 5: calendario (giorno della settimana, fine/inizio
mese, prima/dopo il fine settimana, settimana delle scadenze delle opzioni USA,
mesi dell'anno come descrittiva).

Protocollo: docs/ricerca-da-zero-registrazione.md. Usa SOLO
D:\\ricerca_zero\\scoperta\\<SIM>_M5.parquet (indice UTC all'apertura).
Varianti dichiarate in docs/studies/zero/f5-calendario.md prima del calcolo:
518 = 110 (a giorno settimana) + 304 (b fine/inizio mese) + 80 (c fine
settimana) + 24 (d scadenze opzioni).

Giornate costruite dalle M5: "22-22" = [D-1 22:00, D 22:00) UTC etichettata D;
per gli indici anche "cash" (S&P/Nasdaq 9:30-16:00 New York, DAX 9:00-17:30
Berlino, ora legale vera). Chiusura = apertura dell'ultima M5 della giornata.

Uscite in D:\\ricerca_zero\\risultati\\:
  f5_varianti.parquet   una riga per variante (statistiche e due placebo)
  f5_operazioni.parquet una riga per operazione (tutte le varianti)
  f5_descr.parquet      descrittive (volatilita' per giorno, mesi dell'anno,
                        posizione del giorno nel mese)
Stampa solo aggregati compatti.
"""
from __future__ import annotations

import gc
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)

SCOPERTA = Path(r"D:\ricerca_zero\scoperta")
RISULTATI = Path(r"D:\ricerca_zero\risultati")
SIMBOLI = ["XAUUSD", "XAGUSD", "SPXUSD", "NSXUSD", "GRXEUR"]
COSTO = {"XAUUSD": 0.40, "XAGUSD": 0.025, "SPXUSD": 0.55, "NSXUSD": 1.50, "GRXEUR": 1.50}
CASH = {"SPXUSD": ("America/New_York", 9 * 60 + 30, 16 * 60),
        "NSXUSD": ("America/New_York", 9 * 60 + 30, 16 * 60),
        "GRXEUR": ("Europe/Berlin", 9 * 60, 17 * 60 + 30)}
N_PLACEBO = 1000
SEED = 12345
MIN_OP_ANNO = 5
GIORNI = ["lun", "mar", "mer", "gio", "ven"]
DUE_ORE = np.int64(2 * 3600 * 10**9)


# ---------------------------------------------------------------- dati
def carica(sim: str):
    d = pd.read_parquet(SCOPERTA / f"{sim}_M5.parquet", columns=["open", "high", "low", "close"])
    d = d[~d.index.duplicated()].sort_index()
    d.index = d.index.as_unit("ns")
    return d


def giornate(d: pd.DataFrame, tipo: str, sim: str) -> pd.DataFrame:
    O = d.open.values
    H = d.high.values
    L = d.low.values
    C = d.close.values
    idx = d.index
    ts = idx.asi8
    if tipo == "22-22":
        lab = (idx + pd.Timedelta(hours=2)).normalize().tz_localize(None).values
        pos = np.arange(len(d))
    else:
        tz, a, b = CASH[sim]
        loc = idx.tz_convert(tz)
        mm = loc.hour * 60 + loc.minute
        ok = (mm >= a) & (mm < b) & (loc.dayofweek < 5)
        pos = np.flatnonzero(ok)
        lab = loc[ok].tz_localize(None).normalize().values
    cambi = np.r_[0, np.flatnonzero(lab[1:] != lab[:-1]) + 1]
    st = pos[cambi]
    en = pos[np.r_[cambi[1:] - 1, len(pos) - 1]]
    n = np.diff(np.r_[cambi, len(pos)])
    hh = np.maximum.reduceat(H[pos], cambi)
    ll = np.minimum.reduceat(L[pos], cambi)
    g = pd.DataFrame({"data": pd.to_datetime(lab[cambi]), "st": st, "en": en, "n": n,
                      "H": hh, "L": ll, "Cl": C[en]})
    g = g[g.data.dt.dayofweek < 5]
    g = g[g.n >= 0.5 * g.n.median()].reset_index(drop=True)
    st = g.st.values
    en = g.en.values
    g["Po"] = O[st]                    # apertura della giornata
    g["Pc"] = O[en]                    # "chiusura" = apertura dell'ultima M5
    i_l2 = np.searchsorted(ts, ts[en] - DUE_ORE, side="left")
    g["Pl2"] = np.where((i_l2 >= st) & (i_l2 < en), O[np.minimum(i_l2, len(O) - 1)], np.nan)
    i_f2 = np.searchsorted(ts, ts[st] + DUE_ORE, side="left")
    g["Pf2"] = np.where((i_f2 > st) & (i_f2 <= en), O[np.minimum(i_f2, len(O) - 1)], np.nan)
    g["anno"] = g.data.dt.year
    g["mese"] = g.data.dt.year * 12 + g.data.dt.month - 1
    g["dow"] = g.data.dt.dayofweek
    g["rng"] = g.H - g.L
    cp = g.Cl.shift(1)
    g["tr"] = np.maximum(g.H, cp.fillna(g.H)) - np.minimum(g.L, cp.fillna(g.L))
    g["atr_pre"] = g.tr.rolling(14).mean().shift(1)
    return g


# ---------------------------------------------------------------- finestre
# tipo -> (prezzo di entrata al giorno a, prezzo di uscita al giorno a+L)
TIPI = {"CC": ("Pc", "Pc"), "OC": ("Po", "Pc"), "G": ("Pc", "Po"), "L2": ("Pl2", "Pc"),
        "L2G": ("Pl2", "Po"), "F2": ("Po", "Pf2"), "GF2": ("Pc", "Pf2")}
L_FISSO = {"OC": 0, "G": 1, "L2": 0, "L2G": 1, "F2": 0, "GF2": 1}


class Finestre:
    """Rendimenti lordi long (%) e costo (%) per ogni giornata di ancoraggio."""

    def __init__(self, g: pd.DataFrame, costo: float):
        self.g = g
        self.costo = costo
        self.N = len(g)
        self.giorno = g.data.values.astype("datetime64[D]").astype(np.int64)
        self.cache = {}

    def arr(self, tipo: str, L: int):
        k = (tipo, L)
        if k not in self.cache:
            pe, pu = TIPI[tipo]
            e = self.g[pe].values
            u = np.full(self.N, np.nan)
            if L < self.N:
                u[:self.N - L] = self.g[pu].values[L:]
            span = np.full(self.N, 1e9)
            if L < self.N:
                span[:self.N - L] = self.giorno[L:] - self.giorno[:self.N - L]
            ok = np.isfinite(e) & np.isfinite(u) & (span <= 1.5 * L + 5)
            lordo = (u - e) / e
            self.cache[k] = (e, u, lordo, self.costo / e, ok)
        return self.cache[k]


# ---------------------------------------------------------------- statistiche
def valuta(F: Finestre, anc: np.ndarray, Ls: np.ndarray, tipo: str, dirz: int,
           rng: np.random.Generator):
    """anc: indici di ancoraggio; Ls: durata (giorni di borsa) per operazione."""
    righe = []
    ent, usc, lg, cs = [], [], [], []
    keep = np.zeros(len(anc), bool)
    for j, (a, L) in enumerate(zip(anc, Ls)):
        e, u, lordo, cpc, ok = F.arr(tipo, int(L))
        if 0 <= a < F.N and ok[a]:
            keep[j] = True
            ent.append(e[a]); usc.append(u[a]); lg.append(lordo[a]); cs.append(cpc[a])
    anc = anc[keep]
    Ls = Ls[keep]
    n = len(anc)
    if n < 2:
        return None, None
    ent = np.array(ent); usc = np.array(usc); lg = np.array(lg); cs = np.array(cs)
    netto_pct = dirz * lg - cs
    netto_px = dirz * (usc - ent) - F.costo
    m = netto_pct.mean()
    sd = netto_pct.std(ddof=1)
    t = m / sd * np.sqrt(n) if sd > 0 else np.nan
    anni = pd.Series(netto_pct).groupby(F.g.anno.values[anc]).agg(["sum", "size"])
    anni = anni[anni["size"] >= MIN_OP_ANNO]
    # placebo DATE: stesse finestre/durate su ancoraggi casuali
    pl = np.zeros(N_PLACEBO)
    for L in np.unique(Ls):
        c = int((Ls == L).sum())
        _, _, lordo, cpc, ok = F.arr(tipo, int(L))
        pool = np.flatnonzero(ok)
        r = rng.integers(0, len(pool), size=(N_PLACEBO, c))
        a = pool[r]
        pl += (dirz * lordo[a] - cpc[a]).sum(axis=1)
    pl /= n
    p_date = (1 + (pl >= m).sum()) / (N_PLACEBO + 1)
    # placebo DIREZIONE
    s = np.where(rng.random((N_PLACEBO, n)) < 0.5, 1.0, -1.0)
    pd_ = (s * lg - cs).mean(axis=1)
    p_dir = (1 + (pd_ >= m).sum()) / (N_PLACEBO + 1)
    st = {"n": n, "lordo_px": (dirz * (usc - ent)).mean(), "netto_px": netto_px.mean(),
          "netto_pct": m * 100, "netto_costi": netto_px.mean() / F.costo,
          "costo_pct": cs.mean() * 100, "sd_pct": sd * 100, "t": t,
          "anni_pos": int((anni["sum"] > 0).sum()), "anni": int(len(anni)),
          "p_date": p_date, "p_dir": p_dir, "placebo_medio_pct": pl.mean() * 100}
    op = pd.DataFrame({"data": F.g.data.values[anc], "L": Ls, "dir": dirz, "entrata": ent,
                       "uscita": usc, "netto_px": netto_px, "netto_pct": netto_pct * 100})
    return st, op


# ---------------------------------------------------------------- regole
def ancoraggi(g: pd.DataFrame):
    """Dizionario nome -> (tipo, anc, Ls) per tutte le regole del mercato-giornata."""
    N = len(g)
    dow = g.dow.values
    mese = g.mese.values
    data = g.data.values.astype("datetime64[D]")
    R = {}
    # (a) giorno della settimana
    for di, nome in enumerate(GIORNI):
        a = np.flatnonzero(dow[1:] == di)          # giorno e = a+1, ancoraggio a
        R[("a", f"CC {nome}")] = ("CC", a, np.ones(len(a), int))
        a2 = np.flatnonzero(dow == di)
        R[("a", f"OC {nome}")] = ("OC", a2, np.zeros(len(a2), int))
    # (b) fine/inizio mese
    ultimo = np.flatnonzero(np.r_[mese[1:] != mese[:-1], False])   # TD-1 con mese dopo presente
    primo_mese = np.r_[0, np.flatnonzero(mese[1:] != mese[:-1]) + 1]
    for k in range(4):
        for j in range(5):
            if k == 0 and j == 0:
                continue
            anc, Ls = [], []
            for u in ultimo:
                a = u - k
                if a < 0 or mese[a] != mese[u]:
                    continue
                if u + j >= N or (j > 0 and mese[u + j] != mese[u + 1]):
                    continue
                anc.append(a); Ls.append(k + j)
            R[("b", f"TOM k{k} j{j}")] = ("CC", np.array(anc, int), np.array(Ls, int))
    # (c) fine settimana: a = ultimo giorno della settimana, a+1 = primo della successiva
    a = np.flatnonzero(dow[1:] <= dow[:-1])
    one = np.ones(len(a), int)
    zero = np.zeros(len(a), int)
    R[("c", "WG")] = ("G", a, one)
    R[("c", "WF2")] = ("L2", a, zero)
    R[("c", "WFG")] = ("L2G", a, one)
    R[("c", "WM2")] = ("F2", a + 1, zero)
    R[("c", "WGM2")] = ("GF2", a, one)
    # (d) scadenze opzioni (terzo venerdi')
    mesi = pd.period_range(g.data.iloc[0], g.data.iloc[-1], freq="M")
    ow, owp, of_ = ([], []), ([], []), ([], [])
    for p in mesi:
        d1 = p.start_time
        terzo = d1 + pd.Timedelta(days=(4 - d1.dayofweek) % 7 + 14)
        lun = terzo - pd.Timedelta(days=4)
        t64 = np.datetime64(terzo.date(), "D")
        l64 = np.datetime64(lun.date(), "D")
        i_x = np.searchsorted(data, t64, side="right") - 1        # ultimo valido <= terzo ven
        if i_x < 1 or data[i_x] < l64:
            continue
        i_e = np.searchsorted(data, l64, side="left") - 1         # ultimo valido prima del lunedi'
        if i_e >= 0:
            ow[0].append(i_e); ow[1].append(i_x - i_e)
        nx = np.searchsorted(data, t64 + np.timedelta64(7, "D"), side="right") - 1     # ultimo valido <= venerdi' dopo
        if nx > i_x and nx < N and data[nx] > t64 + np.timedelta64(2, "D"):
            owp[0].append(i_x); owp[1].append(nx - i_x)
        of_[0].append(i_x - 1); of_[1].append(1)
    for nome, (aa, ll) in (("OW", ow), ("OWP", owp), ("OF", of_)):
        R[("d", nome)] = ("CC", np.array(aa, int), np.array(ll, int))
    return R


# ---------------------------------------------------------------- descrittive
def descrittive(g: pd.DataFrame, F: Finestre, sim: str, tipo: str) -> list[dict]:
    out = []
    _, _, cc, _, ok = F.arr("CC", 1)
    ret = np.full(F.N, np.nan)
    ret[1:] = np.where(ok[:-1], cc[:-1], np.nan)               # rendimento CC del giorno e
    rr = (g.rng / g.atr_pre).values
    for di, nome in enumerate(GIORNI):
        m = g.dow.values == di
        out.append({"sim": sim, "giornata": tipo, "tab": "dow", "chiave": nome,
                    "rng_atr": np.nanmean(rr[m]), "abs_ret_pct": np.nanmean(np.abs(ret[m])) * 100,
                    "ret_pct": np.nanmean(ret[m]) * 100, "n": int(np.isfinite(ret[m]).sum())})
    # mesi dell'anno: chiusura ultimo giorno mese prima -> chiusura ultimo giorno mese
    ult = np.flatnonzero(np.r_[g.mese.values[1:] != g.mese.values[:-1], True])
    pc = g.Pc.values[ult]
    mm = pd.Series(pc[1:] / pc[:-1] - 1, index=g.data.values[ult[1:]])
    dfm = pd.DataFrame({"r": mm.values, "mese": mm.index.month, "anno": mm.index.year})
    for mo, x in dfm.groupby("mese"):
        out.append({"sim": sim, "giornata": tipo, "tab": "mese", "chiave": f"{mo:02d}",
                    "ret_pct": x.r.mean() * 100, "pos": int((x.r > 0).sum()), "n": len(x)})
    # posizione del giorno nel mese
    mese = g.mese.values
    primo = np.r_[True, mese[1:] != mese[:-1]]
    ultimo = np.r_[mese[1:] != mese[:-1], True]
    gid = np.cumsum(primo) - 1
    pos_inizio = np.arange(F.N) - np.flatnonzero(primo)[gid] + 1
    pos_fine = -(np.flatnonzero(ultimo)[gid] - np.arange(F.N) + 1)
    for p in list(range(-5, 0)) + list(range(1, 6)):
        m = (pos_fine == p) if p < 0 else (pos_inizio == p)
        x = ret[m]
        x = x[np.isfinite(x)]
        out.append({"sim": sim, "giornata": tipo, "tab": "td", "chiave": f"TD{p:+d}",
                    "ret_pct": x.mean() * 100, "t": x.mean() / x.std(ddof=1) * np.sqrt(len(x)),
                    "n": len(x)})
    tutti = ret[np.isfinite(ret)]
    out.append({"sim": sim, "giornata": tipo, "tab": "td", "chiave": "tutti",
                "ret_pct": tutti.mean() * 100, "t": tutti.mean() / tutti.std(ddof=1) * np.sqrt(len(tutti)),
                "n": len(tutti)})
    return out


# ---------------------------------------------------------------- main
def main():
    RISULTATI.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    var, ops, descr = [], [], []
    vid = 0
    for sim in SIMBOLI:
        d = carica(sim)
        tipi = ["22-22"] + (["cash"] if sim in CASH else [])
        for tipo in tipi:
            g = giornate(d, tipo, sim)
            F = Finestre(g, COSTO[sim])
            descr += descrittive(g, F, sim, tipo)
            for (fam, nome), (wt, anc, Ls) in ancoraggi(g).items():
                if fam == "a" and wt == "OC" and tipo == "22-22":
                    continue
                if fam == "d" and sim not in ("SPXUSD", "NSXUSD"):
                    continue
                for dirz in (1, -1):
                    st, op = valuta(F, anc, Ls, wt, dirz, rng)
                    if st is None:
                        continue
                    vid += 1
                    var.append({"id": vid, "fam": fam, "sim": sim, "giornata": tipo, "regola": nome,
                                "dir": "long" if dirz > 0 else "short", **st})
                    op["id"] = vid
                    ops.append(op)
            del g, F
            gc.collect()
        del d
        gc.collect()
    V = pd.DataFrame(var)
    V["anni_frac"] = V.anni_pos / V.anni.where(V.anni > 0)
    V["n_ok"] = V.n >= 100
    V["promossa"] = ((V.netto_px > 0) & (V.t >= 3) & (V.anni_frac >= 0.75) & (V.p_date < 0.01)
                     & (V.p_dir < 0.01) & V.n_ok)
    V.to_parquet(RISULTATI / "f5_varianti.parquet")
    pd.concat(ops, ignore_index=True).to_parquet(RISULTATI / "f5_operazioni.parquet")
    D = pd.DataFrame(descr)
    D.to_parquet(RISULTATI / "f5_descr.parquet")

    print("varianti:", len(V), V.groupby("fam").size().to_dict(), "promosse:", int(V.promossa.sum()))
    print("t>=3:", int((V.t >= 3).sum()), "t>=2:", int((V.t >= 2).sum()), "t<=-3:", int((V.t <= -3).sum()),
          "p_date<0.01:", int((V.p_date < 0.01).sum()), "n<100:", int((~V.n_ok).sum()))
    cols = ["fam", "sim", "giornata", "regola", "dir", "n", "netto_px", "netto_pct", "netto_costi",
            "t", "anni_pos", "anni", "p_date", "p_dir"]
    print(V.sort_values("t", ascending=False)[cols].head(15).round(3).to_string(index=False))
    print(V[V.n >= 100].sort_values("t", ascending=False)[cols].head(8).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
