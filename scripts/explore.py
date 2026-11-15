"""Explorer: a local, read-only page for experiencing the game as the net
plays it (docs/specs/explorer.md, docs/specs/explorer-v2.md; decisions
"Explorer v2 as built").

    python scripts/explore.py [--port 8765]

Serves http://127.0.0.1:8765 (127.0.0.1 only), styled with the dashboard's
stylesheet (`/ui.css` is `dashboard.CSS`). Nothing is chosen at start: the
page picks the database (`/api/dbs`, `/api/open_db`, `/api/close_db`) and
the players whose one-turn scores show beside the heuristic's (`with=`;
`/api/nets` lists the nets).

What it opens:
- gauntlet files (`/api/files`, `/api/sequences`, `/api/run`, `/api/event`,
  `/api/floor`): a fight is replayed by the file's own player
  (`gauntlet.players`), checked against the file's row (fidelity), and its
  decisions shown with the player's own scores;
- mutate and boss-replay files (`/api/mutate`, `/api/boss_replay`,
  `/api/fight`), rebuilt by those scripts' own functions;
- content (`/api/content`): cards, monsters and powers by source;
- the bench puzzles and, with a database of this rules version open, run
  positions and rows (`/api/puzzles`, `/api/positions`, `/api/state`,
  `/api/solve`, `/api/reopen`).
Any state (`/api/view`, `/api/step`) shows the board (`Combat.board()`),
the net's input rows and static value, and the options with each
player's score; stepping an option, inside a fight or between floors
(`choices`), takes over from the recorded line. A state `Combat.encode`
refuses (pack cards, generated powers) is named by its replay's decision
and the steps since (`n`, `steps`).

Read-only: nothing writes a database, a result file or content; database
listings use sqlite3 mode=ro and a stale database is refused (opening it
would write a version row). It writes only caches under cache/explore/
(puzzle picks, replays). It imports its own copy of `sts`
(cache/explore/sts-<pyd hash>/), so an open explorer never blocks
rebuilding main's module.
"""

import argparse
import copy
import glob
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import sqlite3
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
STS_COPIES = os.environ.get("EXPLORE_STS_ROOT") or os.path.join(REPO, "cache", "explore")  # tests set it


def private_sts(root=STS_COPIES):
    """Puts a copy of the installed `sts` package first on sys.path, so this
    process loads the copy and never holds main's `.pyd` (AGENTS.md). The
    copy lives in `root/sts-<first 12 hex of the .pyd's sha256>/sts/`, made
    once per build; older copies are deleted where Windows allows (one
    another explorer holds stays). Returns the build hash, or None when
    `sts` is already imported (then nothing changes)."""
    if "sts" in sys.modules:
        return None
    spec = importlib.util.find_spec("sts")
    if spec is None or not spec.submodule_search_locations:
        return None
    src = list(spec.submodule_search_locations)[0]
    pyd = next((f for f in os.listdir(src) if f.endswith((".pyd", ".so"))), None)
    if pyd is None:
        return None
    h = hashlib.sha256()
    with open(os.path.join(src, pyd), "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    tag = h.hexdigest()[:12]
    os.makedirs(root, exist_ok=True)
    home = os.path.join(root, f"sts-{tag}")
    # complete only with its __init__.py: another explorer's cleanup can leave just a locked .pyd
    if not all(os.path.isfile(os.path.join(home, "sts", f)) for f in (pyd, "__init__.py")):
        tmp = f"{home}.tmp{os.getpid()}"
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(src, os.path.join(tmp, "sts"), ignore=shutil.ignore_patterns("__pycache__"))
        shutil.rmtree(home, ignore_errors=True)  # a half-deleted copy, so the replace can land
        try:
            os.replace(tmp, home)
        except OSError:  # another explorer made it first, or a held .pyd keeps the half copy
            if os.path.isfile(os.path.join(home, "sts", "__init__.py")):
                shutil.rmtree(tmp, ignore_errors=True)
            else:
                home = tmp  # load our own copy; the next start without that holder cleans it
    for d in os.listdir(root):
        if d.startswith("sts-") and os.path.join(root, d) != home and d != f"sts-{tag}":
            shutil.rmtree(os.path.join(root, d), ignore_errors=True)
    sys.path.insert(0, home)
    return tag


BUILD = private_sts()

import numpy as np  # noqa: E402

import bench  # noqa: E402
import bench_decisions  # noqa: E402
import bench_sets  # noqa: E402
import learn  # noqa: E402
import progress  # noqa: E402
import puzzles  # noqa: E402
import registry  # noqa: E402
import sts  # noqa: E402
import gauntlet  # noqa: E402  (after sts: it imports the private copy's module)

PORT = 8765
PAGE = 25
LIMIT = puzzles.LIMIT
SOLVE_NODES = puzzles.MAX_NODES
CACHE_DIR = os.path.join(REPO, "cache", "explore")
DB_DIR = "db"
RESULTS = os.path.join(REPO, "results")
REPLAY_VERSION = 4  # part of every replay cache key; raise it when a replay's content changes
PRODUCT = os.path.join("configs", "product.json")
PICK_CHUNK = 50  # puzzles per progress update while picks are computed
HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "explore.html")
HEURISTIC = "heuristic"


def parse_steps(steps):
    """A line handle's steps after its recorded decision: [[option, seed], ...]
    (JSON text, a list, or empty)."""
    if steps in (None, "", "[]"):
        return []
    xs = json.loads(steps) if isinstance(steps, str) else steps
    return [[int(o), int(sd)] for o, sd in xs]


def hex_of(c):
    """A state's codec bytes as hex, or None: a state holding generated content
    (pack cards, pack monsters or powers) has no encoding, so the page names
    it by its line instead (a replay's decision and the steps after it)."""
    try:
        return c.encode().hex()
    except ValueError:
        return None


def enc(a):
    return bench_decisions.encode_action(a)


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:12]


def build_hash():
    """The 12-hex hash naming the loaded `sts` build: the private copy's, else
    the loaded `.pyd`'s own."""
    if BUILD:
        return BUILD
    mod = getattr(sts, "sts", None)
    path = getattr(mod, "__file__", None)
    return file_hash(path) if path and os.path.exists(path) else None


_FINGERPRINT = []


def current_fingerprint():
    """This build's rules fingerprint, read from a throwaway database (opening
    one under a path writes a version row, so never the real one)."""
    if not _FINGERPRINT:
        with tempfile.TemporaryDirectory() as d:
            _FINGERPRINT.append(sts.SolvedDb(os.path.join(d, "fp.sqlite")).fingerprint)
    return _FINGERPRINT[0]


