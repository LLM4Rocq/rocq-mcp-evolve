#!/usr/bin/env python3
"""Independent re-verification of recorded attempts with the sibling server's
`rocq_verify` tool (rocq-mcp), driven over its real MCP stdio interface.

For every attempt of a run that left a graded artifact (work/candidate.v or
work/submissions/*.v), the artifact the gate graded is re-submitted to
`rocq_verify(proof, problem_name, problem_statement)`: the sibling wraps the
proof in a `Module M.` sandbox, restates the original statement outside it,
closes it with `exact M.<name>`, and audits `Print Assumptions`. Its verdict
is recorded next to the gate's (`solved` / `reject_reason`) so the two can be
compared row by row. Nothing in logs/runs is modified.

Faithfulness choices (all recorded in every output row):
  * artifact selection replays run_eval.run_attempt: submissions/ (newest
    that the gate did not reject as recompile_failed) take precedence over
    candidate.v -- the SAME file the gate graded is what gets re-verified.
  * ambient environment: the gate compiles with `-ri Stdlib.micromega.Lia`,
    `Lra`, `Psatz` (gate.ENV_INJECT, A11). rocq_verify accepts no coqc flags,
    so the equivalent `Require Import ...` line is prepended to the proof
    text (`--no-env-inject` disables this, for the record).
  * problem_statement = the shipped task prefix (task_prefix.v); the target
    is the LAST theorem in it (datasets.statement_prefix convention).
  * same prover: PATH puts the experiment switch first (common.prover_env),
    so coqc is the Rocq the gate used; server = the pinned sibling binary.

Rows the gate graded as no_candidate are not auditable (whatever file sits
in work/ today was not there at grading) and are skipped.  Every audited row
also carries (i) the artifact's mtime relative to the attempt's end
(`artifact_late_s`; a positive value means the file was rewritten AFTER
grading -- A93 class -- and is not the graded artifact) and (ii) today's
verdict of our own gate on the same file (`gate_now`), so a verifier
disagreement can be separated from artifact drift.  Output: one JSON line
per audited attempt in logs/audit_verify/<run>.jsonl (idempotent: --resume
skips attempts already present).

    .venv-eval python:  /Users/gbaudart/Project/llm4rocq/rocq-mcp/.venv-eval/bin/python
    python harness/audit_verify.py --run FINAL_pf_baseline_opus [--limit 6]
        [--which solved|rejected|all] [--out PATH] [--resume] [--no-env-inject]
        [--no-gate-recheck] [--problems id1,id2] [--server PATH] [--timeout 120]
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
import gate  # noqa: E402

SIBLING = Path("/Users/gbaudart/Project/llm4rocq/rocq-mcp")
SERVER_DEFAULT = SIBLING / ".venv-eval" / "bin" / "rocq-mcp"
# gate.ENV_INJECT as a Require line: -ri M == import M before the file.
ENV_REQUIRE = "Require Import " + " ".join(
    gate.ENV_INJECT[i + 1] for i in range(0, len(gate.ENV_INJECT), 2)) + ".\n"
THM_RE = re.compile(
    r"\b(Theorem|Lemma|Fact|Corollary|Proposition|Remark|Example)\s+"
    r"([A-Za-z_][A-Za-z0-9_']*)")


def rows_of(run):
    p = common.LOGS / "runs" / run / "results.jsonl"
    return [json.loads(l) for l in open(p)]


def attempt_dir(run, r):
    rel = r.get("attempt_dir") or f"runs/{run}/attempts/{r['problem_id']}__rep{r.get('rep', 0)}"
    return common.LOGS / rel


def theorem_name(prefix):
    ms = THM_RE.findall(prefix)
    return ms[-1][1] if ms else None


def graded_artifact(work, prefix, thm):
    """Replay run_eval's selection: which file did the gate grade?"""
    subs = sorted((work / "submissions").glob("*.v"), reverse=True) \
        if (work / "submissions").exists() else []
    if subs:
        if len(subs) == 1:
            return subs[0], "submission"
        for sub in subs:  # newest first; first non-recompile-failure wins
            r = gate.check(sub.read_text(), prefix, thm)
            if r.get("reason") not in ("recompile_failed", "compile_failed"):
                return sub, "submission(replayed-gate)"
        return subs[0], "submission(newest;all-recompile-failed)"
    if (work / "candidate.v").exists():
        return work / "candidate.v", "candidate"
    return None, None


