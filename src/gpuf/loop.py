"""The research loop as one non-interactive CLI: python -m gpuf.loop STEP ...

autopsy   score a system on dev, attribute its loss to causes, write each cause to past.dev as `autopsy` (gpuf-failures)
scout     recall failure cases without a dated explanation (as `scout`), search Exa for announcements bounded by --as-of,
          extract dated changes with the calendar agent's rules, append them to the calendar, write sources (gpuf-evidence)
prior     before spending compute: memory recall (as `proposer`) and an Exa search for prior work on a claim
propose   rank open causes by residual loss share from the latest autopsy and the memory briefing (rule-based)
gate      the dev gate of EVAL_PROTOCOL.md Amendment 2 rule 1; writes the ledger, syncs it to memory as `experimenter`
forecast  date-bounded calendar refresh (memory as `forecaster` and the local file), then a forecast file; never scores
status    ledger, validation queries, calendar, memory counts, Exa spend

Every step prints JSON and appends one line to data_out/loop_journal.jsonl (keys scrubbed). LOOP_OFFLINE=1: no network;
Exa answers come from data_out/exa_cache only (uncached requests are skipped and counted), past.dev replays its journal
(PAST_OFFLINE=1 is set). Live past.dev calls need PAST_ALLOW_WRITES=1. Exa is called only through `_exa` below.
Paths can be redirected (tests): LOOP_JOURNAL, LOOP_CALENDAR, LOOP_RUNS, PAST_JOURNAL, PAST_LEDGER.
"""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA_OUT = ROOT / "data_out"
CALDIR = ROOT / "experiments" / "calendar"
SHIP = ROOT / "experiments" / "loop"
CUTOFF = dt.date(2026, 11, 6)
DEV_CUT = dt.date(2026, 9, 11).toordinal()
K = ["series_id", "origin_day", "horizon_days"]
MIX = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
FM2 = ["fm2", {"grids": ["runs/fm2/grid_bs16_rental_headline.parquet"], "lo": 0.15}]
ANA = ["analog", {"pool": "all", "k": 600, "drop": ["n14", "sign"]}]
PRV = ["prov", {"L": 1, "W": 21, "gate": "dyn"}]
ALIASES = {"mix": MIX, "drift": ["drift", {}], "ens4": ["ens", {"members": [MIX, FM2, ANA, PRV]}],
           "fragility_b20": ["fragility", {"mode": "mix", "boost": 20, "bkind": "any"}]}
ALIASES["ens4_mix_fm2_analog_prov"] = ALIASES["ens4"]
EST = {"search": 0.007, "contents": 0.001}   # USD per call, the observed price of every cached call of each kind
CAUSES = ["none", "dynamic_reprice", "announced_oneoff", "unannounced_oneoff", "entry", "exit", "marketplace_ask", "hyperscaler_spot"]
DEFS = {  # experiments/autopsy2/protocol.yaml, priority order
    "hyperscaler_spot": "afhubbard hyperscaler spot series (no offer panel).",
    "none": "the price did not move between origin and target: the loss is interval width.",
    "marketplace_ask": "the marketplace ask series moved.",
    "entry": "composition-dominated move: an offer entered the panel near the middle.",
    "exit": "composition-dominated move: an offer left the panel, none entered.",
    "dynamic_reprice": "repricing-dominated move; the pivotal provider repriced on >15% of days in the 21 days to the origin.",
    "announced_oneoff": "repricing by a static provider with a calendar entry published on or before the origin, effective in (origin, target].",
    "unannounced_oneoff": "repricing by a static provider with no usable calendar entry.",
}
# Which ledger hypotheses target which cause: word-bounded patterns searched in claim + failure_mode (rule-based)
CAUSE_TERMS = {
    "none": [r"activity gate", r"zero width", r"interval width", r"width ignores"],
    "dynamic_reprice": [r"\bdynamic", r"signed repricing", r"repricing state", r"recent signed", r"changed recently"],
    "announced_oneoff": [r"\bannounc", r"\bcalendar", r"\bheadlines?\b"],
    "unannounced_oneoff": [r"\bunannounced", r"\bone-off", r"\blead(s|ing)?\b", r"\bfootprint"],
    "entry": [r"\bentr(y|ies|ant|ants)\b", r"\benter", r"\bcomposition", r"\bmembership", r"one-offer-in", r"provider-mix"],
    "exit": [r"\bexits?\b", r"\bleav(e|es|ing)\b", r"\bcomposition", r"\bmembership", r"one-offer-out", r"provider-mix"],
    "marketplace_ask": [r"\bmarketplace", r"\bvolatility", r"\bpretrained"],
    "hyperscaler_spot": [r"\bhyperscaler", r"\bafhubbard", r"\bspot\b"],
}


# ----------------------------------------------------------------------------- plumbing
def offline() -> bool:
    return os.environ.get("LOOP_OFFLINE", "") not in ("", "0")


def _p(env: str, default: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(os.environ.get(env) or default)


def journal_path():
    return _p("LOOP_JOURNAL", DATA_OUT / "loop_journal.jsonl")


def cal_path():
    return _p("LOOP_CALENDAR", DATA_OUT / "repricing_calendar.jsonl")


def runs_dir():
    d = _p("LOOP_RUNS", ROOT / "runs" / "loop")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _secrets() -> list[str]:
    out = []
    try:
        from .scout import _key
        out.append(_key())
    except Exception:
        pass
    from .memory import _key as pk
    out.append(pk(False))
    return [s for s in out if s and len(s) > 6]


def _scrub(text: str) -> str:
    for s in _secrets():
        text = text.replace(s, "***")
    return re.sub(r"past_(sk|mk)_[A-Za-z0-9_\-]+", "past_\\1_***", text)


def _log(step: str, argv: list[str], out: dict) -> None:
    rec = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "step": step, "argv": argv,
           "offline": offline(), "result": out}
    p = journal_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(_scrub(json.dumps(rec, default=str, sort_keys=True)) + "\n")


def _journal() -> list[dict]:
    p = journal_path()
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def _sha(o, n=12) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True).encode()).hexdigest()[:n]


def _day(s) -> int:
    return dt.date.fromisoformat(str(s)[:10]).toordinal()


def _date(o: int) -> str:
    return str(dt.date.fromordinal(int(o)))


def spec_of(s: str) -> tuple[str, list]:
    """NAME (alias), JSON [method, params], or FILE.json:KEY (a halves.py spec). Returns (slug, spec)."""
    if s in ALIASES:
        return s, ALIASES[s]
    if s.lstrip().startswith("["):
        sp = json.loads(s)
        return "spec-" + _sha(sp, 8), sp
    if ":" in s and s.split(":")[0].endswith(".json"):
        f, k = s.split(":", 1)
        return k, json.load(open(ROOT / f if not os.path.isabs(f) else f))["cands"][k]
    raise SystemExit(f"error: unknown system {s!r}; use one of {sorted(ALIASES)}, a JSON [method, params], or FILE.json:KEY\n"
                     f"  python -m gpuf.loop autopsy --system ens4")


def _calsys():
    if str(CALDIR) not in sys.path:
        sys.path.insert(0, str(CALDIR))
    import calendar_lib, providers, search  # experiments/calendar (read-only, imported)
    return calendar_lib, providers, search


