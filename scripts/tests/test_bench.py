"""Tests for the evaluation bench. Run with
`python scripts/tests/test_bench.py` or with pytest."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402
import bench_sets  # noqa: E402
import bench_decisions  # noqa: E402
import bench  # noqa: E402
import bench_probes  # noqa: E402


def files(d):
    return {n: open(os.path.join(d, n), "rb").read() for n in sorted(os.listdir(d))}


def test_generation_is_deterministic():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        bench_sets.write_sets(a)
        bench_sets.write_sets(b)
        fa, fb = files(a), files(b)
        assert fa and fa.keys() == fb.keys()
        for n in fa:
            assert fa[n] == fb[n], n


def test_halves_split_held_out_cards():
    for name, halves in bench_sets.build_sets().items():
        for spec in halves.get("train", []):
            assert not set(spec["deck"]) & bench_sets.HELD_OUT_ALL, (name, spec)
        for spec in halves.get("held_out", []):
            assert sum(c in bench_sets.HELD_OUT_ALL for c in spec["deck"]) >= 2, (name, spec)


def test_families_cover_every_encounter():
    fams = bench_sets.build_sets()["families"]
    for half in ("train", "held_out"):
        cells = {(s["family"], s["encounter"]) for s in fams[half]}
        assert cells == {(f, e) for f in bench_sets.FAMILIES for e in sts.encounter_names()}


def test_decks_are_legal():
    for name, halves in bench_sets.build_sets().items():
        for half, specs in halves.items():
            spec = specs[0]
            sts.Combat(spec["deck"], spec["encounter"], seed=spec["seed"], character=spec["character"])


def test_tight_set_uses_calibrated_hp():
    cal = bench_sets.load_calibration()
    hp = {(c["family"], c["half"], c["encounter"]): c["hp"] for c in cal["cells"]}
    excluded = {(c["family"], c["half"], c["encounter"]) for c in cal["excluded"]}
    assert hp and not hp.keys() & excluded
    assert len(hp) + len(excluded) == len(bench_sets.FAMILIES) * 2 * len(sts.encounter_names())
    tight = bench_sets.load_set("tight")
    seen = set()
    for half, specs in tight.items():
        for s in specs:
            key = (s["family"], half, s["encounter"])
            assert s["hp"] == hp[key], key
            seen.add(key)
    assert seen == hp.keys()


def test_tight_fights_win_about_half():
    """Fresh seeds (not the calibration seeds): search + heuristic wins
    40-60% of every calibrated (family, half, encounter)."""
    cal = bench_sets.load_calibration()
    n = bench_sets.TEST_GAMES
    cal_seeds = set()
    for i, _ in enumerate(bench_sets.cells()):
        cal_seeds.update(bench_sets.cell_seeds(i, bench_sets.CAL_SEED, bench_sets.FINAL_GAMES))
    by_hp = {}
    index = {c: i for i, c in enumerate(bench_sets.cells())}
    for c in cal["cells"]:
        key = (c["family"], c["half"], c["encounter"])
        seeds = bench_sets.cell_seeds(index[key], bench_sets.TEST_SEED, n)
        assert not cal_seeds & set(seeds)
        by_hp.setdefault(c["hp"], []).append((key, seeds))
    bad = []
    for hp, group in sorted(by_hp.items()):
        specs = [(k[2], bench_sets.cell_deck(k[0], k[1]), s) for k, seeds in group for s in seeds]
        res = sts.run("search", specs, limit=bench_sets.LIMIT, hp=hp)
        for j, (key, _) in enumerate(group):
            wr = sum(r["won"] for r in res[j * n:(j + 1) * n]) / n
            if not 0.4 <= wr <= 0.6:
                bad.append((key, hp, wr))
    assert not bad, bad


def test_old_sets_unchanged():
    """Tight fights v2 leaves the v1 sets byte-identical to the saved ones."""
    with tempfile.TemporaryDirectory() as d:
        bench_sets.write_sets(d)
        for n in ("standard", "families", "tight"):
            with open(os.path.join(d, n + ".json"), "rb") as a:
                with open(os.path.join(bench_sets.BENCH, n + ".json"), "rb") as b:
                    assert a.read() == b.read(), n


SET_HASHES = {  # sha256 of the saved sets before the Silent tight set (warm-start step 1)
    "standard": "1376a40cf40aa20eeceafc0d852f83678b03865f08512c14ac8480bcdb0b4a26",
    "families": "2531748125a256366b22179635bc2ded452bf6af2d35f0e54ecea777b044b7d1",
    "tight": "553767b7f7af415b291ecaaf252ac7978c16a29b2768bd9aa5bea4fd88e7e909",
    "tight2": "7fa7281f05ed28ff546ab6a22dd050c63ed13704914a9a1626ab6fd9ebb0074d",
    "tight_bosses": "de89fdee3f00bb22a0cba6d257069a08a8c6ed4775168fe89144895fc0c89944",
}


def test_sets_unchanged():
    """The saved sets and a fresh build of them keep their hashes."""
    import hashlib
    with tempfile.TemporaryDirectory() as d:
        bench_sets.write_sets(d)
        for n, h in SET_HASHES.items():
            for folder in (d, bench_sets.BENCH):
                with open(os.path.join(folder, n + ".json"), "rb") as f:
                    assert hashlib.sha256(f.read()).hexdigest() == h, (folder, n)


def check_tight2(cal2, cal, sets, seeds):
    """The v2 set built from `cal2`: legal halves, cells at their
    calibrated HP in order (families first), `seeds` specs per cell with
    its index, encounters filled to the quota but for listed shortfalls,
    and test seeds apart from every calibration and v1 seed."""
    per_enc, encs = cal2["per_encounter"], sts.encounter_names()
    v2 = sets["tight2"]
    j = 0
    for half, specs in v2.items():
        fam = [c for c in cal["cells"] if c["half"] == half]
        drawn = [c for c in cal2["cells"] if c["half"] == half]
        assert len(specs) == (len(fam) + len(drawn)) * seeds
        for k, c in enumerate(fam + drawn):
            cell = specs[k * seeds:(k + 1) * seeds]
            assert {s["cell"] for s in cell} == {k} and {s["hp"] for s in cell} == {c["hp"]}
            assert {s["encounter"] for s in cell} == {c["encounter"]}
            assert [s["seed"] for s in cell] == bench_sets.cell_seeds(j, bench_sets.TEST2_SEED, seeds)
            assert ("family" in c) == ("family" in cell[0])
            j += 1
        short = cal2["short"].get(half, {})
        for e in encs:
            assert sum(c["encounter"] == e for c in drawn) == per_enc - short.get(e, 0), (half, e)
        for s in specs:  # decks: v1's rules, at varied size for drawn cells
            cards = s["deck"][len(bench_sets.selfplay.STARTER):]
            if half == "train":
                assert not set(cards) & bench_sets.HELD_OUT_ALL
            else:
                assert sum(c in bench_sets.HELD_OUT_ALL for c in cards) >= 2
            if "family" not in s:
                assert 3 <= len(cards) <= 15
    test = {s["seed"] for specs in v2.values() for s in specs}
    # calibration seeds: CAL2_SEED + cell * 100_000 + k over the tried cells, all below TEST2_SEED
    assert bench_sets.CAL2_SEED + cal2["tried"] * 100_000 <= bench_sets.TEST2_SEED <= min(test)
    old = {s["seed"] for name in ("standard", "families", "tight") for h in sets[name].values() for s in h}
    assert not test & old and max(old) < bench_sets.CAL2_SEED
    # self-play's combat seeds: sts.make_specs hashes its seed (selfplay: spec seed * 10 + group) to about
    # seed * 1,000,003; spec seeds up to 10^6 (learn: data seed + ROUND_SEED * round + the sweep's round seed)
    selfplay_max = max(s for *_, s in sts.make_specs(bench_sets.selfplay.GROUPS[-1], 100, extra=0, seed=10**7 + 9))
    assert selfplay_max < bench_sets.CAL2_SEED


def test_tight2_build():
    """A tiny v2 calibration (1 cell per encounter and half, few games)
    builds a set that follows the rules and regenerates byte-identically."""
    cal = bench_sets.load_calibration()
    cal2 = bench_sets.calibrate2(per_enc=1, bisect_games=20, final_games=40, log=lambda *_: None)
    assert cal2["cells"] and cal2["tried"] >= 2 * len(sts.encounter_names())
    sets = {**bench_sets.build_sets(cal), "tight2": bench_sets.tight2_set(cal2, cal, seeds=3)}
    check_tight2(cal2, cal, sets, 3)
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        for d in (a, b):
            bench_sets.dump(os.path.join(d, "tight2.json"), "tight2", bench_sets.tight2_set(cal2, cal, seeds=3))
        assert files(a) == files(b)
    # a top-up: one encounter short again, filled from fresh decks; earlier cells and their order kept
    gone = next(k for k, c in enumerate(cal2["cells"]) if c["half"] == "held_out")
    e = cal2["cells"][gone]["encounter"]
    prev = {**cal2, "cells": cal2["cells"][:gone] + cal2["cells"][gone + 1:], "short": {**cal2["short"], "held_out": {**cal2["short"].get("held_out", {}), e: 1}}}
    up = bench_sets.calibrate2(bisect_games=20, final_games=40, log=lambda *_: None, prev=prev)
    assert up["cells"][:len(prev["cells"])] == prev["cells"] and up["topups"] == 1 and up["tried"] > cal2["tried"]
    assert up["excluded"][:len(cal2["excluded"])] == cal2["excluded"]
    new = up["cells"][len(prev["cells"]):]
    assert all(c["encounter"] in prev["short"][c["half"]] for c in new)
    check_tight2(up, cal, {**sets, "tight2": bench_sets.tight2_set(up, cal, seeds=3)}, 3)


def test_tight2_saved():
    """The saved v2 set follows the same rules (once calibrated)."""
    cal2 = bench_sets.load_calibration2()
    sets = bench_sets.build_sets()
    check_tight2(cal2, bench_sets.load_calibration(), sets, bench_sets.SEEDS2)
    assert sets["tight2"] == bench_sets.load_set("tight2")


def test_boss_tight_set():
    """A tiny boss calibration (1 cell per new boss and half, few games)
    builds a boss set for those bosses only, group boss, with seeds apart
    from tight2's, tight_silent's and its own calibration's, regenerating
    byte-identically."""
    cal_b = bench_sets.calibrate_bosses(per_enc=1, bisect_games=20, final_games=40, log=lambda *_: None)
    assert cal_b["cells"] and cal_b["tried"] >= 2 * len(bench_sets.NEW_BOSSES)
    top = bench_sets.selfplay.max_hp("ironclad")
    assert all(1 <= c["hp"] <= top and c["encounter"] in bench_sets.NEW_BOSSES for c in cal_b["cells"])
    tight = bench_sets.tight_bosses_set(cal_b, seeds=3)
    assert list(tight) == ["train", "held_out"]
    for half, specs in tight.items():
        cells = [c for c in cal_b["cells"] if c["half"] == half]
        assert len(specs) == 3 * len(cells)
        for k, c in enumerate(cells):
            cell = specs[3 * k:3 * (k + 1)]
            assert {s["cell"] for s in cell} == {k} and {s["hp"] for s in cell} == {c["hp"]}
            assert {s["encounter"] for s in cell} == {c["encounter"]} and cell[0]["deck"] == c["deck"]
        assert all(s["character"] == "ironclad" and s["group"] == "boss" for s in specs)
    seeds = {s["seed"] for specs in tight.values() for s in specs}
    older = {s["seed"] for n in ("tight2", "tight_silent") for specs in bench_sets.load_set(n).values() for s in specs}
    assert not seeds & older and max(older) < bench_sets.CAL_B_SEED
    assert bench_sets.CAL_B_SEED + cal_b["tried"] * 100_000 <= bench_sets.TEST_B_SEED <= min(seeds)
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        for d in (a, b):
            bench_sets.dump(os.path.join(d, "tight_bosses.json"), "tight_bosses", bench_sets.tight_bosses_set(cal_b))
        assert files(a) == files(b)


def test_silent_tight_set():
    """A tiny Silent calibration (1 cell per encounter and tier, few games)
    builds a Silent set at Silent HPs, with seeds apart from tight2's and
    from its own calibration's, regenerating byte-identically."""
    cal_s = bench_sets.calibrate_silent(per_enc=1, bisect_games=20, final_games=40, log=lambda *_: None)
    assert cal_s["cells"] and cal_s["tried"] >= 2 * len(sts.encounter_names())
    top = bench_sets.selfplay.max_hp("silent")
    assert all(1 <= c["hp"] <= top for c in cal_s["cells"])
    tight = bench_sets.tight_silent_set(cal_s, seeds=3)
    assert list(tight) == ["silent_a", "silent_b"]
    for half, specs in tight.items():
        cells = [c for c in cal_s["cells"] if c["half"] == half]
        assert len(specs) == 3 * len(cells)
        for k, c in enumerate(cells):
            cell = specs[3 * k:3 * (k + 1)]
            assert {s["cell"] for s in cell} == {k} and {s["hp"] for s in cell} == {c["hp"]}
            assert {s["encounter"] for s in cell} == {c["encounter"]} and cell[0]["deck"] == c["deck"]
        for s in specs:
            assert s["character"] == "silent" and 1 <= s["hp"] <= top
            assert s["deck"][:len(bench_sets.transfer.STARTER)] == bench_sets.transfer.STARTER
    seeds = {s["seed"] for specs in tight.values() for s in specs}
    tight2 = {s["seed"] for specs in bench_sets.load_set("tight2").values() for s in specs}
    assert not seeds & tight2 and max(tight2) < bench_sets.CAL_S_SEED
    assert bench_sets.CAL_S_SEED + cal_s["tried"] * 100_000 <= bench_sets.TEST_S_SEED <= min(seeds)
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        for d in (a, b):
            bench_sets.dump(os.path.join(d, "tight_silent.json"), "tight_silent", bench_sets.tight_silent_set(cal_s))
        assert files(a) == files(b)


