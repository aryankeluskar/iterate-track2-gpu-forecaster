"""Self-contained demo page built only from files already in the repo and the data pack.

python -m gpuf.demo [--out demo/index.html]

Reads (never writes) the submission files, the validation gate log, the hypothesis ledger, the failure
analysis, the index-quality card, the repricing calendar, the Exa attribution, the past.dev journal and the
long-run report, plus the offer panel from the pack for prices dated on or before 6 November 2026. No
network, no scoring, no validation data. Output is one HTML file with inline CSS, JavaScript and data; the
same inputs give the same bytes.
"""
from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import hashlib
import html
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, panel

ROOT = data.ROOT
ORIGIN = dt.date(2026, 11, 6)
O = ORIGIN.toordinal()
WINDOW = 60
OUT = ROOT / "demo" / "index.html"

P = {
    "headline": ROOT / "submissions/forecast_final_headline.csv",
    "all": ROOT / "submissions/forecast_final_all.csv",
    "members": ROOT / "submissions/forecast_final_all_members.csv",
    "val_gate": ROOT / "data_out/val_gate.jsonl",
    "val_log": ROOT / "data_out/val_query_log.jsonl",
    "ledger": ROOT / "data_out/ledger.jsonl",
    "loss": ROOT / "experiments/autopsy2/results/loss_by_cause.csv",
    "loss_protocol": ROOT / "experiments/autopsy2/protocol.yaml",
    "card": ROOT / "experiments/insight/results/t1_index_quality_card.csv",
    "rates": ROOT / "experiments/insight/results/t0_provider_reprice_rates.csv",
    "insight_code": ROOT / "experiments/insight/analysis.py",
    "calendar": ROOT / "data_out/repricing_calendar.jsonl",
    "cal_check": ROOT / "experiments/calendar/results/partb_summary.json",
    "exa_head": ROOT / "experiments/exa_attrib/results/headline.json",
    "journal": ROOT / "data_out/memory_journal.jsonl",
    "longrun": ROOT / "experiments/longrun/results/longrun.md",
    "longrun_paths": ROOT / "experiments/longrun/results/v2_t2_scenario_paths.csv",
    "protocol": ROOT / "EVAL_PROTOCOL.md",
    "scout": ROOT / "src/gpuf/scout.py",
    "manifest": data.PACK / "MANIFEST.sha256",
}

EVIDENCE = [
    ("Each scored median is reproduced exactly from the offers in the pack; every jump is a repriced offer near the middle or an offer entering or leaving (H11)",
     ["src/gpuf/panel.py", "experiments/autopsy/results", "data_out/ledger.jsonl"]),
    ("Evaluation protocol, splits, leak rule and the three amendments, each committed before the runs it governs",
     ["EVAL_PROTOCOL.md", "research-log.md"]),
    ("Validation results, with every query logged", ["data_out/val_gate.jsonl", "data_out/val_query_log.jsonl"]),
    ("Loss by cause across the four systems", ["experiments/autopsy2/results/loss_by_cause.csv", "experiments/autopsy2/protocol.yaml"]),
    ("All hypotheses and verdicts", ["data_out/ledger.jsonl", "src/gpuf/ledger.py"]),
    ("Provider simulator and the one-offer fragility tails", ["src/gpuf/methods/prov.py", "src/gpuf/methods/fragility.py"]),
    ("The submitted forecaster and its files", ["src/gpuf/methods/final.py", "reproduce.sh", "submissions/forecast_final_headline.csv",
                                                 "submissions/forecast_final_all.csv", "submissions/forecast_final_all_members.csv"]),
    ("Index-quality card and provider repricing rates", ["experiments/insight/results/t1_index_quality_card.csv",
                                                         "experiments/insight/results/t0_provider_reprice_rates.csv", "experiments/insight/results/insight.md"]),
    ("Repricing calendar found by Exa search, and its check against the panel", ["data_out/repricing_calendar.jsonl",
                                                                                "experiments/calendar/results/partb_summary.json",
                                                                                "experiments/calendar/results/b1_panel_check.csv"]),
    ("Exa calls and cached responses", ["src/gpuf/scout.py", "data_out/exa_cache"]),
    ("Were large repricings announced ahead (Exa attribution); pricing-policy label", ["experiments/exa_attrib/results/attribution.md",
                                                                                     "experiments/policy/results/score_report.txt"]),
    ("Shared memory (past.dev): client, journal of every call, who writes and reads what", ["src/gpuf/memory.py", "data_out/memory_journal.jsonl",
                                                                                          "experiments/memory/README_memory.md"]),
    ("The 2 to 3 year view", ["experiments/longrun/results/longrun.md", "experiments/longrun/results/v2_t2_scenario_paths.csv"]),
    ("The whole story with timestamps", ["research-log.md"]),
]

COLLECTOR = {"fastgpu_daily": "FastGPU", "gpurentalprices": "gpurentalprices.com", "afhubbard": "GPU Price Tracker"}
CLASS = {"neocloud_rate_card": "neocloud rate card", "neocloud_spot": "neocloud spot", "marketplace_ask": "marketplace ask",
         "hyperscaler_spot": "hyperscaler spot", "hyperscaler_list": "hyperscaler list"}
TIER = {"on_demand": "on-demand", "spot": "spot"}
CAUSE = {"none": "no move (cost of interval width)", "dynamic_reprice": "a frequently repricing provider moved",
         "announced_oneoff": "one-off repricing, announced", "unannounced_oneoff": "one-off repricing, not announced",
         "entry": "an offer entered", "exit": "an offer left", "marketplace_ask": "marketplace asks",
         "hyperscaler_spot": "hyperscaler spot (no offer panel)"}
SYSTEMS = [("S0", "drift (baseline)"), ("S1", "reference model"), ("S2", "earlier blend"), ("S3", "current blend")]
STATUS = {"supported": "supported", "refuted": "refuted", "not_significant": "not significant", "untestable": "untestable"}
DEFAULT_SID = "gpurentalprices.neocloud_rate_card.B300.on_demand.median"
PRESETS = [
    (DEFAULT_SID, "B300 rate card: a frequent repricer climbs through the middle"),
    ("gpurentalprices.neocloud_rate_card.A100_40GB.on_demand.median", "A100 40GB rate card: one provider sets the median"),
    ("fastgpu_daily.neocloud_spot.B200.spot.median", "B200 spot: four offers, one of them climbing"),
]


# ---------------------------------------------------------------- helpers
def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def jl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


esc = html.escape
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)|(https?://[^\s<>\"'|]+)")


def _fmt_inline(s: str) -> str:
    s = esc(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)


def inline(s: str) -> str:
    """Markdown-ish inline text to HTML; every URL becomes an anchor, so no URL appears outside an href."""
    out, i = [], 0
    for m in LINK.finditer(s):
        out.append(_fmt_inline(s[i:m.start()]))
        if m.group(2):
            out.append(f'<a href="{esc(m.group(2))}">{_fmt_inline(m.group(1))}</a>')
        else:
            u = m.group(3)
            tail = re.search(r"[.,;:)\]]+$", u)
            t = tail.group(0) if tail else ""
            u = u[: len(u) - len(t)]
            out.append(f'<a href="{esc(u)}">{esc(u)}</a>{esc(t)}')
        i = m.end()
    out.append(_fmt_inline(s[i:]))
    return "".join(out)


def md_table(rows: list[str]) -> str:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], [c for c in cells[2:]]
    num = re.compile(r"^[\s*~+\-−0-9.,%x()kUSD/–]+$")
    def td(c, tag):
        cls = ' class="n"' if tag == "td" and num.match(c) and any(ch.isdigit() for ch in c) else ""
        return f"<{tag}{cls}>{inline(c)}</{tag}>"
    return ("<div class=\"tw\"><table><thead><tr>" + "".join(td(c, "th") for c in head) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(td(c, "td") for c in r) + "</tr>" for r in body) + "</tbody></table></div>")


def md_block(text: str) -> str:
    lines, out, i = text.splitlines(), [], 0
    while i < len(lines):
        l = lines[i]
        if not l.strip() or l.startswith("!["):
            i += 1
        elif l.startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.append(md_table(lines[i:j]))
            i = j
        elif re.match(r"^\s*(-|\d+\.)\s", l):
            tag = "ol" if re.match(r"^\s*\d+\.", l) else "ul"
            items = []
            while i < len(lines) and re.match(r"^\s*(-|\d+\.)\s", lines[i]):
                items.append(re.sub(r"^\s*(-|\d+\.)\s+", "", lines[i]))
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
        elif l.startswith("#"):
            out.append(f"<h4>{inline(l.lstrip('#').strip())}</h4>")
            i += 1
        else:
            j = i
            while j < len(lines) and lines[j].strip() and not re.match(r"^(\||#|!\[|\s*(-|\d+\.)\s)", lines[j]):
                j += 1
            out.append("<p>" + inline(" ".join(lines[i:j])) + "</p>")
            i = j
    return "\n".join(out)


def md_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    title, secs, cur, buf = "", [], None, []
    for l in text.splitlines():
        if l.startswith("# ") and not title:
            title = l[2:].strip()
        elif l.startswith("## "):
            if cur is not None:
                secs.append((cur, "\n".join(buf)))
            cur, buf = l[3:].strip(), []
        elif cur is not None:
            buf.append(l)
    if cur is not None:
        secs.append((cur, "\n".join(buf)))
    return title, secs


def f3(x: float) -> str:
    return f"{x:.3f}"


def sgn(x: float, d: int = 3) -> str:
    return f"{x:+.{d}f}".replace("-", "−")


