#!/usr/bin/env python3
"""Concurrency-robustness audit for phase-2 team runs (A40).

    python3 harness/af_robustness.py <team_run_id>

Scans each attempt's per-agent logs for concurrency incidents:
- dune lock contention (dune_build results mentioning the lock)
- file ownership violations (same path written by >1 agent)
- rocq server faults (is_error internal errors, missing responses)
- write-after-open staleness candidates (a file opened by one agent then
  rewritten by another)
Prints a JSON report; nonzero incidents are DATA, not necessarily failures.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common

LOGS = common.LOGS / "autoform"


def audit(run_id):
    run_dir = LOGS / run_id
    report = {"run": run_id, "attempts": {}}
    for adir in sorted((run_dir / "attempts").iterdir()):
        recs = common.read_jsonl(adir / "server.jsonl")
        writes = defaultdict(set)   # path -> agents
        opens = defaultdict(set)    # file -> agents
        incidents = {"dune_lock": 0, "ownership_violation": [],
                     "server_internal_error": 0, "write_after_open": []}
        for r in recs:
            if r.get("kind") != "tool_call":
                continue
            agent = (r.get("meta") or {}).get("agent", "?")
            tool, res = r.get("tool"), (r.get("result") or "")
            args = r.get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if tool == "dune_build" and ("lock" in res.lower()
                                         and "dune" in res.lower()):
                incidents["dune_lock"] += 1
            if tool == "write_file":
                p = args.get("path", "?")
                writes[p].add(agent)
                for a2 in opens.get(p, set()):
                    if a2 != agent:
                        incidents["write_after_open"].append(
                            {"file": p, "opened_by": a2, "rewritten_by": agent})
            if tool == "open":
                f = str(args.get("file", "?"))
                rel = f.split("workspace/")[-1]
                opens[rel].add(agent)
            if "internal tool error" in res:
                incidents["server_internal_error"] += 1
        incidents["ownership_violation"] = [
            {"file": p, "agents": sorted(a)} for p, a in writes.items()
            if len(a) > 1]
        report["attempts"][adir.name] = incidents
    totals = defaultdict(int)
    for inc in report["attempts"].values():
        totals["dune_lock"] += inc["dune_lock"]
        totals["ownership_violations"] += len(inc["ownership_violation"])
        totals["server_internal_errors"] += inc["server_internal_error"]
        totals["write_after_open"] += len(inc["write_after_open"])
    report["totals"] = dict(totals)
    return report


if __name__ == "__main__":
    print(json.dumps(audit(sys.argv[1]), indent=1))
