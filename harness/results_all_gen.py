#!/usr/bin/env python3
"""Regenerate the unified results summary (docs/RESULTS_ALL.md, self-contained
in this repository) from this repository's campaign logs (logs/) alone, via
the producer modules under harness/results_tables/.

    python3 harness/results_all_gen.py --check                 # diff regenerated docs/RESULTS_ALL.md, exit 0 iff identical
    python3 harness/results_all_gen.py --write                 # overwrite docs/RESULTS_ALL.md
    python3 harness/results_all_gen.py OUT --write              # explicit output path
    python3 harness/results_all_gen.py --write --exp-root DIR   # explicit experiment repo root

Works from anywhere: OUT (default: docs/RESULTS_ALL.md next to this script's
own repository) is the markdown file to check or write; --exp-root (default:
this script's own repository) is the experiment repo root logs/ is read
from.

Prose paragraphs and section headers are template string constants (per the
brief); the counts a few of them cite are computed at run time and
interpolated in. Every numeric TABLE CELL is rendered at run time, either
straight from logs/ or via one call to a harness/results_tables/*.py
producer's build(exp_root) (each cached the first time it is built, since
several sections share a producer). Nothing is archived and nothing is
hand-typed.
"""
import argparse
import difflib
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent            # this repo's harness/ dir
sys.path.insert(0, str(HERE / "results_tables"))
import dev60_cap30                 # noqa: E402
import cap30_truncation            # noqa: E402
import heldout_table                # noqa: E402
import crossfam_rows as a113_rows_mod  # noqa: E402
import a115_rows as a115_rows_mod   # noqa: E402
import autoform_arms as autoform_arms_mod  # noqa: E402
import paired_tests_pooled          # noqa: E402
import finisher_partition as finisher_partition_mod  # noqa: E402
import audit_verify_rows as audit_verify_rows_mod  # noqa: E402
import rail_census                  # noqa: E402
import common_solved                # noqa: E402
import ledger                       # noqa: E402

BUCKETS = ("easy", "medium", "hard")
MF2F_N = {"easy": 130, "medium": 79, "hard": 35}   # miniF2F test buckets, §3/§3b/§5
MF2F_TOTAL = sum(MF2F_N.values())                  # 244
R2 = lambda x: round(x, 2)                         # shared bold-comparison / cell rounding
R1 = lambda x: round(x, 1)                         # out ktok (solved) bold-comparison rounding

# --------------------------------------------------------------------------
# table cache: each harness/results_tables/*.py producer is built at most
# once per exp_root, the first time a render_* function below needs it.
# --------------------------------------------------------------------------
_TABLE_CACHE = {}
FORCE = False   # --force: render even if a held-out integrity gate fails (flagged in the document)


def _cached(name, builder, exp_root):
    key = (name, str(exp_root))
    if key not in _TABLE_CACHE:
        _TABLE_CACHE[key] = builder(exp_root)
    return _TABLE_CACHE[key]


def dev60_cap30_table(exp_root):
    return _cached("dev60_cap30", dev60_cap30.build, exp_root)


def heldout_table_data(exp_root):
    return _cached("heldout_table", lambda r: heldout_table.build(r, force=FORCE), exp_root)


def a113_rows_data(exp_root):
    return _cached("a113_rows", a113_rows_mod.build, exp_root)


def a115_rows_data(exp_root):
    return _cached("a115_rows", a115_rows_mod.build, exp_root)


def autoform_arms_data(exp_root):
    return _cached("autoform_arms", autoform_arms_mod.build, exp_root)


def paired_tests_pooled_data(exp_root):
    return _cached("paired_tests_pooled", paired_tests_pooled.build, exp_root)


def finisher_partition_data(exp_root):
    return _cached("finisher_partition", finisher_partition_mod.build, exp_root)


def audit_verify_rows_data(exp_root):
    return _cached("audit_verify_rows", audit_verify_rows_mod.build, exp_root)


def common_solved_data(exp_root):
    return _cached("common_solved", common_solved.build, exp_root)


def ledger_data(exp_root):
    return _cached("ledger", ledger.build, exp_root)


# A single-cell annotation with no general rule behind it (an editorial
# footnote on a 1-solve bucket); kept as a literal suffix, not an archived
# number (the underlying wall value itself IS data-derived).
CELL_ANNOTATIONS = {
    ("sec3", "mistral", "evolve", "hard"): " (n=1)",
}

# --------------------------------------------------------------------------
# formatting helpers
# --------------------------------------------------------------------------

def cell(x):
    """Pass-rate / §2-cost style: '.NN', leading zero stripped; '1.00' at 1."""
    if x is None:
        return "—"
    s = f"{x:.2f}"
    return s[1:] if s.startswith("0.") else s


def money(x):
    """§3/§4 cost style: no zero-stripping; 2dp under 10, else 1dp."""
    if x is None:
        return "—"
    return f"{x:.2f}" if x < 10 else f"{x:.1f}"


def wall_i(x):
    if x is None:
        return "—"
    return str(round(x))


def fmt_ktok(x):
    """out ktok (solved) cell style: one decimal always, e.g. '3.2'; '—' when
    no solved attempt has an exact output-token count."""
    if x is None:
        return "—"
    return f"{x:.1f}"


def recover_frac(x, n):
    """Recover an exact k/n fraction from a value already rounded to 3dp
    (a113_rows.json / a115_rows.json / a117_look_result.json all round
    pass1/pass2/pooled to 3 decimals before archiving): round(x*n) is the
    true numerator whenever 3dp precision disambiguates it (true here for
    every n <= 244 in this document), so k/n is exact where x was not."""
    return round(x * n) / n


def pct_i(x):
    return str(round(x))


def money_round(x):
    return None if x is None else (round(x, 2) if x < 10 else round(x, 1))


def bold_best(vals, minimize=False, round_fn=None):
    """vals: one value (or None) per arm. Marks the unique argmin/argmax.
    Comparison is on the *displayed* value (round_fn), matching the "ties
    ... unmarked" convention as a reader would perceive it -- e.g. .3909
    and .3865 both print "0.39" and must tie, even though .3865 < .3909."""
    if round_fn:
        vals = [None if v is None else round_fn(v) for v in vals]
    present = [v for v in vals if v is not None]
    if len(present) < 2:
        return [False] * len(vals)
    best = min(present) if minimize else max(present)
    if present.count(best) != 1:
        return [False] * len(vals)
    return [v is not None and v == best for v in vals]


def mk(s, bold):
    return f"**{s}**" if bold else s


def pooled_meanrounded(vals):
    """§2 pooled convention: mean of the *displayed* (2dp-rounded) bucket
    fractions, re-rounded (dev60 buckets are equal-sized, so this differs
    from mean-of-raw only via double rounding -- verified against every
    pooled cell in the current table, incl. the two cases where it changes
    the last digit: mistral sibling pass@1, terra sibling pass@1)."""
    r = [round(v, 2) for v in vals]
    return round(sum(r) / len(r), 2)


def fmt_p_2sf(p):
    """Two-significant-figure p-value: scientific below 1e-2 (where a fixed
    2-decimal print would lose both figures), else fixed 2-decimal with the
    leading zero stripped. Used for every §5 p-value (A147 item 5)."""
    if p < 1e-2:
        import math
        exp = math.floor(math.log10(p))
        mant = round(p / (10 ** exp), 1)
        if mant >= 10:
            mant, exp = mant / 10, exp + 1
        return f"{mant:.1f}e{exp}"
    s = f"{p:.2f}"
    return s[1:] if s.startswith("0.") else s


def jl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def load_json(path):
    return json.load(open(path))


# --------------------------------------------------------------------------
# tokens: out ktok (solved) = mean output tokens over solved attempts, in
# thousands. Populations/reps/censoring/solved-sets are always the ones the
# row's own cost computation already uses -- every function below is called
# from inside the existing cost/wall functions (campaign_stats,
# mf2f_cost_wall, sec2_censored_rows, autoform_full_precision,
# sec3_finisher_row), never from a separate pass with its own filtering. A
# solved Claude-CLI attempt with no final usage record (usage.estimated
# True, wall-killed) has no exact output-token count and is excluded from
# the mean, counted instead (see _killed_note).
# --------------------------------------------------------------------------
_TRANSCRIPT_CACHE = {}


def _claude_transcript_sums(path):
    """Claude-code transcript.jsonl -> (tokens_in, tokens_out, had_parse_error),
    deduped by message.id (keep first occurrence) over type=="assistant"
    events. Input is exact; output is a per-message-chunk lower bound
    (disclosed in the section notes). had_parse_error flags a transcript
    with at least one unparseable line (skipped, per spec) -- used only to
    keep the consistency check (below) from asserting against a source that
    is independently corrupted on disk, never to change the token sum
    itself."""
    key = ("claude", path)
    if key in _TRANSCRIPT_CACHE:
        return _TRANSCRIPT_CACHE[key]
    tin = tout = 0
    seen = set()
    had_error = False
    try:
        fh = open(path, errors="replace")
    except OSError:
        _TRANSCRIPT_CACHE[key] = (0, 0, False)
        return (0, 0, False)
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                had_error = True
                continue
            if d.get("type") != "assistant":
                continue
            mid = d.get("message", {}).get("id")
            if mid in seen:
                continue
            seen.add(mid)
            u = d.get("message", {}).get("usage") or {}
            tin += (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                    + u.get("cache_creation_input_tokens", 0))
            tout += u.get("output_tokens", 0)
    _TRANSCRIPT_CACHE[key] = (tin, tout, had_error)
    return (tin, tout, had_error)


def claude_tokens(logs_dir, row):
    """(tokens_in, tokens_out, out_exact) for one claude-code results.jsonl
    row (a usage dict + an attempt_dir). usage.estimated False -> the
    recorded final usage (exact). usage.estimated True -> the attempt was
    wall-killed with no final usage; fall back to the transcript's deduped
    assistant-event sums (input exact, output a lower bound)."""
    u = row["usage"]
    if not u.get("estimated"):
        return (u["input_tokens"] + u["cache_read_input_tokens"] + u["cache_creation_input_tokens"],
                u["output_tokens"], True)
    tin, tout, _had_error = _claude_transcript_sums(logs_dir / row["attempt_dir"] / "transcript.jsonl")
    return (tin, tout, False)


def _mistral_transcript_sums(path, cap=None):
    """Mistral/OpenRouter transcript.jsonl -> (tokens_in, tokens_out): each
    type=="assistant" line is one model call, usage.prompt_tokens (cache
    included) / usage.completion_tokens (reasoning included) summed over all
    calls, or just the first `cap` calls (dev60 cap-30 truncation, item 4)."""
    key = ("mst", path, cap)
    if key in _TRANSCRIPT_CACHE:
        return _TRANSCRIPT_CACHE[key]
    tin = tout = n = 0
    try:
        fh = open(path, errors="replace")
    except OSError:
        _TRANSCRIPT_CACHE[key] = (0, 0)
        return (0, 0)
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
            if cap is not None and n >= cap:
                break
            u = d.get("usage") or {}
            tin += u.get("prompt_tokens", 0) or 0
            tout += u.get("completion_tokens", 0) or 0
            n += 1
    _TRANSCRIPT_CACHE[key] = (tin, tout)
    return (tin, tout)


