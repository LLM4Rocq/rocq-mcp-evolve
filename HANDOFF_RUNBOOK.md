# RUNBOOK — completion without strong supervision (written 2026-07-12)

> 2026-09-03 (trail A128): branches are now `main` (the frozen artifact, formerly
> `autoform-experiments`) and `dev` (evolutions, formerly `dev-rocq-api`). The
> Step 4 merge procedure below was executed on 2026-07-15 and is kept for the
> record only.

For the successor session (any model). This project has a history of
plausible-but-wrong turns that cost days. Therefore: **your job is to
EXECUTE this runbook, not to improve it.** Every decision below is already
made and trail-cited. If something unlisted goes wrong: record it in
docs/ASSUMPTIONS.md (next A-number), do the minimal safe action, stop.

## Standing DO-NOTs (violations have burned us; all trail-cited)
- DO NOT `git checkout` / switch branches in this working tree while any
  chain is running (the running processes read tracked files from it).
- DO NOT re-run, tune, or "improve" any FINAL_* arm. No second look
  (FROZEN.md). The sole permitted repairs: machine_slept and quota-429
  slots (A83), via quarantine + identical-slot redo.
- DO NOT design new experiments, rungs, features, or protocols. The
  evolution arc is CLOSED (A68 rules apply if anyone reopens it later).
- DO NOT hand-compute reported numbers. Scripts only (below). If a
  script refuses, fix the stated cause; never --force into any report.
- DO NOT push any branch. Local commits only.
- DO NOT run heavy builds while measured arms run (wall integrity).
- Infrastructure claims about attempts REQUIRE event-subtype anatomy:
  system/thinking_tokens events ARE model activity (a thinking-only
  attempt is a legitimate failure, A92). Truly dead = no result, no
  assistant, no thinking_tokens.
- Costs: never trust results.jsonl cost fields for killed attempts;
  recovery is inside the scripts.

## State (2026-07-12)
- CHAIN STATE (updated 2026-07-15, post-A99): the ORIGINAL six-arm
  held-out campaign is COMPLETE (registered look taken, A96; table
  archived). NOW IN FLIGHT: the A99 bridged sibling remeasurement chain
  (dev60 fair2 pair -> FINAL_pf_rocqmcp_sonnet), log logs/a99_chain.log.
  On completion: final_tables.py (now 7 arms) is the registered look for
  the NEW arm only; report.py for the fair2 dev rows; disclosure prose
  per WAVE2_STATUS. Same DO-NOTs apply; the supersession rule is in A99
  and is NOT renegotiable after data.
- QUEUED BEHIND IT (A100, registered): when the A99 chain has EXITED and
  `pgrep -f run_eval.py` is empty, launch the wall-only haiku rerun:
    nohup caffeinate -dims sh -c 'ROCQ_FINAL_EVAL=1 python3 -u \
      harness/run_eval.py --config frozen_wallonly --manifest minif2f_test \
      --reps 2 --parallel 4 --run-id FINAL_frozen_wallonly' \
      > logs/a100_haiku.log 2>&1 &
  (Do NOT run it concurrently with the A99 chain. Supersession per A100.)
- QUEUED BEHIND A100 (A101, registered): when A100 has exited and
  `pgrep -f run_eval.py` is empty:
    nohup caffeinate -dims sh -c 'python3 -u harness/run_eval.py \
      --config universal_c30 --manifest dev60 --reps 4 --parallel 4 \
      --run-id universal_c30_dev60' > logs/a101_universal_c30.log 2>&1 &
  Then the SINGLE post-campaign update pass: final_tables.py (8 arms),
  report.py for fair2 + universal_c30 dev rows, and the A98/A99/A100/A101
  disclosure prose across README, REPORT, dashboard, and the surfaces in
  the session memory handoff — numbers from scripts only, one commit set,
  text shown to the user first.
- SUPERSEDED (2026-07-14): everything COMPLETE and valid EXCEPT pf pair. A single detached chain runs
  pf_baseline (262 slots left after the A93 quarantine) -> pf_session
  (488), parallel 8, log logs/pf_chain2.log (wrapper pid 5072, python
  pid 5074). All runs resumable; runner parks on 429s and true dead
  streams (A92 thinking-aware) and wipes stale grading artifacts at
  attempt start (A93). When final_tables.py stops refusing, everything
  is done. The A89-era trio/dev "dead-stream repairs" were RETRACTED
  (A92): those arms were already complete; do not rerun them.
- LAUNCH HYGIENE (A93, binding): before launching ANY runner,
  `pgrep -f run_eval.py` must return NOTHING. To stop a chain, kill the
  PYTHON pid (pgrep -f run_eval.py), not just the wrapper sh — a
  surviving child caused the A93 double-sampling. Laptop must be on AC
  power (caffeinate does not survive battery exhaustion).
- FINAL chain (original; superseded by the above):
  sequential arms baseline(repair) -> session -> rocqmcp -> pf_baseline ->
  pf_session on minif2f_test. Quota-aware (parks 20min on 429 and redoes
  the slot). ETA ~Mon 2026-07-13 pm + quota parks.
