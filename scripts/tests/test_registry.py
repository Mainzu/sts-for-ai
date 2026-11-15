"""Tests for the learned-play registry (datasets, feature caches, runs).
Run with `python scripts/tests/test_registry.py` or with pytest."""

import csv
import json
import os
import sys
import tempfile
import time

import numpy as np
import sts

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import registry  # noqa: E402
import selfplay  # noqa: E402
import bench_compare  # noqa: E402
from stsnet import Dataset  # noqa: E402

CONFIG = {"name": "tiny", "sample_seed": 5, "search": {"limit": selfplay.LIMIT}}


def tiny_specs():
    specs, groups = selfplay.make_specs(2, 11, selfplay.train_deck)
    return specs, groups


def test_replay_reencodes_identically():
    specs, groups = tiny_specs()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        ds, results = registry.selfplay(specs, groups, CONFIG, root=root, keep_states=True)
        # Encoding at generation time, from the live recorded states.
        rng = np.random.default_rng(CONFIG["sample_seed"])
        states, target, grp = selfplay.sample_states(results, groups, rng)
        live = Dataset.from_batches([selfplay.features("effects").encode(states)], target, grp)
        # Encoding later, by replaying the stored game records.
        cached = registry.examples(ds, "effects", root=root)
        again = registry.examples(ds, "effects", root=root)  # from the cache file
        for d in (cached, again):
            assert len(d) == len(live) > 0
            for k in Dataset.FIELDS:
                np.testing.assert_array_equal(getattr(d, k), getattr(live, k), err_msg=k)
        assert os.path.exists(registry.cache_path(ds, "effects", root=root))


def test_dataset_is_never_overwritten_and_id_is_manifest_hash():
    specs, groups = tiny_specs()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        a, _ = registry.selfplay(specs, groups, CONFIG, root=root)
        path = os.path.join(registry.datasets_dir(root), a, "games.jsonl.gz")
        before = os.path.getmtime(path)
        b, _ = registry.selfplay(specs, groups, CONFIG, root=root)
        assert a == b and os.path.getmtime(path) == before
        m = registry.load_manifest(a, root=root)
        assert registry.manifest_id(m) == a
        for k in ("engine_commit", "rules_version", "config", "parent_model", "games_sha256", "n_games"):
            assert k in m, k


def test_streamed_selfplay_writes_the_same_dataset():
    """keep_results=False (learn.dataset's pool) plays and writes a chunk at
    a time: the same id and bytes as the list path, and a second stream of
    an existing dataset leaves no temporary folder."""
    specs, groups = tiny_specs()
    chunk = registry.PLAY_CHUNK
    registry.PLAY_CHUNK = 2  # several chunks over the 6 games
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as a, \
                tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as b:
            listed, _ = registry.selfplay(specs, groups, CONFIG, root=a)
            streamed, res = registry.selfplay(specs, groups, CONFIG, root=b, keep_results=False)
            assert streamed == listed and res is None
            read = lambda r: open(os.path.join(registry.datasets_dir(r), listed, "games.jsonl.gz"), "rb").read()
            assert read(a) == read(b)
            assert registry.load_manifest(listed, a) == registry.load_manifest(listed, b)
            assert registry.selfplay(specs, groups, CONFIG, root=b, keep_results=False)[0] == listed
            assert os.listdir(registry.datasets_dir(b)) == [listed]
    finally:
        registry.PLAY_CHUNK = chunk


def test_dataset_write_retries_a_briefly_locked_folder():
    """Windows refuses to rename a folder while another process (antivirus,
    indexer) has a file in it open: the B4 sweep died with PermissionError
    on the dataset folder's final rename. A few failed renames are retried."""
    real, calls = os.replace, []

    def flaky(src, dst):
        calls.append(src)
        if len(calls) <= 2:
            raise PermissionError(5, "Access is denied")
        real(src, dst)
    games = [{"actions": [], "outcome": {}}]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        registry.os.replace = flaky
        try:
            ds = registry.write_dataset(games, CONFIG, root=root, rules="r")
        finally:
            registry.os.replace = real
        assert len(calls) == 3
        assert os.path.exists(os.path.join(registry.datasets_dir(root), ds, "manifest.json"))


def test_other_rules_version_is_refused():
    specs, groups = tiny_specs()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        games = registry.records(specs[:1], groups[:1], registry.play(specs[:1], CONFIG))
        ds = registry.write_dataset(games, CONFIG, root=root, rules="0000000000000000")
        try:
            registry.examples(ds, "effects", root=root)
        except registry.RulesVersionError as e:
            msg = str(e)
            assert ds in msg and "0000000000000000" in msg and registry.rules_version() in msg
        else:
            raise AssertionError("a dataset from other rules was replayed")


def test_two_runs_make_two_folders_and_index_lines():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        ids = []
        for _ in range(2):
            run = registry.Run.create("tiny", {"name": "tiny", "switches": {"targets": False}}, ["abc"], root=root)
            run.save_curves({"train": [1.0, 0.5], "val": [1.1, 0.6]})
            run.finish(val_mse=0.6)
            ids.append(run.id)
        assert ids[0] != ids[1]
        assert all(os.path.isdir(os.path.join(registry.runs_dir(root), i)) for i in ids)
        with open(os.path.join(registry.runs_dir(root), "index.csv"), newline="") as f:
            rows = list(csv.DictReader(f))
        assert [r["run"] for r in rows] == ids
        info = json.load(open(os.path.join(registry.runs_dir(root), ids[0], "run.json")))
        assert info["datasets"] == ["abc"] and info["commit"]