def ro_connect(path):
    return sqlite3.connect(pathlib.Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def check_db(path):
    """Raises ValueError unless `path` holds rows of the current rules version,
    so that opening it with sts.SolvedDb writes nothing."""
    if not os.path.exists(path):
        raise ValueError(f"{path}: no such database")
    con = ro_connect(path)
    try:
        row = con.execute("SELECT 1 FROM states WHERE version = (SELECT id FROM versions WHERE fingerprint = ?) LIMIT 1",
                          (current_fingerprint(),)).fetchone()
    except sqlite3.Error as e:
        raise ValueError(f"{path}: not a solved-state database ({e})") from e
    finally:
        con.close()
    if row is None:
        raise ValueError(f"{path}: no rows of this build's rules version; opening it would write one")


def resolve_model(spec, runs=None):
    """A run id (its <runs>/<id>/model.pt) or a path to a .pt."""
    if os.path.exists(spec):
        return spec
    path = os.path.join(runs or registry.runs_dir(), spec, "model.pt")
    if not os.path.exists(path):
        raise ValueError(f"no model {spec!r} (a .pt path or a run id with runs/<id>/model.pt)")
    return path


def shown(path):
    """A path as the page names it: relative to the repo, with "/", when it
    lies inside the repo (as result files write players), else absolute."""
    full = os.path.normpath(os.path.abspath(path))
    if os.path.normcase(full).startswith(os.path.normcase(REPO + os.sep)):
        full = os.path.relpath(full, REPO)
    return full.replace("\\", "/")


def loadable(name):
    """A shown player name as the bench loads it (a repo-relative net made
    absolute, so the server's working folder doesn't matter)."""
    if name == HEURISTIC or os.path.isabs(name.partition("@")[0]):
        return name
    return os.path.join(REPO, name).replace("\\", "/")


def resolve_player(spec, runs=None):
    """A player string as the bench takes it: "heuristic", or a net (a .pt
    path or a run id) with any search settings (`@hpb0.01`, ...; a bad one is
    refused with bench.player_settings' message)."""
    spec = spec.strip()
    if spec == HEURISTIC:
        return spec
    base, sep, rest = spec.partition("@")
    full = shown(resolve_model(base, runs)) + sep + rest
    if sep:
        bench.player_settings(full)
    return full


def evaluator_label(spec):
    """The picks cache's name for a player: the net file's hash plus its
    settings, so a renamed run reuses its cache."""
    if spec == HEURISTIC:
        return HEURISTIC
    base, sep, rest = spec.partition(".pt@")
    path = loadable(base + ".pt" if sep else spec)
    return f"net-{file_hash(path)}" + ("_" + rest.replace("@", "_") if sep else "")


def run_id(path):
    """The run id of runs/<id>/model.pt, else the path."""
    parts = path.replace("\\", "/").split("/")
    return parts[-2] if len(parts) >= 2 and parts[-1] == "model.pt" else path


class Explorer:
    """The page's data: every method returns what one endpoint sends. No
    database is open at start (`open_db`); players load on first use and
    stay loaded."""

    def __init__(self, puzzle_path=None, cache_dir=CACHE_DIR, log=print, db_dir=DB_DIR, runs=None, product=PRODUCT,
                 results=RESULTS, two_turn=None):
        self.cache_dir, self.log, self.db_dir, self.product = cache_dir, log, db_dir, product
        self.results = results
        self.two_turn = two_turn  # tests: a cheaper two-turn search than the gauntlet's (ladder.TWO_TURN)
        self.files_cache = {}
        self.recorded_cache = {}  # a replay's recorded states, for afterstate matching (`recorded`)
        self.memo_hooks = {}  # a file's settings -> MemoPlayers (owner lines)
        self.runs = runs or registry.runs_dir()
        self.db_path, self.db, self.db_error, self.db_gen = None, None, None, 0
        self.positions_cache = {}
        self.evaluators, self.picks = {}, {}
        self.lock = threading.Lock()
        puzzle_path = puzzle_path or os.path.join(bench_sets.BENCH, "puzzles.json")
        with open(puzzle_path, encoding="utf-8") as f:
            data = json.load(f)
        self.puzzles = [{**r, "half": h} for h, rows in data["halves"].items() for r in rows]
        self.puzzle_rules = data.get("fingerprint")
        self.puzzle_hash = file_hash(puzzle_path)

    # --- database -------------------------------------------------------

    def dbs(self):
        """The databases in `db_dir` (*.sqlite), each with its size and
        whether it holds rows of this rules version (read with mode=ro)."""
        out = []
        if os.path.isdir(self.db_dir):
            for name in sorted(os.listdir(self.db_dir)):
                if not name.endswith(".sqlite"):
                    continue
                path = os.path.join(self.db_dir, name).replace("\\", "/")
                try:
                    check_db(path)
                    why = None
                except ValueError as e:
                    why = str(e)
                out.append({"path": path, "name": name, "bytes": os.path.getsize(path),
                            "current": why is None, "why": why, "open": self.db_path == path})
        return {"dbs": out}

    def open_db(self, path=None, background=True):
        """Opens `path` (or the open one again: a fresh snapshot), closing the
        one open before. A database without rows of this rules version is
        refused (ValueError) and nothing is written. `sts.SolvedDb` reads
        every row's hash first, so on a big file this runs in a thread."""
        path = (path or self.db_path or "").replace("\\", "/")
        if not path:
            raise ValueError("no database picked")
        check_db(path)
        with self.lock:
            self.db_gen += 1
            gen = self.db_gen
            self.db_path, self.db, self.db_error = path, None, None
            self.positions_cache = {}

        def run():
            try:
                db = sts.SolvedDb(path)
                self.log(f"database open: {db.rows} rows of this rules version")
                with self.lock:
                    if gen == self.db_gen:
                        self.db = db
            except Exception as e:  # shown on the page
                with self.lock:
                    if gen == self.db_gen:
                        self.db_error = str(e)
        if background:
            self.log(f"opening {path} (reads every row's hash; minutes on a big file)")
            threading.Thread(target=run, daemon=True).start()
        else:
            run()
        return self.status()

    def close_db(self):
        with self.lock:
            self.db_gen += 1
            self.db_path, self.db, self.db_error = None, None, None
            self.positions_cache = {}
        return self.status()

    def need_db(self):
        if self.db is None:
            raise LookupError(self.db_error or ("the database is still opening" if self.db_path
                                                else "no database open (pick one of this rules version)"))
        return self.db

    def reopen(self):
        if not self.db_path:
            raise LookupError("no database open")
        return self.open_db()

    def status(self):
        db, sources, note = self.db, [], None
        if db is not None:
            con = ro_connect(self.db_path)
            try:
                sources = [s for (s,) in con.execute("SELECT DISTINCT source FROM positions ORDER BY source")]
            finally:
                con.close()
        elif self.db_path:
            note = self.db_error or "the database is still opening"
        else:
            note = "no database open: run positions and row ids need one of this rules version"
        return {"db": self.db_path, "ready": db is not None, "error": self.db_error,
                "rows": db.rows if db is not None else None, "db_note": note,
                "players": list(self.evaluators), "build": build_hash(), "rules": current_fingerprint(),
                "puzzle_rules": self.puzzle_rules,
                "halves": sorted({r["half"] for r in self.puzzles}), "puzzles": len(self.puzzles),
                "horizons": sorted({int(r["horizon"]) for r in self.puzzles}), "sources": sources}

    # --- players --------------------------------------------------------

    def players(self, with_=None):
        """The players a request names (`with=`, comma separated), heuristic
        always first, each loaded once and kept."""
        names = [HEURISTIC]
        for p in (with_ or "").split(","):
            if p.strip() and p.strip() != HEURISTIC:
                full = resolve_player(p, self.runs)
                if full not in names:
                    names.append(full)
        for n in names:
            if n not in self.evaluators:
                self.evaluators[n] = bench.load_evaluator(loadable(n))
        return names

    def nets(self, file=None):
        """Runs with a model.pt, newest first; the product net
        (configs/product.json) and `file`'s players (a result file's
        settings) on top, each with its player string."""
        top = []
        try:
            with open(self.product, encoding="utf-8") as f:
                top.append((json.load(f)["player"], "product"))
        except (OSError, ValueError, KeyError):
            pass
        if file:
            try:
                with open(file, encoding="utf-8") as f:
                    st = json.load(f).get("settings", {})
                for k in ("player", "chooser"):
                    if isinstance(st.get(k), str) and ".pt" in st[k]:
                        top.append((st[k], "file"))
            except (OSError, ValueError):
                pass
        rows = []
        if os.path.isdir(self.runs):
            for d in os.listdir(self.runs):
                path = os.path.join(self.runs, d, "model.pt")
                if os.path.isfile(path):
                    rows.append({"id": d, "player": shown(path), "tag": None,
                                 "mtime": os.path.getmtime(path)})
        rows.sort(key=lambda r: (-r["mtime"], r["id"]))
        head = [{"id": run_id(p.partition("@")[0]), "player": p, "tag": tag, "mtime": None} for p, tag in top]
        return {"nets": head + rows}

    # --- picks ----------------------------------------------------------

    def load_picks(self, name):
        """{"picks", "values"} per puzzle (file order) for player `name`, from
        memory, the cache, else `bench.search_puzzles` over every puzzle,
        then cached."""
        if name in self.picks:
            return self.picks[name]
        ev = self.evaluators[name]
        path = os.path.join(self.cache_dir, f"{evaluator_label(name)}-{self.puzzle_hash}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.picks[name] = json.load(f)
            return self.picks[name]
        p = progress.Progress(f"picks ({name})", len(self.puzzles), self.log)
        picks, values = [], []
        for at in range(0, len(self.puzzles), PICK_CHUNK):
            pk, vs = bench.search_puzzles(ev, self.puzzles[at:at + PICK_CHUNK])
            picks += pk
            values += vs
            p.update(len(pk))
        p.close()
        out = {"picks": picks, "values": values}
        os.makedirs(self.cache_dir, exist_ok=True)
        tmp = f"{path}.tmp{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f)
        os.replace(tmp, path)
        self.picks[name] = out
        return out

    def regrets(self, i, names):
        exact = [o[1] for o in self.puzzles[i]["options"]]
        return {n: max(exact) - exact[self.load_picks(n)["picks"][i]] for n in names}

    # --- lists ----------------------------------------------------------

    def puzzle_list(self, half=None, horizon=None, contested=None, wrong=None, sort=None, ev=None, page=0, desc=None,
                    dull=None, with_=None, by=None):
        """Puzzles matching the filters, PAGE per page, with each player's
        regret (`with_`, heuristic first). `wrong` names a player (added to
        the players if missing): only puzzles where its pick's regret is
        above bench.EXACT. `dull`: "1" only dull puzzles (`learn.dull`: tied,
        or only End turn worse; the curriculum skips them), "0" none of them.
        `sort`: a column (`sort_rows`), "regret:<player>", or "regret" (of
        `ev`, largest first); else file order. `by` groups them (group_page)
        by set ("half") or encounter."""
        if by not in (None, "", "half", "encounter"):
            raise ValueError(f"group by {by!r}: half or encounter")
        extra = [x for x in (with_, wrong, ev) if x]
        if sort and sort.startswith("regret:") and sort != "regret:":
            extra.append(sort.split(":", 1)[1])
        names = self.players(",".join(extra))
        wrong = resolve_player(wrong, self.runs) if wrong else None
        ev = resolve_player(ev, self.runs) if ev else names[0]
        if sort == "regret":
            sort, desc = f"regret:{ev}", "1" if desc is None else desc
        elif sort and sort.startswith("regret:"):
            sort = "regret:" + resolve_player(sort.split(":", 1)[1], self.runs)
        rows = []
        for i, r in enumerate(self.puzzles):
            exact = [o[1] for o in r["options"]]
            if half and r["half"] != half:
                continue
            if horizon not in (None, "") and int(r["horizon"]) != int(horizon):
                continue
            if contested not in (None, "") and (r["gap"] >= bench.PUZZLE_CONTESTED) != (str(contested) == "1"):
                continue
            reg = self.regrets(i, names)
            if wrong and reg[wrong] <= bench.EXACT:
                continue
            is_dull = learn.dull(exact, ["End" in o[0] for o in r["options"]])
            if dull not in (None, "") and is_dull != (str(dull) == "1"):
                continue
            rows.append({"id": i, "half": r["half"], "horizon": int(r["horizon"]), "gap": r["gap"],
                         "tied": max(exact) - min(exact) <= bench.EXACT, "dull": is_dull, "options": len(exact),
                         "encounter": r["encounter"], "hp": r["hp"], "regret": reg})
        return {"players": names, **group_page(rows, by or None, sort, desc, "id", page)}

    def position_list(self, source, page=0, sort=None, desc=None):
        """`source`'s positions, PAGE per page, `sort` as in `sort_rows`."""
        if source not in self.positions_cache:
            self.positions_cache[source] = self.need_db().positions(source)
        rows = [{"n": k, "spec": r["spec"], "step": r["step"], "horizon": r["horizon"], "gap": r["gap"], "state": r["state"]}
                for k, r in enumerate(self.positions_cache[source])]
        rows = sort_rows(rows, sort, desc, "n")
        page = int(page or 0)
        out = [{**{k: v for k, v in r.items() if k != "state"}, "hex": r["state"].hex()}
               for r in rows[page * PAGE:(page + 1) * PAGE]]
        return {"total": len(rows), "page": page, "pages": (len(rows) + PAGE - 1) // PAGE, "rows": out}

    # --- states ---------------------------------------------------------

    def scores(self, c, groups, names):
        """{player: (score per option, picked option)}: its one-turn search,
        as bench.search_puzzles runs it."""
        out = {}
        for name in names:
            ev = self.evaluators[name]
            s = sts.search(c, ev.evaluator, features=ev.features, limit=bench.LIMIT)
            found = {frozenset(enc(a) for a in acts): float(v) for acts, v in s["options"]}
            pick = enc(s["action"])
            out[name] = ([found.get(frozenset(g)) for g in groups], next(i for i, g in enumerate(groups) if pick in g))
        return out

    def view(self, c, values=None, source=None, extra=None, scores=None, value=None, bounded=None, names=None):
        """A state as the page shows it. `values`: exact value per option in
        `c.options(LIMIT)` order, else looked up in the open database;
        `bounded`: which of them are only upper bounds (solver bounds). A
        state not awaiting an action (a stored chance node) shows `value`
        only. `names`: the players whose scores show."""
        names = names or self.players()
        h = hex_of(c)
        out = {"hex": h, "board": c.render(), "board_data": board_of(c), "over": c.is_over(), "players": names,
               **(extra or {})}
        if c.is_over():
            return {**out, "value": c.score(), "source": "terminal", "options": []}
        if not c.awaiting_action():
            return {**out, "value": value, "source": source, "options": []}
        opts = c.options(LIMIT)
        groups = [[enc(a) for a in acts] for acts, _, _ in opts]
        db = self.db
        if values is None and db is not None and h is not None:
            found = db.lookup([bytes.fromhex(h)])[0]
            if found is not None:
                value, values, bounded = found[0], found[1], found[2]
                source = "database"
        if values is not None and value is None:
            value = max(values)
        scores = scores or self.scores(c, groups, names)
        best = max(values) if values is not None else None
        rows = []
        for k, (g, (_, kind, _)) in enumerate(zip(groups, opts)):
            rows.append({"actions": g, "kind": kind, "value": None if values is None else values[k],
                         "regret": None if values is None else best - values[k],
                         "bounded": bool(bounded and bounded[k]),
                         "scores": {n: s[0][k] for n, s in scores.items()},
                         "picked_by": [n for n, s in scores.items() if s[1] == k]})
        return {**out, "value": value, "source": source or ("unsolved" if db is not None else "no database open"),
                "options": rows}

    def puzzle_state(self, i, names):
        r = self.puzzles[int(i)]
        c = bench_decisions.replay(r)
        groups = [[enc(a) for a in acts] for acts, _, _ in c.options(LIMIT)]
        exact = {frozenset(o[0]): o[1] for o in r["options"]}
        if set(exact) != {frozenset(g) for g in groups}:
            raise ValueError(f"puzzle {i}: options group differently from the solver's")
        values = [exact[frozenset(g)] for g in groups]
        row_groups = [frozenset(o[0]) for o in r["options"]]
        order = [row_groups.index(frozenset(g)) for g in groups]
        scores = {}
        for n in names:
            p = self.load_picks(n)
            scores[n] = ([p["values"][int(i)][j] for j in order], order.index(p["picks"][int(i)]))
        extra = {"puzzle": int(i), "half": r["half"], "horizon": int(r["horizon"]), "encounter": r["encounter"],
                 "rules": self.puzzle_rules}
        return self.view(c, values, "puzzle", extra, scores, names=names)

    def row_state(self, row_id, names):
        (code, value, opts), = self.need_db().fetch([int(row_id)])
        c = sts.Combat.decode(code)
        groups = [[enc(a) for a in acts] for acts, _, _ in c.options(LIMIT)] if c.awaiting_action() else []
        if [frozenset(enc(a) for a in o[0]) for o in opts] != [frozenset(g) for g in groups]:
            raise ValueError(f"row {row_id}: options group differently from the solver's")
        con = ro_connect(self.db_path)
        try:
            cost, turns = con.execute("SELECT cost, turns_left FROM states WHERE id = ?", (int(row_id),)).fetchone()
        finally:
            con.close()
        return self.view(c, [o[1] for o in opts] or None, "database",
                         {"row": int(row_id), "cost": cost, "turns_left": turns}, value=value,
                         bounded=[o[2] for o in opts] or None, names=names)

    def state(self, puzzle=None, id=None, hex=None, seed=0, with_=None):
        names = self.players(with_)
        if puzzle not in (None, ""):
            return self.puzzle_state(puzzle, names)
        if id not in (None, ""):
            return self.row_state(id, names)
        return self.view(sts.Combat.decode(bytes.fromhex(hex), int(seed or 0)), names=names)

    def child(self, hex, option, seed=0):
        """(child Combat, probability of the outcome taken, option kind): the
        option played from the state with RNG seed `seed`; a chance option
        takes one of its outcomes at random (seed), a divergent one samples
        its pending events (`advance`)."""
        return self.child_of(sts.Combat.decode(bytes.fromhex(hex)), option, seed)

    def child_of(self, c, option, seed=0):
        """`child` from a Combat in memory (one with generated content has no
        hex): the same state with RNG seed `seed` (as `Combat.decode(hex,
        seed)` gives it), then the option played."""
        seed = int(seed or 0)
        c = c.with_seed(seed)
        _, kind, outs = c.options(LIMIT)[int(option)]
        j = 0 if len(outs) == 1 else int(np.random.default_rng(seed).choice(len(outs), p=np.array([p for p, _ in outs])))
        p, x = outs[j]
        if not x.is_over() and not x.awaiting_action():
            x.advance()
        return x, (None if kind == "divergent" else p), kind

    def recorded(self, out, file=None, fight=None):
        """A replay's recorded states (Amendment 1: afterstates decide the
        line): {"states": the state before each recorded decision, then the
        end state; "index": {state: its first decision n}}. States compare by
        the engine state, the RNG left out (Combat.__eq__), so a state with
        generated content matches without an encoding."""
        decs = out["decisions"]
        key = json.dumps([file, fight, out.get("spec"), [d["action"] for d in decs]], sort_keys=True, default=str)
        hit = self.recorded_cache.get(key)
        if hit is None:
            c = self.line_state(out, 0, [], file, fight)
            states = []
            for d in decs:
                states.append(c.clone())
                c.step({enc(x): x for x in c.legal_actions()}[d["action"]])
            states.append(c)
            index = {}
            for m, s in enumerate(states[:-1]):
                index.setdefault(s, m)
            hit = self.recorded_cache[key] = {"states": states, "index": index}
            if len(self.recorded_cache) > 64:
                self.recorded_cache.pop(next(iter(self.recorded_cache)))
        return hit

    def end_of(self, x, out):
        """A finished fight's {won, hp_end} and whether it equals the replay's
        result (`as_recorded`): the page records a fight's result only when it
        changes the afterstate."""
        won = bool(x.won())
        end = {"won": won, "hp_end": int(x.player_hp()) if won else 0}
        rec = (out or {}).get("replay")
        same = None if rec is None else (bool(rec["won"]), int(rec["hp_end"]) if rec["won"] else 0) == (
            end["won"], end["hp_end"])
        return {**end, "as_recorded": same}

    def step(self, hex, option, seed=0, with_=None, player=None, file=None, i=None, k=None, n=None, choices=None,
             mine=None, fight=None, steps=None):
        """The option played (`child`) and the next state's view. Without
        `player` or `file`, the solve mode's view as before; with them, the
        state view (`state_view`) with the player's scores for the new state,
        `n` being its decision count along the line (a two-turn player's seed).
        On a replayed floor (`file`, `i`, `k`, with the run's `choices`), or a
        mutate or boss-replay cell (`fight`), afterstates decide the line
        (Amendment 1): the recorded option from a recorded state leads to the
        record's own next state (its chance outcomes as they fell); any step
        whose new state equals a recorded decision's state (Combat.__eq__: the
        engine state, RNG left out) is "as played" at that decision, scored
        from the record, with no new search; any other is "your line". `mine`
        is accepted and ignored (the page's old sticky flag). A finished fight
        adds "end" {won, hp_end (0 on a loss), as_recorded (equals the
        replay's result)}. Without `hex`, in a floor's or a cell's context: the
        current state is the line handle (`n`, `steps`: `line_state`), as
        `state_view` names it (states with generated content have no hex); see
        `step_handle`."""
        line_mark, x, out, rejoined = None, None, None, None
        has_fight = fight not in (None, "")
        if hex in (None, "") and (has_fight or file not in (None, "")) and n not in (None, ""):
            return self.step_handle(option, seed, with_, file, i, k, int(n), parse_steps(steps), choices, fight)
        if (has_fight or file not in (None, "")) and n not in (None, ""):
            out = self.fight(fight) if has_fight else self.floor(file, i, k, choices)
            rec = self.recorded(out, None if has_fight else file, fight)
            decs = out["decisions"]
            c = sts.Combat.decode(bytes.fromhex(hex))
            j = rec["index"].get(c)
            opt = c.options(LIMIT)[int(option)]
            if j is not None and decs[j]["action"] in [enc(a) for a in opt[0]]:
                x, p, kind = rec["states"][j + 1].clone(), None, opt[1]
            line_mark = "your line"
        if x is None:
            x, p, kind = self.child(hex, option, seed)
        if out is not None:
            rec = self.recorded(out, None if has_fight else file, fight)
            if x.is_over():
                if x == rec["states"][-1]:
                    line_mark = "as played"
            else:
                rejoined = rec["index"].get(x)
                if rejoined is not None:
                    line_mark, n = "as played", rejoined
        extra = {"from": hex, "option": int(option), "seed": int(seed or 0), "kind": kind, "prob": p}
        if line_mark:
            extra["line"] = line_mark
        if line_mark == "as played":  # the recorded decision the line is on again (its count at the end)
            extra["at"] = len(out["decisions"]) if x.is_over() else rejoined
        if x.is_over():
            extra["end"] = self.end_of(x, out)
            if out is None:
                extra["end"].pop("as_recorded")
        if player in (None, "") and file in (None, "") and not has_fight:
            return {**self.view(x, extra=extra, names=self.players(with_)), **extra}
        if x.is_over() or not x.awaiting_action():
            v = self.view(x, extra=extra, names=self.players(with_))
            return {**v, "board_data": board_of(x), **extra}
        h = out["decisions"][rejoined]["hex"] if rejoined is not None else None
        return {**self.state_view(h or x.encode().hex(), player, with_, None if has_fight else file, i, k, n,
                                  choices=choices, fight=fight), **extra}

    def step_handle(self, option, seed, with_, file, i, k, n, steps, choices, fight):
        """`step` from the state the handle (`n`, `steps`) names: the recorded
        option at a recorded state leads to the record's next state; a new
        state equal to recorded decision m's is "as played" on handle (m, []),
        scored from the record; anything else is "your line" on handle (n,
        steps + [[option, seed]]). The result carries the new handle."""
        has_fight = fight not in (None, "")
        out = self.fight(fight) if has_fight else self.floor(file, i, k, choices)
        decs = out["decisions"]
        rec = self.recorded(out, None if has_fight else file, fight)
        cur = self.line_state(out, n, steps, file, fight)
        opt = cur.options(LIMIT)[int(option)]
        kind = opt[1]
        j = n if not steps else rec["index"].get(cur)
        if j is not None and j < len(decs) and decs[j]["action"] in [enc(a) for a in opt[0]]:
            x, p = rec["states"][j + 1].clone(), None
        else:
            x, p, kind = self.child_of(cur, option, seed)
        m = None if x.is_over() else rec["index"].get(x)
        if m is not None:
            handle, line_mark = {"n": m, "steps": []}, "as played"
        elif x.is_over() and x == rec["states"][-1]:
            handle, line_mark = {"n": len(decs), "steps": []}, "as played"
        else:
            handle, line_mark = {"n": n, "steps": steps + [[int(option), int(seed or 0)]]}, "your line"
        extra = {"from": None, "option": int(option), "seed": int(seed or 0), "kind": kind, "prob": p,
                 "line": line_mark, "handle": handle}
        if line_mark == "as played":  # the recorded decision the line is on again (its count at the end)
            extra["at"] = handle["n"]
        if x.is_over():
            extra["end"] = self.end_of(x, out)
        if x.is_over() or not x.awaiting_action():
            v = self.view(x, extra=extra, names=self.players(with_))
            return {**v, "board_data": board_of(x), **extra}
        return {**self.state_view(None, None, with_, None if has_fight else file, i, k, handle["n"], choices=choices,
                                  fight=fight, steps=json.dumps(handle["steps"])), **extra}

    def solve(self, hex, with_=None):
        """The state solved now (memory-only store, SOLVE_NODES), or marked
        unsolved when the budget runs out."""
        names = self.players(with_)
        c = sts.Combat.decode(bytes.fromhex(hex))
        if c.is_over():
            return self.view(c, names=names)
        r = sts.solve(c, max_nodes=SOLVE_NODES, store=sts.SolveStore(min_nodes=puzzles.MIN_NODES))
        if r is None:
            return {**self.view(c, names=names), "source": "unsolved (over the node budget)"}
        found = {frozenset(enc(a) for a in o[0]): o[1] for o in r["options"]}
        values = [found[frozenset(enc(a) for a in acts)] for acts, _, _ in c.options(LIMIT)]
        return self.view(c, values, "solved now", {"nodes": r["nodes"]}, names=names)

    # --- gauntlet files (docs/specs/explorer-v2.md) ------------------------

    def gauntlet_dir(self):
        return os.path.join(self.results, "gauntlet")

    def result_path(self, file, kind="gauntlet"):
        """A result file named by the page (its name, or a path under the
        kind's folder); anything outside that folder is refused."""
        folder = os.path.abspath(os.path.join(self.results, kind))
        path = os.path.abspath(os.path.join(folder, os.path.basename(file.replace("\\", "/"))))
        if not os.path.isfile(path):
            raise ValueError(f"no result file {file!r} in {shown(folder)}")
        return path

    def load_result(self, path):
        """A result file's JSON, read again only when its size or mtime moves."""
        st = os.stat(path)
        key = (st.st_size, st.st_mtime_ns)
        hit = self.files_cache.get(path)
        if hit is None or hit[0] != key:
            with open(path, encoding="utf-8") as f:
                hit = (key, json.load(f))
            self.files_cache[path] = hit
        return hit[1]

    def files(self, kind="gauntlet", q=None):
        """The kind's result files grouped by player: per file its setting
        tags, sequences played, clear rate, protocol verdict and why its
        replays are refused (None when they play)."""
        if kind in ("mutate", "boss_replay"):
            return self.test_files(kind, q)
        if kind != "gauntlet":
            raise ValueError(f"no file kind {kind!r} (gauntlet, mutate, boss_replay)")
        groups = {}
        folder = self.gauntlet_dir()
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            if not name.endswith(".json"):
                continue
            path = os.path.join(folder, name)
            try:
                d = self.load_result(path)
                st, rows = d["settings"], d["sequences"]
            except (OSError, ValueError, KeyError, TypeError):
                continue
            tags = setting_tags(st)
            if q and not all(w.lower() in " ".join([name, st.get("player", ""), *tags]).lower() for w in q.split()):
                continue
            n = len(rows)
            groups.setdefault(st.get("player", "?"), []).append({
                "file": name, "tags": tags, "n": n, "mtime": os.path.getmtime(path),
                "clears": sum(bool(r.get("cleared")) for r in rows) / n if n else None,
                "protocol": (d.get("protocol") or {}).get("verdict"), "refused": self.refused(st)})
        out = [{"player": p, "files": sorted(fs, key=lambda f: -f["mtime"])} for p, fs in groups.items()]
        out.sort(key=lambda g: -max(f["mtime"] for f in g["files"]))
        return {"groups": out}

    def refused(self, st):
        """Why a file's fights can't be replayed here, or None: another seed,
        shape or rest share than today's gauntlet.py, or a player net, a
        chooser net or a pack file that is gone."""
        if st.get("seed") != gauntlet.GAUNTLET_SEED or st.get("shape") != list(gauntlet.SHAPE):
            return "played on other sequences than today's gauntlet.py (seed or shape differs)"
        if st.get("rest", gauntlet.REST) != gauntlet.REST:
            return f"rest heals {st.get('rest')} of max HP; today's gauntlet.py heals {gauntlet.REST}"
        for k in ("player", "chooser"):
            p = st.get(k)
            if isinstance(p, str) and p != HEURISTIC:
                for f in ladder_files(p):
                    if not os.path.isfile(loadable(f)):
                        return f"the {k}'s net {f} is gone"
        if st.get("pack") and not os.path.isfile(loadable(st["pack"].rpartition("@")[0])):
            return f"the pack {st['pack'].rpartition('@')[0]} is gone"
        return None

    def sequence_rows(self, file):
        """(settings, {i: row}) of a gauntlet file."""
        d = self.load_result(self.result_path(file))
        return d["settings"], {int(r["i"]): r for r in d["sequences"]}

    def sequences(self, file, half=None, cleared=None, died=None, encounter=None, card=None, sort=None, desc=None,
                  page=0, by=None):
        """A gauntlet file's sequences, PAGE per page: per sequence its half,
        cell, boss, cleared or the floor it died on, end HP (the boss fight's
        HP left when cleared, else 0, as the gauntlet scores it), the final
        deck and the strip of floors (encounter, kind, HP in and out, won,
        card taken, rest, removal, path). Filters: half, cleared ("1"/"0"),
        died (a floor index), encounter (fought on any floor), card (in the
        final deck). `by` groups them (group_page) by half, boss or result
        ("cleared", "died on floor k")."""
        if by not in (None, "", "half", "boss", "result"):
            raise ValueError(f"group by {by!r}: half, boss or result")
        st, rows = self.sequence_rows(file)
        out = []
        for i, r in sorted(rows.items()):
            seq = sequence(st, i)
            fl = r["floors"]
            dead = next((k for k, f in enumerate(fl) if not f["won"]), None)
            deck = walk(st, seq, r)["deck"]
            row = {"i": i, "half": r.get("half", seq["half"]), "cell": r.get("cell", seq["cell"]),
                   "boss": seq["fights"][-1]["encounter"], "cleared": bool(r.get("cleared")), "died": dead,
                   "floors": len(fl), "end_hp": int(fl[-1]["hp_end"]) if r.get("cleared") else 0,
                   "deck": sorted(deck), "strip": [strip_cell(k, f) for k, f in enumerate(fl)]}
            if half and row["half"] != half:
                continue
            if cleared not in (None, "") and row["cleared"] != (str(cleared) == "1"):
                continue
            if died not in (None, "") and dead != int(died):
                continue
            if encounter and all(f["encounter"] != encounter for f in fl):
                continue
            if card and card not in deck:
                continue
            row["result"] = "cleared" if row["cleared"] else f"died on floor {dead + 1}"
            out.append(row)
        order = None
        if by == "result":  # cleared first, then deaths by floor
            order = ["cleared"] + [f"died on floor {k}" for k in range(1, 12)]
        grouped = group_page(out, by or None, sort, desc, "i", page, order=order)
        return {"file": os.path.basename(file), "settings": st, "tags": setting_tags(st), "refused": self.refused(st),
                **grouped}

    def run(self, file, i, choices=None):
        """One sequence's run: its floors in order, each with the fight's
        start (deck, HP), its row and its events (offers, extra offers, rest,
        removal, as the row recorded them; scores come from /api/event), and
        the replay's fidelity when the floor was replayed already (cached)."""
        st, rows = self.sequence_rows(file)
        i = int(i)
        seq, row = sequence(st, i), rows[i]
        head = {"file": os.path.basename(file), "i": i, "half": seq["half"], "cell": seq["cell"],
                "character": seq["character"], "start_deck": list(seq["deck"]), "cleared": bool(row.get("cleared")),
                "tags": setting_tags(st), "refused": self.refused(st), "match": st.get("match"), "choices": choices or None}
        if choices not in (None, "", "[]"):
            return {**head, **self.owner_run(st, i, seq, row, choices)}
        w = walk(st, seq, row)
        floors = []
        for k, (f, spec) in enumerate(zip(row["floors"], w["fights"])):
            cached = self.cached_floor(st, i, k, spec)
            floors.append({"k": k, "kind": gauntlet.SHAPE[k], "line": "file", "row": f,
                           "start": {"deck": sorted(spec["deck"]), "hp": spec["hp"], "encounter": spec["encounter"]},
                           "result": {"won": bool(f["won"]), "hp_end": int(f["hp_end"]) if f["won"] else 0},
                           "events": ([{"e": None, "kind": "path", "j": None, "offer": ["elite", "hallway"],
                                        "options": ["elite", "hallway"], "recorded": f["path"],
                                        "chosen": f["path"], "by": "row"}] if "path" in f else []) +
                                     [{"e": n, "kind": e["kind"], "j": e.get("j"), "offer": e.get("offer"),
                                       "options": event_options(e["kind"], e.get("offer"), e["item"][2]),
                                       "recorded": e["recorded"], "chosen": e["recorded"], "by": "row"}
                                      for n, e in enumerate(w["events"]) if e["k"] == k],
                           "fidelity": fidelity(cached, f) if cached else None})
        return {**head, "floors": floors, "pending": None}

    def memo_players(self, st):
        key = json.dumps(st, sort_keys=True)
        if key not in self.memo_hooks:
            self.memo_hooks[key] = MemoPlayers(gauntlet_players(st))
        return self.memo_hooks[key]

    def owner_line(self, st, i, seq, row, choices, outcome, until=None):
        why = self.refused(st)
        if why:
            raise ValueError(f"can't take over this file: {why}")
        return line(st, seq, row, choices, outcome, self.memo_players(st), until=until)

    def owner_run(self, st, i, seq, row, choices):
        """/api/run with the owner's choices: the line (`line`) with every
        owner-line fight from the replay cache (one opened with /api/floor),
        stopping at the first not played yet (`pending`)."""
        def outcome(k, spec):
            hit = self.cached_floor(st, i, k, spec)
            return hit["replay"] if hit else None
        w = self.owner_line(st, i, seq, row, choices, outcome)
        floors = []
        for fl in w["floors"]:
            k, spec = fl["k"], fl["spec"]
            on = fl["line"] == "file"
            cached = self.cached_floor(st, i, k, spec) if on and k < len(row["floors"]) else None
            floors.append({"k": k, "kind": gauntlet.SHAPE[k], "line": fl["line"],
                           "row": row["floors"][k] if on else None,
                           "start": {"deck": sorted(spec["deck"]), "hp": spec["hp"], "encounter": spec["encounter"]},
                           "result": fl["result"],
                           "source": fl["source"], "events": [{"e": None, **e} for e in fl["events"]],
                           "fidelity": fidelity(cached, row["floors"][k]) if cached else None})
        return {"floors": floors, "pending": w["pending"], "deck": sorted(w["deck"]), "history": w["history"]}

    def event(self, file, i, e):
        """Run event `e` of sequence i (its index in /api/run's events) with
        the file's own chooser's options, scores and pick (event_scores), and
        whether that pick and the offer equal the row's."""
        st, rows = self.sequence_rows(file)
        why = self.refused(st)
        if why:
            raise ValueError(f"can't score this file's choices: {why}")
        i = int(i)
        ev = walk(st, sequence(st, i), rows[i])["events"][int(e)]
        got = event_scores(st, ev)
        want = None if ev["recorded"] == "heal" else ev["recorded"]
        out = {"e": int(e), "k": ev["k"], "kind": ev["kind"], "recorded": ev["recorded"], "scored": got}
        if got is not None:
            out["pick_matches"] = got["pick"] == want
            if "offer" in ev:
                out["offer_matches"] = got.get("offer") == ev["offer"]
        if st.get("match"):
            out["note"] = f"the row's choices were copied from {st['match']}, not made by this chooser"
        return out

    def floor(self, file, i, k, choices=None):
        """Floor k of sequence i replayed by the file's own player (one turn
        deep: bench.run_specs with record and values, as ladder.play_bench
        plays; two turns deep: depth_paired.guarded_fight with record and
        scores, as ladder.play_two_turn plays): the fight's start, every
        decision (state as hex, turn, the action played, the player's scores
        per option and its pick) and the fidelity check against the row.
        Cached under cache/explore/replays/."""
        st, rows = self.sequence_rows(file)
        why = self.refused(st)
        if why:
            raise ValueError(f"can't replay this file: {why}")
        i, k = int(i), int(k)
        seq, row = sequence(st, i), rows[i]
        on_file = True
        if choices not in (None, "", "[]"):
            w = self.owner_line(st, i, seq, row, choices, lambda kk, sp: self.played(st, i, kk, sp)[0]["replay"],
                                until=k)
            last = w["floors"][-1]
            if last["k"] != k:
                raise ValueError(f"this line ends at floor {last['k']} ({'lost' if last['result'] else 'pending'})")
            spec, on_file = last["spec"], last["line"] == "file"
        else:
            fights = walk(st, seq, row)["fights"]
            if k >= len(fights):
                raise ValueError(f"sequence {i} played {len(fights)} floors")
            spec = fights[k]
        out, cached = self.played(st, i, k, spec)
        decisions = [{**d, "board_data": describe_board(d["board_data"])} for d in out["decisions"]]
        return {**out, "decisions": decisions, "line": "file" if on_file else "owner", "cached": cached,
                "fidelity": fidelity(out, row["floors"][k]) if on_file else None}

    def played(self, st, i, k, spec):
        """(floor k's replay from `spec`, from the cache or played now and
        cached; True when it came from the cache)."""
        out = self.cached_floor(st, i, k, spec)
        if out is not None:
            return out, True
        out = self.replay_floor(st, i, k, spec)
        path = self.floor_cache_path(st, i, k, spec)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp{os.getpid()}.{threading.get_ident()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f)
        os.replace(tmp, path)
        return out, False

    def floor_key(self, st, i, k, spec):
        two = st.get("two_turn", False) and k >= st.get("one_turn_floors", 0)
        return {"v": REPLAY_VERSION, "settings": st, "i": i, "k": k, "spec": spec, "build": build_hash(),
                "two": (self.two_turn or two_turn_search()) if two else None}

    def floor_cache_path(self, st, i, k, spec):
        key = json.dumps(self.floor_key(st, i, k, spec), sort_keys=True)
        return os.path.join(self.cache_dir, "replays", hashlib.sha256(key.encode()).hexdigest()[:24] + ".json")

    def cached_floor(self, st, i, k, spec):
        path = self.floor_cache_path(st, i, k, spec)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def load_pack(self, st):
        """A gauntlet file's pack loaded into this process (as play loads it):
        {path, file (its hash in the settings), now (today's)}, or None."""
        if not st.get("pack"):
            return None
        import selfplay
        path, _, h = st["pack"].rpartition("@")
        _, now = selfplay.load_content(loadable(path))
        return {"path": path, "file": h, "now": now}

    def floor_start(self, st, spec):
        """A floor's fight at its start, in memory with its own RNG (its pack loaded)."""
        self.load_pack(st)
        return sts.Combat(spec["deck"], spec["encounter"], seed=spec["seed"], hp=spec["hp"], character=spec["character"])

    def fight_start(self, fight):
        """A mutate or boss-replay cell's fight at its first decision, in memory
        with its own RNG, rebuilt as `fight` rebuilds it."""
        f = json.loads(fight) if isinstance(fight, str) else dict(fight)
        d = self.load_result(self.result_path(f["file"], f["kind"]))
        if f["kind"] == "boss_replay":
            return self.floor_start({}, boss_cell(d, f)["spec"])
        c = mutate_cell(d, f, self.fights_of)["combat"]
        while not c.is_over() and not c.awaiting_action():
            c.advance()
        return c

    def line_state(self, out, n, steps, file=None, fight=None):
        """The state a line handle names: the replay `out` (a floor's or a
        cell's) stepped from its start through its first `n` recorded actions
        (the record's own chance outcomes, from the fight's RNG), then each of
        `steps` ([option, seed]) as `child_of` plays it. States with generated
        content have no hex, so the page names them this way."""
        c = self.fight_start(fight) if fight not in (None, "") else self.floor_start(self.sequence_rows(file)[0],
                                                                                      out["spec"])
        for d in out["decisions"][:n]:
            c.step({enc(x): x for x in c.legal_actions()}[d["action"]])
        for option, seed in steps:
            c = self.child_of(c, option, seed)[0]
        return c

    def replay_floor(self, st, i, k, spec):
        player = st["player"]
        pack = self.load_pack(st)
        key = self.floor_key(st, i, k, spec)
        if key["two"] is not None:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis"))
            import depth_paired
            r = depth_paired.guarded_fight((spec, key["two"], -1.0, loadable(player), 0, 3,
                                            st.get("line_seed", False), st.get("step_line", False), True, True))
            actions, scored = r["actions"], r["scores"]
        else:
            ev = None if player == HEURISTIC else self.evaluator(player)
            r = bench.run_specs([spec], ev=ev, record=True,
                                search={"limit": bench.LIMIT, "threads": 1, "values": True})[0]
            actions = [enc(a) for a in r["actions"]]
            scored = []
            for a, opts in zip(actions, r["values"]):
                groups = [[enc(x) for x in acts] for acts, _ in opts]
                scored.append({"options": groups, "one": [float(v) for _, v in opts], "two": None,
                               "pick": next(n for n, g in enumerate(groups) if a in g)})
        c = self.floor_start(st, spec)
        decisions = []
        legal = {}
        for n, (a, sc) in enumerate(zip(actions, scored)):
            legal = {enc(x): x for x in c.legal_actions()}
            decisions.append({"n": n, "turn": c.turn(), "hex": hex_of(c), "action": a, "scores": sc,
                              "board_data": c.board()})
            c.step(legal[a])
        won = bool(r["won"])
        replay = {"won": won, "hp_end": int(r["hp_end"]) if won else 0}
        steps_end = {"won": bool(c.is_over() and c.won()), "hp_end": int(c.player_hp()) if c.is_over() and c.won() else 0}
        if steps_end != replay:
            raise RuntimeError(f"floor {k}: stepping the recorded actions ends {steps_end}, the player's run {replay}")
        return {"file_settings_tags": setting_tags(st), "i": i, "k": k, "spec": spec,
                "depth": 2 if key["two"] is not None else 1, "decisions": decisions, "end": hex_of(c),
                "pack": pack, "replay": replay}

    def evaluator(self, name):
        """A player's evaluator, loaded once (shared with the comparison players)."""
        if name not in self.evaluators:
            self.evaluators[name] = bench.load_evaluator(loadable(name))
        return self.evaluators[name]

    # --- the state view: the net's view and the player's scores -----------

    def static_ev(self, name):
        """The evaluator whose `static` gives a net player's own value of a
        state: the net file without search-time settings (`@...` prices the
        search's leaves, not the net)."""
        return self.evaluator(name.partition(".pt@")[0] + ".pt" if ".pt@" in name else name)

    def net_view(self, c, player):
        """What `player` gets for state `c`: for a net, its input rows as its
        own features encode them (stsnet.features_for: the net's layout), named
        by column, and its static value; for the heuristic, its named parts."""
        if player in (None, HEURISTIC):
            est, loss, rounds = c.heuristic_parts()
            return {"kind": "heuristic", "parts": [["estimated score", float(est)], ["HP loss from here", float(loss)],
                                                    ["rounds left", float(rounds)]]}
        f = self.evaluator(player).features
        b = f.encode([c])
        piles = list(f.piles)
        out = {"kind": "net", "columns": {"player": list(f.player_names), "monster": list(f.monster_names),
                                          "card": list(f.card_names), "row": list(f.row_names)},
               "player": b["player"][0].tolist(),
               "monsters": [{"slot": s, "values": b["monsters"][0][s].tolist()} for s in range(b["monsters"].shape[1])
                            if b["monsters"][0][s].any()],
               "cards": [{"pile": piles[int(b["card_pile"][j])], "count": float(b["card_count"][j]),
                          "values": b["cards"][j].tolist()} for j in range(b["cards"].shape[0])],
               "rows": [{"card": int(b["row_card"][r]), "entity": int(b["row_entity"][r]),
                         "values": b["rows"][r].tolist()} for r in range(b["rows"].shape[0])]}
        st = self.static_ev(player).static
        if st is not None:
            out["static"] = float(np.asarray(st(f.encode([c], heuristic=True)), np.float64)[0])
        return out

    def player_scores(self, c, player, groups, two=None, seed=None, recorded=None, search=None):
        """The player's own scores at `c`, aligned with `groups` (the view's
        options): from the replay's record (`recorded`, a decision's scores) or
        computed now, one turn deep (sts.search as the gauntlet plays) or, with
        `two` (search settings) and the decision's `seed`, by
        depth_paired.decide (the guarded policy the two-turn player plays).
        {source, one, two (per option, None where unknown), pick (an index into
        groups, or None)}; a later action of a stepped principal line has no
        search of its own (`line`)."""
        if recorded is not None and recorded.get("line"):
            return {"source": "record", "line": True, "one": None, "two": None, "pick": None}
        if recorded is not None:
            sopts, one, twov, pick = recorded["options"], recorded["one"], recorded.get("two"), recorded["pick"]
            source = "record"
        elif search is not None:  # a mutate fight's search agent (sts.play_on's), `seed` its search seed
            sopts, one, twov, pick = search_scores(c, self.evaluator(player) if player != HEURISTIC else None,
                                                   search, seed)
            source = "now"
        elif two is not None:
            d = depth_paired().decide(c, self.evaluator(player), two, None, seed, 0, 3, -1.0)
            sopts = [[enc(a) for a in acts] for acts, _ in d["r1"]["options"]]
            one, twov, pick, source = [float(v) for v in d["v1"]], d["v2"] and [float(v) for v in d["v2"]], d["pick"], "now"
        else:
            ev = self.evaluator(player) if player != HEURISTIC else None
            s = sts.search(c, ev.evaluator if ev else "heuristic", features=ev.features if ev else None,
                           limit=bench.LIMIT)
            sopts = [[enc(a) for a in acts] for acts, _ in s["options"]]
            one, twov, source = [float(v) for _, v in s["options"]], None, "now"
            a = enc(s["action"])
            pick = next(n for n, g in enumerate(sopts) if a in g)
        at = [align(g, sopts) for g in groups]
        return {"source": source, "one": [None if j is None else one[j] for j in at],
                "two": None if twov is None else [None if j is None else twov[j] for j in at],
                "pick": at.index(pick) if pick in at else None}

    def state_view(self, hex=None, player=None, with_=None, file=None, i=None, k=None, n=None, fresh=None, seed=0,
                   choices=None, fight=None, steps=None):
        """Any state as the state view shows it: the solve-mode view (options,
        comparison scores from `with_`, exact values only from an open current
        database) plus the board as data (Combat.board: the draw pile as
        sorted contents, never an order), what the player's net gets
        (`net_view`) and the player's own scores (`player_scores`). With
        `file`, `i`, `k`: the player, its depth and the fight's seed are that
        floor's; with `n` and no `hex` (or the same state's hex), decision n of
        the replay, scored from its record (`fresh` recomputes them now).
        With `fight` (a mutate or boss-replay cell, `Explorer.fight`) in place
        of `file`: the same for that cell's replay. Without `hex` in either
        context, the state is the line handle (`n`, `steps`: decision n of the
        replay, then the steps after it; `line_state`), the only name a state
        with generated content has; the result carries it as "handle"."""
        names = self.players(with_)
        by_handle = hex in (None, "")
        two, fseed, recorded, played, turn_seed = None, None, None, None, False
        fsearch, out = None, None
        steps = parse_steps(steps)
        count = int(n or 0) + len(steps)  # decisions along the line before this state
        if fight not in (None, ""):
            out = self.fight(fight)
            player = out["player"]
            if out["search"] is not None:  # a mutate cell: sts.play_on's search agent
                fsearch = (out["search"], agent_seed(out["agent"], count))
            if n not in (None, "") and not steps and int(n) < len(out["decisions"]):
                dec = out["decisions"][int(n)]
                if hex in (None, "", dec["hex"]):
                    hex, played = dec["hex"], dec["action"]
                    if not fresh or fresh == "0":
                        recorded = dec["scores"]
        elif file not in (None, ""):
            st, _ = self.sequence_rows(file)
            out = self.floor(file, i, k, choices)
            player = st["player"]
            spec = out["spec"]
            fseed, turn_seed = spec["seed"], st.get("line_seed", False)
            if out["depth"] == 2:
                two = self.two_turn or two_turn_search()
            if n not in (None, "") and not steps and int(n) < len(out["decisions"]):
                dec = out["decisions"][int(n)]
                if hex in (None, "", dec["hex"]):
                    hex, played = dec["hex"], dec["action"]
                    if not fresh or fresh == "0":
                        recorded = dec["scores"]
        if hex in (None, "") and out is not None and n not in (None, ""):
            c = self.line_state(out, int(n), steps, file, fight)
        else:
            c = sts.Combat.decode(bytes.fromhex(hex), int(seed or 0))
        v = self.view(c, names=names)
        if out is not None and n not in (None, "") and by_handle:
            v["handle"] = {"n": int(n), "steps": steps}
        v["board_data"] = board_of(c)
        player = resolve_player(player, self.runs) if player not in (None, "") else HEURISTIC
        v["net"] = self.net_view(c, player)
        depth = 2 if two is not None or (fsearch is not None and fsearch[0].get("turns", 1) == 2) else 1
        if v["options"]:
            groups = [o["actions"] for o in v["options"]]
            dseed = None
            if two is not None:
                dseed = depth_paired().decision_seed(fseed, c.turn(), count, turn_seed)
            elif fsearch is not None:
                dseed = fsearch[1]
            ps = self.player_scores(c, player, groups, two, dseed, recorded,
                                    search=fsearch[0] if fsearch is not None else None)
            ps["recorded"] = next((j for j, g in enumerate(groups) if played in g), None) if played else None
            v["player"] = {"name": player, "depth": depth, **ps}
        else:
            v["player"] = {"name": player, "depth": depth}
        return v

    # --- mutate and boss-replay files (docs/specs/explorer-v2.md) ----------

    def test_dir(self, kind):
        return os.path.join(self.results, kind)

    def test_files(self, kind, q=None):
        """The mutate or boss-replay files: per file its kind, the gauntlet
        file it was read from, its players and modifiers (mutate) or HP levels
        (boss replay), rows and seeds, and why its fights can't be replayed
        (None when they can)."""
        folder = self.test_dir(kind)
        out = []
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            if not name.endswith(".json"):
                continue
            path = os.path.join(folder, name)
            try:
                d = self.load_result(path)
                st, rows = d["settings"], d["rows"]
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if kind == "mutate":
                sub = mutate_kind(d)
                players = sorted({p for r in rows for p in r.get("parent", {})})
                info = {"kind": sub, "source": st.get("product"), "mods": st.get("mods", []), "players": players,
                        "seeds": st.get("seeds")}
            else:
                info = {"kind": "boss_replay", "source": st.get("file"), "player": st.get("player"),
                        "hp": st.get("hp"), "seeds": st.get("seeds")}
            if q and not all(w.lower() in json.dumps([name, info]).lower() for w in q.split()):
                continue
            out.append({"file": name, "n": len(rows), "mtime": os.path.getmtime(path), **info,
                        "refused": self.test_refused(kind, d)})
        out.sort(key=lambda f: -f["mtime"])
        return {"files": out}

    def test_refused(self, kind, d):
        """Why a mutate or boss-replay file's fights can't be replayed here."""
        st = d["settings"]
        src = st.get("product") if kind == "mutate" else st.get("file")
        if not src or not os.path.isfile(repo_path(src)):
            return f"the gauntlet file it was read from ({src}) is gone"
        nets = test_players(d).values() if kind == "mutate" else [st.get("player")]
        for p in nets:
            if isinstance(p, str) and p != HEURISTIC and not os.path.isfile(loadable(ladder_files(p)[0])):
                return f"the net {ladder_files(p)[0]} is gone"
        return None

    def mutate(self, file, mod=None, player=None, etype=None, encounter=None, sort=None, desc=None, page=0,
               by="parent"):
        """A mutate file as rows, never one column per modifier (Amendment 3):
        one row per (start, column), where a start is a sequence's floor
        (encounter, encounter type, entry HP, and the card for mutated cards)
        and a column the parent, the official card (mutated cards) or a
        modifier. Each row: per player its wins, mean end HP (0 on a loss)
        and per-seed [won, hp_end], the file's own numbers. `by`: "parent"
        (a group per start, its columns in order) or "modifier" (a group per
        column, parent first, a row per start) or "none" (Amendment 6: every
        row, ungrouped, by start then column). Filters: a modifier (its
        starts; their parent and official rows stay), encounter type,
        encounter, player; sort inside groups by i, floor, encounter,
        encounter_type, hp, column or "wins:<player>" / "hp:<player>"."""
        if by not in ("parent", "modifier", "none"):
            raise ValueError(f"group by {by!r}: parent, modifier or none")
        d = self.load_result(self.result_path(file, "mutate"))
        sub = mutate_kind(d)
        columns = (["official", "parent"] if sub == "cards" else ["parent"]) + list(d["settings"].get("mods", []))
        rows = []
        for r in d["rows"]:
            if etype and r["group"] != etype or encounter and r["encounter"] != encounter:
                continue
            if mod and mod not in r.get("mods", {}):
                continue
            start = {"i": r["i"], "floor": r["floor"], "encounter": r["encounter"], "encounter_type": r["group"],
                     "hp": r["hp"], **({"card": r["card"]} if "card" in r else {})}
            for col in columns:
                if mod and col not in ("official", "parent", mod):
                    continue
                res_by = r.get(col) if col in ("official", "parent") else r.get("mods", {}).get(col)
                if res_by is None:
                    continue
                cells = {p: {"wins": float(np.mean([bool(w) for w, _ in res])) if res else None,
                             "hp": float(np.mean([h if w else 0 for w, h in res])) if res else None,
                             "seeds": [[bool(w), int(h)] for w, h in res]}
                         for p, res in res_by.items() if not player or p == player}
                rows.append({**start, "column": col, "col_rank": columns.index(col), "cells": cells})
        tie = "col_rank" if by == "parent" else "i"
        if sort and sort.split(":")[0] in ("wins", "hp") and ":" in sort:
            what, p = sort.split(":", 1)
            for row in rows:
                row["_sort"] = (row["cells"].get(p) or {}).get(what)
            sort = "_sort"
        start_key = lambda r: (r["i"], r["floor"], r.get("card"))  # noqa: E731
        if by == "parent":
            start_sort = sort if sort in ("i", "floor", "encounter", "encounter_type", "hp", "card") else None
            starts = list(dict.fromkeys(start_key(r) for r in sort_rows(rows, start_sort, desc, "i")))
            names = {start_key(r): r for r in rows}
            out = group_page(rows, by, sort or "col_rank", desc if sort else None, tie, page, key=start_key,
                             order=starts,
                             label=lambda k: f"seq {k[0]} · floor {k[1] + 1} · {names[k]['encounter']}"
                                             + (f" · {k[2]}" if k[2] else "")
                                             + f" · {names[k]['encounter_type']} · {names[k]['hp']} HP")
        elif by == "modifier":
            out = group_page(rows, by, sort, desc, tie, page, key=lambda r: r["column"], order=columns)
        else:  # rows come by start, then column: a stable sort keeps that order among ties
            out = group_page(rows, None, sort, desc, "i", page)
        for row in out["rows"]:
            row.pop("_sort", None)
            row.pop("col_rank", None)
        return {"kind": sub, "columns": columns, "settings": d["settings"], **out}

    def boss_replay(self, file, boss=None, half=None, sort=None, desc=None, page=0, by="sequence"):
        """A boss-replay file's rows: sequence, half, boss, deck, the arrival
        HP and outcome the gauntlet file observed. `by` "sequence" (PAGE
        per page): one row per sequence with the win grid by entry HP
        ("arrival": the row's own arrival HP) and seed, with the end HP per
        seed where the file holds it. `by` "hp" (Amendment 3): a group per
        entry HP level in the file's order, one row per sequence with that
        level's per-seed wins (`won`, `hp_end`), `wins` its share won, and
        `deck_size`. Filters: boss, half; sort by any column."""
        if by not in ("sequence", "hp"):
            raise ValueError(f"group by {by!r}: sequence or hp")
        d = self.load_result(self.result_path(file, "boss_replay"))
        rows = []
        for r in d["rows"]:
            if boss and r["boss"] != boss or half and r["half"] != half:
                continue
            row = {k: r[k] for k in ("i", "half", "boss", "deck", "hp_obs", "won_obs")}
            row["deck_size"] = len(r["deck"])
            if by == "hp":
                for lv, ws in r["won"].items():
                    rows.append({**row, "level": lv, "won": ws, "hp_end": r.get("hp_end") if lv == "arrival" else None,
                                 "wins": float(np.mean(ws)) if ws else None})
                continue
            row["won"] = r["won"]
            if "hp_end" in r:
                row["hp_end"] = r["hp_end"]
            row["wins"] = float(np.mean([w for ws in r["won"].values() for w in ws])) if r["won"] else None
            rows.append(row)
        head = {"settings": d["settings"], "skipped": d.get("skipped")}
        if by == "sequence":
            out = group_page(rows, None, sort, desc, "i", page)
            return {**head, **out, "by": "sequence"}
        levels = list(dict.fromkeys(lv for r in d["rows"] for lv in r["won"]))
        out = group_page(rows, "hp", sort, desc, "i", page, key=lambda r: r["level"], order=levels,
                         label=lambda lv: "at arrival HP" if lv == "arrival" else f"HP {lv}")
        return {**head, **out}

    def fight(self, fight):
        """One mutate or boss-replay cell as a replayed fight, `fight` a JSON
        object (or its text): {"kind": "mutate", "file", "i", "floor", "card"
        (mutated cards), "mod" ("parent", "official" or a modifier), "player",
        "seed" (the seed's index)} or {"kind": "boss_replay", "file", "i",
        "hp" (an HP level, or "arrival"), "seed"}. Rebuilt with the scripts'
        own functions and played by the script's own player: a mutate cell by
        sts.search per decision exactly as sts.play_on's search agent plays it
        (its search seeds rebuilt where the play-out's seed gives them), a
        boss-replay cell as the gauntlet's one-turn floor (bench.run_specs
        with record). Returns the decisions as /api/floor does, the player,
        the search settings and the fidelity check against the file's win and
        end HP for that seed. Cached under cache/explore/replays/."""
        f = json.loads(fight) if isinstance(fight, str) else dict(fight)
        kind = f.get("kind")
        if kind not in ("mutate", "boss_replay"):
            raise ValueError(f"no fight kind {kind!r} (mutate, boss_replay)")
        d = self.load_result(self.result_path(f["file"], kind))
        why = self.test_refused(kind, d)
        if why:
            raise ValueError(f"can't replay this file: {why}")
        if kind == "mutate":
            cell = mutate_cell(d, f, self.fights_of)
        else:
            cell = boss_cell(d, f)
        key = {"v": REPLAY_VERSION, "fight": cell["key"], "build": build_hash()}
        path = os.path.join(self.cache_dir, "replays",
                            hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:24] + ".json")
        out, cached = None, False
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    out, cached = json.load(fh), True
            except (OSError, ValueError):
                out = None
        if out is None:
            if cell["search"] is None:  # a boss replay: the gauntlet's one-turn floor
                out = self.replay_floor({"player": cell["player"]}, int(f["i"]), BOSS_FLOOR, cell["spec"])
            else:
                out = play_cell(cell, None if cell["player"] == HEURISTIC else self.evaluator(cell["player"]))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = f"{path}.tmp{os.getpid()}.{threading.get_ident()}"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(out, fh)
            os.replace(tmp, path)
        decisions = [{**d, "board_data": describe_board(d["board_data"])} for d in out["decisions"]]
        want = cell["file"]
        same = all(out["replay"][key] == want[key] for key in cell["compare"])
        cause = None
        if not same:
            gen, was = cell["key"].get("gen_pack"), d["settings"].get("gen_pack")
            cause = (f"the generated-enemy pack changed since the run (file {was}, today {gen})"
                     if gen and was and gen != was else "this build plays the fight differently")
        return {**out, "decisions": decisions, "fight": f, "player": cell["player"], "search": cell["search"],
                "agent": cell.get("agent"), "cached": cached, "line": "file",
                "fidelity": {"matches": same, "file": want, "replay": {key: out["replay"][key] for key in cell["compare"]},
                             "cause": cause}}

    def fights_of(self, product):
        """bias_audit.fights of a gauntlet file (every elite and boss start),
        computed once per file."""
        path = repo_path(product)
        st = os.stat(path)
        key = (path, st.st_size, st.st_mtime_ns)
        hit = self.files_cache.get(("fights",) + key)
        if hit is None:
            with open(path, encoding="utf-8") as fh:
                hit = analysis("bias_audit").fights(json.load(fh), 10 ** 9)
            self.files_cache[("fights",) + key] = hit
        return hit

    # --- content browser ------------------------------------------------

    def content(self, kind, source=None, q=None, file=None, by=None, sort=None, desc=None):
        """Every entry of `kind` (cards, monsters, powers, encounters or relics) the
        build can load, from every source (`content_sources`), each with its
        file's own numbers (`data`), source label and the kind's own table
        columns (`cols`, CONTENT_COLUMNS; Amendment 3); `source` and `q` (a
        substring of the id, any case) filter, `sort` (a column) and `desc`
        ("1") order the rows (missing values last, file order on ties).
        With `file` (a gauntlet file) a card lists the sequences whose final
        deck held it (`decks`) and those that took it (`took`), a monster or
        an encounter the floors that fought it (`floors`). `by` groups the
        entries (group_page) by one of CONTENT_GROUPS[kind]."""
        if kind not in CONTENT_KINDS:
            raise ValueError(f"no content kind {kind!r} (one of {', '.join(CONTENT_KINDS)})")
        entries = []
        for s, d in content_sources():
            # A card with an upgrade block lists its upgrade after it.
            for e in (x for e0 in d.get(kind, []) for x in (e0, kind == "cards" and
                      upgraded_card(e0, s == "official", d.get("version", 2))) if x):
                ds = describe(kind, e["id"], s)
                cols, sortv = content_cols(kind, e, s, ds)
                entries.append({"id": e["id"], "source": s, "kind": kind, "data": e, "desc": ds, "cols": cols,
                                "_sort": sortv})
        if source:
            entries = [e for e in entries if e["source"] == source]
        if q:
            entries = [e for e in entries if q.lower() in e["id"].lower()]
        if sort:
            if sort not in dict(CONTENT_COLUMNS[kind]):
                raise ValueError(f"no {kind} column {sort!r} (one of {', '.join(k for k, _ in CONTENT_COLUMNS[kind])})")
            have = [e for e in entries if e["_sort"][sort] is not None]
            entries = sorted(have, key=lambda e: e["_sort"][sort], reverse=str(desc) == "1") + \
                [e for e in entries if e["_sort"][sort] is None]
        for e in entries:
            del e["_sort"]
        if file and kind not in ("powers", "relics"):
            links = self.content_links(file)
            for e in entries:
                name = e["id"] if e["source"] == "official" else "gen:" + e["id"]
                if kind == "cards":
                    e["decks"], e["took"] = links["decks"].get(name, []), links["took"].get(name, [])
                elif kind == "monsters":
                    e["floors"] = links["floors"].get(e["id"], [])
                else:
                    e["floors"] = links["encounters"].get(e["id"], [])
        groups = []
        if by:
            if by not in CONTENT_GROUPS.get(kind, ()):
                raise ValueError(f"group {kind} by {by!r}: one of {', '.join(CONTENT_GROUPS.get(kind, ()))}")
            key = lambda e: e["cols"][by] if by in e["cols"] else e["data"].get(by)  # noqa: E731
            order = sorted({key(e) for e in entries}, key=cost_rank) if by == "cost" else                 sorted({key(e) for e in entries}, key=lambda r: RARITY_ORDER.index(r) if r in RARITY_ORDER else len(RARITY_ORDER))                 if by == "rarity" else None
            g = group_page(entries, by, None, None, "id", 0, size=len(entries) + 1, key=key, order=order)
            entries, groups = g["rows"], g["groups"]
        return {"kind": kind, "sources": [s for s, _ in content_sources()], "total": len(entries), "entries": entries,
                "columns": [{"key": k, "label": lab} for k, lab in CONTENT_COLUMNS[kind]],
                "by": by or None, "groups": groups}

    def content_links(self, file):
        """{decks, took, floors} of a gauntlet file, computed once per file
        version: card name -> sequences (final deck; took it on a floor or an
        extra offer), monster name -> [{i, k, encounter}] (the monsters each
        floor's fight starts with, from its own seed)."""
        path = self.result_path(file)
        st_ = os.stat(path)
        key = ("links", path, st_.st_size, st_.st_mtime_ns)
        hit = self.files_cache.get(key)
        if hit is None:
            st, rows = self.sequence_rows(file)
            decks, took, floors, encounters = {}, {}, {}, {}
            for i, r in sorted(rows.items()):
                seq = sequence(st, i)
                for c in set(walk(st, seq, r)["deck"]):
                    decks.setdefault(c, []).append(i)
                for k, fl in enumerate(r["floors"]):
                    for t in [fl.get("took")] + [x.get("took") for x in fl.get("extra", [])]:
                        if t and i not in took.setdefault(t, []):
                            took[t].append(i)
                    encounters.setdefault(fl["encounter"], []).append({"i": i, "k": k, "encounter": fl["encounter"]})
                    for m in floor_monsters(fl["encounter"], seq["fights"][k]["seed"], seq["character"]):
                        floors.setdefault(m, []).append({"i": i, "k": k, "encounter": fl["encounter"]})
            hit = {"decks": decks, "took": took, "floors": floors, "encounters": encounters}
            self.files_cache[key] = hit
        return hit


CONTENT_KINDS = ("cards", "monsters", "powers", "encounters", "relics")
# each kind's own table (Amendment 3): (column key, header), every column sortable
CONTENT_COLUMNS = {
    "cards": [("name", "name"), ("cost", "cost"), ("type", "type"), ("class", "class"), ("keywords", "keywords"),
              ("source", "source"), ("text", "text")],
    "monsters": [("name", "name"), ("hp", "HP"), ("moves", "moves"), ("start_powers", "start powers"),
                 ("source", "source")],
    "powers": [("name", "name"), ("debuff", "buff or debuff"), ("source", "source"), ("text", "text")],
    "encounters": [("name", "name"), ("type", "type"), ("monsters", "monsters"), ("source", "source")],
    "relics": [("name", "name"), ("rarity", "rarity"), ("powers", "start powers"), ("fights", "fights"),
               ("source", "source"), ("text", "text")],
}
# the columns each content kind can be grouped by (an entry's column, else its content data's)
CONTENT_GROUPS = {"cards": ("source", "type", "class", "cost"), "monsters": ("source",),
                  "powers": ("source", "debuff"), "encounters": ("source", "type"),
                  "relics": ("source", "rarity")}
CARD_KEYWORDS = ("exhaust", "ethereal", "retain", "innate")


def _slot_text(m):
    """One encounter slot as text: a monster, or "A or B" for a slot that
    rolls one of several (each option one or more monsters)."""
    if isinstance(m, str):
        return m.removeprefix("gen:")
    if "draw" in m:
        return _draw_text(m, lambda n: n.removeprefix("gen:"))
    return " or ".join(" + ".join(_slot_text(x) for x in o) for o in m.get("one_of", []))


def card_cost(e):
    """A card entry's cost: a number, "X" or "Unplayable". Content files say
    X and Unplayable as cost -1 and -2 (the engine's sentinels); older files
    say them with the `x_cost` / `unplayable` flags."""
    cost = int(e.get("cost", 0))
    if e.get("unplayable") or cost == -2:
        return "Unplayable"
    if e.get("x_cost") or cost == -1:
        return "X"
    return cost


def cost_rank(cost):
    """A card cost's sort key: numbers in order, then X, then Unplayable."""
    return (2, 0) if cost == "Unplayable" else (1, 0) if cost == "X" else (0, cost)


def content_cols(kind, e, source, d):
    """(cols, sort values) of one content entry for its kind's table
    (CONTENT_COLUMNS): what the cell shows, and the value it sorts by
    (None sorts last). A card's cost shows a number, "X" or "Unplayable"
    and sorts numbers first, then X, then Unplayable."""
    # lines joined as sentences: one without a full stop (a power's static) gets one
    text = " ".join(ln if ln[-1:] in ".:!?" else ln + "." for ln in (d["lines"] if d else []) if ln and ln != DIVIDER).strip()
    if kind == "cards":
        cost = card_cost(e)
        ck = cost_rank(cost)
        kws = [k.capitalize() for k in CARD_KEYWORDS if e.get(k)]
        cols = {"name": e["id"], "cost": cost, "type": e.get("type"), "class": e.get("class"), "keywords": kws,
                "source": source, "text": text}
        sortv = {**cols, "cost": ck, "keywords": " ".join(kws) or None}
    elif kind == "monsters":
        hp = e.get("hp")
        lo, hi = (hp[0], hp[1]) if isinstance(hp, list) else (hp, hp)
        moves = list(dict.fromkeys(mv["name"] for mv in e.get("moves", [])))
        powers = [f"{p['power']} {p['amount']}" for p in e.get("start_powers", [])]
        cols = {"name": e["id"], "hp": None if lo is None else (f"{lo}" if lo == hi else f"{lo}–{hi}"),
                "moves": moves, "start_powers": powers, "source": source}
        sortv = {**cols, "hp": lo, "moves": len(moves) or None, "start_powers": " ".join(powers) or None}
    elif kind == "powers":
        cols = {"name": e["id"], "debuff": "debuff" if e.get("debuff") else "buff", "source": source, "text": text}
        sortv = dict(cols)
    elif kind == "relics":
        powers = [f"{human(p['power'])} {p['amount']}" for p in e.get("powers", [])]
        fights = e.get("fights", list(WORDING["fight_kind"]))
        cols = {"name": e["id"], "rarity": e.get("rarity"), "powers": powers, "fights": fights, "source": source, "text": text}
        sortv = {**cols, "rarity": RARITY_ORDER.index(e["rarity"]) if e.get("rarity") in RARITY_ORDER else None,
                 "powers": " ".join(powers) or None, "fights": len(fights)}
    else:
        mons = [_slot_text(m) for m in e.get("monsters", [])]
        cols = {"name": e["id"], "type": e.get("group"), "monsters": mons, "source": source}
        sortv = {**cols, "monsters": ", ".join(mons) or None}
    sortv = {k: (v.lower() if isinstance(v, str) else v) for k, v in sortv.items()}
    if "text" in sortv:
        sortv["text"] = sortv["text"] or None
    return cols, sortv
_SOURCES = []


def content_sources():
    """[(label, content JSON)]: official (content/*.json), each pack in
    content/packs/ ("pack:<name>"), the mutated-card pack and the
    generated-enemy pack, as their scripts build them. Read once."""
    if not _SOURCES:
        off = {}
        for kind in CONTENT_KINDS:
            with open(os.path.join(REPO, "content", f"{kind}.json"), encoding="utf-8") as f:
                off[kind] = json.load(f)[kind]
        # Official potions are described (board tooltips), not listed as a content kind.
        with open(os.path.join(REPO, "content", "potions.json"), encoding="utf-8") as f:
            off["potions"] = json.load(f).get("potions", [])
        out = [("official", off)]
        for p in sorted(glob.glob(os.path.join(REPO, "content", "packs", "*.json"))):
            with open(p, encoding="utf-8") as f:
                out.append(("pack:" + os.path.splitext(os.path.basename(p))[0], json.load(f)))
        out.append(("mutated-cards", analysis("mutate_cards").pack()))
        out.append(("generated-enemies", json.loads(analysis("mutate_monsters").gen_pack())))
        _SOURCES.extend(out)
    return _SOURCES


# --- plain-words descriptions (docs/specs/explorer-v2.md, Amendment 1) -------
# Tooltips say what their label doesn't: each description is {head, lines},
# generated from the content data (content_sources, content/encounters.json and
# the packs' encounters), so it stays right when content changes. Every
# element's words come from content/wording.json (docs/specs/element-wording.md);
# code here only fills the templates, plus the few phrasings that depend on an
# element's values.

WORDING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "content", "wording.json")
with open(WORDING_FILE, encoding="utf-8") as _f:
    WORDING = json.load(_f)
# Monsters whose move choice is partly held in engine code (their `code`), and
# powers whose behaviour is (no hooks, statics or replacements in their data).
CODE_MONSTERS = WORDING["code_monster"]
CODE_POWERS = WORDING["code_power"]
# (family, name) pairs a description had no wording for; test_explore_wording
# asserts it stays empty.
UNWORDED = set()
USER_SLOTS = {  # what fills {subject} {s} {per} for each user of an effect
    "card": {"subject": "", "s": "", "per": ""},
    "monster": {"subject": "", "s": "", "per": ""},
    "power": {"subject": "its owner ", "s": "s", "per": " per stack"},
}


def word(family, name, default=None):
    """An element's wording, recording a miss (UNWORDED) and giving `default`
    (the bare name) in its place."""
    w = WORDING.get(family, {}).get(name)
    if w is None:
        UNWORDED.add((family, str(name)))
        return str(name) if default is None else default
    return w


def fill(template, fields, move=None):
    """`template` with {name} from `fields` ({0}, {1}: a bare value, or a
    list value's items); {x|word} is "N word(s)", {x|move} the move named by
    index x (`move` turns an index into its name)."""
    import re

    def one(m):
        key, flt = m.group(1), m.group(2)
        v = fields.get(key, "")
        if flt == "move":
            return move(v)
        if flt:
            return _plural(v, flt)
        return str(v)
    return re.sub(r"\{(\w+)(?:\|(\w+))?\}", one, template)


def human(name):
    """A power id in prose: "SharpHide" -> "Sharp Hide" (ids with spaces or
    dashes stay as they are)."""
    import re
    return name if (" " in name or "-" in name) else re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)


