# Task: frugal — the frugal cost algebra

Build a fresh Rocq dune project (logical name `TaskLib`) formalizing a small
*cost algebra* and a 2x2 matrix product over it. The algebra is a renamed,
bounded min-plus ("tropical") structure; you are NOT asked for any named
textbook theorem, only the operations, their laws, and a concrete product.

**Every `.v` file must open with the heavy prelude**
`From mathcomp Require Import all_ssreflect all_algebra.`
(the tasks in this wave deliberately pay a real build cost). Do NOT open
`ring_scope`; keep the natural-number operations `addn`, `minn` explicit.

Project shape: `dune-project` = `(lang dune 3.8)` + `(using coq 0.8)`;
`theories/dune` = `(coq.theory (name TaskLib)
(theories Stdlib mathcomp HB elpi elpi_elpi))`. At least 4 `.v` files with a
real dependency chain: `Carrier.v <- Laws.v <- Mat2.v <- Main.v`.
No `Section` `Variable`s (the gate forbids `Variable`).

## The algebra

The **carrier** is `option nat`: a natural cost, or `None` meaning
"unreachable"/"+infinity". Two binary operations:

- **meld** — takes the *cheaper* of two costs (this is the algebra's
  "addition"). Its neutral is **top** = `None` (+infinity): `meld top x = x`.
- **chain** — *accumulates* two costs (the "multiplication"). Its neutral is
  **one** = `Some 0`, and **top is absorbing**: `chain top x = top`.

Concretely `meld (Some a) (Some b) = Some (minn a b)`,
`chain (Some a) (Some b) = Some (a + b)`, with `None` handled as above
(`meld` treats `None` as the identity, `chain` as absorbing).

## Required names (exact)

Carrier.v:
- `Carrier.carrier` : `Type`            (defined as `option nat`)
- `Carrier.meld`  : `carrier -> carrier -> carrier`
- `Carrier.chain` : `carrier -> carrier -> carrier`
- `Carrier.top`   : `carrier`           (the `meld`-neutral, `None`)
- `Carrier.one`   : `carrier`           (the `chain`-neutral, `Some 0`)
- `Carrier.ceq`   : `carrier -> carrier -> bool`   (decidable equality)
- `Carrier.ceqP`  : `forall x y, reflect (x = y) (Carrier.ceq x y)`

Laws.v (state with mathcomp's `commutative`/`associative`/
`left_distributive`/`right_distributive`/`left_id`/`right_id`/`left_zero`/
`right_zero`, or the explicit `forall` form — the probes pin the `forall`):
- `Laws.meldC` : `commutative meld`
- `Laws.meldA` : `associative meld`
- `Laws.chainA` : `associative chain`
- `Laws.chainDl` : `left_distributive chain meld`
- `Laws.chainDr` : `right_distributive chain meld`
- `Laws.meld_topl` : `left_id top meld`
- `Laws.meld_topr` : `right_id top meld`
- `Laws.chain_onel` : `left_id one chain`
- `Laws.chain_oner` : `right_id one chain`
- `Laws.chain_topl` : `left_zero top chain`
- `Laws.chain_topr` : `right_zero top chain`

Mat2.v (2x2 matrices over the carrier):
- `Mat2.mat` : record with fields `a00 a01 a10 a11 : carrier` and
  constructor `Mat` (the probes use `Mat2.Mat a b c d` and `Mat2.a00`)
- `Mat2.mmul` : `mat -> mat -> mat`, the min-plus matrix product:
  entry `(i,j)` = `meld` over the middle index of `chain (A i k) (B k j)`
- `Mat2.mmulA` : `forall A B C, mmul (mmul A B) C = mmul A (mmul B C)`
  (associativity of the product — the meaty proof)

Main.v (the cheapest-route reading):
- `Main.leg1`, `Main.leg2` : `mat`  (two concrete cost matrices)
- `Main.route2` : `mat`  (defined as `mmul leg1 leg2`)
- `Main.route2_val` : `route2 = Mat2.Mat (Some 4) (Some 1) (Some 3) (Some 0)`

`dune build` must pass; no admits/axioms. The probes compute concrete
`meld`/`chain`/matrix values with `vm_compute`, so your definitions must
reduce (keep them plain `Fixpoint`/`match`, not opaque).
