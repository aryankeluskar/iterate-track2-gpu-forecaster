"""Build to_human/progress.html: a plain-language progress page from the run log and the list of ideas tried. No network.

Usage: PYTHONPATH=src .venv/bin/python experiments/report.py

Numbers come from data_out/trajectory.jsonl (every scored run) and data_out/ledger.jsonl (every idea with its verdict).
The plain wording for each idea is in experiments/plain_ledger.json; an idea without an entry there is shown with the
ledger's own wording. The exact record stays in the ledger and research-log.md.
"""
import base64, datetime as dt, html, io, json, pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[1]
rows = [json.loads(l) for l in (ROOT / "data_out/trajectory.jsonl").read_text().splitlines() if l.strip()]
ledger = [json.loads(l) for l in (ROOT / "data_out/ledger.jsonl").read_text().splitlines() if l.strip()]
plain = json.loads((ROOT / "experiments/plain_ledger.json").read_text())
ledger = [r for r in ledger if not r["id"].startswith("L")]  # rows starting with L are re-runs by the loop tool, not ideas


def png(fig):
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=140, bbox_inches="tight"); plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def has_key(p, k):
    """True if params (nested dicts and lists) set key k to a truthy value anywhere."""
    if isinstance(p, dict):
        return bool(p.get(k)) or any(has_key(v, k) for v in p.values())
    if isinstance(p, list):
        return any(has_key(v, k) for v in p)
    return False


def in_sample(r):
    """Runs kept out of the "best so far" line: the provider simulation with the announcement calendar switched on.
    Its gain comes from two announcements whose timing was read off those same two events, it is zero in the first
    half of the practice dates, it cannot be checked on the held-back weeks, and it is off in the submission (H27)."""
    return has_key(r["params"], "cal")


# Runs on the practice dates (the code calls them "dev"), 37 scored series, 4,278 forecasts each.
dev = [r for r in rows if r["split"] == "dev" and r["universe"] == "rental_headline" and r.get("n_cells") == 4278]
NAMES = {"drift": "organisers' baseline", "calib": "auto-adjusted ranges", "mix": "borrow from similar series",
         "ens": "average of several", "prov": "provider simulation"}
LINES = [(0.169, "our starting model", "#57606a"),
         (0.219, "the earlier model, if it knew in advance whether each price would move", "#1a7f37"),
         (0.262, "...and also which way", "#1a7f37")]
MILESTONES = [("1042", "first batch of ideas"), ("1118", "studied our mistakes"), ("1140", "looked inside the price"),
              ("1147", "many ideas at once"), ("1153", "provider ideas")]

fig, ax = plt.subplots(figsize=(9.5, 4.8))
best, xs, ys, bx, by, lab, ex = -9, [], [], [], [], [], []
for i, r in enumerate(dev):
    if in_sample(r):
        ex.append((i, r["pooled_skill"]))
        continue
    xs.append(i); ys.append(r["pooled_skill"])
    if r["pooled_skill"] > best:
        best = r["pooled_skill"]; bx.append(i); by.append(best); lab.append(NAMES.get(r["method"], r["method"]))
ax_top = max(0.285, max([y for _, y in ex] + ys) + 0.035)
ax.scatter(xs, ys, s=9, color="#9aa5b1", label="one test")
ax.step(bx + [len(dev)], by + [by[-1]], where="post", color="#1f6feb", lw=2, label=f"best so far (ends at {by[-1]:.3f})")
if ex:
    ax.scatter([x for x, _ in ex], [y for _, y in ex], s=46, facecolors="none", edgecolors="#bc4c00", linewidths=1.6, zorder=5,
               label="not counted, and not in our submission")
    for x, y in ex:
        ax.annotate(f"announcement calendar switched on ({y:.3f}):\nrests on two events, not in our submission", (x, y),
                    textcoords="offset points", xytext=(-9, -3), fontsize=7.5, color="#bc4c00", ha="right", va="center")
prev = None
for x, y, l in zip(bx, by, lab):
    if l != prev and l != NAMES["drift"]:
        last = x == bx[-1]
        ax.annotate(l, (x, y), textcoords="offset points", xytext=(-3 if last else 3, 5), fontsize=7, ha="right" if last else "left")
    prev = l
drift = next(r["pooled_skill"] for r in dev if r["method"] == "drift")
ax.axhline(drift, color="#d1242f", ls="--", lw=1)
ax.text(8, drift - 0.013, "organisers' baseline (the one to beat)", color="#d1242f", fontsize=7.5)
for y, name, col in LINES:
    below = name == "our starting model"  # the blue line sits just above this one
    ax.axhline(y, color=col, ls=":", lw=1.2)
    ax.text(len(dev) * 0.62 if below else len(dev) * 0.30, y - 0.012 if below else y + 0.003, name, color=col, fontsize=7.5, ha="left")
marks = {}
for hhmm, name in MILESTONES:  # dotted vertical line at the first test logged after each stage began
    i = next((k for k, r in enumerate(dev) if r["experiment_id"][9:13] >= hhmm), len(dev))
    marks.setdefault(i, []).append(name)
