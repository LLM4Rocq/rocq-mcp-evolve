# A130 method (5): protocol checks

29 in-scope runs checked. Toolchain: The Rocq Prover, version 9.1.1
compiled with OCaml 5.3.0 / 3.23.1 / dev-audit commit 71b2bfe2e5be1c139844a2cb041700ac47d92249

## (a) reference/ path reads in transcripts

No transcript or server log line in any of the 29 runs contains a tool call/file path matching `reference/`, `/reference`, or a `reference` path component. No reference/ read found.


## (b) results.jsonl vs verdict.json

Disagreements: 0. Attempts missing verdict.json (killed at the wall): 1.

### Missing verdict.json

- af3_base/ledger__rep1: no verdict.json (killed at the wall / no build produced)

## (c) A75 regrades: trigger class + current gate

8 regrade rows checked.

| run | attempt | in trigger class | # coq.theory dune files | passes current gate |
|---|---|---|---|---|
| af2_base | frugal__rep3 | True | 2 | True |
| af2_base | gauges__rep0 | True | 2 | True |
| af3_base | ledger__rep3 | True | 2 | True |
| af3_evolve | frugal__rep0 | True | 2 | True |
| af3_evolve_c3 | frugal__rep0 | True | 2 | True |
| af3_evolve_r1 | frugal__rep2 | True | 2 | True |
| af3_evolve_r1 | prodauto__rep1 | True | 2 | True |
| af3_evolve_r1 | prodauto__rep2 | True | 2 | True |

## (d) Toolchain

- rocq: `The Rocq Prover, version 9.1.1
compiled with OCaml 5.3.0`
- dune: `3.23.1`
- dev-audit worktree commit: `71b2bfe2e5be1c139844a2cb041700ac47d92249`
- opam list (rocq-*/coq-*/dune):
```
coq                          9.1.1          Compatibility metapackage for Coq after the Rocq renaming
coq-coquelicot               3.4.4          A Coq formalization of real analysis compatible with the standard library
coq-core                     9.1.1          Compatibility binaries for Coq after the Rocq renaming
coq-elpi                     3.4.0          Compatibility metapackage for Elpi extension language after the Rocq renaming
coq-lsp                      0.2.5+9.1      Language Server Protocol native server for Coq
coq-mathcomp-algebra         2.5.0          Compatibility package for rocq-mathcomp-algebra
coq-mathcomp-algebra-tactics 1.2.7          Ring, field, lra, nra, and psatz tactics for Mathematical Components
coq-mathcomp-analysis        1.16.0         Compatibility package for rocq-mathcomp-analysis
coq-mathcomp-ssreflect       2.5.0          Compatibility package for rocq-mathcomp-ssreflect
coq-mathcomp-zify            1.6.0+2.3+8.18 Micromega tactics for Mathematical Components
coq-stdlib                   9.0.0          Compatibility metapackage for Coq Stdlib library after the Rocq renaming
dune                         3.23.1         Fast, portable, and opinionated build system
rocq-core                    9.1.1          The Rocq Prover with its prelude
rocq-elpi                    3.4.0          Elpi extension language for Coq
rocq-hierarchy-builder       1.10.3         High level commands to declare and evolve a hierarchy based on packed classes
rocq-mathcomp-algebra        2.5.0          Mathematical Components Library on Algebra
rocq-mathcomp-analysis       1.16.0         An analysis library for mathematical components
rocq-mathcomp-bigenough      1.0.4          A small library to do epsilon - N reasoning
rocq-mathcomp-boot           2.5.0          Small Scale Reflection
rocq-mathcomp-classical      1.16.0         A library for classical logic for mathematical components
rocq-mathcomp-field          2.5.0          Mathematical Components Library on Fields
rocq-mathcomp-fingroup       2.5.0          Mathematical Components Library on finite groups
rocq-mathcomp-finmap         2.2.2          Finite sets, finite maps, finitely supported functions
rocq-mathcomp-order          2.5.0          Mathematical Components Library on order theory
rocq-mathcomp-reals          1.16.0         A library for real numbers for mathematical components
rocq-mathcomp-solvable       2.5.0          Mathematical Components Library on finite groups (II)
rocq-mathcomp-ssreflect      2.5.0          Compatibility package for rocq-mathcomp-boot and rocq-mathcomp-order
rocq-prover                  meta.1         The Rocq Prover with Stdlib
rocq-runtime                 9.1.1          The Rocq Prover -- Core Binaries and Tools
rocq-stdlib                  9.0.0          The Rocq Proof Assistant -- Standard Library
rocq-tools                   dev            pinned to version dev at git+https://github.com/LLM4Rocq/rocq-tools.git
```

## (e) Per-run table

| run | model | reps | max_turns | timeout_s | attempts | results rows | solved (results.jsonl) | disagreements | missing verdict |
|---|---|---|---|---|---|---|---|---|---|
| af2_base | claude-sonnet-5 | 4 | 40 | 900 | 20 | 20 | 9 | 0 | 0 |
| af2_evolve | claude-sonnet-5 | 4 | 40 | 900 | 20 | 20 | 7 | 0 | 0 |
| af2_sota | claude-sonnet-5 | 4 | 40 | 900 | 20 | 20 | 2 | 0 | 0 |
| af3_base | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 9 | 0 | 1 |
| af3_base2 | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 12 | 0 | 0 |
| af3_evolve | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 13 | 0 | 0 |
| af3_evolve_c3 | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 13 | 0 | 0 |
| af3_evolve_r1 | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 12 | 0 | 0 |
| af3_evolve_r3 | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 15 | 0 | 0 |
| af3_sota | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 12 | 0 | 0 |
| mst3_base | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 0 | 0 | 0 |
| mst3_evolve | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 0 | 0 | 0 |
| mst3_sota | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 0 | 0 | 0 |
| mst3_sota_v2 | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 0 | 0 | 0 |
| mst_base | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 0 | 0 | 0 |
| mst_evolve | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 0 | 0 | 0 |
| op_base | claude-opus-4-8 | 2 | 200 | 900 | 10 | 10 | 3 | 0 | 0 |
| op_evolve | claude-opus-4-8 | 2 | 200 | 900 | 10 | 10 | 6 | 0 | 0 |
| op_sota | claude-opus-4-8 | 2 | 200 | 900 | 10 | 10 | 6 | 0 | 0 |
| orp3_base | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 10 | 0 | 0 |
| orp3_evolve | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 12 | 0 | 0 |
| orp3_sota | claude-sonnet-5 | 4 | 200 | 900 | 20 | 20 | 7 | 0 | 0 |
| w2_base_sonnet | claude-sonnet-5 | 2 | 40 | 900 | 8 | 8 | 5 | 0 | 0 |
| w2_prover2_sonnet | claude-sonnet-5 | 2 | 40 | 900 | 8 | 8 | 4 | 0 | 0 |
| w2_prover_sonnet | claude-sonnet-5 | 2 | 40 | 900 | 8 | 8 | 7 | 0 | 0 |
| w2_sota_sonnet | claude-sonnet-5 | 2 | 40 | 900 | 8 | 8 | 1 | 0 | 0 |
| w2_sota_unfair | claude-sonnet-5 | 2 | 40 | 900 | 8 | 8 | 2 | 0 | 0 |
| w2_team_sonnet | claude-sonnet-5 | 1 | 40 | 900 | 4 | 4 | 2 | 0 | 0 |
| w2_verify_sonnet | claude-sonnet-5 | 2 | 40 | 900 | 8 | 8 | 4 | 0 | 0 |
