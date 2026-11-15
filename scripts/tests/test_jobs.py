"""Tests for the job queue (scripts/jobs.py, docs/specs/job-queue.md).
Run with `python scripts/tests/test_jobs.py` (plain asserts; every
`test_*` function runs) or with pytest."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jobs  # noqa: E402

PY = sys.executable


class FakeProc:
    def __init__(self, pid, code=None):
        self.pid, self.code = pid, code

    def poll(self):
        return self.code


class Env:
    """A temp queue with a runner whose idle, memory, clock, liveness,
    start and kill are injected."""

    def __init__(self, idle=16.0, free=8.0, budget=14, total=16.0):
        self.root = tempfile.mkdtemp(prefix="jobs-test-")
        self.q = jobs.Queue(self.root)
        self.t, self.idle_v, self.free_v, self.total_v = 1_000_000.0, idle, free, total
        self.mem_v = 0.0
        self.live, self.started, self.next_pid, self.killed = set(), [], 50_000, []
        self.r = jobs.Runner(self.q, 2, budget, idle=lambda: self.idle_v, free=lambda: self.free_v,
                             total=lambda: self.total_v, clock=lambda: self.t, alive=lambda pid: pid in self.live,
                             start=self._start, kill=self._kill, mem=lambda job: self.mem_v)

    def _start(self, job):
        self.next_pid += 1
        p = FakeProc(self.next_pid)
        self.live.add(p.pid)
        self.started.append(job["id"])
        return p

    def _kill(self, job, handle):
        self.killed.append(job["id"])
        self.live.discard(job["pid"])
        p = self.r.procs.get(job["id"])
        if p is not None:
            p.code = 1

    def add(self, threads=4, heavy=True, mem_gb=1.0, **kw):
        log = os.path.join(self.root, "logs", f"{len(os.listdir(os.path.join(self.root, 'pending')))}.log")
        return self.q.add([PY, "x.py"], threads, heavy=heavy, mem_gb=mem_gb, log=log, **kw)

    def ids(self, state):
        return [j["id"] for j in self.q.jobs(state)]

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


def test_add_orders():
    e = Env()
    try:
        a, b, c = e.add(), e.add(), e.add()
        assert [a[:4], b[:4], c[:4]] == ["0001", "0002", "0003"] and a.endswith("-x")
        assert e.ids("pending") == [a, b, c]
        lines = []
        jobs.status(e.q, out=lines.append)
        assert lines.index("pending:") < next(i for i, l in enumerate(lines) if a in l)
        for bad in ("python x.py", [], [1]):
            try:
                e.q.add(bad, 4)
                raise AssertionError("accepted a bad cmd")
            except ValueError:
                pass
    finally:
        e.close()


def test_cancel():
    e = Env()
    try:
        a, b = e.add(), e.add()
        assert e.q.cancel(a) and not e.q.cancel("9999-none")
        assert e.ids("pending") == [b] and e.q.jobs("done")[0]["status"] == "cancelled"
        assert e.add()[:4] == "0003"  # numbers count done jobs too
    finally:
        e.close()


def test_slot_rules():
    e = Env()
    try:
        h1, h2, h3 = e.add(4), e.add(4), e.add(4)
        e.r.step()
        e.r.step()
        assert e.started == [h1, h2]  # one start per poll
        behind = e.add(1, heavy=False)
        e.r.step()
        assert e.started == [h1, h2]  # two heavy slots full; h3 blocks the light job behind it
        e.q.cancel(h3)
        e.q.cancel(behind)
        light = e.add(4, heavy=False)
        e.r.step()
        assert e.started[-1] == light  # light ignores heavy slots, 12 of 14 threads used
        wide = e.add(4, heavy=False)
        e.r.step()
        assert wide not in e.started  # 16 > budget 14
        e.q.cancel(wide)
        # idle and memory gates on a fresh env
        f = Env(idle=3.0, free=8.0)
        j = f.add(4)
        f.r.step()
        assert f.started == []
        f.idle_v = 4.0
        f.free_v = 1.5  # needs mem_gb 1 + 1 headroom
        f.r.step()
        assert f.started == []
        f.free_v = 2.0
        f.r.step()
        assert f.started == [j]
        f.close()
    finally:
        e.close()


def test_never_fits():
    e = Env()
    try:
        big, small = e.add(20), e.add(2)
        e.r.step()
        done = e.q.jobs("done")
        assert [j["id"] for j in done] == [big] and done[0]["status"] == "failed" and "budget" in done[0]["reason"]
        e.r.step()
        assert e.started == [small]
    finally:
        e.close()


def test_reap():
    e = Env()
    try:
        a, b = e.add(2), e.add(2)
        e.r.step()
        e.r.step()
        e.r.procs[a].code, e.r.procs[b].code = 0, 3
        lines = e.r.step()
        done = {j["id"]: j for j in e.q.jobs("done")}
        assert done[a]["status"] == "ok" and done[a]["exit_code"] == 0
        assert done[b]["status"] == "failed" and done[b]["exit_code"] == 3
        assert e.ids("running") == [] and len(lines) == 2
    finally:
        e.close()


def test_stall_flag():
    e = Env()
    try:
        a = e.add(2, silence_min=30)
        e.r.step()
        log = e.q.jobs("running")[0]["log"]
        os.makedirs(os.path.dirname(log), exist_ok=True)
        open(log, "w").close()
        os.utime(log, (e.t, e.t))
        e.t += 29 * 60
        assert e.r.step() == []
        e.t += 2 * 60
        lines = e.r.step()
        assert len(lines) == 1 and " stalled " + a in lines[0]
        assert e.r.step() == []  # flagged once
        os.utime(log, (e.t, e.t))
        lines = e.r.step()
        assert len(lines) == 1 and " resumed " + a in lines[0] and "stalled_at" not in e.q.jobs("running")[0]
    finally:
        e.close()


def test_restart_adopts():
    e = Env()
    try:
        a, b = e.add(2), e.add(2)
        e.r.step()
        e.r.step()
        pa, pb = e.r.procs[a].pid, e.r.procs[b].pid
        e.live.discard(pb)
        r2 = jobs.Runner(e.q, idle=lambda: 16.0, free=lambda: 8.0, clock=lambda: e.t, alive=lambda p: p in e.live)
        assert r2.claim()
        assert e.ids("running") == [a] and e.q.jobs("done")[0]["status"] == "lost"
        e.live.discard(pa)
        r2.step()
        assert e.ids("running") == []
        done = {j["id"]: j for j in e.q.jobs("done")}
        assert done[a]["status"] == "ended-unknown" and done[a]["exit_code"] is None  # not passed off as ok
        # a second runner refuses while the first's pid lives
        with open(os.path.join(e.root, "runner.pid"), "w") as f:
            f.write("777")
        e.live.add(777)
        assert not jobs.Runner(e.q, alive=lambda p: p in e.live).claim()
        e.live.discard(777)
        assert jobs.Runner(e.q, alive=lambda p: p in e.live).claim()
    finally:
        e.close()


def test_memory_reservation():
    """A job starts only if the running jobs' mem_gb plus its own fit total
    memory minus the headroom, and the live free reading covers it."""
    e = Env(free=14.0, total=16.0)
    try:
        a, b = e.add(2, mem_gb=8), e.add(2, mem_gb=7.5)
        e.r.step()
        e.r.step()
        assert e.started == [a]  # 8 + 7.5 > 16 - 1, though 14 GB looks free now
        e.r.procs[a].code = 0
        e.r.step()
        assert e.started == [a, b]
        c = e.add(1, mem_gb=1)
        e.free_v = 1.5  # the reservation fits (7.5 + 1 <= 15) but live memory doesn't
        e.r.step()
        assert e.started == [a, b]
        e.free_v = 2.0
        e.r.step()
        assert e.started == [a, b, c]
    finally:
        e.close()


def test_lone_job_takes_commit_headroom():
    """With none of the runner's jobs running, a job needs only commit
    headroom (it may page); beside a running job it needs free memory."""
    e = Env(free=3.0, total=16.0)
    try:
        commit = [6.0]
        e.r.commit = lambda: commit[0]
        a = e.add(2, mem_gb=6)
        e.r.step()
        assert e.started == []  # 6 + 1 > 6 GB of commit headroom
        commit[0] = 14.0
        e.r.step()
        assert e.started == [a]  # 3 GB free RAM, but it runs alone
        b = e.add(2, mem_gb=1)
        e.free_v = 1.5
        e.r.step()
        assert e.started == [a]  # b: 1 + 1 fits commit, not beside a: free RAM rules
        e.free_v = 2.0
        e.r.step()
        assert e.started == [a, b]
    finally:
        e.close()
    assert jobs.commit_gb(__import__("types").SimpleNamespace(ullAvailPageFile=5 * 2**30)) == 5.0


def test_free_takes_commit_headroom():
    """free_gb is the smaller of free physical memory and commit headroom."""
    from types import SimpleNamespace as S
    g = 2**30
    assert jobs.free_gb(S(ullAvailPhys=8 * g, ullAvailPageFile=3 * g)) == 3.0
    assert jobs.free_gb(S(ullAvailPhys=2 * g, ullAvailPageFile=9 * g)) == 2.0
    assert jobs.total_gb(S(ullTotalPhys=16 * g)) == 16.0
    assert 0 < jobs.free_gb() < jobs.total_gb() < 1024  # real readings come back sane


def test_memory_never_fits():
    """A head job needing more than the machine has is refused, not left
    blocking the queue."""
    e = Env(total=16.0)
    try:
        big, small = e.add(2, mem_gb=15.5), e.add(2)
        e.r.step()
        done = e.q.jobs("done")
        assert [j["id"] for j in done] == [big] and "mem_gb" in done[0]["reason"], done
        e.r.step()
        assert e.started == [small]
    finally:
        e.close()


def test_id_from_file_name():
    """A hand-renamed pending file with a stale id field starts once and
    leaves pending."""
    e = Env()
    try:
        a = e.add(2)
        os.rename(e.q.path("pending", a), e.q.path("pending", "0007-renamed"))
        e.r.step()
        e.r.step()
        assert e.started == ["0007-renamed"] and e.ids("pending") == [] and e.ids("running") == ["0007-renamed"]
    finally:
        e.close()


def test_malformed_job_refused():
    """A pending job missing a field is refused; the runner and the queue
    behind it carry on."""
    e = Env()
    try:
        jobs.write_json(e.q.path("pending", "0001-bad"), {"id": "0001-bad", "cmd": [PY, "x.py"]})  # no threads
        good = e.add(2)
        lines = e.r.step()
        done = e.q.jobs("done")
        assert [j["id"] for j in done] == ["0001-bad"] and "malformed" in done[0]["reason"], done
        assert " refused 0001-bad" in lines[0]
        e.r.step()
        assert e.started == [good]
    finally:
        e.close()
    root = tempfile.mkdtemp(prefix="jobs-test-")  # no `log`: the real spawn reads it
    try:
        q = jobs.Queue(root)
        jobs.write_json(q.path("pending", "0001-nolog"), {"cmd": [PY, "-c", "pass"], "threads": 1, "heavy": False})
        r = jobs.Runner(q, idle=lambda: 16.0, free=lambda: 8.0, total=lambda: 16.0)
        lines = r.step()
        assert any(" refused 0001-nolog malformed job: KeyError('log')" in l for l in lines), lines
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_suspect_flag():
    """A crash-looking line in a running job's log tail is flagged once."""
    e = Env()
    try:
        a = e.add(2)
        e.r.step()
        log = e.q.jobs("running")[0]["log"]
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "w") as f:
            f.write("epoch 1\n")
        assert e.r.step() == []
        with open(log, "a") as f:
            f.write("concurrent.futures.process.BrokenProcessPool: A process in the pool was terminated\n")
        lines = e.r.step()
        assert len(lines) == 1 and " suspect " + a in lines[0] and "BrokenProcessPool" in lines[0]
        assert e.r.step() == []  # flagged once
        assert "suspect_at" in e.q.jobs("running")[0]
    finally:
        e.close()


