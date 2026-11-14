import json, math, statistics, datetime as dt
import pandas as pd
import rule
from gpuf.scout import exa_spend
ROOT = "/Users/aryank/Developer/iterate_hackathon/track_2"
sel = pd.read_csv(f"{ROOT}/runs/exa_attrib/selected.csv").set_index("id")
merged = pd.read_csv(f"{ROOT}/runs/exa_attrib/events_merged.csv")
tot_score = merged.score.sum()
# an event seen by two collectors on two days keeps the earlier date and adds the later one's score
merged["k"] = merged.provider + merged.gpu + merged.old.map("{:.2f}".format) + merged.new.map("{:.2f}".format)
w = {i: merged[merged.k == (e.provider + e.gpu + f"{e.old:.2f}" + f"{e.new:.2f}")].score.sum() for i, e in sel.iterrows()}
S = json.load(open(f"{ROOT}/runs/exa_attrib/search_events.json"))
by = {}
for r in S: by.setdefault(r["id"], []).append(r)
J = lambda **k: k
# hand labels. Quotes are verbatim from the fetched text or highlights.
H = {
 26: J(label="ANNOUNCED_BEFORE", first="2026-09-16", url="https://www.thefivenines.com/data-ai/nebius-raises-gpu-prices-20-as-supply-tightens", title="Nebius raises GPU prices 20% as supply tightens | Five Nines",
       quote="BigGo Finance reported that Nebius said it will raise GPU cloud prices by an average of 20 percent from October 1, covering H100, H200, B200 and B300 chips, with B300 rising from $7.85 to $9.50 per GPU-hour.",
       also=["2026-09-17 Reuters: \"Cloud provider Nebius said on Thursday it will raise pay-as-you-go prices for leasing selected Nvidia chips from October 1, marking the company's second price hike\" https://www.reuters.com/technology/nebius-hikes-ai-cloud-prices-again-demand-computing-power-soars-2026-09-17/"],
       note="Customer pricing notice, relayed by Bloomberg and Reuters. Exa's publishedDate for each page is its own article date; the Nebius price page itself is undated in Exa."),
 29: J(label="ANNOUNCED_BEFORE", first="2026-09-24", url="https://jarvislabs.ai/updates/gpu-pricing-october-2026", title="New GPU rates from October 5, 2026 | Jarvislabs Updates",
       quote="From October 5, 2026 at 00:00 IST, new rates apply to NVIDIA H200, H100 and RTX PRO 6000 GPUs. | NVIDIA RTX PRO 6000 | $1.89/hr | $2.19/hr",
       also=[], note="Provider's own changelog page. 00:00 IST on Oct 5 is 18:30 UTC on Oct 4, which is the day the series shows the move."),
 27: J(label="REPORTED_AFTER", first="2026-10-01", url="https://www.usagepricing.com/blueprint/activity/fal-ai-2026-10-04-gpu-fleet-repricing", title="Fal price change: fal reprices GPU fleet upward and adds GB200 | UsagePricing",
       quote="Every negotiated \"as low as\" floor rose, by 32% (H100) to 81% (RTX PRO 6000), and every list price rose except the H100's, which had already gone up in August.",
       also=["PricingSaaS Pulse (published 2026-10-01): \"GPU rates were untouched as well.\" https://pricingsaas.com/news/article/fal-rebuilds-its-model-api-pricing-into-per-endpoint-table"],
       note="Exa dates the page 2026-10-01, the URL slug says 2026-10-04 and the text lists the new B300 list price of $12.99/h that the data first shows on 10-02. It is a report of a change already made, not a notice. Another page (withorb.com, published 2026-09-18) contains text dated 'October 26, 2026', so Exa's published date does not bound the text."),
}
for i in sel.index:
    if i not in H: H[i] = J(label="NO_TRACE", first=None, url=None, title=None, quote=None, also=[], note="")
H[28]["note"] = "Lambda price-list pages through 2026-10-01 still show $3.99 (checked 28 Sep); no page reports a Lambda change."
for i in (0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,18,19,20,22,23,24,30,31):
    H[i]["note"] = "Market-priced ask (SF Compute order book or Spheron marketplace); no list price to announce. Pages with price-change language were sfcompute changelogs whose text is dated after the event (see attribution.md limits)."
rows = []
for i, e in sel.iterrows():
    h = H[i]; D = dt.date.fromisoformat(e.date)
    searches = [s for r in by[i] for s in r["searches"]]
    src = {}
    for s in searches:
        for x in s["hits"]:
            src.setdefault(s["window"], {}).setdefault(x["url"], dict(url=x["url"], title=x["title"], published=x["published"], highlight=(x["highlights"] or [""])[0][:300], query_kind=s["kind"]))
    v2 = any(rule.strict2(x, e.provider) for s in searches if s["window"] == "BEFORE" for x in s["hits"])
    lead = (D - dt.date.fromisoformat(h["first"])).days if h["label"] == "ANNOUNCED_BEFORE" else None
    rows.append(dict(id=int(i), stratum=e.stratum, provider=e.provider, gpu=e.gpu, series_class=e.cls, date=e.date, old=round(float(e.old), 4), new=round(float(e.new), 4),
        provider_change=round(float(e.prov_chg), 4), median_log_move=round(float(e.median_move), 4), loss_weight=round(float(w[i]), 6), label=h["label"], lead_days=lead,
        evidence_url=h["url"], evidence_title=h["title"], evidence_published=h["first"], quote=h["quote"], also=h["also"], note=h["note"], mechanical_rule_v2_fired=bool(v2),
        before_window=[(D - dt.timedelta(21)).isoformat(), (D - dt.timedelta(1)).isoformat()], after_window=[D.isoformat(), min(D + dt.timedelta(14), dt.date(2026, 11, 6)).isoformat()],
        n_hits_before=len(src.get("BEFORE", {})), n_hits_after=len(src.get("AFTER", {})), sources_before=list(src.get("BEFORE", {}).values())[:12], sources_after=list(src.get("AFTER", {}).values())[:12]))
