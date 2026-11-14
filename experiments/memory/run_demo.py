"""Cross-agent demo through the real CLI (live). Writes results/cross_agent_demo.md. Needs PAST_ALLOW_WRITES=1."""
import json, os, pathlib, re, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PAST_ALLOW_WRITES": "1"}
def cli(*a):
    p = subprocess.run([sys.executable, "-m", "gpuf.memory", *a], capture_output=True, text=True, env=env, cwd=ROOT)
    assert p.returncode == 0, p.stderr
    return p.stdout
L = ["# Cross-agent use of the shared memory (live output)", "", "Every block below is the unedited stdout of `python -m gpuf.memory ...` against past.dev, or a table computed from it.", ""]

# (a) scout reads autopsy
import datetime as dt
q = "Autopsy event: one-day move of the median caused by a provider repricing or entering the panel, pivotal provider"
ra = json.loads(cli("recall", "--as", "scout", q, "--top", "40"))
eq = "Web evidence: provider announced GPU price increase, quoted sentence, URL"
ev = json.loads(cli("recall", "--as", "scout", eq, "--top", "40"))
evid = [r for r in ev["results"] if r["author"] == "scout"]
L += ["## (a) `scout` reads what `autopsy` wrote", "", f"`python -m gpuf.memory recall --as scout \"{q}\" --top 40` returned {ra['count']} sources; authors: {sorted({r['author'] for r in ra['results']})}. First 2 rows:", "", "```json", json.dumps(ra["results"][:2], indent=1), "```", "",
      f"`python -m gpuf.memory recall --as scout \"{eq}\" --top 40` returned {len(evid)} scout evidence sources already in memory: " + ", ".join(f"`{r['source_id']}` ({r['label'].split(': ')[1]}, {r['occurred_at'][:10]})" for r in evid) + ".", ""]
def covered(prov, d):
    day = dt.date.fromisoformat(d)
    for r in evid:
        t = dt.date.fromisoformat(r["occurred_at"][:10])
        if re.search(r"\b" + re.escape(prov) + r"\b", (r["excerpt"] or "").lower()) and -14 <= (day - t).days <= 45:
            return r["source_id"]
L += ["Autopsy events returned, with whether scout evidence for the provider exists within 45 days before the move (or 14 days after):", "", "| autopsy source id | date | pivotal / involved providers | scout evidence in memory | search next |", "|---|---|---|---|---|"]
todo = []
for r in ra["results"]:
    ex = r["excerpt"] or ""
    m1 = re.search(r"Pivotal provider: (\S+)", ex)
    if r["author"] != "autopsy" or not m1:
        continue
    d = r["occurred_at"][:10]
    provs = [x for x in m1.group(1).split(",") if x != "none"]
    cov = {p: covered(p, d) for p in provs}
    miss = [p for p, c in cov.items() if not c]
    L.append(f"| `{r['source_id']}` | {d} | {', '.join(provs)} | {', '.join(f'{p}: {c}' for p, c in cov.items() if c) or 'none'} | " + (f"Exa: `{', '.join(miss)} price change {d}`" if miss else "-") + " |")
    todo += [(p, d) for p in miss]
L += ["", "Next searches for scout (distinct provider, first date): " + "; ".join(f"{p} {d}" for p, d in sorted({p: min(d for q_, d in todo if q_ == p) for p, _ in todo}.items())) + ".", ""]
# (b) proposer brief
topic = "upper tail under-covered at 7 days"
bj = json.loads(cli("brief", "--as", "proposer", topic, "--top", "4"))
L += ["## (b) `proposer` briefs itself", "", f"`python -m gpuf.memory brief --as proposer \"{topic}\" --top 4`, briefing text:", "", "```", bj["briefing"], "```", "",
      "| section | source id | author | occurred |", "|---|---|---|---|"]
for s in bj["sections"]:
    for it in s["items"]:
        L.append(f"| {s['key']} | `{it['source_id']}` | {it['author']} | {it['occurred_at']} |")
authors = {s["key"]: {i["author"] for i in s["items"]} for s in bj["sections"]}
L += ["", f"Check: refuted section authors {authors['refuted']}, failures {authors['failures']}, evidence {authors['evidence']}. Contains autopsy failure modes, scout evidence and experimenter hypotheses: {authors['refuted'] == {'experimenter'} and authors['failures'] == {'autopsy'} and authors['evidence'] == {'scout'}}.", ""]
# (c) forecaster as of
qc = "announced price increases effective soon"
c1 = json.loads(cli("recall", "--as", "forecaster", "--as-of", "2026-10-06", qc, "--top", "10"))
c2 = json.loads(cli("recall", "--as", "forecaster", "--as-of", "2026-10-31", qc, "--top", "10"))
late = [r["source_id"] for r in c1["results"] if r["occurred_at"] > "2026-10-06T23:59:59Z"]
L += ["## (c) `forecaster` at forecast origin 2026-10-06", "", f"`python -m gpuf.memory recall --as forecaster --as-of 2026-10-06 \"{qc}\" --top 10`", "", "| rank | source id | author | occurred | label |", "|---|---|---|---|---|"]
L += [f"| {r['rank']} | `{r['source_id']}` | {r['author']} | {r['occurred_at']} | {r['label']} |" for r in c1["results"]]
L += ["", f"Anything dated after 2026-10-06: {late or 'none'}. Evidence rows returned: " + ", ".join(r["source_id"] for r in c1["results"] if r["author"] == "scout") + ".", "",
      "Same question at as-of 2026-10-31 (for contrast; the askgpu Nebius page, timed 2026-10-18, may now appear):", "", "| rank | source id | author | occurred |", "|---|---|---|---|"]
L += [f"| {r['rank']} | `{r['source_id']}` | {r['author']} | {r['occurred_at']} |" for r in c2["results"]]
L += ["", f"The page `scout-f4c32699` (askgpu, Nebius, timed 2026-10-18) is {'absent at 2026-10-06 and present at 2026-10-31' if not any(r['source_id']=='scout-f4c32699' for r in c1['results']) and any(r['source_id']=='scout-f4c32699' for r in c2['results']) else 'see tables'}.", ""]
(ROOT / "experiments/memory/results/cross_agent_demo.md").write_text("\n".join(L))
print("ok", late, authors)
