//+------------------------------------------------------------------+
//| CustomTF_Candles.mq5                                             |
//| Candele a timeframe personalizzato (es. M33, M66) disegnate come |
//| vere candele (corpo + ombra) DIETRO il prezzo, tramite oggetti.  |
//|                                                                  |
//| USO: applicare su un grafico il cui timeframe DIVIDE i minuti    |
//| scelti (per M33: grafico M1 o M3; per M66: M1, M2, M3 o M6).     |
//| Applicare due istanze per avere sia 33 che 66.                   |
//|                                                                  |
//| Convenzione: i bucket ripartono da mezzanotte (ora del server)   |
//| di ogni giorno; l'ultima candela della giornata puo' essere      |
//| piu' corta (1440 non e' multiplo di 33/66).                      |
//+------------------------------------------------------------------+
#property copyright   "Trading Framework XAUUSD"
#property version     "2.00"
#property description "Candele a timeframe personalizzato (M33, M66, ...)"
#property indicator_chart_window
#property indicator_buffers 1
#property indicator_plots   1
#property indicator_type1   DRAW_NONE
#property indicator_label1  " "

input int   InpMinutes   = 33;              // Timeframe personalizzato (minuti)
input int   InpDays      = 15;              // Giorni di storico da disegnare
input color InpBullBody  = C'21,72,120';    // Corpo rialzista
input color InpBearBody  = C'120,40,40';    // Corpo ribassista
input color InpBullWick  = clrDodgerBlue;   // Ombra rialzista
input color InpBearWick  = clrTomato;       // Ombra ribassista
input bool  InpFill      = true;            // Corpo pieno (false = solo bordo)

double DummyBuf[];
string pfx;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpMinutes <= 0 || InpMinutes > 1440)
      return(INIT_PARAMETERS_INCORRECT);
   int chart_min = PeriodSeconds(_Period) / 60;
   if(InpMinutes % chart_min != 0)
     {
      Alert("CustomTF: il timeframe del grafico (", chart_min,
            "m) non divide ", InpMinutes, "m. Usa M1 o M3.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   SetIndexBuffer(0, DummyBuf, INDICATOR_DATA);
   pfx = "CTF" + IntegerToString(InpMinutes) + "_";
   IndicatorSetString(INDICATOR_SHORTNAME,
                      "CustomTF M" + IntegerToString(InpMinutes));
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, pfx);
  }

//+------------------------------------------------------------------+
datetime BucketStart(const datetime t)
  {
   long sec_day = (long)t % 86400;
   long day0    = (long)t - sec_day;
   long bucket  = sec_day / ((long)InpMinutes * 60);
   return (datetime)(day0 + bucket * (long)InpMinutes * 60);
  }

//+------------------------------------------------------------------+
//| Crea/aggiorna corpo e ombra di una candela custom                |
//+------------------------------------------------------------------+
void DrawBucket(const datetime t0, const double o, const double h,
                const double l, const double c)
  {
   // fine del bucket (ma non oltre la mezzanotte successiva)
   datetime day_end = (datetime)(((long)t0 / 86400 + 1) * 86400);
   datetime t1 = (datetime)MathMin((long)t0 + (long)InpMinutes * 60,
                                   (long)day_end) - 1;
   datetime tm = (datetime)(((long)t0 + (long)t1) / 2);
   bool bull = (c >= o);
   color body = bull ? InpBullBody : InpBearBody;
   color wick = bull ? InpBullWick : InpBearWick;
   string ts = IntegerToString((long)t0);
   string rn = pfx + "b" + ts;
   string wn = pfx + "w" + ts;

   if(ObjectFind(0, rn) < 0)
     {
      ObjectCreate(0, rn, OBJ_RECTANGLE, 0, t0, o, t1, c);
      ObjectSetInteger(0, rn, OBJPROP_BACK, true);
      ObjectSetInteger(0, rn, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, rn, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, rn, OBJPROP_WIDTH, 1);
     }
   ObjectSetInteger(0, rn, OBJPROP_FILL, InpFill);
   ObjectSetInteger(0, rn, OBJPROP_COLOR, body);
   ObjectMove(0, rn, 0, t0, o);
   ObjectMove(0, rn, 1, t1, c);

   if(ObjectFind(0, wn) < 0)
     {
      ObjectCreate(0, wn, OBJ_TREND, 0, tm, l, tm, h);
      ObjectSetInteger(0, wn, OBJPROP_BACK, true);
      ObjectSetInteger(0, wn, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, wn, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, wn, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, wn, OBJPROP_WIDTH, 2);
     }
   ObjectSetInteger(0, wn, OBJPROP_COLOR, wick);
   ObjectMove(0, wn, 0, tm, l);
   ObjectMove(0, wn, 1, tm, h);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated,
                const datetime &time[], const double &open[],
                const double &high[], const double &low[],
                const double &close[], const long &tick_volume[],
                const long &volume[], const int &spread[])
  {
   if(rates_total < 1)
      return(0);
   datetime min_time = TimeCurrent() - (datetime)((long)InpDays * 86400);
   int start = (prev_calculated > 0) ? prev_calculated - 1 : 0;
   if(start > 0)
     {
      datetime bs = BucketStart(time[start]);
      while(start > 0 && time[start - 1] >= bs)
         start--;
     }
   else
     {
      // primo passaggio: parti dal limite di storico richiesto
      while(start < rates_total - 1 && time[start] < min_time)
         start++;
      datetime bs = BucketStart(time[start]);
      while(start > 0 && time[start - 1] >= bs)
         start--;
     }
   double o = open[start], h = high[start], l = low[start], c = close[start];
   datetime cur = BucketStart(time[start]);
   for(int i = start; i < rates_total; i++)
     {
      DummyBuf[i] = 0.0;
      datetime bs = BucketStart(time[i]);
      if(bs != cur)
        {
         if(cur >= min_time)
            DrawBucket(cur, o, h, l, c);
         cur = bs;
         o = open[i]; h = high[i]; l = low[i]; c = close[i];
        }
      else if(i > start)
        {
         h = MathMax(h, high[i]);
         l = MathMin(l, low[i]);
         c = close[i];
        }
     }
   DrawBucket(cur, o, h, l, c);   // candela in corso, aggiornata live
   return(rates_total);
  }
//+------------------------------------------------------------------+
