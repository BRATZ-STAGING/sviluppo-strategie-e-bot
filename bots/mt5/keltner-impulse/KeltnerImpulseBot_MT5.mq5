//+------------------------------------------------------------------+
//|  KELTNER IMPULSE BOT - v2 (porting MT5 dal cBot cTrader)         |
//|  Strategia mean-reversion dopo impulso sul Keltner Channel.      |
//|  Obiettivo: raccogliere dati ONESTI per verificare l'edge.       |
//|                                                                  |
//|  BACKTEST consigliato (Strategy Tester):                         |
//|   - Modello: "Every tick based on real ticks" (tick reali)       |
//|   - XAUUSD, M10, deposito 1000 EUR, leva 1:500                   |
//|   - Default = report10 cTrader: Target 50, RR 1.5, Rischio 1%,   |
//|     ATR Exponential, MinSL 0, EquityGuard 50%                    |
//|                                                                  |
//|  NOTA UNITA': su MT5 il filtro Min SL e' espresso in PREZZO      |
//|  (es. oro 5.0 = 5 dollari di distanza = 500 pip cTrader).        |
//|  ATR selezionabile: Exponential (= run cTrader) o Wilder (=TV).  |
//|  COMMISSIONE: se il simbolo demo non la applica, viene modellata |
//|  con CommissionPerLotRT ($/lotto round-turn) per un R onesto.    |
//|                                                                  |
//|  I CSV (stesse colonne della versione cTrader) vengono scritti   |
//|  nella cartella COMUNE di MetaTrader:                            |
//|  C:\Users\<utente>\AppData\Roaming\MetaQuotes\Terminal\Common\Files |
//+------------------------------------------------------------------+
#property copyright "Keltner Impulse v2"
#property version   "2.00"

#include <Trade\Trade.mqh>

//---------------- Tipi ----------------
enum ENUM_ATR_SMOOTH
{
   ATR_WILDER      = 0,   // Wilder (iATR nativo, = TradingView di default)
   ATR_EXPONENTIAL = 1    // Exponential (EMA della True Range, = run cTrader report10-15)
};

//---------------- Parametri ----------------
input group "Keltner"
input int             EmaPeriod    = 20;              // EMA Period (middle)
input int             AtrPeriod    = 10;              // ATR Period (bande)
input ENUM_ATR_SMOOTH AtrSmoothing = ATR_EXPONENTIAL; // ATR smoothing (Exponential = i 7 report cTrader)
input double          MultUp       = 2.0;             // Mult banda superiore
input double          MultDown     = 2.0;             // Mult banda inferiore

input group "Strategia"
input double ImpulseTargetPercent = 50.0;  // Target % impulso (TP)  [report10=50]
input double RiskReward           = 1.5;   // Risk/Reward (TP = RR * SL) [report10=1.5]
input int    ExpiryBars           = 20;    // Scadenza ordine (candele)
input double MinStopPrice         = 0.0;   // Min SL in PREZZO (oro: 5.0 = 500 pip cTrader; 0=off)
input bool   ReplaceOnOutsideClose= false; // true = VECCHIA logica (sostituzione su chiusura fuori banda)

input group "Rischio"
input double RiskPercent        = 1.0;     // Rischio % per trade [report10=1]
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
input long   MagicNumber = 20260702;       // Magic number

//---------------- Stato interno ----------------
CTrade   trade;
int      emaHandle = INVALID_HANDLE;
int      atrHandle = INVALID_HANDLE;
int      trendHandle = INVALID_HANDLE;   // MA sul timeframe alto (solo se UseTrendFilter)

datetime lastBarTime      = 0;
long     barCounter       = 0;
long     placedBarCounter = 0;
bool     pendingIsLong    = false;
double   pendingExtreme   = 0.0;   // estremo della candela d'impulso corrente
ulong    pendingTicket    = 0;
long     curPosId         = -1;
double   initialBalance   = 0.0;
bool     halted           = false;
bool     csvOk            = false;
int      nextId           = 1;

