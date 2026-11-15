"""Progress reporting (scripts/progress.py) and the chunked play it reports:
plain-python asserts; run directly."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import bench  # noqa: E402
import bench_sets  # noqa: E402
import registry  # noqa: E402
import selfplay  # noqa: E402
from progress import Progress  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_log_lines():
    """In a log: a line after 30 s or another 10% done, whichever first,
    none at 100% before the closing line, which gives the total time."""
    clock, lines = Clock(), []
    p = Progress("phase", 100, lines.append, tty=False, clock=clock)
    clock.t = 1
    p.update(5)  # 5%, 1 s: nothing
    assert lines == []
    clock.t = 2
    p.update(5)  # 10%
    assert len(lines) == 1 and "phase: 10/100 (10%)" in lines[0] and "ETA" in lines[0]
    clock.t = 40
    p.update(1)  # 11%, 38 s after the last line
    assert len(lines) == 2 and "11/100" in lines[1]
    clock.t = 41
    p.update(89)  # done: the closing line reports it
    assert len(lines) == 2
    clock.t = 125
    p.close()
    p.close()
    assert lines[-1] == "  phase: 100/100 done in 2m05s" and len(lines) == 3
    quiet = []
    q = Progress("epoch", 4, quiet.append, tty=False, clock=clock)
    q.update(4)
    q.close(final=False)
    assert quiet == []


def _canon(results):
    return json.dumps(results, sort_keys=True, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))


def test_chunked_play_is_identical():
    """Self-play (heuristic and a net, exploring, branch games' forced
    openings) and the tight fights played a few games per `sts.run` call
    give the same records and results as one call."""
    specs, groups = selfplay.make_specs(3, 21, selfplay.varied_deck, hp_fn=selfplay.varied_hp)
    config = {"search": {"limit": selfplay.LIMIT}, "explore": 0.05}
    net = bench.load_evaluator(os.path.join(registry.ROOT, "models", "value_effects.pt"))
    chunk = registry.PLAY_CHUNK
    try:
        for ev in ({}, {"evaluator": net.evaluator, "features": net.features}):
            got = []
            for n in (len(specs), 2):
                registry.PLAY_CHUNK = n
                res = registry.play(specs, config, log=lambda *_: None, **ev)
                forced = [list(r["actions"][:1]) for r in res]
                got.append((registry.records(specs, groups, res, config),
                            _canon(registry.play(specs, config, forced=forced, log=lambda *_: None, **ev))))
            assert got[0] == got[1]
        tight = bench.every(bench_sets.load_set("tight")["train"], 100)
        whole = bench.run_specs(tight, None)
        parts = [r for i in range(0, len(tight), 3) for r in bench.run_specs(tight[i:i + 3], None)]
        assert len(tight) > 6 and _canon(whole) == _canon(parts)
    finally:
        registry.PLAY_CHUNK = chunk


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(f"{len(tests)} passed")
