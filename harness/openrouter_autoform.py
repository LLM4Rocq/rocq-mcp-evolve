#!/usr/bin/env python3
"""OpenRouter autoformalization driver — mirror of mistral_driver.py
(same MCP servers, task specs, prompts, budgets, and autoform_gate
grading) with the OpenRouter transport from openrouter_prover: exact
charged cost from usage.cost, cached/reasoning token telemetry,
credit-floor guard (void, never poison), require_parameters routing.

    python3 harness/openrouter_autoform.py --config af3_evolve \
        --model openai/gpt-5.6-terra --tasks ledger --reps 4 \
        --run-id orp3_evolve --reasoning low
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).parent))
import common
import autoform_gate
from run_autoform import (TASKS_ROOT, LOGS, load_config, task_list,
                          layer_rank, server_specs)
from mistral_driver import McpServer, sweep_workers
from openrouter_prover import chat, api_key, limit_remaining, BudgetHalt


def run_attempt(cfg, model, task, rep, run_dir, run_id, key, opts):
    aid = f"{task}__rep{rep}"
    adir = run_dir / "attempts" / aid
    ws = adir / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    task_dir = TASKS_ROOT / task
    spec = (task_dir / "spec.md").read_text()
    probes = (task_dir / "probes.v").read_text()
    meta = {"run_id": run_id, "config_id": cfg["config_id"], "task": task,
            "rep": rep, "model": model}

    fmt = {"spec": spec, "probes": probes}
    if "{readme}" in cfg["task_prompt"]:
        fmt["readme"] = ((common.REPO / cfg["readme_path"]).read_text() + "\n\n"
                         if cfg.get("readme_path") else "")
    prompt = cfg["task_prompt"].format(**fmt)

    servers = {}
    fns, route = [], {}
    allowed = {t.removeprefix("mcp__") for t in cfg["allowed_tools"]}  # A112b: prefix-only strip ("rocqmcp" contains "mcp__")
    try:
        for name, s in server_specs(cfg, ws, adir, meta).items():
            srv = McpServer(name, s, cwd=str(ws))
            servers[name] = srv
            for t in srv.handshake():
                fq = f"{name}__{t['name']}"
                if fq not in allowed:
                    continue
                route[fq] = (srv, t["name"])
                fns.append({"type": "function", "function": {
                    "name": fq,
                    "description": (t.get("description") or "")[:1024],
                    "parameters": t.get("inputSchema",
                                        {"type": "object", "properties": {}})}})
    except Exception as e:
        for srv in servers.values():
            srv.close()
        raise RuntimeError(f"server spawn/handshake failed: {e}")

    messages = [{"role": "user", "content": prompt}]
    tf = open(adir / "transcript.jsonl", "w")
    tf.write(json.dumps({"type": "init", "model": model,
                         "reasoning": opts.reasoning or None,
                         "tools": sorted(route), "ts": time.time()}) + "\n")
    t0 = time.time()
    cost = 0.0
    pin = pout = pcache = preason = turns = 0
    provider_seen = None
    wall_cap = cfg["attempt_timeout_s"]
    result_text = ""
    halted = None
    try:
        while turns < cfg.get("max_turns", 200):
            if time.time() - t0 > wall_cap:
                result_text = "[wall cap]"
                break
            resp = chat(model, messages, fns, key, reasoning=opts.reasoning)
            u = resp.get("usage", {})
            cost += u.get("cost") or 0.0
            pin += u.get("prompt_tokens", 0)
            pout += u.get("completion_tokens", 0)
            pcache += (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
            preason += (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
            provider_seen = resp.get("provider") or provider_seen
            msg = resp["choices"][0]["message"]
            turns += 1
            tf.write(json.dumps({"type": "assistant", "message": msg,
                                 "usage": u, "provider": resp.get("provider"),
                                 "ts": time.time()}) + "\n")
            tf.flush()
            calls = msg.get("tool_calls") or []
            messages.append(msg)
            if not calls:
                c = msg.get("content") or ""
                if isinstance(c, list):
                    c = " ".join(x.get("text", "") for x in c
                                 if isinstance(x, dict) and x.get("type") == "text")
                result_text = str(c)[:120]
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
                    budget = min(320, max(10, wall_cap - (time.time() - t0)))
                    try:
                        out = srv.call(tool, args, timeout=budget)
                    except Exception as e:
                        out = f"tool error: {e}"
                else:
                    out = f"unknown tool: {fq}"
                out = out[:20000]
                tf.write(json.dumps({"type": "tool_result", "tool": fq,
                                     "content": out[:4000],
                                     "ts": time.time()}) + "\n")
                messages.append({"role": "tool", "tool_call_id": c["id"],
                                 "name": fq, "content": out})
    except BudgetHalt as e:
        halted = str(e)
    finally:
        for srv in servers.values():
            srv.close()
        sweep_workers(adir)  # A115c-c: reap compile workers detached from the server pgid
        tf.close()
    wall = time.time() - t0
    if halted:
        (adir / "BUDGET_HALT").write_text(halted)
        raise BudgetHalt(halted)

    verdict = autoform_gate.check(task_dir, ws)
    sweep_workers(adir)  # A115c-d: grading may spawn workers after the teardown sweep
    row = {"task": task, "rep": rep, "config_id": cfg["config_id"],
           "solved": verdict["solved"], "reason": verdict.get("reason"),
           "layer": layer_rank(verdict), "n_probes": verdict.get("n_probes"),
           "wall_s": round(wall, 1), "num_turns": turns,
           "provider": provider_seen,
           "prompt_tokens": pin, "completion_tokens": pout,
           "cached_tokens": pcache, "reasoning_tokens": preason,
           "total_cost_usd": round(cost, 6), "result_text": result_text,
           "model": model, "ts": time.time()}
    (adir / "verdict.json").write_text(json.dumps(verdict, indent=1))
    with open(run_dir / "results.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", default="all")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--parallel", type=int, default=2)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--reasoning", default="low")
    ap.add_argument("--budget-floor", type=float, default=40.0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if args.reasoning == "off":
        args.reasoning = None
    key = api_key()
    cfg = load_config(args.config)
    run_id = args.run_id or f"orp3_{args.config}"
    run_dir = LOGS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(json.dumps(
        {"config": cfg, "model": args.model, "driver": "openrouter_autoform",
         "reasoning": args.reasoning, "budget_floor": args.budget_floor,
         "started": time.strftime("%F %T"), "reps": args.reps}, indent=1))
    done = {(r["task"], r["rep"])
            for r in common.read_jsonl(run_dir / "results.jsonl")}
    jobs = [(t, r) for t in task_list(args.tasks)
            for r in range(args.reps) if (t, r) not in done]
    if args.limit:
        jobs = jobs[:args.limit]
    rem = limit_remaining(key)
    print(f"[{run_id}] {len(jobs)} attempts (skipping {len(done)}), "
          f"parallel={args.parallel}, model={args.model}, "
          f"limit_remaining=${rem}", flush=True)
    halt = threading.Event()

    def guarded(t, r):
        if halt.is_set():
            raise BudgetHalt("run halted (credit floor)")
        rem = limit_remaining(key)
        if rem is not None and rem < args.budget_floor:
            halt.set()
            raise BudgetHalt(f"limit_remaining ${rem} < floor ${args.budget_floor}")
        return run_attempt(cfg, args.model, t, r, run_dir, run_id, key, args)

    n = 0
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {ex.submit(guarded, t, r): (t, r) for t, r in jobs}
        for fut in as_completed(futs):
            t, r = futs[fut]
            n += 1
            try:
                row = fut.result()
                print(f"  [{n}/{len(jobs)}] {t} rep{r} "
                      f"{'SOLVED' if row['solved'] else row['reason']} "
                      f"turns={row['num_turns']} wall={row['wall_s']}s "
                      f"cost=${row['total_cost_usd']:.4f}", flush=True)
            except BudgetHalt as e:
                print(f"  [{n}/{len(jobs)}] {t} rep{r} BUDGET-HALT: {e}", flush=True)
            except Exception as e:
                print(f"  [{n}/{len(jobs)}] {t} rep{r} ERROR {e}", flush=True)
    rem = limit_remaining(key)
    print(f"[{run_id}] done; limit_remaining=${rem}", flush=True)


if __name__ == "__main__":
    main()
