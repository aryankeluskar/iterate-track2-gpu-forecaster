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
q = "big median moves caused by one provider repricing or entering the panel, with no news explanation yet"
ra = json.loads(cli("recall", "--as", "scout", q, "--top", "40"))
ev = json.loads(cli("recall", "--as", "scout", "dated web evidence about provider price changes", "--top", "40"))
ev_text = " ".join((r["excerpt"] or "") + r["label"] for r in ev["results"] if r["author"] == "scout").lower()
rows = []
for r in ra["results"]:
    md = r["metadata"] if "metadata" in r else {}
L += ["## (a) `scout` reads what `autopsy` wrote", "", f"`python -m gpuf.memory recall --as scout \"{q}\" --top 40` returned {ra['count']} sources; authors: {sorted({r['author'] for r in ra['results']})}.", "", "```json", json.dumps({**ra, "results": ra["results"][:3]}, indent=1)[:3500], "```", "(first 3 of the rows shown)", ""]
cand = []
for r in ra["results"]:
    if r["author"] != "autopsy" or "Autopsy:" not in (r["label"] or ""):
        continue
    ex = r["excerpt"] or ""
    m1 = re.search(r"Pivotal provider: (\S+)", ex)
    m2 = re.search(r"Autopsy event (\d{4}-\d\d-\d\d) on series (\S+)", ex)
    cand.append((r["source_id"], r["occurred_at"][:10], m1.group(1) if m1 else None, r["label"]))
L += ["Autopsy cases returned, and what scout should search next (an autopsy event whose provider has no scout evidence in memory):", "", "| autopsy source id | date | provider | scout evidence for provider in memory? | search next |", "|---|---|---|---|---|"]
for sid, d, prov, lab in cand:
    if prov and prov != "none":
        has = prov.lower() in ev_text
        L.append(f"| `{sid}` | {d} | {prov} | {'yes' if has else 'no'} | {'-' if has else f'Exa: {prov} price change news {d}'} |")
    else:
        L.append(f"| `{sid}` | {d} | (case, no single provider) | n/a | see text of record |")
L.append("")
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
