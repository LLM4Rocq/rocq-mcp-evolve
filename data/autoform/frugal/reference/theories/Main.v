(* Main.v -- the "cheapest-route" reading: two concrete cost matrices and  *)
(* their frugal product, whose entries are the cheapest two-step routes.   *)
From mathcomp Require Import all_ssreflect all_algebra.
From TaskLib Require Import Carrier Mat2.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* leg 1 and leg 2 cost matrices between two 2-node layers; None = no edge *)
Definition leg1 : mat := Mat (Some 1) (Some 4) (Some 0) (Some 2).
Definition leg2 : mat := Mat (Some 3) (Some 0) (Some 1) (Some 5).

(* the cheapest two-step route matrix *)
Definition route2 : mat := mmul leg1 leg2.

(* it pins the semantics: entry (i,j) is the min over the middle node k of
   (leg1 i k) + (leg2 k j) *)
Lemma route2_val : route2 = Mat (Some 4) (Some 1) (Some 3) (Some 0).
Proof. by vm_compute. Qed.
