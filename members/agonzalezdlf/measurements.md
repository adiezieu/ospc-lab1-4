
# Measurements: agonzalezdlf

## Warm-up: permissions

- `ls -l run_report.sh` on my Windows-mounted folder: `-rwxrwxrwx`
- Git mode before the fix: `100644` (not executable).
- Git mode after the fix: `100755` (executable).
- Fix: `git update-index --chmod=+x run_report.sh`
- Commit: `63ea488` — `Make run_report.sh executable`.

The Windows-mounted folder displayed execute permissions even though Git originally recorded the file as non-executable. The Git executable bit was corrected so teammates can receive the intended permission through the repository.

## Task 1: report.py memory

### Original full-dataset run

- Input: 8,400,000 orders.
- Printed DataFrame size: 887 MiB.
- The report process printed `Killed`.
- Exit status when running `python3 steps/report.py` directly: `137` (SIGKILL).
- Container memory limit (`memory.max`): 2,147,483,648 bytes (2 GiB).
- Observed `oom`: 3.
- Observed `oom_kill`: 3.
- Observed `oom_group_kill`: 0.
- OOM counters were checked as a cumulative snapshot, not as a verified before/after comparison.

The original program retains monthly DataFrame copies while keeping the original table in memory. This increases memory demand and is consistent with the observed OOM failure.

### Memory-scaling experiment

| Orders | Table size (MiB) | Peak memory (KB) | Peak memory (MiB) | Elapsed time |
|---|---:|---:|---:|---:|
| 1,000,000 | 106 | 508256 | 496.34 | 4.33 s |
| 2,000,000 | 211 | 854300 | 834.28 | 7.15 s |
| 4,000,000 | 423 | 1568212 | 1531.46 | 11.15 s |

All three smaller runs completed successfully (`report: done`).

Peak memory and elapsed time increased with dataset size. The reported peak memory in MiB was calculated by dividing the KB measurement by 1,024.

### After the fix

Not measured yet.

## Task 2: extracts.sh

- Exit status of script: Not measured yet.
- PIPESTATUS of the grep pipeline: Not measured yet.

## Task 3: audit.py

| Run | Elapsed | User | System | Peak memory |
|---|---|---|---|---|
| Sample (100k) | Not measured | | | |
| Full (8.4M) | Not measured | | | |

- strace -c: openat / write / close counts: Not measured yet.

## Task 4: segments.py

- Profile and function-call counts: Not measured yet.
- Before/after performance: Not measured yet.

## Task 5: stats.sh

- Worker-scaling results: See sweep.csv (pending).
- Process cleanup after interruption: Not measured yet.
- Selected worker count and justification: Pending.
