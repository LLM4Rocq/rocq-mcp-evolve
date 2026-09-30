#!/usr/bin/env python3
"""Model-agnostic MCP driver: run autoformalization attempts with Mistral
models (native function calling) against the same MCP servers, tasks, gate,
budgets, and result format as the claude -p runner.

    python3 harness/mistral_driver.py --config af3_evolve --model mistral-medium-latest \
        --tasks ledger --reps 1 --run-id mst_smoke

Design: one attempt = spawn the config's MCP servers over stdio (specs
shared with run_autoform.server_specs), do the MCP handshake, convert
tools/list schemas to Mistral function-calling format (namespaced
<server>__<tool>, matching the claude allowlist names sans the mcp__
prefix), then loop chat completions until the model stops calling tools or
the wall budget expires. Grading = autoform_gate.check on the workspace —
identical to the claude runner. Rows land in results.jsonl in the same
shape, so the dashboard machinery works unchanged.

The API key is read from $MISTRAL_API_KEY or ~/.mistral_api_key (never
stored in the repo)."""

import argparse
import json
import os
import select
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common
import autoform_gate
from run_autoform import (TASKS_ROOT, LOGS, load_config, task_list,
                          layer_rank, server_specs)

API = "https://api.mistral.ai/v1/chat/completions"
# $/1M tokens (input, output) — approximate public prices; cost column is
# indicative, flagged as such in the trail.
PRICES = {
    "mistral-large-latest": (2.0, 6.0),
    "mistral-medium-latest": (0.4, 2.0),
    "magistral-medium-latest": (2.0, 5.0),
    "magistral-small-latest": (0.5, 1.5),
    "devstral-medium-latest": (0.4, 2.0),
    "codestral-latest": (0.3, 0.9),
}


def api_key():
    k = os.environ.get("MISTRAL_API_KEY", "")
    if not k:
        p = Path.home() / ".mistral_api_key"
        if p.exists():
            k = p.read_text().strip()
    if not k:
        raise SystemExit("no Mistral API key ($MISTRAL_API_KEY or ~/.mistral_api_key)")
    return k


class McpServer:
    """Minimal MCP stdio client: spawn, handshake, tools/list, tools/call."""

    def __init__(self, name, spec, cwd):
        self.name = name
        self.p = subprocess.Popen(
            [spec["command"]] + spec.get("args", []),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=spec.get("env", {}),
            cwd=cwd, text=True, start_new_session=True)
        self._id = 0

    def _rpc(self, method, params, timeout=60):
        self._id += 1
        rid = self._id
        self.p.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "id": rid, "method": method,
             "params": params}) + "\n")
        self.p.stdin.flush()
        deadline = time.time() + timeout
        while time.time() < deadline:
            r, _, _ = select.select([self.p.stdout], [], [],
                                    max(0.1, deadline - time.time()))
            if not r:
                continue
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError(f"{self.name}: server died")
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            if m.get("id") == rid:
                if "error" in m:
                    raise RuntimeError(f"{self.name}: {m['error']}")
                return m["result"]
        raise TimeoutError(f"{self.name}: {method} timed out after {timeout}s")

    def handshake(self):
        self._rpc("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "mistral-driver", "version": "1"}})
        self.p.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.p.stdin.flush()
        # A112: the prewarm proxy answers tools/list instantly, with an
        # empty list while the backend boots. Poll until non-empty (or a
        # 120 s deadline) so slow-booting servers expose their real
        # surface; a genuinely tool-less server would still time out.
        import time as _t
        deadline = _t.time() + 120
        while True:
            tools = [t for t in self._rpc("tools/list", {})["tools"]]
            if tools or _t.time() > deadline:
                return tools
            _t.sleep(2)

    def call(self, tool, args, timeout=320):
        r = self._rpc("tools/call", {"name": tool, "arguments": args},
                      timeout=timeout)
        parts = [c.get("text", "") for c in r.get("content", [])
                 if isinstance(c, dict)]
        return "\n".join(parts)

    def close(self):
        # A115c-b: SIGTERM the server's whole process group (it has its
        # own pgid via start_new_session), so compile workers spawned by
        # the server cannot outlive the attempt as 16-40 GB orphans.
        import signal as _sig
        try:
            os.killpg(os.getpgid(self.p.pid), _sig.SIGTERM)
        except (OSError, ProcessLookupError):
            try:
                self.p.terminate()
            except OSError:
                pass


def chat(model, messages, tools, key, timeout=600):
    # 600s: reasoning models (magistral) legitimately think for minutes on
    # large prompts; 180s produced spurious read timeouts (A72b).
    body = {"model": model, "messages": messages, "tools": tools,
            "tool_choice": "auto"}
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"mistral api {e.code}: {e.read()[:300]}")
        except (urllib.error.URLError, TimeoutError):
            if attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise


