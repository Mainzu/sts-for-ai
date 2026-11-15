"""Generated enemies training pack (docs/specs/generated-pack.md)."""

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
         for f in ("act1-ironclad.json", "act1-monsters.json", "gen-enemies-train.json")]
STARTER = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]


def _load():
    for p in PACKS:
        selfplay.load_content(p)
    with open(gp.OUT, encoding="utf-8") as f:
        return json.load(f)


def test_file_is_the_writers_output():
    with open(gp.OUT, encoding="utf-8") as f:
        assert f.read() == gp.text(gp.generate())


def test_powers_are_the_benchs_training_split():
    pack = _load()
    bench = {p["id"]: p for p in json.loads(mm.gen_pack())["powers"] if p["id"] in mm.GEN}
    ids = [p["id"] for p in pack["powers"]]
    assert len(ids) == 18 and not set(ids) & set(gp.HELD_OUT) and set(ids) | set(gp.HELD_OUT) == set(bench)
    assert all(p == bench[p["id"]] for p in pack["powers"])
    assert len(pack["monsters"]) == 180
    for m in pack["monsters"]:
        mech = m["start_powers"][-1]["power"]
        k = mm.GEN[mech][0][2]
        assert max(1, k // 2) <= m["start_powers"][-1]["amount"] <= 2 * k


def test_encounters_load_and_play():
    pack = _load()
    names = ["gen:" + e["id"] for e in pack["encounters"]]
    assert sorted(e["group"] for e in pack["encounters"]) == ["elite"] * 2 + ["hallway"] * 8
    rng = np.random.default_rng(0)
    for name in names:
        for seed in range(20):
            c = sts.Combat(STARTER, name, seed=seed)
            mons = c.board()["monsters"]
            ge = [p["name"] for m in mons for p in m["powers"] if p["name"].startswith("GE-")]
            assert ge and set(ge) <= set(gp.TRAIN), (name, seed)
            for _ in range(400):
                if c.is_over():
                    break
                acts = c.legal_actions()
                c.step(acts[int(rng.integers(len(acts)))])
            assert c.is_over(), (name, seed)


def test_generated_share_bounded():
    _load()
    packs = [selfplay.load_content(p)[0] for p in PACKS]
    specs, groups = selfplay.make_specs(2000, 7, selfplay.varied_deck)
    out = selfplay.with_pack_encounters(specs, groups, packs)
    for g, want in ((selfplay.GROUPS.index("hallway"), 8 / 22), (selfplay.GROUPS.index("elite"), 2 / 5)):
        encs = [s[0] for s, gg in zip(out, groups) if gg == g]
        share = np.mean([e.startswith("gen:GP ") for e in encs])
        assert abs(share - want) < 0.03, (g, share, want)


def test_search_plays_each_encounter():
    pack = _load()
    specs, _ = selfplay.make_specs(1, 3, selfplay.varied_deck)
    s = specs[0]
    run = [("gen:" + e["id"], *s[1:]) for e in pack["encounters"]]
    res = sts.run("search", run, record=False, limit=4)
    assert len(res) == len(run)


def test_six_pack_is_the_writers_output_over_the_held_out_atoms():
    with open(gp.OUT_SIX, encoding="utf-8") as f:
        assert f.read() == gp.text(gp.generate(list(gp.SIX)))
        f.seek(0)
        six = json.load(f)
    with open(gp.OUT, encoding="utf-8") as f:
        full = json.load(f)
    assert sorted(p["id"] for p in six["powers"]) == sorted(gp.SIX) and set(gp.SIX) <= set(gp.TRAIN)
    atoms = lambda ms: ({m.split("-")[1] for m in ms}, {m.split("-")[2] for m in ms})  # noqa: E731
    assert all(a <= b for a, b in zip(atoms(gp.HELD_OUT), atoms(gp.SIX)))
    assert len(six["monsters"]) == 60
    # The same encounters and groups as the 18-mechanic pack, so the same generated share.
    assert [(e["id"], e["group"]) for e in six["encounters"]] == [(e["id"], e["group"]) for e in full["encounters"]]


def test_six_pack_loads_and_plays():
    # A fresh process: the 18-mechanic pack loaded above holds the same monster ids.
    code = (
        "import sys, json, numpy as np; sys.path.insert(0, 'scripts'); import selfplay, sts\n"
        "for p in ('act1-ironclad.json', 'act1-monsters.json', 'gen-enemies-six.json'):\n"
        "    selfplay.load_content('content/packs/' + p)\n"
        "pack = json.load(open('content/packs/gen-enemies-six.json', encoding='utf-8'))\n"
        "rng = np.random.default_rng(0)\n"
        "for e in pack['encounters']:\n"
        "    for seed in range(10):\n"
        f"        c = sts.Combat({STARTER!r}, 'gen:' + e['id'], seed=seed)\n"
        "        for _ in range(400):\n"
        "            if c.is_over(): break\n"
        "            a = c.legal_actions(); c.step(a[int(rng.integers(len(a)))])\n"
        "        assert c.is_over(), e['id']\n"
        "print('ok')\n")
    import subprocess
    r = subprocess.run([sys.executable, "-c", code], cwd=gp.ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr


def test_resolve_net_takes_the_one_match(tmp_path):
    (tmp_path / "2026-11-12-x-r1-abc").mkdir()
    (tmp_path / "2026-11-12-x-r1-abc" / "model.pt").write_text("")
    got = mm.resolve_net(str(tmp_path / "*-x-r1-*" / "model.pt") + "@tsl1")
    assert got.endswith("2026-11-12-x-r1-abc/model.pt@tsl1")
    assert mm.resolve_net("runs/a/model.pt@tsl1") == "runs/a/model.pt@tsl1"
    import pytest
    with pytest.raises(SystemExit):
        mm.resolve_net(str(tmp_path / "*-y-*" / "model.pt"))
