import pickle, json
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from offline import *
from gpuf.methods.stack import _lp3
cells,C=load(); S=subsets(cells); E=len(BANK)
cfgs,preds=pickle.load(open("runs/stack/grid_preds.pkl","rb"))
def find(**kw):
    for i,p in enumerate(cfgs):
        if all(p.get(k)==v for k,v in kw.items()): return i
    raise KeyError(kw)
fin={
 "equal(11)":None,
 "b ewa h eta5 g.9":find(comb="ewa",key="h",tsep=False,eta=5,gamma=0.9),
 "b ewa h eta20 g.97 (prior)":find(comb="ewa",key="h",tsep=False,eta=20,gamma=0.97),
 "c ewa h x tau eta5 g.9":find(comb="ewa",key="h",tsep=True,eta=5,gamma=0.9),
 "d ewa h x collector x class eta5 g.9":find(comb="ewa",key="grp",tsep=False,eta=5,gamma=0.9),
 "e fixed share eta5 a.2":find(comb="fs",eta=5,alpha=0.2),
 "e follow-the-leader g.9":find(comb="ftl",gamma=0.9),
 "f stack w14 lam.5":find(comb="stack",tsep=False,window=14,lam=0.5),
 "f stack w14 lam0":find(comb="stack",tsep=False,window=14,lam=0.0),
 "f stack w14 lam.5 x tau":find(comb="stack",tsep=True,window=14,lam=0.5),
}
res={}
res["equal(11)"]=score_cells(cells,run(cells,C,comb="equal"))
for k,i in fin.items():
    if i is not None: res[k]=score_cells(cells,preds[i])
# oracles
sing={b:score_cells(cells,np.sort(np.exp(C["logq"][i]),1)) for i,b in enumerate(BANK)}
best=max(sing,key=lambda b:skill(sing[b])); res[f"ORACLE best single in hindsight ({best})"]=sing[best]
Wo=np.stack([_lp3(C["logq"][:,C["h"]==h,:],np.log(C["y"][C["h"]==h]),C["y"][C["h"]==h],E)[0] for h in (1,3,7)])
q=np.zeros((len(cells),3))
for i in range(len(cells)): q[i]=blend(np.tile(Wo[[1,3,7].index(C["h"][i]) if False else {1:0,3:1,7:2}[C["h"][i]]],(3,1)),C["logq"][:,i,:])
res["ORACLE in-sample best fixed weights per h (LP)"]=score_cells(cells,q)
json.dump({str(h):dict(zip(BANK,map(float,Wo[j]))) for j,h in enumerate((1,3,7))},open("experiments/stack/results/oracle_weights.json","w"),indent=1)
eqc=res["equal(11)"]; bestc=res[f"ORACLE best single in hindsight ({best})"]
rows=[]
for k,c in res.items():
    r={"combiner":k}
    for sn,ov in S.items():
        m=c.origin_day.isin(ov); r[sn]=skill(c[m])
    for sn in ("all","last25","ex14"):
        m=c.origin_day.isin(S[sn]); a=c[m].reset_index(drop=True); b=eqc[m].reset_index(drop=True)
        p=paired(a,b); r[f"d_vs_equal_{sn}"]=p["d_pooled_skill"]; r[f"ci_{sn}"]=p["ci90_d_pooled_skill"]
    b=bestc[c.origin_day.isin(S["all"])].reset_index(drop=True)
    p=paired(c.reset_index(drop=True),b); r["d_vs_best_single_all"]=p["d_pooled_skill"]; r["ci_vs_best_all"]=p["ci90_d_pooled_skill"]
    cov=((cells.y>=c.q10)&(cells.y<=c.q90)).mean(); r["coverage"]=float(cov)
    rows.append(r)
T=pd.DataFrame(rows); pd.set_option("display.width",300); pd.set_option("display.max_colwidth",60)
T.to_csv("experiments/stack/results/finalists.csv",index=False)
print(T.round(4).to_string())
# regret curves
tot=cells.baseline_loss.sum()
def reg(c,ref):
    d=(c.loss-ref.loss).groupby(cells.origin_day).sum().cumsum()/tot
    return d
plt.figure(figsize=(9,5))
ref=bestc
for k in ["equal(11)","b ewa h eta5 g.9","d ewa h x collector x class eta5 g.9","e fixed share eta5 a.2","e follow-the-leader g.9","f stack w14 lam.5","f stack w14 lam.5 x tau"]:
    r=reg(res[k],ref); plt.plot(range(len(r)),r.values,label=k)
plt.axhline(0,color="k",lw=.5); plt.xlabel("dev origin index (0=2026-08-18)"); plt.ylabel("cumulative loss minus best single (skill points of total baseline loss; negative = better)")
plt.legend(fontsize=7); plt.title(f"Regret vs hindsight best single expert ({best})"); plt.tight_layout(); plt.savefig("experiments/stack/results/regret.png",dpi=110)
R=pd.DataFrame({k:reg(res[k],ref).values for k in res}); R.index=sorted(cells.origin_day.unique()); R.to_csv("experiments/stack/results/regret_vs_best_single.csv")
print(R.iloc[[0,6,13,24,37,49]].round(4).T.to_string())
# weights over time
def traj(**p):
    out=[]
    for d in np.sort(cells.origin_day.unique()):
        keys,eq=weights(d,C,**p); out.append({h:lookup(keys,eq,h,"","h") for h in (1,3,7)})
    return out
for name,p in {"ewa_hxtau":dict(comb="ewa",key="h",tsep=True,eta=5,gamma=0.9),"stack_w14":dict(comb="stack",key="h",tsep=False,window=14,lam=0.5)}.items():
    tr=traj(**p); recs=[]
    for i,d in enumerate(np.sort(cells.origin_day.unique())):
        for h in (1,3,7):
            for t,tn in enumerate(("q10","q50","q90")):
                recs.append(dict(origin_day=d,idx=i,h=h,tau=tn,**dict(zip(BANK,tr[i][h][t]))))
    W=pd.DataFrame(recs); W.to_csv(f"experiments/stack/results/weights_{name}.csv",index=False)
    last=W[W.idx==W.idx.max()]
    print("\n",name,"last-origin weights"); print(last.drop(columns=["origin_day","idx"]).round(2).to_string(index=False))
    for lo,hi in ((14,24),(25,49)):
        s=W[(W.idx>=lo)&(W.idx<=hi)&(W.tau=="q90")].groupby("h")[BANK].mean()
        print(f"mean q90 weights idx {lo}-{hi}"); print(s.round(2).to_string())
    mv=W.sort_values(["h","tau","idx"]).groupby(["h","tau"])[BANK].diff().abs().sum(axis=1)/2
    print("mean daily turnover (L1/2):",round(mv.mean(),4))
    fig,ax=plt.subplots(1,3,figsize=(15,3.6),sharey=True)
    for j,h in enumerate((1,3,7)):
        s=W[(W.h==h)&(W.tau=="q90")].set_index("idx")[BANK]; s.plot.area(ax=ax[j],legend=(j==2),lw=0); ax[j].set_title(f"{name} q90 weights h={h}")
    plt.tight_layout(); plt.savefig(f"experiments/stack/results/weights_{name}.png",dpi=100)
