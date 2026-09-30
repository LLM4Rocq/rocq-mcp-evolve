(* Sound.v -- soundness of the interval operations: if the arguments are  *)
(* inside their gauges, the result is inside the combined gauge.           *)
From mathcomp Require Import all_ssreflect all_algebra.
From mathcomp Require Import reals.
From TaskLib Require Import Gauge Ops.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.

Lemma gplus_sound (R : realType) (x y : R) (g h : gauge R) :
  inside x g -> inside y h -> inside (x + y) (gplus g h).
Proof.
rewrite /inside/gplus/lo/hi/= => -[l1 u1] [l2 u2]; split; by rewrite lerD.
Qed.

Lemma gneg_sound (R : realType) (x : R) (g : gauge R) :
  inside x g -> inside (- x) (gneg g).
Proof.
rewrite /inside/gneg/lo/hi/= => -[l u]; split; by rewrite lerN2.
Qed.

Lemma gscale_sound (R : realType) (c x : R) (g : gauge R) :
  0 <= c -> inside x g -> inside (c * x) (gscale c g).
Proof.
move=> hc; rewrite /inside/gscale/lo/hi/= => -[l u].
by split; rewrite ler_wpM2l.
Qed.
