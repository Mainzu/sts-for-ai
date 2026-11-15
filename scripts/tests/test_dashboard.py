"""Tests for the dashboard (scripts/dashboard.py, docs/specs/dashboard.md
verification). Run with `python scripts/tests/test_dashboard.py` (plain
asserts; every `test_*` function runs) or with pytest."""

import atexit
import datetime
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import dashboard  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "data", "dashboard")
TZ = datetime.timezone.utc
NOW = datetime.datetime(2026, 11, 3, 12, 0, tzinfo=TZ)
TMP = tempfile.mkdtemp(prefix="dashboard-test-")
atexit.register(shutil.rmtree, TMP, ignore_errors=True)


def checkout(name, extra=False):
    """A copy of the fixture checkout. `extra` adds the fixture's `extra/`
    tree on top: two overlapping lane runs (lanes gamma and, through job
    0005-gauntlet, delta), one with two turns, and a run resuming it."""
    root = os.path.join(TMP, name)
    shutil.copytree(FIXTURE, root, ignore=lambda d, names: ["extra"] if os.path.samefile(d, FIXTURE) else [])
    if extra:
        shutil.copytree(os.path.join(FIXTURE, "extra"), root, dirs_exist_ok=True)
    return root


def many_done(root, n=120):
    """n done jobs, one every 30 min back from 2026-11-03 06:00, lanes and
    statuses cycling, durations 10-59 min."""
    lanes, statuses = ("alpha", "beta", "delta"), ("ok", "ok", "failed", "killed")
    for i in range(n):
        end = datetime.datetime(2026, 11, 3, 6, 0, tzinfo=TZ) - datetime.timedelta(minutes=30 * i)
        took = 10 + (i * 7) % 50
        write(root, f"jobs/done/{1000 + i:04d}-gen.json", {
            "id": f"{1000 + i:04d}-gen", "cmd": ["python", "g.py"], "threads": 2, "estimate_min": 30.0,
            "lane": lanes[i % 3], "added": (end - datetime.timedelta(minutes=took + 5)).isoformat(),
            "started": (end - datetime.timedelta(minutes=took)).isoformat(), "ended": end.isoformat(),
            "status": statuses[i % 4], "exit_code": 0})


def alive(rec):  # the fixture's lane session (pid 111) runs; nothing else does
    return rec["pid"] == 111


def snapshot(root):
    out = {}
    for d, _, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def test_gather_first_screen():
    g = dashboard.gather(checkout("gather"), NOW, alive)
    h = g["health"]
    assert h["state"] == "red", h
    assert [r["name"] for r in h["red"]] == ["disk", "cpu"]
    assert round(h["age_min"]) == 10 and round(h["steward_age_min"]) == 100
    assert [(s["role"], s["lane"], round(s["age_min"]), s["model"]) for s in g["sessions"]] == \
        [("lanes", "alpha", 120, "claude-opus-5-5")]
    assert [(j["id"], round(j["run_min"])) for j in g["running"]] == [("0003-gauntlet", 60)]
    assert [j["id"] for j in g["pending"]] == ["0004-gauntlet"]
    assert [j["id"] for j in g["done"]] == ["0002-python", "0001-test-full"]
    assert len(g["recent"]) == 10 and g["recent"][0].startswith("2026-11-03 10:00 launcher lanes started")
    assert g["recent"][-1].startswith("2026-11-03 03:00")
    lanes = {l["name"]: l for l in g["lanes"]}
    assert (lanes["alpha"]["step"], lanes["alpha"]["checkpoint"], lanes["alpha"]["cpu_h"], lanes["alpha"]["cap"]) == \
        ("probe queued", "passed: probe read", 3.2, 10.0)
    assert lanes["beta"]["checkpoint"] is None and lanes["beta"]["step"] is None
    assert g["digest"] == "2026-11-03.md"


def test_session_without_claim_has_no_lane():
    root = checkout("noclaim")
    os.remove(os.path.join(root, "jobs", "locks", "lane-alpha.json"))
    g = dashboard.gather(root, NOW, alive)
    assert [s["lane"] for s in g["sessions"]] == [None]
    assert "no claim" in dashboard.render(root, "/", NOW, alive)[1]


def test_dead_or_ended_records_are_not_running():
    g = dashboard.gather(checkout("dead"), NOW, lambda rec: False)
    assert g["sessions"] == []
    g = dashboard.gather(checkout("ended"), NOW, lambda rec: True)  # the navigator record has `ended`
    assert [s["role"] for s in g["sessions"]] == ["lanes"]


