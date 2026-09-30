# Task: w2_triadic — the triadic chorus step

Build a fresh Rocq dune project (logical name `TaskLib`) formalizing the
*chorus* of a natural number, its *triad*, and the *triad step* — a small
divisor-combinatorics gadget with one fixed-point theorem and one shrinking
theorem. All names are this task's own; you are NOT asked for any named
textbook theorem.

**Every `.v` file must open with the heavy prelude**
`From mathcomp Require Import all_ssreflect all_algebra.`
(the tasks in this wave deliberately pay a real build cost). Extra imports
after it (e.g. `From Stdlib Require Import Lia.`,
`From mathcomp Require Import zify.`) are allowed in the project files.

Project shape: `dune-project` = `(lang dune 3.8)` + `(using coq 0.8)`;
`theories/dune` = `(coq.theory (name TaskLib)
(theories Stdlib mathcomp HB elpi elpi_elpi))`. Four `.v` files with a real
dependency chain: `Props.v <- Step.v <- Fixed.v` and `Step.v <- Shrink.v`.
No `Section` `Variable`s (the gate forbids `Variable`).

## The concepts

For `n : nat`:

- The **chorus** of `n` is the list of all divisors `d` of `n` with
  `0 < d < n`, in increasing order. (So `chorus 12 = [:: 1; 2; 3; 4; 6]`,
  `chorus 7 = [:: 1]`, `chorus 1 = [::]`.) Define it as the `%|`-filter of
  `iota 1 n.-1`.
- The **triad** of `n` is the list of the (at most) three largest chorus
  members, in decreasing order: `take 3 (rev (chorus n))`.
- The **triad step** `tstep n` is the sum (`sumn`) of the triad.

Two facts govern the step. First, it *fixes* the whole family `6 * m`
whenever `m` is odd, positive, and not a multiple of `5`: the three largest
chorus members of `6 * m` are then `3 * m`, `2 * m`, `m`, which sum back to
`6 * m`. Second, on any odd `n > 1` the step strictly *shrinks*: every
chorus member of an odd `n` has an odd cofactor `>= 3`, so the triad's
cofactors are at least `3`, `5`, `7`, and the sum stays below `n`.

## Required names (exact)

Props.v:
- `Props.chorus` : `nat -> seq nat`  (defined as
  `[seq d <- iota 1 n.-1 | d %| n]` — the probes `vm_compute` it)
- `Props.chorus_sorted` : `forall n, sorted ltn (chorus n)`
- `Props.mem_chorus` : `forall n d,
  (d \in chorus n) = (d %| n) && (0 < d) && (d < n)`
  (this exact boolean shape — the probes pin it)

Step.v:
- `Step.triad` : `nat -> seq nat`  (defined as `take 3 (rev (chorus n))`)
- `Step.tstep` : `nat -> nat`      (defined as `sumn (triad n)`)

Fixed.v (the meaty theorem):
- `Fixed.tstep_fixed` : `forall m,
  odd m -> ~~ (5 %| m) -> 0 < m -> tstep (6 * m) = 6 * m`

Shrink.v:
- `Shrink.tstep_shrink_odd` : `forall n, odd n -> 1 < n -> tstep n < n`

Helper lemmas with other names are welcome, but the names above must exist
with exactly these statements (up to the printed form of the binders).

`dune build` must pass; no admits/axioms. The probes compute concrete
`chorus`/`triad`/`tstep` values with `vm_compute`, so your definitions must
reduce (keep them plain `Definition`s over `iota`/`filter`/`rev`/`take`/
`sumn`, not opaque).
