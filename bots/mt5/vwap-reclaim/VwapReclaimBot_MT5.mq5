//+------------------------------------------------------------------+
//|  VWAP RECLAIM BOT — MT5                                          |
//|                                                                  |
//|  Un solo Expert Advisor per i tre profili della sfida (B, C, D). |
//|  L'ingresso e' identico: reclaim del VWAP giornaliero su M6, le  |
//|  sette condizioni di bots/SCHEDE-STRATEGIE.md. Cambia solo come  |
//|  si esce. Scriverlo tre volte significava tre modi di sbagliarlo.|
//|                                                                  |
//|  | | B | C | D |                                                 |
//|  |obiettivo | 1:8 | 1:2 | 1:10 |                                 |
//|  |gestione | trail MFE-2R da +3R | nessuna | stop a +0,50R quando|
//|  |         |                     |         | l'MFE tocca +3R     |
//|  |chiusura | weekend se > +1R | 21:00 UTC | 21:00 UTC |          |
//|  |lati | long e short | long e short | SOLO LONG |               |
//|  |rischio | 0,75% | 0,75% | 0,53% |                              |
//|                                                                  |
//|  LA LOGICA DEL SEGNALE NON E' QUI: sta in VwapReclaimCore.mqh,   |
//|  che non chiama niente del terminale proprio per poter essere    |
//|  compilato anche con g++ e confrontato col motore Python. Il     |
//|  confronto e' gia' stato fatto (verifica/confronta.py): sul      |
//|  2025-01 -> 2026-06, 309 segnali grezzi e 96 operazioni, zero    |
//|  divergenze su istante, lato, stop e rischio.                    |
//|                                                                  |
//|  QUELLO CHE IL CONFRONTO NON COPRE, e che va fatto in MT5 prima  |
//|  di qualunque conto: fill reali, spread, ordine fra stop e       |
//|  obiettivo nella stessa candela, swap. Vedi SCHEDA.md.           |
//|                                                                  |
//|  Un terminale = un conto = un profilo. Magic number diverso per  |
//|  ciascuno: due EA sullo stesso conto senza distinguerli si       |
//|  chiuderebbero le posizioni a vicenda.                           |
//+------------------------------------------------------------------+
#property copyright "VWAP Reclaim — progetto XAUUSD"
#property version   "1.00"
#property description "Reclaim del VWAP giornaliero su M6, tre profili (B/C/D)"

#include <Trade\Trade.mqh>
#include "VwapReclaimCore.mqh"

//---------------- Tipi ----------------
enum ENUM_PROFILO
{
   PROFILO_B = 0,   // B  1:8, trailing MFE-2R da +3R, weekend se sopra +1R
   PROFILO_C = 1,   // C  1:2 secco, nessuno spostamento dello stop, 21:00 UTC
   PROFILO_D = 2    // D  1:10, stop a +0,50R quando l'MFE tocca +3R, solo long
};

//---------------- Parametri ----------------
input group "Profilo"
input ENUM_PROFILO Profilo        = PROFILO_B;   // Quale delle tre gestioni
input double       RischioPerOp   = 0.0;         // Rischio % (0 = quello del profilo)

input group "Strategia (NON toccare senza verifica fuori campione)"
input double ImpulsoMinimo   = 4.00;      // Allontanamento minimo dal VWAP ($)
input double BufferStop      = 0.30;      // Margine dello stop dall'estremo ($)
input double RischioMinimo   = 1.00;      // Distanza minima entrata-stop ($)
input double RischioMassimo  = 10.00;     // Distanza massima entrata-stop ($)
input double MedianaAtrRif   = 25.5968;   // Mediana ATR 2020-2024, CONGELATA
input int    OraInizio       = 7;         // Prima ora UTC utile (compresa)
input int    OraFine         = 19;        // Ultima ora UTC esclusa
input int    OraChiusura     = 21;        // Chiusura serale UTC (profili C e D)
input int    MaxAlGiorno     = 3;         // Tetto di operazioni al giorno
input int    AttesaMinuti    = 30;        // Minuti fra un segnale e il successivo

