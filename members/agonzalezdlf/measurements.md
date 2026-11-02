# Measurements: agonzalezdlf

**Laptop:** HP OmniBook Ultra Flip, Intel Core Ultra 7 258V, Windows 11  
**Available CPUs in the container (`nproc`):** 8  
**Container memory limit:** 2 GiB (2,147,483,648 bytes)

## Warm-up: permissions

- `ls -l run_report.sh` on my Windows-mounted folder showed `-rwxrwxrwx`.
- Git mode before: `100644` (not executable).
- Git mode after: `100755` (executable).
- Fix: `git update-index --chmod=+x run_report.sh`.
- Commit: `63ea488` — `Make run_report.sh executable`.

My Windows-mounted folder already showed execute permissions, but Git was still recording the file as non-executable. I used `git update-index --chmod=+x` to change the executable bit in Git's staging area, which is what Git uses to prepare the next commit. After committing it, the executable permission could be shared with my teammates.

## Task 1: report.py memory

### Original failure

I ran the original report on the full dataset of 8,400,000 orders.

- DataFrame size printed: 887 MiB.
- Result: `Killed`.
- Exit status: `137` (SIGKILL).
- Container memory limit: 2 GiB.
- Initial `memory.events` reading: `oom=3`, `oom_kill=3`, `oom_group_kill=0`.
- A later reading showed `oom=4` and `oom_kill=4`.

The counters increased by 1 between observations. Since they are cumulative, this indicates one additional OOM event and one additional process killed during that interval, not four kills in a single run. The readings were not recorded as an immediate before/after comparison of an isolated execution.

The problem was that the original code kept the full DataFrame in memory while creating separate monthly DataFrames. These additional copies increased memory consumption until the process exceeded the container's limit.

### Memory-scaling experiment

I tested the report with smaller datasets to see how memory usage changed.

| Orders | DataFrame size (MiB) | Peak memory (KB) | Elapsed |
|---|---:|---:|---:|
| 1,000,000 | 106 | 508,256 | 4.33 s |
| 2,000,000 | 211 | 854,300 | 7.15 s |
| 4,000,000 | 423 | 1,568,212 | 11.15 s |

All three runs completed successfully. Peak memory increased approximately linearly with the number of orders, helping explain why the full dataset failed.

### Pipeline diagnosis

I ran:

`python3 steps/report.py | tee /tmp/report.log`

Results:

- Pipeline status: `0`.
- Individual stages (`PIPESTATUS`): `137 0`.
- The log file was empty.

Python was killed with exit status 137, but `tee` succeeded with status 0. Bash reported the pipeline status as 0 because, by default, it uses the exit status of the last command.

The missing log output is consistent with Python's stdout being buffered when the process was killed.

This showed that a pipeline can appear successful even when an earlier command has failed.

### After the fix

The fixed version groups revenue directly by region and month instead of keeping separate monthly DataFrame copies.

I tested it with the full dataset:

- Input: 8,400,000 orders.
- Result: `report: done`.
- Elapsed: 14.48 s.
- User: 10.49 s.
- System: 3.52 s.
- Peak memory: 1,859,828 KB (approximately 1,816 MiB).
- `tools/check.py`: PASS `revenue_by_region_month.csv`.

The fixed program completed within the 2 GiB memory limit, whereas the original was killed before finishing. The main improvement was making the report complete successfully without exceeding available memory.

## Task 2: extracts.sh

### Original failure

I ran the original `extracts.sh` and initially got:

- Output: `extracts: done`.
- Exit status: `0`.
- All six regional CSV files were empty (0 bytes).

The script changed into the output directory and then tried to read `../data/sales_2025.csv`. From that directory, the relative path pointed to the wrong location.

The `2>/dev/null` redirection also hid the error message.

### Pipeline diagnosis

I ran the pipeline manually from `/home/analyst/data/out/extracts`, without suppressing errors.

Results:

- Error: `grep: ../data/sales_2025.csv: No such file or directory`.
- Output line count: `0`.
- `PIPESTATUS`: `2 0 0`.

`grep` failed with status 2, but the remaining commands returned 0. Without `pipefail`, the failed first stage was hidden by the successful last command.

### Before vs. after — Original and team fix

I measured the original script and the fixed version from GitHub on my laptop.

| Measurement | Original | Team fix |
|---|---:|---:|
| Elapsed | 0.05 s | 4.14 s |
| User | 0.01 s | 4.77 s |
| System | 0.03 s | 1.74 s |
| Peak memory reported (KB) | 8,116 | 7,988 |
| Exit status | 0 | 0 |
| Output | Empty files | Correct regional files |

The original was much faster because it was not actually processing the data. It failed almost immediately but still printed `done`.

The team's fix uses the correct input path, removes the hidden error redirection and adds `set -euo pipefail`. It also avoids changing directory, so the input path no longer depends on the script's working directory.

### Output verification

I ran the official checker on the corrected output directory.

