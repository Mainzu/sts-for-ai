"""Tests for the solved-state explorer (scripts/explore.py), over a tiny
database built in a temp directory. Run with
`python scripts/tests/test_explore.py` or with pytest."""

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.request
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402
import bench_sets  # noqa: E402
import explore  # noqa: E402
import learn  # noqa: E402
import puzzles  # noqa: E402
import sts  # noqa: E402

TEST_NODES = 20_000
N_GAMES = 12
_FIX = {}



def plain_board(bd):
    """A served board without the explorer's added descriptions (desc, why,
    per_hit, describe): what Combat.board() gave."""
    if isinstance(bd, dict):
        return {k: plain_board(v) for k, v in bd.items() if k not in ("desc", "why", "per_hit", "describe")}
    if isinstance(bd, list):
        return [plain_board(x) for x in bd]
    return bd

def quiet(*_):
    pass


def fixture():
    """{dir, db, puzzles, rows}: the walked tails of N_GAMES tight games in a
    database (source "test", every solved state kept), and their puzzles as a
    puzzle file (alternately train / held_out)."""
    if not _FIX:
        d = tempfile.mkdtemp(prefix="explore-test-")
        path = os.path.join(d, "solved.sqlite")
        db = sts.SolvedDb(path)
        specs = bench_sets.load_set("tight")["train"][:N_GAMES]
        rows = []
        for i, (s, r) in enumerate(zip(specs, puzzles.play(specs))):
            identity = {"spec": i, **{k: s[k] for k in ("character", "encounter", "deck", "hp", "seed")}}
            for p in puzzles.walk(r["states"], r["actions"], db, "test", puzzles.spec_key(identity),
                                  max_nodes=TEST_NODES, min_nodes=1):
                rows.append({**identity, **{k: p[k] for k in ("actions", "options", "gap", "horizon", "step")}})
        con = sqlite3.connect(path)  # fold the WAL into the file, so readers never write it
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            con.close()
        _FIX.update(dir=d, db=path, rows=rows, puzzles=write_puzzles(d, "puzzles.json", rows))
    return _FIX


def write_puzzles(d, name, rows, fingerprint=None):
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"halves": {"train": rows[0::2], "held_out": rows[1::2]},
                   **({"fingerprint": fingerprint} if fingerprint else {})}, f)
    return path


def explorer(cache=None, puzzle_path=None, db=True, runs=None, product=None):
    """An explorer over the fixture's puzzles; with `db`, the fixture's
    database opened through `open_db` (no start-time choice any more)."""
    fx = fixture()
    ex = explore.Explorer(puzzle_path=puzzle_path or fx["puzzles"], cache_dir=cache or os.path.join(fx["dir"], "cache"),
                          log=quiet, db_dir=fx["dir"], runs=runs or os.path.join(fx["dir"], "runs"),
                          product=product or os.path.join(fx["dir"], "product.json"))
    if db:
        ex.open_db(fx["db"], background=False)
    return ex


def wait_open(ex):
    for _ in range(1200):  # open_db opens in a thread
        if ex.db is not None or ex.db_error:
            return
        time.sleep(0.05)
    raise AssertionError("database never opened")


NET = os.path.join(os.path.dirname(__file__), "..", "..", "models", "value_effects.contract.pt")


def make_runs(d, ids=("r-old", "r-new")):
    """A registry folder holding `ids`, each a copy of models/value_effects.pt,
    modified one second apart (the last newest)."""
    runs = os.path.join(d, "runs")
    for k, rid in enumerate(ids):
        os.makedirs(os.path.join(runs, rid))
        path = os.path.join(runs, rid, "model.pt")
        shutil.copy(NET, path)
        os.utime(path, (1_700_000_000 + k, 1_700_000_000 + k))
    return runs


def file_state(path):
    with open(path, "rb") as f:
        return os.path.getsize(path), os.stat(path).st_mtime_ns, hashlib.sha256(f.read()).hexdigest()


def decision_ids(fx):
    return sts.SolvedDb(fx["db"]).decision_ids().tolist()


def solved_value(c):
    """A state's exact value: its score when over, else solved now."""
    if c.is_over():
        return c.score()
    r = sts.solve(c, max_nodes=TEST_NODES)
    assert r is not None
    return max(o[1] for o in r["options"])


def test_explore_read_only():
    """Every endpoint leaves the database file's bytes and mtime unchanged;
    a database with no rows of this rules version, or none at all, is
    refused (and not created)."""
    fx = fixture()
    before = file_state(fx["db"])
    ex = explorer()
    some = decision_ids(fx)[0]
    hx = ex.state(id=some)["hex"]
    for path, q in [("/api/status", ""), ("/api/puzzles", "sort=regret"), ("/api/puzzles", "wrong=heuristic"),
                    ("/api/positions", "source=test"), ("/api/state", "puzzle=0"), ("/api/state", f"id={some}"),
                    ("/api/state", f"hex={hx}"), ("/api/step", f"hex={hx}&option=0&seed=3"),
                    ("/api/solve", f"hex={hx}"), ("/api/reopen", "")]:
        status, out = explore.respond(ex, path, q)
        assert status == 200, (path, out)
    wait_open(ex)  # reopen opens in a thread
    assert ex.db is not None
    del ex
    assert file_state(fx["db"]) == before
    with tempfile.TemporaryDirectory() as d:
        empty = os.path.join(d, "empty.sqlite")
        sts.SolvedDb(empty)  # schema and a version row, no states
        ex = explore.Explorer(puzzle_path=fx["puzzles"], cache_dir=os.path.join(d, "c"), log=quiet, db_dir=d)
        for p in (empty, os.path.join(d, "missing.sqlite")):
            status, out = explore.respond(ex, "/api/open_db", f"path={p}")
            assert status == 400 and ("rules version" in out["error"] or "no such" in out["error"]), out
            assert ex.db_path is None
        assert not os.path.exists(os.path.join(d, "missing.sqlite"))


def test_explore_state_matches_db():
    """A row's view carries `fetch`'s value and option values, unchanged."""
    fx = fixture()
    ex = explorer()
    db = sts.SolvedDb(fx["db"])
    ids = decision_ids(fx)[:20]
    for row_id, (_, value, opts) in zip(ids, db.fetch(ids)):
        v = ex.state(id=row_id)
        assert v["value"] == value and v["row"] == row_id and v["source"] == "database"
        assert [o["value"] for o in v["options"]] == [o[1] for o in opts]
        assert v["cost"] >= 0 and v["turns_left"] >= 0


def test_explore_picks_match_bench():
    """On a 3-puzzle set, the picks, search values and regrets are
    bench.search_puzzles' and the exact best minus the pick's value."""
    fx = fixture()
    rows = fx["rows"][:3]
    with tempfile.TemporaryDirectory() as d:
        ex = explorer(cache=d, puzzle_path=write_puzzles(d, "three.json", rows))
        ordered = [r for r in ex.puzzles]
        picks, values = bench.search_puzzles(bench.load_evaluator("heuristic"), ordered)
        ex.players()
        assert ex.load_picks("heuristic") == {"picks": picks, "values": values}
        listed = {r["id"]: r for r in ex.puzzle_list()["rows"]}
        for i, r in enumerate(ordered):
            exact = [o[1] for o in r["options"]]
            assert listed[i]["regret"]["heuristic"] == max(exact) - exact[picks[i]]
            v = ex.state(puzzle=i)
            marked = [k for k, o in enumerate(v["options"]) if "heuristic" in o["picked_by"]]
            assert len(marked) == 1
            assert v["options"][marked[0]]["actions"] == r["options"][picks[i]][0]


def test_explore_step_matches_solve():
    """Each option of solved states: stepping it gives one of its outcomes;
    a deterministic option's child is worth the option's value, a chance
    option's outcomes, weighted by probability, add up to it."""
    fx = fixture()
    ex = explorer()
    kinds = set()
    ids = decision_ids(fx)
    db = sts.SolvedDb(fx["db"])
    # Chance options are rare (all-tied decisions sit in `trivial` since
    # exact-solver Amendment 1): the first 15 rows plus the first 5 with one.
    chance = [int(i) for i, (code, _, _) in zip(ids, db.fetch([int(i) for i in ids[:3000]]))
              if any(k == "chance" for _, k, _ in sts.Combat.decode(code).options(explore.LIMIT))][:5]
    for row_id in [int(i) for i in ids[:15]] + chance:
        v = ex.state(id=row_id)
        c = sts.Combat.decode(bytes.fromhex(v["hex"]))
        for k, (o, (_, kind, outs)) in enumerate(zip(v["options"], c.options(explore.LIMIT))):
            kinds.add(kind)
            if kind == "divergent":
                continue
            states = {x.encode() for _, x in outs}
            for seed in range(3):
                x, p, _ = ex.child(v["hex"], k, seed)
                assert x.encode() in states and p in [q for q, _ in outs]
            total = sum(p * solved_value(x) for p, x in outs)
            assert abs(total - o["value"]) < 1e-9, (row_id, k, kind, total, o["value"])
    assert {"deterministic", "chance"} <= kinds, kinds


def test_explore_filters():
    """Filters and paging over a hand-made picks cache: `wrong` keeps the
    puzzles whose cached pick isn't an exactly best option, `half` and
    `horizon` keep theirs, pages cut at PAGE; any column sorts both ways."""
    fx = fixture()
    with tempfile.TemporaryDirectory() as d:
        n = len(fx["rows"])
        ex0 = explorer(cache=os.path.join(d, "probe"))
        rows = ex0.puzzles
        picks = [min(range(len(r["options"])), key=lambda k: r["options"][k][1]) for r in rows]  # the worst option
        with open(os.path.join(d, f"heuristic-{ex0.puzzle_hash}.json"), "w", encoding="utf-8") as f:
            json.dump({"picks": picks, "values": [[0.0] * len(r["options"]) for r in rows]}, f)
        ex = explorer(cache=d)
        wrong = {i for i, r in enumerate(rows) if max(o[1] for o in r["options"]) - r["options"][picks[i]][1] > bench.EXACT}
        assert 0 < len(wrong) < n
        saved = explore.PAGE
        explore.PAGE = 2
        try:
            got = []
            out = ex.puzzle_list(wrong="heuristic")
            for page in range(out["pages"]):
                part = ex.puzzle_list(wrong="heuristic", page=page)["rows"]
                assert len(part) <= 2
                got += [r["id"] for r in part]
            assert set(got) == wrong and len(got) == len(wrong) == out["total"]
            held = ex.puzzle_list(half="held_out", page=0)
            assert held["total"] == sum(r["half"] == "held_out" for r in rows)
            dull = {i for i, r in enumerate(rows)
                    if learn.dull([o[1] for o in r["options"]], ["End" in o[0] for o in r["options"]])}
            assert 0 < len(dull) < n
            assert {r["id"] for p in range(ex.puzzle_list(dull="1")["pages"]) for r in ex.puzzle_list(dull="1", page=p)["rows"]} == dull
            assert ex.puzzle_list(dull="0")["total"] == n - len(dull)
            h0 = ex.puzzle_list(horizon="0")
            assert h0["total"] == sum(int(r["horizon"]) == 0 for r in rows)
            by = ex.puzzle_list(sort="regret")["rows"]
            assert by[0]["regret"]["heuristic"] >= by[-1]["regret"]["heuristic"]
            for key, get in [("gap", lambda r: r["gap"]), ("encounter", lambda r: r["encounter"]),
                             ("regret:heuristic", lambda r: r["regret"]["heuristic"])]:
                for desc in ("0", "1"):  # every column sorts both ways, ties in id order, across pages
                    out = ex.puzzle_list(sort=key, desc=desc)
                    got = [r for page in range(out["pages"]) for r in ex.puzzle_list(sort=key, desc=desc, page=page)["rows"]]
                    want = sorted(sorted(got, key=lambda r: r["id"]), key=get, reverse=desc == "1")
                    assert [r["id"] for r in got] == [r["id"] for r in want] and len(got) == n
            try:
                ex.puzzle_list(sort="nope")
                raise AssertionError("an unknown column must be refused")
            except ValueError:
                pass
        finally:
            explore.PAGE = saved


