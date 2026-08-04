#!/usr/bin/env python3
"""Grafico LIVE da MT5, con i livelli del progetto disegnati sopra.

Quello che Dukascopy non puo' dare: il prezzo in tempo reale. Legge il
terminale MT5 aperto (stesso flusso che vede il broker), calcola a ogni
aggiornamento le zone order block, lo stato della struttura e il VWAP
giornaliero, e serve una pagina che si ridisegna da sola.

    python3 grafico_live.py            poi apri http://127.0.0.1:8765
    python3 grafico_live.py 9000       su un'altra porta

Sul VPS la porta 8080 e' occupata: usarne un'altra e aprirla nel firewall
solo se serve accedervi da fuori (altrimenti resta su 127.0.0.1, piu' sicuro).

Le zone mostrate sono quelle misurate: la RAFFINATA e' la parte che porta il
vantaggio (appendice AJ, +1,342 R/op su sette anni). Una zona NON e' un
segnale da sola (appendice W) e non va usata come ordine limite in attesa
(appendice AA): serve il segnale della strategia con la struttura concorde.
"""
import glob
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from framework.data import TIMEFRAMES, load_m1, resample_tf       # noqa: E402
from framework.segnali import filtro_macro, genera                # noqa: E402
from framework.structure import state_at, trend_state_series      # noqa: E402
from framework.taratura import UFFICIALE as T                     # noqa: E402
from framework.volatility import (atr_at, daily_atr,              # noqa: E402
                                  high_volatility_months)
from framework.vwap import anchored_vwap                          # noqa: E402

from export_lab import zone_ob                                    # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

TF_ZONE = ["M6", "M12", "M33", "M66", "H2", "H3", "H6", "H12"]
VALIDITA = 30              # candele di vita di una zona, come negli studi
BARRE_M1 = 60_000          # ~6 settimane dal terminale: basta per zone e struttura
MESI_STORIA = 15           # mesi di archivio da anteporre, per il contesto
AGGIORNA = 3.0             # secondi fra un ricalcolo e l'altro
SEGNALI_OGNI = 300         # secondi fra due ricalcoli dei segnali passati
SEGNALI_MAX = 60           # quanti segnali passati tenere

_dati = {"pronto": False, "errore": "in attesa del primo aggiornamento"}
_lock = threading.Lock()
_serie = {"m1": None}      # ultima serie unita, per il calcolo dei segnali
_segnali = {"elenco": [], "ora": None, "errore": None}


def storico_archivio():
    """Gli ultimi mesi dell'archivio, per dare CONTESTO al calcolo dal vivo.

    Il terminale da' sei settimane di minuti: bastano per zone e struttura,
    non per il resto. Il filtro di fondo vuole 50 giornate D1, l'ATR ne vuole
    14, e il riconoscimento dei mesi ad alta volatilita' ne pretende 250 prima
    di rispondere qualcosa di diverso da "normale". Senza questo pezzo di
    archivio il grafico mostrerebbe segnali calcolati con regole piu' blande
    di quelle degli studi, che e' il modo migliore per fidarsi di un numero
    sbagliato.
    """
    cartella = os.path.join(ROOT, "data", "XAUUSD_M1")
    if not os.path.isdir(cartella):
        return None, None
    anni = sorted(int(os.path.basename(f)[10:14])
                  for f in glob.glob(os.path.join(cartella, "XAUUSD_M1_*.parquet")))
    if not anni:
        return None, None
    try:
        d = load_m1(cartella, years=anni[-2:])
    except Exception:
        return None, None
    # La mediana ATR di riferimento va presa dagli ANNI DI CALIBRAZIONE, che
    # negli ultimi quindici mesi non ci sono: senza, nei mesi ad alta
    # volatilita' le soglie riscalate diventerebbero NaN e non uscirebbe piu'
    # nessun segnale, in silenzio.
    mediana = mediana_calibrazione(cartella)
    taglio = d.index[-1] - pd.DateOffset(months=MESI_STORIA)
    return d[d.index >= taglio], mediana


def mediana_calibrazione(cartella):
    """La mediana dell'ATR giornaliero sugli anni di calibrazione."""
    try:
        d = load_m1(cartella, years=list(range(T.calibrazione[0],
                                               T.calibrazione[1] + 1)))
    except Exception:
        return None
    a = daily_atr(d, 14)
    m = float(a.median())
    return m if np.isfinite(m) and m > 0 else None


def unisci(storia, vivo):
    """Archivio davanti, terminale dietro, con il taglio su un confine di GIORNO.

    Tagliare sul primo minuto del terminale spezzerebbe una giornata fra due
    fonti, e il volume non e' la stessa cosa nelle due: conteggio di tick da
    MT5, decimale nell'archivio. Il VWAP e' pesato sui volumi e ancorato alla
    giornata, quindi una giornata mista darebbe un VWAP senza senso. Si taglia
    percio' a mezzanotte: l'archivio arriva fino alla fine dell'ultimo giorno
    intero che precede i dati del terminale.

    Ritorna anche i giorni di buco fra le due fonti: se ce ne sono, il filtro
    di fondo a 50 giornate e l'ATR stanno contando giornate che non ci sono, e
    chi guarda il grafico deve saperlo.
    """
    if storia is None or storia.empty:
        return vivo, None
    confine = vivo.index[0].normalize()
    pezzo = storia[storia.index < confine]
    if pezzo.empty:
        return vivo, None
    buco = (confine - pezzo.index[-1].normalize()).days - 1
    unito = pd.concat([pezzo[vivo.columns], vivo])
    unito = unito[~unito.index.duplicated(keep="last")].sort_index()
    return unito, max(buco, 0)


