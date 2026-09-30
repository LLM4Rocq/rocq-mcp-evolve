# Evaluation results — all models, unified

Conventions (one set, applied to every cell, recomputed from the archived per-attempt logs):
buckets easy/medium/hard (dev60: 20/20/20; miniF2F test: 130/79/35).
Buckets: the workbook sets (dev60, dev150, hard70) use the translation's own labels —
terciles of the Lean statement's length and symbol count, a statement-shape proxy rather
than a measured difficulty (medium and hard barely separate in solve rate); the miniF2F
splits use competition tier, fixed before the first unlock (A9): mathd algebra and number
theory → easy, amc12 and the custom algebra/numbertheory/induction families → medium, aime,
imo and the shortlist → hard.
pass@1 = rep-0 solves;
pass@2 = either of the first two reps. $/solve = total cost of all attempts (failures included)
per solved attempt. out ktok (solved) = mean output tokens over solved attempts, in thousands
(the efficiency metric the brief asked to report; reasoning tokens included — the
ladder itself was decided on per-bucket solve rate, docs/DESIGN.md). wall = mean seconds over
solved attempts in the miniF2F and autoform tables; the dev60 table reports mean seconds per
attempt, failures included (its own convention, shared with the README headline table and the
campaign dashboard). killed = wall-budget kills (%).
Autoform: no buckets; solve = solved/attempts (grading-corrected), single $/solve and wall.
Bold = best arm per column position within a model group; ties and single-arm groups
unmarked. Only the current experiment per arm is shown (superseded arms, earlier
generations, and voided runs omitted).

## 1. Development ledger (every development run, recomputed from its logs)

These are the campaign's decision-time runs, recomputed here under the same campaign
convention section 2 uses (pass@1 = solved attempts / attempts, over all reps; pass@2 =
either of the first two reps; wall = mean seconds per attempt, failures included) — so a
decision-time figure quoted in the trail may differ from the cell below it by rounding, or
because reps were added to a run after the decision was made. pass@1 and pass@2 are shown
per bucket with a pooled column; cost ($/att) and wall are per attempt, failures included
(not per solve). The turn cap of each run is shown because the development arena itself
changed during the campaign: cap 30 for the ladder, cap 50 for the universal runs (the
cap-30 universal re-run is the one section 2 reports); the team runs had no per-attempt turn
cap. Cells are not bolded here — this is a record of every run, not a comparison between
arms.

