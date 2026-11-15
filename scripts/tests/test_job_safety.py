"""Jobs that hang or run out of memory (review 2026-10-31): Rust searches
keep to a job's thread cap, self-play results drop the recorded states
nobody reads, and long label runs save their progress so a dead worker
doesn't lose hours.

Run with `python scripts/tests/test_job_safety.py` or with pytest.
"""

import gzip
import hashlib
import json
import os
import sys
import tempfile
import types

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import bench  # noqa: E402
import depth_paired  # noqa: E402
import learn  # noqa: E402
import registry  # noqa: E402
import selfplay  # noqa: E402
import sts  # noqa: E402
import stsnet  # noqa: E402

CONFIG = {"name": "tiny", "sample_seed": 5, "search": {"limit": selfplay.LIMIT, "threads": 2}}


class _Env:
    """Sets (or with None, unsets) STS_JOB_THREADS for a block."""

    def __init__(self, value):
        self.value = value

    def __enter__(self):
        self.old = os.environ.pop("STS_JOB_THREADS", None)
        if self.value is not None:
            os.environ["STS_JOB_THREADS"] = self.value

    def __exit__(self, *exc):
        os.environ.pop("STS_JOB_THREADS", None)
        if self.old is not None:
            os.environ["STS_JOB_THREADS"] = self.old


def _captured_run_kwargs(call):
    """The keyword arguments of every `sts.run` call `call()` makes (no game is played)."""
    real, seen = sts.run, []

    def fake(agent, specs, **kw):
        seen.append(kw)
        return [{"states": [], "actions": []} for _ in specs]
    sts.run = fake
    try:
        call()
    finally:
        sts.run = real
    return seen


def test_rust_searches_keep_to_the_job_thread_cap():
    spec = {"encounter": "cultist", "deck": sts.starter_deck("ironclad"), "seed": 1, "hp": None,
            "character": "ironclad"}
    calls = {
        "bench": lambda: bench.run_specs([spec]),
        "registry": lambda: registry.play([("cultist", spec["deck"], 1)], {"search": {"limit": selfplay.LIMIT}}),
    }
    for name, call in calls.items():
        with _Env("3"):
            assert [kw.get("threads") for kw in _captured_run_kwargs(call)] == [3], name
        with _Env(None):
            assert all("threads" not in kw for kw in _captured_run_kwargs(call)), name
        with _Env("0"):
            assert all("threads" not in kw for kw in _captured_run_kwargs(call)), name
    with _Env("3"):  # an explicit count, or a Python net's, wins
        assert _captured_run_kwargs(lambda: bench.run_specs([spec], search={"limit": 8, "threads": 5}))[0]["threads"] == 5
        py_net = lambda: registry.play([("cultist", spec["deck"], 1)], {}, evaluator=lambda batch: None)  # noqa: E731
        assert _captured_run_kwargs(py_net)[0]["threads"] == stsnet.NET_THREADS


def test_selfplay_results_drop_states_and_dataset_is_unchanged():
    """Results carry no recorded states unless asked, and the dataset is
    byte for byte what the old code wrote (results with states, one string
    hashed and gzipped)."""
    specs, groups = selfplay.make_specs(20, 11, selfplay.train_deck)
    assert len(specs) == 60
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as a, \
            tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as b:
        ds_old, kept = registry.selfplay(specs, groups, CONFIG, root=a, keep_states=True)
        ds_new, lean = registry.selfplay(specs, groups, CONFIG, root=b)
        assert all("states" in r for r in kept) and not any("states" in r for r in lean)
        assert ds_old == ds_new
        games = registry.records(specs, groups, kept, CONFIG)
        body = "".join(json.dumps(g, sort_keys=True) + "\n" for g in games).encode()
        assert registry.load_manifest(ds_new, b)["games_sha256"] == hashlib.sha256(body).hexdigest()
        path = os.path.join(a, "games.jsonl.gz")  # gzip's header holds the file's name
        with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as f:
            f.write(body)
        with open(path, "rb") as f:
            old = f.read()
        with open(os.path.join(registry.datasets_dir(b), ds_new, "games.jsonl.gz"), "rb") as f:
            assert f.read() == old


# --- teacher labels saved in parts -------------------------------------------

TEACH_CFG = {"name": "distill-t", "mode": "effects", "n_train": 3, "n_val": 1, "train_seed": 71, "val_seed": 72,
             "search": {"limit": selfplay.LIMIT}, "seed": 0, "rounds": {"n": 0, "temperature": 0.05, "every": 100},
             "switches": {}, "solve_games": 0, "solve_games0": 0,
             "teacher": {"turns": 2, "states": 20, "groups": ["elite", "boss"], "max_nodes": 400000, "sample_k": 4,
                         "seed": 0, "threads": 1}}


