#!/bin/bash
# Describes the computer you are working on.
# Usage, inside the container:
#   bash tools/machine_info.sh GITHUB_USERNAME "laptop model, operating system"
# Writes members/GITHUB_USERNAME/machine.txt

set -euo pipefail
user=${1:?usage: bash tools/machine_info.sh GITHUB_USERNAME "laptop model, operating system"}
laptop=${2:?usage: bash tools/machine_info.sh GITHUB_USERNAME "laptop model, operating system"}
dir="$(cd "$(dirname "$0")/.." && pwd)/members/$user"
mkdir -p "$dir"
{
    echo "github_user: $user"
    echo "laptop: $laptop"
    echo "date: $(date -u '+%Y-%m-%d %H:%M UTC')"
    echo "cpus_in_container: $(nproc)"
    echo "architecture: $(uname -m)"
    echo "cpu: $(lscpu | awk -F': *' '/^(Model name|Vendor ID)/ {printf "%s ", $2}')"
    echo "kernel: $(uname -r)"
    echo "docker_memory_kb: $(awk '/^MemTotal/ {print $2}' /proc/meminfo)"
    echo "container_memory_limit: $(cat /sys/fs/cgroup/memory.max 2>/dev/null || echo unknown)"
    echo "container_swap_limit: $(cat /sys/fs/cgroup/memory.swap.max 2>/dev/null || echo unknown)"
} > "$dir/machine.txt"
cat "$dir/machine.txt"
