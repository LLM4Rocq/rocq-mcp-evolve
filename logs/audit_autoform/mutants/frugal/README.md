# Probe mutation analysis — task `frugal` (A130 method 3)

Reference solution confirmed accepted by the original gate before mutating
(`harness/autoform_gate.py data/autoform/frugal <ref copy>` → `"solved": true`,
`n_probes: 18`).

9 mutants, each a single deliberate wrong-formalization change from the
reference. `<mutant>.json` holds the full gate verdict (or a `buildable:
false` stub when the mutant's own project doesn't build). Never used
admit/Admitted/Axiom.

## Survivors (probe gap: gate accepts a wrong formalization)

- **m1_meld_topr_broken** — change: delete `Laws.meld_topr` (`right_id top
  meld`, i.e. `meld x top = x`) from Laws.v entirely; `Carrier.meld` itself
  is untouched. buildable: true. gate: **ACCEPTED** (`solved: true`).
  Why it slips through: `meld_topr` is a spec-required name that no probe
  ever references — only the left-hand law `meld_topl` is pinned
  (`p_meld_top : Carrier.meld Carrier.top x = x`, `exact
  Laws.meld_topl`), and the concrete `vm_compute` pin `p_meld_topc` also
  only puts `None` on the *left* (`meld None (Some 7) = Some 7`). A
  submission can simply skip proving (or even stating) the right-hand
  neutral law.
  Note: an actually-wrong-valued asymmetric `meld` (e.g. `meld (Some a)
  None = None`) is NOT buildable, because `Laws.meldC` (commutativity) is
  itself pinned as a universal statement (`p_meldC`), and commutativity
  forces `meld_topr` to follow from `meld_topl`. So the exploitable gap is
  specifically "the required lemma can be omitted/left unproved", not "meld
  can be made wrong on the right".
  Suggested probe to kill it: pin the right-hand law directly, e.g.
  ```
  Theorem p_meld_topr : forall x, Carrier.meld x Carrier.top = x.
  Proof. exact Laws.meld_topr. Qed.
  ```
  (forces the lemma to exist with the exact universal statement) plus a
  concrete case with `None` on the right, e.g.
  `Example p_meld_topc_r : Carrier.meld (Some 7) None = Some 7.`

- **m2_chain_topr_broken** — change: delete `Laws.chain_topr` (`right_zero
  top chain`, i.e. `chain x top = top`) from Laws.v. buildable: true. gate:
  **ACCEPTED**. Same root cause as m1: only `chain_topl` is pinned
  (`p_chain_top`, plus the concrete `p_chain_absorb : chain None (Some 4) =
  None`, `None` again only on the left); `chain` has no commutativity
  lemma required at all, so there is no algebraic law forcing the
  right-hand absorption to follow from the left-hand one — an asymmetric
  wrong `chain` (`chain (Some a) None = Some a`) *can* in principle be
  buildable for this specific law, but breaks `Laws.chainA` (associativity,
  pinned) for e.g. `x = Some a, y = None, z = Some c`; the simple, cleanly
  buildable exploit is just omitting `chain_topr`.
  Suggested probe: pin
  `Theorem p_chain_topr : forall x, Carrier.chain x Carrier.top = Carrier.top.`
  plus `Example p_chain_absorb_r : Carrier.chain (Some 4) None = None.`

- **m3_chain_oner_weakened** — change: keep `Chain`/`Carrier` correct, but
  restate `Laws.chain_oner` (`right_id one chain`, i.e. `chain x one = x`)
  with an added hypothesis: `forall x, x != top -> chain x one = x` (a
  strictly weaker theorem — the excluded case `x = top` is exactly the one
  case where `chain top one = top`, trivially true, so nothing is even
  lost by adding the guard, but it demonstrates the *shape* of theorem
  weakening the probes cannot detect). buildable: true. gate:
  **ACCEPTED**. Same root cause: `chain_oner` is a required name that no
  probe touches (only `chain_onel` is pinned, via `p_chain_one` and the
  concrete `p_chain_one_c : chain (Some 0) (Some 5) = Some 5`, `one` again
  only on the left).
  Suggested probe: pin the full unconditional statement:
  `Theorem p_chain_oner : forall x, Carrier.chain x Carrier.one = x.
  Proof. exact Laws.chain_oner. Qed.` — this specific `exact` fails to
  typecheck against a hypothesis-guarded lemma, closing the gap.