input group "Rischio e spegnimento"
input double LimiteEquityPct = 50.0;      // Ferma se il saldo scende sotto % iniziale (0=off)
input double FermaADrawdownR = 15.0;      // Ferma a -x R dal massimo (0=off) — PROPOSTA
input int    GiorniStoria    = 420;       // Giorni di M1 da caricare all'avvio

input group "Log"
input bool   ScriviCsv       = true;      // CSV dei segnali valutati
input bool   LogTutteLeBarre = false;     // true = ogni candela M6 (file enorme)
input long   MagicNumber     = 20260805;  // DIVERSO per ogni profilo

//---------------- Stato ----------------
CTrade   trade;
Motore   motore;
Parametri par;

int      scartoUtc      = 0;        // secondi: ora server - UTC
datetime ultimaM1       = 0;
bool     fermato        = false;
bool     avviato        = false;
double   saldoIniziale  = 0.0;
double   rCumulato      = 0.0;      // R realizzati
double   rMassimo       = 0.0;      // massimo di rCumulato
string   fileSegnali    = "";
bool     csvOk          = false;

// posizione in corso
ulong    ticketCorrente = 0;
double   entryCorrente  = 0.0, stopIniziale = 0.0, rischioCorrente = 0.0;
double   denaroRischiato = 0.0;     // quanto valeva 1 R quando si e' aperto
double   estremoFav     = 0.0;      // prezzo piu' favorevole visto
int      latoCorrente   = 0;
datetime apertaIl       = 0;
bool     trailArmato    = false;

//--- Prototipi: OnInit chiama funzioni definite piu' sotto.
int      CalcolaScartoUtc();
datetime InUtc(const datetime oraServer);
bool     CaricaStoria();
void     ApriCsv();
void     LogSegnale(const Esito &e);
void     Apri(const Esito &e);
double   Lotti(const double distanzaStop);
void     GestisciPosizione();
void     SpostaStop(const double nuovo);
void     Chiudi(const string motivo);
void     ChiusuraRilevata();
bool     Fermo();
ulong    TrovaPosizione();
void     RecuperaPosizione();
void     SalvaStatoPosizione();
string   ChiaveGv(const string campo);
double   ObiettivoR();
double   RischioProfilo();
bool     ChiudeOgniSera();
bool     SoloLong();
string   NomeProfilo();

//+------------------------------------------------------------------+
//|  Ora del server -> UTC                                           |
//|                                                                  |
//|  TRAPPOLA 1, la piu' cara: il terminale NON da' UTC, da' l'ora   |
//|  del broker (FP: UTC+2/+3 con l'ora legale) dentro un campo che  |
//|  sembra un epoch. Le soglie della strategia sono in UTC. Un      |
//|  offset fisso nel codice sbaglia due volte l'anno; qui lo scarto |
//|  si ricava a runtime e si arrotonda alla mezz'ora.               |
//|                                                                  |
//|  Sbagliarlo ha gia' reso irreali il 62% dei segnali disegnati    |
//|  sul grafico: il VWAP si ancora alle 21:00 invece che a mezzanotte
//|  e la finestra 07-19 diventa 04-16.                              |
//+------------------------------------------------------------------+
int CalcolaScartoUtc()
{
   const datetime server = TimeCurrent();
   const datetime gmt    = TimeGMT();
   if(server <= 0 || gmt <= 0) return 0;
   const int grezzo = (int)(server - gmt);
   const int mezzore = (int)MathRound((double)grezzo / 1800.0);
   return mezzore * 1800;
}

datetime InUtc(const datetime oraServer) { return (datetime)(oraServer - scartoUtc); }

//+------------------------------------------------------------------+
//|  Parametri del profilo                                           |
//+------------------------------------------------------------------+
double ObiettivoR()
{
   if(Profilo == PROFILO_B) return 8.0;
   if(Profilo == PROFILO_C) return 2.0;
   return 10.0;
}

double RischioProfilo()
{
   if(RischioPerOp > 0.0) return RischioPerOp;
   if(Profilo == PROFILO_B) return 0.75;
   if(Profilo == PROFILO_C) return 0.75;
   return 0.53;                       // D: solo long, drawdown piu' grande
}

bool ChiudeOgniSera() { return (Profilo != PROFILO_B); }
bool SoloLong()       { return (Profilo == PROFILO_D); }

string NomeProfilo()
{
   if(Profilo == PROFILO_B) return "B";
   if(Profilo == PROFILO_C) return "C";
   return "D";
}

//+------------------------------------------------------------------+
int OnInit()
{
   scartoUtc = CalcolaScartoUtc();
   PrintFormat("VWAP Reclaim · profilo %s · obiettivo 1:%.0f · rischio %.2f%% · "
               "scarto server-UTC %+d s (%.1f h)",
               NomeProfilo(), ObiettivoR(), RischioProfilo(),
               scartoUtc, scartoUtc / 3600.0);
   if(scartoUtc == 0)
      Print("ATTENZIONE: scarto server-UTC nullo. Se il broker NON e' su UTC, "
            "tutti gli orari sono sbagliati: verificare prima di operare.");

   ParametriUfficiali(par);
   par.impulsoMin   = ImpulsoMinimo;
   par.buffer       = BufferStop;
   par.rischioMin   = RischioMinimo;
   par.rischioMax   = RischioMassimo;
   par.mediaAtrRif  = MedianaAtrRif;
   par.oraInizio    = OraInizio;
   par.oraFine      = OraFine;
   par.oraChiusura  = OraChiusura;
   par.maxAlGiorno  = MaxAlGiorno;
   par.attesaMinuti = AttesaMinuti;
   par.soloLong     = SoloLong();
   if(par.mediaAtrRif <= 0.0)
   {
      // Senza mediana, nei mesi agitati le soglie diventerebbero indefinite e
      // l'EA smetterebbe di aprire IN SILENZIO. Meglio non partire.
      Print("ERRORE: MedianaAtrRif deve essere > 0 (2020-2024 = 25.5968).");
      return INIT_PARAMETERS_INCORRECT;
   }
   MotoreInit(motore, par);

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(50);
   saldoIniziale = AccountInfoDouble(ACCOUNT_BALANCE);

   if(ScriviCsv) ApriCsv();
   if(!CaricaStoria()) return INIT_FAILED;
   RecuperaPosizione();
   avviato = true;
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//|  Riavvio con una posizione gia' aperta                           |
//|                                                                  |
//|  Sul VPS succede: il terminale si riavvia, l'EA riparte da zero  |
//|  e la posizione della B — che puo' restare aperta per giorni —   |
//|  si troverebbe senza nessuno che le muove il trailing. Il        |
//|  rischio iniziale e il massimo favorevole non si possono         |
//|  dedurre dalla posizione (lo stop nel frattempo si e' mosso):    |
//|  vengono salvati fra le variabili globali del terminale, che     |
//|  sopravvivono al riavvio.                                        |
//+------------------------------------------------------------------+
string ChiaveGv(const string campo)
{
   return StringFormat("VR_%I64d_%s", MagicNumber, campo);
}

void SalvaStatoPosizione()
{
   GlobalVariableSet(ChiaveGv("entry"),   entryCorrente);
   GlobalVariableSet(ChiaveGv("rischio"), rischioCorrente);
   GlobalVariableSet(ChiaveGv("denaro"),  denaroRischiato);
   GlobalVariableSet(ChiaveGv("mfe"),     estremoFav);
   GlobalVariableSet(ChiaveGv("aperta"),  (double)apertaIl);
   GlobalVariableSet(ChiaveGv("lato"),    (double)latoCorrente);
   GlobalVariableSet(ChiaveGv("trail"),   trailArmato ? 1.0 : 0.0);
}

void RecuperaPosizione()
{
   ticketCorrente = TrovaPosizione();
   if(ticketCorrente == 0) return;
   if(!PositionSelectByTicket(ticketCorrente)) { ticketCorrente = 0; return; }

   entryCorrente = PositionGetDouble(POSITION_PRICE_OPEN);
   latoCorrente  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                   ? VR_LONG : VR_SHORT;
   if(GlobalVariableCheck(ChiaveGv("rischio")))
   {
      entryCorrente   = GlobalVariableGet(ChiaveGv("entry"));
      rischioCorrente = GlobalVariableGet(ChiaveGv("rischio"));
      denaroRischiato = GlobalVariableGet(ChiaveGv("denaro"));
      estremoFav      = GlobalVariableGet(ChiaveGv("mfe"));
      apertaIl        = (datetime)GlobalVariableGet(ChiaveGv("aperta"));
      latoCorrente    = (int)GlobalVariableGet(ChiaveGv("lato"));
      trailArmato     = (GlobalVariableGet(ChiaveGv("trail")) > 0.5);
      PrintFormat("Ripresa posizione %I64u · entry %.2f · rischio %.2f $ · "
                  "MFE %.2f", ticketCorrente, entryCorrente, rischioCorrente,
                  estremoFav);
      return;
   }
   // Senza le variabili globali il rischio iniziale non e' ricostruibile: lo
   // stop puo' essersi gia' mosso. Meglio dirlo che inventare un numero.
   rischioCorrente = MathAbs(entryCorrente - PositionGetDouble(POSITION_SL));
   denaroRischiato = 0.0;
   estremoFav = entryCorrente;
   apertaIl = (datetime)PositionGetInteger(POSITION_TIME);
   Print("ATTENZIONE: posizione aperta trovata senza lo stato salvato. Il "
         "rischio iniziale e' stato dedotto dallo stop ATTUALE, che potrebbe "
         "essere gia' stato spostato: trailing e contabilita' in R di QUESTA "
         "posizione non sono affidabili. Le successive tornano corrette.");
}

void OnDeinit(const int reason)
{
   PrintFormat("Chiusura EA (motivo %d). R cumulati %.2f · giornate D1 viste %d",
               reason, rCumulato, motore.d1.n);
}

//+------------------------------------------------------------------+
//|  Riscaldamento: senza abbastanza giornate l'EA opera DIVERSO     |
//|                                                                  |
//|  Il filtro di fondo vuole 50 giornate, l'ATR 14, e la            |
//|  classificazione dei mesi agitati confronta la volatilita'       |
//|  recente con la mediana di TUTTA la storia precedente e sotto    |
//|  250 giornate risponde "normale". Con poca storia l'EA userebbe  |
//|  soglie in dollari dove il motore le riscala: stesso codice,     |
//|  operazioni diverse, e nessun messaggio a dirlo.                 |
//+------------------------------------------------------------------+
bool CaricaStoria()
{
   MqlRates r[];
   ArraySetAsSeries(r, false);
   const datetime da = TimeCurrent() - (datetime)GiorniStoria * 86400;
   const int n = CopyRates(_Symbol, PERIOD_M1, da, TimeCurrent(), r);
   if(n <= 0)
   {
      Print("ERRORE: nessuna candela M1 caricata. Aumentare 'Max bars in chart' "
            "e scaricare lo storico M1 del simbolo.");
      return false;
   }
   Esito e;
   for(int i = 0; i < n; i++)
   {
      const datetime t = InUtc(r[i].time);
      if(MotorePasso(motore, t, r[i].open, r[i].high, r[i].low, r[i].close,
                     (double)r[i].tick_volume, e))
      {
         // i segnali storici non si operano, ma consumano i posti del giorno
         // esattamente come nel motore: altrimenti al primo giorno di
         // esercizio l'EA si troverebbe tre posti liberi che non ha
         if(e.consuma) MotoreRegistraIngresso(motore, e.istante);
      }
      ultimaM1 = r[i].time;
   }
   PrintFormat("Storia: %d candele M1, %d giornate vere, riscaldamento %s",
               n, motore.d1.n,
               MotoreRiscaldamentoOk(motore) ? "COMPLETO" : "INSUFFICIENTE");
   if(!MotoreRiscaldamentoOk(motore))
      PrintFormat("ATTENZIONE: servono %d giornate e ce ne sono %d. L'EA NON "
                  "aprira' finche' non arriva a quel numero.",
                  VR_MIN_STORIA_ATR, motore.d1.n);
   return true;
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!avviato) return;
   GestisciPosizione();

   // il segnale si valuta su candele M1 CHIUSE: la barra 0 e' in corso
   const datetime tUltima = iTime(_Symbol, PERIOD_M1, 1);
   if(tUltima <= ultimaM1) return;

   MqlRates r[];
   ArraySetAsSeries(r, false);
   const int n = CopyRates(_Symbol, PERIOD_M1, ultimaM1 + 60, tUltima, r);
   if(n <= 0) return;

   Esito e;
   for(int i = 0; i < n; i++)
   {
      ultimaM1 = r[i].time;
      if(!MotorePasso(motore, InUtc(r[i].time), r[i].open, r[i].high, r[i].low,
                      r[i].close, (double)r[i].tick_volume, e))
         continue;
      if(ScriviCsv && (LogTutteLeBarre || e.lato != VR_NESSUNO)) LogSegnale(e);
      if(!e.consuma) continue;
      MotoreRegistraIngresso(motore, e.istante);
      if(e.apre) Apri(e);
   }
}

