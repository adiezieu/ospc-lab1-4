

## 5.1 Warm-up
`ls -l run_report.sh` before the fix: -rw-r--r-- (mode 100644)
Missing permission: execute (x), for owner, group and others.
After the fix: -rwxr-xr-x (mode 100755).

## 5.2 Task 1 (report.py)
Full run of ./run_report.sh: 154.12 s elapsed, 197.72 s user, 28.45 s system, 2085500 KB peak
Exit status of report.py on the whole file: 137 (128 + 9 = SIGKILL, "Killed" printed by the shell)
memory.max: 2147483648 bytes (2 GiB)
memory.events before the run: oom 0, oom_kill 0
memory.events after the run: max 24227, oom 1, oom_kill 1, oom_group_kill 0

| Orders | Table size | Elapsed | User | System | Peak memory (KB) |
|--------|------------|---------|------|--------|------------------|
| 1,000,000 | 106 MiB | 2.04 s | 2.37 s | 0.27 s | 506,116 |
| 2,000,000 | 211 MiB | 3.50 s | 3.81 s | 0.29 s | 855,420 |
| 4,000,000 | 423 MiB | 7.05 s | 6.83 s | 0.83 s | 1,567,512 |
| 8,400,000 | 887 MiB (printed before the kill) | killed | - | - | killed by the OOM killer. Extrapolated: about 3,134,000 KB (about 3.0 GiB) |


## 5.3 Task 2 (extracts.sh)
Output: "extracts: done". Exit status: 0.
Files in ~/data/out/extracts: Benelux.csv, DACH.csv, France.csv, Iberia.csv, Italy.csv, Nordics.csv, all 0 bytes ("total 0").

## 5.4 Task 3 (audit.py)
| Run | Elapsed | User | System | Peak memory (KB) |
|-----|---------|------|--------|------------------|
| Sample (100,000 orders) | 1.59 s | 1.56 s | 0.37 s | 128,832 |
| Full (8.4 million orders) | 83.93 s | 63.74 s | 20.79 s | 634,808 |

strace -c on the sample: openat = 100,686 (13 errors), write = 100,001, close = 100,673. Total 301,360 calls.
That is about one open, one write and one close per order.
System share on the sample: 0.37 / (1.56 + 0.37) = 19 %
System share on the full run: 20.79 / (63.74 + 20.79) = 24.6 % (report.py at 4M orders: about 11 %)
Output file size (ls -l audit_2025.csv): 180,634,390 bytes (about 172 MiB)
Expected write calls with one open file and a 128 KiB buffer: 180,634,390 / 131,072 = about 1,379 (instead of 8,400,000 writes in the original design)

