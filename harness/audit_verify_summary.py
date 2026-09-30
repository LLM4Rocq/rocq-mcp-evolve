#!/usr/bin/env python3
"""Aggregate audit_verify.py output files into per-run / per-bucket counts.

    python3 harness/audit_verify_summary.py [DIR=logs/audit_verify] [--json OUT]
        [--triage TRIAGE.json]

Buckets (mutually exclusive, in this priority order):
  artifact_drift   file rewritten after the attempt ended, or our gate's
                   verdict TODAY on the file differs from the record: the
                   graded artifact is not recoverable -> excluded from
                   agreement statistics, disclosed by count
  agree            sibling verdict == gate record
  solved_rejected  gate solved, sibling rejects   (A: limitation or unsound)
  rejected_accept  gate rejected (file present), sibling accepts (B: gate
                   stricter than semantic match)
Counts are recomputed from the JSONL files; nothing is taken from agent
reports.  --triage merges a JSON mapping "run/problem_id/rep" -> category
(from the triage/refute phase) to split A into sibling_limitation /
unsound_solve and to list every unsound_solve row.
"""
import argparse
import collections
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402


def bucket(r):
    if r.get("artifact_post_deadline") or (
            r.get("artifact_reproduces_record") is False):
        return "artifact_drift"
    if r["agree"]:
        return "agree"
    return "solved_rejected" if r["gate_solved"] else "rejected_accept"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", nargs="?", default="logs/audit_verify")
    ap.add_argument("--json", default="")
    ap.add_argument("--triage", default="")
    a = ap.parse_args()
    triage = json.load(open(a.triage)) if a.triage else {}
    per_run = {}
    rows_by_bucket = collections.defaultdict(list)
    reasons = collections.Counter()
    for p in sorted(glob.glob(os.path.join(a.dir, "*.jsonl"))):
        run = os.path.basename(p)[:-6]
        c = collections.Counter()
        seen = set()
        for l in open(p):
            r = json.loads(l)
            key = (r["problem_id"], r["rep"])
            if key in seen:
                c["duplicate_rows"] += 1
                continue
            seen.add(key)
            b = bucket(r)
            c[b] += 1
            c["audited"] += 1
            if b != "agree":
                tag = f"{run}/{r['problem_id']}/{r['rep']}"
                cat = triage.get(tag)
                rows_by_bucket[b].append({
                    "run": run, "problem_id": r["problem_id"], "rep": r["rep"],
                    "gate": "solved" if r["gate_solved"] else r["gate_reason"],
                    "gate_today": None if r.get("gate_now") is None else (
                        "solved" if r["gate_now"]["solved"] else r["gate_now"]["reason"]),
                    "sibling": "accept" if r["verify"].get("success") else r["verify"].get("reason"),
                    "method": r["verify"].get("verification_method"),
                    "late_s": r.get("artifact_late_s"), "category": cat})
                if cat:
                    c[f"cat:{cat}"] += 1
                if b == "solved_rejected":
                    reasons[(run, r["verify"].get("reason"))] += 1
        per_run[run] = dict(c)
    tot = collections.Counter()
    for c in per_run.values():
        tot.update(c)
    print(f"{'run':36s} {'audited':>7s} {'agree':>6s} {'solv>rej':>8s} {'rej>acc':>7s} {'drift':>6s}  triage")
    for run, c in per_run.items():
        cats = {k[4:]: v for k, v in c.items() if k.startswith("cat:")}
        print(f"{run:36s} {c.get('audited',0):7d} {c.get('agree',0):6d} {c.get('solved_rejected',0):8d} "
              f"{c.get('rejected_accept',0):7d} {c.get('artifact_drift',0):6d}  {cats if cats else ''}")
    print(f"{'TOTAL':36s} {tot.get('audited',0):7d} {tot.get('agree',0):6d} {tot.get('solved_rejected',0):8d} "
          f"{tot.get('rejected_accept',0):7d} {tot.get('artifact_drift',0):6d}")
    if reasons:
        print("\nsolved rows the sibling rejects, by its reason:")
        for (run, reason), n in sorted(reasons.items()):
            print(f"  {run:36s} {str(reason):20s} {n}")
    unsound = [x for x in rows_by_bucket["solved_rejected"] if x["category"] == "unsound_solve"]
    if unsound:
        print("\nUNSOUND_SOLVE rows (each must be reproduced by hand before being reported):")
        for x in unsound:
            print("  ", x)
    # Post hoc semantic-gate column (A121 B): rep-0 pass@1 as registered,
    # plus the rep-0 rows the gate rejected on file content but the sibling
    # accepts as proofs of the original statement.  Registered cells are
    # never replaced; this column sits beside them, labelled post hoc.
    sem = {}
    for run in per_run:
        rp = common.LOGS / "runs" / run / "results.jsonl"
        if not rp.exists():
            continue
        rec = [json.loads(l) for l in open(rp)]
        r0 = [r for r in rec if r.get("rep", 0) == 0]
        if not r0:
            continue
        k = sum(1 for r in r0 if r["solved"])
        acc = {(x["problem_id"]) for x in rows_by_bucket["rejected_accept"]
               if x["run"] == run and x["rep"] == 0}
        rej = {(x["problem_id"]) for x in rows_by_bucket["solved_rejected"]
               if x["run"] == run and x["rep"] == 0 and x["category"] == "unsound_solve"}
        sem[run] = {"n": len(r0), "registered_pass1": round(k / len(r0), 3),
                    "gate_stricter_rep0": len(acc), "unsound_rep0": len(rej),
                    "semantic_pass1": round((k + len(acc) - len(rej)) / len(r0), 3)}
    if sem:
        print(f"\n{'run (rep 0)':36s} {'n':>4s} {'registered':>10s} {'+sibling-accepted':>17s} {'-unsound':>8s} {'semantic (post hoc)':>19s}")
        for run, s in sem.items():
            print(f"{run:36s} {s['n']:4d} {s['registered_pass1']:10.3f} {s['gate_stricter_rep0']:17d} "
                  f"{s['unsound_rep0']:8d} {s['semantic_pass1']:19.3f}")
    if a.json:
        json.dump({"per_run": per_run, "total": dict(tot),
                   "rows": {k: v for k, v in rows_by_bucket.items()}},
                  open(a.json, "w"), indent=1)
        print(f"\nwrote {a.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
