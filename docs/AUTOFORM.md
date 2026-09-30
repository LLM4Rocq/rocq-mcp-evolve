# Phase 2 — evaluating rocq-mcp-evolve on autoformalization tasks

Phase 1 measured *proving* through an interface: statement given, prove it.
Realistic use is harder: given a MATHEMATICAL SPEC in natural language,
build a full Rocq project — definitions, layered files, a build system —
and prove the stated theorems about your own definitions. Phase 2 is a
self-contained SIDE EVALUATION of the shipped server in that setting: a
novel machine-gradable dataset (`data/autoform/`), a harness
(`harness/run_autoform.py` + `autoform_gate.py` + `autoform_dashboard.py`),
and A/B arms. It is an evaluation, not a tool-evolution ladder;
orchestration remains harness scaffolding, never a product feature.

## Results at a glance

Gate (all protocols): fresh isolated `dune build` + open-book probes +
assumption audit + forbidden-token scan — no tool output is ever trusted
for grading. The evaluation protocol itself evolved (guided w2 → af2 →
the final af3 arena) and that evolution produced the project's central
methodological findings; every arena's numbers are labeled with its
protocol and never pooled.

**Final arena** (af3, pre-registered A63: no system prompt, wall-only
900 s budget, 5 tasks × 4 reps, corrected grading A75; latency over solved
attempts and kill rates per A78):

| arm | solved | latency (solved) | kill rate | $/solved |
|---|---|---|---|---|
| baseline (files + dune, no MCP) | 10/20 | 608 s | 10/20 | $2.47 |
| **+ rocq-mcp-evolve** | **14/20** (+4, criterion met) | **429 s** | **7/20** | $2.91 |
| + rocq-mcp (sibling, fair) | 12/20 (+2, within noise) | 595 s | 10/20 | $5.73 |

Replication: four independent evolve-family arms (one reverted variant
each) scored 14, 15, 15, 14 vs the same baseline — pooled 58/80 = 72.5%
vs 50%, task-clustered p = 0.006 (A79). Frontier tier (opus, 2 reps,
directional): baseline 3/10, evolve 6/10, sibling 6/10 — the unassisted
baseline collapses; both prover servers double it (A73).

Historical protocols (numbers correct for their own arenas; NOT comparable
across protocols — A62/A81): the guided w2 era measured evolve 7/8 vs
base 5/8 with per-arm system prompts; the af2 arena (no prompts but a
40-turn cap = a covert tool-call tax) measured evolve −4 vs baseline with
the same binaries that score +4 under the wall-only arena — the project's
central evaluation-artifact finding. Full chronology below.

Findings (full trail: A39–A86): the prover-tool effect is real,
replicated, and arena-sensitive. Under the fair arena evolve meets the
pre-registered +3 criterion (+4) with a four-arm replication (p = 0.006);
the sibling server is statistically indistinguishable from evolve on
accuracy, while evolve keeps latency (−43% paired), kill-rate, cost
(2× vs sibling), and the hardest 6-file task (prodauto 3/4 vs 1/8 pooled control at
sonnet — the one gap that never flipped under any sonnet arena). Earlier
verdicts — the guided-era win, the af2 "guidance-conditional" null, and
every "sibling loses" headline — were arena- or grading-confounded and
are retained below as the honest chronology (A54, A58, A62, A70, A75).
Multi-agent teams add no value when solo is strong (A56). Triadic is
unsolved in 51 attempts across every arm, tier, and model family — the
dataset's headroom. All 40 post-correction failures are process failures; zero
wrong mathematics (atlas; 6 further apparent failures were gate
false-negatives on correct work, fixed in A75).

Product changes shipped out of phase 2 (both general, in `src/`):
1. **Relative-path resolution** for `open`/`build` (A42/A48) — open-success
   8.5% → 47% on project files.
2. **Import-echo on proof completion** (A59) — the session preloads tactic
   modules, so found proofs could use tactics the agent's file did not
   import; the completion message now echoes the exact `Require` lines
   (this cost the evolve arm its only dropped task before the fix).

Everything else here is measurement scaffolding: `src/files_server/` (the
common file sidecar all arms share; not shipped as a product library) and
the Python under `harness/`.

## Task format (`data/autoform/<task>/`)

