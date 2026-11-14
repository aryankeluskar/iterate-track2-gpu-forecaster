"""Build every data point sent to past.dev from the project's own files. Nothing is invented: each field is read from a file.

python experiments/memory/build_records.py            writes experiments/memory/results/records.json (offline, no network)
Used by run_live.py (test and import).
"""
from __future__ import annotations

import csv
import glob
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACK = ROOT / "data/pack/gpu-price-pack-v0.1.1-handover"
FAILURES, EVIDENCE, EXPERIMENTS = "gpuf-failures", "gpuf-evidence", "gpuf-experiments"


def eod(date: str) -> str:
    return f"{date}T23:59:59Z"


def exa_ts(published: str) -> str:
    """Exa timestamp; a bare midnight means only the day is known, so the end of that day is used (never earlier than known)."""
    p = published.replace(".000Z", "Z")
    if len(p) == 10:
        return eod(p)
    return eod(p[:10]) if p.endswith("T00:00:00Z") else p


def item(id, audience, author, ts, label, content, **meta):
    return {"id": id, "audience": audience, "identity": author, "timestamp": ts, "label": label,
            "metadata": {"agent": author, **meta}, "content": content.strip()}


def ledger_item(e: dict) -> dict:
    from gpuf.memory import ledger_item as li
    return li(e)


def event_item(r: dict) -> dict:
    sid, d = r["series_id"], r["date_b"]
    def prov(k):
        return r[k] or "none"
    txt = (f"Autopsy event {d} on series {sid} (written by autopsy)\n"
           f"Series: {sid}\nDate of the move: {r['date_a']} -> {d}\n"
           f"Median: {r['m_a']} -> {r['m_b']} USD per GPU-hour (log change {float(r['dlog']):+.4f}, {100 * (2.718281828 ** float(r['dlog']) - 1):+.1f}%)\n"
           f"Cause: {r['cause']} (repricing part {float(r['rep']):+.4f}, composition part {float(r['comp']):+.4f}; Shapley cause {r['cause_shapley']})\n"
           f"Pivotal provider: {prov('pivotal')}\nProviders that raised: {prov('prov_reprice_up')}\nProviders that cut: {prov('prov_reprice_down')}\n"
           f"Providers that entered the panel: {prov('prov_entered')}\nProviders that left the panel: {prov('prov_exited')}\n"
           f"Offers: {r['n_offers_a']} -> {r['n_offers_b']} (repriced {r['n_repriced']}, entered {r['n_entered']}, exited {r['n_exited']})")
    return item(f"autopsy-{sid}-{d}", FAILURES, "autopsy", eod(d), f"Autopsy: {sid}", txt, kind="event", series=sid, date=d,
                cause=r["cause"], source="experiments/autopsy/results/events_dev_top60.csv")


def event_items() -> list[dict]:
    rows = list(csv.DictReader(open(ROOT / "experiments/autopsy/results/events_dev_top60.csv")))
    return [event_item({**r, "series_id": r["series_id"]}) for r in rows]


def mode_items() -> list[dict]:
    f = json.load(open(ROOT / "experiments/autopsy/results/failure_modes.json"))
    out = []
    for m in f["modes"]:
        lines = [f"Autopsy failure mode {m['rank']}: {m['name']} (written by autopsy)"]
        lines += [f"{k}: {v}" for k, v in m.items() if k not in ("rank", "name")]
        out.append(item(f"autopsy-mode-{m['id']}", FAILURES, "autopsy", eod("2026-10-13"), f"Failure mode: {m['name']}",
                        "\n".join(lines), kind="failure_mode", rank=m["rank"], source="experiments/autopsy/results/failure_modes.json"))
    return out


def scout_item(url, title, published, quote, explains, ts=None, **meta):
    sid = "scout-" + __import__("hashlib").sha256(url.encode()).hexdigest()[:8]
    domain = re.sub(r"^www\.", "", url.split("/")[2])
    ts = ts or exa_ts(published)
    txt = (f"Web evidence from {domain}, published {published[:10]} (written by scout)\nURL: {url}\nTitle: {title}\n"
           f"Published: {published}\nQuoted sentence: \"{quote}\"\nExplains: {explains}")
    return item(sid, EVIDENCE, "scout", ts, f"Evidence: {domain}", txt, kind="web_evidence", url=url, published=published, **meta)


