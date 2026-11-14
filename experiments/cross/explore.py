import sys, numpy as np, pandas as pd, json
sys.path.insert(0,'src')
from gpuf import data
from gpuf.data import starter_common as sc
st=data.load_store(); cat=data.load_catalog()
cat=cat[cat.table=='daily_statistics'].set_index('series_id')
D0=sc.day_of(sc.parse_date('2026-08-01')); DEV0=sc.day_of(sc.parse_date('2026-08-18')); DEV1=sc.day_of(sc.parse_date('2026-10-06')); CAP=sc.day_of(sc.parse_date('2026-10-13'))
days=np.arange(D0,CAP+1)
def grid(sid):
    d,v=st.history(sid,CAP); g=np.full(len(days),np.nan)
    m=(d>=D0)&(d<=CAP); g[d[m]-D0]=v[m]
    return pd.Series(g).ffill().to_numpy()
ids=list(cat.index)
G={s:grid(s) for s in ids}
L={s:np.log(g) for s,g in G.items() if np.isfinite(g).sum()>30}
hl=[s for s in L if cat.loc[s,'tier']=='headline']
print(len(L),len(hl))
def chg(s): return np.r_[np.nan,np.diff(L[s])]
C={s:chg(s) for s in L}
rows=[]
H=(1,3,7)
origins=range(DEV0,DEV1+1)
# ---- pair table
def gm_norm(g): return g.replace(' ','_')
pairs=[]
fg={ (cat.loc[s,'instrument_class'],cat.loc[s,'gpu_model']):s for s in L if cat.loc[s,'source_id']=='fastgpu_daily'}
gp={ (cat.loc[s,'instrument_class'],cat.loc[s,'gpu_model']):s for s in L if cat.loc[s,'source_id']=='gpurentalprices'}
alias={'A100 80GB':'A100 SXM 80GB'}
for (ic,gm),s in fg.items():
    gm2=alias.get(gm,gm)
    if (ic,gm2) in gp: pairs.append((s,gp[(ic,gm2)],'fg-gp'))
# fastgpu rate card vs spot same gpu
for (ic,gm),s in fg.items():
    if ic=='neocloud_rate_card' and ('neocloud_spot',gm) in fg: pairs.append((s,fg[('neocloud_spot',gm)],'fg-rc-spot'))
for (ic,gm),s in gp.items():
    if ic=='neocloud_rate_card' and ('neocloud_spot',gm) in gp: pairs.append((s,gp[('neocloud_spot',gm)],'gp-rc-spot'))
pt=pd.DataFrame(pairs,columns=['A','B','kind']); pt.to_csv('experiments/cross/pairs.csv',index=False); print(pt.to_string())
def target(s,t,h): return L[s][t+h-D0]-L[s][t-D0]
def expmean(x,i,minn=7):
    w=x[:i+1]; w=w[np.isfinite(w)]
    return w.mean() if len(w)>=minn else np.nan
def block_ci(df,xcol,ycol,reps=1000,seed=0):
    rng=np.random.default_rng(seed); wk=df.week.values; u=np.unique(wk); out=[]
    gb={w:df[df.week==w] for w in u}
    for _ in range(reps):
        d=pd.concat([gb[w] for w in rng.choice(u,len(u))]); x=d[xcol].values;y=d[ycol].values
        out.append((x*y).sum()/(x*x).sum())
    return np.percentile(out,[5,95])
def slope(df,xcol,ycol): x=df[xcol].values;y=df[ycol].values; return (x*y).sum()/(x*x).sum()
def placebo(df,xcol,ycol,reps=500,seed=1):
    # shuffle feature across origin dates (keep within-series cross-section aligned per date)
    rng=np.random.default_rng(seed); dts=df.t.unique(); res=[]
    byd={t:df[df.t==t] for t in dts}
    for _ in range(reps):
        perm=rng.permutation(dts); x=[];y=[]
        for t,p in zip(dts,perm):
            a=byd[t]; b=byd[p]
            # map by series (feature from date p for same series if present)
            m=a.merge(b[['sid',xcol]],on='sid',suffixes=('','_p'))
            x.append(m[xcol+'_p'].values); y.append(m[ycol].values)
        x=np.concatenate(x);y=np.concatenate(y); res.append((x*y).sum()/(x*x).sum())
    return np.percentile(res,[2.5,97.5])
def report(name,df,x='x',y='y'):
    for h in H:
        d=df[df.h==h].dropna(subset=[x,y])
        if len(d)<30: print(name,h,'n<30'); continue
        b=slope(d,x,y); lo,hi=block_ci(d,x,y); pl=placebo(d,x,y,200)
        print(f'{name} h={h} n={len(d)} slope={b:.3f} CI90=[{lo:.3f},{hi:.3f}] placebo95=[{pl[0]:.3f},{pl[1]:.3f}] corr={np.corrcoef(d[x],d[y])[0,1]:.3f}')
