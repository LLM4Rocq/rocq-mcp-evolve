(* Mat2.v -- 2x2 matrices over the frugal carrier, with the chain-product  *)
(* (min-plus matrix product) and its associativity -- the meaty proof.     *)
From mathcomp Require Import all_ssreflect all_algebra.
From TaskLib Require Import Carrier Laws.
Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(* a 2x2 matrix over the carrier, entries named row/column *)
Record mat := Mat {
  a00 : carrier; a01 : carrier;
  a10 : carrier; a11 : carrier }.

(* matrix product in the frugal algebra: meld of chained entries
   (this is min-plus / "shortest 2-step route" composition)               *)
Definition mmul (A B : mat) : mat :=
  Mat (meld (chain (a00 A) (a00 B)) (chain (a01 A) (a10 B)))
      (meld (chain (a00 A) (a01 B)) (chain (a01 A) (a11 B)))
      (meld (chain (a10 A) (a00 B)) (chain (a11 A) (a10 B)))
      (meld (chain (a10 A) (a01 B)) (chain (a11 A) (a11 B))).

(* left-commutativity of meld, then the 4-term interchange lemma           *)
Lemma meldCA : left_commutative meld.
Proof. by move=> x y z; rewrite meldA (meldC x) -meldA. Qed.

Lemma meldACA w x y z :
  meld (meld w x) (meld y z) = meld (meld w y) (meld x z).
Proof. by rewrite -!meldA [meld x _]meldCA. Qed.

(* associativity of the matrix product: each of the four entries reduces,
   after distributing chain over meld and reassociating chain, to the
   same four chained triples up to the interchange law.                    *)
Lemma mmulA A B C : mmul (mmul A B) C = mmul A (mmul B C).
Proof.
case: A => a b c d; case: B => e f g h; case: C => p q r s.
by rewrite /mmul /=; congr Mat;
   rewrite !chainDl !chainDr !chainA; apply: meldACA.
Qed.
