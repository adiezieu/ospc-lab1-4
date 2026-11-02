# Measurements: adiezieu

## Warm-up: permissions
- `ls -l run_report.sh` before chmod: -rw-r--r--
- `ls -l run_report.sh` after chmod: -rwxr-xr-x

## Task 1: report.py memory
| Orders | Table size | Peak memory (KB) |
|---|---|---|
| 1,000,000 |106 MiB|109236 KB peak memory ~107 MiB |
| 2,000,000 |211 MiB |110428 KB peak memory ~108 MiB |
| 4,000,000 |423 MiB |1567920 KB peak memory ~1.5GB|
- Exit status of the full run: 137
- oom_kill in memory.events (before / after): 0/1 (before/after)

## Task 2: extracts.sh
- Exit status of script: Done
- PIPESTATUS of the grep pipeline: 2 0 0

## Task 3: audit.py
| Run | Elapsed | User | System | Peak memory |
|---|---|---|---|---|
| Sample (100k) |0.67 |1.14 | 0.13| 126692 KB peak memory|
| Full (8.4M) |40.98 |31.07 |10.51 |632608 KB peak memory |
- strace -c: openat / write / close counts: 100,686 / 100,001 / 100,673
- System share: 10.51 / (31.07 + 10.51) = about 25.3% of CPU time in the kernel
* With fix -> strace -c: openat / write / close counts: 686 / 17 / 673

## Task 4: Segmenting the Orders
| Run | Elapsed | User | System | Peak memory |
|---|---|---|---|---|
| 100k Sample |0.57 |1.14 | 0.04| 132320 KB peak memory|
| cProfile Sample |0.24 |0.83 |0.02 |148780 KB peak memory |
* Profiling `segments.py` with `cProfile` revealed that row-by-row iteration (`itertuples`) and per-record string parsing (`strptime`) accounted for over 55% of CPU time; replacing row operations with vectorized Pandas/NumPy expressions reduced the full dataset runtime to just 6.26 seconds.

## Task 5: stats.sh

* `./run_report.sh` printed `stats: done with 16 workers on a container with 8 CPUs.`

Sweep (`members/adiezieu/sweep.csv`), median elapsed of 3 runs:

| Workers | 1 | 2 | 4 | 8 | 16 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Elapsed (s)** | 29.22 | 15.02 | 8.08 | 6.92 | 7.66 |

* Time halves from 1 to 2 to 4 workers (linear scaling with physical cores), flattens at 8 cores, and gets slower at 16 workers.
* User CPU time increases significantly with more workers (from ~29 s with 1 worker to >55 s with 16 workers) due to OS scheduling overhead and context switching.

Ctrl-C test (`bash steps/stats.sh`, Ctrl-C a few seconds after `stats: input ready`):

* `echo $?` printed 130 (128 + 2, SIGINT).
* `ps -ef | grep stats_worker` confirmed no lingering worker processes were left running.
