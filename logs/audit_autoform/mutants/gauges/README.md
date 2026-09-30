# Probe mutation analysis — task `gauges`

Method (3) of A130. Reference confirmed accepted by the original gate before
mutation (`solved: true`, all layers ok). Ten named mutants below, each a
single deliberate wrong-formalization change from the reference. Two
mutants **survive** (the gate accepts a wrong formalization); the other
eight are genuinely false theorems under the mutated definitions and could
not be repaired to build (informative negatives — they show the pins *do*
catch that particular bug).

Mutant sources: `mut-gauges/<name>/` in the audit scratchpad (not committed
to the repo). Verdict JSONs for the two buildable/accepted mutants are in
this directory.

## Survivors (probe gaps — gate ACCEPTS a wrong formalization)

### 1. `lohi_swapped_decorative` — buildable=true, gate: **solved=true**

**Change:** `Gauge.lo`/`Gauge.hi` are defined swapped (`lo g := g.2`,
`hi g := g.1`, i.e. exactly backwards from "the two projections" the spec
requires), while `inside`, `width`, `gplus`, `gneg`, `gscale` are all
rewired to use the raw pair projections `g.1`/`g.2` directly instead of
going through `lo`/`hi`. The externally-observable behaviour (membership,
width, the three ops) is therefore byte-for-byte identical to the
reference — only `Gauge.lo` and `Gauge.hi` themselves are wrong.

**Why the gate accepts it:** none of the nine probes ever calls
`Gauge.lo` or `Gauge.hi` — they only exercise `inside`, `width`, `gplus`,
`gneg`, `gscale`. Nothing in probes.v (or in the required Sound/Width
theorem statements, which are stated purely in terms of `inside`/`width`/
the ops) constrains what `lo`/`hi` actually compute. A submission can ship
completely wrong, swapped, or even constant `lo`/`hi` functions and pass
every layer of the gate, as long as the "real" logic bypasses them.

**Suggested probe to kill it:** add direct projection pins to probes.v,
e.g.
```coq
Theorem p_lo_02 : forall R : realType, Gauge.lo (0 : R, 2) = 0.
Proof. exact ... (* would fail to typecheck/prove against Gauge.lo *) Qed.
Theorem p_hi_02 : forall R : realType, Gauge.hi (0 : R, 2) = 2.
Proof. exact ... Qed.
```
i.e. pin `lo`/`hi` at the same concrete gauge `(0,2)` already used for
`inside_1_02`/`width_02`, the way the spec's "Required names (exact)"
section already documents `lo`/`hi` as "the two projections" but the probe
suite never checks it.

### 2. `gscale_negative_shift` — buildable=true, gate: **solved=true**

**Change:** `Ops.gscale` is correct for `c >= 0` (matches the reference
exactly) but for `c < 0` it adds a spurious `+1` shift to both bounds:
`gscale c g := if 0 <= c then (c*lo g, c*hi g) else (c*lo g + 1, c*hi g + 1)`.

**Why the gate accepts it:** `Sound.gscale_sound` is only stated (per
spec) under the hypothesis `0 <= c`, so the `c < 0` branch is never
soundness-checked. `Width.width_gscale` *is* stated unconditionally for
all `c`, but the `+1` shift cancels out in `hi - lo`, so
`width (gscale c g) = c * width g` still holds exactly for the shifted
negative branch. The negative-`c` behaviour of `gscale` is thus almost
entirely unconstrained by the probe suite — a submission can make it
arbitrarily wrong (as long as it keeps whatever width identity holds) and
still pass.

**Suggested probe to kill it:** pin a concrete negative-`c` scaling, e.g.
```coq
Theorem p_gscale_neg_02 : forall R : realType,
  Ops.gscale (-1 : R) (0, 2) = (-2, 0)  \/  Ops.gscale (-1 : R) (0,2) = (-1*0, -1*2).
```
or, better, a semantic pin in the spirit of `inside_1_02`: assert that for
a concrete negative `c` and concrete `x` inside a concrete `g`, `c*x` is
(or is not) inside `gscale c g` — something the current suite has no
analogue of for negative `c`.

## Non-buildable mutants (probes correctly reject — no repair possible)

For each of these, the listed required theorem becomes a **false**
statement under the mutated definition (there exist counterexample
gauges/reals), so no proof script can close it; `dune build` fails at that
lemma. Recorded as `buildable=false`; no gate run (build layer alone
already fails).

### 3. `inside_or_instead_of_and`
**Change:** `Gauge.inside x g := (lo g <= x) \/ (x <= hi g)` (disjunction
instead of conjunction). **First failing point:** `Gauge.outside_3_02` —
with `\/`, `inside 3 (0,2)` is actually *true* (since `0 <= 3` alone
suffices), so `~ inside 3 (0,2)` is false and unprovable. Caught directly
by the exact concrete pin.

