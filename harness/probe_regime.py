#!/usr/bin/env python3
"""A143/A144: regime probes — does an arm, run today on a subset of its
registered problems, behave like its registered rows?

Two modes, both scored within problem against the registered rows of the
SAME problems, with decision rules fixed before each probe was launched:

  --mode era        (A143, opus control) the reference arm has two eras:
                    rep 0 = July rows (CLI 2.1.209), rep 1 = August rows.
                    Axis 1: re-solve fraction on the problems solved in
                    July and lost in August; axis 2: first-turn thinking
                    and kill rate nearer the July or the August value.
  --mode stability  (A144, sonnet control / haiku evolve) the reference
                    arm has two same-era reps.  Is the probe a plausible
                    third rep?  Axis 1: P(solved | solved in both reps)
                    >= .80; axis 2: kill rate within +-.15 of the reps'
                    mean; axis 3: first-turn thinking median within x1.5
                    of the reps' median (or, when the arm barely thinks,
                    the wall median of solved attempts within x1.5).

First-turn thinking = sum of the CLI's estimated thinking-token deltas
before the first tool call.  Read-only over logs/.  Usage:

  python3 harness/probe_regime.py --mode era --reference FINAL_pf_baseline_opus \
      --manifest data/manifests/minif2f_test_opus_probe60.jsonl [--probe RUN]
  python3 harness/probe_regime.py --mode stability --reference FINAL_pf_baseline_sonnet \
      --manifest data/manifests/minif2f_test_sonnet_probe60.jsonl [--probe RUN]
"""
import argparse
import json
import math
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

JULY_VERSION = "2.1.209"
POISON = re.compile(r"limit|API Error", re.I)
THINK_FLOOR = 500  # below this reference median the thinking axis is replaced by wall


def load_rows(run_id):
    rows = {}
    for r in common.read_jsonl(common.LOGS / "runs" / run_id / "results.jsonl"):
        rows[(r["problem_id"], r.get("rep", 0))] = r
    return rows


