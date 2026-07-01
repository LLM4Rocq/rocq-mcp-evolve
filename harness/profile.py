#!/usr/bin/env python3
"""Bottleneck profiling from raw attempt logs (tests hypotheses H1-H3).

    python3 harness/profile.py <run_dir>

Per bucket:
  - wall-time decomposition: prover vs model-api vs harness/other
  - prover-call latency histogram + timeout share (H1)
  - input-token growth vs tool-call index (H2)
  - compiler error taxonomy over failed checks (H3)
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common

ERROR_PATTERNS = [
    ("timeout", re.compile(r"TIMED OUT")),
    ("no_applicable", re.compile(r"No applicable tactic|Cannot solve this goal|nsatz cannot infer|lia cannot|lra cannot|Tactic failure")),
    ("unfocused/qed", re.compile(r"Attempt to save an incomplete proof|no focused|not in proof mode|There are pending proofs")),
    ("syntax", re.compile(r"Syntax error")),
    ("unknown_ref", re.compile(r"The reference [^ ]+ was not found|Unknown interpretation|not a defined object")),
    ("type_error", re.compile(r"The term .* has type|Unable to unify|Illegal application")),
    ("unbound_ltac", re.compile(r"Unbound|The variable")),
    ("other_error", re.compile(r"Error:")),
]


def classify(output: str) -> str:
    for name, pat in ERROR_PATTERNS:
        if pat.search(output):
            return name
    return "no_error_text"


def main():
    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        run_dir = common.LOGS / "runs" / sys.argv[1]
    rows = common.read_jsonl(run_dir / "results.jsonl")
    by_bucket = defaultdict(list)
    for r in rows:
        by_bucket[r.get("difficulty", "?")].append(r)

    for bucket, rs in sorted(by_bucket.items()):
        print(f"\n=== bucket: {bucket} ({len(rs)} attempts) ===")
        wall = sum(r.get("wall_s") or 0 for r in rs)
        prover = sum((r.get("prover_ms_total") or 0) / 1000 for r in rs)
        api = sum((r.get("duration_api_ms") or 0) / 1000 for r in rs)
        print(f"wall={wall:.0f}s  prover={prover:.0f}s ({100*prover/max(wall,1):.0f}%)  "
              f"api={api:.0f}s ({100*api/max(wall,1):.0f}%)  [api overlaps prover: tool time is inside api turns]")

        # model-only time = api - prover (approx: prover runs inside tool calls, which block the api loop)
        model_s = api - prover
        print(f"model-side ≈ {model_s:.0f}s ({100*model_s/max(wall,1):.0f}% of wall)")

        durs, timeouts, errkinds = [], 0, Counter()
        tok_growth = defaultdict(list)  # call index -> input tokens at that turn
        for r in rs:
            adir = common.LOGS / r["attempt_dir"] if r.get("attempt_dir") else None
            if not adir or not adir.exists():
                continue
            calls = [x for x in common.read_jsonl(adir / "server.jsonl") if x.get("kind") == "tool_call"]
            for i, c in enumerate(calls):
                d = c.get("prover_ms")
                if d is not None:
                    durs.append(d)
                if c.get("timed_out"):
                    timeouts += 1
                if c.get("exit_code", 0) != 0:
                    errkinds[classify(c.get("result", ""))] += 1
            # token growth: index assistant messages in order
            idx = 0
            seen = set()
            for ev in common.read_jsonl(adir / "transcript.jsonl"):
                if ev.get("type") != "assistant":
                    continue
                mid = ev.get("message", {}).get("id")
                if mid in seen:
                    continue
                seen.add(mid)
                u = ev.get("message", {}).get("usage", {})
                tin = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                tok_growth[idx].append(tin)
                idx += 1

        if durs:
            sd = sorted(durs)
            def q(p):
                return sd[min(len(sd) - 1, int(p * (len(sd) - 1)))]
            print(f"prover calls: n={len(durs)} p50={q(.5):.0f}ms p90={q(.9):.0f}ms p99={q(.99):.0f}ms "
                  f"timeouts={timeouts} ({100*timeouts/len(durs):.1f}%)")
            slow = sum(d for d in durs if d >= 0.9 * max(durs))
            print(f"time in timeout-ceiling calls: {sum(d for d in durs if d > 55_000)/1000:.0f}s "
                  f"of {sum(durs)/1000:.0f}s total prover time "
                  f"({100*sum(d for d in durs if d > 55_000)/max(sum(durs),1):.0f}%)")
        if errkinds:
            print("failed-check taxonomy:", dict(errkinds.most_common()))
        if tok_growth:
            print("input tokens by turn idx (mean): "
                  + " ".join(f"{i}:{sum(v)/len(v):.0f}" for i, v in sorted(tok_growth.items())[:12]))


if __name__ == "__main__":
    main()
