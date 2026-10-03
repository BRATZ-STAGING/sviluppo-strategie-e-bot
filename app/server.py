#!/usr/bin/env python3
"""Grafico XAUUSD simil TradingView: server locale.

Avvio:  python app/server.py [--mt5]     poi  http://127.0.0.1:8095

- candele dall'archivio M1 del repository (Dukascopy, BID, UTC) per M1..D1,
  caricate a pezzi di un anno solo quando servono (la RAM del PC e' poca)
- con --mt5: ultime settimane dal terminale MT5 (ora del server del
  broker riportata a UTC, come in trading/scripts/grafico_live.py)
- disegni salvati in app/dati/disegni.json
- risultati di backtest gia' calcolati: elenco in app/backtest/catalogo.json

Solo libreria standard + pandas/pyarrow: sul VPS c'e' Python 3.12 e nient'altro.
Ascolta su 127.0.0.1: non va esposto su internet senza autenticazione
(docs/piano-app.md).
"""
from __future__ import annotations

import glob
import json
import multiprocessing
import os
import sys
import threading
import time
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(QUI)
ARCHIVIO = os.environ.get("APP_ARCHIVIO", os.path.join(ROOT, "data", "XAUUSD_M1"))
STATIC = os.path.join(QUI, "static")
DATI = os.path.join(QUI, "dati")
CATALOGO = os.path.join(QUI, "backtest", "catalogo.json")
PORTA = int(os.environ.get("APP_PORTA", "8095"))
# acceso solo su richiesta: mt5.initialize() AVVIA il terminale se e' chiuso
USA_MT5 = "--mt5" in sys.argv or os.environ.get("APP_MT5") == "1"
BARRE_MT5 = 60_000          # ~6 settimane di minuti dal terminale
OGNI_MT5 = 3.0              # secondi fra due letture del terminale

TF = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
      "H1": "1h", "H4": "4h", "D1": "1D"}
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}

_lock = threading.Lock()
_vivo = {"m1": None, "simbolo": None, "errore": None, "ora": None}


# ------------------------------------------------------------------ candele
def anni_archivio() -> list[int]:
    return sorted(int(os.path.basename(f)[10:14])
                  for f in glob.glob(os.path.join(ARCHIVIO, "XAUUSD_M1_*.parquet")))


@lru_cache(maxsize=3)
def m1_anno(anno: int) -> pd.DataFrame:
    d = pd.read_parquet(os.path.join(ARCHIVIO, f"XAUUSD_M1_{anno}.parquet"))
    if "timestamp" in d.columns:
        d = d.set_index("timestamp")
    d.index = pd.to_datetime(d.index, utc=True)
    if "volume" not in d.columns:
        d["volume"] = 0.0
    return d[["open", "high", "low", "close", "volume"]].sort_index()


def ricampiona(m1: pd.DataFrame, tf: str) -> pd.DataFrame:
    if tf == "M1":
        return m1
    if tf == "D1":
        # lo spezzone della domenica sera va nel lunedi': contarlo come giornata
        # a se' crea una D1 monca ogni settimana (bug noto, CLAUDE.md)
        giorno = m1.index.normalize()
        giorno = giorno.where(giorno.dayofweek != 6, giorno + pd.Timedelta(days=1))
        return m1.groupby(giorno).agg(AGG)
    return m1.resample(TF[tf]).agg(AGG).dropna(subset=["open"])


@lru_cache(maxsize=16)
def barre_anno(tf: str, anno: int) -> pd.DataFrame:
    return ricampiona(m1_anno(anno), tf)


def barre_vive(tf: str):
    with _lock:
        m1 = _vivo["m1"]
    if m1 is None or m1.empty:
        return None, None
    # il terminale prende il posto dell'archivio da mezzanotte del suo primo
    # giorno intero: una giornata a meta' fra due fonti non ha senso
    confine = m1.index[0].normalize() + pd.Timedelta(days=1)
    return ricampiona(m1[m1.index >= confine], tf), confine


def barre_prima(tf: str, prima: pd.Timestamp | None, n: int):
    """Le ultime n candele con apertura < prima (tutte le piu' recenti se None)."""
    vive, confine = barre_vive(tf)
    pezzi, quante = [], 0
    if vive is not None:
        v = vive if prima is None else vive[vive.index < prima]
        pezzi.append(v)
        quante += len(v)
        limite = confine if prima is None else min(prima, confine)
    else:
        limite = prima
    anni = anni_archivio()
    if limite is not None:
        anni = [a for a in anni if a <= limite.year]
    for a in reversed(anni):
        if quante >= n:
            break
        b = barre_anno(tf, a)
        if limite is not None:
            b = b[b.index < limite]
        pezzi.append(b)
        quante += len(b)
    if not pezzi:
        return pd.DataFrame(columns=list(AGG)), False
    tutto = pd.concat(pezzi[::-1]).sort_index()
    tutto = tutto[~tutto.index.duplicated(keep="last")]
    if tutto.empty:
        return tutto, False
    altre = len(tutto) > n or any(a < tutto.index[0].year for a in anni_archivio())
    return tutto.iloc[-n:], altre