def attempt_metrics(row):
    """Per-attempt facts from the results row plus its transcript."""
    m = {
        "solved": bool(row.get("solved")),
        "killed": bool(row.get("attempt_timed_out")),
        "wall": row.get("wall_s"),
        "version": row.get("claude_code_version"),
        "effort": row.get("effort_recorded"),
        "think_first": 0,
        "n_assistant": 0,
        "n_tool_use": 0,
        "poisoned": (not row.get("solved")) and (row.get("num_turns") or 0) <= 2
        and bool(POISON.search(row.get("result_text") or "")),
    }
    rel = row.get("attempt_dir")
    tp = common.LOGS / rel / "transcript.jsonl" if rel else None
    if not tp or not tp.exists():
        return m
    first_tool = False
    with open(tp, errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = e.get("type")
            if t == "system":
                st = e.get("subtype")
                if st == "init" and not m["version"]:
                    m["version"] = e.get("claude_code_version")
                elif st == "thinking_tokens" and not first_tool:
                    m["think_first"] += e.get("estimated_tokens_delta") or 0
            elif t == "assistant":
                m["n_assistant"] += 1
                for blk in (e.get("message") or {}).get("content") or []:
                    if isinstance(blk, dict) and blk.get("type") == "tool_use":
                        m["n_tool_use"] += 1
                        first_tool = True
    return m


def summarize(label, mets):
    n = len(mets)
    if not n:
        print(f"{label:34s} (no rows)")
        return None
    solved_walls = [x["wall"] for x in mets if x["solved"] and x["wall"] is not None]
    s = {
        "n": n,
        "solved": sum(x["solved"] for x in mets) / n,
        "killed": sum(x["killed"] for x in mets) / n,
        "think_median": statistics.median(x["think_first"] for x in mets),
        "wall_solved_median": statistics.median(solved_walls) if solved_walls else float("nan"),
        "no_assistant": sum(x["n_assistant"] == 0 for x in mets),
        "poisoned": sum(x["poisoned"] for x in mets),
    }
    print(f"{label:34s} n={n:3d} solved={s['solved']:.3f} killed={s['killed']:.3f} "
          f"first-turn thinking median={s['think_median']:6.0f} "
          f"wall(solved) median={s['wall_solved_median']:5.0f}s "
          f"no-assistant-turn={s['no_assistant']:2d} poisoned={s['poisoned']}")
    return s


def nearer(x, a, b):
    """Nearer to a (July) or b (August); log scale when all positive."""
    if x > 0 and a > 0 and b > 0:
        x, a, b = math.log(x), math.log(a), math.log(b)
    return "July" if abs(x - a) <= abs(x - b) else "August"


def within_factor(x, ref, factor):
    if ref <= 0 or x <= 0 or math.isnan(x) or math.isnan(ref):
        return None
    return max(x / ref, ref / x) <= factor


def probe_block(args, probs, strata):
    pr = load_rows(args.probe)
    missing = [p for p in probs if (p, 0) not in pr]
    have = [p for p in probs if (p, 0) in pr]
    print(f"\n== probe {args.probe}: {len(have)}/{len(probs)} attempts present"
          + (f" (missing {len(missing)})" if missing else ""))
    pm = {p: attempt_metrics(pr[(p, 0)]) for p in have}
    sp = summarize("probe", [pm[p] for p in have])
    print("  versions:", sorted({m['version'] for m in pm.values() if m['version']}),
          " effort recorded:", sorted({str(m['effort']) for m in pm.values()}))
    return pm, sp, have, missing


def mode_era(args, probs, ref):
    july, aug = {}, {}
    for pid in probs:
        r0, r1 = ref.get((pid, 0)), ref.get((pid, 1))
        if r0 is None or r1 is None:
            sys.exit(f"reference lacks both reps for {pid}")
        m0 = attempt_metrics(r0)
        if m0["version"] != JULY_VERSION:
            sys.exit(f"{pid} rep 0 is not a July row (version {m0['version']})")
        july[pid], aug[pid] = m0, attempt_metrics(r1)
    strata = {}
    for pid in probs:
        a, b = july[pid]["solved"], aug[pid]["solved"]
        strata[pid] = "both" if a and b else "july_only" if a else "aug_only" if b else "neither"
    counts = {s: sum(v == s for v in strata.values()) for s in ("both", "july_only", "aug_only", "neither")}
    print(f"probe subset: {len(probs)} problems, strata {counts}")
    print("\n== reference rows on the SAME problems ==")
    sj = summarize("July rep 0 (2.1.209)", [july[p] for p in probs])
    sa = summarize("August rep 1", [aug[p] for p in probs])
    if not args.probe:
        print("\n(no --probe given; reference only)")
        return
    pm, sp, have, missing = probe_block(args, probs, strata)
    jo = [p for p in have if strata[p] == "july_only"]
    resolve = sum(pm[p]["solved"] for p in jo) / len(jo) if jo else float("nan")
    agree_j = sum(pm[p]["solved"] == july[p]["solved"] for p in have) / len(have)
    agree_a = sum(pm[p]["solved"] == aug[p]["solved"] for p in have) / len(have)
    print("\n== within-problem ==")
    print(f"  axis 1: re-solve fraction on july_only ({len(jo)} problems) = {resolve:.3f}"
          f"   [pre-registered: >= .70 July-like, <= .35 August-like, else intermediate]")
    print(f"  agreement of probe outcomes with July rows = {agree_j:.3f}, with August rows = {agree_a:.3f}")
    ax2_t = nearer(sp["think_median"], sj["think_median"], sa["think_median"])
    ax2_k = nearer(sp["killed"], sj["killed"], sa["killed"])
    print(f"  axis 2: first-turn thinking median {sp['think_median']:.0f} vs July {sj['think_median']:.0f} / "
          f"August {sa['think_median']:.0f} -> nearer {ax2_t}")
    print(f"          kill rate {sp['killed']:.3f} vs July {sj['killed']:.3f} / August {sa['killed']:.3f} -> nearer {ax2_k}")
    ax1 = "July" if resolve >= .70 else "August" if resolve <= .35 else "intermediate"
    if ax1 == ax2_t == ax2_k:
        verdict = f"{ax1}-like on both axes"
    else:
        verdict = f"MIXED (outcome {ax1}; thinking {ax2_t}; kills {ax2_k}) -> treat as a third regime, not a match"
    finish(verdict, sp, missing)


def mode_stability(args, probs, ref):
    r0m, r1m = {}, {}
    for pid in probs:
        r0, r1 = ref.get((pid, 0)), ref.get((pid, 1))
        if r0 is None or r1 is None:
            sys.exit(f"reference lacks both reps for {pid}")
        r0m[pid], r1m[pid] = attempt_metrics(r0), attempt_metrics(r1)
    strata = {}
    for pid in probs:
        a, b = r0m[pid]["solved"], r1m[pid]["solved"]
        strata[pid] = "both" if a and b else "one" if a or b else "neither"
    counts = {s: sum(v == s for v in strata.values()) for s in ("both", "one", "neither")}
    versions = sorted({m["version"] for m in list(r0m.values()) + list(r1m.values()) if m["version"]})
    print(f"probe subset: {len(probs)} problems, strata {counts}, reference builds {versions}")
    print("\n== reference reps on the SAME problems ==")
    s0 = summarize("reference rep 0", [r0m[p] for p in probs])
    s1 = summarize("reference rep 1", [r1m[p] for p in probs])
    both = [p for p in probs if strata[p] == "both"]
    solved0 = [p for p in probs if r0m[p]["solved"]]
    re01 = sum(r1m[p]["solved"] for p in solved0) / len(solved0) if solved0 else float("nan")
    agree01 = sum(r0m[p]["solved"] == r1m[p]["solved"] for p in probs) / len(probs)
    ref_kill = (s0["killed"] + s1["killed"]) / 2
    ref_think = statistics.median([r0m[p]["think_first"] for p in probs] + [r1m[p]["think_first"] for p in probs])
    ref_walls = [m["wall"] for m in list(r0m.values()) + list(r1m.values()) if m["solved"] and m["wall"] is not None]
    ref_wall = statistics.median(ref_walls) if ref_walls else float("nan")
    print(f"  within reference: P(rep1 solved | rep0 solved) = {re01:.3f}; rep0/rep1 agreement = {agree01:.3f}; "
          f"mean kill rate = {ref_kill:.3f}; thinking median (both reps) = {ref_think:.0f}; wall(solved) median = {ref_wall:.0f}s")
    if not args.probe:
        print("\n(no --probe given; reference only)")
        return
    pm, sp, have, missing = probe_block(args, probs, strata)
    both_have = [p for p in have if strata[p] == "both"]
    resolve = sum(pm[p]["solved"] for p in both_have) / len(both_have) if both_have else float("nan")
    agree0 = sum(pm[p]["solved"] == r0m[p]["solved"] for p in have) / len(have)
    agree1 = sum(pm[p]["solved"] == r1m[p]["solved"] for p in have) / len(have)
    print("\n== within-problem ==")
    ax1 = resolve >= .80
    print(f"  axis 1: P(probe solved | solved in both reps) on {len(both_have)} problems = {resolve:.3f}"
          f"   [pre-registered: >= .80 consistent]  -> {'ok' if ax1 else 'FAIL'}")
    print(f"  agreement of probe outcomes with rep 0 = {agree0:.3f}, with rep 1 = {agree1:.3f} (rep 0 vs rep 1: {agree01:.3f})")
    ax2 = abs(sp["killed"] - ref_kill) <= .15
    print(f"  axis 2: kill rate {sp['killed']:.3f} vs reference {ref_kill:.3f}   [within +-.15]  -> {'ok' if ax2 else 'FAIL'}")
    if ref_think >= THINK_FLOOR:
        ax3 = within_factor(sp["think_median"], ref_think, 1.5)
        print(f"  axis 3: first-turn thinking median {sp['think_median']:.0f} vs reference {ref_think:.0f}   [within x1.5]  -> {'ok' if ax3 else 'FAIL'}")
    else:
        ax3 = within_factor(sp["wall_solved_median"], ref_wall, 1.5)
        print(f"  axis 3: wall(solved) median {sp['wall_solved_median']:.0f}s vs reference {ref_wall:.0f}s   [within x1.5; thinking axis "
              f"replaced because the reference median is {ref_think:.0f} < {THINK_FLOOR}]  -> {'ok' if ax3 else 'FAIL'}")
    fails = [name for name, ok in (("re-solve", ax1), ("kills", ax2), ("signature", ax3)) if not ok]
    if not fails:
        verdict = "UNCHANGED since the registered reps (all three axes)"
    elif not ax1 or len(fails) >= 2:
        verdict = f"CHANGED regime (failed: {', '.join(fails)})"
    else:
        verdict = f"AMBIGUOUS (failed only: {', '.join(fails)}) -> report, do not read as either"
    finish(verdict, sp, missing)


def finish(verdict, sp, missing):
    if sp["poisoned"]:
        verdict += f"  !! {sp['poisoned']} quota-poisoned attempts: wipe and rerun those before reading this"
    if missing:
        verdict += "  (probe incomplete: the rule needs every attempt)"
    print(f"\nVERDICT: {verdict}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("era", "stability"), default="era")
    ap.add_argument("--reference", default="FINAL_pf_baseline_opus")
    ap.add_argument("--manifest", default="data/manifests/minif2f_test_opus_probe60.jsonl")
    ap.add_argument("--probe", default=None, help="run id of the probe (omit for reference only)")
    args = ap.parse_args()
    probs = [r["problem_id"] for r in common.load_manifest(args.manifest)]
    ref = load_rows(args.reference)
    (mode_era if args.mode == "era" else mode_stability)(args, probs, ref)


if __name__ == "__main__":
    main()
