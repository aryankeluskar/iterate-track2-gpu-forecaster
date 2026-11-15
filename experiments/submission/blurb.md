# Platform blurb

Paste into the Projects form. Track 2. Challenges: Exa and past.dev.

## Title

Forecasting the offers behind posted GPU prices

## Description

A posted GPU rental price is the middle of a short list of provider offers. It moves when an offer near the middle is repriced, or when an offer joins or leaves. We forecast that list, 1, 3 and 7 days after 6 November 2026, for every posted rental series in the pack.

On 22,390 forecasts of series first checked on the held-back weeks, pooled skill is 0.228 against 0.102 for the organisers' drift baseline. On the 37 series scored on Sunday it is 0.214 against 0.084. That second number is optimistic, because some members of the blend were kept for doing well on those same weeks. An independent audit keeps only two of the four later members under a correctly sized test. On the six origins after those weeks the pooled score is 0.193 against 0.088, and the equal-series average ties the baseline at 0.155, because quiet series inherit a wide interval. Narrowing those intervals made the headline score worse, so the submitted file keeps them.

One command rebuilds the forecasts from the pack: `bash reproduce.sh final`. Findings, the negative ledger (37 hypotheses, 15 refuted), and the live demo are in the repo. H100 static rate-card rent is a stress range, 3.44 USD per GPU-hour now and 2.28 (1.20 to 4.12) at 24 months. No method beat no change on the long-horizon backtests.

Exa is called from the research loop in `src/gpuf/scout.py`. The announcement calendar it built is switched off in the submitted forecast. The gain on practice dates comes from two events. past.dev is written by the autopsy, the scout and the experimenter, and read by the scout and the proposer. We did not show that the memory improves forecast skill. An unattended run of the loop scored 0.1109 against 0.1419 for the frozen submission on later practice origins.

## Links

- Repo: https://github.com/aryankeluskar/iterate-track2-gpu-forecaster
- Demo page: https://aryankeluskar.github.io/iterate-track2-gpu-forecaster/demo/
- Narrated walkthrough: https://github.com/aryankeluskar/iterate-track2-gpu-forecaster/releases/download/demo-2026-11-14/demo-2min-narrated.mp4
- Forecast files: `submissions/forecast_final_all.csv` and `submissions/forecast_final_headline.csv`