def test_missing_or_stale_health_is_not_green():
    root = checkout("missing")
    os.remove(os.path.join(root, "jobs", "health.json"))
    g = dashboard.gather(root, NOW, alive)
    assert g["health"]["state"] == "missing" and g["lanes"] == []
    body = dashboard.render(root, "/", NOW, alive)[1]
    assert "missing: jobs/health.json" in body and 'class="light green"' not in body

    root = checkout("stale")
    p = os.path.join(root, "jobs", "health.json")
    with open(p, encoding="utf-8") as f:
        rep = json.load(f)
    rep.update(blockers=[], work=[], at="2026-11-03T09:00:00+00:00")  # all green but 3 h old
    with open(p, "w", encoding="utf-8") as f:
        json.dump(rep, f)
    g = dashboard.gather(root, NOW, alive)
    assert g["health"]["state"] == "stale"
    body = dashboard.render(root, "/", NOW, alive)[1]
    assert "stale: the report is 3.0 h ago" in body and 'class="light green"' not in body

    root = checkout("nolog")
    os.remove(os.path.join(root, "jobs", "roles.log"))
    assert dashboard.gather(root, NOW, alive)["recent"] is None
    assert "missing: jobs/roles.log" in dashboard.render(root, "/", NOW, alive)[1]


def test_conversation():
    root = checkout("conv")
    items = dashboard.conversation(dashboard.log_path(root, "navigator-20261103-090000.json"))
    assert [i["kind"] for i in items] == ["text", "tool", "tool", "text", "result"]
    assert (items[1]["name"], items[1]["arg"], items[1]["output"]) == ("Read", "docs/operating.md", "# Operating rules")
    assert (items[2]["name"], items[2]["arg"]) == ("Bash", "kb get lane/alpha")
    assert items[-1]["ok"] is True and items[-1]["text"] == "Run complete."

    running = dashboard.conversation(dashboard.log_path(root, "lanes-20261103-100000.json"))
    assert [i["kind"] for i in running] == ["text", "tool", "result"]  # thinking, hooks, system lines skipped
    assert running[1]["arg"] == "python scripts/health.py lock take lane-alpha"  # a command's first line
    assert running[-1]["ok"] is None
    body = dashboard.render(root, "/session/lanes-20261103-100000.json", NOW, alive)[1]
    assert "working" in body and "secret plan" not in body and '<details class="tool">' in body  # live: working


def test_long_output_cut_and_errors():
    root = checkout("long")
    p = os.path.join(root, "logs", "roles", "lanes-20261103-100000.jsonl")
    big = "x" * 30000
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t9", "name": "Grep", "input": {"pattern": "foo"}}]}}) + "\n")
        f.write(json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t9", "content": big}]}}) + "\n")
        f.write(json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True}) + "\n")
        f.write('{"type": "assist')  # a line still being written
    items = dashboard.conversation(p)
    tool = [i for i in items if i["kind"] == "tool" and i["name"] == "Grep"][0]
    assert tool["cut"] and len(tool["output"].encode()) == 20 * 1024
    assert items[-1]["ok"] is False and items[-1]["error"] == "error_max_turns"
    body = dashboard.render(root, "/session/lanes-20261103-100000.json", NOW, lambda rec: False)[1]
    assert "cut at 20 KB" in body and "error: error_max_turns" in body
    body = dashboard.render(root, "/session/lanes-20261103-100000.json", NOW, alive)[1]  # still live: working
    assert "turn ended (error_max_turns)" in body and "error: error_max_turns" not in body


def test_escaping():
    root = checkout("escape")
    for path in ("/", "/log", "/session/navigator-20261103-090000.json", "/digest"):
        body = dashboard.render(root, path, NOW, alive)[1]
        assert "<script>alert" not in body and "<b>bold</b>" not in body, path  # the page's own inline scripts aside
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in dashboard.render(root, "/log", NOW, alive)[1]
    assert "&lt;script&gt;alert(2)&lt;/script&gt;" in \
        dashboard.render(root, "/session/navigator-20261103-090000.json", NOW, alive)[1]


def test_escaping_new_fields():
    """Tool input, lane labels, job tooltips, queue filters and rows, the ?job= note."""
    root = checkout("escape-new", extra=True)
    x = '<img src=x onerror=alert(9)>"\''
    p = os.path.join(root, "jobs", "roles", "lanes-20261103-060000.json")
    rec = json.load(open(p, encoding="utf-8"))
    write(root, "jobs/roles/lanes-20261103-060000.json", {**rec, "why": [f"idle:{x}:z"]})
    p = os.path.join(root, "jobs", "pending", "0004-gauntlet.json")
    write(root, "jobs/pending/0004-gauntlet.json", {**json.load(open(p, encoding="utf-8")), "note": x, "lane": x})
    write(root, "jobs/done/odd.json", {"id": x, "lane": x, "status": x, "started": "2026-11-03T05:00:00+00:00",
                                        "ended": "2026-11-03T05:30:00+00:00"})
    with open(os.path.join(root, "logs", "roles", "lanes-20261103-060000.jsonl"), "a", encoding="utf-8") as f:
        for i, (name, inp) in enumerate((("Bash", {"command": "echo </pre>" + x}), ("Edit", {"x": "</pre>" + x}))):
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": f"e{i}", "name": name, "input": inp}]}}) + "\n")
    for path in ("/", "/queue", "/queue?job=%3Cimg%20src%3Dx%22", "/queue?lane=%3Cimg", "/session/lanes-20261103-060000.json"):
        assert "<img" not in dashboard.render(root, path, NOW, alive)[1], path