int cntSignals=0, cntPlaced=0, cntReplaced=0, cntExpired=0, cntFilled=0, cntSkipped=0;

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
TradeInfoS cur;
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
   // Filtro trend HTF: crea l'handle SOLO se attivo (altrimenti nessun overhead / effetto)
   if(UseTrendFilter)
   {
      trendHandle = iMA(_Symbol, TrendTimeframe, TrendMaPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(trendHandle==INVALID_HANDLE)
      {
         Print("ERRORE creazione MA trend HTF");
         return INIT_FAILED;
      }
      Print("Filtro trend HTF ATTIVO: EMA(", TrendMaPeriod, ") su ", EnumToString(TrendTimeframe));
   }
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(50);

   initialBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   if(EnableCsv) InitCsv();

   Print("KeltnerImpulseBot MT5 avviato su ", _Symbol, " ", EnumToString(_Period),
         " | balance ", DoubleToString(initialBalance,2));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Flush a fine run -> niente survivorship bias nel CSV
   if(haveCur)
   {
      if(curPosId>0)
      {
         // posizione ancora aperta: cerco lo stato live
         for(int i=PositionsTotal()-1; i>=0; i--)
         {
            ulong tk=PositionGetTicket(i);
            if(tk==0) continue;
            if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
            if(PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
            cur.exitTime = TimeCurrent();
            double profit = PositionGetDouble(POSITION_PROFIT);
            double swap   = PositionGetDouble(POSITION_SWAP);
            double net    = profit + swap + cur.entryCommission;
            double pts    = (cur.direction=="LONG")
                          ? (PositionGetDouble(POSITION_PRICE_CURRENT)-cur.entryActual)/_Point
                          : (cur.entryActual-PositionGetDouble(POSITION_PRICE_CURRENT))/_Point;
            double r = (cur.realRisk>0) ? net/cur.realRisk : 0.0;
            WriteTradeRow(net, profit, cur.entryCommission, swap, pts, r, "OPEN_AT_STOP");
            break;
         }
      }
      else if(pendingTicket>0)
         LogSkip(cur.id, cur.direction, "PENDING_AT_STOP", "ordine pendente non eseguito a fine run");
   }

   PrintFormat("RIEPILOGO -> segnali:%d ordini:%d sostituiti:%d scaduti:%d eseguiti:%d scartati:%d",
               cntSignals, cntPlaced, cntReplaced, cntExpired, cntFilled, cntSkipped);
}

//+------------------------------------------------------------------+
void OnTick()
{
   datetime t0 = iTime(_Symbol, _Period, 0);
   if(t0==lastBarTime) return;      // lavora solo a candela chiusa (niente look-ahead)
   lastBarTime = t0;
   barCounter++;
   OnNewBar();
}

//+------------------------------------------------------------------+
void OnNewBar()
{
   // warm-up indicatori
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
   else
   {
      atr = ExpAtr();   // EMA della True Range (come cTrader "Exponential")
   }
   if(atr<=0) return;

   double close = iClose(_Symbol,_Period,1);
   double high  = iHigh (_Symbol,_Period,1);
   double low   = iLow  (_Symbol,_Period,1);
   double upper = middle + MultUp*atr;
   double lower = middle - MultDown*atr;

   if(DrawChannel) DrawKeltner(upper, middle, lower);

   ulong pending = FindOurPending();
   bool  open    = HaveOpenPosition();

   // Salvavita anti-rovina
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

   // Una posizione per simbolo
   if(open) return;

   if(pending==0)
   {
      // CREAZIONE setup: solo su candela che CHIUDE fuori dal canale
      bool ls = close>upper;
      bool ss = close<lower;
      if(ls || ss)
      {
         cntSignals++;
         // Filtro trend HTF: consenti LONG solo se prezzo>MA, SHORT solo se prezzo<MA
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

   // Ordine pendente presente: due modalita' di sostituzione (A/B test)
   if(ReplaceOnOutsideClose)
   {
      // VECCHIA logica: ogni candela che chiude fuori dal canale sostituisce l'ordine
      bool ls = close>upper;
      bool ss = close<lower;
      if(ls || ss)
      {
         cntSignals++;
         if(!TrendAllows(ls, close)) return;   // trend contrario: mantieni il pendente esistente
         PlaceSetup(ls, middle, high, low, pending);
         return;
      }
   }
   else
   {
      // NUOVA logica (spec): sostituzione solo se la candela CHIUDE oltre l'estremo
      // della candela d'impulso. Conta la CHIUSURA, non il wick; non basta chiudere fuori banda.
      bool exceeded = pendingIsLong ? (close>pendingExtreme) : (close<pendingExtreme);
      if(exceeded)
      {
         if(!TrendAllows(pendingIsLong, close)) return;   // trend contrario: mantieni il pendente
         PlaceSetup(pendingIsLong, middle, high, low, pending);
         return;
      }
   }

   // Scadenza dell'ordine pendente
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
// Crea (existing==0) o sostituisce (existing>0) il setup.
void PlaceSetup(bool isLong, double middle, double high, double low, ulong existing)
{
   double extreme = isLong ? high : low;
   double impulse = MathAbs(extreme - middle);
   double tpDist  = ImpulseTargetPercent/100.0*impulse;   // TP = 80% impulso
   double slDist  = tpDist/RiskReward;                    // SL = TP / 1.2
   double entry   = NormalizeDouble(middle, _Digits);     // limit sulla media

   // Filtro volatilita'/costo (i trade con SL piccolo perdono in tutti i regimi)
   if(MinStopPrice>0 && slDist<MinStopPrice)
   {
      cntSkipped++;
      LogSkip(nextId, isLong?"Buy":"Sell", "MIN_SL",
              StringFormat("slDist=%.5f < %.5f", slDist, MinStopPrice));
      return;
   }

   // ---- Position sizing per rischio % ----
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE); // in valuta conto
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
              StringFormat("lotti calcolati %.4f < min %.2f (rischio target troppo piccolo)", rawLots, minLot));
      return;
   }
   if(lots>maxLot) lots=maxLot;
   double realRisk = riskPerLot*lots;

   // ---- Sostituzione dell'eventuale ordine pendente precedente ----
   if(existing>0)
   {
      trade.OrderDelete(existing);
      cntReplaced++;
      LogSkip(cur.id, pendingIsLong?"Buy":"Sell", "REPLACED", "candela chiude oltre l'impulso -> nuovo setup");
      haveCur=false; pendingTicket=0;
   }

   // ---- Piazzamento nuovo limit ----
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
      pendingExtreme   = extreme;   // nuovo riferimento: sostituzione solo su CHIUSURA oltre questo livello
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

      // Segno grafico: STELLA = sostituzione; freccia = nuovo setup
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
// Fill e chiusure: mappatura robusta tramite deal/position id (niente comment parsing)
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL)!=_Symbol) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC)!=MagicNumber) return;

   ENUM_DEAL_ENTRY dealEntry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY);

   if(dealEntry==DEAL_ENTRY_IN)
   {
      if(!haveCur) { Print("ATTENZIONE fill non mappato: trade NON loggato."); return; }
      cur.fillTime        = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);
      cur.entryActual     = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
      cur.filledLots      = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
      cur.entryCommission = HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
      cur.spreadPtsFill   = (SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID))/_Point;

      double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      if(tickSize>0) cur.realRisk = cur.slDist/tickSize*tickValue*cur.filledLots;

      curPosId = (long)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
      pendingTicket=0;
      cntFilled++;
   }
   else if(dealEntry==DEAL_ENTRY_OUT || dealEntry==DEAL_ENTRY_OUT_BY)
   {
      if(!haveCur) { Print("ATTENZIONE chiusura non mappata: trade NON loggato."); return; }
      if((long)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID)!=curPosId) return;

      cur.exitTime = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);
      double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
      double swap   = HistoryDealGetDouble(trans.deal, DEAL_SWAP);
      // Commissione: se il broker la applica (demo con commissione reale) usiamo quella;
      // se il simbolo demo ha commissione 0, la MODELLIAMO (CommissionPerLotRT) per un R onesto.
      double brokerComm = HistoryDealGetDouble(trans.deal, DEAL_COMMISSION) + cur.entryCommission;
      double comm = (MathAbs(brokerComm) > 0.0001)
                  ? brokerComm
                  : -CommissionPerLotRT*cur.filledLots;   // round-turn, gia' negativa
      double closePrice = HistoryDealGetDouble(trans.deal, DEAL_PRICE);

      long reason = HistoryDealGetInteger(trans.deal, DEAL_REASON);
      string reasonS = (reason==DEAL_REASON_SL) ? "StopLoss"
                     : (reason==DEAL_REASON_TP) ? "TakeProfit" : "Other";

      double pts = (cur.direction=="LONG")
                 ? (closePrice-cur.entryActual)/_Point
                 : (cur.entryActual-closePrice)/_Point;
      double net = profit + swap + comm;   // commissioni/swap sono gia' negativi
      double r   = (cur.realRisk>0) ? net/cur.realRisk : 0.0;

      WriteTradeRow(net, profit, comm, swap, pts, r, reasonS);
      haveCur=false; curPosId=-1;
   }
}

