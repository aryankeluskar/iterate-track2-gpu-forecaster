import json, sys
from rule import strict2 as strict, V1 as CHANGE, PRICE
ROOT = "/Users/aryank/Developer/iterate_hackathon/track_2"
f, win, cap = sys.argv[1], sys.argv[2], int(sys.argv[3]); ids = [int(i) for i in sys.argv[4:]]
for r in json.load(open(f"{ROOT}/runs/exa_attrib/search_{f}.json")):
    if r["id"] not in ids: continue
    print(f"=== {r['id']} {r['provider']} {r['gpu']} D={r['date']} {win}")
    seen, n = set(), 0
    for s in r["searches"]:
        if s["window"] != win: continue
        for h in s["hits"]:
            if h["url"] in seen or not strict(h, r["provider"]): continue
            seen.add(h["url"]); n += 1
            if n > cap: continue
            ps = [t for t in h["highlights"] if PRICE.search(t) and CHANGE.search(t)] or [h["title"]]
            m = CHANGE.search(ps[0]) or PRICE.search(ps[0])
            i = max(0, (m.start() if m else 0) - 120)
            print(f"  {h['published']} {h['title'][:60]} | {h['url'][:90]}\n      {ps[0][i:i+260]!r}")
    print(f"  ({n} strict hits)")