def test_log_lines_link_to_sessions():
    root = checkout("links")
    body = dashboard.render(root, "/log", NOW, alive)[1]
    assert body.count('href="/session/navigator-20261103-090000.json"') == 2  # the launcher's end line and the navigator's own
    os.remove(dashboard.log_path(root, "navigator-20261103-090000.json"))
    assert 'href="/session/navigator-20261103-090000.json"' not in dashboard.render(root, "/log", NOW, alive)[1]
    assert dashboard.render(root, "/session/..%2Fhealth.json", NOW, alive)[0] == 404


def test_activity():
    root = checkout("activity")
    a = dashboard.gather(root, NOW, alive)["activity"]
    assert [(s["record"], s["tone"]) for s in a["rows"]["lanes"]] == [("lanes-20261103-100000.json", "live")]
    nav = a["rows"]["navigator"][0]
    assert (nav["tone"], nav["end"].hour, nav["end"].minute) == ("ok", 9, 40)
    assert len(a["steward"]) == 9  # steward lines at 00:00-08:00
    jobs = {j["tip"].split()[0]: j for j in a["jobs"]}
    assert (jobs["0002-python"]["tone"], jobs["0003-gauntlet"]["tone"], jobs["0001-test-full"]["tone"]) == ("bad", "live", "ok")
    assert a["tracks"] == 1  # the three jobs follow each other
    body = dashboard.render(root, "/", NOW, alive)[1]
    assert 'class="gbar live" style="left:91.667%;width:8.333%;top:3px" href="/session/lanes-20261103-100000.json"' in body
    assert body.count('class="gmark"') == 9 and 'title="disk: red, value 1; fix: fix disk"' in body


def write(root, rel, obj):
    with open(os.path.join(root, *rel.split("/")), "w", encoding="utf-8") as f:
        json.dump(obj, f)


def test_chats_resumes_and_wakes():
    root = checkout("amend6")
    write(root, "jobs/roles/navigator-20261103-100500-chat.json", {
        "role": "navigator", "pid": 333, "chat": True, "session": "S2", "model": "m", "effort": "high",
        "started": "2026-11-03T10:05:00+00:00", "log": None, "why": ["chat"],
        "ended": "2026-11-03T10:30:00+00:00", "outcome": "chat"})
    write(root, "jobs/roles/navigator-20261103-110000.json", {
        "role": "navigator", "pid": 444, "model": "m", "effort": "high", "resumed": "S2",
        "started": "2026-11-03T11:00:00+00:00", "log": "x", "why": ["job:0003"],
        "ended": "2026-11-03T11:20:00+00:00", "outcome": "ok"})
    write(root, "jobs/navigator-wakes.json", {"wakes": [
        {"when": "job:0003-gauntlet", "why": "read the gauntlet", "at": "2026-11-03T08:00:00+00:00"},
        {"when": "checkpoint:alpha", "why": "next step", "at": "2026-11-03T08:00:00+00:00"},
        {"when": "owner", "why": "look at <b>this</b>", "at": "2026-11-03T09:30:00+00:00"}]})
    p = os.path.join(root, "jobs", "health.json")
    with open(p, encoding="utf-8") as f:
        rep = json.load(f)
    rep["wakes"]["navigator"] = ["job:0003-gauntlet", "owner@2026-11-03T09:30:00+00:00"]
    with open(p, "w", encoding="utf-8") as f:
        json.dump(rep, f)
    g = dashboard.gather(root, NOW, alive)
    nav = {s["record"]: s for s in g["activity"]["rows"]["navigator"]}
    chat = nav["navigator-20261103-100500-chat.json"]
    assert chat["tone"] == "chat" and "chat with the owner" in chat["tip"] and "resumes S2" in chat["tip"]
    res = nav["navigator-20261103-110000.json"]
    assert res["tone"] == "ok" and "effort high; resumes S2" in res["tip"]
    assert [(w["kind"], w["fired"]) for w in g["wakes"]] == [("job", True), ("checkpoint", False), ("owner", True)]
    body = dashboard.render(root, "/", NOW, alive)[1]
    assert 'class="gbar chat"' in body and "Navigator waits for" in body and "3 set, 2 fired" in body
    assert "look at &lt;b&gt;this&lt;/b&gt;" in body
    page = dashboard.render(root, "/session/navigator-20261103-100500-chat.json", NOW, alive)[1]
    assert "No log for this session" not in page and "keeps no headless log" in page
    assert 'href="/session/navigator-20261103-090000.json"' in page  # the session it resumes starts there
    page = dashboard.render(root, "/session/navigator-20261103-110000.json", NOW, alive)[1]
    assert "effort <b>high</b>" in page and "resumes" in page
    os.remove(os.path.join(root, "jobs", "navigator-wakes.json"))
    assert "missing: jobs/navigator-wakes.json" in dashboard.render(root, "/", NOW, alive)[1]


