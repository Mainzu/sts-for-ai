"""Rounds until the net clearly wins (learned-play Amendment 3, C2): from
round `min` on, a run stops after the first round whose gate is met, else it
goes on to round `n`; `round.json` records the gate check per round, and
only the final round is benched. The gate (Amendment 5, `paired_gate`):
per half, the 95% interval of the net's paired lead over search +
heuristic on the same specs lies above 0, on both halves.

    python scripts/tests/test_stop_rule.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

import bench
import learn


class FakeRun:
    def __init__(self, i):
        self.id = self.model_path = f"m{i}"
        self.written = {}
        self.benched = False

    def _write(self, name, obj):
        self.written[name] = obj

    def save_bench(self, result):
        self.benched = True

    def finish(self, **k):
        pass


def fights(x, n=600):
    """Mock tight-fight results at win rate ~x: spec i is won when its fixed
    fraction is below x, so a stronger mock wins a superset of the specs."""
    return [int((i * 0.6180339887) % 1 < x) for i in range(n)]


def mocked(wins, n=10, low=6, heuristic=0.5):
    """learn.learn (bench_last_only) with self-play, training, tight fights
    and the bench mocked; `wins` {round: win rate, or (train, held_out)}
    (default 0.4), the heuristic's `heuristic`. Returns the runs."""
    def tight_results(ev, search, every, log=None):
        x = heuristic if ev == "heuristic" else wins.get(int(ev[1:]), 0.4)
        x = x if isinstance(x, tuple) else (x, x)
        return {h: fights(v) for h, v in zip(("train", "held_out"), x)}

    def fit(cfg, name, parts, val_id, *a, **k):
        assert not k.get("bench") and not (len(a) > 2 and a[2])  # learn benches, not fit
        fit.n += 1
        return FakeRun(fit.n), 0.1, {d: 0.0 for d, _ in parts}, None
    fit.n = -1
    saved = (learn.tight_results, learn.dataset, learn.fit, bench.bench, bench.load_evaluator, learn.trusted_zone,
             learn.solve_step, learn.tight_cells)
    learn.tight_results, learn.fit = tight_results, fit
    learn.tight_cells = lambda every: None  # mocked fights: each its own cell
    learn.trusted_zone = lambda cfg, model: None  # the puzzles need a real net
    learn.solve_step = lambda *a, **k: None  # the datasets are fake
    learn.dataset = lambda cfg, which, root=None, rnd=0, parent=None, log=None, late=False: f"{which}{rnd}"
    bench.bench, bench.load_evaluator = (lambda ev, quick=False: {}), (lambda p: p)
    cfg = {"name": "x", "search": {"limit": 16}, "rounds": {"n": n, "min": low, "every": 1}, "switches": {}}
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:  # clean_stale stays off main's cache/
            return learn.learn(cfg, bench=True, root=root, log=lambda *a: None, bench_last_only=True)
    finally:
        (learn.tight_results, learn.dataset, learn.fit, bench.bench, bench.load_evaluator, learn.trusted_zone,
         learn.solve_step, learn.tight_cells) = saved


def check(runs, last):
    assert len(runs) == last + 1
    assert [r.benched for r in runs] == [False] * last + [True]
    gates = [r.written["round.json"]["gate"] for r in runs]
    assert gates[0] is None and all(g is not None for g in gates[1:])
    return gates


def test_gate_met_at_round_6_stops_after_6():
    gates = check(mocked({6: 0.7}), 6)
    assert gates[6]["met"] is True and not any(g["met"] for g in gates[1:6])
    h = gates[6]["halves"]["train"]
    assert h["above"] is True and h["n"] == 600 and abs(h["net"][0] - 0.7) < 0.01 and abs(h["heuristic"][0] - 0.5) < 0.01
    assert h["lead"][1] > 0 and abs(h["lead"][0] - (h["net"][0] - h["heuristic"][0])) < 1e-6


def test_gate_first_met_at_round_8_stops_after_8():
    check(mocked({8: 0.7, 9: 0.7}), 8)


def test_never_met_stops_after_round_10():
    gates = check(mocked({}), 10)
    assert not any(g["met"] for g in gates[1:])


def test_met_before_round_6_does_not_stop_early():
    gates = check(mocked({3: 0.7, 5: 0.7, 7: 0.7}), 7)
    assert gates[3]["met"] and gates[5]["met"]


def test_one_half_is_not_enough():
    gates = check(mocked({6: (0.7, 0.5)}), 10)
    assert gates[6]["met"] is False and gates[6]["halves"]["train"]["above"] is True
    assert gates[6]["halves"]["held_out"]["above"] is False


