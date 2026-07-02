# STATUS — AI-native Rocq tooling experiment

_Last updated: 2026-07-02 08:55_

## TL;DR
Infrastructure done and battle-tested; naive control (baseline) re-running clean
on dev60 (~2.5 h, finishes late morning). The first real interface — a
persistent in-process prover session on rocq-runtime — is built, smoke-tested,
and dramatically faster per interaction (0.4–2 ms/step vs 266 ms/full-recompile
call). Its A/B against baseline on dev60 launches the moment the control
finishes. No blockers.

## Environment (recorded)
- Apple M3 Max, 14 cores, 96 GB RAM, macOS 14.3 · dedicated local opam switch
- OCaml 5.3.0 · **Rocq 9.1.1** (downgraded from 9.2.0 by the Coquelicot install —
  accepted, pinned; see A7) · Coquelicot 3.4.4 · mathcomp 2.5.0 · yojson 3.0.0
- Policy (fixed across all configs): claude CLI 2.1.198 headless,
  `claude-haiku-4-5`, MCP tools only, ≤30 turns, ≤300 s/attempt
- Repro: `repro/setup.sh` (fresh switch → pinned install → build → self-test)

## Where things stand
- [x] MCP server framework (OCaml, JSON-RPC stdio) + JSONL instrumentation
- [x] Naive baseline config (control): one `check` tool = full `rocq compile`
- [x] Harness: runner (wall-clock watchdog), layered anti-gaming gate,
  per-bucket report, monitor, profiler; manifests dev60/dev150/minif2f_valid;
  held-out test mechanically locked
- [x] **Session server** (`src/session_server`): prover embedded in-process on
  the public rocq-runtime API. Sentence-level `step` (good prefix commits,
  failing sentence reported structurally with goals after last success), O(1)
  `rollback` (Vernacstate snapshots), `state`, per-sentence timeouts, queries
  (Search/Check) execute without polluting the proof. Measured: init 215 ms
  once; 0.4–2 ms per step; ~310 MB RSS per session.
- [x] **try tool** (`session_try` config): up to 8 candidate scripts evaluated
  speculatively from the same snapshot in one call; first success auto-commits;
  per-candidate verdicts + remaining-goal digests.
- [ ] RUNNING: `baseline_dev60` control (2 reps × 60, parallel=4, caffeinated)
- [ ] NEXT: session and session_try A/Bs on dev60; then compact-state and
  search ladder rungs; scalability sweep; freeze; held-out.

## Profiling so far (easy bucket, first control attempt — full numbers when run completes)
- Prover time = 6% of wall; model API ≈ 90%. **Turns and output tokens are the
  bottleneck, not compile seconds** (H1 partially refuted — timeouts did not
  bite on easy; recheck on medium/hard).
- Failed-check taxonomy: syntax 128 / unknown_ref 43 / other 59 → the policy
  burns whole turns learning one token was invalid Rocq. Sentence-level
  feedback + batched try target exactly this.
- Input tokens grow ~330/turn (quadratic-ish context growth confirmed, small in
  absolute terms on easy).

## Incidents (all diagnosed, fixed, logged)
1. **rocqworker leak**: `rocq compile`'s worker re-groups itself → escaped
   group-kill on timeout, pinned a core for 19 min. Fix: descendant-tree kill.
2. **"Timeout that never fired" = laptop sleep**: monotonic clocks pause during
   macOS sleep; wall clock doesn't. Attempts looked 580 s long; the harness was
   fine. Fix: wall-clock watchdog + `machine_slept` flag per record; evals run
   under `caffeinate`. First two control starts discarded (~$2.4 total);
   third start is the clean one.
3. Coquelicot not in default opam repo → added rocq/coq released repos
   (switch-scoped); solver downgraded Rocq 9.2→9.1.1 (accepted, pinned).

## Budget tracking
- Spend so far: ≈ $4.5 (probes, smokes, discarded control starts, control run).
- Wall-clock: on day 2 of 5. Comfortably on plan.

## Decisions / assumptions since last check-in
A7 updated (Rocq 9.1.1), A8 (proof-region discipline), A9 (miniF2F tier→bucket
mapping). Query sentences excluded from committed proofs (session semantics).
Efficiency metrics measured at parallel=4 for every config (fixed); scalability
axis varies N separately.

## Needs your input
_(empty — nothing blocking)_
