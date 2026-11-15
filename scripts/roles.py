"""Role launcher (docs/specs/role-launcher.md): starts the lane worker and
the navigator as headless Claude Code sessions (`claude -p`) when there is
work for them, within budgets, one-at-a-time rules and time limits. The
steward stays an app scheduled task and restarts this loop if it dies.

    python scripts/roles.py run [--poll 300]   # the loop (one at a time: jobs/roles.pid)
    python scripts/roles.py tick [--dry-run]   # one pass
    python scripts/roles.py status             # running sessions, last starts, the last tick
    python scripts/roles.py probe              # check the CLI does what the launcher relies on
    python scripts/roles.py wake navigator "<note>"   # the owner's wake: the navigator starts with the note
    python scripts/roles.py chat navigator     # the owner talks to the navigator's last session

One red blocker needs only a process started, so the tick starts it
itself (RESTARTS): a dead job runner, checked live first, at most once per
FIX_RETRY_MIN; anything else red waits for the steward.

A role's previous session is resumed (`--resume`) instead of a fresh start
when it ended cleanly under REUSE_MAX_MIN ago with under REUSE_MAX_TOKENS of
context, on the same model, effort and prompt file (a lane worker: the same
lane). The navigator also starts on its own wakes (jobs/navigator-wakes.json,
through health.json) and on a NAV_BACKSTOP_H backstop.

Sessions: records in jobs/roles/<role>-<stamp>.json, output in
logs/roles/<role>-<stamp>.jsonl, one line per start, end or kill in
jobs/roles.log (lines start "<date time> launcher").
"""

import argparse
import ctypes
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import health  # noqa: E402
import jobs  # noqa: E402

MAIN = health.main_checkout()
CLI_FALLBACK = os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def cli_path():
    """The `claude` CLI: on PATH, else where the standalone installer puts it; None if missing."""
    found = shutil.which("claude")
    return found or (CLI_FALLBACK if os.path.isfile(CLI_FALLBACK) else None)


def clean_env():
    """The environment for a CLI session: without the variables of the
    Claude session that may have started this process."""
    return {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "CLAUDECODE"))}


def ask(cli, prompt, model="haiku", timeout=300):
    """Run one headless session; its final JSON (result, is_error, modelUsage, permission_denials)."""
    p = subprocess.run([cli, "-p", prompt, "--model", model, "--permission-mode", "auto", "--output-format", "json"],
                       cwd=MAIN, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, env=clean_env())
    out = p.stdout
    return json.loads(out[out.index("{"):]) if "{" in out else {"is_error": True, "result": out + p.stderr}


def probe(out=print):
    """The spec's outside assumptions 1-7, with cheap Haiku calls. Returns 0 if all hold."""
    cli = cli_path()
    if not cli:
        out("FAIL cli: `claude` not on PATH and not at " + CLI_FALLBACK)
        return 1
    ok = True

    def check(name, cond, detail):
        nonlocal ok
        ok &= bool(cond)
        out(f"{'ok  ' if cond else 'FAIL'} {name}: {detail}")

    r = ask(cli, "Reply with the single word: ok")
    check("1 login", not r.get("is_error") and "ok" in str(r.get("result", "")).lower(), r.get("result", "")[:60])
    r = ask(cli, "Run these Bash commands and report each output verbatim: (1) git rev-parse --short HEAD "
                 "(2) type kb | head -1 (3) echo SID=$CLAUDE_CODE_SESSION_ID. Then say which of these tools you "
                 "have, as a line 'TOOLS: <names>': Workflow, Agent, Bash.")
    text = str(r.get("result", ""))
    check("2 auto mode runs Bash", not r.get("is_error") and not r.get("permission_denials"), f"denials {r.get('permission_denials')}")
    check("4 kb and session id", "kb is a function" in text and "SID=" in text and "SID=\n" not in text, text[:80].replace("\n", " "))
    tools = text[text.find("TOOLS:"):].split("\n")[0]
    check("5 Workflow and Agent", "Workflow" in tools and "Agent" in tools, tools)
    for model in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1"):
        r = ask(cli, "Reply with the single word: ok", model=model)
        check(f"3 model {model}", model in (r.get("modelUsage") or {}), list(r.get("modelUsage") or {}))
    p = spawn(cli, "Run this Bash command and wait for it: sleep 300", "haiku", os.devnull)
    time.sleep(45)
    kill(p.pid)
    time.sleep(5)
    check("6 kill ends the session", p.poll() is not None, f"exit {p.poll()}")
    out("7 cancel a pending job: " + probe_cancel(cli))
    return 0 if ok else 1


