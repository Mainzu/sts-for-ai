"""The exact solver through the binding (`sts.solve`, `SolveStore`,
`SolvedDb`, `Combat.encode` / `decode`): exact values against an
independent brute force, and root options grouped as `search` groups them.
Run with `python scripts/tests/test_solve.py` or with pytest."""

import os
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench_sets  # noqa: E402
import sts  # noqa: E402

TAIL_NODES = 20_000  # the solver holds ~21 KB per node: 50k nodes took 1.1 GB
_GAMES = []


def games():
    """Search + heuristic games (recorded) on the tight specs, both halves."""
    if not _GAMES:
        tight = bench_sets.load_set("tight")
        specs = tight["train"] + tight["held_out"]
        by = {}
        for i, s in enumerate(specs):
            by.setdefault((s["hp"], s["character"]), []).append(i)
        for (hp, ch), idx in sorted(by.items()):
            res = sts.run("search", [(specs[i]["encounter"], specs[i]["deck"], specs[i]["seed"]) for i in idx],
                          limit=bench_sets.LIMIT, hp=hp, character=ch, record=True)
            _GAMES.extend(res)
    return _GAMES


def tails(max_nodes=TAIL_NODES):
    """(Combat, solve result) for each game's decisions from the last one
    back to the first unsolvable one, skipping single-option decisions."""
    for g in games():
        for c in reversed(g["states"]):
            if len(c.options(bench_sets.LIMIT)) < 2:
                continue
            r = sts.solve(c, max_nodes=max_nodes)
            if r is None:
                break
            yield c, r


def living_monsters(c):
    return [int(m) for m in re.findall(r"^\s+\[\d\] .*? HP (\d+)/\d+", c.render(), re.M) if int(m) > 0]


def brute_value(c, memo):
    """Exact value by plain recursive expectimax over `Combat.options`."""
    if c.is_over():
        return c.score()
    key = c.encode()
    if key not in memo:
        memo[key] = max(option_value(o, memo) for o in c.options(10**6))
    return memo[key]


def option_value(o, memo):
    _, kind, outs = o
    assert kind != "divergent", "every event listed at limit 10**6"
    return sum(p * brute_value(child, memo) for p, child in outs)


def test_solve_matches_brute_force():
    """30 tiny tail positions (one monster under 15 HP, draw pile of at most
    3 cards): the solver's option values equal a brute force's to 1e-9."""
    tiny = [c for g in games() for c in g["states"]
            if len(hp := living_monsters(c)) == 1 and hp[0] < 15 and sum(c.piles()["draw"].values()) <= 3]
    with ThreadPoolExecutor(8) as pool:
        solved = list(pool.map(lambda c: sts.solve(c, max_nodes=5_000), tiny))  # 8 at once: ~21 KB per node each
    cases = [(c, r) for c, r in zip(tiny, solved) if r is not None and len(r["options"]) >= 2][:30]
    assert len(cases) == 30, f"only {len(cases)} tiny positions"
    for c, r in cases:
        memo = {}
        brute = [option_value(o, memo) for o in c.options(10**6)]
        assert len(brute) == len(r["options"])
        for b, (_, v) in zip(brute, r["options"]):
            assert abs(b - v) <= 1e-9, (b, v, c.render())


def test_solve_groups_like_search():
    """On 200 solved decisions, the root options' action groups equal
    `sts.search`'s options exactly (actions and order)."""
    n = 0
    for c, r in tails():
        ref = sts.search(c, limit=bench_sets.LIMIT)
        assert [list(a) for a, *_ in r["options"]] == [list(a) for a, _ in ref["options"]]
        n += 1
        if n == 200:
            return
    raise AssertionError(f"only {n} solved decisions")


def test_binding_store_and_db():
    """A memory store and a database store give the same values as no
    store; a reopened database answers a recorded root as one hit; its
    position reads back; `decode(encode(c))` is the same state."""
    c, r = next(tails())
    for d in (False, True):
        cold = sts.solve(c, distribution=d)
        mem = sts.solve(c, distribution=d, store=sts.SolveStore(min_nodes=0))
        assert cold["options"] == mem["options"]
        if d:
            for _, v, (loss, wins) in cold["options"]:
                assert abs(loss + sum(p for _, p in wins) - 1) <= 1e-9
                assert abs(sum(p * (2 - k / 100) for k, p in wins) - v) <= 1e-9
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "solved.sqlite")
        db = sts.SolvedDb(path)
        store = sts.SolveStore(min_nodes=0, db=db)
        first = sts.solve(c, store=store)
        assert store.add_position(c, "bench", "{}", "", 3, 0, 0.25)
        again = sts.solve(c, store=sts.SolveStore(db=sts.SolvedDb(path)))
        assert again["options"] == first["options"] and again["hits"] == 1 and again["nodes"] == 0
        rows = sts.SolvedDb(path).positions("bench")
        assert len(rows) == 1 and rows[0]["options"] == first["options"] and rows[0]["step"] == 3
        assert sts.Combat.decode(rows[0]["state"]).encode() == c.encode()
        st = sts.SolvedDb(path).stats()
        assert st["positions"] == 1 and st["versions"][0][3]
        del store, db  # closes the connection, so the folder can go
    back = sts.Combat.decode(c.encode())
    assert back.render() == c.render() and back.encode() == c.encode()
    assert sts.solve(sts.Combat(sts.starter_deck("ironclad"), "jaw_worm", seed=1), max_nodes=1_000) is None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(len(tests), "passed")
