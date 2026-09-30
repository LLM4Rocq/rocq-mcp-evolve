#!/usr/bin/env python3
# Origin: a tables directory maintained beside the results summary's former
# home (harness/results_tables/, not the top-level tables/ copy this
# particular script lived in). Moved into this repository's
# harness/results_tables/ on 2026-09-08.
# Exposes build(exp_root) -> dict (the results_all_gen.py entry point);
# main() still writes audit_verify_rows.json for ad-hoc use (default:
# docs/results_tables/, via --out-dir), but nothing under docs/results_tables/
# is tracked any more.
"""Post hoc sibling-verified column for the miniF2F test table (RESULTS_ALL §3).

    python3 audit_verify_rows.py <experiment_repo_root>

Source: the A121 audit (experiment repo, logs/audit_verify/summary.json and
per-run JSONL): every gate-rejected artifact of every held-out arm was
re-verified with the sibling server's rocq_verify tool, and every gate-solved
one re-checked. Categories (A121): gate_stricter = the gate rejected a proof
the sibling accepts (helper lemma outside the locked prefix, preamble edit,
Require inside the proof, Unset printing, convertible restatement);
sibling_limitation = gate-solved proofs the sibling cannot check (evar capture);
artifact_drift = file rewritten after the attempt deadline (never credited);
unsound_solve = gate-solved, sibling-rejected for a real reason (zero found).

Registered pass@1 = rep-0 solves / problems per bucket, exactly as final_tables.py.
Semantic pass@1 (post hoc) = registered + gate_stricter rows at rep 0 - unsound
rows at rep 0 (the rule of harness/audit_verify_summary.py, A121 B), per bucket.

The bucket for each problem is taken from results.jsonl's own difficulty
field, cross-checked for agreement across every one of the fourteen arms
below (no archived bucket_manifest file is read; the 244-problem test split
is fixed and every arm's own rows are the ground truth for it). The
registered numbers are never replaced; this column is reported beside them.
"""
import argparse
import json
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]

# A147: the audit column is a rep-0 audit of the REGISTERED runs; the opus
# control row is therefore the registered July-era rep 0 (the A142 rerun
# and the haiku rep-1 rows postdate the A121 audit and are not covered).
ARMS = [
    ("haiku", "control", "FINAL_pf_baseline_haiku"),
    ("haiku", "sibling", "FINAL_pf_rocqmcp_haiku"),
    ("haiku", "evolve, guided phase-1 prompt (A100; the prompt-free A150 arm postdates the audit)", "FINAL_frozen_wallonly"),
    ("sonnet", "control", "FINAL_pf_baseline_sonnet"),
    ("sonnet", "sibling", "FINAL_pf_rocqmcp_sonnet"),
    ("sonnet", "evolve (A108)", "FINAL_pf_session2_sonnet"),
    ("opus (registered rep 0)", "control (July era, A120/A143)", "FINAL_pf_baseline_opus"),
    ("opus (registered rep 0)", "sibling", "FINAL_pf_rocqmcp_opus"),
    ("opus (registered rep 0)", "evolve (A117)", "FINAL_pf_session2_opus"),
    ("mistral", "control", "mstf_base_test"),
    ("mistral", "sibling", "mstf_sota_test"),
    ("mistral", "evolve (A113)", "mstf_evolve_test"),
    ("terra", "control", "orp_base_test"),
    ("terra", "sibling", "orp_sib_test"),
    ("terra", "evolve (A115b)", "orp_evolve_test"),
    ("none", "finisher-only (A114)", "finisher_only_test"),
]
BUCKETS = ["easy", "medium", "hard"]


