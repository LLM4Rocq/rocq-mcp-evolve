# Probe mutation analysis — prodauto (method 3 of A130)

Reference build/gate check: reference is BUILDABLE and the original gate
accepts it (`"solved": true`, all layers ok, `n_probes: 11`), confirming the
baseline before mutating. Mutant sources live under
`/private/tmp/claude-501/-Users-gbaudart-Project-llm4rocq-rocq-tools/92fd7af9-6dfb-42f7-ad3c-3a89b1b13ece/scratchpad/mut-prodauto/<mutant>/`
(not committed to the repo). Each verdict below is the *original*
`harness/autoform_gate.py` run against that mutant, in isolation, saved to
`<mutant>.json` next to this file (build/probe error text truncated where
very long — full mathcomp coercion-ambiguity warning noise elided).

## Survivors — probe gaps (gate ACCEPTS a wrong formalization)

### 1. `mod3_saturating`
- **Change**: `Main.mod3` is redefined to accept once the count of `true`s
  reaches **3 and saturates there** ("at least 3 trues"), instead of
  "count is a multiple of 3". Uses the same 3 states, same type
  `dfa 'I_3`, transitions `c0->c1->c2->c2` (sticks at `c2`) with
  `final := (s == c2)`.
- **Buildable**: yes.
- **Gate reason**: `"solved": true` — full accept.
- **Why it survives**: every probe that touches `mod3`
  (`p_acc_mod3`, and via `prod23` `p_acc_prod3`, `p_acc_prod6`) only ever
  evaluates the automaton at exactly 3 or 6 `true`s, both of which are
  `>= 3` and hence indistinguishable from "divisible by 3" under this
  mutant. No probe checks a count in `{1,2,4,5}` (all of which the two
  notions disagree on) or checks `mod3`/`prod23` in isolation away from
  count-3/6.
- **Suggested probe to kill it** (statement only; probes.v not modified):
  ```
  Example p_acc_mod3_four :
    Dfa.accepts Main.mod3 [:: true; true; true; true] = false.
  Proof. vm_compute; reflexivity. Qed.
  ```
  (4 trues is not a multiple of 3, but is "at least 3"; the reference
  proves `false`, the mutant proves `true`.)

### 2. `parity_ignores_symbol`
- **Change**: `Main.parity`'s transition toggles the state on **every**
  letter, `true` or `false` (`fun s b => if s == p0 then p1 else p0`,
  dropping the `if b then ... else s` guard), instead of leaving the state
  unchanged on `false`.
- **Buildable**: yes.
- **Gate reason**: `"solved": true` — full accept.
- **Why it survives**: every probe word for `parity`, `mod3`, and
  `prod23` in probes.v and in the reference's own `Main.v` lemmas is a
  sequence of `true`s only (`[:: true; true]`, `[:: true;true;true]`,
  6×`true`). `false` never appears in any pinned word, so a DFA that
  mishandles the `false` letter entirely is behaviorally identical to the
  correct one on every tested input. This is a structural gap in the whole
  task, not specific to `parity` (the same trick would work on `mod3` or
  `prod23` directly).
- **Suggested probe to kill it**:
  ```
  Example p_acc_parity_false_noop :
    Dfa.accepts Main.parity [:: true; false; true] = true.
  Proof. vm_compute; reflexivity. Qed.
  ```
  (two `true`s with a `false` in between: correct automaton stays even
  parity = accept; the mutant toggles 3 times = reject.)

### 3. `trace_no_start`
- **Change**: `Pump.trace` is redefined to **omit the start state**
  (`scanl (trans A) (start A) w` with no `start A ::` prefix), contradicting
  the spec's explicit "the states visited, start included".
- **Buildable**: yes, with a trivial proof adaptation (drop the `+1`/`.+1`
  offsets that came from the head cons).
- **Gate reason**: `"solved": true` — full accept.
- **Why it survives**: `Pump.accepts_long_dup` is pinned only by its
  *type* (`#|S| < size w -> ~~ uniq (trace A w)`), which is a purely
  cardinality/pigeonhole fact independent of whether the start state is
  included in the list — a duplicate-free sequence over a finite type of
  size `n` still can't exceed length `n` whether or not you prepend one
  more element. No probe inspects `trace`'s actual contents or its
  relationship to `run`/order of states.
- **Suggested probe to kill it**:
  ```
  Example p_trace_head :
    forall (S : mathcomp.ssreflect.fintype.finType) (A : Dfa.dfa S) w,
    head (Dfa.start A) (Pump.trace A w) = Dfa.start A.
  Proof. by []. Qed.
  ```
  (fails to typecheck/reduce against `trace_no_start`, where the head of
  `trace A w` is generally the first *visited* state, not `start A`.)

### 4. `trace_dup_degenerate`
- **Change**: `Pump.trace` is redefined to list the start state **twice**
  at the head (`start A :: start A :: scanl ...`), which trivializes the
  pigeonhole theorem: the list is never unique regardless of the word, so
  `accepts_long_dup`'s hypothesis (`#|S| < size w`) becomes irrelevant —
  the proof no longer certifies any real revisit-argument about the run.
- **Buildable**: yes — the proof is a one-liner (`~~ uniq (a::a::_)`
  follows immediately from `a \in a::_`), *not needing the hypothesis at
  all*.
- **Gate reason**: `"solved": true` — full accept.
- **Why it survives**: same as #3 — the theorem's exact type only pins a
  logical implication, not that `trace` faithfully mirrors the run, and
  degenerate content that makes the implication trivially/vacuously true
  is not distinguished from a real pigeonhole proof by any probe.
- **Suggested probe to kill it**:
  ```
  Example p_trace_size :
    forall (S : mathcomp.ssreflect.fintype.finType) (A : Dfa.dfa S) w,
    size (Pump.trace A w) = (size w).+1.
  Proof. by []. Qed.
  ```
  (reference: exactly `size w + 1`; `trace_dup_degenerate` gives
  `size w + 2`.)

## Rejected mutants (not buildable, or caught by probes) — negative controls

### 5. `dprod_union`
- **Change**: `Ops.dprod`'s `final` uses `||` (union) instead of `&&`
  (intersection): `fun s => final A s.1 || final B s.2`.
- **Buildable**: **no**. The reference `Lang.v` (shipped inside every
  submission, not the probes file) states `accepts_prod` with the exact
  RHS `accepts A w && accepts B w`; with the real behavior now `||`, that
  in-project theorem is false and `by rewrite /accepts run_prod` fails
  (`Error: No applicable tactic.`).
- **Gate reason**: `build_failed` (first error at `Lang.v:22`,
  `accepts_prod`/`accepts_prodP`).
- Confirms: the exact required-statement pin on `Lang.accepts_prod` /
  `accepts_prodP` (not just the probe) forces the intersection semantics —
  a union-composition mutant cannot even be made to build correctly.

### 6. `dcompl_identity`
- **Change**: `Ops.dcompl` doesn't flip `final` at all
  (`Dfa (start A) (final A) (trans A)`), i.e. it's the identity.
- **Buildable**: **no**. `Lang.accepts_compl`'s exact statement
  (`accepts (dcompl A) w = ~~ accepts A w`) is then false in general;
  `Proof. by []. Qed.` fails.
- **Gate reason**: `build_failed`.
- Confirms: `Lang.accepts_compl`'s exact-statement pin genuinely forces
  correct complementation.

### 7. `nonemptyb_always_true`
- **Change**: `Empty.nonemptyb A := true` unconditionally (degenerate
  constant decider), ignoring the automaton.
- **Buildable**: **no**. `Empty.nonemptyP` is universally quantified over
  *every* `dfa S`, including ones whose language is empty (e.g. `final`
  always `false`), so `reflect (exists w, accepts A w) true` is false in
  general; no proof exists (attempted `exact/(iffP idP) => // _; exists
  [::]; exact: erefl` fails with `Error: No applicable tactic.` — a real
  type error, not `admit`/`Admitted`/`Axiom`).
