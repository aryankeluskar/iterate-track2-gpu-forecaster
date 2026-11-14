"""Run the six test recalls live (as the identities named), replay each offline, write results/test_report.md. Needs PAST_ALLOW_WRITES=1."""
import json, os, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from gpuf import memory as m

RES = ROOT / "experiments/memory/results"
send = json.load(open(RES / "test_send.json"))
A = send["autopsy"]["ids"]; S = send["scout"]["ids"]; E = send["experimenter"]["ids"]
LIMIT = 20
Q = [
 ("Q1", "proposer", None, "Which hypotheses on failure modes of the median have been refuted, and what was the evidence?", "returns the 4 experiment records", lambda src, t: set(E) <= src),
 ("Q2", "proposer", None, "What is the largest unexplained source of last-value loss?", "returns autopsy records 1, 2, 3", lambda src, t: set(A[:3]) <= src),
 ("Q3", "forecaster", "2026-10-06", "Which providers announced price increases before this date?", "returns salad, fireworks, linkedin; not the askgpu Nebius page (timed 10-18)", lambda src, t: set(S[1:4]) <= src and S[0] not in src),
 ("Q4", "forecaster", "2026-10-31", "Nebius H100 on-demand price change", "returns the askgpu Nebius page (record 5); autopsy record 4 listed if present", lambda src, t: S[0] in src),
 ("Q5", "scout", None, "Which dates and providers had big median moves that still lack a news explanation?", "returns autopsy records 3 and 4 and nothing from gpuf-experiments", lambda src, t: {A[2], A[3]} <= src and not any(s.startswith("exp-") for s in src)),
 ("Q6", "forecaster", None, "What did the experiments conclude about breadth?", "returns nothing from gpuf-experiments (access check)", lambda src, t: not any(s.startswith("exp-") for s in src)),
]
def srcs(resp):
    seen = {}
    for r in resp["results"]:
        for s in r["sources"]:
            seen.setdefault(s["sourceId"], (r["rank"], r["artifact"]["kind"], s["occurredAt"], s.get("label"), (s.get("metadata") or {}).get("agent")))
    return seen
u0 = m.usage()
out, md = [], []
for qid, ident, ao, q, passes, chk in Q:
    t0 = time.time(); r = m.recall(q, ident, agent=ident, as_of=ao, limit=LIMIT); dt = time.time() - t0
    s = srcs(r)
    os.environ["PAST_OFFLINE"] = "1"
    r2 = m.recall(q, ident, agent=ident, as_of=ao, limit=LIMIT)
    del os.environ["PAST_OFFLINE"]
    late = [k for k, v in s.items() if ao and v[2][:19] > (ao + "T23:59:59")]
    rec = {"id": qid, "identity": ident, "as_of": ao, "query": q, "seconds": round(dt, 2), "n_results": len(r["results"]), "sources": {k: list(v) for k, v in s.items()},
           "pass": bool(chk(set(s), r)) and not late, "late_sources": late, "offline_replay_identical": r2["results"] == r["results"], "pending": r.get("pending")}
    out.append(rec)
    md.append(f"### {qid}: {ident}" + (f", as_of {ao}" if ao else "") + f"\n\nQuestion: \"{q}\"\n\nExpected: {passes}. **{'PASS' if rec['pass'] else 'FAIL'}**. {rec['n_results']} results in {rec['seconds']} s; offline replay identical: {rec['offline_replay_identical']}.\n\n| first rank | source id | kind of first hit | occurred | label | author |\n|---|---|---|---|---|---|")
    for k, v in s.items():
        md.append(f"| {v[0]} | `{k}` | {v[1]} | {v[2]} | {v[3]} | {v[4]} |")
    md.append("")
u1 = m.usage()
(RES / "test_recall.json").write_text(json.dumps({"recalls": out, "usage_before_recalls": u0, "usage_after": u1}, indent=1))
(RES / "test_recall_tables.md").write_text("\n".join(md))
print(json.dumps([{k: r[k] for k in ("id", "pass", "n_results", "seconds", "late_sources", "offline_replay_identical")} for r in out]))
print(u0["balance"], u1["balance"])