### 4. `width_hi_plus_lo`
**Change:** `Gauge.width g := hi g + lo g` (wrong operator: `+` instead of
`-`). **Note:** this mutant *passes* the concrete `width_02` pin by
coincidence, since `lo (0,2) = 0` makes `hi + lo = hi - lo` there.
**First failing point:** `Width.width_gneg` — `width (gneg g) = width g`
forces `width g = -width g` i.e. `width g = 0` for every gauge, which is
false in general (e.g. `g = (0,2)`, `width g = 2 <> 0 = -2`). Shows the
shape lemma `width_gneg` is doing real pinning work that the concrete
`width_02` pin alone would have missed.

### 5. `inside_half_open`
**Change:** `Gauge.inside x g := (lo g <= x) /\ (x < hi g)` (half-open
interval: excludes the upper endpoint). Passes both concrete pins
(`x = 1` is interior, `x = 3` is still excluded either way) and even
`Sound.gplus_sound` (strict addition combines fine). **First failing
point:** `Sound.gneg_sound` — take `g = (0,2)`, `x = 0` (`inside 0 g`
holds: `0 <= 0 /\ 0 < 2`); then `gneg g = (-2,0)` and `inside (-0) (gneg g)`
would need `0 < 0`, which is false.

### 6. `inside_strict_both`
**Change:** `Gauge.inside x g := (lo g < x) /\ (x < hi g)` (fully open
interval). Passes both concrete pins, `Sound.gplus_sound`, and
`Sound.gneg_sound` (strict inequalities combine fine under negation and
addition too). **First failing point:** `Sound.gscale_sound` — take any
`g` with `lo g < x < hi g` and `c = 0` (satisfies `0 <= c`); `gscale 0 g =
(0,0)` and `inside 0 (0,0)` would need `0 < 0`, which is false.

### 7. `gplus_swapped_cross`
**Change:** `Ops.gplus g h := (lo g - hi h, hi g - lo h)` (a
subtraction/cross-term bug, as if the Minkowski *difference* formula were
pasted in by mistake). **First failing point:** `Sound.gplus_sound` — the
statement is false in general, e.g. `g = h = (-5,-1)`: minimum of `x+y` is
`-10` but `lo g - hi h = -5-(-1) = -4 > -10`.

### 8. `gneg_no_swap`
**Change:** `Ops.gneg g := (- lo g, - hi g)` (negates both bounds but
forgets to swap them, so for a non-degenerate gauge `lo(gneg g) > hi(gneg
g)`, an ill-formed interval). **First failing point:** `Sound.gneg_sound`
— false in general whenever `lo g <> hi g`.

### 9. `width_off_by_one`
**Change:** `Gauge.width g := hi g - lo g + 1` (off-by-one constant).
**First failing point:** `Gauge.width_02` — directly false:
`width (0,2) = 2 - 0 + 1 = 3 <> 2`. Caught immediately by the concrete
pin, no shape-lemma reasoning needed.

### 10. `gplus_union_instead_of_sum`
**Change:** `Ops.gplus g h := (Num.min (lo g) (lo h), Num.max (hi g) (hi
h))` (interval hull/union instead of Minkowski sum — confuses "gplus"
with a different, similarly-shaped notion). **First failing point:**
`Sound.gplus_sound` — false in general, e.g. `g = h = (0,1)`, `x = y = 1`:
`x + y = 2` but the union bound is `max(1,1) = 1 < 2`.

## Summary

| mutant | category | buildable | gate |
|---|---|---|---|
| lohi_swapped_decorative | (i)/spec-gap: lo/hi unpinned | true | **solved=true (SURVIVOR)** |
| gscale_negative_shift | (i): wrong def on untested inputs (c<0) | true | **solved=true (SURVIVOR)** |
| inside_or_instead_of_and | (i): wrong connective | false | outside_3_02 unprovable |
| width_hi_plus_lo | (i): wrong operator | false | width_gneg unprovable |
| inside_half_open | (i): off-by-one (half-open) | false | gneg_sound unprovable |
| inside_strict_both | (i): off-by-one (open) | false | gscale_sound unprovable (c=0) |
| gplus_swapped_cross | (iv): different notion (difference) | false | gplus_sound unprovable |
| gneg_no_swap | (i): missing bound swap | false | gneg_sound unprovable |
| width_off_by_one | (i): off-by-one constant | false | width_02 unprovable |
| gplus_union_instead_of_sum | (iv): different notion (hull) | false | gplus_sound unprovable |