def test_explore_cache():
    """A second start reads the picks cache and runs no search."""
    calls = []
    real = bench.search_puzzles

    def counted(ev, rows, search=None):
        calls.append(len(rows))
        return real(ev, rows, search)
    with tempfile.TemporaryDirectory() as d:
        bench.search_puzzles = counted
        try:
            first = explorer(cache=d, db=False)
            first.puzzle_list()
            n = len(calls)
            second = explorer(cache=d, db=False)
            second.puzzle_list()
        finally:
            bench.search_puzzles = real
        assert n > 0 and len(calls) == n
        assert first.picks == second.picks


def test_explore_server_smoke():
    """A real server on a free port serves the page, the dashboard's
    stylesheet at /ui.css, and every endpoint the page calls answers 200 on
    the fixtures (puzzles and database from `fixture`, gauntlet views on the
    pinned file; the mutate, boss-replay and fight endpoints have their own
    tests, since their files are made there)."""
    import dashboard
    from urllib.parse import quote
    fx = fixture()
    with open(PIN, encoding="utf-8") as f:
        pin = json.load(f)
    res = results_dir({"pin.json": pin})
    pin_path = os.path.join(res, "gauntlet", "pin.json")
    before = file_state(pin_path)
    ex = gauntlet_explorer(res)
    server = explore.serve(ex, 0)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def get(path):
        with urllib.request.urlopen(base + path) as r:
            assert r.status == 200, path
            return r.read()

    def api(path):
        return json.loads(get(path))
    try:
        page = get("/").decode()
        assert "<html" in page.lower() and 'href="/ui.css"' in page
        assert get("/ui.css").decode() == dashboard.CSS
        st = api("/api/status")
        assert st["puzzles"] == len(fx["rows"]) and st["build"]
        assert api("/api/dbs")["dbs"]
        api("/api/nets")
        api("/api/open_db?path=" + quote(fx["db"]))
        wait_open(ex)
        assert api("/api/status")["ready"]
        assert "test" in api("/api/status")["sources"]
        api("/api/positions?source=test")
        api("/api/puzzles?sort=gap&desc=1")
        v = api("/api/state?puzzle=0")
        assert v["board_data"]["player"]["hp"] > 0
        api("/api/step?hex=" + v["hex"] + "&option=0")
        api("/api/view?hex=" + v["hex"])
        api("/api/reopen")
        wait_open(ex)
        api("/api/close_db")
        for kind in ("gauntlet", "mutate", "boss_replay"):
            api("/api/files?kind=" + kind)
        seqs = api("/api/sequences?file=pin.json&sort=end_hp&desc=1")
        i = seqs["rows"][0]["i"]
        run = api(f"/api/run?file=pin.json&i={i}")
        ev = run["floors"][0]["events"][0]["e"]
        api(f"/api/event?file=pin.json&i={i}&e={ev}")
        fl = api(f"/api/floor?file=pin.json&i={i}&k=0")
        assert fl["decisions"][0]["board_data"]
        api(f"/api/view?file=pin.json&i={i}&k=0&n=0")
        d0 = fl["decisions"][0]
        api(f"/api/step?file=pin.json&i={i}&k=0&n=0&option=0&hex={d0['hex']}")
        for kind in ("cards", "monsters", "powers"):
            api(f"/api/content?kind={kind}&file=pin.json")
        desc = api("/api/describe")
        assert desc["encounters"]["cultist"]["lines"] and desc["moves"]["Cultist"]["Incantation"]["lines"]
        assert file_state(pin_path) == before, "a result file changed"
    finally:
        server.shutdown()
        server.server_close()
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


