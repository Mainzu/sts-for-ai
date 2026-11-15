"""Watches a running learned-play sweep (Amendment 3, C3) and prints one
line per event; it exits on a problem so the agent running the night is
woken. It stops nothing.

Reads, under the sweep's registry root: `logs/plan.json` (the sweep's pid,
its rows' projected minutes per round), `logs/sweep.log` (timestamped
starts, finishes and stops of rows), the rows' logs `logs/<row>.log`, the
run folders' `round.json`, and the system's memory.

Events:
- progress (no exit): each round a run finishes, with its tight-fight win
  rate next to the heuristic's, whether round 0 is still in and whether the
  gate is met;
- problems (exit 1, with the reason and evidence: log tail, memory,
  timings): a crash or a guard stop; no log output for SILENCE_MIN; a run
  past 2x its projected minutes; memory above MEMORY_LIMIT of the system's
  commit limit; a label-scale warning;
- a normal finish exits 0 with the table path.

Only what happens after the watcher starts is reported, so restarting it
after a problem doesn't repeat that problem; a sweep that has already
ended is reported at once.

    python scripts/sweep_watch.py --root <registry root> [--poll 30]
"""

import argparse
import ctypes
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import time

SILENCE_MIN = 30.0
SLOW_FACTOR = 2.0
MEMORY_LIMIT = 0.9
LABEL_WARNING = "WARNING labels off the outcome scale"
TAIL_LINES = 15


def now():
    return datetime.datetime.now().astimezone()


def memory():
    """(commit used / commit limit, physical load %) of the system."""
    class Status(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    s = Status()
    s.dwLength = ctypes.sizeof(Status)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
    return 1 - s.ullAvailPageFile / s.ullTotalPageFile, s.dwMemoryLoad


def python_memory():
    """The python processes' memory, as `tasklist` prints it (evidence)."""
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return "tasklist failed"
    rows = [line.strip().strip('"').split('","') for line in out.strip().splitlines() if line.startswith('"')]
    return ", ".join(f"pid {r[1]} {r[4]}" for r in rows if len(r) > 4) or "no python processes"


def pid_alive(pid):
    """Whether process `pid` is still running (Windows)."""
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(h)
    return code.value == 259  # STILL_ACTIVE


def tail(path, n=TAIL_LINES):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-n:]).rstrip()
    except OSError:
        return "(no log)"


def stamp(line):
    """(time, message) of a sweep.log line."""
    t, _, msg = line.rstrip("\n").partition(" ")
    return datetime.datetime.fromisoformat(t), msg


