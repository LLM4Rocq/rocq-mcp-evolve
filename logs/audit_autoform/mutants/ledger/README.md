# Probe mutation analysis — task `ledger`

Method (3) of A130: for each mutant, a copy of `data/autoform/ledger/reference`
with one deliberate wrong-formalization change, repaired where needed so the
project *builds* (no admits/axioms), then run through the unmodified original
gate (`harness/autoform_gate.py`). Reference confirmed accepted first
(`solved: true`) before mutating. Mutant sources kept under
`/private/tmp/.../scratchpad/mut-ledger/<mutant>/` (not in the repo); gate
verdicts for the buildable mutants are saved alongside this file as
`<mutant>.json`.

9 mutants built; 7 were buildable and gate-tested, 2 were not buildable
(the change makes a required theorem genuinely false at some instance, so
no amount of proof-script repair can make the mutant build — itself
informative: it shows the required-theorem statements, as pinned, actually
force the correct formula in those spots). A third mutant, m8, was
originally logged here as "not buildable" by an earlier pass of this
analysis; on review its `_build`/verdict evidence shows it in fact builds
fine and was gate-tested (rejected at the probes layer by a statement-type
mismatch) — corrected below and moved into the non-survivors section.

## Survivors (probe gaps — the gate ACCEPTS a wrong formalization)

### m1_total_peraccount
- **Change**: `Entries.total` is redefined as the sum, over the *accounts*
  touched by the ledger, of the absolute value of each account's *net*
  balance (`sum_(a <- undup accounts) |bal a l|`) instead of the sum of
  `|delta|` per entry. This is a different notion ("net movement per
  account, summed" vs. spec's "total absolute movement" = turnover). On the
  probe's demo ledger `[(0,3);(1,-2);(0,5)]` every account's entries share
  one sign, so netting doesn't cancel anything and the two notions coincide:
  `|8| + |-2| = 10 = 3+2+5`.
- Repaired `Bounds.no_teleport` generically (still true: the bound sums
  nonnegative per-account terms including `|bal a l|` itself when `a`
  appears, and is 0 otherwise).
- **Buildable**: yes. **Gate**: `solved: true` (`m1_total_peraccount.json`).
- **Suggested probe to kill it**: add a ledger where an account's own entries
  net-cancel across accounts differently from raw turnover, e.g. two
  accounts each with one entry that partially offsets a shared magnitude —
  concretely, add
  ```
  Notation demo2 := [:: (0%N, 5); (0%N, -5); (1%N, 3)].
  Example p_total2 : Entries.total demo2 = 13.
  Proof. vm_compute; reflexivity. Qed.
  ```
  The correct `total` (turnover) is `5+5+3=13`; the per-account-net mutant
  gives `|0| + |3| = 3`, so this pin kills it.

### m2_total_hardcode_demo
- **Change**: `Entries.total` is special-cased to return the correct answer
  (10) exactly when its argument is the literal probe ledger
  `[(0,3);(1,-2);(0,5)]`, and on every other ledger doubles the correct total
  (`total0 l + total0 l`). A classic overfit-to-the-grader definition: it is
  provably wrong per spec ("sum of `|delta|`") on any ledger other than the
  one literal the grader happens to `vm_compute` against.
- Repaired `Bounds.no_teleport` by case-splitting on the same literal
  equality and falling back to the (still true, since doubling only grows
  the bound) correct inequality otherwise.
- **Buildable**: yes. **Gate**: `solved: true` (`m2_total_hardcode_demo.json`).
- **Suggested probe to kill it**: a second concrete `vm_compute` pin on any
  ledger other than the exact demo literal, e.g.
  ```
  Notation demo3 := [:: (0%N, 1)].
  Example p_total3 : Entries.total demo3 = 1.
  Proof. vm_compute; reflexivity. Qed.
  ```
  kills any mutant that special-cases only the one literal `demo` currently
  probed. More robustly: probe `total` on an ARBITRARY-shaped ledger built
  from `Random`/several small handwritten ledgers, since a hardcoded special
  case can only ever match finitely many literals.

## Non-survivors — the gate correctly REJECTS these

### m3_bal_const_zero (degenerate/trivial, category ii)
- **Change**: both `Entries.bal` and `Entries.total` collapsed to the
  constant `0`; `Balance.step` made a no-op to stay consistent (so
  `replay_bal`, `checkpoint_bal`, `swap_disjoint`, `no_teleport` are all
  trivially `0 = 0` / `0 <= 0`).
- **Buildable**: yes. **Gate**: `solved: false`, `probes_failed` — fails at
  `p_bal0` (`Entries.bal 0 demo = 8`; got `0`). The four concrete
  `vm_compute` semantic pins (`p_bal0`, `p_bal1`, `p_bal2`, `p_total`) do
  their job here: a fully degenerate formalization cannot survive them.
  (`m3_bal_const_zero.json`)

### m6_swap_disjoint_extra_hyp (weakened theorem, category iii)
- **Change**: `Balance.swap_disjoint` gains a spurious extra hypothesis
  (`e1.2 = e2.2`, equal deltas) alongside the required
  `e1.1 != e2.1`. The statement is still true (even easier to prove), but
  its *type* no longer matches the probe's exact universally-quantified
  statement.
- **Buildable**: yes (project builds fine standalone). **Gate**:
  `solved: false`, `probes_failed` at `p_swap` (probes.v:29) — Rocq reports
  a literal unification failure between the mutant's hypotheses-laden type
  and the required type. Statement-pinning (`exact Balance.swap_disjoint`)
  catches any weakening by extra hypothesis, confirming this pin is tight.
  (`m6_swap_disjoint_extra_hyp.json`)

### m7_no_teleport_extra_hyp (weakened theorem, category iii)
- **Change**: `Bounds.no_teleport` gains a spurious extra hypothesis
  (`l != [::]`, nonempty ledger) that isn't even needed (the empty case is
  `0 <= 0`, already trivial).
