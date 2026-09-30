#!/usr/bin/env python3
"""Generator for triadic/audit/probes_ext.v (A130 method 2: extended,
reference-derived probes).

Builds this task's `reference/` solution in a scratch sandbox, then for
each table below runs `Eval vm_compute in <expr>` on the *built reference*
(never by hand) and reads rocq's own printed normal form back as the
expected value. Emits probes_ext.v as a sequence of

    Example e_k : <expr> = <printed value>.
    Proof. vm_compute; reflexivity. Qed.

plus two non-vacuity witnesses (w_tstep_fixed, w_tstep_shrink_odd) that
combine the theorem's hypotheses and conclusion into one boolean, so a
submission whose side conditions make a theorem vacuous, or whose
`Step.tstep`/`Step.triad` disagree with the spec off the handful of points
`probes.v` already checks, fails to compile probes_ext.v.

`Props.chorus_sorted` and `Props.mem_chorus` are NOT re-pinned here: both
are already pinned in `probes.v` as exact universally-quantified Theorems
(`exact Props.chorus_sorted` / `exact Props.mem_chorus`), which — combined
with each other — already force `Props.chorus n` to be, for every n, the
unique strictly-sorted list with that membership set. Extra concrete
instances of those two would add nothing; see README.md "Not covered".

Usage:
    python3 gen_ext.py
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../data/autoform/triadic/audit
TASK = HERE.parent                               # .../data/autoform/triadic
REPO = TASK.parent.parent.parent                 # worktree root (dev-audit)
REFERENCE = TASK / "reference"
OUT = HERE / "probes_ext.v"

sys.path.insert(0, str(REPO / "harness"))
import common  # noqa: E402

ROCQ = str(common.OPAM_BIN / "rocq") if (common.OPAM_BIN / "rocq").exists() else "rocq"
DUNE = shutil.which("dune") or str(common.OPAM_BIN / "dune")

HEADER = (
    "From TaskLib Require Import Props Step Fixed Shrink.\n"
    "From mathcomp Require Import all_ssreflect all_algebra.\n"
)


def build_reference(sandbox: Path) -> Path:
    """Copy reference/ into sandbox (excluding _build) and dune build it.
    Returns the built theories directory."""
    dst = sandbox / "ref"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(REFERENCE, dst, ignore=shutil.ignore_patterns("_build"))
    env = common.prover_env()
    p = subprocess.run([DUNE, "build", "--root", "."], cwd=dst,
                        capture_output=True, text=True, env=env, timeout=300)
    if p.returncode != 0:
        sys.exit(f"reference dune build failed:\n{p.stdout}\n{p.stderr}")
    theories = dst / "_build" / "default" / "theories"
    assert theories.is_dir(), theories
    return theories


def rocq_list(xs) -> str:
    """A rocq `seq _` literal for a python list of already-stringified items."""
    return "[:: " + "; ".join(str(x) for x in xs) + "]"


# ---------------------------------------------------------------------
# The tables. Each entry is (name, expr) where `expr` is a rocq
# expression over Props/Step (required names only, plus stdlib/mathcomp)
# whose printed vm_compute value becomes the pinned RHS.
# ---------------------------------------------------------------------

def build_entries():
    entries = []

    # A. chorus, exhaustively for n = 1..80 (forces reduction, catches any
    #    opaque/non-computing or off-by-one chorus definition beyond what
    #    the exact-statement pins in probes.v already force set-wise).
    entries.append((
        "e_chorus_table",
        "map Props.chorus (iota 1 80)",
        80,
    ))

    # B. triad, for n = 1..300 (probes.v pins only one instance, triad 30).
    entries.append((
        "e_triad_table",
        "map Step.triad (iota 1 300)",
        300,
    ))

    # C. tstep, for n = 1..1500 (probes.v pins 10 instances). tstep costs
    #    O(n) to compute (a divisor filter over iota 1 n.-1), so this
    #    table alone costs O(sum 1..1500) vm_compute steps -- kept at
    #    1500 rather than a rounder 2000/3000 to hold the whole
    #    generator run to a few minutes wall-clock.
    entries.append((
        "e_tstep_table",
        "map Step.tstep (iota 1 1500)",
        1500,
    ))

    # D. the fixed-point property tstep(6*m) = 6*m, checked directly
    #    (not merely read off table C) across every m in 1..600 that
    #    satisfies the theorem's hypotheses (odd, not a multiple of 5,
    #    positive) -- well past table C's range (6*600 = 3600 > 1500).
    fixed_ms = [m for m in range(1, 601) if m % 2 == 1 and m % 5 != 0]
    lm = rocq_list(fixed_ms)
    entries.append((
        "e_fixed_family_holds",
        f"map (fun m => Step.tstep (6 * m) == 6 * m) {lm}",
        len(fixed_ms),
    ))

    # E. the shrink property tstep n < n, checked directly across every
    #    odd n in 3..3599 -- past table C's range.
    shrink_ns = [n for n in range(3, 3600, 2)]
    ln = rocq_list(shrink_ns)
    entries.append((
        "e_shrink_holds",
        f"map (fun n => Step.tstep n < n) {ln}",
        len(shrink_ns),
    ))

    # F/G. non-vacuity witnesses: one concrete instance per theorem-with-
    # hypotheses, combining "hypotheses hold" and "conclusion holds" (the
    # conclusion computed directly from Step.tstep/Step.triad, not by
    # invoking the theorem) into a single boolean.
    entries.append((
        "w_tstep_fixed",
        "[&& odd 101, ~~ (5 %| 101) & 0 < 101] && (Step.tstep (6 * 101) == 6 * 101)",
        1,
    ))
    entries.append((
        "w_tstep_shrink_odd",
        "(odd 201 && (1 < 201)) && (Step.tstep 201 < 201)",
        1,
    ))

    return entries


def run_generator(theories_dir: Path, entries, workdir: Path) -> list[str]:
    """Compile a .v file whose body is one `Eval vm_compute in <expr>.` per
    entry, in order, against `theories_dir`; return the printed values in
    order."""
    lines = [HEADER, "Set Printing Width 1000000.\n"]
    for name, expr, _n in entries:
        lines.append(f"(* {name} *)\n")
        lines.append(f"Eval vm_compute in ({expr}).\n")
    genfile = workdir / "gen_probe.v"
    genfile.write_text("".join(lines))
    env = common.prover_env()
    p = subprocess.run(
        [ROCQ, "compile", "-Q", str(theories_dir), "TaskLib", "gen_probe.v"],
        cwd=workdir, capture_output=True, text=True, env=env, timeout=600,
    )
    if p.returncode != 0:
        sys.exit(f"generator compile failed:\n{p.stdout}\n{p.stderr}")
    values = re.findall(r"\n\s*=\s(.*?)\n\s*:\s", "\n" + p.stdout, flags=re.S)
    if len(values) != len(entries):
        sys.exit(f"parsed {len(values)} values, expected {len(entries)} "
                  f"-- stdout was:\n{p.stdout}")
    return [v.strip() for v in values]


def emit_probes_ext(entries, values) -> str:
    out = [
        "(* AUTO-GENERATED by gen_ext.py -- do not hand-edit. *)\n",
        "(* A130 method 2: extended, reference-derived probes for w2_triadic. *)\n",
        "(* Every expected value below is rocq's own vm_compute normal form on\n",
        "   the task's reference/ solution -- none were typed by hand. *)\n",
        HEADER,
        "\n",
    ]
    for (name, expr, _n), val in zip(entries, values):
        out.append(f"Example {name} : {expr} = {val}.\n")
        out.append("Proof. vm_compute; reflexivity. Qed.\n\n")
    return "".join(out)


def main():
    import tempfile
    with tempfile.TemporaryDirectory(prefix="triadic_gen_ext_") as tmp:
        sandbox = Path(tmp)
        theories = build_reference(sandbox)
        entries = build_entries()
        workdir = sandbox / "gen"
        workdir.mkdir()
        values = run_generator(theories, entries, workdir)
        text = emit_probes_ext(entries, values)
        OUT.write_text(text)
        total = sum(n for _name, _expr, n in entries)
        print(f"wrote {OUT} ({len(entries)} examples, {total} pinned instances)")


if __name__ == "__main__":
    main()