//+------------------------------------------------------------------+
//  ATR Exponential = EMA della True Range (replica cTrader "Exponential")
//  Ritorna l'ATR sulla candela appena chiusa (shift 1). 0 = dati insufficienti.
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
   int need  = AtrPeriod*20;                 // finestra ampia -> EMA a regime, seed irrilevante
   int avail = Bars(_Symbol,_Period) - 2;    // escludi barra in formazione + serve un close precedente
   int n     = MathMin(need, avail);
   if(n < AtrPeriod+1) return 0.0;

   double hi[], lo[], cl[];
   // range in serie = barre 1..n+1 (bar n+1 = piu vecchia). Array NON as-series:
   // indice 0 = piu vecchio, indice n = barra 1 (ultima chiusa).
   if(CopyHigh (_Symbol,_Period,1,n+1,hi)<n+1) return 0.0;
   if(CopyLow  (_Symbol,_Period,1,n+1,lo)<n+1) return 0.0;
   if(CopyClose(_Symbol,_Period,1,n+1,cl)<n+1) return 0.0;

   double alpha = 2.0/(AtrPeriod+1.0);

   // seed = SMA delle prime AtrPeriod True Range (indici 1..AtrPeriod)
   double sum=0.0;
   for(int i=1;i<=AtrPeriod;i++)
      sum += TrueRange(hi[i],lo[i],cl[i-1]);
   double ema = sum/AtrPeriod;

   // EMA fino alla barra 1 (indice n)
   for(int i=AtrPeriod+1;i<=n;i++)
   {
      double tr = TrueRange(hi[i],lo[i],cl[i-1]);
      ema = alpha*tr + (1.0-alpha)*ema;
   }
   return ema;
}