def server_identity(server):
    ident = {"server": str(server)}
    try:
        ident["version"] = subprocess.run(
            [str(server.parent / "python"), "-c",
             "import importlib.metadata as m; print(m.version('rocq-mcp'))"],
            capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:  # pragma: no cover
        ident["version"] = f"unknown ({e})"
    try:
        ident["commit"] = subprocess.run(
            ["git", "-C", str(SIBLING), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True).stdout.strip()
        ident["dirty"] = bool(subprocess.run(
            ["git", "-C", str(SIBLING), "status", "--short", "--untracked-files=no"],
            capture_output=True, text=True).stdout.strip())
    except Exception:
        pass
    ident["coqc"] = subprocess.run(
        ["coqc", "--version"], env=common.prover_env(),
        capture_output=True, text=True).stdout.strip().splitlines()[0]
    return ident


def tool_result_dict(res):
    """Unwrap a FastMCP tools/call result into the tool's dict envelope."""
    sc = getattr(res, "structuredContent", None)
    if isinstance(sc, dict):
        return sc.get("result", sc) if set(sc) == {"result"} else sc
    for c in res.content or []:
        t = getattr(c, "text", None)
        if t:
            try:
                return json.loads(t)
            except json.JSONDecodeError:
                return {"success": False, "reason": "client_unparsed", "error": t[:2000]}
    return {"success": False, "reason": "client_empty", "error": "no content"}


async def audit(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    run = args.run
    out = Path(args.out) if args.out else common.LOGS / "audit_verify" / f"{run}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.resume and out.exists():
        for l in open(out):
            r = json.loads(l)
            done.add((r["problem_id"], r["rep"]))

    rows = rows_of(run)
    if args.problems:
        keep = set(args.problems.split(","))
        rows = [r for r in rows if r["problem_id"] in keep]
    if args.which == "solved":
        rows = [r for r in rows if r["solved"]]
    elif args.which == "rejected":
        rows = [r for r in rows if not r["solved"]]

    ident = server_identity(Path(args.server))
    ws = Path(tempfile.mkdtemp(prefix="audit_ws_"))
    env = common.prover_env()
    env.update({
        "ROCQ_WORKSPACE": str(ws),
        "ROCQ_VERIFY_TIMEOUT": str(args.timeout),
        "ROCQ_COQC_TIMEOUT": str(args.timeout),
        "PYTHONUNBUFFERED": "1",
    })
    params = StdioServerParameters(command=args.server, args=[], env=env, cwd=str(ws))
    n_audit = n_skip = n_agree = n_dis = 0
    t_start = time.time()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = [t.name for t in (await session.list_tools()).tools]
            if "rocq_verify" not in tools:
                sys.exit(f"rocq_verify not exposed by {args.server}: {tools}")
            print(f"[audit {run}] server {ident} tools={len(tools)} rows={len(rows)} "
                  f"resume-skip={len(done)} env_inject={not args.no_env_inject}", flush=True)
            with open(out, "a") as fo:
                for r in rows:
                    key = (r["problem_id"], r.get("rep", 0))
                    if key in done:
                        continue
                    if args.limit and n_audit >= args.limit:
                        break
                    adir = attempt_dir(run, r)
                    pfile = adir / "task_prefix.v"
                    # graded as no_candidate: nothing was there at grading time;
                    # a file present today was written afterwards (not auditable)
                    if not pfile.exists() or r.get("reject_reason") == "no_candidate":
                        n_skip += 1
                        continue
                    prefix = pfile.read_text()
                    thm = theorem_name(prefix)
                    art, kind = graded_artifact(adir / "work", prefix, thm)
                    if art is None or thm is None:
                        n_skip += 1
                        continue
                    raw_proof = art.read_text()
                    # artifact drift: mtime after the attempt's end == rewritten
                    # after grading (A93 class); the graded file is gone
                    end = (r.get("ts") or 0) + (r.get("wall_s") or 0)
                    late = round(os.path.getmtime(art) - end, 1) if r.get("ts") else None
                    gate_now = None
                    if not args.no_gate_recheck:
                        g = gate.check(raw_proof, prefix, thm)
                        gate_now = {"solved": g["solved"], "reason": g["reason"],
                                    "axioms": g["axioms"]}
                    proof = raw_proof
                    if not args.no_env_inject:
                        proof = ENV_REQUIRE + proof
                    t0 = time.monotonic()
                    try:
                        res = await session.call_tool(
                            "rocq_verify",
                            arguments={"proof": proof, "problem_name": thm,
                                       "problem_statement": prefix,
                                       "workspace": str(ws),
                                       "timeout": args.timeout,
                                       "include_warnings": False},
                            read_timeout_seconds=timedelta(seconds=3 * args.timeout + 60))
                        v = tool_result_dict(res)
                    except Exception as e:
                        v = {"success": False, "reason": "client_error",
                             "error": f"{type(e).__name__}: {e}"[:2000]}
                    el = round(time.monotonic() - t0, 3)
                    if isinstance(v.get("error"), str):
                        v["error"] = v["error"][-2000:]
                    agree = bool(v.get("success")) == bool(r["solved"])
                    rec = {
                        "ts": time.time(), "run_id": run,
                        "problem_id": r["problem_id"], "rep": r.get("rep", 0),
                        "difficulty": r.get("difficulty"),
                        "attempt_dir": str(adir.relative_to(common.LOGS)),
                        "artifact": str(art.relative_to(adir)), "artifact_kind": kind,
                        "theorem_name": thm,
                        "gate_solved": r["solved"], "gate_reason": r.get("reject_reason"),
                        "gate_axioms": (r.get("gate") or {}).get("axioms"),
                        "attempt_timed_out": r.get("attempt_timed_out"),
                        "artifact_late_s": late,
                        "artifact_post_deadline": (late is not None and late > 2.0),
                        "gate_now": gate_now,
                        "artifact_reproduces_record": (
                            None if gate_now is None else gate_now["solved"] == r["solved"]),
                        "env_inject": not args.no_env_inject,
                        "verify": v, "verify_s": el, "agree": agree,
                        "server": ident,
                    }
                    fo.write(json.dumps(rec) + "\n")
                    fo.flush()
                    n_audit += 1
                    n_agree += agree
                    n_dis += (not agree)
                    tag = "AGREE" if agree else "DISAGREE"
                    if rec["artifact_post_deadline"]:
                        tag += f" [artifact rewritten {late:.0f}s after attempt end]"
                    if gate_now is not None and not rec["artifact_reproduces_record"]:
                        tag += f" [gate today: {gate_now['reason'] or 'solved'} != record]"
                    print(f"[audit {run}] {n_audit:4d} {r['problem_id']:32s} rep{r.get('rep',0)} "
                          f"gate={'solved' if r['solved'] else 'no:'+str(r.get('reject_reason'))} "
                          f"verify={'ok' if v.get('success') else 'no:'+str(v.get('reason'))} "
                          f"{v.get('verification_method','')} {el:.1f}s {tag}", flush=True)
    print(f"[audit {run}] done: audited={n_audit} agree={n_agree} disagree={n_dis} "
          f"skipped_no_artifact={n_skip} in {time.time()-t_start:.0f}s -> {out}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--which", choices=["solved", "rejected", "all"], default="all")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--problems", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--no-env-inject", action="store_true")
    ap.add_argument("--no-gate-recheck", action="store_true")
    ap.add_argument("--server", default=str(SERVER_DEFAULT))
    ap.add_argument("--timeout", type=int, default=120)
    asyncio.run(audit(ap.parse_args()))


if __name__ == "__main__":
    main()