def attempt_tokens_row(logs_dir, run, row):
    """(tokens_in, tokens_out, out_exact) for one §2/§3 results.jsonl row of
    any driver family, dispatched on the row's own fields -- claude-code
    (has "usage"), OpenRouter/terra (has "prompt_tokens" directly, exact),
    or Mistral (neither -- read its attempt transcript, exact: every call's
    usage there is a genuine completed-call total, never a lower bound)."""
    if "usage" in row:
        return claude_tokens(logs_dir, row)
    if "prompt_tokens" in row:
        return row["prompt_tokens"], row["completion_tokens"], True
    name = row.get("problem_id") or row.get("task")
    path = logs_dir / "runs" / run / "attempts" / f"{name}__rep{row.get('rep', 0)}" / "transcript.jsonl"
    tin, tout = _mistral_transcript_sums(path)
    return tin, tout, True


def _autoform_claude_tokens(path):
    """Autoform claude-code attempt transcript -> (tokens_in, tokens_out,
    out_exact): a type=="result" event (present iff the attempt completed)
    carries the final usage, exact; otherwise the deduped assistant-event
    sums (input exact, output a lower bound), same as claude_tokens."""
    key = ("afclaude", path)
    if key in _TRANSCRIPT_CACHE:
        return _TRANSCRIPT_CACHE[key]
    tin = tout = 0
    seen = set()
    result_usage = None
    try:
        fh = open(path, errors="replace")
    except OSError:
        _TRANSCRIPT_CACHE[key] = (0, 0, False)
        return (0, 0, False)
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = d.get("type")
            if t == "result":
                result_usage = d.get("usage") or {}
            elif t == "assistant":
                mid = d.get("message", {}).get("id")
                if mid in seen:
                    continue
                seen.add(mid)
                u = d.get("message", {}).get("usage") or {}
                tin += (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                        + u.get("cache_creation_input_tokens", 0))
                tout += u.get("output_tokens", 0)
    if result_usage is not None:
        out = (result_usage.get("input_tokens", 0) + result_usage.get("cache_read_input_tokens", 0)
               + result_usage.get("cache_creation_input_tokens", 0),
               result_usage.get("output_tokens", 0), True)
    else:
        out = (tin, tout, False)
    _TRANSCRIPT_CACHE[key] = out
    return out


def autoform_row_tokens(exp_root, run, row):
    """(tokens_in, tokens_out, out_exact) for one §4 (autoform) row, kind
    dispatched the same way autoform_dashboard's own rows tell the families
    apart: terra rows carry prompt_tokens directly (exact); mistral rows
    carry a "model" field and no prompt_tokens (transcript, exact); the
    remaining rows (af3_*/op_*) are the claude-code families (item 5)."""
    if "prompt_tokens" in row:
        return row["prompt_tokens"], row["completion_tokens"], True
    path = exp_root / "logs" / "autoform" / run / "attempts" / f"{row['task']}__rep{row['rep']}" / "transcript.jsonl"
    if "model" in row:
        tin, tout = _mistral_transcript_sums(path)
        return tin, tout, True
    return _autoform_claude_tokens(path)


_CONSISTENCY_STATS = {"checked": 0, "runs_checked": [], "skipped_corrupt": 0}


def _verify_claude_run_tokens(logs_dir, run):
    """Built-in consistency check (item 1): for the first 20 non-estimated
    rows of this claude-code run whose transcript parses cleanly, the
    transcript's deduped tokens_in must equal the recorded tokens_in. A row
    whose transcript.jsonl has an unparseable line (on-disk corruption --
    5/4496 attempts across every run this checks, all one run, a run of NUL
    bytes replacing a line) is skipped rather than asserted against: with a
    source known to have lost a line, exact equality cannot be verified
    either way, and skipping keeps the check meaningful (it still fires on
    a real extraction bug) without failing on independently corrupted logs."""
    rows = jl(logs_dir / "runs" / run / "results.jsonl")
    n = 0
    for r in rows:
        u = r.get("usage")
        if not u or u.get("estimated"):
            continue
        tin, _tout, had_error = _claude_transcript_sums(logs_dir / r["attempt_dir"] / "transcript.jsonl")
        if had_error:
            _CONSISTENCY_STATS["skipped_corrupt"] += 1
            continue
        recorded_tin = u["input_tokens"] + u["cache_read_input_tokens"] + u["cache_creation_input_tokens"]
        if tin != recorded_tin:
            raise AssertionError(
                f"token consistency check failed: run={run} attempt={r['attempt_dir']} "
                f"transcript tokens_in={tin} recorded tokens_in={recorded_tin}")
        n += 1
        _CONSISTENCY_STATS["checked"] += 1
        if n >= 20:
            break
    _CONSISTENCY_STATS["runs_checked"].append((run, n))


def run_token_consistency_checks(exp_root):
    logs_dir = exp_root / "logs"
    runs = (list(HAIKU_RUNS.values()) + list(SONNET_RUNS.values()) + list(FABLE_RUNS.values())
            + list(SEC3_HAIKU_RUNS.values()) + ["FINAL_frozen_wallonly"] + list(SEC3_SONNET_RUNS.values())
            + ["FINAL_pf_baseline_opus_r245", "FINAL_pf_baseline_opus",
               "FINAL_pf_rocqmcp_opus", "FINAL_pf_session2_opus"])
    for run in runs:
        _verify_claude_run_tokens(logs_dir, run)
    print(f"[tokens] consistency check: {_CONSISTENCY_STATS['checked']} rows compared across "
          f"{len(_CONSISTENCY_STATS['runs_checked'])} runs, 0 mismatches "
          f"({_CONSISTENCY_STATS['skipped_corrupt']} corrupt-transcript rows skipped)", file=sys.stderr)


def _strip_paren(s):
    """Drop a trailing ' (...)' annotation from an arm/model label, e.g.
    'evolve (A117)' -> 'evolve', 'fable (1 rep)' -> 'fable' -- used only for
    the _killed_note labels below, never a table's own display labels."""
    return s.split(" (", 1)[0]


def _killed_note(items):
    """items: (label, excluded_count) per Claude-CLI arm of one table
    (Mistral/OpenRouter arms are always exact -- their callers never append
    to items). Renders the wall-killed-solved-attempt exclusion sentence:
    every arm with >=1 exclusion, sorted by count descending (ties: the
    order items were appended in), or the literal 'none in this table' when
    no arm in the table has any."""
    present = [(label, n) for label, n in items if n]
    if not present:
        tail = "none in this table."
    else:
        present.sort(key=lambda kv: -kv[1])
        tail = ", ".join(f"{label} {n}" for label, n in present) + " (none elsewhere)."
    return ("Solved attempts that were wall-killed have no final usage record and are "
            "excluded from the output-token mean: " + tail)


# --------------------------------------------------------------------------
# §2: dev60, uniform cap-30 arena
# --------------------------------------------------------------------------
HAIKU_RUNS = {"control": "baseline_dev60", "sibling": "rocq_mcp_fair2_dev60",
              "evolve": "universal_c30_dev60"}
SONNET_RUNS = {"control": "baseline_sonnet_dev60", "sibling": "rocq_mcp_fair2_sonnet_dev60",
               "evolve": "universal_sonnet_dev60"}
FABLE_RUNS = {"control": "baseline_fable_dev60", "evolve": "universal_fable_dev60"}


def campaign_stats(exp_root, run, cap=None):
    """Per-bucket pass@1 (attempts convention)/pass@2 (first two reps)/
    $-per-solve/mean-wall-over-all-attempts, optionally cap-30-censored
    (a solve past turn 30 counts unsolved) as in dev60_cap30.py. out ktok
    (solved) (item 1/4) is the mean OUTPUT tokens, in thousands, over the
    same solved population (solved_ok) pass1/cost already use -- for cap=30
    (mistral/terra) it reads the same turn-30-truncated per-call transcripts
    (`cap` boundary) the 30-call cap `pass2` above already uses, but that
    truncation is a no-op on a solved row (num_turns <= cap by definition of
    solved_ok), so these cells carry the attempt's real, untruncated total.
    A solved Claude-CLI attempt with no final usage record (wall-killed) has
    no exact output-token count and is excluded from the mean, counted in
    killed_excluded."""
    rows = jl(exp_root / "logs" / "runs" / run / "results.jsonl")
    logs_dir = exp_root / "logs"
    by_prob, by_bucket = defaultdict(dict), defaultdict(list)
    for r in rows:
        by_prob[r["problem_id"]][r.get("rep", 0)] = r
        by_bucket[r["difficulty"]].append(r)

    def solved_ok(r):
        if not r.get("solved"):
            return False
        return cap is None or (r.get("num_turns") or 0) <= cap

    out = {}
    for b in BUCKETS:
        pids = [p for p, v in by_prob.items() if next(iter(v.values()))["difficulty"] == b]
        n, rs = len(pids), by_bucket[b]
        solved_rows = [r for r in rs if solved_ok(r)]
        solved1 = len(solved_rows)
        solved2 = sum(1 for p in pids if any(solved_ok(by_prob[p].get(rr, {})) for rr in (0, 1)))
        cost = sum(r.get("total_cost_usd") or 0 for r in rs)
        wall = sum(r["wall_s"] for r in rs) / len(rs) if rs else None
        touts = []
        killed_excluded = 0
        for r in solved_rows:
            if cap is None:
                _tin, tout, exact = claude_tokens(logs_dir, r)
            else:
                name = r.get("problem_id")
                path = logs_dir / "runs" / run / "attempts" / f"{name}__rep{r.get('rep', 0)}" / "transcript.jsonl"
                _tin, tout = _mistral_transcript_sums(path, cap=cap)
                exact = True
            if exact:
                touts.append(tout)
            else:
                killed_excluded += 1
        out_ktok = (sum(touts) / len(touts) / 1000.0) if touts else None
        out[b] = dict(pass1=solved1 / len(rs) if rs else None,
                       pass2=solved2 / n if n else None,
                       cost=(cost / solved1) if solved1 else None,
                       wall=wall, out_ktok=out_ktok, killed_excluded=killed_excluded, solved1=solved1)
    return out


def sec2_native_rows(exp_root, run_map):
    return {arm: campaign_stats(exp_root, run) for arm, run in run_map.items()}


def sec2_censored_rows(exp_root, run_map, cap30_json, family):
    """cost/wall (item 3): the turn-30-truncated per-attempt transcripts,
    summed/averaged by cap30_truncation.py -- $/solve divides by the same
    cap-30 solved count (cs30[b]["solved1"]) campaign_stats(cap=30) already
    computes for pass2/out_ktok above."""
    rows = {}
    for arm, run in run_map.items():
        cs30 = campaign_stats(exp_root, run, cap=30)
        pass1 = {b: cap30_json["families"][family][arm]["buckets"][b]["pass1_cap30"] for b in BUCKETS}
        pass2 = {b: cs30[b]["pass2"] for b in BUCKETS}
        trunc = cap30_truncation.build(exp_root, run)
        cost = {b: (trunc[b]["total_cost"] / cs30[b]["solved1"]) if cs30[b]["solved1"] else None for b in BUCKETS}
        wall = {b: trunc[b]["mean_wall"] for b in BUCKETS}
        out_ktok = {b: cs30[b]["out_ktok"] for b in BUCKETS}
        rows[arm] = {b: dict(pass1=pass1[b], pass2=pass2[b], cost=cost[b], wall=wall[b],
                              out_ktok=out_ktok[b], killed_excluded=cs30[b]["killed_excluded"])
                     for b in BUCKETS}
    return rows