def cal_entries() -> list[dict]:
    p = cal_path()
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def usable(entries, origin_day: int, min_conf: str = "B") -> list[dict]:
    """calendar_lib.scheduled_changes on our calendar path: published on or before the origin, confidence A..min_conf."""
    return [e for e in entries if _day(e["published"]) <= origin_day and e["confidence"] <= min_conf]


# ----------------------------------------------------------------------------- Exa (every Exa call of the loop goes here)
class Budget:
    def __init__(self, cap: float):
        self.cap, self.spent, self.errors = cap, 0.0, 0
        self.hits, self.new, self.skipped_budget, self.skipped_offline = ({"search": 0, "contents": 0} for _ in range(4))

    def report(self) -> dict:
        return {"cache_hits": self.hits, "new_calls": self.new, "skipped_over_budget": self.skipped_budget,
                "skipped_offline_uncached": self.skipped_offline, "api_errors": self.errors, "cost_usd_this_run": round(self.spent, 4),
                "cap_usd": self.cap}


def _exa(endpoint: str, body: dict, budget: Budget, lookup=("cal", "loop"), tag: str = "loop") -> dict | None:
    """Cached Exa call through gpuf.scout.exa_call. The cache is looked up under each tag in `lookup` (the calendar agent's
    identical requests are reused); a new request is written under `tag`. Offline or over budget: returns None, no network."""
    from . import scout
    if endpoint == "search":
        end = body.get("endPublishedDate")
        assert end and dt.date.fromisoformat(end[:10]) <= CUTOFF, "every search needs endPublishedDate <= 2026-11-06"
    h = hashlib.sha256(f"{endpoint}|{json.dumps(body, sort_keys=True)}".encode()).hexdigest()[:20]   # = scout.exa_call's key
    for t in lookup:
        p = scout.CACHE / f"{t}_{endpoint}_{h}.json"
        if p.exists():
            budget.hits[endpoint] += 1
            return json.loads(p.read_text())
    if offline():
        budget.skipped_offline[endpoint] += 1
        return None
    if budget.spent + EST[endpoint] > budget.cap + 1e-9:
        budget.skipped_budget[endpoint] += 1
        return None
    rec = scout.exa_call(endpoint, body, tag=tag)
    budget.new[endpoint] += 1
    budget.spent += float(rec["cost"] if rec.get("cost") is not None else 0 if rec.get("error") else EST[endpoint])
    budget.errors += bool(rec.get("error"))
    return rec


def exa_spend_all() -> dict:
    from . import scout
    out = {}
    for p in scout.CACHE.glob("*.json"):
        tag = p.name.split("_")[0] if not p.name[:4].isdigit() else "day_scout"
        out[tag] = out.get(tag, 0.0) + float(json.loads(p.read_text()).get("cost") or 0)
    out = {k: round(v, 4) for k, v in sorted(out.items())}
    out["total"] = round(sum(out.values()), 4)
    return out


# ----------------------------------------------------------------------------- memory helpers
def _mem():
    from . import memory
    if offline():
        os.environ["PAST_OFFLINE"] = "1"
    return memory


def _ledger():
    """gpuf.ledger with its path following PAST_LEDGER (the same file memory.sync_ledger reads)."""
    from . import ledger
    if os.environ.get("PAST_LEDGER"):
        ledger.PATH = pathlib.Path(os.environ["PAST_LEDGER"])
    return ledger


def _mem_items() -> dict[str, dict]:
    """Latest version of every data point written through the memory journal, by id."""
    out = {}
    for r in _mem()._read_journal():
        if r["op"] == "ingest":
            for it in r["request"]["body"]["items"]:
                out[it["id"]] = {**it, "_journal_time": r["time"]}
    return out


def _recall(query: str, identity: str, as_of=None, limit: int = 100) -> tuple[list[dict], str | None]:
    m = _mem()
    try:
        resp = m.recall(query, identity, agent=identity, as_of=as_of, limit=limit)
        return m._dedupe(resp, limit), None
    except m.PastError as e:
        return [], str(e)


def _write(items: list[dict], agent: str) -> dict:
    m = _mem()
    try:
        r = m.ingest(items, agent=agent)
        w = m.wait(r["ingestionId"])
        un = sum(bool(x.get("unchanged")) for x in (r.get("items") or []))
        return {"sent": len(items), "ids": [i["id"] for i in items], "status": w.get("status"), "unchanged": un, "offline": m.offline()}
    except m.PastError as e:
        return {"sent": 0, "error": str(e)}


# ----------------------------------------------------------------------------- autopsy (port of experiments/autopsy2 labelling)
def _first(s):
    return next((x for x in str(s).split(",") if x and x not in ("nan", "None")), None)


def labels():
    """Cause of every dev headline cell (experiments/autopsy2/analyse.py, ported; the calendar is read from cal_path()).
    Cached by calendar content; experiments/loop/cause_labels.parquet ships the labels for the committed calendar."""
    import numpy as np
    import pandas as pd
    calh = hashlib.sha256(cal_path().read_bytes()).hexdigest()[:12]
    cache = runs_dir() / f"labels_{calh}.parquet"
    if cache.exists():
        return pd.read_parquet(cache), f"cache {cache.name}"
    meta = SHIP / "cause_labels.json"
    if meta.exists() and json.loads(meta.read_text()).get("calendar_sha") == calh:
        return pd.read_parquet(SHIP / "cause_labels.parquet"), "shipped experiments/loop/cause_labels.parquet"
    panel_p = ROOT / "runs/autopsy/panel.parquet"
    if not panel_p.exists():
        raise SystemExit("error: the calendar changed and runs/autopsy/panel.parquet (offer panel from experiments/autopsy) is missing, "
                         "so cause labels cannot be recomputed")
    CL, _, _ = _calsys()
    ents = cal_entries()
    CUT = pd.Timestamp("2026-10-13")
    hd = pd.read_parquet(ROOT / "experiments/autopsy/results/hday_cells_dev.parquet")
    b = hd[K + ["origin_date", "source_id", "instrument_class", "y", "baseline", "cause", "rep_shapley", "comp_shapley", "n_entered",
                "prov_entered", "prov_exited", "prov_reprice_up", "prov_reprice_down", "pivotal"]].copy()
    b["o"] = pd.to_datetime(b.origin_date)
    b["t"] = b.o + pd.to_timedelta(b.horizon_days, unit="D")
    b["gpu"] = b.series_id.str.split(".").str[2].str.replace("_", " ")
    b["tier"] = b.series_id.str.split(".").str[3]
    pan = pd.read_parquet(panel_p, columns=["series_id", "source_id", "dt", "provider", "offer", "usd_per_gpu_hour"])
    pan = pan[(pan.dt <= CUT) & (pan.source_id != "afhubbard")]
    po = pan.groupby(["source_id", "series_id", "provider", "offer", "dt"]).usd_per_gpu_hour.mean().rename("p").reset_index()
    po = po.sort_values(["series_id", "offer", "dt"])
    po["dp"] = po.groupby(["series_id", "offer"]).p.diff()
    po["rep"] = po.dp.abs() > 1e-9
    pdd = po[po.dp.notna()].groupby(["source_id", "provider", "dt"]).agg(rep=("rep", "any")).reset_index()
    idx = {k: g.set_index("dt") for k, g in pdd.groupby(["source_id", "provider"])}

    def rate(src, pv, o, W=21):
        g = idx.get((src, pv))
        if g is None:
            return 0.0
        w = g[(g.index > o - pd.Timedelta(days=W)) & (g.index <= o)]
        return float(w.rep.mean()) if len(w) else 0.0

    def announced(pv, gpu, tier, src, o, t):
        if pv is None:
            return False
        od, td = o.toordinal(), t.toordinal()
        for e in usable(ents, od):
            ed = CL.effective_day(e) + CL.COLLECTOR_LAG.get(src, 0)
            if e["provider"] == pv and od < ed <= td and any(gpu in c["panel_gpus"] and tier in CL.TIER_MAP.get(c["tier"], set()) for c in e["changes"]):
                return True
        return False

    labs, provs, rates = [], [], []
    for r in b.itertuples():
        pv, rt = None, np.nan
        if abs(r.y - r.baseline) <= 1e-9:
            lab = "none"
        elif r.source_id == "afhubbard":
            lab = "hyperscaler_spot"
        elif r.instrument_class == "marketplace_ask":
            lab, pv = "marketplace_ask", _first(r.pivotal) or _first(r.prov_reprice_up) or _first(r.prov_reprice_down)
        else:
            compo = r.cause == "composition" or (r.cause == "mixed" and abs(r.comp_shapley) > abs(r.rep_shapley))
            pv = _first(r.pivotal)
            if compo:
                ent, ex = set(str(r.prov_entered).split(",")), set(str(r.prov_exited).split(","))
                lab = "entry" if pv in ent else "exit" if pv in ex else ("entry" if r.n_entered > 0 else "exit")
                pv = pv or _first(r.prov_entered if lab == "entry" else r.prov_exited)
            else:
                pv = pv or _first(r.prov_reprice_up) or _first(r.prov_reprice_down)
                rt = rate(r.source_id, pv, r.o)
                lab = "dynamic_reprice" if rt > 0.15 else "announced_oneoff" if announced(pv, r.gpu, r.tier, r.source_id, r.o, r.t) else "unannounced_oneoff"
        labs.append(lab); provs.append(pv); rates.append(rt)
    out = b[K + ["origin_date", "source_id", "instrument_class"]].assign(cause2=labs, provider=provs, prov_rate21=rates)
    out.to_parquet(cache)
    return out, f"computed from the offer panel ({cache.name})"