for i, names in marks.items():
    ax.axvline(i - 0.5, color="#8250df", ls=":", lw=1)
    ax.text(i - 0.2, 0.03, "\n".join(names), color="#8250df", fontsize=7, rotation=90, va="bottom", ha="left", linespacing=1.1)
ax.set_xlim(-3, len(dev) + 8)
ax.set_xlabel("each test on the practice dates, in the order we ran them")
ax.set_ylabel("score (0 = no better than assuming\nprices stay where they are)")
ax.set_ylim(0.0, ax_top); ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3)
traj = png(fig)
BEST_END = by[-1]

WORD = {"supported": ("Worked", "#1a7f37"), "refuted": ("Didn't work", "#d1242f"), "not_significant": ("No clear effect", "#9a6700"),
        "untestable": ("Couldn't test", "#57606a"), "running": ("Still running", "#57606a"), "registered": ("Not tried yet", "#57606a")}
# A few verdicts need a different word in plain language than the ledger's status, because the plain idea is worded differently.
OVERRIDE = {"H13": "Mostly no", "H21": "Worked, with a caveat", "H27": "Worked on practice dates only", "H28": "Worked, with a caveat",
            "H36": "Ranges yes, proven accuracy no", "H37": "Mostly, not fully"}
counts = {}
for r in ledger:
    w = WORD[r["status"]][0]; counts[w] = counts.get(w, 0) + 1
trs = ""
for n, r in enumerate(ledger, 1):
    p = plain.get(r["id"], {})
    word, col = WORD[r["status"]]
    trs += (f"<tr><td class='k'>{n}</td><td>{html.escape(p.get('idea') or r.get('claim', ''))}</td>"
            f"<td style='color:{col};white-space:nowrap'><b>{html.escape(OVERRIDE.get(r['id'], word))}</b></td>"
            f"<td>{html.escape(p.get('result') or r.get('result', '') or '')}</td></tr>")
tally = ", ".join(f"{counts[w]} {w.lower()}" for w in ("Worked", "Didn't work", "No clear effect", "Couldn't test") if w in counts)

page = f"""<!doctype html><meta charset="utf-8"><title>GPU price forecaster: where we are</title>
<style>body{{font:15px/1.55 -apple-system,Segoe UI,sans-serif;max-width:980px;margin:24px auto;padding:0 16px;color:#1f2328}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #d0d7de;padding:7px 8px;vertical-align:top;text-align:left;font-size:14px}}
h1{{font-size:23px;margin-bottom:4px}}h2{{font-size:18px;margin-top:30px}}img{{max-width:100%}}.k{{color:#57606a}}
.box{{background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;padding:10px 14px}}li{{margin:3px 0}}</style>
<h1>GPU price forecaster: where we are</h1>
<p class="k">Updated {dt.datetime.now().strftime('%a %d %b, %H:%M')}. {len(rows)} tests run, {len(ledger)} ideas tried.</p>

<h2>The short version</h2>
<ul>
<li><b>It works.</b> On three weeks of prices we held back and never built on, our forecaster scores 0.214. The organisers' baseline scores 0.084.</li>
<li><b>Why it works.</b> Each published GPU price is just the middle of a short list of offers from providers. It moves when a provider near
the middle changes its price, or when a provider joins or leaves the list. We forecast that list, not the price line.</li>
<li><b>How we got there.</b> We tried {len(ledger)} ideas: {tally}. All of them are in the table below, including the ones that failed.</li>
<li><b>What to keep in mind.</b> Sunday's scoring is one single date, so a bad week is possible. An outside check also found that some
of our held-back-week claims were too confident. Details are in the table (last row) and in <code>to_human/track2_feasibility.md</code>.</li>
</ul>

<div class="box"><b>Reading the scores.</b> The score says how much better we are than simply assuming every price stays where it is.
Zero means no better, higher is better. "Practice dates" are 18 August to 6 October, which we were free to look at. "Held-back weeks"
are 13 to 30 October, which we only looked at to check an idea once it was finished. The "baseline" is the simple method the organisers
ask everyone to beat.</div>

<h2>Progress on the practice dates</h2><img src="{traj}">
<p class="k">Each grey dot is one test. The blue line is the best score so far and ends at {BEST_END:.3f}. The orange circle is one test we
do not count: the provider simulation with the calendar of announced price changes switched on. Its jump comes from just two announcements
(Nebius on 1 October and Jarvislabs on 5 October), we tuned its timing on those same two, and we could not check it on the held-back weeks.
It is switched off in what we submit. Everything on this chart is from the practice dates; results on the held-back weeks are in the table.</p>

<h2>Everything we tried</h2>
<p class="k">Gains like "+0.03" are in the same score as above. The exact record, with every number and its source, is in
<code>data_out/ledger.jsonl</code> and <code>research-log.md</code>.</p>
<table><tr><th></th><th>The idea</th><th>Did it work?</th><th>What happened</th></tr>{trs}</table>"""
out = ROOT / "to_human/progress.html"; out.parent.mkdir(exist_ok=True); out.write_text(page)
print(out, len(page))
