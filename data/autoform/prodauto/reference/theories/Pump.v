(* Pump.v -- pumping-light: a word longer than the state count drives the   *)
(* run through some state twice (pigeonhole over the finite state space).    *)
From mathcomp Require Import all_ssreflect all_algebra.
From TaskLib Require Import Dfa.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* the full trace of states visited, start state included *)
Definition trace (S : finType) (A : dfa S) (w : seq bool) : seq S :=
  start A :: scanl (trans A) (start A) w.

(* a duplicate-free sequence over a finType is no longer than the finType *)
Lemma seq_card (T : finType) (s : seq T) : uniq s -> size s <= #|T|.
Proof.
move=> u; rewrite cardE; apply: uniq_leq_size => // x _; exact: mem_enum.
Qed.

(* pigeonhole: a word strictly longer than #|S| repeats a state *)
Theorem accepts_long_dup (S : finType) (A : dfa S) w :
  #|S| < size w -> ~~ uniq (trace A w).
Proof.
move=> hw; apply/negP => /seq_card.
rewrite /trace /= size_scanl => h.
by move: (leq_ltn_trans h hw); rewrite ltnNge leqnSn.
Qed.

(* the trace has the expected length and ends at the run's final state *)
Lemma size_trace (S : finType) (A : dfa S) w :
  size (trace A w) = (size w).+1.
Proof. by rewrite /trace /= size_scanl. Qed.

Lemma last_scanl (T U : Type) (f : T -> U -> T) x s :
  last x (scanl f x s) = foldl f x s.
Proof. by elim: s x => [|a s IH] x //=; rewrite IH. Qed.

Lemma last_trace (S : finType) (A : dfa S) w :
  last (start A) (trace A w) = run A w.
Proof. by rewrite /trace /run /= last_scanl. Qed.