def system_cells(spec: list):
    """Dev headline cells of a system through the harness, cached under runs/loop/cells (dev only)."""
    import pandas as pd
    p = runs_dir() / "cells" / f"{_sha(spec)}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    from . import harness, methods
    m, prm = spec
    c = harness.evaluate(methods.get(m, **prm), "dev", "rental_headline", name=m, params=prm).cells
    p.parent.mkdir(parents=True, exist_ok=True)
    c.to_parquet(p)
    return c


def _skill(c) -> float:
    return float(1 - c.loss.sum() / c.baseline_loss.sum())


def step_autopsy(a) -> dict:
    slug, spec = spec_of(a.system)
    lab, src = labels()
    c = system_cells(spec)
    b = c[K + ["q10", "q50", "q90", "y", "baseline", "loss", "baseline_loss"]].merge(lab, on=K, how="inner", validate="one_to_one")
    assert len(b) == len(c), f"label join lost cells: {len(b)} of {len(c)}"
    LV, TL = b.baseline_loss.sum(), b.loss.sum()
    rows, items = [], []
    for cause in CAUSES:
        g = b[b.cause2 == cause]
        lv = g.baseline_loss.sum()
        top = g.sort_values("loss", ascending=False).head(3)
        ex = [f"{r.origin_date} h={r.horizon_days} {r.series_id}: {r.provider or '?'}, {r.baseline:.3f} -> {r.y:.3f}; "
              f"q10 {r.q10:.3f} q50 {r.q50:.3f} q90 {r.q90:.3f}" for r in top.itertuples() if r.loss > 0]
        row = {"cause": cause, "cells": int(len(g)), "share_of_lv_loss": round(float(lv / LV), 4),
               "loss_over_lv": round(float(g.loss.sum() / lv), 4) if lv > 0 else None,
               "residual_share": round(float(g.loss.sum() / TL), 4), "points_of_lv": round(float(g.loss.sum() / LV), 4), "examples": ex}
        rows.append(row)
        txt = (f"Autopsy failure mode (cause) {cause} of system {slug} on dev headline (written by autopsy via gpuf.loop)\n"
               f"id: {cause}\ndefinition: {DEFS[cause]}\nsystem: {slug} {json.dumps(spec)}\ncells: {row['cells']} of {len(b)}\n"
               f"share_of_system_loss: {row['residual_share']}\nshare_of_last_value_loss: {row['share_of_lv_loss']}\n"
               f"system_loss_over_last_value_loss: {row['loss_over_lv']}\nsystem dev skill: {_skill(b):.4f}\n"
               f"Dated failure cases (largest system loss): " + (" | ".join(ex) if ex else "none"))
        items.append({"id": f"autopsy-loop-{slug}-{cause}"[:120], "audience": "gpuf-failures", "identity": "autopsy",
                      "timestamp": "2026-10-13T23:59:59Z", "label": f"Failure mode: {cause} ({slug})", "content": txt,
                      "metadata": {"agent": "autopsy", "kind": "failure_mode", "cause": cause, "system": slug, "source": "gpuf.loop autopsy"}})
    text = [f"{'cause':<20}{'cells':>6}{'LV share':>10}{'loss/LV':>9}{'residual':>10}"]
    text += [f"{r['cause']:<20}{r['cells']:>6}{r['share_of_lv_loss']:>10.3f}" + (f"{r['loss_over_lv']:>9.3f}" if r["loss_over_lv"] is not None else f"{'-':>9}")
             + f"{r['residual_share']:>10.3f}" for r in rows]
    text.append(f"{'total':<20}{len(b):>6}{1.0:>10.3f}{TL / LV:>9.3f}{1.0:>10.3f}")
    return {"system": slug, "spec": spec, "n_cells": int(len(b)), "dev_skill": round(_skill(b), 4),
            "dev_skill_first_half": round(_skill(b[b.origin_day <= DEV_CUT]), 4), "dev_skill_second_half": round(_skill(b[b.origin_day > DEV_CUT]), 4),
            "labels": src, "table": rows, "table_text": "\n".join(text),
            "memory": _write(items, "autopsy") if not a.no_memory else {"skipped": "--no-memory"}}


