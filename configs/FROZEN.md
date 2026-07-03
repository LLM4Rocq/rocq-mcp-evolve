# Frozen configuration — locked 2026-07-03

**Config**: `configs/frozen.json` = the final solo ladder winner
(`session_try_hints_auto_sugg`) + environment v2. Interface: persistent
in-process prover session with `step` / `rollback` / `state` / `try` /
`auto_close` (+ error hints, did-you-mean suggestions, Lia/Lra/Psatz
preloaded, `Require` refused). Selected on dev sets only via 6 kept and 4
reverted measured changes (docs/DESIGN.md; per-step numbers in
docs/REPORT.md).

**Policy (fixed)**: `claude-haiku-4-5` via claude CLI headless, MCP tools
only, ≤30 turns, ≤300 s wall per attempt, parallel=4.

**Frozen at git revision**: `dd583bf50f3165ad836b17fed7745ad3f7e9912a`
(+ this freeze commit). Substrate: Rocq 9.1.1 / OCaml 5.3.0, pinned in
`repro/opam-packages.txt`; environment recreated by `repro/setup.sh`.

## Held-out procedure (run exactly once, after this file is committed)

1. `touch FINAL_UNLOCK` at the repo root (mechanical guard; the unlock is
   logged to `logs/unlock.log` by `harness/datasets.py`).
2. Generate the test manifest at unlock time (the guard makes this the first
   moment test files can be read):
   `ROCQ_FINAL_EVAL=1 python3 harness/make_test_manifest.py`
3. Single evaluation, 2 reps for pass@1/pass@2:
   `ROCQ_FINAL_EVAL=1 caffeinate -dims python3 harness/run_eval.py \
      --config frozen --manifest minif2f_test --reps 2 --parallel 4 \
      --run-id FINAL_minif2f_test`
4. Report per bucket; no reruns, no tuning, no second look. Sleep-contaminated
   attempts (machine_slept) are the sole permitted repair (redo of the
   identical slot via harness/repair_run.py), per the pre-registered protocol.

## Anti-gaming gate (unchanged, applies to the final run)
Locked prefix · forbidden-token region scan · fresh-dir recompile with the
standard `-ri` injection · Print Assumptions audit. Rejection reasons logged.
