#!/usr/bin/env python3
"""A130 method (5): protocol checks over the 29 in-scope autoform runs.

    python3 harness/audit_autoform_protocol.py

Writes logs/audit_autoform/protocol.json and protocol.md.
Must be run with cwd = the dev-audit worktree (so the gate's relative
imports and data/autoform paths resolve), but reads run evidence from the
frozen main checkout via MAIN_ROOT below.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

WORKTREE = Path(__file__).resolve().parent.parent
MAIN_ROOT = WORKTREE.parent.parent.parent  # .../rocq-tools/rocq-tools (.claude/worktrees/dev-audit -> up 3)
AUTOFORM_LOGS = MAIN_ROOT / "logs" / "autoform"
OUT_DIR = MAIN_ROOT / "logs" / "audit_autoform"

EXCLUDE_PREFIX = "af_"
EXCLUDE_SUBSTR = "smoke"
EXCLUDE_EXACT = {"mst_probe_magistral"}

# Require an actual path-shaped occurrence of "reference" as a path
# component (preceded/followed by "/", or forming a whole path segment
# with a typical extension), not a bare word like a JSON content-block
# type "reference" or prose mentioning "reference solution".
REF_PATTERN = re.compile(r"(?:[\w./-]*/reference(?:/[\w./-]*)?|reference/[\w./-]+)")


def in_scope_runs():
    runs = []
    for p in sorted(AUTOFORM_LOGS.iterdir()):
        if not p.is_dir():
            continue
        name = p.name
        if name.startswith(EXCLUDE_PREFIX):
            continue
        if EXCLUDE_SUBSTR in name.lower():
            continue
        if name in EXCLUDE_EXACT:
            continue
        runs.append(p)
    return runs


def scan_reference_reads(run_dir, task_name, rep_name):
    """Scan transcript.jsonl and server.jsonl for a genuine reference/ path
    reference (tool call args / file paths), not a prose mention."""
    hits = []
    for fname in ("transcript.jsonl", "server.jsonl"):
        fpath = run_dir / fname
        if not fpath.exists():
            continue
        try:
            lines = fpath.read_text(errors="replace").splitlines()
        except Exception as e:
            hits.append({"file": fname, "line": None, "error": str(e)})
            continue
        for i, line in enumerate(lines, 1):
            if "reference" not in line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                # fall back to raw regex on the line
                if REF_PATTERN.search(line):
                    hits.append({"file": fname, "line": i, "excerpt": line[:400]})
                continue
            # Look specifically at plausible path-carrying fields.
            candidates = []

            def walk(o):
                if isinstance(o, str):
                    candidates.append(o)
                elif isinstance(o, dict):
                    for v in o.values():
                        walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)

            walk(obj)
            matched = [c for c in candidates if REF_PATTERN.search(c)]
            if matched:
                hits.append({
                    "file": fname,
                    "line": i,
                    "excerpt": line[:400],
                    "matched_strings": matched[:3],
                })
    return hits


def load_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def check_results_vs_verdict(run_dir):
    results = load_jsonl(run_dir / "results.jsonl")
    attempts_dir = run_dir / "attempts"
    disagreements = []
    missing_verdict = []
    by_key = {}
    for r in results:
        key = (r.get("task"), r.get("rep"))
        by_key[key] = r

    attempt_dirs = sorted(attempts_dir.iterdir()) if attempts_dir.exists() else []
    seen_keys = set()
    for adir in attempt_dirs:
        m = re.match(r"^(.*)__rep(\d+)$", adir.name)
        if not m:
            continue
        task, rep = m.group(1), int(m.group(2))
        seen_keys.add((task, rep))
        vpath = adir / "verdict.json"
        rrow = by_key.get((task, rep))
        if not vpath.exists():
            missing_verdict.append({
                "attempt": adir.name,
                "results_row": rrow,
                "note": "no verdict.json (killed at the wall / no build produced)",
            })
            continue
        try:
            verdict = json.loads(vpath.read_text())
        except Exception as e:
            missing_verdict.append({
                "attempt": adir.name,
                "note": f"verdict.json unparsable: {e}",
            })
            continue
        if rrow is None:
            disagreements.append({
                "attempt": adir.name,
                "issue": "in attempts/ + has verdict.json, but no results.jsonl row",
                "verdict": verdict,
            })
            continue
        r_solved = rrow.get("solved")
        v_solved = verdict.get("solved")
        r_reason = rrow.get("reason")
        v_reason = verdict.get("reason")
        if r_solved != v_solved or r_reason != v_reason:
            disagreements.append({
                "attempt": adir.name,
                "results_solved": r_solved,
                "verdict_solved": v_solved,
                "results_reason": r_reason,
                "verdict_reason": v_reason,
            })

    # results.jsonl rows with no matching attempts dir
    orphan_results = []
    for key, r in by_key.items():
        if key not in seen_keys:
            orphan_results.append(r)

    return {
        "n_attempts": len(attempt_dirs),
        "n_results_rows": len(results),
        "disagreements": disagreements,
        "missing_verdict": missing_verdict,
        "orphan_results_rows": orphan_results,
    }


def trigger_class_ok(workspace_dir):
    """>=2 dune files under workspace_dir containing 'coq.theory'."""
    n = 0
    files = []
    if not workspace_dir.exists():
        return False, 0, files
    for p in workspace_dir.rglob("dune"):
        if "_build" in p.parts:
            continue
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        if "coq.theory" in text:
            n += 1
            files.append(str(p.relative_to(workspace_dir)))
    return n >= 2, n, files


def run_current_gate(task, workspace_dir):
    gate = WORKTREE / "harness" / "autoform_gate.py"
    task_dir = WORKTREE / "data" / "autoform" / task
    cmd = [sys.executable, str(gate), str(task_dir), str(workspace_dir)]
    try:
        proc = subprocess.run(
            cmd, cwd=str(WORKTREE), capture_output=True, text=True, timeout=300
        )
    except subprocess.TimeoutExpired:
        return {"passes_now": None, "error": "timeout after 300s", "cmd": cmd}
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    # gate prints one json.dumps(verdict, indent=1) block (possibly multi-line);
    # take the substring from the last top-level '{' to end and parse it.
    verdict = None
    idx = out.rfind("{")
    while idx != -1:
        try:
            verdict = json.loads(out[idx:])
            break
        except Exception:
            idx = out.rfind("{", 0, idx)
    passes = None
    if verdict is not None:
        passes = bool(verdict.get("solved"))
    else:
        passes = proc.returncode == 0
    return {
        "passes_now": passes,
        "returncode": proc.returncode,
        "verdict": verdict,
        "stdout_tail": out[-2000:],
        "stderr_tail": err[-2000:],
    }


OPAM_ROOT = Path("/Users/gbaudart/Project/llm4rocq/rocq-tools/_opam")


def get_toolchain():
    opam_bin = OPAM_ROOT / "bin"
    def v(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception as e:
            return f"ERROR: {e}"
    rocq_v = v([str(opam_bin / "rocq"), "--version"])
    dune_v = v([str(opam_bin / "dune"), "--version"])
    opam_list = v(["opam", "list", "--switch", "/Users/gbaudart/Project/llm4rocq/rocq-tools"])
    filtered = "\n".join(
        l for l in opam_list.splitlines()
        if l.split() and (l.split()[0].startswith(("rocq-", "coq-")) or l.split()[0] in ("dune", "rocq", "coq"))
    )
    commit = v(["git", "-C", str(WORKTREE), "rev-parse", "HEAD"])
    return {
        "rocq_version": rocq_v,
        "dune_version": dune_v,
        "opam_list_rocq_coq_dune": filtered,
        "dev_worktree_commit": commit,
    }


def per_run_summary(run_dir, rv_check):
    meta_path = run_dir / "run_meta.json"
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            meta = {"error": "unparsable run_meta.json"}
    cfg = meta.get("config", {})
    results = load_jsonl(run_dir / "results.jsonl")
    n_solved_reported = sum(1 for r in results if r.get("solved"))
    return {
        "run": run_dir.name,
        "model": cfg.get("model"),
        "reps": meta.get("reps"),
        "max_turns": cfg.get("max_turns"),
        "attempt_timeout_s": cfg.get("attempt_timeout_s"),
        "n_attempts_dirs": rv_check["n_attempts"],
        "n_results_rows": rv_check["n_results_rows"],
        "n_solved_per_results_jsonl": n_solved_reported,
        "n_disagreements": len(rv_check["disagreements"]),
        "n_missing_verdict": len(rv_check["missing_verdict"]),
    }


def main():
    runs = in_scope_runs()
    assert len(runs) == 29, f"expected 29 in-scope runs, got {len(runs)}: {[r.name for r in runs]}"

    report = {"runs": [r.name for r in runs]}

    # (a) reference reads
    ref_reads = []
    for run_dir in runs:
        attempts_dir = run_dir / "attempts"
        if not attempts_dir.exists():
            continue
        for adir in sorted(attempts_dir.iterdir()):
            if not adir.is_dir():
                continue
            hits = scan_reference_reads(adir, run_dir.name, adir.name)
            if hits:
                ref_reads.append({
                    "run": run_dir.name,
                    "attempt": adir.name,
                    "hits": hits,
                })
    report["reference_reads"] = {
        "n_attempts_with_hits": len(ref_reads),
        "details": ref_reads,
    }

    # (b) results vs verdict
    rv_all = {}
    per_run_rows = []
    all_disagreements = []
    all_missing = []
    for run_dir in runs:
        rv = check_results_vs_verdict(run_dir)
        rv_all[run_dir.name] = rv
        per_run_rows.append(per_run_summary(run_dir, rv))
        for d in rv["disagreements"]:
            d2 = dict(d)
            d2["run"] = run_dir.name
            all_disagreements.append(d2)
        for m in rv["missing_verdict"]:
            m2 = dict(m)
            m2["run"] = run_dir.name
            all_missing.append(m2)
    report["results_vs_verdict"] = {
        "n_disagreements_total": len(all_disagreements),
        "disagreements": all_disagreements,
        "n_missing_verdict_total": len(all_missing),
        "missing_verdict": all_missing,
    }

    # (c) regrades
    regrade_checks = []
    for run_dir in runs:
        rpath = run_dir / "regrades.jsonl"
        rows = load_jsonl(rpath)
        for row in rows:
            task = row.get("task")
            rep = row.get("rep")
            attempt_name = f"{task}__rep{rep}"
            workspace = run_dir / "attempts" / attempt_name / "workspace"
            in_class, n_theory_files, theory_files = trigger_class_ok(workspace)
            gate_result = run_current_gate(task, workspace)
            regrade_checks.append({
                "run": run_dir.name,
                "attempt": attempt_name,
                "regrade_row": row,
                "trigger_class": {
                    "in_trigger_class": in_class,
                    "n_dune_files_with_coq_theory": n_theory_files,
                    "files": theory_files,
                },
                "current_gate": gate_result,
            })
    report["regrades"] = {
        "n_regrade_rows_total": len(regrade_checks),
        "details": regrade_checks,
    }

    # (d) toolchain
    report["toolchain"] = get_toolchain()

    # (e) per-run table
    report["per_run_table"] = per_run_rows

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "protocol.json").write_text(json.dumps(report, indent=1, default=str))

    md = []
    md.append("# A130 method (5): protocol checks\n")
    md.append(f"29 in-scope runs checked. Toolchain: {report['toolchain']['rocq_version']} / "
               f"{report['toolchain']['dune_version']} / dev-audit commit "
               f"{report['toolchain']['dev_worktree_commit']}\n")

    md.append("## (a) reference/ path reads in transcripts\n")
    if not ref_reads:
        md.append("No transcript or server log line in any of the 29 runs contains a tool "
                   "call/file path matching `reference/`, `/reference`, or a `reference` path "
                   "component. No reference/ read found.\n")
    else:
        md.append(f"{len(ref_reads)} attempt(s) with a matching hit:\n")
        for item in ref_reads:
            md.append(f"- {item['run']}/{item['attempt']}:")
            for h in item["hits"]:
                exc = h.get("excerpt", "")[:200]
                md.append(f"  - {h['file']}:{h.get('line')} `{exc}`")
    md.append("")

    md.append("## (b) results.jsonl vs verdict.json\n")
    md.append(f"Disagreements: {len(all_disagreements)}. Attempts missing verdict.json "
               f"(killed at the wall): {len(all_missing)}.\n")
    if all_disagreements:
        md.append("### Disagreements\n")
        for d in all_disagreements:
            md.append(f"- {d['run']}/{d.get('attempt')}: {d}")
    if all_missing:
        md.append("### Missing verdict.json\n")
        for m in all_missing:
            md.append(f"- {m['run']}/{m.get('attempt')}: {m.get('note')}")
    md.append("")

    md.append("## (c) A75 regrades: trigger class + current gate\n")
    md.append(f"{len(regrade_checks)} regrade rows checked.\n")
    md.append("| run | attempt | in trigger class | # coq.theory dune files | passes current gate |")
    md.append("|---|---|---|---|---|")
    for rc in regrade_checks:
        md.append(f"| {rc['run']} | {rc['attempt']} | {rc['trigger_class']['in_trigger_class']} "
                   f"| {rc['trigger_class']['n_dune_files_with_coq_theory']} "
                   f"| {rc['current_gate'].get('passes_now')} |")
    md.append("")

    md.append("## (d) Toolchain\n")
    md.append(f"- rocq: `{report['toolchain']['rocq_version']}`")
    md.append(f"- dune: `{report['toolchain']['dune_version']}`")
    md.append(f"- dev-audit worktree commit: `{report['toolchain']['dev_worktree_commit']}`")
    md.append("- opam list (rocq-*/coq-*/dune):")
    md.append("```")
    md.append(report["toolchain"]["opam_list_rocq_coq_dune"])
    md.append("```\n")

    md.append("## (e) Per-run table\n")
    md.append("| run | model | reps | max_turns | timeout_s | attempts | results rows | solved (results.jsonl) | disagreements | missing verdict |")
    md.append("|---|---|---|---|---|---|---|---|---|---|")
    for row in per_run_rows:
        md.append(f"| {row['run']} | {row['model']} | {row['reps']} | {row['max_turns']} | "
                   f"{row['attempt_timeout_s']} | {row['n_attempts_dirs']} | {row['n_results_rows']} | "
                   f"{row['n_solved_per_results_jsonl']} | {row['n_disagreements']} | {row['n_missing_verdict']} |")

    (OUT_DIR / "protocol.md").write_text("\n".join(md) + "\n")
    print(f"Wrote {OUT_DIR / 'protocol.json'} and {OUT_DIR / 'protocol.md'}")


if __name__ == "__main__":
    main()