- **Buildable**: yes. **Gate**: `solved: false`, `probes_failed` at
  `p_no_teleport` (probes.v:42) — same statement-pinning catch as m6.
  (`m7_no_teleport_extra_hyp.json`)

### m8_checkpoint_swapped (different but similarly named notion, category iv)
- **Change**: `Replay.checkpoint_bal`'s checkpoint and suffix are
  transposed: `replay (replay zero_state suf) pre a = bal a (pre ++ suf)`
  instead of the required `replay (replay zero_state pre) suf a = bal a
  (pre ++ suf)` — i.e. it replays `pre` from the checkpoint reached after
  `suf`, backwards from what the name and required statement demand. This
  is numerically still true (`bal` is order-insensitive, so both sides
  reduce to the same value via `bal_cat` + `addrC`), so the mutant not only
  builds but proves cleanly with `by rewrite -replay_cat replay_bal bal_cat
  bal_cat addrC.`
- **Buildable**: yes (contrary to an earlier draft of this README, which
  mis-recorded this mutant as unbuildable; the saved `_build` evidence and
  gate verdict both show `layers.build: "ok"`).
- **Gate**: `solved: false`, `probes_failed` — Rocq reports a literal
  unification failure at `probes.v:38` between the mutant's transposed type
  and the required `forall pre suf a, replay (replay zero_state pre) suf a
  = bal a (pre ++ suf)` (`exact Replay.checkpoint_bal` fails to typecheck).
  So even though the *numeric content* of this mutant happens to coincide
  with the correct theorem, the probe's exact-statement pin (which names
  `pre`/`suf` in a fixed order) still catches the argument-order swap.
  (`m8_checkpoint_swapped.json`)

### m9_bal_le_compare (wrong comparison direction, category i)
- **Change**: `Entries.bal`'s per-entry match test is changed from
  `e.1 == a` to `(e.1 <= a)%N` — every entry whose account is *at most* `a`
  counts toward `a`'s balance, not just entries on account `a` exactly.
  `Balance.step` changed identically to stay consistent, and
  `Bounds.no_teleport`'s case split adjusted accordingly, so the mutant
  still builds and proves all the generic theorems (the argument doesn't
  care which boolean predicate selects entries).
