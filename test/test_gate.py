#!/usr/bin/env python3
"""Suite D — correctness-gate soundness (see test/ARCHITECTURE.md).

Integration-level, no unit-test framework: imports the REAL gate
(harness/gate.py) and drives its `check` against crafted candidates, one case
per contract/regression. TAP-ish output ("ok - <name>" / "FAIL - <name>"),
prints a summary, and exits 1 on any failure.

The gate shells out to `rocq compile`, so `rocq` must be on PATH. This runs
both standalone (`python3 test/test_gate.py`) and under dune, where dune copies
`../harness` next to this script in a sandbox and invokes
`python3 %{dep:test_gate.py}` from the test dir. We therefore resolve the
harness relative to THIS SCRIPT (not cwd) and prepend the opam switch bin to
PATH so `rocq` is found regardless of the sandboxed layout.
"""

import os
import shutil
import sys
from pathlib import Path

# --- environment: make `rocq` findable before importing the gate -------------
# The pinned opam switch bin lives outside any dune sandbox, so its absolute
# location is hardcoded (per the suite spec); an env override wins if present.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_OPAM_BIN = os.path.join(os.path.dirname(_REPO_ROOT), "_opam", "bin")
_OPAM_BIN = os.environ.get("ROCQ_OPAM_BIN", _DEFAULT_OPAM_BIN)
os.environ["PATH"] = _OPAM_BIN + os.pathsep + os.environ.get("PATH", "")

# --- import the gate, resolving harness/ relative to this file ---------------
_HERE = Path(__file__).resolve().parent
_HARNESS = _HERE.parent / "harness"
if not (_HARNESS / "gate.py").exists():
    # Fallback: some sandbox layouts flatten differently; search nearby.
    for cand in (_HERE / "harness", _HERE.parent.parent / "harness"):
        if (cand / "gate.py").exists():
            _HARNESS = cand
            break
sys.path.insert(0, str(_HARNESS))

import gate  # noqa: E402  (gate.py; also pulls in harness/common.py)

# --- tiny TAP-ish runner -----------------------------------------------------
_count = 0
_failures = 0


def ok(cond, name, detail=""):
    global _count, _failures
    _count += 1
    if cond:
        print(f"ok - {name}", flush=True)
    else:
        _failures += 1
        suffix = f"  # {detail}" if detail else ""
        print(f"FAIL - {name}{suffix}", flush=True)


# --- fixtures ----------------------------------------------------------------
# F1 prefix (Reals): the pow2 auxiliary-fact proof is the canonical legit solve.
F1_PREFIX = (
    "From Stdlib Require Import Reals Psatz.\n"
    "Open Scope R_scope.\n\n"
    "Theorem t1 (x : R) : (x^6 + 1) / 2 >= x^3.\n"
)
# Trivial statement for the forbidden/tamper/recompile cases (fast, no imports).
FOO_PREFIX = "Theorem foo : True.\n"


def main():
    if shutil.which("rocq") is None:
        print("Bail out! `rocq` not on PATH (checked ROCQ_OPAM_BIN / "
              f"{_OPAM_BIN}); build/activate the opam switch first.",
              flush=True)
        sys.exit(1)

    # D1 — legit accept: the pow2 auxiliary-fact proof of F1 must be solved.
    r = gate.check(
        F1_PREFIX + "Proof. assert (H := pow2_ge_0 (x^3-1)). nra. Qed.\n",
        F1_PREFIX, "t1", timeout_s=60,
    )
    ok(r["solved"] is True, "D1 legit-accept (pow2 proof)", r["reason"])

    # D2 — assumption-introducing commands in the region are rejected outright.
    r = gate.check(FOO_PREFIX + "Proof. admit. Admitted.\n",
                   FOO_PREFIX, "foo", timeout_s=60)
    ok(not r["solved"] and str(r["reason"]).startswith("forbidden_token"),
       "D2 forbidden-token admit/Admitted", r["reason"])
    r = gate.check(FOO_PREFIX + "Axiom cheat : True.\n",
                   FOO_PREFIX, "foo", timeout_s=60)
    ok(not r["solved"] and str(r["reason"]).startswith("forbidden_token"),
       "D2 forbidden-token Axiom", r["reason"])

    # D3 — tampering with the shipped statement is caught by the prefix lock.
    r = gate.check("Theorem foo : False.\nProof. exact I. Qed.\n",
                   FOO_PREFIX, "foo", timeout_s=60)
    ok(not r["solved"] and r["reason"] == "prefix_modified",
       "D3 prefix-tamper", r["reason"])

    # D4 — comment/string desync exploit (measurement-review critical finding):
    # a crafted comment that hides `Admitted` must NOT be accepted. The exploit
    # string is exactly prefix + '\n(* "(*" *) Admitted.\n'.
    exploit = FOO_PREFIX + '\n(* "(*" *) Admitted.\n'
    r = gate.check(exploit, FOO_PREFIX, "foo", timeout_s=60)
    ok(r["solved"] is False, "D4 comment-desync exploit rejected", r["reason"])

    # D5 — target-is-axiom belt: an Admitted-into-axiom candidate is never a
    # solve. (The forbidden-token layer fires first; any rejection is fine as
    # long as solved is False — the belt is defense-in-depth behind it.)
    r = gate.check(FOO_PREFIX + "Admitted.\n", FOO_PREFIX, "foo", timeout_s=60)
    ok(r["solved"] is False, "D5 admitted-target rejected", r["reason"])

    # D6 — fresh recompile: a proof leaning on an in-session-only fact (H is
    # undefined in a clean file) must fail the from-scratch compile.
    r = gate.check(FOO_PREFIX + "Proof. exact H. Qed.\n",
                   FOO_PREFIX, "foo", timeout_s=60)
    ok(not r["solved"] and r["reason"] == "recompile_failed",
       "D6 fresh-recompile-failed", r["reason"])

    print(f"# suite D: {_count} checks, {_failures} failures", flush=True)
    sys.exit(1 if _failures else 0)


if __name__ == "__main__":
    main()
