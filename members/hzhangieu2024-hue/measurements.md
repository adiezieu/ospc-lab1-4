# Measurements of hzhangieu2024-hue

All numbers are from the original scripts (initial commit of the template), run in the course container on my laptop.

## 5.1 Warm-up
`ls -l run_report.sh` before the fix: -rw-r--r-- (mode 100644)
Missing permission: execute (x), for owner, group and others.
`bash run_report.sh` works because bash only needs to read the file, not execute it.
After the fix: -rwxr-xr-x (mode 100755).

## 5.2 Task 1 (report.py)
Full run of ./run_report.sh: ___ s elapsed, ___ s user, ___ s system, ___ KB peak. Step that did not finish: report.py
Exit status of report.py on the whole file: 137 (128 + 9 = SIGKILL, "Killed" printed by the shell)
memory.max: ___
memory.events before the run: oom 0, oom_kill 0
memory.events after the run: max 24227, oom 1, oom_kill 1, oom_group_kill 0

| Orders | Table size | Elapsed | User | System | Peak memory (KB) |
|--------|------------|---------|------|--------|------------------|
| 1,000,000 | 106 MiB | 2.04 s | 2.37 s | 0.27 s | 506,116 |
| 2,000,000 | 211 MiB | 3.50 s | 3.81 s | 0.29 s | 855,420 |
| 4,000,000 | 423 MiB | 7.05 s | 6.83 s | 0.83 s | 1,567,512 |
| 8,400,000 | 887 MiB (printed before the kill) | killed | - | - | killed by the OOM killer. Extrapolated: about 3,134,000 KB (about 3.0 GiB) |

Extrapolation: from 2M to 4M the peak grows by 712,092 KB, so about 356,000 KB per million orders. Peak(8.4M) = 1,567,512 + 4.4 x 356,046 = about 3,134,000 KB.
Peak memory is about 3.5 times the table size (1,567,512 KB = 1,531 MiB vs 423 MiB at 4M), because the program needs memory beyond the final table while loading it. At 8.4M the table is 887 MiB, but the peak (about 3.0 GiB) is above the container limit, so the kernel killed the process.

Why "loaded ..." is missing with tee: when stdout goes into a pipe, Python buffers its output instead of writing each line at once. The process is killed with SIGKILL, which cannot be caught, so the buffer is never flushed and the line is lost.

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

### Answers (Task 3)
- Why so many system calls: the original audit.py opens the output file, writes one line and closes it again for every order. That gives about 3 system calls per order (100,686 openat, 100,001 write, 100,673 close for 100,000 orders).
- Time on the full file: 83.93 s elapsed, of which 63.74 s user and 20.79 s system (24.6 % in the kernel). The kernel share comes from the system calls, which is about twice the share of report.py.
- "So that each line is saved on disk" is not true. close() only hands the data to the kernel, which keeps it in the page cache and writes it to disk later. Only fsync() forces data onto the disk, and the script does not call it. The repeated open/close adds cost without giving that guarantee.
- With one open file, Python's 128 KiB buffer would give about 1,379 write calls for the 180,634,390 bytes.
