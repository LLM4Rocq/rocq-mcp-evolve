#!/usr/bin/env python3
"""Regenerate docs/REPORT_TABLES.md: only the tables of the write-up, computed from
this repository's campaign logs (logs/) by harness/results_tables/report_tables.py.

    python3 harness/report_tables_gen.py --check                 # diff regenerated docs/REPORT_TABLES.md, exit 0 iff identical
    python3 harness/report_tables_gen.py --write                 # overwrite docs/REPORT_TABLES.md
    python3 harness/report_tables_gen.py OUT --write              # explicit output path
    python3 harness/report_tables_gen.py --write --exp-root DIR   # explicit experiment repo root

docs/RESULTS_ALL.md (harness/results_all_gen.py) is the exhaustive audit
document; this one carries exactly the cells the write-up presents, one
stated convention each, and the run each cell is computed from. The
formatting helpers (cell rounding, bold-best rule) are shared with
results_all_gen.py so that a number common to both documents is rendered
identically. The same integrity gates apply: the held-out arms must be
complete and clean or the generator refuses to write.
"""
import argparse
import difflib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "results_tables"))
import results_all_gen as rag                       # noqa: E402  (shared formatting helpers)
import heldout_table                                 # noqa: E402  (integrity gates)
import report_tables                                 # noqa: E402
import final_tables as ft                            # noqa: E402

BUCKETS = rag.BUCKETS
MF2F_N = rag.MF2F_N
cell, mk, bold_best, wall_i, money, money_round, pct_i = (
    rag.cell, rag.mk, rag.bold_best, rag.wall_i, rag.money, rag.money_round, rag.pct_i)
R2 = rag.R2

MODELS = (("haiku", "Haiku"), ("sonnet", "Sonnet"), ("opus", "Opus"), ("terra", "Terra"))
ARMS = (("control", "control"), ("sibling", "rocq-mcp"), ("evolve", "rocq-mcp-evolve"))
ARM_KEYS = [a for a, _ in ARMS]

_DATA = {}


def data(exp_root):
    if "d" not in _DATA:
        heldout_table.build(exp_root, force=False)   # raises GateFailure on an incomplete/unclean arm
        _DATA["d"] = report_tables.build(exp_root)
    return _DATA["d"]


# --------------------------------------------------------------------------
# run inventory
# --------------------------------------------------------------------------

