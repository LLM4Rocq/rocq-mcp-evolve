#!/usr/bin/env bash
# wait_then_run.sh <run_id> <target_count> <cmd...>: poll until the run has
# target_count records, then exec the command.
set -u
cd "$(dirname "$0")/.."
RUN=$1; TARGET=$2; shift 2
while true; do
  n=$(grep -c "" "logs/runs/$RUN/results.jsonl" 2>/dev/null || echo 0)
  [ "$n" -ge "$TARGET" ] && break
  sleep 60
done
sleep 30
echo "[wait_then_run] $RUN reached $TARGET; starting: $*"
exec "$@"
