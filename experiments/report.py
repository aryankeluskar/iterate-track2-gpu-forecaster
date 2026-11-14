"""Build to_human/progress.html from the trajectory, the ledger and the validation log. No network.

Usage: PYTHONPATH=src .venv/bin/python experiments/report.py
"""
import base64, datetime as dt, html, io, json, pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[1]
rows = [json.loads(l) for l in (ROOT / "data_out/trajectory.jsonl").read_text().splitlines() if l.strip()]
ledger = [json.loads(l) for l in (ROOT / "data_out/ledger.jsonl").read_text().splitlines() if l.strip()]


def png(fig):
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=140, bbox_inches="tight"); plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


dev = [r for r in rows if r["split"] == "dev" and r["universe"] == "rental_headline" and r.get("n_cells") == 4278]
TARGETS = [(0.169, "reference model (mix)", "#57606a"), (0.219, "hindsight: knowing whether the price moves", "#1a7f37"),
           (0.262, "hindsight: knowing whether and which way it moves", "#1a7f37")]
MILESTONES = [("1042", "round 1: nine methods"), ("1118", "failure analysis"), ("1140", "round 2: offer panel"),
              ("1147", "round 3: breadth swarm"), ("1153", "round 4: providers")]
ax_top = 0.285
fig, ax = plt.subplots(figsize=(9.5, 4.4))
best, xs, ys, bx, by, lab = -9, [], [], [], [], []
for i, r in enumerate(dev):
    xs.append(i); ys.append(r["pooled_skill"])
    if r["pooled_skill"] > best:
        best = r["pooled_skill"]; bx.append(i); by.append(best); lab.append(r["method"])
ax.scatter(xs, ys, s=9, color="#9aa5b1", label="each scored run")
ax.step(bx + [len(dev)], by + [by[-1]], where="post", color="#1f6feb", lw=2, label="best so far")
for x, y, l in zip(bx, by, lab):
    ax.annotate(l, (x, y), textcoords="offset points", xytext=(3, 5), fontsize=7)
drift = next(r["pooled_skill"] for r in dev if r["method"] == "drift")
ax.axhline(drift, color="#d1242f", ls="--", lw=1); ax.text(len(dev) * 0.30, drift + 0.003, "drift baseline (the bar to beat)", color="#d1242f", fontsize=7.5)
# Targets: dotted horizontal lines. Hindsight bounds come from runs/failure/decomp.txt (the blend with perfect knowledge).
for y, name, col in TARGETS:
    ax.axhline(y, color=col, ls=":", lw=1.2); ax.text(len(dev) * 0.30, y + 0.003, name, color=col, fontsize=7.5, ha="left")
# Milestones: dotted vertical lines at the first run logged after each round started (local time in the run id).
marks = {}
for hhmm, name in MILESTONES:
    i = next((k for k, r in enumerate(dev) if r["experiment_id"][9:13] >= hhmm), len(dev))
    marks.setdefault(i, []).append(name)
for i, names in marks.items():
    ax.axvline(i - 0.5, color="#8250df", ls=":", lw=1)
    ax.text(i - 0.2, 0.03, "\n".join(names), color="#8250df", fontsize=7, rotation=90, va="bottom", ha="left", linespacing=1.1)
ax.set_xlim(-3, len(dev) + 8)
ax.set_xlabel("scored run on the development period (in order)"); ax.set_ylabel("pooled skill against last value")
ax.set_ylim(0.0, ax_top); ax.legend(frameon=False, fontsize=8, loc="lower center")
traj = png(fig)

counts = {}
for r in ledger:
    counts[r["status"]] = counts.get(r["status"], 0) + 1
color = {"supported": "#1a7f37", "refuted": "#d1242f", "not_significant": "#9a6700", "running": "#57606a", "untestable": "#57606a", "registered": "#57606a"}
trs = "".join(
    f"<tr><td>{html.escape(r['id'])}</td><td style='color:{color[r['status']]}'><b>{r['status'].replace('_', ' ')}</b></td>"
    f"<td>{html.escape(r.get('claim', ''))}</td><td>{html.escape(r.get('result', '') or '')}</td></tr>" for r in ledger)
extra = (ROOT / "to_human/notes.html").read_text() if (ROOT / "to_human/notes.html").exists() else ""
page = f"""<!doctype html><meta charset="utf-8"><title>Track 2 progress</title>
<style>body{{font:14px/1.5 -apple-system,Segoe UI,sans-serif;max-width:980px;margin:24px auto;padding:0 16px;color:#1f2328}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #d0d7de;padding:6px 8px;vertical-align:top;text-align:left;font-size:13px}}
h1{{font-size:22px}}h2{{font-size:17px;margin-top:28px}}img{{max-width:100%}}.k{{color:#57606a}}</style>
<h1>GPU price scientist: progress</h1>
<p class="k">Built {dt.datetime.now().strftime('%a %d %b %H:%M')} from {len(rows)} logged runs and {len(ledger)} hypotheses
({', '.join(f'{v} {k.replace("_", " ")}' for k, v in sorted(counts.items()))}).</p>
{extra}
<h2>Skill on the development period, run by run</h2><img src="{traj}">
<h2>Hypothesis ledger</h2><table><tr><th>id</th><th>status</th><th>claim</th><th>result</th></tr>{trs}</table>"""
out = ROOT / "to_human/progress.html"; out.parent.mkdir(exist_ok=True); out.write_text(page)
print(out, len(page))
