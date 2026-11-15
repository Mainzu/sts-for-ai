"""The sweep watcher (learned-play Amendment 3, C3), on a fake registry and
logs: a finished round gives one progress line and no exit; a crash, a
guard stop, a 30-min silence, a run past 2x its projection, a label-scale
warning and memory above the limit each exit with that reason; a normal
finish exits cleanly with the table path.

    python scripts/tests/test_sweep_watch.py
"""

import datetime
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sweep_watch

T0 = datetime.datetime(2026, 10, 26, 22, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=0)))


class Fake:
    """A sweep root with plan.json, sweep.log and row logs, a settable
    clock, memory and pid liveness."""

    def __init__(self, root):
        self.root, self.logs = root, os.path.join(root, "logs")
        os.makedirs(self.logs)
        os.makedirs(os.path.join(root, "runs"))
        self.t, self.used, self.alive = T0, 0.5, True
        with open(os.path.join(self.logs, "plan.json"), "w") as f:
            json.dump({"pid": 1234, "jobs": 2, "rows": {
                "score-s0": {"minutes_by_round": [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300], "first_round": 1},
                "score-s1": {"minutes_by_round": [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300], "first_round": 1}}}, f)
        self.sweep("started score-s0 (log: x)")
        self.sweep("started score-s1 (log: y)")
        self.row("score-s0", "dataset abc (train, round 1): 3000 games, 40s")
        self.w = sweep_watch.Watcher(root, clock=lambda: self.t, mem=lambda: (self.used, 60),
                                     alive=lambda pid: self.alive)

    def sweep(self, msg, t=None):
        with open(os.path.join(self.logs, "sweep.log"), "a", encoding="utf-8") as f:
            f.write(f"{(t or self.t).isoformat(timespec='seconds')} {msg}\n")
        self.touch()

    def row(self, name, line):
        with open(os.path.join(self.logs, f"{name}.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
        self.touch()

    def touch(self):
        for n in os.listdir(self.logs):
            os.utime(os.path.join(self.logs, n), (self.t.timestamp(), self.t.timestamp()))

    def round(self, name, k, net=(0.5, 0.48), heur=(0.53, 0.5), met=False):
        d = os.path.join(self.root, "runs", f"2026-10-26-{name}-r{k}-{k:06x}")
        os.makedirs(d)
        halves = {h: {"net": [n, n - 0.04, n + 0.04], "heuristic": [x, x - 0.04, x + 0.04]}
                  for h, n, x in zip(("train", "held_out"), net, heur)}
        files = {"config.json": {"name": name}, "run.json": {"created": self.t.isoformat(timespec="seconds")},
                 "round.json": {"round": k, "val_mse": 0.1, "tight_win": {h: v["net"] for h, v in halves.items()},
                                "heuristic": {"halves": halves}, "window": {"round0_in": True},
                                "gate": {"met": met, "halves": halves}}}
        for n, obj in files.items():
            with open(os.path.join(d, n), "w") as f:
                json.dump(obj, f)

    def later(self, minutes):
        self.t += datetime.timedelta(minutes=minutes)


def with_fake(f):
    def run():
        with tempfile.TemporaryDirectory() as root:
            f(Fake(root))
    run.__name__ = f.__name__
    return run


def kinds(events):
    return [k for k, _ in events]


@with_fake
def test_quiet_sweep_reports_nothing(fk):
    fk.later(5)
    assert fk.w.check() == []


@with_fake
def test_finished_round_is_one_progress_line(fk):
    fk.later(10)
    fk.round("score-s0", 1)
    ev = fk.w.check()
    assert kinds(ev) == ["progress"]
    text = ev[0][1]
    assert "score-s0 round 1" in text and "train 0.500 vs heuristic 0.530" in text
    assert "held_out 0.480 vs heuristic 0.500" in text and "round 0 in" in text and "gate not met" in text
    assert fk.w.check() == []  # once


def test_main_prints_progress_and_exits_on_finish():
    with tempfile.TemporaryDirectory() as root:
        fk = Fake(root)
        lines, steps = [], iter([lambda: fk.round("score-s0", 1), lambda: fk.sweep("sweep finished: table runs/sweep-x.md")])

        def sleep(_):
            next(steps)()
        code = sweep_watch.main(["--root", root, "--poll", "0"], out=lambda s, flush=False: lines.append(s),
                                sleep=sleep, watcher=fk.w)
        assert code == 0
        assert any("progress: score-s0 round 1" in s for s in lines)
        assert "finished: sweep finished: table runs/sweep-x.md" in lines[-1]


@with_fake
def test_crash_exits(fk):
    fk.row("score-s1", "Traceback (most recent call last):\nMemoryError")
    fk.sweep("score-s1: exited 1; starting no new rows")
    ev = fk.w.check()
    assert kinds(ev) == ["problem"] and "score-s1: crash (exit 1)" in ev[0][1] and "MemoryError" in ev[0][1]


@with_fake
def test_guard_stop_exits(fk):
    fk.sweep("score-s0: exited 3; starting no new rows")
    ev = fk.w.check()
    assert kinds(ev) == ["problem"] and "score-s0: guard stop" in ev[0][1]


@with_fake
def test_sweep_process_gone_exits(fk):
    fk.alive = False
    ev = fk.w.check()
    assert kinds(ev) == ["problem"] and "1234 is gone" in ev[0][1]


@with_fake
def test_silence_exits(fk):
    fk.later(29)
    assert fk.w.check() == []
    fk.later(2)
    ev = fk.w.check()
    assert kinds(ev) == ["problem"] and "no log output for 31 min" in ev[0][1]


@with_fake
def test_run_past_twice_its_projection_exits(fk):
    """Round 1 is projected to end at 30 min: past 60 min without it is a
    problem; once round 1 has finished, round 2's 60 min gives 120."""
    fk.later(25)
    fk.touch()
    fk.later(25)
    fk.touch()
    fk.round("score-s0", 1)
    fk.round("score-s1", 1)
    assert kinds(fk.w.check()) == ["progress", "progress"]
    fk.later(20)
    fk.touch()
    assert fk.w.check() == []  # 70 min, round 2 projected to 60: limit 120
    fk.later(25)
    fk.touch()
    fk.later(26)
    fk.touch()
    ev = fk.w.check()
    assert kinds(ev) == ["problem", "problem"] and "score-s0 past 2x its projection: 121 min" in ev[0][1]


@with_fake
def test_no_projection_no_slow_alarm(fk):
    """A dry run's rows have 0 projected minutes: never "past 2x"."""
    import json as js
    path = os.path.join(fk.logs, "plan.json")
    plan = js.load(open(path))
    for row in plan["rows"].values():
        row["minutes_by_round"] = [0.0] * 3
    js.dump(plan, open(path, "w"))
    fk.later(10)
    fk.touch()
    assert fk.w.check() == []


@with_fake
def test_label_scale_warning_exits(fk):
    fk.row("score-s0", "round 3: WARNING labels off the outcome scale: abc 0.140")
    ev = fk.w.check()
    assert kinds(ev) == ["problem"] and "label-scale warning in score-s0.log" in ev[0][1]


@with_fake
def test_memory_above_limit_exits(fk):
    fk.used = 0.95
    ev = fk.w.check()
    assert kinds(ev) == ["problem"] and "commit 95%" in ev[0][1]


@with_fake
def test_normal_finish_exits_with_table(fk):
    fk.sweep("score-s0: finished")
    fk.sweep("score-s1: finished")
    fk.sweep("sweep finished: table runs/sweep-2026-10-27.md")
    ev = fk.w.check()
    assert ev == [("finished", "sweep finished: table runs/sweep-2026-10-27.md")]


@with_fake
def test_restart_does_not_repeat_old_problems(fk):
    """A watcher started after a label warning and a row's crash reports
    neither again while the sweep's other row runs on."""
    fk.row("score-s0", "round 3: WARNING labels off the outcome scale: abc 0.140")
    fk.sweep("score-s1: exited 1; starting no new rows")
    w = sweep_watch.Watcher(fk.root, clock=lambda: fk.t, mem=lambda: (0.5, 60), alive=lambda pid: True)
    assert w.check() == []


def test_a_rerun_in_the_same_root_ignores_the_old_sweep():
    """sweep.log is appended across sweeps: lines stamped before the
    current sweep's start (plan.json's `started`) are an earlier sweep's,
    so its end line and finished rows don't count."""
    with tempfile.TemporaryDirectory() as root:
        fk = Fake(root)
        fk.sweep("score-s0: finished")
        fk.sweep("sweep stopped: score-s1 crashed (exit 1)")
        fk.later(60)
        path = os.path.join(fk.logs, "plan.json")
        with open(path) as f:
            plan = json.load(f)
        plan["started"] = fk.t.isoformat(timespec="seconds")
        with open(path, "w") as f:
            json.dump(plan, f)
        fk.sweep("started score-s0 (log: x)")
        w = sweep_watch.Watcher(root, clock=lambda: fk.t, mem=lambda: (0.5, 60), alive=lambda pid: True)
        assert w.check() == []
        starts, done, end = w.sweep_log()
        assert end is None and done == set() and starts == {"score-s0": fk.t}


def test_real_memory_and_pid_readers():
    used, phys = sweep_watch.memory()
    assert 0 < used < 1 and 0 < phys <= 100
    assert sweep_watch.pid_alive(os.getpid()) and not sweep_watch.pid_alive(4_000_000)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(len(tests), "passed")