Two of ten plausible wrong-formalization mutants are genuine probe gaps
(both concern the *unlabeled operators* — `lo`/`hi` never referenced by
name in any probe, and `gscale`'s `c < 0` branch never soundness-checked).
The other eight demonstrate that probes.v's combination of exact concrete
pins (`inside_1_02`/`outside_3_02`/`width_02`) plus the six universally
quantified soundness/width shape theorems is otherwise quite strong: most
"plausible" operational bugs in `gplus`/`gneg`/`gscale`/`inside`/`width`
turn the required theorems into outright false statements, not just
under-tested ones.

## Verification

Independent check of the two survivors reported above (verify-mut:gauges).
For each: read the verdict JSON, diffed the mutant source under
`mut-gauges/<name>/` against `data/autoform/gauges/reference/`, checked
the described change against spec.md's stated meaning of the affected
required name(s), and — for GENUINE verdicts — wrote a killing probe,
then checked it compiles and passes against a sandbox build of the
reference and fails against a sandbox build of the mutant.

| mutant | verdict JSON | source diff matches description | classification | reason |
|---|---|---|---|---|
| `lohi_swapped_decorative` | `solved: true`, all layers ok | yes — `lo g := g.2`, `hi g := g.1`; `inside`/`width`/`gplus`/`gneg`/`gscale` rewired to raw `g.1`/`g.2` | **GENUINE** | spec.md: "a gauge is a `(lo, hi)` pair of reals" and "`Gauge.lo`, `Gauge.hi` : ... (the two projections)" fixes `lo (0,2) = 0`, `hi (0,2) = 2`; the mutant's swapped `lo`/`hi` directly contradict this stated meaning of the two required names, and no probe in probes.v ever calls `Gauge.lo`/`Gauge.hi` to catch it |
| `gscale_negative_shift` | `solved: true`, all layers ok | yes — `c >= 0` branch matches reference exactly; `c < 0` branch is `(c*lo g + 1, c*hi g + 1)` | **GENUINE** | spec.md's "The library" section states the general formula "gscale c (`[c*lo, c*hi]`, sound for `0 <= c`)" unconditionally on `c`, with "sound for 0 <= c" qualifying only the soundness *claim*, not restricting the formula's domain; the mutant's `c < 0` branch contradicts this stated definition, and `Sound.gscale_sound` is only required for `0 <= c` while `Width.width_gscale`'s unconditional identity survives the `+1` shift (it cancels in `hi - lo`), so no probe catches it |

Neither survivor is MISLABELED: both verdict JSONs genuinely show
`"solved": true` with all four layers `ok`/`clean`/`closed`, and both
mutant sources on disk (`mut-gauges/lohi_swapped_decorative/`,
`mut-gauges/gscale_negative_shift/`) diff exactly as described against
the reference — no extraneous changes.

### Checked killing probes

Both probes were compiled with `rocq compile -Q <theory_dir> TaskLib
killing_probes.v` (mirroring `autoform_gate.py`'s probe layer): **pass**
(exit 0, `.vo` produced, only pre-existing mathcomp ambiguous-coercion/
notation warnings) against a fresh sandbox `dune build --root .` of
`data/autoform/gauges/reference/`, and **fail** (`Error: No applicable
tactic.`) against sandbox builds of the corresponding mutant source under
`mut-gauges/<name>/_build/default/theories`.

```coq
(* kills lohi_swapped_decorative: pins Gauge.lo/Gauge.hi at the same
   concrete gauge (0,2) already used for inside_1_02/width_02. Passes
   against the reference (lo (0,2) = 0, hi (0,2) = 2 by the true
   projections); fails against the mutant (lo/hi swapped, so
   lo (0,2) = 2 <> 0). *)
Theorem p_lo_02 : forall R : realType, Gauge.lo (0 : R, 2) = 0.
Proof. by []. Qed.

Theorem p_hi_02 : forall R : realType, Gauge.hi (0 : R, 2) = 2.
Proof. by []. Qed.

(* kills gscale_negative_shift: pins a concrete negative-c scaling.
   Passes against the reference (gscale (-1) (0,2) = (-1*0,-1*2) =
   (0,-2)); fails against the mutant (c<0 branch adds +1 to both
   bounds, giving (1,-1) instead). *)
Theorem p_gscale_neg1_02 : forall R : realType,
  Ops.gscale (-1 : R) (0, 2) = (0, -2).
Proof.
move=> R; rewrite /Ops.gscale/Gauge.lo/Gauge.hi/=.
by rewrite !mulN1r oppr0.
Qed.
```
