#!/usr/bin/env python3
# New module (2026-09-08): ported (single-run form) from a sibling archive's
# tables/rail_census.py, which censused every archived run at once. This
# repository only needs the count for one run at a time (RESULTS_ALL §3
# head, the mistral evolve test arm's cap-100 rail sentence), so build()
# takes a run name rather than replaying the whole RUN_LIST.
"""build(exp_root, run) -> the cap-termination census for one run:
{"n", "solved", "non_solved", "rail_terminated_nonsolves", "max_turns",
"rail_rule"}. Cap termination is num_turns == max_turns (max_turns from the
run's run_meta.json config) among NON-solved rows, for the model-agnostic
drivers (mistral_driver.py, openrouter_prover.py: the loop exits at exactly
max_turns) -- the Claude-CLI off-by-one rule (num_turns >= max_turns + 1) is
not needed by anything RESULTS_ALL renders and is not ported. Descriptive.

Usage: python3 rail_census.py <run> [EXPERIMENT_REPO_ROOT]
"""
import argparse
import json
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def build(exp_root, run):
    """Cap-termination census for one run's results.jsonl."""
    run_dir = exp_root / "logs" / "runs" / run
    rows = [json.loads(l) for l in open(run_dir / "results.jsonl") if l.strip()]
    meta = json.load(open(run_dir / "run_meta.json"))
    max_turns = meta.get("config", {}).get("max_turns") or 0

    def capped(r):
        nt = r.get("num_turns")
        if nt is None or r.get("solved"):
            return False
        return nt == max_turns

    non_solved = [r for r in rows if not r.get("solved")]
    return {"run": run, "n": len(rows), "solved": len(rows) - len(non_solved),
            "non_solved": len(non_solved),
            "rail_terminated_nonsolves": sum(1 for r in non_solved if capped(r)),
            "max_turns": max_turns, "rail_rule": "num_turns == max_turns"}


def main():
    ap = argparse.ArgumentParser(description="Cap-termination census for one run.")
    ap.add_argument("run", help="run id under logs/runs/")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                     help="experiment repo root (default: this repository)")
    args = ap.parse_args()
    rec = build(args.exp_root, args.run)
    print(json.dumps(rec, indent=1))
    print(f"{rec['rail_terminated_nonsolves']}/{rec['n']} attempts ended at the "
          f"cap-{rec['max_turns']} rail")


if __name__ == "__main__":
    main()