def test_explore_private_sts():
    """A fresh process importing explore loads a copy of the installed `sts`
    (under the copies root, named by the .pyd's hash), clears an older
    copy, and leaves the installed .pyd free to rename while it runs."""
    import subprocess
    src = os.path.dirname(sts.__file__)
    pyd = next(f for f in os.listdir(src) if f.endswith(".pyd"))
    with tempfile.TemporaryDirectory() as d:
        site, copies = os.path.join(d, "site"), os.path.join(d, "copies")
        shutil.copytree(src, os.path.join(site, "sts"), ignore=shutil.ignore_patterns("__pycache__"))
        os.makedirs(os.path.join(copies, "sts-000000000000", "sts"))
        env = {**os.environ, "EXPLORE_STS_ROOT": copies,
               "PYTHONPATH": os.pathsep.join([site, os.path.join(os.path.dirname(__file__), "..")]
                                             + [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p])}
        code = ("import sys, explore, sts; print(sts.__file__, explore.BUILD, explore.build_hash(), flush=True); "
                "sys.stdin.read()")
        p = subprocess.Popen([sys.executable, "-c", code], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
        try:
            line = p.stdout.readline().split()
            assert line, p.stderr.read()
            loaded, build, shown = line
            with open(os.path.join(site, "sts", pyd), "rb") as f:
                tag = hashlib.sha256(f.read()).hexdigest()[:12]
            assert build == shown == tag
            assert os.path.normcase(loaded).startswith(os.path.normcase(os.path.join(copies, f"sts-{tag}")))
            assert not os.path.exists(os.path.join(copies, "sts-000000000000"))
            installed = os.path.join(site, "sts", pyd)
            os.rename(installed, installed + ".aside")  # fails on Windows if the process held it
            os.rename(installed + ".aside", installed)
        finally:
            p.stdin.close()
            p.wait(60)


def test_explore_private_sts_half_copy():
    """A copy left half deleted (only its .pyd: the cleanup of another
    explorer removed the rest while this one held the .pyd) under the
    build's own hash is made again, so the process still loads the copy,
    never the installed package."""
    import subprocess
    src = os.path.dirname(sts.__file__)
    pyd = next(f for f in os.listdir(src) if f.endswith(".pyd"))
    with tempfile.TemporaryDirectory() as d:
        site, copies = os.path.join(d, "site"), os.path.join(d, "copies")
        shutil.copytree(src, os.path.join(site, "sts"), ignore=shutil.ignore_patterns("__pycache__"))
        with open(os.path.join(site, "sts", pyd), "rb") as f:
            tag = hashlib.sha256(f.read()).hexdigest()[:12]
        half = os.path.join(copies, f"sts-{tag}", "sts")
        os.makedirs(half)
        shutil.copy2(os.path.join(src, pyd), os.path.join(half, pyd))
        env = {**os.environ, "EXPLORE_STS_ROOT": copies,
               "PYTHONPATH": os.pathsep.join([site, os.path.join(os.path.dirname(__file__), "..")]
                                             + [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p])}
        out = subprocess.run([sys.executable, "-c", "import explore, sts; print(sts.__file__)"], env=env,
                             capture_output=True, text=True, timeout=300)
        assert out.returncode == 0, out.stderr
        loaded = out.stdout.split()[-1]
        assert os.path.normcase(loaded).startswith(os.path.normcase(os.path.join(copies, f"sts-{tag}"))), loaded


def test_explore_starts_without_db():
    """No database open at start: the status says why database views are
    off, puzzles list, positions answer 503; /api/dbs marks a current and a
    stale database, and opening the stale one is refused without writing."""
    fx = fixture()
    with tempfile.TemporaryDirectory() as d:
        shutil.copy(fx["db"], os.path.join(d, "good.sqlite"))
        stale = os.path.join(d, "stale.sqlite")
        sts.SolvedDb(stale)  # a version row, no states
        con = sqlite3.connect(stale)
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.close()
        before = file_state(stale)
        ex = explore.Explorer(puzzle_path=fx["puzzles"], cache_dir=os.path.join(d, "c"), log=quiet, db_dir=d)
        st = explore.respond(ex, "/api/status", "")[1]
        assert not st["ready"] and st["db"] is None and "no database open" in st["db_note"]
        assert explore.respond(ex, "/api/puzzles", "")[0] == 200
        assert explore.respond(ex, "/api/positions", "source=test")[0] == 503
        listed = {r["name"]: r for r in explore.respond(ex, "/api/dbs", "")[1]["dbs"]}
        assert listed["good.sqlite"]["current"] and listed["good.sqlite"]["why"] is None
        assert not listed["stale.sqlite"]["current"] and "rules version" in listed["stale.sqlite"]["why"]
        assert listed["good.sqlite"]["bytes"] == os.path.getsize(os.path.join(d, "good.sqlite"))
        status, out = explore.respond(ex, "/api/open_db", f"path={stale}")
        assert status == 400 and "rules version" in out["error"]
        assert file_state(stale) == before


def test_explore_pick_db():
    """A database opened through the endpoint answers rows as `fetch` does;
    opening another closes the first (its row id no longer answers from it)."""
    fx = fixture()
    with tempfile.TemporaryDirectory() as d:
        a, b = os.path.join(d, "a.sqlite"), os.path.join(d, "b.sqlite")
        shutil.copy(fx["db"], a)
        shutil.copy(fx["db"], b)
        ex = explore.Explorer(puzzle_path=fx["puzzles"], cache_dir=os.path.join(d, "c"), log=quiet, db_dir=d)
        assert explore.respond(ex, "/api/open_db", f"path={a}")[0] == 200
        wait_open(ex)
        ids = decision_ids(fx)[:5]
        db = sts.SolvedDb(fx["db"])
        for row_id, (_, value, opts) in zip(ids, db.fetch(ids)):
            status, v = explore.respond(ex, "/api/state", f"id={row_id}")
            assert status == 200 and v["value"] == value and [o["value"] for o in v["options"]] == [o[1] for o in opts]
        assert explore.respond(ex, "/api/open_db", f"path={b}")[0] == 200
        st = ex.status()
        assert st["db"] == b.replace("\\", "/")
        wait_open(ex)
        listed = {r["name"]: r["open"] for r in ex.dbs()["dbs"]}
        assert listed == {"a.sqlite": False, "b.sqlite": True}
        assert explore.respond(ex, "/api/close_db", "")[1]["db"] is None
        assert explore.respond(ex, "/api/state", f"id={ids[0]}")[0] == 503


def test_explore_players_param():
    """`with=` adds a net's picks and regrets, equal to bench.search_puzzles'
    for that net; leaving it out drops its column; a second explorer reads
    the cache (no search); a bad settings suffix is refused with the bench's
    message."""
    if not os.path.exists(NET):
        return  # models/ is gitignored; the test needs a saved net
    fx = fixture()
    rows = fx["rows"][:4]
    with tempfile.TemporaryDirectory() as d:
        runs = make_runs(d)
        pz = write_puzzles(d, "four.json", rows)
        ex = explorer(cache=os.path.join(d, "c"), puzzle_path=pz, db=False, runs=runs)
        status, out = explore.respond(ex, "/api/puzzles", "with=heuristic,r-new")
        assert status == 200, out
        net = f"{runs}/r-new/model.pt".replace("\\", "/")
        assert out["players"] == ["heuristic", net]
        picks, _ = bench.search_puzzles(bench.load_evaluator(net), ex.puzzles)
        for r in out["rows"]:
            exact = [o[1] for o in ex.puzzles[r["id"]]["options"]]
            assert r["regret"][net] == max(exact) - exact[picks[r["id"]]]
        st = explore.respond(ex, "/api/state", "puzzle=0&with=r-new")[1]
        marked = [k for k, o in enumerate(st["options"]) if net in o["picked_by"]]
        assert len(marked) == 1 and st["options"][marked[0]]["actions"] == ex.puzzles[0]["options"][picks[0]][0]
        assert set(explore.respond(ex, "/api/puzzles", "")[1]["rows"][0]["regret"]) == {"heuristic"}
        calls = []
        real = bench.search_puzzles
        bench.search_puzzles = lambda *a, **k: calls.append(1) or real(*a, **k)
        try:
            ex2 = explorer(cache=os.path.join(d, "c"), puzzle_path=pz, db=False, runs=runs)
            assert explore.respond(ex2, "/api/puzzles", "with=r-new")[0] == 200
        finally:
            bench.search_puzzles = real
        assert calls == []
        status, out = explore.respond(ex, "/api/puzzles", "with=r-new@bogus1")
        assert status == 400 and "bad player setting" in out["error"], out
        status, out = explore.respond(ex, "/api/puzzles", "with=no-such-run")
        assert status == 400 and "no model" in out["error"], out


def test_explore_net_list():
    """/api/nets: runs with a model.pt, newest first, after the product net
    and the named file's players."""
    if not os.path.exists(NET):
        return
    with tempfile.TemporaryDirectory() as d:
        runs = make_runs(d, ("r-a", "r-b", "r-c"))
        os.makedirs(os.path.join(runs, "no-model"))
        product = os.path.join(d, "product.json")
        with open(product, "w", encoding="utf-8") as f:
            json.dump({"player": "runs/r-a/model.pt@hpe0.01"}, f)
        res = os.path.join(d, "res.json")
        with open(res, "w", encoding="utf-8") as f:
            json.dump({"settings": {"player": "runs/r-b/model.pt@hpb0.01", "chooser": "heuristic"}}, f)
        ex = explorer(cache=os.path.join(d, "c"), db=False, runs=runs, product=product)
        nets = explore.respond(ex, "/api/nets", f"file={res}")[1]["nets"]
        assert [(n["id"], n["tag"]) for n in nets] == [("r-a", "product"), ("r-b", "file"), ("r-c", None),
                                                        ("r-b", None), ("r-a", None)]
        assert nets[0]["player"] == "runs/r-a/model.pt@hpe0.01"
        assert [n["id"] for n in explore.respond(ex, "/api/nets", "")[1]["nets"]] == ["r-a", "r-c", "r-b", "r-a"]


def test_explore_puzzles_without_db():
    """With no database open, puzzles list and open with the same rows,
    values, picks and regrets as with one; the status names the puzzle
    file's rules fingerprint beside this build's."""
    fx = fixture()
    with tempfile.TemporaryDirectory() as d:
        pz = write_puzzles(d, "fp.json", fx["rows"], fingerprint="abcdef0123456789")
        off = explorer(cache=os.path.join(d, "c"), puzzle_path=pz, db=False)
        on = explorer(cache=os.path.join(d, "c"), puzzle_path=pz)
        assert off.puzzle_list() == on.puzzle_list()
        for i in range(min(5, len(off.puzzles))):
            a, b = off.state(puzzle=i), on.state(puzzle=i)
            assert [(o["value"], o["regret"], o["picked_by"], o["scores"]) for o in a["options"]] == \
                   [(o["value"], o["regret"], o["picked_by"], o["scores"]) for o in b["options"]]
            assert a["value"] == b["value"] and a["rules"] == "abcdef0123456789"
        st = off.status()
        assert st["puzzle_rules"] == "abcdef0123456789" and st["rules"] == explore.current_fingerprint()
        assert not st["ready"]


def test_explore_offer_scores():
    # explorer-v2 step 4: on the pinned gauntlet file (heuristic, sim rewards,
    # sim rest, strike removal), every event's shown scores pick what the row
    # recorded, and the rebuilt offers are the row's
    pin = os.path.join(os.path.dirname(__file__), "data", "explore", "gauntlet_pin.json")
    with open(pin, encoding="utf-8") as f:
        d = json.load(f)
    st = d["settings"]
    kinds = set()
    for row in d["sequences"]:
        seq = explore.sequence(st, row["i"])
        for ev in explore.run_events(st, seq, row):
            got = explore.event_scores(st, ev)
            kinds.add(ev["kind"])
            if ev["kind"] == "offer":
                assert got["offer"] == ev["offer"]
                assert got["scores"] is not None and len(got["scores"]) == len(got["options"])
            want = None if ev["recorded"] == "heal" else ev["recorded"]
            assert got["pick"] == want, (row["i"], ev["k"], ev["kind"], got, ev["recorded"])
    assert {"offer", "rest", "removal"} <= kinds, kinds


# --- gauntlet files (explorer-v2 step 5) -----------------------------------

PIN = os.path.join(os.path.dirname(__file__), "data", "explore", "gauntlet_pin.json")


def results_dir(files):
    """A temp results folder whose gauntlet/ holds `files` ({name: JSON body});
    its parent also holds the explorer's cache (`gauntlet_explorer`), so the
    results folder holds only result files."""
    d = os.path.join(tempfile.mkdtemp(prefix="explore-results-"), "results")
    os.makedirs(os.path.join(d, "gauntlet"))
    for name, body in files.items():
        with open(os.path.join(d, "gauntlet", name), "w", encoding="utf-8") as f:
            json.dump(body, f)
    return d


def gauntlet_explorer(results, two_turn=None):
    fx = fixture()
    return explore.Explorer(puzzle_path=fx["puzzles"], cache_dir=os.path.join(os.path.dirname(results), "cache"), log=quiet,
                            db_dir=fx["dir"], runs=os.path.join(fx["dir"], "runs"),
                            product=os.path.join(fx["dir"], "product.json"), results=results, two_turn=two_turn)


def test_explore_gauntlet_replay_matches_file():
    """Every floor of the pinned file (one-turn heuristic, sim rewards, sim
    rest, strike removal) replays to the row's win and end HP; each
    decision's pick is the option holding the action played; a row edited in
    a copy flags exactly that floor; a second opening comes from the cache."""
    with open(PIN, encoding="utf-8") as f:
        d = json.load(f)
    edited = json.loads(json.dumps(d))
    edited["sequences"][1]["floors"][10]["hp_end"] -= 1  # the boss: no later floor starts from it
    res = results_dir({"pin.json": d, "edited.json": edited})
    try:
        ex = gauntlet_explorer(res)
        floors = 0
        for row in d["sequences"]:
            for k in range(len(row["floors"])):
                out = ex.floor("pin.json", row["i"], k)
                assert out["fidelity"]["matches"], (row["i"], k, out["fidelity"])
                assert out["decisions"], (row["i"], k)
                for dec in out["decisions"]:
                    assert dec["action"] in dec["scores"]["options"][dec["scores"]["pick"]]
                floors += 1
        assert floors == 44
        again = ex.floor("pin.json", d["sequences"][0]["i"], 0)
        assert again["cached"] and again["fidelity"]["matches"]
        run = ex.run("pin.json", d["sequences"][0]["i"])
        assert run["floors"][0]["fidelity"]["matches"] and len(run["floors"]) == 11
        bad = [(row["i"], k) for row in edited["sequences"] for k in range(len(row["floors"]))
               if not ex.floor("edited.json", row["i"], k)["fidelity"]["matches"]]
        assert bad == [(edited["sequences"][1]["i"], 10)], bad
        flag = ex.floor("edited.json", edited["sequences"][1]["i"], 10)["fidelity"]
        assert flag["file"]["hp_end"] == flag["replay"]["hp_end"] - 1 and flag["cause"]
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


def test_explore_two_turn_replay():
    """One two-turn floor (heuristic, line seed and step line, a low node
    cap) replays to the row the guarded fight played, and its decisions'
    scores are that fight's own `scores`."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
    import depth_paired
    import gauntlet
    two = {"limit": bench.LIMIT, "turns": 2, "sample_k": 2, "max_nodes": 20_000}
    st = {"player": "heuristic", "two_turn": True, "shape": list(gauntlet.SHAPE), "rest": gauntlet.REST,
          "seed": gauntlet.GAUNTLET_SEED, "line_seed": True, "step_line": True}
    seq = explore.sequence(st, 0)
    spec = {"encounter": seq["fights"][0]["encounter"], "deck": list(seq["deck"]), "seed": seq["fights"][0]["seed"],
            "hp": gauntlet.MAX_HP, "character": seq["character"], "group": seq["fights"][0]["group"]}
    r = depth_paired.guarded_fight((spec, two, -1.0, "heuristic", 0, 3, True, True, True, True))
    won = bool(r["won"])
    row = {"i": 0, "half": seq["half"], "cell": seq["cell"], "cleared": False,
           "floors": [{"encounter": spec["encounter"], "hp_start": gauntlet.MAX_HP,
                       "hp_end": int(r["hp_end"]) if won else 0, "won": won}]}
    res = results_dir({"two.json": {"settings": st, "sequences": [row]}})
    try:
        out = gauntlet_explorer(res, two_turn=two).floor("two.json", 0, 0)
        assert out["depth"] == 2 and out["fidelity"]["matches"], out["fidelity"]
        assert [x["action"] for x in out["decisions"]] == r["actions"]
        assert [x["scores"] for x in out["decisions"]] == r["scores"]
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


def made_floor(enc, won=True, hp_start=80, hp_end=70, **extra):
    return {"encounter": enc, "hp_start": hp_start, "hp_end": hp_end if won else 0, "won": won, **extra}


def test_explore_sequence_filters():
    """A hand-made file: the half, cleared, died-on-floor, encounter and card
    filters, sort (a missing value last), paging; the file list's tags and
    clear rate; a file on other sequences lists but refuses replays."""
    import gauntlet
    with open(PIN, encoding="utf-8") as f:
        st = json.load(f)["settings"]
    n = len(gauntlet.SHAPE)

    def floors(seq, died=None, took=None):
        out = []
        for k in range(n if died is None else died + 1):
            f = made_floor(seq["fights"][k]["encounter"], won=died != k, hp_end=60 + k)
            if took and k == 0:
                f.update(offer=[took, "Anger", "Cleave"], took=took)
            out.append(f)
        return out
    seqs = {i: explore.sequence(st, i) for i in range(4)}
    rows = [{"i": 0, "half": seqs[0]["half"], "cell": seqs[0]["cell"], "floors": floors(seqs[0]), "cleared": True},
            {"i": 1, "half": seqs[1]["half"], "cell": seqs[1]["cell"], "floors": floors(seqs[1], died=2),
             "cleared": False},
            {"i": 2, "half": seqs[2]["half"], "cell": seqs[2]["cell"], "floors": floors(seqs[2], died=5),
             "cleared": False},
            {"i": 3, "half": seqs[3]["half"], "cell": seqs[3]["cell"], "floors": floors(seqs[3], took="Inflame"),
             "cleared": True}]
    other = {"settings": {**st, "seed": 1}, "sequences": rows}
    res = results_dir({"made.json": {"settings": st, "sequences": rows}, "other.json": other})
    old = explore.PAGE
    try:
        ex = gauntlet_explorer(res)
        ids = lambda **kw: [r["i"] for r in ex.sequences("made.json", **kw)["rows"]]
        assert ids() == [0, 1, 2, 3]
        assert ids(cleared="1") == [0, 3] and ids(cleared="0") == [1, 2]
        assert ids(died="2") == [1] and ids(died="5") == [2]
        assert ids(half=seqs[1]["half"]) == [i for i in range(4) if seqs[i]["half"] == seqs[1]["half"]]
        enc = seqs[2]["fights"][4]["encounter"]
        assert ids(encounter=enc) == sorted(i for i in range(4) if any(
            f["encounter"] == enc for f in rows[i]["floors"]))
        assert ids(card="Inflame") == [3]
        assert ids(sort="end_hp", desc="1") == [0, 3, 1, 2]  # cleared ones end at 70; ties in i order
        assert ids(sort="died") == [1, 2, 0, 3]  # missing (cleared) last
        assert ids(sort="died", desc="1") == [0, 3, 2, 1]
        top = ex.sequences("made.json")["rows"][1]
        assert top["died"] == 2 and top["end_hp"] == 0 and len(top["strip"]) == 3 and not top["strip"][2]["won"]
        assert ex.sequences("made.json")["rows"][3]["strip"][0]["took"] == "Inflame"
        explore.PAGE = 3
        p0, p1 = ex.sequences("made.json", page=0), ex.sequences("made.json", page=1)
        assert (p0["pages"], len(p0["rows"]), [r["i"] for r in p1["rows"]]) == (2, 3, [3])
        files = {f["file"]: f for g in ex.files()["groups"] for f in g["files"]}
        assert files["made.json"]["n"] == 4 and files["made.json"]["clears"] == 0.5
        assert files["made.json"]["tags"] == ["one-turn", "rewards=sim", "rest_choice=sim", "remove=strike"]
        assert files["made.json"]["refused"] is None and "seed or shape" in files["other.json"]["refused"]
        assert [f["file"] for g in ex.files(q="other")["groups"] for f in g["files"]] == ["other.json"]
        try:
            ex.floor("other.json", 0, 0)
            raise AssertionError("a file on other sequences replayed")
        except ValueError as e:
            assert "seed or shape" in str(e)
        try:
            ex.sequences("../../x.json")
            raise AssertionError("a path outside the folder was read")
        except ValueError:
            pass
    finally:
        explore.PAGE = old
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    try:
        for t in tests:
            t()
            print("ok ", t.__name__)
    finally:
        if _FIX:
            shutil.rmtree(_FIX["dir"], ignore_errors=True)
    print(f"{len(tests)} passed")


def draw_listings(x, out):
    """Every `draw` listing in an endpoint's JSON (board_data's piles)."""
    if isinstance(x, dict):
        for key, v in x.items():
            if key == "draw" and isinstance(v, dict) and "cards" in v:
                out.append(v)
            draw_listings(v, out)
    elif isinstance(x, list):
        for v in x:
            draw_listings(v, out)
    return out


def check_net_inputs(out, f, c):
    """The view's net inputs equal `f.encode([c])`, column by column."""
    import numpy as np
    b = f.encode([c])
    cols = out["columns"]
    assert cols["player"] == list(f.player_names) and len(cols["player"]) == b["player"].shape[1]
    assert len(cols["monster"]) == b["monsters"].shape[2] and len(cols["card"]) == b["cards"].shape[1]
    assert len(cols["row"]) == b["rows"].shape[1]
    assert np.array_equal(np.array(out["player"], np.float32), b["player"][0])
    live = [s for s in range(b["monsters"].shape[1]) if b["monsters"][0][s].any()]
    assert [m["slot"] for m in out["monsters"]] == live
    for m in out["monsters"]:
        assert np.array_equal(np.array(m["values"], np.float32), b["monsters"][0][m["slot"]])
    assert len(out["cards"]) == b["cards"].shape[0] and len(out["rows"]) == b["rows"].shape[0]
    for j, card in enumerate(out["cards"]):
        assert np.array_equal(np.array(card["values"], np.float32), b["cards"][j])
        assert card["pile"] == list(f.piles)[int(b["card_pile"][j])] and card["count"] == float(b["card_count"][j])
    for r, row in enumerate(out["rows"]):
        assert np.array_equal(np.array(row["values"], np.float32), b["rows"][r])
        assert (row["card"], row["entity"]) == (int(b["row_card"][r]), int(b["row_entity"][r]))


