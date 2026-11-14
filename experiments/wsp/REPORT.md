# Direct weight edits for GPU-price quantiles

**Verdict: a small, uncertain improvement over mix; a clear improvement over the particular Adam and random-search controls run here. Do not nominate for validation on this evidence.**

All results below use the headline rental universe, horizons 1/3/7, and pooled dollar pinball skill relative to last value. The held-out period is **September 12–October 6, 2026: 2,775 cells, 37 series, 25 origins, five ISO-week blocks**. It is the second half of dev, not the project's official validation split.

## Frozen comparison

| Method | Practice skill, 1,503 cells | Held-out skill | Held-out difference versus mix, 90% paired interval | Nonzero parameters |
|---|---:|---:|---|---:|
| Reference mix | 0.172004 | 0.168500 | reference | — |
| Hand-written qnet | 0.173870 | **0.174409** | +0.005909 [−0.000684, +0.007466] | **17 / 579** |
| Adam, literal all-zero initialization | 0.172004 | 0.168500 | 0 [0, 0] | 0 |
| Adam, random hidden layer / zero output | 0.320419 | 0.079924 | −0.088576 [−0.120398, −0.077085] | 573 |
| Random search, 40 scored proposals | 0.203397 | 0.152788 | −0.015712 [−0.020132, −0.014324] | 264 |
| Random search, 50 scored proposals | 0.203397 | 0.152788 | −0.015712 [−0.020132, −0.014324] | 264 |
| Half hand / half mix, averaged log quantiles | 0.173108 | 0.171553 | +0.003053 [−0.000261, +0.003833] | — |
| Drift | — | 0.086847 | — | — |

Hand minus drift: **+0.087562 [0.052071, 0.097053]**. Hand minus trainable Adam: **+0.094484 [0.084098, 0.122934]**. Hand minus random40: **+0.021620 [0.018746, 0.024274]**. Intervals use `gpuf.compare.paired`, 2,000 origin-week bootstrap draws, seed 0.

Full dev, including the practice cells used for selection, gives hand **0.174315**, mix **0.169109**, and drift **0.088649** on 4,278 cells. Hand-minus-mix is +0.005206 [0.000188, 0.007607]; hand-minus-drift is +0.085666 [0.057744, 0.100072]. The blend scores 0.171824, +0.002714 [0.000219, 0.003895] over mix. These full-dev intervals are descriptive, not independent evidence after selection.

The all-zero network reproduces every mix forecast bit-for-bit: maximum quantile difference **0**, and both full-dev skills are **0.169109** to six decimals.

## Hypotheses and controls

Every numbered JSON was written before its candidate was scored. Each candidate inserts one new ReLU unit: a read vector and bias, plus a three-output write vector. This is a rank-one insertion in each weight matrix, rather than one rank-one update to a pretrained matrix. Magnitudes were chosen by the writer from a mechanism, not swept. Gains below are incremental over the then-current incumbent.

| Hypothesis | Decision | Practice gain | Reversed-write control gain | Equal-norm random-direction gain |
|---|---|---:|---:|---:|
| 01: widen lower tail at h7 after a recent change | reject | −0.005392 | — | — |
| 02: shrink both tails after 14 idle days | keep | +0.000164 | −0.000176 | −0.050081 |
| 03: widen upper tail when median lies toward panel p25 | keep | +0.000422 | −0.004200 | −0.006073 |
| 04: shrink the h1 upper tail | reject | −0.001838 | — | — |
| 05: widen afhubbard h7 lower tail | keep | +0.001222 | −0.001282 | −0.006110 |
| 06: widen lower tail when median lies toward panel p75 | reject | −0.002456 | — | — |
| 07: shrink both tails when own volatility is below peers | keep | +0.000057 | −0.000058 | −0.006787 |
| 08: widen upper tail at h7 after a recent change | reject | −0.011931 | — | — |

**17/40 hand-tool calls** were used: one zero baseline, eight candidates, eight controls. Each sign control reverses the output write vector while retaining the gate. Each random control rotates the augmented read direction and output direction separately, preserving both norms and hence the full parameter-edit norm. All four kept rules beat both controls. This supports direction specificity on practice, but four individual random draws do not establish superiority over a distribution of random directions.

The final kept prefix is fixed at rules 02+03+05+07. Its held-out skill is 0.174409. Earlier kept prefixes were scored once at the end: 02 alone 0.168488; 02+03 0.174822; 02+03+05 0.174331. **We did not switch to the better held-out prefix.**

The worst practice candidate, recent-change upper widening, lost entirely at h7: −0.010648 pooled-skill contribution from gpurentalprices and −0.001283 from afhubbard. It harmed all five outcome buckets, particularly downward moves (−0.005670). Recent activity alone was not a reliable signal to buy more upside spread.

## What the kept rules teach

The upper-panel rule accounts for essentially all the net held-out benefit. A median near p25, with p75 farther above it, provides a useful conditional measure of possible upward movement in the posted-price panel. The observed gain is consistent with that explanation; this experiment does not identify which provider repriced or establish a causal effect of panel geometry.

Incremental held-out prefix effects are: dormant shrink −0.000012, panel upper widening **+0.006333**, afhubbard lower widening −0.000491, relative-volatility shrink +0.000078. Thus the practice result for the afhubbard rule did not generalize, and the two shrinkage rules added little.

