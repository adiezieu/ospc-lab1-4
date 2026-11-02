#!/bin/bash
# Bootstrap 95% confidence intervals for the average order value of every
# region and month. The work is split among WORKERS processes that run at
# the same time.

# GenAI note:this fix was done with the advise of Claude (Anthropic). Prompt: 'help me check that fix of Task 5 of Lab 1 works fine and syntax is correct, stats.sh uses too many workers and leaves them running after Ctrl-C'.
set -euo pipefail
cd "$(dirname "$0")/.."

# One worker per CPU of the container. More workers than CPUs only compete for them.
WORKERS=${WORKERS:-$(nproc)}
OUT=${OUT:-$HOME/data/out}

# Background jobs of a script ignore Ctrl-C, so stop the workers by hand on any exit.
pids=()
cleanup() {
    if [ "${#pids[@]}" -gt 0 ]; then
        kill "${pids[@]}" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

python3 steps/stats_prepare.py
mkdir -p "$OUT/stats"
rm -f "$OUT"/stats/part_*.csv
for k in $(seq 0 $((WORKERS - 1))); do
    python3 steps/stats_worker.py "$k" "$WORKERS" &
    pids+=($!)
done
# Wait for each worker, so that a failed worker stops the script.
for pid in "${pids[@]}"; do
    wait "$pid"
done
cat "$OUT"/stats/part_*.csv | sort > "$OUT/stats.csv"
echo "stats: done with $WORKERS workers"
