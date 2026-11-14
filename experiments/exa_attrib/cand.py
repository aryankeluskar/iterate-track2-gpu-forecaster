"""Candidate evidence finder: a BEFORE passage that names the provider and either the event's old/new price or an effective date within +-3 days of D."""
import json, re, sys, datetime as dt
import pandas as pd
from rule import NAME, passages
ROOT = "/Users/aryank/Developer/iterate_hackathon/track_2"
sel = pd.read_csv(f"{ROOT}/runs/exa_attrib/selected.csv").set_index("id")
MONTHS = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
def money(x):
    s = {f"{x:.2f}", f"{x:.1f}" if abs(x*10-round(x*10)) < 1e-6 else "~~"}
    return [re.compile(r"\$\s?" + re.escape(v) + r"(?!\d)") for v in s if v != "~~"]
def datepat(D):
    out = []
    for k in range(-3, 4):
        d = D + dt.timedelta(k); m = MONTHS[d.month-1]
        out.append(re.compile(rf"{m}[a-z]*\.?\s+0?{d.day}\b|\b0?{d.day}(st|nd|rd|th)?\s+(of\s+)?{m}", re.I))
    return out
def find(win="BEFORE"):
    res = {}
    for r in json.load(open(f"{ROOT}/runs/exa_attrib/search_events.json")):
        e = sel.loc[r["id"]]; D = dt.date.fromisoformat(e.date); nm = NAME[r["provider"]].split()[0].lower()
        mp = money(e.old) + money(e.new); dp = datepat(D)
        for s in r["searches"]:
            if s["window"] != win: continue
            for h in s["hits"]:
                for t in passages(h):
                    if nm not in (t + h["url"]).lower() and nm not in (h["title"] or "").lower(): continue
                    why = [("price" if any(p.search(t) for p in mp) else None), ("date" if any(p.search(t) for p in dp) else None)]
                    why = [w for w in why if w]
                    if why and re.search(r"(pric|rate|cost|hour|/hr)", t, re.I) and ((h["published"] < str(D)) if win=="BEFORE" else (h["published"] >= str(D))):
                        res.setdefault(r["id"], {}).setdefault(h["url"], dict(h=h, why=why, t=t)); break
    return res
if __name__ == "__main__":
    res = find(sys.argv[1] if len(sys.argv) > 1 else "BEFORE")
    for i, d in sorted(res.items()):
        e = sel.loc[i]; print(f"=== {i} {e.provider} {e.gpu} D={e.date} old={e.old:.3g} new={e.new:.3g}: {len(d)} cands")
        for u, v in list(d.items())[:int(sys.argv[2]) if len(sys.argv) > 2 else 4]:
            print(f"  {v['h']['published']} {v['why']} {v['h']['title'][:60]} | {u[:80]}")
    print("events without candidate:", sorted(set(sel.index) - set(res)))