def test_decision_sets_are_deterministic():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        bench_decisions.write_decisions(a)
        bench_decisions.write_decisions(b)
        fa, fb = files(a), files(b)
        assert fa and fa.keys() == fb.keys()
        for n in fa:
            assert fa[n] == fb[n], n


def test_replay_reproduces_decision_states():
    """Replaying a saved decision (spec + action prefix) gives the state the
    sampling game was in: same board, same options, same features."""
    decisions, states = bench_decisions.sample_decisions(keep_states=True)
    f = sts.Features("effects")
    for half in decisions:
        for d, want in list(zip(decisions[half], states[half]))[::97]:
            got = bench_decisions.replay(d)
            assert got.render() == want.render(), d
            assert [o[0] for o in got.options(bench_decisions.REF["limit"])] ==                 [o[0] for o in want.options(bench_decisions.REF["limit"])]
            fg, fw = f.encode([got]), f.encode([want])
            for k in fw:
                assert (fg[k] == fw[k]).all(), k
            assert len(got.legal_actions()) >= 2


def test_reference_has_zero_self_regret():
    """Recomputing the reference on saved decisions matches the cache, and
    the reference's own pick has regret 0."""
    ref = bench_decisions.load_reference()
    for half, rows in ref["halves"].items():
        for r in rows[::50]:
            d = bench_decisions.load_decisions()[half][r["index"]]
            values = bench_decisions.reference_values(bench_decisions.replay(d))
            assert values == r["values"], (half, r["index"])
            pick = bench_decisions.reference_pick(bench_decisions.replay(d))
            assert bench_decisions.regret(r, pick) == 0.0
            assert r["contested"] == (max(r["values"]) - min(r["values"]) >= bench_decisions.CONTESTED)


