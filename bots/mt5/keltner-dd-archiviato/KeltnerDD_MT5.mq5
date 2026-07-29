//+------------------------------------------------------------------+
//|  KELTNER DD - v1.0  (2026-07-06)                                 |
//|  Base = Keltner Impulse v2 (MT5) + modulo "DD Add":              |
//|  quando la 1a posizione e' in perdita non realizzata pari a      |
//|  DDAddPercent% del balance, apre UNA seconda posizione stessa    |
//|  direzione e stessa size, con lo STESSO SL e lo STESSO TP        |
//|  (livelli di prezzo condivisi). Max 2 posizioni.                 |
//|                                                                  |
//|  ATTENZIONE (onesta' quant): aggiungere in DD e' una martingala/ |
//|  media al ribasso. NON crea edge: rende l'equity piu' liscia ma  |
//|  concentra il rischio nelle code. Su una base gia' negativa su   |
//|  tick reali va trattato con sospetto: il backtest serve a        |
//|  MISURARE il rischio di coda, non a "far bello" il grafico.      |
//|                                                                  |
//|  RICHIEDE CONTO HEDGING (due posizioni stesso simbolo).          |
//|  SOLO DEMO / BACKTEST.                                           |
//|                                                                  |
//|  Backtest: XAUUSD M10, "Every tick based on real ticks",         |
//|  1000 EUR, 1:500. (NB: FP ha ~8 mesi di tick reali XAUUSD.)      |
//|  CSV in Common\Files\keltnerdd\  (cartella propria, non tocca    |
//|  i CSV del Keltner base).                                        |
//+------------------------------------------------------------------+
#property copyright "Trading Bot Factory - KeltnerDD"
#property version   "1.00"

#include <Trade\Trade.mqh>

//---------------- Tipi ----------------
enum ENUM_ATR_SMOOTH
{
   ATR_WILDER      = 0,   // Wilder (iATR nativo, = TradingView di default)
   ATR_EXPONENTIAL = 1    // Exponential (EMA della True Range, = run cTrader)
};

//---------------- Parametri ----------------
input group "Keltner"
input int             EmaPeriod    = 20;              // EMA Period (middle)
input int             AtrPeriod    = 10;              // ATR Period (bande)
input ENUM_ATR_SMOOTH AtrSmoothing = ATR_EXPONENTIAL; // ATR smoothing
input double          MultUp       = 2.0;             // Mult banda superiore
input double          MultDown     = 2.0;             // Mult banda inferiore

input group "Strategia"
input double ImpulseTargetPercent = 80.0;  // Target % impulso (TP)  [setup TP80]
input double RiskReward           = 1.2;   // Risk/Reward (TP = RR * SL) [setup RR1.2]
input int    ExpiryBars           = 20;    // Scadenza ordine (candele)
input double MinStopPrice         = 0.0;   // Min SL in PREZZO (oro: 5.0 = 500 pip cTrader; 0=off)
input bool   ReplaceOnOutsideClose= false; // true = VECCHIA logica (sostituzione su chiusura fuori banda)

input group "DD Add (novita' del bot)"
input bool   EnableDDAdd   = true;   // Apri una 2a posizione quando la 1a e' in DD
input double DDAddPercent  = 0.5;    // DD della 1a posizione (% del balance) che apre la 2a

input group "Rischio"
input double RiskPercent        = 1.0;     // Rischio % per trade (1a posizione)
input double EquityGuardPercent = 50.0;    // Stop se balance < % iniziale (0=off)

input group "Costi"
input double CommissionPerLotRT = 6.0;     // Commissione $/lotto round-turn (usata SOLO se il broker non la applica)

input group "Filtro Trend HTF"
input bool             UseTrendFilter = false;       // OFF di default: comportamento invariato
input ENUM_TIMEFRAMES  TrendTimeframe = PERIOD_D1;   // Timeframe alto per la MA di trend
input int              TrendMaPeriod  = 200;         // Periodo MA (a priori: NON ottimizzare sui dati)

