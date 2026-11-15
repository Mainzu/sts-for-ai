"""Dashboard: a local, read-only page on what the roles and jobs are doing
(docs/decisions.md: "Dashboard as built" and "Dashboard improvements as built").

    python scripts/dashboard.py [--port 8766]

Serves http://127.0.0.1:8766 (127.0.0.1 only); stop it with Ctrl+C. Every
request reads the files again: `jobs/health.json`, `jobs/roles.log`, the
launcher's records in `jobs/roles/` and their logs in `logs/roles/`, the
queue in `jobs/`, lane claims in `jobs/locks/`, lane checkpoints in
`docs/claims/lane/`, the navigator's wakes in `jobs/navigator-wakes.json`,
the candidate lanes in `docs/backlog.md` and the newest `docs/digest/`. It
never writes a file or runs `kb`; everything shown is escaped. Pages: `/`
(health, running now, recent role runs, lanes with their on-close and the
wakes waiting on them, the candidate lanes (ready charters and queued
probes first, the rest folded, by number), the recently closed lanes with their end note (last step fact), the
navigator's wakes with the fired ones marked; a timeline of up to 30 days
that zooms with the wheel and pans by dragging, its view kept in the URL
across the 60 s refresh; the last 7 days' estimated cost),
`/session/<record name>` (a role session's log as a transcript: each tool
call's whole input, turn ends, "working" while it runs, tokens and
estimated cost; its effort and the session it resumes; an owner chat
(`roles.py chat`) has no log and draws in its own neutral colour), `/log`,
`/health`, `/queue` (done jobs in pages of 50, filtered by lane and
status, sorted; `?job=<id>` opens a job's row), `/digest`.
"""

import argparse
import datetime
import glob
import html
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import health  # noqa: E402
import roles  # noqa: E402

PORT = 8766                 # explore.py keeps 8765
HEALTH_STALE_H = 1.0        # the launcher refreshes health.json every 15 min while it runs
RECENT = 10                 # roles.log lines on the first screen
DONE_PAGE = 50              # done jobs per page on /queue
OUTPUT_MAX = 20 * 1024      # a tool's output is cut here (bytes)
REFRESH_S = 60
ACTIVITY_H = 24            # hours the timeline shows first (and spans at least)
TIMELINE_DAYS = 30         # the timeline holds history this far back
CLOSED_SHOWN = 5           # closed lanes on the first screen


def read_json(root, *parts):
    try:
        with open(os.path.join(root, *parts), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def read_text(root, *parts):
    try:
        with open(os.path.join(root, *parts), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def minutes(t, now):
    t = health.parse_time(t) if isinstance(t, str) else t
    return None if t is None else (now - t).total_seconds() / 60


def first_session_id(path):
    """The session id in a stream-json log's first lines; None if it has none yet."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for _, line in zip(range(20), f):
                try:
                    sid = json.loads(line).get("session_id")
                except (ValueError, AttributeError):
                    continue
                if sid:
                    return sid
    except OSError:
        pass
    return None


def log_path(root, record):
    """logs/roles/<role>-<stamp>.jsonl for the record `<role>-<stamp>.json`."""
    return os.path.join(root, "logs", "roles", record[:-len(".json")] + ".jsonl")


_USAGE = {}  # (path, mtime, size) -> log_usage(path); a log that grows gets a new key


def log_usage(path):
    """What a stream-json log's `result` lines say: its session id, turns,
    tokens (each line's `usage` covers that turn) and the last
    `total_cost_usd` (cumulative over the session id, earlier resumed runs
    included). None when there is no log."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (path, st.st_mtime_ns, st.st_size)
    if key in _USAGE:
        return _USAGE[key]
    tokens = dict.fromkeys(("input", "cache_write", "cache_read", "output", "thinking"), 0)
    sid, turns, cost = None, 0, None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if sid is None or '"result"' in line:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(d, dict):
                    continue
                sid = sid or d.get("session_id")
                if d.get("type") != "result":
                    continue
                turns += 1
                u = d.get("usage") if isinstance(d.get("usage"), dict) else {}
                for k, src in (("input", "input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                               ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")):
                    tokens[k] += u.get(src) or 0
                tokens["thinking"] += (u.get("output_tokens_details") or {}).get("thinking_tokens") or 0
                if isinstance(d.get("total_cost_usd"), (int, float)):
                    cost = d["total_cost_usd"]
    if len(_USAGE) > 4000:
        _USAGE.clear()
    _USAGE[key] = out = {"sid": sid, "turns": turns, "tokens": tokens, "cost": cost}
    return out


def usage_index(root):
    """(record, started, session id, cost at its log's end) for every record with a log."""
    out = []
    for name in records(root):
        u = log_usage(log_path(root, name))
        if u:
            rec = read_json(root, "jobs", "roles", name) or {}
            out.append((name, str(rec.get("started") or ""), u["sid"], u["cost"]))
    return out


def run_cost(root, name, rec=None, index=None):
    """A role run's tokens and estimated cost (Claude Code's figure at API
    prices): the cost at its log's end minus the cost at the end of the run
    it resumes (the newest earlier record whose log has that session id).
    `earlier` when it resumes a run with no log here, so the figure
    includes earlier runs. None when the run has no log. `index` is
    usage_index(root), passed when costing many runs."""
    rec = rec if rec is not None else (read_json(root, "jobs", "roles", name) or {})
    u = log_usage(log_path(root, name))
    if u is None:
        return None
    cost, earlier, rid = u["cost"], False, "" if rec.get("chat") else resumed_id(rec)
    if rid and cost is not None:
        started = str(rec.get("started") or "")
        before = [(s, c) for n, s, sid, c in (usage_index(root) if index is None else index)
                  if n != name and sid == rid and c is not None and s < started]
        if before:
            cost -= max(before)[1]
        else:
            earlier = True
    return {**u, "cost": cost, "earlier": earlier}


def count(n):
    """A token count, short: 150, 1.3 k, 93 k, 5.2 M."""
    if n < 1000:
        return f"{n}"
    if n < 10_000:
        return f"{n / 1000:.1f} k"
    return f"{n / 1000:.0f} k" if n < 1_000_000 else f"{n / 1e6:.1f} M"


def records(root):
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(root, "jobs", "roles", "*.json")))


def claims(root):
    """{session id: lane} from the lane claims jobs/locks/lane-<name>.json."""
    out = {}
    for p in glob.glob(os.path.join(root, "jobs", "locks", "lane-*.json")):
        held = read_json(p)
        if held and held.get("session"):
            out[held["session"]] = os.path.basename(p)[len("lane-"):-len(".json")]
    return out


def jobs_in(root, state):
    out = []
    for p in sorted(glob.glob(os.path.join(root, "jobs", state, "*.json"))):
        job = read_json(p)
        if isinstance(job, dict):
            out.append(job)
    return out


def health_block(root, now):
    rep = read_json(root, "jobs", "health.json")
    if not isinstance(rep, dict):
        return {"state": "missing"}
    age = minutes(rep.get("at"), now)
    red = [{"name": m.get("name"), "kind": m.get("kind"), "fix": m.get("fix")}
           for m in (rep.get("blockers") or []) + (rep.get("work") or [])]
    stale = age is None or age > HEALTH_STALE_H * 60
    return {"state": "stale" if stale else ("red" if red else "green"), "red": red, "at": rep.get("at"),
            "age_min": age, "steward_at": rep.get("steward_at"), "steward_age_min": minutes(rep.get("steward_at"), now),
            "metrics": rep.get("metrics") or [], "lanes": rep.get("lanes") or {},
            "lane_cpu_h": (rep.get("wakes") or {}).get("lane_cpu_h") or {},
            "nav_fired": (rep.get("wakes") or {}).get("navigator") or []}


def roles_log(root):
    text = read_text(root, "jobs", "roles.log")
    return None if text is None else [l for l in text.splitlines() if l.strip()][::-1]


def session_lane(rec, done_lane, claim):
    """The lane a lane session worked on: `idle:<lane>` in its why, else the
    lane of the job an `ended:<job id>` names, else its live claim, else
    "lane unknown"."""
    for w in map(str, rec.get("why") or []):
        kind, _, rest = w.partition(":")
        if kind == "idle" and rest.partition(":")[0]:
            return rest.partition(":")[0]
        if kind == "ended" and done_lane.get(rest):
            return str(done_lane[rest])
    return claim or "lane unknown"


def session_span(root, name, rec, live, now, lane=None):
    """A role session as a span: start, end (now while it runs; its log's last
    write when the record has no end), the record, its lane (lane sessions)
    and a tooltip, which for a lane session starts with its lane."""
    start = health.parse_time(rec["started"])
    end = health.parse_time(rec.get("ended"))
    if live:
        end = now
    elif end is None:
        try:
            end = datetime.datetime.fromtimestamp(os.path.getmtime(log_path(root, name))).astimezone()
        except OSError:
            end = start
    out = rec.get("outcome") or ("running" if live else "no end recorded")
    chat = bool(rec.get("chat"))
    what = "chat with the owner" if chat else ", ".join(map(str, rec.get("why") or []))
    extra = "".join(f"; {k} {v}" for k, v in (("effort", rec.get("effort")), ("resumes", resumed_id(rec)[:8])) if v)
    tip = f"{rec.get('role')} {start:%H:%M}-{'now' if live else f'{end:%H:%M}'}: {'running' if live else out}; {what}{extra}"
    tone = "chat" if chat else ("ok" if out == "ok" else "bad" if out != "no end recorded" else "")
    if lane:
        tip = f"{lane}: {tip}"
    return {"row": rec.get("role"), "start": start, "end": end, "record": name, "tip": tip, "lane": lane,
            "tone": ("live " + tone).strip() if live and chat else ("live" if live else tone)}


def resumed_id(rec):
    """The session id a record resumes: `resumed` for a headless run, the
    chosen session for an owner chat; "" for a fresh start."""
    return str(rec.get("resumed") or (rec.get("session") if rec.get("chat") else "") or "")


def wake_fired(w, keys):
    """Whether wake `w` (jobs/navigator-wakes.json) is among the fired,
    not yet handled event keys health.json lists under wakes.navigator
    (health.wake_key's formats)."""
    when = str(w.get("when") or "")
    kind = when.partition(":")[0]
    for k in keys:
        k = str(k)
        if kind in health.NOTE_KINDS:
            if k == f"{when}@{w.get('at')}":
                return True
        elif k == when or k.startswith(when + "@") or (kind == "ideas" and k.startswith("ideas:")):
            return True
    return False


def timeline_rows(spans, running, done, log, now):
    """The history up to TIMELINE_DAYS back (at least ACTIVITY_H hours):
    role sessions and queue jobs as spans, steward runs (roles.log lines)
    as marks. Sessions of one role, and jobs, that overlap take separate
    tracks."""
    lo = now - datetime.timedelta(days=TIMELINE_DAYS)
    stamps = []
    for line in log or []:
        m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) steward (.*)$", line)
        if m:
            t = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=now.tzinfo)
            if t >= lo:
                stamps.append((t, m.group(2)))
    job_times = [(j, health.parse_time(j.get("started")), health.parse_time(j.get("ended")) or now) for j in running + done]
    firsts = [s["start"] for s in spans if s["end"] >= lo] + [t for t, _ in stamps] + \
        [s for _, s, e in job_times if s is not None and e >= lo]
    start = max(lo, min([now - datetime.timedelta(hours=ACTIVITY_H)] + firsts))
    rows = {r: [] for r in ("navigator", "lanes")}
    for s in sorted(spans, key=lambda s: s["start"]):
        if s["end"] >= start:
            rows.setdefault(s["row"], []).append(s)
    row_tracks = {}
    for r, ss in rows.items():
        ends = []
        for s in ss:
            s["track"] = place(ends, s["start"], s["end"])
        row_tracks[r] = max(len(ends), 1)
    marks = [{"at": t, "tip": f"steward {t:%m-%d %H:%M}: {msg[:400]}"} for t, msg in stamps if t >= start]
    jobs, tracks = [], []
    for j, s, e in sorted(job_times, key=lambda x: x[0].get("started") or ""):
        if s is None or e < start:
            continue
        status = j.get("status") or "running"
        k = place(tracks, s, e)
        jobs.append({"start": s, "end": e, "track": k, "href": job_href(j.get("id")), "tone": "live" if status == "running" else ("ok" if status == "ok" else "bad"),
                     "tip": f"{j.get('id')} ({j.get('lane')}, {j.get('threads', '?')} threads) {s:%H:%M}-"
                            f"{'now' if status == 'running' else f'{e:%H:%M}'}: {status}"})
    return {"start": start, "end": now, "rows": rows, "row_tracks": row_tracks, "steward": marks, "jobs": jobs,
            "tracks": max(len(tracks), 1)}


