#!/usr/bin/env python3
# New module (2026-09-25, A152): the tables of the write-up, computed from
# logs/ under one stated convention each, so that every presented cell is
# regenerable. Exposes build(exp_root) -> dict (the harness/report_tables_gen.py entry
# point); nothing archived.
"""Report tables (docs/REPORT_TABLES.md, via harness/report_tables_gen.py): the held-out matrix with cost and wall
time on the common-solved problems, the efficiency table, the project-scale
tables, and the evolution points.

Conventions, fixed here and nowhere else:

  accuracy (miniF2F)  solved attempts / attempts over BOTH runs, per bucket and pooled
                      (A154; §3 of RESULTS_ALL keeps its registered rep-0 pass@1 look).
  intersection        a problem is common-solved when EVERY server of the family
                      solved it in at least one run; n per bucket is the number of
                      such problems.
  cost, wall (miniF2F) per server: mean over that server's SOLVED attempts, both
                      runs, on the common-solved problems (a Claude-CLI solved
                      attempt with no final usage record contributes its wall time
                      and a cost of 0 -- the row's recorded cost -- exactly as §3);
                      cost_full / wall_full = the same means over every solved
                      attempt of the whole dataset (appendix variant).
  efficiency          on the same attempts: calls = tool_use blocks in the
                      transcript (Claude CLI) or tool calls recorded by the driver
                      (Mistral/OpenRouter); input tokens = prompt tokens incl. cache
                      reads and writes; output tokens = the attempt's final usage
                      (exact; attempts without a final usage record are excluded
                      from the token means and counted); output per call = mean
                      output / mean calls per model; the "all models" row is the
                      plain mean over the models present.
  per-run (miniF2F)   the three quantities above on each run alone (appendix variant).
  projects            accuracy = solved runs / runs with the re-verified verdict;
                      accuracy_sd = sample standard deviation of the per-run accuracy
                      (solved tasks / 5) across runs; cost_sd, wall_sd = sample standard
                      deviations over the solved runs;
                      (rows the A130/A131 audit classified ext_mismatch are counted
                      unsolved); cost and wall = means over solved runs; per-task
                      counts with the same rule.
  evolution points    per development run: pooled accuracy = solved attempts /
                      attempts over all runs; cost and wall = means over solved
                      attempts.
  paired tests        one unit per problem: a problem is "better" when the first server
                      solved strictly more of its runs than the second, "worse" when fewer;
                      exact two-sided sign test on the better:worse split (dev60: final
                      Phase-1 server vs control over four runs; miniF2F test: evolve vs
                      control and vs sibling over both runs).
  auto-closable       F = problems auto_close alone solves (rep 0 of finisher_only_test);
                      per server: solved attempts / attempts on F over both runs, cost
                      and wall = means over those solved attempts; "all models" = plain
                      mean over the models.

Usage: python3 report_tables.py [EXPERIMENT_REPO_ROOT]
"""
import argparse
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import final_tables as ft  # noqa: E402  (rows_for: composite arms)

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
BUCKETS = ("easy", "medium", "hard")
ARMS = ("control", "sibling", "evolve")