def pv(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def ci(c: list[float], d: int = 3) -> str:
    return f"{sgn(c[0], d)} to {sgn(c[1], d)}"


def series_name(sid: str) -> str:
    src, cls, gpu, tier, _ = sid.split(".")
    return f"{gpu.replace('_', ' ')}, {CLASS.get(cls, cls)}, {TIER.get(tier, tier)} ({COLLECTOR.get(src, src)})"


def nice_date(d: dt.date) -> str:
    return f"{d.day} {d:%b} {d.year}"


def thresholds() -> tuple[float, float]:
    m = re.search(r"DYN, STATIC = ([\d.]+), ([\d.]+)", P["insight_code"].read_text())
    return float(m.group(1)), float(m.group(2))


def klass(rate, dyn, static) -> str:
    if rate is None or (isinstance(rate, float) and np.isnan(rate)):
        return "na"
    return "dyn" if rate >= dyn else "sta" if rate < static else "mid"


def r4(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 4)


# ---------------------------------------------------------------- explorer data
def af_rows(models: list[str]) -> pd.DataFrame:
    import duckdb
    af = data.PACK / "rental_observations" / "source_id=afhubbard"
    lo = dt.date.fromordinal(O - 22).isoformat()
    q = f"""select cast(dt as date) d, gpu_model, provider,
               coalesce(region_raw,'')||'|'||coalesce(sku_raw,'')||'|'||coalesce(cast(gpu_count as varchar),'') k,
               usd_per_gpu_hour price
            from read_parquet('{af}/*/*.parquet', hive_partitioning=false)
            where instrument_class='hyperscaler_spot' and pricing_tier='spot' and usd_per_gpu_hour is not null
              and cast(dt as date) between date '{lo}' and date '{ORIGIN.isoformat()}'
              and gpu_model in ({",".join("'" + m + "'" for m in models)})"""
    a = duckdb.sql(q).df()
    a["day"] = pd.to_datetime(a.d).map(lambda x: x.toordinal()).astype(np.int64)
    return a


def explorer_data() -> dict:
    dyn, static = thresholds()
    fc = pd.read_csv(P["headline"])
    sids = sorted(fc.series_id.unique(), key=lambda s: (s.split(".")[0], s.split(".")[1], s.split(".")[2]))
    card = pd.read_csv(P["card"]).set_index("series_id")
    rates = pd.read_csv(P["rates"])
    rate21 = {(r.src, r.provider): r.rate21 for r in rates.itertuples()}
    mem = pd.read_csv(P["members"], dtype=str, keep_default_na=False)
    mem = mem[mem.series_id.isin(sids)]
    days = list(range(O - WINDOW + 1, O + 1))
    af_ids = [s for s in sids if not panel.supported(s)]
    A = af_rows([panel.parse_sid(s)[2] for s in af_ids]) if af_ids else None
    sd = pd.read_csv(data.build_series()[0], usecols=["series_id", "date", "value"])
    sd = sd[sd.series_id.isin(af_ids)]
    out = []
    for sid in sids:
        src = sid.split(".")[0]
        f = fc[fc.series_id == sid].sort_values("horizon_days")
        c = card.loc[sid]
        m = mem[mem.series_id == sid].sort_values("horizon_days")
        s = {"id": sid, "name": series_name(sid),
             "fc": [[int(r.horizon_days), r4(r.q10), r4(r.q50), r4(r.q90)] for r in f.itertuples()],
             "card": {"offers": int(c.n_offers), "providers": int(c.n_providers), "mid": c.mid_providers,
                      "mid_rate21": r4(c.mid_rate21), "mid_class": c.mid_class, "frag": r4(c.fragility_pct),
                      "pfrag": r4(c.provider_fragility_pct), "pt": r4(c.max_pass_through), "pt_provider": c.pass_through_provider,
                      "gap": r4(c.neighbour_gap_pct), "median": r4(c["median"]), "alone": not bool(c.do_not_use_alone),
                      "moved60": r4(c.move_share_60d)},
             "members": list(dict.fromkeys(x for v in m.members_used for x in re.split(r"[+|]", v) if x)) or None,
             "gated": sorted({int(r.horizon_days) for r in m.itertuples() if r.gated == "1"})}
        if src != "afhubbard":
            o = panel.offers(sid, O)
            o = o[o.day > O - WINDOW]
            keys = sorted(o.key.unique(), key=lambda k: (k.split("|")[0], k))
            nprov = o.groupby("provider").key.nunique()
            offers = []
            for k in keys:
                g = o[o.key == k].set_index("day").price
                prov = k.split("|")[0]
                parts = [x for x in k.split("#")[0].split("|")[1:] if x]
                label = prov if nprov[prov] == 1 else f"{prov} ({', '.join(parts) or 'offer ' + str(int(k.split('#')[1]) + 1)})"
                if nprov[prov] > 1 and len(label) > 40:
                    label = label[:39] + "…"
                rt = rate21.get((src, prov))
                offers.append({"p": prov, "l": label, "c": klass(rt, dyn, static), "r": r4(rt),
                               "v": [r4(g.get(d)) for d in days]})
            med = o.groupby("day").price.median()
            s.update(kind="panel", offers=offers, med=[r4(med.get(d)) for d in days],
                     maxn=int(o.groupby("day").size().max()))
        else:
            gm = panel.parse_sid(sid)[2]
            a = A[A.gpu_model == gm]
            last = a[a.day == O]
            daily = a.groupby(["provider", "k", "day"]).price.median().reset_index().sort_values(["provider", "k", "day"])
            daily["pd"] = daily.groupby(["provider", "k"]).day.shift(1)
            daily["pp"] = daily.groupby(["provider", "k"]).price.shift(1)
            dc = daily[(daily.day - daily.pd == 1) & (daily.day > O - 21)]
            groups = []
            for prov, g in last.groupby("provider"):
                x = dc[dc.provider == prov]
                rt = float((x.price != x.pp).mean()) if len(x) else None
                q = np.percentile(g.price.values, [10, 50, 90])
                groups.append({"p": prov, "n": int(len(g)), "q": [r4(v) for v in q], "c": klass(rt, dyn, static), "r": r4(rt),
                               "lo": r4(g.price.min()), "hi": r4(g.price.max())})
            h = sd[sd.series_id == sid].assign(day=lambda x: pd.to_datetime(x.date).map(lambda d: d.toordinal())).set_index("day").value
            s.update(kind="af", groups=groups, med=[r4(h.get(d)) for d in days], rows=int(len(last)),
                     origin_median=r4(float(np.median(last.price.values))))
        out.append(s)
    return {"days": [dt.date.fromordinal(d).isoformat() for d in days],
            "labels": [f"{dt.date.fromordinal(d).day} {dt.date.fromordinal(d):%b}" for d in days],
            "default": DEFAULT_SID, "dyn": dyn, "static": static, "series": out,
            "presets": [[s, t] for s, t in PRESETS if s in sids]}


# ---------------------------------------------------------------- sections
def val_section(gate: list[dict], log: list[dict], nhead: int) -> tuple[str, dict]:
    g = {r["name"]: r for r in gate}
    keep = [r for r in gate if r["name"].split("_")[0] in ("q6", "q7", "q8", "q9")]
    ps = sorted((r["p_one_sided"], r["name"]) for r in keep)
    m, passed, kmax = len(ps), set(), 0
    for i, (p, n) in enumerate(ps, 1):
        if p <= 0.10 * i / m:
            kmax = i
    passed = {n for _, n in ps[:kmax]}
    # round 1 (queries 1 to 5): the first distinct candidate configurations on validation headline
    seen, r1 = [], []
    for x in log:
        if x["split"] != "val" or x["universe"] != "rental_headline" or x["method"] in ("drift",) or "role" in x["params"]:
            continue
        key = json.dumps([x["method"], x["params"]], sort_keys=True)
        if key in seen:
            continue
        seen.append(key)
        r1.append(x)
        if len(r1) == 5:
            break
    drift = next(x["result"]["pooled_skill"] for x in log if x["split"] == "val" and x["universe"] == "rental_headline" and x["method"] == "drift")

    def label(method, params):
        if method == "ens":
            alias = {"replay": "Chronos width", "chronos": "Chronos width"}
            names = [alias.get(mm[0], mm[0]) for mm in params["members"]]
            parts = []
            for n in dict.fromkeys(names):
                parts.append(f"{names.count(n)} variants of {n}" if names.count(n) > 1 else n)
            return "blend of " + " + ".join(parts)
        if method == "chronos":
            return "Chronos width around the last value"
        if method == "fragility":
            return "reference model with one-offer fragility tails"
        return {"mix": "reference model (mix)"}.get(method, method)

    names = {"q6": "reference + nearest-neighbour analogs", "q7": "reference + provider simulator",
             "q8": "reference + short-context Chronos width", "q9": "reference with one-offer fragility tails"}
    rows = []
    for i, x in enumerate(r1, 1):
        sk = x["result"]["pooled_skill"]
        rows.append(f"<tr><td class=n>{i}</td><td>{esc(label(x['method'], x['params']))}</td><td class=n>{f3(sk)}</td>"
                    f"<td>drift</td><td class=n>{sgn(sk - drift)}</td><td class=n>not in the log</td><td class=n>–</td><td>–</td></tr>")
    for r in keep:
        q = r["name"].split("_")[0]
        rows.append(f"<tr><td class=n>{q[1:]}</td><td>{esc(names[q])}</td><td class=n>{f3(r['skill'])}</td><td>reference</td>"
                    f"<td class=n>{sgn(r['d_vs_ref'])}</td><td class=n>{ci(r['ci90'])}</td><td class=n>{esc(pv(r['p_one_sided']))}</td>"
                    f"<td>{'kept' if r['name'] in passed else 'not kept'}</td></tr>")
    fh, fn = g["q10_final_headline"], g["q11_final_nonhead"]
    nn = next(int(re.search(r"\d+", x["universe"]).group()) for x in log if x["universe"].startswith("custom") and x["split"] == "val")
    for q, r, what in (("10", fh, f"final blend, {nhead} headline series (optimistic)"), ("11", fn, f"final blend, {nn} other posted rental series")):
        rows.append(f"<tr class=final><td class=n>{q}</td><td>{esc(what)}</td><td class=n>{f3(r['skill'])}</td><td>drift</td>"
                    f"<td class=n>{sgn(r['d_vs_drift'])}</td><td class=n>{ci(r['ci90_vs_drift'])}</td><td class=n>{esc(pv(r['p_one_sided']))}</td><td>submitted</td></tr>")
    nval = sum(1 for x in log if x["split"] == "val" and x["method"] not in ("drift", "mix") and "role" not in x["params"])
    table = ("<div class=tw><table class=val><caption>Validation results, 13 to 30 October 2026 (origins the methods were not tuned on). "
             "Skill is pooled over cells; differences are paired, with 90% week-block bootstrap intervals.</caption><thead><tr><th>Query</th><th>Candidate</th>"
             "<th>Skill</th><th>Compared with</th><th>Difference</th><th>90% interval</th><th>One-sided p</th><th>Decision</th></tr></thead><tbody>"
             + "".join(rows) + "</tbody></table></div>")
    facts = {"bh_kept": sorted(passed), "n_val_candidate_runs": nval, "nonhead_series": nn}
    return table, facts


def loss_svg(rows: list[dict]) -> str:
    causes = [r for r in rows if r["cause"] != "total"]
    tot = {s: float(next(r for r in rows if r["cause"] == "total")[f"{s}_loss_over_lv"]) for s, _ in SYSTEMS}
    W, L, R, BH, GAP, top = 960, 170, 70, 34, 16, 20
    x = lambda v: L + v * (W - L - R)
    shade = {"dynamic_reprice": "var(--a1)", "entry": "var(--a2)", "exit": "var(--a2l)", "none": "var(--g1)", "announced_oneoff": "var(--g2)",
             "unannounced_oneoff": "var(--g3)", "marketplace_ask": "var(--g4)", "hyperscaler_spot": "var(--g5)"}
    parts = []
    for i, (s, name) in enumerate(SYSTEMS):
        y = top + i * (BH + GAP)
        acc = 0.0
        parts.append(f'<text x="{L - 8}" y="{y + BH / 2 + 5}" text-anchor="end" class="lab">{esc(name)}</text>')
        for r in causes:
            v = float(r[f"{s}_loss_share_of_total_lv"])
            parts.append(f'<rect x="{x(acc):.1f}" y="{y}" width="{x(acc + v) - x(acc):.1f}" height="{BH}" fill="{shade[r["cause"]]}" stroke="var(--bg)" stroke-width="1">'
                         f'<title>{esc(name)}: {esc(CAUSE[r["cause"]])}, {v:.3f} of last-value loss</title></rect>')
            acc += v
        parts.append(f'<text x="{x(acc) + 6:.1f}" y="{y + BH / 2 + 5}" class="num">{tot[s]:.3f}</text>')
    yb = top + 4 * (BH + GAP)
    for t in np.arange(0, 1.01, 0.2):
        parts.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top - 6}" y2="{yb - GAP + 4}" class="grid"/>'
                     f'<text x="{x(t):.1f}" y="{yb + 8}" text-anchor="middle" class="tick">{t:.1f}</text>')
    parts.append(f'<text x="{x(0.5):.1f}" y="{yb + 30}" text-anchor="middle" class="tick">loss as a share of the last-value forecast\'s loss (shorter is better; 1.0 = no better than repeating the last price)</text>')
    leg, lx, ly = [], L, yb + 52
    for r in causes:
        lab = CAUSE[r["cause"]]
        wv = 22 + 7.2 * len(lab)
        if lx + wv > W:
            lx, ly = L, ly + 22
        leg.append(f'<rect x="{lx}" y="{ly - 11}" width="14" height="14" fill="{shade[r["cause"]]}"/><text x="{lx + 20}" y="{ly + 1}" class="tick">{esc(lab)}</text>')
        lx += wv + 14
    h = ly + 16
    return (f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="Stacked bars of forecast loss by cause for four systems; the table below gives the numbers">'
            + "".join(parts + leg) + "</svg>")


