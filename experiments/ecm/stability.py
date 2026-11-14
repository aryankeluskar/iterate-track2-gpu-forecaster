import sys, numpy as np, pandas as pd
sys.path.insert(0,'src'); sys.path.insert(0,'experiments/ecm')
from gpuf import compare, harness, methods
REF=["mix",{"pool":"cc","k":20,"state":"chgk","sk":3,"hl":30}]
ev=lambda n,p: harness.evaluate(methods.get(n,**p),'dev','rental_headline',name=n,params=p).cells
b=ev(*REF); c=ev('ecm',{'base':REF,'feats':['pos'],'skew':1.0})
m=c.merge(b[compare.KEY+['loss']],on=compare.KEY,suffixes=('','_b'))
tot=m.baseline_loss.sum()
m['dl']=m.loss_b-m.loss
print('gain share of total baseline loss by origin week:')
print((m.groupby('origin_week').dl.sum()/m.groupby('origin_week').baseline_loss.sum()).round(4).to_string())
print('by class', (m.groupby('instrument_class').dl.sum()/tot).round(5).to_dict())
big=(m.y/m.baseline-1).abs()>0.05
up=(m.y/m.baseline-1)>0.05; dn=(m.y/m.baseline-1)<-0.05
for lab,s in [('no change',m.y==m.baseline),('<1%',((m.y/m.baseline-1).abs()<0.01)&(m.y!=m.baseline)),('1-5%',((m.y/m.baseline-1).abs()>=0.01)&~big),('up>5%',up),('down>5%',dn)]:
    print(lab, int(s.sum()), round(float(m.dl[s].sum()/tot),5))
print('coverage below/above', float((m.y<m.q10).mean()), float((m.y>m.q90).mean()), 'base', float((b.y<b.q10).mean()), float((b.y>b.q90).mean()))
