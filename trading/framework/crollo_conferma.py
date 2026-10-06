"""Crollo -> conferma di ripresa -> entrata (e lo specchio short).

Protocollo VINCOLANTE: ``docs/crollo-conferma-registrazione.md`` (commit
5a2ea2b); per lo swing v2 (stop S1, S2, S3 senza tetto) anche
``docs/crollo-conferma-swing-v2-registrazione.md`` (commit bf9a30b). Questo modulo contiene solo funzioni pure su array numpy: nessun
caricamento di dati, nessuna scelta di periodo.

Convenzioni
-----------
- Tempi in **minuti dall'epoca Unix** (int64), UTC; ogni candela e'
  etichettata all'APERTURA.
- Le serie del timeframe del segnale (M15, H1, H4, D1) sono costruite dalle
  M5 (``barre_da_m5``): ogni barra conosce l'indice della sua prima e ultima
  M5, cosi' l'entrata "all'apertura della barra successiva" e' esattamente
  l'apertura di una M5 e la gestione dell'operazione si fa sulle M5.
- **Nessun lookahead**: ogni decisione alla barra ``j`` usa solo barre
  ``<= j`` chiuse. I frattali a 2 barre per lato sono noti 2 barre dopo
  l'estremo; l'ATR20 giornaliero e' quello delle giornate gia' chiuse; il
  VWAP e la EMA sono cumulativi/ricorsivi.
- Il lato short e' lo **specchio esatto**: si negano i prezzi
  (``specchio``), si cercano i segnali long sulla serie negata e si gestisce
  l'operazione con ``dir = -1`` sui prezzi veri.

Interpretazioni (le piu' prudenti, dichiarate nel rapporto)
----------------------------------------------------------
- Giornata = giorno UTC; una giornata con meno di 300 minuti (domenica sera,
  festivi) si unisce alla giornata valida successiva. ATR20 = media semplice
  dei true range delle ultime 20 giornate chiuse.
- Crollo alla chiusura della barra ``i``: massimo della finestra (24 ore per
  l'intraday, 10 giornate per lo swing, barra ``i`` inclusa) meno il minimo
  della barra ``i`` >= k x ATR. Un episodio parte solo sul **fronte**
  (condizione vera in ``i`` e falsa in ``i-1``) e solo se non c'e' un
  episodio in corso; finisce alla conferma o alla scadenza.
- Inizio del crollo = barra del massimo della finestra (la piu' recente a
  parita'); H = quel massimo (obiettivo "ritorno al massimo d'inizio
  crollo"). L = minimo dalla barra di H, aggiornato fino alla conferma.
- Scadenza: la conferma deve chiudere entro 8 ore (intraday) o entro 10
  giornate (swing) dalla barra dell'ultimo minimo L.
- C3 "recupero": incrocio dal basso (chiusura precedente <= livello,
  chiusura attuale > livello), non la semplice chiusura sopra.
- C5: le conferme C1, C2, C3a, C4 contano solo se avvenute dopo l'ultimo
  nuovo minimo (un nuovo minimo azzera i conteggi).
- Stop (parametro ``stop`` di ``operazioni``): "v1" (default, protocollo v1)
  = L - 0,1 x ATR con 1R <= 1,5 x ATR; "S1" = stesso stop senza tetto;
  "S2" = ultimo minimo frattale confermato (noto alla chiusura della barra
  di conferma) dopo L e sopra L, meno 0,1 x ATR, altrimenti come S1; "S3" =
  1,5 x ATR dal prezzo d'entrata. S1-S3 scartano solo se 1R < 2 x costo.
- Stop e obiettivi sulle M5: lo stop prevale nella stessa candela; apertura
  oltre lo stop = uscita all'apertura; apertura oltre l'obiettivo = uscita
  all'obiettivo (non al prezzo migliore).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace

import numpy as np

# ------------------------------------------------------------------ costanti
CONFERME = ("C1", "C2", "C3a", "C3b", "C3c", "C4", "C5")
OBIETTIVI = ("1R", "2R", "3R", "H")
STOP = ("v1", "S1", "S2", "S3")    # "v1" = protocollo v1 (con tetto 1,5 ATR)
MIN_GIORNATA = 300                 # minuti: sotto e' una sessione parziale
SPREAD_FINO_2019 = 0.46            # $ round trip
SPREAD_DAL_2020 = {2020: 0.35, 2021: 0.349, 2022: 0.395, 2023: 0.334,
                   2024: 0.384, 2025: 0.632, 2026: 0.631}   # verifica_bot.py
EXTRA_DAL_2020 = 0.06
SWAP_LONG, SWAP_SHORT, SWAP_RIF = -0.715, 0.325, 4156.98   # $/oncia/notte FP
ORA_SWAP = 21 * 60                 # 21:00 UTC
INTRADAY = dict(finestra_crollo=24 * 60, scadenza=8 * 60,
                vieta_da=20 * 60 + 45, vieta_a=22 * 60 + 15, chiusura=20 * 60 + 55)
SWING = dict(giornate_crollo=10, scadenza_giornate=10, tenuta_giornate=20)


def costo_rt(anno: int) -> float:
    """Costo round trip in $/oncia (x1): 0,46 fino al 2019, poi SPREAD + 0,06."""
    if anno <= 2019:
        return SPREAD_FINO_2019
    return SPREAD_DAL_2020[min(anno, 2026)] + EXTRA_DAL_2020


# ------------------------------------------------------------- giornate e ATR
def giornate(etichette_d1: np.ndarray, minuti_d1: np.ndarray) -> np.ndarray:
    """Fine (minuti) di ogni giornata valida.

    ``etichette_d1``: inizio del giorno UTC in minuti; ``minuti_d1``: minuti
    M1 presenti. Le giornate con meno di ``MIN_GIORNATA`` minuti si uniscono
    alla successiva valida (la loro fine non e' una fine di giornata).
    """
    ok = np.asarray(minuti_d1) >= MIN_GIORNATA
    return np.asarray(etichette_d1, np.int64)[ok] + 1440


def giorno_di(fine_giorno: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Indice della giornata che contiene l'istante ``t`` (fine > t)."""
    return np.searchsorted(fine_giorno, t, side="right")


def atr_giornaliero(o, h, l, c, n: int = 20) -> np.ndarray:
    """ATR ``n`` (media semplice del true range) noto ALLA FINE di ogni giornata."""
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - pc), np.abs(l - pc)]), axis=0)
    cs = np.r_[0.0, np.cumsum(tr)]
    out = np.full(len(tr), np.nan)
    if len(tr) >= n:
        out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


