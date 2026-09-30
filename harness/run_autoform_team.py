#!/usr/bin/env python3
"""Phase-2 team runner: planner -> parallel workers -> integrator on ONE
shared project workspace (file-level parallelism; each worker gets its own
files sidecar + rocq server).

    python3 harness/run_autoform_team.py --config af_team_sonnet --tasks all --reps 1
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common
import autoform_gate
from run_eval import CLAUDE_BIN, aggregate_usage, kill_attempt_tree
from run_autoform import layer_rank, task_list, TASKS_ROOT, LOGS


def mcp_cfg(adir, ws, agent_id, meta, with_rocq, rocq_env):
    servers = {
        "files": {
            "command": str(common.REPO / "_build/default/src/files_server/rocq_agent_files.exe"),
            "args": [],
            "env": {"PATH": f"{common.OPAM_BIN}:/usr/bin:/bin",
                    "HOME": os.environ.get("HOME", ""),
                    "ROCQ_WORKSPACE": str(ws),
                    "ROCQ_LOG_FILE": str(adir / "server.jsonl"),
                    "ROCQ_LOG_META": json.dumps({**meta, "agent": agent_id})},
        }
    }
    if with_rocq:
        servers["rocq"] = {
            "command": str(common.REPO / "_build/default/src/session_server/rocq_agent_session.exe"),
            "args": [],
            "env": {"PATH": f"{common.OPAM_BIN}:/usr/bin:/bin",
                    "HOME": os.environ.get("HOME", ""),
                    "ROCQ_WORKDIR": str(adir / "rocq_work"),
                    "ROCQ_PROJECT_ROOT": str(ws),
                    "ROCQ_LOG_FILE": str(adir / "server.jsonl"),
                    "ROCQ_LOG_META": json.dumps({**meta, "agent": agent_id}),
                    **rocq_env},
        }
    p = adir / f"mcp_{agent_id}.json"
    p.write_text(json.dumps({"mcpServers": servers}, indent=1))
    return p


def run_agent(cfg, adir, ws, agent_id, system, prompt, max_turns, wall_s,
              meta, with_rocq):
    mcp = mcp_cfg(adir, ws, agent_id, meta, with_rocq,
                  cfg.get("rocq_env", {}))
    allowed = list(cfg["allowed_tools"])
    if not with_rocq:
        allowed = [t for t in allowed if not t.startswith("mcp__rocq__")]
    cmd = [CLAUDE_BIN, "-p", prompt, "--model", cfg["model"],
           "--system-prompt", system,
           "--strict-mcp-config", "--mcp-config", str(mcp),
           "--tools", "", "--allowedTools", ",".join(allowed),
           "--max-turns", str(max_turns),
           "--output-format", "stream-json", "--verbose"]
    out = adir / f"transcript_{agent_id}.jsonl"
    with open(out, "w") as tf, open(adir / f"stderr_{agent_id}.log", "w") as ef:
        p = subprocess.Popen(cmd, stdout=tf, stderr=ef,
                             stdin=subprocess.DEVNULL, cwd=ws,
                             start_new_session=True)
        try:
            p.wait(timeout=wall_s)
        except subprocess.TimeoutExpired:
            kill_attempt_tree(p, lambda m: None)
            p.wait()
    events = common.read_jsonl(out)
    result_event = next((e for e in reversed(events)
                         if e.get("type") == "result"), None)
    u = aggregate_usage(events, result_event)
    return u.get("total_cost_usd") or 0


def run_attempt(cfg, task, rep, run_dir, run_id):
    aid = f"{task}__rep{rep}"
    adir = run_dir / "attempts" / aid
    ws = adir / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    task_dir = TASKS_ROOT / task
    spec = (task_dir / "spec.md").read_text()
    probes = (task_dir / "probes.v").read_text()
    meta = {"run_id": run_id, "config_id": cfg["config_id"], "task": task,
            "rep": rep}
    t0 = time.time()
    cost = 0.0
    b = cfg["team"]

    # phase A: planner (files only)
    cost += run_agent(cfg, adir, ws, "planner", cfg["planner_system"],
                      cfg["planner_prompt"].format(spec=spec, probes=probes,
                                                   k=b["k_workers"]),
                      b["planner_turns"], b["planner_wall_s"], meta, False)

    # parse assignments from PLAN.md (### WORKER i sections listing files)
    plan = (ws / "PLAN.md").read_text() if (ws / "PLAN.md").exists() else ""
    assignments = re.findall(r"^###\s*WORKER\s*(\d+)\s*\n(.*?)(?=^###|\Z)",
                             plan, re.M | re.S)
    if not assignments:
        assignments = [("1", "implement the whole project")]
    assignments = assignments[: b["k_workers"]]

    # phase B: workers in parallel (files + rocq)
    def work(i, section):
        return run_agent(cfg, adir, ws, f"w{i}", cfg["worker_system"],
                         cfg["worker_prompt"].format(spec=spec, probes=probes,
                                                     assignment=section.strip()),
                         b["worker_turns"], b["worker_wall_s"], meta, True)
    with ThreadPoolExecutor(max_workers=len(assignments)) as ex:
        for c in ex.map(lambda a: work(*a), assignments):
            cost += c

    # phase C: integrator (files + rocq)
    cost += run_agent(cfg, adir, ws, "integrator", cfg["integrator_system"],
                      cfg["integrator_prompt"].format(spec=spec, probes=probes),
                      b["integrator_turns"], b["integrator_wall_s"], meta, True)

    wall = time.time() - t0
    verdict = autoform_gate.check(task_dir, ws)
    row = {"task": task, "rep": rep, "config_id": cfg["config_id"],
           "solved": verdict["solved"], "reason": verdict.get("reason"),
           "layer": layer_rank(verdict), "wall_s": round(wall, 1),
           "n_workers": len(assignments), "total_cost_usd": round(cost, 4),
           "num_turns": None, "ts": time.time()}
    (adir / "verdict.json").write_text(json.dumps(verdict, indent=1))
    with open(run_dir / "results.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--tasks", default="all")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()
    cfg = json.loads((common.REPO / "configs" / f"{args.config}.json").read_text())
    run_id = args.run_id or f"{args.config}_{int(time.time())}"
    run_dir = LOGS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(json.dumps(
        {"config": cfg, "started": time.strftime("%F %T"),
         "reps": args.reps}, indent=1))
    done = {(r["task"], r["rep"])
            for r in common.read_jsonl(run_dir / "results.jsonl")}
    jobs = [(t, r) for t in task_list(args.tasks)
            for r in range(args.reps) if (t, r) not in done]
    print(f"[{run_id}] {len(jobs)} team attempts, parallel={args.parallel}")
    n = 0
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        for row in ex.map(lambda j: run_attempt(cfg, j[0], j[1], run_dir,
                                                run_id), jobs):
            n += 1
            print(f"  [{n}/{len(jobs)}] {row['task']} rep{row['rep']} "
                  f"{'SOLVED' if row['solved'] else row['reason']} "
                  f"layer={row['layer']} workers={row['n_workers']} "
                  f"wall={row['wall_s']}s cost=${row['total_cost_usd']:.2f}")
    print(f"[{run_id}] done")


if __name__ == "__main__":
    main()
