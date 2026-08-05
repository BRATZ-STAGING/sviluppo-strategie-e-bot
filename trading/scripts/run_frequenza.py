#!/usr/bin/env python3
"""Frequenza contro vantaggio: si possono fare 10 operazioni al giorno?

Si allentano progressivamente le condizioni d'ingresso e si misura, per ogni
livello di frequenza, il vantaggio LORDO (prima dello spread) e quello netto.
La domanda non e' "quante operazioni si riescono a fare" ma "il vantaggio
sopravvive alla frequenza".
"""
import dataclasses, sys
import numpy as np, pandas as pd
sys.path.insert(0,"/workspace/sviluppo-strategie-e-bot/trading")
from framework.gestione import esito, chiusura_fine_giornata
from framework.data import load_m1
from framework.segnali import genera
from framework.taratura import UFFICIALE as T
pd.set_option("display.width",230)
SPREAD=0.63

def misura(m1, tf, imp, macro_on, max_gg, attesa):
    tar=dataclasses.replace(T, tf_ingresso=tf, conferme=(), ritracciamento=(),
        rischio_min=0.1, rischio_max=100.0, impulso_min=imp,
        max_operazioni_giorno=max_gg, attesa_minuti=attesa,
        media_macro=T.media_macro if macro_on else 1)
    ops=genera(m1, tar)
    if not ops: return None
    giorni=len({o["time"].date() for o in ops})
    out={"tf":tf,"impulso":imp,"macro":"si" if macro_on else "no",
         "max/gg":max_gg,"attesa":attesa,"n":len(ops),
         "op/giorno":len(ops)/max(giorni,1)}
    for st in (3.0,5.0,15.0):
        costo=SPREAD/st; lordi=[]; netti=[]
        for o in ops:
            fav=o["fav"]*o["rischio"]/st; sfav=o["sfav"]*o["rischio"]/st
            eod=o["r_eod"]*o["rischio"]/st
            r,mo=esito(fav,sfav,3.0,costo=0.0)
            if r is None: r=eod
            lordi.append(r); netti.append(r-costo)
        out[f"lordo {st:g}$"]=float(np.mean(lordi))
        out[f"netto {st:g}$"]=float(np.mean(netti))
    return out

if __name__=="__main__":
    m1=load_m1("/workspace/sviluppo-strategie-e-bot/data/XAUUSD_M1")
    prove=[("M6",4.0,True,3,30),("M6",2.0,True,8,10),("M6",1.0,False,20,3),
           ("M3",2.0,True,8,10),("M3",1.0,False,20,3),("M3",0.5,False,40,1),
           ("M1",1.0,False,20,3),("M1",0.5,False,40,1)]
    righe=[]
    for tf,imp,mac,mg,att in prove:
        r=misura(m1,tf,imp,mac,mg,att)
        if r: righe.append(r); print(f"fatto {tf} imp={imp} macro={mac}: "
                                    f"{r['n']} op, {r['op/giorno']:.2f}/giorno", flush=True)
    d=pd.DataFrame(righe).sort_values("op/giorno")
    print("\n=== FREQUENZA CONTRO VANTAGGIO (obiettivo 1:3, spread reale 0,63 $) ===")
    print(d.to_string(index=False,float_format=lambda x:f"{x:+.3f}"))
    d.to_parquet("freq.parquet")
