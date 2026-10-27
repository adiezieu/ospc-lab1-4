"""Records what a command does while it runs, so that you can replay it later.

Usage, inside the container, from the repository folder:
    python3 tools/record.py WHAT [-o FILE] COMMAND
for example
    python3 tools/record.py --memory python3 steps/report.py
    python3 tools/record.py --cpu --processes bash steps/stats.sh

WHAT is one or more of:
    --memory     memory of every process, and of the container
    --cpu        CPU time of every process, the CPU it ran on, and the load of every CPU
    --io         read and write system calls of every process, and the bytes they moved
    --processes  parent, state, working folder and files 0, 1, 2 of every process

The recorder reads /proc every 50 ms. It follows the command and every process
the command starts, until all of them have ended. Ctrl-C reaches the command as
usual; once the command has ended, Ctrl-C stops the recording.

The recording goes to recordings/ (or to FILE). To replay it, open
tools/replay.html in a browser on your laptop.
"""

import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import time

TICKS = os.sysconf("SC_CLK_TCK")
PAGE_KB = os.sysconf("SC_PAGE_SIZE") // 1024
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS = ["DATA", "OUT", "WORKERS"]


def read(path, size=65536):
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return None
    try:
        return os.read(fd, size).decode(errors="replace")
    except OSError:
        return None
    finally:
        os.close(fd)


def stat(pid):
    """Fields of /proc/PID/stat: comm, state, ppid, utime, stime, starttime, rss (KB), last CPU."""
    text = read(f"/proc/{pid}/stat", 4096)
    if not text:
        return None
    left, right = text.find("("), text.rfind(")")
    f = text[right + 2:].split()
    return (text[left + 1:right], f[0], int(f[1]), int(f[11]), int(f[12]),
            int(f[19]), int(f[21]) * PAGE_KB, int(f[36]))


def command_line(pid, comm):
    raw = read(f"/proc/{pid}/cmdline")
    if not raw:
        return f"[{comm}]"
    return " ".join(raw.rstrip("\0").split("\0"))


def switches(pid):
    text = read(f"/proc/{pid}/status")
    if not text:
        return None, None
    values = {}
    for key in ("\nvoluntary_ctxt_switches:", "\nnonvoluntary_ctxt_switches:"):
        i = text.find(key)
        values[key] = int(text[i + len(key):].split(None, 1)[0]) if i >= 0 else None
    return values["\nvoluntary_ctxt_switches:"], values["\nnonvoluntary_ctxt_switches:"]


def io(pid):
    text = read(f"/proc/{pid}/io")
    if not text:
        return None
    values = dict(line.split(": ") for line in text.splitlines() if ": " in line)
    return [int(values.get(k, 0)) for k in ("syscr", "syscw", "rchar", "wchar")]


def link(path):
    try:
        return os.readlink(path)
    except OSError:
        return None


def cpu_times(cpus):
    """User, system and total ticks of each CPU, from /proc/stat."""
    out = {}
    for line in (read("/proc/stat") or "").splitlines():
        if not line.startswith("cpu"):
            break
        name, *v = line.split()
        if name == "cpu" or int(name[3:]) not in cpus:
            continue
        v = [int(x) for x in v[:8]] + [0] * (8 - len(v[:8]))
        out[int(name[3:])] = (v[0] + v[1], v[2] + v[5] + v[6], sum(v))
    return out


def find_cgroup():
    """The cgroup that limits our memory: our own, or the closest parent with a limit."""
    own = None
    for line in (read("/proc/self/cgroup") or "").splitlines():
        if line.startswith("0::"):
            own = os.path.normpath("/sys/fs/cgroup/" + line[3:].strip().strip("/"))
    if not own or not os.path.exists(own + "/memory.current"):
        own = "/sys/fs/cgroup" if os.path.exists("/sys/fs/cgroup/memory.current") else None
    path = own
    while path:
        limit = (read(path + "/memory.max") or "max").strip()
        if limit != "max":
            return path, int(limit)
        if path == "/sys/fs/cgroup":
            break
        path = os.path.dirname(path)
    return own, None


