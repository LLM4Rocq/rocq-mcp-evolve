#!/usr/bin/env python3
# Origin: a tables directory maintained beside the results summary's former
# home. Moved into this repository's harness/results_tables/ on 2026-09-08.
# Exposes build(exp_root) -> dict (the results_all_gen.py entry point);
# main() still writes dev60_cap30.json for ad-hoc use (default: docs/results_tables/,
# via --out-dir) but nothing under docs/results_tables/ is tracked any more.
"""Counterfactual cap-30 censoring of the Mistral and terra dev60 arms
(T-CENSOR; RESULTS_ALL section 2's "uniform cap-30 arena" view). A solve
recorded past turn 30 (num_turns > 30 in the model-agnostic drivers' turn
count) counts as unsolved; pass@1 is the campaign convention (solved
attempts / attempts over all reps, per bucket and pooled). Only the
accuracy censor is computed here; the cost and wall truncation at the
turn-30 boundary printed in RESULTS_ALL section 2 is computed separately,
by cap30_truncation.py. Descriptive (development data).

Usage: python3 dev60_cap30.py [EXPERIMENT_REPO_ROOT]
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]

ARMS = {"mistral": {"control": "mstp_base_dev60", "sibling": "mstp_sota_dev60_v2", "evolve": "mstp_evolve_dev60"},
        "terra": {"control": "orp_base_dev60", "sibling": "orp_sib_dev60", "evolve": "orp_evolve_dev60"}}
CAP = 30
BUCKETS = ("easy", "medium", "hard")


def build(exp_root):
    """Return exactly the dict this producer writes as dev60_cap30.json."""
    runs_dir = exp_root / "logs" / "runs"
    out = {"note": __doc__.strip(), "cap": CAP, "families": {}}
    for fam, arms in ARMS.items():
        out["families"][fam] = {}
        for arm, run in arms.items():
            rows = [json.loads(l) for l in open(runs_dir / run / "results.jsonl") if l.strip()]
            by_b = defaultdict(list)
            for r in rows:
                by_b[r["difficulty"]].append(r)
            rec = {"run": run, "buckets": {}, "pooled": {}}
            tot_raw = tot_cen = 0
            for b in BUCKETS:
                rs = by_b[b]
                raw = sum(1 for r in rs if r.get("solved"))
                cen = sum(1 for r in rs if r.get("solved") and (r.get("num_turns") or 0) <= CAP)
                rec["buckets"][b] = {"attempts": len(rs), "solved_raw": raw, "solved_cap30": cen,
                                     "pass1_raw": round(raw / len(rs), 3), "pass1_cap30": round(cen / len(rs), 3)}
                tot_raw += raw
                tot_cen += cen
            rec["pooled"] = {"attempts": len(rows), "solved_raw": tot_raw, "solved_cap30": tot_cen,
                             "pass1_raw": round(tot_raw / len(rows), 3), "pass1_cap30": round(tot_cen / len(rows), 3),
                             "solves_lost_to_censor": tot_raw - tot_cen}
            out["families"][fam][arm] = rec
    return out


def main():
    ap = argparse.ArgumentParser(description="Counterfactual cap-30 censoring of the dev60 arms.")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                     help="experiment repo root (default: this repository)")
    ap.add_argument("--out-dir", type=Path, default=None,
                     help="directory to write dev60_cap30.json into "
                          "(default: <exp_root>/docs/results_tables)")
    args = ap.parse_args()
    out = build(args.exp_root)
    for fam, arms in out["families"].items():
        for arm, rec in arms.items():
            p = rec["pooled"]
            print(f"{fam:8s} {arm:8s} raw {p['pass1_raw']:.3f} cap30 {p['pass1_cap30']:.3f} lost {p['solves_lost_to_censor']}")
    out_dir = args.out_dir or (args.exp_root / "docs" / "results_tables")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dev60_cap30.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {out_dir / 'dev60_cap30.json'}")


if __name__ == "__main__":
    main()