def test_explore_net_inputs():
    """The state view: the heuristic's named parts; a net's input rows equal
    its features' encoding, its static value the PyTorch net's; the player's
    own scores computed now equal sts.search's (one turn) and, on a two-turn
    floor, depth_paired.decide's, which equal the replay's record; every draw
    listing of every endpoint is the draw pile's sorted contents (the engine
    stores counts only, so no order exists to leak); the render text names no
    draw card."""
    import numpy as np
    ex = explorer(db=False)
    c = sts.Combat(["Strike"] * 5 + ["Defend"] * 4 + ["Bash", "Inflame", "Pommel Strike", "Shrug It Off"],
                   "gremlin_nob", seed=7)
    hexs = c.encode().hex()
    v = ex.state_view(hexs)
    assert v["net"]["kind"] == "heuristic"
    assert [x[1] for x in v["net"]["parts"]] == [float(x) for x in c.heuristic_parts()]
    s = sts.search(c, "heuristic", limit=bench.LIMIT)
    groups = [o["actions"] for o in v["options"]]
    want = {frozenset(explore.enc(a) for a in acts): float(val) for acts, val in s["options"]}
    assert v["player"]["one"] == [want[frozenset(g)] for g in groups] and v["player"]["source"] == "now"
    assert explore.enc(s["action"]) in groups[v["player"]["pick"]]
    assert plain_board(v["board_data"]) == c.board()

    # every endpoint's draw listings, along a few steps of a fight
    seen = []
    x = c
    for step in range(6):
        if x.is_over():
            break
        h = x.encode().hex()
        out = [ex.state(hex=h), ex.state_view(h), ex.step(h, 0, 3, player="heuristic")]
        piles = x.piles()
        for o in out:
            for d in draw_listings(o, []):
                assert [list(t) for t in d["cards"]] == sorted([list(t) for t in d["cards"]]), d
            assert "Draw" in o["board"]
        for d in draw_listings(out[1], []):
            assert [list(t) for t in d["cards"]] == sorted([list(t) for t in piles["draw"].items()]), d
            assert d["count"] == sum(piles["draw"].values())
        draw_line = out[1]["board"].split("Draw ", 1)[1].split("\n")[0]
        assert all(name not in draw_line for name in piles["draw"]), draw_line
        seen.append(out[1])
        x, _, _ = ex.child(h, 0, step)
    assert len(seen) >= 3

    if os.path.exists(NET):
        player = explore.resolve_player(NET)
        nv = ex.state_view(hexs, player=player)
        ev = bench.load_evaluator(NET)
        check_net_inputs(nv["net"], ev.features, c)
        static = float(np.asarray(ev.static(ev.features.encode([c], heuristic=True)), np.float64)[0])
        assert abs(nv["net"]["static"] - static) < 1e-6
        s = sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT)
        want = {frozenset(explore.enc(a) for a in acts): float(val) for acts, val in s["options"]}
        assert nv["player"]["one"] == [want[frozenset(g)] for g in [o["actions"] for o in nv["options"]]]
        hp = ex.state_view(hexs, player=player + "@hpb0.01", with_=player)
        assert hp["net"]["static"] == nv["net"]["static"] and player in hp["players"]
        assert hp["options"][0]["scores"][player] == nv["player"]["one"][0]

    # a two-turn floor: the record's scores, and the same computed now
    import gauntlet
    two = {"limit": bench.LIMIT, "turns": 2, "sample_k": 2, "max_nodes": 20_000}
    st = {"player": "heuristic", "two_turn": True, "shape": list(gauntlet.SHAPE), "rest": gauntlet.REST,
          "seed": gauntlet.GAUNTLET_SEED, "line_seed": True, "step_line": True}
    seq = explore.sequence(st, 0)
    spec = {"encounter": seq["fights"][0]["encounter"], "deck": list(seq["deck"]), "seed": seq["fights"][0]["seed"],
            "hp": gauntlet.MAX_HP, "character": seq["character"], "group": seq["fights"][0]["group"]}
    dp = explore.depth_paired()
    r = dp.guarded_fight((spec, two, -1.0, "heuristic", 0, 3, True, True, True, True))
    won = bool(r["won"])
    row = {"i": 0, "half": seq["half"], "cell": seq["cell"], "cleared": False,
           "floors": [{"encounter": spec["encounter"], "hp_start": gauntlet.MAX_HP,
                       "hp_end": int(r["hp_end"]) if won else 0, "won": won}]}
    res = results_dir({"two.json": {"settings": st, "sequences": [row]}})
    try:
        gx = gauntlet_explorer(res, two_turn=two)
        fl = gx.floor("two.json", 0, 0)
        assert all(plain_board(d["board_data"]) == sts.Combat.decode(bytes.fromhex(d["hex"])).board() for d in fl["decisions"])
        searched = [n for n, d in enumerate(fl["decisions"]) if not d["scores"].get("line")][:3]
        assert searched
        for n in searched:
            rec = gx.state_view(file="two.json", i=0, k=0, n=n)
            now = gx.state_view(file="two.json", i=0, k=0, n=n, fresh="1")
            assert rec["player"]["source"] == "record" and now["player"]["source"] == "now"
            assert rec["player"]["depth"] == 2
            for key in ("one", "two", "pick"):
                assert rec["player"][key] == now["player"][key], (n, key, rec["player"][key], now["player"][key])
            groups = [o["actions"] for o in rec["options"]]
            assert fl["decisions"][n]["action"] in groups[rec["player"]["recorded"]]
            assert rec["player"]["recorded"] == rec["player"]["pick"]
        lines = [n for n, d in enumerate(fl["decisions"]) if d["scores"].get("line")]
        if lines:
            assert gx.state_view(file="two.json", i=0, k=0, n=lines[0])["player"]["line"]
        # a step off the record keeps the two-turn player (scored now, or from the record if the line rejoins it)
        d0 = fl["decisions"][searched[0]]
        off = gx.step(d0["hex"], 0, 0, file="two.json", i=0, k=0, n=searched[0] + 1)
        if off.get("options"):
            assert off["player"]["depth"] == 2 and off["player"]["source"] in ("now", "record")
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


# --- taking over (explorer-v2 step 7) -----------------------------------------

def test_explore_takeover():
    """Inside a fight: stepping the recorded option at every decision of a
    floor reproduces the replay's states and its end, all "as played"; any
    other option is "your line". Between floors: a different card taken at
    floor 2 is in floor 3's deck and floor 3 is the owner's line (played when
    opened, no fidelity check); a taken-over fight's end HP is the next
    floor's start HP."""
    with open(PIN, encoding="utf-8") as f:
        d = json.load(f)
    res = results_dir({"pin.json": d})
    try:
        ex = gauntlet_explorer(res)
        row = d["sequences"][0]
        i = row["i"]
        # inside a fight: the recorded options, one after another
        fl = ex.floor("pin.json", i, 0)
        decs = fl["decisions"]
        hexes, cur = [], decs[0]["hex"]
        for n, dec in enumerate(decs):
            assert cur == dec["hex"], n
            v = ex.state_view(cur, file="pin.json", i=i, k=0, n=n)
            opt = next(j for j, o in enumerate(v["options"]) if dec["action"] in o["actions"])
            nxt = ex.step(cur, opt, 0, file="pin.json", i=i, k=0, n=n + 1)
            assert nxt["line"] == "as played", (n, nxt["line"])
            cur = nxt["hex"]
            hexes.append(cur)
        assert nxt["over"] and nxt["end"] == {**fl["replay"], "as_recorded": True}, (nxt.get("end"), fl["replay"])
        # another option at the first decision is the owner's line
        v0 = ex.state_view(decs[0]["hex"], file="pin.json", i=i, k=0, n=0)
        other = next(j for j, o in enumerate(v0["options"]) if decs[0]["action"] not in o["actions"])
        off = ex.step(decs[0]["hex"], other, 0, file="pin.json", i=i, k=0, n=1)
        assert off["line"] == "your line"
        # no choices: the run is the file's line
        base = ex.run("pin.json", i)
        assert all(f["line"] == "file" for f in base["floors"])
        # between floors: another card at floor 2 (k = 1)
        f1 = row["floors"][1]
        assert "offer" in f1, f1
        card = next(c for c in f1["offer"] if c != f1["took"])
        choices = json.dumps([{"k": 1, "e": "offer", "j": 0, "pick": card}])
        run = ex.run("pin.json", i, choices)
        assert [f["line"] for f in run["floors"][:2]] == ["file", "file"]
        assert run["floors"][1]["events"][0]["chosen"] == card and run["floors"][1]["events"][0]["by"] == "owner"
        f2 = run["floors"][2]
        assert f2["line"] == "owner" and card in f2["start"]["deck"] and f2["fidelity"] is None
        assert run["pending"] == 2 and len(run["floors"]) == 3
        played = ex.floor("pin.json", i, 2, choices)
        assert played["line"] == "owner" and played["fidelity"] is None and card in played["spec"]["deck"]
        run2 = ex.run("pin.json", i, choices)
        assert run2["floors"][2]["result"] == played["replay"] and run2["pending"] in (3, None)
        # a taken-over fight's end HP carries to the next floor
        hp = 50 if row["floors"][0]["hp_end"] != 50 else 49
        choices = json.dumps([{"k": 0, "won": True, "hp": hp}])
        run3 = ex.run("pin.json", i, choices)
        assert run3["floors"][0]["result"] == {"won": True, "hp_end": hp} and run3["floors"][0]["line"] == "owner"
        assert run3["floors"][1]["start"]["hp"] == hp and run3["floors"][1]["line"] == "owner"
        # an offer pick outside the offer is refused
        try:
            ex.run("pin.json", i, json.dumps([{"k": 1, "e": "offer", "j": 0, "pick": "Not A Card"}]))
            raise AssertionError("expected a refusal")
        except ValueError:
            pass
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


