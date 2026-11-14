### Q1: proposer

Question: "Which hypotheses on failure modes of the median have been refuted, and what was the evidence?"

Expected: returns the 4 experiment records. **PASS**. 20 results in 1.31 s; offline replay identical: True.

| first rank | source id | kind of first hit | occurred | label | author |
|---|---|---|---|---|---|
| 1 | `exp-H7` | source | 2026-11-14T19:49:16Z | Experiment: H7 | experimenter |
| 2 | `exp-H7b` | source | 2026-11-14T19:49:16Z | Experiment: H7b | experimenter |
| 4 | `exp-H9` | source | 2026-11-14T19:49:16Z | Experiment: H9 | experimenter |
| 7 | `exp-H10` | source | 2026-11-14T19:49:16Z | Experiment: H10 | experimenter |
| 10 | `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-10-06` | source | 2026-10-06T23:59:59Z | Autopsy: gpurentalprices.marketplace_ask.H100_80GB.spot.median | autopsy |
| 11 | `autopsy-fastgpu_daily.neocloud_rate_card.B300.on_demand.median-2026-10-06` | claim | 2026-10-06T23:59:59Z | Autopsy: fastgpu_daily.neocloud_rate_card.B300.on_demand.median | autopsy |
| 12 | `autopsy-all-2026-10-04` | source | 2026-10-04T23:59:59Z | Autopsy: all series, busiest day | autopsy |
| 19 | `scout-12d5cf4c` | source | 2026-09-02T23:59:59Z | Evidence: linkedin.com | scout |
| 20 | `autopsy-gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand.median-2026-10-03` | claim | 2026-10-03T23:59:59Z | Autopsy: gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand.median | autopsy |

### Q2: proposer

Question: "What is the largest unexplained source of last-value loss?"

Expected: returns autopsy records 1, 2, 3. **PASS**. 20 results in 0.81 s; offline replay identical: True.

| first rank | source id | kind of first hit | occurred | label | author |
|---|---|---|---|---|---|
| 1 | `autopsy-fastgpu_daily.neocloud_rate_card.B300.on_demand.median-2026-10-06` | claim | 2026-10-06T23:59:59Z | Autopsy: fastgpu_daily.neocloud_rate_card.B300.on_demand.median | autopsy |
| 2 | `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-10-06` | source | 2026-10-06T23:59:59Z | Autopsy: gpurentalprices.marketplace_ask.H100_80GB.spot.median | autopsy |
| 9 | `exp-H7` | mention | 2026-11-14T19:49:16Z | Experiment: H7 | experimenter |
| 12 | `autopsy-all-2026-10-04` | source | 2026-10-04T23:59:59Z | Autopsy: all series, busiest day | autopsy |
| 13 | `exp-H7b` | source | 2026-11-14T19:49:16Z | Experiment: H7b | experimenter |
| 15 | `exp-H9` | source | 2026-11-14T19:49:16Z | Experiment: H9 | experimenter |
| 20 | `exp-H10` | source | 2026-11-14T19:49:16Z | Experiment: H10 | experimenter |

### Q3: forecaster, as_of 2026-10-06

Question: "Which providers announced price increases before this date?"

Expected: returns salad, fireworks, linkedin; not the askgpu Nebius page (timed 10-18). **PASS**. 20 results in 0.94 s; offline replay identical: True.

| first rank | source id | kind of first hit | occurred | label | author |
|---|---|---|---|---|---|
| 1 | `autopsy-gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand.median-2026-10-03` | membership | 2026-10-03T23:59:59Z | Autopsy: gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand.median | autopsy |
| 3 | `scout-3d7d1259` | claim | 2026-09-01T23:29:16Z | Evidence: blog.salad.com | scout |
| 4 | `scout-c520a7d6` | source | 2026-09-01T10:35:30Z | Evidence: theweightedaverage.com | scout |
| 7 | `scout-12d5cf4c` | source | 2026-09-02T23:59:59Z | Evidence: linkedin.com | scout |

### Q4: forecaster, as_of 2026-10-31

Question: "Nebius H100 on-demand price change"

Expected: returns the askgpu Nebius page (record 5); autopsy record 4 listed if present. **PASS**. 20 results in 1.0 s; offline replay identical: True.

| first rank | source id | kind of first hit | occurred | label | author |
|---|---|---|---|---|---|
| 1 | `scout-f4c32699` | claim | 2026-10-18T23:59:59Z | Evidence: askgpu.com | scout |
| 5 | `autopsy-gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand.median-2026-10-03` | claim | 2026-10-03T23:59:59Z | Autopsy: gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand.median | autopsy |
| 7 | `scout-c520a7d6` | claim | 2026-09-01T10:35:30Z | Evidence: theweightedaverage.com | scout |
| 17 | `scout-3d7d1259` | claim | 2026-09-01T23:29:16Z | Evidence: blog.salad.com | scout |

### Q5: scout

Question: "Which dates and providers had big median moves that still lack a news explanation?"

Expected: returns autopsy records 3 and 4 and nothing from gpuf-experiments. **PASS**. 20 results in 0.97 s; offline replay identical: True.

| first rank | source id | kind of first hit | occurred | label | author |
|---|---|---|---|---|---|
| 1 | `autopsy-gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand.median-2026-10-03` | source | 2026-10-03T23:59:59Z | Autopsy: gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand.median | autopsy |
| 2 | `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-10-06` | source | 2026-10-06T23:59:59Z | Autopsy: gpurentalprices.marketplace_ask.H100_80GB.spot.median | autopsy |
| 3 | `autopsy-all-2026-10-04` | claim | 2026-10-04T23:59:59Z | Autopsy: all series, busiest day | autopsy |
| 17 | `autopsy-fastgpu_daily.neocloud_rate_card.B300.on_demand.median-2026-10-06` | claim | 2026-10-06T23:59:59Z | Autopsy: fastgpu_daily.neocloud_rate_card.B300.on_demand.median | autopsy |
| 20 | `scout-3d7d1259` | source | 2026-09-01T23:29:16Z | Evidence: blog.salad.com | scout |

### Q6: forecaster

Question: "What did the experiments conclude about breadth?"

Expected: returns nothing from gpuf-experiments (access check). **PASS**. 20 results in 1.47 s; offline replay identical: True.

| first rank | source id | kind of first hit | occurred | label | author |
|---|---|---|---|---|---|
| 1 | `autopsy-all-2026-10-04` | source | 2026-10-04T23:59:59Z | Autopsy: all series, busiest day | autopsy |
| 2 | `autopsy-fastgpu_daily.neocloud_rate_card.B300.on_demand.median-2026-10-06` | source | 2026-10-06T23:59:59Z | Autopsy: fastgpu_daily.neocloud_rate_card.B300.on_demand.median | autopsy |
| 4 | `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-10-06` | source | 2026-10-06T23:59:59Z | Autopsy: gpurentalprices.marketplace_ask.H100_80GB.spot.median | autopsy |
| 6 | `autopsy-gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand.median-2026-10-03` | membership | 2026-10-03T23:59:59Z | Autopsy: gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand.median | autopsy |
| 8 | `scout-12d5cf4c` | source | 2026-09-02T23:59:59Z | Evidence: linkedin.com | scout |
| 10 | `scout-f4c32699` | source | 2026-10-18T23:59:59Z | Evidence: askgpu.com | scout |
| 11 | `scout-3d7d1259` | source | 2026-09-01T23:29:16Z | Evidence: blog.salad.com | scout |
| 13 | `scout-c520a7d6` | source | 2026-09-01T10:35:30Z | Evidence: theweightedaverage.com | scout |
