# ledger — extended probes (A130 method 2)

`probes_ext.v` is the reference-derived extended probe file for task
`ledger`. Every expected value in it was **computed by `rocq compile` /
`vm_compute` against the gate-validated `reference/` solution** — none was
typed by hand. `gen_ext.py` is the generator that produced it; re-run it
with `python3 gen_ext.py` to regenerate from scratch (it re-builds the
reference in a sandbox, so it needs the same toolchain as the campaign:
`_opam/bin/rocq` and `_opam/bin/dune`, discovered automatically or via the
`ROCQ_BIN`/`DUNE_BIN`/`OPAM_BIN` env vars).

`probes_ext.v` opens with the exact same four prelude lines as `probes.v`
(`From TaskLib Require Import Entries Balance Replay Bounds.` + the mathcomp
prelude), so it type-checks against any submission that already passes
`probes.v`. Every table-driving helper `Definition` (`mk_ledgerA/B/C`,
`mk_entry`, `s_lin`, `lens`, `plens`, `qlens`) is built purely from
stdlib/mathcomp primitives (`iota`, `seq`, `odd`, `%%`, `Posz`, ring
arithmetic) — none of them touch a TaskLib name — and every `Example`
statement itself uses only the four required names
(`Entries.bal`/`total`/`entry`/`ledger`, `Balance.state`/`zero_state`/
`step`/`replay`) plus those local helpers, so a submission may differ in
every other detail (proof style, auxiliary lemmas, helper names) and still
be checked.

## What is pinned

All four required data/function names in this task are fully computable
(signed-integer / `nat` / `bool` arithmetic, no reals or opaque structures),
so nothing had to be left out. 28 `Example`s, **4,902 pinned facts** in
total (4,898 concrete numeric/boolean table instances + 3 type-alias
identities + 1 non-vacuity witness):

