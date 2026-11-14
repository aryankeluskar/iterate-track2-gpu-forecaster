import sys; sys.path.insert(0,'/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/code')
from common import *
import warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width',250,'display.max_rows',200,'display.max_columns',30)
s,cat=load(); cat=cat.set_index('series_id')
s=s[(s.date<='2026-08-31')&s.series_id.isin(cat.index[cat.table=='daily_statistics'])]
s=s.merge(cat[['model','family']],left_on='series_id',right_index=True)
s=s.sort_values(['series_id','date']); s['prev']=s.groupby('series_id').value.shift(); s['pd']=s.groupby('series_id').date.shift()
e=s[(s.date-s.pd).dt.days==1].copy(); e['lc']=np.log(e.value/e.prev); e['chg']=(e.lc.abs()>1e-9)
# restrict to series that ever change >=2 times in dev (step series with a real hazard)
nchg=e.groupby('series_id').chg.sum(); e=e[e.series_id.isin(nchg[nchg>=2].index)]
print('series with >=2 changes:',e.series_id.nunique(),'obs',len(e),'base daily change prob',e.chg.mean().round(3))
print(e.groupby('instrument_class').agg(n_ser=('series_id','nunique'),p_chg=('chg','mean')).round(3))
# time since last change
e=e.sort_values(['series_id','date']); 
def tsl(g):
    c=g.chg.values; t=np.zeros(len(c),int); k=0
    for i in range(len(c)): t[i]=k; k=0 if c[i] else k+1   # days since last change BEFORE this day
    return pd.Series(t,index=g.index)
e['tsl']=e.groupby('series_id',group_keys=False).apply(tsl)
b=pd.cut(e.tsl,[-1,0,1,2,4,7,14,30,400]); print('\nP(change today | days since last change)'); print(e.groupby(b).chg.agg(['mean','size']).round(3))
# class rate card / spot step series only
for cl in ['neocloud_rate_card','hyperscaler_list','neocloud_spot','hyperscaler_spot']:
    u=e[e.instrument_class==cl]; 
    if len(u)<50: continue
    print(cl,'n_ser',u.series_id.nunique()); print(u.groupby(pd.cut(u.tsl,[-1,0,2,6,14,40,400])).chg.agg(['mean','size']).round(3).T)
e['dow']=e.date.dt.dayofweek; e['dom']=e.date.dt.day
print('\nDOW'); print(e.groupby('dow').chg.agg(['mean','size']).round(3).T)
print('DOM bucket'); print(e.groupby(pd.cut(e.dom,[0,1,3,7,14,21,28,31])).chg.agg(['mean','size']).round(3).T)
print('first-of-month vs rest by class'); print(e.assign(first=e.dom<=2).groupby(['instrument_class','first']).chg.mean().unstack().round(3))
# collector-wide: per day share of series changing (afhubbard only)
a=e[e.source_id=='afhubbard']; day=a.groupby('date').chg.agg(['mean','sum','size'])
print('\nafhubbard days',len(day),'mean daily share changing',day['mean'].mean().round(3),'p90',day['mean'].quantile(.9).round(3),'max',day['mean'].max().round(3))
# overdispersion: observed var of daily share vs binomial
p=a.chg.mean(); n=day['size'].mean(); print('var observed',day['mean'].var().round(5),'binomial var',round(p*(1-p)/n,5))
# probability a series changes today given >=20% of OTHER series changed today (leave-one-out)
a=a.merge(day[['sum','size']].rename(columns={'sum':'S','size':'N'}),left_on='date',right_index=True); a['others']=(a.S-a.chg.astype(int))/(a.N-1)
print(a.groupby(pd.cut(a.others,[-.01,0.05,.1,.2,.4,1])).chg.agg(['mean','size']).round(3))
print('top days by share changing'); print(day.sort_values('mean',ascending=False).head(8).round(3))
# which class drives the refresh days: share of each class changing on top days
# direction asymmetry
nz=e[e.chg]; print('\ndirection: share of changes that are cuts, by class'); print(nz.groupby('instrument_class').apply(lambda g: pd.Series({'n':len(g),'cut_share':(g.lc<0).mean(),'mean_log_chg':g.lc.mean(),'mean_cut':g.lc[g.lc<0].mean(),'mean_rise':g.lc[g.lc>0].mean()})).round(3))
print(nz.groupby('family').apply(lambda g: pd.Series({'n':len(g),'cut_share':(g.lc<0).mean(),'mean_log_chg':g.lc.mean()})).round(3))
# level drift H100/A100/H200 per 30d: regress log level on date, per series in afhubbard (dev)
ss=s[s.family.isin(['H100','A100','H200'])&(s.source_id=='afhubbard')]
out=[]
for sid,g in ss.groupby('series_id'):
    if len(g)<60: continue
    t=(g.date-g.date.min()).dt.days.values; y=np.log(g.value.values); b_=np.polyfit(t,y,1)[0]*30
    out.append((sid,g.family.iloc[0],g.instrument_class.iloc[0],len(g),b_,np.log(g.value.iloc[-1]/g.value.iloc[0])))
o=pd.DataFrame(out,columns=['sid','fam','ic','n','pct_per_30d_slope','total_logchg'])
print('\nlevel drift per 30d (log slope, afhubbard, Jan-Aug dev)'); print(o.groupby(['fam','ic']).agg(n=('sid','size'),med=('pct_per_30d_slope','median'),mean=('pct_per_30d_slope','mean')).round(4)); 
print(o.groupby('fam').pct_per_30d_slope.median().round(4))
# monthly median level path for key series
for k in ['afhubbard.hyperscaler_list.H100_SXM_80GB.on_demand.median','afhubbard.neocloud_rate_card.H100_SXM_80GB.on_demand.median','afhubbard.neocloud_rate_card.A100_SXM_80GB.on_demand.median','afhubbard.neocloud_rate_card.H200.on_demand.median']:
    if k in cat.index:
        g=s[s.series_id==k].set_index('date').value; print(k.replace('afhubbard.',''),g.resample('MS').median().round(3).to_dict().values())
nz.to_csv(R+'dev_change_events_stepseries.csv',index=False,columns=['series_id','date','prev','value','lc','source_id','instrument_class'])
