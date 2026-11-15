"""Job queue and runner (docs/specs/job-queue.md, docs/specs/lanes-runner.md): managers add jobs, one
runner starts each when the machine has room, records how it ended, and
flags a job whose log stopped changing or shows a crash. It kills a job
only when asked (`kill`).

State lives under `jobs/` (gitignored): `pending/`, `running/`, `done/`,
one JSON file per job named `<NNNN>-<slug>.json` (the file name is the
id), plus `runner.log` (one line per event) and `runner.pid`. A job changes
state by moving between the folders. Each job belongs to a lane (default
`main`); within a lane jobs start in name order.

    python scripts/jobs.py add --threads 8 [--light] [--mem-gb 2] [--silence-min 30] [--lane main]
                               [--estimate-min 90] [--note "..."] -- python -u scripts/curve.py ...
    python scripts/jobs.py status
    python scripts/jobs.py first <id>     # the reservation now, and first in its lane
    python scripts/jobs.py add ... [--after a,b] [--if-passed a,b] [--on-fail park|cancel] [--check "cmd"] -- ...
    python scripts/jobs.py set <id> [--lane L] [--after a,b] [--if-passed a,b] [--on-fail park|cancel]
    python scripts/jobs.py unpark <id>
    python scripts/jobs.py estimate <id> <minutes> [--reason "..."]   # a pending or running job's estimate
    python scripts/jobs.py pins            # snapshots and the jobs pinned to them
    python scripts/jobs.py impact sts|scripts   # unpinned jobs a swap or merge would hit (exit 1 if any)
    python scripts/jobs.py unpin <commit>  # remove a snapshot no job uses (else only the runner's sweep does)
    python scripts/jobs.py verdict <id> pass|fail [--reason "..."]
    python scripts/jobs.py cancel <id>
    python scripts/jobs.py kill <id> [--reason "..."]   # the runner ends the job's tree next poll
    python scripts/jobs.py run [--poll 30] [--heavy-slots 2] [--thread-budget 14]
    python scripts/jobs.py wait [--poll 30]   # exits on the next end, stall, suspect, parked or waiting: 0 ok, 1 look

A job starts only when all hold: its heavy slot fits `heavy-slots` beside
the runner's running jobs (light jobs take none, a heavy job of 2 threads
or fewer half a slot), its own jobs' threads
plus this one fit `thread-budget`, the system's idle CPU over the last poll
is at least `threads` cores (so runs started by hand and other projects
count), the running jobs' reserved memory (`mem_gb`, or the measured
`peak_gb` when higher) plus this one's `mem_gb` fit total physical memory
minus 1 GB (jobs grow, and two peaking together killed one), and free
memory (the smaller of free physical memory and commit headroom) is at
least `mem_gb` + 1 GB. When none of the runner's jobs runs, commit
headroom alone counts as free memory, so one job always runs and may page.

Which job: lane heads are tried in order of lowest use / share, where a
lane's use sums, over its running jobs, the larger of threads / thread
budget and reserved memory / (total memory - 1 GB). When a lane's head
waits for memory only, a later job of that lane may start (backfill). The
top lane head, once it has waited `RESERVE_MIN` for any reason, gets the
reservation (one holder at a time; `first` gives it at once): while a job
holds it, another job starts only if it fits alongside it (slots, thread
budget, reserved memory, as if both ran), and the holder is tried first.
After `WAITING_MIN` the holder logs `waiting`. A lane with share 0 or
below is a filler lane: its head is tried only when no other lane's job
started this poll, and only if it fits alongside a reservation; `add`
refuses a filler job that is neither `--resumable` nor estimated at
`FILLER_MAX_MIN` or less. One job starts per poll, so
the next poll's idle reading includes it.

Conditions: a job with `after` waits until each named job has ended; with
`if_passed`, until each has ended and passed. A waiting job doesn't block
the jobs behind it. When a condition can't hold any more (an `if_passed`
dependency failed, was cancelled or refused, or ended-unknown without a
verdict; any dependency is parked or in no folder), the job is parked (`parked: reason`, a
`parked` event) or, with `on_fail: cancel`, cancelled; parking cascades
through chains in the same poll. A verdict comes from the job's `check`
command, run when it ends `ok` as its own light process through the
wrapper (`running/<id>.check.json`; exit 0 = pass, killed after
`CHECK_MIN`); without a check, `ok` passes. `verdict` sets one by hand. A job that can never start (threads above the
budget, `mem_gb` + 1 GB above total memory, a missing or bad field) is
moved to done as refused.

Each job runs through a frozen wrapper, `jobs/runner-<pid>/exec.py`,
written at `run` start from `EXEC_PY` (standard library only, argv fixed
across versions), so an edit or merge of this file can't break a job that
starts later. The wrapper writes the command's exit code to
`running/<id>.exit`, so a job adopted after a restart still ends `ok` or
`failed`. Lane shares come from `jobs/lanes.json` (`{"lane": share}` over
`DEFAULT_SHARES`), read each poll; a bad file keeps the last good shares.

Each started job runs in its own Job Object (no kill-on-close, so jobs
outlive the runner), and counts as running until its whole process tree
is gone. A job adopted after a runner restart has no Job Object: only its
top pid (the wrapper) is watched, and it is killed with `taskkill /T`; with
no exit file (a job started before the wrapper existed) its exit code is
unknown (`ended-unknown`). A log tail with a crash line (`Traceback`,
`MemoryError`, `memory allocation of`, `BrokenProcessPool`) is flagged
`suspect` once, so `wait` wakes the manager early. Each poll samples the
working set of a running job's process tree (its pid and all descendants)
and keeps the largest sum as `peak_gb`, so `mem_gb` can be set from it.
"""

import argparse
import ctypes
import datetime
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_watch import pid_alive  # noqa: E402



def main_checkout(here):
    """The main checkout of the repository holding `here`: a lane worktree's
    jobs.py queues into, logs to and links snapshots to main's data, never
    the worktree's empty ignored folders."""
    try:
        common = subprocess.run(["git", "-C", here, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return here
    return os.path.normpath(os.path.dirname(common)) if os.path.basename(common) == ".git" else here


HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # this checkout: `--pin HEAD` is its HEAD
REPO = main_checkout(HERE)
ROOT = os.path.join(REPO, "jobs")
STATES = ("pending", "running", "done")
MEM_HEADROOM_GB = 1.0
SILENCE_MIN = 30.0
RESERVE_MIN = 10.0  # how long the top lane head waits before it gets the reservation
WAITING_MIN = 30.0  # how long a job holding the reservation waits before a `waiting` event
DEFAULT_SHARE = 10  # a lane missing from lanes.json
CHECK_MIN = 10.0  # a check process running longer is killed: verdict fail (timeout)
# Pinned code (docs/specs/lanes-runner.md §5): snapshots live outside the repo
BUILDS = os.path.join(os.path.dirname(REPO), "sts-builds")
PIN_PATHS = ("scripts", "engine", "py", "solvedb", "configs", "data/bench", "Cargo.toml", "Cargo.lock", ".cargo")
MODULE_PATHS = ("engine", "py", "solvedb", "Cargo.toml", "Cargo.lock", ".cargo")  # what the sts module is built from
JUNCTIONS = ("results", "db", "cache", "datasets", "models", "logs", "jobs", ".venv", "scripts/analysis/out")
NOT_DATA = ("target", ".pytest_cache", ".claude")  # ignored folders a snapshot needn't see
UNPIN_IDLE_H = 24.0  # the runner unpins a snapshot no pending or running job used for this long
FILLER_MAX_MIN = 20.0  # a filler job must be resumable or estimated at most this long
# runner.log events and the exit code `wait` gives them ("ended": an adopted
# job's end as runners before ended-unknown logged it)
EVENTS = {"ok": 0, "ended": 0, "ended-unknown": 1, "failed": 1, "lost": 1, "stalled": 1, "refused": 1,
          "killed": 1, "suspect": 1, "waiting": 1, "parked": 1}
SUSPECT = re.compile(r"memory allocation of|MemoryError|BrokenProcessPool|Traceback")
DEFAULT_SHARES = {"depth": 35, "run": 30, "goal1": 25, "train": 10, "main": 10, "filler": 0}

# The frozen wrapper (docs/specs/lanes-runner.md §1). Standard library only, and
# its argv never changes (`exec.py <exit file> -- <cmd...>`): each runner starts
# jobs through the copy it wrote at its own start.
EXEC_PY = '''"""Job wrapper written by scripts/jobs.py: runs the command with this
process's cwd, env and standard handles, writes its exit code to the exit
file (temp file, then rename) and exits with that code."""
import os
import subprocess
import sys

exit_file, sep, cmd = sys.argv[1], sys.argv[2], sys.argv[3:]
assert sep == "--", sys.argv
try:
    code = subprocess.call(cmd, stdin=0, stdout=1, stderr=2)
except OSError as err:
    print(f"exec.py: {err}", flush=True)
    code = 127
with open(exit_file + ".tmp", "w") as f:
    f.write(str(code))
os.replace(exit_file + ".tmp", exit_file)
sys.exit(code)
'''

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
CREATE_BREAKAWAY_FROM_JOB = 0x01000000

# own kernel32 instance, so these argtypes don't change ctypes.windll's
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateJobObjectW.restype = ctypes.c_void_p
_k32.CreateJobObjectW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p)
_k32.AssignProcessToJobObject.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
_k32.TerminateJobObject.argtypes = (ctypes.c_void_p, ctypes.c_uint)
_k32.QueryInformationJobObject.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong,
                                           ctypes.c_void_p)
