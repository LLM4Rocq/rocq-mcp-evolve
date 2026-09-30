(* Laws.v -- the algebraic laws of the frugal algebra: meld is a           *)
(* commutative monoid with neutral top, chain is a monoid with neutral one *)
(* and top absorbing, and chain distributes over meld on both sides.       *)
From mathcomp Require Import all_ssreflect all_algebra.
From TaskLib Require Import Carrier.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* meld: commutative and associative *)
Lemma meldC : commutative meld.
Proof. by case=> [a|]; case=> [b|] //=; rewrite minnC. Qed.

Lemma meldA : associative meld.
Proof. by case=> [a|]; case=> [b|]; case=> [c|] //=; rewrite minnA. Qed.

(* chain: associative *)
Lemma chainA : associative chain.
Proof. by case=> [a|]; case=> [b|]; case=> [c|] //=; rewrite addnA. Qed.

(* distributivity of chain over meld, both sides *)
Lemma chainDl : left_distributive chain meld.
Proof. by case=> [a|]; case=> [b|]; case=> [c|] //=; rewrite addn_minl. Qed.

Lemma chainDr : right_distributive chain meld.
Proof. by case=> [a|]; case=> [b|]; case=> [c|] //=; rewrite addn_minr. Qed.

(* neutrals *)
Lemma meld_topl : left_id top meld.
Proof. by case. Qed.

Lemma meld_topr : right_id top meld.
Proof. by case. Qed.

Lemma chain_onel : left_id one chain.
Proof. by case=> [b|] //=; rewrite add0n. Qed.

Lemma chain_oner : right_id one chain.
Proof. by case=> [a|] //=; rewrite addn0. Qed.

(* top is absorbing for chain *)
Lemma chain_topl : left_zero top chain.
Proof. by case. Qed.

Lemma chain_topr : right_zero top chain.
Proof. by case. Qed.
