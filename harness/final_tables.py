#!/usr/bin/env python3
"""Held-out miniF2F table generator (A74/A76/A80/A81 matrix).

    python3 harness/final_tables.py            # refuses unless all gates pass
    python3 harness/final_tables.py --force    # print anyway, loudly flagged

Deterministic and safe by construction: it REFUSES to emit numbers unless
every arm passes its integrity gates (row counts, zero live quota-poisoning
markers, zero machine_slept). It emits (a) a human table, (b) formatted table rows, (c) a JSON artifact with full provenance. Always run THIS script and paste its output — never hand-compute.

Reporting conventions are pinned by the trail: pass@1 = rep0 solves /
problems; pass@2 = either-rep solves; $/solve = total cost of ALL attempts
(failures included) / solved attempts; latency = mean wall over SOLVED
attempts only; kill rate = wall-killed attempts (A78). Wilson 95% CIs on
pass@1. No other statistics are computed here; anything further needs a
new pre-registration.
"""

import argparse
import glob
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common

# A147 (2026-09-16): an arm's rows may be assembled from more than one run.
# COMPOSITE maps an arm key to its sources, (run_id, source_rep, reported_rep):
# the opus control's coherent pair is rep 0 := the A142 pinned-environment
# rerun (FINAL_pf_baseline_opus_r245, its only rep) and rep 1 := the
# registered rep 1 of FINAL_pf_baseline_opus (2026-08-29). The registered
# July-era rep 0 of that run is never pooled; it is reported on its own row
# (report_rep 0, label below). Every other arm key is a plain run id.
COMPOSITE = {
    "FINAL_pf_baseline_opus_coherent": [("FINAL_pf_baseline_opus_r245", 0, 0),
                                        ("FINAL_pf_baseline_opus", 1, 1)],
}
# rows every underlying run must have to be complete (244 problems x reps)
EXPECTED_RUN_N = {"FINAL_pf_baseline_opus_r245": 244}
DEFAULT_RUN_N = 488

ARMS = [
    # arm key (run_id or COMPOSITE key), label, expected_n, report_rep
    # report_rep None = all reps (pass@2 = either rep); 0 = rep-0 only,
    # pass@2 withheld (used for the registered July-era opus control row).
    ("FINAL_minif2f_test",     "evolve (haiku, phase-1 frozen config)", 488, None),
    ("FINAL_baseline_sonnet",  "naive control (sonnet, guided)",                 488, None),
    ("FINAL_session_sonnet",   "evolve (sonnet, guided)",                        488, None),
    ("FINAL_rocqmcp_sonnet",   "rocq-mcp fair (sonnet, guided)",                 488, None),
    ("FINAL_pf_baseline_sonnet", "naive control (sonnet, prompt-free A80)",      488, None),
    ("FINAL_pf_session_sonnet",  "evolve (sonnet, prompt-free A80)",             488, None),
    ("FINAL_pf_rocqmcp_sonnet",  "rocq-mcp fair (sonnet, prompt-free A99, env-bridged)", 488, None),
    ("FINAL_pf_baseline_haiku",  "naive control (haiku, prompt-free A118, rep 1 A146)", 488, None),
    ("FINAL_pf_rocqmcp_haiku",   "rocq-mcp fair (haiku, prompt-free A118, env-bridged, rep 1 A146)", 488, None),
    ("FINAL_frozen_wallonly",    "evolve (haiku, phase-1 GUIDED config, wall-only A100; not pooled, A150)", 488, None),
    ("FINAL_pf_session2_haiku",   "evolve (haiku, prompt-free A150)", 488, None),
    ("FINAL_pf_baseline_opus_coherent",
     "naive control (opus, prompt-free; rep 0 = A142 rerun, rep 1 = registered rep 1; A147)", 488, None),
    ("FINAL_pf_baseline_opus",   "naive control (opus, registered rep 0, July era; A120/A143; not pooled)", 488, 0),
    ("FINAL_pf_session2_opus",   "evolve (opus, prompt-free A117+A119)", 488, None),
    ("FINAL_pf_rocqmcp_opus",    "rocq-mcp fair (opus, prompt-free A117+A119, env-bridged)", 488, None),
    ("FINAL_pf_session2_sonnet", "evolve (sonnet, prompt-free A108, strategy-tail removed)", 488, None),
]


def rows_for(key):
    """All result rows of an arm key: a plain run's results.jsonl, or the
    COMPOSITE assembly (each source row copied with `rep` set to the reported
    rep and `source_run`/`source_rep` recording where it came from). Rows
    keep their own attempt_dir, so per-attempt readers (transcripts, tokens)
    work unchanged on composite arms."""
    if key not in COMPOSITE:
        return common.read_jsonl(common.LOGS / "runs" / key / "results.jsonl")
    out = []
    for run, src_rep, dst_rep in COMPOSITE[key]:
        for r in common.read_jsonl(common.LOGS / "runs" / run / "results.jsonl"):
            if r.get("rep", 0) != src_rep:
                continue
            r = dict(r)
            r["source_run"], r["source_rep"], r["rep"] = run, src_rep, dst_rep
            out.append(r)
    return out


