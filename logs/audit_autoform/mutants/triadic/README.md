# mut:triadic — probe mutation analysis for task `triadic`

Method (3) of A130. Reference solution confirmed accepted by the original
gate (`harness/autoform_gate.py`) before mutating: `{"solved": true, ...}`.

Reading the pins first: `Props.mem_chorus` and `Props.chorus_sorted` are
both pinned with their *exact* general statement (`exact
Props.mem_chorus`/`exact Props.chorus_sorted` in probes.v), and together a
membership characterization + strict sortedness *forces* `chorus` to equal
the correct sorted list of divisors for **every** `n`, not just the tested
ones — so `Props.chorus` turns out to be fully pinned in general, despite
only one concrete value (`chorus 12`) being `vm_compute`d. `Step.triad` and
`Step.tstep`, by contrast, have **no** general required lemma of their own
— they are only reachable through 8 concrete `tstep`/`triad` values and
through the two general theorems `Fixed.tstep_fixed` (an *equality*,
`tstep (6*m) = 6*m`, forced true for the infinite family of `m` odd,
`0 < m`, `~~ (5 %| m)`) and `Shrink.tstep_shrink_odd` (only an
*inequality*, `tstep n < n`, for odd `n > 1`). The equality pin leaves no
slack on the `6*m` family; the inequality pin leaves enormous slack
everywhere else. That asymmetry is the actual probe gap this task has.

## Mutants