def render_sec2_group(model_label, rows, arm_order, no_pass2=False):
    """rows: {arm: {bucket: {pass1,pass2,cost,wall,out_ktok,killed_excluded}}}.
    Returns (lines, killed_items): killed_items is one (label, count) pair
    per arm, count = the sum over buckets of killed_excluded, for the
    section's _killed_note."""
    if no_pass2:
        for a in arm_order:
            for b in BUCKETS:
                rows[a][b]["pass2"] = None
    lines = []
    r2 = R2
    p1_b = {b: bold_best([rows[a][b]["pass1"] for a in arm_order], round_fn=r2) for b in BUCKETS}
    cost_b = {b: bold_best([rows[a][b]["cost"] for a in arm_order], minimize=True, round_fn=r2) for b in BUCKETS}
    ktok_b = {b: bold_best([rows[a][b]["out_ktok"] for a in arm_order], minimize=True, round_fn=R1) for b in BUCKETS}
    wall_b = {b: bold_best([rows[a][b]["wall"] for a in arm_order], minimize=True, round_fn=round) for b in BUCKETS}
    pooled1 = {a: pooled_meanrounded([rows[a][b]["pass1"] for b in BUCKETS]) for a in arm_order}
    p1p_b = bold_best([pooled1[a] for a in arm_order], round_fn=r2)
    if no_pass2:
        p2_b = {b: [False] * len(arm_order) for b in BUCKETS}
        pooled2, p2p_b = {}, [False] * len(arm_order)
    else:
        p2_b = {b: bold_best([rows[a][b]["pass2"] for a in arm_order], round_fn=r2) for b in BUCKETS}
        pooled2 = {a: pooled_meanrounded([rows[a][b]["pass2"] for b in BUCKETS]) for a in arm_order}
        p2p_b = bold_best([pooled2[a] for a in arm_order], round_fn=r2)
    killed_items = []
    for i, arm in enumerate(arm_order):
        r = rows[arm]
        p1 = "/".join(mk(cell(r[b]["pass1"]), p1_b[b][i]) for b in BUCKETS)
        if all(r[b]["pass2"] is None for b in BUCKETS):
            p2 = "—"
            pooled = mk(cell(pooled1[arm]), p1p_b[i])
        else:
            p2 = "/".join(mk(cell(r[b]["pass2"]), p2_b[b][i]) for b in BUCKETS)
            pooled = f"{mk(cell(pooled1[arm]), p1p_b[i])} ({mk(cell(pooled2[arm]), p2p_b[i])})"
        costs = "/".join(mk(cell(r[b]["cost"]), cost_b[b][i]) for b in BUCKETS)
        ktoks = "/".join(mk(fmt_ktok(r[b]["out_ktok"]), ktok_b[b][i]) for b in BUCKETS)
        walls = "/".join(mk(wall_i(r[b]["wall"]), wall_b[b][i]) for b in BUCKETS)
        lines.append(f"| {model_label} | {arm} | {p1} | {p2} | {pooled} | {costs} | {ktoks} | {walls} |")
        killed_items.append((f"{_strip_paren(model_label)} {_strip_paren(arm)}",
                              sum(r[b]["killed_excluded"] for b in BUCKETS)))
    return lines, killed_items


def render_section2(exp_root):
    cap30 = dev60_cap30_table(exp_root)
    lines = []
    killed_items = []

    def group(model_label, rows, arm_order, no_pass2=False):
        gl, gk = render_sec2_group(model_label, rows, arm_order, no_pass2=no_pass2)
        lines.extend(gl)
        killed_items.extend(gk)

    group("haiku", sec2_native_rows(exp_root, HAIKU_RUNS), ["control", "sibling", "evolve"])
    lines.append("| | | | | | | | |")
    group("sonnet", sec2_native_rows(exp_root, SONNET_RUNS), ["control", "sibling", "evolve"])
    lines.append("| | | | | | | | |")
    group("fable (1 rep)", sec2_native_rows(exp_root, FABLE_RUNS), ["control", "evolve"], no_pass2=True)
    lines.append("| | | | | | | | |")
    group("mistral", sec2_censored_rows(exp_root, {"control": "mstp_base_dev60",
          "sibling": "mstp_sota_dev60_v2", "evolve": "mstp_evolve_dev60"},
          cap30, "mistral"), ["control", "sibling", "evolve"])
    lines.append("| | | | | | | | |")
    group("terra", sec2_censored_rows(exp_root, {"control": "orp_base_dev60",
          "sibling": "orp_sib_dev60", "evolve": "orp_evolve_dev60"},
          cap30, "terra"), ["control", "sibling", "evolve"])
    return "\n".join(lines), killed_items


# --------------------------------------------------------------------------
# §3: miniF2F test
# --------------------------------------------------------------------------
SEC3_HAIKU_RUNS = {"control": "FINAL_pf_baseline_haiku", "sibling": "FINAL_pf_rocqmcp_haiku",
                    "evolve (A150)": "FINAL_pf_session2_haiku"}
SEC3_HAIKU_GUIDED = ("evolve, guided phase-1 prompt (A100; not pooled, A150)", "FINAL_frozen_wallonly")
SEC3_SONNET_RUNS = {"control": "FINAL_pf_baseline_sonnet", "sibling": "FINAL_pf_rocqmcp_sonnet",
                     "evolve (A108)": "FINAL_pf_session2_sonnet"}
# A147: the opus control's coherent pair is the composite arm of
# harness/final_tables.py (rep 0 = the A142 rerun, rep 1 = registered rep 1);
# the registered July-era rep 0 is rendered on its own unbolded row.
SEC3_OPUS_RUNS = {"control": "FINAL_pf_baseline_opus_coherent", "sibling": "FINAL_pf_rocqmcp_opus",
                   "evolve (A117)": "FINAL_pf_session2_opus"}
SEC3_OPUS_REGISTERED = ("control, registered rep 0 (July era; A120/A143; not pooled)", "FINAL_pf_baseline_opus")
SEC3_PROVENANCE = [("haiku control", "FINAL_pf_baseline_haiku"), ("haiku sibling", "FINAL_pf_rocqmcp_haiku"),
                   ("haiku evolve", "FINAL_pf_session2_haiku"), ("haiku evolve, guided (A100)", "FINAL_frozen_wallonly"),
                   ("sonnet control", "FINAL_pf_baseline_sonnet"), ("sonnet sibling", "FINAL_pf_rocqmcp_sonnet"),
                   ("sonnet evolve", "FINAL_pf_session2_sonnet"),
                   ("opus control (coherent pair)", "FINAL_pf_baseline_opus_coherent"),
                   ("opus control, registered rep 0", "FINAL_pf_baseline_opus"),
                   ("opus sibling", "FINAL_pf_rocqmcp_opus"), ("opus evolve", "FINAL_pf_session2_opus")]


def heldout_arm(exp_root, run_name):
    d = heldout_table_data(exp_root)
    for a in d["arms"]:
        if a["run"] == run_name:
            return a["buckets"]
    raise KeyError(run_name)


def heldout_arm_record(exp_root, run_name):
    for a in heldout_table_data(exp_root)["arms"]:
        if a["run"] == run_name:
            return a
    raise KeyError(run_name)


def mf2f_cost_wall(exp_root, run, max_rep=None):
    """$/solve, out ktok (solved) and mean-wall-over-solved-attempts per
    bucket at full float precision, straight from results.jsonl --
    a117_look_result.json rounds latency_solved_s to 1dp, which for the opus
    control easy cell (80.5) lands exactly on a rounding tie that the
    source's true 80.52... does not have. max_rep restricts to a
    report-only registration (opus rep 0). out ktok (solved) is the mean
    OUTPUT tokens (thousands) over the same solved population (`solved`)
    $/solve and wall already use, via attempt_tokens_row (dispatched per
    driver family) -- every §3 row (including the ones whose displayed
    $/solve comes from an archived table rather than this function) draws
    its token cell from this same call, on the same run, because that
    population was verified identical to the archived cost figures before
    this column was added. A solved Claude-CLI attempt with no final usage
    record (wall-killed) is excluded from the mean, counted in
    killed_excluded."""
    # rows via heldout_table.rows_for so a composite arm key (A147, the opus
    # control's coherent pair) resolves to its assembled rows; a plain run id
    # reads its own results.jsonl exactly as before.
    rows = heldout_table.rows_for(run)
    if max_rep is not None:
        rows = [r for r in rows if r.get("rep", 0) <= max_rep]
    logs_dir = exp_root / "logs"
    by_b = defaultdict(list)
    for r in rows:
        by_b[r["difficulty"]].append(r)
    out = {}
    for b in BUCKETS:
        rs = by_b[b]
        solved = [r for r in rs if r["solved"]]
        cost = sum(r.get("total_cost_usd") or 0 for r in rs)
        touts = []
        killed_excluded = 0
        for r in solved:
            _tin, tout, exact = attempt_tokens_row(logs_dir, r.get("source_run", run), r)
            if exact:
                touts.append(tout)
            else:
                killed_excluded += 1
        out_ktok = (sum(touts) / len(touts) / 1000.0) if touts else None
        out[b] = dict(cost=(cost / len(solved)) if solved else None,
                      wall=(sum(r["wall_s"] for r in solved) / len(solved)) if solved else None,
                      out_ktok=out_ktok, killed_excluded=killed_excluded)
    return out


def sec3_finisher_row(exp_root):
    rows = jl(exp_root / "logs" / "runs" / "finisher_only_test" / "results.jsonl")
    by_b = defaultdict(list)
    for r in rows:
        by_b[r["difficulty"]].append(r)
    out = {}
    for b in BUCKETS:
        rs = by_b[b]
        solved = [r for r in rs if r["solved"]]
        wall = sum(r["wall_s"] for r in solved) / len(solved) if solved else None
        out[b] = dict(pass1=len(solved) / len(rs), pass2=None, cost=0.0, out_ktok=0.0, wall=wall, kill=0.0)
    return out


def render_sec3_row(model_label, arm_label, buckets, bold, pass2_text=None, kill_text=None,
                     ann_key=None, cost_literal=None, tokens_literal=None):
    p1 = "/".join(mk(cell(buckets[b]["pass1"]), bold["p1"][b]) for b in BUCKETS)
    if pass2_text is not None:
        p2 = pass2_text
    else:
        p2 = "/".join(mk(cell(buckets[b]["pass2"]), bold["p2"][b]) for b in BUCKETS)
    n_tot = MF2F_TOTAL
    pooled1 = sum(round((buckets[b]["pass1"] or 0) * MF2F_N[b]) for b in BUCKETS) / n_tot
    if pass2_text is None and all(buckets[b]["pass2"] is not None for b in BUCKETS):
        pooled2 = sum(round(buckets[b]["pass2"] * MF2F_N[b]) for b in BUCKETS) / n_tot
        pooled = f"{mk(cell(pooled1), bold['pooled1'])} ({mk(cell(pooled2), bold['pooled2'])})"
    else:
        pooled = mk(cell(pooled1), bold["pooled1"])
    if cost_literal is not None:
        costs = cost_literal
    else:
        costs = "/".join(mk(money(buckets[b]["cost"]), bold["cost"][b]) for b in BUCKETS)
    if tokens_literal is not None:
        ktoks = tokens_literal
    else:
        ktoks = "/".join(mk(fmt_ktok(buckets[b]["out_ktok"]), bold["out_ktok"][b]) for b in BUCKETS)

    def wcell(b):
        s = mk(wall_i(buckets[b]["wall"]), bold["wall"][b])
        if ann_key is not None:
            s += CELL_ANNOTATIONS.get(("sec3",) + ann_key + (b,), "")
        return s
    walls = "/".join(wcell(b) for b in BUCKETS)
    if kill_text is not None:
        kills = kill_text
    else:
        kills = "/".join(pct_i(buckets[b]["kill"]) for b in BUCKETS)
    return f"| {model_label} | {arm_label} | {p1} | {p2} | {pooled} | {costs} | {ktoks} | {walls} | {kills} |"


