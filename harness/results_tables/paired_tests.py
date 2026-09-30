#!/usr/bin/env python3
# Origin: a tables directory maintained beside the results summary's former
# home. Moved into this repository's harness/results_tables/ on 2026-09-08.
# Writes nothing (prints computed statistics to stdout); reads
# audit_subset.json from docs/results_tables/ if present.
"""Paired tests quoted in the write-up, computed from the archived
per-attempt records (pure stdlib). POST-HOC STATUS: these analyses were
computed after the registered per-arm looks; the registered quantities
are the per-arm estimates and Wilson CIs. The rep-0 pairing convention
was fixed in the pre-look reporting registration.

Usage (run from the experiment repository root, which holds logs/):
    python3 paired_tests.py <experiment_repo_root>
Outputs every number quoted in the write-up's Section 5.2, Section 6.3,
and Appendix A (paired counts, McNemar exact-binomial p-values, the
task-level sign-flip test, and the audited-subset restriction)."""
import argparse
import itertools
import json
from math import comb
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]

ap = argparse.ArgumentParser(description="Paired tests over the archived per-attempt records.")
ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                 help="experiment repo root (default: this repository)")
ap.add_argument("--out-dir", type=Path, default=None,
                 help="accepted for interface uniformity with the other "
                      "producer scripts; unused, since this script writes no "
                      "file of its own. audit_subset.json is always read from "
                      "<exp_root>/docs/results_tables")
args = ap.parse_args()

ROOT = args.exp_root
ARCHIVE_DIR = ROOT / "docs" / "results_tables"    # archived table inputs always live here
LOGS = ROOT / "logs"


def rows(rel):
    return [json.loads(l) for l in open(LOGS / rel)]


def rep0(run):
    return {r["problem_id"]: r for r in rows(f"runs/{run}/results.jsonl")
            if r.get("rep", 0) == 0}


def mcnemar(a, b, pids):
    n10 = sum(1 for p in pids if a[p]["solved"] and not b[p]["solved"])
    n01 = sum(1 for p in pids if b[p]["solved"] and not a[p]["solved"])
    n = n10 + n01
    p = min(1.0, sum(comb(n, k) for k in range(0, min(n10, n01) + 1))
            / 2 ** n * 2) if n else 1.0
    return n10, n01, p


def main():
    ev = rep0("FINAL_pf_session2_sonnet")  # A108 supersession: corrected arm is the reported evolve row
    ct = rep0("FINAL_pf_baseline_sonnet")
    sb = rep0("FINAL_pf_rocqmcp_sonnet")
    buckets = {"easy", "medium", "hard"}
    print("== held-out paired McNemar (rep-0 problem pairs) ==")
    held_ps = []
    for name, other in (("evolve vs control", ct), ("evolve vs sibling", sb)):
        for b in sorted(buckets) + ["ALL"]:
            pids = [p for p in ev if b == "ALL" or ev[p]["difficulty"] == b]
            n10, n01, p = mcnemar(ev, other, pids)
            print(f"  {name:18s} {b:6s} {n10}:{n01}  p={p:.4f}")
            held_ps.append((f"{name} {b}", p))

    # Holm step-down over the eight held-out tests (post hoc, like the
    # tests themselves): family = {control, sibling} x {e, m, h, ALL}
    print("== Holm adjustment over the eight held-out paired tests ==")
    m = len(held_ps)
    running = 0.0
    for i, (name, pv) in enumerate(sorted(held_ps, key=lambda kv: kv[1])):
        running = min(1.0, max(running, (m - i) * pv))
        print(f"  {name:28s} raw p={pv:.4f}  holm p={running:.4f}")

    # Paired efficiency on jointly-solved rep-0 problems (post hoc; the
    # pooled accuracy McNemar above is registered for the A108 arm)
    for lbl, other in (("SIBLING", sb), ("CONTROL", ct)):
        joint = [q for q in ev if q in other and ev[q]["solved"] and other[q]["solved"]]
        ew = sum(ev[q]["wall_s"] for q in joint) / len(joint)
        cw = sum(other[q]["wall_s"] for q in joint) / len(joint)
        ec = sum(ev[q].get("total_cost_usd") or 0 for q in joint) / len(joint)
        cc = sum(other[q].get("total_cost_usd") or 0 for q in joint) / len(joint)
        print(f"== paired efficiency vs {lbl}, jointly-solved rep-0 (n={len(joint)}) ==")
        print(f"  wall  evolve {ew:.1f}s  other {cw:.1f}s  ({100*(1-ew/cw):.0f}% faster; other {100*(cw/ew-1):.0f}% longer)")
        print(f"  cost  evolve ${ec:.3f}  other ${cc:.3f}  ({100*(1-ec/cc):.0f}% cheaper; other {100*(cc/ec-1):.0f}% more)")
    joint = [q for q in ev if q in ct and ev[q]["solved"] and ct[q]["solved"]]
    ew = sum(ev[q]["wall_s"] for q in joint) / len(joint)
    cw = sum(ct[q]["wall_s"] for q in joint) / len(joint)
    ec = sum(ev[q].get("total_cost_usd") or 0 for q in joint) / len(joint)
    cc = sum(ct[q].get("total_cost_usd") or 0 for q in joint) / len(joint)
    print(f"== paired efficiency vs CONTROL, jointly-solved rep-0 (n={len(joint)}) ==")
    print(f"  wall  evolve {ew:.1f}s  control {cw:.1f}s  ({100*(1-ew/cw):.0f}% faster)")
    print(f"  cost  evolve ${ec:.3f}  control ${cc:.3f}  ({100*(1-ec/cc):.0f}% cheaper)")

    print("== autoformalization task-level sign-flip (5 tasks) ==")
    def by_task(run):
        rs = rows(f"autoform/{run}/results.jsonl")
        over = {(r["task"], r["rep"]): r
                for r in rows(f"autoform/{run}/regrades.jsonl")} \
            if (LOGS / f"autoform/{run}/regrades.jsonl").exists() else {}
        rs = [over.get((r["task"], r["rep"]), r) for r in rs]
        out = {}
        for r in rs:
            out.setdefault(r["task"].split("/")[-1].split("_")[0], []).append(r)
        return out
    base = by_task("af3_base")
    fam = ["af3_evolve", "af3_evolve_r1", "af3_evolve_r3", "af3_evolve_c3"]
    diffs = []
    for t in sorted(base):
        b = base[t]
        f = [r for run in fam for r in by_task(run).get(t, [])]
        diffs.append(sum(r["solved"] for r in f) / len(f)
                     - sum(r["solved"] for r in b) / len(b))
    obs = sum(diffs) / len(diffs)
    hits = sum(1 for signs in itertools.product((1, -1), repeat=len(diffs))
               if abs(sum(s * d for s, d in zip(signs, diffs)) / len(diffs))
               >= abs(obs) - 1e-12)
    print(f"  mean task diff {obs:+.3f}; exact two-sided p = {hits}/32 = {hits/32:.3f}")

    audit_path = ARCHIVE_DIR / "audit_subset.json"
    if audit_path.exists():
        print("== audited-subset restriction: see audit_subset.json; "
              "recompute by intersecting the audit list with the test split ==")


if __name__ == "__main__":
    main()