def atr_a(fine_giorno: np.ndarray, atr_fine: np.ndarray, t: np.ndarray) -> np.ndarray:
    """ATR noto all'istante ``t``: quello dell'ultima giornata chiusa (fine <= t)."""
    k = np.searchsorted(fine_giorno, t, side="right") - 1
    return np.where(k >= 0, atr_fine[np.clip(k, 0, None)], np.nan)


# -------------------------------------------------------------------- barre
@dataclass
class Barre:
    """Serie del timeframe del segnale, array allineati (una voce per barra)."""
    t: np.ndarray        # etichetta (apertura) in minuti
    fine: np.ndarray     # chiusura in minuti
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    vwap: np.ndarray     # VWAP giornaliero alla chiusura della barra
    ema: np.ndarray      # EMA20 delle chiusure del TF
    atr: np.ndarray      # ATR20 giornaliero noto alla chiusura della barra
    atr_ap: np.ndarray   # ATR20 noto all'apertura della barra (entrata)
    giorno: np.ndarray   # indice della giornata
    i5: np.ndarray       # indice della prima M5 della barra
    i5_fine: np.ndarray  # indice dell'ultima M5 della barra


def ema(x: np.ndarray, n: int = 20) -> np.ndarray:
    """EMA ricorsiva (alpha = 2/(n+1), parte dal primo valore)."""
    a = 2.0 / (n + 1)
    out = np.empty(len(x))
    v = x[0]
    for i, xi in enumerate(x):
        v = xi if i == 0 else a * xi + (1 - a) * v
        out[i] = v
    return out