def place(ends, s, e):
    """The first track (an index into `ends`, each track's last end) free at
    `s`; the span ending at `e` takes it."""
    k = next((i for i, last in enumerate(ends) if last <= s), len(ends))
    ends[k:k + 1] = [e]
    return k


def closed_lanes(root, open_names):
    """Retired lane charters, newest close first (CLOSED_SHOWN): name, when
    it closed (the newest `at` of its three facts), the end note (its last
    `lane/<name>/step`) and last checkpoint."""
    out = []
    for p in glob.glob(os.path.join(root, "docs", "claims", "lane", "*.json")):
        name = os.path.basename(p)[:-len(".json")]
        charter = read_json(p)
        if name in open_names or not isinstance(charter, dict) or charter.get("status") != "retired":
            continue
        step = read_json(root, "docs", "claims", "lane", name, "step.json") or {}
        cp = read_json(root, "docs", "claims", "lane", name, "checkpoint.json") or {}
        at = max((str(f.get("at") or "") for f in (charter, step, cp) if isinstance(f, dict)), default="")
        out.append({"name": name, "closed": at, "note": step.get("value") if isinstance(step, dict) else None,
                    "checkpoint": cp.get("value") if isinstance(cp, dict) else None})
    return sorted(out, key=lambda l: l["closed"], reverse=True)[:CLOSED_SHOWN]


RATING = re.compile(r"\b(likely|even|a long shot)\b")


