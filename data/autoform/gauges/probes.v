From TaskLib Require Import Gauge Ops Sound Width.
From mathcomp Require Import all_ssreflect all_algebra.
From mathcomp Require Import reals.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.

(* ===== concrete-value pins (boolean-free; [inside] is a Prop over an
   abstract R, so these named lemmas replace vm_compute) ===== *)
Theorem p_inside_1_02 : forall R : realType, Gauge.inside (1 : R) (0, 2).
Proof. exact Gauge.inside_1_02. Qed.
Theorem p_outside_3_02 : forall R : realType, ~ Gauge.inside (3 : R) (0, 2).
Proof. exact Gauge.outside_3_02. Qed.
Theorem p_width_02 : forall R : realType, Gauge.width (0 : R, 2) = 2.
Proof. exact Gauge.width_02. Qed.

(* ===== soundness shape pins ===== *)
Theorem p_gplus_sound : forall (R : realType) (x y : R) (g h : Gauge.gauge R),
  Gauge.inside x g -> Gauge.inside y h ->
  Gauge.inside (x + y) (Ops.gplus g h).
Proof. exact Sound.gplus_sound. Qed.
Theorem p_gneg_sound : forall (R : realType) (x : R) (g : Gauge.gauge R),
  Gauge.inside x g -> Gauge.inside (- x) (Ops.gneg g).
Proof. exact Sound.gneg_sound. Qed.
Theorem p_gscale_sound :
  forall (R : realType) (c x : R) (g : Gauge.gauge R),
  0 <= c -> Gauge.inside x g -> Gauge.inside (c * x) (Ops.gscale c g).
Proof. exact Sound.gscale_sound. Qed.

(* ===== width shape pins ===== *)
Theorem p_width_gplus : forall (R : realType) (g h : Gauge.gauge R),
  Gauge.width (Ops.gplus g h) = Gauge.width g + Gauge.width h.
Proof. exact Width.width_gplus. Qed.
Theorem p_width_gneg : forall (R : realType) (g : Gauge.gauge R),
  Gauge.width (Ops.gneg g) = Gauge.width g.
Proof. exact Width.width_gneg. Qed.
Theorem p_width_gscale : forall (R : realType) (c : R) (g : Gauge.gauge R),
  Gauge.width (Ops.gscale c g) = c * Gauge.width g.
Proof. exact Width.width_gscale. Qed.
