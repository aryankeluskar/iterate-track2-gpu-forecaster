import sys; sys.path.insert(0,'/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/code')
from common import *
import warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width',250,'display.max_rows',200)
c=pd.read_parquet(O+'dev_cells.parquet'); w=pd.read_parquet(O+'dev_wide.parquet')
last=c[c.method=='last_value'][['series_id','origin','h','q50']].rename(columns={'q50':'last'})
w=w.merge(last,on=['series_id','origin','h'])
pin=lambda y,f,t: np.maximum(t*(y-f),(t-1)*(y-f))
w['lve']=(pin(w.y,w.q10,.1)+pin(w.y,w['last'],.5)+pin(w.y,w.q90,.9))/3
# interval-only variants: drift interval with q50=last (lve); and 'narrow': shrink log-width by 0.5
for f in (0.5,):
    lo=w['last']*np.exp(f*np.log(w.q10/w['last'])); hi=w['last']*np.exp(f*np.log(w.q90/w['last']))
    w['narrow']=(pin(w.y,lo,.1)+pin(w.y,w['last'],.5)+pin(w.y,hi,.9))/3
def sk(g,col): return 1-g[col].sum()/g.lv.sum()
t=w.groupby('instrument_class').apply(lambda g: pd.Series({'n':len(g),'drift':sk(g,'dr'),'last_val_empirical':sk(g,'lve'),'lve_half_width':sk(g,'narrow')})).round(3)
print('ALL dev'); print(t); print('pooled',[round(sk(w,k),3) for k in ('dr','lve','narrow')])
h=w[w.tier=='headline']; print('headline17 pooled',[round(sk(h,k),3) for k in ('dr','lve','narrow')])
nf=w[w.q10!=w.q90]; print('non-flat cells pooled',[round(sk(nf,k),3) for k in ('dr','lve','narrow')],len(nf))
print(nf.groupby('instrument_class').apply(lambda g: pd.Series({'n':len(g),'drift':sk(g,'dr'),'lve':sk(g,'lve'),'narrow':sk(g,'narrow')})).round(3))