| Region | Rows | Checker |
|---|---:|---|
| Benelux | 1,006,912 | PASS |
| DACH | 1,846,894 | PASS |
| France | 1,345,118 | PASS |
| Iberia | 2,183,057 | PASS |
| Italy | 1,178,032 | PASS |
| Nordics | 839,987 | PASS |
| **Total** | **8,400,000** | |

All six files had the expected row counts. I also inspected Iberia rows and confirmed the five required fields.

### Missing-input test

I tested the fixed script with a nonexistent input file:

`DATA=/nonexistent OUT=/tmp/extracts-failure-test bash steps/extracts_team_test.sh`

Results:

- Error: `grep: /nonexistent: No such file or directory`.
- Exit status: `2`.
- The script did not print `extracts: done`.

This confirmed that the fixed script reports an error instead of silently producing empty files.

The improvement here was correctness and error handling, not speed.

## Task 3: audit.py

### Original implementation

The original code opened and closed the audit output file for every single order.

My timing measurements were:

| Input | Elapsed | User | System | Peak memory |
|---|---:|---:|---:|---:|
| Sample (100k) | 4.16 s | 2.03 s | 1.32 s | 129,920 KB |
| Full (8.4M) | 101.21 s | 64.81 s | 36.37 s | 635,876 KB |

The full run spent 36.37 seconds in system CPU time, which seemed high for a program mainly writing a CSV. I used `strace` to see how many file-related system calls it was making.

### strace — Before vs. after

Command used on the 100,000-order sample:

`strace -c -e trace=openat,write,close python3 steps/audit.py`

| System call | Before | After |
|---|---:|---:|
| openat | 100,689 | 689 |
| write | 100,001 | 17 |
| close | 100,677 | 677 |
| **Total** | **301,367** | **1,383** |

The original code made approximately one open, one write and one close call for every order.

The remaining calls after the fix also include Python startup, imports and other file operations.

### After the fix

The fixed implementation opens the output file once, outside the loop, and writes the orders using Python's file buffering.

I measured the full dataset again:

- Elapsed: 12.18 s.
- User: 11.37 s.
- System: 0.97 s.
- Peak memory: 635,456 KB.
- Speedup: 101.21 / 12.18 = **8.31×**.
- Elapsed-time reduction: approximately **88%**.

System CPU time decreased from 36.37 s to 0.97 s, showing how much overhead was caused by opening and closing the file repeatedly.

Peak memory stayed almost the same.

Also, closing a file flushes Python's buffered output to the operating system, but does not guarantee that the data has been physically persisted to disk. That would require an additional operation such as `fsync()`.

### Output verification

- Sample output: 100,000 rows.
- Full output: 8,400,000 rows.
- I checked the revenue calculations for orders 1–4.
- The output contained three fields: `order_id,region,revenue`, without a header.
- Revenues were formatted to two decimal places.
- `tools/check.py`: PASS `audit_2025.csv`.

## Task 4: segments.py

### Original implementation

The original program iterated over orders individually. For every order, it called `segment()`, which used `datetime.strptime()` to parse the date and calculate the quarter.

I first measured and profiled the original version using the 100,000-order sample.

- Elapsed: 1.24 s.
- User: 1.17 s.
- System: 0.21 s.
- Peak memory: 133,596 KB.
- `cProfile`: 3,646,597 function calls.
- `segment()` calls: 100,000.
- `strptime()` calls: 100,000.

The profiler showed that date parsing and classification were being repeated for every order. With 8.4 million orders, this creates millions of Python function calls.

### Fix implemented by the team

I tested the team's committed version, which reads the CSV in chunks of one million rows and processes whole columns instead of looping through every individual order in Python.

The implementation uses:

- `pd.to_datetime()` to calculate quarters.
- `quantity * unit_price` to calculate order values.
- `np.select()` to classify orders as small, medium or large.
- `groupby()` to count orders by region and segment.

The results from each chunk are then combined into the final table.

This reduces repeated Python-level work, while chunked reading helps control memory use.

### Before vs. after — Full dataset

I measured both the original implementation and the team's committed fix on my own laptop, using the same 8,400,000-order dataset.

| Measurement | Original | Team fix |
|---|---:|---:|
| Elapsed | 56.68 s | 11.81 s |
| User | 54.48 s | 9.68 s |
| System | 1.76 s | 1.72 s |
| Peak memory (KB) | 744,200 | 426,940 |

- Speedup: 56.68 / 11.81 = **4.80×**.
- Elapsed-time reduction: approximately **79.2%**.
- Peak-memory reduction: approximately **42.6%**.

The program became considerably faster, mainly because it avoided repeated Python function calls. Memory usage also decreased because the fixed version processed the dataset in chunks.

### Output verification

I compared the original and fixed CSVs on the 100,000-order sample using `diff`.

