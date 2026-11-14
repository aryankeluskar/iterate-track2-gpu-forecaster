import sys, numpy as np, pandas as pd
sys.dont_write_bytecode=True
ROOT='/Users/aryank/Developer/iterate_hackathon/track_2/'
O=ROOT+'runs/eda/'; R=ROOT+'experiments/00-eda/results/'
STARTER=ROOT+'data/pack/gpu-price-pack-v0.1.1-handover/starter'
sys.path.insert(0,STARTER)
import _common as C
from baselines import forecast_one
CUT=pd.Timestamp('2026-11-06')
def load():
    s=pd.read_csv(O+'series_daily.csv',usecols=['series_id','date','value','n_obs','n_providers','is_filled','source_id','instrument_class'])
    s['date']=pd.to_datetime(s['date']); assert s.date.max()<=CUT
    cat=pd.read_csv(R+'catalog_profile_2026-11-06.csv')
    return s,cat
def day(d): return pd.Timestamp(d).toordinal()
def store_of(s):
    df=pd.DataFrame({'series_id':s.series_id,'date':s.date.dt.strftime('%Y-%m-%d'),'value':s.value,'is_filled':s.is_filled})
    return C.SeriesStore(C.read_series_csv(O+'series_daily.csv'))
