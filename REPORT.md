# Lab 1: The Nightly Report

Write your answers in this file. Keep them short: a few sentences, the commands
you used, and the numbers you measured. Copy the lines of output that matter,
not whole screens.

## Warm-up: Generating the report

- What happened, and why: `./run_report.sh` failed with `bash: ./run_report.sh: /bin/bash: bad interpreter: Permission denied`. The message is misleading: /bin/bash is fine. `ls -l run_report.sh` showed `-rw-r--r--`, so the script had no execute permission (x) for owner, group or others, and `./script` needs it. `bash run_report.sh` works because then bash only has to read the file, which needs just the read permission.
- Your fix, and how it reached your teammates: `chmod +x run_report.sh` (`ls -l` then shows `-rwxr-xr-x`), then commit and push. Alexandra's commit (63ea488) reached the rest of us with `git pull`, because git stores the execute bit as part of the file mode. On Windows the bit has to be set with `git update-index --chmod=+x run_report.sh`. A later `git pull --rebase` complained about unstaged changes only because my local copy had a mode change on this file; `git checkout -- run_report.sh` removed it.

## Task 1: Generating the report… again

- Symptom: The original report.py was killed when processing the full dataset of 8,400,000 orders. It printed a DataFrame size of 887 MiB before exiting with status 137 (SIGKILL). The container had a memory limit of 2 GiB.
- Commands and recordings you used, why you chose them, and what they showed: I checked memory.max to confirm the container's memory limit and inspected memory.events to understand why the process was killed. The oom and oom_kill counters initially showed 3 and later increased to 4. Since these are cumulative counters, this indicates one additional OOM event and one additional process killed between observations, not four kills during one execution. I then used /usr/bin/time to test smaller datasets and see how memory consumption increased. Peak memory was 508,256 KB for 1M orders, 854,300 KB for 2M and 1,568,212 KB for 4M. I also tested `python3 steps/report.py | tee /tmp/report.log` and checked PIPESTATUS. The pipeline returned 0 even though Python exited with status 137, because tee was the last command and succeeded.
- Cause: The original code kept the full DataFrame in memory while creating 12 separate monthly DataFrames and then combining them using pd.concat(). These additional copies increased memory consumption until the process exceeded the container's 2 GiB limit.
- Fix: I changed the approach to calculate monthly revenue directly from the original DataFrame, extracting the month from order_date and using groupby() to aggregate revenue by region and month. This avoided creating and concatenating separate monthly DataFrames, reducing memory usage.
- Before and after (my measurements):
  - Before: The original program was killed with exit status 137 and could not complete the full dataset.
  - After: The fixed version successfully processed all 8,400,000 orders in 14.48 s elapsed (10.49 s user, 3.52 s system), with 1,859,828 KB peak memory (approximately 1,816 MiB).
  - python3 tools/check.py: PASS revenue_by_region_month.csv.

The main improvement was that the report could now complete within the memory limit while producing the expected output.

## Task 2: Extracting data

- Symptom: `bash steps/extracts.sh` printed `extracts: done` and ended with exit status 0, but the six files in `~/data/out/extracts/` (Iberia, DACH, France, Italy, Benelux, Nordics) were all 0 bytes. The report looked successful and the regional managers would have received empty files.
- Commands and recordings you used, why you chose them, and what they showed: First `ls -l ~/data/out/extracts` to check the result: six files of 0 bytes. Then I ran the pipeline of the loop by hand and printed `echo ${PIPESTATUS[@]}`, because `$?` of a pipeline is only the status of its last command (`cut`). It showed `2 0 0`: grep failed with status 2, but cut and the redirection succeeded. The error message was `grep: ../data/sales_2025.csv: No such file or directory`. I read `help set` to check what `set -e` and `pipefail` would change.
- Cause: Two things combined. (1) The script does `cd` into `$OUT/extracts` and then reads `../data/sales_2025.csv`, a relative path. From that folder it points to `~/data/out/data/sales_2025.csv`, which does not exist (the real file is `~/data/sales_2025.csv`). (2) The grep error was thrown away with `2>/dev/null`, and the script had no `set -e` / `pipefail`, so the failed grep was hidden: the exit status of the pipeline was the one of `cut`, which is 0. The `>` redirection had already created the empty files.
- Fix: Removed the `cd` and used the absolute paths `$DATA` and `$OUT`, removed `2>/dev/null` so errors are visible, and added `set -euo pipefail` so the script stops and fails if any command of a pipeline fails. Commit a4f561a: "Fix task 2: extracts.sh reads the right file and stops on errors".
- Before and after (your measurements): 
  - Before: exit status 0, six files of 0 bytes, `PIPESTATUS` = `2 0 0`.
  - After: `bash steps/extracts.sh` takes 8.82 s (6.30 s user, 6.38 s system; user + system is larger than elapsed because the commands of each pipeline run in parallel). The six files have 29 to 76 MB, for example Iberia has 2,183,057 lines, and `python3 tools/check.py` shows PASS for them.
  - Failure test: with `DATA=/nonexistent bash steps/extracts.sh` the script now stops with grep's error and exit status 2 instead of printing `done`. It also works when started from another folder (`cd ~` first), since it no longer depends on the current directory.