def test_reference_scores_itself_perfectly():
    """Fed the reference's own picks and values, regret is 0 and ranking
    accuracy 100%, on every subset."""
    ref = bench_decisions.load_reference()
    for half, rows in ref["halves"].items():
        picks = [r["options"][max(range(len(r["values"])), key=r["values"].__getitem__)][0] for r in rows]
        m = bench.decision_metrics(rows, picks, [r["values"] for r in rows], [None] * len(rows), [0.0] * len(rows))
        for sub in bench.SUBSETS:
            assert m[sub]["regret"][0] == 0.0, (half, sub)
            assert m[sub]["ranking"][0] == 1.0, (half, sub)


def test_random_values_rank_at_chance():
    """Random option values order contested pairs right about half the time.
    (A random leaf evaluator searched through does better, ~70%: search
    scores wins and deaths exactly.)"""
    import numpy as np
    rng = np.random.default_rng(0)
    for half, rows in bench_decisions.load_reference()["halves"].items():
        values = [list(rng.random(len(r["values"]))) for r in rows]
        picks = [r["options"][int(np.argmax(v))][0] for r, v in zip(rows, values)]
        m = bench.decision_metrics(rows, picks, values, [None] * len(rows), [0.0] * len(rows))
        acc = m["contested"]["ranking"][0]
        assert 0.45 <= acc <= 0.55, (half, acc)


