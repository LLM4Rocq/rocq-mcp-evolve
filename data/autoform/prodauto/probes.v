From TaskLib Require Import Dfa Ops Lang Empty Pump Main.
From mathcomp Require Import all_ssreflect all_algebra.

(* ===== semantic pins: concrete acceptance (vm_compute) ===== *)
Example p_acc_parity : Dfa.accepts Main.parity [:: true; true] = true.
Proof. vm_compute; reflexivity. Qed.
Example p_acc_parity_odd :
  Dfa.accepts Main.parity [:: true; true; true] = false.
Proof. vm_compute; reflexivity. Qed.
Example p_acc_mod3 :
  Dfa.accepts Main.mod3 [:: true; true; true] = true.
Proof. vm_compute; reflexivity. Qed.
Example p_acc_prod3 :
  Dfa.accepts Main.prod23 [:: true; true; true] = false.
Proof. vm_compute; reflexivity. Qed.
Example p_acc_prod6 :
  Dfa.accepts Main.prod23 [:: true; true; true; true; true; true] = true.
Proof. vm_compute; reflexivity. Qed.

(* ===== statement-shape pins ===== *)
(* language-intersection theorem for the product automaton *)
Theorem p_lang : forall (SA SB : finType) (A : Dfa.dfa SA) (B : Dfa.dfa SB) w,
  Dfa.accepts (Ops.dprod A B) w <-> Dfa.accepts A w /\ Dfa.accepts B w.
Proof. exact Lang.accepts_prodP. Qed.
Theorem p_lang_b :
  forall (SA SB : finType) (A : Dfa.dfa SA) (B : Dfa.dfa SB) w,
  Dfa.accepts (Ops.dprod A B) w = Dfa.accepts A w && Dfa.accepts B w.
Proof. exact Lang.accepts_prod. Qed.

(* complement language *)
Theorem p_compl : forall (S : finType) (A : Dfa.dfa S) w,
  Dfa.accepts (Ops.dcompl A) w = ~~ Dfa.accepts A w.
Proof. exact Lang.accepts_compl. Qed.

(* emptiness decision correctness *)
Theorem p_empty : forall (S : finType) (A : Dfa.dfa S),
  reflect (exists w, Dfa.accepts A w) (Empty.nonemptyb A).
Proof. exact Empty.nonemptyP. Qed.

(* pumping-light: a word longer than #states revisits a state *)
Theorem p_pump : forall (S : finType) (A : Dfa.dfa S) w,
  #|S| < size w -> ~~ uniq (Pump.trace A w).
Proof. exact Pump.accepts_long_dup. Qed.

(* the concrete product automaton is nonempty (via the decider) *)
Theorem p_nonempty23 : Empty.nonemptyb Main.prod23.
Proof. exact Main.prod23_nonempty. Qed.