def test_kill_request():
    """`kill` asks the runner to end a running job (its own or adopted); it
    moves to done as killed with the reason and the log's last lines."""
    e = Env()
    try:
        a, b = e.add(2), e.add(2)
        e.r.step()
        e.r.step()
        log = e.q.jobs("running")[0]["log"]
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "w") as f:
            f.write("line 1\nlast words\n")
        assert e.q.kill(a, "hung") and not e.q.kill("9999-none")
        assert jobs.main(["--root", e.root, "kill", "9999-none"]) == 1
        e.r.step()  # reads the request and sends the kill
        assert e.killed == [a]
        lines = e.r.step()
        done = {j["id"]: j for j in e.q.jobs("done")}
        assert done[a]["status"] == "killed" and done[a]["reason"] == "hung" and "last words" in done[a]["tail"]
        assert any(" killed " + a in l for l in lines)
        assert not os.path.exists(e.q.kill_path(a))
        # an adopted job (no Popen) is killed through its pid
        r2 = jobs.Runner(e.q, idle=lambda: 16.0, free=lambda: 8.0, total=lambda: 16.0, clock=lambda: e.t,
                         alive=lambda p: p in e.live, kill=e._kill)
        e.r = r2
        assert r2.claim() and e.ids("running") == [b]
        assert jobs.main(["--root", e.root, "kill", b, "--reason", "stuck"]) == 0
        r2.step()
        r2.step()
        done = {j["id"]: j for j in e.q.jobs("done")}
        assert done[b]["status"] == "killed" and done[b]["reason"] == "stuck" and e.ids("running") == []
    finally:
        e.close()


GRANDCHILD = ("import subprocess, sys, time\n"
              "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])\n"
              "print('grandchild', g.pid, flush=True)\n")


def _real_runner(root, script):
    """A real runner with one real job running `script`; returns the queue,
    runner, job id and the grandchild's pid the script printed."""
    q = jobs.Queue(root)
    log = os.path.join(root, "g.log")
    jid = q.add([PY, "-c", script], 1, heavy=False, log=log)
    r = jobs.Runner(q, idle=lambda: 16.0, free=lambda: 8.0, total=lambda: 16.0)
    assert r.claim()
    r.step()
    assert [j["id"] for j in q.jobs("running")] == [jid]
    for _ in range(200):
        with open(log) as f:
            m = [l for l in f if l.startswith("grandchild ")]
        if m:
            return q, r, jid, int(m[0].split()[1])
        time.sleep(0.05)
    raise AssertionError("the grandchild never started")


def _kill_and_reap(q, r, jid):
    assert q.kill(jid, "test")
    for _ in range(100):
        r.step()
        if q.jobs("done"):
            return q.jobs("done")[0]
        time.sleep(0.1)
    raise AssertionError("the killed job never left running")


def test_real_kill_tree():
    """A real job's whole tree, its child included, dies on kill; the slot
    frees."""
    root = tempfile.mkdtemp(prefix="jobs-test-")
    g = None
    try:
        q, r, jid, g = _real_runner(root, GRANDCHILD + "time.sleep(600)\n")
        pid = q.jobs("running")[0]["pid"]
        assert r.procs[jid].job, "the job wasn't put in a Job Object"
        d = _kill_and_reap(q, r, jid)
        assert d["status"] == "killed" and d["reason"] == "test"
        assert not jobs.pid_alive(pid) and not jobs.pid_alive(g)
        assert q.jobs("running") == [] and r.procs == {}
    finally:
        if g and jobs.pid_alive(g):
            subprocess.run(["taskkill", "/PID", str(g), "/T", "/F"], capture_output=True)
        shutil.rmtree(root, ignore_errors=True)


def test_real_tree_outlives_parent():
    """A job whose top process exited while its child still runs keeps its
    slot until the tree is gone."""
    root = tempfile.mkdtemp(prefix="jobs-test-")
    g = None
    try:
        q, r, jid, g = _real_runner(root, GRANDCHILD)
        for _ in range(100):
            if r.procs[jid].poll() is not None:
                break
            time.sleep(0.05)
        assert r.procs[jid].poll() == 0
        for _ in range(3):
            assert r.step() == []
        assert [j["id"] for j in q.jobs("running")] == [jid] and jobs.pid_alive(g)
        d = _kill_and_reap(q, r, jid)
        assert d["status"] == "killed" and not jobs.pid_alive(g)
    finally:
        if g and jobs.pid_alive(g):
            subprocess.run(["taskkill", "/PID", str(g), "/T", "/F"], capture_output=True)
        shutil.rmtree(root, ignore_errors=True)


