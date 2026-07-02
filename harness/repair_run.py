#!/usr/bin/env python3
"""Remove sleep-contaminated attempt records from a run so the (resumable)
runner redoes exactly those slots.

    python3 harness/repair_run.py <run_id>          # then re-invoke run_eval
                                                    # with the original args

An attempt is contaminated iff machine_slept=True (the wall-clock watchdog
killed it after a macOS sleep gap, so both its outcome and its timings are
invalid). The dropped records are preserved in results.quarantine.jsonl for
audit.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common


def main():
    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        run_dir = common.LOGS / "runs" / sys.argv[1]
    res = run_dir / "results.jsonl"
    rows = common.read_jsonl(res)
    keep = [r for r in rows if not r.get("machine_slept")]
    drop = [r for r in rows if r.get("machine_slept")]
    if not drop:
        print("no contaminated records")
        return
    with open(run_dir / "results.quarantine.jsonl", "a") as f:
        for r in drop:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    res.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in keep))
    # clear the attempt dirs so reruns start clean
    for r in drop:
        aid = f"{r['problem_id']}__rep{r['rep']}"
        adir = run_dir / "attempts" / aid
        if adir.exists():
            import shutil

            shutil.rmtree(adir)
    print(f"quarantined {len(drop)} records ({[r['problem_id'] for r in drop[:5]]}...); "
          f"re-run run_eval with the original arguments to redo them")


if __name__ == "__main__":
    main()
