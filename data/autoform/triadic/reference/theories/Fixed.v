(* Fixed.v -- the triad step fixes 6*m for m odd, positive, not a multiple *)
(* of 5: the three largest chorus members of 6*m are 3m, 2m, m, and they   *)
(* sum back to 6*m.                                                        *)
From mathcomp Require Import all_ssreflect all_algebra.
From Stdlib Require Import Lia.
From mathcomp Require Import zify.
From TaskLib Require Import Props Step.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* The divisors of 6*m lying in the window [m, 6*m) are exactly m, 2*m and *)
(* 3*m: such a divisor has cofactor c with 2 <= c <= 6, and c = 4, c = 5   *)
(* are barred by m odd and 5 not dividing m.                               *)
Lemma high_chorus m d :
  odd m -> ~~ (5 %| m) -> 0 < m ->
  ((d %| 6 * m) && (m <= d) && (d < 6 * m)) = (d \in [:: m; 2 * m; 3 * m]).
Proof.
move=> oddm m5 m0; apply/idP/idP; last first.
  rewrite !inE => /or3P[] /eqP->.
  - have -> : m %| 6 * m by apply/dvdnP; exists 6.
    by lia.
  - have -> : 2 * m %| 6 * m by apply/dvdnP; exists 3; lia.
    by lia.
  - have -> : 3 * m %| 6 * m by apply/dvdnP; exists 2; lia.
    by lia.
case/andP=> /andP[dvd6 le_md] lt_d6m.
have d0 : 0 < d by lia.
have [c hc] : exists c, c * d = 6 * m.
  by exists (6 * m %/ d); apply: divnK.
have c_ge2 : 2 <= c by nia.
have c_le6 : c <= 6 by nia.
rewrite !inE.
have : c = 2 \/ c = 3 \/ c = 4 \/ c = 5 \/ c = 6 by lia.
case=> [c2|[c3|[c4|[c5|c6]]]].
- by rewrite c2 in hc; lia.
- by rewrite c3 in hc; lia.
- by rewrite c4 in hc; lia.
- by rewrite c5 in hc; lia.
- by rewrite c6 in hc; lia.
Qed.

(* The chorus of 6*m splits into the members below m and the top block.    *)
Lemma chorus_6m m :
  odd m -> ~~ (5 %| m) -> 0 < m ->
  chorus (6 * m)
    = [seq d <- iota 1 m.-1 | d %| 6 * m] ++ [:: m; 2 * m; 3 * m].
Proof.
move=> oddm m5 m0; rewrite /chorus.
have -> : (6 * m).-1 = m.-1 + 5 * m by lia.
rewrite iotaD filter_cat; congr (_ ++ _).
have -> : 1 + m.-1 = m by lia.
apply: (@irr_sorted_eq _ ltn ltn_trans ltnn).
- apply: sorted_filter; first exact: ltn_trans.
  exact: iota_ltn_sorted.
- by rewrite /=; lia.
- move=> x; rewrite mem_filter mem_iota andbA.
  have -> : m + 5 * m = 6 * m by lia.
  by rewrite (@high_chorus m x oddm m5 m0).
Qed.

(* THE theorem: the triad step fixes 6*m.                                  *)
Theorem tstep_fixed m :
  odd m -> ~~ (5 %| m) -> 0 < m -> tstep (6 * m) = 6 * m.
Proof.
move=> oddm m5 m0.
rewrite /tstep /triad (chorus_6m oddm m5 m0) rev_cat /= take0 /=.
by lia.
Qed.
