import sys; sys.path.insert(0,'/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/code')
from common import *
import warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width',250,'display.max_rows',200,'display.max_columns',30)
s,cat=load(); cat=cat.set_index('series_id')
s=s[(s.date<='2026-08-31')&s.series_id.isin(cat.index[cat.table=='daily_statistics'])]
rows=[]
O_=pd.date_range('2026-05-01','2026-08-24').map(pd.Timestamp.toordinal).values
for sid,g in s.groupby('series_id'):
    g=g.sort_values('date'); d=g.date.map(pd.Timestamp.toordinal).values; v=g.value.values; idx={a:i for i,a in enumerate(d)}
    for o in O_:
        i1=np.searchsorted(d,o,side='right')-1
        if i1<0 or o-d[i1]>7: continue
        last=v[i1]
        for h in (1,3,7):
            if o+h not in idx: continue
            y=v[idx[o+h]]; r={'sid':sid,'o':o,'h':h,'y':y,'lv':last}
            for k in (3,5,7,14):
                m=(d<=o)&(d>o-k); r[f'm{k}']=np.median(v[m]) if m.any() else last
            rows.append(r)
D=pd.DataFrame(rows); D=D.merge(cat[['tier','instrument_class','source_id']],left_on='sid',right_index=True)
D.to_parquet(O+'smooth_cells.parquet')
def rep(u,label):
    base=np.abs(u.y-u.lv).sum(); out={'n':len(u),'ser':u.sid.nunique(),'lv_MAE':np.abs(u.y-u.lv).mean()}
    for k in (3,5,7,14): out[f'k{k}']=np.abs(u.y-u[f'm{k}']).sum()/base-1
    return pd.Series(out,name=label)
print('relative change in abs error vs last value (negative = smoothing better), loss-weighted (sum abs err in USD)')
print(pd.concat([rep(D,'all'),rep(D[D.tier=='headline'],'headline')],axis=1).T.round(3))
for h in (1,3,7): print(h); print(pd.concat([rep(D[D.h==h],'all')]+[rep(D[(D.h==h)&(D.instrument_class==c)],c) for c in sorted(D.instrument_class.unique())],axis=1).T.round(3))
# per-series: share of series where k=7 beats last value
sc=D.groupby(['sid']).apply(lambda u: pd.Series({'k7':np.abs(u.y-u.m7).sum()/max(np.abs(u.y-u.lv).sum(),1e-12)-1,'lv':np.abs(u.y-u.lv).sum()}))
sc=sc[sc.lv>0]; print('series with lv error>0:',len(sc),' share where k7 better:',(sc.k7<0).mean(),' loss-weighted share better',sc[sc.k7<0].lv.sum()/sc.lv.sum())
