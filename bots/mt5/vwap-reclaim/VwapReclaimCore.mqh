//+------------------------------------------------------------------+
//|  VwapReclaimCore.mqh — il nucleo della strategia, senza MT5       |
//|                                                                  |
//|  Qui dentro non si chiama NIENTE del terminale: nessun iTime,    |
//|  nessun SymbolInfo, nessun ordine. Solo aritmetica sulle candele |
//|  M1 che gli vengono passate. Il motivo e' che questo file deve   |
//|  compilare in due posti:                                         |
//|                                                                  |
//|    - MetaEditor, incluso da VwapReclaimBot_MT5.mq5;              |
//|    - g++, incluso dal banco di prova in verifica/, che lo fa     |
//|      girare sulle stesse candele del motore Python e confronta   |
//|      i segnali uno per uno.                                      |
//|                                                                  |
//|  Il confronto e' il passo che AVVIO-MT5-VPS.md §3 vieta di       |
//|  saltare: un EA scritto da specifica e mai confrontato sbaglia,  |
//|  e nella sessione precedente le divergenze fra pannello e motore |
//|  sono state nove, ognuna capace di aprire operazioni inesistenti.|
//|                                                                  |
//|  Riferimento: trading/framework/segnali.py, structure.py,        |
//|  vwap.py, volatility.py, data.py. Dove questo file e la prosa    |
//|  delle schede non vanno d'accordo, comanda il codice Python:     |
//|  e' quello che ha prodotto i numeri.                             |
//+------------------------------------------------------------------+
#ifndef VWAP_RECLAIM_CORE_MQH
#define VWAP_RECLAIM_CORE_MQH

//--- Compatibilita' fra MQL5 e C++: gli array si passano per        --
//--- riferimento in MQL5 e per puntatore in C++. Stessa scrittura   --
//--- nel corpo delle funzioni (a[i]), dichiarazione diversa.        --
#ifdef __cplusplus
   #include <cmath>
   #define CARR(t,n)  const t *n
   #define MARR(t,n)  t *n
   typedef long long datetime;
   inline double MathMax(double a, double b) { return a > b ? a : b; }
   inline double MathMin(double a, double b) { return a < b ? a : b; }
   inline double MathAbs(double a)           { return a < 0 ? -a : a; }
   inline bool   MathIsValidNumber(double a) { return a == a && a * 0.0 == 0.0; }
#else
   #define CARR(t,n)  const t &n[]
   #define MARR(t,n)  t &n[]
#endif

#define VR_NESSUNO   0
#define VR_LONG      1
#define VR_SHORT   (-1)

#define VR_MAXK      7                  // k massimo dei frattali
#define VR_FIN     (2 * VR_MAXK + 1)    // finestra per confermare uno swing
#define VR_STOPBAR  16                  // barre tenute per lo stop strutturale
#define VR_MAXATR 8192                  // giornate di ATR conservate

//--- Secondi dei timeframe usati. M33 e M66 non esistono in MT5 e
//--- vengono costruiti da qui; gli altri sono nativi ma li ricostruiamo
//--- comunque dai minuti, per non dipendere da come il broker taglia le
//--- candele.
#define VR_SEC_M6    360
#define VR_SEC_M12   720
#define VR_SEC_M33  1980
#define VR_SEC_H2    7200
#define VR_SEC_H6   21600
#define VR_SEC_H12  43200

//+------------------------------------------------------------------+
//|  Aggregatore M1 -> timeframe, ancorato all'EPOCH                 |
//|                                                                  |
//|  TRAPPOLA 2. data.py usa resample(origin="epoch"): i bin partono |
//|  dal 1/1/1970, NON dalla mezzanotte. Per M6, M12, H2, H6, H12 e' |
//|  lo stesso (dividono il giorno), per M33 e M66 no: 1440 non e'   |
//|  divisibile per 33, quindi ogni giorno le candele cadono in un   |
//|  punto diverso. Ancorandole alla mezzanotte si otterrebbero      |
//|  candele M33 diverse da quelle del motore, e con esse stati di   |
//|  struttura diversi: cioe' le condizioni 2, 3a e 3b sbagliate.    |
//|                                                                  |
//|  AVVIO-MT5-VPS.md dice "allineati all'inizio della giornata UTC" |
//|  ed e' un errore del documento: il codice ancora all'epoch.      |
//|                                                                  |
//|  I bin vuoti non esistono (dropna in data.py): una candela nasce |
//|  solo se almeno un minuto ci e' caduto dentro.                   |
//+------------------------------------------------------------------+
struct AggTF
{
   int      secondi;
   bool     aperta;
   datetime apertura;                    // istante di APERTURA del bin
   double   o, h, l, c, v;
};

