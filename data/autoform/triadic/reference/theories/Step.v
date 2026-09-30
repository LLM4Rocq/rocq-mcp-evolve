(* Step.v -- the triad and the triad step.                                 *)
(* The triad of n is the three largest chorus members (fewer if the chorus *)
(* is short); the triad step is their sum.                                 *)
From mathcomp Require Import all_ssreflect all_algebra.
From TaskLib Require Import Props.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* The triad: the (at most) three largest chorus members, decreasing.      *)
Definition triad (n : nat) : seq nat := take 3 (rev (chorus n)).

(* The triad step: the sum of the triad.                                   *)
Definition tstep (n : nat) : nat := sumn (triad n).