MF2F_FAMILIES = {
    "haiku": {"control": "FINAL_pf_baseline_haiku", "sibling": "FINAL_pf_rocqmcp_haiku", "evolve": "FINAL_pf_session2_haiku"},
    "sonnet": {"control": "FINAL_pf_baseline_sonnet", "sibling": "FINAL_pf_rocqmcp_sonnet", "evolve": "FINAL_pf_session2_sonnet"},
    "opus": {"control": "FINAL_pf_baseline_opus_coherent", "sibling": "FINAL_pf_rocqmcp_opus", "evolve": "FINAL_pf_session2_opus"},
    "terra": {"control": "orp_base_test", "sibling": "orp_sib_test", "evolve": "orp_evolve_test"},
}
AUTOFORM_FAMILIES = {
    "sonnet": {"control": "af3_base", "sibling": "af3_sota", "evolve": "af3_evolve"},
    "opus": {"control": "op_base", "sibling": "op_sota", "evolve": "op_evolve"},
    "terra": {"control": "orp3_base", "sibling": "orp3_sota", "evolve": "orp3_evolve"},
}
# evolution points: index in the write-up's figure -> development run
EVOLUTION_RUNS = [
    (0, "control", "baseline_dev60", "dev60", "kept"), (1, "session", "session_dev60", "dev60", "kept"),
    (2, "try", "session_try_dev60", "dev60", "kept"), (3, "compact rendering", "session_try_compact_dev60", "dev60", "reverted"),
    (4, "search", "session_try_search_dev60", "dev60", "reverted"), (5, "Lean-ism hints", "session_try_hints_dev60", "dev60", "kept"),
    (6, "auto_close", "session_try_hints_auto_dev60", "dev60", "kept"), (7, "did-you-mean", "session_try_hints_auto_sugg_dev60", "dev60", "kept"),
    (7, "did-you-mean (miniF2F valid, before preloading)", "session_try_hints_minif2f_valid", "minif2f_valid", "kept"),
    (8, "preloading", "session_try_hints_v2_minif2f_valid", "minif2f_valid", "kept"),
    (8, "did-you-mean (hard70, solo)", "solo_hard70", "hard70", "kept"), (9, "team of three", "team_k3_hard70", "hard70", "reverted"),
    (10, "hint synthesis", "winner_auto2_dev60", "dev60", "kept"), (11, "check", "universal_c30_dev60", "dev60", "kept"),
    (11, "check (mathcomp35)", "winner_ctx_lean_mathcomp", "mathcomp35", "kept"),
    (12, "ssreflect hints", "winner_ctx_lean_ssr_mathcomp", "mathcomp35", "reverted"),
    (13, "exemplar retrieval", "winner_ctx_lean_ex_mathcomp", "mathcomp35", "reverted"),
    (14, "shipped server", "af3_evolve", "autoform", "kept"), (15, "hole visibility", "af3_evolve_r1", "autoform", "reverted"),
    (16, "finisher in open", "af3_evolve_r3", "autoform", "reverted"), (17, "compact rendering (2nd)", "af3_evolve_c3", "autoform", "reverted"),
]
# per-mutation deltas: (label, dataset label, run, predecessor run); phase 2 rows have no buckets
DELTA_PAIRS = [
    ("step, rollback, state", "dev60", "session_dev60", "baseline_dev60"),
    ("try", "dev60", "session_try_dev60", "session_dev60"),
    ("compact rendering", "dev60", "session_try_compact_dev60", "session_try_dev60"),
    ("search", "dev60", "session_try_search_dev60", "session_try_dev60"),
    ("Lean-ism hints", "dev60", "session_try_hints_dev60", "session_try_dev60"),
    ("auto_close", "dev60", "session_try_hints_auto_dev60", "session_try_hints_dev60"),
    ("near-miss hints", "dev60", "session_try_hints_auto_sugg_dev60", "session_try_hints_auto_dev60"),
    ("preload", "miniF2F valid", "session_try_hints_v2_minif2f_valid", "session_try_hints_minif2f_valid"),
    ("team of three", "hard70", "team_k3_hard70", "solo_hard70"),
    ("false-winner fix", "dev60", "winner_autofix_dev60", "session_try_hints_auto_sugg_dev60"),
    ("real arithmetic help", "dev60", "winner_auto2_dev60", "winner_autofix_dev60"),
    ("check, Haiku", "dev60", "universal_c30_dev60", "winner_auto2_dev60"),
    ("check, Sonnet", "dev60", "universal_sonnet_dev60", "session_try_hints_auto_sonnet_dev60"),
    ("ssreflect hints", "mathcomp35", "winner_ctx_lean_ssr_mathcomp", "winner_ctx_lean_mathcomp"),
    ("exemplar retrieval", "mathcomp35", "winner_ctx_lean_ex_mathcomp", "winner_ctx_lean_mathcomp"),
    ("hole visibility", "autoform", "af3_evolve_r1", "af3_evolve"),
    ("finisher open", "autoform", "af3_evolve_r3", "af3_evolve"),
    ("compact rendering (2nd)", "autoform", "af3_evolve_c3", "af3_evolve"),
]


def _jl(path):
    return [json.loads(l) for l in open(path, errors="replace") if l.strip()]


def _cost(r):
    return r.get("total_cost_usd") or 0.0


def _rows_by_slot(run):
    return {(r["problem_id"], r.get("rep", 0)): r for r in ft.rows_for(run)}