## Task 3: Auditing

- Symptom: audit.py wrote the correct file (8,400,000 lines) but it was slow. On the full file it took 54.71 s, and 15.55 s of that was system time, so about 28% of the CPU time was spent in the kernel instead of in our code.

- Commands and recordings you used, why you chose them, and what they showed: First I used `/usr/bin/time -f "$T" python3 steps/audit.py` to see user vs system time. The system time was very high, which pointed to system calls. Then I used `strace -c -e trace=openat,write,close python3 steps/audit.py` on the sample (100,000 orders) to count them. It showed 100,686 openat, 100,001 write and 100,673 close, so basically one open, one write and one close for every order.

- Cause: the loop opened the file, wrote one line and closed it again for every single order (`with open(path, "a")` was inside the `for` loop). That is 3 system calls per order, and Python's buffer was emptied after every line, so it was never used. The comment said this makes sure each line is saved on disk, but that is not true. close() only gives the data to the kernel's page cache, and the kernel writes it to disk later. Only fsync() forces it to disk.
- Fix: I moved the open() outside the loop, so the file is opened once at the start and closed once at the end. Now Python fills its 128 KiB buffer and writes big blocks instead of one line at a time. Commit: "Fix task 3: open audit file once instead of per order".

- Before and after (your measurements): measured on my MacBook Air M2 (8 CPUs in the container).
  - Sample, system calls: openat 100,686 → 686, write 100,001 → 17, close 100,673 → 673
  - Sample, time: 0.89 s → 0.42 s elapsed, 0.22 s → 0.08 s system
  - Full file: 54.71 s → 11.79 s elapsed, 39.75 s → 11.96 s user, 15.55 s → 0.43 s system
  - Kernel share: about 28% → about 3.5%
  - Peak memory stayed the same (about 634,000 KB)
  - The ~686 openat and ~673 close left are from Python starting up and loading its modules, not from our file. 17 writes makes sense because the output is about 2.1 MB and 2.1 MB / 128 KiB ≈ 17. For the full file (about 180 MB) that is around 1,400 writes instead of 8.4 million.

  - check.py: PASS audit_2025.csv 8,400,000 lines

## Task 4: Segmenting the orders

- Symptom: segments.py took 44.00 s on the full file (44.02s user, 0.58s system, 750,648 KB peak). Much longer than just reading the file 
- Diagnosis: the system time is tiny, the problem is not in the kernel. The time goes into the Python code running for every row. cProfile (100,000 rows) shows 3.6 million function calls, including 100,000 calls of segment() and of datetime.strptime. On the full file, it is 8.4 million calls of each. 
- Commands and recordings you used, why you chose them, and what they showed:
I used '/usr/bin/time -f "$T" python3 steps/segments.py' to measure the symton and whether the time problem was on user or system time. It gave 44s elapsed, 44.02 user ad 0.58s system. Almost all the time is on user time 
Then used 'DATA=~/data/sales_2025_sample.csv /usr/bin/time ...' to make a quick measurement on 100,000 orders, to compare the before and after. It gave 0.89s elapsed, 1.37s user, 0.10s system
'python 3 -m cProfile -s tottime steps/segment.py' To find which functions take more time
I used cat steps/segments.py to find the line behind those calls. The loop 'for order in orders.itertuples()' calls segment(), which calls datetime.strptime for every order
'cp ~/data/out/segments.csv /tmp/segments_before.csv', then used 'diff' after the fix to prove that the fix does not change the result. diff printed nothing and my script printed IDENTICAL
I used 'python3 tools/check.py' to check the reference values. PASS for segments.csv
- Cause: a Python loop calls segment() once per order, and each call parses the date text with strptime, which is slow. 
- Fix: to fix it, we work on the whole columns instead of one time at a time: using pd.to_datetime(...).dt.quarter, np.select for the size, groupby to count. The file is read in chunks of 1 million rows, so memory stays low (container is limited to 2GiB). 
- Before and after (your measurements):

| | Before | After |
|---|---|---|
| Elapsed | 44.00 s | 8.90 s |
| User | 44.02 s | 8.77 s |
| System | 0.58 s | 0.74 s |
| Peak memory | 750,648 KB | 443,280 KB |



## Task 5: Computing the statistics