def test_lane_on_close_wakes_and_closed_lanes():
    root = checkout("closing")
    write(root, "docs/claims/lane/alpha.json", {"key": "lane/alpha", "status": "active",
                                                "value": "goal: g; kind: project; cap: 10 cpu-h; end: 2026-11-10; on-close: wake on go"})
    write(root, "jobs/navigator-wakes.json", {"wakes": [
        {"when": "checkpoint:alpha", "why": "next step decides", "at": "2026-11-03T08:00:00+00:00"},
        {"when": "checkpoint:beta", "why": "other lane", "at": "2026-11-03T08:00:00+00:00"}]})
    os.makedirs(os.path.join(root, "docs", "claims", "lane", "gamma"))
    write(root, "docs/claims/lane/gamma.json", {"key": "lane/gamma", "status": "retired", "value": "goal: x",
                                                "at": "2026-11-02T10:00:00+00:00"})
    write(root, "docs/claims/lane/gamma/step.json", {"key": "lane/gamma/step", "status": "retired",
                                                     "value": "done: probe <i>failed</i>; for the navigator: drop it",
                                                     "at": "2026-11-03T06:00:00+00:00"})
    g = dashboard.gather(root, NOW, alive)
    lanes = {l["name"]: l for l in g["lanes"]}
    assert lanes["alpha"]["on_close"] == "wake on go" and lanes["beta"]["on_close"] is None
    assert [w["when"] for w in lanes["alpha"]["wakes"]] == ["checkpoint:alpha"]
    assert [(l["name"], l["closed"][:13], l["checkpoint"]) for l in g["closed"]] == [("gamma", "2026-11-03T06", None)]
    body = dashboard.render(root, "/", NOW, alive)[1]
    assert "on close: wake on go" in body and "on close: not set" in body and "navigator wakes on checkpoint" in body
    assert "Recently closed" in body and "done: probe &lt;i&gt;failed&lt;/i&gt;; for the navigator: drop it" in body


BACKLOG = """# Backlog

## Open as lanes

- **alpha** (`lane/alpha`)

## Candidates

**Open questions**:
1. Not an entry: plain text.

Ready charters, in order: the next exploration slot takes
`late-charter` (7); the next project slot takes `early-charter` (3).

3. **early-charter** (Source: review 2026-11-09, direction 8; goal 2):
   a <b>new</b> net. Rated **even** that it builds. 40-60 thread-h.
   Ready charter (the next project slot):
   goal: g; kind: project
4. **opened** (open as `lane/alpha` (2026-11-09); Source: x; goal 1):
   Rated **likely**. 2 cpu-h.
5. **probe-one** (Source: navigator ideas run 2026-11-09; goal 1): Rated
   **likely**. About 3 thread-h, no code.
   Queued as a probe 2026-11-09 (probe sheet; jobs 0715-0728).
6. **plain** (Source: owner discussion; goal 1, a long shot): text.
7. **late-charter** (Source: navigator; goal 1): Rated **a long shot**.
   2 cpu-h. Ready charter (the next exploration slot):
   goal: h

**Checked and not proposed**:
- **not-a-candidate**: no.

## Parked

8. **parked-one** (Source: x): Rated **likely**.
"""


def test_candidate_lanes():
    root = checkout("candidates")
    os.makedirs(os.path.join(root, "docs"), exist_ok=True)
    assert dashboard.gather(root, NOW, alive)["candidates"] is None
    assert "missing: docs/backlog.md" in dashboard.render(root, "/", NOW, alive)[1]
    with open(os.path.join(root, "docs", "backlog.md"), "w", encoding="utf-8") as f:
        f.write(BACKLOG)
    cs = dashboard.gather(root, NOW, alive)["candidates"]
    assert [c["name"] for c in cs] == ["late-charter", "early-charter", "probe-one", "plain"]
    c = {c["name"]: c for c in cs}
    assert (c["early-charter"]["goal"], c["early-charter"]["rating"], c["early-charter"]["cost"],
            c["early-charter"]["source"], c["early-charter"]["charter"]) == \
        ("2", "even", "40-60 thread-h", "review 2026-11-09", "the next project slot")
    assert c["probe-one"]["queued"] == "0715-0728" and c["probe-one"]["charter"] is None
    assert c["plain"]["rating"] == "a long shot" and c["plain"]["cost"] is None
    body = dashboard.render(root, "/", NOW, alive)[1]
    assert "Candidate lanes" in body and "charter ready: the next project slot" in body
    assert "queued as a probe: jobs 0715-0728" in body and "1 more candidates" in body
    assert "a &lt;b&gt;new&lt;/b&gt; net" in body and "<b>new</b>" not in body
    assert "parked-one" not in body and "not-a-candidate" not in body