def leggi_mt5():
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
        barre = mt5.copy_rates_from_pos(simbolo, mt5.TIMEFRAME_M1, 0, BARRE_M1)
        tick = mt5.symbol_info_tick(simbolo)
    finally:
        mt5.shutdown()
    if barre is None or len(barre) == 0:
        raise RuntimeError("il terminale non ha restituito barre M1")
    df = pd.DataFrame(barre)
    df["ts"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("ts")[["open", "high", "low", "close", "tick_volume"]]
    df.columns = ["open", "high", "low", "close", "volume"]
    bid = float(tick.bid) if tick else float(df.close.iloc[-1])
    ask = float(tick.ask) if tick else bid
    return simbolo, df, bid, ask


def vwap_motore(m1):
    """Il VWAP come lo calcola ``segnali.genera``: sulle candele di ingresso.

    Indicizzato per ORA DI CHIUSURA della candela, cosi' leggerlo a un istante
    qualunque con un ffill da' il valore che era noto in quel momento — e non
    uno che comprende candele non ancora finite.
    """
    base = resample_tf(m1, T.tf_ingresso)
    v = anchored_vwap(base, "day")
    v.index = base.index + pd.Timedelta(TIMEFRAMES[T.tf_ingresso])
    return v


def leggi_vwap(v, quando):
    """Il VWAP noto a un dato istante (l'ultima candela chiusa)."""
    s = v.reindex(pd.DatetimeIndex(quando), method="ffill")
    return s


def soglie_ora(m1, barra, mediana=None):
    """Le soglie vigenti adesso, con lo stesso conto che fa ``segnali.genera``.

    Nei mesi riconosciuti ad alta volatilita' le soglie non restano in dollari
    ma seguono l'ATR, rapportate alla mediana del periodo di calibrazione. Il
    riconoscimento e' causale (finestra espansiva sul passato) e chiede almeno
    250 giornate di storia: sotto quella soglia risponde "normale".
    """
    atr = daily_atr(m1, 14)
    if mediana is None:
        anni = ((atr.index.year >= T.calibrazione[0])
                & (atr.index.year <= T.calibrazione[1]))
        mediana = float(atr[anni].median()) if anni.any() else float("nan")
    mese = pd.Period(barra.strftime("%Y-%m"), "M")
    alta = high_volatility_months(atr, [mese], T.fattore_alta_volatilita)[mese]
    if not alta:
        return T.soglie(), False, True
    u = atr_at(atr, pd.DatetimeIndex([barra])).iloc[0]
    if not np.isfinite(mediana) or mediana <= 0 or not np.isfinite(u) or u <= 0:
        # senza riferimento il motore non produrrebbe NIENTE questo mese: il
        # pannello deve dirlo, non ripiegare di nascosto sulle soglie fisse
        return T.soglie(), True, False
    return T.soglie(atr=float(u), mediana=mediana), True, True


def condizioni_ora(m1, vwap_m1, stati_tf, adesso, mediana=None, segnali=()):
    """Le cinque condizioni della strategia, adesso, per i due lati.

    Si valutano sull'ultima candela M6 CHIUSA: quella in corso cambierebbe
    idea a ogni tick e non e' su quella che si decide. E' lo stesso conto che
    fa ``segnali.genera``, rifatto qui su una sola barra perche' rigenerare
    tutta la storia a ogni aggiornamento costerebbe mezzo minuto.
    """
    m6 = resample_tf(m1, T.tf_ingresso)
    if len(m6) < 3:
        return None
    passo = pd.Timedelta(TIMEFRAMES[T.tf_ingresso])
    # l'ultima candela CHIUSA si sceglie per orario, non per posizione: nel
    # minuto in cui una candela si chiude, quella dopo non esiste ancora nel
    # terminale (nasce al primo tick), quindi l'indice -2 punterebbe indietro
    # di una candela e il pannello mancherebbe il segnale appena formato
    chiusi = np.flatnonzero((m6.index + passo) <= adesso)
    if len(chiusi) < 2:
        return None
    i = int(chiusi[-1])
    barra = m6.index[i]
    giorno = barra.normalize()
    v = float(leggi_vwap(vwap_m1, [barra + passo]).iloc[0])
    if not np.isfinite(v):
        return None
    # gli stati si leggono all'ISTANTE DELLA DECISIONE, non all'ora corrente:
    # M33 non e' un multiplo di M6, quindi puo' cambiare stato nei minuti fra
    # la chiusura della barra e adesso, e il pannello direbbe una cosa che al
    # momento della decisione non era vera
    struttura = leggi_stati(stati_tf, barra + passo)
    macro = filtro_macro(m1, T.media_macro).get(giorno, None)
    del_giorno = m6[m6.index.normalize() == giorno]
    prima = del_giorno[del_giorno.index < barra]
    hi, lo, cl = m6.high.values, m6.low.values, m6.close.values
    # le soglie NON sono sempre in dollari: nei mesi ad alta volatilita' il
    # motore le riscala sull'ATR. Un pannello che mostrasse sempre 4,00 $
    # direbbe "manca ancora" mentre il motore ha gia' aperto, o il contrario
    soglie, alta, tarabile = soglie_ora(m1, barra, mediana)
    # l'orario si valuta sull'APERTURA della barra decisionale, come fa il
    # motore: guardare l'orologio sposterebbe la finestra di sei minuti e la
    # barra 18:54, che la strategia accetta, non comparirebbe mai
    ora_ok = bool(T.ora_inizio <= barra.hour < T.ora_fine)
    quante_oggi, ultimo = conteggio_giorno(segnali, giorno, barra + passo)
    attesa_ok = ultimo is None or (barra + passo - ultimo
                                   >= pd.Timedelta(minutes=T.attesa_minuti))
    fuori = {"vwap": round(v, 2), "candela": barra.strftime("%d/%m %H:%M"),
             "ora_ok": ora_ok, "alta_volatilita": bool(alta),
             "tarabile": bool(tarabile), "oggi": quante_oggi,
             "max_giorno": T.max_operazioni_giorno, "attesa_ok": bool(attesa_ok),
             "chiusura": T.ora_chiusura, "lati": {}}
    for nome, segno in (("long", 1), ("short", -1)):
        if segno == 1:
            tocca = bool(lo[i] <= v and cl[i] > v and cl[i] > hi[i - 1])
            spinta = float(prima.high.max() - v) if len(prima) else 0.0
        else:
            tocca = bool(hi[i] >= v and cl[i] < v and cl[i] < lo[i - 1])
            spinta = float(v - prima.low.min()) if len(prima) else 0.0
        strut = all(struttura.get(tf, 0) == segno for tf in T.tf_struttura)
        conf = all(struttura.get(tf, 0) == segno for tf in T.conferme)
        # il motore chiede che il ritracciamento NON sia allineato, non che sia
        # per forza contrario: uno stato neutro va bene
        ritr = all(struttura.get(tf, 0) != segno for tf in T.ritracciamento)
        # lo stop e' strutturale e il rischio deve stare nella banda, altrimenti
        # il motore scarta l'operazione anche con tutto il resto a posto
        j0 = max(0, i - T.barre_stop)
        finestra = [k for k in range(j0, i + 1)
                    if m6.index[k].normalize() == giorno] or [i]
        if segno == 1:
            stop = float(min(lo[k] for k in finestra) - soglie["buffer"])
            rischio = float(cl[i]) - stop
        else:
            stop = float(max(hi[k] for k in finestra) + soglie["buffer"])
            rischio = stop - float(cl[i])
        rischio_ok = bool(soglie["rischio_min"] <= rischio <= soglie["rischio_max"])
        fuori["lati"][nome] = {
            "struttura": bool(strut), "conferme": bool(conf),
            "ritracciamento": bool(ritr),
            "macro": None if macro is None else bool(macro == (segno == 1)),
            "reclaim": tocca, "spinta": round(spinta, 2),
            "spinta_ok": bool(spinta >= soglie["impulso"]),
            "soglia": round(soglie["impulso"], 2),
            "stop": round(stop, 2), "rischio": round(rischio, 2),
            "rischio_ok": rischio_ok,
            "banda": [round(soglie["rischio_min"], 2),
                      round(soglie["rischio_max"], 2)],
            "pronto": bool(ora_ok and tarabile and attesa_ok
                           and quante_oggi < T.max_operazioni_giorno
                           and strut and conf and ritr and tocca and rischio_ok
                           and spinta >= soglie["impulso"]
                           and macro == (segno == 1))}
    return fuori


def leggi_stati(stati_tf, quando):
    """Lo stato di ogni timeframe vigente a un dato istante."""
    fuori = {}
    for tf, serie in stati_tf.items():
        if isinstance(serie, pd.Series):
            fuori[tf] = int(state_at(serie, pd.DatetimeIndex([quando]))[0])
        else:
            fuori[tf] = int(serie)          # gia' uno stato, per i test
    return fuori


def conteggio_giorno(segnali, giorno, entro):
    """Quante operazioni oggi PRIMA di ``entro``, e quando e' stata l'ultima.

    Il taglio su ``entro`` non e' pignoleria: contare anche i segnali
    successivi farebbe risultare la quota gia' esaurita e l'attesa gia'
    violata, e il pannello resterebbe spento per sempre.
    """
    fine = giorno + pd.Timedelta(days=1)
    tempi = [pd.Timestamp(s["t"], unit="ms", tz="UTC") for s in segnali]
    oggi = [t for t in tempi if giorno <= t < fine and t < entro]
    return len(oggi), (max(oggi) if oggi else None)


# Cosa vale ciascuna famiglia, secondo le misure: e' l'unica cosa che
# distingue una confluenza su cui si entra da una che e' solo contesto.
PESO = {
    "ob raffinato": ("voto", "l'unica che abbia mai mostrato un vantaggio "
                             "(non regge sui 18 anni, appendice BA)"),
    "ob pieno": ("contesto", "fuori dalla parte raffinata vale quanto niente"),
    "poc ieri": ("contesto", "nessun vantaggio misurato (appendice AZ)"),
    "area valore": ("contesto", "nessun vantaggio misurato (appendice AZ)"),
    "vuoto ieri": ("contesto", "nessun vantaggio misurato (appendice AZ)"),
}


def livelli_di_ieri(m1, atr):
    """POC, estremi dell'area di valore e vuoti della giornata precedente."""
    giorni = m1.index.normalize()
    unici = giorni.unique()
    if len(unici) < 2 or not np.isfinite(atr) or atr <= 0:
        return []
    # non basta "il giorno prima": il lunedi' sarebbe la domenica, che ha solo
    # lo spezzone serale. Si prende l'ultima sessione PIENA prima di oggi.
    d = None
    for g in unici[-2::-1]:
        pezzo = m1[giorni == g]
        if len(pezzo) >= 200:
            d = pezzo
            break
    if d is None:
        return []
    passo = atr * 0.05
    tipico = ((d.high + d.low + d.close) / 3).values
    vol = d.volume.values.astype(float)
    vol[~np.isfinite(vol) | (vol <= 0)] = 1.0
    liv = np.round(tipico / passo).astype(np.int64)
    unici_l, inv = np.unique(liv, return_inverse=True)
    somme = np.zeros(len(unici_l))
    np.add.at(somme, inv, vol)
    prezzi = unici_l * passo
    ordine = np.argsort(somme)[::-1]
    dentro = prezzi[ordine[:np.searchsorted(np.cumsum(somme[ordine]),
                                            .7 * somme.sum()) + 1]]
    fuori = [("poc ieri", float(prezzi[somme.argmax()]), float(prezzi[somme.argmax()])),
             ("area valore", float(dentro.min()), float(dentro.min())),
             ("area valore", float(dentro.max()), float(dentro.max()))]
    soglia = somme.max() * .15
    ini = None
    for i, p in enumerate(prezzi):
        basso = somme[i] < soglia
        if basso and ini is None:
            ini = float(p)
        if not basso and ini is not None:
            if prezzi[i - 1] - ini >= atr * .10:
                fuori.append(("vuoto ieri", ini, float(prezzi[i - 1])))
            ini = None
    return fuori


def confluenze_ora(bid, zone, ieri, atr):
    """I livelli vicini al prezzo adesso, con quanto valgono davvero.

    Risponde alla domanda "con quali confluenze si entra": la risposta
    misurata e' che NESSUNA apre un'operazione da sola (appendice AZ, 720
    configurazioni, zero sopravvissuti). Qui si dice cosa c'e' intorno e come
    va pesato, non si inventa un segnale che i numeri non sostengono.
    """
    if not np.isfinite(atr) or atr <= 0:
        return None
    vicino = atr * 0.5
    vicini = []
    for z in zone:
        for tipo, b, t in (("ob raffinato", z["rbasso"], z["ralto"]),
                           ("ob pieno", z["basso"], z["alto"])):
            if b is None or t is None:
                continue
            d = 0.0 if b <= bid <= t else (b - bid if bid < b else bid - t)
            if abs(d) <= vicino:
                vicini.append({"famiglia": tipo, "tf": z["tf"], "lato": z["lato"],
                               "da": round(b, 2), "a": round(t, 2),
                               "dist": round(d, 2), "dist_atr": round(d / atr, 2)})
                break                       # la raffinata batte la piena
    for fam, b, t in ieri:
        d = 0.0 if b <= bid <= t else (b - bid if bid < b else bid - t)
        if abs(d) <= vicino:
            vicini.append({"famiglia": fam, "tf": "D1", "lato": 0,
                           "da": round(b, 2), "a": round(t, 2),
                           "dist": round(d, 2), "dist_atr": round(d / atr, 2)})
    vicini.sort(key=lambda x: abs(x["dist"]))
    for v in vicini:
        v["peso"], v["perche"] = PESO.get(v["famiglia"], ("contesto", ""))
    return {"atr": round(float(atr), 2), "raggio": round(vicino, 2),
            "vicini": vicini,
            "voti": sum(1 for v in vicini if v["peso"] == "voto"),
            "contesto": sum(1 for v in vicini if v["peso"] == "contesto")}


def aggiorna_segnali(mediana=None):
    """Ricalcola i segnali passati, in disparte dal ciclo dei tre secondi.

    ``genera`` ripercorre tutta la serie: su quindici mesi di minuti sono
    decine di secondi, troppo per il ciclo veloce. Qui gira per conto suo e
    deposita il risultato; il pannello delle condizioni, che e' quello che
    serve per operare adesso, resta invece aggiornato a ogni giro.
    """
    while True:
        with _lock:
            m1 = _serie["m1"]
        if m1 is not None and len(m1) > 5000:
            try:
                ops = genera(m1, T, mediana_atr=mediana)
                elenco = []
                for o in ops[-SEGNALI_MAX * 4:]:
                    ufficiale = (all(o[f"c_{tf}"] for tf in T.conferme)
                                 and all(not o[f"c_{tf}"] for tf in T.ritracciamento))
                    elenco.append({
                        "t": int(pd.Timestamp(o["time"]).timestamp() * 1000),
                        "lato": 1 if o["lato"] == "long" else -1,
                        "entry": round(o["entry"], 2), "stop": round(o["stop"], 2),
                        "obiettivo": round(
                            o["entry"] + (o["entry"] - o["stop"]) * T.obiettivo, 2),
                        "rischio": round(o["rischio"], 2),
                        "ufficiale": bool(ufficiale),
                        "quando": pd.Timestamp(o["time"]).strftime("%d/%m %H:%M")})
                with _lock:
                    _segnali["elenco"] = elenco[-SEGNALI_MAX:]
                    _segnali["ora"] = pd.Timestamp.now("UTC").strftime("%H:%M")
                    _segnali["errore"] = None
            except Exception as e:
                with _lock:
                    _segnali["errore"] = str(e)
        time.sleep(SEGNALI_OGNI)


def calcola(storia, mediana):
    simbolo, vivo, bid, ask = leggi_mt5()
    m1, buco = unisci(storia, vivo)
    with _lock:
        _serie["m1"] = m1
    out = {"simbolo": simbolo, "bid": bid, "ask": ask,
           "spread": round(ask - bid, 3),
           "ora": pd.Timestamp.now("UTC").strftime("%H:%M:%S"),
           "ultima_candela": vivo.index[-1].strftime("%d/%m %H:%M"),
           "storia_da": m1.index[0].strftime("%d/%m/%Y"), "buco": buco,
           "serie": {}, "zone": [], "struttura": {}, "pronto": True}
    # Il VWAP e' quello del MOTORE: ancorato alla giornata e calcolato sulle
    # candele M6, non sui minuti. Sono due linee diverse — pesi diversi — e la
    # decisione si prende su quella di M6, quindi e' quella che va disegnata.
    # Letta alla chiusura di ogni candela resta comunque identica su ogni
    # grafico, che era il motivo per cui la si calcolava una volta sola.
    vwap_m1 = vwap_motore(m1)
    # M1 non serve a operare (l'ingresso e' su M6): serve a vedere con
    # precisione dove sta il prezzo adesso rispetto a un livello
    for tf in ("M1", "M6", "M12", "M33", "M66", "H2", "H3", "H6"):
        s = resample_tf(m1, tf).tail(600)
        passo = pd.Timedelta(TIMEFRAMES[tf])
        v = leggi_vwap(vwap_m1, s.index + passo).values
        out["serie"][tf] = {
            "t": [int(x.timestamp() * 1000) for x in s.index],
            "o": [round(x, 2) for x in s.open], "h": [round(x, 2) for x in s.high],
            "l": [round(x, 2) for x in s.low], "c": [round(x, 2) for x in s.close],
            "v": ([None if np.isnan(x) else round(float(x), 2) for x in v]
                  if v is not None else None)}
    # "adesso" e' l'ora vera, non la chiusura futura della candela in corso:
    # usare quella mostrerebbe struttura e zone nate da una candela non ancora
    # finita, cioe' informazione che dal vivo non esiste ancora
    adesso = pd.Timestamp.now("UTC")
    serie_stati = {}
    for tf in TF_ZONE:
        tfd = resample_tf(m1, tf)
        passo = pd.Timedelta(TIMEFRAMES[tf])
        st = trend_state_series(tfd, T.frattale_k, passo)
        st = st[st.index <= adesso]      # niente stati "noti" solo in futuro
        serie_stati[tf] = st
        out["struttura"][tf] = int(st.iloc[-1]) if len(st) else 0
        z = zone_ob(tfd, T.frattale_k, passo)
        if z.empty:
            continue
        # la scadenza va ricalcolata: zone_ob la tronca all'ultima candela,
        # quindi al bordo destro le zone appena nate sembrerebbero scadute
        scad = z.attiva_da + VALIDITA * passo
        # invalidata_il puo' essere tutta NaT: pandas la crea senza fuso e il
        # confronto con un istante con fuso solleverebbe TypeError
        inval = pd.to_datetime(z.invalidata_il, utc=True, errors="coerce")
        vive = z[(z.attiva_da <= adesso) & (scad > adesso)
                 & (inval.isna() | (inval > adesso))]
        for i, r in vive.iterrows():
            out["zone"].append({
                "tf": tf, "lato": int(r.lato),
                "basso": round(float(r.basso), 2), "alto": round(float(r.alto), 2),
                "rbasso": None if not np.isfinite(r.rbasso) else round(float(r.rbasso), 2),
                "ralto": None if not np.isfinite(r.ralto) else round(float(r.ralto), 2),
                "da": r.attiva_da.strftime("%d/%m %H:%M"),
                "scade": scad[i].strftime("%d/%m %H:%M"),
                "dist": round(bid - r.alto if r.lato == 1 else r.basso - bid, 2)})
    out["zone"].sort(key=lambda x: abs(x["dist"]))
    out["profilo"] = profilo_sessioni(m1)
    with _lock:
        noti = list(_segnali["elenco"])
    out["condizioni"] = condizioni_ora(m1, vwap_m1, serie_stati, adesso,
                                       mediana, noti)
    a = daily_atr(m1, 14)
    atr = float(a.iloc[-1]) if len(a) and np.isfinite(a.iloc[-1]) else float("nan")
    out["confluenze"] = confluenze_ora(bid, out["zone"],
                                       livelli_di_ieri(m1, atr), atr)
    with _lock:
        out["segnali"] = list(_segnali["elenco"])
        out["segnali_ora"] = _segnali["ora"]
        out["segnali_errore"] = _segnali["errore"]
    return out


SESSIONI = {"asia": (0, 7), "london": (7, 12), "ny": (12, 21), "late": (21, 24)}
BIN = 0.5                  # larghezza dei livelli di prezzo, in dollari


def profilo_sessioni(m1):
    """Volume scambiato per livello di prezzo, diviso per sessione UTC.

    Solo la giornata corrente: e' il profilo che serve a leggere dove il
    mercato ha lavorato oggi, non una media storica.
    """
    giorno = m1.index[-1].normalize()
    d = m1[m1.index >= giorno]
    if d.empty:
        return None
    tipico = ((d.high + d.low + d.close) / 3).values
    vol = d.volume.values.astype(float)
    vol[~np.isfinite(vol) | (vol <= 0)] = 1.0
    liv = np.round(tipico / BIN).astype(np.int64)
    ore = d.index.hour.values
    unici = np.unique(liv)
    out = {"prezzi": [round(float(u * BIN), 2) for u in unici]}
    somme = {}
    for nome, (a, b) in SESSIONI.items():
        m = (ore >= a) & (ore < b)
        s = np.zeros(len(unici))
        if m.any():
            np.add.at(s, np.searchsorted(unici, liv[m]), vol[m])
        somme[nome] = s
    # il volume e' in unita' diverse a seconda della fonte (conteggio tick da
    # MT5, decimale nello storico): si normalizza a 100, contano le proporzioni
    massimo = max(1e-12, float(sum(somme.values()).max()))
    for nome, s in somme.items():
        out[nome] = [round(float(x) / massimo * 100, 2) for x in s]
    out["giorno"] = giorno.strftime("%d/%m")
    return out


def aggiorna_sempre():
    storia, mediana = storico_archivio()   # si leggono una volta sola
    if storia is None:
        print("ATTENZIONE: archivio non trovato, i segnali useranno solo le "
              "sei settimane del terminale e le regole saranno piu' blande")
    else:
        print(f"contesto dall'archivio: {storia.index[0]:%d/%m/%Y} "
              f"({len(storia):,} candele)".replace(",", "."))
    while True:
        try:
            d = calcola(storia, mediana)
        except Exception as e:                       # il terminale puo' chiudersi
            d = {"pronto": False, "errore": str(e)}
        with _lock:
            _dati.clear()
            _dati.update(d)
        time.sleep(AGGIORNA)


PAGINA = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>XAUUSD live</title><style>
:root{--g:#151318;--p:#1C1A20;--i:#E9E4DB;--i3:#6E675F;--l:#2C2932;
--up:#4EA57F;--dn:#C25A46;--br:#C99A3E;--vw:#8E7BD0;
--m:ui-monospace,Menlo,Consolas,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--g);color:var(--i);
font:14px/1.5 system-ui,sans-serif}
.w{max-width:1200px;margin:0 auto;padding:12px;display:flex;flex-direction:column;gap:10px}
h1{margin:0;font:600 16px var(--m)}h1 span{color:var(--br)}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.pill{font:11px var(--m);padding:4px 9px;border:1px solid var(--l);border-radius:99px;
background:var(--p);color:var(--i3)}.pill b{color:var(--i)}
.seg{display:flex;gap:3px;background:var(--p);border:1px solid var(--l);border-radius:9px;padding:3px}
.seg button{border:0;background:none;color:var(--i3);font:12px var(--m);
padding:5px 10px;border-radius:6px;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--br);color:var(--g);font-weight:600}
canvas{display:block;width:100%;height:520px;background:var(--p);
border:1px solid var(--l);border-radius:12px;cursor:grab;touch-action:none}
table{width:100%;border-collapse:collapse;font:12px var(--m)}
th,td{text-align:right;padding:6px 8px;border-bottom:1px solid var(--l)}
th{color:var(--i3);font-weight:500;text-align:right}td:first-child,th:first-child{text-align:left}
.buy{color:var(--up)}.sell{color:var(--dn)}
.note{color:var(--i3);font-size:12px}
.chk{display:flex;gap:10px;flex-wrap:wrap}
.lato{flex:1 1 320px;background:var(--p);border:1px solid var(--l);
border-radius:12px;padding:10px 12px}
.lato h2{margin:0 0 8px;font:600 13px var(--m);letter-spacing:.02em}
.lato.si{border-color:var(--up);box-shadow:0 0 0 1px var(--up) inset}
.riga{display:flex;justify-content:space-between;gap:10px;
font:12px var(--m);padding:3px 0;color:var(--i3)}
.riga b{font-weight:500}
.si1{color:var(--up)}.no1{color:var(--dn)}.nd{color:var(--i3)}
</style></head><body><div class="w">
<h1>XAUUSD <span>·</span> live da MT5</h1>
<div class="bar" id="bar"></div>
<div id="cond"></div>
<div class="bar"><div class="seg" id="tf"></div><div class="seg" id="vp"></div><div class="seg" id="et"></div>
<div class="seg" id="sg"></div>
<div class="seg"><button id="ora">torna a ora</button></div>
<span class="pill">rotellina = zoom · trascina = scorri · doppio clic = ora</span></div>
<canvas id="c"></canvas>
<table id="tab"></table>
<p class="note">La colonna <b>raffinata</b> e' la parte che porta il vantaggio misurato.
Una zona non e' un segnale da sola e non va usata come limite in attesa: serve il
segnale della strategia con la struttura concorde.</p>
</div><script>
const TF=["M1","M6","M12","M33","M66","H2","H3","H6"];let tf="M33",D=null,vp=1,etich=0,curY=null,fissate=new Set();
// finestra visibile: quante candele si vedono e di quante il bordo destro sta
// indietro rispetto all'ultima. off negativo = spazio vuoto a destra, cosi' il
// grafico non resta incollato al bordo.
let vis=140,off=-8,nPrec=0,passoX=6,trascina=null,mosso=false,seg=1;
const VUOTE=()=>Math.floor(vis*0.45);          // quanto si puo' andare oltre l'ultima
const el=i=>document.getElementById(i);
el("tf").innerHTML=TF.map(t=>`<button aria-pressed="${t===tf}">${t}</button>`).join("");
[...el("tf").children].forEach((b,k)=>b.onclick=()=>{tf=TF[k];off=-8;nPrec=0;
[...el("tf").children].forEach((x,j)=>x.setAttribute("aria-pressed",j===k));draw();});
el("vp").innerHTML=["profilo off","profilo sessioni"].map((t,k)=>
 `<button aria-pressed="${k===vp}">${t}</button>`).join("");