def _cards(n, card, self_name=None):
    """A count of a card, always as copies: "1 copy of Shiv", "2 copies of
    Shiv"; a card adding itself names "this card"."""
    name = "this card" if self_name is not None and card == self_name else card
    return f"{n} cop{'y' if n == 1 else 'ies'} of {name}"


def _plural(n, w):
    if abs(n) == 1:
        return f"{n} {w}"
    return f"{n} {w[:-1]}ies" if w.endswith("y") and w[-2:-1] not in "aeiou" else f"{n} {w}s"


def _quantity(of):
    """What an Amount counts, in words (the `quantity` family)."""
    if isinstance(of, dict):
        (key, v), = of.items()
        if key in ("CardsTagged", "CardsOfType"):
            return fill(word("quantity", key), {"0": v})
        if key == "HandCards":
            ex = (v or {}).get("except")
            return fill(word("quantity", key), {"except": f" that isn't an {ex}" if ex else ""})
        return word("quantity", key)
    return word("quantity", of)


def _amount(a):
    """An Amount ({base, k, of}) or a plain number as words."""
    if not isinstance(a, dict):
        return str(a)
    base, k, of = a.get("base", 0), a.get("k", 0), a.get("of")
    if of is None:
        return str(base)
    q = _quantity(of)
    if isinstance(of, dict):  # a count of cards: "2 per card tagged Strike ..."
        return f"{k} per {q}" if not base else f"{base}, plus {k} per {q}"
    if isinstance(k, str):  # a fraction "a/b": "1/5 of your max HP"
        term = f"{k} of {q}"
    else:
        term = q if k == 1 else f"{k} × {q}"
    return term if not base else f"{base} + {term}"


