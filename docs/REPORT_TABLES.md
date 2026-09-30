# Report tables

The tables and figure data of the paper, computed from `logs/` by
`harness/results_tables/report_tables.py` and rendered by `harness/report_tables_gen.py`
(`--check` diffs a regeneration against this file). Each table carries the caption of the
paper and the label it has there. The exhaustive document is `docs/RESULTS_ALL.md`.

## Runs behind every held-out cell

| block | model | control | rocq-mcp | rocq-mcp-evolve | reps |
|---|---|---|---|---|---|
| miniF2F test | Haiku | `FINAL_pf_baseline_haiku` | `FINAL_pf_rocqmcp_haiku` | `FINAL_pf_session2_haiku` | 2 |
| miniF2F test | Sonnet | `FINAL_pf_baseline_sonnet` | `FINAL_pf_rocqmcp_sonnet` | `FINAL_pf_session2_sonnet` | 2 |
| miniF2F test | Opus | `FINAL_pf_baseline_opus_r245` rep 0 + `FINAL_pf_baseline_opus` rep 1 | `FINAL_pf_rocqmcp_opus` | `FINAL_pf_session2_opus` | 2 |
| miniF2F test | Terra | `orp_base_test` | `orp_sib_test` | `orp_evolve_test` | 2 |
| projects | Sonnet | `af3_base` | `af3_sota` | `af3_evolve` | 4 |
| projects | Opus | `op_base` | `op_sota` | `op_evolve` | 2 |
| projects | Terra | `orp3_base` | `orp3_sota` | `orp3_evolve` | 4 |

## `tab:evolution_deltas`

**Detailed results** of the evolution process. Each line corresponds to a mutation of
`tab:evolution_chronology`. Each cell reports the change with respect to the previous version
as a diff: the number of new successes (+) and failures (−). For each dataset we report the
number of problems in each difficulty bucket, and the number of runs per problem.

| mutation | dataset | slots | easy | medium | hard | total |
|---|---|---|---|---|---|---|
| step, rollback, state | dev60 | 120 | +4−3 | +4−1 | +4−1 | +12−5 |
| try | dev60 | 120 | +7−0 | +4−2 | +2−0 | +13−2 |
| compact rendering | dev60 | 120 | +1−2 | +1−2 | +0−1 | +2−5 |
| search | dev60 | 120 | +0−2 | +2−3 | +2−1 | +4−6 |
| Lean-ism hints | dev60 | 120 | +0−2 | +6−2 | +1−1 | +7−5 |
| auto_close | dev60 | 120 | +2−0 | +5−2 | +3−1 | +10−3 |
| near-miss hints | dev60 | 120 | +2−0 | +4−2 | +1−1 | +7−3 |
| preload | miniF2F valid | 488 | +66−2 | +29−3 | +4−0 | +99−5 |
| team of three | hard70 | 140 | — | — | +0−11 | +0−11 |
| false-winner fix | dev60 | 120 | +0−2 | +1−7 | +2−1 | +3−10 |
| real arithmetic help | dev60 | 120 | +1−1 | +7−2 | +2−1 | +10−4 |
| check, Haiku | dev60 | 120 | +1−1 | +2−5 | +1−2 | +4−8 |
| check, Sonnet | dev60 | 120 | +1−0 | +7−0 | +8−2 | +16−2 |
| ssreflect hints | mathcomp35 | 35 | — | — | — | +5−4 |
| exemplar retrieval | mathcomp35 | 35 | — | — | — | +1−3 |
| hole visibility | autoform | 20 | — | — | — | +2−1 |
| finisher open | autoform | 20 | — | — | — | +1−0 |
| compact rendering (2nd) | autoform | 20 | — | — | — | +1−1 |

## `tab:detailed_results`

Results on the `test` split of miniF2F. The results on the whole dataset are followed by the
results per difficulty bucket: total (easy/medium/hard). For each model, the cost and wall
time are only computed on attempts on the subset of problems solved by all three MCP servers
in at least one run (results on the entire dataset are reported in `tab:detailed_results_full`).
The size of this subset per difficulty bucket is given next to the model name.

