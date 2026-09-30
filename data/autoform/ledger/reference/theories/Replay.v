(* Replay.v -- replay from checkpoints: replaying a ledger equals replaying *)
(* its suffix from the snapshot reached at the split point (the checkpoint).*)
From mathcomp Require Import all_ssreflect all_algebra.
From TaskLib Require Import Entries Balance.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.

(* replay splits at any point: the checkpoint is [replay s pre] *)
Lemma replay_cat s pre suf :
  replay s (pre ++ suf) = replay (replay s pre) suf.
Proof. by rewrite /replay foldl_cat. Qed.

(* checkpoint-replay equivalence: replaying the suffix from the checkpoint
   [replay zero_state pre] equals a full replay of [pre ++ suf] *)
Lemma checkpoint_bal pre suf a :
  replay (replay zero_state pre) suf a = bal a (pre ++ suf).
Proof. by rewrite -replay_cat replay_bal. Qed.
