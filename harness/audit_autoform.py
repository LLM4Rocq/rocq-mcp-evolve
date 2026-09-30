#!/usr/bin/env python3
"""A130 method (1): independent strict re-check of the autoform campaign.

    python3 -u harness/audit_autoform.py [--runs r1 r2] [--only-solved]
                                         [--limit N] [--jobs N] [--out DIR]
                                         [--resume] [--ext]

For every stored attempt of the 29 in-scope runs under logs/autoform/ this
rebuilds the submitted workspace in a fresh sandbox, compiles the task's
probes.v against it, and computes the assumptions of every probe with the
Rocq API (src/audit/rocq_assumptions.exe -> Assumptions.assumptions),
classified BY CONSTRUCTOR.  Strict acceptance: every probe is closed under
the global context, or its only assumptions are constant axioms whose FULLY
QUALIFIED kernel name is one of the three mathcomp-analysis classical
axioms.  Guard/positivity/type-in-type/UIP bypasses and section variables
are never accepted -- the original gate's `name : type` text parser cannot
see them.

Review flags (OCaml libraries/plugins in the submission, .ml files, Declare
ML Module, bypass_check attributes, kernel-flag commands, several coq.theory
roots, and whether the gate's own forbidden-token scan would have fired) are
RECORDED and never decide anything.

Rows are appended to <out>/attempts.jsonl as they finish (--resume skips
rows already there).  Nothing here mutates logs/autoform/.

Environment events never become claims about a submission: every phase runs
under a wall clock, a killed phase is recorded in row["timeouts"], and any
such row -- like an attempt whose original verdict could not be recovered --
is categorized `toolchain` (listed, excluded from the agree/disagree counts).
"""

import argparse
import json
import multiprocessing as mp
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common                      # noqa: E402
import autoform_gate               # noqa: E402  (helpers only; not modified)
from gate import strip_comments    # noqa: E402

# --------------------------------------------------------------------------
# paths

HARNESS = Path(__file__).resolve().parent
WORKTREE = HARNESS.parent                     # the dev worktree this lives in
MAIN = Path("/Users/gbaudart/Project/llm4rocq/rocq-tools/rocq-tools")
RUNS_ROOT = MAIN / "logs" / "autoform"        # frozen campaign evidence (read-only)
TASKS_ROOT = WORKTREE / "data" / "autoform"
CHECKER = WORKTREE / "_build" / "default" / "src" / "audit" / "rocq_assumptions.exe"

# common.OPAM_BIN is derived from this worktree's location and therefore
# misses the switch; pin it (the campaign's switch) and fall back to what the
# original gate resolved.
SWITCH = MAIN.parent / "_opam"
ROCQ = str(SWITCH / "bin" / "rocq") if (SWITCH / "bin" / "rocq").exists() \
    else autoform_gate.ROCQ
DUNE = str(SWITCH / "bin" / "dune") if (SWITCH / "bin" / "dune").exists() \
    else autoform_gate.DUNE

BUILD_TIMEOUT_S = 1800
PROBES_TIMEOUT_S = 600
CHECKER_TIMEOUT_S = 900

# The classical base of mathcomp-analysis (mathcomp/classical/boolp.v).  These
# three fully qualified kernel names are not guessed: they were READ OFF the
# checker on test/fixtures/audit/classical.v, which proves ~~P->P (contrapT),
# functional extensionality (funext) and choice (cid) against
# coq-mathcomp-analysis 1.16.0 / rocq-core 9.1.1:
#
#   rocq compile -Q . "" classical.v
#   rocq_assumptions.exe -Q . "" --require classical \
#       --names cls_contra cls_funext cls_cid
#   -> "mathcomp.classical.boolp.propositional_extensionality", ...
#
# test/audit_assumptions_test.sh re-runs exactly that and fails if the names
# ever move, so this set cannot drift away from the library silently.
# Qualified on purpose: a submission that declares its own
# `Axiom propositional_extensionality` gets a different kernel name
# (e.g. TaskLib.Main.propositional_extensionality) and is NOT accepted --
# test/fixtures/audit/shadow.v pins that case.
ALLOWED_AXIOMS = {
    "mathcomp.classical.boolp.propositional_extensionality",
    "mathcomp.classical.boolp.functional_extensionality_dep",
    "mathcomp.classical.boolp.constructive_indefinite_description",
}