void AggInit(AggTF &a, const int secondi)
{
   a.secondi  = secondi;
   a.aperta   = false;
   a.apertura = 0;
   a.o = a.h = a.l = a.c = a.v = 0.0;
}

datetime AggBin(const datetime t, const int secondi)
{
   return (datetime)((t / secondi) * secondi);
}

//--- Aggiunge un minuto. Se cosi' facendo la candela precedente si e'
//--- chiusa, la copia nei parametri "ch" e ritorna true.
bool AggAggiungi(AggTF &a, const datetime t, const double o, const double h,
                 const double l, const double c, const double v,
                 datetime &chT, double &chO, double &chH, double &chL,
                 double &chC, double &chV)
{
   const datetime b = AggBin(t, a.secondi);
   bool chiusa = false;
   if(a.aperta && b != a.apertura)
   {
      chT = a.apertura; chO = a.o; chH = a.h; chL = a.l; chC = a.c; chV = a.v;
      chiusa   = true;
      a.aperta = false;
   }
   if(!a.aperta)
   {
      a.aperta = true; a.apertura = b;
      a.o = o; a.h = h; a.l = l; a.c = c; a.v = v;
   }
   else
   {
      a.h = MathMax(a.h, h);
      a.l = MathMin(a.l, l);
      a.c = c;
      a.v += v;
   }
   return chiusa;
}

//+------------------------------------------------------------------+
//|  Stato di trend causale (structure.py)                           |
//|                                                                  |
//|  TRAPPOLA 3. Uno swing e' confermato solo k candele DOPO il suo  |
//|  estremo, e la rottura esiste solo alla chiusura della candela   |
//|  che rompe. Lo stato vale dall'istante di chiusura di quella     |
//|  candela, non dal momento in cui l'estremo si e' formato.        |
//|                                                                  |
//|  La macchina qui sotto e' la stessa passata di trend_events(),   |
//|  fatta una candela alla volta: al bar i si controlla se la barra |
//|  j = i-k e' un massimo (o minimo) circondato da k barre piu'     |
//|  basse (piu' alte) per lato, e poi si guarda se la CHIUSURA di i |
//|  supera l'ultimo estremo confermato.                             |
//|                                                                  |
//|  Se nella stessa candela scattano sia la rottura in su sia       |
//|  quella in giu', vince l'ultima: e' quello che fa il Python con  |
//|  duplicated(keep="last").                                        |
//+------------------------------------------------------------------+
struct StrutTF
{
   int      k;
   int      secondi;
   int      n;                          // candele viste in tutto
   int      w;                          // quante ne ha la finestra
   double   fh[VR_FIN], fl[VR_FIN];     // finestra scorrevole
   bool     haSH, haSL;
   double   sh, sl;                     // ultimo massimo/minimo confermato
   int      stato;                      // -1, 0, +1
   datetime da;                         // da quando lo stato e' noto
};

void StrutInit(StrutTF &s, const int k, const int secondi)
{
   s.k = (k > VR_MAXK ? VR_MAXK : k);
   s.secondi = secondi;
   s.n = 0; s.w = 0;
   s.haSH = false; s.haSL = false;
   s.sh = 0.0; s.sl = 0.0;
   s.stato = 0; s.da = 0;
   for(int i = 0; i < VR_FIN; i++) { s.fh[i] = 0.0; s.fl[i] = 0.0; }
}

//--- Una candela CHIUSA del timeframe, in ordine di tempo.
void StrutAggiungi(StrutTF &s, const datetime apertura, const double h,
                   const double l, const double c)
{
   const int larghezza = 2 * s.k + 1;
   if(s.w < larghezza) s.w++;
   else
      for(int i = 0; i < larghezza - 1; i++) { s.fh[i] = s.fh[i + 1]; s.fl[i] = s.fl[i + 1]; }
   s.fh[s.w - 1] = h;
   s.fl[s.w - 1] = l;
   s.n++;

   // il candidato e' il centro della finestra: la barra i-k
   if(s.w == larghezza && s.n >= 2 * s.k + 1)
   {
      const double hj = s.fh[s.k];
      bool massimo = true;
      for(int i = 0; i < larghezza && massimo; i++)
         if(i != s.k && !(s.fh[i] < hj)) massimo = false;
      if(massimo) { s.sh = hj; s.haSH = true; }

      const double lj = s.fl[s.k];
      bool minimo = true;
      for(int i = 0; i < larghezza && minimo; i++)
         if(i != s.k && !(s.fl[i] > lj)) minimo = false;
      if(minimo) { s.sl = lj; s.haSL = true; }
   }

   const datetime chiusura = (datetime)(apertura + s.secondi);
   if(s.haSH && c > s.sh) { s.stato = 1;  s.da = chiusura; s.haSH = false; }
   if(s.haSL && c < s.sl) { s.stato = -1; s.da = chiusura; s.haSL = false; }
}