def candidates(root):
    """The candidate lanes in docs/backlog.md's "Candidates" section: each
    numbered entry `N. **name** (Source: ...` with its continuation lines.
    Per entry: number, name, source, goal, the first rating in bold words,
    the first CPU- or thread-hour estimate, its ready charter's slot, the
    jobs of a queued probe, and its text. Entries already open as a lane
    are left out. Ready charters come first, in the order the "Ready
    charters, in order" sentence names them, then queued probes, then the
    rest by number (the backlog states no rank between them). None when
    the file is missing."""
    text = read_text(root, "docs", "backlog.md")
    if text is None:
        return None
    sec = re.search(r"^## Candidates\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    entries, cur = [], None
    for line in (sec[1] if sec else "").splitlines():
        m = re.match(r"(\d+)\. \*\*([\w.-]+)\*\*(.*)", line)
        if m:
            cur = {"n": int(m[1]), "name": m[2], "lines": [m[3].strip()]}
            entries.append(cur)
        elif cur and line.startswith(" ") and line.strip():
            cur["lines"].append(line.strip())
        else:
            cur = None
    order = re.search(r"Ready charters, in order:(.*?)(?:\n\n|\Z)", sec[1] if sec else "", re.S)
    order = re.findall(r"`([\w.-]+)`", order[1]) if order else []
    out = []
    for e in entries:
        body = " ".join(e["lines"])
        if re.search(r"open as `lane/", body.split("Ready charter")[0]):
            continue
        src = re.match(r"\(Source:\s*([^;),]+)", body)
        goal = re.search(r"\bgoal (\d)", body)
        rating = re.search(r"\*\*(likely|even|a long shot)\*\*", body) or RATING.search(body.split("):")[0])
        cost = re.search(r"(\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?) (cpu-h|thread-h)", body)
        charter = re.search(r"Ready charter \(([^)]*)\)", body)
        queued = re.search(r"Queued as a probe[^(]*\([^)]*?jobs ([\w-]+)\)", body)
        out.append({"n": e["n"], "name": e["name"], "source": src[1].strip() if src else None,
                    "goal": goal[1] if goal else None, "rating": rating[1] if rating else None,
                    "cost": f"{cost[1]} {cost[2]}" if cost else None,
                    "charter": charter[1].strip() if charter else None,
                    "queued": queued[1] if queued else None, "text": body})

    def key(c):
        if c["charter"]:
            return (0, order.index(c["name"]) if c["name"] in order else len(order), c["n"])
        return (1 if c["queued"] else 2, 0, c["n"])
    return sorted(out, key=key)


def gather(root, now=None, ours=None):
    """Everything the pages show, read from the checkout at `root`. `ours`
    says whether a launcher record's process still runs (default
    roles.Launcher.ours)."""
    now = now or datetime.datetime.now().astimezone()
    ours = ours or roles.Launcher(main=root).ours
    hl = health_block(root, now)
    lane_of = claims(root)
    done = sorted(jobs_in(root, "done"), key=lambda j: j.get("ended") or "", reverse=True)
    done_lane = {str(j.get("id")): j.get("lane") for j in done}
    by_session, sessions, spans = {}, [], []
    for name in records(root):
        sid = first_session_id(log_path(root, name))
        if sid:
            by_session[sid] = name
        rec = read_json(root, "jobs", "roles", name)
        if not isinstance(rec, dict) or not rec.get("started"):
            continue
        live = not rec.get("ended") and bool(rec.get("pid")) and ours(rec)
        lane = session_lane(rec, done_lane, lane_of.get(sid) if live else None) if rec.get("role") == "lanes" else None
        spans.append(session_span(root, name, rec, live, now, lane))
        if not live:
            continue
        sessions.append({"record": name, "role": rec.get("role"), "model": rec.get("model"), "why": rec.get("why") or [],
                         "chat": bool(rec.get("chat")), "resumed": resumed_id(rec), "effort": rec.get("effort"),
                         "age_min": minutes(rec.get("started"), now), "session": sid, "lane": lane_of.get(sid),
                         "has_log": os.path.exists(log_path(root, name))})
    running = []
    for job in jobs_in(root, "running"):
        running.append({**job, "run_min": minutes(job.get("started"), now)})
    log = roles_log(root)
    activity = timeline_rows(spans, running, done, log, now)
    wl = read_json(root, "jobs", "navigator-wakes.json")
    wakes = [{**w, "kind": str(w.get("when") or "").partition(":")[0], "fired": wake_fired(w, hl.get("nav_fired", []))}
             for w in ((wl.get("wakes") if isinstance(wl, dict) else None) or []) if isinstance(w, dict)]
    lanes = []
    for name, c in sorted(hl.get("lanes", {}).items()):
        cp = read_json(root, "docs", "claims", "lane", name, "checkpoint.json")
        charter = read_json(root, "docs", "claims", "lane", f"{name}.json")
        on_close = re.search(r"on-close:\s*([^;]+)", str(charter.get("value", ""))) if isinstance(charter, dict) else None
        lanes.append({"on_close": on_close[1].strip() if on_close else None,
                      "wakes": [w for w in wakes if w["kind"] in ("checkpoint", "lane")
                                and str(w.get("when")).partition(":")[2] == name],"name": name, "kind": c.get("kind"), "step": c.get("step"), "cap": c.get("cap"),
                      "end": c.get("end"), "opened": c.get("opened"), "cpu_h": hl.get("lane_cpu_h", {}).get(name),
                      "checkpoint": cp.get("value") if isinstance(cp, dict) else None,
                      "checkpoint_at": cp.get("at") if isinstance(cp, dict) else None})
    digests = sorted(glob.glob(os.path.join(root, "docs", "digest", "*.md")))
    return {"week": week_cost(root, now), "now": now, "health": hl, "sessions": sessions, "running": running, "pending": jobs_in(root, "pending"),
            "done": done, "log": log, "recent": None if log is None else log[:RECENT],
            "by_session": by_session, "records": set(records(root)), "lanes": lanes, "activity": activity,
            "wakes": None if wl is None else wakes, "closed": closed_lanes(root, set(hl.get("lanes", {}))),
            "candidates": candidates(root),
            "digest": os.path.basename(digests[-1]) if digests else None}


def week_cost(root, now):
    """The estimated cost of the runs started in the last 7 days: total,
    by role, the runs with a log, and owner chats (no log, not counted)."""
    start = now - datetime.timedelta(days=7)
    index = usage_index(root)
    out = {"cost": 0.0, "by_role": {}, "sessions": 0, "chats": 0}
    for name in records(root):
        rec = read_json(root, "jobs", "roles", name)
        t = health.parse_time(rec.get("started")) if isinstance(rec, dict) else None
        if t is None or t < start:
            continue
        if rec.get("chat"):
            out["chats"] += 1
            continue
        c = run_cost(root, name, rec, index)
        if c is None:
            continue
        out["sessions"] += 1
        role = str(rec.get("role") or "?")
        out["by_role"][role] = out["by_role"].get(role, 0.0) + (c["cost"] or 0.0)
        out["cost"] += c["cost"] or 0.0
    return out


def main_arg(name, args):
    """The one argument that says what a tool call did."""
    if not isinstance(args, dict):
        return ""
    for key in {"Bash": ["command"], "PowerShell": ["command"]}.get(name, []) + \
            ["file_path", "path", "pattern", "skill", "key", "url", "query", "description", "prompt"]:
        if isinstance(args.get(key), str):
            return args[key].strip().splitlines()[0] if args[key].strip() else ""
    for v in args.values():
        if isinstance(v, str) and v.strip():
            return v.strip().splitlines()[0]
    return ""


def output_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return "" if content is None else json.dumps(content)


def tool_input(name, args):
    """A tool call's whole input: a shell command as it is, anything else as indented JSON."""
    if name in ("Bash", "PowerShell") and isinstance(args, dict) and isinstance(args.get("command"), str):
        return args["command"]
    return json.dumps(args, indent=2, ensure_ascii=False)


def cut(text):
    """(text cut at OUTPUT_MAX bytes, whether it was cut)."""
    raw = text.encode("utf-8")
    return raw[:OUTPUT_MAX].decode("utf-8", errors="ignore"), len(raw) > OUTPUT_MAX


def conversation(path):
    """A stream-json log as a list of items, in order: {"kind": "text"},
    {"kind": "tool"} (name, arg, its whole input and output once it came,
    each cut when over OUTPUT_MAX, error), {"kind": "turn"} where a turn
    ended and more followed (a background task woke the session), and last
    {"kind": "result"} (ok, or the error type; None while nothing came after
    the last turn end, or there is none). Thinking, hooks and other system
    lines are skipped."""
    items, tools = [], {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue  # a line still being written
            if not isinstance(d, dict):
                continue
            t = d.get("type")
            if t == "result":
                err = d.get("is_error") or d.get("subtype") != "success"
                items.append({"kind": "turn", "ok": not err, "error": (d.get("subtype") or "error") if err else None,
                              "text": d.get("result") if isinstance(d.get("result"), str) else ""})
                continue
            if t not in ("assistant", "user"):
                continue
            content = (d.get("message") or {}).get("content")
            if isinstance(content, str):
                content = [{"type": "text", "text": content}] if t == "assistant" else []
            for b in content or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and t == "assistant" and b.get("text", "").strip():
                    items.append({"kind": "text", "text": b["text"]})
                elif b.get("type") == "tool_use":
                    full, input_cut = cut(tool_input(b.get("name"), b.get("input")))
                    item = {"kind": "tool", "name": b.get("name", "?"), "arg": main_arg(b.get("name"), b.get("input")),
                            "input": full, "input_cut": input_cut, "output": None, "cut": False, "error": False}
                    tools[b.get("id")] = item
                    items.append(item)
                elif b.get("type") == "tool_result" and b.get("tool_use_id") in tools:
                    item = tools[b["tool_use_id"]]
                    item["output"], item["cut"] = cut(output_text(b.get("content")))
                    item["error"] = bool(b.get("is_error"))
    if items and items[-1]["kind"] == "turn":  # the last turn end, with nothing after it, is the outcome
        items.append({**items.pop(), "kind": "result"})
    else:
        items.append({"kind": "result", "ok": None, "error": None, "text": ""})
    return items


# ---- pages ----

E = html.escape

CSS = """
:root{color-scheme:light dark;--page:#f6f6f3;--card:#fff;--ink:#141413;--ink2:#52514e;--mute:#898781;--line:#e4e3dc;--soft:#f1f0eb;
--code:#f4f3ee;--ring:rgba(11,11,11,.08);--shadow:0 1px 2px rgba(11,11,11,.04),0 2px 8px rgba(11,11,11,.04);
--good:#0ca30c;--good-ink:#006300;--good-bg:#e6f4e6;--warn:#fab219;--warn-ink:#7a5200;--warn-bg:#fdf3dc;
--bad:#d03b3b;--bad-ink:#a3201f;--bad-bg:#fbe9e8;--serious:#ec835a;--serious-ink:#9a3f17;--serious-bg:#fcede6;
--accent:#2a78d6;--track:#ebeae4;--chat:#a3a196;--r-steward:#2a78d6;--r-lanes:#1baf7a;--r-navigator:#6250d6;--r-launcher:#a9a79e;--r-other:#c3c2b7}
@media (prefers-color-scheme: dark){:root{--page:#0f0f0e;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--mute:#8f8d86;--line:#2c2c2a;
--soft:#222220;--code:#141413;--chat:#6f6d66;--ring:rgba(255,255,255,.08);--shadow:none;--good-ink:#3fc63f;--good-bg:#132713;--warn-ink:#fab219;
--warn-bg:#2b230f;--bad-ink:#ff8a85;--bad-bg:#2e1514;--serious-ink:#f0a07f;--serious-bg:#2d1b13;--accent:#3987e5;--track:#2c2c2a;
--r-steward:#3987e5;--r-lanes:#199e70;--r-navigator:#9085e9;--r-launcher:#6f6d66;--r-other:#4a4945}}
*{box-sizing:border-box}
body{background:var(--page);color:var(--ink);margin:0;font:14px/1.5 "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;
-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.mono,code,pre{font-family:"Cascadia Mono",Consolas,monospace;font-size:12.5px}
header.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--page) 88%,transparent);backdrop-filter:blur(8px);
border-bottom:1px solid var(--line)}
.bar{max-width:1180px;margin:0 auto;padding:10px 20px;display:flex;align-items:center;gap:20px;flex-wrap:wrap}
.brand{font-weight:650;letter-spacing:-.01em;color:var(--ink)}
nav{display:flex;gap:2px;flex-wrap:wrap}
nav a{color:var(--ink2);padding:5px 10px;border-radius:6px}nav a:hover{background:var(--soft);text-decoration:none}
nav a.on{background:var(--card);color:var(--ink);box-shadow:inset 0 0 0 1px var(--ring)}
.stamp{margin-left:auto;color:var(--mute);font-size:12.5px;display:flex;align-items:center;gap:6px}
.live{width:7px;height:7px;border-radius:50%;background:var(--good);box-shadow:0 0 0 3px var(--good-bg)}
main{max-width:1180px;margin:0 auto;padding:20px}
h1{font-size:22px;letter-spacing:-.015em;margin:4px 0 16px;font-weight:650}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--mute);font-weight:600;margin:0 0 12px;
display:flex;align-items:baseline;gap:8px}
h2 .age,h2 a{text-transform:none;letter-spacing:0;font-weight:400}h2 a{margin-left:auto}
h3{font-size:15px;margin:14px 0 6px}h4{font-size:14px;margin:12px 0 4px}
.age{color:var(--mute);font-size:12.5px}
.card{background:var(--card);border-radius:10px;box-shadow:inset 0 0 0 1px var(--ring),var(--shadow);padding:16px 18px;margin:0 0 16px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:16px;align-items:start}.cols>.card{margin:0}
.stack{display:flex;flex-direction:column;gap:16px;min-width:0}.stack>.card{margin:0}
.row-gap{height:16px}
.pill{display:inline-flex;align-items:center;gap:5px;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:500;
background:var(--soft);color:var(--ink2);white-space:nowrap}
.pill.good{background:var(--good-bg);color:var(--good-ink)}.pill.warn{background:var(--warn-bg);color:var(--warn-ink)}
.pill.bad{background:var(--bad-bg);color:var(--bad-ink)}.pill.serious{background:var(--serious-bg);color:var(--serious-ink)}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;flex:none;background:var(--r-other)}
.role{display:inline-flex;align-items:center;gap:6px;font-weight:600;color:var(--ink)}
.role-steward .dot{background:var(--r-steward)}.role-lanes .dot{background:var(--r-lanes)}
.role-navigator .dot{background:var(--r-navigator)}.role-launcher .dot{background:var(--r-launcher)}
.hero{display:flex;gap:16px;align-items:flex-start}
.badge{width:44px;height:44px;border-radius:12px;display:grid;place-items:center;font-size:22px;font-weight:700;flex:none}
.badge.good{background:var(--good-bg);color:var(--good-ink)}.badge.bad{background:var(--bad-bg);color:var(--bad-ink)}
.badge.warn{background:var(--warn-bg);color:var(--warn-ink)}
.hero .title{font-size:19px;font-weight:650;letter-spacing:-.01em}.hero .sub{color:var(--mute);font-size:12.5px;margin-top:2px}
.issues{margin:14px 0 0;padding:0;list-style:none;border-top:1px solid var(--line)}
.issues li{display:grid;grid-template-columns:76px 130px 1fr;gap:10px;align-items:baseline;padding:8px 0;border-bottom:1px solid var(--line)}
.issues li:last-child{border-bottom:0}.issues .name{font-weight:600}.issues .fix{color:var(--ink2)}
.list{display:flex;flex-direction:column}.item{padding:10px 0;border-top:1px solid var(--line)}.item:first-child{border-top:0;padding-top:0}
.item .head{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.item .meta{color:var(--mute);font-size:12.5px;margin-top:3px}
.item .go{margin-left:auto;font-size:13px}
.empty{color:var(--mute);padding:6px 0}
.meter{display:flex;align-items:center;gap:10px;margin-top:8px}
.track{flex:1;height:6px;border-radius:3px;background:var(--track);overflow:hidden}
.fill{height:100%;border-radius:3px;background:var(--accent)}.fill.over{background:var(--serious)}
.meter .num{font-size:12.5px;color:var(--ink2);white-space:nowrap;font-variant-numeric:tabular-nums}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.sub-h{font-size:12px;color:var(--mute);margin:16px 0 6px;font-weight:600;text-transform:uppercase;letter-spacing:.05em}
.lane .step{color:var(--ink2);margin-top:6px}
.clamp{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
details.more>summary{list-style:none;cursor:pointer}details.more>summary::-webkit-details-marker{display:none}
details.more[open] .clamp{-webkit-line-clamp:unset;display:block}
.day{font-size:12px;font-weight:600;color:var(--mute);margin:14px 0 2px;text-transform:uppercase;letter-spacing:.05em}
.day:first-child{margin-top:0}
.ev{display:grid;grid-template-columns:48px 96px 1fr;gap:10px;padding:7px 0;border-bottom:1px solid var(--line);align-items:baseline}
.ev .t{color:var(--mute);font-variant-numeric:tabular-nums;font-size:12.5px}.ev .msg{color:var(--ink2)}
.ev .open{white-space:nowrap;margin-left:6px;font-size:12.5px}
.sid{color:var(--mute);font-size:11.5px}.nowrap{white-space:nowrap}
td .meter{min-width:170px;margin-top:0}td .clamp{-webkit-line-clamp:2}
table{border-collapse:collapse;width:100%}
th{text-align:left;font-size:12px;font-weight:600;color:var(--mute);padding:6px 10px 6px 0;border-bottom:1px solid var(--line)}
td{padding:8px 10px 8px 0;border-bottom:1px solid var(--line);vertical-align:top}tr:last-child td{border-bottom:0}
td.detail{max-width:420px;word-break:break-word;color:var(--ink2)}
tr:target td{background:var(--warn-bg)}
.filters{display:flex;gap:12px;flex-wrap:wrap;align-items:center;font-size:12.5px;color:var(--ink2);margin-bottom:10px}
.filters select,.filters button{font:inherit;padding:2px 6px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.pager{display:flex;gap:14px;align-items:center;margin:8px 0;font-size:13px}
.state{display:inline-flex;align-items:center;gap:6px;font-weight:600;white-space:nowrap}
.state.green{color:var(--good-ink)}.state.red{color:var(--bad-ink)}
.prose p{margin:0 0 8px}.prose ul,.prose ol{margin:0 0 8px;padding-left:22px}.prose :last-child{margin-bottom:0}
.prose code{background:var(--code);padding:1px 4px;border-radius:4px}
.tablewrap{overflow-x:auto;margin:0 0 8px}table.md{width:auto;font-size:13px}table.md th,table.md td{padding:4px 14px 4px 0}
table.md th{color:var(--ink);border-bottom:1px solid var(--line)}table.md td{border-bottom:1px solid var(--line)}
table.md tr:last-child td{border-bottom:0}table.md td{font-variant-numeric:tabular-nums}
pre{background:var(--code);border-radius:8px;padding:10px 12px;white-space:pre-wrap;word-break:break-word;margin:6px 0;
max-height:520px;overflow:auto}
.convo{max-width:900px}
.say{background:var(--card);border-radius:10px;box-shadow:inset 0 0 0 1px var(--ring),var(--shadow);padding:12px 16px;margin:12px 0}
.tools{border-left:2px solid var(--line);margin:8px 0 8px 10px;padding-left:12px}
.tool>summary{display:flex;gap:8px;align-items:center;padding:4px 0;cursor:pointer;list-style:none;min-width:0}
.tool>summary::-webkit-details-marker{display:none}
.tool>summary::before{content:"\\25B8";color:var(--mute);font-size:11px;width:10px;flex:none}
.tool[open]>summary::before{content:"\\25BE"}
.tool .name{font-weight:600;font-size:12px;padding:1px 7px;border-radius:5px;background:var(--soft);flex:none}
.tool .arg{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--ink2);min-width:0;flex:1}
.tool .size{color:var(--mute);font-size:12px;flex:none}
.tool .cap{font-size:11.5px;color:var(--mute);margin:6px 0 -2px;text-transform:uppercase;letter-spacing:.05em}
.turn{display:flex;align-items:center;gap:10px;color:var(--mute);font-size:12px;margin:14px 0}
.turn::before,.turn::after{content:"";flex:1;border-top:1px solid var(--line)}
.outcome{display:flex;gap:12px;align-items:flex-start}
.facts{display:flex;gap:18px;flex-wrap:wrap;color:var(--ink2);font-size:13px;margin-top:10px}.facts b{color:var(--ink);font-weight:600}
.digest{max-width:900px}
.strip{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-top:14px;font-size:12px;color:var(--mute)}
.strip .grp{display:flex;gap:3px;align-items:center}.strip .grp b{font-weight:600;margin-right:4px}
.m{width:14px;height:14px;border-radius:3px;display:inline-block;background:var(--good);opacity:.85}
.m.red{background:var(--bad);opacity:1}.strip a{color:var(--mute)}
.mlabel{font-size:11.5px;color:var(--mute);width:34px;flex:none}
.gtools{display:flex;gap:6px;margin:-4px 0 8px 94px}.gtools[hidden]{display:none}
.gtools button{border:0;cursor:pointer;font:inherit;font-size:12px}.gtools button:hover{background:var(--line);color:var(--ink)}
.gantt{display:grid;grid-template-columns:84px minmax(0,1fr);gap:10px;margin-top:4px}
.glabel{font-size:12.5px;display:flex;align-items:center;gap:6px;color:var(--ink2);margin:6px 0}
.gscroll{overflow-x:auto;overflow-y:hidden;cursor:grab;scrollbar-width:thin;overscroll-behavior-x:contain}
.gscroll.drag{cursor:grabbing;user-select:none}.gscroll.drag .gbar{pointer-events:none}
.ginner{position:relative;min-width:100%}
.gtrack{position:relative;height:18px;background:var(--soft);border-radius:4px;margin:6px 0}
.gbar{position:absolute;top:3px;height:12px;border-radius:3px;min-width:4px;background:var(--rc,var(--r-other));display:block}
.gbar:hover{outline:2px solid var(--ink);outline-offset:1px;text-decoration:none}
.gbar{container-type:inline-size;overflow:hidden}
.gl{display:block;font-size:10px;line-height:12px;padding:0 4px;color:#fff;white-space:nowrap;overflow:hidden;font-weight:600}
@container (max-width:56px){.gl{display:none}}
.gbar.live{background:repeating-linear-gradient(135deg,var(--rc) 0 5px,color-mix(in srgb,var(--rc) 55%,transparent) 5px 10px)}
.gbar.bad{background:var(--bad)}.gbar.chat{--rc:var(--chat);background:var(--chat)}
.gbar.chat.live{background:repeating-linear-gradient(135deg,var(--chat) 0 5px,color-mix(in srgb,var(--chat) 55%,transparent) 5px 10px)}
.gmark{position:absolute;top:2px;width:3px;height:14px;border-radius:2px;background:var(--r-steward)}
.gmark:hover{outline:2px solid var(--ink)}
.gaxis{position:relative;height:16px;font-size:11px;color:var(--mute)}
.gaxis span{position:absolute;transform:translateX(-50%);white-space:nowrap}
.ggrid{position:absolute;top:0;bottom:16px;left:0;right:0;pointer-events:none}
.ggrid i{position:absolute;top:0;bottom:0;border-left:1px dashed var(--line)}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--mute);margin-top:8px;margin-left:94px}
.legend span{display:inline-flex;align-items:center;gap:6px}.legend .sw{width:18px;height:10px;border-radius:2px;display:inline-block}
.r-steward{--rc:var(--r-steward)}.r-lanes{--rc:var(--r-lanes)}.r-navigator{--rc:var(--r-navigator)}.r-jobs{--rc:var(--r-launcher)}
@media (max-width:640px){.issues li{grid-template-columns:1fr}.ev{grid-template-columns:44px 1fr}.ev .who{display:none}
.cols{grid-template-columns:1fr}}
"""

TIMELINE_JS = r"""
(function(){
var g=document.querySelector('.gantt[data-t0]');if(!g)return;
var sc=g.querySelector('.gscroll'),inner=g.querySelector('.ginner'),grid=g.querySelector('.ggrid'),axis=g.querySelector('.gaxis');
var tools=document.querySelector('.gtools'),viewLabel=document.querySelector('.gview');
var t0=+g.dataset.t0,t1=+g.dataset.t1,full=t1-t0,MIN=3600,span=Math.min(86400,full),start=t1-span;
var off=-new Date().getTimezoneOffset()*60;
var STEPS=[900,1800,3600,7200,10800,21600,43200,86400,172800,604800];
var MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function px(){return inner.offsetWidth;}
function rightGap(){return px()-sc.clientWidth;}
function readLeft(){return rightGap()+sc.scrollLeft;}  /* rtl: scrollLeft is 0 at the right end, negative leftwards */
function writeLeft(p){sc.scrollLeft=p-rightGap();}
function pad(n){return (n<10?'0':'')+n;}
function fmt(t,withDate){var d=new Date(t*1000);var hm=pad(d.getHours())+':'+pad(d.getMinutes());
  var day=MON[d.getMonth()]+' '+d.getDate();return withDate===2?day:(withDate?day+' '+hm:hm);}
function live(){return t1-(start+span)<=span*0.02;}
function ticks(){
  var step=STEPS[STEPS.length-1];for(var i=0;i<STEPS.length;i++){if(span/STEPS[i]<=10){step=STEPS[i];break;}}
  var a=start-span,b=start+2*span,t=Math.ceil((a+off)/step)*step-off,gh='',ah='';
  for(;t<=b;t+=step){if(t<t0||t>t1)continue;var x=((t-t0)/full*100).toFixed(4);
    var mid=((t+off)%86400)===0;
    gh+='<i style="left:'+x+'%"></i>';
    ah+='<span style="left:'+x+'%">'+fmt(t,step>=86400?2:(mid?1:0))+'</span>';}
  grid.innerHTML=gh;axis.innerHTML=ah;
  if(viewLabel)viewLabel.textContent=live()?'last '+human(span):fmt(start,1)+' \u2013 '+fmt(start+span,1);
}
function human(s){return s>=172800?(s/86400).toFixed(s%86400?1:0)+' d':(s/3600).toFixed(s%3600?1:0)+' h';}
function save(){var h='#t='+Math.round(start)+','+Math.round(start+span)+(live()?'&live':'');
  try{history.replaceState(null,'',h);}catch(e){}}
function apply(s,sp){
  span=Math.max(MIN,Math.min(full,sp));start=Math.max(t0,Math.min(t1-span,s));
  inner.style.width=(full/span*100).toFixed(4)+'%';
  if(px())writeLeft((start-t0)/full*px());ticks();save();  /* no width yet (hidden): the ResizeObserver applies it later */
}
function fromScroll(){if(!px())return;start=t0+readLeft()/px()*full;start=Math.max(t0,Math.min(t1-span,start));ticks();save();}
var m=/#t=(\d+),(\d+)(&live)?/.exec(location.hash);
if(m){var a=+m[1],b=+m[2];if(b>a){if(m[3])apply(t1-(b-a),b-a);else apply(a,b-a);}else apply(start,span);}
else apply(start,span);
var pending=false;
sc.addEventListener('scroll',function(){if(pending)return;pending=true;requestAnimationFrame(function(){pending=false;fromScroll();});});
sc.addEventListener('wheel',function(e){
  if(!e.deltaY||Math.abs(e.deltaX)>Math.abs(e.deltaY))return;
  e.preventDefault();
  var r=sc.getBoundingClientRect();if(!r.width)return;var f=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width));
  var at=start+f*span,ns=span*Math.pow(1.0015,e.deltaY);ns=Math.max(MIN,Math.min(full,ns));
  apply(at-f*ns,ns);
},{passive:false});
var down=null,dragged=false;
sc.addEventListener('pointerdown',function(e){if(e.button!==0)return;down={x:e.clientX,left:readLeft(),id:e.pointerId};dragged=false;});
sc.addEventListener('pointermove',function(e){
  if(!down)return;var dx=e.clientX-down.x;
  if(!dragged&&Math.abs(dx)>4){dragged=true;sc.classList.add('drag');try{sc.setPointerCapture(down.id);}catch(_){}}
  if(dragged){writeLeft(down.left-dx);}
});
function up(){if(!down)return;down=null;if(dragged){setTimeout(function(){sc.classList.remove('drag');dragged=false;},0);}}
sc.addEventListener('pointerup',up);sc.addEventListener('pointercancel',up);
sc.addEventListener('click',function(e){if(dragged){e.preventDefault();e.stopPropagation();}},true);
if(tools){tools.hidden=false;tools.addEventListener('click',function(e){
  var b=e.target.closest('button');if(!b)return;
  if(b.dataset.now)apply(t1-span,span);else{var sp=+b.dataset.span;apply(live()?t1-sp:start+span/2-sp/2,sp);}});}
if(window.ResizeObserver)new ResizeObserver(function(){apply(start,span);}).observe(sc);
})();
"""
REFRESH_JS = "setTimeout(function(){location.reload();}," + str(REFRESH_S * 1000) + ");"

NAV = [("/", "Overview"), ("/log", "Role runs"), ("/queue", "Queue"), ("/health", "Health"), ("/digest", "Digest"),
       ("http://127.0.0.1:8765", "Explorer")]  # explore.py (docs/specs/explorer-v2.md)
UUID = re.compile(r"\b(?:[a-z]+-)?([0-9a-f]{8})-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
LOG_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) (\S+) (.*)$")


def ago(m):
    if m is None:
        return "unknown age"
    if m < 0:
        return "in the future"
    if m < 90:
        return f"{m:.0f} min ago"
    return f"{m / 60:.1f} h ago" if m < 48 * 60 else f"{m / 1440:.1f} days ago"


def span(m):
    """A duration in minutes, short."""
    if m is None:
        return "?"
    return f"{m:.0f} min" if m < 90 else f"{m / 60:.1f} h"


def page(title, body, active=None, now=None, refresh=False):
    meta = (f'<noscript><meta http-equiv="refresh" content="{REFRESH_S}"></noscript><script>{REFRESH_JS}</script>'
            if refresh else "")  # the script reloads the same URL, so the timeline's view (#t=...) is kept
    nav = "".join(f'<a href="{href}"{" class=on" if href == active else ""}>{E(label)}</a>' for href, label in NAV)
    stamp = ""
    if now is not None:
        live = '<span class="live"></span>' if refresh else ""
        stamp = (f'<span class="stamp">{live}read {E(now.strftime("%H:%M"))}'
                 f'{f"; refreshes every {REFRESH_S} s" if refresh else ""}</span>')
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'{meta}<title>{E(title)}</title><style>{CSS}</style></head><body>'
            f'<header class="top"><div class="bar"><a class="brand" href="/">sts-for-ai</a><nav>{nav}</nav>{stamp}</div></header>'
            f'<main>{body}</main></body></html>')


def inline(text):
    """Escaped text with `code` and **bold**."""
    t = E(text)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)