class StubPlayers:
    """gauntlet.players' hooks for `explore.line`, each call counted: offers
    are the row's own (the seeded offer), the choosers must not be asked."""

    def __init__(self, row, strict=True):
        self.row, self.calls, self.strict = row, [], strict
        self.elite_offers, self.mid_rest = 1, None

    def offer(self, k, seq, j=0):
        self.calls.append(("offer", k, j))
        return self.row["floors"][k]["offer"]

    def _hook(name):
        def call(self, *args):
            self.calls.append((name,) + tuple(a for a in args if isinstance(a, int)))
            if self.strict:
                raise AssertionError(f"chooser {name} asked on the file's line")
            f = self.row["floors"][args[0]] if name == "reward" else None
            if name == "reward":
                return [(f["offer"], f["took"])]
            if name == "remove_hook":
                return [next((x["removed"] for x in self.row["floors"] if "removed" in x), None)]
            return [None]
        return call
    reward = _hook("reward")
    rest_hook = _hook("rest_hook")
    remove_hook = _hook("remove_hook")
    path_hook = None


def counted_outcome(row):
    """(outcome function, its calls): a fight off the file's line ends as the
    row's floor did (so HP rejoins), each call counted."""
    calls = []

    def outcome(k, spec):
        calls.append(k)
        f = row["floors"][k]
        return {"won": bool(f["won"]), "hp_end": int(f["hp_end"]) if f["won"] else 0}
    return outcome, calls


def pinned_line(choices, row=None, strict=True):
    with open(PIN, encoding="utf-8") as f:
        d = json.load(f)
    row = row or d["sequences"][0]
    seq = explore.sequence(d["settings"], row["i"])
    p = StubPlayers(row, strict)
    outcome, calls = counted_outcome(row)
    w = explore.line(d["settings"], seq, row, json.dumps(choices), outcome, p)
    return w, calls, p.calls, row


def test_explore_fight_redo_same_afterstate():
    """The owner's report: floor 0's fight finished one HP off the row's,
    then finished again with the row's result. The later entry replaces the
    earlier, the afterstate equals the row's, so every floor is the file's
    line and no fight is replayed."""
    with open(PIN, encoding="utf-8") as f:
        row = json.load(f)["sequences"][0]
    hp = int(row["floors"][0]["hp_end"])
    w, calls, hooks, _ = pinned_line([{"k": 0, "won": True, "hp": hp - 1}, {"k": 0, "won": True, "hp": hp}])
    assert [fl["line"] for fl in w["floors"]] == ["file"] * len(row["floors"]), [fl["line"] for fl in w["floors"]]
    assert calls == [] and [c for c in hooks if c[0] != "offer"] == []
    assert [h["changed"] for h in w["history"]] == [False]  # the later entry replaced the earlier


def test_explore_event_rejoins():
    """A different pick (Combust at floor 2, where the row skipped) leaves the
    file's line; removing Combust at the removal floor (where this row keeps
    every card) brings the deck back to the row's, so every later floor is
    the file's line again: no replay, no chooser asked."""
    with open(PIN, encoding="utf-8") as f:
        row = json.load(f)["sequences"][0]
    row = json.loads(json.dumps(row))
    rf = explore.gauntlet.REMOVE_FLOOR
    assert row["floors"][2]["took"] is None and "Combust" in row["floors"][2]["offer"]
    row["floors"][rf]["removed"] = None
    picks = [{"k": 2, "e": "offer", "j": 0, "pick": "Combust"}]
    picks += [{"k": k, "e": "offer", "j": 0, "pick": row["floors"][k]["took"]} for k in range(3, rf + 1)]
    picks += [{"k": rf, "e": "removal", "j": 0, "pick": "Combust"}]
    w, calls, hooks, _ = pinned_line(picks, row)
    lines = [fl["line"] for fl in w["floors"]]
    assert lines[:3] == ["file"] * 3 and set(lines[3:rf + 1]) == {"owner"}, lines
    assert lines[rf + 1:] == ["file"] * (len(row["floors"]) - rf - 1), lines
    assert calls == list(range(3, rf + 1)), calls  # only the fights off the file's line
    assert [c for c in hooks if c[0] != "offer"] == [], hooks
    assert sorted(w["deck"]) == sorted(explore.walk({}, explore.sequence(
        json.load(open(PIN, encoding="utf-8"))["settings"], row["i"]), row)["deck"])
    changed = [h["changed"] for h in w["history"]]
    assert changed[0] is True and changed[-1] is False, changed


def test_explore_history():
    """Choices are an ordered history: the list without its last entry gives
    the run before it; an empty list gives the recorded run."""
    with open(PIN, encoding="utf-8") as f:
        row = json.load(f)["sequences"][0]
    hist = [{"k": 1, "e": "offer", "j": 0, "pick": "Pummel"}, {"k": 0, "won": True, "hp": 60}]
    full, _, _, _ = pinned_line(hist, strict=False)
    undo, _, _, _ = pinned_line(hist[:-1], strict=False)
    one, _, _, _ = pinned_line([hist[0]], strict=False)
    empty, calls, _, _ = pinned_line([])
    assert [fl["line"] for fl in undo["floors"]] == [fl["line"] for fl in one["floors"]]
    assert undo["deck"] == one["deck"] and [fl["result"] for fl in undo["floors"]] == [fl["result"] for fl in one["floors"]]
    assert full["floors"][0]["result"] == {"won": True, "hp_end": 60} and full["floors"][1]["spec"]["hp"] == 60
    assert all(fl["line"] == "file" for fl in empty["floors"]) and calls == []
    assert len(empty["floors"]) == len(row["floors"]) and empty["history"] == []


def test_explore_run_event_options():
    """The run's choice events carry what the page offers to pick from: an
    offer its cards (skip is None), a rest "heal" then the deck's upgradable
    cards, a removal None (keep every card) then the deck's distinct cards,
    a path elite or hallway; on the file's line and on the owner's."""
    with open(PIN, encoding="utf-8") as f:
        d = json.load(f)
    res = results_dir({"pin.json": d})
    try:
        ex = gauntlet_explorer(res)
        i = d["sequences"][0]["i"]
        for choices in (None, json.dumps([{"k": 0, "won": True, "hp": 47}])):
            run = ex.run("pin.json", i, choices)
            kinds = set()
            for fl in run["floors"]:
                for ev in fl["events"]:
                    kinds.add(ev["kind"])
                    if ev["kind"] in ("offer", "extra"):
                        assert ev["options"] == list(ev["offer"]) + [None], ev
                    elif ev["kind"] == "rest":
                        assert ev["options"][0] == "heal" and len(ev["options"]) > 1, ev
                        assert all(not o.endswith("+") for o in ev["options"][1:]), ev
                    elif ev["kind"] == "removal":
                        assert ev["options"][0] is None and "Strike" in ev["options"], ev
                        assert len(set(ev["options"][1:])) == len(ev["options"]) - 1, ev
            if choices is None:
                assert {"offer", "rest", "removal"} <= kinds, kinds
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


# --- afterstates inside a fight (Amendment 1, A3) ------------------------------

def swapped_pair(ex, i, floors):
    """(k, n, a, b): the first recorded pair of actions n, n+1 on a floor of
    sequence i that reach the same state when played the other way round
    (b then a), found by playing both orders."""
    for k in floors:
        out = ex.floor("pin.json", i, k)
        decs = out["decisions"]
        for n in range(len(decs) - 2):
            a, b = decs[n]["action"], decs[n + 1]["action"]
            if a == b:
                continue
            c = ex.line_state(out, n, [], "pin.json")
            legal = {explore.enc(x): x for x in c.legal_actions()}
            if b not in legal:
                continue
            c.step(legal[b])
            if c.is_over() or not c.awaiting_action():
                continue
            legal = {explore.enc(x): x for x in c.legal_actions()}
            if a not in legal:
                continue
            c.step(legal[a])
            if c == ex.line_state(out, n + 2, [], "pin.json"):
                return k, n, a, b
    return None


def option_of(view, action):
    return next(j for j, o in enumerate(view["options"]) if action in o["actions"])


def test_explore_step_rejoins():
    """Inside a recorded fight, two cards played in the other order than the
    record reach recorded decision n+2's state: that step is "as played", on
    the record's handle, scored from the record (no new search)."""
    with open(PIN, encoding="utf-8") as f:
        d = json.load(f)
    res = results_dir({"pin.json": d})
    try:
        ex = gauntlet_explorer(res)
        i = d["sequences"][0]["i"]
        found = swapped_pair(ex, i, range(len(d["sequences"][0]["floors"])))
        assert found, "no commuting pair of recorded actions in the pinned sequence"
        k, n, a, b = found
        ctx = {"file": "pin.json", "i": i, "k": k}
        v = ex.state_view(n=n, **ctx)
        s1 = ex.step(None, option_of(v, b), 0, n=n, **ctx)
        assert s1["line"] == "your line"
        searched = []
        real = ex.player_scores

        def counted(*args, **kw):
            searched.append(args[5] if len(args) > 5 else kw.get("recorded"))
            return real(*args, **kw)
        ex.player_scores = counted
        s2 = ex.step(None, option_of(s1, a), 0, n=s1["handle"]["n"], steps=json.dumps(s1["handle"]["steps"]),
                     **ctx)
        assert s2["line"] == "as played", s2["line"]
        assert s2["handle"] == {"n": n + 2, "steps": []}
        assert s2["at"] == n + 2  # the page reads the recorded decision it is on again
        assert s2["player"]["source"] == "record"
        assert all(r is not None for r in searched), "a rejoined state was searched again"
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


def test_explore_fight_redo_in_fight():
    """The owner's report: leave the record, finish the fight differently
    (ending turns only), then go back to the start and finish it as played,
    with the page still saying its line left the record (`mine`): every step
    is "as played" and the end equals the row's and says so."""
    with open(PIN, encoding="utf-8") as f:
        d = json.load(f)
    res = results_dir({"pin.json": d})
    try:
        ex = gauntlet_explorer(res)
        i = d["sequences"][0]["i"]
        ctx = {"file": "pin.json", "i": i, "k": 0}
        out = ex.floor(**{"file": "pin.json", "i": i, "k": 0})
        # off the record: end the turn at every decision until the fight ends
        h, s = {"n": 0, "steps": []}, None
        for _ in range(400):
            v = ex.state_view(n=h["n"], steps=json.dumps(h["steps"]), **ctx)
            end = next(j for j, o in enumerate(v["options"]) if any("End" in x for x in o["actions"]))
            s = ex.step(None, end, 0, n=h["n"], steps=json.dumps(h["steps"]), mine="1", **ctx)
            if s.get("end"):
                break
            h = s["handle"]
        assert s["end"] != out["replay"] and s["end"]["as_recorded"] is False
        # back to the start, as played, with the page's sticky flag still set
        h = {"n": 0, "steps": []}
        for dec in out["decisions"]:
            v = ex.state_view(n=h["n"], steps=json.dumps(h["steps"]), **ctx)
            s = ex.step(None, option_of(v, dec["action"]), 0, n=h["n"], steps=json.dumps(h["steps"]), mine="1",
                        **ctx)
            assert s["line"] == "as played", (dec["n"], s["line"])
            h = s.get("handle", h)
        assert {k: s["end"][k] for k in ("won", "hp_end")} == out["replay"] and s["end"]["as_recorded"] is True
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


def check_cell(ex, fight):
    """A cell's replay matches its file, every decision's pick holds the action
    played, the state view scores decision 0 from the record and, recomputed
    now (`fresh`), the same; stepping the played option is "as played"."""
    out = ex.fight(json.dumps(fight))
    assert out["fidelity"]["matches"], (fight, out["fidelity"])
    for d in out["decisions"]:
        assert d["action"] in d["scores"]["options"][d["scores"]["pick"]]
    if not out["decisions"]:
        return out
    f = json.dumps(fight)
    v = ex.state_view(n=0, fight=f)
    w = ex.state_view(n=0, fight=f, fresh="1")
    assert v["player"]["source"] == "record" and w["player"]["source"] == "now"
    assert v["player"]["pick"] == w["player"]["pick"] == v["player"]["recorded"]
    assert v["player"]["one"] == w["player"]["one"] and v["player"]["two"] == w["player"]["two"]
    assert v["player"]["depth"] == out["depth"]
    if len(out["decisions"]) > 1:
        check_handles(ex, out, v, fight=f)
        if out["decisions"][0]["hex"] is not None:  # a state with a hex steps by it too
            s = ex.step(out["decisions"][0]["hex"], v["player"]["recorded"], n=1, fight=f)
            assert s["line"] == "as played" and s["hex"] == out["decisions"][1]["hex"]
    return out