| # | run | change | manifest | reps | cap | pass@1 e/m/h | pass@2 e/m/h | pooled @1 (@2) | $/att e/m/h | wall s/att e/m/h | out ktok (solved) e/m/h | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **ladder (haiku, dev60)** |  |  |  |  |  |  |  |  |  |  |  |  |
| 0 | baseline_dev60 | naive whole-file check | dev60 | 4 | 30 | .44/.25/.30 | .50/.30/.35 | .33 (.38) | 0.08/0.11/0.15 | 90/122/157 | 2.5/2.6/8.5 | control |
| 1 | session_dev60 | session: persistent in-process, sentence steps, rollback | dev60 | 2 | 30 | .47/.33/.33 | .55/.40/.35 | .38 (.43) | 0.05/0.06/0.06 | 51/47/49 | 0.9/0.8/0.8 | KEPT |
| 2 | session_try_dev60 | + try (k candidates per call, first success commits) | dev60 | 2 | 30 | .65/.38/.38 | .70/.45/.40 | .47 (.52) | 0.05/0.06/0.06 | 43/51/49 | 1.0/1.5/0.8 | KEPT |
| 3 | session_try_compact_dev60 | + compact rendering (hypothesis deltas) | dev60 | 2 | 30 | .62/.35/.35 | .70/.40/.35 | .44 (.48) | 0.05/0.06/0.06 | 50/52/54 | 1.0/1.1/0.7 | REVERTED |
| 4 | session_try_search_dev60 | + search tool (pull-based) | dev60 | 2 | 30 | .60/.35/.40 | .70/.40/.40 | .45 (.50) | 0.04/0.06/0.06 | 42/53/52 | 0.9/1.2/0.9 | REVERTED |
| 5 | session_try_hints_dev60 | + hints (Lean-ism → Rocq rewrites in errors) | dev60 | 2 | 30 | .60/.47/.38 | .65/.60/.40 | .48 (.55) | 0.05/0.06/0.07 | 50/45/53 | 1.1/1.3/0.9 | KEPT |
| 6 | session_try_hints_auto_dev60 | + auto_close (server-side finisher portfolio) | dev60 | 2 | 30 | .65/.55/.42 | .70/.60/.50 | .54 (.60) | 0.05/0.06/0.06 | 51/48/56 | 1.0/1.3/1.1 | KEPT |
| 7 | session_try_hints_auto_sugg_dev60 | + did-you-mean (near-miss names, push-based) | dev60 | 4 | 30 | .70/.53/.42 | .70/.65/.45 | .55 (.60) | 0.04/0.06/0.06 | 46/45/47 | 1.1/1.6/1.0 | KEPT (this is the frozen winner's tool set) |
| 8 | unified_dev60 | draft-first / repair-from-failure prompting | dev60 | 2 | 30 | .40/.17/.23 | .50/.30/.35 | .27 (.38) | 0.06/0.09/0.09 | 67/85/84 | 1.4/3.6/2.5 | REVERTED |
| 9a | winner_autofix_dev60 | auto_close requires real progress (bug fix) | dev60 | 2 | 30 | .65/.45/.45 | .65/.50/.50 | .52 (.55) | 0.04/0.06/0.06 | 44/46/48 | 0.9/1.3/1.4 | fix |
| 9b | winner_auto2_dev60 | + hint-term synthesis | dev60 | 2 | 30 | .65/.57/.47 | .70/.65/.55 | .56 (.63) | 0.05/0.05/0.06 | 49/42/48 | 1.1/1.5/1.3 | KEPT |
| 10 | universal_dev60 | universal (recommended configuration), cap 50 | dev60 | 4 | 50 | .66/.57/.46 | .70/.65/.50 | .56 (.62) | 0.07/0.09/0.10 | 59/71/87 | 1.3/2.5/1.8 | selected |
| 10c | universal_c30_dev60 | universal, re-run at cap 30 (A101 arena) | dev60 | 4 | 30 | .65/.50/.47 | .65/.55/.50 | .54 (.57) | 0.05/0.06/0.07 | 41/54/73 | 1.1/2.0/2.0 | selected |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
| **confirmation on other development data (haiku)** |  |  |  |  |  |  |  |  |  |  |  |  |
| 2c | session_try_dev150 | try configuration on dev150 (disjoint workbook problems) | dev150 | 2 | 30 | .45/.33/.35 | .50/.36/.36 | .38 (.41) | 0.05/0.07/0.06 | 45/55/50 | 0.7/1.2/0.7 | confirmation |
| 5v | session_try_hints_minif2f_valid | hints configuration on the miniF2F valid split, before environment v2 | minif2f_valid | 2 | 30 | .32/.13/.00 | .35/.16/.00 | .15 (.17) | 0.06/0.08/0.10 | 67/76/87 | 0.9/1.7/— | evidence for v2 |
| 5v2 | session_try_hints_v2_minif2f_valid | same, under environment v2 (preload Lia/Lra/Psatz, refuse mid-proof Require) | minif2f_valid | 2 | 30 | .57/.30/.06 | .62/.37/.06 | .31 (.35) | 0.05/0.07/0.09 | 53/64/75 | 1.1/1.6/1.1 | KEPT (v2) |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
| **team pattern (haiku)** |  |  |  |  |  |  |  |  |  |  |  |  |
| T1 | solo_hard70 | solo winner on hard70 (the hard problems of dev60 and dev150) | hard70 | 2 | 30 | —/—/.40 | —/—/.40 | .40 (.40) | —/—/0.06 | —/—/50 | —/—/1.0 | reference |
| T2 | team_k3_hard70 | three-agent team on hard70, equal total wall | hard70 | 2 | — | —/—/.32 | —/—/.34 | .32 (.34) | —/—/0.10 | —/—/86 | —/—/0.9 | REVERTED |
| T3 | solo_decomposable | solo winner on the decomposable manifest | decomposable | 2 | 30 | .67/.75/.59 | .67/.80/.64 | .67 (.70) | 0.03/0.04/0.05 | 24/30/35 | 0.5/1.0/1.0 | reference |
| T4 | team_decomposable | three-agent team on the decomposable manifest | decomposable | 2 | — | .33/.25/.18 | .67/.50/.36 | .25 (.51) | 0.07/0.10/0.09 | 20/26/24 | 0.7/1.5/0.8 | REVERTED |
|  |  |  |  |  |  |  |  |  |  |  |  |  |
| **policy-neutrality selection (sonnet and fable, dev60)** |  |  |  |  |  |  |  |  |  |  |  |  |
| S0 | baseline_sonnet_dev60 | naive whole-file check | dev60 | 2 | 30 | .93/.95/.80 | .95/1.00/.85 | .89 (.93) | 0.09/0.14/0.15 | 61/77/112 | 3.7/6.1/6.4 | control |
| S7 | session_try_hints_auto_sonnet_dev60 | winner tool set | dev60 | 2 | 30 | .93/.82/.70 | .95/.85/.75 | .82 (.85) | 0.06/0.11/0.13 | 43/49/81 | 1.7/4.6/5.9 | measured |
| S8 | unified_sonnet_dev60 | draft-first prompting | dev60 | 2 | 30 | .93/.85/.75 | 1.00/.95/.90 | .84 (.95) | 0.05/0.12/0.15 | 33/54/89 | 1.7/4.7/5.5 | superseded by universal (A24) |
| Sn | sonnet_native_dev60 | native style, cap 50 | dev60 | 2 | 50 | .95/.85/.75 | .95/.95/.80 | .85 (.90) | 0.04/0.11/0.14 | 37/53/90 | 1.6/4.2/4.4 | measured |
| Sn2 | sonnet_native_auto2_dev60 | native style + synthesis, cap 50 | dev60 | 1 | 50 | 1.00/.85/.85 | 1.00/.85/.85 | .90 (.90) | 0.09/0.10/0.12 | 42/47/93 | 3.3/4.2/4.8 | measured |
| S10 | universal_sonnet_dev60 | universal, cap 50 | dev60 | 2 | 50 | .95/1.00/.85 | .95/1.00/.90 | .93 (.95) | 0.06/0.09/0.11 | 36/42/85 | 2.0/3.4/4.0 | selected |
| F0 | baseline_fable_dev60 | naive whole-file check | dev60 | 1 | 30 | .95/1.00/.95 | .95/1.00/.95 | .97 (.97) | 0.09/0.19/0.33 | 51/39/73 | 1.0/2.5/4.8 | control |
| F10 | universal_fable_dev60 | universal, cap 50 | dev60 | 1 | 50 | .95/1.00/1.00 | .95/1.00/1.00 | .98 (.98) | 0.14/0.16/0.29 | 49/41/57 | 1.7/1.9/3.7 | selected |

Solved attempts that were wall-killed have no final usage record and are excluded from the output-token mean: F0 baseline_fable_dev60 1 (none elsewhere).

Autoform-arc: every autoformalization development run that is not a current arm of section 4
(proposals and reruns, all reverted or superseded; $/solve and wall are computed on the
five-task set, so runs on the earlier seven- and fourteen-task sets show —), computed from
`harness/results_tables/autoform_arms.py`:

- af2_base — 11/20, $2.06, 699 s
- af2_evolve — 7/20, $3.32, 333 s
- af2_sota — 2/20, $16.3, 439 s
- af3_base2 — 12/20, $2.10, 693 s
- af3_evolve_c3 — 14/20, $3.69, 510 s
- af3_evolve_r1 — 15/20, $3.08, 514 s
- af3_evolve_r3 — 15/20, $2.76, 453 s
- af_base_haiku — 1/14, —, —
- af_base_sonnet — 6/7, —, —
- af_plan_sonnet — 6/7, —, —
- af_team_sonnet — 6/7, —, —
- af_tools2_haiku — 0/14, —, —
- af_tools2_sonnet — 7/7, —, —
- af_tools3_haiku — 3/14, —, —
- af_tools_haiku — 2/14, —, —
- af_tools_sonnet — 5/7, —, —
- mst3_sota — 0/20, —, —
- mst_base — 0/20, —, —
- mst_evolve — 0/20, —, —
- w2_base_sonnet — 5/8, $1.37, 648 s
- w2_prover2_sonnet — 4/8, $2.05, 419 s
- w2_prover_sonnet — 7/8, $1.02, 377 s
- w2_sota_sonnet — 1/8, $11.3, 335 s
- w2_sota_unfair — 2/8, $4.75, 488 s
- w2_team_sonnet — 2/4, $3.24, 538 s
- w2_verify_sonnet — 4/8, $1.98, 386 s

## 2. dev60 (uniform cap-30 arena, matching the evolve campaign)

Campaign conventions: pass@1 = solved/attempts over ALL reps; pass@2 = either of the first
two reps; wall = mean seconds per attempt (failures included). Arena is uniformly turn-cap
30: haiku rows are the native cap-30 runs; sonnet and fable rows are verified
cap-30-identical (no attempt, solved or not, ever passed 30 turns); mistral and terra rows
are counterfactually censored at turn 30 (a solve past turn 30 counts as unsolved; cost and
wall truncated at the turn-30 boundary from per-turn transcripts — exact under the
cap-invisible-to-policy assumption, the same replay technique as the turn-cap-tax
analysis). The killed column is dropped: under cap-30, terminations are predominantly
cap-outs and a wall-kill rate is not meaningful. miniF2F remains wall-only.

| model | arm | pass@1 e/m/h | pass@2 e/m/h | pooled @1 (@2) | $/solve e/m/h | out ktok (solved) e/m/h | wall s/att e/m/h |
|---|---|---|---|---|---|---|---|
| haiku | control | .44/.25/.30 | .50/.30/.35 | .33 (.38) | .17/.43/.44 | 2.5/2.6/8.5 | 90/122/157 |
| haiku | sibling | **.68**/.35/.35 | **.70**/.40/.35 | .46 (.48) | .09/.23/.29 | 2.3/2.6/3.0 | 65/80/97 |
| haiku | evolve | .65/**.50**/**.47** | .65/**.55**/**.50** | **.54** (**.57**) | **.08**/**.12**/**.15** | **1.1**/**2.0**/**2.0** | **41**/**54**/**73** |
| | | | | | | | |
| sonnet | control | .93/.95/.80 | .95/1.00/.85 | .89 (.93) | .09/.14/.15 | 3.7/6.1/6.4 | 61/77/112 |
| sonnet | sibling | **1.00**/.97/.78 | **1.00**/1.00/.80 | .92 (.93) | .11/.17/.18 | 3.0/5.0/5.2 | 45/61/110 |
| sonnet | evolve | .95/**1.00**/**.85** | .95/1.00/**.90** | **.93** (**.95**) | **.06**/**.09**/**.11** | **2.0**/**3.4**/**4.0** | **36**/**42**/**85** |
| | | | | | | | |
| fable (1 rep) | control | .95/1.00/.95 | — | .97 | **.08**/.19/.33 | **1.0**/2.5/4.8 | 51/**39**/73 |
| fable (1 rep) | evolve | .95/1.00/**1.00** | — | **.98** | .14/**.16**/**.29** | 1.7/**1.9**/**3.7** | **49**/41/**57** |
| | | | | | | | |
| mistral | control | **.42**/.25/.15 | **.50**/.25/.20 | .27 (.32) | .63/1.39/2.46 | 1.4/**0.4**/6.3 | 153/206/232 |
| mistral | sibling | .25/.17/.07 | .35/.20/.15 | .16 (.23) | .93/1.31/5.58 | 0.9/1.2/3.1 | **45**/**45**/**76** |
| mistral | evolve | .35/**.33**/**.35** | .40/**.35**/**.40** | **.34** (**.38**) | **.59**/**.68**/**.75** | **0.2**/0.5/**0.2** | 141/146/141 |
| | | | | | | | |
| terra | control | .95/.90/**.85** | .95/.95/.85 | **.90** (.92) | .02/.04/.06 | 2.0/2.8/3.9 | 46/61/75 |
| terra | sibling | .95/**.93**/.78 | .95/.95/.85 | .89 (.92) | .02/.04/.08 | 1.5/2.6/3.0 | 45/52/80 |
| terra | evolve | **.97**/.90/.80 | **1.00**/.95/**.90** | .89 (**.95**) | **.01**/**.03**/**.04** | **0.8**/**1.2**/**1.6** | **31**/**41**/**55** |

Cap-30 readings, descriptive: the censor barely touches the weak tiers (mistral loses
0/4/1 solves across control/sibling/evolve) but taxes terra's long sessions — evolve
loses 9 of 116 solves and the
pooled pass@1 ordering flips to control-first (.90/.89/.89), while evolve keeps every cost
and wall column and pass@2. The registered arena is the wall-only matrix (§3); this table is
the development arena's view. Sibling rows remain the env-bridged remeasure. For the
censored mistral and terra rows, the cost and wall are truncated at the
turn-30 boundary from the per-call transcript usage
(`harness/results_tables/cap30_truncation.py`). Solved attempts that were wall-killed have no final usage record and are excluded from the output-token mean: fable control 1 (none elsewhere).

## 3. miniF2F test (244 × 2 reps, 300 s wall, one registered look per registration)

Cost convention of this table (Claude-CLI arms): a wall-killed attempt has no cost record
and contributes zero to $/solve (`final_tables.py`: `total_cost_usd or 0`); the Mistral and
terra drivers record a cost for every attempt. Recovered-cost sonnet cells are computed at
run time by `harness/results_tables/heldout_cost_recovered.py` (same ordering, every
bucket). Every row is prompt-free (no system prompt, one rules template) except the
disclosed extra haiku row "evolve, guided phase-1 prompt": the A100 wall-only rerun of the
frozen phase-1 configuration, whose system prompt and task template prescribe tool strategy;
it is shown unbolded, enters no pooled cell and no contrast (A150), and the haiku evolve row
proper is the prompt-free arm of A150 (same server, tools and rail as the guided one). The mistral evolve arm is partly rail-bound
(72/488 attempts ended at the cap-100
rail, computed by `harness/results_tables/rail_census.py`; the tax falls on evolve). Kill
rates are descriptive (arena-dependent) and not bolded. Every family is reported at two reps
(A147). Haiku: control and sibling are the A118 arms, rep 0 of 2026-08 and rep 1 of 2026-09
(A146), beside the prompt-free evolve arm of 2026-09-23 (A150); the guided phase-1 evolve
row of 2026-07 is kept as the disclosed extra row above. The A144 stability probe (haiku
behaviour unchanged since July) covers the era mix. Opus: the
control's rep 0 is the A142 pinned-environment rerun (CLI 2.1.245, effort xhigh, 2026-09)
and its rep 1 the registered 2026-08-29 rep; the registered July-era rep 0 (A120, A143:
a serving regime that no longer reproduces) is shown on its own unbolded row and enters no
other cell. Solved attempts that were wall-killed have no final usage record and are excluded from the output-token mean: opus evolve 7, opus control 3, haiku evolve, guided 1, opus sibling 1 (none elsewhere).

| model | arm | pass@1 e/m/h | pass@2 e/m/h | pooled @1 (@2) | $/solve e/m/h | out ktok (solved) e/m/h | wall s e/m/h | killed % e/m/h |
|---|---|---|---|---|---|---|---|---|
| haiku | control | .28/.05/.03 | .32/.05/.03 | .17 (.19) | 0.13/**0.22**/2.19 | 5.0/5.8/14.7 | 53/**60**/**86** | 65/92/90 |
| haiku | sibling | .55/.10/.09 | .59/.14/.09 | .34 (.37) | 0.15/0.48/0.49 | 4.1/**5.5**/**8.3** | 51/66/96 | 39/80/86 |
| haiku | evolve (A150) | **.69**/**.28**/**.14** | **.72**/**.35**/**.17** | **.48** (**.52**) | **0.12**/0.39/**0.48** | **4.0**/9.3/12.6 | 51/116/136 | 29/60/77 |
| haiku | evolve, guided phase-1 prompt (A100; not pooled, A150) | .67/.25/.09 | .72/.33/.17 | .45 (.51) | 0.06/0.26/0.68 | 2.4/4.5/7.6 | 51/107/156 | 33/56/73 |
| | | | | | | | | |
| sonnet | control | .67/.34/.20 | .71/.41/.20 | .50 (.54) | 0.20/0.43/0.39 | 6.6/14.9/15.0 | 77/161/153 | 32/63/83 |
| sonnet | sibling | .88/.54/.63 | .90/.57/.66 | .73 (.76) | 0.19/0.48/0.52 | 3.4/9.0/12.8 | 47/**114**/142 | 8/35/40 |
| sonnet | evolve (A108) | **.92**/**.71**/**.69** | **.94**/**.78**/**.71** | **.82** (**.86**) | **0.13**/**0.38**/0.39 | **2.7**/**8.8**/**10.7** | **41**/115/**127** | 8/26/31 |
| | | | | | | | | |
| opus | control | .62/.29/.11 | .64/.32/.14 | .44 (.46) | 0.22/0.52/0.68 | 4.8/13.3/17.9 | 67/169/206 | 40/72/87 |
| opus | sibling | .89/.54/.51 | .92/.62/.51 | .73 (.77) | 0.24/0.49/0.61 | 4.0/9.3/13.5 | 57/121/**163** | 12/43/56 |
| opus | evolve (A117) | .89/**.61**/.51 | **.93**/**.65**/**.63** | **.75** (**.80**) | **0.18**/**0.38**/**0.55** | **3.1**/**8.0**/**12.9** | **49**/**116**/165 | 9/40/47 |
| opus | control, registered rep 0 (July era; A120/A143; not pooled) | .78/.44/.34 | — | .61 | 0.23/0.42/0.58 | 5.5/10.6/15.6 | 81/136/187 | 22/54/66 |
| | | | | | | | | |
| mistral | control | .16/.04/.00 | .22/.04/.00 | .10 (.13) | **2.86**/**12.9**/— | 1.6/2.7/— | 29/49/— | 48/73/77 |
| mistral | sibling | .11/.03/.00 | .14/.04/.00 | .07 (.09) | 6.12/27.0/— | 1.2/1.1/— | 25/**22**/— | 5/9/10 |
| mistral | evolve (A113, partly rail-bound) | **.42**/**.06**/**.03** | **.47**/**.10**/**.03** | **.25** (**.29**) | 3.34/28.3/86.1 | **0.5**/**1.0**/0.1 | **18**/31/3 (n=1) | 10/15/24 |
| | | | | | | | | |
| terra | control | .72/.42/.29 | .77/.44/.34 | .56 (.60) | 0.10/0.28/0.42 | 4.5/8.1/10.7 | 71/111/135 | 7/5/1 |
| terra | sibling | .95/.67/.66 | .95/.72/.71 | .82 (.84) | 0.04/0.14/0.15 | 2.3/6.4/7.1 | 44/102/101 | 5/8/1 |
| terra | evolve (A115b) | **.97**/**.81**/**.71** | **.98**/**.85**/**.77** | **.88** (**.91**) | **0.03**/**0.09**/**0.10** | **1.4**/**3.6**/**4.2** | **41**/**93**/**93** | 1/3/4 |
| | | | | | | | | |
| none | finisher-only (A114) | .35/.06/.03 | — | .21 | 0 | 0.0 | 1/1/2 | 0/0/0 |

Provenance of the Claude-CLI rows above (CLI build of each attempt, from the attempts' own
init events; counts are rows):

- haiku control: 2.1.233 ×292, 2.1.245 ×196
- haiku sibling: 2.1.233 ×241, 2.1.245 ×247
- haiku evolve: 2.1.245 ×488
- haiku evolve, guided (A100): 2.1.209 ×488
- sonnet control: 2.1.201 ×224, 2.1.209 ×264
- sonnet sibling: 2.1.209 ×488
- sonnet evolve: 2.1.209 ×488
- opus control (coherent pair): 2.1.245 ×488
- opus control, registered rep 0: 2.1.209 ×201, 2.1.228 ×43
- opus sibling: 2.1.228 ×244, 2.1.245 ×244
- opus evolve: 2.1.228 ×244, 2.1.245 ×244

### 3b. Sibling-verified pass@1 (post hoc, A121; the registered numbers above are unchanged)

Every gate-rejected artifact of every arm in §3, and every gate-solved one, was re-verified
with the sibling server's `rocq_verify` tool (rocq-mcp 0.3.1) over its real MCP interface:
6,535 artifacts, 6,385 agreements, 0 unsound solves (no gate-accepted proof the sibling
rejects for a real reason), 139 gate-stricter rows (proofs the sibling accepts and our gate
rejects: 54 helper lemmas outside the locked prefix, 46 preamble edits, 29 `Require` inside
the proof, 8 `Unset` printing flags, 2 convertible restatements), 2 sibling limitations
(gate-solved proofs the sibling cannot check, evar capture), 9 artifact-drift rows (file
rewritten after the attempt deadline, never credited). The column below adds the rep-0
gate-stricter rows to the registered rep-0 solves, per bucket, computed at run time by
`harness/results_tables/audit_verify_rows.py` (evidence `EXP/logs/audit_verify/`). It is
post hoc and direction-blind; the registered column stays
the reported one. The only arm it moves by more than one point is the sonnet sibling (+14
rep-0 solves, helper-lemma and preamble patterns the locked-prefix gate refuses), which
narrows the sonnet evolve−sibling pooled gap from .09 to .03; the terra evolve−sibling gap
is unchanged (+1 on evolve).

| model | arm | registered e/m/h | pooled | sibling-verified e/m/h | pooled | rep-0 credited / debited |
|---|---|---|---|---|---|---|
| haiku | control | .28/.05/.03 | .17 | .33/.05/.03 | .20 | +7 / −0 |
| haiku | sibling | .55/.10/.09 | .34 | .57/.10/.09 | .35 | +3 / −0 |
| haiku | evolve, guided phase-1 prompt (A100; the prompt-free A150 arm postdates the audit) | .67/.25/.09 | .45 | .67/.25/.09 | .45 | +0 / −0 |
| sonnet | control | .67/.34/.20 | .50 | .68/.34/.20 | .50 | +1 / −0 |
| sonnet | sibling | .88/.54/.63 | .73 | .91/.67/.63 | .79 | +14 / −0 |
| sonnet | evolve (A108) | .92/.71/.69 | .82 | .92/.71/.69 | .82 | +0 / −0 |
| opus (registered rep 0) | control (July era, A120/A143) | .78/.44/.34 | .61 | .78/.44/.34 | .61 | +0 / −0 |
| opus (registered rep 0) | sibling | .89/.54/.51 | .73 | .89/.56/.51 | .73 | +1 / −0 |
| opus (registered rep 0) | evolve (A117) | .89/.61/.51 | .75 | .90/.62/.51 | .75 | +2 / −0 |
| mistral | control | .16/.04/.00 | .10 | .19/.04/.00 | .11 | +4 / −0 |
| mistral | sibling | .11/.03/.00 | .07 | .12/.03/.00 | .07 | +2 / −0 |
| mistral | evolve (A113) | .42/.06/.03 | .25 | .42/.06/.03 | .25 | +0 / −0 |
| terra | control | .72/.42/.29 | .56 | .72/.42/.29 | .56 | +0 / −0 |
| terra | sibling | .95/.67/.66 | .82 | .95/.67/.66 | .82 | +0 / −0 |
| terra | evolve (A115b) | .97/.81/.71 | .88 | .97/.81/.74 | .89 | +1 / −0 |
| none | finisher-only (A114) | .35/.06/.03 | .21 | .35/.06/.03 | .21 | +0 / −0 |

### 3c. Efficiency on the problems every arm solved (post hoc, descriptive)

For each family, the set below is the (problem, slot) pairs where control, sibling AND
evolve ALL solved the same problem in the same slot — slot 0 and slot 1 are the two reps
of each arm as §3 reports them (for the opus control, slot 0 is the A142 rerun and slot 1
the registered rep 1, A147; slot pairing across arms is a convention, reps being
independent draws) — so the $/solve, wall and token columns are not confounded by which
problems each arm happened to solve, unlike the pass@1-conditioned columns of §3. A pair
is dropped, and counted, when any arm's solved attempt there was wall-killed (Claude-CLI
usage.estimated true: no final usage record, hence no cost record); dropped pairs:
haiku none, sonnet none, opus 4, mistral none, terra none (mistral and terra never drop a pair — neither driver ever records a
solved attempt with no usage). Every attempt in a family's set is solved by construction,
so $/solve and wall need no failure convention here, unlike §2/§3/§4's total-cost/wall-of-
all-attempts-per-solved convention. Post hoc and descriptive: not a registered contrast.

