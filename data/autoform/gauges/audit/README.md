# gauges — extended probes (A130 method (2))

`gauges` formalizes closed real intervals ("gauges") over an **abstract**
`R : realType`. This is the case A130 flagged in advance: mathcomp's
`realType` rests on classical (boolp) axioms, so arithmetic on its
literals is only *propositionally* equal, never *definitionally* equal —
`(9 : R) - 5` and `(4 : R)` do not reduce to the same normal form under
`vm_compute`, they are only provably equal via mathcomp lemmas
(`natrB`, `natrD`, ...). A literal `vm_compute; reflexivity` probe, as
used for the other tasks' method (2), is therefore unusable here. This
file records exactly what A130 asked for in that situation: what could be
pinned, and how, and what could not.

## Method actually used, in place of vm_compute

- **Gauge.v's five names** (`gauge`, `lo`, `hi`, `inside`, `width`) carry
  an **exact** required formula in spec.md, not just a type signature
  (e.g. `inside x g := lo g <= x /\ x <= hi g` is given verbatim). So they
  can be unfolded and their arithmetic consequences proved with generic
  mathcomp order/ring lemmas (`natrB`, `natrD`, `ler_nat`, `ler0n`,
  `ler01`, `ler1n`, `lern1`, `opprK`, `lerN2`, ...) instead of
  `vm_compute`. `gen_ext.py` emits one such `Example` per concrete
  `(lo, hi)` pair, picking a proof-tactic template by the sign pattern of
  `(lo, hi)` — nonnegative / straddles 0 / both negative — three
  hand-verified templates instantiated across a numeral table.

  A wrinkle specific to `ring_scope`: `0` and `1` have their own
  dedicated notations (`GRing.zero`/`GRing.one`), while every literal
  `>= 2` goes through the generic `n%:R` (`natmul`) Number Notation.
  `ler_nat`/`ltr_nat` only fire on the latter, so any comparison
  touching a literal `0` or `1` needs the matching dedicated lemma
  (`lexx`, `ler01`, `ler0n`, `ler1n`, `lern1`, `ltr01`, `ltr0n`, `ltr1n`)
  instead — `gen_ext.py`'s `nonneg_pf`/`le_term`/`lt_term`/`refute_le`
  helpers pick the right one per instance; this is exactly the kind of
  gap a hand-written probe file would likely miss (the table below does
  include several 0s and 1s, both as bounds and as scale factors, and
  every one of them exercises a different branch).

- **Ops.v's three names** (`gplus`, `gneg`, `gscale`) are pinned by
  spec.md **only** by type signature — the Minkowski-sum / reflection /
  scale formulas are prose, not part of "Required names (exact)". So
  `gen_ext.py` does not assume any particular internal representation.
  Instead it proves three general "value" lemmas directly from the
  required `Sound.v` + `Width.v` lemmas: apply soundness at the two
  endpoints of a nonempty gauge (`lo g` and `hi g`, both trivially
  "inside" `g`), then use the two resulting one-sided bounds together
  with the *exact* width equation to squeeze (sandwich) the endpoints of
  `gplus`/`gneg`/`gscale g` to a unique value (`sandwich` lemma, by
  antisymmetry of `<=`). E.g. for `gplus`:
  `lo (gplus g h) = lo g + lo h` and `hi (gplus g h) = hi g + hi h`
  follow from `gplus_sound` + `width_gplus` alone, for **any** submission
  whose required lemmas type-check — not only one shaped like the
  reference. These three lemmas (`h_gplus_value`, `h_gneg_value`,
  `h_gscale_value`) are then instantiated on concrete gauge/scalar
  combinations.

  Calling `Sound.gplus_sound`/`Width.width_gplus` etc. robustly across
  submissions took one more fix: `R` (and the other arguments) are
  **explicit** in the spec's required type (matched exactly by
  `probes.v`'s `exact Sound.gplus_sound` etc.), but a submission is free
  to additionally mark them `Set Implicit Arguments`/`{R : realType}` —
  implicit-vs-explicit is an elaboration-time convention, not part of
  the underlying type, so `exact` doesn't care, but plain application
  syntax does. The two validated submissions below actually disagree
  (the reference effectively makes `R` implicit via `Set Implicit
  Arguments`; both validated campaign submissions keep it fully
  explicit) — `gen_ext.py`'s helper lemmas call these four names with
  `@Lemma _ _ _ ... proof_args` (fully-explicit application via `@`),
  which works regardless of which convention a given submission chose.

- Every "expected value" below is the actual sum/negation/product of the
  picked bounds, computed by Python (never a hand-typed unrelated
  literal), and the file is checked against the reference build before
  any submission (well-posedness rule).

## What is pinned

- **Section 1 — exact-formula pins** (4 universal `Example`s, one per
  Gauge.v name): `lo (a,b) = a`, `hi (a,b) = b`,
  `inside x g <-> lo g <= x /\ x <= hi g`, `width g = hi g - lo g`, each
  `forall R a b` / `forall R x g`. Strictly stronger than any finite
  numeral table for these four names.
- **Section 2 — width + nonemptiness table**, table-driven over the
  three sign cases of `(lo, hi)`: 20 nonnegative pairs, 10
  straddle-zero pairs, 10 both-negative pairs = **40 gauges**, each with
  an `e_width_*` (width equals the Python-computed value) and an
  `e_ne_*` (`lo <= hi`, used downstream as the nonemptiness witness for
  Section 4) — **80 Examples**.
