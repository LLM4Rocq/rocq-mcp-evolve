#!/usr/bin/env python3
"""A114: finisher-only zero-model arm. No LLM. Fixed policy: call
rocq__auto_close until 'no finisher applies' / goals closed / 10 calls /
wall 300s; grade work/candidate.v via the standard gate.

    python3 harness/finisher_only.py --config af_pf_session2 \
        --manifest minif2f_test --parallel 8 --run-id finisher_only_test
"""
import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import common
import gate
import datasets
from run_eval import build_task
from mistral_prover import server_env
from mistral_driver import McpServer

MAX_CALLS = 10
WALL = 300


def run_attempt(cfg, rec, run_dir):
    aid = f"{rec['problem_id']}__rep0"
    adir = run_dir / "attempts" / aid
    work = adir / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "candidate.v").unlink(missing_ok=True)
    prefix, thm = build_task(rec)
    if cfg.get("prefix_prepend"):
        prefix = cfg["prefix_prepend"] + prefix
    (adir / "task_prefix.v").write_text(prefix)

    env = server_env(cfg, work, adir, rec)
    spec = {"command": cfg["server"]["command"].replace("{repo}", str(common.REPO)),
            "args": cfg["server"].get("args", []), "env": env}
    t0 = time.time()
    calls = 0
    outcome = "wall"
    tf = open(adir / "transcript.jsonl", "w")
    tf.write(json.dumps({"type": "init", "model": "NONE(finisher-only)",
                         "policy": f"auto_close x<= {MAX_CALLS}",
                         "ts": t0}) + "\n")
    try:
        srv = McpServer("rocq", spec, cwd=str(adir))
        srv.handshake()
        while calls < MAX_CALLS and time.time() - t0 < WALL:
            budget = max(10, min(120, WALL - (time.time() - t0)))
            out = srv.call("auto_close", {}, timeout=budget)
            calls += 1
            tf.write(json.dumps({"type": "tool_result", "tool": "rocq__auto_close",
                                 "content": out[:2000], "ts": time.time()}) + "\n")
            low = out.lower()
            if "no finisher applies" in low:
                outcome = "no_finisher"
                break
            if "no open goals" in low or "proof complete" in low or "qed" in low:
                outcome = "closed"
                break
        srv.close()
    except Exception as e:
        outcome = f"server_error:{type(e).__name__}"
        tf.write(json.dumps({"type": "error", "err": str(e)[:300]}) + "\n")
    tf.close()
    wall = time.time() - t0

    rocq_args = tuple(rec.get("rocq_args") or [])
    if (work / "candidate.v").exists():
        g = gate.check((work / "candidate.v").read_text(), prefix, thm,
                       extra_args=rocq_args)
    else:
        g = {"solved": False, "reason": "no_candidate", "axioms": None}
    row = {"problem_id": rec["problem_id"], "rep": 0,
           "difficulty": datasets.bucket_of(rec), "config_id": cfg["config_id"],
           "model": "NONE(finisher-only)", "solved": g["solved"],
           "reject_reason": g.get("reason"), "policy_outcome": outcome,
           "finisher_calls": calls, "wall_s": round(wall, 1),
           "attempt_timed_out": wall > WALL, "total_cost_usd": 0.0,
           "ts": time.time()}
    with open(run_dir / "results.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    recs = common.load_manifest(args.manifest)
    run_dir = common.LOGS / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(json.dumps(
        {"run_id": args.run_id, "config": cfg, "manifest": args.manifest,
         "driver": "finisher_only(A114)", "policy": f"auto_close<= {MAX_CALLS}, wall {WALL}",
         "started": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1))
    done = {r["problem_id"] for r in common.read_jsonl(run_dir / "results.jsonl")}
    todo = [r for r in recs if r["problem_id"] not in done]
    print(f"[{args.run_id}] {len(todo)} attempts (skip {len(done)})", flush=True)
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {ex.submit(run_attempt, cfg, r, run_dir): r for r in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            r = futs[fut]
            try:
                row = fut.result()
                print(f"  [{i}/{len(todo)}] {r['problem_id']} "
                      f"{'SOLVED' if row['solved'] else row['policy_outcome']} "
                      f"calls={row['finisher_calls']} wall={row['wall_s']}s", flush=True)
            except Exception as e:
                print(f"  [{i}/{len(todo)}] {r['problem_id']} ERROR {e}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
