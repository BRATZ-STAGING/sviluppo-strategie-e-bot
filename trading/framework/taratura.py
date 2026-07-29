"""La taratura ufficiale della strategia intraday XAUUSD.

Un solo posto in cui stanno i numeri, cosi' gli studi futuri partono tutti
dalla stessa configurazione e le differenze fra un risultato e l'altro sono
attribuibili a cio' che si sta provando, non a costanti scopiazzate.

Ogni valore qui dentro e' stato scelto e verificato fuori campione: la
motivazione e la misura sono in ``docs/studies/rr-intraday-study.md``.
Cambiare un numero qui cambia tutti gli studi: farlo solo con una verifica
per anno e fuori campione alle spalle.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Taratura:
    # --- costi e struttura del segnale -------------------------------------
    spread: float = 0.30              # costo di andata e ritorno, in dollari
    buffer: float = 0.30              # distanza dello stop dall'estremo
    impulso_min: float = 4.00         # allontanamento minimo dal VWAP
    rischio_min: float = 1.00         # distanza minima dell'entrata dallo stop
    rischio_max: float = 10.00        # distanza massima
    barre_stop: int = 5               # candele guardate indietro per lo stop

    # Le soglie sopra sono in dollari nei mesi normali e riscalate con l'ATR
    # nei mesi ad alta volatilita' (fattore 1,5 sulla mediana storica). La
    # mediana di riferimento si calcola su questi anni.
    calibrazione: tuple[int, int] = (2020, 2024)
    fattore_alta_volatilita: float = 1.5

    # --- quando si puo' entrare --------------------------------------------
    ora_inizio: int = 7               # ore UTC, estremi [inizio, fine)
    ora_fine: int = 19
    ora_chiusura: int = 21            # chiusura di tutte le posizioni
    max_operazioni_giorno: int = 3
    attesa_minuti: int = 30           # fra un segnale e il successivo

    # --- direzione e struttura ---------------------------------------------
    media_macro: int = 50             # filtro di fondo: chiusura D1 vs media
    tf_ingresso: str = "M6"           # timeframe su cui si valuta l'ingresso
    tf_struttura: tuple[str, ...] = ("H6", "H2")     # devono essere allineati
    conferme: tuple[str, ...] = ("M33", "H12")       # devono essere allineate
    ritracciamento: tuple[str, ...] = ("M12",)       # devono essere CONTRARI
    frattale_k: int = 3               # barre di conferma di uno swing

    # --- gestione della posizione ------------------------------------------
    obiettivo: float = 10.0           # take profit, in multipli del rischio
    pareggio: float | None = 3.0      # a +xR lo stop va al prezzo d'ingresso
    rischio_per_operazione: float = 0.01     # frazione del capitale

    def __post_init__(self):
        if not 0 < self.rischio_per_operazione <= 0.05:
            raise ValueError("rischio_per_operazione fuori range (0, 0.05]")
        if self.rischio_min >= self.rischio_max:
            raise ValueError("rischio_min deve essere minore di rischio_max")
        if self.pareggio is not None and not 0 < self.pareggio < self.obiettivo:
            raise ValueError("il pareggio deve stare fra 0 e l'obiettivo")
        if not self.ora_inizio < self.ora_fine <= self.ora_chiusura:
            raise ValueError("orari incoerenti")
        doppie = set(self.conferme) & set(self.ritracciamento)
        if doppie:
            raise ValueError(f"timeframe sia conferma sia ritracciamento: {doppie}")

    @property
    def timeframes(self) -> tuple[str, ...]:
        """Tutti i timeframe che servono per valutare un segnale."""
        return tuple(dict.fromkeys(
            self.tf_struttura + self.conferme + self.ritracciamento))

    def soglie(self, atr: float | None = None, mediana: float | None = None
               ) -> dict[str, float]:
        """Soglie in dollari; se ``atr`` e' dato, riscalate sulla volatilita'.

        Nei mesi ad alta volatilita' le soglie non restano in dollari fissi ma
        seguono l'ATR, rapportate alla mediana del periodo di calibrazione.
        """
        base = {"impulso": self.impulso_min, "buffer": self.buffer,
                "rischio_min": self.rischio_min, "rischio_max": self.rischio_max}
        if atr is None:
            return base
        if not mediana or mediana <= 0:
            raise ValueError("serve la mediana ATR del periodo di calibrazione")
        return {k: v / mediana * atr for k, v in base.items()}


UFFICIALE = Taratura()