[...el("vp").children].forEach((b,k)=>b.onclick=()=>{vp=k;
 [...el("vp").children].forEach((x,j)=>x.setAttribute("aria-pressed",j===k));draw();});
el("et").innerHTML=["nomi al passaggio","nomi sempre"].map((t,k)=>
 `<button aria-pressed="${k===etich}">${t}</button>`).join("");
[...el("et").children].forEach((b,k)=>b.onclick=()=>{etich=k;
 [...el("et").children].forEach((x,j)=>x.setAttribute("aria-pressed",j===k));draw();});
el("sg").innerHTML=["segnali off","ufficiali","tutti"].map((t,k)=>
 `<button aria-pressed="${k===seg}">${t}</button>`).join("");
[...el("sg").children].forEach((b,k)=>b.onclick=()=>{seg=k;
 [...el("sg").children].forEach((x,j)=>x.setAttribute("aria-pressed",j===k));draw();});
// il puntatore decide quali nomi mostrare; il clic li fissa
const cv0=el("c");
const aOra=()=>{off=-8;draw();};
el("ora").onclick=aOra; cv0.addEventListener("dblclick",aOra);
cv0.addEventListener("mousemove",e=>{
 curY=e.clientY-cv0.getBoundingClientRect().top;
 if(trascina){const dx=e.clientX-trascina.x;
  if(Math.abs(dx)>2)mosso=true;
  off=trascina.off+Math.round(dx/passoX);}
 draw();});