- **Buildable**: yes. **Gate**: `solved: false`, `probes_failed` at
  `p_bal1` (`Entries.bal 1 demo = -2`; got `6`, since with `<=` account 1
  also picks up both of account 0's entries: `3 - 2 + 5 = 6`). The demo
  ledger's multiple distinct accounts are enough to catch a comparison-
  direction slip. (`m9_bal_le_compare.json`)

## Not buildable (the required generic theorems force the correct formula)

### m4_zero_state_nonzero
- **Change**: `Balance.zero_state := fun _ => 5` instead of `fun _ => 0`
  (wrong neutral element).
- **Why unbuildable**: `replay_bal : forall l a, replay zero_state l a = bal
  a l` forces, at `l = [::]`, `zero_state a = bal a [::] = 0` for every `a`
  — i.e. the theorem's very shape pins `zero_state` to the all-zero
  function. `add0r` no longer applies once the base case is `5 + bal a l =
  bal a l`, which is false in general; `dune build` fails on `Balance.v`
  (`replay_bal`) with "The LHS of add0r ... does not match any subterm",
  and downstream `Replay.v` also fails to build.
  **gate_reason**: statement-forced — the required generic theorem makes
  the wrong neutral element unprovable, so no gate run was needed.

### m5_step_wrong_sign
- **Change**: `Balance.step` subtracts the entry's delta on a match instead
  of adding it (`s a - (if e.1 == a then e.2 else 0)`).
- **Why unbuildable**: same forcing as m4, but through the inductive step:
  `replay_bal` (and the auxiliary `replayE`) require `step`'s effect on a
  match to be `+ e.2`, matching `Entries.bal`'s (separately pinned by the
  concrete `p_bal*`/`p_total` probes) additive recursion. With subtraction,
  `replay zero_state l a = -(bal a l)` in general, not `bal a l`; the
  original proof script fails ("No applicable tactic") and cannot be
  repaired without also changing `bal`'s sign — which would break the
  concrete vm_compute pins instead. **gate_reason**: statement-forced.

(m8_checkpoint_swapped was originally listed here as unbuildable; corrected
above under "Non-survivors" — it builds and is gate-tested.)

## Summary

Of 9 mutants, 2 are confirmed probe gaps (**m1_total_peraccount**,
**m2_total_hardcode_demo**) — both are wrong/overfit definitions of
`Entries.total` that happen to reproduce the single `vm_compute`-pinned
value (10) on the one demo ledger the probes exercise. The four required
*theorem* pins (`p_replay_bal`, `p_swap`, `p_replay_cat`/`p_checkpoint`,
`p_no_teleport`) are tight against weakening by extra hypotheses (m6, m7)
and against argument-order/comparison slips (m8, m9, and the genuinely
unbuildable m4/m5, where the required theorem's very shape forces the
correct neutral element and step sign). The one soft spot across both
survivors is the same: `total`'s correctness is asserted by exactly one
concrete number on exactly one ledger, so any definition (correct or not)
that reproduces `10` on `[(0,3);(1,-2);(0,5)]` passes, whether or not it
computes the spec's actual quantity elsewhere.

## Verification

Independent re-check of both survivors against `spec.md`'s stated meaning
of `Entries.total` ("the total absolute movement, sum of `|delta|`") and
against the saved gate verdicts, plus a killing probe for each, compiled
with `rocq compile -Q <built theories> TaskLib <probe>.v` against sandbox
builds of the reference (`.../scratchpad/verify-mut-ledger/ref`) and of
each mutant (`.../scratchpad/verify-mut-ledger/m1`,
`.../scratchpad/verify-mut-ledger/m2`, copied from
`.../scratchpad/mut-ledger/<name>`, rebuilt fresh with
`dune build --root .`).

### Classification