def _hits(a):
    """A hit count (number or Amount) as words after "deal N damage"."""
    if not isinstance(a, dict) or a.get("of") is None:
        n = a if not isinstance(a, dict) else a.get("base", 1)
        return "" if n == 1 else f" {n} times"
    of = a["of"]
    plain = a.get("k", 1) == 1 and not a.get("base")
    if of == "EnergySpent" and plain:
        return " X times"
    if isinstance(of, dict) and "HandCards" in of and plain:
        ex = (of["HandCards"] or {}).get("except")
        return " once for each card in your hand" + (f" that isn't an {ex}" if ex else "")
    return f" {_amount(a)} times"


def _condition(c, family="condition"):
    """A hook's condition (`family` "static_condition" for a static's); a
    list of two is both (fight-vocabulary spec)."""
    if isinstance(c, list):
        return " and ".join(x for x in (_condition(x, family) for x in c) if x)
    key, v = (c, None) if isinstance(c, str) else next(iter(c.items()))
    w = word(family, key, default=f"{key} {v}" if v is not None else key)
    if key == "CardType":  # the article follows the type: "an Attack"
        return f"if it is a{'n' if str(v)[0] in 'AEIOU' else ''} {v}"
    if key == "HandAll" and str(v)[:1] in "AEIOU":  # "an Attack"
        w = w.replace("a {0}", "an {0}")
    if isinstance(v, dict):  # Holds: worded by its side
        return fill(w.get(v.get("side"), key) if isinstance(w, dict) else w, v)
    return fill(w, {"0": v})