TABLE_SEP = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$")


def md_table(lines):
    """Markdown table lines as a table: the row before a |---| line is the
    header; short rows are padded; an escaped pipe stays a pipe inside its cell."""
    def cells(line):
        line = line.strip()
        line = line[1:] if line.startswith("|") else line
        line = line[:-1] if line.endswith("|") and not line.endswith("\\|") else line
        return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)]
    head = len(lines) > 1 and TABLE_SEP.match(lines[1]) is not None
    rows = [cells(l) for i, l in enumerate(lines) if not (head and i == 1)]
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    html_rows = [("th" if head and i == 0 else "td", r) for i, r in enumerate(rows)]
    body = "".join("<tr>" + "".join(f"<{t}>{inline(c)}</{t}>" for c in r) + "</tr>" for t, r in html_rows)
    return f'<div class="tablewrap"><table class="md">{body}</table></div>'


def md(text):
    """A small, safe markdown subset: headings, lists, fenced code, tables,
    paragraphs. Everything is escaped first; nothing from the text becomes a
    tag or a link."""
    out, para, lst, fence, tbl = [], [], None, None, []

    def flush():
        nonlocal para, lst
        if tbl:
            out.append(md_table(tbl))
            tbl.clear()
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para = []
        if lst:
            out.append(f"<{lst[0]}>{''.join(f'<li>{inline(i)}</li>' for i in lst[1])}</{lst[0]}>")
            lst = None
    for line in text.splitlines():
        if fence is not None:
            if line.strip().startswith("```"):
                out.append(f"<pre>{E(chr(10).join(fence))}</pre>")
                fence = None
            else:
                fence.append(line)
            continue
        s = line.strip()
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        bullet = re.match(r"^[-*]\s+(.*)$", s)
        num = re.match(r"^\d+[.)]\s+(.*)$", s)
        if s.startswith("```"):
            flush()
            fence = []
        elif not s:
            flush()
        elif m:
            flush()
            level = 3 if len(m.group(1)) <= 2 else 4
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
        elif bullet or num:
            kind = "ul" if bullet else "ol"
            if para or tbl or (lst and lst[0] != kind):
                flush()
            lst = lst or (kind, [])
            lst[1].append((bullet or num).group(1))
        elif lst and line.startswith((" ", "\t")):
            lst[1][-1] += " " + s
        elif s.startswith("|"):
            if para or lst:
                flush()
            tbl.append(s)
        else:
            if lst or tbl:
                flush()
            para.append(s)
    if fence is not None:
        out.append(f"<pre>{E(chr(10).join(fence))}</pre>")
    flush()
    return f'<div class="prose">{"".join(out)}</div>'