_k32.CloseHandle.argtypes = (ctypes.c_void_p,)


def lane(job):
    return job.get("lane", "main")


def slot_w(job):
    """Heavy slots a job takes: none if light, half for 2 threads or fewer."""
    return 0.0 if not job.get("heavy", True) else 0.5 if job["threads"] <= 2 else 1.0


def held_gb(job):
    """Memory a running job reserves: its mem_gb, or its measured peak if higher."""
    return max(job.get("mem_gb", 1.0), job.get("peak_gb", 0.0))


def lane_use(running, budget, cap):
    """Each lane's use: over its running jobs, the sum of the larger of
    threads / thread budget and reserved memory / `cap` (total - headroom)."""
    use = {}
    for j in running:
        use[lane(j)] = use.get(lane(j), 0.0) + max(j["threads"] / budget, held_gb(j) / cap)
    return use


def check_fields(job):
    """Raise KeyError, TypeError or ValueError if a (hand-made) pending job
    lacks a field the runner reads or holds one of the wrong type."""
    for v in (job["threads"], job.get("mem_gb", 1.0), job.get("first_at", 0), job.get("reserved_at", 0),
              job.get("wait_since", 0)):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise TypeError(f"not a number: {v!r}")
    if not isinstance(lane(job), str) or not job["cmd"]:
        raise ValueError("lane not a string or cmd empty")


def passed(job):
    """A done job's verdict: True (pass), False (fail), or None while its
    check hasn't decided. Without a check, `ok` passes."""
    if "verdict" in job:
        return job["verdict"] == "pass"
    if job.get("status") == "ok" and job.get("check"):
        return None
    return job.get("status") == "ok"


def condition(job, find):
    """Whether a pending job's `after` / `if_passed` hold: None (they do),
    "wait", or why it parks. `find(id)` gives (state, job) or (None, None);
    state "parked" is the manual `jobs/parked/` folder."""
    wait = False
    for kind in ("after", "if_passed"):
        for dep in job.get(kind, []):
            state, d = find(dep)
            if state is None:
                return f"{dep} is in no folder"
            if state == "parked" or d.get("parked"):
                return f"{dep} is parked"
            ok = passed(d) if state == "done" else None
            if ok is None:
                wait = True  # pending, running, or its check runs
            elif kind == "if_passed" and not ok:
                why = d.get("verdict_reason") or d.get("reason") or ""
                return f"{dep} did not pass ({d.get('verdict') or d.get('status')}{': ' + why if why else ''})"
    return "wait" if wait else None


def cmd_key(cmd):
    """The script of a command and its first argument (looked for inside a
    `bash -c` string too), to match earlier runs of the same command."""
    words = [w for a in cmd for w in a.split()]
    i = next((i for i, w in enumerate(words) if w.endswith(".py")), 0)
    return words[i:i + 2]


def read_shares(root):
    """Lane shares: `lanes.json` under `root` over DEFAULT_SHARES. Raises
    OSError, ValueError or TypeError on a bad file."""
    try:
        with open(os.path.join(root, "lanes.json"), encoding="utf-8") as f:
            got = json.load(f)
    except FileNotFoundError:
        got = {}
    if not isinstance(got, dict) or not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                           for v in got.values()):
        raise TypeError("lanes.json must map lane names to numbers")
    return {**DEFAULT_SHARES, **got}


def now_iso(t=None):
    return datetime.datetime.fromtimestamp(time.time() if t is None else t).astimezone().isoformat(timespec="seconds")


class MemStatus(ctypes.Structure):  # MEMORYSTATUSEX
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def mem_status():
    s = MemStatus()
    s.dwLength = ctypes.sizeof(MemStatus)
    _k32.GlobalMemoryStatusEx(ctypes.byref(s))
    return s


def free_gb(s=None):
    """Memory a new job can take, in GB: the smaller of free physical memory
    and commit headroom (ullAvailPageFile; allocations fail when commit runs
    out, however much RAM looks free)."""
    s = s or mem_status()
    return min(s.ullAvailPhys, s.ullAvailPageFile) / 2**30


def commit_gb(s=None):
    """Commit headroom in GB (ullAvailPageFile): what RAM plus pagefile can
    still hand out before allocations fail."""
    s = s or mem_status()
    return s.ullAvailPageFile / 2**30


def total_gb(s=None):
    """Total physical memory, in GB."""
    s = s or mem_status()
    return s.ullTotalPhys / 2**30


class JobAccounting(ctypes.Structure):  # JOBOBJECT_BASIC_ACCOUNTING_INFORMATION
    _fields_ = [("TotalUserTime", ctypes.c_longlong), ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong), ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", ctypes.c_ulong), ("TotalProcesses", ctypes.c_ulong),
                ("ActiveProcesses", ctypes.c_ulong), ("TotalTerminatedProcesses", ctypes.c_ulong)]


def job_object(p):
    """Put a started process (a Popen) in a new Job Object, so its whole tree
    can be counted and ended; its children join it. None if Windows refuses.
    No kill-on-close: the tree outlives the runner's handle."""
    h = _k32.CreateJobObjectW(None, None)
    if h and _k32.AssignProcessToJobObject(h, int(p._handle)):
        return h
    if h:
        _k32.CloseHandle(h)
    return None


class ProcessEntry(ctypes.Structure):  # PROCESSENTRY32W
    _fields_ = [("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong), ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", ctypes.c_ulong),
                ("cntThreads", ctypes.c_ulong), ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_wchar * 260)]


class MemCounters(ctypes.Structure):  # PROCESS_MEMORY_COUNTERS
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
        (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                       "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                       "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]


_k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
_k32.CreateToolhelp32Snapshot.argtypes = (ctypes.c_ulong, ctypes.c_ulong)
_k32.Process32FirstW.argtypes = _k32.Process32NextW.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
_k32.OpenProcess.restype = ctypes.c_void_p
_k32.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
_k32.K32GetProcessMemoryInfo.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)


def tree_mem_gb(job):
    """Working set (GB) of a job's process tree: its pid and all descendants
    (one process snapshot). 0.0 if nothing can be read."""
    snap = _k32.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if not snap or snap == ctypes.c_void_p(-1).value:
        return 0.0
    kids = {}
    try:
        e = ProcessEntry()
        e.dwSize = ctypes.sizeof(ProcessEntry)
        ok = _k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            if e.th32ProcessID != e.th32ParentProcessID:
                kids.setdefault(e.th32ParentProcessID, []).append(e.th32ProcessID)
            ok = _k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        _k32.CloseHandle(snap)
    todo, seen, total = [job.get("pid", 0)], set(), 0
    while todo:
        pid = todo.pop()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        todo += kids.get(pid, [])
        h = _k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if h:
            c = MemCounters()
            c.cb = ctypes.sizeof(MemCounters)
            if _k32.K32GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
                total += c.WorkingSetSize
            _k32.CloseHandle(h)
    return total / 2**30


def job_active(h):
    """Processes still running in Job Object `h` (0 if it can't be read)."""
    info = JobAccounting()  # info class 1 = JobObjectBasicAccountingInformation
    if not _k32.QueryInformationJobObject(h, 1, ctypes.byref(info), ctypes.sizeof(info), None):
        return 0
    return info.ActiveProcesses


def kill_tree(job, h):
    """End a job's whole process tree: through its Job Object `h`, or for a
    job without one (adopted) by its pid's tree."""
    if h:
        _k32.TerminateJobObject(h, 1)
    else:
        subprocess.run(["taskkill", "/PID", str(job["pid"]), "/T", "/F"], capture_output=True)


def log_tail(path, size=8192):
    """The last `size` bytes of a log as text ("" if it can't be read)."""
    try:
        with open(path, "rb") as f:
            f.seek(max(0, os.path.getsize(path) - size))
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


