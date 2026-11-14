# Pitch: 3 minutes, walking demo/index.html top to bottom

Open `demo/index.html` from disk before you start (no server, no network). Every number below is on the page and comes from a file in the repo. If files change, rebuild with `PYTHONPATH=src .venv/bin/python -m gpuf.demo` and read the numbers off the page, not from this script.

## Script (about 420 words, under 3 minutes)

**[Result, 0:00 to 0:30]**
"Pacific asked what GPUs will rent for. The prices everyone quotes are posted prices. We built an AI scientist that forecasts them one, three and seven days ahead and improves by studying its own mistakes. The clean result first: on 555 price series we never used for any decision, it scores 0.228, against 0.102 for the organisers' baseline. Zero means no better than assuming prices stay put. On the 37 series scored on Sunday it scores 0.214 against 0.084, but that one flatters us, because we kept some parts of the mix for doing well on those same weeks. 80% of real prices landed inside our low-to-high range, which is the target."

**[What to keep in mind, 0:30 to 0:55]**
"Two caveats matter most. First, Sunday scores a single date. On 50 practice dates we beat the baseline on 46, but those dates overlap, so one bad week is possible. Second, of the four new models we added, an independent audit says only two clearly hold on the held-back weeks. The other two stay in only because they helped on the practice dates. The rest is listed here: a tiny leak that was found and fixed, and series that were picked with hindsight."

**[Offer explorer, 0:55 to 1:45]** *(B300 preset is loaded)*
"Here's what the system found. A posted price is the middle of a short list of provider offers, here ten. Orange means a provider that changes its price most days. Blue means it rarely does. Watch Verda." *Drag the slider from late September to about 18 October.* "Verda climbs every day. The price follows it only while Verda is in the middle. Once Verda passes Together at 9.99, the price stops there. The dashed lines show where the price jumps if one offer leaves or joins. So we stopped forecasting the line and started simulating the list." *Click the A100 40GB preset.* "Here Lambda holds five of the seven offers, so Lambda is the index."

**[How it improved, 1:45 to 2:10]**
"Each bar splits our error by what happened to the list. The provider simulator took out the orange part. In the table, each new model got one look at the held-back weeks, written down before it ran. The planned test and the stricter test sit side by side, so you can see which two hold."

**[Ideas tested and Exa, 2:10 to 2:35]**
"We tested 37 ideas. 13 worked, 15 didn't and 7 made no clear difference, and all of them are listed. Exa found dated price announcements, each linked with its quote. 17 of 17 offers we could check moved to exactly the announced price. But only 2 of the 37 largest price changes were announced beforehand."

**[Memory, long run, reproduce, 2:35 to 3:00]**
"Four agents write to shared memory in past.dev and four read from it. The forecaster only sees what was known on its forecast date. Over two to three years we give ranges, H100 from 3.49 now to about 2.3 at 24 months, and nothing beat 'no change' on the backtests. One command rebuilds the forecasts, and the file hashes are on the page."

## Video shot list (2 minutes)

| # | time | shot | on screen | voice |
|---|---|---|---|---|
| 1 | 0:00–0:12 | Page top, still | result sentence; the three number cards, clean number first | 0.228 against 0.102 on series never used; 0.214 on the scored 37 is optimistic |
| 2 | 0:12–0:24 | Scroll to "What to keep in mind" | first and third bullets highlighted | one scored date; two of four new models clearly hold |
| 3 | 0:24–0:55 | Offer explorer, B300 preset, slow slider drag from ~25 Sep to 18 Oct | Verda's orange diamond passing Together; the middle line stopping at 9.99 | "the price follows Verda until it passes its neighbour, then stops" |
| 4 | 0:55–1:03 | Slider back to 6 Nov; the three forecast rows and the side panel | low, middle and high estimates at 1, 3, 7 days; "2.5% if one offer leaves" | forecast and how solid this price is |
| 5 | 1:03–1:10 | A100 40GB preset | five Lambda offers at 1.99; "if one provider leaves 36%" | "one provider is the index" |
| 6 | 1:10–1:25 | Error-by-cause bars, then the held-back-weeks table | orange part shrinking; "Logged p" and "Stricter p" columns | "planned test and stricter test side by side" |
| 7 | 1:25–1:33 | Ideas tested, click "did not work" | the 15 failed ideas | "failures stay on the record" |
| 8 | 1:33–1:45 | Exa timeline and table; hover a source link (do not click) | Nebius and Jarvislabs rows; the "17 of 17" line; "What did not work" | "every claim traces to a dated source" |
| 9 | 1:45–1:53 | Shared-memory tables and recall 1 | writers by folder; "none is later than the bound" | "agents share memory; the forecaster's view stops at its date" |
| 10 | 1:53–2:00 | Long-run figure, then the reproduce command and hashes | rent paths; `bash reproduce.sh final` | "ranges, not a proven forecast; one command rebuilds it" |
