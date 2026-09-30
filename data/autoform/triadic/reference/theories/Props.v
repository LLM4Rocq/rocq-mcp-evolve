(* Props.v -- the "chorus" of a number: its inner divisors, in order.      *)
(* chorus n lists the divisors d of n with 0 < d < n, increasing.          *)
From mathcomp Require Import all_ssreflect all_algebra.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* The chorus of n: every divisor of n strictly between 0 and n,           *)
(* enumerated in increasing order.                                         *)
Definition chorus (n : nat) : seq nat := [seq d <- iota 1 n.-1 | d %| n].

(* The chorus is strictly increasing.                                      *)
Lemma chorus_sorted n : sorted ltn (chorus n).
Proof.
rewrite /chorus; apply: sorted_filter; first exact: ltn_trans.
exact: iota_ltn_sorted.
Qed.

(* Membership: d sings in the chorus of n iff d divides n and 0 < d < n.   *)
Lemma mem_chorus n d : (d \in chorus n) = (d %| n) && (0 < d) && (d < n).
Proof.
case: n => [|n]; first by rewrite /chorus /= in_nil ltn0 !andbF.
by rewrite mem_filter mem_iota add1n andbA.
Qed.
