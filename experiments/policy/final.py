"""Assign provider x slot labels from cached dated evidence. Labels are fixed here before scoring; measured_rates.csv is not read."""
import json, re, pathlib, sys, collections
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import search, label as L

OUT = pathlib.Path(__file__).parent / "results"
CLASS_SLOT = {"neocloud_rate_card": "RATE", "hyperscaler_list": "RATE", "neocloud_spot": "SPOT", "hyperscaler_spot": "SPOT", "marketplace_ask": "SPOT"}
PROV_SLOTS = {  # slots present per provider, from the class lists printed by measure.py (class names only)
 "aws": "RATE SPOT", "azure": "RATE SPOT", "gcp": "RATE SPOT", "oci": "RATE SPOT", "coreweave": "RATE SPOT", "daytona": "RATE SPOT", "hyperstack": "RATE SPOT", "nebius": "RATE SPOT",
 "together": "RATE SPOT", "verda": "RATE SPOT", "vultr": "RATE SPOT", "clore": "SPOT", "lium": "SPOT", "primeintellect": "SPOT", "salad": "SPOT", "sfcompute": "SPOT", "spheron": "SPOT",
 "tensordock": "SPOT", "theta": "SPOT"}
RATE_ONLY = "baseten cerebrium cloudrift crusoe cudo deepinfra digitalocean exoscale fal fireworks gmi hetzner hotaisle impossiblecloud jarvislabs koyeb lambdalabs latitude linode massedcompute modal northflank ovhcloud paperspace quantacloud replicate scaleway synteq tensorwave thundercompute voltagepark".split()
for p in RATE_ONLY: PROV_SLOTS[p] = "RATE"
# crusoe and others with a spot class in the panel: crusoe, coreweave, daytona, hyperstack, nebius, together, verda, vultr (neocloud_spot) -- crusoe has only neocloud_rate_card in the panel
LATE = re.compile(r"(sep(t|tember)?|oct(ober)?|nov(ember)?|dec(ember)?)\.?\s+(\d{1,2},?\s+)?2026|2026-(09|1[0-2])|aug(ust)?\s+(1[89]|2\d|3[01]),?\s+2026|q4 2026|2026-08-(1[89]|2\d|3[01])", re.I)

# (provider, slot) -> (label, url substring, sentence substring, strength, note)
SPEC = {
 ("aws", "SPOT"): ("DYNAMIC", "new-amazon-ec2-spot-pricing", "you just pay the Spot price that", "strong", ""),
 ("azure", "SPOT"): ("DYNAMIC", "azure-spot-instances", "Pricing for Azure Spot instances is dynamic", "strong", ""),
 ("gcp", "SPOT"): ("DYNAMIC", "julien-cartigny", "Prices will change daily", "strong", "third-party LinkedIn post reporting a Google notice, 2025-07-28"),
 ("oci", "SPOT"): ("FIXED", "announcing", "Always 50% off", "strong", "preemptible instances at a fixed discount: rubric clarification, fixed-discount spot = FIXED"),
 ("hyperstack", "SPOT"): ("FIXED", "hyperstack.cloud/blog", "Spot VMs with 20% lower pricing", "strong", "fixed-discount spot = FIXED"),
 ("coreweave", "SPOT"): ("DYNAMIC", "coreweave-s-flexible", "Spot instances are generally available", "weak", "spot offered; no sentence on how the price moves"),
 ("verda", "SPOT"): ("DYNAMIC", "verda-monthly-digest-november", "Spot prices starting from", "weak", "spot offered; the same digest says dynamic pricing is being phased out for on-demand"),
 ("vultr", "SPOT"): ("DYNAMIC", "amd-gpu-preemptible", "preemptible instances offer", "weak", "preemptible offered; no sentence on how the price moves"),
 ("clore", "SPOT"): ("DYNAMIC", "blog.clore.ai", "Hardware owners list their servers, set their prices", "strong", ""),
 ("primeintellect", "SPOT"): ("DYNAMIC", "primeintellect.ai/blog/compute", "lowest bid on any request", "weak", "marketplace aggregator; no sentence on price dynamics"),
 ("salad", "SPOT"): ("DYNAMIC", "community.salad.com", "workloads compete for the best nodes", "weak", "priority tiers priced differently; interruptible nodes"),
 ("sfcompute", "SPOT"): ("DYNAMIC", "dailydropout", "SF Compute runs", "strong", "marketplace described as a stock exchange"),
 ("theta", "SPOT"): ("DYNAMIC", "docs.thetatoken.org", "node operators (the supply side) to set their own hourly rental rates", "strong", ""),
 ("verda", "RATE"): ("FIXED", "verda-monthly-digest-november", "Dynamic Pricing is being phased out", "strong",
                     "conflict rule: 2024-08-02 PRWeb says dynamic pricing (daily market price); the later 2025-12-05 digest says it is being phased out for fixed pricing"),
}
OVERRIDE_NOT_DYN = {  # (provider, url substring) -> reason: sentence is not about the provider's own posted price
 ("modal", "resource-solver"): "'prices change by the minute' describes the clouds Modal rents from, not Modal's posted price",
 ("cerebrium", "how-much-does-a-h200"): "generic market sentence in a GPU cost guide, not about Cerebrium's own posted price",
 ("hetzner", "excello"): "hardware component cost fluctuation, announced as a discrete price rise",
 ("digitalocean", "askgpu"): "SPOT-only statement (spot droplets launched 2026-08-10); does not describe the on-demand rate card",
}


