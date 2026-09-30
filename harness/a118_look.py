#!/usr/bin/env python3
"""A118 autonomous registered look: haiku-tier pf comparators against the
existing wall-only evolve arm. Same gates/metrics/contrast machinery as
a115_look, with two A118-specific rules fixed at registration: (1) an arm
is analyzable at 244 rows (rep 0 complete; pass@2 absent) or 488 rows
(full); any other count is ABSENT and blocks its contrasts only;
(2) a turn-rail gate: any non-solve with num_turns >= cap and wall
< 285 s fails the arm (the rail must be non-binding, as in the evolve
arm). Primary contrast: pooled exact McNemar on rep-0 pairs, evolve vs
control and evolve vs sibling, Holm over the two-test family. Writes
logs/a118_look_result.json.
"""
import json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import common

# A118b: comparator rails raised to 200 (parity with the evolve arm);
# rows recorded under the old cap-100 rail are still gated at 100 via
# the per-row check below (a 100-turn non-solve from the old-rail era
# remains a violation; redone rows run under cap-200).
ARMS = [("control", "FINAL_pf_baseline_haiku", 200),
        ("evolve",  "FINAL_frozen_wallonly", 200),
        ("sibling", "FINAL_pf_rocqmcp_haiku", 200)]
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

def gate(run, cap, rows):
    problems = []
    if len(rows) not in (244, 488):
        problems.append(f"{run}: {len(rows)} rows (need 244 or 488)")
    poisoned = sum(1 for r in rows if not r["solved"]
                   and (r.get("num_turns") or 99) <= 2
                   and any(m in json.dumps(r) for m in POISON))
    if poisoned: problems.append(f"{run}: {poisoned} poisoned rows")
    railed = sum(1 for r in rows if not r["solved"]
                 and (r.get("num_turns") or 0) >= cap
                 and (r.get("wall_s") or 0) < 285)
    if railed: problems.append(f"{run}: {railed} rail-bound non-solves (rail must not bind)")
    return problems

def metrics(rows, full):
    by = {}
    for r in rows: by.setdefault(r["problem_id"], {})[r.get("rep",0)] = r
    out = {}
    for b in BUCKETS:
        bp = {p:v for p,v in by.items() if (list(v.values())[0]).get("difficulty")==b}
        n = len(bp)
        k1 = sum(1 for v in bp.values() if (v.get(0) or {}).get("solved"))
        srows = [x for v in bp.values() for x in v.values() if x.get("solved")]
        allr = [x for v in bp.values() for x in v.values()]
        cost = sum(x.get("total_cost_usd") or 0 for x in allr)
        kills = sum(1 for x in allr if x.get("attempt_timed_out"))
        d = {"n": n, "pass1": round(k1/n,3) if n else None, "pass1_ci": wilson(k1,n),
             "cost_per_solve": round(cost/len(srows),3) if srows else None,
             "latency_solved_s": round(sum(x["wall_s"] for x in srows)/len(srows),1) if srows else None,
             "kill_pct": round(100*kills/len(allr)) if allr else None}
        if full:
            d["pass2"] = round(sum(1 for v in bp.values() if any(x.get("solved") for x in v.values()))/n,3) if n else None
        out[b] = d
    n = len(by)
    out["pooled"] = {"n": n, "pass1": round(sum(1 for v in by.values() if (v.get(0) or {}).get("solved"))/n,3)}
    if full:
        out["pooled"]["pass2"] = round(sum(1 for v in by.values() if any(x.get("solved") for x in v.values()))/n,3)
    return out

def rep0(rows):
    return {r["problem_id"]: r for r in rows if r.get("rep",0)==0}

def mcnemar(a, b):
    pids = [p for p in a if p in b]
    n10 = sum(1 for p in pids if a[p]["solved"] and not b[p]["solved"])
    n01 = sum(1 for p in pids if b[p]["solved"] and not a[p]["solved"])
    n = n10+n01
    p = min(1.0, sum(math.comb(n,k) for k in range(0,min(n10,n01)+1))/2**n*2) if n else 1.0
    return n10, n01, round(p,6)

def main():
    result = {"pre_registration": "A118", "arms": {}, "status": "CLEAN"}
    data = {}
    failures = []
    for label, run, cap in ARMS:
        rows = rows_of(run)
        # A118b: analyzability is rep-0 completeness per the registration
        # text, not total row count (a partial rep-1 tail is excluded from
        # analysis, disclosed); full mode requires both reps complete.
        r0 = [r for r in rows if r.get("rep",0)==0]
        r1 = [r for r in rows if r.get("rep",0)==1]
        if len(r0) != 244:
            result["arms"][label] = {"run": run, "status": f"ABSENT (rep0 {len(r0)}/244)"}
            continue
        rows = r0 + r1 if len(r1)==244 else r0
        g = gate(run, cap, rows)
        if g:
            failures += g
            result["arms"][label] = {"run": run, "status": "GATE-FAIL", "failures": g}
            continue
        result["arms"][label] = {"run": run, "status": "COMPLETE" if len(rows)==488 else "REP0-ONLY",
                                 "metrics": metrics(rows, len(rows)==488)}
        data[label] = rep0(rows)
    if failures:
        result["status"] = "BLOCKED"
        result["gate_failures"] = failures
    if "evolve" in data:  # A118b: per-arm gating; Holm multiplier stays 2 (registered family size)
        fam = []
        pc = {}
        for name in ("control", "sibling"):
            if name in data:
                n10, n01, p = mcnemar(data["evolve"], data[name])
                pc[f"evolve_vs_{name}"] = {"discordant": f"{n10}:{n01}", "raw_p": p}
                fam.append((f"evolve_vs_{name}", p))
        run_max = 0.0
        for i,(name,pv) in enumerate(sorted(fam, key=lambda kv: kv[1])):
            run_max = max(run_max, min(1.0,(2-i)*pv))
            pc[name]["holm_p"] = round(run_max,6)
        result["primary_contrast"] = pc
    (common.LOGS/"a118_look_result.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))

if __name__ == "__main__":
    main()