def role_tag(role):
    r = str(role or "?")
    known = r if r in ("steward", "lanes", "navigator", "launcher") else "other"
    return f'<span class="role role-{known}"><span class="dot"></span>{E(r)}</span>'


def meter(value, total, unit):
    if value is None or not total:
        return f'<div class="meter"><div class="track"></div><span class="num">{"?" if value is None else f"{value:g}"} {E(unit)}</span></div>'
    share = value / total
    over = " over" if share > 1 else ""
    return (f'<div class="meter"><div class="track"><div class="fill{over}" style="width:{min(share, 1) * 100:.1f}%"></div></div>'
            f'<span class="num">{value:g} of {total:g} {E(unit)}</span></div>')


def log_target(line, g):
    """The session record a roles.log line belongs to, when its log exists."""
    target = None
    for name in g["records"]:
        if f"({name})" in line:
            target = name
    if target is None:
        parts = line.split()
        if len(parts) >= 4:
            target = g["by_session"].get(parts[3]) or g["by_session"].get(parts[3].removeprefix(parts[2] + "-"))
    return target if target and os.path.exists(log_path(g["root"], target)) else None


def timeline(lines, g):
    """roles.log lines (newest first) grouped by day: time, role, message;
    long messages open on click; a session's line links to its page."""
    out, day = [], None
    for line in lines:
        m = LOG_LINE.match(line)
        date, t, who, msg = m.groups() if m else ("", "", "", line)
        if date != day:
            day = date
            out.append(f'<div class="day">{E(date or "undated")}</div>')
        target = log_target(line, g)
        text = UUID.sub(lambda u: "\0" + u.group(1) + "\1", msg)  # session ids shortened to their first 8 hex
        text = E(text).replace("\0", '<span class="sid mono">').replace("\1", "</span>")
        link = f' <a class="open" href="/session/{E(target)}">open session &rarr;</a>' if target else ""
        out.append(f'<div class="ev"><span class="t">{E(t)}</span><span class="who">{role_tag(who) if who else ""}</span>'
                   f'<details class="more"><summary><span class="msg clamp">{text}{link}</span></summary></details></div>')
    return "".join(out)


def health_card(g):
    h = g["health"]
    if h["state"] == "missing":
        return ('<section class="card"><div class="hero"><div class="badge warn">?</div><div>'
                '<div class="title">Health unknown</div><div class="sub">missing: jobs/health.json is not there or not readable</div>'
                '</div></div></section>')
    sub = f'report {E(ago(h["age_min"]))} &middot; steward ran {E(ago(h["steward_age_min"]))}'
    n = len(h["red"])
    if h["state"] == "stale":
        badge, title = '<div class="badge warn">!</div>', "Health report is stale"
        sub = f'stale: the report is {E(ago(h["age_min"]))} (over {HEALTH_STALE_H:g} h); the launcher may be down &middot; ' + sub
    elif h["state"] == "green":
        badge, title = '<div class="badge good">&#10003;</div>', "All green"
    else:
        badge, title = '<div class="badge bad">&#10005;</div>', f'{n} red: {", ".join(str(r["name"]) for r in h["red"])}'
    rows = "".join(
        f'<li><span>{"<span class=\"pill bad\">blocker</span>" if r["kind"] == "blocker" else "<span class=\"pill serious\">work</span>"}</span>'
        f'<span class="name">{E(str(r["name"]))}</span><span class="fix">{E(str(r["fix"] or ""))}</span></li>' for r in h["red"])
    issues = f'<ul class="issues">{rows}</ul>' if rows else ""
    return (f'<section class="card"><div class="hero">{badge}<div><div class="title">{E(title)}</div>'
            f'<div class="sub">{sub}</div></div></div>{issues}{metric_strip(h["metrics"])}</section>')


def metric_strip(metrics):
    """One square per health metric, green or red; its name, value and fix on hover."""
    def sq(m):
        tip = f'{m.get("name")}: {m.get("state")}, value {json.dumps(m.get("value"))}' + (f'; fix: {m["fix"]}' if m.get("fix") else "")
        return f'<span class="m {"red" if m.get("state") != "green" else ""}" title="{E(tip)}"></span>'
    groups = [(k, [m for m in metrics if m.get("kind") == k]) for k in ("blocker", "work")]
    body = "".join(f'<span class="grp"><b>{"blockers" if k == "blocker" else "work"}</b>{"".join(sq(m) for m in ms)}</span>' for k, ms in groups if ms)
    return f'<div class="strip">{body}<a href="/health">every metric &rarr;</a></div>' if body else ""


