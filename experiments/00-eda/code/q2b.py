import sys; sys.path.insert(0,'/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/code')
from common import *
pd.set_option('display.width',250,'display.max_colwidth',70,'display.max_rows',200,'display.max_columns',30)
w=pd.read_parquet(O+'dev_wide.parquet')
w['flat']=(w.q10==w.q90)
print('flat-fallback share all',w.flat.mean(),' headline',w[w.tier=='headline'].flat.mean())
print(w.groupby('source_id').flat.mean())
def sk(g): return 1-g.dr.sum()/g.lv.sum()
for name,u in [('headline37',w[w.tier=='headline']),('all',w)]:
    print('==',name)
    nf=u[~u.flat]; print('non-flat cells',len(nf),'skill on non-flat',sk(nf),'share lv loss in nonflat',nf.lv.sum()/u.lv.sum())
    ser=u.groupby('series_id').agg(lv=('lv','sum'),cells=('lv','size'),skill=('lv',lambda x:np.nan)).drop(columns='skill')
    ser['skill']=[sk(u[u.series_id==i]) for i in ser.index]; ser['share']=ser.lv/ser.lv.sum(); ser=ser.sort_values('share',ascending=False); ser['cum']=ser.share.cumsum()
    ser.index=[i.replace('gpurentalprices','gpr').replace('afhubbard','afh') for i in ser.index]
    print(ser.head(14).round(3))
    g=u.groupby(['instrument_class']).apply(lambda g: pd.Series({'n_ser':g.series_id.nunique(),'share':g.lv.sum()/u.lv.sum(),'skill':sk(g),'cov_in':((g.y>=g.q10)&(g.y<=g.q90)).mean(),'cov_in_nonflat':((g.y>=g.q10)&(g.y<=g.q90))[~g.flat].mean()}))
    print(g.round(3))
    g=u.groupby(['source_id']).apply(lambda g: pd.Series({'n_ser':g.series_id.nunique(),'share':g.lv.sum()/u.lv.sum(),'skill':sk(g)}))
    print(g.round(3))
    g=u.groupby(['h']).apply(lambda g: pd.Series({'share':g.lv.sum()/u.lv.sum(),'lv_mean':g.lv.mean(),'skill':sk(g)}))
    print(g.round(3))
# afhubbard-only (the only collector with real dev history)
a=w[w.source_id=='afhubbard']
print('== afhubbard all series: cells',len(a),'skill',sk(a)); 
print(a.groupby(['instrument_class','h']).apply(sk).unstack().round(3))
print(a.groupby('instrument_class').apply(lambda g: pd.Series({'n_ser':g.series_id.nunique(),'share':g.lv.sum()/a.lv.sum(),'skill':sk(g),'cov_in':((g.y>=g.q10)&(g.y<=g.q90)).mean(),'below':(g.y<g.q10).mean(),'above':(g.y>g.q90).mean()})).round(3))
ser=a.groupby('series_id').lv.sum().sort_values(ascending=False); cs=ser.cumsum()/ser.sum(); print('afh n series 50/80/95',[(int((cs<q).sum()+1)) for q in (.5,.8,.95)],len(ser))