def test_wait():
    e = Env()
    try:
        for event, code in (("ok", 0), ("stalled", 1), ("suspect", 1), ("killed", 1), ("ended-unknown", 1)):
            got = []

            def later():
                time.sleep(0.3)
                e.q.event("start", "0001-x")
                e.q.event(event, "0001-x")

            th = threading.Thread(target=later)
            th.start()
            rc = jobs.wait(e.q, poll=0.05, out=lambda s, flush=False: got.append(s))
            th.join()
            assert rc == code and f" {event} 0001-x" in got[0]
    finally:
        e.close()


def test_real_job_runs():
    """A real tiny job through spawn: thread env set, log written, exit code reaped."""
    root = tempfile.mkdtemp(prefix="jobs-test-")
    try:
        q = jobs.Queue(root)
        log = os.path.join(root, "a.log")
        q.add([PY, "-c", "import os,sys; print(os.environ['OMP_NUM_THREADS']); sys.exit(3)"], 3, heavy=False,
              log=log)
        r = jobs.Runner(q, idle=lambda: 16.0, free=lambda: 8.0)
        assert r.claim()
        r.step()
        for _ in range(100):
            if r.step():
                break
            time.sleep(0.1)
        d = q.jobs("done")[0]
        assert d["status"] == "failed" and d["exit_code"] == 3
        with open(log) as f:
            assert f.read().strip() == "3"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_start_error_fails_job():
    """A job whose program or cwd is missing fails; the queue moves on.
    A relative program is resolved against the job's cwd, with `.exe`
    added when it was left off."""
    root = tempfile.mkdtemp(prefix="jobs-test-")
    try:
        q = jobs.Queue(root)
        bad = q.add([PY, "-c", "pass"], 1, heavy=False, cwd=os.path.join(root, "no-such-dir"),
                    log=os.path.join(root, "bad.log"))
        rel = q.add([os.path.relpath(PY, jobs.REPO), "-c", "pass"], 1, heavy=False, log=os.path.join(root, "r.log"))
        bare = q.add([os.path.splitext(os.path.relpath(PY, jobs.REPO))[0].replace("\\", "/"), "-c", "pass"], 1, heavy=False,
                     log=os.path.join(root, "b.log"))
        r = jobs.Runner(q, idle=lambda: 16.0, free=lambda: 8.0)
        assert r.claim()
        here = os.getcwd()
        os.chdir(root)  # the live runner's own cwd isn't the repo
        r.step()
        d = q.jobs("done")[0]
        assert d["id"] == bad and d["status"] == "failed" and d["reason"].startswith("start:")
        r.step()
        for _ in range(100):
            if r.step():
                break
            time.sleep(0.1)
        for _ in range(100):
            r.step()
            if bare in {j["id"] for j in q.jobs("done")}:
                break
            time.sleep(0.1)
        done = {j["id"]: j["status"] for j in q.jobs("done")}
        assert done[rel] == "ok" and done[bare] == "ok", done
    finally:
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


def test_move_retries_while_read():
    """A reader holding a job file open briefly doesn't break a move."""
    e = Env()
    try:
        a = e.add(2)
        held = open(e.q.path("pending", a), encoding="utf-8")
        threading.Timer(0.3, held.close).start()
        e.r.step()
        assert e.ids("running") == [a] and e.ids("pending") == []
    finally:
        e.close()


def test_idle_gate():
    """Outside assumption: GetSystemTimes sees a 4-core busy load (runs
    started by hand count). Compared against the idle reading just before,
    so other load on the machine doesn't decide it. Other jobs' load moves
    between readings, so up to three trials; one that sees the load passes."""
    idle = jobs.IdleCores(first=1.0)
    seen = []
    for _ in range(3):
        before = idle()
        busy = [subprocess.Popen([PY, "-c", "import time\nt=time.time()+4\nwhile time.time()<t: pass"]) for _ in range(4)]
        time.sleep(0.5)
        idle()
        time.sleep(2.0)
        during = idle()
        for p in busy:
            p.wait()
        seen.append((before, during))
        if before - during >= 3.0 or during < 1.0:
            return
    raise AssertionError(seen)


def test_child_survives_runner():
    """Outside assumption: a job outlives the runner process that started it."""
    root = tempfile.mkdtemp(prefix="jobs-test-")
    try:
        q = jobs.Queue(root)
        q.add([PY, "-c", "import time; time.sleep(8)"], 1, heavy=False, log=os.path.join(root, "c.log"))
        code = ("import sys; sys.path.insert(0, %r); import jobs; q = jobs.Queue(%r); "
                "r = jobs.Runner(q, idle=lambda: 16.0, free=lambda: 8.0); r.claim(); r.step()") % (os.path.dirname(jobs.__file__), root)
        subprocess.run([PY, "-c", code], check=True, timeout=60)
        pid = q.jobs("running")[0]["pid"]
        time.sleep(1.0)
        assert jobs.pid_alive(pid), "the job died with its runner"
    finally:
        time.sleep(8)
        shutil.rmtree(root, ignore_errors=True)


def test_peak_memory():
    e = Env()
    try:
        a = e.add()
        e.r.step()
        for gb, want in ((1.234, 1.23), (3.0, 3.0), (0.5, 3.0), (2.9, 3.0)):
            e.mem_v = gb
            e.r.step()
            assert e.q.jobs("running")[0]["peak_gb"] == want
        lines = []
        jobs.status(e.q, out=lines.append)
        assert any(a in l and "peak 3 GB" in l for l in lines)
        e.live.clear()
        e.r.procs[a].code = 0
        e.r.step()
        done = e.q.jobs("done")[0]
        assert done["status"] == "ok" and done["peak_gb"] == 3.0
        lines = []
        jobs.status(e.q, out=lines.append)
        assert any(a in l and "peak 3 GB" in l for l in lines[lines.index("done (last 10):"):])
    finally:
        e.close()


def test_real_tree_mem():
    """tree_mem_gb sums a parent and its child: the child holds ~200 MB."""
    code = ("import subprocess,sys,time;"
            "c=subprocess.Popen([sys.executable,'-c','b=bytearray(200*2**20);import time;time.sleep(30)']);"
            "time.sleep(30)")
    p = subprocess.Popen([PY, "-c", code])
    try:
        gb = 0.0
        for _ in range(100):
            gb = jobs.tree_mem_gb({"pid": p.pid})
            if gb > 0.2:
                break
            time.sleep(0.1)
        assert 0.2 < gb < 2.0, gb
        assert jobs.tree_mem_gb({"pid": 0}) == 0.0
    finally:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)


def test_backfill():
    """A head that waits for memory only lets a later job of its lane that
    fits start (after RESERVE_MIN only one that fits alongside it); a head
    waiting for a slot doesn't."""
    e = Env(free=6.0, total=16.0)
    try:
        a = e.add(3, mem_gb=4)
        e.r.step()
        assert e.started == [a]
        e.free_v = 3.0
        big, small, small2 = e.add(3, mem_gb=5), e.add(3, mem_gb=1), e.add(3, mem_gb=1)
        e.r.step()
        assert e.started == [a, small]  # big waits for memory; small fits
        assert e.q.jobs("pending")[0]["wait_since"] == e.t
        with open(e.q.log_path) as f:
            assert f" backfill {small} ahead of {big}" in f.read()
        e.r.step()
        assert e.started == [a, small]  # two heavy slots taken: nobody jumps a slot wait
        e.r.procs[small].code = 0
        e.t += (jobs.RESERVE_MIN + 1) * 60
        e.r.step()
        assert e.started == [a, small]  # big holds the reservation: small2 would take its slot
        e.free_v = 7.0
        e.r.step()
        assert e.started == [a, small, big] and "wait_since" not in e.q.jobs("running")[-1]
        assert e.ids("pending") == [small2]
    finally:
        e.close()


def _until(fn, tries=200, pause=0.1):
    """Call `fn` until it returns something truthy; return that."""
    for _ in range(tries):
        got = fn()
        if got:
            return got
        time.sleep(pause)
    raise AssertionError("timed out")


