#!/usr/bin/env python3
"""A113 autonomous registered look. Deterministic, direction-blind.
Runs with NO agent. Reads the three test-split arms, gate-checks them,
computes per-arm metrics and the pre-declared primary contrast (pooled
exact McNemar rep-0, evolve-vs-control and evolve-vs-sibling, Holm over
the two-test family). Writes logs/a113_look_result.{json,txt}. If any
surface gate fails it writes a BLOCKED result and computes NOTHING on
the contaminated data (A112 lesson).

    python3 harness/a113_look.py
"""
import json, math, glob, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import common

ARMS = [("control", "mstf_base_test", 1),
        ("evolve",  "mstf_evolve_test", 5),
        ("sibling", "mstf_sota_test", 12)]
BUCKETS = ["easy", "medium", "hard"]
POISON = ['"api_error_status": 429', "session limit", "You've hit your",
          '"api_error_status": 529']

def rows_of(run):
    p = common.LOGS / "runs" / run / "results.jsonl"
    return [json.loads(l) for l in open(p)] if p.exists() else []

def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    p = k/n; d = 1+z*z/n
    c = (p+z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (round(max(0,c-h),3), round(min(1,c+h),3))

def gate(run, min_tools):
    rd = common.LOGS / "runs" / run
    rows = rows_of(run)
    problems = []
    if len(rows) != 488:
        problems.append(f"{run}: {len(rows)}/488 rows")
    crippled = poisoned = 0
    for r in rows:
        tp = rd/"attempts"/f"{r['problem_id']}__rep{r.get('rep',0)}"/"transcript.jsonl"
        try:
            first = open(tp, errors="replace").readline()
            if len(json.loads(first).get("tools", [])) < min_tools:
                crippled += 1
            if any(m in open(tp, errors="replace").read() for m in POISON):
                poisoned += 1
        except Exception:
            crippled += 1
    if crippled: problems.append(f"{run}: {crippled} rows below tool-surface floor {min_tools}")
    if poisoned: problems.append(f"{run}: {poisoned} live-poisoned transcripts")
    return problems

def metrics(run):
    rows = rows_of(run)
    by = {}
    for r in rows: by.setdefault(r["problem_id"], {})[r.get("rep",0)] = r
    out = {}
    for b in BUCKETS:
        bp = {p:v for p,v in by.items() if (v.get(0) or v.get(1) or {}).get("difficulty")==b}
        n = len(bp)
        k1 = sum(1 for v in bp.values() if (v.get(0) or {}).get("solved"))
        k2 = sum(1 for v in bp.values() if any(x.get("solved") for x in v.values()))
        srows = [x for v in bp.values() for x in v.values() if x.get("solved")]
        allr = [x for v in bp.values() for x in v.values()]
        cost = sum(x.get("total_cost_usd") or 0 for x in allr)
        out[b] = {"n": n, "pass1": round(k1/n,3) if n else None,
                  "pass1_ci": wilson(k1,n),
                  "pass2": round(k2/n,3) if n else None,
                  "cost_per_solve": round(cost/len(srows),3) if srows else None,
                  "latency_solved_s": round(sum(x["wall_s"] for x in srows)/len(srows),1) if srows else None}
    n = len(by)
    k1 = sum(1 for v in by.values() if (v.get(0) or {}).get("solved"))
    k2 = sum(1 for v in by.values() if any(x.get("solved") for x in v.values()))
    out["pooled"] = {"n": n, "pass1": round(k1/n,3), "pass2": round(k2/n,3)}
    return out

def rep0(run):
    return {r["problem_id"]: r for r in rows_of(run) if r.get("rep",0)==0}

def mcnemar(a, b):
    pids = [p for p in a if p in b]
    n10 = sum(1 for p in pids if a[p]["solved"] and not b[p]["solved"])
    n01 = sum(1 for p in pids if b[p]["solved"] and not a[p]["solved"])
    n = n10+n01
    p = min(1.0, sum(math.comb(n,k) for k in range(0,min(n10,n01)+1))/2**n*2) if n else 1.0
    return n10, n01, round(p,6)

def main():
    gates = []
    for _, run, mt in ARMS:
        gates += gate(run, mt)
    result = {"pre_registration": "A113", "arms": {r:run for r,run,_ in ARMS}}
    if gates:
        result["status"] = "BLOCKED"
        result["gate_failures"] = gates
        result["note"] = "Surface/row/poison gate failed; contrasts NOT computed on contaminated data (A112 lesson). Quarantine+redo per A113, then rerun this look."
    else:
        result["status"] = "CLEAN"
        result["metrics"] = {r: metrics(run) for r,run,_ in ARMS}
        ev, ct, sb = rep0("mstf_evolve_test"), rep0("mstf_base_test"), rep0("mstf_sota_test")
        c = mcnemar(ev, ct); s = mcnemar(ev, sb)
        fam = sorted([("evolve_vs_control", c[2]), ("evolve_vs_sibling", s[2])], key=lambda x:x[1])
        holm = {}
        run_max = 0.0
        for i,(name,pv) in enumerate(fam):
            run_max = max(run_max, min(1.0,(2-i)*pv)); holm[name] = round(run_max,6)
        result["primary_contrast"] = {
            "evolve_vs_control": {"discordant": f"{c[0]}:{c[1]}", "raw_p": c[2], "holm_p": holm["evolve_vs_control"]},
            "evolve_vs_sibling": {"discordant": f"{s[0]}:{s[1]}", "raw_p": s[2], "holm_p": holm["evolve_vs_sibling"]}}
        p = result["metrics"]
        result["ordering"] = sorted([(r, p[r]["pooled"]["pass1"]) for r,_,_ in ARMS], key=lambda x:-x[1])
    (common.LOGS/"a113_look_result.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))
    return result

if __name__ == "__main__":
    main()