def group_bold(rows_by_arm, arm_order, has_pass2=True):
    r2 = R2
    b = {"p1": {}, "p2": {}, "cost": {}, "out_ktok": {}, "wall": {}}
    for bk in BUCKETS:
        b["p1"][bk] = bold_best([rows_by_arm[a][bk]["pass1"] for a in arm_order], round_fn=r2)
        if has_pass2:
            b["p2"][bk] = bold_best([rows_by_arm[a][bk].get("pass2") for a in arm_order], round_fn=r2)
        else:
            b["p2"][bk] = [False] * len(arm_order)
        b["cost"][bk] = bold_best([rows_by_arm[a][bk]["cost"] for a in arm_order], minimize=True, round_fn=money_round)
        b["out_ktok"][bk] = bold_best([rows_by_arm[a][bk]["out_ktok"] for a in arm_order], minimize=True, round_fn=R1)
        b["wall"][bk] = bold_best([rows_by_arm[a][bk]["wall"] for a in arm_order], minimize=True, round_fn=round)
    n_tot = MF2F_TOTAL
    pooled1 = {a: sum(round((rows_by_arm[a][b]["pass1"] or 0) * MF2F_N[b]) for b in BUCKETS) / n_tot for a in arm_order}
    b["pooled1"] = dict(zip(arm_order, bold_best([pooled1[a] for a in arm_order], round_fn=r2)))
    if has_pass2 and all(rows_by_arm[a][bk].get("pass2") is not None for a in arm_order for bk in BUCKETS):
        pooled2 = {a: sum(round(rows_by_arm[a][b]["pass2"] * MF2F_N[b]) for b in BUCKETS) / n_tot for a in arm_order}
        b["pooled2"] = dict(zip(arm_order, bold_best([pooled2[a] for a in arm_order], round_fn=r2)))
    else:
        b["pooled2"] = dict(zip(arm_order, [False] * len(arm_order)))
    return b


def resolve_bold(group, arm_order, arm):
    """Turn group_bold()'s per-bucket per-arm-index lists into the scalar
    per-bucket dict render_sec3_row() expects for one arm."""
    i = arm_order.index(arm)
    return {"p1": {b: group["p1"][b][i] for b in BUCKETS},
            "p2": {b: group["p2"][b][i] for b in BUCKETS},
            "cost": {b: group["cost"][b][i] for b in BUCKETS},
            "out_ktok": {b: group["out_ktok"][b][i] for b in BUCKETS},
            "wall": {b: group["wall"][b][i] for b in BUCKETS},
            "pooled1": group["pooled1"][arm], "pooled2": group["pooled2"][arm]}


def render_section3(exp_root):
    lines = []
    killed_items = []  # (label, count) per claude-code arm, for the _killed_note

    def bucket_killed(cw):
        return sum(cw[b]["killed_excluded"] for b in BUCKETS)

    def arm_row(key, max_rep=None):
        """One §3 row's per-bucket cells for an arm key (plain run or
        composite, A147), from the gated held-out table plus the
        full-precision cost/wall/token pass; max_rep restricts the latter
        to a report-only rep (the registered opus rep-0 row)."""
        d = heldout_arm(exp_root, key)
        cw = mf2f_cost_wall(exp_root, key, max_rep=max_rep)
        row = {}
        for b in BUCKETS:
            k, n = (int(x) for x in d[b]["kill_rate"].split("/"))
            row[b] = dict(pass1=d[b]["pass1"], pass2=d[b]["pass2"], cost=d[b]["cost_per_solve"],
                          out_ktok=cw[b]["out_ktok"], wall=d[b]["latency_solved_s"],
                          kill=(100 * k / n) if n else 0.0)
        return row, cw

    def family(model_label, runs):
        """Three-arm family block: rows bolded within the family, exactly
        the sonnet convention, now applied to haiku and opus as well
        (A147: every family at two reps)."""
        rows_by_arm = {}
        for arm, key in runs.items():
            row, cw = arm_row(key)
            killed_items.append((f"{model_label} {_strip_paren(arm)}", bucket_killed(cw)))
            rows_by_arm[arm] = row
        gb = group_bold(rows_by_arm, list(runs))
        for arm in runs:
            lines.append(render_sec3_row(model_label, arm, rows_by_arm[arm], resolve_bold(gb, list(runs), arm)))

    # haiku: control and sibling (A118, rep 1 A146) beside the wall-only evolve arm
    family("haiku", SEC3_HAIKU_RUNS)
    g_label, g_key = SEC3_HAIKU_GUIDED
    g_row, g_cw = arm_row(g_key)
    killed_items.append(("haiku evolve, guided", bucket_killed(g_cw)))
    no_bold_h = {"p1": {b: False for b in BUCKETS}, "p2": {b: False for b in BUCKETS},
                 "cost": {b: False for b in BUCKETS}, "out_ktok": {b: False for b in BUCKETS},
                 "wall": {b: False for b in BUCKETS}, "pooled1": False, "pooled2": False}
    lines.append(render_sec3_row("haiku", g_label, g_row, no_bold_h))
    lines.append("| | | | | | | | | |")

    # sonnet
    family("sonnet", SEC3_SONNET_RUNS)
    lines.append("| | | | | | | | | |")

    # opus: coherent pair for the control (A142 rerun + registered rep 1),
    # both reps for sibling and evolve; then the registered July-era
    # control rep 0 on its own unbolded row, pass@2 blank (A147).
    family("opus", SEC3_OPUS_RUNS)
    reg_label, reg_key = SEC3_OPUS_REGISTERED
    reg_row, reg_cw = arm_row(reg_key, max_rep=0)
    killed_items.append(("opus control (registered rep 0)", bucket_killed(reg_cw)))
    no_bold = {"p1": {b: False for b in BUCKETS}, "p2": {b: False for b in BUCKETS},
               "cost": {b: False for b in BUCKETS}, "out_ktok": {b: False for b in BUCKETS},
               "wall": {b: False for b in BUCKETS}, "pooled1": False, "pooled2": False}
    lines.append(render_sec3_row("opus", reg_label, reg_row, no_bold, pass2_text="—"))
    lines.append("| | | | | | | | | |")

    # mistral
    mist = a113_rows_data(exp_root)
    mist_order = ["control", "sibling", "evolve (A113, partly rail-bound)"]
    mist_key = {"control": "control", "sibling": "sibling", "evolve (A113, partly rail-bound)": "evolve"}
    mist_run = {"control": "mstf_base_test", "sibling": "mstf_sota_test",
                "evolve (A113, partly rail-bound)": "mstf_evolve_test"}
    mist_rows = {}
    for arm in mist_order:
        d = mist[mist_key[arm]]
        cw = mf2f_cost_wall(exp_root, mist_run[arm])
        mist_rows[arm] = {b: dict(pass1=recover_frac(d[b]["pass1"], MF2F_N[b]),
                                   pass2=recover_frac(d[b]["pass2"], MF2F_N[b]),
                                   cost=d[b]["cost_per_solve"], out_ktok=cw[b]["out_ktok"],
                                   wall=d[b]["latency_solved_s"], kill=d[b]["kill_pct"]) for b in BUCKETS}
    mb = group_bold(mist_rows, mist_order)
    n_tot = MF2F_TOTAL
    mb_pooled = {arm: {"pass1": recover_frac(mist[mist_key[arm]]["pooled"]["pass1"], n_tot),
                        "pass2": recover_frac(mist[mist_key[arm]]["pooled"]["pass2"], n_tot)}
                 for arm in mist_order}
    r2 = R2
    mb_p1 = dict(zip(mist_order, bold_best([mb_pooled[a]["pass1"] for a in mist_order], round_fn=r2)))
    mb_p2 = dict(zip(mist_order, bold_best([mb_pooled[a]["pass2"] for a in mist_order], round_fn=r2)))
    for arm in mist_order:
        i = mist_order.index(arm)
        row = mist_rows[arm]
        p1 = "/".join(mk(cell(row[b]["pass1"]), mb["p1"][b][i]) for b in BUCKETS)

        p2 = "/".join(mk(cell(row[b]["pass2"]), mb["p2"][b][i]) for b in BUCKETS)
        pooled = f"{mk(cell(mb_pooled[arm]['pass1']), mb_p1[arm])} ({mk(cell(mb_pooled[arm]['pass2']), mb_p2[arm])})"
        costs = "/".join(mk(money(row[b]["cost"]), mb["cost"][b][i]) for b in BUCKETS)
        ktoks = "/".join(mk(fmt_ktok(row[b]["out_ktok"]), mb["out_ktok"][b][i]) for b in BUCKETS)

        def wcell(b):
            s = mk(wall_i(row[b]["wall"]), mb["wall"][b][i])
            if mist_key[arm] == "evolve":
                s += CELL_ANNOTATIONS.get(("sec3", "mistral", "evolve", b), "")
            return s
        walls = "/".join(wcell(b) for b in BUCKETS)
        kills = "/".join(pct_i(row[b]["kill"]) for b in BUCKETS)
        lines.append(f"| mistral | {arm} | {p1} | {p2} | {pooled} | {costs} | {ktoks} | {walls} | {kills} |")
    lines.append("| | | | | | | | | |")

    # terra
    terra = a115_rows_data(exp_root)["matrix"]
    terra_order = ["control", "sibling", "evolve (A115b)"]
    terra_key = {"control": "control", "sibling": "sibling", "evolve (A115b)": "evolve"}
    terra_run = {"control": "orp_base_test", "sibling": "orp_sib_test", "evolve (A115b)": "orp_evolve_test"}
    terra_rows = {}
    for arm in terra_order:
        d = terra[terra_key[arm]]
        cw = mf2f_cost_wall(exp_root, terra_run[arm])
        terra_rows[arm] = {b: dict(pass1=recover_frac(d[b]["pass1"], MF2F_N[b]),
                                    pass2=recover_frac(d[b]["pass2"], MF2F_N[b]),
                                    cost=d[b]["cost_per_solve"], out_ktok=cw[b]["out_ktok"],
                                    wall=d[b]["latency_solved_s"], kill=d[b]["kill_pct"]) for b in BUCKETS}
    tb = group_bold(terra_rows, terra_order)
    n_tot = MF2F_TOTAL
    tb_pooled = {arm: {"pass1": recover_frac(terra[terra_key[arm]]["pooled"]["pass1"], n_tot),
                        "pass2": recover_frac(terra[terra_key[arm]]["pooled"]["pass2"], n_tot)}
                 for arm in terra_order}
    r2 = R2
    tb_p1 = dict(zip(terra_order, bold_best([tb_pooled[a]["pass1"] for a in terra_order], round_fn=r2)))
    tb_p2 = dict(zip(terra_order, bold_best([tb_pooled[a]["pass2"] for a in terra_order], round_fn=r2)))
    for arm in terra_order:
        i = terra_order.index(arm)
        row = terra_rows[arm]
        p1 = "/".join(mk(cell(row[b]["pass1"]), tb["p1"][b][i]) for b in BUCKETS)
        p2 = "/".join(mk(cell(row[b]["pass2"]), tb["p2"][b][i]) for b in BUCKETS)
        pooled = f"{mk(cell(tb_pooled[arm]['pass1']), tb_p1[arm])} ({mk(cell(tb_pooled[arm]['pass2']), tb_p2[arm])})"
        costs = "/".join(mk(money(row[b]["cost"]), tb["cost"][b][i]) for b in BUCKETS)
        ktoks = "/".join(mk(fmt_ktok(row[b]["out_ktok"]), tb["out_ktok"][b][i]) for b in BUCKETS)
        walls = "/".join(mk(wall_i(row[b]["wall"]), tb["wall"][b][i]) for b in BUCKETS)
        kills = "/".join(pct_i(row[b]["kill"]) for b in BUCKETS)
        lines.append(f"| terra | {arm} | {p1} | {p2} | {pooled} | {costs} | {ktoks} | {walls} | {kills} |")
    lines.append("| | | | | | | | | |")

    # finisher-only: single arm, cost literally "0", killed literally "0/0/0"
    fr = sec3_finisher_row(exp_root)
    solved_tot = sum(round(fr[b]["pass1"] * MF2F_N[b]) for b in BUCKETS)
    pooled1 = solved_tot / MF2F_TOTAL
    fb = {"p1": {b: False for b in BUCKETS}, "cost": {b: False for b in BUCKETS},
          "out_ktok": {b: False for b in BUCKETS}, "wall": {b: False for b in BUCKETS}, "pooled1": False}
    row = render_sec3_row("none", "finisher-only (A114)", fr, fb, pass2_text="—",
                           cost_literal="0", tokens_literal="0.0", kill_text="0/0/0")
    lines.append(row)

    return "\n".join(lines), _killed_note(killed_items)


