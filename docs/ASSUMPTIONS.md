# Autonomous decisions & assumptions log

Every decision made without user input, with reasoning. Numbered, append-only.

## A1 — Agent policy = `claude` CLI headless
No raw API key is present in the environment; the `claude` CLI (2.1.198) is the
only configured, authenticated LLM endpoint. Policy runs use
`claude -p --output-format json --strict-mcp-config --mcp-config <cfg>` with all
built-in tools disabled, so the ONLY actions available to the policy are the tools
under test. Token usage and cost are read from the CLI JSON result. Model is
pinned per run and held fixed across configs.

## A2 — Policy model: `claude-haiku-4-5`
Reasoning: hundreds of proof attempts across configs/ablations/repetitions make a
small-fast model the only affordable fixed policy; Haiku 4.5 is tool-use capable.
Risk: low solve rate on hard bucket → mitigated by reporting per-bucket numbers
and efficiency metrics that are defined for failures too (tokens/calls/latency per
attempt). Will be revisited ONLY if the easy bucket solves ≈0 on the baseline
(would make deltas unmeasurable); any change would be recorded and all configs
re-run — the policy is held fixed across every comparison in the report.

## A3 — Tool layer implemented as an OCaml MCP stdio server
The agent-facing interface is the deliverable, so it is implemented in OCaml as a
first-class binary (`rocq-agent-mcp`) speaking MCP JSON-RPC over stdio, linking
rocq-runtime libraries in-process where the config calls for it. MCP is chosen
because it is the native tool protocol of the fixed policy endpoint (claude CLI);
the protocol adapter is thin and identical across configs, so measured deltas come
from the tool semantics, not transport differences. No existing Rocq MCP server
code is used or consulted.

## A4 — Working-directory layout interpretation
The task says the working dir contains `rocq-workbook/`, `minif2f/`, `rocq-tools/`.
Actual names: `rocq-workbook/`, `miniF2F-rocq/` (test+valid splits), `rocq-tools/`
(the empty git repo, where this project lives). `miniF2F-rocq/valid` = the "train"
split used as dev; `miniF2F-rocq/test` = held-out (the dataset ships no separate
train, valid is the conventional dev split for miniF2F).

## A5 — Difficulty labels
- rocq-workbook: use the dataset's own `difficulty` field (easy/medium/hard).
- miniF2F: no explicit difficulty label in the .v files; proxy = problem source
  tier extracted from the filename (amc → easy-tier, aime → medium-tier,
  imo → hard-tier, mathd_* → course-tier easy) — documented in the report; both
  splits contain the same source families so stratification holds by construction.

## A6 — Budgets
Fixed 2026-07-01, printed in STATUS.md: run ends 2026-07-06 EOD; per proof attempt
≤ 16 policy turns and ≤ 300 s; dev60 iteration set (20/20/20 stratified,
stdlib-only, seed 42); ≥ 2 reps for kept changes. Rationale: keeps a full dev60
eval under ~1 h so several ablation cycles fit per day, while leaving the final
day for the frozen run + report.

## A7 — Switch amendments (and a Rocq downgrade)
The dedicated switch lacked `yojson` (JSON for the OCaml server) and the libraries
~10% of dataset files import. Installed and pinned: yojson 3.0.0,
coq-coquelicot 3.4.4, (rocq-)mathcomp-ssreflect 2.5.0 (repos `rocq-released` +
`coq-released` added, scoped to this switch). Side effect: the opam solver
**downgraded Rocq 9.2.0 → 9.1.1** (the coq-* compat shims Coquelicot needs cap at
9.1.1). Accepted: verified datasets still compile identically and the project
builds; Coquelicot coverage is worth more than the newer point release. The
experiment substrate is therefore **Rocq 9.1.1 / OCaml 5.3.0**, pinned in
repro/opam-packages.txt.

## A10 — Cross-policy robustness annex (user-requested, 2026-07-02)
The ladder is selected under the fixed policy (A2, claude-haiku-4-5) per the
brief. As a robustness annex — not a selection criterion — baseline and the
final winner are additionally measured once with a stronger policy
(`claude-sonnet-5`, 2 reps, dev60) to report whether the interface deltas
transfer across policy strength. Hypothesis: structural wins (session/try)
transfer; the hints delta shrinks (it targets Haiku-specific Lean-isms).
Runs tagged `*_sonnet`; never used for keep/revert decisions or the freeze.

## A13 — Team experiments are first-class experiment citizens (user steer)
The multi-agent workstream follows the exact same discipline as the solo
ladder: (a) problems come from the dev manifests (team manifest = the hard
bucket of dev60+dev150, 70 problems, both configs run the SAME problems);
(b) the daemon emits the standard JSONL instrumentation (ts, latency, op,
agent id, prover ms, run/config/problem metadata); (c) team attempts produce
standard results.jsonl records (schema-compatible + team extras: n_workers,
phase walls, per-agent usage) so report.py/monitor.py/dashboard work
unchanged; (d) the correctness gate applies identically to the composed
candidate.v; (e) the solo-vs-team comparison is a config A/B at EQUAL total
wall-clock, reported per bucket like every other ablation.

## A12 — Intra-proof parallelism directive (user steer, 2026-07-02 evening)
The tool layer must generalize to large-scale projects: parallel agents working
on DIFFERENT PARTS of the SAME proof (multi-agent workflows for hard problems).
Plan: (1) rung: fork-based `parallel_close` — attack all open subgoals
simultaneously in COW child processes; (2) architecture: shared session daemon
(Unix socket) + thin MCP shims so multiple policy agents attach to one live
proof with goal-scoped focus/commit; (3) experiment: coordinator + k workers
vs solo agent at EQUAL wall-clock budget on the hard bucket (pass@equal-budget
is the honest metric). Enabling primitive already in place: immutable
Vernacstate snapshots make any subgoal shippable to any worker.

## A9 — miniF2F difficulty buckets from source tiers
Filename-prefix tiers map to buckets: mathd_algebra + mathd_numbertheory → easy
(course problems, 130/244 per split); amc12* + algebra + numbertheory +
induction → medium (79); aime* + imo* + imosl → hard (35). Rationale:
competition tier is the only difficulty signal in miniF2F and is standard
practice; both splits contain the same families, so dev/test stay comparable.
Recorded per-record as `source_tier`; the mapping lives in
`datasets.MINIF2F_TIER_TO_BUCKET` and is applied at record-writing time.

## A8 — Proof-region discipline (anti-gaming)
The agent may only append content AFTER the shipped theorem statement; the file
prefix (imports + preamble + statement) must match the dataset file exactly
(whitespace-normalized). Rationale: inserting imports/scopes/notations before the
statement can silently change what the statement means (e.g. `Open Scope`
re-parsing `+`), which is unauditable at scale. Helper facts remain expressible
via `assert`/`have` inside the proof. Uniform across all configs, so it cannot
bias comparisons.

## A14 — Pipeline acceleration (user steer, 2026-07-03)
(1) parallel=8 adopted as the standard for winner-family dev runs, justified by
the measured sweep (wall +7 %, CPU 24 % at N=8; near-linear throughput); any
compared pair must share N. (2) The held-out run is pulled forward: freeze
committed (FROZEN.md); unlock+final chained behind the 4-rep variance top-up
the same day. The one-shot discipline is sequence-based (frozen before
unlock), not calendar-based. Final runs at parallel=4 per the frozen protocol.

## A15 — Policy-robustness objective (user steer, 2026-07-03)
The tool layer must serve multiple policies including the strongest, not be a
Haiku-specialized artifact. Design response: the Sonnet regression traces to
the prompted interaction STYLE, not the tools — `step` already accepts whole
proof scripts with commit-good-prefix semantics (strictly more informative
than a whole-file check at identical turn cost). New `unified` config =
frozen toolset + draft-first/repair-from-failure prompting; measured on dev60
vs all four existing controls (haiku/sonnet × naive/winner). Test split is
already spent on the frozen config per the brief's freeze-then-test sequence;
unified evidence is dev-only and framed as the recommended config going
forward.

## A16 — SOTA comparison against rocq-mcp (user-requested, 2026-07-03 ~16:45)
First contact with github.com/LLM4Rocq/rocq-mcp (local checkout inspected)
happened ONLY NOW, after the ladder closed, the config froze, and the held-out
run completed — the commit history (through the freeze at configs/FROZEN.md)
proves design independence per the brief's "do not copy existing Rocq/Lean MCP
servers". Comparison protocol: rocq-mcp runs as an external config through the
SAME harness — same policy (claude-haiku-4-5), same dev manifests, same turn/
wall budgets, same correctness gate on a submitted candidate (a minimal
`submit` sidecar tool writes the artifact; the gate re-verifies from scratch,
so submission is not trusted). Never run on the test split. Reported as a
dev-set comparison.

## A17 — Rung 9 from residual-failure mining (2026-07-03 evening)
User challenge ("no additional tools would make a difference?") answered by
mining the winner's 130 hard-bucket failures: 123 had already exhausted the
auto_close portfolio; residual goals are 41 % nonlinear inequalities; agents'
last-ditch pattern is assert(154)+nra(94) — hunting the auxiliary square/
product fact that lets nra close. Rung 9 = server-side HINT-TERM SYNTHESIS
(auto_close2): harvest R-variables, mechanically assert pow2_ge_0/product
facts, run nra/psatz on the enriched context; bounded trials, zero model
turns. Dev-evidence only (test spent); measured on dev60 + hard bucket.

## A18 — Budget extension (user, 2026-07-03 ~17:15)
Hard stop moved from 2026-07-06 EOD to 2026-07-07 EOD. Revised calendar:
Jul 3 eve–Jul 5: continued iteration (rung 9 hint-synthesis; rocq-mcp SOTA
comparison; sonnet-native follow-ups if won; team re-test on a mechanically
detected DECOMPOSABLE-problem manifest — addressing the honest gap in the
team negative result; pass@k scaling on hard at N=8). Jul 6: consolidation +
full report. Jul 7: buffer + clean end. Held-out protocol unchanged (already
executed; one shot, spent on the frozen config).

## A19 — Pre-registered SOTA predictions (written BEFORE rocq_mcp_dev60 ran)
Design analysis of rocq-mcp v0.3.1 against our measured ablations predicts,
for dev60 @ claude-haiku-4-5, identical budgets/gate:
(1) pass@1 strictly between baseline (.44/.25/.30) and session_try
    (.65/.375/.375) in every bucket — warm interactive sessions (their
    rocq_start/rocq_check ≈ our kept session rung) but no machine-enumerated
    portfolio (our largest single gain), no error-payload hints, and
    step_multi requires a commit round-trip (turn cost).
(2) Their pull-based info tools (rocq_query/toc/notations/assumptions/diag)
    show the search-tool signature: meaningful adoption, no rescue effect.
(3) Turns/attempt higher than winner's at similar wall (more round-trips).
Convergences noted for the report: interactive state-id sessions, multi-
tactic testing, goals-at-error — independent replication of 3 of our kept
design pressures. Their workspace/multi-file tools target a regime our
experiment does not measure (honest scope limit).

## A20 — In-project proving benchmark (user steer, 2026-07-03 ~17:45)
Goal extended: tools must be realistically usable in bigger projects. New
benchmark axis: lemmas extracted from MID-FILE positions of the local Rocq
stdlib checkout (a real ~700-file project, builds on this exact switch),
proofs stripped, task = prove in true file context (immutable prefix = all
of the file above the lemma; the target's own installed module is never
Required, so no self-application leakage). Difficulty = ground-truth proof
sentence-count buckets. Interface A/B this benchmark isolates: full-prefix-
in-prompt vs STATEMENT-ONLY prompting with server-side context (the session
already executes the prefix; the agent pulls context on demand) — the
context-economy question that dominates big-project use. Memorization risk
(policy trained on stdlib) affects absolute rates only, not the config A/B
(shared policy); noted in threats-to-validity. Multi-file editing = future
work.

## A21 — Involved-project extension (user steer, 2026-07-03 ~18:00)
In-project benchmark extended beyond stdlib: (i) mathcomp60 — mid-file lemmas
from the local math-comp checkout (boot/order; ssreflect proof language, a
qualitatively different regime for both policy habits and our stdlib-centric
hint tables; Requires resolve against installed rocq-mathcomp 2.5.0, drift
filtered by compile-verification); (ii) mathcomp algebra/field + mathcomp-
analysis installing in background (solver dry-run verified: Rocq untouched)
to unlock analysis-based tasks; (iii) load-path plumbing (-Q/-R via env into
session init + gate) planned as the dune-project infrastructure deliverable,
demonstrated on one dune-built project if time permits. Honest expectation:
absolute solve rates on ssreflect will be low for this policy; the interface
A/Bs (ctx_full vs ctx_lean; vs naive baseline) remain valid comparisons.

## A22 — False-winner bug in auto_close (found by rung-9 smoke, 2026-07-03)
`auto`-style no-op-tolerant tactics "succeed" without progress, so
auto_close's ran-without-error winner check committed useless sentences and
told the agent the goal closed (the truthful goal render followed, limiting
harm). Consequences: the rung-7 mechanism stat ("71 % of calls close a goal",
top winner `auto with real arith` 46/64) was inflated by fake wins and is
retracted in the report; rung-7's KEEP verdict is unaffected (pass@1 measured
end-to-end). Fix: winner requires goal-count decrease or completion, in both
session server and team daemon. Measured as rung 9a (winner_autofix) before
rung 9b (hint synthesis) so the two effects are separable.

## A23 — Usage-pool optimization + real-project infra directive (user, Jul 3 ~21:10)
User at 75 % of shared model quota (Max x20), Fable at 30 %. (1) Queued evals
trimmed: rocq_mcp_sonnet finishes (sunk); sonnet_native_auto2 and the
mathcomp probe drop to 1 rep (pass@1 only, noted); decomposable solo/team
pair kept at 2 reps (cheap haiku, n=27); nothing else queued — consolidation
uses existing data. (2) Engineering shifts to Fable-powered infra: dune +
_CoqProject load-path support end-to-end (session init via ROCQ_INIT_ARGS,
gate extra args, manifest plumbing, project-args helper), validated on a real
dune project with a micro-eval.

## A24 — Policy-neutral MCP requirement (user steer, Jul 3 ~22:20)
The deliverable must NOT be Haiku-specialized. Finding to date: all
server-side capabilities are policy-neutral; the Haiku flavor lived in
prompts (style forcing, give-up) and in the Haiku-only selection criterion.
Response: (1) style-agnostic surface — whole-proof `check` added INSIDE the
session server (one-shot submission with repair-from-failure semantics), so
both interaction styles are first-class in ONE server; (2) neutral prompt
(both workflows presented, no give-up); (3) recommended-config criterion =
best worst-case across measured policies (extends A15's pre-registration).
Validation: `universal` (haiku) + `universal_sonnet`, 1 rep each, queued
after the trimmed queue.

## A25 — Atlas-derived fixes (rung 10, Jul 4 ~00:15)
From docs/FAILURE_ATLAS.md: (1) auto-Qed handshake — any tool leaving zero
open goals on an incomplete proof now issues Qed server-side (the missing
handshake cost 13 attempts = the entire sonnet-incremental gap; agents
fabricated "PROOF COMPLETE"); (2) dead tools purged — psatz (requires the
absent csdp binary; ALWAYS failed) and field_simp (Lean-ism, nonexistent)
removed from portfolio and hint texts, replaced with working closers;
(3) Search inequality-direction flip-retry (`_ >= 0` patterns found nothing
though the lemma exists as `0 <= _`). All deterministic, zero-turn. The A24
universal pair (re)runs on this fixed binary; earlier configs' measured
numbers stand as recorded (their binaries documented per run_meta git_rev).


## A26 — ssreflect knowledge-distillation probe (Jul 7)
Evidence-mined from the mathcomp probe corpus (Search-idiom failures x66
dominate; stdlib-tactic habits; name guessing): gated ssreflect hint table
(ROCQ_HINTS_SSR=1) — Search/Check syntax failures get mathcomp naming +
boolean-reflection guidance; stdlib tactics get ssreflect equivalents;
mathcomp-fragment unknown refs get name-fragment search advice — plus
`by []`/`done` portfolio entries. Tests the per-project distillation
mechanism (DESIGN evolution path) with one measured rerun of mathcomp35.


## A27 — server-side exemplar retrieval (Jul 7, large-project axis)
Grounded in A20 (in-project medium wins with adjacent proof BODIES, +12.5pp
full-vs-lean) but full-file context cannot scale to large projects. New
mechanism, gated ROCQ_EXEMPLARS=1: at session start the server scans project
sources (ROCQ_PROJECT_SRC or ROCQ_INIT_ARGS paths), extracts proved
(statement, proof) pairs comment-stripped, ranks by rare-token (IDF) overlap
with the theorem statement, and PUSHES the top-3 with proofs into the first
tool response — zero turns, ~1.5k tokens, any file size, any policy.
Leak-proofing: for the file the task was cut from, only the region BEFORE
the prefix end is admissible (the target's own proof is never retrievable).
Smoke: ltn_exp2r -> {expnI, ltn_pexp2l, leq_pexp2l}. A/B on mathcomp35 at
haiku + fable vs same configs without.

## A28 — productization (Jul 7, from user review of README)
User: "why is install so complicated / why python to use it on a project?"
Root cause: README documented the experiment artifact; project_args.py was
harness leakage into the usage path. Fixed: (1) opam package `rocq-tools`
(public binaries rocq-mcp / rocq-mcp-daemon / rocq-mcp-shim); (2) in-server
load-path auto-discovery (walk up from ROCQ_TASK_FILE to _CoqProject or
dune-project; OCaml, zero external tooling); (3) product defaults: all tools
on, hints/suggest/synthesis/exemplars on (opt-out with =0), tactic preload
split from the Require-refusal policy (preload default-on via ROCQ_PRELOAD,
refusal stays opt-in via ROCQ_ENV_V2). All historical configs pinned with
explicit values so their semantics are unchanged and self-describing.
Verified hermetically: installed binary + ROCQ_TASK_FILE alone proves a
lemma in a fresh dune project (auto-discovery + preload + portfolio).


## A29 — runtime `open` tool (Jul 7, from user review)
User: "why ROCQ_TASK_FILE — can't I just register the mcp and ask the agent
to finish a proof in a file?" Correct: task-at-launch was harness DNA. New
`open{file, theorem?}` tool: executes the file (project auto-discovered from
its location), targets the named theorem's statement (everything after it,
e.g. its Admitted, is ignored) or the trailing open statement; session
resets per open (several proofs per session, one project per process);
missing-file/no-goal/failing-file errors are directive. Completion messages
now carry the finished proof script so the CLIENT agent inserts it into the
user's file (server proves, agent edits). ROCQ_TASK_FILE remains as the
harness preset. Verified: open Admitted theorem -> auto_close -> script;
re-open same file trailing goal -> check -> script.


## A27 verdict (Jul 7 evening)
Haiku A/B clean (35/35, 0 poisoned): medium unchanged, short −.10 → REVERTED
to opt-in. Fable arm confounded by pool throttling; not re-run (worst-case
rule decides). Mechanism ships gated; quality verified; test-covered.

## A30 — prefix replay memoization (Jul 7 evening, from user design review)
User: heavy mathcomp imports reload per open. Measured: all_ssreflect +
all_algebra prefix = 7.5 s at first load; re-open of the same file was
14.4 s (full redundant re-exec, doubled by open's probe+make_session).
Fix: sentence-level replay cache in the driver — re-execution from the
pristine state skips the interpreter for every leading sentence whose text
matches the previous run, resuming at the divergence snapshot. Measured
after: re-open 0.4 s (36x), opening a SIBLING file sharing the import block
0.5 s (imports paid once per process). Correctness: cache entries are real
snapshots from identical sentence sequences off the identical start state;
only prefix/open paths pass the cache. Cross-process warm-pool forking
remains the documented next step (DESIGN A12).

## A32 — mathcomp algebra-tactics conditional (Jul 7 night, user suggestion)
User: "mathcomp has algebra-tactics — worth a conditional for auto solve?"
Yes: the corpus showed the stdlib portfolio is POWERLESS on boolean-
reflection/ssralg goals (mathcomp medium collapse; A26/A27 informed but
could not close). Installed coq-mathcomp-zify + coq-mathcomp-algebra-tactics;
make_session detects the mathcomp regime (prefix mentions mathcomp) and
best-effort preloads `zify` + algebra-tactics `lra` (silent when absent;
ROCQ_MC_TACTICS=0 opt-out; historical configs pinned =0). Portfolio gains
by []/done/by lia/by ring/by lra/by nia in-regime. Smoke: `by lia.` closes
`(n + m * 2 = m + n + m)%N`. A/B at haiku on mathcomp35 vs winner_ctx_lean
(.50 short / .071 medium) running — this adds CAPABILITY, not information,
so it is the first intervention with a mechanical reason to move the weak-
policy mathcomp numbers.

## A31 — product-code adversarial review (Jul 7 night): 24 confirmed, triaged
Five-skeptic workflow + refuting verifiers over the day's additions.
FIXED (repro-verified where applicable):
- CRITICAL exemplar leak-guard dead after `open` (byte-prefix never matches a
  normalized prefix; _build mirrors served the target's own proof): replaced
  with statement-token identity exclusion + _build/.git/_opam skipped in the
  scan; live repro now clean (sibling served, target proof not retrievable).
- Memoization staleness (live-reproduced stale accept after .vo recompile):
  .vo fingerprint (path,mtime,size) over init load paths; cache dropped on
  change; repro now correctly fails the changed proof.
- Cache truncation/wipe: prefix-of-cache runs no longer overwrite.
- open re-armed exemplars with inverted polarity (default-on): now opt-in.
- with_exemplars consumed the one-shot block on ERROR results: guarded.
- stmt_re \b failed on prime-terminated names: explicit non-ident/end match.
- Dune discovery bound the first (name) anywhere in the file: now scoped
  after the coq.theory occurrence; missing _build mirror now falls back to
  the source dir (in-place builds); _CoqProject -arg kept, tab-safe split.
- Daemon focus guard compared stale positional ids: conclusion digest now.
- Cross-project `open` after init: explicit NOTE in the response.
DOCUMENTED, NOT FIXED (accepted): mk_prefix drops comments between sentences
(candidate.v cosmetic); open probe executes the whole file once before
cutting (memoized thereafter); preload re-executes per open (~0.3 s);
strip_comments depth-0 string literals containing "(*"; score recomputation
in sort; Failure-only clean surfacing; cache memory footprint.

## A32 verdict (Jul 7 night)
A/B at haiku on mathcomp35, clean (0 poisoned), portfolio confirmed loaded
(16 candidates incl. by lia/by ring): short .50 = .50, medium 0/14 vs 1/14
(noise). NO measured lift — mathcomp35 mediums are not final-goal-arithmetic
failures; they need structural ssreflect steps first (fourth consistent
confirmation: atlas, counterfactual replay, A26, now A32). DISPOSITION: the
conditional SHIPS (regime-gated, zero cost when absent, mechanically
verified capability on arithmetic-shaped goals — the mathcomp analog of
env-v2, whose miniF2F win came precisely from arithmetic-shaped goals) but
claims NO benchmark improvement. The honest boundary stands: weak-policy
ssreflect proving is bounded by structural competence, not by closers.


## A33 — multi-error `build` tool (Jul 8, user suggestion)
"Would it make sense to report multiple errors at once, e.g. building
several helper lemmas?" Yes by the design law (n independent errors/turn >
1). Rocq disallows nested Lemmas in proof mode, so the scenario lives at
FILE level: new `build{file}` tool executes every top-level block with
admit-and-continue (failed proof -> rolled back, statement Admitted so
dependents still elaborate; unparseable block -> skipped to next block),
reports every hole in one call, discards all state (pure diagnosis; the
completion/auto-Qed guardrail question never arises). Smoke: h1+h3 broken,
h2+main(depends on h2) OK -> exactly 2 holes reported with real errors.
UNMEASURABLE on the benchmark manifests (single-statement tasks) — ships as
suite-tested capability for the project axis, like the daemon.

## A34 — uninterruptible-tactic hang guard (Jul 8, user-reported divergence class)
User observed rocq-mcp diverging on hung tactics (vm_compute on
2016^20214 mod 10). Empirical audit of OUR design: Control.timeout catches
cbv/ltac runaways cleanly, but vm_compute and native_compute BYPASS it
(hang forever — the VM misses the interrupt checkpoints on such workloads).
The experiment was protected only by the harness's attempt-level
process-tree watchdog; interactive/product mode was NOT safe. Fix:
fork-probe — sentences matching vm_compute/native_compute/vm_cast/native_cast
first execute in a forked child under a hard SIGKILL deadline (timeout+2s);
only a probe that terminates within budget is re-executed in-process
(deterministic => sound; session state untouched by the child; COW-cheap).
Verified: the exact divergent case now returns a structured TIMEOUT in
~5s; small vm_compute still succeeds (0.3s). Residual, documented: the
probe costs 2x on slow-but-convergent heavy compute; the team daemon's
older driver copy is NOT probed (covered by the harness watchdog; not the
product path); exotic uninterruptible plugin loops outside the matched
tactics remain covered only by client-side timeouts.


## A35 — memprof-limits as the primary hang guard (Jul 8, user pointer)
User: "this may already work with memprof-limits". Confirmed empirically:
token interruption (allocation-triggered, the coq-lsp mechanism; statmemprof
restored in OCaml 5.3 = our compiler) stops BOTH vm_compute and
native_compute divergence with structured TIMEOUTs at ~5s, at 1x cost and
without the fork — strictly better than the A34 fork-probe as the primary.
Wired into exec_sentence (token + watchdog thread wrapping Control.timeout;
interp cache invalidated on interrupt; per-sentence unfreeze restores
summary state — the same state-consistency posture coq-lsp ships). The A34
fork-probe remains as an opt-in belt (ROCQ_FORK_PROBE=1) for
zero-state-risk contexts. Suite green (57/35/10/7); small vm_compute
success path verified.

## A36 — open reaches targets past broken proofs (Jul 8, found by the A14 test agent)
The build->open repair loop was broken for every hole after the first:
`open{theorem:X}` stopped at the first failing proof and could never reach
X. Fix: when targeting a theorem, open now admits-and-continues past
earlier broken blocks (build's mechanism; the reconstructed prefix replaces
each broken proof with `Admitted.`), so every hole `build` reports is
directly openable and provable. Verified: h1 broken FIRST, open h2 -> proved,
open main -> reached. The A14 fixture was restored to broken-first order as
the regression test (109 checks green).

## A37 — fair rocq-mcp comparison (Jul 8, user question "is it fair?")
Audit: original runs had rocq-mcp pending at agent start in 116-118/120
attempts (CLI sync-window vs Python startup); comparison retracted publicly.
Fix: instant-handshake proxy (harness/mcp_prewarm_proxy.py). Rerun 2x dev60
both policies: 120/120 connected, 0 poisoned. Fair verdict: sonnet near
accuracy-parity (.95/.925/.80 vs universal .95/1.00/.85), haiku mixed
(rocq-mcp edges easy .675; universal +.225 med/+.075 hard); rocq-tools'
robust edge = weak-policy med/hard + ~2x cost efficiency at sonnet. The
"dominated on all three axes" claim was wrong and is corrected everywhere.

## A38 — dogfood round (Jul 8): fresh-switch install + 10 hard AIME, 3 fixes
A fresh-switch agent followed the README verbatim: switch create + opam pin
worked with no deviation (rocq-mcp installed, smoke passed). Driving the
INSTALLED binary over raw MCP, it solved 10/10 hard-tier miniF2F problems
(AIME; <=7 calls each; every candidate independently recompiled) — an
informal frontier-policy anecdote, not a benchmark row. Product bugs found
and fixed: (1) open with empty args + preset -> raw Yojson error, now falls
back to ROCQ_TASK_FILE or errors cleanly; (2) auto_close with no open proof
claimed "no finisher applies", now says no proof open; (3) candidate.v was
NOT standalone (missing preload Requires) — in product mode it now embeds
the preload (and mathcomp-bridge) Requires; harness mode (ROCQ_ENV_V2=1)
keeps the bare shape for the gate's -ri protocol. Bare-recompile verified.

## A39 — phase-2 protocol (autoformalization, Jul 9)
Dataset: data/autoform (7 tasks, references validated). Conditions share an
identical file-workspace sidecar (write/read/list/dune_build); af_tools adds
the rocq MCP — the measured delta isolates the prover interface. Metrics
per task (NEVER pooled): solved (autoform_gate), layer reached (ordinal:
forbidden 0 / build 1 / probes 2 / audit 3 / solved 4), cost, wall, turns.
Policy: haiku 2 reps first; annexes later. Decision rule unchanged: one
measured change at a time; keep only what improves per-task outcomes.
Budgets: 80 turns, 1500 s/attempt.

## A40 — realistic-workflow conditions (user steer, Jul 9)
Goal restated: evaluate REALISTIC setups — planners, multi-agent workflows.
Phase-1's team negative does not transfer: projects decompose naturally at
FILE granularity. Two added conditions decompose workflow structure:
af_plan_sonnet (single agent forced to write PLAN.md first — isolates
planning) and af_team_sonnet (planner -> 2 parallel workers with exclusive
file ownership + own rocq sessions -> integrator — isolates parallelism;
run_autoform_team.py). Equal-ish wall budgets (team 300+900+700 vs single
1500 s); cost premium recorded honestly. Comparison axis at sonnet:
af_base vs af_tools vs af_plan vs af_team, per task, never pooled.

## A40 addendum — concurrency robustness (assessed, not assumed)
Synchronous stress smoke on one workspace: 2 concurrent rocq-mcp sessions
proving different files = clean (per-process isolation holds). 2 concurrent
raw `dune build` = loser fails on dune's global lock ("Unexpected contents
of build directory global lock file") — fixed at the shared-sidecar level:
dune_build now serializes via a workspace flock across all team agents
(callers queue; verified 3-way). Post-run audit tooling:
harness/af_robustness.py scans team logs for lock contention, file
ownership violations, write-after-open staleness, and server faults —
incidents are recorded as experiment data.

## A41 — phase-2 first data (af_base_haiku complete)
1/14 solved (haiku fully built+proved graph_reach unassisted, layer 4);
13/14 die at the BUILD layer with all 80 turns spent. Profile: write_file
596 + dune_build 496 across 14 attempts (~78 calls/attempt) — a whole-file
rewrite / full-rebuild loop, one syntax error per cycle (ltac syntax,
bullets, notations dominate). Hypothesis for the A/B now precise: the rocq
arm's sentence-level tools should convert rebuild-cycles into in-session
repairs. af_tools_haiku in flight.

## A42 — relative-path resolution in open/build (evidence-cited rung)
af_tools_haiku (2/14 vs base 1/14, mean layer 1.36 vs 1.21): rocq-tool
adoption was 111 calls vs 940 sidecar calls, and the friction audit
explains it — 25/59 open calls failed "no such file" because agents pass
WORKSPACE-RELATIVE paths (the files sidecar's convention), while open/build
demanded absolute. rocq build{file} delivered useful hole-reports (17) when
it was reached. Change: open/build resolve relative paths against
ROCQ_WORKDIR — tool-only, prompt identical (clean ablation). Rerun as
af_tools2_haiku behind the sonnet arms.

## A43 — sonnet A/B + the candidate.v artifact (regraded honestly)
af_base_sonnet: 6/7 solved (only mca_limits fails, at build). af_tools_sonnet
RAW: 3/7 with four layer-0 forbidden_token failures — ALL traced to
candidate.v, the session server's own phase-1 artifact dropped into the
graded workspace (ROCQ_WORKDIR pointed there; agents verifiably never wrote
it — 0 write_file calls). Fixed: both runners now put ROCQ_WORKDIR outside
the workspace; the four attempts were REGRADED with the server artifact
removed: binomial -> SOLVED (a real solve my infrastructure had masked);
mc_bigops + regex_deriv -> still forbidden (agents' OWN Admitted
scaffolding left in files — real failures with a mechanism: the tools
workflow invites Admitted-as-scaffold, and agents forget the final sweep);
mca_limits -> build_failed. CORRECTED sonnet A/B: base 6/7 vs tools 4/7.
Next-rung candidate (2/7 = scaffold-not-cleaned): a client-side gate-mirror
`verify` affordance so DONE is informed — to be implemented as its own
measured rung after the A42 rerun reports.

## A45 — verify{} gate-mirror rung (targets A43's scaffold-not-cleaned)
Evidence: 2/7 corrected sonnet tools-arm failures are agents' own leftover
Admitted scaffolding. Change (one rung, tool+closing-instruction together):
files sidecar gains verify{} — forbidden-token scan (comment-stripped, the
gate's own token set) + clean dune build — and the af_tools2_sonnet prompt
legitimizes temporary scaffolding but REQUIRES verify-before-DONE. Mirrors
real-world CI-before-commit. Rerun queued as af_tools2_sonnet.

## A44 — ops incident: mutual watcher deadlock (3rd pgrep lesson, now final)
The three queued arms never started: each while-pgrep watcher's [r]-bracket
prevented SELF-match but matched the OTHER watchers' command lines →
mutual deadlock once the real chain drained (queue logs all 0 bytes).
Rule going forward: never chain via pgrep watchers; one sequential nohup
chain (af_chain2: plan -> team -> tools2_haiku -> tools2_sonnet), python -u
for unbuffered logs.

## A46 — gate refinement (Unset false positive) + global regrade
`Unset Strict Implicit.` — standard ssreflect prelude — tripped phase-1's
blanket Unset ban in THREE genuine solves (mc_bigops at plan, team, tools
sonnet arms). Gate refined: blanket Unset/Set dropped for project tasks;
only kernel-flag tampering (Unset/Set Guard|Positivity|Universe Checking)
stays banned. ALL forbidden rows regraded globally. Corrected standings:
base_sonnet 6/7 · plan_sonnet 6/7 · tools_sonnet 5/7 · team_sonnet 4/4 (in
progress, mean layer 4.0!) · haiku arms 1/14 and 2/14. Sonnet single-agent
arms now fail ONLY mca_limits; tools arm additionally drops regex_deriv to
Admitted scaffolding (the A45 verify rung, queued, targets exactly this).

## A47 — team arm verdict + concurrency audit
af_team_sonnet FINAL: 6/7 (fails only mca_limits, the universal holdout),
mean layer 3.57, $14.06 (~2.2x single-agent cost), mean wall 723 s.
Notable: the team RESCUED regex_deriv (single tools arm scaffold-failed it
— the integrator role de-facto performs the verify sweep). vs phase-1's
proof-level team negative: FILE-level decomposition works — same solves as
the best single arm, bought with parallel wall (task time bounded by the
slowest worker, not the sum). Concurrency audit (af_robustness): 0 dune
locks, 0 ownership violations, 0 write-after-open, 2 minor server internal
errors across all attempts — the A40 flock + ownership discipline held
under real concurrent load. Cost premium recorded honestly.

## A48 — fix collision: A42 x A43 (rerun invalidated, corrected)
af_tools2_haiku: 0/14, open success 0/26 — WORSE than pre-A42. Cause: A42
resolved relative paths against ROCQ_WORKDIR, which A43 had moved OUT of
the workspace (server scratch) — every relative open resolved into an
empty dir. Fix: resolution base = ROCQ_PROJECT_ROOT (runner passes the
workspace explicitly), falling back to process cwd. af_tools2_haiku data
kept as the collision record; clean rerun = af_tools3_haiku. Note:
af_tools2_sonnet (mid-run) carries the same confound for open-utility;
its A45 verify verdict remains interpretable (scaffold-failure axis).

## A49 — A45 verdict: verify-before-DONE -> 7/7 (KEPT, the phase-2 headline)
af_tools2_sonnet: 7/7 solved, mean layer 4.00 — the FIRST arm to clear the
dataset, including mca_limits (65 turns), which base/plan/tools/team all
failed. Verify adoption: 10 calls, 1 VERIFY FAILED that caught a violation
before DONE. Mechanism: legitimize Admitted-as-scaffold + a client-side
gate mirror = the CI-before-commit workflow. Ladder at sonnet: base 6/7 ->
tools(raw) 5/7 -> tools+verify 7/7. Caveats: 1 rep; the A48 relative-path
confound was ACTIVE in this run (agents succeeded despite broken relative
opens — if anything a lower bound). VERDICT: verify rung KEPT.

## A50 — clean A42 verdict (af_tools3_haiku)
Open success 26/55 (47%) vs 5/59 (8.5%) pre-A42 — the relative-path rung
works (5.6x usability lift). Solves 3/14 (vs tools1 2/14, base 1/14), mean
layer 1.43 (1.36, 1.21): monotone but small — haiku remains BUILD-bound on
project construction (the weak-policy boundary, phase-1 echo). Rung KEPT.

## A51 — wave-2 task construction (4 novel expensive-feedback tasks, Jul 9)
Built + reference-validated 4 tasks per docs/WAVE2.md, all passing
autoform_gate (solved:true) BEFORE any eval (well-posedness rule):
- w2_frugal (18 probes): bounded min-plus/tropical algebra on option nat
  (meld=min, chain=+, top=None=+inf, one=Some 0) + 2x2 matrices; the meaty
  proof is matrix-product associativity via a 4-term interchange (meldACA)
  after distributing chain over meld. Carrier/Laws/Mat2/Main. ~22s build.
- w2_gauges (9 probes): real interval "gauges" (lo,hi) over R:realType,
  inside as a Prop (boolean-free) + concrete-value lemmas as the semantic
  pins (inside_1_02/outside_3_02/width_02); gplus/gneg/gscale soundness +
  width transport. Gauge/Ops/Sound/Width. Audit closed under the boolp trio.
- w2_ledger (9 probes): append-only ledger of (account,delta) over ssrint;
  bal/total as reducing Fixpoints (vm_compute pins on a concrete ledger),
  replay(foldl)+checkpoint equivalence (foldl_cat), no-teleport bound
  (|bal|<=total by triangle ineq). Entries/Balance/Replay/Bounds.
- w2_prodauto (11 probes): DFAs over a finType state space; product
  (SA*SB, card n*m), complement, language-intersection theorem; emptiness
  via connect-closure bounded reachability (nonemptyP = the meaty reflect,
  linking connect to word-runs both ways); pumping-light accepts_long_dup
  (pigeonhole over the trace). Dfa/Ops/Lang/Empty/Pump/Main (6 files).
  Audit closed with NO axioms.
Design decisions (I owned the specs until validation):
1. gauges over R:realType (+`reals` import) rather than realFieldType:
   importing `reals` adds only ~0.4s over all_algebra (which already loads
   the heavy hierarchy), so realType is faithful to the spec at negligible
   cost; kept topology/normedtype/boolp OUT to bound build cost, resolving
   the WAVE2 parenthetical.
2. prodauto states = a general finType (ordinals are the concrete
   instances), not a dependent `'I_n` field; the product's SA*SB finType has
   card n*m, realizing "bounded reachability over 'I_(n*m)" without an
   ordinal encoding. Cleaner and strictly more general.
3. ledger uses additive delta semantics (matches "delta"/"no-teleport"),
   which makes the disjoint-account swap commute UNCONDITIONALLY; the
   disjointness hypothesis is retained as the intended-domain framing
   (a true lemma, hypothesis unused in proof) — recorded honestly.
Reusable finding: `inord`/`insubd` BLOCK vm_compute (the ordinal bound proof
gets stuck); build concrete `'I_n` constants with explicit `@Ordinal n k isT`
and pattern-match transitions on named constants so `accepts` reduces.
Every file opens with `all_ssreflect all_algebra` (+`reals`/`ssrint` as
needed): 4-6 mathcomp files => ~20-30s clean rebuild = the expensive
feedback the wave is designed to test. Commits: 7c0bb96, 2a678a3, e5b3422,
c0a380c. Next id: A52 (first arm findings).

## A52 — wave-2 verdict: interface does NOT beat the build loop under
## expensive feedback (base 5/8 > verify 4/8), Jul 9
Two arms, 2 reps x 4 novel expensive-feedback tasks (900s / 40-turn
budgets), poisoning-CLEAN (all rate-limit statuses allowed_warning/connected,
no API errors; is_error hits are ordinary dune_build failures).
Per-task solves (base / verify):
  w2_frugal   1/2 / 1/2
  w2_gauges   2/2 / 0/2   <- interface HURTS
  w2_ledger   2/2 / 2/2
  w2_prodauto 0/2 / 1/2   <- interface HELPS (only place)
  TOTAL       5/8 / 4/8
VERDICT (honest, either-way headline per WAVE2): the tools+verify interface
does NOT beat the plain write/rebuild loop under expensive feedback + tight
budgets. It trades tasks: the live prover cracked the hardest 6-file task
(prodauto rep1 solved, clean DONE 39 turns/499s) where base went 0/2 (both
900s wall), but the scaffold-first (Admitted-as-scaffold + verify-before-
DONE) workflow BACKFIRED on gauges (0/2 vs base 2/2): every verify failure
is forbidden_token = real leftover `Admitted.` (confirmed: multiple per
file, not a grader artifact) that the agent never discharged because it hit
max_turns 40 (all verify fails at turns=41). Under a TIGHT turn budget the
scaffold workflow accrues admit-debt it cannot pay down — the exact inverse
of the wave-1 result (af_tools2_sonnet 7/7 at 1500s/80 turns, where verify
was the winner). The rung that won under generous budgets LOSES under
expensive-feedback + tight budgets.
BUILD-WAIT MECHANISM PROBE (sum dune_build dur_ms per attempt from
server.jsonl):
- base mean 30.0s/attempt dune_build-wait, BUT the 3 base FAILURES did 0
  dune_builds — they were killed by extended THINKING before ever building
  (frugal rep1, prodauto rep0/rep1 all reached the 900s wall with 0 builds).
  So base did NOT fail by "burning budget waiting for builds" (the wave-2
  hypothesis); it failed by over-thinking into the wall on the hard/novel
  tasks. Base SUCCESSES rebuilt heavily (gauges 18x/77s, 14x/86s).
- verify mean 35.1s/attempt dune_build-wait but with FEWER full rebuilds
  (1-5x) plus interactive rocq build{file} (2-12x, ~11-75s). The interface
  converts full-rebuild cycles into interactive builds -- roughly a WASH on
  total build-wait, not the predicted large saving.
Net: the interface neither removed the build-wait bottleneck (it shifted it)
nor improved accuracy; its scaffold workflow added a failure mode that cost
more tasks than the live prover saved. Cost ~$18 (est; killed attempts
report $0 so summed from transcript tokens+thinking). Caveats: 2 reps/task,
1 policy (sonnet), single wave; extended-thinking-induced 900s timeouts add
variance to the base absolute rate. The A/B delta (same policy, same tasks,
same budget) is the valid comparison. Next id: A53 (team-arm probe).

## A53 — wave-2 team probe: file-decomposition cracks the hardest task
## (prodauto: base 0/2, verify 1/2, team 1/1), Jul 9
Spend after both single arms ~$18 (< $40 gate), so ran w2_team_sonnet on
w2_prodauto only, 1 rep, tight per-role budgets (planner 10/200s, workers
30/500s, integrator 22/420s). Result: SOLVED (layer 4, 744 s, $1.23),
poisoning-clean. The 6-file product-automaton task — which base could not
build in either rep (0/2, both 900 s walls) — yields to file-level
decomposition, reproducing the wave-1 A47 finding that the integrator role
de-facto performs the verify sweep. Standing on the HARDEST task:
  base 0/2 · verify 1/2 · team 1/1.
Reading (reinforces A52): the interface's value is CONCENTRATED on the
hardest/largest task, where interactive proving + role decomposition beat a
single agent's write/rebuild loop. It does NOT generalize to the mid tasks
(where the single verify arm's scaffold-debt LOST 2 tasks vs base). So the
realistic-regime takeaway is nuanced but honest: expensive feedback + tight
budgets do NOT make the interface a net win (base 5/8 > verify 4/8); the
interface pays off only when task size/difficulty is high enough that a lone
agent cannot finish at all — and even then the tools+verify single-agent
form is at risk of leaving scaffold-debt, which the team's integrator
mitigates. Build-wait (team): dune_build 5×/29 s + interactive build 12×/68 s
— again the interface shifts full rebuilds to interactive builds. Total
wave-2 spend ~$19.7 (cap $60). Wave 2 complete.

## A54 — correction: wave-2 "interface loses" was a bundled-change artifact
User challenge (correct): for mathcomp-heavy tasks, memoization + warm start
should be a clean gain — how can the interface be a liability? Investigation:
(1) memoization/warm-start VERIFIED working — in w2_verify, the first open of
a heavy-prelude file (Gauge.v, Sound.v) costs ~6s, every re-open 0.4s (15x).
Clean gain, exactly as designed (A30). (2) The wave-2 loss is NOT the prover:
both gauges-verify failures hit turns=41 (40-turn cap) with reason
forbidden_token — a leftover `Admitted` in Width.v/Sound.v. (3) Root cause:
the w2_verify config bundles the prover tools AND a prompt sentence "You may
use Admitted as TEMPORARY scaffolding ... call verify{} before DONE." Under a
tight turn budget the agent sketches with Admitted, plans to discharge, runs
out of turns → gate reject. base has no such prompt so never introduces the
failure. This VIOLATES one-change-at-a-time (A52's "interface loses" headline
is retracted as imprecise). Decisive isolating arm w2_prover_sonnet (prover
tools + STRICT no-Admitted prompt, verify{} available only to confirm a clean
build) LAUNCHED: w2_prover vs w2_base isolates the prover-tool effect;
w2_verify vs w2_prover isolates the scaffold-workflow effect.

## A54 VERDICT — the MCP prover tools HELP on novel real-project tasks
w2_prover (prover tools + STRICT no-Admitted prompt) collected, 0 poisoned:
- baseline w2_base            5/8  (frugal 1/2, gauges 2/2, ledger 2/2, prodauto 0/2)
- iteration 1 w2_prover       7/8  (frugal 2/2, gauges 1/2, ledger 2/2, prodauto 2/2)
- bundled  w2_verify          4/8  (the retracted "loss")
Decomposition: prover-tool effect = +2 tasks (5/8->7/8); scaffold-prompt cost
= -3 (7/8->4/8). HEADLINE: once the A54 confound is removed, the general
prover tools ADD value on novel, contamination-controlled tasks, and
specifically cracked the HARDEST 6-file task prodauto 0/2 -> 2/2 (interface
value concentrates where the lone build loop fails). This is the clean
iteration-1 result the wave converged on; the earlier "interface loses" was
purely the bundled scaffold prompt. gauges 2/2->1/2 (one build_failed) is the
only regression, within 2-rep noise. Iteration 1 KEPT.
Wave-2 spend $22/$60. Next: multi-agent frontier — establish a CLEAN team
baseline (team with the strict-no-Admitted prover config) before A/B-ing any
multi-agent tool (signatures{}), per the corrected roadmap.

## A55 — gate: judge DELIVERED files only (+ team frugal is a genuine miss)
User noticed a forb pill in the team column. Investigation: the team frugal
attempt left `Admitted` on mmulA (matrix-product associativity, the task's
HARD proof) in the DELIVERED theories/Mat2.v — the worker couldn't close it
and the integrator didn't rescue it. (A stray scratch/Scratch.v also had an
admit and was alphabetically first in the scan — a red herring.) Gate fix
(harness, not product): the forbidden-token scan now judges ONLY files under
a coq.theory (the delivered dune project), NOT stray scratch/prototype files
— an admit in an uncompiled scratchpad must not fail a clean project.
Re-graded all wave-2 forbs: NONE flipped (all had genuine delivered-file
tokens), so the fix changes no current verdict but prevents future
stray-file artifacts and is the correct semantics. MULTI-AGENT DATA POINT:
solo w2_prover solved frugal 2/2 (closed mmulA), but the TEAM left it
Admitted — on this task the team did WORSE than solo; the integrator did not
catch the undischarged hard lemma. Relevant to the team verdict (A55 team
collection pending remaining tasks).

## A56 — team verdict + roadmap REDIRECT (evidence over the stale plan)
Clean team baseline collected (4/4, 0 poisoned). Team solved 2/4 vs solo
w2_prover which solved ALL 4 (per-task: solo frugal 2/2, gauges 1/2, ledger
2/2, prodauto 2/2; team frugal 0/1 [Admitted mmulA], gauges 0/1
[build_failed], ledger 1/1, prodauto 1/1). Team ~$1.62/attempt vs solo
~$0.90. VERDICT: multi-agent parallelism does NOT add value once the solo
prover is strong — redundant cost + coordination failures (integrator missed
the undischarged mmulA). Consistent with phase-1: teams pay off ONLY when the
lone agent cannot finish; a strong MCP makes solo sufficient at this scale.
(1-rep team caveat.)
REDIRECT: the roadmap lead was signatures{} (interface-query). But the
OBSERVED failures are NOT coordination — team frugal = hard-proof difficulty,
and BOTH gauges failures (solo AND team) are the SAME root cause: the agent
used lra/nra without importing the module -> "reference nra/lra not found",
surfaced via the rocq-server tools 5-6x/attempt (a hint CAN reach it).
signatures{} would not touch any observed failure -> NOT built (no supporting
bottleneck; discipline: tools need an observed bottleneck + measured delta).
Evidence-grounded next rung instead: a MISSING-IMPORT HINT (general error
enrichment) — when a proof references an arithmetic tactic whose module isn't
imported, suggest the exact Require. Addresses the one thing blocking the
strong solo prover (gauges). Wave-2 spend $27/$60.

## A57 — hint A/B was variance + a trigger bug; the NOISE-FLOOR finding
w2_prover2 (prover + missing-import hint) = 4/8 vs w2_prover 7/8. NOT a hint
effect: ledger 2/2->1/2 and prodauto 2/2->1/2 dropped, but those tasks use
NO lra/nra so the arithmetic hint physically cannot touch them -> the swing
is pure Sonnet run-to-run variance. Mechanism check: the hint fired 0x in
the prover2 gauges attempts despite 3-4 'reference lra/nra not found' errors
-> the A56 trigger (sentence FIRST WORD == tactic) never matched, because
tactics appear mid-sentence (Proof. nra. / by nra). FIXED (A57): trigger on
the error message's unfound reference; re-smoked, fires on the real message.
DECISION: KEEP the hint (correct, general, low-risk error enrichment now
firing) but its SOLVE-RATE effect is UNMEASURABLE at this sample size.
METHODOLOGICAL FINDING (important): at 2 reps x 4 tasks = 8 attempts with
nondeterministic Sonnet, the noise floor is +-2 tasks. Only COARSE effects
resolve (prover tools +2, team -2); FINE tool refinements (a single hint)
sit below the floor. Measuring hint-level deltas needs many more reps/tasks
(future work). Not spending more on noisy 8-attempt hint A/Bs. Wave-2 spend
~$34/$60. Phase 2 concludes here.

## A57b — REFRAME: phase 2 is an EVALUATION, keep only relative-path fix
Per user: reframe the arc as EVALUATION of rocq-mcp-evolve on
autoformalization tasks, not tool evolution. Kept product change =
relative-path resolution for open/build (A42/A48 — genuine usability fix,
open-success 8.5%->47%). REVERTED the missing-import hint (A56/A57): its
solve-rate effect was below the +-2-task noise floor, so under an
evaluation framing it is not a justified product addition. Product diff vs
main is now ONLY the relative-path resolution (+ files_server, which is
harness scaffolding, no public_name, not shipped). Suite green.

## A58 — SOTA sibling rocq-mcp comparison: no help here, but NOT blind
Ran the baseline + the sibling rocq-mcp (SOTA) arm, w2_sota_sonnet, 4 tasks
x 2 reps, via the instant-handshake prewarm proxy. CONNECTION HEALTH: 0/8
attempts showed a `pending` handshake (phase-1 startup race did NOT recur —
proxy works). RESULT: 2/8 solved vs base 5/8, vs rocq-mcp-evolve 7/8; all 8
SOTA attempts ran to the 40-turn wall (0 early convergences vs several for
base/evolve).

RETRACTION (same session): my first reading was "the SOTA REPL tools cannot
see the agent's own multi-file symbols." That is WRONG. Verified against the
sibling source (rocq-mcp/src/rocq_mcp/server.py): it is fully dune-aware —
_PROJECT_MARKERS includes dune-project, and _parse_dune_flags runs
`dune coq top --toplevel echo --no-build` per coq.theory to derive the real
-Q/-R load paths. Measured on the transcripts: 129/204 (63%) of the agent's
rocqmcp calls returned success:true, and queries resolved the projects' OWN
symbols (e.g. the `dfa` record printed back). The `not a defined object`
lines I over-read were the agent querying names not-yet-defined/built at
that moment — ordinary mid-development friction. The delivered projects
failed for ORDINARY reasons: 3 build_failed, 2 probes_failed, 1 leftover
admit (forbidden_token). Not tool blindness.

HONEST VERDICT: on this dune / 40-turn testbed, adding the sibling server
did not help and measured worse (2/8). But the finding is WEAK and
CONFOUNDED: (a) ±2-task noise floor makes an 8-attempt gap soft; (b) the arm
carries its own prompt + 11-tool surface, so base->SOTA is not a clean "just
add the server" isolation; (c) every attempt exhausting the turn budget
suggests the interactive tool surface invited a proof-stepping loop that did
not convert to solved projects under a tight budget, but I did NOT cleanly
isolate that mechanism. Reported as such (dashboard Findings + three-way
overall table). NO product change follows from this arm. LESSON (methodology):
do not infer a mechanism from a handful of error strings — read the other
server's source and measure call-level success before attributing a cause.

## A58b — prompt-asymmetry hypothesis TESTED and REFUTED; SOTA verdict final
After A58, a config audit found the SOTA arm's system prompt was a generic
tool list while the prover arm's was a tuned recipe (write skeleton ->
dune_build -> open each theorem -> finisher-first -> paste back). Hypothesis:
that asymmetry, not the server, explained SOTA 2/8. TEST: archived the
generic-prompt run to logs/autoform/w2_sota_unfair and re-ran the full arm
with a symmetric recipe prompt mapped to the sibling's own tools
(rocq_start / rocq_step_multi battery-first / rocq_check / paste back).
RESULT: 1/8 (ledger rep0 only) — WORSE than the generic prompt's 2/8.
Hypothesis refuted: two independent prompt variants score 2/8 and 1/8, both
below baseline 5/8 and far below evolve 7/8. Handshake health 0/16 pending
across both variants.

Mechanisms (from transcript analysis, session audit): (a) rocq_compile_file
drops .vo files into the dune source tree, breaking subsequent dune_build —
a real SOTA-x-dune interaction defect for this workflow; (b) sibling
sessions see only the file's own imports, so the recommended tactic
batteries (lia/lra/ring) often cannot fire — evolve preloads
Lia/Lra/zify/algebra-tactics, a genuine product difference; (c) the
interactive surface invites proof-stepping that exhausts the 40-turn budget
before files are complete (gauges rep0: 53/56 tool calls interactive, zero
.v files written, zero dune_build; all 16 SOTA attempts across both variants
hit the turn wall); (d) two attempts wrote Admitted skeletons despite the
explicit ban (forbidden_token).

RESIDUAL CAVEATS (honest): the SOTA allowlist omitted mcp__files__verify
(the grader-aligned pre-DONE check the prover arm had) — a harness
asymmetry that penalizes SOTA, though it cannot explain a 6-task gap; the
runner passed ROCQ_WORKDIR but the sibling reads ROCQ_WORKSPACE (env var
dead; load-path auto-detection from file paths did the work — confirmed
functional in transcripts); +-2-task noise floor blurs magnitudes but not
direction replicated twice. DECISION: no third run — at this noise floor it
cannot flip a replicated 6-task gap; SOTA-comparison spend $20.79, phase-2
total ~$55/$60 cap. VERDICT: on multi-file dune autoformalization under
tight budgets, rocq-mcp-evolve's file-oriented loop (build{file} diagnosis
+ preloaded finishers + paste-back) beats both no-MCP and the SOTA
sibling's REPL-oriented surface. No product change follows (the evaluation
framing holds; relative-path resolution remains the only product diff).

## A59 (candidate, not implemented) — import-echo on auto_close/check success
User question surfaced a real product gap, verified in source + logs.
MECHANISM: open{} preloads the session with Stdlib Lia/Lra/Psatz (+ mathcomp
zify/lra when the file mentions mathcomp) — rocq_agent_session.ml:102-136 —
so the session env is a strict SUPERSET of the file env. auto_close/try/
check succeed in the enriched env and reply only "`nra.` closes it —
COMMITTED" with no import advice. candidate.v is protected (write_candidate
prepends the preload Requires, :233-247) but the paste-back-into-own-file
workflow (the autoform recipe) is not. MEASURED BITE in the winning
w2_prover run: 10 build errors "reference lia/nra/... was not found" across
transcripts (each costs an expensive rebuild cycle), and the arm's SINGLE
failure (gauges rep0) is exactly this — delivered Gauge.v calls nra. x3
with no Psatz/zify import; gate error verbatim. Evolve was plausibly 8/8
without the gap. Grading unaffected (gate rebuilds fresh in isolation; 7/8
sound). PROPOSED CHANGE (next measured A/B, NOT shipped): on auto_close/
check success, if the winning script uses a preloaded-only tactic not
importable from the file's own prefix, append the exact Require line to the
reply. Fires on success (proactive), general, OCaml-only. Strictly better
scoped than the reverted error-message hint (A56/A57: fired after failure).