# ----------------------------------------------------------------------------- scout
MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
DATE_RX = re.compile(r"((jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+20\d\d)?|\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:\s+20\d\d)?|20\d\d-\d\d-\d\d)", re.I)
# experiments/calendar/triage.py
CHG = re.compile(r"(rais\w*|increas\w*|hik\w*|cut\w*|lower\w*|reduc\w*|drop\w*|new (gpu )?(rates|prices|pricing)|price (change|update|adjust)\w*|repric\w*)", re.I)
PRICE = re.compile(r"(price|pricing|rate|\$\s?\d|/hr|per hour|gpu-hour)", re.I)
EFF = re.compile(r"(effective|starting|from|beginning|as of|on|takes? effect)\s+(on\s+)?(the\s+)?((jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\.?\s+\d{1,2}|\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*|20\d\d-\d\d-\d\d)", re.I)
GPU = re.compile(r"(gpu|h100|h200|b200|b300|a100|l40s|rtx|mi300|mi325|mi355|a10|l4\b|t4\b)", re.I)
GPU_TOK = re.compile(r"(H100|H200|B200|B300|A100\s*(?:SXM\s*)?(?:80|40)\s*GB|A100|L40S|RTX\s*PRO\s*6000|RTX\s*5090|RTX\s*4090|MI300X)", re.I)
NUM = r"\$\s?(\d{1,3}(?:\.\d{1,3})?)"
UNIT = r"(?:\s*(?:per\s+GPU[- ]hour|/\s*GPU[- ]h(?:ou)?r|/hr|/hour|an hour|per hour))?"
PAIRS = [(re.compile(NUM + UNIT + r"\s*(?:->|→|to)\s*" + NUM, re.I), False),
         (re.compile(NUM + UNIT + r"[^$]{0,30}?instead of\s*" + NUM, re.I), True)]
# evergreen pricing guides ("X GPU Pricing 2026", "Per-Hour Cost") are rewritten in place: treated like trackers, never extracted
EVERGREEN = re.compile(r"(pricing\s*\(?20\d\d\)?|per[- ]hour cost|pricing (guide|explained|breakdown)|how much does|cost of renting|price list)", re.I)
SENT = re.compile(r"(?<=[.!?])\s+|\n+")


def _parse_date(s: str, year: int = 2026) -> dt.date | None:
    s = s.strip()
    try:
        if re.match(r"20\d\d-\d\d-\d\d", s):
            return dt.date.fromisoformat(s[:10])
        w = re.findall(r"[A-Za-z]+|\d+", s)
        mon = next(MON[x[:3].lower()] for x in w if x[:3].lower() in MON)
        nums = [int(x) for x in w if x.isdigit()]
        y = next((n for n in nums if n > 1900), year)
        return dt.date(y, mon, next(n for n in nums if n < 32))
    except (StopIteration, ValueError):
        return None


def _gpu_panel(tok: str) -> list[str]:
    t = re.sub(r"\s+", " ", tok.upper()).replace("SXM ", "")
    if t.startswith("A100"):
        return ["A100 40GB"] if "40" in t else ["A100 SXM 80GB", "A100 80GB"]
    return {"H100": ["H100 SXM 80GB", "H100 80GB"], "RTX PRO 6000": ["RTX PRO 6000"]}.get(t, [t])


def extract_announcement(text: str, published: dt.date) -> tuple[dt.date | None, list[dict], str]:
    """The calendar's rule for one passage (a sentence and the next): effective-date language, a change verb and an
    old -> new hourly price next to a GPU name all in the same passage. Returns (effective date, changes, quote)."""
    s = [x for x in SENT.split(text) if x.strip()]
    for i in range(len(s)):
        ctx = " ".join(s[i:i + 2])
        m = EFF.search(ctx)
        if not (m and (CHG.search(ctx) or "instead of" in ctx)):
            continue
        eff = _parse_date(m.group(4), published.year)
        ch = extract_changes(ctx)
        if eff and ch and -120 <= (eff - published).days <= 90:
            return eff, ch, ctx.strip()[:400]
    return None, [], ""


def subject_provider(passage: str, P: dict) -> str | None:
    """The panel provider named first in the passage (whose change it reports): slug or display name, word-bounded;
    a single-word display name must be capitalised (Together, Modal, Lambda are also common words)."""
    best = None
    for slug, (name, _) in P.items():
        for pat, fl in ((rf"\b{re.escape(slug)}\b", re.I), (rf"\b{re.escape(name.split(' (')[0])}\b", 0 if " " not in name else re.I)):
            m = re.search(pat, passage, fl)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), slug)
    return best[1] if best else None


def extract_changes(text: str) -> list[dict]:
    """Old -> new hourly prices next to a GPU name (calendar entry `changes` schema; tier on_demand)."""
    out, seen = [], set()
    for rx, rev in PAIRS:
        for m in rx.finditer(text):
            a, b = float(m.group(1)), float(m.group(2))
            old, new = (b, a) if rev else (a, b)
            toks = list(GPU_TOK.finditer(text[max(0, m.start() - 80):m.start()]))
            if not toks or not (0.05 <= old <= 60 and 0.05 <= new <= 60) or not -0.6 <= new / old - 1 <= 1.0 or old == new:
                continue
            g = re.sub(r"\s+", " ", toks[-1].group(1))
            if (g.upper(), old, new) in seen:
                continue
            seen.add((g.upper(), old, new))
            out.append({"gpu": g, "panel_gpus": _gpu_panel(g), "tier": "on_demand", "old": old, "new": new, "pct": round(new / old - 1, 4)})
    return out


def _case_rows(as_of: str) -> tuple[list[dict], str | None]:
    rows, err = _recall("Dated failure cases of the median forecast: autopsy event, date of the move, pivotal provider, providers that "
                        "raised, cut, entered or left the panel", "scout", as_of=as_of, limit=100)
    return [r for r in rows if (r.get("metadata") or {}).get("kind") in ("event", "case")], err


def _case_providers(r: dict) -> tuple[set[str], str | None]:
    t = r.get("text") or r.get("excerpt") or ""
    prov = set()
    for k in ("Pivotal provider", "Providers that raised", "Providers that cut", "Providers that entered the panel", "Providers that left the panel"):
        m = re.search(rf"^{k}: (.+)$", t, re.M)
        if m:
            prov |= {x.strip() for x in m.group(1).split(",") if x.strip() and x.strip() != "none"}
    m = re.search(r"Date of the move: \S+ -> (\d{4}-\d\d-\d\d)", t)
    d = m.group(1) if m else (r.get("metadata") or {}).get("date") or str(r.get("occurred_at"))[:10]
    return prov, d


