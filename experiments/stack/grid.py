import itertools, pickle, sys
from offline import *
cells,C=load(); S=subsets(cells)
cfgs=[]
for tsep in (False,True):
    for key in ("h","grp"):
        for eta,gm in itertools.product((5,20,80),(1.0,0.97,0.9)):
            cfgs.append(dict(comb="ewa",key=key,tsep=tsep,eta=eta,gamma=gm))
for eta,al in itertools.product((5,20,80),(0.01,0.05,0.2)):
    cfgs.append(dict(comb="fs",key="h",tsep=False,eta=eta,alpha=al))
for gm in (1.0,0.97,0.9):
    cfgs.append(dict(comb="ftl",key="h",tsep=False,gamma=gm))
for w,lam,ts in itertools.product((14,28,56),(0.0,0.5),(False,True)):
    cfgs.append(dict(comb="stack",key="h",tsep=ts,window=w,lam=lam))
rows=[]; preds={}
for i,p in enumerate(cfgs):
    q=run(cells,C,**p); c=score_cells(cells,q); preds[i]=q
    r=dict(p); r["cfg"]=i
    for k,v in S.items(): r[k]=skill(c[c.origin_day.isin(v)])
    rows.append(r); print(i,p,round(r["all"],4),flush=True)
pd.DataFrame(rows).to_csv("experiments/stack/results/grid.csv",index=False)
pickle.dump((cfgs,preds),open("runs/stack/grid_preds.pkl","wb"))
