"""Dated Exa search per provider. Caches only sanitised responses under runs/policy/cache (key = sha256 of endpoint+request).
Results with no publishedDate or a date after END are discarded; tracker pages are reduced to a url stub before caching."""
import datetime as dt, hashlib, json, pathlib, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from gpuf.scout import _key

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / "runs" / "policy" / "cache"
END = "2026-08-17"
END_TS = f"{END}T23:59:59Z"
TRACKER = re.compile(r"gpurentalprices|fastgpu|getdeploying|cloud-gpus|computeprices|gpulist|gpu-?price|pricing-?tracker|vantage\.sh|pricepertoken|gpuhunt|gpucompare|gpu\.fm|price[- ]tracker|price[- ]history", re.I)
NAMES = {
 "aws": "Amazon Web Services EC2", "azure": "Microsoft Azure", "baseten": "Baseten", "cerebrium": "Cerebrium", "clore": "Clore.ai",
 "cloudrift": "CloudRift", "coreweave": "CoreWeave", "crusoe": "Crusoe Cloud", "cudo": "Cudo Compute", "daytona": "Daytona",
 "deepinfra": "DeepInfra", "digitalocean": "DigitalOcean", "exoscale": "Exoscale", "fal": "fal.ai", "fireworks": "Fireworks AI",
 "gcp": "Google Cloud Platform", "gmi": "GMI Cloud", "hetzner": "Hetzner", "hotaisle": "Hot Aisle", "hyperstack": "Hyperstack NexGen Cloud",
 "impossiblecloud": "Impossible Cloud", "jarvislabs": "Jarvislabs", "koyeb": "Koyeb", "lambdalabs": "Lambda Labs", "latitude": "Latitude.sh",
 "linode": "Linode Akamai", "lium": "Lium Datura", "massedcompute": "Massed Compute", "modal": "Modal Labs", "nebius": "Nebius",
 "northflank": "Northflank", "oci": "Oracle Cloud Infrastructure", "ovhcloud": "OVHcloud", "paperspace": "Paperspace", "primeintellect": "Prime Intellect",
 "quantacloud": "QuantaCloud", "replicate": "Replicate", "salad": "Salad Cloud", "scaleway": "Scaleway", "sfcompute": "SF Compute",
 "spheron": "Spheron Network", "synteq": "Synteq", "tensordock": "TensorDock", "tensorwave": "TensorWave", "theta": "Theta EdgeCloud",
 "thundercompute": "Thunder Compute", "together": "Together AI", "verda": "Verda DataCrunch", "voltagepark": "Voltage Park", "vultr": "Vultr",
}
HL_Q = "how are prices set: fixed rate card per hour, or dynamic, market, demand-based, spot, auction or bidding prices"


def _post(endpoint, body):
    CACHE.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(f"{endpoint}|{json.dumps(body, sort_keys=True)}".encode()).hexdigest()[:20]
    path = CACHE / f"{endpoint}_{h}.json"
    if path.exists():
        return json.loads(path.read_text())
    req = urllib.request.Request(f"https://api.exa.ai/{endpoint}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-api-key": _key(), "User-Agent": "gpuf-policy"})
    rec = {"request": body, "fetched_at": dt.datetime.utcnow().isoformat() + "Z"}
    for a in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                out = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and a < 3:
                time.sleep(2 * (a + 1)); continue
            rec["error"] = f"{e.code} {e.read().decode()[:300]}"; out = None; break
        except Exception as e:
            if a == 3:
                rec["error"] = repr(e); out = None; break
            time.sleep(2 * (a + 1))
    if out is not None:
        c = out.get("costDollars")
        rec["cost"] = c.get("total") if isinstance(c, dict) else c
        kept, dropped = [], {"undated": 0, "late": 0, "tracker": 0}
        for x in out.get("results", []):
            pdt = (x.get("publishedDate") or "")[:10]
            if not pdt: dropped["undated"] += 1; continue
            if pdt > END: dropped["late"] += 1; continue
            if TRACKER.search(x.get("url", "")) or TRACKER.search(x.get("title") or ""):
                dropped["tracker"] += 1; continue
            kept.append({"url": x.get("url"), "title": x.get("title"), "publishedDate": x.get("publishedDate"),
                         "highlights": x.get("highlights") or [], "text": x.get("text")})
        rec["results"], rec["dropped"] = kept, dropped
    path.write_text(json.dumps(rec))
    return rec


def search(provider, kind, n=8):
    name = NAMES[provider]
    q = {"docs": f"{name} GPU cloud pricing page: on-demand hourly rate, spot, bidding or dynamic pricing",
         "news": f"{name} announces GPU pricing model dynamic market pricing spot or price change",
         "spot": f"{name} GPU spot instances, preemptible, marketplace or bidding prices that change with demand"}[kind]
    body = {"query": q, "type": "auto", "numResults": n, "endPublishedDate": END_TS,
            "contents": {"highlights": {"query": HL_Q}, "maxAgeHours": -1}}
    rec = _post("search", body)
    rec["provider"], rec["kind"] = provider, kind
    return rec


def contents(urls):
    body = {"urls": urls, "highlights": {"query": HL_Q}, "maxAgeHours": -1}
    return _post("contents", body)


def spend():
    return round(sum(json.loads(p.read_text()).get("cost") or 0 for p in CACHE.glob("*.json")), 4)


if __name__ == "__main__":
    provs = sys.argv[1:] or list(NAMES)
    jobs = [(p, k) for p in provs for k in ("docs", "news", "spot")]
    with ThreadPoolExecutor(4) as ex:
        recs = list(ex.map(lambda j: search(*j), jobs))
    errs = [(r["provider"], r["kind"], r["error"][:80]) for r in recs if "error" in r]
    print("searches", len(recs), "errors", errs, "kept", sum(len(r.get("results", [])) for r in recs),
          "dropped", {k: sum(r.get("dropped", {}).get(k, 0) for r in recs) for k in ("undated", "late", "tracker")}, "spend $", spend())
