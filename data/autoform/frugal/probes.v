From TaskLib Require Import Carrier Laws Mat2 Main.
From mathcomp Require Import all_ssreflect all_algebra.

(* ===== semantic pins: concrete computations (vm_compute) ===== *)
Example p_meld    : Carrier.meld (Some 3) (Some 5) = Some 3.
Proof. vm_compute; reflexivity. Qed.
Example p_meld_topc : Carrier.meld None (Some 7) = Some 7.
Proof. vm_compute; reflexivity. Qed.
Example p_chain   : Carrier.chain (Some 2) (Some 4) = Some 6.
Proof. vm_compute; reflexivity. Qed.
Example p_chain_absorb : Carrier.chain None (Some 4) = None.
Proof. vm_compute; reflexivity. Qed.
Example p_chain_one_c : Carrier.chain (Some 0) (Some 5) = Some 5.
Proof. vm_compute; reflexivity. Qed.
Example p_ceq_yes : Carrier.ceq (Some 3) (Some 3) = true.
Proof. vm_compute; reflexivity. Qed.
Example p_ceq_no  : Carrier.ceq (Some 3) (Some 4) = false.
Proof. vm_compute; reflexivity. Qed.

(* the frugal matrix product computes the cheapest two-step routes *)
Example p_route : Main.route2 = Mat2.Mat (Some 4) (Some 1) (Some 3) (Some 0).
Proof. vm_compute; reflexivity. Qed.
Example p_route00 : Mat2.a00 Main.route2 = Some 4.
Proof. vm_compute; reflexivity. Qed.

(* ===== statement-shape pins for the algebraic laws ===== *)
Theorem p_meldC : forall x y, Carrier.meld x y = Carrier.meld y x.
Proof. exact Laws.meldC. Qed.
Theorem p_meldA : forall x y z,
  Carrier.meld x (Carrier.meld y z) = Carrier.meld (Carrier.meld x y) z.
Proof. exact Laws.meldA. Qed.
Theorem p_chainA : forall x y z,
  Carrier.chain x (Carrier.chain y z) = Carrier.chain (Carrier.chain x y) z.
Proof. exact Laws.chainA. Qed.
Theorem p_chainDl : forall x y z,
  Carrier.chain (Carrier.meld x y) z
  = Carrier.meld (Carrier.chain x z) (Carrier.chain y z).
Proof. exact Laws.chainDl. Qed.
Theorem p_chainDr : forall x y z,
  Carrier.chain x (Carrier.meld y z)
  = Carrier.meld (Carrier.chain x y) (Carrier.chain x z).
Proof. exact Laws.chainDr. Qed.
Theorem p_meld_top : forall x, Carrier.meld Carrier.top x = x.
Proof. exact Laws.meld_topl. Qed.
Theorem p_chain_one : forall x, Carrier.chain Carrier.one x = x.
Proof. exact Laws.chain_onel. Qed.
Theorem p_chain_top : forall x, Carrier.chain Carrier.top x = Carrier.top.
Proof. exact Laws.chain_topl. Qed.

(* the meaty theorem: associativity of the frugal matrix product *)
Theorem p_mmulA : forall A B C,
  Mat2.mmul (Mat2.mmul A B) C = Mat2.mmul A (Mat2.mmul B C).
Proof. exact Mat2.mmulA. Qed.