def loss_table(rows: list[dict]) -> str:
    th = "".join(f"<th>{esc(n)}</th>" for _, n in SYSTEMS)
    body = []
    for r in rows:
        lab = "total (1 − skill on dev)" if r["cause"] == "total" else CAUSE[r["cause"]]
        cells = "".join(f"<td class=n>{float(r[f'{s}_loss_share_of_total_lv']):.3f}</td>" for s, _ in SYSTEMS)
        body.append(f"<tr{' class=final' if r['cause'] == 'total' else ''}><td>{esc(lab)}</td><td class=n>{int(r['cells']):,}</td>{cells}</tr>")
    return ("<details><summary>Numbers behind the chart</summary><div class=tw><table><thead><tr><th>Cause</th><th>Cells</th>" + th
            + "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div></details>")


def ledger_section(led: list[dict]) -> tuple[str, dict]:
    counts = {k: sum(1 for r in led if r["status"] == k) for k in STATUS}
    other = len(led) - sum(counts.values())
    btns = [f'<button type=button class=flt aria-pressed=true data-f="all">All <span class=n>{len(led)}</span></button>']
    btns += [f'<button type=button class=flt aria-pressed=false data-f="{k}">{v} <span class=n>{counts[k]}</span></button>' for k, v in STATUS.items()]
    items = []
    for r in led:
        st = r["status"]
        items.append(f'<li data-s="{esc(st)}"><div class=lh><span class="badge b-{esc(st)}">{esc(STATUS.get(st, st))}</span> '
                     f'<b>{esc(r["id"])}</b> <span class=muted>tested by the {esc(r.get("agent", ""))} agent</span></div>'
                     f'<p class=claim>{inline(r.get("claim", ""))}</p><p class=res>{inline(r.get("result", "") or "No result recorded.")}</p>'
                     f'<p class=ev>Evidence: {inline(r.get("evidence", "") or "–")}</p></li>')
    html_ = (f'<div class=filters role=group aria-label="Filter hypotheses by verdict">{"".join(btns)}</div>'
             f'<p class=muted id=ledger-count aria-live=polite>Showing all {len(led)} hypotheses.</p>'
             f'<div class=scroll tabindex=0 role=region aria-label="Hypothesis list"><ol class=ledger id=ledger>{"".join(items)}</ol></div>')
    return html_, {"ledger_total": len(led), **{f"ledger_{k}": v for k, v in counts.items()}, "ledger_other": other}


def calendar_section(cal: list[dict], check: dict, exa: dict, led: dict) -> tuple[str, dict]:
    cal = sorted(cal, key=lambda r: (r["effective_date"], r["provider"], r["published"]))
    ds = [dt.date.fromisoformat(r[k]) for r in cal for k in ("published", "effective_date")] + [ORIGIN]
    d0, d1 = min(ds) - dt.timedelta(days=4), max(ds) + dt.timedelta(days=6)
    W, L, R, RH, top = 960, 150, 30, 24, 26
    x = lambda d: L + (d - d0).days / (d1 - d0).days * (W - L - R)
    parts = []
    m = dt.date(d0.year, d0.month, 1)
    while m <= d1:
        if m >= d0:
            parts.append(f'<line x1="{x(m):.1f}" x2="{x(m):.1f}" y1="{top - 8}" y2="{top + RH * len(cal)}" class="grid"/>'
                         f'<text x="{x(m) + 3:.1f}" y="{top - 12}" class="tick">1 {m:%b}</text>')
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    parts.append(f'<line x1="{x(ORIGIN):.1f}" x2="{x(ORIGIN):.1f}" y1="{top - 8}" y2="{top + RH * len(cal)}" class="cut"/>'
                 f'<text x="{x(ORIGIN) - 4:.1f}" y="{top + RH * len(cal) + 16}" text-anchor="end" class="tick">data cutoff, 6 Nov</text>')
    for i, r in enumerate(cal):
        y = top + i * RH + RH / 2
        pub, eff = dt.date.fromisoformat(r["published"]), dt.date.fromisoformat(r["effective_date"])
        ahead = bool(r.get("announced_before_effective")) and (eff - pub).days > 0
        col = "var(--a2)" if ahead else "var(--g4)"
        parts.append(f'<text x="{L - 8}" y="{y + 4}" text-anchor="end" class="lab">{esc(r["provider"])}</text>'
                     f'<line x1="{x(pub):.1f}" x2="{x(eff):.1f}" y1="{y}" y2="{y}" stroke="{col}" stroke-width="3"/>'
                     f'<circle cx="{x(pub):.1f}" cy="{y}" r="5" fill="var(--bg)" stroke="{col}" stroke-width="2"><title>published {pub}</title></circle>'
                     f'<circle cx="{x(eff):.1f}" cy="{y}" r="5" fill="{col}"><title>effective {eff}</title></circle>')
    svg = (f'<svg viewBox="0 0 {W} {top + RH * len(cal) + 24}" role="img" aria-label="Timeline of announced repricings: hollow dot is the publication date, filled dot the effective date">'
           + "".join(parts) + "</svg>")
    trs = []
    for r in cal:
        chs = [f"{c['gpu']} {('%.2f → ' % c['old']) if c.get('old') is not None else ''}{c['new']:.2f}"
               + (f" ({c['pct'] * 100:+.0f}%)" if c.get("pct") is not None else "") for c in r["changes"] if c.get("new") is not None]
        ch = "; ".join(chs[:4]) + (f"; and {len(chs) - 4} more GPU classes" if len(chs) > 4 else "") if chs else "–"
        lead = r.get("lead_days")
        lead_s = (f"{lead} days ahead" if lead and lead > 0 else "same day" if lead == 0 else f"{-lead} day{'s' if lead < -1 else ''} after" if lead is not None else "–")
        also = "".join(f'<br><a href="{esc(a["url"])}">also, {esc(a.get("published", ""))}</a>' for a in r.get("also", []) if a.get("url"))
        note = f'<br><span class=muted>{inline(r["edit_note"])}</span>' if r.get("edit_note") else ""
        trs.append(f"<tr><td class=n>{esc(r['published'])}</td><td class=n>{esc(r['effective_date'])}</td><td>{esc(r['provider'])}</td>"
                   f"<td>{esc(ch).replace('−', '-')}</td><td>{esc(lead_s)}</td>"
                   f"<td><a href=\"{esc(r['url'])}\">{esc(r['title'])}</a> <span class=muted>({esc(r['published'])}, {esc(r.get('source_type', ''))}, confidence {esc(r.get('confidence', ''))})</span>{also}</td>"
                   f"<td class=q>“{inline(r['quote'])}”{note}</td></tr>")
    table = ("<div class=tw><table class=cal><thead><tr><th>Published</th><th>Effective</th><th>Provider</th><th>Change, USD per GPU-hour</th>"
             "<th>Notice</th><th>Source</th><th>Quoted sentence</th></tr></thead><tbody>" + "".join(trs) + "</tbody></table></div>")
    n_ahead = sum(1 for r in cal if r.get("announced_before_effective") and (r.get("lead_days") or 0) > 0)
    facts = {"cal_entries": len(cal), "cal_ahead": n_ahead, "cal_hits": check["b1_hits"], "cal_checkable": check["b1_checkable"],
             "exa_events": exa["n_events"], "exa_announced": exa["n_announced_before"]}
    neg = (f"<ul class=neg><li><strong>Most large repricings were not announced.</strong> Of the {exa['n_events']} largest repricing events on the development period, "
           f"{exa['n_announced_before']} had a dated public announcement before the move ({exa['marketplace_events']} were marketplace asks, which have nothing to announce). "
           f"A keyword rule for spotting announcements also fired on {exa['control_false_alarms_v2']} of {exa['control_pairs']} control dates with no repricing. "
           f"Ledger H13, verdict {esc(STATUS.get(led['H13']['status'], led['H13']['status']))}.</li>"
           f"<li><strong>A provider's published pricing policy did not help.</strong> {inline(led['H26']['result'])} Ledger H26, verdict {esc(STATUS.get(led['H26']['status'], led['H26']['status']))}.</li></ul>")
    return svg, table, neg, facts