def test_read_only():
    root = checkout("readonly")
    before = snapshot(root)
    dashboard.gather(root, NOW, alive)
    for path in ("/", "/log", "/health", "/queue", "/digest", "/session/lanes-20261103-100000.json",
                 "/session/navigator-20261103-090000.json", "/nope"):
        dashboard.render(root, path, NOW, alive)
    dashboard.render(root, "/")  # with the real clock and roles.Launcher.ours
    assert snapshot(root) == before


PAGES = ("/", "/log", "/health", "/queue", "/digest", "/session/navigator-20261103-090000.json",
         "/session/lanes-20261103-060000.json")


def test_stdlib_only():
    import ast
    tree = ast.parse(open(os.path.join(os.path.dirname(__file__), "..", "dashboard.py"), encoding="utf-8").read())
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods - set(sys.stdlib_module_names) <= {"health", "roles"}, mods
    root = checkout("stdlib", extra=True)
    many_done(root)
    for path in PAGES:
        status, body = dashboard.render(root, path, NOW, alive)
        assert status == 200, path
        low = body.lower()
        assert "<script src" not in low and "<link" not in low and "@import" not in low, path
        assert "http://" not in low.replace("http://127.0.0.1", "") and "https://" not in low, path


def test_explorer_link():
    """Every page's top bar links to the explorer (explore.py's port)."""
    root = checkout("explorer-link")
    for path in ("/", "/log", "/queue", "/health", "/digest"):
        body = dashboard.render(root, path, NOW, alive)[1]
        assert '<a href="http://127.0.0.1:8765">Explorer</a>' in body, path


def test_refresh_kept():
    body = dashboard.render(checkout("refresh", extra=True), "/", NOW, alive)[1]
    assert f'<meta http-equiv="refresh" content="{dashboard.REFRESH_S}">' in body and dashboard.REFRESH_S == 60


def test_transcript_wording():
    root = checkout("wording", extra=True)
    for path in PAGES + ("/session/lanes-20261103-100000.json",):
        body = dashboard.render(root, path, NOW, alive)[1]
        assert "conversation" not in body.lower(), path
    assert "transcript &rarr;" in dashboard.render(root, "/", NOW, alive)[1]
    assert "conversation" not in dashboard.__doc__.lower()


def test_tool_input_shown():
    root = checkout("input", extra=True)
    body = dashboard.render(root, "/session/lanes-20261103-060000.json", NOW, alive)[1]
    assert "python scripts/jobs.py add probe\n  --threads 3\n  --lane gamma</pre>" in body  # the whole command
    assert "&quot;file_path&quot;: &quot;results/probe.json&quot;" in body  # other tools: their input as JSON
    p = os.path.join(root, "logs", "roles", "lanes-20261103-100000.jsonl")
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "w1", "name": "Write", "input": {"file_path": "a.txt", "content": "y" * 30000}}]}}) + "\n")
    items = dashboard.conversation(p)
    tool = [i for i in items if i["kind"] == "tool" and i["name"] == "Write"][0]
    assert tool["input_cut"] and len(tool["input"].encode()) == 20 * 1024 and tool["output"] is None
    body = dashboard.render(root, "/session/lanes-20261103-100000.json", NOW, alive)[1]
    assert "input, cut at 20 KB" in body and "no output yet" in body
    assert '<details class="tool nil">' not in body  # a call without output still opens, to its input