input group "Log"
input bool   EnableCsv   = true;           // Scrivi CSV
input bool   DrawChannel = false;          // Disegna Keltner (SOLO test corti in visuale)
input string LogSubfolder= "keltnerdd";    // Sottocartella log in Common\Files
input long   MagicNumber = 20260706;       // Magic number (diverso dal Keltner base!)

//---------------- Stato interno ----------------
CTrade   trade;
int      emaHandle = INVALID_HANDLE;
int      atrHandle = INVALID_HANDLE;
int      trendHandle = INVALID_HANDLE;

datetime lastBarTime      = 0;
long     barCounter       = 0;
long     placedBarCounter = 0;
bool     pendingIsLong    = false;
double   pendingExtreme   = 0.0;
ulong    pendingTicket    = 0;
long     curPosId         = -1;    // position id della 1a posizione
double   initialBalance   = 0.0;
bool     halted           = false;
bool     csvOk            = false;
int      nextId           = 1;

// --- Stato DD Add (2a posizione) ---
bool     addDone          = false; // gia' aggiunta la 2a per il basket corrente
bool     awaitingAddFill  = false; // ordine add inviato, in attesa del fill
bool     haveAdd          = false; // 2a posizione aperta
long     addPosId         = -1;    // position id della 2a posizione
double   addSL            = 0.0;   // SL/TP condivisi (dalla 1a posizione)
double   addTP            = 0.0;

int cntSignals=0, cntPlaced=0, cntReplaced=0, cntExpired=0, cntFilled=0, cntSkipped=0, cntAdds=0;

string tradesFile="", skipsFile="";

struct TradeInfoS
{
   int      id;
   string   direction;
   datetime signalTime, fillTime, exitTime;
   double   signalClose, middle, impulse;
   double   slDist, tpDist, slPts, tpPts;
   double   entryPlanned, entryActual, spreadPtsFill;
   double   rawLots, lots, filledLots;
   double   theoRisk, realRisk, entryCommission;
};
TradeInfoS cur;      // 1a posizione
TradeInfoS curAdd;   // 2a posizione (add)
bool haveCur = false;

// stato disegno canale
double prevU=0, prevM=0, prevL=0;
datetime prevT=0;