def flat(path):
    """A flat-keyed cgroup file, such as memory.stat or memory.events, as a dict."""
    values = {}
    for line in (read(path) or "").splitlines():
        key, _, value = line.partition(" ")
        if value.strip().isdigit():
            values[key] = int(value)
    return values


class Process:
    def __init__(self, pid, st, i, cmd):
        self.pid, self.born_ticks, self.first, self.last = pid, st[5], i, None
        self.comm = st[0]
        self.cmd = [[i, cmd]]
        self.parent = [[i, st[2]]]
        self.series = {}
        self.changes = {}

    def add(self, name, value):
        self.series.setdefault(name, []).append(value)

    def change(self, name, i, value):
        history = self.changes.setdefault(name, [])
        if value is not None and (not history or history[-1][1] != value):
            history.append([i, value])


class Recorder:
    def __init__(self, what, interval):
        self.what, self.interval = what, interval
        self.t, self.events, self.procs, self.alive = [], [], [], {}
        self.ignored = set()
        self.cpus = sorted(os.sched_getaffinity(0))
        self.cgroup, self.memory_max = find_cgroup()
        self.container = {"current": [], "anon": [], "file": []}
        self.memory_events = []
        self.cpu_load = {"user": [], "system": [], "total": []}
        self.previous_cpu = None
        self.signals = []

    def event(self, i, kind, text, pid=None, t=None):
        self.events.append({"i": i, "kind": kind, "pid": pid, "text": text, "t": t})

    def discover(self, i):
        """Finds the processes started by the ones we follow since the last sample."""
        listed = {int(name) for name in os.listdir("/proc") if name.isdigit()}
        self.ignored &= listed
        new = {}
        for pid in listed - self.alive.keys() - self.ignored:
            st = stat(pid)
            if st:
                new[pid] = st
        found = True
        while found:
            found = False
            for pid, st in list(new.items()):
                if st[2] in self.alive:
                    p = Process(pid, st, i, command_line(pid, st[0]))
                    self.alive[pid] = p
                    self.procs.append(p)
                    self.event(i, "start", f"PID {pid} started: {p.cmd[0][1]} (parent {st[2]})", pid)
                    del new[pid]
                    found = True
        self.ignored |= new.keys()

    def sample(self, i, now):
        self.t.append(round(now * 1000))
        self.discover(i)
        for pid, p in list(self.alive.items()):
            st = stat(pid)
            if st is None or st[5] != p.born_ticks:
                self.end(i, p)
                continue
            if st[0] != p.comm:
                p.comm = st[0]
                cmd = command_line(pid, st[0])
                if cmd != p.cmd[-1][1]:
                    p.cmd.append([i, cmd])
            p.add("state", st[1])
            if "memory" in self.what:
                p.add("rss", st[6])
            if "cpu" in self.what:
                p.add("user", st[3])
                p.add("system", st[4])
                p.add("core", st[7])
                voluntary, involuntary = switches(pid)
                p.add("voluntary", voluntary)
                p.add("involuntary", involuntary)
            if "io" in self.what:
                # A process that has ended but not been collected (a zombie) has no /proc/PID/io:
                # keep its last values.
                names = ("read_calls", "write_calls", "read_bytes", "write_bytes")
                values = io(pid) or [p.series[name][-1] if p.series.get(name) else None for name in names]
                for name, value in zip(names, values):
                    p.add(name, value)
            if "processes" in self.what:
                if st[2] != p.parent[-1][1]:
                    self.event(i, "parent", f"PID {pid}: parent changed from {p.parent[-1][1]} to {st[2]}", pid)
                    p.parent.append([i, st[2]])
                p.change("cwd", i, link(f"/proc/{pid}/cwd"))
                for fd in (0, 1, 2):
                    p.change(f"fd{fd}", i, link(f"/proc/{pid}/fd/{fd}"))
            else:
                if st[2] != p.parent[-1][1]:
                    p.parent.append([i, st[2]])
        if "memory" in self.what and self.cgroup:
            current = read(self.cgroup + "/memory.current")
            memory_stat = flat(self.cgroup + "/memory.stat")
            self.container["current"].append(int(current) // 1024 if current else None)
            self.container["anon"].append(memory_stat.get("anon", 0) // 1024)
            self.container["file"].append(memory_stat.get("file", 0) // 1024)
            counters = flat(self.cgroup + "/memory.events")
            if not self.memory_events or self.memory_events[-1][1] != counters:
                if self.memory_events:
                    old = self.memory_events[-1][1]
                    changed = [f"{k} {old.get(k, 0)} → {v}" for k, v in counters.items() if old.get(k, 0) != v]
                    self.event(i, "memory.events", "memory.events: " + ", ".join(changed))
                self.memory_events.append([i, counters])
        if "cpu" in self.what:
            times = cpu_times(self.cpus)
            for k, name in enumerate(("user", "system", "total")):
                if self.previous_cpu is None:
                    self.cpu_load[name].append([0] * len(self.cpus))
                else:
                    self.cpu_load[name].append([times.get(c, (0, 0, 0))[k] - self.previous_cpu.get(c, (0, 0, 0))[k]
                                                for c in self.cpus])
            self.previous_cpu = times

    def end(self, i, p):
        p.last = i - 1
        del self.alive[p.pid]
        self.event(i, "end", f"PID {p.pid} ended", p.pid)

    def save(self, path, command, result):
        processes = []
        for p in self.procs:
            processes.append({"pid": p.pid, "first": p.first, "last": p.last,
                              "born": round((p.born_ticks / TICKS - self.boot_t0) * 1000),
                              "cmd": p.cmd, "parent": p.parent, **p.series, **p.changes})
        recording = {
            "format": "ospc-recording-1",
            "command": command,
            "folder": os.getcwd(),
            "date": self.date,
            "recorded": [w for w in ("memory", "cpu", "io", "processes") if w in self.what],
            "interval_ms": round(self.interval * 1000),
            "machine": {"hostname": os.uname().nodename, "kernel": os.uname().release,
                        "cpus": self.cpus, "memory_kb": memory_total(),
                        "cgroup": self.cgroup, "memory_max_kb": self.memory_max // 1024 if self.memory_max else None,
                        "ticks_per_second": TICKS},
            "settings": {k: os.environ[k] for k in SETTINGS if k in os.environ},
            "t": self.t,
            "result": result,
            "events": [dict(e, t=e["t"] if e["t"] is not None else self.t[min(e["i"], len(self.t) - 1)])
                       for e in self.events],
            "processes": processes,
        }
        if "memory" in self.what:
            recording["container"] = dict(self.container, events=self.memory_events)
        if "cpu" in self.what:
            recording["cpu_load"] = self.cpu_load
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(recording, f, separators=(",", ":"))


def memory_total():
    for line in (read("/proc/meminfo") or "").splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1])
    return None


def default_name(command):
    name = os.path.basename(command[0])
    for arg in command:
        if arg.endswith((".py", ".sh")):
            name = os.path.basename(arg)[:-3]
            break
    stamp = datetime.datetime.now().strftime("%H%M%S")
    return os.path.join(ROOT, "recordings", f"{name}-{stamp}.json")


def shell_status(status):
    """The exit status as the shell reports it: 128 + N for a process killed by signal N."""
    return os.waitstatus_to_exitcode(status) if os.WIFEXITED(status) else 128 + os.WTERMSIG(status)


def main():
    parser = argparse.ArgumentParser(
        prog="python3 tools/record.py",
        description="Records what a command does while it runs. Replay it with tools/replay.html.")
    parser.add_argument("--memory", action="store_true", help="memory of every process, and of the container")
    parser.add_argument("--cpu", action="store_true", help="CPU time, the CPU each process ran on, and the load of every CPU")
    parser.add_argument("--io", action="store_true", help="read and write system calls, and the bytes they moved")
    parser.add_argument("--processes", action="store_true", help="parent, state, working folder and files 0, 1, 2")
    parser.add_argument("-o", "--output", metavar="FILE", help="where to save the recording (default: recordings/)")
    parser.add_argument("--interval", type=float, default=0.05, metavar="SECONDS", help="time between samples (default: 0.05)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="the command to record")
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    what = {w for w in ("memory", "cpu", "io", "processes") if getattr(args, w)}
    if not what:
        parser.error("choose what to record: --memory, --cpu, --io, --processes (one or more)")
    if not command:
        parser.error("give the command to record, for example: python3 tools/record.py --memory python3 steps/report.py")
    path = args.output or default_name(command)

    rec = Recorder(what, args.interval)
    rec.date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def on_signal(signum, frame):
        rec.signals.append((signum, time.monotonic()))

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    print(f"record: recording {', '.join(sorted(what))} of: {' '.join(command)}", file=sys.stderr)
    t0 = time.monotonic()
    rec.boot_t0 = time.clock_gettime(time.CLOCK_BOOTTIME)
    try:
        child = subprocess.Popen(command)
    except FileNotFoundError:
        print(f"record: {command[0]}: command not found", file=sys.stderr)
        sys.exit(127)
    except PermissionError:
        print(f"record: {command[0]}: Permission denied", file=sys.stderr)
        sys.exit(126)
    signal.signal(signal.SIGQUIT, signal.SIG_IGN)

    st = stat(child.pid)
    root = Process(child.pid, st, 0, " ".join(command)) if st else None
    if root:
        rec.alive[child.pid] = root
        rec.procs.append(root)
        rec.event(0, "start", f"PID {child.pid} started: {' '.join(command)}", child.pid)

    result, i, seen, stop, told = None, 0, 0, False, False
    next_time = t0
    while True:
        now = time.monotonic()
        # Events in the order they happened: signals, then the end of the
        # command, then what the sample shows (for example, new parents).
        while seen < len(rec.signals):
            signum, when = rec.signals[seen]
            name = "Ctrl-C (SIGINT)" if signum == signal.SIGINT else "SIGTERM"
            rec.event(i, "signal", f"{name} received", t=round((when - t0) * 1000))
            seen += 1
            if result is not None:
                stop = True
        if result is None and i > 0:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                result = {"status": shell_status(status), "elapsed_s": round(now - t0, 2),
                          "user_s": round(usage.ru_utime, 2), "system_s": round(usage.ru_stime, 2),
                          "peak_memory_kb": usage.ru_maxrss}
                rec.event(i, "exit", f"PID {child.pid} ended with exit status {result['status']}", child.pid)
                if child.pid in rec.alive:
                    root.last = i - 1
                    del rec.alive[child.pid]
        rec.sample(i, now - t0)
        if result is not None:
            if rec.alive and not told:
                told = True
                print(f"record: the command ended with exit status {result['status']}; "
                      f"{len(rec.alive)} of the processes it started are still running. "
                      "Recording continues until they end; Ctrl-C stops it.", file=sys.stderr)
            if not rec.alive or stop:
                break
        i += 1
        next_time += args.interval
        delay = next_time - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            next_time = time.monotonic()

    if rec.alive:
        rec.event(i, "stop", f"Recording stopped with {len(rec.alive)} processes still running")
    rec.save(path, " ".join(command), result)
    shown = os.path.relpath(path)
    print(f"record: saved {shown} ({rec.t[-1] / 1000:.1f} s, {len(rec.t)} samples). "
          "Open tools/replay.html in your browser to replay it.", file=sys.stderr)
    sys.exit(result["status"])


if __name__ == "__main__":
    main()