- `spec.md` — the natural-language mathematical specification. All tasks
  require `theories/dune` to declare `(theories Stdlib)` (dune isolates the
  loadpath; without it `From Stdlib Require` fails). Lists the
  REQUIRED logical names (`TaskLib.<Module>.<name>`) with their informal
  meaning, and the required project shape (dune project, logical name
  `TaskLib`, ≥ 3 `.v` files with a genuine dependency chain).
- `probes.v` — the grader's teeth, OPEN BOOK (the agent may read it; it is
  the acceptance test, like a test suite in software tasks). It compiles
  against the agent's built project and checks:
  1. **semantic pins**: concrete instances computed with `vm_compute`
     (e.g. `sort [3;1;2] = [1;2;3]`) — a wrong formalization of the
     definitions fails here no matter how many theorems were "proved";
  2. **statement shapes**: `Theorem probe_X : <spec statement> . Proof.
     exact TaskLib.thm_X. Qed.` — pins the exact logical form of each
     required theorem (up to the agent's own definitions, which the
     semantic pins constrain);
  3. `Print Assumptions` on every probe → must be closed, except exactly
     the boolp classical trio (prop-ext, funext-dep, constructive
     indefinite description) that mathcomp-analysis itself is built on.

## Grading (`harness/autoform_gate.py`)

A submission = a directory. Gate layers:
1. `dune build` of the submission succeeds (fresh `_build`).
2. `probes.v` compiles against the built project (`-Q _build/default/… TaskLib`).
3. Assumption audit: a generated `probe_assumptions.v` prints assumptions
   of every probe; any axiom → reject.
4. Forbidden-token scan over ALL submission `.v` files (comment-stripped):
   admit/Admitted/Axiom/Parameter/Hypothesis/Variable at top level.
Score per task: pass/fail + per-probe breakdown.

## Well-posedness rule

A task enters the dataset only with a REFERENCE SOLUTION that passes its
own probes through the gate. References live in `data/autoform/<task>/
reference/` (excluded from agent context at eval time).

## Dataset (current — `data/autoform/`)

Five novel, contamination-controlled tasks (concepts renamed and composed
unusually; no task states a textbook theorem under its textbook name; every
file requires a heavy mathcomp prelude so rebuilds are expensive), each
with a gate-validated reference solution (well-posedness rule):

| task | mathematical content (novel framing) | files |
|---|---|---|
| frugal | bounded min-plus ("tropical") cost algebra on option nat + 2×2 matrix product associativity | 4 |
| gauges | real-interval "gauges" over `realType`; op soundness + width transport (mathcomp-analysis) | 4 |
| ledger | append-only (account, delta) ledger over ssrint; replay/checkpoint equivalence + a no-teleport bound | 4 |
| prodauto | DFAs over a finType; product construction, language-intersection, emptiness via reachability, pumping-light pigeonhole | 6 |
| triadic | divisor-sum dynamical system (derived from a 2025 olympiad problem, renamed beyond retrieval); fixed-point + shrink theorems | 4 |

### Wave-1 pilot dataset (DISCARDED — contamination)

The first five tasks (monoid homs, insertion sort, Brzozowski derivatives,
graph reachability, binomial identities) stated classic textbook material
under its textbook names; training-data familiarity was certain, so their
ABSOLUTE numbers are memorization-inflated and the task dirs were removed.
The pilot's A/B deltas and its methodological lessons (gate design, probe
style, path-resolution fix) carried forward; its numbers appear below only
as the historical record.

## Chronology — wave-1 pilot results (discarded dataset; trail A39–A50)

Conditions share the file-workspace sidecar (write/read/list/dune_build);
tools arms add the rocq MCP; verify adds the gate-mirror + verify-before-
DONE workflow. Numbers are CORRECTED (all regrades documented: A43
candidate.v artifact, A46 Unset false positive).

| arm (policy, reps) | solved | mean layer | note |
|---|---|---|---|
| base (haiku, 2) | 1/14 | 1.21 | write/rebuild loop, ~78 calls/attempt (A41) |
| tools (haiku, 2) | 2/14 | 1.36 | open success 8.5% — path friction (A42) |
| tools+pathfix (haiku, 2) | 3/14 | 1.43 | open success 47%; still build-bound (A50) |
| base (sonnet, 1) | 6/7 | 3.57 | fails only mca_limits |
| plan-first (sonnet, 1) | 6/7 | 3.43 | planning alone: no delta on 7 tasks |
| tools raw (sonnet, 1) | 5/7 | 3.00 | Admitted-scaffold left in files (A43) |
| **tools+verify (sonnet, 1)** | **7/7** | **4.00** | first arm to clear the set incl. mca_limits (A49) |
| team p→2w→i (sonnet, 1) | 6/7 | 3.57 | 2.2x cost; rescued regex_deriv; audit clean (A47) |