- Follow-on duties for successor sessions are deliberately NOT tracked
  in this repo: see the session memory handoff.
- main already carries the merged branch state as of this runbook's
  commit; later commits land on autoform-experiments (merge again at the
  very end, same --no-ff procedure via a temporary worktree).

## Step 1 — when the chain exits (pid 32566 gone)
    cd /Users/gbaudart/Project/llm4rocq/rocq-tools/rocq-tools
    tail -20 logs/final_repair_chain.log        # expect all five arms "done"
    python3 harness/final_tables.py             # integrity gates run here
If it REFUSES: it names the exact run and cause.
  - "INCOMPLETE" -> re-invoke the exact run_eval command for that arm from
    logs/final_repair_chain.log header (the runner resumes missing slots).
  - "LIVE quota-poisoned" -> quarantine per A83: move those rows to
    results.quarantine.jsonl, park transcripts as *.poisoned.jsonl, rerun
    the same run_eval command (it redoes only missing slots).
  - "machine_slept" -> python3 harness/repair_run.py <run_id>, then rerun
    the same run_eval command.
Repeat Step 1 until final_tables.py prints the table.

## Step 2 — universal_dev60 repair (DONE 2026-07-14, A94)
The repair and the lockstep recompute are COMPLETE (commit for A94):
README/REPORT/site/figures all carry the repaired dev numbers
(universal hard .463; rocq-mcp fair sonnet hard .825). Do NOT redo this
step; the original instructions are kept below only for provenance.

## Step 2 (historical) — universal_dev60 repair (14 slots, haiku, ~20min; A84e)
    cd /Users/gbaudart/Project/llm4rocq/rocq-tools/rocq-tools
    ROCQ_FINAL_EVAL=1 python3 -u harness/run_eval.py --config universal \
        --manifest dev60 --reps 4 --parallel 4 --run-id universal_dev60
(Resumable: only the 14 quarantined slots run. If config name differs,
check logs/runs/universal_dev60/run_meta.json "config".)
Then recompute the dev headline row:
python3 - <<'PYEOF'
import json, sys; sys.path.insert(0,'harness'); import common
rows = common.read_jsonl(common.LOGS/'runs'/'universal_dev60'/'results.jsonl')
for b in ('easy','medium','hard'):
    pr = {}
    for r in rows:
        if r['difficulty']==b: pr.setdefault(r['problem_id'],[]).append(r)
    n=len(pr); k=sum(1 for v in pr.values() if v[0]['solved'])
    print(b, f"pass@1 {k}/{n} = {k/n:.3f}")
PYEOF
LOCKSTEP RULE (A84d/A84e): update the README.md headline row + the
trail entry IN ONE COMMIT, and mirror any further surfaces listed in the
session memory handoff. If numbers unchanged, say so in the trail.

## Step 3 — export the results
- Run harness/final_tables.py; archive logs/final_heldout_table.json.
- Report ONLY what the script emits: per-bucket pass@1 with CIs, pass@2,
  cost/latency/kill columns. No significance language beyond the script's
  output.
- Remaining downstream steps: session memory handoff.

## Step 4 — trail + status + final merge
- Append the completion entry to docs/ASSUMPTIONS.md (next A-number):
  arm totals, poisoning census results, repairs performed.
- Add the held-out result line to README (phase-2 section) and refresh
  STATUS.md (still phase-1-only) — numbers strictly from final_tables.py
  output, nothing hand-computed.
- HISTORY HYGIENE (before the merge, chain must be DEAD, user approval
  required as for the A85/A86 rewrites): one git filter-repo pass over
  the branch with --replace-message and --replace-text mapping the two
  residual tokens found in the 2026-07-14 audit — the compound word
  "report-critical" (commit 935c3f4's message and its ASSUMPTIONS blob;
  now "report-critical") and the A85-entry wording replaced by commit
  eb9beed ("destination..." phrasing) — so pre-fix blobs/messages match the
  A86 rule. Verify with: git log --all -i --grep of those tokens plus a
  git grep over all revs; then re-run the freeze-provenance hash check.
- Update WAVE2_STATUS.md: mark held-out complete; it stays until the final
  merge, then delete it in the merge commit.
- Final merge WITHOUT touching this tree:
    git worktree add /tmp/main-merge main
    cd /tmp/main-merge && git merge --no-ff autoform-experiments \
        -m "phase 2 complete: held-out results + artifacts"
    cd - && git worktree remove /tmp/main-merge
- DO NOT push.

## Optional (only if the user says time+tokens remain — A84b)
baseline_fable_dev60 (1 slot), team_decomposable (29 slots), opus miniF2F
trio (restore configs from configs/deferred/), reciprocal eval (A59b).

## Contacts with reality
Decision trail: docs/ASSUMPTIONS.md (A1-A87+). Live status: WAVE2_STATUS.md.
Failure atlas: docs/FAILURE_ATLAS_AUTOFORM.md. Ops hazards: memory ops-rules
(watcher deadlocks, pipestatus, cwd resets, quota poisoning).
