"""Part B (dev rows <= 2026-10-13 only) and Part C membership (panel of 2026-11-06, membership only).
B1: did the provider's panel offer change on the effective day to the announced price?
B2: calendar-adjusted centre vs last value on headline cells with origin in [published, effective) and target >= effective."""
import datetime as dt, json, pathlib, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from gpuf import panel, data
from calendar_lib import load, effective_day, apply_to_panel, TIER_MAP, _day, COLLECTOR_LAG

ROOT = pathlib.Path(__file__).resolve().parents[2]
RES = ROOT / "experiments/calendar/results"
DEV_END = _day("2026-10-13")
df = panel.load()
dev = df[df.day <= DEV_END]
headline = [s for s in data.universe("rental_headline") if s.split(".")[0] in panel.SOURCES]
hl_keys = {panel.parse_sid(s): s for s in headline}

# ---------- B1
rows = []
for e in load():
    eff = effective_day(e)
    if eff > DEV_END:
        continue
    for c in e["changes"]:
        tiers = TIER_MAP.get(c["tier"], set())
        sub = dev[(dev.provider == e["provider"]) & dev.gpu.isin(c["panel_gpus"]) & dev.tier.isin(tiers)]
        for (src, cls, gpu, tier), g in sub.groupby(["src", "cls", "gpu", "tier"]):
            daily = g.groupby("day")["price"].apply(lambda x: np.sort(x.to_numpy()))
            pre_days = [d for d in daily.index if d < eff]
            if not pre_days:
                rows.append(dict(provider=e["provider"], eff=e["effective_date"], gpu=c["gpu"], ann_tier=c["tier"], src=src, gpu_panel=gpu, tier=tier,
                                 status="no_panel_data_before")); continue
            pre = daily[max(pre_days)]
            # which offer this announced tier refers to: the provider offer closest to the announced old price
            ref = pre[np.argmin(np.abs(pre - c["old"]))] if c["old"] else np.median(pre)
            if c["old"] and abs(ref / c["old"] - 1) > 0.03:
                rows.append(dict(provider=e["provider"], eff=e["effective_date"], gpu=c["gpu"], ann_tier=c["tier"], src=src, gpu_panel=gpu, tier=tier,
                                 pre=float(ref), old=c["old"], new=c["new"], status="old_price_not_in_panel")); continue
            win = [d for d in daily.index if eff - 10 <= d <= eff + 10]
            chg = next((d for d in win if d >= max(pre_days) and not np.any(np.isclose(daily[d], ref, rtol=0.005))), None)
            post_days = [d for d in daily.index if d >= eff]
            post = daily[chg] if chg is not None else (daily[min(post_days)] if post_days else None)
            near = None if post is None else float(post[np.argmin(np.abs(post - c["new"]))])
            hit = near is not None and abs(near / c["new"] - 1) <= 0.02 and chg is not None and abs(chg - eff) <= 2
            rows.append(dict(provider=e["provider"], eff=e["effective_date"], gpu=c["gpu"], ann_tier=c["tier"], src=src, gpu_panel=gpu, tier=tier,
                             pre=float(ref), old=c["old"], new=c["new"], post_nearest=near,
                             price_err=None if near is None else round(near - c["new"], 4),
                             change_day=None if chg is None else str(dt.date.fromordinal(chg)),
                             date_err=None if chg is None else chg - eff, status="hit" if hit else "miss",
                             first_post_day=None if not post_days else str(dt.date.fromordinal(min(post_days)))))
b1 = pd.DataFrame(rows)
b1.to_csv(RES / "b1_panel_check.csv", index=False)

# ---------- B2
cells = pd.read_parquet(ROOT / "runs/failure/blend_dev_cells.parquet")
cells = cells[cells.target_day <= DEV_END]
tot_lv = cells.baseline_loss.sum()
out = []
for e in load():
    eff, pub = effective_day(e), _day(e["published"])
    if eff > DEV_END or e["confidence"] > "B":
        continue
    for key, sid in hl_keys.items():
        src, cls, gpu, tier = key
        if not any(gpu in c["panel_gpus"] and tier in TIER_MAP.get(c["tier"], set()) for c in e["changes"]):
            continue
        rws = panel.offers(sid, DEV_END)
        if not (rws.provider == e["provider"]).any():
            continue
        cs = cells[(cells.series_id == sid) & (cells.origin_day >= pub) & (cells.origin_day < eff) & (cells.target_day >= eff)]
        for r in cs.itertuples():
            c_adj, applied = apply_to_panel(rws, e["provider"], gpu, tier, r.target_day, r.origin_day, lag=COLLECTOR_LAG[src])
            c0, _ = apply_to_panel(rws, e["provider"], gpu, tier, r.target_day, r.origin_day, lag=0)
            if c_adj is None:
                continue
            lv = r.baseline
            out.append(dict(event=f"{e['provider']} {e['effective_date']}", series=sid, origin=str(r.origin_date)[:10], h=r.horizon_days,
                            y=r.y, last=lv, adj=c_adj, applied=len(applied), err_lv=abs(r.y - lv), err_adj=abs(r.y - c_adj),
                            lv_loss=r.baseline_loss, adj_loss=0.5 * abs(r.y - c_adj), adj0_loss=0.5 * abs(r.y - c0), blend_q50=r.q50,
                            blend_q50_loss=0.5 * abs(r.y - r.q50)))