# ---------------------------------------------------------------- tokens/calls
def _claude_transcript(path):
    """(tool_use blocks, input tokens summed over distinct messages, output
    tokens of the final usage or None) for one Claude-CLI attempt."""
    n_tu, tin, seen, final_out = 0, 0, set(), None
    try:
        fh = open(path, errors="replace")
    except OSError:
        return 0, 0, None
    with fh:
        for line in fh:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = e.get("type")
            if t == "assistant":
                m = e.get("message") or {}
                for b in m.get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        n_tu += 1
                mid = m.get("id")
                if mid in seen:
                    continue
                seen.add(mid)
                u = m.get("usage") or {}
                tin += (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0))
            elif t == "result":
                final_out = (e.get("usage") or {}).get("output_tokens")
    return n_tu, tin, final_out


def _attempt_efficiency(exp_root, run, row):
    """(calls, tokens_in, tokens_out or None) for one solved attempt of any
    driver family."""
    if "usage" in row:  # Claude CLI
        calls, tin, tout = _claude_transcript(exp_root / "logs" / row["attempt_dir"] / "transcript.jsonl")
        u = row["usage"]
        if not u.get("estimated"):
            tin = u["input_tokens"] + u["cache_read_input_tokens"] + u["cache_creation_input_tokens"]
            tout = u["output_tokens"]
        else:
            tout = None
        return calls, tin, tout
    if "prompt_tokens" in row:  # OpenRouter driver: exact per attempt
        return row.get("tool_calls") or 0, row["prompt_tokens"], row["completion_tokens"]
    # Mistral driver: sum over the attempt transcript
    tin = tout = 0
    path = exp_root / "logs" / "runs" / run / "attempts" / f"{row['problem_id']}__rep{row.get('rep', 0)}" / "transcript.jsonl"
    for d in _jl(path) if path.exists() else []:
        if d.get("type") == "assistant":
            u = d.get("usage") or {}
            tin += u.get("prompt_tokens", 0) or 0
            tout += u.get("completion_tokens", 0) or 0
    return row.get("tool_calls") or 0, tin, tout


# ---------------------------------------------------------------- miniF2F
def build_minif2f(exp_root):
    out = {}
    for fam, runs in MF2F_FAMILIES.items():
        R = {a: _rows_by_slot(runs[a]) for a in ARMS}
        pids = sorted({p for p, _ in R["control"]})
        reps = sorted({s for _, s in R["control"]})
        bucket = {p: R["control"][(p, reps[0])]["difficulty"] for p in pids}
        common = [p for p in pids if all(any(R[a][(p, s)]["solved"] for s in reps if (p, s) in R[a]) for a in ARMS)]
        n = {b: sum(bucket[p] == b for p in common) for b in BUCKETS}
        n["all"] = len(common)
        fam_out = {"n_common": n, "arms": {}}
        for a in ARMS:
            rows_all = list(R[a].values())   # every attempt, both runs (A154)
            acc = {b: sum(r["solved"] for r in rows_all if r["difficulty"] == b) / sum(1 for r in rows_all if r["difficulty"] == b) for b in BUCKETS}
            acc["all"] = sum(r["solved"] for r in rows_all) / len(rows_all)
            sel = [R[a][(p, s)] for p in common for s in reps if (p, s) in R[a] and R[a][(p, s)]["solved"]]
            cost, wall, eff = {}, {}, {}
            for b in BUCKETS + ("all",):
                rs = [r for r in sel if b == "all" or r["difficulty"] == b]
                cost[b] = statistics.mean(_cost(r) for r in rs) if rs else None
                wall[b] = statistics.mean(r["wall_s"] for r in rs) if rs else None
            calls, tins, touts, excluded = [], [], [], 0
            for r in sel:
                c, ti, to = _attempt_efficiency(exp_root, runs[a], r)
                calls.append(c)
                tins.append(ti)
                if to is None:
                    excluded += 1
                else:
                    touts.append(to)
            eff = {"calls": statistics.mean(calls) if calls else None,
                   "tokens_in": statistics.mean(tins) if tins else None,
                   "tokens_out": statistics.mean(touts) if touts else None,
                   "out_excluded": excluded, "n_attempts": len(sel)}
            eff["tokens_out_per_call"] = (eff["tokens_out"] / eff["calls"]) if eff["calls"] and eff["tokens_out"] is not None else None
            # whole-dataset variant (appendix): the same means over every solved attempt, both runs
            solved_all = [r for r in R[a].values() if r["solved"]]
            cost_full, wall_full = {}, {}
            for b in BUCKETS + ("all",):
                rs = [r for r in solved_all if b == "all" or r["difficulty"] == b]
                cost_full[b] = statistics.mean(_cost(r) for r in rs) if rs else None
                wall_full[b] = statistics.mean(r["wall_s"] for r in rs) if rs else None
            # per-run variant (appendix): the same quantities on each run alone
            per_run = {}
            for s_ in reps:
                rs_run = [r for r in rows_all if r.get("rep", 0) == s_]
                acc_r = {b: sum(r["solved"] for r in rs_run if r["difficulty"] == b) / sum(1 for r in rs_run if r["difficulty"] == b) for b in BUCKETS}
                acc_r["all"] = sum(r["solved"] for r in rs_run) / len(rs_run)
                sel_r = [r for r in sel if r.get("rep", 0) == s_]
                cost_r, wall_r = {}, {}
                for b in BUCKETS + ("all",):
                    rs = [r for r in sel_r if b == "all" or r["difficulty"] == b]
                    cost_r[b] = statistics.mean(_cost(r) for r in rs) if rs else None
                    wall_r[b] = statistics.mean(r["wall_s"] for r in rs) if rs else None
                per_run[s_] = {"accuracy": acc_r, "cost": cost_r, "wall": wall_r}
            fam_out["arms"][a] = {"run": runs[a], "accuracy": acc, "cost": cost, "wall": wall, "efficiency": eff,
                                  "cost_full": cost_full, "wall_full": wall_full, "per_run": per_run}
        out[fam] = fam_out
    # efficiency averaged over the models present
    avg = {}
    for a in ARMS:
        avg[a] = {}
        for k in ("calls", "tokens_in", "tokens_out", "tokens_out_per_call"):
            vals = [out[f]["arms"][a]["efficiency"][k] for f in out if out[f]["arms"][a]["efficiency"][k] is not None]
            avg[a][k] = statistics.mean(vals) if vals else None
    return {"families": out, "efficiency_all_models": avg, "models": list(out)}