def effect_text(e, user, split=None, self_name=None):
    """One effect in plain words, for a `user` ("card", "monster" or "power":
    who uses it, which sets who its targets are and the {subject} {s} {per}
    slots). `self_name` is the card whose text this is (a card adding itself)."""
    key, v = (e, None) if isinstance(e, str) else next(iter(e.items()))
    w = word("effect", key, default=f"{key}: {v}" if v is not None else key)
    f = dict(USER_SLOTS[user])
    if isinstance(v, dict):
        f.update(v)
    elif v is not None:
        f["0"] = v
    t = v.get("target") if isinstance(v, dict) else None
    if t is not None:
        tw = word("target", t)
        f["target"] = tw[user] if isinstance(tw, dict) else tw
        f["to"] = "" if (user == "card" and t == "Opponent") or (user == "monster" and f["target"] == "you") \
            else f" to {f['target']}"
    if "hits" in f:
        f["hits"] = _hits(f["hits"])
    if "power" in f:
        f["power"] = human(f["power"])
    if key in ("BlockOf", "HealOf", "LoseHpOf"):
        f["0"] = _amount(v)
    if key == "CapHp":  # the cap: "1", "3/4 of its max HP", "1 + 3/4 of its max HP"
        n, d, a = v.get("num", 0), v.get("den", 1), v.get("amount", 0)
        part = f"{n}/{d} of its max HP" if n and n != d else ("its max HP" if n else "")
        f["cap"] = " + ".join(x for x in (str(a) if a or not part else "", part) if x)
    # phrasings that depend on the values (docs/specs/element-wording.md)
    if key == "Split" and split:
        return "split into " + " and ".join(split["into"]) + ", each with its current HP"
    if key == "PlainDamage" and user == "card" and t == "Me":
        return f"take {v['amount']} damage"
    if key == "ScaledDamage":
        a = v["amount"]
        to = "" if user == "card" and t == "Opponent" else f" to {f['target']}"
        if isinstance(a, dict) and isinstance(a.get("of"), dict):  # Perfected Strike: base, plus k per card
            per = _amount({**a, "base": 0}).split(" per ", 1)[1]
            return f"deal {a.get('base') or 0} damage{to}{f['hits']}, plus {a.get('k', 1)} per {per}"
        if isinstance(a, dict) and not a.get("base") and a.get("k") == 1:
            return f"deal damage equal to {_amount(a)}{to}" + f["hits"]
        f["to"], f["amount"] = to, _amount(a)
    if key == "ScaledBlock":
        tm = v["times"]
        if (isinstance(tm, dict) and isinstance(tm.get("of"), dict) and "HandCards" in tm["of"]
                and tm.get("k") == 1 and not tm.get("base")):
            ex = (tm["of"]["HandCards"] or {}).get("except")
            return f"gain {v['amount']} Block for each card in your hand" + (f" that isn't an {ex}" if ex else "")
        f["times"] = _amount(tm)
    if key in ("Apply", "ApplyOf", "ApplyAsMonster"):
        n = _amount(v["amount"]) if key == "ApplyOf" else v["amount"]
        p, per = f["power"], f["per"]
        if t == "Me":
            subj = f["subject"]
            if key == "ApplyOf":
                return f"{subj}gain{'s' if subj else ''} {p} equal to {n}{per}".strip()
            if isinstance(n, int) and n < 0:
                return f"{subj}lose{'s' if subj else ''} {-n} {p}{per}".strip()
            return f"{subj}gain{'s' if subj else ''} {n} {p}{per}".strip()
        if isinstance(n, int) and n < 0:
            return f"{f['target']} lose{'' if f['target'] == 'you' else 's'} {-n} {p}{per}"
        f["amount"] = n
        if user == "monster":  # a monster's Apply names you, unlike its Damage
            f["to"] = f" to {f['target']}"
    if key == "RandomizeCost":  # docs/specs/sparse-piles.md
        f["0"] = word("cost_roll", v)
    if key == "AddCard":
        f["cards"] = _cards(v["n"], v["card"], self_name)
        f["pile"] = word("pile", v["pile"])
    if key == "AddCopy":  # a copy of the card it is on (Necronomicurse)
        f["cards"] = _cards(v.get("n", 1), self_name, self_name)
        f["pile"] = word("pile", v["pile"])
    if key == "ExhaustHand":
        ex = (v or {}).get("except")
        f["except"] = " except Attacks" if ex == "Attack" else (f" except {ex}s" if ex else "")
    if key == "PlayTop":
        f["exhaust"] = (" and exhaust it" if v.get("n", 1) == 1 else " and exhaust them") if v.get("exhaust") else ""
    if key == "ObtainRandomPotions":  # docs/specs/act1-singles.md section 5
        ex = (v or {}).get("except") or []
        f["except"] = (", never " + " or ".join(ex)) if ex else ""
    if key == "Discover":  # docs/specs/discovery.md
        f["type"] = f"{v['type']} " if v.get("type") else ""
        f["offer"], f["copies"] = v.get("offer", 3), v.get("copies", 1)
        f["skip"] = ", or skip," if v.get("skip") else ""
        f["free"] = "; it costs 0 this turn" if v.get("free") else ""
        if f["offer"] == 1:  # Infernal Blade: no choice
            return fill("add {copies|copy} of a random {type}card from the {pool} pool to your hand{free}", f)
    if key == "MakeRandom":  # docs/specs/colorless-cards.md step 3
        n = v["n"]
        f["n"] = _amount(n)
        f["type"] = f"{v['type']} " if v.get("type") else ""
        one = not isinstance(n, dict) and n == 1
        f["cards"] = "card" if one else "cards"
        f["pile"] = word("pile", v["pile"])
        f["spot"] = ", never on top" if v["pile"] == "Draw" else ""
        it = "it costs" if one else "they cost"
        f["zero_cost"] = f"; {it} 0 for the rest of combat" if v.get("zero_cost") else ""
        f["free"] = f"; {it} 0 this turn" if v.get("free") else ""
        f["upgraded"] = ", upgraded if this card is" if v.get("match_level") else ""
    if key == "Pick":
        s = fill(word("pick", v["kind"]), {"n": v.get("n", 1), "copies": v.get("copies", 1)})
        if v.get("of"):  # a type filter (Dual Wield)
            s += fill(word("pick_rule", "of"), {"of": " or ".join(v["of"])})
        if v.get("free_this_turn"):
            s += word("pick_rule", "free_this_turn")
        return s if v.get("exact", True) else "up to " + s
    return fill(w, f)


def _hook_line(h, user="power"):
    """A hook in words; a relic's (`user` "card": no stacks, "you") reads as
    the player acting."""
    t = h["trigger"]
    if isinstance(t, dict):
        (key, v), = t.items()
        forms = word("trigger", key, default={})
        param = v.get("by") if key == "CardPlayed" else v.get("from")
        head = forms.get(param) if isinstance(forms, dict) else None
        if head is None:
            UNWORDED.add(("trigger", f"{key}.{param}"))
            head = f"{key} {v}"
    else:
        head = word("trigger", t)
    cond = _condition(h.get("condition", "Always"))
    if cond.startswith("if it is a"):
        head = head.replace("plays a card", "plays a" + cond[len("if it is a"):])
        cond = ""
    effects = [effect_text(e, user) for e in h.get("effects", [])]
    effects = [("then " + t if t == "the power ends" and j else t) for j, t in enumerate(effects)]
    line = f"{head}{(' ' + cond) if cond else ''}: " + ", ".join(effects) + "."
    if user != "card":
        return line
    for a, b in (("its owner's", "your"), ("its owner is", "you are"), ("its owner draws", "you draw"), ("its owner dies", "you die"),
                 ("its owner plays", "you play"), ("its owner loses", "you lose"), ("its owner", "you")):
        line = line.replace(a, b)
    return line


def _static_line(s):
    what = word("modifies", s["modifies"]).capitalize()
    cond = _condition(s.get("condition", "Always"), "static_condition")
    if s["stage"] == "Add":
        fields = {"what": what, "amount": f"{'+' if s['amount'] >= 0 else ''}{s['amount']}"}
    else:
        fields = {"what": what, "factor": f"{s['num'] / s['den']:g}"}
    line = fill(word("stage", s["stage"]), fields)
    return line + (f" {cond}" if cond else "") + "."


def _replacement_line(r):
    ev = word("replacement_event", r["event"])
    if r.get("power"):  # a filter (fight-vocabulary spec): "a debuff ..., if it is Weak"
        ev = f"{ev}, if it is {r['power']}"
    act = r["action"]
    key, v = (act, None) if isinstance(act, str) else next(iter(act.items()))
    fields = {"event": ev, "0": v, **(v if isinstance(v, dict) else {})}
    line = fill(word("replacement_action", key, default=f"Changes {ev}: {act}"), fields)
    if "upTo" in r:  # a range (after-block spec): Torii's "5 or less"
        line += ", " + fill(word("replacement_rule", "upTo"), {"0": r["upTo"]})
    then = [effect_text(e, "power") for e in r.get("then", [])]
    return line + (", then " + ", ".join(then) if then else "") + "."


def _rule_lines(p):
    """A power's rules on its owner's cards (forbids, sets_cost,
    exhausts_played; docs/specs/card-rules.md), worded from `power_rule`."""
    lines = []
    if "forbids" in p:
        lines.append(fill(word("power_rule", "forbids"), {"0": p["forbids"]}))
    if "sets_cost" in p:
        lines.append(fill(word("power_rule", "sets_cost"), p["sets_cost"]))
    if "exhausts_played" in p:
        lines.append(fill(word("power_rule", "exhausts_played"), {"0": p["exhausts_played"]}))
    if "plays_unplayable" in p:
        lines.append(fill(word("power_rule", "plays_unplayable"), {"0": p["plays_unplayable"]}))
    return [line[:1].upper() + line[1:] for line in lines]


def _field_lines(p):
    """A power's fields on how applying it works and how its owner attacks
    (debuff_if_negative, can_go_negative, skips_first_round, attack_shape,
    block_loss, cap), worded from
    `power_field`."""
    lines = []
    if p.get("debuff_if_negative"):
        lines.append(word("power_field", "debuff_if_negative"))
    if p.get("can_go_negative"):
        lines.append(word("power_field", "can_go_negative"))
    for k, on in p.get("skips_first_round", {}).items():
        if on:
            lines.append(word("power_field", "skips_first_round")[k])
    if "attack_shape" in p:
        lines.append(fill(word("power_field", "attack_shape"), {"0": p["attack_shape"]["split"]}))
    if "block_loss" in p:  # docs/specs/blocked-relics.md step 1
        lines.append(fill(word("power_field", "block_loss"), {"0": p["block_loss"]}))
    if "cap" in p:  # the game's caps (Strength 999, Poison 9999)
        lines.append(fill(word("power_field", "cap"), {"0": p["cap"]}))
    return [line[:1].upper() + line[1:] + "." for line in lines]


def describe_power(p):
    lines = [_static_line(s) for s in p.get("statics", [])] + [_hook_line(h) for h in p.get("hooks", [])] + \
            [_replacement_line(r) for r in p.get("replacements", [])] + _rule_lines(p) + _field_lines(p)
    if not lines and p["id"] in CODE_POWERS:
        lines = [CODE_POWERS[p["id"]]]
    if not lines:
        lines = ["No effect of its own in the content data; the engine reads it elsewhere."]
    return {"head": f"{human(p['id'])} · {'Debuff' if p.get('debuff') else 'Buff'}", "lines": lines}