- **Gate reason**: `build_failed`.
- Confirms: because `nonemptyP` (unlike the `Main.v`-specific instance
  lemma) is stated generically over all automata, a constant "always
  nonempty" cheat cannot be pushed through even though the *concrete*
  probe `p_nonempty23` alone would have accepted it.

### 8. `accepts_prod_extra_hyp`
- **Change**: `Lang.accepts_prod` gains a spurious extra hypothesis
  `0 < size w -> ...` (true statement, over-qualified/weakened type).
- **Buildable**: yes, on its own.
- **Gate reason**: `probes_failed` — probes.v's `p_lang_b` does
  `Proof. exact Lang.accepts_prod. Qed.` against the exact required type
  (no hypothesis); Rocq reports
  `The term "accepts_prod" has type ... 0 < size w -> ... while it is
  expected to have type ...` and cannot unify.
- Confirms: the probes' `exact <name>` statement-shape pins do catch a
  weakened-by-extra-hypothesis theorem, as intended.

### 9. `dstep_forall`
- **Change**: `Empty.dstep` uses `[forall b, trans A s b == t]`
  (both letters must land on `t`) instead of
  `[exists b, trans A s b == t]` (one-letter reachability via *some*
  letter).
- **Buildable**: **no**. The existing `path_run`/`connect_run` proofs in
  `Empty.v` rely on `existsP` to extract a witness letter driving each
  step; with `forall` the needed witness-extraction step doesn't apply,
  and the reachability relation itself no longer matches actual
  one-letter transitions, so the file fails to compile.
- **Gate reason**: `build_failed`.
- Confirms: `Empty.dstep`'s required shape (`forall S, dfa S -> rel S`)
  combined with `Empty.nonemptyP`'s exact-statement pin does force the
  `exists`-quantified (not `forall`-quantified) step relation.

## Summary

| mutant | category | buildable | gate verdict | survivor? |
|---|---|---|---|---|
| mod3_saturating | (i) wrong def, untested inputs | yes | solved | **yes** |
| parity_ignores_symbol | (i) wrong def, untested inputs | yes | solved | **yes** |
| trace_no_start | (v) spec detail not pinned | yes | solved | **yes** |
| trace_dup_degenerate | (ii) degenerate/trivial | yes | solved | **yes** |
| dprod_union | (iv) different notion | no | build_failed | no |
| dcompl_identity | (ii) degenerate | no | build_failed | no |
| nonemptyb_always_true | (ii) degenerate | no | build_failed | no |
| accepts_prod_extra_hyp | (iii) weakened theorem | yes | probes_failed | no |
| dstep_forall | (i) wrong def | no | build_failed | no |

4 of 9 mutants (mod3_saturating, parity_ignores_symbol, trace_no_start,
trace_dup_degenerate) are genuine probe gaps: plausible wrong
formalizations that a careless/adversarial agent could produce, which the
current `probes.v` accepts as fully solved. Common root cause for three of
the four: **no probe word ever contains a `false` letter**, and **no probe
ever inspects `Pump.trace`'s content** (only the abstract pigeonhole
implication it must satisfy) — both are blind spots orthogonal to the
5 rejected mutants, which show the exact-statement pins on `Lang.v` and
`Empty.v`'s required theorems are otherwise doing real work.

## Verification

Independent check (label `verify-mut:prodauto`) of the 4 reported
survivors. For each: read `spec.md`'s "Required names (exact)" section and
its prose semantics for `Main.parity`/`Main.mod3`/`Pump.trace`; confirmed
the JSON verdict actually shows `"solved": true` with all layers `ok`;
diffed the mutant source (under
`/private/tmp/claude-501/-Users-gbaudart-Project-llm4rocq-rocq-tools/92fd7af9-6dfb-42f7-ad3c-3a89b1b13ece/scratchpad/mut-prodauto/<name>/`)
against the reference to confirm the described change is what the source
actually does; wrote a killing probe (required names only, `probes.v`
style) for each; checked every probe **passes** against a fresh sandbox
`dune build --root .` of the reference
(`/private/tmp/claude-501/-Users-gbaudart-Project-llm4rocq-rocq-tools/92fd7af9-6dfb-42f7-ad3c-3a89b1b13ece/scratchpad/verify-mut-prodauto/ref`)
and **fails** against a sandbox rebuild of the corresponding mutant.

