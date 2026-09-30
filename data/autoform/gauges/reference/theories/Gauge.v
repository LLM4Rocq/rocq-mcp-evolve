(* Gauge.v -- "gauges": closed real intervals [lo, hi] as bound pairs,     *)
(* with membership as a Prop and interval width.                           *)
From mathcomp Require Import all_ssreflect all_algebra.
From mathcomp Require Import reals.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.

(* a gauge is a (lo, hi) pair of reals *)
Definition gauge (R : realType) := (R * R)%type.
Definition lo (R : realType) (g : gauge R) : R := g.1.
Definition hi (R : realType) (g : gauge R) : R := g.2.

(* membership is a Prop (boolean-free): x is inside [lo, hi] *)
Definition inside (R : realType) (x : R) (g : gauge R) : Prop :=
  (lo g <= x) /\ (x <= hi g).

(* the width of a gauge *)
Definition width (R : realType) (g : gauge R) : R := hi g - lo g.

(* ===== concrete-value lemmas: they pin the semantics of [inside] and
   [width], since [inside] is a Prop over an abstract R and cannot be
   evaluated by [vm_compute] ===== *)
Lemma inside_1_02 (R : realType) : inside (1 : R) (0, 2).
Proof. rewrite /inside/lo/hi/=; split; [exact: ler01 | by rewrite ler1n]. Qed.

Lemma outside_3_02 (R : realType) : ~ inside (3 : R) (0, 2).
Proof. rewrite /inside/lo/hi/= => -[_ h]; move: h; by rewrite ler_nat. Qed.

Lemma width_02 (R : realType) : width (0 : R, 2) = 2.
Proof. by rewrite /width/lo/hi/= subr0. Qed.
