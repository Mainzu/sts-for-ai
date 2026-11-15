"""Health check for the steward (docs/specs/operating-model.md, section 3):
measures the environment and writes `jobs/health.json` (gitignored) in the
main checkout. Each metric has a kind, a state and a fix:

- blockers (they gate the navigator; the steward fixes them at once):
  runner, launcher (scripts/roles.py run), disk, push;
- work items (red but not a gate): ready, cpu, tests, facts, debris,
  snapshots, ideas, stagnation.

A state is green, red or unknown (a probe that couldn't run). Exit 1 only
when a blocker is red.

Besides the metrics, the report lists the open lanes (active `lane/<name>`
charters: kind, share, cap, end, step), wake events not yet recorded
(`wakes.lanes` for the lane worker, lane closes included; `wakes.navigator`
for the navigator: stagnation and the wakes in jobs/navigator-wakes.json,
with `wakes.notes` giving each one's reason; none while a blocker is red),
each lane's CPU-hours since it opened, each
metric's red streak (steward runs in a row), `steward_at` (the last
steward run: the lane worker's dead-man check) and `unfiled`: results no
fact cites. Other roles and re-checks pass `--no-state`, which keeps the
streaks, the seen branches and `steward_at` as the last report left them.

    python scripts/health.py [--quiet] [--no-state]
    python scripts/health.py woke lanes|navigator [--ran]   # record the wakes just sent
    python scripts/health.py navwake add <when> --why <reason>   # a navigator wake (kinds: NAV_KINDS)
    python scripts/health.py navwake clear|show   # clear: drop self-set and handled wakes
    python scripts/health.py lock take|beat|release|show <name> --holder <role> --session <id> [--break]

The steward files kb facts with CLAUDE_CODE_SESSION_ID=steward-<id> (kb's
`by`); stagnation ignores those revisions, so its filing never resets it.
"""

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jobs  # noqa: E402
from sweep_watch import pid_alive  # noqa: E402

def find_kb():
    """kb.py: $KB_PY, else the skills folder, else the newest installed kb plugin."""
    if os.environ.get("KB_PY"):
        return os.environ["KB_PY"]
    home = os.path.expanduser("~")
    path = os.path.join(home, ".claude", "skills", "kb", "kb.py")
    if os.path.exists(path):
        return path
    found = glob.glob(os.path.join(home, ".claude", "plugins", "cache", "mainzu", "kb", "*", "skills", "kb", "kb.py"))
    return max(found, key=os.path.getmtime) if found else path


KB = find_kb()
IDEAS_REPO = os.environ.get("STS_IDEAS_REPO", "")  # owner/repo of the idea issues; unset: the ideas metric is unknown
DISK_MIN_GB = 8.0
UNPUSHED_MAX_H = 0.5        # a commit on main not pushed after this long means a refused push
READY_MIN_H = 3.0
CPU_SHARE_MIN = 0.5
ZERO_JOB_MAX_MIN = 60.0
TEST_ID = re.compile(r"^\d{4}[a-z0-9]*-test-full$")
TEST_MAX_H = 48.0
FACTS_MAX = 10
IDLE_BRANCH_H = 72.0
SYSTEM_BRANCHES = ("lane/", "claude/", "worktree-agent-", "worktree-wf_")  # the last two: agent and workflow worktrees
SNAP_MAX = 20
SNAP_MAX_BYTES = 2e9
STAGNANT_H = 72.0
OVERRUN_MIN = 30.0          # a running job this far past its estimate is re-estimated from its pace
PROGRESS = re.compile(r"\b(\d+)\s*/\s*(\d+)\b")  # "119 / 200 starts", "4 / 4 sequences played"
NAV_KINDS = {  # navigator wakes (jobs/navigator-wakes.json): kind -> the argument it takes
    "job": re.compile(r"^\S+$"), "fact": re.compile(r"^\S+$"), "checkpoint": re.compile(r"^\S+$"),
    "ideas": re.compile(r"^\d+$"), "date": re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"),
    "owner": None, "lane": re.compile(r"^\S+$")}
NOTE_KINDS = ("owner", "lane")  # added by the owner or a lane worker; a navigator's clear keeps them until handled
BLOCKERS = ("runner", "launcher", "disk", "push")
FIX = {
    "runner": "restart the runner detached (operating.md, job queue)",
    "launcher": "restart the role launcher detached (operating.md, roles)",
    "disk": "delete rebuildable files only (grants); escalate if none are left",
    "push": "find the refused push or expired auth; never force; escalate",
    "ready": "wake the lane worker; top up filler",
    "cpu": "top up filler; wake the lane worker",
    "tests": "queue test-full (filler.md); a failure is the lane worker's first task",
    "facts": "kb verify, then flag what fails; confirm only what passes",
    "debris": "prune merged branches and worktrees (never data); list the rest in the digest",
    "snapshots": "jobs.py unpin <commit> for snapshots no job uses",
    "ideas": "triage into docs/backlog.md with an agent note on each issue",
    "stagnation": "wake the navigator",
    "overrun": "re-estimate each job from its pace: jobs.py estimate <id> <projected_min> (detail.jobs); "
               "no projection and a silent log: the owning lane reads the log; kill only a stuck job",
    "sessions": "read the failed sessions' logs (logs/roles/); escalate if the cause is the owner's to fix",
    "stale-facts": "the owning role re-checks each (operating.md, Filing facts); escalate if it stays",
}