def barre_da_m5(t5, o5, h5, l5, c5, chiave, durata, vwap5, fine_giorno, atr_fine,
                fine=None) -> Barre:
    """Aggrega le M5 per ``chiave`` (non decrescente) in barre del TF.

    ``durata`` in minuti (etichetta = chiave x durata), oppure ``fine``
    esplicita per barra (giornate unite). ``vwap5`` = VWAP alla chiusura di
    ogni M5.
    """
    chiave = np.asarray(chiave)
    i5 = np.r_[0, np.nonzero(np.diff(chiave))[0] + 1]
    i5f = np.r_[i5[1:] - 1, len(chiave) - 1]
    o = o5[i5]
    h = np.maximum.reduceat(h5, i5)
    l = np.minimum.reduceat(l5, i5)
    c = c5[i5f]
    if fine is None:
        t = chiave[i5].astype(np.int64) * durata
        fn = t + durata
    else:
        fn = np.asarray(fine, np.int64)
        t = fn - durata
    return Barre(t=t, fine=fn, o=o, h=h, l=l, c=c, vwap=vwap5[i5f], ema=ema(c),
                 atr=atr_a(fine_giorno, atr_fine, fn),
                 atr_ap=atr_a(fine_giorno, atr_fine, t5[i5]),
                 giorno=giorno_di(fine_giorno, t5[i5]), i5=i5, i5_fine=i5f)


def specchio(B: Barre) -> Barre:
    """Prezzi negati: un'impennata diventa un crollo (lato short)."""
    return replace(B, o=-B.o, h=-B.l, l=-B.h, c=-B.c, vwap=-B.vwap, ema=-B.ema)


# ------------------------------------------------------------- strumenti
def frattali(h: np.ndarray, l: np.ndarray, n: int = 2):
    """Frattali a ``n`` barre per lato (estremo stretto). Segnati sull'estremo f;
    sono NOTI solo alla chiusura di f + n (``ultimo_noto``)."""
    N = len(h)
    fh = np.zeros(N, bool)
    fl = np.zeros(N, bool)
    if N >= 2 * n + 1:
        mh = np.ones(N - 2 * n, bool)
        ml = np.ones(N - 2 * n, bool)
        mid = slice(n, N - n)
        for d in range(1, n + 1):
            for s in (-d, d):
                mh &= h[mid] > h[n + s:N - n + s]
                ml &= l[mid] < l[n + s:N - n + s]
        fh[mid] = mh
        fl[mid] = ml
    return fh, fl


def ultimo_noto(flag: np.ndarray, n: int = 2) -> np.ndarray:
    """Per ogni barra j: indice dell'ultimo frattale f con f + n <= j (-1 se nessuno)."""
    idx = np.where(flag, np.arange(len(flag)), -1)
    sh = np.full(len(flag), -1)
    sh[n:] = idx[:-n] if n else idx
    return np.maximum.accumulate(sh)


def martello(o, h, l, c) -> np.ndarray:
    """Chiusura nel terzo alto e ombra inferiore >= 2 x corpo."""
    rng = h - l
    return (rng > 0) & (c - l >= rng * (2.0 / 3.0)) & (np.minimum(o, c) - l >= 2 * np.abs(c - o))


def engulfing(o, h, l, c) -> np.ndarray:
    """Engulfing rialzista: barra precedente ribassista, corpo attuale la avvolge."""
    out = np.zeros(len(o), bool)
    out[1:] = (c[:-1] < o[:-1]) & (c[1:] > o[1:]) & (o[1:] <= c[:-1]) & (c[1:] >= o[:-1])
    return out


def inizio_finestra(B: Barre, orizzonte: str) -> np.ndarray:
    """Prima barra della finestra del massimo (24 ore o 10 giornate, barra inclusa)."""
    if orizzonte == "intraday":
        return np.searchsorted(B.t, B.t - INTRADAY["finestra_crollo"], side="right")
    return np.searchsorted(B.giorno, B.giorno - (SWING["giornate_crollo"] - 1), side="left")