//+------------------------------------------------------------------+
int OnInit()
{
   emaHandle = iMA(_Symbol, _Period, EmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   atrHandle = iATR(_Symbol, _Period, AtrPeriod);
   if(emaHandle==INVALID_HANDLE || atrHandle==INVALID_HANDLE)
   {
      Print("ERRORE creazione indicatori");
      return INIT_FAILED;
   }
   if(UseTrendFilter)
   {
      trendHandle = iMA(_Symbol, TrendTimeframe, TrendMaPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(trendHandle==INVALID_HANDLE){ Print("ERRORE creazione MA trend HTF"); return INIT_FAILED; }
      Print("Filtro trend HTF ATTIVO: EMA(", TrendMaPeriod, ") su ", EnumToString(TrendTimeframe));
   }
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(50);

   // Il DD Add richiede conto HEDGING (due posizioni stesso simbolo)
   if(EnableDDAdd)
   {
      long mode = (long)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
      if(mode != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
         Print("ATTENZIONE: conto NON hedging. Il DD Add potrebbe fondere le posizioni (netting). Usa un conto/backtest HEDGING.");
   }

   initialBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   if(EnableCsv) InitCsv();

   Print("KeltnerDD avviato su ", _Symbol, " ", EnumToString(_Period),
         " | balance ", DoubleToString(initialBalance,2),
         " | DDAdd ", (EnableDDAdd?"ON @"+DoubleToString(DDAddPercent,2)+"%":"OFF"));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Flush a fine run -> niente survivorship bias nel CSV
   if(haveCur && curPosId>0) FlushOpen(cur, curPosId);
   else if(haveCur && pendingTicket>0)
      LogSkip(cur.id, cur.direction, "PENDING_AT_STOP", "ordine pendente non eseguito a fine run");
   if(haveAdd && addPosId>0) FlushOpen(curAdd, addPosId);

   PrintFormat("RIEPILOGO -> segnali:%d ordini:%d sostituiti:%d scaduti:%d eseguiti:%d add:%d scartati:%d",
               cntSignals, cntPlaced, cntReplaced, cntExpired, cntFilled, cntAdds, cntSkipped);
}

// scrive la riga di una posizione ancora aperta a fine run
void FlushOpen(TradeInfoS &ti, long posId)
{
   if(!PositionSelectByTicket((ulong)posId)) return;
   ti.exitTime = TimeCurrent();
   double profit = PositionGetDouble(POSITION_PROFIT);
   double swap   = PositionGetDouble(POSITION_SWAP);
   double net    = profit + swap + ti.entryCommission;
   double pts    = (ti.direction=="LONG")
                 ? (PositionGetDouble(POSITION_PRICE_CURRENT)-ti.entryActual)/_Point
                 : (ti.entryActual-PositionGetDouble(POSITION_PRICE_CURRENT))/_Point;
   double r = (ti.realRisk>0) ? net/ti.realRisk : 0.0;
   WriteTradeRow(ti, net, profit, ti.entryCommission, swap, pts, r, "OPEN_AT_STOP");
}

//+------------------------------------------------------------------+
void OnTick()
{
   // 1) Controllo DD Add ad OGNI tick (piu' fedele a "quando e' in DD")
   CheckDDAdd();

   // 2) Logica di segnale solo a candela chiusa (niente look-ahead)
   datetime t0 = iTime(_Symbol, _Period, 0);
   if(t0==lastBarTime) return;
   lastBarTime = t0;
   barCounter++;
   OnNewBar();
}

//+------------------------------------------------------------------+
//  DD ADD: se la 1a posizione e' in perdita >= DDAddPercent% del balance,
//  apre UNA seconda posizione a mercato, stessa direzione/size, con lo
//  STESSO SL e lo STESSO TP (livelli condivisi). Max 2 posizioni.
//+------------------------------------------------------------------+
void CheckDDAdd()
{
   if(!EnableDDAdd || halted) return;
   if(curPosId<=0) return;                         // 1a non ancora aperta
   if(addDone || haveAdd || awaitingAddFill) return; // gia' aggiunta / in corso
   if(!PositionSelectByTicket((ulong)curPosId)) return;

   double bal     = AccountInfoDouble(ACCOUNT_BALANCE);
   if(bal<=0) return;
   double floatPL = PositionGetDouble(POSITION_PROFIT);   // P&L non realizzato (senza swap/comm)
   double trigger = -bal*DDAddPercent/100.0;
   if(floatPL > trigger) return;                          // non ancora abbastanza in DD

   bool   isLong = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY);
   addSL = PositionGetDouble(POSITION_SL);
   addTP = PositionGetDouble(POSITION_TP);
   double lots = cur.filledLots;                          // stessa size della 1a
   if(lots<=0) return;

   awaitingAddFill = true;
   string cmt = "DDADD_"+IntegerToString(cur.id);
   double px = isLong ? SymbolInfoDouble(_Symbol,SYMBOL_ASK) : SymbolInfoDouble(_Symbol,SYMBOL_BID);
   bool ok = isLong ? trade.Buy (lots, _Symbol, px, addSL, addTP, cmt)
                    : trade.Sell(lots, _Symbol, px, addSL, addTP, cmt);

   if(!ok || (trade.ResultRetcode()!=TRADE_RETCODE_DONE && trade.ResultRetcode()!=TRADE_RETCODE_PLACED))
   {
      awaitingAddFill = false;
      addDone = true;   // niente retry a raffica su questo basket (evita spam nei skip)
      cntSkipped++;
      LogSkip(100000+cur.id, isLong?"Buy":"Sell", "ADD_FAILED",
              StringFormat("retcode=%d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription()));
      return;
   }

   // Prepara le info dell'add (entry/risk verranno completate al fill)
   ZeroMemory(curAdd);
   curAdd.id          = 100000 + cur.id;   // id in alto = ADD; (id-100000) = id della 1a
   curAdd.direction   = isLong ? "LONG" : "SHORT";
   curAdd.signalClose = iClose(_Symbol,_Period,1);
   curAdd.middle      = cur.middle;
   curAdd.impulse     = cur.impulse;
   addDone = true;
   cntAdds++;
   LogSkip(cur.id, curAdd.direction, "DD_ADD",
           StringFormat("2a posizione: floatPL=%.2f <= %.2f (%.2f%% di %.2f)", floatPL, trigger, DDAddPercent, bal));
}

//+------------------------------------------------------------------+
void OnNewBar()
{
   if(Bars(_Symbol,_Period) < MathMax(EmaPeriod,AtrPeriod)+2) return;

   double emaB[1];
   if(CopyBuffer(emaHandle,0,1,1,emaB)<1) return;
   double middle = emaB[0];

   double atr;
   if(AtrSmoothing==ATR_WILDER)
   {
      double atrB[1];
      if(CopyBuffer(atrHandle,0,1,1,atrB)<1) return;
      atr = atrB[0];
   }
   else atr = ExpAtr();
   if(atr<=0) return;

   double close = iClose(_Symbol,_Period,1);
   double high  = iHigh (_Symbol,_Period,1);
   double low   = iLow  (_Symbol,_Period,1);
   double upper = middle + MultUp*atr;
   double lower = middle - MultDown*atr;

   if(DrawChannel) DrawKeltner(upper, middle, lower);

   ulong pending = FindOurPending();
   bool  open    = HaveOpenPosition();

   if(halted) return;
   if(EquityGuardPercent>0 && AccountInfoDouble(ACCOUNT_BALANCE) < initialBalance*EquityGuardPercent/100.0)
   {
      halted = true;
      if(pending>0){ trade.OrderDelete(pending); haveCur=false; pendingTicket=0; }
      LogSkip(0,"-","EQUITY_GUARD",
              StringFormat("balance %.2f < %.0f%% del capitale iniziale %.2f: bot fermato",
                           AccountInfoDouble(ACCOUNT_BALANCE), EquityGuardPercent, initialBalance));
      Print("EQUITY GUARD: balance sotto soglia. Il bot smette di aprire trade.");
      return;
   }

   // Nessun nuovo setup mentre una posizione (1a o add) e' aperta
   if(open) return;

   if(pending==0)
   {
      bool ls = close>upper;
      bool ss = close<lower;
      if(ls || ss)
      {
         cntSignals++;
         if(!TrendAllows(ls, close))
         {
            cntSkipped++;
            LogSkip(nextId, ls?"Buy":"Sell", "TREND_FILTER",
                    StringFormat("%s bloccato dal filtro trend HTF", ls?"LONG":"SHORT"));
            return;
         }
         PlaceSetup(ls, middle, high, low, 0);
      }
      return;
   }

   // Ordine pendente presente: due modalita' di sostituzione (A/B)
   if(ReplaceOnOutsideClose)
   {
      bool ls = close>upper;
      bool ss = close<lower;
      if(ls || ss)
      {
         cntSignals++;
         if(!TrendAllows(ls, close)) return;
         PlaceSetup(ls, middle, high, low, pending);
         return;
      }
   }
   else
   {
      bool exceeded = pendingIsLong ? (close>pendingExtreme) : (close<pendingExtreme);
      if(exceeded)
      {
         if(!TrendAllows(pendingIsLong, close)) return;
         PlaceSetup(pendingIsLong, middle, high, low, pending);
         return;
      }
   }

   if(barCounter - placedBarCounter >= ExpiryBars)
   {
      trade.OrderDelete(pending);
      cntExpired++;
      LogSkip(cur.id, pendingIsLong?"Buy":"Sell", "EXPIRED",
              StringFormat("non eseguito entro %d candele", ExpiryBars));
      haveCur=false; pendingTicket=0;
   }
}

//+------------------------------------------------------------------+
void PlaceSetup(bool isLong, double middle, double high, double low, ulong existing)
{
   double extreme = isLong ? high : low;
   double impulse = MathAbs(extreme - middle);
   double tpDist  = ImpulseTargetPercent/100.0*impulse;
   double slDist  = tpDist/RiskReward;
   double entry   = NormalizeDouble(middle, _Digits);

   if(MinStopPrice>0 && slDist<MinStopPrice)
   {
      cntSkipped++;
      LogSkip(nextId, isLong?"Buy":"Sell", "MIN_SL",
              StringFormat("slDist=%.5f < %.5f", slDist, MinStopPrice));
      return;
   }

   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize<=0 || tickValue<=0) return;
   double riskPerLot = slDist/tickSize*tickValue;
   if(riskPerLot<=0) return;

   double targetRisk = AccountInfoDouble(ACCOUNT_BALANCE)*RiskPercent/100.0;
   double rawLots    = targetRisk/riskPerLot;

   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step<=0) step=0.01;
   double lots = MathFloor(rawLots/step)*step;
   lots = NormalizeDouble(lots, 8);

   if(lots<minLot)
   {
      cntSkipped++;
      LogSkip(nextId, isLong?"Buy":"Sell", "MIN_VOLUME",
              StringFormat("lotti calcolati %.4f < min %.2f", rawLots, minLot));
      return;
   }
   if(lots>maxLot) lots=maxLot;
   double realRisk = riskPerLot*lots;

   if(existing>0)
   {
      trade.OrderDelete(existing);
      cntReplaced++;
      LogSkip(cur.id, pendingIsLong?"Buy":"Sell", "REPLACED", "candela chiude oltre l'impulso -> nuovo setup");
      haveCur=false; pendingTicket=0;
   }

   int id = nextId++;
   double sl, tp;
   if(isLong){ sl=NormalizeDouble(entry-slDist,_Digits); tp=NormalizeDouble(entry+tpDist,_Digits); }
   else      { sl=NormalizeDouble(entry+slDist,_Digits); tp=NormalizeDouble(entry-tpDist,_Digits); }

   bool ok;
   if(isLong) ok = trade.BuyLimit (lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, IntegerToString(id));
   else       ok = trade.SellLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, IntegerToString(id));

   if(ok && (trade.ResultRetcode()==TRADE_RETCODE_DONE || trade.ResultRetcode()==TRADE_RETCODE_PLACED))
   {
      pendingTicket    = trade.ResultOrder();
      placedBarCounter = barCounter;
      pendingIsLong    = isLong;
      pendingExtreme   = extreme;
      cntPlaced++;

      cur.id=id;
      cur.direction   = isLong ? "LONG" : "SHORT";
      cur.signalTime  = TimeCurrent();
      cur.signalClose = iClose(_Symbol,_Period,1);
      cur.middle=middle; cur.impulse=impulse;
      cur.slDist=slDist; cur.tpDist=tpDist;
      cur.slPts=slDist/_Point; cur.tpPts=tpDist/_Point;
      cur.entryPlanned=entry; cur.entryActual=0; cur.spreadPtsFill=0;
      cur.rawLots=rawLots; cur.lots=lots; cur.filledLots=0;
      cur.theoRisk=targetRisk; cur.realRisk=realRisk; cur.entryCommission=0;
      cur.fillTime=0; cur.exitTime=0;
      haveCur=true;

      if(DrawChannel)
      {
         datetime t1=iTime(_Symbol,_Period,1);
         string nm=(existing>0 ? "kReBreak" : "kNew")+IntegerToString(id);
         ObjectCreate(0,nm,OBJ_ARROW,0,t1,extreme);
         ObjectSetInteger(0,nm,OBJPROP_ARROWCODE, existing>0 ? 172 : (isLong?233:234));
         ObjectSetInteger(0,nm,OBJPROP_COLOR, existing>0 ? clrOrange : (isLong?clrLime:clrRed));
         ObjectSetInteger(0,nm,OBJPROP_WIDTH,2);
      }
   }
   else
   {
      cntSkipped++;
      LogSkip(id, isLong?"Buy":"Sell", "PLACE_FAILED",
              StringFormat("retcode=%d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription()));
   }
}

//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL)!=_Symbol) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC)!=MagicNumber) return;

   ENUM_DEAL_ENTRY dealEntry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY);

   if(dealEntry==DEAL_ENTRY_IN)
   {
      double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);

      // --- Fill della 2a posizione (add) ---
      if(awaitingAddFill)
      {
         curAdd.fillTime        = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);
         curAdd.entryActual     = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
         curAdd.filledLots      = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
         curAdd.entryCommission = HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
         curAdd.spreadPtsFill   = (SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID))/_Point;
         curAdd.signalTime      = curAdd.fillTime;
         double slD = MathAbs(curAdd.entryActual-addSL);
         double tpD = MathAbs(addTP-curAdd.entryActual);
         curAdd.slDist=slD; curAdd.tpDist=tpD;
         curAdd.slPts=slD/_Point; curAdd.tpPts=tpD/_Point;
         curAdd.entryPlanned=curAdd.entryActual;   // market
         curAdd.rawLots=curAdd.filledLots; curAdd.lots=curAdd.filledLots;
         if(tickSize>0) curAdd.realRisk = slD/tickSize*tickValue*curAdd.filledLots;
         curAdd.theoRisk=curAdd.realRisk;
         addPosId = (long)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
         haveAdd = true;
         awaitingAddFill=false;
         cntFilled++;
         return;
      }

      // --- Fill della 1a posizione ---
      if(!haveCur) { Print("ATTENZIONE fill non mappato: trade NON loggato."); return; }
      cur.fillTime        = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);
      cur.entryActual     = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
      cur.filledLots      = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
      cur.entryCommission = HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
      cur.spreadPtsFill   = (SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID))/_Point;
      if(tickSize>0) cur.realRisk = cur.slDist/tickSize*tickValue*cur.filledLots;
      curPosId = (long)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
      pendingTicket=0;
      cntFilled++;
      // nuovo basket: azzera lo stato dell'add
      addDone=false; haveAdd=false; addPosId=-1; awaitingAddFill=false;
      return;
   }

   if(dealEntry==DEAL_ENTRY_OUT || dealEntry==DEAL_ENTRY_OUT_BY)
   {
      long pid = (long)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);

      if(pid==curPosId && haveCur)      { CloseRow(cur,    trans.deal); haveCur=false; curPosId=-1; return; }
      if(pid==addPosId && haveAdd)      { CloseRow(curAdd, trans.deal); haveAdd=false; addPosId=-1; return; }
   }
}