def build(exp_root):
    """Return exactly the dict this producer writes as audit_verify_rows.json."""
    summary = json.load(open(exp_root / "logs/audit_verify/summary.json"))
    credit = {}   # run -> set of problem_id credited post hoc (rep 0, gate_stricter)
    debit = {}    # run -> set of problem_id debited (rep 0, unsound_solve)
    for row in summary["rows"]["rejected_accept"]:
        if int(row["rep"]) == 0 and row["category"] == "gate_stricter":
            credit.setdefault(row["run"], set()).add(row["problem_id"])
    for row in summary["rows"]["solved_rejected"]:
        if int(row["rep"]) == 0 and row["category"] == "unsound_solve":
            debit.setdefault(row["run"], set()).add(row["problem_id"])
    limitation = {row["run"]: 0 for row in summary["rows"]["solved_rejected"]}
    for row in summary["rows"]["solved_rejected"]:
        if int(row["rep"]) == 0 and row["category"] == "sibling_limitation":
            limitation[row["run"]] += 1

    manifest = {}  # problem_id -> bucket, derived from the arms themselves
    out = {"note": __doc__, "arms": []}
    for model, arm, run in ARMS:
        rows = [json.loads(l) for l in open(exp_root / "logs/runs" / run / "results.jsonl") if l.strip()]
        r0 = {r["problem_id"]: r for r in rows if r.get("rep", 0) == 0}
        assert len(r0) == 244, (run, len(r0))
        for pid, r in r0.items():
            b = manifest.setdefault(pid, r["difficulty"])
            assert b == r["difficulty"], (run, pid)
        reg, sem, n = {}, {}, {}
        for b in BUCKETS:
            pids = [p for p in r0 if r0[p]["difficulty"] == b]
            n[b] = len(pids)
            reg[b] = sum(1 for p in pids if r0[p]["solved"])
            sem[b] = reg[b] + sum(1 for p in pids if p in credit.get(run, ()) and not r0[p]["solved"]) \
                - sum(1 for p in pids if p in debit.get(run, ()) and r0[p]["solved"])
        N = sum(n.values())
        rec = {"model": model, "arm": arm, "run": run, "n_problems": n,
               "registered_solves": reg, "semantic_solves": sem,
               "registered_pass1": {b: round(reg[b] / n[b], 3) for b in BUCKETS},
               "semantic_pass1": {b: round(sem[b] / n[b], 3) for b in BUCKETS},
               "registered_pooled": round(sum(reg.values()) / N, 3),
               "semantic_pooled": round(sum(sem.values()) / N, 3),
               "credited_rep0": sum(sem.values()) - sum(reg.values()),
               "sibling_limitation_rep0": limitation.get(run, 0)}
        rec["unsound_rep0"] = len(debit.get(run, set()))
        cell = lambda k, m: f"{k / m:.2f}"[1:] if k < m else "1.00"
        f3 = lambda d: "/".join(cell(d[b], n[b]) for b in BUCKETS)
        rec["registered_cells"] = f3(reg) + " | " + cell(sum(reg.values()), N)
        rec["semantic_cells"] = f3(sem) + " | " + cell(sum(sem.values()), N)
        out["arms"].append(rec)

    out["totals"] = summary["total"]
    return out


def main():
    ap = argparse.ArgumentParser(description="Post hoc sibling-verified column for the miniF2F test table.")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                     help="experiment repo root (default: this repository)")
    ap.add_argument("--out-dir", type=Path, default=None,
                     help="directory to write audit_verify_rows.json into "
                          "(default: <exp_root>/docs/results_tables)")
    args = ap.parse_args()
    out = build(args.exp_root)
    print("| model | arm | registered pass@1 e/m/h | pooled | sibling-verified e/m/h | pooled | rep-0 credited / debited |")
    print("|---|---|---|---|---|---|---|")
    for rec in out["arms"]:
        print(f"| {rec['model']} | {rec['arm']} | {rec['registered_cells']} | "
              f"{rec['semantic_cells']} | +{rec['credited_rep0']} / -{rec['unsound_rep0']} |")
    print("\ntotals:", json.dumps(out["totals"]))
    out_dir = args.out_dir or (args.exp_root / "docs" / "results_tables")
    out_dir.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(out_dir / "audit_verify_rows.json", "w"), indent=1)
    print(f"wrote {out_dir / 'audit_verify_rows.json'}")


if __name__ == "__main__":
    main()