def massimo_scorrevole(h: np.ndarray, lo: np.ndarray):
    """Massimo di h[lo[i]..i] e indice (il piu' recente a parita'); lo non decrescente."""
    n = len(h)
    mx = np.empty(n)
    ix = np.empty(n, np.int64)
    dq: deque = deque()
    for i in range(n):
        hi = h[i]
        while dq and h[dq[-1]] <= hi:
            dq.pop()
        dq.append(i)
        while dq[0] < lo[i]:
            dq.popleft()
        mx[i] = h[dq[0]]
        ix[i] = dq[0]
    return mx, ix


def fronti_crollo(B: Barre, k: float, orizzonte: str):
    """Condizione di crollo per barra, fronti di salita, massimo e sua barra."""
    hw, hi = massimo_scorrevole(B.h, inizio_finestra(B, orizzonte))
    with np.errstate(invalid="ignore"):
        cond = (hw - B.l) >= k * B.atr
    cond &= ~np.isnan(B.atr)
    fronte = cond & ~np.r_[False, cond[:-1]]
    return cond, fronte, hw, hi


# ----------------------------------------------------------------- segnali
@dataclass
class Segnale:
    inizio: int      # barra di rilevazione del crollo (fronte)
    conferma: int    # barra della conferma (entrata all'apertura di conferma+1)
    H: float         # massimo d'inizio crollo
    iH: int
    L: float         # minimo del crollo alla conferma
    iL: int
    F: float = np.nan   # ultimo minimo frattale noto alla conferma, dopo L e sopra L (S2)


def _scaduto(B: Barre, j: int, iL: int, orizzonte: str) -> bool:
    if orizzonte == "intraday":
        return B.fine[j] - B.fine[iL] > INTRADAY["scadenza"]
    return B.giorno[j] - B.giorno[iL] > SWING["scadenza_giornate"]


def segnali(B: Barre, k: float, conferma: str, orizzonte: str) -> list[Segnale]:
    """Segnali long (per lo short: ``segnali(specchio(B), ...)``).

    ``conferma`` in CONFERME oppure "NESSUNA" (riferimento senza conferma:
    entrata alla barra dopo il fronte del crollo).
    """
    _, fronte, hw, hix = fronti_crollo(B, k, orizzonte)
    out: list[Segnale] = []
    n = len(B.c)
    starts = np.nonzero(fronte)[0]
    fh, fl = frattali(B.h, B.l)
    ufh, ufl = ultimo_noto(fh), ultimo_noto(fl)

    def minimo_crescente(j: int, iL: int, L: float) -> float:
        """Ultimo minimo frattale noto alla chiusura di j, dopo L e sopra L."""
        f = ufl[j]
        return float(B.l[f]) if (f > iL and B.l[f] > L) else np.nan

    if conferma == "NESSUNA":
        for s in starts:
            iH = int(hix[s])
            seg = B.l[iH:s + 1]
            iL = iH + int(len(seg) - 1 - np.argmin(seg[::-1]))
            out.append(Segnale(int(s), int(s), float(hw[s]), iH, float(B.l[iL]), iL,
                               minimo_crescente(int(s), iL, float(B.l[iL]))))
        return out

    cand = martello(B.o, B.h, B.l, B.c) | engulfing(B.o, B.h, B.l, B.c)
    o, h, l, c, vw, em = B.o, B.h, B.l, B.c, B.vwap, B.ema
    libero = 0
    for s in starts:
        if s < libero:
            continue
        iH = int(hix[s])
        H = float(hw[s])
        L, iL = np.inf, -1
        for m in range(iH, s):          # minimo prima della barra di rilevazione
            if l[m] <= L:
                L, iL = l[m], m
        flags = set()
        cand_prev = -10
        fine_ep = n - 1
        conf = -1
        for j in range(s, n):
            if l[j] < L or iL < 0:
                L, iL = l[j], j
                flags.clear()
            elif l[j] == L:
                iL = j
            if j > s and _scaduto(B, j, iL, orizzonte):
                fine_ep = j
                break
            # --- conferme alla chiusura di j
            ok = {}
            if conferma in ("C1", "C5"):
                f = ufh[j]
                ok["C1"] = f > iH and c[j] > h[f]
            if conferma in ("C2", "C5"):
                f = ufl[j]
                ok["C2"] = (f > iL and l[f] > L and c[j] > h[iL:f + 1].max())
            if conferma in ("C3a", "C5"):
                ok["C3a"] = j > 0 and c[j] > vw[j] and c[j - 1] <= vw[j - 1]
            if conferma == "C3b":
                ok["C3b"] = j > 0 and c[j] > em[j] and c[j - 1] <= em[j - 1]
            if conferma == "C3c":
                lv = L + 0.5 * (H - L)
                ok["C3c"] = j > 0 and c[j] > lv and c[j - 1] <= lv
            if conferma in ("C4", "C5"):
                ok["C4"] = cand_prev == j - 1 and c[j] > h[j - 1]
                cand_prev = j if (l[j] <= L and cand[j]) else cand_prev
            if conferma == "C5":
                flags.update(x for x, v in ok.items() if v)
                hit = len(flags) >= 2
            else:
                hit = bool(ok[conferma])
            if hit:
                conf = j
                fine_ep = j
                break
        libero = fine_ep + 1
        if conf >= 0:
            out.append(Segnale(int(s), int(conf), H, iH, float(L), int(iL),
                               minimo_crescente(int(conf), int(iL), float(L))))
    return out


