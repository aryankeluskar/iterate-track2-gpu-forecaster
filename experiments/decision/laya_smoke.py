import os, time
os.environ.setdefault("USE_TF", "0")
import torch
torch.set_num_threads(2)
import laya

t = time.time()
agent = laya.load("convaiinnovations/laya", device="mps" if torch.backends.mps.is_available() else "cpu")
print("loaded", round(time.time() - t, 1), "s", agent, flush=True)
state = {"collector": "fastgpu_daily", "gpu": "H100 80GB", "pct_changes_last14": [0, 0, 1.2, 0, 0, -0.5, 0, 0, 0, 0, 0, 0, 0, 0],
         "days_since_change": 9, "n_providers": 7, "median_pos_in_p25_p75": 0.4}
qs = {"dir": {"type": "choice", "instructions": "Over the next 7 days, will this posted GPU rental median price be lower, unchanged or higher than today?",
              "criteria": {"lower": "the price falls", "unchanged": "the price stays exactly the same", "higher": "the price rises"}}}
t = time.time()
r = agent.predict_batch([state] * 16, qs, batch_size=16)
print("16 states", round(time.time() - t, 2), "s", r[0]["answers"], flush=True)
print("temps", agent.temperature, agent.temperature_by_options, flush=True)