def check_handles(ex, out, v, **ctx):
    """Stepping by line handle (no hex: the only name a state with generated
    content has): the recorded option is "as played" to the next decision's
    handle and board; another option is "your line", one step on."""
    s = ex.step(None, v["player"]["recorded"], n=0, **ctx)
    assert s["line"] == "as played" and s["handle"] == {"n": 1, "steps": []}
    assert s["board_data"] == out["decisions"][1]["board_data"] and s["hex"] == out["decisions"][1]["hex"]
    other = next((j for j in range(len(v["options"])) if j != v["player"]["recorded"]), None)
    if other is not None:
        y = ex.step(None, other, seed=3, n=0, **ctx)
        assert y["line"] == "your line" and y["handle"] == {"n": 0, "steps": [[other, 3]]}
        if "options" in y and y["options"] and not y.get("end"):
            z = ex.state_view(n=0, steps=json.dumps([[other, 3]]), **ctx)
            assert z["board_data"] == y["board_data"]


def test_explore_mutate_replay():
    """Small mutated-monster (heuristic one turn deep, and two turns deep
    with sampled chance, so the search seeds matter; a generated-enemy
    modifier among them) and mutated-card files made by the scripts: every
    cell's replay matches the file's win and end HP for its seed; the list
    endpoints show the file's own numbers."""
    import pytest
    mm, mc = explore.analysis("mutate_monsters"), explore.analysis("mutate_cards")
    res = results_dir({})
    mp = pytest.MonkeyPatch()
    try:
        os.makedirs(os.path.join(res, "mutate"))
        mp.setitem(mm.PLAYERS, "two", None)  # the heuristic two turns deep: cheap, and it samples
        mp.setattr(mm, "TWO_TURN", {"sample_k": 2, "turns": 2, "max_nodes": 4000})
        mods = ["str2", "hp0.8", mm.GEN_BATCH1[0]]
        mfile = os.path.join(res, "mutate", "m.json")
        mm.main(["play", "--product", PIN, "--starts", "2", "--seeds", "2", "--players", "heuristic,two",
                 "--two-starts", "1", "--two-seeds", "1", "--mods", ",".join(mods), "--threads", "1", "--out", mfile])
        cfile = os.path.join(res, "mutate", "c.json")
        mc.main(["play", "--product", PIN, "--starts", "1", "--seeds", "2", "--players", "heuristic",
                 "--mods", "bash-c1-d5", "--threads", "1", "--out", cfile])
        before = {p: file_state(p) for p in (mfile, cfile)}
        ex = gauntlet_explorer(res)
        files = {f["file"]: f for f in ex.files("mutate")["files"]}
        assert files["m.json"]["kind"] == "monsters" and files["c.json"]["kind"] == "cards"
        assert files["m.json"]["refused"] is None and files["c.json"]["refused"] is None
        m = ex.mutate("m.json")
        assert m["columns"] == ["parent"] + mods and m["total"] == 2 * (1 + len(mods))
        with open(mfile, encoding="utf-8") as f:
            raw = json.load(f)
        two_cells = 0
        cells = {(row["i"], row["floor"], row["column"]): row["cells"] for row in m["rows"]}
        for r in raw["rows"]:
            assert cells[(r["i"], r["floor"], "str2")]["heuristic"]["seeds"] == r["mods"]["str2"]["heuristic"]
            for col in ["parent"] + mods:
                by = r["parent"] if col == "parent" else r["mods"][col]
                for p, seeds in by.items():
                    for j in range(len(seeds)):
                        out = check_cell(ex, {"kind": "mutate", "file": "m.json", "i": r["i"], "floor": r["floor"],
                                              "mod": col, "player": p, "seed": j})
                        two_cells += out["depth"] == 2
        assert two_cells == 1 + len(mods)
        c = ex.mutate("c.json")
        assert c["kind"] == "cards" and c["columns"] == ["official", "parent", "bash-c1-d5"]
        with open(cfile, encoding="utf-8") as f:
            craw = json.load(f)
        assert craw["rows"], "no start holds Bash"
        for r in craw["rows"]:
            for col in ("official", "parent", "bash-c1-d5"):
                by = r[col] if col != "bash-c1-d5" else r["mods"][col]
                for j in range(len(by["heuristic"])):
                    check_cell(ex, {"kind": "mutate", "file": "c.json", "i": r["i"], "floor": r["floor"],
                                    "card": r["card"], "mod": col, "player": "heuristic", "seed": j})
        # a cached replay comes back the same
        f0 = {"kind": "mutate", "file": "m.json", "i": raw["rows"][0]["i"], "floor": raw["rows"][0]["floor"],
              "mod": "str2", "player": "heuristic", "seed": 0}
        a, b = ex.fight(json.dumps(f0)), ex.fight(json.dumps(f0))
        assert b["cached"] and a["decisions"] == b["decisions"]
        assert {p: file_state(p) for p in (mfile, cfile)} == before, "a result file changed"
        # the shown result is the player's own sts.play_on, as the script plays the cell
        cell = explore.mutate_cell(json.load(open(mfile, encoding="utf-8")), f0, ex.fights_of)
        r = sts.play_on([cell["combat"].clone()], threads=1, **cell["search"])[0]
        assert a["replay"] == {"won": bool(r["won"]), "hp_end": int(r["hp_end"])}
        # a loop that ends elsewhere than play_on is reported, not shown as the result
        real = explore.sts.play_on
        mp.setattr(explore.sts, "play_on", lambda cs, **kw: [{**x, "hp_end": int(x["hp_end"]) + 1}
                                                              for x in real(cs, **kw)])
        shutil.rmtree(os.path.join(os.path.dirname(res), "cache"))  # replay f0 again, not from the cache
        fresh = gauntlet_explorer(res)
        with pytest.raises(RuntimeError, match="stepping the recorded actions ends"):
            fresh.fight(json.dumps(f0))
    finally:
        mp.undo()
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


def test_explore_boss_replay():
    """Boss-replay files (an HP grid and arrival HP) made by boss_replay.py
    from a small gauntlet file: every cell's replay matches the file's win
    (and end HP on arrival) for its seed."""
    br = explore.analysis("boss_replay")
    import gauntlet
    res = results_dir({})
    try:
        os.makedirs(os.path.join(res, "boss_replay"))
        src = os.path.join(res, "gauntlet", "src.json")
        gauntlet.main(["play", "heuristic", "--sequences", "3", "--threads", "1", "--out", src])
        grid = os.path.join(res, "boss_replay", "grid.json")
        br.main(["play", "--file", src, "--player", "heuristic", "--seeds", "2", "--hp", "30,70", "--threads", "1",
                 "--out", grid])
        arr = os.path.join(res, "boss_replay", "arr.json")
        br.main(["play", "--file", src, "--player", "heuristic", "--seeds", "2", "--hp", "arrival", "--threads", "1",
                 "--out", arr])
        before = {p: file_state(p) for p in (src, grid, arr)}
        ex = gauntlet_explorer(res)
        files = {f["file"]: f for f in ex.files("boss_replay")["files"]}
        assert set(files) == {"grid.json", "arr.json"} and all(f["refused"] is None for f in files.values())
        g = ex.boss_replay("grid.json")
        assert g["total"] >= 1, "no sequence reached the boss"
        n = 0
        for row in g["rows"]:
            for hp in ("30", "70"):
                for j in range(2):
                    out = check_cell(ex, {"kind": "boss_replay", "file": "grid.json", "i": row["i"], "hp": hp,
                                          "seed": j})
                    assert out["fidelity"]["file"]["won"] == bool(row["won"][hp][j])
                    n += 1
        for row in ex.boss_replay("arr.json")["rows"]:
            for j in range(2):
                out = check_cell(ex, {"kind": "boss_replay", "file": "arr.json", "i": row["i"], "hp": "arrival",
                                      "seed": j})
                assert out["replay"]["hp_end"] == row["hp_end"][j]
                assert out["spec"]["hp"] == row["hp_obs"]
        assert n >= 4
        assert {p: file_state(p) for p in (src, grid, arr)} == before, "a result file changed"
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


def _cell(seeds):
    return {"wins": float(np.mean([bool(w) for w, _ in seeds])), "hp": float(np.mean([h if w else 0 for w, h in seeds])),
            "seeds": [[bool(w), int(h)] for w, h in seeds]}


MUT_FILE = {"settings": {"product": PIN, "seeds": 2, "two_seeds": 1, "mods": ["str2", "hp0.8", "sharp2"]},
            "rows": [{"i": i, "floor": fl, "encounter": enc, "group": grp, "hp": hp,
                      "parent": {"heuristic": [[True, 40 + i], [False, 0]], "one": [[True, 50 + i], [True, 30]]},
                      "mods": {m: {"heuristic": [[j % 2 == 0, 20 + j + i], [True, 10 + j]], "one": [[True, 5 + j], [False, 0]]}
                               for j, m in enumerate(["str2", "hp0.8", "sharp2"])}}
                     for i, fl, enc, grp, hp in [(0, 5, "gremlin_nob", "elite", 80), (1, 8, "lagavulin", "elite", 61),
                                                 (2, 10, "hexaghost", "boss", 55)]]}


def test_explore_mutate_grouping():
    """Amendment 3: a mutate file's modifiers are rows, never columns. Grouped
    by parent, each start is a group (parent row first, then one row per
    modifier); grouped by modifier, each modifier is a group (parent first),
    one row per start. Each row carries the file's own per-player numbers
    for its (start, column) cell; the encounter group is named "encounter
    type"."""
    res = results_dir({})
    try:
        os.makedirs(os.path.join(res, "mutate"))
        with open(os.path.join(res, "mutate", "m.json"), "w", encoding="utf-8") as f:
            json.dump(MUT_FILE, f)
        ex = gauntlet_explorer(res)
        cols = ["parent", "str2", "hp0.8", "sharp2"]
        want = {}
        for r in MUT_FILE["rows"]:
            for c in cols:
                by = r["parent"] if c == "parent" else r["mods"][c]
                want[(r["i"], c)] = {p: _cell(s) for p, s in by.items()}
        for by in ("parent", "modifier"):
            out = ex.mutate("m.json", by=by)
            assert out["by"] == by and out["total"] == len(want), out["total"]
            rows = out["rows"]
            assert all("column" in r and "encounter_type" in r and "group" not in r for r in rows), rows[0]
            assert {(r["i"], r["column"]): r["cells"] for r in rows} == want
            keys = [r["_group"] for r in rows]
            assert keys == sorted(keys, key=keys.index), "a group's rows are contiguous"
            if by == "parent":
                assert [r["column"] for r in rows[:4]] == cols and len(set(keys)) == 3
            else:
                assert [g for g in dict.fromkeys(keys)] == cols, keys
                assert [r["i"] for r in rows[:3]] == [0, 1, 2]
        # a filter on the encounter type keeps its starts only, either way
        assert {r["i"] for r in ex.mutate("m.json", by="modifier", etype="boss")["rows"]} == {2}
        # sorting works inside the groups: by the heuristic's wins, highest first
        out = ex.mutate("m.json", by="modifier", sort="wins:heuristic", desc="1")
        for g in cols:
            ws = [r["cells"]["heuristic"]["wins"] for r in out["rows"] if r["column"] == g]
            assert ws == sorted(ws, reverse=True)
        # Amendment 6: "none" is every row, ungrouped, sorted across the whole list
        out = ex.mutate("m.json", by="none")
        assert out["by"] is None and not out["groups"] and out["total"] == len(want)
        assert {(r["i"], r["column"]): r["cells"] for r in out["rows"]} == want
        assert [(r["i"], r["column"]) for r in out["rows"][:4]] == [(0, c) for c in cols]
        ws = [r["cells"]["heuristic"]["wins"] for r in ex.mutate("m.json", by="none", sort="wins:heuristic", desc="1")["rows"]]
        assert ws == sorted(ws, reverse=True)
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


