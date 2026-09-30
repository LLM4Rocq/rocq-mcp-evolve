(* Dfa.v -- deterministic finite automata over the alphabet [bool], with    *)
(* an arbitrary finite state space, and their run/accept semantics.          *)
From mathcomp Require Import all_ssreflect all_algebra.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* a DFA: a start state, an acceptance predicate, and a transition function *)
Record dfa (S : finType) := Dfa {
  start : S;
  final : S -> bool;
  trans : S -> bool -> S }.
Arguments Dfa {S}.

(* the state reached after reading the whole word *)
Definition run (S : finType) (A : dfa S) (w : seq bool) : S :=
  foldl (trans A) (start A) w.

(* the word is accepted iff the run ends in a final state *)
Definition accepts (S : finType) (A : dfa S) (w : seq bool) : bool :=
  final A (run A w).
