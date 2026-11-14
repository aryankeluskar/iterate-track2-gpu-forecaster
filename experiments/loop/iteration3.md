# Iteration 3, run end to end with `python -m gpuf.loop` (14 Nov 2026, 20:52 to 20:57 UTC)

Run from `track_2/` with `PYTHONPATH=src`, live past.dev (`PAST_ALLOW_WRITES=1`) and live Exa, dev period only. The full JSON
of every step is one line in `data_out/loop_journal.jsonl`; outputs below are trimmed. Offline replay of all of it:
`LOOP_OFFLINE=1 python -m gpuf.loop ...` (tests/test_loop.py does this with the network disabled).

## 1. Autopsy of the current four-member blend

```
$ python -m gpuf.loop autopsy --system ens4        # = runs/orch/spec_r4.json ens4_mix_fm2_analog_prov
dev_skill 0.2133 (first half 0.2217, second 0.2115), 4,278 cells; labels: autopsy2 labelling, ported, 100% identical
cause                cells  LV share  loss/LV  residual
none                  2211     0.000        -     0.037
dynamic_reprice       1027     0.205    0.573     0.149
announced_oneoff        52     0.127    0.843     0.136
unannounced_oneoff     195     0.098    0.823     0.103
entry                  236     0.279    0.843     0.298
exit                   125     0.087    0.951     0.106
marketplace_ask        124     0.136    0.635     0.110
hyperscaler_spot       308     0.068    0.706     0.061
total                 4278     1.000    0.787     1.000
memory: 8 records autopsy-loop-ens4-<cause> -> gpuf-failures as `autopsy`, status completed
```

The skill equals the orchestrator's number for this blend (0.2133). The labels are identical to
`runs/autopsy2/cells_labelled.parquet` on all 4,278 cells, and `--system mix` reproduces autopsy2's S1 column
(loss/LV 0.628, 0.854, 0.856, 0.907, 0.965, 0.714, 0.698; total 0.831). Offers entering the panel are still the largest
residual (30%). Exits are the cause the blend handles worst (0.95 of last-value loss).

## 2. Scout as of 2026-10-06, 1 US dollar cap

```
$ python -m gpuf.loop scout --as-of 2026-10-06 --max-usd 1
failure cases recalled as `scout` (date-bounded, written by `autopsy`): 43
case-provider pairs: 3 with a calendar entry within 3 days, 77 without -> 18 providers searched
searches 108 (the calendar agent's own per-provider requests, windows clipped at the as-of date)
  cache hits 72 (identical requests from experiments/calendar), new 36; contents fetches 10 (new)
  new spend $0.234 (36 x $0.007, 4 billed $0; 10 x $0.001)
dropped unopened: tracker 136; not a price change by that provider 550; kept 165 (106 with effective-date language)
rejected 102: no passage with effective date + change verb + old->new price 80, passage names no panel provider 7,
  already in calendar 8, evergreen pricing guide 4, text carries a date after 2026-10-06 3
NEW calendar entry (1): nebius, effective 2026-06-01, published 2026-08-22, confidence C (reported after the change)
  "Nebius raised on-demand GPU rental prices by roughly 30% from June 1, with H100 pricing moving from $2.95 to $3.85
   per GPU-hour and B200 pricing from $5.50 to $7.15" (startupfortune.com, 2026-08-22)
memory: 15 sources -> gpuf-evidence as `scout`, each timed at its publication date
```

New in this run: the Nebius June repricing. It is a real dated change, but it was reported 82 days after it took effect
and falls before the dev period. Its confidence is C, so neither the prov `cal` switch nor the autopsy labels use it,
and the loss table is unchanged. Everything else was already in the calendar or failed the calendar's rules. The 36
new searches were the October window (1 to 6 October), which the calendar agent had only searched up to 6 November
and which this run may not see past its as-of date. A second run cost $0.00 (108 of 108 searches and 10 of 10 contents
were cache hits) and added no calendar line. Evidence writes are capped at 15 per run, so the second run wrote the next
15 kept sources and repeated no id.

## 3. Prior check before spending compute

