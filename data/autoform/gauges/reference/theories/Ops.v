(* Ops.v -- interval arithmetic on gauges: sum, negation, nonneg scaling.  *)
From mathcomp Require Import all_ssreflect all_algebra.
From mathcomp Require Import reals.
From TaskLib Require Import Gauge.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.

(* Minkowski sum of intervals *)
Definition gplus (R : realType) (g h : gauge R) : gauge R :=
  (lo g + lo h, hi g + hi h).

(* reflection through 0: [lo, hi] |-> [-hi, -lo] *)
Definition gneg (R : realType) (g : gauge R) : gauge R :=
  (- hi g, - lo g).

(* scaling by a constant (sound for nonnegative c) *)
Definition gscale (R : realType) (c : R) (g : gauge R) : gauge R :=
  (c * lo g, c * hi g).