# ------------------------------------------------------------ gestione M5
def limite_uscita(t5: np.ndarray, e: int, orizzonte: str, fine_giorno=None,
                  giorno5=None) -> int:
    """Ultima M5 della tenuta (uscita alla sua chiusura); -1 = entrata vietata.

    Intraday: niente entrate 20:45-22:15 UTC; uscita al prezzo delle 20:55
    (chiusura dell'ultima M5 terminata entro le 20:55) dello stesso giorno, o
    del giorno dopo per le entrate dopo le 22:15. Swing: chiusura dell'ultima
    M5 della giornata (giorno d'entrata + 19), cioe' al massimo 20 giornate.
    """
    te = int(t5[e])
    if orizzonte == "intraday":
        tod = te % 1440
        base = te - tod
        if INTRADAY["vieta_da"] <= tod < INTRADAY["vieta_a"]:
            return -1
        tx = base + INTRADAY["chiusura"] + (1440 if tod >= INTRADAY["vieta_a"] else 0)
        lim = int(np.searchsorted(t5, tx - 5, side="right")) - 1
        return lim if lim >= e else -1
    g = int(giorno5[e]) + SWING["tenuta_giornate"] - 1
    if g >= len(fine_giorno):
        return len(t5) - 1
    return int(np.searchsorted(t5, fine_giorno[g], side="left")) - 1


def gestisci(o5, h5, l5, c5, e: int, lim: int, dz: int, stop: float, obiettivi):
    """Esiti di un'operazione per piu' obiettivi (versione vettoriale).

    Entrata all'apertura della M5 ``e``; tenuta fino alla chiusura di ``lim``.
    Ritorna liste (indice M5 d'uscita, prezzo, motivo) per ogni obiettivo:
    motivo 0 = stop, 1 = obiettivo, 2 = tempo.
    """
    ent = o5[e]
    sl = slice(e, lim + 1)
    if dz == 1:
        run_s = np.minimum.accumulate(l5[sl])
        ks = int(np.searchsorted(-run_s, -stop, side="left"))    # primo low <= stop
        run_t = np.maximum.accumulate(h5[sl])
    else:
        run_s = np.maximum.accumulate(h5[sl])
        ks = int(np.searchsorted(run_s, stop, side="left"))       # primo high >= stop
        run_t = -np.minimum.accumulate(l5[sl])
    m = lim - e + 1
    res = []
    for tg in obiettivi:
        if dz * (tg - ent) <= 0:                     # obiettivo gia' raggiunto
            res.append((e, ent, 1))
            continue
        kt = int(np.searchsorted(run_t, dz * tg, side="left"))
        if ks < m and ks <= kt:
            x = e + ks
            px = stop if ks == 0 else (min(o5[x], stop) if dz == 1 else max(o5[x], stop))
            res.append((x, px, 0))
        elif kt < m:
            res.append((e + kt, tg, 1))
        else:
            res.append((lim, c5[lim], 2))
    return res