# ---- H-a
ra=[]
for _,r in pt.iterrows():
    A,B=r.A,r.B; lr=L[A]-L[B]
    for t in origins:
        i=t-D0; g=lr[i]-expmean(lr,i)
        for h in H:
            ra.append(dict(sid=A,t=t,h=h,x=g,y=target(A,t,h),week=t//7,kind=r.kind,pair=1))
            ra.append(dict(sid=B,t=t,h=h,x=-g,y=target(B,t,h),week=t//7,kind=r.kind,pair=1))
ra=pd.DataFrame(ra)
print('--- H-a (x = own-minus-partner gap; expect negative slope)')
report('all',ra)
for k in ra.kind.unique(): report(k,ra[ra.kind==k])
ra.to_pickle('runs/cross/ha.pkl')
# ---- H-b / H-c: collector factor
col={}
for s in L: col.setdefault(cat.loc[s,'source_id'],[]).append(s)
rb=[];rc=[]
for src in ['fastgpu_daily','gpurentalprices','afhubbard']:
    ss=[s for s in col[src]]
    M=np.vstack([C[s] for s in ss]); 
    for t in origins:
        i=t-D0
        for s in ss:
            if s not in hl: continue
            others=[j for j,u in enumerate(ss) if u!=s]
            act=M[others,i]; ok=np.isfinite(act)
            if ok.sum()<5: continue
            fchg=(np.abs(act[ok])>1e-9).mean()
            f1=np.nanmean(M[others,i]); f3=np.nanmean(M[others][:,i-2:i+1]); f7=np.nanmean(M[others][:,i-6:i+1])
            own_prev=np.abs(C[s][i-6:i+1]); ownfrac=np.nanmean(own_prev>1e-9)
            for h in H:
                y=target(s,t,h); fut=np.abs(L[s][t+1-D0:t+h-D0+1]-L[s][t-D0:t+h-D0]); 
                rb.append(dict(sid=s,t=t,h=h,src=src,fchg=fchg,ownfrac=ownfrac,absy=abs(y),anychg=float((fut>1e-9).any()),y=y,f1=f1,f3=f3,f7=f7,week=t//7))
rb=pd.DataFrame(rb); rb.to_pickle('runs/cross/hbc.pkl')
print('--- H-b: regress anychg and |y| on collector-wide change share (demeaned within series+h)')
for src in rb.src.unique():
  for h in H:
    d=rb[(rb.src==src)&(rb.h==h)].copy()
    for c in ['fchg','anychg','absy','ownfrac']: d[c+'_d']=d[c]-d.groupby('sid')[c].transform('mean')
    for yv in ['anychg_d','absy_d']:
        for ctrl in [False,True]:
            dd=d.copy()
            if ctrl: # partial out own recent change frac
                bb=slope(dd,'ownfrac_d','fchg_d'); dd['fchg_d']=dd['fchg_d']-bb*dd['ownfrac_d']; 
                bo=slope(dd,'ownfrac_d',yv); dd[yv]=dd[yv]-bo*dd['ownfrac_d']
            dd=dd.rename(columns={'fchg_d':'x'}); 
            b=slope(dd,'x',yv); lo,hi=block_ci(dd,'x',yv,500); 
            print(f'{src} h={h} {yv} ctrl_own={ctrl} n={len(dd)} slope={b:.4f} CI90=[{lo:.4f},{hi:.4f}] corr={np.corrcoef(dd.x,dd[yv])[0,1]:.3f}')
print('--- H-c')
for src in rb.src.unique():
    for f in ['f1','f3','f7']:
        report(f'{src}:{f}',rb[rb.src==src].assign(x=rb[f]) if False else rb[rb.src==src].rename(columns={f:'x'}).drop(columns=[c for c in ['f1','f3','f7'] if c!=f and c in rb.columns]))
# ---- H-d
rd=[]
for a,b,nm in [('B300','B200','B300-B200'),('H200','H100_SXM_80GB','H200-H100')]:
    for src,ic in [('fastgpu_daily','neocloud_rate_card'),('gpurentalprices','neocloud_rate_card'),('fastgpu_daily','neocloud_spot')]:
        sa=[s for s in L if cat.loc[s,'source_id']==src and cat.loc[s,'instrument_class']==ic and cat.loc[s,'gpu_model'].replace(' ','_')==a]
        sb=[s for s in L if cat.loc[s,'source_id']==src and cat.loc[s,'instrument_class']==ic and cat.loc[s,'gpu_model'].replace(' ','_')==b]
        if not sa or not sb: continue
        A,B=sa[0],sb[0]; sp=L[A]-L[B]
        for t in origins:
            i=t-D0; g=sp[i]-expmean(sp,i)
            for h in H:
                rd.append(dict(sid=A,t=t,h=h,x=g,y=target(A,t,h),week=t//7,nm=nm+'/'+src+'/'+ic[:6]))
                rd.append(dict(sid=B,t=t,h=h,x=-g,y=target(B,t,h),week=t//7,nm=nm+'/'+src+'/'+ic[:6]))
rd=pd.DataFrame(rd); print('--- H-d (x=spread dev for A, minus for B; expect negative)')
report('all',rd)
for n in rd.nm.unique(): report(n,rd[rd.nm==n])
rd.to_pickle('runs/cross/hd.pkl')
