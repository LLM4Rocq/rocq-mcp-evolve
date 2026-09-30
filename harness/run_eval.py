#!/usr/bin/env python3
"""Eval runner.

For each problem in a manifest, spawns the pinned policy — `claude` CLI in
headless mode, MCP tools only — against the tool-layer config under test,
then verifies the outcome with the correctness gate (gate.py) and appends one
structured record per attempt to <run_dir>/results.jsonl.

Contract with tool servers (all configs): the server must write the current
best complete .v to $ROCQ_WORKDIR/candidate.v whenever a full check passes.
The gate re-verifies candidate.v from scratch; the in-session result is never
trusted.
"""

import argparse
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common
import datasets
import gate

CLAUDE_BIN = os.environ.get("CLAUDE_BIN", os.path.expanduser("~/.local/bin/claude"))


def _parse_claude_version(bin_path):
    """A142 (CLI era gate): resolve the actual CLI build behind CLAUDE_BIN
    (which may be a pinned binary, a shim, or the ambient PATH claude) so a
    run can be pinned to it and every run records what actually ran."""
    try:
        out = subprocess.run(
            [bin_path, "--version"], capture_output=True, text=True, timeout=30
        )
        text = (out.stdout or out.stderr or "").strip()
        return text.split()[0] if text else None
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[run_eval] A142: could not run {bin_path!r} --version: {e!r}",
              file=sys.stderr)
        return None


def _descendants(pid: int) -> list[int]:
    try:
        out = subprocess.run(
            ["pgrep", "-P", str(pid)], capture_output=True, text=True
        ).stdout.split()
    except OSError:
        return []
    ds = []
    for c in out:
        try:
            c = int(c)
        except ValueError:
            continue
        ds.append(c)
        ds.extend(_descendants(c))
    return ds


def kill_attempt_tree(p: subprocess.Popen, log):
    """SIGKILL the spawned CLI, its descendants (MCP server, prover workers),
    and its process group. Logs every step: the 300s-timeout failure observed
    in run baseline_dev60_r1 (attempts alive at ~580s) needs a diagnosable
    kill path."""
    log(f"kill_attempt_tree pid={p.pid} t={time.time():.1f}")
    for d in _descendants(p.pid):
        try:
            os.kill(d, signal.SIGKILL)
        except OSError as e:
            log(f"  kill child {d}: {e!r}")
    for target, fn in [("pg", lambda: os.killpg(os.getpgid(p.pid), signal.SIGKILL)),
                       ("pid", lambda: os.kill(p.pid, signal.SIGKILL))]:
        try:
            fn()
        except OSError as e:
            log(f"  kill {target}: {e!r}")


def build_task(rec):
    """(file prefix the agent must extend, theorem name)."""
    if rec["source"].endswith("_project"):
        # in-project benchmarks (A20/A21): prefix = the real file above the lemma
        content = Path(rec["path"]).read_text(errors="replace")
        return content[: rec["prefix_chars"]] + "\n", rec["theorem_name"]
    if rec["source"] == "workbook":
        prefix = datasets.workbook_problem_to_vfile(
            {
                "rocq_imports": rec["imports"],
                "rocq_preamble": rec["preamble"],
                "rocq_statement": rec["statement"],
            }
        )
    else:
        content = (common.WORKROOT / rec["path"]).read_text()
        prefix = datasets.statement_prefix(content)
        if not prefix.endswith("\n"):
            prefix += "\n"
    return prefix, rec["theorem_name"]


def aggregate_usage(events, result_event):
    """Token accounting; falls back to per-message events for killed runs."""
    if result_event is not None:
        u = result_event.get("usage", {})
        return {
            "input_tokens": u.get("input_tokens", 0),
            "output_tokens": u.get("output_tokens", 0),
            "cache_read_input_tokens": u.get("cache_read_input_tokens", 0),
            "cache_creation_input_tokens": u.get("cache_creation_input_tokens", 0),
            "total_cost_usd": result_event.get("total_cost_usd"),
            "estimated": False,
        }
    seen_msg, out_tok, in_last = set(), 0, 0
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        msg = ev.get("message", {})
        mid = msg.get("id")
        u = msg.get("usage", {})
        if mid in seen_msg:
            continue
        seen_msg.add(mid)
        out_tok += u.get("output_tokens", 0)
        in_last = max(
            in_last,
            u.get("input_tokens", 0)
            + u.get("cache_read_input_tokens", 0)
            + u.get("cache_creation_input_tokens", 0),
        )
    return {
        "input_tokens": in_last,
        "output_tokens": out_tok,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "total_cost_usd": None,
        "estimated": True,
    }