# --------------------------------------------------------------------------
# §3b: sibling-verified pass@1
# --------------------------------------------------------------------------
SEC3B_ARMS = [
    ("haiku", "control", "FINAL_pf_baseline_haiku"),
    ("haiku", "sibling", "FINAL_pf_rocqmcp_haiku"),
    ("haiku", "evolve, guided phase-1 prompt (A100; the prompt-free A150 arm postdates the audit)", "FINAL_frozen_wallonly"),
    ("sonnet", "control", "FINAL_pf_baseline_sonnet"),
    ("sonnet", "sibling", "FINAL_pf_rocqmcp_sonnet"),
    ("sonnet", "evolve (A108)", "FINAL_pf_session2_sonnet"),
    ("opus (registered rep 0)", "control (July era, A120/A143)", "FINAL_pf_baseline_opus"),
    ("opus (registered rep 0)", "sibling", "FINAL_pf_rocqmcp_opus"),
    ("opus (registered rep 0)", "evolve (A117)", "FINAL_pf_session2_opus"),
    ("mistral", "control", "mstf_base_test"),
    ("mistral", "sibling", "mstf_sota_test"),
    ("mistral", "evolve (A113)", "mstf_evolve_test"),
    ("terra", "control", "orp_base_test"),
    ("terra", "sibling", "orp_sib_test"),
    ("terra", "evolve (A115b)", "orp_evolve_test"),
    ("none", "finisher-only (A114)", "finisher_only_test"),
]