- Symptom: Two problems. (1) `stats.sh` started 16 workers by default on a container with 8 CPUs (`nproc` = 8). (2) When I pressed Ctrl-C during the run, the script ended (exit status 130 = 128 + SIGINT) but the workers kept running: `ps -ef | grep stats_worker` showed 14 `stats_worker.py` processes with parent PID 1, still using the CPUs after the script was gone.
- Commands and recordings you used, why you chose them, and what they showed: `/usr/bin/time -f "$T" bash steps/stats.sh` for elapsed, user and system time, and `tools/sweep.sh` to repeat the run with 1, 2, 4, 8, 16... workers (result in `members/agendraieu2024/sweep.csv`). With more workers than CPUs the elapsed time stopped improving and user time grew, because the workers only compete for the same cores. For the Ctrl-C problem I ran the script, pressed Ctrl-C and looked at `ps -ef | grep stats_worker` right away (PPID 1 means the original parent died and init adopted the process); `pkill -f stats_worker` cleaned up afterwards.
- Cause: (1) `WORKERS` defaulted to 16, twice the number of CPUs. Extra workers do not add computing power, they only add scheduling and memory overhead. (2) The workers are started with `&` inside a non-interactive script. In that case bash starts background jobs with SIGINT ignored, so Ctrl-C does not reach them, and the script had no `trap` to stop them. They become orphans and run until they finish.
- Fix: `WORKERS=${WORKERS:-$(nproc)}`, one worker per CPU. The script now saves the PID of each worker in an array, has a `cleanup` function that kills them, and uses `trap cleanup EXIT`, `trap 'exit 130' INT` and `trap 'exit 143' TERM`, so the workers are stopped whenever the script ends. It also has `set -euo pipefail` and waits for each worker by PID, so a failed worker makes the script fail. Commit dcb4d7a: "Fix task 5: stats.sh uses one worker per CPU and stops its workers on exit".
- Before and after (your measurements): 
  - Before (median of my sweep): 16 workers took 8.87 s elapsed with about 64 s of user time.
  - After: 8 workers (= `nproc`) take 7.72 s elapsed with about 55 s of user time, so it is faster and uses less CPU time.
  - Ctrl-C test of the fixed script (with `WORKERS=2`, so that the run lasts about 17 s and I could interrupt it): exit status 130 and no `stats_worker.py` process left in `ps`. With the original script the same test left 14 orphans with PPID 1.
  - `python3 tools/check.py` shows PASS for `stats.csv` (72 rows).
  - Note: some later runs on my laptop took 21 to 26 s. I ran the original script at 8 workers in the same session and it also took 21.05 s (148.48 s user), so that slowdown came from my laptop at that moment (probably thermal throttling) and not from the fix. For the comparison I use the sweep medians, which were measured under the same conditions.

## The worker experiment

Every member runs `tools/sweep.sh` on their own laptop. Then run
`python3 tools/plot_sweep.py` and commit `results/sweep.png`.

![Elapsed time against the number of workers](results/sweep.png)

- How does the elapsed time change with the number of workers on each laptop?
- Why do the curves of your laptops differ? Use the cores and threads of each
  laptop, listed in `TEAM.md`.
- Which default number of workers did you choose for `stats.sh`, and why?

## Use of generative AI

Follow the format in the syllabus: quote any generated text and name the tool
and the prompts; add the same note as a comment before any generated code. If
you did not use GenAI, write: "No content generated by AI technologies has been
used in this assignment."


- Task 3 (MasihGhadbeygi): I used Claude (Anthropic) to guide me through the lab setup and the Task 3 diagnosis, to explain the strace and time outputs, and to write the fixed version of steps/audit.py (open the file once before the loop). Prompts were along the lines of 'walk me through Task 3 of Lab 1 step by step'. I ran all the commands and measurements myself on my laptop, and I checked the fix with tools/check.py, having a complete understanding of the Task. 
- Warm-up, Task 2 and Task 5 (agendraieu2024): I used Claude (Anthropic) as a tutor and assistant. It explained the outputs of `time`, `strace`, `ps` and `PIPESTATUS` to me, helped me with the diagnosis, helped me write and check the code of the fixed steps/extracts.sh and steps/stats.sh (the code is marked with a GenAI comment), and helped me write up these three sections of REPORT.md. Prompts were along the lines of 'help me fix Task 2 of Lab 1, extracts.sh writes empty files' and 'help me fix Task 5 of Lab 1, stats.sh uses too many workers and leaves them running after Ctrl-C'. I ran all the commands and measurements myself on my laptop, decided which fixes to apply after understanding each fault, tested them with tools/check.py and with the failure and Ctrl-C tests described above, and reviewed the text of the report.
- Warm-up, measurements, Task 4 (hzhangieu2024-hue): I used Claude (Anthropic) as a tutor and assistant. It help me fix some terminal setup problems I had, recover the original scripts from the git history (because was giving different results), and explain the outputs of 'time', 'strace', 'memory.events' and cProfile. Helped me diagnose Task 4 from the profile and assisted in writing the fixed version of steps/segment.py (The code is marked with a GenAI comment), and draft Task 4 section of REPORT.md and my measurements.md. Prompts were along the lines of 'help me complete measurements.md and the sweep', 'help me understand task 4 results and interpretation'. I ran all the commands and measurements myself on my laptop, checked the fix with diff against the original output and with tools/check.py. I understand the fault, its cause and the fix  

