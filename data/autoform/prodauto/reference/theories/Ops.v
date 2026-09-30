(* Ops.v -- automaton constructions: the product automaton (states are      *)
(* pairs, so its state space has cardinality n*m) and the complement.        *)
From mathcomp Require Import all_ssreflect all_algebra.
From TaskLib Require Import Dfa.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* the product automaton runs both machines in lockstep; its state space is
   [SA * SB] with #|SA * SB| = #|SA| * #|SB| *)
Definition dprod (SA SB : finType) (A : dfa SA) (B : dfa SB)
  : dfa (SA * SB)%type :=
  Dfa (start A, start B)
      (fun s => final A s.1 && final B s.2)
      (fun s b => (trans A s.1 b, trans B s.2 b)).

(* the complement flips acceptance, keeping the structure *)
Definition dcompl (S : finType) (A : dfa S) : dfa S :=
  Dfa (start A) (fun s => ~~ final A s) (trans A).
