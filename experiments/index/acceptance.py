"""Acceptance test for gpuf.index, frozen in experiments/index/protocol.yaml. Practice dates 2026-09-08..2026-10-06 only.

Run: OMP_NUM_THREADS=2 PYTHONPATH=src .venv/bin/python experiments/index/acceptance.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from gpuf import index as gi
from gpuf import panel

OUT = Path(__file__).parent / "results"
OUT.mkdir(exist_ok=True)
D = gi.ordinal
START, END = D("2026-09-08"), D("2026-10-06")
T0 = START + 7
TDAYS = np.arange(T0, END + 1)
WEEK = (TDAYS - T0) // 7
STATS = ["index", "posted", "balanced", "constant"]
COL = {"index": "index_log", "posted": "posted_log", "balanced": "balanced_log"}
FG, GR = "fastgpu_daily", "gpurentalprices"
EXACT = ["A100 40GB", "B200", "B300", "H100 SXM 80GB", "H200", "L40S", "RTX 6000 Ada", "RTX A6000", "RTX PRO 6000"]
PAIRS = [((FG, g), (GR, g)) for g in EXACT] + [((FG, "A100 80GB"), (GR, "A100 SXM 80GB")),
                                                ((FG, "H100 SXM 80GB"), (GR, "H100 80GB"))]
SERIES = sorted({s for p in PAIRS for s in p})
EVENTS = {"nebius": D("2026-10-01"), "jarvislabs": D("2026-10-05")}
RNG = np.random.default_rng(0)
pname = lambda p: f"{p[0][1]}~{p[1][1]}"


def d7(path: pd.DataFrame, stat: str) -> np.ndarray:
    if stat == "constant":
        return np.zeros(len(TDAYS))
    s = path[COL[stat]]
    return s.reindex(TDAYS).to_numpy() - s.reindex(TDAYS - 7).to_numpy()


P = {s: gi.paths(*s, to_day=END) for s in SERIES}
ROWS = {s: gi.rows(*s, to_day=END) for s in SERIES}

# ---------- (a) cross-collector 7-day disagreement ----------
gap = {st: np.array([np.abs(d7(P[a], st) - d7(P[b], st)) for a, b in PAIRS]) for st in STATS}  # pairs x days
moved = {pname(p): [bool((P[s]["change"].loc[START + 1:END] != 0).any()) for s in p] for p in PAIRS}
active = np.array([any(moved[pname(p)]) for p in PAIRS])
exact9 = np.array([p[0][1] == p[1][1] for p in PAIRS])


def boot(diff: np.ndarray) -> list:
    blocks = np.unique(WEEK)
    est = [np.nanmean(diff[:, np.concatenate([np.where(WEEK == w)[0] for w in RNG.choice(blocks, len(blocks))])])
           for _ in range(4000)]
    return [float(np.percentile(est, 5)), float(np.percentile(est, 95))]


def dsum(mask):
    r = {st: float(np.nanmean(gap[st][mask])) for st in STATS}
    r["ratio_index_to_posted"] = r["index"] / r["posted"]
    r["pass_20pct"] = bool(r["index"] <= 0.80 * r["posted"])
    r["n_pairs"], r["n_pair_days"] = int(mask.sum()), int(np.isfinite(gap["index"][mask]).sum())
    return r


A = {"all_11": dsum(np.ones(len(PAIRS), bool)), "active_pairs": dsum(active), "exact_name_9": dsum(exact9)}
A["all_11"]["diff_index_minus_posted"] = float(np.nanmean(gap["index"] - gap["posted"]))
A["all_11"]["diff_ci90_week_block"] = boot(gap["index"] - gap["posted"])
A["all_11"]["diff_balanced_minus_posted"] = float(np.nanmean(gap["balanced"] - gap["posted"]))
A["all_11"]["diff_balanced_ci90_week_block"] = boot(gap["balanced"] - gap["posted"])
A["never_moved_pairs"] = [pname(p) for p, a in zip(PAIRS, active) if not a]

by_pair = pd.DataFrame([dict(pair=pname(p), index_moved_fg=moved[pname(p)][0], index_moved_grp=moved[pname(p)][1],
                             **{f"D_{st}": float(np.nanmean(gap[st][i])) for st in STATS},
                             diff_index_minus_posted=float(np.nanmean(gap["index"][i] - gap["posted"][i])))
                        for i, p in enumerate(PAIRS)])
by_pair["group"] = np.where(active, "index moved", "index never moved")
by_pair.sort_values(["group", "pair"]).to_csv(OUT / "d_by_pair.csv", index=False)
wk_lab = {w: f"{gi.iso(T0 + 7 * w)}..{gi.iso(min(T0 + 7 * w + 6, END))}" for w in np.unique(WEEK)}
by_week = pd.DataFrame([dict(week=wk_lab[w], n_days=int((WEEK == w).sum()),
                             **{f"D_{st}": float(np.nanmean(gap[st][:, WEEK == w])) for st in STATS},
                             diff_index_minus_posted_all=float(np.nanmean((gap["index"] - gap["posted"])[:, WEEK == w])),
                             diff_index_minus_posted_active=float(np.nanmean((gap["index"] - gap["posted"])[active][:, WEEK == w])))
                        for w in np.unique(WEEK)])
by_week.to_csv(OUT / "d_by_week.csv", index=False)

# activity: share of days each statistic moves
act = {st: float(np.mean([(P[s][COL[st]].diff().loc[START + 1:END].abs() > 1e-12).mean() for s in SERIES]))
       for st in COL}
act["constant"] = 0.0
A["share_of_days_moving"] = act
A["mean_abs_7d_change"] = {st: float(np.nanmean(np.abs(np.array([d7(P[s], st) for s in SERIES])))) for st in STATS}

# ---------- (b) one-provider deletion ----------
S, del_rows = {st: [] for st in ["index", "posted", "balanced"]}, []
for s in SERIES:
    provs = sorted(ROWS[s]["provider"].unique())
    base = {st: d7(P[s], st) for st in S}
    worst = {st: np.zeros(len(TDAYS)) for st in S}
    who = {st: np.array([""] * len(TDAYS), dtype=object) for st in S}
    for p in provs:
        alt = gi.paths(*s, to_day=END, exclude=p)
        for st in S:
            dv = np.abs(d7(alt, st) - base[st]) if not alt.empty else np.abs(base[st])
            dv = np.nan_to_num(dv, nan=0.0)
            upd = dv > worst[st]
            worst[st] = np.where(upd, dv, worst[st])
            who[st] = np.where(upd, p, who[st])
    for st in S:
        S[st].append(worst[st])
    del_rows.append(dict(series=f"{s[0]}|{s[1]}", n_providers=len(provs),
                         **{f"S_{st}": float(worst[st].mean()) for st in S},
                         **{f"max_{st}": float(worst[st].max()) for st in S},
                         most_pivotal_index=pd.Series(who["index"][worst["index"] > 0]).mode().tolist()[:1],
                         most_pivotal_posted=pd.Series(who["posted"][worst["posted"] > 0]).mode().tolist()[:1]))
B = {st: float(np.mean(S[st])) for st in S}
B["pass"] = bool(B["index"] < B["posted"])
B["n_series"], B["n_days"] = len(SERIES), len(TDAYS)
pd.DataFrame(del_rows).to_csv(OUT / "b_deletion_by_series.csv", index=False)

# ---------- (c) responsiveness to Nebius and Jarvislabs ----------
C = []
for s in SERIES:
    core = gi._core(ROWS[s])
    for prov, eff in EVENTS.items():
        w = [d for d in range(eff - 1, eff + 2) if d in core.index]
        rp = [core.at[d, "r"].get(prov) for d in w]
        rp = [v for v in rp if v is not None]
        if not rp:
            continue
        R = float(np.sum(rp))
        lo, hi = eff - 2, eff + 1
        mv = {st: float(P[s][COL[st]].loc[hi] - P[s][COL[st]].loc[lo]) for st in COL}
        C.append(dict(series=f"{s[0]}|{s[1]}", provider=prov, effective=gi.iso(eff), provider_move=R,
                      eligible=abs(R) >= 0.03, matched_providers_eff=int(core.at[eff, "providers"]) if eff in core.index else 0,
                      **{f"move_{st}": mv[st] for st in COL}, move_constant=0.0,
                      **{f"retained_{st}": mv[st] / R if R else np.nan for st in COL}, retained_constant=0.0))
Cdf = pd.DataFrame(C)
Cdf.to_csv(OUT / "c_responsiveness.csv", index=False)
el = Cdf[Cdf.eligible]
Cres = {}
for st in STATS:
    mvst = el[f"move_{st}"].to_numpy()
    right = np.sign(mvst) == np.sign(el.provider_move.to_numpy())
    Cres[st] = dict(n_cases=int(len(el)), right_direction=int(right.sum()), share_right=float(right.mean()) if len(el) else np.nan,
                    mean_retention=float(el[f"retained_{st}"].mean()) if len(el) else np.nan,
                    median_retention=float(el[f"retained_{st}"].median()) if len(el) else np.nan,
                    pass_rule=bool(len(el) and right.mean() >= 0.8 and el[f"retained_{st}"].mean() > 0))
Cres["mean_one_over_matched_providers"] = float((1 / el.matched_providers_eff.replace(0, np.nan)).mean())

# ---------- coverage and duplication ----------
inv = []
for s in SERIES:
    t = gi.compute(*s, to_day=END)
    w = t[(t.day >= START) & (t.day <= END) & ~t.anchor]
    inv.append(dict(series=f"{s[0]}|{s[1]}", days=len(w), invalid_days=int((~w.valid).sum()),
                    mean_matched_providers=float(w.providers.mean()), mean_providers_present=float(w.providers_present.mean()),
                    mean_matched_offers=float(w.offers.mean()), mean_offers_present=float(w.offers_present.mean()),
                    mean_largest_share=float(w.largest_provider_share.mean()), mean_removal_1d=float(w.one_provider_removal.mean())))
INV = pd.DataFrame(inv)
INV.to_csv(OUT / "d_coverage_by_series.csv", index=False)
full = panel.load()
dup = {src: sorted(set(full[full.src == src].provider) & set(gi.ALIASES)) for src in (FG, GR)}
alias_hits = {src: [a for a in dup[src] if gi.ALIASES[a] in set(full[full.src == src].provider)] for src in dup}

inv_share = INV.invalid_days.sum() / INV.days.sum()
drop = {"inactivity": not A["active_pairs"]["pass_20pct"],
        "provider_duplication": any(alias_hits.values()) or not A["exact_name_9"]["pass_20pct"],
        "discarded_or_invalid_days_over_20pct": bool(inv_share > 0.20),
        "responsiveness_fails": not Cres["index"]["pass_rule"]}
summary = dict(window=[gi.iso(START), gi.iso(END)], target_days=[gi.iso(T0), gi.iso(END)], min_providers=gi.MIN_PROVIDERS,
               a_disagreement=A, b_deletion=B, c_responsiveness=Cres,
               d_invalid_days=dict(total=int(INV.invalid_days.sum()), of=int(INV.days.sum()), share=float(inv_share)),
               alias_conflicts_within_collector=alias_hits,
               pass_a=A["all_11"]["pass_20pct"], pass_b=B["pass"], pass_c=Cres["index"]["pass_rule"],
               constant_fails_c=not Cres["constant"]["pass_rule"], drop_checks=drop)
summary["product_claim"] = bool(summary["pass_a"] and summary["pass_b"] and summary["pass_c"] and not any(drop.values()))
(OUT / "acceptance.json").write_text(json.dumps(summary, indent=2, default=str))
print(json.dumps(summary, indent=2, default=str))
print(by_pair.sort_values(["group", "pair"]).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
print(by_week.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
print(Cdf.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
print(pd.DataFrame(del_rows).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
print(INV.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
