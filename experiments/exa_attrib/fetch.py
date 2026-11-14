import json, sys
from gpuf.scout import exa_call, exa_spend
URLS = {26: ["https://www.thefivenines.com/data-ai/nebius-raises-gpu-prices-20-as-supply-tightens",
             "https://www.reuters.com/technology/nebius-hikes-ai-cloud-prices-again-demand-computing-power-so",
             "https://marketcatalyst.ai/posts/nebius-to-raise-gpu-cloud-pricing-across-h100-h200-b200-and-b30"],
        29: ["https://jarvislabs.ai/updates/gpu-pricing-october-2026"],
        27: ["https://www.usagepricing.com/blueprint/activity/fal-ai-2026-10-04-gpu-fleet-repricing", "https://www.withorb.com/pricing-atlas/fal"],
        28: ["https://www.memetik.ai/guides/lambda-gpu-cloud-pricing"],
        32: ["https://www.gmicloud.ai/en/blog/like-for-like-quotes-managed-b200-b300-nvl72"],
        33: ["https://quantacloud.net/gpus/h100"],
        22: ["https://autoresearch.sfcompute.com/changelog/sandbox-price-increase-notice"]}
# resolve truncated urls from the search results
allurls = {}
for r in json.load(open("../../runs/exa_attrib/search_events.json")):
    for s in r["searches"]:
        for h in s["hits"]: allurls[h["url"]] = h
out = {}
for i, us in URLS.items():
    full = [next((u for u in allurls if u.startswith(x)), x) for x in us]
    r = exa_call("contents", {"urls": full, "text": {"maxCharacters": 6000}})
    out[i] = [{"url": x["url"], "title": x.get("title"), "published": (x.get("publishedDate") or "")[:10], "text": x.get("text", "")} for x in (r.get("response") or {}).get("results", [])]
    print(i, len(out[i]), r.get("error"))
json.dump(out, open("../../runs/exa_attrib/contents.json", "w"))
print("spend", exa_spend())