def probe_cancel(cli):
    """Queue a dummy job that waits behind a running one, have a session cancel it, report what happened."""
    py = os.path.join(MAIN, ".venv", "Scripts", "python.exe")
    jobs_py = os.path.join(MAIN, "scripts", "jobs.py")
    running = sorted(os.path.splitext(n)[0] for n in os.listdir(os.path.join(MAIN, "jobs", "running"))
                     if n.endswith(".json") and not n.endswith(".check.json"))
    if not running:
        return "skipped (no running job to wait behind)"
    add = subprocess.run([py, jobs_py, "add", "--lane", "main", "--light", "--threads", "1", "--estimate-min", "1",
                          "--unpinned", "--after", running[0], "--note", "roles.py probe: a dummy to cancel",
                          "--", py, "-c", "pass"], cwd=MAIN, capture_output=True, text=True)
    jid = add.stdout.strip().splitlines()[-1] if add.returncode == 0 else None
    if not jid:
        return "skipped (add failed: " + (add.stderr or add.stdout).strip()[-120:] + ")"
    r = ask(cli, f"Run this Bash command and report its output: .venv/Scripts/python.exe scripts/jobs.py cancel {jid}")
    gone = not os.path.exists(os.path.join(MAIN, "jobs", "pending", jid + ".json"))
    if not gone:  # leave nothing behind
        subprocess.run([py, jobs_py, "cancel", jid], cwd=MAIN, capture_output=True)
    return f"{'allowed' if gone else 'REFUSED'} (job {jid}; denials {r.get('permission_denials')})"


def spawn(cli, prompt, model, log, cwd=None, effort=None, resume=None):
    """Start a headless session detached, its stream-json output in `log`;
    `resume`: continue that session id. `cli` is the program, or a list (a
    test's fake CLI)."""
    cmd = (list(cli) if isinstance(cli, (list, tuple)) else [cli]) + [
        "-p", prompt, "--model", model, "--permission-mode", "auto", "--output-format", "stream-json", "--verbose"]
    if effort:
        cmd += ["--effort", effort]
    if resume:
        cmd += ["--resume", resume]
    return detached(cmd, log, cwd or MAIN, env=clean_env())


def detached(cmd, log, cwd, env=None):
    """Start `cmd` with no window, its output appended to `log`, outliving
    the session or job object that started the launcher."""
    os.makedirs(os.path.dirname(log), exist_ok=True)
    f = open(log, "a", encoding="utf-8")
    flags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    try:
        try:
            return subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
                                    env=env, creationflags=flags | jobs.CREATE_BREAKAWAY_FROM_JOB)
        except OSError:  # breakaway not allowed here
            return subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
                                    env=env, creationflags=flags)
    finally:
        f.close()


def proc_created(pid):
    """When process `pid` was created (Windows), or None if it can't be read."""
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    times = [ctypes.c_ulonglong() for _ in range(4)]
    ok = ctypes.windll.kernel32.GetProcessTimes(h, *[ctypes.byref(t) for t in times])
    ctypes.windll.kernel32.CloseHandle(h)
    if not ok:
        return None
    unix = times[0].value / 1e7 - 11644473600  # FILETIME: 100 ns since 1601
    return datetime.datetime.fromtimestamp(unix).astimezone()


def kill(pid):
    """End a session's whole process tree."""
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)