def test_working_not_ok():
    root = checkout("working", extra=True)
    p = os.path.join(root, "jobs", "roles", "lanes-20261103-060000.json")
    with open(p, encoding="utf-8") as f:
        rec = json.load(f)
    ended = dashboard.render(root, "/session/lanes-20261103-060000.json", NOW, alive)[1]
    assert ended.count("turn ended (ok)") == 1 and 'badge good' in ended and "working" not in ended
    items = dashboard.conversation(dashboard.log_path(root, "lanes-20261103-060000.json"))
    assert [i["kind"] for i in items].count("turn") == 1 and items[-1]["ok"] is True
    rec.pop("ended")
    rec.pop("outcome")
    write(root, "jobs/roles/lanes-20261103-060000.json", rec)
    live = dashboard.render(root, "/session/lanes-20261103-060000.json", NOW, lambda r: r["pid"] == 501)[1]
    assert "working" in live and "last turn ended" in live and 'badge good' not in live
    assert live.count("turn ended (ok)") == 2  # the mid-log turn and the last one so far
    # a live run with no result line yet: working, no "last turn ended"
    body = dashboard.render(root, "/session/lanes-20261103-100000.json", NOW, alive)[1]
    assert "working" in body and "last turn ended" not in body and "no result yet" not in body


def add_run(root, name, rec, sid, cost=None, usage=None):
    """A role record and its log: one init line, one result line when `cost` is given."""
    write(root, f"jobs/roles/{name}.json", {"role": name.split("-")[0], "pid": 900, "model": "m", **rec})
    lines = [{"type": "system", "subtype": "init", "session_id": sid}]
    if cost is not None:
        lines.append({"type": "result", "subtype": "success", "is_error": False, "result": "done", "session_id": sid,
                      "total_cost_usd": cost, "usage": usage or {"input_tokens": 1, "output_tokens": 1}})
    with open(os.path.join(root, "logs", "roles", f"{name}.jsonl"), "w", encoding="utf-8") as f:
        f.write("".join(json.dumps(l) + "\n" for l in lines))


def test_tokens_and_cost():
    root = checkout("cost", extra=True)
    first = dashboard.run_cost(root, "lanes-20261103-060000.json")
    assert first["tokens"] == {"input": 30, "cache_write": 2500, "cache_read": 90000, "output": 1300, "thinking": 400}
    assert abs(first["cost"] - 2.06) < 1e-9 and not first["earlier"] and first["turns"] == 2
    resumed = dashboard.run_cost(root, "lanes-20261103-083000.json")
    assert abs(resumed["cost"] - 0.20) < 1e-9 and not resumed["earlier"]  # 2.26 at its end minus 2.06 at R1's end
    body = dashboard.render(root, "/session/lanes-20261103-060000.json", NOW, alive)[1]
    assert "93 k in &middot; 1.3 k out &middot; &asymp; $2.06" in body
    assert 'title="input 30, cache write 2,500, cache read 90,000, output 1,300 (thinking 400)"' in body
    body = dashboard.render(root, "/session/lanes-20261103-083000.json", NOW, alive)[1]
    assert "20 k in &middot; 150 out &middot; &asymp; $0.20" in body and "includes earlier runs" not in body
    # a resume whose earlier run has no log here: the full figure, marked
    add_run(root, "lanes-20261103-090000", {"started": "2026-11-03T09:00:00+00:00", "ended": "2026-11-03T09:10:00+00:00",
                                            "resumed": "ZZ"}, "ZZ", cost=3.0)
    body = dashboard.render(root, "/session/lanes-20261103-090000.json", NOW, alive)[1]
    assert "&asymp; $3.00" in body and "includes earlier runs" in body
    # live: so far; live with no finished turn: none yet
    add_run(root, "lanes-20261103-110000", {"started": "2026-11-03T11:00:00+00:00", "pid": 111}, "LV", cost=0.5)
    body = dashboard.render(root, "/session/lanes-20261103-110000.json", NOW, alive)[1]
    assert "&asymp; $0.50 so far" in body
    body = dashboard.render(root, "/session/lanes-20261103-100000.json", NOW, alive)[1]
    assert "tokens <b>none yet</b>" in body


def test_week_cost():
    root = checkout("week", extra=True)
    # the last 7 days before NOW start 2026-10-27 12:00
    add_run(root, "lanes-20261027-115900", {"started": "2026-10-27T11:59:00+00:00", "ended": "2026-10-27T12:30:00+00:00"},
            "W0", cost=5.0)
    add_run(root, "navigator-20261027-120100", {"started": "2026-10-27T12:01:00+00:00",
                                                "ended": "2026-10-27T12:30:00+00:00"}, "W1", cost=1.0)
    write(root, "jobs/roles/navigator-20261103-080000.json", {"role": "navigator", "pid": 0, "chat": True,
                                                              "started": "2026-11-03T08:00:00+00:00", "session": "W1"})
    g = dashboard.gather(root, NOW, alive)
    w = g["week"]
    assert abs(w["cost"] - 4.06) < 1e-9, w  # 2.06 + 0.80 + 0.20 (lanes) + 1.00 (navigator); W0 is older
    assert abs(w["by_role"]["lanes"] - 3.06) < 1e-9 and abs(w["by_role"]["navigator"] - 1.0) < 1e-9
    assert w["sessions"] == 6 and w["chats"] == 1  # the fixture's two logs, the three extra runs, W1
    body = dashboard.render(root, "/", NOW, alive)[1]
    assert "&asymp; $4.06 in the last 7 days (6 sessions)" in body
    assert "owner chats not counted: no log" in body and "lanes $3.06" in body


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_end_to_end():
    root = checkout("e2e")
    before = snapshot(root)
    port = free_port()
    proc = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), "..", "dashboard.py"),
                             "--port", str(port), "--root", root], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        expect = {"/": "Recent role runs", "/log": "lanes started: idle:alpha:none", "/health": "disk",
                  "/queue": "0004-gauntlet", "/digest": "Red now: cpu",
                  "/session/navigator-20261103-090000.json": "Run complete."}
        for path, text in expect.items():
            for _ in range(50):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as r:
                        assert r.status == 200 and text in r.read().decode("utf-8"), path
                    break
                except urllib.error.URLError:
                    time.sleep(0.2)
            else:
                raise AssertionError(f"no answer on {path}")
    finally:
        proc.kill()
        proc.wait()
    assert snapshot(root) == before


