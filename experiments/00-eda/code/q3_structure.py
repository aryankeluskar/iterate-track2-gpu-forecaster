import sys; sys.path.insert(0,'/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/code')
from common import *
import warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width',250,'display.max_colwidth',70,'display.max_rows',200,'display.max_columns',30)
s,cat=load(); cat=cat.set_index('series_id')
s=s[(s.date<='2026-08-31')&s.series_id.isin(cat.index[cat.table=='daily_statistics'])]
s=s.merge(cat[['tier','instrument_class','model']].rename(columns={'instrument_class':'ic'}),left_on='series_id',right_index=True)
s['d']=s.date.map(pd.Timestamp.toordinal)
rows=[]; pairs=[]
for sid,g in s.groupby('series_id'):
    g=g.sort_values('d'); d=g.d.values; x=np.log(g.value.values)
    if len(d)<30: continue
    ic=g.ic.iloc[0]; tier=g.tier.iloc[0]; src=g.source_id.iloc[0]
    # consecutive day log changes
    dx=np.diff(x); ok=np.diff(d)==1
    r1=dx[ok]
    chg=(np.abs(r1)>1e-9)
    # run lengths between changes on consecutive spans
    # h-day changes
    idx={dd:i for i,dd in enumerate(d)}
    out={'series_id':sid,'ic':ic,'tier':tier,'src':src,'n':len(d),'n_dchg':len(r1),'frac_chg':chg.mean() if len(r1) else np.nan}
    for h in (1,3,7):
        ch=np.array([x[idx[dd+h]]-x[i] for i,dd in enumerate(d) if dd+h in idx])
        out[f'zero_h{h}']=(np.abs(ch)<1e-9).mean() if len(ch) else np.nan; out[f'n_h{h}']=len(ch)
    # change-run: days between changes
    pos=np.where(chg)[0]; out['med_gap']=np.median(np.diff(pos)) if len(pos)>2 else np.nan
    nz=np.abs(r1[chg]); out['absnz_med']=np.median(nz) if len(nz) else np.nan; out['absnz_p90']=np.quantile(nz,.9) if len(nz) else np.nan
    # acf1 of consecutive daily changes
    a,b=[],[]
    for i in range(1,len(d)-1):
        if d[i]-d[i-1]==1 and d[i+1]-d[i]==1: a.append(x[i]-x[i-1]); b.append(x[i+1]-x[i])
    a,b=np.array(a),np.array(b)
    out['acf1']=np.corrcoef(a,b)[0,1] if len(a)>20 and a.std()>0 and b.std()>0 else np.nan
    rows.append(out)
    # undo regression pairs: prior change (d-1->d) vs future change (d->d+h)
    for i,dd in enumerate(d):
        if dd-1 in idx:
            p=x[i]-x[idx[dd-1]]
            for h in (1,3,7):
                if dd+h in idx: pairs.append((sid,ic,src,h,p,x[idx[dd+h]]-x[i]))
st=pd.DataFrame(rows); st.to_csv(R+'step_structure_by_series_dev.csv',index=False)
print(st.groupby('ic').agg(n_ser=('series_id','size'),frac_chg_med=('frac_chg','median'),frac_chg_mean=('frac_chg','mean'),zero_h1=('zero_h1','median'),zero_h3=('zero_h3','median'),zero_h7=('zero_h7','median'),absnz_med=('absnz_med','median'),absnz_p90=('absnz_p90','median'),acf1_med=('acf1','median'),acf1_mean=('acf1','mean')).round(3))
print(st.groupby('src').agg(n_ser=('series_id','size'),frac_chg_med=('frac_chg','median'),zero_h7=('zero_h7','median'),acf1_med=('acf1','median')).round(3))
P=pd.DataFrame(pairs,columns=['sid','ic','src','h','prior','fut'])
P['pw']=P.prior.clip(P.prior.quantile(.005),P.prior.quantile(.995)); 
def beta(g):
    g=g[g.prior.abs()>1e-9]
    if len(g)<30: return pd.Series({'n':len(g),'beta':np.nan})
    # series-demeaned OLS through origin, winsorised 1/99 within group
    lo,hi=g.prior.quantile([.01,.99]); p=g.prior.clip(lo,hi); lo,hi=g.fut.quantile([.01,.99]); f=g.fut.clip(lo,hi)
    b=(p*f).sum()/(p*p).sum()
    # bootstrap by series
    return pd.Series({'n':len(g),'beta':b})
res=P.groupby(['ic','h']).apply(beta).unstack('h'); print('\nundo regression: future h-day change on prior 1-day nonzero change (beta<0 = reversal; -1 = fully undone)'); print(res.round(3))
res2=P.groupby(['src','h']).apply(beta).unstack('h'); print(res2.round(3))
P.to_parquet(O+'undo_pairs.parquet')
# big prior moves
