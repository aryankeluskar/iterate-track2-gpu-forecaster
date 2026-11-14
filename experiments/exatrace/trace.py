"""Task 1 trace: source -> announcement -> offer rows -> forecast -> outcome, one row per (calendar entry, scored series), plus one row
per source. Reads data_out/exa_cache (sources.py), the offer rows (gpuf.panel) and arms_cells.parquet (run arms.py first). No network.

LOOP_OFFLINE=1 PYTHONPATH=src .venv/bin/python experiments/exatrace/trace.py
Writes results/trace_sources.csv, results/trace_series.csv, results/trace_events.json.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "calendar"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import numpy as np
import pandas as pd

import calendar_lib as CL
from gpuf import data, loop, panel as P
import arms as A
import sources as S

RES = pathlib.Path(__file__).parent / "results"
W0, W1 = loop._day(A.ORIGINS[0]), loop._day(A.ORIGINS[-1])
DEV_END = loop._day("2026-10-13")
NOV6 = loop._day("2026-11-06")
K = A.K


def position(sid, provider, ch, od):
    """Where the provider's offer at the announced old price sits in the series' list on day od."""
    o = P.offers(sid, od)
    cur = o[o.day == o.day.max()].sort_values("price", kind="stable").reset_index(drop=True)
    n = len(cur)
    mine = cur.index[(cur.provider == provider) & (np.isclose(cur.price, ch["old"], rtol=0.03) if ch.get("old") else True)].tolist()
    if not n or not mine:
        at_new = bool(((cur.provider == provider) & np.isclose(cur.price, ch["new"], rtol=0.02)).any()) if ch.get("new") else False
        return {"n_offers": n, "rank": None, "position": ("already at the new price (reflected in the collector)" if at_new else
                                                          "no offer at the old price" if (cur.provider == provider).any() else "provider not in list")}
    lo, hi = (n - 1) // 2, n // 2
    dist = min(min(abs(i - lo), abs(i - hi)) for i in mine)
    px = cur.price.to_numpy(float).copy()
    before = float(np.median(px))
    px[mine] = ch["new"]
    return {"n_offers": n, "rank": [i + 1 for i in mine], "position": "middle" if dist == 0 else "next to middle" if dist == 1 else f"{dist} ranks from middle",
            "median_day": float(before), "median_if_only_this_changes": float(np.median(px)),
            "static_pass_through_pct": round(100 * (float(np.median(px)) / before - 1), 2)}


def main():
    ents = A.base_entries()
    cells = pd.read_parquet(RES / "arms_cells.parquet")
    off = cells[cells.arm == "i_off"].set_index(K)
    val = cells[cells.arm == "ii_valid"].set_index(K)
    aff = pd.read_csv(RES / "affected_cells.csv")
    sids = [s for s in data.universe("rental_headline") if P.supported(s)]
    src_rows, ser_rows, ev = [], [], []
    for e in ents:
        k = A.key(e)
        E, pub = CL.effective_day(e), loop._day(e["published"])
        sup = S.support(e)
        for s in sup:
            c = S.cached(s["url"]) or {}
            q = e["quote"] if s["primary"] else next((x.get("quote") for x in e.get("also", []) if x["url"] == s["url"]), "")
            src_rows.append({"event": k, "url": s["url"], "primary": s["primary"], "title": s["title"], "exa_published": s["published"],
                             "in_cache": s["in_cache"], "cache_files": s["n_cache_files"], "full_text_cached": s["has_full_text"],
                             "quoted_sentence": q, "quote_found_in_cached_text": s["quote_in_cached_text"],
                             "states_effective_date": s["states_effective_date"], "states_prices": f"{len(s['supports'])}/{s['n_changes']}",
                             "latest_date_in_text": s["latest_date_in_text"], "scout_rule_recovers": "; ".join(s["scout_rule_changes"])})
        obs_to = min(max(E + 10, pub), DEV_END) if E <= DEV_END else NOV6
        fo = loop.first_observed(e["provider"], [c for c in e["changes"] if c.get("new") is not None and c["new"] != c["old"]],
                                 dt.date.fromordinal(min(pub, E) - 7), dt.date.fromordinal(obs_to))
        # scored series this entry's contract maps to
        touched = []
        for sid in sids:
            src, cls, gpu, tier = P.parse_sid(sid)
            for c in e["changes"]:
                if gpu in c["panel_gpus"] and tier in CL.TIER_MAP.get(c["tier"], set()):
                    touched.append((sid, c))
        usable_in_window = pub <= W1 and E > max(pub, W0) and e["confidence"] <= "B"
        if e["confidence"] > "B":
            reason = f"too late: confidence C (published {e['published']}, effective {e['effective_date']}: reported after the change)"
        elif not touched:
            tiers = sorted({c["tier"] for c in e["changes"]})
            reason = f"wrong contract: no scored series has an announced GPU in a matching tier (announced tiers {tiers}; calendar_lib.TIER_MAP)"
        elif E <= W0:
            reason = f"outside the origin window: effective {e['effective_date']} before the first origin {A.ORIGINS[0]}"
        elif pub > W1:
            reason = f"outside the origin window: published {e['published']} after the last practice origin {A.ORIGINS[-1]}"
        else:
            reason = None
        n_aff = int((aff.event == k).sum())
        evrow = {"event": k, "provider": e["provider"], "effective_date": e["effective_date"], "effective_utc": e["effective_utc"],
                 "published_usable_from": e["published"], "confidence": e["confidence"], "lead_days": e.get("lead_days"),
                 "changes": [f"{c['gpu']} [{c['tier']}] {c['old']}->{c['new']}" for c in e["changes"]][:8], "n_changes": len(e["changes"]),
                 "first_observed_new_price": fo, "first_observed_rows_up_to": str(dt.date.fromordinal(obs_to)),
                 "n_sources": len(sup), "scored_series_touched": len({t[0] for t in touched}), "affected_cells": n_aff,
                 "usable_in_window": usable_in_window, "does_nothing_because": reason}
        # per scored series
        for sid, c in touched:
            # the last practice origin before the change, or (entries outside the window) the publication day / the day before the change
            od = min(E - 1, W1) if usable_in_window else min(pub, NOV6) if pub > W1 else E - 1
            pos = position(sid, e["provider"], c, od)
            a = aff[(aff.event == k) & (aff.series_id == sid)][K].drop_duplicates()
            row = {"event": k, "series_id": sid, "gpu": c["gpu"], "tier": c["tier"], "old": c["old"], "new": c["new"],
                   "position_day": str(dt.date.fromordinal(od)), **{k2: (json.dumps(v) if isinstance(v, list) else v) for k2, v in pos.items()},
                   "affected_cells": int(len(a))}
            if len(a):
                ix = pd.MultiIndex.from_frame(a)
                b, v = off.loc[ix], val.loc[ix]
                chg = (b[["q10", "q50", "q90"]].to_numpy() != v[["q10", "q50", "q90"]].to_numpy()).any(axis=1)
                row.update(cells_changed=int(chg.sum()), q50_before_mean=round(float(b.q50.mean()), 4), q50_after_mean=round(float(v.q50.mean()), 4),
                           last_value_mean=round(float(b.baseline.mean()), 4), truth_mean=round(float(b.y.mean()), 4),
                           loss_before=round(float(b.loss.sum()), 4), loss_after=round(float(v.loss.sum()), 4),
                           last_value_loss=round(float(b.baseline_loss.sum()), 4),
                           price_moved_cells=int((np.abs(b.y - b.baseline) > 1e-9).sum()))
                row["outcome"] = ("forecast changed, loss down" if row["cells_changed"] and row["loss_after"] < row["loss_before"] else
                                  "forecast changed, loss up" if row["cells_changed"] else
                                  "no change: no pass-through to the median" if pos.get("static_pass_through_pct", 0) == 0 else
                                  "no change: simulated median does not move")
            else:
                row["outcome"] = ("no change: " + reason) if reason else (
                    "no change: " + pos["position"] if pos["rank"] is None else "no cell between availability and effective date")
            ser_rows.append(row)
        ev.append(evrow)
    pd.DataFrame(src_rows).to_csv(RES / "trace_sources.csv", index=False)
    pd.DataFrame(ser_rows).to_csv(RES / "trace_series.csv", index=False)
    (RES / "trace_events.json").write_text(json.dumps(ev, indent=1, default=str))
    for x in ev:
        print(x["event"], "|", x["does_nothing_because"], "| touched", x["scored_series_touched"], "aff", x["affected_cells"], "| fo", x["first_observed_new_price"])


if __name__ == "__main__":
    main()