def test_lane_tracks():
    root = checkout("lanetracks", extra=True)
    write(root, "jobs/roles/lanes-20261103-090000.json", {
        "role": "lanes", "pid": 504, "model": "m", "started": "2026-11-03T09:00:00+00:00",
        "ended": "2026-11-03T09:10:00+00:00", "outcome": "ok", "why": ["backstop:x"]})
    a = dashboard.gather(root, NOW, alive)["activity"]
    lanes = {s["record"]: s for s in a["rows"]["lanes"]}
    assert lanes["lanes-20261103-060000.json"]["track"] == 0
    assert lanes["lanes-20261103-070000.json"]["track"] == 1  # overlaps 06:00-08:00
    assert lanes["lanes-20261103-083000.json"]["track"] == 0
    assert a["row_tracks"]["lanes"] == 2 and a["row_tracks"]["navigator"] == 1
    assert lanes["lanes-20261103-060000.json"]["tip"].startswith("gamma: ")
    assert lanes["lanes-20261103-070000.json"]["tip"].startswith("delta: ")  # through job 0005-gauntlet
    assert lanes["lanes-20261103-090000.json"]["tip"].startswith("lane unknown: ")
    assert lanes["lanes-20261103-100000.json"]["lane"] == "alpha"
    body = dashboard.render(root, "/", NOW, alive)[1]
    assert '<span class="gl">gamma</span>' in body and '<span class="gl">delta</span>' in body
    assert 'top:17px' in body  # the second lanes track


def test_job_chip_tooltip():
    root = checkout("chips")
    body = dashboard.render(root, "/", NOW, alive)[1]
    assert 'title="lane filler · 2 threads · estimate 60 min' in body  # the pending chip
    running = dashboard.gather(root, NOW, alive)["running"][0]
    assert f'title="lane {running["lane"]} · {running["threads"]} threads' in body  # the running job's id


def done_ids(body):
    """Job ids of the Done table's rows, in order."""
    import re
    part = body[body.index("<h2>Done"):]
    return re.findall(r'<tr id="job-([^"]+)"', part)


def test_queue_pages():
    root = checkout("queuepages")
    many_done(root)  # 120 generated + the fixture's 2 = 122 done jobs
    body = dashboard.render(root, "/queue", NOW, alive)[1]
    ids = done_ids(body)
    assert len(ids) == 50 and ids[:2] == ["0002-python", "0001-test-full"] and "page 1 of 3" in body
    assert 'href="/queue?page=2"' in body and "Older" in body
    assert len(done_ids(dashboard.render(root, "/queue?page=3", NOW, alive)[1])) == 22
    last = dashboard.render(root, "/queue?page=99", NOW, alive)[1]
    assert "page 3 of 3" in last and len(done_ids(last)) == 22
    alpha = dashboard.render(root, "/queue?lane=alpha", NOW, alive)[1]
    assert len(done_ids(alpha)) == 42 and "page 1 of 1" in alpha
    failed = dashboard.render(root, "/queue?status=failed&page=1", NOW, alive)[1]
    assert len(done_ids(failed)) == 31
    took = done_ids(dashboard.render(root, "/queue?sort=took&order=asc", NOW, alive)[1])
    gens = [int(i[:4]) - 1000 for i in took if i.endswith("-gen")]
    assert [10 + (i * 7) % 50 for i in gens] == sorted(10 + (i * 7) % 50 for i in gens)
    assert took[0].endswith("-gen") and 10 + ((int(took[0][:4]) - 1000) * 7) % 50 == 10
    by_id = done_ids(dashboard.render(root, "/queue?sort=id&order=asc", NOW, alive)[1])
    assert by_id[:2] == ["0001-test-full", "0002-python"]
    bad = dashboard.render(root, "/queue?sort=bogus&order=sideways&lane=nope&status=%3Cb%3E&page=x", NOW, alive)[1]
    assert done_ids(bad) == ids
    assert '<select name="lane">' in bad and '<option value="alpha">' in bad and '<option value="failed">' in bad