```
$ python -m gpuf.loop prior --claim "when an offer leaves a small panel the posted median steps to the neighbouring
  offer and does not revert, so the lower and upper tails should sit on the one-offer-out medians"
memory (as `proposer`), experiments only:
  rank 2  H28 supported        overlap 0.20  Tails shaped by the panel's one-offer-out and one-offer-in medians ...
  rank 3  H11 supported        overlap 0.13  Every median jump is a repriced offer near the middle of the panel or a membership change
  rank 5  H12 not_significant  overlap 0.14  Simulating the offer panel and recomputing the median beats scaling ...
Exa: 2 searches ($0.014), end published date 2026-11-06: type auto + category "publication" (papers), type auto + trackers excluded (posts)
  10 results dropped (no published date). Top sources by overlap with the claim:
  2017-11-30  Sequential Posted-Price Mechanisms with Correlated Valuations  https://doi.org/10.1145/3157085
              "We study the revenue performance of sequential posted-price mechanisms ..."            overlap 0.03
  2009-01-01  Essays on dynamic sales mechanisms  http://hdl.handle.net/1721.1/49715                   overlap 0.02
  2015-05-29  Polemic's Pains: Benchmarking on the outliers  https://polemics-pains.blogspot.com/...  overlap 0.01
recommendation: already tested here and supported (H28): build on it, do not re-run it
```

The literature search found nothing close. The best overlap was 0.03, and the results are about posted-price mechanism
design, not order statistics of offer panels. The claim is known here (H28, and H4 refuted reversion), not in the
literature the search returned.

## 4. Propose

```
$ python -m gpuf.loop propose          # latest autopsy (ens4) + memory briefing as `proposer` (3 recalls)
rank cause               residual loss/LV  state
1    entry               0.298    0.843    open (supported: H11, H28, H31; refuted/ns: H4, H30)
2    dynamic_reprice     0.149    0.573    open (supported: H2, H24, H31, H32; refuted/ns: H7b, H25)
3    announced_oneoff    0.136    0.843    open (supported: H27, H34; refuted/ns: H10, H13, H33, H35)
4    marketplace_ask     0.110    0.635    open (supported: H6, H18)
5    exit                0.106    0.951    open (supported: H11, H28, H31; refuted/ns: H4, H30)
6    unannounced_oneoff  0.103    0.823    open (supported: H28, H31; refuted/ns: H7, H30, H33)
7    hyperscaler_spot    0.061    0.706    reopened: its only targeted hypothesis (H35) is refuted, but 18 evidence items
                                           naming aws/azure/gcp/oci arrived after it (e.g. scout-57682c53 "AWS EC2 Capacity
                                           Blocks Price Hike: Up 20% in 2026")
8    none (width cost)   0.037    -        open (supported: H2, H23, H34; refuted/ns: H25)
registered but untested: none for any cause. Leads (autopsy2's "visible at origin"), e.g. entry: a provider listing the
same GPU on the other collector lifts the chance of an entry 2.2x; exit: size known (one-offer-out median), timing not.
```

## 5. Gate on an existing candidate (reproduction check)

```
$ python -m gpuf.loop gate --name L3-frag-b20 --candidate '["fragility",{"mode":"mix","boost":20,"bkind":"any"}]'
fragility 0.1924 vs mix 0.1691: d +0.0232 [+0.011, +0.045], DM one-sided p 0.0003
first half +0.0485 [+0.013, +0.094], second half +0.0179 [+0.001, +0.038]; coverage 0.77, h7 above q90 0.21
status by Amendment 2 rule 1: supported -> ledger L3-frag-b20; memory sync as `experimenter`: 4 changed entries sent
```

This reproduces the orchestrator's halves.py result for H28 exactly (research-log 12:31: +0.0232 [+0.011, +0.045],
halves +0.049 and +0.018).

## 6. Forecast for a dev origin (no scoring)

```
$ python -m gpuf.loop forecast --origin 2026-10-06 --method ens4 --out runs/loop/forecast_ens4_2026-10-06.csv
111 rows, 37 series, 0 filled, scored: false
calendar usable at 2026-10-06, local file: aws 10-07, fireworks 09-01, jarvislabs 10-05, nebius 10-01, salad 09-12
calendar via memory (as `forecaster`, as-of 2026-10-06): the same five + digitalocean 08-01
difference: digitalocean is in memory but has confidence C, which calendar_lib excludes; agree = false (reported, by design)
usable entries effective after the origin: aws 2026-10-07 (capacity blocks, not in any panel)
```

## 7. Status

```
$ python -m gpuf.loop status
ledger 37 hypotheses: supported 14, refuted 14, not_significant 7, untestable 2
validation: 42 harness queries logged; gate queries q6 to q11
calendar 9 entries (1 added by the loop)
memory 164 data points: gpuf-failures 77 (autopsy), gpuf-evidence 48 (scout), gpuf-experiments 39 (experimenter 37, researcher 2)
Exa spend: attribution $1.564, calendar $2.827, day scout $2.982, loop $0.248 (this iteration), total $7.621
```

## What the loop did not do by itself

It did not write a hypothesis. `propose` points at entry (30% of residual loss), where every registered idea has been
tested. Turning the entry lead (the other-collector footprint) into a new forecaster, and declaring a validation query
for it, is still a job for a research agent or a human.
