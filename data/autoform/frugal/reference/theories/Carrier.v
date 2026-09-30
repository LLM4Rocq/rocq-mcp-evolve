(* Carrier.v -- the "frugal" carrier: a bounded min-plus (tropical) scalar. *)
(* option nat, with None the distinguished top element (+infinity).         *)
From mathcomp Require Import all_ssreflect all_algebra.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* The carrier: a natural cost, or None meaning "unreachable" / +infinity. *)
Definition carrier := option nat.

(* meld = the "addition" of the algebra: pick the cheaper of two costs.
   None (top) is its neutral because meld top x = x.                        *)
Definition meld (x y : carrier) : carrier :=
  match x, y with
  | None, _ => y
  | _, None => x
  | Some a, Some b => Some (minn a b)
  end.

(* chain = the "multiplication": accumulate costs.  None is absorbing
   (an unreachable step keeps the whole chain unreachable).                 *)
Definition chain (x y : carrier) : carrier :=
  match x, y with
  | None, _ => None
  | _, None => None
  | Some a, Some b => Some (a + b)
  end.

(* the distinguished constants *)
Definition top : carrier := None.     (* meld-neutral, +infinity           *)
Definition one : carrier := Some 0.   (* chain-neutral                     *)

(* decidable equality on the carrier (option of an eqType is an eqType) *)
Definition ceq (x y : carrier) : bool := x == y.

Lemma ceqP (x y : carrier) : reflect (x = y) (ceq x y).
Proof. exact: eqP. Qed.