def attribution_items() -> list[dict]:
    rows = [json.loads(l) for l in open(ROOT / "experiments/exa_attrib/results/attribution.jsonl")]
    out = []
    # timestamps: the later of Exa's published date and any date the page text states about itself (all checked in the
    # cached highlights); the fal page's URL slug says 2026-10-04, later than its published date, so the later date is used
    ts = {"thefivenines.com": "2026-09-16T07:00:00Z", "usagepricing.com": eod("2026-10-04"), "jarvislabs.ai": "2026-09-24T16:33:04Z"}
    pub = {"thefivenines.com": "2026-09-16T07:00:00Z", "usagepricing.com": "2026-10-01", "jarvislabs.ai": "2026-09-24T16:33:04Z"}
    for r in rows:
        if not (r["evidence_url"] and r["evidence_published"] and r["quote"]):
            continue
        dom = re.sub(r"^www\.", "", r["evidence_url"].split("/")[2])
        expl = (f"{r['provider']} {r['gpu']} repricing seen in the data on {r['date']} (attribution label {r['label']}"
                + (f", lead {r['lead_days']} days" if r["lead_days"] is not None else "") + f"). {r['note']}")
        out.append(scout_item(r["evidence_url"], r["evidence_title"], pub.get(dom, r["evidence_published"]), r["quote"], expl,
                              ts=ts.get(dom), attribution_id=r["id"], label_class=r["label"]))
        for a in r["also"]:
            m = re.match(r"^(\d{4}-\d\d-\d\d) (\S.*?): \"(.+)\" (https?://\S+)$", a) or re.match(r"^(.+?) \(published (\d{4}-\d\d-\d\d)\): \"(.+)\" (https?://\S+)$", a)
            if not m:
                continue
            g = m.groups()
            d, src, q, u = (g[0], g[1], g[2], g[3]) if re.match(r"\d{4}", g[0]) else (g[1], g[0], g[2], g[3])
            when = "2026-09-17T16:12:34Z" if "reuters.com" in u else None
            out.append(scout_item(u, f"{src} (second source for attribution {r['id']})", d, q,
                                  f"Same repricing as above: {r['provider']} {r['gpu']} on {r['date']}.", ts=when, attribution_id=r["id"]))
    return out


def exa_hit(url_part: str):
    for p in sorted(glob.glob(str(ROOT / "data_out/exa_cache/*.json")) + glob.glob(str(ROOT / "runs/orch/exa/*.json"))):
        try:
            s = json.load(open(p))
        except Exception:
            continue
        for r in (s.get("results") or []) if isinstance(s, dict) else []:
            if url_part in r.get("url", ""):
                return r
    raise KeyError(url_part)


def prweb_item() -> dict:
    r = exa_hit("prweb.com/releases/datacrunchio-introduces-dynamic-pricing")
    hl = r["highlights"][0]
    q = next(s for s in re.split(r"(?<=\.)\s+", hl) if "market price changes daily based on demand" in s)
    return scout_item(r["url"], r["title"], r["publishedDate"], q,
                      "How the provider now called Verda priced GPUs: a dynamic market price that changes daily. Note from the orchestrator, not verified by scout: "
                      "DataCrunch is now Verda, the provider that makes 84% of reprices on fastgpu_daily.", note_source="runs/orch/exa/60e0f8de5c762c6c.json")


def test_scout_items() -> list[dict]:
    a = exa_hit("askgpu.com/updates/nebius-raises-on-demand-gpu-prices")
    s = exa_hit("blog.salad.com/saladcloud-price-changes-september-2026")
    f = exa_hit("theweightedaverage.com/notes/2026-09-01-fireworks-gpu-rate-increase")
    l = exa_hit("7501005054821253121")
    fw_q = re.search(r"Fireworks.{0,3} current on-demand price table raises[^\n]*?increase\.", f["highlights"][0]).group(0)
    return [
        scout_item(a["url"], a["title"], a["publishedDate"],
                   "From October 1, 2026, a Nebius H100 costs $4.50 per GPU-hour on demand instead of $3.85, and a B300 $9.50 instead of $7.85.",
                   "Nebius on-demand repricing effective 2026-10-01. Exa's published date is 2026-10-01 but the page text says \"Published Oct 18, 2026\", so it is timed 2026-10-18.",
                   ts=eod("2026-10-18")),
        scout_item(s["url"], s["title"], s["publishedDate"],
                   "SaladCloud GPU and vCPU pricing is changing on September 12, 2026: 15 GPU classes drop 25% on average, while RTX 5090 and 4090 prices increase.",
                   "A September down-move on the marketplace class (effective 2026-09-12)."),
        scout_item(f["url"], f["title"], f["publishedDate"], fw_q, "Fireworks on-demand GPU rate increase effective 2026-09-01."),
        scout_item(l["url"], l["title"], l["publishedDate"], "In the last 3 months, GPU prices have risen across all SKUs.",
                   "Context for the burst of price increases from 17 September onward."),
    ]


