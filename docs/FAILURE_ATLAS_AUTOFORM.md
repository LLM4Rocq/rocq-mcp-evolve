# Failure Atlas — af3 autoform arena (phase 2)

Lab-notebook synthesis of five verified mining passes over the six current-arena
runs (`logs/autoform/{af3_base, af3_evolve, af3_sota, af3_evolve_r1, af3_evolve_r3,
af3_evolve_c3}`; wall-only 900s budget, no system prompt, 5 tasks x 4 reps = 20
attempts/arm, 120 attempts total). Every claim below was independently re-derived
by a verifier from `results.jsonl`, `verdict.json`, `server.jsonl`,
`transcript.jsonl`, and final workspaces; miners' corrections are folded in.
**All findings in this atlas carry `verified: true`; no [UNVERIFIED] items remain.**
The single forward-looking caveat (audit layer unobserved for the 6 gate-artifact
attempts) is flagged inline where used.

Scoreboard (recomputed from `results.jsonl`, 2026-07): base 9/20, evolve 13/20,
sota 12/20, evolve_r1 12/20, evolve_r3 15/20, evolve_c3 13/20 — 74 solved / 46
failed.

---

## 1. Headline taxonomy

Failure **class** is the mechanism; the gate's `reason` column is shown in
parentheses. Classes are disjoint; every one of the 46 failures is assigned
exactly once.

| Class (gate reason) | base | evolve | sota | r1 | r3 | c3 | **total** |
|---|---|---|---|---|---|---|---|
| **S — scaffold-at-wall** (forbidden_token) | 1 | 5 | 1 | 4 | 5 | 6 | **22** |
| **G — gate discovery artifact** (probes_failed, false negative) | 1 | 1 | 0 | 3 | 0 | 1 | **6** |
| **T — wall-kill, back-half modules never written** (probes_failed) | 2 | 0 | 4 | 0 | 0 | 0 | **6** |
| **B — broken deliverable** (build_failed) | 5 | 1 | 3 | 1 | 0 | 0 | **10** |
| **N — nothing built** (no_vo_built) | 2 | 0 | 0 | 0 | 0 | 0 | **2** |
| **failed** | 11 | 7 | 8 | 8 | 5 | 7 | **46** |
| **solved** | 9 | 13 | 12 | 12 | 15 | 13 | **74** |

Per-task failure mass: **triadic 24/24 failed** (0 solves in any arm), prodauto
14/24 failed (solved only by evolve-family: evolve 3, r1 2, r3 3, c3 2), ledger
3/24, frugal 3/24 (all three are Class G artifacts), gauges 2/24.

Two structural facts frame everything below:

1. **The gate grades disk state at a hard 900s kill.** All 22 Class-S rows and
   all 6 Class-T rows have `wall_s = 900.0/900.1`, `num_turns = None`, empty
   `result_text` — the process was killed mid-work, there was no submission.
   Three *solved* rows (af3_evolve/prodauto__rep3, af3_sota/ledger__rep1,
   af3_sota/ledger__rep3) were also wall-killed and graded solved on clean disk.
2. **The layer ordering inverts progress on triadic** (`harness/run_autoform.py:41-43`:
   `forbidden_token: 0 < build_failed/no_vo_built: 1 < probes_failed < audit`).
   Evolve-family attempts that machine-verified a whole theorem grade *lower*
   (forbidden_token, a leftover stub) than base attempts that never wrote the
   file at all (probes_failed/no_vo_built). Do not read the layer as progress.

---

## 2. Failure classes

### 2.1 Class S — scaffold-at-wall (forbidden_token), 22 attempts

**Mechanism.** Agents deliberately write all required `.v` files early with
`Admitted` stubs as project scaffolding, then interactively fill them; the 900s
wall kills them mid-fill; the gate finds a stub on disk and grades
forbidden_token (the lowest layer). This is **time-exhaustion of a deliberate
scaffold-first strategy, not forgetting**.

**Census** (from `verdict.json` `layers.forbidden` across all 6 runs): 22 total —
tasks triadic 17, prodauto 3, ledger 1, gauges 1; token `Admitted` x20, `admit`
x2 (af3_base/triadic__rep0 `Shrink.v: admit`, af3_evolve_c3/prodauto__rep3
`Scratch.v: admit`). Flagged files: Shrink.v x9, Fixed.v x6, Scratch.v x5,
Main.v x1, Empty.v x1 (verdict names the alphabetically-first dirty file; 6
attempts had 2-3 dirty files).

**Evidence chain.**

- *Deliberate and early*: in 13/22 the verdict-flagged file receives the token
  within ~6.5 min (63s, 75s, 101s, 195...381s; write seq 7-10); counting any
  `.v` file, 18/22 within 380s, typically Props.v at seq 4-5 (r3/triadic__rep1:
  Props.v with Admitted at t=10s). Verbatim intent: *"I'll scaffold the project
  structure first, then work through each file."* (af3_evolve/triadic__rep3);
  *"setting up the project skeleton (dune files + the four .v files with
  scaffolded definitions"* (c3/triadic__rep3); *"Good, it builds (with expected
  warnings, using Admitted as scaffolding)."* (c3/triadic__rep1).
- *No submission, active at kill*: last tool call lands at t=868-899s in 21/22
  (sole exception af3_base/triadic__rep0, dune_build@720s then thinking until
  the kill). Final assistant texts open *new* work: *"Fixed.v is complete. Now
  let's tackle Shrink.v."* (evolve/triadic__rep1); *"Now the k=5 case (should
  derive a contradiction via 5 | m)."* (r3/triadic__rep1); *"Excellent! Shrink.v
  is fully proven. Let me write the final file with the complete proof."*
  (c3/triadic__rep3).
