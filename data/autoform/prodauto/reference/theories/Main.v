(* Main.v -- concrete instances: a 2-state parity DFA, a 3-state mod-3 DFA,  *)
(* and their 6-state product, with acceptance pinned by computation.         *)
From mathcomp Require Import all_ssreflect all_algebra.
From TaskLib Require Import Dfa Ops Lang Empty.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* explicit ordinal constants so that [accepts]/[nonemptyb] reduce *)
Definition p0 : 'I_2 := ord0.
Definition p1 : 'I_2 := @Ordinal 2 1 isT.

(* parity: accept words with an even number of [true]s *)
Definition parity : dfa 'I_2 :=
  Dfa p0 (fun s => s == p0)
      (fun s b => if b then (if s == p0 then p1 else p0) else s).

Definition c0 : 'I_3 := ord0.
Definition c1 : 'I_3 := @Ordinal 3 1 isT.
Definition c2 : 'I_3 := @Ordinal 3 2 isT.

(* mod3: accept words whose number of [true]s is a multiple of 3 *)
Definition mod3 : dfa 'I_3 :=
  Dfa c0 (fun s => s == c0)
      (fun s b => if b then (if s == c0 then c1
                             else if s == c1 then c2 else c0) else s).

(* the 6-state product: accept iff #true is even AND a multiple of 3 *)
Definition prod23 : dfa ('I_2 * 'I_3)%type := dprod parity mod3.

(* concrete acceptance pins (vm_compute) *)
Lemma acc_parity : accepts parity [:: true; true] = true.
Proof. by vm_compute. Qed.
Lemma acc_parity_odd : accepts parity [:: true; true; true] = false.
Proof. by vm_compute. Qed.
Lemma acc_mod3 : accepts mod3 [:: true; true; true] = true.
Proof. by vm_compute. Qed.
Lemma acc_prod3 : accepts prod23 [:: true; true; true] = false.
Proof. by vm_compute. Qed.
Lemma acc_prod6 :
  accepts prod23 [:: true; true; true; true; true; true] = true.
Proof. by vm_compute. Qed.

(* the product language really is the intersection, on this instance *)
Lemma acc_prod6_split :
  accepts parity [:: true; true; true; true; true; true]
  && accepts mod3 [:: true; true; true; true; true; true].
Proof. by vm_compute. Qed.

(* the product automaton is nonempty: the empty word is accepted, so the
   emptiness decision returns true (proved through its correctness lemma) *)
Lemma prod23_nonempty : nonemptyb prod23.
Proof. by apply/nonemptyP; exists [::]. Qed.
