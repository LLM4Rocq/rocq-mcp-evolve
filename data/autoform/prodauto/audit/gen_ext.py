#!/usr/bin/env python3
"""Generator for data/autoform/prodauto/audit/probes_ext.v (audit method 2, A130).

Every expected value in the generated file is harvested by actually running
`rocq compile` against the gate-validated reference build and capturing the
printed `Compute` results -- nothing here is typed by hand. Run:

    python3 gen_ext.py [--ref-theories DIR] [--rocq PATH]

Defaults assume this script sits at data/autoform/prodauto/audit/gen_ext.py
and that a built reference theory directory is passed explicitly (see
README.md for the exact sandbox build command used to produce it), because
the frozen main checkout must never be built into.
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK_DIR = HERE.parent

# Same opening lines as probes.v, so probes_ext.v type-checks against any
# submission that already passes probes.v.
PRELUDE = (
    "From TaskLib Require Import Dfa Ops Lang Empty Pump Main.\n"
    "From mathcomp Require Import all_ssreflect all_algebra.\n"
)

# Auxiliary word-generators used only inside this probe file (not required
# names, but built exclusively from stdlib/mathcomp primitives so they
# type-check against ANY submission that exposes the required names).
HELPERS = """
(* ----- auxiliary word generators (stdlib/mathcomp only, not required
   names) used to build the concrete instances below ----- *)

(* [wlen n] cycles the word length 1..15 as n grows, so table entries mix
   many different lengths, not just one. *)
Definition wlen (n : nat) : nat := (n %% 15).+1.

(* [word n] is the length-(wlen n) word whose bits are n's own binary
   digits: this varies both the word length and the number/placement of
   [true]s (not just constant-symbol words), so it stresses the transition
   on [false] as well as [true]. *)
Definition word (n : nat) : seq bool :=
  [seq odd (n %/ 2 ^ i) | i <- iota 0 (wlen n)].

(* [bits k n] is the fixed-length-k word given by the low k binary digits
   of n; ranging n over [iota 0 (2^k)] enumerates EVERY length-k word
   exactly once (exhaustive, not sampled). *)
Definition bits (k n : nat) : seq bool :=
  [seq odd (n %/ 2 ^ i) | i <- iota 0 k].
