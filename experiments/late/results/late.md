# Late-window check (EVAL_PROTOCOL.md Amendment 4)

Origins 31 October to 5 November 2026, which no split holds; h=1 (six origins) and h=3 (31 Oct to 3 Nov), the cells whose target is on or before 6 November. Declared and committed (7a8f2eb) before any forecast was made at these origins; reporting only, the submission did not change. Systems: `final` exactly as submitted, the reference `mix`, the starter `drift`. Source: `late.json`, `cells.csv` (`python experiments/late/run.py build && ... score`).

| universe | cells | drift | mix | final | final minus drift | coverage of [q10, q90] (final) | above q90 / below q10 (final) |
|---|---|---|---|---|---|---|---|
| 37 headline series | 357 | 0.0876 | 0.1286 | 0.1932 | +0.1055 | 0.815 | 0.081 / 0.104 |
| other posted rental series | 4,838 | 0.0683 | 0.1871 | 0.2207 | +0.1524 | 0.893 | 0.050 / 0.058 |

By origin, headline, final minus drift: +0.088, +0.049, +0.160, +0.130, -0.117 (4 Nov, h=1 only), +0.096. Final beats drift at 5 of 6 origins on headline and 6 of 6 on the other series; it is below mix at 2 of 6 headline origins (1 and 4 November).

Why it matters: every scored series has 54 or more rows here (the 20 fastgpu series 54 to 59, as on 6 November with 60), so this is the first check of the blend on histories as mature as Sunday's. The development-period maturity slice (0.154 against drift 0.138, 745 cells, mostly afhubbard) does not repeat: the margin over drift here (+0.106) is close to the validation margin (+0.130).

Limits: six overlapping origins and no h=7 cells; the targets (1 to 6 November) were also targets of validation cells, whose aggregate scores had been seen; five cells of one marketplace series and the B300 rate card carry 23% of final's headline loss; no interval or p-value is claimed.