def step_scout(a) -> dict:
    CL, PV, SE = _calsys()
    as_of = dt.date.fromisoformat(a.as_of)
    if as_of > CUTOFF:
        raise SystemExit("error: --as-of must be on or before 2026-11-06 (the data cutoff)")
    budget = Budget(a.max_usd)
    ents = cal_entries()
    cases, err = _case_rows(a.as_of)
    unexplained, explained = {}, []
    for r in cases:
        provs, d = _case_providers(r)
        for pv in provs:
            if pv not in PV.P:
                continue
            md = _day(d)
            hit = [e for e in ents if e["provider"] == pv and abs(CL.effective_day(e) - md) <= 3]
            (explained if hit else unexplained.setdefault(pv, [])).append({"case": r["source_id"], "provider": pv, "date": d})
    jobs = []
    for pv, cs in sorted(unexplained.items()):
        d0 = min(dt.date.fromisoformat(c["date"]) for c in cs) - dt.timedelta(days=45)
        name, dom = PV.P[pv]
        for s, e in SE.WINDOWS:
            if dt.date.fromisoformat(s) > as_of or dt.date.fromisoformat(e) < d0:
                continue
            e2 = str(min(dt.date.fromisoformat(e), as_of))
            jobs.append((pv, "news", s, e2, SE.body(f"{name} announces GPU price change effective date, new hourly prices for H100 H200 B200 GPUs", s, e2)))
            jobs.append((pv, "own", s, e2, SE.body(f"{name} GPU pricing update: new rates take effect on a date, price increase or decrease notice", s, e2, dom)))
    drops, kept = {}, {}
    for pv, kind, s, e, body in jobs:
        rec = _exa("search", body, budget)
        for x in ((rec or {}).get("response") or {}).get("results", []):
            pub, url, title = (x.get("publishedDate") or "")[:10], x.get("url") or "", x.get("title") or ""
            why = ("no_date" if not pub else "outside_window" if not (s <= pub <= e) or pub > a.as_of else
                   "tracker" if any(t in url for t in PV.TRACKERS) or SE.TRACKER_TITLE.search(title) else None)
            if why:
                drops[why] = drops.get(why, 0) + 1
                continue
            hl = " | ".join(x.get("highlights") or [])
            text = f"{title} {hl}"
            name, dom = PV.P[pv]
            named = kind == "own" or any(d in url for d in dom) or re.search(rf"\b({re.escape(pv)}|{re.escape(name.split()[0])})", text, re.I)
            if not (CHG.search(text) and PRICE.search(text) and GPU.search(text) and named):
                drops["not_a_price_change_by_provider"] = drops.get("not_a_price_change_by_provider", 0) + 1
                continue
            k = kept.setdefault(url, {"url": url, "title": title, "published": pub, "provider": pv, "own_domain": any(d in url for d in dom),
                                      "highlight": hl, "eff": bool(EFF.search(text)), "found_for": sorted({c["case"] for c in unexplained[pv]})[:5]})
            k["eff"] |= bool(EFF.search(text))
    known_urls = {e["url"] for e in ents} | {x["url"] for e in ents for x in e.get("also", [])}
    have = {(e["provider"], e["effective_date"]) for e in ents}
    new_entries, rejected, n_contents = [], [], 0
    for k in sorted(kept.values(), key=lambda k: k["published"]):
        if not k["eff"] or k["url"] in known_urls:
            continue
        if EVERGREEN.search(k["title"]):
            rejected.append({"url": k["url"], "provider": k["provider"], "published": k["published"], "why": "evergreen pricing guide (edited in place)"})
            continue
        pub = dt.date.fromisoformat(k["published"])
        text = f"{k['title']}. {k['highlight']}"
        eff, changes, quote = extract_announcement(text, pub)
        if not changes and n_contents < 10:  # highlights carried no dated price pair: Exa's stored copy, never a live tracker page
            n_contents += 1
            r = _exa("contents", {"urls": [k["url"]], "text": {"maxCharacters": 8000}}, budget)
            res = ((r or {}).get("response") or {}).get("results", [])
            if res and res[0].get("text"):
                text = f"{k['title']}. {res[0]['text']}"
                eff, changes, quote = extract_announcement(text, pub)
        later = sorted({d for d in (_parse_date(x.group(0), pub.year) for x in DATE_RX.finditer(text)) if d and d > pub and d != eff})
        known = max([pub] + later)   # the calendar's timing rule: the later of Exa's date and any later date in the text
        subj = subject_provider(quote, PV.P) if changes else None
        if subj and subj != k["provider"]:   # the passage reports another provider's change (e.g. a Spheron post about Nebius)
            k = {**k, "provider": subj, "own_domain": any(d in k["url"] for d in PV.P[subj][1])}
        why = ("no passage with effective date, change verb and old -> new price" if not changes else
               "passage names no panel provider" if not subj else
               f"text carries a date after {a.as_of} ({known}): edited after the as-of date" if known > as_of else
               "already in calendar" if any(p == k["provider"] and abs(_day(d) - eff.toordinal()) <= 2 for p, d in have) else None)
        if why:
            rejected.append({"url": k["url"], "provider": k["provider"], "published": k["published"], "why": why})
            continue
        conf = "C" if known > eff else "A" if k["own_domain"] else "B"   # calendar_lib: A primary, B secondary, C reported after
        e = {"provider": k["provider"], "effective_date": str(eff), "effective_utc": f"{eff}T00:00Z", "published": str(known), "url": k["url"],
             "title": k["title"], "quote": quote, "quote_states_effective_date": True,
             "source_type": "auto-extracted by gpuf.loop scout from Exa search highlights", "also": [], "changes": changes, "confidence": conf,
             "edited_after_published": bool(later), "edit_note": f"later dates in text: {[str(x) for x in later]}" if later else "",
             "announced_before_effective": known < eff, "lead_days": (eff - known).days, "usable_from": str(known), "auto": True,
             "found_by": f"gpuf.loop scout --as-of {a.as_of}"}
        new_entries.append(e)
        have.add((e["provider"], e["effective_date"]))
    if new_entries and not a.dry_run:
        with cal_path().open("a") as f:
            for e in new_entries:
                f.write(json.dumps(e) + "\n")
        CL.load.cache_clear()
    mem_ids = set(_mem_items())
    ev = []
    for k in sorted(kept.values(), key=lambda k: k["published"]):
        sid = "scout-" + hashlib.sha256(k["url"].encode()).hexdigest()[:8]
        if not k["eff"] or EVERGREEN.search(k["title"]) or sid in mem_ids or len(ev) >= a.max_evidence:
            continue
        dom = re.sub(r"^https?://(www\.)?", "", k["url"]).split("/")[0]
        txt = (f"Web evidence from {dom}, published {k['published']} (written by scout via gpuf.loop)\nURL: {k['url']}\nTitle: {k['title']}\n"
               f"Published: {k['published']}\nQuoted sentence: \"{k['highlight'][:500]}\"\nExplains: provider {k['provider']}; searched for "
               f"failure cases without a dated explanation: {', '.join(k['found_for'])}")
        ev.append({"id": sid, "audience": "gpuf-evidence", "identity": "scout", "timestamp": f"{k['published']}T23:59:59Z", "label": f"Evidence: {dom}",
                   "content": txt, "metadata": {"agent": "scout", "kind": "web_evidence", "published": k["published"], "url": k["url"],
                                                "provider": k["provider"], "source": "gpuf.loop scout"}})
    return {"as_of": a.as_of, "failure_cases_recalled": len(cases), "recall_error": err,
            "cases_with_dated_explanation": len(explained), "cases_without": sum(len(v) for v in unexplained.values()),
            "providers_searched": sorted(unexplained), "searches": len(jobs), **budget.report(), "contents_fetches": n_contents,
            "dropped": drops, "kept_sources": len(kept), "kept_with_effective_date_language": sum(k["eff"] for k in kept.values()),
            "new_calendar_entries": new_entries, "rejected_candidates": rejected[:25], "n_rejected": len(rejected),
            "calendar_entries_now": len(cal_entries()), "dry_run": a.dry_run,
            "evidence_written": _write(ev, "scout") if ev and not a.dry_run else {"sent": 0},
            "exa_spend_usd": exa_spend_all()}


# ----------------------------------------------------------------------------- prior
STOP = set("the a an and or of to in on at for is are be it that this with by as from so should sit not does do when its into than then there".split())


def _toks(s: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2}


def _jac(a: str, b: str) -> float:
    x, y = _toks(a), _toks(b)
    return len(x & y) / max(1, len(x | y))