cv0.addEventListener("mousedown",e=>{trascina={x:e.clientX,off:off};mosso=false;
 cv0.style.cursor="grabbing";});
addEventListener("mouseup",()=>{trascina=null;cv0.style.cursor="grab";});
cv0.addEventListener("mouseleave",()=>{curY=null;draw();});
// zoom tenendo fermo il punto sotto il puntatore, come su TradingView
cv0.addEventListener("wheel",e=>{e.preventDefault();
 const r=cv0.getBoundingClientRect();
 const fx=Math.min(Math.max((e.clientX-r.left-8)/Math.max(r.width-70,1),0),1);
 const nv=Math.round(vis*(e.deltaY>0?1.18:1/1.18));
 off=Math.round(off-(nv-vis)*(1-fx)); vis=nv; draw();},{passive:false});
cv0.addEventListener("click",()=>{if(mosso||!D||!D.zone)return;   // trascinare non fissa
 D.zone.forEach((z,i)=>{if(z._sotto){fissate.has(i)?fissate.delete(i):fissate.add(i);}});
 draw();});
const stat=v=>v===1?["rialzista","buy"]:v===-1?["ribassista","sell"]:["neutra",""];
const bollo=v=>v===null||v===undefined?'<b class="nd">—</b>'
 :v?'<b class="si1">si</b>':'<b class="no1">no</b>';
