import sys; sys.path.insert(0,'/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/code')
from common import *
import warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width',250,'display.max_rows',200)
s,cat=load(); s=s[s.series_id.isin(cat[cat.table=='daily_statistics'].series_id)].sort_values(['series_id','date'])
# STRUCTURAL ONLY (counts of providers/obs, not price predictability): dates where many series in a collector change n_providers
s['dp']=s.groupby('series_id').n_providers.diff(); s['dd']=s.groupby('series_id').date.diff().dt.days
x=s[(s.dd==1)]
t=x.groupby(['source_id','date']).agg(share_dprov=('dp',lambda v:(v!=0).mean()),n=('dp','size'),net=('dp','mean')).reset_index()
print(t[(t.share_dprov>0.3)&(t.n>=10)].sort_values(['source_id','date']).to_string(index=False))
# afhubbard 2026-05-25: which classes changed
a=s[(s.source_id=='afhubbard')].copy(); a['pv']=a.groupby('series_id').value.shift(); a['chg']=(a.value!=a.pv)&(a.dd==1)
for d in ['2026-05-25','2026-01-15','2026-08-05','2026-07-23']:
    z=a[a.date==d]; print(d,'n',len(z),'changed share by class:',z.groupby('instrument_class').chg.mean().round(2).to_dict())
# afhubbard hyperscaler_spot freeze 7-16 Jul check
f=a[(a.instrument_class=='hyperscaler_spot')&(a.date>='2026-07-05')&(a.date<='2026-07-20')].groupby('date').chg.mean().round(2); print('afhubbard hyperscaler_spot daily share changing, 5-20 Jul:',f.to_dict())