| mutant | verdict JSON | classification | reason |
| --- | --- | --- | --- |
| m1_total_peraccount | `m1_total_peraccount.json`: `"solved": true`, all layers `ok`/`closed` | **GENUINE** | `Entries.v` (`.../scratchpad/mut-ledger/m1_total_peraccount/theories/Entries.v`) redefines `total` as `sum_(a <- undup accounts) |bal a l|` (sum of per-account *net* absolute balances), not spec's `total l` = "sum of `|delta|` per entry" (turnover). These are different functions of `ledger -> int` that happen to agree at the one literal `demo` the probes pin (`|8|+|-2|=10=3+2+5`) because no account's entries offset within that literal. A ledger where one account's entries offset (e.g. `[(0,5);(0,-5);(1,3)]`, net total `3` vs. turnover `13`) separates them, confirming the divergence is real, not an artifact of the mutant description. |
| m2_total_hardcode_demo | `m2_total_hardcode_demo.json`: `"solved": true`, all layers `ok`/`closed` | **GENUINE** | `Entries.v` (`.../scratchpad/mut-ledger/m2_total_hardcode_demo/theories/Entries.v`) literally special-cases `total` on `l == [:: (0,3); (1,-2); (0,5)]` (returns hardcoded `10`) and returns `total0 l + total0 l` (double the correct value) on every other ledger — read directly from the source, matching the mutant description exactly. This is a definition that is provably wrong per spec on all but one literal input; the gate accepted it (`solved: true`) purely because the only `vm_compute` pin on `total` happens to use that literal. |

Both survivors' source diffs were read directly (not just inferred from the
description) and match the README's stated changes verbatim; both verdict
JSONs show `"solved": true` with every layer `ok`/`closed`; both are
confirmed **not** mislabeled. Neither mutant's changed behavior is
permitted by `spec.md`, which pins `total` to one specific fixed-point
recursion (`match l with [::] => 0 | e :: t => |e.2| + total t end`,
i.e. "sum of `|delta|`"), so both are genuine probe gaps, not
spec-permitted freedom (the spec gives `total` no leeway: it is not
described as "any measure of ledger activity", only as this exact sum).

### Checked killing probes

Both probes use only required names (`Entries.total`), in the style of
`probes.v` (a `Notation` for the concrete ledger plus an `Example` with a
`vm_compute; reflexivity` proof).

```coq
(* kills m1_total_peraccount: two entries on account 0 net-cancel (5+-5=0),
   so the per-account-net total (|0|+|3| = 3) diverges from the correct
   turnover total (|5|+|-5|+|3| = 13). *)
Notation demo2 := [:: (0%N, 5); (0%N, -5); (1%N, 3)].
Example p_total2 : Entries.total demo2 = 13.
Proof. vm_compute; reflexivity. Qed.
```

```coq
(* kills m2_total_hardcode_demo: any ledger other than the exact demo
   literal; correct turnover on a single (0,1) entry is 1, the hardcode
   mutant's doubling fallback gives 2 on any non-demo ledger. *)
Notation demo3 := [:: (0%N, 1)].
Example p_total3 : Entries.total demo3 = 1.
Proof. vm_compute; reflexivity. Qed.
```

Compile results (rocq 9.1.1 / mathcomp 2.5.0, from
`.../scratchpad/verify-mut-ledger/`, `Q` mapped to each sandbox's
`_build/default/theories`):

| probe | vs. `ref` (reference) | vs. `m1_total_peraccount` | vs. `m2_total_hardcode_demo` |
| --- | --- | --- | --- |
| `p_total2` (kills m1) | compiles, `Qed` succeeds | **fails**: `Error: Unable to unify "13%Z" with "3%Z"` | **fails**: `Error: Unable to unify "13%Z" with "26%Z"` (also kills m2) |
| `p_total3` (kills m2) | compiles, `Qed` succeeds | compiles, `Qed` succeeds (m1's per-account-net formula happens to equal turnover on a single-entry, single-account ledger, so this probe alone does not distinguish m1 from the reference) | **fails**: `Error: Unable to unify "1%Z" with "2%Z"` |

Both probes pass against the reference and fail (statement mismatch at
`vm_compute`) against their target mutant, as required. `p_total2` turns
out to be the stronger of the two — it independently kills both survivors
— while `p_total3` kills only m2 (m1's error is specifically about
cross-account net-cancellation, which a single-account ledger cannot
exercise). Adding `p_total2` (or an equivalent second-ledger `total` pin)
to `probes.v` would close both gaps found by this analysis.
