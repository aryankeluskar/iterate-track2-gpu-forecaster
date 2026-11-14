# Pitch: 3 minutes, walking demo/index.html top to bottom

Open `demo/index.html` from the file system before you start (no server and no network needed). Every number below is on the page and comes from a file in the repo. If a file changes, rebuild with `PYTHONPATH=src .venv/bin/python -m gpuf.demo` and re-read the numbers from the page, not from this script.

## Script (about 400 words)

**[Headline, 0:00 to 0:30]**
"Pacific asked what GPUs will rent for. The numbers everyone quotes are posted medians. We built an AI scientist that forecasts them one, three and seven days ahead and learns from its own failures. On 18 validation days it had never been tuned on, it scored a skill of 0.214. The organisers' drift baseline scored 0.084. On 555 series nobody had looked at, it scored 0.228 against 0.102. Its 80% intervals contained 80% of outcomes."

**[Panel explorer, 0:30 to 1:20]** *(B300 preset is loaded by default)*
"Here is why. A posted median is not a market price. It is the middle of a small panel, here ten offers. Orange means a provider that reprices most days. Blue means static. Watch Verda." *Drag the slider from late September to mid-October.* "Verda climbs every day. The median follows only while Verda holds the middle. Once it passes Together, here at 9.99, the median stops. The dashed lines show where the median jumps if one offer leaves or joins. The system found this by taking apart its own worst misses. Then it stopped forecasting the line and started simulating the panel. On the right: this index moves 2.5% if one offer leaves." *Click the A100 40GB preset.* "Here Lambda holds five of seven offers. Lambda is the index."

**[How it improved, 1:20 to 1:50]**
"Each bar splits forecast loss by what physically happened. The provider simulator went after the orange segment, frequent repricers. Fragility tails went after offers entering and leaving. We declared each validation query before running it. Four directions passed a false-discovery test. What remains is mostly new offers entering, which nobody announces."

**[Ledger, 1:50 to 2:05]**
"We tested 38 hypotheses. 15 were refuted and 7 were not significant, and they stay on the page next to the 14 that held."

**[Exa, 2:05 to 2:25]**
"Search is how we explain the jumps. Exa found dated repricing announcements. Every source is linked with its date and the quoted sentence. 17 of 17 checkable offers moved to exactly the announced price. The negative result: only 2 of the 37 largest repricings were announced ahead."

**[Shared memory, 2:25 to 2:40]**
"Four agents write to past.dev and four read from it. The forecaster's recall is limited to what was known on its forecast date. Here it asks as of 6 October, and nothing later comes back."

**[Two to three years and reproduce, 2:40 to 3:00]**
"For the long view: H100 static rate cards go from 3.49 today to about 2.3 at 24 months, with the range and the assumptions shown, and the backtests that failed are stated. One command rebuilds the forecasts. The hashes are on the page."

## Video shot list (2 minutes)

| # | time | shot | on screen | voice |
|---|---|---|---|---|
| 1 | 0:00–0:12 | Page top, still | question, result sentence, three number cards | question and the two skill numbers |
| 2 | 0:12–0:45 | Explorer, B300 preset, slow slider drag from ~25 Sep to 18 Oct | Verda's orange diamond passing Together; median line stopping at 9.99; lower chart cursor moving | "the median follows Verda until it passes its neighbour, then stops" |
| 3 | 0:45–0:55 | Slider back to 6 Nov; zoom on the three forecast rows and the facts panel | q10, q50, q90 at 1, 3, 7 days; "2.5% if one offer leaves" | forecast and index fragility |
| 4 | 0:55–1:05 | A100 40GB preset | five Lambda offers at 1.99; facts "if one provider leaves 36%" | "one provider is the index" |
| 5 | 1:05–1:20 | Loss-by-cause bars, then the validation table | orange segment shrinking across systems; rows 6 to 11 | "each change aimed at a cause found by failure analysis; declared before it ran" |
| 6 | 1:20–1:30 | Ledger, click "refuted" filter | refuted list with results | "refuted results stay visible" |
| 7 | 1:30–1:45 | Exa timeline and table; hover a source link (do not click) | Nebius and Jarvislabs rows with dates and quotes; "17 of 17" line | "every claim traces to a dated source" |
| 8 | 1:45–1:53 | Shared-memory matrix and recall 1 | writers by audience; "nothing later than the bound" | "agents share memory, date-bounded for the forecaster" |
| 9 | 1:53–2:00 | Long-run figure, then the reproduce command and hashes | rent paths; `bash reproduce.sh final` | "one command rebuilds it" |
