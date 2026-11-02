# Measurements: igonzalezdel

**Laptop:** My Dell Inspiron 16 7640 (Intel Core Ultra 7 155H, 16 cores, 22 threads, Windows 11, `nproc` 22, see `machine.txt`) broke after the in-class session. With Matteo's approval, Tasks 1 to 5 below were measured on 2026-11-02 on a teammate's laptop (agendraieu2024), the same one used for his measurements.  
**Laptop used for these measurements:** Apple MacBook Air 15-inch M2 2023, macOS 26.6.2  
**Available CPUs in the container (`nproc`):** 8  
**Container memory limit:** 2 GiB  
**Code measured:** the original steps (commit `fbf1f18`), except the memory-scaling table of Task 1, which uses the fixed `report.py` on main. Outputs were written to `/tmp/out` (`OUT=/tmp/out`).

## Warm-up: permissions

- Measured on my Dell during the in-class session.
- `ls -l run_report.sh` on the Windows-mounted folder showed `-rwxrwxrwx`, so `./run_report.sh` ran without a permission error.
- Windows folders mounted into the container show every file as fully permitted, while on Mac and Linux teammates got `-rw-r--r--` and `Permission denied`.
- The executable bit was fixed in Git by a teammate (commit `63ea488`).

## Task 1: report.py memory

### Original failure

On my Dell, the whole pipeline (`./run_report.sh`) printed `Killed` on the `report.py` line, but the script kept going and printed "Nightly report finished".

On the MacBook, running `report.py` alone on the full file:

- Printed: `report: loaded 8,400,000 orders (887 MiB)`, then `Killed`.
- `echo $?`: `137` (128 + 9, SIGKILL).
- `memory.events` before: `max 0`, `oom 0`, `oom_kill 0`.
- `memory.events` after: `max 2337`, `oom 1`, `oom_kill 1`.

`oom_kill` went from 0 to 1, so the kernel's out-of-memory killer stopped the program when the container reached its 2 GiB limit. The table itself was 887 MiB, but the original code also creates separate monthly copies, so the total went over the limit.

### Memory-scaling experiment

Run with the fixed `report.py` on main.

| Orders | DataFrame size (MiB) | Peak memory (KB) | Elapsed |
|---|---:|---:|---:|
| 1,000,000 | 106 | 348,908 | 2.00 s |
| 2,000,000 | 211 | 558,520 | 3.91 s |
| 4,000,000 | 423 | 965,736 | 6.88 s |

All three runs completed. The DataFrame size grows linearly with the number of orders. From 2M to 4M, peak memory grows by about 203,600 KB per million orders. Extrapolating to 8,400,000 orders gives about 1,862,000 KB (1.78 GiB), under the 2 GiB limit but close.

Comparison with agendraieu2024 on the same laptop:

| Orders | My peak (KB) | agendraieu2024 peak (KB) | Difference |
|---|---:|---:|---:|
| 1,000,000 | 348,908 | 360,068 | -3.1% |
| 2,000,000 | 558,520 | 558,616 | -0.0% |
| 4,000,000 | 965,736 | 965,328 | +0.0% |

### Pipeline diagnosis

`python3 steps/report.py | tee /tmp/report.log`

- `PIPESTATUS`: `137 0`.
- `/tmp/report.log` was empty.

Python was killed with 137, but `tee` returned 0, and without `pipefail` the pipeline takes the status of its last command. The log is empty because Python's stdout is buffered when it writes to a pipe instead of a terminal, and SIGKILL ended the process before the buffer was flushed.

## Task 2: extracts.sh

- `bash steps/extracts.sh` printed `extracts: done`; `echo $?` printed `0`.
- `ls -l /tmp/out/extracts`: all 6 files (Benelux, DACH, France, Iberia, Italy, Nordics) were 0 bytes.
- Running the pipeline by hand from `~/data/out/extracts`:
  `grep ",Iberia," ../data/sales_2025.csv | cut -d, -f1,2,4,6,7 | wc -l`
  printed `grep: ../data/sales_2025.csv: No such file or directory` and `0`.
- `echo ${PIPESTATUS[@]}`: `2 0 0`.
- `pwd`: `/home/analyst/data/out/extracts`.

From the folder the script works in, `../data/sales_2025.csv` points to `~/data/out/data/sales_2025.csv`, which does not exist. The real file is `~/data/sales_2025.csv`. `grep` failed with 2, but `cut` and `wc` returned 0, so the pipeline and the script reported success. The `2>/dev/null` in the script hides the grep error.