RARITY_ORDER = ("starter", "common", "uncommon", "rare", "boss", "shop", "event")


def describe_relic(r, powers):
    """A relic in plain words (docs/specs/relics.md): head "Name · Rarity
    relic", then its hooks (docs/specs/relic-entity.md) and starting counter,
    each starting power with what that power does (`powers`: power name ->
    its description), the fights it acts in when not all, and its
    combat-end heal."""
    lines = [_hook_line(h, "card") for h in r.get("hooks", [])]
    if r.get("counter"):
        lines.append(fill(word("relic_rule", "counter"), {"0": r["counter"]}))
    for p in r.get("powers", []):
        lines.append(word("relic_rule", "start_power").format(amount=p["amount"], power=human(p["power"])))
        d = powers.get(p["power"])
        if d and d["lines"] and not d["lines"][0].startswith("No effect of its own"):
            lines += [f"{human(p['power'])}: {ln}" for ln in d["lines"]]
    fights = r.get("fights")
    if fights and set(fights) != set(WORDING["fight_kind"]):
        kinds = " and ".join(word("fight_kind", k) for k in fights)
        lines.append(word("relic_rule", "fights").format(kinds=kinds))
    if r.get("win_heal"):
        lines.append(word("relic_rule", "win_heal").format(amount=r["win_heal"]))
    if r.get("potion_potency", 1) != 1:
        lines.append(fill(word("relic_rule", "potion_potency"), {"0": r["potion_potency"]}))
    if r.get("potion_slots"):
        lines.append(fill(word("relic_rule", "potion_slots"), {"0": r["potion_slots"]}))
    if r.get("draw_per_turn"):  # docs/specs/sparse-piles.md
        lines.append(fill(word("relic_rule", "draw_per_turn"), {"0": r["draw_per_turn"]}))
    # docs/specs/blocked-relics.md step 1
    for k in ("x_bonus", "plays_per_turn"):
        if r.get(k):
            lines.append(fill(word("relic_rule", k), {"0": r[k]}))
    for k in ("keeps_energy", "keeps_hand"):
        if r.get(k):
            lines.append(word("relic_rule", k))
    if r.get("heal_scale", [1, 1]) != [1, 1]:  # docs/specs/blocked-relics.md step 4
        lines.append(fill(word("relic_rule", "heal_scale"), {"0": r["heal_scale"][0], "1": r["heal_scale"][1]}))
    if r.get("exhaust_save"):  # docs/specs/blocked-relics.md step 7
        lines.append(fill(word("relic_rule", "exhaust_save"), {"0": r["exhaust_save"][0], "1": r["exhaust_save"][1]}))
    return {"head": f"{r['id']} · {word('relic_rarity', r.get('rarity'))}", "lines": lines or ["No effect in a fight."]}


def describe_potion(q):
    """A potion in plain words (docs/specs/potions.md): head "Name · Rarity
    potion", then its effects and rows as a card's are worded, the fights
    it can be drunk in when not all, then its potency (what Sacred Bark
    doubles) when it has one."""
    lines = describe_card({**q, "type": "Potion", "cost": 0})["lines"]
    if lines == ["No effect when played."]:
        lines = ["No effect when used."]
    if q.get("trigger"):
        lines.insert(0, word("potion_rule", "trigger"))
    fights = q.get("fights")
    if fights and set(fights) != set(WORDING["fight_kind"]):
        kinds = " and ".join(word("fight_kind", k) for k in fights)
        lines.append(word("potion_rule", "fights").format(kinds=kinds))
    if q.get("potency"):
        lines.append(fill(word("potion_rule", "potency"), {"0": q["potency"]}))
    return {"head": f"{q['id']} · {word('potion_rarity', q.get('rarity'))}", "lines": lines}


def _source_powers(d):
    """power name -> description for a source's own powers, over the
    official ones."""
    out = dict(describe_index()["powers"])
    out.update({p["id"]: describe_power(p) for p in d.get("powers", [])})
    return out


def describe_card(c):
    """A card in the game's words: head "Name · N Cost · [Rarity · Class ·] Type"
    (X Cost; Unplayable in place of the cost), then its text with keywords as
    keywords (Innate, Ethereal first; Retain, Exhaust last)."""
    cost = card_cost(c)
    cost = cost if cost == "Unplayable" else f"{cost} Cost"
    parts = [c["id"], cost]
    if c.get("rarity"):
        parts.append(str(c["rarity"]))
    if c.get("class") and c["class"] != "Colorless" and c.get("type") not in ("Status", "Curse"):
        parts.append(c["class"])
    parts.append(c.get("type", "Card"))
    lines = [w for k, w in (("innate", "Innate."), ("ethereal", "Ethereal.")) if c.get(k)]
    # Its play condition (a version-1 file says only_attacks_in_hand).
    cond = c.get("playable_if") or ({"HandAll": "Attack"} if c.get("only_attacks_in_hand") else None)
    if cond:
        w = fill(word("card_rule", "playable_if"), {"0": _condition(cond)})
        lines.append(w[0].upper() + w[1:] + ".")
    for e in c.get("effects", []):
        t = effect_text(e, "card", self_name=c["id"])
        lines.append(t[0].upper() + t[1:] + ".")
    for r in c.get("rows", []):
        t = ", ".join(effect_text(e, "card", self_name=c["id"]) for e in r.get("effects", []))
        cond = _condition(r.get("condition", "Always"))
        lines.append(f"{cond[0].upper() + cond[1:]}, {t}." if cond else t[0].upper() + t[1:] + ".")
    for e in c.get("turn_end", []):
        lines.append(f"At the end of your turn, {effect_text(e, 'card', self_name=c['id'])}.")
    # While held (docs/specs/blocked-relics.md step 6: Pain, Normality).
    for e in c.get("other_played", []):
        lines.append(f"While this is in your hand, whenever you play another card, {effect_text(e, 'card', self_name=c['id'])}.")
    if c.get("plays_per_turn"):
        w = fill(word("card_rule", "plays_per_turn"), {"0": c["plays_per_turn"]})
        lines.append(w[0].upper() + w[1:] + ".")
    lines += [w for k, w in (("retain", "Retain."), ("exhaust", "Exhaust.")) if c.get(k)]
    # A copy of itself when exhausted (Necronomicurse).
    copies = [e for e in c.get("exhausted", []) if isinstance(e, dict) and "AddCopy" in e]
    for e in copies:
        lines.append(f"Whenever this card is exhausted, {effect_text(e, 'card', self_name=c['id'])}.")
    if c.get("exhausted") and not copies and "Exhaust." not in lines:
        lines.append("Exhaust.")
    if not lines:
        lines = ["No effect when played."]
    return {"head": " · ".join(parts), "lines": lines}


_POOLS_LOADED = []


def _load_pools():
    """Loads the content packs' pools once, so a card naming one
    (`Discover`, docs/specs/discovery.md) parses alone."""
    if not _POOLS_LOADED:
        todo = []
        for p in sorted(glob.glob(os.path.join(REPO, "content", "packs", "*.json"))):
            with open(p, encoding="utf-8") as f:
                text = f.read()
            if json.loads(text).get("pools"):
                todo.append(text)
        # A pack may Discover from another pack's pool (act1-colorless's
        # Discovery names Ironclad): load in passes until none is left.
        while todo:
            left = []
            for text in todo:
                try:
                    sts.load_content(text)
                except ValueError:
                    left.append(text)
            if len(left) == len(todo):
                sts.load_content(left[0])  # raises the first pack's error
            todo = left
        _POOLS_LOADED.append(True)


def upgraded_card(c, official=False, version=2):
    """Card entry `c` (from a content file) at level 1, as the engine
    resolves its upgrade block (sts.card_level), with the entry's other
    fields (rarity, class, ...) kept; None for no upgrade block."""
    _load_pools()
    up = sts.card_level(json.dumps(c), 1, official, version)
    if up is None:
        return None
    return {**{k: v for k, v in c.items() if k not in ("upgrade", "max_level")}, **json.loads(up)}


def _runs(texts):
    """Consecutive equal texts merged: [a, a, a] -> ["a (3 times)"]."""
    out = []
    for t in texts:
        if out and out[-1][0] == t:
            out[-1][1] += 1
        else:
            out.append([t, 1])
    return [t if n == 1 else f"{t}, {n} times" for t, n in out]


def describe_move(m, mv):
    lines = _runs([effect_text(e, "monster", m.get("split")) for e in mv.get("effects", [])])
    lines = [t[0].upper() + t[1:] + "." for t in lines] or ["Does nothing this turn."]
    return {"head": f"{mv['name']} · {m['id']}'s move", "lines": lines}


DIVIDER = "---"  # a description line drawn as a rule: a monster's move set above, how it picks below


def _pattern_lines(m):
    """Every pick rule in order, under its heading (none for no rules)."""
    moves = m.get("moves", [])
    names = [x["name"] for x in moves]
    # rules point at moves by position: a name several moves share gets its position (Sear #3)
    name = lambda i: ("no move" if i is None or not 0 <= i < len(moves)  # noqa: E731
                      else names[i] if names.count(names[i]) == 1 else f"{names[i]} #{i + 1}")
    rows = m.get("pattern", [])
    out = ["How it picks its move, the first rule that holds:"] if rows else []
    for r in rows:
        conds = []
        for c in r.get("when", []):
            key, v = (c, None) if isinstance(c, str) else next(iter(c.items()))
            if key == "Window" and v[1] is None:  # a value-dependent phrasing
                conds.append(f"after {name(v[0])} as its only move so far")
                continue
            w = word("pattern_condition", key, default=f"{key} {v}" if v is not None else key)
            conds.append(fill(w, {"0": v[0], "1": v[1]} if isinstance(v, list) else {"0": v}, name))
        (key, v), = r["then"].items()
        fields = {"0": v} if key == "Move" else {**v, "percent": round(v["p"] * 100)}
        what = fill(word("pattern_pick", key, default=f"{key} {v}"), fields, name)
        out.append(("Otherwise" if not conds else ", ".join(conds)[0].upper() + ", ".join(conds)[1:]) + f": {what}.")
    return out


def describe_monster(m):
    lo, hi = m["hp"] if isinstance(m.get("hp"), list) else (m.get("hp"), m.get("hp"))
    head = f"{m['id']} · {lo}{'' if lo == hi else '–' + str(hi)} HP"
    lines = []
    if m.get("start_block"):
        lines.append(f"Starts with {m['start_block']} block.")
    for p in m.get("start_powers", []):
        lines.append(f"Starts with {p['amount']} {human(p['power'])}.")
    seen = set()
    for mv in m.get("moves", []):
        d = describe_move(m, mv)
        key = (mv["name"], tuple(d["lines"]))
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"{mv['name']}: " + " ".join(d["lines"]))
    behaviour = []
    if m.get("code"):
        behaviour.append(word("code_monster", m["code"], f"Part of its behaviour is held in the engine's code: {m['code']}."))
    behaviour += _pattern_lines(m)
    if behaviour:
        lines += [DIVIDER] + behaviour
    return {"head": head, "lines": lines}


def _monster_hp(name, mons):
    """ "Cultist (48–54 HP)", "Acid Slime (M, 28–32 HP)"."""
    name = name.removeprefix("gen:")
    m = mons.get(name)
    if not m:
        return name
    lo, hi = m["hp"] if isinstance(m.get("hp"), list) else (m.get("hp"), m.get("hp"))
    hp = f"{lo}{'' if lo == hi else '–' + str(hi)} HP"
    return f"{name[:-1]}, {hp})" if name.endswith(")") else f"{name} ({hp})"


def _draw_text(s, name_of):
    """A slot that draws k monsters from a list, without putting them back
    (engine/src/registry.rs EncounterSlot::Draw): "4 drawn from 2 × A, B"."""
    counts = {}
    for n in s["from"]:
        counts[n] = counts.get(n, 0) + 1
    names = ", ".join(name_of(n) if c == 1 else f"{c} × {name_of(n)}" for n, c in counts.items())
    return fill(word("encounter_slot", "draw"), {"draw": s["draw"], "from": names})


def _slot_options(s):
    """A slot's options as lists of monster names, nested one_of flattened."""
    if isinstance(s, str):
        return [[s]]
    out = []
    for o in s["one_of"]:
        if len(o) == 1 and not isinstance(o[0], str):
            out += _slot_options(o[0])
        else:
            out.append([x for x in o if isinstance(x, str)])
    return out


def _encounter_slots(slots, mons):
    """Words for an encounter's monster list: one line per distinct slot
    ("2 × ..." for repeats), a slot that picks among monsters as "One of"."""
    texts = []
    for s in slots:
        if isinstance(s, dict) and "draw" in s:
            texts.append(_draw_text(s, lambda n: _monster_hp(n, mons)))
            continue
        words = [" + ".join(_monster_hp(n, mons) for n in o) for o in _slot_options(s)]
        texts.append(words[0] if len(words) == 1 else
                     fill(word("encounter_slot", "one_of"), {"options": ", ".join(words[:-1]) + " or " + words[-1]}))
    out = []
    for t in texts:
        if out and out[-1][0] == t:
            out[-1][1] += 1
        else:
            out.append([t, 1])
    return [t if n == 1 else f"{n} × " + (t[0].lower() + t[1:] if t.startswith("One of") else t) for t, n in out]


_DESCRIBE = {}


def describe_index():
    """{cards, monsters, powers, encounters, relics, potions: {name: {head, lines}}, moves:
    {monster: {move name: {head, lines}}}} for every source, official first
    (a pack entry of the same name doesn't replace it). Built once."""
    if not _DESCRIBE:
        ix = {"cards": {}, "monsters": {}, "powers": {}, "encounters": {}, "relics": {}, "potions": {}, "moves": {}}
        mons, encs = {}, []
        with open(os.path.join(REPO, "content", "encounters.json"), encoding="utf-8") as f:
            encs += json.load(f)["encounters"]
        for src, d in content_sources():
            for c in d.get("cards", []):
                ix["cards"].setdefault(c["id"], describe_card(c))
                up = upgraded_card(c, src == "official", d.get("version", 2))
                if up:
                    ix["cards"].setdefault(up["id"], describe_card(up))
            for q in d.get("potions", []):
                ix["potions"].setdefault(q["id"], describe_potion(q))
            for p in d.get("powers", []):
                ix["powers"].setdefault(p["id"], describe_power(p))
            for m in d.get("monsters", []):
                mons.setdefault(m["id"], m)
                ix["monsters"].setdefault(m["id"], describe_monster(m))
                mv = ix["moves"].setdefault(m["id"], {})
                for x in m.get("moves", []):
                    d_ = describe_move(m, x)
                    if x["name"] in mv and mv[x["name"]]["lines"] != d_["lines"]:
                        # moves sharing a name: each variant stays whole, in first-seen order
                        old = mv[x["name"]]["lines"]
                        alts = old[1:] if old[0] == "One of:" else [" ".join(old)]
                        new = " ".join(d_["lines"])
                        mv[x["name"]] = {"head": d_["head"], "lines": ["One of:"] + alts + ([new] if new not in alts else [])}
                    else:
                        mv.setdefault(x["name"], d_)
            encs += d.get("encounters", [])
        for e in encs:
            ix["encounters"].setdefault(e["id"], {
                "head": f"{e['id']} · {e.get('group', 'fight')} fight",
                "lines": _encounter_slots(e.get("monsters", []), mons)})
        _DESCRIBE.update(ix)
        for src, d in content_sources():
            own = None
            for r in d.get("relics", []):
                if r["id"] not in ix["relics"]:
                    own = own or _source_powers(d)
                    ix["relics"][r["id"]] = describe_relic(r, own)
    return _DESCRIBE


def describe(kind, name, source=None):
    """One description by kind ("cards", "monsters", "powers",
    "encounters", "relics", "potions") and name ("gen:" prefixes allowed); `source` picks that
    source's own entry. None when unknown."""
    name = str(name).removeprefix("gen:")
    if source not in (None, "official") and kind in ("cards", "monsters", "powers", "relics", "potions"):
        for s, d in content_sources():
            if s == source:
                for e in d.get(kind, []):
                    if e["id"] == name:
                        if kind == "relics":
                            return describe_relic(e, _source_powers(d))
                        return {"cards": describe_card, "monsters": describe_monster, "powers": describe_power,
                                "potions": describe_potion}[kind](e)
                    if kind == "cards" and e["id"] + "+" == name:
                        up = upgraded_card(e, s == "official", d.get("version", 2))
                        if up:
                            return describe_card(up)
        return None
    return describe_index()[kind].get(name)


INTENT_MODS = {"Strength": "its Strength", "Weak": "its Weak, × 0.75", "DamageDown": "its Damage Down, × 0.8",
               "SplitHits": "Split Hits, twice the hits at half damage"}


def board_of(c):
    """Combat.board() with plain-words descriptions (describe_board)."""
    return describe_board(c.board())


def describe_board(bd):
    """A Combat.board() dict (a copy) with plain-words descriptions: `desc`
    on each monster, its intent (the move's effects; `per_hit`, and `why`
    when the shown damage per hit isn't the move's base), each power and
    each card in hand; `describe` maps every card and power named on the
    board (piles included) to its description."""
    bd = copy.deepcopy(bd)
    ix = describe_index()
    cards, powers = {}, {}

    def card(name):
        d = describe("cards", name)
        if d is not None:
            cards[name] = d
        return d

    def power(p):
        d = describe("powers", p["name"])
        if d is not None:
            powers[p["name"]] = d
            p["desc"] = d
    for p in bd["player"]["powers"]:
        power(p)
    you = {p["name"]: p["amount"] for p in bd["player"]["powers"]}
    for m in bd["monsters"]:
        key = m["name"].removeprefix("gen:")
        m["desc"] = ix["monsters"].get(key)
        for p in m["powers"]:
            power(p)
        it = m.get("intent")
        if it:
            it["desc"] = ix["moves"].get(key, {}).get(it["name"])
            mon = next((x for _, d in content_sources() for x in d.get("monsters", []) if x["id"] == key), None)
            # the intent's `damage` is the move's total (engine agent::intent_damage), `hits` its hit count
            hits = it.get("hits") or 0
            it["per_hit"] = it["damage"] // hits if hits and it.get("damage") and it["damage"] % hits == 0 else None
            base = None
            for mv in (mon or {}).get("moves", []):
                if mv["name"] == it["name"]:
                    dmg = [e["Damage"] for e in mv["effects"] if isinstance(e, dict) and "Damage" in e]
                    if len(dmg) == 1:
                        base = (dmg[0]["amount"], dmg[0].get("hits", 1))
                    break
            shown = (it["per_hit"], hits)
            if it.get("damage") and base and it["per_hit"] is not None and shown != base:
                mods = [f"its Strength {p['amount']}" if p["name"] == "Strength" else INTENT_MODS[p["name"]]
                        for p in m["powers"] if p["name"] in INTENT_MODS]
                if "Vulnerable" in you:
                    mods.append("your Vulnerable, × 1.5")
                it["why"] = (f"The move's base is {base[0]}" + (f" × {base[1]}" if base[1] != 1 else "") +
                             f"; it shows {shown[0]}" + (f" × {shown[1]}" if shown[1] != 1 else "") +
                             (" because of " + ", ".join(mods) if mods else " after the engine's modifiers") + ".")
    for h in bd["hand"]:
        h["desc"] = card(h["name"])
    for pile in bd["piles"].values():
        for name, _ in pile.get("cards", []):
            card(name)
        for name in pile.get("known_top", []) or []:
            card(name if isinstance(name, str) else name[0])
    potions = {}
    for name in bd["player"].get("potions", []):
        d = describe("potions", name)
        if d is not None:
            potions[name] = d
    bd["describe"] = {"cards": cards, "powers": powers, "potions": potions}
    return bd