def sources():
    src = L.load_sources()
    out, dropped = {}, collections.Counter()
    for p, d in src.items():
        for u, x in d.items():
            blob = " ".join([x["title"] or ""] + x["highlights"])
            if LATE.search(blob):
                dropped[p] += 1; continue
            out.setdefault(p, {})[u] = x
    return out, dropped


def rec(p, slot, lab, ev, strength, note, nsrc, ndrop, extra=None):
    r = {"provider": p, "slot": slot, "label": lab, "strength": strength, "note": note, "dated_sources": nsrc, "late_dated_text_dropped": ndrop}
    r.update(ev or {"url": None, "title": None, "published": None, "sentence": None}); r["other_evidence"] = extra or []
    return r


def main():
    src, dropped = sources()
    rows = []
    for p, slots in PROV_SLOTS.items():
        evs = [e for x in src.get(p, {}).values() for e in L.evidence(p, x)]
        nsrc, nd = len(src.get(p, {})), dropped.get(p, 0)
        for slot in slots.split():
            spec = SPEC.get((p, slot))
            if spec:
                lab, us, ss, st, note = spec
                hit = next(({"url": u, "title": x["title"], "published": x["publishedDate"][:10], "sentence": sn} for u, x in src.get(p, {}).items() if us in u
                             for sn in L.sentences(p, x) if ss in sn and (L.mentions(p, x["title"], u) or L.mentions(p, sn))), None)
                if hit is None:
                    raise SystemExit(f"spec evidence not found: {p} {slot}")
                extra = []
                if (p, slot) == ("verda", "RATE"):
                    extra = [e for u, x in src["verda"].items() if "prweb" in u for e in L.evidence(p, x) if "dynamic" in e["sentence"].lower()][:1]
                rows.append(rec(p, slot, lab, hit, st, note, nsrc, nd, extra)); continue
            if slot == "RATE":
                dyn = [e for e in evs if "dyn" in e["kinds"] and not any(k == p and s in e["url"] for (k, s) in OVERRIDE_NOT_DYN)
                       and re.search(r"dynamic pric|market[- ]based|demand[- ]based|prices? (fluctuat|chang|vary)", e["sentence"], re.I)
                       and not SPOTP_ONLY(e["sentence"]) and L.mentions(p, e["sentence"])]
                if dyn:
                    rows.append(rec(p, slot, "DYNAMIC", dyn[0], "weak", "auto rule hit", nsrc, nd)); continue
            fix = [e for e in evs if "fix" in e["kinds"] and re.search(r"\$\s?\d", e["sentence"]) and re.search(r"hour|hr", e["sentence"], re.I) and "marketplace" not in e["sentence"].lower()]
            if slot == "RATE" and fix:
                rows.append(rec(p, slot, "FIXED", fix[0], "weak", "published per-hour price in a dated source; no dynamic statement", nsrc, nd)); continue
            if slot == "SPOT":
                rows.append(rec(p, slot, "UNKNOWN", None, "-", "no usable dated source stating how spot or marketplace prices are set", nsrc, nd)); continue
            rows.append(rec(p, slot, "UNKNOWN", None, "-", "no usable dated source with a published price", nsrc, nd))
    with open(OUT / "provider_policy.jsonl", "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    md = ["| provider | slot | label | strength | published | title | quote | note |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        q = (r["sentence"] or "").replace("|", "/")[:200]
        md.append(f"| {r['provider']} | {r['slot']} | {r['label']} | {r['strength']} | {r['published'] or ''} | [{(r['title'] or '')[:50].replace('|','/')}]({r['url']}) | {q} | {r['note'][:110]} |" if r["url"] else
                  f"| {r['provider']} | {r['slot']} | {r['label']} | - | | | | {r['note'][:110]} (dated sources {r['dated_sources']}, dropped for post-cutoff text {r['late_dated_text_dropped']}) |")
    (OUT / "provider_policy.md").write_text("\n".join(md) + "\n")
    c = collections.Counter((r["slot"], r["label"]) for r in rows)
    print(dict(c))


def SPOTP_ONLY(s):
    return bool(re.search(r"\bspot\b|preemptible|interruptible", s, re.I))


if __name__ == "__main__":
    main()