| model | arm | $/solve e/m/h | wall s e/m/h | out ktok e/m/h |
|---|---|---|---|---|
| haiku (n 71/7/1) | control | 0.06/0.08/0.15 | 51/65/86 | 4.8/6.3/14.7 |
| haiku (n 71/7/1) | sibling | 0.05/0.05/0.05 | 28/30/40 | 2.2/2.4/3.8 |
| haiku (n 71/7/1) | evolve (A150) | **0.03**/**0.03**/**0.04** | **17**/**17**/**28** | **1.1**/**1.1**/**2.8** |
| | | | | |
| sonnet (n 172/49/11) | control | 0.19/0.36/0.39 | 75/153/153 | 6.4/14.1/15.0 |
| sonnet (n 172/49/11) | sibling | 0.11/0.27/0.23 | 28/84/66 | 1.7/6.1/5.6 |
| sonnet (n 172/49/11) | evolve (A108) | **0.08**/**0.17**/**0.18** | **21**/**57**/**62** | **1.1**/**3.8**/**4.8** |
| | | | | |
| opus (n 154/38/9) | control (A142 rerun + registered rep 1) | 0.21/0.48/0.68 | 63/153/206 | 4.6/12.5/17.9 |
| opus (n 154/38/9) | sibling | 0.13/0.29/0.31 | 26/68/**66** | 1.5/4.9/5.3 |
| opus (n 154/38/9) | evolve (A117) | **0.07**/**0.18**/**0.24** | **16**/**51**/67 | **0.7**/**3.4**/**4.9** |
| | | | | |
| mistral (n 21/3/0) | control | 0.01/0.02/— | 11/20/— | 0.6/1.0/— |
| mistral (n 21/3/0) | sibling | 0.12/0.14/— | 17/23/— | 0.8/1.0/— |
| mistral (n 21/3/0) | evolve (A113) | 0.01/**0.00**/— | **5**/**3**/— | **0.1**/**0.1**/— |
| | | | | |
| terra (n 180/58/19) | control | 0.04/0.08/0.10 | 69/108/135 | 4.5/8.2/10.7 |
| terra (n 180/58/19) | sibling | 0.02/0.05/0.04 | 27/68/58 | 1.3/3.8/4.1 |
| terra (n 180/58/19) | evolve (A115b) | **0.01**/**0.03**/**0.03** | **21**/**54**/**50** | **0.6**/**1.8**/**2.1** |