## A59b (future work) — pre-registered fair-SOTA protocol
If the comparison is rerun: (1) mechanical parity — SOTA allowlist includes
files.verify; pass ROCQ_WORKSPACE (not ROCQ_WORKDIR); (2) prompt parity by
one of two pre-registered designs: (A) identical minimal prompt, tools
described only by their own docstrings (measures affordance), or (B) each
server's prompt taken VERBATIM from its own README best practice (measures
product-as-shipped; the sibling's README documents rocq_start+rocq_check
iteration and keep_vo semantics — its prompt writes itself, removing the
experimenter as author); (3) power: >=4 reps/arm, decision rule |delta| >
noise floor fixed in advance; (4) allegiance control: freeze configs before
launch; reciprocal test = run evolve on the sibling's benchmark; ideally a
neutral party runs it. Cost ~$20-40; NOT run now (cap ~$55/$60 spent,
direction already replicated across two prompt variants).

## A59 IMPLEMENTED — import-echo on proof completion
Shipped in the session server (complete_msg): if the committed script uses
lia/nia/lra/nra/psatz and the file's prefix lacks a providing Require, the
PROOF COMPLETE message appends the exact lines to add (Stdlib Lia/Lra/Psatz;
mathcomp zify+lra when the bridge was preloaded). Token-based heuristic:
may over-echo (Require Import is idempotent), never under-echoes what the
session preloaded. ROCQ_IMPORT_ECHO=0 disables (for later isolated A/B);
harness mode (ROCQ_ENV_V2) excluded. Smoke 3/3: echo fires on lia-needing
proof without import; silent when the import exists; silent when the proof
does not use the family. NOTE: discovered on this benchmark, so the A60
rerun measures evolve-as-shipped INCLUDING it — it is not the echo's A/B.

## A60 — PRE-REGISTERED fair three-way protocol (af2_*), frozen before data
Question: baseline vs +rocq-mcp-evolve vs +rocq-mcp(SOTA) with authorship
bias minimized. Protocol, registered before any af2 attempt runs:
1. NO system prompt (flag omitted). One IDENTICAL task prompt template for
   all arms: task + machine-checked grading rules + open-book probes + a
   {readme} slot.
2. Documentation rule: each treatment's {readme} = its server's OWN shipped
   docs, verbatim — evolve: src/session_server/README.md (new; aggregates
   only what its shipped tool descriptions already say); SOTA: the sibling
   README's Tools + Recommended-usage sections verbatim (operator/deploy
   sections excluded; harness/sota_readme_excerpt.md). Baseline: empty slot.
3. Common environment: identical files sidecar for ALL arms (write/read/
   list/dune_build/verify — the gate-mirror goes to everyone). Treatments
   add their server's FULL shipped tool surface (evolve 10, sibling 11 incl
   rocq_diag — the previous arm's 10-tool allowlist is corrected).
4. Env fixes: sibling gets ROCQ_WORKSPACE (ROCQ_WORKDIR was dead). Evolve
   as-shipped includes the A59 import-echo (on).
5. Budgets identical: sonnet-5, 40 turns, 900s, 4 reps per task per arm.
   Tasks: the 4 validated + triadic (IMO-2025-P4-derived, renamed) IF its
   reference passes the gate before launch, else 4.
6. DECISION RULE (fixed now): per arm-pair, |delta solved| >= 3 (of 16-20
   attempts) = signal; <= 2 = within noise; report per-task layers besides.
   Costs/time reported as secondary, cost recovery per A-trail.
7. Smoke attempts (run-ids af2_smoke_*) are excluded from analysis.
8. Prior w2_* runs are NOT comparable to af2_* (different prompt protocol);
   no cross-protocol deltas will be claimed.
Freeze = the commit introducing this entry. Budget ~$60-75.

## A60 correction (pre-launch, pre-data) — evolve ships 9 prover tools
Smoke revealed `search` is NOT in the session server's default enabled set
(ROCQ_ENABLE_TOOLS default omits it) — evolve-as-shipped is 9 prover tools,
not 10. Corrected the af2_evolve allowlist and the README (which documented
search) to match the shipped default; no env override (as-shipped rule).
Recorded before any non-smoke af2 attempt ran; smokes excluded per rule 7.

## A61 — triadic task validated, joins the dataset (5th task)
New task `triadic` (derived from a 2025 olympiad number-theory problem;
renamed framing — "chorus"/"triad"/"tstep" — no olympiad mention anywhere in
spec/probes/reference, verified by scan): chorus n = proper divisors in
increasing order, triad = three largest, tstep = their sum. Required
theorems BOTH at full generality (no fallback rung used):
tstep_fixed (m odd, 5∤m, 0<m -> tstep (6m) = 6m) and tstep_shrink_odd
(n odd, 1<n -> tstep n < n). Reference gate-validated INDEPENDENTLY
(re-run by the orchestrator): solved:true, 14 probes, audit closed,
build ~17s. Well-posedness rule satisfied. af2 arms run 5 tasks × 4 reps.

## A62 — af2 VERDICT (pre-registered fair protocol): tool value is
## guidance-conditional; SOTA below baseline under both protocols
Ran the frozen A60 protocol: 3 arms x 5 tasks x 4 reps = 60 attempts, no
system prompt, per-server shipped READMEs, identical sidecar/budgets.
Health: 40/40 treatment attempts connected (0 pending); no API/rate-limit
poisoning (the 15-20 "errored" results per treatment arm are all
error_max_turns — the CLI flags the 40-turn cap as an error; benign).

RESULTS (solved / $ per solved, cost recovered for wall-killed attempts):
  af2_base    9/20  $2.52   (frugal 3/4, gauges 2/4, ledger 3/4, prodauto 1/4, triadic 0/4)
  af2_evolve  7/20  $3.32   (frugal 3/4, gauges 0/4, ledger 3/4, prodauto 1/4, triadic 0/4)
  af2_sota    2/20  $16.31  (frugal 0/4, gauges 1/4, ledger 1/4, prodauto 0/4, triadic 0/4)

PER THE FROZEN RULE (|delta solved| >= 3 = signal):
1. evolve vs base: -2 -> WITHIN NOISE. The w2 advantage (7/8 vs 5/8) does
   NOT survive removal of usage guidance. HONEST HEADLINE: the measured
   value of the prover tools is CONDITIONAL on guidance.
2. sota vs base: -7 -> SIGNAL. The sibling lands below baseline under the
   fair protocol too (replicates w2 direction with clean provenance).
3. evolve vs sota: +5 -> SIGNAL. Evolve beats the sibling under both
   protocols.

MECHANISMS (measured): (a) budget-shape asymmetry — tool-rich arms are
turn-bound (evolve 17/20, sota 20/20 hit the 40-turn cap; each tool call
costs a turn) while base is wall-bound (10/20 killed at 900s, i.e. base
effectively gets ~2x the wallclock; evolve mean wall 394s vs base 771s).
This asymmetry was inherited from w2 where guidance taught turn economy;
pre-registered, so reported as a caveat, not patched post hoc. (b) unguided
agents drive the interactive tools sentence-by-sentence: step 7.0/attempt
vs auto_close 0.9/attempt — the READMEs' workflow section did not overcome
default behavior. (c) without the strict never-admit push, evolve leaves
Admitted scaffolds and runs out of turns: 7 forbidden_token failures
(gauges 3/4, triadic 4/4). (d) triadic went 0/12 across ALL arms —
a genuinely hard, discriminating task (reference validated; kept).
(e) import-echo (A59) fired 16x in production replies.

IMPLICATIONS (candidates for future MEASURED changes, not shipped now):
make the winning workflow the path of least resistance inside tool
RESPONSES rather than depending on prompts — e.g. open{} suggesting
auto_close-first, turn-economy nudges, verify-before-done reminders in
late-session replies. The evaluation's product lesson: shipped tool
descriptions alone do not steer a strong model to the workflow that wins.

## A62b — batch capability exists but is unused (user question, measured)
The interface already supports fix-the-whole-proof-in-one-turn: check{}
(whole script, repair-from-failure), multi-sentence step{}, try{} (8
candidates/call). Measured usage: check = 2 calls across all 20 unguided
attempts and 0 across the guided w2 arm; step median 1 sentence/call (56%
single-sentence; max 10 proves capability discovery); try 2.7 of 8
candidates. Hardest fact: 0% of 1128 assistant turns (both arms) contained
more than one tool call — in headless claude -p, sonnet issues exactly one
tool call per turn, so turn budget == tool-call budget. The turn-burn is a
STEERING failure, not a capability gap: the one-sentence loop is the
model's natural habit and nothing in the response shape pushes toward the
batch forms. A63 candidates (one-variable A/Bs, not shipped): step's
single-sentence success reply nudging toward check; auto_close folded into
open; late-session turn-economy nudges in replies.

## A63 — PRE-REGISTERED evolution arc: wall-only arena + rung ladder
User green-lit resuming the phase-1 evolution method on this benchmark
(~$150 envelope). ARENA FIX (motivated by A62b: turns == tool calls, a CLI
artifact that structurally punishes tool-rich interfaces while $ and wall
are measured directly): max_turns raised to a safety-only 200 for ALL arms;
the 900 s wall is the binding budget. Everything else inherits the frozen
A60 protocol (no system prompt, per-server shipped docs, identical sidecar,
5 tasks x 4 reps, |delta solved| >= 3 = signal). Re-baseline af3_base +
af3_evolve (~$45); af2_sota stands as the SOTA reference (not our product
to evolve). af2 and af3 numbers are not directly comparable (arena change).

RUNG LADDER (order fixed now; one change per rung; keep/revert by the
rule; all rungs are GENERAL in-band product behavior, no orchestration):
  R1 hole-visibility — surface remaining admit/Admitted holes (count +
     locations) in build{}/completion replies; attacks the 7-forbidden
     failure class (A62 mechanism c).
  R2 turn-economy steering — single-sentence step success replies note
     that the rest of the proof can be submitted in one check{} call;
     open{} reply names auto_close as the first move; attacks batch
     non-use (A62b).
  R3 open+finish fusion — open{} runs the finisher portfolio on the
     opened goal automatically (merges the two most common consecutive
     calls; saves a round-trip per theorem).
Each rung: implement -> af3_evolve_rN (20 attempts) -> compare vs
af3_evolve AND af3_base -> keep/revert -> next.

## A64 — R1 IMPLEMENTED: scaffold visibility in build{} replies
Evidence: 15 of 16 forbidden-token eval failures across af2/af3 were
admit/Admitted (+1 Abort in a leftover Scratch.v), and build{} was ACTIVELY
misleading — Admitted compiles, so a file of stubs returned "BUILD OK,
no holes". Change (one rung): build{} now appends a WARNING with the count
and 1-based line numbers of admit/Admitted/Abort tokens in the file's
comment-stripped text; description + README row updated truthfully.
General product behavior (any Rocq user wants to know a "green" file has
unproven stubs); ROCQ_HOLE_WARN=0 disables for A/B isolation. Smoke 3/3
(fires with line number; comment mentions don't count; silent on clean
files). Suite green (A 57/0, C, D). Measured next as af3_evolve_r1
(20 attempts) vs af3 baselines under the frozen |delta|>=3 rule. Note:
the README row change is part of the rung (as-shipped docs must describe
the tool truthfully); the task prompt's grading rules are unchanged.

## A63 addendum — gate build budget = 1800s, exceeding = build_failed
af3_base ledger rep1's delivered project does not finish `dune build` in
1800s (the task reference builds in ~20s; no other attempt in any arm ever
needed >600s). Policy, applied uniformly from here on: the gate's fresh
build gets 1800s; exceeding it grades build_failed (layer 1). The attempt's
row is appended with that verdict (agent sample preserved, not resampled).
af3 BASELINES FINAL: base 9/20, evolve 13/20 -> delta +4 = SIGNAL per the
frozen A60/A63 rule. The af2 null is attributed to the turns==calls arena
artifact: with the wall as the only binding budget, the unguided prover
tools BEAT baseline (prodauto 0/4 -> 3/4, third replication of the
hardest-task pattern) at lower wall (570s vs 746s/attempt).

## A64 VERDICT — R1 REVERTED (no signal; wrong premise for the class)
af3_evolve_r1: 12/20 vs af3_evolve 13/20 (within noise; keep required
|delta| >= 3), vs control 9/20 (+3). Health clean (20/20 connected).
Class movement: forbidden_token 5 -> 4 (unmoved within noise), probes 1->3.
The warning FIRED in only 6/20 attempts — it lives on build{}, a call
agents don't reliably make on the offending file at the right moment.
Deeper mechanism read: the surviving scaffold failures concentrate on
triadic at wall-kill — agents KNOW admits are forbidden (it is in the task
prompt); they run out of TIME on hard proofs. Visibility does not buy time.
Feature reverted per the rule (code + README row; config and run logs kept
as the record). LESSON: under a wall-only arena, in-band TEXT nudges have
a weak delivery channel and target information gaps that may not exist;
MECHANICAL round-trip savings are the lever that buys time.

## A65 — rung reorder (recorded before running): R3 before R2
R1's lesson: text-nudge rungs depend on model compliance and delivery
timing; mechanical rungs do not. R3 (open{} runs the finisher portfolio on
the opened goal automatically — merges the two most common consecutive
calls, ~6 open/attempt measured) saves a full model round-trip per theorem
REGARDLESS of agent behavior, and under the wall arena time is the binding
budget. Running R3 next; R2 (check{} steering text) deferred, run only if
budget remains. Each rung remains its own A/B vs af3_evolve under the
frozen rule.

## A65 IMPLEMENTED — R3: open-side finisher fusion
Change (one rung): open{} runs the auto_close portfolio on the freshly
opened goal automatically — easy goals return already COMMITTED/COMPLETE
with the paste-back script (+ import-echo), hard goals return with "no
finisher applies — do structural work". Mechanics: the finisher core is
factored out of auto_close{} into run_finishers (shared; auto_close's own
contract unchanged). Deletes the most common round-trip pair (open ->
auto_close; ~6 opens/attempt, one full model round-trip each) REGARDLESS
of agent compliance. ROCQ_OPEN_AUTOCLOSE=0 disables. Tests: legacy
per-tool contract tests pinned with the toggle off; new A15 check pins the
fusion (open returns "ran automatically" + PROOF COMPLETE on an easy
goal). Suite 60/60 green. Measured as af3_evolve_r3 vs af3_evolve under
the frozen rule.

## A66 — DESIGN CONSTRAINT (user steer) + communication-first replan
User: the arc is over-committing to the auto-finisher (proof automation
that could be developed independently of MCP) instead of improving the
LLM<->prover COMMUNICATION. Accepted and recorded as a constraint:
evolution rungs must improve the channel — what the prover tells the
model, what the model can ask, how much one exchange accomplishes. The
automation CORE (portfolio strength, hint synthesis) is out of scope for
this arc; R3 is defended only narrowly (it adds zero automation — it moves
WHERE existing automation runs, i.e. exchange density) and is the LAST
automation-adjacent rung; it finishes and is judged by the rule.

Re-planned ladder (communication-native, evidence first):
  C1 unknown-reference recovery — measured: agents HALLUCINATE library
     names (sorted_ltn_iota, iota_add, filter_pred0_eq in triadic
     transcripts) because search{} is off in the shipped default and their
     only namespace knowledge is training memory. Change: when a tactic/
     script fails with "The reference X was not found", the server queries
     the LOADED namespace for near-matches (suffix/edit-distance/head
     constant) and attaches "closest loaded lemmas: ...". Pushes prover-
     side knowledge into an exchange that already happens — the A62b
     lesson (response-side > new tools the model won't call).
  C2 statement falsification — autoformalization agents prove their OWN
     statements; a wrong statement burns wall on an unprovable goal.
     Change: for computable/decidable goals, the server tries small
     instances (vm_compute) and reports a counterexample BEFORE the agent
     invests ("false at n=0"). Prover computes, model learns.
  C3 goal-diff rendering after step/check — exchange economy: show what
     changed, not the full goal, with the full form on demand.
Each: one rung, 20 attempts, frozen |delta|>=3 rule vs af3_evolve.

## A67 — C2 pulled forward (user steer: "push it"); design registered
LINEAGE: C2 is the QuickChick idea — property-based falsification —
relocated into the MCP channel. QuickChick itself is not installed in the
switch and needs per-type generator derivation; v1 instead does BOUNDED
ENUMERATION over the goal's leading nat/bool binders + vm_compute (zero
setup, covers the mathcomp bool-reflection style our tasks use). A future
version may delegate to QuickChick when present for richer types.

DESIGN (registered before implementation):
- Trigger: the "no finisher applies" site in run_finishers — fires from
  auto_close{} and (while R3 lives) open{}'s fusion, i.e. exactly when an
  agent is about to invest in a hard goal. No new tool: response-side.
