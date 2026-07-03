# rocq-tools — an AI-native tooling layer for the Rocq prover

An empirical study: design the tool interface an LLM agent uses to drive the
Rocq prover, iterate it change-by-change against measured baselines, and back
every design decision with numbers. Built as a standalone OCaml project on the
installed Rocq 9.1 OCaml libraries (no source changes to Rocq).

**Start here**: [`STATUS.md`](STATUS.md) (current state, 2-minute read) ·
[`docs/REPORT.md`](docs/REPORT.md) (results) ·
[`docs/DESIGN.md`](docs/DESIGN.md) (per-decision rationale + numbers) ·
[`docs/TASK.md`](docs/TASK.md) (original brief) ·
[`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md) (autonomous decisions log A1–A15).

## Headline results (details + variance in the report)

- Fixed weak policy (claude-haiku-4-5), dev60 pass@1 easy/medium/hard:
  **baseline .44/.25/.30 → winner .70/.525/.425** at −45 % cost, −55 % wall,
  via 6 kept + 4 reverted measured interface changes.
- Per-interaction prover latency: 266 ms (full recompile) → **~1 ms**
  (persistent in-process session, snapshot rollback).
- **Interface efficiency compounds under parallelism**: winner scales
  near-linearly to N=8 agents (baseline saturates at N=2) — 19× solved
  proofs/hour at N=8.
- **The optimal interface is policy-dependent** (§5b): a strong policy
  (claude-sonnet-5) one-shots via the naive interface; the session substrate
  still cuts its cost ~30 %. Same substrate, per-policy prompting.
- Intra-proof multi-agent teaming (shared-proof daemon, branch-per-subgoal,
  merge-by-replay): infrastructure validated; **negative result** at equal
  wall-clock on competition problems (they rarely decompose) — kept honestly.

## Layout

```
src/mcp_core/        MCP stdio server framework + subprocess util (OCaml)
src/baseline_server/ naive control: one `check` tool = full rocq compile
src/session_server/  the iterated interface: step/try/rollback/state/search/
                     auto_close + hints, did-you-mean, env-v2 preloading
src/psession/        shared-proof daemon (k agents on one live proof) + MCP shim
harness/             eval runner, correctness gate, team orchestrator, report,
                     profiler, monitor, dashboard, plots, sweeps, manifests
configs/             one JSON per experimental condition + FROZEN.md
data/manifests/      stratified problem manifests (dev60/dev150/hard70/…)
docs/                task brief, report, design rationale, assumptions, figures
repro/               pinned package list + one-command environment recreation
logs/                runs, JSONL instrumentation, dashboard (gitignored)
```

## Reproduce

```sh
./repro/setup.sh /path/for/new/switch   # fresh opam switch -> pinned deps ->
                                        # build -> MCP self-test
python3 harness/run_eval.py --config baseline --manifest smoke5 --reps 1
python3 harness/report.py <run_id>      # every reported number comes from this
python3 harness/dashboard.py --watch &  # live view: logs/dashboard.html
```

Datasets are expected as siblings of this repo (`rocq-workbook/`,
`miniF2F-rocq/`); the policy endpoint is an authenticated `claude` CLI.
The held-out split is guarded: code refuses to read `miniF2F-rocq/test`
unless `FINAL_UNLOCK` + `ROCQ_FINAL_EVAL=1` are set; the single unlock is
logged in `logs/unlock.log` (see `configs/FROZEN.md`).

## Method in one paragraph

One deliberately-naive control; profile; one change at a time; keep only what
improves per-bucket dev numbers (never pooled); every attempt gated by an
anti-gaming checker (locked statement prefix, forbidden tokens, fresh-dir
recompile, `Print Assumptions` audit); all interactions logged as JSONL;
every number in the report reproducible by one command from raw logs; freeze,
then a single logged evaluation on the held-out split.