## 4. Autoformalization (5 tasks × 4 reps, 900 s wall; grading-corrected; $/solve cost-recovered)

$/solve here = total cost of ALL attempts (failures included) per solved attempt, with the
costs of wall-killed attempts recovered from per-message token usage exactly as the
experiment repo's dashboard does (A78/A79; computed at run time by
`harness/results_tables/autoform_arms.py`). The recovery prices tokens at the
claude-sonnet-5 rate table, so the opus cells are lower bounds for the killed attempts'
share. Kills (num_turns absent): sonnet 10/10/7, opus 7/5/4, terra 0
(killed-attempt fractions differ by more than 10 points in some pairs, so cost and wall
comparisons are censored per A71b).

| model | arm | solve | $/solve | out ktok (solved) | wall s |
|---|---|---|---|---|---|
| sonnet | control | 10/20 | **2.47** | 52.2 | 608 |
| sonnet | sibling | 12/20 | 5.73 | 34.8 | 595 |
| sonnet | evolve | **14/20** | 2.91 | **23.2** | **429** |
| | | | | | |
| opus (2 reps) | control | 3/10 | **2.30** | 50.7 | 714 |
| opus (2 reps) | sibling | 6/10 | 3.56 | 40.2 | 661 |
| opus (2 reps) | evolve | 6/10 | 2.37 | **39.3** | **574** |
| | | | | | |
| mistral | control | 0/20 | — | — | — |
| mistral | sibling | 0/20 | — | — | — |
| mistral | evolve | 0/20 | — | — | — |
| | | | | | |
| terra | control | 10/20 | 0.58 | 14.4 | 348 |
| terra | sibling | 7/20 | 1.00 | 14.2 | 502 |
| terra | evolve | **12/20** | **0.37** | **7.8** | **278** |