def in_ms(t) -> int:
    return int(pd.Timestamp(t).timestamp() * 1000)


def in_json(b: pd.DataFrame) -> list[dict]:
    ts = ((b.index - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(milliseconds=1)).tolist()
    cols = [b[c].round(3).tolist() for c in ("open", "high", "low", "close", "volume")]
    return [{"timestamp": t, "open": o, "high": h, "low": l, "close": c, "volume": v}
            for t, o, h, l, c, v in zip(ts, *cols)]


# ---------------------------------------------------------------------- MT5
def scarto_server(tick) -> int:
    """Di quante ore l'orologio del broker e' avanti rispetto a UTC."""
    quando = pd.Timestamp(int(tick.time), unit="s", tz="UTC")
    ore = (quando - pd.Timestamp.now("UTC")).total_seconds() / 3600
    scarto = int(round(ore))
    if abs(scarto) > 14:
        raise RuntimeError(f"ora del terminale incoerente con quella di sistema ({ore:+.1f} h)")
    return scarto


def leggi_mt5(quante: int):
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise RuntimeError(f"MT5 non risponde: {mt5.last_error()}")
    try:
        nomi = [s.name for s in mt5.symbols_get()
                if "XAU" in s.name.upper() or "GOLD" in s.name.upper()]
        if not nomi:
            raise RuntimeError("nessun simbolo XAU/GOLD presso questo broker")
        simbolo = "XAUUSD" if "XAUUSD" in nomi else nomi[0]
        mt5.symbol_select(simbolo, True)
        barre = mt5.copy_rates_from_pos(simbolo, mt5.TIMEFRAME_M1, 0, quante)
        tick = mt5.symbol_info_tick(simbolo)
    finally:
        mt5.shutdown()
    if barre is None or len(barre) == 0:
        raise RuntimeError("il terminale non ha restituito barre M1")
    df = pd.DataFrame(barre)
    df.index = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df[["open", "high", "low", "close", "tick_volume"]].astype("float64")
    df.columns = ["open", "high", "low", "close", "volume"]
    # MT5 da' l'ora del SERVER del broker, non UTC (FP: UTC+3)
    if tick is not None:
        df.index = df.index - pd.Timedelta(hours=scarto_server(tick))
    return simbolo, df


def lettore_mt5(coda):
    """Gira in un PROCESSO a parte: la libreria MetaTrader5 tiene bloccato
    l'interprete mentre aspetta il terminale (fino a 60 s con "IPC timeout"),
    e in un thread fermerebbe anche il server web."""
    primo = True
    while True:
        try:
            simbolo, df = leggi_mt5(BARRE_MT5 if primo else 500)
            coda.put(("ok", simbolo, df))
            primo = False
            time.sleep(OGNI_MT5)
        except Exception as e:  # terminale chiuso, non collegato, libreria assente...
            coda.put(("errore", None, str(e)))
            time.sleep(30)


def ricevi_mt5(coda):
    while True:
        esito, simbolo, dato = coda.get()
        with _lock:
            if esito != "ok":
                _vivo["errore"] = dato
                continue
            vecchio = _vivo["m1"]
            if vecchio is not None:
                dato = pd.concat([vecchio, dato])
                dato = dato[~dato.index.duplicated(keep="last")].sort_index().iloc[-BARRE_MT5:]
            _vivo.update(m1=dato, simbolo=simbolo, errore=None, ora=time.time())


# ----------------------------------------------------------------- disegni
def leggi_disegni() -> list:
    f = os.path.join(DATI, "disegni.json")
    if not os.path.exists(f):
        return []
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


def scrivi_disegni(lista: list):
    os.makedirs(DATI, exist_ok=True)
    f = os.path.join(DATI, "disegni.json")
    tmp = f + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(lista, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, f)   # mai un file a meta' se il processo muore


# ----------------------------------------------------------------- backtest
def catalogo() -> list[dict]:
    if not os.path.exists(CATALOGO):
        return []
    with open(CATALOGO, encoding="utf-8") as fh:
        return json.load(fh)


def carica_backtest(voce: dict) -> dict:
    """Operazioni nel formato comune; colonne minime: time, lato, entry.

    Facoltative: stop, target, exit_time, exit_price, R. Se R manca ma ci sono
    uscita e stop, si calcola; se mancano entrambi, il riepilogo resta vuoto.
    """
    f = os.path.join(ROOT, voce["file"])
    d = pd.read_parquet(f) if f.endswith(".parquet") else pd.read_csv(f)
    d["time"] = pd.to_datetime(d["time"], utc=True)
    if "exit_time" in d:
        d["exit_time"] = pd.to_datetime(d["exit_time"], utc=True)
    segno = np.where(d["lato"].str.lower().str.startswith("l"), 1.0, -1.0)
    if "R" not in d and {"exit_price", "stop"} <= set(d):
        d["R"] = segno * (d["exit_price"] - d["entry"]) / (d["entry"] - d["stop"]).abs()
    if "target" not in d and "stop" in d and voce.get("rr"):
        d["target"] = d["entry"] + segno * (d["entry"] - d["stop"]).abs() * float(voce["rr"])
    ops = []
    for r in d.itertuples(index=False):
        op = {"t": in_ms(r.time), "lato": r.lato, "entry": float(r.entry)}
        for c in ("stop", "target", "exit_price", "R"):
            v = getattr(r, c, None)
            if v is not None and pd.notna(v):
                op[c] = round(float(v), 3)
        v = getattr(r, "exit_time", None)
        if v is not None and pd.notna(v):
            op["t_uscita"] = in_ms(v)
        ops.append(op)
    riep = {"operazioni": len(d), "dal": str(d["time"].min().date()), "al": str(d["time"].max().date())}
    if "R" in d:
        riep.update(R_totale=round(float(d["R"].sum()), 1),
                    R_medio=round(float(d["R"].mean()), 3),
                    vinte=round(float((d["R"] > 0).mean()), 3),
                    per_anno={str(a): round(float(v), 1)
                              for a, v in d.groupby(d["time"].dt.year)["R"].sum().items()})
    return {"voce": voce, "riepilogo": riep, "operazioni": ops}


# ------------------------------------------------------------------- server
TIPI = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def manda(self, corpo: bytes, tipo: str, codice: int = 200):
        self.send_response(codice)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def json(self, obj, codice: int = 200):
        self.manda(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8", codice)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/candele":
                tf = q.get("tf", "M5")
                if tf not in TF:
                    return self.json({"errore": f"timeframe sconosciuto: {tf}"}, 400)
                prima = pd.Timestamp(int(q["prima"]), unit="ms", tz="UTC") if q.get("prima") else None
                n = min(int(q.get("n", 1000)), 5000)
                b, altre = barre_prima(tf, prima, n)
                return self.json({"barre": in_json(b), "altre": altre})
            if u.path == "/api/stato":
                with _lock:
                    m1 = _vivo["m1"]
                    stato = {"mt5": USA_MT5, "simbolo": _vivo["simbolo"], "errore": _vivo["errore"],
                             "vivo_dal": str(m1.index[0]) if m1 is not None else None,
                             "vivo_al": str(m1.index[-1]) if m1 is not None else None}
                anni = anni_archivio()
                stato["archivio"] = f"{anni[0]}-{anni[-1]}" if anni else None
                if anni:
                    stato["archivio_al"] = str(m1_anno(anni[-1]).index[-1])
                return self.json(stato)
            if u.path == "/api/disegni":
                return self.json(leggi_disegni())
            if u.path == "/api/backtest":
                return self.json([{"id": v["id"], "nome": v["nome"]} for v in catalogo()])
            if u.path.startswith("/api/backtest/"):
                voce = next((v for v in catalogo() if v["id"] == u.path.rsplit("/", 1)[1]), None)
                if voce is None:
                    return self.json({"errore": "backtest sconosciuto"}, 404)
                return self.json(carica_backtest(voce))
            return self.statico(u.path)
        except Exception as e:
            return self.json({"errore": f"{type(e).__name__}: {e}"}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/disegni":
            return self.json({"errore": "non trovato"}, 404)
        try:
            corpo = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            lista = json.loads(corpo)
            if not isinstance(lista, list):
                raise ValueError("serve un elenco")
            scrivi_disegni(lista)
            return self.json({"salvati": len(lista)})
        except Exception as e:
            return self.json({"errore": str(e)}, 400)

    def statico(self, percorso: str):
        if percorso in ("", "/"):
            percorso = "/index.html"
        f = os.path.normpath(os.path.join(STATIC, percorso.lstrip("/")))
        if not f.startswith(STATIC + os.sep) or not os.path.isfile(f):
            return self.json({"errore": "non trovato"}, 404)
        with open(f, "rb") as fh:
            self.manda(fh.read(), TIPI.get(os.path.splitext(f)[1], "application/octet-stream"))


def main():
    if USA_MT5:
        coda = multiprocessing.Queue()
        multiprocessing.Process(target=lettore_mt5, args=(coda,), daemon=True).start()
        threading.Thread(target=ricevi_mt5, args=(coda,), daemon=True).start()
        with _lock:
            _vivo["errore"] = "in attesa del terminale (fino a un minuto)"
    srv = ThreadingHTTPServer(("127.0.0.1", PORTA), Handler)
    print(f"grafico su http://127.0.0.1:{PORTA}  (archivio: {ARCHIVIO}, MT5: {'si' if USA_MT5 else 'no'})",
          flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