class Watcher:
    """One sweep's watch state. `check()` returns [(kind, text)] for what
    happened since the last check; kind is "progress", "problem" or
    "finished"."""

    def __init__(self, root, clock=now, mem=memory, alive=pid_alive):
        self.root, self.clock, self.mem, self.alive = root, clock, mem, alive
        self.logs = os.path.join(root, "logs")
        self.seen = set(self._round_files())
        self.offsets = {p: os.path.getsize(p) for p in self._log_files()}
        self.started = self.clock()

    def _round_files(self):
        return glob.glob(os.path.join(self.root, "runs", "*", "round.json"))

    def _log_files(self):
        return glob.glob(os.path.join(self.logs, "*.log"))

    def _read(self, path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _new_lines(self, path):
        """Lines appended to `path` since the last read (all of a new file)."""
        start = self.offsets.get(path, 0)
        with open(path, "rb") as f:
            f.seek(start)
            data = f.read()
        cut = data.rfind(b"\n") + 1  # leave a half-written line for next time
        self.offsets[path] = start + cut
        return data[:cut].decode("utf-8", errors="replace").splitlines()

    def plan(self):
        p = os.path.join(self.logs, "plan.json")
        return self._read(p) if os.path.exists(p) else None

    def sweep_log(self):
        """(row start times, finished rows, the end line or None) from the
        current sweep's lines of sweep.log (an earlier sweep in the same root
        appended the lines stamped before plan.json's `started`)."""
        starts, done, end = {}, set(), None
        since = (self.plan() or {}).get("started")
        since = datetime.datetime.fromisoformat(since) if since else None
        p = os.path.join(self.logs, "sweep.log")
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not line.strip():
                        continue
                    t, msg = stamp(line)
                    if since and t < since:
                        continue
                    if m := re.match(r"started (\S+)", msg):
                        starts[m.group(1)] = t
                    elif m := re.match(r"(\S+): (finished|exited)", msg):
                        done.add(m.group(1))
                    elif msg.startswith(("sweep finished", "sweep stopped")):
                        end = msg
        return starts, done, end

    def progress(self, path):
        rj = self._read(path)
        cfg = self._read(os.path.join(os.path.dirname(path), "config.json"))
        k, name = rj["round"], cfg.get("name", "?")
        if not rj.get("tight_win"):
            return f"{name} round {k} trained (val MSE {rj.get('val_mse', float('nan')):.4f})"
        halves = (rj.get("heuristic") or {}).get("halves", {})
        wins = ", ".join(f"{h} {v['net'][0]:.3f} vs heuristic {v['heuristic'][0]:.3f}" for h, v in halves.items())
        r0 = "round 0 in" if (rj.get("window") or {}).get("round0_in") else "round 0 out"
        gate = rj.get("gate")
        g = "" if gate is None else ("; GATE MET" if gate["met"] else "; gate not met")
        return f"{name} round {k}: tight-fight win {wins}; {r0}{g}"

    def rounds_done(self, name, since):
        """The highest round a row's runs finished since `since`."""
        best = None
        for p in self._round_files():
            folder = os.path.dirname(p)
            try:
                cfg = self._read(os.path.join(folder, "config.json"))
                created = datetime.datetime.fromisoformat(self._read(os.path.join(folder, "run.json"))["created"])
            except (OSError, KeyError, ValueError):
                continue
            if cfg.get("name") == name and created.astimezone() >= since:
                k = self._read(p)["round"]
                best = k if best is None else max(best, k)
        return best

    def check(self):
        out = []
        t = self.clock()
        for p in sorted(set(self._round_files()) - self.seen, key=os.path.getmtime):
            self.seen.add(p)
            try:
                out.append(("progress", self.progress(p)))
            except (OSError, KeyError, ValueError, TypeError) as e:
                out.append(("progress", f"{p}: unreadable round.json ({e})"))
        plan = self.plan()
        starts, done, end = self.sweep_log()
        # New log lines: a worker's exit, label-scale warnings.
        for p in self._log_files():
            for line in self._new_lines(p):
                if LABEL_WARNING in line:
                    out.append(("problem", f"label-scale warning in {os.path.basename(p)}: {line.strip()}\n"
                                           f"{tail(p)}"))
                if os.path.basename(p) == "sweep.log":
                    msg = stamp(line)[1] if line.strip() else ""
                    if m := re.match(r"(\S+): exited (\d+)", msg):
                        row, code = m.group(1), int(m.group(2))
                        why = "guard stop" if code == 3 else f"crash (exit {code})"
                        out.append(("problem", f"{row}: {why}\n{tail(os.path.join(self.logs, row + '.log'))}"))
        if end is not None:
            if end.startswith("sweep finished"):
                out.append(("finished", end))
            elif not any(k == "problem" for k, _ in out):
                out.append(("problem", f"{end}\n{tail(os.path.join(self.logs, 'sweep.log'))}"))
            return out
        if plan and not self.alive(plan["pid"]):
            out.append(("problem", f"the sweep process {plan['pid']} is gone without finishing\n"
                                   f"{tail(os.path.join(self.logs, 'sweep.log'))}"))
            return out
        logs = self._log_files()
        last = max([os.path.getmtime(p) for p in logs], default=self.started.timestamp())
        last = max(last, self.started.timestamp())
        if t.timestamp() - last > SILENCE_MIN * 60:
            newest = max(logs, key=os.path.getmtime) if logs else None
            out.append(("problem", f"no log output for {(t.timestamp() - last) / 60:.0f} min"
                        + (f"; last lines of {os.path.basename(newest)}:\n{tail(newest)}" if newest else "")))
        for name, t0 in starts.items():
            row = (plan or {}).get("rows", {}).get(name)
            if name in done or row is None:
                continue
            j = self.rounds_done(name, t0)
            j = row.get("first_round", 0) - 1 if j is None else j
            cum = row["minutes_by_round"]
            limit = SLOW_FACTOR * cum[min(j + 1, len(cum) - 1)]
            elapsed = (t - t0).total_seconds() / 60
            if limit > 0 and elapsed > limit:  # a dry run has no projection
                out.append(("problem", f"{name} past {SLOW_FACTOR:g}x its projection: {elapsed:.0f} min, "
                                       f"projected {cum[min(j + 1, len(cum) - 1)]:.0f} min through round "
                                       f"{min(j + 1, len(cum) - 1)} (last finished round: {j})\n"
                                       f"{tail(os.path.join(self.logs, name + '.log'))}"))
        used, phys = self.mem()
        if used > MEMORY_LIMIT:
            out.append(("problem", f"memory: commit {used:.0%} of the system's limit (physical {phys}%); "
                                   f"{python_memory()}"))
        return out


def main(argv=None, out=print, sleep=time.sleep, watcher=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="the sweep's registry root")
    ap.add_argument("--poll", type=float, default=30.0, help="seconds between checks")
    args = ap.parse_args(argv)
    w = watcher or Watcher(args.root)
    out(f"{now():%H:%M} watching {os.path.abspath(args.root)}", flush=True)
    while True:
        for kind, text in w.check():
            out(f"{now():%H:%M} {kind}: {text}", flush=True)
            if kind == "finished":
                return 0
            if kind == "problem":
                return 1
        sleep(args.poll)


if __name__ == "__main__":
    sys.exit(main())
