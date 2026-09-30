#!/usr/bin/env python3
"""
gen_ext.py -- generator for data/autoform/ledger/audit/probes_ext.v

Method (2) of docs/ASSUMPTIONS.md A130: an extended probe file whose
expected values are COMPUTED from the gate-validated reference (never
hand-typed), on far more concrete instances than probes.v, restricted to
the task's required names (Entries.*, Balance.*, Replay.*, Bounds.*) plus
stdlib/mathcomp.

How it works
------------
1. Build the reference solution (data/autoform/ledger/reference) in a fresh
   sandbox with `dune build --root .`.
2. Emit a "driver" .v file: the same opening prelude as probes.v, a handful
   of local helper `Definition`s (built only from stdlib/mathcomp, used to
   synthesize many concrete ledgers/entries/states -- never touching a
   TaskLib-required name themselves), and one `Eval vm_compute in EXPR.`
   command per table we want pinned.
3. Compile the driver against the reference build with `rocq compile` and
   capture stdout. `Set Printing Width` is cranked up so every printed
   value lands on a single line.
4. Parse the "= VALUE\n     : TYPE" blocks in order (one per Eval, in
   source order) and pair each back up with the EXPR that produced it.
5. Emit probes_ext.v: the same helper Definitions, then one
   `Example name : EXPR = VALUE. Proof. vm_compute; reflexivity. Qed.`
   per table, plus the swap_disjoint non-vacuity witness and three
   type-alias identities (checked with plain `reflexivity`, since Eval
   does not apply to Type-sorted terms).
6. Re-run the whole thing once more against the reference build as a
   well-posedness check (the emitted file must also compile clean).

Nothing here ever types an expected numeral by hand: every RHS in
probes_ext.v is lifted verbatim out of rocq's own stdout for this
generator run.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../data/autoform/ledger/audit
TASK_DIR = HERE.parent                          # .../data/autoform/ledger
REFERENCE_DIR = TASK_DIR / "reference"
OUT_FILE = HERE / "probes_ext.v"

# Locate the opam switch bin dir the same way harness/common.py does:
# walk up from this file until we find a directory containing "_opam".
def _find_opam_bin() -> Path:
    env_override = os.environ.get("OPAM_BIN")
    if env_override:
        return Path(env_override)
    p = HERE
    for _ in range(12):
        cand = p / "_opam" / "bin"
        if cand.is_dir():
            return cand
        p = p.parent
    # fall back to the known absolute path documented for this task
    return Path("/Users/gbaudart/Project/llm4rocq/rocq-tools/_opam/bin")


OPAM_BIN = _find_opam_bin()
ROCQ = os.environ.get("ROCQ_BIN", str(OPAM_BIN / "rocq"))
DUNE = os.environ.get("DUNE_BIN", str(OPAM_BIN / "dune"))

# ---------------------------------------------------------------------------
# The shared preamble -- identical opening lines to probes.v, so probes_ext.v
# type-checks against any submission that already passes probes.v.
# ---------------------------------------------------------------------------
PREAMBLE = """From TaskLib Require Import Entries Balance Replay Bounds.
From mathcomp Require Import all_ssreflect all_algebra.
Import Order.TTheory GRing.Theory Num.Theory.
Local Open Scope ring_scope.
"""

# Local helper definitions: only stdlib/mathcomp combinators (iota, seq,
# odd, modn, Posz, ring arithmetic) plus the *required* type names Entries.
# entry / Entries.ledger / Balance.state used purely as ascribed result
# types (to double-check those aliases really are what the spec pins).
# No TaskLib *value* name (bal, total, step, replay, ...) is referenced
# here -- those only ever appear in the tables below.
HELPERS = """
(* ---- table-driving helpers: stdlib/mathcomp only, no TaskLib values ---- *)

Definition mk_ledgerA (n : nat) : Entries.ledger :=
  [seq (((i * 7 + 3) %% 6)%N, Posz (i %% 11)%N - 5) | i <- iota 0 n].

Definition mk_ledgerB (n : nat) : Entries.ledger :=
  [seq ((i %% 4)%N,
        if odd i then Posz (i %% 13)%N else - Posz (i %% 9)%N) | i <- iota 0 n].

Definition mk_ledgerC (n : nat) : Entries.ledger :=
  [seq ((i %% 9)%N, Posz ((i * i) %% 17)%N - 8) | i <- iota 0 n].

Definition mk_entry (n : nat) : Entries.entry :=
  ((n %% 6)%N, Posz (n %% 15)%N - 7).

Definition s_lin : Balance.state := fun a => Posz a.