def test_exit_survives_restart():
    """A job runs through the wrapper; a new runner adopts it and still ends
    it ok (0) or failed (3) from the exit file. A stale exit file is deleted
    when the job starts, and a job that ended while no runner watched ends
    with its code too."""
    root = tempfile.mkdtemp(prefix="jobs-test-")
    try:
        q = jobs.Queue(root)
        a = q.add([PY, "-c", "import time; time.sleep(2)"], 1, heavy=False, log=os.path.join(root, "a.log"))
        b = q.add([PY, "-c", "import sys, time; time.sleep(2); sys.exit(3)"], 1, heavy=False,
                  log=os.path.join(root, "b.log"))
        with open(q.exit_path(a), "w") as f:
            f.write("5")  # left by an earlier job of this id
        r = jobs.Runner(q, idle=lambda: 16.0, free=lambda: 8.0, total=lambda: 16.0)
        assert r.claim() and os.path.isfile(r.wrapper())
        r.step()
        assert not os.path.exists(q.exit_path(a))
        r.step()
        assert [j["id"] for j in q.jobs("running")] == [a, b]
        r2 = jobs.Runner(q, idle=lambda: 16.0, free=lambda: 8.0, total=lambda: 16.0)  # the restart
        assert r2.claim() and [j["id"] for j in q.jobs("running")] == [a, b]
        _until(lambda: (r2.step(), len(q.jobs("done")) == 2)[1])
        done = {j["id"]: j for j in q.jobs("done")}
        assert (done[a]["status"], done[a]["exit_code"]) == ("ok", 0), done[a]
        assert (done[b]["status"], done[b]["exit_code"]) == ("failed", 3), done[b]
        assert not os.listdir(os.path.join(root, "running"))  # exit files go with the job
    finally:
        shutil.rmtree(root, ignore_errors=True)
    e = Env()
    try:
        a = e.add(2)
        e.r.step()
        e.live.clear()  # ended while the runner was down
        with open(e.q.exit_path(a), "w") as f:
            f.write("0")
        assert jobs.Runner(e.q, alive=lambda p: p in e.live).claim()
        d = e.q.jobs("done")[0]
        assert (d["status"], d["exit_code"]) == ("ok", 0) and not os.path.exists(e.q.exit_path(a))
    finally:
        e.close()


