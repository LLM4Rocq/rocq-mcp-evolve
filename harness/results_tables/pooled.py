#!/usr/bin/env python3
# Origin: a tables directory maintained beside the results summary's former
# home. Moved into this repository's harness/results_tables/ on 2026-09-08.
# Writes nothing (prints pooled pass@1/pass@2 to stdout); computes the
# held-out table at run time via heldout_table.build() (no archived JSON
# read any more: docs/results_tables/ is gone).
"""Pooled (whole-split) pass@1/pass@2 per arm, computed at run time by
heldout_table.build() (which in turn calls harness/final_tables.py's own
functions) — the aggregate figure conventionally quoted for miniF2F.
Never hand-compute:  python3 pooled.py"""
import argparse
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

ap = argparse.ArgumentParser(description="Pooled pass@1/pass@2 per arm from the held-out table.")
ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                 help="experiment repo root (default: this repository)")
ap.add_argument("--out-dir", type=Path, default=None,
                 help="accepted for interface uniformity with the other "
                      "producer scripts; unused, since this script writes no "
                      "file of its own and reads no archived table.")
args = ap.parse_args()

sys.path.insert(0, str(HERE))
import heldout_table  # noqa: E402

art = heldout_table.build(args.exp_root)
for a in art["arms"]:
    b = a["buckets"]
    n = sum(b[x]["n_problems"] for x in ("easy", "medium", "hard"))
    k1 = sum(round(b[x]["pass1"] * b[x]["n_problems"]) for x in ("easy", "medium", "hard"))
    k2 = sum(round(b[x]["pass2"] * b[x]["n_problems"]) for x in ("easy", "medium", "hard") if b[x]["pass2"] is not None)
    print(f"{a['run']:28s} pass@1 {k1}/{n} = {k1/n:.3f}   pass@2 {k2}/{n} = {k2/n:.3f}")
