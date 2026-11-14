import sys; sys.path.insert(0,'/Users/aryank/Developer/iterate_hackathon/track_2/experiments/00-eda/code')
from common import *
import warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width',250,'display.max_rows',200,'display.max_columns',30,'display.max_colwidth',60)
s,cat=load(); cat=cat.set_index('series_id')
s=s[(s.date<='2026-08-31')&s.series_id.isin(cat.index[cat.table=='daily_statistics'])]
W=s.pivot(index='date',columns='series_id',values='value'); W=W.reindex(pd.date_range(W.index.min(),W.index.max()))
L=np.log(W)
X=L.diff(1)                          # known at t: change t-1 -> t (needs both days present)
# keep series with >=15 nonzero daily changes
nzc=(X.abs()>1e-9).sum(); keep=nzc[nzc>=15].index; print('series kept',len(keep),'of',W.shape[1])
res=[]; rng=np.random.default_rng(0)
def corrmat(A,B):
    # pairwise-complete correlation between columns of A (predictors) and B (targets), rows aligned
    a=A.values; b=B.values; ma=~np.isnan(a); mb=~np.isnan(b)
    a0=np.where(ma,a,0); b0=np.where(mb,b,0); n=ma.astype(float).T@mb.astype(float)
    sa=a0.T@mb.astype(float); sb=ma.astype(float).T@b0; sab=a0.T@b0
    saa=(a0**2).T@mb.astype(float); sbb=ma.astype(float).T@(b0**2)
    cov=sab/np.maximum(n,1)-sa*sb/np.maximum(n,1)**2; va=saa/np.maximum(n,1)-(sa/np.maximum(n,1))**2; vb=sbb/np.maximum(n,1)-(sb/np.maximum(n,1))**2
    with np.errstate(all='ignore'): c=cov/np.sqrt(va*vb)
    c[n<40]=np.nan; return c,n
Xk=X[keep]
out={}
for h in (1,3,7):
    Y=(L.shift(-h)-L)[keep]            # change t -> t+h
    c,n=corrmat(Xk,Y); np.fill_diagonal(c,np.nan); out[h]=(c,n)
    # null: circularly shift target rows by random offset >=14 days, record max |corr|
    mx=[]
    for _ in range(200):
        k=rng.integers(14,len(Y)-14); Ys=pd.DataFrame(np.roll(Y.values,k,axis=0),index=Y.index,columns=Y.columns)
        cc,_=corrmat(Xk,Ys); np.fill_diagonal(cc,np.nan); mx.append(np.nanmax(np.abs(cc)))
    mx=np.array(mx); obs=np.abs(c); idx=np.dstack(np.unravel_index(np.argsort(-np.nan_to_num(obs).ravel())[:10],obs.shape))[0]
    print(f'\nh={h}: pairs {np.isfinite(c).sum()}, null max|corr| median {np.median(mx):.3f} p95 {np.quantile(mx,.95):.3f}; observed max {np.nanmax(obs):.3f}; #pairs above null p95: {(obs>np.quantile(mx,.95)).sum()}')
    for i,j in idx:
        res.append((h,keep[i].replace('afhubbard','afh').replace('gpurentalprices','gpr'),keep[j].replace('afhubbard','afh').replace('gpurentalprices','gpr'),c[i,j],int(n[i,j])))
r=pd.DataFrame(res,columns=['h','predictor_change_of','target_future_change_of','corr','n']); print(r.to_string(index=False)); r.to_csv(R+'leadlag_top_pairs_dev.csv',index=False)
# contemporaneous context: mean |corr| of same-day changes among kept
cc,_=corrmat(Xk,Xk); np.fill_diagonal(cc,np.nan); print('\nsame-day |corr| median',np.nanmedian(np.abs(cc)).round(3),'p95',np.nanquantile(np.abs(cc),.95).round(3))
# average lead-lag in aggregate: mean over pairs of corr(x_i(t), y_j(t->t+1)) vs null mean
c1=out[1][0]; print('mean corr h=1 over pairs',np.nanmean(c1).round(4),'median',np.nanmedian(c1).round(4))
