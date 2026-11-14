import sys; sys.path.insert(0,'/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/code')
from common import *
import duckdb, warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width',250,'display.max_rows',200,'display.max_columns',30)
a=pd.read_csv(O+'series_daily.csv',usecols=['series_id','date','value','n_obs','n_providers']); b=pd.read_csv(ROOT+'demo_out/series_daily.csv',usecols=['series_id','date','value','n_obs','n_providers'])
m=a.merge(b,on=['series_id','date'],how='outer',suffixes=('','_demo'),indicator=True); print('demo_out series_daily vs mine: merge',m._merge.value_counts().to_dict(),' value diffs',(m.value.sub(m.value_demo).abs()>1e-9).sum())
ds=pd.read_csv(ROOT+'data/pack/gpu-price-pack-v0.1.1-handover/daily_statistics.csv',usecols=['date','source_id'])
print('daily_statistics.csv date max by source'); print(ds.groupby('source_id').date.agg(['min','max','nunique']))
s,cat=load(); s=s[s.series_id.isin(cat[cat.table=='daily_statistics'].series_id)]
# last-day n_obs vs trailing 7-day median, by source
s=s.sort_values(['series_id','date']); 
res=[]
for sid,g in s.groupby('series_id'):
    g=g.set_index('date'); 
    for d in pd.date_range('2026-10-20','2026-11-06'):
        if d in g.index:
            prev=g.n_obs[(g.index<d)&(g.index>=d-pd.Timedelta(days=7))]
            if len(prev)>=3: res.append((g.source_id.iloc[0],d,g.n_obs[d]/prev.median(),g.n_providers[d]-g.n_providers[(g.index<d)&(g.index>=d-pd.Timedelta(days=7))].median()))
r=pd.DataFrame(res,columns=['src','d','ratio','dprov']); 
x=r.groupby(['src','d']).ratio.median().unstack('src').round(3); print('median n_obs ratio (day / prior-7d median) by source, last 18 days'); print(x.tail(18))
print('share series with n_obs on 11-06 < 0.8 x prior median'); print(r[r.d=='2026-11-06'].assign(low=lambda t:t.ratio<0.8).groupby('src').low.agg(['mean','size']).round(3))
# snapshots per day for afhubbard and snapshot timing
con=duckdb.connect()
q=con.execute(f"""select source_id, dt, count(distinct snapshot_ts_utc) n_snap, min(snapshot_ts_utc) first_ts, max(snapshot_ts_utc) last_ts, count(*) n from read_parquet('{ROOT}data/pack/gpu-price-pack-v0.1.1-handover/rental_observations/*/*/*.parquet', hive_partitioning=false) where dt between '2026-10-28' and '2026-11-06' and source_id in ('afhubbard','gpurentalprices','tanod') group by 1,2 order by 1,2""").df()
print(q.to_string())
dtmax=con.execute(f"select source_id,max(dt) from read_parquet('{ROOT}data/pack/gpu-price-pack-v0.1.1-handover/rental_observations/*/*/*.parquet', hive_partitioning=false) group by 1").df(); print(dtmax)
