# Can we do Track 2? Yes.

Saturday 14 November, early afternoon. This is for the team's choice between Track 2 and Track 5.

## The short answer

We have a working GPU price forecaster. It beats the organisers' baseline on weeks of data it was never built on, it rebuilds from one command in 25 seconds, and the file we would submit already exists. The research is done. What is left is writing it up and presenting it.

## How good is it?

The score says how much better we are than simply assuming every price stays where it is. Zero means no better. Higher is better.

| Tested on | Us | Organisers' baseline |
|---|---|---|
| Three held-back weeks, the 37 series that get scored | 0.214 | 0.084 |
| Three held-back weeks, every other series (the first time we checked these on those weeks; we did use them on the practice dates) | 0.228 | 0.102 |
| The practice dates we built on, the 37 scored series | 0.208 | 0.089 |

We also give a price range for each forecast. On the held-back weeks, 80% of real prices landed inside it. The target is 80%.

## The idea

A published GPU price is not really one price. It is the middle of a short list of offers from different providers. It moves when a provider near the middle changes its price, or when a provider joins or leaves the list. We found this by looking at where our own forecasts went wrong. Then we forecast the list instead of the price, and that is what worked.

## What else we have

- **A full record.** 37 ideas tried: 13 worked, 15 did not, 7 made no clear difference, 2 could not be tested. Every check on held-back data was written down before we ran it, with one early exception listed below.
- **Exa.** We used it to build a calendar of announced price changes. All 17 announced prices we could check showed up in the data exactly as announced.
- **past.dev.** It is live. Three agents write to it and others read from it.
- **The business angle and the 2 to 3 year outlook.** Both are written and I have read them. An outside adviser found a few errors and overstatements in them, which are being corrected now.
- **A clean rebuild.** A fresh copy of the repo in a fresh Python environment reproduces both forecast files exactly, in under a minute.

## What could go wrong

- **Sunday is a single date.** On 50 practice dates we beat the baseline on 46 and did worse than "no change" on 2. Those dates overlap, so this is weaker than it sounds. One bad week is possible.
- **Two of our four new methods are on shakier ground.** An outside check found that my test on the held-back weeks was too easy to pass. Under a stricter test, the provider simulation and the short-memory Chronos model still clearly hold. The other two might be luck: about a 1 in 15 chance for one and 1 in 7 for the other. We kept them because they helped throughout the practice dates.
- **The ranges I quoted for the held-back weeks are rough.** That period is only three weeks long, which is too little to put firm error bars on.
- **We picked the 37 series with hindsight.** They are the ones that qualify on 6 November. Most did not qualify until October. On the ones that did qualify earlier, our lead over the baseline is smaller. So the numbers above flatter us somewhat.
- **We have not shown an edge on series with a long history, and on Sunday every series has one.** On the practice dates, almost all of our lead over the baseline (0.117 of 0.119) came from series that were too new to qualify. On the ones that already qualified we scored 0.154, the baseline 0.138, and our own simplest model 0.171. That evidence is thin (mostly four series, plus one collector in one week), and the held-back weeks, where a third of the series had a long history, still went well. An adviser reviewed it and we are leaving the forecast unchanged, but we should not promise a big margin on Sunday.
- **We found and fixed one small leak.** One method could be nudged by data from after the forecast date. The effect was at most 0.002% on a price, and it cannot affect Sunday. Every other method passed a test where we deleted or scrambled all later data.
- **One early check was logged in the wrong order.** It was committed 32 seconds after its result, not before, and its score was missing from the log. Both are now corrected.
- **The 2 to 3 year outlook gives ranges, not proven forecasts.** Nothing beat "assume no change" when tested on the past. It says so.
- **A good score alone will not win.** The brief says so. Judges have to read the method and the findings.

## What is left for a Track 2 entry

- README, findings and the demo page are written. They need the results of the work now running folded in.
- Running now: a version of the system that proposes and tests its own ideas with no human in between; a price index a lender could compute; a source-to-forecast trail for Exa; corrections to the 2 to 3 year outlook.
- From the team: make the repo public and push it, register on the platform by Sunday noon, record a 2-minute video.