ROLES = {
    "lanes": {"prompt": "docs/roles/sts-lanes.md", "model": "claude-opus-5-5", "effort": "medium", "max_h": 4.0},
    "navigator": {"prompt": "docs/roles/sts-navigator.md", "model": "claude-opus-5-5", "effort": "high", "max_h": 2.0},
}
HEALTH_MAX_MIN = 15.0      # refresh health.json when older
LANE_BACKSTOP_H = 4.0      # a lane session at least this often while a lane is open
LANES_MAX = 2
NAV_BACKSTOP_H = 72.0      # a safety net: the navigator wakes on its own conditions
REUSE_MAX_MIN = 55.0       # resume only while the 1-hour prompt cache lasts
REUSE_MAX_TOKENS = 400000  # and while its context is this small
RESUME_PROMPT = ("Resumed for a new run of your role ({prompt}, unchanged since this session started). "
                 "Everything in your context from before this message may be stale, so treat it as possibly "
                 "stale: re-read jobs/health.json, `kb render` and `git log` since your last run before acting "
                 "on anything. Then do this run from section 1 of your prompt.")
RETRY_H = 4.0              # an event a session was started on and didn't handle starts another after this
RESTARTS = ("runner",)     # red blockers the tick fixes by starting the process
FIX_RETRY_MIN = 30.0       # a restarted process found dead again within this waits for the steward