- *Not forgetting*: agents were provably working on the flagged lemma at kill
  time (evolve/triadic__rep1's last call is `open()` on tstep_shrink_odd at
  t=896s), and acted on verify signals when received: evolve/ledger__rep3 got
  *"VERIFY FAILED — fix before finishing: - Balance.v: `Admitted`"* at t=234s
  and 583s and delivered Balance.v with 0 Admitted (879s/888s rewrites) — it
  died on a *new* Scratch.v (6 Admitted, written t=673s).
- *Rule was in-band from turn 0*: all six `configs/af3_*.json` contain verbatim
  rule (4): *"your .v files must not contain admit, Admitted, Axiom, Parameter,
  Hypothesis, Variable, or Section. Prove every lemma outright or leave it
  unwritten."* A post-scaffold VERIFY FAILED warning reached only 5/22; 15/22
  never called verify; dune_build carries no token information (Admitted
  compiles clean).
- *The strategy itself is viable*: 32 of 74 **solved** attempts used identical
  Admitted scaffolds and cleaned them in time (e.g. evolve/gauges__rep0: first
  token write 40s, last 152s, solved at 369.1s); 74/74 solved attempts called
  verify before grading. evolve/prodauto__rep3 scaffolded at 331s, cleaned by
  373s, was wall-killed at 900s and graded **solved** on clean disk — same
  strategy, same kill, different disk state.

**Outlier**: the single af3_base case (triadic__rep0) is a different profile —
first tool call at t=427.5s (47.5% of wall) after a ~39.7k-token thinking run;
the 484s Shrink.v write already carried a real `Admitted.`; final 180s spent
thinking with no tool activity. verify was available in base
(`mcp__files__verify` in allowed_tools; all 9 base solves used it) but never
invoked here.

**Attempts (22):** af3_base/triadic__rep0; af3_evolve/{ledger__rep3,
triadic__rep0-3}; af3_evolve_c3/{prodauto__rep0, prodauto__rep3, triadic__rep0-3};
af3_evolve_r1/{gauges__rep3, triadic__rep0, rep1, rep3};
af3_evolve_r3/{prodauto__rep0, triadic__rep0-3}; af3_sota/triadic__rep0.

### 2.2 Class G — gate discovery artifact (probes_failed on provably-correct work), 6 attempts

**Mechanism.** `harness/autoform_gate.py:97-101`: the gate locates the task
library via `vo = list((work/"_build"/"default").rglob("*.vo"))` then
`theory_dir = vo[0].parent` over an **unordered** rglob. Six agents delivered
all required TaskLib modules *and* a byte-identical copy of `probes.v` in a
second dune theory (`tests/`, `test/`, or `probes/`) as self-verification. The
rglob resolved `theory_dir` to the test-theory dir (which contains only
`probes.vo`), so `-Q <testdir> TaskLib` was empty and every probe run died at
line 1: *"Unable to locate library \<Mod\> with prefix TaskLib (while searching
for a .vos file)"*.

**Evidence chain.**

- `diff -q` shows the in-workspace probes copy **byte-identical** to
  `data/autoform/<task>/probes.v` in all 6; all required `.vo` files exist under
  `workspace/_build/default/theories`; `layers.build == 'ok'` in all 6 — the
  gate's own fresh dune build compiled the verbatim probes.v against their
  TaskLib, proving every pin holds.
- **Deterministic**: rescanning `_build/default` of all 120 attempts, exactly 6
  workspaces have `.vo` in more than one directory, and all 6 are these cases;
  zero solved attempts are multi-dir. The verdict always names the *first*
  module of probes.v line 1 (offsets match the 28-char prefix
  `From TaskLib Require Import `), consistent with an empty mapping.
