#!/usr/bin/env python3
"""Phase-2 runner: autoformalization of multi-file Rocq projects.

    python3 harness/run_autoform.py --config af_base --tasks all --reps 2

Per attempt: a fresh workspace dir; the agent gets the task's spec.md and
probes.v in its prompt plus a file-workspace MCP sidecar (write_file /
read_file / list_dir / dune_build). Treatment configs additionally attach
the rocq-tools MCP. Grading = harness/autoform_gate.check on the workspace.
Results land in logs/autoform/<run_id>/results.jsonl with the layer reached
(build/probes/audit/solved) as ordinal progress."""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common
import autoform_gate
from run_eval import CLAUDE_BIN, aggregate_usage, kill_attempt_tree

TASKS_ROOT = common.REPO / "data" / "autoform"
LOGS = common.LOGS / "autoform"


def load_config(name):
    return json.loads((common.REPO / "configs" / f"{name}.json").read_text())


def task_list(spec):
    all_tasks = sorted(d.name for d in TASKS_ROOT.iterdir()
                       if (d / "spec.md").exists())
    return all_tasks if spec == "all" else spec.split(",")


def layer_rank(verdict):
    order = {"build_failed": 1, "no_vo_built": 1, "probes_failed": 2,
             "audit_failed": 3, "axioms_present": 3, "forbidden_token": 0,
             "ok": 4}
    return order.get(verdict.get("reason"), 0)


def server_specs(cfg, ws, adir, meta):
    """MCP server spec dict for an attempt — shared by the claude -p runner
    (writes it to mcp.json) and the model-agnostic driver (spawns directly)."""
    servers = {
        "files": {
            "command": str(common.REPO / "_build/default/src/files_server/rocq_agent_files.exe"),
            "args": [],
            "env": {"PATH": f"{common.OPAM_BIN}:/usr/bin:/bin",
                    "HOME": os.environ.get("HOME", ""),
                    "ROCQ_WORKSPACE": str(ws),
                    "ROCQ_LOG_FILE": str(adir / "server.jsonl"),
                    "ROCQ_LOG_META": json.dumps(meta)},
        }
    }
    if cfg.get("with_rocq_server"):
        servers["rocq"] = {
            "command": str(common.REPO / "_build/default/src/session_server/rocq_agent_session.exe"),
            "args": [],
            "env": {"PATH": f"{common.OPAM_BIN}:/usr/bin:/bin",
                    "HOME": os.environ.get("HOME", ""),
                    "ROCQ_WORKDIR": str(adir / "rocq_work"),
                    "ROCQ_PROJECT_ROOT": str(ws),
                    "ROCQ_LOG_FILE": str(adir / "server.jsonl"),
                    "ROCQ_LOG_META": json.dumps(meta),
                    **cfg.get("rocq_env", {})},
        }
    if cfg.get("sota_server"):
        # SOTA rocq-mcp via the instant-handshake proxy (phase-1 found its
        # Python startup loses the CLI's synchronous MCP window; the proxy
        # answers the handshake from cache while it warms). Fair-integration.
        # A60 fix: the sibling reads ROCQ_WORKSPACE (ROCQ_WORKDIR was dead).
        servers[cfg.get("sota_mcp_name", "rocqmcp")] = {
            "command": "/usr/bin/python3",
            "args": ["-S", str(common.REPO / "harness/mcp_prewarm_proxy.py"),
                     cfg["sota_server"]],
            "env": {"PATH": f"{common.OPAM_BIN}:/usr/bin:/bin",
                    "HOME": os.environ.get("HOME", ""),
                    "ROCQ_WORKSPACE": str(ws)},
        }
    return servers


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
    servers = server_specs(cfg, ws, adir, meta)
    mcp_path = adir / "mcp.json"
    mcp_path.write_text(json.dumps({"mcpServers": servers}, indent=1))

    # A60 fair protocol: optional per-arm {readme} slot in the task prompt —
    # each treatment ships its server's own docs verbatim; baseline gets "".
    fmt = {"spec": spec, "probes": probes}
    if "{readme}" in cfg["task_prompt"]:
        fmt["readme"] = ((common.REPO / cfg["readme_path"]).read_text() + "\n\n"
                         if cfg.get("readme_path") else "")
    prompt = cfg["task_prompt"].format(**fmt)
    cmd = [CLAUDE_BIN, "-p", prompt,
           "--model", cfg["model"]]
    # A60: empty system_prompt = omit the flag entirely (no-prompt protocol)
    if cfg.get("system_prompt"):
        cmd += ["--system-prompt", cfg["system_prompt"]]
    cmd += ["--strict-mcp-config", "--mcp-config", str(mcp_path),
           "--tools", "",
           "--allowedTools", ",".join(cfg["allowed_tools"]),
           "--max-turns", str(cfg["max_turns"]),
           "--output-format", "stream-json", "--verbose"]
    t0 = time.time()
    tf = open(adir / "transcript.jsonl", "w")
    ef = open(adir / "stderr.log", "w")
    p = subprocess.Popen(cmd, stdout=tf, stderr=ef, stdin=subprocess.DEVNULL,
                         cwd=ws, start_new_session=True)
    try:
        p.wait(timeout=cfg["attempt_timeout_s"])
    except subprocess.TimeoutExpired:
        kill_attempt_tree(p, lambda m: None)
        p.wait()
    tf.close(); ef.close()
    wall = time.time() - t0

    events = common.read_jsonl(adir / "transcript.jsonl")
    result_event = next((e for e in reversed(events)
                         if e.get("type") == "result"), None)
    usage = aggregate_usage(events, result_event)

    verdict = autoform_gate.check(task_dir, ws)
    row = {"task": task, "rep": rep, "config_id": cfg["config_id"],
           "solved": verdict["solved"], "reason": verdict.get("reason"),
           "layer": layer_rank(verdict), "n_probes": verdict.get("n_probes"),
           "wall_s": round(wall, 1),
           "num_turns": (result_event or {}).get("num_turns"),
           "total_cost_usd": usage.get("total_cost_usd"),
           "result_text": ((result_event or {}).get("result") or "")[:120],
           "ts": time.time()}
    (adir / "verdict.json").write_text(json.dumps(verdict, indent=1))
    with open(run_dir / "results.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--tasks", default="all")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--parallel", type=int, default=2)
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()
    cfg = load_config(args.config)
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
    print(f"[{run_id}] {len(jobs)} attempts (skipping {len(done)} done), "
          f"parallel={args.parallel}, model={cfg['model']}")
    n = 0
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {ex.submit(run_attempt, cfg, t, r, run_dir, run_id): (t, r)
                for t, r in jobs}
        for fut in as_completed(futs):
            t, r = futs[fut]
            try:
                row = fut.result()
                n += 1
                print(f"  [{n}/{len(jobs)}] {t} rep{r} "
                      f"{'SOLVED' if row['solved'] else row['reason']} "
                      f"layer={row['layer']} turns={row['num_turns']} "
                      f"wall={row['wall_s']}s cost=${row['total_cost_usd'] or 0:.2f}")
            except Exception as e:
                print(f"  [{t} rep{r}] ERROR {e}")
    print(f"[{run_id}] done")


if __name__ == "__main__":
    main()