# ---------------------------------------------------------------- projects
def _autoform_rows(exp_root, run):
    sys.path.insert(0, str(HERE.parent))
    import autoform_dashboard as ad
    rows = [r for r in ad.rows_of(run) if ad._norm_task(r["task"]) in ad.TASK_IDS]
    for r in rows:
        r["_task"] = ad._norm_task(r["task"])
    return rows


def build_autoform(exp_root):
    summary = json.load(open(exp_root / "logs" / "audit_autoform" / "summary.json"))
    bad = {(d["run"], d["task"], int(d["rep"])) for d in summary["disagreements"] if d["category"] == "ext_mismatch"}
    out = {"families": {}, "excluded_ext_mismatch": sorted(bad)}
    tasks = set()
    for fam, runs in AUTOFORM_FAMILIES.items():
        out["families"][fam] = {}
        for a in ARMS:
            rows = _autoform_rows(exp_root, runs[a])
            for r in rows:
                r["_solved"] = bool(r["solved"]) and (runs[a], r["_task"], int(r.get("rep", 0))) not in bad
                tasks.add(r["_task"])
            solved = [r for r in rows if r["_solved"]]
            per_task = {t: [sum(1 for r in rows if r["_task"] == t and r["_solved"]), sum(1 for r in rows if r["_task"] == t)] for t in sorted({r["_task"] for r in rows})}
            by_run = {}
            for r in rows:
                by_run.setdefault(int(r.get("rep", 0)), []).append(r)
            acc_runs = [sum(r["_solved"] for r in rs) / len(rs) for _, rs in sorted(by_run.items())]
            sd = lambda xs: statistics.stdev(xs) if len(xs) > 1 else None
            out["families"][fam][a] = {"run": runs[a], "solved": len(solved), "n": len(rows), "accuracy": len(solved) / len(rows),
                                       "accuracy_runs": acc_runs, "accuracy_sd": sd(acc_runs),
                                       "cost_sd": sd([_cost(r) for r in solved]), "wall_sd": sd([r["wall_s"] for r in solved]),
                                       "cost": statistics.mean(_cost(r) for r in solved) if solved else None,
                                       "wall": statistics.mean(r["wall_s"] for r in solved) if solved else None,
                                       "per_task": per_task,
                                       "registered_solved": sum(bool(r["solved"]) for r in rows)}
    out["tasks"] = sorted(tasks)
    return out


# ---------------------------------------------------------------- evolution
def _run_point(exp_root, run):
    rows = _jl(exp_root / "logs" / "runs" / run / "results.jsonl")
    solved = [r for r in rows if r["solved"]]
    return {"run": run, "n": len(rows), "solved": len(solved), "accuracy": len(solved) / len(rows),
            "cost": statistics.mean(_cost(r) for r in solved) if solved else None,
            "wall": statistics.mean(r["wall_s"] for r in solved) if solved else None}