//+------------------------------------------------------------------+
//|  Apertura                                                        |
//+------------------------------------------------------------------+
void Apri(const Esito &e)
{
   if(Fermo()) return;
   if(TrovaPosizione() != 0) return;                    // una alla volta

   const double lotti = Lotti(e.rischio);
   if(lotti <= 0.0)
   {
      // Sotto il lotto minimo l'operazione SI SALTA. Forzarla a 0,01
      // significherebbe rischiare il triplo del previsto, e in una sfida il
      // vincolo e' sopravvivere, non fare numero.
      PrintFormat("saltata: lotto sotto il minimo (rischio %.2f $)", e.rischio);
      return;
   }
   const bool  lungo  = (e.lato == VR_LONG);
   const double prezzo = lungo ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                               : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double stop  = NormalizeDouble(e.stop, _Digits);
   const double tp    = NormalizeDouble(lungo ? e.entry + ObiettivoR() * e.rischio
                                              : e.entry - ObiettivoR() * e.rischio,
                                        _Digits);

   const bool ok = lungo ? trade.Buy(lotti, _Symbol, 0.0, stop, tp, "vwap-reclaim")
                         : trade.Sell(lotti, _Symbol, 0.0, stop, tp, "vwap-reclaim");
   if(!ok)
   {
      PrintFormat("apertura fallita: retcode %d (%s)", trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
      return;
   }
   // il ticket della POSIZIONE non e' quello dell'ordine: su conto netting
   // coincidono, su hedging no. Si cerca fra le posizioni col nostro magic.
   ticketCorrente  = TrovaPosizione();
   latoCorrente    = e.lato;
   entryCorrente   = e.entry;
   stopIniziale    = e.stop;
   rischioCorrente = e.rischio;
   denaroRischiato = lotti * e.rischio /
                     SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE) *
                     SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   estremoFav      = prezzo;
   apertaIl        = TimeCurrent();
   trailArmato     = false;
   SalvaStatoPosizione();
   PrintFormat("APERTA %s %.2f lotti · entry %.2f · stop %.2f · rischio %.2f $ · "
               "obiettivo %.2f", lungo ? "LONG" : "SHORT", lotti, e.entry,
               e.stop, e.rischio, tp);
}