def render_inventory(exp_root):
    lines = ["| block | model | control | rocq-mcp | rocq-mcp-evolve | reps |", "|---|---|---|---|---|---|"]
    for fam, label in MODELS:
        runs = report_tables.MF2F_FAMILIES[fam]
        cells = []
        for a in ARM_KEYS:
            key = runs[a]
            if key in ft.COMPOSITE:
                cells.append(" + ".join(f"`{r}` rep {rep}" for r, rep, _ in ft.COMPOSITE[key]))
            else:
                cells.append(f"`{key}`")
        lines.append(f"| miniF2F test | {label} | {' | '.join(cells)} | 2 |")
    for fam, label in (("sonnet", "Sonnet"), ("opus", "Opus"), ("terra", "Terra")):
        runs = report_tables.AUTOFORM_FAMILIES[fam]
        reps = data(exp_root)["autoform"]["families"][fam]["control"]["n"] // len(data(exp_root)["autoform"]["tasks"])
        lines.append(f"| projects | {label} | {' | '.join(f'`{runs[a]}`' for a in ARM_KEYS)} | {reps} |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# miniF2F
# --------------------------------------------------------------------------

def _mf2f_rows(exp_root, cost_key, wall_key):
    d = data(exp_root)["minif2f"]["families"]
    lines = []
    for fam, label in MODELS:
        rec = d[fam]; n = rec["n_common"]; arms = rec["arms"]
        bold = {}
        for metric, minimize, rf in (("accuracy", False, R2), (cost_key, True, R2), (wall_key, True, round)):
            for b in BUCKETS + ("all",):
                flags = bold_best([arms[a][metric][b] for a in ARM_KEYS], minimize=minimize, round_fn=rf)
                bold[(metric, b)] = {a for a, f in zip(ARM_KEYS, flags) if f}
        for a, alabel in ARMS:
            x = arms[a]
            acc = f"{mk(cell(x['accuracy']['all']), a in bold[('accuracy','all')])} ({'/'.join(mk(cell(x['accuracy'][b]), a in bold[('accuracy', b)]) for b in BUCKETS)})"
            cst = f"{mk(cell(x[cost_key]['all']), a in bold[(cost_key,'all')])} ({'/'.join(mk(cell(x[cost_key][b]), a in bold[(cost_key, b)]) for b in BUCKETS)})"
            wl = f"{mk(wall_i(x[wall_key]['all']), a in bold[(wall_key,'all')])} ({'/'.join(mk(wall_i(x[wall_key][b]), a in bold[(wall_key, b)]) for b in BUCKETS)})"
            model_cell = f"{label} ({n['easy']}/{n['medium']}/{n['hard']})" if cost_key == "cost" else label
            lines.append(f"| {model_cell} | {alabel} | {acc} | {cst} | {wl} |")
    return "\n".join(lines)


def render_minif2f(exp_root):
    return _mf2f_rows(exp_root, "cost", "wall")


def render_minif2f_full(exp_root):
    return _mf2f_rows(exp_root, "cost_full", "wall_full")


def render_minif2f_runs(exp_root):
    """Appendix: accuracy, cost and wall time per run (same conventions as Table 2)."""
    d = data(exp_root)["minif2f"]["families"]
    lines = []
    for fam, label in MODELS:
        arms = d[fam]["arms"]
        for a, alabel in ARMS:
            for s_, x in sorted(arms[a]["per_run"].items()):
                acc = f"{cell(x['accuracy']['all'])} ({'/'.join(cell(x['accuracy'][b]) for b in BUCKETS)})"
                cst = f"{cell(x['cost']['all'])} ({'/'.join(cell(x['cost'][b]) for b in BUCKETS)})"
                wl = f"{wall_i(x['wall']['all'])} ({'/'.join(wall_i(x['wall'][b]) for b in BUCKETS)})"
                lines.append(f"| {label} | {alabel} | {s_ + 1} | {acc} | {cst} | {wl} |")
    return "\n".join(lines)


def render_efficiency(exp_root):
    d = data(exp_root)["minif2f"]
    lines = []

    def row(label, e, bold):
        c = f"{e['calls']:.1f}"; ti = f"{e['tokens_in']/1000:.1f}k"; to = f"{e['tokens_out']/1000:.1f}k"; pc = f"{e['tokens_out_per_call']/1000:.2f}k"
        return f"| {label} | {mk(c, bold[0])} | {mk(ti, bold[1])} | {mk(to, bold[2])} | {mk(pc, bold[3])} |"

    metrics = ("calls", "tokens_in", "tokens_out", "tokens_out_per_call")
    for fam, label in MODELS + (("all", "all models"),):
        effs = {a: (d["families"][fam]["arms"][a]["efficiency"] if fam != "all" else d["efficiency_all_models"][a]) for a in ARM_KEYS}
        flags = {m: bold_best([effs[a][m] for a in ARM_KEYS], minimize=True,
                              round_fn=(lambda v: round(v, 1)) if m == "calls" else (lambda v, m=m: round(v / 1000, 2 if m == "tokens_out_per_call" else 1)))
                 for m in metrics}
        for i, (a, alabel) in enumerate(ARMS):
            lines.append(row(f"{label} | {alabel}", effs[a], [flags[m][i] for m in metrics]))
    return "\n".join(lines)


def render_figure_data(exp_root):
    """The pooled columns of the miniF2F table as the bar-chart series of the write-up's
    first figure (accuracy in %, cost $, wall s; models in table order, servers in
    control / rocq-mcp / rocq-mcp-evolve order)."""
    d = data(exp_root)["minif2f"]["families"]
    acc = ",".join("{" + ", ".join(str(round(100 * d[f]["arms"][a]["accuracy"]["all"])) for a in ARM_KEYS) + "}" for f, _ in MODELS)
    cost = ",".join("{" + ", ".join(f"{d[f]['arms'][a]['cost']['all']:.2f}" for a in ARM_KEYS) + "}" for f, _ in MODELS)
    wall = ",".join("{" + ", ".join(str(round(d[f]["arms"][a]["wall"]["all"])) for a in ARM_KEYS) + "}" for f, _ in MODELS)
    return "\n".join([
        "| series | values (Haiku, Sonnet, Opus, Terra; each control / rocq-mcp / rocq-mcp-evolve) |",
        "|---|---|",
        f"| accuracy % | `{acc}` |",
        f"| cost $ | `{cost}` |",
        f"| wall s | `{wall}` |",
    ])


def render_autoclose(exp_root):
    d = data(exp_root)["autoclose"]
    lines = []
    for fam, label in MODELS + (("all", "all models"),):
        recs = {a: (d["families"][fam][a] if fam != "all" else d["all_models"][a]) for a in ARM_KEYS}
        b_cost = bold_best([recs[a]["cost"] for a in ARM_KEYS], minimize=True, round_fn=R2)
        b_wall = bold_best([recs[a]["wall"] for a in ARM_KEYS], minimize=True, round_fn=round)
        for i, (a, alabel) in enumerate(ARMS):
            x = recs[a]
            solved = f"{x['solved']}/{x['n']}" if fam != "all" else "—"
            lines.append(f"| {label} | {alabel} | {solved} | {mk(cell(x['cost']), b_cost[i])} | {mk(wall_i(x['wall']), b_wall[i])} |")
    return "\n".join(lines)


def render_paired(exp_root):
    d = data(exp_root)["paired"]
    fp = lambda x: f"{x['better']}:{x['worse']} (p = {rag.fmt_p_2sf(x['p'])})"
    lines = [f"| dev60, final Phase-1 server vs control (4 runs) | {d['dev60']['problems']} | {fp(d['dev60'])} | — |"]
    for fam, label in MODELS:
        x = d["minif2f"][fam]
        lines.append(f"| miniF2F test, {label} (2 runs) | {x['vs_control']['problems']} | {fp(x['vs_control'])} | {fp(x['vs_sibling'])} |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# projects
# --------------------------------------------------------------------------

def render_autoform(exp_root):
    d = data(exp_root)["autoform"]
    lines = []
    for fam, label in (("sonnet", "Sonnet"), ("opus", "Opus"), ("terra", "Terra")):
        arms = d["families"][fam]
        b_acc = bold_best([arms[a]["accuracy"] for a in ARM_KEYS], round_fn=R2)
        b_cost = bold_best([arms[a]["cost"] for a in ARM_KEYS], minimize=True, round_fn=money_round)
        b_wall = bold_best([arms[a]["wall"] for a in ARM_KEYS], minimize=True, round_fn=round)
        for i, (a, alabel) in enumerate(ARMS):
            x = arms[a]
            lines.append(f"| {label} | {alabel} | {mk(f'{x['solved']}/{x['n']}', b_acc[i])} | {mk(cell(x['accuracy']), b_acc[i])} | {mk(money(x['cost']), b_cost[i])} | {mk(wall_i(x['wall']), b_wall[i])} |")
    return "\n".join(lines)


def render_autoform_sd(exp_root):
    """Appendix: project-scale means with the standard deviation across runs (accuracy) or
    over solved runs (cost, wall)."""
    d = data(exp_root)["autoform"]
    lines = []
    pm = lambda m, sd, f: f"{f(m)} ± {f(sd)}" if sd is not None else f"{f(m)} ± —"
    for fam, label in (("sonnet", "Sonnet"), ("opus", "Opus"), ("terra", "Terra")):
        for a, alabel in ARMS:
            x = d["families"][fam][a]
            runs = "/".join(cell(v) for v in x["accuracy_runs"])
            lines.append(f"| {label} | {alabel} | {len(x['accuracy_runs'])} | {runs} | {pm(x['accuracy'], x['accuracy_sd'], cell)} | {pm(x['cost'], x['cost_sd'], money)} | {pm(x['wall'], x['wall_sd'], wall_i)} |")
    return "\n".join(lines)


def render_autoform_tasks(exp_root):
    d = data(exp_root)["autoform"]; tasks = d["tasks"]
    lines = []
    for fam, label in (("sonnet", "Sonnet"), ("opus", "Opus"), ("terra", "Terra")):
        arms = d["families"][fam]
        for a, alabel in ARMS:
            x = arms[a]
            lines.append(f"| {label} | {alabel} | " + " | ".join(f"{x['per_task'][t][0]}/{x['per_task'][t][1]}" for t in tasks) + " |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# evolution
# --------------------------------------------------------------------------

def render_evolution_points(exp_root):
    d = data(exp_root)["evolution"]
    return "\n".join("| " + " | ".join([str(p["index"]), p["label"], p["dataset"], p["verdict"], f"{p['solved']}/{p['n']}",
                                         pct_i(100 * p["accuracy"]), money(p["cost"]) if p["cost"] is not None else "—",
                                         wall_i(p["wall"])]) + " |" for p in d["points"])


def render_deltas(exp_root):
    d = data(exp_root)["evolution"]
    lines = []
    for x in d["deltas"]:
        if x["buckets"]:
            bk = " | ".join(f"+{x['buckets'][b]['won']}−{x['buckets'][b]['lost']}" if b in x["buckets"] else "—" for b in BUCKETS)
        else:
            bk = "— | — | —"
        lines.append(f"| {x['label']} | {x['dataset']} | {x['n_slots']} | {bk} | +{x['won']}−{x['lost']} |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# document
# --------------------------------------------------------------------------

def build_document(exp_root):
    d = data(exp_root)
    tasks = d["autoform"]["tasks"]
    ac = d["autoclose"]
    parts = [
        "# Report tables",
        "",
        "The tables and figure data of the paper, computed from `logs/` by",
        "`harness/results_tables/report_tables.py` and rendered by `harness/report_tables_gen.py`",
        "(`--check` diffs a regeneration against this file). Each table carries the caption of the",
        "paper and the label it has there. The exhaustive document is `docs/RESULTS_ALL.md`.",
        "",
        "## Runs behind every held-out cell",
        "",
        render_inventory(exp_root),
        "",
        "## `tab:evolution_deltas`",
        "",
        "**Detailed results** of the evolution process. Each line corresponds to a mutation of",
        "`tab:evolution_chronology`. Each cell reports the change with respect to the previous version",
        "as a diff: the number of new successes (+) and failures (−). For each dataset we report the",
        "number of problems in each difficulty bucket, and the number of runs per problem.",
        "",
        "| mutation | dataset | slots | easy | medium | hard | total |",
        "|---|---|---|---|---|---|---|",
        render_deltas(exp_root),
        "",
        "## `tab:detailed_results`",
        "",
        "Results on the `test` split of miniF2F. The results on the whole dataset are followed by the",
        "results per difficulty bucket: total (easy/medium/hard). For each model, the cost and wall",
        "time are only computed on attempts on the subset of problems solved by all three MCP servers",
        "in at least one run (results on the entire dataset are reported in `tab:detailed_results_full`).",
        "The size of this subset per difficulty bucket is given next to the model name.",
        "",
        "| model (e/m/h) | server | accuracy: total (e/m/h) | cost $: total (e/m/h) | wall s: total (e/m/h) |",
        "|---|---|---|---|---|",
        render_minif2f(exp_root),
        "",
        "## `tab:efficiency_results`",
        "",
        "Efficiency results for the different MCP servers, averaged over the four models.",
        "",
        "| model | server | calls | input tokens | output tokens | output tokens per call |",
        "|---|---|---|---|---|---|",
        render_efficiency(exp_root),
        "",
        "## Paired tests at the problem level",
        "",
        "For each problem, the number of runs solved under each server; a problem counts as better",
        "(worse) for rocq-mcp-evolve when it solved strictly more (fewer) of its runs than the other",
        "server. Exact two-sided sign test on the better:worse split; one unit per problem.",
        "",
        "| comparison | problems | rocq-mcp-evolve vs control | rocq-mcp-evolve vs rocq-mcp |",
        "|---|---|---|---|",
        render_paired(exp_root),
        "",
        "## Auto-closable problems (RQ3)",
        "",
        f"The tool `auto_close` alone solves {ac['n']}/{ac['n_total']} problems of the `test` split of miniF2F, i.e.,",
        f"{round(100 * ac['n'] / ac['n_total'])} % ({'/'.join(cell(ac['per_bucket'][b][0] / ac['per_bucket'][b][1]) for b in BUCKETS)} per bucket).",
        "On this subset of problems: solved attempts over both runs, cost and wall time per solve for",
        "each server, and the averages over all models.",
        "",
        "| model | server | solved attempts | cost $ | wall s |",
        "|---|---|---|---|---|",
        render_autoclose(exp_root),
        "",
        "## `tab:autoform_results`",
        "",
        "Results on project-scale tasks for the models Sonnet | Opus | Terra averaged on all tasks",
        "(detailed results are reported in `tab:autoform_results_full`).",
        "",
        "| model | server | solved | accuracy | cost $ | wall s |",
        "|---|---|---|---|---|---|",
        render_autoform(exp_root),
        "",
        "## `tab:detailed_results_full`",
        "",
        "Results on the `test` split of miniF2F with cost and wall time computed on the whole dataset",
        "instead of the problems solved with all three MCP servers.",
        "",
        "| model | server | accuracy: total (e/m/h) | cost $: total (e/m/h) | wall s: total (e/m/h) |",
        "|---|---|---|---|---|",
        render_minif2f_full(exp_root),
        "",
        "## `tab:detailed_results_runs`",
        "",
        "Results on the `test` split of miniF2F for each of the two runs (same conventions as",
        "`tab:detailed_results`: cost and wall time on the problems solved by all three MCP servers).",
        "",
        "| model | server | run | accuracy: total (e/m/h) | cost $: total (e/m/h) | wall s: total (e/m/h) |",
        "|---|---|---|---|---|---|",
        render_minif2f_runs(exp_root),
        "",
        "## `tab:autoform_results_sd`",
        "",
        "Results on project-scale tasks with the standard deviation of the accuracy across runs",
        "(accuracy per run = solved tasks / 5) and of the cost and wall time over the solved runs.",
        "",
        "| model | server | runs | accuracy per run | accuracy ± sd | cost $ ± sd | wall s ± sd |",
        "|---|---|---|---|---|---|---|",
        render_autoform_sd(exp_root),
        "",
        "## `tab:autoform_results_full`",
        "",
        "Results on the five project-scale tasks (4 runs per task, 2 for Opus). Four Terra solutions",
        "that passed the gate by hardcoding the probe inputs are not counted.",
        "",
        f"| model | server | {' | '.join(tasks)} |",
        f"|---|---|{'---|' * len(tasks)}",
        render_autoform_tasks(exp_root),
        "",
        "## `fig:phase1_evolution`",
        "",
        "Evolution of accuracy, cost, and wall time across the mutations of Phase 1 and Phase 2. The",
        "mutations are numbered chronologically (except number 14, which represents the server",
        "obtained after Phase 1).",
        "",
        "| index | mutation | dataset | verdict | solved/attempts | accuracy % | cost $ (solved) | wall s (solved) |",
        "|---|---|---|---|---|---|---|---|",
        render_evolution_points(exp_root),
        "",
        "## `fig:intro_results`",
        "",
        "Results on the `test` split of miniF2F-Rocq. Each model is evaluated with three MCP servers:",
        "control, a minimal server wrapping the Rocq compiler, rocq-mcp, an established MCP server for",
        "Rocq, and rocq-mcp-evolve. For a fair comparison, cost and wall time are averaged over the",
        "theorems proved with all three servers.",
        "",
        render_figure_data(exp_root),
        "",
    ]
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Regenerate the write-up's tables from this repository's logs.")
    parser.add_argument("out", type=Path, nargs="?", default=HERE.parent / "docs" / "REPORT_TABLES.md",
                        help="markdown file to check or write (default: docs/REPORT_TABLES.md)")
    parser.add_argument("--exp-root", type=Path, default=HERE.parent, help="experiment repo root")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="diff the regenerated document against out, exit 0 iff identical")
    mode.add_argument("--write", action="store_true", help="overwrite out with the regenerated document")
    args = parser.parse_args()
    try:
        doc = build_document(args.exp_root)
    except heldout_table.GateFailure as e:
        print("REFUSING to regenerate: the held-out integrity gates failed:")
        for f in e.failures:
            print("  -", f)
        sys.exit(1)
    if args.write:
        args.out.write_text(doc)
        print(f"wrote {args.out}")
        return
    old = args.out.read_text() if args.out.exists() else ""
    if old == doc:
        print("IDENTICAL")
        sys.exit(0)
    sys.stdout.writelines(difflib.unified_diff(old.splitlines(keepends=True), doc.splitlines(keepends=True),
                                               fromfile=str(args.out), tofile="regenerated"))
    sys.exit(1)


if __name__ == "__main__":
    main()
