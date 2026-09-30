(* Empty.v -- emptiness via bounded reachability: the reachable set is the  *)
(* reflexive-transitive closure of the one-letter step relation over the     *)
(* finite state space, and a final state is reachable iff a word is accepted.*)
From mathcomp Require Import all_ssreflect all_algebra.
From TaskLib Require Import Dfa.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* one-letter reachability *)
Definition dstep (S : finType) (A : dfa S) : rel S :=
  fun s t => [exists b, trans A s b == t].

(* states reachable from the start (bounded: connect over a finType only
   explores paths of length < #|S|) *)
Definition reachable (S : finType) (A : dfa S) : {set S} :=
  [set t | connect (dstep A) (start A) t].

(* the emptiness decision: is any final state reachable? *)
Definition nonemptyb (S : finType) (A : dfa S) : bool :=
  [exists t, (t \in reachable A) && final A t].

(* a step-path yields a word that drives the run along it *)
Lemma path_run (S : finType) (A : dfa S) p s :
  path (dstep A) s p -> exists w, foldl (trans A) s w = last s p.
Proof.
elim: p s => [|t' p' IH] s /=; first by exists [::].
move=> /andP[/existsP[b /eqP hb] pth].
have [w' hw'] := IH t' pth.
by exists (b :: w'); rewrite /= hb hw'.
Qed.

Lemma connect_run (S : finType) (A : dfa S) t :
  connect (dstep A) (start A) t -> exists w, run A w = t.
Proof. by move=> /connectP[p pth ->]; apply: path_run. Qed.

Lemma run_connect (S : finType) (A : dfa S) w :
  connect (dstep A) (start A) (run A w).
Proof.
rewrite /run; elim/last_ind: w => [|w b IH]; first exact: connect0.
rewrite -cats1 foldl_cat /=.
apply: connect_trans IH _; apply: connect1.
by apply/existsP; exists b.
Qed.

(* correctness of the emptiness decision *)
Theorem nonemptyP (S : finType) (A : dfa S) :
  reflect (exists w, accepts A w) (nonemptyb A).
Proof.
apply: (iffP existsP).
  move=> [t /andP[]]; rewrite inE => /connect_run[w hw] hf.
  by exists w; rewrite /accepts hw.
move=> [w hw]; exists (run A w); apply/andP; split; last exact: hw.
by rewrite inE run_connect.
Qed.
