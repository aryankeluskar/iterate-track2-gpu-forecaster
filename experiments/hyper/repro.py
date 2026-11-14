"""Step 1: the panel reproduces the stored afhubbard series of rental_all (dev rows, day <= 2026-10-13)."""
import resource, time, datetime as dt, numpy as np, pandas as pd
from gpuf import data, panel_hyper as H
t=time.time(); H.load(); H._index()
print(f"load {time.time()-t:.0f}s  maxrss {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1e9:.2f} GB")
CUT = dt.date(2026,10,13).toordinal()
store = data.load_store(data.series_path())
ids = [s for s in data.universe("rental_all") if s.startswith("afhubbard.")]
out=[]
for s in ids:
    d, v = store.history(s, CUT)
    if not H.supported(s): out.append((s, s.split('.')[1], len(d), 0, 0, 0)); continue
    o = H.offers(s, CUT)
    med = o.groupby("day")["price"].apply(lambda x: np.median(x.to_numpy(np.float64)))
    m = pd.Series(v, index=d)
    j = m.index.intersection(med.index)
    out.append((s, s.split('.')[1], len(d), len(j), int((np.abs(m[j]-np.floor(med[j]*1e4+0.5+1e-9)/1e4)<1e-9).sum()), int((np.abs(m[j]-med[j])<=5.01e-5).sum())))
r = pd.DataFrame(out, columns=["sid","cls","n_store","n_panel_days","n_match","n_within5e5"])
g = r.groupby("cls")[["n_store","n_panel_days","n_match","n_within5e5"]].sum().assign(n_series=r.groupby("cls").size())
g["match_rate"] = g.n_match/g.n_store
print(g.to_string()); print("unsupported:", r[r.n_panel_days==0].sid.tolist()[:10])
miss = r[r.n_match<r.n_store]; print(miss.head(15).to_string())
print(f"maxrss {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1e9:.2f} GB")
