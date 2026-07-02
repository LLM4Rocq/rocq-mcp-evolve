# Design rationale — an AI-native tooling layer for Rocq

Working doc. Every interface decision gets: the alternative considered, the
measured delta that justified it, and the config/ablation id that produced the
number. Decisions without numbers yet are marked [PENDING-MEASUREMENT].

## First-principles requirements (what an LLM agent actually needs)

Derived before building anything, to be validated/falsified by measurement:

1. **Feedback, not files.** A human watches a goal buffer evolve; an LLM pays
   tokens for every character it re-reads. The unit of feedback should be the
   *delta* caused by a command, rendered compactly, not the full buffer.
2. **Cheap backtracking.** LLM proof search is trial-heavy. If undo costs a full
   recompile, the agent is punished for exploring. Backtracking should be O(state
   swap), not O(replay).
3. **Errors as data.** Prover errors must arrive structured (location, kind,
   suggestion) so the policy can react without parsing prose.
4. **Batched hypotheses.** An LLM can propose k candidate tactics in one
   completion; a round-trip per candidate wastes latency and turns. The interface
   should accept a set and return which succeeded (first-success or all-results).
5. **Context is a budget.** Every tool result competes with the proof itself for
   context. Results need token budgets, truncation with explicit elision markers,
   and stable ids to re-fetch elided detail on demand.
6. **Parallelism is the norm.** Many agents will hammer the same prover install;
   session state must be isolated, cheap to create, and cheap to snapshot.

## Substrate decision

Link against installed Rocq 9.2 OCaml libraries (`rocq-runtime.*`), no source
changes to Rocq. The interaction core is built directly on the public vernac /
proof-engine API. [Baseline deliberately ignores all of the above requirements:
one `check(file)` tool, full `rocq compile` per call.]

## Interface iterations

(one section per kept/reverted change, with numbers — appended as measured)

### Profiling signal shaping the ladder (early, easy bucket, n=14)

Wall decomposition: prover 6%, model API ≈ 90%. Prover p50/call 266 ms (flat
`Require` replay), zero timeouts on easy. Failed-check taxonomy: syntax 128,
unknown_ref 43 — i.e. the policy burns whole turns (≈3.5 s + a full-file rewrite
of output tokens) discovering that one token was invalid Rocq. Input tokens grow
~330/turn (H2 confirmed in shape, small in absolute terms on easy).

Consequence: the metric that matters is **turns-to-solve and output tokens per
solve**, not raw prover seconds (revisit on medium/hard where timeout-ceiling
calls may dominate). The interface must convert each model turn into more prover
information: batched speculative execution, sentence-level persistence so partial
progress is never re-generated, errors that carry the failing sentence.

### Planned change ladder (each = one config, measured on dev60 vs predecessor)

1. `baseline` — control (naive whole-file check).
2. `session` — persistent in-process interpreter on rocq-runtime:
   sentence-level `step` (commit good prefix, report failing sentence
   structurally), O(1) `rollback` via Vernacstate snapshots, `state` rendering
   of open goals, per-sentence tactic timeout ≪ 60 s. Kills: whole-file
   re-generation (output tokens), whole-file re-compilation (prover ms), full
   context re-reads. [PENDING-MEASUREMENT]
3. `session+try` — `try {candidates:[...]}`: k tactic candidates from ONE
   completion, evaluated speculatively against the same snapshot in-process;
   returns per-candidate verdict + resulting-goal digest. Converts k model
   turns into 1. [PENDING-MEASUREMENT]
4. `+compact-state` — goal-delta rendering with token budgets + stable ids to
   re-fetch elided detail. [PENDING-MEASUREMENT]
5. `+search` — token-budgeted `Search`/`About` over the loaded environment,
   targeting the unknown_ref failure class. [PENDING-MEASUREMENT]

Order rationale: 2 unlocks 3-5 mechanically; 3 targets the measured dominant
cost (turns); 4 targets token growth; 5 targets the #2 error class.