def test_job_link():
    root = checkout("joblink")
    many_done(root)
    body = dashboard.render(root, "/queue?job=1100-gen", NOW, alive)[1]
    assert "1100-gen" in done_ids(body) and "page 3 of 3" in body
    assert '<tr id="job-1100-gen"' in body and "tr:target" in body
    run = dashboard.render(root, "/queue?job=0003-gauntlet", NOW, alive)[1]
    assert '<tr id="job-0003-gauntlet"' in run and "page 1 of 3" in run
    gone = dashboard.render(root, "/queue?job=9999-%3Cx%3E", NOW, alive)[1]
    assert "job 9999-&lt;x&gt; not found" in gone and "page 1 of 3" in gone
    assert dashboard.job_href("0003-gauntlet") == "/queue?job=0003-gauntlet#job-0003-gauntlet"
    assert 'href="/queue?job=0003-gauntlet#job-0003-gauntlet"' in dashboard.render(root, "/", NOW, alive)[1]


def test_timeline_range():
    root = checkout("timeline")
    write(root, "jobs/roles/navigator-20261031-120000.json", {  # 3 days back: kept, and widens the span
        "role": "navigator", "pid": 601, "model": "m", "started": "2026-10-31T12:00:00+00:00",
        "ended": "2026-10-31T13:00:00+00:00", "outcome": "ok", "why": ["date:x"]})
    write(root, "jobs/roles/navigator-20260920-120000.json", {  # 44 days back: dropped
        "role": "navigator", "pid": 602, "model": "m", "started": "2026-09-20T12:00:00+00:00",
        "ended": "2026-09-20T13:00:00+00:00", "outcome": "ok", "why": ["date:y"]})
    with open(os.path.join(root, "jobs", "roles.log"), "a", encoding="utf-8") as f:
        f.write("2026-09-21 00:00 steward steward-x old\n2026-11-01 00:00 steward steward-x two days back\n")
    a = dashboard.gather(root, NOW, alive)["activity"]
    assert a["end"] == NOW and a["start"] == NOW - datetime.timedelta(days=3)
    assert [s["record"] for s in a["rows"]["navigator"]] == ["navigator-20261031-120000.json", "navigator-20261103-090000.json"]
    assert len(a["steward"]) == 10  # the 9 of 11-03 and the one of 11-01; the one of 09-21 is past 30 days
    body = dashboard.render(root, "/", NOW, alive)[1]
    t0, t1 = int((NOW - datetime.timedelta(days=3)).timestamp()), int(NOW.timestamp())
    assert f'data-t0="{t0}" data-t1="{t1}"' in body
    assert 'class="ginner" dir="ltr" style="width:300.00%"' in body  # the first view: the last 24 h of 3 days
    assert 'class="gscroll" dir="rtl"' in body  # opens at its right end, also without the script
    assert "navigator-20260920" not in body
    # history shorter than 24 h still spans 24 h (test_activity's positions)
    short = dashboard.gather(checkout("timeline-short"), NOW, alive)["activity"]
    assert short["start"] == NOW - datetime.timedelta(hours=24)
    # an old record past 30 days caps the span at 30 days
    root2 = checkout("timeline-cap")
    write(root2, "jobs/roles/navigator-20261002-000000.json", {
        "role": "navigator", "pid": 603, "model": "m", "started": "2026-10-02T00:00:00+00:00",
        "ended": "2026-10-05T00:00:00+00:00", "outcome": "ok", "why": ["date:z"]})
    assert dashboard.gather(root2, NOW, alive)["activity"]["start"] == NOW - datetime.timedelta(days=dashboard.TIMELINE_DAYS)


def test_md_tables():
    text = r"""Before

| arm | HP | note |
|---|---:|---|
| a | +1.5 | `x` \| y |
| <b>b</b> | -2 |

After
| lone | row |
"""
    h = dashboard.md(text)
    assert '<table class="md">' in h and "<th>arm</th>" in h and "<th>HP</th>" in h
    assert "<td>+1.5</td>" in h and "<code>x</code> | y" in h  # an escaped pipe stays in its cell
    assert "&lt;b&gt;b&lt;/b&gt;" in h and "<b>b</b>" not in h
    assert h.count("<tr>") == 4 and "<td></td>" in h  # a short row is padded
    assert "<p>Before</p>" in h and "<p>After</p>" in h
    assert "<td>lone</td>" in h  # a table without a separator row has no header


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
