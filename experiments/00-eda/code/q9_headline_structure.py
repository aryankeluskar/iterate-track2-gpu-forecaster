import sys; sys.path.insert(0,'/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/code')
from common import *
s,cat=load(); h=pd.read_csv(R+'headline_rental_series.csv')
s=s[s.series_id.isin(h.series_id)].sort_values(['series_id','date'])
s['pv']=s.groupby('series_id').value.shift(); s['dd']=s.groupby('series_id').date.diff().dt.days
e=s[s.dd==1]; e=e.assign(chg=(e.value!=e.pv))
g=e.groupby(['source_id','series_id']).chg.agg(['mean','size']).reset_index()
n=s.groupby('series_id').size().rename('n_days')
g=g.merge(n,on='series_id')
print(g.groupby('source_id').agg(series=('series_id','size'),n_days_med=('n_days','median'),n_days_min=('n_days','min'),n_days_max=('n_days','max'),frac_chg_mean=('mean','mean'),frac_chg_med=('mean','median'),frac_chg_min=('mean','min'),frac_chg_max=('mean','max')).round(3))
g.merge(h[['series_id','instrument_class']],on='series_id').groupby(['source_id','instrument_class']).agg(series=('series_id','size'),frac_chg_med=('mean','median')).round(3).pipe(print)