## Task 3: audit.py

| Input | Elapsed | User | System | Peak memory |
|---|---:|---:|---:|---:|
| Sample (100k) | 2.49 s | 1.99 s | 0.80 s | 127,816 KB |
| Full (8.4M) | 105.86 s | 69.36 s | 37.08 s | 634,056 KB |

`strace -c -e trace=openat,write,close` on the sample:

| System call | Calls | Errors |
|---|---:|---:|
| openat | 100,686 | 13 |
| write | 100,001 | |
| close | 100,673 | |
| **Total** | **301,360** | **13** |

- About one openat, one write and one close per order, because the file is opened and closed inside the loop.
- Share of CPU time spent in the kernel on the full run: 37.08 / (69.36 + 37.08) = 35%. For `report.py` on 4M orders: 0.59 / (6.90 + 0.59) = 8%.
- The sample output is 1,952,269 bytes. Writing it through one open file with Python's 128 KiB buffer would take about 1,952,269 / 131,072 ≈ 15 write calls.
- Closing a file passes Python's buffer to the operating system, but does not guarantee the data is on disk. That would need `fsync()`, so the comment in `audit.py` is wrong.

## Task 4: segments.py

`cProfile` on the sample (100,000 orders):

- 3,646,600 function calls in 2.347 s.
- `_strptime` is called 100,000 times (once per order): tottime 0.547 s, cumtime 1.059 s. It is the function with the largest tottime.
- `segment()` is called 100,000 times: cumtime 1.273 s, more than half of the total.

Full file (8.4M orders):

| Elapsed | User | System | Peak memory |
|---:|---:|---:|---:|
| 59.66 s | 59.13 s | 1.12 s | 743,488 KB |

- Share of CPU time spent in the kernel: 1.12 / (59.13 + 1.12) = 2%. The step is CPU bound: the time goes into Python's own code, not into system calls.
- A function called 100,000 times on the sample is called 8.4 million times on the full file. Parsing each date with `strptime()` inside `segment()`, one order at a time, is where the time goes.

## Task 5: stats.sh

### Worker-scaling experiment

`bash tools/sweep.sh igonzalezdel`. All 15 measurements are in `members/igonzalezdel/sweep.csv`.

| Workers | Run 1 | Run 2 | Run 3 | Median elapsed |
|---|---:|---:|---:|---:|
| 1 | 55.63 s | 57.47 s | 55.66 s | 55.66 s |
| 2 | 38.10 s | 28.27 s | 28.75 s | 28.75 s |
| 4 | 19.81 s | 16.13 s | 19.26 s | 19.26 s |
| 8 | 22.52 s | 21.02 s | 22.50 s | 22.50 s |
| 16 | 22.33 s | 21.70 s | 25.42 s | 22.33 s |

Elapsed time drops a lot from 1 to 4 workers, and 4 workers was the fastest in my run. With 8 and 16 workers it got slower, even though `nproc` is 8. User time roughly doubled from 4 workers (62 to 76 s) to 8 workers (148 to 159 s), so the extra workers used more CPU without finishing sooner.

### Comparison with agendraieu2024 on the same laptop

| Workers | 1 | 2 | 4 | 8 | 16 |
|---|---:|---:|---:|---:|---:|
| My median (s) | 55.66 | 28.75 | 19.26 | 22.50 | 22.33 |
| agendraieu2024 median (s) | 32.24 | 16.86 | 9.48 | 7.72 | 8.87 |

On the same hardware, my sweep was about 1.7 to 2.9 times slower, and the best worker count was different (4 for me, 8 for him). Since the laptop and the container were the same, the gap comes from the conditions during each run, not from the hardware. Possible causes are other load on the laptop, thermal throttling (the MacBook Air has no fan) or Docker's state, but I cannot confirm which one from these measurements.

### Ctrl-C test

`bash steps/stats.sh`, Ctrl-C about 3 seconds after `stats: input ready`:

- `echo $?`: `130` (128 + 2, SIGINT).
- `ps -ef | grep stats_worker` right after: 15 `python3 steps/stats_worker.py K 16` processes still running (K from 0 to 15, except 9), all with PPID 1.
- I removed them with `pkill -f stats_worker` and checked again with `ps -ef`: none left.

Ctrl-C stopped the main script, but its background workers kept running. Their parent had exited, so they were adopted by process 1 of the container. The original script has no `trap` to stop its workers when it exits.
