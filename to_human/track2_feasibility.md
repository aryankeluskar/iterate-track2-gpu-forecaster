# Can we do Track 2? Yes.

Saturday 14 November, early afternoon. This is for the team's choice between Track 2 and Track 5.

## The short answer

We have a working GPU price forecaster. It beats the organisers' baseline on weeks of data it was never built on, it rebuilds from one command in 25 seconds, and the file we would submit already exists. The research is done. What is left is writing it up and presenting it.

## How good is it?

The score says how much better we are than simply assuming every price stays where it is. Zero means no better. Higher is better.

| Tested on | Us | Organisers' baseline |
|---|---|---|
| Three held-back weeks, the 37 series that get scored | 0.214 | 0.084 |
| Three held-back weeks, every other series (we never tuned anything on these) | 0.228 | 0.102 |
| The practice dates we built on, the 37 scored series | 0.208 | 0.089 |

We also give a price range for each forecast. On the held-back weeks, 80% of real prices landed inside it. The target is 80%.

## The idea

A published GPU price is not really one price. It is the middle of a short list of offers from different providers. It moves when a provider near the middle changes its price, or when a provider joins or leaves the list. We found this by looking at where our own forecasts went wrong. Then we forecast the list instead of the price, and that is what worked.

## What else we have

- **A full record.** 37 ideas tried: 13 worked, 15 did not, 7 made no clear difference, 2 could not be tested. Every check on held-back data was written down before we ran it, with one early exception listed below.
- **Exa.** We used it to build a calendar of announced price changes. All 17 announced prices we could check showed up in the data exactly as announced.
- **past.dev.** It is live. Three agents write to it and others read from it.
- **The business angle and the 2 to 3 year outlook.** Both are written. I have not read either one line by line yet.

## What could go wrong

- **Sunday is a single date.** On 50 practice dates we beat the baseline on 46 and did worse than "no change" on 2. Those dates overlap, so this is weaker than it sounds. One bad week is possible.
- **Two of our four new methods are on shakier ground.** An outside check found that my test on the held-back weeks was too easy to pass. Under a stricter test, the provider simulation and the short-memory Chronos model still clearly hold. The other two might be luck: about a 1 in 15 chance for one and 1 in 7 for the other. We kept them because they helped throughout the practice dates.
- **The ranges I quoted for the held-back weeks are rough.** That period is only three weeks long, which is too little to put firm error bars on.
- **We picked the 37 series with hindsight.** They are the ones that qualify on 6 November. Most did not qualify until October. On the ones that did qualify earlier, our lead over the baseline is smaller. So the numbers above flatter us somewhat.
- **We found and fixed one small leak.** One method could be nudged by data from after the forecast date. The effect was at most 0.002% on a price, and it cannot affect Sunday. Every other method passed a test where we deleted or scrambled all later data.
- **One early check was logged in the wrong order.** It was committed 32 seconds after its result, not before, and its score was missing from the log. Both are now corrected.
- **The 2 to 3 year outlook gives ranges, not proven forecasts.** Nothing beat "assume no change" when tested on the past. It says so.
- **A good score alone will not win.** The brief says so. Judges have to read the method and the findings.

## What is left for a Track 2 entry

- README and findings (being written now).
- Demo page and a 3-minute pitch (being built now).
- From the team: make the repo public and push it, register on the platform by Sunday noon, record a 2-minute video.

## Track 2 or Track 5: what the hackathon page says

- **Track 5 is "build whatever you want".** Same rules and same judging. No set question and no sponsor.
- **Only Track 2 has its own prize:** $5K in compute, on top of the overall top 3. Track 5 has none.
- **The top 2 of each track go to the finals.** The page does not say whether that includes Track 5.
- **The submission form only lists Tracks 1 to 4.** Ask the organisers on Discord how Track 5 is submitted before picking it.
- **Exa, past.dev and Modal prizes are open to both.**
- **Not shown anywhere:** how many teams picked each track.
- **One catch for past.dev.** The submission form asks you to prove the memory makes things more accurate, faster and cheaper. The resources page says you do not have to. We have not measured what the memory adds.

## What this does not tell you

It does not compare the two prototypes. I have not seen the Track 5 one.

The detailed version of everything here, with sources, is in `research-log.md`, `experiments/audit/results/audit.md` and `experiments/submission/track_choice.md`.
