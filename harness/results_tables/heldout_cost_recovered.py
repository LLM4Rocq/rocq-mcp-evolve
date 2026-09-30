#!/usr/bin/env python3
# Origin: a tables directory maintained beside the results summary's former
# home. Moved into this repository's harness/results_tables/ on 2026-09-08.
# Exposes build(exp_root) -> dict (the results_all_gen.py entry point);
# main() still writes heldout_cost_recovered.json for ad-hoc use (default:
# docs/results_tables/, via --out-dir), but nothing under docs/results_tables/
# is tracked any more.
"""Held-out $/solve for the SONNET prompt-free arms under the recovered-cost
convention (T-COST1): the cost of a wall-killed attempt (no CLI result
event, total_cost_usd null) is recovered from the per-message usage in its
transcript at the claude-sonnet-5 cache-aware rate table used by the
experiment repo's autoformalization dashboard (input 3e-6, output 15e-6,
cache read 0.3e-6, cache write 3.75e-6 USD per token). Printed beside the
RESULTS_ALL section 3 convention (killed attempts contribute zero). Only
sonnet is covered because the repo holds no rate table for the haiku and
opus tiers. Descriptive.

Usage: python3 heldout_cost_recovered.py [EXPERIMENT_REPO_ROOT]
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]

RIN, ROUT, RCR, RCW = 3e-6, 15e-6, 0.3e-6, 3.75e-6
ARMS = {"control": "FINAL_pf_baseline_sonnet", "sibling": "FINAL_pf_rocqmcp_sonnet",
        "evolve": "FINAL_pf_session2_sonnet", "evolve_superseded_A80": "FINAL_pf_session_sonnet"}


def _recover(logs, attempt_dir):
    tp = logs / attempt_dir / "transcript.jsonl"
    if not tp.exists():
        return 0.0, "no_transcript"
    tot = 0.0
    for line in tp.read_text(errors="replace").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "result" and e.get("total_cost_usd") is not None:
            return e["total_cost_usd"], "result_event"
        if e.get("type") == "assistant":
            u = e.get("message", {}).get("usage", {}) or {}
            tot += (u.get("input_tokens", 0) * RIN + u.get("output_tokens", 0) * ROUT
                    + u.get("cache_read_input_tokens", 0) * RCR + u.get("cache_creation_input_tokens", 0) * RCW)
    return tot, "recovered_from_usage"


def build(exp_root):
    """Return exactly the dict this producer writes as heldout_cost_recovered.json."""
    logs = exp_root / "logs"
    out = {"note": __doc__.strip(), "arms": {}}
    for arm, run in ARMS.items():
        rows = [json.loads(l) for l in open(logs / "runs" / run / "results.jsonl") if l.strip()]
        by_b = defaultdict(list)
        for r in rows:
            c = r.get("total_cost_usd")
            src = "results_row"
            if c is None:
                c, src = _recover(logs, r["attempt_dir"])
            r["_cost_rec"] = c
            r["_cost_src"] = src
            by_b[r["difficulty"]].append(r)
        rec = {"run": run, "buckets": {}, "pooled": {}}
        for b in ("easy", "medium", "hard", "ALL"):
            rs = rows if b == "ALL" else by_b[b]
            solved = sum(1 for r in rs if r.get("solved"))
            raw = sum(r.get("total_cost_usd") or 0 for r in rs)
            recd = sum(r["_cost_rec"] for r in rs)
            cell = {"attempts": len(rs), "solved_attempts": solved,
                    "rows_missing_cost": sum(1 for r in rs if r.get("total_cost_usd") is None),
                    "recovered_rows": sum(1 for r in rs if r["_cost_src"] == "recovered_from_usage"),
                    "total_cost_res3_convention": round(raw, 2), "total_cost_recovered": round(recd, 2),
                    "cost_per_solve_res3_convention": round(raw / solved, 3) if solved else None,
                    "cost_per_solve_recovered": round(recd / solved, 3) if solved else None}
            (rec["pooled"] if b == "ALL" else rec["buckets"]).update({b: cell} if b != "ALL" else cell)
        out["arms"][arm] = rec
    return out


def main():
    ap = argparse.ArgumentParser(description="Held-out $/solve, recovered-cost convention (sonnet).")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                     help="experiment repo root (default: this repository)")
    ap.add_argument("--out-dir", type=Path, default=None,
                     help="directory to write heldout_cost_recovered.json into "
                          "(default: <exp_root>/docs/results_tables)")
    args = ap.parse_args()
    out = build(args.exp_root)
    for arm, rec in out["arms"].items():
        print(f"{arm:24s} $/solve e/m/h RES3 " + "/".join(f"{rec['buckets'][b]['cost_per_solve_res3_convention']:.2f}" for b in ("easy", "medium", "hard"))
              + "  recovered " + "/".join(f"{rec['buckets'][b]['cost_per_solve_recovered']:.2f}" for b in ("easy", "medium", "hard"))
              + f"  pooled {rec['pooled']['cost_per_solve_res3_convention']:.3f} -> {rec['pooled']['cost_per_solve_recovered']:.3f}")
    out_dir = args.out_dir or (args.exp_root / "docs" / "results_tables")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "heldout_cost_recovered.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {out_dir / 'heldout_cost_recovered.json'}")


if __name__ == "__main__":
    main()