- Statement source: the last lemma-statement sentence of the session
  prefix (open loads up to the statement, so it is the prefix's tail).
- Instantiation: parse leading `forall`-binder groups typed nat/bool
  (skip goals with other binder types or name shadowing in the body —
  silent no-op). Enumerate small tuples (nat in {0,1,2,3,5,6}, bool both;
  cap ~12 instances, total prover budget ~5s).
- Soundness: for each instance, SPECULATIVELY attempt to prove
  `~ (<instantiated statement>)` with a small script battery
  (vm_compute + intro/specialize(erefl)/discriminate patterns for
  is_true/eq/implication chains). Only a KERNEL-CHECKED refutation counts;
  anything else = silence. No false alarms by construction.
- Reply on hit: "COUNTEREXAMPLE (kernel-checked): the statement is FALSE
  at (m := 2) — fix the statement or your definitions before proving."
- ROCQ_FALSIFY=0 disables (A/B isolation). General product value: any
  user proving their own statements (the autoformalization regime) is
  warned before burning time on unprovable goals.
- Order note: C2 measured BEFORE C1 per user steer (recorded pre-run;
  both remain single-change rungs vs af3_evolve under the frozen rule).

## A67b — CORRECTION: C2 SHELVED (misread steer; the critique was the point)
I misread the user's "push it" as prioritizing C2. Their actual point, now
explicit: C2 REINVENTS an existing tool (QuickChick), repeating the
auto-finisher mistake (A66); and its v1 scope (nat/bool enumeration) does
not reach real-life goals — the dataset itself quantifies over realType,
finType automata, ssrint, records, where small-instance enumeration is
useless or impossible. C2 is shelved, not run. If falsification ever
matters, the right form is QuickChick INTEGRATION when installed —
dependency plumbing, out of scope for this channel-research arc. The
ladder returns to A66's evidence order: C1 (unknown-reference recovery —
pure information flow: the loaded namespace is something only the prover
side knows; no new proof capability) next after R3's arm lands, then C3
(goal-diff). Lesson logged: when the user names a resemblance to an
existing tool, it is a warning, not a feature request.

## A65 VERDICT — R3 REVERTED (best point estimate, below the bar; wrong-time automation)
af3_evolve_r3: 15/20 (frugal 4/4, gauges 4/4, ledger 4/4, prodauto 3/4,
triadic 0/4; all 5 failures = triadic/scaffold class), wall 564s/att,
health 20/20. vs af3_evolve 13/20: +2 — BELOW the frozen |delta|>=3 keep
bar -> REVERTED per the rule, despite being the best arm measured so far.
MECHANISM (decisive): 70 open replies carried the fused finisher outcome;
exactly 1 closed a goal. At open time the goal is the raw statement,
BEFORE the intros/structural work the portfolio needs — the automation
ran at the wrong time. Any real effect likely came from the informational
half ("no finisher applies — do structural work" skipping a doomed
auto_close round-trip), i.e. the CHANNEL half — consistent with the user's
A66 critique. The run_finishers factoring is kept (pure refactor;
auto_close unchanged). Trail continues at C1 (unknown-reference recovery).
Arc spend ~$116/$150.

## A68 — C1 CANCELLED before running: it already ships (and fired)
Implementing C1 exposed, via its own smoke test, that unknown-reference
recovery ALREADY EXISTS in the server: with_suggestions (near-miss lemma
names on "X was not found", ON by default) — a phase-1 feature I proposed
to rebuild. Worse for C1's premise: in the af3_evolve triadic failures
cited as its evidence, 7 of 11 not-found errors ALREADY CARRIED the
"near-miss lemmas that DO exist" suggestions — the information was
delivered and did not convert those attempts. My evidence pass had grepped
for the errors without reading the replies. The duplicate implementation
is removed (suite 57/57 green); nothing was measured.

Same check applied to C3 (goal-diff): goals_block_compact ?prev already
renders hypothesis +/- deltas — ALSO shipped in phase 1 — but it is OFF by
default (ROCQ_RENDER=compact opt-in) with no recorded measured reason:
the one surviving, non-duplicate, channel-pure rung candidate is flipping
that default (exchange economy: goal reprinting dominates reply tokens in
long sessions).

