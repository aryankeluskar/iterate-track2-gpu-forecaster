"""Read-only checks of saved artifacts; no project imports or scoring."""

import collections
import datetime
import hashlib
import json
import pathlib
import re
import resource
import subprocess
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[2]
print("checked_at", datetime.datetime.now().astimezone().isoformat())
print("mode: saved artifacts and source only; no scoring, no network")

ledger = [
    json.loads(line)
    for line in (ROOT / "data_out/ledger.jsonl").read_text().splitlines()
    if line.strip()
]
hypotheses = [row for row in ledger if re.fullmatch(r"H\d+b?", row["id"])]
print("hypotheses", len(hypotheses), dict(collections.Counter(r["status"] for r in hypotheses)))
print("other_ledger_rows", [r["id"] for r in ledger if r not in hypotheses])

for name in ("forecast_final_all.csv", "forecast_final_headline.csv"):
    content = (ROOT / "submissions" / name).read_bytes()
    print(name, "sha256", hashlib.sha256(content).hexdigest())

tracked = set(
    subprocess.check_output(
        ["git", "ls-files"], cwd=ROOT, text=True, env={"PATH": "/usr/bin:/bin"}
    ).splitlines()
)
for name in (
    "data_out/ledger.jsonl",
    "data_out/memory_journal.jsonl",
    "data_out/loop_journal.jsonl",
    "data_out/repricing_calendar.jsonl",
    "experiments/loop/cause_labels.parquet",
    "demo/index.html",
):
    print("artifact", name, "exists", (ROOT / name).exists(), "tracked", name in tracked)
project = tomllib.loads((ROOT / "pyproject.toml").read_text())
print("declared_dependencies", project["project"]["dependencies"])

pitch = (ROOT / "experiments/demo/pitch.md").read_text()
for phrase in (
    "never been tuned on",
    "555 series nobody had looked at",
    "declared each validation query before running it",
    "Four directions passed",
    "38 hypotheses",
    "555 price series we never used for any decision",
):
    print("pitch_phrase", repr(phrase), phrase in pitch)

html = (ROOT / "demo/index.html").read_text()
for phrase in (
    "What to keep in mind",
    "departure from our original rule",
    "555 price series we never used for any choice",
):
    print("demo_phrase", repr(phrase), phrase in html)

for name, patterns in {
    "experiments/longrun/code/panel_v2.py": [
        'groupby(["src", "provider"]).price.median()',
    ],
    "src/gpuf/loop.py": [
        'end = "2026-11-06T23:59:59Z"',
        'if not k["eff"] or EVERGREEN.search(k["title"]) or sid in mem_ids',
        '"timestamp": f"{k[\'published\']}T23:59:59Z"',
        '"note": "Rule-based: it lists where the loss is',
        "led = ledger.load()",
    ],
}.items():
    for line_no, line in enumerate((ROOT / name).read_text().splitlines(), 1):
        if any(pattern in line for pattern in patterns):
            print(f"source {name}:{line_no}: {line.strip()}")

for line in (ROOT / "data_out/val_gate.jsonl").read_text().splitlines():
    row = json.loads(line)
    if row["name"] in ("q10_final_headline", "q11_final_nonhead"):
        print(
            "saved_result",
            {key: row[key] for key in ("name", "universe", "n_cells", "skill", "ref_skill")},
        )

for name in ("README.md", "FINDINGS.md", "findings.md"):
    path = ROOT / name
    if path.exists():
        print("doc", name, "inode", path.stat().st_ino)
print("peak_rss_bytes_macos", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