- `diff` showed no differences.
- Exit status: `0`.
- The full fixed run completed successfully.
- `tools/check.py`: PASS `segments.csv`.

This confirmed that the optimized implementation preserved the expected results.

## Task 5: stats.sh

### Original problems

I investigated two issues with the statistics script:

1. The original default was 16 workers, even though my container has 8 available logical CPUs.
2. Pressing Ctrl+C could stop the main shell script without stopping its background Python workers.

The script divides the region-month calculations among multiple worker processes. Running workers in parallel can reduce elapsed time, but using more workers than available CPUs does not create additional CPU capacity and may introduce overhead.

### Worker-scaling experiment

I ran:

`bash tools/sweep.sh agonzalezdlf`

The script tested 1, 2, 4, 8 and 16 workers, with three runs for each configuration. All 15 measurements are saved in `members/agonzalezdlf/sweep.csv`.

| Workers | Run 1 | Run 2 | Run 3 | Median elapsed |
|---|---:|---:|---:|---:|
| 1 | 43.27 s | 51.63 s | 48.58 s | 48.58 s |
| 2 | 29.89 s | 33.78 s | 38.50 s | 33.78 s |
| 4 | 21.67 s | 23.13 s | 22.05 s | 22.05 s |
| 8 | 20.27 s | 20.60 s | 19.84 s | 20.27 s |
| 16 | 19.80 s | 19.56 s | 20.77 s | 19.80 s |

Elapsed time decreased substantially between 1 and 4 workers, but improvements became much smaller after that.

16 workers had the lowest median on my laptop (19.80 s), but this was only 0.47 s, or approximately 2.3%, faster than 8 workers (20.27 s).

I would therefore choose **8 workers as a sensible default**, since my container has 8 logical CPUs and it achieved nearly the same performance with fewer processes. However, my results do not prove that 8 is always the fastest configuration.

My results were noticeably slower than those reported by teammates using MacBooks. I also observed much higher accumulated system CPU time. I cannot confirm the exact cause from these measurements alone, as hardware, Docker/WSL2, storage and system workload may all contribute.

### Ctrl+C test — Before the fix

I ran the original statistics script with two workers and monitored the processes from a second terminal.

Command:

`WORKERS=2 bash steps/stats.sh`

**Before Ctrl+C:**
- Worker PIDs: 1782 and 1783.
- Parent PID (PPID): 1761.
- Both workers were running.

**After Ctrl+C:**
- The main script exited.
- Both workers continued running.
- Their PPID changed from 1761 to 1.
- They remained active for several seconds afterward.

This confirmed the original cleanup problem: the main script stopped, but its background workers kept running as orphan processes.

### Team fix

The team's committed `stats.sh` implementation addresses both problems.

**Fix A — Worker count**

`WORKERS=${WORKERS:-$(nproc)}`

The script now uses the number of logical CPUs available to the container as its default worker count. The value can still be overridden, for example with `WORKERS=4`, when testing different configurations.

**Fix B — Worker cleanup**

The script now:

- Records the PID of each background worker using `$!`, so it knows which processes it launched.
- Uses `trap cleanup EXIT` to run the cleanup function when the shell script exits, allowing it to stop its background workers.
- Handles **SIGINT (signal 2)**, normally triggered by Ctrl+C, by exiting with status `130` (128 + 2).
- Handles **SIGTERM (signal 15)**, a request to terminate a process, by exiting with status `143` (128 + 15).
- Sends termination signals to the tracked workers during cleanup.
- Uses individual `wait` commands and `set -euo pipefail` to detect failures.

The key idea is that an interruption causes the script to exit, which triggers the `EXIT` trap and runs the cleanup function. `EXIT` is a Bash trap event, not a signal.

### Verification of the team fix

I tested the team's committed `stats.sh` implementation to check both normal execution and worker cleanup. For these tests, I ran it as `steps/stats_team_test.sh`.

**Syntax check**

- `bash -n steps/stats_team_test.sh`: exit status `0`, confirming there were no Bash syntax errors.

**Ctrl+C test**

I ran:

`WORKERS=2 bash steps/stats_team_test.sh`

I monitored the processes from a second terminal.

Before Ctrl+C:
- Two active workers: PIDs 2644 and 2645.
- Both had PPID 2626.

After Ctrl+C:
- The workers stopped appearing in the process monitor.
- No surviving workers with PPID 1 were observed.
- `echo $?` returned `130`, indicating interruption by SIGINT.

This showed that the team's fix successfully stopped the background workers in my test, unlike the original version, which left orphan processes running.

**Normal execution**

I ran:

`WORKERS=8 bash steps/stats_team_test.sh`

Results:
- `stats: input ready`.
- `stats: done with 8 workers`.
- `tools/check.py`: PASS `stats.csv` — 72 region-month groups, as expected.

The fixed script completed successfully, produced the expected output and passed the interruption test.

The worker sweep was a separate performance experiment, so I kept my original 15 measurements in `sweep.csv`.
