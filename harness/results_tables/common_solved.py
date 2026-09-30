#!/usr/bin/env python3
# New module (2026-09-09): backs RESULTS_ALL §3c (post hoc, descriptive).
"""Cost/wall/output-token efficiency for each miniF2F-test family's three
arms, restricted to the (problem, rep) pairs where control, sibling AND
evolve all solved -- so the columns are not confounded by which problems
each arm happened to solve, unlike the pass@1-conditioned $/solve, wall and
token columns of RESULTS_ALL §3.

    python3 common_solved.py <experiment_repo_root>

Families and reps, exactly as RESULTS_ALL §3 uses them (A147): every family
has two slots; slot i of an arm is one (run, rep) draw, and the pairs are
formed slot-wise across the family's three arms. For sonnet, haiku,
mistral and terra a slot is simply rep i of the arm's run; for opus the
control's slot 0 is the A142 pinned-environment rerun
(FINAL_pf_baseline_opus_r245, its only rep) and slot 1 the registered rep 1
of FINAL_pf_baseline_opus, while sibling and evolve use their registered
reps 0 and 1 — the same coherent pair §3 reports. Slot pairing is a
convention (reps are independent draws), stated in the section text.

A (problem, slot) pair enters a family's set when all three of its arms
solved that pair. A pair is then DROPPED (excluded, counted separately) if
any arm's solved attempt there was wall-killed: a Claude-CLI attempt whose
usage.estimated is true has no final usage record and hence no exact cost
or output-token count (same convention `results_all_gen.py` already uses
for the out-ktok-over-solved column elsewhere in this document). Mistral
and terra attempts always carry an exact recorded cost and token count
(A139/heldout_cost_recovered's own note: those two drivers record a cost
for every attempt), so only the Claude-CLI families (sonnet, opus) can ever
drop a pair.

Per surviving pair and arm: cost = the row's own total_cost_usd; wall = the
row's own wall_s; output tokens = usage.output_tokens (Claude-CLI, exact by
construction here), completion_tokens (terra/OpenRouter, exact), or the sum
of usage.completion_tokens over every "assistant" line of the attempt's own
transcript.jsonl (Mistral -- mirrors, without importing across the
harness/results_tables.py script boundary per this directory's existing
convention (see cap30_truncation.py), `results_all_gen.py`'s
`_mistral_transcript_sums`: one model call per assistant line, no cap).
$/solve, wall and out-ktok per arm/bucket are then the plain mean of those
per-pair values over the pairs in the family's set -- every attempt in the
set is solved, so (unlike every other cost/wall cell in this document)
there is no failure convention to state.
"""
import argparse
import json
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
BUCKETS = ("easy", "medium", "hard")

def _two_reps(run):
    return [(run, 0), (run, 1)]


# family -> arm -> [(run, rep) per slot]
FAMILIES = {
    "haiku": {"control": _two_reps("FINAL_pf_baseline_haiku"),
              "sibling": _two_reps("FINAL_pf_rocqmcp_haiku"),
              "evolve": _two_reps("FINAL_pf_session2_haiku")},
    "sonnet": {"control": _two_reps("FINAL_pf_baseline_sonnet"),
               "sibling": _two_reps("FINAL_pf_rocqmcp_sonnet"),
               "evolve": _two_reps("FINAL_pf_session2_sonnet")},
    "opus": {"control": [("FINAL_pf_baseline_opus_r245", 0), ("FINAL_pf_baseline_opus", 1)],
             "sibling": _two_reps("FINAL_pf_rocqmcp_opus"),
             "evolve": _two_reps("FINAL_pf_session2_opus")},
    "mistral": {"control": _two_reps("mstf_base_test"),
                "sibling": _two_reps("mstf_sota_test"),
                "evolve": _two_reps("mstf_evolve_test")},
    "terra": {"control": _two_reps("orp_base_test"),
              "sibling": _two_reps("orp_sib_test"),
              "evolve": _two_reps("orp_evolve_test")},
}
ARM_ORDER = ("control", "sibling", "evolve")


def _jl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def _mistral_out_tokens(exp_root, run, row):
    """Sum of usage.completion_tokens over every "assistant" line of one
    Mistral attempt's transcript -- the per-call reasoning-included output
    total, no cap (every attempt reaching this function is solved)."""
    name = row["problem_id"]
    path = (exp_root / "logs" / "runs" / run / "attempts"
            / f"{name}__rep{row.get('rep', 0)}" / "transcript.jsonl")
    tout = 0
    try:
        fh = open(path, errors="replace")
    except OSError:
        return 0
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "assistant":
                continue
            tout += (d.get("usage") or {}).get("completion_tokens", 0) or 0
    return tout