- 5 of 6 finished under the cap claiming success (e.g. r1/prodauto__rep2 at
  790.3s with result_text containing verbatim *"clean build with no
  admits/axioms and all 11 probe proof blocks pass"*).
- **Score impact** (corrected scores if the artifact is fixed): base 9→10,
  evolve 13→14, r1 12→**15** (tying r3), c3 13→14; sota (12) and r3 (15)
  unchanged. CAVEAT: counts these as solved assuming the never-reached audit
  layer (Print Assumptions) would pass — plausible (forbidden layer passed,
  pins provably compile) but not directly observed.
- Spec deviation note: `data/autoform/frugal/spec.md:13-15` does mandate the
  single-`theories/` shape, so these agents deviated in layout — but the
  deviation was *adding self-verification of the probes*, and the gate's own
  build validated the mathematics.
- **Fix**: select `theory_dir` from the dune file declaring `(name TaskLib)`
  instead of `vo[0].parent` (`harness/autoform_gate.py:101`).

**Attempts (6):** af3_base/ledger__rep3 (tests/), af3_evolve/frugal__rep0
(probes/), af3_evolve_r1/frugal__rep2 (test/), af3_evolve_r1/prodauto__rep1
(tests/), af3_evolve_r1/prodauto__rep2 (probes/), af3_evolve_c3/frugal__rep0
(tests/).

### 2.3 Class T — wall-kill with back-half modules never written (probes_failed), 6 attempts

**Mechanism.** 900s kill mid-development before the hard back-half modules
existed; probes.v dies at the line-1 `Require` on the first missing module.
Module-level missing names, **not** wrong math or statement-shape mismatch.

**Evidence chain.**

- All six rows: `wall_s` 900.0/900.1, `num_turns` null, result_text `''`.
- Triadic x4: workspaces contain only `theories/Props.v + Step.v`; Fixed.v and
  Shrink.v absent (verdict offset names `Fixed` at chars 39-44, i.e. Props and
  Step resolved fine). Prodauto x2 (both sota): Dfa/Ops/Lang/Empty delivered,
  Pump.v/Main.v absent.
- Killed mid-stride, verbatim transcript tails: af3_sota/prodauto__rep0 ends
  *"Now let's develop Pump.v."* followed by `rocq_start`;
  af3_sota/triadic__rep2 ends *"Now let's redo the crux `chorus6m_ge` lemma
  with `lia` working directly."*
- **Zero paraphrase failures anywhere in the probes class** (this class + Class
  G = all 12 probes_failed attempts): regex check of definition headers shows
  every delivered module defines 100% of the names probes.v references; the
  gate-artifact 6 embedded probes.v byte-for-byte. 0% of probes_failed is wrong
  formalization; the split is exactly 50% gate artifact / 50% wall-clock.

**Attempts (6):** af3_base/triadic__rep1, af3_base/triadic__rep3,
af3_sota/triadic__rep2, af3_sota/triadic__rep3, af3_sota/prodauto__rep0,
af3_sota/prodauto__rep2.

### 2.4 Class B — broken deliverable (build_failed), 10 attempts

Heterogeneous; four sub-mechanisms.

**B1 — base blind-batch + thinking burn (5: af3_base {prodauto__rep1, rep2,
rep3; ledger__rep1; gauges 1 fail}).** Base writes whole files from in-head
plans and gets first compiler feedback catastrophically late (prodauto: 603.7s
rep2, 709.6s rep1, never for rep0/rep3). The errors it died on are three
mundane classes: (1) script overshoot — *"No such goal."* (tactic lines left
after `//=` closed the goal; prodauto rep2 Empty.v:17 + Lang.v:9, rep3
Lang.v:15); (2) the vm_compute wall — rep1 Main.v:31 `Proof. by vm_compute.
Qed.` under `Empty.nonemptyb prod23` → *"Error: No applicable tactic."*;
(3) implicit-argument misapplication — rep2 Pump.v:39 *"The term \"Hu\" has
type \"is_true (uniq (trace A w))\" while it is expected to have type \"dfa
?S\""*. Compounding noise: two base reps got ~6.1KB of pure
deprecation/coercion warnings clipped mid-line with **no Error line despite
exit 1**, and both rewrote `theories/dune` with `(flags (:standard -w -all))`.
(af3_base/ledger__rep1 is the A63-addendum gate-build-timeout case; recorded
here for completeness from `docs/ASSUMPTIONS.md`, not re-mined.)

**B2 — sota self-inflicted plumbing (3: af3_sota {prodauto__rep1, prodauto__rep3,
triadic__rep1}).** rep1: the `keep_vo=True` load-path workaround wrote
.vo/.vok/.vos into `theories/`, and with no file-delete tool dune died at
874.6s with verbatim *"Error: Multiple rules generated for
_build/default/theories/Dfa.vo ... - file present in source tree ... Hint: rm
-f theories/Dfa.vo"* — **after every theorem including prod23_nonempty had been
proven interactively** (857.5s). rep3: with its interactive loop broken by
load-path failures, it wrote Main.v's key proof blind at 495.3s
(`Proof. vm_compute. reflexivity. Qed.`) and learned it was wrong only from
dune at 859.6s (*"Unable to unify \"true\" with ..."*) — the exact same
vm_compute wall that killed base rep1, never interactively checked.
triadic__rep1: the same .vo-pollution mechanism on triadic — verdict quotes
*"Multiple rules generated for _build/default/theories/Props.vo"*.

**B3 — evolve repackaging timeout (1: af3_evolve/prodauto__rep0).** After
~250s of load-path friction (recurring *"Unable to locate library Dfa with
prefix TaskLib"* through ~570s despite dune exit 0, including reading the
binary `Dfa.vo`), it proved **all the mathematics** in a flat Scratch.v —
verbatim *"BUILD OK: 11 proof block(s), no holes."* at t=823.8s — and was
killed mid-repackaging into the required six-module layout; delivered Ops.v
line 2 reads `Require Import Dfa.` (not `From TaskLib`).

**B4 — dune '(mode vos)' brick (1: af3_evolve_r1/triadic__rep2).** Wrote
`theories/dune` 6x including a `(mode vos)` speed hack; verdict build layer
quotes `(mode vos)` and *"Error: File unavailable:
.../mathcomp/algebra/all_algebra.vos"*; last tool call was `read_file` on the
binary `theories/Props.vo`; only 9 sentences committed all session — the sole
evolve-family triadic attempt not graded forbidden_token.

### 2.5 Class N — nothing built (no_vo_built), 2 attempts

**Mechanism: extended-thinking burn consumed the entire wall.** af3_base
{prodauto__rep0, triadic__rep2}: both made exactly **1 tool call**
(`list_dir`, returning `'(empty workspace)'` / an empty dir), wrote zero files,
and ended in an unbroken run of `system subtype='thinking_tokens'` events (final
unfinished runs reaching ~24.6k and ~21.4k estimated tokens; ~88.4k/~85.2k
total across each attempt's episodes).

**Cross-cutting driver (base-wide).** First tool call on triadic at
428s/612s/3s/126s across base reps; peak thinking-token episodes
39.7k/58.1k/63.8k/57.3k on triadic and 57-64k on prodauto, vs 11.6-34.6k in
evolve arms. Median gap between 1st and 2nd tool result: **379s in base failed
vs 32s in base solved**; the largest gaps sit between `list_dir` and the first
`write_file` (379s/617s/644s in ledger__rep1, triadic__rep3, prodauto__rep3).
Base's failure mode is thinking-burn plus blind batch-writing, not build
inability — base *solved* attempts do **more** tool calls than failed ones
(26.3 vs 14.6, dune_builds 9.6 vs 4.2).

### 2.6 Cross-cutting: infrastructure churn (~6 attempts lose decisive time off the critical path)

Not a gate class but a time sink inside S/B failures (all six churn cases below
are triadic attempts, per the triadic-wall pass): r1/triadic__rep2 (6 dune
writes, `(mode vos)` brick — Class B4); r3/triadic__rep1 (15 `theories/dune`
writes + 16 dune_builds, 4 failed); c3/triadic__rep0 (9 dune writes + 1
_CoqProject); c3/triadic__rep2 (12 dune writes, both theorems left Admitted in
Scratch.v, Fixed.v/Shrink.v never created); sota/triadic__rep1 (verdict:
*"Multiple rules generated for _build/default/theories/Props.vo ... file
present in source tree"*) and sota/triadic__rep3 (wrote Props.vo/.vok/.vos via
write_file; first 3 dune_builds failed). The same .vo-pollution mechanism
recurs on prodauto in sota (Class B2). Successful dune_builds take 5.0-16.1s
(failures ~0.1s) — builds are cheap; the churn is pure navigation loss.

### 2.7 Cross-cutting: the triadic wall (0/24 across all six arms)

Triadic is the single largest failure mass (24/24, all at wall_s=900) and its
mechanism is **budget, not insight**:

- **Definitions are never the problem**: 23/24 final workspaces have Props.v
  fully Qed'd (chorus_sorted + mem_chorus); the one exception (base rep2) made
  1 tool call total.
- **The key insight is found**: the cofactor-window argument for tstep_fixed
  (divisor of 6m in [m,6m) has cofactor 2..6; c=4 barred by parity, c=5 by
  5-nondivisibility, leaving m,2m,3m) is independently discovered and **fully
  formalized in 8/16 evolve-family attempts** (e.g. evolve rep0's gap12 proof
  literally contains `have Heven : m = 2 * (d - m) by lia. move: Hodd; rewrite
  Heven oddM`), stated-but-unlanded in 3 more (incl. sota rep3's `topS`
  restatement of the reference's high_chorus, 5/5 failing rocq_check calls).
  The shrink-side decomposition (odd cofactor >= 3, antitone, hence 3/5/7
  bounds) is fully formalized in 3 evolve-family attempts and correctly stated
  in 4 more (incl. base rep0, which stalled on a trivial `odd (n %/ d)`
  subgoal discharged by `admit.`).
- **One theorem per 900s**: tstep_fixed machine-verified in-session in 8/16
  evolve-family attempts, tstep_shrink_odd in 3/16 — **never both** (0/24).
  Each theorem costs ~400-700s. At least 5 attempts were killed within ~7-52s
  of verifying their first theorem (evolve rep1 BUILD OK at t=879s — 21s before
  the wall; c3 rep3 at t=893s — 7s; r3 rep0 PROOF COMPLETE at 848s, killed
  during the confirming build; r3 rep2 BUILD OK at 872s; r1 rep0 at 526s then
  194 committed sentences deep into theorem two at kill).
- **Arm contrast is stark**: interactive sentences committed 9-194 per
  evolve-family attempt vs exactly 0 in all base/sota attempts (no `step` tool
  there); base never wrote Fixed.v in any rep; sota died iterating failing
  whole-proof `rocq_check` submissions with both theorems still `Proof.
  Admitted.` stubs (rep0) or Fixed.v absent (reps 1-3).
- **Rung arms do not beat plain evolve on triadic content**: verified-theorem
  tallies — plain evolve 4 (3x Fixed + 1x Shrink), r1 3, r3 2, c3 2 — while r3
  and c3 add detours (r3 rep3: Foo.v/Bar.v plus Scratch.v with both theorems
  Admitted; c3 rep0: 5 Qed blocks in Scratch.v never transferred to Fixed.v,
  whose 5 lemmas are all Admitted).

### 2.8 Cross-cutting: tool-repertoire signatures (what failure looks like per arm)

Recounted over all 60 base/evolve/sota transcripts:

- **Repertoires**: base = pure write/dune loop, 19.9 calls/attempt; evolve adds
  the interactive prover (62.8 calls/att; step 18.2, open 8.8, try 5.9, build
  5.5); sota adds a query/check-heavy prover (78.8 calls/att; query 17.3,
  check 15.1).
- **Solved vs failed inverts by arm**: base solved does MORE (26.3 vs 14.6
  calls); evolve/sota failed do more calls but fewer productive builds
  (build cadence dies out late in failures: evolve failed 15→4 across attempt
  halves, sota failed 29→14; denser-late marks success).
- **3-gram signatures**: base solved = `build>write>build` repair loop (54);
  base failed = `write>write>write` batch-dumping (42); evolve solved =
  `open>step>...>auto_close` pipeline; evolve failed = `step>step>step` grind
  at 13.3/att vs 3.9 solved + `try>open>try` thrash; sota failed =
  `query>query>query` read-only churn at 2.8x the solved rate (14.3 vs
  5.1/att) and `check^3` at 10.3 vs 2.9.
- **is_error concentrates in failures**: evolve 29 is_error results, ALL in
  failed attempts (0/760 solved calls), 23/29 being `rocq__open` "theorem not
  found" file/prover desyncs. Base has 0.0% is_error — dune failures come back
  in-band (59/131 build results contain Error text; the rate does NOT differ
  between base solved 45% and failed 44%).
- **verify is a near-perfect solve marker**: verify calls in solved vs failed —
  base 11/1, evolve 13/1, sota 28/1; 74/74 solved attempts called verify.

---

## 3. The prodauto mechanism (causal centerpiece)

Prodauto separates the arms like no other task (evolve-family 10/24 vs base+sota
0/8) and the mining recovered the full causal chain. The task is gated by **two
traps plus a noise source**, and the arm outcome is determined by **the price of
converting each trap-hit into a fix**.

**The traps.**

1. *Script overshoot*: a tactic line left after `//=` already closed the goal →
   *"No such goal."* Killed base rep2 (Empty.v:17, Lang.v:9) and rep3
   (Lang.v:15).
2. *The vm_compute wall*: `Empty.nonemptyb prod23` does not vm_compute to a
   literal (the stuck term contains `match idP with | @ReflectT _ x1 => Some
   (Ordinal (n:=3) (m:=1) x1)`), so `by vm_compute.` dies with *"No applicable
   tactic."* / an `Unable to unify` error. Killed base rep1 (in-file proof
   falsified by its final dune_build at 888.6s) and sota rep3 (blind-written at
   495.3s, falsified at 859.6s).
3. *Warning noise*: mathcomp deprecation spam fills the 6.1KB result clip with
   zero Error lines on exit 1 (base rep1/rep2), costing extra dune cycles and
   `-w -all` detours.

**Evolve prices a trap-hit at seconds** (why it solves 3/4):

- Overshoot: rep1's check at t=193.7s returned verbatim *"2 sentence(s)
  committed, then ERROR at `by rewrite IH.`: No such goal. ... you are now AT
  that point in the proof — repair from here"*; 2.4s later the state call read
  *"committed proof: Proof. elim: w sa sb => [|b w IH] sa sb //=. Qed.
  PROOF COMPLETE."* — the overshoot auto-resolved by prefix-commit. rep2 got
  the per-theorem hole report (*"BUILD: 3 block(s) OK, 1 hole(s): -
  run_dprod: proof fails at `by rewrite IH.`: No such goal."*) and fixed it in
  ~22s.
- vm_compute wall: rep1's `try` (t=450.6s, 3.1s after the prior call) tested
  the failing tactic and the fix in one call: *"[1] `by vm_compute.` — error
  ... [2] `apply/Empty.nonemptyP. exists [::]. by vm_compute.` — OK, no goals
  left — finish with `Qed.` << COMMITTED"*. All four evolve reps (and r3 rep1,
  identical route at 573.3s) landed the nonemptyP-witness proof.
- Misapplication: rep1's step error (*"The term \"Hr\" has type \"is_true
  (connect ...)\" while it is expected to have type \"finType\""*) was repaired
  7.7s later because the session stayed alive at the failure point; in-session
  Search delivered card_uniqP/max_card/size_scanl in three calls.
- First compiler/prover feedback on .v content: **14.8s / 125.2s / 175.8s**
  across evolve solvers. Evolve rep1's whole solve: {open:11, step:24,
  check:6, build:5} in 499.7s.

