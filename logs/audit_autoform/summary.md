# Strict re-check of the autoform campaign (A130, method 1)

462 attempts audited.

| run | model | n | original_solved | strict_solved | agree | gate_unsound | gate_stricter | ext_mismatch | toolchain | ext_ok | ext_fail | ext_timeout | timed_out | flagged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| af2_base | claude-sonnet-5 | 20 | 11 | 11 | 20 | 0 | 0 | 0 | 0 | 11 | 0 | 0 | 0 | 2 |
| af2_evolve | claude-sonnet-5 | 20 | 7 | 8 | 19 | 0 | 1 | 0 | 0 | 11 | 0 | 0 | 0 | 10 |
| af2_sota | claude-sonnet-5 | 20 | 2 | 2 | 20 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 2 |
| af3_base | claude-sonnet-5 | 20 | 10 | 10 | 19 | 0 | 0 | 0 | 1 | 10 | 0 | 0 | 1 | 3 |
| af3_base2 | claude-sonnet-5 | 20 | 12 | 12 | 20 | 0 | 0 | 0 | 0 | 12 | 0 | 0 | 0 | 1 |
| af3_evolve | claude-sonnet-5 | 20 | 14 | 15 | 19 | 0 | 1 | 0 | 0 | 19 | 0 | 0 | 0 | 6 |
| af3_evolve_c3 | claude-sonnet-5 | 20 | 14 | 14 | 20 | 0 | 0 | 0 | 0 | 17 | 0 | 0 | 0 | 7 |
| af3_evolve_r1 | claude-sonnet-5 | 20 | 15 | 15 | 20 | 0 | 0 | 0 | 0 | 18 | 0 | 0 | 0 | 7 |
| af3_evolve_r3 | claude-sonnet-5 | 20 | 15 | 15 | 20 | 0 | 0 | 0 | 0 | 19 | 0 | 0 | 0 | 5 |
| af3_sota | claude-sonnet-5 | 20 | 12 | 12 | 20 | 0 | 0 | 0 | 0 | 12 | 0 | 0 | 0 | 1 |
| mst3_base | mistral-large-latest | 20 | 0 | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| mst3_evolve | mistral-large-latest | 20 | 0 | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| mst3_sota | mistral-large-latest | 20 | 0 | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| mst3_sota_v2 | mistral-large-latest | 20 | 0 | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| mst_base | mistral-medium-latest | 20 | 0 | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| mst_evolve | mistral-medium-latest | 20 | 0 | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| op_base | claude-opus-4-8 | 10 | 3 | 3 | 10 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| op_evolve | claude-opus-4-8 | 10 | 6 | 6 | 10 | 0 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 1 |
| op_sota | claude-opus-4-8 | 10 | 6 | 6 | 10 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 0 |
| orp3_base | openai/gpt-5.6-terra | 20 | 10 | 10 | 18 | 0 | 0 | 2 | 0 | 10 | 2 | 0 | 0 | 3 |
| orp3_evolve | openai/gpt-5.6-terra | 20 | 12 | 12 | 18 | 0 | 0 | 2 | 0 | 13 | 2 | 0 | 0 | 3 |
| orp3_sota | openai/gpt-5.6-terra | 20 | 7 | 7 | 20 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 1 |
| w2_base_sonnet | claude-sonnet-5 | 8 | 5 | 5 | 8 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 |
| w2_prover2_sonnet | claude-sonnet-5 | 8 | 4 | 4 | 8 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 3 |
| w2_prover_sonnet | claude-sonnet-5 | 8 | 7 | 7 | 8 | 0 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 0 |
| w2_sota_sonnet | claude-sonnet-5 | 8 | 1 | 1 | 8 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 2 |
| w2_sota_unfair | claude-sonnet-5 | 8 | 2 | 2 | 8 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 1 |
| w2_team_sonnet | claude-sonnet-5 | 4 | 2 | 2 | 4 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 1 |
| w2_verify_sonnet | claude-sonnet-5 | 8 | 4 | 4 | 8 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 3 |
| ALL |  | 462 | 181 | 183 | 455 | 0 | 2 | 4 | 1 | 207 | 4 | 0 | 1 | 64 |

Counted (toolchain rows excluded): n=461, agree=459, gate_unsound=0, gate_stricter=2 (of which ext_mismatch=4 pass probes.v but fail probes_ext.v).

## Review flags (recorded, never deciding)

- `forbidden_token`: 54
- `guard_checking`: 6
- `n_theory_roots`: 10

## Rows that are not `agree`

| category | run | task | rep | original | strict | reason | killed |
|---|---|---|---|---|---|---|---|
| ext_mismatch | orp3_base | triadic | 0 | True/ok | True | ok | - |
| ext_mismatch | orp3_base | triadic | 3 | True/ok | True | ok | - |
| ext_mismatch | orp3_evolve | prodauto | 0 | True/ok | True | ok | - |
| ext_mismatch | orp3_evolve | triadic | 3 | True/ok | True | ok | - |
| gate_stricter | af2_evolve | ledger | 1 | False/forbidden_token | True | ok | - |
| gate_stricter | af3_evolve | ledger | 3 | False/forbidden_token | True | ok | - |
| toolchain | af3_base | ledger | 1 | False/build_failed | False | build_timeout | build:1800s |

## Toolchain

- rocq: `The Rocq Prover, version 9.1.1`
- dune: `3.23.1`
- dev commit: `f9b4acb A130 tooling: strict assumptions checker (Rocq API), audit driver, reference-derived extended probes, mutation and protocol scripts`
- data/autoform content hash: `ef68e18619cbe0a2`
- packages:

  - `coq-elpi                     3.4.0`
  - `coq-mathcomp-algebra         2.5.0`
  - `coq-mathcomp-algebra-tactics 1.2.7`
  - `coq-mathcomp-analysis        1.16.0`
  - `coq-mathcomp-ssreflect       2.5.0`
  - `coq-mathcomp-zify            1.6.0+2.3+8.18`
  - `rocq-core                    9.1.1`
  - `rocq-elpi                    3.4.0`
  - `rocq-hierarchy-builder       1.10.3`
  - `rocq-mathcomp-algebra        2.5.0`
  - `rocq-mathcomp-analysis       1.16.0`
  - `rocq-mathcomp-bigenough      1.0.4`
  - `rocq-mathcomp-boot           2.5.0`
  - `rocq-mathcomp-classical      1.16.0`
  - `rocq-mathcomp-field          2.5.0`
  - `rocq-mathcomp-fingroup       2.5.0`
  - `rocq-mathcomp-finmap         2.2.2`
  - `rocq-mathcomp-order          2.5.0`
  - `rocq-mathcomp-reals          1.16.0`
  - `rocq-mathcomp-solvable       2.5.0`
  - `rocq-mathcomp-ssreflect      2.5.0`
  - `rocq-prover                  meta.1`
  - `rocq-runtime                 9.1.1`
  - `rocq-stdlib                  9.0.0`
  - `rocq-tools                   dev`