def activity_card(g):
    """The history as a chart that opens on the last ACTIVITY_H hours: one
    row per role, bars for sessions and jobs, marks for steward runs;
    details on hover. The bars sit in % of the whole span inside an inner
    track as wide as the view's zoom needs; its scroller is right-to-left,
    so it opens at the present also without the script (TIMELINE_JS), which
    adds wheel zoom, drag, range buttons and ticks for the visible span."""
    a = g["activity"]
    t0, t1 = a["start"], a["end"]
    total = (t1 - t0).total_seconds()

    def x(t):
        return max(0.0, min(100.0, (t - t0).total_seconds() / total * 100))

    def bar(sp, top=3):
        left, width = x(sp["start"]), max(x(sp["end"]) - x(sp["start"]), 0.01)
        style = f'left:{left:.3f}%;width:{width:.3f}%;top:{top}px'
        tone = "".join(f" {t}" for t in sp["tone"].split() if t in ("live", "bad", "chat"))
        label = f'<span class="gl">{E(sp["lane"])}</span>' if sp.get("lane") else ""
        if sp.get("record"):
            return (f'<a class="gbar{tone}" style="{style}" href="/session/{E(sp["record"])}" title="{E(sp["tip"])}">'
                    f'{label}</a>')
        if sp.get("href"):
            return f'<a class="gbar{tone}" style="{style}" href="{E(sp["href"])}" title="{E(sp["tip"])}"></a>'
        return f'<span class="gbar{tone}" style="{style}" title="{E(sp["tip"])}"></span>'
    ticks, t = [], (t0 + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    while t < t1:
        if t.hour % 3 == 0:
            ticks.append(t)
        t += datetime.timedelta(hours=1)
    labels, tracks = [], []

    def row(label, height, body, cls=""):
        style = f' style="height:{height}px"'
        labels.append(f'<div class="glabel"{style}>{label}</div>')
        tracks.append(f'<div class="gtrack{cls}"{style}>{body}</div>')
    for role, spans in a["rows"].items():
        known = role if role in ("steward", "lanes", "navigator") else "jobs"
        n = a["row_tracks"].get(role, 1)
        row(role_tag(role), 6 + 14 * n if n > 1 else 18,
            "".join(bar(sp, 3 + 14 * sp.get("track", 0)) for sp in spans), f" r-{known}")
    row(role_tag("steward"), 18,
        "".join(f'<span class="gmark" style="left:{x(m["at"]):.3f}%" title="{E(m["tip"])}"></span>' for m in a["steward"]))
    row('<span class="role"><span class="dot" style="background:var(--r-launcher)"></span>jobs</span>',
        6 + 14 * a["tracks"], "".join(bar(sp, 3 + 14 * sp["track"]) for sp in a["jobs"]), " r-jobs")
    grid = "".join(f'<i style="left:{x(t):.3f}%"></i>' for t in ticks)
    axis = "".join(f'<span style="left:{x(t):.3f}%">{t:%H:%M}</span>' for t in ticks)
    legend = ('<div class="legend"><span><i class="sw" style="background:var(--r-navigator)"></i>finished</span>'
              '<span class="r-navigator"><i class="sw gbar live" style="position:static"></i>running now</span>'
              '<span><i class="sw" style="background:var(--bad)"></i>failed or no outcome</span>'
              '<span><i class="sw" style="background:var(--chat)"></i>chat with the owner</span>'
              '<span><i class="sw" style="background:var(--r-steward);width:3px;height:12px"></i>steward run</span>'
              '<span>hover for details; click a bar to open it; wheel zooms, drag pans</span></div>')
    w = g["week"]
    tip = ", ".join(f"{r} ${c:.2f}" for r, c in sorted(w["by_role"].items())) or "no run with a log"
    tip += f"; owner chats not counted: no log ({w['chats']} in 7 days)" if w["chats"] else "; owner chats not counted: no log"
    week = (f'<span class="age" title="{E(tip)}">&asymp; ${w["cost"]:.2f} in the last 7 days ({w["sessions"]} sessions)'
            f'</span>')
    width = total / (ACTIVITY_H * 3600) * 100
    buttons = "".join(f'<button type="button" class="pill" data-span="{h * 3600}">{lab}</button>'
                      for h, lab in ((6, "6 h"), (24, "24 h"), (72, "3 d"), (168, "7 d")))
    tools = f'<div class="gtools" hidden>{buttons}<button type="button" class="pill" data-now="1">now</button></div>'
    return (f'<section class="card"><h2>Timeline <span class="gview">last {ACTIVITY_H} h</span> {week}</h2>{tools}'
            f'<div class="gantt" data-t0="{int(t0.timestamp())}" data-t1="{int(t1.timestamp())}">'
            f'<div class="glabels">{"".join(labels)}</div>'
            f'<div class="gscroll" dir="rtl"><div class="ginner" dir="ltr" style="width:{width:.2f}%">'
            f'<div class="ggrid">{grid}</div>{"".join(tracks)}<div class="gaxis">{axis}</div></div></div></div>'
            f'{legend}</section><script>{TIMELINE_JS}</script>')


def session_pills(s):
    """What a running session is: a chat with the owner, or its lane claim;
    and the session it resumes."""
    if s["chat"]:
        out = '<span class="pill">chat with the owner</span>'
    else:
        out = f'<span class="pill">lane {E(s["lane"])}</span>' if s["lane"] else '<span class="pill">no claim</span>'
    if s["resumed"]:
        out += f'<span class="pill mono" title="resumes session {E(s["resumed"])}">resumes {E(s["resumed"][:8])}</span>'
    return out


def wakes_card(g):
    """The navigator's wakes (jobs/navigator-wakes.json): kind, argument,
    when set, reason; fired ones (health.json wakes.navigator) marked."""
    head = '<h2>Navigator waits for</h2>'
    if g["wakes"] is None:
        return f'<section class="card">{head}<div class="empty">missing: jobs/navigator-wakes.json</div></section>'
    if not g["wakes"]:
        return f'<section class="card">{head}<div class="empty">No wake set.</div></section>'
    rows = []
    for w in g["wakes"]:
        arg = str(w.get("when") or "").partition(":")[2]
        state = ('<span class="pill good" title="health.json lists it under wakes.navigator: the launcher starts '
                 'the navigator on it">fired</span>' if w["fired"] else '<span class="pill">waiting</span>')
        rows.append(f'<div class="item"><div class="head"><span class="pill">{E(w["kind"] or "?")}</span>'
                    f'{f"<span class=mono>{E(arg)}</span>" if arg else ""}{state}'
                    f'<span class="age" style="margin-left:auto">set {E(ago(minutes(w.get("at"), g["now"])))}</span></div>'
                    f'<details class="more"><summary><div class="meta clamp">{E(str(w.get("why") or ""))}</div></summary>'
                    f'</details></div>')
    fired = sum(w["fired"] for w in g["wakes"])
    return (f'<section class="card"><h2>Navigator waits for <span class="age">{len(g["wakes"])} set, {fired} fired</span></h2>'
            f'<div class="list">{"".join(rows)}</div></section>')


def job_tip(j):
    """A job's tooltip: lane, threads, estimate and its note's first line."""
    note = str(j.get("note") or "").strip().splitlines()
    return (f'lane {j.get("lane")} · {j.get("threads", "?")} threads · estimate {span(j.get("estimate_min"))}'
            + (f' · {note[0]}' if note else ""))


def running_card(g):
    if g["sessions"]:
        rows = "".join(
            f'<div class="item"><div class="head">{role_tag(s["role"])}'
            f'{session_pills(s)}'
            f'<a class="go" href="/session/{E(s["record"])}">transcript &rarr;</a></div>'
            f'<div class="meta">started {E(ago(s["age_min"]))} &middot; <span class="mono">{E(str(s["model"]))}</span>'
            f'{" &middot; " + E(", ".join(map(str, s["why"]))) if s["why"] else ""}</div></div>' for s in g["sessions"])
        sess = f'<div class="list">{rows}</div>'
    else:
        sess = '<div class="empty">No role session running.</div>'
    if g["running"]:
        rows = []
        for j in g["running"]:
            est = j.get("estimate_min")
            run = None if j["run_min"] is None else round(j["run_min"])
            rows.append(f'<div class="item"><div class="head"><span class="mono" title="{E(job_tip(j))}">'
                        f'{E(str(j.get("id")))}</span>'
                        f'<span class="pill">{E(str(j.get("lane")))}</span>'
                        f'<span class="age" style="margin-left:auto">{E(str(j.get("threads", "?")))} threads</span></div>'
                        f'{meter(run, est if isinstance(est, (int, float)) else None, "min")}</div>')
        jobs = f'<div class="list">{"".join(rows)}</div>'
    else:
        jobs = '<div class="empty">No job running.</div>'
    pend = "".join(f'<span class="pill mono" title="{E(job_tip(j))}">{E(str(j.get("id")))}</span>' for j in g["pending"])
    pend = f'<div class="chips">{pend}</div>' if pend else '<div class="empty">Nothing pending.</div>'
    return (f'<section class="card"><h2>Running now <span class="age">read just now</span></h2>{sess}'
            f'<div class="sub-h">Jobs</div>{jobs}<div class="sub-h">Pending</div>{pend}</section>')


def days_left(end, now):
    try:
        d = (datetime.date.fromisoformat(str(end)) - now.date()).days
    except ValueError:
        return ""
    return "ends today" if d == 0 else (f"{d} days left" if d > 0 else f"{-d} days past end")


def lane_meters(l, now):
    """CPU-hours against the cap, and days used against the lane's span."""
    cpu = meter(l["cpu_h"], l["cap"], "CPU-h")
    opened = health.parse_time(l.get("opened"))
    try:
        end = datetime.datetime.combine(datetime.date.fromisoformat(str(l["end"])), datetime.time(23, 59), now.tzinfo)
    except ValueError:
        end = None
    if opened and end and end > opened:
        days = meter(round((now - opened).total_seconds() / 86400, 1), round((end - opened).total_seconds() / 86400, 1), "days")
    else:
        days = meter(None, None, "days")
    return (f'<div style="display:flex;align-items:center;gap:6px"><span class="mlabel">CPU</span><div style="flex:1">{cpu}</div></div>'
            f'<div style="display:flex;align-items:center;gap:6px"><span class="mlabel">time</span><div style="flex:1">{days}</div></div>')


def lanes_card(g):
    h = g["health"]
    if h["state"] == "missing":
        return '<section class="card"><h2>Lanes</h2><div class="empty">missing: jobs/health.json</div></section>'
    stale = " (stale)" if h["state"] == "stale" else ""
    head = f'<h2>Lanes <span class="age">from health.json, {E(ago(h["age_min"]))}{stale}</span></h2>'
    if not g["lanes"]:
        return f'<section class="card">{head}<div class="empty">No open lane.</div></section>'
    rows = []
    for l in g["lanes"]:
        cp_at = f' <span class="age">({E(str(l["checkpoint_at"]).split(" @ ")[0][:16].replace("T", " "))})</span>' \
            if l["checkpoint_at"] else ""
        rows.append(
            f'<div class="item lane"><div class="head"><b>{E(l["name"])}</b><span class="pill">{E(str(l["kind"]))}</span>'
            f'<span class="age" style="margin-left:auto">ends {E(str(l["end"]))} &middot; {E(days_left(l["end"], g["now"]))}</span></div>'
            f'{lane_meters(l, g["now"])}'
            f'<details class="more"><summary><div class="step clamp">{E(l["step"] or "no step yet")}</div></summary></details>'
            f'<div class="meta">last checkpoint: {E(l["checkpoint"] or "none yet")}{cp_at}</div>'
            f'<div class="chips"><span class="pill" title="what the lane worker does when it closes the lane">'
            f'on close: {E(l["on_close"] or "not set")}</span>'
            f'{"".join(wake_pill(w) for w in l["wakes"])}</div></div>')
    return f'<section class="card">{head}<div class="list">{"".join(rows)}</div></section>'


def wake_pill(w):
    """A navigator wake that waits on this lane, as a chip; its reason on hover."""
    tone = " good" if w["fired"] else ""
    return (f'<span class="pill{tone}" title="{E(str(w.get("why") or ""))}">navigator wakes on {E(w["kind"])}'
            f'{" (fired)" if w["fired"] else ""}</span>')


def closed_card(g):
    """Recently closed lanes with their end note (the last step fact)."""
    if not g["closed"]:
        return ""
    rows = "".join(
        f'<div class="item"><div class="head"><b>{E(l["name"])}</b><span class="pill">closed</span>'
        f'<span class="age" style="margin-left:auto">{E(ago(minutes(l["closed"], g["now"])))}</span></div>'
        f'<details class="more"><summary><div class="step clamp">{E(l["note"] or "no end note")}</div></summary></details>'
        f'<div class="meta">last checkpoint: {E(l["checkpoint"] or "none")}</div></div>' for l in g["closed"])
    return f'<section class="card"><h2>Recently closed lanes</h2><div class="list">{rows}</div></section>'


TONE = {"likely": "good", "even": "warn", "a long shot": "serious"}


def candidate_row(c, full):
    """One candidate lane: number, name, rating pill, goal and estimate;
    `full` adds its charter slot or queued jobs and its text (clamped,
    opens on click), else its text is the tooltip."""
    rating = (f'<span class="pill {TONE[c["rating"]]}" title="the navigator\'s rating">{E(c["rating"])}</span>'
              if c["rating"] else "")
    meta = " &middot; ".join(E(x) for x in (f'goal {c["goal"]}' if c["goal"] else None, c["cost"],
                                             f'source: {c["source"]}' if c["source"] else None) if x)
    head = (f'<div class="head"><span class="age mono">{c["n"]}</span><b>{E(c["name"])}</b>{rating}'
            f'<span class="age" style="margin-left:auto">{meta}</span></div>')
    if not full:
        return f'<div class="item" title="{E(c["text"][:400])}">{head}</div>'
    chips = ""
    if c["charter"]:
        chips += f'<span class="pill good" title="a ready charter: the lane can open as written">charter ready: {E(c["charter"])}</span>'
    if c["queued"]:
        chips += f'<a class="pill" href="/queue?lane=main">queued as a probe: jobs {E(c["queued"])}</a>'
    return (f'<div class="item lane">{head}<div class="chips">{chips}</div>'
            f'<details class="more"><summary><div class="step clamp">{E(c["text"])}</div></summary></details></div>')


def candidates_card(g):
    """The candidate lanes from docs/backlog.md: ready charters and queued
    probes in full, the rest one line each under a fold, by number."""
    cs = g["candidates"]
    if cs is None:
        return '<section class="card"><h2>Candidate lanes</h2><div class="empty">missing: docs/backlog.md</div></section>'
    head = '<h2>Candidate lanes <span class="age">from docs/backlog.md</span></h2>'
    if not cs:
        return f'<section class="card">{head}<div class="empty">No candidate in the backlog.</div></section>'
    top = [c for c in cs if c["charter"] or c["queued"]]
    rest = [c for c in cs if not (c["charter"] or c["queued"])]
    body = f'<div class="list">{"".join(candidate_row(c, True) for c in top)}</div>' if top else ""
    if rest:
        body += (f'<details><summary class="sub-h" style="cursor:pointer">{len(rest)} more candidates, by number '
                 f'(the backlog ranks them only in prose)</summary>'
                 f'<div class="list">{"".join(candidate_row(c, False) for c in rest)}</div></details>')
    return f'<section class="card">{head}{body}</section>'


def recent_card(g):
    if g["recent"] is None:
        return '<section class="card"><h2>Recent role runs</h2><div class="empty">missing: jobs/roles.log</div></section>'
    body = timeline(g["recent"], g) or '<div class="empty">No runs logged yet.</div>'
    return f'<section class="card"><h2>Recent role runs <a href="/log">all runs &rarr;</a></h2>{body}</section>'


def first_screen(g):
    return page("sts-for-ai dashboard",
                health_card(g) + activity_card(g) + f'<div class="cols"><div class="stack">{running_card(g)}{wakes_card(g)}{recent_card(g)}</div>'
                f'<div class="stack">{lanes_card(g)}{candidates_card(g)}{closed_card(g)}</div></div>', active="/", now=g["now"], refresh=True)


def tool_html(it):
    head = f'<span class="name mono">{E(it["name"])}</span><span class="arg mono" title="{E(it["arg"])}">{E(it["arg"])}</span>'
    given = (f'<div class="cap">input{", cut at 20 KB" if it.get("input_cut") else ""}</div>'
             f'<pre class="input">{E(it.get("input") or "")}</pre>')
    if it["output"] is None:
        return f'<details class="tool"><summary>{head}<span class="size">no output yet</span></summary>{given}</details>'
    size = len(it["output"].encode("utf-8"))
    label = "cut at 20 KB" if it["cut"] else (f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B")
    err = ' <span class="pill bad">error</span>' if it["error"] else ""
    return (f'<details class="tool"><summary>{head}{err}<span class="size">{label}</span></summary>'
            f'{given}<div class="cap">output</div><pre>{E(it["output"]) or "(empty)"}</pre></details>')


def turn_html(it):
    """A turn that ended with more after it: a thin divider."""
    how = "ok" if it["ok"] else E(str(it["error"]))
    return f'<div class="turn"><span>turn ended ({how})</span></div>'


def cost_fact(c, live):
    """Tokens in and out and the estimated cost of a run; the split on hover."""
    if not c or not c["turns"]:
        return '<span>tokens <b>none yet</b></span>'
    t = c["tokens"]
    tip = (f'input {t["input"]:,}, cache write {t["cache_write"]:,}, cache read {t["cache_read"]:,}, '
           f'output {t["output"]:,} (thinking {t["thinking"]:,})')
    money = "" if c["cost"] is None else f' &middot; &asymp; ${c["cost"]:.2f}'
    note = (" so far" if live else "") + (" (includes earlier runs)" if c["earlier"] else "")
    return (f'<span title="{E(tip)}"><b>{count(t["input"] + t["cache_write"] + t["cache_read"])} in &middot; '
            f'{count(t["output"])} out{money}{E(note)}</b></span>')


def session_page(root, name, now, ours=None):
    p = log_path(root, name)
    rec = read_json(root, "jobs", "roles", name) or {}
    ours = ours or roles.Launcher(main=root).ours
    live = not rec.get("ended") and bool(rec.get("pid")) and ours(rec)
    started, ended = health.parse_time(rec.get("started")), health.parse_time(rec.get("ended"))
    took = span((ended - started).total_seconds() / 60) if started and ended else None
    items = conversation(p) if os.path.exists(p) else None
    facts = [f'<span>model <b class="mono">{E(str(rec.get("model")))}</b></span>',
             f'<span>started <b>{E(str(rec.get("started", "?"))[:16].replace("T", " "))}</b></span>',
             f'<span>{"took <b>" + E(took) + "</b>" if took else "no end recorded"}</span>']
    if rec.get("effort"):
        facts.append(f'<span>effort <b>{E(str(rec["effort"]))}</b></span>')
    if rec.get("chat"):
        facts.append('<span><b>chat with the owner</b></span>')
    elif rec.get("why"):
        facts.append(f'<span>why <b>{E(", ".join(map(str, rec["why"])))}</b></span>')
    rid = resumed_id(rec)
    if rid:
        first = next((r for r in records(root) if r != name and first_session_id(log_path(root, r)) == rid), None)
        sid = f'<b class="mono" title="{E(rid)}">{E(rid[:8])}</b>'
        facts.append(f'<span>resumes {f'<a href="/session/{E(first)}">{sid}</a>' if first else sid}</span>')
    if items is not None:
        facts.append(f'<span><b>{sum(i["kind"] == "tool" for i in items)}</b> tool calls</span>')
        facts.append(cost_fact(run_cost(root, name, rec), live))
    head = (f'<section class="card"><div class="head" style="display:flex;gap:10px;align-items:center">'
            f'{role_tag(rec.get("role"))}<span class="age mono">{E(name)}</span></div>'
            f'<div class="facts">{"".join(facts)}</div></section>')
    if items is None:
        why = ("The owner talks to the navigator in a terminal (roles.py chat); a chat keeps no headless log. "
               "Its messages are in the resumed session's transcript.") if rec.get("chat") else "No log for this session."
        return page(name, head + f'<div class="empty">{E(why)}</div>', now=now)
    out, tools = [], []
    said = [i["text"].strip() for i in items if i["kind"] == "text"]
    last = said[-1] if said else None

    def flush():
        if tools:
            out.append(f'<div class="tools">{"".join(tools)}</div>')
            tools.clear()
    for it in items:
        if it["kind"] == "tool":
            tools.append(tool_html(it))
            continue
        flush()
        if it["kind"] == "text":
            out.append(f'<div class="say">{md(it["text"])}</div>')
        elif it["kind"] == "turn":
            out.append(turn_html(it))
        elif live:  # still running: never ok or an error, however the last turn ended
            if it["ok"] is not None:
                out.append(turn_html(it))
            ended = any(i["kind"] == "turn" for i in items) or it["ok"] is not None
            out.append('<section class="card outcome"><div class="badge warn">&hellip;</div><div><b>working</b>'
                       f'<div class="age">{"last turn ended; " if ended else ""}the session still runs</div></div></section>')
        elif it["ok"] is None:
            out.append('<section class="card outcome"><div class="badge warn">&hellip;</div><div><b>no result yet</b>'
                       '<div class="age">ended without a result line</div></div></section>')
        elif it["ok"]:  # the result repeats the last message: shown once
            text = it["text"] if it["text"] and it["text"].strip() != last else ""
            out.append(f'<section class="card outcome"><div class="badge good">&#10003;</div><div><b>ok</b>'
                       f'{md(text) if text else ""}</div></section>')
        else:
            out.append(f'<section class="card outcome"><div class="badge bad">&#10005;</div><div><b>error: {E(it["error"])}</b>'
                       f'{md(it["text"]) if it["text"] else ""}</div></section>')
    return page(name, head + f'<div class="convo">{"".join(out)}</div>', now=now)


def log_page(g):
    if g["log"] is None:
        return page("Role runs", '<div class="empty">missing: jobs/roles.log</div>', active="/log", now=g["now"])
    return page("Role runs", f'<h1>Role runs</h1><section class="card">{timeline(g["log"], g)}</section>',
                active="/log", now=g["now"])


def health_page(g):
    h = g["health"]
    if h["state"] == "missing":
        return page("Health", '<div class="empty">missing: jobs/health.json</div>', active="/health", now=g["now"])
    metrics = sorted(h["metrics"], key=lambda m: (m.get("kind") != "blocker", m.get("state") == "green"))
    rows = "".join(
        f'<tr><td class="nowrap"><b>{E(str(m.get("name")))}</b></td><td><span class="pill">{E(str(m.get("kind")))}</span></td>'
        f'<td><span class="state {"green" if m.get("state") == "green" else "red"}">'
        f'{"&#10003;" if m.get("state") == "green" else "&#10005;"} {E(str(m.get("state")))}</span></td>'
        f'<td class="mono">{E(json.dumps(m.get("value")))}</td>'
        f'<td class="detail mono">{E(json.dumps(m.get("detail"), ensure_ascii=False)) if m.get("detail") else ""}</td>'
        f'<td>{E(str(m.get("fix") or ""))}</td></tr>' for m in metrics)
    stale = " (stale)" if h["state"] == "stale" else ""
    return page("Health", f'<h1>Health <span class="age">report {E(ago(h["age_min"]))}{stale}</span></h1>'
                f'<section class="card"><table><tr><th>metric</th><th>kind</th><th>state</th><th>value</th><th>detail</th>'
                f'<th>fix</th></tr>{rows}</table></section>', active="/health", now=g["now"])


def job_href(job_id):
    """Where a job's entry is: its row on /queue, on the page that holds it."""
    return f"/queue?job={quote(str(job_id), safe='')}#job-{quote(str(job_id), safe='')}"


def took_min(j):
    s, e = health.parse_time(j.get("started")), health.parse_time(j.get("ended"))
    return round((e - s).total_seconds() / 60) if s and e else None


SORTS = {"ended": lambda j: str(j.get("ended") or ""), "took": lambda j: took_min(j) if took_min(j) is not None else -1,
         "id": lambda j: str(j.get("id"))}


def done_view(done, q, running_or_pending):
    """The Done table's view from the query `q`: filters (lane, status; an
    unknown value is "all"), sort (ended, took, id; default ended), order
    (desc default), page (1-based, clamped); `job=<id>` opens the default
    view on the page holding that job. Returns the view and a note."""
    lanes = sorted({str(j.get("lane")) for j in done})
    statuses = sorted({str(j.get("status")) for j in done})
    one = lambda k: (q.get(k) or [""])[0]
    v = {"lane": one("lane") if one("lane") in lanes else "", "status": one("status") if one("status") in statuses else "",
         "sort": one("sort") if one("sort") in SORTS else "ended", "order": "asc" if one("order") == "asc" else "desc"}
    try:
        page_no = int(one("page"))
    except ValueError:
        page_no = 1
    note, job = None, one("job")
    if job:
        v = {"lane": "", "status": "", "sort": "ended", "order": "desc"}
        page_no = 1
    rows = [j for j in done if (not v["lane"] or str(j.get("lane")) == v["lane"])
            and (not v["status"] or str(j.get("status")) == v["status"])]
    rows = sorted(rows, key=SORTS[v["sort"]], reverse=v["order"] == "desc")
    pages = max(1, -(-len(rows) // DONE_PAGE))
    if job:
        at = next((i for i, j in enumerate(rows) if str(j.get("id")) == job), None)
        if at is not None:
            page_no = at // DONE_PAGE + 1
        elif job not in running_or_pending:
            note = f"job {job} not found"
    page_no = min(max(page_no, 1), pages)
    return {**v, "page": page_no, "pages": pages, "lanes": lanes, "statuses": statuses, "total": len(rows),
            "rows": rows[(page_no - 1) * DONE_PAGE:page_no * DONE_PAGE]}, note


def queue_url(v, page_no):
    q = {k: v[k] for k in ("lane", "status") if v[k]}
    if v["sort"] != "ended":
        q["sort"] = v["sort"]
    if v["order"] != "desc":
        q["order"] = v["order"]
    if page_no != 1:
        q["page"] = page_no
    return "/queue" + (f"?{urlencode(q)}" if q else "")


def queue_page(g, q=None):
    def status(j):
        s = str(j.get("status", ""))
        tone = "good" if s == "ok" else ("bad" if s in ("failed", "killed", "stalled") else "")
        return f'<span class="pill {tone}">{E(s or "?")}</span>'

    def table(jobs, cols, extra=None):
        if not jobs:
            return '<div class="empty">none</div>'
        head = "".join(f"<th>{E(c)}</th>" for c, _ in cols)
        rows = "".join(f'<tr id="job-{E(quote(str(j.get("id")), safe=""))}">' + "".join(f"<td>{fn(j)}</td>" for _, fn in cols)
                       + "</tr>" for j in jobs)
        return f"<table><tr>{head}</tr>{rows}</table>"
    ident = lambda j: f'<span class="mono nowrap">{E(str(j.get("id")))}</span>'
    lane = lambda j: f'<span class="pill">{E(str(j.get("lane")))}</span>'
    note = lambda j: (f'<details class="more"><summary><span class="age clamp">{E(str(j.get("note") or ""))}</span>'
                      f'</summary></details>')
    when = lambda k: lambda j: f'<span class="nowrap">{E(str(j.get(k) or "")[5:16].replace("T", " "))}</span>'
    run = [("job", ident), ("lane", lane), ("threads", lambda j: E(str(j.get("threads", "")))),
           ("progress", lambda j: meter(None if j["run_min"] is None else round(j["run_min"]), j.get("estimate_min"), "min")),
           ("note", note)]
    pend = [("job", ident), ("lane", lane), ("threads", lambda j: E(str(j.get("threads", "")))), ("added", when("added")),
            ("estimate", lambda j: E(span(j.get("estimate_min")))), ("note", note)]
    done = [("job", ident), ("lane", lane), ("status", status), ("ended", when("ended")),
            ("took, of estimate", lambda j: meter(took_min(j), j.get("estimate_min"), "min")), ("note", note)]
    v, missing = done_view(g["done"], q or {}, {str(j.get("id")) for j in g["running"] + g["pending"]})

    def select(name, options, labels=None):
        opts = "".join(f'<option value="{E(o)}"{" selected" if v[name] == o else ""}>{E((labels or {}).get(o, o or "all"))}</option>'
                       for o in options)
        return f'<select name="{name}">{opts}</select>'
    form = (f'<form class="filters" method="get" action="/queue">'
            f'<label>lane {select("lane", [""] + v["lanes"])}</label><label>status {select("status", [""] + v["statuses"])}</label>'
            f'<label>sort {select("sort", list(SORTS), {"ended": "when it ended", "took": "how long it took", "id": "job id"})}</label>'
            f'{select("order", ["desc", "asc"], {"desc": "high to low", "asc": "low to high"})}'
            f'<button type="submit">show</button></form>')
    newer, older = ("Newer", "Older") if v["sort"] == "ended" and v["order"] == "desc" else ("Previous", "Next")
    links = [f'<a href="{E(queue_url(v, v["page"] - 1))}">&larr; {newer}</a>' if v["page"] > 1 else "",
             f'<span class="age">page {v["page"]} of {v["pages"]} &middot; {v["total"]} jobs</span>',
             f'<a href="{E(queue_url(v, v["page"] + 1))}">{older} &rarr;</a>' if v["page"] < v["pages"] else ""]
    pager = f'<div class="pager">{"".join(links)}</div>'
    warn = f'<div class="empty">{E(missing)}</div>' if missing else ""
    return page("Queue", f'<h1>Queue</h1>{warn}<section class="card"><h2>Running</h2>{table(g["running"], run)}</section>'
                f'<section class="card"><h2>Pending</h2>{table(g["pending"], pend)}</section>'
                f'<section class="card"><h2>Done</h2>{form}{pager}{table(v["rows"], done)}{pager}</section>',
                active="/queue", now=g["now"])


def digest_page(root, g):
    if not g["digest"]:
        return page("Digest", '<div class="empty">missing: no docs/digest/*.md</div>', active="/digest", now=g["now"])
    text = read_text(root, "docs", "digest", g["digest"]) or ""
    return page(f"Digest {g['digest']}", f'<section class="card digest">{md(text)}</section>', active="/digest", now=g["now"])


def render(root, path, now=None, ours=None):
    """(status, html) for a request path."""
    url = urlparse(path)
    path, query = unquote(url.path), parse_qs(url.query)
    if path.startswith("/session/"):
        name = path[len("/session/"):]
        if name not in records(root):
            return 404, page("Not found", "<p>No such session record.</p>")
        return 200, session_page(root, name, now or datetime.datetime.now().astimezone(), ours)
    pages = {"/": first_screen, "/log": log_page, "/health": health_page, "/queue": lambda g: queue_page(g, query),
             "/digest": lambda g: digest_page(root, g)}
    if path not in pages:
        return 404, page("Not found", "<p>No such page.</p>")
    g = gather(root, now, ours)
    g["root"] = root
    return 200, pages[path](g)


def handler(root):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                status, body = render(root, self.path)
            except Exception as e:  # show the failure, keep serving
                status, body = 500, page("Error", f"<pre>{E(repr(e))}</pre>")
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass
    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--root", default=roles.MAIN, help="the checkout to read (default: the main checkout)")
    a = ap.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", a.port), handler(a.root))
    print(f"dashboard on http://127.0.0.1:{a.port} (Ctrl+C stops it)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