def memory_section(journal: list[dict]) -> tuple[str, dict]:
    live = [x for x in journal if not x.get("offline")]
    writes: dict[tuple, set] = {}
    for x in live:
        if x["op"] != "ingest":
            continue
        for it in x["request"]["body"].get("items", []):
            writes.setdefault((it.get("identity"), it.get("audience")), set()).add(it["id"])
    reads: dict[tuple, int] = {}
    nrecall: dict[str, int] = {}
    for x in live:
        if x["op"] != "recall" or not isinstance(x.get("response"), dict):
            continue
        who = x["request"]["body"].get("identity")
        nrecall[who] = nrecall.get(who, 0) + 1
        for res in x["response"].get("results", []):
            authors = {s.get("metadata", {}).get("agent") for s in res.get("sources", [])} - {None}
            for a in authors or {"unknown"}:
                reads[(who, a)] = reads.get((who, a), 0) + 1
    wid = sorted({k[0] for k in writes})
    aud = sorted({k[1] for k in writes})
    readers = sorted(nrecall)
    authors = sorted({k[1] for k in reads})
    wt = ("<table class=mx><caption>Records written (distinct ids), by author and audience</caption><thead><tr><th>Author</th>"
          + "".join(f"<th>{esc(a)}</th>" for a in aud) + "</tr></thead><tbody>"
          + "".join(f"<tr><th scope=row>{esc(w)}</th>" + "".join(f"<td class=n>{len(writes.get((w, a), ())) or ''}</td>" for a in aud) + "</tr>" for w in wid)
          + "</tbody></table>")
    rt = ("<table class=mx><caption>Records returned to each reader, by the agent that wrote them (live recalls)</caption><thead><tr><th>Reader (recalls)</th>"
          + "".join(f"<th>{esc(a)}</th>" for a in authors) + "</tr></thead><tbody>"
          + "".join(f"<tr><th scope=row>{esc(r)} ({nrecall[r]})</th>" + "".join(f"<td class=n>{reads.get((r, a), '') or ''}</td>" for a in authors) + "</tr>" for r in readers)
          + "</tbody></table>")

    def example(x, k=3):
        b, resp = x["request"]["body"], x["response"]
        res = resp.get("results", [])
        asof = b.get("occurredTo")
        dates = [r.get("occurredAt", "") for r in res]
        bound = ""
        if asof:
            ok = all(d[:10] <= asof for d in dates if d)
            bound = (f"<p>Date bound: the recall was limited to records dated on or before {esc(asof)}. "
                     f"{len(res)} records came back; the latest is dated {esc(max(dates)[:10] if dates else '–')}"
                     f"{', so none is later than the bound' if ok else ', which is LATER than the bound'}.</p>")
        items = []
        for r in res[:k]:
            a = sorted({s.get("metadata", {}).get("agent") for s in r.get("sources", [])} - {None})
            lab = (r.get("sources") or [{}])[0].get("label", "")
            txt = r.get("content", "").strip()
            txt = txt if len(txt) <= 420 else txt[:417] + "…"
            items.append(f"<li><span class=muted>written by <b>{esc(', '.join(a) or 'unknown')}</b>, dated {esc(r.get('occurredAt', '')[:10])}, record “{esc(lab)}”</span>"
                         f"<blockquote>{inline(txt)}</blockquote></li>")
        return (f"<div class=recall><p><b>Asked by:</b> {esc(b.get('identity', ''))}"
                f"{(' &nbsp; <b>as of:</b> ' + esc(asof)) if asof else ''} &nbsp; <b>at:</b> {esc(x['time'][:16].replace('T', ' '))} UTC</p>"
                f"<p><b>Question:</b> “{esc(b.get('query', ''))}”</p>{bound}<p>First {min(k, len(res))} of {len(res)} records returned:</p><ol>{''.join(items)}</ol></div>")

    rec = [x for x in live if x["op"] == "recall" and isinstance(x.get("response"), dict) and x["response"].get("results")]
    ex1 = next(x for x in rec if x["request"]["body"].get("identity") == "forecaster" and x["request"]["body"].get("occurredTo"))
    ex2 = next(x for x in rec if x["request"]["body"].get("identity") == "proposer"
               and any(s.get("metadata", {}).get("agent") not in (None, "proposer") for r in x["response"]["results"] for s in r.get("sources", [])))
    n_ing = sum(1 for x in live if x["op"] == "ingest")
    facts = {"mem_live_ingests": n_ing, "mem_live_recalls": sum(nrecall.values()),
             "mem_distinct_records": sum(len(v) for v in writes.values()), "mem_writers": len(wid), "mem_readers": len(readers)}
    html_ = (f"<p>{facts['mem_writers']} agents wrote {facts['mem_distinct_records']} distinct records in {n_ing} live write calls; "
             f"{facts['mem_readers']} agents read them in {facts['mem_live_recalls']} live recalls. Counts come from <code>data_out/memory_journal.jsonl</code>, "
             f"which logs every request and response; offline replays are excluded.</p><div class=two>{wt}{rt}</div>"
             f"<h3>Recall 1: the forecaster asks, limited to what was known on the forecast date</h3>{example(ex1)}"
             f"<h3>Recall 2: the agent that proposes hypotheses reads what other agents found</h3>{example(ex2)}")
    return html_, facts


def longrun_section() -> tuple[str, dict]:
    text = P["longrun"].read_text()
    title, secs = md_sections(text)
    answer = next((b for h, b in secs if "answer" in h.lower()), secs[0][1] if secs else "")
    assum = next(((h, b) for h, b in secs if "assumption" in h.lower()), None)
    lines, tbl = text.splitlines(), None
    for i, l in enumerate(lines):
        if l.startswith("|") and "24 month" in l and (i == 0 or not lines[i - 1].startswith("|")):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            tbl = md_table(lines[i:j])
            break
    fig = longrun_fig()
    parts = [f"<p class=muted>Rendered at build time from <code>{rel(P['longrun'])}</code> (“{esc(title)}”), sha256 {sha(P['longrun'])[:12]}.</p>",
             f"<h3>The answer in brief</h3>{md_block(answer)}"]
    if tbl:
        parts.append(f"<h3>Rent paths, USD per GPU-hour on the static rate-card median</h3>{tbl}")
    parts.append(fig)
    if assum:
        parts.append(f"<h3>{esc(re.sub(r'^\d+\.\s*', '', assum[0]))}</h3>{md_block(assum[1])}")
    return "\n".join(parts), {"longrun_sha": sha(P["longrun"])}


def longrun_fig() -> str:
    p = P["longrun_paths"]
    if not p.exists():
        m = re.search(r"!\[[^\]]*\]\(([^)]+\.png)\)", P["longrun"].read_text())
        if not m:
            return ""
        img = P["longrun"].parent / m.group(1)
        return f'<figure><img alt="Figure from the long-run report" src="data:image/png;base64,{base64.b64encode(img.read_bytes()).decode()}"></figure>'
    df = pd.read_csv(p)
    chips = list(dict.fromkeys(df.chip))
    W, H, pw = 960, 300, 440
    parts = []
    for ci_, chip in enumerate(chips):
        d = df[df.chip == chip]
        base = d.base.iloc[0]
        d = d[d.base == base]
        lvl = float(d.level_nov2026.iloc[0])
        ymax = max(d.q90.max(), lvl) * 1.08
        x0 = 60 + ci_ * (pw + 40)
        X = lambda mth: x0 + mth / 36 * (pw - 70)
        Y = lambda v: H - 40 - v / ymax * (H - 80)
        for t in np.arange(0, ymax, 1.0 if ymax > 3 else 0.5):
            parts.append(f'<line x1="{X(0):.1f}" x2="{X(36):.1f}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="grid"/><text x="{X(0) - 6:.1f}" y="{Y(t) + 4:.1f}" text-anchor="end" class="tick">{t:.1f}</text>')
        for mth in (0, 12, 24, 36):
            parts.append(f'<text x="{X(mth):.1f}" y="{H - 22}" text-anchor="middle" class="tick">{"Nov 2026" if mth == 0 else f"+{mth} mo"}</text>')
        mx = d[d.scenario == "mixture"].sort_values("h_months")
        hs = [0] + list(mx.h_months)
        lo = [lvl] + list(mx.q10)
        hi = [lvl] + list(mx.q90)
        mid = [lvl] + list(mx.q50)
        band = " ".join(f"{X(h):.1f},{Y(v):.1f}" for h, v in zip(hs, hi)) + " " + " ".join(f"{X(h):.1f},{Y(v):.1f}" for h, v in zip(hs[::-1], lo[::-1]))
        parts.append(f'<polygon points="{band}" fill="var(--a2)" opacity="0.18"><title>{esc(chip)} mixture, 10th to 90th percentile</title></polygon>')
        for sc in sorted(set(d.scenario) - {"mixture"}):
            s = d[d.scenario == sc].sort_values("h_months")
            pts = " ".join(f"{X(h):.1f},{Y(v):.1f}" for h, v in zip([0] + list(s.h_months), [lvl] + list(s.q50)))
            parts.append(f'<polyline points="{pts}" fill="none" stroke="var(--g4)" stroke-width="1.5" stroke-dasharray="4 3"/>'
                         f'<text x="{X(36) + 4:.1f}" y="{Y(float(s.q50.iloc[-1])) + 4:.1f}" class="tick">{esc(sc)}</text>')
        pts = " ".join(f"{X(h):.1f},{Y(v):.1f}" for h, v in zip(hs, mid))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="var(--a2)" stroke-width="2.5"/>'
                     f'<text x="{X(0):.1f}" y="22" class="lab">{esc(chip)}: {esc(base)}, {lvl:.2f} today</text>')
    parts.append(f'<text x="60" y="{H - 4}" class="tick">Solid line and band: probability-weighted mixture, median and 10th to 90th percentile. Dashed: median of each scenario. USD per GPU-hour.</text>')
    return (f'<figure><svg viewBox="0 0 {W} {H}" role="img" aria-label="Projected rent paths for each chip under three scenarios and their mixture">{"".join(parts)}</svg>'
            f'<figcaption>Drawn from <code>{rel(p)}</code>.</figcaption></figure>')


