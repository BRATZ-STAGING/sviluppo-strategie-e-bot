"""Gestione della posizione: stop a pareggio e chiusure parziali.

Lo studio sulle conferme mostra che nessuna combinazione di timeframe abbassa
il tasso di stop sotto il 60% circa: le conferme spostano il rendimento, non
la frequenza degli stop. La frequenza degli stop la decide la gestione della
posizione, ed e' quello che questo modulo modella.

Convenzioni conservative, identiche al resto del progetto: al minuto, se stop
e obiettivo cadono insieme vince lo stop; lo stesso vale fra lo stop portato
a pareggio e l'obiettivo.
"""
from __future__ import annotations

import numpy as np

# Motivi di uscita
STOP, OBIETTIVO, FINE_GIORNATA, PAREGGIO = 0, 1, 2, 3


def _primo(v: np.ndarray) -> int | None:
    """Indice del primo True, o None se non ce ne sono."""
    return int(np.argmax(v)) if v.any() else None


def esito_indice(fav: np.ndarray, sfav: np.ndarray, rr: float,
                 be: float | None = None, parziale: bool = False,
                 costo: float = 0.0) -> tuple[float | None, int, int | None]:
    """Come ``esito``, ma ritorna anche il minuto in cui la posizione si chiude.

    Il terzo valore e' l'indice di uscita, o None se la posizione arriva
    aperta a fine giornata.
    """
    i_sl = _primo(sfav >= 1.0)
    i_tp = _primo(fav >= rr)

    if be is None:
        if i_sl is not None and (i_tp is None or i_sl <= i_tp):
            return -1.0 - costo, STOP, i_sl
        if i_tp is not None:
            return rr - costo, OBIETTIVO, i_tp
        return None, FINE_GIORNATA, None

    i_be = _primo(fav >= be)
    if i_sl is not None and (i_be is None or i_sl <= i_be):
        return -1.0 - costo, STOP, i_sl      # stoppati prima di poter armare
    if i_be is None:
        return None, FINE_GIORNATA, None     # mai armato e mai stoppato
    if i_tp is not None and i_tp <= i_be:
        return rr - costo, OBIETTIVO, i_tp   # obiettivo raggiunto nello stesso
                                             # minuto in cui si sarebbe armato
    dopo = slice(i_be + 1, None)             # da qui lo stop e' a pareggio
    j_be = _primo(sfav[dopo] > 0.0)          # ritorno sul prezzo d'ingresso
    j_tp = _primo(fav[dopo] >= rr)
    incassato = 0.5 * be if parziale else 0.0
    resto = 0.5 if parziale else 1.0

    if j_be is not None and (j_tp is None or j_be <= j_tp):
        return incassato - costo, PAREGGIO, i_be + 1 + j_be
    if j_tp is not None:
        return incassato + resto * rr - costo, OBIETTIVO, i_be + 1 + j_tp
    return None, FINE_GIORNATA, None


def esito(fav: np.ndarray, sfav: np.ndarray, rr: float,
          be: float | None = None, parziale: bool = False,
          costo: float = 0.0) -> tuple[float | None, int]:
    """Esito in R di una posizione, dati i percorsi favorevole e contrario.

    ``fav[j]``   escursione favorevole al minuto j, in multipli del rischio
    ``sfav[j]``  escursione contraria al minuto j, in multipli del rischio
                 (>= 1 significa stop colpito)
    ``rr``       obiettivo in multipli del rischio
    ``be``       soglia oltre la quale lo stop va al prezzo d'ingresso
                 (None = stop fisso)
    ``parziale`` se True, raggiunta la soglia si chiude meta' posizione
    ``costo``    spread di andata e ritorno, gia' espresso in R

    Ritorna ``(R, motivo)``. ``R is None`` significa che la posizione e'
    ancora aperta a fine giornata: il risultato lo decide il chiamante, che
    conosce il prezzo di chiusura.
    """
    r, motivo, _ = esito_indice(fav, sfav, rr, be, parziale, costo)
    return r, motivo


def chiusura_fine_giornata(r_eod: float, be: float | None, parziale: bool,
                           mfe: float, costo: float) -> float:
    """R di una posizione ancora aperta alla chiusura della giornata.

    Se era attiva la chiusura parziale ed era stata raggiunta la soglia, meta'
    del risultato e' gia' stata incassata a ``be``.
    """
    if parziale and be is not None and mfe >= be:
        return 0.5 * be + 0.5 * r_eod - costo
    return r_eod - costo


def valuta(op: dict, rr: float, be: float | None = None,
           parziale: bool = False) -> tuple[float, int]:
    """Esito di un'operazione prodotta da :func:`framework.segnali.genera`.

    Scioglie il caso "ancora aperta a fine giornata" usando ``r_eod``, cosi'
    chi chiama ottiene sempre un numero.
    """
    r, motivo = esito(op["fav"], op["sfav"], rr, be=be, parziale=parziale,
                      costo=op["costo"])
    if r is None:
        r = chiusura_fine_giornata(op["r_eod"], be, parziale, op["mfe"],
                                   op["costo"])
    return r, motivo