def autopsy_test_items() -> list[dict]:
    ev = {(r["series_id"], r["date_b"]): r for r in csv.DictReader(open(ROOT / "experiments/autopsy/results/events_dev_top60.csv"))}
    ts6 = eod("2026-10-06")
    i1 = item("autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-10-06", FAILURES, "autopsy", ts6,
              "Autopsy: gpurentalprices.marketplace_ask.H100_80GB.spot.median",
              "Autopsy case 2026-10-06 (written by autopsy): the largest loss series on the dev period\n"
              "Series: gpurentalprices.marketplace_ask.H100_80GB.spot.median\n"
              "Share of the blend's last-value loss: 13.6% (largest of 37 series, runs/failure/decomp.txt)\n"
              "Skill against the last value: blend 0.346, drift 0.130\n"
              "What moves: marketplace asks (providers sfcompute and spheron in events_dev_top60.csv), not rate-card repricing. Example: median 2.19 -> 1.46 on 2026-08-05 (spheron cut), 1.46 -> 2.10 on 2026-08-06.",
              kind="case", source="runs/failure/decomp.txt")
    i2 = item("autopsy-fastgpu_daily.neocloud_rate_card.B300.on_demand.median-2026-10-06", FAILURES, "autopsy", ts6,
              "Autopsy: fastgpu_daily.neocloud_rate_card.B300.on_demand.median",
              "Autopsy case 2026-10-06 (written by autopsy): second largest loss series\n"
              "Series: fastgpu_daily.neocloud_rate_card.B300.on_demand.median\n"
              "Share of the blend's last-value loss: 13.1% (cumulative 0.267 after 0.136 for the largest series); blend skill 0.157, drift 0.087\n"
              "The same B300 class on gpurentalprices.neocloud_rate_card.B300.on_demand.median carries 9.6% (blend skill 0.131, drift 0.091).\n"
              "Both collectors moved together: mean same-day correlation of changes 0.248 (median 0.249) over 9 GPUs shared by fastgpu_daily and gpurentalprices.",
              kind="case", source="runs/failure/decomp.txt; runs/failure/events.txt")
    i3 = item("autopsy-all-2026-10-04", FAILURES, "autopsy", eod("2026-10-04"), "Autopsy: all series, busiest day",
              "Autopsy case 2026-10-04 (written by autopsy): the busiest day of the dev period\n"
              "6 of 37 series moved more than 5% on 2026-10-04. Days with 5 or more big moves: 2026-10-02 (5), 2026-10-03 (5), 2026-10-04 (6), 2026-10-06 (5) (runs/failure/events.txt).\n"
              "The 5 busiest days carry 34.8% of big moves.\n"
              "Upper tail under-covered at h=7: 27 to 33% of truths fall above q90 for every method (research-log.md).",
              kind="case", source="runs/failure/events.txt; research-log.md")
    k = ("gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand.median", "2026-10-03")
    i4 = event_item(ev[k])
    return [i1, i2, i3, i4]


def experiment_test_items() -> list[dict]:
    from gpuf import ledger
    by = {e["id"]: e for e in ledger.load()}
    return [ledger_item(by[i]) for i in ("H7b", "H7", "H9", "H10")]


def test_items() -> dict[str, list[dict]]:
    return {"autopsy": autopsy_test_items(), "scout": test_scout_items(), "experimenter": experiment_test_items()}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from gpuf import ledger
    allr = {"tests": test_items(), "modes": mode_items(), "events": event_items(), "evidence": attribution_items() + [prweb_item()],
            "ledger": [ledger_item(e) for e in ledger.load()]}
    out = ROOT / "experiments/memory/results/records.json"
    out.write_text(json.dumps(allr, indent=1))
    print({k: (len(v) if isinstance(v, list) else {a: len(b) for a, b in v.items()}) for k, v in allr.items()}, "->", out)
