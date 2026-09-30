#!/usr/bin/env python3
# New module (2026-09-09): backs RESULTS_ALL §1 (development ledger,
# replacing the decision-time prose ablation table).
"""Every development run of the evolution campaign, as a labelled row,
recomputed from its own logs/runs/<run>/{results.jsonl,run_meta.json} --
including runs on manifests other than dev60 (dev150, hard70, decomposable,
minif2f_valid) and the sonnet/fable policy-neutrality runs. LEDGER below is
the fixed, hand-maintained list of (block, tag, run_id, change_label,
verdict) rows the campaign trail records; nothing about a row's own numbers
is typed here -- every number in the returned dict is read or computed from
the run's own logs.

Per bucket (easy/medium/hard), mirrors results_all_gen.py's campaign_stats
(§2) exactly for pass@1/pass@2/out ktok (solved), duplicated locally rather
than imported -- results_all_gen.py imports every harness/results_tables/*
module at load time, so a module here importing back would be a circular
partial import; this directory's existing convention (see common_solved.py,
cap30_truncation.py) is to mirror the needed slice locally instead:
  - pass@1 = solved attempts / attempts, over ALL reps.
  - pass@2 = problems solved in rep 0 or rep 1, / problems.
  - out ktok (solved) = mean OUTPUT tokens (thousands) over solved attempts;
    a solved attempt with an exact final usage record (usage.estimated
    False) counts that record; one wall-killed (usage.estimated True, no
    final usage) falls back to its own transcript.jsonl's deduped
    assistant-event output-token sum (a lower bound) and is also counted in
    killed_excluded, exactly as claude_tokens/_claude_transcript_sums do.
  - every run in this ledger is a Claude-CLI run (haiku, sonnet or fable),
    so no other driver's token dispatch is needed here.
$/att is a DIFFERENT convention from every other cost cell in this
document (which are all $/solve): harness/report.py's own bucket_stats
convention, `m("total_cost_usd", rows)` -- the mean total_cost_usd per
attempt over attempts that HAVE a cost record (isinstance float/int),
failures included; this is a development-ledger column, not a $/solve
column, so it is computed independently of the pass@1/out-ktok population
above. wall s/att = mean wall_s over ALL attempts (the §2 dev60-table
convention, not the §3/§4 solved-only convention).

pooled pass@1 / pass@2: the mean of the *rounded* per-bucket values (§2's
pooled_meanrounded convention), over only the buckets that have attempts --
degenerates to that single bucket's own value for hard70 (hard only); for
dev60 (equal 20/20/20 buckets) this is the same convention §2 already uses.

reps = the number of distinct `rep` values seen in the run's own
results.jsonl (not run_meta's declared "reps", though the two agree in
every run here). cap = run_meta["config"]["max_turns"] (absent -- None --
for the two team runs, which had no per-attempt turn cap; rendered "--" by
the generator). manifest = run_meta["manifest"]. model = the rows' own
"model" field.

A bucket with no attempts (hard70 has only hard; every other manifest here
has all three) renders every one of its fields None -- the generator's
existing cell()/money()/wall_i()/fmt_ktok() formatters already print "--"
for None, so no separate handling is needed downstream.

    python3 ledger.py [<experiment_repo_root>]
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
BUCKETS = ("easy", "medium", "hard")

LEDGER = [
    ("ladder (haiku, dev60)", [
        ("0", "baseline_dev60", "naive whole-file check", "control"),
        ("1", "session_dev60",
         "session: persistent in-process, sentence steps, rollback", "KEPT"),
        ("2", "session_try_dev60",
         "+ try (k candidates per call, first success commits)", "KEPT"),
        ("3", "session_try_compact_dev60",
         "+ compact rendering (hypothesis deltas)", "REVERTED"),
        ("4", "session_try_search_dev60", "+ search tool (pull-based)", "REVERTED"),
        ("5", "session_try_hints_dev60",
         "+ hints (Lean-ism → Rocq rewrites in errors)", "KEPT"),
        ("6", "session_try_hints_auto_dev60",
         "+ auto_close (server-side finisher portfolio)", "KEPT"),
        ("7", "session_try_hints_auto_sugg_dev60",
         "+ did-you-mean (near-miss names, push-based)",
         "KEPT (this is the frozen winner's tool set)"),
        ("8", "unified_dev60", "draft-first / repair-from-failure prompting", "REVERTED"),
        ("9a", "winner_autofix_dev60",
         "auto_close requires real progress (bug fix)", "fix"),
        ("9b", "winner_auto2_dev60", "+ hint-term synthesis", "KEPT"),
        ("10", "universal_dev60",
         "universal (recommended configuration), cap 50", "selected"),
        ("10c", "universal_c30_dev60",
         "universal, re-run at cap 30 (A101 arena)", "selected"),
    ]),
    ("confirmation on other development data (haiku)", [
        ("2c", "session_try_dev150",
         "try configuration on dev150 (disjoint workbook problems)", "confirmation"),
        ("5v", "session_try_hints_minif2f_valid",
         "hints configuration on the miniF2F valid split, before environment v2",
         "evidence for v2"),
        ("5v2", "session_try_hints_v2_minif2f_valid",
         "same, under environment v2 (preload Lia/Lra/Psatz, refuse mid-proof Require)",
         "KEPT (v2)"),
    ]),
    ("team pattern (haiku)", [
        ("T1", "solo_hard70",
         "solo winner on hard70 (the hard problems of dev60 and dev150)", "reference"),
        ("T2", "team_k3_hard70",
         "three-agent team on hard70, equal total wall", "REVERTED"),
        ("T3", "solo_decomposable", "solo winner on the decomposable manifest", "reference"),
        ("T4", "team_decomposable",
         "three-agent team on the decomposable manifest", "REVERTED"),
    ]),
    ("policy-neutrality selection (sonnet and fable, dev60)", [
        ("S0", "baseline_sonnet_dev60", "naive whole-file check", "control"),
        ("S7", "session_try_hints_auto_sonnet_dev60", "winner tool set", "measured"),
        ("S8", "unified_sonnet_dev60", "draft-first prompting", "superseded by universal (A24)"),
        ("Sn", "sonnet_native_dev60", "native style, cap 50", "measured"),
        ("Sn2", "sonnet_native_auto2_dev60", "native style + synthesis, cap 50", "measured"),
        ("S10", "universal_sonnet_dev60", "universal, cap 50", "selected"),
        ("F0", "baseline_fable_dev60", "naive whole-file check", "control"),
        ("F10", "universal_fable_dev60", "universal, cap 50", "selected"),
    ]),
]


def _jl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def _transcript_out_tokens(path):
    """Deduped (by message.id) sum of assistant-event usage.output_tokens
    over one claude-code attempt transcript -- mirrors
    results_all_gen.py's _claude_transcript_sums (output half only; this
    module never needs input tokens)."""
    tout = 0
    seen = set()
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
            mid = d.get("message", {}).get("id")
            if mid in seen:
                continue
            seen.add(mid)
            u = d.get("message", {}).get("usage") or {}
            tout += u.get("output_tokens", 0)
    return tout


def _out_tokens(logs_dir, row):
    """(tokens_out, exact) for one claude-code results.jsonl row -- mirrors
    results_all_gen.py's claude_tokens: usage.estimated False -> the
    recorded final usage (exact); True -> the wall-killed attempt's own
    transcript.jsonl, deduped assistant-event sum (a lower bound)."""
    u = row["usage"]
    if not u.get("estimated"):
        return u["output_tokens"], True
    path = logs_dir / row["attempt_dir"] / "transcript.jsonl"
    return _transcript_out_tokens(path), False


def _bucket_stats(rows, logs_dir):
    by_prob, by_bucket = defaultdict(dict), defaultdict(list)
    for r in rows:
        by_prob[r["problem_id"]][r.get("rep", 0)] = r
        by_bucket[r["difficulty"]].append(r)

    out = {}
    for b in BUCKETS:
        pids = [p for p, v in by_prob.items() if next(iter(v.values()))["difficulty"] == b]
        n, rs = len(pids), by_bucket[b]
        solved_rows = [r for r in rs if r.get("solved")]
        solved1 = len(solved_rows)
        solved2 = sum(1 for p in pids
                      if any((by_prob[p].get(rr) or {}).get("solved") for rr in (0, 1)))
        costed = [r["total_cost_usd"] for r in rs if isinstance(r.get("total_cost_usd"), (int, float))]
        cost_att = sum(costed) / len(costed) if costed else None
        wall = sum(r["wall_s"] for r in rs) / len(rs) if rs else None
        touts, killed_excluded = [], 0
        for r in solved_rows:
            tout, exact = _out_tokens(logs_dir, r)
            if exact:
                touts.append(tout)
            else:
                killed_excluded += 1
        out_ktok = (sum(touts) / len(touts) / 1000.0) if touts else None
        out[b] = dict(pass1=solved1 / len(rs) if rs else None,
                       pass2=solved2 / n if n else None,
                       cost_att=cost_att, wall=wall, out_ktok=out_ktok,
                       killed_excluded=killed_excluded,
                       attempts=len(rs), solved1=solved1, problems=n)
    return out


def _pooled(bstats, key):
    vals = [round(bstats[b][key], 2) for b in BUCKETS if bstats[b][key] is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def build(exp_root):
    """{"blocks": [{"name": str, "rows": [row, ...]}, ...]}; each row:
    tag, run, change, verdict, manifest, model, reps, cap,
    buckets ({bucket: {pass1,pass2,cost_att,wall,out_ktok,killed_excluded,
    attempts,solved1,problems}}), pooled_pass1, pooled_pass2,
    killed_excluded (summed over buckets)."""
    logs_dir = exp_root / "logs"
    blocks = []
    for block_name, rows_spec in LEDGER:
        block_rows = []
        for tag, run_id, change, verdict in rows_spec:
            run_dir = logs_dir / "runs" / run_id
            rows = _jl(run_dir / "results.jsonl")
            meta = json.load(open(run_dir / "run_meta.json"))
            bstats = _bucket_stats(rows, logs_dir)
            reps = sorted({r.get("rep", 0) for r in rows})
            model = rows[0]["model"] if rows else None
            block_rows.append(dict(
                tag=tag, run=run_id, change=change, verdict=verdict,
                manifest=meta.get("manifest"), model=model, reps=len(reps),
                cap=meta.get("config", {}).get("max_turns"),
                buckets=bstats,
                pooled_pass1=_pooled(bstats, "pass1"),
                pooled_pass2=_pooled(bstats, "pass2"),
                killed_excluded=sum(bstats[b]["killed_excluded"] for b in BUCKETS),
            ))
        blocks.append({"name": block_name, "rows": block_rows})
    return {"blocks": blocks}


def main():
    ap = argparse.ArgumentParser(description="Development ledger (RESULTS_ALL §1).")
    ap.add_argument("exp_root", nargs="?", type=Path, default=DEFAULT_ROOT,
                     help="experiment repo root (default: this repository)")
    args = ap.parse_args()
    out = build(args.exp_root)
    for block in out["blocks"]:
        print(f"## {block['name']}")
        for r in block["rows"]:
            p1 = "/".join("--" if r["buckets"][b]["pass1"] is None else f"{r['buckets'][b]['pass1']:.2f}"
                           for b in BUCKETS)
            print(f"  {r['tag']:4s} {r['run']:32s} manifest={r['manifest']:14s} reps={r['reps']} "
                  f"cap={r['cap']} pass1={p1} pooled1={r['pooled_pass1']} verdict={r['verdict']}")


if __name__ == "__main__":
    main()