| model (e/m/h) | server | accuracy: total (e/m/h) | cost $: total (e/m/h) | wall s: total (e/m/h) |
|---|---|---|---|---|
| Haiku (40/4/1) | control | .17 (.28/.05/.01) | .07 (.06/.07/.15) | 52 (50/60/86) |
| Haiku (40/4/1) | rocq-mcp | .33 (.54/.11/.07) | .05 (.05/.05/.06) | 32 (32/30/48) |
| Haiku (40/4/1) | rocq-mcp-evolve | **.48** (**.69**/**.30**/**.14**) | **.04** (**.04**/**.03**/**.05**) | **19** (**19**/**16**/**36**) |
| Sonnet (90/28/7) | control | .50 (.68/.35/.17) | .24 (.19/.36/.39) | 96 (76/153/153) |
| Sonnet (90/28/7) | rocq-mcp | .72 (.88/.53/.56) | .16 (.12/.28/.23) | 44 (30/86/**64**) |
| Sonnet (90/28/7) | rocq-mcp-evolve | **.80** (**.91**/**.68**/**.67**) | **.11** (**.08**/**.18**/**.22**) | **35** (**23**/**62**/77) |
| Opus (83/24/5) | control | .43 (.60/.28/.13) | .28 (.21/.47/.68) | 93 (67/163/206) |
| Opus (83/24/5) | rocq-mcp | .72 (.88/.56/.46) | .19 (.14/.34/.35) | 42 (28/83/81) |
| Opus (83/24/5) | rocq-mcp-evolve | **.76** (**.90**/**.61**/**.54**) | **.12** (**.08**/**.22**/**.24**) | **33** (**20**/**73**/**67**) |
| Terra (99/33/12) | control | .54 (.70/.40/.27) | .06 (.04/.08/.10) | 84 (70/107/135) |
| Terra (99/33/12) | rocq-mcp | .80 (.92/.66/.63) | .03 (.02/.05/.05) | 42 (29/74/63) |
| Terra (99/33/12) | rocq-mcp-evolve | **.88** (**.97**/**.80**/**.71**) | **.02** (**.01**/**.03**/**.04**) | **34** (**23**/**58**/**60**) |

## `tab:efficiency_results`

Efficiency results for the different MCP servers, averaged over the four models.

| model | server | calls | input tokens | output tokens | output tokens per call |
|---|---|---|---|---|---|
| Haiku | control | 6.4 | 129.1k | 5.0k | 0.78k |
| Haiku | rocq-mcp | 9.0 | 216.4k | 2.6k | 0.29k |
| Haiku | rocq-mcp-evolve | **5.6** | **84.1k** | **1.3k** | **0.23k** |
| Sonnet | control | **3.3** | **73.5k** | 8.6k | 2.59k |
| Sonnet | rocq-mcp | 5.9 | 174.3k | 3.0k | 0.52k |
| Sonnet | rocq-mcp-evolve | 4.6 | 80.3k | **2.2k** | **0.47k** |
| Opus | control | **1.6** | **19.6k** | 7.0k | 4.49k |
| Opus | rocq-mcp | 5.2 | 112.5k | 2.8k | 0.53k |
| Opus | rocq-mcp-evolve | 3.8 | 32.9k | **1.9k** | **0.51k** |
| Terra | control | 12.5 | 93.8k | 5.8k | 0.46k |
| Terra | rocq-mcp | 8.7 | 90.5k | 2.3k | 0.27k |
| Terra | rocq-mcp-evolve | **8.4** | **42.3k** | **1.2k** | **0.14k** |
| all models | control | 5.9 | 79.0k | 6.6k | 2.08k |
| all models | rocq-mcp | 7.2 | 148.4k | 2.7k | 0.40k |
| all models | rocq-mcp-evolve | **5.6** | **59.9k** | **1.6k** | **0.34k** |

