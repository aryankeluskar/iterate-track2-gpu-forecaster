"""Rule-based labelling from cached, dated, non-tracker results. Reads only runs/policy/cache. Never touches measured_rates.csv."""
import json, re, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import search

ALIAS = {"verda": ["verda", "datacrunch"], "lambdalabs": ["lambda"], "gcp": ["google cloud", "gcp", "google compute"], "aws": ["aws", "amazon web services", "amazon ec2", "ec2"],
         "azure": ["azure"], "oci": ["oracle", "oci"], "hyperstack": ["hyperstack", "nexgen"], "together": ["together ai", "together.ai"], "fal": ["fal.ai"],
         "sfcompute": ["sf compute", "sfcompute"], "lium": ["lium", "datura"], "primeintellect": ["prime intellect", "primeintellect"], "hotaisle": ["hot aisle", "hotaisle"],
         "massedcompute": ["massed compute", "massedcompute"], "impossiblecloud": ["impossible cloud"], "thundercompute": ["thunder compute"], "voltagepark": ["voltage park"],
         "digitalocean": ["digitalocean", "digital ocean"], "jarvislabs": ["jarvislabs", "jarvis labs"], "tensordock": ["tensordock"], "ovhcloud": ["ovh"], "gmi": ["gmi cloud"],
         "daytona": ["daytona"], "latitude": ["latitude.sh"], "linode": ["linode", "akamai"], "modal": ["modal labs", "modal.com"], "salad": ["salad"], "theta": ["theta edgecloud", "thetaedgecloud", "theta network"],
         "spheron": ["spheron"], "clore": ["clore"], "fireworks": ["fireworks ai", "fireworks.ai"]}
DYN = re.compile(r"dynamic pric|dynamic market|market[- ]based pric|market (price|rate)|demand[- ]based|demand[- ]driven pric|prices? (that )?(change|fluctuat|vary|adjust|move)\w*|pric\w* (changes|fluctuat\w+|varies|adjusts)|real[- ]time pric|supply and demand|surge pric|price (is|are) (set|determined) by|changes? (daily|hourly)|adjusted daily|updated daily|\bbid\w*|auction|reverse auction|orderbook|order book|spot (price|market|instance|pric)|preemptible|interruptible|peer[- ]to[- ]peer|marketplace|decentrali[sz]ed|set (their|own) (own )?price", re.I)
SPOTP = re.compile(r"\bspot\b|preemptible|interruptible|\bbid\w*|auction|marketplace|peer[- ]to[- ]peer|decentrali|order ?book|host(s)? set|set (their|own) (own )?price", re.I)
ENDED = re.compile(r"(phas\w+ out|discontinu\w+|sunset\w*|retir\w+|no longer|replac\w+ (dynamic|the dynamic)|moving (away )?from dynamic|end(ed|ing)? (of )?dynamic|fixed pric\w+ (instead|going forward))", re.I)
FIX = re.compile(r"\$\s?\d|per (gpu[- ])?(hour|hr)|/\s?(gpu[- ])?(hr|hour)|pay[- ]as[- ]you[- ]go|fixed (price|rate|pricing)|flat (rate|fee)|reserved|committed|on[- ]demand|rate card|price list|starting (at|from)", re.I)
SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def names(p):
    return ALIAS.get(p, [p])


def mentions(p, *texts):
    t = " ".join(x or "" for x in texts).lower()
    return any(a in t for a in names(p))


def load_sources():
    out = {}
    for f in search.CACHE.glob("search_*.json"):
        r = json.loads(f.read_text())
        if "results" not in r:
            continue
        p = r["provider"] if "provider" in r else None
        # provider tag is not stored in the cache file: recover from the query
        q = r["request"]["query"]
        prov = next((k for k, v in search.NAMES.items() if q.startswith(v + " ")), None)
        for x in r["results"]:
            if x["publishedDate"][:10] > search.END:
                continue
            out.setdefault(prov, {})[x["url"]] = x
    return out


def sentences(prov, x):
    sents = []
    for h in x["highlights"]:
        for s in SPLIT.split(h):
            s = s.strip()
            if 25 <= len(s) <= 500:
                sents.append(s)
    return sents


def evidence(prov, x):
    """Admissible = provider name in title, url or the sentence."""
    ev = []
    host = x["url"].split("/")[2] if "//" in x["url"] else x["url"]
    title_url = mentions(prov, host)
    for s in sentences(prov, x):
        if not (title_url or mentions(prov, s)):
            continue
        kinds = []
        if DYN.search(s): kinds.append("dyn")
        if SPOTP.search(s): kinds.append("spot")
        if ENDED.search(s): kinds.append("ended")
        if FIX.search(s): kinds.append("fix")
        if kinds:
            ev.append({"url": x["url"], "title": x["title"], "published": x["publishedDate"][:10], "sentence": s, "kinds": kinds})
    return ev


if __name__ == "__main__":
    src = load_sources()
    allev = {p: [e for x in src.get(p, {}).values() for e in evidence(p, x)] for p in search.NAMES}
    json.dump(allev, open(search.CACHE.parent / "candidates.json", "w"), indent=1)
    for p, ev in allev.items():
        print(f"## {p}: dated sources {len(src.get(p, {}))}, evidence sentences {len(ev)}, dyn {sum('dyn' in e['kinds'] for e in ev)}, spot {sum('spot' in e['kinds'] for e in ev)}, fix {sum('fix' in e['kinds'] for e in ev)}, ended {sum('ended' in e['kinds'] for e in ev)}")