| # | name | change | buildable | gate result | first failing probe / reason |
|---|------|--------|-----------|-------------|-------------------------------|
| M1 | `M1_offbyone_chorus_upper` | `Props.chorus`: `iota 1 n.-1` → `iota 1 n` (includes `d = n` itself) | **no** | n/a (build fails) | `Props.v` proof of `mem_chorus` no longer closes (`d = n` case gives `d \in chorus n = true` but `d < n = false`, contradicting the pinned RHS) — the theorem is genuinely false, not just a proof-script issue |
| M2 | `M2_triad_swap_take_rev` | `Step.triad`: `take 3 (rev (chorus n))` → `rev (take 3 (chorus n))` (three *smallest* members, reversed, instead of three largest) | **no** | n/a (build fails) | `Shrink.v` line 61 (`Cannot find witness`) and `Fixed.v` line 67 (`rev_cat` mismatch) — both required theorems become false for a general `n`/`m` |
| M3 | `M3_degenerate_odd_shrink` | `Step.tstep`: on odd `n`, instead of `sumn (triad n)`, use a stub `if n==15 then 9 else if n==27 then 13 else n.-1` (matches the only two odd `tstep` pins by name, junk everywhere else); even branch untouched | **yes** | **SOLVED — gate accepts it** | none — all 14 probes pass. `Shrink.tstep_shrink_odd` is now a 4-line trivial case split instead of the real combinatorial proof, because the theorem only pins `tstep n < n`, never an exact value, for any odd `n` outside {15, 27} |
| M4 | `M4_degenerate_even_nonfamily` | `Step.tstep`: on even `n`, real formula only if `n` is one of the 3 pinned values `{12,30,100}` or is genuinely in the `6*m`-family (`6 %\| n`, `odd (n/6)`, `~~(5 %\| (n/6))`); **`0`** for every other even `n` (e.g. `tstep 4 = 0`, real value would be `3`) | **yes** | **SOLVED — gate accepts it** | none — all 14 probes pass. `Fixed.tstep_fixed` and the odd branch of `Shrink` are untouched (still real math); the entire class of even non-family, non-pinned `n` is never touched by any probe or required lemma |
| M5 | `M5_wrong_divisibility_direction` | `Props.chorus`: `d %\| n` → `n %\| d` (divisibility direction swapped) | **no** | n/a (build fails) | `Props.v` `mem_chorus` proof fails immediately (`No applicable tactic`) — confirms `mem_chorus`+`chorus_sorted` really do pin `chorus` tightly; no version of this class of bug survives |
| M6 | `M6_triad_take2` | `Step.triad`: `take 3` → `take 2` (dyad instead of triad) | **no** | n/a (build fails) | `Fixed.v` line 67 and `Shrink.v` line 94: `take0` rewrite no longer applies — both general theorems become false (2-member sum isn't generally `6*m`, nor generally `< n`) |
| M7 | `M7_tstep_sum_all_chorus` | `Step.tstep`: `sumn (triad n)` → `sumn (chorus n)` (sum of the *whole* chorus, ignoring `take 3` entirely) | **no** | n/a (build fails) | `Shrink.v` line 61 / `Fixed.v` line 67 — both required theorems false in general (and would already fail probe `p_tstep12` numerically: `sumn (chorus 12) = 16 ≠ 13`) |
| M8 | `M8_degenerate_both` | Combines M3 + M4: real formula **only** at the 2 pinned odd values, the 3 pinned even values, and the `6*m` family; junk (`n.-1` / `0`) everywhere else | **yes** | **SOLVED — gate accepts it** | none — all 14 probes pass. The "worst case": a `tstep` that is mathematically meaningless outside a finite/pin-shaped set of inputs still gets a clean `solved: true` verdict |

Verdict JSON for every mutant above is saved next to this file as
`<mutant>.json` (`M1_offbyone_chorus_upper.json` … `M8_degenerate_both.json`).

## Survivors (probe gaps)

Three mutants are accepted by the current gate despite `Step.tstep` being
formalized wrongly (arbitrarily, even) on most inputs:

- **`M3_degenerate_odd_shrink`** — wrong/degenerate on almost all odd `n`.
- **`M4_degenerate_even_nonfamily`** — wrong/degenerate (constant `0`) on
  most even `n`.
- **`M8_degenerate_both`** — wrong/degenerate on almost *all* `n`
  simultaneously; only the handful of pinned/family inputs are real.

### Root cause

`Fixed.tstep_fixed` pins `tstep` by *equality* on the infinite family
`n = 6*m` (`m` odd, `0 < m`, `~~ (5 %\| m)`), which is airtight. But
`Shrink.tstep_shrink_odd` pins `tstep` on odd `n > 1` only by the
*inequality* `tstep n < n`, and the 8 concrete `vm_compute` pins cover only
`n ∈ {6, 12, 15, 27, 30, 42, 66, 100}` — leaving every other odd `n` (e.g.
`n = 3, 5, 7, 9, 11, 13, 17, 19, 21, 23, 25, 29, ...`) and every even `n`
not in the `6*m`-family and not individually pinned (e.g. `n = 2, 4, 8, 10,
14, 16, 20, 22, 24, ...`) completely unconstrained. A submission can return
essentially anything on those inputs — including a value with no relation
to the actual "triad step" — as long as it stays below `n` when `n` is odd,
and the gate will still call it solved.

### Suggested probes to close the gap

Add `vm_compute` pins that break the "special-case the pinned points,
default elsewhere" strategy by hitting *unpinned* representative inputs on
both sides of the odd/even split, e.g. (values are the real, correct
`tstep`):

```coq
(* kill M3 / M8: an odd value that is not in {15, 27} *)
Example p_tstep21 : Step.tstep 21 = 11.
Proof. vm_compute; reflexivity. Qed.
(* chorus 21 = [1;3;7]; triad = [7;3;1]; sum = 11 -- checked against the
   reference build with `rocq repl`/vm_compute, not just hand arithmetic. *)

(* kill M4 / M8: an even value that is neither pinned nor in the 6*m family *)
Example p_tstep8 : Step.tstep 8 = 7.
Proof. vm_compute; reflexivity. Qed.
(* chorus 8 = [1;2;4]; triad = [4;2;1]; sum = 7 -- also checked against the
   reference build. *)
```

Both right-hand sides above (`11` and `7`) were computed by loading the
compiled reference `TaskLib` into `rocq repl` and `vm_compute`ing
`Step.tstep 21` / `Step.tstep 8` directly, not by hand arithmetic. Two such
additional pins at odd/even values outside the current pinned set (and
outside the `6*m`-family for the even one) would force `tstep`/`triad` to
be genuinely correct on ordinary inputs, not just on the family the meaty
theorem already covers plus a finite pinned set.

## Notes

- All 8 mutants avoid `admit`/`Admitted`/`Axiom`; the 5 non-buildable ones
  are non-buildable because the *theorem itself* becomes false under the
  mutation, not because of a fixable proof-script issue — repair was not
  possible without reverting the mutation.
- Mutant sources live under
  `/private/tmp/claude-501/-Users-gbaudart-Project-llm4rocq-rocq-tools/92fd7af9-6dfb-42f7-ad3c-3a89b1b13ece/scratchpad/mut-triadic/<mutant>/`
  (scratch only, not committed).

## Verification

Re-audit of the three reported survivors against `spec.md`'s "Required
names (exact)" section, which pins `Step.tstep` as "defined as
`sumn (triad n)`" — an unconditional, unqualified definition, not one that
carves out exceptions for specific inputs or families. All three mutants
replace that definition with a case split that special-cases only the
pinned/family points and falls back to arbitrary junk (`n.-1` or `0`)
everywhere else, which is a direct violation of the stated meaning of the
required name, not a spec ambiguity the task leaves open. Each verdict JSON
was re-read and each mutant's `Step.v` source (still present under
`<scratch>/mut-triadic/<mutant>/`, `<scratch>` =
`/private/tmp/claude-501/-Users-gbaudart-Project-llm4rocq-rocq-tools/92fd7af9-6dfb-42f7-ad3c-3a89b1b13ece/scratchpad`)
was diffed against the reference and confirmed to match the README's
description of the mutation exactly (see below). All three are classified
**GENUINE**.

