# Submission requirements (Iterate AI Research Hackathon, SF, 14-15 Nov 2026)

Sources
- **PAGE** = https://iterate.inc/ai-research?welcome=true&tab=resources (read in Brave on 14 Nov 2026 in a new tab; logged-in view). Section names below are the page's headings.
- **PAGE/judges** = same page, `tab=judges` (JUDGES & MENTORS; only names/roles).
- **T2BRIEF** = `track_2/description.md` (local copy of Pacific's Track 2 brief).
- **EXA** = `../exa.md`, **PAST** = `../past_dev.md` (local copies; wording matches PAGE "Sponsor Challenges").
- **PASTDOCS** = https://past.dev/docs/memory-api/overview (fetched, public).
- Not read: the Drive briefs (sign-in wall). PAGE tabs PICTURES, PROJECTS, TEAMS, HOME not read (not requirement-bearing; the Resources tab already contains Information, Schedule, Tracks, Challenges, Judging, Prizes, Rules). Judges tab only shows a first page of judges ("Load More" not clicked).

All times are PT (PAGE, Schedule: "All times PT").

## (a) Hackathon overall

| Item | Finding |
| --- | --- |
| Deadline | PAGE Judging > "What to submit (by Sunday 14:30)". PAGE Schedule says "02:00 PM Hacking ends, submissions due" (Sunday 15 Nov). **CONFLICT: 14:00 vs 14:30. Treat 14:00 PT as the hard deadline.** Time zone PT (PAGE, Schedule: "All times PT"). |
| Platform deadline | PAGE Schedule: "08:00 PM Reminder: your team must be on the platform by Sunday 12:00"; "12:00 AM Lunch, team list closes on the platform" (Sunday, the page's "12:00 AM" is almost certainly 12:00 noon). Team must exist on the iterate.inc Teams panel: "Go to the 'Teams' panel on the platform, create your team and have your teammates join it." |
| Where/how | PAGE "What to submit": "1 track, plus any challenges you enter"; "The link to your GitHub repo"; "A 2-minute demo video (YouTube, Drive or Loom)"; "A short description of your project". The exact submission form/URL is **NOT FOUND** on the page (presumably the platform Projects tab; confirm on Discord https://discord.gg/Jjh7XdWeF, "All news about the event will be posted there!"). |
| Track choice | PAGE Tracks: "Each team picks one track." |
| Judging criteria | PAGE Judging: "5 criteria, equal weight (20% each)": Research rigour ("clear question, sound experiment design, baselines or ablations, claims backed by results"); Novelty ("a new idea, method or use case, beyond existing papers and open-source baselines"); Results ("a measurable result on a real problem or benchmark, ideally against a baseline; a working live demo"); Autonomy & self-improvement ("how much of the research loop runs without a human; extra credit if it gets better from its own results"); Interpretability & reproducibility ("decisions can be followed (logs, traces, sources), code runs, failures reported honestly"). |
| Schedule | PAGE Schedule, Sunday: "01:30 PM Judging schedule posted on Discord: your room and your time"; "02:00 PM Hacking ends, submissions due"; "02:45 PM Round 1: every team pitches in its room"; "04:45 PM Finals on stage"; "06:00 PM Prizes & closing ceremony, followed by drinks". Saturday: 09:00 doors, 09:30 kickoff, 10:00 hacking begins, 12:30 lunch & sponsor office hours, 19:00 dinner, then overnight hacking. Venue: "Wefunder, 1885 Mission St, San Francisco". |
| Demo format | PAGE Judging > How it works: "Round 1 (5 min per team, 6 rooms): pitch (3:00) + Q&A (2:00). The top 2 of each track go to the finals." "Finals at 16:30 (3 min per team, on stage): pitch + live demo, no Q&A. Then the challenge winners demo (2 min)." "The final panel picks the top 3. All winners are announced at 18:00." **CONFLICT: Schedule says Finals 04:45 PM, How-it-works says 16:30.** Be ready by 16:30. |
| Judges | PAGE/judges: names/roles listed (e.g. Simran Singh, Researcher @ MSL; Jamie Pinheiro, Jane Street; Mehdi Djabri, past.dev; Zakee Abdi, Cognition; Long Do, OpenAI; Michelangelo Valtancoli; Soroush Zare; Chen Yang, Scale AI; Ajay Prakash, LinkedIn; ...; Lazare Masset). No mapping of judges to rooms/tracks: **NOT FOUND** (room and time are to be posted on Discord at 13:30 Sunday). |
| Rules / disqualifiers | PAGE Rules (verbatim): "Build entirely during the event. No prior commits to the repo."; "Teams of 3 to 5."; "Open-source libraries, APIs and pre-trained models are allowed if properly credited."; "Submit all code and demos before the deadline to be eligible."; "Follow the law, ethical AI practices and the Code of Conduct. Never use data without consent."; "Use partner and sponsor APIs according to their terms of service."; "All team members must be physically present at the venue. Remote participation is not permitted."; "Organizers may disqualify any team for rule violations or unfair play." Track 5 text: "Same rules: built during the hackathon, public repo, demo, same judging criteria." |
| Repo public? Licence? AI-tool disclosure? | Public: PAGE only says "public repo" in the Track 5 blurb (applies to "same rules"), so make it public. Licence requirement: **NOT FOUND**. AI-tool disclosure requirement: **NOT FOUND** (only "properly credited" for libraries/APIs/models; the Originator challenge uses AI agent session logs). |
| Prizes (overall) | PAGE Prizes: "Top 3 overall (all tracks combined) 1st: $5K OpenAI credits + $5K Tinker credits + cash prize + Boardy Pro; 2nd: $2.5K OpenAI credits + cash prize + Boardy Pro; 3rd: $1K OpenAI credits + cash prize + Boardy Pro". "Tracks & challenges (stack on top of the top 3)". "Best photo on X: $500 cash". Cash amounts: **NOT FOUND**. |

## (b) Track 2 (Pacific)

| Item | Finding |
| --- | --- |
| Deadline | Same as (a) for repo/video/description (14:00-14:30 PT Sun). Forecast truth is "frozen at the end of Friday 13 November (UTC) with its SHA-256 hash published" (T2BRIEF s5), scored "on Sunday 15 November". |
| What to submit | T2BRIEF s7: "Submit code and a demo, plus concise findings." (1) "Forecasts in the starter kit's format with `origin_date` 2026-11-06 and horizons 1, 3 and 7, for the posted rental series you choose." (2) "One command that reproduces them from the pack and any cited public data dated on or before 6 November." (3) "Findings: the question, method, evaluation, results with uncertainty, what your system learned across iterations and, if you address it, your argued view on resale and rentals in 2-3 years." PAGE Track 2 "Submit": "forecasts in the starter kit format, one command that reproduces them, and concise findings (question, method, evaluation, results with uncertainty, what your system learned across iterations)." |
| Forecast file format | T2BRIEF s4: one CSV, one row per (`series_id`, `origin_date`, `horizon_days`); columns `series_id`, `origin_date`, `horizon_days` (1, 3, 7 or 30), `q10`, `q50`, `q90` ("`q10` > 0 and `q10` <= `q50` <= `q90`"), optional `target_date`, `team_id`, `method_note`. Series ids from `series_catalog.csv`. |
| Scoring | T2BRIEF s5: origin 6 Nov 2026, horizons 1, 3, 7 (targets 7, 9, 13 Nov). "pinball loss at quantiles 0.1, 0.5 and 0.9, averaged over each (series, origin, horizon) cell; skill is 1 - loss / last-value loss." Report: pooled skill (headline), mean/median/geo-mean skill, coverage (target 0.8). "Cells you leave out are filled with the last-value baseline, which scores zero skill." Frozen mode "refuses, with `REFUSED` and exit code 2, any forecast whose origin is not the cutoff and any history file holding a row dated after it." Invalid rows dropped. Horizon 30 and AWS spot are "Not scored on Sunday." |
| Judging criteria | T2BRIEF s8 (no weights given: **NOT FOUND**): Rigour, Useful economic insight, Reproducibility, Originality. PAGE: "Judged on: rigour, useful economic insight, reproducibility and originality." Leaderboard alone does not win (T2BRIEF s5: "Leaderboard position alone will not win. Well-supported negative results count as much as positive ones"). The overall PAGE 5x20% criteria also apply to the whole event. |
| Direction | T2BRIEF s6: "Choose one direction" (A self-improving forecasts, B market signals with memory, C own approach). |
| Data rules | T2BRIEF s3: "External data must be public, free to every team and dated before each forecast origin." "do not add them back (`DATA.md`, section 9)" for excluded sources. Pass the pack on unchanged. Cite with wording in `ATTRIBUTION.md` (CC BY 4.0). Cite news by date, title and link; follow sites' terms on automated access. |
| Resale / 2-3 yr | T2BRIEF s5: "cannot be scored by Sunday. Argue them from public evidence ... the judges assess the argument. State your assumptions and give ranges." |
| Prize | T2BRIEF s8 / PAGE: "$5,000 worth of Pacific compute hours: first $3,000, second $1,500, third $500." Stacks on the overall top 3 (PAGE). |
| Judges/schedule specific to Track 2 | Pacific-specific judge: **NOT FOUND**. Demo: same Round 1 / Finals format as (a); "top 2 of each track go to the finals". |

## (c) Exa challenge

| Item | Finding |
| --- | --- |
| Deadline | Same as (a): "Optional and open to every track: enter as many as you like, on top of your track." (PAGE Sponsor Challenges). Any challenge-specific deadline: **NOT FOUND**. |
| Requirements | EXA/PAGE: "At least one Exa API call (search, contents, find similar, answer, research or Websets) runs in your project's main loop, not only in a side feature." "Submit a repo link and point to where Exa is called." "Show your sources: the demo makes clear what the system found through Exa and how it used it." EXA also: "Built during the hack. Open to all four tracks." (PAGE says open to Track 5 as well for sponsor challenges). |
| How to submit | Flag Exa among "challenges you enter" in the main submission; put the file/line of the Exa call in the README/description. Separate form: **NOT FOUND**. |
| Judging | "Exa is central 30% (The project would break, or get clearly worse, without search); Research value 25%; Creativity 25%; Checkable output 20% (Results trace back to real sources, and it works in a live demo)". |
| Judging schedule | EXA: "Exa judges review every entry on Sunday afternoon. Winners are announced at the closing ceremony at 18:00." Plus PAGE: "Then the challenge winners demo (2 min)" after Finals. |
| Prizes | "1st $5K Exa credits per team; Exa hoodie, Exa-branded TRMNL running the Exa plugin, Exa goat (per member); 2nd $3K, hoodie, goat; 3rd $1K, goat. Prize credits are issued to the winning teams' Exa dashboard accounts." (so each member needs an Exa dashboard account/team's account). |
| Credits | PAGE API Keys & Credits: Exa $50 via dashboard.exa.ai with the code shown on the page (not repeated here). |
| Disqualifiers | None specific. General: "Use partner and sponsor APIs according to their terms of service." |

## (d) past.dev challenge

| Item | Finding |
| --- | --- |
| Deadline | Same as (a). Challenge-specific deadline: **NOT FOUND**. |
| Requirements | PAGE/PAST: "More than one agent writes to the memory layer." "More than one agent reads from it." "At least one agent reads data written by a different agent and uses it in its tasks." "You can combine past.dev with other memory techniques (markdown, RAG): say in your README which one holds what. You don't have to prove the memory improves your results: if it didn't, explain why in your README." |
| README duties | State which memory holds what; if no improvement, explain why. |
| How to submit | Repo link + enter as a challenge in the main submission. Separate form: **NOT FOUND**. Full brief (Drive 1uM3EgLx...) is behind Google sign-in: **NOT FOUND**. |
| Judging | "Judge: Mehdi Djabri (CEO, past.dev). Mentor on site: Lazare Masset." Criteria/weights: **NOT FOUND**. Demo slot: probably challenge winners' 2-min demo (PAGE) - past.dev-specific demo format **NOT FOUND**. |
| Prize | "a Bambu Lab P1S 3D printer for each team member + $1K in past.dev credits." |
| API notes | PASTDOCS (last-updated 2026-11-13): `POST /api/v1/ingest` (1 data point), `/ingest/batch` (up to 1,000), `GET /api/v1/ingest/{ingestionId}` for completion, `POST /api/v1/recall` ("names a reader and a question"; returns ranked documents for one identity), audiences/identities/traits for access control. Multi-agent = separate identities writing/reading in one project. Credits: PAGE "past.dev (500,000 credits per team)": sign up at past.dev, choose 500,000 credits in the console, enter the code on the page (only works with 500,000 selected), create an API key; ask Lazare. |

## (e) Other prizes our project could plausibly enter

| Prize | Finding |
| --- | --- |
| Best use of Modal | PAGE: "The best use of Modal for training, inference, or running large numbers of experiments and agent sandboxes in parallel. Open to any team using Modal." Prize "$5,000 in Modal credits." Needs: real Modal usage (e.g. run the experiment sweeps / forecasting backtests / agent sandboxes as Modal functions in parallel) and say so in README/demo. Entry mechanism, criteria, judge: **NOT FOUND**. Credits: Modal $250 claimable via the fillout link on the PAGE. |
| Most frontier agentic work by Originator | PAGE: "Hack directly on hackwithori.com (pwd on page) with 24/7h cloud based agents (codex, claude code..) or upload your sessions when done to participate to the challenge. An agent will review your work & pre-score it for the judges." Prize "$1,000 in cash for #1st, $500 for #2nd, $500 for #3rd. Not a finalist? The winner still demos on stage (2 min)." Needs: upload our agent session logs to hackwithori.com (cost: the upload; deadline **NOT FOUND**, assume before 14:00). Low effort if the sessions are exportable. |
| Best photo on X | PAGE: "$500 cash". Rules **NOT FOUND**. |
| Overall top 3 | Automatic if judged into the final (see (a)). |
| Tinker / Cognition / OpenAI | Credits only on PAGE (Tinker $100, Devin $200, OpenAI credits link); no prize challenge found. |

## Surprising / easy to miss
1. Deadline conflict: submissions due 14:00 (Schedule) vs 14:30 ("What to submit"). Use 14:00.
2. Team must be on the platform by Sunday 12:00 (noon); team list closes at lunch. Teams of 3-5 only.
3. "No prior commits to the repo" and "Build entirely during the event": the submission repo must have its first commit on or after Sat 14 Nov (our local track_2 repo has pre-existing material such as a 6 Nov data pack and earlier experiments; make sure whatever repo is submitted respects this).
4. All team members must be physically at the venue.
5. Demo video is 2 minutes; Round 1 pitch is 3:00 + 2:00 Q&A; finals 3:00 live demo with no Q&A.
6. Track 2 scoring truth freezes Fri 13 Nov UTC; only 1/3/7-day horizons at origin 2026-11-06 count. Forecast CSV must have exactly origin_date 2026-11-06; frozen scorer refuses anything else.
7. Exa prizes go to a dashboard account; past.dev brief and Modal/Originator entry mechanics are not public on the page.
8. Finals time differs inside the page (16:30 vs 16:45).

## Artefact checklist (deadline: Sun 15 Nov 14:00 PT unless noted; assume 14:00 not 14:30)

- [ ] Team created on iterate.inc platform with 3-5 members, all joined. Deadline Sun 12:00 PT (PAGE Schedule).
- [ ] Public GitHub repo, first commit on/after 14 Nov, credits for open-source libs/APIs/models. 14:00 PT. (Licence file: not required by page; add one anyway if cheap.)
- [ ] Track selection: Track 2 (+ challenges Exa, past.dev, plus any Modal/Originator entries) recorded in the submission. 14:00 PT.
- [ ] Short project description (platform/Projects submission). 14:00 PT.
- [ ] 2-minute demo video (YouTube, Drive or Loom link). 14:00 PT.
- [ ] Track 2: forecast CSV in starter-kit format, origin_date 2026-11-06, horizons 1, 3, 7, for chosen posted rental series. 14:00 PT (truth frozen Fri 13 Nov UTC; scored Sun).
- [ ] Track 2: single command that reproduces forecasts from the pack + cited public data dated <= 6 Nov. 14:00 PT.
- [ ] Track 2: concise findings doc (question, method, evaluation, results with uncertainty, iteration learnings, optional 2-3 year resale/rental argument with assumptions and ranges). 14:00 PT.
- [ ] Track 2: data attribution per `ATTRIBUTION.md` (CC BY 4.0); news cited by date, title, link. 14:00 PT.
- [ ] Exa: README/description pointing to where Exa is called in the main loop; demo shows sources found through Exa. 14:00 PT.
- [ ] past.dev: README stating which memory layer holds what; more than one agent writes, more than one reads, at least one reads another agent's data; explanation if no improvement. 14:00 PT.
- [ ] Modal (optional): Modal usage in code + README note. 14:00 PT.
- [ ] Originator (optional): upload agent sessions to hackwithori.com. Deadline unknown; assume 14:00 PT.
- [ ] Be reachable for Discord judging schedule post (13:30 PT); Round 1 pitch from 14:45 PT (3:00 + 2:00 Q&A), Finals 16:30 PT (3:00, live demo), closing 18:00 PT.