Coverage notes: every miniF2F family (haiku, sonnet, opus, mistral, terra) is reported at
two reps per arm. The A120 era question is closed by the A143/A144 probes: the
July→August shift was server-side and specific to claude-opus-4-8; sonnet and haiku
reproduce their July reps today. Opus miniF2F therefore reports both reps, with the
control's coherent pair (A142 rerun + registered rep 1, A147) and the registered July-era
rep 0 kept visible but unpooled. Haiku control and sibling are the A118 arms completed
to two reps under A146; the haiku evolve arm is the prompt-free A150 arm, the guided
phase-1 row being a disclosed extra. Fable has no sibling run and 1 rep (pass@2 undefined).
Sonnet autoform control has a second current draw at 12/20 ($2.10 recovered, 693 s); the
evolve row is the shipped-config draw, the other three draws (15, 15, 14) are the
single-feature-reverted variants R1, R3, C3, not re-runs of the shipped binary.
Mistral autoform sibling is the v2 full-surface remeasure. Terra rows are post-A115c repair.
Solved attempts that were wall-killed have no final usage record and are excluded from the output-token mean: sonnet sibling 2, sonnet evolve 1, opus sibling 1 (none elsewhere).

### 4b. Re-verified solve counts (post hoc, A130/A131; the registered cells above are unchanged)

