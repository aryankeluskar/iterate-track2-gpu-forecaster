import sys; sys.path.insert(0,'/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/code')
from common import *
pd.set_option('display.width',250,'display.max_colwidth',80,'display.max_rows',200)
c=pd.read_parquet(O+'dev_cells.parquet'); s,cat=load()
w=c.pivot_table(index=['series_id','origin','h'],columns='method',values=['loss','q10','q90','y']).reset_index()
w.columns=['_'.join([a for a in col if a]) for col in w.columns]
w=w.rename(columns={'loss_last_value':'lv','loss_drift':'dr','y_drift':'y','q10_drift':'q10','q90_drift':'q90'})
w=w.merge(cat[['series_id','tier','source_id','instrument_class','model','family']],on='series_id')
w['date']=pd.to_datetime(w.origin.map(pd.Timestamp.fromordinal))
w.to_parquet(O+'dev_wide.parquet')
print('cells',len(w),'series',w.series_id.nunique()); print(w.groupby('source_id').agg(series=('series_id','nunique'),cells=('lv','size'),first=('date','min')))
def skill(g): return 1-g.dr.sum()/g.lv.sum()
def cov(g): return pd.Series({'below':(g.y<g.q10).mean(),'inside':((g.y>=g.q10)&(g.y<=g.q90)).mean(),'above':(g.y>g.q90).mean()})
for name,u in [('headline37',w[w.tier=='headline']),('all_rental',w)]:
    print('\n=====',name,'cells',len(u),'series',u.series_id.nunique(),'pooled lv',u.lv.mean(),'drift skill',skill(u))
    ser=u.groupby('series_id').lv.sum().sort_values(ascending=False); cs=ser.cumsum()/ser.sum()
    print('n series for 50/80/95% of baseline loss:',[(int((cs<q).sum()+1)) for q in (.5,.8,.95)],'of',len(ser))
    t=ser.head(12).to_frame('lv_sum'); t['share']=t.lv_sum/ser.sum(); t['cum']=cs.head(12)
    t['skill']=[skill(u[u.series_id==i]) for i in t.index]; t['cells']=[ (u.series_id==i).sum() for i in t.index]
    print(t)
    for k in ['instrument_class','source_id','h','family']:
        g=u.groupby(k).apply(lambda g: pd.Series({'series':g.series_id.nunique(),'cells':len(g),'lv_share':g.lv.sum()/u.lv.sum(),'lv_mean':g.lv.mean(),'drift_skill':skill(g),**cov(g)}))
        print(g.round(3))
    # by class x h
    print(u.groupby(['instrument_class','h']).apply(skill).unstack().round(3))
    ser.to_frame('lv_sum').assign(share=ser/ser.sum(),cum=cs).to_csv(R+f'loss_concentration_{name}.csv')
