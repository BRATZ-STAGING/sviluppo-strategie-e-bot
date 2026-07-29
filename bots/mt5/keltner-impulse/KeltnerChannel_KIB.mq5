//+------------------------------------------------------------------+
//|  KELTNER CHANNEL - replica ESATTA del canale di KeltnerImpulseBot|
//|  middle = EMA(EmaPeriod) su close                                |
//|  bande  = middle ± Mult · ATR(AtrPeriod)                         |
//|  ATR: Wilder (=iATR/TradingView) o Exponential (=EA in forward)  |
//|  Per verificare visivamente segnali/sostituzioni del bot:        |
//|  usare AtrSmoothing = Exponential (default, come l'EA).          |
//+------------------------------------------------------------------+
#property copyright "Trading Bot Factory"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 4
#property indicator_plots   3

#property indicator_label1  "KC Upper"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrGold
#property indicator_width1  1

#property indicator_label2  "KC Middle"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrGray
#property indicator_width2  1

#property indicator_label3  "KC Lower"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrGold
#property indicator_width3  1

enum ENUM_ATR_SMOOTH
{
   ATR_WILDER      = 0,   // Wilder (iATR nativo, = TradingView)
   ATR_EXPONENTIAL = 1    // Exponential (EMA della True Range, = EA in forward)
};

input int             EmaPeriod    = 20;              // EMA Period (middle)
input int             AtrPeriod    = 10;              // ATR Period (bande)
input ENUM_ATR_SMOOTH AtrSmoothing = ATR_EXPONENTIAL; // ATR smoothing (= input dell'EA)
input double          MultUp       = 2.0;             // Mult banda superiore
input double          MultDown     = 2.0;             // Mult banda inferiore

double upBuf[], midBuf[], loBuf[], atrBuf[];

//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, upBuf,  INDICATOR_DATA);
   SetIndexBuffer(1, midBuf, INDICATOR_DATA);
   SetIndexBuffer(2, loBuf,  INDICATOR_DATA);
   SetIndexBuffer(3, atrBuf, INDICATOR_CALCULATIONS);
   IndicatorSetString(INDICATOR_SHORTNAME,
      StringFormat("KC_KIB(%d,%d,%s)", EmaPeriod, AtrPeriod,
                   AtrSmoothing==ATR_WILDER ? "Wil" : "Exp"));
   return INIT_SUCCEEDED;
}

double TrueRange(const double h, const double l, const double pc)
{
   double a = h - l;
   double b = MathAbs(h - pc);
   double c = MathAbs(l - pc);
   return MathMax(a, MathMax(b, c));
}

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated,
                const datetime &time[], const double &open[],
                const double &high[], const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
{
   if(rates_total < MathMax(EmaPeriod, AtrPeriod)+2) return 0;

   int start = (prev_calculated>1) ? prev_calculated-1 : 0;
   double alphaE = 2.0/(EmaPeriod+1.0);
   double alphaA = 2.0/(AtrPeriod+1.0);

   for(int i=start; i<rates_total; i++)
   {
      // ---- EMA del close (middle) ----
      if(i==0) midBuf[0] = close[0];
      else     midBuf[i] = alphaE*close[i] + (1.0-alphaE)*midBuf[i-1];

      // ---- True Range ----
      double tr = (i==0) ? (high[0]-low[0]) : TrueRange(high[i], low[i], close[i-1]);

      // ---- ATR secondo lo smoothing scelto ----
      if(i < AtrPeriod)
      {
         // seed: SMA progressiva delle prime TR (identico all'avvio di iATR / ExpAtr dell'EA)
         double sum = tr;
         for(int k=1; k<=i && k<AtrPeriod; k++)
            sum += (i-k==0) ? (high[0]-low[0]) : TrueRange(high[i-k], low[i-k], close[i-k-1]);
         atrBuf[i] = sum/(i+1);
      }
      else if(AtrSmoothing==ATR_WILDER)
         atrBuf[i] = (atrBuf[i-1]*(AtrPeriod-1) + tr)/AtrPeriod;
      else
         atrBuf[i] = alphaA*tr + (1.0-alphaA)*atrBuf[i-1];

      // ---- Bande ----
      upBuf[i] = midBuf[i] + MultUp  *atrBuf[i];
      loBuf[i] = midBuf[i] - MultDown*atrBuf[i];
   }
   return rates_total;
}
//+------------------------------------------------------------------+
