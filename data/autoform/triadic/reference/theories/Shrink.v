(* Shrink.v -- the triad step strictly shrinks every odd n > 1: each       *)
(* chorus member of an odd n has an odd cofactor >= 3, so the triad's      *)
(* cofactors are at least 3, 5, 7 and the sum stays below n.               *)
From mathcomp Require Import all_ssreflect all_algebra.
From Stdlib Require Import Lia.
From mathcomp Require Import zify.
From TaskLib Require Import Props Step.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* A chorus member's cofactor multiplies back to n.                        *)
Lemma chorus_cofK n d : d \in chorus n -> n %/ d * d = n.
Proof. by rewrite mem_chorus => /andP[/andP[dn _] _]; apply: divnK. Qed.

(* For odd n, every cofactor is odd.                                       *)
Lemma chorus_cof_odd n d : odd n -> d \in chorus n -> odd (n %/ d).
Proof.
by move=> oddn dc; move: oddn; rewrite -{1}(chorus_cofK dc) oddM => /andP[].
Qed.

(* For odd n, every cofactor is at least 3 (2 is barred by parity).        *)
Lemma chorus_cof_ge3 n d : odd n -> d \in chorus n -> 3 <= n %/ d.
Proof.
move=> oddn dc; have oc := chorus_cof_odd oddn dc.
have hK := chorus_cofK dc.
move: dc; rewrite mem_chorus => /andP[/andP[_ d0] dn].
by move: hK oc; case: (n %/ d) => [|[|[|c']]]; lia.
Qed.

(* Cofactors are strictly antitone on the chorus.                          *)
Lemma chorus_cof_anti n d e :
  d \in chorus n -> e \in chorus n -> d < e -> n %/ e < n %/ d.
Proof.
move=> dc ec de.
have hd := chorus_cofK dc; have he := chorus_cofK ec.
move: dc ec; rewrite !mem_chorus.
move=> /andP[/andP[_ d0] dn] /andP[/andP[_ e0] en].
have cd0 : 0 < n %/ d by rewrite divn_gt0 //; apply: ltnW.
rewrite ltnNge; apply/negP => hle.
have h1 : n %/ d * d < n %/ d * e by rewrite ltn_pmul2l.
have h2 : n %/ d * e <= n %/ e * e by rewrite leq_mul2r hle orbT.
by move: (leq_trans h1 h2); rewrite hd he ltnn.
Qed.

(* A cofactor bound scales the member: k <= n %/ d gives k * d <= n.       *)
Lemma chorus_scale n d k : d \in chorus n -> k <= n %/ d -> k * d <= n.
Proof.
by move=> dc hk; rewrite -(chorus_cofK dc); apply: leq_mul.
Qed.

(* THE theorem: for odd n > 1 the triad step strictly decreases.           *)
Theorem tstep_shrink_odd n : odd n -> 1 < n -> tstep n < n.
Proof.
move=> oddn n1; rewrite /tstep /triad.
have srt : sorted gtn (rev (chorus n)).
  by rewrite rev_sorted; exact: chorus_sorted.
have mem_rc : {subset rev (chorus n) <= chorus n}.
  by move=> x; rewrite mem_rev.
move: srt mem_rc; case: (rev (chorus n)) => [|a [|b [|c r]]] srt mem_rc.
- by rewrite /=; lia.
- have ha : a \in chorus n by apply: mem_rc; exact: mem_head.
  move: ha; rewrite mem_chorus => /andP[_ an] /=.
  by lia.
- have ha : a \in chorus n by apply: mem_rc; exact: mem_head.
  have hb : b \in chorus n.
    by apply: mem_rc; rewrite in_cons mem_head orbT.
  move: srt => /= /andP[ba _].
  have hca : 3 <= n %/ a by apply: chorus_cof_ge3.
  have hab := chorus_cof_anti hb ha ba.
  have oa := chorus_cof_odd oddn ha.
  have ob := chorus_cof_odd oddn hb.
  have hcb : 5 <= n %/ b by lia.
  have sa : 3 * a <= n by apply: chorus_scale.
  have sb : 5 * b <= n by apply: chorus_scale.
  by rewrite /=; lia.
- have ha : a \in chorus n by apply: mem_rc; exact: mem_head.
  have hb : b \in chorus n.
    by apply: mem_rc; rewrite !in_cons eqxx orTb !orbT.
  have hc : c \in chorus n.
    by apply: mem_rc; rewrite !in_cons eqxx orTb !orbT.
  move: srt => /= /andP[ba /andP[cb _]].
  have hca : 3 <= n %/ a by apply: chorus_cof_ge3.
  have hab := chorus_cof_anti hb ha ba.
  have hbc := chorus_cof_anti hc hb cb.
  have oa := chorus_cof_odd oddn ha.
  have ob := chorus_cof_odd oddn hb.
  have oc := chorus_cof_odd oddn hc.
  have hcb : 5 <= n %/ b by lia.
  have hcc : 7 <= n %/ c by lia.
  have sa : 3 * a <= n by apply: chorus_scale.
  have sb : 5 * b <= n by apply: chorus_scale.
  have sc : 7 * c <= n by apply: chorus_scale.
  by rewrite /= take0 /=; lia.
Qed.