//+------------------------------------------------------------------+
//  Filtro trend HTF
//  Valore della MA sul timeframe alto, sulla barra HTF gia' chiusa
//  (shift 1 -> niente repaint / look-ahead). 0 = dati insufficienti.
//+------------------------------------------------------------------+
double TrendMa()
{
   if(trendHandle==INVALID_HANDLE) return 0.0;
   double b[1];
   if(CopyBuffer(trendHandle,0,1,1,b)<1) return 0.0;
   return b[0];
}

// Consenti LONG solo se prezzo>MA HTF, SHORT solo se prezzo<MA HTF.
// Filtro OFF -> sempre true (comportamento invariato).
// Dati MA non ancora disponibili -> fail-open (true): nel forward su broker
// live la storia D1 e' gia' presente, quindi non si verifica in pratica.
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

// formato tempo identico ai CSV cTrader: yyyy-MM-dd HH:mm:ss
string Ts(datetime t)
{
   if(t==0) return "";
   string s=TimeToString(t, TIME_DATE|TIME_SECONDS);   // "yyyy.mm.dd hh:mm:ss"
   StringReplace(s,".","-");
   return s;
}

//+------------------------------------------------------------------+
//  CSV (stesse colonne della versione cTrader)
//+------------------------------------------------------------------+
void InitCsv()
{
   string tag=_Symbol+"_"+EnumToString(_Period);
   tradesFile="trades_"+tag+".csv";
   skipsFile ="skips_"+tag+".csv";

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

void WriteTradeRow(double net, double gross, double comm, double swap, double pts, double r, string reason)
{
   if(!EnableCsv || !csvOk) return;
   double bal=AccountInfoDouble(ACCOUNT_BALANCE);
   double minToFill=(cur.fillTime>0 && cur.signalTime>0) ? (double)(cur.fillTime-cur.signalTime)/60.0 : 0;
   double theoPct=(bal>0)?cur.theoRisk/bal*100.0:0;
   double realPct=(bal>0)?cur.realRisk/bal*100.0:0;
   double roundingDelta=cur.theoRisk-cur.realRisk;

   string row=StringFormat(
      "%d,%s,%s,%s,%.1f,%s,%.5f,%.5f,%.5f,%.5f,%.5f,%.1f,%.1f,%.5f,%.5f,%.1f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.1f,%.3f,%s",
      cur.id, Ts(cur.signalTime), Ts(cur.fillTime), Ts(cur.exitTime), minToFill, cur.direction,
      cur.signalClose, cur.middle, cur.impulse, cur.slDist, cur.tpDist, cur.slPts, cur.tpPts,
      cur.entryPlanned, cur.entryActual, cur.spreadPtsFill, cur.filledLots, cur.rawLots,
      cur.theoRisk, theoPct, cur.realRisk, realPct, roundingDelta,
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
