"""Triage search hits: keep dated, non-tracker hits whose title/highlights state a price change; flag effective-date language."""
import json, re, pathlib, collections
ROOT = pathlib.Path(__file__).resolve().parents[2]
CHG = re.compile(r"(rais\w*|increas\w*|hik\w*|cut\w*|lower\w*|reduc\w*|drop\w*|new (gpu )?(rates|prices|pricing)|price (change|update|adjust)\w*|repric\w*)", re.I)
PRICE = re.compile(r"(price|pricing|rate|\$\s?\d|/hr|per hour|gpu-hour)", re.I)
EFF = re.compile(r"(effective|starting|from|beginning|as of|on|takes? effect)\s+(on\s+)?(the\s+)?((jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\.?\s+\d{1,2}|\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*|20\d\d-\d\d-\d\d)", re.I)
GPU = re.compile(r"(gpu|h100|h200|b200|b300|a100|l40s|rtx|mi300|mi325|mi355|a10|l4\b|t4\b)", re.I)

res = json.load(open(ROOT / "runs/calendar/search_run.json"))
seen = {}
drops = collections.Counter()
for r in res:
    for h in r["hits"]:
        if h["drop"]:
            drops[h["drop"]] += 1
            continue
        text = (h["title"] or "") + " " + " ".join(h["highlights"])
        if not (CHG.search(text) and PRICE.search(text) and GPU.search(text)):
            continue
        k = h["url"]
        e = seen.setdefault(k, dict(url=k, title=h["title"], published=h["published"], providers=set(), eff=bool(EFF.search(text)),
                                    hl=" | ".join(h["highlights"])[:700]))
        e["providers"].add(r["provider"])
cand = sorted(seen.values(), key=lambda e: e["published"])
for e in cand:
    e["providers"] = sorted(e["providers"])
json.dump(cand, open(ROOT / "runs/calendar/candidates.json", "w"), indent=0)
print("drops", dict(drops), "candidates", len(cand), "with eff-date language", sum(e["eff"] for e in cand))