class IdleCores:
    """Idle cores of the whole system between successive calls
    (GetSystemTimes; kernel time includes idle time). The first call
    measures over `first` seconds."""

    def __init__(self, first=2.0):
        self.first, self.last = first, None

    @staticmethod
    def _times():
        idle, kernel, user = (ctypes.c_ulonglong() for _ in range(3))
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
        return idle.value, kernel.value + user.value

    def __call__(self):
        if self.last is None:
            self.last = self._times()
            time.sleep(self.first)
        cur = self._times()
        d_idle, d_total = cur[0] - self.last[0], cur[1] - self.last[1]
        self.last = cur
        return os.cpu_count() * d_idle / d_total if d_total > 0 else 0.0


def retry(fn, *args, tries=20):
    """Run a file operation, retrying while a reader (`status`, `wait`, an
    editor) holds the file open: Windows refuses replace and delete then."""
    for i in range(tries):
        try:
            return fn(*args)
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(0.05)


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    retry(os.replace, tmp, path)


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout


def junction(link, target):
    os.makedirs(os.path.dirname(link), exist_ok=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", os.path.normpath(link), os.path.normpath(target)],
                   capture_output=True, check=True)


def dirty_paths(repo):
    """Changed or untracked files under the paths a pin covers."""
    return [l[3:] for l in git(repo, "status", "--porcelain", "--untracked-files=all", "--", *PIN_PATHS).splitlines()]