def step_prior(a) -> dict:
    _, PV, SE = _calsys()
    claim = a.claim
    rows, err = _recall(claim, "proposer", limit=40)
    led = {}
    ledger = _ledger()
    for e in ledger.load():
        led[e["id"]] = e
    mem = []
    for r in rows:
        md = r.get("metadata") or {}
        if md.get("kind") != "experiment":
            continue
        e = led.get(md.get("hypothesis"), {})
        mem.append({"rank": r["rank"], "id": r["source_id"], "hypothesis": md.get("hypothesis"), "verdict": e.get("status") or md.get("status"),
                    "claim": e.get("claim"), "overlap": round(_jac(claim, (e.get("claim") or "") + " " + (e.get("failure_mode") or "")), 3),
                    "result": (e.get("result") or "")[:300]})
    mem = mem[:a.top]
    lex = sorted(({"hypothesis": e["id"], "verdict": e["status"], "overlap": round(_jac(claim, (e.get("claim") or "") + " " + (e.get("failure_mode") or "")), 3),
                   "claim": e.get("claim")} for e in led.values()), key=lambda x: -x["overlap"])[:3]
    budget = Budget(a.max_usd)
    end = "2026-11-06T23:59:59Z"
    obj = ("Find prior work that already tested or explained this claim about posted prices; rank empirical studies and methods first; "
           "exclude live price lists and price trackers; pull the finding and its evidence.")
    reqs = {"papers": {"query": f"Research papers and preprints that study: {claim}", "type": "auto", "category": "publication", "numResults": 8,
                       "endPublishedDate": end, "contents": {"highlights": True}, "objective": obj},
            "posts": {"query": f"Technical blog posts and articles that analyse: {claim}", "type": "auto", "numResults": 8, "endPublishedDate": end,
                      "excludeDomains": PV.TRACKERS, "contents": {"highlights": True}, "objective": obj}}
    sources, dropped = [], {}
    for kind, body in reqs.items():
        rec = _exa("search", body, budget, lookup=("loop",))
        if rec and rec.get("error"):
            dropped[f"{kind}_api_error"] = str(rec.get("status"))
        for x in ((rec or {}).get("response") or {}).get("results", []):
            pub, url, title = (x.get("publishedDate") or "")[:10], x.get("url") or "", x.get("title") or ""
            why = "no_date" if not pub else "after_cutoff" if pub > str(CUTOFF) else \
                  "tracker" if any(t in url for t in PV.TRACKERS) or SE.TRACKER_TITLE.search(title) else None
            if why:
                dropped[why] = dropped.get(why, 0) + 1
                continue
            hl = (x.get("highlights") or [""])[0]
            sources.append({"kind": kind, "date": pub, "title": title, "link": url, "highlight": re.sub(r"\s+", " ", hl)[:350],
                            "overlap": round(_jac(claim, f"{title} {hl}"), 3)})
    sources.sort(key=lambda s: -s["overlap"])
    near = sorted([m for m in mem if m["rank"] <= 5 and m["overlap"] >= 0.12] + [x for x in lex if x["overlap"] >= 0.2], key=lambda n: -n["overlap"])
    lit = [s for s in sources if s["overlap"] >= 0.12]
    nn = near[0] if near else None   # the nearest neighbour decides (a refuted opposite claim must not veto a supported one)
    if nn and nn["verdict"] in ("refuted", "not_significant"):
        rec = f"already refuted here ({nn['hypothesis']}, {nn['verdict']}): re-test only with a new reason"
    elif nn and nn["verdict"] == "supported":
        rec = f"already tested here and supported ({nn['hypothesis']}): build on it, do not re-run it"
    elif lit:
        rec = f"already known in the literature ({lit[0]['title'][:80]}, {lit[0]['date']}): cite it and test only what is new here"
    else:
        rec = "untested: no near neighbour in memory or the ledger, and no close source found"
    return {"claim": claim, "memory_hits": mem, "memory_error": err, "ledger_nearest": lex, "sources": sources[:a.top], "dropped": dropped,
            "exa_requests": reqs, **budget.report(), "recommendation": rec,
            "rule": "nearest neighbour = the highest-overlap top-5 memory hit with overlap >= 0.12 or ledger claim with overlap >= 0.2; its "
                    "verdict decides (refuted/not_significant -> refuted here, supported -> tested here); otherwise literature if a dated "
                    "source overlaps >= 0.12; else untested (overlap = Jaccard of 6-letter stems)"}


# ----------------------------------------------------------------------------- propose
def _targets(cause: str, e: dict) -> bool:
    t = f"{e.get('claim') or ''} {e.get('failure_mode') or ''}".lower()
    return any(re.search(s, t) for s in CAUSE_TERMS[cause])


def step_propose(a) -> dict:
    auto = [r for r in _journal() if r["step"] == "autopsy"]
    if not auto:
        raise SystemExit("error: no autopsy in the loop journal yet; run first:\n  python -m gpuf.loop autopsy --system ens4")
    last = auto[-1]["result"]
    ledger = _ledger()
    led = ledger.load()
    tab = sorted(last["table"], key=lambda r: -r["residual_share"])
    m = _mem()
    try:
        br = m.brief("proposer", "largest residual causes of loss: " + ", ".join(r["cause"] for r in tab[:3]), top=4)
        brief_txt, brief_err = br["briefing"], None
    except m.PastError as e:
        brief_txt, brief_err = None, str(e)
    items = _mem_items()
    ev_times = sorted(it["_journal_time"] for it in items.values() if it.get("audience") == "gpuf-evidence")
    cal_times = sorted(r["utc"] for r in _journal() if r["step"] == "scout" and r["result"].get("new_calendar_entries"))
    leads = {}
    fm = ROOT / "experiments/autopsy2/results/failure_modes_iter2.json"
    if fm.exists():
        leads = {x["id"]: x.get("visible_in_panel_at_origin") for x in json.loads(fm.read_text())["modes"]}
    out = []
    for r in tab:
        hyps = [e for e in led if _targets(r["cause"], e)]
        tested = [{"id": e["id"], "status": e["status"], "claim": (e.get("claim") or "")[:140]} for e in hyps if e["status"] not in ("registered", "running")]
        untested = [{"id": e["id"], "status": e["status"], "claim": (e.get("claim") or "")[:140]} for e in hyps if e["status"] in ("registered", "running")]
        all_neg = bool(tested) and not untested and all(e["status"] in ("refuted", "not_significant", "untestable") for e in tested)
        newest = max((e["updated_utc"] for e in hyps), default="")
        new_ev = [t for t in ev_times if t[:19] > newest[:19]] + [t for t in cal_times if t[:19] > newest[:19]]
        state = ("excluded: every targeted hypothesis refuted, no new evidence since" if all_neg and not new_ev else
                 f"reopened: all targeted hypotheses refuted, but {len(new_ev)} evidence items arrived since {newest[:19]}" if all_neg else
                 "open: supported hypotheses target it and it still carries residual loss" if any(e["status"] == "supported" for e in tested) else
                 "open: registered hypotheses wait to be tested" if untested else "open: no hypothesis registered against it")
        out.append({"cause": r["cause"], "residual_share": r["residual_share"], "loss_over_lv": r["loss_over_lv"], "cells": r["cells"], "state": state,
                    "registered_untested": untested, "tested": tested, "not_yet_registered_lead": leads.get(r["cause"])})
    ranked = [x for x in out if not x["state"].startswith("excluded")] + [x for x in out if x["state"].startswith("excluded")]
    return {"autopsy_of": last["system"], "autopsy_utc": auto[-1]["utc"], "dev_skill": last["dev_skill"], "ranked": ranked,
            "briefing": brief_txt, "briefing_error": brief_err,
            "note": "Rule-based: it lists where the loss is and what has been tried; it does not invent hypotheses. "
                    "Leads are the autopsy's own statement of what was visible at the origin (experiments/autopsy2)."}


