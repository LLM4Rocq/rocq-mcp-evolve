(* Entries.v -- an append-only ledger: a sequence of (account, delta)      *)
(* entries over the signed integers, with per-account balance and the       *)
(* total absolute movement.                                                 *)
From mathcomp Require Import all_ssreflect all_algebra.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.

(* an entry credits/debits one account by a signed delta *)
Definition entry := (nat * int)%type.
Definition ledger := seq entry.

(* the balance of account [a] after replaying [l] from zero *)
Fixpoint bal (a : nat) (l : ledger) : int :=
  match l with
  | [::] => 0
  | e :: t => (if e.1 == a then e.2 else 0) + bal a t
  end.

(* total absolute movement of a ledger (sum of |delta|) *)
Fixpoint total (l : ledger) : int :=
  match l with
  | [::] => 0
  | e :: t => `|e.2| + total t
  end.