def test_explore_boss_grouping():
    """Amendment 3: a boss-replay file grouped by HP has one group per entry
    HP level (in the file's order), one row per sequence with its boss, deck
    size and per-seed wins equal to today's grid; grouped by sequence it is
    today's grid."""
    rows = [{"i": i, "half": "train" if i % 2 == 0 else "held_out", "boss": b, "deck": ["Strike"] * (10 + i),
             "hp_obs": 40 + i, "won_obs": i % 2 == 0, "won": {"30": [i % 2, 1], "70": [1, 1 - i % 2]}}
            for i, b in [(0, "slime_boss"), (3, "hexaghost"), (4, "the_guardian")]]
    res = results_dir({})
    try:
        os.makedirs(os.path.join(res, "boss_replay"))
        with open(os.path.join(res, "boss_replay", "g.json"), "w", encoding="utf-8") as f:
            json.dump({"settings": {"file": PIN, "player": "heuristic", "hp": [30, 70], "seeds": 2}, "skipped": 0,
                       "rows": rows}, f)
        ex = gauntlet_explorer(res)
        grid = ex.boss_replay("g.json")
        assert [r["i"] for r in grid["rows"]] == [0, 3, 4] and "won" in grid["rows"][0]
        out = ex.boss_replay("g.json", by="hp")
        assert out["by"] == "hp" and out["total"] == 6
        assert list(dict.fromkeys(r["_group"] for r in out["rows"])) == ["HP 30", "HP 70"]
        for r in out["rows"]:
            src = next(x for x in rows if x["i"] == r["i"])
            assert r["level"] in ("30", "70") and r["won"] == src["won"][r["level"]]
            assert r["boss"] == src["boss"] and r["deck_size"] == len(src["deck"])
            assert r["wins"] == float(np.mean(src["won"][r["level"]]))
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


def test_explore_sequences_grouping():
    """Amendment 3: the shared group-by on a categorical column: sequences
    grouped by boss come in contiguous groups, each sorted inside."""
    ex = gauntlet_explorer(results_dir({"pin.json": json.load(open(PIN, encoding="utf-8"))}))
    out = ex.sequences("pin.json", by="boss", sort="end_hp", desc="1")
    keys = [r["_group"] for r in out["rows"]]
    assert keys and keys == sorted(keys, key=keys.index)
    for g in set(keys):
        hp = [r["end_hp"] for r in out["rows"] if r["_group"] == g]
        assert hp == sorted(hp, reverse=True)
    import pytest
    with pytest.raises(ValueError):
        ex.sequences("pin.json", by="strip")


def test_explore_puzzles_grouping():
    """Amendment 3: puzzles grouped by set hold the same rows as ungrouped,
    in contiguous groups per set, each row tagged with its set; by encounter
    too; another column is refused."""
    with tempfile.TemporaryDirectory() as d:
        ex = explorer(cache=d)
        plain = ex.puzzle_list(sort="gap", desc="1")
        flat = [r for p in range(plain["pages"]) for r in ex.puzzle_list(sort="gap", desc="1", page=p)["rows"]]
        out = ex.puzzle_list(sort="gap", desc="1", by="half")
        got = [r for p in range(out["pages"]) for r in ex.puzzle_list(sort="gap", desc="1", by="half", page=p)["rows"]]
        assert out["by"] == "half" and out["total"] == plain["total"] == len(got)
        assert sorted(r["id"] for r in got) == sorted(r["id"] for r in flat)
        assert all(r["_group"] == r["half"] for r in got)
        keys = [r["_group"] for r in got]
        assert len(set(keys)) > 1 and keys == sorted(keys, key=keys.index)
        assert [g["n"] for g in out["groups"]] == [keys.count(g["key"]) for g in out["groups"]]
        for g in set(keys):
            assert [r["id"] for r in got if r["_group"] == g] == [r["id"] for r in flat if r["half"] == g]
        enc = ex.puzzle_list(by="encounter")
        assert all(r["_group"] == r["encounter"] for r in enc["rows"])
        import pytest
        with pytest.raises(ValueError):
            ex.puzzle_list(by="gap")


def test_explore_generated_floor():
    """A gauntlet floor whose deck holds a pack card (generated content: no
    state encoding) replays and matches its row; its decisions carry their
    board but no hex, and the state view and steps name them by line handle."""
    import gauntlet
    res = results_dir({})
    try:
        src = os.path.join(res, "gauntlet", "pack.json")
        gauntlet.main(["play", "heuristic", "--sequences", "2", "--threads", "1", "--start", "starter", "--rewards",
                       "random", "--pack", "content/packs/act1-ironclad.json", "--out", src])
        with open(src, encoding="utf-8") as f:
            d = json.load(f)
        ex = gauntlet_explorer(res)
        found = None
        for r in d["sequences"]:
            took = [fl.get("took") or "" for fl in r["floors"]]
            k = next((j + 1 for j, t in enumerate(took) if t.startswith("gen:")), None)
            if k is not None and k < len(r["floors"]):
                found = (r["i"], k)
                break
        assert found, "no sequence took a pack card before its last floor"
        i, k = found
        out = ex.floor("pack.json", i, k)
        assert out["fidelity"]["matches"], out["fidelity"]
        assert out["decisions"] and all(x["hex"] is None and x["board_data"] for x in out["decisions"])
        v = ex.state_view(file="pack.json", i=i, k=k, n=0)
        assert v["hex"] is None and v["handle"] == {"n": 0, "steps": []} and v["player"]["source"] == "record"
        assert v["player"]["pick"] == v["player"]["recorded"]
        if len(out["decisions"]) > 1:
            check_handles(ex, out, v, file="pack.json", i=i, k=k)
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


def test_explore_content_tables():
    """A table per content kind (docs/specs/explorer-v2.md, Amendment 3):
    each kind names its own columns and every row carries them; cost sorts
    as numbers, then X, then Unplayable; encounters are a fourth kind with
    their type and monsters; every column sorts both ways."""
    res = results_dir({"pin.json": json.load(open(PIN, encoding="utf-8"))})
    try:
        ex = gauntlet_explorer(res)
        want = {"cards": ["name", "cost", "type", "class", "keywords", "source", "text"],
                "monsters": ["name", "hp", "moves", "start_powers", "source"],
                "powers": ["name", "debuff", "source", "text"],
                "encounters": ["name", "type", "monsters", "source"]}
        for kind, cols in want.items():
            out = ex.content(kind)
            assert [c["key"] for c in out["columns"]] == cols, (kind, out["columns"])
            assert out["entries"], kind
            for e in out["entries"]:
                assert set(cols) <= set(e["cols"]), (kind, e["id"], e["cols"])
            for c in cols:  # every column sorts, both ways, keeping every row
                for desc in ("0", "1"):
                    s = ex.content(kind, sort=c, desc=desc)
                    assert sorted(x["id"] + x["source"] for x in s["entries"]) == \
                        sorted(x["id"] + x["source"] for x in out["entries"]), (kind, c)
        cards = ex.content("cards", sort="cost")["entries"]
        rank = [0 if isinstance(e["cols"]["cost"], int) else 1 if e["cols"]["cost"] == "X" else 2 for e in cards]
        assert rank == sorted(rank) and 0 in rank and 1 in rank and 2 in rank, [e["cols"]["cost"] for e in cards]
        nums = [e["cols"]["cost"] for e in cards if isinstance(e["cols"]["cost"], int)]
        assert nums == sorted(nums)
        burn = next(e for e in cards if e["id"] == "Burn")
        assert burn["cols"]["cost"] == "Unplayable"
        groups = [g["key"] for g in ex.content("cards", by="cost")["groups"]]  # groups keep the cost order
        assert groups[-2:] == ["X", "Unplayable"] and groups[:-2] == sorted(groups[:-2]), groups
        ww = next(e for e in cards if e["id"] == "Whirlwind")
        assert ww["cols"]["cost"] == "X" and ww["cols"]["class"] == "Ironclad" and ww["cols"]["type"] == "Attack"
        encs = {e["id"]: e for e in ex.content("encounters")["entries"]}
        assert encs["cultist"]["cols"]["type"] == "hallway" and "Cultist" in encs["cultist"]["cols"]["monsters"]
        assert encs["gremlin_nob"]["cols"]["type"] == "elite" and encs["hexaghost"]["cols"]["type"] == "boss"
        assert any(e["source"].startswith("pack:") for e in encs.values()), "pack encounters listed"
        cul = next(e for e in ex.content("monsters")["entries"] if e["id"] == "Cultist")
        assert cul["cols"]["hp"] == "48–54" and "Incantation" in cul["cols"]["moves"]
        assert ex.content("encounters", by="type")["groups"]
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


def test_explore_relics():
    """Relics are a content kind (docs/specs/relics.md step 6): official
    (Burning Blood) and pack relics with rarity, start powers, fight kinds
    and text worded from content/wording.json; every column sorts; groups by
    rarity follow the game's order."""
    ex = explore.Explorer()
    out = ex.content("relics")
    assert [c["key"] for c in out["columns"]] == ["name", "rarity", "powers", "fights", "source", "text"]
    rel = {(e["source"], e["id"]): e for e in out["entries"]}
    bb = rel[("official", "Burning Blood")]
    assert bb["cols"]["rarity"] == "starter" and bb["cols"]["powers"] == [] and "Heal 6 HP" in bb["cols"]["text"]
    assert bb["desc"]["head"] == "Burning Blood · Starter relic"
    pack = {i: e for (s, i), e in rel.items() if s == "pack:act1-relics"}
    with open(os.path.join(os.path.dirname(__file__), "..", "..", "content", "packs", "act1-relics.json"), encoding="utf-8") as f:
        assert len(pack) == len(json.load(f)["relics"])  # every relic in the pack file shows
    assert pack["Vajra"]["cols"]["powers"] == ["Strength 1"] and pack["Vajra"]["cols"]["rarity"] == "common"
    collar = pack["Slaver's Collar"]
    assert collar["cols"]["fights"] == ["elite", "boss"] and "Acts only in elite fights and boss fights." in collar["desc"]["lines"]
    assert "At the start of your turn: gain 1 energy." in collar["cols"]["text"]
    assert explore.describe("relics", "gen:Vajra", "pack:act1-relics") == pack["Vajra"]["desc"]
    for c, _ in explore.CONTENT_COLUMNS["relics"]:
        for desc in ("0", "1"):
            assert len(ex.content("relics", sort=c, desc=desc)["entries"]) == len(out["entries"]), c
    rar = [e["cols"]["rarity"] for e in ex.content("relics", sort="rarity")["entries"]]
    assert rar[0] == "starter" and rar == sorted(rar, key=explore.RARITY_ORDER.index)
    groups = [g["key"] for g in ex.content("relics", by="rarity")["groups"]]
    assert groups == sorted(groups, key=explore.RARITY_ORDER.index), groups
    assert not explore.UNWORDED


def test_explore_content():
    """The content browser lists every card, monster and power of every
    source with its file's own numbers; with a gauntlet file, a card links
    to the sequences whose final deck held it and those that took it, a
    monster to the floors that fought it (a direct scan of the file)."""
    import glob
    import gauntlet
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
    import mutate_cards
    import mutate_monsters
    repo = os.path.join(os.path.dirname(__file__), "..", "..")
    expect = {}

    def add(source, d):
        for kind in ("cards", "monsters", "powers"):
            for e in d.get(kind, []):
                expect.setdefault(kind, {}).setdefault(source, []).append(e)
                # a card with an upgrade block lists its upgrade after it
                up = kind == "cards" and explore.upgraded_card(e, source == "official", d.get("version", 2))
                if up:
                    expect[kind][source].append(up)
    off = {}
    for kind in ("cards", "monsters", "powers"):
        with open(os.path.join(repo, "content", f"{kind}.json"), encoding="utf-8") as f:
            off[kind] = json.load(f)[kind]
    add("official", off)
    for p in sorted(glob.glob(os.path.join(repo, "content", "packs", "*.json"))):
        with open(p, encoding="utf-8") as f:
            add("pack:" + os.path.splitext(os.path.basename(p))[0], json.load(f))
    add("mutated-cards", mutate_cards.pack())
    add("generated-enemies", json.loads(mutate_monsters.gen_pack()))

    res = results_dir({"pin.json": json.load(open(PIN, encoding="utf-8"))})
    try:
        ex = gauntlet_explorer(res)
        for kind, by_source in expect.items():
            out = ex.content(kind)
            got = {}
            for e in out["entries"]:
                got.setdefault(e["source"], []).append(e["data"])
            assert {s: len(v) for s, v in got.items()} == {s: len(v) for s, v in by_source.items()}, kind
            assert got == by_source, kind  # the files' own numbers, in file order
            assert out["total"] == sum(len(v) for v in by_source.values())
        one = ex.content("cards", source="official", q="strike")
        assert one["entries"] and all("strike" in e["id"].lower() and e["source"] == "official" for e in one["entries"])

        with open(PIN, encoding="utf-8") as f:
            d = json.load(f)
        st = d["settings"]
        decks, took, fought = {}, {}, {}
        for r in d["sequences"]:
            seq = explore.sequence(st, r["i"])
            for c in set(explore.walk(st, seq, r)["deck"]):
                decks.setdefault(c, []).append(r["i"])
            for k, fl in enumerate(r["floors"]):
                for t in [fl.get("took")] + [x.get("took") for x in fl.get("extra", [])]:
                    if t:
                        took.setdefault(t, set()).add(r["i"])
                c = sts.Combat(list(seq["deck"]), fl["encounter"], seed=seq["fights"][k]["seed"],
                               character=seq["character"])
                for m in {m["name"] for m in c.board()["monsters"]}:
                    fought.setdefault(m, []).append({"i": r["i"], "k": k, "encounter": fl["encounter"]})
        cards = {e["id"]: e for e in ex.content("cards", source="official", file="pin.json")["entries"]}
        assert any(cards[c]["decks"] for c in cards)
        for cid, e in cards.items():
            assert e["decks"] == sorted(decks.get(cid, [])), cid
            assert e["took"] == sorted(took.get(cid, set())), cid
        mons = {e["id"]: e for e in ex.content("monsters", source="official", file="pin.json")["entries"]}
        assert any(mons[m]["floors"] for m in mons)
        for mid, e in mons.items():
            assert e["floors"] == fought.get(mid, []), mid
        assert "decks" not in ex.content("cards")["entries"][0]  # links only with a file
        status, body = explore.respond(ex, "/api/content", "kind=powers&source=generated-enemies")
        assert status == 200 and body["total"] == len(expect["powers"]["generated-enemies"])
    finally:
        shutil.rmtree(os.path.dirname(res), ignore_errors=True)


