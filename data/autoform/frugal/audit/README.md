# frugal — extended probes (audit method 2, A130)

`probes_ext.v` is a reference-derived extension of `data/autoform/frugal/probes.v`:
a battery of `vm_compute` pins over hundreds of concrete instances of every
required name that computes, generated automatically from the task's
`reference/` solution by `gen_ext.py`. It never types an expected value by
hand — every RHS in the file came out of `rocq compile`'s own printed
normal form for that expression evaluated against the reference build.

Opens with the same lines as `probes.v`
(`From TaskLib Require Import Carrier Laws Mat2 Main.` +
`From mathcomp Require Import all_ssreflect all_algebra.`) and uses only
required names (`Carrier.*`, `Mat2.*`) plus stdlib/mathcomp (`map`, `iota`,
tuples), so it type-checks against any submission that already passes
`probes.v`.

## Regenerate

```
python3 gen_ext.py
```

Resolves `dune`/`rocq` from `/Users/gbaudart/Project/llm4rocq/rocq-tools/_opam/bin`
(falling back to an ancestor `_opam/bin` or `$PATH`), builds `../reference`
into a temp dir, runs the query battery against it, writes
`probes_ext.v`, and re-compiles it against the reference build as a
self-check (the well-posedness rule). Exits non-zero and prints the
`rocq`/`dune` output on any failure.

## What is pinned, and how many instances

