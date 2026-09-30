# prodauto — extended probes (A130 audit method 2)

`probes_ext.v` is a reference-derived extended probe file for task
`prodauto`. It supplements the original grader's `probes.v` (forbidden-token
scan + fresh build + statement/semantic pins) with many more concrete
instances, all harvested by actually compiling `Compute` commands against
the gate-validated `reference/` build — no expected value in the file was
typed by hand.

Regenerate with:

```
python3 gen_ext.py --ref-theories <built-reference-theories-dir>
```

(`--ref-theories` must point at a *sandbox* build of `../reference/`, e.g.
`<sandbox>/ref/_build/default/theories` — never build inside the frozen
main checkout or this worktree's own `reference/`.) The script recompiles
one `harvest.v` (all `Compute`s at once, `Set Printing Width` forced high so
every result prints on a single line) against that reference build, parses
the printed values in order, and writes `probes_ext.v`.

## What is pinned

`probes_ext.v` opens with exactly `probes.v`'s prelude
(`From TaskLib Require Import Dfa Ops Lang Empty Pump Main.` +
`From mathcomp Require Import all_ssreflect all_algebra.`) and afterwards
uses only the required names (`Dfa.accepts`, `Dfa.run`, `Dfa.start`,
`Ops.dprod`, `Ops.dcompl`, `Lang.accepts_prod`, `Lang.accepts_compl`,
`Empty.nonemptyb`, `Empty.nonemptyP`, `Pump.trace`,
`Pump.accepts_long_dup`, `Main.parity`, `Main.mod3`, `Main.prod23`) plus
three small local word-generator `Definition`s built only from
stdlib/mathcomp (`wlen`, `word`, `bits` — documented in the file), so it
type-checks against any submission that already passes `probes.v`.

Two kinds of checks:

**A. Computed tables (`vm_compute; reflexivity`).** `Dfa.run`/`Dfa.accepts`
(plain `foldl`) and `Pump.trace` (plain `scanl`) reduce cleanly under
`vm_compute`, so these are pinned as large table equalities
`map (fun n => <expr n>) (iota 0 N) = [:: ...]`:

| table | instances | what it pins |
|---|---:|---|
| `e_acc_parity_word` | 1000 | `Dfa.accepts Main.parity` on mixed-length (1–15), mixed-content words (`word n` = the binary digits of `n`, length `1 + n mod 15`) |
| `e_acc_mod3_word` | 1000 | same, `Main.mod3` |
| `e_acc_prod23_word` | 1000 | same, `Main.prod23` |
| `e_acc_dprod_fresh_word` | 1000 | `Ops.dprod Main.parity Main.mod3` built fresh (independent of how the submission's own `Main.prod23` is written) |
| `e_acc_dcompl_parity_word` | 1000 | `Ops.dcompl Main.parity` |
| `e_acc_dcompl_mod3_word` | 1000 | `Ops.dcompl Main.mod3` |
| `e_acc_bits10_parity` | 1024 | `Dfa.accepts Main.parity` on **every** length-10 word (`bits 10 n`, `n` over `iota 0 1024` — exhaustive, not sampled) |
| `e_acc_bits10_mod3` | 1024 | same, `Main.mod3`, exhaustive |
| `e_acc_bits10_prod23` | 1024 | same, `Main.prod23`, exhaustive |
| `e_acc_nested_prod` | 500 | `Ops.dprod Main.prod23 Main.parity` — a doubly-nested product (state type `('I_2*'I_3)*'I_2`), exercising `Ops.dprod`'s genericity beyond the two fixed `Main` instances |
| `e_trace_len_word` | 1000 | `size (Pump.trace Main.parity (word n))` |
| `e_trace_last_run_parity_word` | 1000 | `Dfa.run A w == last (Dfa.start A) (Pump.trace A w)` on `Main.parity` |
| `e_trace_last_run_prod23_word` | 500 | same, on `Main.prod23` |
| 4 scalars (`acc_parity_empty`, `acc_mod3_empty`, `acc_prod23_empty`, `acc_parity_single_true`) | 4 | boundary cases: the empty word (0 trues) and a single `true` |

Total: **12,086 concrete instances** pinned by `vm_compute`.

**B. Theorem-derived checks (proved with tactics, not `vm_compute`).**
`Empty.dstep` / `Empty.reachable` / `Empty.nonemptyb` are built from
`#|_|` / `enum` / `connect`, and — independently verified in this exact
Rocq 9.1.1 + mathcomp 2.5.0 toolchain — **`#|'I_2|` itself does not reduce
to a literal under `vm_compute`** (nor `compute`/`native_compute`,
`native_compute` being disabled at configure time and falling back to
`vm_compute`): `Eval vm_compute in (#|'I_2|)` leaves the goal `card`
un-reduced, and `Lemma _ : #|'I_2| = 2. Proof. by vm_compute. Qed.` fails
with "No applicable tactic". This blocks direct computation of
`Empty.nonemptyb`, `Empty.reachable`, `#|S|` on any submission's own
`finType`, no matter how it is implemented — it is a toolchain limitation,
not a property of any one submission.

So instead of computing `nonemptyb` directly, `probes_ext.v` derives
concrete `Empty.nonemptyb` facts from the required *theorems*
(`Lang.accepts_prod`, `Lang.accepts_compl`, `Empty.nonemptyP`) applied to
concrete automata, using only the mathcomp cardinality lemmas `card_ord` /
`card_prod` (via the `{: T}` finType notation) — no `vm_compute` on
`Empty.v`'s own definitions is needed:

- `w_empty_selfcompl` — a fully generic lemma, proved purely from
  `Lang.accepts_prod` + `Lang.accepts_compl`, that `Ops.dprod A
  (Ops.dcompl A)` accepts no word, for **any** `dfa`. This alone is a
  strong check that the two theorems actually compose as intended.
- `w_nonemptyb_selfcompl_{parity,prod23}` — `Empty.nonemptyb (Ops.dprod A
  (Ops.dcompl A))` is `false`, via `Empty.nonemptyP` + the lemma above,
  instantiated on both `Main.parity` (2 states) and `Main.prod23`
  (6 states).
- `w_nonemptyb_full_parity` — dually, the complement of that empty-language
  automaton accepts everything, hence is nonempty.
- `w_nonemptyb_parity`, `w_nonemptyb_mod3`, `w_nonemptyb_dcompl_parity` —
  fresh `Empty.nonemptyb` witnesses (not already covered by `probes.v`,
  which only pins `Main.prod23_nonempty`), derived through
  `Empty.nonemptyP` from the harvested empty-word/single-symbol facts.

These matter even though `Lang.accepts_prod`/`Lang.accepts_compl`/
`Empty.nonemptyP` are already type/shape-pinned in `probes.v`: a `Qed`
there only proves the PROP type-checks, which is exactly what a
guardedness-check bypass on a recursive definition (`#[bypass_check(guard)]`
— the known hole in the original gate's assumption parser) could abuse
without showing up as a flagged axiom. Re-deriving concrete facts from
those theorems, and separately re-computing `accepts`/`trace` values by
`vm_compute`, tests that the *definitions* actually behave as claimed at
runtime, not just that a proof term of the right type exists.

**Non-vacuity witness (step 3).** The one required theorem with a
hypothesis is `Pump.accepts_long_dup : #|S| < size w -> ~~ uniq (trace A
w)`. `w_accepts_long_dup_parity` and `w_accepts_long_dup_prod23` show the
hypothesis is satisfiable with the submission's own `Main.parity` (2
states, a 3-symbol word) and `Main.prod23` (6 states, a 7-symbol word)
respectively, and derive the pigeonhole conclusion — so a submission whose
definitions make the hypothesis unsatisfiable (or the conclusion false)
fails here.

## Not covered

- **`Empty.dstep`, `Empty.reachable`, `Empty.nonemptyb`, `#|S|` — no direct
  `vm_compute` pins.** As detailed above, `#|'I_n|` (hence anything built
  from `card`/`enum`/`connect`, i.e. all of `Empty.v`) does not reduce to a
  literal under `vm_compute`/`compute`/`native_compute` in this Rocq
  9.1.1 + mathcomp 2.5.0 toolchain, independent of the submission. Section
  B above pins what these functions *entail* (via the required theorems)
  instead of their raw computed values.
- **Raw state identities** (e.g. "`Dfa.start Main.parity` is exactly
  `@Ordinal 2 0 isT`", or specific `Empty.dstep`/`Empty.reachable`
  membership facts). The spec fixes `parity`/`mod3`'s *language* ("even
  number of trues", "trues divisible by 3") but not the internal state
  labeling, so pinning a specific `Ordinal` value for a specific state
  would be over-specific — a correct submission could relabel states
  (e.g. swap which of the two `'I_2` values is the accepting one) as long
  as the observable `accepts`/`nonemptyb` behavior matches. All pins above
  are on `accepts`/`run`-vs-`trace`/`nonemptyb` behavior, never on raw
  state values.

## Validation performed

- `probes_ext.v` compiles cleanly (only the usual `all_algebra`/coercion
  notation-override warnings, no errors) against a sandbox build of
  `../reference/` — required well-posedness check.
- Compiled cleanly against **two solved submissions**
  (`verdict.json` `"solved": true`), each built in its own sandbox:
  - `logs/autoform/af2_base/attempts/prodauto__rep3/workspace`
  - `logs/autoform/af3_evolve/attempts/prodauto__rep1/workspace`

  Both pass `probes_ext.v` with no errors (~10–12s each, dominated by the
  ~12k-instance `vm_compute` tables). No over-specific probes were found
  needing a fix on these two attempts.

## Files

- `gen_ext.py` — the generator (harvests all expected values by running
  `rocq compile` against the reference build; never hand-edit
  `probes_ext.v` directly).
- `probes_ext.v` — the generated extended probe file (28 top-level
  `Example`/`Lemma` statements, 12,086 concrete `vm_compute`-checked
  instances plus 11 theorem-derived witness checks).