FULL LADDER ACCOUNTING (the user's critique, vindicated three ways):
finisher fusion = automation relocation (reverted, 1/70 closes); C2 =
QuickChick reinvention (shelved); C1 = duplicate of with_suggestions
(cancelled); C3 = duplicate of goals_block_compact (only its DEFAULT is
new). METHODOLOGY RULE, binding from now on: before proposing any rung,
(1) read the shipped feature surface for prior art (including THIS
codebase), and (2) verify the failure evidence at the REPLY level, not
the error level. Remaining failure mass (triadic 0/4, scaffold-at-wall)
is difficulty/time-bound — no channel rung targets it credibly.

## A69 — PRE-REGISTERED (before running): C3-default efficiency rung
Change (one line): render_compact becomes the DEFAULT (opt-out
ROCQ_RENDER=full) — the shipped diff renderer (first goal + hypothesis
+/- deltas vs the previous state; `state` still renders full, so detail
stays one call away) stops being dark. Motivation: exchange economy —
goal reprinting dominates reply tokens in long interactive sessions; the
feature exists, is phase-1 tested, and only its default is new.
AMENDED DECISION RULE for efficiency rungs, fixed NOW: keep iff
|delta solved| <= 2 vs af3_evolve (accuracy within noise) AND
(cost/solved OR wall/attempt improves >= 20%); revert otherwise —
including any solved drop >= 3, which is an accuracy regression
regardless of savings. Measured as af3_evolve_c3, 20 attempts.

## A70 — PRE-REGISTERED: af3_sota (fair SOTA arm under the wall-only arena)
User request: complete the three-way under the fairest protocol. Config =
af2_sota with max_turns 200 (everything else already fair per A60: no
system prompt, sibling README excerpt verbatim, ROCQ_WORKSPACE fix,
full 11-tool surface, prewarm proxy, identical sidecar/tasks/reps).
Checks on landing: 0-pending handshake audit, poisoning check, 1800s gate
policy. Comparison per the frozen |delta solved| >= 3 rule vs af3_base
and af3_evolve. Launches after the C3 arm clears (no CPU contention in
measured walls). Cost ~$35 — takes the arc past the $150 envelope
(~$190 total), explicitly user-authorized.

## A71 — three-objective ledger for reverted rungs (user challenge)
User: why park evolutions that were accuracy-flat but token/time wins?
Answer in two parts. (1) PROCESS ERROR, acknowledged: the A63 keep rule
operationalized only accuracy despite the arc's three stated objectives;
efficiency columns were not published with the rung verdicts. Fixed: full
ledger now in the trail, and A69's efficiency criterion applies to all
future rungs. (2) DATA: nothing efficiency-positive was parked.
  af3_evolve     13/20  $40.75 total  $3.13/solved  570s/att
  af3_evolve_r1  12/20  $46.13        $3.84         611s   (worse on all 3)
  af3_evolve_r3  15/20  $41.45        $2.76         564s
R3's -12% cost/solved is the noise numerator (+2 solves) over flat total
cost (+2%) and flat wall (-1%): not a real efficiency win; reverts under
the A69 rule as well. KEY REFRAME (the durable lesson): the +-3 noise
floor is an ACCURACY limitation only — cost and wall are continuous and
resolve ~10-20% effects at n=20. Efficiency rungs were measurable all
along; the parked turn-economy/batching ideas are re-classified as
efficiency rungs, measurable at current N under A69.

## A71b — retro-audit: all prior rounds under the three-objective lens
No verdict flips. (1) w2 prover keep STRENGTHENS: accuracy +2 was at the
n=8 floor, but cost/solved -26% and wall -50% make it a three-objective
sweep. (2) w2 team unchanged (lost accuracy AND cost). (3) A57 hint
revert shares the A71 accuracy-myopia (efficiency never measured) —
practically moot, superseded by the shipped import-echo (A59). (4) af2
evolve is the CAUTION: naive three-objective judging would have declared
a FALSE wall win (-49%) that was turn-cap censoring, not speed; the
accuracy-first skepticism is what exposed the arena bug instead. RULE
ADDENDUM to A69, binding: efficiency comparisons are only valid between
arms whose attempts end for intrinsic reasons — any arm with >10% of
attempts ended by a budget guillotine (turn cap / wall kill differential
vs its comparator) must flag wall/cost as censored. (5) R1/R3 unchanged
(A71). (6) Phase 1 was already three-objective-native.

## A72 — PRE-REGISTERED: Mistral generalization probe (user-provided key)
Question: does the af3 result (evolve +4 over baseline, unguided, wall-only
arena) GENERALIZE across model families? The harness was claude -p-bound;
a new model-agnostic MCP driver (harness/mistral_driver.py) speaks MCP
stdio to the same servers and Mistral's function-calling API: same tasks,
gate, budgets, task prompt, README slot, allowlist, and results.jsonl row
shape (dashboard-compatible). Smoke PASSED (handshake -> tool call ->
grounded reply). API key stored OUTSIDE the repo (~/.mistral_api_key, 600);
rotation recommended after the run since it transited chat. Cost column
uses approximate public prices (flagged indicative).
ARMS (after the current queue: C3 arm -> af3_sota; no CPU overlap in
measured walls): mst_base + mst_evolve = af3_base/af3_evolve configs,
model mistral-medium-latest, 5 tasks x 4 reps, ~$10-20 on the user's key.
Decision rule: the frozen |delta solved| >= 3 within the Mistral pair;
cross-family comparisons reported descriptively only (different tokenizer,
pricing, latency profile — not arms of one experiment).

## A69 VERDICT — C3 REVERTED: the token economy INVERTED
af3_evolve_c3: 13/20 (accuracy +0, within noise), but cost/solved +27%,
wall +10%, input-side tokens 109M -> 145M (+33%), output +15%. Censoring
comparable (7/7 wall-killed both arms), health 20/20. Under the A69 rule
(needed >=20% improvement): REVERT — and the mechanism is the story:
compact hypothesis-delta replies withheld context the model was actually
using, so it bought the information back with MORE round-trips, each
re-reading the whole conversation. Per-reply token savings were swamped by
per-attempt turn inflation. LESSON (AI-native design principle, measured):
INFORMATION DENSITY PER EXCHANGE BEATS TOKENS PER REPLY. The phase-1
opt-in default is retroactively justified with data; rationale recorded in
the code. ARC RUNG LEDGER COMPLETE: R1, R3, C3 measured and reverted;
C1, C2 cancelled on prior art. The shipped server stands as a measured
local optimum for this benchmark/model tier.

## A70 VERDICT — fair three-way: BOTH MCPs beat baseline; prior SOTA
## verdicts were arena-confounded (retraction-grade update)
af3_sota: 12/20 (frugal 4/4, gauges 4/4, ledger 4/4, prodauto 0/4,
triadic 0/4; failures: 4 probes, 3 build, 1 forbidden), $5.73/solved
(recovered), wall 717s/att, handshake 20/20 connected, 0 turn caps,
end-modes comparable (10 wall-killed vs evolve 7 — flag: mild censoring
asymmetry on wall/cost comparisons).

THREE-WAY UNDER THE FAIR ARENA (one protocol, one arena, frozen rule):
  base 9/20 · evolve 13/20 (+4 SIGNAL) · sota 12/20 (+3 SIGNAL)
  evolve vs sota: -1 -> STATISTICAL TIE on accuracy.

RETRACTION-GRADE UPDATE: every prior "SOTA hurts" verdict (A58/A58b 2/8 &
1/8; A62 2/20, -7 signal) carried the same arena artifact that produced
evolve's af2 null — turn caps punish call-hungry interfaces, and the
sibling's REPL surface is the calliest of all. Those numbers remain true
OF THEIR ARENAS; they do not describe the interface's value. Under
wall-only budgets the interface CLASS wins: both rocq MCPs beat the
no-MCP baseline with signal. Evolve's real, surviving edges: cost/solved
-45%, wall -21%, and prodauto 3/4 vs 0/4 (the hardest task; the one
capability difference that never flipped under any arena). Sota shows
fewer scaffold failures (1 forbidden vs evolve's 5).

META: the single most valuable steer of this whole phase was the user's
repeated insistence on fairness — every headline that later flipped
(evolve af2 null, SOTA "blindness", SOTA "loses") fell to a fairness
audit, and the surviving result is stronger for it. Spend: af3_sota ~$69
recovered (wall-only attempts run longer); phase total ~$260.

## A72 VERDICT — Mistral probe: floor effect at the medium tier
mst_base 0/20, mst_evolve 0/20 (all build_failed) — mistral-medium-latest,
af3 protocol, ~$50 on the user's key (my $10-20 estimate was WRONG: long
turn counts, median 58-134, x full-context re-reads). DRIVER EXONERATED
before concluding: agents wrote real dune projects, base called dune_build
266x / verify 55x, evolve exercised the prover hard (975 step, 271 build,
195 open) — the plumbing is clean and the run is valid. FAILURE CLASS:
Gallina/Ltac SYNTAX errors dominate, with the phase-1 Lean-ism signature
([ltac_use_default], def_body) and a literal `sorry` in delivered code.
CONCLUSION: mistral-medium is below this benchmark's syntax floor at 900s;
0-vs-0 gives zero discriminative signal about the interface (floor effect,
same regime the IMO-full tasks were rejected for). The cross-family
generalization question stays OPEN — answering it needs a stronger Mistral
tier (mistral-large ~$25-40 for a 5-attempt base-arm floor probe;
magistral-medium similar) or easier tasks. No further spend on the user's
key without explicit approval. Key rotation reminder stands.

## A73 — PRE-REGISTERED: opus three-way (frontier-tier probe, user request)
Question: crutch or multiplier — does the interface delta persist at the
frontier tier? Configs op_{base,evolve,sota} = af3 configs with model
claude-opus-4-8; identical arena/protocol/gate. 2 reps x 5 tasks x 3 arms
= 30 attempts, ~$250-300 (user-approved). At 10 attempts/arm the frozen
|delta|>=3 rule does NOT apply cleanly — results reported as directional +
per-task, no keep/revert decisions hang on them. Known risks, stated
up front: (a) ceiling effect — if op_base nears 10/10 the deltas are
clipped from above ("frontier doesn't need the MCP" would then be the
honest headline); (b) rate limits — opus burns ~5x faster; arms run
SEQUENTIALLY with a utilization/poisoning check between arms; a
rate-limited arm is invalid and gets re-run or marked, never pooled.
Queues behind the magistral floor probe.

## A72b — Mistral chapter CLOSED (driver-bug retraction + final verdicts)
The first magistral probe was INVALID — my driver's 180s HTTP timeout
crashed 3/5 attempts (reasoning models think longer); fixed to 600s and
re-run. FINAL: magistral-medium 0/5, every attempt turns=1 with ZERO tool
calls — it reasons for 2-13 minutes, answers in text, and never acts under
the protocol (tool_choice auto, no coaching — identical to every other
arm). mistral-medium: 0/40 with heavy real tool use but sub-syntax-floor
Rocq (A72). VERDICT: cross-family transfer of the interface effect is
UNMEASURABLE on this benchmark with the available Mistral tiers — two
distinct floor modes (syntax floor; act-vs-plan floor). The model-agnostic
driver is validated infrastructure (handshake, function calling, grading,
dashboard-compatible rows) for future families. Key spend total ~$50.3;
ROTATE THE KEY now (it transited chat).

## A74 — PRE-REGISTERED: miniF2F-test final matrix (final held-out matrix)
FINAL_UNLOCK was never created — the test split is virgin. Per
configs/FROZEN.md addendum (committed with this entry BEFORE unlock):
6 arms = 3 interfaces x {sonnet, opus}, 2 reps x 244 problems each,
sequential chains behind the running op_ autoform chain. Estimated
~$1,000; ~15h. Report: pass@1/pass@2 per difficulty bucket + cost/solve +
wall, binomial CIs. No reruns, no tuning, no second look.

## A75 — GATE BUG (found by the mining workflow, verified by hand): fixed
The gate located the built theory dir as vo[0].parent over an UNORDERED
rglob (autoform_gate.py). Agents that ship a second dune theory (tests/
with a probes.v copy, as self-verification) could have the gate select the
test theory — only probes.vo inside — so -Q <dir> TaskLib was empty and
every probe failed on provably-correct work. SYSTEMATIC BIAS: 5 of the 6
atlas-identified hits are evolve-family arms (that agent style adopts the
self-test layout). VERIFIED by hand: af3_evolve/frugal__rep0 regrades
probes_failed -> ok under the fix (prefer the dune theory declaring
TaskLib; fallback = dir with most .vo). Gate suite green; references
unaffected. SWEEP (deterministic trigger class = workspaces with >=2
coq.theory dunes) queued after the op_ chain; originals preserved,
corrections land in <run>/regrades.jsonl, dashboard applies overrides.
EXPECTED (atlas, to be confirmed by sweep): base 9->10, evolve 13->14,
r1 12->15, c3 13->14; sota unchanged 12 — which would WEAKEN A70's
"sota +3 signal" to +2 (below the frozen bar; correction to follow the
sweep, not precede it).

## A76 — PRE-LAUNCH FAIRNESS AUDIT of the miniF2F matrix (user-prompted);
## amendments applied BEFORE any test attempt
Audit (4 auditors + batched verification; one auditor died mid-run and its
scope was covered inline). VERIFIED FINDINGS and dispositions:
1. BLOCKER, FIXED: the evolve arms were cloned from the WRONG RUNG
   (Change-7 auto, not the frozen sugg winner): ROCQ_SUGGEST=0, missing
   ROCQ_ENV_V2=1, stray ROCQ_PRELOAD=0, pre-freeze system prompt. Fixed
   atomically (the audit itself identified the coupling trap: enabling
   preload without ENV_V2 writes a Require into the graded region =
   systematic zero). Arms now equal frozen.json in every field except
   config_id/model/description — verified by stripped-field diff.
2. FIXED (harness parity, favors the COMPETITOR): the submit sidecar was
   last-write-wins on unverified content — a later broken submit could
   clobber an earlier good one, unlike baseline (candidate persists only
   on exit-0) and session (only on verified completion). Now: submissions
   versioned; grading takes the newest submission that compiles.
3. ARENA STANDS (measured): the 30-turn cap binds NOWHERE in proving —
   0/360 dev60 attempts turn-capped (median 2-6 turns/arm); the 300s wall
   is the binding budget for all arms. The A62b artifact is immaterial in
   this regime; no amendment.
4. DOCUMENTED, NOT FIXED (freeze discipline; biases AGAINST our product):
   the session arm's submission plumbing can commit exploratory
   meta-commands (Abort/Unset) into the graded region — a frozen-product
   deficiency; losses it causes are the interface's own.
5. DOCUMENTED: sota arm tool metrics in results.jsonl undercount (the
   sibling does not write our log); any efficiency table will use
   transcript-derived counts. Latent timeout-reachability asymmetry
   (session candidates can exceed the gate's 120s recompile where other
   arms' cannot) documented; affects evolve only.
6. SOTA integration verified: prewarm proxy present; task travels
   in-prompt (workspace-free scratch mode, the sibling's documented
   preferred workflow); empty env is correct for this mode.
All amendments pre-data; the held-out set remains unconsumed.

## A73 VERDICT — opus autoform three-way (directional, n=10/arm)
op_base 3/10 · op_evolve 6/10 · op_sota 6/10 (health 20/20 both treatment
arms; recovered cost $6.57/$11.37/$12.38; walls 844/705/757s). READING
(directional per A73's pre-registration; no keep/revert hangs on it):
the FRONTIER answer on autoform is MULTIPLIER, not crutch — the opus
baseline collapses (thinking-burn against the 900s wall; below sonnet
base's 45%) while BOTH prover interfaces double it; evolve == sota at
this tier. prodauto 0/2 everywhere at opus (sonnet evolve got 3/4);
triadic 0 everywhere (28+6 attempts). Ceiling risk did not materialize —
the frontier tier had MORE headroom on this benchmark, not less.

## A77 — CORRECTION: the held-out set was consumed ONCE in phase 1
A74 claimed the test split was virgin ("FINAL_UNLOCK never created").
WRONG: logs/runs/FINAL_minif2f_test (frozen config, haiku, 488 rows,
2026-07-03) shows phase 1 executed its pre-registered final run; my check
looked in the wrong directory and keyed on a file that was removed or
ignored post-run. CONTAMINATION ANALYSIS for the A74 matrix: (a) the
frozen interface was selected on dev sets before that run; (b) today's
arm amendments (A76) derive exclusively from configs, source, and dev60
logs — no test data was read; (c) the haiku FINAL results were never
inspected during this arc (and the arms are now frozen and launched, so
they can no longer influence configuration). The correct claim for the
record: the test split has been evaluated under pre-registered protocols
exactly twice — the phase-1 frozen-haiku run and the A74/A76 six-arm
matrix — with no tuning feedback from either. BONUS: the haiku FINAL run
gives the frozen arm a third model tier for the report's sweep at no cost.

## A78 — reporting convention (user challenge): decompose wall, keep cost
Prior tables reported mean wall over ALL attempts — budget consumption,
censored upward by wall-kills; with differential kill rates it partially
re-measures the solve rate (A71b within-arena). CONVENTION from here, in
dashboard and report: (1) latency = mean wall over SOLVED attempts
(uncensored time-to-solve; evolve: 431s vs base 603s at sonnet, 574s vs
714s at opus — ~25-30% faster when it solves, on top of solving more);
(2) the wall-kill fraction is its own column; (3) budget-consumption
(wall over all) reported only when explicitly labeled; (4) cost/solved
stays failures-included by definition (expected spend per solved task,
killed attempts cost-recovered), definition stated at each table.

## A75 FINAL — sweep complete: 8 verdicts corrected; A70 CLAIM DOWNGRADED
Sweep: 400 attempts scanned, 9 in the trigger class, 8 flips (all
probes_failed -> ok on provably-correct work; the atlas predicted 6 and
missed 2 in af2_base). CORRECTED TOTALS: af3_base 10/20, af3_evolve 14/20,
af3_sota 12/20 (unchanged), r1 15/20, r3 15/20, c3 14/20, af2_base 11/20.
CONSEQUENCES, applied:
1. HEADLINE HOLDS: evolve 14 vs base 10 = +4 -> SIGNAL.
2. A70 CORRECTION (downgrade): sota 12 vs base 10 = +2 -> WITHIN NOISE at
   sonnet. The "both MCPs beat baseline with signal" claim is corrected to:
   evolve holds the only sonnet-tier signal; sota is +2 directional; at
   opus both double the baseline (directional, n=10). The interface-class
   claim survives directionally, not as a sonnet-tier signal pair.
3. ALL RUNG REVERTS ROBUST: r1 15 vs evolve 14 (+1), r3 15 vs 14 (+1),
   c3 14 vs 14 (0) — every keep/revert decision unchanged.
4. af2 history note: corrected af2_base 11 vs af2_evolve 7 makes the
   superseded af2 arena read as -4 for evolve — further evidence that
   arena carried the verdict, not the interface (the same binary swings
   -4 to +4 across arenas).
Gate bias direction confirmed: 6 of 8 flips favored evolve-family arms —
the bug systematically suppressed OUR product's scores; fixing it was
against-interest-proof of the gate's neutrality.

## A79 — adversarial-audit response: corrected artifacts and statistics
An adversarial expert audit of the phase-2 report draft (verified
against this repo) found: misattributed mechanism numbers (sonnet figures presented as
opus), a mis-scoped failure-audit population, three provenance-broken
figures, an over-claim of universal pre-registration, un-disclosed
sibling-project COI framing, and statistically hollow "signal" language.
CORRECTED ARTIFACTS, recorded here:
1. STATISTICS (task-stratified permutation, 200k draws, two-sided):
   af3_evolve 14/20 vs af3_base 10/20 -> p = 0.164 alone. POOLED
   REPLICATION (the four independent evolve-family 20-attempt arms:
   14, 15, 15, 14 = 58/80 = 72.5%) vs base 10/20 -> p = 0.0062.
   Paired-task latency (commonly-solved tasks frugal/gauges/ledger):
   base 608s (n=10) vs evolve 349s (n=11) = -43%.
2. COST CELLS: recovered totals af3_base $24.75 ($2.47/solve), op_base
   $6.91 ($2.30), op_evolve $14.24 ($2.37), op_sota $21.37 ($3.56).
   A73's figures labeled "recovered" were RAW sums (wall-killed attempts
   contribute null) — label corrected here; the dashboard recovery is the
   canonical artifact (harness/autoform_dashboard.py _recover_cost).
3. PROVENANCE FIXES: max num_turns opus=45, sonnet=108 (no 130-turn
   attempt exists); triadic = 18 attempts in the af3 headline-table arms, 51
   project-wide, all unsolved; trail = 77 unique entries (two identifier
   collisions preserved as written).
4. UNGATED CHANGES (the report must say so): build{} shipped suite-tested,
   explicitly unmeasurable on benchmark manifests (A33); import-echo
   shipped as a grading-path fix without isolated A/B (A59); relative-path
   resolution kept on a usability criterion (A42/A50). All other shipped
   features were solve-rate-gated.
5. PROMPT-ASYMMETRY CLAIM DOWNGRADED in the report: 2/8 vs 1/8 vs 2/20 are
   statistically indistinguishable; the 12/20 jump coincides with the
   arena change (A70); cross-protocol deltas were banned by A60 rule 8.
   The report presents prompts as a controlled-by-design risk, not a
   demonstrated artifact.

## A80 — PRE-REGISTERED (before reading ANY held-out result): supplementary
## no-prompt held-out pair
The registered six-arm matrix follows the phase-1 guided protocol; the
review correctly notes the report's own doctrine prefers prompt-free arms.
REGISTERED NOW, while the FINAL chain is still running and no test result
has been read: a supplementary pair {baseline, evolve} x sonnet under the
autoform doctrine — NO system prompt, tools documented by shipped
descriptions only, wall-only budget (300s, turn ceiling 100 safety-only),
2 reps, minif2f_test. Run pending user approval (~$70, ~5h) after the
main chain completes; reported alongside the guided matrix either way.

## A81 — PRE-DATA SCOPE REDUCTION of the held-out matrix (user decision)
Measured pace on the test split (~55 attempts/h; the split is far harder
than dev: ~60% baseline wall-kills) put the six-arm matrix at ~53h. User
decision, recorded BEFORE any opus-arm test attempt exists: the OPUS trio
is cut from the held-out matrix (configs moved to configs/deferred/ so
the running chain's opus steps no-op). The tier claim rests on: held-out
haiku (phase-1 FINAL run) + held-out sonnet trio + autoform opus
(directional). The A80 prompt-free pair RUNS after the sonnet trio, at
2 reps and parallel 8 (its own registration; internally consistent —
its two arms share contention conditions; cross-protocol latency vs the
guided trio will not be compared). SCOPE REFRAME (user): the evolution
corpus is the DIVERSE development set (workbook + miniF2F-dev +
autoformalization benchmark); held-out claims rest on miniF2F-test only;
autoform results are development-set evidence under strict protocol —
the fresh-task follow-up is no longer required for the report's claims.
Revised ETA ~31h; opus-miniF2F deferred, not cancelled.

## A82 — COI facts recorded (user statement) + comparison framing final
The user is the MAIN MAINTAINER of the sibling rocq-mcp: coq-lsp-based,
inspired by Lean MCP designs, battle-tested and refined through several
large-scale formalization projects. rocq-mcp-evolve is the deliberate
counterpoint: minimal (Rocq runtime only, linked in-process), grown
exclusively by the measured-evolution experiments. The report now frames
every comparison as an INTRA-TEAM DESIGN-PHILOSOPHY ABLATION (production
maturity vs measured minimalism) — no rival-group incentive; residual
risk = asymmetric familiarity, mitigated by the fair protocol and the
three sibling-favoring repairs. This supersedes all "SOTA competitor"
framing in earlier trail entries.

## A83 — HELD-OUT TRIO QUOTA-POISONED; identical-slot repair in progress
The 27h chain ran unattended through subscription session-limit windows:
transcripts carry verbatim "You've hit your session limit" with
api_error_status 429. Poisoning census: FINAL_baseline_sonnet 379/488
poisoned (109 clean rows kept, incl. 30 solves), FINAL_session_sonnet and
FINAL_rocqmcp_sonnet 488/488 (zero valid attempts — the arms' agents were
never able to act). My earlier "the test split is far harder than dev"
pace reading conflated quota lockouts with hard problems; retracted until
clean data exists. REPAIR, per the pre-registered infrastructure carve-out
(machine_slept precedent, harness/repair_run.py convention): poisoned rows
quarantined to results.quarantine.jsonl, poisoned transcripts parked, the
resumable runner redoes exactly those slots; run_eval is now QUOTA-AWARE
(a 429/session-limit result parks the transcript, sleeps 20min, and redoes
the same slot — attempts can no longer be silently burned). Ops lesson
recorded: per-arm poisoning checks exist precisely because unattended
chains cross quota windows; they must run BETWEEN arms, not after the
matrix. ALSO: the A80 prompt-free pair's first attempts failed
prefix_modified — the prefix-discipline rules lived in the system prompt;
per the autoformalization protocol's precedent, grading rules are TASK
information and now live in the (identical) task prompt of both pf arms;
the pair restarts from zero with run-ids unchanged (no valid attempt
existed).

## A82b — COI framing final (user facts, round 2)
rocq-mcp is not merely in-house: it is adopted by several teams across
multiple projects and has external contributors — it IS the state of the
art for Rocq MCP. Comparison framing updated: the SOTA label returns, now
SUPPORTED (adoption + external contributors), alongside the maintainer
disclosure. The comparison is thus both an external benchmark (against
the deployed SOTA, not a strawman) and incentive-symmetric (both systems
ours). This is the strongest honest framing available and supersedes
A82's "intra-team only" wording.

## A84 — PROJECT-WIDE quota-poisoning census (user question)
First scan used sloppy markers (field names, loose patterns) and flagged
everything — retracted within minutes; the A68 reply-level rule applies to
audits too. PRECISE census (value-bearing markers: api_error_status 429/
529, session-limit text), all transcripts in the project:
CLEAN: every autoformalization run (all w2/af/af2/af3/op arms — the entire
phase-2 story), all Mistral runs (separate API), the phase-1 haiku
FINAL_minif2f_test held-out run, and every dev-ladder proving run except
those below. The FINAL sonnet trio's poisoning is fully parked (0 live).
LIVE-CONTAMINATED (3 runs):
1. universal_dev60 (the haiku dev-headline arm): 14/240 attempts
   (5.8%) — REPAIR REQUIRED (identical-slot redo, dev data so reruns are
   unproblematic); dev-headline-table haiku evolve numbers to be recomputed after.
   Queued behind the FINAL repair chain (no CPU contention in measured
   walls).
2. baseline_fable_dev60: 1/60 — annex run, not in any reported table;
   repair queued with (1).
3. team_decomposable: 29/176 — phase-1 team experiment; feeds REPORT.md
   team claims but NO reported table; repair deferred with this
   note (any team claim revived for the report must be re-validated first).
All other numbers in the report stand on clean transcripts.

## A84b — repairs classified by report impact (user decision)
REPORT-REQUIRED (stays queued behind the FINAL chain): universal_dev60
14-slot repair — feeds the dev headline table (haiku evolve row).
OPTIONAL — explicitly flagged, run ONLY if time and tokens remain:
  (a) baseline_fable_dev60 1-slot repair (fable annex; no reported table);
  (b) team_decomposable 29-slot repair (phase-1 team claims; feeds no reported
      table; REPORT.md team numbers carry a contamination flag until
      repaired);
  (c) opus miniF2F trio (deferred pre-data, A81; scope reframed around
      its absence).
Any claim touching (a)-(c) must cite this entry until repaired.

## A84c — universal_dev60 contamination: downstream impact analysis
Could the 14 poisoned slots have changed anything that happened after?
NO, on three verified facts: (1) TIMELINE — the run spans Jul 3 23:57 to
Jul 7 10:41, entirely AFTER the Jul 3 freeze; it is the post-freeze
headline run, and no keep/revert decision cites it (ladder decisions used
their own rung arms, all census-clean; grep confirms zero decision-entry
citations). The row gap shows the mechanics: attempts died against the
weekly limit ("resets Jul 7 9am"), the run resumed 10:03 Jul 7, the 14
dead rows stayed. (2) DIRECTION — all 14 slots recorded solved=False, all
in the hard bucket: the contamination only DEFLATES the evolve interface's
reported .40; the repair is favorable-only and the dev table's value is a lower
bound meanwhile. (3) DOWNSTREAM — phase 2 ran on autoform data (clean);
the held-out arms restore frozen.json (locked before this run existed).
The repair remains queued as report-required (it corrects a table cell,
not a decision).

## A84d — universal_dev60 repair OFF the critical path (user decision)
Repairing would change an ALREADY-ANNOUNCED number (README headline /
public dashboard: haiku evolve .66/.58/.40), creating inconsistency
between the announcement and the report. Since the contamination is
one-directional (14/240 attempts, hard bucket, all recorded as failures
for OUR arm), the published value is a valid CONSERVATIVE LOWER BOUND and
is reported as such: the report's dev headline table carries the contamination note, no
number changes anywhere. Repair reclassified REQUIRED -> OPTIONAL (time+
tokens permitting); IF ever run, README + dashboard + report update
together in one commit. Nothing remains on the report's critical path
except the FINAL chain itself.

## A84e — user reversal: universal repair IS important; back on the queue
The 14 universal_dev60 slots are quarantined and will be redone right
after the FINAL chain (haiku, ~20min). Per A84d's lockstep rule: when the
repaired number lands, README + public dashboard + the report's dev headline table update
TOGETHER in one commit (the lower-bound footnote then becomes the change
note). The repair can only raise the hard-bucket cell.

## A85 — confidentiality scrub (user-authorized history rewrite, pre-push)
The draft material was briefly tracked in this repo before moving to its
own private repo; its content therefore lived in local git history, and
tracked docs named the external destination. Verified BEFORE acting: no remote ref
ever contained any affected commit (origin/main sat at the pre-merge tip);
the draft material repo has no remote. With explicit user approval:
git filter-repo expunged the draft material path from all history and replaced
external-destination names across all blobs; the remote was re-added; old objects
repacked away. Verified after: draft material unrecoverable from any ref,
those names absent from all tracked files and history, freeze-provenance
hashes (pre-rewrite-window) unchanged, the running FINAL chain unaffected.
Branch tips changed (main a05e661). Lesson: draft materials never start life inside a repo with
a public remote, even untracked-then-moved.

## A86 — repository self-sufficiency pass (user-directed)
Residual references to material maintained outside this repository were
removed from tracked files, all historical blobs, and all commit messages
(second history rewrite, same user authorization and pre-push verification
as A85). This repository now documents its results exclusively through its
own artifacts: README.md, docs/REPORT.md, docs/ASSUMPTIONS.md,
docs/FAILURE_ATLAS_AUTOFORM.md, and the dashboard. Follow-on duties for
successor sessions live in the machine-local session memory, deliberately
outside version control.

## A87 — handoff consistency audit: 26+3 verified findings fixed
A final four-auditor sweep (numbers vs regrade-corrected data, post-scrub
coherence, runbook dry-run, generated-dashboard check) found and fixed:
stale pre-A75 numbers on the dashboard (sibling "+3 signal" -> +2 within
noise; af2 delta -7 -> -9 corrected; rung labels; -45% -> -49%; 1128 ->
2,109 messages); a real dashboard bug (rung discovery glob missed
af3_evolve_c3 — headline showed 15/15 instead of 15/15/14); the A84e
status reversal never propagated to the deferred-items table; seven runs
rendering "unlabeled"; the headline table violating the A78 convention
(now: solved-only latency + wall-killed columns); scrub garbles in
A79/A84/A84b/A85; runbook heredoc that would not have terminated for the
successor, missing cd, confusing log-path notation, stale trail ranges;
and the results exporter's row format neutralized. AUTOFORM's failure
count corrected 46 -> 40 post-regrade. All surfaces now agree with the
corrected record and with each other.

## A88 — weekly-limit lockout: trio unscathed; detector gap closed
The provider's WEEKLY limit hit 2026-07-12 08:20, two days into the
held-out chain. INTEGRITY: all three guided sonnet arms completed BEFORE
the lockout (last row 08:01; zero rows after) — the core matrix is clean.
The park-and-retry mechanism held the prompt-free arms' slots for two
days (1,168 parked retries; no quota burned — 429s are free) until the
window reopened. FALSE-NEGATIVE GAP (user-predicted): attempts that
streamed NOTHING during lockout produce no 429 result event, wall-kill at
300s, and were written as failures — 6 pf_baseline rows quarantined (4
with provably zero assistant events; 2 adjacent, quarantined
conservatively; 20 pre-lockout rows kept). FIXES: (1) the runner now
parks any attempt whose transcript has zero assistant events (dead
stream = infrastructure, not model); (2) final_tables.py's integrity
gate refuses tables containing dead-stream rows (defense in depth for
the successor). The mid-lockout pf_baseline runner (old code) was cycled;
the chain advances to pf_session under the fixed runner, and a detached
launcher completes pf_baseline's remaining slots afterwards.

## A89 — dead-stream census (user question): the A88 gap was project-wide
Verified by transcript anatomy: flagged rows contain ~200 system events
and ZERO assistant events — the model never ran (infrastructure), and
these carry NO 429 marker, so every earlier marker-based census missed
them. The "difficulty correlation" was manifest-order: early slots hit
Jul-11 session-limit windows. CENSUS RESULTS (dead rows quarantined,
identical-slot redos queued):
  FINAL trio — NOT complete after all: baseline 83, evolve 8, sibling 15
  dead rows (A88's "complete and clean" claim CORRECTED: pre-weekly-
  lockout, yes; dead-stream-free, no).
  Dev tables — baseline_sonnet_dev60 9/120 and rocq_mcp_fair_sonnet_dev60
  3/120 contaminated while evolve's dev arm is CLEAN: a bias in OUR favor,
  which per our own standard (inverse of A84d) MUST be repaired, not
  disclosed-and-kept. Repairs queued. Superseded/annex runs also affected
  (rocq_mcp_sonnet_dev60 14 — unfair-era, superseded; fable/ctx annexes
  2 each) — flagged optional. team-run "missing transcripts" are a layout
  artifact (per-agent transcripts), not dead streams. Phase-1 haiku FINAL
  run and ALL autoform runs: CLEAN.
DEFENSE VERIFIED: final_tables.py's A88 gate already refuses dead-stream
rows — the successor could not have exported the contaminated table.

## A90 — quota-scarcity reorder (user: 10% of weekly limit remains)
The completion chain is reordered, report-critical first: trio dead-stream
repairs (106 slots) -> dev-table repairs (12) -> universal repair (14,
A84e, pulled into the chain) -> the pf pair last (~940 slots, the bulk).
Rationale: the registered guided matrix + corrected dev tables must
complete inside the current quota window; the pf replication parks
harmlessly across weekly resets if quota dies (delay, never loss; the
only deadline is September). No registration changes: same configs, same
reps, order only — order across arms was never part of any registration.
Orchestrator token use drops to minimal check-ins from here.

## A91 — window-economy: cheap critical repairs parallelized
With session windows gating throughput, the cheap critical stages
(universal haiku 14 slots; dev sonnet 12 short slots) now run in a side
chain so each open window completes many cheap slots instead of few
expensive ones. Main chain skips them when it arrives (resumable).
Registration untouched. Option recorded: an API key would lift session
caps entirely for the remainder (billing channel is not registered);
pending user decision.

## A92 — RETRACTION of A89: the "dead streams" were extended thinking
Transcript anatomy (subtypes, which A89's census never inspected): the
flagged transcripts contain ~210 system/thinking_tokens events — the
model thinking for the full 300s budget without emerging. These are
LEGITIMATE hard-problem failures, not infrastructure. CORRECTED CENSUS:
120 of the 121 rows quarantined under A89 (and A88's 4 "provably dead"
pf rows, which began thinking just before the weekly cutoff) were valid;
exactly 1 row (rocq_mcp_fair_sonnet_dev60) shows zero model activity and
stays quarantined. CONSEQUENCES, all applied:
1. RESTORATION with no-resampling discipline: all 120 original rows
   restored; the 25 redo rows already produced by the repair chain were
   DISCARDED (originals win — re-running valid attempts would be
   resampling outside any carve-out); redo transcripts archived.
2. The trio was COMPLETE all along (488x3); baseline_sonnet_dev60 is
   complete; the A89-era "bias in our favor" claim is void.
3. DETECTOR fixed in run_eval.py and final_tables.py: dead requires no
   result AND no assistant AND no thinking_tokens (A88's gate edit had
   also silently failed to land in final_tables — now present).
4. COST of the error: ~25 wasted redo attempts plus park-retry loops on
   thinking-burn slots (~3h of stalled chain and the user-observed quota
   drain); the A89 quarantine/redo chain is stopped.
5. Remaining genuine work: universal_dev60 429-slots (in flight, haiku),
   1 truly-dead sibling dev slot, and the pf pair (~800 slots).
LESSON (binding, added to the runbook's DO-NOTs): transcript-level
infrastructure claims require EVENT-SUBTYPE anatomy, not event-type
counting — thinking-only attempts are model activity.

## A93 — concurrent-writer contamination in pf_baseline (power-loss audit)
2026-07-14. A battery power loss (~20:44) killed the pf chain; the
post-reboot audit found 68 double-sampled slots in
FINAL_pf_baseline_sonnet. CAUSE: the earlier kill of the mistaken
parallel-4 stint (remainder_chain.log) hit the wrapper sh but MISSED the
python child, which kept running; from 19:47 to the power loss it ran
concurrently with the registered parallel-8 relaunch (pf_chain.log).
Receipts: relaunch resumed at 180 done and logged 114 attempts, yet 182
rows landed — 68 extra = exactly the duplicated slots; the zombie logged
73 attempts = 5 pre-overlap (kept) + 68 overlap (all duplicated).
CONTAMINATION: both attempts of a pair share attempts/<slot>/work, and
grading reads work/candidate.v at attempt end — either row can be graded
on the other attempt's proof (2 of 68 pairs had conflicting verdicts).
Both rows of every pair are therefore untrustworthy. REPAIR (outcome-
blind, A83 class, harness/a93_quarantine.py): all 136 rows of the 68
slots quarantined (results.quarantine.jsonl, reason
A93_concurrent_writer_contamination); their attempt dirs plus 8 row-less
in-flight dirs (stale-candidate hazard) parked to attempts_contaminated/;
identical-slot redo via the standard resumable runner. Kept 226 clean
rows (175 parallel-8, 5 parallel-4-solo, 46 single-sampled overlap).
HARDENING: run_attempt now deletes stale grading artifacts (candidate.v,
submissions/, server.jsonl, gate_reject.txt) at attempt start — no
attempt can ever be graded on a predecessor's files.
HISTORICAL BOUND: all FINAL + dev arms scanned for the stale-artifact
false-positive signature (solved with zero tool calls): 0 hits anywhere;
no completed arm is affected.
LATENCY FOOTNOTE (pf_baseline only): 51 of 488 kept rows ran off the
registered parallel=8 (5 at parallel 4, 46 under dual-runner load <=12).
Verdicts unaffected; the latency-solved column for this arm carries this
caveat in any report that cites it.
LESSON (runbook DO-NOTs): kill the PYTHON pid, not the wrapper; verify
`pgrep -f run_eval.py` is EMPTY before launching any runner; laptop must
be on AC power for unattended chains (caffeinate cannot survive battery
exhaustion).

## A94 — dev-table lockstep recompute after repairs (A84e rule applied)
All numbers regenerated by scripts only (harness/report.py; site and
figures by dashboard.py/plots.py — plots.py repaired first, it had
drifted from the dashboard refactor). universal_dev60, 240/240 after the
429-slot repair: hard pass@1 .400->.463 (sigma .14->.05), hard wall
74->87s; easy/medium and all $/solve cells unchanged.
rocq_mcp_fair_sonnet_dev60, 120/120: hard .800->.825, $/solve .26->.25,
wall 105->106 — the repair moved the EXTERNAL arm up, not ours.
baseline_sonnet_dev60: unchanged (.925/.95/.80). Surfaces updated in ONE
commit: README headline row + honesty note, REPORT (policy table +
efficiency annex), site/index.html and docs/figures regenerated. The
A84d "conservative lower bound" stance is retired — published numbers
are the actual repaired measurements. Hand-division of the 3-decimal
report output would have given a wrong $/solve cell (.15 vs the
script's .16): numbers come from scripts, never hand math.

## A95 — stale-artifact false positives: 2 rows quarantined (pf_baseline)
The completed FINAL_pf_baseline_sonnet arm's integrity audit plus a new
cross-validation (every solved row must be backed by ITS OWN transcript:
assistant turns AND tool use; baseline arms additionally an
"exit code: 0" check result; MCP arms a PROOF COMPLETE / final-submit
marker) found exactly TWO false-positive rows, both pf_baseline, both
pre-dating the A93 hardening:
1. aime_1989_p8 rep1 (ts 20:15, inside the A93 dual-runner window):
   transcript = 1 init event, model never acted, wall 34s — graded
   SOLVED on a candidate.v it could not have written.
2. induction_pord1p1on2powklt5on2 rep0 (ts 19:42): 217 thinking_tokens
   events, zero assistant turns (a legitimate A92 thinking-only FAILURE)
   — graded SOLVED on a stale candidate.v left by one of its four
   parked quota-poisoned predecessors (pre-hardening park-recursion
   reused the dir without wiping).
Both violate a hard invariant (a solve requires the attempt's own tool
action), so quarantining them is outcome-forced, not outcome-conditioned.
REPAIR: rows to results.quarantine.jsonl, transcripts parked, identical-
slot redo when the running pf_session arm finishes (single-runner rule,
A93; the hardened runner wipes stale artifacts at attempt start, so the
redo is immune to recurrence). GATE: the own-activity invariant is now a
permanent audit gate in final_tables.py. SWEEP RESULT: all other arms
CLEAN under both the weak and strong invariants (trio, haiku, pf so far,
all dev tables — 875 at-risk solved rows with parked predecessors, zero
further violations). Why the earlier A93 scan missed these: it keyed on
the row's tool_calls field, which was counted from the shared cumulative
server.jsonl — the same staleness it was hunting; detectors must read
the per-attempt transcript, never shared files.

## A96 — HELD-OUT COMPLETE: the single registered look (2026-07-15)
All six pre-registered arms complete and integrity-clean: 488 rows each
(244 problems x 2 reps), every gate green (row counts; zero live quota
markers; zero machine_slept; zero A92 dead streams; zero A95 solved-
without-own-activity). Repairs performed across the campaign, all
quarantine + identical-slot redo under the pre-registered infrastructure
carve-out and all disclosed: A83/A84 (provider rate-limit windows),
A93 (concurrent-writer contamination, 68 slots), A95 (2 stale-artifact
false positives; on redo aime_1989_p8 rep1 solved legitimately and
induction_pord1p1on2powklt5on2 rep0 failed — the phantom solve did not
survive). harness/final_tables.py ran once; output archived VERBATIM to
docs/final_heldout_table.json, REPORT §16 (table + CI-only reading),
README phase-2 block, STATUS.md. Convention note recorded: pass@1 is
rep0-only (A78); phase-1 §7's haiku row used mean-over-reps — same run,
both stated, no renumbering. No further statistics computed; nothing on
the held-out split may run again. Remaining work is runbook Step 4 only
(history-hygiene pass with user approval, then the final --no-ff merge;
NEVER push).

## A97 — cosmetic relabel of the phase-1 held-out arm (user review)
"frozen interface (haiku, phase-1 registration)" renamed to "evolve
(haiku, phase-1 frozen config)" everywhere: it is the SAME server binary,
tool surface, and enrichment flags as the sonnet evolve arms (verified
against run_meta; the phase-2 arms merely pin three later features off,
which equals the phase-1 freeze). The regenerated artifact was diffed
against the archived copy: label-only, all data byte-identical. The row
stays in the table as the tier anchor: same interface, weak policy.

## A98 — held-out sibling arm: environment asymmetry found, quantified
Post-hoc forensics on the surprising sibling gap (user challenge). The
A11 ambient-environment rule ("micromega preloaded everywhere: session,
baseline, gate") silently did not extend to the external sibling server,
which receives no ROCQ_* environment: its in-session checks lacked
Lia/Lra/Psatz while the gate injects them. VERIFIED FOOTPRINT: 153/211
of its failed held-out attempts contain phantom "lia/lra not found"
errors; agents abandoned gate-acceptable proofs and burned budget
rebuilding tactic-free. COUNTERFACTUAL GATE REPLAY (mechanical assembly
of the model's own in-session proof onto the unmodified prefix, real
gate, every flip independently re-verified; unreproduced flips dropped):
34 verified rescues -> sensitivity pass@1 .82/.46/.31, pooled .63
(registered .73/.43/.20, pooled .56). Evolve (.90/.65/.63, pooled .78)
leads every bucket under BOTH readings. Dev-side replay: ZERO flips in
both dev60 sibling runs (12 + 66 failures all genuine: helper-lemma
structure, real nra limits reproducing under the gate env, thinking
stalls) — the published dev rows carry no manufactured losses.
Registered numbers stand everywhere (no resampling); the sensitivity
bound is reported alongside, clearly labeled. Residual mechanism per the
adjudicated forensics: wall-censoring (184/211 failures killed at 300s,
often mid-proof) plus the assemble-and-submit tail the session servers
do not pay; minor asymmetric model-behavior contributions (16 vs 8
thinking stalls, 23 prefix-compliance rejects) disclosed. The flaw is a
HARNESS integration limitation, biased only against the sibling.

## A99 — PRE-REGISTERED: bridged sibling remeasurement (user decision)
Scope (user-selected, ~730 slots): (1) FINAL_pf_rocqmcp_sonnet —
prompt-free sibling arm completing the A80 pf matrix into a three-way;
minif2f_test, 2 reps, parallel 8, max_turns 100, 300s wall, no system
prompt, A80 rules wording with only the completion-mechanism sentence
adapted to submit. (2) rocq_mcp_fair2_sonnet_dev60 (dev60, 2 reps,
parallel 4) and (3) rocq_mcp_fair2_dev60 (haiku, dev60, 2 reps,
parallel 3) — arena-identical dev reruns. BRIDGE: the ambient modules
are delivered in the task-file prefix ("From Stdlib Require Import Lia
Lra Psatz.", runner option prefix_prepend; the gate receives the same
prefix) — the server's native channel, after project-file routes failed
(-ri crashes coq-lsp's workspace scanner; -arg injection is silently
dropped). Verified: session lia closes in 3ms; compile passes; smoke
af_pf_rocqmcp_smoke (EXCLUDED from analysis) 5 attempts, zero phantom
errors, submits flow, bridged prefix identical in session/submission/
gate. SUPERSESSION RULE (declared before any registered attempt runs):
these runs become the reported sibling numbers for the dev table and
the pf matrix; the original sibling runs remain in the record as the
disclosed A98 artifact story; the guided held-out sibling row keeps its
registered number + A98 sensitivity (no guided held-out rerun in this
scope). Report-only: no keep/revert decision hangs on these runs. Test-
split re-consumption: sibling arms only; evolve/control arms are NOT
rerun (their environment was already uniform; resampling them has no
cause and would violate the single-look rule). Dev-replay context: dev
rows had zero manufactured losses, so (2)/(3) are uniformity runs, not
corrections.

## A100 — PRE-REGISTERED: wall-only haiku held-out rerun (user-conditional
## on budget; budget verified: ~30% of the weekly window remains after A99)
FINDING (user question exposed it): the phase-1 haiku held-out arm was
TURN-CAPPED, not wall-bound — all 291 tool_use-stopped rows sit at
num_turns=31 (cap 30 + CLI off-by-one); 289/330 failures ended by cap,
only 12 by wall. The registration predated A62b's discovery that turn
caps are covert tool-call taxes; the .52/.14/.03 row therefore measures
"frozen evolve at haiku under a 30-call budget". All five SONNET arms
are verifiably wall-bound (zero error_max_turns; stop_reason==None
reconciles with wall-kill counts arm-by-arm; pf cap 100 never
approached). REGISTRATION: FINAL_frozen_wallonly = config identical to
frozen except max_turns 30->200 (safety rail, A63 convention);
minif2f_test, 2 reps, parallel 4 (matching the phase-1 arm). Runs AFTER
the A99 chain exits (single-runner rule); launch command in the runbook.
SUPERSESSION RULE (declared before any attempt): FINAL_frozen_wallonly
becomes the reported weak-tier held-out row; the phase-1 capped row
remains in the record, re-labeled as the measured demonstration of the
A62b turn-cap tax at held-out scale (same config, cap 30 vs 200 — the
delta IS the tax). Removing a binding cap is monotone (cannot lower a
pass rate), so this registration cannot flatter our arm relative to the
disclosed row. Report-only; no decision rule attaches.

## A101 — PRE-REGISTERED: cap-30 universal dev rerun (arena symmetry audit)
FINDING (user question "are we sure everything is symmetric?"): the dev60
tables mix turn caps — universal (and the native/auto2 configs) ran at
max_turns 50 while the naive control, every ladder rung, and rocq-mcp
fair ran at 30 — and at the HAIKU tier the caps BIND (42-61% of attempts
cap-terminated in every haiku dev run; even the naive control: 147/240).
This asymmetry favored OUR headline arm. Scope of damage, verified:
sonnet/fable rows have ZERO cap terminations (nominal difference only —
disclose); the ladder is internally symmetric (all rungs cap 30); the
autoform af3 arena is fully uniform (cap 200 / 900s wall, zero hits, all
arms). EXACT truncation estimate (the model never sees its budget, so
trajectories are identical up to the cap; truncating recorded runs to 30
turns is an unbiased cap-30 estimator): universal haiku .662/.575/.463
-> .637/.450/.463 at cap 30. Conclusions survive (medium/hard leads over
naive and the sibling persist; medium lead shrinks .225->.100; the
already-disclosed easy deficit to the sibling remains), but the
published row is flattered and the cost/wall columns cannot be
truncated. REGISTRATION: universal_c30_dev60 = config identical to
universal except max_turns 30; dev60, 4 reps, parallel 4 (matching
universal_dev60). Runs after the A100 arm (single-runner rule; launch
command in the runbook). SUPERSESSION (declared before any attempt): the
cap-30 row becomes the reported universal haiku dev row in every
surface; the cap-50 row stays in the record with the truncation analysis
as the arena-symmetry exhibit. Correction direction is against our own
arm by construction. Report-only. Budget: ~7% of the weekly window,
within the user's standing rerun-if-budget rule.

## A102 — CAMPAIGN COMPLETE: A99/A100/A101 landed; supersessions applied
All three registered remeasurement arms complete and gate-clean; the
eight-arm registered look ran once (final_tables.py, 2026-07-15 night;
artifact archived to docs/final_heldout_table.json and mirrored).
RESULTS (verbatim from the scripts):
- FINAL_pf_rocqmcp_sonnet (bridged, prompt-free): .88/.54/.63 pass@1 —
  above the control with disjoint CIs (easy/hard; adjacent medium),
  overlapping CIs with evolve in all three buckets (evolve holds every
  point estimate, every pass@2 cell, ~30-45% lower $/solve, near-equal
  latency). Zero cap terminations; the 2 strict-scan phantom matches
  were triaged to model-composed rocq_start preambles (agent behavior
  available in every arm), not harness environment.
- FINAL_frozen_wallonly (A100): .67/.25/.09 vs the capped phase-1 row
  .52/.14/.03 — every bucket rises, $/solve improves everywhere; max
  observed turns 131 (rail 200 never fired) — the turn-cap tax at the
  weak tier, now measured at held-out scale.
- universal_c30_dev60 (A101): .650/.500/.475 (4 reps, sigma <= .04) —
  at or slightly above the truncation bound (.64/.45/.46) in every
  bucket, as the bound's construction predicts. Supersedes the cap-50
  row per registration.
READING (recorded): with the environment uniform and prompts removed,
the interface CLASS is the first-order effect (both prover MCPs >>
file-editing control, disjoint CIs); the evolved design's edge at the
anchor tier is efficiency (cost/solve), not reachability. Surfaces
updated in lockstep with this entry: README (dev rows, honesty note,
held-out block, readings), REPORT (policy row, annex, §16, §17),
dashboard (universal slot -> c30 run; SOTA dev sections -> fair2 runs;
held-out section renders the 8-arm artifact). Remaining project work:
merge-day steps only (runbook Step 4: history-hygiene pass with user
approval, then the --no-ff merge; NEVER push).

## A103 — PRE-REGISTERED: second independent autoform baseline arm
Motivation (review panel, statistics): the four evolve-family arms
replicate against a SINGLE baseline measurement (af3_base, 10/20); the
control has never been replicated, and by the ±2 calibration one
unlucky draw could carry half the pooled effect. REGISTRATION (before
any attempt): af3_base2 = config af3_base verbatim, 5 tasks x 4 reps
(20 attempts), same wall-only arena (900s, cap 200), same gate, run-id
af3_base2. Report-only: the row is reported alongside af3_base
whichever way it lands (consistency support or effect shrinkage); no
decision rule attaches; no keep/revert reopens. Cost ~4% of the weekly
window per the user's standing budget rule.

## A103 addendum — second control arm complete (reported per registration)
af3_base2: 12/20 (frugal 4/4, gauges 4/4, ledger 3/4, prodauto 1/4,
triadic 0/4) — within the ±2 calibration of af3_base (10/20): the
control replicates. Consequences, reported both ways as registered:
(1) the pooled control is 22/40 (55%) vs the evolve family's 58/80
(72.5%); individual family-arm deltas vs the pooled control average
+2.5 to +3 (vs +4/+5 against the single first control) — the
consistency framing stands, the margin narrows, and no significance
claim changes (none was made). (2) prodauto is no longer evolve-
exclusive: the second control solved it once; the write-up sentence
"falls only to sonnet+evolve" is corrected. (3) triadic remains
unsolved by every arm ever (now 0/55). Surfaces updated in lockstep
with this entry.

## A104 — PRE-REGISTERED: opus prompt-free pair on the held-out split
Context: an unexpected full quota reset with ~2 days of subscription
remaining (user directive: spend it). The A81-deferred opus trio cannot
fit (an opus arm weighs ~4-5x sonnet); REGISTERED SCOPE: the prompt-free
pair at 1 rep on the full split — FINAL_pf_baseline_opus then
FINAL_pf_session_opus (244 attempts each, parallel 4, 300s wall, cap-100
rail, configs identical to the sonnet pf arms except the model).
pass@1 is rep0-only by convention, so 1 rep reports completely; pass@2
columns are absent. ORDER is registered control-first: the control arm
tests the frontier-collapse claim at held-out scale and is
interpretable alone if quota or subscription ends mid-chain; an
incomplete arm is not reported. CHECKPOINT rule: after ~50 control
rows, project the quota burn from recorded costs; the env-bridged
sibling arm (FINAL_pf_rocqmcp_opus) is appended ONLY if the projection
fits all three arms; otherwise the pair stands. Report-only; no
decision rule attaches; tier claims remain scoped to what completes.
ALSO RECORDED — A59b RETIRED: the "reciprocal eval / reverse-harness
control" is impossible as designed; the sibling has NO evaluation
harness (it ships as an interactive tool — author statement). The
write-up now carries the permanent familiarity-asymmetry caveat with the
integration audits as partial mitigation; do not re-promise the
control unless a community harness appears.

## A104 checkpoint executed (registered rule, 52 control rows)
Projection from recorded costs: $0.17/attempt (cheaper than the sonnet
arms — the 4-5x weighting estimate was wrong in our favor); control arm
~8% of the window, trio ~23%, wall-clock ~11h of ~44h. Per the
pre-declared rule the env-bridged sibling arm IS appended:
FINAL_pf_rocqmcp_opus (config = af_pf_rocqmcp + model swap; 244 x 1 rep,
parallel 4), launched after the pair's chain exits. Scope otherwise
unchanged (1 rep; no renegotiation after data).

## A105 — fidelity audit extension: full coverage
The remaining 34 evolve-family autoform solves audited (same method as
A-round M12): 34/34 faithful — coverage is now 80/80 solved attempts
across all six af3 arms. Blind second rater on 10 first-round attempts
(all arms, four tasks): 10/10 agreement. The write-up's asymmetric-coverage
disclosure is replaced by the full-coverage statement.

## A106 — PRE-REGISTERED: cross-family directional matrix (Mistral)
Acting-floor smokes on the user's new key (run-ids mst_large_smoke,
mst_devstral_smoke, EXCLUDED from analysis): both mistral-large-latest
(23 turns, build attempted) and devstral-medium-latest (17 turns) ACT —
unlike the 2026-07 floors (medium: syntax; magistral: zero calls). The
cross-family question is posable. REGISTERED: af3_base / af3_evolve /
af3_sota at mistral-large-latest, 5 tasks x 2 reps per arm (30
attempts, ~$15 on the user's Mistral credit), same arena/gate as af3,
run-ids mst3_{base,evolve,sota}. Directional only (n=10/arm; no
decision rule; reported as the first above-floor second-family data
point, whatever it shows). Launches AFTER the A104 opus chain exits
(wall integrity). Checkpoint: if any arm's first 10 attempts all fail
at layer<=1 with build_failed, the arm still completes (report-only) —
no mid-run scope changes.

## A104 PAUSED (user directive, 2026-07-16 evening)
Opus chain paused at control 201/244 (python pid killed exactly, no
survivors verified) to dedicate the machine and the July-19 window to
the Mistral cross-family work (A106+). The arm is resumable with the
identical registered command; per A104, an incomplete arm is NOT
reported. If the subscription ends before resumption, the opus tier
remains covered by the autoformalization directional rows only.

## A106b — pre-launch amendment (before any registered attempt)
With the opus chain paused and ~3 days of Mistral window, the A106
matrix is upgraded BEFORE launch from 2 to 4 reps/arm — making the
Mistral arms attempt-count-identical to the Claude af3 arms (5 tasks x
4 reps = 20 attempts/arm, 60 total, est. ~$30-60 on the user's key).
Same arms, arena, gate, order (base -> evolve -> sota), run-ids
mst3_{base,evolve,sota}. Also queued for the window (registered here):
A107 — a Mistral PROVING directional pair on dev60 (baseline + evolve
at mistral-large, 1 rep each), pending a driver adaptation smoke; the
AC's cross-family ask targeted the proving dev split. Report-only
throughout.

## A107 — PRE-REGISTERED: Mistral proving three-way on dev60
Driver adaptation smoke PASSED (mstp_smoke, EXCLUDED from analysis:
4/5 workbook problems solved by mistral-large through the evolve
interface, 5-8s solves, ~$0.01/attempt; grading via the real gate,
run_eval-identical arena and prompts). REGISTERED: the prompt-free
three-way on dev60 at mistral-large-latest — af_pf_baseline /
af_pf_session / af_pf_rocqmcp (env-bridged), 60 problems x 2 reps per
arm (360 attempts, est. $50-120 on the user's key), parallel 3, 300s
wall, cap-100 rail, run-ids mstp_{base,evolve,sota}_dev60. Launches
after the A106 autoform matrix exits (machine contention). Directional,
report-only: the first above-floor second-family PROVING comparison —
the AC's exact cross-family ask. Driver: harness/mistral_prover.py
(committed; reuses mistral_driver's MCP client + run_eval's build_task,
prompts, grading logic verbatim).

## A108 — PRE-REGISTERED, DIRECTION-BLIND: evolve pf arm rerun, tail removed
Round-3 review (artifact chair; verified in run_meta by both the AC and
the orchestrator): the "prompt-free" evolve arm's task template ends
with a tool-strategy sentence ("Use try with several candidate tactics
in one call; refine from what the results tell you") that neither the
control nor the sibling received — a prompt asymmetry in OUR favor
inside the matrix the write-up calls prompt-free. REGISTERED BEFORE
LAUNCH: af_pf_session2 = af_pf_session with the tail removed (template
verified byte-equal to the control's); FINAL_pf_session2_sonnet,
minif2f_test, 2 reps, parallel 8 (A80 conventions). SUPERSESSION RULE
(direction-blind, declared now): the rerun becomes the reported evolve
prompt-free row WHATEVER it shows — better, worse, or unchanged; the
tailed run stays in the record as the disclosed asymmetry exhibit. The
disclosure lands in the write-up immediately, before the rerun's data
exists. SEQUENCING: launches when the A106 Mistral autoform matrix
exits (machine contention); the A107 Mistral proving three-way runs
after this arm (a FINAL supersession arm outranks a directional one).
A107's evolve arm ALSO switches to af_pf_session2 (same fix, same
justification, registered here before any A107 attempt runs).

## A108 correction (minutes later): "byte-equal" overclaimed
The corrected template's RULES text is byte-equal to the control's; the
first sentence still differs — it is the registered per-arm completion-
mechanism sentence (A80 convention, like the sibling's submit sentence):
evolve states the theorem is already loaded in its session. What A108
removes is exactly and only the strategy-coaching tail. The asymmetry
class disclosed in the write-up is "strategy coaching", not "mechanism
description".

## A108 addendum (declared pre-launch, before any A108 attempt ran)

Primary confirmatory contrast for the A108 look, fixed now: pooled
(all-244, rep-0) exact McNemar vs the prompt-free control and vs the
prompt-free env-bridged sibling, Holm-adjusted within this two-test
family. Per-bucket estimates, CIs, and per-bucket paired tests are
reported descriptively only. This declaration is direction-blind: it
applies whichever way the numbers land, and the supersession rule of
the original A108 entry is unchanged.

## A109 — correction: A62b's "zero multi-call turns" was a counting artifact

The A62b supporting statistic ("zero multi-call turns in 2,109 assistant
messages", counted by harness/count_parallel_calls.py and echoed by the
autoform dashboard) counted per stream-json EVENT. The claude CLI emits
one content block per assistant event, so a per-event count cannot
exceed one tool call by construction — the audit could not have seen a
multi-call turn no matter how many existed. Recounted at the correct
granularity (tool_use blocks grouped by API message id) over the nine
ARCHIVED FINAL_* arms (all reps; the in-flight A108 arm excluded,
unopened): 2,409 multi-call turns of 63,246 tool-bearing assistant
turns (3.8%). Mistral arms (message.tool_calls arrays): 282 of 4,299
(6.6%). No harness setting disables parallel tool calls (only
tool_choice="auto" in mistral_driver.py:127; the claude CLI invocation
passes no such flag); execution of a multi-call turn's calls is
serialized by the runtime (verified on a concrete transcript instance).
DECISION IMPACT: none. A62b's decision (wall-bound protocol; turn caps
demoted to safety rails) rests on the serialization of execution and
the measured arena sign-flip, both unaffected; at a 3.8% batching rate
a turn budget remains, nearly one-for-one, a tool-call budget. The
count itself is corrected wherever quoted. count_parallel_calls.py to
be fixed to message-id granularity once no arms are running (no-builds
rule); the corrected scan script lives with the analysis artifacts.

## A110 — declared pre-completion: A108 contention/limit window repair rule

Between 18:00 and 19:10 (Europe/Paris) on 2026-07-16, the machine ran
concurrent heavy agent workloads alongside the in-flight A108 arm, and
the provider session limit was hit during part of that window (reset
19:10). Observed so far in A108's results (without opening transcripts):
rows with the A92 dead-stream signature (num_turns null, zero cost,
tool-call wrapper counts only). Mechanical repair rule, declared now,
before the arm completes and before any look: when A108 finishes, (i)
every row failing the A92 own-activity gate is quarantined and its slot
redone identically, and (ii) every wall-killed (attempt_timed_out) row
with ts inside [18:00, 19:10] 2026-07-16 is quarantined and redone
identically — load-inflated walls can kill attempts that would
otherwise complete, and kills inside the window are not
distinguishable from genuine ones, so all of them are redone. Solved
rows inside the window are KEPT (their inflated walls bias latency
against the arm; disclosed at reporting). Redos run with no concurrent
agent workloads. Rule is direction-blind: it keys on infrastructure
signatures and timestamps only, never on outcomes. Root cause noted for
ops: no multi-agent workloads while a measured arm runs — reaffirming
the existing no-heavy-builds rule, which this session violated.

## A110b — supplement (declared before any redo ran or was read)

The A108 infrastructure failures observed are stream deaths, not
no-activity dead streams: 90 rows whose transcripts contain model
activity but no terminal result event (equivalently, at results level:
num_turns null and cost null). The A92 no-activity gate catches zero of
them; the two mechanical signatures select the identical 90-row set,
verified before quarantine. Rule (i) of A110 is therefore executed with
"failing the A92 own-activity gate" replaced by the strictly-broader
mechanical signature "transcript lacks a terminal result event"; rule
(ii) adds nothing (zero window wall-kills outside that set). 90 slots
quarantined (rows preserved in results.quarantine.jsonl) and redone
identically on a quiet machine. Signature-keyed, timestamp-independent,
outcome-blind.

## A110c — second repair round (same rule, applied iteratively)

The first redo of the 90 quarantined A108 slots itself ran into the
provider session limit: 13 slots completed cleanly (solves with real
cost), 8 completed as ordinary failures, and 69 show the identical
terminal-result-event stream-death signature (zero poison markers in
transcripts — the limit failure never writes into them, which is why
the signature scan, not marker grep, is the detection rule). The A110b
rule is signature-keyed and therefore applies iteratively: the 69 are
quarantined (preserved in results.quarantine.jsonl) and will be redone
after the provider window resets (00:10), launched automatically behind
a canary check, on a machine running nothing else. No numbers from this
arm have been read; the registered look remains pending until the
signature scan over all 488 rows comes back clean.

## A110d — third repair round (same signature rule)

Round-2's redo also straddled a provider-limit window: 9 of its 69
slots completed cleanly, 60 show the stream-death signature and are
re-quarantined. Third redo launched immediately after a window reset
verified by canary, machine otherwise idle. Rule unchanged; still no
look.

## A110e — CORRECTION of A110b/c/d's failure model, and reconstruction rule

The "stream-death signature" of A110b (transcript lacks a terminal
result event; num_turns and cost null) is NOT an infrastructure
signature. Forensic check against the registered FINAL_pf_session_sonnet
arm: its 94 wall-killed rows are 94/94 turns-null and cost-null with no
terminal result event — this is the harness's NORMAL wall-kill shape
(the runner kills the CLI at the wall; kill costs are recovered from
API usage records, as registered). The A110b-d redos therefore
re-rolled legitimately wall-killed attempts; every solve they produced
is an undeclared extra roll and is void. All displaced rows are
preserved in results.quarantine.jsonl in append order (originals 1-90,
round-1 rows 91-159, round-2 rows 160-219; round-3 rows in the current
results file), so the arm is reconstructed mechanically:
- Non-window slots: the ORIGINAL first-pass row stands. Rounds 1-3 void.
- Window slots (original row wall-killed with ts in [18:00, 19:10]
  2026-07-16 — the concurrent-workload window of A110 rule (ii), the
  only defensible redo class): the ROUND-1 redo row stands (quiet
  machine, whatever its outcome — solve, completed failure, or kill).
  Rounds 2-3 void.
- All other rows in the current file produced by rounds 2-3 are void
  and replaced per the two rules above.
Disclosure: runner logs printed per-round aggregate solve counts
(13/90, 8/69, 5/60) before this correction was understood; the
reconstruction rule above is nevertheless purely mechanical
(order- and timestamp-keyed, no outcome consulted). The registered
look happens only after reconstruction passes the arm's actual
gates (A92 activity, A95 own-activity, poison markers, cap
terminations). Ops lesson appended to the runbook: turns-null +
cost-null + wall≈cap is the NORMAL kill shape; infrastructure damage
is detected by the A92/A95/poison gates, not by result-event absence.

## A111 — registered look: A108 arm (FINAL_pf_session2_sonnet)

Unlock logged now. Single consumption: per-arm registered quantities
(final_tables metrics, Wilson CIs) plus the A108-addendum primary
contrast (pooled exact McNemar vs prompt-free control and vs
prompt-free env-bridged sibling, Holm over the two-test family).
Per-bucket paired tests descriptive only. Numbers appended below after
the look; the A108 supersession rule then applies as registered.

## A111 (completed) — look results and supersession applied

FINAL_pf_session2_sonnet: e/m/h pass@1 .923/.709/.686 (Wilson CIs
.864-.958 / .601-.797 / .520-.814), pass@2 .938/.785/.714, $/solve
0.13/0.38/0.39, wall 41/115/127, kills 20/260, 41/158, 22/70. Pooled
200/244 = .820 pass@1, 209/244 = .857 pass@2. PRIMARY (pre-declared,
Holm/2): vs pf control 81:2, p<1e-5; vs pf env-bridged sibling 26:5,
raw p=.00019, Holm p=.00019. Descriptive: corrected vs superseded
evolve arm 15:8, p=.21 (consistent with no tail effect). Per the A108
registration, FINAL_pf_session2_sonnet SUPERSEDES
FINAL_pf_session_sonnet as the reported evolve prompt-free row;
superseded row remains in the record. Note: by the A108 addendum this
paired result is REGISTERED (contrast declared pre-look), unlike the
superseded arm's post-hoc pairing.

## A112 — driver artifact voids both Mistral sibling arms; fix + reruns

Author question ("is the sibling failing because no Mistral-format
interface exists for it?") led to a transcript check: the A107 sibling
proving arm exposed ONE tool to the model (final__submit) and the A106
sibling autoform arm exposed only the shared files__* tools — zero
prover tools in either. Mechanism, verified offline: the sibling runs
behind the instant-handshake prewarm proxy (built for the claude CLI
startup race), which answers tools/list immediately — with an empty
list while the petanque backend boots; mistral_driver's handshake
called tools/list exactly once, so under run-time load the sibling's
surface was empty every time, while an idle-machine reproduction
returns all 11 tools. The model's single blind submit (118/120) was
the only possible behavior, not a disposition finding. This is a
confound-schema instance: the harness silently assumed
handshake-tool-list == server tool surface, and the failure was
differential by arm (only the sibling boots behind the proxy).
CONSEQUENCE: mstp_sota_dev60 and mst3_sota are VOID as interface
measurements (rows retained, marked void); the evolve and base arms
delivered their surfaces (5- and 1-tool inits as configured) and
stand, with the base arm renamed precisely (a write-and-check loop,
not the claude arms' file-editing surface). FIX: handshake now polls
tools/list until non-empty (120 s deadline). RERUNS, declared now,
direction-blind, reported whichever way they land: mstp_sota_dev60_v2
(dev60, 2 reps, parallel 3) then mst3_sota_v2 (autoform, 4 reps),
sequential, after an init-line spot check confirms 11+ tools.

## A112b — mechanism correction: the filter, not the handshake race

The A112 rerun still exposed one tool, which falsified the proxy-race
mechanism: the handshake (cache-backed proxy) returns all 11 sibling
tools even under load. The actual defect is the allowed-tools filter in
both Mistral drivers: str.replace("mcp__", "") strips ALL occurrences,
and the sibling's server name "rocqmcp" itself contains "mcp__" once
prefixed ("mcp__rocqmcp__X" -> "rocqrocqX"-class garbage), so every
sibling tool failed the allow-list while evolve ("rocq") and the submit
server ("final") were untouched — a name-dependent, arm-differential
filter bug. Fixed with removeprefix (prefix-only). The A112 handshake
poll patch stays as robustness. Void verdicts and declared reruns of
A112 unchanged; reruns relaunched after an init-line check shows the
full sibling surface. The confound-schema instance sharpens: the
harness silently assumed name-mangling is injective across arms.

## A112 completion — remeasured sibling arms (full surface verified)

Proving (mstp_sota_dev60_v2, 120/120 rows, 0 crippled inits; 25
pre-fix rows quarantined): pass@1 13/60 = .217, pass@2 17/60 = .283,
$/solve 2.517, wall-solved 38.5s, median 6 tool calls, 1/120
single-call. Ordering at mistral-large (dev60, directional): evolve
.350 > control .250 > sibling .217. The evolve-vs-control direction
transfers; the full Claude-tier ordering does not — the sibling lands
below the check-loop control at this family (descriptive, n=60, no
significance claims, no mechanism claim). Autoform remeasurement
(mst3_sota_v2, 20/20, 16-tool surface verified): 0/20 — the family
autoform floor now genuinely covers all three interfaces. A112 closed.

## A113 — pre-registration: second-family held-out matrix (Mistral, full scale)

Declared before launch. Arms, sequential, quiet machine, mistral_prover
(post-A112 driver: prefix-only strip, patient handshake): model
mistral-large-latest, manifest minif2f_test (244 problems), reps 2,
parallel 3, wall 300 s: (1) af_pf_baseline -> mstf_base_test; (2)
af_pf_session2 -> mstf_evolve_test; (3) af_pf_rocqmcp ->
mstf_sota_test. Acting-floor screen: PASSED pre-launch by the A112
remeasured dev60 arms (all three interfaces operated in earnest:
median 15/30/6 calls; recorded here as the registered screen result;
the screen rule for any future family: an arm is above the floor iff
its dev-scale run shows median >= 3 tool calls per attempt and
completed non-vacuous artifacts). Integrity gates for the look: 488
rows per arm; per-attempt init tool-surface minimums (base >= 1,
evolve >= 5, sibling >= 12) with any violation quarantining the
affected rows for identical-slot redo; no other exclusions. PRIMARY
CONTRAST, fixed now: pooled exact McNemar (rep-0) evolve-vs-control
and evolve-vs-sibling, Holm over the two-test family; per-bucket and
efficiency quantities descriptive. Single registered look after all
three arms pass gates. Direction-blind: results reported whichever way
they land, including a failure of the ordering to transfer, which
would be reported as a co-adaptation finding of equal standing.

## A113-look (autonomous, 2026-07-19 17:00 CEST) — status: CLEAN

Registered look executed by harness/a113_look.py (no agent; math
pre-validated against the A111 arms). Full result:
logs/a113_look_result.json / .txt. Direction-blind per A113.
Infrastructure note: run completed at parallel 3; latency-under-load
not a factor. If status is BLOCKED, surface/poison gates flagged
contaminated rows and NO contrasts were computed — quarantine+redo
per A113 then rerun the look.

```
{
 "pre_registration": "A113",
 "arms": {
  "control": "mstf_base_test",
  "evolve": "mstf_evolve_test",
  "sibling": "mstf_sota_test"
 },
 "status": "CLEAN",
 "metrics": {
  "control": {
   "easy": {
    "n": 130,
    "pass1": 0.162,
    "pass1_ci": [
     0.108,
     0.234
    ],
    "pass2": 0.215,
    "cost_per_solve": 2.864,
    "latency_solved_s": 28.7
   },
   "medium": {
    "n": 79,
    "pass1": 0.038,
    "pass1_ci": [
     0.013,
     0.106
    ],
    "pass2": 0.038,
    "cost_per_solve": 12.879,
    "latency_solved_s": 48.7
   },
   "hard": {
    "n": 35,
    "pass1": 0.0,
    "pass1_ci": [
     0,
     0.099
    ],
    "pass2": 0.0,
    "cost_per_solve": null,
    "latency_solved_s": null
   },
   "pooled": {
    "n": 244,
    "pass1": 0.098,
    "pass2": 0.127
   }
  },
  "evolve": {
   "easy": {
    "n": 130,
    "pass1": 0.423,
    "pass1_ci": [
     0.342,
     0.509
    ],
    "pass2": 0.469,
    "cost_per_solve": 3.341,
    "latency_solved_s": 17.6
   },
   "medium": {
    "n": 79,
    "pass1": 0.063,
    "pass1_ci": [
     0.027,
     0.14
    ],
    "pass2": 0.101,
    "cost_per_solve": 28.281,
    "latency_solved_s": 30.5
   },
   "hard": {
    "n": 35,
    "pass1": 0.029,
    "pass1_ci": [
     0.005,
     0.145
    ],
    "pass2": 0.029,
    "cost_per_solve": 86.078,
    "latency_solved_s": 2.7
   },
   "pooled": {
    "n": 244,
    "pass1": 0.25,
    "pass2": 0.287
   }
  },
  "sibling": {
   "easy": {
    "n": 130,
    "pass1": 0.108,
    "pass1_ci": [
     0.065,
     0.173
    ],
    "pass2": 0.138,
    "cost_per_solve": 6.123,
    "latency_solved_s": 24.6
   },
   "medium": {
    "n": 79,
    "pass1": 0.025,
    "pass1_ci": [
     0.007,
     0.088
    ],
    "pass2": 0.038,
    "cost_per_solve": 26.967,
    "latency_solved_s": 22.5
   },
   "hard": {
    "n": 35,
    "pass1": 0.0,
    "pass1_ci": [
     0,
     0.099
    ],
    "pass2": 0.0,
    "cost_per_solve": null,
    "latency_solved_s": null
   },
   "pooled": {
    "n": 244,
    "pass1": 0.066,
    "pass2": 0.086
   }
  }
 },
 "primary_contrast": {
  "evolve_vs_control": {
   "discordant": "38:1",
   "raw_p": 0.0,
   "holm_p": 0.0
  },
  "evolve_vs_sibling": {
   "discordant": "46:1",
   "raw_p": 0.0,
   "holm_p": 0.0
  }
 },
 "ordering": [
  [
   "evolve",
   0.25
  ],
  [
   "control",
   0.098
  ],
  [
   "sibling",
   0.066
  ]
 ]
}
```

## A114 — pre-registration: finisher-only zero-model arm (attribution)

Declared before launch, direction-blind (AC flip-condition (a); the
result is reported whichever way it lands, including "the portfolio
earns the bulk of the margin", which would be reported as re-measured
automation). ARM: no LLM anywhere. For each of the 244 test problems
(1 rep — the policy is deterministic): spawn the af_pf_session2 server
exactly as the model arms do (same env, task preload, wall 300 s), then
apply the FIXED policy: call rocq__auto_close repeatedly until it
reports no finisher applies / no open goals / 10 calls / wall; then
grade work/candidate.v through the standard gate (identical
newest-submission-else-candidate logic). Run id: finisher_only_test.
ANALYSIS, fixed now: report the finisher-only solve set F (pooled +
per bucket) beside tab:heldout; mechanism partition by problem-level
overlap: F vs the rep-0 solve sets of FINAL_pf_session2_sonnet (E),
FINAL_pf_baseline_sonnet, FINAL_pf_rocqmcp_sonnet, and
mstf_evolve_test; headline quantities |F|, |E∩F| (portfolio-closable
share of evolve's solves, an upper bound on portfolio-attributable
solves) and |E\F| (solves requiring the model in the loop). No
significance tests. Machine idle during the run.

## A114-look — finisher-only result and partition (as declared)

F = 52/244 pooled .21 (46/5/1 e/m/h; 130/79/35 buckets -> .35/.06/.03).
Flagship attribution: E (FINAL_pf_session2_sonnet rep-0, 200 solves):
E∩F = 52 (26%, the upper bound on portfolio-attributable solves),
E\F = 148 (74% model-required); F\E = 0. Sonnet control ∩F = 48,
sibling ∩F = 52. The sonnet-tier interface margin survives attribution:
148 model-required solves vs the control's 121 total. Cross-family
attribution: mstf_evolve_test rep-0 (61 solves): ∩F = 50 (82%), model-
required 11; mistral check-loop control 24 total (∩F 20); mistral
sibling 16. The model-free finisher (52) outscores every mistral arm
except evolve (61): the A113 transferred margin at this capability tier
is largely the interface's built-in finisher portfolio, with an
11-problem model-in-the-loop residue. Both findings reported per the
A114 direction-blind rule. Scripts: harness/finisher_only.py,
tables/finisher_partition.py; artifact finisher_partition.json.

## A115 — pre-registration: third-family calibration (dev60, GPT-5.6 Terra via OpenRouter)

Declared before launch. PURPOSE: acting-floor check and per-attempt
cost calibration for a third model family, on the dev sample only — no
held-out problem is touched under this entry. MODEL: openai/gpt-5.6-terra
(OpenAI's current workhorse tier, tier-matched to the sonnet and
mistral-large arms) served first-party through OpenRouter; reasoning
effort "low" (recorded in run_meta and per-row); driver
harness/openrouter_prover.py — same MCP client, task prompts, arena
(wall 300 s, max_turns 100), and gate as the A107/A113 runners; cost is
the exact per-response charged amount (usage.cost), with cached and
reasoning token counts recorded per row. Credit budget is hard-capped
at $500 server-side; the driver refuses new attempts below a $40
remaining floor, and credit-aborted attempts are void (no row), never
non-solves. ARMS (byte-identical configs to A113): af_pf_baseline /
af_pf_session2 / af_pf_rocqmcp; manifest dev60; 2 reps; parallel 3;
sequential chain in that order; run ids orp_base_dev60,
orp_evolve_dev60, orp_sib_dev60. Smoke runs orp_smoke_* (4 attempts,
$0.01 total) validated tool transport, caching, and cost accounting.
GATES for proceeding to a held-out matrix (to be registered separately
as A115b BEFORE any held-out attempt): (1) acting floor — per-arm
tool-surface minima 1/5/12 as in A113, poison sweep (turns<=2
non-solves with API-error text) clean; (2) cost — projected full
matrix cost = sum over arms of (mean cost/attempt x 244 x 2 reps)
must be <= $360 of remaining credit. If (2) fails for Terra, the
pre-declared fallback is z-ai/glm-5.2 under the same two gates (one
fallback only); if that also fails, a stratified fixed-seed subsample
design will be registered instead. The dev60 results themselves are
reportable as dev-sample calibration under the usual dev-sample
caveats, whichever way they land.

## A115-cal — dev60 calibration result (as declared)

Both A115 gates PASS. Acting floor: all three arms far above the
surface minima; poison sweep clean (0 rows; 2/360 attempts hit a
transient malformed API response, driver hardened to retry, both
backfilled). Scores (pass@1 (pass@2), buckets 20/20/20): control
.90 (.93), evolve .95 (.98), sibling .93 (.93) — near-ceiling in ALL
arms at this capability tier; dev-sample arm spreads are compressed
(3-problem pass@1 differences) and carry no comparative weight. Cost:
$0.0264-0.0460/attempt (evolve arm cheapest); cache hit fraction
.87-.93; dev60 spend $13.39; projected full held-out matrix (244 x 2
reps x 3 arms) $54.45 <= $360 -> proceed with gpt-5.6-terra; the
z-ai/glm-5.2 fallback is not triggered. Held-out design to be
registered as A115b before any test attempt.

## A115b — pre-registration: third-family held-out matrix (gpt-5.6-terra)

Declared before any test-split attempt, per A115-cal gate PASS. ARMS:
af_pf_baseline / af_pf_session2 / af_pf_rocqmcp, byte-identical configs
to A113; manifest minif2f_test (244 problems); 2 reps; model
openai/gpt-5.6-terra via OpenRouter (first-party OpenAI serving,
reasoning effort low, contexts far below the 272k surcharge line);
driver harness/openrouter_prover.py; run ids orp_base_test,
orp_evolve_test, orp_sib_test. EXECUTION: single sequential chain,
arms interleaved in blocks of 20 attempt-slots (rep-major order:
rep 0 completes across all arms before rep 1), parallel 3 within an
invocation, machine otherwise idle; credit floor $40 (credit-aborted
attempts are void, never rows). Projected cost $54 against $486
remaining; if the floor nonetheless halts the chain, the row-count
gate of the look will BLOCK and the fallback analysis (maximal set of
problems with both reps complete in all three arms) will be registered
before being run. LOOK (single consumption): harness/a115_look.py,
executed autonomously at chain end — identical gates, metrics, and
pre-declared primary contrast to A113 (pooled exact McNemar rep-0,
evolve-vs-control and evolve-vs-sibling, Holm over the two-test
family); the script was validated by re-running the A113 arms and
reproducing the recorded A113 result exactly before this registration.
No supersession: this adds a family; no recorded number is replaced.
The result is recorded whichever way it lands, explicitly including
compression or reversal of arm spreads at this capability tier.

## A116 — pre-registration: autoformalization three-way (gpt-5.6-terra)

Declared before launch. Replication of the mst3 dev-style suite on the
third family: configs af3_base / af3_evolve / af3_sota byte-identical
to mst3; all 5 tasks (frugal, gauges, ledger, prodauto, triadic) x 4
reps; parallel 2; driver harness/openrouter_autoform.py (same servers,
prompts, budgets, and autoform_gate grading as mistral_driver); run ids
orp3_base, orp3_evolve, orp3_sota, after a single-attempt smoke
(orp3_smoke). Runs strictly AFTER the A115b chain and look complete
(no concurrent measured runs). Dev-style suite: reported in the same
per-task format as mst3, direction-blind, no held-out claim. Reporting
of layers/probe metrics identical to the recorded mst3 treatment.

## A115c — external-kill incident during A115b: forensics, repair rule, resume

INCIDENT: an unrelated agent process on this host ran a memory watchdog
during the A115b matrix (and, per its own report, back through the
A115-cal tail): 12 Rocq compile workers killed at 16-40 GB RSS, one
path-pinned to orp_sib_dev60/lean_workbook_plus_66199__rep0. The chain
was stopped on notification (matrix ~45% complete); the operator
confirmed the watchdog is stopped. FORENSICS (all recorded before any
repair): no SIGKILL or server-death markers anywhere in the six runs'
transcripts; driver crashes write no row (self-healing under resume);
tool-timeout rates per arm are within or near the A113 killer-free
base rates (sibling test 6/200 vs 3/488, mildly elevated); all 22
compile-failure rows (4 sib dev60, 18 sib test) were deterministically
replayed with the arm's own config on an idle host — 0 flips, all
recompile_failed, i.e. genuine session-vs-file divergence rejects, not
kill artifacts. (A first replay pass omitted the config prefix_prepend,
produced a uniform prefix_modified artifact, and was discarded as a
methodology error before any verdict was accepted.) REPAIR RULE
(mechanical, uniform across arms, fixed before outcomes): void and
redo every attempt whose transcript contains a tool-call timeout AND
whose row is a non-solve, plus the externally path-pinned attempt.
Solves stand: a kill cannot manufacture a solve (grading requires a
successful gate compile), so contamination is deflation-only, and it
lands mainly on the sibling arm — i.e. against the baselines. VOIDS
(19): base_dev60 66199 r0 r1; evolve_dev60 66199 r0; sib_dev60 66199
r0(pinned) r1, 66169 r1, 23430 r1; base_test mathd_numbertheory_341
_430 _457 _234, amc12a_2003_p5, amc12b_2002_p7 (all r0); sib_test
imo_1984_p6, amc12_2000_p12, amc12a_2003_p5, amc12a_2021_p9,
amc12_2001_p21, imo_1965_p2 (all r0). The recurring problems (66199,
66169, 23430 across multiple arms) are compile memory bombs; their
redos may legitimately fail again under the unchanged arena — either
outcome stands. Execution: dev60 voids refilled first, calibration
metrics recomputed to logs/a115_cal_recheck.json (gates re-verified;
margins were 7x), then the matrix resumes under the registered A115b
execution plan (parallel 3 unchanged), look and A116 unchanged.

## A115c-b — chain-kill root cause, orphan mechanism, and execution hardening

The resumed chain's process group died at ~00:30 (external to this
session; the operator did not stop it). The watchdog operator's ledger
(coordinated directly): its 12 kills were hand-issued single-PID
SIGTERMs on rocqworkers 14:30-22:30 only, never process groups or
drivers, stopped before midnight — leaving macOS memory-pressure
termination as the leading explanation for the group kill: the resumed
chain front-loaded six voided compile memory bombs at parallel 3 on
top of orphaned workers. ORPHAN MECHANISM identified: a client-side
tool-call timeout abandons the server's compile; McpServer.close()
terminated only the server process, so rocqworker grandchildren
survived as multi-GB orphans (three found at 16-40 GB, PPID 1, cwds in
this campaign's own attempt dirs; killed with peer no-objection). Two
matrix rows (mathd_numbertheory_430 r0, _457 r0) were written while a
crashed prior try's compiler was live in the same work directory —
re-voided under the same-dir-overlap rule; the other four in-window
rows stand (no dir overlap; solves are immune since grading compiles
candidate text in a fresh tempdir). A sweep for SIGTERM markers
(signal 15/143/Terminated) across all six runs found none — the A115c
void net was complete. HARDENING (disclosed execution changes, arena
untouched): (1) McpServer.close() now SIGTERMs the server's process
group, preventing orphan accumulation; (2) matrix resumes at parallel
2 (uniform across arms from a problem-block boundary) bounding worst
case ~80 GB on the 96 GB host; (3) hands-off agreement in force with
the other host agent (no kills under rocq-tools/_opam or logs; memory
danger is messaged, not killed).

## A115c-c — second orphan class closed (detached compile workers)

A 58 GB rocqworker orphan (PPID 1, 17 min old, cwd in the redone
mathd_numbertheory_457 rep0 attempt dir) appeared despite the A115c-b
process-group teardown: compile workers detach from the server's pgid,
so killpg cannot reach them. The orphan was killed (recorded row
unaffected: grading completed at attempt end, before the worker was
reaped). Fix: sweep_workers(scope_dir) in the shared driver — at
attempt teardown, any rocqworker whose cwd lies inside the attempt's
own directory is SIGTERMed. cwd-scoped, so it cannot touch other arms'
or other agents' processes; takes effect from the next chain
invocation (per-invocation import). Arena untouched: the sweep runs
after grading.

## A115c-d — third orphan class closed (gate-compile workers); chain killed again

The hardened chain's group was killed a second time (external, deep in
rep 1; rep 0 complete across arms). Kernel logs yielded no direct
jetsam evidence; attribution remains host memory pressure
(circumstantial). Found: a 27.6 GB rocqworker orphan, PPID 1, 20 min
old, compiling a /private/tmp gate tempfile — the GRADING-time compile
class: subprocess timeout kills only the direct `rocq compile`
process, the worker detaches and survives; and grading runs after the
attempt-teardown sweep, so A115c-c could not see it. (The other host
agent's earlier "/private/tmp attempt compile" kill was this same
class.) Fixes: (1) gate._run_rocq reaps workers referencing its unique
tempfile name on timeout; (2) both drivers sweep the attempt dir again
after grading. Grading semantics unchanged (timeout verdicts
identical); cleanup only. Orphan killed; chain relaunched (resume).

## A115b-look (autonomous) - third-family held-out matrix result

Recorded by the registered look script at chain end, as declared; status CLEAN. Chain resumed post-A115c repair.

```json
{
 "pre_registration": "A115b",
 "arms": {
  "control": "orp_base_test",
  "evolve": "orp_evolve_test",
  "sibling": "orp_sib_test"
 },
 "status": "CLEAN",
 "metrics": {
  "control": {
   "easy": {
    "n": 130,
    "pass1": 0.715,
    "pass1_ci": [
     0.633,
     0.786
    ],
    "pass2": 0.769,
    "cost_per_solve": 0.105,
    "latency_solved_s": 70.6
   },
   "medium": {
    "n": 79,
    "pass1": 0.418,
    "pass1_ci": [
     0.315,
     0.528
    ],
    "pass2": 0.443,
    "cost_per_solve": 0.28,
    "latency_solved_s": 110.9
   },
   "hard": {
    "n": 35,
    "pass1": 0.286,
    "pass1_ci": [
     0.163,
     0.451
    ],
    "pass2": 0.343,
    "cost_per_solve": 0.418,
    "latency_solved_s": 135.3
   },
   "pooled": {
    "n": 244,
    "pass1": 0.557,
    "pass2": 0.602
   }
  },
  "evolve": {
   "easy": {
    "n": 130,
    "pass1": 0.969,
    "pass1_ci": [
     0.924,
     0.988
    ],
    "pass2": 0.985,
    "cost_per_solve": 0.025,
    "latency_solved_s": 40.8
   },
   "medium": {
    "n": 79,
    "pass1": 0.81,
    "pass1_ci": [
     0.71,
     0.881
    ],
    "pass2": 0.848,
    "cost_per_solve": 0.088,
    "latency_solved_s": 92.9
   },
   "hard": {
    "n": 35,
    "pass1": 0.714,
    "pass1_ci": [
     0.549,
     0.837
    ],
    "pass2": 0.771,
    "cost_per_solve": 0.103,
    "latency_solved_s": 92.9
   },
   "pooled": {
    "n": 244,
    "pass1": 0.881,
    "pass2": 0.91
   }
  },
  "sibling": {
   "easy": {
    "n": 130,
    "pass1": 0.946,
    "pass1_ci": [
     0.893,
     0.974
    ],
    "pass2": 0.946,
    "cost_per_solve": 0.039,
    "latency_solved_s": 44.1
   },
   "medium": {
    "n": 79,
    "pass1": 0.671,
    "pass1_ci": [
     0.561,
     0.764
    ],
    "pass2": 0.722,
    "cost_per_solve": 0.142,
    "latency_solved_s": 102.1
   },
   "hard": {
    "n": 35,
    "pass1": 0.657,
    "pass1_ci": [
     0.492,
     0.792
    ],
    "pass2": 0.714,
    "cost_per_solve": 0.146,
    "latency_solved_s": 100.7
   },
   "pooled": {
    "n": 244,
    "pass1": 0.816,
    "pass2": 0.84
   }
  }
 },
 "primary_contrast": {
  "evolve_vs_control": {
   "discordant": "79:0",
   "raw_p": 0.0,
   "holm_p": 0.0
  },
  "evolve_vs_sibling": {
   "discordant": "21:5",
   "raw_p": 0.002494,
   "holm_p": 0.002494
  }
 },
 "ordering": [
  [
   "evolve",
   0.881
  ],
  [
   "sibling",
   0.816
  ],
  [
   "control",
   0.557
  ]
 ]
}
```

## A115c-e — fourth orphan class (autoform staging builds); restart sweep

Third external group kill, during the A116 base arm (18/20 rows; the
matrix and registered look were already complete and committed —
unaffected). Found: a 27.8 GB PPID-1 rocqworker, 22 min old, cwd in an
afgate_* staging dir — autoform_gate.run()'s subprocess timeout kills
only the direct child, and the staging dir lies outside the attempt
dir, invisible to the A115c-c/d sweeps. Also recognized: a group kill
itself orphans in-flight attempts' workers (their teardown sweeps
never run), re-seeding the pressure cycle that likely invites the next
kill. Fixes: (1) autoform_gate.run() reaps workers under its own cwd
on timeout, then re-raises (caller semantics unchanged); (2) the chain
script begins with a stale-orphan sweep — PPID-1 rocqworkers whose cwd
is in this campaign's logs tree, an afgate_* staging dir, or a
/private/tmp gate compile — so restarts never inherit pressure. All
reaps remain cwd/PPID-scoped. A116 resumes (2 base attempts + evolve +
sota arms).

## A116-look — autoform three-way result (as declared)

All arms complete, poison sweeps clean. Dev-style per-task counts
(solved/4 reps): base 10/20 (frugal 4, gauges 0, ledger 4, prodauto 0,
triadic 2); evolve 12/20 (frugal 4, gauges 2, ledger 4, prodauto 1,
triadic 1); sota 7/20 (frugal 3, gauges 2, ledger 2, prodauto 0,
triadic 0). No significance tests, per registration. Reference point:
the second family's mst3 arms scored 0/20 in ALL three configurations
at 15-25x the cost — the autoformalization acting floor sits above
that family's capability; the third family clears it in every arm,
with the evolved interface leading. Costs: $5.82/$4.38/$6.98.
Cross-family attribution extension (A114 partition form, post hoc):
terra evolve rep-0 |E|=215, E∩F=52, model-required 163 (76%), F ⊆ E;
control |E|=136 (64% model-required, |F\E|=3); sibling |E|=199 (74%).
The model-required count of the evolved arm alone (163) exceeds the
control's total solve count (136). CAMPAIGN LEDGER: total third-family
spend $131.47 of the $500 hard budget ($368.53 remaining); chain
completed autonomously after the A115c/c-b/c-c/c-d/c-e repairs with
zero further external kills.

## A117 — pre-registered: completing the A104 opus arc (subscription restored)

Declared before launch, on the operator's directive to finish the A104
scope natively. (1) CONTROL COMPLETION: FINAL_pf_baseline_opus resumes
its remaining 43 attempts under the identical config and pinned model
(claude-opus-4-8), a 31-day gap disclosed; the remainder is the fixed
manifest tail, so no outcome-based selection is possible. The arm is
reported only when complete (A104 rule stands). (2) CONFIG
SUBSTITUTION, fairness-motivated and decided before any opus evolve
attempt: A104 named af_pf_session_opus, which carries the pre-A108
task text whose tool-strategy tail the sonnet supersession removed;
the evolve arm instead runs af_pf_session2_opus — the corrected
session2 config verbatim (task prompt byte-identical to the reported
sonnet arm's) with only the model id swapped. Run id
FINAL_pf_session2_opus. (3) SIBLING: af_pf_rocqmcp_opus runs third,
sequentially (FINAL_pf_rocqmcp_opus); any arm interrupted by quota
limits resumes; incomplete arms are not reported. (4) SCOPE: 1 rep,
244 problems, 300 s wall, parallel 4, pass@1 only; REPORT-ONLY as in
A104 — no registered contrast attaches, and any later paired analysis
is post hoc and labeled as such. (5) LOOK: harness/a117_look.py at
chain end, autonomous (row-count and poison gates per arm, per-arm
metrics only), result appended to this trail and committed by the
chain. Ops: single sequential caffeinated chain, machine otherwise
idle, no agent fan-out while arms run.

## A117b — machine-sleep incident during the control tail; repair and resume

The host slept mid-chain: the harness's per-attempt watchdog flagged
"machine slept during attempt" (wall-mono drift), four in-flight
workers dropped to dead streams (zero assistant events) and wedged in
the park-retry loop for ~4.4 h. A CLI probe confirmed auth, quota, and
the pinned model healthy. MECHANICAL VOID (rule fixed before
outcomes): last-24 h rows with wall > 330 s, OR harness sleep flag in
kill.log, OR zero-tool-call zero-cost non-solves — 4 rows voided and
redone (457, 495, 483, 451; 11 healthy fresh solves stand; poison
sweep otherwise clean). Chain relaunched from 215/244 control rows
with caffeinate extended to prevent system sleep on AC power. Arena
unchanged.

## A117-look (autonomous) - opus arc result

Recorded by the look script at chain end, as declared; status CLEAN.

```json
{
 "pre_registration": "A117 (A104 scope)",
 "arms": {
  "control": {
   "run": "FINAL_pf_baseline_opus",
   "status": "COMPLETE",
   "metrics": {
    "easy": {
     "n": 130,
     "pass1": 0.785,
     "pass1_ci": [
      0.706,
      0.847
     ],
     "cost_per_solve": 0.229,
     "latency_solved_s": 80.5,
     "kill_pct": 22
    },
    "medium": {
     "n": 79,
     "pass1": 0.443,
     "pass1_ci": [
      0.339,
      0.553
     ],
     "cost_per_solve": 0.423,
     "latency_solved_s": 136.3,
     "kill_pct": 54
    },
    "hard": {
     "n": 35,
     "pass1": 0.343,
     "pass1_ci": [
      0.208,
      0.508
     ],
     "cost_per_solve": 0.584,
     "latency_solved_s": 187.2,
     "kill_pct": 66
    },
    "pooled": {
     "n": 244,
     "pass1": 0.611
    }
   }
  },
  "evolve": {
   "run": "FINAL_pf_session2_opus",
   "status": "COMPLETE",
   "metrics": {
    "easy": {
     "n": 130,
     "pass1": 0.892,
     "pass1_ci": [
      0.827,
      0.935
     ],
     "cost_per_solve": 0.17,
     "latency_solved_s": 49.3,
     "kill_pct": 11
    },
    "medium": {
     "n": 79,
     "pass1": 0.608,
     "pass1_ci": [
      0.497,
      0.708
     ],
     "cost_per_solve": 0.391,
     "latency_solved_s": 120.4,
     "kill_pct": 39
    },
    "hard": {
     "n": 35,
     "pass1": 0.514,
     "pass1_ci": [
      0.356,
      0.67
     ],
     "cost_per_solve": 0.552,
     "latency_solved_s": 178.1,
     "kill_pct": 51
    },
    "pooled": {
     "n": 244,
     "pass1": 0.746
    }
   }
  },
  "sibling": {
   "run": "FINAL_pf_rocqmcp_opus",
   "status": "COMPLETE",
   "metrics": {
    "easy": {
     "n": 130,
     "pass1": 0.892,
     "pass1_ci": [
      0.827,
      0.935
     ],
     "cost_per_solve": 0.256,
     "latency_solved_s": 61.8,
     "kill_pct": 11
    },
    "medium": {
     "n": 79,
     "pass1": 0.544,
     "pass1_ci": [
      0.435,
      0.65
     ],
     "cost_per_solve": 0.476,
     "latency_solved_s": 115.4,
     "kill_pct": 44
    },
    "hard": {
     "n": 35,
     "pass1": 0.514,
     "pass1_ci": [
      0.356,
      0.67
     ],
     "cost_per_solve": 0.66,
     "latency_solved_s": 184.1,
     "kill_pct": 51
    },
    "pooled": {
     "n": 244,
     "pass1": 0.725
    }
   }
  }
 },
 "status": "CLEAN"
}
```

## A118 — pre-registered: haiku-tier held-out comparators (weekly-window scope)

Declared before launch. PURPOSE: complete the haiku tier of the
prompt-free matrix — the existing wall-only \evolve arm
(FINAL_frozen_wallonly, claude-haiku-4-5, 488 rows) has never had
comparators on the split. ARMS: af_pf_baseline_haiku and
af_pf_rocqmcp_haiku — the sonnet pf configs verbatim with only the
model id swapped to claude-haiku-4-5 (matching the evolve arm's pinned
model, verified served on every sampled attempt); run ids
FINAL_pf_baseline_haiku, FINAL_pf_rocqmcp_haiku; 244 problems, target
2 reps, parallel 4 (matched to the evolve arm's execution), 300 s
wall, cap-100 safety rail required non-binding by the look gate.
SCHEDULING CONSTRAINT (operator): the chain runs only inside the
current weekly-credit window under a hard 9 h timeout — rep-0 for both
arms first (control, then sibling), rep-1 only as time allows; an arm
is analyzable at rep-0-complete (244 rows, pass@2 absent) or full
(488); anything else is ABSENT and unreported. PRIMARY CONTRAST
(registered): pooled exact McNemar on rep-0 pairs, evolve vs control
and evolve vs sibling, Holm over the two-test family. DISCLOSURE: the
evolve arm's per-arm numbers are already recorded and public in this
trail, so this registration is of the same registered-after-
partial-knowledge class as the pf sibling arm's (disclosed in the
look-sequence note); the contrasts themselves are computed by
harness/a118_look.py autonomously at chain end, no model in the loop.
Poison sweep in-gate; machine on AC with system-sleep prevention; no
agent fan-out while arms run.

## A118-look (autonomous) - haiku comparator result

Recorded at chain end, as declared; status BLOCKED.

```json
{
 "pre_registration": "A118",
 "arms": {
  "control": {
   "run": "FINAL_pf_baseline_haiku",
   "status": "ABSENT (293 rows)"
  },
  "evolve": {
   "run": "FINAL_frozen_wallonly",
   "status": "COMPLETE",
   "metrics": {
    "easy": {
     "n": 130,
     "pass1": 0.669,
     "pass1_ci": [
      0.585,
      0.744
     ],
     "cost_per_solve": 0.065,
     "latency_solved_s": 51.4,
     "kill_pct": 33,
     "pass2": 0.715
    },
    "medium": {
     "n": 79,
     "pass1": 0.253,
     "pass1_ci": [
      0.17,
      0.359
     ],
     "cost_per_solve": 0.265,
     "latency_solved_s": 107.2,
     "kill_pct": 56,
     "pass2": 0.329
    },
    "hard": {
     "n": 35,
     "pass1": 0.086,
     "pass1_ci": [
      0.03,
      0.224
     ],
     "cost_per_solve": 0.68,
     "latency_solved_s": 156.5,
     "kill_pct": 73,
     "pass2": 0.171
    },
    "pooled": {
     "n": 244,
     "pass1": 0.451,
     "pass2": 0.512
    }
   }
  },
  "sibling": {
   "run": "FINAL_pf_rocqmcp_haiku",
   "status": "GATE-FAIL",
   "failures": [
    "FINAL_pf_rocqmcp_haiku: 3 rail-bound non-solves (rail must not bind)"
   ]
  }
 },
 "status": "BLOCKED",
 "gate_failures": [
  "FINAL_pf_rocqmcp_haiku: 3 rail-bound non-solves (rail must not bind)"
 ]
}
```

## A118b — window outcome, look-criterion fix, rail-parity repair (redos pending)

The 9 h ceiling cut during control rep-1 (49/244 rows; excluded from
analysis per registration). LOOK IMPLEMENTATION CORRECTED before any
contrast was computed or seen (the first look BLOCKED and emitted no
comparator numbers): analyzability now tests rep-0 completeness as the
registration specifies, rather than total row count; partial rep-1
tails are excluded; per-arm gating; the Holm multiplier is fixed at 2,
the registered family size, regardless of how many arms are
analyzable at a look. RAIL PARITY DEFECT, caught by the look's own
gate: the comparator configs cloned the sonnet cap-100 rail while the
evolve haiku arm ran cap-200, and at haiku pace the 100-turn rail
BOUND on 4 rep-0 non-solves (3 sibling: induction_1pxpownlt1pnx,
mathd_algebra_114, mathd_algebra_598; 1 control, same mechanical
rule). Those rows are voided; both configs now carry the evolve arm's
cap-200 rail; the 4 redos (and any rep-1 completion) are DEFERRED
awaiting the operator's clearance to spend post-renewal weekly credit,
per the A118 scheduling constraint. No contrast has been computed on
any comparator arm to date.

## A119 — PRE-REGISTERED: opus rep-1 (matrix completion) + the A118 redos

Declared before any attempt, on the operator's directive to complete
the held-out matrix.

(1) SCOPE: rep 1 for all three opus prompt-free arms —
FINAL_pf_baseline_opus, FINAL_pf_session2_opus, FINAL_pf_rocqmcp_opus —
configs, manifest and arena VERBATIM as executed in A104/A117
(af_pf_{baseline,session2,rocqmcp}_opus; minif2f_test; 244 problems;
parallel 4; 300 s wall; cap-100 rail), model pinned claude-opus-4-8 (a
CLI probe before launch confirms the id still resolves and returns
opus usage). run_eval resumes on (problem_id, rep) pairs, so relaunching
each run-id with --reps 2 executes exactly the 244 missing rep-1
attempts and cannot touch or rewrite a recorded rep-0 row. ORDER:
control -> evolve -> sibling, one sequential chain, as in A117. RAIL:
cap-100 did not bind in rep 0 (max observed turns 7 / 27 / 19 of 100),
so the rail is nominal at this tier; rep 1 keeps it for within-arm
identity rather than adopting the cap-200 used at the weak tier.

(2) WHAT REP 1 CAN AND CANNOT CHANGE, fixed here so it cannot be
renegotiated after data: pass@1 is the rep-0 cell by project
convention, and rep-0 is already recorded and reported for all three
arms. Adding rep 1 therefore CANNOT revise a single reported pass@1
number; it can only ADD pass@2 columns. A117 stays REPORT-ONLY: no
registered contrast attaches to the opus tier, and the existing
post-hoc McNemar numbers (42:9 vs control, 15:10 vs sibling) remain
labeled post hoc, computed on rep-0 pairs, and are NOT recomputed,
re-tested, or supplemented on rep-1 data.

(3) LOOK, amended BEFORE the rep-1 data exists: harness/a117_look.py
now accepts 244 OR 488 rows per arm (mirroring a118_look), reports
pass@2 only when an arm has both reps complete, and excludes a partial
rep-1 tail from analysis with the tail size disclosed in the arm
status. VALIDATED against the archived artifact on the current rep-0-
only data: zero numeric differences in every cell of every arm
(control .611 / evolve .746 / sibling .725 pooled, unchanged), so the
amendment is a pure extension and cannot move a published cell.

(4) BUDGET, recorded before the spend: rep-0 cost was $45.17 / $48.46 /
$62.01 = $155.64 API-equivalent. The rep-1/rep-0 cost ratio measured on
the four arms that already carry both reps is 0.87-1.12 (mean 0.99), and
the A104 checkpoint calibration puts a 244-attempt opus arm at ~8-9% of
a weekly window, so the trio projects to ~30% (range 26-34%) and ~9-10 h
of chain wall clock at parallel 4. NO checkpoint/abort rule attaches
(unlike A104): all three arms are already reported at pass@1, so an
exhausted window costs a pass@2 column and nothing else. Arms whose
rep-1 does not complete simply report as they do today, per (3).

(5) A118 REDOS ride along AHEAD of the opus chain (4 haiku attempts,
<0.1% of the window): the 4 rail-voided rep-0 rows (1 control, 3
sibling) are redone under the A118b cap-200 configs, completing rep-0
for both comparators and unblocking the A118 registered look, which
then runs and is recorded whatever it shows. DISCLOSED: inside those
two arms the retained rows ran under a cap-100 rail and the 4 redone
rows under cap-200. No retained row reaches 100 turns, so the
difference is nominal — the model never sees its budget, so
trajectories are identical up to the cap (A101 reasoning). The haiku
rep-1 completion stays deferred and out of scope here.

(6) OPS: single sequential caffeinated chain on AC power; pgrep clean
before launch; worker sweep before and after; no agent fan-out and no
heavy interactive use while the arms run (A93, ops rule 5).

## A120 — FINDING: the CLI version is an uncontrolled arena variable

Discovered while checking (operator's question) that rep 1 used the same
opus model as rep 0. It did: a sweep of every assistant message and
every modelUsage key in all 1464 opus attempts returns exactly one
proving model, claude-opus-4-8, in both reps of all three arms (the
haiku entries in modelUsage are the CLI's own auxiliary usage, present
symmetrically in both reps). The configs were also verified byte-
identical to each run's recorded config before launch. But the CLI
VERSION was never pinned, recorded as an arena variable, or gated, and
it is not uniform across arms or reps.

CENSUS (claude_code_version from every attempt's init event):
  pf_baseline_opus    rep0 {2.1.209: 201, 2.1.228: 43}  rep1 {2.1.245: 244}
  pf_session2_opus    rep0 {2.1.228: 244}               rep1 {2.1.245: 244}
  pf_rocqmcp_opus     rep0 {2.1.228: 244}               rep1 {2.1.245: 244}
  pf_baseline_sonnet  rep0 {2.1.201: 179, 2.1.209: 65}  rep1 {2.1.201: 45, 2.1.209: 199}
  pf_session2_sonnet  / pf_rocqmcp_sonnet   both reps {2.1.209}
  frozen_wallonly     both reps {2.1.209}
  pf_baseline_haiku   rep0 {2.1.233: 243, +1 @2.1.245}  (the A119 redo)
  pf_rocqmcp_haiku    rep0 {2.1.233: 241, +3 @2.1.245}  (the A119 redos)

EVIDENCE THAT IT MATTERS, from the within-problem paired split of the
opus control arm (every problem compared against itself; difficulty is
therefore controlled, and rep 1 is uniformly 2.1.245 for both subsets):
  rep0 served by 2.1.209 (n=201): 128 -> 85 solved, lost 45 / gained 2,
    kills 36% -> 58%
  rep0 served by 2.1.228 (n= 43):  21 -> 19 solved, lost  2 / gained 0
  evolve  (2.1.228 -> 2.1.245): lost  7 / gained 12   [balanced]
  sibling (2.1.228 -> 2.1.245): lost 14 / gained 10   [balanced]
Ruled out as explanations: model substitution (census above); machine
sleep or long walls (zero rows with the sleep flag or wall > 330 s);
host load (median local tool duration 259 -> 267 ms, unchanged); service
throughput (median 68.5 -> 73.7 output tok/s, if anything faster); a
startup transient (the deficit is spread across the whole arm, not
clustered). The failed rep-1 attempts carry MORE transcript events than
the rep-0 solves of the same problems and sit pinned at the 300 s wall:
the arm is wall-bound, and its measured rate is sensitive to whatever
the surrounding CLI does with the budget. Time is confounded with
version for the 2.1.209 subset (July rows vs August rows, same pinned
model id), so "2.1.209-era environment" is the honest attribution
rather than the version string alone -- but the arm-asymmetry is not
explicable by sampling.

CONSEQUENCES, stated in the direction each one runs:
(1) AGAINST OUR ARM, already published: the opus control pass@1 (.611)
    rests 201/244 on the 2.1.209 era; re-measured today the same arm
    gives .426. The published control anchor is GENEROUS to the control,
    so the reported evolve-vs-control gap at the opus tier is
    conservative. The number stands as registered (rep-0 cell, never
    replaced post hoc); what is added is the disclosure that it is not
    reproducible in the current environment.
(2) FLATTERS OUR ARM, not yet published: opus pass@2 mixes a strong-era
    rep 0 with a weak-era rep 1 in the control only, so control pass@2
    (.619) is depressed while evolve rises to .795. The A119 pass@2
    columns MUST NOT be reported as a clean comparison. Held back
    pending (4).
(3) FLATTERS OUR ARM, registered contrast: A118's haiku evolve arm
    (frozen_wallonly) ran entirely on 2.1.209 while both comparators ran
    on 2.1.233 -- the evolve arm sits on the era that measured strongest
    for a wall-bound arm. The A118 look reported CLEAN (69:0 and 31:3)
    because no gate tests version. The contrast is now IN QUESTION and
    is not to be cited until (4) settles it. Also disclosed: the 4 A119
    redo rows entered those arms at 2.1.245 (too few to move 69:0 or
    31:3, but recorded).
(4) REQUIRED NEXT STEP, to be pre-registered separately before any
    attempt: a version A/B at fixed model on the same problems, using
    the versions still present on disk (2.1.227/228/233/235/236/245;
    2.1.201 and 2.1.209 are NOT installed and may be unrecoverable). The
    haiku tier makes this nearly free and tests exactly the arm shape at
    issue. No number in (2) or (3) is reported until it lands.
GATE CHANGE (applies to every future look): record claude_code_version
per attempt and FAIL any arm that is version-mixed, or any contrast
whose arms ran on different versions, rather than discovering it by
hand afterwards.

## A121 — independent re-verification of every MiniF2F attempt with the sibling's `rocq_verify` (report-only audit)
2026-09-02, registered before the full run; the 120-row pilot below is
the only data seen.

SCOPE. Every attempt row of every run whose manifest is minif2f_test or
minif2f_valid (23 runs, 14 of them FINAL_* held-out arms): 6,535 rows
that left a graded artifact (5,382 solved, 1,153 rejected-with-file);
4,006 rows graded no_candidate are not auditable (nothing existed at
grading) and are counted as skipped. Nothing under logs/runs is modified.

VERIFIER. The mature sibling MCP server's `rocq_verify` tool (rocq-mcp
0.3.1, commit 6983113, the `.venv-eval` binary used in the sibling arms),
called over its real MCP stdio interface by harness/audit_verify.py, on
the same Rocq 9.1.1 switch as the gate. It wraps the proof in a
`Module M.` sandbox, restates the ORIGINAL statement outside it, closes
it with `exact M.<name>`, and audits `Print Assumptions` against its own
standard-axiom allowlist: an independent code base with a different
anti-gaming design (semantic statement match) from our gate (A8 prefix
lock + forbidden tokens + fresh recompile + assumption audit).

FAITHFULNESS RULES (fixed now).
 1. The audited file is the artifact the gate graded: submissions/
    (newest not rejected as recompile_failed, replaying run_eval) else
    work/candidate.v.
 2. Ambient environment (A11): the gate compiles with `-ri` Lia/Lra/
    Psatz; rocq_verify takes no flags, so the equivalent `Require Import`
    line is prepended to the proof text. Pilot check on a row using
    `nra`: without it the sibling rejects a valid proof, with it accepts.
 3. problem_statement = the shipped task prefix; problem_name = the last
    theorem of the prefix (statement_prefix convention).
 4. Every audited row also records (a) the artifact's mtime relative to
    the attempt's end and (b) today's verdict of OUR gate on the same
    file. A row whose file was rewritten after the attempt ended (A93
    class) or whose gate-today verdict differs from the record is
    `artifact_drift`: the graded file is gone, the row is excluded from
    agreement statistics and disclosed by count. Census: 45 FINAL rows
    have post-deadline writes (2 solved, both pf_baseline_sonnet slots
    whose server log spans two days; 43 rejected, mostly no_candidate).
 5. Rows graded no_candidate are skipped.

WHAT IS MEASURED (per run and per arm, by direction).
 A. Solved rows the sibling REJECTS -> `sibling_limitation` (its own
    machinery: Module M, Require-in-module, timeout, allowlist) or
    `unsound_solve` (the candidate does not prove the original
    statement). `unsound_solve` is the only category that can call a
    registered number into question; every such row is listed with its
    evidence and reproduced by hand before it is reported.
 B. Rejected-with-file rows the sibling ACCEPTS -> `gate_stricter`:
    valid proofs of the original statement rejected by the registered
    prefix lock / token rule. Pre-run census (statement text intact
    somewhere in the file, rep 0): sibling arms pf_rocqmcp_sonnet 14,
    rocqmcp_sonnet 11, pf_rocqmcp_opus 1, pf_rocqmcp_haiku 3; controls
    pf_baseline_sonnet 8, baseline_sonnet 5, pf_baseline_opus 0,
    pf_baseline_haiku 10; controls mostly rewrote the statement itself
    (105/118 sonnet, 28/28 opus), sibling arms inserted helper lemmas
    ahead of an intact statement. DIRECTION: the lock's cost lands mainly
    on the sibling arms, i.e. against us on the evolve-vs-sibling
    contrast (sonnet rep-0 upper bound .734 -> .791 vs evolve .820; opus
    .725 -> .730). The task prompt of every pf arm stated the
    character-for-character prefix rule, so the rejections follow the
    registered protocol; the audit reports, per arm, a post hoc
    "semantic-gate" pass@1 alongside the registered cell, clearly
    labelled. No registered cell is replaced.
 C. `artifact_drift` and skipped counts, disclosed.

PILOT (120 rows: 40 each of pf_baseline_sonnet, pf_session2_opus,
pf_rocqmcp_sonnet; logs/audit_verify/smoke/): 109 agree, 0 solved rows
rejected by the sibling, 5 artifact_drift (all wall-killed 2026-07-14
rows whose candidate.v was rewritten 22 s to 25 min after the attempt
ended), 6 gate_stricter (5 sibling-arm helper-lemma insertions, 1
evolve-arm `Unset Printing All.`); every triage verdict survived an
independent skeptic.

TRIAGE PROTOCOL. Six small-model runner shards execute the driver
(harness/audit_verify_chunk.sh); counts are recomputed from the output
files by harness/audit_verify_summary.py, never taken from an agent's
report. Every disagreement is classified by a triage agent from a fixed
dossier (harness/audit_verify_show.py) in batches of <=25 and every
`unsound_solve` / `unclear` / `sibling_limitation` item, plus one in
five of the rest, is independently re-derived by an adversarial skeptic;
the supervisor resolves conflicts from the primary evidence.

WHAT CANNOT CHANGE. No registered cell is edited. If `unsound_solve`
rows exist, the affected cells are reported with the audited count
subtracted in a separate, labelled column and the registered cell
stands with a disclosure.

OPS. No eval runner active; the audit uses coqc only (no API quota);
parallelism 6 shards; AC power; output logs/audit_verify/<run>.jsonl.

### A121 OUTCOME (2026-09-02, full run; numbers from harness/audit_verify_summary.py
### on logs/audit_verify/, triage map logs/audit_verify/triage.json)
COVERAGE. 23 runs, 6,535 rows with a graded artifact audited (5,382
solved, 1,153 rejected-with-file); 4,006 no_candidate rows skipped.
Rows written twice by parallel runner invocations (1,563) were deduped
keeping the first copy; 4 duplicate pairs disagreed, all our gate's 120 s
recompile budget expiring under six-way load on heavy proofs. Every row
carrying that signature (12, all record=solved, sibling=accept) was
re-audited single-process and spliced (logs/audit_verify/redo.log): all
12 resolve to gate solved / sibling accept.
AGREEMENT. 6,385 / 6,535 rows agree (97.7%). Disagreements:
 A. solved rows the sibling REJECTS: 2, both mathd_algebra_144 (rep 0 and
    rep 1) of session_try_hints_v2_minif2f_valid (dev valid split, not a
    held-out arm). Reproduced by hand: the sibling's closing script
    `eapply M.<name>; all: first [eassumption|...]` lets eassumption
    instantiate the evars for a, b, c with d, leaving `d - d = d`,
    `d + d + d = 60`, `d + d > d` open; naming the binders explicitly
    (`exact (M.thm a b c d h0 .. h7)`) closes the shipped statement with
    "Closed under the global context". Category sibling_limitation.
    unsound_solve: 0 rows in any run. No registered cell is touched.
 B. rejected-with-file rows the sibling ACCEPTS: 139, all gate_stricter
    (137 keep the statement text intact: 54 helper declarations inserted
    before the statement, 46 preamble/import edits, 29 `Require` in the
    proof region, 8 printing-option `Unset`; 2 in mstf_base_test restate
    the theorem in a convertible form -- `List.fold_left` for
    `fold_left`; a literal list for `seq 1 49` whose multiples-of-3
    filter coincides, checked by vm_compute). Both verifiers reject all
    11 `Unset Guard Checking` candidates.
 C. artifact_drift: 9, all rep-0 slots of FINAL_pf_baseline_sonnet in the
    A93 window (5 record=prefix_modified vs gate-today=solved, file
    rewritten 22 s to 25 min after the wall kill; 2 record=solved with
    consistent verdicts; 2 rewritten and still rejected). Excluded.
TRIAGE. 146 rows classified by sonnet triage agents from the dossier, 4
drift rows classified mechanically (both verifiers agreed, so the show
script never listed them; A121 rule 4), 37 independent skeptic checks
(all category-A/unclear/limitation items plus a 1-in-5 sample), 0
refuted; 1 supervisor correction (a rep key transcribed as 1 for a rep-0
row; logs/audit_verify/triage_supervisor_fixes.log).
PER-ARM REP-0 SEMANTIC COLUMN (post hoc; registered cell unchanged):
   arm                    registered  +sibling-accepted  semantic
   pf_rocqmcp_sonnet         .734          14              .791
   rocqmcp_sonnet (guided)   .557          11              .602
   pf_rocqmcp_opus           .725           1              .730
   pf_rocqmcp_haiku          .336           3              .348
   pf_session2_sonnet        .820           0              .820
   pf_session2_opus          .746           2              .754
   pf_session_sonnet         .791           0              .791
   session_sonnet (guided)   .779           0              .779
   pf_baseline_sonnet        .496           1              .500
   baseline_sonnet (guided)  .475          11              .520
   pf_baseline_opus          .611           0              .611
   pf_baseline_haiku         .168           7              .197
   frozen_wallonly / minif2f_test / finisher_only_test: +0.
DIRECTION. The prefix lock's cost lands on the sibling sonnet arms and on
the guided sonnet control, not on us: under the semantic gate the sonnet
evolve-vs-sibling rep-0 gap narrows from +.086 to +.029; the opus gap is
unchanged in direction (+.021 registered, +.024 semantic). The pf task
prompt stated the character-for-character prefix rule to every arm, so
the registered rejections follow the protocol; the semantic column is
reported beside the registered cells, labelled post hoc, wherever the
sibling arms are cited. No registered number is replaced.
VERIFIER NOTE (for the sibling maintainers, direction-neutral): the
closing script's `eassumption` can capture the wrong hypothesis when a
binder-style statement has several hypotheses of the same shape (2 of
5,384 solved rows here); 12 of our gate's recompiles hit their 120 s
budget only under 6-way parallel load (single-process: all pass).

## Branch note — entries A122–A125 below describe code on branch `dev` (named `dev-rocq-api` until A128)
2026-09-03. The server refactor that followed the API audit (A122: build
EOF hole; A123: driver package; A124: six integrated packages; A125: fork
probe removed, OCaml constraint tightened) changes the session-server
binary's behaviour on some inputs and plausibly its timings. It lives on
branch `dev` (named `dev-rocq-api` until A128; forked from this branch at
1be821e + the audit report commits). THIS branch (`main`, named
`autoform-experiments` until A128) keeps the frozen server exactly as every
recorded arm ran it, so its numbers and scripts stay in
sync; any evaluation of the refactored server is a new, separately
registered arm. The entries are copied here verbatim so the trail stays
complete on both branches.
2026-09-17 (A149): `main` now carries `dev`'s tooling as well (harness/, configs/,
data/, docs/); src/, test/ and dune-project stay frozen here, so the entries A122–A127
and A133–A134 below still describe code that lives on `dev` only.

## A122 — `build` reported "OK, no holes" on a file whose last proof is never closed (fix, post-freeze server change)
2026-09-03, user-reported during manual testing (scripts/mcp_repl.py on a
benchmark task prefix): `build` answered "BUILD OK: 0 proof block(s), no
holes" for a file ending in a bare `Theorem X : T.`, which `rocq compile`
rejects ("There are pending proofs"). CAUSE: the whole-file walk counted a
block only on Qed/Defined and recorded a hole only on a timeout, parse
error or failing sentence; a statement left open at end of file is none
of those. FIX (src/session_server/rocq_agent_session.ml, build_tool): after
the walk, if the file was consumed to its end and the prover state still
has an open proof, that proof is reported as a hole -- named from the
prover's own lemma stack (new Rocq_driver.open_proof_name:
LemmaStack.get_top + Declare.Proof.get_name), so every proof-opening
command is covered (Theorem/Lemma/Instance/Example/Remark/Definition with
a tactic body) with no text inspection. Skipping past an error to the end
of the file does not count as reaching it, so an error already reported
never gains a second "unfinished proof" entry. An independent review of
the first version of the patch found exactly those two defects (keyword-
gated detection; duplicate hole after a parse error with trailing text);
the runtime-based rewrite closes both, and both shapes are now regression
cases (test/test_session.ml A15, 10 checks; suite A 57 -> 67).
IMPACT ON RECORDED RESULTS: none. `build` was never exposed in any
miniF2F arm (tool sets: step/rollback/state/try/auto_close, or subsets)
and no miniF2F server log contains a build call. The autoformalization
evolve arm exposed it and called it 1,457 times; reconstructing each
built file from the preceding write_file payloads in the same server log,
the 476 "BUILD OK" verdicts split 348 all-proofs-closed / 128 no-theorem
(definitions-only, correctly OK) / 0 open-proof-at-end -- the false OK
never fired; autoformalization is graded independently (autoform_gate:
clean dune build + assumptions) in any case.
FREEZE NOTE: this changes the session-server binary used by the completed
held-out evolve arms. The change is confined to the `build` tool, which
those arms did not expose; no recorded verdict depends on it. Any future
FINAL run (e.g. the A120 version A/B) uses the rebuilt binary; its
registration should cite this entry.
KNOWN, UNCHANGED (review notes): an explicitly `Admitted.`/`Abort.`ed lemma
in the source is neither an OK block nor a hole ("no holes" is then
misleading, though rocq compile accepts the file); an unclosed
Section/Module at EOF is not reported (rocq compile rejects it). Both
predate this entry and are left for a separate change.

## A123 — API audit, driver package: typed errors, Rocq's classifier, AST-level Require policy, prover-side library and tactic queries (post-freeze server change)
2026-09-03. Implements the first tier of docs/ROCQ_API_AUDIT.md in
src/session_server/rocq_driver.ml and rocq_agent_session.ml:
 - exec_sentence classifies the raised exception BEFORE rendering it
   (err_kind: Unknown_ref qualid | Syntax | Other_err; Logic_monad.
   TacticFailure unwrapped; Nametab.GlobalizationError, Pretype_errors
   VarNotFound/EvarNotFound, CLexer/Gramlib errors). Hints and did-you-mean
   suggestions consume the kind; the unresolved qualid (qualified names
   included) replaces a regex capture from the rendered message; an unknown
   TACTIC name (a plain Ltac user error) is recognised through the Ltac name
   table (Tacenv.locate_tactic) instead of a message substring.
 - query / closer / statement sentences are what Vernac_classifier says
   (VtQuery / VtQed / VtStartProof): `Time Search ...` and `Redirect ...`
   queries are no longer committed into the proof script.
 - the ROCQ_ENV_V2 Require refusal is decided on the parsed sentences
   (D.has_require, proof mode tracked through the classifier): the word
   inside a comment or string no longer trips it. Measured arms: the ten
   refusals recorded in the held-out session arms were all real Require
   commands (A122-era census), so no recorded verdict moves.
 - the prefix-cache freshness fingerprint covers exactly the libraries the
   deepest cached state has loaded (Library.loaded_libraries located via
   Loadpath.locate_absolute_library), instead of a depth-4 walk over
   hand-parsed -Q/-R directories that missed the implicit paths and watched
   nothing without a project file; loadpath_dirs comes from
   Loadpath.get_load_paths after init.
 - the mathcomp-bridge preload and the completion-time import reminder ask
   the prover (Library.loaded_libraries for mathcomp; Tacenv visibility of
   the tactics the proof actually uses, in the post-prefix state) instead of
   substring-searching the prefix text. Verified: Reals LOADS micromega
   transitively without importing it, so library loading would have been the
   wrong predicate; `psatz` takes arguments and has no atomic Ltac constant,
   so `nra` (same module) stands in for it.
 - the session executable now links rocq-runtime.plugins.ltac (Tacenv).
Regression cases: test/test_session.ml A16 (9 checks); suite A 67 -> 76,
all four suites green (128). No tool exposed to a completed held-out arm
changes its verdict on the inputs those arms produced (census above); the
rebuilt binary is the one any future FINAL run uses (A122 freeze note).

## A124 — API audit, remaining packages integrated (post-freeze server change)
2026-09-03. Six packages implemented by delegated agents in isolated
worktrees from A123's commit, each built and tested there, each reviewed
adversarially, then integrated one at a time (helpers appended to
rocq_driver.ml, tests spliced) with all four suites run after every step:
 - P3 open/build walk on parsed sentences: the next closer / next
   statement are found by forward parsing with Pvernac.main_entry and
   Rocq's classifier (VtQed / VtStartProof), names from the lemma stack;
   qed_re, the lemma_re statement scans, stmt_re_of are gone (a keyword
   regex remains only as the last-resort name for a block with no executed
   statement step). Review fix applied: the forward scan starts in the
   caller's proof mode.
 - P4 typed Search: the query is parsed with the Search vernacular's own
   grammar entry and interpreted with ComSearch.interp_search_request /
   Search.search into typed hits; counts and truncation are per object;
   the ">" -> "<" query rewrite is removed; suggest_names uses
   Search.interface_search with a Name_Pattern. Review fix applied: parse
   errors keep their own "search syntax error" wording.
 - P6 exemplars on parsed files: D.parse_units (parser + classifier, no
   execution) replaces the regex lemma extraction and the hand-rolled
   comment stripper; names and statements come from the AST. Review fixes
   applied: the closer belongs to the unit's proof text; the target's own
   proof under another name is excluded (statement identity without the
   name, scoped to the task's own file and its build mirrors -- an
   identical statement in a genuinely different file is a legitimate
   exemplar, as the A13x test states).
 - P7 daemon goal identity by Evar.t (Proof.data.goals / Evar.repr) for
   focus ownership, owner attribution and merge; a vanished goal reports
   "gone" instead of matching another goal by printed text. Suite B 35 -> 44.
 - P8 forbidden-token verification on Rocq lexer tokens (CLexer under the
   current keyword state) in the session server; the files server, not
   linked against the runtime, keeps a stripper made symmetric for string
   literals.
 - P9 typed terms: hypothesis delta on the named context (identifier +
   EConstr.eq_constr), R-typed variables by the registered reference for R,
   power terms by EConstr.decompose_app on the pow constant, goal digest
   from a fixed-margin formatter. Review fix applied: only compound bases
   are parenthesised in the synthesised hints.
The A122-era comment stripper is deleted from the session server. Suite A
76 -> 113; all four suites green (174). Left as documented in
docs/ROCQ_API_AUDIT.md: the dune stanza scanner (no runtime API), the
_CoqProject parser, the vm_compute sentence regex, proc.ml and the opt-in
fork probe (external processes), an explicitly Admitted lemma reported as
neither block nor hole, and an unclosed Section/Module at EOF.
Recorded results are untouched: every tool involved was either unexposed
to the held-out arms or, where exposed (step/try/state/auto_close paths
through hints and the Require policy), behaves identically on the inputs
those arms produced (A123 census). The rebuilt binary is the one any
future FINAL run uses.

## A125 — fork probe removed; memprof-limits is the sole in-process hang guard; OCaml constraint tightened (branch dev-rocq-api)
2026-09-03, user question: why keep the A34 fork probe when A35 showed
memprof-limits stops vm_compute / native_compute divergence? Answer
recorded: the probe was opt-in (ROCQ_FORK_PROBE=1), off in every measured
arm, redundant for that class, and its only remaining role was a fallback
for OCaml 5.0-5.2, where statmemprof (which memprof-limits needs) is
missing -- a packaging matter, not a runtime one. CHANGE: fork_probe, its
probe_outcome type and the vm_compute/native_compute sentence regex are
deleted from src/session_server/rocq_driver.ml (the last regex over
sentence text in the driver); exec_text calls exec_sentence directly,
whose memprof-limits token + Control.timeout is the guard. The package
constraint is now `ocaml >= 4.14 & (< 5.0 | >= 5.3)` (dune-project and
the opam file) so a build without statmemprof is refused instead of
silently losing the guard. The subprocess runner (mcp_core/proc.ml) is
unrelated: it bounds OTHER processes (rocq compile in the control arm's
check tool, dune build in verify), which no in-process library can reach.
Regression: test A18 (3 checks) -- a unary-nat vm_compute divergence
returns a structured TIMEOUT within the step budget and the session keeps
answering. Suite A 113 -> 116; all four suites green (177).
BRANCHES: this change and A122-A124 live on `dev-rocq-api`; the
`autoform-experiments` branch keeps the frozen server that every recorded
arm ran (see the branch note preceding A122 there).

## A126 — nine fixes from the campaign note (ROCQ_TOOLS_IMPROVEMENT_PLAN.md v5), branch dev-rocq-api
2026-09-03. The note (verified by its authors against 13b81bd) was
re-checked against the code; nine of its findings are real on both
branches and small enough to fix without any new tool. All done on the
runtime API: every executed sentence now carries Rocq's own class
(exec_step.cls from Vernac_classifier), and the fixes key on it.
 1. build: an explicit `Admitted.` (VtQed (VtKeep VtKeepAxiom)) or `Abort.`
    (VtQed VtDrop) is a hole named after the open proof (lemma stack), never
    "no holes"; the walk's own injected Admitted is not reported twice.
 2. query accounting: "N sentence(s) committed" counts proof sentences
    only; queries (VtQuery) are reported apart as executed, not committed
    (step and check).
 3. focused-zero: when the focused goals are closed but D.n_goals says more
    remain, `try` and the compact renderer say "close the focus with `}`"
    instead of "finish with `Qed.`" -- the literal message of the note's
    worst incident.
 4. proof artifact: committed sentences are split by class; environment
    side effects (VtSideff: Require, Set, Open Scope, Notation ...) executed
    mid-proof are listed as prefix edits to add BEFORE the statement and no
    longer shown inside "the proof script to insert after the statement".
 5. finisher portfolio filtered by tactic visibility (Tacenv): library
    closers (lia/nia/lra/nra/psatz/ring/ring_simplify/field, and the
    ssreflect `by`/`done` forms) are tried only when in scope, which
    retires the dead `by ring.` in the mathcomp regime (the ring bridge is
    not preloaded); the Require-refusal message names the bridges when
    loaded; the A32 comment corrected.
 6. error truncation keeps head AND tail with an explicit
    "[N chars elided]" marker, so the diagnosis at the end of long Rocq
    errors survives.
 7. after a timeout the interrupted sentence's garbage is reclaimed
    (Gc.full_major + Gc.compact, OCaml 5 returns freed pools) and the reply
    states the major-heap size; addresses the note's retained multi-GB
    worker after a timed-out rewrite. Process-global library data is live
    and untouched; a supervisor/worker split remains a design change.
 8. check states how many previously committed sentences it discarded
    (fresh-attempt semantics are unchanged, the wipe is no longer silent).
 9. step names the argument key it received when `text` is missing.
Not done, by decision: the architectural items of the note (restartable
worker and cancellation, RSS/heap caps, bounded snapshot retention with
replay, strict import-faithful verification, structured result envelope).
Regression: test A19 (24 checks); suite A 116 -> 140; all four suites
green (201). Frozen branch untouched (this entry copied there).

## A127 — shared-proof daemon path removed (branch dev-rocq-api)
2026-09-03. The multi-agent daemon (src/psession: daemon, shim and a
July-2 copy of the session driver never updated since, without the A35
memprof guard or anything from A122-A126), its config (team_k3), its
orchestrator (harness/run_team.py) and suite B are removed from this
branch. Grounds: the daemon backed exactly one measured design, intra-proof
parallelism (A12), which lost both times it was measured on dev manifests
(team 13/54 vs solo 36/54 on decomposable; 45/140 vs 56/140 on hard70, at
higher cost); no held-out arm ever ran it; it was the only client of the
duplicated driver. The negative result stays recorded in docs/DESIGN.md
and the code stays on branch autoform-experiments (ec0c104 and later).
Suite C loses its two daemon-load checks (10 -> 8); suites now
A 140 / C 8 / D 7 (155). If a process boundary is wanted later for
recovery, it should wrap the single session server over stdio rather than
revive branch-and-merge semantics that measured badly.

## A128 — branch consolidation: `main` := `autoform-experiments`; `dev-rocq-api` renamed `dev`
2026-09-03. Before this entry `main` (79c163e) was the 2026-07-15 state:
two merge commits (e6f6af6, 942345e) bringing in `autoform-experiments`
plus one commit deleting WAVE2_STATUS.md, and nothing else, while
`autoform-experiments` carried 65 further commits (A103-A127: campaign
completion, the A121 sibling audit, the API-audit reports and the copied
A122-A127 notes). `main` is now moved onto the `autoform-experiments` tip
a532620 with no history rewrite; the three superseded main-only commits
become unreachable, and their only content not already here (the
WAVE2_STATUS.md deletion prescribed by HANDOFF_RUNBOOK.md for the final
merge) is redone in this commit; that file's last state is in history at
a532620. `autoform-experiments` is deleted locally and on the private
remote; `dev-rocq-api` is renamed `dev` and merged with `main` so it sits
strictly above it. Reading rule for earlier entries and docs:
`autoform-experiments` now means `main`, `dev-rocq-api` now means `dev`.
Invariants checked: the tree of `main` outside docs/ and the runbook is
identical to a532620 (src/, harness/, test/, configs/ unchanged, so the
measured server build b951c2d is still what this tree produces); the
public repository tip stays 13b81bd (the phase-1 snapshot of 2026-07-09)
and nothing is pushed there.

## A129 — complete logs published as release assets of the private repository
2026-09-03. The untracked `logs/` tree (8.29 GB on disk; 159,651 regular
files plus 51 dune install symlinks: every run directory under logs/runs/,
logs/autoform/, the chain logs, the look results and the A121 audit
evidence) is archived as 91 zstd-compressed tar files (427.2 MB in total;
one per run directory, one for logs/autoform, one for the top-level files
with logs/archive and logs/audit_verify) and attached to release
`artifact-2026-09-03` of git@github.com:LLM4Rocq/rocq-mcp-evolve-private.git,
whose tag points at this commit. Nothing is excluded: compile artifacts
and micromega caches are kept (the 3.9 GB proof.glob under
mstp_base_dev60/lean_workbook_30055__rep1 is a runaway glob index that
compresses to a few MB); the only file left out is a Finder `.DS_Store`
between run directories. Verified before upload by listing every archive
and comparing with a fresh listing of logs/ (one file only on disk: that
`.DS_Store`; the 51 entries only in archives are the symlinks, which the
file count excludes). docs/LOGS_RELEASE.md lists each archive with its
source directory, file count, raw and compressed sizes;
docs/logs_release.sha256 carries the SHA-256 of every archive so a
downloaded copy is checked with `shasum -a 256 -c`. The manifest is
committed BEFORE the tag so the tagged tree verifies its own assets.
Restoring the archives into logs/ reproduces the tree every script in
harness/ read to produce the registered numbers.

## A130 — PRE-REGISTERED: independent re-verification audit of the autoformalization campaign (report-only)
2026-09-04. Scope: the 29 current-dataset autoform runs under logs/autoform/
(462 attempts: af2_*, af3_*, op_*, orp3_*, mst*, w2_*; smokes, the magistral
probe and the discarded wave-1 af_* runs excluded) — every attempt, solved
or not (181 solved after the A75 regrades). Methods, fixed before any
attempt is re-checked:
(1) Independent checker (harness/audit_autoform.py + an OCaml tool under
src/audit on the Rocq API): fresh sandbox `dune build` of the stored
workspace, probes.v compiled against the built TaskLib theory, and the
assumptions of every probe computed with Assumptions.assumptions and
classified by kind (constant axiom / guard bypass / positivity bypass /
type-in-type / UIP). Accepted = closed, or only the boolp classical trio.
Review flags are recorded but never decide: OCaml libraries or plugins in
the submission's dune files, Declare ML Module, bypass_check attributes,
several coq.theory roots. Toolchain versions recorded per run.
(2) Reference-derived extended probes, data/autoform/<task>/audit/probes_ext.v:
expected values COMPUTED from the gate-validated reference (not
hand-written) on far more instances than probes.v, restricted to the
required names, plus one non-vacuity witness per hypothesised required
theorem; each file must pass on the reference before use (well-posedness
rule). Where computation is unavailable (gauges) the file records what
could be pinned and what could not.
(3) Probe mutation analysis on the references: named mutants (dropped
hypothesis, transposed product, off-by-one, weakened conclusion, degenerate
definition) run through the ORIGINAL gate; a mutant that passes is a probe
gap, listed per task.
(4) Fidelity rating (LLM, the M12 rubric: faithful / weakened / divergent
per required name and per theorem) of the solved attempts the report lists
as unaudited (af3_base2, op_*, orp3_*), plus a blind second rater on a
random 20% of all rated attempts. Ratings are judgments and are reported
apart from the mechanical results.
(5) Protocol checks: no transcript reads a reference/ path; the eight A75
regrades belong to the trigger class and pass the fixed gate; results.jsonl
equals verdict.json for every run.
Outcome categories, direction-blind: agree; gate_unsound (solved, fails the
strict checker); gate_stricter (failed originally, passes the strict
checker); ext_mismatch (passes probes.v, fails probes_ext.v); vacuous (a
required hypothesis unsatisfiable under the submission's definitions);
toolchain (build outcome differs for environment reasons; listed, not
counted). Reported per arm beside the registered numbers, never replacing
them, as A121 did. Evidence: logs/audit_autoform/ (tracked). Code lives on
dev only; main receives this entry, the outcome entry and the evidence.
Known before launch: the gate's assumption parser recognises only
`name : type` lines, so a `#[bypass_check(guard)]` definition would pass
it (verified on a toy file; `rocq check` accepts the .vo as well); a scan of
all 211 solved workspaces found no bypass attribute or flag command.

## A131 — A130 outcome: the autoformalization campaign re-verified (report-only)
2026-09-04. Sweep of all 462 in-scope attempts (29 runs) with the A130
tooling (dev f9b4acb): fresh sandbox build, probes.v, assumptions through
the Rocq API, reference-derived extended probes where the task has them
(all five; gauges by lemma-proved instances since realType arithmetic does
not compute). 6,064 s at 4 workers. Evidence: logs/audit_autoform/
(attempts.jsonl, summary.json/md, protocol.json/md, mutants/, sweep.log).
Categories (direction-blind, A130): agree 455; gate_unsound 0;
gate_stricter 2; ext_mismatch 4; toolchain 1 (listed, not counted).
- gate_unsound 0: no gate-solved attempt fails the strict checker. No
  bypass attribute anywhere. Six terra triadic attempts (orp3_base rep1/2,
  orp3_evolve rep0/1/2, orp3_sota rep2) wrote `Unset Guard Checking` around
  a required theorem; the gate rejected them on the token and the strict
  checker rejects them on the `guarded` assumption kind, so both agree.
- gate_stricter 2 (af2_evolve/ledger rep1: `Abort`; af3_evolve/ledger rep3:
  `Admitted`; both in a delivered theories/Scratch.v that no probe depends
  on; the probes' assumptions are closed). The registered rule bans those
  tokens in delivered files, so these rows are credited only on the
  semantic column, and a rule-strict variant leaves them out.
- ext_mismatch 4, all gpt-5.6-terra, all verified by reading the sources:
  orp3_base/triadic rep0 and rep3, orp3_evolve/triadic rep3 define
  Step.tstep by cases on the probe inputs (12, 15, 27, 30; e.g. `if n == 12
  then 13 else if n == 30 then 31 else if odd n then (if n == 15 then 9 else
  if n == 27 then 13 else n.-1) else if 6 %| n then n else sumn (triad n)`)
  and return junk elsewhere; both required theorems hold of such a function.
  orp3_evolve/prodauto rep0 defines `Pump.trace A w := [:: start; start]`,
  a constant two-element list, so `accepts_long_dup` (~~ uniq (trace A w))
  is trivially true; the spec says trace is "the states visited, start
  included". First divergence from the reference: tstep 3 = 2 instead of 1;
  size (trace parity w) = 2 for every w instead of size w + 1.
  These are the only three triadic solves and the only terra prodauto
  solve ever recorded.
- toolchain 1: af3_base/ledger rep1 (wall-killed, never graded, results
  row build_failed) times out the 1800 s sandbox build today; excluded.
- Extended probes ran on 211 attempts whose probes.v compiled: 207 pass,
  4 fail (above). Every solved attempt of every Claude and Mistral arm
  passes them.
- Protocol (method 5): no transcript read a reference path; results.jsonl
  equals verdict.json in all 29 runs (one attempt without verdict, killed
  at the wall); all eight A75 regrades are in the trigger class and pass
  the fixed gate today.
- Mutation analysis (method 3): 16 genuine probe gaps (frugal 5, gauges 2,
  ledger 2, prodauto 4, triadic 3), each with a checked killing probe that
  passes on the reference and fails on the mutant
  (logs/audit_autoform/mutants/<task>/README.md). They are benchmark
  revision material; probes.v is not changed for any recorded arm.
SEMANTIC COLUMN (post hoc; strict checker AND extended probes; the
registered gate numbers are never replaced): per arm, registered -> semantic
(rule-strict variant in brackets when different):
af2_base 11->11; af2_evolve 7->8 [7]; af2_sota 2->2; af3_base 10->10;
af3_base2 12->12; af3_evolve 14->15 [14]; af3_evolve_c3 14->14;
af3_evolve_r1 15->15; af3_evolve_r3 15->15; af3_sota 12->12; op_base 3->3;
op_evolve 6->6; op_sota 6->6; all mst*/mst3* 0->0; orp3_base 10->8;
orp3_evolve 12->10; orp3_sota 7->7; w2_* unchanged. Per task the only
moves are terra triadic (3->0) and terra prodauto (1->0) and the two
Scratch.v credits on ledger. Readings: the sonnet arena ordering and the
+4 evolve margin stand (evolve 14-15 vs control 10, sibling 12); the terra
ordering stands with a smaller spread (evolve 10, control 8, sibling 7);
triadic is unsolved by every arm, tier and family (0/82 all-time); prodauto
at terra is unsolved. Two typed cells found while regenerating tables are
recorded outside this repository, not here. Code stays on dev; main
receives A130, this entry and logs/audit_autoform/.

## A132 — final_tables.py repaired (branch dev); a second typed cell caught
2026-09-06. The held-out table generator had been stale since A119 gave the
opus arms a second rep: its ARMS list expected 244 rows and named the
superseded FINAL_pf_session_opus, so the integrity gate refused to emit
(LINEAGE_AUDIT finding). Repair, on dev only: ARMS names
FINAL_pf_session2_opus; opus arms declare 488 file rows with report_rep=0 —
rep-0-only statistics and pass@2 withheld, the A120 rule; latency is stored
unrounded so the printed cell rounds once (80.52 -> 81, not the old
round-twice 80.5 -> 80). Output verified against the registered cells:
every §-3-reported pass@1/pass@2/cost/latency cell reproduces, EXCEPT that
the regenerated table shows sonnet evolve (A108) medium pass@2 = 62/79 =
.785 -> .78 where the registered summary carried .79 — the same slip class
as the opus control easy .79 (both are the two cells LINEAGE_AUDIT lists
for the case-study section). The .78 is the correct value; corrected in the
external results summary with a dated revision note. No registered
direction or decision changes (the pooled pass@2 and the A108 contrasts
never used that cell). The frozen main branch keeps the stale script; this
entry records the divergence.

## A133 — `verify` de-duplicated across the session server and the files sidecar (branch dev)
2026-09-07. The two `verify` tools (src/session_server/rocq_agent_session.ml
and src/files_server/rocq_agent_files.ml) carried the same project walk,
the same `dune build --root .` call and the same verdict rendering, and the
sidecar's `dune_build` tool repeated the A40 flock a third time. One shared
module, src/mcp_core/project_verify.ml, now holds the forbidden vocabulary
(also the source of rocq_driver.ml's `forbidden_tokens`), the .v walk
(`_build` and dot-entries skipped, depth cap 6 for both servers, entries
sorted so reports are deterministic), the build (flock optional, released
under Fun.protect), the issue format `path:line: \`label\`` with the
root-relative path, and the verdict (a timed-out build is now named as
such). The session server's UTF-8-safe middle truncation moved to
src/mcp_core/text.ml; the sidecar's `dune_build` output uses it instead of a
head cut. Each server keeps only its tool description, its scanner and its
two verdict strings, which are unchanged ("fix before finishing" /
"Safe to reply DONE"). The scanner split recorded in A124 P8 stands: the
session server lexes with Rocq's lexer; the sidecar, not linked against the
runtime, keeps its hand-rolled string-aware stripper, which now preserves
every stripped newline so it reports the line of every hit like the session
server does (before: one `forbidden token` line per label per file, no line
number, first hit only). Regression added to P8: a nested theories/lines.v
whose `Admitted.` follows a multi-line comment is reported by both servers
as `theories/lines.v:6` and never at the comment's line. Suite A 140 -> 146
(A 146 / C 8 / D 7, 161), all green after a rebuild. Not measured, and the
frozen main branch is untouched: `mcp__files__verify` and
`mcp__rocq__verify` were exposed only to the autoformalization arms (af2/af3
configs), which are complete and re-verified (A131), and the harness does
not parse the tool's text. Implementation delegated to a sonnet agent under
a written spec and reviewed line by line; the suite was rerun independently.

## A134 — second Rocq-API pass over the session server (branch dev)
2026-09-07. A sweep of src/session_server/ for the ad-hoc text handling
the A122-A124 passes left behind (regexes, hand parsers, printed-text
inspection), each replaced by the runtime API where one exists; the
table in docs/ROCQ_API_AUDIT.md ("Status (2026-09-07)") lists the
thirteen sites. Highlights: one-line rendering by an oversized-margin
Format print instead of a space-collapsing regex; a shared lexer walk
(CLexer under the live keyword state) behind import_echo, closer_available,
the search head check and exemplar tokens, so a tactic name in a comment or
a string literal no longer counts; statement names from the AST for every
proof opener build's fallback can meet (Definition/Fixpoint/Instance
included); exemplar leak-proofing by structural signature equality
(Constrexpr_ops) instead of a name-stripped text compare; nat exponents
walked as S/O applications; `_CoqProject` read by CoqProject_file (the
`rocq makefile` reader) and dune stanzas by a real s-expression read that
registers every theory stanza (the audit's known first-stanza limitation);
the stray terminator after a failing sentence skipped on lexer tokens so a
comment before the `.` no longer derails open's admit-and-continue walk;
an unclosed Section/Module at end of file reported as a build hole (Lib
section/module state). Left, with reasons, in the same status section
(Name_Pattern takes a Str.regexp; hint tables run on possibly non-Rocq
agent text; four UserError messages have no typed constructor). Regression
cases A20-A25 (a20 import echo on comment vs real use; a21 search head
token; a22 build fallback name from the AST; a23 dune and _CoqProject
discovery from the task file with no ROCQ_INIT_ARGS; a24 unclosed
Section/Module; a25 stray terminator behind a comment). Suite A 146 ->
165 (A 165 / C 8 / D 7, 180), all green after an independent rebuild.
Not measured; main untouched; no held-out arm exposed the changed paths
beyond what A123's census already covered (step/try/state/auto_close: the
closer availability check is stricter only in requiring every library
tactic in a candidate to be in scope, which the portfolio's candidates
already satisfied whenever their head did). Implementation delegated to
two sonnet agents under written specs, reviewed line by line against the
installed .mli files; the suite was rerun independently.

## A135 — results-summary generator moved into harness/ (branch dev)
2026-09-08. harness/results_all_gen.py regenerates the unified results
summary (RESULTS_ALL.md, maintained outside this repository next to the
table JSONs its own scripts produce) from logs/runs/*/results.jsonl,
logs/audit_autoform/summary.json, harness/autoform_dashboard.py and those
JSONs. It used to live beside the summary; the summary's directory and the
tables directory are now positional arguments (--audit-rows and --exp-root
override the eleventh table and the repo root), and the prose cites the
tables directory by its path relative to the summary, computed at run
time, so the tracked file names no external location. Moving it changed
the generated document by one reworded phrase (section 2, replay
technique) plus a dated revision paragraph; every cell is unchanged and
`--check` reports IDENTICAL against the regenerated file.

## A136 — token efficiency column in the results summary (branch dev)
2026-09-08. The evolve campaign minimized three objectives per solved proof
(dollars, wall seconds, model output tokens; harness/dashboard.py "Cost and
time", docs/DESIGN.md), but the dev60, miniF2F and autoform tables of the
external results summary carried only the first two. harness/results_all_gen.py
now adds `Mtok/solve` after `$/solve` in those three tables: total tokens of
all attempts (failures included) per solved attempt, in millions, where a
token is every prompt token the model processed (cache reads and writes
included) plus every output token (reasoning included); same population,
reps, censoring and solved denominator as the `$/solve` cell of the row,
computed inside the same functions. Why total rather than the campaign's
output-only objective: a wall-killed Claude-CLI attempt leaves no final
usage record, and its per-message transcript events carry first-chunk
output counts only, so output tokens are unrecoverable for killed attempts
(about half the attempts of the miniF2F control arms); input tokens summed
over the deduplicated per-message events are exact (identical to the
recorded totals on 405/405 completed sonnet evolve attempts, and on the
generator's own 300-row check every regeneration). Sources: recorded usage
for completed Claude-CLI attempts, transcript sums for killed ones (output
a lower bound, disclosed in the section notes with the measured output
share: 0.8-26.6 % of total tokens on completed miniF2F attempts, highest
opus control; 0.9-6.8 % autoform); Mistral per-call transcript usage; OpenRouter recorded totals;
the section-2 cap-30 rows truncated at the first 30 model calls of each
transcript (script-derived, unlike the archived cost and wall of those
rows). Three sonnet control transcripts contain NUL-byte corruption (two of
them killed attempts): their sums are partial, effect below the cell's
rounding. Reading note: cache reads count at full weight, so the column
moves differently from `$/solve` — the session interface re-reads a long
cached context every turn, which is cheap in dollars but not in tokens;
where the evolve arm wins on `$/solve` it does not necessarily win on
`Mtok/solve` (opus miniF2F: control 0.03/0.04/0.06 vs evolve
0.06/0.17/0.22). No pre-existing cell changed (verified line by line
against the previous document); `--check` IDENTICAL after `--write`.

## A137 — results summary regenerates from this repository alone (branch dev)
2026-09-08. Until today harness/results_all_gen.py (A135) read nine table
JSONs from the directory beside the summary's former home. Those tables
are now archived under docs/results_tables/ (thirteen files: the nine the
generator loads, the two the prose cites, and the two fixed inputs the
producers read; byte-identical copies, one reworded `note` field, no value
changed) with a provenance README, and their producers under
harness/results_tables/ (nine scripts, experiment root defaulting to this
repo, `--out-dir` for regeneration elsewhere). Reproducibility check, every
producer run against today's logs into a scratch directory: seven tables
regenerate IDENTICAL (dev60_cap30, a113_rows, a115_rows, autoform_arms,
finisher_partition, heldout_cost_recovered, audit_verify_rows); two are
registration-day outputs of scripts that live in this repo and have since
been extended, so today's runs emit supersets in a different shape while
every shared cell is identical (final_heldout_table.json from
harness/final_tables.py, which A132 taught to add the opus arms and keep
latency unrounded; a117_look_result.json from harness/a117_look.py, which
A119 taught to read the second opus rep -- the summary reports opus at
rep 0, A120, which is exactly the archived file; nothing in the logs is
missing); paired_tests.json's producer prints and does not write (its
archive step lived in a script not ported; recorded, not guessed);
rail_census, bucket_manifest and audit_subset are fixed inputs with no
producer here. The generator's defaults are now docs/results_tables and
docs/RESULTS_ALL.md, so `python3 harness/results_all_gen.py --write`
regenerates the summary with no argument and no external path; explicit
paths still work. docs/RESULTS_ALL.md is table-line identical to the
previously maintained copy; the only text differences are the cited
table paths and a dated revision paragraph. Nothing outside this
repository was modified. Superseded the same day by A138: no archived
tables remain.

## A138 — results summary from the campaign logs and scripts alone (branch dev)
2026-09-08. User requirement: the artifact is the logs plus the scripts,
with no archived table files and no hand-typed cells. Done: docs/results_tables/
is removed (and ignored as scratch); every module under
harness/results_tables/ exposes build(exp_root) computing its table in
memory from logs/, and harness/results_all_gen.py calls them (each once,
cached) — `python3 harness/results_all_gen.py --write` regenerates
docs/RESULTS_ALL.md with no argument, in about three seconds. New modules:
heldout_table (harness/final_tables.py factored into build_table(), the
integrity gates unchanged, refusal surfaced as an exception), opus_look
(harness/a117_look.py's own functions on rep-0 rows, which reproduce the
registration-day kill percentages), paired_tests_pooled (the pooled
exact-binomial McNemar families with Holm, ported; the expert-audited
subset restrictions, which need data outside this repo, are not), rail_census
(cap termination = num_turns == max_turns from the run's run_meta.json),
cap30_truncation (below); audit_verify_rows derives its bucket assignment
from the arms' own results.jsonl instead of a fixed file. The ARCHIVE dict is
gone: the six cap-30-censored $/solve and six wall cells of the section-2
mistral and terra rows are computed per attempt from the transcripts — an
attempt within the cap keeps its recorded cost and wall; past the cap, cost
is the sum of the first thirty model calls (terra: the charged usage.cost
per call; mistral: prompt and completion tokens at harness/mistral_driver.py's
rate table) and wall runs from the transcript's first event to the END of
turn thirty, i.e. the tool result following the thirtieth reply (a turn
ends when its tool result is back, the same reading the recorded wall_s of
an attempt stopping at the cap has). Under that boundary all twelve cells
reproduce the previously typed values; the model-reply boundary would move
one cell (mistral control medium wall 206 -> 205, raw 205.49 vs 205.54 s)
— checked independently before the definition was fixed. Prose counts that
were literals (72/488 rail-bound mistral evolve attempts; autoform kills
10/10/7, 7/5/4, 0; cap-30 losses 0/4/1 and 9 of 116; censored terra pooled
.90/.89/.89) are rendered from the same computations and equal the former
literals. Verification: every table line of docs/RESULTS_ALL.md identical
to the version generated from the archived tables (itself table-identical
to the copy maintained beside the write-up); each build() equal to its
former JSON where one existed; `--check` IDENTICAL; wording scan clean.

## A139 — token column reports the campaign objective: output tokens over solved attempts (branch dev)
2026-09-09. The A136 column (`Mtok/solve`, total tokens of all attempts per
solved attempt) counted every prompt token at full weight, so on the
session arms it mostly measured the cached context re-read every turn --
volume the campaign never optimized and dollars barely charge for -- and it
ranked the evolve arms below their controls at opus and sonnet while the
campaign's own objective (harness/dashboard.py "Cost and time": model
output tokens per solved proof) says the opposite. User request: report
output tokens over solved attempts. The column is now `out ktok (solved)`:
mean output tokens over the row's solved attempts, in thousands, the same
population convention as `wall` (mean seconds over solved attempts) and the
campaign's own solved_tokens_out_mean (harness/report.py); reasoning
tokens included; bold = lowest in the model group. Exactness: a solved
attempt has a final usage record unless it was wall-killed after solving;
those are excluded from the mean and counted in each section's note
(dev60: fable control 1; miniF2F: opus evolve 4, haiku evolve 1, opus
sibling 1 -- opus at rep 0 per A120; autoform: sonnet sibling 2, sonnet
evolve 1, opus sibling 1; 12 of 2,893 solved Claude attempts on dev60 and
miniF2F over all reps). Mistral and OpenRouter attempts are exact from
per-call usage; the section-2 cap-30 rows need no truncation because their
solved set is within the cap. Result: the evolve arm has the lowest
solved-attempt output in every bucket at haiku, sonnet and opus on both
dev60 and miniF2F (miniF2F sonnet control 6.6/14.9/15.0 vs evolve
2.7/8.8/10.7; opus 5.5/10.6/15.6 vs 3.1/8.4/13.6), and on autoform for
sonnet, opus and terra. Verification: nine rows recomputed independently
from raw results.jsonl and transcripts before the change was reviewed, all
equal; every other cell of docs/RESULTS_ALL.md byte-identical (106 table
lines, 40 changed in exactly the token cell); `--check` IDENTICAL; wording
scan clean. The A136 total-token figure is not kept; its definition and
the killed-attempt output lower bound it needed are recorded there.

## A140 — §3c: miniF2F efficiency on the problems every arm solved (branch dev)
2026-09-09. User request. docs/RESULTS_ALL.md gains subsection 3c (post
hoc, descriptive): for each miniF2F family, cost, wall and output tokens
per arm restricted to the (problem, rep) pairs that control, sibling and
evolve ALL solved — both reps for sonnet, mistral and terra, rep 0 for opus
(A120) — so the efficiency comparison is on identical work rather than on
each arm's own solved set. Pairs where any arm's solved attempt was
wall-killed are dropped and counted (opus: one, imo_1977_p6 rep 0). Sets:
sonnet 172/49/11, opus 96/30/9, mistral 21/3/0 (no hard problem is solved
by all three), terra 180/58/19. Computed by
harness/results_tables/common_solved.py. Reading: on identical problems the
evolve arm is the cheapest, fastest and shortest arm in every cell for
sonnet and terra, and for opus in every cell but the hard-bucket wall
(sibling 143 s vs 147 s); e.g. sonnet easy $0.19 / 75 s / 6.4 ktok
(control) -> $0.08 / 21 s / 1.1 ktok (evolve). Verified by an independent
recomputation of all four families from the raw logs before review (all
cells equal); no pre-existing line of the document changed; `--check`
IDENTICAL; wording scan clean. Not a registered contrast.

## A141 — section 1 of the results summary is a computed development ledger (branch dev)
2026-09-09. User decision ("the honest version"): section 1 of
docs/RESULTS_ALL.md, until now decision-time prose with typed numbers, is a
table computed from the logs by harness/results_tables/ledger.py: one row
per development run under the campaign convention of section 2 (pass@1 =
solved attempts / attempts over all reps; pass@2 = either of the first two
reps; $/att and wall per attempt, failures included; out ktok over solved
attempts; reps, manifest and turn cap from run_meta.json). Four blocks:
the haiku dev60 ladder (baseline, session, try, compact, search, hints,
auto_close, did-you-mean, draft-first, the auto_close fix, synthesis,
universal at cap 50 and its cap-30 re-run); the confirmation runs on other
development data (try on dev150; the hints configuration on the miniF2F
valid split before and under environment v2, which is where v2's evidence
comes from); the team pattern (solo vs three-agent team on hard70 and on
the decomposable manifest); the policy-neutrality selection (sonnet and
fable dev60 runs). The autoform-arc paragraph becomes a rendered list of
every autoformalization development run that is not a current arm, from
autoform_arms.build. Bucket definitions added to the conventions: the
workbook sets use the translation's own labels (terciles of the Lean
statement's length and symbol count, a statement-shape proxy; medium and
hard barely separate in solve rate), the miniF2F splits use competition
tier (A9). Labels: the sonnet draft-first run is "superseded by universal
(A24)", not reverted — its dev60 numbers (.84 pooled) are not below the
winner tool set's (.82); the haiku draft-first run is reverted on its own
numbers (.27 vs .55). Recomputation reproduces the decision-time figures
(dev150 .45/.33/.35; team hard70 .32 vs solo .40; four rows recomputed
independently before review). Sections 2-7 byte-identical; `--check`
IDENTICAL; wording scan clean.

## A142 — PRE-REGISTERED: pinned-environment rerun of the opus control arm (branch dev)
2026-09-16, written before launch. Context: A120 found the registered opus
control (FINAL_pf_baseline_opus) era-mixed inside rep 0 -- 201 rows on CLI
2.1.209 (2026-07-16) plus 43 on 2.1.228 (08-16) -- while the opus sibling
and evolve arms ran rep 0 on 2.1.228 (08-16/17) and all three arms ran rep 1
on 2.1.245 (08-29/30). Audits of 2026-09-16 (trail-external, recorded in
this entry): (i) every held-out Claude cell except the control's 201 July
rows resolves to effort xhigh -- RECORDED on the opus rep-1 session files
(156/224/226 of 244 attempts, the rest killed before any assistant turn),
inferred for sonnet (outside the CLI's launch-pin family; settings
effortLevel xhigh attested 07-01 and 09-16) -- and haiku takes no effort
parameter in any build; (ii) the July control rows are the only cell
whose effort is unverifiable (the CLI's 30-day transcript cleanup removed
every session file older than 2026-08-17; the surviving 1,273 attempt
session files are archived under logs/cli_sessions_backup/), and they show
half the first-turn thinking of every later opus row (median 8.5k vs
19.7k tokens), consistent with a still-pinned launch effort ("high") at
the time; (iii) across every adjacent-version pair in the logs the CLI
build itself shows no effect (sonnet control 2.1.201/2.1.209 within four
days: 73 vs 71 solved within problem; opus evolve/sibling 2.1.228 ->
2.1.245: +5/-4; dev60 2.1.198..2.1.201: none); the opus-4-8 catalog entry
and the launch-pin code are identical in 2.1.209 and 2.1.228.
DESIGN. One new arm, FINAL_pf_baseline_opus_r245: config
configs/af_pf_baseline_opus_r245.json = the registered af_pf_baseline_opus
byte-for-byte (baseline server, mcp__rocq__check only, claude-opus-4-8,
max_turns 100, wall 300 s, prompt-free) plus "cli_version": "2.1.245" and
"effort": "xhigh"; CLI pinned to the 2.1.245 build installed from the
registry at ~/.local/share/claude-pinned/2.1.245/claude (the default
~/.local/bin/claude, 2.1.273, untouched; DISABLE_AUTOUPDATER=1); one rep
(244 attempts) on minif2f_test, parallel 4. Runner changes (harness/
run_eval.py, harness/version_gate.py, "A142 (CLI era gate)" comments):
--effort passed explicitly; the run refuses to start unless CLAUDE_BIN
reports the pinned version; every attempt records claude_code_version,
session_id, effort_requested and effort_recorded (read from the CLI's own
session file, which is copied into the attempt dir as cli_session.jsonl so
the 30-day cleanup cannot remove it); run_meta records the binary's real
path and version; a version census is written at the end and a mixed arm
is flagged; version_gate.py fails a mixed run or a cross-version pair.
Rows written from this change on carry the four provenance keys; older
rows do not (they are censused from their transcripts' init events).
Server binary: the baseline server's source is unchanged since 0cec6b6
(2026-07-03); the rebuilt binary links two mcp_core modules added since
the frozen artifact (A133) that it does not use -- same source, not
byte-identical. Smoke test passed on dev data (run _smoke_opus_r245: one
attempt, version 2.1.245, effort_requested xhigh, effort_recorded [xhigh],
session file archived).
ANALYSIS, fixed now. Cells: pass@1 e/m/h and pooled, cost, wall, output
tokens, kill rate, under the section-3 conventions. Comparisons: (a)
within problem against the retained rep 1 of FINAL_pf_baseline_opus
(2.1.245, xhigh recorded, 08-29): agreement within sampling noise means
the September environment is the August one and the new cell is
comparable with the retained opus sibling/evolve cells; (b) within problem
against the registered rep 0 (.611): the size of the July-era premium.
Reporting: the registered .611 stays as registered and is never replaced;
the new cell is reported beside it as the version-matched opus control
(rep 0 = this run), which restores the opus evolve-vs-control contrast,
section 3c and the opus paired test on one era; opus pass@2 is reported
only if computed within the new family (this rep with the retained rep 1
would be two reps of the same regime, and is reported as such, labelled).
Direction of any change is known in advance from the paired evidence: the
control is expected to land near .43, i.e. the registered gap was
conservative. Sonnet and haiku arms are not rerun (sonnet: one regime on
both reps; haiku: no effort parameter; the haiku held-out family stays
withheld per A120 unless a separate registration reruns it).
PRECONDITIONS at launch: `pgrep -f run_eval.py` empty (A93); laptop on
AC; no other Claude usage on this account while it runs (including
interactive sessions -- quota poisoning, ops rule 5); the exact command:
nohup caffeinate -dims sh -c 'CLAUDE_BIN=/Users/gbaudart/.local/share/claude-pinned/2.1.245/claude DISABLE_AUTOUPDATER=1 ROCQ_FINAL_EVAL=1 python3 -u harness/run_eval.py --config configs/af_pf_baseline_opus_r245.json --manifest minif2f_test --reps 1 --parallel 4 --run-id FINAL_pf_baseline_opus_r245' > logs/FINAL_pf_baseline_opus_r245.log 2>&1 &
After completion: check for quota poisoning (ops rule 2), run
`python3 harness/version_gate.py FINAL_pf_baseline_opus_r245`, then the
outcome entry.
A142 AMENDMENT (2026-09-16, still before launch; supersedes clause (ii)
above). A diff of the native builds 2.1.209 (July era) and 2.1.228
(August era) for the harness's exact configuration (opus-4-8, `claude -p`,
no --system-prompt, no effort flag) finds nothing material: both emit the
same lean system prompt (differences are punctuation, two informational
environment lines, one added Bash-tool bullet and Agent-tool wording), the
same thinking configuration (adaptive, no budget, same beta headers, same
max_tokens), the same print-mode loop limits, MCP timeouts, retry and
backoff policy, and the same effort resolution order; the opus-4-8 catalog
entry is identical (default effort "high", same capabilities) apart from
added cost metadata. The launch-pin hypothesis of clause (ii) is REFUTED
on primary sources: the pins are released by the interactive /effort
command, which the operator's session ran on 2026-07-01, 07-02, 07-03 and
07-14 (builds 2.1.198/199/201, which write the flags unconditionally);
~/.claude.json was created 2025-06-23 and never recreated (numStartups
143), and no code path re-pins; settings.json read effortLevel "xhigh" on
2026-07-01 and reads it today. The July opus control rows therefore ran at
effort xhigh -- the same value as every other effort-capable cell -- and
the July->August doubling of first-turn thinking at fixed effort, fixed
build, fixed prompt and fixed tools (init events show mcp__rocq__check
only in all 488 attempts) is not explained by anything the client
controls. What remains: server-side behaviour of claude-opus-4-8 at fixed
effort between 2026-07-16 and 2026-08-16 (the model id is unversioned;
haiku's is a dated snapshot), remotely delivered configuration applied by
date rather than build, or account-level effort caps. None is observable
from the client. Consequences for this registration: the design is
unchanged (the rerun measures the control under the current server-side
regime with the build and effort pinned and recorded, and the comparison
against the retained rep 1 tests whether that regime is still the
August one); the reporting term is "cross-era", meaning a server-side
change, not a CLI or effort change; the earlier idea of a high-vs-xhigh
test is dropped as moot. The changelog reader of the audit failed
(output limit) and was not needed for the conclusion.

A142 PUBLIC-SOURCE CHECK (2026-09-16, after the amendment, still before
launch). Whether the server side changed between the eras was checked
against the public record. (1) Anthropic's model-versioning page
(docs.claude.com, "Model IDs and versions", fetched 2026-09-16) states
that every model id, dateless ids included, is a pinned snapshot and that
the weights or configuration of an existing id are never updated; the
same page states that the serving infrastructure around a model (request
router, safety classifiers, sampling logic) changes over time, that such
updates can produce observable behaviour differences, and that "if you
notice unexpected behavioral differences on a previously stable model ID,
an infrastructure update is the most likely cause". That is the
documented form of the residual named in the amendment. (2) The API
release notes for 2026-07-10..08-31 carry no entry for claude-opus-4-8.
(3) Claude Opus 5 was released on 2026-07-24, inside the 2026-07-16..
08-16 gap in which no Claude-driven attempt ran: the one dated public
event touching the Opus serving tier in the window. (4) The status feed
retains nothing before 2026-08-14; the late-August rows overlap "degraded
performance" notices for Opus 5 (08-17/18/19, elevated error rates; not
opus-4-8). (5) The Claude Code changelog for builds 2.1.210..2.1.228
(fetched at tag v2.1.228; the binary diff above cannot see
behaviour-only fixes) has no change to thinking, effort defaults or
print-mode request shaping for opus-4-8. Entries touching the harness
path: 2.1.212 session transcripts record the effort level per assistant
message (why the recorded-effort field exists only from August); 2.1.212
MCP calls longer than 2 minutes are backgrounded (the check tool is
capped at 60 s, never reached); 2.1.219 Opus 5 becomes the default Opus
model (the harness pins its model explicitly); 2.1.221 fix for
--mcp-config servers not being connected before the first turn in print
mode, "which made the model emit tool calls as literal text". That last
item is a July-era client defect with a transcript signature, so all
6,473 FINAL transcripts were censused for it: an assistant text block
containing a literal <function_calls>/<invoke> element in an attempt with
zero tool_use blocks. It occurs in exactly 4 attempts, all in
FINAL_minif2f_test (haiku evolve, build 2.1.199, 2026-07-03
15:34-15:35, rep 1, problems amc12a_2021_p12/p14/p18/p19), all recorded
as non-solves; zero occurrences on every other build, including the
2.1.209 July opus and sonnet control rows. Its direction is against the
July side (it can only remove solves from July cells) and its magnitude
is at most 4/488 on one haiku cell; it does not touch the opus control
contrast. Conclusion: the public record documents that behaviour on a
fixed model id can change through serving infrastructure, without
notice, and supplies one dated event inside the gap; it does not identify
the change and cannot confirm it. Design and analysis plan unchanged.

## A143 — PRE-REGISTERED: regime probe of the opus control on 60 July problems (branch dev)

Registered 2026-09-16 before launch. Question (user): does the opus
control, run today, behave like its July rows or like its August rows?
If July-like, the August regime (2026-08-16..29) was the transient state
and the whole August opus block ran inside it; if August-like, the July
rep 0 is the outlier era, as the A142 amendment assumes. Either way the
probe decides which cells the coherent matrix needs rerun; that decision
is deferred until the probe is scored.

Design. Subset: 60 of the 201 July problems of FINAL_pf_baseline_opus,
built from the within-problem July/August outcome strata (rep 0 on build
2.1.209 vs rep 1): all 45 "july_only" (solved in July, lost in August),
both "aug_only", plus 7 "both" and 6 "neither" drawn with
random.Random(142).sample from each stratum sorted by problem id.
Manifest data/manifests/minif2f_test_opus_probe60.jsonl (records copied
verbatim from minif2f_test.jsonl). Config af_pf_baseline_opus_r245: CLI
pinned at 2.1.245 (the August build that served rep 1), effort xhigh
passed explicitly, model claude-opus-4-8 as in the registered arm; the
build is deliberately NOT today's 2.1.273 so that a July-like outcome
cannot be attributed to the client. Run id PROBE_pf_baseline_opus_r245_60,
1 rep, parallel 4, launched from dev with the same runner as A142
(version/effort/session recorded per attempt). Scorer:
harness/probe_regime.py (read-only; prints reference and probe blocks and
the verdict below). The probe rows never enter a registered cell and are
never merged into the A142 rerun (separate run id).

Reference on the same 60 problems (scorer output, before launch):
July rep 0 solved .867, killed .133, first-turn thinking median 8,125
estimated tokens, 6 attempts without an assistant turn; August rep 1
solved .150, killed .833, median 22,775, 30 without an assistant turn.
First-turn thinking = sum of the CLI's thinking_tokens deltas before the
first tool call (the A142 signature). Same-regime references for the
thresholds: P(re-solve | solved in the other rep) = .96 opus evolve, .92
opus sibling (both August reps), .90 opus control within August (43
problems, rep 0 on 08-16 vs rep 1 on 08-29); P(solve | unsolved in the
other rep) = .19, .15, .00 respectively; cross-era control .65.

Decision rule, fixed now. Axis 1 (outcome): re-solve fraction on the 45
july_only problems: >= .70 July-like (same-regime re-solve is >= .90;
the margin allows for selection of marginal problems), <= .35
August-like (same-regime solve-after-unsolved is <= .19), otherwise
intermediate, which is what pure noise plus regression to the mean would
give (~.5) and is NOT read as a match with either era. Axis 2
(signature): first-turn thinking median and kill rate, each nearer (log
scale) to the July or to the August value on the same 60 problems.
Verdict "July-like" or "August-like" only when all three agree;
anything else is a third regime and is reported as such. Attempts that
match the quota-poisoning pattern (<= 2 turns, non-solve, "limit"/"API
Error" in result_text) are wiped and rerun before scoring. Expected
size: 60 attempts, 45-55 min at parallel 4.

Consequences by outcome, decided now. July-like: the August rows are the
anomaly; a coherent opus family then needs the control rerun (A142, as
prepared) AND fresh evolve/sibling reps in the current regime, sized
after the probe; the registered August cells stay in the tables with the
era flagged. August-like: A142 proceeds unchanged. Third regime: report
the three regimes side by side and rerun the full opus family in one
window (the A142 census machinery applies). Registered numbers are never
replaced in any branch.

A143 ABORTED (2026-09-16, user decision, ~35 min after launch). The
runner was killed after 13 of 60 attempts had completed (python process
first, then the wrapper and the orphaned CLI children; 16 attempt
directories exist, 13 result rows). The pre-registered rule needs all 60
and is NOT applied; the partial rows stay in
logs/runs/PROBE_pf_baseline_opus_r245_60/ as a description only. What
they show: 1 solve (213 s) and 12 wall kills at 300 s, of which 5 had no
assistant turn; killed attempts accumulated 230-245 thinking events
(~24k estimated thinking tokens) with every rate-limit event "allowed"
at utilization 0, so the kills are genuine thinking, not stalls or quota
poisoning; all rows on 2.1.245 with the single MCP tool. On these
problems the July rows killed 13% and thought ~8k on the first turn. The
partial probe therefore looks like the August regime and not the July
one, and nothing in it suggests the August rows were a transient
glitch; the A142 rerun stays as prepared. The user then asked for the
same kind of probe on the other families (A144).

## A144 — PRE-REGISTERED: regime probes of the sonnet and haiku families (branch dev)

Registered 2026-09-16 before launch. Question (user): was the
July->August change limited to opus? The sonnet family (control,
evolve, sibling; all July, builds 2.1.201/2.1.209) and the haiku family
(wall-only evolve July 2.1.209; control and sibling August 2.1.233) have
no same-arm rows in two eras, so the test is whether a fresh run TODAY
is a plausible third rep of an arm's two July reps ("stability" mode of
harness/probe_regime.py). One arm per family, the most wall-sensitive
one that needs no new binary except the frozen server:

- sonnet: control af_pf_baseline (claude-sonnet-5, baseline server,
  single check tool) on 60 of its 244 problems: 40 solved in both July
  reps, 10 in exactly one, 10 in neither, random.Random(144).sample per
  stratum sorted by problem id; manifest
  data/manifests/minif2f_test_sonnet_probe60.jsonl; config
  configs/af_pf_baseline_r245.json = af_pf_baseline + cli_version
  2.1.245 + effort xhigh explicit (sonnet ran at settings xhigh in July,
  A142 amendment); server = the dev build of the baseline server, whose
  sources are identical between main and dev (git diff main dev --
  src/baseline_server is empty; mcp_core only gained two files the
  baseline server does not use). Run id PROBE_pf_baseline_sonnet_r245_60.
- haiku: wall-only evolve frozen_wallonly (claude-haiku-4-5, frozen
  session server, 200-turn rail, 300 s) on 60 of its problems, same
  40/10/10 construction, seed 144; manifest
  data/manifests/minif2f_test_haiku_probe60.jsonl; config
  configs/frozen_wallonly_r245.json = frozen_wallonly + cli_version
  2.1.245 + server command pointing at
  .claude/worktrees/main-frozen/_build/default/src/session_server/rocq_agent_session.exe,
  a worktree of branch main (tip 7abb90b) built with `dune build --root
  .`. Server identity, checked directly: src/ and dune-project at
  9efd7bd (2026-07-15 09:40, the last surviving commit before the
  wall-only run started at 14:16) and at d554a38 (2026-07-17) are
  identical to main's tip, so the worktree build is the server those
  rows ran; the sonnet control's baseline server likewise matches main
  and dev from b48fbf4 (2026-07-15 01:01) onward. CORRECTION to the
  first draft of this entry: the run_meta git revs of the three
  2026-07-15 runs (ca4322c6, 61c4ac40) are absent from the object
  database, but that is NOT due to the A85/A86 filter-repo rewrites,
  which took place on 2026-07-11, before those runs; neighbouring
  commits survive with no rebase signature, and the cause (most likely
  a launch checkout whose HEAD was later dropped and garbage-collected)
  is not established. No effort flag (haiku has none). Run id
  PROBE_frozen_wallonly_r245_60.
Both: 1 rep, parallel 4, one sequential chain (sonnet then haiku), the
A142 runner (version/effort/session recorded per attempt, refuses a
mismatched binary). Smoke runs _smoke_sonnet_r245 and _smoke_haiku_r245
(one attempt each) precede the launch. Probe rows never enter a
registered cell.

Reference on the probe problems (scorer, before launch):
- sonnet control: rep 0 solved .750 / killed .267 / first-turn thinking
  median 2,175 / wall(solved) median 71 s; rep 1 .750 / .250 / 1,600 /
  62 s; P(rep 1 solved | rep 0 solved) .889; rep0/rep1 agreement .833;
  mean kill rate .258; thinking median over both reps 1,775.
- haiku wall-only evolve: rep 0 .717 / .233 / 228 / 15 s; rep 1 .783 /
  .217 / 237 / 16 s; re-solve .930; agreement .833; mean kill rate .225;
  thinking median 234 (below the 500 floor, so axis 3 uses the wall of
  solved attempts, median 16 s).

Decision rule, fixed now, per arm. Axis 1: P(probe solved | solved in
both reps) >= .80 (same-era references .87-.96; the opus cross-era value
was .65 on all July-solved problems). Axis 2: probe kill rate within
+-.15 of the reps' mean. Axis 3: first-turn thinking median within a
factor 1.5 of the reps' median, or for haiku the wall(solved) median
within a factor 1.5. UNCHANGED = all three hold; CHANGED = axis 1 fails
or two axes fail; AMBIGUOUS = exactly one of axes 2/3 fails (reported,
not read either way). Quota-poisoned attempts are wiped and rerun
before scoring.

Consequences, decided now. Sonnet UNCHANGED: the sonnet family, already
single-era, needs no rerun and stays comparable across families; sonnet
CHANGED: the family stays internally coherent (all July) but sits in a
different era from any current-window opus rerun; whether that requires
rerunning the sonnet family (3 arms x 2 reps = 1,464 attempts) is the
user's call and depends on whether the coherence claim is within-family
or matrix-wide. Haiku UNCHANGED: the haiku family as recorded (evolve
July, control/sibling August) is coherent and the A118 contrast can be
reported with this probe as the evidence; haiku CHANGED: rerun the
wall-only evolve arm in the current window (488 attempts) before
reporting the contrast. Opus: the A143 partial probe is August-like, so
A142 proceeds as prepared. Registered numbers are never replaced.

A144 OUTCOME, sonnet (2026-09-16, chain launched 17:30 local after both
smoke runs passed; 60/60 attempts, 2,327 s, all on 2.1.245, no API-error
or limit text in any row). Probe: solved .700, killed .300, first-turn
thinking median 1,600, wall(solved) median 53 s, 2 attempts without an
assistant turn. Axis 1: P(probe solved | solved in both July reps) =
.925 on 40 problems (rule >= .80). Axis 2: kill rate .300 vs reference
.258 (rule +-.15). Axis 3: thinking median 1,600 vs 1,775 (rule x1.5).
Agreement of probe outcomes with rep 0 .883, with rep 1 .817, against a
rep0-vs-rep1 agreement of .833. VERDICT: UNCHANGED since the registered
reps, all three axes. Consequence as pre-declared: the sonnet family
needs no rerun. (Provenance note: effort_recorded is empty on some rows
where the CLI session file was not found at copy time; effort_requested
is xhigh on every row and the rows that were recovered read xhigh.)

A144 haiku, first launch VOID (2026-09-16): the haiku probe started
right after the sonnet one (attempts written 17:52-18:11 local) and 28
of its first 29 rows are the CLI's "API Error: Can't reach the API
server (ENOTFOUND)" with zero tool calls and no assistant turn, a DNS
outage on the host during that window (the sonnet rows, which finished
before it, carry no such text; DNS resolved again by 18:12). The 29th
row, mathd_algebra_342, is a genuine solve (4 tool calls, 35 s) from the
end of the window; four more attempts were in flight when the runner
was killed. The whole first-launch directory and log were moved aside
as PROBE_frozen_wallonly_r245_60.void_network(.log) and the probe was
relaunched alone under the same run id, redoing all 60 slots. The rule
is applied only to the relaunch.

A144 OUTCOME, haiku (2026-09-16, relaunch 18:15-18:45 local; 60/60
attempts, 1,780 s, all on 2.1.245, no API-error or limit text in any
row). Probe: solved .767, killed .233, first-turn thinking median 229,
wall(solved) median 18 s, no attempt without an assistant turn. Axis 1:
P(probe solved | solved in both July reps) = .950 on 40 problems (rule
>= .80). Axis 2: kill rate .233 vs reference .225 (rule +-.15). Axis 3:
wall(solved) median 18 s vs 16 s (rule x1.5; thinking axis replaced as
pre-declared, reference median 234 < 500). Agreement of probe outcomes
with rep 0 .850, with rep 1 .883, against a rep0-vs-rep1 agreement of
.833. VERDICT: UNCHANGED since the registered reps, all three axes.
Consequence as pre-declared: the haiku family as recorded (wall-only
evolve July, control and sibling August) is coherent, and the A118
contrast can be reported with this probe as the evidence.

A144 CONCLUSION (2026-09-16). The July->August change is specific to
claude-opus-4-8: sonnet control and haiku wall-only evolve, rerun today
on 60 registered problems each with the CLI held at the August build,
reproduce their July reps within the same-era agreement seen between
those reps; the opus control, on the same build, reproduces its August
rows (A143, partial). The only cell that needs a rerun for a coherent
held-out matrix is therefore the opus control, and A142 stands exactly
as prepared. The probe rows (PROBE_pf_baseline_sonnet_r245_60,
PROBE_frozen_wallonly_r245_60, the aborted PROBE_pf_baseline_opus_r245_60
and the quarantined void directory) remain in logs/runs/ as evidence and
never enter a registered cell.

## A145 — version gate withdrawn; haiku family status restated (branch dev)

2026-09-16, user decision after A144. With the CLI build shown
immaterial and the July->August shift opus-specific and server-side,
the per-rep build gate is dropped: harness/version_gate.py is deleted
(never committed) and the "VERSION-MIXED ARM" alarm at the end of
harness/run_eval.py becomes a plain provenance line. What stays: the
per-attempt provenance the A142 runner records (claude_code_version,
session_id, effort_requested, effort_recorded, the copied
cli_session.jsonl), the run_meta build census, and the optional config
key cli_version, which makes the runner refuse a binary of another
version when a run chooses to pin one (the prepared A142 rerun does).

Haiku family, restated from the rows on disk: every haiku arm has a
complete rep 0 (wall-only evolve 244 + a full rep 1; control 244 = 243
on 2.1.233 + the A119 redo; sibling 244 = 241 + the three A119 redos).
The comparators' rep 1 was never completed (control 49/244, cut by the
A118 9 h ceiling and excluded per A118b; sibling none) and A119 left it
"deferred and out of scope". A144 removes the era objection that
withheld the A118 contrast. CORRECTED the same day (user requirement,
restated): every (model, arm) cell of the held-out matrix carries two
full reps, so the haiku comparators' rep 1 IS required; the first draft
of this entry called it optional and was wrong. The rerun list for a
complete, coherent matrix is therefore: the opus control (A142) plus
rep 1 of the haiku control and of the haiku sibling (A146).

## A146 — PRE-REGISTERED: haiku comparators, rep 1 completion (branch dev)

Registered 2026-09-16 before launch, on the user's requirement that
every (model, arm) cell carry two full reps. SCOPE: rep 1 of
FINAL_pf_baseline_haiku (195 slots: the 49 rows of 2026-08-18, build
2.1.233, are retained; their max turn count is 40, so neither the
cap-100 rail they ran under nor the registered cap-200 rail bound, and
none carries limit/API-error text) and rep 1 of FINAL_pf_rocqmcp_haiku
(all 244 slots). Configs VERBATIM as registered in A118b
(af_pf_baseline_haiku, af_pf_rocqmcp_haiku: claude-haiku-4-5, 300 s
wall, cap-200 rail, prompt-free template, no effort parameter); run
ids unchanged, since harness/run_eval.py resumes by (problem, rep)
slot: `--reps 2` runs exactly the missing slots. Runner = the A142
runner (per-attempt provenance recorded; no gate, A145). CLI = the
pinned 2.1.245 binary via CLAUDE_BIN, chosen for uniformity with the
September block; no cli_version key is added to the registered
configs. Servers: the control's baseline server from the dev build,
source-identical to main's (A144); the sibling's rocq-mcp editable
install at commit 6983113 (the commit A121 records for every sibling
arm), whose source tree carries no modification (git status: uv.lock
only, plus untracked scratch files), driven through the unchanged
harness/mcp_prewarm_proxy.py (no harness drift since the rep-0 rows,
git diff 3bc79ad6..dev empty for the proxy, common.py, datasets.py).
Smoke: one attempt of the sibling config on 2.1.245 before launch
(_smoke_rocqmcp_haiku_r245). Expected 439 attempts, about 7 h at
parallel 4 from the recorded per-attempt walls (control 255 s, sibling
212 s); token cost negligible.

ANALYSIS, fixed now: the haiku held-out rows enter the tables like the
sonnet ones (pass@1 = solved/attempts over both reps, pass@2 = either
rep), together with the A121 semantic column where it exists. The
same-regime check for the new rows is within-problem agreement of rep
1 with rep 0 on each arm, read against the same-era references
(.90-.96 re-solve; the haiku wall-only evolve arm .91) and against the
A144 haiku probe, which showed the haiku regime unchanged from July.
Era for the record: haiku control/sibling rep 0 = August, rep 1 =
September; haiku evolve = July; A144 justifies pooling. Registered
numbers are never replaced; the 4 A119 redo rows stay as recorded.
Launch order, one sequential chain after the smoke passes: A142 opus
control first (decision-relevant), then haiku sibling rep 1, then
haiku control rep 1; preconditions per the ops rules (no other runner,
AC power, no concurrent heavy CLI use on the account).

LAUNCHED 2026-09-16 20:23 local (user: "launch everything overnight"):
one caffeinate'd sequential chain, logs/matrix_completion_chain.log,
per-run logs logs/FINAL_pf_baseline_opus_r245.log,
logs/FINAL_pf_rocqmcp_haiku_rep1.log, logs/FINAL_pf_baseline_haiku_rep1.log;
pinned CLI 2.1.245 confirmed at launch, AC power, no other runner.

A142 OUTCOME (2026-09-17 00:02 local; run finished 23:59, 13,115 s, 244
rows, all on 2.1.245, effort_requested xhigh on every row and
effort_recorded xhigh on the 161 rows that have at least one assistant
message; the other 83 are exactly the attempts killed before the first
API response arrived (zero assistant events), and the CLI stamps the
effort on assistant records, so for them there is nothing to record —
verified 2026-09-17 against the session files, A149; 0
quota-poison-pattern rows). Pre-registered within-problem
comparison, 244 problems: rerun solved 107 (.439), killed .561;
registered rep 1 solved 104 (.426), killed .578; registered rep 0
solved 149 (.611), killed .385. Agreement rerun vs rep 1 .939
(discordant 9:6), P(rerun solved | rep 1 solved) .942 — inside the
same-regime band (.90-.96); rerun vs rep 0 .779 (discordant 6:48),
P(rerun solved | rep 0 solved) .678 — the cross-era value. Per bucket
(rerun / rep 1 / rep 0): easy .615/.592/.785, medium .291/.278/.443,
hard .114/.143/.343. Reading: the September regime is the August one;
the registered July-era rep 0 is the outlier, as A143 indicated. The
coherent opus control pair for reporting is therefore (rerun, registered
rep 1), exactly as A147 fixed; the registered .611 stays in the tables,
unpooled.

A146 OUTCOME, sibling (2026-09-17 03:40 local; 13,180 s, 244 new rows,
all on 2.1.245, 0 quota-poison-pattern rows): rep 1 solved 80 (.328),
killed .574, against rep 0 solved 82 (.336), killed .602; within-problem
agreement .918, P(rep 1 solved | rep 0 solved) .866, discordant 11:9 —
same-regime (references .87-.96). The haiku control's rep 1 (195 slots)
started at 03:40.

A146 OUTCOME, control (2026-09-17 07:04 local; 12,138 s for the 195
slots, all on 2.1.245, 0 quota-poison-pattern rows; the 49 retained
2026-08-18 rows complete the rep): rep 1 solved 42 (.172), killed .775,
against rep 0 solved 41 (.168), killed .775; within-problem agreement
.963, P(rep 1 solved | rep 0 solved) .902, discordant 4:5 — same-regime.
MATRIX COMPLETE: every (model, arm) cell of the held-out matrix carries
two full reps (haiku 3 x 488; sonnet 3 x 488; opus sibling and evolve
488 each, opus control = 244 rerun + 244 registered rep 1, with the
registered July-era rep 0 kept unpooled). docs/RESULTS_ALL.md
regenerated at 07:10 under the full integrity gates (no failure, no
--force) by `python3 harness/results_all_gen.py --write`.

## A147 — PRE-DECLARED: reporting rules of the completed held-out matrix (branch dev)

Declared 2026-09-16 ~20:45 local, while the A142/A146 chain runs and
before any of its rows has been read (the first opus attempts had
completed; none was inspected). Purpose: fix, before the data exist,
how docs/RESULTS_ALL.md reports the matrix once every (model, arm)
cell has two reps, so that no reporting choice is made after seeing a
number. Implemented in harness/results_all_gen.py and the producers
under harness/results_tables/ the same evening; the generator refuses
to write until the integrity gates of every arm pass (a --force
preview is flagged in the document itself).

1. Reps and slots. §3 keeps its conventions (pass@1 = rep-0 solves /
   problems; pass@2 = either rep; $/solve, wall, tokens over all rows
   of the arm). For every arm, rep 0 and rep 1 are the registered
   rows, except the opus control, whose COHERENT pair is: rep 0 := the
   A142 rerun (FINAL_pf_baseline_opus_r245, all 244 rows), rep 1 := the
   registered rep 1 of FINAL_pf_baseline_opus (2026-08-29). The
   registered July-era rep 0 of the opus control is NOT pooled into
   any cell; it is shown as its own unbolded row, "control, registered
   rep 0 (July era, A120/A143)", with pass@2 blank, so the registered
   number remains visible and unreplaced. Reason: A143 showed the July
   rows belong to a serving regime that no longer exists, while the
   August/September rows of every opus arm are mutually consistent.
2. Haiku family. Control FINAL_pf_baseline_haiku and sibling
   FINAL_pf_rocqmcp_haiku enter §3 beside the wall-only evolve arm
   FINAL_frozen_wallonly, at two reps each, with bold within the
   family like every other family; the A118 registered contrast
   (pooled exact McNemar, rep 0, Holm over the two-test family) enters
   §5 as "haiku (A118)". Era note carried in the coverage text:
   evolve July, comparators August (rep 0) and September (rep 1),
   pooled on the strength of A144.
3. Opus contrasts. §5 gains "opus (A147)": evolve rep 0 vs the A142
   control rep and vs sibling rep 0, same test as the other families.
   The registered rep-0 contrast with the July-era control (A117
   report-only) stays as a computed paragraph under the table, labelled
   as such. §3c (common-solved efficiency) pairs slots across arms:
   slot 0 = (r245 control, sibling rep 0, evolve rep 0), slot 1 = the
   three registered rep-1 rows; haiku gets a §3c block on its two reps.
4. §3b (A121 sibling-verified column) stays a rep-0 audit of the
   REGISTERED runs, so its opus control row is the registered July-era
   rep 0 and is labelled so; the A142 rerun and the haiku rep-1 rows
   were not audited (the audit predates them) and the coverage text
   says so. Haiku control and sibling rep-0 rows are added to §3b if
   the A121 evidence covers them, otherwise listed as not audited.
5. p-values in §5 are printed from the computed value (two significant
   figures, scientific below 1e-2) for every family; the two literal
   bounds the previous generator carried ("p < 1e-5", "p < 1e-23")
   become exact values — a presentation change only.
   Implemented and previewed the same evening (forced preview on the
   unfinished runs, scratch output only): sonnet, mistral, terra, §2
   and §4 cells reproduce byte-for-byte; only the intended rows and
   prose differ. The generator refuses docs/RESULTS_ALL.md until the
   three running arms are complete and clean.
6. Provenance census: the §3 head lists, per arm, the CLI builds its
   rows ran on (from the per-attempt init events), so the era structure
   is visible in the document rather than only in this trail.
Nothing in 1-6 is changed after the chain finishes; if a gate fails in
the morning, the failing arm is repaired per the runbook (quarantine +
redo), never edited, and the repair is logged here.

## A148 — launch checkout of the completion chain, and the replay proof (branch dev)

2026-09-17, raised by the user ("You run on dev!!"). FACT: the A142/A146
chain (and the A144 sonnet probe) was launched from the `dev` checkout,
whose `_build` holds the dev binaries; the operator was not told this at
launch and should have been. What that touched, per arm:
- opus control rerun (FINAL_pf_baseline_opus_r245) and haiku control rep
  1 (FINAL_pf_baseline_haiku): MCP server = the dev build of
  src/baseline_server (mcp.json records
  <repo>/_build/default/src/baseline_server/rocq_agent_baseline.exe).
  Sources of src/baseline_server are identical between main and dev
  (git diff empty); the baseline server links only Mcp_core.Mcp_server
  and Mcp_core.Proc, both unchanged; dev's mcp_core additionally
  contains project_verify.ml and text.ml, which nothing in the baseline
  server references. The two builds are not byte-identical (library
  archive contents and build paths differ), so the identity is at the
  source level.
- haiku sibling rep 1 (FINAL_pf_rocqmcp_haiku): the external rocq-mcp
  tool (editable install at 6983113) through harness/mcp_prewarm_proxy.py;
  no server of this repository; the proxy is unchanged since rep 0.
- the runner path (harness/run_eval.py, common.py, datasets.py, the
  proxy) is identical between main and dev apart from the A142
  provenance additions (uncommitted).
- the refactored component, src/session_server, ran in NO registered
  row; the only session-server run of the night (the A144 haiku probe)
  used the frozen main worktree build explicitly.
The solve verdict is harness-side (harness/gate.py on the delivered
file); the server supplies the check tool's feedback and writes
candidate.v after a successful check.

REPLAY PROOF (harness/replay_check_equivalence.py, same day): every
`check` call of the new control rows, taken from the attempt's own
server.jsonl (args.content), replayed through the FROZEN main build of
the baseline server (.claude/worktrees/main-frozen, tip 7abb90b, `dune
build --root .`) with the attempt's own task_prefix.v and ROCQ_*
environment; reply text, exit code, error flag and timeout flag compared
call by call, and the resulting candidate.v compared byte for byte with
the run's own:
- FINAL_pf_baseline_opus_r245: 244 attempts, 300 check calls, 0
  mismatching calls, 0 short replays; candidate.v identical in all 122
  attempts that had one, absent in both builds in 39, no check call in
  83; 0 errors.
- FINAL_pf_baseline_haiku rep 1: 244 attempts, 8,349 check calls, 0
  mismatching calls, 0 short replays; candidate.v identical in all 65
  attempts that had one, absent in both in 179; 0 errors.
Evidence: logs/replay_equivalence/FINAL_pf_baseline_opus_r245.json and
FINAL_pf_baseline_haiku_rep1.json (per-attempt records). Conclusion:
on every input these rows actually produced, the dev build of the
baseline server and the frozen build are indistinguishable, and the
gate input (candidate.v) is identical; the rows stand as recorded
unless the user decides otherwise. RULE, added to the runbook practice:
registered arms are launched from a checkout of `main` (or with the
config's server command pointing at the frozen worktree build by
absolute path, as configs/frozen_wallonly_r245.json does), never from
`dev`; a run launched from dev must say so in its registration.

## A149 — session files dropped from the record; tooling sync `dev` -> `main`; single-file logs release

2026-09-17, user decisions. (1) CLI SESSION FILES. The per-attempt
cli_session.jsonl copies (A142 runner) and the backup directory
logs/cli_sessions_backup/ served one audit (the effort question, closed in
the A142 amendment) and feed no table. They are excluded from the logs
release; the runner no longer copies the session file into the attempt
dir and only extracts the per-attempt effort value into the result row
(harness/run_eval.py `_recorded_effort`, read in place). The 83 opus
rerun rows and 2 sonnet-probe rows with an empty effort_recorded were
checked against the CLI's own session files: every one of them is an
attempt with zero assistant messages (killed before the first API
response), and the effort is stamped on assistant records only, so the
empty value is the correct record, not a gap; no sidecar, no edit. (2)
TOOLING SYNC. `main` receives
every change of `dev` EXCEPT src/, test/ and dune-project, so that `main`
keeps building the frozen server byte-for-byte (verified by rebuilding
and comparing the session-server binary hash) while carrying the
generator, producers, runner, probe and replay tooling, configs,
manifests and this trail; `dev` is then merged with `main` so it stays
strictly above it. (3) RELEASE. The complete logs/ tree ships as ONE zip
(harness/release_logs.py; entries `logs/...`, unpacks in place; the
manifest docs/LOGS_RELEASE.md and checksum docs/logs_release.sha256 are
regenerated by the same script), attached to a new release of the
private repository whose tag points at the synced `main`; the
regenerated docs/RESULTS_ALL.md at that commit is byte-identical to the
generator's output over the shipped logs (`--check`). The A130/A131 audit
tooling under src/audit/ and test/audit_* is dev-only OCaml and test code
and stays on `dev` with the rest of src/ and test/; `main` keeps their
evidence (logs/audit_autoform, logs/audit_verify) and the trail. Three
pre-existing wording hits (docs/REPORT.md, two July trail lines) were
scrubbed the same day. Outcome recorded below once done.

A149 OUTCOME (2026-09-17). Sync: `main` f7f3c86 = merge of `dev` 951a8e4
into 7abb90b with src/, test/ and dune-project taken from 7abb90b
(dev's 13 added files under src/audit, src/mcp_core and test/ removed
from the merge); verified: `git diff 7abb90b f7f3c86 -- src test
dune-project` empty, `git diff dev f7f3c86` outside those paths = the
16-line branch note only, harness/ identical, and the rebuilt session
and baseline servers byte-identical to the pre-merge frozen build
(sha256 e5fd1ba3… and fb8a2692…). A first attempt at the merge had left
dev's added source files in place and changed the binaries; it was
reset and redone, and the checks above are of the redone commit.
Tag artifact-2026-09-17 (annotated, 810c893) points at f7f3c86; `dev`
fast-forwarded to f7f3c86. Release asset: logs_artifact-2026-09-17.zip,
653,472,469 bytes, sha256
6811db34bd1383d6cca5dc4715d6c4335b02c064db8b5a4944b438b778175f53,
170,437 files (7.5 GB raw); excluded as declared (849 per-attempt
session copies, the session backup directory, 6 .DS_Store, 51
symlinks); verified before upload to contain no path under the backup
directory, no cli_session.jsonl, no path containing any of the 24 CLI
session ids present under ~/.claude/projects on the operator's machine,
and no uuid-named .jsonl. REPRODUCTION, run before the release was
created: a fresh `git clone --branch main` at f7f3c86 plus the zip
unpacked in place leaves no tracked file modified (the shipped audit
evidence equals the tracked copies), `python3
harness/results_all_gen.py --check` prints IDENTICAL (token consistency
360 rows, 0 mismatches), a fresh `--write` to a scratch path is
byte-identical to docs/RESULTS_ALL.md, and `dune build` in the clone
yields the two frozen binaries byte-identical to the pre-merge build.
Note for the record: `main` and the tag reached the remote a few
minutes before this reproduction ran (an interrupted command chain);
the release itself was created only after it passed.

## A150 — PRE-REGISTERED: prompt-free haiku evolve arm (branch dev; frozen server)

2026-09-23, before launch. FINDING (external audit, confirmed from the
run_meta configs): the held-out haiku family is not prompt-uniform. Its
evolve row (FINAL_frozen_wallonly, A100) is the phase-1 frozen
configuration with a 1,582-character system prompt that describes every
tool and prescribes strategy (auto_close first on every goal, try with
several candidates as the main tool) and a task template ending in "Use
try with several candidate tactics in one call", while its comparators
(A118: af_pf_baseline_haiku, af_pf_rocqmcp_haiku) are the sonnet
prompt-free configs with the model swapped: no system prompt, the
prompt-free rules template. The other four families (sonnet, opus,
mistral, terra) are prompt-free in all three arms. The A118 registration
did not name this asymmetry; the results document labels the row
"guided prompt" in §3/§3b/§3c but the §5 haiku contrast (69:0, 31:3)
carried no flag and is confounded in evolve's favour. (§2 dev60 is
separately non-uniform: all Claude arms guided with arm-specific
prompts, mistral/terra prompt-free at rail 100; disclosed as the
development arena, no registered contrast rests on it.)

REGISTRATION. New arm af_pf_session2_haiku = af_pf_session2 verbatim
(no system prompt, prompt-free rules template, same server env and five
tools) with model claude-haiku-4-5 and the haiku family's cap-200 rail
(A118b), 300 s wall; server = the frozen session server built in the
main worktree, by absolute path (A148 rule; sha256 e5fd1ba3…); CLI
pinned 2.1.245, no effort flag (haiku has none); run id
FINAL_pf_session2_haiku, minif2f_test, 2 reps, parallel 4, launched from
the dev checkout with the server path pinned as above. Smoke
_smoke_pf_session2_haiku precedes the launch.

ANALYSIS, fixed now. The prompt-free haiku evolve arm becomes the haiku
evolve row of §3 (pass@1/pass@2/cost/tokens/wall/kills, both reps), of
§3c and of the §5 haiku contrast (pooled exact McNemar, rep 0, Holm over
the two-test family, vs the A118 comparators), making the haiku family
identical in construction to the other four. The guided row
FINAL_frozen_wallonly stays in §3 as a disclosed, unbolded extra row
("evolve, guided phase-1 prompt (A100); not pooled") and in §3b as its
audited self; it enters no contrast. No prediction is registered on the
direction of the change; whatever the prompt-free arm measures is
reported. Reporting rule for a comparison between the two haiku evolve
rows: within-problem, descriptive, in the §3 text. Same-regime check as
A146: rep-1 vs rep-0 agreement.
A150 SLEEP REPAIR (2026-09-23 14:30): the laptop slept twice during the
first half hour (wake 14:25); the runner survived but 8 of its first 19
rows are contaminated (7 flagged machine_slept by the watchdog, plus
algebra_9onxpypzleqsum2onxpy at wall 556 s, unflagged; both criteria
quarantine: machine_slept or wall > 320 s). Those rows were moved to
results.quarantine.jsonl, the runner killed (in-flight attempts
discarded) and relaunched with the same command; it resumes on the 11
clean slots kept. Machine on battery at relaunch, operator asked to plug
in.
A150 OUTCOME (2026-09-23 21:00 local; 477 slots in 23,529 s after the
sleep repair, 488 rows, all on 2.1.245, 0 quota-poison rows, 0 sleep
flags, 8 quarantined rows from the first half hour). Prompt-free haiku
evolve: rep 0 solved 117 (.480), killed .463; rep 1 solved 119 (.488),
killed .455; rep agreement .918, P(rep 1 solved | rep 0 solved) .923,
discordant 9:11 — same-regime. Per bucket rep 0 / rep 1: easy
.692/.685, medium .278/.316, hard .143/.143. Against the guided phase-1
row on the same problems (descriptive, as pre-declared): guided rep 0
solved 110 (.451), rep 1 115 (.471); within-problem agreement .906 (rep
0; prompt-free-only 15, guided-only 8) and .902 (rep 1; 14 vs 10). The
prompt-free arm solves slightly more in every bucket; the guided prompt
did not help this arm, and the guided row's lower cost and token cells
(0.06/0.26/0.68 vs 0.12/0.39/0.48 $/solve; 2.4/4.5/7.6 vs 4.0/9.3/12.6
ktok) reflect the prompt's strategy prescription (auto_close first, try
batches), not a solve advantage. Registered haiku contrast on the
prompt-free arm (§5): evolve vs control 76:0 (p = 2.6e-23), vs sibling
37:2 (p = 2.8e-9), Holm within the family. docs/RESULTS_ALL.md
regenerated under the full gates (no --force); the miniF2F matrix is now
prompt-uniform across all five families (three prompt-free arms each).
A150 RELEASE (2026-09-23). Logs re-packaged as one zip after the
prompt-free haiku arm (harness/release_logs.py --tag artifact-2026-09-23):
logs_artifact-2026-09-23.zip, 174,611 files, 668.4 MB, sha256
dca2faaf354e5aab85956acef9203a74ff52015e7afc59b4bbc6a4b80f40141e; same
exclusions as A149; verified to contain no path under the session backup
directory, no cli_session.jsonl, no path containing any of the 27 CLI
session ids under ~/.claude/projects on the operator's machine, and no
uuid-named .jsonl. Tag artifact-2026-09-23 on `main`; reproduction from a
fresh clone plus the zip (--check IDENTICAL, frozen build byte-identical)
run BEFORE the tag was pushed and the release created this time; outcome
appended below.
A150 RELEASE OUTCOME (2026-09-23): reproduction from a fresh clone of
`main` at a9e1a22 plus the zip: no tracked file modified by the unzip,
checksum OK, `--check` IDENTICAL, fresh write byte-identical, frozen
binaries byte-identical (e5fd1ba3…, fb8a2692…). Then pushed dev, main
and tag artifact-2026-09-23 (a9e1a22), and created the release with the
single asset logs_artifact-2026-09-23.zip (700,879,237 bytes as uploaded
= local size). The release artifact-2026-09-17 stays as the pre-A150
snapshot.

## A151 — anonymized reproduction archive (branch dev; built from `main`)

2026-09-25. A single zip for double-blind review, built by exporting
`main` (git archive, tip 3a22994: the frozen src/, harness, configs,
manifests, docs, results document) and copying logs/ with the A149
exclusions plus every compiled artifact (`_build/`, `.glob`, `.vo`,
`.vos`, `.vok`, `.cache`, `.aux`): 114,123 log files, 4.5 GB raw, in
place of 174,617 / 9.0 GB. The results path reads only results.jsonl,
transcript.jsonl, run_meta.json, regrades.jsonl and the two audit
summaries, and this was verified rather than assumed: inside the archive
`python3 harness/results_all_gen.py --check` prints IDENTICAL (token
consistency 380 rows, 0 mismatches). Anonymization: every text file
(114,399 scanned, 32,704 changed) had the operator's home directory,
user name, the authors' names and e-mail, and the organisation name
replaced by placeholders; release-specific files (docs/LOGS_RELEASE.md,
docs/logs_release.sha256, harness/release_logs.py), the runbook, the
status file and .github/ were removed; the README's log-release
instructions were replaced by in-archive instructions and its citation
block dropped. Checks after scrubbing: no occurrence of any of the
scrubbed strings, no first name, no e-mail domain other than the
placeholder, no hostname in any run_meta (platform string only), no
account field in the CLI init events (apiKeySource "none"), sampled
transcripts free of account-like keys; the one external URL left is the
public opam repository in repro/setup.sh. File and directory NAMES were
scanned as well: one workspace directory an agent had named after the
operator's home path was renamed. Archive: rocq-mcp-evolve-artifact.zip,
616.6 MB, 154,898 entries, sha256
cb53c7edca39139a350b715f0aa95101ce63929649c17ec7e02c81fa328d3140, kept
outside the repository next to the logs release zips.

## A152 — report tables: one convention per presented cell (branch dev)

2026-09-25, user request: every table of the external write-up must be
regenerable from the logs. FINDING: the write-up's held-out cost and wall
cells had been computed outside this repository with an intersection taken
over run 0 only (reproduced exactly for sonnet and terra by that rule), and
its project cost cells mixed raw and grading-corrected rows (sonnet control
1.52/603 s = raw rows, evolve 431 s = raw, 1.25 = neither). The user set the
intersection rule as "across all runs". RESOLUTION: a new producer,
harness/results_tables/report_tables.py, rendered as RESULTS_ALL §8 (8a-8e),
with the conventions fixed in its docstring: accuracy = rep-0 pass@1;
common-solved problems = every server of the family solved the problem in at
least one run; cost and wall = means over each server's solved attempts on
those problems, both runs; efficiency on the same attempts with tool calls
counted in the transcripts (the sibling's results rows record one call per
attempt), input tokens including cache reads and writes, output tokens from
the final usage; projects on the re-verified verdicts (4 Terra rows
unsolved), cost and wall means over solved runs, grading-corrected rows
throughout; evolution points = pooled accuracy over all runs, cost and wall
means over solved attempts; per-mutation deltas as in A150's tables, the
project rows now on the grading-corrected rows (+2-1, +1-0, +1-1 instead of
the raw +3-4, +2-0, +1-1). The write-up's tables and figure data are
regenerated from §8 the same day; cells that changed are listed in the
session record, not here. `--check` IDENTICAL after the change.

## A153 — presented tables in their own document (branch dev)

2026-09-25, user request: RESULTS_ALL carries too much for a reader who only
wants the presented tables. RESOLUTION: §8 moves out of docs/RESULTS_ALL.md
into docs/REPORT_TABLES.md, generated by harness/report_tables_gen.py from
the same producer (harness/results_tables/report_tables.py) and the same
formatting helpers, so a cell common to both documents renders identically;
sections 1-7 of RESULTS_ALL are unchanged (`--check` IDENTICAL). The new
document opens with the run inventory behind every held-out cell (fair
protocol only: no system prompt, one template per server, two reps; the
Opus control = A142 rerun rep 0 + registered rep 1; the guided Haiku evolve
arm, the July-era Opus rep 0, development and probe runs enter no cell) and
carries: the per-mutation deltas, the held-out miniF2F table on the
common-solved problems, the efficiency table, the project-scale table, the
appendix variants (whole-dataset cost and wall time; per-task counts) and
the figure data (evolution points; bar-chart series). FINDING while
regenerating: the write-up's whole-dataset appendix table had its cost
column computed under the §3 convention (total spend / solves, failed
attempts included) while its body table uses means over solved attempts;
the appendix cells are regenerated under the body convention (producer
field cost_full), accuracy and wall time unchanged. docs/REPORT.md, the
pre-A121 narrative report, is untouched and still superseded by RESULTS_ALL.

## A154 — held-out accuracy reported over both runs (branch dev)

2026-09-25, user decision. The presented miniF2F tables reported accuracy
as the registered rep-0 look (pass@1, A147) while their cost and wall
columns used the solved attempts of both runs and the setup states two
runs per problem. RESOLUTION: in docs/REPORT_TABLES.md accuracy = solved
attempts / attempts over both runs, per bucket and pooled (producer
report_tables.py, build_minif2f); the auto-closable subset reports solved
attempts over both runs the same way. RESULTS_ALL §3 keeps the registered
rep-0 pass@1 and either-run pass@2 looks unchanged. Cells move by at most
.02 (sonnet sibling .73→.72, evolve .82→.80; terra sibling .82→.80; opus
control .44→.43, evolve .75→.76); bold placement unchanged except the opus
hard bucket (.54 evolve vs .46 sibling now bolded). Project accuracy was
already solved runs / all runs. The external figure files and the two
accuracy-derived prose numbers (gap to the sibling: +15/+8/+4 points on
Haiku/Sonnet/Opus) regenerated the same day. Planned next: problem-level
bootstrap intervals (both runs of a problem resampled together) on
accuracy, cost and wall time. The A151 archive predates A152-A154 and is
to be rebuilt.

## A155 — anonymized reproduction archive rebuilt (from `main` 845d96f)

2026-09-25. The A151 archive predates A152-A154, so it was rebuilt by the
same procedure from `main` at 845d96f: git archive of the tracked tree
(376 files, no history), logs/ with the A149 exclusions plus compiled
artifacts (`_build/`, .glob, .vo, .vos, .vok, .aux, and the micromega
.nra.cache/.nia.cache files: 114,123 log files, 4.48 GB raw, the A151
count), release files, runbook, status file and .github/ removed, README
patched to in-archive instructions with both `--check` commands. Scrub as
A151, extended to the 26 non-UTF-8 server logs (byte-preserving pass);
114,403 files scanned, 32,716 changed, one workspace directory renamed.
Inside the archive `harness/report_tables_gen.py --check` and
`harness/results_all_gen.py --check` both print IDENTICAL. Zero
occurrences of every scrubbed string in contents and names; run_meta
hosts carry platform strings only; 304 sampled CLI init events have no
account field. Archive: rocq-mcp-evolve-artifact.zip, 616,582,525 bytes,
154,901 entries, sha256
a0d3cb6c39205aec67c0db2f943a933d3b7b218fa2186918e4bc6c05d02f9295, kept
outside the repository; the A151 archive was re-checked for the
non-UTF-8 residue (none found) and is retained beside it as .prev.