## Paired tests at the problem level

For each problem, the number of runs solved under each server; a problem counts as better
(worse) for rocq-mcp-evolve when it solved strictly more (fewer) of its runs than the other
server. Exact two-sided sign test on the better:worse split; one unit per problem.

| comparison | problems | rocq-mcp-evolve vs control | rocq-mcp-evolve vs rocq-mcp |
|---|---|---|---|
| dev60, final Phase-1 server vs control (4 runs) | 60 | 22:0 (p = 4.8e-7) | — |
| miniF2F test, Haiku (2 runs) | 244 | 91:1 (p = 3.8e-26) | 55:2 (p = 2.3e-14) |
| miniF2F test, Sonnet (2 runs) | 244 | 95:4 (p = 1.2e-23) | 37:5 (p = 4.4e-7) |
| miniF2F test, Opus (2 runs) | 244 | 95:1 (p = 2.4e-27) | 26:8 (p = 2.9e-3) |
| miniF2F test, Terra (2 runs) | 244 | 104:2 (p = 1.4e-28) | 35:6 (p = 4.9e-6) |

## Auto-closable problems (RQ3)

The tool `auto_close` alone solves 52/244 problems of the `test` split of miniF2F, i.e.,
21 % (.35/.06/.03 per bucket).
On this subset of problems: solved attempts over both runs, cost and wall time per solve for
each server, and the averages over all models.

| model | server | solved attempts | cost $ | wall s |
|---|---|---|---|---|
| Haiku | control | 62/104 | .05 | 35 |
| Haiku | rocq-mcp | 95/104 | .04 | 24 |
| Haiku | rocq-mcp-evolve | 104/104 | **.03** | **16** |
| Sonnet | control | 96/104 | .11 | 39 |
| Sonnet | rocq-mcp | 104/104 | .09 | 20 |
| Sonnet | rocq-mcp-evolve | 104/104 | **.05** | **9** |
| Opus | control | 94/104 | .13 | 36 |
| Opus | rocq-mcp | 104/104 | .11 | 20 |
| Opus | rocq-mcp-evolve | 104/104 | **.06** | **12** |
| Terra | control | 99/104 | .03 | 46 |
| Terra | rocq-mcp | 104/104 | .01 | 13 |
| Terra | rocq-mcp-evolve | 104/104 | **.00** | **5** |
| all models | control | — | .08 | 39 |
| all models | rocq-mcp | — | .06 | 19 |
| all models | rocq-mcp-evolve | — | **.03** | **11** |

## `tab:autoform_results`

Results on project-scale tasks for the models Sonnet | Opus | Terra averaged on all tasks
(detailed results are reported in `tab:autoform_results_full`).

| model | server | solved | accuracy | cost $ | wall s |
|---|---|---|---|---|---|
| Sonnet | control | 10/20 | .50 | 1.56 | 608 |
| Sonnet | rocq-mcp | 12/20 | .60 | 2.63 | 595 |
| Sonnet | rocq-mcp-evolve | **14/20** | **.70** | **1.44** | **429** |
| Opus | control | 3/10 | .30 | 2.19 | 714 |
| Opus | rocq-mcp | 6/10 | .60 | 2.48 | 661 |
| Opus | rocq-mcp-evolve | 6/10 | .60 | **1.89** | **574** |
| Terra | control | 8/20 | .40 | 0.22 | 332 |
| Terra | rocq-mcp | 7/20 | .35 | 0.34 | 502 |
| Terra | rocq-mcp-evolve | **10/20** | **.50** | **0.16** | **269** |

## `tab:detailed_results_full`

Results on the `test` split of miniF2F with cost and wall time computed on the whole dataset
instead of the problems solved with all three MCP servers.