## Track 2 or Track 5: what the hackathon page says

- **Track 5 is "build whatever you want".** Same rules and same judging. No set question and no sponsor.
- **Only Track 2 has its own prize:** $5K in compute, on top of the overall top 3. Track 5 has none.
- **The top 2 of each track go to the finals.** The page does not say whether that includes Track 5.
- **The submission form only lists Tracks 1 to 4.** Ask the organisers on Discord how Track 5 is submitted before picking it.
- **Exa, past.dev and Modal prizes are open to both.**
- **Not shown anywhere:** how many teams picked each track.
- **One catch for past.dev.** The submission form asks you to prove the memory makes things more accurate, faster and cheaper. The resources page says you do not have to. We have not measured what the memory adds.

## Track 2 or Track 5: the two prototypes side by side

I have read the Track 5 blog post (tinkerings.dev/posts/weight-edits). I have not read its code or run it, so the right-hand column is what the post says.

**What Track 5 is.** A language model reads the weights of a small model (Qwen3.5-0.8B), finds the few values that make it loop on "Wait..." in maths answers, and overwrites them. No training. The best edit, found by Claude Opus, takes the small model from 7.6% to 34.8% correct on a 500-problem maths test. A published edit from a paper this month gets 28.9%.

The hackathon scores five things, 20% each:

| | Track 2 (GPU prices) | Track 5 (weight edits) |
|---|---|---|
| Research rigour | Strong. Leak tests, an outside audit, every held-back check written down first, corrections logged. | Decent. Separate train, check and test problems; the test is run once. But each result is one run, and the post says results vary a lot between runs. |
| Novelty | The idea that a posted price is the middle of a short list of offers, and forecasting that list. New to us; the organisers already warn that medians depend on who is in the list. | Builds on a method published this month. The new parts are the map of edit types and a first try at training the editor by reward. |
| Results and live demo | A real margin over the baseline on past dates, with honest caveats. Sunday's official score is one date and could go either way. The demo is an offline page. | The more striking number: 7.6% to 34.8%, past the published 28.9%. That gap is about 30 problems out of 500 from single runs, so it is suggestive, not settled. The step-through of each edit is a good demo. |
| Autonomy and self-improvement | Our weak spot today: agents wrote every idea under direction. The fix is being built now. | Its natural strength: the editor model diagnoses, edits and checks by itself. The reward-training step is only a first test (4 runs, 2 scored zero). |
| Easy to follow and reproduce | Strong. One command rebuilds the forecasts; every number is traced to a file. | The post explains the method clearly and links every run. I could not check reproducibility. |

**Prizes and logistics**

- **Track 2 has three ways to win something:** its own prize (top 3 among Track 2 teams only), Exa, and past.dev, plus the overall top 3. All three are already wired in.
- **Track 5 has one sure way:** the overall top 3. The post shows no Exa or past.dev use, so those prizes would need extra work. There is no Track 5 prize, and the submission form still has no Track 5 option.
- **One rule to check for Track 5:** "No prior commits to the repo." Make sure its repo started during the event.

**My read.** Track 5 has the better single headline and fits the autonomy criterion without effort. Track 2 has more ways to place, a submission path that certainly exists, and is further along as a complete entry. If the aim is any prize, Track 2 is the safer choice. If the aim is the overall top 3 and nothing else, Track 5's result may land better in a 3-minute pitch, provided it holds up when re-run and the organisers confirm how Track 5 is submitted and judged.

**Two things that would settle it**

1. Ask the organisers on Discord: how is Track 5 submitted, and do its top 2 go to the finals?
2. Re-run the best weight edit two or three times. If it stays near 35% and stays ahead of the published edit, the Track 5 headline is solid.

## What this does not tell you

The Track 5 column above comes from one blog post, not from its code or a re-run. The number of teams in each track is still unknown.

The detailed version of everything here, with sources, is in `research-log.md`, `experiments/audit/results/audit.md` and `experiments/submission/track_choice.md`.