with open(f"{ROOT}/experiments/exa_attrib/results/attribution.jsonl", "w") as f:
    for r in rows: f.write(json.dumps(r) + "\n")
df = pd.DataFrame(rows)
def share(mask, wcol=None): return float(df[mask].loss_weight.sum() / df.loss_weight.sum()) if wcol else float(mask.mean())
A = df.label == "ANNOUNCED_BEFORE"
rc = df.series_class == "neocloud_rate_card"
# controls
C = [r for r in json.load(open(f"{ROOT}/runs/exa_attrib/search_controls.json"))]
cf = {r["id"]: any(rule.strict2(x, r["provider"]) for s in r["searches"] if s["window"] == "BEFORE" for x in s["hits"]) for r in C}
nfa = sum(cf.values()); n = len(cf)
def wilson(k, n, z=1.645):
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - a) / d, (c + a) / d
lo, hi = wilson(nfa, n)
head = dict(n_events=len(df), n_announced_before=int(A.sum()), share_events_announced=round(float(A.mean()), 3),
    share_loss_announced_of_selected=round(share(A, 1), 3), selected_cover_of_all_event_score=round(float(df.loss_weight.sum() / tot_score), 3),
    lower_bound_share_of_all_event_score=round(float(df[A].loss_weight.sum() / tot_score), 3),
    n_reported_after=int((df.label == "REPORTED_AFTER").sum()), n_no_trace=int((df.label == "NO_TRACE").sum()),
    rate_card_events=int(rc.sum()), rate_card_announced=int((A & rc).sum()), rate_card_share_loss_announced=round(float(df[A & rc].loss_weight.sum() / df[rc].loss_weight.sum()), 3),
    marketplace_events=int((df.series_class == "marketplace_ask").sum()), median_lead_days=statistics.median(df[A].lead_days), leads=df[A].lead_days.tolist(),
    v2_fired_on_events=int(df.mechanical_rule_v2_fired.sum()), v2_true_among_fired=int((df.mechanical_rule_v2_fired & A).sum()),
    control_pairs=n, control_false_alarms_v2=nfa, control_false_alarm_rate=round(nfa / n, 2), control_ci90=[round(lo, 2), round(hi, 2)], control_fired_ids=[i for i, v in cf.items() if v],
    spend_usd=exa_spend())
json.dump(head, open(f"{ROOT}/experiments/exa_attrib/results/headline.json", "w"), indent=1)
print(json.dumps(head, indent=1))
L = ["# Failure attribution with Exa: were provider repricings announced before they showed up in the price data?\n",
 "Dev rows only (<= 2026-10-13); every search had endPublishedDate <= 2026-11-06. BEFORE = D-21..D-1, AFTER = D..min(D+14, 11-06). Size = how far the series median moved that day (log). Loss weight = |median move| x the series' share of dev last-value loss (merged duplicates summed).\n",
 "## Headline\n", "```json\n" + json.dumps(head, indent=1) + "\n```\n",
 "## Events\n", "| id | provider | GPU | date | price old>new | median move | label | lead (d) | source (published) | quoted sentence |", "|---|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    src = f"[{(r['evidence_title'] or '')[:50]}]({r['evidence_url']}) ({r['evidence_published']})" if r["evidence_url"] else ""
    L.append(f"| {r['id']} | {r['provider']} | {r['gpu']} | {r['date']} | {r['old']:.3g}>{r['new']:.3g} | {r['median_log_move']:+.3f} | {r['label']} | {r['lead_days'] if r['lead_days'] is not None else ''} | {src} | {(r['quote'] or '').replace('|', '/')} |")
L += ["\n## Notes per labelled event\n"] + [f"- **{r['id']} {r['provider']} {r['gpu']} {r['date']} ({r['label']})**: {r['note']} " + " ".join(r["also"]) for r in rows if r["label"] != "NO_TRACE"]
L += ["\n## Control (10 provider-GPU-date pairs with no repricing in D-21..D+7)\n", "| id | provider | GPU | date | rule v2 fired | hand check |", "|---|---|---|---|---|---|"]
ctl = pd.read_csv(f"{ROOT}/runs/exa_attrib/controls.csv")
hand = {3: "provider-wide hike announced for other GPUs (H200/H100/RTX PRO 6000 from Oct 5), not A100 40GB", 4: "pricing-guide page, no change stated", 7: "Nebius Oct 1 hike covers H100-B300, not RTX PRO 6000", 9: "page published 09-10 whose text was updated 10-01; no change for L40S"}
for i, c in ctl.iterrows(): L.append(f"| {i} | {c.provider} | {c.gpu} | {c.date} | {cf[i]} | {hand.get(i, '')} |")
open(f"{ROOT}/experiments/exa_attrib/results/attribution.md", "w").write("\n".join(L) + "\n")