def main_checkout():
    """The main checkout (where jobs/ and the data live), also from a worktree."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=here,
                                capture_output=True, text=True, timeout=30).stdout.strip()
        return os.path.dirname(common) if common else here
    except (OSError, subprocess.SubprocessError):
        return here


def parse_time(text):
    """A job's ISO time or a kb `at` ("<iso> @ <commit>"); None if absent."""
    if not text:
        return None
    t = datetime.datetime.fromisoformat(str(text).split(" @ ")[0])
    return t if t.tzinfo else t.astimezone()


class Probe:
    """What health reads from the machine. Tests override the methods that
    touch processes, git, gh, kb or the disk."""

    def __init__(self, main=None, now=None, builds=jobs.BUILDS):
        self.main = main or main_checkout()
        self.now = now or datetime.datetime.now().astimezone()
        self.builds = builds

    def path(self, *parts):
        return os.path.join(self.main, *parts)

    def run(self, cmd, timeout=60, env=None):
        """stdout of `cmd` run in the main checkout, or None if it couldn't run."""
        try:
            p = subprocess.run(cmd, cwd=self.main, capture_output=True, text=True, timeout=timeout,
                               env=env, encoding="utf-8", errors="replace")
        except (OSError, subprocess.SubprocessError):
            return None
        return p.stdout if p.returncode == 0 else None

    SLEEPS_PS = ("Get-WinEvent -FilterHashtable @{LogName='System';"
                 "ProviderName='Microsoft-Windows-Power-Troubleshooter';Id=1;StartTime=(Get-Date).AddDays(-30)}"
                 " -EA SilentlyContinue | % { $d=([xml]$_.ToXml()).Event.EventData.Data;"
                 " ($d | ? Name -eq 'SleepTime').'#text' + ' ' + ($d | ? Name -eq 'WakeTime').'#text' }")

    def sleeps(self):
        """[(start, end)] of the machine's sleeps in the last 30 days (Windows' System log)."""
        out = self.run(["powershell", "-NoProfile", "-Command", self.SLEEPS_PS])
        spans = []
        for line in (out or "").splitlines():
            try:
                t = [parse_time(x[:26].rstrip("Z") + "+00:00") for x in line.split()]
            except ValueError:
                continue
            if len(t) == 2 and t[1] > t[0]:
                spans.append((t[0], t[1]))
        return spans

    def jobs(self, state):
        out = []
        for p in sorted(glob.glob(self.path("jobs", state, "*.json"))):
            if p.endswith(".check.json"):
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    job = json.load(f)
            except (OSError, ValueError):
                continue
            if isinstance(job, dict):
                job["id"] = os.path.basename(p)[:-5]
                out.append(job)
        return out

    def shares(self):
        try:
            return jobs.read_shares(self.path("jobs"))
        except (OSError, ValueError, TypeError):
            return dict(jobs.DEFAULT_SHARES)

    def runner_pid(self, name="runner.pid"):
        try:
            with open(self.path("jobs", name), encoding="utf-8") as f:
                return int(f.read().split()[0])
        except (OSError, ValueError, IndexError):
            return None

    def pid_alive(self, pid):
        return pid_alive(pid)

    def log_tail(self, job, size=8192):
        """The last `size` bytes of a job's log as text, or "" if unreadable."""
        path = job.get("log")
        if not path:
            return ""
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - size))
                return f.read().decode("utf-8", "replace")
        except OSError:
            return ""

    def disk_free_gb(self):
        return shutil.disk_usage(self.main[:3] if self.main[1:2] == ":" else self.main).free / 2**30

    def kb(self, *args):
        """kb's output (read-only: no statistics, no cache), or None."""
        env = {**os.environ, "KB_READONLY": "1"}
        try:
            p = subprocess.run([sys.executable, "-I", KB, *args], cwd=self.main, capture_output=True, text=True,
                               timeout=120, env=env, encoding="utf-8", errors="replace")
        except (OSError, subprocess.SubprocessError):
            return None
        return p.stdout or None  # `kb check` exits 1 when facts aren't clean

    def branches(self):
        """[(branch, hours since its tip commit, merged into main)]."""
        refs = self.run(["git", "for-each-ref", "refs/heads", "--format=%(refname:short)\t%(committerdate:unix)"])
        merged = self.run(["git", "branch", "--merged", "main", "--format=%(refname:short)"])
        if refs is None or merged is None:
            return None
        done = set(merged.split())
        now = self.now.timestamp()
        out = []
        for line in refs.splitlines():
            name, _, ts = line.partition("\t")
            if name and ts and name != "main":
                out.append((name, (now - int(ts)) / 3600, name in done))
        return out

    def unpushed_ages_h(self):
        out = self.run(["git", "log", "origin/main..main", "--format=%ct"])
        if out is None:
            return None
        return [(self.now.timestamp() - int(t)) / 3600 for t in out.split()]

    def gh_auth_ok(self):
        try:
            return subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=60).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return None

    def ideas(self):
        if not IDEAS_REPO:
            return None
        out = self.run(["gh", "issue", "list", "--repo", IDEAS_REPO, "--label", "project:sts-for-ai",
                        "--state", "open", "--json", "number", "--limit", "500"], timeout=90)
        try:
            return None if out is None else [i["number"] for i in json.loads(out)]
        except (ValueError, KeyError, TypeError):
            return None

    def backlog_text(self):
        try:
            with open(self.path("docs", "backlog.md"), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def snapshot_sizes(self):
        """Bytes each snapshot holds on its own: junctions and hard links
        into main's data (jobs.link_data) don't count."""
        def size(d):
            total = 0
            try:
                entries = list(os.scandir(d))
            except OSError:
                return 0
            for e in entries:
                try:
                    if e.is_symlink() or e.is_junction():
                        continue
                    if e.is_dir():
                        total += size(e.path)
                    else:
                        st = os.stat(e.path)  # DirEntry.stat() leaves st_nlink 0 on Windows
                        total += st.st_size if st.st_nlink <= 1 else 0
                except OSError:
                    pass
            return total
        if not os.path.isdir(self.builds):
            return []
        return [size(os.path.join(self.builds, n)) for n in sorted(os.listdir(self.builds))
                if os.path.isdir(os.path.join(self.builds, n, "pyroot"))]

    def claims(self, prefix):
        """Fact dicts whose key starts with `prefix` (read straight from docs/claims)."""
        out = []
        root = self.path("docs", "claims")
        for p in glob.glob(os.path.join(root, "**", "*.json"), recursive=True):
            key = os.path.relpath(p, root)[:-5].replace(os.sep, "/")
            if key.startswith(prefix):
                try:
                    with open(p, encoding="utf-8") as f:
                        out.append({**json.load(f), "key": key})
                except (OSError, ValueError):
                    pass
        return out

    def direction_commit(self):
        """(sha, time) of the last commit that touched docs/direction.md, or None."""
        out = self.run(["git", "log", "-1", "--format=%h %cI", "main", "--", "docs/direction.md"])
        if not out or not out.split():
            return None
        sha, t = out.split()[:2]
        return sha, parse_time(t)

    def wakes(self):
        try:
            with open(self.path("jobs", "wakes.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def sessions(self):
        """The role launcher's session records (jobs/roles/*.json), oldest first."""
        out = []
        for p in sorted(glob.glob(self.path("jobs", "roles", "*.json"))):
            try:
                with open(p, encoding="utf-8") as f:
                    out.append(json.load(f))
            except (OSError, ValueError):
                pass
        return out

    def previous(self):
        try:
            with open(self.path("jobs", "health.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}


def metric(name, state, value=None, **detail):
    return {"name": name, "kind": "blocker" if name in BLOCKERS else "work", "state": state, "value": value,
            "detail": detail, "fix": FIX[name] if state == "red" else None}


def green(ok):
    return "unknown" if ok is None else ("green" if ok else "red")


def interval(job, now):
    start = job.get("started_ts")
    start = datetime.datetime.fromtimestamp(start).astimezone() if start else parse_time(job.get("started"))
    if start is None:
        return None
    end = parse_time(job.get("ended")) or now
    return start, end


def cpu(probe):
    """Booked thread share and minutes with no job over the last 24 h."""
    now = probe.now
    lo = now - datetime.timedelta(hours=24)
    spans = []
    booked = 0.0
    for job in probe.jobs("done") + probe.jobs("running"):
        iv = interval(job, now)
        if iv is None:
            continue
        a, b = max(iv[0], lo), min(iv[1], now)
        if b > a:
            spans.append((a, b))
            booked += job.get("threads", 1) * (b - a).total_seconds()
    covered, cur = 0.0, None
    for a, b in sorted(spans):
        if cur is None or a > cur[1]:
            if cur:
                covered += (cur[1] - cur[0]).total_seconds()
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    if cur:
        covered += (cur[1] - cur[0]).total_seconds()
    share = booked / ((os.cpu_count() or 1) * 86400)
    zero = (86400 - covered) / 60
    return metric("cpu", green(share >= CPU_SHARE_MIN and zero <= ZERO_JOB_MAX_MIN), round(share, 3),
                  zero_job_min=round(zero))


def charters(probe):
    """{lane: charter} of open lanes (active `lane/<name>` facts): kind,
    share, cap (CPU-hours), end (date), opened (first revision's time),
    step (the `lane/<name>/step` value), step_rev (its revision)."""
    facts = {f["key"]: f for f in probe.claims("lane/") if f.get("status", "active") == "active"}
    out = {}
    for key, f in facts.items():
        name = key[len("lane/"):]
        if "/" in name:
            continue
        v = str(f.get("value", ""))
        field = lambda pat: (re.search(pat, v) or [None, None])[1]  # noqa: E731
        revs = [parse_time(r.get("at")) for r in [f] + list(f.get("history") or [])]
        step_fact = facts.get(key + "/step", {})
        step = step_fact.get("value")
        out[name] = {"kind": field(r"kind:\s*(\w+)"), "share": field(r"share:\s*([\d.]+)"),
                     "cap": float(field(r"cap:\s*([\d.]+)\s*cpu-h") or 0) or None,
                     "end": field(r"end:\s*(\d{4}-\d{2}-\d{2})"),
                     "opened": min((t for t in revs if t), default=None), "step": step,
                     "step_rev": step_fact.get("rev")}
    return out


def open_lanes(probe, lanes):
    """Project lanes: the chartered ones, or (before any charter) lanes.json's
    lanes with a share above 0, `main` excluded."""
    if lanes:
        return set(lanes)
    return {n for n, s in probe.shares().items() if s > 0 and n != "main"}


def ready(probe, lanes):
    """Hours of queued work in open lanes: running remainders plus pending estimates."""
    now = probe.now
    hours, no_estimate = 0.0, []
    by_lane = {n: 0.0 for n in lanes}
    for state in ("running", "pending"):
        for job in probe.jobs(state):
            lane = job.get("lane", "main")
            if lane not in lanes or job.get("parked"):  # the runner skips parked jobs
                continue
            est = job.get("estimate_min")
            if est is None:
                no_estimate.append(job["id"])
                continue
            if state == "running":
                iv = interval(job, now)
                est -= (now - iv[0]).total_seconds() / 60 if iv else 0
            hours += max(0.0, est) / 60
            by_lane[lane] += max(0.0, est) / 60
    return metric("ready", green(hours >= READY_MIN_H), round(hours, 2), no_estimate=no_estimate,
                  by_lane={n: round(h, 2) for n, h in sorted(by_lane.items())})


def lane_use(probe, lanes):
    """{lane: CPU-hours} its jobs booked since the lane opened, less the machine's sleeps."""
    use = {n: 0.0 for n in lanes}
    sleeps = probe.sleeps() if lanes else []
    for job in probe.jobs("done") + probe.jobs("running"):
        c = lanes.get(job.get("lane"))
        iv = interval(job, probe.now)
        if c is None or iv is None:
            continue
        start = max(iv[0], c["opened"]) if c["opened"] else iv[0]
        if iv[1] > start:
            slept = sum(max(0.0, (min(iv[1], b) - max(start, a)).total_seconds()) for a, b in sleeps)
            use[job["lane"]] += job.get("threads", 1) * ((iv[1] - start).total_seconds() - slept) / 3600
    return {n: round(h, 1) for n, h in use.items()}


HELD_DAYS = 13  # a held ended job waits this long for its lane's decisive wake


def wake_events(probe, lanes, use, report, record):
    """Events a role can act on now, minus those already recorded in
    jobs/wakes.json: `lanes` for the lane worker, `navigator` for the
    navigator (none while a blocker is red). A lane's ended job wakes it only
    when decisive: it has a check, it didn't end ok, or its lane has nothing
    else running or pending (unparked). Other ended jobs are held (up to
    HELD_DAYS), and listed with the lane's next unhandled decisive event,
    at the latest when the lane's queue drains."""
    now = probe.now
    done = probe.jobs("done")
    busy = {j.get("lane") for s in ("running", "pending") for j in probe.jobs(s) if not j.get("parked")}
    seen = record.get("woken") or {}
    lane_ev, held = [], []
    for j in done:  # an ended job wakes its lane only when decisive; the rest fold into the next decisive wake
        t = parse_time(j.get("ended"))
        if j.get("lane") in lanes and t and now - t <= datetime.timedelta(days=HELD_DAYS):
            decisive = j.get("check") or j.get("status") != "ok" or j["lane"] not in busy
            if decisive and now - t <= datetime.timedelta(hours=24):
                lane_ev.append((j["lane"], f"ended:{j['id']}"))
            elif not decisive:  # held up to HELD_DAYS (under woke's 14-day record), so a long queue loses none
                held.append((j["lane"], f"ended:{j['id']}"))
    woke_now = {n for n, k in lane_ev if k not in seen}
    lane_ev = [k for n, k in lane_ev] + [k for n, k in held if n in woke_now]
    for name, c in lanes.items():  # named by the step's revision: a moved step wakes again (code-only lanes)
        if name not in busy and not str(c["step"] or "").startswith("done"):
            rev = c.get("step_rev")
            lane_ev.append(f"idle:{name}:{'rev' + str(rev) if rev else 'none'}")
    tests_m = next(m for m in report if m["name"] == "tests")
    if tests_m["detail"].get("passed") is False:
        lane_ev.append(f"tests:{tests_m['detail']['id']}")
    for name, c in lanes.items():  # the lane worker closes its own lane
        if str(c["step"] or "").startswith("done"):
            lane_ev.append(f"lane-done:{name}")
        if c["cap"] and use.get(name, 0) >= c["cap"]:
            lane_ev.append(f"lane-cap:{name}")
        if c["end"] and now.date().isoformat() > c["end"]:
            lane_ev.append(f"lane-end:{name}")
    nav, notes = [], {}
    stag = next(m for m in report if m["name"] == "stagnation")
    if stag["state"] == "red":
        nav.append(f"stagnation:{stag['detail'].get('since')}")
    for key, why in fired_wakes(probe, record):
        nav.append(key)
        notes[key] = why
    if any(m["kind"] == "blocker" and m["state"] == "red" for m in report):
        nav = []
    nav =[k for k in nav if k not in seen]
    return {"lanes": [k for k in lane_ev if k not in seen], "navigator": nav,
            "notes": {k: v for k, v in notes.items() if k in nav}, "lane_cpu_h": use}


def nav_wakes(probe):
    """The wake list in jobs/navigator-wakes.json: [{when, why, at}]."""
    try:
        with open(probe.path("jobs", "navigator-wakes.json"), encoding="utf-8") as f:
            return list(json.load(f).get("wakes") or [])
    except (OSError, ValueError, AttributeError):
        return []


def wake_key(probe, w, record):
    """The event key of wake `w` once it has fired, else None."""
    kind, _, arg = w["when"].partition(":")
    at = parse_time(w.get("at"))
    if kind in NOTE_KINDS:
        return f"{w['when']}@{w.get('at')}"
    if kind == "job":
        ends = [parse_time(j.get("ended")) for j in probe.jobs("done")
                if j["id"] == arg or j["id"].startswith(arg + "-")]
        return w["when"] if any(t and at and t > at for t in ends) else None  # ended after it was set
    if kind in ("fact", "checkpoint"):
        key = arg if kind == "fact" else f"lane/{arg}/checkpoint"
        f = next((f for f in probe.claims(key) if f["key"] == key), None)
        t = parse_time(f.get("at")) if f else None
        return f"{w['when']}@{f.get('rev', len(f.get('history') or []) + 1)}" if t and at and t > at else None
    if kind == "ideas":
        triaged = len(set(re.findall(r"ideas#(\d+)", probe.backlog_text())))
        return f"ideas:{triaged}" if triaged - record.get("ideas_at_navigator", triaged) >= int(arg) else None
    if kind == "date":
        due = datetime.datetime.strptime(arg, "%Y-%m-%d %H:%M").replace(tzinfo=probe.now.tzinfo)
        return w["when"] if probe.now >= due else None
    return None


def fired_wakes(probe, record):
    """[(key, why)] of the navigator wakes that have fired."""
    out = []
    for w in nav_wakes(probe):
        key = wake_key(probe, w, record)
        if key:
            out.append((key, w.get("why") or ""))
    return out


def navwake(probe, action, when=None, why=None, out=print):
    """add: append a wake (kinds NAV_KINDS; exit 2 on a bad one); clear: drop
    the self-set wakes, and owner or lane wakes already handled (in woken);
    show: print the list."""
    wakes = nav_wakes(probe)
    if action == "add":
        kind, sep, arg = when.partition(":")
        pat = NAV_KINDS.get(kind, False)
        if pat is False or (pat is None and sep) or (pat is not None and not pat.match(arg)):
            out(f"bad wake {when!r}: kinds are job:<id>, fact:<key>, checkpoint:<lane>, ideas:<n>, "
                "date:<YYYY-MM-DD HH:MM>, owner, lane:<name>")
            return 2
        wakes.append({"when": when, "why": why or "", "at": probe.now.isoformat(timespec="seconds")})
    elif action == "clear":
        record = probe.wakes()
        seen = record.get("woken") or {}
        wakes = [w for w in wakes if w["when"].partition(":")[0] in NOTE_KINDS
                 and wake_key(probe, w, record) not in seen]
    else:
        for w in wakes:
            out(f"{w['at']}  {w['when']}  {w['why']}")
        return 0
    jobs.write_json(probe.path("jobs", "navigator-wakes.json"), {"wakes": wakes})
    return 0


def unfiled(probe):
    """Ids of jobs that ended ok in the last 7 days (over 4 h ago) in a lane
    other than main and filler, whose record no kb fact cites."""
    cited = set()
    for f in probe.claims(""):
        for r in [f] + list(f.get("history") or []):
            for s in r.get("sources") or []:
                m = re.search(r"jobs/done/([^/]+)\.json$", str(s.get("path", "")))
                if m:
                    cited.add(m[1])
    out = []
    for j in probe.jobs("done"):
        t = parse_time(j.get("ended"))
        if j.get("status") == "ok" and j.get("lane", "main") not in ("main", "filler") and t \
                and datetime.timedelta(hours=4) <= probe.now - t <= datetime.timedelta(days=7) and j["id"] not in cited:
            out.append(j["id"])
    return sorted(out)


def is_suite(job):
    """A test-full job that runs the whole suite (not a `--per-test` probe)."""
    return bool(TEST_ID.match(job["id"])) and "--per-test" not in job.get("cmd", [])


def tests(probe):
    runs = [j for j in probe.jobs("done") if is_suite(j)]
    queued = [j["id"] for s in ("pending", "running") for j in probe.jobs(s) if is_suite(j)]
    if not runs:
        return metric("tests", "red", None, id=None, queued=queued)
    last = max(runs, key=lambda j: parse_time(j.get("ended")) or probe.now - datetime.timedelta(days=999))
    ended = parse_time(last.get("ended"))
    age = (probe.now - ended).total_seconds() / 3600 if ended else None
    ok = jobs.passed(last) is True and age is not None and age <= TEST_MAX_H
    return metric("tests", green(ok), None if age is None else round(age, 1), id=last["id"],
                  status=last.get("status"), passed=jobs.passed(last), queued=queued)


def facts(out):
    m = re.search(r"(\d+) suspect, (\d+) unchecked", out or "")
    if not m:
        return metric("facts", "unknown")
    n = int(m[1]) + int(m[2])
    return metric("facts", green(n <= FACTS_MAX), n)


def debris(probe, seen):
    refs = probe.branches()
    if refs is None:
        return metric("debris", "unknown"), seen
    idle = [(n, merged) for n, age, merged in refs if n.startswith(SYSTEM_BRANCHES) and age > IDLE_BRANCH_H]
    others = sorted(n for n, _, _ in refs if not n.startswith(SYSTEM_BRANCHES))
    new = [n for n in others if n not in seen]
    m = metric("debris", green(not idle), len(idle), merged=sorted(n for n, mg in idle if mg),
               unmerged=sorted(n for n, mg in idle if not mg), other_new=new)
    return m, sorted(set(seen) | set(others))


def snapshots(probe):
    sizes = probe.snapshot_sizes()
    total = sum(sizes)
    return metric("snapshots", green(len(sizes) <= SNAP_MAX and total <= SNAP_MAX_BYTES), len(sizes),
                  gb=round(total / 1e9, 2))


def ideas(probe):
    open_ = probe.ideas()
    if open_ is None:
        return metric("ideas", "unknown")
    triaged = {int(n) for n in re.findall(r"ideas#(\d+)", probe.backlog_text())}
    untriaged = sorted(n for n in open_ if n not in triaged)
    return metric("ideas", green(not untriaged), len(untriaged), untriaged=untriaged)


def progress(text):
    """The last "done / total" count in a log tail, with 0 < done <= total, or None."""
    for line in reversed(text.splitlines()):
        found = [(int(a), int(b)) for a, b in PROGRESS.findall(line) if 0 < int(a) <= int(b)]
        if found:
            return found[-1]
    return None


def overrun(probe):
    """Running jobs more than OVERRUN_MIN past their estimate, each with its
    progress and the total run time its pace projects (elapsed x total / done)."""
    now = probe.now
    late = []
    for job in probe.jobs("running"):
        est, iv = job.get("estimate_min"), interval(job, now)
        if est is None or iv is None:
            continue
        elapsed = (now - iv[0]).total_seconds() / 60
        if elapsed <= est + OVERRUN_MIN:
            continue
        p = progress(probe.log_tail(job))
        projected = round(elapsed * p[1] / p[0]) if p and p[0] < p[1] else None
        late.append({"id": job["id"], "lane": job.get("lane", "main"), "elapsed_min": round(elapsed),
                     "estimate_min": est, "progress": f"{p[0]} / {p[1]}" if p else None,
                     "projected_min": projected})
    return metric("overrun", green(not late), len(late), jobs=late)


def stagnation(probe):
    """Hours since a headline measurement changed or a lane checkpoint passed,
    counting only revisions not filed by the steward: its note or its `by`
    (kb's session id; the steward sets CLAUDE_CODE_SESSION_ID=steward-<id>,
    which, unlike the note, survives into kb history) starts "steward"."""
    times = []
    for fact in probe.claims("measurement/headline") + [f for f in probe.claims("lane/")
                                                        if f["key"].endswith("/checkpoint")]:
        checkpoint = fact["key"].startswith("lane/")
        for rev in [fact] + list(fact.get("history") or []):
            if str(rev.get("note") or "").startswith("steward") or str(rev.get("by") or "").startswith("steward"):
                continue
            if checkpoint and not str(rev.get("value", "")).startswith("passed"):
                continue
            t = parse_time(rev.get("at"))
            if t:
                times.append(t)
    if not times:
        return metric("stagnation", "red", None, since=None)
    age = (probe.now - max(times)).total_seconds() / 3600
    return metric("stagnation", green(age <= STAGNANT_H), round(age, 1), since=max(times).isoformat())


def measure(probe, state=True):
    """`state` False (a role other than the steward): keep the steward's
    streaks, seen branches and `steward_at` from the last report."""
    prev = probe.previous()
    pid = probe.runner_pid()
    lpid = probe.runner_pid("roles.pid")
    unpushed = probe.unpushed_ages_h()
    auth = probe.gh_auth_ok()
    if auth is False or any(a > UNPUSHED_MAX_H for a in unpushed or []):
        push_ok = False
    else:
        push_ok = None if unpushed is None or auth is None else True  # git or gh couldn't tell
    free = probe.disk_free_gb()
    debris_m, seen = debris(probe, prev.get("debris_other_seen") or [])
    if not state:
        seen = prev.get("debris_other_seen") or []
    lanes = charters(probe)
    check = probe.kb("check")
    stale_m, suspect_since = stale_facts(check, probe.now, prev.get("suspect_since") or {})
    metrics = [
        metric("runner", green(pid is not None and probe.pid_alive(pid)), pid),
        metric("launcher", green(lpid is not None and probe.pid_alive(lpid)), lpid),
        metric("disk", green(free >= DISK_MIN_GB), round(free, 1)),
        metric("push", green(push_ok), len(unpushed or []), auth=auth),
        ready(probe, open_lanes(probe, lanes)), cpu(probe), tests(probe), facts(check), stale_m, debris_m,
        snapshots(probe), ideas(probe), stagnation(probe), overrun(probe), sessions(probe),
    ]
    streaks = {m["name"]: m.get("streak", 0) for m in prev.get("metrics") or []}
    for m in metrics:
        m["streak"] = streaks.get(m["name"], 0) if not state else             streaks.get(m["name"], 0) + 1 if m["state"] == "red" else 0
    red = [m for m in metrics if m["state"] == "red"]
    at = probe.now.isoformat(timespec="seconds")
    return {"at": at, "steward_at": at if state else prev.get("steward_at"), "metrics": metrics,
            "blockers": [m for m in red if m["kind"] == "blocker"],
            "work": [m for m in red if m["kind"] == "work"],
            "lanes": {n: {**c, "opened": c["opened"] and c["opened"].isoformat()} for n, c in lanes.items()},
            "wakes": wake_events(probe, lanes, lane_use(probe, lanes), metrics, probe.wakes()),
            "unfiled": unfiled(probe),
            "debris_other_seen": seen, "suspect_since": suspect_since}


def exit_code(report):
    return 1 if report["blockers"] else 0


LOCK_STALE_MIN = 45.0


def sessions(probe):
    """Red when a role's last two ended sessions both failed (outcome not ok)."""
    failing = []
    for role in sorted({r.get("role") for r in probe.sessions()} - {None}):
        ended = [r for r in probe.sessions() if r.get("role") == role and r.get("ended") and "outcome" in r
                 and r["outcome"] != "chat"]  # an owner chat isn't a headless run
        last = sorted(ended, key=lambda r: r.get("started", ""))[-2:]
        if len(last) == 2 and all(r["outcome"] != "ok" for r in last):
            failing.append(role)
    return metric("sessions", green(not failing), len(failing), failing=failing)


STALE_FACT_H = 24.0


def stale_facts(out, now, since):
    """Facts suspect for over a day (unchecked ones have no owner to re-check them): `since` holds when each was
    first seen so (from the last report); returns the metric and the new map."""
    keys = re.findall(r"^(\S+) \[suspect\]", out or "", re.M)
    new = {k: since.get(k) or now.isoformat(timespec="seconds") for k in keys}
    old = sorted(k for k, t in new.items() if (now - parse_time(t)).total_seconds() > STALE_FACT_H * 3600)
    if out is None:
        return metric("stale-facts", "unknown"), since
    return metric("stale-facts", green(not old), len(old), keys=old), new


def woke(probe, role, ran=False, keys=None):
    """Record the current health.json wake events for `role` (lanes or
    navigator) in jobs/wakes.json, so one event wakes once. `ran`: the
    navigator ran now (its triggers count from here)."""
    record = probe.wakes()
    report = probe.previous()
    seen = record.setdefault("woken", {})
    for key in keys if keys is not None else (report.get("wakes") or {}).get(role) or []:
        seen[key] = probe.now.isoformat(timespec="seconds")
    if ran:
        record["navigator_ran"] = probe.now.isoformat(timespec="seconds")
        record["ideas_at_navigator"] = len(set(re.findall(r"ideas#(\d+)", probe.backlog_text())))
    cut = probe.now - datetime.timedelta(days=14)
    record["woken"] = {k: t for k, t in seen.items() if parse_time(t) > cut}
    jobs.write_json(probe.path("jobs", "wakes.json"), record)
    return 0


def lock(probe, action, name, holder=None, session=None, force=False, out=print):
    """take / beat / release / show `jobs/locks/<name>.json`. `take` exits 1
    when the lock is held (by anyone; `--break` takes a stale one: the caller
    has checked its holder isn't running)."""
    path = probe.path("jobs", "locks", name + ".json")
    now = probe.now.isoformat(timespec="seconds")
    try:
        with open(path, encoding="utf-8") as f:
            held = json.load(f)
    except (OSError, ValueError):
        held = None
    if held:
        age = (probe.now - parse_time(held.get("heartbeat"))).total_seconds() / 60
        desc = f"{name}: {held.get('holder')} {held.get('session')} since {held.get('time')}, heartbeat {age:.0f} min ago"
    if action == "show":
        out(desc if held else f"{name}: free")
        return 0
    if action == "take":
        if held and not (force and age > LOCK_STALE_MIN):
            out("held: " + desc + (" (not stale)" if force else ""))
            return 1
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if held:  # move the stale lock aside; if it changed meanwhile, someone else broke it first
            aside = f"{path}.{session}"
            try:
                os.replace(path, aside)
            except FileNotFoundError:
                out(f"held: {name} was taken just now")
                return 1
            try:
                with open(aside, encoding="utf-8") as f:
                    moved = json.load(f)
            except (OSError, ValueError):  # another session moved it on at the same moment
                out(f"held: {name} was taken just now")
                return 1
            if moved.get("heartbeat") != held.get("heartbeat") or moved.get("session") != held.get("session"):
                try:
                    os.rename(aside, path)  # not the stale lock any more: put it back
                except FileExistsError:
                    os.remove(aside)
                out(f"held: {name} was taken just now")
                return 1
            os.remove(aside)
        try:  # exclusive create: of two sessions taking at once, one wins
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            out(f"held: {name} was taken just now")
            return 1
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"holder": holder, "session": session, "time": now, "heartbeat": now}, f, indent=1)
        out(f"{name}: taken" + (" (broke " + desc + ")" if held else ""))
        return 0
    if not held or held.get("session") != session:
        out(f"{name}: not held by {session}" + (f" ({desc})" if held else ""))
        return 1
    if action == "beat":
        jobs.write_json(path, {**held, "heartbeat": now})
    else:
        os.remove(path)
    out(f"{name}: {'heartbeat' if action == 'beat' else 'released'}")
    return 0


def main(argv=None, probe=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["lock"]:
        ap = argparse.ArgumentParser(prog="health.py lock")
        ap.add_argument("action", choices=("take", "beat", "release", "show"))
        ap.add_argument("name", help="main-merge or lane-<name>")
        ap.add_argument("--holder", help="role: steward, navigator or lanes")
        ap.add_argument("--session", help="session id")
        ap.add_argument("--break", dest="force", action="store_true",
                        help=f"take a lock whose heartbeat is over {LOCK_STALE_MIN:g} min old")
        a = ap.parse_args(argv[1:])
        if a.action != "show" and not a.session:
            ap.error("--session is required")
        return lock(probe or Probe(), a.action, a.name, a.holder, a.session, a.force)
    if argv[:1] == ["navwake"]:
        ap = argparse.ArgumentParser(prog="health.py navwake")
        ap.add_argument("action", choices=("add", "clear", "show"))
        ap.add_argument("when", nargs="?", help="job:<id>, fact:<key>, checkpoint:<lane>, ideas:<n>, "
                                                "date:<YYYY-MM-DD HH:MM>, owner or lane:<name>")
        ap.add_argument("--why", help="why the result matters (shown to the navigator)")
        a = ap.parse_args(argv[1:])
        if a.action == "add" and not a.when:
            ap.error("add needs <when>")
        return navwake(probe or Probe(), a.action, a.when, a.why)
    if argv[:1] == ["woke"]:
        ap = argparse.ArgumentParser(prog="health.py woke")
        ap.add_argument("role", choices=("lanes", "navigator"))
        ap.add_argument("--ran", action="store_true", help="the navigator ran (its own close)")
        ap.add_argument("--keys", type=lambda t: [k for k in t.split(",") if k],
                        help="record these events only (the ones this session handled)")
        a = ap.parse_args(argv[1:])
        return woke(probe or Probe(), a.role, a.ran, a.keys)
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--no-state", action="store_true",
                    help="a role other than the steward: don't count streaks or mark branches seen")
    a = ap.parse_args(argv)
    probe = probe or Probe()
    report = measure(probe, state=not a.no_state)
    jobs.write_json(probe.path("jobs", "health.json"), report)
    if not a.quiet:
        for m in report["metrics"]:
            detail = ", ".join(f"{k} {v}" for k, v in m["detail"].items() if v not in (None, [], "", {}))
            print(f"{m['state']:7} {m['kind']:7} {m['name']:11} {m['value'] if m['value'] is not None else '-'}"
                  + (f"  ({detail})" if detail else "") + (f"  fix: {m['fix']}" if m["fix"] else "")
                  + (f"  red {m['streak']} runs" if m["streak"] > 1 else ""))
        w = report["wakes"]
        print(f"wake lanes: {', '.join(w['lanes']) or '-'}")
        print(f"wake navigator: {', '.join(w['navigator']) or '-'}")
        print(f"lane CPU-hours: {w['lane_cpu_h'] or '-'}; unfiled results: {', '.join(report['unfiled']) or '-'}")
    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
