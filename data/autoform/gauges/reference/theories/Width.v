(* Width.v -- how the interval width transforms under the operations.      *)
From mathcomp Require Import all_ssreflect all_algebra.
From mathcomp Require Import reals.
From TaskLib Require Import Gauge Ops.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.

Lemma width_gplus (R : realType) (g h : gauge R) :
  width (gplus g h) = width g + width h.
Proof. by rewrite /width/gplus/lo/hi/= opprD addrACA. Qed.

Lemma width_gneg (R : realType) (g : gauge R) :
  width (gneg g) = width g.
Proof. by rewrite /width/gneg/lo/hi/= opprK addrC. Qed.

Lemma width_gscale (R : realType) (c : R) (g : gauge R) :
  width (gscale c g) = c * width g.
Proof. by rewrite /width/gscale/lo/hi/= mulrBr. Qed.