def uncovered(repo):
    """Ignored folders of `repo` that a snapshot would neither junction nor
    link (a new data folder pinned jobs wouldn't see)."""
    out = []
    for line in git(repo, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory").splitlines():
        p = line.strip('"').rstrip("/")
        if not line.endswith("/") or p.split("/")[0] in ("runs", "data") or p.split("/")[-1] == "__pycache__" \
                or any(p == n or p.startswith(n + "/") for n in JUNCTIONS + NOT_DATA):
            continue
        out.append(p)
    return out


def link_data(snap, repo):
    """Link each entry of main's `data/` missing from the snapshot: a
    junction for a folder, a hard link for a file. Returns the new names."""
    new = []
    for name in sorted(os.listdir(os.path.join(repo, "data"))):
        link, target = os.path.join(snap, "data", name), os.path.join(repo, "data", name)
        if os.path.lexists(link):
            continue  # data/bench (the snapshot's own) or linked before
        if os.path.isdir(target):
            junction(link, target)
        else:
            os.link(target, link)
        new.append(name)
    return new


def build_module(snap, pyroot, builds):
    """Build the snapshot's `sts` wheel into `pyroot/wheel/` (shared cargo
    target folder for snapshot builds, 4 cargo jobs)."""
    env = dict(os.environ, CARGO_TARGET_DIR=os.path.join(builds, "target"), CARGO_BUILD_JOBS="4")
    subprocess.run([os.path.join(snap, ".venv", "Scripts", "maturin.exe"), "build", "--release", "-o",
                    os.path.join(pyroot, "wheel")], cwd=os.path.join(snap, "py"), env=env, check=True,
                   capture_output=True)


def snapshot_wheel(snap):
    """The snapshot's `sts` wheel, or None."""
    d = os.path.join(snap, "pyroot", "wheel")
    whl = sorted(os.listdir(d)) if os.path.isdir(d) else []
    return os.path.join(d, whl[-1]) if whl else None


def snapshot(commit, repo=REPO, builds=BUILDS, build=build_module):
    """The snapshot of `commit` (made if missing): a detached, locked
    worktree `builds/<c12>` with main's data folders junctioned or linked
    in and its own `sts` module in `pyroot/`. Returns (path, full commit,
    names newly linked into data/)."""
    import zipfile
    c = git(repo, "rev-parse", "--verify", commit + "^{commit}").strip()
    snap = os.path.join(builds, c[:12])
    pyroot = os.path.join(snap, "pyroot")
    if not os.path.isfile(os.path.join(pyroot, "key.txt")):  # missing or half made: each part redoes itself
        bad = uncovered(repo)
        if bad:
            raise ValueError(f"main has ignored folders a snapshot wouldn't link: {', '.join(bad)}")
        os.makedirs(builds, exist_ok=True)
        if not os.path.exists(snap):
            git(repo, "worktree", "add", "--detach", "--lock", snap, c)
        elif not os.path.isfile(os.path.join(snap, ".git")):
            raise ValueError(f"{snap} is left from a removal that failed (a process had its cwd there?); "
                             "check it holds no links, then delete it")
        runs = os.path.join(snap, "runs")
        if not os.path.isjunction(runs):
            tracked = [p[len("runs/"):] for p in git(snap, "ls-files", "runs").splitlines()]
            if tracked:
                git(snap, "update-index", "--skip-worktree", *("runs/" + p for p in tracked))
            have = [os.path.relpath(os.path.join(d, f), runs).replace("\\", "/")
                    for d, _, fs in os.walk(runs) for f in fs]
            if set(have) - set(tracked):
                raise ValueError(f"{runs} holds untracked files: {sorted(set(have) - set(tracked))}")
            shutil.rmtree(runs, ignore_errors=True)
            junction(runs, os.path.join(repo, "runs"))
        for name in JUNCTIONS:
            link = os.path.join(snap, name)
            if not os.path.lexists(link):
                os.makedirs(os.path.join(repo, name), exist_ok=True)
                junction(link, os.path.join(repo, name))
        key = hashlib.sha256(git(repo, "ls-tree", c, "--", *MODULE_PATHS).encode()).hexdigest()
        donor = next((os.path.join(builds, d, "pyroot") for d in sorted(os.listdir(builds)) if d != c[:12]
                      and _read(os.path.join(builds, d, "pyroot", "key.txt")) == key), None)
        shutil.rmtree(pyroot, ignore_errors=True)
        os.makedirs(pyroot)
        if donor:  # same module trees: the same bytes, hard-linked
            for d, _, fs in os.walk(donor):
                for f in fs:
                    rel = os.path.relpath(os.path.join(d, f), donor)
                    if rel not in ("key.txt", "used"):
                        os.makedirs(os.path.dirname(os.path.join(pyroot, rel)), exist_ok=True)
                        os.link(os.path.join(d, f), os.path.join(pyroot, rel))
        else:
            build(snap, pyroot, builds)
            with zipfile.ZipFile(snapshot_wheel(snap)) as z:
                z.extractall(pyroot, [n for n in z.namelist() if n.startswith("sts/")])
        with open(os.path.join(pyroot, "key.txt"), "w") as f:
            f.write(key)
    return snap, c, link_data(snap, repo)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def unpin_snapshot(snap, repo=REPO):
    """Remove a snapshot (the caller checked no job uses it): refuse, naming
    the paths, if it holds anything besides its links, pyroot/ and caches;
    remove every junction and data link; then let git remove the rest.
    Raises ValueError when refused."""
    def linked(rel):  # a junction, or a hard link to main's file of that name
        p, m = os.path.join(snap, rel), os.path.join(repo, rel)
        return os.path.isjunction(p) or os.path.isfile(p) and os.path.isfile(m) and os.path.samefile(p, m)

    links = [l for l in list(JUNCTIONS) + ["runs"] + [f"data/{n}" for n in os.listdir(os.path.join(snap, "data"))]
             if linked(l)]
    st = git(snap, "status", "--porcelain", "--ignored", "--untracked-files=all", "--", ".",
             *(f":(exclude){l}" for l in links if os.path.isjunction(os.path.join(snap, l))))
    bad = []
    for line in st.splitlines():
        code, path = line[:2], line[3:].strip('"')
        if code not in ("??", "!!"):
            bad.append(line)  # a changed tracked file: a job's output
        elif not (path.startswith(("pyroot/", ".pytest_cache/")) or "__pycache__/" in "/" + path
                  or any(path == l or path.startswith(l + "/") for l in links)):
            bad.append(line)
    if bad:
        raise ValueError("holds files besides its links: " + "; ".join(bad))
    git(repo, "worktree", "unlock", snap)  # fails here, before anything is removed, if repo is wrong
    if os.path.exists(os.path.join(snap, "pyroot", "key.txt")):  # a half-made one has none
        os.remove(os.path.join(snap, "pyroot", "key.txt"))  # from here on a partial removal counts as half made
    for l in links:
        p = os.path.join(snap, l)
        if os.path.isjunction(p):
            subprocess.run(["cmd", "/c", "rmdir", os.path.normpath(p)], capture_output=True, check=True)
        else:
            os.remove(p)  # a hard link: main's file stays
    left = [os.path.join(d, n) for d, ds, fs in os.walk(snap) for n in ds + fs
            if os.path.isjunction(os.path.join(d, n)) or os.path.islink(os.path.join(d, n))]
    if left:
        raise ValueError(f"links left after removal, not removing: {left}")
    git(repo, "worktree", "remove", "--force", snap)


class Queue:
    """The job folders under `root`; pinned jobs' snapshots of `repo` live
    under `builds`."""

    def __init__(self, root=ROOT, repo=REPO, builds=BUILDS, build=build_module, here=None):
        self.root, self.repo, self.builds, self.build = root, repo, builds, build
        self.here = here or repo  # the checkout whose HEAD and changes `pin="HEAD"` means
        for s in STATES:
            os.makedirs(os.path.join(root, s), exist_ok=True)
        self.log_path = os.path.join(root, "runner.log")

    def path(self, state, jid):
        return os.path.join(self.root, state, jid + ".json")

    def jobs(self, state):
        d = os.path.join(self.root, state)
        out = []
        for name in sorted(os.listdir(d)):
            if name.endswith(".json") and not name.endswith(".check.json"):
                try:
                    with open(os.path.join(d, name), encoding="utf-8") as f:
                        job = json.load(f)
                except (OSError, ValueError):
                    continue  # a file mid-move; next poll sees it
                if isinstance(job, dict):
                    job["id"] = name[:-5]  # the name wins over a stale id field (a renamed file)
                    out.append(job)
        return out

    def add(self, cmd, threads, heavy=True, mem_gb=1.0, silence_min=SILENCE_MIN, estimate_min=None,
            note="", cwd=None, log=None, lane="main", after=(), if_passed=(), on_fail="park", check=None,
            resumable=False, pin=None):
        """Queue a job. `pin`: a commit ("HEAD" refuses while the pinned
        paths have changes) whose snapshot the job runs in (cwd, and `sts`
        from its pyroot); None runs it unpinned in `cwd`."""
        if not isinstance(cmd, list) or not cmd or not all(isinstance(a, str) for a in cmd):
            raise ValueError("cmd must be a non-empty list of strings")
        if threads < 1:
            raise ValueError("threads must be >= 1")
        self.check_conditions(after, if_passed, on_fail)
        try:
            share = read_shares(self.root).get(lane, DEFAULT_SHARE)
        except (OSError, ValueError, TypeError):
            share = DEFAULT_SHARES.get(lane, DEFAULT_SHARE)
        if share <= 0 and not resumable and not (estimate_min is not None and estimate_min <= FILLER_MAX_MIN):
            raise ValueError(f"lane {lane} is a filler lane (share {share:g}): give --resumable, or "
                             f"--estimate-min {FILLER_MAX_MIN:g} or less")
        env = {}
        if pin:
            if pin == "HEAD":
                if dirty_paths(self.here):
                    raise ValueError("uncommitted or untracked files a pinned job wouldn't see: "
                                     f"{', '.join(dirty_paths(self.here))}; commit them, or add with --unpinned")
                pin = git(self.here, "rev-parse", "HEAD").strip()
            cwd, pin, new = snapshot(pin, self.repo, self.builds, self.build)
            env["PYTHONPATH"] = os.path.join(cwd, "pyroot")
        nums = [int(n[:4]) for s in STATES for n in os.listdir(os.path.join(self.root, s)) if re.match(r"\d{4}-", n)]
        script = next((a for a in cmd if a.endswith(".py")), cmd[0])
        slug = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(os.path.basename(script))[0].lower()).strip("-") or "job"
        jid = f"{max(nums, default=0) + 1:04d}-{slug}"
        job = {"id": jid, "cmd": cmd, "cwd": cwd or REPO, "threads": int(threads), "heavy": bool(heavy),
               "mem_gb": float(mem_gb), "log": log or os.path.join(REPO, "logs", "jobs", jid + ".log"),
               "silence_min": float(silence_min), "estimate_min": estimate_min, "note": note,
               "added": now_iso(), "lane": lane}
        job.update({k: list(v) for k, v in (("after", after), ("if_passed", if_passed)) if v})
        if on_fail != "park":
            job["on_fail"] = on_fail
        if check:
            job["check"] = list(check)
        if resumable:
            job["resumable"] = True
        if pin:
            job.update(pin=pin, env=env)
        peaks = [j for j in self.jobs("done") if "peak_gb" in j and cmd_key(j.get("cmd") or [""]) == cmd_key(cmd)]
        if peaks:
            last = max(peaks, key=lambda j: j.get("ended", ""))["peak_gb"]
            if last > job["mem_gb"]:
                job["mem_gb_low"] = last  # `add` warns
        write_json(self.path("pending", jid), job)
        return jid

    def find(self, jid):
        """(state, job) of a job in any folder, the manual `parked/` one
        included, or (None, None)."""
        for state in STATES + ("parked",):
            try:
                with open(os.path.join(self.root, state, jid + ".json"), encoding="utf-8") as f:
                    return state, json.load(f)
            except (OSError, ValueError):
                pass
        return None, None

    def check_conditions(self, after, if_passed, on_fail):
        unknown = [d for d in list(after) + list(if_passed) if self.find(d)[0] is None]
        if unknown:
            raise ValueError(f"unknown job ids: {', '.join(unknown)}")
        if on_fail not in ("park", "cancel"):
            raise ValueError("on_fail must be park or cancel")

    def set(self, jid, lane=None, after=None, if_passed=None, on_fail=None):
        """Change a pending job's lane or conditions; its id (and pin) stay.
        False if there is no such pending job."""
        state, job = self.find(jid)
        if state != "pending":
            return False
        self.check_conditions(after or (), if_passed or (), on_fail or "park")
        for k, v in (("lane", lane), ("after", after), ("if_passed", if_passed), ("on_fail", on_fail)):
            if v is not None:
                job[k] = list(v) if isinstance(v, (list, tuple)) else v
        job["id"] = jid
        self.update(job, "pending")
        self.event("set", jid, " ".join(f"{k}={job[k]}" for k in ("lane", "after", "if_passed", "on_fail")
                                        if k in job))
        return True

    def estimate(self, jid, minutes, reason=""):
        """Set a pending or running job's `estimate_min` (a running one's,
        from its pace); the old value is kept in `estimates`. False if there
        is no such pending or running job."""
        state, job = self.find(jid)
        if state not in ("pending", "running") or minutes <= 0:
            return False
        old = job.get("estimate_min")
        job["estimate_min"] = round(float(minutes))
        job.setdefault("estimates", []).append({"at": now_iso(), "from": old, "to": job["estimate_min"],
                                                "reason": reason or "by hand"})
        self.update(job, state)
        self.event("estimate", jid, f"{old} -> {job['estimate_min']} min ({reason or 'by hand'})")
        return True

    def unpark(self, jid):
        state, job = self.find(jid)
        if state != "pending" or "parked" not in job:
            return False
        del job["parked"]
        self.update(job, "pending")
        self.event("unparked", jid)
        return True

    def set_verdict(self, jid, verdict, reason=""):
        """Set a done job's verdict by hand."""
        state, job = self.find(jid)
        if state != "done" or verdict not in ("pass", "fail"):
            return False
        job.update(verdict=verdict, verdict_reason=reason or "by hand")
        self.update(job, "done")
        self.event("verdict", jid, f"{verdict} {job['verdict_reason']}")
        return True

    def check_path(self, jid):
        return os.path.join(self.root, "running", jid + ".check.json")

    def first(self, jid):
        """Give a pending job the reservation now and put it first in its lane."""
        for job in self.jobs("pending"):
            if job["id"] == jid:
                job["first_at"] = job["reserved_at"] = time.time()
                self.update(job, "pending")
                self.event("first", jid)
                return True
        return False

    def move(self, job, src, dst):
        write_json(self.path(dst, job["id"]), job)
        try:
            retry(os.remove, self.path(src, job["id"]))
        except FileNotFoundError:
            pass

    def update(self, job, state):
        write_json(self.path(state, job["id"]), job)

    def event(self, kind, jid, detail="", t=None):
        line = f"{now_iso(t)} {kind} {jid} {detail}".rstrip()
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return line

    def cancel(self, jid):
        for job in self.jobs("pending"):
            if job["id"] == jid:
                job["status"] = "cancelled"
                self.move(job, "pending", "done")
                self.event("cancelled", jid)
                return True
        return False

    def exit_path(self, jid):
        return os.path.join(self.root, "running", jid + ".exit")

    def exit_code(self, jid):
        """The exit code the wrapper wrote for a job, or None."""
        try:
            with open(self.exit_path(jid), encoding="utf-8") as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def kill_path(self, jid):
        return os.path.join(self.root, "running", jid + ".kill")

    def kill(self, jid, reason=""):
        """Ask the runner to end a running job's process tree on its next
        poll; the request file holds the reason."""
        if not os.path.exists(self.path("running", jid)):
            return False
        tmp = self.kill_path(jid) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(reason)
        retry(os.replace, tmp, self.kill_path(jid))
        return True