def run_attempt(cfg, model, task, rep, run_dir, run_id, key):
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

    # spawn servers; map namespaced function names -> (server, tool)
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
                         "tools": sorted(route), "ts": time.time()}) + "\n")
    t0 = time.time()
    pin = pout = turns = 0
    wall_cap = cfg["attempt_timeout_s"]
    result_text = ""
    try:
        while turns < cfg.get("max_turns", 200):
            if time.time() - t0 > wall_cap:
                result_text = "[wall cap]"
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
                # magistral returns content as a list of chunks (thinking +
                # text) — coerce to text for the result column
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
    finally:
        for srv in servers.values():
            srv.close()
        tf.close()
    wall = time.time() - t0

    inp, outp = PRICES.get(model, (0.0, 0.0))
    cost = (pin * inp + pout * outp) / 1e6
    verdict = autoform_gate.check(task_dir, ws)
    row = {"task": task, "rep": rep, "config_id": cfg["config_id"],
           "solved": verdict["solved"], "reason": verdict.get("reason"),
           "layer": layer_rank(verdict), "n_probes": verdict.get("n_probes"),
           "wall_s": round(wall, 1), "num_turns": turns,
           "total_cost_usd": round(cost, 4), "result_text": result_text,
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
    args = ap.parse_args()
    key = api_key()
    cfg = load_config(args.config)
    run_id = args.run_id or f"{args.config}_{args.model}_{int(time.time())}"
    run_dir = LOGS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(json.dumps(
        {"config": cfg, "model": args.model, "driver": "mistral",
         "started": time.strftime("%F %T"), "reps": args.reps}, indent=1))
    done = {(r["task"], r["rep"])
            for r in common.read_jsonl(run_dir / "results.jsonl")}
    jobs = [(t, r) for t in task_list(args.tasks)
            for r in range(args.reps) if (t, r) not in done]
    print(f"[{run_id}] {len(jobs)} attempts (skipping {len(done)}), "
          f"parallel={args.parallel}, model={args.model}")
    n = 0
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {ex.submit(run_attempt, cfg, args.model, t, r, run_dir,
                          run_id, key): (t, r) for t, r in jobs}
        for fut in as_completed(futs):
            t, r = futs[fut]
            try:
                row = fut.result()
                n += 1
                print(f"  [{n}/{len(jobs)}] {t} rep{r} "
                      f"{'SOLVED' if row['solved'] else row['reason']} "
                      f"turns={row['num_turns']} wall={row['wall_s']}s "
                      f"cost=${row['total_cost_usd']:.2f}")
            except Exception as e:
                print(f"  [{t} rep{r}] ERROR {e}")
    print(f"[{run_id}] done")


if __name__ == "__main__":
    main()


def sweep_workers(scope_dir):
    """A115c-c: kill leftover rocqworker compiles whose cwd lies inside
    this attempt's own directory. Compile workers detach from the server's
    process group, so McpServer.close()'s killpg cannot reach them; without
    this sweep a timed-out bomb compile survives as a multi-GB orphan.
    cwd-scoped: cannot touch processes outside scope_dir."""
    import subprocess as _sp
    try:
        pids = _sp.run(["pgrep", "-f", "rocqworker"], capture_output=True,
                       text=True).stdout.split()
        for pid in pids:
            out = _sp.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
                          capture_output=True, text=True).stdout
            if any(l.startswith("n") and str(scope_dir) in l
                   for l in out.splitlines()):
                try:
                    os.kill(int(pid), 15)
                except (OSError, ValueError):
                    pass
    except Exception:
        pass