| model | server | accuracy: total (e/m/h) | cost $: total (e/m/h) | wall s: total (e/m/h) |
|---|---|---|---|---|
| Haiku | control | .17 (.28/.05/.01) | **.07** (**.07**/**.07**/**.15**) | 54 (53/**60**/**86**) |
| Haiku | rocq-mcp | .33 (.54/.11/.07) | .10 (.09/.12/.17) | 54 (51/66/96) |
| Haiku | rocq-mcp-evolve | **.48** (**.69**/**.30**/**.14**) | .13 (.10/.24/.23) | 67 (51/116/136) |
| Sonnet | control | .50 (.68/.35/.17) | .25 (.20/.38/.39) | 100 (77/161/153) |
| Sonnet | rocq-mcp | .72 (.88/.53/.56) | .25 (.17/.36/.46) | 73 (47/**114**/142) |
| Sonnet | rocq-mcp-evolve | **.80** (**.91**/**.68**/**.67**) | **.21** (**.13**/**.33**/**.37**) | **72** (**41**/115/**127**) |
| Opus | control | .43 (.60/.28/.13) | .29 (.21/.49/.68) | 95 (67/169/206) |
| Opus | rocq-mcp | .72 (.88/.56/.46) | .34 (.24/.48/.61) | 83 (57/121/**163**) |
| Opus | rocq-mcp-evolve | **.76** (**.90**/**.61**/**.54**) | **.25** (**.16**/**.36**/**.55**) | **79** (**49**/**116**/165) |
| Terra | control | .54 (.70/.40/.27) | .06 (.04/.08/.10) | 85 (71/111/135) |
| Terra | rocq-mcp | .80 (.92/.66/.63) | .05 (.03/.08/.08) | 66 (44/102/101) |
| Terra | rocq-mcp-evolve | **.88** (**.97**/**.80**/**.71**) | **.04** (**.02**/**.06**/**.06**) | **62** (**41**/**93**/**93**) |

## `tab:detailed_results_runs`

Results on the `test` split of miniF2F for each of the two runs (same conventions as
`tab:detailed_results`: cost and wall time on the problems solved by all three MCP servers).

| model | server | run | accuracy: total (e/m/h) | cost $: total (e/m/h) | wall s: total (e/m/h) |
|---|---|---|---|---|---|
| Haiku | control | 1 | .17 (.28/.05/.03) | .06 (.06/.07/.15) | 51 (49/64/86) |
| Haiku | control | 2 | .17 (.29/.05/.00) | .07 (.07/.08/—) | 52 (52/56/—) |
| Haiku | rocq-mcp | 1 | .34 (.55/.10/.09) | .05 (.05/.04/.05) | 32 (32/33/40) |
| Haiku | rocq-mcp | 2 | .33 (.53/.11/.06) | .06 (.06/.05/.07) | 33 (32/28/56) |
| Haiku | rocq-mcp-evolve | 1 | .48 (.69/.28/.14) | .03 (.03/.03/.04) | 19 (19/17/28) |
| Haiku | rocq-mcp-evolve | 2 | .49 (.68/.32/.14) | .04 (.04/.03/.06) | 20 (19/15/43) |
| Sonnet | control | 1 | .50 (.67/.34/.20) | .24 (.18/.36/.44) | 94 (71/150/169) |
| Sonnet | control | 2 | .50 (.69/.35/.14) | .24 (.20/.37/.33) | 99 (80/156/131) |
| Sonnet | rocq-mcp | 1 | .73 (.88/.54/.63) | .16 (.12/.28/.27) | 44 (30/83/78) |
| Sonnet | rocq-mcp | 2 | .70 (.88/.51/.49) | .16 (.12/.28/.19) | 45 (31/89/50) |
| Sonnet | rocq-mcp-evolve | 1 | .82 (.92/.71/.69) | .11 (.08/.20/.23) | 36 (22/70/81) |
| Sonnet | rocq-mcp-evolve | 2 | .79 (.90/.66/.66) | .11 (.08/.17/.20) | 33 (24/53/73) |
| Opus | control | 1 | .44 (.62/.29/.11) | .30 (.24/.49/.62) | 98 (74/168/186) |
| Opus | control | 2 | .43 (.59/.28/.14) | .26 (.18/.46/.73) | 88 (60/159/222) |
| Opus | rocq-mcp | 1 | .73 (.89/.54/.51) | .19 (.14/.35/.36) | 44 (29/85/89) |
| Opus | rocq-mcp | 2 | .71 (.88/.57/.40) | .19 (.14/.34/.34) | 40 (27/80/73) |
| Opus | rocq-mcp-evolve | 1 | .75 (.89/.61/.51) | .12 (.08/.24/.19) | 34 (23/70/51) |
| Opus | rocq-mcp-evolve | 2 | .77 (.92/.61/.57) | .11 (.07/.21/.29) | 32 (17/76/79) |
| Terra | control | 1 | .56 (.72/.42/.29) | .06 (.04/.08/.10) | 84 (68/114/133) |
| Terra | control | 2 | .53 (.69/.38/.26) | .05 (.05/.07/.10) | 84 (73/99/137) |
| Terra | rocq-mcp | 1 | .82 (.95/.67/.66) | .03 (.02/.05/.05) | 43 (32/68/67) |
| Terra | rocq-mcp | 2 | .77 (.90/.65/.60) | .03 (.02/.06/.05) | 40 (25/80/59) |
| Terra | rocq-mcp-evolve | 1 | .88 (.97/.81/.71) | .02 (.01/.03/.04) | 38 (26/62/71) |
| Terra | rocq-mcp-evolve | 2 | .88 (.97/.80/.71) | .02 (.01/.03/.03) | 30 (21/53/49) |

