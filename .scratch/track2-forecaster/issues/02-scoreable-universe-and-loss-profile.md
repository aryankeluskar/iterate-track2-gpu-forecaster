# Scoreable universe and loss profile

Type: research
Status: resolved
Blocked by: 

## Question

Which series can Sunday's scorer actually cover, where does the baseline loss concentrate, and what statistical structure (steps, mean reversion, revisions, provider-mix shifts) do those series have?

## Answer

Sunday scores 37 series: the headline tier of posted rental series as of 2026-11-06 (20 fastgpu from 8 Sep, 13 gpurentalprices from 4 Aug, 4 afhubbard spot). They change on about a third of days. Loss concentrates in the B300 and B200 rate cards and one marketplace H100 series. Full findings in `findings.md`; scripts and CSVs in `experiments/00-eda/`.
