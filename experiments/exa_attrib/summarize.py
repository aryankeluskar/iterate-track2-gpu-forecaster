import json
import rule
ROOT = "/Users/aryank/Developer/iterate_hackathon/track_2"
for f in ("events", "controls"):
    rs = [r for r in json.load(open(f"{ROOT}/runs/exa_attrib/search_{f}.json")) if f == "controls" or True]
    ids = sorted({r["id"] for r in rs})
    for name, fn in (("v0", rule.strict0), ("v1", rule.strict), ("v2", rule.strict2)):
        fired = {r["id"] for r in rs if any(fn(h, r["provider"]) for s in r["searches"] if s["window"] == "BEFORE" for h in s["hits"])}
        print(f, name, "BEFORE fires on", len(fired), "of", len(ids), sorted(fired))