double Lotti(const double distanzaStop)
{
   const double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   const double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0 || tickValue <= 0.0 || distanzaStop <= 0.0) return 0.0;

   const double denaro = AccountInfoDouble(ACCOUNT_EQUITY) * RischioProfilo() / 100.0;
   const double perLotto = distanzaStop / tickSize * tickValue;
   if(perLotto <= 0.0) return 0.0;

   const double passo = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   const double minimo = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double massimo = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotti = denaro / perLotto;
   if(passo > 0.0) lotti = MathFloor(lotti / passo) * passo;   // per DIFETTO
   if(lotti < minimo) return 0.0;                              // si salta
   if(lotti > massimo) lotti = massimo;
   return lotti;
}

//+------------------------------------------------------------------+
//|  Gestione: e' qui che i tre profili si separano                  |
//|                                                                  |
//|  Sulla B il trailing NON e' un dettaglio: l'obiettivo 1:8 viene  |
//|  toccato nel 4% delle operazioni, il 29% le chiude lo stop       |
//|  mobile in guadagno. Se il trailing e' implementato male la B    |
//|  non perde qualche punto, smette di funzionare.                  |
//+------------------------------------------------------------------+
void GestisciPosizione()
{
   if(!PositionSelectByTicket(ticketCorrente))
   {
      if(ticketCorrente != 0) ChiusuraRilevata();
      return;
   }
   if(rischioCorrente <= 0.0) return;

   const bool lungo = (latoCorrente == VR_LONG);
   const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   const double corrente = lungo ? bid : ask;
   const double primaFav = estremoFav;
   estremoFav = lungo ? MathMax(estremoFav, corrente) : MathMin(estremoFav, corrente);
   if(estremoFav != primaFav) SalvaStatoPosizione();

   const double mfeR = lungo ? (estremoFav - entryCorrente) / rischioCorrente
                             : (entryCorrente - estremoFav) / rischioCorrente;
   const double rOra = lungo ? (corrente - entryCorrente) / rischioCorrente
                             : (entryCorrente - corrente) / rischioCorrente;
   const double stopAttuale = PositionGetDouble(POSITION_SL);

   if(Profilo == PROFILO_B)
   {
      // da +3R lo stop insegue l'MFE a distanza 2R, e non torna mai indietro
      if(mfeR >= 3.0)
      {
         const double nuovo = lungo ? estremoFav - 2.0 * rischioCorrente
                                    : estremoFav + 2.0 * rischioCorrente;
         if((lungo && nuovo > stopAttuale) || (!lungo && nuovo < stopAttuale))
            SpostaStop(nuovo);
         trailArmato = true;
      }
   }
   else if(Profilo == PROFILO_D)
   {
      // quando l'MFE tocca +3R lo stop va a +0,50 R e li' resta.
      // +0,50 R e non il pareggio esatto: due dollari sopra uno stop da 2 $
      // sono un R intero, sopra uno da 15 $ sono un settimo — in dollari
      // fissi si applicherebbe una regola diversa ogni mese.
      if(!trailArmato && mfeR >= 3.0)
      {
         const double nuovo = lungo ? entryCorrente + 0.5 * rischioCorrente
                                    : entryCorrente - 0.5 * rischioCorrente;
         SpostaStop(nuovo);
         trailArmato = true;
      }
   }
   // PROFILO_C: nessuno spostamento. Misurato: portare lo stop a +1R fa
   // scendere la C da +86,6 a +47,3 R. Il 1:2 secco vive delle operazioni
   // che vanno dritte al bersaglio.

   const datetime utc = InUtc(TimeCurrent());
   const int ora = VrOraDi(utc);
   const int giornoSettimana = (int)(((utc / 86400) + 4) % 7);   // 0=domenica

   if(ChiudeOgniSera())
   {
      if(ora >= OraChiusura) Chiudi("chiusura serale 21:00 UTC");
      return;
   }
   // profilo B: il venerdi' alle 21:00 UTC si attraversa il fine settimana
   // solo se l'operazione e' sopra +1R. Lo stop NON si tocca: sopra +3R il
   // trailing lo ha gia' portato ad almeno +1R, e spostarlo alla chiusura del
   // venerdi' azzererebbe il margine che serve ad assorbire il salto del
   // lunedi' (appendice AT).
   if(giornoSettimana == 5 && ora >= OraChiusura && rOra <= 1.0)
      Chiudi("venerdi' sera sotto +1R");
   else if(apertaIl > 0 && (TimeCurrent() - apertaIl) > 30 * 86400)
      Chiudi("scadenza 30 giorni");
}