class Launcher:
    """One tick decides which role sessions to stop and start. Clock,
    processes, health refresh and the CLI are injected for tests."""

    def __init__(self, main=MAIN, now=None, alive=None, spawn=None, kill=None, refresh=None, cli=cli_path,
                 created=proc_created, dead=None, restart=None):
        self.main = main
        self.now = now or (lambda: datetime.datetime.now().astimezone())
        self.alive = alive or health.pid_alive
        self.spawn = spawn or self._spawn
        self.kill = kill or globals()['kill']
        self.refresh = refresh or self._refresh
        self.cli = cli
        self.created = created
        self.dead = dead or self._dead
        self.restart = restart or self._restart
        self.restarted = {}  # blocker name -> when this launcher last started it

    def ours(self, rec):
        """The record's process still runs: its pid lives and wasn't created
        after the session started (a pid reused after a reboot isn't ours)."""
        if not self.alive(rec["pid"]):
            return False
        made = self.created(rec["pid"])
        return made is None or made <= health.parse_time(rec["started"]) + datetime.timedelta(seconds=60)

    def path(self, *parts):
        return os.path.join(self.main, *parts)

    def read(self, *parts, default=None):
        try:
            with open(self.path(*parts), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return default

    def log(self, text):
        os.makedirs(self.path("jobs"), exist_ok=True)
        with open(self.path("jobs", "roles.log"), "a", encoding="utf-8") as f:
            f.write(f"{self.now():%Y-%m-%d %H:%M} launcher {text}\n")

    def sessions(self):
        """Session records under jobs/roles/, oldest first."""
        d = self.path("jobs", "roles")
        out = []
        for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            rec = self.read("jobs", "roles", n)
            if n.endswith(".json") and isinstance(rec, dict):
                out.append({**rec, "file": n})
        return out

    def save(self, rec):
        jobs.write_json(self.path("jobs", "roles", rec["file"]), {k: v for k, v in rec.items() if k != "file"})

    def model(self, role):
        return ROLES[role]["model"]

    def _refresh(self):
        subprocess.run([sys.executable, os.path.join(self.main, "scripts", "health.py"), "--no-state", "--quiet"],
                       cwd=self.main, capture_output=True, timeout=600)

    def _spawn(self, role, model, prompt, log, resume=None):
        return spawn(self.cli(), prompt, model, log, cwd=self.main, effort=ROLES[role].get("effort"),
                     resume=resume).pid

    def _dead(self, name):
        """A live check: True when the process is not running, None if unknown."""
        pid = health.Probe(self.main).runner_pid()
        return pid is None or not health.pid_alive(pid)

    def _restart(self, name):
        py = self.path(".venv", "Scripts", "python.exe")
        py = py if os.path.isfile(py) else sys.executable
        cmd, log = [py, "-u", "scripts/jobs.py", "run"], self.path("logs", "jobs", "runner.out")
        return detached(cmd, log, self.main).pid

    def fix(self, names):
        """Start each dead RESTARTS process among the red blockers `names`;
        the names it started."""
        out = []
        for name in names:
            if name not in RESTARTS or self.dead(name) is not True:
                continue
            last = self.restarted.get(name)
            if last and (self.now() - last).total_seconds() < FIX_RETRY_MIN * 60:
                if not self.restarted.get(name + ":noted"):
                    self.log(f"{name} dead again within {FIX_RETRY_MIN:g} min of a restart: left for the steward")
                    self.restarted[name + ":noted"] = True
                continue
            pid = self.restart(name)
            self.restarted[name] = self.now()
            self.restarted.pop(name + ":noted", None)
            self.log(f"restarted {name} (pid {pid}): health saw it dead")
            out.append(name)
        return out

    def lane_of(self, key):
        """The lane an event is about: ended:<job> (the job's lane), idle:<lane>:..., tests:<job> (test-full)."""
        kind, _, rest = key.partition(":")
        if kind == "idle":
            return rest.split(":")[0]
        if kind in ("lane-done", "lane-cap", "lane-end"):
            return rest
        if kind == "tests":
            return "test-full"
        if kind == "ended":
            return (self.read("jobs", "done", rest + ".json", default={}) or {}).get("lane")
        return None

    def claimed(self, lane):
        return os.path.exists(self.path("jobs", "locks", f"lane-{lane}.json"))

    def tick(self, dry=False):
        """One pass. Returns what it did (or, with `dry`, would do)."""
        now, did = self.now(), []
        running = []
        for rec in self.sessions():
            if rec.get("ended"):
                continue
            age_h = (now - health.parse_time(rec["started"])).total_seconds() / 3600
            if not self.ours(rec):
                outcome = "chat" if rec.get("chat") else self.outcome(rec)
                did.append(f"{rec['role']} ended ({rec['file']}, {outcome})")
                if not dry:
                    self.save({**rec, "ended": now.isoformat(timespec="seconds"), "outcome": outcome})
                    self.log(f"{rec['role']} ended after {age_h:.1f} h: {outcome} ({rec['file']})")
            elif age_h > ROLES[rec["role"]]["max_h"] and not rec.get("chat"):  # the owner's chat runs on
                did.append(f"kill {rec['role']} ({rec['file']}, {age_h:.1f} h)")
                if not dry:
                    self.kill(rec["pid"])
                    self.save({**rec, "ended": now.isoformat(timespec="seconds"), "killed": True, "outcome": "killed"})
                    self.log(f"{rec['role']} killed after {age_h:.1f} h ({rec['file']})")
            else:
                running.append(rec)
        h = self.read("jobs", "health.json")
        if not h or (now - health.parse_time(h.get("at"))).total_seconds() > HEALTH_MAX_MIN * 60 \
                or self.wakes_newer(h):
            if not dry:
                self.refresh()
            h = self.read("jobs", "health.json") or h
        if not h:
            return did + ["no health.json"]
        if h.get("blockers") and not dry:
            fixed = self.fix([b.get("name", "?") for b in h["blockers"]])
            if fixed:
                did += [f"restarted {n}" for n in fixed]
                self.refresh()
                h = self.read("jobs", "health.json") or h
        if h.get("blockers"):
            return did + ["blocker red: " + ", ".join(b.get("name", "?") for b in h["blockers"])]
        if not self.cli():
            if not dry and "CLI missing" not in (self.roles_log() or [""])[-1]:  # once until something else happens
                self.log("CLI missing: `claude` not on PATH and not at " + CLI_FALLBACK)
            return did + ["CLI missing"]
        wakes = self.read("jobs", "wakes.json", default={}) or {}
        recent = {k for r in self.sessions() for k in r.get("why") or []
                  if not r.get("ended") or (now - health.parse_time(r["started"])).total_seconds() < RETRY_H * 3600}
        woken = set(wakes.get("woken") or {}) | recent  # handled, or tried recently
        lanes_running = [r for r in running if r["role"] == "lanes"]
        nav_running = [r for r in running if r["role"] == "navigator"]
        # navigator first
        triggers = [k for k in (h.get("wakes") or {}).get("navigator") or [] if k not in woken]
        nav_starts = [health.parse_time(r["started"]) for r in self.sessions() if r["role"] == "navigator"]
        ran = max([t for t in [health.parse_time(wakes.get("navigator_ran"))] + nav_starts if t], default=None)
        if not nav_running:
            why = triggers or ([] if ran and (now - ran).total_seconds() < NAV_BACKSTOP_H * 3600 else ["backstop"])
            if why:
                did += self.start("navigator", why, dry, notes=(h.get("wakes") or {}).get("notes") or {})
        events = [k for k in (h.get("wakes") or {}).get("lanes") or [] if k not in woken]
        lane_starts = [r for r in self.sessions() if r["role"] == "lanes"]
        last = max((health.parse_time(r["started"]) for r in lane_starts), default=None)
        if len(lanes_running) >= LANES_MAX:
            return did
        if lanes_running:
            why = [k for k in events if self.lane_of(k) and not self.claimed(self.lane_of(k))]
        else:
            open_lanes = [n for n, c in (h.get("lanes") or {}).items() if not str(c.get("step") or "").startswith("done")]
            why = events or (["backstop"] if open_lanes and (last is None or (now - last).total_seconds()
                                                              >= LANE_BACKSTOP_H * 3600) else [])
        if why:
            did += self.start("lanes", why, dry)
        return did

    def outcome(self, rec):
        """How an ended session finished, from its log's last result line:
        ok, error: <subtype>, or no result (it crashed or was cut off)."""
        try:
            with open(rec["log"], encoding="utf-8", errors="replace") as f:
                lines = [l for l in f.read().splitlines() if '"type":"result"' in l.replace(" ", "")]
            res = json.loads(lines[-1][lines[-1].index("{"):])
        except (OSError, ValueError, IndexError, KeyError):
            return "no result"
        return f"error: {res.get('subtype')}" if res.get("is_error") or res.get("subtype") != "success" else "ok"

    def wakes_newer(self, h):
        """jobs/navigator-wakes.json changed after health.json was written (an owner or lane wake)."""
        try:
            t = os.path.getmtime(self.path("jobs", "navigator-wakes.json"))
        except OSError:
            return False
        at = health.parse_time(h.get("at"))
        return at is not None and t > at.timestamp()

    def stamp(self, role, suffix=""):
        stamp = f"{self.now():%Y%m%d-%H%M%S}"
        n = 2
        while os.path.exists(self.path("jobs", "roles", f"{role}-{stamp}{suffix}.json")):  # two in one second
            stamp = f"{self.now():%Y%m%d-%H%M%S}-{n}"
            n += 1
        return stamp + suffix

    def reusable(self, role, why, prompt_sha):
        """The session id to resume for this start, or None (see the module docstring)."""
        recs = [r for r in self.sessions() if r["role"] == role]
        prev = recs[-1] if recs else None
        if not prev or not prev.get("ended") or prev.get("outcome") != "ok" or prev.get("chat"):
            return None
        if prev.get("model") != self.model(role) or prev.get("effort") != ROLES[role].get("effort") \
                or prev.get("prompt_sha") != prompt_sha:
            return None
        if role == "lanes":
            was, now_ = {self.lane_of(k) for k in prev.get("why") or []}, {self.lane_of(k) for k in why}
            if None in was | now_ or was != now_ or len(was) != 1:
                return None
        sid, ctx = log_session(prev.get("log"))
        try:
            age_min = (self.now().timestamp() - os.path.getmtime(prev["log"])) / 60
        except (OSError, TypeError):
            return None
        return sid if sid and ctx is not None and ctx < REUSE_MAX_TOKENS and age_min < REUSE_MAX_MIN else None

    def start(self, role, why, dry, notes=None):
        model = self.model(role)
        if dry:
            return [f"start {role} on {model}: {', '.join(why)}"]
        stamp = self.stamp(role)
        with open(self.path(ROLES[role]["prompt"]), encoding="utf-8") as f:
            text = f.read()
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        resume = self.reusable(role, why, sha)
        prompt = RESUME_PROMPT.format(prompt=ROLES[role]["prompt"]) if resume else text
        prompt += "\n\n## This run started on\n\n" + "\n".join(
            f"- {k}" + (f": {notes[k]}" if (notes or {}).get(k) else "") for k in why) + "\n"
        os.makedirs(self.path("logs", "roles"), exist_ok=True)
        os.makedirs(self.path("jobs", "roles"), exist_ok=True)
        log = self.path("logs", "roles", f"{role}-{stamp}.jsonl")
        pid = self.spawn(role, model, prompt, log, resume=resume)
        self.save({"file": f"{role}-{stamp}.json", "role": role, "pid": pid, "model": model,
                   "effort": ROLES[role].get("effort"), "prompt_sha": sha, "resumed": resume,
                   "started": self.now().isoformat(timespec="seconds"), "log": log, "why": why})
        how = f", resumed {resume[:8]}" if resume else ""
        self.log(f"{role} started: {', '.join(why)} (pid {pid}, {model}{how})")
        return [f"start {role} on {model}{how}: {', '.join(why)}"]

    def roles_log(self):
        try:
            with open(self.path("jobs", "roles.log"), encoding="utf-8") as f:
                return f.read().splitlines()
        except OSError:
            return []


def log_session(path):
    """(session id, the main session's last request's context tokens) from a session's stream-json log;
    None where unknown."""
    sid, ctx = None, None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if o.get("type") == "system" and o.get("session_id"):
                    sid = o["session_id"]
                elif o.get("type") == "assistant" and not o.get("parent_tool_use_id"):  # a subagent's is its own context
                    u = (o.get("message") or {}).get("usage") or {}
                    ctx = sum(u.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens",
                                                    "cache_creation_input_tokens"))
    except (OSError, TypeError):
        pass
    return sid, ctx