Definition lens : seq nat := [:: 0; 1; 2; 3; 5; 8; 13; 21; 34; 55; 89; 144].
Definition plens : seq nat := [:: 0; 4; 11; 27; 63; 140].
Definition qlens : seq nat := [:: 1; 3; 9; 22; 58; 133].
"""

# ---------------------------------------------------------------------------
# The tables. Each entry: (name, expr) where expr is a Rocq term of type
# int, bool, or seq of those -- something Eval vm_compute in can print on
# one line, and something an Example can then pin by equality.
# ---------------------------------------------------------------------------
TABLES = []


def add(name, expr):
    TABLES.append((name, expr))


# --- Entries.total, three ledger families, n = 0..299 -----------------
for fam in "ABC":
    add(f"ext_total_{fam}",
        f"map (fun n => Entries.total (mk_ledger{fam} n)) (iota 0 300)")

# --- Entries.bal, fixed-length-250 ledger, accounts 0..299 (many miss) --
for fam in "ABC":
    add(f"ext_bal_acct_{fam}",
        f"map (fun a => Entries.bal a (mk_ledger{fam} 250)) (iota 0 300)")

# --- Entries.bal grid: length (from lens) x account (0..9) -------------
for fam in "ABC":
    add(f"ext_bal_grid_{fam}",
        f"flatten [seq [seq Entries.bal a (mk_ledger{fam} n) | a <- iota 0 10] "
        f"| n <- lens]")

# --- Bounds.no_teleport, boolean table, three families, n = 0..299 -----
for fam in "ABC":
    add(f"ext_no_teleport_{fam}",
        f"map (fun n => `|Entries.bal (n %% 11)%N (mk_ledger{fam} n)| "
        f"<= Entries.total (mk_ledger{fam} n)) (iota 0 300)")

# --- Balance.replay from zero_state, three families, n = 0..199 --------
for fam in "ABC":
    add(f"ext_replay_zero_{fam}",
        f"map (fun n => Balance.replay Balance.zero_state (mk_ledger{fam} n) "
        f"(n %% 7)%N) (iota 0 200)")

# --- Balance.replay from a nonzero state s_lin, grid over lens x accts -
for fam in "ABC":
    add(f"ext_replay_lin_{fam}",
        f"flatten [seq [seq Balance.replay s_lin (mk_ledger{fam} n) a "
        f"| a <- iota 0 6] | n <- lens]")

# --- Balance.step, single application, from zero_state and from s_lin --
add("ext_step_zero",
    "map (fun n => Balance.step Balance.zero_state (mk_entry n) (n %% 6)%N) "
    "(iota 0 150)")
add("ext_step_lin",
    "map (fun n => Balance.step s_lin (mk_entry n) (n %% 6)%N) (iota 0 150)")

# --- Balance.zero_state itself, direct table ----------------------------
add("ext_zero_state", "map Balance.zero_state (iota 0 50)")

# --- Replay.replay_cat: grid over (plens x qlens) x accounts -----------
add("ext_replay_cat",
    "flatten [seq [seq [seq Balance.replay s_lin "
    "(mk_ledgerA p ++ mk_ledgerC q) a | a <- iota 0 6] | q <- qlens] | p <- plens]")

# --- Replay.checkpoint_bal: grid over (plens x qlens) x accounts -------
add("ext_checkpoint_bal",
    "flatten [seq [seq [seq Balance.replay "
    "(Balance.replay Balance.zero_state (mk_ledgerB p)) (mk_ledgerA q) a "
    "| a <- iota 0 6] | q <- qlens] | p <- plens]")

# --- swap_disjoint: step order-invariance grid on guaranteed-disjoint ---
#     accounts (mk_entry (2*n) and mk_entry (2*n+1) always land on
#     different residues mod 6, since 6 is even so parity is preserved)
add("ext_swap_step",
    "flatten [seq [seq Balance.step (Balance.step s_lin (mk_entry (2 * n)%N)) "
    "(mk_entry (2 * n + 1)%N) a | a <- iota 0 6] | n <- iota 0 40]")

# ---------------------------------------------------------------------------


def run_rocq(vfile: Path, theories_dir: Path, cwd: Path) -> str:
    cmd = [ROCQ, "compile", "-Q", str(theories_dir), "TaskLib", vfile.name]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(
            f"rocq compile failed on {vfile}:\n--- stdout ---\n{r.stdout}\n"
            f"--- stderr ---\n{r.stderr}"
        )
    return r.stdout + r.stderr


def build_reference(sandbox: Path) -> Path:
    ref_copy = sandbox / "ref"
    if ref_copy.exists():
        shutil.rmtree(ref_copy)
    shutil.copytree(REFERENCE_DIR, ref_copy, ignore=shutil.ignore_patterns("_build"))
    r = subprocess.run([DUNE, "build", "--root", "."], cwd=ref_copy,
                        capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"dune build of reference failed:\n{r.stdout}\n{r.stderr}")
    theories = ref_copy / "_build" / "default" / "theories"
    assert (theories / "Bounds.vo").exists(), "reference build missing Bounds.vo"
    return theories


EVAL_BLOCK_RE = re.compile(r"^\s*=\s(?P<val>.*?)\s*$\n\s*:\s", re.M)


def parse_eval_outputs(stdout: str, n_expected: int):
    """Extract the n_expected '= VALUE\\n     : TYPE' blocks, in order."""
    vals = []
    for m in EVAL_BLOCK_RE.finditer(stdout):
        vals.append(m.group("val"))
    if len(vals) < n_expected:
        raise RuntimeError(
            f"expected {n_expected} Eval results, only parsed {len(vals)} "
            f"from stdout:\n{stdout[-4000:]}"
        )
    # Some noise lines (coercion-path warnings etc.) never match "= ... :"
    # at line start the way Eval results do, so the *last* n_expected
    # matches are the ones we want (in case any leaked through).
    return vals[-n_expected:]


def build_driver_source():
    lines = [PREAMBLE, "Set Printing Width 1000000.\n", HELPERS]
    for _name, expr in TABLES:
        lines.append(f"Eval vm_compute in ({expr}).")
    return "\n".join(lines) + "\n"


def build_probes_ext_source(values):
    lines = [PREAMBLE, HELPERS]
    lines.append("(* ===== type-alias identities (forced by the required-names spec) ===== *)")
    lines.append("Example e_entry_type : Entries.entry = (nat * int)%type.")
    lines.append("Proof. reflexivity. Qed.")
    lines.append("Example e_ledger_type : Entries.ledger = seq (nat * int).")
    lines.append("Proof. reflexivity. Qed.")
    lines.append("Example e_state_type : Balance.state = (nat -> int).")
    lines.append("Proof. reflexivity. Qed.")
    lines.append("")
    lines.append("(* ===== non-vacuity witness for Balance.swap_disjoint's hypothesis ===== *)")
    lines.append("Example w_swap_disjoint :")
    lines.append("  ((mk_entry 0).1 != (mk_entry 1).1) = true.")
    lines.append("Proof. vm_compute; reflexivity. Qed.")
    lines.append("")
    lines.append("(* ===== reference-computed tables (never hand-typed) ===== *)")
    for (name, expr), val in zip(TABLES, values):
        lines.append(f"Example {name} :")
        lines.append(f"  ({expr}) = {val}.")
        lines.append("Proof. vm_compute; reflexivity. Qed.")
        lines.append("")
    return "\n".join(lines)


def compile_and_check(vfile: Path, theories_dir: Path, label: str):
    cwd = vfile.parent
    out = run_rocq(vfile, theories_dir, cwd)
    print(f"[ok] {label}: {vfile.name} compiled against {theories_dir}")
    return out


def main():
    sandbox = Path(os.environ.get(
        "EXT_LEDGER_SANDBOX",
        "/private/tmp/claude-501/-Users-gbaudart-Project-llm4rocq-rocq-tools/"
        "92fd7af9-6dfb-42f7-ad3c-3a89b1b13ece/scratchpad/ext-ledger-gen"))
    sandbox.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] building reference in sandbox: {sandbox}")
    theories_dir = build_reference(sandbox)

    print(f"[2/4] running the driver ({len(TABLES)} Eval commands) against the reference")
    drv_dir = sandbox / "driver"
    drv_dir.mkdir(exist_ok=True)
    drv_file = drv_dir / "driver.v"
    drv_file.write_text(build_driver_source())
    stdout = compile_and_check(drv_file, theories_dir, "driver")
    values = parse_eval_outputs(stdout, len(TABLES))

    print(f"[3/4] writing {OUT_FILE}")
    OUT_FILE.write_text(build_probes_ext_source(values))

    print("[4/4] well-posedness check: compiling probes_ext.v against the reference")
    wp_dir = sandbox / "wp"
    wp_dir.mkdir(exist_ok=True)
    wp_file = wp_dir / "probes_ext.v"
    wp_file.write_text(OUT_FILE.read_text())
    compile_and_check(wp_file, theories_dir, "well-posedness")

    n_examples = 3 + 1 + len(TABLES)  # 3 type aliases + 1 witness + tables
    print(f"done: {n_examples} Examples written to {OUT_FILE}")


if __name__ == "__main__":
    main()