def gestisci_barra_per_barra(o5, h5, l5, c5, e, lim, dz, stop, obiettivo):
    """Stessa gestione con un ciclo esplicito barra per barra (controllo)."""
    ent = o5[e]
    if (obiettivo - ent) * dz <= 0:
        return e, ent, 1
    x = e
    while x <= lim:
        if dz == 1:
            if x > e and o5[x] <= stop:
                return x, o5[x], 0
            if l5[x] <= stop:
                return x, stop, 0
            if h5[x] >= obiettivo:
                return x, obiettivo, 1
        else:
            if x > e and o5[x] >= stop:
                return x, o5[x], 0
            if h5[x] >= stop:
                return x, stop, 0
            if l5[x] <= obiettivo:
                return x, obiettivo, 1
        x += 1
    return lim, c5[lim], 2


def _peso_giorno(d):
    """Peso swap del giorno d (giorni dall'epoca; 1970-01-01 = giovedi')."""
    dow = (np.asarray(d) + 3) % 7          # 0 = lunedi'
    return np.where(dow >= 5, 0, np.where(dow == 2, 3, 1))


def notti_swap(t_in, t_out):
    """Notti pesate: 21:00 UTC lun-ven (mercoledi' x3) con t_in < T <= t_out."""
    def F(t):
        t = np.asarray(t, np.int64)
        d = t // 1440
        # giorni interi prima di d: 5 settimanali + 2 extra del mercoledi' per settimana
        sett, r = d // 7, d % 7
        base = sett * 7                    # peso di una settimana = 1+1+3+1+1 = 7
        # resto: giorni da giovedi' (d%7 == 0) in avanti
        parz = np.array([0, 1, 2, 2, 2, 3, 4])[r]   # gio, ven, sab, dom, lun, mar
        extra = np.where(t % 1440 >= ORA_SWAP, _peso_giorno(d), 0)
        return base + parz + extra
    return F(t_out) - F(t_in)


def esito_usd(dz, ent, px, notti, costo, molt=1.0):
    """Netto in $/oncia: lordo + swap riscalato sul prezzo - costo x molt."""
    sw = (SWAP_LONG if dz == 1 else SWAP_SHORT) * ent / SWAP_RIF * notti
    return dz * (px - ent) + sw - costo * molt


def stop_e_rischio(L_m: float, atr: float, ent: float, dz: int, modo: str = "v1",
                   F_m: float = np.nan):
    """Stop riportato ai prezzi veri e 1R = distanza entrata-stop.

    ``L_m`` e ``F_m`` (minimo frattale crescente) sono nello spazio
    specchiato (dz = -1: prezzi negati). "v1"/"S1": L - 0,1 x ATR; "S2":
    F - 0,1 x ATR se F esiste, altrimenti come S1; "S3": 1,5 x ATR
    dall'entrata.
    """
    if modo == "S3":
        stop = ent - dz * 1.5 * atr
    else:
        base = F_m if (modo == "S2" and np.isfinite(F_m)) else L_m
        stop = dz * (base - 0.1 * atr)
    return stop, dz * (ent - stop)


def rischio_valido(R: float, atr: float, costo: float, tetto: bool = True) -> bool:
    """Si scarta se 1R < 2 x costo e, con il tetto (v1), se 1R > 1,5 x ATR."""
    return ((R <= 1.5 * atr) or not tetto) and (R >= 2 * costo)


def obiettivi_prezzo(ent: float, R: float, H_m: float, dz: int) -> list[float]:
    """1R, 2R, 3R e ritorno al massimo d'inizio crollo (prezzi veri)."""
    return [ent + dz * R, ent + dz * 2 * R, ent + dz * 3 * R, dz * H_m]