// il pannello delle cinque condizioni, per i due lati, sull'ultima M6 chiusa
function pannello(){
 const C=D.condizioni;
 if(!C){el("cond").innerHTML="";return;}
 el("cond").innerHTML='<div class="chk">'+["long","short"].map(n=>{
  const L=C.lati[n];
  const righe=[
   ["1 · orario della candela",bollo(C.ora_ok)
     +(C.alta_volatilita?' <b class="nd">· mese agitato</b>':"")],
   ["2 · struttura H6+H2",bollo(L.struttura)],
   ["3a · conferme M33+H12",bollo(L.conferme)],
   ["3b · M12 non allineato",bollo(L.ritracciamento)],
   ["4a · spinta dal VWAP","<b>"+L.spinta.toFixed(2)+" / "+L.soglia.toFixed(2)
     +" $</b> "+bollo(L.spinta_ok)],
   ["4b · riprende il VWAP",bollo(L.reclaim)],
   ["5 · filtro di fondo D1",bollo(L.macro)],
   ["6 · rischio nella banda","<b>"+L.rischio.toFixed(2)+" $</b> ("
     +L.banda[0].toFixed(2)+"-"+L.banda[1].toFixed(2)+") "+bollo(L.rischio_ok)],
   ["7 · quota del giorno","<b>"+C.oggi+"/"+C.max_giorno+"</b> "
     +bollo(C.oggi<C.max_giorno)+" · attesa "+bollo(C.attesa_ok)],
  ].concat(C.tarabile?[]:[["mese agitato senza riferimento ATR",
    '<b class="no1">il motore non aprirebbe</b>']])
  .map(([a,b])=>`<div class="riga"><span>${a}</span><span>${b}</span></div>`).join("");
  return `<div class="lato${L.pronto?" si":""}"><h2>${n.toUpperCase()}`
   +(L.pronto?' · <span class="si1">SEGNALE</span>':"")
   +`</h2>${righe}</div>`;}).join("")+conflu()+'</div>';}

