#!/usr/bin/env python3
"""A117 autonomous look (report-only, per A104/A117/A119 registrations).
Opus prompt-free arms on the held-out split: per-arm metrics only, NO
registered contrast. Gates per arm: rep-0 complete at 244 rows, poison
sweep (non-solves with <=2 turns and rate-limit/API-error text). The
sibling arm is optional: absent or incomplete arms are reported as
ABSENT and excluded (A104 incomplete-arm rule).

A119 amendment, fixed BEFORE the rep-1 data exists: an arm is
analyzable at 244 rows (rep 0 complete; pass@2 absent) or 488 rows
(both reps; pass@2 reported), mirroring a118_look. A partial rep-1
tail is excluded from analysis and disclosed -- the arm then reports
exactly the rep-0 pass@1 it reports today. pass@1 stays the rep-0
convention in every case, so rep 1 cannot revise a reported number.

Writes logs/a117_look_result.json.

    python3 harness/a117_look.py
"""
import json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import common

ARMS = [("control", "FINAL_pf_baseline_opus"),
        ("evolve",  "FINAL_pf_session2_opus"),
        ("sibling", "FINAL_pf_rocqmcp_opus")]
BUCKETS = ["easy", "medium", "hard"]
POISON = ["session limit", "You've hit your", "api_error_status",
          "API Error", "usage limit"]

def rows_of(run):
    p = common.LOGS / "runs" / run / "results.jsonl"
    return [json.loads(l) for l in open(p)] if p.exists() else []

def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    p = k/n; d = 1+z*z/n
    c = (p+z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (round(max(0,c-h),3), round(min(1,c+h),3))

def metrics(rows, full):
    """A119: pass@1 is the rep-0 cell in both modes; pass@2 only when full.
    With rep 0 alone this reproduces the pre-amendment cells exactly."""
    by = {}
    for r in rows: by.setdefault(r["problem_id"], {})[r.get("rep",0)] = r
    out = {}
    for b in BUCKETS:
        bp = {p:v for p,v in by.items() if (list(v.values())[0]).get("difficulty")==b}
        n = len(bp)
        k1 = sum(1 for v in bp.values() if (v.get(0) or {}).get("solved"))
        allr = [x for v in bp.values() for x in v.values()]
        sr = [x for x in allr if x.get("solved")]
        cost = sum(x.get("total_cost_usd") or 0 for x in allr)
        kills = sum(1 for x in allr if x.get("attempt_timed_out"))
        d = {"n": n, "pass1": round(k1/n,3) if n else None,
             "pass1_ci": wilson(k1,n),
             "cost_per_solve": round(cost/len(sr),3) if sr else None,
             "latency_solved_s": round(sum(x["wall_s"] for x in sr)/len(sr),1) if sr else None,
             "kill_pct": round(100*kills/len(allr)) if allr else None}
        if full:
            d["pass2"] = round(sum(1 for v in bp.values() if any(x.get("solved") for x in v.values()))/n,3) if n else None
        out[b] = d
    n = len(by)
    out["pooled"] = {"n": n, "pass1": round(sum(1 for v in by.values() if (v.get(0) or {}).get("solved"))/n,3) if n else None}
    if full:
        out["pooled"]["pass2"] = round(sum(1 for v in by.values() if any(x.get("solved") for x in v.values()))/n,3) if n else None
    return out

def main():
    result = {"pre_registration": "A117 (A104 scope) + A119 rep-1", "arms": {}, "status": "CLEAN"}
    failures = []
    for label, run in ARMS:
        rows = rows_of(run)
        # A119: analyzability is rep-0 completeness; a partial rep-1 tail
        # is excluded from analysis (disclosed), not a gate failure.
        r0 = [r for r in rows if r.get("rep",0)==0]
        r1 = [r for r in rows if r.get("rep",0)==1]
        if len(r0) != 244:
            result["arms"][label] = {"run": run, "status": f"ABSENT (rep0 {len(r0)}/244; not reported)"}
            continue
        full = len(r1) == 244
        rows = r0 + r1 if full else r0
        poisoned = [r["problem_id"] for r in rows
                    if not r["solved"] and (r.get("num_turns") or 99) <= 2
                    and any(m in json.dumps(r) for m in POISON)]
        if poisoned:
            failures.append(f"{run}: {len(poisoned)} poisoned rows")
            result["arms"][label] = {"run": run, "status": f"POISONED ({len(poisoned)})", "poisoned": poisoned}
            continue
        status = "COMPLETE (2 reps)" if full else "REP0-ONLY"
        if r1 and not full:
            status += f" (rep-1 tail {len(r1)}/244 excluded)"
        result["arms"][label] = {"run": run, "status": status, "metrics": metrics(rows, full)}
    if failures:
        result["status"] = "BLOCKED"
        result["gate_failures"] = failures
    (common.LOGS/"a117_look_result.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))

if __name__ == "__main__":
    main()
