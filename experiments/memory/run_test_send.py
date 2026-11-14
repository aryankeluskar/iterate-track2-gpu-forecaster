"""Send the 12 test records (3 batches, one per writer) live and poll each ingestion to completion. Needs PAST_ALLOW_WRITES=1."""
import json, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "experiments/memory"))
from gpuf import memory as m
import build_records as b

out = {}
for author, items in b.test_items().items():
    t0 = time.time()
    r = m.ingest(items, agent=author, idempotency_key=f"gpuf-test-{author}-v1")
    t1 = time.time()
    try:
        w = m.wait(r["ingestionId"])
        err = None
    except m.PastError as e:
        w, err = {}, str(e)
    t2 = time.time()
    out[author] = {"ingestionId": r["ingestionId"], "n": len(items), "accept_s": round(t1 - t0, 2), "complete_s": round(t2 - t0, 2),
                   "per_item_s": round((t2 - t0) / len(items), 2), "receipt": {k: r.get(k) for k in ("status", "unchanged")},
                   "final": {k: w.get(k) for k in ("status", "settled", "readiness", "failure")}, "error": err,
                   "ids": [i["id"] for i in items]}
    print(author, json.dumps(out[author]), flush=True)
    if err:
        break
pathlib.Path(ROOT / "experiments/memory/results/test_send.json").write_text(json.dumps(out, indent=1))
