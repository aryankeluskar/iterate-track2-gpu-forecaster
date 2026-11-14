"""Markdown tables for trace.md from results/*.csv|json (run arms.py, trace.py, forward.py first). Writes results/trace_tables.md."""
import json
import pathlib

import pandas as pd

RES = pathlib.Path(__file__).parent / "results"


def md(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        out.append("| " + " | ".join("" if (isinstance(v, float) and pd.isna(v)) else str(v) for v in r) + " |")
    return "\n".join(out)


def main():
    s = json.loads((RES / "arms_summary.json").read_text())
    arms = pd.DataFrame([{"arm": k, "skill, all 2,331 cells": v["skill_all"], "skill, 142 affected cells": v["skill_affected"],
                          "Nebius cells (88)": v["per_event_affected"]["nebius 2026-10-01"],
                          "Jarvislabs cells (66)": v["per_event_affected"]["jarvislabs 2026-10-05"],
                          "cells changed vs off": v["cells_changed_vs_off"], "bit-identical to off": v["bit_identical_to_off"]}
                         for k, v in s["arms"].items()])
    src = pd.read_csv(RES / "trace_sources.csv")
    src = src.assign(title=src.title.str.slice(0, 60), quoted_sentence=src.quoted_sentence.fillna("").str.slice(0, 140).str.replace("|", "/"))
    src = src[["event", "url", "exa_published", "title", "quoted_sentence", "quote_found_in_cached_text", "states_effective_date", "states_prices",
               "latest_date_in_text"]]
    ev = pd.DataFrame(json.loads((RES / "trace_events.json").read_text()))
    ev = ev.assign(first_observed_new_price=ev.first_observed_new_price.map(lambda d: ", ".join(f"{k.split('_')[0]} {v}" for k, v in d.items())),
                   changes=ev.changes.map(lambda c: "; ".join(c[:4]) + (" ..." if len(c) > 4 else "")))
    ev = ev[["event", "published_usable_from", "effective_utc", "confidence", "changes", "n_changes", "first_observed_new_price",
             "scored_series_touched", "affected_cells", "does_nothing_because"]]
    ser = pd.read_csv(RES / "trace_series.csv")
    ser = ser.assign(series=ser.series_id.str.replace(".median", "", regex=False).str.replace("neocloud_rate_card.", "", regex=False))
    act = ser[ser.event.isin(["nebius 2026-10-01", "jarvislabs 2026-10-05"])]
    act = act[["event", "series", "old", "new", "position_day", "n_offers", "rank", "position", "static_pass_through_pct", "affected_cells",
               "cells_changed", "last_value_mean", "q50_before_mean", "q50_after_mean", "truth_mean", "loss_before", "loss_after", "outcome"]]
    late = ser[ser.event.str.startswith("lambdalabs")][["series", "old", "new", "position_day", "n_offers", "rank", "position", "static_pass_through_pct"]]
    f = json.loads((RES / "forward.json").read_text())
    rows = [{"series": x["series_id"].replace(".median", ""), "offers": x.get("n", ""),
             "middle": ", ".join(f"{p} {v}" for p, v in x.get("middle") or []), "next to middle": ", ".join(f"{p} {v}" for p, v in x.get("adjacent") or []),
             "note": x.get("note", "")} for x in f["series"]]
    hits = []
    for h in f["hits"]:
        pts = [r for v in h["pass_through"].values() for r in v]
        hits.append({"provider": h["provider"], "published": h["published"], "effective": h["effective_date"], "url": h["url"],
                     "quote": h["quote"][:160].replace("|", "/"), "new price already in 6 Nov rows": h["new_price_already_in_6nov_rows"],
                     "max abs pass-through %": max((abs(r["pass_through_pct"]) for r in pts), default=0.0),
                     "flag (non-zero, not in rows)": h["nonzero_pass_through_not_in_rows"]})
    txt = ["## Arms (origins 2026-09-16..2026-10-06, prov {L 1, W 21, gate dyn})", md(arms),
           "## Sources (all read from data_out/exa_cache)", md(src),
           "## Events", md(ev),
           "## Series rows of the two events that change forecasts (q50 and loss over the affected cells of that series)", md(act),
           "## Lambda 16 Nov on 6 Nov (already reflected / no pass-through)", md(late),
           "## Scored series on 2026-11-06: middle and adjacent offers", md(pd.DataFrame(rows)),
           "## Forward search hits (eligible, effective 2026-10-30..2026-11-13)", md(pd.DataFrame(hits)) if hits else "none"]
    (RES / "trace_tables.md").write_text("\n\n".join(txt) + "\n")


if __name__ == "__main__":
    main()
