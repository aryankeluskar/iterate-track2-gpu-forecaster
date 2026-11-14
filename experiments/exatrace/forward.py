"""Task 4: forward-looking search for the scored week (protocol.yaml, forward_search). Changes no forecast.

1. Providers holding the middle offer, or an offer next to it, of each of the 37 scored series on 2026-11-06 (gpuf.panel rows of that day).
2. For each: the scout's dated searches (experiments/calendar/search.py body(): trackers excluded, window 2026-10-01..2026-11-06, the
   calendar agent's identical requests are reused from the cache) plus one query for changes effective 7..13 November.
3. Every result through the scout's filters (undated, outside the window, trackers, not a price change by the provider) and
   gpuf.loop.assess with as-of 2026-11-06 (Exa contents, the stored copy, when the highlights carry no dated price pair).
4. For each eligible announcement effective 2026-10-30..2026-11-13: whether the new price is already in the 6 Nov offer rows, and the
   pass-through: each scored median recomputed with only that provider's matching offers at the new price.

PYTHONPATH=src .venv/bin/python experiments/exatrace/forward.py [--offline]    (new requests are tagged exatrace_ in data_out/exa_cache)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "calendar"))
if "--offline" in sys.argv:
    os.environ["LOOP_OFFLINE"] = "1"

import numpy as np

import calendar_lib as CL
import providers as PV
import search as SE
from gpuf import data, loop, panel as P

RES = pathlib.Path(__file__).parent / "results"
ASOF = dt.date(2026, 11, 6)
O = ASOF.toordinal()
WEEK = (dt.date(2026, 11, 7), dt.date(2026, 11, 13))
LOOK = dt.date(2026, 10, 30)            # also report changes effective from 30 Oct whose new price is not yet in the rows
WIN = ("2026-10-01", "2026-11-06")
CAP = 1.50


def middle_providers():
    out, series = {}, []
    for sid in data.universe("rental_headline"):
        if not P.supported(sid):
            series.append({"series_id": sid, "panel": False, "note": "no offer panel in gpuf.panel (afhubbard hyperscaler spot)"})
            continue
        o = P.offers(sid, O)
        cur = o[o.day == O].sort_values("price", kind="stable").reset_index(drop=True)
        n = len(cur)
        if n == 0:
            series.append({"series_id": sid, "panel": True, "n": 0, "note": "no offers on 2026-11-06"})
            continue
        mid = sorted({(n - 1) // 2, n // 2})
        adj = sorted({max(mid[0] - 1, 0), min(mid[-1] + 1, n - 1)} - set(mid))
        row = {"series_id": sid, "panel": True, "n": n, "median": float(cur.price.median()),
               "middle": [(cur.provider[i], float(cur.price[i])) for i in mid], "adjacent": [(cur.provider[i], float(cur.price[i])) for i in adj]}
        series.append(row)
        for pv, _ in row["middle"] + row["adjacent"]:
            out.setdefault(pv, set()).add(sid)
    return {k: sorted(v) for k, v in sorted(out.items())}, series


def pass_through(provider, ch):
    """Each scored series with an offer of `provider` at the announced old price on 6 Nov: the median with only those offers moved."""
    rows = []
    for sid in data.universe("rental_headline"):
        if not P.supported(sid):
            continue
        src, cls, gpu, tier = P.parse_sid(sid)
        if gpu not in ch["panel_gpus"] or tier not in CL.TIER_MAP.get(ch["tier"], set()):
            continue
        o = P.offers(sid, O)
        cur = o[o.day == O]
        mine = (cur.provider == provider).to_numpy()
        if not mine.any():
            continue
        px = cur.price.to_numpy(float).copy()
        tol = min(0.03, abs(ch["new"] / ch["old"] - 1) / 2) if ch.get("old") else 0.02   # small (1%) moves: half the step, not 3%
        at_new = bool(np.isclose(px[mine], ch["new"], rtol=tol).any())
        m = mine & (np.isclose(px, ch["old"], rtol=tol) if ch.get("old") else True)
        before = float(np.median(px))
        px[m] = ch["new"]
        rows.append({"series_id": sid, "provider_offers": int(mine.sum()), "at_old_price": int(m.sum()), "new_price_already_in_rows": at_new,
                     "median_6nov": before, "median_if_only_this_changes": float(np.median(px)),
                     "pass_through_pct": round(100 * (float(np.median(px)) / before - 1), 3)})
    return rows


def main():
    RES.mkdir(parents=True, exist_ok=True)
    provs, series = middle_providers()
    budget = loop.Budget(CAP)
    jobs = []
    for pv in provs:
        if pv not in PV.P:
            continue
        name, dom = PV.P[pv]
        s, e = WIN
        jobs.append((pv, "news", SE.body(f"{name} announces GPU price change effective date, new hourly prices for H100 H200 B200 GPUs", s, e)))
        jobs.append((pv, "own", SE.body(f"{name} GPU pricing update: new rates take effect on a date, price increase or decrease notice", s, e, dom)))
        jobs.append((pv, "week", SE.body(f"{name} GPU price change taking effect in November 2026 (from November 7 to November 13): "
                                         f"new per-hour rates for H100, H200, B200, A100, L40S, RTX GPUs", s, e)))
    drops, kept = {}, {}
    for pv, kind, body in jobs:
        rec = loop._exa("search", body, budget, lookup=("cal", "loop", "exatrace"), tag="exatrace")
        for x in ((rec or {}).get("response") or {}).get("results", []):
            pub, url, title = (x.get("publishedDate") or "")[:10], x.get("url") or "", x.get("title") or ""
            why = ("no_date" if not pub else "outside_window" if not (WIN[0] <= pub <= WIN[1]) else
                   "tracker" if any(t in url for t in PV.TRACKERS) or SE.TRACKER_TITLE.search(title) else None)
            if why:
                drops[why] = drops.get(why, 0) + 1
                continue
            hl = " | ".join(x.get("highlights") or [])
            text = f"{title} {hl}"
            name, dom = PV.P[pv]
            named = kind == "own" or any(d in url for d in dom) or re.search(rf"\b({re.escape(pv)}|{re.escape(name.split()[0])})", text, re.I)
            if not (loop.CHG.search(text) and loop.PRICE.search(text) and loop.GPU.search(text) and named):
                drops["not_a_price_change_by_provider"] = drops.get("not_a_price_change_by_provider", 0) + 1
                continue
            kept.setdefault(url, {"url": url, "title": title, "published": pub, "provider": pv, "own_domain": any(d in url for d in dom),
                                  "highlight": hl, "eff_language": bool(loop.EFF.search(text)), "found_by": kind})
    judged, n_contents = [], 0
    for k in sorted(kept.values(), key=lambda k: k["published"]):
        pub = dt.date.fromisoformat(k["published"])
        j = loop.assess(k["title"], f"{k['title']}. {k['highlight']}", pub, ASOF, PV.P, k["provider"], k["own_domain"], k["url"])
        if not j["changes"] and not loop.EVERGREEN.search(k["title"]) and k["eff_language"] and n_contents < 40:
            n_contents += 1
            r = loop._exa("contents", {"urls": [k["url"]], "text": {"maxCharacters": 8000}}, budget, lookup=("cal", "loop", "exatrace"), tag="exatrace")
            res = ((r or {}).get("response") or {}).get("results", [])
            if res and res[0].get("text"):
                j = loop.assess(k["title"], f"{k['title']}. {res[0]['text']}", pub, ASOF, PV.P, k["provider"], k["own_domain"], k["url"])
        j["found_by"] = k["found_by"]
        judged.append(j)
    hits = []
    for j in judged:
        if not j["eligible"]:
            continue
        eff = dt.date.fromisoformat(j["effective_date"])
        j["in_scored_week"] = WEEK[0] <= eff <= WEEK[1]
        if not (LOOK <= eff <= WEEK[1]):
            continue
        j["pass_through"] = {f"{c['gpu']} {c['old']}->{c['new']}": pass_through(j["provider"], c) for c in j["changes"]}
        j["new_price_already_in_6nov_rows"] = any(r["new_price_already_in_rows"] for v in j["pass_through"].values() for r in v)
        j["nonzero_pass_through_not_in_rows"] = any(abs(r["pass_through_pct"]) > 1e-9 and not r["new_price_already_in_rows"]
                                                    for v in j["pass_through"].values() for r in v)
        hits.append(j)
    rej = {}
    for j in judged:
        if not j["eligible"]:
            w = j["why"].split(" (")[0]
            rej[w] = rej.get(w, 0) + 1
    elig_other = [{"provider": j["provider"], "effective_date": j["effective_date"], "published": j["published"], "url": j["url"]}
                  for j in judged if j["eligible"] and j not in hits]
    out = {"as_of": str(ASOF), "scored_week": [str(WEEK[0]), str(WEEK[1])], "search_window": WIN,
           "providers_at_or_next_to_middle": provs, "n_providers": len(provs),
           "providers_not_in_provider_list": [p for p in provs if p not in PV.P], "series": series,
           "searches": len(jobs), **budget.report(), "contents_fetches": n_contents, "dropped": drops, "kept": len(kept),
           "judged": len(judged), "rejected_by_reason": rej, "eligible_effective_outside_window": elig_other,
           "hits": hits, "flag_for_orchestrator": [h for h in hits if h["nonzero_pass_through_not_in_rows"]],
           "judged_detail": [{k: j[k] for k in ("url", "title", "published", "provider", "eligible", "why", "effective_date", "latest_date_in_text",
                                                 "known", "quote", "found_by")} for j in judged]}
    (RES / "forward.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("n_providers", "searches", "cache_hits", "new_calls", "cost_usd_this_run", "dropped", "kept",
                                          "rejected_by_reason")}, indent=1))
    print("hits:", [(h["provider"], h["effective_date"], h["url"], h["nonzero_pass_through_not_in_rows"]) for h in hits])
    print("eligible, effective outside 30 Oct..13 Nov:", elig_other)


if __name__ == "__main__":
    main()
