#!/usr/bin/env python3
# New module (2026-09-08): ported (pooled-family part only) from a sibling
# archive's tables/paired_archive.py, which computed the full paired_tests.json
# once quoted here (per-bucket splits, efficiency pairings, the clean-subset
# and expert-audited-subset restrictions -- the latter needs data outside
# this repository, so it is not ported). Only the pooled two-test-per-family
# exact McNemar (RESULTS_ALL §5) is reproduced.
"""build(exp_root) -> {"families": {"sonnet": {...}, "haiku": {...},
"opus": {...}, "mistral": {...}, "terra": {...}, "opus_rep0": {...}}}, each
family {"pooled": {"evolve_vs_control": {"n10", "n01", "p", "holm_p"},
"evolve_vs_sibling": {...}, "n_pairs": ...}}: exact two-sided binomial
McNemar on discordant rep-0 problem pairs, Holm step-down within the
two-test family {vs control, vs sibling}.

Families (rep-0 rows only): sonnet = FINAL_pf_session2_sonnet (evolve) vs
FINAL_pf_baseline_sonnet (control) / FINAL_pf_rocqmcp_sonnet (sibling);
haiku (A118 comparators, A150 prompt-free evolve) = FINAL_pf_session2_haiku vs
FINAL_pf_baseline_haiku / FINAL_pf_rocqmcp_haiku; opus (A147) = FINAL_pf_session2_opus vs the A142
control rerun FINAL_pf_baseline_opus_r245 / FINAL_pf_rocqmcp_opus; mistral
= mstf_evolve_test vs mstf_base_test / mstf_sota_test; terra =
orp_evolve_test vs orp_base_test / orp_sib_test; opus_rep0 =
FINAL_pf_session2_opus vs the REGISTERED July-era rep 0 of
FINAL_pf_baseline_opus / FINAL_pf_rocqmcp_opus (report-only, A117; the
control side belongs to the July serving regime, A120/A143).

Usage: python3 paired_tests_pooled.py [EXPERIMENT_REPO_ROOT]
"""
import argparse
import json
from math import comb
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]

FAMILIES = {
    "sonnet": ("FINAL_pf_session2_sonnet", "FINAL_pf_baseline_sonnet", "FINAL_pf_rocqmcp_sonnet"),
    "haiku": ("FINAL_pf_session2_haiku", "FINAL_pf_baseline_haiku", "FINAL_pf_rocqmcp_haiku"),
    "opus": ("FINAL_pf_session2_opus", "FINAL_pf_baseline_opus_r245", "FINAL_pf_rocqmcp_opus"),
    "mistral": ("mstf_evolve_test", "mstf_base_test", "mstf_sota_test"),
    "terra": ("orp_evolve_test", "orp_base_test", "orp_sib_test"),
    "opus_rep0": ("FINAL_pf_session2_opus", "FINAL_pf_baseline_opus", "FINAL_pf_rocqmcp_opus"),
}


def _rep0(exp_root, run):
    rows = [json.loads(l) for l in open(exp_root / "logs" / "runs" / run / "results.jsonl") if l.strip()]
    return {r["problem_id"]: r for r in rows if r.get("rep", 0) == 0}


def _mcnemar(a, b, pids):
    n10 = sum(1 for p in pids if a[p]["solved"] and not b[p]["solved"])
    n01 = sum(1 for p in pids if b[p]["solved"] and not a[p]["solved"])
    n = n10 + n01
    p = min(1.0, sum(comb(n, k) for k in range(0, min(n10, n01) + 1)) / 2 ** n * 2) if n else 1.0
    return {"n10": n10, "n01": n01, "p": p}


def _holm(named):
    m = len(named)
    out, running = {}, 0.0
    for i, (name, pv) in enumerate(sorted(named, key=lambda kv: kv[1])):
        running = min(1.0, max(running, (m - i) * pv))
        out[name] = running
    return out


def _pooled_family(ev, ct, sb):
    # problems present in all three arms' rep 0 (244 when every arm is
    # complete; fewer only in a forced preview of an unfinished run)
    pids = [p for p in ev if p in ct and p in sb]
    vc = _mcnemar(ev, ct, pids)
    vs = _mcnemar(ev, sb, pids)
    holm = _holm([("evolve_vs_control", vc["p"]), ("evolve_vs_sibling", vs["p"])])
    return {"evolve_vs_control": dict(vc, holm_p=holm["evolve_vs_control"]),
            "evolve_vs_sibling": dict(vs, holm_p=holm["evolve_vs_sibling"]),
            "n_pairs": len(pids),
            "holm": "Holm over the two-test family {vs control, vs sibling}"}


def build(exp_root):
    """Return {"families": {fam: {"pooled": {...}}}} -- the pooled McNemar
    entries RESULTS_ALL §5 consumes (families/paired_tests.json's shape,
    pooled-family part only)."""
    out = {"families": {}}
    for fam, (ev_run, ct_run, sb_run) in FAMILIES.items():
        ev, ct, sb = _rep0(exp_root, ev_run), _rep0(exp_root, ct_run), _rep0(exp_root, sb_run)
        out["families"][fam] = {"pooled": _pooled_family(ev, ct, sb)}
    return out


def main():
    ap = argparse.ArgumentParser(description="Pooled McNemar families (ported pooled-family part of paired_archive.py).")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                     help="experiment repo root (default: this repository)")
    ap.add_argument("--out-dir", type=Path, default=None,
                     help="accepted for interface uniformity with the other "
                          "producer scripts; unused, since this script writes no file of its own.")
    args = ap.parse_args()
    out = build(args.exp_root)
    for fam, rec in out["families"].items():
        pc, ps = rec["pooled"]["evolve_vs_control"], rec["pooled"]["evolve_vs_sibling"]
        print(f"{fam:10s} vs control {pc['n10']}:{pc['n01']} p={pc['p']:.2g}   "
              f"vs sibling {ps['n10']}:{ps['n01']} p={ps['p']:.2g}")


if __name__ == "__main__":
    main()
