#!/usr/bin/env bash
# Auto-chain: when the control run completes (120 records), run the next two
# ladder configs with identical protocol (dev60, 2 reps, parallel=4).
set -u
cd "$(dirname "$0")/.."
TARGET=120
while true; do
  n=$(grep -c "" logs/runs/baseline_dev60/results.jsonl 2>/dev/null || echo 0)
  [ "$n" -ge "$TARGET" ] && break
  sleep 60
done
sleep 30
echo "[chain] control complete, starting session_dev60 $(date)"
caffeinate -dims python3 harness/run_eval.py --config session --manifest dev60 --reps 2 --parallel 4 --run-id session_dev60
echo "[chain] starting session_try_dev60 $(date)"
caffeinate -dims python3 harness/run_eval.py --config session_try --manifest dev60 --reps 2 --parallel 4 --run-id session_try_dev60
echo "[chain] all done $(date)"