def log_age_min(job, t):
    """Minutes since the job's log last changed (or since it started)."""
    try:
        m = os.path.getmtime(job["log"])
    except OSError:
        m = 0.0
    return (t - max(m, job.get("started_ts", 0.0))) / 60


def spawn(job, wrapper, exit_file):
    """Start a job detached from the runner, with its thread caps, through
    the wrapper script `wrapper`, which writes the exit code to `exit_file`."""
    env = dict(os.environ)
    for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "RAYON_NUM_THREADS", "STS_JOB_THREADS"):
        env[k] = str(job["threads"])
    env["PYTHONUNBUFFERED"] = "1"
    env.update(job.get("env", {}))  # a pinned job: PYTHONPATH = its snapshot's pyroot
    os.makedirs(os.path.dirname(job["log"]), exist_ok=True)
    cmd = list(job["cmd"])
    for exe in (os.path.join(job["cwd"], cmd[0]), os.path.join(job["cwd"], cmd[0] + ".exe")):
        if not os.path.isabs(cmd[0]) and os.path.isfile(exe):
            cmd[0] = exe  # CreateProcess doesn't resolve a relative program against `cwd`
            break
    cmd = [sys.executable, "-I", wrapper, exit_file, "--"] + cmd
    log = open(job["log"], "a", encoding="utf-8")
    flags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    try:
        try:
            p = subprocess.Popen(cmd, cwd=job["cwd"], env=env, stdout=log, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB)
        except OSError:  # the job object around us forbids breakaway
            p = subprocess.Popen(cmd, cwd=job["cwd"], env=env, stdout=log, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, creationflags=flags)
    finally:
        log.close()
    p.job = job_object(p)  # a child started in the instant before this escapes it; jobs start theirs later
    return p