//--- Lo stato vigente a un istante. Serve perche' M33 non e' multiplo
//--- di M6: fra la chiusura della barra decisionale e "adesso" lo stato
//--- puo' cambiare, e leggerlo adesso significherebbe decidere con
//--- un'informazione che al momento della decisione non c'era.
int StrutStatoA(const StrutTF &s, const datetime quando)
{
   if(s.da == 0 || s.da > quando) return 0;
   return s.stato;
}

//+------------------------------------------------------------------+
//|  Giornate vere, ATR, filtro di fondo (volatility.py, segnali.py) |
//|                                                                  |
//|  TRAPPOLA 6. Lo spezzone della domenica sera NON e' una giornata:|
//|  sotto le 300 candele M1 la sessione si scarta. Contandola, la   |
//|  media a 50 giornate ne copriva 42 e una volta a settimana ci    |
//|  entrava un valore quasi uguale alla chiusura del venerdi'.      |
//|  Misurato: 5,1% delle giornate classificate diversamente.        |
//+------------------------------------------------------------------+
#define VR_MIN_M1_GIORNO 300
#define VR_MAXD1 4096

struct StoriaD1
{
   int      n;
   datetime giorno[VR_MAXD1];
   double   chiusura[VR_MAXD1];
   double   atr[VR_MAXD1];              // ATR del giorno, gia' spostato di 1
   bool     atrOk[VR_MAXD1];
   bool     macro[VR_MAXD1];            // chiusura di ieri sopra la sua media
   bool     macroOk[VR_MAXD1];
   // giornata in costruzione
   bool     aperta;
   datetime gCorr;
   double   gO, gH, gL, gC;
   int      gN;
   // serie per il true range
   double   trStorico[VR_MAXD1];
};

void D1Init(StoriaD1 &d)
{
   d.n = 0; d.aperta = false; d.gCorr = 0; d.gN = 0;
   d.gO = d.gH = d.gL = d.gC = 0.0;
}

datetime VrGiornoDi(const datetime t) { return (datetime)((t / 86400) * 86400); }

void D1Chiudi(StoriaD1 &d, const int mediaMacro)
{
   if(!d.aperta) return;
   d.aperta = false;
   if(d.gN < VR_MIN_M1_GIORNO) return;          // domenica sera: non e' una giornata
   if(d.n >= VR_MAXD1) return;

   const int i = d.n;
   d.giorno[i]   = d.gCorr;
   d.chiusura[i] = d.gC;

   // true range con la chiusura della giornata VERA precedente
   double tr = d.gH - d.gL;
   if(i > 0)
   {
      const double pc = d.chiusura[i - 1];
      tr = MathMax(tr, MathAbs(d.gH - pc));
      tr = MathMax(tr, MathAbs(d.gL - pc));
   }
   d.trStorico[i] = tr;

   // ATR a 14 giornate, spostato di uno: il valore del giorno i usa le
   // giornate i-14..i-1, quindi e' noto prima di operare in i
   d.atrOk[i] = false; d.atr[i] = 0.0;
   if(i >= 14)
   {
      double s = 0.0;
      for(int j = i - 14; j < i; j++) s += d.trStorico[j];
      d.atr[i] = s / 14.0;
      d.atrOk[i] = true;
   }

   // filtro di fondo: chiusura di IERI contro la sua media a 50 giornate
   d.macroOk[i] = false; d.macro[i] = false;
   if(i >= mediaMacro)
   {
      double s = 0.0;
      for(int j = i - mediaMacro; j < i; j++) s += d.chiusura[j];
      d.macro[i]   = (d.chiusura[i - 1] > s / (double)mediaMacro);
      d.macroOk[i] = true;
   }
   d.n++;
}

void D1Aggiungi(StoriaD1 &d, const datetime t, const double o, const double h,
                const double l, const double c, const int mediaMacro)
{
   const datetime g = VrGiornoDi(t);
   if(d.aperta && g != d.gCorr) D1Chiudi(d, mediaMacro);
   if(!d.aperta)
   {
      d.aperta = true; d.gCorr = g;
      d.gO = o; d.gH = h; d.gL = l; d.gC = c; d.gN = 0;
   }
   else
   {
      d.gH = MathMax(d.gH, h);
      d.gL = MathMin(d.gL, l);
      d.gC = c;
   }
   d.gN++;
}