- **m4_chain_topr_mislabeled** — change: `Laws.chain_topr` is *present*
  but proves the wrong law under the right name: its statement is
  `left_zero top chain` (`chain top x = top`, a restatement of
  `chain_topl`) instead of the true `right_zero top chain` (`chain x top =
  top`) that the name promises. buildable: true (trivial, `by case`). gate:
  **ACCEPTED** — a stronger demonstration than m2: this is not merely an
  omission but a required theorem present under its exact required name
  and stating a genuine (if redundant) fact, yet about the *wrong* side of
  the algebra, and no probe can tell the difference because none
  references `Laws.chain_topr` by name or forces its statement shape.
  Suggested probe: same as m2's suggested `p_chain_topr` — an `exact
  Laws.chain_topr` against the true right-hand type would fail to
  typecheck against this mislabeled lemma.

- **m5_mmul_ignore_second_arg** — change: the "meaty" theorem of the task.
  `Mat2.mmul A B := A` (ignores `B` entirely, so it isn't a matrix product
  at all), making `Mat2.mmulA` (associativity) trivially true by
  reflexivity (`mmul (mmul A B) C = A = mmul A (mmul B C)`). `Main.route2`
  is then *hardcoded* to the literal expected matrix
  `Mat2.Mat (Some 4) (Some 1) (Some 3) (Some 0)` instead of being defined
  as `mmul leg1 leg2` (the spec's required definition, but the required-name
  list only pins the *value* of `route2` and `mmul`'s type, never the
  equation `route2 = mmul leg1 leg2` itself). buildable: true. gate:
  **ACCEPTED** — this is the single biggest probe gap found: the entire
  point of the task (`Mat2.mmul` correctly implementing min-plus matrix
  multiplication, proved associative — described in the spec as "the meaty
  proof") can be completely sidestepped. `mmulA` is pinned only as an
  abstract identity (`mmul (mmul A B) C = mmul A (mmul B C)`), which holds
  for *any* left-projection-like `mmul`, and nothing pins `route2` to
  actually be computed via `mmul`.
  Suggested probes: (a) pin the definitional equation directly:
  `Theorem p_route2_def : Main.route2 = Mat2.mmul Main.leg1 Main.leg2.`
  (this alone kills m5, since `Mat.Mat(4,1,3,0) <> mmul leg1 leg2 = leg1 =
  Mat(1,4,0,2)` under the degenerate `mmul`); (b) more robustly, pin
  `mmul` on inputs beyond `leg1`/`leg2`, e.g. a probe checking
  `Mat2.mmul (Mat2.Mat (Some 1) None None (Some 1)) (Mat2.Mat (Some 2)
  (Some 3) (Some 4) (Some 5)) = Mat2.Mat (Some 3) (Some 4) (Some 5) (Some
  6)` (an off-diagonal/identity-like case that a projection cannot satisfy
  regardless of how `route2` is wired up), so the gap is closed even if a
  submission avoids the `route2_val` shortcut in a different way.

## Non-survivors (buildable, but the gate correctly rejects — kept for contrast)

- **m6_elementwise_mmul** — change: `Mat2.mmul` redefined as pure
  per-entry `chain` (`Mat (chain a00A a00B) (chain a01A a01B) (chain a10A
  a10B) (chain a11A a11B)`) instead of the true min-plus product — a
  degenerate/simpler-than-required definition (type ii). Trivially
  associative via `chainA`, so buildable (own `route2_val` restated to the
  actual computed value `Mat (Some 4) (Some 4) (Some 1) (Some 7)`). gate:
  **REJECTED** at the probes layer — `p_route` fails to unify
  `{a00:=4;a01:=1;a10:=3;a11:=0}` with `{a00:=4;a01:=4;a10:=1;a11:=7}`. The
  concrete `route2_val`/`p_route00` pins do catch this one.

- **m7_meld_maxn** — change: `Carrier.meld` uses `maxn` instead of `minn`
  (wrong comparison direction — takes the costlier route instead of the
  cheaper one, type i). buildable: true (Laws.v repaired with
  `maxnC`/`maxnA`/`addn_maxl`/`addn_maxr`; own `route2_val` restated to
  the actual value `Mat (Some 5) (Some 9) (Some 3) (Some 7)`). gate:
  **REJECTED** — fails already at the first concrete pin, `p_meld :
  Carrier.meld (Some 3) (Some 5) = Some 3` (actual value `Some 5`).

- **m9_swapped_route2** — change: `Main.route2 := Mat2.mmul leg2 leg1`
  (operands swapped, type i "swapped argument order") instead of `mmul
  leg1 leg2`; `mmul` itself is correct. buildable: true (own
  `route2_val` restated to the actual value `Mat (Some 0) (Some 2) (Some
  2) (Some 5)`, since the algebra is not commutative in general).
  gate: **REJECTED** at `p_route`/`p_route00` (`Some 0 <> Some 4`, etc.).

## Not buildable (informative negative)

- **m8_wrong_one_value** — change: `Carrier.one := Some 1` instead of
  `Some 0` (wrong neutral element, type i). buildable: **false** — the
  required, pinned-shape lemma `Laws.chain_onel` (`left_id one chain`,
  i.e. `chain one x = x`, pinned universally by `p_chain_one`) becomes
  false in general (`chain (Some 1) x = Some (1+n) <> x` for `x = Some n`
  with `n > 0`); the reference proof step `rewrite add0n` fails outright
  and no repair without weakening the pinned statement is possible. Not
  run through the gate — the submission's own `dune build` never
  succeeds, so it can never reach a grading attempt. Recorded here to show
  this axis is *not* exploitable (unlike m1–m5): the pinned universal laws
  do force the two algebraic neutrals (`top = None`, `one = Some 0`) to be
  exactly right.

## Summary

| mutant | type | buildable | gate verdict |
|---|---|---|---|
| m1_meld_topr_broken | (v) omitted required law | yes | **ACCEPTED (survivor)** |
| m2_chain_topr_broken | (v) omitted required law | yes | **ACCEPTED (survivor)** |
| m3_chain_oner_weakened | (iii) weakened theorem | yes | **ACCEPTED (survivor)** |
| m4_chain_topr_mislabeled | (iv) wrong notion, right name | yes | **ACCEPTED (survivor)** |
| m5_mmul_ignore_second_arg | (ii) degenerate + hardcoded value | yes | **ACCEPTED (survivor)** |
| m6_elementwise_mmul | (ii) degenerate | yes | rejected (p_route) |
| m7_meld_maxn | (i) wrong comparison direction | yes | rejected (p_meld) |
| m8_wrong_one_value | (i) wrong neutral element | **no** | n/a (own build fails) |
| m9_swapped_route2 | (i) swapped argument order | yes | rejected (p_route) |

5 of 8 buildable mutants (m1, m2, m3, m4, m5) are accepted by the current
`probes.v` — all along the same axis: **every "right-hand"/second-operand
algebraic law in the spec (`meld_topr`, `chain_oner`, `chain_topr`) is a
required name that no probe exercises**, plus **the definitional link
`route2 = mmul leg1 leg2` is never pinned**, so the task's core theorem
(`mmulA`) can be satisfied by a `mmul` that isn't a matrix product at all.
The concrete `vm_compute` pins (`p_meld`, `p_chain`, `p_route`,
`p_route00`) are effective against wrong *values* on the inputs they do
cover (m6, m7, m9), and the universal statement pins (`meldC`, `meldA`,
`chainA`, `chainDl`, `chainDr`, `ceqP`) are effective against asymmetric
low-level bugs in `meld`/`chain`/`one`/`top` themselves (m8, and the
non-buildable asymmetric variants of m1/m2 discussed above).

## Verification

Checked against `<mutant>.json`, the mutant sources retained under
`/private/tmp/claude-501/-Users-gbaudart-Project-llm4rocq-rocq-tools/92fd7af9-6dfb-42f7-ad3c-3a89b1b13ece/scratchpad/mut-frugal/<name>/`,
and `data/autoform/frugal/reference/theories/` on branch `dev-audit`. All 5
reported survivors are confirmed **GENUINE** probe gaps: each verdict JSON
does show `"solved": true` with all layers `ok`/`clean`/`closed` and
`n_probes: 18` (matching `probes.v`'s literal 18 `Example`/`Theorem`
entries, none of which name `Laws.meld_topr`, `Laws.chain_topr`,
`Laws.chain_oner`, or the equation `Main.route2 = Mat2.mmul Main.leg1
Main.leg2`); the `theories/*.v` diffs against the reference match each
mutant's described change byte-for-byte; and the spec's "Required names
(exact)" section states every affected law as an unconditional
`right_id`/`right_zero` on the exact required name, and states `Mat2.mmul`
and `Main.route2`'s definitions in prose, so each mutant's deviation
contradicts the specification, not just the gate's probe coverage.

For each, a killing probe was written (only required names, in
`probes.v`'s style: `Theorem`/`Example` + `exact`/`vm_compute`), then
`rocq compile -Q <built theory dir> TaskLib <probe>.v` was run — once
against a clean sandbox `dune build --root .` of the unmodified reference
(all 5 probes compile there, confirming they are not themselves
over-strict), and once against a clean sandbox `dune build --root .` of
the corresponding mutant (all 5 probes fail there with the expected
error). Toolchain: `_opam/bin/{dune,rocq}` from this repo's opam switch
(Rocq 9.1.1).

| mutant | verdict | reason |
|---|---|---|
| m1_meld_topr_broken | **GENUINE** | `Laws.meld_topr : right_id top meld` is a required name, unconditionally stated in the spec; the mutant omits it entirely and still gets `"solved": true`. |
| m2_chain_topr_broken | **GENUINE** | `Laws.chain_topr : right_zero top chain` is a required name, unconditionally stated in the spec; omitted, still `"solved": true`. |
| m3_chain_oner_weakened | **GENUINE** | `Laws.chain_oner : right_id one chain` is required as the unconditional `forall x, chain x one = x`; the mutant proves only a `x <> top`-guarded version, still `"solved": true`. |
| m4_chain_topr_mislabeled | **GENUINE** | `Laws.chain_topr` is present under its exact required name but proves `left_zero top chain` (a restatement of `chain_topl`) instead of the spec's stated `right_zero top chain`; still `"solved": true`. |
| m5_mmul_ignore_second_arg | **GENUINE** | The spec states in prose that `Mat2.mmul` is the min-plus product (`meld` over `chain` of the middle index) and that `Main.route2` is defined as `mmul leg1 leg2`; the mutant's `mmul A B := A` and hardcoded `route2` contradict both, yet `mmulA` and `route2_val` are satisfied vacuously/by construction, still `"solved": true`. |

### Killing probes (all 5 verified: pass on reference, fail on mutant)

```coq
(* kills m1_meld_topr_broken *)
Theorem kp_meld_topr : forall x, Carrier.meld x Carrier.top = x.
Proof. exact Laws.meld_topr. Qed.

Example kp_meld_topc_r : Carrier.meld (Some 7) None = Some 7.
Proof. vm_compute; reflexivity. Qed.
(* on the mutant: Error: The reference Laws.meld_topr was not found in the
   current environment. *)
```

```coq
(* kills m2_chain_topr_broken *)
Theorem kp_chain_topr : forall x, Carrier.chain x Carrier.top = Carrier.top.
Proof. exact Laws.chain_topr. Qed.

Example kp_chain_absorb_r : Carrier.chain (Some 4) None = None.
Proof. vm_compute; reflexivity. Qed.
(* on the mutant: Error: The reference Laws.chain_topr was not found in the
   current environment. *)
```

```coq
(* kills m3_chain_oner_weakened *)
Theorem kp_chain_oner : forall x, Carrier.chain x Carrier.one = x.
Proof. exact Laws.chain_oner. Qed.
(* on the mutant: Error: cannot unify "x != top -> chain x Carrier.one = x"
   and "chain x Carrier.one = x". *)
```

```coq
(* kills m4_chain_topr_mislabeled (same probe as m2 -- both name the same
   gap: one by omission, one by mislabeling) *)
Theorem kp_chain_topr : forall x, Carrier.chain x Carrier.top = Carrier.top.
Proof. exact Laws.chain_topr. Qed.

Example kp_chain_absorb_r : Carrier.chain (Some 4) None = None.
Proof. vm_compute; reflexivity. Qed.
(* on the mutant: Error: cannot unify "chain top x = top" and
   "chain x top = top". *)
```

```coq
(* kills m5_mmul_ignore_second_arg *)
Theorem kp_route2_def : Main.route2 = Mat2.mmul Main.leg1 Main.leg2.
Proof. reflexivity. Qed.

Example kp_mmul_uses_second_arg :
  Mat2.mmul (Mat2.Mat (Some 1) None None (Some 1))
            (Mat2.Mat (Some 2) (Some 3) (Some 4) (Some 5))
  = Mat2.Mat (Some 3) (Some 4) (Some 5) (Some 6).
Proof. vm_compute; reflexivity. Qed.
(* on the mutant: Error: Unable to unify "mmul leg1 leg2" with "route2". *)
```

All 5 probes above compile cleanly (`rocq compile`, exit 0, `.vo` produced)
against `dune build --root .` of the unmodified reference, and all 5 fail
to compile (no `.vo` produced, the `Error:` shown in each comment) against
`dune build --root .` of their respective mutant. No forbidden tokens, no
`admit`/`Admitted`/`Axiom` used anywhere in this verification.
