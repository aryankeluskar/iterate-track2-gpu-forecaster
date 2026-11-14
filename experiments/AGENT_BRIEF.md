# Shared brief for method agents (read fully before starting)

## The task

Iterate SF AI Research Hackathon, Track 2 (Pacific). Forecast posted GPU rental prices (USD per GPU-hour, one daily value per series) as q10, q50, q90 at horizons 1, 3 and 7 days. Score is pinball loss; skill is 1 minus loss over last-value loss, pooled over all cells (a ratio of summed losses, so high-priced, volatile series dominate). The bar is `drift`: the last value scaled by the empirical 0.1/0.5/0.9 quantiles of that series' own historical h-day log changes (flat when it has fewer than 20 samples). You are one of about nine agents each exploring one direction in parallel. The goal of this round is fast prototyping: find out quickly whether your direction beats drift on dev, and why or why not. A clean negative result is as useful as a win.

## What Sunday scores (measured)

37 series: the headline tier of the posted rental series as of 2026-11-06 (universe `rental_headline`). 20 from collector `fastgpu_daily` (history starts 2026-09-08), 13 from `gpurentalprices` (starts 2026-08-04), 4 `afhubbard` hyperscaler spot (from January). By class: 23 neocloud_rate_card, 7 neocloud_spot, 6 hyperscaler_spot, 1 marketplace_ask. Each value is a median over the offers a collector saw that day (3 to 17 providers). The wider universe `rental_all` has 592 series and can be used as training data for pooled models.

## What is already known (dev-period data only)

- The scored series change on about a third of days (fastgpu median 0.32, gpurentalprices 0.39, afhubbard 0.10). They are not rare-step series.
- Smoothing the centre loses: as a point forecast, the median of the last 3 or 5 days or an EWMA is worse than the last value on almost every series (loss-weighted error ratio 1.6 at h=1, 1.2 at h=3, 1.1 at h=7). Exceptions: fastgpu A100_40GB and A100_80GB rate cards at h=3 and h=7 (ratio 0.5 to 0.7).
- Partial reversion at longer horizons on fastgpu: regressing the h-day-ahead change on the latest one-day change gives a median slope of about -0.18 (h=3) and -0.26 (h=7). gpurentalprices shows the opposite sign (+0.20, +0.38) and some of its rate cards have lag-1 autocorrelation of 0.4 to 0.6. Samples are small (36 to 71 days).
- Loss is concentrated. Share of h=7 last-value absolute error on dev: fastgpu B300 rate card 19%, fastgpu B200 rate card 11%, gpurentalprices H100_80GB marketplace spot 9%, fastgpu H100_PCIe rate card 6%, gpurentalprices B300 6%.
- On older afhubbard data: changes cluster (chance of a change 0.63 the day after one, 0.155 on average, 0.03 after two idle weeks); a change in provider count marks a step the same day; no day-of-week or month-start effect; no lead-lag found on 19 series.
- Drift's skill on headline series in May to August was about +0.09, almost all at h=7. On all rental series drift was worse than last value because its intervals come from rare large jumps. Halving drift's interval width recovered 0.04 to 0.08 skill on some classes.
- Histories are short (60 to 89 days for 33 of 37 series), so per-series quantiles rest on few samples.

## The harness (do not edit it)

Package `src/gpuf/`. Run from the project root `/Users/aryank/Developer/iterate_hackathon/track_2` with `PYTHONPATH=src .venv/bin/python -m gpuf.run --method NAME --split dev --universe rental_headline --params '{"k": 3}'`. It prints one JSON line and appends it to `data_out/trajectory.jsonl` (add `--no-log` while debugging). Read `src/gpuf/harness.py`, `src/gpuf/methods/__init__.py`, `src/gpuf/compare.py` and `EVAL_PROTOCOL.md` (including Amendment 1) first. Another agent is finishing the harness right now: if a command fails because of that, re-read the code and retry after a minute rather than patching it.

A method is a file `src/gpuf/methods/<your_slug>.py`:

```python
from gpuf.methods import register

@register("my_method")
def make(**params):
    def f(sid, days, vals, origin_day, horizons, ctx):
        # days, vals: this series' history truncated at origin_day
        # ctx.history(other_sid): another series truncated at the same origin; ctx.meta(sid): static catalog fields
        return {h: (q10, q50, q90) for h in horizons}
    return f
```

Use `gpuf.compare` for the paired difference against drift with its 90% block-bootstrap interval. Report it.

## Rules (hard)

1. Dev split only (`--split dev`, daily origins 2026-08-18 to 2026-10-06). Never run `--split val`, never read values dated after 2026-10-13 for tuning or model fitting outside the harness, never fetch any price data from the network. The orchestrator alone runs validation, once per nominated method.
2. A forecast for origin d may use only rows dated on or before d, for every series and every auxiliary table. If you read pack tables directly (for example `rental_observations/`), filter by date inside the forecaster and include a test showing that perturbing data after the origin leaves the forecast unchanged.
3. The data pack `data/pack/` is read-only. Do not edit the harness, `EVAL_PROTOCOL.md`, `research-state.yaml`, `findings.md`, `research-log.md`, `.scratch/`, or other agents' files. Your files: `src/gpuf/methods/<your_slug>*.py` and `experiments/<your_slug>/` (code, small result files). Scratch goes under `runs/<your_slug>/`.
4. Before the first run, save `experiments/<your_slug>/protocol.yaml`: the hypothesis, the mechanism, the prediction (direction and rough size, and on which series group), and what result would refute it. Then run. If a file write is refused, do not work around it: put the content in your final report.
5. Do not git commit. Install packages only with `uv pip install --python .venv/bin/python <pkg>`.
6. Shell is zsh: call the interpreter path directly; do not store a command with flags in a variable.
7. Time budget about 25 minutes. Start with the simplest version that could show the effect, score it, then refine. Do not polish. Stop when you have a clear answer.
8. Explain, do not only sweep: for the best and worst variants say which series and horizons moved and why.

## Final report (under 350 words; it is all the orchestrator reads)

- Verdict in one line: beats drift on dev / ties / loses.
- Best configuration: registered method name and exact params, dev pooled skill, drift's dev pooled skill on the same cells, the paired difference with its 90% interval, coverage of [q10, q90].
- Breakdown of the gain or loss by collector and by horizon, and the top three series that moved.
- The mechanism: why it works or fails, in two or three sentences.
- Variants tried, one line each with the number.
- Whether you nominate the method for a validation query (yes or no) and with which frozen params.
- What you ran versus what you assume, and anything that failed to run.