// quali confluenze contano e quali no: la risposta misurata e' che nessuna
// apre un'operazione da sola, quindi qui si pesa, non si segnala
function conflu(){
 const K=D.confluenze;
 if(!K)return "";
 const v=K.vicini.length?K.vicini.map(z=>{
  const c=z.peso==="voto"?"si1":"nd";
  const l=z.lato===1?"BUY":z.lato===-1?"SELL":"—";
  return `<div class="riga"><span>${z.tf} ${z.famiglia} <b class="${
   z.lato===1?"buy":z.lato===-1?"sell":""}">${l}</b></span>`
   +`<span><b>${z.dist_atr.toFixed(2)} ATR</b> · <b class="${c}">${z.peso}</b></span></div>`;
  }).join("")
  :'<div class="riga"><span>nessun livello entro il raggio</span><span></span></div>';
 return `<div class="lato"><h2>CONFLUENZE · ${K.voti} voto/i, ${K.contesto
  } di contesto</h2>${v}<div class="riga" style="margin-top:6px">`
  +`<span>raggio ${K.raggio.toFixed(2)} $ (mezzo ATR di ${K.atr.toFixed(2)})</span>`
  +`</div><p class="note" style="margin:8px 0 0">Le confluenze <b>non aprono</b> `
  +`un'operazione: misurate su 18 anni e 720 configurazioni, zero sopravvissute `
  +`(appendice AZ). Si entra con le cinque condizioni qui accanto; una zona `
  +`<b>raffinata concorde</b> dice solo che l'occasione e' migliore della media.</p></div>`;}
