"""Full import: one data point per record, stable ids (re-sending updates, never duplicates). Needs PAST_ALLOW_WRITES=1."""
import json, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "experiments/memory"))
from gpuf import memory as m, ledger
import build_records as b

u0 = m.usage()
batches = {"experimenter": ("gpuf-experiments", [m.ledger_item(e) for e in ledger.load()]),
           "autopsy": ("gpuf-failures", b.mode_items() + b.event_items()),
           "scout": ("gpuf-evidence", b.attribution_items() + [b.prweb_item()])}
out = {}
for author, (aud, items) in batches.items():
    assert all(i["audience"] == aud and i["identity"] == author for i in items)
    t0 = time.time()
    r = m.ingest(items, agent=author)
    w = m.wait(r["ingestionId"])
    out[author] = {"audience": aud, "sent": len(items), "completed": w["status"] == "completed" and w.get("settled"),
                   "unchanged": sum(1 for i in r.get("items", []) if i.get("unchanged")), "ingestionId": r["ingestionId"],
                   "seconds": round(time.time() - t0, 1), "failure": w.get("failure")}
    print(author, json.dumps(out[author]), flush=True)
u1 = m.usage()
out["credits_used"] = u1["balance"]["spent"] - u0["balance"]["spent"]; out["balance_left"] = u1["balance"]["left"]
(ROOT / "experiments/memory/results/import_summary.json").write_text(json.dumps(out, indent=1))
print(out["credits_used"], out["balance_left"])
