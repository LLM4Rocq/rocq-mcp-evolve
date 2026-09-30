#!/usr/bin/env python3
"""Evidence printer for audit_verify.py output: one compact dossier per row
so a triage reader can classify a gate/verifier disagreement without
re-running anything.

    python3 harness/audit_verify_show.py logs/audit_verify/RUN.jsonl [--all]
        [--problems id1,id2] [--diff-lines N] [--json]

Default: disagreements only (rows where the sibling's verdict differs from
the gate's recorded verdict).  --all prints every row.  --json emits the
dossiers as JSON lines instead of text.

Each dossier carries: both verdicts, today's gate verdict on the same file,
artifact provenance (which file, whether it was rewritten after the attempt
ended), the sibling's reason / method / error tail / assumptions, and a
unified diff of the candidate's head (everything before the proof body)
against the shipped task prefix -- which shows exactly what a prefix_modified
candidate changed.
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402

PROOF_START = re.compile(r"^\s*Proof\b", re.M)


def head_of(candidate, prefix, thm):
    """Candidate text up to the TARGET theorem's proof body: the region the
    prefix lock covers.  Helper lemmas inserted before the target therefore
    show up as '+' lines and the target statement itself stays in place."""
    decl = re.search(r"\b(Theorem|Lemma|Fact|Corollary|Proposition|Remark|Example)\s+"
                     + re.escape(thm or "\x00") + r"\b", candidate)
    start = decl.end() if decl else 0
    m = PROOF_START.search(candidate, start)
    if m:
        return candidate[: m.start()]
    return candidate[: len(prefix) + 200]


def dossier(r, diff_lines):
    ad = common.LOGS / r["attempt_dir"]
    prefix = (ad / "task_prefix.v").read_text()
    art = ad / r["artifact"]
    cand = art.read_text() if art.exists() else ""
    v = r["verify"]
    d = {
        "run": r["run_id"], "problem_id": r["problem_id"], "rep": r["rep"],
        "difficulty": r.get("difficulty"),
        "gate_record": "solved" if r["gate_solved"] else f"rejected:{r['gate_reason']}",
        "gate_today": None if r.get("gate_now") is None else (
            "solved" if r["gate_now"]["solved"] else f"rejected:{r['gate_now']['reason']}"),
        "artifact": r["artifact"], "artifact_kind": r["artifact_kind"],
        "artifact_late_s": r.get("artifact_late_s"),
        "artifact_post_deadline": r.get("artifact_post_deadline"),
        "attempt_timed_out": r.get("attempt_timed_out"),
        "sibling": "accept" if v.get("success") else f"reject:{v.get('reason')}",
        "sibling_method": v.get("verification_method"),
        "sibling_error_tail": (v.get("error") or "")[-600:],
        "sibling_assumptions": v.get("assumptions"),
        "gate_axioms": r.get("gate_axioms"),
        "env_inject": r.get("env_inject"),
        "verify_s": r.get("verify_s"),
        "theorem_name": r.get("theorem_name"),
        "candidate_lines": cand.count("\n"),
        "attempt_dir": str(ad),
    }
    hd = head_of(cand, prefix, r.get("theorem_name"))
    diff = list(difflib.unified_diff(prefix.splitlines(), hd.splitlines(),
                                     "task_prefix.v", "candidate_head", lineterm="", n=1))
    d["head_diff"] = "\n".join(diff[2:2 + diff_lines]) if diff else "(candidate head identical to task prefix)"
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--problems", default="")
    ap.add_argument("--diff-lines", type=int, default=40)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--batch", default="",
                    help="i/k: print only the i-th (1-based) of k equal slices of the selected rows")
    ap.add_argument("--count", action="store_true", help="print only the number of selected rows")
    a = ap.parse_args()
    keep = set(a.problems.split(",")) if a.problems else None
    rows = [json.loads(l) for l in open(a.path)]
    sel = [r for r in rows if (not keep or r["problem_id"] in keep) and (a.all or not r["agree"])]
    if a.count:
        print(len(sel))
        return
    if a.batch:
        i, k = (int(x) for x in a.batch.split("/"))
        size = -(-len(sel) // k)
        sel = sel[(i - 1) * size: i * size]
    n = 0
    for r in sel:
        d = dossier(r, a.diff_lines)
        n += 1
        if a.json:
            print(json.dumps(d))
            continue
        print("=" * 78)
        print(f"{d['run']} :: {d['problem_id']} rep{d['rep']} ({d['difficulty']})  thm={d['theorem_name']}")
        print(f"  gate record : {d['gate_record']}    gate today: {d['gate_today']}")
        print(f"  sibling     : {d['sibling']}  method={d['sibling_method']}  ({d['verify_s']}s, env_inject={d['env_inject']})")
        print(f"  artifact    : {d['artifact']} [{d['artifact_kind']}] late_s={d['artifact_late_s']} "
              f"post_deadline={d['artifact_post_deadline']} attempt_timed_out={d['attempt_timed_out']}")
        print(f"  gate axioms : {d['gate_axioms']}")
        if d["sibling_assumptions"]:
            print(f"  sibling asm : {[s.split(' :')[0] for s in d['sibling_assumptions']]}")
        if d["sibling_error_tail"]:
            print("  sibling err : " + d["sibling_error_tail"].replace("\n", "\n                "))
        print("  head diff   :")
        print("    " + d["head_diff"].replace("\n", "\n    "))
        print(f"  dir         : {d['attempt_dir']}")
    print(f"[show] {n} row(s) printed from {len(rows)} in {a.path}", file=sys.stderr)


if __name__ == "__main__":
    main()