class Runner:
    def __init__(self, queue, heavy_slots=2, thread_budget=14, idle=None, free=free_gb, total=total_gb,
                 commit=None, clock=time.time, alive=pid_alive, start=None, kill=kill_tree, mem=tree_mem_gb, sweep=False):
        self.q, self.heavy_slots, self.thread_budget = queue, heavy_slots, thread_budget
        self.idle = idle or IdleCores()
        self.free, self.total, self.clock, self.alive, self.kill = free, total, clock, alive, kill
        self.commit = commit or free  # free memory a job may take when none of the runner's jobs runs
        self.start = start or (lambda job: spawn(job, self.wrapper(), self.q.exit_path(job["id"])))
        self.mem = mem
        self.procs = {}  # id -> Popen (with .job, its Job Object handle), for jobs this runner started
        self._why = None  # why the last job _admit looked at waits
        self._wrapper = None
        self.shares, self._lanes_bad = dict(DEFAULT_SHARES), False
        self.sweeps, self._unpin_refused = sweep, set()

    def wrapper(self):
        """Path of this runner's frozen wrapper, `runner-<pid>/exec.py`,
        written on first use; the folders of dead runners are removed."""
        if self._wrapper is None:
            for name in os.listdir(self.q.root):
                m = re.fullmatch(r"runner-(\d+)", name)
                if m and int(m[1]) != os.getpid() and not self.alive(int(m[1])):
                    shutil.rmtree(os.path.join(self.q.root, name), ignore_errors=True)
            d = os.path.join(self.q.root, f"runner-{os.getpid()}")
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, "exec.py")
            with open(path + ".tmp", "w", encoding="utf-8") as f:
                f.write(EXEC_PY)
            retry(os.replace, path + ".tmp", path)
            self._wrapper = path
        return self._wrapper

    def load_lanes(self, t):
        """Read `lanes.json` over the default shares. A bad file keeps the
        last good shares and logs `lanes-bad` once (returns that line)."""
        try:
            self.shares, self._lanes_bad = read_shares(self.q.root), False
        except (OSError, ValueError, TypeError) as err:
            if not self._lanes_bad:
                self._lanes_bad = True
                return self.q.event("lanes-bad", "-", f"{err!r}; keeping the last shares", t)
        return None

    def claim(self):
        """Take the pid file and adopt or retire `running/` jobs. Returns
        False if another live runner holds it."""
        pid_path = os.path.join(self.q.root, "runner.pid")
        try:
            with open(pid_path) as f:
                other = int(f.read().strip() or 0)
        except (OSError, ValueError):
            other = 0
        if other and other != os.getpid() and self.alive(other):
            return False
        with open(pid_path, "w") as f:
            f.write(str(os.getpid()))
        self.wrapper()
        for job in self.q.jobs("running"):
            if job["id"] not in self.procs and not self.alive(job.get("pid", 0)):
                code = self.q.exit_code(job["id"])  # ended while no runner watched
                self._finish(job, "lost" if code is None else "ok" if code == 0 else "failed", code)
        for job in self.q.jobs("done"):  # checks cut off by a restart, or never started
            if job.get("check") and job.get("status") == "ok" and "verdict" not in job:
                rec = self._check_record(job["id"])
                if rec is None or (not self.alive(rec.get("pid", 0))
                                   and self.q.exit_code(job["id"] + ".check") is None):
                    self._start_check(job)
        return True

    def _check_record(self, jid):
        try:
            with open(self.q.check_path(jid), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _start_check(self, job):
        """Start a done job's check as its own light process, through the
        wrapper (exit file `running/<id>.check.exit`), and record it in
        `running/<id>.check.json`."""
        cid, t = job["id"] + ".check", self.clock()
        log = os.path.splitext(job["log"])[0] + ".check.log"
        try:
            retry(os.remove, self.q.exit_path(cid))
        except FileNotFoundError:
            pass
        try:
            p = self.start({"id": cid, "cmd": job["check"], "cwd": job["cwd"], "threads": 1, "log": log,
                            "env": job.get("env", {})})
        except OSError as err:
            return self._verdict(job["id"], "fail", f"check start: {err}", t)
        write_json(self.q.check_path(job["id"]), {"pid": p.pid, "started_ts": t, "log": log, "cmd": job["check"]})
        return self.q.event("check", job["id"], f"pid {p.pid}", t)

    def _verdict(self, jid, verdict, reason, t):
        state, job = self.q.find(jid)
        if state == "done":
            job.update(verdict=verdict, verdict_reason=reason)
            self.q.update(job, "done")
        for path in (self.q.check_path(jid), self.q.exit_path(jid + ".check")):
            try:
                retry(os.remove, path)
            except FileNotFoundError:
                pass
        return self.q.event("verdict", jid, f"{verdict} {reason}".strip(), t)

    def reap_checks(self, t):
        """Write the verdict of each check that ended, or ran CHECK_MIN."""
        out = []
        for name in os.listdir(os.path.join(self.q.root, "running")):
            rec = self._check_record(name[:-len(".check.json")]) if name.endswith(".check.json") else None
            if rec is None:
                continue
            jid = name[:-len(".check.json")]
            dead = not self.alive(rec["pid"])  # before the exit file: the wrapper writes it, then exits
            code = self.q.exit_code(jid + ".check")
            if code is not None:
                last = (log_tail(rec["log"]).strip().splitlines() or [""])[-1].strip()[:200]
                out.append(self._verdict(jid, "pass", "", t) if code == 0 else
                           self._verdict(jid, "fail", f"exit {code}: {last}" if last else f"exit {code}", t))
            elif dead:
                out.append(self._verdict(jid, "fail", "check ended without an exit code", t))
            elif t - rec["started_ts"] > CHECK_MIN * 60:
                self.kill({"id": jid + ".check", "pid": rec["pid"]}, None)
                out.append(self._verdict(jid, "fail", "timeout", t))
        return out

    def sweep(self, t):
        """Mark the snapshots jobs use (pin_users; `pyroot/used`),
        and unpin those unused for UNPIN_IDLE_H; a refusal is logged once.
        The only automatic deletion of a snapshot."""
        if not self.sweeps or not os.path.isdir(self.q.builds):
            return []
        used = pin_users(self.q)
        out = []
        for name in sorted(os.listdir(self.q.builds)):
            snap = os.path.join(self.q.builds, name)
            key, mark = os.path.join(snap, "pyroot", "key.txt"), os.path.join(snap, "pyroot", "used")
            if not os.path.isfile(key):
                # the cargo target folder (no .git), or a half-made snapshot (a failed build): that one
                # goes the same way as an idle one once nothing has touched it for UNPIN_IDLE_H
                if (name not in used and os.path.isfile(os.path.join(snap, ".git"))
                        and t - os.path.getmtime(snap) > UNPIN_IDLE_H * 3600 and name not in self._unpin_refused):
                    try:
                        unpin_snapshot(snap, self.q.repo)
                        out.append(self.q.event("unpinned", name, "half made", t))
                    except (ValueError, OSError, subprocess.CalledProcessError) as err:
                        self._unpin_refused.add(name)
                        out.append(self.q.event("unpin-refused", name, str(err)[:300], t))
                continue
            if name in used:
                with open(mark, "a"):
                    pass
                os.utime(mark, (t, t))
                continue
            last = os.path.getmtime(mark if os.path.exists(mark) else key)
            if t - last > UNPIN_IDLE_H * 3600 and name not in self._unpin_refused:
                try:
                    unpin_snapshot(snap, self.q.repo)
                    out.append(self.q.event("unpinned", name, f"unused {(t - last) / 3600:.0f} h", t))
                except (ValueError, OSError, subprocess.CalledProcessError) as err:
                    self._unpin_refused.add(name)
                    out.append(self.q.event("unpin-refused", name, str(err)[:300], t))
        return out

    def _decide(self, t):
        """Decide each pending job's conditions from the queue files: park
        (or cancel, with `on_fail: cancel`) the ones that can't hold,
        cascading through chains in this poll. Returns the event lines and
        the ids that wait."""
        if not any(j.get("after") or j.get("if_passed") for j in self.q.jobs("pending")):
            return [], set()
        index = {}
        for state in STATES + ("parked",):
            if os.path.isdir(os.path.join(self.q.root, state)):
                index.update((j["id"], (state, j)) for j in self.q.jobs(state))
        out, changed = [], True
        while changed:
            changed, waiting = False, set()
            for state, job in list(index.values()):
                if state != "pending" or job.get("parked") or not (job.get("after") or job.get("if_passed")):
                    continue
                why = condition(job, lambda i: index.get(i, (None, None)))
                if why == "wait":
                    waiting.add(job["id"])
                elif why:
                    changed = True
                    if job.get("on_fail") == "cancel":
                        job.update(status="cancelled", reason=why, ended=now_iso(t))
                        self.q.move(job, "pending", "done")
                        index[job["id"]] = ("done", job)
                        out.append(self.q.event("cancelled", job["id"], why, t))
                    else:
                        job["parked"] = why
                        self.q.update(job, "pending")
                        out.append(self.q.event("parked", job["id"], why, t))
        return out, waiting

    def _finish(self, job, status, code, detail=""):
        job.update(status=status, exit_code=code, ended=now_iso(self.clock()))
        self.q.move(job, "running", "done")
        for path in (self.q.kill_path(job["id"]), self.q.exit_path(job["id"])):  # a kill request that came too late
            try:
                retry(os.remove, path)
            except FileNotFoundError:
                pass
        detail = " ".join(s for s in (f"exit {code}" if code is not None else "", detail) if s)
        return self.q.event(status, job["id"], detail, self.clock())

    def _gone(self, job, p, h):
        """Whether the job's whole process tree has ended."""
        if p is None:
            return not self.alive(job.get("pid", 0))  # adopted: only the top pid is known
        return p.poll() is not None and not (h and job_active(h))

    def _end(self, job, p, h):
        code = self.q.exit_code(job["id"])
        if p is not None:
            if code is None:
                code = p.poll()
            del self.procs[job["id"]]
            if h:
                _k32.CloseHandle(h)
        if "kill_reason" in job:
            reason = job.pop("kill_reason")
            job.update(reason=reason, tail="\n".join(log_tail(job["log"]).splitlines()[-15:]))
            return self._finish(job, "killed", code, reason)
        if code is None:
            return self._finish(job, "ended-unknown", None)  # adopted, no exit file: a crash looks like success
        return self._finish(job, "ok" if code == 0 else "failed", code)

    def _refuse(self, job, reason, t):
        job.update(status="failed", exit_code=None, ended=now_iso(t), reason=reason)
        self.q.move(job, "pending", "done")
        return self.q.event("refused", job["id"], reason, t)

    def step(self):
        """One poll: reap, kill on request, watch, maybe start one job.
        Returns the event lines."""
        out, t = [], self.clock()
        line = self.load_lanes(t)
        if line:
            out.append(line)
        running = []
        for job in self.q.jobs("running"):
            p = self.procs.get(job["id"])
            h = getattr(p, "job", None)
            gone = self._gone(job, p, h)
            req = self.q.kill_path(job["id"])
            if not gone and os.path.exists(req):
                with open(req, encoding="utf-8") as f:
                    job["kill_reason"] = f.read().strip() or "kill requested"
                self.q.update(job, "running")
                retry(os.remove, req)
            if gone:
                out.append(self._end(job, p, h))
                if job.get("status") == "ok" and job.get("check"):
                    out.append(self._start_check(job))
                continue
            if "kill_reason" in job:
                self.kill(job, h)  # again each poll until the tree is gone
            gb = round(self.mem(job), 2)
            if gb > job.get("peak_gb", 0.0):
                job["peak_gb"] = gb
                self.q.update(job, "running")
            age = log_age_min(job, t)
            if age >= job.get("silence_min", SILENCE_MIN) and "stalled_at" not in job:
                job["stalled_at"] = now_iso(t)
                self.q.update(job, "running")
                out.append(self.q.event("stalled", job["id"], f"log silent {age:.0f} min", t))
            elif age < job.get("silence_min", SILENCE_MIN) and "stalled_at" in job:
                del job["stalled_at"]
                self.q.update(job, "running")
                out.append(self.q.event("resumed", job["id"], "", t))
            if "suspect_at" not in job:
                hit = [l for l in log_tail(job["log"]).splitlines() if SUSPECT.search(l)]
                if hit:
                    job["suspect_at"] = now_iso(t)
                    self.q.update(job, "running")
                    out.append(self.q.event("suspect", job["id"], hit[-1].strip()[:200], t))
            running.append(job)
        out += self.reap_checks(t) + self.sweep(t)
        idle = self.idle()  # read every poll, so the reading covers one poll
        lines, waiting = self._decide(t)
        out += lines
        pending = []
        for job in self.q.jobs("pending"):
            if job.get("parked") or job["id"] in waiting:
                continue  # neither blocks the jobs behind it
            try:
                check_fields(job)
                pending.append(job)
            except (KeyError, TypeError, ValueError) as err:  # a hand-made job with a missing or bad field
                out.append(self._refuse(job, f"malformed job: {err!r}", t))
        return out + self._choose(pending, running, idle, t) if pending else out

    def _choose(self, pending, running, idle, t):
        """Start at most one pending job; returns the event lines. Tried in
        order: jobs holding a reservation (oldest first), lane heads by
        lowest use / share (ties by lane name), then later jobs of a lane
        whose head waits for memory only (backfill). The top lane head, once
        refused for RESERVE_MIN, gets the reservation if no job holds one.
        While a job holds one, another starts only if it fits alongside it:
        slots, thread budget and reserved memory, as if both ran."""
        cap = self.total() - MEM_HEADROOM_GB
        base = (sum(slot_w(j) for j in running), sum(j["threads"] for j in running),
                sum(held_gb(j) for j in running))
        use = lane_use(running, self.thread_budget, cap)
        lanes = {}
        for j in sorted(pending, key=lambda j: -j.get("first_at", 0)):  # stable: name order otherwise
            lanes.setdefault(lane(j), []).append(j)

        def rank(name):
            share = self.shares.get(name, DEFAULT_SHARE)
            return use.get(name, 0.0) / share if share > 0 else math.inf

        order = sorted(lanes, key=lambda n: (rank(n), n))
        fillers = [n for n in order if rank(n) == math.inf]  # share 0 or below
        order = [n for n in order if rank(n) < math.inf]
        held = sorted((j for j in pending if "reserved_at" in j), key=lambda j: j["reserved_at"])
        out, passed, whys = [], [], {}

        def beside(job):
            heads = held[:held.index(job)] if job in held else held
            if not heads:
                return True
            w = slot_w(job)
            return ((w == 0 or base[0] + w + sum(slot_w(h) for h in heads) <= self.heavy_slots)
                    and base[1] + job["threads"] + sum(h["threads"] for h in heads) <= self.thread_budget
                    and base[2] + job.get("mem_gb", 1.0) + sum(h.get("mem_gb", 1.0) for h in heads) <= cap)

        def go(job, refuse):
            """Try one job; True if it started."""
            line = None
            if beside(job):
                try:
                    line = self._admit(job, *base, idle, t, refuse=refuse)
                    whys[job["id"]] = self._why
                except (KeyError, TypeError, ValueError) as err:  # a field check_fields doesn't cover
                    line, whys[job["id"]] = self._refuse(job, f"malformed job: {err!r}", t), "never"
            else:
                whys[job["id"]] = "reserved"
            if line is None:
                passed.append(f"{job['id']} ({whys[job['id']]})")
                if refuse and "wait_since" not in job:
                    job["wait_since"] = t
                    self.q.update(job, "pending")
                return False
            out.append(line)
            return " start " in line  # a refusal or failed start doesn't end the poll

        for job in held:
            if go(job, True):
                out.append(self.q.event("choice", job["id"], "holds the reservation", t))
                return out
        for i, name in enumerate(order):
            job = lanes[name][0]
            if "reserved_at" in job:
                continue  # tried above
            if go(job, True):
                why = f"; passed {', '.join(passed)}" if passed else ""
                out.append(self.q.event("choice", job["id"], f"lane {name}, use / share {rank(name):.3f}{why}", t))
                return out
            if i == 0 and not held and whys[job["id"]] not in (None, "never") \
                    and t - job["wait_since"] >= RESERVE_MIN * 60:
                job["reserved_at"] = t
                self.q.update(job, "pending")
                held.append(job)
                out.append(self.q.event("reserve", job["id"], f"top of lane {name}, waited "
                                        f"{(t - job['wait_since']) / 60:.0f} min ({whys[job['id']]})", t))
        for job in held:
            if t - job.get("wait_since", t) >= WAITING_MIN * 60 and "waiting_at" not in job:
                job["waiting_at"] = now_iso(t)
                self.q.update(job, "pending")
                out.append(self.q.event("waiting", job["id"], f"holds the reservation, waited "
                                        f"{(t - job['wait_since']) / 60:.0f} min ({whys.get(job['id'])})", t))
        for name in order:
            head = lanes[name][0]
            if whys.get(head["id"]) == "memory":
                for job in lanes[name][1:]:
                    if go(job, False):
                        out.append(self.q.event("backfill", job["id"],
                                                f"ahead of {head['id']}, which waits for memory", t))
                        return out
        for name in fillers:  # only when no other lane's job started this poll
            if go(lanes[name][0], True):
                out.append(self.q.event("choice", lanes[name][0]["id"], f"filler lane {name}", t))
                return out
        return out

    def _admit(self, job, heavy, threads, reserved, idle, t, refuse=True):
        """Start `job` if it fits beside the running jobs' heavy slots,
        threads and reserved memory, refuse it if it never will (when
        `refuse`); returns the event line or None, and leaves why it waits
        in self._why ("never", "slot", "threads" or "memory")."""
        total, mem = self.total(), job.get("mem_gb", 1.0)
        self._why = "never"
        if job["threads"] > self.thread_budget:
            return self._refuse(job, f"threads {job['threads']} above the budget {self.thread_budget}", t) \
                if refuse else None
        if mem + MEM_HEADROOM_GB > total:
            return self._refuse(job, f"mem_gb {mem:g} + {MEM_HEADROOM_GB:g} GB headroom above total memory "
                                     f"{total:.1f} GB", t) if refuse else None
        self._why = "slot"
        if heavy + slot_w(job) > self.heavy_slots:
            return None
        self._why = "threads"
        if threads + job["threads"] > self.thread_budget or idle < job["threads"]:
            return None
        self._why = "memory"
        free = self.free() if reserved else self.commit()  # alone, it may page: commit headroom only
        if reserved + mem > total - MEM_HEADROOM_GB or free < mem + MEM_HEADROOM_GB:
            return None
        self._why = None
        for k in ("mem_wait_since", "wait_since", "reserved_at", "first_at", "waiting_at"):
            job.pop(k, None)
        try:
            retry(os.remove, self.q.exit_path(job["id"]))  # stale: left by an earlier run of this id
        except FileNotFoundError:
            pass
        try:
            p = self.start(job)
        except OSError as err:  # missing cwd: fail the job, keep the queue moving (a missing program
            # starts the wrapper, which logs the error and exits 127)
            job.update(status="failed", exit_code=None, ended=now_iso(t), reason=f"start: {err}")
            self.q.move(job, "pending", "done")
            return self.q.event("failed", job["id"], job["reason"], t)
        self.procs[job["id"]] = p
        job.update(pid=p.pid, started=now_iso(t), started_ts=t)
        self.q.move(job, "pending", "running")
        return self.q.event("start", job["id"], f"pid {p.pid}, {job['threads']} threads, idle {idle:.1f}", t)


def status(queue, t=None, out=print, budget=14, total=None):
    t = time.time() if t is None else t
    running, pending = queue.jobs("running"), queue.jobs("pending")
    try:
        shares, bad = read_shares(queue.root), ""
    except (OSError, ValueError, TypeError) as err:
        shares, bad = dict(DEFAULT_SHARES), f" (lanes.json unreadable, defaults shown: {err!r})"
    use = lane_use(running, budget, (total or total_gb()) - MEM_HEADROOM_GB)
    out(f"lanes (use / share){bad}:")
    for name in sorted(set(shares) | {lane(j) for j in running + pending}):
        n_run, n_pend = sum(lane(j) == name for j in running), sum(lane(j) == name for j in pending)
        if n_run or n_pend:
            out(f"  {name}  use {use.get(name, 0.0):.2f}  share {shares.get(name, DEFAULT_SHARE):g}  "
                f"{n_run} running, {n_pend} pending")
    out("running:")
    for j in running:
        run = (t - j.get("started_ts", t)) / 60
        est = f" / est {j['estimate_min']:g}" if j.get("estimate_min") else ""
        flag = ("  STALLED" if "stalled_at" in j else "") + ("  SUSPECT" if "suspect_at" in j else "") \
            + ("  KILLING" if "kill_reason" in j else "")
        peak = f"  peak {j['peak_gb']:g} GB" if "peak_gb" in j else ""
        out(f"  {j['id']}  lane {lane(j)}  {pin_text(j)}  pid {j.get('pid')}  {j['threads']} thr  "
            f"{run:.0f}{est} min  "
            f"log quiet {log_age_min(j, t):.0f} min{peak}{flag}")
    out("pending:")
    for j in pending:
        kind = "heavy" if j.get("heavy", True) else "light"
        est = f"  est {j['estimate_min']:g} min" if j.get("estimate_min") else ""
        flag = (f"  waited {(t - j['wait_since']) / 60:.0f} min" if isinstance(j.get("wait_since"), (int, float))
                else "") + ("  RESERVED" if "reserved_at" in j else "")             + "".join(f"  {k} {','.join(j[k])}" for k in ("after", "if_passed") if j.get(k))             + (f"  PARKED ({j['parked']})" if j.get("parked") else "")
        out(f"  {j['id']}  lane {lane(j)}  {pin_text(j)}  {j.get('threads')} thr {kind}{est}{flag}  "
            f"{' '.join(j.get('cmd', []))}")
    out("done (last 10):")
    for j in sorted(queue.jobs("done"), key=lambda j: j.get("ended", ""))[-10:]:
        out(f"  {j['id']}  {j.get('status')}  exit {j.get('exit_code')}  ended {j.get('ended')}"
            + (f"  peak {j['peak_gb']:g} GB" if "peak_gb" in j else "")
            + (f"  ({j['reason']})" if j.get("reason") else "")
            + (f"  verdict {j['verdict']}" + (f" ({j['verdict_reason']})" if j.get("verdict_reason") else "")
               if "verdict" in j else "  check running" if j.get("check") and j.get("status") == "ok" else ""))


def pin_text(job):
    return f"pin {job['pin'][:12]}" if job.get("pin") else "unpinned"


def pins(queue, out=print):
    """Each snapshot, the pending or running jobs pinned to it, entries of
    main's data/ not linked into it yet, and its wheel."""
    users = pin_users(queue)
    names = sorted(os.listdir(queue.builds)) if os.path.isdir(queue.builds) else []
    data = set(os.listdir(os.path.join(queue.repo, "data")))
    for name in names:
        snap = os.path.join(queue.builds, name)
        if not os.path.isdir(os.path.join(snap, "pyroot")):
            continue
        made = "" if os.path.isfile(os.path.join(snap, "pyroot", "key.txt")) else "  HALF MADE"
        new = sorted(data - set(os.listdir(os.path.join(snap, "data"))))
        out(f"{name}  {snap}{made}  jobs: {', '.join(users.get(name, [])) or 'none'}"
            + (f"  not linked yet from data/: {', '.join(new)}" if new else "")
            + (f"  wheel {snapshot_wheel(snap)}" if snapshot_wheel(snap) else ""))


def pin_users(queue):
    """{snapshot name: [job ids]} of jobs that use a snapshot: pending,
    running or in the manual `parked/` folder, and done jobs whose check
    still runs (its cwd is the snapshot)."""
    found = [j for state in ("pending", "running", "parked") if os.path.isdir(os.path.join(queue.root, state))
             for j in queue.jobs(state)]
    found += [queue.find(n[:-len(".check.json")])[1] or {} for n in os.listdir(os.path.join(queue.root, "running"))
              if n.endswith(".check.json")]
    users = {}
    for j in found:
        if j.get("pin"):
            users.setdefault(j["pin"][:12], []).append(j["id"])
    return users


def unpin(queue, commit):
    """Remove the snapshot of `commit` if no job uses it (pin_users).
    Returns an error text, or None."""
    name = git(queue.repo, "rev-parse", "--verify", commit + "^{commit}").strip()[:12]
    snap = os.path.join(queue.builds, name)
    if not os.path.isdir(snap):
        return f"no snapshot {snap}"
    users = pin_users(queue).get(name)
    if users:
        return f"used by {', '.join(users)}"
    try:
        unpin_snapshot(snap, queue.repo)
    except (ValueError, OSError, subprocess.CalledProcessError) as err:
        return f"refused: {err}"
    queue.event("unpinned", name, "by hand")
    return None


def impact(queue, what, out=print):
    """List the pending and running jobs a swap of main's `sts` or a merge
    into main's scripts would hit: the unpinned ones. Returns 1 if any."""
    hit = [j for state in ("running", "pending") for j in queue.jobs(state) if not j.get("pin")]
    out(f"unpinned jobs a {'swap of sts' if what == 'sts' else 'change to scripts'} would hit: "
        + (", ".join(j["id"] for j in hit) if hit else "none"))
    return 1 if hit else 0


def wait(queue, poll=30.0, out=print, sleep=time.sleep):
    """Block until the next end or stall event; return its exit code."""
    pos = os.path.getsize(queue.log_path) if os.path.exists(queue.log_path) else 0
    while True:
        if os.path.exists(queue.log_path):
            with open(queue.log_path, encoding="utf-8") as f:
                f.seek(pos)
                lines = f.readlines()
                pos = f.tell()
            for line in lines:
                parts = line.split()
                if len(parts) > 1 and parts[1] in EVENTS:
                    out(line.rstrip(), flush=True)
                    return EVENTS[parts[1]]
        sleep(poll)


def id_list(text):
    return [i for i in text.split(",") if i]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ROOT, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="action", required=True)
    a = sub.add_parser("add")
    a.add_argument("--threads", type=int, required=True)
    a.add_argument("--light", action="store_true", help="doesn't take a heavy slot")
    a.add_argument("--mem-gb", type=float, default=1.0)
    a.add_argument("--silence-min", type=float, default=SILENCE_MIN)
    a.add_argument("--estimate-min", type=float)
    a.add_argument("--note", default="")
    a.add_argument("--lane", default="main")
    a.add_argument("--resumable", action="store_true", help="safe to kill and requeue (filler lanes)")
    a.add_argument("--unpinned", action="store_true", help="run in main's checkout with main's sts (jobs that "
                   "write tracked files or new files directly in data/, runs by hand)")
    a.add_argument("--pin", default="HEAD", help="the commit whose snapshot the job runs in (default HEAD)")
    a.add_argument("--after", type=id_list, default=[], help="ids (comma-separated): wait until each has ended")
    a.add_argument("--if-passed", type=id_list, default=[], help="ids: wait until each has ended and passed")
    a.add_argument("--on-fail", choices=("park", "cancel"), default="park")
    a.add_argument("--check", help="command (one string, forward slashes) run when the job ends ok; "
                                   "exit 0 = pass")
    a.add_argument("cmd", nargs=argparse.REMAINDER)
    f = sub.add_parser("first")
    f.add_argument("id")
    es = sub.add_parser("estimate", help="set a pending or running job's estimate_min")
    es.add_argument("id")
    es.add_argument("minutes", type=float)
    es.add_argument("--reason", default="")
    st = sub.add_parser("set", help="change a pending job; its id stays")
    st.add_argument("id")
    st.add_argument("--lane")
    st.add_argument("--after", type=id_list, help='ids, comma-separated ("" clears)')
    st.add_argument("--if-passed", type=id_list)
    st.add_argument("--on-fail", choices=("park", "cancel"))
    im = sub.add_parser("impact", help="exit 1 if a swap or merge would hit unpinned jobs")
    im.add_argument("what", choices=("sts", "scripts"))
    sub.add_parser("pins")
    up = sub.add_parser("unpin")
    up.add_argument("commit")
    u = sub.add_parser("unpark")
    u.add_argument("id")
    v = sub.add_parser("verdict")
    v.add_argument("id")
    v.add_argument("verdict", choices=("pass", "fail"))
    v.add_argument("--reason", default="")
    sub.add_parser("status")
    c = sub.add_parser("cancel")
    c.add_argument("id")
    k = sub.add_parser("kill")
    k.add_argument("id")
    k.add_argument("--reason", default="")
    r = sub.add_parser("run")
    r.add_argument("--poll", type=float, default=30.0)
    r.add_argument("--heavy-slots", type=int, default=2)
    r.add_argument("--thread-budget", type=int, default=14)
    w = sub.add_parser("wait")
    w.add_argument("--poll", type=float, default=30.0)
    args = ap.parse_args(argv)
    q = Queue(args.root, here=HERE)
    if args.action == "add":
        cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
        try:
            jid = q.add(cmd, args.threads, heavy=not args.light, mem_gb=args.mem_gb, silence_min=args.silence_min,
                        estimate_min=args.estimate_min, note=args.note, lane=args.lane, after=args.after,
                        if_passed=args.if_passed, on_fail=args.on_fail, resumable=args.resumable,
                        pin=None if args.unpinned else args.pin,
                        check=shlex.split(args.check) if args.check else None)
        except ValueError as err:
            print(f"refused: {err}")
            return 1
        low = next((j.get("mem_gb_low") for j in q.jobs("pending") if j["id"] == jid), None)
        if low:
            print(f"warning: --mem-gb {args.mem_gb:g} is below the last peak {low:g} GB of this script and "
                  "first argument (recorded as mem_gb_low)", file=sys.stderr)
        print(jid)
    elif args.action == "status":
        status(q)
    elif args.action == "first":
        if not q.first(args.id):
            print(f"no pending job {args.id}")
            return 1
    elif args.action == "set":
        try:
            ok = q.set(args.id, args.lane, args.after, args.if_passed, args.on_fail)
        except ValueError as err:
            print(f"refused: {err}")
            return 1
        if not ok:
            print(f"no pending job {args.id}")
            return 1
    elif args.action == "impact":
        return impact(q, args.what)
    elif args.action == "pins":
        pins(q)
    elif args.action == "unpin":
        err = unpin(q, args.commit)
        if err:
            print(err)
            return 1
    elif args.action == "estimate":
        if not q.estimate(args.id, args.minutes, args.reason):
            print(f"no pending or running job {args.id}, or minutes not above 0")
            return 1
    elif args.action == "unpark":
        if not q.unpark(args.id):
            print(f"no parked pending job {args.id}")
            return 1
    elif args.action == "verdict":
        if not q.set_verdict(args.id, args.verdict, args.reason):
            print(f"no done job {args.id}")
            return 1
    elif args.action == "cancel":
        if not q.cancel(args.id):
            print(f"no pending job {args.id}")
            return 1
    elif args.action == "kill":
        if not q.kill(args.id, args.reason):
            print(f"no running job {args.id}")
            return 1
    elif args.action == "wait":
        return wait(q, args.poll)
    elif args.action == "run":
        runner = Runner(q, args.heavy_slots, args.thread_budget, commit=commit_gb, sweep=args.root == ROOT)  # tests: no sweep
        if not runner.claim():
            print("another runner holds jobs/runner.pid")
            return 1
        print(f"{now_iso()} runner {os.getpid()} on {q.root}", flush=True)
        while True:
            try:
                for line in runner.step():
                    print(line, flush=True)
            except OSError as err:  # a transient file clash costs one poll, not the runner
                print(f"{now_iso()} poll error: {err!r}", flush=True)
            time.sleep(args.poll)
    return 0


if __name__ == "__main__":
    sys.exit(main())
