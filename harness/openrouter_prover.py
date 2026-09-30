#!/usr/bin/env python3
"""OpenRouter proving driver — run miniF2F proving attempts with any
OpenRouter-served model against the SAME server configs, task prompts,
arena, and gate as run_eval.py / mistral_prover.py. Reuses the MCP stdio
client from mistral_driver.

    python3 harness/openrouter_prover.py --config af_pf_session2 \
        --model openai/gpt-5.6-luna --manifest dev60 --reps 1 \
        --parallel 2 --run-id orp_smoke --limit 1

Differences from the Mistral driver, all budget/accounting-motivated:
  * cost is the exact charged amount from the response usage.cost field
    (OpenRouter deducts credits per response and reports it), not a
    price-table estimate; cached/reasoning token details land in the
    transcript for later accounting.
  * before each attempt the driver polls GET /api/v1/key and refuses to
    start a new attempt when limit_remaining < --budget-floor, so the run
    halts cleanly on its own side of the hard credit limit instead of
    poisoning rows with 402s. A 402 mid-attempt aborts the attempt
    without writing a results row.
  * provider routing is constrained with require_parameters so requests
    can never land on an endpoint that silently drops the tools array;
    --provider pins a single provider with fallbacks disabled.
  * modest max_tokens per call: OpenRouter preflights affordability
    against max_tokens, and an oversized value near the credit floor
    fails requests early.

The API key is read from $OPEN_ROUTER_API_KEY (never stored in the repo).
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).parent))
import common
import gate
from run_eval import build_task
from mistral_driver import McpServer, sweep_workers

API = "https://openrouter.ai/api/v1/chat/completions"
KEY_API = "https://openrouter.ai/api/v1/key"


class BudgetHalt(Exception):
    pass


def api_key():
    k = os.environ.get("OPEN_ROUTER_API_KEY", "")
    if not k:
        raise SystemExit("no OpenRouter API key ($OPEN_ROUTER_API_KEY)")
    return k


def limit_remaining(key):
    req = urllib.request.Request(KEY_API,
                                 headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        d = json.loads(resp.read())["data"]
    return d.get("limit_remaining")


def chat(model, messages, tools, key, reasoning=None, provider_pin=None,
         max_tokens=8192, timeout=600):
    # no parallel_tool_calls: GPT-5.6 endpoints reject the parameter and
    # require_parameters would filter them out; the loop handles multiple
    # tool_calls per message regardless.
    body = {"model": model, "messages": messages, "tools": tools,
            "tool_choice": "auto", "max_tokens": max_tokens,
            "provider": {"require_parameters": True}}
    if provider_pin:
        body["provider"]["order"] = [provider_pin]
        body["provider"]["allow_fallbacks"] = False
    if reasoning:
        body["reasoning"] = {"effort": reasoning}
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                r = json.loads(resp.read())
            # rare: a 200-shaped body without choices (upstream glitch or
            # embedded error object) — retryable, not a crash
            if "choices" not in r:
                if attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"openrouter response without choices: "
                                   f"{json.dumps(r)[:300]}")
            return r
        except urllib.error.HTTPError as e:
            if e.code == 402:
                raise BudgetHalt(f"openrouter 402: {e.read()[:200]}")
            if e.code in (429, 500, 502, 503) and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"openrouter api {e.code}: {e.read()[:300]}")
        except (urllib.error.URLError, TimeoutError):
            if attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise


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


def run_attempt(cfg, model, rec, rep, run_dir, run_id, key, opts):
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
                         "reasoning": opts.reasoning or None,
                         "provider_pin": opts.provider or None,
                         "tools": sorted(route), "ts": time.time()}) + "\n")
    t0 = time.time()
    cost = 0.0
    pin = pout = pcache = preason = turns = calls_n = 0
    provider_seen = None
    wall_cap = cfg["attempt_timeout_s"]
    halted = None
    try:
        while turns < cfg.get("max_turns", 100):
            if time.time() - t0 > wall_cap:
                break
            resp = chat(model, messages, fns, key, reasoning=opts.reasoning,
                        provider_pin=opts.provider or None)
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
    except BudgetHalt as e:
        halted = str(e)
    finally:
        for srv in servers.values():
            srv.close()
        sweep_workers(adir)  # A115c-c: reap compile workers detached from the server pgid
        tf.close()
    wall = time.time() - t0
    if halted:
        # do NOT write a results row for a credit-aborted attempt: the
        # attempt is void (rerunnable after top-up), not a non-solve.
        (adir / "BUDGET_HALT").write_text(halted)
        raise BudgetHalt(halted)

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
    sweep_workers(adir)  # A115c-d: grading may spawn workers after the teardown sweep

    row = {"problem_id": rec["problem_id"], "rep": rep, "difficulty":
           __import__("datasets").bucket_of(rec), "config_id": cfg["config_id"],
           "model": model, "provider": provider_seen,
           "solved": gate_res["solved"],
           "reject_reason": gate_res.get("reason"), "wall_s": round(wall, 1),
           "num_turns": turns, "tool_calls": calls_n,
           "prompt_tokens": pin, "completion_tokens": pout,
           "cached_tokens": pcache, "reasoning_tokens": preason,
           "attempt_timed_out": wall > wall_cap,
           "total_cost_usd": round(cost, 6), "ts": time.time()}
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
    ap.add_argument("--reasoning", default="low",
                    help="reasoning effort passed to OpenRouter "
                         "(none/low/medium/high/...); 'off' omits the field")
    ap.add_argument("--provider", default="",
                    help="pin a single provider slug (fallbacks disabled)")
    ap.add_argument("--budget-floor", type=float, default=40.0,
                    help="stop starting attempts when limit_remaining < this")
    ap.add_argument("--limit", type=int, default=0,
                    help="cap number of attempts this invocation (0 = all)")
    args = ap.parse_args()
    if args.reasoning == "off":
        args.reasoning = None
    cfg = common.load_config(args.config)
    recs = common.load_manifest(args.manifest)
    run_id = args.run_id or f"orp_{args.config}"
    run_dir = common.LOGS / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(json.dumps(
        {"run_id": run_id, "config": cfg, "manifest": args.manifest,
         "reps": args.reps, "parallel": args.parallel, "model": args.model,
         "reasoning": args.reasoning, "provider_pin": args.provider or None,
         "budget_floor": args.budget_floor,
         "driver": "openrouter_prover",
         "started": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1))
    done = {(r["problem_id"], r["rep"]) for r in
            common.read_jsonl(run_dir / "results.jsonl")}
    key = api_key()
    rem = limit_remaining(key)
    slots = [(rec, rep) for rep in range(args.reps) for rec in recs
             if (rec["problem_id"], rep) not in done]
    if args.limit:
        slots = slots[:args.limit]
    print(f"[run {run_id}] {len(slots)} attempts (skipping {len(done)} done), "
          f"parallel={args.parallel}, model={args.model}, "
          f"reasoning={args.reasoning}, limit_remaining=${rem}", flush=True)
    halt = threading.Event()

    def guarded(rec, rep):
        if halt.is_set():
            raise BudgetHalt("run halted (credit floor)")
        rem = limit_remaining(key)
        if rem is not None and rem < args.budget_floor:
            halt.set()
            raise BudgetHalt(f"limit_remaining ${rem} < floor ${args.budget_floor}")
        return run_attempt(cfg, args.model, rec, rep, run_dir, run_id, key, args)

    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {ex.submit(guarded, rec, rep): (rec, rep)
                for rec, rep in slots}
        n = 0
        for fut in as_completed(futs):
            rec, rep = futs[fut]
            n += 1
            try:
                row = fut.result()
                print(f"  [{n}/{len(slots)}] {rec['problem_id']} rep{rep} "
                      f"{'SOLVED' if row['solved'] else 'no (' + str(row['reject_reason']) + ')'} "
                      f"turns={row['num_turns']} wall={row['wall_s']}s "
                      f"cost=${row['total_cost_usd']:.4f} "
                      f"cached={row['cached_tokens']}", flush=True)
            except BudgetHalt as e:
                print(f"  [{n}/{len(slots)}] {rec['problem_id']} rep{rep} "
                      f"BUDGET-HALT: {e}", flush=True)
            except Exception as e:
                print(f"  [{n}/{len(slots)}] {rec['problem_id']} rep{rep} "
                      f"ERROR: {e}", flush=True)
    rem = limit_remaining(key)
    print(f"[run {run_id}] done; limit_remaining=${rem}", flush=True)


if __name__ == "__main__":
    main()