def build_evolution(exp_root):
    points = []
    for idx, label, run, dataset, verdict in EVOLUTION_RUNS:
        src = _autoform_rows(exp_root, run) if dataset == "autoform" else None
        if src is not None:
            solved = [r for r in src if r["solved"]]
            pt = {"run": run, "n": len(src), "solved": len(solved), "accuracy": len(solved) / len(src),
                  "cost": statistics.mean(_cost(r) for r in solved) if solved else None,
                  "wall": statistics.mean(r["wall_s"] for r in solved) if solved else None}
        else:
            pt = _run_point(exp_root, run)
        pt.update({"index": idx, "label": label, "dataset": dataset, "verdict": verdict})
        points.append(pt)
    deltas = []
    for label, dataset, cur_run, prv_run in DELTA_PAIRS:
        if dataset == "autoform":
            cur = {(r["_task"], r.get("rep", 0)): r for r in _autoform_rows(exp_root, cur_run)}
            prv = {(r["_task"], r.get("rep", 0)): r for r in _autoform_rows(exp_root, prv_run)}
            keys = sorted(set(cur) & set(prv))
            won = sum(bool(cur[k]["solved"]) and not prv[k]["solved"] for k in keys)
            lost = sum(bool(prv[k]["solved"]) and not cur[k]["solved"] for k in keys)
            deltas.append({"label": label, "dataset": dataset, "run": cur_run, "predecessor": prv_run, "n_slots": len(keys),
                           "buckets": None, "won": won, "lost": lost})
            continue
        cur, prv = _rows_by_slot(cur_run), _rows_by_slot(prv_run)
        reps = sorted({s for _, s in cur} & {s for _, s in prv})
        keys = [(p, s) for (p, s) in cur if s in reps and (p, s) in prv]
        per_b = {}
        for b in sorted({cur[k]["difficulty"] for k in keys}):
            ks = [k for k in keys if cur[k]["difficulty"] == b]
            per_b[b] = {"n_slots": len(ks), "won": sum(cur[k]["solved"] and not prv[k]["solved"] for k in ks),
                        "lost": sum(prv[k]["solved"] and not cur[k]["solved"] for k in ks)}
        deltas.append({"label": label, "dataset": dataset, "run": cur_run, "predecessor": prv_run, "n_slots": len(keys),
                       "reps": reps, "buckets": per_b if dataset != "mathcomp35" else None,
                       "won": sum(v["won"] for v in per_b.values()), "lost": sum(v["lost"] for v in per_b.values())})
    return {"points": points, "deltas": deltas}


# ---------------------------------------------------------------- auto-closable subset (RQ3)
AUTOCLOSE_RUN = "finisher_only_test"   # auto_close alone on the whole test split (A114)


def build_autoclose(exp_root):
    """The problems auto_close alone solves (rep 0 of AUTOCLOSE_RUN), per bucket; then, for
    every family and server, rep-0 solves on that subset and cost / wall = means over the
    server's solved attempts (both runs) on it; the "all models" row is the plain mean over
    the models present."""
    frows = _jl(exp_root / "logs" / "runs" / AUTOCLOSE_RUN / "results.jsonl")
    F = {r["problem_id"]: r["difficulty"] for r in frows if r.get("rep", 0) == 0 and r["solved"]}
    n_bucket = {b: sum(1 for r in frows if r.get("rep", 0) == 0 and r["difficulty"] == b) for b in BUCKETS}
    out = {"n": len(F), "n_total": sum(1 for r in frows if r.get("rep", 0) == 0),
           "per_bucket": {b: [sum(1 for d in F.values() if d == b), n_bucket[b]] for b in BUCKETS}, "families": {}}
    for fam, runs in MF2F_FAMILIES.items():
        out["families"][fam] = {}
        for a in ARMS:
            rows = [r for r in ft.rows_for(runs[a]) if r["problem_id"] in F]
            sol = [r for r in rows if r["solved"]]
            out["families"][fam][a] = {"solved": len(sol), "n": len(rows),
                                       "cost": statistics.mean(_cost(r) for r in sol) if sol else None,
                                       "wall": statistics.mean(r["wall_s"] for r in sol) if sol else None}
    out["all_models"] = {a: {k: statistics.mean(out["families"][f][a][k] for f in out["families"]) for k in ("cost", "wall")} for a in ARMS}
    return out