Key findings:
1. **verify-before-DONE is the phase-2 headline rung**: legitimize
   Admitted-as-scaffold + a client-side gate mirror = CI-before-commit for
   proofs; the only arm to solve mca_limits. (Caveat: ran with the A48
   path confound active — 7/7 is a lower bound.)
2. **File-level multi-agent decomposition WORKS** (vs phase-1's proof-level
   team negative): same solves as best single arm, wall bounded by slowest
   worker, integrator de-facto performs the verify sweep; concurrency
   audit clean (0 lock contention after flock serialization, 0 ownership
   violations, 0 write-after-open).
3. **Interface friction compounds at project scale**: the path-resolution
   saga (A42 -> A48 collision -> A50 fix) moved open usability 8.5%→47%;
   grading correctness needed two regrade rounds (A43, A46) — building the
   arena honestly is half the experiment.
4. Weak policies stay build-bound regardless of tools (haiku ladder
   1→2→3 of 14): the phase-1 boundary reproduces in the realistic setting.

Caveats: sonnet arms are 1 rep on 7 tasks (directional, not definitive);
all regrades and the invalidated af_tools2_haiku run are preserved in the
logs as the record. CONTAMINATION: the underlying mathematics is classic
(insertion sort in Software Foundations, Brzozowski in several published
formalizations, Pascal in mathcomp's own binomial.v; mca_limits explicitly
permits library lemmas) — training-data familiarity is certain. The A/B
deltas remain valid (memorization is constant across same-policy arms), and
observed failures were integration/discipline, not recall; but ABSOLUTE
solve rates should be read as familiar-mathematics performance. Novel-spec
tasks (renamed concepts, unusual compositions) are the future-work fix.

## Chronology — wave 2, the expensive-feedback regime (current dataset; trail A51–A53)

Wave 1 found that on small, familiar projects with cheap builds a plain
write/rebuild loop suffices at strong tiers (base 6/7) and the interface's
one clear win (verify-before-DONE, 7/7) came under *generous* budgets
(1500 s / 80 turns). Wave 2 attacks all three confounds at once: **expensive
feedback** (every file opens with a heavy mathcomp prelude — 4–6 files ⇒
~20–30 s clean rebuild), **novel specs** (renamed/recomposed concepts, no
task states a textbook theorem under its textbook name — contamination
kill), and **tight budgets** (900 s / 40 turns, half of wave 1). Four new
reference-validated tasks (well-posedness rule enforced BEFORE eval; A51):

| task | content (novel framing) | files |
|---|---|---|
| frugal | bounded min-plus/"tropical" cost algebra on option nat + 2×2 matrix product (associativity the meaty proof) | 4 |
| gauges | real-interval "gauges" over `realType`, `inside` as a Prop + concrete-value lemmas; op soundness + width transport | 4 |
| ledger | append-only (account,delta) ledger over ssrint; replay/checkpoint equivalence + a "no-teleport" `|bal| ≤ total` bound | 4 |
| prodauto | DFAs over a finType; product (card n·m) + complement, language-intersection theorem, emptiness via `connect` reachability, pumping-light pigeonhole | 6 |

Two arms, 2 reps each, one sequential chain, poisoning-clean (all rate-limit
statuses `allowed_warning`/`connected`, no API errors):

| arm | frugal | gauges | ledger | prodauto | **total** |
|---|---|---|---|---|---|
| **w2_base** (files sidecar only) | 1/2 | **2/2** | 2/2 | 0/2 | **5/8** |
| **w2_verify** (tools + verify-before-DONE) | 1/2 | **0/2** | 2/2 | **1/2** | **4/8** |

### Verdict (honest, the headline WAVE2 asked for)

**The interface does NOT beat the build loop under expensive feedback — it
does slightly worse (4/8 vs 5/8).** The rung that WON under generous budgets
(verify 7/7, A49) LOSES under tight ones. It trades tasks rather than adding:

- **The live prover cracked the hardest task**: verify solved prodauto
  (6 files, the product-automaton/emptiness/pigeonhole task) in one rep —
  clean DONE, 39 turns, 499 s — where base went 0/2 (both hit the 900 s
  wall). This is the one place the interface earned its keep.
- **The scaffold workflow BACKFIRED on gauges** (verify 0/2 vs base 2/2).
  Every verify failure is `forbidden_token` — real leftover `Admitted.`
  (confirmed: multiple per file, not a grader artifact). The
  Admitted-as-scaffold + verify-before-DONE workflow accrues admit-debt that
  the agent never discharges because it hits `max_turns 40` first (all
  verify failures at turns = 41). Under a tight turn budget, legitimizing
  scaffolding is a net liability: base's plain build loop never *introduces*
  an admit, so its failures are honest build/timeout failures, not
  gate-violating ones.

### Build-wait mechanism probe (the wave-2 thesis, tested directly)

Thesis: "base burns its budget waiting for builds while the tools arm spends
turns proving." We summed every `dune_build` call's wall from each attempt's
sidecar log (`server.jsonl`, `dur_ms`). The data **refutes the thesis's
mechanism**:

- **base's failures did ZERO `dune_build`s.** The three base failures
  (frugal rep1, prodauto rep0/rep1) reached the 900 s wall having built
  *nothing* — they were killed by extended *thinking*, not by build-waiting.
  Base *successes* did rebuild heavily (gauges 18×/77 s, 14×/86 s). So base
  is not "build-bound"; on novel hard tasks it is **think-bound** (sonnet's
  extended thinking eats the tight wall before it acts).
- **verify shifts, not removes, the wait.** It does fewer full rebuilds
  (1–5 `dune_build`s, mean 35 s) but adds interactive `build{file}` calls
  (2–12×, ~11–75 s). Total build-wait is comparable to base — the interface
  converts full-rebuild cycles into interactive-build cycles, roughly a wash,
  not the predicted large saving.

Net: the interface neither removed the build-wait bottleneck (it moved it)
nor improved accuracy; its scaffold discipline added a failure mode that cost
more tasks (gauges −2) than the live prover saved (prodauto +1).

### Team arm (file-level decomposition, tight per-role budgets)

Spend after the two single arms was ~$18 (< the $40 gate), so a team arm
(planner → 2 file-owning workers with their own rocq sessions → integrator;
tight per-role budgets) ran on prodauto only, 1 rep. **Result: SOLVED**
(layer 4, 744 s, $1.23) — poisoning-clean. Standing on the hardest task:

| task | base | verify | team |
|---|---|---|---|
| prodauto (6 files) | **0/2** | 1/2 | **1/1** |

The product-automaton task that base could not even build (both reps hit the
900 s wall) yields to file-level decomposition, reproducing wave 1's finding
(A47) that the integrator role de-facto performs the verify sweep. **The
interface's value is concentrated on the hardest/largest task** — where a
lone write/rebuild agent cannot finish at all — not across the board. It does
not rescue the mid tasks where the single verify arm's scaffold-debt lost
ground to base. (A53)

### Caveats

2 reps/task, one policy (sonnet), a single wave; extended-thinking-induced
900 s timeouts add variance to the *absolute* base rate (several attempts
were killed mid-work, so their `results.jsonl` cost reads $0 — real spend was
reconstructed from transcript tokens, ~$18 total). The valid comparison is
the same-policy / same-tasks / same-budget A/B delta, and that delta says:
**when feedback is expensive and budgets are tight, the plain build loop is
at least as good as the prover interface, and the scaffold-first workflow is
actively harmful.** This is the mirror image of wave 1 and the more
realistic regime — the honest wave-2 headline.

## Naming note
The four novel tasks are `frugal`, `gauges`, `ledger`, `prodauto` (renamed
from `w2_*` — the wave prefix was experiment-internal). Completed run logs
under logs/autoform/ retain the old `w2_` task names as frozen history.

## Verdict — the evaluation in detail

Framing: phase 2 EVALUATES the existing rocq-mcp-evolve server on realistic
multi-file autoformalization tasks. It is NOT a tool-evolution ladder — the
only code change it surfaced as necessary is relative-path resolution
(open/build accept workspace-relative paths, a usability fix; kept). Other
tweaks explored during the evaluation (a missing-import hint) were REVERTED
as below the measurement noise floor. What the evaluation MEASURED:

(decision trail A39–A57)

Goal: evolve the best general Rocq MCP server (rocq-mcp-evolve) by A/B-tested
features on real multi-file autoformalization tasks. After a contaminated
wave-1 pilot (classic theorems; established the method + gate), the real
experiment ran on 4 NOVEL, contamination-controlled tasks (mathcomp /
mathcomp-analysis projects), sonnet, tight budget (40 turns / 900s).

Measured results (baseline = agent with file+dune access, no MCP):
1. **Prover tools (iteration 1) — KEPT, the win.** + rocq-mcp-evolve's
   prover tools (open/build/check/step/try/auto_close, clean strict-no-
   Admitted prompt): 7/8 vs baseline 5/8 (+2 tasks), and cracked the hardest
   6-file task prodauto 0/2 -> 2/2. The general prover interface measurably
   helps building real projects. (The earlier "interface loses" was a
   bundled scaffold-prompt confound, retracted — A54.)
2. **Multi-agent teams — no value at this scale, documented.** A clean
   planner->workers->integrator team solved 2/4 vs solo 4/4 at ~1.8x cost;
   the integrator even missed an undischarged hard lemma solo had closed.
   Consistent with phase 1: teams pay off ONLY when the lone agent cannot
   finish; a strong MCP makes solo sufficient here (A56). Orchestration
   stays a harness scaffold, never a product feature.
3. **Missing-import hint — explored then REVERTED (A57b).** Evidence-mined
   (both gauges failures = lra/nra used without Require); built as general
   error enrichment; a trigger bug (fired 0x) was found and fixed (A56/A57).
   But its solve-rate delta was UNMEASURABLE at 8 attempts, so under the
   evaluation framing it is not a justified product addition and was removed.
4. **SOTA sibling rocq-mcp — hurts on this testbed, replicated across two
   prompt variants (A58/A58b).** Baseline + the sibling rocq-mcp server
   (instant-handshake proxy; 0/16 pending handshakes — no startup race):
   generic tool-list prompt 2/8, tuned recipe prompt (mirroring the evolve
   arm's) 1/8 — both below baseline 5/8, far below rocq-mcp-evolve 7/8, all
   16 attempts hitting the 40-turn wall. The prompt-asymmetry hypothesis was
   explicitly tested and refuted. Not a connectivity/load-path defect (the
   sibling is dune-aware; 63% of calls succeeded); the measured mechanisms
   are workflow-level: rocq_compile_file's .vo output pollutes the dune
   source tree and breaks dune_build; its sessions see only the file's own
   imports (evolve preloads Lia/Lra/zify/algebra-tactics, so finishers fire
   out of the box); and the REPL-oriented surface invites proof-stepping
   that exhausts tight turn budgets before files are complete. Residual
   caveat: the SOTA arms lacked the files.verify pre-DONE check the evolve
   arm had. Lessons: read the other server's source and measure call-level
   success before attributing a mechanism; and test a suspected confound
   rather than asserting it.

Methodological finding: at 2 reps x 4 tasks the noise floor is +-2 tasks
(Sonnet nondeterminism), so only COARSE effects resolve (prover tools +2,
team -2); fine tool refinements need many more reps/tasks.

Caveats: sonnet arms are small-N; wave-1 absolutes are contamination-
inflated (novel w2_* control for it); ~$55/$60 total spend; team is 1 rep.
The ONLY product change phase 2 surfaced as necessary is relative-path
resolution for open/build (A42/A48; kept — the prover suite, verify{} were
already core). Next frontier (future work): a harder task wave where solo
CANNOT finish — the regime where multi-agent showed value in phase 1.

## A103 second control arm (2026-07-16)
af3_base2 (config verbatim copy of af3_base, registered before launch,
report-only): **12/20** — frugal 4/4, gauges 4/4, ledger 3/4, prodauto
1/4, triadic 0/4. The control replicates within its ±2 calibration.
Pooled control 22/40 vs evolve family 58/80; per-arm margins vs the
pooled control are +2.5 to +3 (vs +4/+5 against the single first
control). prodauto is no longer evolve-exclusive (1/8 pooled control
solves); triadic remains 0/55 all-time.