b2 = pd.DataFrame(out)
b2.to_csv(RES / "b2_cells.csv", index=False)
# sanity: baseline_loss == 0.5*|y - last| (point forecast at all three quantiles)
chk = float(np.nanmax(np.abs(b2.lv_loss - 0.5 * b2.err_lv))) if len(b2) else 0.0
summ = b2.groupby(["event", "series"]).agg(cells=("h", "size"), lv_loss=("lv_loss", "sum"), adj_loss=("adj_loss", "sum")).reset_index()
summ["removed"] = 1 - summ.adj_loss / summ.lv_loss
summ["share_total_dev_lv_loss"] = summ.lv_loss / tot_lv
summ["removed_nolag"] = 1 - b2.groupby(["event", "series"]).adj0_loss.sum().values / summ.lv_loss
ev = b2.groupby("event").agg(cells=("h", "size"), lv_loss=("lv_loss", "sum"), adj_loss=("adj_loss", "sum"), adj0_loss=("adj0_loss", "sum"),
                             moved=("applied", lambda x: int((x > 0).sum()))).reset_index()
ev = pd.concat([ev, pd.DataFrame([dict(event="ALL", cells=ev.cells.sum(), lv_loss=ev.lv_loss.sum(), adj_loss=ev.adj_loss.sum(),
                                       adj0_loss=ev.adj0_loss.sum(), moved=ev.moved.sum())])], ignore_index=True)
ev["removed"] = 1 - ev.adj_loss / ev.lv_loss
ev["removed_nolag"] = 1 - ev.adj0_loss / ev.lv_loss
ev["share_total_dev_lv_loss"] = ev.lv_loss / tot_lv
ev["loss_removed_share_of_total"] = (ev.lv_loss - ev.adj_loss) / tot_lv

# ---------- Part C membership (panel of 2026-11-06, membership only; no prices analysed)
D6 = _day("2026-11-06")
memb = []
for e in load():
    if not (_day("2026-11-01") <= effective_day(e) <= _day("2026-11-20")) or _day(e["published"]) > D6:
        continue
    for c in e["changes"]:
        sub = df[(df.day == D6) & (df.provider == e["provider"]) & df.gpu.isin(c["panel_gpus"]) & df.tier.isin(TIER_MAP.get(c["tier"], set()))]
        for (src, cls, gpu, tier), g in sub.groupby(["src", "cls", "gpu", "tier"]):
            sid = f"{src}.{cls}.{gpu.replace(' ', '_')}.{tier}.median"
            memb.append(dict(provider=e["provider"], eff=e["effective_date"], gpu=c["gpu"], ann_tier=c["tier"], series=sid,
                             headline=sid in headline, n_offers_panel=int((df.day == D6).mul(df.src == src).mul(df.cls == cls).mul(df.gpu == gpu).mul(df.tier == tier).sum())))
memb = pd.DataFrame(memb).drop_duplicates("series" if False else ["provider", "eff", "series"])
memb.to_csv(RES / "partc_membership.csv", index=False)

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)
print("B1\n", b1.drop(columns=["first_post_day"], errors="ignore").to_string(index=False))
print("\nB2 baseline check max|lv_loss-0.5|e||:", chk, " total dev last-value loss:", round(tot_lv, 4), " cells:", len(cells))
print(summ.to_string(index=False)); print(ev.to_string(index=False))
print("\nPart C\n", memb.to_string(index=False))
json.dump(dict(b1_rows=len(b1), b1_hits=int((b1.status == "hit").sum()), b1_checkable=int(b1.status.isin(["hit", "miss"]).sum()),
               events=ev.to_dict("records"), total_dev_lv_loss=tot_lv), open(RES / "partb_summary.json", "w"), indent=1, default=float)
