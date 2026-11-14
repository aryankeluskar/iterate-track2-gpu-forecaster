"""Part A search: per-provider and generic Exa searches for dated GPU price-change announcements.
Every request: endPublishedDate <= 2026-11-06, trackers excluded, highlights from the stored copy as of the cutoff.
Usage: PYTHONPATH=src:experiments/calendar .venv/bin/python experiments/calendar/search.py [probe|run]"""
import datetime as dt, json, re, sys, pathlib
from concurrent.futures import ThreadPoolExecutor
from gpuf.scout import exa_call, exa_spend
from providers import P, TRACKERS

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "calendar"
CUTOFF = dt.date(2026, 11, 6)
TAG = "cal"
WINDOWS = [("2026-08-01", "2026-08-31"), ("2026-09-01", "2026-09-30"), ("2026-10-01", "2026-11-06")]
TRACKER_TITLE = re.compile(r"(compar|cheapest|price tracker|prices? by provider|hourly rates by provider|price index|best gpu cloud|"
                           r"top \d+|\bvs\.?\b|alternatives|price list across|live price)", re.I)


def body(q, s, e, domains=None, n=10):
    assert dt.date.fromisoformat(e) <= CUTOFF
    b = {"query": q, "type": "auto", "numResults": n, "startPublishedDate": f"{s}T00:00:00Z", "endPublishedDate": f"{e}T23:59:59Z",
         "contents": {"highlights": True}}
    if domains:
        b["includeDomains"] = domains
    else:
        b["excludeDomains"] = TRACKERS
    return b


def jobs():
    out = []
    for slug, (name, dom) in P.items():
        for s, e in WINDOWS:
            out.append((slug, "news", s, e, body(f"{name} announces GPU price change effective date, new hourly prices for H100 H200 B200 GPUs", s, e)))
            out.append((slug, "own", s, e, body(f"{name} GPU pricing update: new rates take effect on a date, price increase or decrease notice", s, e, dom)))
    # generic press, weekly windows so recent items are not crowded out
    d = dt.date(2026, 8, 1)
    while d <= CUTOFF:
        e = min(d + dt.timedelta(6), CUTOFF)
        for k, q in enumerate(["GPU cloud provider will raise prices for H100 B200 B300 GPUs starting next month, customer notice",
                               "neocloud cuts on-demand GPU prices effective date announced",
                               "AI cloud company price hike for Nvidia GPU rental from October November"]):
            out.append(("_generic", f"gen{k}", str(d), str(e), body(q, str(d), str(e))))
        d = e + dt.timedelta(1)
    return out


def run_job(j):
    slug, kind, s, e, b = j
    r = exa_call("search", b, tag=TAG)
    res = (r.get("response") or {}).get("results", [])
    hits = []
    for x in res:
        pub = (x.get("publishedDate") or "")[:10]
        drop = None
        if not pub:
            drop = "no_date"
        elif pub > e or pub < s:
            drop = "outside_window"
        elif any(t in x["url"] for t in TRACKERS) or TRACKER_TITLE.search(x.get("title") or ""):
            drop = "tracker"
        hits.append(dict(url=x["url"], title=x.get("title"), published=pub, drop=drop,
                         highlights=[] if drop == "tracker" else (x.get("highlights") or [])))
    return dict(provider=slug, kind=kind, start=s, end=e, query=b["query"], error=r.get("error"), cost=r.get("cost"), hits=hits)


if __name__ == "__main__":
    J = jobs()
    if sys.argv[1] == "probe":
        J = [j for j in J if j[0] in ("nebius", "jarvislabs")]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(run_job, J))
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT / f"search_{sys.argv[1]}.json", "w"))
    errs = [(r["provider"], r["kind"], (r["error"] or "")[:150]) for r in res if r["error"]]
    print(len(res), "searches; errors:", len(errs), errs[:3], "| spend $", exa_spend(TAG))