def _recorded_effort(session_id, adir):
    """A142/A149: read the CLI's own session log IN PLACE (never copied into
    the attempt dir any more, A149) and return the sorted list of distinct
    top-level "effort" values on its assistant records -- the per-attempt
    effort provenance kept in the result row. Returns None if no session
    file could be found (the CLI prunes them after 30 days), [] if the
    model has no effort parameter (haiku). Never raises: the caller must
    not fail an attempt over this."""
    if not session_id:
        return None
    projects_dir = Path(os.path.expanduser("~/.claude/projects"))
    matches = list(projects_dir.glob(f"*/{session_id}.jsonl"))
    if not matches:
        # fall back to the sanitized-cwd directory convention ("/" and "_"
        # both replaced by "-")
        sanitized = str(adir).replace("/", "-").replace("_", "-")
        fallback = projects_dir / sanitized / f"{session_id}.jsonl"
        if fallback.exists():
            matches = [fallback]
    if not matches:
        return None
    efforts = {
        r["effort"] for r in common.read_jsonl(matches[0])
        if r.get("type") == "assistant" and "effort" in r
    }
    return sorted(efforts)


def run_attempt(cfg, rec, rep, run_dir, run_id):
    prefix, thm = build_task(rec)
    # A99: environment standardization delivered via the task file, for
    # servers that cannot receive ambient flags any other way (the gate
    # injects the same modules via -ri for every arm; A11 verified them
    # statement-invariant). The gate below receives the SAME prefix, so
    # grading and session see one file.
    if cfg.get("prefix_prepend"):
        prefix = cfg["prefix_prepend"] + prefix
    aid = f"{rec['problem_id']}__rep{rep}"
    adir = run_dir / "attempts" / aid
    work = adir / "work"
    work.mkdir(parents=True, exist_ok=True)
    server_log = adir / "server.jsonl"
    # A93: a crashed or duplicated predecessor attempt may have left grading
    # artifacts behind; this attempt must never be graded on them.
    for stale in [work / "candidate.v", server_log, adir / "gate_reject.txt"]:
        stale.unlink(missing_ok=True)
    if (work / "submissions").exists():
        shutil.rmtree(work / "submissions")
    bucket = datasets.bucket_of(rec)
    meta = {
        "run_id": run_id,
        "config_id": cfg["config_id"],
        "problem_id": rec["problem_id"],
        "difficulty": bucket,
        "source": rec["source"],
        "rep": rep,
        "agent_id": aid,
    }
    server_env = {
        "PATH": f"{common.OPAM_BIN}:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": os.environ.get("HOME", ""),
        "ROCQ_WORKDIR": str(work),
        "ROCQ_LOG_FILE": str(server_log),
        "ROCQ_LOG_META": json.dumps(meta),
        "ROCQ_TASK_FILE": str(adir / "task_prefix.v"),
    }
    rocq_args = rec.get("rocq_args") or []
    if rocq_args:
        server_env["ROCQ_INIT_ARGS"] = "\n".join(rocq_args)
        server_env["ROCQ_COMPILE_ARGS"] = "\n".join(rocq_args)
    server_env.update(cfg["server"].get("env", {}))
    server_cmd = cfg["server"]["command"].replace("{repo}", str(common.REPO))
    mcp_cfg = {
        "mcpServers": {
            cfg.get("mcp_server_name", "rocq"): {
                "command": server_cmd,
                "args": cfg["server"].get("args", []),
                "env": server_env,
            }
        }
    }
    # additional MCP servers (e.g. the submit sidecar for external-tool
    # configs, A16); {repo} and the standard ROCQ_* env are provided
    for name, srv in cfg.get("extra_servers", {}).items():
        mcp_cfg["mcpServers"][name] = {
            "command": srv["command"].replace("{repo}", str(common.REPO)),
            "args": srv.get("args", []),
            "env": {**server_env, **srv.get("env", {})},
        }
    (adir / "mcp.json").write_text(json.dumps(mcp_cfg, indent=1))
    task_prompt = cfg["task_prompt_template"].format(
        prefix=prefix, statement=rec.get("statement", ""))
    (adir / "task_prefix.v").write_text(prefix)
    cmd = [
        CLAUDE_BIN,
        "-p", task_prompt,
        "--model", cfg["model"],
        *(["--system-prompt", cfg["system_prompt"]]
          if cfg.get("system_prompt") else []),
        "--strict-mcp-config", "--mcp-config", str(adir / "mcp.json"),
        "--tools", "",
        "--allowedTools", ",".join(cfg["allowed_tools"]),
        "--max-turns", str(cfg["max_turns"]),
        # A142 (CLI era gate): explicit --effort when the config pins one,
        # so a comparison across CLI eras also controls thinking effort.
        *(["--effort", cfg["effort"]] if cfg.get("effort") else []),
        "--output-format", "stream-json", "--verbose",
    ]
    t0 = time.time()
    timed_out = False
    kill_log_path = adir / "kill.log"

    def klog(msg):
        with open(kill_log_path, "a") as kf:
            kf.write(msg + "\n")

    with open(adir / "transcript.jsonl", "w") as tf, open(adir / "stderr.log", "w") as ef:
        p = subprocess.Popen(
            cmd,
            stdout=tf,
            stderr=ef,
            stdin=subprocess.DEVNULL,
            cwd=adir,
            start_new_session=True,
        )
        # WALL-CLOCK deadline watchdog. p.wait(timeout)/threading.Timer use the
        # monotonic clock, which does not advance while macOS sleeps — an
        # attempt spanning a laptop sleep would blow way past its budget
        # (observed: 580 s walls in the discarded first control run). Poll
        # wall-clock time instead; the sleep gap then counts against the
        # attempt and it is killed on wake.
        watchdog_fired = threading.Event()
        slept = threading.Event()
        stop_wd = threading.Event()
        deadline_wall = t0 + cfg["attempt_timeout_s"]
        m0 = time.monotonic()

        def watchdog():
            while not stop_wd.wait(2.0):
                drift = (time.time() - t0) - (time.monotonic() - m0)
                if drift > 5.0 and not slept.is_set():
                    slept.set()
                    klog(f"machine slept during attempt: wall-mono drift {drift:.0f}s")
                if time.time() > deadline_wall:
                    watchdog_fired.set()
                    klog(f"wall-clock watchdog fired at +{time.time()-t0:.1f}s")
                    kill_attempt_tree(p, klog)
                    return

        wd = threading.Thread(target=watchdog, daemon=True)
        wd.start()
        try:
            p.wait(timeout=cfg["attempt_timeout_s"] + 15)
        except subprocess.TimeoutExpired:
            klog(f"p.wait timeout at +{time.time()-t0:.1f}s")
            kill_attempt_tree(p, klog)
            p.wait()
        finally:
            stop_wd.set()
        timed_out = timed_out or watchdog_fired.is_set() or (time.time() > deadline_wall)
    wall_s = time.time() - t0
    if wall_s > cfg["attempt_timeout_s"] + 30:
        klog(f"ANOMALY: attempt outlived timeout: wall={wall_s:.1f}s timed_out={timed_out}")

    events = common.read_jsonl(adir / "transcript.jsonl")
    result_event = next((e for e in reversed(events) if e.get("type") == "result"), None)
    # A83: quota poisoning — a 429/session-limit result invalidates the
    # attempt (infrastructure, not model). Park the transcript, wait out the
    # window, and redo the SAME slot (identical-slot repair; machine_slept
    # precedent). Recursion depth is bounded by the subscription window.
    _re = result_event or {}
    _dead_stream = (result_event is None
                    and not any(e.get("type") == "assistant" for e in events)
                    and not any(e.get("type") == "system"
                                and e.get("subtype") == "thinking_tokens"
                                for e in events))
    if (_re.get("api_error_status") == 429
            or "session limit" in str(_re.get("result", "")).lower()
            or _dead_stream):
        import shutil as _sh
        _sh.move(adir / "transcript.jsonl",
                 adir / f"transcript.poisoned.{int(time.time())}.jsonl")
        klog("quota-poisoned or dead stream (zero assistant events); parking 20min then redoing this slot")
        time.sleep(1200)
        return run_attempt(cfg, rec, rep, run_dir, run_id)
    # A142 (CLI era gate): the init event names the CLI build and session
    # actually used for this attempt, independent of CLAUDE_BIN/cfg intent.
    init_event = next(
        (e for e in events if e.get("type") == "system" and e.get("subtype") == "init"),
        None,
    )
    claude_code_version = (init_event or {}).get("claude_code_version")
    session_id = (init_event or {}).get("session_id")
    try:
        effort_recorded = _recorded_effort(session_id, adir)
    except Exception as e:
        print(f"[run_eval] A142: effort recovery failed for "
              f"session_id={session_id!r} attempt={adir}: {e!r}", file=sys.stderr)
        effort_recorded = None
    usage = aggregate_usage(events, result_event)
    denials = (result_event or {}).get("permission_denials", [])

    server_records = common.read_jsonl(server_log)
    calls = [r for r in server_records if r.get("kind") == "tool_call"]
    prover_ms = sum(r.get("prover_ms", 0.0) for r in calls)
    tool_durs = [round(r.get("dur_ms", 0.0), 1) for r in calls]

    candidate_path = work / "candidate.v"
    subs_dir = work / "submissions"
    if subs_dir.exists() and any(subs_dir.glob("*.v")):
        # A76 parity (external-submit arms): the artifact is the NEWEST
        # submission that compiles — mirroring baseline's last-exit-0
        # semantics — so a later broken submit cannot clobber a good one.
        gate_res = None
        for sub in sorted(subs_dir.glob("*.v"), reverse=True):
            r = gate.check(sub.read_text(), prefix, thm,
                           extra_args=tuple(rocq_args))
            if gate_res is None:
                gate_res = r          # newest verdict is the default
            if r.get("reason") not in ("recompile_failed", "compile_failed"):
                gate_res = r
                break
    elif candidate_path.exists():
        gate_res = gate.check(candidate_path.read_text(), prefix, thm,
                              extra_args=tuple(rocq_args))
    else:
        gate_res = {"solved": False, "reason": "no_candidate", "axioms": None,
                    "recompile_s": None, "detail": None}

    record = {
        "ts": t0,
        "run_id": run_id,
        "config_id": cfg["config_id"],
        "model": cfg["model"],
        "problem_id": rec["problem_id"],
        "source": rec["source"],
        "difficulty": bucket,
        "source_tier": rec.get("source_tier"),
        "rep": rep,
        "seed": rep,
        "solved": gate_res["solved"],
        "reject_reason": gate_res["reason"],
        "gate": {k: v for k, v in gate_res.items() if k != "detail"},
        "wall_s": round(wall_s, 2),
        "attempt_timed_out": timed_out,
        "machine_slept": slept.is_set(),
        "num_turns": (result_event or {}).get("num_turns"),
        "stop_reason": (result_event or {}).get("stop_reason"),
        "duration_ms": (result_event or {}).get("duration_ms"),
        "duration_api_ms": (result_event or {}).get("duration_api_ms"),
        "usage": usage,
        "total_cost_usd": usage.get("total_cost_usd"),
        "tool_calls": len(calls),
        "prover_ms_total": round(prover_ms, 1),
        "tool_dur_ms": tool_durs,
        "permission_denials": len(denials),
        "result_text": ((result_event or {}).get("result") or "")[:200],
        "attempt_dir": str(adir.relative_to(common.LOGS)),
        # A142 (CLI era gate): what the CLI reports it ran as (init event)
        # and what was asked for (cfg), plus what the CLI's own session log
        # carries per-turn — these can disagree (silent auto-update, a
        # config effort the CLI ignored) and that disagreement is the point.
        "claude_code_version": claude_code_version,
        "session_id": session_id,
        "effort_requested": cfg.get("effort"),
        "effort_recorded": effort_recorded,
    }
    if gate_res.get("detail"):
        (adir / "gate_reject.txt").write_text(gate_res["detail"])
    common.append_jsonl(run_dir / "results.jsonl", record)
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--buckets", default=None, help="comma-separated difficulty filter")
    args = ap.parse_args()

    cfg = common.load_config(args.config)

    # A142 (CLI era gate): resolve the CLI build behind CLAUDE_BIN before any
    # attempt spawns; when the config pins one, refuse to start on a mismatch
    # rather than silently mixing CLI eras into one arm (a mid-run
    # auto-update is the failure this guards against).
    claude_bin_realpath = os.path.realpath(CLAUDE_BIN)
    claude_version = _parse_claude_version(CLAUDE_BIN)
    if cfg.get("cli_version") and claude_version != cfg["cli_version"]:
        sys.exit(
            f"[run_eval] A142: config {cfg['config_id']!r} pins cli_version="
            f"{cfg['cli_version']!r}, but CLAUDE_BIN={CLAUDE_BIN} "
            f"(realpath {claude_bin_realpath}) reports version "
            f"{claude_version!r}. Refusing to start."
        )

    problems = common.load_manifest(args.manifest)
    if args.buckets:
        keep = set(args.buckets.split(","))
        problems = [p for p in problems if p["difficulty"] in keep]
    if args.limit:
        problems = problems[: args.limit]

    run_id = args.run_id or f"{cfg['config_id']}__{Path(args.manifest).stem}__{time.strftime('%m%d_%H%M%S')}"
    run_dir = common.LOGS / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    done = {(r["problem_id"], r["rep"]) for r in common.read_jsonl(run_dir / "results.jsonl")}
    todo = [
        (rec, rep)
        for rep in range(args.reps)
        for rec in problems
        if (rec["problem_id"], rep) not in done
    ]

    git_rev = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=common.REPO, capture_output=True, text=True
    ).stdout.strip()
    run_meta = {
        "run_id": run_id,
        "config": cfg,
        "manifest": args.manifest,
        "n_problems": len(problems),
        "reps": args.reps,
        "parallel": args.parallel,
        "git_rev": git_rev,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
        },
        "claude_bin": CLAUDE_BIN,
        "resumed_skipping": len(done),
        # A142 (CLI era gate): what actually ran, vs. what the config asked
        # for; the end-of-run census below checks these against every row.
        "claude_bin_realpath": claude_bin_realpath,
        "claude_version": claude_version,
        "effort": cfg.get("effort"),
        "cli_version_pinned": cfg.get("cli_version"),
    }
    (run_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=1))
    print(f"[run {run_id}] {len(todo)} attempts (skipping {len(done)} done), "
          f"parallel={args.parallel}, model={cfg['model']}", flush=True)

    t0 = time.time()
    n_done = n_solved = 0
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {
            ex.submit(run_attempt, cfg, rec, rep, run_dir, run_id): (rec, rep)
            for rec, rep in todo
        }
        for fut in as_completed(futs):
            rec, rep = futs[fut]
            try:
                r = fut.result()
                n_done += 1
                n_solved += r["solved"]
                print(
                    f"  [{n_done}/{len(todo)}] {r['problem_id']} rep{rep} "
                    f"{'SOLVED' if r['solved'] else 'no (' + str(r['reject_reason']) + ')'} "
                    f"turns={r['num_turns']} calls={r['tool_calls']} "
                    f"wall={r['wall_s']}s cost=${r['total_cost_usd'] or 0:.4f}",
                    flush=True,
                )
            except Exception as e:
                n_done += 1
                print(f"  [{n_done}/{len(todo)}] {rec['problem_id']} rep{rep} HARNESS-ERROR {e!r}", flush=True)
                common.append_jsonl(
                    run_dir / "results.jsonl",
                    {
                        "ts": time.time(), "run_id": run_id, "config_id": cfg["config_id"],
                        "problem_id": rec["problem_id"], "difficulty": datasets.bucket_of(rec),
                        "source": rec["source"], "rep": rep, "solved": False,
                        "reject_reason": f"harness_error:{type(e).__name__}",
                        "harness_error": repr(e),
                    },
                )
    # A142/A145 provenance: record the CLI builds actually used across this
    # run's attempts. Informational only — the build was shown immaterial
    # (A144), so a mixed census is not an error.
    final_rows = common.read_jsonl(run_dir / "results.jsonl")
    versions_seen = sorted({
        r["claude_code_version"] for r in final_rows if r.get("claude_code_version")
    })
    run_meta["claude_version_census"] = versions_seen
    (run_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=1))
    print(f"[run {run_id}] CLI build census: {versions_seen}", flush=True)
    print(f"[run {run_id}] done: {n_solved}/{n_done} solved in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
