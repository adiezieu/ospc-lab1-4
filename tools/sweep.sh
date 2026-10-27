#!/bin/bash
# Runs the stats step with 1, 2, 4, 8 and 16 workers, three times each, and
# records the elapsed, user and system time of every run.
# Usage, inside the container, from the repository folder:
#   bash tools/sweep.sh GITHUB_USERNAME
# Writes members/GITHUB_USERNAME/sweep.csv. It takes a few minutes: do not
# run anything else on your laptop meanwhile.

set -euo pipefail
user=${1:?usage: bash tools/sweep.sh GITHUB_USERNAME}
cd "$(dirname "$0")/.."
mkdir -p "members/$user"
csv="members/$user/sweep.csv"
python3 steps/stats_prepare.py
echo "workers,run,elapsed_s,user_s,sys_s" > "$csv"
for run in 1 2 3; do
    for w in 1 2 4 8 16; do
        t=$( { /usr/bin/time -f "%e,%U,%S" env WORKERS=$w bash steps/stats.sh > /dev/null; } 2>&1 | tail -1 )
        echo "$w,$run,$t" | tee -a "$csv"
    done
done
echo "Saved $csv"
