#!/usr/bin/env python3
# New module (2026-09-08): replaces the six hand-typed cap-30 $/solve and
# six hand-typed cap-30 wall cells of RESULTS_ALL §2 (mistral and terra
# dev60 rows) with a computation over the per-call transcripts.
"""Per-attempt cost/wall truncated at the turn-30 boundary for a dev60
mistral (mstp_*) or terra (orp_*) run, and the per-bucket aggregates
RESULTS_ALL §2 renders from them.

Per attempt: if num_turns <= 30, cost/wall are the recorded total_cost_usd
and wall_s. Otherwise, truncate at the turn-30 boundary from the attempt's
transcript.jsonl (whose "assistant" lines are one per model call, in order,
each carrying usage and ts): cost = sum over the first 30 assistant lines'
per-call cost (terra: usage["cost"]; mistral: (prompt_tokens * in_rate +
completion_tokens * out_rate) / 1e6, at the per-model rate table imported
from harness/mistral_driver.py -- never copied); wall = the ts of the end of
turn 30 (the event following the 30th assistant line, i.e. its tool result
coming back; the line itself when nothing follows) minus the ts of the
transcript's first line -- a turn ends when its tool result is back, which
is also what the recorded wall_s of an attempt stopping at the cap measures.

build(exp_root, run) returns, per bucket, the SUM of truncated cost and the
MEAN of truncated wall over every attempt of the bucket (not just solved
ones) -- $/solve is then that total cost divided by the cap-30 solved
count the generator already computes (dev60_cap30.py's solved_ok(cap=30)
rule); wall is that mean directly.

Usage: python3 cap30_truncation.py <run> [EXPERIMENT_REPO_ROOT]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BUCKETS = ("easy", "medium", "hard")
CAP = 30


def attempt_cost_wall(exp_root, run, row, cap=CAP):
    """Truncated (cost, wall) for one dev60 mistral/terra results.jsonl row."""
    nt = row.get("num_turns") or 0
    if nt <= cap:
        return row.get("total_cost_usd") or 0, row["wall_s"]
    name = row.get("problem_id")
    path = (exp_root / "logs" / "runs" / run / "attempts"
            / f"{name}__rep{row.get('rep', 0)}" / "transcript.jsonl")
    lines = [json.loads(l) for l in open(path) if l.strip()]
    first_ts = lines[0]["ts"]
    asst_idx = [i for i, l in enumerate(lines) if l.get("type") == "assistant"]
    first_cap = [lines[i] for i in asst_idx[:cap]]
    # a turn ends when its tool result is back: the boundary is the event
    # that FOLLOWS the cap-th model reply (its tool_result line), or that
    # reply itself when nothing follows -- the same end-of-turn reading the
    # recorded wall_s uses for an attempt that stops at the cap
    end_idx = min(asst_idx[cap - 1] + 1, len(lines) - 1)
    wall = lines[end_idx]["ts"] - first_ts
    if "prompt_tokens" in row:  # terra (OpenRouter): dispatch as results_all_gen.py does elsewhere
        cost = sum((l.get("usage") or {}).get("cost", 0) or 0 for l in first_cap)
    else:  # mistral
        sys.path.insert(0, str(HERE.parent))
        from mistral_driver import PRICES  # noqa: E402
        in_rate, out_rate = PRICES.get(row.get("model"), (0.0, 0.0))
        cost = sum(((l.get("usage") or {}).get("prompt_tokens", 0) or 0) * in_rate
                    + ((l.get("usage") or {}).get("completion_tokens", 0) or 0) * out_rate
                    for l in first_cap) / 1e6
    return cost, wall


def build(exp_root, run, cap=CAP):
    """Per-bucket {"total_cost", "mean_wall", "n"} over ALL attempts of one
    mistral/terra dev60 run, cap-30 truncated."""
    rows = [json.loads(l) for l in open(exp_root / "logs" / "runs" / run / "results.jsonl") if l.strip()]
    by_b = defaultdict(list)
    for r in rows:
        by_b[r["difficulty"]].append(r)
    out = {}
    for b in BUCKETS:
        rs = by_b[b]
        total_cost = total_wall = 0.0
        for r in rs:
            c, w = attempt_cost_wall(exp_root, run, r, cap=cap)
            total_cost += c
            total_wall += w
        out[b] = {"total_cost": total_cost, "mean_wall": (total_wall / len(rs)) if rs else None, "n": len(rs)}
    return out


def main():
    ap = argparse.ArgumentParser(description="Cap-30 truncated cost/wall aggregates for one dev60 run.")
    ap.add_argument("run", help="run id under logs/runs/ (mstp_* or orp_* dev60)")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                     help="experiment repo root (default: this repository)")
    args = ap.parse_args()
    print(json.dumps(build(args.exp_root, args.run), indent=1))


if __name__ == "__main__":
    main()