Hand-versus-mix held-out gains, as contributions to the total pooled-skill difference:

| Partition | Contribution |
|---|---:|
| gpurentalprices / fastgpu_daily / afhubbard | +0.004229 / +0.002784 / −0.001104 |
| h1 / h3 / h7 | +0.000039 / +0.000895 / +0.004974 |
| unchanged / under 1% / 1–5% | −0.000894 / −0.000269 / +0.001288 |
| upward over 5% / downward over 5% | +0.005842 / −0.000059 |

The three largest positive series contributions are gpurentalprices B300 rate card **+0.002377**, fastgpu B300 rate card **+0.001079**, and fastgpu RTX PRO 6000 rate card **+0.000703**. The largest losses are afhubbard A100 40GB spot **−0.000561**, afhubbard A100 SXM 80GB spot **−0.000356**, and gpurentalprices H100 80GB marketplace spot **−0.000245**.

This residual architecture has a limitation: multiplying an exactly zero base tail offset cannot create a new nonzero tail offset. On practice, 962 lower offsets and 934 upper offsets were zero. Aggregate undercoverage therefore does not imply that a multiplicative widening rule can fix the missing tail.

## Gradient and search controls

The network has 20 fixed-scale causal features, 24 ReLU units, and three outputs. Literal all-zero initialization leaves the hidden matrices with zero gradients; only the output bias can initially learn. The regression test verifies this. Adam tried 40 epochs but early stopping selected epoch 0.

To avoid presenting a disabled learner as a meaningful comparison, the second Adam run initializes the hidden layer with seed 31415 and leaves the output layer zero. It starts with exactly the same forecast function as mix, while allowing feature-dependent training. Adam uses learning rate 0.01 and dollar pinball loss, with up to 500 epochs and patience 40. Its selected checkpoint is epoch 26, from a 66-epoch run.

Early stopping uses September 5–11 origins (593 cells). Training uses earlier practice origins whose targets precede September 5 (731 cells), purging 179 overlapping-target cells. There is no final refit on the early-stopping cells.

The trainable network performs well on practice but poorly on held-out data. A material distribution shift accompanies that failure: fastgpu contributes only **4.55%** of practice last-value loss and **52.69%** of held-out loss. Its history begins September 8, so the gradient fitting portion contains no fastgpu series. These results show a failure of this fixed training recipe, not that gradient training in general is inferior.

Random search uses seed 2718 and independent random one-unit mutations of its incumbent, with read norm 1 and write norm 0.2. Fifty scored steps cannot fit a forty-call cap. We therefore froze the 40-call result for the matched **budget ceiling**, and reported the 50-call sensitivity separately. Steps 41–50 did not improve the selected weights. The hand writer used only 17 of its 40 calls, so actual evaluation counts are unequal.

**Writing weights by hand added held-out skill over the trained comparator in this run. It did not demonstrate a statistically reliable improvement over leaving mix unchanged, nor a general advantage over competent gradient training.** Only one writer trajectory, one initialization, and one search seed were tested.

## Integrity, uncertainty, and coverage

The requested chronological split shares target dates through September 18. Practice scoring and early stopping can therefore reveal outcomes later than the first held-out origins. The preregistered sensitivity starts held-out origins on September 19, after the last practice target: 1,998 cells and four week blocks. Hand scores **0.178288** versus mix **0.171518**, a difference **+0.006770 [−0.000447, 0.007957]**. This sensitivity uses the same saved predictions, not a second forecasting run. It still does not establish improvement over mix.

The supplied briefs already described full-dev failures, so this was not a pristine blind discovery. We made no official-validation query and fetched no price data. The literature note's search did not find previous forecasting WSP work; that does not prove the claim that nobody has published it. No novelty claim was independently verified here.

Strict held-out coverage is **68.47%** for hand and **69.01%** for mix. Hand lower/upper tail miss rates are **10.77% / 20.76%**; mix's are **9.37% / 21.62%**. The log/exp transformation creates tiny floating-point round trips at collapsed intervals. A separately labeled diagnostic using absolute and relative tolerance 1e−12 on the same saved predictions gives coverage **69.91%** for hand and **69.05%** for mix; hand misses **9.44% / 20.65%**. Strict harness coverage remains primary. No weights or forecast implementation were altered after observing held-out results.

The first baseline command failed on relative-path formatting before any forward pass. After all final forecasts were saved, reporting failed on a duplicated grouping column and then an undefined DM statistic for identical predictions. Those reporting bugs were fixed, and `finish` regenerated summaries exclusively from saved forecasts. No held-out model was rerun. Hashes of the runner as it existed before evaluation remain in `heldout_started.json`; the later runner changes only repair reporting.

Six focused tests pass, covering zero identity, quantile ordering, future auxiliary/history perturbations, zero-initialization gradients, budget/freeze refusal, and reporting failures. `audit.py` reconstructs every candidate and control exactly, verifies frozen hashes and call counts, and confirms cached scoring matches registered-method practice forecasts.

The next useful experiment is a newly preregistered test of the panel upper-tail rule on another untouched period, with several trained-network initializations and collector-balanced training. This run does not request a validation query.