async function tira(){try{const r=await fetch("/api/dati");D=await r.json();draw();}
catch(e){}finally{setTimeout(tira,3000);}}
function draw(){
 const b=el("bar");
 if(!D||!D.pronto){b.innerHTML=`<span class="pill">${D?D.errore:"connessione..."}</span>`;return;}
 b.innerHTML=`<span class="pill">bid <b>${D.bid.toFixed(2)}</b></span>
  <span class="pill">spread <b>${D.spread.toFixed(2)} $</b></span>
  <span class="pill">candela ${D.ultima_candela}</span>
  <span class="pill">agg. ${D.ora} UTC</span>
  <span class="pill">VWAP <b>${D.condizioni?D.condizioni.vwap.toFixed(2):"—"}</b></span>
  <span class="pill">segnali ${D.segnali?D.segnali.length:0}${
    D.segnali_ora?" · "+D.segnali_ora:" · in calcolo"}</span>`+
  (D.buco?`<span class="pill" style="border-color:var(--dn)">buco di <b class="no1">${
    D.buco} giorni</b> fra archivio e terminale</span>`:"")+
  Object.entries(D.struttura).map(([k,v])=>{const[s,c]=stat(v);
   return `<span class="pill">${k} <b class="${c}">${s}</b></span>`}).join("");
 pannello();
 const s=D.serie[tf];if(!s)return;
 const cv=el("c"),x=cv.getContext("2d"),dpr=devicePixelRatio||1;
 const W=cv.clientWidth,H=cv.clientHeight;cv.width=W*dpr;cv.height=H*dpr;
 x.setTransform(dpr,0,0,dpr,0,0);x.clearRect(0,0,W,H);
 const n=s.c.length;
 // se si sta guardando il passato, l'arrivo di una candela non deve spostare
 // la vista: si scala l'offset di altrettante candele
 if(nPrec&&n>nPrec&&off>0)off+=n-nPrec;
 nPrec=n;
 vis=Math.max(15,Math.min(vis,Math.max(n,15)));
 off=Math.max(-VUOTE(),Math.min(off,Math.max(n-10,0)));
 const destra=n-1-off,i0=destra-vis+1;
 const a0=Math.max(0,i0),a1=Math.min(n-1,destra);
 const zs=D.zone;
 let lo=Math.min(...s.l.slice(a0,a1+1)),hi=Math.max(...s.h.slice(a0,a1+1));
 if(!isFinite(lo)||!isFinite(hi)){lo=D.bid-5;hi=D.bid+5;}
 zs.forEach(z=>{if(z.basso>lo-200&&z.alto<hi+200){lo=Math.min(lo,z.basso);hi=Math.max(hi,z.alto);}});
 const pad=(hi-lo)*.06||1;lo-=pad;hi+=pad;
 const pl=8,pr=62,pt=10,pb=8,pw=W-pl-pr,ph=H-pt-pb;
 passoX=pw/vis;
 const X=i=>pl+(i-i0+.5)*passoX, Y=p=>pt+(hi-p)/(hi-lo)*ph;
 const F="11px "+getComputedStyle(document.body).getPropertyValue("--m");

 // --- profilo volume: a SINISTRA, sotto a tutto il resto -------------------
 let poc=null, vuoti=[];
 if(D.profilo){const P=D.profilo,SS=["asia","london","ny","late"],
   CO={asia:"rgba(142,123,208,.50)",london:"rgba(201,154,62,.50)",
       ny:"rgba(78,165,127,.50)",late:"rgba(110,103,95,.50)"};
  const tot=P.prezzi.map((_,i)=>SS.reduce((a,s2)=>a+P[s2][i],0));
  const max=Math.max(...tot,0);
  if(max>0){
   poc=P.prezzi[tot.indexOf(max)];
   // zone di vuoto: livelli scambiati poco, uniti in fasce contigue
   const soglia=max*.15; let ini=null;
   P.prezzi.forEach((p,i)=>{const sotto=tot[i]<soglia&&tot[i]>0;
    if(sotto&&ini===null)ini=p; if(!sotto&&ini!==null){vuoti.push([ini,P.prezzi[i-1]]);ini=null;}});
   if(ini!==null)vuoti.push([ini,P.prezzi[P.prezzi.length-1]]);
   vuoti=vuoti.filter(v=>v[1]-v[0]>=1.5);           // solo i vuoti veri
   if(vp){const lw=pw*.20, hb=Math.max(2,ph/((hi-lo)/0.5));
    // le fasce di vuoto attraversano tutto il grafico
    x.fillStyle="rgba(233,228,219,.045)";
    vuoti.forEach(v=>x.fillRect(pl,Y(v[1]),pw,Math.max(Y(v[0])-Y(v[1]),1.5)));
    P.prezzi.forEach((p,i)=>{if(p<lo||p>hi)return;let x0=pl;
     SS.forEach(s2=>{const v=P[s2][i];if(!v)return;const w2=v/max*lw;
      x.fillStyle=CO[s2];x.fillRect(x0,Y(p)-hb/2,w2,hb);x0+=w2;});});
    // il livello piu' scambiato, esteso su tutto il grafico
    const yp=Math.round(Y(poc))+.5;
    x.strokeStyle="rgba(233,228,219,.55)";x.lineWidth=1;x.setLineDash([2,4]);
    x.beginPath();x.moveTo(pl,yp);x.lineTo(pl+pw,yp);x.stroke();x.setLineDash([]);
    x.font=F;x.textAlign="left";x.textBaseline="bottom";x.fillStyle="#8E877E";
    x.fillText("volume massimo "+poc.toFixed(2),pl+4,yp-2);
    x.textAlign="left";x.textBaseline="top";
    x.fillText("profilo "+P.giorno+" · asia londra ny sera",pl+4,pt+4);}}}

 // --- scala dei prezzi: passo tondo, cosi' si legge quanto vale un movimento
 {const gr=[.1,.2,.5,1,2,5,10,20,50,100,200,500];
  const ideale=(hi-lo)/7; let p0=gr[gr.length-1];
  for(const g of gr){if(g>=ideale){p0=g;break;}}
  x.font=F;x.textAlign="left";x.textBaseline="middle";
  for(let p=Math.ceil(lo/p0)*p0;p<=hi;p+=p0){const y=Math.round(Y(p))+.5;
   x.strokeStyle="rgba(233,228,219,.07)";x.lineWidth=1;
   x.beginPath();x.moveTo(pl,y);x.lineTo(pl+pw,y);x.stroke();
   x.fillStyle="#6E675F";x.fillText(p.toFixed(p0<1?2:(p0<10?1:0)),pl+pw+6,y);}}

 // --- zone: bande, senza etichetta (le etichette vanno a destra, in fondo) --
 zs.forEach(z=>{const y1=Y(z.alto),y2=Y(z.basso),up=z.lato===1;
  x.fillStyle=up?"rgba(78,165,127,.10)":"rgba(194,90,70,.10)";
  x.fillRect(pl,Math.min(y1,y2),pw,Math.abs(y2-y1));
  if(z.rbasso!==null){const r1=Y(z.ralto),r2=Y(z.rbasso);
   x.fillStyle=up?"rgba(78,165,127,.32)":"rgba(194,90,70,.32)";
   x.fillRect(pl,Math.min(r1,r2),pw,Math.max(Math.abs(r2-r1),1.5));}
  z._sotto = curY!==null && curY>=Math.min(y1,y2)-2 && curY<=Math.max(y1,y2)+2;
  if(z._sotto){x.strokeStyle=up?"#4EA57F":"#C25A46";x.lineWidth=1;
   x.strokeRect(pl+.5,Math.min(y1,y2)+.5,pw-1,Math.max(Math.abs(y2-y1)-1,1));}});

 if(s.v){x.strokeStyle=getComputedStyle(document.body).getPropertyValue("--vw");
  x.lineWidth=1.6;x.beginPath();let pen=false;
  for(let i=a0;i<=a1;i++){if(s.v[i]===null){pen=false;continue;}
   pen?x.lineTo(X(i),Y(s.v[i])):(x.moveTo(X(i),Y(s.v[i])),pen=true);}x.stroke();}
 // corpi su pixel interi: a mezzo pixel il canvas antialiasa e le candele
 // sfocano, che e' quello che si vedeva zoomando
 const bw=Math.max(1,Math.round(Math.min(passoX*.7,22)));
 for(let i=a0;i<=a1;i++){const up=s.c[i]>=s.o[i];
  x.strokeStyle=x.fillStyle=up?"#4EA57F":"#C25A46";x.lineWidth=1;
  const xc=Math.round(X(i))+.5;
  x.beginPath();x.moveTo(xc,Math.round(Y(s.h[i])));x.lineTo(xc,Math.round(Y(s.l[i])));x.stroke();
  const yo=Math.round(Y(s.o[i])),yc=Math.round(Y(s.c[i]));
  x.fillRect(Math.round(X(i)-bw/2),Math.min(yo,yc),bw,Math.max(Math.abs(yc-yo),1));}

 // --- segnali della strategia: triangolo all'ingresso ----------------------
 if(seg&&D.segnali&&D.segnali.length){
  const scelti=D.segnali.filter(g=>seg===2||g.ufficiale);
  scelti.forEach(g=>{
   let k=0,lo2=0,hi2=s.t.length-1;          // la barra che contiene il segnale
   while(lo2<=hi2){const md=(lo2+hi2)>>1;
    if(s.t[md]<=g.t){k=md;lo2=md+1;}else hi2=md-1;}
   if(k<a0-1||k>a1+1)return;
   const xc=Math.round(X(k)),yv=Math.round(Y(g.entry)),up=g.lato===1;
   const h2=up?-1:1, col=up?"#4EA57F":"#C25A46";
   x.beginPath();
   x.moveTo(xc,yv+6*h2);x.lineTo(xc-5,yv+13*h2);x.lineTo(xc+5,yv+13*h2);
   x.closePath();
   if(g.ufficiale){x.fillStyle=col;x.fill();}
   else{x.strokeStyle=col;x.lineWidth=1;x.stroke();}
   g._x=xc;g._y=yv;});
  // il segnale piu' recente mostra anche stop e obiettivo
  const ult=scelti[scelti.length-1];
  if(ult&&ult._x!==undefined){
   [[ult.stop,"#C25A46","stop"],[ult.obiettivo,"#4EA57F","1:"+Math.round(
     Math.abs((ult.obiettivo-ult.entry)/(ult.entry-ult.stop)))]].forEach(([p,c,t2])=>{
    if(p<lo||p>hi)return;const y2=Math.round(Y(p))+.5;
    x.strokeStyle=c;x.lineWidth=1;x.setLineDash([1,3]);
    x.beginPath();x.moveTo(ult._x,y2);x.lineTo(pl+pw,y2);x.stroke();x.setLineDash([]);
    x.fillStyle=c;x.font=F;x.textAlign="left";x.textBaseline="bottom";
    x.fillText(t2+" "+p.toFixed(2),ult._x+4,y2-2);});}}

 const yb=Math.round(Y(D.bid))+.5;
 x.strokeStyle="#C99A3E";x.lineWidth=1;x.setLineDash([4,3]);
 x.beginPath();x.moveTo(pl,yb);x.lineTo(pl+pw,yb);x.stroke();x.setLineDash([]);
 x.fillStyle="#C99A3E";x.font=F;x.textAlign="left";
 x.textBaseline="middle";x.fillText(D.bid.toFixed(2),pl+pw+6,yb);

 // --- etichette: solo la banda sotto il puntatore, o quelle fissate col clic
 x.font=F;x.textBaseline="middle";x.textAlign="right";
 const scelte=zs.filter((z,i)=>etich===1||z._sotto||fissate.has(i));
 if(!scelte.length){x.fillStyle="#6E675F";x.textAlign="right";x.textBaseline="top";
  x.fillText(zs.length+" zone · passa sopra una banda per il nome, clic per fissarlo",
             pl+pw-4,pt+4);x.textBaseline="middle";}
 const et=scelte.map(z=>({t:z.tf+" "+(z.lato===1?"BUY":"SELL")+"  "
    +z.basso.toFixed(2)+"–"+z.alto.toFixed(2),up:z.lato===1,
   y:(Y(z.alto)+Y(z.basso))/2})).sort((a,b)=>a.y-b.y);
 const H0=16;                                  // altezza minima fra etichette
 for(let k=1;k<et.length;k++)                  // scendendo: spingi in giu'
  if(et[k].y-et[k-1].y<H0) et[k].y=et[k-1].y+H0;
 for(let k=et.length-1;k>0;k--)                // risalendo: rientra nel bordo
  if(et[k].y>pt+ph-8){et[k].y=pt+ph-8;
   if(et[k].y-et[k-1].y<H0) et[k-1].y=et[k].y-H0;}
 et.forEach(e=>{const w=x.measureText(e.t).width+9, xr=pl+pw-4;
  x.fillStyle=e.up?"rgba(78,165,127,.22)":"rgba(194,90,70,.22)";
  x.fillRect(xr-w,e.y-8,w,16);
  x.fillStyle=e.up?"#4EA57F":"#C25A46";x.fillText(e.t,xr-5,e.y);});
 el("tab").innerHTML="<tr><th>tf</th><th>lato</th><th>zona</th><th>raffinata</th>"+
  "<th>distanza</th><th>attiva da</th><th>scade</th></tr>"+
  (D.zone.length?D.zone.map(z=>`<tr><td>${z.tf}</td>
   <td class="${z.lato===1?"buy":"sell"}">${z.lato===1?"BUY":"SELL"}</td>
   <td>${z.basso.toFixed(2)}–${z.alto.toFixed(2)}</td>
   <td>${z.rbasso===null?"—":z.rbasso.toFixed(2)+"–"+z.ralto.toFixed(2)}</td>
   <td>${z.dist>0?"+":""}${z.dist.toFixed(2)}</td><td>${z.da}</td><td>${z.scade}</td></tr>`).join("")
   :`<tr><td colspan="7" style="text-align:center;color:var(--i3)">nessuna zona attiva</td></tr>`);
}
addEventListener("resize",draw);tira();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/dati"):
            with _lock:
                corpo = json.dumps(_dati).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            corpo = PAGINA.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a):
        pass                                   # niente rumore sul terminale


def main():
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    threading.Thread(target=aggiorna_sempre, daemon=True).start()
    _, mediana = storico_archivio()
    threading.Thread(target=aggiorna_segnali, args=(mediana,),
                     daemon=True).start()
    print(f"grafico live su http://127.0.0.1:{porta}  (CTRL+C per fermare)")
    HTTPServer(("127.0.0.1", porta), Handler).serve_forever()


if __name__ == "__main__":
    main()