//--- Indice dell'ultima giornata CHIUSA precedente a g (esclusa g stessa).
//
//    Serve proprio l'ultima PRIMA: quando si decide, la giornata in corso
//    non e' finita, e il motore Python calcola i suoi valori per il giorno g
//    usando solo le giornate che lo precedono (rolling().shift(1)). Prendere
//    l'ultima giornata <= g darebbe i valori di IERI per la giornata di oggi:
//    uno sfasamento di un giorno su ATR e filtro di fondo, cioe' soglie
//    sbagliate e direzione sbagliata.
int D1IndicePrec(const StoriaD1 &d, const datetime g)
{
   int lo = 0, hi = d.n - 1, out = -1;
   while(lo <= hi)
   {
      const int mid = (lo + hi) / 2;
      if(d.giorno[mid] < g) { out = mid; lo = mid + 1; }
      else hi = mid - 1;
   }
   return out;
}

//--- ATR vigente nella giornata g: media dei 14 true range delle giornate
//--- vere che la precedono. E' il valore che il Python associa a g con
//--- tr.rolling(14).mean().shift(1).
bool D1AtrPer(const StoriaD1 &d, const datetime g, double &atr)
{
   const int ip = D1IndicePrec(d, g);
   if(ip < 13) return false;
   double s = 0.0;
   for(int j = ip - 13; j <= ip; j++) s += d.trStorico[j];
   atr = s / 14.0;
   return (atr > 0.0);
}

//--- Filtro di fondo per la giornata g: la chiusura dell'ultima giornata
//--- vera precedente sta sopra la sua media a mediaMacro giornate?
bool D1MacroPer(const StoriaD1 &d, const datetime g, const int mediaMacro,
                bool &sopra)
{
   const int ip = D1IndicePrec(d, g);
   if(ip < mediaMacro - 1) return false;
   double s = 0.0;
   for(int j = ip - mediaMacro + 1; j <= ip; j++) s += d.chiusura[j];
   sopra = (d.chiusura[ip] > s / (double)mediaMacro);
   return true;
}

//+------------------------------------------------------------------+
//|  Mese ad alta volatilita' (volatility.high_volatility_months)    |
//|                                                                  |
//|  TRAPPOLA 7. Il confronto NON e' contro la mediana di            |
//|  riferimento: e' contro la mediana di TUTTA la storia precedente |
//|  (finestra espansiva). La mediana di riferimento (25,5968 $)     |
//|  serve a un'altra cosa, a riscalare le soglie. Sotto 250         |
//|  giornate di storia la risposta e' "normale".                    |
//|                                                                  |
//|  Conseguenza operativa da non sottovalutare: con poca storia     |
//|  caricata l'EA direbbe "mese normale" dove il motore dice        |
//|  "agitato", userebbe soglie in dollari invece che riscalate e    |
//|  aprirebbe operazioni diverse. Per questo l'EA si rifiuta di     |
//|  operare finche' non ha abbastanza giornate: vedi RiscaldamentoOk|
//+------------------------------------------------------------------+
#define VR_MIN_STORIA_ATR 250
#define VR_GIORNI_RECENTI  21

