#!/usr/bin/env python3
"""Decomposable-problem manifest (team re-test): mechanically probe every dev
problem — execute the statement in a session, try `split.` (and
`intros. split.`) — and keep problems yielding >= 2 open goals.

    python3 harness/make_decomposable_manifest.py
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common
from run_eval import build_task

SESSION = common.REPO / "_build/default/src/session_server/rocq_agent_session.exe"


def probe(prefix: str) -> int:
    """Max open goals reachable by a cheap structural split, else 1/0."""
    with tempfile.TemporaryDirectory() as td:
        tf = Path(td) / "task.v"
        tf.write_text(prefix)
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "try", "arguments":
                        {"candidates": ["split.", "intros. split.", "intros; split."],
                         "commit": "none"}}},
        ]
        try:
            p = subprocess.run(
                [str(SESSION)],
                input="".join(json.dumps(m) + "\n" for m in msgs),
                env={"PATH": f"{common.OPAM_BIN}:/usr/bin:/bin",
                     "HOME": str(Path.home()),
                     "ROCQ_TASK_FILE": str(tf), "ROCQ_WORKDIR": td,
                     "ROCQ_ENV_V2": "1",
                     "ROCQ_ENABLE_TOOLS": "try"},
                capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return 0
    best = 1
    for line in p.stdout.splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        txt = str(d.get("result", {}).get("content", ""))
        for m in re.finditer(r"OK, (\d+) goal\(s\) left", txt):
            best = max(best, int(m.group(1)))
    return best


def main():
    seen, out = set(), []
    for mani in ["dev60", "dev150", "hard70"]:
        for rec in common.load_manifest(mani):
            if rec["problem_id"] in seen:
                continue
            seen.add(rec["problem_id"])
            prefix, _ = build_task(rec)
            g = probe(prefix)
            if g >= 2:
                rec2 = dict(rec)
                rec2["probe_goals"] = g
                out.append(rec2)
    p = common.MANIFESTS / "decomposable.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in out))
    from collections import Counter
    print(f"wrote {len(out)} decomposable problems to {p}")
    print("by bucket:", dict(Counter(r["difficulty"] for r in out)))
    print("by probe goals:", dict(Counter(r["probe_goals"] for r in out)))


if __name__ == "__main__":
    main()
