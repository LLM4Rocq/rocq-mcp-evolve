#!/usr/bin/env bash
# One-command reproduction: fresh opam switch -> pinned deps -> build -> smoke run.
#
#   ./repro/setup.sh /path/to/new/switch-dir
#
# Recreates the experiment environment (OCaml 5.3.0, Rocq 9.1.1, Coquelicot
# 3.4.4, mathcomp 2.5.0, yojson 3.0.0 — full pin list in opam-packages.txt),
# builds the tool servers, and runs the harness self-test. Dataset dirs
# (rocq-workbook/, miniF2F-rocq/) are expected as siblings of the repo, as in
# the original layout. The eval itself additionally needs an authenticated
# `claude` CLI (>= 2.1.198) on PATH.
set -euo pipefail

SWITCH_DIR="${1:?usage: setup.sh <switch-dir>}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

opam switch create "$SWITCH_DIR" --packages ocaml-base-compiler.5.3.0 --yes
eval "$(opam env --switch="$SWITCH_DIR" --set-switch)"

opam repo add rocq-released https://rocq-prover.org/opam/released --this-switch --yes
opam repo add coq-released https://coq.inria.fr/opam/released --this-switch --yes

opam install --yes \
  dune.3.23.1 \
  yojson.3.0.0 \
  rocq-prover.meta.1 rocq-runtime.9.1.1 rocq-core.9.1.1 rocq-stdlib.9.1.0 \
  coq-coquelicot.3.4.4 coq-mathcomp-ssreflect.2.5.0

cd "$REPO"
dune build

# self-test: MCP handshake + one compile through the baseline server
python3 - <<'EOF'
import json, subprocess, sys, os
repo = os.getcwd()
msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-11-25", "clientInfo": {"name": "repro"}}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
     "params": {"name": "check", "arguments": {"content":
        "From Stdlib Require Import Reals.\nOpen Scope R_scope.\n"
        "Theorem repro_t (x : R) : x = x.\nProof. reflexivity. Qed.\n"}}},
]
p = subprocess.run(
    [f"{repo}/_build/default/src/baseline_server/rocq_agent_baseline.exe"],
    input="\n".join(json.dumps(m) for m in msgs) + "\n",
    capture_output=True, text=True, timeout=120)
lines = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
ok = any("exit code: 0" in str(l) for l in lines)
print("SELF-TEST", "PASSED" if ok else f"FAILED: {p.stdout[:500]}")
sys.exit(0 if ok else 1)
EOF

echo "Environment ready. Run an eval with e.g.:"
echo "  python3 harness/run_eval.py --config baseline --manifest smoke5 --reps 1"
echo "  python3 harness/report.py <run_id>"