double VrMediana(MARR(double, v), const int n)
{
   if(n <= 0) return 0.0;
   for(int i = 1; i < n; i++)                    // insertion sort: n <= 4096
   {
      const double x = v[i];
      int j = i - 1;
      while(j >= 0 && v[j] > x) { v[j + 1] = v[j]; j--; }
      v[j + 1] = x;
   }
   if((n % 2) == 1) return v[n / 2];
   return 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

//--- Il mese che inizia a "inizioMese" e' agitato? Guarda solo le
//--- giornate precedenti: causale.
bool VrMeseAgitato(const StoriaD1 &d, const datetime inizioMese, const double fattore)
{
   double tutte[VR_MAXATR];
   int n = 0;
   for(int i = 0; i < d.n && n < VR_MAXATR; i++)
   {
      if(d.giorno[i] >= inizioMese) break;
      if(!d.atrOk[i]) continue;                  // dropna: i primi 14 non ci sono
      tutte[n] = d.atr[i];
      n++;
   }
   if(n < VR_MIN_STORIA_ATR) return false;

   double recenti[VR_GIORNI_RECENTI];
   for(int i = 0; i < VR_GIORNI_RECENTI; i++) recenti[i] = tutte[n - VR_GIORNI_RECENTI + i];
   const double mRecente = VrMediana(recenti, VR_GIORNI_RECENTI);
   const double mTutte   = VrMediana(tutte, n);  // ordina tutte[] sul posto
   return (mRecente > fattore * mTutte);
}

//+------------------------------------------------------------------+
//|  Soglie (taratura.soglie)                                        |
//+------------------------------------------------------------------+
struct Soglie
{
   double impulso, buffer, rischioMin, rischioMax;
};

void SoglieBase(Soglie &s, const double impulso, const double buffer,
                const double rMin, const double rMax)
{
   s.impulso = impulso; s.buffer = buffer;
   s.rischioMin = rMin; s.rischioMax = rMax;
}

//--- Nei mesi agitati ogni soglia diventa  valore / mediana * atr.
void SoglieScala(Soglie &s, const double atr, const double mediana)
{
   const double f = atr / mediana;
   s.impulso *= f; s.buffer *= f; s.rischioMin *= f; s.rischioMax *= f;
}

//+------------------------------------------------------------------+
//|  Il valutatore: una candela M6 chiusa -> le sette condizioni     |
//+------------------------------------------------------------------+
struct Esito
{
   bool     valutata;            // c'era una barra da valutare
   datetime barra;               // apertura della candela M6 decisionale
   datetime istante;             // chiusura: e' l'istante dell'ingresso
   int      lato;                // VR_LONG / VR_SHORT / VR_NESSUNO
   bool     c1_orario, c2_struttura, c3a_conferme, c3b_ritracciamento;
   bool     c4a_impulso, c4b_reclaim, c5_macro, c6_rischio, c7_frequenza;
   bool     consuma;             // occupa uno dei tre posti del giorno
   bool     apre;                // tutte e sette
   double   vwap, entry, stop, rischio, spinta;
   double   sogliaImpulso, rischioMinimo, rischioMassimo;
   bool     agitato;             // mese ad alta volatilita'
   int      stH6, stH2, stM33, stH12, stM12;
};

void EsitoAzzera(Esito &e)
{
   e.valutata = false; e.barra = 0; e.istante = 0; e.lato = VR_NESSUNO;
   e.c1_orario = false; e.c2_struttura = false; e.c3a_conferme = false;
   e.c3b_ritracciamento = false; e.c4a_impulso = false; e.c4b_reclaim = false;
   e.c5_macro = false; e.c6_rischio = false; e.c7_frequenza = false;
   e.consuma = false; e.apre = false;
   e.vwap = 0.0; e.entry = 0.0; e.stop = 0.0; e.rischio = 0.0; e.spinta = 0.0;
   e.sogliaImpulso = 0.0; e.rischioMinimo = 0.0; e.rischioMassimo = 0.0;
   e.agitato = false;
   e.stH6 = 0; e.stH2 = 0; e.stM33 = 0; e.stH12 = 0; e.stM12 = 0;
}

//--- Parametri della strategia: gli stessi nomi di taratura.py.
struct Parametri
{
   double impulsoMin, buffer, rischioMin, rischioMax, mediaAtrRif, fattoreAlta;
   int    barreStop, oraInizio, oraFine, oraChiusura, maxAlGiorno, attesaMinuti;
   int    mediaMacro, frattaleK;
   bool   soloLong;
};

void ParametriUfficiali(Parametri &p)
{
   p.impulsoMin   = 4.00;
   p.buffer       = 0.30;
   p.rischioMin   = 1.00;
   p.rischioMax   = 10.00;
   p.mediaAtrRif  = 25.5968;     // mediana ATR 2020-2024, congelata
   p.fattoreAlta  = 1.5;
   p.barreStop    = 5;
   p.oraInizio    = 7;
   p.oraFine      = 19;
   p.oraChiusura  = 21;
   p.maxAlGiorno  = 3;
   p.attesaMinuti = 30;
   p.mediaMacro   = 50;
   p.frattaleK    = 3;
   p.soloLong     = false;
}

//+------------------------------------------------------------------+
//|  Il motore completo, incrementale                                |
//|                                                                  |
//|  Si alimenta un minuto alla volta con Passo(); ogni volta che una|
//|  candela M6 si chiude restituisce l'Esito di quella candela, con |
//|  tutte e sette le condizioni. Il chiamante (l'EA o il banco di   |
//|  prova) decide cosa farne.                                       |
//+------------------------------------------------------------------+
struct Motore
{
   Parametri p;
   AggTF     aM6, aM12, aM33, aH2, aH6, aH12;
   StrutTF   sM12, sM33, sH2, sH6, sH12;
   StoriaD1  d1;

   // VWAP giornaliero sulle candele M6 (TRAPPOLA 4: sulle M6, non sui minuti)
   datetime  giornoVwap;
   double    cumPV, cumV;

   // stato della giornata sulle M6
   datetime  giornoM6;
   bool      haPrec;
   double    precH, precL;               // candela M6 precedente
   bool      haSpinta;
   double    maxH, minL;                 // estremi del giorno PRIMA di questa barra
   double    stopH[VR_STOPBAR], stopL[VR_STOPBAR];
   datetime  stopG[VR_STOPBAR];
   int       stopN;

   // frequenza
   int       oggi;
   datetime  ultimoIngresso;

   // mese corrente
   datetime  meseCorrente;
   bool      meseAgitato;

   bool      pronto;                     // riscaldamento completato
};

void MotoreInit(Motore &m, const Parametri &p)
{
   m.p = p;
   AggInit(m.aM6, VR_SEC_M6);   AggInit(m.aM12, VR_SEC_M12);
   AggInit(m.aM33, VR_SEC_M33); AggInit(m.aH2, VR_SEC_H2);
   AggInit(m.aH6, VR_SEC_H6);   AggInit(m.aH12, VR_SEC_H12);
   StrutInit(m.sM12, p.frattaleK, VR_SEC_M12);
   StrutInit(m.sM33, p.frattaleK, VR_SEC_M33);
   StrutInit(m.sH2,  p.frattaleK, VR_SEC_H2);
   StrutInit(m.sH6,  p.frattaleK, VR_SEC_H6);
   StrutInit(m.sH12, p.frattaleK, VR_SEC_H12);
   D1Init(m.d1);
   m.giornoVwap = 0; m.cumPV = 0.0; m.cumV = 0.0;
   m.giornoM6 = 0; m.haPrec = false; m.precH = 0.0; m.precL = 0.0;
   m.haSpinta = false; m.maxH = 0.0; m.minL = 0.0; m.stopN = 0;
   m.oggi = 0; m.ultimoIngresso = 0;
   m.meseCorrente = 0; m.meseAgitato = false;
   m.pronto = false;
}

//--- Primo istante del mese di t. Senza librerie di calendario: si
//--- risale dai giorni, perche' i mesi hanno lunghezze diverse.
datetime VrInizioMese(const datetime t)
{
   long giorni = (long)(t / 86400);           // giorni dal 1/1/1970 (giovedi')
   int  anno = 1970;
   for(;;)
   {
      const bool bis = ((anno % 4 == 0 && anno % 100 != 0) || anno % 400 == 0);
      const int  len = (bis ? 366 : 365);
      if(giorni < len) break;
      giorni -= len; anno++;
   }
   const bool bis = ((anno % 4 == 0 && anno % 100 != 0) || anno % 400 == 0);
   int lunghezza[12];
   lunghezza[0]=31; lunghezza[1]=(bis?29:28); lunghezza[2]=31; lunghezza[3]=30;
   lunghezza[4]=31; lunghezza[5]=30; lunghezza[6]=31; lunghezza[7]=31;
   lunghezza[8]=30; lunghezza[9]=31; lunghezza[10]=30; lunghezza[11]=31;
   long dalPrimo = 0;
   for(int mese = 0; mese < 12; mese++)
   {
      if(giorni < lunghezza[mese]) { dalPrimo = (long)(t / 86400) - giorni; break; }
      giorni -= lunghezza[mese];
   }
   return (datetime)(dalPrimo * 86400);
}

int VrOraDi(const datetime t) { return (int)((t % 86400) / 3600); }

//--- Alimenta il motore con un minuto. Ritorna true se una candela M6
//--- si e' chiusa, e in quel caso "e" contiene la valutazione.
bool MotorePasso(Motore &m, const datetime t, const double o, const double h,
                 const double l, const double c, const double v, Esito &e)
{
   EsitoAzzera(e);

   // --- giornate, ATR, filtro di fondo -------------------------------
   D1Aggiungi(m.d1, t, o, h, l, c, m.p.mediaMacro);
   m.pronto = (m.d1.n >= VR_MIN_STORIA_ATR);   // riscaldamento, vedi in fondo

   // --- timeframe della struttura ------------------------------------
   datetime bt = 0; double bo = 0, bh = 0, bl = 0, bc = 0, bv = 0;
   if(AggAggiungi(m.aM12, t, o, h, l, c, v, bt, bo, bh, bl, bc, bv))
      StrutAggiungi(m.sM12, bt, bh, bl, bc);
   if(AggAggiungi(m.aM33, t, o, h, l, c, v, bt, bo, bh, bl, bc, bv))
      StrutAggiungi(m.sM33, bt, bh, bl, bc);
   if(AggAggiungi(m.aH2,  t, o, h, l, c, v, bt, bo, bh, bl, bc, bv))
      StrutAggiungi(m.sH2,  bt, bh, bl, bc);
   if(AggAggiungi(m.aH6,  t, o, h, l, c, v, bt, bo, bh, bl, bc, bv))
      StrutAggiungi(m.sH6,  bt, bh, bl, bc);
   if(AggAggiungi(m.aH12, t, o, h, l, c, v, bt, bo, bh, bl, bc, bv))
      StrutAggiungi(m.sH12, bt, bh, bl, bc);

   // --- la candela d'ingresso ----------------------------------------
   if(!AggAggiungi(m.aM6, t, o, h, l, c, v, bt, bo, bh, bl, bc, bv))
      return false;

   const datetime barra   = bt;
   const datetime istante = (datetime)(barra + VR_SEC_M6);
   const datetime giorno  = VrGiornoDi(barra);

   // nuovo giorno: VWAP, estremi, conteggio operazioni
   if(giorno != m.giornoM6)
   {
      m.giornoM6 = giorno;
      m.cumPV = 0.0; m.cumV = 0.0;
      m.haSpinta = false; m.maxH = 0.0; m.minL = 0.0;
      m.stopN = 0;
      m.oggi = 0;
   }
   // nuovo mese: si decide una volta sola, con la storia fino a ieri
   const datetime mese = VrInizioMese(barra);
   if(mese != m.meseCorrente)
   {
      m.meseCorrente = mese;
      m.meseAgitato  = VrMeseAgitato(m.d1, mese, m.p.fattoreAlta);
   }

   // VWAP sulle M6, ancorato a 00:00 UTC, prezzo tipico pesato al volume
   m.cumPV += ((bh + bl + bc) / 3.0) * bv;
   m.cumV  += bv;
   const double vwap = (m.cumV > 0.0 ? m.cumPV / m.cumV : 0.0);
   const bool   vwapOk = (m.cumV > 0.0);

   e.valutata = true;
   e.barra = barra; e.istante = istante; e.vwap = vwap;
   e.agitato = m.meseAgitato;
   e.stH6  = StrutStatoA(m.sH6,  istante);
   e.stH2  = StrutStatoA(m.sH2,  istante);
   e.stM33 = StrutStatoA(m.sM33, istante);
   e.stH12 = StrutStatoA(m.sH12, istante);
   e.stM12 = StrutStatoA(m.sM12, istante);

   // --- condizione 1: l'orario si legge sull'APERTURA della barra -----
   // Guardare l'orologio invece della candela sposta la finestra di sei
   // minuti e la barra delle 18:54, che la strategia accetta, non
   // comparirebbe mai. E' una delle nove divergenze del pannello.
   const int ora = VrOraDi(barra);
   e.c1_orario = (ora >= m.p.oraInizio && ora < m.p.oraFine);

   // --- condizione 7: non piu' di 3 al giorno, 30 minuti fra una e l'altra
   e.c7_frequenza = (m.oggi < m.p.maxAlGiorno) &&
                    (m.ultimoIngresso == 0 ||
                     (istante - m.ultimoIngresso) >= (datetime)(m.p.attesaMinuti * 60));

   // --- soglie: in dollari, o riscalate se il mese e' agitato ---------
   Soglie s;
   SoglieBase(s, m.p.impulsoMin, m.p.buffer, m.p.rischioMin, m.p.rischioMax);
   bool sogliePronte = true;
   if(m.meseAgitato)
   {
      double atrOggi = 0.0;
      if(D1AtrPer(m.d1, giorno, atrOggi) && m.p.mediaAtrRif > 0.0)
         SoglieScala(s, atrOggi, m.p.mediaAtrRif);
      else
         sogliePronte = false;      // il motore salta la barra: qui idem
   }
   e.sogliaImpulso = s.impulso;
   e.rischioMinimo = s.rischioMin;
   e.rischioMassimo = s.rischioMax;

   // --- condizioni 2, 3a, 3b, 4a, 4b, 5, 6 su ciascun lato ------------
   // Long prima, come nel motore. I due lati si escludono da soli: la
   // struttura non puo' essere +1 e -1 insieme.
   for(int passo = 0; passo < 2; passo++)
   {
      const int lato = (passo == 0 ? VR_LONG : VR_SHORT);
      if(m.p.soloLong && lato == VR_SHORT) continue;

      const bool strut = (e.stH6 == lato && e.stH2 == lato);
      const bool conf  = (e.stM33 == lato && e.stH12 == lato);
      // il ritracciamento chiede che M12 NON sia allineato: neutro va bene
      const bool ritr  = (e.stM12 != lato);

      bool tocca = false;
      double spinta = 0.0;
      if(m.haPrec && vwapOk)
      {
         if(lato == VR_LONG)
         {
            tocca  = (bl <= vwap && bc > vwap && bc > m.precH);
            spinta = (m.haSpinta ? m.maxH - vwap : 0.0);
         }
         else
         {
            tocca  = (bh >= vwap && bc < vwap && bc < m.precL);
            spinta = (m.haSpinta ? vwap - m.minL : 0.0);
         }
      }

      double stop = 0.0, rischio = 0.0;
      if(vwapOk)
      {
         // stop strutturale: minimo (massimo) delle ultime barreStop
         // candele DELLA GIORNATA, compresa questa, piu' il buffer
         double estremo = (lato == VR_LONG ? bl : bh);
         const int quante = (m.stopN < m.p.barreStop ? m.stopN : m.p.barreStop);
         for(int i = 0; i < quante; i++)
         {
            const int idx = m.stopN - 1 - i;
            if(m.stopG[idx % VR_STOPBAR] != giorno) break;
            if(lato == VR_LONG) estremo = MathMin(estremo, m.stopL[idx % VR_STOPBAR]);
            else                estremo = MathMax(estremo, m.stopH[idx % VR_STOPBAR]);
         }
         stop    = (lato == VR_LONG ? estremo - s.buffer : estremo + s.buffer);
         rischio = (lato == VR_LONG ? bc - stop : stop - bc);
      }

      bool sopraMedia = false;
      const bool macroOk = D1MacroPer(m.d1, giorno, m.p.mediaMacro, sopraMedia);
      const bool macro   = macroOk && (sopraMedia == (lato == VR_LONG));

      const bool rischioOk = sogliePronte && vwapOk &&
                             (rischio >= s.rischioMin && rischio <= s.rischioMax);

      // il lato "candidato" e' quello con struttura e reclaim: e' cosi'
      // che il motore sceglie, prima ancora di guardare macro e rischio
      if(strut && tocca && sogliePronte && spinta >= s.impulso)
      {
         e.lato = lato;
         e.c2_struttura = true; e.c3a_conferme = conf; e.c3b_ritracciamento = ritr;
         e.c4a_impulso = true;  e.c4b_reclaim = true;
         e.c5_macro = macro;    e.c6_rischio = rischioOk;
         e.entry = bc; e.stop = stop; e.rischio = rischio; e.spinta = spinta;
         break;
      }
      // nessun lato candidato: si registra comunque il piu' informativo
      if(e.lato == VR_NESSUNO)
      {
         e.c2_struttura = strut; e.c3a_conferme = conf; e.c3b_ritracciamento = ritr;
         e.c4a_impulso = (sogliePronte && spinta >= s.impulso);
         e.c4b_reclaim = tocca;  e.c5_macro = macro; e.c6_rischio = rischioOk;
         e.spinta = spinta;
      }
   }

   // ATTENZIONE, e' il punto piu' facile da sbagliare di tutto il file.
   //
   // segnali.genera() applica le conferme M33/H12 e il ritracciamento M12
   // DOPO, come filtro sulle operazioni prodotte: il tetto di tre al
   // giorno e l'attesa di trenta minuti sono gia' stati consumati dal
   // segnale grezzo, anche da quelli che le conferme scarteranno.
   // (`prepara_verifiche.py`: `ops = genera(m1, T)  # nessun filtro sulle
   // conferme: grezzo`, e solo dopo `tab[c_M33] & tab[c_H12] & ~tab[c_M12]`.)
   //
   // Un EA che contasse solo le operazioni APERTE si troverebbe posti
   // liberi che il motore non ha, e aprirebbe piu' tardi nella giornata
   // operazioni che nel motore non esistono. Quindi: "consuma" e' il
   // segnale grezzo, "apre" e' il segnale grezzo piu' le conferme.
   e.consuma = (e.lato != VR_NESSUNO && e.c1_orario && e.c4a_impulso &&
                e.c4b_reclaim && e.c5_macro && e.c6_rischio && e.c7_frequenza &&
                m.pronto);
   e.apre = (e.consuma && e.c3a_conferme && e.c3b_ritracciamento);

   // --- aggiornamento dello stato per la barra successiva -------------
   if(!m.haSpinta) { m.maxH = bh; m.minL = bl; m.haSpinta = true; }
   else { m.maxH = MathMax(m.maxH, bh); m.minL = MathMin(m.minL, bl); }
   m.stopH[m.stopN % VR_STOPBAR] = bh;
   m.stopL[m.stopN % VR_STOPBAR] = bl;
   m.stopG[m.stopN % VR_STOPBAR] = giorno;
   m.stopN++;
   m.precH = bh; m.precL = bl; m.haPrec = true;
   return true;
}

//--- Da chiamare quando un'operazione viene aperta davvero: e' cio' che
//--- fa scattare il tetto giornaliero e l'attesa di 30 minuti.
void MotoreRegistraIngresso(Motore &m, const datetime istante)
{
   m.oggi++;
   m.ultimoIngresso = istante;
}

//--- Riscaldamento: senza abbastanza giornate il filtro di fondo, l'ATR
//--- e la classificazione dei mesi sarebbero diversi da quelli del
//--- motore, e l'EA aprirebbe operazioni diverse SENZA dirlo.
bool MotoreRiscaldamentoOk(const Motore &m)
{
   return (m.d1.n >= VR_MIN_STORIA_ATR);
}

#endif // VWAP_RECLAIM_CORE_MQH