def test_bench_rerun_is_identical():
    """Two bench runs of the same config write byte-identical results."""
    with tempfile.TemporaryDirectory() as d:
        a, b = os.path.join(d, "a.json"), os.path.join(d, "b.json")
        bench.main(["--evaluator", "heuristic", "--out", a, "--quick"])
        bench.main(["--evaluator", "heuristic", "--out", b, "--quick"])
        assert open(a, "rb").read() == open(b, "rb").read()


def test_alias_audit_flags_planted_pair():
    """Two Cultist openings whose boards match (same hand, HP, intent) but
    whose seeds differ share a feature key; as planted siblings, values 0.5
    apart are flagged, 0.03 apart are not, and a different board stays
    apart."""
    deck = ["Strike"] * 3 + ["Defend"] * 2
    a = sts.Combat(deck, "cultist", seed=1)
    b = next(c for c in (sts.Combat(deck, "cultist", seed=s) for s in range(2, 200))
             if c.render() == a.render())
    other = sts.Combat(deck, "jaw_worm", seed=1)
    f = sts.Features("effects")
    keys = bench_probes.feature_keys(f, [a, b, other])
    assert keys[0] == keys[1] and keys[0] != keys[2]
    flagged = bench_probes.aliased_pairs(keys, [0.0, 0.5, 1.0])
    assert [(i, j) for i, j, _ in flagged] == [(0, 1)]
    assert abs(flagged[0][2] - 0.5) < 1e-9
    assert bench_probes.aliased_pairs(keys, [0.0, 0.03, 1.0]) == []