| mutant | verdict JSON | classification | reason |
|---|---|---|---|
| `M3_degenerate_odd_shrink` | `{"solved": true, ...}` (re-confirmed) | **GENUINE** | `Step.tstep` on odd `n` is a 3-way stub (`n==15`/`n==27`/else `n.-1`) instead of `sumn (triad n)`, matching the README's description exactly (diffed against `theories/Step.v`). This contradicts the spec's exact required definition of `Step.tstep` for every odd `n ∉ {15, 27}`. The gate accepts it only because `Shrink.tstep_shrink_odd` pins solely the inequality `tstep n < n`, which `n.-1 < n` satisfies trivially. |
| `M4_degenerate_even_nonfamily` | `{"solved": true, ...}` (re-confirmed) | **GENUINE** | `Step.tstep` on even `n` is `sumn (triad n)` only at the 3 pinned values or the genuine `6*m` family, else the constant `0`, matching the README's description exactly. This contradicts the spec's exact required definition of `Step.tstep` for every even `n` outside the pinned/family set (e.g. `n = 8`, real value `7`, mutant value `0`). No probe or required lemma ever touches this class. |
| `M8_degenerate_both` | `{"solved": true, ...}` (re-confirmed) | **GENUINE** | Combines M3's odd stub and M4's even stub verbatim (diff confirms `Step.v` is literally the union of the two), so it inherits both violations above simultaneously — `Step.tstep` is the real `sumn (triad n)` only on the finite pinned/family set and arbitrary junk everywhere else. |

### Killing probes (checked)

Both probes below were checked against a fresh sandbox build of the
reference (`<scratch>/verify-mut-triadic/ref`, `dune build --root .`,
succeeded) and against fresh sandbox builds of each mutant
(`<scratch>/mut-triadic/<mutant>`, each already built by the original
mutation run). Each probe was compiled with
`rocq compile -Q <theory_dir> TaskLib killing_probes.v`, exactly as the
gate invokes probes.v:

- Against the **reference** theory dir: both probes compile and pass
  (`rocq compile` exit 0).
- Against **M3**'s theory dir: `p_tstep21` fails to compile
  (`Error: Unable to unify "11" with "20".` — the mutant's odd-branch stub
  returns `n.-1 = 20` for `n = 21`, not the real triad sum `11`); overall
  `rocq compile` exit 1.
- Against **M4**'s theory dir: `p_tstep8` fails to compile
  (`Error: Unable to unify "7" with "0".` — the mutant's even-branch falls
  through to the constant `0` for `n = 8`, not the real triad sum `7`);
  overall `rocq compile` exit 1.
- Against **M8**'s theory dir: `p_tstep21` fails the same way as against
  M3 (`Unable to unify "11" with "20"`); overall `rocq compile` exit 1.
  `p_tstep8` was also checked in isolation against M8 and independently
  fails the same way as against M4 (`Unable to unify "7" with "0"`,
  `rocq compile` exit 1) — M8's even branch is identical to M4's.

```coq
From TaskLib Require Import Props Step Fixed Shrink.
From mathcomp Require Import all_ssreflect all_algebra.

(* kills M3_degenerate_odd_shrink / M8_degenerate_both: an odd value not in
   the pinned set {15, 27} that the degenerate odd branch mishandles. *)
Example p_tstep21 : Step.tstep 21 = 11.
Proof. vm_compute; reflexivity. Qed.

(* kills M4_degenerate_even_nonfamily / M8_degenerate_both: an even value
   that is neither individually pinned nor in the 6*m family. *)
Example p_tstep8 : Step.tstep 8 = 7.
Proof. vm_compute; reflexivity. Qed.
```

Both right-hand sides (`11` for `n = 21`, `7` for `n = 8`) were confirmed
by `vm_compute` against the sandboxed reference build, not by hand
arithmetic — `chorus 21 = [1; 3; 7]`, triad `[7; 3; 1]`, sum `11`;
`chorus 8 = [1; 2; 4]`, triad `[4; 2; 1]`, sum `7`. These are the same two
probes the original README's "Suggested probes" section proposed; this
verification pass re-derived and independently re-checked them against
live sandbox builds rather than taking the proposal on faith.