def _row_out_tokens(exp_root, run, row):
    """(output_tokens, exact) for one solved row of any §3c driver family."""
    if "usage" in row:
        u = row["usage"]
        return u["output_tokens"], not u.get("estimated")
    if "prompt_tokens" in row:
        return row["completion_tokens"], True
    return _mistral_out_tokens(exp_root, run, row), True


def _wall_killed(row):
    """A Claude-CLI solved attempt with no final usage record (mistral/terra
    rows never carry "usage" and so are never wall-killed by this test)."""
    u = row.get("usage")
    return bool(u) and bool(u.get("estimated"))


def build(exp_root):
    """family -> {"n": {bucket: int}, "dropped": int,
    "arms": {arm: {bucket: {"cost", "wall", "out_ktok"} or None}}}, over the
    (problem, rep) pairs every arm of the family solved (wall-killed pairs
    dropped and counted)."""
    out = {}
    file_cache = {}

    def run_rows(run):
        if run not in file_cache:
            file_cache[run] = _jl(exp_root / "logs" / "runs" / run / "results.jsonl")
        return file_cache[run]

    for fam, spec in FAMILIES.items():
        n_slots = len(spec["control"])
        # rows_by_arm[arm][(pid, slot)] = row; slot_run[arm][slot] = source run
        rows_by_arm = {a: {} for a in ARM_ORDER}
        slot_run = {a: {} for a in ARM_ORDER}
        for arm in ARM_ORDER:
            for slot, (run, rep) in enumerate(spec[arm]):
                slot_run[arm][slot] = run
                for r in run_rows(run):
                    if r.get("rep", 0) == rep:
                        rows_by_arm[arm][(r["problem_id"], slot)] = r
        problem_ids = sorted({pid for (pid, _slot) in rows_by_arm["control"]})

        n = {b: 0 for b in BUCKETS}
        dropped = 0
        sums = {a: {b: {"cost": 0.0, "wall": 0.0, "out_tok": 0, "n": 0} for b in BUCKETS} for a in ARM_ORDER}
        for pid in problem_ids:
            for slot in range(n_slots):
                key = (pid, slot)
                if not all(key in rows_by_arm[a] for a in ARM_ORDER):
                    continue
                rows = {a: rows_by_arm[a][key] for a in ARM_ORDER}
                if not all(rows[a]["solved"] for a in ARM_ORDER):
                    continue
                if any(_wall_killed(rows[a]) for a in ARM_ORDER):
                    dropped += 1
                    continue
                buckets = {rows[a]["difficulty"] for a in ARM_ORDER}
                assert len(buckets) == 1, (fam, pid, slot, buckets)
                b = buckets.pop()
                n[b] += 1
                for a in ARM_ORDER:
                    r = rows[a]
                    tout, exact = _row_out_tokens(exp_root, slot_run[a][slot], r)
                    assert exact, (fam, a, pid, slot)  # dropped above whenever any arm is inexact
                    s = sums[a][b]
                    s["cost"] += r.get("total_cost_usd") or 0
                    s["wall"] += r["wall_s"]
                    s["out_tok"] += tout
                    s["n"] += 1
        arms_out = {}
        for a in ARM_ORDER:
            arms_out[a] = {}
            for b in BUCKETS:
                s = sums[a][b]
                if s["n"] == 0:
                    arms_out[a][b] = None
                else:
                    arms_out[a][b] = {"cost": s["cost"] / s["n"], "wall": s["wall"] / s["n"],
                                       "out_ktok": s["out_tok"] / s["n"] / 1000.0}
        out[fam] = {"n": n, "dropped": dropped, "arms": arms_out}
    return out


def main():
    ap = argparse.ArgumentParser(description="§3c common-solved-pair efficiency rows.")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                     help="experiment repo root (default: this repository)")
    args = ap.parse_args()
    out = build(args.exp_root)
    for fam, rec in out.items():
        print(f"{fam}: n={rec['n']} dropped={rec['dropped']}")
        for a in ARM_ORDER:
            cells = []
            for b in BUCKETS:
                v = rec["arms"][a][b]
                cells.append("--" if v is None else f"${v['cost']:.2f}/{v['wall']:.0f}s/{v['out_ktok']:.1f}k")
            print(f"  {a:8s} " + " / ".join(cells))


if __name__ == "__main__":
    main()