def render_section3b(exp_root):
    d = {a["run"]: a for a in audit_verify_rows_data(exp_root)["arms"]}
    lines = []
    for model, arm, run in SEC3B_ARMS:
        a = d[run]
        n = a["n_problems"]
        reg, sem = a["registered_solves"], a["semantic_solves"]
        N = sum(n.values())
        reg1 = "/".join(cell(reg[b] / n[b]) for b in BUCKETS)
        sem1 = "/".join(cell(sem[b] / n[b]) for b in BUCKETS)
        reg_p = cell(sum(reg.values()) / N)
        sem_p = cell(sum(sem.values()) / N)
        credit = sum(sem.values()) - sum(reg.values())
        debit = a["unsound_rep0"]
        lines.append(f"| {model} | {arm} | {reg1} | {reg_p} | {sem1} | {sem_p} | +{credit} / −{debit} |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# §3c: common-solved-pair efficiency (post hoc, descriptive)
# --------------------------------------------------------------------------
SEC3C_ORDER = ("haiku", "sonnet", "opus", "mistral", "terra")
SEC3C_MODEL_LABEL = {"haiku": "haiku", "sonnet": "sonnet", "opus": "opus", "mistral": "mistral", "terra": "terra"}
SEC3C_ARM_LABEL = {
    "haiku": {"control": "control", "sibling": "sibling", "evolve": "evolve (A150)"},
    "sonnet": {"control": "control", "sibling": "sibling", "evolve": "evolve (A108)"},
    "opus": {"control": "control (A142 rerun + registered rep 1)", "sibling": "sibling", "evolve": "evolve (A117)"},
    "mistral": {"control": "control", "sibling": "sibling", "evolve": "evolve (A113)"},
    "terra": {"control": "control", "sibling": "sibling", "evolve": "evolve (A115b)"},
}


def sec3c_head(exp_root):
    d = common_solved_data(exp_root)
    dropped_txt = ", ".join(f"{fam} {d[fam]['dropped'] if d[fam]['dropped'] else 'none'}" for fam in SEC3C_ORDER)
    return f"""### 3c. Efficiency on the problems every arm solved (post hoc, descriptive)

For each family, the set below is the (problem, slot) pairs where control, sibling AND
evolve ALL solved the same problem in the same slot — slot 0 and slot 1 are the two reps
of each arm as §3 reports them (for the opus control, slot 0 is the A142 rerun and slot 1
the registered rep 1, A147; slot pairing across arms is a convention, reps being
independent draws) — so the $/solve, wall and token columns are not confounded by which
problems each arm happened to solve, unlike the pass@1-conditioned columns of §3. A pair
is dropped, and counted, when any arm's solved attempt there was wall-killed (Claude-CLI
usage.estimated true: no final usage record, hence no cost record); dropped pairs:
{dropped_txt} (mistral and terra never drop a pair — neither driver ever records a
solved attempt with no usage). Every attempt in a family's set is solved by construction,
so $/solve and wall need no failure convention here, unlike §2/§3/§4's total-cost/wall-of-
all-attempts-per-solved convention. Post hoc and descriptive: not a registered contrast.

| model | arm | $/solve e/m/h | wall s e/m/h | out ktok e/m/h |
|---|---|---|---|---|"""


def render_section3c(exp_root):
    d = common_solved_data(exp_root)
    lines = []
    for i, fam in enumerate(SEC3C_ORDER):
        rec = d[fam]
        n_str = "/".join(str(rec["n"][b]) for b in BUCKETS)
        model_label = f"{SEC3C_MODEL_LABEL[fam]} (n {n_str})"

        def v(arm, b, key):
            cell_ = rec["arms"][arm][b]
            return None if cell_ is None else cell_[key]

        cost_b = {b: bold_best([v(a, b, "cost") for a in common_solved.ARM_ORDER], minimize=True, round_fn=money_round) for b in BUCKETS}
        wall_b = {b: bold_best([v(a, b, "wall") for a in common_solved.ARM_ORDER], minimize=True, round_fn=round) for b in BUCKETS}
        ktok_b = {b: bold_best([v(a, b, "out_ktok") for a in common_solved.ARM_ORDER], minimize=True, round_fn=R1) for b in BUCKETS}
        for j, arm in enumerate(common_solved.ARM_ORDER):
            costs = "/".join(mk(money(v(arm, b, "cost")), cost_b[b][j]) for b in BUCKETS)
            walls = "/".join(mk(wall_i(v(arm, b, "wall")), wall_b[b][j]) for b in BUCKETS)
            ktoks = "/".join(mk(fmt_ktok(v(arm, b, "out_ktok")), ktok_b[b][j]) for b in BUCKETS)
            lines.append(f"| {model_label} | {SEC3C_ARM_LABEL[fam][arm]} | {costs} | {walls} | {ktoks} |")
        if i != len(SEC3C_ORDER) - 1:
            lines.append("| | | | | |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# §4: autoformalization
# --------------------------------------------------------------------------
SEC4_FAMILIES = [
    ("sonnet", [("control", "af3_base"), ("sibling", "af3_sota"), ("evolve", "af3_evolve")]),
    ("opus (2 reps)", [("control", "op_base"), ("sibling", "op_sota"), ("evolve", "op_evolve")]),
    ("mistral", [("control", "mst3_base"), ("sibling", "mst3_sota_v2"), ("evolve", "mst3_evolve")]),
    ("terra", [("control", "orp3_base"), ("sibling", "orp3_sota"), ("evolve", "orp3_evolve")]),
]


def autoform_full_precision(exp_root, run):
    """$/solve, out ktok (solved) and wall-over-solved at full float
    precision, straight from the experiment repo's own dashboard module --
    autoform_arms.json rounds these to 3/1 decimals, which lands exactly on
    a rounding knife-edge for a few current-table cells (e.g. af3_base:
    24.75/10 = 2.475 stored, but the *unrounded* total is 2.47456..., so
    %.2f of the archive's 2.475 disagrees with %.2f of the true value on
    the 2nd decimal). out ktok (solved) is the mean OUTPUT tokens (thousands)
    over the same solved rows5 population m["solved"] already counts
    (grading-corrected, via rows_of's regrades override), through
    autoform_row_tokens (dispatched per driver family). A solved Claude-CLI
    attempt whose transcript has no `result` event has no exact
    output-token count and is excluded from the mean, counted in the 4th
    return value."""
    sys.path.insert(0, str(HERE))
    import autoform_dashboard as ad
    rows = ad.rows_of(run)
    rows5 = [r for r in rows if ad._norm_task(r["task"]) in ad.TASK_IDS]
    m = ad.metrics(rows5) if rows5 else None
    if m is None:
        return (None, None, None, 0)
    solved_rows = [r for r in rows5 if r["solved"]]
    touts = []
    killed_excluded = 0
    for r in solved_rows:
        _tin, tout, exact = autoform_row_tokens(exp_root, run, r)
        if exact:
            touts.append(tout)
        else:
            killed_excluded += 1
    out_ktok = (sum(touts) / len(touts) / 1000.0) if touts else None
    return (m["cps"], m["lat"], out_ktok, killed_excluded)


def render_section4(exp_root):
    runs = autoform_arms_data(exp_root)["runs"]
    lines = []
    killed_items = []  # (label, count) per claude-code arm (sonnet/opus families)
    for fam_idx, (model, arms) in enumerate(SEC4_FAMILIES):
        arm_order = [a for a, _ in arms]
        solved = {a: runs[r]["solved"] for a, r in arms}
        n = {a: runs[r]["n"] for a, r in arms}
        precise = {a: autoform_full_precision(exp_root, r) for a, r in arms}
        cost = {a: precise[a][0] for a, _ in arms}
        out_ktok = {a: precise[a][2] for a, _ in arms}
        wall = {a: precise[a][1] for a, _ in arms}
        if fam_idx in (0, 1):  # sonnet (af3_*), opus (op_*): the claude-code families
            for a, _ in arms:
                killed_items.append((f"{_strip_paren(model)} {a}", precise[a][3]))
        b_solved = dict(zip(arm_order, bold_best([solved[a] for a in arm_order])))
        b_cost = dict(zip(arm_order, bold_best([cost[a] for a in arm_order], minimize=True, round_fn=money_round)))
        b_ktok = dict(zip(arm_order, bold_best([out_ktok[a] for a in arm_order], minimize=True, round_fn=R1)))
        b_wall = dict(zip(arm_order, bold_best([wall[a] for a in arm_order], minimize=True, round_fn=round)))
        for arm in arm_order:
            sv = mk(f"{solved[arm]}/{n[arm]}", b_solved[arm])
            cv = mk(money(cost[arm]), b_cost[arm]) if cost[arm] is not None else "—"
            kv = mk(fmt_ktok(out_ktok[arm]), b_ktok[arm]) if out_ktok[arm] is not None else "—"
            wv = mk(wall_i(wall[arm]), b_wall[arm]) if wall[arm] is not None else "—"
            lines.append(f"| {model} | {arm} | {sv} | {cv} | {kv} | {wv} |")
        if fam_idx != len(SEC4_FAMILIES) - 1:
            lines.append("| | | | | | |")
    return "\n".join(lines), _killed_note(killed_items)


# --------------------------------------------------------------------------
# §4b: re-verified solve counts
# --------------------------------------------------------------------------

def render_section4b(exp_root):
    s = load_json(exp_root / "logs" / "audit_autoform" / "summary.json")
    per_run = {r["run"]: r for r in s["per_run"]}
    disagreements = s["disagreements"]

    def ext_mismatch_count(run):
        return sum(1 for x in disagreements if x["run"] == run and x["category"] == "ext_mismatch")

    def gate_stricter_count(run):
        return sum(1 for x in disagreements if x["run"] == run and x["category"] == "gate_stricter")

    lines = []
    b, n = per_run["af3_base"]["original_solved"], per_run["af3_base"]["n"]
    lines.append(f"| sonnet | control | {b}/{n} | {b}/{n} |")
    b, n = per_run["af3_sota"]["original_solved"], per_run["af3_sota"]["n"]
    lines.append(f"| sonnet | sibling | {b}/{n} | {b}/{n} |")
    b, n = per_run["af3_evolve"]["original_solved"], per_run["af3_evolve"]["n"]
    credit = gate_stricter_count("af3_evolve")
    lines.append(f"| sonnet | evolve | {b}/{n} | {b}/{n} [{b + credit} crediting the scratch-file row] |")

    c, s6, e = (per_run[r]["original_solved"] for r in ("op_base", "op_sota", "op_evolve"))
    n10 = per_run["op_base"]["n"]
    assert all(per_run[r]["original_solved"] == per_run[r]["strict_solved"] for r in ("op_base", "op_sota", "op_evolve"))
    lines.append(f"| opus (2 reps) | control / sibling / evolve | {c} / {s6} / {e} of {n10} | unchanged |")

    n20 = per_run["mst3_base"]["n"]
    assert all(per_run[r]["original_solved"] == 0 for r in ("mst3_base", "mst3_sota_v2", "mst3_evolve"))
    lines.append(f"| mistral | all three | 0/{n20} | 0/{n20} |")

    b, n = per_run["orp3_base"]["original_solved"], per_run["orp3_base"]["n"]
    debit = ext_mismatch_count("orp3_base")
    lines.append(f"| terra | control | {b}/{n} | **{b - debit}/{n}** (both triadic solves) |")
    b, n = per_run["orp3_sota"]["original_solved"], per_run["orp3_sota"]["n"]
    lines.append(f"| terra | sibling | {b}/{n} | {b}/{n} |")
    b, n = per_run["orp3_evolve"]["original_solved"], per_run["orp3_evolve"]["n"]
    debit = ext_mismatch_count("orp3_evolve")
    lines.append(f"| terra | evolve | {b}/{n} | **{b - debit}/{n}** (triadic and prodauto solves) |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# §5: paired contrasts
# --------------------------------------------------------------------------

SEC5_FAMILIES = [("sonnet", "sonnet (A108)"), ("haiku", "haiku (A118 comparators, A150 prompt-free evolve)"),
                 ("opus", "opus (A147; control = A142 rerun)"),
                 ("mistral", "mistral (A113)"), ("terra", "terra (A115b)")]


def render_section5_table(exp_root):
    """Every p-value printed from the computed statistic (two significant
    figures, scientific below 1e-2; A147 item 5) -- the earlier generator
    carried two literal '< 1e-K' bounds for cells whose exact value is
    printed here instead."""
    d = paired_tests_pooled_data(exp_root)["families"]
    lines = []
    for fam, label in SEC5_FAMILIES:
        vc = d[fam]["pooled"]["evolve_vs_control"]
        vs = d[fam]["pooled"]["evolve_vs_sibling"]
        n_pairs = d[fam]["pooled"]["n_pairs"]
        tag = "" if n_pairs == MF2F_TOTAL else f" (INCOMPLETE: {n_pairs}/{MF2F_TOTAL} problems)"
        c1 = f"{vc['n10']}:{vc['n01']}, p = {fmt_p_2sf(vc['p'])}"
        c2 = f"{vs['n10']}:{vs['n01']}, p = {fmt_p_2sf(vs['p'])}"
        lines.append(f"| {label}{tag} | {c1} | {c2} |")
    return "\n".join(lines)


def render_section5_opus_paragraph(exp_root):
    o = paired_tests_pooled_data(exp_root)["families"]["opus_rep0"]["pooled"]
    vc, vs = o["evolve_vs_control"], o["evolve_vs_sibling"]
    return (f"Opus, registered rep-0 contrast against the July-era control (A117 report-only; kept for the\n"
            f"record, A147): evolve vs control {vc['n10']}:{vc['n01']} (p = {fmt_p_2sf(vc['p'])}); evolve vs sibling\n"
            f"{vs['n10']}:{vs['n01']} (p = {fmt_p_2sf(vs['p'])}). The control side of the first pair is the 2026-07-16\n"
            f"rep 0 (201 rows on CLI 2.1.209 + 43 on 2.1.228), which the A143 probe showed to belong to a serving\n"
            f"regime that no longer reproduces; the opus row of the table above uses the A142 rerun instead.")


# --------------------------------------------------------------------------
# §6: attribution
# --------------------------------------------------------------------------

def render_section6(exp_root):
    fp = finisher_partition_data(exp_root)
    terra_attr = a115_rows_data(exp_root)["attribution"]["evolve"]
    rows = [
        ("sonnet evolve", fp["E_total"], fp["E_and_F"], fp["E_minus_F"]),
        ("mistral evolve", fp["M_total"], fp["M_and_F"], fp["M_minus_F"]),
        ("terra evolve", terra_attr["E"], terra_attr["E_and_F"], terra_attr["model_required"]),
    ]
    lines = []
    for label, e, ef, mr in rows:
        pct = round(100 * mr / e)
        lines.append(f"| {label} | {e} | {ef} | {mr} ({pct}%) |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# static template text (verbatim sections / prose)
# --------------------------------------------------------------------------
HEADER = """# Evaluation results — all models, unified

Conventions (one set, applied to every cell, recomputed from the archived per-attempt logs):
buckets easy/medium/hard (dev60: 20/20/20; miniF2F test: 130/79/35).
Buckets: the workbook sets (dev60, dev150, hard70) use the translation's own labels —
terciles of the Lean statement's length and symbol count, a statement-shape proxy rather
than a measured difficulty (medium and hard barely separate in solve rate); the miniF2F
splits use competition tier, fixed before the first unlock (A9): mathd algebra and number
theory → easy, amc12 and the custom algebra/numbertheory/induction families → medium, aime,
imo and the shortlist → hard.
pass@1 = rep-0 solves;
pass@2 = either of the first two reps. $/solve = total cost of all attempts (failures included)
per solved attempt. out ktok (solved) = mean output tokens over solved attempts, in thousands
(the efficiency metric the brief asked to report; reasoning tokens included — the
ladder itself was decided on per-bucket solve rate, docs/DESIGN.md). wall = mean seconds over
solved attempts in the miniF2F and autoform tables; the dev60 table reports mean seconds per
attempt, failures included (its own convention, shared with the README headline table and the
campaign dashboard). killed = wall-budget kills (%).
Autoform: no buckets; solve = solved/attempts (grading-corrected), single $/solve and wall.
Bold = best arm per column position within a model group; ties and single-arm groups
unmarked. Only the current experiment per arm is shown (superseded arms, earlier
generations, and voided runs omitted)."""

SEC1_HEAD = """## 1. Development ledger (every development run, recomputed from its logs)

These are the campaign's decision-time runs, recomputed here under the same campaign
convention section 2 uses (pass@1 = solved attempts / attempts, over all reps; pass@2 =
either of the first two reps; wall = mean seconds per attempt, failures included) — so a
decision-time figure quoted in the trail may differ from the cell below it by rounding, or
because reps were added to a run after the decision was made. pass@1 and pass@2 are shown
per bucket with a pooled column; cost ($/att) and wall are per attempt, failures included
(not per solve). The turn cap of each run is shown because the development arena itself
changed during the campaign: cap 30 for the ladder, cap 50 for the universal runs (the
cap-30 universal re-run is the one section 2 reports); the team runs had no per-attempt turn
cap. Cells are not bolded here — this is a record of every run, not a comparison between
arms.

| # | run | change | manifest | reps | cap | pass@1 e/m/h | pass@2 e/m/h | pooled @1 (@2) | $/att e/m/h | wall s/att e/m/h | out ktok (solved) e/m/h | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|"""


def render_section1_table(exp_root):
    """The development-ledger table (item 1): every LEDGER row of
    harness/results_tables/ledger.py, blocks separated by a blank row and
    preceded by a bold one-line label row, no bolded cells (a record, not a
    comparison). Returns (table_text, killed_items) — killed_items feeds
    the same _killed_note() every other section's token-exclusion sentence
    uses."""
    data = ledger_data(exp_root)
    n_cols = 13
    lines = []
    killed_items = []
    for i, block in enumerate(data["blocks"]):
        if i:
            lines.append("| " + " | ".join([""] * n_cols) + " |")
        lines.append("| " + " | ".join([f"**{block['name']}**"] + [""] * (n_cols - 1)) + " |")
        for r in block["rows"]:
            b = r["buckets"]
            p1 = "/".join(cell(b[bk]["pass1"]) for bk in BUCKETS)
            p2 = "/".join(cell(b[bk]["pass2"]) for bk in BUCKETS)
            if r["pooled_pass2"] is not None:
                pooled = f"{cell(r['pooled_pass1'])} ({cell(r['pooled_pass2'])})"
            else:
                pooled = cell(r["pooled_pass1"])
            costs = "/".join(money(b[bk]["cost_att"]) for bk in BUCKETS)
            walls = "/".join(wall_i(b[bk]["wall"]) for bk in BUCKETS)
            ktoks = "/".join(fmt_ktok(b[bk]["out_ktok"]) for bk in BUCKETS)
            cap = "—" if r["cap"] is None else str(r["cap"])
            cells = [r["tag"], r["run"], r["change"], r["manifest"], str(r["reps"]), cap,
                     p1, p2, pooled, costs, walls, ktoks, r["verdict"]]
            lines.append("| " + " | ".join(cells) + " |")
            killed_items.append((f"{r['tag']} {r['run']}", r["killed_excluded"]))
    return "\n".join(lines), killed_items


def render_sec1_autoform_tail(exp_root):
    """Item 2: every autoformalization development run that is NOT a
    current arm of section 4 and not a smoke/probe run (already excluded by
    autoform_arms.build itself), as one bare 'run — solved/attempts,
    $/solve, wall s' bullet per run, no description text (the trail is the
    record of what each run was)."""
    runs = autoform_arms_data(exp_root)["runs"]
    sec4_ids = {run for _, arms in SEC4_FAMILIES for _, run in arms}

    def dollar(x):
        m = money(x)
        return m if m == "—" else f"${m}"

    def secs(x):
        w = wall_i(x)
        return w if w == "—" else f"{w} s"

    lines = []
    for run_id, rec in runs.items():
        if run_id in sec4_ids:
            continue
        lines.append(f"- {run_id} — {rec['solved']}/{rec['n']}, "
                      f"{dollar(rec.get('cost_per_solve_recovered'))}, "
                      f"{secs(rec.get('latency_over_solved_s'))}")
    return "\n".join(lines)


def sec1_tail(exp_root, killed_items):
    return f"""
{_killed_note(killed_items)}

Autoform-arc: every autoformalization development run that is not a current arm of section 4
(proposals and reruns, all reverted or superseded; $/solve and wall are computed on the
five-task set, so runs on the earlier seven- and fourteen-task sets show —), computed from
`harness/results_tables/autoform_arms.py`:

{render_sec1_autoform_tail(exp_root)}"""

SEC2_HEAD = """## 2. dev60 (uniform cap-30 arena, matching the evolve campaign)

Campaign conventions: pass@1 = solved/attempts over ALL reps; pass@2 = either of the first
two reps; wall = mean seconds per attempt (failures included). Arena is uniformly turn-cap
30: haiku rows are the native cap-30 runs; sonnet and fable rows are verified
cap-30-identical (no attempt, solved or not, ever passed 30 turns); mistral and terra rows
are counterfactually censored at turn 30 (a solve past turn 30 counts as unsolved; cost and
wall truncated at the turn-30 boundary from per-turn transcripts — exact under the
cap-invisible-to-policy assumption, the same replay technique as the turn-cap-tax
analysis). The killed column is dropped: under cap-30, terminations are predominantly
cap-outs and a wall-kill rate is not meaningful. miniF2F remains wall-only.

| model | arm | pass@1 e/m/h | pass@2 e/m/h | pooled @1 (@2) | $/solve e/m/h | out ktok (solved) e/m/h | wall s/att e/m/h |
|---|---|---|---|---|---|---|---|"""

def sec2_tail(exp_root, killed_items):
    fams = dev60_cap30_table(exp_root)["families"]
    mist_lost = "/".join(str(fams["mistral"][a]["pooled"]["solves_lost_to_censor"])
                          for a in ("control", "sibling", "evolve"))
    terra_evolve = fams["terra"]["evolve"]["pooled"]
    terra_pooled = "/".join(
        cell(pooled_meanrounded([fams["terra"][a]["buckets"][b]["pass1_cap30"] for b in BUCKETS]))
        for a in ("control", "sibling", "evolve"))
    return f"""
Cap-30 readings, descriptive: the censor barely touches the weak tiers (mistral loses
{mist_lost} solves across control/sibling/evolve) but taxes terra's long sessions — evolve
loses {terra_evolve['solves_lost_to_censor']} of {terra_evolve['solved_raw']} solves and the
pooled pass@1 ordering flips to control-first ({terra_pooled}), while evolve keeps every cost
and wall column and pass@2. The registered arena is the wall-only matrix (§3); this table is
the development arena's view. Sibling rows remain the env-bridged remeasure. For the
censored mistral and terra rows, the cost and wall are truncated at the
turn-30 boundary from the per-call transcript usage
(`harness/results_tables/cap30_truncation.py`). {_killed_note(killed_items)}"""

def sec3_head(exp_root, killed_note):
    rail = rail_census.build(exp_root, "mstf_evolve_test")
    return f"""## 3. miniF2F test (244 × 2 reps, 300 s wall, one registered look per registration)

Cost convention of this table (Claude-CLI arms): a wall-killed attempt has no cost record
and contributes zero to $/solve (`final_tables.py`: `total_cost_usd or 0`); the Mistral and
terra drivers record a cost for every attempt. Recovered-cost sonnet cells are computed at
run time by `harness/results_tables/heldout_cost_recovered.py` (same ordering, every
bucket). Every row is prompt-free (no system prompt, one rules template) except the
disclosed extra haiku row "evolve, guided phase-1 prompt": the A100 wall-only rerun of the
frozen phase-1 configuration, whose system prompt and task template prescribe tool strategy;
it is shown unbolded, enters no pooled cell and no contrast (A150), and the haiku evolve row
proper is the prompt-free arm of A150 (same server, tools and rail as the guided one). The mistral evolve arm is partly rail-bound
({rail['rail_terminated_nonsolves']}/{rail['n']} attempts ended at the cap-{rail['max_turns']}
rail, computed by `harness/results_tables/rail_census.py`; the tax falls on evolve). Kill
rates are descriptive (arena-dependent) and not bolded. Every family is reported at two reps
(A147). Haiku: control and sibling are the A118 arms, rep 0 of 2026-08 and rep 1 of 2026-09
(A146), beside the prompt-free evolve arm of 2026-09-23 (A150); the guided phase-1 evolve
row of 2026-07 is kept as the disclosed extra row above. The A144 stability probe (haiku
behaviour unchanged since July) covers the era mix. Opus: the
control's rep 0 is the A142 pinned-environment rerun (CLI 2.1.245, effort xhigh, 2026-09)
and its rep 1 the registered 2026-08-29 rep; the registered July-era rep 0 (A120, A143:
a serving regime that no longer reproduces) is shown on its own unbolded row and enters no
other cell. {killed_note}

| model | arm | pass@1 e/m/h | pass@2 e/m/h | pooled @1 (@2) | $/solve e/m/h | out ktok (solved) e/m/h | wall s e/m/h | killed % e/m/h |
|---|---|---|---|---|---|---|---|---|"""


def render_sec3_provenance(exp_root):
    """Per-arm CLI-build census of the §3 Claude rows, from each attempt's
    own init event (A147 item 6): the era structure, visible in the
    document itself."""
    lines = ["Provenance of the Claude-CLI rows above (CLI build of each attempt, from the attempts' own",
             "init events; counts are rows):", ""]
    for label, key in SEC3_PROVENANCE:
        rec = heldout_arm_record(exp_root, key)
        builds = rec.get("builds_reported") if rec.get("report_rep") is not None else rec["builds"]
        lines.append(f"- {label}: " + ", ".join(f"{v} ×{n}" for v, n in builds.items()))
    return "\n".join(lines)

SEC3B_HEAD = """### 3b. Sibling-verified pass@1 (post hoc, A121; the registered numbers above are unchanged)

Every gate-rejected artifact of every arm in §3, and every gate-solved one, was re-verified
with the sibling server's `rocq_verify` tool (rocq-mcp 0.3.1) over its real MCP interface:
6,535 artifacts, 6,385 agreements, 0 unsound solves (no gate-accepted proof the sibling
rejects for a real reason), 139 gate-stricter rows (proofs the sibling accepts and our gate
rejects: 54 helper lemmas outside the locked prefix, 46 preamble edits, 29 `Require` inside
the proof, 8 `Unset` printing flags, 2 convertible restatements), 2 sibling limitations
(gate-solved proofs the sibling cannot check, evar capture), 9 artifact-drift rows (file
rewritten after the attempt deadline, never credited). The column below adds the rep-0
gate-stricter rows to the registered rep-0 solves, per bucket, computed at run time by
`harness/results_tables/audit_verify_rows.py` (evidence `EXP/logs/audit_verify/`). It is
post hoc and direction-blind; the registered column stays
the reported one. The only arm it moves by more than one point is the sonnet sibling (+14
rep-0 solves, helper-lemma and preamble patterns the locked-prefix gate refuses), which
narrows the sonnet evolve−sibling pooled gap from .09 to .03; the terra evolve−sibling gap
is unchanged (+1 on evolve).

| model | arm | registered e/m/h | pooled | sibling-verified e/m/h | pooled | rep-0 credited / debited |
|---|---|---|---|---|---|---|"""

def sec4_head(exp_root):
    runs = autoform_arms_data(exp_root)["runs"]

    def kills(run_ids):
        vals = [runs[r]["kills_num_turns_none"] for r in run_ids]
        return str(vals[0]) if len(set(vals)) == 1 else "/".join(str(v) for v in vals)

    sonnet_k = kills(["af3_base", "af3_sota", "af3_evolve"])
    opus_k = kills(["op_base", "op_sota", "op_evolve"])
    terra_k = kills(["orp3_base", "orp3_sota", "orp3_evolve"])
    return f"""## 4. Autoformalization (5 tasks × 4 reps, 900 s wall; grading-corrected; $/solve cost-recovered)

$/solve here = total cost of ALL attempts (failures included) per solved attempt, with the
costs of wall-killed attempts recovered from per-message token usage exactly as the
experiment repo's dashboard does (A78/A79; computed at run time by
`harness/results_tables/autoform_arms.py`). The recovery prices tokens at the
claude-sonnet-5 rate table, so the opus cells are lower bounds for the killed attempts'
share. Kills (num_turns absent): sonnet {sonnet_k}, opus {opus_k}, terra {terra_k}
(killed-attempt fractions differ by more than 10 points in some pairs, so cost and wall
comparisons are censored per A71b).

| model | arm | solve | $/solve | out ktok (solved) | wall s |
|---|---|---|---|---|---|"""

def sec4_tail(killed_note):
    return f"""
Coverage notes: every miniF2F family (haiku, sonnet, opus, mistral, terra) is reported at
two reps per arm. The A120 era question is closed by the A143/A144 probes: the
July→August shift was server-side and specific to claude-opus-4-8; sonnet and haiku
reproduce their July reps today. Opus miniF2F therefore reports both reps, with the
control's coherent pair (A142 rerun + registered rep 1, A147) and the registered July-era
rep 0 kept visible but unpooled. Haiku control and sibling are the A118 arms completed
to two reps under A146; the haiku evolve arm is the prompt-free A150 arm, the guided
phase-1 row being a disclosed extra. Fable has no sibling run and 1 rep (pass@2 undefined).
Sonnet autoform control has a second current draw at 12/20 ($2.10 recovered, 693 s); the
evolve row is the shipped-config draw, the other three draws (15, 15, 14) are the
single-feature-reverted variants R1, R3, C3, not re-runs of the shipped binary.
Mistral autoform sibling is the v2 full-surface remeasure. Terra rows are post-A115c repair.
{killed_note}

### 4b. Re-verified solve counts (post hoc, A130/A131; the registered cells above are unchanged)

All 462 attempts of the 29 archived runs were re-graded in fresh sandboxes by an independent
checker (assumptions of every probe read through the Rocq API, where the original grader
parses `Print Assumptions` text and would miss a `#[bypass_check]` definition; none was
found) and by REFERENCE-DERIVED EXTENDED PROBES: hundreds to thousands of concrete
instances per required name with expected values computed from each task's gate-validated
reference, plus non-vacuity witnesses (`EXP/data/autoform/<task>/audit/`, evidence
`EXP/logs/audit_autoform/`). Outcome: 0 gate-unsound rows (no gate solve fails the strict
checker), 2 gate-stricter rows (a scratch file with `Abort`/`Admitted` that no probe uses;
credited below, bracketed), 4 extended-probe failures, all terra, all verified in the
sources: the three triadic solves define `tstep` by cases on the probe inputs 12/15/27/30
and return junk elsewhere; the terra evolve prodauto solve defines `trace` as a constant
two-element list, which makes the pumping theorem trivially true. Six further terra triadic
attempts tried `Unset Guard Checking` and were rejected by both graders. A mutation
analysis of the references found 16 wrong formalizations the shipped probes accept
(frugal 5, gauges 2, ledger 2, prodauto 4, triadic 3, each with a checked killing probe):
the probes pin a handful of literal inputs. Every solved attempt of every Claude and
Mistral arm passes the extended probes.

| model | arm | registered | re-verified |
|---|---|---|---|"""

SEC4B_TAIL = """
Sonnet control draw 2 (12), the reverted variants R1/R3/C3 (15/15/14) and every historical
arena row are unchanged. The sonnet ordering and margins stand; the terra ordering stands
with a smaller spread (evolve 10, control 8, sibling 7)."""

SEC5_HEAD = """## 5. Registered paired contrasts, miniF2F (pooled exact McNemar, rep-0, Holm per family)

| family | evolve vs control | evolve vs sibling |
|---|---|---|"""

SEC6_HEAD = """## 6. Attribution (A114 zero-model finisher, F = 52/244)

| arm | rep-0 solves E | E∩F | model-required (E\\F) |
|---|---|---|---|"""

SEC7 = """## 7. Hardest autoform tasks, all-time record

- prodauto: among the arms of §4, sonnet evolve 3/4, sonnet control draw 2 1/4, terra evolve
  1/4, no other; across the four sonnet evolve-family draws 12/16 (`autoform_arms.json`
  all_time: 21/95 over every archived non-smoke run, including superseded arenas). The terra
  evolve solve is a degenerate `trace` (A131, §4b), so re-verified: 20/95 all-time and 0 at
  terra; every sonnet prodauto solve passes the extended probes.
- triadic (olympiad): 0/55 across all Claude and Mistral arms through the A103 count and
  none in the 16 mistral-large attempts since (0/70 non-terra in `autoform_arms.json`); terra
  3/12 by the gate (control 2/4, evolve 1/4; solved walls 249–416 s of the 900 s budget) —
  BUT all three gate-passing terra submissions hardcode `tstep` on the probes' literal
  inputs (A130, verified in the sources; §4), so no arm, tier or family has formalized
  triadic: 0/82 all-time on the semantic column. The gate count stays the registered
  number; any sentence reading "terra solved triadic" must carry this caveat."""

def revisions():
    return """---

Revision 2026-09-02 (blueprint archive pass): §3 conventions paragraph added (cost
convention, guided haiku row, mistral rail, kill rates unbolded); opus rows relabelled rep 0
with pass@2 withheld [superseded 2026-09-17: opus pass@2 is reported]; finisher-only wall
cell corrected from "2/4/9" (no traceable source) to the log means 1.4/1.1/1.5 s printed as
1/1/2; §4 $/solve cells regenerated under the recovered-cost convention (previous raw cells:
sonnet 1.56/1.86/1.17, opus 2.19/2.06/1.89, base2 1.18) with bold recomputed; coverage
notes corrected (haiku comparators run and withheld [superseded 2026-09-17: reported];
opus rep 1 exists); §5 opus note carries the CLI-version tag; §7 counts scoped.
Every number is computed at run time from `logs/` by `harness/results_all_gen.py` and the
modules under `harness/results_tables/`; nothing is archived or typed.

Revision 2026-09-04 (audit pass): §3 opus control easy pass@1 corrected from `.79` to `.78`
(102/130 = .785 at rep 0 of FINAL_pf_baseline_opus; a typed slip also present in the
case-study section, LINEAGE_AUDIT.md); 2026-09-06: §3 sonnet evolve (A108) medium pass@2
likewise `.79` → `.78` (62/79 = .785; the same two slips LINEAGE_AUDIT.md lists for the
case-study section, caught here by the repaired `EXP/harness/final_tables.py`); §3 mistral
control easy pass@2 `.21` → `.22` (28/130 = .215, per `a113_rows.json` and the raw log,
caught by `tables/results_all_gen.py`, which now regenerates this whole file); every other §3 pass@1 and pooled cell re-derived
from results.jsonl by `tables/audit_verify_rows.py` and found identical. §3b added (A121
sibling-verified column). §4b added (A130/A131 re-verified solve counts over all 462
attempts) and §7 caveats added: the three terra triadic gate solves are hardcoded on the
probe inputs and the terra evolve prodauto solve has a degenerate `trace`; registered
cells unchanged.

Revision 2026-09-08: generator moved to the experiment repo (harness/results_all_gen.py);
table and output locations are now arguments; one phrase reworded (§2, replay technique),
no cell changed.

Revision 2026-09-08 (tokens): Mtok/solve column added to sections 2, 3 and 4 (definition in
the conventions; killed-attempt caveat in the section notes); every pre-existing cell
unchanged.

Revision 2026-09-08 (self-contained): the summary regenerates from the experiment repository
alone — archived table inputs under docs/results_tables (registered snapshots; provenance in
its README), producers under harness/results_tables, default output docs/RESULTS_ALL.md;
prose paths updated, no cell changed.

Revision 2026-09-08 (logs + scripts only): every table is computed at run time from the
campaign logs by the modules under harness/results_tables; the archived table JSONs and the
six hand-typed cap-30 cost/wall cells are gone (those cells are now derived from the
per-call transcripts, a turn ending when its tool result is back). All twelve reproduce the
previously typed values.

Revision 2026-09-09 (output tokens): the token column now reports the campaign's efficiency
objective, mean output tokens over solved attempts (out ktok (solved)), replacing the
total-token Mtok/solve figure, which counted cache reads at full weight and tracked context
volume rather than model output; wall-killed solved attempts (no final usage) are excluded
and counted in the section notes; every other cell unchanged.

Revision 2026-09-09 (common-solved efficiency): §3c added — cost, wall and output tokens
per arm restricted to the (problem, rep) pairs every arm of the family solved; no other cell
changed.

Revision 2026-09-09 (development ledger): section 1 is now a computed ledger of every
development run (harness/results_tables/ledger.py), replacing the decision-time prose;
bucket definitions added to the conventions; no other cell changed.

Revision 2026-09-17 (matrix completion, A142/A146/A147): every miniF2F family is reported
at two reps. The haiku control and sibling arms (A118, completed to two reps under A146)
enter §3, §3b, §3c and §5; the opus control is reported on its coherent pair (rep 0 = the
A142 pinned-environment rerun, rep 1 = the registered 2026-08-29 rep) with pass@2, and its
registered July-era rep 0 stays visible on an unbolded row that enters no other cell
(A120/A143); opus evolve and sibling report both reps; §5 gains the haiku (A118) and opus
(A147) rows and prints every p-value from the computed statistic (the two literal bounds
of the previous generator became exact values); a per-arm CLI-build provenance list
follows the §3 table; coverage notes rewritten. No sonnet, mistral, terra or autoform cell
changed.

Revision 2026-09-24 (A150, prompt uniformity): the haiku evolve row is now the prompt-free
arm FINAL_pf_session2_haiku (af_pf_session2 with the haiku model and the family's cap-200
rail; frozen server), so every family of §3 has three prompt-free arms; the guided phase-1
row (A100) stays as a disclosed, unbolded extra that enters no pooled cell and no contrast;
§3c and the §5 haiku contrast use the prompt-free arm; §3b keeps the guided row as the
audited one. Conventions: output tokens described as the reported efficiency metric, not an
optimized objective. No sonnet, opus, mistral, terra or autoform cell changed.

Revision 2026-09-25 (report tables, A152): section 8 added — the tables of the external
write-up (common-solved cost/wall, efficiency, project-scale, evolution points, per-mutation
deltas) computed by harness/results_tables/report_tables.py under one stated convention each;
no other section changed. Same day (A153): section 8 moved out to its own document,
docs/REPORT_TABLES.md (harness/report_tables_gen.py), which carries only the presented tables
and the runs behind them; this document keeps sections 1-7 unchanged."""


def build_document(exp_root):
    run_token_consistency_checks(exp_root)
    sec1_table, sec1_killed_items = render_section1_table(exp_root)
    sec2_lines, sec2_killed_items = render_section2(exp_root)
    sec3_lines, sec3_killed_note = render_section3(exp_root)
    sec4_lines, sec4_killed_note = render_section4(exp_root)
    parts = [
        HEADER, "",
        SEC1_HEAD,
        sec1_table,
        sec1_tail(exp_root, sec1_killed_items), "",
        SEC2_HEAD,
        sec2_lines,
        sec2_tail(exp_root, sec2_killed_items), "",
        sec3_head(exp_root, sec3_killed_note),
        sec3_lines, "",
        render_sec3_provenance(exp_root), "",
        SEC3B_HEAD,
        render_section3b(exp_root), "",
        sec3c_head(exp_root),
        render_section3c(exp_root), "",
        sec4_head(exp_root),
        sec4_lines,
        sec4_tail(sec4_killed_note),
        render_section4b(exp_root),
        SEC4B_TAIL, "",
        SEC5_HEAD,
        render_section5_table(exp_root), "",
        render_section5_opus_paragraph(exp_root), "",
        SEC6_HEAD,
        render_section6(exp_root), "",
        SEC7, "",
        revisions(),
    ]
    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate the unified results summary from this repository's logs "
                     "alone, via the producer modules under harness/results_tables/.")
    parser.add_argument("out", type=Path, nargs="?", default=HERE.parent / "docs" / "RESULTS_ALL.md",
                         help="markdown file to check or write "
                              "(default: docs/RESULTS_ALL.md next to this repository)")
    parser.add_argument("--exp-root", type=Path, default=HERE.parent,
                         help="experiment repo root (default: parent of this script's "
                              "own directory)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                       help="diff the regenerated document against out, exit 0 iff identical")
    mode.add_argument("--write", action="store_true",
                       help="overwrite out with the regenerated document")
    parser.add_argument("--force", action="store_true",
                         help="render even if a held-out integrity gate fails (incomplete or "
                              "unclean arm); the document then opens with a FORCED PREVIEW "
                              "banner listing the failures and must not be released")
    args = parser.parse_args()
    global FORCE
    FORCE = args.force

    try:
        doc = build_document(args.exp_root)
    except heldout_table.GateFailure as e:
        print("REFUSING to regenerate: the held-out table's integrity gates failed "
              "(harness/final_tables.py, via harness/results_tables/heldout_table.py):")
        for f in e.failures:
            print("  -", f)
        print("\nFix per the runbook (quarantine + redo, never edit), or --force to preview (flagged).")
        sys.exit(1)
    failures = heldout_table_data(args.exp_root).get("gate_failures") or []
    if failures:
        banner = ("> **FORCED PREVIEW — integrity gates failing; not a release of this document:**\n"
                  + "".join(f"> - {f}\n" for f in failures) + "\n")
        doc = banner + doc
        print("!! FORCED PREVIEW — gates failing:", *failures, sep="\n!!   ", file=sys.stderr)

    if args.write:
        args.out.write_text(doc)
        print(f"wrote {args.out}")
        return
    old = args.out.read_text()
    if old == doc:
        print("IDENTICAL")
        sys.exit(0)
    diff = difflib.unified_diff(old.splitlines(keepends=True), doc.splitlines(keepends=True),
                                 fromfile=str(args.out), tofile="regenerated")
    sys.stdout.writelines(diff)
    sys.exit(1)


if __name__ == "__main__":
    main()