# ---------------------------------------------------------------- paired tests at the problem level
PAIRED_DEV60 = ("universal_c30_dev60", "baseline_dev60")   # final Phase-1 server vs control, four runs each


def _sign_test(k_down, n):
    """Exact two-sided sign test: probability of a split at least as unbalanced as
    (n - k_down) : k_down under p = 1/2."""
    if n == 0:
        return 1.0
    k = min(k_down, n - k_down)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def _paired(cur_rows, prv_rows):
    """Per problem, the number of solved runs under each server; a problem counts as
    better (worse) when the first server solved strictly more (fewer) runs. One unit per
    problem, so runs of the same problem are never treated as independent."""
    c, p = {}, {}
    for r in cur_rows:
        c[r["problem_id"]] = c.get(r["problem_id"], 0) + int(bool(r["solved"]))
    for r in prv_rows:
        p[r["problem_id"]] = p.get(r["problem_id"], 0) + int(bool(r["solved"]))
    keys = [k for k in c if k in p]
    better = sum(c[k] > p[k] for k in keys)
    worse = sum(c[k] < p[k] for k in keys)
    return {"problems": len(keys), "better": better, "worse": worse, "p": _sign_test(worse, better + worse)}


def build_paired(exp_root):
    out = {"dev60": dict(_paired(_jl(exp_root / "logs" / "runs" / PAIRED_DEV60[0] / "results.jsonl"),
                                 _jl(exp_root / "logs" / "runs" / PAIRED_DEV60[1] / "results.jsonl")),
                         run=PAIRED_DEV60[0], control=PAIRED_DEV60[1]),
           "minif2f": {}}
    for fam, runs in MF2F_FAMILIES.items():
        R = {a: ft.rows_for(runs[a]) for a in ARMS}
        out["minif2f"][fam] = {"vs_control": _paired(R["evolve"], R["control"]),
                               "vs_sibling": _paired(R["evolve"], R["sibling"])}
    return out


def build(exp_root):
    return {"minif2f": build_minif2f(exp_root), "autoform": build_autoform(exp_root), "evolution": build_evolution(exp_root),
            "autoclose": build_autoclose(exp_root), "paired": build_paired(exp_root)}


def main():
    ap = argparse.ArgumentParser(description="Report tables, computed from logs/.")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT)
    args = ap.parse_args()
    d = build(args.exp_root)
    for fam, rec in d["minif2f"]["families"].items():
        n = rec["n_common"]
        print(f"{fam:7s} common-solved n={n['easy']}/{n['medium']}/{n['hard']} ({n['all']})")
        for a in ARMS:
            x = rec["arms"][a]
            f3 = lambda dct, fmt: "/".join(fmt(dct[b]) for b in BUCKETS)
            print(f"   {a:8s} acc {x['accuracy']['all']:.3f} {f3(x['accuracy'], lambda v: f'{v:.2f}')} | cost {x['cost']['all']:.3f} {f3(x['cost'], lambda v: f'{v:.2f}')} "
                  f"| wall {x['wall']['all']:.0f} {f3(x['wall'], lambda v: f'{v:.0f}')} | calls {x['efficiency']['calls']:.2f} in {x['efficiency']['tokens_in']/1000:.1f}k out {(x['efficiency']['tokens_out'] or 0)/1000:.2f}k")
    print("efficiency, all models:", {a: {k: round(v, 3) if v else v for k, v in e.items()} for a, e in d["minif2f"]["efficiency_all_models"].items()})
    for fam, arms in d["autoform"]["families"].items():
        for a, x in arms.items():
            print(f"autoform {fam:7s} {a:8s} {x['solved']}/{x['n']} (registered {x['registered_solved']}) cost {x['cost']:.2f} wall {x['wall']:.0f} per task {x['per_task']}")
    for p in d["evolution"]["points"]:
        print(f"evolution {p['index']:2d} {p['label']:42s} {p['dataset']:14s} acc {100*p['accuracy']:.1f} cost {p['cost']:.3f} wall {p['wall']:.0f}")
    for x in d["evolution"]["deltas"]:
        per_b = ", ".join(f"{b} +{v['won']}-{v['lost']}" for b, v in (x["buckets"] or {}).items())
        print(f"delta {x['label']:26s} {x['dataset']:14s} +{x['won']}-{x['lost']}  {per_b}")


if __name__ == "__main__":
    main()