def test_wrapper_frozen():
    """Editing jobs.py to a syntax error while the runner runs doesn't stop
    a job from starting and ending ok: jobs start through the wrapper the
    runner wrote at its start."""
    root = tempfile.mkdtemp(prefix="jobs-test-")
    code = os.path.join(root, "scripts")
    os.makedirs(code)
    here = os.path.dirname(jobs.__file__)
    for name in ("jobs.py", "sweep_watch.py"):
        shutil.copy(os.path.join(here, name), code)
    q = jobs.Queue(os.path.join(root, "jobs"))
    runner = subprocess.Popen([PY, os.path.join(code, "jobs.py"), "--root", q.root, "run", "--poll", "0.2"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _until(lambda: [n for n in os.listdir(q.root) if n.startswith("runner-")])
        with open(os.path.join(code, "jobs.py"), "w") as f:
            f.write("def broken(:\n")
        jid = q.add([PY, "-c", "print('hi')"], 1, heavy=False, log=os.path.join(root, "j.log"))
        d = _until(lambda: q.jobs("done"), tries=300)[0]
        assert d["id"] == jid and d["status"] == "ok", d
    finally:
        subprocess.run(["taskkill", "/PID", str(runner.pid), "/T", "/F"], capture_output=True)
        time.sleep(0.5)
        shutil.rmtree(root, ignore_errors=True)


def test_lanes_json_bad():
    """A corrupt lanes.json keeps the last good shares and logs lanes-bad
    once; the runner keeps stepping and starting jobs."""
    e = Env()
    try:
        path = os.path.join(e.root, "lanes.json")
        assert e.r.step() == [] and e.r.shares == jobs.DEFAULT_SHARES  # no file: the defaults
        with open(path, "w") as f:
            json.dump({"depth": 5, "new": 2}, f)
        e.r.step()
        assert e.r.shares["depth"] == 5 and e.r.shares["new"] == 2 and e.r.shares["run"] == 30
        with open(path, "w") as f:
            f.write("{not json")
        lines = e.r.step()
        assert len(lines) == 1 and " lanes-bad " in lines[0]
        with open(path, "w") as f:
            json.dump({"depth": "x"}, f)
        a = e.add(2)
        lines = e.r.step()
        assert e.started == [a] and not any("lanes-bad" in l for l in lines) and e.r.shares["depth"] == 5
        with open(e.q.log_path) as f:
            assert f.read().count(" lanes-bad ") == 1
        with open(path, "w") as f:
            json.dump({"depth": 7}, f)
        e.r.step()
        assert e.r.shares["depth"] == 7 and "new" not in e.r.shares
    finally:
        e.close()


def test_old_job_files():
    """Pending and running files written by the runner before lanes still
    run: a pending job starts (lane main, no conditions), and an adopted
    running job with no exit file ends ended-unknown as before."""
    e = Env()
    try:
        old = {"cmd": [PY, "x.py"], "cwd": jobs.REPO, "threads": 6, "heavy": True, "mem_gb": 6.0,
               "log": os.path.join(e.root, "old.log"), "silence_min": 40.0, "estimate_min": 110.0, "note": "",
               "added": "2026-11-01T15:48:38+05:00"}
        jobs.write_json(e.q.path("pending", "0059l8b-bash"), dict(old, id="0059l8b-bash", mem_wait_since=e.t - 99))
        jobs.write_json(e.q.path("running", "0058-run"), dict(old, id="0058-run", pid=777, started="x",
                                                               started_ts=e.t - 60, peak_gb=3.0))
        e.live.add(777)
        assert e.r.claim()
        e.r.step()
        assert e.started == ["0059l8b-bash"] and set(e.ids("running")) == {"0059l8b-bash", "0058-run"}
        e.live.discard(777)
        e.r.step()
        d = e.q.jobs("done")[0]
        assert d["id"] == "0058-run" and d["status"] == "ended-unknown" and d["exit_code"] is None
    finally:
        e.close()


def _shares(e, shares):
    with open(os.path.join(e.root, "lanes.json"), "w") as f:
        json.dump(shares, f)


def test_lane_choice():
    """Lane heads start in order of lowest use / share (ties by lane name);
    a job's use is the larger of its thread and memory fractions."""
    e = Env()
    try:
        _shares(e, {"a": 3, "b": 1})
        a = [e.add(1, heavy=False, mem_gb=0.1, lane="a") for _ in range(4)]
        b = [e.add(1, heavy=False, mem_gb=0.1, lane="b") for _ in range(2)]
        for _ in range(6):
            e.r.step()
        assert e.started == [a[0], b[0], a[1], a[2], a[3], b[1]], e.started
        with open(e.q.log_path) as f:
            assert f.read().count(" choice ") == 6
        lines = []
        jobs.status(e.q, out=lines.append)
        assert any(l.split()[:1] == ["a"] and "share 3" in l for l in lines), lines
        assert any(a[0] in l and "lane a" in l for l in lines)
    finally:
        e.close()
    e = Env()
    try:
        _shares(e, {"a": 1, "b": 1})
        t4 = e.add(4, heavy=False, mem_gb=1, lane="a")  # use 4/14 = 0.29 by threads
        e.r.step()
        m6 = e.add(1, heavy=False, mem_gb=6, lane="b")  # use 6/15 = 0.4 by memory, 1/14 by threads
        e.r.step()
        assert e.started == [t4, m6]
        b2, a2 = e.add(1, heavy=False, mem_gb=0.5, lane="b"), e.add(1, heavy=False, mem_gb=0.5, lane="a")
        e.r.step()
        assert e.started[-1] == a2  # threads alone would have picked lane b
    finally:
        e.close()


def test_head_reserved_threads():
    """The l8b case, waiting for threads: once the top lane head has waited
    RESERVE_MIN, a job that would take the threads it needs doesn't start,
    one that fits alongside it does, and when room frees the head starts."""
    e = Env()
    try:
        r1 = e.add(4, heavy=False, lane="r")
        e.r.step()
        e.idle_v = 5.0  # load from outside: the head (6 threads) waits
        head = e.add(6, lane="a")
        e.r.step()
        assert e.started == [r1] and "reserved_at" not in e.q.jobs("pending")[0]
        e.t += (jobs.RESERVE_MIN + 1) * 60
        big, small = e.add(5, heavy=False, lane="x"), e.add(3, heavy=False, lane="y")
        lines = e.r.step()
        assert any(" reserve " + head in l for l in lines), lines
        assert e.started == [r1, small]  # 4 + 5 + 6 > 14; 4 + 3 + 6 fits
        e.r.step()
        assert e.started == [r1, small]
        e.q.kill(r1, "room for the head")
        e.r.step()
        e.idle_v = 16.0
        e.r.step()
        assert e.started == [r1, small, head] and e.ids("pending") == [big]
    finally:
        e.close()


def test_head_reserved_memory():
    """The l8b case, waiting for memory: same rule on reserved memory, and
    `first` gives a pending job the reservation at once."""
    e = Env(free=14.0)
    try:
        r1, r2 = e.add(3, mem_gb=4, lane="r"), e.add(2, heavy=False, mem_gb=4, lane="s")
        e.r.step()
        e.r.step()
        e.free_v = 3.0  # another program took memory: the head (6 GB) waits
        head = e.add(6, mem_gb=6, lane="a")
        e.r.step()
        e.t += (jobs.RESERVE_MIN + 1) * 60
        big, small = e.add(2, heavy=False, mem_gb=2, lane="x"), e.add(1, heavy=False, mem_gb=1, lane="y")
        e.r.step()
        assert e.started == [r1, r2, small]  # 8 + 2 + 6 > 15; 8 + 1 + 6 fits
        e.q.kill(r1, "room")
        e.r.step()
        e.free_v = 8.0
        e.r.step()
        assert e.started[-1] == head and e.ids("pending") == [big]
    finally:
        e.close()
    e = Env(free=3.0)
    try:
        r1 = e.add(2, heavy=False, mem_gb=4, lane="run")
        e.free_v = 8.0
        e.r.step()
        e.free_v = 3.0
        a, b = e.add(2, mem_gb=7), e.add(2, mem_gb=1)
        assert e.q.first(b) and not e.q.first("9999-none")
        pend = {j["id"]: j for j in e.q.jobs("pending")}
        assert "reserved_at" in pend[b] and "reserved_at" not in pend[a]
        e.r.step()
        assert e.started[-1] == b  # first in its lane
        c = e.add(2, heavy=False, mem_gb=4, lane="depth")
        assert e.q.first(a)
        e.free_v = 6.0  # enough for c (4 + 1), not for a (7 + 1)
        e.r.step()  # a holds the reservation at once: 5 + 4 + 7 > 15
        assert e.started[-1] == b and e.ids("pending") == [a, c]
    finally:
        e.close()


def test_peak_reserved():
    """A running job reserves the larger of mem_gb and its measured peak;
    `add` warns about a mem_gb below the last peak of the same script."""
    e = Env(free=12.0)
    try:
        js = [e.add(2, mem_gb=3) for _ in range(3)]
        e.mem_v = 4.0
        for _ in range(3):
            e.r.step()
        assert e.started == js
        d = e.add(2, mem_gb=3.5)  # 9 + 3.5 fits 15, 12 + 3.5 doesn't
        e.r.step()
        assert all(j["peak_gb"] == 4.0 for j in e.q.jobs("running"))
        assert e.started == js and e.ids("pending") == [d]
        e.r.procs[js[0]].code = 0
        e.live.discard(e.r.procs[js[0]].pid)
        e.r.step()
        e.r.step()
        assert e.started[-1] == d
        e.add(2, mem_gb=3)
        assert e.q.jobs("pending")[0]["mem_gb_low"] == 4.0
        assert jobs.main(["--root", e.root, "add", "--unpinned", "--threads", "1", "--mem-gb", "5", "--", PY, "x.py"]) == 0
        assert "mem_gb_low" not in e.q.jobs("pending")[-1]
    finally:
        e.close()


def test_half_slot():
    """A heavy job with 2 threads or fewer takes half a slot."""
    e = Env()
    try:
        h1, h2, h3 = e.add(2), e.add(2), e.add(4)
        for _ in range(3):
            e.r.step()
        assert e.started == [h1, h2, h3]
        h4 = e.add(2)
        e.r.step()
        assert e.started == [h1, h2, h3]  # 0.5 + 0.5 + 1 + 0.5 > 2
    finally:
        e.close()


def _end(e, jid, code):
    """End a running fake job with `code` (the runner reaps it next poll)."""
    e.r.procs[jid].code = code
    e.live.discard(e.r.procs[jid].pid)


def test_conditions():
    """if_passed waits, starts on pass, parks on fail; after starts on any
    end; parking cascades; a missing or parked dependency parks; a parked or
    waiting job doesn't block others; unpark; set; on_fail cancel."""
    e = Env()
    try:
        a = e.add(2, heavy=False)
        b = e.add(2, heavy=False, if_passed=[a])
        x = e.add(2, heavy=False)
        e.r.step()
        e.r.step()
        assert e.started == [a, x]  # b waits for a without blocking x
        _end(e, a, 0)
        e.r.step()
        assert e.started == [a, x, b]
        # a failure parks, cascades, and leaves `after` free to start
        f = e.add(2, heavy=False)
        e.r.step()
        g = e.add(2, heavy=False, if_passed=[f])
        h = e.add(2, heavy=False, if_passed=[g])
        k = e.add(2, heavy=False, after=[g])
        m = e.add(2, heavy=False, after=[f])
        c = e.add(2, heavy=False, if_passed=[f], on_fail="cancel")
        _end(e, f, 3)
        lines = e.r.step()
        pend = {j["id"]: j for j in e.q.jobs("pending")}
        assert "did not pass" in pend[g]["parked"] and f in pend[g]["parked"]
        assert pend[h]["parked"] == f"{g} is parked" and pend[k]["parked"] == f"{g} is parked"  # same poll
        assert sum(" parked " in l for l in lines) == 3 and e.started[-1] == m
        assert {j["id"]: j for j in e.q.jobs("done")}[c]["status"] == "cancelled"
        # a parked job doesn't block a later one in its lane
        n = e.add(2, heavy=False)
        e.r.step()
        assert e.started[-1] == n
        # unknown ids are refused at add; a hand-made dependency that vanished parks
        try:
            e.add(2, after=["9999-none"])
            raise AssertionError("accepted an unknown id")
        except ValueError:
            pass
        jobs.write_json(e.q.path("pending", "0100-hand"), {"cmd": [PY, "x.py"], "threads": 1, "heavy": False,
                                                          "log": "x", "after": ["9999-gone"]})
        e.r.step()
        assert e.q.find("0100-hand")[1]["parked"] == "9999-gone is in no folder"
        # unpark: re-decided next poll; a verdict by hand lets it run
        assert e.q.unpark(g) and not e.q.unpark(n)
        e.r.step()
        assert "parked" in e.q.find(g)[1]
        assert e.q.set_verdict(f, "pass", "rule read by hand") and e.q.unpark(g)
        e.r.step()
        assert e.started[-1] == g
        # set: adds a condition to a pending job and keeps its id
        p = e.add(2, heavy=False)
        blocker = e.add(2, heavy=False, lane="z")
        assert e.q.set(p, after=[blocker], lane="y")
        try:
            e.q.set(p, if_passed=["9999-none"])
            raise AssertionError("set accepted an unknown id")
        except ValueError:
            pass
        assert e.q.find(p)[0] == "pending" and e.q.find(p)[1]["after"] == [blocker]
        e.r.step()
        assert e.started[-1] == blocker and e.ids("pending").count(p) == 1
        _end(e, blocker, 1)
        e.r.step()
        assert e.started[-1] == p  # `after`: any end
        lines = []
        jobs.status(e.q, out=lines.append)
        assert any(h in l and "PARKED" in l for l in lines)
    finally:
        e.close()


def test_check_process():
    """A check exiting 0 / 1 gives pass / fail without blocking a poll; a
    runner restart during a check restarts it; a CHECK_MIN timeout gives
    fail (timeout); `verdict` sets one by hand."""
    e = Env()
    try:
        a = e.add(2, heavy=False, check=[PY, "check.py"])
        b = e.add(2, heavy=False, if_passed=[a])
        b2 = e.add(2, heavy=False, after=[a])
        e.r.step()
        _end(e, a, 0)
        lines = e.r.step()
        assert e.started == [a, a + ".check"] and any(" check " + a in l for l in lines)
        assert os.path.exists(e.q.check_path(a)) and e.ids("running") == []  # not a job
        e.r.step()
        assert e.started[-1] == a + ".check"  # b and b2 wait for the verdict
        log = e.q.jobs("done")[0]["log"][:-4] + ".check.log"
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(e.q.exit_path(a + ".check"), "w") as f:
            f.write("0")
        e.live.discard(e.next_pid)
        e.r.step()
        assert e.q.find(a)[1]["verdict"] == "pass" and e.started[-1] == b
        assert not os.path.exists(e.q.check_path(a))
        e.r.step()
        assert e.started[-1] == b2
        # the check ends between the runner's reads: still its exit code, not a lost check
        r = e.add(2, heavy=False, check=[PY, "check.py"])
        e.r.step()
        _end(e, r, 0)
        e.r.step()
        pid = e.next_pid

        def ends_now(p):
            if p == pid and p in e.live:
                with open(e.q.exit_path(r + ".check"), "w") as f:
                    f.write("0")
                e.live.discard(p)
            return p in e.live
        e.r.alive = ends_now
        e.r.step()
        e.r.alive = lambda p: p in e.live
        assert e.q.find(r)[1]["verdict"] == "pass", e.q.find(r)[1]
        # fail, with the check's last output line
        c = e.add(2, heavy=False, check=[PY, "check.py"])
        e.r.step()
        _end(e, c, 0)
        e.r.step()
        with open(e.q.find(c)[1]["log"][:-4] + ".check.log", "w") as f:
            f.write("rows 200\nFAIL: clears -0.02\n")
        with open(e.q.exit_path(c + ".check"), "w") as f:
            f.write("1")
        e.r.step()
        d = e.q.find(c)[1]
        assert d["verdict"] == "fail" and "FAIL: clears -0.02" in d["verdict_reason"]
        # a restart during a check restarts it
        k = e.add(2, heavy=False, check=[PY, "check.py"])
        e.r.step()
        _end(e, k, 0)
        e.r.step()
        e.live.discard(e.next_pid)  # the check died with the machine
        n = len(e.started)
        e.r = jobs.Runner(e.q, idle=lambda: 16.0, free=lambda: 8.0, total=lambda: 16.0, clock=lambda: e.t,
                          alive=lambda p: p in e.live, start=e._start, kill=e._kill)
        assert e.r.claim() and e.started[n:] == [k + ".check"]
        # a check never started (an ok job without verdict) starts at claim too
        os.remove(e.q.check_path(k))
        e.r = jobs.Runner(e.q, idle=lambda: 16.0, free=lambda: 8.0, total=lambda: 16.0, clock=lambda: e.t,
                          alive=lambda p: p in e.live, start=e._start, kill=e._kill)
        assert e.r.claim() and e.started[-1] == k + ".check" and len(e.started) == n + 2
        # timeout
        e.t += (jobs.CHECK_MIN + 1) * 60
        lines = e.r.step()
        assert e.q.find(k)[1]["verdict_reason"] == "timeout" and e.killed[-1] == k + ".check"
        # by hand
        assert jobs.main(["--root", e.root, "verdict", k, "pass", "--reason", "read the rows"]) == 0
        assert e.q.find(k)[1]["verdict"] == "pass" and jobs.main(["--root", e.root, "verdict", "9999-x", "pass"]) == 1
    finally:
        e.close()
    root = tempfile.mkdtemp(prefix="jobs-test-")  # the same through real processes and the wrapper
    try:
        q = jobs.Queue(root)
        jid = q.add([PY, "-c", "pass"], 1, heavy=False, log=os.path.join(root, "r.log"),
                    check=[PY, "-c", "import sys; print('rows 9'); print('below the bar'); sys.exit(1)"])
        r = jobs.Runner(q, idle=lambda: 16.0, free=lambda: 8.0, total=lambda: 16.0)
        assert r.claim()
        d = _until(lambda: (r.step(), q.find(jid)[1].get("verdict"))[1] and q.find(jid)[1])
        assert d["verdict"] == "fail" and d["verdict_reason"] == "exit 1: below the bar", d
        assert os.listdir(os.path.join(root, "running")) == []
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_filler():
    """A filler (share 0) starts only when no other lane's job started this
    poll, never into a protected head's room; `add` refuses a long filler
    that isn't resumable."""
    e = Env()
    try:
        f = e.add(1, heavy=False, lane="filler", estimate_min=15)
        m = e.add(2, heavy=False)
        e.r.step()
        assert e.started == [m]  # main's head went first
        e.r.step()
        assert e.started == [m, f]  # nothing else to start
        # a head that waits: a filler may start beside it until the head is protected
        e.idle_v = 5.0
        head = e.add(6, lane="a")
        f2 = e.add(1, heavy=False, lane="filler", resumable=True)
        e.r.step()
        assert e.started[-1] == f2  # the head (6 threads) didn't fit, nothing else started
        e.t += (jobs.RESERVE_MIN + 1) * 60
        f3 = e.add(5, heavy=False, lane="filler", estimate_min=10)  # fits alone; 4 + 5 + 6 > 14
        lines = e.r.step()
        assert any(" reserve " + head in l for l in lines) and e.ids("pending") == [head, f3]
        e.q.cancel(f3)
        f4 = e.add(1, heavy=False, lane="filler", estimate_min=10)  # fits alongside: 4 + 1 + 6 <= 14
        e.r.step()
        assert e.started[-1] == f4
        e.q.cancel(head)
        # a backfill in another lane starts before a filler
        e.idle_v, e.free_v = 16.0, 3.0
        big, small, f5 = e.add(1, mem_gb=5), e.add(1, heavy=False, mem_gb=1), \
            e.add(1, heavy=False, mem_gb=1, lane="filler", estimate_min=5)
        e.r.step()
        assert e.started[-1] == small and e.ids("pending") == [big, f5]
        e.r.step()
        assert e.started[-1] == f5
        for kw in ({}, {"estimate_min": 60}):
            try:
                e.add(1, lane="filler", **kw)
                raise AssertionError(f"accepted a long filler {kw}")
            except ValueError as err:
                assert "resumable" in str(err)
        assert jobs.main(["--root", e.root, "add", "--unpinned", "--threads", "1", "--lane", "filler", "--", PY, "x.py"]) == 1
    finally:
        e.close()


def _sts_dir():
    import importlib.util
    return importlib.util.find_spec("sts").submodule_search_locations[0]


def _wheel_build(snap, pyroot, builds, calls=[]):
    """Stands in for the cargo build: a wheel holding the installed `sts`
    package's bytes (real, importable), with the files pip needs."""
    import zipfile
    calls.append(snap)
    os.makedirs(os.path.join(pyroot, "wheel"))
    whl = os.path.join(pyroot, "wheel", "sts-0.1.0-cp313-cp313-win_amd64.whl")
    d, info = _sts_dir(), "sts-0.1.0.dist-info"
    names = [f"sts/{n}" for n in sorted(os.listdir(d)) if n.endswith((".py", ".pyd"))]
    with zipfile.ZipFile(whl, "w") as z:
        for n in names:
            z.write(os.path.join(d, n[4:]), n)
        z.writestr(f"{info}/METADATA", "Metadata-Version: 2.1\nName: sts\nVersion: 0.1.0\n")
        z.writestr(f"{info}/WHEEL", "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: false\n"
                                    "Tag: cp313-cp313-win_amd64\n")
        z.writestr(f"{info}/RECORD", "".join(f"{n},,\n" for n in names + [f"{info}/METADATA", f"{info}/WHEEL",
                                                                           f"{info}/RECORD"]))


def _git(repo, *args):
    return jobs.git(repo, "-c", "user.name=t", "-c", "user.email=t@t", *args)


def _write(root, files):
    for rel, text in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)


def test_main_checkout_from_worktree():
    """jobs.py run from a lane worktree resolves the main checkout (its queue,
    logs and the data a snapshot links), and the main checkout itself."""
    tmp = tempfile.mkdtemp()
    try:
        repo, builds = _repo(tmp)
        wt = os.path.join(tmp, "wt")
        _git(repo, "worktree", "add", "-q", wt, "-b", "lane/x")
        assert os.path.samefile(jobs.main_checkout(wt), repo)
        assert os.path.samefile(jobs.main_checkout(repo), repo)
        assert jobs.main_checkout(tmp) == tmp  # not a repository: unchanged
        _write(wt, {"scripts/x.py": "print('lane')\n"})
        _git(wt, "commit", "-qam", "lane")
        q = jobs.Queue(os.path.join(tmp, "jobs"), repo, builds, build=_wheel_build, here=wt)
        with open(os.path.join(repo, "scripts", "x.py"), "a") as f:
            f.write("# main's uncommitted edit doesn't block a worktree's pin\n")
        jid = q.add(["python", "scripts/x.py"], 1, pin="HEAD", log=os.path.join(tmp, "a.log"))
        job = json.load(open(q.path("pending", jid), encoding="utf-8"))
        assert job["pin"] == _git(wt, "rev-parse", "HEAD").strip()
        assert os.path.samefile(os.path.join(job["cwd"], "results", "r.txt"), os.path.join(repo, "results", "r.txt"))
        assert os.path.samefile(os.path.join(job["cwd"], ".venv", "v"), os.path.join(repo, ".venv", "v"))
        jobs.unpin_snapshot(job["cwd"], repo)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _repo(tmp, scripts=()):
    """A scratch main checkout: tracked code, the real .gitignore, and
    ignored data in every kind of place a snapshot links."""
    repo = os.path.join(tmp, "main")
    _write(repo, {"scripts/x.py": "print('x')\n", "engine/tests/data/golden.txt": "g\n", "py/Cargo.toml": "",
                  "solvedb/a.rs": "", "configs/c.json": "{}", "scripts/analysis/a.py": "", "data/bench/b.txt": "b", "runs/index.csv": "run\n",
                  "runs/sweep-1.md": "s", "Cargo.toml": "", "Cargo.lock": "", ".cargo/config.toml": ""})
    shutil.copy(os.path.join(jobs.REPO, ".gitignore"), repo)
    for name in scripts:
        shutil.copy(os.path.join(jobs.REPO, "scripts", name), os.path.join(repo, "scripts"))
    jobs.git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    _write(repo, {"results/r.txt": "keep", "db/keep.db": "keep", "cache/c": "keep", "datasets/d": "keep",
                  "models/m": "keep", "logs/l": "keep", ".venv/v": "keep", "scripts/analysis/out/o": "keep",
                  "data/ref/d.txt": "keep", "data/f.npz": "keep", "target/t": "", "scripts/__pycache__/x.pyc": "",
                  "runs/2026-old/model.pt": "keep"})
    return repo, os.path.join(tmp, "builds")


MAIN_DATA = ("results/r.txt", "db/keep.db", "cache/c", "datasets/d", "models/m", "logs/l", ".venv/v",
             "scripts/analysis/out/o", "data/ref/d.txt", "data/f.npz", "runs/2026-old/model.pt", "runs/index.csv",
             "data/bench/b.txt")


def test_pin():
    """add pins HEAD into a snapshot laid out as the spec says; refuses with
    an untracked config, naming it; unpinned doesn't; a new data/ entry is
    linked at the next add; equal module trees reuse the pyroot by hard
    link; an ignored folder no rule covers refuses the snapshot."""
    tmp = tempfile.mkdtemp(prefix="jobs-test-")
    try:
        repo, builds = _repo(tmp)
        calls = []
        q = jobs.Queue(os.path.join(repo, "jobs"), repo=repo, builds=builds,
                       build=lambda *a: _wheel_build(*a, calls=calls))
        jid = q.add([PY, "scripts/x.py"], 1, heavy=False, pin="HEAD", log=os.path.join(tmp, "a.log"))
        head = jobs.git(repo, "rev-parse", "HEAD").strip()
        snap, job = os.path.join(builds, head[:12]), q.find(jid)[1]
        assert job["pin"] == head and job["cwd"] == snap and job["env"] == {"PYTHONPATH": os.path.join(snap, "pyroot")}
        for name in jobs.JUNCTIONS + ("runs", "data/ref"):
            assert os.path.isjunction(os.path.join(snap, name)), name
        assert os.path.samefile(os.path.join(snap, "data", "f.npz"), os.path.join(repo, "data", "f.npz"))
        assert not os.path.isjunction(os.path.join(snap, "data", "bench"))  # the snapshot's own, part of the pin
        assert sorted(jobs.git(snap, "ls-files", "-v", "runs").split()) == ["S", "runs/sweep-1.md"]  # runs/index.csv is ignored (.gitignore), so untracked
        assert jobs.git(snap, "worktree", "list", "--porcelain").count("locked") == 1
        assert os.path.isfile(os.path.join(snap, "pyroot", "sts", "__init__.py")) and len(calls) == 1
        _write(repo, {"configs/new.json": "{}"})
        try:
            q.add([PY, "scripts/x.py"], 1, pin="HEAD")
            raise AssertionError("pinned with an untracked config")
        except ValueError as err:
            assert "configs/new.json" in str(err) and "--unpinned" in str(err)
        assert "pin" not in q.find(q.add([PY, "scripts/x.py"], 1, log=os.path.join(tmp, "b.log")))[1]
        os.remove(os.path.join(repo, "configs", "new.json"))
        _write(repo, {"data/new.npz": "n", "data/newdir/x": "n"})
        q.add([PY, "scripts/x.py"], 1, pin="HEAD", log=os.path.join(tmp, "c.log"))
        assert os.path.samefile(os.path.join(snap, "data", "new.npz"), os.path.join(repo, "data", "new.npz"))
        assert os.path.isjunction(os.path.join(snap, "data", "newdir"))
        _write(repo, {"scripts/x.py": "print('y')\n"})
        _git(repo, "commit", "-qam", "scripts only")
        j2 = q.add([PY, "scripts/x.py"], 1, pin="HEAD", log=os.path.join(tmp, "d.log"))
        snap2 = q.find(j2)[1]["cwd"]
        pyd = [n for n in os.listdir(os.path.join(snap, "pyroot", "sts")) if n.endswith(".pyd")][0]
        assert snap2 != snap and len(calls) == 1 and os.path.samefile(
            os.path.join(snap, "pyroot", "sts", pyd), os.path.join(snap2, "pyroot", "sts", pyd))
        _write(repo, {"engine/logs/run.log": "x", "engine/lib.rs": "// changed\n"})  # `logs/` ignores engine/logs
        _git(repo, "add", "engine/lib.rs")
        _git(repo, "commit", "-qm", "engine")
        try:
            q.add([PY, "scripts/x.py"], 1, pin="HEAD")
            raise AssertionError("made a snapshot with an uncovered ignored folder")
        except ValueError as err:
            assert "engine/logs" in str(err)
        assert jobs.uncovered(jobs.REPO) == []  # the real checkout: every ignored folder is covered
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_pinned_writes_main():
    """A pinned job that creates a registry run (registry finds runs/ from
    its own file) writes the run folder and its index.csv line into main,
    and imports sts from the snapshot's pyroot."""
    tmp = tempfile.mkdtemp(prefix="jobs-test-")
    try:
        repo, builds = _repo(tmp, scripts=("registry.py", "selfplay.py", "stsnet.py", "action_text.py"))
        _write(repo, {"scripts/mkrun.py": "import registry, sts\nprint('sts', sts.__file__)\n"
                                          "r = registry.Run.create('pintest', {'name': 'pintest'}, [])\n"
                                          "r.finish()\nprint('run', r.id)\n"})
        _git(repo, "add", "scripts/mkrun.py")
        _git(repo, "commit", "-qm", "mkrun")
        q = jobs.Queue(os.path.join(repo, "jobs"), repo=repo, builds=builds, build=_wheel_build)
        log = os.path.join(tmp, "run.log")
        import torch  # registry needs it; the job's PYTHONPATH drops the test's packages, so run torch's venv
        venv = os.path.join(os.path.dirname(torch.__file__), "..", "..", "..", "Scripts", "python.exe")
        py = venv if os.path.exists(venv) else PY
        jid = q.add([py, "scripts/mkrun.py"], 1, heavy=False, pin="HEAD", log=log)
        r = jobs.Runner(q, idle=lambda: 16.0, free=lambda: 8.0, total=lambda: 16.0)
        assert r.claim()
        d = _until(lambda: (r.step(), q.find(jid)[0] == "done")[1] and q.find(jid)[1], tries=600)
        with open(log) as f:
            out = f.read()
        assert d["status"] == "ok", out
        snap = d["cwd"]
        run_id = out.split("run ")[-1].strip()
        assert os.path.normcase(os.path.join(snap, "pyroot")) in os.path.normcase(out)  # sts from the pin
        assert os.path.isfile(os.path.join(repo, "runs", run_id, "config.json"))
        with open(os.path.join(repo, "runs", "index.csv")) as f:
            assert f.read().splitlines()[-1].startswith(run_id)
        assert json.load(open(os.path.join(repo, "runs", run_id, "run.json")))["commit"] == d["pin"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_unpin_keeps_data():
    """unpin removes a snapshot and nothing of main's data; caches inside
    it are allowed; a modified data/bench file, an unknown untracked file
    or a new file in data/ is refused, naming the paths; a snapshot a job
    uses is refused; the runner's sweep unpins one unused for 24 h."""
    tmp = tempfile.mkdtemp(prefix="jobs-test-")
    try:
        repo, builds = _repo(tmp)
        q = jobs.Queue(os.path.join(repo, "jobs"), repo=repo, builds=builds, build=_wheel_build)
        jid = q.add([PY, "scripts/x.py"], 1, heavy=False, pin="HEAD", log=os.path.join(tmp, "a.log"))
        snap = q.find(jid)[1]["cwd"]
        assert jobs.unpin(q, "HEAD") == f"used by {jid}"
        q.cancel(jid)
        jobs.write_json(q.check_path(jid), {"pid": 1, "started_ts": 0, "log": "x"})  # its check runs in the snapshot
        assert jobs.unpin(q, "HEAD") == f"used by {jid}"
        os.remove(q.check_path(jid))
        other, _ = _repo(os.path.join(tmp, "other"))
        try:  # a repo the snapshot isn't a worktree of: refused before anything is removed
            jobs.unpin_snapshot(snap, other)
            raise AssertionError("unpinned through the wrong repo")
        except (ValueError, subprocess.CalledProcessError):
            pass
        assert os.path.isfile(os.path.join(snap, "pyroot", "key.txt")) and os.path.isjunction(os.path.join(snap, "db"))
        _write(snap, {"scripts/__pycache__/x.cpython-313.pyc": "", ".pytest_cache/v": ""})
        for files, named in (({"data/bench/b.txt": "changed"}, "data/bench/b.txt"),
                             ({"scripts/out.txt": "a job's output"}, "scripts/out.txt"),
                             ({"data/out.npz": "new"}, "data/out.npz")):
            backup = {k: open(os.path.join(snap, k)).read() for k in files if os.path.exists(os.path.join(snap, k))}
            _write(snap, files)
            err = jobs.unpin(q, "HEAD")
            assert err and named in err, err
            assert os.path.isjunction(os.path.join(snap, "results"))  # nothing removed
            for k in files:
                os.remove(os.path.join(snap, k))
            _write(snap, backup)
        assert jobs.unpin(q, "HEAD") is None, jobs.unpin(q, "HEAD")
        assert not os.path.exists(snap) and snap.replace("\\", "/") not in jobs.git(repo, "worktree", "list")
        for rel in MAIN_DATA:
            assert os.path.isfile(os.path.join(repo, rel)), rel
        # the sweep: unused for 24 h after its last job left
        jid = q.add([PY, "scripts/x.py"], 1, heavy=False, pin="HEAD", log=os.path.join(tmp, "b.log"))
        t = [time.time()]
        r = jobs.Runner(q, idle=lambda: 0.0, free=lambda: 8.0, total=lambda: 16.0, clock=lambda: t[0], sweep=True)
        r.step()
        assert os.path.isfile(os.path.join(snap, "pyroot", "used"))
        q.cancel(jid)
        t[0] += 23 * 3600
        assert not any(" unpinned " in l for l in r.step())
        t[0] += 2 * 3600
        assert any(" unpinned " in l for l in r.step()) and not os.path.exists(snap)
        for rel in MAIN_DATA:
            assert os.path.isfile(os.path.join(repo, rel)), rel
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sweep_removes_half_made():
    """A snapshot whose build failed (no pyroot/key.txt) is left for 24 h,
    then the sweep removes it the way unpin does; main's data stays."""
    tmp = tempfile.mkdtemp(prefix="jobs-test-")
    try:
        repo, builds = _repo(tmp)
        q = jobs.Queue(os.path.join(repo, "jobs"), repo=repo, builds=builds, build=_wheel_build)
        jid = q.add([PY, "scripts/x.py"], 1, heavy=False, pin="HEAD", log=os.path.join(tmp, "a.log"))
        snap = q.find(jid)[1]["cwd"]
        q.cancel(jid)
        os.remove(os.path.join(snap, "pyroot", "key.txt"))  # as a failed build leaves it
        t = [time.time()]
        r = jobs.Runner(q, idle=lambda: 0.0, free=lambda: 8.0, total=lambda: 16.0, clock=lambda: t[0], sweep=True)
        assert not any(" unpinned " in l for l in r.step()) and os.path.isdir(snap)
        t[0] += 25 * 3600
        assert any(" unpinned " in l and "half made" in l for l in r.step()), "not swept"
        assert not os.path.exists(snap) and snap.replace("\\", "/") not in jobs.git(repo, "worktree", "list")
        for rel in MAIN_DATA:
            assert os.path.isfile(os.path.join(repo, rel)), rel
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_same_pyd_bytes():
    """Installing the snapshot's wheel (main's build-then-swap) gives the
    same .pyd bytes as the snapshot's pyroot, so ladder caches keyed by the
    .pyd hash are shared."""
    tmp = tempfile.mkdtemp(prefix="jobs-test-")
    try:
        repo, builds = _repo(tmp)
        snap = jobs.snapshot("HEAD", repo, builds, _wheel_build)[0]
        target = os.path.join(tmp, "site")
        subprocess.run([PY, "-m", "pip", "install", "-q", "--no-deps", "--target", target, jobs.snapshot_wheel(snap)],
                       check=True, capture_output=True)
        import hashlib

        def pyd_hash(d):
            return [hashlib.sha256(open(os.path.join(d, n), "rb").read()).hexdigest()
                    for n in sorted(os.listdir(d)) if n.endswith(".pyd")]
        assert pyd_hash(os.path.join(target, "sts")) == pyd_hash(os.path.join(snap, "pyroot", "sts")) != []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_impact():
    """impact lists the unpinned pending and running jobs and exits 1;
    with only pinned jobs it exits 0."""
    e = Env()
    try:
        a = e.add(2)
        e.r.step()
        b = e.add(2)
        got = []
        assert jobs.impact(e.q, "sts", out=got.append) == 1 and a in got[0] and b in got[0]
        assert jobs.main(["--root", e.root, "impact", "scripts"]) == 1
        e.q.cancel(b)
        _end(e, a, 0)
        e.r.step()
        jobs.write_json(e.q.path("pending", "0100-pinned"), {"cmd": [PY, "x.py"], "threads": 1, "pin": "a" * 40})
        got = []
        assert jobs.impact(e.q, "sts", out=got.append) == 0 and got[0].endswith("none")
    finally:
        e.close()


def test_estimate():
    e = Env()
    try:
        a = e.add(2, estimate_min=60)
        assert e.q.estimate(a, 90, "pending, by hand")
        e.r.step()
        assert e.started == [a] and e.q.find(a)[0] == "running"
        assert e.q.estimate(a, 120.4, "pace: 50 / 100")  # a running job too
        job = e.q.find(a)[1]
        assert job["estimate_min"] == 120 and [x["to"] for x in job["estimates"]] == [90, 120]
        assert job["estimates"][0]["from"] == 60 and job["estimates"][1]["reason"] == "pace: 50 / 100"
        assert not e.q.estimate(a, 0) and not e.q.estimate("9999-none", 10)
        with open(e.q.log_path, encoding="utf-8") as f:
            assert "estimate " + a + " 90 -> 120 min (pace: 50 / 100)" in f.read()
        _end(e, a, 0)
        e.r.step()
        assert not e.q.estimate(a, 30)  # done: no change
    finally:
        e.close()


if __name__ == "__main__":
    names = [n for n in sorted(globals()) if n.startswith("test_")]
    for n in names:
        t0 = time.time()
        globals()[n]()
        print(f"ok {n} ({time.time() - t0:.1f}s)", flush=True)
    print(f"{len(names)} passed")
