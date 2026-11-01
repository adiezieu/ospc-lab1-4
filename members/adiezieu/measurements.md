# Measurements: adiezieu

## Warm-up: permissions
- `ls -l run_report.sh` before chmod:
- `ls -l run_report.sh` after chmod:

## Task 1: report.py memory
| Orders | Table size | Peak memory (KB) |
|---|---|---|
| 1,000,000 | | |
| 2,000,000 | | |
| 4,000,000 | | |
- Exit status of the full run:
- oom_kill in memory.events (before / after):

## Task 2: extracts.sh
- Exit status of script:
- PIPESTATUS of the grep pipeline:

## Task 3: audit.py
| Run | Elapsed | User | System | Peak memory |
|---|---|---|---|---|
| Sample (100k) | | | | |
| Full (8.4M) | | | | |
- strace -c: openat / write / close counts:
