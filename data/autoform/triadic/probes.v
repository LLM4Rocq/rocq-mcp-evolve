From TaskLib Require Import Props Step Fixed Shrink.
From mathcomp Require Import all_ssreflect all_algebra.

(* ===== semantic pins: concrete computations (vm_compute) ===== *)
Example p_chorus12 : Props.chorus 12 = [:: 1; 2; 3; 4; 6].
Proof. vm_compute; reflexivity. Qed.
Example p_triad30 : Step.triad 30 = [:: 15; 10; 6].
Proof. vm_compute; reflexivity. Qed.
Example p_tstep12 : Step.tstep 12 = 13.
Proof. vm_compute; reflexivity. Qed.
Example p_tstep30 : Step.tstep 30 = 31.
Proof. vm_compute; reflexivity. Qed.
Example p_tstep15 : Step.tstep 15 = 9.
Proof. vm_compute; reflexivity. Qed.
Example p_tstep27 : Step.tstep 27 = 13.
Proof. vm_compute; reflexivity. Qed.
Example p_tstep100 : Step.tstep 100 = 95.
Proof. vm_compute; reflexivity. Qed.

(* the triad step fixes the 6*m family *)
Example p_tstep6 : Step.tstep 6 = 6.
Proof. vm_compute; reflexivity. Qed.
Example p_tstep42 : Step.tstep 42 = 42.
Proof. vm_compute; reflexivity. Qed.
Example p_tstep66 : Step.tstep 66 = 66.
Proof. vm_compute; reflexivity. Qed.

(* ===== statement-shape pins for the required theorems ===== *)
Theorem p_chorus_sorted : forall n, sorted ltn (Props.chorus n).
Proof. exact Props.chorus_sorted. Qed.
Theorem p_mem_chorus : forall n d,
  (d \in Props.chorus n) = (d %| n) && (0 < d) && (d < n).
Proof. exact Props.mem_chorus. Qed.

(* the meaty theorem: the triad step fixes 6*m for odd m coprime to 5 *)
Theorem p_tstep_fixed : forall m,
  odd m -> ~~ (5 %| m) -> 0 < m -> Step.tstep (6 * m) = 6 * m.
Proof. exact Fixed.tstep_fixed. Qed.

(* the shrink theorem: on odd n > 1 the triad step strictly decreases *)
Theorem p_tstep_shrink_odd : forall n,
  odd n -> 1 < n -> Step.tstep n < n.
Proof. exact Shrink.tstep_shrink_odd. Qed.