All 462 attempts of the 29 archived runs were re-graded in fresh sandboxes by an independent
checker (assumptions of every probe read through the Rocq API, where the original grader
parses `Print Assumptions` text and would miss a `#[bypass_check]` definition; none was
found) and by REFERENCE-DERIVED EXTENDED PROBES: hundreds to thousands of concrete
instances per required name with expected values computed from each task's gate-validated
reference, plus non-vacuity witnesses (`EXP/data/autoform/<task>/audit/`, evidence
`EXP/logs/audit_autoform/`). Outcome: 0 gate-unsound rows (no gate solve fails the strict
checker), 2 gate-stricter rows (a scratch file with `Abort`/`Admitted` that no probe uses;
credited below, bracketed), 4 extended-probe failures, all terra, all verified in the
sources: the three triadic solves define `tstep` by cases on the probe inputs 12/15/27/30
and return junk elsewhere; the terra evolve prodauto solve defines `trace` as a constant
two-element list, which makes the pumping theorem trivially true. Six further terra triadic
attempts tried `Unset Guard Checking` and were rejected by both graders. A mutation
analysis of the references found 16 wrong formalizations the shipped probes accept
(frugal 5, gauges 2, ledger 2, prodauto 4, triadic 3, each with a checked killing probe):
the probes pin a handful of literal inputs. Every solved attempt of every Claude and
Mistral arm passes the extended probes.

