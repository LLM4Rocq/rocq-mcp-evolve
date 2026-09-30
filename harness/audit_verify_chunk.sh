#!/bin/bash
# One resumable chunk of the sibling re-verification audit for one run.
# Prints the driver's progress lines and its final "done:" line.  Repeat
# until the done line reports audited=0 (everything already present in
# the output file is skipped via --resume).  Each chunk stays well under
# a 10-minute wall (150 rows at ~1.4 s/row).
#
#   bash harness/audit_verify_chunk.sh RUN [CHUNK=150] [OUT_DIR=logs/audit_verify]
set -u
RUN="$1"; CHUNK="${2:-150}"; OUT_DIR="${3:-logs/audit_verify}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY=/Users/gbaudart/Project/llm4rocq/rocq-mcp/.venv-eval/bin/python
cd "$REPO" || exit 2
mkdir -p "$OUT_DIR"
"$PY" -u harness/audit_verify.py --run "$RUN" --which all --limit "$CHUNK" --resume \
    --out "$OUT_DIR/$RUN.jsonl" 2>&1 | grep -E '^\[audit|Traceback|Error:' | grep -v 'server {'
echo "[chunk] rows now in $OUT_DIR/$RUN.jsonl: $(wc -l < "$OUT_DIR/$RUN.jsonl" 2>/dev/null || echo 0)"
