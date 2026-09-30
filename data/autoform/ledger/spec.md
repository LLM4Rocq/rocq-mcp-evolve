# Task: ledger — an append-only ledger with replay integrity

Build a fresh Rocq dune project (logical name `TaskLib`) formalizing a small
append-only ledger and its replay semantics over the signed integers. This is
a novel, systems-flavored specification: no named textbook theorem is asked,
only the definitions and four integrity properties.

**Every `.v` file must open with the heavy prelude**
```
From mathcomp Require Import all_ssreflect all_algebra.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.
```
Deltas and balances are mathcomp `int` (signed integers, from ssrint, which
`all_algebra` re-exports). Absolute values use the ring norm `` `|_| ``.
NO `Section` `Variable`s (the gate forbids `Variable`).

Project shape: `dune-project` = `(lang dune 3.8)` + `(using coq 0.8)`;
`theories/dune` = `(coq.theory (name TaskLib)
(theories Stdlib mathcomp HB elpi elpi_elpi))`. Four `.v` files with a real
dependency chain: `Entries.v <- Balance.v <- Replay.v`, and `Bounds.v`
depending on `Entries.v`.

## The model

- An **entry** is a `(account, delta)` pair `(nat * int)`; a **ledger** is a
  `seq entry` (append-only: new entries are consed/appended, never edited).
- **bal a l** : the balance of account `a` after the ledger `l`, i.e. the
  sum of the deltas of the entries whose account is `a` (define as a
  `Fixpoint` that reduces under `vm_compute`).
- **total l** : the total absolute movement `sum of |delta|` (also a
  reducing `Fixpoint`).
- A **state** (snapshot) is `nat -> int`; **zero_state** is the all-zero
  snapshot; **step s e** applies one entry to a snapshot (adds `e`'s delta to
  `e`'s account); **replay s l** folds `step` over the ledger (`foldl`).

## Required names (exact)

Entries.v:
- `Entries.entry` := `(nat * int)%type`
- `Entries.ledger` := `seq entry`
- `Entries.bal` : `nat -> ledger -> int`
- `Entries.total` : `ledger -> int`

Balance.v:
- `Balance.state` := `nat -> int`
- `Balance.zero_state` : `state`
- `Balance.step` : `state -> entry -> state`
- `Balance.replay` : `state -> ledger -> state`   (`foldl step`)
- `Balance.replay_bal` : `forall l a, replay zero_state l a = bal a l`
- `Balance.swap_disjoint` : `forall s e1 e2, e1.1 != e2.1 ->
    step (step s e1) e2 =1 step (step s e2) e1`
    (disjoint-account entries commute; `=1` is pointwise state equality)

Replay.v:
- `Replay.replay_cat` : `forall s pre suf,
    replay s (pre ++ suf) = replay (replay s pre) suf`
- `Replay.checkpoint_bal` : `forall pre suf a,
    replay (replay zero_state pre) suf a = bal a (pre ++ suf)`
    (checkpoint-replay equivalence: replaying the suffix from the checkpoint
     reached after `pre` equals a full replay)

Bounds.v:
- `Bounds.no_teleport` : `forall a l, `|bal a l| <= total l`
    (no account moves by more than the total absolute movement — this is the
     meaty proof; induct on the ledger using the triangle inequality)

`dune build` must pass; no admits/axioms. The probes compute `bal`/`total`
on a concrete ledger with `vm_compute`, so those definitions must reduce.