**Base prices a trap-hit at one ~600s thinking episode plus full dune cycles**
(why it solves 0/4): every base rep burned one ~57-64k-token thinking episode
(~550-650s) designing the six-file development in-head before any compiler
feedback; first feedback at 603.7s/709.6s or **never** (rep0: one list_dir;
rep3: 6 writes, zero dune_builds). Each trap then surfaced with no wall left.

**Sota had the tools but paid a plumbing tax plus a self-inflicted breaker**
(why it solves 0/4 despite proving the theorems): its pet-based session could
not see the dune-built TaskLib out of the box (*"Coq: Dfa.dfa not a defined
object."* / *"Unknown Module Dfa"*), and every rep burned 100-430s
rediscovering a workaround (rep0 `_CoqProject` at 730.2s; rep1 `-R theories
TaskLib` + keep_vo recompiles, working at 475.5s; rep2 inlined the dfa Record
into its preamble at 798.0s; rep3 never fixed it and proved surrogate lemmas).
Where the session worked, sota converted theorems **at the same speed as
evolve** (rep1: run_prod 487.9s → accepts_compl 498.5s, all proof_finished;
prod23_nonempty at 857.5s with the *identical* witness script) — but rep1's
keep_vo workaround then poisoned the deliverable (Class B2: *"Multiple rules
generated"*, no delete tool, dead at 875s with everything proven), rep0/rep2
ran out of wall with Pump.v missing, and rep3 died blind on the vm_compute
wall. The single decisive interface difference: evolve's `open` auto-discovers
dune load paths (README.md:156) and worked on first use at 191.5s.

**Replication**: af3_evolve_r3 prodauto 3/4 with the same open/step/try/build
pattern and the identical nonemptyP witness route.

---

## 4. Implications for future rungs

Each implication cites its evidence class (§) and the prior rung it explains or
contradicts (A-numbers from `docs/ASSUMPTIONS.md`).

1. **A64 (R1, scaffold-visibility in build{}) — verdict CONFIRMED, premise now
   proven wrong at higher resolution.** §2.1: the no-admit rule was in-band
   from turn 0 in all six configs; 32/74 solved attempts used the same scaffold
   strategy and cleaned it when time allowed; the 5 attempts that *received*
   explicit VERIFY FAILED file lists still died dirty, grinding new proof work
   at t=886-899s. Information was never the gap — time was. R1's revert
   ("visibility does not buy time") is the correct causal read.

2. **A64's class-movement narrative was confounded by the gate artifact.**
   The A64 verdict recorded r1 "probes 1→3" as a regression; §2.2 shows all
   three r1 probes_failed rows are the `vo[0].parent` false negative on
   provably-correct work (r1 corrected: 12→15, tying r3). The revert stands
   under the frozen |delta|>=3 rule (corrected r1 15 vs corrected evolve 14),
   but no probes regression is attributable to the R1 change.

3. **A65 (R3, open-side finisher fusion) — below-bar result explained by the
   size of the deficit.** §2.7: on triadic each theorem costs ~400-700s and no
   attempt ever finished both; saving one model round-trip per open (~6/att,
   seconds each) is two orders of magnitude short of the missing ~400-700s.
   r3's triadic content (2 theorem verifications) did not exceed plain
   evolve's (4). The A65 revert is consistent; the wall deficit is not
   addressable by exchange-density rungs.

4. **A69 (C3, compact-render default) — the measured token inversion has a
   qualitative face in the failure data.** §2.6/§2.7: c3 is the only arm with
   6 forbidden_token failures, and its distinctive failures are
   context-management pathologies — c3/triadic__rep0 with 9 dune rewrites and
   5 Qed blocks in Scratch.v never transferred to the Admitted Fixed.v,
   c3/triadic__rep2 with 12 dune rewrites and Fixed.v/Shrink.v never created,
   c3/prodauto__rep3 with the development living in Scratch.v (6 Qed) while
   Dfa.v/Ops.v have 0. Consistent with A69's mechanism
   (withheld context bought back with more round-trips); the revert stands.

5. **A70 (fair three-way) — one headline number weakens under the gate fix.**
   §2.2 score impact: corrected scores are base 10, evolve 14, sota 12. Evolve
   vs base +4 (signal) survives; **sota vs base becomes +2, below the frozen
   |delta|>=3 bar** — A70's "both MCPs beat baseline with signal" would read
   "evolve with signal, sota within noise" after fixing
   `autoform_gate.py:101`. (Caveat: assumes the unobserved audit layer passes
   for the 6 artifact attempts.) The evolve-vs-sota statistical tie is
   unchanged (14 vs 12).

6. **A70's surviving evolve edge (prodauto 3/4 vs 0/4) is an integration
   property, not prover power.** §3: sota converted the same theorems at the
   same speed once its session worked; its 0/4 decomposes into a 100-430s
   load-path tax, a keep_vo pollution breaker with no delete tool, and one
   blind write. Rung-shaped fixes with direct evidence: load-path
   auto-discovery for the sota-style server (evolve's README.md:156 behavior),
   and a file-delete (or no-keep_vo-default) escape hatch. Neither is a
   channel nudge; both are mechanical — the A64 lesson generalizes.

7. **The scaffold class needs a grader-side or arena-side lever, not more
   in-band text.** §2.1: no remaining-wall-time signal exists
   (`harness/run_autoform.py:128` enforces the wall only via
   `p.wait(timeout=...)`); all 22 deaths were active-work kills. Candidate
   levers, each mechanical: (a) an in-band remaining-time signal, (b) an
   end-of-wall cleanup grace (the 3 clean-disk wall-kill solves show grading
   disk-at-kill already rewards agents whose fill happens to complete),
   (c) reordering layers so forbidden_token does not mask near-complete work
   (§1, fact 2). Explains the residual mass A68 flagged as
   "difficulty/time-bound — no channel rung targets it credibly".

8. **Triadic needs task-budget honesty (or a split), not capability work.**
   §2.7: 0/24 at 900s across every arm; the mathematical insights are found
   and formalized one-at-a-time; >=5 attempts died within 7-52s of verifying
   theorem one. At the observed ~400-700s/theorem rate, a two-theorem budget
   is ~1200-1500s minimum for the current agents. Any future rung measured on
   triadic at 900s measures the wall, not the rung (cf. A65/A69 triadic 0/4
   in every arm — zero discriminating power).

9. **Fix the gate before the next comparison** (§2.2): one-line change,
   `theory_dir` from the dune file declaring `(name TaskLib)`. 5 of the 6
   artifact hits are in evolve-family arms because those agents adopt the
   self-test-theory layout — the artifact systematically penalizes exactly the
   self-verification behavior the arena should reward, and it contaminated two
   rung comparisons (A64's r1, A70's sota-vs-base margin).

10. **Base's arm score is substantially an extended-thinking-allocation story**
    (§2.5, §3): first tool call at 126-612s on triadic, ~600s in-head design
    episodes on prodauto, two attempts spending the whole wall on one
    list_dir. Any base-arm comparison at this wall partly measures
    thinking-budget discipline, not the absence of prover tools. Cross-check
    for report writing: the five-hour rate_limit_event appears in **every**
    arm's sessions (status allowed) — it is not a base-specific confound.

---

## 5. Report-ready numbers (with provenance)

All numbers recomputed by verifiers from the named artifacts; paths relative to
`logs/autoform/` unless noted.

### 5.1 Arm scores

| Number | Value | Provenance |
|---|---|---|
| Solved/20: base, evolve, sota, r1, r3, c3 | 9, 13, 12, 12, 15, 13 | each run's `results.jsonl` |
| Corrected for gate artifact (§2.2, audit-layer caveat) | 10, 14, 12, 15, 15, 14 | results.jsonl + 6 artifact verdicts/workspaces |
| Per-task solves base | F4 G3 L2 P0 T0 | af3_base/results.jsonl |
| Per-task solves evolve | F3 G4 L3 P3 T0 | af3_evolve/results.jsonl |
| Per-task solves sota | F4 G4 L4 P0 T0 | af3_sota/results.jsonl |
| Per-task solves r1 / r3 / c3 | F3G3L4P2T0 / F4G4L4P3T0 / F3G4L4P2T0 | respective results.jsonl |
| Failure reasons base (11) | build x5, probes x3, no_vo x2, forbidden x1 | af3_base/results.jsonl |
| Failure reasons evolve (7) | forbidden x5, probes x1, build x1 | af3_evolve/results.jsonl |
| Failure reasons sota (8) | probes x4, build x3, forbidden x1 | af3_sota/results.jsonl |
| Failure reasons r1 (8) / r3 (5) / c3 (7) | forb4 probes3 build1 / forb5 / forb6 probes1 | respective results.jsonl |

### 5.2 Class S (scaffold-at-wall)

| Number | Value | Provenance |
|---|---|---|
| forbidden_token failures, total / by task | 22; triadic 17, prodauto 3, ledger 1, gauges 1 | all results.jsonl + verdict.json |
| Token split | Admitted x20, admit x2 | verdict layers.forbidden (admit: af3_base/triadic__rep0, c3/prodauto__rep3) |
| Flagged files | Shrink.v x9, Fixed.v x6, Scratch.v x5, Main.v x1, Empty.v x1 | verdict.json x22 |
| Wall-killed, no submission | 22/22 (wall_s 900.0/900.1, num_turns None, result_text '') | results.jsonl |
| Last tool call at t=868-899s | 21/22 (exception: af3_base/triadic__rep0, dune_build@720s) | server.jsonl x22 |
| Flagged-file token intro <= ~6.5 min | 13/22 (63s/75s/101s/195-381s; write seq 7-10) | server.jsonl write logs |
| Any-.v token intro <= 380s | 18/22 (earliest Props.v t=10s, r3/triadic__rep1) | server.jsonl |
| Verify called / VERIFY FAILED received | 7/22 called; 5/22 received FAILED lists; all 5 still died dirty | server.jsonl (c3/t0 465s; r3/t1 146+391s; r3/t3 502/545/727s; r3/prodauto0 655s; evolve/ledger3 234+583s) |
| Solved attempts using Admitted scaffolds | 32/74 | all solved server.jsonl (comment-stripped word-boundary scan) |
| Solved attempts calling verify | 74/74 | all solved server.jsonl |
| Clean-disk wall-kill solves | 3 (evolve/prodauto__rep3, sota/ledger__rep1, __rep3) | results.jsonl + workspaces |
| Layer ranks (forbidden below build) | forbidden_token 0 < build_failed/no_vo_built 1 | harness/run_autoform.py:41-43 |

### 5.3 Probes class (12 = 6 artifact + 6 timeout)

| Number | Value | Provenance |
|---|---|---|
| probes_failed total / per run | 12; base 3, evolve 1, sota 4, r1 3, c3 1, r3 0 | results.jsonl |
| All 12 fail at probes.v line 1 Require; layers.build='ok' in all 12 | 12/12 | verdict.json x12 |
| Byte-identical probes.v copy in 2nd theory | 6/6 artifact cases (diff -q clean vs data/autoform/<task>/probes.v) | workspaces of the 6 (§2.2 list) |
| Multi-dir .vo workspaces across all 120 attempts | exactly 6 = the 6 artifact cases; 0 among 74 solved | rescan of all `workspace/_build/default` |
| Root cause | `vo[0].parent` over unordered rglob | harness/autoform_gate.py:97-101 |
| Artifact attempts finishing under cap claiming success | 5/6 (654.8s/20t; 405.1s/57t; 782.4s/81t; 802.9s/50t; 790.3s/58t) | results.jsonl rows |
| Timeout-6: delivered vs missing modules | triadic: Props+Step only (x4); prodauto: Dfa/Ops/Lang/Empty, no Pump/Main (x2) | workspaces |
| Paraphrase-induced probe failures | 0/12 (100% of referenced names defined in delivered modules) | probes.v vs workspace headers |
| Wrong-math / statement-shape probe failures | 0/12 | verdict.json x12 (no pin ever the failing layer) |

### 5.4 Triadic (0/24)

| Number | Value | Provenance |
|---|---|---|
| Solved / wall-killed | 0/24; 24/24 at wall_s=900.0/900.1 | all results.jsonl |
| Props.v fully Qed'd | 23/24 (exception af3_base/triadic__rep2: 1 tool call, no files) | workspaces + af3_base transcript |
| tstep_fixed verified in-session | 8/16 evolve-family (evolve r0/r1/r2, r1 rep1, r1 rep3*, r3 rep0*, r3 rep2, c3 rep1; *=checker/step PROOF COMPLETE) — 0/4 base, 0/4 sota | server.jsonl BUILD OK / PROOF COMPLETE events |
| tstep_shrink_odd verified in-session | 3/16 (evolve rep3 t=789s, r1 rep0 t=526s, c3 rep3 t=893s) — 0 base/sota | server.jsonl |
| Both theorems verified | 0/24 | server.jsonl (all attempts checked) |
| Cofactor-window insight (tstep_fixed) | formalized 8/16 evolve-family; stated 3 more (incl. sota rep3 topS, 5/5 checks failed); base 0 | workspaces + transcripts |
| Shrink decomposition insight | formalized 3 (evolve rep3, r1 rep0, c3 rep3); stated 4 more incl. base rep0 | workspaces |
| Killed within 7-52s of first theorem verification | >=5 attempts (evolve rep1 21s; c3 rep3 7s; r3 rep0 ~52s; r3 rep2 ~28s; r1 rep0 continued 358s into thm 2) | server.jsonl timestamps |
| Sentences committed, evolve-family | 9 (r1 rep2) to 194 (r1 rep0); all 16 > 0 | server.jsonl 'ok: N sentence(s) committed' sums |
| Sentences committed, base + sota | 0 in all 8 (no step tool used) | server.jsonl |
| Evolve-family scaffold write times (Props/Fixed/Shrink stubs) | 192-283s window (e.g. evolve rep0: 259.2/261.4/262.1s) | server.jsonl write logs |
| base first tool call (triadic reps 0-3) | 428s / 612s / 3s / 126s | server.jsonl |
| base peak thinking episodes (triadic) | 39.7k / 58.1k / 63.8k / 57.3k est. tokens | transcript thinking_tokens events |
| evolve-family peak thinking range | 11.55k (r3 rep1) - 34.6k (r3 rep2); sota rep3 34.45k | transcripts |
| Verified-theorem tally per arm | evolve 4, r1 3, r3 2, c3 2 | server.jsonl events |

### 5.5 Prodauto (evolve-family 10/24; base 0/4, sota 0/4)

| Number | Value | Provenance |
|---|---|---|
| base thinking episode before first content write | ~550-650s (rep1 634s gap; rep2 557.7s; rep3 643.7s; rep0 one list_dir only); max episodes 62.65-63.9k tokens in 3/4 reps | af3_base prodauto transcripts |
| base dune_builds per rep (0-3) | 0 / 4 / 5 / 0 — reps 0 and 3 got zero compiler feedback | server.jsonl |
| First compiler/prover feedback on .v content | evolve 14.8/125.2/175.8s; sota 93.7/123.1/209.3/348.5-374.0s; base 603.7/709.6s or never | server.jsonl per rep |
| Overshoot fix cost, evolve | 2.4s (rep1 check→state) and ~22s (rep2 build→step) | af3_evolve transcripts, t=193.7-196.1s / 148.1-170.4s |
| vm_compute-wall fix cost, evolve | one try call, 3.1s after prior call (rep1 t=450.6s) | af3_evolve/prodauto__rep1 |
| sota load-path workaround tax | ~100-430s per rep (rep0 566.8→739.0s; rep1 266.8→475.5s; rep2 inline Record at 798.0s; rep3 never) | af3_sota transcripts |
| sota rep1 death | all 6 files compiled by 872.2s, prod23_nonempty proven 857.5s, dune 'Multiple rules generated' 874.6s (= its verdict) | af3_sota/prodauto__rep1 |
| sota rep3 blind write → falsification gap | Main.v written 495.3s, falsified by dune 859.6s | af3_sota/prodauto__rep3 |
| evolve rep0 (its 1 fail) | 'BUILD OK: 11 proof block(s), no holes.' at 823.8s in Scratch.v; killed repackaging; Ops.v line 2 `Require Import Dfa.` | af3_evolve/prodauto__rep0 |
| evolve solve profile (rep1) | {open 11, step 24, check 6, build 5} in 499.7s | transcript recount |
| sota rep1 profile | {start 10, check 22, query 20, compile_file 11}, ~66 rocq calls in ~880s | transcript recount |
| r3 replication | prodauto 3/4, identical nonemptyP witness committed at 573.3s | af3_evolve_r3/prodauto__rep1 |

### 5.6 Tool profiles and cadence (base/evolve/sota, 60 attempts)

| Number | Value | Provenance |
|---|---|---|
| Calls/attempt | base 19.9, evolve 62.8, sota 78.8 | all 60 transcripts, tool_use recount |
| Solved vs failed calls/att | base 26.3/14.6; evolve 58.5/70.7; sota 76.6/82.1 | transcripts + results.jsonl |
| dune_builds/att solved vs failed | base 9.6/4.2; evolve 3.5/2.7; sota 5.9/5.4 | transcripts |
| Build-cadence halves, failed arms | evolve 15→4; sota 29→14 (rarer late = failure marker) | transcripts |
| Median inter-result gap | base 7.5s (7.0 solved / 8.6 failed); evolve 4.3 (3.9/4.9); sota 4.9 (4.9/4.9) | user-event timestamps |
| Mean gap failed/solved | base 40.7/16.9; evolve 11.1/7.1; sota 10.4/7.6 | same |
| base 1st→2nd result gap, median | solved 32s vs failed 379s (max gaps 379/617/644s before first write) | af3_base transcripts |
| is_error fraction | base 0/398; evolve 0/760 solved, 29/495 failed (23 = open desyncs); sota 2/919 solved, 7/657 failed | transcripts |
| base dune results with Error text | 59/131 (solved 45%, failed 44% — no separation) | transcripts |
| sota in-band build-failure separation | failed 19/43=44% vs solved 12/71=17% | transcripts |
| Top failed 3-grams | base write^3 42; evolve step^3 93 (13.3/att vs 3.9); sota query^3 114 (14.3/att, 2.8x solved) | transcripts |
| verify calls solved/failed | base 11/1, evolve 13/1, sota 28/1 | transcripts |

### 5.7 Infrastructure churn

| Number | Value | Provenance |
|---|---|---|
| r1/triadic__rep2 | 6 theories/dune writes incl. '(mode vos)'; verdict quotes 'File unavailable: .../all_algebra.vos'; 9 sentences all session | server.jsonl + verdict.json |
| r3/triadic__rep1 | 15 dune writes + 16 dune_builds (4 failed) | server.jsonl |
| c3/triadic__rep0 / rep2 | 9 / 12 theories/dune writes; rep2 never created Fixed.v/Shrink.v, theorems Admitted in Scratch.v | server.jsonl + workspace |
| sota .vo pollution | triadic__rep1 'Multiple rules generated ... Props.vo' (verdict); triadic__rep3 wrote Props.vo/.vok/.vos via write_file, 3 failed builds; prodauto__rep1 same on Dfa.vo (fatal, §3) | verdict + server.jsonl |
| dune_build cost | success 5.0-16.1s; failure ~0.1s | server.jsonl durations |

### 5.8 Arena/context facts

| Number | Value | Provenance |
|---|---|---|
| No in-band wall-time signal | wall enforced only by `p.wait(timeout=900)` | harness/run_autoform.py:128 |
| Task-prompt no-admit rule, verbatim rule (4) | present in all six configs | configs/af3_*.json |
| VERIFY FAILED strings | 'fix before finishing' (session server), 'fix before DONE' (files server) | src/session_server/rocq_agent_session.ml:1957, src/files_server/rocq_agent_files.ml:241 |
| Evolve load-path auto-discovery | documented behavior; first open worked at 191.5s (prodauto rep1) | README.md:156 + transcript |
| five_hour rate_limit_event (status allowed) | present in every arm's sessions — not a base-specific confound | all transcripts |
| Ledger figures (not re-mined here): evolve $40.75 tot / $3.13/solved / 570s; r1 $46.13/$3.84/611s; r3 $41.45/$2.76/564s; sota $5.73/solved / 717s | as recorded | docs/ASSUMPTIONS.md A71/A70 |

---

*Compiled 2026-07 from five verified mining passes (triadic-wall,
prodauto-mechanism, scaffold-class, tool-profiles, probes-failures) over
logs/autoform/af3_*. Every quoted string was re-located verbatim in the cited
artifact by an independent verifier; numeric corrections applied by the miners'
verifiers are reflected throughout.*
