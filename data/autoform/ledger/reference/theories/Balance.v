(* Balance.v -- a balance snapshot (account -> int), the single-entry step, *)
(* and full replay of a ledger onto a snapshot; its agreement with [bal]    *)
(* and the disjoint-account commutation law.                                *)
From mathcomp Require Import all_ssreflect all_algebra.
From TaskLib Require Import Entries.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.

(* a snapshot maps each account to its balance *)
Definition state := nat -> int.
Definition zero_state : state := fun _ => 0.

(* apply one entry to a snapshot *)
Definition step (s : state) (e : entry) : state :=
  fun a => s a + (if e.1 == a then e.2 else 0).

(* replay a whole ledger onto a snapshot *)
Definition replay (s : state) (l : ledger) : state := foldl step s l.

(* replaying onto snapshot [s] shifts each account by its ledger balance *)
Lemma replayE l s a : replay s l a = s a + bal a l.
Proof.
elim: l s => [|e t IH] s /=; first by rewrite addr0.
by rewrite IH /step addrA.
Qed.

(* replaying from zero reproduces [bal] exactly *)
Lemma replay_bal l a : replay zero_state l a = bal a l.
Proof. by rewrite replayE /zero_state add0r. Qed.

(* two adjacent entries on distinct accounts commute (as snapshots agree
   on every account) *)
Lemma swap_disjoint s e1 e2 : e1.1 != e2.1 ->
  step (step s e1) e2 =1 step (step s e2) e1.
Proof. by move=> _ a; rewrite /step /= addrAC. Qed.