## `tab:autoform_results_sd`

Results on project-scale tasks with the standard deviation of the accuracy across runs
(accuracy per run = solved tasks / 5) and of the cost and wall time over the solved runs.

| model | server | runs | accuracy per run | accuracy ± sd | cost $ ± sd | wall s ± sd |
|---|---|---|---|---|---|---|
| Sonnet | control | 4 | .60/.40/.60/.40 | .50 ± .12 | 1.56 ± 0.25 | 608 ± 74 |
| Sonnet | rocq-mcp | 4 | .60/.60/.60/.60 | .60 ± .00 | 2.63 ± 1.05 | 595 ± 181 |
| Sonnet | rocq-mcp-evolve | 4 | .60/.80/.80/.60 | .70 ± .12 | 1.44 ± 0.84 | 429 ± 202 |
| Opus | control | 2 | .20/.40 | .30 ± .14 | 2.19 ± 0.12 | 714 ± 65 |
| Opus | rocq-mcp | 2 | .60/.60 | .60 ± .00 | 2.48 ± 0.27 | 661 ± 142 |
| Opus | rocq-mcp-evolve | 2 | .60/.60 | .60 ± .00 | 1.89 ± 0.74 | 574 ± 209 |
| Terra | control | 4 | .40/.40/.40/.40 | .40 ± .00 | 0.22 ± 0.12 | 332 ± 166 |
| Terra | rocq-mcp | 4 | .40/.40/.40/.20 | .35 ± .10 | 0.34 ± 0.19 | 502 ± 245 |
| Terra | rocq-mcp-evolve | 4 | .60/.40/.40/.60 | .50 ± .12 | 0.16 ± 0.11 | 269 ± 137 |

## `tab:autoform_results_full`

Results on the five project-scale tasks (4 runs per task, 2 for Opus). Four Terra solutions
that passed the gate by hardcoding the probe inputs are not counted.

| model | server | frugal | gauges | ledger | prodauto | triadic |
|---|---|---|---|---|---|---|
| Sonnet | control | 4/4 | 3/4 | 3/4 | 0/4 | 0/4 |
| Sonnet | rocq-mcp | 4/4 | 4/4 | 4/4 | 0/4 | 0/4 |
| Sonnet | rocq-mcp-evolve | 4/4 | 4/4 | 3/4 | 3/4 | 0/4 |
| Opus | control | 0/2 | 1/2 | 2/2 | 0/2 | 0/2 |
| Opus | rocq-mcp | 2/2 | 2/2 | 2/2 | 0/2 | 0/2 |
| Opus | rocq-mcp-evolve | 2/2 | 2/2 | 2/2 | 0/2 | 0/2 |
| Terra | control | 4/4 | 0/4 | 4/4 | 0/4 | 0/4 |
| Terra | rocq-mcp | 3/4 | 2/4 | 2/4 | 0/4 | 0/4 |
| Terra | rocq-mcp-evolve | 4/4 | 2/4 | 4/4 | 0/4 | 0/4 |