def protocol_bits() -> dict:
    t = P["protocol"].read_text()
    leak = re.search(r"## Leakage rule\s+(.+?)\n\n", t, re.S).group(1).strip()
    v = re.search(r"Validation: every day from (\S+) to (\S+) \((\d+) origins", t)
    return {"leak": leak, "val_from": v.group(1), "val_to": v.group(2), "val_origins": int(v.group(3))}


def exa_lines() -> list[int]:
    return [i for i, l in enumerate(P["scout"].read_text().splitlines(), 1) if "api.exa.ai" in l and "Request(" in l]


# ---------------------------------------------------------------- page
def build(out: Path = OUT) -> Path:
    gate, log = jl(P["val_gate"]), jl(P["val_log"])
    g = {r["name"]: r for r in gate}
    fh, fn = g["q10_final_headline"], g["q11_final_nonhead"]
    led_rows = jl(P["ledger"])
    led = {r["id"]: r for r in led_rows}
    with open(P["loss"]) as f:
        loss = list(csv.DictReader(f))
    proto = protocol_bits()
    ex = explorer_data()
    nhead = len(ex["series"])
    val_html, vfacts = val_section(gate, log, nhead)
    led_html, lfacts = ledger_section(led_rows)
    cal_svg, cal_table, cal_neg, cfacts = calendar_section(jl(P["calendar"]), json.loads(P["cal_check"].read_text()),
                                                           json.loads(P["exa_head"].read_text()), led)
    mem_html, mfacts = memory_section(jl(P["journal"]))
    lr_html, lrfacts = longrun_section()
    total = next(r for r in loss if r["cause"] == "total")
    facts = {
        "final_head_skill": round(fh["skill"], 4), "final_head_drift": round(fh["drift_skill"], 4), "final_head_d_drift": round(fh["d_vs_drift"], 4),
        "final_head_ci_drift": [round(v, 4) for v in fh["ci90_vs_drift"]], "final_head_cov": round(fh["coverage"], 4), "final_head_cells": fh["n_cells"],
        "final_non_skill": round(fn["skill"], 4), "final_non_drift": round(fn["drift_skill"], 4), "final_non_d_drift": round(fn["d_vs_drift"], 4),
        "final_non_ci_drift": [round(v, 4) for v in fn["ci90_vs_drift"]], "final_non_cov": round(fn["coverage"], 4), "final_non_cells": fn["n_cells"],
        "loss_total": {s: round(float(total[f"{s}_loss_over_lv"]), 4) for s, _ in SYSTEMS}, "headline_series": nhead,
        **proto, **vfacts, **lfacts, **cfacts, **mfacts, **lrfacts,
    }
    del facts["leak"]
    inputs = sorted(set(P.values()) - {P["longrun_paths"]} | ({P["longrun_paths"]} if P["longrun_paths"].exists() else set()))
    hashes = "".join(f"<tr><td><code>{esc(rel(p))}</code></td><td class=h><code>{sha(p)}</code></td></tr>" for p in inputs)
    subs = "".join(f"<tr><td><code>{esc(rel(P[k]))}</code></td><td class=h><code>{sha(P[k])}</code></td></tr>" for k in ("headline", "all", "members"))
    ev = "".join(f"<tr><td>{esc(c)}</td><td>{'<br>'.join(('<code>' + esc(p) + '</code>' + ('' if (ROOT / p).exists() else ' <b>(missing)</b>')) for p in ps)}</td></tr>" for c, ps in EVIDENCE)
    lines = ", ".join(str(n) for n in exa_lines())
    nval_dir = len([r for r in gate if r["name"].split("_")[0] in ("q6", "q7", "q8", "q9")])

    head = f"""
<section id=s1 aria-labelledby=h1>
<p class=kicker>Iterate AI Research Hackathon, Track 2 (Pacific Machines)</p>
<h1 id=h1>Forecasting posted GPU rental prices by modelling the offers behind each median</h1>
<p class=q><b>Question.</b> What will the posted GPU rental medians in the data pack be 1, 3 and 7 days after 6 November 2026, with intervals that can be trusted?</p>
<p class=lead><b>Result.</b> On {proto['val_origins']} validation origins it had not been tuned on ({proto['val_from']} to {proto['val_to']}), the submitted forecaster scored a pooled skill of
<b>{f3(fh['skill'])}</b> against <b>{f3(fh['drift_skill'])}</b> for the drift baseline on the {nhead} headline series (difference {sgn(fh['d_vs_drift'])}, 90% interval {ci(fh['ci90_vs_drift'])}),
and <b>{f3(fn['skill'])}</b> against <b>{f3(fn['drift_skill'])}</b> on {vfacts['nonhead_series']} other posted rental series that no one had evaluated before (difference {sgn(fn['d_vs_drift'])}, {ci(fn['ci90_vs_drift'])}).</p>
<div class=big>
<div><span class=v>{f3(fh['skill'])} <small>vs {f3(fh['drift_skill'])}</small></span><span class=k>skill on the {nhead} headline series, against drift ({fh['n_cells']:,} forecasts). Optimistic: four of its members were kept on this period.</span></div>
<div><span class=v>{f3(fn['skill'])} <small>vs {f3(fn['drift_skill'])}</small></span><span class=k>skill on {vfacts['nonhead_series']} series nobody had tuned on ({fn['n_cells']:,} forecasts). The cleaner estimate.</span></div>
<div><span class=v>{fh['coverage']:.2f}</span><span class=k>share of outcomes inside the 10th to 90th percentile interval on the headline series (target 0.80).</span></div>
</div>
<p><b>The idea.</b> A posted GPU price median is the middle of a small panel of provider offers, usually 3 to 17 of them. It moves only when a provider near the middle reprices,
or when an offer enters or leaves. The system found this by analysing its own forecast failures, then stopped forecasting the series as a line and started forecasting the panel:
each offer follows its own provider's recent repricing, and the median is read off the simulated panel. That change held on dates it had not seen.</p>
<details class=terms><summary>Terms used on this page</summary><dl>
<dt>Offer</dt><dd>One provider's posted price for one GPU configuration on one day, in USD per GPU-hour.</dd>
<dt>Panel</dt><dd>All offers behind one series on one day. The series value is their median, reproduced exactly from the offers in the pack.</dd>
<dt>Skill</dt><dd>1 minus the forecast's pinball loss (at the 10th, 50th and 90th percentiles) divided by the loss of repeating the last price. 0 means no better than repeating the last price.</dd>
<dt>Drift</dt><dd>The organisers' baseline: the last price scaled by the historical spread of that series' price changes.</dd>
<dt>Reference model</dt><dd>The system's first validated model (called <code>mix</code> in the code): drift pooled across similar series and conditioned on whether the price moved recently.</dd>
<dt>Provider simulator</dt><dd>A forecaster (<code>prov</code>) that moves each offer the way its provider repriced over the previous 21 days and takes the median of the simulated panel, so a climbing provider pulls the median only until it passes the next offer.</dd>
<dt>One-offer fragility</dt><dd>The largest move of the median if one offer left the panel. The fragility forecaster puts interval mass on the values the median would jump to if one offer left or joined.</dd>
<dt>Cell</dt><dd>One forecast: a series, an origin date and a horizon.</dd>
</dl></details>
</section>"""

    explorer = f"""
<section id=s2 aria-labelledby=h2>
<h2 id=h2>The panel behind each median</h2>
<p>Pick any of the {nhead} scored series. The upper chart shows every offer on the day chosen with the slider, sorted by price, coloured by how often its provider repriced in the 21 days to 6 November.
Dashed lines mark where the median would jump if one offer left or one joined. The three bottom rows are the submitted forecast from 6 November. The lower chart shows the previous {WINDOW} days (prices on or before 6 November only).</p>
<div class=controls>
<label for=sel>Series</label> <select id=sel></select>
<span class=presets role=group aria-label="Preset series" id=presets></span>
</div>
<p class=muted id=preset-note></p>
<div class=legend aria-hidden=true><span><svg width=14 height=14><path d="M7 1 L13 7 L7 13 L1 7 Z" fill="var(--a1)"/></svg> reprices often (on {ex['dyn'] * 100:.0f}% or more of days)</span>
<span><svg width=14 height=14><circle cx=7 cy=7 r=5.5 fill="var(--a2)"/></svg> static (under {ex['static'] * 100:.0f}% of days)</span>
<span><svg width=14 height=14><rect x=2 y=2 width=10 height=10 fill="var(--mid)"/></svg> in between</span>
<span><svg width=22 height=14><line x1=0 x2=22 y1=7 y2=7 stroke="var(--fg)" stroke-width=2.5/></svg> median</span>
<span><svg width=22 height=14><line x1=0 x2=22 y1=7 y2=7 stroke="var(--fg)" stroke-dasharray="4 3"/></svg> median if one offer leaves or joins</span></div>
<div class=exp>
<div class=stripwrap><div id=strip></div>
<div class=sliderrow><label for=day>Day</label> <input type=range id=day min=0 max={WINDOW - 1} step=1 value={WINDOW - 1}> <output id=daylab for=day></output></div>
<p id=readout aria-live=polite></p></div>
<aside class=facts aria-labelledby=facth><h3 id=facth>Index quality on 6 November</h3><dl id=facts></dl>
<p class=muted>From <code>experiments/insight/results/t1_index_quality_card.csv</code>.</p></aside>
</div>
<div id=hist></div>
</section>"""

    improved = f"""
<section id=s3 aria-labelledby=h3>
<h2 id=h3>How it improved: where the forecast loss went</h2>
<p>Each bar splits a system's forecast loss on the development period ({int(total['cells']):,} cells) by what physically happened to the panel. The system aimed its later members at the causes it found:
the provider simulator at frequent repricers (orange), the fragility tails at offers entering and leaving (blue). The current blend here is the six-member blend analysed in the second failure analysis;
the submitted forecaster adds the fragility tails as a seventh member.</p>
{loss_svg(loss)}
{loss_table(loss)}
<p>Validation queries were spent sparingly: {nval_dir} round-two directions were sent to validation, each declared in <code>research-log.md</code> before it ran, each tested against the reference model, and kept only if it passed the
Benjamini-Hochberg false-discovery rule at 10% over that round ({len(vfacts['bh_kept'])} of {nval_dir} passed). Query 5 is the exception: it was added after seeing queries 1 to 4, which the log says, and it was used only to pick a safety-net submission.
The final blend's members were fixed on development data by a rule written before it was scored (EVAL_PROTOCOL.md, Amendment 3), and it was then scored once on each universe.</p>
{val_html}
</section>"""

    ledger = f"""
<section id=s4 aria-labelledby=h4>
<h2 id=h4>The ledger: every hypothesis and its verdict</h2>
<p>Each hypothesis was registered with a prediction and a refutation condition before it was tested. Refuted and not-significant results stay in the record; several of them pointed to the next idea.</p>
{led_html}
</section>"""

    exa = f"""
<section id=s5 aria-labelledby=h5>
<h2 id=h5>What search found (Exa)</h2>
<p>The scout agent searched the web through Exa for dated provider price announcements, keeping only pages published on or before each forecast origin and never opening price-tracker pages.
The calendar below is what it kept: {cfacts['cal_entries']} entries, {cfacts['cal_ahead']} of them published before the effective date. Exa is called in <code>src/gpuf/scout.py</code> (lines {lines}); every response is cached in <code>data_out/exa_cache/</code>.</p>
{cal_svg}
<p class=muted>Hollow dot: date the source was published. Filled dot: date the new price took effect. Blue: published before the effective date. Grey: published on or after it.</p>
<p class=check><b>Check against the panel:</b> {cfacts['cal_hits']} of {cfacts['cal_checkable']} offers that could be checked moved to exactly the announced price (<code>experiments/calendar/results/partb_summary.json</code>).</p>
{cal_table}
<h3>Honest negatives</h3>
{cal_neg}
</section>"""

    memory = f"""
<section id=s6 aria-labelledby=h6>
<h2 id=h6>Shared memory between agents (past.dev)</h2>
<p>Agents write what they learn to three audiences in past.dev: failure cases (the autopsy agent), dated web evidence (the scout), and tested hypotheses (the experimenter and method agents).
Other agents read from it before they start. The forecaster may read only failures and evidence, and only records dated on or before its forecast origin.</p>
{mem_html}
</section>"""

    longrun = f"""
<section id=s7 aria-labelledby=h7>
<h2 id=h7>The 2 to 3 year view</h2>
{lr_html}
</section>"""

    repro = f"""
<section id=s8 aria-labelledby=h8>
<h2 id=h8>Reproduce</h2>
<p>From <code>track_2/</code>, with the pack in <code>data/pack/</code>: <code>bash reproduce.sh final</code> checks the pack against its manifest, rebuilds the series as of 6 November and writes the three submission files below
(about 25 seconds; needs the Chronos-Bolt-small weights in the local Hugging Face cache, never downloads). This page: <code>PYTHONPATH=src .venv/bin/python -m gpuf.demo</code>.</p>
<p><b>Leak rule</b> (EVAL_PROTOCOL.md): {inline(proto['leak'])}</p>
<h3>Submission files</h3><div class=tw><table><thead><tr><th>File</th><th>SHA-256</th></tr></thead><tbody>{subs}</tbody></table></div>
<h3>Where each claim's evidence lives</h3><div class=tw><table><thead><tr><th>Claim</th><th>Files</th></tr></thead><tbody>{ev}</tbody></table></div>
<details><summary>Every input this page was built from, with its SHA-256</summary><div class=tw><table><tbody>{hashes}</tbody></table></div></details>
</section>"""

    js_data = json.dumps(ex, sort_keys=True, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    js_facts = json.dumps(facts, sort_keys=True, separators=(",", ":")).replace("</", "<\\/")
    page = (TEMPLATE.replace("%%BODY%%", head + explorer + improved + ledger + exa + memory + longrun + repro)
            .replace("%%DATA%%", js_data).replace("%%FACTS%%", js_facts).replace("%%JS%%", JS).replace("%%CSS%%", CSS))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    return out


CSS = r"""
:root{--bg:#ffffff;--fg:#1c2128;--muted:#59636e;--line:#d1d9e0;--soft:#f6f8fa;--a1:#c45100;--a2:#0a6aa6;--a2l:#7fb3d5;--mid:#8c959f;
--g1:#e3e7eb;--g2:#c3cad1;--g3:#a2abb5;--g4:#7d8792;--g5:#5b646e;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#101418;--fg:#e4e8ec;--muted:#9ba5b0;--line:#2f3741;--soft:#171c22;--a1:#f08a4b;--a2:#58b0e3;--a2l:#2f6f99;
--mid:#7d8792;--g1:#2a3139;--g2:#3d4650;--g3:#55606b;--g4:#7a8590;--g5:#a3adb7}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
main{max-width:1000px;margin:0 auto;padding:28px 20px 80px}
nav{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);z-index:2}
nav ol{max-width:1000px;margin:0 auto;padding:8px 20px;list-style:none;display:flex;flex-wrap:wrap;gap:4px 18px;font-size:14px}
nav a{color:var(--muted);text-decoration:none}nav a:hover{color:var(--fg);text-decoration:underline}
section{padding-top:28px;border-top:1px solid var(--line);margin-top:28px}section:first-of-type{border-top:0;margin-top:0}
h1{font-size:30px;line-height:1.2;margin:4px 0 14px;letter-spacing:-.01em}h2{font-size:23px;margin:0 0 10px}h3{font-size:17px;margin:22px 0 8px}h4{font-size:15px;margin:14px 0 6px}
p{margin:8px 0}.kicker{color:var(--muted);margin:0;font-size:14px}.muted{color:var(--muted)}.lead{font-size:17px}
a{color:var(--a2)}a:focus-visible,button:focus-visible,select:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid var(--a2);outline-offset:2px}
code{font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--soft);padding:1px 4px;border-radius:3px;word-break:break-all}
.big{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:18px 0}
.big>div{border:1px solid var(--line);border-radius:6px;padding:12px 14px;background:var(--soft)}
.big .v{display:block;font-size:28px;font-weight:650;font-variant-numeric:tabular-nums}.big .v small{font-size:16px;font-weight:400;color:var(--muted)}
.big .k{display:block;font-size:14px;color:var(--muted)}
details{margin:10px 0}summary{cursor:pointer;color:var(--a2)}dl{margin:6px 0}dt{font-weight:600;margin-top:6px}dd{margin:0 0 4px 0}
.terms dl{display:grid;grid-template-columns:170px 1fr;gap:2px 14px}.terms dt{margin:0}.terms dd{margin:0}
svg{display:block;width:100%;height:auto;overflow:visible}
svg text{fill:var(--muted);font:12px system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
svg .lab{fill:var(--fg);font-size:13px}svg .labb{fill:var(--fg);font-size:13px;font-weight:700}svg .num{fill:var(--fg);font-size:13px;font-variant-numeric:tabular-nums}
svg .tick{font-size:12px}svg .grid{stroke:var(--line);stroke-width:1}svg .cut{stroke:var(--fg);stroke-width:1.5;stroke-dasharray:3 3}
svg .midrow{fill:var(--soft)}
.controls{display:flex;flex-wrap:wrap;align-items:center;gap:8px 10px;margin:12px 0 4px}
select{font:inherit;padding:5px 8px;max-width:100%;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:5px}
button{font:inherit;font-size:14px;padding:5px 10px;border:1px solid var(--line);border-radius:5px;background:var(--bg);color:var(--fg);cursor:pointer}
button[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.presets{display:flex;flex-wrap:wrap;gap:6px}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:14px;color:var(--muted);margin:8px 0}.legend span{display:inline-flex;align-items:center;gap:6px}.legend svg{display:inline;width:auto}
.exp{display:grid;grid-template-columns:1fr 250px;gap:18px;align-items:start}
.facts{border:1px solid var(--line);border-radius:6px;padding:10px 14px;font-size:14px;background:var(--soft)}.facts h3{margin:2px 0 6px;font-size:15px}
.facts dl{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:4px 10px;margin:0}.facts dt{font-weight:400;color:var(--muted);margin:0}
.facts dd{margin:0;text-align:right;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.sliderrow{display:flex;align-items:center;gap:10px;margin:6px 0}.sliderrow input{flex:1}#daylab{font-variant-numeric:tabular-nums;min-width:90px}
#readout{min-height:3em;font-size:15px}
.tw{overflow-x:auto;margin:10px 0}
table{border-collapse:collapse;width:100%;font-size:14px}caption{text-align:left;color:var(--muted);padding:4px 0 6px;font-size:14px}
th,td{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}th{font-weight:600;background:var(--soft)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}td.h code{font-size:12px}
tr.final td{font-weight:600}
table.cal td.q{min-width:260px}table.cal td{font-size:13px}
.mx{width:auto;min-width:46%}.mx td.n{min-width:44px}.two{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-start}
.filters{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}.filters .n{font-variant-numeric:tabular-nums;opacity:.8}
ol.ledger{list-style:none;padding:0 12px 0 0;margin:0}.scroll{max-height:640px;overflow-y:auto;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}ol.ledger li{border-bottom:1px solid var(--line);padding:10px 0}
.lh{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}.claim{margin:4px 0;font-weight:500}.res{margin:4px 0;font-size:14px}.ev{margin:2px 0;font-size:13px;color:var(--muted)}
.badge{font-size:12px;font-weight:600;padding:1px 7px;border-radius:10px;border:1.5px solid}
.b-supported{color:var(--a2);border-color:var(--a2)}.b-refuted{color:var(--a1);border-color:var(--a1)}.b-not_significant{color:var(--muted);border-color:var(--muted);border-style:dashed}
.b-untestable{color:var(--muted);border-color:var(--line)}
.recall{border-left:3px solid var(--line);padding:2px 0 2px 14px;font-size:14px}.recall blockquote{margin:4px 0 8px;white-space:pre-wrap;color:var(--fg)}
.neg li{margin:6px 0}.check{font-size:16px}
figure{margin:14px 0}figure img{max-width:100%}figcaption{font-size:13px;color:var(--muted)}
@media (max-width:760px){.big{grid-template-columns:1fr}.exp{grid-template-columns:1fr}.terms dl{grid-template-columns:1fr}}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
"""

JS = r"""
(function(){
const D=JSON.parse(document.getElementById('explorer-data').textContent);
const byId={};D.series.forEach(s=>byId[s.id]=s);
const sel=document.getElementById('sel'),day=document.getElementById('day'),daylab=document.getElementById('daylab');
const strip=document.getElementById('strip'),hist=document.getElementById('hist'),readout=document.getElementById('readout'),facts=document.getElementById('facts');
const N=D.days.length;let cur=byId[D.default]||D.series[0],idx=N-1;
const e=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const f2=x=>x==null?'n/a':x.toFixed(2);
const COL={dyn:'var(--a1)',sta:'var(--a2)',mid:'var(--mid)',na:'var(--mid)'};
const CLS={dyn:'reprices often',sta:'static',mid:'in between',na:'rate unknown'};
function sym(c,x,y){
  if(c==='dyn')return `<path d="M${x} ${y-7} L${x+7} ${y} L${x} ${y+7} L${x-7} ${y} Z" fill="${COL[c]}"/>`;
  if(c==='mid')return `<rect x="${x-5}" y="${y-5}" width="10" height="10" fill="${COL[c]}"/>`;
  if(c==='na')return `<circle cx="${x}" cy="${y}" r="5" fill="var(--bg)" stroke="${COL[c]}" stroke-width="2"/>`;
  return `<circle cx="${x}" cy="${y}" r="6" fill="${COL[c]}"/>`;}
function ticks(a,b,n){let st=Math.pow(10,Math.floor(Math.log10((b-a)/n)));const r=(b-a)/n/st;st*=r>=7.5?10:r>=3.5?5:r>=1.5?2:1;
  const t=[];for(let v=Math.ceil(a/st)*st;v<=b+1e-9;v+=st)t.push(+v.toFixed(6));return t;}
function median(p){const n=p.length,lo=(n-1)>>1,hi=n>>1;return (p[lo]+p[hi])/2;}
function jumps(p){const n=p.length;if(n<2)return [null,null];
  if(n%2){const k=(n-1)/2;return [(p[k-1]+p[k])/2,(p[k]+p[k+1])/2];}
  return [p[n/2-1],p[n/2]];}
function domain(s){let lo=Infinity,hi=-Infinity;
  const up=v=>{if(v!=null){lo=Math.min(lo,v);hi=Math.max(hi,v);}};
  if(s.kind==='panel')s.offers.forEach(o=>o.v.forEach(up));else{s.groups.forEach(g=>{up(g.q[0]);up(g.q[2]);});s.med.forEach(up);}
  s.fc.forEach(f=>{up(f[1]);up(f[3]);});
  const core=s.med.filter(v=>v!=null).concat(s.fc.flatMap(f=>[f[1],f[3]]));
  if(s.kind==='panel'){lo=Math.max(lo,Math.min(...core)/1.4);hi=Math.min(hi,Math.max(...core)*1.4);}
  const pad=(hi-lo)*0.06||0.1;return [Math.max(0,lo-pad),hi+pad];}
const clamp=(v,a,b)=>Math.min(Math.max(v,a),b);
function today(s,i){if(s.kind!=='panel')return null;
  const o=s.offers.filter(o=>o.v[i]!=null).map(o=>({l:o.l,p:o.p,c:o.c,r:o.r,v:o.v[i]})).sort((a,b)=>a.v-b.v||a.l.localeCompare(b.l));
  return o;}
function drawStrip(){const s=cur,[d0,d1]=domain(s),W=720,L=215,R=105,RH=20,top=26;
  const X=v=>L+(clamp(v,d0,d1)-d0)/(d1-d0)*(W-L-R),off=v=>v<d0||v>d1;let rows,h,out=[];
  if(s.kind==='panel'){
    const o=today(s,idx),n=o.length,p=o.map(x=>x.v),m=n?median(p):null,[jd,ju]=jumps(p),lo=(n-1)>>1,hi=n>>1;
    rows=s.maxn;h=top+(rows+4.4)*RH+34;
    o.forEach((x,k)=>{const y=top+(n-1-k)*RH+RH/2,isMid=(k===lo||k===hi);
      if(isMid)out.push(`<rect x="0" y="${y-RH/2}" width="${W-R+10}" height="${RH}" class="midrow"/>`);
      out.push(`<text x="${L-12}" y="${y+4}" text-anchor="end" class="${isMid?'labb':'lab'}">${e(x.l)}</text>`);
      out.push(`<line x1="${L}" x2="${X(x.v)}" y1="${y}" y2="${y}" class="grid" stroke-dasharray="1 3"/>`);
      out.push(`<g>${off(x.v)?`<text x="${X(x.v)+(x.v>d1?3:-3)}" y="${y+4}" text-anchor="${x.v>d1?'start':'end'}" class="labb">${x.v>d1?'›':'‹'}</text>`:''}${sym(x.c,X(x.v),y)}<title>${e(x.l)}: ${f2(x.v)} USD per GPU-hour; ${CLS[x.c]}${x.r!=null?' ('+Math.round(x.r*100)+'% of days in the 21 days to 6 Nov)':''}</title></g>`);
      out.push(`<text x="${X(x.v)+(off(x.v)&&x.v>d1?16:10)}" y="${y+4}" class="tick">${f2(x.v)}${off(x.v)?' (off scale)':''}</text>`);});
    const yb=top+rows*RH;
    if(m!=null){out.push(`<line x1="${X(m)}" x2="${X(m)}" y1="${top-8}" y2="${yb}" stroke="var(--fg)" stroke-width="2.5"/>`);
      out.push(`<text x="${X(m)}" y="${top-12}" text-anchor="middle" class="labb">median ${f2(m)}</text>`);}
    [jd,ju].forEach((v,j)=>{if(v!=null&&Math.abs(v-m)>1e-9){out.push(`<line x1="${X(v)}" x2="${X(v)}" y1="${top}" y2="${yb}" stroke="var(--fg)" stroke-dasharray="4 3"/>`);
      out.push(`<text x="${X(v)+(j?4:-4)}" y="${yb+13}" text-anchor="${j?'start':'end'}" class="tick">${f2(v)}</text>`);}});
  }else{
    rows=s.groups.length+2;h=top+(rows+4.4)*RH+34;
    s.groups.forEach((g,k)=>{const y=top+k*RH*1.4+RH/2;
      out.push(`<text x="${L-12}" y="${y+4}" text-anchor="end" class="lab">${e(g.p)} (${g.n.toLocaleString('en')} zone rows)</text>`);
      out.push(`<line x1="${X(g.q[0])}" x2="${X(g.q[2])}" y1="${y}" y2="${y}" stroke="${COL[g.c]}" stroke-width="4"/>`);
      out.push(`<g>${sym(g.c,X(g.q[1]),y)}<title>${e(g.p)}: 10th to 90th percentile ${f2(g.q[0])} to ${f2(g.q[2])}, median ${f2(g.q[1])}</title></g>`);});
    const m=s.origin_median,yb=top+rows*RH;
    out.push(`<line x1="${X(m)}" x2="${X(m)}" y1="${top-8}" y2="${yb}" stroke="var(--fg)" stroke-width="2.5"/><text x="${X(m)}" y="${top-12}" text-anchor="middle" class="labb">median ${f2(m)}</text>`);}
  const yf=top+(rows+1.2)*RH,lbl={1:'+1 day (7 Nov)',3:'+3 days (9 Nov)',7:'+7 days (13 Nov)'};
  out.push(`<text x="${L-12}" y="${yf-8}" text-anchor="end" class="tick">forecast made on 6 Nov:</text>`);
  s.fc.forEach((f,k)=>{const y=yf+k*RH+RH/2;
    out.push(`<text x="${L-12}" y="${y+4}" text-anchor="end" class="lab">${lbl[f[0]]}</text>`);
    out.push(`<line x1="${X(f[1])}" x2="${X(f[3])}" y1="${y}" y2="${y}" stroke="var(--fg)" stroke-width="5" opacity="0.35"/>`);
    out.push(`<line x1="${X(f[2])}" x2="${X(f[2])}" y1="${y-7}" y2="${y+7}" stroke="var(--fg)" stroke-width="2.5"><title>10th ${f2(f[1])}, median ${f2(f[2])}, 90th ${f2(f[3])}</title></line>`);
    out.push(`<text x="${X(f[3])+8}" y="${y+4}" class="num">${f2(f[1])} | ${f2(f[2])} | ${f2(f[3])}</text>`);});
  const ya=h-30;out.push(`<line x1="${L}" x2="${W-R}" y1="${ya}" y2="${ya}" stroke="var(--line)"/>`);
  ticks(d0,d1,7).forEach(t=>out.push(`<line x1="${X(t)}" x2="${X(t)}" y1="${ya}" y2="${ya+5}" stroke="var(--line)"/><text x="${X(t)}" y="${ya+18}" text-anchor="middle" class="tick">${t.toFixed(2)}</text>`));
  out.push(`<text x="${L-12}" y="${ya+18}" text-anchor="end" class="tick">USD per GPU-hour</text>`);
  strip.innerHTML=`<svg viewBox="0 0 ${W} ${h}" role="img" aria-label="Offers on ${e(D.days[idx])} along the price axis with the median and the forecast">${out.join('')}</svg>`;}
function path(vals,X,Y,med){let d='',pen=false;vals.forEach((v,i)=>{if(med[i]==null)return;if(v==null){pen=false;return;}d+=(pen?'L':'M')+X(i).toFixed(1)+' '+Y(v).toFixed(1);pen=true;});return d;}
function drawHist(){const s=cur,[d0,d1]=domain(s),W=960,H=300,L=60,R=30,T=16,B=40,xmax=N-1+8;
  const X=i=>L+i/xmax*(W-L-R),Y=v=>T+(1-(v-d0)/(d1-d0))*(H-T-B),out=[],lines=[];
  out.push(`<rect x="${X(N-0.5)}" y="${T}" width="${X(xmax)-X(N-0.5)}" height="${H-T-B}" fill="var(--soft)"/><text x="${X(N+3)}" y="${T+14}" text-anchor="middle" class="tick">forecast</text>`);
  ticks(d0,d1,6).forEach(t=>out.push(`<line x1="${L}" x2="${W-R}" y1="${Y(t)}" y2="${Y(t)}" class="grid"/><text x="${L-6}" y="${Y(t)+4}" text-anchor="end" class="tick">${t.toFixed(2)}</text>`));
  for(let i=N-1;i>=0;i-=7)out.push(`<text x="${X(i)}" y="${H-B+16}" text-anchor="middle" class="tick">${e(D.labels[i])}</text><line x1="${X(i)}" x2="${X(i)}" y1="${H-B}" y2="${H-B+4}" stroke="var(--line)"/>`);
  out.push(`<text x="${L}" y="${H-4}" class="tick">USD per GPU-hour, daily, ${e(D.labels[0])} to ${e(D.labels[N-1])} 2026</text>`);
  if(s.kind==='panel')s.offers.forEach(o=>{const d=path(o.v,X,Y,s.med);if(d)lines.push(`<path d="${d}" fill="none" stroke="${COL[o.c]}" stroke-width="1.6" opacity="0.6"><title>${e(o.l)}</title></path>`);});
  lines.push(`<path d="${path(s.med,X,Y,s.med)}" fill="none" stroke="var(--fg)" stroke-width="2.6"><title>median</title></path>`);
  out.push(`<clipPath id="hclip"><rect x="${L}" y="${T}" width="${W-L-R}" height="${H-T-B}"/></clipPath><g clip-path="url(#hclip)">${lines.join('')}</g>`);
  if(s.med.some(v=>v==null))out.push(`<text x="${W-R}" y="${H-4}" text-anchor="end" class="tick">lines are joined across days the collector did not publish</text>`);
  s.fc.forEach(f=>{const x=X(N-1+f[0]);out.push(`<line x1="${x}" x2="${x}" y1="${Y(f[1])}" y2="${Y(f[3])}" stroke="var(--fg)" stroke-width="6" opacity="0.3"/><circle cx="${x}" cy="${Y(f[2])}" r="4" fill="var(--fg)"><title>+${f[0]} days: ${f2(f[1])} to ${f2(f[3])}, median ${f2(f[2])}</title></circle>`);});
  if(s.kind==='panel')out.push(`<line x1="${X(idx)}" x2="${X(idx)}" y1="${T}" y2="${H-B}" stroke="var(--fg)" stroke-dasharray="2 3"/>`);
  hist.innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Offers and median over the previous ${N} days with the forecast">${out.join('')}</svg>`;}
function drawFacts(){const c=cur.card,pct=v=>v==null?'n/a':v.toFixed(1)+'%';
  const rows=[['Offers',c.offers],['Providers',c.providers],['Middle offer held by',e(c.mid.split('|').join(', '))],
   ['Their 21-day repricing rate',c.mid_rate21==null?'n/a':Math.round(c.mid_rate21*100)+'% of days'],
   ['Median move if one offer leaves',pct(c.frag)],['If one provider leaves',pct(c.pfrag)],
   ['Largest pass-through of a 10% repricing',c.pt==null?'n/a':Math.round(c.pt*100)+'% ('+e(c.pt_provider)+')'],
   ['Gap between neighbours of the middle',pct(c.gap)],['Days the median moved, last 60',c.moved60==null?'n/a':Math.round(c.moved60*100)+'%'],
   ['Robust enough to use alone as an index',c.alone?'yes':'no'],
   ['Forecast members used',cur.members?e(cur.members.join(', ')):'all seven'],
   ['Zero-width forecast (activity gate)',cur.gated.length?'yes, horizons '+cur.gated.join(', '):'no']];
  facts.innerHTML=rows.map(r=>`<dt>${r[0]}</dt><dd>${r[1]}</dd>`).join('');}
function drawReadout(){const s=cur;daylab.textContent=D.labels[idx]+' 2026';
  day.setAttribute('aria-valuetext',D.labels[idx]+' 2026');
  if(s.kind!=='panel'){readout.textContent=`This series is the median of ${s.rows.toLocaleString('en')} availability-zone rows from ${s.groups.length} hyperscalers on 6 November, so offers are summarised by provider (bar: 10th to 90th percentile across zones). The slider is not used; the lower chart shows the median for the previous ${N} days.`;return;}
  const o=today(s,idx),n=o.length;if(!n){readout.textContent='No offers on this day.';return;}
  const p=o.map(x=>x.v),m=median(p),[jd,ju]=jumps(p),lo=(n-1)>>1,hi=n>>1;
  const mid=[...new Set([o[lo],o[hi]].map(x=>x.l+' ('+CLS[x.c]+')'))].join(' and ');
  const provs=new Set(o.map(x=>x.p)).size;
  readout.innerHTML=`<b>${e(D.labels[idx])}:</b> median ${f2(m)} USD per GPU-hour from ${n} offers by ${provs} providers. The middle ${lo===hi?'offer is':'offers are'} ${e(mid)}. `+
    (jd!=null?`If one offer left or joined, the median would move to ${f2(jd)} or ${f2(ju)}.`:'');}
function draw(){drawStrip();drawHist();drawFacts();drawReadout();
  day.disabled=cur.kind!=='panel';document.querySelectorAll('#presets button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.sid===cur.id?'true':'false'));
  const pr=D.presets.find(p=>p[0]===cur.id);document.getElementById('preset-note').textContent=pr?pr[1]+'. Drag the day slider from late September to 6 November and watch the coloured offers move past the middle.':'';}
D.series.forEach(s=>{const op=document.createElement('option');op.value=s.id;op.textContent=s.name;sel.appendChild(op);});
const pz=document.getElementById('presets');D.presets.forEach(p=>{const b=document.createElement('button');b.type='button';b.dataset.sid=p[0];b.textContent=byId[p[0]].name.split(' (')[0];b.title=p[1];
  b.addEventListener('click',()=>{cur=byId[p[0]];sel.value=cur.id;idx=N-1;day.value=idx;draw();});pz.appendChild(b);});
const hp=new URLSearchParams(location.hash.slice(1));
if(byId[hp.get('s')])cur=byId[hp.get('s')];
if(hp.has('d')&&+hp.get('d')>=0&&+hp.get('d')<N){idx=+hp.get('d');day.value=idx;}
const keep=()=>{try{history.replaceState(null,'','#s='+encodeURIComponent(cur.id)+'&d='+idx);}catch(err){}};
sel.value=cur.id;sel.addEventListener('change',()=>{cur=byId[sel.value];idx=N-1;day.value=idx;draw();keep();});
day.addEventListener('input',()=>{idx=+day.value;drawStrip();drawReadout();drawHist();keep();});
pz.addEventListener('click',keep);
draw();
const items=[...document.querySelectorAll('#ledger li')],cnt=document.getElementById('ledger-count');
document.querySelectorAll('.flt').forEach(b=>b.addEventListener('click',()=>{const f=b.dataset.f;
  document.querySelectorAll('.flt').forEach(x=>x.setAttribute('aria-pressed',x===b?'true':'false'));
  let k=0;items.forEach(li=>{const on=f==='all'||li.dataset.s===f;li.hidden=!on;if(on)k++;});
  cnt.textContent=f==='all'?`Showing all ${k} hypotheses.`:`Showing ${k} of ${items.length} hypotheses (${b.firstChild.textContent.trim()}).`;}));
})();
"""

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forecasting posted GPU rental prices from the offers behind each median</title>
<style>%%CSS%%</style>
</head>
<body>
<nav aria-label="Sections"><ol>
<li><a href="#s1">Result</a></li><li><a href="#s2">Panel explorer</a></li><li><a href="#s3">How it improved</a></li><li><a href="#s4">Ledger</a></li>
<li><a href="#s5">Search (Exa)</a></li><li><a href="#s6">Shared memory</a></li><li><a href="#s7">2 to 3 years</a></li><li><a href="#s8">Reproduce</a></li></ol></nav>
<main>
%%BODY%%
</main>
<script type="application/json" id="explorer-data">%%DATA%%</script>
<script type="application/json" id="facts-data">%%FACTS%%</script>
<script>%%JS%%</script>
</body>
</html>
"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build the self-contained demo page (no network, no scoring).")
    ap.add_argument("--out", type=Path, default=OUT)
    p = build(ap.parse_args().out)
    print(f"{p}  {p.stat().st_size:,} bytes  sha256 {sha(p)}")
