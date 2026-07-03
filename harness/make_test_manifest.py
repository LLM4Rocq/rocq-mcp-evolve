#!/usr/bin/env python3
"""Generate the held-out test manifest — ONLY runnable after the mechanical
unlock (FINAL_UNLOCK file + ROCQ_FINAL_EVAL=1); see configs/FROZEN.md.
All access goes through datasets.load_minif2f('test'), which enforces the
guard and logs the unlock event."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common
import datasets

recs = datasets.load_minif2f("test")  # raises unless unlocked
out = common.MANIFESTS / "minif2f_test.jsonl"
rows = []
for r in recs:
    rows.append({
        "problem_id": r["problem_id"],
        "source": "minif2f_test",
        "difficulty": r["source_tier"],
        "source_tier": r["source_tier"],
        "theorem_name": r["theorem_name"],
        "path": r["path"],
    })
out.write_text("".join(json.dumps(r) + "\n" for r in rows))
print(f"wrote {len(rows)} records to {out} (held-out; single final run only)")