# ----------------------------------------------------------------------------- gate
def _p1(r) -> float | None:
    if r.get("dm_p_two_sided") is None:
        return None
    return r["dm_p_two_sided"] / 2 if r["dm_stat"] < 0 else 1 - r["dm_p_two_sided"] / 2


def verdict(d_all: float, ci_lo: float, d_first: float, d_second: float) -> str:
    """EVAL_PROTOCOL.md Amendment 2 rule 1: supported = 90% interval above zero and the gain positive in both halves of dev;
    refuted = no gain overall (point estimate <= 0); otherwise not_significant."""
    if ci_lo > 0 and d_first > 0 and d_second > 0:
        return "supported"
    return "refuted" if d_all <= 0 else "not_significant"


def step_gate(a) -> dict:
    from . import compare
    ledger = _ledger()
    cslug, cand = spec_of(a.candidate)
    rslug, ref = spec_of(a.ref)
    c, r = system_cells(cand), system_cells(ref)
    res = {}
    for lab, mc, mr in (("all", slice(None), slice(None)), ("first", c.origin_day <= DEV_CUT, r.origin_day <= DEV_CUT),
                        ("second", c.origin_day > DEV_CUT, r.origin_day > DEV_CUT)):
        p = compare.paired(c[mc], r[mr])
        res[lab] = {"d": round(p["d_pooled_skill"], 4), "ci90": [round(x, 4) for x in p["ci90_d_pooled_skill"]], "n_cells": p["n_cells"]}
        if lab == "all":
            res[lab]["dm_p_one_sided"] = round(_p1(p), 4) if _p1(p) is not None else None
    h7 = c[c.horizon_days == 7]
    st = verdict(res["all"]["d"], res["all"]["ci90"][0], res["first"]["d"], res["second"]["d"])
    result = (f"dev headline (gpuf.loop gate): {cslug} {_skill(c):.4f} vs {rslug} {_skill(r):.4f}, d {res['all']['d']:+.4f} "
              f"[{res['all']['ci90'][0]:+.3f},{res['all']['ci90'][1]:+.3f}]; first half {res['first']['d']:+.4f}, second {res['second']['d']:+.4f}; "
              f"{res['all']['n_cells']} cells; status by Amendment 2 rule 1: {st}")
    row = ledger.put(a.name, agent="loop", claim=a.claim or f"{json.dumps(cand)} beats {json.dumps(ref)} on dev headline", status=st,
                     failure_mode=a.failure_mode or "", result=result, evidence="data_out/loop_journal.jsonl (gate)",
                     refuted_if="Amendment 2 rule 1 fails: 90% interval not above zero or a half of dev negative")
    m = _mem()
    try:
        sync = m.sync_ledger()
    except m.PastError as e:
        sync = {"error": str(e)}
    return {"name": a.name, "candidate": cand, "ref": ref, "skill": round(_skill(c), 4), "ref_skill": round(_skill(r), 4), **res,
            "coverage": round(float(((c.y >= c.q10) & (c.y <= c.q90)).mean()), 3), "h7_above_q90": round(float((h7.y > h7.q90).mean()), 3),
            "q50_loss_ratio": round(float(c.loss_q50.sum() / max(r.loss_q50.sum(), 1e-12)), 3), "status": st,
            "ledger": {k: row[k] for k in ("id", "status", "updated_utc")}, "memory_sync": sync}


# ----------------------------------------------------------------------------- forecast
def step_forecast(a) -> dict:
    from . import splits
    o = _day(a.origin)
    if o in splits.VAL and not a.i_am_the_orchestrator:
        raise PermissionError(f"REFUSED: origin {a.origin} is inside the validation period 2026-10-13..2026-10-30; "
                              "only the orchestrator forecasts there (--i-am-the-orchestrator)")
    if o > CUTOFF.toordinal():
        raise PermissionError(f"REFUSED: origin {a.origin} is after the data cutoff 2026-11-06")
    slug, spec = spec_of(a.method)
    # 1. calendar through memory: the forecaster's date-bounded read of scout's writes
    rows, err = _recall("Announced GPU price changes with an effective date: provider, new hourly price, effective date, calendar entry",
                        "forecaster", as_of=a.origin, limit=100)
    ents = cal_entries()
    by_url = {}
    for e in ents:
        for u in [e["url"]] + [x["url"] for x in e.get("also", [])]:
            by_url[u] = (e["provider"], e["effective_date"])
    mem_set, mem_unmatched = {}, []
    for r in rows:
        md = r.get("metadata") or {}
        if str(r.get("occurred_at"))[:10] > a.origin:
            continue
        sid = r["source_id"]
        m = re.match(r"scout-cal-(.+)-(\d{4}-\d\d-\d\d)$", sid)
        key = (m.group(1), m.group(2)) if m else by_url.get(md.get("url"))
        if key:
            mem_set[key] = sid
        elif md.get("kind") == "web_evidence":
            mem_unmatched.append({"id": sid, "date": str(r.get("occurred_at"))[:10], "url": md.get("url")})
    loc = {(e["provider"], e["effective_date"]): e for e in usable(ents, o)}
    loc_all = {(e["provider"], e["effective_date"]): e for e in ents if _day(e["published"]) <= o}
    only_local = [{"provider": k[0], "effective_date": k[1], "published": loc[k]["published"]} for k in loc if k not in mem_set]
    only_mem = [{"provider": k[0], "effective_date": k[1], "memory_id": v,
                 "why": ("in calendar but confidence C (calendar_lib excludes it)" if k in loc_all else "no matching calendar line usable at the origin")}
                for k, v in mem_set.items() if k not in loc]
    future = [f"{k[0]} {k[1]}" for k, e in loc.items() if _day(k[1]) > o]
    # 2. forecast through the harness's forecast path (no scoring)
    from . import data, harness, methods
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    sids = data.universe(a.universe)
    fc, counts = harness.forecast(methods.get(spec[0], **spec[1]), [o], sids, (1, 3, 7), store, meta)
    fc["origin_date"] = a.origin
    fc["target_date"] = [_date(o + h) for h in fc.horizon_days]
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fc[["series_id", "origin_date", "horizon_days", "q10", "q50", "q90", "target_date"]].to_csv(out, index=False)
    return {"origin": a.origin, "method": slug, "spec": spec, "out": str(out), "rows": int(len(fc)), "series": int(fc.series_id.nunique()), **counts,
            "scored": False, "calendar_check": {"memory_recall_error": err, "memory_rows": len(rows), "usable_local": sorted(f"{k[0]} {k[1]}" for k in loc),
                                                "usable_memory": sorted(f"{k[0]} {k[1]}" for k in mem_set), "agree": not only_local and not only_mem,
                                                "only_in_local_file": only_local, "only_in_memory": only_mem,
                                                "memory_evidence_without_calendar_line": mem_unmatched[:10],
                                                "usable_entries_effective_after_origin": future,
                                                "method_applies_calendar": bool(spec[1].get("cal")) or "cal" in json.dumps(spec)}}


