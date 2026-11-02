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