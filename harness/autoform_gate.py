#!/usr/bin/env python3
"""Grader for autoformalization tasks (docs/AUTOFORM.md).

    python3 harness/autoform_gate.py <task_dir> <submission_dir>

A submission is a dune project (logical root TaskLib). Layers:
  1. fresh `dune build` of the submission
  2. compile <task_dir>/probes.v against the built project
  3. assumption audit on every probe theorem/example (no axioms)
  4. forbidden-token scan over all submission .v files (comment-stripped)
Exit 0 + JSON verdict on stdout.
"""

import json
import re
import shutil
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gate import strip_comments, FORBIDDEN as _PHASE1_FORBIDDEN

# whole-project submissions legitimately Require between their own files and
# the stdlib; the phase-1 import lock does not apply here
# blanket `Unset` also dropped: `Unset Strict Implicit.` is standard
# ssreflect prelude; only the soundness-critical flags stay banned
FORBIDDEN = [(rx, lb) for rx, lb in _PHASE1_FORBIDDEN
             if lb not in ("Require", "From", "Load", "Unset", "Set")]
FORBIDDEN.append((re.compile(
    r"\b(?:Unset|Set)\s+(?:Guard|Positivity|Universe)\s+Checking\b"),
    "kernel-flag tampering"))

import common

ROCQ = str(common.OPAM_BIN / "rocq") if (common.OPAM_BIN / "rocq").exists() else "rocq"
DUNE = shutil.which("dune") or str(common.OPAM_BIN / "dune")


def run(cmd, cwd=None, timeout=600):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        # A115c-e: build workers (rocqworker under dune) detach from the
        # killed direct child and survive as multi-GB orphans in the
        # afgate_* staging dir. Reap by cwd before re-raising — scoped to
        # this run's own directory, semantics unchanged for callers.
        _reap_workers_under(cwd)
        raise
    return p.returncode, (p.stdout + p.stderr)[-4000:]


def _reap_workers_under(scope_dir):
    if not scope_dir:
        return
    try:
        pids = subprocess.run(["pgrep", "-f", "rocqworker"], capture_output=True,
                              text=True).stdout.split()
        for pid in pids:
            out = subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
                                 capture_output=True, text=True).stdout
            if any(l.startswith("n") and str(scope_dir) in l
                   for l in out.splitlines()):
                try:
                    os.kill(int(pid), 15)
                except (OSError, ValueError):
                    pass
    except Exception:
        pass


def probe_names(probes_src):
    return re.findall(r"^\s*(?:Example|Theorem)\s+([A-Za-z0-9_']+)",
                      probes_src, re.M)