All counts are list lengths (each list element is one concrete instance,
per the campaign's counting convention); the `e_*_top_top` /
`e_ceq_top_top` entries are single scalar instances (the `top`/`top`
corner case that a length-N sweep over `Some _` values can't reach).

| Required name | Examples | Instances |
|---|---|---|
| `Carrier.meld` | `e_meld_sweep` (full symmetric sweep over 0..999), `e_meld_top_left`, `e_meld_top_right` (top-identity, 0..499), `e_meld_top_top` | 1000 + 500 + 500 + 1 = **2001** |
| `Carrier.chain` | `e_chain_sweep` (0..999), `e_chain_top_absorb_left/right` (0..499), `e_chain_one_left/right` (0..499), `e_chain_top_top` | 1000 + 500 + 500 + 500 + 500 + 1 = **3001** |
| `Carrier.ceq` | `e_ceq_refl`, `e_ceq_diff`, `e_ceq_vs_top` (0..499 each), `e_ceq_top_top` | 500 + 500 + 500 + 1 = **1501** |
| `Carrier.ceqP` | `e_ceqP` (statement-shape `Theorem`, `exact: Carrier.ceqP`) — probes.v never exercises `ceqP` at all, only the `ceq` booleans it should agree with; this closes that gap the same way probes.v pins `Laws.*` by `exact` | shape pin, not a concrete-instance count |
| `Carrier.top`, `Carrier.one` | exercised as arguments throughout the `meld`/`chain` top- and one- tables above | (covered via the above) |
| `Mat2.mat`, `Mat2.Mat`, `Mat2.a00/a01/a10/a11` | `e_mat_accessors`: 300 matrices, each field read back through the required accessors | **300** matrices (1200 field reads) |
| `Mat2.mmul` | `e_mmul_table1` (right factor has one `top` entry), `e_mmul_table2` (both factors have `top` entries in different positions, forcing the absorbing/identity cases through the product, not just plain arithmetic) — both project the result back through `Mat2.a00/a01/a10/a11` rather than reconstructing a raw `mat` record literal (see note below) | 300 + 300 = **600** |

Total: **18** statements (17 `vm_compute`-pinned `Example`s + 1 shape-pin
`Theorem`), **7403** concrete instances.

`Carrier.carrier` itself is exercised implicitly throughout: every RHS is a
literal built from `Some _ : option nat` / `None`, so a submission whose
`carrier` is not (isomorphic to, at these values) `option nat` fails to
type-check the file at all, before any `vm_compute` even runs.

### Why `mmul`/accessor results are tuples, not `mat` record literals

An earlier version of the generator let `Eval vm_compute` print raw `mat`
values and pasted the printed `{| a00 := ...; a01 := ...; ... |}` literal
back as the RHS. That failed to re-elaborate against real submissions
(`af2_base__rep0`, `orp3_sota__rep0`, `op_evolve__rep0` — see below) whose
`Mat2.v` wraps its content in an inner `Module Mat2. ... End Mat2.` (a
common pattern in this campaign, matching `Carrier.v`'s own
`Module Carrier. ... End Carrier.`): after `Require Import Mat2`, the
*qualified* name `Mat2.a00` resolves fine (that's what `probes.v` and this
file both use), but the *bare* field name `a00` used by Rocq's own
pretty-printer for record literals is never brought into scope, so
`rocq compile` failed with `Error: a00: Not a projection.` The fix was to
never let the generator reconstruct a `mat` literal at all: every `mmul`
query projects its result back to a plain 4-tuple of `carrier` values
through `Mat2.a00/a01/a10/a11` before printing, which stays entirely
within the qualified required names and sidesteps the ambiguity. This is
recorded here because it is exactly the kind of over-specific probe the
audit task warns about (pins a definitional detail — bare field-name
scoping — that the spec leaves open), and it was caught by the required
cross-check against solved submissions rather than by compiling against
the reference alone (the reference's `Mat2.v` does *not* wrap in an inner
module, so the record-literal version passed step 5's reference check and
would only have failed on real submissions).

## Non-vacuity witnesses

None were added. Every required theorem in this task's `spec.md`
(`Laws.meldC`, `meldA`, `chainA`, `chainDl`, `chainDr`, `meld_topl`,
`meld_topr`, `chain_onel`, `chain_oner`, `chain_topl`, `chain_topr`, and
`Mat2.mmulA`) is an unconditional `forall` — none carries a hypothesis a
submission's own definitions could make unsatisfiable. `probes.v` already
pins each of these by `exact <name>`, which is a proof term of the fully
universal statement and is already as strong as any finite instantiation;
there is nothing for a `w_<theorem>` witness to add here.

## Not covered

- **`Main.leg1`, `Main.leg2` (concrete entries)** — `spec.md`'s "Required
  names" section only pins `Main.route2_val` (the *product*
  `mmul leg1 leg2`); it explicitly leaves `leg1`/`leg2` as "two concrete
  cost matrices" with no fixed values. Different submissions are free to
  choose different `leg1`/`leg2` as long as their product matches
  `route2_val` (already pinned by `probes.v`'s `p_route`/`p_route00`), so
  pinning specific `leg1`/`leg2` values here would be over-specific and
  was deliberately omitted.
- **`Main.route2`, `Main.route2_val`** — fully pinned already by
  `probes.v` (`p_route`, `p_route00`); not duplicated here.
- **`Laws.*`, `Mat2.mmulA`** — see "Non-vacuity witnesses" above: already
  maximally pinned by `probes.v`'s `exact`-style `Theorem`s; nothing left
  to add.

Nothing in this task is non-computable (the whole algebra is `option nat`
with structural `match`es), so there is no "does not `vm_compute`" case
here, unlike tasks built on real-number or opaque structures.

## Validation performed

1. **Reference (well-posedness rule).** `gen_ext.py` builds
   `data/autoform/frugal/reference/` fresh in a temp dir and re-compiles
   `probes_ext.v` against it as its last step, every run. Confirmed
   passing.
2. **Solved submissions.** Built and checked against 4 solved attempts
   (`verdict.json` `"solved": true`) drawn from different runs/models to
   catch definitional variance (e.g. the `Module Carrier./Module Mat2.`
   wrapping pattern above):
   - `logs/autoform/af2_base/attempts/frugal__rep0/workspace`
   - `logs/autoform/af3_evolve/attempts/frugal__rep1/workspace`
   - `logs/autoform/orp3_sota/attempts/frugal__rep0/workspace`
   - `logs/autoform/op_evolve/attempts/frugal__rep0/workspace`

   Each was copied to a sandbox, built with `dune build --root .`, and
   `probes_ext.v` was compiled with
   `rocq compile -Q <workspace>/_build/default/theories TaskLib probes_ext.v`.
   The first pass (raw `mat` record literals) failed on 3 of the 4
   (`af2_base__rep0`, `orp3_sota__rep0`, `op_evolve__rep0`) with
   `Error: a00: Not a projection.` — diagnosed as the over-specific probe
   described above, fixed by projecting through `Mat2.a00/a01/a10/a11`
   instead of reconstructing a `mat` literal, and regenerated. All 4
   submissions now pass the fixed `probes_ext.v` cleanly (exit 0, no
   `Error` lines).
