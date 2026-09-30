#!/usr/bin/env python3
# Origin: a tables directory maintained beside the results summary's former
# home. Moved into this repository's harness/results_tables/ on 2026-09-08.
# Exposes build(exp_root) -> dict (the results_all_gen.py entry point);
# main() still writes finisher_partition.json for ad-hoc use (default:
# docs/results_tables/, via --out-dir), but nothing under docs/results_tables/
# is tracked any more.
"""A114 declared analysis: finisher-only solve set F and the overlap
partition against the rep-0 solve sets of the held-out arms.
    python3 finisher_partition.py <experiment_repo_root>
"""
import argparse
import json
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def _rep0_solved(exp_root, run):
    rows = [json.loads(l) for l in open(exp_root / "logs/runs" / run / "results.jsonl")]
    return {r["problem_id"] for r in rows if r.get("rep", 0) == 0 and r["solved"]}, \
           {r["problem_id"]: r.get("difficulty") for r in rows if r.get("rep", 0) == 0}


def build(exp_root):
    """Return exactly the dict this producer writes as finisher_partition.json."""
    F, buckets = _rep0_solved(exp_root, "finisher_only_test")
    E, _ = _rep0_solved(exp_root, "FINAL_pf_session2_sonnet")
    C, _ = _rep0_solved(exp_root, "FINAL_pf_baseline_sonnet")
    S, _ = _rep0_solved(exp_root, "FINAL_pf_rocqmcp_sonnet")
    M, _ = _rep0_solved(exp_root, "mstf_evolve_test")
    MC, _ = _rep0_solved(exp_root, "mstf_base_test")
    MS2, _ = _rep0_solved(exp_root, "mstf_sota_test")

    def bk(s):
        out = {"easy": 0, "medium": 0, "hard": 0}
        for p in s:
            out[buckets[p]] += 1
        return f"{out['easy']}/{out['medium']}/{out['hard']}"

    return {
        "F_total": len(F), "F_buckets": bk(F),
        "E_total": len(E), "E_and_F": len(E & F), "E_minus_F": len(E - F),
        "F_minus_E": len(F - E),
        "C_and_F": len(C & F), "S_and_F": len(S & F), "M_and_F": len(M & F),
        "M_total": len(M), "M_minus_F": len(M - F),
        "Mctrl_total": len(MC), "Mctrl_and_F": len(MC & F), "Mctrl_minus_F": len(MC - F),
        "Msib_total": len(MS2), "Msib_and_F": len(MS2 & F),
    }


def main():
    ap = argparse.ArgumentParser(description="A114 finisher-only overlap partition.")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                     help="experiment repo root (default: this repository)")
    ap.add_argument("--out-dir", type=Path, default=None,
                     help="directory to write finisher_partition.json into "
                          "(default: <exp_root>/docs/results_tables)")
    args = ap.parse_args()
    res = build(args.exp_root)
    print(json.dumps(res, indent=1))
    print(f"\nfinisher-only F = {res['F_total']}/244 ({res['F_buckets']} e/m/h)")
    print(f"evolve E = {res['E_total']}: portfolio-closable |E∩F| = {res['E_and_F']} "
          f"({100*res['E_and_F']/res['E_total']:.0f}%), model-required |E\\F| = {res['E_minus_F']} "
          f"({100*res['E_minus_F']/res['E_total']:.0f}%)")
    print(f"mistral evolve M = {res['M_total']}: |M∩F| = {res['M_and_F']} "
          f"({100*res['M_and_F']/res['M_total']:.0f}%), model-required {res['M_minus_F']}")
    out_dir = args.out_dir or (args.exp_root / "docs" / "results_tables")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "finisher_partition.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