def test_cache_evicts_oldest_past_cap():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        now = time.time()
        for i, name in enumerate(["a", "b", "c", "d"]):
            p = os.path.join(d, f"{name}-effects.npz")
            with open(p, "wb") as f:
                f.write(b"x" * 100)
            os.utime(p, (now - 100 + i, now - 100 + i))  # a oldest, d newest
        with open(os.path.join(d, "a-effects.npz.games.npy"), "wb") as f:  # curve's sidecar goes with its npz
            f.write(b"x")
        os.makedirs(os.path.join(d, "explore"))  # the explorer's own folder: never a cache to evict
        os.utime(os.path.join(d, "explore"), (now - 1000, now - 1000))
        registry.evict(d, cap_bytes=250)
        assert sorted(os.listdir(d)) == ["c-effects.npz", "d-effects.npz", "explore"]
        os.rmdir(os.path.join(d, "explore"))
        # The file just written survives even when it alone is over the cap.
        registry.evict(d, cap_bytes=50, keep=os.path.join(d, "c-effects.npz"))
        assert os.listdir(d) == ["c-effects.npz"]


def test_mapped_cache_not_evicted():
    """A v7 cache another object still maps is left whole by eviction (not
    half deleted); once let go, it is evicted."""
    import gc
    from stsnet import DatasetWriter
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        n = 5
        ds = Dataset(np.zeros((n, 3), np.float32), np.zeros((n, 2, 4), np.float32), np.zeros((n, 2), np.float16),
                     np.ones(n * 2, np.float32), np.zeros(n * 2, np.int8), np.arange(n) * 2, np.full(n, 2),
                     np.zeros((0, 2), np.float16), np.zeros(0, np.int16), np.zeros(0, np.int8), np.zeros(n, np.int64),
                     np.zeros(n, np.int64), np.zeros(n, np.float32))
        path = os.path.join(d, "ab12-effects_rows-v7")
        w = DatasetWriter(path)
        w.append(ds)
        w.close()
        files = sorted(os.listdir(path))
        mapped = Dataset.load(path)
        registry.evict(d, cap_bytes=0)
        assert sorted(os.listdir(path)) == files and float(mapped.player.sum()) == 0.0
        del mapped
        gc.collect()
        registry.evict(d, cap_bytes=0)
        assert os.listdir(d) == []


def test_stale_tmp_cleaned():
    """Temporary caches left by a process that no longer runs (a crashed
    round's exact examples, a half-built cache) are deleted at the start of
    a run; this process's own and finished caches stay."""
    import subprocess
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        names = [f"exact.tmp{dead.pid}-0", f"ab12-effects_rows-v7.tmp{dead.pid}", f"exact.tmp{os.getpid()}-3",
                 "ab12-effects_rows-v7"]
        for n in names:
            os.makedirs(os.path.join(d, n, "inner"))
        registry.clean_stale(d)
        assert sorted(os.listdir(d)) == sorted(names[2:])
        assert registry.pid_alive(os.getpid()) and not registry.pid_alive(dead.pid)


def test_bench_compare_accepts_run_ids():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        run = registry.Run.create("tiny", {"name": "tiny"}, [], root=root)
        res = {"version": 1, "sets": {}}
        run.save_bench(res)
        run.finish()
        other = os.path.join(root, "old.json")
        json.dump({"version": 0, "sets": {}}, open(other, "w"))
        loaded, warnings = bench_compare.load_results([run.id, other], runs_root=registry.runs_dir(root))
        assert [n for n, _ in loaded] == [run.id, "old"]
        assert warnings and "version" in warnings[0]


def test_learn_writes_through_the_registry():
    import learn
    cfg = {"name": "smoke", "mode": "effects", "n_train": 2, "n_val": 1, "train_seed": 21, "val_seed": 22,
           "search": {"limit": selfplay.LIMIT}, "seed": 0, "switches": {}, "rounds": {"n": 0}}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        [a] = learn.learn(cfg, root=root, log=lambda *_: None)
        [b] = learn.learn(cfg, root=root, log=lambda *_: None)  # reuses both datasets
        assert len(os.listdir(registry.datasets_dir(root))) == 2
        ia = json.load(open(os.path.join(a.path, "run.json")))
        ib = json.load(open(os.path.join(b.path, "run.json")))
        assert ia["datasets"] == ib["datasets"] and a.id != b.id
        curves = json.load(open(os.path.join(a.path, "curves.json")))
        assert len(curves["train"]) == len(curves["val"]) > 0
        assert os.path.exists(a.model_path)


def test_replay_checks_outcome():
    """`replay` accepts recorded official games (normal, no-death, a branch
    game, one stopped at the turn limit) and raises when the replayed game
    ends other than its record says."""
    def recorded(agent, specs, config=None, **kw):
        res = sts.run(agent, specs, record=True, limit=selfplay.LIMIT, threads=2, **kw)
        return registry.records(specs, [0] * len(specs), res, config)

    specs = [("jaw_worm", ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"], 3)]
    normal = recorded("search", specs)[0]
    no_death = recorded("search", specs, {"no_death": True}, no_death=True)[0]
    branch = recorded("search", specs, forced=[[registry.decode_action(a) for a in normal["actions"][:2]]])[0]
    branch["branch_at"] = 1
    stalled = recorded("greedy", [("jaw_worm", ["Defend"] * 10, 1, 30000)])[0]
    assert stalled["outcome"]["turns"] == 101 and not stalled["outcome"]["won"]
    for g in (normal, no_death, branch, stalled):
        registry.replay(g)
    bad = {**normal, "outcome": {**normal["outcome"], "won": not normal["outcome"]["won"]}}
    try:
        registry.replay(bad)
    except ValueError as e:
        assert "jaw_worm" in str(e)
    else:
        raise AssertionError("a replay that ends other than its record was accepted")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(f"{len(tests)} passed")
