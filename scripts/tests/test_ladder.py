"""Tests for the champion ladder (scripts/ladder.py,
docs/specs/champion-ladder.md). Run with `python scripts/tests/test_ladder.py`
(plain asserts; every `test_*` function runs) or with pytest."""

import json
import math
import os
import shutil
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import bench_sets  # noqa: E402
import ladder  # noqa: E402

CONTRACT = os.path.join(os.path.dirname(__file__), "data", "contract")
NET = os.path.join(os.path.dirname(__file__), "..", "..", "runs", "2026-10-29-seed-check-r2-s1-1a789b2", "model.pt")


def seeds_in(x, out):
    if isinstance(x, dict):
        for k, v in x.items():
            if k == "seed" and isinstance(v, int):
                out.add(v)
            else:
                seeds_in(v, out)
    elif isinstance(x, list):
        for v in x:
            seeds_in(v, out)
    return out


def test_seeds_fresh():
    """Ladder seeds of blocks 0-2 are unique and outside every saved set's
    seeds and every calibration or test seed range."""
    cells = ladder.pool_cells()
    seeds = [s["seed"] for b in range(3) for s in ladder.block(b, cells)]
    assert len(seeds) == len(set(seeds)) == 3 * ladder.SEEDS_PER_BLOCK * len(cells)
    used = set()
    for name in os.listdir(bench_sets.BENCH):
        if name.endswith(".json"):
            with open(os.path.join(bench_sets.BENCH, name), encoding="utf-8") as f:
                seeds_in(json.load(f), used)
    assert not used & set(seeds)
    bases = [v for k, v in vars(bench_sets).items() if k.endswith("_SEED") and isinstance(v, int) and v > 10**6]
    lo, hi = min(seeds), max(seeds)
    for base in bases:  # a range runs base + cell * 100_000 + k, far below the next 1e15
        assert not (base <= lo < base + 10**12 or base <= hi < base + 10**12), base


def test_order_stratified():
    """Block 0 holds SEEDS_PER_BLOCK fights per cell; every prefix keeps each
    stratum within one fight of its share; the order repeats, and blocks
    differ."""
    cells = ladder.pool_cells()
    a, a2, b = ladder.block(0, cells), ladder.block(0, cells), ladder.block(1, cells)
    assert a == a2 and [s["seed"] for s in a] != [s["seed"] for s in b]
    per_cell = {}
    for s in a:
        per_cell[(s["half"], s["cell"])] = per_cell.get((s["half"], s["cell"]), 0) + 1
    assert set(per_cell.values()) == {ladder.SEEDS_PER_BLOCK} and len(per_cell) == len(cells)
    total = len(a)
    share = {}
    for s in a:
        share[(s["half"], s["group"])] = share.get((s["half"], s["group"]), 0) + 1
    assert len(share) == 6
    taken = {k: 0 for k in share}
    for n, s in enumerate(a, 1):
        taken[(s["half"], s["group"])] += 1
        for k, m in share.items():
            assert abs(taken[k] - m * n / total) <= 1, (n, k)


def test_llr_matches_replay():
    """Decision and stop index equal sprt_replay.sprt_paths' on synthetic
    sequences (both a pass and a fail)."""
    import sprt_replay
    rng = np.random.default_rng(3)
    for lead in (0.04, -0.03, 0.0):
        p = rng.random(6000)
        x = np.where(p < 0.25 + lead / 2, 1, np.where(p < 0.5, -1, 0)).astype(np.float64)
        (dec, stop), _ = sprt_replay.sprt_paths(x[None, :], ladder.D1, ladder.MIN_FIGHTS)
        verdict, (n, _, _) = ladder.decide([int(v) for v in x], cap=len(x))
        want = {1: "pass", -1: "fail", 0: "cap"}[int(dec[0])]
        assert verdict == want and n == int(stop[0]), (lead, verdict, n, want, stop)


def test_floor():
    """The held-out floor sits at -0.005: -0.01 refused, -0.005 and -0.004
    pass, no held-out pairs refused; fail and cap are untouched."""
    assert ladder.HELD_OUT_FLOOR == -0.005
    assert ladder.final_verdict("pass", -0.01) == "pass-held-out-fail"
    assert ladder.final_verdict("pass", -0.0051) == "pass-held-out-fail"
    assert ladder.final_verdict("pass", -0.005) == "pass"
    assert ladder.final_verdict("pass", -0.004) == "pass"
    assert ladder.final_verdict("pass", None) == "pass-held-out-fail"
    assert ladder.final_verdict("fail", -0.5) == "fail"
    assert ladder.final_verdict("cap", 0.1) == "inconclusive"


