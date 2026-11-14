import json, re, sys, pandas as pd
ROOT = "/Users/aryank/Developer/iterate_hackathon/track_2"
P = re.compile(r"(pric|rate card|per hour|/hr|\$\s?\d)", re.I)
C = re.compile(r"(increas|rais|hike|cut|reduc|lower|new pric|effective|starting|updat|adjust|change|drop|discount|rise|surge)", re.I)
from run_search import NAME, DOM
def rule(h, prov):
    t = " ".join([h["title"] or "", h["url"]] + h["highlights"]).lower()
    named = any(w in t for w in [NAME[prov].split()[0].lower()] + [d.split(".")[0] for d in DOM[prov]])
    return named and bool(P.search(t)) and bool(C.search(t))
if __name__ == "__main__":
    f, ids = sys.argv[1], [int(i) for i in sys.argv[2:]]
    for r in json.load(open(f"{ROOT}/runs/exa_attrib/search_{f}.json")):
        if ids and r["id"] not in ids: continue
        print(f"=== {r['id']} {r['provider']} {r['gpu']} D={r['date']}")
        seen = set()
        for s in r["searches"]:
            for h in s["hits"]:
                if h["url"] in seen: continue
                seen.add(h["url"])
                if rule(h, r["provider"]) or "-v" in sys.argv:
                    print(f"  [{s['window'][0]}{s['kind'][:3]}] {h['published']} {h['title'][:80]} | {h['url'][:100]}")