// Scrive la riga di chiusura di una posizione (1a o add)
void CloseRow(TradeInfoS &ti, ulong deal)
{
   ti.exitTime = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
   double profit = HistoryDealGetDouble(deal, DEAL_PROFIT);
   double swap   = HistoryDealGetDouble(deal, DEAL_SWAP);
   double brokerComm = HistoryDealGetDouble(deal, DEAL_COMMISSION) + ti.entryCommission;
   double comm = (MathAbs(brokerComm) > 0.0001) ? brokerComm : -CommissionPerLotRT*ti.filledLots;
   double closePrice = HistoryDealGetDouble(deal, DEAL_PRICE);

   long reason = HistoryDealGetInteger(deal, DEAL_REASON);
   string reasonS = (reason==DEAL_REASON_SL) ? "StopLoss"
                  : (reason==DEAL_REASON_TP) ? "TakeProfit" : "Other";

   double pts = (ti.direction=="LONG") ? (closePrice-ti.entryActual)/_Point
                                       : (ti.entryActual-closePrice)/_Point;
   double net = profit + swap + comm;
   double r   = (ti.realRisk>0) ? net/ti.realRisk : 0.0;

   WriteTradeRow(ti, net, profit, comm, swap, pts, r, reasonS);
}

//+------------------------------------------------------------------+
//  ATR Exponential = EMA della True Range (replica cTrader "Exponential")
//+------------------------------------------------------------------+
double TrueRange(double h, double l, double prevClose)
{
   double a = h - l;
   double b = MathAbs(h - prevClose);
   double c = MathAbs(l - prevClose);
   return MathMax(a, MathMax(b, c));
}