def test_explore_card_text():
    """Card, move and power text in the game's own words (docs/specs/explorer-v2.md,
    Amendment 3): the card head is "Name · N Cost · [Rarity · Class ·] Type"
    (X Cost, Unplayable), no explanations in parentheses, keywords kept as
    keywords. Names keep their own parentheses ("Acid Slime (M)")."""
    ix = explore.describe_index()
    assert ix["cards"]["Whirlwind"]["head"] == "Whirlwind · X Cost · Ironclad · Attack", ix["cards"]["Whirlwind"]
    assert ix["cards"]["Burn"]["head"] == "Burn · Unplayable · Status", ix["cards"]["Burn"]
    assert ix["cards"]["Bash"]["head"] == "Bash · 2 Cost · Ironclad · Attack", ix["cards"]["Bash"]
    bash = _desc_text(ix["cards"]["Bash"])
    assert "Vulnerable" in bash and "more damage" not in bash and "1.5" not in bash, bash
    names = set()
    for src, data in explore.content_sources():
        for kind in ("cards", "monsters", "powers"):
            names |= {e["id"] for e in data.get(kind, [])}
        for m in data.get("monsters", []):
            names |= {mv["name"] for mv in m.get("moves", [])}
    paren = [n for n in names if "(" in n]

    def clean(t):
        for n in sorted(paren, key=len, reverse=True):
            t = t.replace(n, "")
        return t
    texts = [(k, n, _desc_text(d)) for k in ("cards", "powers") for n, d in ix[k].items()]
    texts += [("moves", f"{mon}/{n}", _desc_text(d)) for mon, mv in ix["moves"].items() for n, d in mv.items()]
    texts += [("engine", n, t) for n, t in {**explore.CODE_MONSTERS, **explore.CODE_POWERS}.items()]
    bad =[(k, n, t) for k, n, t in texts if "(" in clean(t)]
    assert not bad, bad[:5]


def _desc_text(d):
    """A description ({head, lines}) as one string."""
    return " ".join([d["head"]] + list(d["lines"]))


def test_explore_monster_rules():
    """A monster's hover card (Amendment 3): a divider between its move set
    and how it picks its moves, every pick rule listed (Hexaghost's 17
    too, no rule count standing in), and no divider or heading for a
    monster with no rules or engine-held behaviour."""
    ix = explore.describe_index()
    mons = {}
    for _, d in explore.content_sources():
        for m in d.get("monsters", []):
            mons.setdefault(m["id"], m)
    hexa = ix["monsters"]["Hexaghost"]["lines"]
    assert explore.DIVIDER in hexa, hexa
    after = hexa[hexa.index(explore.DIVIDER) + 1:]
    rules = mons["Hexaghost"]["pattern"]
    assert len(rules) == 17
    assert not any("pattern of" in ln for ln in hexa), hexa
    assert any(ln.startswith("How it picks its move") for ln in after), after
    assert sum(1 for ln in after if ln.endswith(".") and ":" in ln) >= len(rules), after
    rule_lines = [ln for ln in after if ln.startswith(("After", "On its", "Otherwise"))]
    assert len(rule_lines) == len(set(rule_lines)) == len(rules), rule_lines  # moves sharing a name told apart
    before = hexa[:hexa.index(explore.DIVIDER)]
    assert not any(ln.startswith("How it picks") for ln in before), before
    for name, d in ix["monsters"].items():
        m = mons.get(name)
        if m and not m.get("pattern") and not m.get("code"):
            assert explore.DIVIDER not in d["lines"], (name, d)
            assert not any(ln.startswith("How it picks") for ln in d["lines"]), (name, d)
    sg = ix["monsters"]["Shield Gremlin"]["lines"]  # a condition without a value (Allies)
    assert any("while another enemy is alive" in ln.lower() for ln in sg), sg


def test_explore_describe():
    """Tooltips say what their label doesn't (docs/specs/explorer-v2.md,
    Amendment 1): plain-words descriptions generated from the content data.
    A non-damage move says what it does with no damage talk; damage moves
    name their damage and hits; a power says what it does per stack; every
    card, monster, move, power and encounter of every source gets a text
    that differs from its name, and no describer raises."""
    ix = explore.describe_index()
    inc = ix["moves"]["Cultist"]["Incantation"]
    assert "gain 3 ritual" in _desc_text(inc).lower(), inc
    assert "damage" not in _desc_text(inc).lower(), inc
    assert "deal 6 damage" in _desc_text(ix["moves"]["Cultist"]["Dark Strike"]).lower()
    multi = [d for mon in ix["moves"].values() for d in mon.values()
             if any("damage" in ln.lower() and " times" in ln for ln in d["lines"])]
    assert multi, "a multi-hit move names its hits"
    sear = ix["moves"]["Hexaghost"]["Sear"]["lines"]  # two moves share the name: each stays whole, in order
    assert sear[0] == "One of:" and len(sear) == 3 and all(ln.startswith("Deal 6 damage.") for ln in sear[1:]), sear
    strength = _desc_text(ix["powers"]["Strength"]).lower()
    assert "damage" in strength and "per stack" in strength, strength
    assert "debuff" in _desc_text(ix["powers"]["Weak"]).lower()
    enc = _desc_text(ix["encounters"]["two_louse"])
    assert "Red Louse" in enc and "Green Louse" in enc and "HP" in enc, enc
    assert "hallway" in enc
    counts = {}
    for kind in ("cards", "monsters", "powers", "encounters"):
        for name, d in ix[kind].items():
            text = _desc_text(d)
            assert d["lines"] or d["head"] != name, (kind, name)
            assert text.strip() and text.strip() != name, (kind, name, d)
            counts[kind] = counts.get(kind, 0) + 1
    for mon, moves in ix["moves"].items():
        for name, d in moves.items():
            assert d["lines"] and _desc_text(d).strip() != name, (mon, name, d)
    # every entry of every content source is described
    for kind in ("cards", "monsters", "powers"):
        for src, data in explore.content_sources():
            for e in data.get(kind, []):
                assert explore.describe(kind, e["id"], src) is not None, (kind, src, e["id"])
    assert counts["encounters"] >= 17
    # the board carries them: monster, intent, power, card in hand
    c = sts.Combat(list(sts.starter_deck("ironclad")), "cultist", seed=1)
    bd = explore.board_of(c)
    m = bd["monsters"][0]
    assert m["desc"]["head"] != m["name"] and m["intent"]["desc"]["lines"]
    assert "Ritual" in _desc_text(m["intent"]["desc"])
    assert all(h.get("desc") for h in bd["hand"])
    assert set(bd["describe"]["cards"]) >= {n for n, _ in bd["piles"]["draw"]["cards"]}
    # content entries carry theirs
    ex_entries = explore.Explorer.content(None, "powers", source="official")["entries"]
    assert all(e["desc"]["lines"] for e in ex_entries)


def test_explore_group_pages():
    """Each group names the page its first row is on (docs/specs/explorer-v2.md,
    Amendment 4), so the page's jump bar can open a group on another page."""
    rows = [{"i": i, "g": f"g{i % 7}"} for i in range(5 * explore.GROUP_PAGE)]
    for page in range(5):
        out = explore.group_page(rows, "g", None, None, "i", page)
        for g in out["groups"]:
            first = explore.group_page(rows, "g", None, None, "i", g["page"])["rows"]
            prev = explore.group_page(rows, "g", None, None, "i", g["page"] - 1)["rows"] if g["page"] else []
            assert any(r["_group"] == g["label"] for r in first), g
            assert not any(r["_group"] == g["label"] for r in prev), g
    assert {g["page"] for g in out["groups"]} != {0}
    assert all(g["page"] == 0 for g in explore.group_page(rows[:10], "g", None, None, "i", 0)["groups"])


WORDING_PIN = os.path.join(os.path.dirname(__file__), "data", "explore", "wording_pin.json")


def wording_snapshot():
    """Every description the explorer gives (docs/specs/element-wording.md):
    describe_index() for every source, plus each content table row's text
    columns (an encounter's monster list, a card's text)."""
    ix = explore.describe_index()
    ex = explore.Explorer()
    rows = {}
    for kind in explore.CONTENT_KINDS:
        for e in ex.content(kind)["entries"]:
            rows[f"{kind}/{e['source']}/{e['id']}"] = {k: v for k, v in e["cols"].items() if isinstance(v, str)}
    return json.loads(json.dumps({"describe": ix, "rows": rows}))


def test_explore_wording():
    """The element-wording spec: every description of every content source
    equals the pin written before the wording moved to content/wording.json,
    and none falls back to an element's raw engine name."""
    with open(WORDING_PIN, encoding="utf-8") as f:
        pin = json.load(f)
    now = wording_snapshot()
    diff = [(g, k) for g in pin for k in set(pin[g]) | set(now[g]) if pin[g].get(k) != now[g].get(k)]
    assert not diff, [(g, k, pin[g].get(k), now[g].get(k)) for g, k in diff[:5]]
    assert not explore.UNWORDED, f"no wording in content/wording.json for {sorted(explore.UNWORDED)}"


def test_explore_words_heal_of():
    """fractional-amounts: a fraction of a quantity reads "1/5 of ...", and
    HealOf of max HP reads as Blood Potion's heal."""
    e = {"HealOf": {"base": 0, "k": "1/5", "of": "OwnMaxHp"}}
    assert explore.effect_text(e, "card") == "heal HP equal to 1/5 of your max HP"
    assert explore._amount({"base": 2, "k": "3/10", "of": "OwnBlock"}) == "2 + 3/10 of your Block"
    assert explore._amount({"base": 0, "k": 2, "of": "OwnBlock"}) == "2 × your Block"


def test_explore_describes_upgrades():
    """Every card of every source with an upgrade block has its X+
    described, from the engine's resolution of the block (sts.card_level):
    Bash+ in the game's words, and each X+ listed in the cards table."""
    ix = explore.describe_index()["cards"]
    assert ix["Bash+"]["lines"] == ["Deal 10 damage.", "Apply 3 Vulnerable."]
    rows = {(e["source"], e["id"]) for e in explore.Explorer().content("cards")["entries"]}
    n = 0
    for src, d in explore.content_sources():
        for c in d.get("cards", []):
            if "upgrade" in c:
                assert c["id"] + "+" in ix, (src, c["id"])
                assert (src, c["id"] + "+") in rows, (src, c["id"])
                n += 1
    assert n >= 90, n
