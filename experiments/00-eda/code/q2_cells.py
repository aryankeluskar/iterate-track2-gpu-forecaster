# dev cells for last_value and drift on all daily_statistics series; origins daily 2026-05-01..2026-08-24, h=1,3,7
import sys; sys.path.insert(0,'/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/code')
from common import *
s,cat=load()
ds_ids=set(cat[cat.table=='daily_statistics'].series_id)
df=C.read_series_csv(O+'series_daily.csv'); df=df[df.series_id.isin(ds_ids)]
store=C.SeriesStore(df)
# harness check of drift quantiles vs demo_out at 10-24 (quantile identity only, no loss)
dem=pd.read_csv(ROOT+'demo_out/baseline_drift.csv'); dh=C.SeriesStore(C.read_series_csv(ROOT+'demo_out/history_2026-10-24.csv'))
o=day('2026-10-24'); mx=0; n=0
for sid,g in dem.groupby('series_id'):
    if sid.startswith('aws') or sid not in store: continue
    # use the same history file as the starter did
    rows=forecast_one(dh,sid,o,[1,3,7],'drift',20,None)
    for r in rows:
        gg=g[g.horizon_days==r['horizon_days']].iloc[0]
        mx=max(mx,abs(gg.q10-r['q10']),abs(gg.q50-r['q50']),abs(gg.q90-r['q90'])); n+=1
print('drift reproduction check (demo_out): cells',n,'max abs diff',mx)
origins=pd.date_range('2026-05-01','2026-08-24').map(pd.Timestamp.toordinal)
rows=[]
for sid in store.ids():
    d,v=store.arrays(sid)
    if d.max()<origins[0]+1 or d.min()>day('2026-08-31'): continue
    for o in origins:
        lv=store.history(sid,o)
        if len(lv[0])==0: continue
        for m in ['last_value','drift']:
            for r in forecast_one(store,sid,o,[1,3,7],m,20,None):
                y=store.value_at(sid,o+r['horizon_days'])
                if y is None: continue
                last_day=int(store.history(sid,o)[0][-1])
                rows.append((sid,o,r['horizon_days'],m,y,r['q10'],r['q50'],r['q90'],o-last_day))
c=pd.DataFrame(rows,columns=['series_id','origin','h','method','y','q10','q50','q90','stale'])
def pin(y,f,t): d=y-f; return np.maximum(t*d,(t-1)*d)
c['loss']=(pin(c.y,c.q10,.1)+pin(c.y,c.q50,.5)+pin(c.y,c.q90,.9))/3
c['date']=pd.to_datetime(c.origin.map(pd.Timestamp.fromordinal))
c.to_parquet(O+'dev_cells.parquet'); print(len(c), c.groupby('method').size().to_dict(), c.series_id.nunique())
