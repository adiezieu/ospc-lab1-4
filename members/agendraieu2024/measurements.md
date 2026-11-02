# Measurements: agendraieu2024

Laptop: Apple MacBook Air 15-inch M2 2023, macOS 26.6.2
nproc in the container: 8
Container memory limit: 2147483648 bytes (2 GiB)
Code measured: the original steps (commit fbf1f18), except the memory table of Task 1, which uses the fixed report.py now on main.

## Warm-up: permissions
- `ls -l run_report.sh` before chmod: `-rw-r--r--`
- `./run_report.sh` printed: `bash: ./run_report.sh: /bin/bash: bad interpreter: Permission denied`
- `ls -l run_report.sh` after chmod +x: `-rwxr-xr-x`
- The fix was already pushed by a teammate (63ea488), so I discarded my local mode change and pulled it.

## Task 1: report.py memory
Whole pipeline, original code (./run_report.sh, 8.4M orders):
- Printed: `report: loaded 8,400,000 orders (887 MiB)`, then `55 Killed python3 steps/report.py`
- The script kept going: audit, segments and stats ran, and it printed "Nightly report finished"
- 114.83 s elapsed, 147.14 s user, 22.38 s system, 2089912 KB peak memory (the limit is 2097152 KB)

Memory scaling, with the fixed report.py now on main (groupby, no monthly copies):

| Orders | Table size (MiB) | Peak memory (KB) | Elapsed (s) |
|---|---:|---:|---:|
| 1,000,000 | 106 | 360068 | 3.34 |
| 2,000,000 | 211 | 558616 | 3.57 |
| 4,000,000 | 423 | 965328 | 6.76 |

- The table size grows linearly with the orders (106, 211, 423 MiB, so 887 MiB for 8.4M).
- Peak memory grows about 203,000 KB per million orders. Extrapolating to 8.4M: about 1.86M KB (1.77 GiB), under the 2 GiB limit but close.
- Not measured on my laptop: exit status 137 of report.py alone, oom_kill before and after, the tee test.

## Task 2: extracts.sh
- `bash steps/extracts.sh` printed `extracts: done`; `echo $?` printed 0.
- `ls -l ~/data/out/extracts`: all 6 files (Benelux, DACH, France, Iberia, Italy, Nordics) are 0 bytes.
- Running the pipeline by hand from ~/data/out/extracts:
  `grep ",Iberia," ../data/sales_2025.csv | cut -d, -f1,2,4,6,7 | wc -l`
  printed `grep: ../data/sales_2025.csv: No such file or directory` and `0`.
- `echo ${PIPESTATUS[@]}` printed `2 0 0`: grep failed with 2, cut and wc returned 0, so `$?` of the pipeline was 0.
- Cause: from the folder the script works in, `../data/sales_2025.csv` is `~/data/out/data/sales_2025.csv`, which does not exist. The real file is `~/data/sales_2025.csv`.

## Task 3: audit.py
| Run | Elapsed | User | System | Peak memory |
|---|---:|---:|---:|---:|
| Sample (100k) | 2.08 s | 1.95 s | 0.73 s | 128356 KB |
| Full (8.4M) | 97.65 s | 68.41 s | 29.79 s | 634348 KB |

- `strace -c -e trace=openat,write,close` on the sample: openat 100686, write 100001, close 100673 (301360 calls in total, 13 errors in openat).
- About one openat, one write and one close per order, because the file is opened and closed inside the loop.
- Share of the CPU time spent in the kernel on the full run: 29.79 / (68.41 + 29.79) = 30%.
- For comparison, report.py on 4M orders: 0.71 / (6.64 + 0.71) = 10%.

## Task 4: segments.py
- cProfile on the sample (100,000 orders): 3,646,592 function calls in 2.556 s.
- `_strptime` is called 100000 times (once per order): tottime 0.560 s, cumtime 1.064 s.
- `segment()` is called 100000 times: cumtime 1.273 s, about half of the total.
- Full file (8.4M): 59.72 s elapsed, 58.24 s user, 2.08 s system, 749708 KB peak memory.
- The step is CPU bound (kernel time is about 3%). A function called once per row on 100,000 orders is called 8.4 million times on the whole file.

## Task 5: stats.sh
- `./run_report.sh` printed `stats: done with 16 workers` on a container with 8 CPUs.

Sweep (members/agendraieu2024/sweep.csv), median elapsed of 3 runs:

| Workers | 1 | 2 | 4 | 8 | 16 |
|---|---:|---:|---:|---:|---:|
| Elapsed (s) | 32.24 | 16.86 | 9.48 | 7.72 | 8.87 |

- Time halves from 1 to 2 to 4 workers, flattens at 8 (the number of CPUs), and gets slower at 16.
- User CPU time keeps growing with more workers (about 32 s with 1 worker, about 64 s with 16).

Ctrl-C test (`bash steps/stats.sh`, Ctrl-C a few seconds after `stats: input ready`):
- `echo $?` printed 130 (128 + 2, SIGINT).
- First attempt: `ps -ef | grep stats_worker` showed nothing (I ran it several seconds later, the workers had probably finished).
- Second attempt, `ps` right after Ctrl-C: 14 `python3 steps/stats_worker.py K 16` processes still running, all with PPID 1.
- I removed them with `pkill -f stats_worker`.