"""

# Each table: (name, coq expression template with {n} for the bound
# variable, upper bound N (map is taken over (iota 0 N)), one-line comment).
# Every one only uses Required names (Dfa.accepts / Dfa.run / Pump.trace /
# Dfa.start / Ops.dprod / Ops.dcompl / Main.parity / Main.mod3 /
# Main.prod23) plus the local word/bits helpers and stdlib/mathcomp.
TABLES = [
    ("acc_parity_word",
     "Dfa.accepts Main.parity (word {n})", 1000,
     "Dfa.accepts on Main.parity over 1000 mixed-length/mixed-content words"),
    ("acc_mod3_word",
     "Dfa.accepts Main.mod3 (word {n})", 1000,
     "Dfa.accepts on Main.mod3 over 1000 mixed-length/mixed-content words"),
    ("acc_prod23_word",
     "Dfa.accepts Main.prod23 (word {n})", 1000,
     "Dfa.accepts on Main.prod23 over 1000 mixed words"),
    ("acc_dprod_fresh_word",
     "Dfa.accepts (Ops.dprod Main.parity Main.mod3) (word {n})", 1000,
     "Ops.dprod built fresh from parity/mod3 (independent of how the "
     "submission implemented Main.prod23 itself)"),
    ("acc_dcompl_parity_word",
     "Dfa.accepts (Ops.dcompl Main.parity) (word {n})", 1000,
     "Ops.dcompl of Main.parity"),
    ("acc_dcompl_mod3_word",
     "Dfa.accepts (Ops.dcompl Main.mod3) (word {n})", 1000,
     "Ops.dcompl of Main.mod3"),
    ("acc_bits10_parity",
     "Dfa.accepts Main.parity (bits 10 {n})", 1024,
     "EXHAUSTIVE over all 1024 length-10 words"),
    ("acc_bits10_mod3",
     "Dfa.accepts Main.mod3 (bits 10 {n})", 1024,
     "EXHAUSTIVE over all 1024 length-10 words"),
    ("acc_bits10_prod23",
     "Dfa.accepts Main.prod23 (bits 10 {n})", 1024,
     "EXHAUSTIVE over all 1024 length-10 words"),
    ("acc_nested_prod",
     "Dfa.accepts (Ops.dprod Main.prod23 Main.parity) (word {n})", 500,
     "a doubly-nested product (state type (('I_2*'I_3)*'I_2)) exercising "
     "Ops.dprod's genericity beyond the two fixed Main instances"),
    ("trace_len_word",
     "size (Pump.trace Main.parity (word {n}))", 1000,
     "Pump.trace length vs. word length, over 1000 mixed-length words"),
    ("trace_last_run_parity_word",
     "Dfa.run Main.parity (word {n}) == "
     "last (Dfa.start Main.parity) (Pump.trace Main.parity (word {n}))",
     1000,
     "Pump.trace's last state agrees with Dfa.run, on Main.parity"),
    ("trace_last_run_prod23_word",
     "Dfa.run Main.prod23 (word {n}) == "
     "last (Dfa.start Main.prod23) (Pump.trace Main.prod23 (word {n}))",
     500,
     "same consistency check on the 6-state product"),
]

# A few boundary-case scalars, harvested the same way (never hand-typed).
SCALARS = [
    ("acc_parity_empty", "Dfa.accepts Main.parity [::]",
     "the empty word has 0 (even) trues"),
    ("acc_mod3_empty", "Dfa.accepts Main.mod3 [::]",
     "the empty word has 0 (a multiple of 3) trues"),
    ("acc_prod23_empty", "Dfa.accepts Main.prod23 [::]",
     "product of the two above"),
    ("acc_parity_single_true", "Dfa.accepts Main.parity [:: true]",
     "one true is odd"),
]

# Witnesses / theorem-derived facts: these are proved with tactics from the
# required Lemmas themselves (Lang.accepts_prod, Lang.accepts_compl,
# Empty.nonemptyP, Pump.accepts_long_dup), not by vm_compute -- because
# Empty.v's card/enum/connect machinery does not reduce under vm_compute in
# this toolchain (see README.md "Not covered"). They are still genuine
# extended probes: they hold only if the required THEOREMS actually compose
# with the required DEFINITIONS as intended, which a vacuous/inconsistent
# implementation (e.g. one abusing a guardedness-check bypass on a
# recursive definition) need not satisfy even if its Print Assumptions is
# clean.
WITNESSES = '''
(* ===== witnesses / theorem-derived checks (proved, not vm_compute) =====

   Empty.dstep / Empty.reachable / Empty.nonemptyb are built from
   #|_| / enum / connect, and #|'I_2| itself does not reduce to a literal
   under vm_compute in this Rocq 9.1.1 + mathcomp 2.5.0 toolchain (verified
   independently -- see README.md). So instead of computing nonemptyb
   directly, these checks derive concrete nonemptyb facts from the
   required theorems (Lang.accepts_prod, Lang.accepts_compl,
   Empty.nonemptyP) applied to concrete automata, which only needs
   plain proof search plus the mathcomp cardinality lemmas card_ord /
   card_prod (not vm_compute on Empty.v's own definitions). *)

(* -- non-vacuity witness for Pump.accepts_long_dup's hypothesis -- *)

Lemma w_card_parity : #|{: 'I_2}| = 2.
Proof. exact: card_ord. Qed.

Lemma w_card_prod23 : #|{: 'I_2 * 'I_3}| = 6.
Proof. by rewrite card_prod !card_ord. Qed.

(* the hypothesis #|S| < size w is satisfiable with the submission's own
   Main.parity (2 states) ... *)
Example w_accepts_long_dup_parity :
  ~~ uniq (Pump.trace Main.parity [:: true; false; true]).
Proof. apply: Pump.accepts_long_dup. by rewrite w_card_parity. Qed.

(* ... and with the 6-state Main.prod23. *)
Example w_accepts_long_dup_prod23 :
  ~~ uniq (Pump.trace Main.prod23
             [:: true; true; true; true; true; true; true]).
Proof. apply: Pump.accepts_long_dup. by rewrite w_card_prod23. Qed.

(* -- theorem-derived nonemptyb facts (no hypotheses to witness, but
   these compose Lang.accepts_prod / Lang.accepts_compl / Empty.nonemptyP
   in a way a vacuous or inconsistent implementation need not satisfy) -- *)

(* the product of ANY automaton with its own complement is the empty
   language -- purely from the required equalities, for every dfa. *)
Lemma w_empty_selfcompl :
  forall (S : finType) (A : Dfa.dfa S) w,
    Dfa.accepts (Ops.dprod A (Ops.dcompl A)) w = false.
Proof.
move=> S A w; rewrite Lang.accepts_prod Lang.accepts_compl.
by rewrite andbN.
Qed.

Example w_nonemptyb_selfcompl_parity :
  ~~ Empty.nonemptyb (Ops.dprod Main.parity (Ops.dcompl Main.parity)).
Proof.
apply/negP => /Empty.nonemptyP [w hw].
by move: hw; rewrite w_empty_selfcompl.
Qed.

Example w_nonemptyb_selfcompl_prod23 :
  ~~ Empty.nonemptyb (Ops.dprod Main.prod23 (Ops.dcompl Main.prod23)).
Proof.
apply/negP => /Empty.nonemptyP [w hw].
by move: hw; rewrite w_empty_selfcompl.
Qed.

(* dually, the complement of that empty-language automaton accepts
   everything, so in particular it is nonempty. *)
Example w_nonemptyb_full_parity :
  Empty.nonemptyb (Ops.dcompl (Ops.dprod Main.parity (Ops.dcompl Main.parity))).
Proof.
apply/Empty.nonemptyP; exists [::].
by rewrite Lang.accepts_compl w_empty_selfcompl.
Qed.

(* Empty.nonemptyb of Main.parity / Main.mod3 themselves, established
   through Empty.nonemptyP plus the harvested empty-word/single-symbol
   facts above (fresh instances not already covered by probes.v, which
   only pins Main.prod23_nonempty). *)
Example w_nonemptyb_parity :
  Empty.nonemptyb Main.parity.
Proof. apply/Empty.nonemptyP; exists [::]; exact: acc_parity_empty. Qed.

Example w_nonemptyb_mod3 :
  Empty.nonemptyb Main.mod3.
Proof. apply/Empty.nonemptyP; exists [::]; exact: acc_mod3_empty. Qed.

Example w_nonemptyb_dcompl_parity :
  Empty.nonemptyb (Ops.dcompl Main.parity).
Proof.
apply/Empty.nonemptyP; exists [:: true].
by rewrite Lang.accepts_compl acc_parity_single_true.
Qed.
'''


def run_rocq(rocq, ref_theories, harvest_file, work_dir):
    cmd = [rocq, "compile", "-Q", str(ref_theories), "TaskLib",
           str(harvest_file.name)]
    proc = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True)
    return proc


def parse_results(stdout, expected_count):
    """Extract each `= ...` result line (values only, `Set Printing Width`
    keeps every result on one line) in the order the Compute commands
    appear."""
    lines = [l for l in stdout.split("\n") if l.startswith("     = ")]
    if len(lines) != expected_count:
        raise SystemExit(
            f"expected {expected_count} Compute results, got {len(lines)}; "
            f"first few: {lines[:3]}")
    return [l[len("     = "):] for l in lines]


def build_harvest(ref_theories_placeholder):
    lines = ["Set Printing Width 1000000.", PRELUDE.rstrip("\n"), HELPERS]
    order = []
    for name, tmpl, n, _ in TABLES:
        expr = tmpl.format(n="n")
        lines.append(f"Compute (map (fun n => {expr}) (iota 0 {n})).")
        order.append(("table", name, tmpl, n))
    for name, expr, _ in SCALARS:
        lines.append(f"Compute ({expr}).")
        order.append(("scalar", name, expr, None))
    return "\n".join(lines) + "\n", order


def render_probes_ext(order, values):
    out = [
        "(* probes_ext.v -- reference-derived extended probes for prodauto "
        "(A130 audit method 2).",
        "   GENERATED by gen_ext.py -- every expected value below was ",
        "   harvested by compiling this file's Compute commands against the",
        "   gate-validated reference build; nothing is typed by hand.",
        "   Do not hand-edit; re-run `python3 gen_ext.py` instead. *)",
        PRELUDE.rstrip("\n"),
        HELPERS,
        "(* ===== computed tables (vm_compute) ===== *)",
    ]
    vi = iter(values)
    for kind, name, tmpl_or_expr, n in order:
        val = next(vi)
        if kind == "table":
            expr = tmpl_or_expr.format(n="n")
            out.append(f"Example e_{name} :")
            out.append(f"  map (fun n => {expr}) (iota 0 {n}) = {val}.")
            out.append("Proof. vm_compute; reflexivity. Qed.\n")
        else:
            out.append(f"Example {name} : {tmpl_or_expr} = {val}.")
            out.append("Proof. vm_compute; reflexivity. Qed.\n")
    out.append(WITNESSES.strip("\n"))
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-theories", required=True,
                     help="built reference theories dir "
                          "(.../reference-sandbox/_build/default/theories)")
    ap.add_argument("--rocq",
                     default="/Users/gbaudart/Project/llm4rocq/rocq-tools/"
                             "_opam/bin/rocq")
    ap.add_argument("--out", default=str(TASK_DIR / "audit" / "probes_ext.v"))
    args = ap.parse_args()

    ref_theories = Path(args.ref_theories).resolve()
    if not ref_theories.is_dir():
        raise SystemExit(f"reference theories dir not found: {ref_theories}")

    harvest_src, order = build_harvest(ref_theories)

    with tempfile.TemporaryDirectory(prefix="prodauto_gen_ext_") as td:
        work = Path(td)
        harvest_file = work / "harvest.v"
        harvest_file.write_text(harvest_src)
        proc = run_rocq(args.rocq, ref_theories, harvest_file, work)
        if proc.returncode != 0 and "Error" in proc.stdout:
            sys.stderr.write(proc.stdout)
            sys.stderr.write(proc.stderr)
            raise SystemExit("harvest compile failed")
        values = parse_results(proc.stdout, len(order))

    content = render_probes_ext(order, values)
    out_path = Path(args.out)
    out_path.write_text(content)
    print(f"wrote {out_path} ({len(content)} bytes, {len(order)} tables/scalars)")


if __name__ == "__main__":
    main()
