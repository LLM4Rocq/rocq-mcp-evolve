#!/usr/bin/env python3
# Origin: a tables directory maintained beside the results summary's former
# home. Moved into this repository's harness/results_tables/ on 2026-09-08.
# Exposes build(exp_root) -> dict (the results_all_gen.py entry point);
# main() still writes autoform_arms.json for ad-hoc use (default:
# docs/results_tables/, via --out-dir), but nothing under docs/results_tables/
# is tracked any more.
"""Autoformalization arms archive (T-AFKILLS, T-COST2, T-TRIADIC): every
non-smoke autoformalization run, grading-corrected (regrades.jsonl applied)
and COST-RECOVERED exactly as the experiment repo's dashboard does
(harness/autoform_dashboard.rows_of / metrics). Per run: solved/n, per-task
solved counts, recovered total cost, $/solve (all attempts' cost, failures
included, killed attempts' costs recovered from per-message token usage),
latency over solved attempts, mean wall over all attempts, kills (num_turns
is None, the dashboard definition), and over-wall attempts (wall_s >= 899.5,
the count that matters for the Mistral driver, which does not null
num_turns).

CAVEAT: the dashboard's recovery prices tokens at the claude-sonnet-5 rate
table, so recovered increments for killed OPUS attempts are priced at
sonnet rates (a lower bound for opus); Mistral and terra rows have no
missing costs and are unaffected. Also computes the all-time prodauto and
triadic solve census across every listed run.

Usage: python3 autoform_arms.py [EXPERIMENT_REPO_ROOT]
"""
import argparse
import json
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]

CURRENT = {
    "af3_base": ("sonnet", "control, draw 1"), "af3_base2": ("sonnet", "control, draw 2 (A103)"),
    "af3_evolve": ("sonnet", "evolve, shipped configuration"),
    "af3_evolve_r1": ("sonnet", "evolve + R1 hole warnings (reverted)"),
    "af3_evolve_r3": ("sonnet", "evolve + R3 open+finisher fusion (reverted)"),
    "af3_evolve_c3": ("sonnet", "evolve + C3 compact default (reverted)"),
    "af3_sota": ("sonnet", "sibling"),
    "op_base": ("opus", "control"), "op_evolve": ("opus", "evolve"), "op_sota": ("opus", "sibling"),
    "mst3_base": ("mistral-large", "control"), "mst3_evolve": ("mistral-large", "evolve"),
    "mst3_sota": ("mistral-large", "sibling, VOID (A112 driver artifact)"), "mst3_sota_v2": ("mistral-large", "sibling, remeasure (A112)"),
    "orp3_base": ("terra", "control"), "orp3_evolve": ("terra", "evolve"), "orp3_sota": ("terra", "sibling"),
    "af2_base": ("sonnet", "40-turn arena control (superseded)"), "af2_evolve": ("sonnet", "40-turn arena evolve (superseded)"),
    "af2_sota": ("sonnet", "40-turn arena sibling (superseded)"),
}


def build(exp_root):
    """Return exactly the dict this producer writes as autoform_arms.json."""
    sys.path.insert(0, str(exp_root / "harness"))
    import autoform_dashboard as ad  # noqa: E402

    af = exp_root / "logs" / "autoform"
    out = {"note": __doc__.strip(), "runs": {}, "all_time": {"prodauto": {}, "triadic": {}}}
    for d in sorted(af.iterdir()):
        if not d.is_dir() or not (d / "results.jsonl").exists():
            continue
        run = d.name
        if "smoke" in run or "probe" in run:
            continue
        rows = ad.rows_of(run)
        rows5 = [r for r in rows if ad._norm_task(r["task"]) in ad.TASK_IDS]
        m = ad.metrics(rows5) if rows5 else None
        per_task = {t: f"{sum(1 for r in rows if ad._norm_task(r['task']) == t and r['solved'])}/{sum(1 for r in rows if ad._norm_task(r['task']) == t)}"
                    for t in sorted({ad._norm_task(r["task"]) for r in rows})}
        rec = {"model_tier": CURRENT.get(run, ("", ""))[0], "role": CURRENT.get(run, ("", "not a current arm"))[1],
               "in_current_table": run in CURRENT,
               "n": len(rows), "solved": sum(1 for r in rows if r["solved"]), "per_task": per_task,
               "recovered_total_cost_usd": round(sum(r.get("total_cost_usd") or 0 for r in rows), 2),
               "cost_per_solve_recovered": round(m["cps"], 3) if m and m["cps"] is not None else None,
               "latency_over_solved_s": round(m["lat"], 1) if m and m["lat"] is not None else None,
               "wall_all_attempts_s": round(m["wall"], 1) if m else None,
               "kills_num_turns_none": sum(1 for r in rows if r.get("num_turns") is None),
               "over_wall_899_5s": sum(1 for r in rows if (r.get("wall_s") or 0) >= 899.5),
               "regrades_applied": sum(1 for _ in open(d / "regrades.jsonl")) if (d / "regrades.jsonl").exists() else 0}
        try:
            meta = json.load(open(d / "run_meta.json"))
            rec["model"] = meta.get("model") or meta.get("config", {}).get("model")
            rec["driver"] = meta.get("driver", "claude-cli")
            rec["reasoning"] = meta.get("reasoning")
        except Exception:
            pass
        out["runs"][run] = rec
        for t in ("prodauto", "triadic"):
            if t in per_task:
                out["all_time"][t][run] = per_task[t]
    for t in ("prodauto", "triadic"):
        s = sum(int(v.split("/")[0]) for v in out["all_time"][t].values())
        n = sum(int(v.split("/")[1]) for v in out["all_time"][t].values())
        out["all_time"][t]["TOTAL"] = f"{s}/{n}"
    return out


def main():
    ap = argparse.ArgumentParser(description="Autoformalization arms archive.")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                     help="experiment repo root (default: this repository)")
    ap.add_argument("--out-dir", type=Path, default=None,
                     help="directory to write autoform_arms.json into "
                          "(default: <exp_root>/docs/results_tables)")
    args = ap.parse_args()
    out = build(args.exp_root)
    for run, rec in out["runs"].items():
        print(f"{run:18s} {rec['solved']:2d}/{rec['n']:<3d} $/solve {rec['cost_per_solve_recovered']}  "
              f"lat {rec['latency_over_solved_s']}  kills {rec['kills_num_turns_none']}  {rec['per_task']}")
    for t in ("prodauto", "triadic"):
        print(t, "all-time", out["all_time"][t]["TOTAL"])
    out_dir = args.out_dir or (args.exp_root / "docs" / "results_tables")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "autoform_arms.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {out_dir / 'autoform_arms.json'}")


if __name__ == "__main__":
    main()