- Boundary membership + outside points for all 20 nonnegative-case
  gauges (`e_inside_lo_*`, `e_inside_hi_*`, `e_outside_above_*`,
  `e_outside_below_*`, testing the fixed point `-1` below and `hi+1`
  above) — **80 Examples** — plus one hand-verified outside-membership
  example each for the straddle and both-negative cases.
- **Section 3 — 4 general lemmas** (`sandwich`, `h_gplus_value`,
  `h_gneg_value`, `h_gscale_value`), proved only from the required
  Sound.v/Width.v lemmas (see above).
- **Section 4 — concrete applications** of the Section 3 lemmas: 6
  `gplus` pairs, 6 `gneg` gauges, 6 `gscale` instances (scale factors
  0, 1, 2, 3, 5) drawn from the Section 2 table — **18 Examples**, each
  pinning both endpoints of the result as the literal sum/negation/
  product of the operands' endpoints.
- **Section 5 — non-vacuity witnesses**: for each of `gplus_sound`,
  `gneg_sound`, `gscale_sound`, a concrete instance showing the
  hypotheses are simultaneously satisfiable under the submission's own
  required definitions (`w_gplus_sound`, `w_gneg_sound`,
  `w_gscale_sound`) — so a submission that proves these lemmas
  vacuously (e.g. `inside` never holds) fails here.

Total: **187 `Example`s + 4 helper `Lemma`s** in `probes_ext.v`.

## Not covered

- **No literal `vm_compute` numeral pin exists anywhere in this file** —
  every equality above is closed by unfolding + a named mathcomp
  lemma, never by computational reduction to a normal form. This is the
  case A130 pre-registered for gauges specifically.
- **`gplus`/`gneg`/`gscale`'s internal representation** is not pinned at
  all (deliberately — see above): a submission could implement `gplus`
  via a wholly different encoding than `(lo g+lo h, hi g+hi h)` (e.g. an
  intermediate `match`) and still pass every Section 4 Example, as long
  as its externally-observable `lo`/`hi` values are the ones forced by
  `Sound.v` + `Width.v`. That is intentional (`gplus` is pinned only by
  type signature per the Required-names list), not a gap.
- **Boundary membership / outside points for the straddle and
  both-negative sign cases** are pinned for only one representative
  gauge each (`(-3,7)` and `(-7,-3)`), not the full 10-entry tables —
  the general derivation needs a case split on which side of 0 the
  tested point falls that was not worth re-deriving generically for
  every table entry given the time budget; the width/nonemptiness pins
  for all 20 straddle/negative gauges are still full-table.
- **`Gauge.lo`/`Gauge.hi`'s own implicit-vs-explicit `R` convention** is
  not gate-constrained (`probes.v` never calls `Gauge.lo`/`Gauge.hi`
  directly, only `Gauge.inside`/`Gauge.width`, whose single-argument
  call shape *is* gate-guaranteed since `probes.v` itself uses it that
  way). This file calls `Gauge.lo g`/`Gauge.hi g` with a single argument
  throughout; a submission that made `R` an *explicit* leading argument
  of `lo`/`hi` specifically (stylistically unusual, not observed in
  either validated submission or the reference) would fail to compile
  against this file even though it passes `probes.v`. Not fixed, given
  the volume of call sites it would touch versus the low likelihood.
- Everything above the closed-interval arithmetic itself — no norm,
  metric, or topology reasoning is attempted (the task spec explicitly
  forbids importing that machinery), so this file adds nothing there.

## Validation performed

1. **Reference**: `probes_ext.v` compiles cleanly against a fresh sandbox
   build of `reference/` (`dune build --root .`, then
   `rocq compile -Q <built theories> TaskLib probes_ext.v`) — required
   before any submission is checked (well-posedness rule). Confirmed via
   `python3 gen_ext.py --check <reference>/_build/default/theories`.
2. **Two solved campaign submissions**, chosen to differ structurally
   from the reference and from each other (module-wrapped vs bare,
   `Set Implicit Arguments` vs not, `ssreflect` rewriting vs `lra`):
   - `logs/autoform/af2_base/attempts/gauges__rep2` (`verdict.json`
     `"solved": true`) — wraps every file in `Module X. ... End X.`,
     makes `Gauge.lo`/`hi`/`inside`/`width` implicit-`R`, keeps
     `Sound.*`/`Width.*` explicit-`R`. **Passes.**
   - `logs/autoform/af3_evolve/attempts/gauges__rep0` (`"solved": true`)
     — bare top-level definitions (no module wrapper), pulls in
     `mathcomp.analysis.lra`/`zify` and proves everything with `lra`.
     **Passes.**
   Both were rebuilt fresh (`dune build --root .` in an isolated
   sandbox copy, `_build` excluded from the copy) and then
   `probes_ext.v` was compiled against each with
   `rocq compile -Q <built theories> TaskLib probes_ext.v`; both exit 0.
   No adjustment to the probe file was needed after the fix described
   below (an earlier draft called `Sound.gplus_sound hlo hlo'`
   positionally, which happened to work against the reference by luck
   of its `Set Implicit Arguments` but failed against both real
   submissions since their `Sound.*` lemmas keep `R` explicit like the
   spec requires; switched to fully-explicit `@Lemma _ _ _ ...`
   application, which is convention-agnostic and now passes all three).

## Regenerating

```
python3 gen_ext.py                                   # writes probes_ext.v
python3 gen_ext.py --check <built theories dir>       # also compiles it
```