double ExpAtr()
{
   int need  = AtrPeriod*20;
   int avail = Bars(_Symbol,_Period) - 2;
   int n     = MathMin(need, avail);
   if(n < AtrPeriod+1) return 0.0;

   double hi[], lo[], cl[];
   if(CopyHigh (_Symbol,_Period,1,n+1,hi)<n+1) return 0.0;
   if(CopyLow  (_Symbol,_Period,1,n+1,lo)<n+1) return 0.0;
   if(CopyClose(_Symbol,_Period,1,n+1,cl)<n+1) return 0.0;

   double alpha = 2.0/(AtrPeriod+1.0);
   double sum=0.0;
   for(int i=1;i<=AtrPeriod;i++) sum += TrueRange(hi[i],lo[i],cl[i-1]);
   double ema = sum/AtrPeriod;
   for(int i=AtrPeriod+1;i<=n;i++)
   {
      double tr = TrueRange(hi[i],lo[i],cl[i-1]);
      ema = alpha*tr + (1.0-alpha)*ema;
   }
   return ema;
}

//+------------------------------------------------------------------+
//  Filtro trend HTF
//+------------------------------------------------------------------+
double TrendMa()
{
   if(trendHandle==INVALID_HANDLE) return 0.0;
   double b[1];
   if(CopyBuffer(trendHandle,0,1,1,b)<1) return 0.0;
   return b[0];
}

