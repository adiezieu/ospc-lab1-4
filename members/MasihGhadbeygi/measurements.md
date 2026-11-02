# Measurements: MasihGhadbeygi
Laptop: Apple MacBook Air 15-inch M2 2023, macOS Tahoe 26.3.1
nproc in the container: 8



## Task 1: whole pipeline (./run_report.sh)
- Elapsed: 230.52 s
- User: 374.51 s
- System: 49.87 s
- Peak memory: 2087744 KB (about 2 GB, the container limit)
- report.py was Killed, but the script continued with audit, segments and stats
- stats ran with 16 workers (my laptop has 8 CPUs)



## Task 1: report.py alone (8.4M orders)
- Printed: loaded 8,400,000 orders (887 MiB), then Killed
- Exit status: 137 (128 + 9 = SIGKILL)
- memory.events: oom_kill 2, max 3010
- Missing output: revenue_by_region_month.csv
- extracts/*.csv: all 6 files are 0 bytes



## Task 3: audit.py (BEFORE fix) - Masih Ghadbeygi's Part
- Sample (100k orders): 0.89 s elapsed, 1.27 s user, 0.22 s system, 129376 KB peak memory
- strace (sample): openat 100686, write 100001, close 100673 (about one of each per order)
- Full file (8.4M orders): 54.71 s elapsed, 39.75 s user, 15.55 s system, 634388 KB peak memory
- System share: 15.55 / (39.75 + 15.55) = about 28% of CPU time in the kernel



## Task 3: audit.py (AFTER fix: file opened once) - Masih Ghadbeygi's Part
- Sample (100k orders): 0.42 s elapsed, 0.94 s user, 0.08 s system, 128740 KB peak memory
- strace (sample): openat 686, write 17, close 673
- Full file (8.4M orders): 11.79 s elapsed, 11.96 s user, 0.43 s system, 634304 KB peak memory
- System share: 0.43 / (11.96 + 0.43) = about 3.5% (was 28%)
- check.py: PASS audit_2025.csv 8,400,000 lines