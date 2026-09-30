(* Bounds.v -- the "no-teleport" bound: no account's balance can move by    *)
(* more than the total absolute movement recorded in the ledger.            *)
From mathcomp Require Import all_ssreflect all_algebra.
From TaskLib Require Import Entries.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.

Lemma no_teleport a l : `|bal a l| <= total l.
Proof.
elim: l => [|e t IH] /=; first by rewrite normr0.
apply: le_trans (ler_normD _ _) _.
apply: lerD IH.
case: (e.1 == a); first exact: lexx.
by rewrite normr0 normr_ge0.
Qed.
