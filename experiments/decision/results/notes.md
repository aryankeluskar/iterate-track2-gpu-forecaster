# decision: results (dev only; train origins 2026-08-18..09-14, targets <= 09-21; test origins 09-22..10-06)

Dataset rental_all: 18,416 train cells, 14,615 test cells (runs/decision/cells.parquet, built by build.py).
3-way base rates  train: down 0.071 / flat 0.850 / up 0.078   test: 0.077 / 0.732 / 0.191 (up-moves 2.4x: regime shift).
Headline only     train: 0.209 / 0.630 / 0.160               test: 0.156 / 0.380 / 0.464.

## 3-way, same 3,000 stratified test cells (logloss / Brier / acc / AUC move-vs-no-move)
base rate (collector x h)        0.760 / 0.427 / 0.732 / 0.683
logistic (18k train)             0.562 / 0.298 / 0.794 / 0.895
LightGBM (18k train)             0.491 / 0.256 / 0.814 / 0.910
logistic (same 2k train)         0.609 / 0.305 / 0.789 / 0.891
LightGBM (same 2k train)         0.605 / 0.303 / 0.788 / 0.904
Laya zero-shot raw (T=1)         1.851 / 1.152 / 0.109 / 0.275   (mean P(lower)=0.67; ranking inverted)
Laya + temperature (T=54.6)      1.105 / 0.671 / 0.109 / 0.288   (T explodes: logits carry no usable signal as given)
Laya + temperature + class bias  0.812 / 0.448 / 0.732 / 0.287   (worse than base rate)
Laya 8 log-probs -> logistic     0.635 / 0.341 / 0.754 / 0.845   (readout recovers some signal; still below LR on 2k)
Full test (14,615): base 0.769, logistic 0.576, LightGBM 0.514. Headline subset (1,665): 1.569 / 1.280 / 1.202.
5-level: base 0.920, logistic 0.768, LightGBM 0.742, Laya temp 1.596, Laya temp+bias 0.939, Laya readout 0.815.

Fine-tune: not completed. laya.train.finetune ran (frozen encoder, 1,500 rows = 2,700 items, 1 epoch, 245 s), but the
process grew to 7.2 GB while scoring the test cells and the orchestrator killed it. ps RSS had shown about 0.1 GB, because MPS
unified memory is not counted in RSS. No fine-tuned number exists.

## Step 4: method `decision` (LightGBM probabilities + pooled up/down move sizes), rental_headline, test origins, 1,665 cells
drift 0.0795, mix 0.1653, decision 0.0987, ens(mix, decision) 0.1561.
decision - drift +0.019 [+0.011, +0.025]; decision - mix -0.067 [-0.070, -0.058]; ens - mix -0.009 [-0.013, +0.005].
(90% intervals from only 3 ISO weeks: too narrow to trust.)

## Step 5: weight-space programming (dspy-wsp), reading only
Published: a 25-pass run on a decision model took 68-167 min and $5.42-$10.78 of writer calls (gpt-6-astra, max effort);
gains of 2-16 points on Typed Decisions. Laya is not one of the five supported families (d1, NanoJev, d1-2B, Clef, Strands),
so a run needs a new backend first. Forward passes would be cheap here (about 31 cells/s on MPS, so a 300-cell holdout pass is about 10 s).
The cost is the writer's time, and the same per-pass budget applies. The technique needs one fault: "editing removes obstacles; it doesn't add abilities" (Gemma 270M barely moved).
Our failure is missing capability. The encoder has no prior that maps 14 numbers to price dynamics, and an 8-parameter readout of its own outputs
still loses to logistic regression on the raw numbers. The one fault-like symptom (ranking inverted, P(lower)=0.67) is already
removed by a recalibration layer at zero cost. Not worth running.
