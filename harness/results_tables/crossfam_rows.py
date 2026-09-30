#!/usr/bin/env python3
# Origin: a tables directory maintained beside the results summary's former
# home. Moved into this repository's harness/results_tables/ on 2026-09-08.
# Exposes build(exp_root) -> dict (the results_all_gen.py entry point);
# main() still writes a113_rows.json for ad-hoc use (default:
# docs/results_tables/, via --out-dir), but nothing under docs/results_tables/
# is tracked any more.
"""A113 second-family held-out rows for tab:heldout and fig_crossfam.
Reads the three mstf_* runs, emits per-bucket pass@1/pass@2/$-per-solve/
wall/kill plus pooled.
    python3 crossfam_rows.py <experiment_repo_root>
"""
import argparse
import json
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]

ARMS = [("control", "mstf_base_test"), ("sibling", "mstf_sota_test"),
        ("evolve", "mstf_evolve_test")]
BK = ["easy", "medium", "hard"]


def build(exp_root):
    """Return exactly the dict this producer writes as a113_rows.json."""
    out = {}
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
            d[b] = {"n": n, "pass1": round(k1 / n, 3), "pass2": round(k2 / n, 3),
                    "cost_per_solve": round(cost / len(srows), 2) if srows else None,
                    "latency_solved_s": round(sum(x["wall_s"] for x in srows) / len(srows)) if srows else None,
                    "kill_pct": round(100 * kills / len(allr))}
        n = len(by)
        d["pooled"] = {"pass1": round(sum(1 for v in by.values() if (v.get(0) or {}).get("solved")) / n, 3),
                       "pass2": round(sum(1 for v in by.values() if any(x.get("solved") for x in v.values())) / n, 3)}
        out[label] = d
    return out


def main():
    ap = argparse.ArgumentParser(description="A113 second-family held-out rows.")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                     help="experiment repo root (default: this repository)")
    ap.add_argument("--out-dir", type=Path, default=None,
                     help="directory to write a113_rows.json into "
                          "(default: <exp_root>/docs/results_tables)")
    args = ap.parse_args()
    out = build(args.exp_root)
    for label, d in out.items():
        def t(k, f=".2f"):
            vals = [d[b][k] for b in BK]
            return " / ".join(("--" if v is None else (f"{v:{f}}" if f != "d" else str(v))) for v in vals)
        p1 = " / ".join(f"{d[b]['pass1']:.2f}".lstrip('0') or '.00' for b in BK)
        p2 = " / ".join(f"{d[b]['pass2']:.2f}".lstrip('0') or '.00' for b in BK)
        pl = f"{d['pooled']['pass1']:.2f}".lstrip('0') + "/" + f"{d['pooled']['pass2']:.2f}".lstrip('0')
        print(f"{label:8s} & {p1} & {p2} & {pl} & {t('cost_per_solve')} & {t('latency_solved_s','d')} & {t('kill_pct','d')}")
    out_dir = args.out_dir or (args.exp_root / "docs" / "results_tables")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "a113_rows.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {out_dir / 'a113_rows.json'}")


if __name__ == "__main__":
    main()
