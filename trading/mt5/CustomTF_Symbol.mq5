//+------------------------------------------------------------------+
//| CustomTF_Symbol.mq5                                              |
//| Crea un SIMBOLO PERSONALIZZATO con candele a timeframe custom    |
//| (es. XAUUSD.M33): un vero grafico nativo, non un overlay.        |
//| Su quel grafico funzionano tutti gli indicatori normali.         |
//|                                                                  |
//| USO:                                                             |
//| 1. Applicare questo EA a un grafico del simbolo sorgente         |
//|    (es. XAUUSD, timeframe qualsiasi). Abilitare "Algo Trading"   |
//|    NON e' necessario: l'EA non fa trading, solo dati.            |
//| 2. L'EA crea il simbolo "XAUUSD.M33" (visibile nel Market Watch  |
//|    sotto Custom) e lo riempie con lo storico aggregato.          |
//| 3. Aprire un grafico di XAUUSD.M33 su timeframe M1: ogni candela |
//|    e' una candela da 33 minuti reali (orari corretti).           |
//| 4. Lasciare l'EA in esecuzione: aggiorna la candela in corso.    |
//|                                                                  |
//| Bonus: sul grafico del simbolo custom, M2 = 66 minuti reali.     |
//| Convenzione bucket: ripartono da mezzanotte (ora server).        |
//+------------------------------------------------------------------+
#property copyright "Trading Framework XAUUSD"
#property version   "1.00"
#property description "Simbolo personalizzato a timeframe custom (M33, M66, ...)"

input int InpMinutes = 33;   // Timeframe custom in minuti
input int InpDays    = 90;   // Giorni di storico da costruire

string src;   // simbolo sorgente (quello del grafico)
string sym;   // simbolo custom creato

//+------------------------------------------------------------------+
datetime BucketStart(const datetime t)
  {
   long sec_day = (long)t % 86400;
   long day0    = (long)t - sec_day;
   long bucket  = sec_day / ((long)InpMinutes * 60);
   return (datetime)(day0 + bucket * (long)InpMinutes * 60);
  }

//+------------------------------------------------------------------+
//| Aggrega barre M1 del sorgente in candele custom                  |
//+------------------------------------------------------------------+
int Aggregate(const datetime from, const datetime to, MqlRates &out[])
  {
   MqlRates m1[];
   int n = CopyRates(src, PERIOD_M1, from, to, m1);
   if(n <= 0)
      return(0);
   ArrayResize(out, 0);
   int k = -1;
   datetime cur = 0;
   for(int i = 0; i < n; i++)
     {
      datetime bs = BucketStart(m1[i].time);
      if(bs != cur)
        {
         k++;
         ArrayResize(out, k + 1);
         out[k].time = bs;
         out[k].open = m1[i].open;
         out[k].high = m1[i].high;
         out[k].low  = m1[i].low;
         out[k].close = m1[i].close;
         out[k].tick_volume = m1[i].tick_volume;
         out[k].real_volume = m1[i].real_volume;
         out[k].spread = 0;
         cur = bs;
        }
      else
        {
         out[k].high = MathMax(out[k].high, m1[i].high);
         out[k].low  = MathMin(out[k].low, m1[i].low);
         out[k].close = m1[i].close;
         out[k].tick_volume += m1[i].tick_volume;
         out[k].real_volume += m1[i].real_volume;
        }
     }
   return(k + 1);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpMinutes <= 0 || InpMinutes > 1440)
      return(INIT_PARAMETERS_INCORRECT);
   src = _Symbol;
   sym = src + ".M" + IntegerToString(InpMinutes);

   if(!SymbolSelect(sym, true))
     {
      if(!CustomSymbolCreate(sym, "Custom\\TF", src))
        {
         Alert("CustomTF: impossibile creare ", sym,
               " (errore ", GetLastError(), ")");
         return(INIT_FAILED);
        }
      SymbolSelect(sym, true);
     }
   // storico completo
   MqlRates out[];
   datetime from = TimeCurrent() - (datetime)((long)InpDays * 86400);
   int n = Aggregate(from, TimeCurrent(), out);
   if(n > 0)
     {
      CustomRatesReplace(sym, out[0].time, out[n - 1].time, out);
      PrintFormat("CustomTF: %s pronto, %d candele da %d minuti. "
                  "Apri il grafico M1 di %s.", sym, n, InpMinutes, sym);
     }
   else
      Print("CustomTF: nessuna barra M1 del sorgente (storico in download?)");
   EventSetTimer(2);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
  }

//+------------------------------------------------------------------+
//| Ogni 2s riaggiorna le ultime due candele custom (quella in corso |
//| e la precedente, per sicurezza sui cambi di bucket)              |
//+------------------------------------------------------------------+
void OnTimer()
  {
   datetime cur = BucketStart(TimeCurrent());
   datetime prev = (datetime)((long)cur - (long)InpMinutes * 60);
   MqlRates out[];
   int n = Aggregate(prev, TimeCurrent(), out);
   if(n > 0)
      CustomRatesUpdate(sym, out);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // gli aggiornamenti viaggiano sul timer; il tick non serve
  }
//+------------------------------------------------------------------+