_FLOOR_MONSTERS = {}


def floor_monsters(encounter, seed, character):
    """Names of the monsters a fight of `encounter` starts with on `seed`
    (the starter deck stands in: the deck doesn't pick monsters)."""
    key = (encounter, int(seed), character)
    if key not in _FLOOR_MONSTERS:
        c = sts.Combat(list(sts.starter_deck(character)), encounter, seed=int(seed), character=character)
        _FLOOR_MONSTERS[key] = sorted({m["name"] for m in c.board()["monsters"]})
    return _FLOOR_MONSTERS[key]


# --- gauntlet runs (docs/specs/explorer-v2.md) ---------------------------------

_PLAYERS = {}  # a file's settings (as JSON) -> gauntlet.players(...)


def gauntlet_players(settings, threads=1):
    """gauntlet.players for a file's settings, built once per settings."""
    key = json.dumps(settings, sort_keys=True)
    if key not in _PLAYERS:
        _PLAYERS[key] = gauntlet.players(settings, threads)
    return _PLAYERS[key]


_CELLS = []


def pool_cells():
    """ladder.pool_cells, read once (about 0.75 s each time otherwise)."""
    if not _CELLS:
        import ladder
        _CELLS.append(ladder.pool_cells())
    return _CELLS[0]


def sequence(settings, i):
    """Sequence i as the file's run played it: gauntlet.sequences, with the
    starter deck when the file's start is "starter" (as play_cmd does)."""
    s = gauntlet.sequences(1, int(i), pool_cells())[0]
    if settings.get("start", "cell") == "starter":
        s = {**s, "deck": list(sts.starter_deck(s["character"]))}
    return s


def run_events(settings, seq, row, max_hp=gauntlet.MAX_HP):
    """The choices of a file's row, rebuilt in gauntlet.run's order: per
    event {k, kind (rest, offer, extra, removal), j (extra offers), item
    (sequence, HP, deck) as the hook saw it, recorded (the row's choice:
    a card or None, "heal" or a card to upgrade, the card removed or None)}."""
    return walk(settings, seq, row, max_hp)["events"]


def walk(settings, seq, row, max_hp=gauntlet.MAX_HP):
    """A file's row walked in gauntlet.run's order: {events (run_events),
    fights (per floor played, the spec its fight started from: encounter,
    deck, seed, hp, character, group, as run() builds it), deck (the deck
    after the last floor's choices)}."""
    hp, deck, out, fights = max_hp, list(seq["deck"]), [], []
    for k, f in enumerate(row["floors"]):
        if "rest" in f:
            out.append({"k": k, "kind": "rest", "item": (seq, hp, list(deck)), "recorded": f["rest"]})
            if f["rest"] == "heal":
                hp = gauntlet.rest(hp, max_hp)
            else:
                deck = gauntlet.upgrade(deck, f["rest"])
        elif gauntlet.SHAPE[k] == "boss":
            hp = gauntlet.rest(hp, max_hp)
        group = "hallway" if f.get("path") == "hallway" else gauntlet.GROUP[gauntlet.SHAPE[k]]
        fights.append({"encounter": f["encounter"], "deck": list(deck), "seed": seq["fights"][k]["seed"], "hp": hp,
                       "character": seq["character"], "group": group})
        if not f["won"]:
            break
        hp = min(max_hp, int(f["hp_end"]))
        if "mid_rest" in f:
            hp = f["mid_rest"]
        if "offer" in f:
            out.append({"k": k, "kind": "offer", "j": 0, "item": (seq, hp, list(deck)), "recorded": f["took"],
                        "offer": f["offer"]})
            if f["took"] is not None:
                deck.append(f["took"])
        for j, x in enumerate(f.get("extra", []), 1):
            out.append({"k": k, "kind": "extra", "j": j, "item": (seq, hp, list(deck)), "recorded": x["took"],
                        "offer": x["offer"]})
            if x["took"] is not None:
                deck.append(x["took"])
        if "removed" in f:
            out.append({"k": k, "kind": "removal", "item": (seq, hp, list(deck)), "recorded": f["removed"]})
            if f["removed"] is not None:
                deck = gauntlet.remove(deck, f["removed"])
    return {"events": out, "fights": fights, "deck": deck}


def parse_choices(choices):
    """The page's `choices` (a JSON list, URL-encoded by the page), an
    ordered history of the owner's changes: picks {k, e (offer, extra, rest,
    removal, path), j, pick} and taken-over fights {k, won, hp}. A later
    entry for the same event or the same floor's fight replaces an earlier
    one. Returns ({(k, e, j): pick}, {k: (won, hp_end)}, entries), entries
    being the kept ones in history order, each {key, entry}."""
    if choices in (None, "", "[]"):
        return {}, {}, []
    picks, fights, last = {}, {}, {}
    for n, c in enumerate(json.loads(choices) if isinstance(choices, str) else choices):
        k = int(c["k"])
        if "e" in c:
            if c["e"] not in ("offer", "extra", "rest", "removal", "path"):
                raise ValueError(f"no event kind {c['e']!r}")
            key = (k, c["e"], int(c.get("j") or 0))
            picks[key] = c.get("pick")
        else:
            won = bool(c["won"])
            key = (k, "fight", 0)
            fights[k] = (won, int(c["hp"]) if won else 0)
        last[key] = (n, c)
    entries = [{"key": key, "entry": c} for key, (n, c) in sorted(last.items(), key=lambda kv: kv[1][0])]
    return picks, fights, entries


def file_points(seq, row, max_hp=gauntlet.MAX_HP):
    """The file's carried state at every point of its row, for comparing the
    owner's line by afterstates: {(k, point): (HP, deck as a sorted tuple)}
    with point "start" (after the boss's rest), "fight" (after the fight and
    a mid-rest; None when the row lost it), ("offer", j) and "removal"."""
    hp, deck, pts = max_hp, list(seq["deck"]), {}
    st = lambda: (hp, tuple(sorted(deck)))  # noqa: E731
    for k, f in enumerate(row["floors"]):
        if "rest" in f:
            hp, deck = (gauntlet.rest(hp, max_hp), deck) if f["rest"] == "heal" else (hp, gauntlet.upgrade(deck, f["rest"]))
        elif gauntlet.SHAPE[k] == "boss":
            hp = gauntlet.rest(hp, max_hp)
        pts[(k, "start")] = st()
        if not f["won"]:
            pts[(k, "fight")] = None
            break
        hp = min(max_hp, int(f["hp_end"]))
        if "mid_rest" in f:
            hp = f["mid_rest"]
        pts[(k, "fight")] = st()
        for j, x in enumerate(([f] if "offer" in f else []) + f.get("extra", [])):
            if x["took"] is not None:
                deck.append(x["took"])
            pts[(k, ("offer", j))] = st()
        if "removed" in f:
            if f["removed"] is not None:
                deck = gauntlet.remove(deck, f["removed"])
            pts[(k, "removal")] = st()
    return pts


_MISSING = object()


class MemoPlayers:
    """gauntlet.players' hooks for one sequence item at a time, each call
    remembered (the sim chooser plays fights per call; the page asks again
    on every /api/run)."""

    def __init__(self, p):
        self.p, self.memo = p, {}
        for name in ("offer", "elite_offers", "mid_rest"):
            setattr(self, name, getattr(p, name))
        for name in ("reward", "rest_hook", "remove_hook", "path_hook"):
            setattr(self, name, None if getattr(p, name) is None else self.wrap(name))

    def wrap(self, name):
        fn = getattr(self.p, name)

        def call(*args):
            key = json.dumps([name, [a if not isinstance(a, list) else
                                     [[s["i"], hp, sorted(deck)] for s, hp, deck in a] for a in args]])
            if key not in self.memo:
                self.memo[key] = fn(*args)
            return self.memo[key]
        return call


def line(settings, seq, row, choices, outcome, p=None, max_hp=gauntlet.MAX_HP, until=None):
    """A sequence walked as gauntlet.run plays it, with the owner's history
    (`choices`, parse_choices) applied, judged by afterstates
    (docs/specs/explorer-v2.md, Amendment 1): after every fight and every
    event the owner's carried state (HP, the deck as a multiset, and the
    floor's path) is compared with the file's row at the same point
    (`file_points`). While equal, the walk is on the file's line: the row's
    events and results, no chooser call, no replay. While different, it is
    the owner's line: the owner's picks and taken-over fights where given,
    else the file's own player and hooks (`p`, gauntlet.players), each fight
    from `outcome(k, spec)` ({won, hp_end}, or None when not played yet: the
    walk stops there, `pending`). As soon as the state equals the row's
    again, it rejoins the file's line. `until` k stops once floor k's fight
    spec is known, before its outcome. Returns {floors: per floor fought {k,
    line ("file" when the fight starts from the row's state on the row's
    path and ends as the row's did, else "owner"), spec, result (None when
    pending), source (row, owner, player), events}, pending (the floor to
    open next, or None), deck, history (the kept entries in order, each with
    `changed`: False when the afterstate after it equalled the row's, None
    when the walk never reached it)}. Each event: {k, kind, j, offer,
    recorded (the row's choice, None off the row), chosen, by (row, owner,
    file)}."""
    picks, overrides, entries = parse_choices(choices)
    rows = row["floors"]
    pts = file_points(seq, row, max_hp)
    hp, deck, floors, pending = max_hp, list(seq["deck"]), [], None
    changed = {}

    def at(k, point, path_same=True):
        """True when the owner's carried state equals the row's at (k, point)."""
        want = pts.get((k, point))
        return path_same and want is not None and want == (hp, tuple(sorted(deck)))

    def choose(k, kind, j, rec, on, offer, file_pick):
        """(chosen, by) for one event, the owner's pick checked."""
        pick = picks.get((k, kind, j), _MISSING)
        if pick is not _MISSING:
            if offer is not None and pick is not None and pick not in offer:
                raise ValueError(f"floor {k}: {pick!r} isn't in the offer {offer}")
            if kind == "rest" and pick not in ("heal", *gauntlet.upgradable(deck)):
                raise ValueError(f"floor {k}: can't upgrade {pick!r}")
            if kind == "removal" and pick is not None and pick not in deck:
                raise ValueError(f"floor {k}: no {pick!r} in the deck to remove")
            return pick, "owner"
        if on:
            return rec, "row"
        return file_pick(), "file"

    on = True  # the owner's state equals the row's at the current point
    for k, kind in enumerate(gauntlet.SHAPE):
        f = rows[k] if k < len(rows) else None
        on = on and f is not None
        events = []
        item = lambda: (seq, hp, list(deck))  # noqa: E731
        if kind == "boss":
            if (on and "rest" in f) or (not on and p is not None and p.rest_hook is not None):
                rec = f["rest"] if on else None
                chosen, by = choose(k, "rest", 0, rec, on, None, lambda: p.rest_hook([item()])[0] or "heal")
                events.append({"k": k, "kind": "rest", "j": None, "offer": None,
                               "options": event_options("rest", None, deck),
                               "recorded": rec, "chosen": chosen, "by": by})
                hp, deck = (gauntlet.rest(hp, max_hp), deck) if chosen == "heal" else (hp, gauntlet.upgrade(deck, chosen))
            else:
                hp = gauntlet.rest(hp, max_hp)
        on = at(k, "start")
        if (k, "rest", 0) in picks:
            changed[(k, "rest", 0)] = not on
        path, fpath = None, (f.get("path") if f is not None else None)
        if kind == "elite" and ((on and "path" in f) or (not on and p is not None and p.path_hook)):
            rec = f["path"] if on else None
            chosen, by = choose(k, "path", 0, rec, on, None,
                                lambda: "elite" if p.path_hook(k, [item()])[0] else "hallway")
            events.append({"k": k, "kind": "path", "j": None, "offer": ["elite", "hallway"],
                           "options": ["elite", "hallway"], "recorded": rec, "chosen": chosen, "by": by})
            path = chosen
        same_path = path == fpath
        on = on and same_path
        if (k, "path", 0) in picks:
            changed[(k, "path", 0)] = not on
        if on:
            enc_ = f["encounter"]
        elif path == "hallway":
            enc_ = gauntlet.alt_fight(seq["i"], k, seq["fights"][k - 1]["encounter"])
        else:
            enc_ = seq["fights"][k]["encounter"]
        group = "hallway" if path == "hallway" else gauntlet.GROUP[kind]
        spec = {"encounter": enc_, "deck": list(deck), "seed": seq["fights"][k]["seed"], "hp": hp,
                "character": seq["character"], "group": group}
        floor = {"k": k, "line": "file" if on else "owner", "spec": spec, "events": events}
        floors.append(floor)
        if until is not None and k == until:
            break
        row_result = {"won": bool(f["won"]), "hp_end": int(f["hp_end"]) if f["won"] else 0} if f is not None else None
        if k in overrides:
            won, hpe = overrides[k]
            result, source = {"won": won, "hp_end": hpe}, "owner"
        elif on:
            result, source = row_result, "row"
        else:
            result, source = outcome(k, spec), "player"
        if on and result != row_result:
            floor["line"] = "owner"
        floor["result"], floor["source"] = (result, source) if result is not None else (None, None)
        if result is None:
            pending = k
            break
        if not result["won"]:
            if k in overrides:
                changed[(k, "fight", 0)] = not (on and row_result == result)
            break
        hp = min(max_hp, int(result["hp_end"]))
        if (f is not None and "mid_rest" in f) or (p is not None and k == p.mid_rest):
            hp = gauntlet.rest(hp, max_hp)
        on = at(k, "fight", same_path)
        if k in overrides:
            changed[(k, "fight", 0)] = not on
        if kind == "boss":
            continue
        n_offers = 0
        if on:
            n_offers = (1 if "offer" in f else 0) + len(f.get("extra", []))
        elif p is not None and p.reward is not None:
            n_offers = p.elite_offers if kind == "elite" and path != "hallway" else 1
        for j in range(n_offers):
            fj = (f if j == 0 else f["extra"][j - 1]) if on else None
            if fj is None and p is None:
                break
            offer = fj["offer"] if fj is not None else p.offer(k, seq, j)
            rec = fj["took"] if fj is not None else None

            def file_pick(j=j):
                return p.reward(k, [item()], j) if j else p.reward(k, [item()])
            ekind = "offer" if j == 0 else "extra"
            chosen, by = choose(k, ekind, j, rec, fj is not None, offer, lambda: file_pick()[0][1])
            events.append({"k": k, "kind": ekind, "j": j, "offer": list(offer),
                           "options": event_options("offer", offer, deck), "recorded": rec, "chosen": chosen,
                           "by": by})
            if chosen is not None:
                deck.append(chosen)
            on = at(k, ("offer", j), same_path)
            if (k, ekind, j) in picks:
                changed[(k, ekind, j)] = not on
        if (on and "removed" in f) or (
                not on and p is not None and p.remove_hook is not None and k == gauntlet.REMOVE_FLOOR):
            rec = f["removed"] if on else None
            chosen, by = choose(k, "removal", 0, rec, on, None, lambda: p.remove_hook([item()])[0])
            events.append({"k": k, "kind": "removal", "j": None, "offer": None,
                           "options": event_options("removal", None, deck), "recorded": rec, "chosen": chosen,
                           "by": by})
            if chosen is not None:
                deck = gauntlet.remove(deck, chosen)
            on = at(k, "removal", same_path)
            if (k, "removal", 0) in picks:
                changed[(k, "removal", 0)] = not on
    history = [{**e["entry"], "changed": changed.get(e["key"])} for e in entries]
    return {"floors": floors, "pending": pending, "deck": deck, "history": history}


def event_options(kind, offer, deck):
    """What a run event lets the owner pick (the choices `line` accepts): an
    offer's cards then None (skip), a rest "heal" then the deck's upgradable
    cards, a removal None (keep every card) then the deck's distinct cards."""
    if kind in ("offer", "extra"):
        return list(offer) + [None]
    if kind == "rest":
        return ["heal"] + gauntlet.upgradable(deck)
    if kind == "removal":
        return [None] + list(dict.fromkeys(deck))
    return ["elite", "hallway"]


def event_scores(settings, event, threads=1):
    """One run event's options, scores and pick from the file's own chooser
    (gauntlet.players' score functions, the ones its hooks choose by):
    {options (None = skip / keep / heal first), scores (None for a rule),
    pick}; None when the setting made no choice there."""
    p = gauntlet_players(settings, threads)
    kind, item = event["kind"], [event["item"]]
    if kind in ("offer", "extra"):
        return p.offer_scores(event["k"], item, event.get("j", 0))[0] if p.offer_scores else None
    if kind == "rest":
        return p.rest_scores(item)[0] if p.rest_scores else None
    return p.remove_scores(item)[0] if p.remove_scores else None


def depth_paired():
    """scripts/analysis/depth_paired.py, imported on first use."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis")
    if path not in sys.path:
        sys.path.insert(0, path)
    import depth_paired as dp
    return dp


def align(group, sopts):
    """The index in `sopts` (a search's options, each a list of action
    texts) of the option holding the view's option `group`, else None."""
    want = frozenset(group)
    for j, g in enumerate(sopts):
        if frozenset(g) == want:
            return j
    return next((j for j, g in enumerate(sopts) if group and group[0] in g), None)


BASE_SETTINGS = ("player", "two_turn", "shape", "rest", "seed")


def fidelity(out, frow):
    """A replayed floor (`out`, from Explorer.replay_floor) against the file's
    row: {matches, file and replay (won, end HP: 0 on a loss, as the gauntlet
    records it), cause (None when they match: the pack's change since the
    run when its hash moved, else this build playing the fight differently)}."""
    want = {"won": bool(frow["won"]), "hp_end": int(frow["hp_end"]) if frow["won"] else 0}
    cause = None
    if out["replay"] != want:
        pack = out.get("pack")
        cause = (f"the pack changed since the run (file {pack['file']}, today {pack['now']})"
                 if pack and pack["file"] != pack["now"] else "this build plays the fight differently")
    return {"matches": out["replay"] == want, "file": want, "replay": out["replay"], "cause": cause}


def setting_tags(st):
    """A gauntlet file's settings as short tags: "two-turn" when two turns
    deep, then each setting past the base ones (a flag by its name, others
    as name=value; a pack by its file's name)."""
    tags = ["two-turn"] if st.get("two_turn") else ["one-turn"]
    for k, v in st.items():
        if k in BASE_SETTINGS:
            continue
        if k == "pack" and isinstance(v, str):
            v = os.path.splitext(os.path.basename(v.rpartition("@")[0]))[0]
        elif k in ("chooser", "match") and isinstance(v, str):
            v = run_id(v.partition("@")[0]) + (("@" + v.partition("@")[2]) if "@" in v else "")
        elif isinstance(v, dict):
            v = ",".join(f"{a}={b}" for a, b in v.items())
        tags.append(k if v is True else f"{k}={v}")
    return tags


