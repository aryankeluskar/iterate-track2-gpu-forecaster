import sys; sys.path.insert(0,'/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/code')
from common import *
import warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width',250,'display.max_rows',200,'display.max_columns',30)
s,cat=load(); cat=cat.set_index('series_id')
s=s[(s.date<='2026-08-31')&s.series_id.isin(cat.index[cat.table=='daily_statistics'])].sort_values(['series_id','date'])
g=s.groupby('series_id')
for c in ['value','n_providers','n_obs','date']: s['p_'+c]=g[c].shift()
s=s[(s.date-s.p_date).dt.days==1].copy()
s['lc']=np.log(s.value/s.p_value); s['dprov']=s.n_providers!=s.p_n_providers; s['dobs']=(np.abs(np.log(s.n_obs/s.p_n_obs))>0.2)
s['mix']=s.dprov|s.dobs
# future values
vv=s.set_index(['series_id','date']).value
for h in (1,3,7): s[f'f{h}']=[vv.get((a,b+pd.Timedelta(days=h)),np.nan) for a,b in zip(s.series_id,s.date)]
s['chg']=np.abs(s.lc)>1e-9
print('rows',len(s),' share days with n_providers change',s.dprov.mean().round(3),' with n_obs jump>20%',s.dobs.mean().round(3))
print(s.groupby('source_id').agg(dprov=('dprov','mean'),dobs=('dobs','mean')).round(3))
print('\nP(value change | mix change) by class'); 
print(s.groupby(['instrument_class','mix']).chg.agg(['mean','size']).unstack().round(3))
print('P(value change | n_providers change)'); print(s.groupby(['instrument_class','dprov']).chg.mean().unstack().round(3))
# jumps
for thr in (0.03,0.10):
    J=s[np.abs(s.lc)>thr].copy()
    print(f'\nJumps |dlog|>{thr}: n={len(J)}; share with mix change {J.mix.mean():.3f} (vs base {s.mix.mean():.3f}), with n_providers change {J.dprov.mean():.3f} (base {s.dprov.mean():.3f})')
    for h in (1,3,7):
        J[f'rev{h}']=-(np.log(J[f'f{h}']/J.value))/J.lc   # fraction of jump undone by day d+h
    print(J.groupby('mix')[['rev1','rev3','rev7']].agg(['median','mean','count']).round(3))
    print(J.groupby(['instrument_class','mix'])[['rev1','rev7']].agg(['median','count']).round(3))
    print('share of jumps >50% undone within 7d: mix vs not'); print(J.assign(u7=J.rev7>0.5).groupby('mix').u7.mean().round(3))
J=s[np.abs(s.lc)>0.03]
J.to_csv(R+'dev_jumps_with_mix_flags.csv',index=False,columns=['series_id','date','p_value','value','lc','p_n_providers','n_providers','p_n_obs','n_obs','mix','f1','f3','f7'])
