"""The wide generated enemies pack (docs/specs/wider-generators.md). Its own
file: with the old pack in the same process the registry's 236 pack
monsters overflow (each test file runs in its own process, scripts/test_full.py)."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))

import numpy as np  # noqa: E402

import gen_enemy_pack as gp  # noqa: E402
import mutate_monsters as mm  # noqa: E402
import selfplay  # noqa: E402
import sts  # noqa: E402

PACKS = [os.path.join(gp.ROOT, "content", "packs", f)
         for f in ("act1-ironclad.json", "act1-monsters.json", "gen-enemies-wide.json")]
STARTER = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]


def _load():
    for p in PACKS:
        selfplay.load_content(p)
    with open(gp.OUT_WIDE, encoding="utf-8") as f:
        return json.load(f)


def test_file_is_the_writers_output():
    with open(gp.OUT_WIDE, encoding="utf-8") as f:
        assert f.read() == gp.text(gp.generate(gp.TRAIN_WIDE, gp.wide_carriers(gp.TRAIN_WIDE)))


def test_powers_and_carriers():
    pack = _load()
    bench = {p["id"]: p for p in json.loads(mm.gen_pack())["powers"]}
    ids = [p["id"] for p in pack["powers"]]
    held = set(gp.HELD_OUT) | {m for k, v in mm.WIDE_SPLIT.items() if k != "train" for m in v}
    assert ids == gp.TRAIN_WIDE and len(ids) == 58 and not set(ids) & held
    assert set(ids) | held == set(bench) and all(p == bench[p["id"]] for p in pack["powers"])
    car = gp.wide_carriers(gp.TRAIN_WIDE)
    hall = [m for e in gp.WIDE_HALLWAYS for m in car[e]]
    assert sorted(hall) == sorted(gp.TRAIN_WIDE)  # each mechanic on exactly one hallway
    assert car["gremlin_nob"] == car["three_sentries"] == gp.TRAIN_WIDE
    assert len(pack["monsters"]) == 58 * 3
    for m in pack["monsters"]:
        mech = m["start_powers"][-1]["power"]
        k = mm.GEN_ALL[mech][0][2]
        assert max(1, k // 2) <= m["start_powers"][-1]["amount"] <= 2 * k


def test_encounters_load_and_play():
    pack = _load()
    assert sorted(e["group"] for e in pack["encounters"]) == ["elite"] * 2 + ["hallway"] * 4
    rng = np.random.default_rng(0)
    seen = set()
    for e in pack["encounters"]:
        for seed in range(12):
            c = sts.Combat(STARTER, "gen:" + e["id"], seed=seed)
            ge = [p["name"] for m in c.board()["monsters"] for p in m["powers"] if p["name"].startswith("GE-")]
            assert ge and set(ge) <= set(gp.TRAIN_WIDE), (e["id"], seed)
            seen |= set(ge)
            for _ in range(400):
                if c.is_over():
                    break
                acts = c.legal_actions()
                c.step(acts[int(rng.integers(len(acts)))])
            assert c.is_over(), (e["id"], seed)
    assert len(seen) > 30


def test_generated_share_bounded():
    _load()
    packs = [selfplay.load_content(p)[0] for p in PACKS]
    specs, groups = selfplay.make_specs(2000, 7, selfplay.varied_deck)
    out = selfplay.with_pack_encounters(specs, groups, packs)
    for g, want in ((selfplay.GROUPS.index("hallway"), 4 / 18), (selfplay.GROUPS.index("elite"), 2 / 5)):
        encs = [s[0] for s, gg in zip(out, groups) if gg == g]
        share = np.mean([e.startswith("gen:GP ") for e in encs])
        assert abs(share - want) < 0.03, (g, share, want)
