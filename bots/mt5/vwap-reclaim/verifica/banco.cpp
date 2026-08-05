// Banco di prova del nucleo dell'EA, fuori da MT5.
//
// Compila VwapReclaimCore.mqh con g++ e gli passa le stesse candele M1 che
// legge il motore Python, un minuto alla volta. Stampa ogni segnale grezzo
// con le sette condizioni, e serve a rispondere all'unica domanda che conta
// prima di mettere l'EA su un conto: produce le stesse operazioni?
//
//   g++ -O2 -o banco banco.cpp
//   ./banco m1.csv > segnali_ea.csv
//
// Ingresso: CSV senza intestazione, "epoch,open,high,low,close,volume",
// ordinato per tempo. Lo produce confronta.py.
//
// Uscita: CSV con intestazione, una riga per candela M6 che ha prodotto un
// segnale grezzo (quello che il motore conta) e la colonna "apre" a dire se
// passa anche le conferme.
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "../VwapReclaimCore.mqh"

static const char *IsoUtc(datetime t, char *buf, size_t n)
{
   // conversione epoch -> "YYYY-MM-DD HH:MM:SS" senza dipendere da gmtime,
   // cosi' il banco non cambia risultato col fuso della macchina
   long giorni = (long)(t / 86400);
   long resto  = (long)(t % 86400);
   int anno = 1970;
   for(;;)
   {
      const bool bis = ((anno % 4 == 0 && anno % 100 != 0) || anno % 400 == 0);
      const int  len = bis ? 366 : 365;
      if(giorni < len) break;
      giorni -= len; anno++;
   }
   const bool bis = ((anno % 4 == 0 && anno % 100 != 0) || anno % 400 == 0);
   int lung[12] = {31, bis ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
   int mese = 0;
   while(giorni >= lung[mese]) { giorni -= lung[mese]; mese++; }
   snprintf(buf, n, "%04d-%02d-%02d %02d:%02d:%02d", anno, mese + 1,
            (int)giorni + 1, (int)(resto / 3600), (int)((resto % 3600) / 60),
            (int)(resto % 60));
   return buf;
}

int main(int argc, char **argv)
{
   if(argc < 2)
   {
      fprintf(stderr, "uso: banco <m1.csv> [--tutte]\n");
      return 1;
   }
   const bool tutte = (argc > 2 && strcmp(argv[2], "--tutte") == 0);

   FILE *f = fopen(argv[1], "r");
   if(!f) { fprintf(stderr, "non riesco ad aprire %s\n", argv[1]); return 1; }

   Parametri p;
   ParametriUfficiali(p);
   Motore m;
   MotoreInit(m, p);

   printf("time,barra,lato,apre,consuma,entry,stop,rischio,spinta,vwap,"
          "soglia_impulso,agitato,c1,c2,c3a,c3b,c4a,c4b,c5,c6,c7,"
          "st_h6,st_h2,st_m33,st_h12,st_m12\n");

   char riga[256], buf[48], buf2[48];
   long long minuti = 0, segnali = 0, aperte = 0;
   // conteggi per capire DOVE si ferma, quando non esce niente: senza questi
   // "zero segnali" e' un muro liscio
   long long barre = 0, cPronto = 0, c1 = 0, c2 = 0, c4a = 0, c4b = 0,
             c5 = 0, c6 = 0, cLato = 0;
   while(fgets(riga, sizeof(riga), f))
   {
      long long ts;
      double o, h, l, c, v;
      if(sscanf(riga, "%lld,%lf,%lf,%lf,%lf,%lf", &ts, &o, &h, &l, &c, &v) != 6)
         continue;
      minuti++;
      Esito e;
      if(!MotorePasso(m, (datetime)ts, o, h, l, c, v, e)) continue;
      if(!e.valutata) continue;
      barre++;
      if(MotoreRiscaldamentoOk(m)) cPronto++;
      if(e.c1_orario) c1++;
      if(e.c2_struttura) c2++;
      if(e.c4a_impulso) c4a++;
      if(e.c4b_reclaim) c4b++;
      if(e.c5_macro) c5++;
      if(e.c6_rischio) c6++;
      if(e.lato != VR_NESSUNO) cLato++;
      if(!(e.consuma || (tutte && e.lato != VR_NESSUNO))) continue;

      if(e.consuma) { segnali++; MotoreRegistraIngresso(m, e.istante); }
      if(e.apre) aperte++;

      printf("%s,%s,%s,%d,%d,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%d,"
             "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
             IsoUtc(e.istante, buf, sizeof(buf)),
             IsoUtc(e.barra, buf2, sizeof(buf2)),
             e.lato == VR_LONG ? "long" : (e.lato == VR_SHORT ? "short" : "-"),
             e.apre ? 1 : 0, e.consuma ? 1 : 0,
             e.entry, e.stop, e.rischio, e.spinta, e.vwap, e.sogliaImpulso,
             e.agitato ? 1 : 0,
             e.c1_orario ? 1 : 0, e.c2_struttura ? 1 : 0, e.c3a_conferme ? 1 : 0,
             e.c3b_ritracciamento ? 1 : 0, e.c4a_impulso ? 1 : 0,
             e.c4b_reclaim ? 1 : 0, e.c5_macro ? 1 : 0, e.c6_rischio ? 1 : 0,
             e.c7_frequenza ? 1 : 0,
             e.stH6, e.stH2, e.stM33, e.stH12, e.stM12);
   }
   fclose(f);
   fprintf(stderr,
           "minuti %lld · barre M6 %lld · riscaldate %lld\n"
           "c1 orario %lld · c2 struttura %lld · c4a impulso %lld · "
           "c4b reclaim %lld · c5 macro %lld · c6 rischio %lld · lato %lld\n"
           "segnali grezzi %lld · con conferme %lld\n",
           minuti, barre, cPronto, c1, c2, c4a, c4b, c5, c6, cLato,
           segnali, aperte);
   return 0;
}
