#!/usr/bin/env python3
"""Stop a pareggio appena l'operazione va di 1 punto in vantaggio: conviene?

Idea dell'utente. Con uno stop da 3 $, portare a pareggio a +1 $ significa
armare il pareggio a +0,33 R: molto presto. E il pareggio NON e' zero, costa
lo spread (0,63 $), quindi uscire "a pareggio" e' comunque una piccola perdita.

Si provano soglie da 1 a 5 dollari, piu' il caso senza pareggio, su ogni
combinazione di stop e obiettivo.
"""
import dataclasses, sys
import numpy as np, pandas as pd
sys.path.insert(0,"/workspace/sviluppo-strategie-e-bot/trading"); sys.path.insert(0,".")
from framework.data import TIMEFRAMES, load_m1, resample_tf
from framework.gestione import esito, chiusura_fine_giornata
from framework.segnali import genera
from framework.taratura import UFFICIALE as T
from ob import order_blocks, dentro_una_zona
pd.set_option("display.width",230)

SPREAD=0.63
STOP=[3.0,5.0]
RR=[3.0,5.0]
BE_DOLLARI=[None,1.0,2.0,3.0,5.0]

m1=load_m1("/workspace/sviluppo-strategie-e-bot/data/XAUUSD_M1")
zone=order_blocks(resample_tf(m1,"M33"),T.frattale_k,TIMEFRAMES["M33"])
tar=dataclasses.replace(T, tf_ingresso="M6", conferme=(), ritracciamento=(),
                        rischio_min=0.1, rischio_max=100.0, impulso_min=2.0,
                        max_operazioni_giorno=8, attesa_minuti=10)
righe=[]
for o in genera(m1, tar, tf_extra=("M33","H12","M12")):
    s=1 if o["lato"]=="long" else -1
    fav_d=o["fav"]*o["rischio"]; sfav_d=o["sfav"]*o["rischio"]; eod_d=o["r_eod"]*o["rischio"]
    rec={"anno":o["anno"],
         "conf":int(o["c_M33"] and o["c_H12"] and not o["c_M12"]),
         "ob":int(dentro_una_zona(zone,o["time"],o["entry"],s,2.5))}
    for st in STOP:
        fav,sfav=fav_d/st,sfav_d/st; costo=SPREAD/st
        for rr in RR:
            for bd in BE_DOLLARI:
                be = None if bd is None else bd/st
                if be is not None and be >= rr:
                    continue
                r,mo=esito(fav,sfav,rr,be=be,costo=costo)
                if r is None:
                    r=chiusura_fine_giornata(eod_d/st,be,False,float(fav.max()),costo)
                k=f"{st:g}_{rr:g}_{'no' if bd is None else f'{bd:g}'}"
                rec["r_"+k]=r; rec["m_"+k]=mo
    righe.append(rec)
d=pd.DataFrame(righe); d.to_parquet("be.parquet")
print(f"ingresso M6, {len(d)} segnali, spread reale {SPREAD} $\n")

def tab(sub, etichetta):
    out=[]
    for st in STOP:
        for rr in RR:
            riga={"stop":f"{st:g}$","RR":f"1:{rr:g}","n":len(sub)}
            for bd in BE_DOLLARI:
                if bd is not None and bd/st>=rr: continue
                k=f"{st:g}_{rr:g}_{'no' if bd is None else f'{bd:g}'}"
                v=sub["r_"+k].values; mo=sub["m_"+k].values
                nome="nessuno" if bd is None else f"+{bd:g}$"
                riga[nome]=v.mean()
                riga[nome+" %pari"]=(mo==3).mean()*100
            out.append(riga)
    print(f"\n--- {etichetta} ---")
    print(pd.DataFrame(out).to_string(index=False,float_format=lambda x:f"{x:+.3f}"))

tab(d,"tutti i segnali")
tab(d[(d.conf==1)&(d.ob==1)],"conferme E order block")
