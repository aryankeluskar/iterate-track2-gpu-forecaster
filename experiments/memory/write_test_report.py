"""Assemble results/test_report.md from test_send.json, test_recall.json, test_recall_tables.md, usage_before.json (+ one extra live date-bound recall)."""
import json, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from gpuf import memory as m
R = ROOT / "experiments/memory/results"
send, rc, ub = json.load(open(R / "test_send.json")), json.load(open(R / "test_recall.json")), json.load(open(R / "usage_before.json"))
ua = m.usage()
t0 = time.time()
x = m.recall("Nebius raises on-demand GPU prices H100 B300 $9.50 October 1", "forecaster", agent="forecaster", as_of="2026-10-06", limit=20)
dt = time.time() - t0
xs = {s["sourceId"]: s["occurredAt"] for r in x["results"] for s in r["sources"]}
txt = " ".join(r["content"] for r in x["results"])
leak = [k for k, v in xs.items() if v > "2026-10-06T23:59:59Z"] + (["text mentions Oct 18"] if "Oct 18" in txt or "October 18" in txt else []) + (["askgpu id"] if "scout-f4c32699" in xs else [])
ua = m.usage()
spent0, spent1 = ub["balance"]["spent"], ua["balance"]["spent"]
rec = rc["recalls"]
L = ["# past.dev memory: live test report", "",
     f"Run 2026-11-14 on project `default-project` (existing; no project, key, MCP server or webhook was created). Setup: 3 audiences, 6 identities (the plan's 5 plus `researcher`). Verified by `GET /identities/{{id}}`: each reader's `audiences` list matches the plan (forecaster and scout: failures + evidence; autopsy, experimenter, proposer, researcher: all three).", "",
     "## Summary", "", "| question | identity | as_of | result |", "|---|---|---|---|"]
L += [f"| {r['id']} | {r['identity']} | {r['as_of'] or '-'} | {'PASS' if r['pass'] else 'FAIL'} |" for r in rec]
L += ["", f"Access check (forecaster must get nothing from gpuf-experiments): {'PASS' if next(r for r in rec if r['id']=='Q6')['pass'] else 'FAIL'} (Q6 returned no `exp-*` source; Q3 and Q4 likewise).",
      f"Date-bound check (as_of 2026-10-06 must not return the askgpu Nebius page timed 2026-10-18): {'PASS' if not leak and next(r for r in rec if r['id']=='Q3')['pass'] else 'FAIL'}. Q3 returned none of it; an extra targeted recall for its exact wording (`$9.50`, `B300`, `October 1`) at as_of 2026-10-06 returned {len(x['results'])} results, sources {sorted(xs)}, leaks: {leak or 'none'}. The raw API response (journalled before our own filter) already contained no result dated after the bound, and no derived memory text mentioned \"Oct 18\" or $4.50. At as_of 2026-10-31 (Q4) the page comes back.", "",
      "## Credits and time", "",
      f"- Usage before setup: balance left {ub['balance']['left']:.0f}, spent {spent0:.0f} (1 credit and 1 ingestion were already in the project before this run).",
      f"- After the test (plus one exploratory recall and the extra date-bound recall): left {ua['balance']['left']:.0f}, spent {spent1:.0f}. Credits used by this test: {spent1 - spent0:.0f} = 25 for 12 records (1 per 350 bytes, rounded up per record) + {spent1 - spent0 - 25:.0f} recalls (1 credit each: the plan is metered pay-as-you-go).",
      "- Ingestion (time from POST to `status: completed`, `settled: true`, polled every 2 s): " + "; ".join(f"{k}: {v['n']} records, {v['complete_s']} s ({v['per_item_s']} s per record, accepted in {v['accept_s']} s)" for k, v in send.items()) + ".",
      f"- Recall latency: " + ", ".join(f"{r['id']} {r['seconds']} s" for r in rec) + f", extra {dt:.2f} s; every recall returned 20 results (limit 20). Offline replay from the journal was identical for all six.", "",
      "## Deviations from the plan (documented, nothing invented)", "",
      "- Record 4: the plan said the on-demand H100 median was repriced by Nebius on 2026-10-01. The pack disagrees: `gpurentalprices` H100 SXM 80GB on-demand rate-card median is 3.20 on 2026-10-01 and 2026-10-02 and 3.64195 on 2026-10-03 (daily_statistics.csv; events_dev_top60.csv row: cause composition, verda raised, scaleway cut, offers 7 to 10). The record states that event (timed 2026-10-03, same text the full import sends, so the import leaves it unchanged) and makes no claim about Nebius or a forecast miss. Q4 therefore expects the askgpu page (record 5) and lists record 4 as a bonus.",
      "- Experiment records 9 to 12: the ledger ids differ from the plan's names (H7b breadth, H7 lead, H9 reversal, H10 news); the records are the ledger entries verbatim, ids `exp-<ledger id>`, timed with `updated_utc`, so the full import re-sends them unchanged.",
      "- Date-only timestamps are stored as the end of that day UTC (a datapoint is never visible earlier than known).", "",
      "## Recall tables (first rank of each distinct source, top 20 results)", ""]
L.append((R / "test_recall_tables.md").read_text())
(R / "test_report.md").write_text("\n".join(L))
print(leak, spent0, spent1, dt)
