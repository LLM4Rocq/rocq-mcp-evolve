#!/usr/bin/env python3
# Origin: a tables directory maintained beside the results summary's former
# home. Moved into this repository's harness/results_tables/ on 2026-09-08.
# Exposes build(exp_root) -> dict (the results_all_gen.py entry point);
# main() still writes a115_rows.json for ad-hoc use (default:
# docs/results_tables/, via --out-dir), but nothing under docs/results_tables/
# is tracked any more.
"""A115b/A116 third-family (gpt-5.6-terra via OpenRouter) rows for
tab:heldout, fig_crossfam, the autoform replication sentence, and the
attribution-partition extension. Reads the three orp_*_test runs, the
three orp3_* autoform runs, and finisher_only_test.
    python3 a115_rows.py <experiment_repo_root>
"""
import argparse
import json
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]

ARMS = [("control", "orp_base_test"), ("sibling", "orp_sib_test"),
        ("evolve", "orp_evolve_test")]
BK = ["easy", "medium", "hard"]


def build(exp_root):
    """Return exactly the dict this producer writes as a115_rows.json."""
    out = {"matrix": {}, "autoform": {}, "attribution": {}}
    for label, run in ARMS:
        rows = [json.loads(l) for l in open(exp_root / "logs/runs" / run / "results.jsonl")]
        by = {}
        for r in rows:
            by.setdefault(r["problem_id"], {})[r.get("rep", 0)] = r
        d = {}
        for b in BK:
            bp = {p: v for p, v in by.items()
                  if (v.get(0) or v.get(1) or {}).get("difficulty") == b}
            n = len(bp)
            k1 = sum(1 for v in bp.values() if (v.get(0) or {}).get("solved"))
            k2 = sum(1 for v in bp.values() if any(x.get("solved") for x in v.values()))
            allr = [x for v in bp.values() for x in v.values()]
            srows = [x for x in allr if x.get("solved")]
            cost = sum(x.get("total_cost_usd") or 0 for x in allr)
            kills = sum(1 for x in allr if x.get("attempt_timed_out"))
            # 2-dp table cells are computed from the raw counts here, never by
            # re-rounding the 3-dp values (a 0.715 -> .71 double-rounding hazard)
            d[b] = {"n": n, "pass1": round(k1 / n, 3), "pass2": round(k2 / n, 3),
                    "pass1_cell": f"{k1/n:.2f}"[1:], "pass2_cell": f"{k2/n:.2f}"[1:],
                    "cost_per_solve": round(cost / len(srows), 3) if srows else None,
                    "latency_solved_s": round(sum(x["wall_s"] for x in srows) / len(srows)) if srows else None,
                    "kill_pct": round(100 * kills / len(allr))}
        n = len(by)
        d["pooled"] = {"pass1": round(sum(1 for v in by.values() if (v.get(0) or {}).get("solved")) / n, 3),
                       "pass2": round(sum(1 for v in by.values() if any(x.get("solved") for x in v.values())) / n, 3)}
        out["matrix"][label] = d

    for label, run in [("control", "orp3_base"), ("evolve", "orp3_evolve"),
                       ("sibling", "orp3_sota")]:
        rows = [json.loads(l) for l in open(exp_root / "logs/autoform" / run / "results.jsonl")]
        by = {}
        for r in rows:
            by.setdefault(r["task"].split("/")[-1].split("_")[0], []).append(r)
        out["autoform"][label] = {
            "total": sum(1 for r in rows if r["solved"]), "n": len(rows),
            "per_task": {t: sum(1 for r in v if r["solved"]) for t, v in sorted(by.items())}}

    F = {json.loads(l)["problem_id"]
         for l in open(exp_root / "logs/runs/finisher_only_test/results.jsonl")
         if json.loads(l)["solved"]}
    for label, run in ARMS:
        E = {json.loads(l)["problem_id"] for l in open(exp_root / "logs/runs" / run / "results.jsonl")
             if json.loads(l)["solved"] and json.loads(l)["rep"] == 0}
        out["attribution"][label] = {
            "E": len(E), "E_and_F": len(E & F), "model_required": len(E - F),
            "model_required_pct": round(100 * len(E - F) / len(E)), "F_minus_E": len(F - E)}
    return out


def main():
    ap = argparse.ArgumentParser(description="A115b/A116 third-family rows.")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                     help="experiment repo root (default: this repository)")
    ap.add_argument("--out-dir", type=Path, default=None,
                     help="directory to write a115_rows.json into "
                          "(default: <exp_root>/docs/results_tables)")
    args = ap.parse_args()
    out = build(args.exp_root)
    out_dir = args.out_dir or (args.exp_root / "docs" / "results_tables")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "a115_rows.json").write_text(json.dumps(out, indent=1))
    m = out["matrix"]
    for label in ("evolve", "sibling", "control"):
        d = m[label]
        p1 = " / ".join(f"{d[b]['pass1']:.3f}".lstrip("0") for b in BK)
        print(f"{label:8s} pass1 e/m/h {p1}  pooled {d['pooled']['pass1']:.3f} ({d['pooled']['pass2']:.3f})")
    print("autoform:", {k: f"{v['total']}/{v['n']}" for k, v in out["autoform"].items()})
    print("attribution:", out["attribution"])
    print(f"wrote {out_dir / 'a115_rows.json'}")


if __name__ == "__main__":
    main()
