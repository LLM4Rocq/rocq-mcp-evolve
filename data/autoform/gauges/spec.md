# Task: gauges — an interval-bounds ("gauge") library over reals

Build a fresh Rocq dune project (logical name `TaskLib`) formalizing closed
real intervals ("gauges") and a small sound interval arithmetic. This is a
renamed, self-contained interval-arithmetic core; no named textbook theorem
is requested, only the definitions, three soundness lemmas, and three width
lemmas.

**Every `.v` file must open with the heavy prelude**
```
From mathcomp Require Import all_ssreflect all_algebra.
From mathcomp Require Import reals.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.
```
Work over an abstract `R : realType` (from mathcomp's `reals`). Do NOT import
the analysis topology / `normedtype` / `boolp` machinery — the order and ring
structure of `realType` is all that is needed, and the build stays bounded.
Quantify explicitly over `R : realType`; NO `Section` `Variable`s (the gate
forbids `Variable`).

Project shape: `dune-project` = `(lang dune 3.8)` + `(using coq 0.8)`;
`theories/dune` = `(coq.theory (name TaskLib)
(theories Stdlib mathcomp HB elpi elpi_elpi))`. Four `.v` files with a real
dependency chain: `Gauge.v <- Ops.v <- {Sound.v, Width.v}`.

## The library

A **gauge** is a `(lo, hi)` pair of reals, read as the closed interval
`[lo, hi]`. Membership is a **Prop** (deliberately boolean-free):
`inside x g` means `lo g <= x` and `x <= hi g`. The **width** is `hi - lo`.

Operations: `gplus` (Minkowski sum, `[lo1+lo2, hi1+hi2]`), `gneg`
(reflection through 0, `[-hi, -lo]`), `gscale c` (`[c*lo, c*hi]`, sound for
`0 <= c`).

## Required names (exact)

Gauge.v:
- `Gauge.gauge` : `realType -> Type`   (defined as `fun R => (R * R)%type`)
- `Gauge.lo`, `Gauge.hi` : `forall R, gauge R -> R`   (the two projections)
- `Gauge.inside` : `forall R, R -> gauge R -> Prop`
    (`inside x g := (lo g <= x) /\ (x <= hi g)`)
- `Gauge.width` : `forall R, gauge R -> R`   (`width g := hi g - lo g`)
- concrete-value lemmas (they pin the semantics; state them EXACTLY):
  - `Gauge.inside_1_02` : `forall R : realType, inside (1 : R) (0, 2)`
  - `Gauge.outside_3_02` : `forall R : realType, ~ inside (3 : R) (0, 2)`
  - `Gauge.width_02` : `forall R : realType, width (0 : R, 2) = 2`

Ops.v:
- `Ops.gplus` : `forall R, gauge R -> gauge R -> gauge R`
- `Ops.gneg`  : `forall R, gauge R -> gauge R`
- `Ops.gscale` : `forall R, R -> gauge R -> gauge R`

Sound.v:
- `Sound.gplus_sound` : `forall R (x y : R) (g h : gauge R),
    inside x g -> inside y h -> inside (x + y) (gplus g h)`
- `Sound.gneg_sound` : `forall R (x : R) (g : gauge R),
    inside x g -> inside (- x) (gneg g)`
- `Sound.gscale_sound` : `forall R (c x : R) (g : gauge R),
    0 <= c -> inside x g -> inside (c * x) (gscale c g)`

Width.v:
- `Width.width_gplus` : `forall R (g h : gauge R),
    width (gplus g h) = width g + width h`
- `Width.width_gneg` : `forall R (g : gauge R), width (gneg g) = width g`
- `Width.width_gscale` : `forall R (c : R) (g : gauge R),
    width (gscale c g) = c * width g`

`dune build` must pass; no admits/axioms. The assumption audit permits only
the boolp classical trio that `realType` itself rests on.
