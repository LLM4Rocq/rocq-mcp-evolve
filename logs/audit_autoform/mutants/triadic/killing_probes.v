From TaskLib Require Import Props Step Fixed Shrink.
From mathcomp Require Import all_ssreflect all_algebra.

(* kills M3_degenerate_odd_shrink / M8_degenerate_both: an odd value not in
   the pinned set {15, 27} that the degenerate odd branch mishandles. *)
Example p_tstep21 : Step.tstep 21 = 11.
Proof. vm_compute; reflexivity. Qed.

(* kills M4_degenerate_even_nonfamily / M8_degenerate_both: an even value
   that is neither individually pinned nor in the 6*m family. *)
Example p_tstep8 : Step.tstep 8 = 7.
Proof. vm_compute; reflexivity. Qed.
