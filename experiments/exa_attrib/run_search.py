"""Searches for events and controls. BEFORE = D-21..D-1, AFTER = D..min(D+14, 2026-11-06). All cached via gpuf.scout.exa_call."""
import datetime as dt, json, sys
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from gpuf.scout import exa_call, exa_spend

ROOT = "/Users/aryank/Developer/iterate_hackathon/track_2"
END_CAP = dt.date(2026, 11, 6)
NAME = {"spheron": "Spheron", "sfcompute": "SF Compute", "fal": "fal", "nebius": "Nebius", "lambdalabs": "Lambda", "verda": "Verda (formerly DataCrunch)",
        "massedcompute": "Massed Compute", "jarvislabs": "Jarvislabs", "quantacloud": "QuantaCloud", "gmi": "GMI Cloud"}
DOM = {"spheron": ["spheron.network", "spheron.ai"], "sfcompute": ["sfcompute.com"], "fal": ["fal.ai"], "nebius": ["nebius.com"],
       "lambdalabs": ["lambda.ai", "lambdalabs.com"], "verda": ["verda.com", "datacrunch.io"], "massedcompute": ["massedcompute.com"],
       "jarvislabs": ["jarvislabs.ai"], "quantacloud": ["quantacloud.ai", "quantacloud.com"], "gmi": ["gmicloud.ai"]}

def win(D, which):
    if which == "BEFORE":
        a, b = D - dt.timedelta(21), D - dt.timedelta(1)
    else:
        a, b = D, min(D + dt.timedelta(14), END_CAP)
    assert b <= END_CAP
    return f"{a}T00:00:00Z", f"{b}T23:59:59Z"

def queries(prov, gpu):
    n = NAME[prov]
    return [("news", f"{n} {gpu} GPU price change announcement per hour", False),
            ("news2", f"{n} raises or cuts GPU prices", False),
            ("domain", f"{n} pricing update: new {gpu} GPU price per hour, blog post or changelog", True)]

def run_one(prov, gpu, D, which, kinds=None):
    out = []
    s, e = win(D, which)
    for kind, q, dom in queries(prov, gpu):
        if kinds and kind not in kinds: continue
        body = {"query": q, "type": "auto", "numResults": 10, "startPublishedDate": s, "endPublishedDate": e, "contents": {"highlights": True}}
        if dom: body["includeDomains"] = DOM[prov]
        r = exa_call("search", body)
        res = (r.get("response") or {}).get("results", [])
        out.append(dict(window=which, kind=kind, query=q, start=s, end=e, error=r.get("error"), cost=r.get("cost"),
                        hits=[dict(url=x["url"], title=x.get("title"), published=(x.get("publishedDate") or "")[:10], highlights=x.get("highlights") or []) for x in res]))
    return out

if __name__ == "__main__":
    which = sys.argv[1]
    if which == "events":
        sel = pd.read_csv(f"{ROOT}/runs/exa_attrib/selected.csv")
        jobs = [(r.provider, r.gpu, dt.date.fromisoformat(r.date), w, int(r.id)) for r in sel.itertuples() for w in ("BEFORE", "AFTER")]
    else:
        c = pd.read_csv(f"{ROOT}/runs/exa_attrib/controls.csv")
        jobs = [(r.provider, r.gpu, dt.date.fromisoformat(r.date), "BEFORE", i) for i, r in enumerate(c.itertuples())]
    def f(j):
        return dict(id=j[4], provider=j[0], gpu=j[1], date=str(j[2]), searches=run_one(*j[:4]))
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(f, jobs))
    json.dump(res, open(f"{ROOT}/runs/exa_attrib/search_{which}.json", "w"))
    errs = [(r["id"], s["error"][:120]) for r in res for s in r["searches"] if s["error"]]
    print(which, len(res), "jobs, errors:", errs[:5], "spend $", exa_spend())