def test_alias_audit_covers_every_sibling_pair():
    """The audit counts every pair of options of every saved decision."""
    decisions = bench_decisions.load_decisions()
    reference = bench_decisions.load_reference()
    ref = {"halves": {h: rows[:20] for h, rows in reference["halves"].items()}}
    out = bench_probes.aliasing(sts.Features("effects"), decisions, ref, "effects")
    for half, rows in ref["halves"].items():
        expect = sum(len(r["options"]) * (len(r["options"]) - 1) // 2 for r in rows)
        assert out["halves"][half]["pairs"] == expect, half


def test_probe_reference_orders_match_expected():
    """Every probe's good action beats its bad one by at least CONTESTED in
    reference value, so a pass or fail isn't down to noise."""
    assert len(bench_probes.PROBES) >= 12
    for p in bench_probes.PROBES:
        good, bad = bench_probes.reference_pair(p)
        assert good - bad >= bench_decisions.CONTESTED, (p["name"], good, bad)


def test_evaluator_options_group_like_the_reference():
    """The evaluator's search groups options exactly as the reference does,
    so ranking accuracy never pairs a reference option with itself."""
    decisions = bench_decisions.load_decisions()
    for half, rows in bench_decisions.load_reference()["halves"].items():
        for r in rows[:50]:
            c = bench_decisions.replay(decisions[half][r["index"]])
            mine = sorted(sorted(bench_decisions.encode_action(a) for a in acts) for acts, _, _ in c.options(bench.LIMIT))
            assert mine == sorted(sorted(o) for o in r["options"]), (half, r["index"])


SNAPSHOT = os.path.join(os.path.dirname(__file__), "data", "bench_quick_heuristic.json")


def quick_heuristic(path):
    bench.main(["--evaluator", "heuristic", "--out", path, "--quick"])
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_bench_unchanged():
    """The heuristic's quick bench, minus the `puzzles` set, is byte-identical
    to the snapshot taken before the exact-solver work (docs/specs/
    exact-solver.md, step 1). Regenerate only for an intended bench change:
    python scripts/bench.py --evaluator heuristic --quick --out scripts/tests/data/bench_quick_heuristic.json"""
    with tempfile.TemporaryDirectory() as d:
        result = quick_heuristic(os.path.join(d, "now.json"))
        result["sets"].pop("puzzles", None)
        bench.write(os.path.join(d, "trimmed.json"), result)
        assert open(os.path.join(d, "trimmed.json"), "rb").read() == open(SNAPSHOT, "rb").read()


def test_bench_compare_reads_old_format():
    """Comparing an old result file (no `puzzles` set) with a new one, in
    either order, prints the tables instead of failing."""
    import contextlib
    import io
    import bench_compare
    with tempfile.TemporaryDirectory() as d:
        now = os.path.join(d, "now.json")
        quick_heuristic(now)
        for files in ([SNAPSHOT, now], [now, SNAPSHOT]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                bench_compare.main(files)
            assert "tight / train" in out.getvalue(), files
            assert "puzzles / train" in out.getvalue(), files  # shown from the new file


def test_puzzle_metrics():
    """At the bench puzzles: exact values score accuracy 1, regret 0 and
    ranking 1; random option values rank at chance; a random leaf evaluator
    searched through ranks near its floor (one-turn search sees most
    endgames' last turn exactly, so the floor is higher than at the
    decisions' ~0.72)."""
    import numpy as np
    puzzles = bench.load_puzzles()
    rng = np.random.default_rng(0)
    random_ev = bench.load_evaluator("bench:random_evaluator")
    searched = bench.puzzle_quality(random_ev, puzzles)
    for half, rows in puzzles["halves"].items():
        exact = [[o[1] for o in r["options"]] for r in rows]
        planted = bench.puzzle_half(rows, [int(np.argmax(x)) for x in exact], exact)
        for name, m in planted.metrics.items():
            want = 0.0 if name.startswith("regret") else 1.0
            assert m is not None and m[0] == want, (half, name, m)
        values = [list(rng.random(len(x))) for x in exact]
        chance = bench.puzzle_half(rows, [int(np.argmax(v)) for v in values], values)
        assert 0.45 <= chance.metrics["ranking.all"][0] <= 0.55, (half, chance.metrics["ranking.all"])
        floor = searched[half].metrics["ranking.contested"][0]
        assert 0.72 <= floor <= 0.87, (half, floor)  # measured 0.77-0.82
        assert planted.counts["puzzles.all"] == len(rows) == puzzles["per_half"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(f"{len(tests)} passed")