def chat(launcher, out=print, run=subprocess.run):
    """Open the navigator's last session interactively for the owner; the
    launcher starts no headless navigator while it runs."""
    recs = [r for r in launcher.sessions() if r["role"] == "navigator"]
    running = [r for r in recs if not r.get("ended") and launcher.ours(r)]
    if running:
        r = running[-1]
        until = health.parse_time(r["started"]) + datetime.timedelta(hours=ROLES["navigator"]["max_h"])
        out(f"a navigator runs (started {r['started']}{', a chat' if r.get('chat') else ''}); it ends by "
            f"{until:%H:%M} at the latest. Try then, or leave a note: roles.py wake navigator \"<note>\"")
        return 1
    sid = next((s for s in (r.get("session") or log_session(r.get("log"))[0] for r in reversed(recs)) if s), None)
    cli = launcher.cli()
    if not sid or not cli:
        out("no navigator session to resume" if not sid else "CLI missing")
        return 1
    model = launcher.model("navigator")
    os.makedirs(launcher.path("jobs", "roles"), exist_ok=True)
    rec = {"file": f"navigator-{launcher.stamp('navigator', '-chat')}.json", "role": "navigator",
           "pid": os.getpid(), "chat": True, "session": sid, "model": model,
           "effort": ROLES["navigator"].get("effort"), "started": launcher.now().isoformat(timespec="seconds"),
           "log": None, "why": ["chat"]}
    launcher.save(rec)
    launcher.log(f"navigator chat opened (resumes {sid[:8]})")
    try:
        cmd = (list(cli) if isinstance(cli, (list, tuple)) else [cli]) + [
            "--resume", sid, "--model", model, "--effort", ROLES["navigator"]["effort"]]
        run(cmd, cwd=launcher.main, env=clean_env())
    finally:
        launcher.save({**rec, "ended": launcher.now().isoformat(timespec="seconds"), "outcome": "chat"})
        launcher.log("navigator chat closed")
    return 0


