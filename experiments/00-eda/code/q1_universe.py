import pandas as pd, numpy as np, re, sys
O='/Users/aryank/Developer/iterate_hackathon/track_2/runs/eda/'
R='/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/results/'
cat=pd.read_csv(O+'catalog_2026-11-06.csv',dtype=str,keep_default_na=False)
for c in ['n_days','n_distinct_values_90d']: cat[c]=pd.to_numeric(cat[c])
cat['median_n_providers']=pd.to_numeric(cat['median_n_providers'],errors='coerce')
cat['last_value']=pd.to_numeric(cat['last_value_to_as_of'],errors='coerce')
def fam(m):
    m=str(m)
    for k in ['H100','A100','H200','B200']:
        if m.startswith(k): return k
    return 'other'
def gm(r):
    if r['table']=='daily_statistics': return r['gpu_model']
    it=r['instance_type']
    return {'p4d.24xlarge':'A100 (p4d)','p4de.24xlarge':'A100 (p4de)','p5.48xlarge':'H100 (p5)','p5e.48xlarge':'H200 (p5e)','p5en.48xlarge':'H200 (p5en)','p6-b200.48xlarge':'B200','p6-b300.48xlarge':'B300'}.get(it,it)
cat['model']=cat.apply(gm,axis=1); cat['family']=cat['model'].map(fam)
cat['stale_days']=(pd.Timestamp('2026-11-06')-pd.to_datetime(cat['last_date_to_as_of'])).dt.days
cat['has_0611']=cat['stale_days']==0
print(len(cat)); print(cat.groupby(['table','tier']).size().unstack(fill_value=0))
ds=cat[cat.table=='daily_statistics']
print('\nDS by tier'); print(ds.tier.value_counts())
print('\nDS by source x tier'); print(pd.crosstab(ds.source_id,ds.tier,margins=True))
print('\nDS by class x tier'); print(pd.crosstab(ds.instrument_class,ds.tier,margins=True))
print('\nDS by family x tier'); print(pd.crosstab(ds.family,ds.tier,margins=True))
print('\nDS value on 11-06 by tier'); print(pd.crosstab(ds.tier,ds.has_0611))
print('\nstale days (non-0) distribution'); print(ds[~ds.has_0611].groupby('tier').stale_days.describe())
print(ds[~ds.has_0611].groupby('source_id').stale_days.agg(['count','median','max']))
print('\nstale buckets'); print(pd.cut(ds.stale_days,[-1,0,1,3,7,30,90,400]).value_counts().sort_index())
print('\ntier_reason (DS extended)'); 
rs=ds[ds.tier=='extended'].tier_reason.str.split(';').explode().value_counts(); print(rs)
a=cat[cat.table!='daily_statistics']; print('\nAWS tier'); print(a.tier.value_counts()); print(a.last_date_to_as_of.value_counts().head(5)); print(a.tier_reason.value_counts().head(8))
h=cat[cat.tier=='headline']; print('\nheadline total',len(h), h.table.value_counts().to_dict())
cols=['series_id','source_id','instrument_class','model','last_value','last_date_to_as_of','n_days','median_n_providers','n_distinct_values_90d','stale_days']
hh=ds[ds.tier=='headline'][cols].sort_values('series_id')
pd.set_option('display.width',250,'display.max_colwidth',90,'display.max_rows',500)
print(hh.to_string(index=False))
hh.to_csv(R+'headline_rental_series.csv',index=False)
cat[['series_id','tier','tier_reason','table','source_id','instrument_class','model','family','first_date','last_date_to_as_of','stale_days','n_days','median_n_providers','n_distinct_values_90d','last_value']].to_csv(R+'catalog_profile_2026-11-06.csv',index=False)
# DS only: family by source, class
print('\nDS by source x class'); print(pd.crosstab(ds.source_id,ds.instrument_class))
print('\nDS by source: first_date min / last_date max'); print(ds.groupby('source_id').agg(first=('first_date','min'),last=('last_date','max')))
print(ds.groupby('source_id').stale_days.apply(lambda s:(s==0).sum()))