bool TrendAllows(bool isLong, double price)
{
   if(!UseTrendFilter) return true;
   double ma = TrendMa();
   if(ma<=0.0) return true;
   return isLong ? (price>ma) : (price<ma);
}

//+------------------------------------------------------------------+
//  Helpers
//+------------------------------------------------------------------+
ulong FindOurPending()
{
   for(int i=OrdersTotal()-1; i>=0; i--)
   {
      ulong tk=OrderGetTicket(i);
      if(tk==0) continue;
      if(OrderGetString(ORDER_SYMBOL)!=_Symbol) continue;
      if(OrderGetInteger(ORDER_MAGIC)!=MagicNumber) continue;
      return tk;
   }
   return 0;
}

bool HaveOpenPosition()
{
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong tk=PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
      return true;
   }
   return false;
}

void DrawKeltner(double u, double m, double l)
{
   datetime t=iTime(_Symbol,_Period,1);
   if(prevT>0 && t>prevT)
   {
      string s=TimeToString(t,TIME_DATE|TIME_MINUTES);
      TL("kU"+s, prevT, prevU, t, u, clrGold);
      TL("kM"+s, prevT, prevM, t, m, clrGray);
      TL("kL"+s, prevT, prevL, t, l, clrGold);
   }
   prevU=u; prevM=m; prevL=l; prevT=t;
}

