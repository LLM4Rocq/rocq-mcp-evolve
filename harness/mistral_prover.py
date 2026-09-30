#!/usr/bin/env python3
"""A107: Mistral proving driver — run miniF2F proving attempts with
Mistral models against the SAME server configs, task prompts, arena, and
gate as the claude -p runner (run_eval.py). Reuses mistral_driver's MCP
client and chat loop.

    python3 harness/mistral_prover.py --config af_pf_session \
        --model mistral-large-latest --manifest dev60 --reps 1 \
        --parallel 2 --run-id mstp_evolve_dev60
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
from run_eval import build_task
from mistral_driver import McpServer, chat, api_key, PRICES


def server_env(cfg, work, adir, rec):
    env = {
        "PATH": f"{common.OPAM_BIN}:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": os.environ.get("HOME", ""),
        "ROCQ_WORKDIR": str(work),
        "ROCQ_LOG_FILE": str(adir / "server.jsonl"),
        "ROCQ_TASK_FILE": str(adir / "task_prefix.v"),
    }
    rocq_args = rec.get("rocq_args") or []
    if rocq_args:
        env["ROCQ_INIT_ARGS"] = "\n".join(rocq_args)
        env["ROCQ_COMPILE_ARGS"] = "\n".join(rocq_args)
    env.update(cfg["server"].get("env", {}))
    return env


def run_attempt(cfg, model, rec, rep, run_dir, run_id, key):
    aid = f"{rec['problem_id']}__rep{rep}"
    adir = run_dir / "attempts" / aid
    work = adir / "work"
    work.mkdir(parents=True, exist_ok=True)
    for stale in [work / "candidate.v", adir / "server.jsonl"]:
        stale.unlink(missing_ok=True)
    prefix, thm = build_task(rec)
    if cfg.get("prefix_prepend"):
        prefix = cfg["prefix_prepend"] + prefix
    (adir / "task_prefix.v").write_text(prefix)
    prompt = cfg["task_prompt_template"].format(
        prefix=prefix, statement=rec.get("statement", ""))

    env = server_env(cfg, work, adir, rec)
    specs = {cfg.get("mcp_server_name", "rocq"): {
        "command": cfg["server"]["command"].replace("{repo}", str(common.REPO)),
        "args": cfg["server"].get("args", []), "env": env}}
    for name, srv in cfg.get("extra_servers", {}).items():
        specs[name] = {"command": srv["command"].replace("{repo}", str(common.REPO)),
                       "args": srv.get("args", []),
                       "env": {**env, **srv.get("env", {})}}

    servers, fns, route = {}, [], {}
    allowed = {t.removeprefix("mcp__") for t in cfg["allowed_tools"]}  # A112b: prefix-only strip ("rocqmcp" contains "mcp__")
    try:
        for name, s in specs.items():
            srv = McpServer(name, s, cwd=str(adir))
            servers[name] = srv
            for t in srv.handshake():
                fq = f"{name}__{t['name']}"
                if fq not in allowed:
                    continue
                route[fq] = (srv, t["name"])
                fns.append({"type": "function", "function": {
                    "name": fq, "description": (t.get("description") or "")[:1024],
                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}})}})
    except Exception as e:
        for srv in servers.values():
            srv.close()
        raise RuntimeError(f"server spawn failed: {e}")

    messages = [{"role": "user", "content": prompt}]
    tf = open(adir / "transcript.jsonl", "w")
    tf.write(json.dumps({"type": "init", "model": model,
                         "tools": sorted(route), "ts": time.time()}) + "\n")
    t0 = time.time()
    pin = pout = turns = calls_n = 0
    wall_cap = cfg["attempt_timeout_s"]
    try:
        while turns < cfg.get("max_turns", 100):
            if time.time() - t0 > wall_cap:
                break
            resp = chat(model, messages, fns, key)
            u = resp.get("usage", {})
            pin += u.get("prompt_tokens", 0)
            pout += u.get("completion_tokens", 0)
            msg = resp["choices"][0]["message"]
            turns += 1
            tf.write(json.dumps({"type": "assistant", "message": msg,
                                 "usage": u, "ts": time.time()}) + "\n")
            tf.flush()
            calls = msg.get("tool_calls") or []
            messages.append(msg)
            if not calls:
                break
            for c in calls:
                if time.time() - t0 > wall_cap:
                    break
                fq = c["function"]["name"]
                try:
                    args = json.loads(c["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                if fq in route:
                    srv, tool = route[fq]
                    budget = min(120, max(10, wall_cap - (time.time() - t0)))
                    try:
                        out = srv.call(tool, args, timeout=budget)
                    except Exception as e:
                        out = f"tool error: {e}"
                else:
                    out = f"unknown tool: {fq}"
                calls_n += 1
                out = out[:20000]
                tf.write(json.dumps({"type": "tool_result", "tool": fq,
                                     "content": out[:4000], "ts": time.time()}) + "\n")
                messages.append({"role": "tool", "tool_call_id": c["id"],
                                 "name": fq, "content": out})
    finally:
        for srv in servers.values():
            srv.close()
        tf.close()
    wall = time.time() - t0

    # grading: identical to run_eval — newest compiling submission, else candidate.v
    rocq_args = tuple(rec.get("rocq_args") or [])
    subs = sorted((work / "submissions").glob("*.v"), reverse=True) \
        if (work / "submissions").exists() else []
    gate_res = None
    if subs:
        for sub in subs:
            r = gate.check(sub.read_text(), prefix, thm, extra_args=rocq_args)
            if gate_res is None:
                gate_res = r
            if r.get("reason") not in ("recompile_failed", "compile_failed"):
                gate_res = r
                break
    elif (work / "candidate.v").exists():
        gate_res = gate.check((work / "candidate.v").read_text(), prefix, thm,
                              extra_args=rocq_args)
    else:
        gate_res = {"solved": False, "reason": "no_candidate", "axioms": None}

    inp, outp = PRICES.get(model, (2.0, 6.0))
    cost = (pin * inp + pout * outp) / 1e6
    row = {"problem_id": rec["problem_id"], "rep": rep, "difficulty":
           __import__("datasets").bucket_of(rec), "config_id": cfg["config_id"],
           "model": model, "solved": gate_res["solved"],
           "reject_reason": gate_res.get("reason"), "wall_s": round(wall, 1),
           "num_turns": turns, "tool_calls": calls_n,
           "attempt_timed_out": wall > wall_cap,
           "total_cost_usd": round(cost, 4), "ts": time.time()}
    with open(run_dir / "results.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--parallel", type=int, default=2)
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    recs = common.load_manifest(args.manifest)
    run_id = args.run_id or f"mstp_{args.config}"
    run_dir = common.LOGS / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(json.dumps(
        {"run_id": run_id, "config": cfg, "manifest": args.manifest,
         "reps": args.reps, "parallel": args.parallel, "model": args.model,
         "driver": "mistral_prover", "started": time.strftime("%Y-%m-%dT%H:%M:%S")},
        indent=1))
    done = {(r["problem_id"], r["rep"]) for r in
            common.read_jsonl(run_dir / "results.jsonl")}
    key = api_key()
    slots = [(rec, rep) for rep in range(args.reps) for rec in recs
             if (rec["problem_id"], rep) not in done]
    print(f"[run {run_id}] {len(slots)} attempts (skipping {len(done)} done), "
          f"parallel={args.parallel}, model={args.model}", flush=True)
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {ex.submit(run_attempt, cfg, args.model, rec, rep, run_dir,
                          run_id, key): (rec, rep) for rec, rep in slots}
        n = 0
        for fut in as_completed(futs):
            rec, rep = futs[fut]
            n += 1
            try:
                row = fut.result()
                print(f"  [{n}/{len(slots)}] {rec['problem_id']} rep{rep} "
                      f"{'SOLVED' if row['solved'] else 'no (' + str(row['reject_reason']) + ')'} "
                      f"turns={row['num_turns']} wall={row['wall_s']}s "
                      f"cost=${row['total_cost_usd']:.3f}", flush=True)
            except Exception as e:
                print(f"  [{n}/{len(slots)}] {rec['problem_id']} rep{rep} "
                      f"ERROR: {e}", flush=True)
    print(f"[run {run_id}] done", flush=True)


if __name__ == "__main__":
    main()