def test_paired_gate():
    """The lead is mean(net - heuristic) per spec, its interval mean +-
    Z * sd / sqrt(n) (sd with n-1); a half passes when it lies above 0."""
    def one(net, heur):
        return learn.gate({"train": net, "held_out": net}, {"train": heur, "held_out": heur})
    same = fights(0.5)
    g = one(same, same)  # identical: lead 0, no spread
    assert g["met"] is False and g["halves"]["train"]["lead"] == [0.0, 0.0, 0.0]
    base = [0] * 100 + [1] * 100  # the heuristic wins half of 200
    for k, ok in ((2, False), (10, True)):  # the net also wins k of its losses
        net = [1] * k + base[k:]
        d = np.array(net) - np.array(base)
        w = bench.Z * d.std(ddof=1) / np.sqrt(len(d))
        g = one(net, base)
        assert np.allclose(g["halves"]["train"]["lead"], [d.mean(), d.mean() - w, d.mean() + w], atol=1e-6)
        assert g["met"] is ok, (k, g)
    swapped = base[::-1]  # equal win rates on different specs
    g = one(swapped, base)
    assert g["met"] is False and g["halves"]["held_out"]["lead"][0] == 0.0 and g["halves"]["held_out"]["lead"][1] < 0
    g = learn.gate({"train": [1] * 10 + base[10:], "held_out": base}, {"train": base, "held_out": base})
    assert g["halves"]["train"]["above"] and not g["met"]  # one half only


def test_cell_gate():
    """Tight fights v2: with cells the lead is the mean of per-cell mean
    differences, its interval over cells; a lead spread over cells passes
    where the same total packed into one cell doesn't; win rates take the
    per-cell interval."""
    cells = [c for c in range(40) for _ in range(10)]  # 40 cells of 10 fights
    base = [k % 2 for k in range(400)]  # the heuristic wins half of every cell
    g = learn.gate({"train": base}, {"train": base}, {"train": cells})
    assert g["halves"]["train"]["lead"] == [0.0, 0.0, 0.0] and not g["met"]
    spread = [1 if k % 10 == 0 and k < 100 else b for k, b in enumerate(base)]  # one more win in cells 0-9
    packed = [1 if k < 20 and k % 2 == 0 else b for k, b in enumerate(base)]  # as many, in cells 0-1
    assert sum(spread) == sum(packed)
    gs = learn.gate({"train": spread}, {"train": base}, {"train": cells})["halves"]["train"]
    gp = learn.gate({"train": packed}, {"train": base}, {"train": cells})["halves"]["train"]
    assert gs["above"] and not gp["above"] and gs["cells"] == gp["cells"] == 40
    assert abs(gs["lead"][0] - gp["lead"][0]) < 1e-6 and gp["lead"][2] - gp["lead"][1] > gs["lead"][2] - gs["lead"][1]
    d = (np.array(packed) - np.array(base)).reshape(40, 10).mean(axis=1)
    w = bench.Z * d.std(ddof=1) / np.sqrt(40)
    assert np.allclose(gp["lead"], [d.mean(), d.mean() - w, d.mean() + w], atol=1e-6)
    r = learn.win_rates({"train": packed}, {"train": cells})["train"]
    m = np.array(packed).reshape(40, 10).mean(axis=1)
    assert np.allclose(r, [m.mean(), m.mean() - bench.Z * m.std(ddof=1) / np.sqrt(40),
                           m.mean() + bench.Z * m.std(ddof=1) / np.sqrt(40)], atol=1e-6)


def test_every_keeps_cells():
    """Thinning by n keeps every cell and every n-th seed within each."""
    import bench_sets
    fake = {"train": [{"cell": c, "seed": c * 100 + k} for c in range(5) for k in range(7)],
            "held_out": [{"cell": c, "seed": c * 100 + k} for c in range(3) for k in range(2)]}
    saved = bench_sets.load_set
    bench_sets.load_set = lambda name, bench=None: fake
    try:
        assert learn.tight_specs(1) == fake
        got = learn.tight_specs(3)
        assert [s["seed"] for s in got["train"]] == [c * 100 + k for c in range(5) for k in (0, 3, 6)]
        assert {s["cell"] for s in learn.tight_specs(20)["held_out"]} == {0, 1, 2}
        assert learn.tight_cells(3)["train"] == [c for c in range(5) for _ in range(3)]
    finally:
        bench_sets.load_set = saved


def test_without_min_every_round_runs():
    """No `min` (configs before Amendment 3): all n rounds, last benched."""
    check(mocked({1: 0.9, 2: 0.9}, n=3, low=None), 3)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(len(tests), "passed")
