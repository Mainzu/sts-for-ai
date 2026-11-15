"""Tests for the role launcher's tick (scripts/roles.py, docs/specs/role-launcher.md
verification 1). Run with `python scripts/tests/test_roles.py` (plain
asserts; every `test_*` function runs) or with pytest."""

import atexit
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import roles  # noqa: E402

TZ = datetime.timezone.utc
NOW = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=TZ)


def ago(h, now=NOW):
    return (now - datetime.timedelta(hours=h)).isoformat(timespec="seconds")


class Env:
    """A temp main checkout with health.json, wakes.json, prompts and fake processes."""

    def __init__(self, now=NOW, events=(), triggers=(), lanes=None, blockers=(), ran=None, steward_h=0.5,
                 notes=None):
        self.dir = tempfile.mkdtemp(prefix="roles-test-")
        for d in ("jobs/done", "jobs/locks", "docs/roles"):  # jobs/roles and logs/roles: the launcher makes them
            os.makedirs(os.path.join(self.dir, d))
        for r in ("sts-lanes", "sts-navigator"):
            with open(os.path.join(self.dir, "docs", "roles", r + ".md"), "w") as f:
                f.write(f"prompt of {r}")
        self.now = now
        self.live, self.spawned, self.killed, self.refreshed, self.resumed = set(), [], [], 0, []
        self.dead, self.restarts = set(), []  # processes a live check finds dead; ones the launcher started
        self.cli = "C:/fake/claude.exe"
        self.next_pid = 100
        self.lanes = lanes if lanes is not None else {"deep": {"step": "step 1"}, "wide": {"step": "not started"}}
        self.steward_h = steward_h
        self.health(events, triggers, blockers, notes=notes)
        self.wakes = {"woken": {}}
        if ran:
            self.wakes["navigator_ran"] = ran
        self.save_wakes()
        self.l = roles.Launcher(main=self.dir, now=lambda: self.now, alive=lambda pid: pid in self.live,
                                spawn=self._spawn, kill=self._kill, refresh=self._refresh, cli=lambda: self.cli,
                                created=lambda pid: None, dead=lambda n: n in self.dead, restart=self._restart)

    def health(self, events=(), triggers=(), blockers=(), at=None, notes=None):
        h = {"at": at or self.now.isoformat(timespec="seconds"), "steward_at": ago(self.steward_h, self.now),
             "metrics": [],
             "blockers": [{"name": b} for b in blockers],
             "lanes": {n: {"step": c["step"]} for n, c in self.lanes.items()},
             "wakes": {"lanes": list(events), "navigator": list(triggers), "notes": dict(notes or {}),
                       "lane_cpu_h": {}}}
        with open(os.path.join(self.dir, "jobs", "health.json"), "w") as f:
            json.dump(h, f)

    def save_wakes(self):
        with open(os.path.join(self.dir, "jobs", "wakes.json"), "w") as f:
            json.dump(self.wakes, f)

    def job(self, jid, lane):
        with open(os.path.join(self.dir, "jobs", "done", jid + ".json"), "w") as f:
            json.dump({"id": jid, "lane": lane}, f)

    def claim(self, lane):
        with open(os.path.join(self.dir, "jobs", "locks", f"lane-{lane}.json"), "w") as f:
            json.dump({"holder": "lanes", "session": "x", "time": ago(0), "heartbeat": ago(0)}, f)

    def _spawn(self, role, model, prompt, log, resume=None):
        self.next_pid += 1
        self.live.add(self.next_pid)
        self.spawned.append((role, model, prompt, log))
        self.resumed.append(resume)
        return self.next_pid

    def _kill(self, pid):
        self.killed.append(pid)
        self.live.discard(pid)

    def _restart(self, name):
        self.restarts.append(name)
        self.dead.discard(name)
        return 900 + len(self.restarts)

    def _refresh(self):
        self.refreshed += 1
        with open(os.path.join(self.dir, "jobs", "health.json")) as f:
            h = json.load(f)
        h["at"] = self.now.isoformat(timespec="seconds")
        h["blockers"] = [b for b in h["blockers"] if b["name"] not in self.restarts or b["name"] in self.dead]
        with open(os.path.join(self.dir, "jobs", "health.json"), "w") as f:
            json.dump(h, f)

    def wakes_woken(self):
        with open(os.path.join(self.dir, "jobs", "wakes.json")) as f:
            return json.load(f).get("woken") or {}

    def write_log(self, n, text):
        """Write the n-th started session's output log (a fake session's last line)."""
        with open(self.spawned[n][3], "w") as f:
            f.write(text)

    def roles_log(self):
        try:
            with open(os.path.join(self.dir, "jobs", "roles.log")) as f:
                return f.read()
        except OSError:
            return ""

    def started(self, role):
        return [s for s in self.spawned if s[0] == role]

    def done(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def run(env, ticks=1):
    """Tick, leaving the temp folder for the asserts (removed at exit)."""
    atexit.register(env.done)
    for _ in range(ticks):
        env.l.tick()
    return env


def test_new_lane_event_starts_one_session_once():
    e = Env(events=["ended:0101-gauntlet"], ran=ago(1))
    e.job("0101-gauntlet", "deep")
    run(e, ticks=3)
    assert len(e.started("lanes")) == 1, e.spawned
    assert e.wakes_woken() == {}, "the launcher doesn't mark events handled; the session does"
    assert "launcher lanes started: ended:0101-gauntlet" in e.roles_log(), e.roles_log()


def test_handled_event_starts_nothing_after_the_session_ends():
    e = Env(events=["ended:0101-gauntlet"], ran=ago(1))
    e.job("0101-gauntlet", "deep")
    try:
        e.l.tick()
        e.live.clear()  # the session ended
        e.now += datetime.timedelta(minutes=10)
        e.l.tick()
        assert len(e.started("lanes")) == 1, e.spawned
        assert "launcher lanes ended" in e.roles_log()
    finally:
        e.done()


def test_backstop_starts_a_lane_session_after_4_hours():
    e = Env(ran=ago(1))
    run(e)
    assert len(e.started("lanes")) == 1 and "backstop" in e.roles_log(), e.roles_log()


def test_no_backstop_when_every_lane_is_done_or_recently_worked():
    e = Env(ran=ago(1), lanes={"deep": {"step": "done: passed"}})
    run(e)
    assert e.started("lanes") == []
    e = Env(ran=ago(1))
    try:
        e.l.tick()
        e.live.clear()
        e.now += datetime.timedelta(hours=3)
        e.l.tick()
        assert len(e.started("lanes")) == 1, e.spawned
        e.now += datetime.timedelta(hours=1, minutes=5)
        e.l.tick()
        assert len(e.started("lanes")) == 2, e.spawned
    finally:
        e.done()


def test_second_lane_session_only_for_an_unclaimed_lane():
    e = Env(events=["ended:0101-gauntlet"], ran=ago(1))
    e.job("0101-gauntlet", "deep")
    try:
        e.l.tick()
        e.claim("deep")
        e.health(events=["idle:deep:0101-gauntlet"])  # deep is claimed: no second session
        e.l.tick()
        assert len(e.started("lanes")) == 1, e.spawned
        e.health(events=["idle:wide:none"])
        e.l.tick()
        assert len(e.started("lanes")) == 2, e.spawned
        e.health(events=["idle:other:none"])
        e.l.tick()
        assert len(e.started("lanes")) == 2, "at most 2 lane sessions"
    finally:
        e.done()


def test_navigator_trigger_and_72_hour_backstop():
    e = Env(triggers=["job:0092"], ran=ago(2))
    run(e)
    assert len(e.started("navigator")) == 1, e.spawned
    for now, h, starts in ((NOW, 25, 0), (NOW, 73, 1)):
        e = Env(now=now, ran=ago(h, now), lanes={})
        run(e)
        assert len(e.started("navigator")) == starts, (now, h, e.spawned)
        assert not starts or "backstop" in e.roles_log()


def test_wake_notes_reach_the_navigator_prompt():
    e = Env(triggers=["owner@2026-11-10T11:58:00+00:00", "stagnation:x"], ran=ago(2),
            notes={"owner@2026-11-10T11:58:00+00:00": "look at the boss curve"})
    run(e)
    prompt = e.started("navigator")[0][2]
    assert prompt.startswith("prompt of sts-navigator") and "look at the boss curve" in prompt, prompt
    assert "stagnation:x" in prompt, prompt


def test_a_new_wake_file_refreshes_health():
    e = Env(ran=ago(1))
    path = os.path.join(e.dir, "jobs", "navigator-wakes.json")
    with open(path, "w") as f:
        json.dump({"wakes": []}, f)
    os.utime(path, (NOW.timestamp() + 60, NOW.timestamp() + 60))   # written after health.json's `at`
    e.now = NOW + datetime.timedelta(minutes=2)
    run(e)
    assert e.refreshed == 1, "a wake added since the last health refresh is seen at once"


def ended_session(e, role="lanes", why=("idle:wide:none",), minutes_ago=10, ctx=120000, outcome_line=None):
    """Start a session on `why`, give it a log with an init line, a usage line and a result, and end it."""
    e.health(events=list(why) if role == "lanes" else [], triggers=list(why) if role == "navigator" else [])
    e.l.tick()
    log = e.spawned[-1][3]
    with open(log, "w") as f:
        f.write('{"type":"system","subtype":"init","session_id":"sess-1"}\n')
        f.write(json.dumps({"type": "assistant", "message": {"usage": {
            "input_tokens": 10, "cache_read_input_tokens": ctx - 10, "cache_creation_input_tokens": 0}}}) + "\n")
        f.write(outcome_line or '{"type":"result","subtype":"success","is_error":false}\n')
    e.live.clear()
    e.now += datetime.timedelta(minutes=minutes_ago)
    t = (e.now - datetime.timedelta(minutes=minutes_ago)).timestamp()
    os.utime(log, (t, t))
    e.l.tick()   # records the end
    return log


def test_session_is_resumed_only_when_every_reuse_condition_holds():
    def second(e, why=("ended:0101-gauntlet",)):
        e.health(events=list(why))
        e.now += datetime.timedelta(minutes=1)
        e.l.tick()
        return e.resumed[-1], e.spawned[-1][2]

    e = Env(ran=ago(1))
    atexit.register(e.done)
    e.job("0101-gauntlet", "wide")
    ended_session(e)
    sid, prompt = second(e)
    assert sid == "sess-1" and "possibly stale" in prompt and "prompt of sts-lanes" not in prompt, (sid, prompt)
    rec = [r for r in e.l.sessions() if r["role"] == "lanes"][-1]
    assert rec["resumed"] == "sess-1", rec

    cases = {
        "cache gone": dict(minutes_ago=56),
        "context too big": dict(ctx=400001),
        "ended badly": dict(outcome_line='{"type":"result","subtype":"error_max_turns","is_error":true}\n'),
    }
    for name, kw in cases.items():
        e = Env(ran=ago(1))
        atexit.register(e.done)
        e.job("0101-gauntlet", "wide")
        ended_session(e, **kw)
        assert second(e)[0] is None, name
    e = Env(ran=ago(1))       # the role's prompt changed since the session started
    atexit.register(e.done)
    e.job("0101-gauntlet", "wide")
    ended_session(e)
    with open(os.path.join(e.dir, "docs", "roles", "sts-lanes.md"), "w") as f:
        f.write("a new prompt")
    assert second(e)[0] is None, "prompt changed"
    e = Env(ran=ago(1))       # another lane
    atexit.register(e.done)
    e.job("0102-gauntlet", "deep")
    ended_session(e)
    assert second(e, why=("ended:0102-gauntlet",))[0] is None, "another lane"
    e = Env(ran=ago(1))       # the effort changed
    atexit.register(e.done)
    e.job("0101-gauntlet", "wide")
    ended_session(e)
    rec = [r for r in e.l.sessions() if r["role"] == "lanes"][-1]
    e.l.save({**rec, "effort": "low"})
    assert second(e)[0] is None, "effort changed"
    e = Env(ran=ago(1))       # the model changed
    atexit.register(e.done)
    e.job("0101-gauntlet", "wide")
    ended_session(e)
    rec = [r for r in e.l.sessions() if r["role"] == "lanes"][-1]
    e.l.save({**rec, "model": "claude-sonnet-5-5"})
    assert second(e)[0] is None, "model changed"


def test_log_session_reads_the_main_context_not_a_subagents():
    e = Env()
    atexit.register(e.done)
    log = os.path.join(e.dir, "sub.jsonl")
    usage = lambda n: {"usage": {"input_tokens": n, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}
    with open(log, "w") as f:
        f.write('{"type":"system","subtype":"init","session_id":"sess-1"}\n')
        f.write(json.dumps({"type": "assistant", "message": usage(450000)}) + "\n")
        f.write(json.dumps({"type": "assistant", "parent_tool_use_id": "t1", "message": usage(20000)}) + "\n")
    assert roles.log_session(log) == ("sess-1", 450000)


def test_lane_close_events_map_to_their_lane():
    e = Env()
    atexit.register(e.done)
    for k in ("lane-done:wide", "lane-cap:wide", "lane-end:wide"):
        assert e.l.lane_of(k) == "wide", k


def test_chat_blocks_headless_navigator_and_is_refused_while_one_runs():
    e = Env(triggers=["job:0092"], ran=ago(30))
    atexit.register(e.done)
    os.makedirs(os.path.join(e.dir, "jobs", "roles"), exist_ok=True)
    e.live.add(999)
    e.l.save({"file": "navigator-20261110-115000-chat.json", "role": "navigator", "pid": 999, "chat": True,
              "model": "m", "started": ago(3), "why": ["chat"], "log": None})
    e.l.tick()
    assert e.started("navigator") == [] and e.killed == [], "no headless navigator beside a chat, chat never killed"
    e.live.discard(999)
    e.now += datetime.timedelta(minutes=5)
    e.l.tick()
    chat_rec = [r for r in e.l.sessions() if r.get("chat")][0]
    assert chat_rec["outcome"] == "chat", chat_rec
    assert len(e.started("navigator")) == 1   # the chat ended: the trigger starts one
    opened = []
    out = []
    assert roles.chat(e.l, out=out.append, run=lambda *a, **k: opened.append(a)) == 1, out
    assert opened == [] and "runs" in out[0], out


def test_chat_resumes_the_last_navigator_session():
    e = Env(ran=ago(1), lanes={})
    atexit.register(e.done)
    ended_session(e, role="navigator", why=("job:0092",))
    opened = []
    assert roles.chat(e.l, out=lambda t: None, run=lambda cmd, **k: opened.append(cmd)) == 0
    assert opened and opened[0][opened[0].index("--resume") + 1] == "sess-1", opened
    rec = [r for r in e.l.sessions() if r.get("chat")][0]
    assert rec["outcome"] == "chat" and rec.get("ended"), rec


def test_wake_command_adds_an_owner_wake():
    e = Env(ran=ago(1))
    atexit.register(e.done)
    assert roles.main(["--main", e.dir, "wake", "navigator", "look at 0092"]) == 0
    with open(os.path.join(e.dir, "jobs", "navigator-wakes.json")) as f:
        w = json.load(f)["wakes"]
    assert [(x["when"], x["why"]) for x in w] == [("owner", "look at 0092")], w


def test_gates_start_nothing():
    for kw in ({"blockers": ["disk"]},):
        e = Env(events=["idle:wide:none"], triggers=["headline:m@2"], ran=ago(30), **kw)
        run(e)
        assert e.spawned == [], kw
    e = Env(events=["idle:wide:none"], ran=ago(30))
    e.cli = None
    run(e)
    assert e.spawned == [] and "CLI missing" in e.roles_log()


def test_dead_runner_is_restarted_then_roles_start():
    for name in roles.RESTARTS:
        e = Env(events=["idle:wide:none"], ran=ago(30), blockers=[name])
        e.dead.add(name)
        run(e)
        assert e.restarts == [name], name
        assert f"restarted {name} (pid 901)" in e.roles_log(), name
        assert e.started("lanes"), name  # health re-read green: the tick goes on


def test_restart_only_when_the_live_check_finds_it_dead():
    e = Env(events=["idle:wide:none"], ran=ago(30), blockers=["runner"])  # stale health: it runs
    run(e)
    assert e.restarts == [] and e.spawned == []


def test_other_blockers_are_never_restarted():
    e = Env(events=["idle:wide:none"], ran=ago(30), blockers=["disk", "push"])
    e.dead.update(["disk", "push"])
    run(e)
    assert e.restarts == [] and e.spawned == []


def test_dead_again_soon_after_a_restart_waits_for_the_steward():
    e = Env(events=["idle:wide:none"], ran=ago(30), blockers=["runner"])
    e.dead.add("runner")
    run(e)
    e.dead.add("runner")  # died again
    e.health(events=["idle:wide:none"], blockers=["runner"])
    e.now += datetime.timedelta(minutes=10)
    run(e, ticks=2)
    assert e.restarts == ["runner"]
    assert e.roles_log().count("left for the steward") == 1
    e.now += datetime.timedelta(minutes=25)  # past FIX_RETRY_MIN from the restart
    e.health(events=["idle:wide:none"], blockers=["runner"])
    run(e)
    assert e.restarts == ["runner", "runner"]


def test_dry_run_restarts_nothing():
    e = Env(events=["idle:wide:none"], ran=ago(30), blockers=["runner"])
    e.dead.add("runner")
    atexit.register(e.done)
    out = e.l.tick(dry=True)
    assert e.restarts == [] and out[-1] == "blocker red: runner"


def test_overrun_session_is_killed_and_logged():
    e = Env(events=["idle:wide:none"], ran=ago(1))
    try:
        e.l.tick()
        pid = e.next_pid
        e.now += datetime.timedelta(hours=4, minutes=1)
        e.l.tick()
        assert e.killed == [pid], e.killed
        assert "launcher lanes killed" in e.roles_log()
    finally:
        e.done()


def test_spawn_passes_effort():
    d = tempfile.mkdtemp()
    log = os.path.join(d, "argv.jsonl")
    cli = [sys.executable, "-c", "import sys, json; print(json.dumps(sys.argv[1:]))"]
    roles.spawn(cli, "p", "m", log, cwd=d, effort="high", resume="sess-9").wait()
    with open(log, encoding="utf-8") as f:
        argv = json.loads(f.read())
    assert argv[argv.index("--effort") + 1] == "high" and argv[argv.index("--model") + 1] == "m", argv
    assert argv[argv.index("--resume") + 1] == "sess-9", argv
    assert roles.ROLES["navigator"]["effort"] == "high" and roles.ROLES["lanes"]["effort"] == "medium"


def test_model_command_and_paths():
    e = Env(events=["idle:wide:none"], triggers=["headline:m@2"], ran=ago(1))
    try:
        e.l.tick()
        role, model, prompt, log = e.started("lanes")[0]
        assert model == "claude-opus-5-5" and prompt.startswith("prompt of sts-lanes"), (model, prompt)
        assert os.path.dirname(log) == os.path.join(e.dir, "logs", "roles") and log.endswith(".jsonl"), log
        assert e.started("navigator")[0][1] == "claude-opus-5-5"
        recs = os.listdir(os.path.join(e.dir, "jobs", "roles"))
        assert len(recs) == 2 and all(r.endswith(".json") for r in recs), recs
    finally:
        e.done()


def test_stale_health_is_refreshed():
    e = Env(ran=ago(1))
    e.health(at=ago(0.5))
    run(e)
    assert e.refreshed == 1
    e = Env(ran=ago(1))
    run(e)
    assert e.refreshed == 0


def test_dry_run_changes_nothing():
    e = Env(events=["idle:wide:none"], triggers=["headline:m@2"], ran=ago(1))
    try:
        actions = e.l.tick(dry=True)
        assert e.spawned == [] and e.roles_log() == "", e.spawned
        assert any("start lanes" in a for a in actions) and any("start navigator" in a for a in actions), actions
    finally:
        e.done()


def test_first_start_makes_jobs_roles_and_starts_once():
    e = Env(events=["idle:wide:none"], ran=ago(1))
    for _ in range(3):
        e.l.tick()
        e.now += datetime.timedelta(minutes=5)
    run(e)
    assert len(e.started("lanes")) == 1, e.spawned


def test_navigator_that_ends_without_recording_its_run_waits_for_the_backstop():
    e = Env(ran=ago(80), lanes={})
    for _ in range(6):
        e.l.tick()
        e.live.clear()  # it ended at once, without `woke navigator --ran`
        e.now += datetime.timedelta(minutes=5)
    run(e)
    assert len(e.started("navigator")) == 1, e.spawned


def test_reused_pid_after_a_reboot_is_not_a_session():
    e = Env(ran=ago(1), lanes={})
    atexit.register(e.done)
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        os.makedirs(os.path.join(e.dir, "jobs", "roles"), exist_ok=True)
        with open(os.path.join(e.dir, "jobs", "roles", "lanes-20261110-010000.json"), "w") as f:
            json.dump({"role": "lanes", "pid": other.pid, "model": "m", "log": "x",
                       "started": ago(10, datetime.datetime.now().astimezone())}, f)
        killed = []
        l = roles.Launcher(main=e.dir, now=lambda: datetime.datetime.now().astimezone(), refresh=lambda: None,
                           cli=lambda: None, kill=lambda pid: killed.append(pid))
        l.tick()
        assert killed == [], f"would kill unrelated pid {killed}"
        assert "ended" in l.read("jobs", "roles", "lanes-20261110-010000.json")
    finally:
        other.kill()


def test_unhandled_event_retries_after_4_hours_handled_one_does_not():
    e = Env(events=["idle:wide:none"], ran=ago(1), lanes={})
    atexit.register(e.done)
    e.l.tick()
    e.live.clear()  # the session ended without handling (e.g. it ran out of time)
    e.now += datetime.timedelta(hours=1)
    e.l.tick()
    assert len(e.started("lanes")) == 1, "not again within 4 h"
    e.now += datetime.timedelta(hours=3, minutes=5)
    e.l.tick()
    assert len(e.started("lanes")) == 2 and e.started("lanes")[1], e.spawned
    e.live.clear()
    e.wakes["woken"] = {"idle:wide:none": ago(0, e.now)}  # a session handled it (health.py woke --keys)
    e.save_wakes()
    e.now += datetime.timedelta(hours=5)
    e.l.tick()
    assert len(e.started("lanes")) == 2, "a handled event starts nothing"


def test_session_outcome_is_parsed_and_logged():
    e = Env(events=["idle:wide:none"], ran=ago(1), lanes={})
    atexit.register(e.done)
    e.l.tick()
    e.write_log(0, '{"type":"system"}\n{"type":"result","subtype":"error_max_turns","is_error":true}\n')
    e.live.clear()
    e.now += datetime.timedelta(minutes=5)
    e.l.tick()
    rec = [r for r in e.l.sessions() if r["role"] == "lanes"][0]
    assert rec["outcome"] == "error: error_max_turns", rec
    assert "lanes ended after" in e.roles_log() and "error: error_max_turns" in e.roles_log()
    e.health(events=["idle:deep:none"])
    e.now += datetime.timedelta(minutes=5)
    e.l.tick()
    e.write_log(1, '{"type":"result","subtype":"success","is_error":false}\n')
    e.live.clear()
    e.now += datetime.timedelta(minutes=5)
    e.l.tick()
    assert [r for r in e.l.sessions() if r["role"] == "lanes"][1]["outcome"] == "ok"


def test_killed_or_silent_session_outcome():
    e = Env(events=["idle:wide:none"], ran=ago(1), lanes={})
    atexit.register(e.done)
    e.l.tick()
    e.now += datetime.timedelta(hours=4, minutes=1)
    e.l.tick()
    assert [r for r in e.l.sessions() if r["role"] == "lanes"][0]["outcome"] == "killed"


FAKE_CLI = '''import sys, time
print("fake claude", " ".join(sys.argv[1:4]), flush=True)
time.sleep(float(sys.argv[sys.argv.index("--sleep") + 1]) if "--sleep" in sys.argv else 1.0)
'''


def fake_cli(env, sleep=1.0):
    path = os.path.join(env.dir, "fake_claude.py")
    with open(path, "w") as f:
        f.write(FAKE_CLI.replace("1.0)", f"{sleep})"))
    return [sys.executable, path]


def test_end_to_end_run_with_a_fake_cli():
    real_now = datetime.datetime.now().astimezone()
    e = Env(now=real_now, events=["idle:wide:none"], ran=ago(1, real_now), lanes={"wide": {"step": "x"}})
    atexit.register(e.done)
    script = os.path.join(os.path.dirname(__file__), "..", "roles.py")
    p = subprocess.run([sys.executable, script, "--main", e.dir, "--cli", json.dumps(fake_cli(e)),
                        "run", "--poll", "1", "--ticks", "5"], capture_output=True, text=True, timeout=120)
    log = e.roles_log()
    assert p.returncode == 0, p.stderr
    assert "launcher lanes started: idle:wide:none" in log and "launcher lanes ended" in log, log + p.stdout
    outs = os.listdir(os.path.join(e.dir, "logs", "roles"))
    with open(os.path.join(e.dir, "logs", "roles", outs[0])) as f:
        assert "fake claude -p prompt of sts-lanes" in f.read()
    assert e.wakes_woken() == {}, "the session marks events handled, not the launcher"
    assert os.path.exists(os.path.join(e.dir, "jobs", "roles-status.json"))
    assert os.path.exists(os.path.join(e.dir, "jobs", "roles.pid"))


def test_overrun_real_process_is_killed():
    # The real clock: the launcher only kills a pid created before the session's start.
    real_now = datetime.datetime.now().astimezone()
    e = Env(now=real_now, events=["idle:wide:none"], ran=ago(1, real_now))
    atexit.register(e.done)
    clock = [real_now]
    cli = fake_cli(e, sleep=60)
    l = roles.Launcher(main=e.dir, now=lambda: clock[0], refresh=lambda: None, cli=lambda: cli)
    l.tick()
    rec = [r for r in l.sessions() if r["role"] == "lanes"][0]
    assert roles.health.pid_alive(rec["pid"])
    clock[0] = real_now + datetime.timedelta(hours=5)
    l.tick()
    for _ in range(20):
        if not roles.health.pid_alive(rec["pid"]):
            break
        time.sleep(0.25)
    assert not roles.health.pid_alive(rec["pid"])
    assert [r for r in l.sessions() if r["file"] == rec["file"]][0].get("killed")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