def underlying_runs(key):
    return [run for run, _s, _d in COMPOSITE[key]] if key in COMPOSITE else [key]


_BUILD_CACHE = {}


def build_of(row):
    """CLI build a row's attempt ran on: the per-attempt provenance key
    (A142 runner) when present, else the attempt transcript's init event
    (first `system` line). Cached per attempt directory."""
    if row.get("claude_code_version"):
        return row["claude_code_version"]
    rel = row.get("attempt_dir")
    if not rel:
        return None
    if rel in _BUILD_CACHE:
        return _BUILD_CACHE[rel]
    ver = None
    try:
        with open(common.LOGS / rel / "transcript.jsonl", errors="replace") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("type") == "system":
                    ver = e.get("claude_code_version")
                    break
    except OSError:
        pass
    _BUILD_CACHE[rel] = ver
    return ver


def builds_census(rows):
    """{build: row count} over the rows (None for rows with no init event)."""
    out = {}
    for r in rows:
        v = build_of(r) or "unknown"
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))
POISON_MARKERS = ['"api_error_status": 429', '"api_error_status":429',
                  "session limit", "You've hit your",
                  '"api_error_status": 529']
BUCKETS = ["easy", "medium", "hard"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def audit(run):
    """Integrity gates. Returns list of failures (empty = clean)."""
    problems = []
    rd = common.LOGS / "runs" / run
    rows = common.read_jsonl(rd / "results.jsonl")
    if not rows:
        return [f"{run}: no results"]
    slept = [r for r in rows if r.get("machine_slept")]
    if slept:
        problems.append(f"{run}: {len(slept)} machine_slept rows — run "
                        f"harness/repair_run.py then resume the runner")
    live_poison = 0
    for tp in glob.glob(str(rd / "attempts" / "*" / "transcript.jsonl")):
        try:
            txt = open(tp, errors="replace").read()
        except OSError:
            continue
        if any(m in txt for m in POISON_MARKERS):
            live_poison += 1
    if live_poison:
        problems.append(f"{run}: {live_poison} LIVE quota-poisoned transcripts "
                        f"— quarantine + redo those slots (A83 procedure)")
    # A92: truly-dead rows = transcript shows NO model activity at all
    # (no assistant events AND no thinking_tokens progress). Extended
    # thinking emits system/thinking_tokens events only — such attempts
    # are LEGITIMATE failures, not infrastructure (the A89 lesson).
    dead = 0
    for r in rows:
        tp = (rd / "attempts" / f"{r['problem_id']}__rep{r.get('rep', 0)}"
              / "transcript.jsonl")
        try:
            alive = False
            for l in open(tp, errors="replace"):
                if ('"type": "assistant"' in l or '"type":"assistant"' in l
                        or '"subtype": "thinking_tokens"' in l
                        or '"subtype":"thinking_tokens"' in l):
                    alive = True
                    break
            dead += (not alive)
        except OSError:
            dead += 1
    if dead:
        problems.append(f"{run}: {dead} rows with ZERO model activity "
                        f"(true dead streams, A92) — quarantine + redo")
    # A95: a solved row must be backed by ITS OWN attempt — assistant
    # turns AND tool use in its transcript. Solved without them means the
    # verdict came from stale/shared grading artifacts left in the attempt
    # dir by a parked or concurrent predecessor (pre-A93-hardening), not
    # from anything this attempt produced.
    fp = 0
    for r in rows:
        if not r.get("solved"):
            continue
        tp = (rd / "attempts" / f"{r['problem_id']}__rep{r.get('rep', 0)}"
              / "transcript.jsonl")
        try:
            txt = open(tp, errors="replace").read()
        except OSError:
            fp += 1
            continue
        if not (('"type": "assistant"' in txt or '"type":"assistant"' in txt)
                and ('"type": "tool_use"' in txt or '"type":"tool_use"' in txt)):
            fp += 1
    if fp:
        problems.append(f"{run}: {fp} solved rows without own-transcript "
                        f"activity (stale-artifact false positives, A95) — "
                        f"quarantine + redo")
    # A100/A101: every reported held-out arm must be WALL-bound — a turn
    # cap that fires is a covert tool-call tax (A62b). The phase-1 haiku
    # arm is exempt: its cap-30 registration predates A62b and it stays
    # in the record as the measured demonstration of the tax.
    if run != "FINAL_minif2f_test":
        capped = sum(1 for r in rows
                     if str(r.get("stop_reason")) == "error_max_turns")
        if capped:
            problems.append(f"{run}: {capped} turn-cap-terminated rows — "
                            f"held-out arms must be wall-bound (A100)")
    return problems


def metrics(run, expected_n, report_rep=None):
    rows = rows_for(run)
    out = {"run": run, "n": len(rows), "expected_n": expected_n,
           "complete": len(rows) == expected_n, "report_rep": report_rep,
           "sources": COMPOSITE.get(run), "builds": builds_census(rows)}
    if report_rep is not None:
        rows = [r for r in rows if r.get("rep", 0) == report_rep]
        out["builds_reported"] = builds_census(rows)
    probs = {}
    for r in rows:
        probs.setdefault(r["problem_id"], {})[r.get("rep", 0)] = r
    per_bucket = {}
    for b in BUCKETS:
        bp = {p: v for p, v in probs.items()
              if (v.get(0) or v.get(1) or {}).get("difficulty") == b}
        n = len(bp)
        k1 = sum(1 for v in bp.values() if (v.get(0) or {}).get("solved"))
        # pass@2 is withheld (None) when only one rep is reported (A120)
        k2 = (sum(1 for v in bp.values() if any(x.get("solved") for x in v.values()))
              if report_rep is None else None)
        brows = [r for v in bp.values() for r in v.values()]
        cost = sum(r.get("total_cost_usd") or 0 for r in brows)
        srows = [r for r in brows if r.get("solved")]
        lat = (sum(r["wall_s"] for r in srows) / len(srows)) if srows else None
        kills = sum(1 for r in brows if r.get("attempt_timed_out"))
        lo, hi = wilson(k1, n)
        per_bucket[b] = {
            "n_problems": n, "pass1": k1 / n if n else None,
            "pass1_ci": (round(lo, 3), round(hi, 3)),
            "pass2": (k2 / n) if (n and k2 is not None) else None,
            "cost_per_solve": (cost / len(srows)) if srows else None,
            "latency_solved_s": round(lat, 3) if lat else None,
            "kill_rate": f"{kills}/{len(brows)}",
        }
    out["buckets"] = per_bucket
    return out


class GateFailure(Exception):
    """Raised by build_table() when an integrity gate fails and force=False
    — the same refusal main() prints without --force, as an exception a
    caller (e.g. harness/results_tables/heldout_table.py) can catch."""
    def __init__(self, failures):
        self.failures = failures
        super().__init__("; ".join(failures))


def build_table(force=False):
    """Compute the `art` dict main() writes to logs/final_heldout_table.json
    (and the `run`/`label`/`n`/`rep` rows it prints), running the exact same
    integrity gates main() runs. Refuses (raises GateFailure) unless
    force=True, exactly as main() refuses without --force. Returns
    (art, failures) — failures is empty unless force=True was needed to get
    past a gate."""
    failures = []
    seen = set()
    for key, _, _n, _rep in ARMS:
        for run in underlying_runs(key):
            if run in seen:
                continue
            seen.add(run)
            failures += audit(run)
            rows = common.read_jsonl(common.LOGS / "runs" / run / "results.jsonl")
            n = EXPECTED_RUN_N.get(run, DEFAULT_RUN_N)
            if len(rows) != n:
                failures.append(f"{run}: {len(rows)}/{n} rows — INCOMPLETE")
    if failures and not force:
        raise GateFailure(failures)

    art = {"arms": []}
    for run, label, n, rep in ARMS:
        m = metrics(run, n, rep)
        art["arms"].append({"label": label, **m})
    return art, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    try:
        art, failures = build_table(force=args.force)
    except GateFailure as e:
        print("REFUSING to emit table; integrity gates failed:")
        for f in e.failures:
            print("  -", f)
        print("\nFix per the runbook, or --force to preview (flagged).")
        sys.exit(1)
    if failures:
        print("!! FORCED OUTPUT — gates failing:", *failures, sep="\n!!   ")

    print(f"\n{'arm':46s} {'pass@1 e/m/h':>20s} {'pass@2 e/m/h':>20s}")
    latex = []
    for a in art["arms"]:
        run, label, b = a["run"], a["label"], a["buckets"]
        p1 = " / ".join(f"{b[x]['pass1']:.2f}" if b[x]["pass1"] is not None
                        else "--" for x in BUCKETS)
        p2 = " / ".join(f"{b[x]['pass2']:.2f}" if b[x]["pass2"] is not None
                        else "--" for x in BUCKETS)
        print(f"{label:46s} {p1:>20s} {p2:>20s}")
        cost = " / ".join(f"{b[x]['cost_per_solve']:.2f}"
                          if b[x]["cost_per_solve"] else "--" for x in BUCKETS)
        lat = " / ".join(f"{b[x]['latency_solved_s']:.0f}"
                         if b[x]["latency_solved_s"] else "--" for x in BUCKETS)
        latex.append(f"{run} | {label} | {p1} | {p2} | {cost} | {lat}")
    out = common.LOGS / "final_heldout_table.json"
    out.write_text(json.dumps(art, indent=1))
    print(f"\nartifact: {out}\n\n==== delimited rows (run | label | pass@1 | pass@2 | $/solve | latency) ====")
    print("\n".join(latex))
    print("\nCIs and kill rates are in the JSON artifact; archive it with "
          "the run records.")


if __name__ == "__main__":
    main()
