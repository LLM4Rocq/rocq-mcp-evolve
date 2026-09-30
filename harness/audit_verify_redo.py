#!/usr/bin/env python3
"""Re-audit selected rows single-process and splice the fresh rows into the
audit files (A121).  Use for rows whose first audit ran under heavy parallel
load: our gate's fresh recompile has a 120 s budget and heavy proofs
(vm_compute-style) can hit it when six shards compile at once, which shows
up as gate_now=recompile_failed on a row whose record is solved and whose
sibling verdict is accept -- a false artifact_drift flag.

    python harness/audit_verify_redo.py --auto        # every such row
    python harness/audit_verify_redo.py RUN/PROBLEM/REP [...]

Every replaced row is logged to logs/audit_verify/redo.log with both the
old and the new gate_now / verify verdicts, so the splice is auditable.
Run with the sibling venv python (needs the mcp client):
    /Users/gbaudart/Project/llm4rocq/rocq-mcp/.venv-eval/bin/python
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402

AUDIT = common.LOGS / "audit_verify"
PY = sys.executable
DRIVER = Path(__file__).parent / "audit_verify.py"


def load_flagged():
    keys = []
    for p in sorted(glob.glob(str(AUDIT / "*.jsonl"))):
        run = os.path.basename(p)[:-6]
        for l in open(p):
            r = json.loads(l)
            gn = r.get("gate_now") or {}
            if (not r.get("artifact_post_deadline") and r["gate_solved"]
                    and not gn.get("solved") and gn.get("reason") == "recompile_failed"):
                keys.append((run, r["problem_id"], r["rep"]))
    return keys


def redo(run, pid, rep):
    with tempfile.TemporaryDirectory(prefix="audit_redo_") as td:
        out = Path(td) / "redo.jsonl"
        subprocess.run([PY, "-u", str(DRIVER), "--run", run, "--problems", pid,
                        "--out", str(out)], capture_output=True, text=True, timeout=1800)
        rows = [json.loads(l) for l in open(out)] if out.exists() else []
    return [r for r in rows if r["rep"] == rep]


def splice(run, pid, rep, new, log):
    p = AUDIT / f"{run}.jsonl"
    rows = [json.loads(l) for l in open(p)]
    done = False
    for i, r in enumerate(rows):
        if (r["problem_id"], r["rep"]) == (pid, rep):
            log.write(json.dumps({"ts": time.time(), "run": run, "problem_id": pid, "rep": rep,
                                  "old_gate_now": r.get("gate_now"),
                                  "old_verify": {k: r["verify"].get(k) for k in ("success", "reason")},
                                  "new_gate_now": new.get("gate_now"),
                                  "new_verify": {k: new["verify"].get(k) for k in ("success", "reason")}}) + "\n")
            rows[i] = new
            done = True
    if done:
        with open(p, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--auto", action="store_true")
    a = ap.parse_args()
    keys = [tuple(k.split("/")) for k in a.keys]
    keys = [(r, p, int(x)) for r, p, x in keys]
    if a.auto:
        keys += load_flagged()
    if not keys:
        print("nothing to redo")
        return
    with open(AUDIT / "redo.log", "a") as log:
        for run, pid, rep in keys:
            t0 = time.monotonic()
            new = redo(run, pid, rep)
            if not new:
                print(f"[redo] {run} {pid} rep{rep}: driver produced no row (skipped)")
                continue
            new = new[0]
            ok = splice(run, pid, rep, new, log)
            gn = new.get("gate_now") or {}
            print(f"[redo] {run} {pid} rep{rep}: gate_now={'solved' if gn.get('solved') else gn.get('reason')} "
                  f"verify={'ok' if new['verify'].get('success') else new['verify'].get('reason')} "
                  f"spliced={ok} {time.monotonic()-t0:.0f}s")


if __name__ == "__main__":
    main()
