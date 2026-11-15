"""Tests for the health check (scripts/health.py, docs/specs/operating-model.md
verification 1). Run with `python scripts/tests/test_health.py` (plain
asserts; every `test_*` function runs) or with pytest."""

import datetime
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import health  # noqa: E402

NOW = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone.utc)


def iso(hours_ago):
    return (NOW - datetime.timedelta(hours=hours_ago)).isoformat(timespec="seconds")


class Fake(health.Probe):
    """A healthy machine on temp folders; each test breaks one thing."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="health-test-")
        super().__init__(main=self.dir, now=NOW, builds=os.path.join(self.dir, "builds"))
        for s in ("pending", "running", "done", "parked"):
            os.makedirs(os.path.join(self.dir, "jobs", s))
        os.makedirs(os.path.join(self.dir, "docs", "claims", "measurement"))
        os.makedirs(self.builds)
        with open(os.path.join(self.dir, "jobs", "runner.pid"), "w") as f:
            f.write("4242")
        with open(os.path.join(self.dir, "jobs", "roles.pid"), "w") as f:
            f.write("4343")
        self.alive_pids = {4242, 4343}
        self.free = 50.0
        self.check_text = "88 facts: 83 clean, 5 suspect, 0 unchecked\n"
        self.render_lines = 40
        self.refs = []          # (branch, commit age in hours, merged)
        self.unpushed = []      # commit ages in hours
        self.auth = True
        self.open_ideas = [80, 77]
        self.backlog = "- ideas#80 ...\n- ideas#77 ...\n"
        self.snaps = []         # sizes in bytes
        self.direction = None   # (sha, time) of the last direction.md commit
        self.slept = []         # (start, end) of machine sleeps
        # a lane with 6 h of ready work, a test-full that passed yesterday, a fresh headline fact
        self.job("pending", "0100-gauntlet", lane="depth", estimate_min=360)
        self.job("done", "0090-test-full", lane="filler", status="ok", started=iso(25), ended=iso(24))
        self.job("done", "0091-gauntlet", lane="depth", threads=12, status="ok", started=iso(24), ended=iso(0))
        self.fact("measurement/headline@two-turn", at=iso(10))

    def job(self, state, jid, **kw):
        d = {"id": jid, "threads": 4, "lane": "main", "estimate_min": None}
        d.update(kw)
        with open(os.path.join(self.dir, "jobs", state, jid + ".json"), "w") as f:
            json.dump(d, f)

    def fact(self, key, at, note=None, value="x", history=(), by="lane-session", sources=(), status="active"):
        path = os.path.join(self.dir, "docs", "claims", key + ".json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"key": key, "rev": len(history) + 1, "value": value, "status": status, "note": note,
                       "by": by, "sources": list(sources), "at": at + " @ abc1234", "history": list(history)}, f)

    def direction_commit(self):
        return self.direction

    def sleeps(self):
        return self.slept

    def pid_alive(self, pid):
        return pid in self.alive_pids

    def disk_free_gb(self):
        return self.free

    def kb(self, *args):
        if args[0] == "check":
            return self.check_text
        return "line\n" * self.render_lines

    def branches(self):
        return self.refs

    def unpushed_ages_h(self):
        return self.unpushed

    def gh_auth_ok(self):
        return self.auth

    def ideas(self):
        return self.open_ideas

    def backlog_text(self):
        return self.backlog

    def snapshot_sizes(self):
        return self.snaps

    def done(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def metric(report, name):
    return next(m for m in report["metrics"] if m["name"] == name)


def run(probe, **kw):
    try:
        return health.measure(probe, **kw)
    finally:
        probe.done()


def test_healthy_machine_is_green_and_exits_0():
    p = Fake()
    r = run(p)
    reds = [m["name"] for m in r["metrics"] if m["state"] != "green"]
    assert reds == [], reds
    assert health.exit_code(r) == 0


def test_dead_runner_is_a_blocker():
    p = Fake()
    p.alive_pids = set()
    r = run(p)
    m = metric(r, "runner")
    assert (m["kind"], m["state"]) == ("blocker", "red"), m
    assert health.exit_code(r) == 1


def test_missing_runner_pid_is_a_blocker():
    p = Fake()
    os.remove(os.path.join(p.dir, "jobs", "runner.pid"))
    r = run(p)
    assert metric(r, "runner")["state"] == "red"


def test_dead_or_missing_launcher_is_a_blocker():
    p = Fake()
    p.alive_pids = {4242}
    r = run(p)
    m = metric(r, "launcher")
    assert (m["kind"], m["state"]) == ("blocker", "red"), m
    p = Fake()
    os.remove(os.path.join(p.dir, "jobs", "roles.pid"))
    assert metric(run(p), "launcher")["state"] == "red"


def test_disk_stub_under_8_gb_is_a_blocker():
    p = Fake()
    p.free = 7.5
    r = run(p)
    assert metric(r, "disk")["state"] == "red"
    assert health.exit_code(r) == 1


def test_push_failure_old_unpushed_commit_is_a_blocker():
    p = Fake()
    p.unpushed = [2.0]
    r = run(p)
    assert metric(r, "push")["state"] == "red"


def test_push_fresh_unpushed_commit_is_fine():
    p = Fake()
    p.unpushed = [0.1]
    r = run(p)
    assert metric(r, "push")["state"] == "green"


def test_push_unknown_when_git_cant_tell():
    p = Fake()
    p.unpushed = None
    r = run(p)
    assert metric(r, "push")["state"] == "unknown"


def test_auth_failure_is_a_blocker():
    p = Fake()
    p.auth = False
    r = run(p)
    assert metric(r, "push")["state"] == "red"


def test_empty_queue_is_a_work_item_not_a_blocker():
    p = Fake()
    os.remove(os.path.join(p.dir, "jobs", "pending", "0100-gauntlet.json"))
    r = run(p)
    m = metric(r, "ready")
    assert (m["kind"], m["state"]) == ("work", "red"), m
    assert health.exit_code(r) == 0


def test_ready_work_counts_running_remainder_not_main_or_filler():
    p = Fake()
    os.remove(os.path.join(p.dir, "jobs", "pending", "0100-gauntlet.json"))
    p.job("running", "0101-learn", lane="run", estimate_min=300, started=iso(1))   # 4 h left
    p.job("pending", "0102-x", lane="main", estimate_min=600)
    p.job("pending", "0103-y", lane="filler", estimate_min=600)
    r = run(p)
    m = metric(r, "ready")
    assert m["state"] == "green" and abs(m["value"] - 4.0) < 0.01, m


def test_parked_job_is_not_ready_work():
    p = Fake()
    os.remove(os.path.join(p.dir, "jobs", "pending", "0100-gauntlet.json"))
    p.job("pending", "0100-gauntlet", lane="depth", estimate_min=360, parked="0099-x did not pass (failed)")
    r = run(p)
    m = metric(r, "ready")
    assert m["state"] == "red" and m["value"] == 0, m


def test_cpu_red_when_share_low():
    p = Fake()
    os.remove(os.path.join(p.dir, "jobs", "done", "0091-gauntlet.json"))
    p.job("done", "0091-gauntlet", lane="depth", threads=4, status="ok", started=iso(24), ended=iso(0))
    r = run(p)
    m = metric(r, "cpu")
    assert m["state"] == "red", m   # 4 threads: a low share
    assert m["kind"] == "work"


def test_cpu_red_on_zero_job_minutes():
    p = Fake()
    os.remove(os.path.join(p.dir, "jobs", "done", "0091-gauntlet.json"))
    p.job("done", "0091-gauntlet", lane="depth", threads=16, status="ok", started=iso(22), ended=iso(0))
    r = run(p)
    m = metric(r, "cpu")
    assert m["state"] == "red", m   # a high share but two idle hours
    assert 115 <= m["detail"]["zero_job_min"] <= 125, m


def test_test_full_found_by_id():
    p = Fake()
    p.job("done", "0095-test-fullish", lane="filler", status="failed", started=iso(2), ended=iso(1))
    p.job("done", "0096-gauntlet", lane="depth", status="failed", started=iso(2), ended=iso(1))
    r = run(p)
    m = metric(r, "tests")
    assert m["state"] == "green" and m["detail"]["id"] == "0090-test-full", m


def test_test_full_per_test_probe_ignored():
    p = Fake()
    p.job("done", "0099-test-full", lane="x", status="failed", started=iso(2), ended=iso(1),
          cmd=["python", "scripts/test_full.py", "--cap-gb", "1.7", "--per-test", "scripts/tests/test_solve.py"])
    m = metric(run(p), "tests")
    assert m["state"] == "green" and m["detail"]["id"] == "0090-test-full", m


def test_test_full_failing_is_red():
    p = Fake()
    p.job("done", "0099-test-full", lane="filler", status="failed", started=iso(2), ended=iso(1))
    r = run(p)
    m = metric(r, "tests")
    assert m["state"] == "red" and m["detail"]["id"] == "0099-test-full", m
    assert health.exit_code(r) == 0


def test_test_full_older_than_48h_is_red():
    p = Fake()
    os.remove(os.path.join(p.dir, "jobs", "done", "0090-test-full.json"))
    p.job("done", "0090-test-full", lane="filler", status="ok", started=iso(51), ended=iso(50))
    r = run(p)
    assert metric(r, "tests")["state"] == "red"


def test_test_full_never_run_is_red():
    p = Fake()
    os.remove(os.path.join(p.dir, "jobs", "done", "0090-test-full.json"))
    r = run(p)
    assert metric(r, "tests")["state"] == "red"


def test_fake_kb_check_over_10_is_red():
    p = Fake()
    p.check_text = "suspect lines\n90 facts: 79 clean, 8 suspect, 3 unchecked\n"
    r = run(p)
    m = metric(r, "facts")
    assert m["state"] == "red" and m["value"] == 11, m


def test_kb_check_unreadable_is_unknown():
    p = Fake()
    p.check_text = None
    r = run(p)
    assert metric(r, "facts")["state"] == "unknown"


def test_debris_idle_branches():
    p = Fake()
    p.refs = [("claude/old", 100, True), ("lane/x", 10, False), ("lane/y", 80, False), ("feature", 500, False)]
    r = run(p)
    m = metric(r, "debris")
    assert m["state"] == "red", m
    assert m["detail"]["merged"] == ["claude/old"] and m["detail"]["unmerged"] == ["lane/y"], m
    assert m["detail"]["other_new"] == ["feature"], m


def test_debris_other_branches_listed_once():
    p = Fake()
    p.refs = [("feature", 500, False)]
    with open(os.path.join(p.dir, "jobs", "health.json"), "w") as f:
        json.dump({"debris_other_seen": ["feature"]}, f)
    r = run(p)
    m = metric(r, "debris")
    assert m["state"] == "green" and m["detail"]["other_new"] == [], m
    assert r["debris_other_seen"] == ["feature"]


def test_snapshots_too_many_or_too_big():
    p = Fake()
    p.snaps = [1] * 21
    assert metric(run(p), "snapshots")["state"] == "red"
    p = Fake()
    p.snaps = [1.5e9, 0.6e9]
    assert metric(run(p), "snapshots")["state"] == "red"
    p = Fake()
    p.snaps = [0.5e9] * 3
    assert metric(run(p), "snapshots")["state"] == "green"


def test_untriaged_ideas():
    p = Fake()
    p.open_ideas = [80, 77, 81]
    r = run(p)
    m = metric(r, "ideas")
    assert m["state"] == "red" and m["detail"]["untriaged"] == [81], m


def test_ideas_unknown_when_gh_fails():
    p = Fake()
    p.open_ideas = None
    assert metric(run(p), "ideas")["state"] == "unknown"


def test_stagnation_after_3_days():
    p = Fake()
    p.fact("measurement/headline@two-turn", at=iso(80))
    r = run(p)
    m = metric(r, "stagnation")
    assert (m["kind"], m["state"]) == ("work", "red"), m


def test_stagnation_ignores_steward_filed_facts():
    p = Fake()
    p.fact("measurement/headline@two-turn", at=iso(5), note="steward: 0123", by="steward-abc",
           history=[{"rev": 1, "value": "y", "at": iso(80) + " @ abc", "by": "lane-session"}])
    r = run(p)
    assert metric(r, "stagnation")["state"] == "red"


def test_stagnation_ignores_steward_revisions_in_history():
    # kb drops `note` from history entries; `by` survives
    p = Fake()
    p.fact("measurement/headline@two-turn", at=iso(5), note="steward: 0124", by="steward-abc",
           history=[{"rev": 1, "value": "y", "at": iso(80) + " @ abc", "by": "lane-session"},
                    {"rev": 2, "value": "z", "at": iso(10) + " @ abc", "by": "steward-abc"}])
    r = run(p)
    assert metric(r, "stagnation")["state"] == "red"


def test_passed_checkpoint_resets_stagnation():
    p = Fake()
    p.fact("measurement/headline@two-turn", at=iso(80))
    p.fact("lane/cheap-depth/checkpoint", at=iso(20), value="passed line-step read")
    assert metric(run(p), "stagnation")["state"] == "green"
    p = Fake()
    p.fact("measurement/headline@two-turn", at=iso(80))
    p.fact("lane/cheap-depth/checkpoint", at=iso(20), value="failed line-step read")
    assert metric(run(p), "stagnation")["state"] == "red"


def test_blockers_and_work_items_separated():
    p = Fake()
    p.free = 1.0
    os.remove(os.path.join(p.dir, "jobs", "pending", "0100-gauntlet.json"))
    r = run(p)
    assert [m["name"] for m in r["blockers"]] == ["disk"], r["blockers"]
    assert "ready" in [m["name"] for m in r["work"]]
    kinds = {m["name"]: m["kind"] for m in r["metrics"]}
    assert {n for n, k in kinds.items() if k == "blocker"} == {"runner", "launcher", "disk", "push"}


def test_main_writes_health_json_and_exits_1_only_on_blocker():
    p = Fake()
    out = os.path.join(p.dir, "jobs", "health.json")
    try:
        assert health.main([], probe=p) == 0
        with open(out) as f:
            assert json.load(f)["blockers"] == []
        p.free = 1.0
        assert health.main([], probe=p) == 1
    finally:
        p.done()


CHARTER = "goal: g; measure: m; stop: s; kind: project; share: 35; cap: 30 cpu-h; end: 2026-11-12"


def lanes_fake():
    """Two chartered lanes: deep (6 h queued) and wide (nothing queued)."""
    p = Fake()
    os.remove(os.path.join(p.dir, "jobs", "pending", "0100-gauntlet.json"))
    p.fact("lane/deep", at=iso(48), value=CHARTER)
    p.fact("lane/deep/step", at=iso(2), value="step 2: read 0101")
    p.fact("lane/wide", at=iso(48), value=CHARTER.replace("project", "exploration"))
    p.job("pending", "0101-gauntlet", lane="deep", estimate_min=360)
    return p


def test_ready_counts_chartered_lanes_by_lane():
    p = lanes_fake()
    p.job("pending", "0102-gauntlet", lane="depth", estimate_min=600)   # an unchartered lane
    r = run(p)
    m = metric(r, "ready")
    assert m["value"] == 6.0 and m["detail"]["by_lane"] == {"deep": 6.0, "wide": 0.0}, m
    assert r["lanes"]["wide"]["kind"] == "exploration" and r["lanes"]["deep"]["cap"] == 30.0, r["lanes"]


def test_lane_wakes_once_per_event():
    p = lanes_fake()
    try:
        r = health.measure(p)
        assert r["wakes"]["lanes"] == ["idle:wide:none"], r["wakes"]
        assert health.main(["--quiet"], probe=p) == 0
        assert health.main(["woke", "lanes"], probe=p) == 0
        r = health.measure(p)
        assert r["wakes"]["lanes"] == [], r["wakes"]   # the same event doesn't wake twice
        p.job("done", "0103-gauntlet", lane="deep", status="ok", started=iso(3), ended=iso(1), check=["x"])
        r = health.measure(p)
        assert r["wakes"]["lanes"] == ["ended:0103-gauntlet"], r["wakes"]
    finally:
        p.done()


def test_only_decisive_ended_jobs_wake_a_lane():
    """An ok job without a check, ended while its lane has more queued, is
    held; a check job, a failed job or the lane's last job wakes the lane,
    and the held ends ride along with it."""
    p = lanes_fake()
    try:
        assert health.main(["--quiet"], probe=p) == 0
        assert health.main(["woke", "lanes"], probe=p) == 0   # idle:wide:none handled
        p.job("done", "0103-gauntlet", lane="deep", status="ok", started=iso(4), ended=iso(3))
        p.job("done", "0102-gauntlet", lane="deep", status="ok", started=iso(31), ended=iso(30))  # older than 24 h
        assert health.measure(p)["wakes"]["lanes"] == [], "0101 still pending: held"
        p.job("done", "0104-gauntlet", lane="deep", status="failed", started=iso(3), ended=iso(2))
        r = health.measure(p)
        assert sorted(r["wakes"]["lanes"]) == ["ended:0102-gauntlet", "ended:0103-gauntlet",
                                               "ended:0104-gauntlet"], r["wakes"]
        assert health.main(["woke", "lanes", "--keys", "ended:0102-gauntlet,ended:0103-gauntlet,ended:0104-gauntlet"],
                           probe=p) == 0
        p.job("done", "0105-gauntlet", lane="deep", status="ok", started=iso(2), ended=iso(1))
        assert health.measure(p)["wakes"]["lanes"] == [], "held again"
        os.remove(os.path.join(p.dir, "jobs", "pending", "0101-gauntlet.json"))  # the lane's last job ended
        r = health.measure(p)
        assert sorted(r["wakes"]["lanes"]) == ["ended:0105-gauntlet", "idle:deep:rev1"], r["wakes"]
    finally:
        p.done()


def test_moved_step_wakes_an_idle_lane_again():
    """A code-only lane queues no jobs: its idle wake is named by its step's
    revision, so landing a step (a new revision) wakes the worker again."""
    p = lanes_fake()
    try:
        p.fact("lane/wide/step", at=iso(3), value="stage 2 built; next: stage 3 spec")
        r = health.measure(p)
        assert r["wakes"]["lanes"] == ["idle:wide:rev1"], r["wakes"]
        assert health.main(["woke", "lanes", "--keys", "idle:wide:rev1"], probe=p) == 0
        assert health.measure(p)["wakes"]["lanes"] == [], "handled: no second wake"
        p.fact("lane/wide/step", at=iso(1), value="stage 3 built; next: stage 4 spec",
               history=[{"value": "stage 2 built; next: stage 3 spec", "at": iso(3)}])
        r = health.measure(p)
        assert r["wakes"]["lanes"] == ["idle:wide:rev2"], r["wakes"]
    finally:
        p.done()


def test_failed_test_full_wakes_the_lane_worker():
    p = Fake()
    p.job("done", "0099-test-full", lane="filler", status="failed", started=iso(2), ended=iso(1))
    r = run(p)
    assert "tests:0099-test-full" in r["wakes"]["lanes"], r["wakes"]


def test_lane_close_events_go_to_the_lane_worker_not_the_navigator():
    p = lanes_fake()
    with open(os.path.join(p.dir, "jobs", "wakes.json"), "w") as f:
        json.dump({"navigator_ran": iso(20)}, f)
    p.fact("lane/wide/step", at=iso(1), value="done: probe failed, stop")
    p.job("done", "0104-learn", lane="deep", threads=8, status="ok", started=iso(5), ended=iso(1))  # 32 CPU-h
    p.fact("lane/old", at=iso(200), value=CHARTER.replace("2026-11-12", "2026-11-09"))
    p.fact("measurement/headline@two-turn", at=iso(1))       # a headline change after the last run
    p.direction = ("abc1234", NOW - datetime.timedelta(hours=1))
    p.backlog += "".join(f"- ideas#{n} x\n" for n in range(1, 9))
    r = run(p)
    lanes = r["wakes"]["lanes"]
    assert "lane-done:wide" in lanes and "lane-cap:deep" in lanes and "lane-end:old" in lanes, lanes
    assert "lane-end:deep" not in lanes, lanes
    assert r["wakes"]["navigator"] == [], r["wakes"]   # no fixed lane, headline, direction or ideas trigger
    assert r["wakes"]["lane_cpu_h"]["deep"] == 32.0, r["wakes"]


def navwake(p, *args):
    assert health.main(["navwake", *args], probe=p) == 0


def nav(p):
    w = health.measure(p)["wakes"]
    return w["navigator"], w["notes"]


def test_self_set_wakes_fire_on_their_event_only():
    p = lanes_fake()
    try:
        assert health.main(["woke", "navigator", "--ran"], probe=p) == 0
        p.fact("measurement/x", at=iso(5))
        navwake(p, "add", "job:0105", "--why", "the stack read decides stage B")
        navwake(p, "add", "fact:measurement/x", "--why", "x moves the ranking")
        navwake(p, "add", "checkpoint:deep", "--why", "deep's first checkpoint")
        navwake(p, "add", "ideas:2", "--why", "two new ideas")
        navwake(p, "add", "date:2026-11-10 13:00", "--why", "review due")
        assert nav(p)[0] == [], nav(p)
        p.job("done", "0105-gauntlet", lane="deep", status="ok", started=iso(2), ended=iso(-1))
        p.fact("measurement/x", at=iso(-1), history=[{"at": iso(5), "value": "old"}])
        p.fact("lane/deep/checkpoint", at=iso(-1), value="failed first")
        p.backlog += "- ideas#1 x\n- ideas#2 x\n"
        p.now = NOW + datetime.timedelta(hours=2)
        keys, notes = nav(p)
        assert set(keys) == {"job:0105", "fact:measurement/x@2", "checkpoint:deep@1", "ideas:4",
                             "date:2026-11-10 13:00"}, keys
        assert notes["job:0105"] == "the stack read decides stage B", notes
        p.job("done", "0106-gauntlet", lane="deep", status="ok", started=iso(30), ended=iso(28))
        navwake(p, "add", "job:0106", "--why", "already ended before the wake was set")
        assert "job:0106" not in nav(p)[0], "a job that ended before its wake doesn't fire it"
    finally:
        p.done()


def test_bad_wake_kind_is_refused():
    p = Fake()
    try:
        for when in ("whenever the boss looks odd", "date:tomorrow", "ideas:many", "job:"):
            assert health.main(["navwake", "add", when, "--why", "x"], probe=p) == 2, when
        assert health.nav_wakes(p) == []
    finally:
        p.done()


def test_owner_and_lane_wakes_fire_with_their_notes_and_clear_keeps_unseen_ones():
    p = lanes_fake()
    try:
        navwake(p, "add", "owner", "--why", "look at the boss curve")
        navwake(p, "add", "lane:deep", "--why", "deep closed on go: the ranking may change")
        navwake(p, "add", "job:0199", "--why", "self-set")
        keys, notes = nav(p)
        assert len(keys) == 2 and all(k.startswith(("owner@", "lane:deep@")) for k in keys), keys
        assert "look at the boss curve" in notes.values(), notes
        assert health.main(["--quiet"], probe=p) == 0
        assert health.main(["woke", "navigator", "--ran"], probe=p) == 0    # the run handled both
        p.now = NOW + datetime.timedelta(minutes=5)
        navwake(p, "add", "owner", "--why", "a second note, mid-run")
        navwake(p, "clear")
        left = health.nav_wakes(p)
        assert [w["why"] for w in left] == ["a second note, mid-run"], left
    finally:
        p.done()


def test_a_wake_added_mid_run_survives_the_close():
    p = lanes_fake()
    try:
        navwake(p, "add", "owner", "--why", "A")
        assert health.main(["--quiet"], probe=p) == 0
        started_on = nav(p)[0]
        p.now = NOW + datetime.timedelta(minutes=5)
        navwake(p, "add", "owner", "--why", "B, mid-run")
        assert health.main(["--no-state", "--quiet"], probe=p) == 0   # the launcher's refresh lists B too
        assert health.main(["woke", "navigator", "--ran", "--keys", ",".join(started_on)], probe=p) == 0
        navwake(p, "clear")
        assert [w["why"] for w in health.nav_wakes(p)] == ["B, mid-run"]
        assert list(nav(p)[1].values()) == ["B, mid-run"], nav(p)
    finally:
        p.done()


def test_navigator_ran_resets_its_triggers_and_blockers_gate_it():
    p = lanes_fake()
    try:
        navwake(p, "add", "owner", "--why", "x")
        assert health.main(["--quiet"], probe=p) == 0
        assert health.main(["woke", "navigator", "--ran"], probe=p) == 0
        assert nav(p)[0] == []
        p.free = 1.0
        navwake(p, "add", "owner", "--why", "y")
        assert nav(p)[0] == []   # a blocker is red
    finally:
        p.done()


def test_stagnation_still_wakes_the_navigator():
    p = Fake()
    p.fact("measurement/headline@two-turn", at=iso(100))
    r = run(p)
    assert [k for k in r["wakes"]["navigator"] if k.startswith("stagnation:")], r["wakes"]


def session(p, role, name, outcome, hours_ago):
    os.makedirs(os.path.join(p.dir, "jobs", "roles"), exist_ok=True)
    with open(os.path.join(p.dir, "jobs", "roles", name + ".json"), "w") as f:
        json.dump({"role": role, "pid": 1, "started": iso(hours_ago), "ended": iso(hours_ago - 0.5),
                   "outcome": outcome, "log": "x"}, f)


def test_two_failed_sessions_of_a_role_turn_red():
    p = Fake()
    session(p, "lanes", "lanes-1", "ok", 5)
    session(p, "lanes", "lanes-2", "error: error_max_turns", 3)
    session(p, "navigator", "navigator-1", "killed", 2)
    assert metric(run(p), "sessions")["state"] == "green"
    p = Fake()
    session(p, "navigator", "navigator-1", "killed", 5)
    session(p, "navigator", "navigator-2", "chat", 3)       # an owner chat is not a failed session
    assert metric(run(p), "sessions")["state"] == "green"
    p = Fake()
    session(p, "lanes", "lanes-1", "no result", 5)
    session(p, "lanes", "lanes-2", "killed", 3)
    m = metric(run(p), "sessions")
    assert (m["kind"], m["state"]) == ("work", "red") and m["detail"]["failing"] == ["lanes"], m


def test_fact_suspect_over_a_day_turns_red():
    p = Fake()
    p.check_text = "how/tests [suspect]: changed: x\n88 facts: 87 clean, 1 suspect, 0 unchecked\n"
    try:
        health.main(["--quiet"], probe=p)
        with open(os.path.join(p.dir, "jobs", "health.json")) as f:
            r = json.load(f)
        assert metric(r, "stale-facts")["state"] == "green" and r["suspect_since"]["how/tests"] == NOW.isoformat(timespec="seconds")
        p.now = NOW + datetime.timedelta(hours=25)
        health.main(["--quiet"], probe=p)
        with open(os.path.join(p.dir, "jobs", "health.json")) as f:
            m = metric(json.load(f), "stale-facts")
        assert m["state"] == "red" and m["detail"]["keys"] == ["how/tests"], m
        p.check_text = "88 facts: 88 clean, 0 suspect, 0 unchecked\n"
        health.main(["--quiet"], probe=p)
        with open(os.path.join(p.dir, "jobs", "health.json")) as f:
            r = json.load(f)
        assert metric(r, "stale-facts")["state"] == "green" and r["suspect_since"] == {}
    finally:
        p.done()


def test_unchecked_facts_dont_count_as_stale():
    p = Fake()
    p.check_text = "results/x [unchecked]: not here\n88 facts: 87 clean, 0 suspect, 1 unchecked\n"
    try:
        health.main(["--quiet"], probe=p)
        p.now = NOW + datetime.timedelta(hours=30)
        health.main(["--quiet"], probe=p)
        with open(os.path.join(p.dir, "jobs", "health.json")) as f:
            assert metric(json.load(f), "stale-facts")["state"] == "green"
    finally:
        p.done()


def test_woke_with_keys_records_only_those():
    p = lanes_fake()
    try:
        health.main(["--quiet"], probe=p)
        assert health.main(["woke", "lanes", "--keys", "idle:wide:none,ended:9999-x"], probe=p) == 0
        with open(os.path.join(p.dir, "jobs", "wakes.json")) as f:
            assert set(json.load(f)["woken"]) == {"idle:wide:none", "ended:9999-x"}
    finally:
        p.done()


def test_overrun_projects_from_pace():
    p = Fake()
    try:
        log = os.path.join(p.dir, "late.log")
        with open(log, "w") as f:
            f.write("1 / 200 starts, 21 s\n119 / 200 starts, 24656 s\n")
        p.job("running", "0083-mutate-monsters", lane="goal1", estimate_min=340, started=iso(7), log=log)
        p.job("running", "0084-gauntlet", lane="goal1", estimate_min=500, started=iso(7))  # within its estimate
        p.job("running", "0085-x", lane="goal1", estimate_min=60, started=iso(3), log=os.path.join(p.dir, "none.log"))
        m = health.overrun(p)
        assert m["state"] == "red" and m["kind"] == "work" and m["value"] == 2 and m["fix"]
        late = {j["id"]: j for j in m["detail"]["jobs"]}
        assert set(late) == {"0083-mutate-monsters", "0085-x"}
        assert late["0083-mutate-monsters"]["progress"] == "119 / 200"
        assert late["0083-mutate-monsters"]["projected_min"] == round(420 * 200 / 119)
        assert late["0085-x"]["projected_min"] is None  # no progress line: the lane reads the log
        names = [x["name"] for x in health.measure(p)["metrics"]]
        assert "overrun" in names
    finally:
        p.done()


def test_overrun_green_after_re_estimate():
    p = Fake()
    try:
        p.job("running", "0083-mutate-monsters", lane="goal1", estimate_min=720, started=iso(7))
        assert health.overrun(p)["state"] == "green"
    finally:
        p.done()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)


def test_lane_cpu_hours_leave_out_machine_sleep():
    p = lanes_fake()
    p.job("done", "0104-learn", lane="deep", threads=8, status="ok", started=iso(5), ended=iso(1))  # 32 CPU-h booked
    p.slept = [(NOW - datetime.timedelta(hours=3), NOW - datetime.timedelta(hours=2)),   # inside: -8
               (NOW - datetime.timedelta(hours=1.5), NOW - datetime.timedelta(hours=0.5))]  # half inside: -4
    r = run(p)
    assert r["wakes"]["lane_cpu_h"]["deep"] == 20.0, r["wakes"]


def test_sleeps_parse_the_event_lines():
    p = Fake()
    p.run = lambda cmd, **kw: "2026-11-11T19:00:36.1571554Z 2026-11-11T21:29:15.0388617Z\nbad line\n"
    p.sleeps = lambda: health.Probe.sleeps(p)
    (a, b), = p.sleeps()
    assert round((b - a).total_seconds() / 60) == 149 and a.utcoffset().total_seconds() == 0, (a, b)