void TL(string name, datetime t1, double p1, datetime t2, double p2, color c)
{
   ObjectCreate(0,name,OBJ_TREND,0,t1,p1,t2,p2);
   ObjectSetInteger(0,name,OBJPROP_COLOR,c);
   ObjectSetInteger(0,name,OBJPROP_RAY_RIGHT,false);
}

string Ts(datetime t)
{
   if(t==0) return "";
   string s=TimeToString(t, TIME_DATE|TIME_SECONDS);
   StringReplace(s,".","-");
   return s;
}

//+------------------------------------------------------------------+
//  CSV (stesse colonne della versione cTrader/Keltner base)
//+------------------------------------------------------------------+
void InitCsv()
{
   string tag=_Symbol+"_"+EnumToString(_Period);
   string pre=(StringLen(LogSubfolder)>0 ? LogSubfolder+"\\" : "");
   tradesFile=pre+"trades_"+tag+".csv";
   skipsFile =pre+"skips_"+tag+".csv";

   if(!FileIsExist(tradesFile, FILE_COMMON))
   {
      int h=FileOpen(tradesFile, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
      if(h==INVALID_HANDLE){ Print("ERRORE creazione CSV trades"); return; }
      FileWriteString(h,
         "id,signal_time_utc,fill_time_utc,exit_time_utc,min_signal_to_fill,direction,"+
         "signal_close,middle_entry,impulse,sl_dist,tp_dist,sl_pips,tp_pips,"+
         "entry_planned,entry_actual,spread_pips_fill,volume_units,raw_volume,"+
         "theo_risk,theo_risk_pct,real_risk,real_risk_pct,rounding_risk_delta,"+
         "gross_profit,commission,swap,net_profit,pips,R,close_reason\n");
      FileClose(h);
   }
   if(!FileIsExist(skipsFile, FILE_COMMON))
   {
      int h=FileOpen(skipsFile, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
      if(h==INVALID_HANDLE){ Print("ERRORE creazione CSV skips"); return; }
      FileWriteString(h,"time_utc,id,direction,reason,detail\n");
      FileClose(h);
   }
   csvOk=true;
}

void AppendLine(string fname, string line)
{
   int h=FileOpen(fname, FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(h==INVALID_HANDLE) return;
   FileSeek(h,0,SEEK_END);
   FileWriteString(h,line+"\n");
   FileClose(h);
}

void WriteTradeRow(TradeInfoS &ti, double net, double gross, double comm, double swap, double pts, double r, string reason)
{
   if(!EnableCsv || !csvOk) return;
   double bal=AccountInfoDouble(ACCOUNT_BALANCE);
   double minToFill=(ti.fillTime>0 && ti.signalTime>0) ? (double)(ti.fillTime-ti.signalTime)/60.0 : 0;
   double theoPct=(bal>0)?ti.theoRisk/bal*100.0:0;
   double realPct=(bal>0)?ti.realRisk/bal*100.0:0;
   double roundingDelta=ti.theoRisk-ti.realRisk;

   string row=StringFormat(
      "%d,%s,%s,%s,%.1f,%s,%.5f,%.5f,%.5f,%.5f,%.5f,%.1f,%.1f,%.5f,%.5f,%.1f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.1f,%.3f,%s",
      ti.id, Ts(ti.signalTime), Ts(ti.fillTime), Ts(ti.exitTime), minToFill, ti.direction,
      ti.signalClose, ti.middle, ti.impulse, ti.slDist, ti.tpDist, ti.slPts, ti.tpPts,
      ti.entryPlanned, ti.entryActual, ti.spreadPtsFill, ti.filledLots, ti.rawLots,
      ti.theoRisk, theoPct, ti.realRisk, realPct, roundingDelta,
      gross, comm, swap, net, pts, r, reason);
   AppendLine(tradesFile,row);
}

void LogSkip(int id, string direction, string reason, string detail)
{
   if(!EnableCsv || !csvOk) return;
   StringReplace(detail,"\"","'");
   string row=StringFormat("%s,%d,%s,%s,\"%s\"", Ts(TimeCurrent()), id, direction, reason, detail);
   AppendLine(skipsFile,row);
}
//+------------------------------------------------------------------+