| model | arm | registered | re-verified |
|---|---|---|---|
| sonnet | control | 10/20 | 10/20 |
| sonnet | sibling | 12/20 | 12/20 |
| sonnet | evolve | 14/20 | 14/20 [15 crediting the scratch-file row] |
| opus (2 reps) | control / sibling / evolve | 3 / 6 / 6 of 10 | unchanged |
| mistral | all three | 0/20 | 0/20 |
| terra | control | 10/20 | **8/20** (both triadic solves) |
| terra | sibling | 7/20 | 7/20 |
| terra | evolve | 12/20 | **10/20** (triadic and prodauto solves) |

Sonnet control draw 2 (12), the reverted variants R1/R3/C3 (15/15/14) and every historical
arena row are unchanged. The sonnet ordering and margins stand; the terra ordering stands
with a smaller spread (evolve 10, control 8, sibling 7).

## 5. Registered paired contrasts, miniF2F (pooled exact McNemar, rep-0, Holm per family)

| family | evolve vs control | evolve vs sibling |
|---|---|---|
| sonnet (A108) | 81:2, p = 7.2e-22 | 26:5, p = 1.9e-4 |
| haiku (A118 comparators, A150 prompt-free evolve) | 76:0, p = 2.6e-23 | 37:2, p = 2.8e-9 |
| opus (A147; control = A142 rerun) | 76:1, p = 1.0e-21 | 15:10, p = .42 |
| mistral (A113) | 38:1, p = 1.5e-10 | 46:1, p = 6.8e-13 |
| terra (A115b) | 79:0, p = 3.3e-24 | 21:5, p = 2.5e-3 |

Opus, registered rep-0 contrast against the July-era control (A117 report-only; kept for the
record, A147): evolve vs control 42:9 (p = 3.4e-6); evolve vs sibling
15:10 (p = .42). The control side of the first pair is the 2026-07-16
rep 0 (201 rows on CLI 2.1.209 + 43 on 2.1.228), which the A143 probe showed to belong to a serving
regime that no longer reproduces; the opus row of the table above uses the A142 rerun instead.

## 6. Attribution (A114 zero-model finisher, F = 52/244)

| arm | rep-0 solves E | E∩F | model-required (E\F) |
|---|---|---|---|
| sonnet evolve | 200 | 52 | 148 (74%) |
| mistral evolve | 61 | 50 | 11 (18%) |
| terra evolve | 215 | 52 | 163 (76%) |

## 7. Hardest autoform tasks, all-time record

- prodauto: among the arms of §4, sonnet evolve 3/4, sonnet control draw 2 1/4, terra evolve
  1/4, no other; across the four sonnet evolve-family draws 12/16 (`autoform_arms.json`
  all_time: 21/95 over every archived non-smoke run, including superseded arenas). The terra
  evolve solve is a degenerate `trace` (A131, §4b), so re-verified: 20/95 all-time and 0 at
  terra; every sonnet prodauto solve passes the extended probes.
- triadic (olympiad): 0/55 across all Claude and Mistral arms through the A103 count and
  none in the 16 mistral-large attempts since (0/70 non-terra in `autoform_arms.json`); terra
  3/12 by the gate (control 2/4, evolve 1/4; solved walls 249–416 s of the 900 s budget) —
  BUT all three gate-passing terra submissions hardcode `tstep` on the probes' literal
  inputs (A130, verified in the sources; §4), so no arm, tier or family has formalized
  triadic: 0/82 all-time on the semantic column. The gate count stays the registered
  number; any sentence reading "terra solved triadic" must carry this caveat.