PROBE_RX = re.compile(
    r"^[ \t]*(?:Theorem|Example|Lemma|Fact|Corollary|Proposition|Remark)"
    r"\s+([A-Za-z0-9_']+)", re.M)

FLAG_TOKENS = [
    ("declare_ml_module", re.compile(r"Declare\s+ML\s+Module")),
    ("bypass_check", re.compile(r"bypass_check")),
    ("guard_checking", re.compile(r"(?:Unset|Set)\s+Guard\s+Checking")),
    ("positivity_checking", re.compile(r"(?:Unset|Set)\s+Positivity\s+Checking")),
    ("universe_checking", re.compile(r"(?:Unset|Set)\s+Universe\s+Checking")),
]


def log(msg):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.stderr.flush()


# --------------------------------------------------------------------------
# scope

def in_scope_runs():
    """The 29 runs of A130: everything under logs/autoform/ that is not a
    wave-1 af_* run, not a smoke, and not the magistral probe."""
    out = []
    for d in sorted(RUNS_ROOT.iterdir()):
        if not d.is_dir() or not (d / "attempts").is_dir():
            continue
        n = d.name
        if n.startswith("af_") or "smoke" in n or n == "mst_probe_magistral":
            continue
        out.append(d)
    return out


def task_dir_of(task):
    """Attempt task name -> current dataset directory.  The wave-2 runs were
    graded before the tasks lost their `w2_` prefix (commit 17a0ea6, content
    unchanged), so `w2_frugal` is today's `frugal`."""
    d = TASKS_ROOT / task
    if d.is_dir():
        return d
    if task.startswith("w2_") and (TASKS_ROOT / task[3:]).is_dir():
        return TASKS_ROOT / task[3:]
    return None


def attempts_of(run_dir, only_solved=False):
    results = {(r.get("task"), r.get("rep")): r
               for r in common.read_jsonl(run_dir / "results.jsonl")}
    regrades = {(r.get("task"), r.get("rep")): r
                for r in common.read_jsonl(run_dir / "regrades.jsonl")}
    meta = {}
    if (run_dir / "run_meta.json").exists():
        try:
            meta = json.loads((run_dir / "run_meta.json").read_text())
        except Exception:
            meta = {}
    model = (meta.get("config") or {}).get("model")
    out = []
    for a in sorted((run_dir / "attempts").iterdir()):
        if not a.is_dir() or "__rep" not in a.name:
            continue
        task, rep = a.name.rsplit("__rep", 1)
        try:
            rep = int(rep)
        except ValueError:
            continue
        res = results.get((task, rep), {})
        reg = regrades.get((task, rep))
        # the original verdict is the attempt's own verdict.json; the eight
        # A75 regrades override it; results.jsonl is the last resort
        verdict = {}
        unparsed = False
        vp = a / "verdict.json"
        if vp.exists():
            try:
                verdict = json.loads(vp.read_text(errors="replace"))
            except Exception:
                verdict, unparsed = {}, True   # recorded: never silent
        orig = reg or verdict or res
        source = ("regrades.jsonl" if reg else
                  "verdict.json" if verdict else
                  "results.jsonl" if res else None)
        layers = verdict.get("layers") or {}
        orig_build = layers.get("build")
        out.append({
            "run": run_dir.name,
            "task": task,
            "rep": rep,
            "attempt_dir": str(a),
            "model": res.get("model") or model,
            "original_solved": bool(orig.get("solved")) if orig else None,
            "original_reason": orig.get("reason") if orig else None,
            "original_source": source,
            "original_verdict_unparsed": unparsed,
            "original_build_ok": (None if orig_build is None
                                  else orig_build == "ok"),
            "results_solved": (bool(res.get("solved")) if res else None),
            "regraded": reg is not None,
            "only_solved": only_solved,
        })
    if only_solved:
        out = [a for a in out if a["original_solved"]]
    return out


# --------------------------------------------------------------------------
# process helpers

def prover_env():
    """Switch bin first, so the sandbox build resolves the campaign's rocq
    whatever the caller's PATH is."""
    env = dict(os.environ)
    env["PATH"] = f"{SWITCH / 'bin'}:{env.get('PATH', '')}"
    return env