def status(launcher, out=print):
    now = launcher.now()
    recs = launcher.sessions()
    for rec in recs:
        if not rec.get("ended") and launcher.ours(rec):
            age = (now - health.parse_time(rec["started"])).total_seconds() / 3600
            out(f"running {rec['role']:9} {age:4.1f} h  pid {rec['pid']}  {rec['model']}  {rec['log']}")
    for role in ROLES:
        last = [r for r in recs if r["role"] == role]
        out(f"last {role}: " + (f"{last[-1]['started']} ({', '.join(last[-1].get('why') or [])})" if last else "never"))
    st = launcher.read("jobs", "roles-status.json", default={}) or {}
    out(f"last tick {st.get('at', 'never')}: {'; '.join(st.get('did') or []) or 'nothing to do'}")
    return 0


def run(launcher, poll, out=print, sleep=time.sleep, ticks=None):
    """The loop: one tick per `poll` seconds; refuses when another launcher lives."""
    pidfile = launcher.path("jobs", "roles.pid")
    try:
        with open(pidfile, encoding="utf-8") as f:
            other = int(f.read().split()[0])
        if other != os.getpid() and launcher.alive(other):
            out(f"another launcher runs (pid {other})")
            return 1
    except (OSError, ValueError, IndexError):
        pass
    with open(pidfile, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    n = 0
    while ticks is None or n < ticks:
        try:
            did = launcher.tick()
        except Exception as e:  # a bad tick must not end the loop
            did = [f"tick failed: {type(e).__name__}: {e}"]
        jobs.write_json(launcher.path("jobs", "roles-status.json"),
                        {"at": launcher.now().isoformat(timespec="seconds"), "pid": os.getpid(), "did": did})
        for line in did:
            out(f"{launcher.now():%Y-%m-%d %H:%M:%S} {line}")
        n += 1
        if ticks is None or n < ticks:
            sleep(poll)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--main", default=MAIN, help=argparse.SUPPRESS)  # tests: another checkout
    ap.add_argument("--cli", help=argparse.SUPPRESS)                 # tests: a fake CLI, as a JSON list
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--poll", type=float, default=300.0)
    r.add_argument("--ticks", type=int, help=argparse.SUPPRESS)
    t = sub.add_parser("tick")
    t.add_argument("--dry-run", action="store_true")
    sub.add_parser("status")
    sub.add_parser("probe")
    w = sub.add_parser("wake", help="the owner's wake: the navigator starts on the next tick with the note")
    w.add_argument("role", choices=("navigator",))
    w.add_argument("note")
    c = sub.add_parser("chat", help="talk to the navigator's last session (blocks headless runs meanwhile)")
    c.add_argument("role", choices=("navigator",))
    a = ap.parse_args(argv)
    if a.cmd == "probe":
        return probe()
    if a.cmd == "wake":
        rc = health.navwake(health.Probe(main=a.main), "add", "owner", a.note)
        if rc == 0:
            l = Launcher(main=a.main)
            running = any(r["role"] == "navigator" and not r.get("ended") and l.ours(r) for r in l.sessions())
            print("noted: " + ("a navigator runs now; the note goes to the next run" if running
                               else f"the launcher starts the navigator on its next tick (within "
                                    f"{300 // 60} min)"))
        return rc
    cli = (lambda: json.loads(a.cli)) if a.cli else cli_path
    launcher = Launcher(main=a.main, cli=cli)
    if a.cmd == "run":
        return run(launcher, a.poll, ticks=a.ticks)
    if a.cmd == "chat":
        return chat(launcher)
    if a.cmd == "tick":
        for line in launcher.tick(dry=a.dry_run) or ["nothing to do"]:
            print(line)
        return 0
    return status(launcher)


if __name__ == "__main__":
    sys.exit(main())