def una_alla_volta(entrate: np.ndarray, uscite: np.ndarray) -> np.ndarray:
    """Maschera delle operazioni tenute con una posizione alla volta
    (entrate ordinate; si salta un'entrata finche' la precedente e' aperta)."""
    keep = np.zeros(len(entrate), bool)
    occupato = -1
    for i in range(len(entrate)):
        if entrate[i] > occupato:
            keep[i] = True
            occupato = uscite[i]
    return keep


def operazioni(segn: list[Segnale], B: Barre, m5, orizzonte: str, dz: int, costo: float,
               fine_giorno=None, giorno5=None, stop: str = "v1") -> dict:
    """Dai segnali (calcolati sulla serie gia' specchiata se dz = -1) agli esiti.

    ``m5`` = (t5, o5, h5, l5, c5) ai prezzi VERI. Ritorna array: per segnale
    ``conf, e, lim, ent, R, atr, stop`` e, con forma (n, 4) per i 4 obiettivi,
    ``obj`` (prezzo dell'obiettivo), ``x, px, mot, notti`` (direzione dz) e ``xf, pxf, motf, nottif``
    (direzione opposta, stessi istanti, stop e obiettivi specchiati: serve al
    placebo). Segnali scartati: entrata mancante o vietata, rischio fuori
    dai limiti. ``stop`` in ``STOP`` (default "v1" = protocollo v1); la
    colonna ``fr`` vale 1 se lo stop S2 usa il minimo frattale crescente.
    """
    if stop not in STOP:
        raise ValueError(stop)
    modo_stop = stop
    t5, o5, h5, l5, c5 = m5
    cols = {k: [] for k in ("conf", "e", "lim", "ent", "R", "atr", "stop", "fr", "obj", "x", "px", "mot",
                            "notti", "xf", "pxf", "motf", "nottif")}
    nb = len(B.c)
    for s in segn:
        j = s.conferma + 1
        if j >= nb:
            continue
        e = int(B.i5[j])
        lim = limite_uscita(t5, e, orizzonte, fine_giorno, giorno5)
        if lim < 0:
            continue
        atr = float(B.atr_ap[j])
        ent = float(o5[e])
        stop, R = stop_e_rischio(s.L, atr, ent, dz, modo_stop, s.F)
        if not np.isfinite(R) or not rischio_valido(R, atr, costo, modo_stop == "v1"):
            continue
        obj = obiettivi_prezzo(ent, R, s.H, dz)
        es = gestisci(o5, h5, l5, c5, e, lim, dz, stop, obj)
        objf = [2 * ent - v for v in obj]
        esf = gestisci(o5, h5, l5, c5, e, lim, -dz, 2 * ent - stop, objf)
        for nome, v in (("conf", s.conferma), ("e", e), ("lim", lim), ("ent", ent), ("R", R),
                        ("atr", atr), ("stop", stop),
                        ("fr", int(modo_stop == "S2" and np.isfinite(s.F)))):
            cols[nome].append(v)
        cols["obj"].append(obj)
        cols["x"].append([r[0] for r in es])
        cols["px"].append([r[1] for r in es])
        cols["mot"].append([r[2] for r in es])
        cols["notti"].append(notti_swap(t5[e], t5[[r[0] for r in es]]))
        cols["xf"].append([r[0] for r in esf])
        cols["pxf"].append([r[1] for r in esf])
        cols["motf"].append([r[2] for r in esf])
        cols["nottif"].append(notti_swap(t5[e], t5[[r[0] for r in esf]]))
    out = {}
    for k, v in cols.items():
        if k in ("obj", "x", "px", "mot", "notti", "xf", "pxf", "motf", "nottif"):
            out[k] = np.array(v, dtype=float).reshape(-1, 4)
        else:
            out[k] = np.array(v, dtype=float)
    for k in ("conf", "e", "lim", "fr", "x", "mot", "notti", "xf", "motf", "nottif"):
        out[k] = out[k].astype(np.int64)
    return out
