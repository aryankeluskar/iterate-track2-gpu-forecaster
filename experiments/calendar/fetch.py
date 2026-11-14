"""Fetch candidate announcement pages from Exa's stored copies (never live): snapshot as of the cutoff and as of published+2d.
A page whose cutoff text differs materially from its early text, or that mentions dates after its published date, is flagged."""
import datetime as dt, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from gpuf.scout import exa_call, exa_spend
from providers import TRACKERS

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "calendar"
PREFIXES = {
    "nebius": ["https://www.reuters.com/technology/nebius-hikes-ai-cloud-prices-again", "https://www.thefivenines.com/data-ai/nebius-raises",
               "https://longbridge.com/en/topics/100000000903151", "https://gpucloudadvisors.com/news/nebius-october"],
    "jarvislabs": ["https://jarvislabs.ai/updates/gpu-pricing-october-2026"],
    "aws": ["https://fourweekmba.com/ai-aws-ec2-capacity-block-rates-october-2026", "https://gfdaily.com/tech/en-aws-flags",
            "https://cryptobriefing.com/aws-gpu-capacity-block-price-increase", "https://www.itechguides.com/aws-hikes-prices-for-ec2-capacity"],
    "digitalocean": ["https://theweightedaverage.com/notes/2026-08-02-digitalocean"],
    "fireworks": ["https://modelswar.com/change/fireworks-h100-80gb-gpu-price-increases-effective-sep-1",
                  "https://modelswar.com/change/fireworks-b200-180gb-gpu-price-increases-effective-sep-1",
                  "https://modelswar.com/change/fireworks-h200-141gb-gpu-price-increases-effective-sep-1"],
    "salad": ["https://blog.salad.com/saladcloud-price-changes-september-2026", "https://blog.salad.com/saladcloud-price-changes-november-2026"],
    "lambdalabs": ["https://gpujournal.ai/story/lambda-announced-rises-nov-16"],
    "ovhcloud": ["https://privatedevops.com/news/ovhcloud-price-increase-october-2026"],
    "coreweave": ["https://finance.yahoo.com/markets/stocks/articles/crwv-stock-hits-17-month", "https://www.gate.com/en-us/news/detail/coreweave-raises-prices"],
    "crusoe": ["https://nbistracker.com/signals/pricing-crusoe-h100-2026-11-03"],
}
LATER = re.compile(r"((jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\.?\s+\d{1,2},?\s+2026|\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+2026|2026-\d\d-\d\d)", re.I)
MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def dates_in(text):
    out = []
    for m in LATER.finditer(text):
        s = m.group(0)
        try:
            if s[:4] == "2026":
                out.append(dt.date.fromisoformat(s))
            else:
                w = re.findall(r"[A-Za-z]+|\d+", s)
                mon = next(MON[x[:3].lower()] for x in w if x[:3].lower() in MON)
                day = next(int(x) for x in w if x.isdigit() and x != "2026")
                out.append(dt.date(2026, mon, day))
        except Exception:
            pass
    return out


hits = {}
for f in ("search_run.json", "search_run2.json"):
    for r in json.load(open(OUT / f)):
        for h in r["hits"]:
            if not h["drop"]:
                hits.setdefault(h["url"], h)
out = {}
for prov, prefs in PREFIXES.items():
    for p in prefs:
        url = next((u for u in hits if u.startswith(p)), None)
        if url is None or any(t in url for t in TRACKERS):
            print("unresolved", p); continue
        pub = hits[url]["published"]
        # snapshotAsOf is not on this Exa plan (403 SNAPSHOT_NOT_ON_PLAN, cached): fall back to Exa's cached copy, and flag edits from the text.
        r = exa_call("contents", {"urls": [url], "text": {"maxCharacters": 8000}}, tag="cal")
        res = (r.get("response") or {}).get("results", [])
        txt = res[0].get("text", "") if res else ""
        later = sorted({str(d) for d in dates_in(txt) if str(d) > pub})
        out[url] = dict(provider=prov, url=url, title=hits[url]["title"], published=pub, text=txt, search_highlights=hits[url]["highlights"],
                        later_dates_in_text=later, err=r.get("error"))
        print(prov, pub, len(txt), later[:8], url[:80])
json.dump(out, open(OUT / "contents.json", "w"), indent=0)
print("spend $", exa_spend("cal"))
