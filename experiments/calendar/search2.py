"""Follow-up searches: effective-November notices, specific leads, and change-news sites, weekly windows. End dates <= 2026-11-06."""
import datetime as dt, json, sys, pathlib
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from search import body, run_job, OUT, TAG, CUTOFF
from gpuf.scout import exa_spend


def weeks(a, b):
    d = dt.date.fromisoformat(a)
    while d <= dt.date.fromisoformat(b):
        e = min(d + dt.timedelta(6), CUTOFF)
        yield str(d), str(e)
        d = e + dt.timedelta(1)


J = []
for s, e in weeks("2026-10-01", "2026-11-06"):
    for k, q in enumerate(["GPU cloud price increase effective November 2026, new per-hour GPU rates announced",
                           "GPU price cut takes effect in November 2026 on-demand H100 B200 per hour",
                           "provider announces upcoming GPU pricing changes on November 15 2026"]):
        J.append(("_nov", f"nov{k}", s, e, body(q, s, e)))
for s, e in weeks("2026-08-01", "2026-11-06"):
    J.append(("_gpujournal", "gj", s, e, body("GPU cloud provider announces or raises GPU prices", s, e, ["gpujournal.ai"])))
    J.append(("_modelswar", "mw", s, e, body("GPU price increase or decrease effective date", s, e, ["modelswar.com"])))
LEADS = [("lambdalabs", "Lambda GPU price increase from November 16 2026 B200 H100 A100", ["lambda.ai", "lambdalabs.com"]),
         ("lambdalabs", "Lambda announces GPU price rises about 15% from Nov 16", None),
         ("salad", "SaladCloud price changes November 1 2026 GPU priority pricing", None),
         ("aws", "AWS EC2 Capacity Blocks for ML price increase October 7 2026", None),
         ("aws", "AWS EC2 GPU instance price reduction effective date 2026 P5 P6", None),
         ("digitalocean", "DigitalOcean GPU Droplet H100 price increase effective date", None),
         ("coreweave", "CoreWeave GPU price increase effective date notice customers", None),
         ("crusoe", "Crusoe H100 GPU price increase reversed October 2026", None),
         ("modal", "Modal lowers H100 GPU price to $3.95 per hour", None),
         ("verda", "Verda GPU price increase announced effective date", None),
         ("fireworks", "Fireworks AI GPU price increase effective September 1", None),
         ("together", "Together AI GPU price change effective date", None),
         ("_eu", "three European GPU clouds raised prices for October 2026", None),
         ("hyperstack", "Hyperstack price increase GPU effective date 2026", None),
         ("runpod", "GPU cloud raises prices with 30 days notice effective date", None)]
for slug, q, dom in LEADS:
    for s, e in (("2026-08-01", "2026-09-15"), ("2026-09-16", "2026-10-20"), ("2026-10-21", "2026-11-06")):
        J.append((slug, "lead", s, e, body(q, s, e, dom)))

if __name__ == "__main__":
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(run_job, J))
    json.dump(res, open(OUT / "search_run2.json", "w"))
    print(len(res), "searches; errors:", sum(bool(r["error"]) for r in res), "| spend $", exa_spend(TAG))