void SpostaStop(const double nuovo)
{
   const double tp = PositionGetDouble(POSITION_TP);
   if(!trade.PositionModify(ticketCorrente, NormalizeDouble(nuovo, _Digits), tp))
      PrintFormat("spostamento stop fallito: retcode %d", trade.ResultRetcode());
}

void Chiudi(const string motivo)
{
   if(trade.PositionClose(ticketCorrente))
      PrintFormat("chiusa: %s", motivo);
   else
      PrintFormat("chiusura fallita (%s): retcode %d", motivo, trade.ResultRetcode());
}

//--- La posizione non c'e' piu': si contabilizza il risultato in R.
void ChiusuraRilevata()
{
   double r = 0.0;
   if(HistorySelect(apertaIl - 60, TimeCurrent() + 60))
   {
      double netto = 0.0;
      for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
      {
         const ulong d = HistoryDealGetTicket(i);
         if(HistoryDealGetInteger(d, DEAL_MAGIC) != MagicNumber) continue;
         netto += HistoryDealGetDouble(d, DEAL_PROFIT)
                + HistoryDealGetDouble(d, DEAL_SWAP)
                + HistoryDealGetDouble(d, DEAL_COMMISSION);
      }
      // 1 R e' quello che si rischiava ALL'APERTURA, non il rischio che si
      // correrebbe adesso: usare l'equity corrente farebbe misurare le
      // operazioni con un metro che cambia dopo ogni vittoria e ogni perdita
      if(denaroRischiato > 0.0) r = netto / denaroRischiato;
   }
   rCumulato += r;
   rMassimo = MathMax(rMassimo, rCumulato);
   PrintFormat("posizione chiusa · %.2f R · cumulati %.2f R (massimo %.2f)",
               r, rCumulato, rMassimo);
   ticketCorrente = 0; latoCorrente = 0; rischioCorrente = 0.0;
   denaroRischiato = 0.0; trailArmato = false; apertaIl = 0;
   GlobalVariableDel(ChiaveGv("entry"));   GlobalVariableDel(ChiaveGv("rischio"));
   GlobalVariableDel(ChiaveGv("denaro"));  GlobalVariableDel(ChiaveGv("mfe"));
   GlobalVariableDel(ChiaveGv("aperta"));  GlobalVariableDel(ChiaveGv("lato"));
   GlobalVariableDel(ChiaveGv("trail"));
}