| Example(s) | Required name(s) exercised | Instances |
|---|---|---|
| `e_entry_type` | `Entries.entry = (nat * int)%type` | 1 (type identity, `reflexivity`) |
| `e_ledger_type` | `Entries.ledger = seq (nat * int)` | 1 (type identity, `reflexivity`) |
| `e_state_type` | `Balance.state = (nat -> int)` | 1 (type identity, `reflexivity`) |
| `ext_total_{A,B,C}` | `Entries.total` | 3 × 300 = 900 (ledger lengths 0..299, three families) |
| `ext_bal_acct_{A,B,C}` | `Entries.bal` | 3 × 300 = 900 (accounts 0..299 on a fixed length-250 ledger, most missing) |
| `ext_bal_grid_{A,B,C}` | `Entries.bal` | 3 × 120 = 360 (12 ledger lengths × 10 accounts) |
| `ext_no_teleport_{A,B,C}` | `Bounds.no_teleport` (as a decidable `bool` check `` `\|bal a l\| <= total l `` ) | 3 × 300 = 900 |
| `ext_replay_zero_{A,B,C}` | `Balance.replay`, `Balance.zero_state` | 3 × 200 = 600 |
| `ext_replay_lin_{A,B,C}` | `Balance.replay` from a **nonzero** initial state `s_lin := fun a => Posz a` | 3 × 72 = 216 (12 lengths × 6 accounts) |
| `ext_step_zero` | `Balance.step` from `zero_state` | 150 |
| `ext_step_lin` | `Balance.step` from `s_lin` | 150 |
| `ext_zero_state` | `Balance.zero_state` directly | 50 |
| `ext_replay_cat` | `Replay.replay_cat` (LHS evaluated concretely) | 216 (6 pre-lengths × 6 suf-lengths × 6 accounts) |
| `ext_checkpoint_bal` | `Replay.checkpoint_bal` (LHS evaluated concretely) | 216 |
| `ext_swap_step` | `Balance.swap_disjoint`'s conclusion, evaluated concretely on entry pairs guaranteed disjoint | 240 (40 pairs × 6 accounts) |
| `w_swap_disjoint` | non-vacuity witness | 1 |

Three ledger families (`mk_ledgerA/B/C`) give varied account distributions
(mod 6 / mod 4 / mod 9) and delta patterns (small-magnitude linear, an
odd/even sign flip, and a quadratic-magnitude pattern via `i*i mod 17`),
so the tables cover empty ledgers, ledgers where an account never appears
(`bal` = 0), and both positive- and negative-dominant deltas.

`Balance.state`, `Balance.zero_state`, `Balance.step` and `Balance.replay`
are all exercised beyond the zero-state special case that `probes.v`
already pins (`replay zero_state l a = bal a l`): `ext_replay_lin_*` and
`ext_step_lin` start from `s_lin := fun a => Posz a`, a state that does not
collapse to `bal`, so a submission whose `step`/`replay` happen to be
correct only for the zero snapshot (e.g. by special-casing it) would be
caught here.

### Non-vacuity witness

`Balance.swap_disjoint` is the only required theorem with a hypothesis
(`e1.1 != e2.1`). `w_swap_disjoint` pins that the hypothesis is concretely
satisfiable (`(mk_entry 0).1 != (mk_entry 1).1 = true`); `ext_swap_step`
separately pins the theorem's *conclusion* — `step`'s order-invariance —
on 240 concrete `(s, e1, e2, a)` instances where `e1.1 <> e2.1` holds by
construction (`mk_entry (2*n)` and `mk_entry (2*n+1)` always land on
different residues mod 6, since 6 is even so parity is preserved through
`mod 6`), so a `swap_disjoint` that only type-checks (e.g. via a broken
`step`/`.1` that makes the hypothesis vacuous, or a `step` that is
internally self-consistent but numerically wrong) would fail one of these
two `Example`s.

`replay_bal` and `checkpoint_bal`/`replay_cat` have no hypotheses (both
are unconditional `forall`s), so no witness is needed for them beyond the
direct value tables above.

## Not covered

Nothing in this task's required names was left unpinned — `bal`, `total`,
`state`, `zero_state`, `step`, `replay` and the `no_teleport` bound are all
`nat`/`int`/`bool`-valued and fully `vm_compute`-reducible (per the
task's own `spec.md`: "those definitions must reduce"). There is no gauge,
real-number, or opaque structure in this task's required-names surface, so
method (2) has full coverage here.

The only intentional limitation: `Balance.state` is a *function* `nat ->
int`, so it can never be printed or pinned as a whole value — every check
above evaluates `zero_state`/`step`/`replay` results at concrete accounts
instead (never claims two states are pointwise-equal beyond finitely many
probed accounts).

## Validation performed

1. **Well-posedness**: `probes_ext.v` compiles clean against the reference
   build (`gen_ext.py` re-checks this automatically as its step 4/4).
2. **Solved-submission compatibility**: checked against three solved
   attempts (`verdict.json` `"solved": true`), each rebuilt fresh with
   `dune build --root .` in its own sandbox, then
   `rocq compile -Q <its _build/default/theories> TaskLib probes_ext.v`:
   - `logs/autoform/af3_base/attempts/ledger__rep0` — compiles clean (exit 0, `probes_ext.vo` produced).
   - `logs/autoform/orp3_sota/attempts/ledger__rep1` — compiles clean.
   - `logs/autoform/op_evolve/attempts/ledger__rep0` — compiles clean.

   All three pass with no probe-side adjustment needed: every table used
   only the four required names plus this file's own stdlib/mathcomp
   helpers, so none of the three submissions' internal implementation
   choices (all define `bal`/`total`/`step` as `Fixpoint`s/`Definition`s
   equivalent-but-not-textually-identical to the reference, e.g. `step`
   phrased with `if e.1 == a then s a + e.2 else s a` instead of the
   reference's `s a + (if e.1 == a then e.2 else 0)`) caused a divergence
   — all reduce to the same numbers under `vm_compute`, as expected for a
   task with no named theorem left underspecified.

## Regenerating

```
python3 gen_ext.py
```

Runtime: a few minutes (`rocq compile` on ~4,900 pinned instances, run
twice — once for the driver, once for the well-posedness check). Requires
the same opam switch as the rest of the campaign
(`_opam/bin/rocq`, `_opam/bin/dune`); override with `ROCQ_BIN`/`DUNE_BIN`/
`OPAM_BIN` env vars if run from elsewhere. Uses
`EXT_LEDGER_SANDBOX` (default under the audit scratchpad) as scratch space
for the reference build and driver/well-posedness runs; nothing under the
task directory is touched except `probes_ext.v` itself.