def _fake_examples(n_dec=30):
    """A dataset-like object: per decision a state row (option -1, codec
    bytes) and two option rows; elite and boss groups alternate."""
    rows = [(k, o) for k in range(n_dec) for o in (-1, 0, 1)]
    d = types.SimpleNamespace(decision=np.array([k for k, _ in rows], np.int64),
                              option=np.array([o for _, o in rows], np.int64),
                              group=np.array([1 + k % 2 for k, _ in rows], np.int64),
                              codec_len=np.ones(len(rows), np.int64),
                              rank_value=np.linspace(0, 1, len(rows)).astype(np.float32))
    d.codec_bytes = lambda i: bytes([i % 256])
    return d


def _teach(root, fail_after=None):
    """`learn.teach` on a fake dataset with a fake per-state search: (record
    or the exception, example indices searched). `fail_after`: the search
    raises on that call, as a dying worker would."""
    seen = []

    def one(job):
        _, code, seed, _ = job
        if fail_after is not None and len(seen) == fail_after:
            raise RuntimeError("worker died")
        seen.append(code[0])
        return [seed % 7 / 7.0, seed % 5 / 5.0 + 1e-9], seed % 3 == 0
    real = (registry.examples, registry.load_manifest, registry.Run, learn.teacher_path, learn._teach_one,
            learn.TEACHER_PARTIAL_N)
    registry.examples = lambda *a, **k: _fake_examples()
    registry.load_manifest = lambda *a, **k: {"parent_model": "run0"}
    registry.Run = lambda p: types.SimpleNamespace(model_path=p)
    learn.teacher_path = lambda cfg, ds, root=None: os.path.join(root, "teacher-k.npz")
    learn._teach_one = one
    learn.TEACHER_PARTIAL_N = 3
    try:
        try:
            out = learn.teach(TEACH_CFG, "ds", 1, root=root, log=lambda *_: None)
        except RuntimeError as e:
            out = e
    finally:
        (registry.examples, registry.load_manifest, registry.Run, learn.teacher_path, learn._teach_one,
         learn.TEACHER_PARTIAL_N) = real
    return out, seen


def _final(root):
    with np.load(os.path.join(root, "teacher-k.npz")) as z:
        rec = json.loads(str(z["record"]))
        rec.pop("minutes")
        return {k: z[k] for k in ("idx", "cut", "len", "start", "values")}, rec


def test_teacher_resumes_from_its_partial_file():
    with tempfile.TemporaryDirectory() as whole, tempfile.TemporaryDirectory() as cut:
        rec, all_seen = _teach(whole)
        assert not os.path.exists(os.path.join(whole, "teacher-k.npz.partial.npz"))
        assert len(all_seen) == 20 and not rec["cached"]

        err, first = _teach(cut, fail_after=7)
        assert isinstance(err, RuntimeError) and len(first) == 7
        assert not os.path.exists(os.path.join(cut, "teacher-k.npz"))
        assert os.path.exists(os.path.join(cut, "teacher-k.npz.partial.npz"))
        rec2, second = _teach(cut)
        assert sorted(second) == sorted(set(all_seen) - set(first))  # only the missing decisions
        assert not os.path.exists(os.path.join(cut, "teacher-k.npz.partial.npz"))

        (a, ra), (b, rb) = _final(whole), _final(cut)
        assert ra == rb
        for k in a:
            assert a[k].dtype == b[k].dtype and np.array_equal(a[k], b[k]), k


# --- depth_paired's guarded fights saved per fight -----------------------------

def test_guarded_fights_resume_from_partial_lines():
    specs = [{"deck": sts.starter_deck("ironclad"), "encounter": "cultist", "seed": s, "hp": 80,
              "character": "ironclad"} for s in range(3)]
    two = {"limit": selfplay.LIMIT, "turns": 2, "sample_k": 2, "max_nodes": 2000}
    with tempfile.TemporaryDirectory() as d:
        part = os.path.join(d, "out.json.partial.jsonl")
        want = depth_paired.run_guarded(specs, two, -1.0, "heuristic", 1, part)
        with open(part, encoding="utf-8") as f:
            lines = f.read().splitlines()
        assert len(lines) == 3
        keep = next(line for line in lines if json.loads(line)["i"] == 0)
        with open(part, "w", encoding="utf-8") as f:
            f.write(keep + "\n" + lines[1][:20])  # fight 0 done, a line cut short
        got = depth_paired.run_guarded(specs, two, -1.0, "heuristic", 1, part)
        assert got == want
        assert sorted(r["i"] for r in _rows(part)) == [0, 1, 2]  # fights 1 and 2 played again, fight 0 not
        # other settings don't reuse these lines: fight 0 is played again
        depth_paired.run_guarded(specs[:1], two, 0.5, "heuristic", 1, part)
        assert sorted(r["i"] for r in _rows(part)) == [0, 0, 1, 2]


def _rows(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(f"{len(tests)} passed")