//--- La posizione aperta da QUESTO EA su QUESTO simbolo, se c'e'.
//    Ciascuna istanza gestisce solo le proprie: due EA sullo stesso conto
//    senza distinguerle si chiuderebbero le operazioni a vicenda.
ulong TrovaPosizione()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      const ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      return t;
   }
   return 0;
}

//+------------------------------------------------------------------+
//|  Spegnimento                                                     |
//|                                                                  |
//|  La soglia in R e' la PROPOSTA di AVVIO-MT5-VPS.md §4: -15 R e'  |
//|  oltre il peggio del periodo buono (12,6 R per la B) ed entro il |
//|  peggio del periodo cattivo (87,4 R). Va confermata prima di     |
//|  partire: senza una soglia decisa a freddo la decisione la       |
//|  prende la paura.                                                |
//+------------------------------------------------------------------+
bool Fermo()
{
   if(fermato) return true;
   if(LimiteEquityPct > 0.0 &&
      AccountInfoDouble(ACCOUNT_BALANCE) < saldoIniziale * LimiteEquityPct / 100.0)
   {
      fermato = true;
      PrintFormat("FERMO: saldo %.2f sotto il %.0f%% di %.2f",
                  AccountInfoDouble(ACCOUNT_BALANCE), LimiteEquityPct, saldoIniziale);
   }
   if(FermaADrawdownR > 0.0 && (rMassimo - rCumulato) >= FermaADrawdownR)
   {
      fermato = true;
      PrintFormat("FERMO: discesa di %.2f R dal massimo (soglia %.2f R)",
                  rMassimo - rCumulato, FermaADrawdownR);
   }
   return fermato;
}

