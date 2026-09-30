# Task: prodauto — product automaton and its language

Build a fresh Rocq dune project (logical name `TaskLib`) formalizing
deterministic finite automata (DFAs) over the alphabet `bool`, the product
construction, the complement, and three properties: the language of the
product is the intersection, an emptiness decision via bounded reachability,
and a pumping-light pigeonhole fact. No named textbook theorem is asked; the
composition (product + emptiness + pigeonhole) is the novelty.

**Every `.v` file must open with the heavy prelude**
`From mathcomp Require Import all_ssreflect all_algebra.`
Work over mathcomp finite types (`finType`) and use `'I_n` (ordinals) for the
concrete instances. NO `Section` `Variable`s (the gate forbids `Variable`);
quantify explicitly, and make each definition/lemma take its automata as
arguments.

Project shape: `dune-project` = `(lang dune 3.8)` + `(using coq 0.8)`;
`theories/dune` = `(coq.theory (name TaskLib)
(theories Stdlib mathcomp HB elpi elpi_elpi))`. Six `.v` files with a real
dependency chain: `Dfa.v <- Ops.v <- Lang.v <- Main.v`, plus `Empty.v` and
`Pump.v` depending on `Dfa.v` (and `Main.v` also on `Empty.v`).

## The model

A **DFA** is a record over a finite state space `S : finType`: a `start`
state, a `final : S -> bool` acceptance predicate, and a transition
`trans : S -> bool -> S`. The `run` is the state reached by folding `trans`
from `start` over the word; `accepts A w := final A (run A w)`.

The **product** `dprod A B` has state space `(SA * SB)%type` (so
`#|SA * SB| = #|SA| * #|SB|`), runs both machines in lockstep, and accepts
iff both do. The **complement** `dcompl A` flips `final`.

Emptiness is decided by **bounded reachability**: the reachable set is the
reflexive-transitive closure (`connect`) of the one-letter step relation over
the finite state space, and `nonemptyb A` tests whether any final state is
reachable.

## Required names (exact)

Dfa.v:
- `Dfa.dfa` : `finType -> Type`   (a record with constructor `Dfa` and
  fields `start`, `final`, `trans`)
- `Dfa.run` : `forall S, dfa S -> seq bool -> S`
- `Dfa.accepts` : `forall S, dfa S -> seq bool -> bool`

Ops.v:
- `Ops.dprod` : `forall SA SB, dfa SA -> dfa SB -> dfa (SA * SB)%type`
- `Ops.dcompl` : `forall S, dfa S -> dfa S`

Lang.v:
- `Lang.accepts_prod` : `forall SA SB (A : dfa SA) (B : dfa SB) w,
    accepts (dprod A B) w = accepts A w && accepts B w`
- `Lang.accepts_prodP` : `forall SA SB (A : dfa SA) (B : dfa SB) w,
    accepts (dprod A B) w <-> accepts A w /\ accepts B w`
    (the language-intersection theorem)
- `Lang.accepts_compl` : `forall S (A : dfa S) w,
    accepts (dcompl A) w = ~~ accepts A w`

Empty.v:
- `Empty.dstep` : `forall S, dfa S -> rel S`   (one-letter reachability)
- `Empty.reachable` : `forall S, dfa S -> {set S}`
- `Empty.nonemptyb` : `forall S, dfa S -> bool`
- `Empty.nonemptyP` : `forall S (A : dfa S),
    reflect (exists w, accepts A w) (nonemptyb A)`
    (correctness of the emptiness decision — the meaty proof; link the
     graph closure `connect` to word-runs in both directions)

Pump.v:
- `Pump.trace` : `forall S, dfa S -> seq bool -> seq S`
    (the states visited, start included)
- `Pump.accepts_long_dup` : `forall S (A : dfa S) w,
    #|S| < size w -> ~~ uniq (trace A w)`
    (pigeonhole: a word longer than the state count revisits a state)

Main.v (concrete instances over ordinals; use explicit `Ordinal` constants
so `accepts` reduces under `vm_compute` — do NOT use `inord`, it blocks
computation):
- `Main.parity` : `dfa 'I_2`   (even number of `true`s)
- `Main.mod3` : `dfa 'I_3`   (number of `true`s divisible by 3)
- `Main.prod23` : `dfa ('I_2 * 'I_3)%type`   (`dprod parity mod3`)
- `Main.prod23_nonempty` : `nonemptyb prod23`

`dune build` must pass; no admits/axioms. The assumption audit must be
closed with NO axioms (everything here is constructive). The probes compute
`accepts` on concrete words with `vm_compute`, so the concrete instances
must reduce.