## `fig:phase1_evolution`

Evolution of accuracy, cost, and wall time across the mutations of Phase 1 and Phase 2. The
mutations are numbered chronologically (except number 14, which represents the server
obtained after Phase 1).

| index | mutation | dataset | verdict | solved/attempts | accuracy % | cost $ (solved) | wall s (solved) |
|---|---|---|---|---|---|---|---|
| 0 | control | dev60 | kept | 79/240 | 33 | 0.04 | 41 |
| 1 | session | dev60 | kept | 45/120 | 38 | 0.02 | 17 |
| 2 | try | dev60 | kept | 56/120 | 47 | 0.03 | 20 |
| 3 | compact rendering | dev60 | reverted | 53/120 | 44 | 0.02 | 19 |
| 4 | search | dev60 | reverted | 54/120 | 45 | 0.02 | 19 |
| 5 | Lean-ism hints | dev60 | kept | 58/120 | 48 | 0.02 | 19 |
| 6 | auto_close | dev60 | kept | 65/120 | 54 | 0.03 | 22 |
| 7 | did-you-mean | dev60 | kept | 132/240 | 55 | 0.03 | 22 |
| 7 | did-you-mean (miniF2F valid, before preloading) | minif2f_valid | kept | 105/488 | 22 | 0.02 | 22 |
| 8 | preloading | minif2f_valid | kept | 199/488 | 41 | 0.03 | 22 |
| 8 | did-you-mean (hard70, solo) | hard70 | kept | 56/140 | 40 | 0.02 | 16 |
| 9 | team of three | hard70 | reverted | 45/140 | 32 | 0.03 | 23 |
| 10 | hint synthesis | dev60 | kept | 68/120 | 57 | 0.03 | 22 |
| 11 | check | dev60 | kept | 130/240 | 54 | 0.03 | 29 |
| 11 | check (mathcomp35) | mathcomp35 | kept | 11/35 | 31 | 0.04 | 25 |
| 12 | ssreflect hints | mathcomp35 | reverted | 12/35 | 34 | 0.05 | 41 |
| 13 | exemplar retrieval | mathcomp35 | reverted | 9/35 | 26 | 0.04 | 29 |
| 14 | shipped server | autoform | kept | 14/20 | 70 | 1.44 | 429 |
| 15 | hole visibility | autoform | reverted | 15/20 | 75 | 1.68 | 514 |
| 16 | finisher in open | autoform | reverted | 15/20 | 75 | 1.40 | 453 |
| 17 | compact rendering (2nd) | autoform | reverted | 14/20 | 70 | 1.85 | 510 |

## `fig:intro_results`

Results on the `test` split of miniF2F-Rocq. Each model is evaluated with three MCP servers:
control, a minimal server wrapping the Rocq compiler, rocq-mcp, an established MCP server for
Rocq, and rocq-mcp-evolve. For a fair comparison, cost and wall time are averaged over the
theorems proved with all three servers.

| series | values (Haiku, Sonnet, Opus, Terra; each control / rocq-mcp / rocq-mcp-evolve) |
|---|---|
| accuracy % | `{17, 33, 48},{50, 72, 80},{43, 72, 76},{54, 80, 88}` |
| cost $ | `{0.07, 0.05, 0.04},{0.24, 0.16, 0.11},{0.28, 0.19, 0.12},{0.06, 0.03, 0.02}` |
| wall s | `{52, 32, 19},{96, 44, 35},{93, 42, 33},{84, 42, 34}` |