//+------------------------------------------------------------------+
//|  Il log — senza questo non si puo' fare il confronto             |
//|                                                                  |
//|  Ogni segnale VALUTATO, non solo quelli aperti, con quali delle  |
//|  sette condizioni erano vere. E' il file che si mette accanto a  |
//|  quello del motore Python per scoprire dove i due divergono: se  |
//|  si registrassero solo le operazioni aperte, di una divergenza   |
//|  si vedrebbe l'effetto e mai la causa.                           |
//+------------------------------------------------------------------+
void ApriCsv()
{
   fileSegnali = StringFormat("vwap_reclaim_%s_%I64d.csv", NomeProfilo(), MagicNumber);
   const int h = FileOpen(fileSegnali, FILE_WRITE | FILE_CSV | FILE_ANSI |
                          FILE_COMMON, ',');
   if(h == INVALID_HANDLE)
   {
      PrintFormat("CSV non apribile (%s): errore %d", fileSegnali, GetLastError());
      return;
   }
   FileWrite(h, "utc", "barra_utc", "lato", "apre", "consuma", "entry", "stop",
             "rischio", "spinta", "vwap", "soglia_impulso", "agitato",
             "c1_orario", "c2_struttura", "c3a_conferme", "c3b_ritracciamento",
             "c4a_impulso", "c4b_reclaim", "c5_macro", "c6_rischio",
             "c7_frequenza", "st_h6", "st_h2", "st_m33", "st_h12", "st_m12",
             "bid", "ask");
   FileClose(h);
   csvOk = true;
}

void LogSegnale(const Esito &e)
{
   if(!csvOk) return;
   const int h = FileOpen(fileSegnali, FILE_READ | FILE_WRITE | FILE_CSV |
                          FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h,
             TimeToString(e.istante, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
             TimeToString(e.barra, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
             e.lato == VR_LONG ? "long" : (e.lato == VR_SHORT ? "short" : "-"),
             e.apre ? 1 : 0, e.consuma ? 1 : 0,
             DoubleToString(e.entry, 3), DoubleToString(e.stop, 3),
             DoubleToString(e.rischio, 3), DoubleToString(e.spinta, 3),
             DoubleToString(e.vwap, 3), DoubleToString(e.sogliaImpulso, 3),
             e.agitato ? 1 : 0,
             e.c1_orario ? 1 : 0, e.c2_struttura ? 1 : 0, e.c3a_conferme ? 1 : 0,
             e.c3b_ritracciamento ? 1 : 0, e.c4a_impulso ? 1 : 0,
             e.c4b_reclaim ? 1 : 0, e.c5_macro ? 1 : 0, e.c6_rischio ? 1 : 0,
             e.c7_frequenza ? 1 : 0,
             e.stH6, e.stH2, e.stM33, e.stH12, e.stM12,
             DoubleToString(SymbolInfoDouble(_Symbol, SYMBOL_BID), 3),
             DoubleToString(SymbolInfoDouble(_Symbol, SYMBOL_ASK), 3));
   FileClose(h);
}
//+------------------------------------------------------------------+
