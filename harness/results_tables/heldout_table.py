#!/usr/bin/env python3
# New module (2026-09-08): wraps harness/final_tables.py so the held-out
# miniF2F table (RESULTS_ALL §3) is computed in memory at run time instead
# of being read from the archived logs/final_heldout_table.json snapshot
# under docs/results_tables/ (gone).
"""build(exp_root) -> the `art` dict harness/final_tables.py's main() writes
to logs/final_heldout_table.json (arms x buckets: pass1, pass2, cost_per_solve,
latency_solved_s, kill_rate, ...), computed via final_tables.build_table() —
same integrity gates, same logic, nothing changed. Raises
final_tables.GateFailure if a gate refuses and force=False (final_tables.py's
own functions read this repository's own logs via harness/common.py, so
exp_root is accepted here only for interface uniformity with the other
harness/results_tables/*.py producers).

Usage: python3 heldout_table.py [--force]
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import final_tables as ft  # noqa: E402

GateFailure = ft.GateFailure
rows_for = ft.rows_for          # arm key -> rows (composite arms assembled, A147)
COMPOSITE = ft.COMPOSITE


def build(exp_root=None, force=False):
    """art dict of final_tables.build_table(); when force=True and a gate
    failed, the failures are carried in art["gate_failures"] so the caller
    can flag its output (results_all_gen.py's --force preview banner)."""
    art, failures = ft.build_table(force=force)
    art["gate_failures"] = failures
    return art


def main():
    ap = argparse.ArgumentParser(description="Held-out miniF2F table (harness/final_tables.py), in memory.")
    ap.add_argument("exp_root", nargs="?", type=Path, default=HERE.resolve().parents[2],
                     help="accepted for interface uniformity; unused (see docstring)")
    ap.add_argument("--force", action="store_true", help="preview even if an integrity gate fails")
    args = ap.parse_args()
    try:
        art = build(args.exp_root, force=args.force)
    except GateFailure as e:
        print("REFUSING to emit table; integrity gates failed:")
        for f in e.failures:
            print("  -", f)
        sys.exit(1)
    print(json.dumps(art, indent=1))


if __name__ == "__main__":
    main()
