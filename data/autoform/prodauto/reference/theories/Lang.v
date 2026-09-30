(* Lang.v -- the languages of the constructions: the product accepts        *)
(* exactly the intersection, the complement exactly the complement.          *)
From mathcomp Require Import all_ssreflect all_algebra.
From TaskLib Require Import Dfa Ops.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* the product run is the pair of component runs *)
Lemma foldl_prod (SA SB : finType) (A : dfa SA) (B : dfa SB) sa sb w :
  foldl (trans (dprod A B)) (sa, sb) w
  = (foldl (trans A) sa w, foldl (trans B) sb w).
Proof. by elim: w sa sb => [|b w IH] sa sb //=; rewrite IH. Qed.

Lemma run_prod (SA SB : finType) (A : dfa SA) (B : dfa SB) w :
  run (dprod A B) w = (run A w, run B w).
Proof. by rewrite /run /= foldl_prod. Qed.

(* language-intersection theorem (boolean form) *)
Theorem accepts_prod (SA SB : finType) (A : dfa SA) (B : dfa SB) w :
  accepts (dprod A B) w = accepts A w && accepts B w.
Proof. by rewrite /accepts run_prod. Qed.

(* language-intersection theorem (propositional form) *)
Theorem accepts_prodP (SA SB : finType) (A : dfa SA) (B : dfa SB) w :
  accepts (dprod A B) w <-> accepts A w /\ accepts B w.
Proof. rewrite accepts_prod; split; by move/andP. Qed.

(* complement language *)
Theorem accepts_compl (S : finType) (A : dfa S) w :
  accepts (dcompl A) w = ~~ accepts A w.
Proof. by []. Qed.
