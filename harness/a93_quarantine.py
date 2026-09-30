#!/usr/bin/env python3
"""A93 repair: concurrent-writer contamination in FINAL_pf_baseline_sonnet.

2026-07-14: the parallel-4 pf chain kill missed the python child (the
wrapper sh died, the runner survived). It ran concurrently with the
relaunched parallel-8 chain for ~2h until a battery power loss killed
both. 68 slots were sampled by BOTH runners into the SAME attempt dir
(shared work/candidate.v -> final grading can read the other attempt's
proof), so BOTH rows of each pair are untrustworthy. Outcome-blind
repair per A83: quarantine all rows of double-sampled slots, park the
attempt dirs, redo each slot once. Attempt dirs with no results row
(in-flight at power loss) are parked too (stale candidate.v hazard).

Run once. Idempotent second runs find nothing to do.
"""
import json
import shutil
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import common

RUN = "FINAL_pf_baseline_sonnet"
REASON = "A93_concurrent_writer_contamination"

rd = common.LOGS / "runs" / RUN
rows = common.read_jsonl(rd / "results.jsonl")
slots = {}
for r in rows:
    slots.setdefault((r["problem_id"], r.get("rep", 0)), []).append(r)
dup_slots = {k for k, v in slots.items() if len(v) > 1}
print(f"{RUN}: {len(rows)} rows, {len(slots)} unique slots, "
      f"{len(dup_slots)} double-sampled")

post = [r for r in rows[180:]]
if post:
    ts = [r["ts"] for r in post]
    print(f"overlap window rows: ts {time.strftime('%F %T', time.localtime(min(ts)))}"
          f" .. {time.strftime('%F %T', time.localtime(max(ts)))}")

kept, quarantined = [], []
for r in rows:
    k = (r["problem_id"], r.get("rep", 0))
    if k in dup_slots:
        quarantined.append({**r, "quarantine_reason": REASON})
    else:
        kept.append(r)

park_root = rd / "attempts_contaminated"
parked_dup = parked_inflight = 0
if quarantined:
    with open(rd / "results.quarantine.jsonl", "a") as qf:
        for r in quarantined:
            qf.write(json.dumps(r) + "\n")
    (rd / "results.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in kept))
    park_root.mkdir(exist_ok=True)
    stamp = int(time.time())
    for pid, rep in sorted(dup_slots):
        adir = rd / "attempts" / f"{pid}__rep{rep}"
        if adir.exists():
            shutil.move(str(adir), str(park_root / f"{pid}__rep{rep}.{stamp}"))
            parked_dup += 1

# in-flight at power loss: attempt dir exists, no results row
have_row = {(r["problem_id"], r.get("rep", 0)) for r in kept}
stamp = int(time.time())
for adir in sorted((rd / "attempts").glob("*__rep*")):
    name = adir.name
    pid, rep = name.rsplit("__rep", 1)
    if (pid, int(rep)) not in have_row:
        park_root.mkdir(exist_ok=True)
        shutil.move(str(adir), str(park_root / f"{name}.inflight.{stamp}"))
        parked_inflight += 1

print(f"kept {len(kept)} rows; quarantined {len(quarantined)} rows; "
      f"parked {parked_dup} contaminated + {parked_inflight} in-flight attempt dirs")
print(f"remaining slots for {RUN}: {488 - len(kept)}")