def check(task_dir, sub_dir):
    task_dir, sub_dir = Path(task_dir), Path(sub_dir)
    verdict = {"task": task_dir.name, "solved": False, "layers": {}}

    # layer 4 first (cheap): forbidden tokens in the DELIVERED project only.
    # Judge only .v files that belong to a coq.theory (part of the dune
    # build) — NOT stray scratch/prototype files (an admit in a scratchpad
    # that isn't compiled must not fail a submission whose project is clean).
    theory_roots = []
    for dune in sub_dir.rglob("dune"):
        if "_build" in dune.parts:
            continue
        try:
            if "coq.theory" in dune.read_text(errors="replace"):
                theory_roots.append(dune.parent)
        except OSError:
            pass

    def delivered(vpath):
        return any(root == vpath.parent or root in vpath.parents
                   for root in theory_roots)

    for v in sorted(sub_dir.rglob("*.v")):
        if "_build" in v.parts or not delivered(v):
            continue
        body = strip_comments(v.read_text(errors="replace"))
        for rx, label in FORBIDDEN:
            if rx.search(body):
                verdict["layers"]["forbidden"] = f"{v.name}: {label}"
                verdict["reason"] = "forbidden_token"
                return verdict
    verdict["layers"]["forbidden"] = "clean"

    # layer 1: fresh build — in an ISOLATED copy outside any enclosing dune
    # workspace (submissions may live inside a larger repo; --root pins it)
    build_root = Path(tempfile.mkdtemp(prefix="afgate_"))
    work = build_root / "sub"
    shutil.copytree(sub_dir, work, ignore=shutil.ignore_patterns("_build"))
    rc, out = run([DUNE, "build", "--root", "."], cwd=work)
    verdict["layers"]["build"] = "ok" if rc == 0 else out
    if rc != 0:
        verdict["reason"] = "build_failed"
        return verdict

    # locate the built theory dir. A75: prefer the dune theory DECLARING
    # TaskLib — agents sometimes ship a second test theory containing a
    # probes.v copy, and the previous `vo[0].parent` over an unordered
    # rglob could select it (only probes.vo inside), failing every probe
    # on provably-correct work. Fallback: the dir with the most .vo files.
    vo = list((work / "_build" / "default").rglob("*.vo"))
    if not vo:
        verdict["reason"] = "no_vo_built"
        return verdict
    theory_dir = None
    for dune in work.rglob("dune"):
        if "_build" in dune.parts:
            continue
        try:
            txt = dune.read_text(errors="replace")
        except OSError:
            continue
        if "coq.theory" in txt and re.search(r"\(name\s+TaskLib\s*\)", txt):
            d = work / "_build" / "default" / dune.parent.relative_to(work)
            if list(d.glob("*.vo")):
                theory_dir = d
                break
    if theory_dir is None:
        theory_dir = max({v.parent for v in vo},
                         key=lambda d: len(list(d.glob("*.vo"))))

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        probes = (task_dir / "probes.v").read_text()
        shutil.copy(task_dir / "probes.v", td / "probes.v")

        # layer 2: probes compile against the submission
        rc, out = run([ROCQ, "compile", "-Q", str(theory_dir), "TaskLib",
                       "probes.v"], cwd=td)
        verdict["layers"]["probes"] = "ok" if rc == 0 else out
        if rc != 0:
            verdict["reason"] = "probes_failed"
            return verdict

        # layer 3: assumption audit over every probe
        names = probe_names(probes)
        audit = "\n".join(
            ["From TaskLib Require Import " +
             " ".join(re.findall(r"From TaskLib Require Import ([^\n.]+)",
                                 probes)[0].split()) + ".",
             'Require Import probes.'] +
            [f"Print Assumptions {n}." for n in names])
        (td / "audit.v").write_text(audit)
        rc, out = run([ROCQ, "compile", "-Q", str(theory_dir), "TaskLib",
                       "-Q", str(td), "", "audit.v"], cwd=td)
        if rc != 0:
            verdict["layers"]["audit"] = out
            verdict["reason"] = "audit_failed"
            return verdict
        # mathcomp-analysis is built on the boolp classical trio; exactly
        # these are acceptable, nothing else (mirrors the library's own base)
        ALLOWED = {"boolp.propositional_extensionality",
                   "boolp.functional_extensionality_dep",
                   "boolp.constructive_indefinite_description",
                   "propositional_extensionality",
                   "functional_extensionality_dep",
                   "constructive_indefinite_description"}
        bad = [a for a in re.findall(r"^([A-Za-z_][\w.']*) :", out, re.M)
               if a not in ALLOWED]
        if bad:
            verdict["layers"]["audit"] = "non-allowlisted axioms: " + ", ".join(sorted(set(bad))[:10])
            verdict["reason"] = "axioms_present"
            return verdict
        verdict["layers"]["audit"] = "closed"

    verdict["solved"] = True
    verdict["reason"] = "ok"
    verdict["n_probes"] = len(names)
    return verdict


if __name__ == "__main__":
    v = check(sys.argv[1], sys.argv[2])
    print(json.dumps(v, indent=1))
    sys.exit(0 if v["solved"] else 1)