### Classification table

| mutant | verdict | reason |
|---|---|---|
| `mod3_saturating` | **GENUINE** | spec.md states `Main.mod3` accepts iff the count of `true`s "is a multiple of 3"; the mutant's saturating ("at least 3") counter contradicts this stated meaning of a required concrete instance. Diff of `Main.v` confirms the mutant only changes `final`/`trans` on `mod3` as described (`c1->c2->c2` instead of `c1->c2->c0`, `final := s==c2`); verdict JSON shows `"solved": true`, all layers `ok`. |
| `parity_ignores_symbol` | **GENUINE** | spec.md states `Main.parity` accepts on "even number of `true`s", which by construction requires `false` letters to leave the state unchanged (only `true`s are counted). The mutant's transition toggles on every letter, contradicting this. Diff confirms the described change (drops the `if b then ... else s` guard); verdict JSON shows `"solved": true`, all layers `ok`. |
| `trace_no_start` | **GENUINE** | spec.md's Required-names section states `Pump.trace` is "the states visited, start included" — explicit, unambiguous text. The mutant drops the `start A ::` head, directly contradicting it. Diff confirms; verdict JSON shows `"solved": true`, all layers `ok`. |
| `trace_dup_degenerate` | **GENUINE** | Same spec text ("the states visited, start included") requires `trace` to faithfully list each state visited once; duplicating the start state at the head is not "the states visited" (the start state is visited once, not twice) and trivializes `accepts_long_dup`'s hypothesis. Diff confirms `start A :: start A :: scanl ...`; verdict JSON shows `"solved": true`, all layers `ok`. |

All 4 reported survivors confirmed genuine probe gaps; none reclassified as
spec-permitted or mislabeled.

### Checked killing probes

```coq
(* kills mod3_saturating: 4 trues is not a multiple of 3, but is >= 3 *)
Example p_acc_mod3_four :
  Dfa.accepts Main.mod3 [:: true; true; true; true] = false.
Proof. vm_compute; reflexivity. Qed.

(* kills parity_ignores_symbol: a `false` letter must not flip parity *)
Example p_acc_parity_false_noop :
  Dfa.accepts Main.parity [:: true; false; true] = true.
Proof. vm_compute; reflexivity. Qed.

(* kills trace_no_start: trace's head must be the start state *)
Example p_trace_head :
  forall (S : finType) (A : Dfa.dfa S) w,
    head (Dfa.start A) (Pump.trace A w) = Dfa.start A.
Proof. by move=> S A w; rewrite /Pump.trace /=. Qed.

(* kills trace_dup_degenerate: trace has exactly size w + 1 entries *)
Example p_trace_size :
  forall (S : finType) (A : Dfa.dfa S) w,
    size (Pump.trace A w) = (size w).+1.
Proof. by move=> S A w; rewrite /Pump.trace /= size_scanl. Qed.
```

Verified: all four probes compile and prove against a fresh sandbox
`dune build --root .` of the reference (combined in one file,
`killing_probes.v`, `rocq compile -Q <ref theory dir> TaskLib
killing_probes.v` exits 0, `.vo` produced). Verified separately, each
probe fails to compile against a fresh sandbox rebuild of its own mutant:

| probe | against mutant | result |
|---|---|---|
| `p_acc_mod3_four` | `mod3_saturating` | `Error: Unable to unify "false" with "true".` |
| `p_acc_parity_false_noop` | `parity_ignores_symbol` | `Error: Unable to unify "true" with "false".` |
| `p_trace_head` | `trace_no_start` | `Error: No applicable tactic.` |
| `p_trace_size` | `trace_dup_degenerate` | `Error: No applicable tactic.` |
