From TaskLib Require Import Entries Balance Replay Bounds.
From mathcomp Require Import all_ssreflect all_algebra.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.

(* a concrete ledger: two credits to account 0, one debit to account 1 *)
Notation demo := [:: (0%N, 3); (1%N, -2); (0%N, 5)].

(* ===== semantic pins: concrete balances / totals (vm_compute) ===== *)
Example p_bal0 : Entries.bal 0 demo = 8.
Proof. vm_compute; reflexivity. Qed.
Example p_bal1 : Entries.bal 1 demo = -2.
Proof. vm_compute; reflexivity. Qed.
Example p_bal2 : Entries.bal 2 demo = 0.
Proof. vm_compute; reflexivity. Qed.
Example p_total : Entries.total demo = 10.
Proof. vm_compute; reflexivity. Qed.

(* ===== shape pins ===== *)
(* replay from zero reproduces the per-account balance *)
Theorem p_replay_bal : forall l a,
  Balance.replay Balance.zero_state l a = Entries.bal a l.
Proof. exact Balance.replay_bal. Qed.

(* disjoint-account entries commute *)
Theorem p_swap : forall (s : Balance.state) (e1 e2 : Entries.entry),
  e1.1 != e2.1 ->
  Balance.step (Balance.step s e1) e2 =1 Balance.step (Balance.step s e2) e1.
Proof. exact Balance.swap_disjoint. Qed.

(* checkpoint-replay equivalence *)
Theorem p_replay_cat : forall (s : Balance.state) (pre suf : Entries.ledger),
  Balance.replay s (pre ++ suf) = Balance.replay (Balance.replay s pre) suf.
Proof. exact Replay.replay_cat. Qed.
Theorem p_checkpoint : forall (pre suf : Entries.ledger) a,
  Balance.replay (Balance.replay Balance.zero_state pre) suf a
  = Entries.bal a (pre ++ suf).
Proof. exact Replay.checkpoint_bal. Qed.

(* the no-teleport bound *)
Theorem p_no_teleport : forall a l, `|Entries.bal a l| <= Entries.total l.
Proof. exact Bounds.no_teleport. Qed.
