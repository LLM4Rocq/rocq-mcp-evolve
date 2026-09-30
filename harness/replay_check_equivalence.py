#!/usr/bin/env python3
"""A148: behavioural-equivalence replay of the baseline server.

The 2026-09-16/17 matrix-completion rows (A142 opus control rerun, A146
haiku control rep 1) were launched from the `dev` checkout, so their MCP
server was the dev build of src/baseline_server (whose sources are
identical to main's; the only build difference is that dev's mcp_core
library carries two extra modules the baseline server never references).
This script turns that source-level argument into an empirical one on the
actual data: every `check` call those attempts made (args.content, as the
server itself logged it in the attempt's server.jsonl) is replayed through
the FROZEN main build of the baseline server, with the attempt's own
task_prefix.v and the same ROCQ_* environment, and the frozen server's
reply (result text, exit code, error flag, timeout flag) and the
candidate.v it leaves behind (the harness gate's input) are compared with
what the dev build produced during the run.

    python3 harness/replay_check_equivalence.py --exe PATH/TO/frozen/rocq_agent_baseline.exe \
        --run FINAL_pf_baseline_opus_r245 --run FINAL_pf_baseline_haiku:1 [--parallel 6]

Writes logs/replay_equivalence/<run>.json (per attempt: calls, mismatching
calls with a diff excerpt, candidate.v comparison) and prints one summary
line per run. Read-only on the run directories; scratch under
logs/replay_equivalence/scratch/.
"""
import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

OUT_DIR = common.LOGS / "replay_equivalence"


def attempts_of(run, rep):
    d = common.LOGS / "runs" / run / "attempts"
    for a in sorted(d.iterdir()):
        if not a.is_dir():
            continue
        if rep is not None and not a.name.endswith(f"__rep{rep}"):
            continue
        if (a / "server.jsonl").exists() and (a / "task_prefix.v").exists():
            yield a


def replay_attempt(exe, adir, scratch):
    orig = [r for r in common.read_jsonl(adir / "server.jsonl") if r.get("kind") == "tool_call"]
    calls = [r for r in orig if r.get("tool") == "check"]
    rec = {"attempt": adir.name, "n_calls": len(calls), "n_other_tools": len(orig) - len(calls)}
    if not calls:
        rec["candidate"] = "no calls"
        return rec
    mcp = json.load(open(adir / "mcp.json"))
    env0 = list(mcp["mcpServers"].values())[0].get("env") or {}
    sdir = scratch / adir.name
    work = sdir / "work"
    work.mkdir(parents=True, exist_ok=True)
    log = sdir / "server.jsonl"
    if log.exists():
        log.unlink()
    env = {k: v for k, v in env0.items() if k.startswith("ROCQ_") or k in ("PATH", "HOME")}
    env.update({"ROCQ_WORKDIR": str(work), "ROCQ_LOG_FILE": str(log),
                "ROCQ_TASK_FILE": str(adir / "task_prefix.v"),
                "ROCQ_LOG_META": json.dumps({"replay_of": adir.name})})
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}]
    for i, c in enumerate(calls):
        msgs.append({"jsonrpc": "2.0", "id": 2 + i, "method": "tools/call",
                     "params": {"name": "check", "arguments": c["args"]}})
    inp = "".join(json.dumps(m) + "\n" for m in msgs)
    per_call_timeout = float(env.get("ROCQ_COMPILE_TIMEOUT", "60"))
    try:
        subprocess.run([str(exe)], input=inp, env=env, capture_output=True, text=True,
                       timeout=per_call_timeout * len(calls) + 60)
    except subprocess.TimeoutExpired:
        rec["error"] = "replay process timeout"
        return rec
    replayed = [r for r in common.read_jsonl(log) if r.get("kind") == "tool_call" and r.get("tool") == "check"]
    rec["n_replayed"] = len(replayed)
    mism = []
    for i, (a, b) in enumerate(zip(calls, replayed)):
        diffs = [f for f in ("result", "exit_code", "is_error", "timed_out") if a.get(f) != b.get(f)]
        if diffs:
            mism.append({"call": i, "fields": diffs,
                         "orig": {f: (a.get(f)[:300] if isinstance(a.get(f), str) else a.get(f)) for f in diffs},
                         "replay": {f: (b.get(f)[:300] if isinstance(b.get(f), str) else b.get(f)) for f in diffs}})
    rec["mismatches"] = mism
    rec["n_timed_out_orig"] = sum(bool(c.get("timed_out")) for c in calls)
    oc, rc = adir / "work" / "candidate.v", work / "candidate.v"
    if oc.exists() and rc.exists():
        rec["candidate"] = "identical" if oc.read_bytes() == rc.read_bytes() else "DIFFERENT"
    elif oc.exists() or rc.exists():
        rec["candidate"] = f"PRESENCE DIFFERS (orig {oc.exists()}, replay {rc.exists()})"
    else:
        rec["candidate"] = "absent in both"
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True, type=Path, help="frozen baseline server binary")
    ap.add_argument("--run", action="append", required=True,
                    help="run id, optionally :rep to restrict (e.g. FINAL_pf_baseline_haiku:1)")
    ap.add_argument("--parallel", type=int, default=6)
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scratch = OUT_DIR / "scratch"
    exe = args.exe.resolve()
    for spec in args.run:
        run, _, rep = spec.partition(":")
        rep = int(rep) if rep else None
        adirs = list(attempts_of(run, rep))
        recs = []
        with ThreadPoolExecutor(max_workers=args.parallel) as ex:
            futs = {ex.submit(replay_attempt, exe, a, scratch / run): a for a in adirs}
            for f in as_completed(futs):
                try:
                    recs.append(f.result())
                except Exception as e:  # keep going; report
                    recs.append({"attempt": futs[f].name, "error": repr(e)})
        recs.sort(key=lambda r: r["attempt"])
        n_calls = sum(r.get("n_calls", 0) for r in recs)
        n_mism = sum(len(r.get("mismatches", [])) for r in recs)
        n_short = sum(1 for r in recs if r.get("n_calls", 0) and r.get("n_replayed", 0) != r.get("n_calls", 0))
        cand = {}
        for r in recs:
            cand[r.get("candidate", "?")] = cand.get(r.get("candidate", "?"), 0) + 1
        errors = [r for r in recs if r.get("error")]
        summary = {"run": run, "rep": rep, "exe": str(exe), "attempts": len(recs), "check_calls": n_calls,
                   "mismatching_calls": n_mism, "attempts_with_fewer_replayed_calls": n_short,
                   "candidate_v": cand, "errors": len(errors)}
        (OUT_DIR / f"{run}{'' if rep is None else f'_rep{rep}'}.json").write_text(
            json.dumps({"summary": summary, "attempts": recs}, indent=1))
        print(f"[{spec}] attempts {len(recs)}, check calls {n_calls}, mismatching calls {n_mism}, "
              f"short replays {n_short}, candidate.v {cand}, errors {len(errors)}", flush=True)


if __name__ == "__main__":
    main()