def run_cmd(cmd, cwd, timeout, env=None):
    """Run in its own session so a timeout can kill the whole group; reap
    rocqworker orphans under cwd exactly as the original gate does.

    Returns (rc, output, seconds, timed_out).  `timed_out` is reported apart
    from `rc` on purpose: a phase killed by its wall clock (or by an OOM kill,
    which lands on the same path) is an ENVIRONMENT event and says nothing
    about the submission, so categorize() must route it to `toolchain` instead
    of asserting a disagreement.  This sweep runs several attempts in parallel
    on a shared machine, so contention-induced kills are expected, not
    hypothetical."""
    t0 = time.time()
    timed_out = False
    p = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, errors="replace", start_new_session=True,
                         env=env or prover_env())
    try:
        out, _ = p.communicate(timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except OSError:
            pass
        try:
            out, _ = p.communicate(timeout=120)
        except Exception:
            out = ""
        autoform_gate._reap_workers_under(cwd)
        rc = -9
        timed_out = True
        out = (out or "") + f"\n[killed: timeout after {timeout}s]"
    return rc, out or "", round(time.time() - t0, 2), timed_out


ERR_HEAD_RX = re.compile(r'(?m)^File "[^"]*", line \d+.*$')


def excerpt(s, n=2000):
    """Head+tail excerpt of a compiler log, with the last Rocq error header.

    A failed vm_compute pin -- the usual way probes.v / probes_ext.v reject a
    submission -- makes Rocq print ONE huge `Unable to unify` term dump, so the
    last n characters are the middle of a term and carry no error text at all.
    Keeping both ends, plus the `File "...", line N` header that starts the
    error when it falls in the elided middle, keeps the row readable."""
    s = s or ""
    if len(s) <= n:
        return s
    head = n // 2
    body = (s[:head] + f"\n[... {len(s) - n} chars elided ...]\n"
            + s[-(n - head):])
    m = None
    for m in ERR_HEAD_RX.finditer(s):
        pass
    if m is not None and head <= m.start() < len(s) - (n - head):
        body = s[m.start():m.start() + 400].rstrip() + "\n[...]\n" + body
    return body


# --------------------------------------------------------------------------
# per-attempt work

def theory_dir_of(work):
    """Locate the built theory dir exactly like autoform_gate.check."""
    vo = list((work / "_build" / "default").rglob("*.vo"))
    if not vo:
        return None
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
                return d
    return max({v.parent for v in vo}, key=lambda d: len(list(d.glob("*.vo"))))


def review_flags(sub_dir):
    flags = {"dune_library": False, "dune_executable": False,
             "dune_plugin": False, "coq_plugin": False, "ml_files": [],
             "n_theory_roots": 0, "forbidden_token": None}
    for k, _ in FLAG_TOKENS:
        flags[k] = False
    theory_roots = []
    for dune in sub_dir.rglob("dune"):
        if "_build" in dune.parts:
            continue
        try:
            txt = dune.read_text(errors="replace")
        except OSError:
            continue
        if "(library" in txt:
            flags["dune_library"] = True
        if "(executable" in txt:
            flags["dune_executable"] = True
        if "(plugin" in txt:
            flags["dune_plugin"] = True
        if "coq.plugin" in txt:
            flags["coq_plugin"] = True
        if "coq.theory" in txt:
            flags["n_theory_roots"] += 1
            theory_roots.append(dune.parent)
    for p in sorted(sub_dir.rglob("*")):
        if "_build" in p.parts or not p.is_file():
            continue
        if p.suffix in (".ml", ".mli", ".mlg"):
            flags["ml_files"].append(str(p.relative_to(sub_dir)))
        if p.suffix == ".v":
            try:
                body = strip_comments(p.read_text(errors="replace"))
            except OSError:
                continue
            for k, rx in FLAG_TOKENS:
                if rx.search(body):
                    flags[k] = True
            # The strict checker deliberately drops the gate's layer-4 token
            # scan (assumptions decide, not spelling), so a `gate_stricter`
            # row can be an attempt the gate rejected on a token alone.
            # Record which, so those rows are readable; never decide on it.
            delivered = any(r == p.parent or r in p.parents
                            for r in theory_roots)
            if delivered and flags["forbidden_token"] is None:
                for rx, label in autoform_gate.FORBIDDEN:
                    if rx.search(body):
                        flags["forbidden_token"] = \
                            f"{p.relative_to(sub_dir)}: {label}"
                        break
    flags["any"] = bool(flags["dune_library"] or flags["dune_executable"]
                        or flags["dune_plugin"] or flags["coq_plugin"]
                        or flags["ml_files"] or flags["n_theory_roots"] > 1
                        or flags["forbidden_token"]
                        or any(flags[k] for k, _ in FLAG_TOKENS))
    return flags


def strict_decision(names, probe_names):
    """accepted iff every probe is closed, or every item is a constant axiom
    whose fully qualified name is allowlisted."""
    by_name = {n["name"]: n for n in names}
    bad = []
    for pn in probe_names:
        n = by_name.get(pn)
        if n is None:
            bad.append(f"{pn}: missing from checker output")
            continue
        if n["status"] == "error":
            bad.append(f"{pn}: {n.get('error', 'error')}")
            continue
        for it in n.get("items", []):
            if it["kind"] != "axiom" or it["name"] not in ALLOWED_AXIOMS:
                bad.append(f"{pn}: {it['kind']} {it['name']}")
    if not probe_names:
        return False, "no_probe_names"
    if bad:
        uniq = sorted(set(bad))
        return False, "non_allowlisted: " + "; ".join(uniq[:10])
    return True, "ok"


def audit_attempt(spec, sandbox_root, want_ext, keep):
    run, task, rep = spec["run"], spec["task"], spec["rep"]
    aid = f"{run}/{task}__rep{rep}"
    row = dict(spec)
    row.pop("only_solved", None)
    row.update({"strict_solved": False, "strict_reason": None,
                "assumptions": None, "flags": None, "ext": None,
                "category": None, "seconds": {}, "timeouts": [],
                "build_log_tail": None,
                "timestamp": time.time()})
    t_all = time.time()

    ws = Path(spec["attempt_dir"]) / "workspace"
    task_dir = task_dir_of(task)
    if not ws.is_dir():
        row["strict_reason"] = "no_workspace"
    elif task_dir is None:
        row["strict_reason"] = "no_task_dir"
    if row["strict_reason"]:
        row["category"] = categorize(row, None)
        row["seconds"]["total"] = round(time.time() - t_all, 2)
        return row

    row["flags"] = review_flags(ws)

    sandbox_root.mkdir(parents=True, exist_ok=True)
    sb = Path(tempfile.mkdtemp(prefix=f"aa_{run}_{task}_{rep}_", dir=sandbox_root))
    work = sb / "sub"
    try:
        t0 = time.time()
        shutil.copytree(ws, work, ignore=shutil.ignore_patterns("_build"),
                        symlinks=True)
        row["seconds"]["copy"] = round(time.time() - t0, 2)

        log(f"[{aid}] build")
        rc, out, secs, killed = run_cmd([DUNE, "build", "--root", "."], work,
                                        BUILD_TIMEOUT_S)
        row["seconds"]["build"] = secs
        row["build_ok"] = rc == 0
        if killed:
            row["timeouts"].append(f"build:{BUILD_TIMEOUT_S}s")
        if rc != 0:
            row["strict_reason"] = "build_timeout" if killed else "build_failed"
            row["build_log_tail"] = excerpt(out)
            row["category"] = categorize(row, None)
            row["seconds"]["total"] = round(time.time() - t_all, 2)
            log(f"[{aid}] build FAILED in {secs}s")
            return row

        theory_dir = theory_dir_of(work)
        if theory_dir is None:
            row["strict_reason"] = "no_vo_built"  # dune succeeded, nothing built
            row["build_log_tail"] = excerpt(out)
            row["category"] = categorize(row, None)
            row["seconds"]["total"] = round(time.time() - t_all, 2)
            return row
        row["theory_dir"] = str(theory_dir.relative_to(work))

        pd = sb / "probes"
        pd.mkdir()
        shutil.copy(task_dir / "probes.v", pd / "probes.v")
        probe_src = (task_dir / "probes.v").read_text(errors="replace")
        probe_names = PROBE_RX.findall(strip_comments(probe_src))

        log(f"[{aid}] probes ({len(probe_names)} names)")
        rc, out, secs, killed = run_cmd(
            [ROCQ, "compile", "-Q", str(theory_dir), "TaskLib", "probes.v"],
            pd, PROBES_TIMEOUT_S)
        row["seconds"]["probes"] = secs
        if killed:
            row["timeouts"].append(f"probes:{PROBES_TIMEOUT_S}s")
        if rc != 0:
            # a killed compile is an environment event, not a rejection
            row["strict_reason"] = ("probes_timeout" if killed
                                    else "probes_failed")
            row["build_log_tail"] = excerpt(out)
            row["category"] = categorize(row, None)
            row["seconds"]["total"] = round(time.time() - t_all, 2)
            log(f"[{aid}] probes FAILED in {secs}s")
            return row

        log(f"[{aid}] assumptions")
        cmd = [str(CHECKER), "-Q", str(theory_dir), "TaskLib",
               "-Q", str(pd), "", "--require", "probes", "--names"] + probe_names
        rc, out, secs, killed = run_cmd(cmd, pd, CHECKER_TIMEOUT_S)
        row["seconds"]["assumptions"] = secs
        if killed:
            row["timeouts"].append(f"assumptions:{CHECKER_TIMEOUT_S}s")
        try:
            doc = json.loads(out.strip().splitlines()[-1])
        except Exception:
            doc = None
        if doc is None or "names" not in doc:
            row["strict_reason"] = ("checker_timeout" if killed
                                    else "checker_failed")
            row["build_log_tail"] = excerpt(out)
            row["category"] = categorize(row, None)
            row["seconds"]["total"] = round(time.time() - t_all, 2)
            return row
        row["assumptions"] = json.dumps(doc, separators=(",", ":"))
        ok, reason = strict_decision(doc["names"], probe_names)
        row["strict_solved"] = ok
        row["strict_reason"] = reason

        if want_ext:
            ext = task_dir / "audit" / "probes_ext.v"
            if ext.exists():
                shutil.copy(ext, pd / "probes_ext.v")
                rc, out, secs, killed = run_cmd(
                    [ROCQ, "compile", "-Q", str(theory_dir), "TaskLib",
                     "probes_ext.v"], pd, PROBES_TIMEOUT_S)
                row["seconds"]["ext"] = secs
                if killed:
                    # probes_ext.v is the heaviest artifact in the pipeline;
                    # a kill is never a semantic mismatch
                    row["timeouts"].append(f"ext:{PROBES_TIMEOUT_S}s")
                    row["ext"] = "timeout: " + excerpt(out, 2000)
                else:
                    row["ext"] = ("ok" if rc == 0
                                  else "fail: " + excerpt(out, 2000))

        row["category"] = categorize(row, None)
        row["seconds"]["total"] = round(time.time() - t_all, 2)
        log(f"[{aid}] strict={row['strict_solved']} ({row['strict_reason'][:60]}) "
            f"orig={row['original_solved']} cat={row['category']} "
            f"{row['seconds']}")
        return row
    finally:
        if not keep:
            shutil.rmtree(sb, ignore_errors=True)


def categorize(row, _):
    """A130 outcome categories.  toolchain wins over everything (the row is
    listed but excluded from agree/disagree); then the two disagreement
    classes; ext_mismatch only when the gate and the strict checker agree.

    Two rules keep the audit from asserting a disagreement it did not observe:
    ANY phase killed by its timeout (build, probes, assumptions, probes_ext)
    is `toolchain`, and so is an attempt whose ORIGINAL verdict could not be
    recovered -- with nothing to compare against, the row is unknown, never
    `agree`."""
    orig = row.get("original_solved")
    orig_reason = row.get("original_reason")
    strict = row.get("strict_solved")
    build_ok = row.get("build_ok")
    orig_build_ok = row.get("original_build_ok")
    if orig_build_ok is None and orig_reason is not None:
        # no verdict.json layers: the reason still tells build failures apart
        orig_build_ok = (None if orig_reason == "forbidden_token"
                         else orig_reason != "build_failed")
    if row.get("timeouts"):
        return "toolchain"
    if build_ok is not None and orig_build_ok is not None and build_ok != orig_build_ok:
        return "toolchain"
    if row.get("strict_reason") in ("no_workspace", "no_task_dir",
                                    "checker_failed", "checker_timeout",
                                    "probes_timeout", "build_timeout"):
        return "toolchain"
    if orig is None:
        return "toolchain"   # nothing to compare against
    if orig and not strict:
        return "gate_unsound"
    if orig is False and strict:
        return "gate_stricter"
    if strict and isinstance(row.get("ext"), str) and row["ext"].startswith("fail"):
        return "ext_mismatch"
    return "agree"


# --------------------------------------------------------------------------
# driver

_G = {}


def _init_worker(sandbox_root, want_ext, keep):
    _G["sandbox_root"] = sandbox_root
    _G["want_ext"] = want_ext
    _G["keep"] = keep


def _work(spec):
    try:
        return audit_attempt(spec, Path(_G["sandbox_root"]), _G["want_ext"],
                             _G["keep"])
    except Exception as e:  # never lose the rest of the sweep to one attempt
        row = dict(spec)
        row.pop("only_solved", None)
        row.update({"strict_solved": False, "strict_reason": f"driver_error: {e!r}",
                    "assumptions": None, "flags": None, "ext": None,
                    "category": "toolchain", "seconds": {}, "timeouts": [],
                    "build_log_tail": None, "timestamp": time.time()})
        return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=None)
    ap.add_argument("--tasks", nargs="*", default=None)
    ap.add_argument("--attempts", nargs="*", default=None,
                    help="explicit run/task__repN ids (smoke runs)")
    ap.add_argument("--only-solved", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--out", default=str(MAIN / "logs" / "audit_autoform"))
    ap.add_argument("--tmp", default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--ext", action="store_true")
    ap.add_argument("--keep-sandbox", action="store_true")
    args = ap.parse_args()

    if not CHECKER.exists():
        log(f"missing {CHECKER}\n  build it: cd {WORKTREE} && "
            f"dune build --root . src/audit/rocq_assumptions.exe")
        sys.exit(2)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sandbox_root = Path(args.tmp) if args.tmp else out.parent / "tmp"

    runs = in_scope_runs()
    if args.runs:
        want = set(args.runs)
        runs = [r for r in runs if r.name in want]
        missing = want - {r.name for r in runs}
        if missing:
            log(f"warning: not in scope / not found: {sorted(missing)}")

    specs = []
    for r in runs:
        specs.extend(attempts_of(r, args.only_solved))
    if args.tasks:
        specs = [s for s in specs if s["task"] in set(args.tasks)]
    if args.attempts:
        want = set(args.attempts)
        specs = [s for s in specs
                 if f"{s['run']}/{s['task']}__rep{s['rep']}" in want]
        missing = want - {f"{s['run']}/{s['task']}__rep{s['rep']}" for s in specs}
        if missing:
            log(f"warning: attempts not found: {sorted(missing)}")

    rows_path = out / "attempts.jsonl"
    if args.resume:
        done = {(r.get("run"), r.get("task"), r.get("rep"))
                for r in common.read_jsonl(rows_path)}
        before = len(specs)
        specs = [s for s in specs
                 if (s["run"], s["task"], s["rep"]) not in done]
        log(f"resume: {before - len(specs)} rows already present, "
            f"{len(specs)} to do")
    if args.limit:
        specs = specs[:args.limit]

    log(f"{len(specs)} attempts over {len(runs)} runs; jobs={args.jobs}; "
        f"out={out}")
    t0 = time.time()
    n = 0
    if args.jobs > 1:
        ctx = mp.get_context("fork")
        with ctx.Pool(args.jobs, initializer=_init_worker,
                      initargs=(str(sandbox_root), args.ext,
                                args.keep_sandbox)) as pool:
            for row in pool.imap_unordered(_work, specs):
                common.append_jsonl(rows_path, row)
                n += 1
                log(f"--- {n}/{len(specs)} done ({round(time.time()-t0)}s)")
    else:
        _init_worker(str(sandbox_root), args.ext, args.keep_sandbox)
        for spec in specs:
            row = _work(spec)
            common.append_jsonl(rows_path, row)
            n += 1
            log(f"--- {n}/{len(specs)} done ({round(time.time()-t0)}s)")
    log(f"finished {n} attempts in {round(time.time()-t0)}s -> {rows_path}")


if __name__ == "__main__":
    main()