def strip_cell(k, f):
    """One floor of a row as the sequence strip shows it."""
    out = {"k": k, "kind": gauntlet.SHAPE[k], "encounter": f["encounter"], "hp_start": f["hp_start"],
           "hp_end": f["hp_end"], "won": bool(f["won"])}
    for key in ("took", "rest", "removed", "path", "mid_rest"):
        if key in f:
            out[key] = f[key]
    if "extra" in f:
        out["extra"] = [x["took"] for x in f["extra"]]
    return out


def ladder_files(p):
    """The net files of a player string (ladder.player_files without the
    import: a .pt path, or several joined by +)."""
    base = p.partition("@")[0]
    return base.split("+") if "+" in base else [base]


def two_turn_search():
    """The gauntlet's two-turn search settings (ladder.play_two_turn's)."""
    import ladder
    return {"limit": bench.LIMIT, **ladder.TWO_TURN}


# --- mutate and boss-replay cells ------------------------------------------------

BOSS_FLOOR = len(gauntlet.SHAPE) - 1
AGENT_XOR = 0xA6E7A6E7  # sts.play_on: the search agent's RNG is Rng(game RNG's next u64 ^ this)
_U64 = (1 << 64) - 1


def analysis(name):
    """A module of scripts/analysis/, imported on first use."""
    depth_paired()  # puts scripts/analysis on sys.path
    return importlib.import_module(name)


def repo_path(p):
    """A path a result file names (repo-relative, or absolute)."""
    return p if os.path.isabs(p) else os.path.join(REPO, p)


class Rng:
    """The engine's Rng (engine/src/rng.rs: xoshiro256** seeded by
    splitmix64), so the explorer can rebuild a play-out's search seeds."""

    def __init__(self, seed):
        x, self.s = int(seed) & _U64, []
        for _ in range(4):
            x = (x + 0x9E3779B97F4A7C15) & _U64
            z = x
            z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _U64
            z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _U64
            self.s.append(z ^ (z >> 31))

    @staticmethod
    def _rotl(v, k):
        return ((v << k) | (v >> (64 - k))) & _U64

    def next_u64(self):
        s = self.s
        out = (self._rotl((s[1] * 5) & _U64, 7) * 9) & _U64
        t = (s[1] << 17) & _U64
        s[2] ^= s[0]
        s[3] ^= s[1]
        s[1] ^= s[2]
        s[0] ^= s[3]
        s[2] ^= t
        s[3] = self._rotl(s[3], 45)
        return out


def agent_rng(play_seed):
    """sts.play_on's search-agent RNG for a play-out seeded `play_seed`
    (Combat.with_seed / decode: the game RNG is Rng(play_seed))."""
    return Rng(Rng(play_seed).next_u64() ^ AGENT_XOR)


def agent_seed(play_seed, n):
    """The search seed of decision n (0 on) of that play-out; 0 when the
    play-out's seed isn't known (its one-turn searches don't sample)."""
    if play_seed is None:
        return 0
    r = agent_rng(play_seed)
    for _ in range(n):
        r.next_u64()
    return r.next_u64()


def search_scores(c, ev, search, seed, action=False):
    """(options as action texts, one-turn values, two-turn values, pick[,
    the action]) of sts.search at `c` with the search agent's settings
    (`search`: limit, and sample_k, turns, max_nodes when two turns deep)
    and search seed `seed`; values of a two-turn search go in the second
    list."""
    r = sts.search(c, ev.evaluator if ev else "heuristic", features=ev.features if ev else None,
                   seed=int(seed or 0), **search)
    sopts = [[enc(a) for a in acts] for acts, _ in r["options"]]
    vals = [float(v) for _, v in r["options"]]
    a = enc(r["action"])
    pick = next((n for n, g in enumerate(sopts) if a in g), None)
    one, two = (vals, None) if search.get("turns", 1) == 1 else ([None] * len(vals), vals)
    return (sopts, one, two, pick, r["action"]) if action else (sopts, one, two, pick)


def play_cell(cell, ev):
    """A mutate cell's fight played to the end the way sts.play_on's search
    agent plays it (engine/src/runner.rs play_from: advance, then one
    search per action, its seed the agent RNG's next value, stop past turn
    100), every decision recorded with its search's scores. The result shown
    is the player's own: `sts.play_on` (as the scripts play the cell) runs
    first, and the loop's end must equal it, else this raises."""
    c = cell["combat"]
    kw = dict(cell["search"])
    if ev is not None:
        kw.update(evaluator=ev.evaluator, features=ev.features)
    r = sts.play_on([c.clone()], threads=1, **kw)[0]
    replay = {"won": bool(r["won"]), "hp_end": int(r["hp_end"])}
    agent = agent_rng(cell["agent"]) if cell["agent"] is not None else None
    while not c.is_over() and not c.awaiting_action():
        c.advance()
    decisions = []
    while not c.is_over() and c.turn() <= 100:
        sopts, one, two, pick, a = search_scores(c, ev, cell["search"], agent.next_u64() if agent else 0, action=True)
        decisions.append({"n": len(decisions), "turn": c.turn(), "hex": hex_of(c), "action": enc(a),
                          "scores": {"options": sopts, "one": one, "two": two, "pick": pick}, "board_data": c.board()})
        c.step(a)
    steps_end = {"won": bool(c.is_over() and c.won()), "hp_end": int(c.player_hp())}
    if steps_end != replay:
        raise RuntimeError(f"stepping the recorded actions ends {steps_end}, the player's run {replay}")
    return {"depth": 2 if cell["search"].get("turns", 1) == 2 else 1, "decisions": decisions,
            "end": hex_of(c), "replay": replay}


def mutate_kind(d):
    """"monsters" (mutate_monsters.py) or "cards" (mutate_cards.py) by the
    file's settings: only mutated monsters record two_seeds."""
    return "monsters" if "two_seeds" in d["settings"] else "cards"


def test_players(d):
    """{player name: player string} of a mutate file's players present in its
    rows, as its script plays them (its PLAYERS with the file's net)."""
    st = d["settings"]
    if mutate_kind(d) == "monsters":
        mm = analysis("mutate_monsters")
        p = dict(mm.PLAYERS)
        if st.get("net"):
            p["one"] = st["net"] + "@hpb0.01"
        if st.get("two_net"):
            p["two"] = st["two_net"] + "@hpe0.01"
    else:
        mc = analysis("mutate_cards")
        p = dict(mc.PLAYERS)
        if st.get("net"):
            p["one"], p["tsl"] = st["net"] + "@hpb0.01", st["net"] + "@hpb0.01@tsl1"
            for a in mc.PROJECTED:
                p[a] = st["net"] + "@hpb0.01@tsl1@" + a
    present = {q for r in d["rows"] for col in ("official", "parent") for q in r.get(col, {})}
    return {k: v or HEURISTIC for k, v in p.items() if k in present}


def mutate_cell(d, f, fights_of):
    """A mutate cell rebuilt by its script's own functions: the start
    (bias_audit.fights of the file's product, matched by sequence and
    floor), the column's fight (mutated monsters: mutate_monsters.variant of
    start_state, played from with_seed of the seed; mutated cards:
    mutate_cards.start with the deck swapped to the pack copy or variant, the
    full pack loaded as the script loads it), the seed (the script's
    per-start seed list) and the player (its PLAYERS)."""
    st, sub = d["settings"], mutate_kind(d)
    i, floor, col = int(f["i"]), int(f["floor"]), f.get("mod") or "parent"
    row = next((r for r in d["rows"] if r["i"] == i and r["floor"] == floor
                and (sub == "monsters" or r.get("card") == f.get("card"))), None)
    if row is None:
        raise ValueError(f"no start (sequence {i}, floor {floor}{', card ' + str(f.get('card')) if sub == 'cards' else ''})")
    by = row.get(col) if col in ("official", "parent") else row.get("mods", {}).get(col)
    if by is None or f.get("player") not in by:
        raise ValueError(f"no {f.get('player')!r} results under {col!r} at this start")
    res, j = by[f["player"]], int(f.get("seed") or 0)
    if not 0 <= j < len(res):
        raise ValueError(f"seed index {j} out of 0..{len(res) - 1}")
    spec = next((s for s in fights_of(st["product"]) if s["i"] == i and s["floor"] == floor), None)
    if spec is None:
        raise ValueError(f"the product file has no elite or boss start at sequence {i}, floor {floor}")
    name = test_players(d)[f["player"]]
    if sub == "monsters":
        mm = analysis("mutate_monsters")
        gen = sts.load_content(mm.gen_pack()) if col in mm.GEN else None
        c = mm.start_state(spec)
        v = sts.Combat.decode(bytes(c.encode())) if col == "parent" else mm.variant(c, mm.ALL[col])
        seeds = [int(x) for x in np.random.default_rng([20261103, i, floor]).integers(2**62, size=st["seeds"])]
        seed = seeds[j]
        combat, agent = v.with_seed(seed), seed
        search = {"limit": bench.LIMIT, **(mm.TWO_TURN if f["player"] == "two" else {})}
        extra = {"gen_pack": gen}
    else:
        mc = analysis("mutate_cards")
        h = sts.load_content(json.dumps(mc.pack()))  # the full pack, as the script loads it
        card = row["card"]
        deck = spec["deck"] if col == "official" else mc.swapped(
            spec["deck"], card, "gen:" + (mc.copy_id(card) if col == "parent" else col))
        seeds = [int(x) for x in np.random.default_rng([20261107, i, floor]).integers(2**62, size=st["seeds"])]
        seed = seeds[j]
        combat, agent = mc.start(spec, deck, seed), None  # the agent seed comes from the started combat's RNG
        search = {"limit": bench.LIMIT}
        extra = {"pack": h, "deck": deck}
    won, hp = res[j]
    return {"key": {"kind": "mutate", "sub": sub, "product": st["product"], "i": i, "floor": floor,
                    "card": row.get("card"), "col": col, "player": name, "seed": seed, "search": search, **extra},
            "combat": combat, "agent": agent, "search": search, "player": name,
            "file": {"won": bool(won), "hp_end": int(hp)}, "compare": ("won", "hp_end")}


def boss_cell(d, f):
    """A boss-replay cell rebuilt by boss_replay.py's own functions: the row
    (rebuild of the gauntlet file it read), the spec (specs_for: the HP
    level, or the row's arrival HP, and seed j) and the file's player, played
    as the gauntlet's one-turn floor (ladder.play_bench)."""
    br, st = analysis("boss_replay"), d["settings"]
    with open(repo_path(st["file"]), encoding="utf-8") as fh:
        src = json.load(fh)
    seqs = {s["i"]: s for s in gauntlet.sequences(max(r["i"] for r in src["sequences"]) + 1, 0, pool_cells())}
    try:
        decks, _ = br.rebuild(src["sequences"], src["settings"], seqs)
    except SystemExit as e:
        raise ValueError(str(e)) from None
    i, j = int(f["i"]), int(f.get("seed") or 0)
    row = next((r for r in decks if r["i"] == i), None)
    frow = next((r for r in d["rows"] if r["i"] == i), None)
    if row is None or frow is None:
        raise ValueError(f"no boss row for sequence {i}")
    if not 0 <= j < int(st["seeds"]):
        raise ValueError(f"seed index {j} out of 0..{int(st['seeds']) - 1}")
    if st["hp"] == "arrival":
        hp = row["hp_obs"]
        want, compare = {"won": bool(frow["won"]["arrival"][j]), "hp_end": int(frow["hp_end"][j])}, ("won", "hp_end")
    else:
        hp = int(f["hp"])
        if str(hp) not in frow["won"]:
            raise ValueError(f"no HP level {hp} in this file ({', '.join(frow['won'])})")
        want, compare = {"won": bool(frow["won"][str(hp)][j])}, ("won",)
    spec = br.specs_for(row, [hp], int(st["seeds"]))[j]
    return {"key": {"kind": "boss_replay", "spec": spec, "player": st["player"]}, "spec": spec, "search": None,
            "player": st["player"], "file": want, "compare": compare}


def sort_rows(rows, sort, desc, tie):
    """`rows` sorted by column `sort` ("regret:<player>" reads that
    player's regret), descending when `desc` is "1", ties in `tie` order;
    unchanged when `sort` is empty. A missing value (None) sorts after every
    value, before them when descending."""
    if not sort:
        return rows
    if sort.startswith("regret:"):
        name = sort.split(":", 1)[1]
        get = lambda r: r["regret"][name]
    elif rows and sort not in rows[0]:
        raise ValueError(f"no column {sort!r}")
    else:
        get = lambda r: r[sort]
    key = lambda r: (get(r) is None, get(r) if get(r) is not None else 0)
    rows = sorted(rows, key=lambda r: r[tie])
    return sorted(rows, key=key, reverse=str(desc) == "1")


GROUP_PAGE = 100  # rows per page when a table is grouped (a group's rows stay together; headers repeat)


def group_page(rows, by, sort, desc, tie, page, size=None, key=None, label=None, order=None):
    """The shared group-by (docs/specs/explorer-v2.md, Amendment 3): `rows`
    sorted by `sort` (sort_rows) inside groups of equal `key(row)` (default
    row[by]), groups in `order` (a list of keys) or by key (missing last),
    each row tagged `_group` (`label(key)`, default the key as text), then
    paged. Without `by`, today's sort and paging. Returns {by, total, page,
    pages, groups: [{key, label, n, page of its first row}], rows}."""
    size = PAGE if size is None else size
    if by:
        if key is None:
            if rows and by not in rows[0]:
                raise ValueError(f"no column {by!r} to group by")
            key = lambda r: r[by]  # noqa: E731
        label = label or (lambda k: "–" if k is None else str(k))
        rows = sort_rows(rows, sort, desc, tie)
        ks = [key(r) for r in rows]
        if order is None:
            uniq = list(dict.fromkeys(ks))
            num = lambda k: isinstance(k, (int, float)) and not isinstance(k, bool)  # noqa: E731
            order = sorted(uniq, key=lambda k: (k is None, "" if num(k) else str(k), k if num(k) else 0))
        rank = {k: j for j, k in enumerate(order)}
        both = sorted(zip(ks, rows), key=lambda kr: rank.get(kr[0], len(rank)))
        rows = [{**r, "_group": label(k)} for k, r in both]
        size = max(size, GROUP_PAGE)
        counts, first = {}, {}
        for j, (k, _) in enumerate(both):
            counts[k] = counts.get(k, 0) + 1
            first.setdefault(k, j)
        groups = [{"key": k, "label": label(k), "n": counts[k], "page": first[k] // size} for k in order if k in counts]
    else:
        rows, groups = sort_rows(rows, sort, desc, tie), []
    page = int(page or 0)
    return {"by": by or None, "groups": groups, "total": len(rows), "page": page,
            "pages": (len(rows) + size - 1) // size, "rows": rows[page * size:(page + 1) * size]}


def respond(ex, path, query):
    """(status, JSON-able body) for one GET."""
    q = {k: v[0] for k, v in parse_qs(query).items()}
    routes = {
        "/api/status": lambda: ex.status(),
        "/api/dbs": lambda: ex.dbs(),
        "/api/open_db": lambda: ex.open_db(q["path"]),
        "/api/close_db": lambda: ex.close_db(),
        "/api/nets": lambda: ex.nets(q.get("file")),
        "/api/puzzles": lambda: ex.puzzle_list(q.get("half"), q.get("horizon"), q.get("contested"), q.get("wrong"),
                                               q.get("sort"), q.get("ev"), q.get("page"), q.get("desc"), q.get("dull"),
                                               q.get("with"), q.get("by")),
        "/api/positions": lambda: ex.position_list(q["source"], q.get("page"), q.get("sort"), q.get("desc")),
        "/api/state": lambda: ex.state(q.get("puzzle"), q.get("id"), q.get("hex"), q.get("seed"), q.get("with")),
        "/api/step": lambda: ex.step(q.get("hex"), q["option"], q.get("seed"), q.get("with"), q.get("player"), q.get("file"),
                                     q.get("i"), q.get("k"), q.get("n"), q.get("choices"), q.get("mine"),
                                     q.get("fight"), q.get("steps")),
        "/api/view": lambda: ex.state_view(q.get("hex"), q.get("player"), q.get("with"), q.get("file"), q.get("i"),
                                           q.get("k"), q.get("n"), q.get("fresh"), q.get("seed"), q.get("choices"),
                                           q.get("fight"), q.get("steps")),
        "/api/mutate": lambda: ex.mutate(q["file"], q.get("mod"), q.get("player"), q.get("etype"), q.get("encounter"),
                                         q.get("sort"), q.get("desc"), q.get("page"), q.get("by") or "parent"),
        "/api/boss_replay": lambda: ex.boss_replay(q["file"], q.get("boss"), q.get("half"), q.get("sort"),
                                                   q.get("desc"), q.get("page"), q.get("by") or "sequence"),
        "/api/fight": lambda: ex.fight(q["fight"]),
        "/api/solve": lambda: ex.solve(q["hex"], q.get("with")),
        "/api/reopen": lambda: ex.reopen(),
        "/api/files": lambda: ex.files(q.get("kind") or "gauntlet", q.get("q")),
        "/api/sequences": lambda: ex.sequences(q["file"], q.get("half"), q.get("cleared"), q.get("died"),
                                               q.get("encounter"), q.get("card"), q.get("sort"), q.get("desc"),
                                               q.get("page"), q.get("by")),
        "/api/run": lambda: ex.run(q["file"], q["i"], q.get("choices")),
        "/api/event": lambda: ex.event(q["file"], q["i"], q["e"]),
        "/api/floor": lambda: ex.floor(q["file"], q["i"], q["k"], q.get("choices")),
        "/api/content": lambda: ex.content(q.get("kind") or "cards", q.get("source"), q.get("q"), q.get("file"),
                                           q.get("by"), q.get("sort"), q.get("desc")),
        "/api/describe": lambda: describe_index(),
    }
    if path not in routes:
        return 404, {"error": f"no endpoint {path}"}
    try:
        return 200, routes[path]()
    except LookupError as e:
        return 503, {"error": str(e)}
    except (KeyError, ValueError, IndexError, sqlite3.Error, RuntimeError) as e:
        return 400, {"error": f"{type(e).__name__}: {e}"}


def ui_css():
    """The dashboard's stylesheet, imported (not copied), so both pages keep
    one look; the explorer's additions live in explore.html."""
    import dashboard
    return dashboard.CSS


def handler(ex):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                with open(HTML, "rb") as f:
                    body, ctype, status = f.read(), "text/html; charset=utf-8", 200
            elif url.path == "/ui.css":
                body, ctype, status = ui_css().encode(), "text/css; charset=utf-8", 200
            else:
                status, out = respond(ex, url.path, url.query)
                body, ctype = json.dumps(out).encode(), "application/json"
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    return Handler


def serve(ex, port=PORT):
    """The server (127.0.0.1 only); port 0 picks a free one. A thread per
    request: browsers open spare connections that send nothing, which would
    block a one-at-a-time server for good."""
    server = ThreadingHTTPServer(("127.0.0.1", port), handler(ex))
    server.daemon_threads = True
    return server


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)
    ex = Explorer()
    server = serve(ex, args.port)
    print(f"serving http://127.0.0.1:{server.server_address[1]} (sts build {build_hash()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