def test_identical_players_fail():
    verdict, (n, _, _) = ladder.decide([0] * 1000)
    assert verdict == "fail" and n == ladder.MIN_FIGHTS


def tiny_cells(n=60):
    cells = ladder.pool_cells()
    by = {}
    for c in cells:
        by.setdefault((c["half"], c["group"]), []).append(c)
    return [c for v in by.values() for c in v[:n // 6]]


def test_held_out_rule():
    """A pass whose held-out lead clears HELD_OUT_FLOOR promotes the
    candidate (the refusal is test_pass_with_held_out_loss)."""
    root = tempfile.mkdtemp()
    try:
        cand = os.path.join(CONTRACT, "tiny_effects.pt")
        def play(specs, player):  # held-out lead 0 (both lose every held-out fight), train +1
            return [s["half"] == "train" and player != ladder.HEURISTIC for s in specs]
        rec = ladder.run_test(cand, root=root, cells=tiny_cells(), log=lambda m: None, play=play)
        assert rec["verdict"] == "pass" and rec["promoted"], rec["verdict"]
        assert rec["by_half"]["held_out"]["lead"] == 0
        assert ladder.champion(root)["player"] == cand
        assert ladder.champion(root)["test"] == rec["id"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_pass_with_held_out_loss():
    """Train wins everything, held-out loses about 1 in 5 to the champion
    (seed k 0 of each cell): a pass on the pooled pairs, refused by the
    held-out rule."""
    root = tempfile.mkdtemp()
    try:
        cand = os.path.join(CONTRACT, "tiny_effects.pt")
        def play(specs, player):
            if player == ladder.HEURISTIC:
                return [s["half"] == "held_out" and s["seed"] % 50 == 0 for s in specs]
            return [s["half"] == "train" for s in specs]
        rec = ladder.run_test(cand, root=root, cells=tiny_cells(), log=lambda m: None, play=play)
        assert rec["verdict"] == "pass-held-out-fail", rec["verdict"]
        assert rec["by_half"]["held_out"]["lead"] < ladder.HELD_OUT_FLOOR
        assert not rec["promoted"] and ladder.champion(root)["player"] == ladder.HEURISTIC
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_refuses_champion_and_missing():
    for cand, err in ((ladder.HEURISTIC, ValueError), ("no/such/net.pt", FileNotFoundError),
                      ("models/value_effects.pt+no/such/net.pt", FileNotFoundError)):
        try:
            ladder.run_test(cand, root=tempfile.gettempdir() + "/ladder-none", log=lambda m: None)
            raise AssertionError("not refused")
        except err:
            pass


def test_plus_in_a_single_net_path():
    """A run directory named like `score+branch` is one net, not an ensemble."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", "runs/2026-10-25-hp+branch-s0-r1-0ae6866/model.pt")
    if not os.path.exists(path):
        return
    class Played(Exception):
        pass

    def play(specs, player):
        raise Played  # the existence check let it through

    try:
        ladder.run_test(path, root=tempfile.gettempdir() + "/ladder-none", play=play, promote=False,
                        log=lambda m: None)
    except FileNotFoundError as e:
        raise AssertionError(f"existing net refused: {e}")
    except Played:
        pass


def test_start_block():
    """Ladder-v2: ids 1 / 2 / 9 / 21 start at blocks 0 / 4 / 0 / 16 (8
    slots), two tests' first blocks share no seed, and a block past the
    cell seed spacing raises; ids are reserved in order."""
    assert [ladder.start_block(t) for t in ("0001", "0002", "0009", "0021")] == [0, 4, 0, 16]
    cells = tiny_cells()
    a = {s["seed"] for s in ladder.block(ladder.start_block("0001"), cells)}
    b = {s["seed"] for s in ladder.block(ladder.start_block("0002"), cells)}
    assert a and b and not a & b
    try:
        ladder.block(ladder.SEED_SPACING // ladder.SEEDS_PER_BLOCK, cells)
        raise AssertionError("not refused")
    except ValueError:
        pass
    root = tempfile.mkdtemp()
    try:
        assert [ladder.reserve_id(root) for _ in range(3)] == ["0001", "0002", "0003"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_champion_cache():
    """Two fake-play tests on the same blocks: the second never plays the
    champion and gets the same outcomes; real play of 10 fights alone equals
    their results inside a 30-fight batch (the cache's determinism
    assumption)."""
    root = tempfile.mkdtemp()
    try:
        cand = os.path.join(CONTRACT, "tiny_effects.pt")
        calls = []

        def play(specs, player):
            calls.append((player, len(specs)))
            return [s["half"] == "train" and (player != ladder.HEURISTIC or s["seed"] % 3 == 0) for s in specs]
        kw = dict(root=root, cells=tiny_cells(), log=lambda m: None, play=play, promote=False, first_block=0)
        a = ladder.run_test(cand, **kw)
        champ_calls = sum(1 for p, _ in calls if p == ladder.HEURISTIC)
        b = ladder.run_test(cand, **kw)
        assert champ_calls > 0 and sum(1 for p, _ in calls if p == ladder.HEURISTIC) == champ_calls
        assert (a["pairs"], a["lead"]) == (b["pairs"], b["lead"])
        assert len(os.listdir(os.path.join(root, "cache"))) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)
    specs = ladder.block(0, tiny_cells())[:30]
    whole = ladder.play_bench(specs, ladder.HEURISTIC, 2)
    alone = ladder.play_bench(specs[10:20], ladder.HEURISTIC, 2)
    assert whole[10:20] == alone


def test_fixed_n():
    """A test that decides early plays on to fixed_n pairs: the SPRT counts
    only its own pairs, `fixed` is the plain lead of the first fixed_n."""
    root = tempfile.mkdtemp()
    try:
        cand = os.path.join(CONTRACT, "tiny_effects.pt")
        def play(specs, player):
            return [s["half"] == "train" and (player != ladder.HEURISTIC or s["seed"] % 4 == 0) for s in specs]
        rec = ladder.run_test(cand, root=root, cells=tiny_cells(), log=lambda m: None, play=play, promote=False,
                              fixed_n=1500)
        with open(os.path.join(root, "tests", rec["id"] + ".json"), encoding="utf-8") as f:
            saved = json.load(f)
        pp = saved["pairs_played"]
        assert rec["pairs"] < 1000 and len(pp) == 1500
        assert sum(p["counted"] for p in pp) == rec["pairs"] and all(p["counted"] for p in pp[:rec["pairs"]])
        assert abs(rec["fixed"]["lead"] - np.mean([p["cand"] - p["champ"] for p in pp])) < 1e-12
        assert rec["fixed"]["n"] == 1500 and "fixed n 1500" in ladder.report(rec)
        assert not os.path.exists(os.path.join(root, "tests", rec["id"] + ".pending"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_runhp_draw_and_score():
    """Start HP inside its group's band, the same for a seed every time;
    HP lost on hand cases; run-HP blocks clear of the ladder's."""
    for group, (lo, hi) in ladder.HP_BANDS.items():
        hps = [ladder.run_hp({"group": group, "seed": s}, 80) for s in range(500)]
        assert min(hps) >= math.ceil(lo * 80) and max(hps) <= int(hi * 80) and len(set(hps)) > 5, group
    assert ladder.run_hp({"group": "elite", "seed": 7}, 80) == ladder.run_hp({"group": "elite", "seed": 7}, 80)
    assert ladder.hp_lost({"won": True, "hp_start": 50, "hp_end": 40}) == 10
    assert ladder.hp_lost({"won": False, "hp_start": 50, "hp_end": 0}) == 80
    assert ladder.RUNHP_BLOCK0 >= ladder.LADDER_SLOTS * ladder.BLOCKS_PER_TEST


def test_runhp_fake():
    """300 fake pairs: the candidate always wins losing 5 HP, the heuristic
    wins only train fights losing 10: score per pair hand-computed, file and
    log line written, opponent cached."""
    root = tempfile.mkdtemp()
    try:
        cand = os.path.join(CONTRACT, "tiny_effects.pt")
        def play(specs, player):
            if player == ladder.HEURISTIC:
                return [{"won": s["half"] == "train", "hp_start": s["hp"], "hp_end": s["hp"] - 10} for s in specs]
            return [{"won": True, "hp_start": s["hp"], "hp_end": s["hp"] - 5} for s in specs]
        rec = ladder.run_runhp(cand, n_pairs=300, root=root, play=play, cells=tiny_cells(), log=lambda m: None)
        with open(os.path.join(root, "runhp", rec["id"] + ".json"), encoding="utf-8") as f:
            pp = json.load(f)["pairs_played"]
        assert len(pp) == rec["pairs"] == 300
        for p in pp:
            assert p["score"] == (10 - 5 if p["half"] == "train" else p["hp"] + ladder.DEATH_PENALTY - 5)
        assert abs(rec["by_half"]["train"]["lead"] - 5) < 1e-9 and rec["cand_win"] == 1
        assert rec["all"]["lo"] < rec["all"]["lead"] < rec["all"]["hi"]
        with open(os.path.join(root, "runhp", "log.jsonl"), encoding="utf-8") as f:
            assert json.loads(f.readline())["id"] == rec["id"]
        assert len(os.listdir(os.path.join(root, "cache"))) == 1 and "run-HP" in ladder.report_runhp(rec)
        calls = []
        again = ladder.run_runhp(cand, n_pairs=300, root=root, cells=tiny_cells(), log=lambda m: None,
                                 play=lambda specs, player: calls.append(player) or play(specs, player))
        assert ladder.HEURISTIC not in calls and again["score"] == rec["score"]  # same fights, opponent cached
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_runhp_end_to_end_small():
    """The champion vs the heuristic, 120 real pairs at 2 threads."""
    root = tempfile.mkdtemp()
    try:
        rec = ladder.run_runhp(NET, n_pairs=120, threads=2, root=root, cells=tiny_cells(120), log=lambda m: None)
        assert rec["pairs"] == 120 and 0 < rec["opp_lost"] and rec["lost_corr"] is not None
        print(ladder.report_runhp(rec))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_old_record_report():
    """`report` reads a test record from before ladder-v2 (no `fixed`)."""
    rec = {"id": "0001", "candidate": "a.pt", "champion": "heuristic", "verdict": "fail", "promoted": False,
           "pairs": 200, "lead": -0.01, "by_half": {}, "by_type": {}, "by_half_type": {}}
    assert "fail" in ladder.report(rec)


def test_end_to_end_small():
    """Heuristic vs a round-2 net with cap 600: real play, test file and log
    line written, decision or cap at <= 600 pairs."""
    root = tempfile.mkdtemp()
    try:
        cand = NET
        rec = ladder.run_test(cand, cap=600, threads=4, root=root, cells=tiny_cells(120), log=lambda m: None)
        assert rec["pairs"] <= 600 and rec["verdict"] in ("pass", "fail", "inconclusive", "pass-held-out-fail")
        with open(os.path.join(root, "tests", rec["id"] + ".json"), encoding="utf-8") as f:
            saved = json.load(f)
        assert sum(p["counted"] for p in saved["pairs_played"]) == rec["pairs"]
        with open(os.path.join(root, "log.jsonl"), encoding="utf-8") as f:
            assert json.loads(f.readline())["id"] == rec["id"]
        assert "held_out" in rec["by_half"] and set(rec["by_type"]) <= set(ladder.GROUPS)
        print(ladder.report(rec))
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    names = [n for n in sorted(globals()) if n.startswith("test_")]
    for n in names:
        t0 = time.time()
        globals()[n]()
        print(f"ok {n} ({time.time() - t0:.1f}s)", flush=True)
    print(f"{len(names)} passed")


def test_runhp_two_turn_small():
    """The champion two turns deep vs the heuristic, 6 real pairs at 2
    threads: the record names the search and the partial file resumes."""
    root = tempfile.mkdtemp()
    try:
        cells = tiny_cells(6)
        rec = ladder.run_runhp(NET, n_pairs=6, threads=2, root=root, cells=cells, log=lambda m: None, two_turn=True)
        assert rec["pairs"] == 6 and rec["cand_search"].startswith("two-turn")
        played = lambda r: json.load(open(os.path.join(root, "runhp", r["id"] + ".json")))["pairs_played"]  # noqa: E731
        assert all(p["cand_lost"] >= 0 for p in played(rec))
        assert os.path.exists(os.path.join(root, "runhp", f"two-{ladder.file_sha(NET)[:12]}.partial.jsonl"))
        again = ladder.run_runhp(NET, n_pairs=6, threads=2, root=root, cells=cells, log=lambda m: None, two_turn=True)
        assert [p["cand_lost"] for p in played(again)] == [p["cand_lost"] for p in played(rec)]
        print(ladder.report_runhp(rec))
    finally:
        shutil.rmtree(root, ignore_errors=True)