# ----------------------------------------------------------------------------- status
def step_status(a) -> dict:
    ledger = _ledger()
    led = ledger.load()
    by = {}
    for e in led:
        by[e["status"]] = by.get(e["status"], 0) + 1
    vq = [json.loads(l) for l in (DATA_OUT / "val_query_log.jsonl").read_text().splitlines() if l.strip()] if (DATA_OUT / "val_query_log.jsonl").exists() else []
    vg = [json.loads(l) for l in (DATA_OUT / "val_gate.jsonl").read_text().splitlines() if l.strip()] if (DATA_OUT / "val_gate.jsonl").exists() else []
    items = _mem_items()
    aud, auth = {}, {}
    for it in items.values():
        aud[it.get("audience") or "project"] = aud.get(it.get("audience") or "project", 0) + 1
        au = (it.get("metadata") or {}).get("agent") or it.get("identity")
        auth[au] = auth.get(au, 0) + 1
    rec = {}
    for r in _mem()._read_journal():
        if r["op"] == "recall":
            rec[r["agent"]] = rec.get(r["agent"], 0) + 1
    ents = cal_entries()
    steps = {}
    for r in _journal():
        steps[r["step"]] = steps.get(r["step"], 0) + 1
    return {"ledger": {"hypotheses": len(led), "by_status": by, "latest": [f"{e['id']} {e['status']} {e['updated_utc']}" for e in
                                                                          sorted(led, key=lambda e: e["updated_utc"])[-5:]]},
            "validation": {"queries_logged": len(vq), "gate_queries": [{"name": g["name"], "d_vs_ref": round(g["d_vs_ref"], 4),
                                                                        "p_one_sided": round(g["p_one_sided"], 4)} for g in vg]},
            "calendar": {"entries": len(ents), "auto_added_by_loop": sum(bool(e.get("auto")) for e in ents),
                         "lines": [f"{e['provider']} eff {e['effective_date']} pub {e['published']} conf {e['confidence']}" for e in ents]},
            "memory": {"data_points": len(items), "by_audience": aud, "by_author": auth, "recalls_by_agent": rec},
            "exa_spend_usd": exa_spend_all(), "loop_steps_run": steps, "offline": offline()}


# ----------------------------------------------------------------------------- CLI
STEPS = {
    "autopsy": ("Score a system on dev, attribute its loss to causes, write each cause to memory as `autopsy` (gpuf-failures).",
                "python -m gpuf.loop autopsy --system ens4"),
    "scout": ("Recall failure cases lacking a dated explanation (as `scout`), search Exa bounded by --as-of, append announced changes "
              "to the calendar, write kept sources to memory (gpuf-evidence).", "python -m gpuf.loop scout --as-of 2026-10-06 --max-usd 1"),
    "prior": ("Before spending compute: has a claim been tested here (memory, as `proposer`) or in the literature (Exa)?",
              'python -m gpuf.loop prior --claim "posted medians step to the neighbouring offer when an offer leaves"'),
    "propose": ("Rank open causes by residual loss share from the latest autopsy and the memory briefing (rule-based; invents nothing).",
                "python -m gpuf.loop propose"),
    "gate": ("Dev gate (EVAL_PROTOCOL.md Amendment 2 rule 1) of a candidate against a reference; writes the ledger, syncs memory as `experimenter`.",
             "python -m gpuf.loop gate --name L-frag-b20 --candidate '[\"fragility\",{\"mode\":\"mix\",\"boost\":20,\"bkind\":\"any\"}]'"),
    "forecast": ("Date-bounded calendar refresh (memory as `forecaster` vs the local file), then a forecast CSV for one origin. Never scores; "
                 "refuses validation origins.", "python -m gpuf.loop forecast --origin 2026-10-06 --method ens4 --out runs/loop/fc_2026-10-06.csv"),
    "status": ("Ledger summary, validation queries used, calendar, memory counts by audience and author, Exa spend.", "python -m gpuf.loop status"),
}
SYSHELP = f"system: alias ({', '.join(sorted(ALIASES))}), JSON [method, params], or FILE.json:KEY (a halves.py spec)"


def parser() -> argparse.ArgumentParser:
    epi = "steps (one example each; `python -m gpuf.loop STEP --help` for options):\n" + "\n".join(
        f"  {k:<9} {v[1]}" for k, v in STEPS.items()) + ("\n\nenvironment: LOOP_OFFLINE=1 (no network: Exa cache and memory journal only), "
                                                     "PAST_ALLOW_WRITES=1 (live past.dev), OMP_NUM_THREADS=2 is set by default.\n"
                                                     "output: JSON on stdout, one line per run in data_out/loop_journal.jsonl; "
                                                     "exit 1 on error, 2 on a refusal.")
    P = argparse.ArgumentParser(prog="python -m gpuf.loop", description="The failure-driven research loop, one step per command.",
                                epilog=epi, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = P.add_subparsers(dest="step", required=True, metavar="STEP")
    mk = lambda n: sub.add_parser(n, help=STEPS[n][0], description=STEPS[n][0], epilog="example:\n  " + STEPS[n][1],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    s = mk("autopsy"); s.add_argument("--system", required=True, help=SYSHELP)
    s.add_argument("--no-memory", action="store_true", help="do not write the causes to memory")
    s = mk("scout"); s.add_argument("--as-of", required=True, help="YYYY-MM-DD: every search ends on or before this date")
    s.add_argument("--max-usd", type=float, default=1.0, help="cap on new Exa spend in this run (default 1.0)")
    s.add_argument("--max-evidence", type=int, default=15, help="max new evidence records written to memory (default 15)")
    s.add_argument("--dry-run", action="store_true", help="search and extract, but append nothing to the calendar or memory")
    s = mk("prior"); s.add_argument("--claim", required=True); s.add_argument("--top", type=int, default=5, help="rows per list (default 5)")
    s.add_argument("--max-usd", type=float, default=0.05, help="cap on new Exa spend (default 0.05: two searches)")
    mk("propose")
    s = mk("gate"); s.add_argument("--name", required=True, help="ledger id to create or update")
    s.add_argument("--candidate", required=True, help=SYSHELP); s.add_argument("--ref", default="mix", help="reference system (default mix)")
    s.add_argument("--claim", help="ledger claim text"); s.add_argument("--failure-mode", help="ledger failure_mode text")
    s = mk("forecast"); s.add_argument("--origin", required=True, help="YYYY-MM-DD"); s.add_argument("--method", required=True, help=SYSHELP)
    s.add_argument("--out", required=True, help="CSV path (starter forecast format)")
    s.add_argument("--universe", default="rental_headline", help="rental_headline (default) or rental_all")
    s.add_argument("--i-am-the-orchestrator", action="store_true", help="allow an origin inside the validation period")
    mk("status")
    return P


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    a = parser().parse_args(argv)
    if offline():
        os.environ["PAST_OFFLINE"] = "1"
    fn = globals()[f"step_{a.step}"]
    try:
        out = fn(a)
    except PermissionError as e:
        out = {"refused": str(e)}
        _log(a.step, argv, out)
        print(_scrub(json.dumps(out, indent=1)))
        return 2
    _log(a.step, argv, out)
    print(_scrub(json.dumps(out, indent=1, ensure_ascii=False, default=str)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