---

Revision 2026-09-02 (blueprint archive pass): §3 conventions paragraph added (cost
convention, guided haiku row, mistral rail, kill rates unbolded); opus rows relabelled rep 0
with pass@2 withheld [superseded 2026-09-17: opus pass@2 is reported]; finisher-only wall
cell corrected from "2/4/9" (no traceable source) to the log means 1.4/1.1/1.5 s printed as
1/1/2; §4 $/solve cells regenerated under the recovered-cost convention (previous raw cells:
sonnet 1.56/1.86/1.17, opus 2.19/2.06/1.89, base2 1.18) with bold recomputed; coverage
notes corrected (haiku comparators run and withheld [superseded 2026-09-17: reported];
opus rep 1 exists); §5 opus note carries the CLI-version tag; §7 counts scoped.
Every number is computed at run time from `logs/` by `harness/results_all_gen.py` and the
modules under `harness/results_tables/`; nothing is archived or typed.

Revision 2026-09-04 (audit pass): §3 opus control easy pass@1 corrected from `.79` to `.78`
(102/130 = .785 at rep 0 of FINAL_pf_baseline_opus; a typed slip also present in the
case-study section, LINEAGE_AUDIT.md); 2026-09-06: §3 sonnet evolve (A108) medium pass@2
likewise `.79` → `.78` (62/79 = .785; the same two slips LINEAGE_AUDIT.md lists for the
case-study section, caught here by the repaired `EXP/harness/final_tables.py`); §3 mistral
control easy pass@2 `.21` → `.22` (28/130 = .215, per `a113_rows.json` and the raw log,
caught by `tables/results_all_gen.py`, which now regenerates this whole file); every other §3 pass@1 and pooled cell re-derived
from results.jsonl by `tables/audit_verify_rows.py` and found identical. §3b added (A121
sibling-verified column). §4b added (A130/A131 re-verified solve counts over all 462
attempts) and §7 caveats added: the three terra triadic gate solves are hardcoded on the
probe inputs and the terra evolve prodauto solve has a degenerate `trace`; registered
cells unchanged.

Revision 2026-09-08: generator moved to the experiment repo (harness/results_all_gen.py);
table and output locations are now arguments; one phrase reworded (§2, replay technique),
no cell changed.

Revision 2026-09-08 (tokens): Mtok/solve column added to sections 2, 3 and 4 (definition in
the conventions; killed-attempt caveat in the section notes); every pre-existing cell
unchanged.

Revision 2026-09-08 (self-contained): the summary regenerates from the experiment repository
alone — archived table inputs under docs/results_tables (registered snapshots; provenance in
its README), producers under harness/results_tables, default output docs/RESULTS_ALL.md;
prose paths updated, no cell changed.

Revision 2026-09-08 (logs + scripts only): every table is computed at run time from the
campaign logs by the modules under harness/results_tables; the archived table JSONs and the
six hand-typed cap-30 cost/wall cells are gone (those cells are now derived from the
per-call transcripts, a turn ending when its tool result is back). All twelve reproduce the
previously typed values.

Revision 2026-09-09 (output tokens): the token column now reports the campaign's efficiency
objective, mean output tokens over solved attempts (out ktok (solved)), replacing the
total-token Mtok/solve figure, which counted cache reads at full weight and tracked context
volume rather than model output; wall-killed solved attempts (no final usage) are excluded
and counted in the section notes; every other cell unchanged.

Revision 2026-09-09 (common-solved efficiency): §3c added — cost, wall and output tokens
per arm restricted to the (problem, rep) pairs every arm of the family solved; no other cell
changed.

Revision 2026-09-09 (development ledger): section 1 is now a computed ledger of every
development run (harness/results_tables/ledger.py), replacing the decision-time prose;
bucket definitions added to the conventions; no other cell changed.

Revision 2026-09-17 (matrix completion, A142/A146/A147): every miniF2F family is reported
at two reps. The haiku control and sibling arms (A118, completed to two reps under A146)
enter §3, §3b, §3c and §5; the opus control is reported on its coherent pair (rep 0 = the
A142 pinned-environment rerun, rep 1 = the registered 2026-08-29 rep) with pass@2, and its
registered July-era rep 0 stays visible on an unbolded row that enters no other cell
(A120/A143); opus evolve and sibling report both reps; §5 gains the haiku (A118) and opus
(A147) rows and prints every p-value from the computed statistic (the two literal bounds
of the previous generator became exact values); a per-arm CLI-build provenance list
follows the §3 table; coverage notes rewritten. No sonnet, mistral, terra or autoform cell
changed.

Revision 2026-09-24 (A150, prompt uniformity): the haiku evolve row is now the prompt-free
arm FINAL_pf_session2_haiku (af_pf_session2 with the haiku model and the family's cap-200
rail; frozen server), so every family of §3 has three prompt-free arms; the guided phase-1
row (A100) stays as a disclosed, unbolded extra that enters no pooled cell and no contrast;
§3c and the §5 haiku contrast use the prompt-free arm; §3b keeps the guided row as the
audited one. Conventions: output tokens described as the reported efficiency metric, not an
optimized objective. No sonnet, opus, mistral, terra or autoform cell changed.

Revision 2026-09-25 (report tables, A152): section 8 added — the tables of the external
write-up (common-solved cost/wall, efficiency, project-scale, evolution points, per-mutation
deltas) computed by harness/results_tables/report_tables.py under one stated convention each;
no other section changed. Same day (A153): section 8 moved out to its own document,
docs/REPORT_TABLES.md (harness/report_tables_gen.py), which carries only the presented tables
and the runs behind them; this document keeps sections 1-7 unchanged.
