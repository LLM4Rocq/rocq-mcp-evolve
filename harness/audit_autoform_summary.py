#!/usr/bin/env python3
"""Summary for the A130 method-(1) strict re-check.

    python3 -u harness/audit_autoform_summary.py [--out DIR]

Reads <out>/attempts.jsonl (written by harness/audit_autoform.py) and writes
<out>/summary.json and <out>/summary.md: a per-run/arm table (n, original
solved, strict solved, one column per outcome category, flagged attempts)
plus the toolchain block (rocq/dune versions, the rocq-*/coq-mathcomp-*
packages of the switch, the dev commit, a content hash of data/autoform).

Categories are those of A130.  `toolchain` rows are listed and excluded from
the agree/disagree counts.  `ext` (probes_ext.v) is reported as its own
column because ext_mismatch is only assigned when the gate and the strict
checker already agree; a probes_ext.v run KILLED by its wall clock is counted
in `ext_timeout`, never in `ext_fail` (the row is toolchain).
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import audit_autoform  # noqa: E402  (paths + pinned binaries)

HARNESS = Path(__file__).resolve().parent
WORKTREE = HARNESS.parent
MAIN = Path("/Users/gbaudart/Project/llm4rocq/rocq-tools/rocq-tools")
CATEGORIES = ["agree", "gate_unsound", "gate_stricter", "ext_mismatch",
              "toolchain"]


def sh(cmd, cwd=None):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=120)
        return (p.stdout + p.stderr).strip()
    except Exception as e:
        return f"<unavailable: {e!r}>"


def data_hash(root):
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if not p.is_file() or "_build" in p.parts:
            continue
        h.update(str(p.relative_to(root)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def toolchain_block():
    rocq, dune = audit_autoform.ROCQ, audit_autoform.DUNE
    switch = audit_autoform.SWITCH
    pkgs = sh(["opam", "list", "--switch", str(switch.parent), "--short",
               "--columns", "name,version"])
    keep = [l for l in pkgs.splitlines()
            if l.startswith(("rocq-", "coq-mathcomp", "coq-elpi", "coq-hierarchy"))]
    rocq_v = sh([rocq, "--version"]).splitlines()
    return {
        "rocq_version": rocq_v[0] if rocq_v else "",
        "dune_version": sh([dune, "--version"]),
        "packages": keep,
        "dev_commit": sh(["git", "-C", str(WORKTREE), "rev-parse", "HEAD"]),
        "dev_describe": sh(["git", "-C", str(WORKTREE), "log", "-1",
                            "--oneline"]),
        "data_autoform_sha256_16": data_hash(WORKTREE / "data" / "autoform"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(MAIN / "logs" / "audit_autoform"))
    args = ap.parse_args()
    out = Path(args.out)
    rows = common.read_jsonl(out / "attempts.jsonl")
    # last row wins for a re-audited (run, task, rep)
    dedup = {}
    for r in rows:
        dedup[(r.get("run"), r.get("task"), r.get("rep"))] = r
    rows = list(dedup.values())

    per_run = {}
    for r in rows:
        d = per_run.setdefault(r["run"], {
            "run": r["run"], "model": r.get("model"), "n": 0,
            "original_solved": 0, "strict_solved": 0, "flagged": 0,
            "ext_ok": 0, "ext_fail": 0, "ext_timeout": 0, "timed_out": 0,
            **{c: 0 for c in CATEGORIES}})
        d["n"] += 1
        d["original_solved"] += 1 if r.get("original_solved") else 0
        d["strict_solved"] += 1 if r.get("strict_solved") else 0
        cat = r.get("category") or "toolchain"
        d[cat] = d.get(cat, 0) + 1
        if (r.get("flags") or {}).get("any"):
            d["flagged"] += 1
        if r.get("timeouts"):
            d["timed_out"] += 1
        e = r.get("ext")
        if e == "ok":
            d["ext_ok"] += 1
        elif isinstance(e, str) and e.startswith("fail"):
            d["ext_fail"] += 1
        elif isinstance(e, str) and e.startswith("timeout"):
            d["ext_timeout"] += 1

    totals = {"run": "ALL", "model": "", "n": 0, "original_solved": 0,
              "strict_solved": 0, "flagged": 0, "ext_ok": 0, "ext_fail": 0,
              "ext_timeout": 0, "timed_out": 0,
              **{c: 0 for c in CATEGORIES}}
    for d in per_run.values():
        for k in list(totals):
            if k in ("run", "model"):
                continue
            totals[k] += d.get(k, 0)

    disagreements = [
        {**{k: r.get(k) for k in ("run", "task", "rep", "model",
                                  "original_solved", "original_reason",
                                  "regraded", "strict_solved", "strict_reason",
                                  "category", "ext")},
         "timeouts": r.get("timeouts") or []}
        for r in rows
        if r.get("category") in ("gate_unsound", "gate_stricter",
                                 "ext_mismatch", "toolchain")]
    disagreements.sort(key=lambda r: (r["category"], r["run"], r["task"],
                                      r["rep"]))

    # which review flags actually fired, campaign-wide (recorded, not deciding)
    flag_hist = {}
    for r in rows:
        f = r.get("flags") or {}
        for k, v in f.items():
            if k == "any":
                continue
            hit = (v > 1 if k == "n_theory_roots" else bool(v))
            if hit:
                flag_hist[k] = flag_hist.get(k, 0) + 1

    summary = {
        "n_attempts": len(rows),
        "flags": dict(sorted(flag_hist.items())),
        "per_run": [per_run[k] for k in sorted(per_run)],
        "totals": totals,
        "counted": {  # agree/disagree counts exclude toolchain rows
            "n": totals["n"] - totals["toolchain"],
            "agree": totals["agree"] + totals["ext_mismatch"],
            "gate_unsound": totals["gate_unsound"],
            "gate_stricter": totals["gate_stricter"],
            "ext_mismatch": totals["ext_mismatch"],
        },
        "disagreements": disagreements,
        "toolchain": toolchain_block(),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1,
                                                 sort_keys=True))

    cols = ["run", "model", "n", "original_solved", "strict_solved"] + \
        CATEGORIES + ["ext_ok", "ext_fail", "ext_timeout", "timed_out",
                      "flagged"]
    md = ["# Strict re-check of the autoform campaign (A130, method 1)", "",
          f"{len(rows)} attempts audited.", "",
          "| " + " | ".join(cols) + " |",
          "|" + "|".join("---" for _ in cols) + "|"]
    for d in [per_run[k] for k in sorted(per_run)] + [totals]:
        md.append("| " + " | ".join(str(d.get(c, "")) for c in cols) + " |")
    md += ["", "Counted (toolchain rows excluded): "
           f"n={summary['counted']['n']}, "
           f"agree={summary['counted']['agree']}, "
           f"gate_unsound={summary['counted']['gate_unsound']}, "
           f"gate_stricter={summary['counted']['gate_stricter']} "
           f"(of which ext_mismatch={summary['counted']['ext_mismatch']} "
           "pass probes.v but fail probes_ext.v).", ""]
    if flag_hist:
        md += ["## Review flags (recorded, never deciding)", ""]
        md += [f"- `{k}`: {v}" for k, v in sorted(flag_hist.items())]
        md.append("")
    if disagreements:
        md += ["## Rows that are not `agree`", "",
               "| category | run | task | rep | original | strict | reason | "
               "killed |",
               "|---|---|---|---|---|---|---|---|"]
        for r in disagreements:
            md.append("| {category} | {run} | {task} | {rep} | {o} | {s} | "
                      "{reason} | {killed} |".format(
                          o=f"{r['original_solved']}/{r['original_reason']}",
                          s=r["strict_solved"],
                          reason=(r["strict_reason"] or "")[:120].replace("|", "/"),
                          killed=",".join(r["timeouts"]) or "-",
                          **{k: v for k, v in r.items() if k != "timeouts"}))
        md.append("")
    tc = summary["toolchain"]
    md += ["## Toolchain", "",
           f"- rocq: `{tc['rocq_version']}`",
           f"- dune: `{tc['dune_version']}`",
           f"- dev commit: `{tc['dev_describe']}`",
           f"- data/autoform content hash: `{tc['data_autoform_sha256_16']}`",
           "- packages:", ""]
    md += [f"  - `{p}`" for p in tc["packages"]]
    md.append("")
    (out / "summary.md").write_text("\n".join(md))
    print(f"wrote {out/'summary.json'} and {out/'summary.md'}")
    print("\n".join(md[:12]))


if __name__ == "__main__":
    main()
