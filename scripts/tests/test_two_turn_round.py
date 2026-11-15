"""Tests for the two-turn self-play round (docs/specs/two-turn-round.md).
Run with `python scripts/tests/test_two_turn_round.py` (plain asserts; every
`test_*` function runs) or with pytest."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import json
import shutil
import tempfile

import pytest

import action_text  # noqa: E402
import depth_paired  # noqa: E402
import registry  # noqa: E402
import selfplay  # noqa: E402
import sts  # noqa: E402
import two_turn_games  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
TWO = {"limit": 16, "turns": 2, "sample_k": 4, "max_nodes": 2000}


def _spec():
    cwd = os.getcwd()
    os.chdir(ROOT)  # depth_paired.fights reads data/bench/<set>.json by a relative path
    try:
        return depth_paired.fights("held_out", ["elite"], 1)[0]
    finally:
        os.chdir(cwd)


def test_record_actions_replay():
    """With `record`, the guarded fight returns its actions as text that
    replays from a fresh combat to the same outcome; without it the result
    has no `actions` and `row_key` is unchanged."""
    s = _spec()
    job = (s, TWO, -1.0, "heuristic", 0, 3, True, True)
    plain = depth_paired.guarded_fight(job)
    assert "actions" not in plain
    rec = depth_paired.guarded_fight(job + (True,))
    acts = rec["actions"]
    assert isinstance(acts, list) and acts and all(isinstance(a, str) for a in acts)
    assert len(acts) == rec["decisions"]
    assert {k: v for k, v in rec.items() if k != "actions"} == plain
    c = sts.Combat(s["deck"], s["encounter"], seed=s["seed"], hp=s["hp"], character=s["character"])
    for t in acts:
        assert not c.is_over()
        c.step(action_text.decode_in(c, t))
    assert (c.is_over() and c.won(), c.player_hp(), c.turn()) == (rec["won"], rec["hp_end"], rec["turns"])
    # Partial-file keys don't know about recording: old rows still match.
    assert depth_paired.row_key(TWO, -1.0, "heuristic", 0, True, True) == \
        depth_paired.row_key(TWO, -1.0, "heuristic", seed_per_turn=True, step_line=True)


def _fake_run_guarded(calls):
    """A stand-in for depth_paired.run_guarded: every fight won on turn 3,
    actions ["End"]; records how often it was called."""
    def fake(specs, two, margin, evaluator, threads, partial=None, **kw):
        calls.append({"n": len(specs), "two": two, "margin": margin, "evaluator": evaluator, **kw})
        if partial:
            open(partial, "a").close()  # the resume log the real one appends to
        return [{"won": True, "score": 1.0, "turns": 3, "decisions": 1, "cut": 0, "override": 0,
                 "outside": 0, "hp_start": s["hp"], "hp_end": s["hp"], "actions": ["End"]} for s in specs]
    return fake


def test_dataset_specs():
    """The two-turn dataset: elite and boss fights only, varied training decks
    at run-like HP, no values, the documented config; a second call reuses it."""
    root = tempfile.mkdtemp(prefix="twoturn-")
    calls = []
    old, depth_paired.run_guarded = depth_paired.run_guarded, _fake_run_guarded(calls)
    try:
        ds = two_turn_games.dataset("fake.pt@hpe0.01", 2, 5, "two", 1, root=root, log=lambda *a: None)
        games = registry.load_games(ds, root)
        assert len(games) == 4
        assert all(g["encounter"] in {"gremlin_nob", "lagavulin", "three_sentries", "slime_boss"} for g in games)
        assert [g["group"] for g in games] == [1, 1, 2, 2]
        pool = set(selfplay.TRAIN_POOL) | set(selfplay.STARTER)
        for g in games:
            extra = list(g["deck"])
            for c in selfplay.STARTER:
                extra.remove(c)
            assert 3 <= len(extra) <= 15 and set(extra) <= pool and not (set(g["deck"]) & selfplay.HELD_OUT_ALL)
            assert 0.4 * selfplay.max_hp() <= g["hp"] <= selfplay.max_hp()
            assert g["values"] is None and g["actions"] == ["End"]
            assert set(g["outcome"]) == {"won", "hp_start", "hp_end", "turns", "score"}
        m = registry.load_manifest(ds, root)
        assert m["config"] == {"kind": "two-turn games", "player": "fake.pt@hpe0.01", "depth": "two",
                               "search": {"limit": 16, "turns": 2, "sample_k": 4, "max_nodes": 400000,
                                          "line_seed": True, "step_line": True},
                               "groups": ["elite", "boss"], "setups": "varied", "hp": [0.4, 1.0],
                               "n_per_group": 2, "seed": 5, "character": "ironclad"}
        assert m["parent_model"] is None and m["n_games"] == 4
        assert len(calls) == 1 and calls[0]["seed_per_turn"] and calls[0]["step_line"] and calls[0]["record"]
        assert calls[0]["margin"] == -1.0 and calls[0]["two"]["max_nodes"] == 400000
        assert not [n for n in os.listdir(registry.cache_dir(root)) if n.endswith(".partial.jsonl")]  # resume log gone
        again = two_turn_games.dataset("fake.pt@hpe0.01", 2, 5, "two", 1, root=root, log=lambda *a: None)
        assert again == ds and len(calls) == 1
        # A smoke node cap is part of the identity: another dataset.
        smoke = two_turn_games.dataset("fake.pt@hpe0.01", 2, 5, "two", 1, root=root, log=lambda *a: None,
                                       max_nodes=2000)
        assert smoke != ds and registry.load_manifest(smoke, root)["config"]["search"]["max_nodes"] == 2000
    finally:
        depth_paired.run_guarded = old
        shutil.rmtree(root, ignore_errors=True)


def test_dataset_encounters():
    """`encounters`: boss fights only, those encounters in turn, the full
    call's boss decks, seeds and HP; part of the identity only when given;
    an unknown name raises before any play."""
    plain, pg = two_turn_games.specs_for(4, 5)
    boss = [s for s, g in zip(plain, pg) if selfplay.GROUPS[g] == "boss"]
    specs, groups = two_turn_games.specs_for(4, 5, ["the_guardian", "hexaghost"])
    assert [s[0] for s in specs] == ["the_guardian", "hexaghost"] * 2 and set(groups) == {2}
    assert [s[1:] for s in specs] == [s[1:] for s in boss]
    with pytest.raises(ValueError):
        two_turn_games.specs_for(2, 5, ["no_such_boss"])
    assert "encounters" not in two_turn_games.config_of("p", 2, 5, "one")
    root = tempfile.mkdtemp(prefix="twoturn-")
    calls = []
    old, depth_paired.run_guarded = depth_paired.run_guarded, _fake_run_guarded(calls)
    try:
        ds = two_turn_games.dataset("fake.pt@hpe0.01", 3, 5, "two", 1, root=root, log=lambda *a: None,
                                    encounters=["the_guardian", "hexaghost"])
        games = registry.load_games(ds, root)
        assert [g["encounter"] for g in games] == ["the_guardian", "hexaghost", "the_guardian"]
        assert [g["group"] for g in games] == [2, 2, 2]
        cfg = registry.load_manifest(ds, root)["config"]
        assert cfg["groups"] == ["boss"] and cfg["encounters"] == ["the_guardian", "hexaghost"]
        assert two_turn_games.dataset("fake.pt@hpe0.01", 3, 5, "two", 1, root=root, log=lambda *a: None) != ds
    finally:
        depth_paired.run_guarded = old
        shutil.rmtree(root, ignore_errors=True)


def test_held_out_decks():
    """`decks="held-out"`: starter + 3-15 cards from the whole pool, at least
    two held out (check 6 or 9), Demon Form in at least a third of the decks;
    `setups` in the identity; the default identity unchanged; an unknown
    kind raises."""
    specs, groups = two_turn_games.specs_for(300, 7, decks="held-out")
    plain, _ = two_turn_games.specs_for(300, 7)
    assert [s[0] for s in specs] == [s[0] for s in plain] and [s[2] for s in specs] == [s[2] for s in plain]
    held = selfplay.HELD_OUT_ALL | set(sts.held_out_card_names())
    pool = set(sts.deck_card_names()) | set(sts.held_out_card_names())
    for s in specs:
        extra = list(s[1])
        for c in selfplay.STARTER:
            extra.remove(c)
        assert 3 <= len(extra) <= 15 and set(extra) <= pool and sum(c in held for c in extra) >= 2
    df = sum(any(c.rstrip("+") == "Demon Form" for c in s[1]) for s in specs) / len(specs)
    assert df >= 1 / 3, df
    assert two_turn_games.config_of("heuristic", 2, 5, "one", decks="held-out")["setups"] == "held-out"
    assert two_turn_games.config_of("heuristic", 2, 5, "one")["setups"] == "varied"
    with pytest.raises(ValueError):
        two_turn_games.config_of("heuristic", 2, 5, "one", decks="nope")


def test_smoke_two_games():
    """Two real stepped fights (heuristic, small node cap) land in a dataset
    whose games replay to their recorded outcomes."""
    root = tempfile.mkdtemp(prefix="twoturn-smoke-")
    try:
        ds = two_turn_games.dataset("heuristic", 1, 7, "two", 1, root=root, log=lambda *a: None, max_nodes=2000)
        games = registry.load_games(ds, root)
        assert len(games) == 2 and [g["group"] for g in games] == [1, 2]
        for g in games:
            r = registry.replay(g)  # raises when the outcome differs
            assert r["won"] == g["outcome"]["won"] and "values" not in r
        assert registry.load_manifest(ds, root)["config"]["search"]["max_nodes"] == 2000
    finally:
        shutil.rmtree(root, ignore_errors=True)


class Found(Exception):
    pass


def test_finetune_source():
    """A `source` config takes its new and validation games from
    two_turn_games.dataset (depth from the kind) and the Ironclad
    validation and replay pool from the "varied" kind; `content` plus
    `source` is refused."""
    import finetune
    import stsnet
    calls = {"dataset": [], "games": []}

    def fake_dataset(player, n, seed, depth, threads, root=None, log=None, max_nodes=None, encounters=None,
                     decks="varied"):
        calls["dataset"].append((player, n, seed, depth, max_nodes))
        calls.setdefault("decks", []).append(decks)
        return f"ds-{depth}-{n}-{seed}"

    def fake_games(kind, n, seed, *a, **k):
        calls["games"].append((kind, n, seed))
        return f"games-{kind}-{n}-{seed}"

    def fake_encoded(*a, **k):
        raise Found

    import two_turn_games as ttg
    old = ttg.dataset, finetune.games, finetune.encoded
    ttg.dataset, finetune.games, finetune.encoded = fake_dataset, fake_games, fake_encoded
    try:
        cfg = {"name": "src", "source": {"kind": "two-turn", "player": "runs/x/model.pt@hpe0.01"},
               "game_seed": 41, "games": 1500, "n_val": 150, "pool": 10000, "seed": 1}
        parent = os.path.join(ROOT, "models", "value_effects.pt")
        try:
            finetune.finetune(parent, cfg, root="unused", log=lambda *a: None, threads=2)
        except Found:
            pass
        else:
            raise AssertionError("encoded not reached")
        assert calls["dataset"] == [("runs/x/model.pt@hpe0.01", 1500, 41, "two", None),
                                    ("runs/x/model.pt@hpe0.01", 150, 41 + finetune.VAL_OFFSET, "two", None)]
        assert calls["games"] == [("varied", 150, finetune.IRONCLAD_VAL_SEED), ("varied", 10000, finetune.POOL_SEED)]
        calls["dataset"].clear(), calls["games"].clear()
        one = {**cfg, "source": {"kind": "one-turn", "player": "runs/x/model.pt@hpe0.01"}}
        try:
            finetune.finetune(parent, one, root="unused", log=lambda *a: None, threads=2, max_nodes=2000)
        except Found:
            pass
        assert [c[3:] for c in calls["dataset"]] == [("one", 2000), ("one", 2000)]
        assert calls["decks"] == ["varied"] * 4
        calls["dataset"].clear(), calls["games"].clear()
        held = {**cfg, "source": {"kind": "one-turn", "player": "heuristic", "decks": "held-out"}}
        try:
            finetune.finetune(parent, held, root="unused", log=lambda *a: None, threads=2)
        except Found:
            pass
        assert calls["decks"][4:] == ["held-out", "held-out"]
        assert calls["games"] == [("varied", 150, finetune.IRONCLAD_VAL_SEED), ("varied", 10000, finetune.POOL_SEED)]
        try:
            finetune.finetune(parent, {**cfg, "content": "varied"}, root="unused", log=lambda *a: None)
        except ValueError as e:
            assert "source" in str(e) and "content" in str(e)
        else:
            raise AssertionError("content plus source accepted")
        try:
            finetune.finetune(parent, {**cfg, "source": {"kind": "three-turn", "player": "p"}}, root="unused",
                              log=lambda *a: None)
        except ValueError as e:
            assert "three-turn" in str(e)
        else:
            raise AssertionError("unknown source kind accepted")
    finally:
        ttg.dataset, finetune.games, finetune.encoded = old
    assert stsnet  # the parent loaded above is an effects net; vocab_for widened it (no error)


def test_arm_smoke():
    """`two_turn_round.py arm` with a tiny config: a fine-tune run under the
    temp root and a 2-sequence gauntlet file read against a 2-sequence
    control played by the parent net."""
    import subprocess
    root = tempfile.mkdtemp(prefix="twoturn-arm-")
    try:
        parent = os.path.join(ROOT, "models", "value_effects.pt").replace("\\", "/")
        cfg = {"name": "arm-smoke", "source": {"kind": "two-turn", "player": "heuristic"},
               "game_seed": 7, "games": 1, "n_val": 1, "pool": 1, "seed": 0, "epochs": 1}
        cfg_path = os.path.join(root, "arm.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        ctl = os.path.join(root, "ctl.json").replace("\\", "/")
        out = os.path.join(root, "out.json").replace("\\", "/")
        py = sys.executable
        r = subprocess.run([py, "-u", os.path.join(ROOT, "scripts", "gauntlet.py"), "play", parent + "@hpb0.01",
                            "--sequences", "2", "--threads", "1", "--out", ctl], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-2000:]
        r = subprocess.run([py, "-u", os.path.join(ROOT, "scripts", "two_turn_round.py"), "arm", "--config", cfg_path,
                            "--from", parent, "--against", ctl, "--out", out, "--threads", "1", "--max-nodes", "2000",
                            "--sequences", "2", "--root", root], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, (r.stdout[-2000:], r.stderr[-3000:])
        runs = [d for d in os.listdir(os.path.join(root, "runs")) if os.path.isdir(os.path.join(root, "runs", d))]
        assert len(runs) == 1 and os.path.exists(os.path.join(root, "runs", runs[0], "model.pt"))
        info = json.load(open(os.path.join(root, "runs", runs[0], "run.json"), encoding="utf-8"))
        assert info["parent"]["path"].endswith("value_effects.pt")
        body = json.load(open(out, encoding="utf-8"))
        assert len(body["sequences"]) == 2 and body["protocol"]["verdict"] == "open" and body["protocol"]["n"] == 2
        assert runs[0] in r.stdout and "open" in r.stdout
        # the run's config records the source as given, no max_nodes
        cfg_saved = json.load(open(os.path.join(root, "runs", runs[0], "config.json"), encoding="utf-8"))
        assert cfg_saved["source"] == cfg["source"] and "max_nodes" not in json.dumps(cfg_saved)
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(name, "ok")
